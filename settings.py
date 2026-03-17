DEBUG = True

# 临时开关：关闭后，AI 分析不会校验额度不足，也不会扣减用户额度。
AI_QUOTA_DEDUCTION_ENABLED = False

DB_HOST = "localhost"
DB_USER = "api"
DB_PASSWORD = "cZ6aF0rO0gA0sF2fV5cC1cO0"
DB_DATABASE = "zhongrong"
DB_PORT = 3306

WX_APP_ID = 'wx276d3b776e47c682'
WX_APP_SECRET = '5654bdfd979bef4f4be46715f572f5ff'
WX_OFFER_ID = '1450474385'
WX_MIDAS_TOKEN = 'WDMNEYNnaLIEDABSBIDYNASODIBQWUEQ'  # 微信服务器验证token - 从微信公众平台获取
WX_ENCODINGAESKEY = 'LvIaGOIjqberGcsvY7r4dWdGWIC0GWjZMhexfoR5v1G'
WX_LOGIN_APP_ID = 'wx61848022937f1de5'
WX_LOGIN_APP_SECRET = '6632cde4656f1f7a3af37092263a3564'
WX_MIDAS_ENV = 1    # 0-正式环境 1-沙箱环境
if (WX_MIDAS_ENV == 0):
    WX_MIDAS_APP_KEY = 'cNxlxH50XD2iLcCZVNVOSQLK5Z1iFtcO'  # 正式key
else:
    WX_MIDAS_APP_KEY = 'M22ZpaULH7X8VivOMmh3Qc0g6SlKKnvs'  # 沙箱key


AI_DEEPSEEK_API_KEY = "sk"
AI_TENCENT_SECRET_ID = "AKIDU3pW7awLhsukNrAKI4eTG3LYgpu8FAtQ"
AI_TENCENT_SECRET_KEY = "Pm398FByb5UkrpcGl6QqaJwbGnAOgqri"


AI_HUOSHAN_API_KEY = "6a401bfa-6e6f-44ad-a5b6-e09fe262f592" #company

if DEBUG:
    STATIC_FILE_DIR = "./static"
    MEDIA_FILE_DIR = "./static/media"
else:
    STATIC_FILE_DIR = "/work/static"
    MEDIA_FILE_DIR = "/work/static/media"

STATIC_BASE_URL = "https://static.zhongrongxinfu.cn"
MEDIA_BASE_URL = "https://media.zhongrongxinfu.cn"

UPLOAD_FILE_DIR = STATIC_FILE_DIR

PRODUCT_IMAGE_DIR = STATIC_FILE_DIR
