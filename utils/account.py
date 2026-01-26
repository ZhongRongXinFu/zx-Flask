import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uuid
from utils.mysql import connect

def account_create(nickname, wechat, email=None, phone=None, avatar=None, uuid=None) -> dict:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT uuid FROM `user` WHERE wechat=%s"
            cursor.execute(sql, (wechat,))
            result = cursor.fetchone()
            if result is not None: return { "code": 400, "message": "账号已存在" }
            user_uuid = str(uuid.uuid4()) if uuid is None else uuid
            sql = "INSERT INTO `user` (uuid, nickname, wechat, email, phone, avatar) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(sql, (user_uuid, nickname, wechat, email, phone, avatar))
            result = cursor.fetchone()
        connection.commit()
        return { "code": 200, "message": "账号创建成功", "uuid": user_uuid }
    except Exception as e:
        return { "code": 400, "message": f"账号创建失败: {str(e)}" }
    finally:
        connection.close()

def account_exist(wechat) -> dict:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT uuid, is_op FROM `user` WHERE wechat=%s"
            cursor.execute(sql, (wechat,))
            result = cursor.fetchone()
            # print(result)
            return { "code": 200, "exists": result is not None , "data": result }
    finally:
        connection.close()

def account_info(uid) -> dict:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = """SELECT 
                uuid,
                nickname,
                wechat,
                email, 
                phone,
                avatar,
                ai_quota,
                is_op
             FROM `user` WHERE uuid=%s"""
            cursor.execute(sql, (uid,))
            result = cursor.fetchone()
            if result is not None:
                return { "code": 200, "data": result }
            else:
                return { "code": 404, "message": "账号不存在" }
    except Exception as e:
        return { "code": 400, "message": f"获取账号信息失败: {str(e)}" }
    finally:
        connection.close()

def account_getall():
    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = """SELECT 
                uuid,
                nickname,
                wechat,
                email, 
                phone,
                avatar,
                ai_quota,
                is_op
             FROM `user` """
            cursor.execute(sql)
            result = cursor.fetchall()
            return { "code": 200, "data": result }
    except Exception as e:
        return { "code": 400, "message": f"获取账号列表失败: {str(e)}" }
    finally:
        connection.close()

def account_delete(wechat, wechat_again) -> dict:
    if wechat != wechat_again:
        return { "code": 400, "message": "两次输入的微信号不一致" }
    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = "DELETE FROM `user` WHERE wechat=%s"
            cursor.execute(sql, (wechat,))
        connection.commit()
        return { "code": 200, "message": "账号删除成功" }
    except Exception as e:
        return { "code": 400, "message": f"账号删除失败: {str(e)}" }
    finally:
        connection.close()

def account_update(wechat, key, value) -> dict:
    allowed_fields = {"nickname", "email", "phone", "avatar", "ai_quota"}
    if key not in allowed_fields:
        return { "code": 400, "message": "不允许更新该字段" }
    if not account_exist(wechat)["exists"]:
        return { "code": 400, "message": "账号不存在" }
    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = f"UPDATE `user` SET {key}=%s WHERE wechat=%s"
            cursor.execute(sql, (value, wechat))
        connection.commit()
        return { "code": 200, "message": "账号信息更新成功" }
    except Exception as e:
        return { "code": 400, "message": f"账号信息更新失败: {str(e)}" }
    finally:
        connection.close()

def account_token_save(uuid, token, expire_at) -> dict:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = "REPLACE INTO user_token (uuid, token, expire_at) VALUES (%s, %s, %s)"
            cursor.execute(sql, (uuid, token, expire_at))
        connection.commit()
        return { "code": 200, "message": "登录token创建成功", "token": token }
    except Exception as e:
        return { "code": 400, "message": f"登录token创建失败: {str(e)}" }
    finally:
        connection.close()
    
def account_logout(token):
    conn = connect()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM user_token WHERE token=%s", (token,))
        conn.commit()
    finally:
        conn.close()

    return { "code": 200, "message": "已退出登录" }

def account_check_phone_openid(phone, openid) -> dict:
    """检查手机号和openid是否已存在"""
    connection = connect()
    try:
        with connection.cursor() as cursor:
            # 检查手机号
            sql = "SELECT uuid FROM `user` WHERE phone=%s"
            cursor.execute(sql, (phone,))
            if cursor.fetchone() is not None:
                return { "code": 400, "message": "手机号已被注册" }
            
            # 检查openid
            sql = "SELECT uuid FROM `user` WHERE wechat=%s"
            cursor.execute(sql, (openid,))
            if cursor.fetchone() is not None:
                return { "code": 400, "message": "微信账号已被注册" }
            
            return { "code": 200, "exists": False }
    except Exception as e:
        return { "code": 400, "message": f"检查失败: {str(e)}" }
    finally:
        connection.close()

def account_create_temp(phone, openid) -> dict:
    """创建临时用户（仅包含phone和openid）"""
    connection = connect()
    try:
        user_uuid = str(uuid.uuid4())
        sql = "INSERT INTO `user` (uuid, wechat, phone) VALUES (%s, %s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(sql, (user_uuid, openid, phone))
        connection.commit()
        return { "code": 200, "message": "临时用户创建成功", "uuid": user_uuid }
    except Exception as e:
        return { "code": 400, "message": f"用户创建失败: {str(e)}" }
    finally:
        connection.close()

def account_update_by_uuid(uuid_str, nickname, avatar) -> dict:
    """根据uuid更新用户的昵称和头像"""
    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = "UPDATE `user` SET nickname=%s, avatar=%s WHERE uuid=%s"
            cursor.execute(sql, (nickname, avatar, uuid_str))
        connection.commit()
        return { "code": 200, "message": "用户信息更新成功" }
    except Exception as e:
        return { "code": 400, "message": f"更新失败: {str(e)}" }
    finally:
        connection.close()


def account_update_nickname(uuid_str, nickname) -> dict:
    """仅更新昵称"""
    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = "UPDATE `user` SET nickname=%s WHERE uuid=%s"
            cursor.execute(sql, (nickname, uuid_str))
        connection.commit()
        return { "code": 200, "message": "昵称更新成功" }
    except Exception as e:
        return { "code": 400, "message": f"昵称更新失败: {str(e)}" }
    finally:
        connection.close()


def account_update_avatar(uuid_str, avatar) -> dict:
    """仅更新头像"""
    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = "UPDATE `user` SET avatar=%s WHERE uuid=%s"
            cursor.execute(sql, (avatar, uuid_str))
        connection.commit()
        return { "code": 200, "message": "头像更新成功" }
    except Exception as e:
        return { "code": 400, "message": f"头像更新失败: {str(e)}" }
    finally:
        connection.close()

if __name__ == "__main__":
    # print(account_create("测试用户", "oU-J716qXHV4IZwjKhIgymHIYcYg"))
    print(account_exist("ozNfp4ieQ_Y579Uj6voSfq72A30k"))
    # print(account_delete("oU-J716qXHV4IZwjKhIgymHIYcYg", "oU-J716qXHV4IZwjKhIgymHIYcYg"))
    # print(account_update("oU-J716qXHV4IZwjKhIgymHIYcYg", "nickname", "更新后的昵称"))
