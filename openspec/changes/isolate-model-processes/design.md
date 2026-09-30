## Context

动机见 proposal.md 的 Why 一节，需求见 `specs/`。本文只记录会影响实现方式的现状：

- `TaskScheduler`（`features/tasks/application/scheduler.py`）通过 `ThreadPoolExecutor` 调用 `TaskProcessor.process(task, progress_queue)`，同一个 `task` 对象在两个线程之间共享。handler 在线程里直接修改 `task.file.tags`、`task.file.chunks`，scheduler 在 `finally` 里把它们落库。
- 模块 docstring 已经说明不用进程池的原因：绑定方法里带着 `threading.Lock` 和 Chroma 原生句柄，无法 pickle；子进程拿到的也只是 `task` 的副本。
- `DocumentHandler`、`ImageHandler`、`VideoHandler` 都是"算完就写"，在第 4 步直接调用 `vector_index.add_batch`。
- `ChromaVectorStore` 使用 `PersistentClient`（本地 SQLite 加索引文件），API 进程里的回收站删除也会写它。
- 分类器（`infrastructure/classifier/factory.py`）通过 `get_embedding_service()` 复用 embedding 实例来计算标签向量，所以分类只能和导入 embedding 放在同一个进程里。
- 搜索（`search_files.py:141`）通过 `run_in_threadpool` 调用 `embedder.embed_text(query, query=True)`，查询结果已有 `QUERY_CACHE_KEY` 缓存。
- 后端以 `python -m fileseek` 作为 sidecar 启动，仓库里没有 PyInstaller 或 Nuitka 配置。
- 实测数据（本机 macOS，jina-clip-v2 int8 联合模型 874MB）：
  - 加载后 RSS 约 1.9GB，冷启动 4 到 6 秒。
  - 在进程内置空 session 再 gc，只能回到 870 到 1392MB，`malloc_zone_pressure_relief` 归还 0MB。
  - 每做一轮"卸载再加载"，底数上涨约 260MB。

## Goals / Non-Goals

**Goals:**
- 原生层的任何崩溃都只让当前任务失败，或让本次搜索报错，uvicorn 进程不退出。
- 导入和搜索各用一个独立进程，一方忙碌或崩溃时另一方不受影响。
- 空闲时两个模型进程都退出，API 进程常驻内存只保留框架和数据库部分。
- 前端任务进度、终止任务和优雅关闭的行为与现在一致，只有终止任务变得更及时。

**Non-Goals:**
- 不限制子进程内存的硬上限（macOS 上 `RLIMIT_AS` 基本不起作用）。按 RSS 阈值主动杀进程留作后续可选项。
- 不支持多个导入 worker 并发，保持现有的 `max_workers` 语义（见 D8）。
- 不做进程内的模型空闲卸载。
- 不改变 embedding 数值、分块策略或检索排序。

## Decisions

### D1. 两个专用子进程，不用进程池
- **导入进程**（`TaskWorker`）：负责解析、embedding（联合模型）、OCR、分类和视频抽帧。
- **查询进程**（`QueryWorker`）：只加载文本 embedding。
- 两个进程都由 API 进程里的一个管理器对象（`WorkerHandle`）持有，统一负责启动、健康检查、空闲状态和结束进程。
- 备选方案：
  - `ProcessPoolExecutor` + initializer：子进程一崩就是 `BrokenProcessPool`，整个池都要重建，而且没法单独杀掉某个任务所在的进程。
  - 每个任务起一个新进程：每个任务都要付 4 到 6 秒的模型加载，批量导入图片时不可接受。
  - 把整个任务子系统拆成独立 sidecar：Tauri 要多管理一个进程，Chroma 仍然会被两个进程访问，收益和成本不成比例。

### D2. 用 spawn 启动，子进程自己构建依赖，跨进程只传纯数据
- `multiprocessing.get_context("spawn")`。不用 fork：API 进程里已有 asyncio 事件循环、Tortoise 连接池和原生线程，fork 之后状态不确定。
- 子进程入口是模块级函数 `run_task_worker(conn, config)` / `run_query_worker(conn, config)`。进程里用现有的工厂函数（`get_embedding_service()`、`get_ocr_service()`、`DocumentParser(...)`、`ClassifierFactory`）构建依赖，因此 `threading.Lock` 和原生句柄都不需要 pickle。
- 传给子进程的 `config` 是 `Settings` 里相关字段组成的 dict，不传整个 `Settings` 对象，以免把环境变量解析逻辑带进子进程。
- 跨进程只传以下两类 dataclass（字段都可以 pickle）：
  - 请求：`TaskSpec`（`task_id`、`temp_path`、`file_type`、`metadata`，含分类标签快照）。
  - 结果：`TaskResult`（`chunks: list[ChunkPayload]`、`vectors: np.ndarray[float32]`、`tags: list[str]`）。
