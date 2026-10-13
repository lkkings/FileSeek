## Purpose

在生产环境中下载、校验、安装并启动 FileSeek 后端运行时（Python + 依赖）和模型文件，并由桌面应用管理后端进程的生命周期。

## ADDED Requirements

### Requirement: 从官方源安装运行时
系统 SHALL 从官方源或其镜像下载 Python 解释器（python-build-standalone）、`backend/uv.lock` 锁定的每个依赖 wheel 和固定 revision 的模型文件，SHALL NOT 从 FileSeek 自有的服务器或 Keygate 下载这些文件。要下载的文件及其 sha256 SHALL 在构建时确定并编译进应用。每个文件 SHALL 依次尝试其各个地址；任何来源的文件都 SHALL 按 sha256 校验后才使用。依赖 SHALL 用该解释器自带的 pip 离线安装（只安装下载并校验过的文件，不解析依赖）。

#### Scenario: 镜像不可达
- **WHEN** 第一个镜像地址连接失败
- **THEN** 系统改用下一个地址（最终是官方源）继续下载，不报错

#### Scenario: 镜像返回了不同的文件
- **WHEN** 某个镜像返回的文件 sha256 与编译进应用的不一致
- **THEN** 系统丢弃该文件，改用下一个地址；所有地址都不一致时，初始化进入失败状态，提示"文件校验失败"

#### Scenario: 不支持的平台
- **WHEN** 应用没有当前平台的下载清单
- **THEN** 初始化进入失败状态，提示"当前平台暂不支持"，不发起任何下载

### Requirement: 安装前的磁盘空间检查
系统 SHALL 在下载前，按目标卷分别检查可用空间是否不少于"下载大小 + 解压后大小 + 10%"。空间不足时 SHALL NOT 开始下载。

#### Scenario: 空间不足
- **WHEN** 运行时包下载 600MB、解压后 1.8GB，目标卷可用空间 2.4GB
- **THEN** 系统计算需要约 2.64GB，不开始下载，显示所需空间、可用空间和目标路径

### Requirement: 可续传的下载
系统 SHALL 把下载写入 `.part` 临时文件，中断后用 HTTP Range 从已下载位置继续。每个文件失败后 SHALL 按 1s、2s、4s 退避重试最多 3 次。

#### Scenario: 应用关闭后续传
- **WHEN** 运行时包下载到 40% 时应用被关闭，之后再次启动
- **THEN** 系统从已下载的字节处继续下载，而不是从头开始

#### Scenario: 服务端不支持续传
- **WHEN** 服务端对 Range 请求返回完整内容（200）
- **THEN** 系统丢弃 `.part` 并从头下载

#### Scenario: 重试耗尽
- **WHEN** 同一文件连续失败 3 次
- **THEN** 初始化进入失败状态，显示错误原因、"重试"按钮和日志路径；已下载的 `.part` 保留，供下次续传

### Requirement: 完整性校验
系统 SHALL 在每个文件下载完成后计算 SHA256 并与清单比对。只有校验通过的文件才能被 rename 为正式文件名。

#### Scenario: 校验和不匹配
- **WHEN** 下载完成的文件 SHA256 与清单不一致
- **THEN** 系统删除该 `.part`，从头重新下载该文件，并计入重试次数

### Requirement: 原子安装运行时
系统 SHALL 把运行时包解压到临时目录，确认关键文件（`bin/python` 或 `python.exe`）存在后，再 rename 为 `<data_dir>/runtime/<runtime_id>/`，最后写入内容为清单 sha256 的 `.complete` 标记。系统 SHALL 保留上一个运行时版本，并删除更早的版本。

#### Scenario: 解压过程中断
- **WHEN** 解压过程中应用被强制退出
- **THEN** 下次启动时，正式目录不存在或没有 `.complete`，系统清理临时目录并重新安装

#### Scenario: 已安装的运行时
- **WHEN** 应用启动，所需 `runtime_id` 的目录存在、`.complete` 存在且其中记录的解释器文件存在
- **THEN** 系统跳过下载和安装，不获取清单，不重新计算整个目录的哈希（离线也能启动）

### Requirement: 预下载模型文件
系统 SHALL 按清单把模型文件下载到 `embedding_model_cache_dir` 的现有布局（`model_quantized.onnx`、`tokenizer/` 下的文件），采用与运行时包相同的 `.part`、校验、rename 流程。

#### Scenario: 模型在后端启动前就绪
- **WHEN** 初始化完成，后端首次加载 jina-clip-v2
- **THEN** `ensure_model_cached` 发现所有文件已存在，不访问 Hugging Face

### Requirement: 启动和停止后端进程
桌面应用 SHALL 只在许可有效（见 licensing-activation）且运行时就绪后启动后端：生产构建用清单中记录的运行时解释器执行 `-m fileseek`，`PYTHONPATH` 指向随应用分发的后端代码，`EMBEDDING_MODEL_CACHE_DIR` 指向已安装的模型目录；debug 构建同样由桌面应用启动后端，用 `uv run`；两者都可被 `FILESEEK_BACKEND` 覆盖。后端 SHALL 运行在独立进程组中，并记录在 pidfile 里；下次启动时，若 pidfile 指向的进程组仍是 FileSeek 后端，系统 SHALL 先结束它。系统 SHALL 等待 `connection.json` 被重写且 `/health` 返回成功后，才认为后端就绪。停止后端时 SHALL 先请求优雅停止（Unix 发 SIGTERM；Windows 调用后端 `POST /shutdown`，以 `connection.json` 中的 token 鉴权），15 秒后仍未退出则强制终止。强制终止时限 SHALL 大于后端等待在飞任务的时限，使在飞任务能落地或被放回队列。

#### Scenario: 正常启动
- **WHEN** 运行时已就绪，应用启动
- **THEN** 系统启动后端，`/health` 成功后进入主界面

#### Scenario: 无有效许可
- **WHEN** 应用启动时没有有效许可
- **THEN** 系统不启动后端，后端端口上没有 FileSeek 进程监听

#### Scenario: 应用退出
- **WHEN** 用户从托盘退出应用
- **THEN** 后端进程（包括模型子进程）在 15 秒内结束，没有残留进程

#### Scenario: 退出时有在飞任务
- **WHEN** 正在导入一个文件时用户退出应用（任一平台）
- **THEN** 该任务在后端 drain 时限内完成，或被放回 `queued`；下次启动后继续，不会停留在 `processing`

#### Scenario: 应用被强制结束
- **WHEN** 应用被直接杀掉（如 `tauri dev` 重建），没有机会停止后端，之后再次启动
- **THEN** 新的应用实例先结束遗留的后端进程组，再启动新的后端

### Requirement: 修复运行时
后端启动后 30 秒内连续崩溃 2 次时，系统 SHALL 提示用户修复运行时。用户确认后，系统 SHALL 删除当前运行时的 `.complete`，并重新执行下载和安装流程。

#### Scenario: 运行时文件损坏
- **WHEN** 运行时中的某个动态库被删除，后端两次启动都立即崩溃
- **THEN** 系统显示"后端无法启动，是否修复运行时？"，确认后重新下载并安装运行时
