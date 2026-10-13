## 1. 运行时来源（构建时）

上一版的 1.1–1.6（自制运行时包 `build_runtime.py`、签名清单 `build_manifest.py`、运行时签名密钥、`runtime-index.json`）已被下面替换并删除。

- [x] 1.7 `release/runtime.json` 记录 PBS 版本与 sha256、镜像列表、模型 revision 与各文件 sha256
- [x] 1.8 `release/build_sources.py`：按平台解析 `uv.lock`（环境标记 + wheel 标签），生成 `desktop/src-tauri/runtime-sources/<target>.json`；`--check` 校验是否最新（macOS arm64 解析结果与 uv 安装的 134 个包一致）
- [x] 1.9 `build.rs` 把当前目标的清单编译进应用；清单的 `runtime_id` 不一致时拒绝使用
- [x] 1.4 把后端代码作为 Tauri resources 打进应用包

## 2. 运行时下载与安装（Rust）

- [x] 2.1 每个文件依次尝试各个地址（镜像在前、官方源在后）；镜像返回不同文件时丢弃并换下一个地址
- [x] 2.2 按目标卷检查磁盘空间（下载 + 解压 + 10%），并验证空间不足时不开始下载
- [x] 2.3 实现 `.part` 下载、Range 续传、3 次退避重试，并验证中断后能续传、服务端返回 200 时从头下载
- [x] 2.4 SHA256 校验通过后再 rename，并验证校验失败会触发重新下载
- [x] 2.5 解压解释器、用其 pip 离线安装 wheel（`--no-index --no-deps`）、rename、写入 `.complete`；保留上一个版本；pip 失败时不留下半成品
- [x] 2.6 把模型文件预下载到 `embedding_model_cache_dir` 的布局，并验证后端首次加载模型时不访问 Hugging Face

## 3. 后端进程管理（Rust）

- [x] 3.1 恢复 sidecar 模块：生产构建用 `<runtime>/bin/python -m fileseek` + PYTHONPATH，debug 构建用 `uv run` / `FILESEEK_BACKEND`
- [x] 3.2 等待 `connection.json` 被重写、`/health` 成功；退出时先优雅停止，5 秒后强杀；验证退出后没有残留进程
- [x] 3.3 检测到后端 30 秒内连续崩溃 2 次时提示修复运行时，并验证确认后会重新下载
- [x] 3.4 恢复 `api_request` 命令和按请求读取连接文件（预览协议同样改为每次读取），让打包后的界面能连上后端
- [x] 3.5 debug 构建也由 Rust 启动后端（`uv run`）；删除 vite.config.ts 中的 detached 启动，开发代理改为每个请求读取连接文件；用 pidfile + 进程组在下次启动时清掉 `tauri dev` 重建遗留的后端
- [x] 3.6 `STOP_GRACE_PERIOD` 从 5 秒改为 15 秒，确保大于后端 `task_drain_timeout`（10 秒）；验证 drain 中的任务在退出时放回 `queued`，而不是被强杀后停在 `processing`（应用退出等待 readiness 线程的时限同步改为 grace + 3 秒；`stop_waits_for_a_backend_still_draining_its_queue` 在 5 秒下失败、15 秒下通过；后端 `test_shutdown_puts_a_task_still_computing_back_in_the_queue`）
- [ ] 3.7 Windows 优雅停止：后端新增 `POST /shutdown`（token 鉴权、仅回环），触发与 SIGTERM 相同的关闭流程；Rust 在 Windows 上先调用它，超时后再强杀；验证 Windows 退出时任务正常放回队列（已实现：后端端点 + 单测、真实 `python -m fileseek` 上 `/shutdown` 1 秒内走完 lifespan 并删掉连接文件；Rust `request_shutdown` 在 macOS 上对假后端测试通过。未验证：Windows 分支未在 Windows 上编译和运行——本机交叉 `cargo check` 卡在 ring 缺 Windows SDK 头文件）；Windows 已在 CI 编译通过，运行时行为仍未在 Windows 上实测

## 4. 就绪状态机与初始化界面

