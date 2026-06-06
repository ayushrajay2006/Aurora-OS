import threading
from typing import List, Dict, Any

class EventHistoryBuffer:
    def __init__(self, max_length: int = 100):
        self.max_length = max_length
        self._buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def add_event(self, event_data: Dict[str, Any]):
        with self._lock:
            self._buffer.append(event_data)
            if len(self._buffer) > self.max_length:
                self._buffer.pop(0)

    def get_snapshot(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._buffer)

event_buffer = EventHistoryBuffer(max_length=100)
