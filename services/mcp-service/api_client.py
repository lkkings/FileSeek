"""FileSeek Backend API 客户端。"""

import httpx
from typing import Any, Optional

from connection import ConnectionManager


class FileSeekAPIClient:
    """FileSeek Backend API 客户端（支持动态 token）。"""

    def __init__(self, connection_manager: ConnectionManager):
        self.connection = connection_manager
        self.client = httpx.Client(timeout=30.0)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """发送请求到 Backend API。

        自动使用最新的 URL 和 token。

        Args:
            method: HTTP 方法
            path: API 路径（相对于 /api/v1）
            **kwargs: 传递给 httpx 的其他参数

        Returns:
            解析后的 JSON 响应

        Raises:
            PermissionError: 认证失败（401）
            httpx.HTTPStatusError: 其他 HTTP 错误
        """
        url = f"{self.connection.get_api_url()}{path}"
        headers = kwargs.pop("headers", {})
        headers["X-FileSeek-Token"] = self.connection.get_token()

        try:
            resp = self.client.request(method, url, headers=headers, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise PermissionError(
                    "认证失败。Backend 可能已重启并生成了新 token。\n"
                    "请稍后重试，MCP Server 将自动使用新 token。"
                )
            raise

    def get_folders(self) -> list[dict]:
        """获取所有文件夹。

        Returns:
            文件夹列表，每个文件夹包含 id, name, file_count 等字段
        """
        data = self._request("GET", "/library/folders")
        return data.get("data", [])

    def search_files(
        self,
        query: str,
        folder_id: Optional[str] = None,
        file_types: Optional[list[str]] = None,
        limit: int = 20,
    ) -> dict:
        """搜索文件。

        Args:
            query: 搜索查询
            folder_id: 可选，限制到指定文件夹
            file_types: 可选，限制文件类型
            limit: 返回结果数量上限

        Returns:
            搜索结果，包含 items 和 total 字段
        """
        body: dict[str, Any] = {"query": query, "limit": limit}
        if folder_id:
            body["folder_id"] = folder_id
        if file_types:
            body["file_types"] = file_types

        return self._request("POST", "/search", json=body)

    def get_file_chunks(
        self,
        file_id: str,
        page: Optional[int] = None,
        chunk_start: Optional[int] = None,
        chunk_end: Optional[int] = None,
    ) -> dict:
        """获取文件的 chunks。

        Args:
            file_id: 文件 ID
            page: 可选，过滤到指定页
            chunk_start: 可选，起始 chunk（基于 line_number）
            chunk_end: 可选，结束 chunk（基于 line_number）

        Returns:
            包含 chunks, total_chunks, page_count 的字典
        """
        params = {}
        if page is not None:
            params["page"] = page
        if chunk_start is not None:
            params["chunk_start"] = chunk_start
        if chunk_end is not None:
            params["chunk_end"] = chunk_end

        data = self._request("GET", f"/library/files/{file_id}/chunks", params=params)
        return data.get("data", {})

    def get_file_info(self, file_id: str) -> dict:
        """获取文件基本信息。

        Args:
            file_id: 文件 ID

        Returns:
            文件信息字典
        """
        data = self._request("GET", f"/library/files/{file_id}")
        return data.get("data", {})

    def close(self):
        """关闭客户端连接。"""
        self.client.close()
