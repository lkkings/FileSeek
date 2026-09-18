## Context

动机见 `proposal.md` - Why；行为契约见本 change 下 `specs/` 的五个 capability。

约束这套设计的现实条件：

- **空白项目**：`D:\FileSeek` 下无既有代码，无向后兼容负担，可自由选型
- **三平台原生集成**：右键菜单在 Windows / macOS / Linux 上是三套完全不同的系统 API，无跨平台抽象可用
- **推理必须本地**：模型体积与推理耗时直接决定安装包大小和入库延迟，无法靠云端算力回避
- **中文查询是一等需求**：示例查询全部为中文，而主流 CLIP 权重是英文对齐的，这一点约束模型选型
- **NAS 模式 B**：库文件在网络挂载点，索引在本地。跨设备移动不是原子 rename，网络可能随时断开
- **单用户桌面产品**：没有多租户、没有服务端集群，但需要开机自启、托盘常驻、进程生命周期管理

## Goals / Non-Goals

**Goals:**

- 一个进程边界清晰的三层结构：平台原生扩展（极薄）→ 本地后端服务（全部业务逻辑）→ 桌面 UI（纯呈现）
- 入库路径对数据安全负责：移动失败、跨卷移动、NAS 断连都不能丢文件
- 索引与检索的性能可预期：明确批处理、并发上限、索引类型的升级路径
- 三平台共享同一后端与同一 UI，平台差异被隔离在扩展层与少量适配代码中

**Non-Goals:**

- 不做多设备索引同步（模式 B 的定义是各设备维护自己的本地索引）
- 不做人脸识别、说话人识别等身份类特征（"红色头发的女孩"靠 CLIP 的通用视觉语义命中，不建人物库）
- 不做搜索结果的个性化排序或学习用户点击行为
- 不做移动端、不做 Web 端、不做远程访问
- v1 不做百万级向量的检索优化（预留升级路径，不在本 change 实现）

## Decisions

### 1. 三进程结构：原生扩展 / 后端服务 / UI

```
+---------------------------+     +---------------------------+
|  平台原生右键扩展          |     |  桌面 UI (Tauri WebView)  |
|  Win: IExplorerCommand    |     |  React + TypeScript       |
|  mac: FinderSync ext      |     |                           |
|  Linux: FM 脚本/插件      |     |                           |
+------------+--------------+     +-------------+-------------+
             |                                  |
             |  POST /ingest (loopback + token) |
             v                                  v
      +------------------------------------------------+
      |     本地后端服务 (Python / FastAPI)             |
      |  路由 · 任务队列 · 元数据 · 检索 · 文件搬运      |
      +----------------------+-------------------------+
                             |  IPC (queue)
                             v
                  +------------------------+
                  |  模型工作进程 (单实例)  |
                  |  CLIP / 文本编码 / OCR  |
                  +------------------------+
```

**为什么把全部逻辑放在后端服务**：右键扩展跑在文件管理器进程内（Windows 的 shell extension 尤其如此），任何崩溃、阻塞或重依赖都会拖累 Explorer/Finder。扩展只做"判断文件类型是否受支持 + 发一个 HTTP 请求 + 立刻返回"，几十 KB 的原生代码，不加载任何 AI 依赖。

**替代方案**：扩展直接写数据库或直接调用 Python。否决——把 Python 运行时和 torch 加载进 Explorer 进程是灾难，且无法满足"500ms 内交回控制权"。

**为什么模型单独一个进程**：CUDA 上下文在多进程中初始化会重复占用显存，且 fork 后的 CUDA 状态不可用。单个常驻工作进程持有模型、串行消费批次请求，是最省显存也最稳的做法。同时它让"切换模型规模"变成重启一个子进程，而非重启整个服务。

### 2. 桌面栈：Tauri v2 + Python 后端（而非 Electron 或 PyQt）

| 方案 | 安装包增量 | 前端生态 | 与 Python 后端的配合 | 结论 |
|------|-----------|---------|---------------------|------|
| Tauri v2 | ~10 MB（系统 WebView） | 完整 Web 生态 | sidecar 机制原生支持 | **选用** |
| Electron | ~120 MB（自带 Chromium） | 完整 Web 生态 | 需自行管理子进程 | 否决：体积 |
| PyQt/PySide | ~40 MB | 受限 | 同进程最简单 | 否决：UI 表达力与缩略图网格/内嵌播放器体验 |

