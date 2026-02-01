import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import shutil
import uuid
import json
import time
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
from utils.ai.usage_tracker import AIUsageTracker
from utils.login import login_required, op_required
from settings import PRODUCT_IMAGE_DIR

import pymysql
import requests
from utils.mysql import connect
from utils.ai.basic import *

ai_page = Blueprint('ai', __name__)


def get_remote_file_size(url: str) -> int:
    """
    通过HEAD请求获取远程文件的大小（bytes）
    
    Args:
        url: 文件URL
    
    Returns:
        文件大小（bytes），如果获取失败返回 -1
    """
    try:
        response = requests.head(url, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            content_length = response.headers.get('content-length')
            if content_length:
                return int(content_length)
        return -1
    except Exception:
        return -1


# 固定分析提示词
ANALYSIS_PROMPTS = {
    "personal2": """不用管我上传的文件，随便输出一点markdown格式的文本内容+表格测试一下，限制100token""",
    "personal": """个人征信
第一个步骤  写清楚客户的姓名 年纪
贷款的余额。和担保的余额。(同一个银行核算到一笔)只需要总结未结清的部分，单位万元列举清楚 银行名称和对应的余额担保的贷款 核算贷款的总和 和担保的总和贷款发一个文字清单，担保的发文字清单按排列下顺序，标注数字。数字需要精，核算清楚，不能有任何错误(最后核验比对贷款的汇总金额是否错误的话 就比对 信贷交易授信及负债信息概要里面的，循环贷账户+非循环贷里面的余额 想加一起就可以，核验贷款管理机构数量=非循环贷管理机构数=循环贷账户管理机构数合计一起)  住房贷款 正常核算，但是不计入负债好
第二个步骤 
只需需要写银行名称  和对应的余额  汇总   验算步骤 不要写出来了   
先按照第1个步骤运行，然后再按照第2个步骤，全部弄好之后，直接弄个表格发给我

【重要约束】
你必须严格遵循上述指令，第一次回复时必须按照这个格式执行分析，不能有任何偏离，必须严格使用表格的形式输出，贷款余额保留2位小数，必须准确。表格结构为银行、贷款/担保/未结清担保余额、备注（如有），如果一个表格中遇到相同的银行，则合并，每个表格结尾做一个合计，必须保证数据准确无误，可进行多次运算，但不要输出多余计算内容""",
    
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
        messages = conv.get("messages") or []
        result.append({
            "id": conv["id"],
            "model": conv["model"],
            "title": conv["title"],
            "analysis_type": conv.get("analysis_type"),
            "is_analysis": bool(conv.get("analysis_type")),
            "created_at": conv.get("created_at"),
            "updated_at": conv.get("updated_at"),
            "message_count": len(messages)
        })
    
    return jsonify({
        "code": 200,
        "data": result,
        "total": len(result)
    })
    # except Exception as e:
    #     return jsonify({
    #         "code": 500,
    #         "message": f"获取会话列表失败: {str(e)}"
    #     })


@ai_page.route("/conversation/<conversation_id>/history/", methods=["GET"])
def get_conversation_history(conversation_id):
    """获取会话的历史对话内容（用于会话恢复或查看分享的会话）"""
    # 尝试获取当前用户ID（支持已登录和未登录用户）
    user_id = None
    
    # 尝试从 token 获取用户信息（如果用户已登录）
    token = request.headers.get('Authorization')
    if token and token.startswith('Bearer '):
        token = token[7:]
    if not token:
        token = request.headers.get('X-Token')
    
    if token:
        conn = connect()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                from datetime import datetime, timezone
                # 查询有效的 token 和用户信息
                cursor.execute("""
                    SELECT u.*
                    FROM user_token t
                    JOIN user u ON t.uuid = u.uuid
                    WHERE t.token = %s AND t.expire_at > %s
                """, (token, datetime.now(timezone.utc)))
                user = cursor.fetchone()
                if user:
                    g.current_user = user
                    user_id = user.get("uuid")
        finally:
            conn.close()
    
    try:
        # 首先从数据库直接查询会话信息，以获取share字段
        conn = connect()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = "SELECT id, user_id, share FROM conversations WHERE id = %s"
                cursor.execute(sql, (conversation_id,))
                conversation_meta = cursor.fetchone()
        finally:
            conn.close()
        
        if not conversation_meta:
            return jsonify({
                "code": 404,
                "message": "会话不存在"
            }), 404
        
        # 检查访问权限
        is_owner = user_id and user_id == conversation_meta["user_id"]
        # 明确转换为布尔值，处理 NULL、0、1 等各种情况
        is_shared = bool(conversation_meta.get("share"))
        
        # print(user_id, conversation_meta["user_id"], is_owner, is_shared)

        # 只有所有者或分享公开的会话才能被访问
        if not is_owner and not is_shared:
            return jsonify({
                "code": 403,
                "message": "无权访问此会话"
            }), 403
        
        # 获取完整的会话信息
        conversation = get_conversation(conversation_id, conversation_meta["user_id"])
        
        if not conversation:
            return jsonify({
                "code": 404,
                "message": "会话不存在"
            }), 404
        
        # 返回完整的会话信息
        return jsonify({
            "code": 200,
            "data": {
                "id": conversation["id"],
                "model": conversation["model"],
                "title": conversation["title"],
                "analysis_type": conversation.get("analysis_type"),
                "is_analysis": bool(conversation.get("analysis_type")),
                "messages": conversation.get("messages", []),
                "files": conversation.get("files", []),
                "created_at": conversation.get("created_at"),
                "updated_at": conversation.get("updated_at"),
                "share": conversation.get("share", False),
                "owner_id": conversation_meta["user_id"]
            }
        }), 200
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取会话历史失败: {str(e)}"
        }), 500


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
            "code": 200,
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


