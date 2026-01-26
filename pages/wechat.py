import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uuid
from flask import Flask, Blueprint, Response, stream_with_context, request, jsonify
from utils.token import *
from utils.account import *
from utils.wechat import *
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


@wechat_page.route("/register/client/miniprogram/", methods=["POST"])
def wechat_register():
    """
    处理微信小程序用户注册请求
    请求参数: {
        'code': '微信登录凭证',
        'nickname': '用户昵称',
        'avatar': '头像URL',
        'phone': '手机号（可选）'
    }
    返回: 注册成功后自动登录，返回token
    """
    data = request.get_json() or {}
    openid= data.get("openid")
    nickname = data.get("nickname", "微信用户")
    avatar = data.get("avatar")
    idd = data.get("uuid")

    if not openid:
        return jsonify({"code": 400, "message": "缺少 openid 参数"}), 400
    
    # 检查用户是否已存在
    info = account_exist(openid)
    if info["exists"]:
        return jsonify({"code": 400, "message": "用户已存在，请直接登录"}), 400
    
    # 创建新账户
    r = account_create(nickname=nickname, wechat=openid, avatar=avatar, uuid=idd)
    if r["code"] != 200:
        return jsonify({"code": 0, "message": "账号创建失败: " + r["message"]})
    
    # 注册成功后自动登录
    user_uuid = r["uuid"]
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