## Context

FileSeek 要从开发者工具变成可售卖的桌面产品，需要：付费激活、可信的自动更新、普通用户能装能用。

现状里和这次设计直接相关的几点：

- **生产环境没有拉起后端的路径。** `desktop/src-tauri/src/sidecar.rs` 在 `09eb462 前端重构` 中被删除；它原本也只会用 `uv run --directory <repo>/backend python -m fileseek` 从源码目录启动。现在打包的 sidecar 只有 `fileseek-mcp-service`。
- **后端依赖很重。** torch、transformers、onnxruntime、chromadb 等，加上 jina-clip-v2 量化模型（约 874MB，`shared/utils/model_cache.py` 首次使用时从 Hugging Face 懒下载）。没有 Python 运行时，搜索、导入、预览全都不可用。
- **配置来自环境变量和 `.env`**（pydantic-settings，`config/settings.py`），没有 `config.yaml`。应用级目录由 `config/paths.py:AppPaths` 和 Rust 侧 `preview_protocol::connection_file_path` 按同一规则计算；文件库默认在 `~/FileSeekLibrary`。
- macOS 当前是 ad-hoc 签名（`signingIdentity: "-"`）。
- **许可和更新服务是自部署的 Keygate**（AGPL 开源），地址 `https://licenses.tuodianyuan.com`，产品 slug `fileseek`。参考：`docs/许可证及应用更新开发文档.md`、keygate.app/zh/docs 的 license-activation、tauri、software-updates 三页。
- 本 change 的上一版按自定义许可服务器协议实现了许可模块（试用、离线激活、套餐刷新窗口、防回放等）。改为 Keygate 后，这部分按本设计重写；运行时与 sidecar 部分不受影响。

## Goals / Non-Goals

**Goals:**
- 原生安装包安装，激活后首次启动自动下载后端运行时和模型，过程可见、可续传、可修复
- 必须持有 Keygate 签发的有效许可才能使用应用
- 套餐、有效期、设备数、更新期、强制更新全部由 Keygate 后台决定，客户端不内置套餐知识
- 应用本体和后端运行时都通过签名校验后自动更新

**Non-Goals:**
- 防御能修改本地二进制的攻击者。本地检查只是减速带，真正的安全边界是服务端签名和激活数管理
- 代码混淆、虚拟机检测、调试器检测、文件哈希自检
- 试用期（客户端不提供；如需试用，由 Keygate 后台配置短期套餐）
- 浮动许可（并发席位）
- 按 `ftr` 做功能分级
- 应用内展示套餐与价格（只提供购买链接）
- 离线激活
- 便携模式

## Decisions

### 1. 分发：原生安装包 + 首次运行下载后端运行时

**决策：** Tauri 外壳按平台惯例打包（macOS `.app`/dmg、Windows NSIS、Linux AppImage/deb），安装包里不含 Python 运行时和模型。激活后由 Rust 侧下载、校验、安装。

**理由：** 运行时加模型是 GB 级，变化频率远低于外壳；放进安装包会让每次更新都重下几个 GB。

**放弃的方案：**
- *PyInstaller 冻结后端为 sidecar*：torch 冻结脆弱（spawn 子进程、动态库加载），体积大，且每次发版都要整体替换。
- *所有东西写进 `<app_dir>`*：macOS `.app` 写入会破坏签名且 `/Applications` 不可写，Windows `Program Files` 普通用户不可写。

### 2. 后端运行时：首次运行从官方源安装

**决策：** 不自制、不托管运行时包。应用首次运行时，从官方源或其镜像下载三类文件，逐个按编译进应用的 sha256 校验，然后在本机安装：

| 内容 | 官方源 | 镜像（先试） |
|------|--------|-------------|
| CPython 3.12（python-build-standalone `install_only_stripped`） | github.com/astral-sh/python-build-standalone | registry.npmmirror.com |
| 后端依赖：`backend/uv.lock` 锁定的每个 wheel | files.pythonhosted.org | 阿里云、清华 PyPI 镜像 |
| 模型：jina-clip-v2 固定 revision 的 ONNX 与 tokenizer | huggingface.co | hf-mirror.com |

