## Why

> **Superseded:** `protected-backend-runtime-download` replaces this Nuitka packaging direction. The app now ships PyArmor-protected source and downloads the pinned interpreter, wheels, and model.

release 版首次启动要先下载 python-build-standalone 解释器和 `uv.lock` 里的全部 wheel，再下载模型；后端以明文 `.py` 随安装包分发。把后端用 Nuitka 编译成可执行文件随安装包发布后，首次启动只需下载模型，不再依赖下载来的 Python 环境，源码也不再以明文出现在安装包里。

推理统一使用 CPU。原提案的 CoreML/CUDA/DirectML 加速已放弃：在 Apple Silicon 上用当前的 INT8 动态量化模型实测（512×512 单图），CPU 1052ms，CoreML 8028ms（加载 27s），CoreML MLProgram 约 45s。模型里的 `MatMulInteger`、`DynamicQuantizeLinear` 和不定长维度 CoreML 不支持，图被切成大量碎片在 CPU 和 CoreML 之间往返。GPU 方案还需要用户自装 CUDA/cuDNN，且 Nuitka 编译后能否用 `sys.path` 替换内置 onnxruntime 未经验证。

## What Changes

- 新增 `backend/build_nuitka.py`：用 Nuitka `--standalone` 把后端编译为 `backend/dist/fileseek-backend.dist/`（入口 `fileseek-backend[.exe]`），带上 chromadb、rapidocr 等包的数据文件，排除开发工具。
- `desktop/scripts/stage-backend.mjs` 改为调用编译脚本并把产物目录放进 `src-tauri/resources/backend/`，不再拷贝 `.py`。
- `sidecar.rs` 的 `BackendCommand::production` 直接启动编译产物，不再设置 `PYTHONPATH`。
- **BREAKING**（相对 `commercial-licensing-and-updates` 的 `backend-runtime`）：首次下载只剩模型。删除解释器和 wheel 的下载与安装、`runtime_id` 及其构建期计算；`release/runtime.json` 和 `runtime-sources/*.json` 只保留模型。"修复运行时"改为修复模型。
- CI（macOS arm64、Windows x64）在 `tauri build` 前编译后端，检查产物大小并对 `/health` 冒烟测试。
- ONNX Runtime 保持 `CPUExecutionProvider`，不做硬件检测。删除未接入的 `infrastructure/embedding/onnx_runtime_bootstrap.py`。

不在本次范围：GPU/CoreML 加速、Linux 发布、Developer ID 签名和公证（仍由 `commercial-licensing-and-updates` 8.3/8.4 负责，目前保持 ad-hoc 签名）、镜像测速（模型下载沿用现有的按序镜像回退）。

## Capabilities

### New Capabilities
- `backend-executable`：后端编译为自包含可执行文件，随安装包分发，由桌面端直接启动，不受用户 Python 环境影响；推理只用 CPU。
- `desktop-packaging`：安装包包含编译后的后端、不含 Python 源码和模型文件；首次启动只下载模型。

### Modified Capabilities
（无已归档的 spec。`commercial-licensing-and-updates` 尚未归档的 `backend-runtime` 中"从官方源安装运行时""原子安装运行时""修复运行时"会被本变更取代，归档前需同步修改该 spec。）

## Impact

- 后端：新增 `backend/build_nuitka.py`；`backend/pyproject.toml` 增加 nuitka 开发依赖；删除 `onnx_runtime_bootstrap.py`。
- 桌面端 Rust：`sidecar.rs`、`readiness.rs`、`runtime/{manifest,prepare,install,download,mod,runtime_id}.rs`、`build.rs`。
- 构建与发布：`desktop/scripts/stage-backend.mjs`、`tauri.conf.json`、`release/runtime.json`、`release/build_sources.py`、`desktop/src-tauri/runtime-sources/*.json`、`.github/workflows/release.yml`。
- 体积：安装包和每次应用更新都会包含整个后端（预计 200–350MB 未压缩，实际以 spike 测量为准）。以前只改后端代码的更新只有几 MB，且不变的运行时可以复用；现在每次更新都带完整后端。
- 首次下载：从"解释器 + wheel + 模型"降到只有模型（约 834MB）。
- 构建时间：CI 每个平台增加 Nuitka 编译时间（预计 10–20 分钟，以实测为准）。
