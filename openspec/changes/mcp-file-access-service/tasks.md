## 1. Backend API 扩展

- [x] 1.1 在 `backend/src/fileseek/features/library/interfaces/http/schemas/file.py` 新增 `FileChunksRequest` 和 `FileChunksResponse` schema，包含 page、chunk_start、chunk_end 参数和返回结构，验证 schema 定义符合 OpenAPI 规范
- [x] 1.2 在 `backend/src/fileseek/features/library/domain/repositories/__init__.py` 的 `FileChunkRepository` 协议中新增 `get_chunks_by_range` 方法签名，验证类型注解正确
- [x] 1.3 在 `backend/src/fileseek/features/library/infrastructure/repositories/chunk.py` 实现 `get_chunks_by_range` 方法，支持按 page、line_number 范围查询，验证单元测试覆盖所有查询组合（仅 page、仅 chunk 范围、page+chunk 范围、无参数）
- [x] 1.4 新增 use case `backend/src/fileseek/features/library/application/use_cases/get_file_chunks.py`，调用 repository 并返回 DTO，验证单元测试通过
- [x] 1.5 在 `backend/src/fileseek/features/library/interfaces/http/routers/file.py` 新增 `GET /files/{file_id}/chunks` 路由，验证 `curl "http://localhost:8765/api/v1/library/files/{id}/chunks?page=1"` 返回正确数据

## 2. MCP Server - 基础设施

- [x] 2.1 创建 `services/mcp-service/` 目录结构，包含 `__main__.py`、`requirements.txt`、`pyproject.toml`，验证目录结构符合 Python 包规范
- [x] 2.2 在 `requirements.txt` 添加依赖：`mcp>=1.0.0`、`httpx>=0.27.0`，验证 `pip install -r requirements.txt` 成功
- [x] 2.3 实现 `services/mcp-service/connection.py` 的 `ConnectionManager` 类，包含 mtime 缓存逻辑，验证单元测试覆盖：connection.json 不存在、JSON 损坏、mtime 缓存命中、文件变化重新加载
- [x] 2.4 实现 `services/mcp-service/permissions.py` 的 `GrantStore` 类，支持加载、保存、检查权限，验证单元测试覆盖：加载不存在的文件、过期授权自动清理、授权检查（文件授权、文件夹授权、过期授权）
- [x] 2.5 实现 `services/mcp-service/api_client.py` 的 `FileSeekAPIClient` 类，封装对 Backend API 的调用，验证单元测试覆盖：成功请求、401 错误处理、网络错误处理

## 3. MCP Server - 工具实现

- [x] 3.1 实现 `services/mcp-service/tools/folders.py` 的 `list_folders` 工具，调用 `/library/folders` API，验证返回格式符合 MCP 工具规范
- [x] 3.2 实现 `services/mcp-service/tools/search.py` 的 `search_files` 工具，调用 `/search` API 并支持 query、folder_id、file_types 参数，验证返回格式符合 MCP 工具规范
- [x] 3.3 实现 `services/mcp-service/tools/files.py` 的 `read_file` 工具，包含权限检查逻辑，验证：无权限时返回结构化错误（包含文件信息和授权选项）、有权限时调用 chunks API 或返回图片 Base64、视频文件返回不支持错误
- [x] 3.4 实现 `services/mcp-service/tools/files.py` 的 `grant_file_access` 工具，记录文件授权到 GrantStore，验证授权成功后 read_file 可通过
- [x] 3.5 实现 `services/mcp-service/tools/files.py` 的 `grant_folder_access` 工具，查询文件夹下的文件 ID 列表并记录授权，验证授权成功后该文件夹下所有文件的 read_file 可通过

## 4. MCP Server - 主程序

- [x] 4.1 实现 `services/mcp-service/__main__.py`，初始化 MCP Server、注册所有工具、启动 stdio transport，验证 `python -m mcp-service` 可启动且无异常退出
- [x] 4.2 实现工具的错误处理和日志记录，所有异常捕获并返回结构化错误而非崩溃，验证模拟异常场景（Backend 不可用、文件不存在）时返回清晰错误信息
- [x] 4.3 编写 `services/mcp-service/README.md` 文档，说明配置方式、环境变量、文件路径约定，验证文档清晰可读
- [x] 4.4 配置 PyInstaller 打包脚本 `services/mcp-service/build.spec`，验证 `pyinstaller build.spec` 生成单文件可执行且体积合理（< 50MB）

## 5. MCP Server - 集成测试

