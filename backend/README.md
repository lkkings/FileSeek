# FileSeek Backend

本地语义文件搜索的后端服务。接收桌面客户端与命令行的入库与查询请求，管理异步任务队列，抽取特征向量并维护 FAISS 索引，提供语义检索接口。

## 快速开始

```bash
uv sync --extra dev      # 安装依赖（含开发工具）
uv run pytest            # 运行测试
uv run ruff check .      # lint
uv run mypy src          # 类型检查
```

服务仅监听 `127.0.0.1`，通过连接文件中的令牌鉴权，确保只有本机客户端可访问。

## 架构

### 请求与数据流

```
右键扩展 / CLI                         桌面 UI
      │  POST /ingest                       │  POST /search
      │  (只写任务行, <500ms 返回)           │
      ▼                                     ▼
┌──────────────────────────────────────────────────────┐
│  FastAPI 服务 (127.0.0.1, 令牌鉴权)                   │
│  api/routes.py → api/dependencies.py 注入协作对象      │
└───────┬──────────────────────────────────┬───────────┘
        │                                  │
        ▼ 写 tasks 表                       ▼ search/service.py
┌────────────────────┐            ┌────────────────────┐
│ tasks/queue.py     │            │ 编码查询 → 查三个索引 │
│ (SQLite 即队列)     │            │ → 按类型分组返回     │
└───────┬────────────┘            └─────────┬──────────┘
        │ claim_next()                      │
        ▼                                   │
┌────────────────────────────────────┐      │
│ pipeline/runner.py 按类型分派        │      │
│  ├─ pipeline/documents.py           │      │
│  ├─ pipeline/images.py              │      │
│  └─ pipeline/video.py               │      │
│                                     │      │
│  每条流水线的固定顺序:               │      │
│  library/ 搬运 → extract/ 抽取       │      │
│  → 编码 → db/ 写元数据 → index/ 写索引│      │
└──────────┬──────────────────────────┘      │
           │ encode_images / encode_texts     │
           ▼                                  ▼
    ┌─────────────────────┐        ┌──────────────────┐
    │ 模型子进程 (spawn)   │        │ index/ 三个索引   │
    │ models/worker.py    │        │ FAISS IndexFlatIP│
    │ Chinese-CLIP + 文本  │        └──────────────────┘
    └─────────────────────┘
```

先搬运再抽取是有意的:文件在读内容之前就已进库,所以解码失败只留下一个可重试的失败任务,原文件安然在库里。

### 模块结构

```
src/fileseek/
├── api/              # 本地 HTTP 服务
├── db/               # SQLite 元数据与迁移
├── extract/          # 内容抽取(文本/像素/帧)
├── index/            # FAISS 向量索引
├── library/          # 库目录与文件搬运
├── models/           # 模型加载与子进程
├── pipeline/         # 入库流水线
├── search/           # 检索
├── tasks/            # 任务队列
├── config.py         # 用户配置
├── media_types.py    # 受支持扩展名
└── paths.py          # 三平台目录
```

### 文件职责

#### `api/` — 本地 HTTP 服务

| 文件 | 职责 |
|------|------|
| `app.py` | 装配 FastAPI:注册路由、健康检查、异常信封、lifespan 钩子 |
| `auth.py` | 令牌中间件与 `Origin` / `Sec-Fetch-Site` 校验;健康检查豁免 |
| `connection.py` | 写 `{port, token}` 连接文件(仅当前用户可读),启动时轮换 token |
| `dependencies.py` | `Services` 聚合协作对象,经 FastAPI 依赖注入给处理器 |
| `lifecycle.py` | `ServiceLifecycle` 状态 + `drain()` 排空 + `shutdown()` 存索引 |
| `models.py` | 响应信封 `success_response` / `error_response` 与分页元数据 |
| `routes.py` | 七个端点的处理逻辑与入参校验 |
| `server.py` | 端口探测(从 8765 向上找空闲端口),只绑 127.0.0.1 |

#### `db/` — SQLite 元数据

