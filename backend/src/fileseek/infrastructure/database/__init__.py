"""数据库模块，统一管理 SQLite 连接和 schema。"""

from fileseek.infrastructure.database.connection import close_db, init_db

__all__ = [
    "close_db",
    "init_db",
]
