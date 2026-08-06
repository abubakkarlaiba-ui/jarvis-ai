from jarvis.core.performance.base import TaskPriority, TaskState, ScheduledTask, HealthStatus
import asyncio
import heapq
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable


class TaskScheduler:
    def __init__(self, max_workers: int = 4):
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._queue: list[tuple[int, float, ScheduledTask]] = []
        self._tasks: dict[str, ScheduledTask] = {}
        self._history: list[dict] = []
        self._running = False
        self._loop_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._loop_task = asyncio.create_task(self._process_queue())

    async def stop(self) -> None:
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        self._executor.shutdown(wait=True)

    def schedule(
        self,
        name: str,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        interval: float = 0,
        delay: float = 0,
        max_retries: int = 3,
        timeout: float = 300,
        tags: list[str] = None,
    ) -> str:
        task_id = str(uuid.uuid4())
        next_run = time.time() + delay if delay else time.time()
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            func=func,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            interval=interval,
            next_run=next_run,
            max_retries=max_retries,
            timeout=timeout,
            tags=tags or [],
        )
        self._tasks[task_id] = task
        heapq.heappush(self._queue, (priority.value, next_run, task))
        return task_id

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.state == TaskState.RUNNING:
            return False
        task.state = TaskState.CANCELLED
        return True

    def pause(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.state != TaskState.RUNNING:
            return False
        task.state = TaskState.PAUSED
        return True

    def resume(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.state != TaskState.PAUSED:
            return False
        task.state = TaskState.PENDING
        heapq.heappush(self._queue, (task.priority.value, task.next_run, task))
        return True

    def get_task(self, task_id: str) -> ScheduledTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self, state: TaskState = None, tag: str = None) -> list[dict]:
        results = []
        for task in self._tasks.values():
            if state and task.state != state:
                continue
            if tag and tag not in task.tags:
                continue
            results.append({
                "task_id": task.task_id,
                "name": task.name,
                "state": task.state.value,
                "priority": task.priority.value,
                "interval": task.interval,
                "tags": task.tags,
                "retries": task.retries,
                "last_run": task.last_run,
            })
        return results

    def get_stats(self) -> dict:
        states = [t.state for t in self._tasks.values()]
        return {
            "total": len(self._tasks),
            "running": sum(1 for s in states if s == TaskState.RUNNING),
            "completed": sum(1 for s in states if s == TaskState.COMPLETED),
            "failed": sum(1 for s in states if s == TaskState.FAILED),
            "queue_size": len(self._queue),
        }

    async def run_now(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, self._run_task, task)

    async def _process_queue(self) -> None:
        while self._running:
            now = time.time()
            while self._queue:
                priority, next_run, task = self._queue[0]
                if task.state == TaskState.CANCELLED:
                    heapq.heappop(self._queue)
                    continue
                if next_run > now:
                    break
                heapq.heappop(self._queue)
                if task.state == TaskState.PAUSED:
                    continue
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(self._executor, self._run_task, task)
                if task.interval > 0 and task.state not in (TaskState.CANCELLED, TaskState.FAILED):
                    task.next_run = now + task.interval
                    heapq.heappush(self._queue, (task.priority.value, task.next_run, task))
            await asyncio.sleep(0.1)

    def _run_task(self, task: ScheduledTask) -> None:
        task.state = TaskState.RUNNING
        task.last_run = time.time()
        try:
            task.func(*task.args, **task.kwargs)
            task.state = TaskState.COMPLETED
            self._history.append({
                "task_id": task.task_id,
                "name": task.name,
                "state": "completed",
                "timestamp": time.time(),
            })
        except Exception as e:
            self._handle_error(task, e)

    def _handle_error(self, task: ScheduledTask, error: Exception) -> None:
        task.retries += 1
        if task.retries < task.max_retries:
            task.state = TaskState.PENDING
            task.next_run = time.time() + (2 ** task.retries)
            heapq.heappush(self._queue, (task.priority.value, task.next_run, task))
        else:
            task.state = TaskState.FAILED
        self._history.append({
            "task_id": task.task_id,
            "name": task.name,
            "state": "failed",
            "error": str(error),
            "timestamp": time.time(),
        })

    def cleanup_completed(self) -> int:
        cutoff = time.time() - 3600
        to_remove = [
            tid for tid, t in self._tasks.items()
            if t.state == TaskState.COMPLETED and t.last_run and t.last_run < cutoff
        ]
        for tid in to_remove:
            del self._tasks[tid]
        return len(to_remove)

    def get_history(self, count: int = 50) -> list[dict]:
        return self._history[-count:]
