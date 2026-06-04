import sys
import os
import threading
from PySide6.QtCore import QObject, Signal, Slot, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from config.event_bus import event_bus
from config.logging import logger
from config.config import config

# Global variables for background command execution
_shared_chat_history = []
_shared_tts_manager = None

class EventBridge(QObject):
    stateChanged = Signal(str)
    
    def __init__(self):
        super().__init__()
        # Connect Event Bus topics to Qt Signal triggers
        event_bus.subscribe("thinking_started", self._on_thinking_started)
        event_bus.subscribe("thinking_finished", self._on_thinking_finished)
        event_bus.subscribe("tool_started", self._on_tool_started)
        event_bus.subscribe("tool_completed", self._on_tool_completed)
        event_bus.subscribe("speech_started", self._on_speech_started)
        event_bus.subscribe("speech_completed", self._on_speech_completed)
        event_bus.subscribe("wake_status", self._on_wake_status)
        event_bus.subscribe("error_occurred", self._on_error)
        
    def _on_thinking_started(self, **kwargs):
        self.stateChanged.emit("thinking")
        
    def _on_thinking_finished(self, **kwargs):
        self.stateChanged.emit("idle")
        
    def _on_tool_started(self, tool, **kwargs):
        self.stateChanged.emit("executing")
        
    def _on_tool_completed(self, tool, success, **kwargs):
        self.stateChanged.emit("idle")
        
    def _on_speech_started(self, text, **kwargs):
        self.stateChanged.emit("speaking")
        
    def _on_speech_completed(self, **kwargs):
        self.stateChanged.emit("idle")

    def _on_wake_status(self, active, **kwargs):
        if active:
            self.stateChanged.emit("idle")
        else:
            self.stateChanged.emit("sleeping")
        
    def _on_error(self, error, **kwargs):
        # Gracefully handle sleep source vs critical runtime errors
        source = kwargs.get("source", "")
        if source == "sleep":
            self.stateChanged.emit("sleeping")
        else:
            self.stateChanged.emit("error")

    @Slot(str)
    def submitCommand(self, text: str):
        """Handles text commands submitted from QML, executing them on a background thread."""
        logger.info(f"GUI: User submitted command text: '{text}'")
        
        def run_command_worker():
            from main import execute_assistant_turn
            try:
                execute_assistant_turn(
                    user_input=text,
                    chat_history=_shared_chat_history,
                    tts_manager=_shared_tts_manager,
                    voice_output=config.voice_output_enabled or (_shared_tts_manager is not None),
                    stt_manager=None
                )
            except Exception as e:
                logger.error(f"GUI: Command execution worker failed: {e}", exc_info=True)
                event_bus.publish("error_occurred", error=str(e), source="gui_worker")
                
        threading.Thread(target=run_command_worker, daemon=True).start()

def run_gui_app(chat_history: list, tts_manager):
    """Launches the PySide6 UI loop on the main thread (blocking)."""
    global _shared_chat_history, _shared_tts_manager
    _shared_chat_history = chat_history
    _shared_tts_manager = tts_manager
    
    logger.info("GUI: Initializing PySide6 desktop client...")
    app = QGuiApplication(sys.argv)
    
    engine = QQmlApplicationEngine()
    bridge = EventBridge()
    
    # Register the event bridge object on the QML root context
    engine.rootContext().setContextProperty("eventBridge", bridge)
    
    # Load QML layout
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    qml_path = os.path.join(project_root, "ui", "orb.qml")
    engine.load(QUrl.fromLocalFile(qml_path))
    
    if not engine.rootObjects():
        logger.error("GUI: Failed to load QML window objects.")
        sys.exit(-1)
        
    logger.info("GUI: UI loaded successfully. Starting app exec...")
    
    # Start as sleeping
    bridge.stateChanged.emit("sleeping")
    
    # Start blocking Qt Event Loop
    sys.exit(app.exec())
