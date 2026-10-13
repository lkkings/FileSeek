## Purpose

通过自部署的 Keygate 激活、验证和解绑 FileSeek 许可；没有有效许可时只提供激活界面，套餐、有效期和设备数全部由 Keygate 决定。

## ADDED Requirements

### Requirement: 激活界面
没有有效许可时，系统 SHALL 只显示激活界面，SHALL NOT 显示文件库界面、下载运行时或启动后端。激活界面 SHALL 包含：许可证密钥输入框、"购买许可证"链接（`{base_url}/buy/{product_slug}`，在系统浏览器打开）、当前无许可的原因、"打开文件库目录"按钮。

#### Scenario: 未激活的首次启动
- **WHEN** 用户首次启动应用，本地没有许可
- **THEN** 显示激活界面，原因为"尚未激活"，主界面不可进入

#### Scenario: 购买链接
- **WHEN** 用户点击"购买许可证"
- **THEN** 系统浏览器打开 `https://licenses.tuodianyuan.com/buy/fileseek`

#### Scenario: 打开文件库目录
- **WHEN** 许可已失效的用户点击"打开文件库目录"
- **THEN** 系统文件管理器打开文件库目录（默认 `~/FileSeekLibrary`），用户可以直接访问原文件

### Requirement: 在线激活
用户提交许可证密钥后，系统 SHALL 调用 Keygate `POST /api/v1/license/activate`，携带密钥、本机 identifier、`identifier_type: "device"` 和电脑名作为 `label`，并带 `Idempotency-Key` 请求头（同一次激活的重试复用同一个值）。响应 `activated` 或 `already_activated` 且返回的 token 验签通过时，系统 SHALL 保存密钥和 token 并继续启动流程。失败时 SHALL 按错误码分类展示原因。

#### Scenario: 激活成功
- **WHEN** 用户输入有效密钥，Keygate 返回 `activated` 和 token
- **THEN** 系统保存许可，离开激活界面，进入运行时检查

#### Scenario: 本机已激活过
- **WHEN** 同一台机器重新输入同一密钥，Keygate 返回 `already_activated`
- **THEN** 视为激活成功，不额外占用设备数

#### Scenario: 设备数已满
- **WHEN** Keygate 返回 `409 ACTIVATION_LIMIT`
- **THEN** 显示"此许可证已在 N/M 台设备上激活"，并提供客户门户链接以释放旧设备

#### Scenario: 密钥无效或许可不可用
- **WHEN** Keygate 返回 `LICENSE_NOT_FOUND`、`LICENSE_EXPIRED`、`LICENSE_SUSPENDED`、`LICENSE_REVOKED` 或 `LICENSE_CANCELED`
- **THEN** 分别显示"许可证不存在""许可证已过期""许可证已暂停""许可证已吊销""许可证已取消"，不保存任何内容

#### Scenario: 尝试次数过多
- **WHEN** Keygate 返回 `429 LOCKED_OUT`
- **THEN** 显示"尝试次数过多，请稍后再试"

#### Scenario: 网络失败
- **WHEN** 无法连接 Keygate
- **THEN** 显示"无法连接许可服务器，请检查网络"和"重试"

#### Scenario: 返回的 token 无法验签
- **WHEN** 激活响应成功，但 token 验签失败或 `did` 与本机不符
- **THEN** 不保存许可，显示"许可服务器返回了无效的许可"，并记录日志

### Requirement: 许可验证
系统 SHALL 在启动时、以及之后每 24 小时判断许可状态：本地 token 有效且当前时间早于 `exp` 时 SHALL 直接视为有效，不联网；当前时间不早于 `exp` 时 SHALL 调用 `POST /api/v1/license/verify`。verify 成功且新 token 验签通过时 SHALL 替换本地 token；verify 返回 404 时 SHALL 删除本地许可，视为已失效。

#### Scenario: exp 之前
- **WHEN** 本地 token 的 `exp` 在 3 天后
- **THEN** 启动时不发起网络请求，直接进入运行时检查

