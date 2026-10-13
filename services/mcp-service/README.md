# FileSeek MCP Service

让 AI 助手（Claude Desktop、Cline 等）直接访问 FileSeek 文件库。

## 功能

- `list_folders` - 列出所有文件夹
- `search_files` - 搜索文件
- `read_file` - 读取文件内容（需要授权）
- `grant_file_access` - 授予文件访问权限
- `grant_folder_access` - 授予文件夹访问权限

## 安装

打包成单文件可执行：

```bash
pyinstaller --onefile __main__.py -n fileseek-mcp-service
```

## 配置

MCP 客户端配置示例（Claude Desktop）：

```json
{
  "mcpServers": {
    "fileseek": {
      "command": "/path/to/fileseek-mcp-service"
    }
  }
}
```

MCP Server 会自动从以下路径读取 FileSeek 的连接信息：
- macOS: `~/Library/Application Support/FileSeek/connection.json`
- Windows: `%APPDATA%/FileSeek/connection.json`
- Linux: `~/.config/FileSeek/connection.json`

如果 FileSeek 安装在非标准位置，可通过环境变量指定：

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

## 授权机制

读取文件内容需要用户授权。授权以文件或文件夹为单位，可设置有效时长（默认 10 分钟）。

授权信息持久化到本地文件，MCP Server 重启后仍然有效。

## 开发

安装依赖：

```bash
pip install -r requirements.txt
```

运行：

```bash
python -m mcp-service
```