Python 后端已是既定前提（faiss、torch、OCR 生态都在 Python），所以 UI 层的选择只看体积与表达力。Tauri 用系统 WebView，把安装包增量压到最低——这在一个已经要背模型权重的产品里很关键。Tauri 的 sidecar 正好用来管理 Python 后端进程的启停。

**代价**：需要写少量 Rust（sidecar 管理、托盘、平台适配）。Windows 侧的右键扩展本来也要用 Rust，技能栈是复用的。

### 3. 本地 IPC：loopback HTTP + 文件令牌

后端只绑定 `127.0.0.1`，端口从固定起始端口向上探测第一个可用端口，把 `{port, token}` 写入用户配置目录下一个仅当前用户可读的文件。扩展与 UI 都从该文件读取连接信息，并在 `Authorization` 头中带上 token。

**为什么要 token 而不只靠 loopback**：loopback 能挡住局域网，但挡不住本机上任何其他进程——包括浏览器里的网页（`http://127.0.0.1:<port>` 是可达的）。没有 token，任意网页就能让后端把用户磁盘上的文件移进库、或读出库内文件列表。token + 校验 `Origin`/`Sec-Fetch-Site` 一起用。

**替代方案**：Unix domain socket / Windows named pipe。更安全但三平台代码分叉、且 Tauri WebView 侧不方便直接用，收益不足以抵消复杂度。

### 4. 右键扩展：各平台用各自的现代 API，保留降级入口

- **Windows**：`IExplorerCommand`，通过 sparse MSIX package 注册，才能出现在 Windows 11 的一级右键菜单（旧式 `IContextMenu` 只会落到"显示更多选项"里）。用 Rust + `windows-rs` 实现
- **macOS**：Finder Extension（`FIFinderSync`），必须打进 app bundle 并签名/公证
- **Linux**：不存在统一机制。为 Nautilus（Python GObject 扩展）、Dolphin（`.desktop` service menu）、Thunar（custom action）各提供一份薄适配，三者都调用同一个小 CLI 入口

**共同降级路径**：后端同时提供一个 `fileseek add <paths...>` 的 CLI 与一个"拖拽到窗口即入库"的 UI 区域。任何平台的扩展安装失败或用户拒绝授权时，功能不至于完全不可用。

**替代方案**：只做"监视文件夹"（用户把文件拖进某个目录自动入库）。作为唯一方案否决——不满足"右键即入库"的核心体验；但它的实现成本低，可作为后续增强。

### 5. 文件搬运：跨卷用"复制-校验-删除"，同卷用 rename

模式 B 下"本地磁盘 → NAS 挂载点"必然跨卷，`rename` 不可用，而 `shutil.move` 的复制+删除中间失败会留下半个文件。

流程固定为：

```
1. 流式读源文件，边写目标临时名 (.fileseek-part) 边算 SHA-256
2. flush + fsync 目标文件
3. 校验：目标文件大小与摘要 == 源文件摘要
4. 原子 rename 临时名 -> 最终库内名
5. 只有 4 成功后，才删除源文件
6. 写入元数据（含原始路径与内容摘要）
```

任何一步失败都保留源文件不动，并清理临时文件。同卷情况下 1-5 退化为单次 `rename`，摘要另行流式计算。

**为什么摘要在搬运时顺带算**：去重需要内容摘要，搬运本来就要完整读一遍文件，两件事合并成一次 IO。对 5 GB 视频，这省掉一整轮读盘。

### 6. 去重：SHA-256 全文摘要 + 唯一约束

`files.content_hash` 上建唯一索引。命中已有记录时不产生第二份库内副本，只把这次提交的原始路径追加到该记录的来源列表。

**替代方案**：`size + 头尾若干 KB` 的快速摘要。否决——快速摘要要么需要在冲突时回退到全文比对（复杂度更高），要么承担误判风险。既然搬运阶段本来就要读全文，全文摘要是免费的。

### 7. 模型选型：中文对齐是硬约束

| 用途 | GPU 档 | CPU 档 | 关键考虑 |
|------|--------|--------|---------|
| 图片/视频帧 ↔ 文本 | Chinese-CLIP ViT-L/14 | Chinese-CLIP ViT-B/16 | **必须中文对齐** |
| 文档文本 | multilingual-e5-large | multilingual-e5-small | 中英同一向量空间 |
| OCR | RapidOCR (ONNX) | RapidOCR (ONNX) | 中文识别 + 体积小 |

