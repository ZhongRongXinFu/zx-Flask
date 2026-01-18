import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from settings import AI_HUOSHAN_API_KEY

import os, shutil, base64, mimetypes
import time
import json
from openai import OpenAI
from utils.ai.pdfmaker import submit_convert, query_task, OFFICE_EXTS

client = OpenAI(
    base_url='https://ark.cn-beijing.volces.com/api/v3',
    api_key=AI_HUOSHAN_API_KEY,
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

def is_image(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()  # 取后缀并转小写

    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
    if ext in image_exts:
        return True
    else:
        return False


def convert_office_to_pdf_sync(file_path: str, timeout_sec: int = 300, poll_interval: float = 1.0) -> str:
    """同步阻塞地将 Office 文档转换为 PDF，返回 PDF 绝对路径。"""
    task_id = submit_convert(file_path, timeout_sec=timeout_sec)
    deadline = time.time() + timeout_sec

    while True:
        if time.time() > deadline:
            raise TimeoutError(f"转换超时：{file_path}")

        info = query_task(task_id)
        if not info.get("ok"):
            raise RuntimeError(f"转换任务查询失败：{info.get('error')}")

        status = info.get("status")
        if status == "DONE":
            pdf_path = info.get("pdf")
            if not pdf_path:
                raise RuntimeError(f"转换完成但未返回 pdf 路径：{file_path}")
            return pdf_path
        if status == "FAILED":
            raise RuntimeError(f"转换失败：{info.get('error')}" )

        time.sleep(poll_interval)


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
    
    # 构建当前用户消息的内容
    current_content = []
    
    # 处理文件上传
    if files:
        files = [os.path.expanduser(fp) for fp in files]
        for fp in files:
            if not os.path.isfile(fp):
                continue

            ext = os.path.splitext(fp)[1].lower()
            upload_path = fp

            # 如果是 Office 文档，先转成 PDF 再上传
            if ext in OFFICE_EXTS:
                upload_path = convert_office_to_pdf_sync(fp)

            if is_image(upload_path):
                # 图片转 base64
                current_content.append({
                    "type": "input_image",
                    "image_url": image_to_base64(upload_path)
                })
            else:
                # 其他文件上传到 doubao
                file = client.files.create(
                    file=open(upload_path, "rb"),
                    purpose="user_data"
                )
                # 等待处理完成
                while getattr(file, 'status', None) == "processing":
                    time.sleep(2)
                    file = client.files.retrieve(file.id)
                
                current_content.append({
                    "type": "input_file",
                    "file_id": file.id
                })
    
    # 添加文本提示
    if prompt:
        current_content.append({
            "type": "input_text",
            "text": prompt
        })
    
    # 如果有当前内容，添加到 input 数组
    if current_content:
        input_array.append({
            "role": "user",
            "content": current_content
        })
    
    # 如果没有任何输入，使用默认提示
    if not input_array:
        input_array = [{
            "role": "user",
            "content": [{"type": "input_text", "text": "你好"}]
        }]
    
    # 调用 API
    response = client.responses.create(
        model="doubao-seed-1-6-251015",
        input=input_array,
        extra_body={"thinking": {"type": think}},
        stream=True,
    )

    # 流式输出
    for event in response:
        etype = getattr(event, "type", None)

        # 只关心输出文本增量事件
        if etype == "response.output_text.delta":
            delta = getattr(event, "delta", None)

            # 兼容各种结构：字符串 或 dict 里带 text
            text = None
            if isinstance(delta, str):
                text = delta
            elif isinstance(delta, dict):
                text = delta.get("text") or delta.get("output_text")
            else:
                if delta is not None:
                    text = str(delta)

            if text:
                yield text

if __name__ == "__main__":
    # 测试单轮对话
    for chunk in chat(prompt="写一段关于 Python 的小介绍。"):
        print(chunk, end="")
    print("\n\nDoubao Chat Completed.")