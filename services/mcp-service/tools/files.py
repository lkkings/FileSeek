"""read_file 工具实现。"""

import base64
from pathlib import Path
from typing import Any, Optional

from api_client import FileSeekAPIClient
from permissions import GrantStore


class PermissionDeniedError(Exception):
    """权限被拒绝错误。"""

    def __init__(self, file_info: dict, folder_info: Optional[dict] = None):
        self.file_info = file_info
        self.folder_info = folder_info
        super().__init__("Permission denied")


async def read_file_tool(
    api_client: FileSeekAPIClient,
    grant_store: GrantStore,
    file_id: str,
    page: Optional[int] = None,
    chunk_start: Optional[int] = None,
    chunk_end: Optional[int] = None,
) -> dict[str, Any]:
    """读取文件内容。

    需要授权。支持文档按页/chunk 读取，图片返回 Base64。

    Args:
        api_client: API 客户端
        grant_store: 授权存储
        file_id: 文件 ID
        page: 可选，文档的页码
        chunk_start: 可选，起始 chunk
        chunk_end: 可选，结束 chunk

    Returns:
        文件内容或错误信息
    """
    try:
        # 1. 检查权限
        if not grant_store.check_permission(file_id):
            # 获取文件信息用于错误提示
            try:
                file_info = api_client.get_file_info(file_id)

                # 尝试获取文件夹信息
                folder_id = file_info.get("folder_id")
                folder_info = None
                if folder_id:
                    folders = api_client.get_folders()
                    folder_info = next(
                        (f for f in folders if f.get("id") == folder_id),
                        None
                    )

                raise PermissionDeniedError(file_info, folder_info)
            except PermissionDeniedError:
                raise
            except Exception as e:
                return {
                    "error": "permission_required",
                    "message": f"需要权限才能读取文件 {file_id}",
                    "file": {"id": file_id},
                }

        # 2. 获取文件信息，判断类型
        file_info = api_client.get_file_info(file_id)
        file_type = file_info.get("file_type", "").lower()
        file_path = file_info.get("path", "")

        # 3. 视频文件不支持
        video_types = ["mp4", "avi", "mov", "mkv", "flv", "wmv", "webm"]
        if file_type in video_types:
            return {
                "error": "unsupported_file_type",
                "message": "视频文件暂不支持通过 MCP 读取。",
                "file_type": file_type,
            }

        # 4. 图片文件返回 Base64
        image_types = ["jpg", "jpeg", "png", "gif", "bmp", "webp", "svg"]
        if file_type in image_types:
            try:
                file_path_obj = Path(file_path)
                if file_path_obj.exists():
                    content = file_path_obj.read_bytes()
                    base64_content = base64.b64encode(content).decode("utf-8")

                    # 推断 MIME 类型
                    mime_types = {
                        "jpg": "image/jpeg",
                        "jpeg": "image/jpeg",
                        "png": "image/png",
                        "gif": "image/gif",
                        "bmp": "image/bmp",
                        "webp": "image/webp",
                        "svg": "image/svg+xml",
                    }
                    mime_type = mime_types.get(file_type, "application/octet-stream")

                    return {
                        "type": "image",
                        "file_id": file_id,
                        "name": file_info.get("name"),
                        "content": base64_content,
                        "mime_type": mime_type,
                        "size": len(content),
                    }
                else:
                    return {
                        "error": "file_not_found",
                        "message": f"文件不存在: {file_path}",
                    }
            except Exception as e:
                return {
                    "error": "read_failed",
                    "message": f"读取图片失败: {str(e)}",
                }

        # 5. 文档文件返回文本内容
        try:
            chunks_data = api_client.get_file_chunks(
                file_id=file_id,
                page=page,
                chunk_start=chunk_start,
                chunk_end=chunk_end,
            )

            chunks = chunks_data.get("chunks", [])

            # 拼接文本
            text_parts = [chunk.get("text", "") for chunk in chunks]
            content = "\n\n".join(text_parts)

            return {
                "type": "document",
                "file_id": file_id,
                "name": file_info.get("name"),
                "content": content,
                "chunk_info": {
                    "total_chunks": chunks_data.get("total_chunks", 0),
                    "returned_chunks": len(chunks),
                    "page": page,
                    "chunk_range": [chunk_start, chunk_end] if chunk_start or chunk_end else None,
                    "page_count": chunks_data.get("page_count"),
                },
            }
        except Exception as e:
            return {
                "error": "read_failed",
                "message": f"读取文档失败: {str(e)}",
            }

    except PermissionDeniedError as e:
        file_info = e.file_info
        folder_info = e.folder_info

        return {
            "error": "permission_required",
            "message": f"需要权限才能读取文件 '{file_info.get('name', file_id)}'",
            "file": {
                "id": file_id,
                "name": file_info.get("name"),
                "folder_id": file_info.get("folder_id"),
                "folder_name": folder_info.get("name") if folder_info else None,
            },
            "options": [
                {
                    "type": "file",
                    "description": "仅授权此文件",
                    "tool": "grant_file_access",
                    "params": {"file_id": file_id, "duration_minutes": 10},
                },
                {
                    "type": "folder",
                    "description": f"授权整个文件夹（{folder_info.get('name')}）"
                    if folder_info
                    else "授权整个文件夹",
                    "tool": "grant_folder_access",
                    "params": {
                        "folder_id": file_info.get("folder_id"),
                        "duration_minutes": 10,
                    },
                }
                if file_info.get("folder_id")
                else None,
            ],
        }
    except Exception as e:
        return {
            "error": "unknown_error",
            "message": f"读取文件时发生错误: {str(e)}",
        }


