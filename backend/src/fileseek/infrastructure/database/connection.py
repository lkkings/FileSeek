"""SQLite 数据库连接管理。

提供数据库连接、初始化和事务管理。
"""

from __future__ import annotations

import logging
from uuid import uuid4

from tortoise import Tortoise

from fileseek.config.settings import get_settings

logger = logging.getLogger(__name__)

# 给已存在的表补列。
#
# `generate_schemas(safe=True)` 只建缺失的**表**，对已存在的表一个字段都不会动，所以给模型
# 加字段之后老库会缺列，一读就报 "no such column"。这里按 (表, 列, 类型) 声明需要补的列，
# 启动时逐个检查。
#
# 只加可空列：已有行没有值可填，加非空列必须给默认值，那等于在这里定业务语义。
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    # 压缩包的位置。加入回收站＝压缩，`original_path` 记文件原来在哪、`recycle_path` 记包在哪。
    ("recycle_bin", "recycle_path", "VARCHAR(4096)"),
    ("files", "storage_id", "VARCHAR(64)"),
    ("files", "access_state", "VARCHAR(32)"),
    ("files", "last_checked_at", "TIMESTAMP"),
    ("tasks", "completed_count", "INT"),
    ("tasks", "total_count", "INT"),
)


async def init_db() -> None:
    """初始化 Tortoise ORM 并创建缺失的表和列。"""
    settings = get_settings()
    await Tortoise.init(
        db_url=f"sqlite://{settings.db_path}",
        modules={"models": ["fileseek.infrastructure.database.models"]},
    )
    await Tortoise.generate_schemas(safe=True)
    await _add_missing_columns()
    await _seed_settings_and_backfill_files(settings)


async def _add_missing_columns() -> None:
    """把 `_ADDED_COLUMNS` 里还不存在的列加上。"""
    connection = Tortoise.get_connection("default")

    for table, column, column_type in _ADDED_COLUMNS:
        # 表可能还不存在（全新库由 generate_schemas 建出来时已经带上了这些列）。
        existing = await connection.execute_query_dict(f"PRAGMA table_info({table})")
        if not existing:
            continue

        if any(row["name"] == column for row in existing):
            continue

        # 表名和列名都来自上面那个常量，不是外部输入。
        await connection.execute_script(
            f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"
        )
        logger.info("已为表 %s 补上列 %s", table, column)


async def _seed_settings_and_backfill_files(settings: Settings) -> None:
    from fileseek.infrastructure.database.models import (
        ClassifierLabelModel,
        FileModel,
        StorageLocationModel,
    )

    await StorageLocationModel.get_or_create(
        id="local",
        defaults={
            "type": "local",
            "name": "本地存储",
            "protocol": "file",
            "endpoint": "file://localhost",
            "root_path": str(settings.lib_root),
            "is_system": True,
        },
    )
    await StorageLocationModel.get_or_create(
        id="external",
        defaults={
            "type": "external",
            "name": "外部链接",
            "protocol": "http",
            "endpoint": "external",
            "is_system": True,
        },
    )

    if await ClassifierLabelModel.all().count() == 0:
        default_labels = (
            ("document", settings.classifier_document_labels),
            ("image", settings.classifier_image_labels),
            ("video", settings.classifier_video_labels),
        )
        await ClassifierLabelModel.bulk_create(
            [
                ClassifierLabelModel(
                    id=uuid4().hex,
                    category=category,
                    label=label,
                )
                for category, labels in default_labels
                for label in labels
            ]
        )

    legacy_files = await FileModel.filter(storage_id__isnull=True).only(
        "id",
        "path",
        "access_state",
    )
    for model in legacy_files:
        model.storage_id = (
            "external"
            if model.path.startswith(("http://", "https://"))
            else "local"
        )
        model.access_state = model.access_state or "unknown"
        await model.save(update_fields=("storage_id", "access_state"))


async def close_db() -> None:
    """关闭 Tortoise 的连接池。"""
    if Tortoise._inited:
        await Tortoise.close_connections()