- [x] 4.1 实现就绪状态机，通过 Tauri 事件推送状态和进度，并验证已安装时直接进入 `starting`
- [x] 4.2 初始化页：步骤、已下载/总量、速度、ETA；支持最小化到托盘并在完成时通知
- [x] 4.3 `failed` 状态：错误原因、重试（从失败步骤继续）、日志路径；验证目录不可写时显示具体路径
- [x] 4.4 首次进入主界面时显示一次"建议设置"对话框，选项默认不勾选
- [x] 4.5 在状态机最前面加入 `license_check` / `activation`；验证无许可时不请求运行时清单、不启动后端（`readiness::tests::without_a_license_nothing_starts_until_activation`）
- [x] 4.6 删除"首次进入 ready 时开始试用"的逻辑

## 5. 构建时配置与许可核心（Rust，按 Keygate 重写）

上一版的 5.x / 6.x（三项指纹、多公钥 `key_id`、试用双存储、防回放、套餐刷新窗口、离线激活/续期、mock 许可服务器）已被本节和第 6 节替换；可复用 `status.rs` 的状态计算骨架、`store.rs` 的文件读写和 `.bad-` 重命名、`last_seen_at`。

- [x] 5.1 构建配置：`KEYGATE_BASE_URL`、`KEYGATE_PRODUCT_SLUG`、许可公钥（hex）由 `build.rs` 写成编译期常量；release 构建缺项时失败；验证运行时无法覆盖（配置在 `desktop/src-tauri/keygate.json`，`KEYGATE_*` 环境变量可在 CI 覆盖；运行时的 `FILESEEK_LICENSE_SERVER_URL` 覆盖已删除。`product_id` 尚未填写：release 构建会按设计失败，需要真实 token 中的 `pid`）
- [x] 5.2 设备 identifier：hex(SHA256(盐 + 机器 ID))，三平台取值；读取失败时返回错误而不是随机值；删除三项指纹和模糊匹配
- [x] 5.3 token 解析与验签：`payload.signature`、对原始 payload 验签、校验 `pid` 和 `did`；验证改任意字符、换设备、换产品都失败
- [x] 5.4 `license.json` 存 `{license_key, token}`；损坏时重命名 `.bad-<时间戳>`；日志脱敏（只记许可 ID / 密钥末 4 位）（Rust 侧不记录密钥和 token；`license.json` 权限 0600）
- [ ] 5.5 Keygate 客户端：`activate`（带 `Idempotency-Key`、`X-Product-ID`）、`verify`、`deactivate`；按 `error.code` 分类错误；用本地 docker 部署的 Keygate 跑集成测试（已实现并有脚本服务器测试；真实服务器上错误路径已通过（`cargo test -- --ignored keygate`）。未完成：完整的激活→验证→解绑往返需要测试用许可证密钥，设置 `FILESEEK_TEST_LICENSE_KEY` 后运行 `keygate_round_trip`；Keygate 是用户自部署的真实服务，没有改用 docker）
- [x] 5.6 许可判断：`exp` 前不联网；`exp` 后 verify（200 替换 / 404 删除 / 网络失败 7 天离线宽限）；时钟回拨时强制 verify；输出 `licensed | unlicensed{reason}`
- [x] 5.7 启动时和每 24 小时检查；debug 构建默认有效，`FILESEEK_LICENSE_ENFORCE=1` 时走真实流程（启动检查在 readiness 线程上，之后 `start_checker` 每 24 小时一次）
- [x] 5.8 删除试用、`Plan` 枚举、刷新窗口/续费提示、防回放、离线请求码、`release/mock_license_server.py` 及其测试（同时删除 `release/test-keys/license-test.json`、`tests/fixtures/license/`、`keyring` 依赖）

## 6. 激活界面与运行中失效（前端 + Rust）