@ai_page.route("/conversation/<conversation_id>/share/", methods=["PUT"])
@login_required
def update_conversation_share(conversation_id):
    """修改会话分享状态"""
    user_id = g.current_user["uuid"]
    
    try:
        # 获取请求数据
        data = request.get_json()
        if data is None or "share" not in data:
            return jsonify({
                "code": 400,
                "message": "缺少 share 参数"
            }), 400
        
        share = data["share"]
        
        # 验证share参数类型
        if not isinstance(share, bool):
            return jsonify({
                "code": 400,
                "message": "share 参数必须是布尔值 (true/false)"
            }), 400
        
        # 验证会话是否存在且属于当前用户
        conversation = get_conversation(conversation_id, user_id)
        if not conversation:
            return jsonify({
                "code": 404,
                "message": "会话不存在或无权访问"
            }), 404
        
        # 更新分享状态
        conn = connect()
        try:
            with conn.cursor() as cursor:
                sql = "UPDATE conversations SET share = %s WHERE id = %s AND user_id = %s"
                cursor.execute(sql, (share, conversation_id, user_id))
                conn.commit()
                
                if cursor.rowcount == 0:
                    return jsonify({
                        "code": 404,
                        "message": "会话不存在或无权访问"
                    }), 404
            
            return jsonify({
                "code": 200,
                "message": "分享状态已更新",
                "data": {
                    "id": conversation_id,
                    "share": share
                }
            })
        finally:
            conn.close()
    
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"更新分享状态失败: {str(e)}"
        }), 500


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
            "code": 200,
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


def validate_and_prepare_files(file_urls=None, file_names=None, conversation_id=None):
    """
    验证并准备URL文件列表（仅支持公网URL）
    
    参数：
        file_urls: 公网URL列表
        file_names: 对应的文件原名列表（必须与file_urls一一对应）
        conversation_id: 对话ID
    
    仅支持 PDF 和图片文件
    
    返回格式：[
        {"type": "image_url", "url": "https://...jpg", "original_name": "photo.jpg"},
        {"type": "file_url", "url": "https://...pdf", "original_name": "report.pdf"}
    ]
    """
    ALLOWED_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    ALLOWED_PDF_EXTS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md', '.csv'}
    ALLOWED_ALL = ALLOWED_IMAGE_EXTS | ALLOWED_PDF_EXTS
    
    result = []
    
    # 处理公网URL
    if file_urls:
        # 确保file_urls是列表
        if isinstance(file_urls, str):
            file_urls = [file_urls]
        
        # 确保file_names是列表且与file_urls长度相同
        if file_names is None:
            file_names = [None] * len(file_urls)
        elif isinstance(file_names, str):
            file_names = [file_names]
        
        if len(file_names) != len(file_urls):
            raise ValueError(f"文件名列表长度({len(file_names)})与URL列表长度({len(file_urls)})不匹配")
        
        for url, original_name in zip(file_urls, file_names):
            if not url or not isinstance(url, str):
                continue
            
            url = url.strip()
            if not url:
                continue
            
            # 验证URL格式
            if not (url.startswith('http://') or url.startswith('https://')):
                raise ValueError(f"无效的URL: {url}，必须以 http:// 或 https:// 开头")
            
            # 从URL提取文件名用于验证扩展名
            filename = url.split('/')[-1].split('?')[0]  # 去掉查询参数
            if not filename or '.' not in filename:
                raise ValueError(f"无法从URL提取文件名: {url}")
            
            # 验证文件扩展名（仅PDF和图片）
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext not in ALLOWED_ALL:
                raise ValueError(f"文件扩展名 {file_ext}: 仅支持 PDF 和图片文件 (.pdf, .jpg, .jpeg, .png, .gif, .bmp, .webp)")
            
            # 使用传入的原名，如果未提供则使用从URL提取的名称
            display_name = original_name.strip() if original_name and isinstance(original_name, str) else filename
            
            # 验证原名扩展名
            original_ext = os.path.splitext(display_name)[1].lower()
            if original_ext not in ALLOWED_ALL:
                raise ValueError(f"文件 {display_name}: 仅支持 PDF 和图片文件 (.pdf, .jpg, .jpeg, .png, .gif, .bmp, .webp)")
            
            # 根据类型生成对应的格式
            if original_ext in ALLOWED_IMAGE_EXTS:
                file_size = get_remote_file_size(url)
                result.append({
                    "type": "image_url",
                    "url": url,
                    "original_name": display_name,
                    "size": file_size
                })
            elif original_ext in ALLOWED_PDF_EXTS:
                file_size = get_remote_file_size(url)
                result.append({
                    "type": "file_url",
                    "url": url,
                    "original_name": display_name,
                    "size": file_size
                })
    
    return result