| 文件 | 职责 |
|------|------|
| `connection.py` | 连接工厂:autocommit 模式 + 外键约束,拒绝网络路径 |
| `migrations.py` | 按 `schema_meta` 记录的版本号增量应用迁移 |
| `records.py` | 行值对象:`FileRecord`、`SegmentRecord`、`ChunkRecord` 等 |
| `repositories.py` | 六个仓储:files、documents、images、videos、segments、chunks |
| `schema.py` | 有序迁移列表:八张表、索引、FTS5 虚表 |

#### `extract/` — 内容抽取

| 文件 | 职责 |
|------|------|
| `chunking.py` | 长文档切块,记录 `chunk_index` 与字符区间以便回溯命中位置 |
| `documents.py` | PDF / DOCX / TXT / MD 取文本与页数;无文本层 PDF 走 OCR 回退 |
| `images.py` | 读宽高,解码为编码器可用的像素 |
| `video.py` | 探测容器元数据(时长/宽高/帧率),按采样率抽帧 |

#### `index/` — 向量索引

| 文件 | 职责 |
|------|------|
| `registry.py` | 拥有三个索引,分配只增不复用的向量 id,校验模型标识,`save_all` 落盘 |
| `store.py` | 单个索引封装:`IndexIDMap2` + `IndexFlatIP`,add / search / remove_ids / 持久化 |

#### `library/` — 库目录与搬运

| 文件 | 职责 |
|------|------|
| `consistency.py` | 存在性 + 摘要比对,识别被外部删除或替换的库内文件 |
| `hashing.py` | 流式 SHA-256;搬运时顺带算,省掉一整轮读盘 |
| `ingest.py` | 入库主流程:摘要命中已有记录则只追加来源路径,不产生副本 |
| `layout.py` | 库内布局:文档 / 图片 / 视频 / `.thumbnails/` 子目录,拒绝不可写目录 |
| `mover.py` | 同卷 `rename`;跨卷复制-校验-删除,任何一步失败都保留源文件 |
| `thumbnails.py` | 片段缩略图写入库内,并 write-through 到本地缓存 |

#### `models/` — 模型与子进程

| 文件 | 职责 |
|------|------|
| `encoders.py` | 真实编码器,在子进程内加载 Chinese-CLIP 与多语言文本模型 |
| `hardware.py` | 探测 CUDA 可用性与显存、Apple MPS,回退 CPU |
| `protocol.py` | 父子进程间的请求 / 响应消息定义 |
| `tiers.py` | 档位决策:GPU 档 ViT-L/14,CPU 档 ViT-B/16,含用户覆盖 |
| `vectors.py` | L2 归一化,让内积等价于余弦相似度 |
| `weights.py` | 权重就位检查、下载(需同意、可续传、校验摘要) |
| `worker.py` | `spawn` 子进程与父进程侧的调用句柄 |

#### `pipeline/` — 入库流水线

| 文件 | 职责 |
|------|------|
| `context.py` | `IndexingContext` 聚合流水线所需的一切,以及进度上报协议 |
| `documents.py` | 搬运 → 抽取 → 分块 → 编码 → 写元数据 / FTS / 索引 |
| `images.py` | 搬运 → 编码 → OCR → 写元数据 → 写索引 |
| `video.py` | 搬运 → 抽帧 → 批量编码 → 按向量相似度切片段 → 缩略图 → 写索引 |
| `maintenance.py` | 一致性扫描后的索引修复:物化删除被标记条目 |
| `runner.py` | 按媒体类型分派到上面三条流水线,并把结果记在任务上 |

#### `search/` — 检索

| 文件 | 职责 |
|------|------|
| `results.py` | 按类型分组的结果结构与每类的 `has_more` 标记 |
| `service.py` | 编码查询 → 跨索引查询 → 文档按文件聚合、视频按视频聚合 |

#### `tasks/` — 任务队列

| 文件 | 职责 |
|------|------|
| `queue.py` | SQLite 即队列:事务化 `claim_next`、进度上报、重试、重启恢复 |
| `records.py` | `TaskRecord` 与状态机,拒绝非法状态转移 |

#### 根模块

