## 1. 可行性 spike（macOS 本机）

- [x] 1.1 `backend/pyproject.toml` 的 dev 依赖加入固定版本的 `nuitka`，`uv sync` 通过。验证：`uv run python -m nuitka --version` 输出版本号
- [x] 1.2 新建 `backend/build_nuitka.py`：`--standalone`、`--include-package=fileseek`、`--include-package-data=chromadb,rapidocr_onnxruntime`、`--nofollow-import-to=pytest,mypy,ruff,IPython`，输出到 `backend/dist/fileseek-backend.dist/`，入口名 `fileseek-backend`。验证：脚本执行成功，入口文件存在（备注：第一次编译的产物启动即崩，chromadb 按字符串 `import_module("chromadb.api.rust")`；另外整包加入 `chromadb`、`uvicorn`、`tortoise.backends.sqlite`，三者都按名字加载实现。本机全量编译约 25 分钟）
- [x] 1.3 启动编译产物，确认 `/health` 返回成功；记录启动到就绪的耗时。验证：耗时写进本任务备注（备注：`scripts/smoke_compiled.py` 通过。新产物第一次启动到连接文件出现 9.9s（macOS 首次校验新二进制），之后 0.5–0.9s）
- [x] 1.4 用编译产物真实导入一张图片并搜索，确认 spawn 子进程只跑 worker、没有第二个 uvicorn。验证：任务完成、搜索命中，进程列表中只有一个监听端口的进程（备注：导入 14.4s 完成；导入和查询两个 worker 子进程，只有主进程监听端口；搜索命中该图）
- [x] 1.5 确认 chromadb 迁移、rapidocr 模型和配置在编译版中可加载（导入一张带文字的图片触发 OCR）。验证：OCR 文本可搜到（备注：OCR 分片为 "INVOICE ZEBRA 4821"，搜 "ZEBRA" 命中）
- [x] 1.6 检查产物里的 Mach-O 是否已 ad-hoc 签名；没有则在脚本末尾补 `codesign -s - --force`。验证：`codesign -v` 对目录中所有 Mach-O 通过（备注：Nuitka 已签，229 个文件全部通过，脚本无需补签）
- [x] 1.7 设置 `PYTHONPATH`、`VIRTUAL_ENV` 指向无关目录后启动编译产物，记录是否受影响。验证：结论写进本任务备注（备注：三个变量连同 `PYTHONHOME` 指向含"坏" `fastapi`/`fileseek` 包的目录，产物照常启动，未加载这些包。sidecar 仍清除这些变量）
- [x] 1.8 测量产物目录总大小，把"实测值 × 1.15"写进 `build_nuitka.py` 作为上限，超出时以非零状态退出。验证：把上限临时调小后脚本失败并打印实际值和上限（备注：实测 629 MB，上限 725 MB；上限 100 时 `main()` 返回 1）
- [x] 1.9 产物中没有 `fileseek` 的 `.py`，也没有 pytest、mypy、ruff 模块。验证：`find` 检查为空（备注：产物中 `.py` 为 0 个）

## 2. 后端清理

- [x] 2.1 删除未接入的 `infrastructure/embedding/onnx_runtime_bootstrap.py`，确认 `jina_clip_v2.py` 仍只用 `CPUExecutionProvider`。验证：`ruff`、`mypy`、`pytest` 通过
- [x] 2.2 `backend/README` 或脚本文档说明编译方法、前置条件（C 编译器）和产物位置。验证：按说明在干净 checkout 中能编译成功

## 3. 打包

- [x] 3.1 `desktop/scripts/stage-backend.mjs` 改为调用 `uv run --directory backend python build_nuitka.py`，把 `backend/dist/fileseek-backend.dist/` 整个拷到 `src-tauri/resources/backend/`；编译失败时打印错误并以非零状态退出。验证：`pnpm run build` 后 `resources/backend/fileseek-backend` 存在，且目录下无 `.py`
- [x] 3.2 Unix 上确保入口文件权限为 755。验证：`stat` 检查
- [x] 3.3 更新 `build.rs` 中 `ensure_backend_resource_dir` 的注释。验证：`cargo build` 通过

## 4. Rust：启动编译后的后端

