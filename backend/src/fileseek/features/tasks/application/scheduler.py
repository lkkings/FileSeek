"""任务调度器。

后台轮询队列，取出待处理任务并交给处理器执行。

关闭顺序是固定的：先停止取新任务，再等在飞的任务落地，最后才让进程退出。反过来
做（直接 cancel）会把一个正在写向量的任务拦腰截断，留下一个状态是 processing、
却再没有人推进的任务——下次启动它既不在队列里，也永远不会完成。

超时仍未结束的任务放回 `queued` 而非判失败：它的文件没动过、已完成阶段也保留，
下次启动继续，而不是要用户重新添加一遍。

任务跑成功之后在这里登记文件库记录。登记用的 id 就是 `task.id`——向量是按这个 id 落盘的
（见 `TaskProcessor._describe_file`），检索也按这个 id 回给前端做预览地址。两边不一致的话
每条搜索结果都指向一个查不到的文件。登记失败判任务失败而不是完成：只有向量没有库记录的
任务从界面上看是"成功"的，用户没有任何补救途径；判失败它至少还能重试。

计算跑在独立的导入模型子进程里，写入留在这里。PDF 解析、ONNX 推理、OCR、视频解码都是
原生代码，它们 abort 或内存耗尽被系统杀掉时，线程方案会把整个服务进程一起带走；放到子进程
里，崩溃只让当前任务失败，下一个任务到来时子进程按需重启。

不用进程池：派发绑定方法要 pickle 整个 `TaskProcessor`，连带模型懒加载用的
`threading.Lock` 和 Chroma 原生句柄一起序列化而失败；子进程拿到的也只是 `task` 的副本。
所以子进程只收纯数据 `TaskSpec`、只回纯数据 `TaskResult`，模型在子进程里自己构建；
`task` 实例始终只在这里，进度一到就推进、落库。

向量库也只在这里写：Chroma `PersistentClient` 不支持多进程并发写，而回收站删除同样在
服务进程里写它。

终止任务直接结束子进程：计算可能正卡在一次长推理里，等它下一次上报进度才检查取消，
用户要等上几分钟。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime

from fileseek.config.constant import QUERY_CACHE_KEY
from fileseek.features.library.domain.repositories import FileChunkRepository, FileRepository
from fileseek.features.tasks.application.cancellation import (
    TaskCancellationRegistry,
)
from fileseek.features.tasks.application.compute import (
    TaskComputeFailedError,
    TaskComputePort,
    TaskResult,
)
from fileseek.features.tasks.application.processor import TaskProcessor
from fileseek.features.tasks.application.progress_reporter import CallbackProgressReporter
from fileseek.features.tasks.domain.entities import Task, TaskProgress, TaskStatus
from fileseek.features.tasks.domain.exceptions import TaskCancelledError
from fileseek.features.tasks.domain.repositories import TaskRepository
from fileseek.shared.infrastructure.worker import WorkerCrashedError, WorkerUnavailableError
from fileseek.shared.utils.cache import TTLLRUCache

logger = logging.getLogger(__name__)

# 关闭时等待在飞任务落地的默认时限。够一个阶段落地，又短到从托盘退出时
# 感觉是"退了"而不是"卡住了"。
DEFAULT_DRAIN_TIMEOUT = 10.0

# drain 轮询间隔。相对超时足够小，所以最常见的情况（没有在飞任务）立刻返回。
_DRAIN_POLL_INTERVAL = 0.05

# 在飞任务的轮询间隔。管道读空时睡这么久再来一轮：足够小，进度看起来是实时涨的；
# 又不至于空转烧 CPU。
_PROGRESS_POLL_INTERVAL = 0.02


class TaskScheduler:
    """任务调度器，后台轮询并派发任务给处理器。"""

    def __init__(
        self,
        task_repo: TaskRepository,
        file_repo: FileRepository,
        file_chunk_repo: FileChunkRepository,
        processor: TaskProcessor,
        compute: TaskComputePort,
        poll_interval: float,
        cache: TTLLRUCache[str, object],
        cancellation_registry: TaskCancellationRegistry,
    ) -> None:
        self.task_repo = task_repo
        self.file_repo = file_repo
        self.file_chunk_repo = file_chunk_repo
        self.processor = processor
        self.compute = compute
        self.cache = cache
        self._cancellation_registry = cancellation_registry
        self.poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task[None] | None = None
        # 是否还接新任务。和 _running 分开：关闭时先停止领取，但循环还要把
        # 手上那个任务跑完。
        self._accepting = True
        # 同时在飞的任务数，只会是 0 或 1：导入子进程只有一个，每多一个就多一份约 2GB 的
        # 模型，而 ONNX Runtime 在单进程内已经会用满多核。
        self._active = 0

    @property
    def is_running(self) -> bool:
        """调度循环是否还在跑。"""
        return self._running

    @property
    def active_count(self) -> int:
        """当前正在处理的任务数。"""
        return self._active

    def start(self) -> None:
        """启动调度器后台循环。"""
        if self._running:
            return
        self._running = True
        self._accepting = True
        logger.info("调度器已启动")
        self._task = asyncio.create_task(self._run_loop())

    def stop_accepting(self) -> None:
        """停止领取新任务，已在飞的任务不受影响。"""
        self._accepting = False

    async def shutdown(self, timeout: float = DEFAULT_DRAIN_TIMEOUT) -> tuple[str, ...]:
        """优雅关闭：停止领取 → 等在飞任务落地 → 放回超时未落地的任务。

        Returns:
            被放回队列的任务 id；常见情况下为空（一切都自己跑完了）。
        """
        self.stop_accepting()

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        # 至少让出一次控制权：timeout 比轮询间隔还小时，下面的循环可能一次都不执行，
        # 于是刚被领走的任务连"开始跑"的机会都没有就被当成滞留任务放回去。
        await asyncio.sleep(0)
        while self._active > 0 and loop.time() < deadline:
            await asyncio.sleep(_DRAIN_POLL_INTERVAL)

        self._running = False
        if self._task is not None:
            self._task.cancel()
            # 等 cancel 真正生效，否则进程可能先退出，留下"Task was destroyed
            # but it is pending"，更要紧的是在飞的那一步没机会收尾。
            #
            # release_stranded 必须在这之后跑：cancel 落在 _execute_task 的等待点上，
            # 它的 finally 会先把任务落库一次；放在前面会和那次写互相打架。
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        # 超时仍在算的任务：结束子进程，任务由下面的 release_stranded 放回队列，下次启动
        # 重新计算。子进程是 daemon，不结束它服务进程也会带走它，这里显式做是为了等它退干净。
        try:
            self.compute.shutdown()
        except Exception:  # noqa: BLE001
            logger.exception("导入模型进程关闭失败")

        return await self.release_stranded()

    def stop(self) -> None:
        """立即停止调度器，不等在飞任务。

        只在拿不到事件循环的场合用（比如同步的清理路径）；正常关闭走 shutdown()。
        """
        self._running = False
        self._accepting = False
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def release_stranded(self) -> tuple[str, ...]:
        """把状态停在 processing 的任务放回队列。

        两个场合需要它：关闭时超时未落地的任务，以及上次运行崩溃遗留的任务
        （没有它，那些任务永远不会被 claim_next_queued 取到）。
        """
        released: list[str] = []
        page = 1
        while True:
            tasks, total = await self.task_repo.list_all(TaskStatus.PROCESSING, page, 100)
            if not tasks:
                break
            for task in tasks:
                task.release()
                task.updated_at = datetime.now()  # noqa: DTZ005
                await self.task_repo.save(task)
                released.append(task.id)
            if len(released) >= total:
                break
            # 不递增 page：放回后这些任务已不在 processing 里，下一页会顶上来。

        if released:
            logger.info("已将 %d 个在飞任务放回队列: %s", len(released), released)
        return tuple(released)

    async def _run_loop(self) -> None:
        """调度器主循环：轮询队列，取出任务并处理。"""
        while self._running:
            try:
                logger.info("等待任务")
                await self._process_next()
            except Exception:
                import traceback

                traceback.print_exc()
                logger.exception("执行任务报错")
            finally:
                await asyncio.sleep(self.poll_interval)

    async def _process_next(self) -> None:
        """处理下一个排队中的任务。"""
        if not self._accepting:
            return
        # 导入进程连续崩溃冷却中：任务先留在队列里，冷却结束再领，不把它们一个个判失败。
        if self.compute.in_cooldown():
            return

        task = await self.task_repo.claim_next_queued()
        if task is None:
            return

        await self._execute_task(task)

    async def _advance(self, task: Task, progress: TaskProgress) -> None:
        """推进任务阶段并落库。

        进度落库失败不往外抛：进度是派生信息，一次写冲突不该让一个已经抽完取、编完码的
        任务判失败——重试要把这些活全部重做一遍。任务终态由 `_execute_task` 的 finally
        那次保存决定。

        不吞 `advance_stage` 之外的错误类型之前的行为：状态机错误同样记日志而不是静默。
        """
        try:
            task.advance_stage(progress)
            task.updated_at = datetime.now()  # noqa: DTZ005
            await self.task_repo.save(task)
        except Exception:
            logger.exception(
                "任务 %s 的进度落库失败（stage=%s），处理继续",
                task.id,
                getattr(progress.stage, "value", progress.stage),
            )

    async def _await_compute(self, task: Task) -> TaskResult:
        """等子进程算完：一边推进进度，一边盯着取消请求和子进程死活。

        Raises:
            TaskCancelledError: 用户终止了任务（子进程已被结束）
            TaskComputeFailedError: 子进程里的计算抛了 Python 异常
            WorkerCrashedError: 子进程在给出结果前退出了
        """
        while True:
            if self._cancellation_registry.is_cancelled(task.id):
                # 计算可能正卡在一次长推理里，等它自己检查取消要几分钟；直接结束进程。
                await asyncio.to_thread(self.compute.terminate)
                raise TaskCancelledError(task.id)

            event = self.compute.poll()
            if event is None:
                await asyncio.sleep(_PROGRESS_POLL_INTERVAL)
                continue
            if isinstance(event, TaskProgress):
                await self._advance(task, event)
                continue
            if isinstance(event, TaskResult):
                return event
            if isinstance(event, BaseException):
                raise event
            logger.warning("任务 %s 收到未知事件: %r", task.id, event)

    async def _persist(self, task: Task, result: TaskResult) -> None:
        """把计算结果写进向量库和文件实体，INDEXED 进度就地推进。"""
        pending: list[TaskProgress] = []
        reporter = CallbackProgressReporter(pending.append)
        # 向量写入是同步 IO，放线程里跑，别卡住事件循环。
        await asyncio.to_thread(self.processor.persist, task, result, reporter)
        for progress in pending:
            await self._advance(task, progress)

    async def _execute_task(self, task: Task) -> None:
        """执行单个任务，处理成功/失败均落库。

        任务在 claim_next_queued() 中已被原子标记为 PROCESSING，此处直接派发给子进程。
        """
        self._active += 1
        cancelled = False
        try:
            if self._cancellation_registry.is_cancelled(task.id):
                task.mark_cancelled()
                self.processor.cleanup(task)
                cancelled = True
            else:
                await asyncio.to_thread(self.compute.submit, self.processor.build_spec(task))
                result = await self._await_compute(task)
                if self._cancellation_registry.is_cancelled(task.id):
                    raise TaskCancelledError(task.id)  # noqa: TRY301 - 与计算阶段的终止走同一收尾分支
                await self._persist(task, result)
                task.mark_completed()
                await self.cache.clear(QUERY_CACHE_KEY)
        except TaskCancelledError:
            logger.info("任务 %s 已被用户终止", task.id)
            task.mark_cancelled()
            self.processor.cleanup(task)
            cancelled = True
        except TaskComputeFailedError as exc:
            if exc.error_type == "NotImplementedError":
                logger.warning("任务 %s 处理器功能尚未实现: %s", task.id, exc)
                task.mark_failed(f"处理器功能尚未实现: {exc}")
            else:
                logger.error("任务 %s 处理失败: %s", task.id, exc)  # noqa: TRY400 - 堆栈在子进程
                task.mark_failed(str(exc))
        except WorkerCrashedError as exc:
            # 已写入的部分向量没有对应的库记录，留着就成了搜得到却打不开的孤儿。
            logger.error("任务 %s 处理失败: %s", task.id, exc)  # noqa: TRY400 - 进程已不在，没有可用堆栈
            task.mark_failed(str(exc))
        except WorkerUnavailableError as exc:
            # 刚领到任务，导入进程就进了冷却：放回队列，冷却结束后再试，不算这个文件的错。
            logger.warning("任务 %s 暂缓处理: %s", task.id, exc)
            task.release()
        except Exception as exc:  # noqa: BLE001
            logger.exception("任务 %s 处理失败", task.id)
            task.mark_failed(str(exc))
        finally:
            task.updated_at = datetime.now()  # noqa: DTZ005
            await self.task_repo.save(task)
            if not cancelled and task.status is not TaskStatus.QUEUED:
                await self.file_repo.save(task.file)
                await self.file_chunk_repo.save_batch(task.file.chunks)
            self._cancellation_registry.remove(task.id)
            self._active -= 1