| 文件 | 职责 |
|------|------|
| `config.py` | 读写 `config.yaml`,加载时全量校验并指明出错字段 |
| `media_types.py` | 受支持扩展名的唯一来源,可导出 JSON 供三平台原生扩展复用 |
| `paths.py` | 三平台配置 / 数据 / 缓存目录,以及网络路径判定 |


### 关键设计

**模型推理隔离**  
推理跑在 `spawn` 出的独立子进程里，父进程通过 `multiprocessing.Queue` 收发编码请求。CUDA 上下文在多进程中重复初始化会重复占用显存，fork 后的 CUDA 状态也不可用——单个常驻工作进程持有模型、串行消费批次，是最省显存的做法。它还让"切换模型档位"变成重启一个子进程，而不是重启整个服务。

**任务队列即数据表**  
桌面产品不该为了排队引入 Redis 或 Celery，所以 `tasks` 表本身就是队列：取任务在 `BEGIN IMMEDIATE` 事务里完成（并发取任务不会把同一行分配两次），进度持久化，重启后残留的 `processing` 行被重置回 `queued`。

状态机是 `queued → processing → completed | failed`，`failed → queued` 是重试入口。`processing → queued` 同时覆盖重启恢复与 NAS 断连时的暂停——断连时任务被放回队列而非判定为永久失败。

阶段记录在 `completed_stages`（`moved → extracted → encoded → indexed`），所以重试跳过已完成的阶段而不是从头再来。交互式提交（右键单个文件）优先级 100，批量导入 0，单个提交不会卡在批量导入后面。

**三个独立索引**  
文档分块、图片、视频片段各有一个 FAISS 索引：向量来自不同模型、维度不同，分开存放还让"只搜视频"变成选索引而不是过滤结果。索引按需打开，未用到的不占磁盘。

每个索引旁记录产生它的模型标识与向量维度。两个模型的向量混进同一个索引会悄悄毁掉相似度，所以档位变更在加载时被检测出来，并在索引重建前拒绝写入。

向量 id 由 `schema_meta` 里的序列分配，只向前增长、从不复用——复用会让被删除条目的 id 与新条目重名。

**优雅关闭**  
关闭顺序是固定的：先停止取新任务，等在飞的任务落地（默认 10s 超时），最后把索引写盘。反过来做会写出一份缺少在飞任务向量的状态。

FAISS 的增量写入留在内存里，进程不落盘就退出会留下一个仍可读、但丢掉了本次运行全部新向量的文件——文件看着正常，受影响的文件却再也搜不到。超时仍未结束的任务被放回 `queued` 而非判失败：它的文件没动过、已完成阶段也保留，下次启动继续。


## 启动与使用

### 本地开发启动

```bash
# 1. 安装依赖
uv sync --extra dev

# 2. 配置（可选）。配置由 pydantic-settings 从环境变量 / backend/.env 读取，
#    字段名见 fileseek/config/settings.py。不配也能跑，库根目录默认 ~/FileSeekLibrary。
cat > .env << EOF
LIB_ROOT=$HOME/FileSeekLibrary
API_PORT=8765
EOF

# 3. 启动服务（推荐：自己探测空闲端口、写连接文件、装配依赖）
uv run python -m fileseek

# 指定端口（被占用时自动改用空闲端口）
uv run python -m fileseek --port 8765

# 不启动后台调度器（入库文件会停在 queued 不被处理，只在调试处理流程时用）
uv run python -m fileseek --no-scheduler

# 开发模式（自动重载）。uvicorn 自己持有 socket，应用问不到真实端口，
# 所以端口靠 FILESEEK_PORT 告知，需与 --port 一致；不设它就不会发布连接文件，
# 桌面端会一直等不到后端就绪。
FILESEEK_PORT=8765 uv run uvicorn fileseek.bootstrap:create_service_app \
  --factory --reload --host 127.0.0.1 --port 8765
```

服务启动后会：
1. 在配置目录写入 `connection.json`（包含 `{port, token}`）
2. 客户端读此文件获取端口与鉴权令牌
3. 仅监听 127.0.0.1，外部无法访问

### 模型权重

权重不在仓库里，首次使用需下载。GPU 档用 ViT-L/14 与 e5-large，CPU 档用 ViT-B/16 与 e5-small，后者小得多；OCR 模型随 pip 包自带，无需下载。

