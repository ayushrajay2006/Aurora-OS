import os
import sys
import threading
import subprocess
import time
from config.config import config
from config.logging import logger
from config.event_bus import event_bus
from memory.memory import memory

def build_tts_manager():
    """Safe factory for TTS manager. Returns None if voice_out is disabled or dependencies fail."""
    from brain.voice_control import TextToSpeechManager, TTS_SAPI5_AVAILABLE
    # Even if missing, TextToSpeechManager degrades gracefully
    return TextToSpeechManager(
        rate=config.voice_rate,
        voice_index=config.voice_index,
        volume=config.voice_volume,
        voice_name=config.voice_name
    )

def build_stt_manager():
    """Safe factory for STT manager. Returns None if voice_in is disabled or dependencies fail."""
    from brain.voice_control import SpeechToTextManager
    manager = SpeechToTextManager()
    if not manager.available:
        return None
    manager.adjust_for_noise()
    return manager

def run_orb_mode(execute_assistant_turn_fn, run_voice_activation_loop_fn):
    """
    Coordinator for launching the permanent Tauri orb interface,
    WebSocket bridge, and Voice loops.
    """
    from ui.ws_bridge import ws_bridge
    
    # Start WebSocket event bridge (daemon thread)
    ws_bridge.attach()
    ws_bridge.start()
    
    tts_manager = build_tts_manager()
    stt_manager = build_stt_manager()
    
    # Load conversation history context
    history_records = memory.load_history(limit=30)
    chat_history = []
    for r in history_records:
        chat_history.append({"role": r["role"], "content": r["content"]})
    assistant_turn_lock = threading.Lock()

    def handle_ws_command(command_text: str):
        clean_text = (command_text or "").strip()
        if not clean_text:
            return False

        def run_command():
            try:
                with assistant_turn_lock:
                    execute_assistant_turn_fn(
                        clean_text,
                        chat_history,
                        tts_manager,
                        voice_output=True,
                        stt_manager=None
                    )
            except Exception as e:
                logger.error(f"WebSocket command execution failed: {e}", exc_info=True)
                event_bus.publish("error_occurred", error=str(e), source="ws_command")

        threading.Thread(target=run_command, daemon=True, name="aurora-ws-command").start()
        return True

    ws_bridge.set_command_handler(handle_ws_command)
         
    # Launch voice wake activation loop in a background daemon thread
    threading.Thread(
        target=run_voice_activation_loop_fn,
        args=(tts_manager, stt_manager, chat_history, assistant_turn_lock),
        daemon=True
    ).start()
    
    # Launch Tauri orb window as a subprocess (non-blocking)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    orb_dir = os.path.join(project_root, "aurora-orb")
    tauri_exe = os.path.join(orb_dir, "src-tauri", "target", "release", "aurora-orb.exe")
    if os.path.exists(tauri_exe):
        logger.info(f"Launching Tauri orb window: {tauri_exe}")
        subprocess.Popen([tauri_exe], cwd=orb_dir)
    else:
        logger.warning("Tauri orb binary not found. Run 'npm run tauri build' inside aurora-orb/ first.")
        logger.info("WebSocket bridge is running. Connect a client to ws://localhost:8765")
    
    # Block the main thread indefinitely (voice loop is on daemon thread)
    try:
        threading.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        event_bus.publish("system_shutdown", reason="user_exit")
        logger.info("Aurora shutting down.")
