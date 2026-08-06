"""Background task scheduling with priorities, retries, and concurrency control."""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    task_id: str
    name: str
    status: TaskStatus
    priority: TaskPriority
    created_at: float = field(default_factory=time.time)
    started_at: float = None
    completed_at: float = None
    timeout: float = 300.0
    max_retries: int = 3
    retry_count: int = 0
    result: Any = None
    error: Exception = None
    callback: Callable = None


class TaskScheduler:
    def __init__(self, max_concurrent: int = 10):
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._tasks: dict[str, TaskInfo] = {}
        self._running: dict[str, asyncio.Task] = {}
        self._history: list[TaskInfo] = []
        self._paused = False
        self._shutdown = False
        self._processor_task: asyncio.Task = None

    async def submit(
        self,
        name: str,
        func: Callable,
        args: tuple = None,
        kwargs: dict = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: float = 300.0,
        max_retries: int = 3,
    ) -> str:
        task_id = str(uuid.uuid4())
        task_info = TaskInfo(
            task_id=task_id,
            name=name,
            status=TaskStatus.PENDING,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
        )
        task_entry = (func, args or (), kwargs or {}, task_info)
        await self._queue.put((-priority.value, task_entry))
        self._tasks[task_id] = task_info
        return task_id

    async def submit_delayed(self, name: str, func: Callable, delay: float, **kwargs) -> str:
        task_id = str(uuid.uuid4())
        task_info = TaskInfo(
            task_id=task_id,
            name=name,
            status=TaskStatus.PENDING,
            priority=TaskPriority.NORMAL,
        )
        self._tasks[task_id] = task_info

        async def delayed_exec():
            await asyncio.sleep(delay)
            task_entry = (func, (), kwargs, task_info)
            await self._queue.put((-TaskPriority.NORMAL.value, task_entry))

        asyncio.create_task(delayed_exec())
        return task_id

    async def submit_periodic(self, name: str, func: Callable, interval: float, **kwargs) -> str:
        task_id = str(uuid.uuid4())
        task_info = TaskInfo(
            task_id=task_id,
            name=name,
            status=TaskStatus.PENDING,
            priority=TaskPriority.NORMAL,
        )
        self._tasks[task_id] = task_info

        async def periodic_exec():
            while task_info.status != TaskStatus.CANCELLED:
                await asyncio.sleep(interval)
                if task_info.status == TaskStatus.CANCELLED:
                    break
                task_entry = (func, (), kwargs, task_info)
                await self._queue.put((-TaskPriority.NORMAL.value, task_entry))

        asyncio.create_task(periodic_exec())
        return task_id

    def cancel(self, task_id: str) -> bool:
        if task_id in self._tasks:
            self._tasks[task_id].status = TaskStatus.CANCELLED
            if task_id in self._running:
                self._running[task_id].cancel()
                del self._running[task_id]
            return True
        return False

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        return self._tasks.get(task_id)

    def list_tasks(self, status: TaskStatus = None, limit: int = 50) -> list[TaskInfo]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks[:limit]

    def get_stats(self) -> dict:
        return {
            "active": sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING),
            "completed": sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED),
            "queue_depth": self._queue.qsize(),
            "max_concurrent": self._max_concurrent,
        }

    async def wait_for(self, task_id: str, timeout: float = None) -> Any:
        task_info = self._tasks.get(task_id)
        if not task_info:
            raise ValueError(f"Task {task_id} not found")
        if task_info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return task_info.result
        start = time.time()
        while task_info.status == TaskStatus.PENDING or task_info.status == TaskStatus.RUNNING:
            if timeout and (time.time() - start) >= timeout:
                raise TimeoutError(f"Wait for task {task_id} timed out")
            await asyncio.sleep(0.1)
        if task_info.status == TaskStatus.FAILED:
            raise task_info.error
        return task_info.result

    def set_concurrency(self, max_concurrent: int):
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def shutdown(self, wait: bool = True):
        self._shutdown = True
        if self._processor_task and not self._processor_task.done():
            self._processor_task.cancel()

    async def _process_queue(self):
        while not self._shutdown:
            if self._paused:
                await asyncio.sleep(0.1)
                continue
            try:
                priority, task_entry = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            func, args, kwargs, task_info = task_entry
            if task_info.status == TaskStatus.CANCELLED:
                continue
            asyncio.create_task(self._run_task(task_entry))

    async def _run_task(self, task_entry):
        func, args, kwargs, task_info = task_entry
        task_info.status = TaskStatus.RUNNING
        task_info.started_at = time.time()
        self._running[task_info.task_id] = asyncio.current_task()
        try:
            async with self._semaphore:
                result = await asyncio.wait_for(
                    asyncio.to_thread(func, *args, **kwargs),
                    timeout=task_info.timeout,
                )
                task_info.result = result
                task_info.status = TaskStatus.COMPLETED
                task_info.completed_at = time.time()
                if task_info.callback:
                    try:
                        await task_info.callback(task_info)
                    except Exception:
                        pass
        except Exception as e:
            task_info.error = e
            if task_info.retry_count < task_info.max_retries:
                task_info.retry_count += 1
                task_info.status = TaskStatus.PENDING
                task_entry_new = (func, args, kwargs, task_info)
                await self._queue.put((-task_info.priority.value, task_entry_new))
            else:
                task_info.status = TaskStatus.FAILED
                task_info.completed_at = time.time()
        finally:
            self._running.pop(task_info.task_id, None)
            self._history.append(task_info)

    def _handle_failure(self, task_info: TaskInfo, error: Exception):
        task_info.error = error
        task_info.status = TaskStatus.FAILED
        task_info.completed_at = time.time()

    def get_history(self, count: int = 50) -> list[TaskInfo]:
        return self._history[-count:]

    def register_callback(self, task_id: str, callback: Callable):
        if task_id in self._tasks:
            self._tasks[task_id].callback = callback
