import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

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
    返回: {'openid': '用户唯一标识', 'session_key': '会话密钥'}
    """
    data = request.form.get("code")
    match f:
        case "miniprogram":
            result = get_openid(data)
            match result["code"]:
                case 1:
                    openid, session_key = result["openid"], result["session_key"]
                case _:
                    return jsonify(result)
        case "openid":
            openid = request.form.get("openid")
        case _:
            return jsonify({'code': 0,'error': '不支持的登录来源'})

    
        
    info = account_exist(openid)

    if not info["exists"]:
        r = account_create(nickname="微信用户", wechat=openid)
        if r["code"] != 200:
            return jsonify({ "code": 0, "message": "账号创建失败: " + r["message"] })

    token = gen_token()
    expire = gen_expire(days=30)
    
    result = account_token_save(info["data"]["uuid"], token, expire)

    return jsonify(result)