# FileSeek MCP 服务配置指南

本指南将帮助你配置 MCP (Model Context Protocol) 服务，让 AI 助手（如 Claude Desktop、Cline 等）直接访问你的 FileSeek 文件库。

## 前置条件

- FileSeek Desktop 应用已安装并运行
- 支持 MCP 的 AI 客户端（如 Claude Desktop）

## 支持的 MCP 客户端

- **Claude Desktop** - Anthropic 官方桌面客户端
- **Cline** - VS Code 扩展
- 其他支持 MCP 协议的客户端

## 配置步骤

### 1. 打开 FileSeek 的 MCP 设置

1. 启动 FileSeek Desktop
2. 进入 **设置** (⚙️)
3. 找到 **MCP 服务** 部分

### 2. 复制 MCP 配置

在 MCP 设置页面：

1. 点击 **复制配置** 按钮
2. 配置 JSON 已复制到剪贴板

配置示例：
```json
{
  "mcpServers": {
    "fileseek": {
      "command": "/Applications/FileSeek.app/Contents/Resources/fileseek-mcp-service"
    }
  }
}
```

### 3. 配置你的 MCP 客户端

#### Claude Desktop

**macOS:**
1. 打开 Finder
2. 按 `Cmd + Shift + G`，输入：
   ```
   ~/Library/Application Support/Claude/
   ```
3. 打开或创建 `claude_desktop_config.json`
4. 粘贴 FileSeek 的配置（如果文件已有内容，合并到 `mcpServers` 对象中）
5. 保存文件

**Windows:**
1. 打开文件资源管理器
2. 在地址栏输入：
   ```
   %APPDATA%\Claude\
   ```
3. 打开或创建 `claude_desktop_config.json`
4. 粘贴 FileSeek 的配置
5. 保存文件

#### Cline (VS Code)

1. 打开 VS Code
2. 进入 **Settings** (设置)
3. 搜索 "Cline: MCP Settings"
4. 粘贴 FileSeek 的配置

### 4. 重启 MCP 客户端

配置完成后，**完全退出并重启** Claude Desktop 或其他 MCP 客户端，使配置生效。

### 5. 测试连接

在 Claude 或其他 AI 助手中输入：

```
列出我的文件夹
```

或

```
搜索"报告"
```

如果配置成功，AI 助手将返回你的文件夹列表或搜索结果。

## 功能说明

### 无需授权的功能

- **列出文件夹** - 查看所有文件夹
- **搜索文件** - 搜索文件（支持按文件夹、文件类型过滤）

### 需要授权的功能

- **读取文件内容** - 读取文档文本或图片（Base64）

当 AI 助手尝试读取文件时，如果没有授权，会返回错误并询问是否授权。你可以选择：

- **授权单个文件** - 仅授权当前文件
- **授权整个文件夹** - 授权文件夹下的所有文件

授权默认有效期为 **10 分钟**，过期后需要重新授权。

### 授权管理

在 FileSeek 的 **MCP 设置** 页面，你可以：

- 查看所有已授权的文件和文件夹
- 查看剩余时间
- 手动撤销授权
- 清除过期或所有授权

## 权限和安全

### 授权机制

- **明确授权** - AI 助手无法在未经授权的情况下读取文件内容
- **时间窗口** - 授权有时间限制，默认 10 分钟
- **持久化** - 授权信息保存到本地，MCP 服务重启后仍然有效
- **文件/文件夹级别** - 可以精确控制授权范围

### 数据隐私

- MCP 服务运行在你的本地计算机上
- 所有文件访问都在本地完成，不会上传到云端
- 授权信息存储在本地文件：
  - macOS: `~/Library/Application Support/FileSeek/mcp-grants.json`
  - Windows: `%APPDATA%\FileSeek\mcp-grants.json`
  - Linux: `~/.config/FileSeek/mcp-grants.json`

## 故障排除

### MCP 客户端无法连接

**症状**：AI 助手提示"工具不可用"或"FileSeek 连接失败"

**解决方法**：
1. 确保 FileSeek Desktop 正在运行
2. 检查 MCP 配置文件路径是否正确
3. 完全退出并重启 MCP 客户端
4. 检查 FileSeek 的 MCP 设置，确认"MCP 服务已就绪"

### 文件读取失败

**症状**：搜索可用，但读取文件返回错误

**解决方法**：
1. 在 FileSeek 的 MCP 设置中授予文件或文件夹权限
2. 检查授权是否过期（查看剩余时间）
3. 确认文件确实存在于 FileSeek 文件库中

### Backend 重启后连接断开

**正常行为**：FileSeek Backend 重启会生成新的认证 token，MCP 服务会自动适配。

如果仍然无法连接：
1. 等待几秒钟，MCP 服务会在下次 API 调用时自动读取新 token
2. 如果持续失败，重启 MCP 客户端

### 视频文件无法读取

视频文件暂不支持通过 MCP 读取，这是设计限制。

## 进阶配置

### 自定义连接文件路径

如果 FileSeek 安装在非标准位置，可以通过环境变量指定 `connection.json` 路径：

```json
{
  "mcpServers": {
    "fileseek": {
      "command": "/path/to/fileseek-mcp-service",
      "env": {
        "FILESEEK_CONNECTION_FILE": "/custom/path/connection.json"
      }
    }
  }
}
```

### 多个 MCP 服务

你可以在配置文件中添加多个 MCP 服务：

```json
{
  "mcpServers": {
    "fileseek": {
      "command": "/Applications/FileSeek.app/Contents/Resources/fileseek-mcp-service"
    },
    "other-service": {
      "command": "/path/to/other-service"
    }
  }
}
```

## 反馈和支持

如果遇到问题或有建议，请通过 FileSeek 的反馈渠道联系我们。

---

**版本**：0.1.0  
**最后更新**：2024 年 10 月
