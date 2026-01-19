import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json, os
from settings import PRODUCT_IMAGE_DIR
from datetime import datetime
from flask import Flask, Blueprint, Response, stream_with_context, request, jsonify, g
from utils.mysql import connect
from utils.login import login_required, op_required

dynamic_components_page = Blueprint('dynamic_components', __name__)

@dynamic_components_page.route("/get/", methods=["GET"])
def get_components():
    key = request.args.get("key", "")
    match key:
        case "title":
            key = "title"
        case "swiper":
            key = "swiper"
        case _:
            return jsonify({"code": 400, "message": "错误的key参数"}), 400

    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT content FROM `dynamic_components` WHERE name=%s"
            cursor.execute(sql, (key,))
            result = cursor.fetchone()
            
            if result is not None:
                result = result["content"]
                return { "code": 200, "data": json.loads(result) }, 200
            else:
                return { "code": 404, "message": "标题不存在" }, 404
    except Exception as e:
        return jsonify({"code": 500, "message": f"数据库读取失败: {e}"}), 500
    finally:
        connection.close()

@dynamic_components_page.route("/update/", methods=["POST"])
@login_required
@op_required
def add_components():
    print("request.form:", request.form)

    key = request.form.get("key", "")
    data = request.form.get("data", {})

    match key:
        case "title":
            key = "title"
        case "swiper":
            key = "swiper"
            
            # 解析 data JSON
            try:
                data_obj = json.loads(data) if isinstance(data, str) else data
            except json.JSONDecodeError:
                return jsonify({"code": 400, "message": "data 格式错误"}), 400
            
            if "images" not in data_obj or not isinstance(data_obj["images"], list):
                return jsonify({"code": 400, "message": "data 中缺少 images 数组"}), 400
            
            # 验证所有图片都有 URL
            for i, image_info in enumerate(data_obj["images"]):
                if not image_info.get("url"):
                    return jsonify({"code": 400, "message": f"图片 {i+1} 缺少 url"}), 400
            
            # 更新 metadata 中的最后修改时间
            if "metadata" in data_obj:
                data_obj["metadata"]["lastModified"] = datetime.now().isoformat() + "Z"
            
            # 将更新后的 data_obj 转回 JSON 字符串
            data = json.dumps(data_obj)
                
        case _:
            return jsonify({"code": 400, "message": "错误的key参数"}), 400

    try:
        connection = connect()
        with connection.cursor() as cursor:
            sql = """
            UPDATE `dynamic_components`
            SET content = %s
            WHERE name = %s
            """
            cursor.execute(sql, (data, key))
        connection.commit()
    except Exception as e:
        return jsonify({"code": 500, "message": f"数据库写入失败: {e}"}),500
    finally:
        connection.close()
    return jsonify({"code": 200, "message": "更新成功", "data": json.loads(data) if isinstance(data, str) else data}), 200
