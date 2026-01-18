import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from settings import AI_HUOSHAN_API_KEY

import os, shutil, base64, mimetypes
import time
import json
from openai import OpenAI

# 使用环境变量 ARK_API_KEY
ARK_API_KEY = os.environ.get("ARK_API_KEY")
if not ARK_API_KEY:
    ARK_API_KEY = AI_HUOSHAN_API_KEY

# bots 端用于 chat.completions
chat_client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3/bots",
    api_key=ARK_API_KEY,
)

# 通用端用于文件上传/检索
file_client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=ARK_API_KEY,
)

def image_to_base64(path: str) -> str:
    """
    把绝对路径的图片转换成 data:image/...;base64,xxxx 字符串
    支持 jpg/png/gif/webp 等所有常见格式
    """

    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")

    # 自动识别 MIME 类型，例如 image/png、image/jpeg
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type is None:
        # 默认给个 image/png
        mime_type = "image/png"

    # 读取文件 → base64 编码
    with open(path, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode("utf-8")

    # 拼接成 data:image/...;base64,xxxx
    return f"data:{mime_type};base64,{b64}"

def is_image(file_path: str) -> bool:
    ext = os.path.splitext(file_path)[1].lower()  # 取后缀并转小写
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
    return ext in image_exts


def is_pdf(file_path: str) -> bool:
    """简单检测是否为 PDF 文件"""
    return os.path.splitext(file_path)[1].lower() == ".pdf"


def chat(messages=None, prompt=None, think="disabled", files=None):
    """
    Doubao 对话函数，支持对话历史和多文件上传
    
    Args:
        messages: 对话历史数组 [{"role": "user/assistant", "content": "..."}]
                 注意：doubao 的 responses API 使用 input 而非 messages
        prompt: 当前用户输入（如果 messages 为空则使用此参数）
        think: 思维链模式 "enabled"/"disabled"
        files: 文件路径列表（支持图片和文档）
    
    Yields:
        str: 流式输出的文本片段
    """
    # 构建内容列表
    input_array = []
    
    # 如果有历史消息，先转换为 doubao 格式
    if messages:
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # 如果是字符串内容，转为文本格式
            if isinstance(content, str):
                input_array.append({
                    "role": role,
                    "content": [{"type": "input_text", "text": content}]
                })
            # 如果是数组（多模态内容），保持原样
            elif isinstance(content, list):
                input_array.append({
                    "role": role,
                    "content": content
                })
    
    # 构建当前用户消息的内容（bots API 使用数组格式）
    current_content = []
    
    # 处理文件上传
    if files:
        files = [os.path.expanduser(fp) for fp in files]
        for fp in files:
            if not os.path.isfile(fp):
                continue
            
            if is_image(fp):
                # 图片：上传获取URL
                with open(fp, "rb") as fobj:
                    file = file_client.files.create(
                        file=fobj,
                        purpose="user_data"
                    )
                # 等待处理完成
                while getattr(file, 'status', None) == "processing":
                    time.sleep(2)
                    file = file_client.files.retrieve(file.id)
                
                # 获取文件URL（从file对象中提取）
                file_url = getattr(file, 'url', None) or getattr(file, 'download_url', None)
                if file_url:
                    current_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": file_url
                        }
                    })
            elif is_pdf(fp):
                # PDF：上传获取URL
                with open(fp, "rb") as fobj:
                    file = file_client.files.create(
                        file=fobj,
                        purpose="user_data"
                    )
                # 等待处理完成
                while getattr(file, 'status', None) == "processing":
                    time.sleep(2)
                    file = file_client.files.retrieve(file.id)
                
                # PDF作为文件URL
                file_url = getattr(file, 'url', None) or getattr(file, 'download_url', None)
                if file_url:
                    current_content.append({
                        "type": "file_url",
                        "file_url": {
                            "url": file_url
                        }
                    })
            else:
                # 其他类型：作为文本说明
                file_name = os.path.basename(fp)
                current_content.append({
                    "type": "text",
                    "text": f"[文件: {file_name}, 路径: {fp}]"
                })
    
    # 添加文本提示
    if prompt:
        current_content.append({
            "type": "text",
            "text": prompt
        })
    
    # 如果有当前内容，添加到消息数组（直接作为 content）
    if current_content:
        input_array.append({
            "role": "user",
            "content": current_content
        })
    
    # 如果没有任何输入，使用默认提示
    if not input_array:
        input_array = [{
            "role": "user",
            "content": [{"type": "text", "text": "你好"}]
        }]
    
    # 转换为 chat.completions 的 messages 格式
    chat_messages = []
    for item in input_array:
        role = item.get("role", "user")
        content_parts = item.get("content", [])
        
        # 如果是字符串，转为文本数组
        if isinstance(content_parts, str):
            chat_messages.append({
                "role": role,
                "content": [{"type": "text", "text": content_parts}]
            })
            continue
        
        # 转换旧格式到新格式
        normalized_content = []
        for part in content_parts:
            ptype = part.get("type")
            if ptype in ("input_text", "text"):
                normalized_content.append({
                    "type": "text",
                    "text": part.get("text", "")
                })
            elif ptype == "image_url":
                # 已经是正确格式
                normalized_content.append(part)
            elif ptype == "file_url":
                # 已经是正确格式
                normalized_content.append(part)
            elif ptype == "input_image":
                # 旧格式转新格式
                normalized_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": part.get("image_url", "")
                    }
                })
        
        chat_messages.append({
            "role": role,
            "content": normalized_content
        })

    # 调用 Chat Completions（流式）- 使用 bots 端点
    response = chat_client.chat.completions.create(
        model="bot-20251218153820-m4k68",
        messages=chat_messages,
        stream=True,
        extra_body={"thinking": {"type": think}},
    )

    # 流式输出
    for chunk in response:
        if not chunk.choices:
            continue
        delta = getattr(chunk.choices[0], "delta", None)
        if not delta:
            continue
        content = getattr(delta, "content", None)
        if not content:
            continue
        # content 可能是字符串
        if isinstance(content, str):
            yield content

if __name__ == "__main__":
    # 测试单轮对话
    for chunk in chat(prompt="写一段关于 Python 的小介绍。"):
        print(chunk, end="")
    print("\n\nDoubao Chat Completed.")