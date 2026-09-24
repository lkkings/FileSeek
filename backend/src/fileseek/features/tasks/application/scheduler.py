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

处理跑在线程里而不是进程里。进程池在这里根本跑不通：派发的是 `self.processor.process`
这个绑定方法，pickle 它会连带整个 `TaskProcessor` 一起序列化，而它持有的
`EmbeddingService` 和 `OCRService` 各有一个 `threading.Lock`（用于模型懒加载的互斥），
锁不可 pickle（`cannot pickle '_thread.lock' object`），每个任务都会在派发那一刻就
失败。同理 `ChromaVectorStore` 的原生句柄也不可 pickle。退一步说，即使能 pickle，
子进程推进的也是任务对象的副本，进度永远回不到父进程。线程共享同一个 `task` 实例，
处理器每推进一个阶段就能立刻落库。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import queue
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from fileseek.features.tasks.domain.entities import Task, TaskStatus
from fileseek.features.tasks.domain.repositories import TaskRepository
from fileseek.features.tasks.application.processor import TaskProcessor

logger = logging.getLogger(__name__)

# 关闭时等待在飞任务落地的默认时限。够一个阶段落地，又短到从托盘退出时
# 感觉是"退了"而不是"卡住了"。
DEFAULT_DRAIN_TIMEOUT = 10.0

# drain 轮询间隔。相对超时足够小，所以最常见的情况（没有在飞任务）立刻返回。
_DRAIN_POLL_INTERVAL = 0.05

# 在飞任务的进度轮询间隔。队列读空时睡这么久再来一轮：足够小，进度看起来是实时涨的；
# 又不至于空转烧 CPU。
_PROGRESS_POLL_INTERVAL = 0.02

# 收尾那次读队列的宽限。`queue.Queue.put` 把对象交给 feeder 线程就返回了，处理器 return
# 的那一刻最后几条进度很可能还在管道里没过来。给一点时间等它们，否则任务阶段会停在
# 倒数第二个（encoded 而不是 indexed）。
_PROGRESS_FINAL_GRACE = 0.5


