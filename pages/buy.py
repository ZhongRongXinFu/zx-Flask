import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, Blueprint, Response, stream_with_context, request, jsonify
from utils.login import login_required, op_required

buy_page = Blueprint('buy', __name__)

@buy_page.route("/ai/code/", methods=["POST"])
@login_required
def ai_code_endpoint():
    code = request.form.get("code", "")
    print(code)
    if not code:
        return jsonify({"code": 400, "message": "缺少 code 参数"}), 400
    
    return jsonify({"code": 200, "message": "代码生成成功", "data": code})