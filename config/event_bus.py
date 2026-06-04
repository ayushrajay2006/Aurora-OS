import threading
from typing import Callable, Dict, List, Any
from config.logging import logger

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[..., None]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, callback: Callable[..., None]):
        """Registers a subscriber callback for a specific event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            logger.debug(f"EventBus: Registered subscriber for event '{event_type}'")

    def publish(self, event_type: str, **kwargs):
        """Publishes an event to all registered subscribers asynchronously (safe execution)."""
        with self._lock:
            subscribers = self._subscribers.get(event_type, []).copy()
        
        if subscribers:
            logger.debug(f"EventBus: Publishing event '{event_type}' with payload: {kwargs}")
        
        for callback in subscribers:
            try:
                callback(**kwargs)
            except Exception as e:
                logger.error(f"EventBus: Subscriber failed for event '{event_type}': {e}", exc_info=True)

# Global instance of EventBus
event_bus = EventBus()
