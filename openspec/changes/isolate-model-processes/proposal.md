## Why

文件处理（PDF 解析、ONNX 推理、OCR、视频解码）目前在 API 服务进程的线程池里运行。原生层一旦崩溃或内存耗尽被系统杀掉，uvicorn 会跟着退出，整个应用随之终止。已在 `~/Library/Logs/DiagnosticReports/` 找到 12 份 `onnxruntime` 触发的 SIGABRT 报告，处理 `PDF32000_2008.pdf` 时进程也曾被 SIGKILL。此外，查询用的 jina-clip-v2 常驻在 API 进程里，约占 1.9GB。实测表明，在进程内卸载模型只能回收约 55% 的内存，而且每做一轮"卸载再加载"就残留约 260MB，释放内存只能靠进程退出。

## What Changes

- 新增**导入模型进程**：用 spawn 方式启动的常驻子进程，负责文件解析、向量化、OCR 和分类计算，不直接读写 ChromaDB 或 SQLite。
- 新增**查询模型进程**：独立于导入进程的另一个子进程，只负责搜索时的文本向量化。两者互不共享、互不等待，任何一方崩溃或忙碌都不影响另一方。
- API 进程不再加载任何模型，只负责调度、IPC 和写入（ChromaDB 和 SQLite 始终只由 API 进程写）。
- `FileHandler` 拆分为两部分：子进程里的纯计算部分返回 chunks、向量和标签，主进程里的写入部分负责向量入库和登记 chunk。
- 导入进程崩溃（非 0 退出码或被信号终止）时，当前任务标记为失败并记录可读原因，下一个任务到来时自动重启进程；查询进程崩溃时，本次搜索返回错误，下次搜索时自动重启。
- 两个进程都支持**空闲超时退出**。新增配置 `task_worker_idle_timeout`（默认 5 分钟）和 `query_worker_idle_timeout`（默认 15 分钟），设为 0 表示不退出。
- 用户终止任务时可以直接结束导入进程，立即生效，不必等下一次进度上报。
- 新增**预热接口**：前端搜索框获得焦点时调用，提前拉起查询进程并加载模型，尽量消除冷启动带来的等待。
- 新增**文本塔子图**：用 `onnx.utils.Extractor` 从官方联合 ONNX 模型中抽取 `input_ids -> l2norm_text_embeddings` 子图，供查询进程加载，以减小查询进程的内存占用。抽取失败或子图不存在时回退到联合模型。
- 服务入口调用 `multiprocessing.freeze_support()`，兼容以后可能采用的冻结打包方式。
- **不做**：在进程内空闲卸载模型（实测不可行，详见 design.md）。

## Capabilities

### New Capabilities
- `tasks/model-process-isolation`：导入计算在独立子进程中运行、崩溃隔离、崩溃后重启、空闲退出、终止任务时结束进程，以及只由主进程写入存储。
- `search/query-embedding-process`：查询向量化在独立子进程中运行、与导入互不影响、空闲退出、预热接口、优先使用文本塔子图。

### Modified Capabilities
（无：现有 `openspec/specs/` 只有 `recent/access-records`，与本变更无关）

## Impact

- **后端代码**：
  - `features/tasks/application/{scheduler,processor,progress_reporter}.py`
  - `features/tasks/application/handlers/{document,image,video}.py`
  - `features/search/application/use_cases/search_files.py`
  - `features/search/interfaces/http/routers/__init__.py`（新增预热路由）
  - `bootstrap/{container,dependencies,lifespan}.py`
  - `infrastructure/embedding/jina_clip_v2.py`（支持加载文本塔子图）
  - `config/settings.py`
  - `main.py` / `__main__.py`
  - 新增 worker 进程模块
- **前端**：`desktop/src/services/api/search.ts` 新增预热调用；`SearchBar` 在获得焦点时触发预热。
- **依赖**：新增 `onnx`，仅用于抽取文本塔子图。
- **资源**：空闲时 API 进程不占用模型内存；导入和搜索同时进行时，内存中有两份模型（导入用的联合模型约 1.9GB，查询用的文本塔预计更小）。
- **行为**：模型进程退出后的第一次搜索或第一个导入任务会有 4 到 6 秒的冷启动。导入进程崩溃时，只有当前任务失败，服务不会退出。
- **测试**：`tests/tasks` 中依赖线程池和进程内 handler 的测试需要调整；新增崩溃隔离、空闲退出和预热相关的测试。
