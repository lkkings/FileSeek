# FileSeek

本地优先的语义文件检索桌面应用。右键把文件收入受管理的文件库，用自然语言检索文档、图片与视频，视频可定位到出现目标内容的片段。全部 AI 推理在本机完成。

## 仓库结构

| 目录 | 内容 |
|------|------|
| `backend/` | Python 后端服务：入库、索引、检索、任务队列 |
| `desktop/` | Tauri + React 桌面客户端 |
| `extensions/windows/` | Windows 资源管理器右键扩展（Rust） |
| `extensions/macos/` | macOS Finder 扩展 |
| `extensions/linux/` | Linux 文件管理器适配（Nautilus / Dolphin / Thunar） |
| `tests/` | 跨组件的端到端测试 |
| `openspec/` | 规格与变更计划 |

## 开发环境

后端依赖通过 [uv](https://docs.astral.sh/uv/) 管理，无需预装系统 Python：

```bash
cd backend
uv sync --extra dev
uv run pytest
```

设计决策与行为契约见 `openspec/changes/add-semantic-file-library/`。