- 安装：解压解释器 → 用它自带的 pip `install --no-index --no-deps` 安装已校验的 wheel 文件（精确到 `uv.lock` 锁定的文件）→ 写 `.complete`。全部在 staging 目录完成后一次 rename，中断后下次重做。
- **完整性：** 来源无所谓，sha256 在签名的应用里。镜像只能慢或失败，不能换文件。每个文件依次尝试各个地址，再按退避重试。
- **`runtime_id`** = hash(`uv.lock` + Python 版本 + PBS 发布)，仍是安装目录名；依赖不变的版本直接复用已装的运行时。
- **FileSeek 后端自身代码**随应用发布（Tauri resources），通过 `PYTHONPATH` 加载，经 Keygate 更新。
- **安装位置**不变：`<data_dir>/runtime/<runtime_id>/`，保留上一个版本，更早的清理掉。

### 3. 下载清单：构建时生成，编译进应用

**决策：** `release/build_sources.py` 读取 `uv.lock`、`release/runtime.json`（PBS 版本与 sha256、镜像列表、模型 revision 与各文件 sha256），按每个平台的环境标记和 wheel 标签解析出要装的 wheel，写到 `desktop/src-tauri/runtime-sources/<target>.json`；`build.rs` 把当前目标的那份 `include_str!` 进二进制。

- 清单在签名的二进制里，不需要单独签名，也不需要运行时签名密钥、`runtime-manifest.json`、`runtime-index.json` 或自有 CDN（上一版的这些全部删除）。
- 清单的 `runtime_id` 与构建算出的不一致时拒绝使用（忘了重新生成）；CI 用 `--check` 校验已提交的清单是最新的。
- 没有清单的目标（不支持的平台）在初始化页显示"当前平台暂不支持"。
- 实测 macOS arm64 解析出 134 个 wheel，与 uv 直接安装的包集合完全一致；首次下载约 0.42 GB 依赖 + 0.89 GB 模型。

**已知问题：** Linux 上 PyPI 的 torch 依赖 CUDA（19 个 nvidia/triton wheel，约 2.45 GB），Linux 首次下载约 3.4 GB。要改用 CPU 版 torch 需要调整 `backend/pyproject.toml` 的索引配置，另行处理（tasks 8.10）。

### 4. 启动流程：许可检查在运行时之前

**决策：** 启动是一个由 Rust 驱动的状态机，前端只负责展示。许可检查是第一步：

```
license_check --无有效许可--> activation（激活界面）--激活成功--+
     |                                                          |
     +--有效-------------------------------------------------- -+
     v
checking -+- 已就绪 -----------------------------------------> starting -> ready
          +- 缺失/损坏 -> space_check -> downloading -> verifying -> installing -> starting -> ready
                           任一步失败 -> failed（可重试 / 查看日志）
```

- **激活在下载之前**：没有许可的用户不需要先下载 1.2GB；激活界面不依赖后端。
- 运行时就绪前显示初始化页（当前步骤、已下载/总量、速度、ETA），可以最小化到托盘。
- 空间检查按目标卷分别计算：下载大小 + 解压后大小 + 10% 余量。
- 下载：写 `.part`，用 HTTP Range 续传；每轮依次试每个地址，失败后按 1s/2s/4s 退避再来一轮。服务端不支持 Range 时从头下载。
- 安装完成写 `.complete`，记录解释器路径。

### 5. 后端进程管理（恢复 sidecar）

**决策：** 在 Rust 侧恢复 sidecar 模块：

- 生产环境用 `<runtime>/bin/python -m fileseek`，`PYTHONPATH` 指向随应用分发的后端代码。
- 开发环境（debug 构建）保留 `uv run`，可用 `FILESEEK_BACKEND` 覆盖。
- 沿用原协议：等待 `connection.json` 被重写、`/health` 返回成功。
- **优雅停止**：后端收到停止请求后由 lifespan 调用 `TaskScheduler.shutdown()`：停止领取新任务 → 等在飞任务落地（`task_drain_timeout`，10 秒）→ 超时未落地的放回 `queued`。Rust 的强杀时限 SHALL 大于后端的 drain 时限：`STOP_GRACE_PERIOD` 从 5 秒改为 15 秒，否则后端还在 drain 就被强杀，`release_stranded` 来不及执行（下次启动会补做，任务不丢，但关闭不干净）。
- **Windows 优雅停止**：Windows 没有 SIGTERM，现在直接 `child.kill()`。改为 Rust 调用后端的 `POST /shutdown`（用 `connection.json` 中的 token 鉴权，只监听回环地址），后端触发与 SIGTERM 相同的关闭流程；请求失败或超时后再强杀。Unix 保持 SIGTERM。
- 只有许可有效时才启动后端；许可在运行中失效时停止后端（见决策 9）。

