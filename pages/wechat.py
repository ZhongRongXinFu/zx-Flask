import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uuid
import hashlib
import json
import time
from flask import Flask, Blueprint, Response, stream_with_context, request, jsonify
from utils.token import *
from utils.account import *
from utils.wechat import *
from utils.account import account_check_phone_openid, account_create_temp, account_update_by_uuid
from utils.login import login_required, op_required
from utils.mysql import connect
import pymysql

wechat_page = Blueprint('wechat', __name__)


def handle_midas_payment_callback(msg_data):
    """
    处理米大师支付回调
    
    Args:
        msg_data: 完整的消息数据（xpay_goods_deliver_notify）
        
    Returns:
        dict: {"ErrCode": 0, "ErrMsg": "success"} 或错误信息
    """
    try:
        # 获取数据库连接
        conn = connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 提取消息字段
        user_openid = msg_data.get("OpenId")
        out_trade_no = msg_data.get("OutTradeNo")  # 业务订单号
        env = msg_data.get("Env")  # 0-正式环境 1-沙箱环境
        
        # 提取微信支付信息
        wechat_pay_info = msg_data.get("WeChatPayInfo", {})
        mch_order_no = wechat_pay_info.get("MchOrderNo")  # 微信支付商户单号
        transaction_id = wechat_pay_info.get("TransactionId")  # 微信支付订单号
        paid_time = wechat_pay_info.get("PaidTime")  # 支付时间戳
        
        # 提取道具信息
        goods_info = msg_data.get("GoodsInfo", {})
        product_id = goods_info.get("ProductId")  # 道具ID（对应package_id）
        quantity = goods_info.get("Quantity", 1)  # 购买数量
        orig_price = goods_info.get("OrigPrice")  # 原始价格（分）
        actual_price = goods_info.get("ActualPrice")  # 实际支付价格（分）
        attach = goods_info.get("Attach")  # 透传信息（用户UUID）
        
        print(f"收到支付回调 - 订单号: {out_trade_no}, 道具ID: {product_id}, 用户: {user_openid}")
        print(f"透传UUID: {attach}, 数量: {quantity}, 实付: {actual_price}分")
        
        # 1. 查询订单信息（使用业务订单号）
        query_order = "SELECT * FROM recharge_order WHERE order_no = %s"
        cursor.execute(query_order, (out_trade_no,))
        order = cursor.fetchone()
        
        if not order:
            print(f"订单不存在: {out_trade_no}")
            cursor.close()
            conn.close()
            return {"ErrCode": -1, "ErrMsg": f"订单不存在: {out_trade_no}"}
        
        # 2. 验证订单状态
        user_id = order['user_id']
        user_uuid = order['uuid']
        
        # 如果已经完全处理（状态=3），则幂等处理
        if order['status'] >= 3:
            print(f"订单已完全处理，无需重复处理: {out_trade_no}, status={order['status']}")
            cursor.close()
            conn.close()
            return {"ErrCode": 0, "ErrMsg": "success"}
        
        # 3. 从ai_package表查询套餐信息（根据product_id）
        query_package = "SELECT quota_amount, price FROM ai_package WHERE package_id = %s AND is_active = 1"
        cursor.execute(query_package, (product_id,))
        package = cursor.fetchone()
        
        if not package:
            print(f"套餐不存在或已禁用: {product_id}")
            cursor.close()
            conn.close()
            return {"ErrCode": -1, "ErrMsg": f"套餐不存在: {product_id}"}
        
        quota_amount = package['quota_amount'] * quantity  # 额度 × 数量
        
        # 4. 验证透传的UUID是否匹配
        if attach and attach != user_uuid:
            print(f"UUID不匹配: 透传={attach}, 订单={user_uuid}")
            # 警告但不阻止，因为可能有特殊情况
        
        # 5. 如果订单状态为0（待支付），先更新为已支付
        if order['status'] == 0:
            update_order = """
                UPDATE recharge_order 
                SET status = 2, 
                    wx_order_id = %s, 
                    wx_transaction_id = %s, 
                    pay_time = FROM_UNIXTIME(%s), 
                    updated_at = NOW()
                WHERE id = %s
            """
            cursor.execute(update_order, (mch_order_no, transaction_id, paid_time, order['id']))
            conn.commit()
            print(f"订单状态已更新为已支付: {out_trade_no}")
        elif order['status'] == 2:
            # 订单已支付但未处理，更新支付信息
            update_order = """
                UPDATE recharge_order 
                SET wx_order_id = %s, 
                    wx_transaction_id = %s, 
                    pay_time = FROM_UNIXTIME(%s), 
                    updated_at = NOW()
                WHERE id = %s
            """
            cursor.execute(update_order, (mch_order_no, transaction_id, paid_time, order['id']))
            conn.commit()
            print(f"订单支付信息已更新: {out_trade_no}")

        # 6. 幂等保护：如果已存在额度日志，直接补齐订单完成状态
        check_log_sql = """
            SELECT id FROM ai_quota_log 
            WHERE related_id = %s AND change_type = 'purchase' LIMIT 1
        """
        cursor.execute(check_log_sql, (out_trade_no,))
        existing_log = cursor.fetchone()
        if existing_log:
            if order.get('pay_time') is not None or order.get('status', 0) >= 2:
                update_order_complete = """
                    UPDATE recharge_order 
                    SET status = 3, complete_time = COALESCE(complete_time, NOW()), updated_at = NOW()
                    WHERE id = %s
                """
                cursor.execute(update_order_complete, (order['id'],))
                conn.commit()
                print(f"订单已记录额度日志，补齐完成时间: {out_trade_no}")
                cursor.close()
                conn.close()
                return {"ErrCode": 0, "ErrMsg": "success"}
            else:
                print(f"订单未支付且无支付时间，保持完成时间为空: {out_trade_no}")
                cursor.close()
                conn.close()
                return {"ErrCode": 0, "ErrMsg": "success"}

        # 7. 增加用户AI额度
        query_user = "SELECT ai_quota FROM user WHERE id = %s"
        cursor.execute(query_user, (user_id,))
        user = cursor.fetchone()
        
        if not user:
            print(f"用户不存在: {user_id}")
            cursor.close()
            conn.close()
            return {"ErrCode": -1, "ErrMsg": f"用户不存在: {user_id}"}
        
        current_quota = user.get('ai_quota', 0)
        new_quota = current_quota + quota_amount
        
        # 更新用户额度
        update_quota = "UPDATE user SET ai_quota = %s WHERE id = %s"
        cursor.execute(update_quota, (new_quota, user_id))
        conn.commit()
        
        print(f"用户额度已更新: {user_id}, {current_quota} → {new_quota} (+{quota_amount})")
        
        # 8. 记录额度变动日志到ai_quota_log表
        insert_log = """
            INSERT INTO ai_quota_log 
            (user_id, uuid, change_type, change_amount, quota_before, quota_after, related_id, remark, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        remark = f"米大师充值 - 订单:{out_trade_no}, 道具:{product_id}, 数量:{quantity}, 实付:{actual_price/100:.2f}元"
        cursor.execute(insert_log, (
            user_id, 
            user_uuid, 
            'purchase', 
            quota_amount, 
            current_quota, 
            new_quota, 
            out_trade_no,
            remark
        ))
        conn.commit()
        
        print(f"额度日志已记录: {remark}")
        
        # 9. 更新订单状态为"已完成"
        update_order_complete = """
            UPDATE recharge_order 
            SET status = 3, complete_time = NOW(), updated_at = NOW()
            WHERE id = %s
        """
        cursor.execute(update_order_complete, (order['id'],))
        conn.commit()
        
        print(f"✅ 订单处理完成: {out_trade_no}, 已增加额度 {quota_amount}，用户额度: {current_quota} → {new_quota}")
        
        cursor.close()
        conn.close()
        
        # 返回成功响应（微信要求的格式）
        return {"ErrCode": 0, "ErrMsg": "success"}
        
    except pymysql.Error as db_error:
        print(f"数据库错误: {str(db_error)}")
        import traceback
        traceback.print_exc()
        return {"ErrCode": -1, "ErrMsg": f"数据库错误: {str(db_error)}"}
    except Exception as e:
        print(f"处理支付回调异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"ErrCode": -1, "ErrMsg": f"处理失败: {str(e)}"}

@wechat_page.route("/", methods=["POST"])
def index():
    return jsonify({
        "code": 200, "message": "Wechat open server is running"
    })

@wechat_page.route("/login/client/<f>/", methods=["POST", "GET"])
def wechat_login(f):
    """
    处理微信小程序登录请求
    请求参数: {'code': '微信登录凭证'}
    返回: 200-登录成功, 201-用户未注册需要注册
    """
    # 兼容表单和 JSON 两种传参
    code = request.form.get("code") or (request.get_json(silent=True) or {}).get("code")
    session_key = None
    match f:
        case "miniprogram":
            if not code:
                return jsonify({"code": 400, "message": "缺少 code 参数"}), 400
            result = get_unionid(code)
            match result["code"]:
                case 1:
                    openid, session_key = result["openid"], result["session_key"]
                case _:
                    return jsonify(result)
        case "openid":
            openid = request.form.get("openid") or (request.get_json(silent=True) or {}).get("openid")
        case _:
            return jsonify({'code': 0,'error': '不支持的登录来源'})

    
        
    info = account_exist(openid)
    # print(info)
    if not info["exists"]:
        # print("dhasbkjdabsdjkahsdkjasdkjsahdkasjhd")
        # 用户未注册，返回201提示需要注册
        return jsonify({
            "code": 201,
            "message": "用户未注册，请先注册",
            "data": {
                "openid": openid,
                "session_key": session_key if f == "miniprogram" else None
            }
        }), 201
    
    # 用户已存在，生成token登录
    user_uuid = info["data"]["uuid"]
    token = gen_token()
    expire = gen_expire(days=30)
    
    result = account_token_save(user_uuid, token, expire)

    return jsonify(result)


@wechat_page.route("/register/init/miniprogram/", methods=["POST"])
def wechat_register_init():
    """
    初始化注册流程：根据微信手机号动态令牌换取手机号，检查是否重复后生成uuid
    请求参数: {
        'code': '微信登录凭证',
        'phone_code': '微信手机号动态令牌'
    }
    返回: {
        'code': 200,
        'uuid': '生成的用户UUID',
        'openid': 'WeChat openid',
        'phone': '手机号'
    }
    """
    data = request.get_json() or {}
    code = data.get("code")
    phone_code = data.get("phone_code")

    if not code:
        return jsonify({"code": 400, "message": "缺少 code 参数"}), 400
    if not phone_code:
        return jsonify({"code": 400, "message": "缺少 phone_code 参数"}), 400
    
    # 获取openid
    result = get_unionid(code)
    if result["code"] != 1:
        return jsonify({"code": 400, "message": "获取openid失败", "detail": result}), 400

    openid = result["openid"]

    # 通过动态令牌获取真实手机号
    phone_result = get_phone_number(phone_code)
    if phone_result["code"] != 1:
        return jsonify({"code": 400, "message": "获取手机号失败", "detail": phone_result}), 400

    phone = phone_result["phone"]
    
    # 检查手机号和openid是否已存在
    check_result = account_check_phone_openid(phone, openid)
    if check_result["code"] != 200:
        return jsonify(check_result), 400
    
    # 创建临时用户，只保存phone和openid
    create_result = account_create_temp(phone, openid)
    if create_result["code"] != 200:
        return jsonify(create_result), 400
    
    return jsonify({
        "code": 200,
        "message": "初始化成功，请完成注册",
        "data": {
            "uuid": create_result["uuid"],
            "openid": openid,
            "phone": phone
        }
    })


@wechat_page.route("/register/complete/miniprogram/", methods=["POST"])
def wechat_register_complete():
    """
    完成注册流程：更新用户的昵称和头像，并返回token
    请求参数: {
        'uuid': '用户UUID',
        'nickname': '用户昵称',
        'avatar': '头像URL（可选）'
    }
    返回: {
        'code': 200,
        'token': '登录token',
        'message': '注册成功'
    }
    """
    data = request.get_json() or {}
    user_uuid = data.get("uuid")
    nickname = data.get("nickname", "微信用户")
    avatar = data.get("avatar")

    if not user_uuid:
        return jsonify({"code": 400, "message": "缺少 uuid 参数"}), 400
    
    # 更新用户的昵称和头像
    update_result = account_update_by_uuid(user_uuid, nickname, avatar)
    if update_result["code"] != 200:
        return jsonify(update_result), 400
    
    # 生成token登录
    token = gen_token()
    expire = gen_expire(days=30)
    
    result = account_token_save(user_uuid, token, expire)
    result["message"] = "注册成功"
    
    return jsonify(result)

@wechat_page.route("/webhook/verify/", methods=["GET"])
def wechat_webhook_verify():
    """
    微信服务器验证接口
    
    微信服务器会向此接口发送GET请求验证服务器的有效性
    验证流程：
    1. 将token、timestamp、nonce三个参数进行字典序排序
    2. 将排序后的三个参数拼接成一个字符串
    3. 进行SHA1签名计算
    4. 与URL参数中的signature进行对比验证
    5. 相等则验证通过，返回challenge参数；否则返回401
    """
    import hashlib
    from settings import WX_MIDAS_TOKEN
    
    signature = request.args.get("signature")
    timestamp = request.args.get("timestamp")
    nonce = request.args.get("nonce")
    challenge = request.args.get("echostr")  # 微信服务器验证时会发送echostr
    
    # 参数验证
    if not all([signature, timestamp, nonce]):
        return jsonify({
            "code": 400,
            "message": "缺少必要参数: signature, timestamp, nonce"
        }), 400
    
    try:
        # 1. 将token、timestamp、nonce进行字典序排序
        params = sorted([WX_MIDAS_TOKEN, timestamp, nonce])
        
        # 2. 拼接排序后的字符串
        concat_str = ''.join(params)
        
        # 3. 进行SHA1签名计算
        sha1_hash = hashlib.sha1(concat_str.encode('utf-8')).hexdigest()
        
        # 4. 与URL参数中的signature进行对比
        if sha1_hash == signature:
            # 验证通过
            # 如果是服务器验证请求（包含echostr），直接返回echostr
            if challenge:
                return challenge
            
            # 否则返回成功响应
            return jsonify({
                "code": 0,
                "message": "验证通过"
            }), 200
        else:
            # 验证失败
            return jsonify({
                "code": 401,
                "message": "签名验证失败",
                "debug": {
                    "expected": sha1_hash,
                    "received": signature
                }
            }), 401
    
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"验证过程出错: {str(e)}"
        }), 500
    
@wechat_page.route("/webhook/", methods=["POST"])
def wechat_webhook_handle():
    """
    微信消息接收和处理接口（安全模式）
    
    处理流程：
    1. 验证msg_signature签名
    2. 解密Encrypt消息
    3. 验证appid
    4. 处理消息
    5. 加密回包
    6. 生成回包签名
    """
    from settings import WX_MIDAS_TOKEN, WX_ENCODINGAESKEY, WX_APP_ID
    from utils.wechat_crypt import WXBizMsgCrypt
    import time
    import json
    
    # 获取URL参数
    msg_signature = request.args.get("msg_signature")
    timestamp = request.args.get("timestamp")
    nonce = request.args.get("nonce")
    openid = request.args.get("openid")
    
    # 获取POST包体
    data = request.get_json()
    if not data:
        return jsonify({"code": 400, "message": "无效的请求体"}), 400
    
    encrypt_msg = data.get("Encrypt")
    to_username = data.get("ToUserName")
    
    # 参数验证
    if not all([msg_signature, timestamp, nonce, encrypt_msg]):
        return jsonify({
            "code": 400,
            "message": "缺少必要参数"
        }), 400
    
    try:
        # 初始化加密解密工具
        crypt = WXBizMsgCrypt(
            token=WX_MIDAS_TOKEN,
            encoding_aes_key=WX_ENCODINGAESKEY,
            appid=WX_APP_ID
        )
        
        # 1. 验证msg_signature签名
        if not crypt.verify_signature(msg_signature, timestamp, nonce, encrypt_msg):
            return jsonify({
                "code": 401,
                "message": "签名验证失败，请求非法"
            }), 401
        
        # 2. 解密消息
        success, decrypted_msg, from_appid = crypt.decrypt(encrypt_msg)
        
        if not success:
            return jsonify({
                "code": 500,
                "message": "消息解密失败"
            }), 500
        
        # 3. 解析解密后的消息
        msg_data = json.loads(decrypted_msg)
        
        print(f"收到微信消息: {msg_data}")
        print(f"来自用户: {openid}")
        
        # 4. 处理不同类型的消息
        msg_type = msg_data.get("MsgType")
        event = msg_data.get("Event")
        
        if msg_type == "event":
            match event:
                case "xpay_goods_deliver_notify":
                    # 米大师支付回调处理
                    print("===== 处理米大师支付回调 =====")
                    print(f"完整消息数据: {json.dumps(msg_data, ensure_ascii=False, indent=2)}")
                    
                    # 调用支付回调处理函数
                    callback_result = handle_midas_payment_callback(msg_data)
                    
                    # 根据处理结果返回微信要求的格式
                    if callback_result.get("ErrCode") == 0:
                        print(f"✓ 支付回调处理成功: {msg_data.get('OutTradeNo')}")
                        # 构造成功回包
                        reply_msg = json.dumps({
                            "ErrCode": 0,
                            "ErrMsg": "success"
                        })
                    else:
                        print(f"✗ 支付回调处理失败: {callback_result.get('ErrMsg')}")
                        # 构造失败回包
                        reply_msg = json.dumps({
                            "ErrCode": callback_result.get("ErrCode", -1),
                            "ErrMsg": callback_result.get("ErrMsg", "处理失败")
                        })
                    
                    # 加密回包
                    encrypted_reply = crypt.encrypt(reply_msg)
                    if encrypted_reply:
                        reply_timestamp = int(time.time())
                        reply_signature = crypt.generate_signature(reply_timestamp, nonce, encrypted_reply)
                        return jsonify({
                            "Encrypt": encrypted_reply,
                            "MsgSignature": reply_signature,
                            "TimeStamp": reply_timestamp,
                            "Nonce": nonce
                        }), 200
                    else:
                        # 加密失败，返回纯文本JSON
                        return jsonify(callback_result), 200

                case "debug_demo":
                    # 调试事件
                    print(f"调试事件: {msg_data.get('debug_str')}")

        
        # 5. 构造回包
        # 如果不需要特殊回包内容，返回success即可
        reply_msg = "success"
        
        # 如果需要加密回包（根据消息类型决定）
        # reply_msg = json.dumps({"demo_resp": "good luck"})
        
        # 6. 加密回包
        encrypted_reply = crypt.encrypt(reply_msg)
        
        if not encrypted_reply:
            # 加密失败，返回纯文本
            return "success", 200
        
        # 7. 生成新的时间戳和签名
        reply_timestamp = int(time.time())
        reply_signature = crypt.generate_signature(reply_timestamp, nonce, encrypted_reply)
        
        # 8. 构造加密回包（JSON格式）
        reply_data = {
            "Encrypt": encrypted_reply,
            "MsgSignature": reply_signature,
            "TimeStamp": reply_timestamp,
            "Nonce": nonce
        }
        
        return jsonify(reply_data), 200
        
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {str(e)}")
        return jsonify({
            "code": 400,
            "message": "消息格式错误"
        }), 400
    except Exception as e:
        print(f"处理消息失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "code": 500,
            "message": f"处理失败: {str(e)}"
        }), 500