**图像模型为什么不用 OpenAI CLIP / OpenCLIP**：它们的文本塔只对齐英文，"图中带有猫的图片"这类查询会显著退化。可选路径有三条：(a) Chinese-CLIP，中文原生对齐；(b) M-CLIP 等多语言蒸馏版本；(c) 查询先机翻成英文再用英文 CLIP。选 (a)：(c) 引入翻译模型或联网、且会丢失查询细节；(b) 中文效果通常弱于 (a)。Chinese-CLIP 同时保留英文能力，能满足 spec 里的中英混合查询。

**Chinese-CLIP 经 `transformers` 加载而非官方 `cn-clip` 包**：`cn-clip` 硬依赖 `lmdb`（其训练侧的数据集格式所需），而 `lmdb` 在 Windows + CPython 3.12 上没有可用 wheel，源码构建还要求 `patch-ng`，会让 Windows 安装直接失败。`transformers` 原生提供 `ChineseCLIPModel` / `ChineseCLIPProcessor`，可加载同一批 OFA-Sys 官方权重，且推理侧不需要 `lmdb` 与 `timm`/`torchvision`。模型选型不变，只换加载途径，依赖树同时变小。

**OCR 为什么用 RapidOCR**：Tesseract 的中文准确率明显偏弱；PaddleOCR 准确但要拖入整个 Paddle 运行时。RapidOCR 是 PaddleOCR 模型的 ONNXRuntime 移植，准确率接近而依赖只有 onnxruntime，且不占用 torch 的显存预算。

**硬件探测**：`torch.cuda.is_available()` + 显存查询决定 GPU 档；Apple Silicon 走 MPS 且归入 GPU 档；其余走 CPU 档。加载时若显存不足则捕获 OOM 并降级到 CPU 档（spec 要求降级而非失败）。

### 8. 向量索引：三个独立索引 + IDMap，v1 用精确检索

- 三个索引分开（文档 / 图片 / 视频片段）：向量维度与语义空间本就不同，分开还让"按类型限定检索"变成选择索引而非过滤结果
- 一律用 `IndexIDMap2` 包裹，让 Faiss 内部 id 等于我们自己的稳定整型 id。**这是删除能力的前提**：文件被移出库或需重新索引时可以 `remove_ids`，不必整体重建
- 向量入库前 L2 归一化，用 `IndexFlatIP`，内积即余弦相似度
- v1 用 `IndexFlatIP`（精确）。万级到十万级向量下，暴力检索在 CPU 上是毫秒到几十毫秒量级，满足 spec 的 2 秒预算，且没有训练步骤、没有召回率损失
- 预留升级：向量数超过阈值时切 `IndexIVFFlat`。索引类型与模型标识一起记录在元数据里，升级走"从已存向量重建"路径

**为什么不一开始就用 IVF**：IVF 需要训练集、有召回率损失、参数需要调，而在目标规模下收益是"几十毫秒变几毫秒"——用户感知不到。过早引入是纯粹的复杂度成本。

**模型变更的隔离**：每个索引文件旁记录产生它的模型标识与向量维度。加载时若与当前生效模型不符，拒绝混写并向用户提示重建（对应 media-indexing 的兼容性要求）。

### 9. 元数据：SQLite，一张主表 + 三张类型表 + 片段表

```
files (id, path, original_paths, filename, media_type, size,
       content_hash UNIQUE, created_at, added_at, modified_at,
       index_state)            -- indexed / missing / needs_reindex
  |
  +-- documents (file_id, text_content, page_count, language, chunk_count)
  +-- images    (file_id, width, height, ocr_text, vector_id)
  +-- videos    (file_id, duration, width, height, fps, sampled_frames)
  |     |
  |     +-- video_segments (id, video_id, start_time, end_time,
  |                         vector_id, thumbnail_rel_path)
  +-- doc_chunks (id, file_id, chunk_index, char_start, char_end, vector_id)

tasks (id, source_paths, media_type, status, stage, progress,
       error_message, completed_stages, priority, created_at, ...)

schema_meta (key, value)   -- schema 版本、各索引的模型标识与维度
```

**为什么主表 + 类型表而不是单张宽表**：三类文件的字段差异大（视频有片段、文档有分块），单张宽表会有大量 NULL 列且随类型增加而膨胀。主表承载所有共有查询（去重、一致性检查、按时间列表），类型表按需 join。

