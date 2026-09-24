"""唯一标识符生成工具。"""

from __future__ import annotations

import uuid


def generate_id(prefix: str = "") -> str:
    """生成唯一标识符。

    Args:
        prefix: 可选前缀（如 "f", "d", "task"），以下划线与随机部分连接

    Returns:
        唯一标识符字符串
    """
    if prefix:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"
    return uuid.uuid4().hex[:16]
