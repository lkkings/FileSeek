## Context

FileSeek 当前由三个部分组成：
- **Backend**（Python/FastAPI）：运行在本地，每次启动生成新的认证 token 并写入 `connection.json`
- **Desktop**（Tauri/React）：读取 `connection.json` 获取 Backend 的端口和 token
- **文件库**：位于 `~/FileSeekLibrary/`，文件由 Backend 解析为 chunks 并存储向量索引

现有架构中没有对外暴露的 API（token 是动态的，不适合外部集成）。MCP（Model Context Protocol）是 Anthropic 推出的协议，让 AI 助手通过 stdio 与本地服务通信。

## Goals / Non-Goals

**Goals:**
- 实现符合 MCP 协议的独立服务，可被任意 MCP 客户端使用（Claude Desktop、Cline、其他）
- 用户可控的权限系统，避免 AI 未经授权访问敏感文件
- 适配 Backend 的动态 token 机制，重启不影响 MCP 服务可用性
- 授权状态持久化，MCP Server 重启后无需重新授权
- 配置简单，用户只需复制一段 JSON 到 MCP 客户端配置文件

**Non-Goals:**
- 不实现 MCP Server 的自动安装或更新（用户手动配置）
- 不支持视频文件读取（MCP 协议传输大文件受限，且视频对 LLM 意义有限）
- 不实现细粒度权限（如"只读某一页"），授权以文件或文件夹为单位
- Desktop 不启动或停止 MCP Server（MCP Server 由 MCP 客户端管理）

## Decisions

### D1. MCP Server 作为独立进程

**决策**：MCP Server 是独立的 Python 可执行文件，由 MCP 客户端（如 Claude Desktop）启动，通过 stdio 通信。

**备选方案**：
- 方案 A：集成到 Backend 中，暴露 WebSocket 或 SSE 接口 → 需要 MCP 客户端支持 HTTP transport，限制兼容性
- 方案 B：集成到 Desktop 中，作为 Tauri sidecar → Desktop 重启会中断 MCP 连接

**理由**：
- MCP 协议的标准实现是 stdio transport，独立进程符合生态惯例
- 独立进程隔离故障，MCP Server 崩溃不影响 Desktop 或 Backend
- 打包成单文件可执行（PyInstaller），用户配置时指定路径即可

### D2. 动态读取 connection.json

**决策**：MCP Server 不在配置文件中写死 token，而是每次 API 调用前从 `connection.json` 读取最新的端口和 token。使用文件 mtime 缓存，避免频繁 I/O。

**数据流**：
```
Backend 启动 → 生成新 token → 写入 connection.json
                                     ↓
MCP Server 调用 API ← 检查 mtime ← 缓存 token
                         ↓ (文件变化)
                      重新读取 token
```

**备选方案**：
- 方案 A：在 MCP 配置中写死 token → Backend 重启后所有 MCP 请求 401，用户需重新配置
- 方案 B：Backend 提供长期有效的 API Key → 增加安全风险，且违背现有的动态 token 设计

**理由**：
- Backend 每次重启都生成新 token 是安全设计，不应为 MCP 改变
- 文件 mtime 缓存策略在正常使用下（Backend 不频繁重启）几乎无性能损耗

### D3. 授权状态持久化到 JSON 文件

**决策**：授权记录存储在 `~/Library/Application Support/FileSeek/mcp-grants.json`，MCP Server 启动时加载，每次授权后写入。

**文件格式**：
```json
{
  "version": 1,
  "grants": {
    "file:abc123": {
      "type": "file",
      "file_id": "abc123",
      "file_name": "报告.pdf",
      "granted_at": 1696123456,
      "expires_at": 1696124056,
      "folder_id": null
    },
    "folder:work_docs": {
      "type": "folder",
      "folder_id": "work_docs",
      "folder_name": "工作文档",
      "granted_at": 1696123500,
      "expires_at": 1696125100,
      "file_ids": ["abc", "def", ...]
    }
  }
}
```

**备选方案**：
- 方案 A：存储在 Backend 数据库 → MCP Server 需要频繁查询数据库，增加耦合
- 方案 B：仅存内存，不持久化 → MCP Server 重启后所有授权丢失，用户体验差