class TaskScheduler:
    """任务调度器，后台轮询并派发任务给处理器。"""

    def __init__(
        self,
        task_repo: TaskRepository,
        processor: TaskProcessor,
        poll_interval: float = 2.0,
        max_workers: int = 1,
    ) -> None:
        self.task_repo = task_repo
        self.processor = processor
        self.poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task[None] | None = None
        # 是否还接新任务。和 _running 分开：关闭时先停止领取，但循环还要把
        # 手上那个任务跑完。
        self._accepting = True
        self._active = 0
        self._max_workers = max_workers
        # 线程池而非进程池，原因见模块 docstring：派发的是 processor.process 这个绑定
        # 方法，进程池要 pickle 它，会连带 EmbeddingService / OCRService 持有的
        # threading.Lock 一起序列化而失败。
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="fileseek-task",
        )

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
            # 注意 asyncio.to_thread 起的线程取消不了：如果此刻正卡在 processor.process
            # 里，这里会一直等到那一步自己返回、_execute_task 的 finally 落库之后才继续。
            # 所以 release_stranded 必须在这之后跑——放在前面会把一个马上就要写回
            # completed 的任务先放回 queued，两次写互相打架。
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

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
            tasks, total = await self.task_repo.list_all(TaskStatus.PROCESSING.value, page, 100)
            if not tasks:
                break
            for task in tasks:
                task.release()
                task.updated_at = datetime.now().isoformat()  # noqa: DTZ005
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
            except Exception as e:
                import traceback
                traceback.print_exc()
                logger.exception(f"执行任务报错: {e}")
            finally:
                await asyncio.sleep(self.poll_interval)

    async def _process_next(self) -> None:
        """处理下一个排队中的任务。"""
        if not self._accepting:
            return

        task = await self.task_repo.claim_next_queued()
        if task is None:
            return

        await self._execute_task(task)

    async def _drain_progress(
        self,
        task: Task,
        progress_queue: queue.Queue,
        grace: float = 0.0,
    ) -> bool:
        """把队列里现有的进度全部取出来推进并落库。

        Args:
            task: 正在处理的任务，阶段直接推进在它身上
            progress_queue: 处理器写进度的队列
            grace: 队列读空之后还要再等多久。`queue.Queue.put` 不是同步写管道的，它把对象
                交给一个 feeder 线程后立刻返回，所以"读到空"不等于"没有进度了"——刚
                put 进去的那条可能还在路上。收尾那次必须给一点宽限，否则任务的阶段会
                停在倒数第二个。在飞循环里用 0：那里读空本来就该去睡一小会儿再来。

        Returns:
            是否至少取到一条。取到了就立刻再读一轮，不必先睡——积压的进度应该尽快落库。

        只捕获 `queue.Empty`：那才是"暂时没有新进度"。捕获 `Exception` 会把
        `advance_stage` 的状态机错误、仓储的写失败一起吞掉，看起来只是队列空了，
        于是进度永远不前进而日志里一片干净。

        进度落库失败不往外抛：进度是派生信息，一次写冲突不该让一个已经抽完取、编完码的
        任务判失败——重试要把这些活全部重做一遍。任务终态由 `_execute_task` 的 finally
        那次保存决定。
        """
        drained = False
        deadline = time.monotonic() + grace
        while True:
            try:
                progress = progress_queue.get_nowait()
            except queue.Empty:
                # 用 get_nowait + sleep 而不是 get(timeout=...)：后者会把事件循环
                # 整个阻塞住，期间连别的协程都跑不了。
                if time.monotonic() < deadline:
                    await asyncio.sleep(_PROGRESS_POLL_INTERVAL)
                    continue
                return drained

            drained = True
            try:
                task.advance_stage(progress)
                task.updated_at = datetime.now().isoformat()  # noqa: DTZ005
                await self.task_repo.save(task)
            except Exception:
                logger.exception(
                    "任务 %s 的进度落库失败（stage=%s），处理继续",
                    task.id,
                    getattr(progress.stage, "value", progress.stage),
                )

    async def _execute_task(self, task: Task) -> None:
        """执行单个任务，处理成功/失败均落库。

        任务在 claim_next_queued() 中已被原子标记为 PROCESSING，此处直接执行处理器。
        """
        self._active += 1
        loop = asyncio.get_running_loop()
        progress_queue: queue.Queue = queue.Queue()
        try:
            future = loop.run_in_executor(
                self._executor,
                self.processor.process,
                task,
                progress_queue,
            )
            try:
                while not future.done():
                    if not await self._drain_progress(task, progress_queue):
                        await asyncio.sleep(_PROGRESS_POLL_INTERVAL)
                await future
            finally:
                # 收尾这次读队列成功失败都要做，而且必须在状态还是 PROCESSING 时做
                # （advance_stage 只认这个状态）。
                #
                # 成功时：处理器最后那几条（通常是 encoded/indexed）很可能还在管道里
                # 没过来——put 只是交给 feeder 线程，而上面的循环在 future.done() 变
                # True 的那一刻就不再读了。少了这一次，任务阶段会永远停在倒数第二个。
                #
                # 失败时：队列里压着的是已经跑完的那几个阶段。丢掉它们，失败任务的
                # progress 就成了 0，用户没法知道到底卡在哪一步。
                await self._drain_progress(task, progress_queue, grace=_PROGRESS_FINAL_GRACE)
            task.mark_completed()
        except NotImplementedError as exc:
            logger.warning("任务 %s 处理器功能尚未实现: %s", task.id, exc)
            task.mark_failed(f"处理器功能尚未实现: {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("任务 %s 处理失败", task.id)
            task.mark_failed(str(exc))
        finally:
            task.updated_at = datetime.now().isoformat()  # noqa: DTZ005
            await self.task_repo.save(task)
            self._close_progress_queue(progress_queue)
            self._active -= 1

    @staticmethod
    def _close_progress_queue(progress_queue: queue.Queue) -> None:
        """关掉这个任务的进度队列。

        每个任务一个队列，而一个 `queue.Queue` 背后是一根管道（两个 fd）和一个 feeder 线程。
        不关的话跑几千个文件就能把进程的 fd 配额耗光，表现成后面的任务莫名其妙失败。

        `cancel_join_thread` 要在 `close` 之前调用，它表示"剩下没写完的不要了"——任务已
        经结束，残留的进度没有意义，而 `join_thread` 在任务失败、队列里还压着东西时会一
        直等下去。清理失败只记日志：它不该盖掉任务本身的结果。
        """
        try:
            progress_queue.cancel_join_thread()
            progress_queue.close()
        except Exception:  # noqa: BLE001
            logger.debug("进度队列关闭失败，忽略", exc_info=True)
