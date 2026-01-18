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
        openid = result.get("openid")
        session_key = result.get("session_key")
        if not openid: return { "code": 0, "message": "未获取到openid" }
        return { "code": 1, "openid": openid, "session_key": session_key }

    except Exception as e:
        return { "code": -1, "message": "服务器内部错误" }