**理由**：
- 授权是 MCP Server 的本地状态，不涉及业务逻辑，无需入库
- JSON 文件简单可靠，Desktop 也可直接读取用于 UI 展示
- 自动清理过期授权：加载时丢弃 `expires_at < now` 的记录

### D4. Backend 新增 chunks 查询接口

**决策**：新增 `GET /library/files/{file_id}/chunks` 接口，支持按页和 chunk 范围查询。

**接口设计**：
```
GET /library/files/{file_id}/chunks
    ?page=5
    &chunk_start=10
    &chunk_end=25

Response:
{
  "status": "success",
  "data": {
    "chunks": [
      {
        "text": "...",
        "page_number": 5,
        "line_number": 10,  // 实际是段落编号
        "chunk_index": 42
      },
      ...
    ],
    "total_chunks": 100,
    "page_count": 20
  }
}
```

**参数语义**：
- `page`：可选，过滤到指定页
- `chunk_start` / `chunk_end`：可选，基于 `line_number`（段落编号）过滤
- 不指定任何参数：返回全文（可能需要分页或截断大文档）

**备选方案**：
- 方案 A：MCP Server 直接查询数据库 → 需要暴露数据库连接，耦合过紧
- 方案 B：复用现有的搜索接口 → 搜索接口返回的 chunks 不完整，无法满足"读取特定范围"的需求

**理由**：
- Backend 是唯一有权访问数据库的组件，通过 HTTP API 暴露是标准做法
- 接口设计灵活，支持按页、按 chunk、或全文读取

### D5. 图片返回 Base64，视频不支持

**决策**：
- 图片文件（JPG、PNG、GIF 等）：返回 Base64 编码的二进制数据 + MIME 类型
- 视频文件（MP4、AVI 等）：返回错误，提示暂不支持

**理由**：
- MCP 协议基于 JSON-RPC，大文件传输（几百 MB 视频）会导致内存和性能问题
- LLM 对视频的理解有限，即使传输成功，处理效果也不理想
- FileSeek 已在导入时提取视频的关键帧和音频转录，未来可考虑返回这些元数据（不在本次 change 范围）

### D6. 前端 MCP 设置页面读取 grants 文件

**决策**：Desktop 的 MCP 设置页面直接读取 `mcp-grants.json`，显示当前授权状态。提供手动撤销功能，直接修改文件。

**交互设计**：
```
┌────────────────────────────────────┐
│ MCP 服务配置                        │
├────────────────────────────────────┤
│ [配置生成部分]                      │
│                                    │
│ ── 已授权的资源 ──                  │
│                                    │
│ 📁 工作文档 (15个文件)              │
│    剩余时间: 8分钟  [撤销]          │
│                                    │
│ 📄 个人简历.pdf                     │
│    剩余时间: 3分钟  [撤销]          │
│                                    │
│ [清除已过期] [清除所有]             │
└────────────────────────────────────┘
```

**实现**：
- 使用 Tauri 的文件系统 API 读取 JSON
- 计算剩余时间：`(expires_at - Date.now()) / 60000` 分钟
- 撤销授权：删除对应的 key，写回文件
- 每分钟刷新一次 UI（用 `setInterval`）

**备选方案**：
- 方案 A：通过 Backend API 查询授权状态 → 需要 Backend 新增接口，且 Backend 不应管理 MCP 的授权
- 方案 B：不显示授权状态，只提供配置生成 → 用户无法知道哪些文件/文件夹已授权

**理由**：
- 授权文件是明文 JSON，Desktop 可以安全读取
- 直接文件操作简单高效，无需新增 Backend 接口

### D7. MCP 配置不包含 token，仅包含可执行文件路径

**决策**：生成的 MCP 配置 JSON 只包含 MCP Server 可执行文件的路径，不包含 API URL 或 token。

**配置示例**：
```json
{
  "mcpServers": {
    "fileseek": {
      "command": "/Applications/FileSeek.app/Contents/Resources/fileseek-mcp-service"
    }
  }
}
```

