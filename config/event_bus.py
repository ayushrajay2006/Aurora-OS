import threading
import queue
import time
from typing import Callable, Dict, List, Any
from config.logging import logger

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[..., None]]] = {}
        self._lock = threading.Lock()
        self._queue = queue.Queue()
        self._running = True
        self._worker_thread = threading.Thread(target=self._dispatch_loop, daemon=True, name="EventBusThread")
        self._worker_thread.start()

    def subscribe(self, event_type: str, callback: Callable[..., None]):
        """Registers a subscriber callback for a specific event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            logger.debug(f"EventBus: Registered subscriber for event '{event_type}'")

    def publish(self, event_type: str, **kwargs):
        """Publishes an event to the queue asynchronously without blocking the caller."""
        self._queue.put((event_type, kwargs))
        
    def _dispatch_loop(self):
        """Background thread that consumes the queue and triggers callbacks sequentially."""
        while self._running:
            try:
                event_type, kwargs = self._queue.get(timeout=0.5)
                
                with self._lock:
                    subscribers = self._subscribers.get(event_type, []).copy()
                
                if subscribers:
                    logger.debug(f"EventBus: Dispatching event '{event_type}' with payload: {kwargs}")
                
                for callback in subscribers:
                    try:
                        callback(**kwargs)
                    except Exception as e:
                        logger.error(f"EventBus: Subscriber failed for event '{event_type}': {e}", exc_info=True)
                        
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"EventBus: Dispatch loop encountered error: {e}", exc_info=True)

    def shutdown(self):
        """Cleanly shutdown the event bus thread."""
        self._running = False
        self._worker_thread.join(timeout=2.0)

# Global instance of EventBus
event_bus = EventBus()

