"""Tortoise ORM 数据模型。

模型只描述数据库结构，不承载领域规则。
领域实体与模型之间的转换由各仓储完成。
"""

from tortoise import fields
from tortoise.models import Model


class FolderModel(Model):
    """文件夹数据库模型。"""

    # 文件夹唯一标识
    id = fields.CharField(
        max_length=255,
        pk=True,
    )

    # 文件夹名称
    name = fields.CharField(
        max_length=255,
    )

    # 文件夹图标类型
    icon_type = fields.CharField(
        max_length=255,
    )

    # 文件夹描述
    description = fields.TextField()

    # 最近修改时间
    modified = fields.DatetimeField()

    # 当前文件数量，属于缓存/派生数据
    file_count = fields.IntField(
        default=0,
    )

    class Meta:
        table = "folders"


class TagModel(Model):
    """文件标签。"""

    id = fields.CharField(
        max_length=64,
        pk=True,
    )

    name = fields.CharField(
        max_length=64,
        unique=True,
    )

    created_at = fields.DatetimeField(
        auto_now_add=True,
    )

    class Meta:
        table = "tags"
        indexes = (("name",),)


class StorageLocationModel(Model):
    """Indexed file source location database model."""

    id = fields.CharField(
        max_length=64,
        pk=True,
    )

    type = fields.CharField(
        max_length=32,
    )

    name = fields.CharField(
        max_length=255,
    )

    protocol = fields.CharField(
        max_length=32,
    )

    endpoint = fields.CharField(
        max_length=2048,
    )

    root_path = fields.CharField(
        max_length=4096,
        default="",
    )

    account = fields.CharField(
        max_length=255,
        null=True,
    )

    password = fields.CharField(
        max_length=4096,
        null=True,
    )

    status = fields.CharField(
        max_length=32,
        default="active",
    )

    is_system = fields.BooleanField(
        default=False,
    )

    created_at = fields.DatetimeField(
        auto_now_add=True,
    )

    updated_at = fields.DatetimeField(
        auto_now=True,
    )

    class Meta:
        table = "storage_locations"
        indexes = (
            ("type",),
            ("status",),
        )


class ClassifierLabelModel(Model):
    """Model classifier vocabulary database model."""

    id = fields.CharField(
        max_length=64,
        pk=True,
    )

    category = fields.CharField(
        max_length=32,
    )

    label = fields.CharField(
        max_length=255,
    )

    enabled = fields.BooleanField(
        default=True,
    )

    created_at = fields.DatetimeField(
        auto_now_add=True,
    )

    updated_at = fields.DatetimeField(
        auto_now=True,
    )

    class Meta:
        table = "classifier_labels"
        unique_together = (("category", "label"),)


class AgentSettingsModel(Model):
    """Retrieval agent settings database model."""

    id = fields.CharField(
        max_length=32,
        pk=True,
    )

    base_url = fields.CharField(
        max_length=2048,
        default="",
    )

    api_key = fields.CharField(
        max_length=4096,
        null=True,
    )

    model = fields.CharField(
        max_length=255,
        default="",
    )

    created_at = fields.DatetimeField(
        auto_now_add=True,
    )

    updated_at = fields.DatetimeField(
        auto_now=True,
    )

    class Meta:
        table = "agent_settings"


class FileChunkModel(Model):
    # 文件唯一标识
    id = fields.CharField(
        max_length=128,
        pk=True,
    )

    file = fields.ForeignKeyField(
        "models.FileModel",
        related_name="filechunks",
        on_delete=fields.CASCADE,
    )

    # 文件块相关的扩展元信息
    metadata = fields.JSONField(
        default=dict,
    )


class FolderSourceBindingModel(Model):
    """Folder-to-storage source directory binding database model."""

    id = fields.CharField(
        max_length=64,
        pk=True,
    )

    folder = fields.ForeignKeyField(
        "models.FolderModel",
        related_name="source_bindings",
        on_delete=fields.CASCADE,
    )

    storage_id = fields.CharField(
        max_length=64,
    )

    source_path = fields.CharField(
        max_length=4096,
    )

    recursive = fields.BooleanField(
        default=True,
    )

    enabled = fields.BooleanField(
        default=True,
    )

    watch_status = fields.CharField(
        max_length=32,
        default="disabled",
    )

    last_error = fields.TextField(
        null=True,
    )

    last_error_at = fields.DatetimeField(
        null=True,
    )

    created_at = fields.DatetimeField(
        auto_now_add=True,
    )

    updated_at = fields.DatetimeField(
        auto_now=True,
    )

    class Meta:
        table = "folder_source_bindings"
        unique_together = (("folder", "storage_id", "source_path"),)
        indexes = (
            ("storage_id",),
            ("enabled",),
            ("watch_status",),
        )


