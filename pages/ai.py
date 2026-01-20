import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import shutil
import uuid
import json
from flask import Blueprint, request, jsonify, Response, stream_with_context, g
from datetime import datetime

from utils.conversation import (
    create_conversation,
    get_conversation,
    update_conversation,
    list_conversations,
    delete_conversation
)
from utils.ai.deepseek import chat as deepseek_chat
from utils.ai.doubao import chat as doubao_chat
from utils.ai.ai import validate_file_ext, validate_file_size
from utils.login import login_required, op_required
from settings import PRODUCT_IMAGE_DIR

import pymysql
from utils.mysql import connect
from utils.ai.basic import *

ai_page = Blueprint('ai', __name__)


# 固定分析提示词
ANALYSIS_PROMPTS = {
    "personal": """【个人分析模式】

我需要你帮我分析以下上传的文件，请：

1. 提取文件中的关键信息和数据
2. 进行数据分析和趋势判断
3. 给出专业的建议和意见
4. 用通俗易懂的语言解释复杂概念
5. 如有多个文件，请逐个分析并给出综合结论

请确保分析清晰、准确、有参考价值。""",
    
    "company": """【企业分析模式】

我需要你以企业级专业顾问的身份分析以下文件，请：

1. 进行全面的数据分析和商业价值评估
2. 识别关键业务指标和风险点
3. 提供战略性建议和优化方案
4. 标出需要重点关注的问题
5. 给出改进建议和实施优先级

分析框架：
- 概要分析（Executive Summary）
- 详细分析（Detailed Analysis）
- 关键指标（Key Metrics）
- 风险评估（Risk Assessment）
- 建议方案（Recommendations）
- 实施计划（Implementation Plan）

请确保分析专业、准确、可操作、具有战略意义。"""
}


def get_analysis_prompt(use_type: str, custom_instruction: str = "") -> str:
    """获取分析提示词"""
    prompt = ANALYSIS_PROMPTS.get(use_type, ANALYSIS_PROMPTS["personal"])
    if custom_instruction:
        prompt += f"\n\n【补充指示】\n{custom_instruction}"
    return prompt


def save_uploaded_files(files, conversation_id: str) -> list:
    """保存上传的文件，返回文件路径列表"""
    if not files:
        return []
    
    base_dir = os.path.expanduser(PRODUCT_IMAGE_DIR)
    saved_files = []
    
    for f in files:
        if not f or f.filename == "":
            continue
        
        # 校验扩展名与大小
        ok_ext, ext_or_err = validate_file_ext(f.filename)
        if not ok_ext:
            raise ValueError(f"文件 {f.filename}: {ext_or_err}")
        
        ok_size, size_or_err = validate_file_size(f)
        if not ok_size:
            raise ValueError(f"文件 {f.filename}: {size_or_err}")
        
        # 保存文件
        file_ext = os.path.splitext(f.filename)[1]
        filename = f"{uuid.uuid4().hex}{file_ext}"
        path = os.path.join(base_dir, "chat-uploads", conversation_id, filename)
        dir_path = os.path.dirname(path)
        
        os.makedirs(dir_path, exist_ok=True)
        f.save(path)
        saved_files.append(path)
    
    return saved_files


# ===================== 会话管理接口 =====================

@ai_page.route("/conversations/", methods=["GET"])
@login_required
def get_user_conversations():
    """获取用户的所有会话ID信息"""
    user_id = g.current_user["uuid"]
    model = request.args.get("model")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))
    
    # try:
    conversations = list_conversations(user_id, model, limit, offset)
    
    # 格式化返回数据，只返回必要的会话信息
    result = []
    for conv in conversations:
        result.append({
            "id": conv["id"],
            "model": conv["model"],
            "title": conv["title"],
            "created_at": conv.get("created_at"),
            "updated_at": conv.get("updated_at"),
            "message_count": len(conv.get("messages", [])) if "messages" in conv else 0
        })
    
    return jsonify({
        "code": 0,
        "data": result,
        "total": len(result)
    })
    # except Exception as e:
    #     return jsonify({
    #         "code": 500,
    #         "message": f"获取会话列表失败: {str(e)}"
    #     })


@ai_page.route("/conversation/<conversation_id>/history/", methods=["GET"])
@login_required
def get_conversation_history(conversation_id):
    """获取会话的历史对话内容（用于会话恢复）"""
    user_id = g.current_user["uuid"]
    
    try:
        conversation = get_conversation(conversation_id, user_id)
        
        if not conversation:
            return jsonify({
                "code": 404,
                "message": "会话不存在或无权访问"
            })
        
        # 返回完整的会话信息
        return jsonify({
            "code": 0,
            "data": {
                "id": conversation["id"],
                "model": conversation["model"],
                "title": conversation["title"],
                "messages": conversation.get("messages", []),
                "files": conversation.get("files", []),
                "created_at": conversation.get("created_at"),
                "updated_at": conversation.get("updated_at")
            }
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取会话历史失败: {str(e)}"
        })