- 数据量估算：`PDF32000_2008.pdf` 有 789 个 chunk，789×1024×4 字节约 3.2MB，加上文本约 3MB，走 `Connection.send` 没有问题。视频帧向量更少。

### D3. Handler 拆成 `compute` 和 `persist` 两段
- `FileHandler` 新增 `compute(spec, progress) -> TaskResult`，只在子进程里运行。它包含现有 `process()` 的第 1 到 3 步（抽取、编码、分类）。
- 写入部分（现有第 4 步：`vector_index.add_batch`、`task.add_file_chunks`、`task.add_file_tags`）移到主进程的 `TaskProcessor.persist(task, result, progress)`，按 batch 写入，并上报 INDEXED 进度。这样 INDEXED 阶段的进度来源从子进程变为主进程，前端看到的行为不变。
- ID 规则保持 `f"{task.file.id}_{index}"` 不变，这样现有的 `cleanup` 和预览逻辑都不用改。
- 备选方案：让子进程也连 Chroma 直接写入。被否决，理由是 Chroma `PersistentClient` 不支持多进程并发写，而回收站删除正是在 API 进程里写 Chroma。

### D4. 进度和结果共用一条 Pipe，消息带类型
- 每个 worker 使用一对 `multiprocessing.Pipe(duplex=True)`。子进程发送的消息有三种：`("progress", TaskProgress)`、`("result", TaskResult)`、`("error", message, traceback_str)`。
- 主进程的 `_execute_task` 保留现有的"轮询加 drain"结构，只把 `queue.Queue.get_nowait()` 换成 `conn.poll(0)` 加 `conn.recv()`。`_drain_progress` 里吞异常的策略、`advance_stage` 和落库逻辑都不变。
- 不再使用 `multiprocessing.Queue`，改用 Pipe，原因有两点：
  - 省去 feeder 线程，以及现有的 `_PROGRESS_FINAL_GRACE`、`cancel_join_thread` 这些补丁。
  - 同一条连接上的消息天然有序，result 一定排在最后一条 progress 之后。
- 子进程里的 Python 异常（比如 `ValueError: 任务缺少元数据`）会被捕获并以 `error` 消息发回，主进程照旧调用 `task.mark_failed(message)`，行为和现在一致。

### D5. 崩溃判定与重启
- 主进程在等待期间，除了 `conn.poll`，还检查 `process.is_alive()` 和 `process.exitcode`。
- 进程在"没有发出 result 或 error"的情况下退出，就判定为崩溃：
  - `exitcode < 0`（被信号杀死）：失败原因写 `处理进程异常退出（signal {name}），可能是内存不足或原生库崩溃`。
  - `exitcode > 0`：失败原因写 `处理进程异常退出（exit {code}）`。
- 崩溃后主进程把这个 `WorkerHandle` 标记为已死亡，下一次需要时（`claim_next_queued` 拿到任务时，或下一次搜索时）再重新 spawn，不在崩溃当下立刻重启，避免同一个文件导致反复崩溃、进程被连续拉起。
- 连续崩溃保护：同一个 `WorkerHandle` 在 60 秒内崩溃 3 次，就进入 30 秒冷却，冷却期间搜索直接返回错误。任务不在冷却期内领取，仍留在队列里。

### D6. 空闲退出由子进程自己决定
- 子进程主循环调用 `conn.poll(idle_timeout)`。超时时没有收到消息，就发送 `("idle_exit",)` 后 `sys.exit(0)`。
- 主进程收到 `idle_exit`，或看到 `exitcode == 0`，把这个 handle 标为"未运行"，不算作崩溃，也不写错误日志。
- 竞态处理：主进程刚发出请求、子进程恰好在同一时刻空闲退出时，主进程会发现 `exitcode == 0` 而且请求没有得到响应。这种情况只重试一次：重启子进程并重新发送同一个请求。第二次仍失败时，按 D5 判定为崩溃。
- 超时设为 0 时，调用 `conn.poll(None)`，子进程一直阻塞等待，不会空闲退出。

