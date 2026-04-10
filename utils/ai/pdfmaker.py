import os
import time
import uuid
import requests
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any

from concurrent.futures import ThreadPoolExecutor, Future
from threading import Lock

OFFICE_EXTS = {".doc", ".docx", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx"}

# ---- 线程池配置：按你服务器核数/并发调 ----
MAX_WORKERS = int(os.getenv("PDF_CONVERT_WORKERS", "4"))      # 同时转换的“并发数”
MAX_QUEUE = int(os.getenv("PDF_CONVERT_MAX_QUEUE", "200"))    # 等待队列上限（保护主进程）


@dataclass
class TaskInfo:
    task_id: str
    src: str
    pdf: Optional[str] = None
    status: str = "PENDING"  # PENDING/RUNNING/DONE/FAILED
    error: Optional[str] = None
    created_at: float = 0.0
    updated_at: float = 0.0


_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="pdf-conv")
_tasks: Dict[str, TaskInfo] = {}
_futures: Dict[str, Future] = {}
_lock = Lock()


def _find_soffice() -> str:
    """
    自动查找 LibreOffice 的 soffice 命令（macOS/Ubuntu）
    """
    candidates = [
        "soffice",  # PATH
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",  # macOS
        "/usr/bin/soffice",
        "/usr/lib/libreoffice/program/soffice",
    ]
    for cmd in candidates:
        if cmd == "soffice":
            if shutil.which("soffice"):
                return "soffice"
            continue
        if Path(cmd).exists():
            return cmd
    raise RuntimeError("LibreOffice (soffice) not found. Please install LibreOffice.")


_SOFFICE = None


def _ensure_soffice() -> str:
    global _SOFFICE
    if _SOFFICE is None:
        _SOFFICE = _find_soffice()
    return _SOFFICE