后端在启动后 30 秒内连续崩溃 2 次时，提示"修复运行时"，确认后删除 `.complete` 并重新下载。

### 6. 构建时配置

**决策：** Keygate 地址、产品和公钥都在构建时确定，安装后用户无法修改。

| 项 | 示例 | 来源 |
|----|------|------|
| `KEYGATE_BASE_URL` | `https://licenses.tuodianyuan.com` | 构建配置，`build.rs` 写成编译期常量 |
| `KEYGATE_PRODUCT_SLUG` | `fileseek` | 同上 |
| 许可公钥 | `GET /api/v1/license/pubkey` 的 hex | 同上 |
| 更新公钥 | Keygate Signing 页 "Public key for Tauri" | `tauri.conf.json` `plugins.updater.pubkey` |
| 运行时公钥、运行时 CDN 地址 | 自有 | 同上（沿用现有 `build.rs` 注入） |

- 配置放在仓库内一个构建配置文件中（随 CI 环境变量覆盖），缺失时 release 构建失败，避免发出连不上服务器的包。
- 公钥必须是编译期常量：地址被改成伪造的服务器时，伪造的 token 过不了验签；公钥若可配置，签名就没有意义。
- 购买链接由配置拼出：`{base_url}/buy/{product_slug}`。

### 7. 许可 token：Keygate 签发、本地验签

**决策：** 许可凭证是 Keygate 返回的 token，格式为 `base64url(payload) "." base64url(ed25519(payload))`（不是 JWT，没有 header）。签名针对 token 中 payload 的原始字符串（解码前）。验签在 Rust 侧（`ed25519-dalek`）。

payload 中客户端使用的字段：

| 字段 | 用途 |
|------|------|
| `lid` | 许可 ID，用于展示和日志 |
| `pid` | 产品 ID，须与本产品一致 |
| `did` | 设备 identifier，须等于本机 identifier |
| `iat` | 签发时间，用于时钟回拨检测 |
| `exp` | 下次必须联网校验的时间（Keygate 已取 min(签发 + 校验间隔, `vun` + `grc`)） |
| `vun` | 许可到期时间，缺省为永不过期，只用于展示 |
| `upd` | 更新期截止，只用于展示（门控由 Keygate feed 执行） |

客户端**不**解释 `pln`、`sts`、`grc`、`ftr`：套餐、宽限、功能全部由服务端通过 `exp` 和 verify 的结果体现。

- 存放在 `<config_dir>/license/license.json`：`{license_key, token}`，明文。token 的完整性靠签名；`license_key` 可被他人用来占用激活数，但不能绕过激活数上限，所以接受明文存放，日志和崩溃报告中不得出现它。
- **放弃的方案：** 上一版的自定义 JSON 许可 + `key_id` 多公钥轮换。Keygate 只有一把签名密钥，轮换需要发新版本内置新公钥，这在服务端更换 `LICENSE_SIGNING_KEY` 时才发生。

### 8. 激活、验证、解绑

**决策：** 直接调用 Keygate 的三个接口（`{base_url}/api/v1/license/...`，请求头 `X-Product-ID: fileseek`）：

- **激活** `POST /activate {license_key, identifier, identifier_type: "device", label}`。`label` 为电脑名。请求带 `Idempotency-Key`（每次激活操作生成一个，重试复用）。`activated` 和 `already_activated` 都视为成功。拿到 token 后先验签再保存。
- **验证** `POST /verify {license_key, identifier}`。只在 `exp` 已过时调用（启动时和之后每 24 小时检查一次是否需要）。
- **解绑** `POST /deactivate {license_key, identifier}`。成功后删除本地许可，回到激活界面。网络失败时不删除本地许可，提示稍后重试或去客户门户解绑。

许可判断：