MCP Server 自己从平台标准路径查找 `connection.json`：
- macOS: `~/Library/Application Support/FileSeek/connection.json`
- Windows: `%APPDATA%/FileSeek/connection.json`
- Linux: `~/.config/FileSeek/connection.json`

如果用户的 FileSeek 安装在非标准位置，可通过环境变量覆盖：
```json
{
  "mcpServers": {
    "fileseek": {
      "command": "/custom/path/fileseek-mcp-service",
      "env": {
        "FILESEEK_CONNECTION_FILE": "/custom/path/connection.json"
      }
    }
  }
}
```

**理由**：
- 配置简洁通用，适配任意 MCP 客户端
- 避免在配置中暴露 token（安全）
- 用户只需复制一次配置，Backend 重启无需重新配置

## Risks / Trade-offs

### [MCP Server 崩溃导致 MCP 客户端卡住]

**风险**：如果 MCP Server 因未捕获异常崩溃，MCP 客户端可能收不到响应，导致超时或卡住。

**缓解**：
- 所有工具调用都包裹在 try-except 中，返回结构化错误而非崩溃
- 使用 Python 的 logging 模块记录所有异常，方便调试
- MCP 客户端通常有超时机制，最坏情况下用户重启客户端即可

### [大文档读取可能返回大量数据]

**风险**：用户请求读取整个 PDF（`read_file(file_id="abc")` 不带参数），如果文档有几百页，返回数据可能达到数 MB。

**缓解**：
- 在 MCP Server 中限制单次返回的 chunk 数量（如最多 100 个 chunk）
- 超过限制时返回截断的内容 + 提示信息："文档过大，已返回前 100 个 chunk，请指定 page 或 chunk 范围"
- 文档说明建议用户按页或范围读取，而非全文

### [connection.json 损坏或被删除]

**风险**：如果 `connection.json` 被意外删除或内容损坏，MCP Server 无法连接 Backend。

**缓解**：
- 返回清晰的错误提示："FileSeek Backend 未运行或连接文件损坏，请确保 FileSeek Desktop 应用正在运行"
- 用户重启 Desktop 会重新生成 `connection.json`

### [授权文件被手动修改后格式错误]

**风险**：用户或其他程序修改 `mcp-grants.json`，导致 JSON 解析失败。

**缓解**：
- 加载时捕获 `JSONDecodeError`，如果解析失败，清空授权并重新初始化为空对象
- 记录警告日志，提示授权文件已重置

### [FileSeek 的"文件夹"是虚拟分组，不是真实目录]

**权衡**：FileSeek 的 folder 不是文件系统目录，而是标签式的分组。这可能让用户误以为"授权 /documents 文件夹"是授权某个磁盘目录。

**缓解**：
- 在错误提示和文档中明确说明"文件夹"是 FileSeek 中的分组概念
- 授权时返回文件夹名称和文件数量，让用户明确授权范围

### [MCP 协议不支持弹窗，依赖 LLM 转述]

**权衡**：MCP 协议没有原生的"弹窗"能力。权限请求通过返回特殊错误，由 LLM 理解并询问用户，再调用授权工具。这依赖 LLM 的理解能力。

**缓解**：
- 错误信息结构化且详细，包含文件名、文件夹名、可选的授权方式
- 在 MCP Server 的工具描述中明确说明授权流程，帮助 LLM 理解

## Migration Plan

**部署步骤**：
1. Backend 部署：新增 `/library/files/{file_id}/chunks` 接口
2. 打包 MCP Server：使用 PyInstaller 打包成单文件可执行，嵌入 Desktop 应用包
3. Desktop 部署：新增 MCP 设置页面
4. 文档：提供用户指南，说明如何配置 MCP 客户端

**回滚策略**：
- Backend 新增的接口是独立的，不影响现有功能，可随时下线
- MCP Server 是可选功能，用户不配置则无影响
- Desktop 的 MCP 设置页面是新增页面，删除不影响其他功能

**兼容性**：
- 现有用户无需迁移，MCP 功能是增量添加
- 未来如果 MCP 协议更新，只需更新 MCP Server 可执行文件

## Open Questions

无。所有影响实现的问题已在设计阶段解决。