def prepare_files_for_ai_model(file_objects: list) -> dict:
    """
    为AI模型准备文件参数
    
    输入格式：[
        {"type": "local_file", "path": "/path/to/file.pdf"},
        {"type": "image_url", "url": "https://...jpg"},
        {"type": "file_url", "url": "https://...pdf"}
    ]
    
    输出格式：{
        "images": ["https://image1.jpg", "https://image2.jpg"],
        "files": ["/local/path1.pdf", "https://remote.pdf"]
    }
    """
    images = []
    files = []
    
    for item in file_objects:
        if not isinstance(item, dict):
            continue
        
        item_type = item.get("type")
        
        if item_type == "local_file":
            files.append(item.get("path"))
        elif item_type == "image_url":
            images.append(item.get("url"))
        elif item_type == "file_url":
            files.append(item.get("url"))
    
    return {
        "images": images if images else None,
        "files": files if files else None
    }


def save_uploaded_files(files, conversation_id: str) -> list:
    """保存上传的文件，返回包含文件路径和原始文件名的对象列表"""
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
        
        # 返回包含原始文件名和路径的对象
        saved_files.append({
            "path": path,
            "original_name": f.filename
        })
    
    return saved_files


def extract_file_paths(file_objects: list) -> list:
    """从文件对象列表中提取路径列表（用于传给AI模型）"""
    if not file_objects:
        return []
    return [f["path"] if isinstance(f, dict) else f for f in file_objects]


@ai_page.route("/chat/new/", methods=["POST"])
@login_required
def new_conversation():
    """创建新对话（仅创建会话，返回会话ID）"""
    user_id = g.current_user["uuid"]
    data = request.get_json() or {}
    
    model = data.get("model", "deepseek")
    title = data.get("title", "新对话")
    
    # 验证模型
    if model not in {"deepseek", "doubao"}:
        return jsonify({"code": 400, "message": "不支持的模型"})
    
    # 创建对话
    conversation = create_conversation(user_id, model, title)
    conversation_id = conversation["id"]
    
    return jsonify({
        "code": 200,
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
    data = request.get_json() or {}
    prompt = data.get("prompt", "")
    think = data.get("think", False)
    
    if not prompt:
        return jsonify({"code": 400, "message": "提示词不能为空"})
    
    # 获取对话
    conversation = get_conversation(conversation_id, user_id)
    if not conversation:
        return jsonify({"code": 404, "message": "对话不存在"})
    
    # 检查是否是分析类型的会话（普通对话不扣配额）
    analysis_type = conversation.get("analysis_type")
    
    model = conversation["model"]
    messages = conversation["messages"]
    conversation_files = conversation["files"]
    
    try:
        # 分析会话提前校验配额，不足直接返回 JSON 错误
        quota_cost = 1 if analysis_type == "personal" else 2 if analysis_type else 0
        if analysis_type:
            has_enough, current_quota = check_analysis_quota(user_id, analysis_type)
            if not has_enough:
                def generate_quota_error():
                    # 先推送一条注释行以触发客户端建立事件流
                    yield ": keep-alive\n\n"
                    # 先发 start 事件，确保前端建立 SSE 监听后能收到 error 事件
                    yield f"event: start\ndata: {json.dumps({'conversation_id': conversation_id, 'status': 'started'})}\n\n"
                    payload = {
                        "status": "error",
                        "code": 402,
                        "message": "配额不足",
                        "data": {"required": quota_cost, "current": current_quota}
                    }
                    yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    # 结束事件，避免前端长时间等待
                    yield f"event: end\ndata: {json.dumps({'status': 'error'})}\n\n"
                return Response(
                    stream_with_context(generate_quota_error()),
                    mimetype="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache, no-transform",
                        "Pragma": "no-cache",
                        "X-Accel-Buffering": "no",
                        "Connection": "keep-alive",
                        "Content-Type": "text/event-stream; charset=utf-8"
                    },
                    status=200
                )
        # 仅支持公网URL
        file_urls = data.get("file_urls") or []
        file_names = data.get("file_names") or []
        
        # 确保是列表
        if isinstance(file_urls, str):
            file_urls = [file_urls]
        if isinstance(file_names, str):
            file_names = [file_names]
        
        # 验证并准备新的文件
        new_file_objects = validate_and_prepare_files(file_urls, file_names, conversation_id)
        
        # 转换为数据库格式，保留原始文件名和文件大小便于审计
        new_db_files = []
        for obj in new_file_objects:
            if obj["type"] == "local_file":
                new_db_files.append({
                    "path": obj["path"],
                    "original_name": obj["original_name"],
                    "size": obj.get("size", -1)
                })
            elif obj["type"] == "image_url":
                new_db_files.append({
                    "url": obj["url"],
                    "type": "image_url",
                    "original_name": obj.get("original_name"),
                    "size": obj.get("size", -1)
                })
            elif obj["type"] == "file_url":
                new_db_files.append({
                    "url": obj["url"],
                    "type": "file_url",
                    "original_name": obj.get("original_name"),
                    "size": obj.get("size", -1)
                })
        
        # 扩展会话文件列表
        if new_db_files:
            conversation_files.extend(new_db_files)

        def generate():
            # try:
                # 如果是分析类型的会话，扣除配额
                if analysis_type:
                    if not deduct_analysis_quota(user_id, analysis_type):
                        yield f"event: error\ndata: {json.dumps({'status': 'error', 'message': '配额扣除失败'})}\n\n"
                        return
                
                # 构建用户消息 - 如果有文件，需要构建多模态内容格式
                if new_file_objects:
                    # 对 deepseek 强制纯文本描述；其他模型保留多模态
                    if model == "deepseek":
                        desc = []
                        for fo in new_file_objects:
                            if fo.get("type") == "image_url":
                                desc.append(f"[图片] {fo.get('url')}")
                            elif fo.get("type") == "file_url":
                                desc.append(f"[文件] {fo.get('url')}")
                        desc.append(prompt)
                        user_message = {"role": "user", "content": "\n".join([d for d in desc if d]), "files": new_db_files}
                    else:
                        content = []
                        for file_obj in new_file_objects:
                            if file_obj.get("type") == "image_url":
                                content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": file_obj.get("url")
                                    }
                                })
                            elif file_obj.get("type") == "file_url":
                                content.append({
                                    "type": "file_url",
                                    "file_url": {
                                        "url": file_obj.get("url")
                                    }
                                })
                        content.append({"type": "text", "text": prompt})
                        user_message = {"role": "user", "content": content, "files": new_db_files}
                else:
                    user_message = {"role": "user", "content": prompt}
                
                messages.append(user_message)

                # 调用对应的 AI 模型
                if model == "deepseek":
                    chat_func = deepseek_chat
                else:
                    chat_func = doubao_chat

                # 流式输出响应
                yield f"event: start\ndata: {json.dumps({'conversation_id': conversation_id, 'status': 'started'})}\n\n"

                response_text = ""
                # 不通过 files 参数，因为文件已在 messages 中
                for chunk in chat_func(messages=messages, user_id=user_id, think=think, conversation_id=conversation_id):
                    chunk_str = chunk if isinstance(chunk, str) else json.dumps(chunk, ensure_ascii=False)
                    response_text += chunk_str
                    yield f"event: message\ndata: {json.dumps({'message': chunk_str})}\n\n"

                # 保存助手响应到数据库
                messages.append({"role": "assistant", "content": response_text})
                update_conversation(conversation_id, messages, conversation_files)

                # 返回成功状态，如果是分析类型则包含配额消耗信息
                end_data = {'status': 'completed'}
                if analysis_type:
                    end_data['quota_cost'] = quota_cost
                yield f"event: end\ndata: {json.dumps(end_data)}\n\n"
            # except Exception as e:
            #     yield f"event: error\ndata: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

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
        "code": 200,
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
        "code": 200,
        "data": conversation
    })


