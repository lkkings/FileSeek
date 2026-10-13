"""FileSeek MCP Service 入口点。"""

import asyncio
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server

from connection import ConnectionManager, ConnectionError
from permissions import GrantStore
from api_client import FileSeekAPIClient
from tools.folders import list_folders_tool
from tools.search import search_files_tool
from tools.files import (
    read_file_tool,
    grant_file_access_tool,
    grant_folder_access_tool,
)


async def main():
    """MCP Server 主函数。"""
    # 初始化连接管理器
    try:
        connection_manager = ConnectionManager()
        print(f"[INFO] 连接文件路径: {connection_manager.path}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] 初始化连接管理器失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 初始化授权存储
    try:
        # 授权文件与 connection.json 放在同一目录
        grants_path = connection_manager.path.parent / "mcp-grants.json"
        grant_store = GrantStore(grants_path)
        print(f"[INFO] 授权文件路径: {grants_path}", file=sys.stderr)

        # 显示已加载的授权数量
        active_grants = grant_store.list_active_grants()
        print(f"[INFO] 已加载 {len(active_grants)} 个有效授权", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] 初始化授权存储失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 初始化 API 客户端
    api_client = FileSeekAPIClient(connection_manager)

    # 创建 MCP Server
    server = Server("fileseek")

    # 注册工具：list_folders
    @server.list_tools()
    async def list_tools():
        return [
            {
                "name": "list_folders",
                "description": "列出 FileSeek 文件库中的所有文件夹。不需要授权。",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "search_files",
                "description": "在 FileSeek 文件库中搜索文件。不需要授权。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索查询",
                        },
                        "folder_id": {
                            "type": "string",
                            "description": "可选，限制到指定文件夹",
                        },
                        "file_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "可选，限制文件类型（如 ['pdf', 'jpg']）",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返回结果数量上限，默认 20",
                            "default": 20,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "read_file",
                "description": (
                    "读取文件内容。需要授权。"
                    "文档文件支持按页或 chunk 范围读取，图片返回 Base64 编码。"
                    "如果没有授权，会返回错误并提示如何授权。"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "文件 ID",
                        },
                        "page": {
                            "type": "integer",
                            "description": "可选，文档的页码",
                        },
                        "chunk_start": {
                            "type": "integer",
                            "description": "可选，起始 chunk（基于段落编号）",
                        },
                        "chunk_end": {
                            "type": "integer",
                            "description": "可选，结束 chunk（基于段落编号）",
                        },
                    },
                    "required": ["file_id"],
                },
            },
            {
                "name": "grant_file_access",
                "description": "授予读取单个文件的权限。授权后可以在指定时长内读取该文件。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "文件 ID",
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "授权时长（分钟），默认 10 分钟",
                            "default": 10,
                        },
                    },
                    "required": ["file_id"],
                },
            },
            {
                "name": "grant_folder_access",
                "description": "授予读取整个文件夹的权限。授权后可以在指定时长内读取该文件夹下的所有文件。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "folder_id": {
                            "type": "string",
                            "description": "文件夹 ID",
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "授权时长（分钟），默认 10 分钟",
                            "default": 10,
                        },
                    },
                    "required": ["folder_id"],
                },
            },
        ]

    # 注册工具调用处理器
    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        try:
            if name == "list_folders":
                return await list_folders_tool(api_client)
            elif name == "search_files":
                return await search_files_tool(
                    api_client=api_client,
                    query=arguments.get("query", ""),
                    folder_id=arguments.get("folder_id"),
                    file_types=arguments.get("file_types"),
                    limit=arguments.get("limit", 20),
                )
            elif name == "read_file":
                return await read_file_tool(
                    api_client=api_client,
                    grant_store=grant_store,
                    file_id=arguments.get("file_id"),
                    page=arguments.get("page"),
                    chunk_start=arguments.get("chunk_start"),
                    chunk_end=arguments.get("chunk_end"),
                )
            elif name == "grant_file_access":
                return await grant_file_access_tool(
                    api_client=api_client,
                    grant_store=grant_store,
                    file_id=arguments.get("file_id"),
                    duration_minutes=arguments.get("duration_minutes", 10),
                )
            elif name == "grant_folder_access":
                return await grant_folder_access_tool(
                    api_client=api_client,
                    grant_store=grant_store,
                    folder_id=arguments.get("folder_id"),
                    duration_minutes=arguments.get("duration_minutes", 10),
                )
            else:
                return {
                    "error": "unknown_tool",
                    "message": f"未知工具: {name}",
                }
        except Exception as e:
            print(f"[ERROR] 工具调用失败 ({name}): {e}", file=sys.stderr)
            return {
                "error": "tool_execution_failed",
                "message": f"工具执行失败: {str(e)}",
            }

    # 启动 stdio transport
    print("[INFO] FileSeek MCP Service 启动", file=sys.stderr)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[INFO] 收到中断信号，退出", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] 服务异常退出: {e}", file=sys.stderr)
        sys.exit(1)
