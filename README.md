# FileSeek

FileSeek 是一个智能文件管理和搜索系统，支持本地和 NAS 存储，提供强大的向量搜索和 AI 集成能力。

## 功能特性

- 📁 **智能文件管理** - 支持本地和 NAS 多存储源
- 🔍 **向量搜索** - 基于语义的文件内容搜索
- 🤖 **AI 集成 (MCP)** - 让 AI 助手直接访问你的文件库
- 🏷️ **标签管理** - 灵活的文件分类和组织
- 🖼️ **多格式支持** - 文档、图片、音频、视频等

## MCP 服务

FileSeek 支持 MCP (Model Context Protocol)，让 Claude Desktop 等 AI 助手直接访问你的文件库。

### 功能

- ✅ 列出文件夹
- ✅ 搜索文件
- ✅ 读取文档内容（需要授权）
- ✅ 读取图片（Base64 编码）
- ✅ 用户可控的权限管理

### 快速开始

1. 确保 FileSeek Desktop 正在运行
2. 进入 **设置 → MCP 服务**
3. 复制配置到 Claude Desktop 的配置文件
4. 重启 Claude Desktop

详细配置指南：[docs/mcp-setup-guide.md](docs/mcp-setup-guide.md)

## 项目结构

```
FileSeek/
├── backend/           # Python FastAPI 后端
├── desktop/           # Tauri + React 桌面应用
├── services/          
│   └── mcp-service/   # MCP 服务（独立 Python 进程）
└── docs/              # 文档
```

## 开发

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m fileseek.main
```

### Desktop

```bash
cd desktop
pnpm install
pnpm run tauri dev
```

### MCP Service

```bash
cd services/mcp-service
pip install -r requirements.txt
python -m mcp-service
```

## 文档

- [MCP 配置指南](docs/mcp-setup-guide.md)
- [MCP Service README](services/mcp-service/README.md)

## 技术栈

- **Backend**: Python 3.12+, FastAPI, Tortoise ORM, Qdrant
- **Desktop**: Tauri 2, React, TypeScript
- **MCP Service**: Python 3.12+, MCP SDK, httpx

## 授权

本项目为私有项目。

---

**版本**：0.1.0
