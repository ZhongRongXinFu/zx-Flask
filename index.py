from flask import Flask, Blueprint, jsonify, request, make_response
from flask_cors import CORS




app = Flask(__name__)

# 设置最大请求体大小（100MB）
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 100MB

# 允许跨域所有域名，并允许带 cookie
CORS(app, 
     resources={r"/*": {"origins": "*"}}, 
     supports_credentials=True
)

def count_custom_routes(app):
    return sum(
        1
        for r in app.url_map.iter_rules()
        if not r.rule.startswith("/static")
    )





from pages.ai import ai_page
from pages.buy import buy_page
from pages.wechat import wechat_page
from pages.account import account_page
from pages.product import product_page
from pages.dynamic_components import dynamic_components_page
from pages.chat import chat_page
from pages.upload import upload_page
app.register_blueprint(ai_page, url_prefix="/ai")
app.register_blueprint(buy_page, url_prefix="/buy")
app.register_blueprint(wechat_page, url_prefix="/wechat")
app.register_blueprint(account_page, url_prefix="/account")
app.register_blueprint(product_page, url_prefix="/product")
app.register_blueprint(dynamic_components_page, url_prefix="/dynamic_components")
app.register_blueprint(chat_page, url_prefix="/chat")
app.register_blueprint(upload_page, url_prefix="/upload")
@app.route("/")
def index():
    return jsonify({"code": 200,"message": "ZRXF server is running"})

if __name__ == "__main__":
    with app.app_context():
        print("你自定义的路由数量：", count_custom_routes(app))
    app.run(host="0.0.0.0", port=8000, debug=True)