### D7. 终止任务改为结束导入进程
- `TaskCancellationRegistry` 保持不变。scheduler 在轮询循环里发现 `is_cancelled(task.id)` 后：
  1. 调用 `process.terminate()`（SIGTERM），最多等 3 秒。
  2. 仍未退出就 `kill()`。
  3. 走现有的 `TaskCancelledError` 分支：`mark_cancelled`，然后 `processor.cleanup(task)`。
- 由于写入集中在主进程（D3），被终止的任务最多写入了此前 `persist` 完成的部分，`cleanup` 删除的 ID 集合和现在一致。在 `compute` 阶段被终止时，还没有任何写入。
- 这次终止导致的进程退出是主动行为，不计入 D5 的连续崩溃次数。
- `QueueProgressReporter` 里的取消检查在子进程中无法访问主进程的 registry，因此移除。子进程的 reporter 只负责发送进度。

### D8. 保持单个导入进程
- 目前 `max_workers` 控制线程池大小。改造后导入进程只有一个，`max_workers` 的语义改为"同时在飞的任务数"，固定为 1。
- 理由：
  - 每多一个导入进程，就多一份约 1.9GB 的模型。
  - ONNX Runtime 在单个进程内已经会用满多核（实测 user 时间约 3454 秒，real 约 744 秒，也就是约 4.6 核）。
- 如果以后要并发，可以扩展成 N 个 `TaskWorker`，不影响本设计的接口。

### D9. 查询进程与搜索用例的接口
- 新增 `QueryEmbeddingClient`，实现现有 `EmbeddingPort` 中 `embed_text` 的 query 用法。`dependencies.py` 把它注入 `SearchFilesUseCase`，替换 `get_embedding_service()`。这样搜索用例的代码不变，现有测试里的 fake embedder 仍然可用。
- 请求在 `run_in_threadpool` 中同步调用 `send` 和 `recv`。用一把 `threading.Lock` 把同一时刻的请求串行化，因为搜索是交互操作，并发量很低。单次超时 30 秒，包含冷启动时间。超时后结束查询进程，本次搜索返回错误。
- 查询进程崩溃或超时时，抛出 `InferenceError`，搜索路由返回可识别的错误码。前端现有的错误提示逻辑可以复用。
- `search_files.py` 已经会捕获 `NotImplementedError` 并降级处理。查询进程的错误不走这条降级路径，因为静默返回空结果会让用户误以为"没有搜到"。

### D10. 预热接口
- 新增 `POST /search/warmup`，返回 `202`。处理函数只调用 `QueryEmbeddingClient.ensure_started()`，也就是在进程未运行时执行 spawn，立即返回，不等待模型加载。
- 为了让模型在后台加载，子进程启动后立即执行一次 `embed_text(["warmup"], query=True)`。这样 session 和 tokenizer 都会被加载，JIT 和 arena 也会完成首次分配。
- 这个接口与其他路由共用现有的 token 鉴权，不新增匿名入口。
- 前端：`SearchBar` 的输入框加上 `onFocus` 处理，调用 `searchApi.warmup()`。同一组件内 30 秒节流，失败时静默处理（`catch` 后什么都不做）。

### D11. 文本塔子图
- 生成：首次需要时，或者在模型下载完成后，由 `model_cache.py` 调用 `onnx.utils.Extractor`，以 `input_ids` 为输入、`l2norm_text_embeddings` 为输出，从 `model_quantized.onnx` 中抽取子图，保存为缓存目录下的 `model_quantized.text.onnx`。
- 为了保证原子性，先写入 `.tmp` 文件再 `rename`。生成失败时记录 warning 并回退到联合模型，不阻塞搜索。
- 加载：`JinaClipV2Embedding` 新增可选参数 `text_only: bool`，只在查询进程里设为 `True`。
  - 优先加载 `.text.onnx`。
  - 加载成功后，graph 的输入中已经没有 `pixel_values`，现有的 `_build_text_inputs` 会自动跳过构造假图片输入。
  - `_extract_text_embedding` 按名称查找 `l2norm_text_embeddings`，不需要修改。
