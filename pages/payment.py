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


@payment_page.route("/list/", methods=["GET"])
@login_required
def payment_list():
    """
    获取用户的订单列表
    
    查询参数:
    - page: 页码，默认1
    - page_size: 每页数量，默认10，最大100
    - status: 订单状态过滤（可选），0-待支付, 2-已支付, 3-已完成等
    
    返回:
    {
        "code": 200,
        "message": "success",
        "data": {
            "total": 总订单数,
            "page": 当前页,
            "page_size": 每页数量,
            "orders": [
                {
                    "id": 订单ID,
                    "order_no": "订单号",
                    "plan": "套餐ID",
                    "quota_amount": 购买额度,
                    "price": 订单金额(分),
                    "status": 订单状态,
                    "status_text": "状态描述",
                    "created_at": "创建时间",
                    "pay_time": "支付时间",
                    "complete_time": "完成时间"
                }
            ]
        }
    }
    """
    user = g.current_user
    user_id = user["id"]
    
    # 获取分页参数
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 10, type=int)
    status_filter = request.args.get("status", None, type=int)
    
    # 参数验证
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 10
    
    # 状态描述映射
    status_map = {
        0: "待支付",
        1: "支付中",
        2: "已支付",
        3: "已完成",
        4: "已取消",
        5: "已退款"
    }
    
    try:
        connection = connect()
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # 构建查询条件
            where_clause = "WHERE user_id = %s"
            params = [user_id]
            
            if status_filter is not None:
                where_clause += " AND status = %s"
                params.append(status_filter)
            
            # 1. 查询总数
            count_sql = f"SELECT COUNT(*) as total FROM recharge_order {where_clause}"
            cursor.execute(count_sql, params)
            total = cursor.fetchone()['total']
            
            # 2. 计算分页
            total_pages = (total + page_size - 1) // page_size
            if page > total_pages and total_pages > 0:
                page = total_pages
            
            offset = (page - 1) * page_size
            
            # 3. 查询订单列表
            query_sql = f"""
                SELECT 
                    id, order_no, plan, quota_amount, price, status,
                    created_at, pay_time, complete_time
                FROM recharge_order 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([page_size, offset])
            cursor.execute(query_sql, params)
            orders = cursor.fetchall()
            
            # 4. 格式化订单数据
            formatted_orders = []
            for order in orders:
                formatted_order = {
                    "id": order['id'],
                    "order_no": order['order_no'],
                    "plan": order['plan'],
                    "quota_amount": order['quota_amount'],
                    "price": order['price'],
                    "price_yuan": round(order['price'] / 100, 2),  # 转换为元
                    "status": order['status'],
                    "status_text": status_map.get(order['status'], "未知"),
                    "created_at": order['created_at'].strftime("%Y-%m-%d %H:%M:%S") if order['created_at'] else None,
                    "pay_time": order['pay_time'].strftime("%Y-%m-%d %H:%M:%S") if order['pay_time'] else None,
                    "complete_time": order['complete_time'].strftime("%Y-%m-%d %H:%M:%S") if order['complete_time'] else None
                }
                formatted_orders.append(formatted_order)
            
            connection.close()
            
            return jsonify({
                "code": 200,
                "message": "success",
                "data": {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "orders": formatted_orders
                }
            }), 200
            
    except pymysql.Error as db_error:
        print(f"数据库错误: {str(db_error)}")
        return jsonify({
            "code": 500,
            "message": f"数据库错误: {str(db_error)}"
        }), 500
    except Exception as e:
        print(f"查询订单列表异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "code": 500,
            "message": f"查询失败: {str(e)}"
        }), 500


@payment_page.route("/delete/", methods=["POST"])
@login_required
def payment_delete():
    """
    删除未支付的订单
    
    请求参数:
    - order_no: 订单号（必填）
    
    说明:
    - 只能删除状态 < 2（待支付、支付中）的订单
    - 已支付、已完成、已退款的订单不能删除
    
    返回:
    {
        "code": 200,
        "message": "success",
        "data": {
            "order_no": "删除的订单号",
            "status": "订单原状态"
        }
    }
    """
    data = request.get_json() or {}
    order_no = data.get("order_no")
    
    if not order_no:
        return jsonify({
            "code": 400,
            "message": "缺少必要参数: order_no"
        }), 400
    
    user = g.current_user
    user_id = user["id"]
    
    try:
        connection = connect()
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. 查询订单是否存在且属于该用户
            query_order = "SELECT id, status, order_no FROM recharge_order WHERE order_no = %s AND user_id = %s"
            cursor.execute(query_order, (order_no, user_id))
            order = cursor.fetchone()
            
            if not order:
                return jsonify({
                    "code": 404,
                    "message": f"订单不存在或不属于该用户: {order_no}"
                }), 404
            
            # 2. 检查订单状态（只允许删除status < 2的订单）
            order_status = order['status']
            
            if order_status >= 2:
                status_map = {
                    0: "待支付",
                    1: "支付中",
                    2: "已支付",
                    3: "已完成",
                    4: "已取消",
                    5: "已退款"
                }
                return jsonify({
                    "code": 403,
                    "message": f"无法删除已支付的订单 (当前状态: {status_map.get(order_status, '未知')})",
                    "data": {
                        "order_no": order_no,
                        "status": order_status
                    }
                }), 403
            
            # 3. 删除订单
            delete_order = "DELETE FROM recharge_order WHERE id = %s"
            cursor.execute(delete_order, (order['id'],))
            connection.commit()
            
            connection.close()
            
            return jsonify({
                "code": 200,
                "message": "success",
                "data": {
                    "order_no": order_no,
                    "status": order_status
                }
            }), 200
            
    except pymysql.Error as db_error:
        print(f"数据库错误: {str(db_error)}")
        return jsonify({
            "code": 500,
            "message": f"数据库错误: {str(db_error)}"
        }), 500
    except Exception as e:
        print(f"删除订单异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "code": 500,
            "message": f"删除失败: {str(e)}"
        }), 500