```
本地 token 验签失败 / did 不符 / pid 不符 ------------------> 无许可
now < exp -------------------------------------------------> 有效（不联网）
now >= exp -> verify:
    200                 -> 验签新 token 并保存 -----------> 有效
    404                 -> 删除本地许可 ------------------> 无许可（已失效）
    网络失败 / 5xx / 429 -> now < exp + 7 天 ? 有效（离线宽限） : 无许可（需要联网）
```

- 离线宽限 `OFFLINE_GRACE_DAYS = 7`，编译期常量。宽限期间设置页显示"离线中，请在 N 天内联网验证"。
- 激活错误按 Keygate 错误码分类展示：`LICENSE_NOT_FOUND`（密钥不存在）、`ACTIVATION_LIMIT`（设备数已满，附 `details.current/max` 和客户门户链接）、`LICENSE_EXPIRED` / `SUSPENDED` / `REVOKED` / `CANCELED`、`LOCKED_OUT`（稍后再试）、网络失败。

**理由：** Keygate 用 `exp` 把校验节拍、到期和宽限合在一个时间点里，客户端只需要"`exp` 前信本地、`exp` 后问服务器"。上一版按套餐计算刷新窗口、续费提示窗口、宽限期的逻辑全部由服务端接管。

### 9. 无许可时的拦截

**决策：** 权益只有两态：`licensed` 和 `unlicensed`（附原因：`none` 未激活、`invalid` 验签或设备不符、`revoked` 服务端已失效、`offline_expired` 离线宽限用完）。`unlicensed` 时只显示激活界面：

- 激活界面：许可证密钥输入框、"购买许可证"链接、失败原因、"打开文件库目录"按钮（让用户知道原文件仍在 `~/FileSeekLibrary`，没有被锁住）。`offline_expired` 显示"需要联网验证许可"和"重试"，与"许可无效"区分。
- 不下载运行时、不启动后端，所以搜索、预览和 MCP 都不可用。这也堵上了上一版"过期后 MCP 客户端仍可访问后端"的漏洞。
- **运行中失效**（24 小时检查时 verify 返回 404，或离线宽限用完）：先切到激活界面，然后按决策 5 优雅停止后端。在飞任务有 10 秒落地，未落地的放回 `queued`。重新激活后正常启动后端，调度器继续处理队列。不需要新增"暂停队列"接口。
- debug 构建默认 `licensed`，设置 `FILESEEK_LICENSE_ENFORCE=1` 时走真实流程。

**放弃的方案：** 上一版的"失效降级为只读、数据永远可浏览"。按产品要求改为硬拦截；原文件始终在文件库目录中，用户不会丢数据。

### 10. 设备标识

**决策：** `identifier` = hex(SHA256(盐 + 机器 ID))。机器 ID 取 macOS `IOPlatformUUID`、Windows 注册表 `MachineGuid`、Linux `/etc/machine-id`。盐为编译期常量。

- Keygate 在服务端做精确匹配，上一版的三项指纹模糊匹配已无意义。
- 不发送序列号、MAC 地址、安装路径。
- 读取失败（如 Linux 容器没有 machine-id）时激活界面提示无法识别设备，不生成随机 ID：随机 ID 每次启动都会变，会把用户的激活数耗尽。
- **已知局限：** 重装系统会改变 `MachineGuid` / `machine-id`，需要用户在客户门户释放旧设备后重新激活。虚拟机克隆会得到相同的 ID，接受。

### 11. 时钟回拨

**决策：** 维护单调递增的 `last_seen_at`（`<config_dir>/license/` 下）。当前时间早于 `last_seen_at - 24h`，或早于 token 的 `iat - 24h` 时，视为时钟回拨：本地判断不再相信 `exp`，强制联网 verify；联网失败按 `offline_expired` 处理。

**理由：** 不处理的话，把系统时间拨回 `exp` 之前就能永远离线使用。

### 12. 应用更新：tauri-plugin-updater + Keygate feed

**决策：** 使用官方 `tauri-plugin-updater`，endpoint 为 Keygate 的 Tauri feed：

```
{base_url}/api/v1/releases/{product_slug}/upgrade.json?platform={{target}}-{{arch}}
请求头 X-License-Key: <license_key>      （由 updater_builder().header() 运行时设置）
```