- 数值一致性：子图与联合模型中文本塔的算子和权重完全相同。实测 20 条中英文查询，两者输出逐位一致（最大绝对差 0.0，余弦 1.00000000）；`tests/infrastructure/test_text_model.py` 以余弦不低于 0.9999 作为回归门槛。
- 依赖：新增 `onnx==1.23.1`（连带 `ml-dtypes`），只在生成子图时 import。
- 子图体积与生成耗时（实测）：537MB（联合模型 874MB），节点 3298 个（联合模型 6259 个），抽取加保存约 1 秒，生成过程峰值 RSS 约 3GB（只在首次发生）。
- 内存（实测，本机 macOS，同一进程加载后再跑 20 条查询，各测 4 次）：
  - 文本塔子图：稳定在 1736 到 1740MB，冷启动约 2.5s。
  - 联合模型（text-only 调用、空 batch 假图片）：1434 到 2325MB，波动很大，冷启动约 3.3 到 3.7s。
  - 结论：常驻内存平均约省 450 到 580MB，并且更稳定；冷启动约快 1 秒。比原先按文件体积比例估算的约 1.2GB 高，因为 tokenizer 和 transformers 加 ORT 运行时本身就占了约 1GB，这部分不随模型文件变小而减少。
- 备选方案：
  - 使用 `satorean/jina-clip-v2-split-onnx`。被否决：它是第三方仓库，输出名称不同，而且导入端仍在使用官方联合模型，两者的向量空间一致性没有保证。
  - 从 PyTorch 重新导出。被否决：已知 `torch.onnx.export` 会遇到 flash-attention 的 `IndexError`。

### D12. 入口与关闭顺序
- 在 `__main__.py` 的 `main()` 最前面调用 `multiprocessing.freeze_support()`。spawn 子进程只 import worker 模块，不会执行 uvicorn 启动代码。
- 关闭时 `lifespan._shutdown` 的顺序如下：
  1. 执行 `scheduler.shutdown()`（原有逻辑：停止领取任务，drain 在飞任务）。在飞任务超时后，结束导入进程，再执行 `release_stranded`。
  2. 向查询进程发送 `("shutdown",)`，等待 2 秒，超时后 `kill()`。
- 子进程设为 `daemon=True`，作为兜底：父进程异常退出时，子进程也随之结束，避免留下孤儿进程。

## Risks / Trade-offs

- [导入和搜索同时进行时有两份模型，查询进程常驻约 1.7GB（实测，见 D11）] → 查询进程使用文本塔子图（D11）；两个进程都会空闲退出，只有在两者同时使用时才会叠加。
- [冷启动导致第一次搜索延迟 4 到 6 秒] → 聚焦搜索框时预热（D10），加上查询缓存，默认 `query_worker_idle_timeout` 设为 15 分钟。
- [导入期间搜索会变慢，因为 CPU 被导入进程占满] → 可以把导入进程的 `intra_op_num_threads` 设为核数减 1，给查询进程留出余量。默认值在实现时实测后确定，具体数值不影响规格。
- [同一个文件反复导致崩溃，任务重试时又崩溃] → 崩溃的任务标记为失败，不会自动重试，由用户决定是否重试。D5 的冷却机制防止进程被连续拉起。
- [空闲退出与新请求之间的竞态] → D6 中只重试一次的逻辑。测试中用很短的 idle timeout 覆盖这种情况。
- [spawn 子进程在冻结打包环境下会重新执行入口] → `freeze_support()`（D12）。当前的发布方式是 `python -m fileseek`，不受影响。
- [Pipe 单条消息过大] → `Connection.send` 对大对象会分块传输，没有硬性上限。如果以后出现超大文档（例如数万个 chunk），可以把 `TaskResult` 改成按 batch 流式回传，接口已预留 `progress` 通道。
- [子进程失去主进程的 log 配置] → worker 入口调用 `configure_logging()`，日志写到同一个日志文件，并在格式中带上进程名。

## Migration Plan

- 不涉及数据迁移：向量 ID、chunk 结构和数据库表都不变。
- 文本塔子图在首次使用时自动生成，老用户升级后不需要手动操作。
- 回滚：恢复到线程池版本即可，已写入的数据完全兼容。

## Open Questions

- `intra_op_num_threads` 在两个进程之间如何分配，需要在实现阶段根据实测确定默认值。它只影响性能，不影响规格和任务拆分。
