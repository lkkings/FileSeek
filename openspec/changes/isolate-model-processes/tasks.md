## 1. Worker 进程基础设施

- [x] 1.1 新增 worker 消息协议模块，包含 `TaskSpec`、`ChunkPayload`、`TaskResult` 和消息类型（progress/result/error/idle_exit/shutdown）。验证：单测对每种消息做 pickle 往返，结果与原对象相等。
- [x] 1.2 实现 `WorkerHandle`：用 spawn 启动进程，持有 duplex Pipe，提供 `ensure_started()`、`is_alive()`、`terminate(grace)`，以及按 exitcode 区分空闲退出、被信号杀死、非 0 退出。验证：单测用一个简单的 echo worker 分别覆盖启动、正常退出、`os.kill(SIGKILL)` 和 `os.abort()` 四种情况，并断言 handle 判定出的状态类型正确。
- [x] 1.3 在 `WorkerHandle` 中实现连续崩溃冷却：60 秒内崩溃 3 次后冷却 30 秒（D5）。主动终止不计入崩溃次数。验证：用可注入时钟的单测覆盖。
- [x] 1.4 在 worker 主循环中实现空闲退出，用 `poll(idle_timeout)` 控制，超时为 0 时不退出。另外处理 D6 描述的空闲退出与新请求同时发生的竞态：检测到后重启进程并只重试一次。验证：用 idle_timeout=0.2s 的单测断言进程以 exitcode 0 退出、不产生错误日志，且紧接着发出的请求仍能成功。
- [x] 1.5 在 `settings.py` 中新增 `task_worker_idle_timeout`（默认 300）和 `query_worker_idle_timeout`（默认 900），取值必须 ≥0，0 表示不退出。验证：settings 单测和环境变量覆盖测试均通过。
- [x] 1.6 在 `__main__.py` 的 `main()` 开头调用 `multiprocessing.freeze_support()`；worker 入口调用 `configure_logging()`，日志格式中带上进程名。验证：执行 `python -m fileseek --help`，行为不变；worker 的日志出现在同一个日志文件中。

## 2. Handler 拆分为 compute / persist

- [x] 2.1 在 `FileHandler` 基类中定义 `compute(spec, progress) -> TaskResult`，把原先直接修改 task 的写入逻辑去掉。验证：mypy 对 handlers 包检查通过。
- [x] 2.2 把 `DocumentHandler` 拆开：compute 负责抽取、编码和分类，返回 chunks、向量和标签，不再依赖 `vector_index`。验证：更新后的 `tests/tasks` 文档用例通过，并断言 compute 期间没有调用 vector_index。
- [x] 2.3 按同样方式拆分 `ImageHandler`，OCR 和 embedding 都放在 compute 里。验证：图片相关用例通过。
- [x] 2.4 按同样方式拆分 `VideoHandler`，抽帧和 embedding 都放在 compute 里。验证：视频相关用例通过。
- [x] 2.5 在 `TaskProcessor` 中新增 `persist(task, result, progress)`：按 batch 调用 `add_batch`，依次执行 `add_file_chunks`、`add_file_tags`，并上报 INDEXED 进度；ID 规则仍为 `{file_id}_{index}`。验证：单测断言写入的 ID、metadata 和进度序列与改造前一致。

## 3. 导入进程接入调度器

- [x] 3.1 实现 `run_task_worker(conn, config)`：在子进程内用现有工厂构建 parser、embedding、OCR 和 classifier；对每个收到的 `TaskSpec` 执行 `compute`，进度通过 Pipe 发回；Python 异常以 error 消息发回，处理完成后删除 temp 文件。验证：集成测试在真实子进程中处理一个小的 txt fixture，收到 result。
- [x] 3.2 改造 `TaskScheduler._execute_task`：把 run_in_executor 换成向 `WorkerHandle` 发送 `TaskSpec`，在轮询 Pipe 的同时 drain 进度并检查进程是否存活；收到 result 后调用 `persist`，收到 error 后执行 `mark_failed`。删除 `ThreadPoolExecutor`、`_PROGRESS_FINAL_GRACE` 和 `_close_progress_queue`，并同步更新模块 docstring。验证：`tests/tasks` 全部通过。
- [x] 3.3 实现崩溃判定：进程在发出 result 之前就退出时，按 D5 的文案 `mark_failed`，下一个任务到来时重新 spawn。验证：集成测试让 worker 在处理某个特殊 fixture 时执行 `os.kill(os.getpid(), SIGKILL)`，断言该任务失败、API 进程仍存活，且紧接着的任务成功。
- [x] 3.4 实现终止任务：检测到 `is_cancelled` 后先 terminate，等 3 秒，仍未退出则 kill，然后走 `mark_cancelled` 和 `cleanup`；移除 `QueueProgressReporter` 中的取消检查。验证：集成测试让 worker 在 compute 中 sleep 60 秒，发出终止请求后 5 秒内任务状态变为 cancelled，下一个任务正常完成。
- [x] 3.5 改造 `container.py` 和 `lifespan.py`：API 进程不再为导入构建 embedding、OCR、classifier；按 D12 的顺序关闭时结束导入进程。验证：用 `tests/api` 启动应用、执行 lifespan 关闭，不留下子进程，可用 `psutil.Process().children()` 断言为空。

