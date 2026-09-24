# FileSeek Desktop

本地语义文件搜索的桌面客户端。基于 Tauri 2 + React + TypeScript，启动时自动拉起 Python 后端并常驻系统托盘。

## 快速开始

```bash
npm install                # 安装前端依赖
npm run tauri dev          # 启动桌面应用（会自动拉起后端）
```

首次运行前确认 `backend/` 已能独立启动（见 [backend/README.md](../backend/README.md) 的“快速开始”），否则托盘会提示后端启动失败。

## 启动方式

### 桌面应用开发模式（推荐）

```bash
npm run tauri dev
```

这会依次做三件事：

1. 编译并运行 Rust 侧的 Tauri 外壳（`src-tauri/`）
2. Rust 侧 `start_backend()`（见 `src-tauri/src/lib.rs`）以 `uv run --directory backend python -m fileseek` 拉起 Python 后端子进程
3. 起一个 Vite dev server（端口固定 `1420`，被占用则直接失败而不是换端口，见 `vite.config.ts`），Tauri 窗口加载它

后端就绪的判定是轮询连接文件（`connection.json`）被重写 + `/health` 返回 `ok`，超时时间 30 秒（`BACKEND_READY_TIMEOUT`）。超时或后端进程提前退出，`start_backend()` 只打印错误、不阻塞窗口打开，此时前端请求会因为拿不到 token 而失败。

### 只跑前端（不涉及 Rust/后端）

```bash
npm run dev            # 纯 Vite dev server，用于调试组件/样式
```

此时没有 Tauri 运行时，`@tauri-apps/api` 的调用会失败，仅适合不依赖后端数据的 UI 开发。

### 生产构建

```bash
npm run build           # tsc + vite build，产出 dist/
npm run tauri build     # 打包安装包（会先跑上面两步，再用 Cargo 编译发布版并打包）
```

打包产物按平台生成安装包（macOS `.dmg`/`.app`，Windows `.msi`/`.exe`，Linux `.deb`/`.AppImage` 等），见 `src-tauri/tauri.conf.json` 的 `bundle.targets`。

### 覆盖后端启动命令

开发或调试时如果不想每次都走 `uv run`（比如后端已经在另一个终端跑着，或想接一个假后端做集成测试），设置环境变量：

```bash
FILESEEK_BACKEND="python -m fileseek --port 8765" npm run tauri dev
```

`FILESEEK_BACKEND` 按空白分词为程序名 + 参数,直接替换默认的 `uv run --directory backend python -m fileseek`(见 `src-tauri/src/sidecar.rs::BackendCommand::resolve`)。留空则用仓库内的 `backend/` 目录。

## 架构

### 进程关系

```
Tauri 主进程 (Rust)
  ├─ 启动时 spawn 后端子进程 (uv run python -m fileseek)
  │    └─ 轮询 connection.json + /health,就绪后记录 port
  ├─ 前端 (WebView) 经 Tauri command 发起请求
  │    connection::api_request → 读 connection.json 取 {port, token}
  │    → 用 token 请求 http://127.0.0.1:{port}/...
  └─ 托盘图标 (tray.rs)
       关闭主窗口 → 隐藏到托盘,后端继续跑
       托盘“退出” → 停止后端子进程,进程退出
```

前端不直接用 `fetch` 打后端接口,而是经 Tauri command `connection::api_request` 转发,原因是 token 只存在于 Rust 侧读到的 `connection.json` 里,不下发给 WebView。

### 生命周期

**启动**:窗口打开与后端启动并行,不互相阻塞。后端没就绪时前端请求会失败,UI 需要自行处理“后端未就绪”的状态,而不是假设启动即可用。

**关闭主窗口**:只隐藏窗口,进程与后端子进程都不退出——本地语义搜索的入库任务可能耗时几分钟,关窗口不该打断它。

**从托盘退出**:触发 `ExitRequested`,调用 `BackendState::stop()`,向后端子进程发 `SIGTERM`(Windows 上直接 kill,无信号等价物)等待优雅关闭,超时 5 秒后强杀。这与后端自身的优雅关闭顺序衔接:先停止取新任务,再等在飞任务落地,最后存索引(见 [backend/README.md](../backend/README.md) “优雅关闭”)。

### 模块结构

```
src/                  # React 前端
├── api/              # 经 Tauri command 调用后端的封装
├── App.tsx
└── test/             # Vitest 环境配置

src-tauri/src/        # Rust 外壳
├── lib.rs            # 应用入口:装配后端启动、窗口事件、托盘
├── sidecar.rs         # 拉起/健康检查/停止后端子进程,不依赖 Tauri 运行时
├── connection.rs      # 读 connection.json,转发带 token 的请求
├── lifecycle.rs       # 关闭窗口时“隐藏到托盘”还是“真正退出”的决策
└── tray.rs            # 托盘图标与菜单
```

## 测试

```bash
npm run test           # Vitest,前端组件与 api 封装
npm run test:watch     # watch 模式
npm run typecheck      # tsc --noEmit
npm run lint           # eslint

cd src-tauri && cargo test   # Rust 侧:sidecar 启动/超时/停止、生命周期决策
```

`sidecar.rs` 的测试用标准库起一个假后端(Python 一行式 HTTP 服务器模拟 `/health` 与连接文件),不依赖真实的 FileSeek 后端,也不需要 GPU 或网络。

## 依赖

| 依赖 | 用途 |
|------|------|
| Tauri 2 | 桌面外壳,WebView + Rust 后端进程管理 |
| React 19 | UI |
| Vite | 前端构建与 dev server |
| ureq | Rust 侧发健康检查请求,同步阻塞式,匹配轮询逻辑 |
| Vitest + Testing Library | 前端测试 |

Rust 侧编译需要本机已装 Rust 工具链与 Tauri 的平台依赖(详见 [Tauri 官方前置条件](https://tauri.app/start/prerequisites/))。运行 `npm run tauri dev` 前还需要 `backend/` 能用 `uv run python -m fileseek` 独立启动。

## 推荐 IDE 配置

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)
