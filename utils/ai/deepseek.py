import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from settings import AI_DEEPSEEK_API_KEY

import os
import base64
from typing import Optional, List
from openai import OpenAI
from utils.ai.usage_tracker import AIUsageTracker

client = OpenAI(
    api_key=AI_DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)


def encode_image(image_path: str) -> str:
    """将图片文件编码为 base64 字符串"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def _content_to_text_list(parts: List) -> List[str]:
    """把多模态内容转换为纯文本片段，DeepSeek 不支持 image_url/file_url。"""
    texts = []
    for part in parts:
        if isinstance(part, str):
            if part:
                texts.append(part)
            continue
        if not isinstance(part, dict):
            texts.append(str(part))
            continue

        ptype = part.get("type")
        if ptype == "text" and isinstance(part.get("text"), str):
            texts.append(part["text"])
            continue
        if ptype == "image_url":
            url = ""
            if isinstance(part.get("image_url"), dict):
                url = part.get("image_url", {}).get("url", "")
            elif isinstance(part.get("url"), str):
                url = part.get("url")
            texts.append(f"[图片] {url}".strip())
            continue
        if ptype == "file_url":
            url = ""
            if isinstance(part.get("file_url"), dict):
                url = part.get("file_url", {}).get("url", "")
            elif isinstance(part.get("url"), str):
                url = part.get("url")
            texts.append(f"[文件] {url}".strip())
            continue

        # 兜底
        if isinstance(part.get("text"), str):
            texts.append(part.get("text"))
        else:
            texts.append(str(part))
    return texts


def chat(messages=None, prompt=None, think=False, files=None, user_id: Optional[str] = None, conversation_id: Optional[str] = None):
    """
    DeepSeek 对话函数，支持对话历史和文件上传
    
    Args:
        messages: 对话历史数组 [{"role": "user/assistant", "content": "..."}]
        prompt: 当前用户输入（如果 messages 为空则使用此参数）
        think: 思维链模式 "enabled"/"disabled"
        files: 文件路径列表（目前 DeepSeek 支持图片）
        user_id: 用户ID（用于记录统计）
        conversation_id: 会话ID（用于记录统计）
    
    Yields:
        str: 流式输出的文本片段
    """
    if think:
        think = "enabled"
        model = "deepseek-reasoner"
    else:
        think = "disabled"
        model = "deepseek-chat"

    # 初始化消息列表
    if messages is None:
        messages = []
    else:
        # 深拷贝消息列表，避免修改原列表
        messages = [dict(m) for m in messages]

    # 将历史消息中的多模态内容转换为纯文本
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            texts = _content_to_text_list(content)
            msg["content"] = "\n".join(t for t in texts if t)
    
    # 如果提供了新的 prompt，添加到消息列表
    if prompt:
        # 构建用户消息内容（纯文本）
        texts = []
        if files:
            for file_path in files:
                label = "文件"
                url = ""
                if isinstance(file_path, str) and (file_path.startswith('http://') or file_path.startswith('https://')):
                    url = file_path
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}:
                        label = "图片"
                else:
                    file_path = os.path.expanduser(file_path)
                    if not os.path.exists(file_path):
                        continue
                    url = file_path
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}:
                        label = "图片"
                texts.append(f"[{label}] {url}".strip())

        texts.append(prompt)
        messages.append({"role": "user", "content": "\n".join(t for t in texts if t)})
    
    # 调用 API
    stream = client.chat.completions.create(
        model=model,
        extra_body={"thinking": {"type": think}},
        messages=messages,
        stream=True,
        stream_options={"include_usage": True}
    )

    for chunk in stream:
        # 检查是否有 usage 信息（通常在最后一个 chunk）
        if hasattr(chunk, 'usage') and chunk.usage:
            usage = chunk.usage
            
            # 提取 token 数量
            prompt_tokens = getattr(usage, 'prompt_tokens', 0)
            completion_tokens = getattr(usage, 'completion_tokens', 0)
            total_tokens = getattr(usage, 'total_tokens', 0)
            
            # 提取缓存信息（如果有）
            prompt_cache_hit_tokens = getattr(usage, 'prompt_cache_hit_tokens', 0)
            prompt_cache_miss_tokens = getattr(usage, 'prompt_cache_miss_tokens', 0)
            
            # 如果没有缓存信息，则全部计为未命中
            if prompt_cache_hit_tokens == 0 and prompt_cache_miss_tokens == 0:
                prompt_cache_miss_tokens = prompt_tokens
            
            # 计算价格（单位：元）
            # DeepSeek 计费：
            # - 输入（缓存命中）：0.2元/百万tokens
            # - 输入（缓存未命中）：2元/百万tokens
            # - 输出：3元/百万tokens
            cache_hit_price = (prompt_cache_hit_tokens / 1_000_000) * 0.2
            cache_miss_price = (prompt_cache_miss_tokens / 1_000_000) * 2.0
            output_price = (completion_tokens / 1_000_000) * 3.0
            total_price = cache_hit_price + cache_miss_price + output_price
            
            # 打印详细信息
            print("\n" + "="*60)
            print("[DeepSeek Token Usage & Pricing]")
            print("-" * 60)
            print(f"输入 Token:")
            print(f"  - 缓存命中: {prompt_cache_hit_tokens:,} tokens × ¥0.2/M = ¥{cache_hit_price:.6f}")
            print(f"  - 缓存未命中: {prompt_cache_miss_tokens:,} tokens × ¥2.0/M = ¥{cache_miss_price:.6f}")
            print(f"  - 小计: {prompt_tokens:,} tokens")
            print(f"输出 Token:")
            print(f"  - {completion_tokens:,} tokens × ¥3.0/M = ¥{output_price:.6f}")
            print("-" * 60)
            print(f"总计: {total_tokens:,} tokens")
            print(f"总价格: ¥{total_price:.6f} (约 {total_price * 1000:.4f} 厘)")
            print("=" * 60 + "\n")
            
            # 记录到数据库
            if user_id:
                try:
                    AIUsageTracker.log_usage(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        model_key="deepseek-chat",
                        provider="deepseek",
                        input_tokens=prompt_tokens,
                        output_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        input_cost=cache_miss_price,  # 缓存未命中费用
                        output_cost=output_price,
                        total_cost=total_price,
                        cache_hit_tokens=prompt_cache_hit_tokens,
                        cache_miss_tokens=prompt_cache_miss_tokens,
                        cache_hit_cost=cache_hit_price
                    )
                except Exception as e:
                    print(f"记录DeepSeek使用统计失败: {e}")
        
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


if __name__ == "__main__":
    # 测试单轮对话
    for content in chat(prompt="写一段关于 Python 的小介绍。"):
        print(content, end="")
    print("\n\nDeepSeek Chat Completed.")