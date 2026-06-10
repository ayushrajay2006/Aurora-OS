import threading
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class AppState:
    status: str = "Starting"
    model_name: str = "qwen2.5:14b"
    memory_active: bool = False
    voice_enabled: bool = False
    vision_enabled: bool = False
    messages: List[Dict[str, Any]] = field(default_factory=list)
    planned_actions: List[Dict[str, Any]] = field(default_factory=list)
    tool_logs: List[str] = field(default_factory=list)
    pending_confirmation: Optional[Dict[str, Any]] = None
    error_notification: Optional[str] = None
    last_ui_x: Optional[int] = None
    last_ui_y: Optional[int] = None
    last_update: float = field(default_factory=time.time)

class StateManager:
    def __init__(self):
        self._state = AppState()
        self._lock = threading.Lock()
        self._callbacks = []

    def register_callback(self, callback):
        """Register a callback that triggers whenever state changes."""
        self._callbacks.append(callback)

    def _notify(self):
        for cb in self._callbacks:
            try:
                cb(self._state)
            except Exception:
                pass

    def get_state(self) -> AppState:
        with self._lock:
            return AppState(
                status=self._state.status,
                model_name=self._state.model_name,
                memory_active=self._state.memory_active,
                voice_enabled=self._state.voice_enabled,
                vision_enabled=self._state.vision_enabled,
                messages=list(self._state.messages),
                planned_actions=list(self._state.planned_actions),
                tool_logs=list(self._state.tool_logs),
                pending_confirmation=dict(self._state.pending_confirmation) if self._state.pending_confirmation else None,
                error_notification=self._state.error_notification,
                last_ui_x=self._state.last_ui_x,
                last_ui_y=self._state.last_ui_y,
                last_update=self._state.last_update
            )

    def update_state(self, **kwargs):
        """Update multiple fields of the state thread-safely."""
        with self._lock:
            updated = False
            for k, v in kwargs.items():
                if hasattr(self._state, k):
                    setattr(self._state, k, v)
                    updated = True
            if updated:
                self._state.last_update = time.time()
            self._notify()

    def add_message(self, role: str, content: str):
        with self._lock:
            self._state.messages.append({
                "role": role,
                "content": content,
                "timestamp": time.strftime("%H:%M:%S")
            })
            self._state.last_update = time.time()
            self._notify()

    def add_tool_log(self, log_msg: str):
        with self._lock:
            timestamp = time.strftime("%H:%M:%S")
            self._state.tool_logs.append(f"[{timestamp}] {log_msg}")
            if len(self._state.tool_logs) > 100:
                self._state.tool_logs.pop(0)
            self._state.last_update = time.time()
            self._notify()

    def set_planned_actions(self, actions: List[Dict[str, Any]]):
        with self._lock:
            self._state.planned_actions = actions
            self._state.last_update = time.time()
            self._notify()

    def update_action_status(self, action_id: str, status: str):
        with self._lock:
            for act in self._state.planned_actions:
                if act.get("id") == action_id:
                    act["status"] = status
                    break
            self._state.last_update = time.time()
            self._notify()

    def set_pending_confirmation(self, action_id: str, action_type: str, description: str, expected_input: Optional[str] = None):
        with self._lock:
            self._state.pending_confirmation = {
                "action_id": action_id,
                "action_type": action_type,
                "description": description,
                "expected_input": expected_input
            }
            self._state.last_update = time.time()
            self._notify()

    def clear_pending_confirmation(self):
        with self._lock:
            self._state.pending_confirmation = None
            self._state.last_update = time.time()
            self._notify()

# Global state manager instance
state_manager = StateManager()
