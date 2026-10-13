"""管理文件访问授权。"""

import json
import time
from pathlib import Path
from typing import Optional


class GrantStore:
    """管理文件和文件夹的访问授权。"""

    def __init__(self, grants_path: Path):
        self.path = grants_path
        self.grants = self._load()

    def _load(self) -> dict:
        """从磁盘加载授权信息，清理过期授权。"""
        if not self.path.exists():
            return {"version": 1, "grants": {}}

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))

            # 清理过期的授权
            now = time.time()
            if "grants" in data:
                data["grants"] = {
                    k: v
                    for k, v in data["grants"].items()
                    if v.get("expires_at", 0) > now
                }

            return data
        except (json.JSONDecodeError, KeyError, ValueError):
            # 文件损坏，重新初始化
            return {"version": 1, "grants": {}}

    def _save(self):
        """保存授权信息到磁盘。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.grants, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def grant_file(
        self,
        file_id: str,
        file_name: str,
        duration_minutes: int,
        folder_id: Optional[str] = None,
    ):
        """授予单个文件的访问权限。"""
        key = f"file:{file_id}"
        now = time.time()

        self.grants["grants"][key] = {
            "type": "file",
            "file_id": file_id,
            "file_name": file_name,
            "granted_at": now,
            "expires_at": now + duration_minutes * 60,
            "folder_id": folder_id,
        }

        self._save()

    def grant_folder(
        self,
        folder_id: str,
        folder_name: str,
        file_ids: list[str],
        duration_minutes: int,
    ):
        """授予文件夹下所有文件的访问权限。"""
        key = f"folder:{folder_id}"
        now = time.time()

        self.grants["grants"][key] = {
            "type": "folder",
            "folder_id": folder_id,
            "folder_name": folder_name,
            "granted_at": now,
            "expires_at": now + duration_minutes * 60,
            "file_ids": file_ids,
        }

        self._save()

    def check_permission(self, file_id: str) -> bool:
        """检查是否有权限读取指定文件。

        Args:
            file_id: 文件 ID

        Returns:
            True 表示有权限，False 表示无权限
        """
        now = time.time()

        # 检查单文件授权
        file_key = f"file:{file_id}"
        if file_key in self.grants.get("grants", {}):
            grant = self.grants["grants"][file_key]
            if grant.get("expires_at", 0) > now:
                return True
            else:
                # 过期，删除
                del self.grants["grants"][file_key]
                self._save()

        # 检查文件夹授权
        for key, grant in list(self.grants.get("grants", {}).items()):
            if grant.get("type") == "folder":
                if grant.get("expires_at", 0) > now:
                    # 检查文件是否在这个文件夹里
                    if file_id in grant.get("file_ids", []):
                        return True
                else:
                    # 过期，删除
                    del self.grants["grants"][key]
                    self._save()

        return False

    def revoke(self, resource_id: str):
        """撤销授权（文件或文件夹）。

        Args:
            resource_id: 格式为 "file:xxx" 或 "folder:yyy"
        """
        if resource_id in self.grants.get("grants", {}):
            del self.grants["grants"][resource_id]
            self._save()

    def list_active_grants(self) -> list[dict]:
        """列出所有有效的授权。"""
        now = time.time()
        active = []

        for key, grant in self.grants.get("grants", {}).items():
            if grant.get("expires_at", 0) > now:
                active.append({
                    "key": key,
                    **grant,
                    "remaining_seconds": int(grant.get("expires_at", 0) - now),
                })

        return active

    def clear_expired(self) -> int:
        """清除所有过期的授权。

        Returns:
            清除的授权数量
        """
        now = time.time()
        original_count = len(self.grants.get("grants", {}))

        self.grants["grants"] = {
            k: v
            for k, v in self.grants.get("grants", {}).items()
            if v.get("expires_at", 0) > now
        }

        removed = original_count - len(self.grants["grants"])
        if removed > 0:
            self._save()

        return removed

    def clear_all(self):
        """清除所有授权。"""
        self.grants["grants"] = {}
        self._save()
