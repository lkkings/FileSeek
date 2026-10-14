## Context

现在 release 版的后端启动链路：安装包带 `resources/backend/fileseek/*.py`；首次启动 `readiness.rs` 调 `runtime::prepare` 下载 python-build-standalone、`uv.lock` 的全部 wheel 和模型，安装到 `<data>/runtime/<runtime_id>/`；`sidecar.rs` 用 `BackendCommand::production(python, backend_src, model_cache_dir)` 以 `PYTHONPATH` 启动 `python -m fileseek`。`runtime_id` 由 `build.rs` 从 `uv.lock` 和 `release/runtime.json` 算出，只改后端代码的更新可以复用已装的运行时。

导入和查询模型跑在 `multiprocessing.get_context("spawn")` 子进程里，`__main__.py` 已调用 `freeze_support()`。MCP 服务已经用 PyInstaller 打成单文件 sidecar。

## Goals / Non-Goals

**Goals:**
- 后端编译为自包含产物，随安装包发布，release 版首次启动只下载模型。
- 安装包里不出现 `.py` 源码。
- 编译版与源码版 API 行为一致，包括 spawn 子进程。
- 开发模式（`pnpm tauri dev` 用 `uv run`）不变。

**Non-Goals:**
- GPU、CoreML 加速：实测 CoreML 比 CPU 慢 8 倍以上（见 proposal）。
- Linux 发布、Developer ID 签名与公证。
- 代码加密：Nuitka 只是编译成本地代码，不是混淆。
- 镜像测速：模型下载沿用 `runtime.json` 里按序回退的镜像。

## Decisions

### 1. Nuitka `--standalone`，不用 `--onefile`

`--onefile` 每次启动先解压到临时目录；spawn 子进程会重新执行入口，导入和查询子进程各自再触发一次，加上空闲退出后的重启，解压开销会反复出现。`--standalone` 产出一个目录，Tauri 通过 `bundle.resources` 原样打包，启动没有解压步骤。

考虑过 PyInstaller（MCP 服务在用）：构建快，但同样有 onedir/onefile 的取舍，且字节码容易被还原。保留 Nuitka 的前提是 spike（任务 1）能编译成功；如果 chromadb 或 onnxruntime 在 Nuitka 下无法解决，再回到 PyInstaller onedir，sidecar 和打包部分的设计不变。

### 2. 产物布局

```
backend/dist/fileseek-backend.dist/
  fileseek-backend[.exe]      入口
  *.so / *.dll / *.pyd        扩展模块与依赖库
  chromadb/... rapidocr_onnxruntime/...  数据文件
```

`stage-backend.mjs` 把整个目录拷到 `src-tauri/resources/backend/`，安装后位于 `<resource_dir>/backend/fileseek-backend[.exe]`。`tauri.conf.json` 的 `resources` 映射保持 `resources/backend/ -> backend/` 不变。

### 3. 包含与排除

- `--include-package=fileseek`：路由、ORM 模型等有按名字加载的情况，整包包含比逐个追踪可靠。
- `--include-package-data=chromadb,rapidocr_onnxruntime`：chromadb 有 16 个 `.sql` 迁移文件，rapidocr 自带 3 个 `.onnx` 和 `config.yaml`。
- `--nofollow-import-to=pytest,mypy,ruff,IPython`。
- 其余依赖靠 Nuitka 跟踪导入；spike 中缺什么补什么，并记录在脚本注释里。

原 spec 里的 `sqlalchemy` 删除：后端用的是 tortoise-orm。

### 4. 去掉解释器和 wheel 的下载，只保留模型

后端随安装包发布后，`runtime_id`、`PythonArchive`、wheel 列表和 `install_runtime` 都不再需要：

- `manifest`：只解析 `model` 段。
- `prepare::installed` 只检查模型；`Ready` 去掉 `python`。
- `readiness` 的 `BackendSource::Runtime` 改成持有后端可执行文件路径。开发模式下的 `FILESEEK_DEV_USE_RUNTIME=1` 改为"用 `backend/dist/` 里已编译的产物 + 下载模型"，方便本地调试 release 路径。
- `build.rs` 不再计算 `FILESEEK_RUNTIME_ID`；`runtime_id.rs` 与 `release/runtime_id.py` 删除。
- `release/build_sources.py` 只生成模型文件清单；CI 里"Runtime sources match uv.lock"改为检查模型清单。
- 已安装用户磁盘上旧的 `<data>/runtime/` 目录：启动时删除，失败只记日志。

### 5. 启动命令

`BackendCommand::production(backend_exe, model_cache_dir)`：`program` 为可执行文件，无参数；`env` 只有 `EMBEDDING_MODEL_CACHE_DIR` 和 `PYTHONUTF8=1`；`env_remove` 保留 `PYTHONHOME`、`PYTHONPATH`、`VIRTUAL_ENV`、`PYTHONSTARTUP`，防止用户环境变量影响内嵌解释器（是否真有影响在 spike 中验证，不影响也保留，代价为零）。

### 6. 签名

macOS 继续 ad-hoc 签名。Tauri 只给主程序和 `externalBin` 签名，`resources` 里的可执行文件和 `.so` 不会被签，Apple Silicon 要求代码至少 ad-hoc 签名才能执行。Nuitka 在 macOS 上会对产物做 ad-hoc 签名；spike 中确认，若没有则在 `build_nuitka.py` 末尾对目录里所有 Mach-O 跑 `codesign -s - --force`。

## Risks / Trade-offs

- **Nuitka 编译不过某个依赖**（chromadb 的 Rust 绑定、onnxruntime、av、cv2）→ 任务 1 先做 spike；不行就换 PyInstaller onedir（决策 1）。
- **体积**：onnxruntime 75MB、cv2 119MB、chromadb 绑定 49MB、av 44MB、numpy 26MB，合计已超 300MB，原 spec 的 250MB 上限大概率达不到 → 上限按 spike 实测值加 15% 余量设定，写进 CI。
- **每次更新都带完整后端**：以前只改后端代码的更新只有几 MB，现在每次几百 MB → 接受；更新包是压缩的 `.app.tar.gz`/NSIS，实际下载小于未压缩体积。
- **构建时间**：CI 每平台多 10–20 分钟 → 用 Nuitka 的 ccache 缓存（`actions/cache` 缓存 `~/.cache/Nuitka`）。
- **spawn 子进程在编译产物里重启入口** → `freeze_support()` 已存在；spike 中真实导入一张图、跑一次查询来验证，不能只测 `/health`。
- **Windows 未在本机验证**：只能靠 CI 构建和冒烟测试，运行时行为需要在 Windows 机器上手工确认。

## Migration Plan

1. spike：本机 macOS 编译、启动、导入、查询，记录体积和启动时间。
2. 打包与 Rust 改动，本机 `tauri build` 出 DMG，全新数据目录下验证首次只下载模型。
3. CI 两个平台构建；Windows 产物手工验证。
4. 回滚：恢复 `stage-backend.mjs` 拷源码和运行时下载，相关提交可整体 revert。