#### Scenario: exp 之后自动续上
- **WHEN** `exp` 已过，用户的订阅已经续费，verify 返回新 token
- **THEN** 系统保存新 token，用户无感知

#### Scenario: 许可已失效
- **WHEN** `exp` 已过，verify 返回 404（到期未续、吊销、暂停、在门户解绑了本机）
- **THEN** 系统删除本地许可，显示激活界面，原因为"许可证已失效"

### Requirement: 离线宽限
verify 因网络失败、5xx 或 429 无法完成时，若当前时间早于 `exp + 7 天`，系统 SHALL 继续视许可为有效，并在设置页显示"离线中，请在 N 天内联网验证"；超过后 SHALL 显示激活界面，原因为"需要联网验证许可"，并提供"重试"。该原因 SHALL 与"许可证已失效"区分显示。

#### Scenario: 短期离线
- **WHEN** `exp` 已过 2 天，网络不可用
- **THEN** 应用正常使用，设置页提示"请在 5 天内联网验证"

#### Scenario: 离线超过宽限
- **WHEN** `exp` 已过 8 天，网络仍不可用
- **THEN** 显示激活界面，原因为"需要联网验证许可"；联网后点击"重试"，verify 成功即恢复

### Requirement: 运行中许可失效
应用运行期间许可变为无效（verify 返回 404，或离线宽限用完）时，系统 SHALL 显示激活界面并优雅停止后端：后端停止领取新任务，等待在飞任务落地（最多 10 秒），未落地的任务放回队列。重新激活后 SHALL 正常启动后端，队列中未完成的任务 SHALL 继续处理。

#### Scenario: 导入过程中失效
- **WHEN** 正在导入 100 个文件，第 40 个处理中时 24 小时检查发现许可已失效
- **THEN** 立即显示激活界面；第 40 个文件在 10 秒内落地或被放回队列后后端停止；重新激活后剩余任务继续导入

### Requirement: 解绑本机
设置页 SHALL 提供"解绑本机"。系统 SHALL 调用 `POST /api/v1/license/deactivate`，成功后删除本地许可并显示激活界面。网络失败时 SHALL NOT 删除本地许可，并提示稍后重试或在客户门户解绑。

#### Scenario: 换机前解绑
- **WHEN** 用户点击"解绑本机"并确认，Keygate 返回 `deactivated`
- **THEN** 本地许可被删除，后端停止，显示激活界面，Keygate 上的设备数减一

#### Scenario: 解绑时离线
- **WHEN** 用户点击"解绑本机"，网络不可用
- **THEN** 本地许可保留，显示"无法连接许可服务器，请稍后重试，或在客户门户中解绑"

### Requirement: 许可信息展示
设置页 SHALL 显示许可区：许可状态、套餐名称（verify 返回的 `plan_name`，激活后尚未 verify 时显示许可 ID）、到期日（`vun`，缺省显示"永久"）、更新期截止（`upd`，缺省不显示）、"解绑本机"和"购买/续费"链接。系统 SHALL NOT 根据套餐、`ftr` 或 `grc` 限制任何功能。

#### Scenario: 永久许可
- **WHEN** token 中没有 `vun`
- **THEN** 到期日显示"永久"

#### Scenario: 不同套餐同等可用
- **WHEN** 两个用户分别持有不同套餐的有效许可，`ftr` 内容不同
- **THEN** 两者能使用的功能完全相同

### Requirement: 开发构建
debug 构建 SHALL 默认视许可为有效，不联网。设置环境变量 `FILESEEK_LICENSE_ENFORCE=1` 时 SHALL 走真实流程。release 构建 SHALL 始终走真实流程，不受该变量影响。

#### Scenario: 开发者本地调试
- **WHEN** 开发者用 `tauri dev` 启动，没有设置 `FILESEEK_LICENSE_ENFORCE`
- **THEN** 不显示激活界面，直接进入运行时检查
