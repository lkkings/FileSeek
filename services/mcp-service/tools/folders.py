"""list_folders 工具实现。"""

from typing import Any

from api_client import FileSeekAPIClient


async def list_folders_tool(api_client: FileSeekAPIClient) -> dict[str, Any]:
    """列出所有文件夹。

    不需要授权。

    Returns:
        包含文件夹列表的字典
    """
    try:
        folders = api_client.get_folders()

        return {
            "folders": [
                {
                    "id": folder.get("id"),
                    "name": folder.get("name"),
                    "file_count": folder.get("file_count", 0),
                }
                for folder in folders
            ],
            "total": len(folders),
        }
    except Exception as e:
        return {
            "error": str(e),
            "message": "无法获取文件夹列表，请确保 FileSeek Backend 正在运行。",
        }
