import os
import time
import uuid
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

    # NOTE：捕获输出便于排错；timeout 防止卡死占线程
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_sec,
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