## 4. 查询进程

- [x] 4.1 实现 `run_query_worker(conn, config)`：只构建文本 embedding，启动后先执行一次 warmup 推理，然后循环处理查询请求。验证：集成测试启动子进程后发送查询，返回 1024 维且已归一化的向量。
- [x] 4.2 实现 `QueryEmbeddingClient`，满足 `EmbeddingPort.embed_text` 的签名：请求间用锁串行化，单次超时 30 秒；超时或崩溃时结束进程并抛出 `InferenceError`，下次调用时重新启动进程。验证：单测覆盖正常返回、超时和崩溃后恢复三种情况。
- [x] 4.3 在 `dependencies.py` 中为 `SearchFilesUseCase` 注入 `QueryEmbeddingClient`，API 进程中不再调用 `get_embedding_service()`；搜索路由把 `InferenceError` 转成前端能识别的错误响应，不降级为空结果。验证：`tests/api` 搜索用例通过，并新增一个用例：查询进程崩溃时返回错误，下一次搜索成功。
- [x] 4.4 新增 `POST /search/warmup` 路由，返回 202，只调用 `ensure_started()`，使用现有 token 鉴权。验证：API 测试断言 202，未带 token 时返回 401，重复调用不会重复启动进程。
- [x] 4.5 在 `lifespan._shutdown` 中向查询进程发送 shutdown，等待 2 秒，超时则 kill。验证：与 3.5 相同的关闭后无子进程断言。

## 5. 文本塔子图

- [x] 5.1 在 `pyproject.toml` 中新增固定版本的 `onnx` 依赖，并执行 `uv lock`。验证：`uv sync` 成功，`python -c "import onnx"` 可以运行。
- [x] 5.2 在 `model_cache.py` 中实现文本塔子图生成：用 `onnx.utils.Extractor` 抽取 `input_ids → l2norm_text_embeddings`，写入临时文件后 rename 为 `model_quantized.text.onnx`，失败时记录 warning 并返回 None。验证：在本机实际生成子图，检查其输入只有 `input_ids`，并记录文件大小。
- [x] 5.3 给 `JinaClipV2Embedding` 增加 `text_only` 参数：优先加载子图，失败时回退到联合模型；查询进程中启用该参数。验证：单测断言子图不存在时会回退；在真实模型上对 20 条查询比较子图和联合模型的向量，余弦相似度不低于 0.9999。
- [x] 5.4 实测查询进程加载子图后的常驻 RSS，把结果更新到 design.md D11 中替换估算值。验证：design.md 中写入实测数字。

## 6. 前端预热

- [x] 6.1 在 `desktop/src/services/api/search.ts` 中新增 `warmup()`，调用 `POST /search/warmup`。验证：`api-contracts.test.ts` 新增用例并通过。
- [x] 6.2 给 `SearchBar` 输入框加上 `onFocus` 调用预热：30 秒内节流，失败时静默处理，不影响输入。验证：组件测试断言聚焦时调用 warmup，30 秒内再次聚焦不会重复调用，warmup 请求被拒时界面不出现错误提示。

## 7. 端到端验证

- [x] 7.1 通过真实应用导入 `/Users/lkkings/Downloads/PDF32000_2008.pdf`，任务完成，789 个 chunk 可以被检索到；处理期间多次搜索都在 2 秒内返回（查询进程已预热）。验证：记录任务耗时、两个进程的峰值 RSS 以及搜索延迟。
- [x] 7.2 崩溃演练：导入过程中用 `kill -9` 杀掉导入进程，确认该任务失败、应用和搜索都正常、后续任务可以继续处理；再用 `kill -9` 杀掉查询进程，确认导入不受影响，下一次搜索恢复。验证：记录两次演练的结果。
- [x] 7.3 空闲退出演练：把两个 idle timeout 临时设为 30 秒，导入完成且停止搜索后，确认两个子进程都退出，API 进程的 RSS 回落到不含模型的水平；聚焦搜索框后查询进程被重新拉起。验证：记录各阶段的 RSS 和进程列表。
- [x] 7.4 运行后端完整测试、ruff、mypy 以及前端测试。验证：除本变更之前已存在的失败（`test_search_ranking` 权重断言、`compatibility-tests` fixture 差异）外全部通过，且 ruff 和 mypy 不新增错误。
