import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uuid
import hashlib
from flask import Flask, Blueprint, Response, stream_with_context, request, jsonify
from utils.token import *
from utils.account import *
from utils.wechat import *
from utils.account import account_check_phone_openid, account_create_temp, account_update_by_uuid
from utils.login import login_required, op_required
wechat_page = Blueprint('wechat', __name__)

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
    print(info)
    if not info["exists"]:
        print("dhasbkjdabsdjkahsdkjasdkjsahdkasjhd")
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

@wechat_page.route("/webhook/", methods=["GET"])
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