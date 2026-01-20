import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from settings import AI_HUOSHAN_API_KEY

import os, shutil, base64, mimetypes
import time
import json
from typing import Optional
from openai import OpenAI
from utils.ai.pdfmaker import submit_convert, query_task, OFFICE_EXTS
from utils.ai.usage_tracker import AIUsageTracker

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


def chat(messages=None, prompt=None, think="disabled", files=None, user_id: Optional[str] = None, conversation_id: Optional[str] = None):
    """
    Doubao 对话函数，支持对话历史和多文件上传
    
    Args:
        messages: 对话历史数组 [{"role": "user/assistant", "content": "..."}]
                 注意：doubao 的 responses API 使用 input 而非 messages
        prompt: 当前用户输入（如果 messages 为空则使用此参数）
        think: 思维链模式 "enabled"/"disabled"
        files: 文件路径列表（支持图片和文档）
        user_id: 用户ID（用于记录统计）
        conversation_id: 会话ID（用于记录统计）
    
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
        model="doubao-seed-1-8-251228",
        input=input_array,
        extra_body={"thinking": {"type": think}},
        stream=True,
    )

    # 流式输出
    for event in response:
        etype = getattr(event, "type", None)

        # 检查是否有 usage 信息（在 response.completed 事件中）
        if etype == "response.completed":
            # usage 信息在 event.response.usage 中
            response_obj = getattr(event, "response", None)
            usage = getattr(response_obj, "usage", None) if response_obj else None
            
            if usage:
                # 提取 token 数量
                input_tokens = getattr(usage, "input_tokens", 0)
                output_tokens = getattr(usage, "output_tokens", 0)
                total_tokens = getattr(usage, "total_tokens", input_tokens + output_tokens)
                
                # 提取缓存信息（如果有）
                cache_read_input_tokens = getattr(usage, "cache_read_input_tokens", 0)
                
                # 计算非缓存输入
                non_cache_input_tokens = input_tokens - cache_read_input_tokens
                
                # 豆包分段计费：输入<=32k，输出<=200
                # 价格：
                # - 推理输入: 0.8元/百万tokens
                # - 推理输出: 2.0元/百万tokens
                # - 缓存命中: 0.16元/百万tokens
                
                # 分段阈值（tokens）
                INPUT_THRESHOLD = 32 * 1024  # 32k
                OUTPUT_THRESHOLD = 200
                
                # 输入分段计算
                if non_cache_input_tokens <= INPUT_THRESHOLD:
                    input_tier1 = non_cache_input_tokens
                    input_tier2 = 0
                else:
                    input_tier1 = INPUT_THRESHOLD
                    input_tier2 = non_cache_input_tokens - INPUT_THRESHOLD
                
                # 输出分段计算
                if output_tokens <= OUTPUT_THRESHOLD:
                    output_tier1 = output_tokens
                    output_tier2 = 0
                else:
                    output_tier1 = OUTPUT_THRESHOLD
                    output_tier2 = output_tokens - OUTPUT_THRESHOLD
                
                # 价格计算（单位：元）
                cache_price = (cache_read_input_tokens / 1_000_000) * 0.16
                input_tier1_price = (input_tier1 / 1_000_000) * 0.8
                input_tier2_price = (input_tier2 / 1_000_000) * 0.8  # 超出部分仍用同一价格
                output_tier1_price = (output_tier1 / 1_000_000) * 2.0
                output_tier2_price = (output_tier2 / 1_000_000) * 2.0  # 超出部分仍用同一价格
                
                total_input_price = cache_price + input_tier1_price + input_tier2_price
                total_output_price = output_tier1_price + output_tier2_price
                total_price = total_input_price + total_output_price
                
                # 打印详细信息
                print("\n" + "="*60)
                print("[Doubao Token Usage & Pricing]")
                print("-" * 60)
                print(f"输入 Token:")
                if cache_read_input_tokens > 0:
                    print(f"  - 缓存命中: {cache_read_input_tokens:,} tokens × ¥0.16/M = ¥{cache_price:.6f}")
                if non_cache_input_tokens > 0:
                    if input_tier2 > 0:
                        print(f"  - 推理输入 (≤32k): {input_tier1:,} tokens × ¥0.8/M = ¥{input_tier1_price:.6f}")
                        print(f"  - 推理输入 (>32k): {input_tier2:,} tokens × ¥0.8/M = ¥{input_tier2_price:.6f}")
                    else:
                        print(f"  - 推理输入: {input_tier1:,} tokens × ¥0.8/M = ¥{input_tier1_price:.6f}")
                print(f"  - 小计: {input_tokens:,} tokens")
                print(f"输出 Token:")
                if output_tier2 > 0:
                    print(f"  - 推理输出 (≤200): {output_tier1:,} tokens × ¥2.0/M = ¥{output_tier1_price:.6f}")
                    print(f"  - 推理输出 (>200): {output_tier2:,} tokens × ¥2.0/M = ¥{output_tier2_price:.6f}")
                else:
                    print(f"  - 推理输出: {output_tier1:,} tokens × ¥2.0/M = ¥{output_tier1_price:.6f}")
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
                            model_key="doubao-seed-1-8-251228",
                            provider="doubao",
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=total_tokens,
                            input_cost=total_input_price - cache_price,  # 非缓存输入费用
                            output_cost=total_output_price,
                            total_cost=total_price,
                            cache_hit_tokens=cache_read_input_tokens,
                            cache_miss_tokens=non_cache_input_tokens,
                            cache_hit_cost=cache_price
                        )
                    except Exception as e:
                        print(f"记录Doubao使用统计失败: {e}")

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