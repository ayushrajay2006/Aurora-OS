import queue
import threading
from typing import List, Dict, Optional
from brain.schemas import Task
from config.logging import logger
from config.event_bus import event_bus

class TaskManager:
    def __init__(self):
        # We use a standard queue to hold pending tasks
        self._queue = queue.Queue()
        # We use a dictionary to track all tasks by ID (running, queued, completed)
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._active_task: Optional[Task] = None

    def enqueue(self, task: Task):
        with self._lock:
            self._tasks[task.task_id] = task
            task.status = "queued"
        
        self._queue.put(task)
        logger.info(f"Task Queued: {task.task_id} -> {task.tool_call.tool_name}")
        event_bus.publish("task_queued", task_id=task.task_id, tool_name=task.tool_call.tool_name)

    def get_next_task(self) -> Optional[Task]:
        """Called by the execution worker to get the next task (blocking)."""
        task = self._queue.get() # Blocks until a task is available
        with self._lock:
            self._active_task = task
        return task

    def mark_task_done(self):
        """Called by the worker after completion or failure."""
        with self._lock:
            self._active_task = None
        self._queue.task_done()

    def update_task_status(self, task_id: str, status: str, attempts: int = None, verification_result = None):
        with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.status = status
                if attempts is not None:
                    task.attempts = attempts
                if verification_result is not None:
                    task.verification_result = verification_result

    def get_queued_tasks(self) -> List[Task]:
        with self._lock:
            return [t for t in self._tasks.values() if t.status == "queued"]
            
    def get_active_task(self) -> Optional[Task]:
        with self._lock:
            return self._active_task

    def get_all_tasks(self) -> List[Task]:
        with self._lock:
            return list(self._tasks.values())

task_manager = TaskManager()