class FolderSourceSeenModel(Model):
    """Per-binding seen file state used for baseline and restart scans."""

    id = fields.CharField(
        max_length=128,
        pk=True,
    )

    binding = fields.ForeignKeyField(
        "models.FolderSourceBindingModel",
        related_name="seen_files",
        on_delete=fields.CASCADE,
    )

    source_path = fields.CharField(
        max_length=4096,
    )

    outcome = fields.CharField(
        max_length=32,
        default="seen",
    )

    last_seen_at = fields.DatetimeField(
        auto_now=True,
    )

    class Meta:
        table = "folder_source_seen_files"
        unique_together = (("binding", "source_path"),)
        indexes = (("outcome",),)


class FileModel(Model):
    """文件数据库模型。"""

    # 文件唯一标识
    id = fields.CharField(
        max_length=64,
        pk=True,
    )

    # 文件名称，不包含父目录路径
    name = fields.CharField(
        max_length=255,
    )

    # 文件扩展名，例如 pdf、jpg、mp4
    file_type = fields.CharField(
        max_length=32,
    )

    # 文件种类，例如 image、video、document
    category = fields.CharField(
        max_length=32,
    )

    # 文件大小，单位：字节
    size = fields.BigIntField()

    # 文件最后修改时间
    modified = fields.DatetimeField()

    # 数据库记录创建时间
    created_at = fields.DatetimeField(
        auto_now_add=True,
    )

    # 当前所属父文件夹
    folder = fields.ForeignKeyField(
        "models.FolderModel",
        related_name="files",
        null=True,
        on_delete=fields.SET_NULL,
    )

    # 文件当前实际路径
    path = fields.CharField(
        max_length=4096,
        unique=True,
    )

    storage_id = fields.CharField(
        max_length=64,
        null=True,
    )

    access_state = fields.CharField(
        max_length=32,
        null=True,
    )

    last_checked_at = fields.DatetimeField(
        null=True,
    )

    # 文件标签
    tags = fields.ManyToManyField(
        "models.TagModel",
        related_name="files",
        through="file_tags",
    )

    class Meta:
        table = "files"

        indexes = (
            ("folder_id",),
            ("category",),
            ("file_type",),
            ("created_at",),
            ("modified",),
            ("size",),
        )


class RecycleItemModel(Model):
    """回收站项目数据库模型。"""

    # 回收站项目唯一标识
    id = fields.CharField(
        max_length=64,
        pk=True,
    )

    # 对应的文件
    file = fields.OneToOneField(
        "models.FileModel",
        related_name="recycle_item",
        on_delete=fields.RESTRICT,
    )

    # 文件进入回收站时的实际存储路径
    recycle_path = fields.CharField(
        max_length=4096,
        null=True,
    )

    # 文件进入回收站的时间
    deleted_at = fields.DatetimeField(
        auto_now_add=True,
    )

    class Meta:
        table = "recycle_bin"

        indexes = (("deleted_at",),)


class TaskModel(Model):
    """后台任务数据库模型。"""

    # 任务唯一标识
    id = fields.CharField(
        max_length=255,
        pk=True,
    )

    # 任务关联的文件
    file = fields.ForeignKeyField(
        "models.FileModel",
        related_name="tasks",
        on_delete=fields.CASCADE,
        null=True,
    )

    # 任务相关的扩展元信息
    metadata = fields.JSONField(
        default=dict,
    )

    # 任务当前状态
    status = fields.CharField(
        max_length=32,
    )

    # 任务当前阶段的完成数量；任务进度以该列与 total_count 为准
    completed_count = fields.IntField(
        null=True,
    )

    # 任务当前阶段的总数量
    total_count = fields.IntField(
        null=True,
    )

    # 任务当前执行阶段
    stage = fields.CharField(
        max_length=32,
        null=True,
    )

    # 任务失败时的错误信息
    error_message = fields.TextField(
        null=True,
    )

    # 任务创建时间
    created_at = fields.DatetimeField(
        auto_now_add=True,
    )

    # 任务最后更新时间
    updated_at = fields.DatetimeField(
        auto_now=True,
    )

    # 已重试次数
    retry_count = fields.IntField(
        default=0,
    )

    class Meta:
        table = "tasks"
        indexes = (
            ("status", "created_at"),
            ("file_id",),
        )


class RecentAccessModel(Model):
    """文件最近访问记录数据库模型。"""

    # 访问记录唯一标识
    id = fields.IntField(
        pk=True,
    )

    # 被访问的文件 ID
    file_id = fields.CharField(
        max_length=255,
    )

    # 文件访问时间
    accessed_at = fields.DatetimeField()

    class Meta:
        table = "recent_access"
        indexes = (
            ("accessed_at",),
            ("file_id", "accessed_at"),
        )


__all__ = [
    "ClassifierLabelModel",
    "FileModel",
    "FolderModel",
    "RecentAccessModel",
    "RecycleItemModel",
    "StorageLocationModel",
    "TaskModel",
]
