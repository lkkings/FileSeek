"""search_files 工具实现。"""

from typing import Any, Optional

from api_client import FileSeekAPIClient


async def search_files_tool(
    api_client: FileSeekAPIClient,
    query: str,
    folder_id: Optional[str] = None,
    file_types: Optional[list[str]] = None,
    limit: int = 20,
) -> dict[str, Any]:
    """搜索文件。

    不需要授权。

    Args:
        api_client: API 客户端
        query: 搜索查询
        folder_id: 可选，限制到指定文件夹
        file_types: 可选，限制文件类型（如 ["pdf", "jpg"]）
        limit: 返回结果数量上限

    Returns:
        包含搜索结果的字典
    """
    try:
        result = api_client.search_files(
            query=query,
            folder_id=folder_id,
            file_types=file_types,
            limit=limit,
        )

        data = result.get("data", {})
        items = data.get("items", [])

        return {
            "files": [
                {
                    "file_id": item.get("id"),
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "file_type": item.get("file_type"),
                    "score": item.get("score", 0),
                    "folder_id": item.get("folder_id"),
                    "size": item.get("size"),
                }
                for item in items
            ],
            "total": data.get("total", 0),
            "query": query,
        }
    except Exception as e:
        return {
            "error": str(e),
            "message": "搜索失败，请确保 FileSeek Backend 正在运行。",
        }