**为什么文档要 `doc_chunks`**：spec 要求长文档分段而非截断，且结果要给出匹配文本片段。分块必须是一等实体，才能让"命中哪一段"可回溯到字符区间。检索时按文件聚合分块命中，取最高分代表该文件。

**全文检索**：文件名与抽取文本另建 FTS5 虚表，作为向量检索的补充通道（精确关键词、文件名匹配）。向量负责语义，FTS 负责字面。

### 10. 视频管线：1 fps 采样 → 向量相似度聚合成片段

```
video (10 min)
   |  ffmpeg/PyAV 解码，1 fps 采样
   v
600 frames --[批量 16 帧送模型工作进程]--> 600 vectors
   |
   |  相邻向量余弦相似度 < 阈值 处切分
   |  + 最短片段 2s / 最长片段 30s 约束
   v
segments [(0.0, 8.0), (8.0, 23.0), ...]
   |
   |  每段取中间帧 -> 缩略图；段内向量取均值并归一化 -> 段向量
   v
写入 video_segments + 向量索引 + 缩略图
```

**为什么用向量相似度切段而不用 PySceneDetect**：帧向量本来就要算，用它做场景边界判断是零额外成本；而 PySceneDetect 需要再解码一遍、多一个依赖。更重要的是，向量相似度切出的边界与"语义内容变化"对齐，正好是检索想要的粒度——镜头切换但内容相同的两段没必要拆开。

**为什么 1 fps**：这是"不漏掉一次出场"与"计算量"的折中。人物出场通常持续数秒，1 fps 足以捕获；提到 2 fps 会让耗时翻倍而召回提升有限。采样率作为配置项暴露。

**批量 16 帧**：单帧逐次送 GPU 的瓶颈在 kernel 启动与数据传输，批量化能拿到数倍吞吐。批大小随显存档位调整。

### 11. 任务队列：SQLite 表 + 单消费者 + 阶段级断点

不引入 Celery / Redis / RabbitMQ——桌面产品加一个外部 broker 的部署成本远超收益。任务表本身就是队列：

- 取任务：按 `priority DESC, created_at ASC` 选 `queued`，事务内置为 `processing`
- 并发上限：消费者同时持有的任务数不超过配置值（默认 3）
- 优先级：右键单次提交 = 高优先级，批量导入 = 低优先级（满足 file-ingestion 的优先级要求）
- **阶段级断点**：`completed_stages` 记录已完成阶段（moved / extracted / encoded / indexed）与其中间产物位置。重试从第一个未完成阶段开始，不重复抽帧
- 服务重启：启动时把残留的 `processing` 重置为 `queued`（其 `completed_stages` 保留，因此不丢已完成工作）
- NAS 断连：需要写库目录的任务置为 `queued` 并暂停消费，而非 `failed`（对应 library-storage 的健康检查要求）

### 12. 缩略图：NAS 为准 + 本地 LRU 缓存（write-through）

缩略图写入库内 `.thumbnails/`（在 NAS 上），同时写入本地缓存目录。UI 读取时先查本地缓存，未命中再回源 NAS 并填充缓存。

**为什么两处都写**：spec 要求 NAS 不可达时仍能展示已缓存的缩略图（desktop-client），同时要求缩略图随库存放以便另一台设备复用（library-storage）。write-through 同时满足两者，代价是几十 KB 级的重复存储。

### 13. 视频播放：后端提供支持 Range 的流式端点，UI 内嵌播放器

UI 不直接用 `file://` 或 Tauri asset 协议读 NAS 上的视频，而是请求后端的 `GET /media/{file_id}` —— 该端点校验 token、把路径限制在库根目录内、并支持 HTTP Range。

**为什么绕一层后端**：(a) 内嵌播放器要 seek 到片段起点，Range 请求让它只拉需要的字节，而不是等整个文件；(b) 路径校验集中在一处，避免 UI 侧拼出越界路径；(c) NAS 读取的重试与超时逻辑有地方放。

**替代方案**：调用系统播放器并传时间戳参数（`vlc --start-time=`）。否决为主方案——依赖用户装了特定播放器，且各播放器参数不一、失败时无法反馈。保留"用系统默认程序打开"作为次要入口。

### 14. 模型权重：不进安装包，首次启动经用户同意后下载

