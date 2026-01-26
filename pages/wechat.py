import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uuid
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
            result = get_openid(code)
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
    result = get_openid(code)
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


@wechat_page.route("/get-uuid/miniprogram/", methods=["POST"])
def get_user_uuid():
    """
    通过小程序微信登录获取用户UUID
    请求参数: {
        'code': '微信登录凭证'
    }
    返回: {
        'code': 200,
        'uuid': '用户UUID（如已注册）或 openid（如未注册）',
        'is_registered': true/false,
        'openid': 'openid'
    }
    """
    data = request.get_json() or {}
    code = data.get("code")
    
    if not code:
        return jsonify({"code": 400, "message": "缺少 code 参数"}), 400
    
    # 获取openid
    result = get_openid(code)
    if result["code"] != 1:
        return jsonify({"code": 400, "message": "获取openid失败", "detail": result}), 400
    
    openid = result["openid"]
    
    # 检查用户是否已存在
    info = account_exist(openid)
    
    if info["exists"]:
        # 用户已注册，返回uuid
        return jsonify({
            "code": 200,
            "message": "用户已注册",
            "data": {
                "uuid": info["data"]["uuid"],
                "is_registered": True,
                "openid": openid
            }
        })
    else:
        # 用户未注册，返回随机生成的uuid作为临时标识
        return jsonify({
            "code": 200,
            "message": "用户未注册",
            "data": {
                "uuid": str(uuid.uuid4()),  # 生成随机uuid作为临时标识
                "is_registered": False,
                "openid": openid
            }
        })