@ai_page.route("/conversation/<conversation_id>/title/", methods=["PUT"])
@login_required
def update_conversation_title(conversation_id):
    """修改会话标题"""
    user_id = g.current_user["uuid"]
    
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "title" not in data:
            return jsonify({
                "code": 400,
                "message": "缺少 title 参数"
            })
        
        new_title = data["title"].strip()
        
        if not new_title:
            return jsonify({
                "code": 400,
                "message": "标题不能为空"
            })
        
        if len(new_title) > 255:
            return jsonify({
                "code": 400,
                "message": "标题过长，最多255个字符"
            })
        
        # 验证会话是否存在且属于当前用户
        conversation = get_conversation(conversation_id, user_id)
        if not conversation:
            return jsonify({
                "code": 404,
                "message": "会话不存在或无权访问"
            })
        
        # 更新标题
        update_conversation(
            conversation_id,
            conversation.get("messages", []),
            conversation.get("files", []),
            new_title,
            conversation.get("file_details", [])
        )
        
        return jsonify({
            "code": 0,
            "message": "标题已更新",
            "data": {
                "id": conversation_id,
                "title": new_title
            }
        })
    
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"更新标题失败: {str(e)}"
        })


@ai_page.route("/conversation/deleteall/", methods=["DELETE"])
@login_required
def delete_all_conversations():
    """删除用户的所有会话"""
    user_id = g.current_user["uuid"]

    limit = 500
    deleted = 0
    files_deleted = 0
    base_dir = os.path.expanduser(PRODUCT_IMAGE_DIR)

    try:
        while True:
            conversations = list_conversations(user_id, None, limit, 0)
            if not conversations:
                break

            for conv in conversations:
                conv_id = conv["id"]

                # 获取完整会话以删除关联文件
                full = get_conversation(conv_id, user_id)
                if full:
                    for fp in full.get("files", []) or []:
                        try:
                            file_path = os.path.expanduser(fp)
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                                files_deleted += 1
                        except Exception:
                            pass

                # 删除上传目录（如果存在）
                upload_dir = os.path.join(base_dir, "chat-uploads", conv_id)
                if os.path.isdir(upload_dir):
                    try:
                        shutil.rmtree(upload_dir)
                    except Exception:
                        pass

                # 删除会话记录
                if delete_conversation(conv_id, user_id):
                    deleted += 1

            if len(conversations) < limit:
                break

        return jsonify({
            "code": 0,
            "message": "所有会话已删除",
            "data": {
                "deleted_conversations": deleted,
                "deleted_files": files_deleted
            }
        })

    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"删除会话失败: {str(e)}"
        })


def save_uploaded_files(files, conversation_id: str) -> list:
    """保存上传的文件，返回文件路径列表"""
    if not files:
        return []
    
    base_dir = os.path.expanduser(PRODUCT_IMAGE_DIR)
    saved_files = []
    
    for f in files:
        if not f or f.filename == "":
            continue
        
        # 校验扩展名与大小
        ok_ext, ext_or_err = validate_file_ext(f.filename)
        if not ok_ext:
            raise ValueError(f"文件 {f.filename}: {ext_or_err}")
        
        ok_size, size_or_err = validate_file_size(f)
        if not ok_size:
            raise ValueError(f"文件 {f.filename}: {size_or_err}")
        
        # 保存文件
        file_ext = os.path.splitext(f.filename)[1]
        filename = f"{uuid.uuid4().hex}{file_ext}"
        path = os.path.join(base_dir, "chat-uploads", conversation_id, filename)
        dir_path = os.path.dirname(path)
        
        os.makedirs(dir_path, exist_ok=True)
        f.save(path)
        saved_files.append(path)
    
    return saved_files