权重未就位时服务仍能启动并接受入库（任务排队等待），但检索会明确报告不可用——而不是假装索引已经好了：

```bash
# 检查缺失的权重
uv run python -c "
from fileseek.models.weights import WeightStore
from fileseek.models.tiers import select_models
from fileseek.paths import AppPaths

paths = AppPaths.resolve()
store = WeightStore(paths.model_dir)
selection = select_models()
readiness = store.readiness_for_tier(selection.tier)

if readiness.missing:
    print('缺失:', [w.name for w in readiness.missing])
else:
    print(f'{selection.tier} 档权重已就位')
"

# 下载（需同意许可协议）
# 权重保存位置见上方 model_dir 路径，或配置 models.path 覆盖
```

客户端首次连接时也会检测并提示下载。

### 入库与搜索示例

```bash
# 获取连接信息（路径随平台而异，问出来更省事）
CONN=$(uv run python -c "from fileseek.config.paths import AppPaths; print(AppPaths.resolve().connection_file)")
TOKEN=$(jq -r .token "$CONN")
PORT=$(jq -r .port "$CONN")

# 入库文件
curl -X POST "http://127.0.0.1:$PORT/ingest" \
  -H "X-FileSeek-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"paths": ["/path/to/document.pdf", "/path/to/image.jpg"]}'
# 返回 {"status": "success", "data": {"task_ids": ["uuid-1", "uuid-2"]}}

# 查询任务状态
curl "http://127.0.0.1:$PORT/tasks/<task-id>" \
  -H "X-FileSeek-Token: $TOKEN"

# 搜索
curl -X POST "http://127.0.0.1:$PORT/search" \
  -H "X-FileSeek-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "机器学习算法", "limit": 10}'
# 返回 {"status": "success", "data": {"documents": [...], "images": [...], "videos": [...]}}
```

### 进程管理

```bash
# 查看服务进程
ps aux | grep fileseek

# 停止服务（SIGTERM 触发优雅关闭）
pkill -TERM -f "python -m fileseek"      # 上面推荐的启动方式
pkill -TERM -f "uvicorn fileseek"        # 开发模式（--reload）

# 优雅关闭会：
# 1. 停止接受新任务
# 2. 等待进行中任务完成（默认 10s 超时）
# 3. 保存已打开的 FAISS 索引
# 4. 关闭模型子进程
```

### 目录结构

启动后产生的文件（macOS 示例，其他平台路径见配置节）：

```
~/Library/Application Support/FileSeek/
├── config.yaml          # 用户配置
├── connection.json      # {port, token}，客户端据此连接
├── metadata.db          # SQLite 元数据（files、segments、chunks、tasks 表）
├── index/               # FAISS 向量索引
│   ├── image.faiss
│   ├── video_segment.faiss
│   └── document_chunk.faiss
└── models/              # 模型权重缓存
    ├── chinese-clip-vit-large-patch14/
    └── multilingual-e5-large/

~/Library/Caches/FileSeek/
└── thumbnails/          # 视频分段缩略图缓存

~/FileSeekLibrary/       # 库根目录（在 config.yaml 的 library.root 配置）
├── documents/           # 按媒体类型分目录，保留原文件名
│   └── report.pdf
├── images/
├── videos/
└── .thumbnails/         # 片段缩略图（隐藏目录，随库存放）
```

库内文件保留原文件名；同名不同内容时自动消解冲突，不覆盖已有文件。去重靠 `files.content_hash` 的唯一索引，不靠目录结构。

## 测试

```bash
uv run pytest                           # 运行全部测试
uv run pytest tests/test_api_lifecycle.py  # 单个文件
uv run pytest -k "queue or index"       # 按名称筛选
uv run pytest --cov --cov-report=html   # 生成覆盖率报告
```

覆盖率门限为 80%（`fail_under`），低于此值命令以非零码退出。

标记 `slow` 的测试（`test_models_encoders.py`、`test_pipeline_documents_real.py`）会加载真实模型权重，权重不在磁盘上时自动跳过。其余测试通过 `tests/fake_encoders.py` 里的替身编码器运行，因此整个套件不需要 GPU 也不联网。

