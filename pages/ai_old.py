import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pymysql
import os, uuid, json
from settings import PRODUCT_IMAGE_DIR
from datetime import datetime, timezone
from flask import Flask, Blueprint, Response, stream_with_context, request, jsonify, g
from utils.ai.ai import (
    validate_prompt,
    validate_file_ext,
    validate_file_size,
    save_temp_file,
    office_to_pdf,
    pdf_to_images,
)

from utils.ai.basic import *
from utils.ai.deepseek import chat as deepseek_chat
from utils.ai.doubao_neo import chat as doubao_chat
from utils.mysql import connect
from utils.login import login_required, op_required


ai_page = Blueprint('ai', __name__)

@ai_page.route("/analyze/", methods=["POST"])
def zhengxin_analyze():
    category = request.form.get("use")
    
    if not category:
        return jsonify({"code": 400, "message": "缺少 category 参数"}), 400
    match category:
        case "personal":
            prompt = "写清楚客户的姓名 年纪贷款的余额。和担保的余额。(同一个银行核算到一笔)只需要总结未结清的部分，单位万元列举清楚 银行名称和对应的余额担保的贷款 核算贷款的总和 和担保的总和贷款发一个文字清单，担保的发文字清单按排列下顺序，标注数字。数字需要精，核算清楚，不能有任何错误(最后核验比对贷款的汇总金额是否错误的话 就比对 信贷交易授信及负债信息概要里面的，循环贷账户+非循环贷里面的余额 想加一起就可以，核验贷款管理机构数量=非循环贷管理机构数=循环贷账户管理机构数合计一起)"
        case "company":
            prompt = "只需要总结未结清的部分，列举清楚 银行名称和对应的余额  （同一个 银行核算到一笔） 汇总金额也算下排列下顺序，标注数字。数字需要精准，核算清楚，不能有任何错误 （反复验算 总金额和贷款的机构数 ）"
        case _:
            return jsonify({"code": 400, "message": "category 参数错误"}), 400
    files = request.files.getlist("files")
    is_file = bool(files)
    chat_uuid = str(uuid.uuid4()) if is_file else None
    file_list = []
    if is_file:
        # 展开用户目录，确保是绝对路径
        base_dir = os.path.expanduser(PRODUCT_IMAGE_DIR)
        for f in files:
            # 校验扩展名与大小
            ok_ext, ext_or_err = validate_file_ext(f.filename)
            if not ok_ext:
                return jsonify({"code": 400, "message": ext_or_err}), 400
            ok_size, size_or_err = validate_file_size(f)
            if not ok_size:
                return jsonify({"code": 400, "message": size_or_err}), 400

            # 保存到持久目录（多级目录确保存在）
            path = os.path.join(base_dir, "ai-upload", chat_uuid, f.filename)
            dir_path = os.path.dirname(path)
            try:
                os.makedirs(dir_path, exist_ok=True)
                f.save(path)
            except Exception as e:
                return jsonify({"code": 500, "message": f"文件保存失败: {e}"}), 500
            file_list.append(path)
        

        model = "doubao"
        def generate():
            try:
                # 发送开始信号
                yield f"event: start\ndata: {json.dumps({'status': 'started', 'model': model, 'message': '开始生成'})}\n\n"
                
                for chunk in doubao_chat(prompt, "enabled", is_file=is_file, file_path=file_list):
                    data = chunk if isinstance(chunk, str) else json.dumps(chunk, ensure_ascii=False)
                    yield f"event: message\ndata: {json.dumps({'status': 'streaming', 'message': data})}\n\n"

                # 发送结束信号
                yield f"event: end\ndata: {json.dumps({'status': 'completed', 'model': model, 'message': '生成完成'})}\n\n"
            except Exception as e:
                # 发送错误信号
                yield f"event: error\ndata: {json.dumps({'status': 'error', 'model': model, 'message': str(e)})}\n\n"
            
        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        return jsonify({"code": 400, "message": "请上传文件进行分析"})



