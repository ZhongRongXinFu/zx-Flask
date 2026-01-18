# utils/token.py
import secrets
from datetime import datetime, timedelta, timezone

def gen_token():
    return secrets.token_hex(32)  # 64位十六进制字符串

def gen_expire(days=7):
    return datetime.now(timezone.utc) + timedelta(days=days)
