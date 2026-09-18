# 平台原生右键扩展

三个平台各自的「添加到 FileSeek 库」入口。扩展保持极薄：判断选中项是否含受支持文件、向本地后端发一个请求、立刻交回控制权。不加载任何 AI 依赖。

| 目录 | 平台 | 机制 |
|------|------|------|
| `windows/` | Windows | `IExplorerCommand`（sparse MSIX 注册），Rust |
| `macos/` | macOS | Finder Sync Extension (`FIFinderSync`) |
| `linux/` | Linux | Nautilus 扩展、Dolphin service menu、Thunar custom action |

三者最终都调用同一个 `fileseek add` CLI 入口。任何平台的扩展不可用时，CLI 与「拖拽到窗口」入口仍然可用。
