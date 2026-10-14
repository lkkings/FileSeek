## Purpose

> **Superseded:** `protected-backend-runtime-download` ships PyArmor-protected backend source and downloads the interpreter, wheels, and model on first run.

桌面安装包包含编译后的后端，不含 Python 源码和模型文件；release 版首次启动只下载模型。

## ADDED Requirements

### Requirement: 安装包包含编译后的后端

安装包 SHALL 在资源目录的 `backend/` 下包含编译产物，并 SHALL NOT 包含后端的 `.py` 源码。

#### Scenario: macOS
- **WHEN** 检查 `FileSeek.app`
- **THEN** `Contents/Resources/backend/fileseek-backend` 存在且可执行，`Contents/Resources/backend/` 下没有 `.py` 文件

#### Scenario: Windows
- **WHEN** 检查 NSIS 安装后的目录
- **THEN** `backend/fileseek-backend.exe` 存在，`backend/` 下没有 `.py` 文件

#### Scenario: 不含模型
- **WHEN** 检查安装包
- **THEN** 其中没有 jina-clip-v2 的 `.onnx` 模型文件

### Requirement: release 版直接启动编译后的后端

release 版 SHALL 以资源目录中的 `fileseek-backend` 作为后端进程启动，参数为空，并通过 `EMBEDDING_MODEL_CACHE_DIR` 传入模型目录。

#### Scenario: 启动后端
- **WHEN** release 版模型已就绪
- **THEN** 桌面端启动 `<resource_dir>/backend/fileseek-backend[.exe]`，后端在连接文件中写入地址，状态变为就绪

#### Scenario: 开发模式不变
- **WHEN** 以 debug 构建运行且未设置 `FILESEEK_BACKEND`、`FILESEEK_DEV_USE_RUNTIME`
- **THEN** 后端仍以 `uv run python -m fileseek` 从源码启动

### Requirement: 首次启动只下载模型

release 版首次启动 SHALL 只下载模型文件，不下载 Python 解释器或 wheel。

#### Scenario: 全新安装
- **WHEN** 在没有数据目录的机器上首次启动 release 版
- **THEN** 下载列表只包含模型文件，完成并校验 sha256 后后端启动

#### Scenario: 模型已存在
- **WHEN** 模型已下载并校验过
- **THEN** 启动时不发起任何下载

#### Scenario: 修复
- **WHEN** 用户在就绪失败后选择修复
- **THEN** 重新下载并校验模型文件

### Requirement: 清理旧运行时

升级到本版本后，桌面端 SHALL 删除数据目录中旧版本安装的 Python 运行时目录。

#### Scenario: 旧运行时存在
- **WHEN** 数据目录中存在 `runtime/` 目录
- **THEN** 启动时删除该目录；删除失败只记录日志，不影响启动

### Requirement: CI 构建编译后的后端

发布流程 SHALL 在每个发布平台（macOS arm64、Windows x64）上先编译后端，再构建安装包，并对编译产物做冒烟测试。

#### Scenario: 冒烟测试
- **WHEN** CI 编译完后端
- **THEN** 启动产物并请求 `/health`，得到成功响应，否则任务失败

#### Scenario: 体积检查
- **WHEN** 编译产物超过体积上限
- **THEN** CI 任务失败
