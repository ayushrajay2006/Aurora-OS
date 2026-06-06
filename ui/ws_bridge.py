"""
Aurora WebSocket bridge for the permanent Tauri orb UI.

- broadcasts backend events to connected UI clients
- accepts inbound `user_command` messages from the orb
- acknowledges command submission back to the client
"""

import asyncio
import json
import threading
import time
from typing import Callable, Optional

from config.config import config
from config.event_bus import event_bus
from config.logging import logger
from ui.event_buffer import event_buffer

RELAYED_EVENTS = [
    "thinking_started",
    "thinking_finished",
    "tool_started",
    "tool_completed",
    "speech_started",
    "speech_completed",
    "wake_status",
    "listening_started",
    "listening_finished",
    "audio_amplitude",
    "tts_amplitude",
    "task_queued",
    "task_progress",
    "task_verifying",
    "task_recovering",
    "task_failed",
    "memory_written",
    "error_occurred",
    "system_ready",
    "system_shutdown",
]


class WsBridge:
    """Thread-safe asyncio WebSocket broadcast server."""

    def __init__(self):
        self._host: str = config.get("ws_bridge_host", "localhost")
        self._port: int = int(config.get("ws_bridge_port", 8765))
        self._clients: set = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()
        self._attached = False
        self._command_handler: Optional[Callable[[str], bool]] = None

    def _make_handler(self, event_type: str):
        """Return a thread-safe EventBus subscriber callback."""
        def _handler(**kwargs):
            safe_payload = {}
            for key, value in kwargs.items():
                try:
                    json.dumps(value)
                    safe_payload[key] = value
                except (TypeError, ValueError):
                    safe_payload[key] = str(value)

            event_obj = {
                "event": event_type,
                "ts": time.time(),
                "payload": safe_payload,
            }
            event_buffer.add_event(event_obj)
            
            frame = json.dumps(event_obj)
            if self._loop and not self._loop.is_closed():
                asyncio.run_coroutine_threadsafe(self._broadcast(frame), self._loop)

        return _handler

    def attach(self):
        """Subscribe relay events to the global EventBus singleton."""
        if self._attached:
            logger.warning("WsBridge: attach() called more than once, skipping.")
            return

        for event_type in RELAYED_EVENTS:
            event_bus.subscribe(event_type, self._make_handler(event_type))

        self._attached = True
        logger.info("WsBridge: Subscribed to relay events.")

    def set_command_handler(self, handler: Callable[[str], bool]):
        """Register the callback used for inbound orb text commands."""
        self._command_handler = handler
        logger.info("WsBridge: Inbound command handler registered.")

    async def _broadcast(self, message: str):
        """Send a JSON frame to all connected WebSocket clients."""
        with self._lock:
            clients = self._clients.copy()

        if not clients:
            return

        results = await asyncio.gather(
            *[self._safe_send(client, message) for client in clients],
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.debug(f"WsBridge: Send error: {result}")

    async def _safe_send(self, websocket, message: str):
        await websocket.send(message)

    async def _handle_inbound_message(self, websocket, raw_message: str):
        """Process JSON messages sent from UI clients."""
        try:
            frame = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.warning("WsBridge: Ignored non-JSON client message.")
            return

        event_type = frame.get("event", "")
        payload = frame.get("payload", {}) or {}

        if event_type == "get_diagnostics":
            from brain.task_manager import task_manager
            from config.state import state_manager
            import dataclasses
            
            snapshot = {
                "event": "diagnostics_snapshot",
                "ts": time.time(),
                "payload": {
                    "current_state": dataclasses.asdict(state_manager.get_state()),
                    "queued_tasks": [t.dict() for t in task_manager.get_queued_tasks()],
                    "active_task": task_manager.get_active_task().dict() if task_manager.get_active_task() else None,
                    "event_history": event_buffer.get_snapshot()
                }
            }
            try:
                await websocket.send(json.dumps(snapshot))
            except Exception as e:
                logger.debug(f"WsBridge: Failed to send diagnostics: {e}")
            return

        if event_type != "user_command":
            logger.debug(f"WsBridge: Ignored unsupported inbound event '{event_type}'.")
            return

        command_text = str(payload.get("text", "")).strip()
        accepted = False
        error_message: str | None = None

        if self._command_handler and command_text:
            try:
                accepted = bool(self._command_handler(command_text))
            except Exception as e:
                logger.error(f"WsBridge: Command handler failed: {e}", exc_info=True)
                error_message = str(e)

        response = json.dumps({
            "event": "command_ack",
            "ts": time.time(),
            "payload": {
                "accepted": accepted,
                "text": command_text,
                "error": error_message,
            },
        })

        try:
            await websocket.send(response)
        except Exception as e:
            logger.debug(f"WsBridge: Failed to send command acknowledgement: {e}")

    async def _connection_handler(self, websocket):
        """Manage a single client connection lifetime."""
        with self._lock:
            self._clients.add(websocket)
            count = len(self._clients)

        logger.info(f"WsBridge: Client connected ({count} total) from {websocket.remote_address}")

        welcome = json.dumps({
            "event": "connected",
            "ts": time.time(),
            "payload": {"clients": count},
        })
        try:
            await websocket.send(welcome)
        except Exception:
            pass

        try:
            async for message in websocket:
                await self._handle_inbound_message(websocket, message)
        finally:
            with self._lock:
                self._clients.discard(websocket)
                remaining = len(self._clients)
            logger.info(f"WsBridge: Client disconnected ({remaining} remaining)")

    async def _serve(self):
        """Run the asyncio WebSocket server indefinitely."""
        import websockets

        async with websockets.serve(self._connection_handler, self._host, self._port):
            logger.info(f"WsBridge: Listening on ws://{self._host}:{self._port}")
            await asyncio.Future()

    def start(self):
        """Launch the asyncio event loop and WebSocket server on a daemon thread."""
        def _run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._serve())
            except Exception as e:
                logger.error(f"WsBridge: Server error: {e}", exc_info=True)

        thread = threading.Thread(target=_run, daemon=True, name="aurora-ws-bridge")
        thread.start()
        logger.info("WsBridge: Server daemon thread started.")

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)


ws_bridge = WsBridge()