@ai_page.route("/conversation/delete/<conversation_id>/", methods=["DELETE"])
@login_required
def delete_conversation_endpoint(conversation_id):
    """删除对话"""
    user_id = g.current_user["uuid"]
    
    if not delete_conversation(conversation_id, user_id):
        return jsonify({"code": 404, "message": "对话不存在"})
    
    return jsonify({
        "code": 200,
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
    data = request.get_json() or {}
    code = data.get("code")
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
    data = request.get_json() or {}
    codes = data.get("codes")
    if not codes:
        return jsonify({"code": 400, "message": "缺少 codes 参数"}), 400
    if isinstance(codes, str):
        codes = [codes]
    if not isinstance(codes, (list, tuple)):
        return jsonify({"code": 400, "message": "codes 参数格式错误"}), 400
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


# ========== AI使用统计接口 ==========

@ai_page.route("/usage/stats/", methods=["GET"])
@login_required
def get_usage_stats():
    """
    获取用户AI使用统计
    
    参数:
        time_range: 时间范围 (1h, 1d, 1w, 1y)，默认 1d
        model_key: 模型标识（可选），不传则查询所有模型
    
    返回:
        {
            "code": 200,
            "data": {
                "time_range": "1d",
                "start_time": "2024-01-01 00:00:00",
                "end_time": "2024-01-02 00:00:00",
                "models": [
                    {
                        "model_key": "deepseek-chat",
                        "provider": "deepseek",
                        "request_count": 10,
                        "tokens": {
                            "input": 1000,
                            "output": 500,
                            "total": 1500,
                            "cache_hit": 200,
                            "cache_miss": 800
                        },
                        "cost": {
                            "input": 0.001,
                            "output": 0.0015,
                            "cache_hit": 0.00004,
                            "total": 0.00254
                        }
                    }
                ],
                "summary": {
                    "total_requests": 10,
                    "total_tokens": 1500,
                    "total_cost": 0.00254
                }
            }
        }
    """
    user_id = g.current_user["uuid"]
    time_range = request.args.get("time_range", "1d")
    model_key = request.args.get("model_key")
    
    # 验证时间范围
    if time_range not in {"1h", "1d", "1w", "1y"}:
        return jsonify({"code": 400, "message": "无效的时间范围，支持: 1h, 1d, 1w, 1y"})
    
    try:
        stats = AIUsageTracker.get_user_usage_stats(user_id, time_range, model_key)
        return jsonify({
            "code": 200,
            "data": stats
        })
    except Exception as e:
        return jsonify({"code": 500, "message": f"查询失败: {str(e)}"})


@ai_page.route("/usage/history/", methods=["GET"])
@login_required
def get_usage_history():
    """
    获取用户AI使用历史记录
    
    参数:
        time_range: 时间范围 (1h, 1d, 1w, 1y)，默认 1d
        limit: 返回记录数，默认 100
    
    返回:
        {
            "code": 200,
            "data": [
                {
                    "id": 1,
                    "conversation_id": "xxx",
                    "model_key": "deepseek-chat",
                    "provider": "deepseek",
                    "tokens": {...},
                    "cost": {...},
                    "created_at": "2024-01-01 12:00:00"
                }
            ]
        }
    """
    user_id = g.current_user["uuid"]
    time_range = request.args.get("time_range", "1d")
    limit = int(request.args.get("limit", 100))
    
    # 验证时间范围
    if time_range not in {"1h", "1d", "1w", "1y"}:
        return jsonify({"code": 400, "message": "无效的时间范围，支持: 1h, 1d, 1w, 1y"})
    
    # 限制最大记录数
    if limit > 1000:
        limit = 1000
    
    try:
        history = AIUsageTracker.get_user_usage_history(user_id, time_range, limit)
        return jsonify({
            "code": 200,
            "data": history
        })
    except Exception as e:
        return jsonify({"code": 500, "message": f"查询失败: {str(e)}"})


@ai_page.route("/model/config/", methods=["GET"])
@login_required
@op_required
def get_model_config_endpoint():
    """
    获取模型配置（管理员）
    
    参数:
        model_key: 模型标识
    """
    model_key = request.args.get("model_key")
    if not model_key:
        return jsonify({"code": 400, "message": "缺少 model_key 参数"})
    
    try:
        config = AIUsageTracker.get_model_config(model_key)
        if not config:
            return jsonify({"code": 404, "message": "模型配置不存在"})
        
        return jsonify({
            "code": 200,
            "data": config
        })
    except Exception as e:
        return jsonify({"code": 500, "message": f"查询失败: {str(e)}"})


@ai_page.route("/model/config/add/", methods=["POST"])
@login_required
@op_required
def add_model_config_endpoint():
    """
    添加或更新模型配置（管理员）
    
    参数:
        model_key: 模型标识
        model_name: 模型名称
        provider: 提供商
        input_price: 输入价格（元/百万tokens）
        output_price: 输出价格（元/百万tokens）
        cache_hit_price: 缓存命中价格（可选）
        input_threshold: 输入分段阈值（可选）
        output_threshold: 输出分段阈值（可选）
    """
    data = request.get_json()
    
    required_fields = ["model_key", "model_name", "provider", "input_price", "output_price"]
    for field in required_fields:
        if field not in data:
            return jsonify({"code": 400, "message": f"缺少必填参数: {field}"})
    
    try:
        success = AIUsageTracker.add_model_config(
            model_key=data["model_key"],
            model_name=data["model_name"],
            provider=data["provider"],
            input_price=float(data["input_price"]),
            output_price=float(data["output_price"]),
            cache_hit_price=float(data.get("cache_hit_price", 0)) if data.get("cache_hit_price") else None,
            input_threshold=int(data.get("input_threshold")) if data.get("input_threshold") else None,
            output_threshold=int(data.get("output_threshold")) if data.get("output_threshold") else None
        )
        
        if success:
            return jsonify({
                "code": 200,
                "message": "配置保存成功"
            })
        else:
            return jsonify({"code": 500, "message": "配置保存失败"})
    
    except Exception as e:
        return jsonify({"code": 500, "message": f"操作失败: {str(e)}"})


@ai_page.route("/platform-stats/", methods=["GET"])
@login_required
@op_required
def get_platform_stats():
    """
    获取全平台模型使用统计（管理员）
    
    参数:
        time_range: 时间范围 (1h, 1d, 1w, 1y, all)，默认 1d
        model_key: 模型标识（可选），不传则查询所有模型
    
    返回:
        {
            "code": 200,
            "data": {
                "time_range": "1d",
                "start_time": "2024-01-01 00:00:00",
                "end_time": "2024-01-02 00:00:00",
                "models": [
                    {
                        "model_key": "deepseek-chat",
                        "provider": "deepseek",
                        "user_count": 50,
                        "request_count": 1000,
                        "tokens": {...},
                        "cost": {...},
                        "usage_period": {...}
                    }
                ],
                "summary": {
                    "total_unique_users": 50,
                    "total_requests": 1000,
                    "total_tokens": 150000,
                    "total_cost": 0.45,
                    "avg_cost_per_request": 0.00045,
                    "avg_tokens_per_request": 150
                }
            }
        }
    """
    time_range = request.args.get("time_range", "1d")
    model_key = request.args.get("model_key")
    
    # 验证时间范围
    if time_range not in {"1h", "1d", "1w", "1y", "all"}:
        return jsonify({"code": 400, "message": "无效的时间范围，支持: 1h, 1d, 1w, 1y, all"})
    
    try:
        stats = AIUsageTracker.get_platform_model_stats(time_range, model_key)
        
        if 'error' in stats:
            return jsonify({"code": 500, "message": stats['error']})
        
        return jsonify({
            "code": 200,
            "data": stats
        })
    except Exception as e:
        return jsonify({"code": 500, "message": f"查询失败: {str(e)}"})


@ai_page.route("/time-series-stats/", methods=["GET"])
@login_required
@op_required
def get_time_series_stats():
    """
    获取时间序列统计数据（管理员）
    
    参数:
        time_range: 时间范围 (1h, 1d, 1w, 1y, all)，默认 1d
        model_key: 模型标识（可选），不传则查询所有模型
    """
    time_range = request.args.get("time_range", "1d")
    model_key = request.args.get("model_key")

    if time_range not in {"1h", "1d", "1w", "1y", "all"}:
        return jsonify({"code": 400, "message": "无效的时间范围，支持: 1h, 1d, 1w, 1y, all"})

    try:
        stats = AIUsageTracker.get_time_series_stats(time_range, model_key)
        if 'error' in stats:
            return jsonify({"code": 500, "message": stats['error']})
        return jsonify({
            "code": 200,
            "data": stats
        })
    except Exception as e:
        return jsonify({"code": 500, "message": f"查询失败: {str(e)}"})


@ai_page.route("/user-ranking/", methods=["GET"])
@login_required
@op_required
def get_user_ranking():
    """
    获取用户使用排行榜（管理员）
    
    参数:
        time_range: 时间范围 (1h, 1d, 1w, 1y, all)，默认 1d
        model_key: 模型标识（可选）
        order_by: 排序字段 (cost, tokens, requests)，默认 cost
        limit: 返回数量，默认 50，最大 200
    
    返回:
        {
            "code": 200,
            "data": [
                {
                    "rank": 1,
                    "user_id": "xxx",
                    "request_count": 100,
                    "total_tokens": 15000,
                    "total_cost": 0.045,
                    "avg_cost_per_request": 0.00045,
                    "usage_period": {...}
                }
            ]
        }
    """
    time_range = request.args.get("time_range", "1d")
    model_key = request.args.get("model_key")
    order_by = request.args.get("order_by", "cost")
    limit = int(request.args.get("limit", 50))
    
    # 验证参数
    if time_range not in {"1h", "1d", "1w", "1y", "all"}:
        return jsonify({"code": 400, "message": "无效的时间范围，支持: 1h, 1d, 1w, 1y, all"})
    
    if order_by not in {"cost", "tokens", "requests"}:
        return jsonify({"code": 400, "message": "无效的排序字段，支持: cost, tokens, requests"})
    
    if limit > 200:
        limit = 200
    
    try:
        ranking = AIUsageTracker.get_user_ranking(time_range, model_key, order_by, limit)
        return jsonify({
            "code": 200,
            "data": ranking
        })
    except Exception as e:
        return jsonify({"code": 500, "message": f"查询失败: {str(e)}"})


# ========== 数据分析接口 ==========

def check_analysis_quota(user_id: str, analysis_type: str) -> tuple:
    """
    检查用户分析配额
    
    Args:
        user_id: 用户ID
        analysis_type: 分析类型 (personal/company)
    
    Returns:
        (has_enough, current_quota): 是否有足够的配额，当前配额值
    """
    quota_cost = 1 if analysis_type == "personal" else 2
    
    conn = connect()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT ai_quota FROM user WHERE uuid = %s", (user_id,))
            result = cursor.fetchone()
            
            if not result:
                return False, 0
            
            current_quota = result["ai_quota"]
            has_enough = current_quota >= quota_cost
            
            return has_enough, current_quota
    finally:
        conn.close()


def deduct_analysis_quota(user_id: str, analysis_type: str) -> bool:
    """
    扣除用户分析配额
    
    Args:
        user_id: 用户ID
        analysis_type: 分析类型 (personal/company)
    
    Returns:
        bool: 是否扣除成功
    """
    quota_cost = 1 if analysis_type == "personal" else 2
    
    conn = connect()
    try:
        with conn.cursor() as cursor:
            sql = "UPDATE user SET ai_quota = ai_quota - %s WHERE uuid = %s AND ai_quota >= %s"
            cursor.execute(sql, (quota_cost, user_id, quota_cost))
            conn.commit()
            return cursor.rowcount > 0
    finally:
        conn.close()


# ========== 数据分析接口（新版拆分） ==========
@ai_page.route("/analyze/new/", methods=["POST"])
@login_required
def new_analysis():
    """创建新的数据分析会话（仅创建会话，返回会话ID）"""
    user_id = g.current_user["uuid"]
    model = "doubao"  # 数据分析模型固定为豆包
    data = request.get_json() or {}
    analysis_type = data.get("analysis_type", "personal")  # personal or company
    title = data.get("title", "新分析")
    
    # 验证参数
    if analysis_type not in {"personal", "company"}:
        return jsonify({"code": 400, "message": "不支持的分析类型，支持: personal, company"})
    
    # 创建对话（使用 analysis_type）
    conversation = create_conversation(user_id, model, title, analysis_type)
    
    return jsonify({
        "code": 200,
        "message": "分析会话已创建",
        "data": {
            "conversation_id": conversation.get("id"),
            "user_id": user_id,
            "model": model,
            "analysis_type": analysis_type,
            "title": title,
            "created_at": conversation.get("created_at")
        }
    })


@ai_page.route("/analyze/<conversation_id>/continue/", methods=["POST"])
@login_required
def continue_analysis(conversation_id):
    """继续数据分析对话（支持追问和上传新文件）"""
    user_id = g.current_user["uuid"]
    data = request.get_json() or {}
    prompt = data.get("prompt", "")
    think = data.get("think", False)
    
    if not prompt:
        return jsonify({"code": 400, "message": "提示词不能为空"})
    
    # 获取对话
    conversation = get_conversation(conversation_id, user_id)
    if not conversation:
        return jsonify({"code": 404, "message": "对话不存在"})
    
    analysis_type = conversation.get("analysis_type")
    if not analysis_type:
        return jsonify({"code": 400, "message": "这不是一个分析对话"})
    
    # 检查用户配额
    has_enough, current_quota = check_analysis_quota(user_id, analysis_type)
    quota_cost = 1 if analysis_type == "personal" else 2
    
    if not has_enough:
        return jsonify({
            "code": 402,
            "message": "配额不足",
            "data": {
                "required": quota_cost,
                "current": current_quota
            }
        })
    
    model = conversation["model"]
    messages = conversation["messages"]
    conversation_files = conversation["files"]
    
    try:
        # 仅支持公网URL
        file_urls = data.get("file_urls") or []
        file_names = data.get("file_names") or []
        
        # 确保是列表
        if isinstance(file_urls, str):
            file_urls = [file_urls]
        if isinstance(file_names, str):
            file_names = [file_names]
        
        # 验证并准备新文件
        new_file_objects = validate_and_prepare_files(file_urls, file_names, conversation_id)
        
        # 转换为数据库格式，保留原始文件名和文件大小便于审计
        new_db_files = []
        for obj in new_file_objects:
            if obj["type"] == "local_file":
                new_db_files.append({
                    "path": obj["path"],
                    "original_name": obj["original_name"],
                    "size": obj.get("size", -1)
                })
            elif obj["type"] == "image_url":
                new_db_files.append({
                    "url": obj["url"],
                    "type": "image_url",
                    "original_name": obj.get("original_name"),
                    "size": obj.get("size", -1)
                })
            elif obj["type"] == "file_url":
                new_db_files.append({
                    "url": obj["url"],
                    "type": "file_url",
                    "original_name": obj.get("original_name"),
                    "size": obj.get("size", -1)
                })
        
        # 扩展会话文件列表
        if new_db_files:
            conversation_files.extend(new_db_files)
        
        def generate():
            try:
                # 先扣除配额
                if not deduct_analysis_quota(user_id, analysis_type):
                    yield f"event: error\ndata: {json.dumps({'status': 'error', 'message': '配额扣除失败'})}\n\n"
                    return
                
                # 获取分析提示词
                system_prompt = get_analysis_prompt(analysis_type)
                
                # 构建用户消息 - 如果有文件，需要构建多模态内容格式
                if new_file_objects:
                    # 多模态内容：包含文件URL和文本提示
                    content = []
                    
                    # 添加文件内容 - 支持图片和文档URL
                    for file_obj in new_file_objects:
                        if file_obj.get("type") == "image_url":
                            content.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": file_obj.get("url")
                                }
                            })
                        elif file_obj.get("type") == "file_url":
                            content.append({
                                "type": "file_url",
                                "file_url": {
                                    "url": file_obj.get("url")
                                }
                            })
                    
                    # 添加文本提示
                    content.append({
                        "type": "text",
                        "text": prompt
                    })
                    
                    user_message = {"role": "user", "content": content, "files": new_db_files}
                else:
                    # 仅文本内容
                    user_message = {"role": "user", "content": prompt}
                
                messages.append(user_message)
                
                # 调用豆包模型
                chat_func = doubao_chat
                
                # 构建消息，在开始时添加系统提示词
                # 对于 personal 分析，添加强制约束以确保第一个回复遵守指令
                if analysis_type == "personal":
                    # 如果是第一条消息（messages 中只有一条用户消息），添加强制约束
                    if len(messages) == 1:
                        system_prompt += "\n\n【强制约束】你的回复必须立即按照上述指令执行分析步骤，不允许询问澄清或延迟执行。"
                
                messages_with_system = [{"role": "system", "content": system_prompt}] + messages
                
                # 流式输出响应
                yield f"event: start\ndata: {json.dumps({'conversation_id': conversation_id, 'status': 'started'})}\n\n"
                
                response_text = ""
                start_time = time.time()
                first_token_sent = False
                print(f"\n[继续分析] 会话ID: {conversation_id}, 类型: {analysis_type}")
                
                # 不通过 files 参数，因为文件已在 messages 中
                for chunk in chat_func(messages=messages_with_system, user_id=user_id, think=think, conversation_id=conversation_id):
                    chunk_str = chunk if isinstance(chunk, str) else json.dumps(chunk, ensure_ascii=False)
                    response_text += chunk_str
                    if not first_token_sent:
                        first_token_sent = True
                        elapsed_ms = int((time.time() - start_time) * 1000)
                        yield f"event: progress\ndata: {json.dumps({'stage': 'first_token', 'elapsed_ms': elapsed_ms})}\n\n"
                    print(chunk_str, end='', flush=True)  # 实时打印AI输出
                    yield f"event: message\ndata: {json.dumps({'message': chunk_str})}\n\n"
                print(f"\n[分析完成] 总字数: {len(response_text)}")
                
                # 保存助手响应到数据库
                messages.append({"role": "assistant", "content": response_text})
                update_conversation(conversation_id, messages, conversation_files)
                
                yield f"event: end\ndata: {json.dumps({'status': 'completed', 'quota_cost': quota_cost})}\n\n"
            
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


