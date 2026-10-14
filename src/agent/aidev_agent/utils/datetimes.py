import time
from datetime import datetime


def get_current_timestamp_in_milliseconds() -> int:
    """Get the current timestamp in milliseconds."""

    return int(time.time() * 1000)


def created_at_to_ms(created_at: str | None) -> int | None:
    """将入库 created_at（带时区的 ISO 8601）转为毫秒；缺失、无法解析或无时区时返回 None。"""
    try:
        dt = datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return None
    # 无时区会按本机时区解释，毫秒值不可信，交由调用方回退墙钟
    if dt.tzinfo is None:
        return None
    return int(dt.timestamp() * 1000)