- [x] 5.1 编写端到端测试：启动隔离的 Backend 实例，调用 MCP Server 工具，验证 list_folders、search_files 返回正确数据
- [x] 5.2 验证授权流程：调用 grant_file_access 后 read_file 成功，验证授权过期后 read_file 失败
- [x] 5.3 验证 connection.json 动态刷新：模拟 Backend 重启生成新 token，验证 MCP Server 自动使用新 token
- [x] 5.4 验证授权持久化：MCP Server 重启后加载 mcp-grants.json，验证未过期的授权仍然有效

## 6. Desktop - MCP 设置页面

- [x] 6.1 创建 `desktop/src/pages/settings/MCPSettings.tsx` 组件，包含页面布局和占位符内容，验证页面在设置菜单中显示（已优化为专业设计）
- [x] 6.2 创建 `desktop/src/services/mcp-config.ts`，实现 `generateMCPConfig()` 函数，从应用资源目录解析 MCP Server 可执行文件路径，验证在 macOS/Windows 上返回正确路径
- [x] 6.3 实现配置生成 UI：显示 JSON 配置、复制到剪贴板按钮、平台特定的配置目录路径，验证点击复制后剪贴板包含正确 JSON
- [x] 6.4 实现 `openClaudeConfigDir()` 函数，根据平台打开对应目录（macOS: `~/Library/Application Support/Claude/`），验证在 macOS 上调用 Tauri 的 `shell.open()` 打开正确目录
- [x] 6.5 实现授权列表显示：读取 `mcp-grants.json`、计算剩余时间、显示文件/文件夹授权卡片，验证页面正确显示已授权资源且每分钟刷新时间

## 7. Desktop - 授权管理

- [x] 7.1 实现单个授权撤销功能：点击撤销按钮后从 JSON 删除对应 key 并写回文件，验证撤销后授权列表更新且 MCP Server 再次读取文件时权限失效
- [x] 7.2 实现"清除已过期"功能：过滤出 `expires_at < now` 的授权并删除，验证点击后已过期授权从列表移除
- [x] 7.3 实现"清除所有授权"功能：弹出确认对话框，确认后清空 `grants` 对象并写回文件，验证确认后所有授权被清除
- [x] 7.4 实现默认授权时长设置：添加输入框保存到本地存储，验证设置后新授权请求建议该时长（此功能在 MCP Server 中体现，Desktop 只负责存储配置）

## 8. Desktop - 集成与 UI 优化

- [x] 8.1 在设置页面菜单添加"MCP 服务"入口，验证从设置页面可进入 MCP 设置
- [x] 8.2 添加 MCP 设置页面的帮助文本：显示配置步骤（安装 MCP 客户端 → 复制配置 → 重启客户端 → 测试连接），验证文本清晰易懂
- [x] 8.3 添加"检测 MCP Server 可执行文件"功能：检查应用资源目录是否存在可执行文件，验证存在时显示绿色"就绪"状态，不存在时显示错误提示
- [x] 8.4 实现响应式布局和样式：确保 MCP 设置页面在不同窗口大小下正常显示，验证页面在最小窗口宽度下无布局错乱

## 9. 打包与部署

- [x] 9.1 将打包好的 MCP Server 可执行文件放入 `desktop/src-tauri/binaries/`，按平台命名（如 `fileseek-mcp-service-aarch64-apple-darwin`），验证文件存在且有执行权限
- [x] 9.2 更新 `desktop/src-tauri/tauri.conf.json` 的 `externalBin` 配置，包含 MCP Server 可执行文件，验证 Tauri 打包后应用包内包含可执行文件
- [x] 9.3 编写用户文档 `docs/mcp-setup-guide.md`，说明如何配置 Claude Desktop 和其他 MCP 客户端，验证按文档操作可成功启用 MCP 服务
- [x] 9.4 更新 `README.md`，添加 MCP 功能说明和文档链接，验证说明准确且链接有效

## 10. 端到端验证

- [x] 10.1 在本地环境配置 Claude Desktop，验证 list_folders 工具返回文件夹列表
- [x] 10.2 在 Claude 中搜索文件，验证 search_files 工具返回搜索结果
- [x] 10.3 尝试读取未授权文件，验证 Claude 理解错误并询问用户是否授权
- [x] 10.4 用户授权后再次读取，验证 read_file 成功返回文件内容
- [x] 10.5 重启 FileSeek Backend，验证 MCP Server 自动适配新 token 且功能正常
- [x] 10.6 重启 Claude Desktop（重启 MCP Server），验证之前的授权仍然有效