def _convert_one(src_path: Path, timeout_sec: int = 300) -> str:
    """
    真正执行转换的函数（在线程池里跑）
    - 输出到同目录同名 pdf
    - 返回 pdf 绝对路径
    """
    src_path = src_path.expanduser().resolve()

    if not src_path.exists():
        raise FileNotFoundError(f"File not found: {src_path}")

    if src_path.suffix.lower() not in OFFICE_EXTS:
        raise ValueError(f"Unsupported file type: {src_path.suffix}")

    soffice = _ensure_soffice()
    out_dir = src_path.parent
    pdf_path = out_dir / f"{src_path.stem}.pdf"

    # LibreOffice 输出有时会出现同名覆盖，建议先删掉旧的，避免你误判“已存在”
    if pdf_path.exists():
        pdf_path.unlink()

    cmd = [
        soffice,
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--convert-to", "pdf",
        "--outdir", str(out_dir),
        str(src_path),
    ]


    env = os.environ.copy()
    env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    env.setdefault("HOME", "/tmp")

    # NOTE：捕获输出便于排错；timeout 防止卡死占线程
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_sec,
        env=env,
    )

    if p.returncode != 0 or not pdf_path.exists():
        raise RuntimeError(
            f"Conversion failed (code={p.returncode}).\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )

    return str(pdf_path)


def submit_convert(file_path: str, timeout_sec: int = 300) -> str:
    """
    提交一个转换任务：
    - 立即返回 task_id（不阻塞请求线程）
    - 若队列已满，抛 RuntimeError（你在 Flask 里返回 429/503）
    """
    src = str(Path(file_path).expanduser().resolve())

    with _lock:
        # 队列保护：tasks 里未完成的数量限制
        unfinished = sum(1 for t in _tasks.values() if t.status in ("PENDING", "RUNNING"))
        if unfinished >= MAX_QUEUE:
            raise RuntimeError("Converter is busy: queue is full")

        task_id = uuid.uuid4().hex
        now = time.time()
        _tasks[task_id] = TaskInfo(
            task_id=task_id,
            src=src,
            created_at=now,
            updated_at=now,
        )

        def _runner():
            # 标记 RUNNING
            with _lock:
                _tasks[task_id].status = "RUNNING"
                _tasks[task_id].updated_at = time.time()

            try:
                pdf = _convert_one(Path(src), timeout_sec=timeout_sec)
                with _lock:
                    _tasks[task_id].pdf = pdf
                    _tasks[task_id].status = "DONE"
                    _tasks[task_id].updated_at = time.time()
                return pdf
            except Exception as e:
                with _lock:
                    _tasks[task_id].status = "FAILED"
                    _tasks[task_id].error = str(e)
                    _tasks[task_id].updated_at = time.time()
                raise

        fut = _executor.submit(_runner)
        _futures[task_id] = fut

    return task_id


def query_task(task_id: str) -> Dict[str, Any]:
    """
    查询任务状态（用于 Flask 轮询接口）
    """
    with _lock:
        t = _tasks.get(task_id)
        if not t:
            return {"ok": False, "error": "task_not_found"}

        return {
            "ok": True,
            "task_id": t.task_id,
            "src": t.src,
            "pdf": t.pdf,
            "status": t.status,
            "error": t.error,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }


# if __name__ == "__main__":
#     # 测试转换功能
#     test_file = "~/Documents/期末考核.docx"  # 修改为你的测试文件路径
#     try:
#         pdf_file = convert_office_to_pdf(test_file)
#         print(f"Converted PDF: {pdf_file}")
#     except Exception as e:
#         print(f"Error: {e}")


# ---- 火山引擎 LAS PDF 解析器 ----

LAS_SUBMIT_URL = "https://operator.las.cn-beijing.volces.com/api/v1/submit"
LAS_POLL_URL   = "https://operator.las.cn-beijing.volces.com/api/v1/poll"


def parse_pdf_to_markdown(url: str, api_key: str, parse_mode: str = "normal", timeout_sec: int = 300) -> str:
    """
    调用火山引擎 LAS PDF 解析器，将 PDF URL 解析为 Markdown 文本。

    Args:
        url: PDF 文件的公网 URL
        api_key: 火山引擎 API Key（AI_HUOSHAN_API_KEY）
        parse_mode: "normal"（默认）或 "detail"（深度思考，更慢）
        timeout_sec: 轮询总超时秒数

    Returns:
        解析出的 Markdown 字符串

    Raises:
        RuntimeError: API 调用失败或任务执行失败
        TimeoutError: 超过 timeout_sec 仍未完成
    """
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # 1. Submit
    resp = requests.post(LAS_SUBMIT_URL, json={
        "operator_id": "las_pdf_parse_doubao",
        "operator_version": "v1",
        "data": {"url": url, "parse_mode": parse_mode}
    }, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"LAS submit 失败 HTTP {resp.status_code}: {resp.text}")
    task_id = resp.json().get("metadata", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"LAS submit 未返回 task_id: {resp.text}")

    # 2. Poll
    start = time.time()
    while True:
        time.sleep(2)
        if time.time() - start > timeout_sec:
            raise TimeoutError(f"LAS PDF 解析超时（>{timeout_sec}s），task_id={task_id}")
        poll_resp = requests.post(LAS_POLL_URL, json={
            "operator_id": "las_pdf_parse_doubao",
            "operator_version": "v1",
            "task_id": task_id
        }, headers=headers, timeout=15)
        if poll_resp.status_code != 200:
            raise RuntimeError(f"LAS poll 失败 HTTP {poll_resp.status_code}: {poll_resp.text}")
        meta = poll_resp.json().get("metadata", {})
        status = meta.get("task_status")
        if status == "COMPLETED":
            return poll_resp.json().get("data", {}).get("markdown", "")
        if status == "FAILED":
            error_detail = poll_resp.json().get("metadata", {}).get("error_message") or poll_resp.text
            raise RuntimeError(f"LAS PDF 解析任务失败，task_id={task_id}，detail={error_detail}")