- [x] 6.1 激活界面：密钥输入、"购买许可证"（`{base_url}/buy/{product_slug}`）、原因展示（未激活 / 许可无效 / 已失效 / 需要联网验证）、"打开文件库目录"
- [ ] 6.2 激活错误文案：`ACTIVATION_LIMIT`（含 N/M 和客户门户链接）、`LICENSE_NOT_FOUND`、`EXPIRED/SUSPENDED/REVOKED/CANCELED`、`LOCKED_OUT`、网络失败、token 无效（文案和 N/M 已完成；缺客户门户链接：Keygate 前端对任意路径都返回 200，无法确认门户地址，需要提供）
- [x] 6.3 运行中失效：切到激活界面 → 优雅停止后端（复用 3.6/3.7）；验证导入中途失效后，重新激活时剩余任务继续（`readiness::tests::losing_the_license_stops_the_backend_and_shows_activation`）
- [x] 6.4 设置页许可区：状态、套餐名、到期日（无 `vun` 显示"永久"）、更新期截止、离线宽限剩余天数、"解绑本机"、"购买/续费"
- [x] 6.5 解绑：成功后删除本地许可、停止后端、回到激活界面；网络失败时保留本地许可
- [x] 6.6 删除上一版的试用横幅、续费/宽限横幅、离线激活对话框、导入入口和 MCP 的降级限制（`api_request` 改为无许可时拒绝所有请求，覆盖后端停止前的间隙）

## 7. 应用更新（Keygate feed）

- [x] 7.1 接入 tauri-plugin-updater，下载进度、取消、安装（沿用）
- [x] 7.2 写 `update.log`（沿用）
- [x] 7.3 endpoint 改为 `{base_url}/api/v1/releases/{product_slug}/upgrade.json?platform={{target}}-{{arch}}`，运行时设置 `X-License-Key` 请求头；`plugins.updater.pubkey` 改为 Keygate 的 Tauri 公钥；`401` 视为无更新；日志中不含密钥（Keygate 公钥写在 `keygate.json` 的 `updater_public_key`，目前为空：release 构建按设计会失败；`401/404` 时插件报 `ReleaseNotFound`，按无更新处理；真实 feed 上用未知密钥验证过返回 404）
- [x] 7.4 只在 `licensed` 状态下检查：启动 30 秒后、每 24 小时、手动
- [x] 7.5 强制更新：读取 `minimum_supported_version` / `minimum_supported_message`，显示不可关闭的横幅；删除 `update_type` 三档
- [x] 7.6 运行时联动改为读取并验签 `runtime-index.json`；index 不可用时直接提供应用更新；删除对 `latest.json` 中 `runtime_id` 的依赖
- [x] 7.7 删除 `release/build_latest.py` 和 `latest.json` 生成（同时删除 `release/tests/test_build_latest.py`）

## 8. 发布与签名

- [ ] 8.1 在 Keygate 后台：创建 `fileseek` 产品与套餐，生成 Signing 密钥，记录许可公钥和 Tauri 公钥写入构建配置
- [ ] 8.3 macOS：Developer ID 签名 + 公证，替换当前的 ad-hoc 签名
- [ ] 8.4 Windows：代码签名（NSIS，选定后不再更换）
- [x] 8.5 CI：`.github/workflows/release.yml`（plan / app / publish，darwin-arm64 + windows-x64；run 38394540618 两个平台构建成功，均已上传到 Keygate 1.0.2 草稿）
- [x] 8.6 `release/publish_keygate.py`：创建或复用草稿 release、按平台上传更新包、finalize、发布；支持 `--dry-run`；对本地假服务器测试（假服务器 7 个测试；对真实 Keygate 的 `--dry-run` 能正确读到 1.0.1 草稿、1.0.0 已撤回）
- [x] 8.8 `tauri.conf.json` 设 `productName: FileSeek`
- [ ] 8.10 （暂不需要：不发布 Linux）Linux 改用 CPU 版 torch

## 9. 端到端测试（对接真实或本地 docker 的 Keygate）

- [ ] 9.1 全新机器：安装 → 激活界面 → 激活 → 下载 → 就绪 → 导入和搜索
- [ ] 9.2 设备数已满、密钥不存在、已吊销；在客户门户释放设备后重新激活
- [ ] 9.3 Keygate 配置很短的校验间隔：`exp` 后自动 verify；断网 7 天内可用、超过后被拦截、联网重试恢复；改系统时间被检测
- [ ] 9.4 运行中吊销许可：导入中途被拦截，重新激活后任务继续
- [ ] 9.5 解绑本机后设备数减一
- [ ] 9.6 只改后端代码的更新；`runtime_id` 变化的更新；设置最低版本后出现强制更新横幅
- [ ] 9.7 macOS 和 Windows 各跑一遍 9.1–9.6