async def grant_file_access_tool(
    api_client: FileSeekAPIClient,
    grant_store: GrantStore,
    file_id: str,
    duration_minutes: int = 10,
) -> dict[str, Any]:
    """授予单个文件的访问权限。

    Args:
        api_client: API 客户端
        grant_store: 授权存储
        file_id: 文件 ID
        duration_minutes: 授权时长（分钟），默认 10 分钟

    Returns:
        授权结果
    """
    try:
        # 获取文件信息
        file_info = api_client.get_file_info(file_id)

        # 记录授权
        grant_store.grant_file(
            file_id=file_id,
            file_name=file_info.get("name", ""),
            duration_minutes=duration_minutes,
            folder_id=file_info.get("folder_id"),
        )

        return {
            "success": True,
            "message": f"已授予文件 '{file_info.get('name')}' 访问权限",
            "file": {
                "id": file_id,
                "name": file_info.get("name"),
            },
            "expires_in_minutes": duration_minutes,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"授权失败: {str(e)}",
        }


async def grant_folder_access_tool(
    api_client: FileSeekAPIClient,
    grant_store: GrantStore,
    folder_id: str,
    duration_minutes: int = 10,
) -> dict[str, Any]:
    """授予文件夹下所有文件的访问权限。

    Args:
        api_client: API 客户端
        grant_store: 授权存储
        folder_id: 文件夹 ID
        duration_minutes: 授权时长（分钟），默认 10 分钟

    Returns:
        授权结果
    """
    try:
        # 获取文件夹信息
        folders = api_client.get_folders()
        folder = next((f for f in folders if f.get("id") == folder_id), None)

        if not folder:
            return {
                "success": False,
                "error": "folder_not_found",
                "message": f"文件夹不存在: {folder_id}",
            }

        # 搜索该文件夹下的所有文件
        search_result = api_client.search_files(
            query="",  # 空查询返回所有文件
            folder_id=folder_id,
            limit=1000,  # 假设文件夹最多 1000 个文件
        )

        files = search_result.get("data", {}).get("items", [])
        file_ids = [f.get("id") for f in files if f.get("id")]

        # 记录授权
        grant_store.grant_folder(
            folder_id=folder_id,
            folder_name=folder.get("name", ""),
            file_ids=file_ids,
            duration_minutes=duration_minutes,
        )

        return {
            "success": True,
            "message": f"已授予文件夹 '{folder.get('name')}' 访问权限",
            "folder": {
                "id": folder_id,
                "name": folder.get("name"),
                "file_count": len(file_ids),
            },
            "expires_in_minutes": duration_minutes,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"授权失败: {str(e)}",
        }