@ai_page.route("/chat/new/", methods=["POST"])
@login_required
def new_conversation():
    """创建新对话"""
    user_id = g.current_user["uuid"]
    model = request.form.get("model", "deepseek")
    title = request.form.get("title", "新对话")
    prompt = request.form.get("prompt", "")
    
    # 验证模型
    if model not in {"deepseek", "doubao"}:
        return jsonify({"code": 400, "message": "不支持的模型"})
    
    # 创建对话
    conversation = create_conversation(user_id, model, title)
    conversation_id = conversation["id"]
    
    # 如果有初始消息，保存文件并开始对话
    if prompt:
        try:
            files = request.files.getlist("files")
            saved_files = save_uploaded_files(files, conversation_id)
            
            # 保存到数据库
            if saved_files:
                update_conversation(conversation_id, [], saved_files)
            
            def generate():
                try:
                    # 构建消息
                    messages = [{"role": "user", "content": prompt}]
                    
                    # 调用对应的 AI 模型
                    if model == "deepseek":
                        chat_func = deepseek_chat
                    else:
                        chat_func = doubao_chat
                    
                    # 流式输出响应
                    yield f"event: start\ndata: {json.dumps({'conversation_id': conversation_id, 'status': 'started'})}\n\n"
                    
                    response_text = ""
                    for chunk in chat_func(messages=messages, files=saved_files if saved_files else None):
                        chunk_str = chunk if isinstance(chunk, str) else json.dumps(chunk, ensure_ascii=False)
                        response_text += chunk_str
                        yield f"event: message\ndata: {json.dumps({'message': chunk_str})}\n\n"
                    
                    # 保存对话到数据库
                    messages.append({"role": "assistant", "content": response_text})
                    update_conversation(conversation_id, messages, saved_files)
                    
                    yield f"event: end\ndata: {json.dumps({'status': 'completed'})}\n\n"
                
                except Exception as e:
                    yield f"event: error\ndata: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
            
            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
            )
        
        except ValueError as e:
            return jsonify({"code": 400, "message": str(e)})
        except Exception as e:
            return jsonify({"code": 500, "message": f"处理失败: {str(e)}"})
    
    return jsonify({
        "code": 0,
        "data": {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "model": model,
            "title": title
        }
    })


@ai_page.route("/chat/continue/<conversation_id>/", methods=["POST"])
@login_required
def continue_conversation(conversation_id):
    """继续对话"""
    user_id = g.current_user["uuid"]
    prompt = request.form.get("prompt", "")
    
    if not prompt:
        return jsonify({"code": 400, "message": "提示词不能为空"})
    
    # 获取对话
    conversation = get_conversation(conversation_id, user_id)
    if not conversation:
        return jsonify({"code": 404, "message": "对话不存在"})
    
    model = conversation["model"]
    messages = conversation["messages"]
    conversation_files = conversation["files"]
    
    try:
        # 保存新上传的文件
        files = request.files.getlist("files")
        if files:
            new_files = save_uploaded_files(files, conversation_id)
            conversation_files.extend(new_files)
        
        def generate():
            try:
                # 添加新的用户消息
                messages.append({"role": "user", "content": prompt})
                
                # 调用对应的 AI 模型
                if model == "deepseek":
                    chat_func = deepseek_chat
                else:
                    chat_func = doubao_chat
                
                # 流式输出响应
                yield f"event: start\ndata: {json.dumps({'conversation_id': conversation_id, 'status': 'started'})}\n\n"
                
                response_text = ""
                for chunk in chat_func(messages=messages, files=conversation_files if conversation_files else None):
                    chunk_str = chunk if isinstance(chunk, str) else json.dumps(chunk, ensure_ascii=False)
                    response_text += chunk_str
                    yield f"event: message\ndata: {json.dumps({'message': chunk_str})}\n\n"
                
                # 保存助手响应到数据库
                messages.append({"role": "assistant", "content": response_text})
                update_conversation(conversation_id, messages, conversation_files)
                
                yield f"event: end\ndata: {json.dumps({'status': 'completed'})}\n\n"
            
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
        
        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )
    
    except ValueError as e:
        return jsonify({"code": 400, "message": str(e)})
    except Exception as e:
        return jsonify({"code": 500, "message": f"处理失败: {str(e)}"})


@ai_page.route("/list/", methods=["GET"])
@login_required
def list_user_conversations():
    """列出用户的所有对话"""
    user_id = g.current_user["uuid"]
    model = request.args.get("model")  # 可选：按模型筛选
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    
    conversations = list_conversations(user_id, model, limit, offset)
    
    return jsonify({
        "code": 0,
        "data": conversations
    })


@ai_page.route("/get/<conversation_id>/", methods=["GET"])
@login_required
def get_conversation_detail(conversation_id):
    """获取对话详情（包括完整的消息历史）"""
    user_id = g.current_user["uuid"]
    
    conversation = get_conversation(conversation_id, user_id)
    if not conversation:
        return jsonify({"code": 404, "message": "对话不存在"})
    
    return jsonify({
        "code": 0,
        "data": conversation
    })


