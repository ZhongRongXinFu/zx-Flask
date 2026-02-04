import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Blueprint, request, jsonify, Response, stream_with_context, g
from utils.mysql import connect
from utils.quota_logger import log_quota_change
from utils.login import login_required
import time
import json
import hashlib
from datetime import datetime
import pymysql

from settings import WX_OFFER_ID, WX_MIDAS_ENV
from utils.wechat import get_openid, get_paySig, get_signature

payment_page = Blueprint('payment', __name__)


ENV_TYPE = 1  # 0-正式环境 1-沙箱环境

@payment_page.route("/", methods=["GET"])
def index():
    return jsonify({
        "code": 200, "message": "Payment open server is running"
    })

@payment_page.route("/midas/recharge/create/", methods=["POST"])
@login_required
def midas_recharge_create():
    data = request.get_json()
    code = data.get("code")
    plan = data.get("plan")
    if not all([code, plan]):
        return jsonify({"code": 400, "message": "缺少必要参数: code, plan"}), 400
    temp = get_openid(code)
    openid = temp.get("openid")
    session_key = temp.get("session_key")
    if not all([openid, session_key]):
        return jsonify({"code": 400, "message": "获取openid失败"}), 400
    # print(plan, openid, session_key)

    user = g.current_user
    user_uuid = user["uuid"]
    user_ip = request.remote_addr

    connection = connect()
    with connection.cursor(pymysql.cursors.DictCursor) as cursor:
        # 1. 查询套餐信息
        query_package = "SELECT id, package_name, quota_amount, price, description FROM ai_package WHERE package_id = %s AND is_active = 1"
        cursor.execute(query_package, (plan,))
        package = cursor.fetchone()
        
        if not package:
            return jsonify({
                "code": 404,
                "message": f"套餐 {plan} 不存在或已禁用"
            }), 404
        
        # 2. 生成订单号
        timestamp = str(int(time.time()))
        random_str = hashlib.md5(f"{user_uuid}{openid}{time.time()}".encode()).hexdigest()[:8].upper()
        order_no = f"ZX{timestamp}{random_str}"
        
        # 3. 插入订单记录
        insert_order = """
            INSERT INTO recharge_order 
            (order_no, user_id, uuid, plan, quota_amount, price, status, user_ip, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        cursor.execute(insert_order, (
            order_no,
            user["id"],
            user_uuid,
            plan,
            package['quota_amount'],
            package['price'],
            0,  # 状态: 0-待支付
            user_ip
        ))
        connection.commit()
        
        # 4. 获取订单ID
        cursor.execute("SELECT id FROM recharge_order WHERE order_no = %s", (order_no,))
        order_result = cursor.fetchone()
        order_id = order_result['id']
        signData = json.dumps({
            "offerId": WX_OFFER_ID,
            "buyQuantity": 1,
            "env": WX_MIDAS_ENV,
            "currencyType": "CNY",
            "productId": plan,
            "goodsPrice": package['price'],
            "outTradeNo": order_no,
            "attach": user_uuid,
        }, separators=(',', ':'))

        signature = get_signature(session_key, signData)
        paySig = get_paySig(session_key, 'requestVirtualPayment', signData)
        
        # 5. 返回订单信息
        return jsonify({
            "code": 200,
            "message": "success",
            "data": {
                "order_no": order_no,
                "quota_amount": package['quota_amount'],
                "signature": signature,
                "paySig": paySig,
                "signData": signData

            }
        }), 200

    return jsonify({"code": 400, "message": "服务出错辣"})