@ai_page.route("/chat/<model>/", methods=["POST"])
@login_required
@op_required
def deepseek_chat_endpoint(model):
    prompt = request.form.get("prompt", "")
    think = request.form.get("think", "disabled")

    # 先在请求上下文仍有效时处理上传文件，避免生成器中访问已关闭的文件流
    files = request.files.getlist("files")
    is_file = bool(files)
    chat_uuid = str(uuid.uuid4()) if is_file else None
    file_list = []
    if is_file:
        # 展开用户目录，确保是绝对路径
        base_dir = os.path.expanduser(PRODUCT_IMAGE_DIR)
        for f in files:
            # 校验扩展名与大小
            ok_ext, ext_or_err = validate_file_ext(f.filename)
            if not ok_ext:
                return jsonify({"code": 400, "message": ext_or_err}), 400
            ok_size, size_or_err = validate_file_size(f)
            if not ok_size:
                return jsonify({"code": 400, "message": size_or_err}), 400

            # 保存到持久目录（多级目录确保存在）
            path = os.path.join(base_dir, "ai-upload", chat_uuid, f.filename)
            dir_path = os.path.dirname(path)
            try:
                os.makedirs(dir_path, exist_ok=True)
                f.save(path)
            except Exception as e:
                return jsonify({"code": 500, "message": f"文件保存失败: {e}"}), 500
            file_list.append(path)

    def generate():
        try:
            # 发送开始信号
            yield f"event: start\ndata: {json.dumps({'status': 'started', 'model': model, 'message': '开始生成'})}\n\n"
            
            match model:
                case "deepseek":
                    for chunk in deepseek_chat(prompt, think):
                        data = chunk if isinstance(chunk, str) else json.dumps(chunk, ensure_ascii=False)
                        yield f"event: message\ndata: {json.dumps({'status': 'streaming', 'message': data})}\n\n"
                case "doubao":
                    for chunk in doubao_chat(prompt, think, is_file=is_file, file_path=file_list):
                        data = chunk if isinstance(chunk, str) else json.dumps(chunk, ensure_ascii=False)
                        yield f"event: message\ndata: {json.dumps({'status': 'streaming', 'message': data})}\n\n"
                case _:
                    raise ValueError("不支持的模型类型")
                
            # 发送结束信号
            yield f"event: end\ndata: {json.dumps({'status': 'completed', 'model': model, 'message': '生成完成'})}\n\n"
        except Exception as e:
            # 发送错误信号
            yield f"event: error\ndata: {json.dumps({'status': 'error', 'model': model, 'message': str(e)})}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

@ai_page.route("/redeem-code/create/", methods=["POST"])
@login_required
@op_required
def ai_redeem_code_create():
    amount = request.form.get("amount", 1)
    count = request.form.get("count", 1)
    valid_from_str = request.form.get("valid_from", None)
    valid_to_str = request.form.get("valid_to", None)
    remark = request.form.get("remark", None)

    try:
        amount = int(amount)
        count = int(count)
    except ValueError:
        return jsonify({"code": 400, "message": "amount 和 count 必须是数字"}), 400

    if amount <= 0:
        return jsonify({"code": 400, "message": "amount 必须大于 0"}), 400
    if count <= 0 or count > 500:
        return jsonify({"code": 400, "message": "count 必须在 1 到 500 之间"}), 400
    
    dt_format = "%Y-%m-%d %H:%M:%S"
    valid_from = None
    valid_to = None
    generated_codes = []

    print("valid_from_str:", valid_from_str, "valid_to_str:", valid_to_str)
    try:
        if valid_from_str:
            valid_from = parse_datetime(valid_from_str)
        if valid_to_str:
            valid_to = parse_datetime(valid_to_str)
    except ValueError:
        return jsonify({"code": 400, "message": "时间格式错误，应为 YYYY-MM-DD HH:MM:SS"}), 400

    connection = connect()
    sql = "INSERT INTO ai_redeem_code (code, amount, valid_from, valid_to, remark) VALUES (%s, %s, %s, %s, %s)"

    connection.commit()

    try:
        with connection.cursor() as cursor:
            for _ in range(count):
                # 尝试生成一个唯一的兑换码，如果撞 UNIQUE 就重试几次
                for _retry in range(5):
                    code = str(uuid.uuid4().hex.upper())
                    try:
                        cursor.execute(
                            sql,
                            (code, amount, valid_from, valid_to, remark)
                        )
                        generated_codes.append(code)
                        break
                    except pymysql.err.IntegrityError as e:
                        continue
                else:
                    # 多次重试仍然失败
                    raise RuntimeError("生成唯一兑换码失败，请稍后重试")
        connection.commit()
    except Exception as e:
        return { "code": 400, "message": f"创建失败: {str(e)}" }
    finally:
        connection.close()
    
    return jsonify({"code": 200, "message": "兑换码生成成功", "data": generated_codes})