- [x] 4.1 `BackendCommand::production(backend_exe, model_cache_dir)`：无参数，`env` 为 `EMBEDDING_MODEL_CACHE_DIR`、`PYTHONUTF8=1`，`env_remove` 为 `PYTHONHOME`、`PYTHONPATH`、`VIRTUAL_ENV`、`PYTHONSTARTUP`；更新 `production_command_isolates_the_interpreter` 测试。验证：`cargo test sidecar` 通过
- [x] 4.2 `readiness.rs`：`BackendSource::Runtime` 改为持有后端可执行文件路径；release 版取 `<resource_dir>/backend/fileseek-backend[.exe]`，`FILESEEK_DEV_USE_RUNTIME=1` 时取 `backend/dist/fileseek-backend.dist/` 下的产物。验证：`cargo test readiness` 通过

## 5. Rust：首次启动只下载模型

- [x] 5.1 `runtime/manifest.rs` 删除 `PythonArchive` 和 wheel 列表，只解析模型。验证：`cargo test manifest` 通过
- [x] 5.2 `runtime/prepare.rs`：`installed` 只检查模型，`Ready` 去掉 `python`，`prepare` 只下载模型。验证：`cargo test prepare` 通过，包括"从无到有安装"的用例
- [x] 5.3 `runtime/install.rs` 删除 `install_runtime` 及解释器相关的 `Layout` 方法，保留模型安装标记。验证：`cargo test install` 通过
- [x] 5.4 删除 `runtime_id.rs`、`EXPECTED_RUNTIME_ID`、`build.rs` 的 `emit_runtime_id` 和 `release/runtime_id.py`；`mod.rs` 的模块说明改为只描述模型。验证：`cargo build` 和 `cargo test` 通过
- [x] 5.5 启动时删除数据目录下的旧 `runtime/` 目录，失败只记日志。验证：新增单测：目录存在时被删除、删除失败不报错
- [x] 5.6 "修复运行时"改为重新下载模型；检查前端相关文案（`i18n`）是否还提到 Python 运行时，有则改为模型。验证：`cargo test` 与 `pnpm test` 通过
- [x] 5.7 `release/runtime.json` 删除 `python_version`、`pbs_release`、`pbs_sha256` 和 `python`、`pypi` 镜像；`release/build_sources.py` 只生成模型清单并重新生成 `runtime-sources/*.json`。验证：`build_sources.py --check` 通过，`release/tests` 通过

## 6. CI

- [x] 6.1 `release.yml` 在 `tauri build` 前确保 Nuitka 可用（随 dev 依赖安装），Windows 上确认有 MSVC。验证：工作流语法检查通过
- [x] 6.2 "Runtime sources match uv.lock" 改为检查模型清单。验证：本地执行同一命令通过
- [x] 6.3 编译后启动产物、请求 `/health`，失败则任务失败；体积超限由 `build_nuitka.py` 让任务失败。验证：本地按 CI 命令执行一遍通过
- [x] 6.4 用 `actions/cache` 缓存 Nuitka 的编译缓存目录。验证：工作流语法检查通过
- [x] 6.5 更新 `release.yml` 顶部注释：后端随安装包发布，首次只下载模型。验证：人工检查

## 7. 端到端验证

- [x] 7.1 本机 `pnpm tauri build` 出 DMG，`FileSeek.app/Contents/Resources/backend/` 只有编译产物。验证：`find` 检查无 `.py`、无 `.onnx` 模型
- [ ] 7.2 用全新数据目录启动 release 版：只下载模型，完成后能导入和搜索。验证：下载列表只有模型文件
- [ ] 7.3 数据目录中有旧 `runtime/` 时启动，目录被删除，应用正常就绪。验证：手工检查
- [ ] 7.4 CI 两个平台构建成功，产出 DMG 和 NSIS 安装包。验证：Actions 运行通过
- [ ] 7.5 Windows 机器上安装并完成导入和搜索。验证：手工确认（本机无法验证）

## 8. 关联变更

- [x] 8.1 在 `commercial-licensing-and-updates` 的 `backend-runtime` spec 中标注被本变更取代的需求（从官方源安装运行时、原子安装运行时、修复运行时），并更新其 9.6 中关于 `runtime_id` 变化的测试项。验证：`openspec validate` 两个变更都通过
