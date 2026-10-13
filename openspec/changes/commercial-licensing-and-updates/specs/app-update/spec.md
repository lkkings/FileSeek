## Purpose

通过 tauri-plugin-updater 从自部署 Keygate 的更新 feed 检查、下载并安装经过签名的应用更新，支持强制更新，并在需要时先更新后端运行时，保证新版本启动时运行时已经就绪。

## ADDED Requirements

### Requirement: 定期检查更新
系统 SHALL 在许可有效时于启动 30 秒后检查更新，之后每 24 小时检查一次，另外支持在设置中手动检查。请求地址 SHALL 为 `{base_url}/api/v1/releases/{product_slug}/upgrade.json?platform=<平台>-<架构>`，并通过 `X-License-Key` 请求头携带许可证密钥；许可证密钥 SHALL NOT 出现在 URL 中。

#### Scenario: 有新版本
- **WHEN** Keygate feed 返回比当前版本新的 release
- **THEN** 设置页显示"有新版本 x.y.z"，并弹出一次提示，可以选择"稍后"

#### Scenario: 更新服务不可达
- **WHEN** 请求 feed 超时或失败
- **THEN** 系统记录日志，不打扰用户，下一个周期再试

#### Scenario: feed 拒绝
- **WHEN** feed 返回 `401`（例如门控 feed 下更新期已过）
- **THEN** 系统视为"暂无可用更新"，不显示错误

### Requirement: 强制更新
系统 SHALL 从 feed 响应中读取 `minimum_supported_version` 和 `minimum_supported_message`。当前版本低于 `minimum_supported_version` 时，系统 SHALL 在主界面显示不可关闭的横幅，内容为 `minimum_supported_message`（缺省为"当前版本已不再受支持，请更新"），直到更新完成。强制更新 SHALL NOT 禁用任何功能。

#### Scenario: 当前版本低于最低支持版本
- **WHEN** 当前版本 1.2.0，feed 返回 `minimum_supported_version` 为 1.3.0
- **THEN** 主界面显示不可关闭的横幅和 Keygate 中填写的消息，其他功能照常可用

#### Scenario: 没有设置最低版本
- **WHEN** feed 响应中没有 `minimum_supported_version`
- **THEN** 按普通更新处理

### Requirement: 签名校验与安装
系统 SHALL 通过 tauri-plugin-updater 下载更新包，安装前用内置的 Keygate 更新公钥校验签名。签名不匹配时 SHALL NOT 安装。下载阶段 SHALL 显示进度，并允许取消。

#### Scenario: 签名不匹配
- **WHEN** 下载的更新包签名无法被更新公钥验证
- **THEN** 系统丢弃更新包，提示"更新包校验失败"，当前版本不受影响

#### Scenario: 取消下载
- **WHEN** 用户在下载过程中点击取消
- **THEN** 下载停止，当前版本继续运行

### Requirement: 依赖变化的版本
Keygate SHALL 只承载应用本体。新版本的 `runtime_id` 与已安装的运行时相同时，重启后 SHALL 直接使用它；不同时，新版本首次启动 SHALL 显示初始化页，从官方源下载并安装新运行时（按 backend-runtime 的流程），并保留旧运行时用于回滚。

#### Scenario: 只改了后端代码的版本
- **WHEN** 新版本的 `runtime_id` 与当前一致
- **THEN** 更新只下载应用更新包；重启后不显示初始化页

#### Scenario: 依赖升级的版本
- **WHEN** 新版本升级了 torch，`runtime_id` 发生变化
- **THEN** 重启后显示初始化页，下载并安装新运行时后进入主界面

### Requirement: 更新日志
系统 SHALL 把每次检查结果、下载、安装和失败记录到 `<config_dir>/logs/update.log`，每条带时间戳、当前版本和目标版本。日志 SHALL NOT 包含许可证密钥。

#### Scenario: 记录失败
- **WHEN** 更新安装失败
- **THEN** 日志中有一条包含失败原因、当前版本和目标版本的记录，不含许可证密钥