@ai_page.route("/redeem-code/redeem/", methods=["POST"])
@login_required
def ai_redeem_code_redeem():
    user = g.current_user
    user_uuid = user["uuid"]
    code = request.form.get("code", None)
    if not code:
        return jsonify({"code": 400, "message": "缺少 code 参数"}), 400
    connection = connect()
    sql = """
            SELECT id, code, amount, is_used, used_by, valid_from, valid_to
            FROM ai_redeem_code
            WHERE code = %s
            FOR UPDATE
        """
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (code,))
            results = cursor.fetchone()
            if not results:
                return jsonify({"code": 400, "message": "兑换码不存在"}), 400
            if results["is_used"]:
                return jsonify({"code": 400, "message": "兑换码已被使用"}), 400
            now = datetime.now()
            if results["valid_from"] and now < results["valid_from"]:
                return jsonify({"code": 400, "message": "兑换码尚未生效"}), 400
            if results["valid_to"] and now > results["valid_to"]:
                return jsonify({"code": 400, "message": "兑换码已过期"}), 400
            sql = """
            UPDATE user
                SET ai_quota = ai_quota + %s
                WHERE uuid = %s
            """
            cursor.execute(sql, (results["amount"], user_uuid))
            if cursor.rowcount == 0:
                return jsonify({"code": 400, "message": "用户不存在"}), 400
            sql = """
                UPDATE ai_redeem_code
                SET is_used = 1,
                    used_by = %s,
                    used_at = NOW()
                WHERE id = %s
            """
            cursor.execute(sql, (user_uuid, results["id"]))
            cursor.execute(
                "SELECT used_at FROM ai_redeem_code WHERE id = %s",
                (results["id"],)
            )
            used_row = cursor.fetchone()
        connection.commit()
        used_at = used_row["used_at"].strftime("%Y-%m-%d %H:%M:%S") if used_row and used_row["used_at"] else None

        return jsonify({
            "code": 200,
            "message": "兑换成功",
            "data": {
                "code": code,
                "amount": results["amount"],
                "user_uuid": user_uuid,
                "used_at": used_at,
            }
        })
    except Exception as e:
        return { "code": 400, "message": f"兑换失败: {str(e)}" }
    finally:
        connection.close()

@ai_page.route("/redeem-code/list/", methods=["GET"])
@login_required
@op_required
def ai_redeem_code_list():
    connection = connect()
    sql = "SELECT code, amount, is_used, used_by, valid_from, valid_to, remark, created_at FROM ai_redeem_code ORDER BY created_at DESC"
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql)
            results = cursor.fetchall()
    except Exception as e:
        return { "code": 400, "message": f"查询失败: {str(e)}" }
    finally:
        connection.close()
    
    return jsonify({"code": 200, "message": "查询成功", "data": results})

@ai_page.route("/redeem-code/delete/", methods=["DELETE"])
@login_required
@op_required
def ai_redeem_code_delete():
    codes = request.form.getlist("codes[]")
    if not codes:
        return jsonify({"code": 400, "message": "缺少 codes 参数"}), 400
    connection = connect()
    sql = "DELETE FROM ai_redeem_code WHERE code IN (%s)" % ",".join(["%s"] * len(codes))
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, codes)
        connection.commit()
        return jsonify({"code": 200, "message": "删除成功", "data": {"deleted_count": cursor.rowcount}})
    except Exception as e:
        return { "code": 400, "message": f"删除失败: {str(e)}" }
    finally:
        connection.close()