`tests/` 下的 `api_fixtures.py`、`doc_fixtures.py`、`video_fixtures.py` 提供共享夹具：内存数据库、临时库目录、装配好依赖的 app。

## API 端点

除健康检查外，所有请求需携带 `X-FileSeek-Token` 头，值取自连接文件 `connection.json`。浏览器发起的请求还会校验 `Origin` / `Sec-Fetch-Site`，拒绝跨站来源。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 服务状态（无需鉴权） |
| `/ingest` | POST | 提交路径批量入库，立即返回任务 id |
| `/tasks/{task_id}` | GET | 查询任务状态、阶段与进度 |
| `/tasks/{task_id}/retry` | POST | 重试失败任务 |
| `/search` | POST | 自然语言检索 |
| `/thumbnails/{file_id}/{segment_id}` | GET | 获取视频片段缩略图 |
| `/media/{file_id}` | GET | 流式返回媒体文件（支持 HTTP Range） |

响应统一包裹在信封中：

```json
{"status": "success", "data": {...}, "error": null}
```

`/search` 响应在 `data` 内含 `documents`、`images`、`videos` 三数组以及 `has_more_documents`、`has_more_images`、`has_more_videos` 标记，表示该类型还有更多结果。翻页通过 `offset` 和 `limit` 控制。

`/ingest` 不做任何搬运或索引工作，只写任务行后返回——调用它的 shell 扩展必须在 500ms 内把控制权交回文件管理器，即使选中的是 5GB 视频。不受支持的扩展名被静默跳过，以 `skipped` 计数返回。

## 配置

配置文件 `config.yaml` 与连接文件 `connection.json` 位于同一目录：

| 平台 | 配置目录 |
|------|---------|
| macOS | `~/Library/Application Support/FileSeek/` |
| Windows | `%APPDATA%\FileSeek\` |
| Linux | `${XDG_CONFIG_HOME:-~/.config}/fileseek/` |

索引与元数据库另存于数据目录（Windows 上是 `%LOCALAPPDATA%`，其余平台见 `paths.py`），且强制为本地路径——库文件可以放在 NAS 上，索引不行。

示例（实际 YAML 结构）：

```yaml
library_root: /Users/alice/FileSeekLibrary
model_dir: null          # 留空则用默认权重目录
processing:
  max_concurrent: 3
  video_fps: 1.0
  thumbnail_size: [320, 180]
  device_preference: auto  # auto | gpu | cpu
nas:
  enabled: false
  protocol: smb            # smb | nfs | webdav
  host: nas.local
  share: /volume1/photos
  username: alice
  has_credential: true
  auto_discover: true
  health_check_seconds: 60
```

配置在加载时全量校验：手改出的非法值会立刻报错并指明字段，而不是在运行时变成难以定位的故障。NAS 密码存在系统钥匙串里，配置文件只记录 `has_credential` 标记它存在。

## 依赖

版本全部固定（见 `pyproject.toml`），需要 Python 3.12。

| 依赖 | 用途 |
|------|------|
| fastapi + uvicorn | HTTP 服务 |
| faiss-cpu | 向量索引 |
| torch + transformers | Chinese-CLIP 图文双塔编码 |
| sentence-transformers | 多语言文本编码 |
| rapidocr-onnxruntime | 中文 OCR（PaddleOCR 模型的 ONNX 移植，不占 torch 显存预算） |
| av | 视频解码与抽帧 |
| pypdf / pypdfium2 / python-docx | 文档解析 |
| pillow | 图片解码与缩略图 |
| zeroconf / keyring | NAS 自动发现与凭据存储（模式 B，尚未接入） |

Chinese-CLIP 经 `transformers.ChineseCLIPModel` 加载，而不是官方 `cn-clip` 包：后者硬依赖 `lmdb`，而 `lmdb` 在 Windows + CPython 3.12 上没有可用 wheel，会让安装直接失败。模型权重不变，只换加载途径。

开发依赖：`pytest` + `pytest-cov`（测试与覆盖率）、`ruff`（lint 与格式化）、`mypy`（strict 模式类型检查）、`httpx`（驱动 TestClient）。