@ai_page.route("/delete/<conversation_id>/", methods=["DELETE"])
@login_required
def delete_conversation_endpoint(conversation_id):
    """删除对话"""
    user_id = g.current_user["uuid"]
    
    if not delete_conversation(conversation_id, user_id):
        return jsonify({"code": 404, "message": "对话不存在"})
    
    return jsonify({
        "code": 0,
        "message": "对话已删除"
    })


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
    # 获取分页参数
    page = request.args.get("page", 1, type=int)
    range_size = request.args.get("range", 10, type=int)

    # 排序与检索参数
    sort_by = request.args.get("sort_by", "created_at", type=str)
    order = request.args.get("order", "desc", type=str).lower()

    # 过滤参数
    is_effective = request.args.get("is_effective", type=str)  # active/inactive
    is_used = request.args.get("is_used", type=int)
    amount = request.args.get("amount", type=int)
    amount_min = request.args.get("amount_min", type=int)
    amount_max = request.args.get("amount_max", type=int)
    used_by = request.args.get("used_by", type=str)
    code = request.args.get("code", type=str)

    created_start = request.args.get("created_start", type=str)
    created_end = request.args.get("created_end", type=str)
    valid_from_start = request.args.get("valid_from_start", type=str)
    valid_from_end = request.args.get("valid_from_end", type=str)
    valid_to_start = request.args.get("valid_to_start", type=str)
    valid_to_end = request.args.get("valid_to_end", type=str)

    # 参数验证
    if page < 1:
        return jsonify({"code": 400, "message": "page 必须大于等于1"}), 400
    if range_size < 1 or range_size > 500:
        return jsonify({"code": 400, "message": "range 必须在1-500之间"}), 400

    allowed_sort_fields = {
        "amount": "amount",
        "valid_from": "valid_from",
        "valid_to": "valid_to",
        "created_at": "created_at",
        "is_used": "is_used"
    }
    if sort_by not in allowed_sort_fields:
        sort_by = "created_at"
    if order not in ("asc", "desc"):
        order = "desc"

    # 计算分页偏移量
    offset = (page - 1) * range_size

    # 构建 WHERE 条件
    where_clauses = []
    params = []

    # 手动检索：金额
    if amount is not None:
        where_clauses.append("amount = %s")
        params.append(amount)
    else:
        if amount_min is not None:
            where_clauses.append("amount >= %s")
            params.append(amount_min)
        if amount_max is not None:
            where_clauses.append("amount <= %s")
            params.append(amount_max)

    # 手动检索：使用者 uuid
    if used_by:
        where_clauses.append("used_by = %s")
        params.append(used_by)

    # 手动检索：code 支持模糊
    if code:
        where_clauses.append("code LIKE %s")
        params.append(f"%{code}%")

    # 手动检索：是否使用
    if is_used is not None:
        where_clauses.append("is_used = %s")
        params.append(is_used)

    # 有效期状态过滤
    # active: 当前时间在有效期内；inactive: 未到生效或已过期
    if is_effective in ("active", "inactive"):
        if is_effective == "active":
            where_clauses.append("((valid_from IS NULL OR valid_from <= NOW()) AND (valid_to IS NULL OR valid_to >= NOW()))")
        else:
            # 未生效或已过期
            where_clauses.append("((valid_from IS NOT NULL AND valid_from > NOW()) OR (valid_to IS NOT NULL AND valid_to < NOW()))")

    # 时间范围过滤：创建时间
    if created_start:
        where_clauses.append("created_at >= %s")
        params.append(created_start)
    if created_end:
        where_clauses.append("created_at <= %s")
        params.append(created_end)

    # 时间范围过滤：valid_from
    if valid_from_start:
        where_clauses.append("valid_from >= %s")
        params.append(valid_from_start)
    if valid_from_end:
        where_clauses.append("valid_from <= %s")
        params.append(valid_from_end)

    # 时间范围过滤：valid_to
    if valid_to_start:
        where_clauses.append("valid_to >= %s")
        params.append(valid_to_start)
    if valid_to_end:
        where_clauses.append("valid_to <= %s")
        params.append(valid_to_end)

    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    connection = connect()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # 统计总数
            count_sql = f"SELECT COUNT(*) as total FROM ai_redeem_code{where_sql}"
            cursor.execute(count_sql, params)
            total_result = cursor.fetchone()
            total = total_result['total'] if total_result else 0

            # 查询数据
            select_sql = (
                "SELECT code, amount, is_used, used_by, valid_from, valid_to, remark, created_at "
                "FROM ai_redeem_code"
                f"{where_sql} "
                f"ORDER BY {allowed_sort_fields[sort_by]} {order.upper()} "
                "LIMIT %s OFFSET %s"
            )
            exec_params = list(params)
            exec_params.extend([range_size, offset])
            cursor.execute(select_sql, exec_params)
            results = cursor.fetchall()
    except Exception as e:
        return jsonify({"code": 400, "message": f"查询失败: {str(e)}"}), 400
    finally:
        connection.close()

    # 计算总页数
    total_pages = (total + range_size - 1) // range_size

    return jsonify({
        "code": 200,
        "message": "查询成功",
        "data": results,
        "pagination": {
            "page": page,
            "range": range_size,
            "total": total,
            "total_pages": total_pages
        }
    })

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