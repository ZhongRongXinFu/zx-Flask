import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
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
from utils.login import login_required
from settings import PRODUCT_IMAGE_DIR

chat_page = Blueprint('chat', __name__)


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


@chat_page.route("/chat/new/", methods=["POST"])
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
        "code": 200,
        "data": {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "model": model,
            "title": title
        }
    })


@chat_page.route("/chat/continue/<conversation_id>/", methods=["POST"])
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


@chat_page.route("/list/", methods=["GET"])
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


@chat_page.route("/get/<conversation_id>/", methods=["GET"])
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


@chat_page.route("/delete/<conversation_id>/", methods=["DELETE"])
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
