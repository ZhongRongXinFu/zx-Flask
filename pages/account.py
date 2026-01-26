import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests; import pymysql; from settings import WX_LOGIN_APP_ID, WX_LOGIN_APP_SECRET
from flask import Flask, Blueprint, Response, stream_with_context, request, jsonify, g, redirect

from utils.login import login_required, op_required
from utils.account import *
from utils.account import account_update_nickname, account_update_avatar
from utils.mysql import connect
from utils.token import *

account_page = Blueprint('account', __name__)

@account_page.route("/", methods=["POST"])
def index():
    return jsonify({
        "code": 200, "message": "Account open server is running"
    })

@account_page.route("/oauth/wechat/callback/", methods=["GET"])
def oauth_wechat_callback():
    code = request.args.get("code")
    state, redirect_uri = request.args.get("state", "0;http://localhost:5173/redirect").split(";")
    
    if not code:
        return jsonify({"error": "缺少 code"}), 400
    token_url = "https://api.weixin.qq.com/sns/oauth2/access_token"
    token_params = {
        "appid": WX_LOGIN_APP_ID,
        "secret": WX_LOGIN_APP_SECRET,
        "code": code,
        "grant_type": "authorization_code"
    }
    token_resp = requests.get(token_url, params=token_params).json()
    if "errcode" in token_resp:
        return jsonify({"error": "获取 access_token 失败", "detail": token_resp}), 500

    access_token = token_resp.get("access_token")
    openid = token_resp.get("openid")

    # Step4: 拿 access_token/openid 获取用户信息
    userinfo_url = "https://api.weixin.qq.com/sns/userinfo"
    userinfo_params = {
        "access_token": access_token,
        "openid": openid,
        "lang": "zh_CN"
    }
    userinfo_resp = requests.get(userinfo_url, params=userinfo_params).json()
    unionid = userinfo_resp.get("unionid")

    info = account_exist(unionid)
    
    if not info["exists"]:
        return jsonify({ "code": 400, "message": "没有相应的账户" }), 400

    if info["data"]["is_op"] != 1:
        return jsonify({ "code": 403, "message": "需要管理员权限" }), 403

    token = gen_token()
    expire = gen_expire(days=30)
    
    result = account_token_save(info["data"]["uuid"], token, expire)

    redirect_uri += f"?token={token}"

    return redirect(redirect_uri)
    # return jsonify({
    #     "code": 200,
    #     "message": "获取用户信息成功",
    #     "data": userinfo_resp
    # })

@account_page.route("/profile/", methods=["GET", "POST"])
@login_required
def web_account_profile():
    user = g.current_user
    data = {
        "code": 200,
        "message": "获取用户信息成功",
        "data": {
            "uuid": user["uuid"],
            "nickname": user["nickname"],
            "wechat": user["wechat"],
            "email": user["email"],
            "phone": user["phone"],
            "avatar": user["avatar"],
            "is_op": user["is_op"],
            "ai_quota": user["ai_quota"]
        }
    }
    print(data)
    return jsonify(data), 200


@account_page.route("/profile/update/nickname/", methods=["POST"])
@login_required
def web_account_update_nickname():
    payload = request.get_json() or {}
    nickname = payload.get("nickname")
    if not nickname:
        return jsonify({"code": 400, "message": "缺少 nickname"}), 400

    user_uuid = g.current_user["uuid"]
    result = account_update_nickname(user_uuid, nickname)
    return jsonify(result)


@account_page.route("/profile/update/avatar/", methods=["POST"])
@login_required
def web_account_update_avatar():
    payload = request.get_json() or {}
    avatar = payload.get("avatar")
    if not avatar:
        return jsonify({"code": 400, "message": "缺少 avatar"}), 400

    user_uuid = g.current_user["uuid"]
    result = account_update_avatar(user_uuid, avatar)
    return jsonify(result)

@account_page.route("/info/<uid>/", methods=["GET"])
@login_required
def web_account_info(uid):
    return jsonify(account_info(uid))

@account_page.route("/logout/", methods=["DELETE"])
@login_required
def web_account_logout():
    token = request.headers.get('Authorization')
    if token and token.startswith("Bearer "):
        token = token[7:]

    if not token:
        return jsonify({"code": 400, "message": "缺少 token"}), 400

    return jsonify(account_logout(token))

@account_page.route("/login/manager/", methods=["POST"])
def login_manager():
    openid = request.form.get("openid")
    print(openid)
    if not openid:
        return jsonify({"code": 400, "message": "缺少 openid 参数"}), 400

    info = account_exist(openid)
    
    if not info["exists"]:
        return jsonify({ "code": 400, "message": "没有相应的账户" }), 400

    if info["data"]["is_op"] != 1:
        return jsonify({ "code": 403, "message": "需要管理员权限" }), 403

    token = gen_token()
    expire = gen_expire(days=30)
    
    result = account_token_save(info["data"]["uuid"], token, expire)
    # print("login_manager result:", result)
    return jsonify(result)

@account_page.route("/getall/", methods=["GET"])
@login_required
@op_required
def web_account_getall():
    # 分页参数
    page = request.args.get("page", 1, type=int)
    range_size = request.args.get("range", 10, type=int)

    # 排序参数
    sort_by = request.args.get("sort_by", "created_at", type=str)
    order = request.args.get("order", "desc", type=str).lower()

    # 过滤参数（简化版）
    nickname = request.args.get("nickname", type=str)
    email = request.args.get("email", type=str)
    phone = request.args.get("phone", type=str)

    # 参数校验
    if page < 1:
        return jsonify({"code": 400, "message": "page 必须大于等于1"}), 400
    if range_size < 1 or range_size > 500:
        return jsonify({"code": 400, "message": "range 必须在1-500之间"}), 400

    allowed_sort_fields = {
        "created_at": "created_at",
        "ai_quota": "ai_quota",
        "is_op": "is_op",
        "nickname": "nickname"
    }
    if sort_by not in allowed_sort_fields:
        sort_by = "created_at"
    if order not in ("asc", "desc"):
        order = "desc"

    offset = (page - 1) * range_size

    where_clauses = []
    params = []

    if nickname:
        where_clauses.append("nickname LIKE %s")
        params.append(f"%{nickname}%")
    if email:
        where_clauses.append("email LIKE %s")
        params.append(f"%{email}%")
    if phone:
        where_clauses.append("phone LIKE %s")
        params.append(f"%{phone}%")

    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    connection = connect()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            count_sql = f"SELECT COUNT(*) as total FROM `user`{where_sql}"
            cursor.execute(count_sql, params)
            total_result = cursor.fetchone()
            total = total_result.get("total", 0) if total_result else 0

            select_sql = (
                "SELECT uuid, nickname, wechat, email, phone, avatar, ai_quota, is_op, created_at "
                "FROM `user`"
                f"{where_sql} "
                f"ORDER BY {allowed_sort_fields[sort_by]} {order.upper()} "
                "LIMIT %s OFFSET %s"
            )
            exec_params = list(params)
            exec_params.extend([range_size, offset])
            cursor.execute(select_sql, exec_params)
            result = cursor.fetchall()
    except Exception as e:
        return jsonify({"code": 400, "message": f"获取账号列表失败: {str(e)}"}), 400
    finally:
        connection.close()

    total_pages = (total + range_size - 1) // range_size

    return jsonify({
        "code": 200,
        "message": "查询成功",
        "data": result,
        "pagination": {
            "page": page,
            "range": range_size,
            "total": total,
            "total_pages": total_pages
        }
    })