import requests
from settings import WX_APP_ID, WX_APP_SECRET, WX_API_URL

def get_access_token():
    """获取微信access_token"""
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={WX_APP_ID}&secret={WX_APP_SECRET}"
    response = requests.get(url)
    return response.json().get("access_token")

def get_openid(code):
    """通过登录凭证获取openid和session_key"""
    params = {
        "appid": WX_APP_ID,
        "secret": WX_APP_SECRET,
        "js_code": code,
        "grant_type": "authorization_code"
    }
    
    try:
        response = requests.get(WX_API_URL, params=params)
        result = response.json()
        
        if "errcode" in result:
            return {
                "code": result.get("errcode"),
                "message": result.get("errmsg")
            }
        openid = result.get("unionid")
        session_key = result.get("session_key")
        if not openid: return { "code": 0, "message": "未获取到openid" }
        return { "code": 1, "openid": openid, "session_key": session_key }

    except Exception as e:
        return { "code": -1, "message": "服务器内部错误" }


def get_phone_number(phone_code):
    """通过动态令牌获取用户手机号"""
    access_token = get_access_token()
    if not access_token:
        return { "code": -1, "message": "获取access_token失败" }

    url = f"https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={access_token}"
    try:
        resp = requests.post(url, json={"code": phone_code})
        data = resp.json()

        if data.get("errcode") != 0:
            return { "code": data.get("errcode"), "message": data.get("errmsg") }

        phone_info = data.get("phone_info") or {}
        if phone_info.get("countryCode") != "86":
            return { "code": 0, "message": "暂不支持非大陆手机号" }
        phone = phone_info.get("purePhoneNumber") or phone_info.get("phoneNumber")
        if not phone:
            return { "code": 0, "message": "未获取到手机号" }

        return { "code": 1, "phone": phone, "raw": phone_info }
    except Exception:
        return { "code": -1, "message": "服务器内部错误" }