import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from settings import AI_DEEPSEEK_API_KEY

import os
import base64
from openai import OpenAI

client = OpenAI(
    api_key=AI_DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)


def encode_image(image_path: str) -> str:
    """将图片文件编码为 base64 字符串"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def chat(messages=None, prompt=None, think="disabled", files=None):
    """
    DeepSeek 对话函数，支持对话历史和文件上传
    
    Args:
        messages: 对话历史数组 [{"role": "user/assistant", "content": "..."}]
        prompt: 当前用户输入（如果 messages 为空则使用此参数）
        think: 思维链模式 "enabled"/"disabled"
        files: 文件路径列表（目前 DeepSeek 支持图片）
    
    Yields:
        str: 流式输出的文本片段
    """
    # 初始化消息列表
    if messages is None:
        messages = []
    else:
        # 深拷贝消息列表，避免修改原列表
        messages = [dict(m) for m in messages]
    
    # 如果提供了新的 prompt，添加到消息列表
    if prompt:
        # 构建用户消息内容
        if files:
            # 多模态内容
            content = []
            for file_path in files:
                file_path = os.path.expanduser(file_path)
                if not os.path.exists(file_path):
                    continue
                
                # DeepSeek 支持图片
                ext = os.path.splitext(file_path)[1].lower()
                if ext in {'.jpg', '.jpeg', '.png', '.gif', '.webp'}:
                    try:
                        base64_image = encode_image(file_path)
                        content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        })
                    except Exception:
                        pass
            
            # 添加文本提示
            if content:
                content.append({
                    "type": "text",
                    "text": prompt
                })
                messages.append({"role": "user", "content": content})
            else:
                # 没有有效的文件，只添加文本
                messages.append({"role": "user", "content": prompt})
        else:
            # 仅文本内容
            messages.append({"role": "user", "content": prompt})
    
    # 调用 API
    stream = client.chat.completions.create(
        model="deepseek-chat",
        extra_body={"thinking": {"type": think}},
        messages=messages,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


if __name__ == "__main__":
    # 测试单轮对话
    for content in chat(prompt="写一段关于 Python 的小介绍。"):
        print(content, end="")
    print("\n\nDeepSeek Chat Completed.")