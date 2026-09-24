"""Tortoise ORM 数据模型。

模型只描述数据库结构，不承载领域规则。领域实体与模型之间的转换由各仓储完成。
"""

from tortoise import fields
from tortoise.models import Model



class FolderModel(Model):
    id = fields.CharField(max_length=255, pk=True)
    name = fields.CharField(max_length=255)
    icon_type = fields.CharField(max_length=255)
    description = fields.TextField()
    modified = fields.CharField(max_length=64)
    file_count = fields.IntField(default=0)

    class Meta:
        table = "folders"


class FileModel(Model):
    id = fields.CharField(
        max_length=64,
        pk=True,
    )

    name = fields.CharField(
        max_length=255,
    )

    file_type = fields.CharField(
        max_length=32,
    )

    size = fields.BigIntField()

    modified = fields.DatetimeField()

    created_at = fields.DatetimeField(
        auto_now_add=True,
    )

    parent_folder = fields.ForeignKeyField(
        "models.FolderModel",
        related_name="files",
        null=True,
        on_delete=fields.SET_NULL,
    )

    path = fields.CharField(
        max_length=4096,
        unique=True,
    )

    class Meta:
        table = "files"
        indexes = (
            ("parent_folder", "file_type"),
        )


class RecycleItemModel(Model):
    id = fields.CharField(max_length=255, pk=True)
    original_file_id = fields.CharField(max_length=255)
    original_name = fields.CharField(max_length=255)
    original_parent_folder = fields.CharField(max_length=255, null=True)
    original_path = fields.CharField(max_length=4096)
    # 压缩包在哪。和 original_path 分开存：前者是还原目标（文件原来在哪），后者是包的位置。
    recycle_path = fields.CharField(max_length=4096, null=True)
    deleted_at = fields.CharField(max_length=64)
    file_type = fields.CharField(max_length=32)
    size = fields.BigIntField()

    class Meta:
        table = "recycle_bin"


class TaskModel(Model):
    id = fields.CharField(max_length=255, pk=True)
    source_path = fields.CharField(max_length=4096)
    status = fields.CharField(max_length=32)
    progress = fields.IntField(default=0)
    stage = fields.CharField(max_length=32, null=True)
    error_message = fields.TextField(null=True)
    created_at = fields.CharField(max_length=64)
    updated_at = fields.CharField(max_length=64)
    retry_count = fields.IntField(default=0)

    class Meta:
        table = "tasks"
        indexes = ("status", "created_at")


class RecentAccessModel(Model):
    id = fields.IntField(pk=True)
    file_id = fields.CharField(max_length=255)
    accessed_at = fields.CharField(max_length=64)

    class Meta:
        table = "recent_access"
        indexes = ("accessed_at",)


class SettingsModel(Model):
    id = fields.CharField(max_length=64, pk=True)
    lib_root = fields.CharField(max_length=4096)
    nas_enabled = fields.BooleanField(default=False)
    nas_protocol = fields.CharField(max_length=32, null=True)
    nas_host = fields.CharField(max_length=255, null=True)
    nas_share_path = fields.CharField(max_length=4096, null=True)
    nas_username = fields.CharField(max_length=255, null=True)
    nas_password = fields.CharField(max_length=255, null=True)

    class Meta:
        table = "settings"



__all__ = [
    "FileModel",
    "FolderModel",
    "RecentAccessModel",
    "RecycleItemModel",
    "TaskModel",
    "SettingsModel",
]
