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
            
            whitelist = []
            # 遍历所有图片，上传并替换 URL
            for i, image_info in enumerate(data_obj["images"]):
                image_id = image_info.get("id")
                if not image_id:
                    return jsonify({"code": 400, "message": f"图片 {i+1} 缺少 id"}), 400
                
                # 获取对应的文件
                file = request.files.get(f"image_{image_id-1}")
                if not file or file.filename == "":
                    return jsonify({"code": 400, "message": f"缺少 image_{image_id-1} 文件"}), 400
                
                # 保存文件
                ext = file.filename.rsplit('.', 1)[-1] if '.' in file.filename else 'jpg'
                new_filename = f"{image_id}.{ext}"
                save_path = os.path.join(os.path.expanduser(PRODUCT_IMAGE_DIR), key, new_filename)
                
                # 确保目录存在
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                file.save(save_path)
                
                # 替换 data 中的 URL
                new_url = f"http://192.168.196.47:8000/static/{key}/{new_filename}"
                data_obj["images"][i]["url"] = new_url
                whitelist.append(new_filename)
            
            # 更新 metadata 中的最后修改时间
            if "metadata" in data_obj:
                data_obj["metadata"]["lastModified"] = datetime.now().isoformat() + "Z"
            
            # 将更新后的 data_obj 转回 JSON 字符串
            data = json.dumps(data_obj)

            for filename in os.listdir(os.path.join(os.path.expanduser(PRODUCT_IMAGE_DIR), key)):
                file_path = os.path.join(os.path.join(os.path.expanduser(PRODUCT_IMAGE_DIR), key), filename)
                if os.path.isfile(file_path) and filename not in whitelist:
                    os.remove(file_path)
                
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