- **license 放请求头，不放 URL**：Keygate 文档明确要求，URL 会进入代理和 CDN 日志。Tauri 不支持 `{{LICENSE_KEY}}` 占位符，所以由 Rust 在检查前设置请求头。
- **签名**：发布时由 Keygate 签名每个更新包，客户端用 `tauri.conf.json` 中的 Keygate Tauri 公钥校验。不再自管 minisign 发布密钥。
- **门控与更新期**：feed 是否要求许可、更新期（`upd`）限制哪些版本，都在 Keygate 后台配置并由服务端执行。客户端收到 `401` 视为"暂无可用更新"。
- **检查时机**：启动后 30 秒（只在 `licensed` 状态下）、之后每 24 小时、手动检查。
- **强制更新**：读取 `rawJson` 中的 `minimum_supported_version` 和 `minimum_supported_message`。当前版本低于最低版本时，显示不可关闭的横幅和 Keygate 给出的消息，引导更新；不禁用功能。其余情况为普通更新，只在设置页显示"有新版本"并弹出一次提示。替代上一版的 `update_type` 三档。
- **渠道**：只用 stable。设置页暂不提供 beta 开关。
- **Windows 安装包类型**选定 NSIS 后不再更换（Keygate 要求）。

### 13. 依赖变化的版本

**决策：** Keygate 只发应用本体。新版本的 `runtime_id` 与已装的相同时，重启即用；不同时（`uv.lock` 变了），新版本首次启动显示初始化页，从官方源下载并安装新运行时，旧运行时保留一个版本用于回滚。

**放弃的方案：** 更新前预下载新运行时（上一版的 runtime-index）。它需要在 Keygate 之外发布并签名一份索引；依赖变化不频繁，首次启动多等一次可以接受。

### 14. 代码保护：不做

**决策：** 不引入代码混淆，不做文件哈希自检，不做调试器检测，也不在代码签名校验失败时退出。

**理由：** 后端代码和运行时位于用户可写目录，替换一个 `.py` 文件就能绕过任何放在 Python 侧的检查；自我校验哈希是被篡改的代码在检查自己；检测到调试器就退出会误伤开发者，补丁几行即可绕过。参考文档第 5 节的这些建议面向原生 Swift/C# 应用。许可检查放在编译后的 Rust 里，加上服务端签名和激活数，已经足够。

### 15. 配置

**决策：** 后端继续使用 pydantic-settings。许可、运行时状态由 Rust 管理，分别位于 `<config_dir>/license/` 和 `<data_dir>/runtime/`。文件库路径和 `connection.json` 的位置保持不变。

### 16. 支持的平台与发布流水线

**决策：** 发布 2 个平台：`darwin-arm64`、`windows-x64`。Linux 不发布（产品决定；`runtime-sources/` 里仍保留 Linux 清单，以后要发只需在工作流里加回矩阵项）。下面 3 个平台因依赖缺失无法支持：

| 平台 | 缺的依赖（Python 3.12，按 `uv.lock`） |
|------|------|
| `darwin-x64` | torch（2.3 起不再发 Intel Mac）、onnxruntime 1.30 |
| `windows-arm64` | torch、chromadb、opencv |
| `linux-armhf` | torch、onnxruntime、chromadb、faiss、numpy、opencv、pillow；且 32 位放不下约 2GB 的模型 |

要支持这 3 个，需要降级依赖或从源码编译，另开 change 评估。

**流水线：** GitHub Actions `.github/workflows/release.yml`（保留在仓库中备用），推 `v<版本>` tag 或手动触发。也可以在各平台本机构建后用 `release/publish_keygate.py` 上传。

```
plan ──> app (macos-14 / windows-2022 原生 runner) ──> publish (Keygate)
```

