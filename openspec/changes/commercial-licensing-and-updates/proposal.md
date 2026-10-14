## Why

> **Packaging supersession:** `protected-backend-runtime-download` supersedes the later Nuitka packaging direction and keeps this change's downloaded Python runtime, while adding PyArmor source protection and content-defined model sets.

FileSeek 要从开发者工具变成可售卖的桌面产品，需要付费激活、可信的自动更新，以及普通用户能装能用的分发方式。目前生产环境甚至没有拉起后端的路径（`sidecar.rs` 已在前端重构中删除），后端运行时和模型都依赖开发环境。

许可和更新统一对接自部署的 Keygate（`https://licenses.tuodianyuan.com`，产品 `fileseek`），套餐、有效期、设备数、更新期、强制更新都由 Keygate 后台配置，客户端不内置任何套餐知识。

## What Changes

**分发与首次运行：**
- 原生安装包只含 Tauri 外壳和后端代码；Python 运行时和模型由应用首次运行时下载
- 签名的运行时清单、断点续传、SHA256 校验、原子安装、可修复
- 恢复 Rust 侧的后端进程管理，生产环境使用下载的运行时

**许可（Keygate）：**
- 没有有效许可时只显示激活界面（输入许可证密钥 + 购买链接），不进入主界面、不下载运行时、不启动后端
- `POST /api/v1/license/activate | verify | deactivate`；Keygate 签发的 Ed25519 token（`payload.signature`）在本地验签，`exp` 之前离线可用
- `exp` 过后联网 verify；verify 返回 404（到期、吊销、暂停、设备已解绑）时删除本地许可并回到激活界面；联网失败时在 `exp` 之后给 7 天离线宽限
- 运行中许可失效时，停止进行中的任务和后端，切到激活界面
- 设备标识为机器 ID 的 SHA256；只看许可是否有效，不读 `ftr`
- `base_url`、`product_slug` 为构建时配置；许可公钥编译进二进制

**更新（Keygate feed）：**
- tauri-plugin-updater 使用 Keygate 的 `upgrade.json`，通过 `X-License-Key` 请求头携带许可，更新包由 Keygate 签名
- 强制更新读取 `minimum_supported_version` / `minimum_supported_message`
- 运行时包仍托管在自有 CDN，用独立的运行时签名密钥；新增签名的 `runtime-index.json` 把应用版本映射到 `runtime_id`，依赖变化时先更新运行时再安装应用

**相对上一版设计删除的内容：** 本地 7 天试用、离线激活（请求码）、离线续期、自定义许可服务器协议、`monthly/quarterly/yearly/lifetime` 套餐枚举与按套餐的刷新窗口、续费提示、多项设备指纹模糊匹配、keychain 防回放、`update_type` 自定义字段、"许可失效降级为只读"、自管 minisign 发布密钥。理由见 design.md。

**不做：** 浮动许可、按 `ftr` 的功能分级、应用内展示套餐价格、代码混淆、调试器检测、文件哈希自检。

## Capabilities

### New Capabilities

- `backend-runtime`: 运行时与模型的清单校验、下载、安装、修复，以及后端进程的启停
- `app-initialization`: 启动流程（许可检查 → 运行时就绪 → 主界面）、初始化界面、错误与重试、就绪后的可选设置
- `licensing-activation`: 激活界面、在线激活、验证与离线宽限、解绑、许可失效时的拦截
- `licensing-security`: token 验签、设备标识、许可存储、时钟回拨检测、构建时配置
- `app-update`: Keygate feed 更新检查、强制更新、签名校验与安装、运行时联动更新

### Modified Capabilities

<!-- 无。后端配置系统保持不变 -->

## Impact

**桌面端（Rust）：** sidecar、运行时下载与安装（已完成）；许可模块按 Keygate 协议重写（`client`、`document`、`device`、`store`、`status`）；更新模块改用 Keygate feed 和 runtime-index。新增构建时配置读取。

**桌面端（前端）：** 激活界面替代原来的试用横幅和功能降级；设置页许可区（状态、到期、解绑）；更新提示改为强制更新逻辑。

**后端：** 不需要修改。

**发布流水线：** 应用更新包上传 Keygate 并由其签名；运行时包、清单、`runtime-index.json` 用运行时密钥签名后上传自有 CDN；macOS 公证、Windows 代码签名。

**外部服务：** 自部署 Keygate（许可 + 更新 feed + 更新包存储），自有 CDN（运行时与模型）。

**用户影响：** 必须先激活才能使用；激活后首次启动下载约 1.2GB（macOS arm64 实测）；许可失效后只能看到激活界面，原文件仍在文件库目录中可直接访问。
