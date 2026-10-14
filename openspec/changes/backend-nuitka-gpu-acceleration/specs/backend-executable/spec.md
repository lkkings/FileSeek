## Purpose

后端编译为自包含的可执行产物，随安装包分发，由桌面端直接启动，不依赖也不受用户 Python 环境影响。推理只使用 CPU。

## ADDED Requirements

### Requirement: 编译为自包含产物

构建脚本 SHALL 把后端编译为包含解释器、全部依赖和应用代码的目录产物，入口为 `fileseek-backend`（Windows 为 `fileseek-backend.exe`）。

#### Scenario: 编译成功
- **WHEN** 运行 `backend/build_nuitka.py`
- **THEN** 生成 `backend/dist/fileseek-backend.dist/`，其中包含入口可执行文件

#### Scenario: 不含源码
- **WHEN** 检查编译产物目录
- **THEN** 其中没有 `fileseek` 包的 `.py` 文件

#### Scenario: 在没有 Python 的机器上运行
- **WHEN** 在未安装 Python 的机器上启动入口可执行文件
- **THEN** 后端正常启动并响应 `/health`

### Requirement: 编译版与源码版行为一致

编译产物 SHALL 提供与 `python -m fileseek` 相同的 API 行为，包括在 spawn 子进程中运行的导入和查询。

#### Scenario: 导入与查询
- **WHEN** 编译版后端导入一张图片后执行一次搜索
- **THEN** 导入任务完成，搜索返回该图片

#### Scenario: 子进程不重复启动服务
- **WHEN** 导入或查询子进程以 spawn 方式启动
- **THEN** 子进程只运行模型 worker，不会再启动一个 HTTP 服务

#### Scenario: 依赖的数据文件可用
- **WHEN** 编译版后端首次初始化向量库和 OCR
- **THEN** chromadb 的迁移文件和 rapidocr 自带的模型、配置都能被加载

### Requirement: 推理只使用 CPU

后端 SHALL 只用 `CPUExecutionProvider` 创建 ONNX Runtime 会话，不做硬件检测，也不下载其他 ONNX Runtime 变体。

#### Scenario: 任意平台
- **WHEN** 在任意平台加载 embedding 模型
- **THEN** 会话的 provider 为 `["CPUExecutionProvider"]`，且没有发起任何 ONNX Runtime 相关的网络请求

### Requirement: 隔离用户 Python 环境

桌面端启动编译版后端时 SHALL 清除 `PYTHONHOME`、`PYTHONPATH`、`VIRTUAL_ENV`、`PYTHONSTARTUP`。

#### Scenario: 用户设置了 Python 环境变量
- **WHEN** 用户环境中设置了 `PYTHONPATH` 或 `VIRTUAL_ENV`
- **THEN** 后端进程环境中没有这些变量，且后端正常启动

### Requirement: 构建声明包含与排除

构建脚本 SHALL 显式包含 `fileseek` 包以及 chromadb、rapidocr_onnxruntime 的数据文件，并排除 pytest、mypy、ruff。

#### Scenario: 开发工具被排除
- **WHEN** 编译完成
- **THEN** 产物目录中没有 pytest、mypy、ruff 的模块

### Requirement: 产物体积上限

构建 SHALL 在产物目录总大小超过设定上限时失败。上限由首次实测体积加 15% 余量确定，并写在构建脚本中。

#### Scenario: 超出上限
- **WHEN** 产物目录总大小超过上限
- **THEN** 构建脚本以非零状态退出并打印实际大小和上限

### Requirement: macOS 产物可执行

在 macOS 上，编译产物中的所有 Mach-O 文件 SHALL 至少带 ad-hoc 签名。

#### Scenario: Apple Silicon 上运行
- **WHEN** 在 Apple Silicon 上从安装后的应用中启动后端
- **THEN** 进程正常启动，没有因代码签名被系统终止