- **plan**：校验 tag 与 `tauri.conf.json` 版本一致，`build_sources.py --check` 校验下载清单是最新的。
- **app**：PyInstaller 打 MCP sidecar，`tauri build` 产出安装包和更新包。安装包类型固定：macOS `.dmg` + 更新包 `.app.tar.gz`；Windows NSIS。`tauri build` 要求的更新签名私钥用每次运行临时生成的一把，因为 Keygate 发布时会重新签名，这份 `.sig` 不使用。
- **publish**：`release/publish_keygate.py` 调用 Keygate admin API：`POST /admin/releases` → 每个平台 `POST /admin/releases/:id/artifacts` 拿预签名地址 → `PUT` 上传 → `POST .../finalize`（带本地 sha256，由 Keygate 复核）→ `POST /admin/releases/:id/actions/publish`。同一版本已有草稿时复用它，重复运行不会建出多个版本。
- **没有签名证书时**：macOS 用 ad-hoc 签名（首次打开需要右键"打开"），Windows 不签名（SmartScreen 警告）。证书到位后只需加 Secrets。

**GitHub 配置：**

| 名称 | 类型 | 用途 |
|------|------|------|
| `KEYGATE_API_KEY` | Secret | 只需 `releases:write`，限定到 fileseek 产品 |

## Risks / Trade-offs

| 风险 | 影响 | 缓解 |
|-----|------|------|
| 没有试用，必须先买才能用 | 转化率下降 | 购买页充分介绍；如需试用，在 Keygate 配置短期套餐 |
| 首次下载约 1.2GB（解压后约 2.3GB） | 网络差的用户流失 | 断点续传、托盘后台下载、CDN 选国内可达节点 |
| 许可失效后看不到应用内数据 | 用户以为数据被锁 | 激活界面提供"打开文件库目录"；原文件始终在磁盘上 |
| Keygate 服务器不可用 | 新激活失败；`exp` 已过的设备 7 天后被拦截 | 自部署可控；`exp` 节拍（建议 7 天）+ 7 天离线宽限，最长 14 天不联网 |
| 本地检查可被修改二进制绕过 | 破解版流通 | 接受；安全边界在服务端签名和激活数 |
| 重装系统导致机器 ID 变化 | 付费用户占用多一个激活数 | 客户门户自助解绑；设置页提供"解绑本机" |
| `license_key` 明文存放 | 被他人拿去激活 | 受激活数上限约束；日志脱敏 |
| Keygate 签名密钥更换 | 旧版本无法验签新 token | 先发内置新公钥的版本，等大多数用户升级后再更换服务端密钥 |
| 官方源或镜像不可达 | 首次运行无法完成 | 每个文件有多个地址依次尝试；断点续传；失败后可重试 |
| 运行中失效时停止后端 | 正在导入的任务被打断 | 复用优雅关闭：在飞任务有 10 秒落地，未落地的放回队列，重新激活后继续 |

## Migration Plan

- 开发者用 `uv run` 和 `tauri dev` 不受影响：debug 构建跳过许可检查，权益默认为 `licensed`。`FILESEEK_LICENSE_ENFORCE=1` 时走真实流程，配合本地 docker 部署的 Keygate 测试。`release/mock_license_server.py` 删除。
- 上一版许可模块尚未发布给用户，没有需要迁移的本地许可文件；开发机上旧的 `license.json`、`trial_started_at.txt` 和 keychain 条目在新逻辑下读不出 token，按"无许可"处理，可以手动清理。
- 现有 `~/FileSeekLibrary` 和 `connection.json` 位置不变。

**分阶段：**
1. **后端运行时与 sidecar**：已完成。
2. **许可（Keygate）**：client/token/device/store/status 重写，激活界面，启动流程中的许可前置，运行中失效处理。
3. **更新**：Keygate feed、强制更新、runtime-index。
4. **发布流水线**：Keygate 上传、运行时签名与 CDN、macOS 公证、Windows 签名。

## Open Questions

1. ~~**任务队列暂停**~~ 已解决：复用 `TaskScheduler.shutdown()` 的优雅关闭（见决策 5、9），不新增接口。
2. **Keygate 套餐的校验间隔**：决定 `exp` 节拍，建议 7 天。在 Keygate 后台配置，不影响客户端代码。
3. **更新 feed 是否门控**：Keygate 后台设置。按 Keygate 的建议，要先发一个携带 `X-License-Key` 的版本（本 change 的首个版本即是），再开启门控和更新期。
4. ~~**macOS Intel**~~ 已决定：不支持（决策 16）。
5. ~~**运行时 CDN**~~ 已决定：不需要，依赖和模型从官方源与镜像下载（决策 2、3）。
