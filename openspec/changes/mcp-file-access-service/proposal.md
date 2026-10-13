## Why

FileSeek 的文件库目前只能通过桌面应用访问。AI 助手（如 Claude Desktop、Cline 等）无法直接读取和搜索用户的文件，导致用户需要手动复制文件内容或在两个应用间切换。通过 MCP（Model Context Protocol）封装 FileSeek 的核心能力，可以让 AI 助手直接访问文件库，提升用户体验和工作效率。

## What Changes

- 新增独立的 MCP Server 可执行文件（Python），通过 stdio 实现 MCP 协议
- 实现三个 MCP 工具：`list_folders`、`search_files`、`read_file`
- 实现基于时间窗口的权限系统：读取文件需要用户授权（按文件或文件夹），授权信息持久化到本地文件
- 新增两个授权工具：`grant_file_access`、`grant_folder_access`
- Backend 新增 API：`GET /library/files/{id}/chunks` 用于按页和 chunk 范围读取文档内容
- Desktop 新增 MCP 设置页面：生成配置、复制到剪贴板、管理已授权资源
- MCP Server 自动从 `connection.json` 读取动态刷新的 token，适配 Backend 重启
- 图片文件返回 Base64 编码，视频文件暂不支持

## Capabilities

### New Capabilities

- `mcp-service/file-access`: MCP Server 的文件访问工具（列表、搜索、读取）和权限管理
- `mcp-service/configuration`: Desktop 的 MCP 配置生成和授权管理 UI

### Modified Capabilities

<!-- 无现有 capability 的需求变更 -->

## Impact

**新增组件**：
- `services/mcp-service/`：独立的 Python MCP Server，打包成单文件可执行
- `backend/src/fileseek/features/library/interfaces/http/routers/file.py`：新增 chunks 查询接口
- `desktop/src/pages/settings/MCPSettings.tsx`：MCP 设置页面
- `desktop/src/services/mcp-config.ts`：配置生成逻辑

**依赖变更**：
- MCP Server 依赖：`mcp` (MCP SDK)、`httpx`（HTTP 客户端）
- Backend 无新增依赖
- Desktop 无新增依赖

**数据存储**：
- `~/Library/Application Support/FileSeek/mcp-grants.json`：授权记录（MCP Server 写入）
- `~/Library/Application Support/FileSeek/connection.json`：Backend 连接信息（已存在，MCP Server 读取）

**兼容性**：
- 现有 Desktop 和 Backend 功能不受影响
- MCP 服务是可选功能，不启用时无影响
