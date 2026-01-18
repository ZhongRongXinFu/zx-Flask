import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from datetime import datetime, timezone

from utils.mysql import *
from flask import request, jsonify, g
from functools import wraps
from datetime import datetime

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        # 从 header 里拿 token（Authorization 或 X-Token）
        token = request.headers.get('Authorization')
        if token and token.startswith('Bearer '):
            token = token[7:]
        if not token:
            token = request.headers.get('X-Token')

        if not token:
            return jsonify({"code": 401, "message": "未登录"}), 401

        conn = connect()
        try:
            with conn.cursor() as cursor:
                # 先删除过期的 token
                cursor.execute("""
                    DELETE FROM user_token
                    WHERE token = %s AND expire_at <= %s
                """, (token, datetime.now(timezone.utc)))
                
                # 查询有效的 token 和用户信息
                cursor.execute("""
                    SELECT u.*
                    FROM user_token t
                    JOIN user u ON t.uuid = u.uuid
                    WHERE t.token = %s AND t.expire_at > %s
                """, (token, datetime.now(timezone.utc)))
                user = cursor.fetchone()
                
                if not user:
                    return jsonify({"code": 401, "message": "登录已过期，请重新登录"}), 401
                
                # 存到 g 里，后续接口直接用 g.current_user
                g.current_user = user
                conn.commit()
        finally:
            conn.close()

        return f(*args, **kwargs)
    return wrapper

def op_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = g.current_user
        if str(user["is_op"])  != "1":
            return jsonify({"code": 403, "message": "需要管理员权限"}), 403
        return f(*args, **kwargs)
    return wrapper