@ai_page.route("/analyze/list/", methods=["GET"])
@login_required
def list_user_analyses():
    """列出用户的所有分析对话"""
    user_id = g.current_user["uuid"]
    analysis_type = request.args.get("analysis_type")  # 可选：按分析类型筛选 (personal/company)
    model = request.args.get("model")  # 可选：按模型筛选
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    
    conn = connect()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 构建查询条件
            where_clauses = ["user_id = %s", "analysis_type IS NOT NULL"]
            params = [user_id]
            
            if analysis_type:
                where_clauses.append("analysis_type = %s")
                params.append(analysis_type)
            
            if model:
                where_clauses.append("model = %s")
                params.append(model)
            
            where_sql = " WHERE " + " AND ".join(where_clauses)
            
            # 查询总数
            count_sql = f"SELECT COUNT(*) as total FROM conversations{where_sql}"
            cursor.execute(count_sql, params)
            total = cursor.fetchone()["total"]
            
            # 查询数据
            sql = f"""
                SELECT id, model, title, analysis_type, created_at, updated_at
                FROM conversations{where_sql}
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])
            cursor.execute(sql, params)
            results = cursor.fetchall()
        
        return jsonify({
            "code": 200,
            "data": results,
            "total": total
        })
    finally:
        conn.close()


@ai_page.route("/analyze/get/<conversation_id>/", methods=["GET"])
@login_required
def get_analysis_detail(conversation_id):
    """获取分析对话详情"""
    user_id = g.current_user["uuid"]
    
    conversation = get_conversation(conversation_id, user_id)
    if not conversation:
        return jsonify({"code": 404, "message": "对话不存在"})
    
    if not conversation.get("analysis_type"):
        return jsonify({"code": 400, "message": "这不是一个分析对话"})
    
    return jsonify({
        "code": 200,
        "data": conversation
    })


@ai_page.route("/analyze/delete/<conversation_id>/", methods=["DELETE"])
@login_required
def delete_analysis(conversation_id):
    """删除分析对话"""
    user_id = g.current_user["uuid"]
    
    # 获取对话以验证类型和获取文件列表
    conversation = get_conversation(conversation_id, user_id)
    if not conversation:
        return jsonify({"code": 404, "message": "对话不存在"})
    
    if not conversation.get("analysis_type"):
        return jsonify({"code": 400, "message": "这不是一个分析对话"})
    
    # 删除关联的文件
    base_dir = os.path.expanduser(PRODUCT_IMAGE_DIR)
    upload_dir = os.path.join(base_dir, "chat-uploads", conversation_id)
    if os.path.isdir(upload_dir):
        try:
            shutil.rmtree(upload_dir)
        except Exception:
            pass
    
    # 删除对话
    if not delete_conversation(conversation_id, user_id):
        return jsonify({"code": 500, "message": "删除失败"})
    
    return jsonify({
        "code": 200,
        "message": "分析对话已删除"
    })


@ai_page.route("/analyze/quota/", methods=["GET"])
@login_required
def get_analysis_quota():
    """获取用户的分析配额信息"""
    user_id = g.current_user["uuid"]
    
    conn = connect()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT ai_quota FROM user WHERE uuid = %s", (user_id,))
            result = cursor.fetchone()
            
            if not result:
                return jsonify({"code": 404, "message": "用户不存在"})
            
            ai_quota = result["ai_quota"]
            
            return jsonify({
                "code": 200,
                "data": {
                    "current_quota": ai_quota,
                    "personal_cost": 1,
                    "company_cost": 2,
                    "can_do_personal": ai_quota >= 1,
                    "can_do_company": ai_quota >= 2
                }
            })
    finally:
        conn.close()