四个模型（图像 GPU/CPU 档、文本 GPU/CPU 档、OCR）全部内置会让安装包到 GB 级，而任一用户只会用到其中一档。安装包只带下载器；首次启动按探测到的硬件档位下载对应权重，并按 spec 要求在权重就位前明示索引不可用。

**代价**：首次启动需要联网。为离线部署场景额外提供"离线权重包"手动放置路径。

## Risks / Trade-offs

- **[Windows 11 一级右键菜单需要 MSIX sparse package 注册，签名与打包链条复杂]** → 先用旧式 `IContextMenu`（落在"显示更多选项"）打通端到端功能，把 `IExplorerCommand` + sparse package 作为独立任务推进；CLI 与拖拽入口始终可用，不让右键成为唯一路径

- **[macOS Finder Extension 必须签名公证，个人开发者账号与公证流程可能阻塞]** → 同上，拖拽与 CLI 兜底；公证作为发布任务而非功能任务

- **[Linux 各文件管理器机制不统一，覆盖成本随发行版发散]** → 三个适配都只是调同一个 CLI 的薄壳，新增一种文件管理器的成本是几十行配置

- **[Chinese-CLIP 对"红色头发的女孩"这类复合属性查询的精度未经验证]** → 在实现前用一批真实样本做检索质量基线测试，若不达预期则评估 M-CLIP 或"CLIP 粗筛 + 属性标签补充"；spec 只承诺"命中出现该内容的片段"，不承诺精确率数字

- **[无 GPU 设备上视频索引可能慢到不可接受（10 分钟视频数分钟以上）]** → CPU 档默认降低采样率、允许用户把视频索引限定在空闲时段；任务视图明示预估耗时，让慢有预期而不是像卡死

- **[跨卷"复制-校验-删除"对大文件是两倍 IO 且中途断连会留下临时文件]** → 临时文件用固定后缀，启动时清理孤儿；校验通过才删源，最坏情况是浪费一次 IO 而非丢数据

- **[SQLite 在 NAS 上会因文件锁不可靠而损坏]** → 设计上元数据库与索引强制本地（library-storage 明确 MUST NOT 写 NAS），配置层面拒绝把它们指向网络路径

- **[loopback HTTP 端点可被本机任意进程/网页访问]** → token 文件权限限制为当前用户 + 校验请求来源；token 随服务启动轮换

- **[Faiss 的 `remove_ids` 在 FlatIP 上是 O(n) 且会打乱内部顺序]** → 删除走标记为主（`index_state = missing` 时检索层过滤），批量物化删除在维护窗口执行

- **[Python 后端打包（PyInstaller + torch + faiss）体积大且平台差异多]** → 三平台各自构建产物；把体积预算作为发布前的检查项，而非事后惊喜

- **[模型档位切换要求重建索引，用户可能在库很大时才发现]** → 首次启动就明确当前档位与"切换需重建"的代价；索引文件旁记录模型标识，加载时即刻校验而非静默混写

## Migration Plan

全新项目，无数据迁移。以下是交付与回退策略：

1. **端到端骨架优先**：后端服务 + SQLite schema + 一个平台的入库入口（CLI）+ 最小检索 UI，先让"加一张图片、搜到它"这条链路跑通
2. **按媒体类型分批接入**：图片 → 文档 → 视频。每一类接入后其检索路径独立可用，视频这类高风险项不阻塞前两类交付
3. **平台扩展作为独立增量**：CLI 入口先行，三个平台的原生扩展各自作为可独立完成、可独立失败的任务
4. **NAS 支持在本地库稳定后接入**：本地库路径先稳定，再把库根目录换成挂载点并补健康检查与暂停/恢复语义
5. **schema 版本化**：`schema_meta` 记录版本号，后续 change 通过版本号执行前向迁移
6. **回退策略**：索引与元数据可从库内文件完整重建（这是"文件被移动而非复制"下唯一的真实数据源），因此任何索引层问题的兜底都是"重建索引"，不涉及用户文件

## Open Questions

- 权重下载走 Hugging Face 直连还是自建镜像（国内网络可达性可能影响首次启动成功率）——不影响架构与任务划分，发布前定
- 离线权重包的分发形态（单个压缩包 / 按档位拆分）
- 三个 Linux 文件管理器的适配优先顺序，可按目标用户分布在实现时排序
