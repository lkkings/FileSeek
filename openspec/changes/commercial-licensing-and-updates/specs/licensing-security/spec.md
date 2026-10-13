## Purpose

保证本地许可只能来自 Keygate 签发、只对本机有效、不能通过修改配置或系统时间绕过，并约束许可相关信息的存储与传输方式。

## ADDED Requirements

### Requirement: 构建时配置
Keygate 地址（`https://licenses.tuodianyuan.com`）、产品 slug（`fileseek`）、许可公钥、更新公钥、运行时公钥 SHALL 在构建时确定并编译进应用，安装后 SHALL NOT 能通过配置文件、环境变量或命令行参数修改。release 构建缺少任一项时 SHALL 构建失败。

#### Scenario: 用户修改配置
- **WHEN** 用户在 `<config_dir>` 下创建或修改任何文件，试图把许可服务器指向别的地址
- **THEN** 应用仍然只访问构建时配置的 Keygate 地址

#### Scenario: 构建配置缺失
- **WHEN** CI 在没有设置许可公钥的情况下执行 release 构建
- **THEN** 构建失败并指出缺少的配置项

### Requirement: Token 验签
系统 SHALL 把 token 按第一个 `.` 拆成 payload 和 signature，用内置的 Ed25519 许可公钥校验 signature 对 payload 原始字符串的签名，验签通过后才解码 payload。验签失败、`pid` 与本产品不符、或 `did` 与本机 identifier 不符时，SHALL 视为无有效许可。

#### Scenario: 篡改 payload
- **WHEN** 用户修改 `license.json` 中 token 的 payload（例如延后 `exp`）
- **THEN** 验签失败，显示激活界面，原因为"许可无效"

#### Scenario: 复制到另一台机器
- **WHEN** 把 `license.json` 复制到另一台机器
- **THEN** `did` 不符，显示激活界面，原因为"许可无效"

#### Scenario: 其他产品的 token
- **WHEN** token 能用同一把公钥验签，但 `pid` 属于 Keygate 上的另一个产品
- **THEN** 视为无有效许可

### Requirement: 设备标识
系统 SHALL 以 hex(SHA256(盐 + 机器 ID)) 作为 identifier，机器 ID 取 macOS `IOPlatformUUID`、Windows `MachineGuid`、Linux `/etc/machine-id`。同一台机器上 identifier SHALL 保持稳定。系统 SHALL NOT 把序列号、MAC 地址或安装路径发送给服务器。无法读取机器 ID 时 SHALL 在激活界面提示"无法识别本机"，SHALL NOT 生成随机 identifier。

#### Scenario: 移动应用位置
- **WHEN** 用户把应用移到另一个目录，或开关 VPN
- **THEN** identifier 不变，不需要重新激活

#### Scenario: 无法读取机器 ID
- **WHEN** Linux 系统上 `/etc/machine-id` 不存在
- **THEN** 激活界面显示"无法识别本机，无法激活"，不发起激活请求

### Requirement: 许可存储
系统 SHALL 把许可证密钥和 token 保存在 `<config_dir>/license/license.json`。许可证密钥和 token SHALL NOT 出现在日志、崩溃报告或更新请求的 URL 中。文件无法解析时 SHALL 重命名为 `license.json.bad-<时间戳>`，并视为无有效许可。

#### Scenario: 日志脱敏
- **WHEN** 激活、验证或更新检查的请求被记录到日志
- **THEN** 日志中只出现许可 ID 或密钥的末 4 位，不出现完整密钥和 token

#### Scenario: 文件损坏
- **WHEN** `license.json` 被截断成无效 JSON
- **THEN** 文件被重命名为 `.bad-<时间戳>`，显示激活界面

### Requirement: 时钟回拨检测
系统 SHALL 记录单调递增的 `last_seen_at`。当前时间早于 `last_seen_at` 或 token 的 `iat` 超过 24 小时时，系统 SHALL 不再根据本地 `exp` 判定有效，而是立即调用 verify；verify 无法完成时 SHALL 视为离线宽限已用完。

#### Scenario: 把时间调回 exp 之前
- **WHEN** `exp` 已过，用户把系统时间调回一个月前并断网
- **THEN** 系统检测到时钟回拨，显示激活界面，原因为"需要联网验证许可"

#### Scenario: 轻微的时钟误差
- **WHEN** 系统时间比 `last_seen_at` 早 10 分钟（NTP 校正）
- **THEN** 不视为回拨，按正常流程判断
