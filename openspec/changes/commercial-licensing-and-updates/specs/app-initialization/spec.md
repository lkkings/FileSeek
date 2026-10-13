## Purpose

驱动应用从启动到主界面可用的流程：先确认许可有效，再准备后端运行时并启动后端，向用户如实展示进度和错误，并在就绪后提供可选的系统集成设置。

## ADDED Requirements

### Requirement: 就绪状态机
系统 SHALL 在每次启动时运行就绪状态机：`license_check → (activation) → checking → (space_check → downloading → verifying → installing) → starting → ready`。`license_check` 判定无有效许可时 SHALL 进入 `activation`，激活成功后继续 `checking`。运行时相关的任一步失败都 SHALL 进入 `failed`。状态 SHALL 通过 Tauri 事件推送给前端。

#### Scenario: 已激活、已安装用户的普通启动
- **WHEN** 本地许可有效，运行时和模型都已安装，应用启动
- **THEN** 状态依次为 `license_check`、`checking`、`starting`、`ready`，不显示激活界面和下载步骤

#### Scenario: 首次启动
- **WHEN** 新安装的应用首次启动，没有许可，运行时不存在
- **THEN** 状态进入 `activation`；用户激活成功后依次经过 `checking`、`space_check`、`downloading`、`verifying`、`installing`、`starting`，最终到达 `ready`

#### Scenario: 激活前不下载
- **WHEN** 状态为 `activation`
- **THEN** 系统不请求运行时清单，不下载任何运行时或模型文件

### Requirement: 初始化界面
激活后、运行时就绪前，系统 SHALL 显示初始化页面，而不是文件库界面。页面 SHALL 显示当前步骤，以及已下载/总量、速度和预计剩余时间。用户 SHALL 可以把窗口最小化到托盘，下载在后台继续进行。

#### Scenario: 下载进度
- **WHEN** 正在下载运行时
- **THEN** 页面显示类似"下载运行时 256MB / 2.4GB · 2.5 MB/s · 约 14 分钟"

#### Scenario: 后台下载完成
- **WHEN** 用户把初始化窗口最小化到托盘，随后下载完成、后端就绪
- **THEN** 系统发送通知"FileSeek 已就绪"，点击后打开主界面

### Requirement: 失败状态可重试
`failed` 状态 SHALL 显示失败步骤、可读的错误原因、"重试"按钮，以及日志文件路径。重试 SHALL 从失败的步骤继续，而不是从头开始。

#### Scenario: 网络断开
- **WHEN** 下载过程中网络断开，重试耗尽
- **THEN** 页面显示"网络连接失败"和"重试"按钮；网络恢复后点击重试，从断点继续下载

### Requirement: 目录不可写时的提示
系统 SHALL 在 `space_check` 阶段检查 `<config_dir>` 和 `<data_dir>` 是否可写。不可写时 SHALL 进入 `failed`，并显示无法写入的具体路径。

#### Scenario: 数据目录无写权限
- **WHEN** `<data_dir>` 因权限问题无法创建
- **THEN** 页面显示"无法写入 <路径>，请检查该目录的权限"

### Requirement: 就绪后的可选设置
系统 SHALL 在首次进入主界面时，显示一次可选设置对话框（开机自启、右键菜单集成），所有选项默认不勾选。用户关闭对话框后 SHALL NOT 再次自动弹出；相同设置在设置页中可用。

#### Scenario: 首次进入主界面
- **WHEN** 首次进入 `ready`
- **THEN** 显示"建议设置"对话框，选项均未勾选，可以跳过
