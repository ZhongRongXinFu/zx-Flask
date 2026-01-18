import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import datetime

def parse_datetime(value: str):
    """解析多格式日期字符串:
    1. 'YYYY-MM-DD HH:MM:SS'
    2. ISO8601: '2025-12-05T06:00:46.000Z'
    3. 空字符串或None → 返回 None
    """
    if not value or value.strip() == "":
        return None
    
    value = value.strip()

    # 情况 1：标准格式 YYYY-MM-DD HH:MM:SS
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass

    # 情况 2：带 Z 的 ISO8601 格式
    if value.endswith("Z"):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            # 如果你希望输出为无时区的本地时间（例如存数据库），就转成本地时间再去掉 tzinfo
            dt_local = dt.astimezone().replace(tzinfo=None)
            return dt_local
        except ValueError:
            pass

    raise ValueError(f"无法解析日期格式: {value}")