import threading
import time
import win32gui
import win32process
import psutil
import pyperclip
from typing import Optional
from brain.schemas import ContextSnapshot
from config.logging import logger

class ContextService:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = True
        self._last_snapshot: Optional[ContextSnapshot] = None
        self._clipboard_update_time = 0.0
        self._last_clipboard = ""
        
        self._daemon_thread = threading.Thread(target=self._run_loop, daemon=True, name="ContextDaemon")
        self._daemon_thread.start()

    def _get_active_window_info(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None, None
                
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            
            process_name = None
            if pid > 0:
                try:
                    p = psutil.Process(pid)
                    process_name = p.name()
                except psutil.NoSuchProcess:
                    pass
                    
            return title, process_name
        except Exception:
            return None, None

    def _run_loop(self):
        logger.info("ContextDaemon started.")
        while self._running:
            try:
                title, process_name = self._get_active_window_info()
                
                # Check clipboard safely
                current_clipboard = ""
                try:
                    current_clipboard = pyperclip.paste()
                except Exception:
                    pass
                    
                if current_clipboard != self._last_clipboard:
                    self._last_clipboard = current_clipboard
                    self._clipboard_update_time = time.time()
                
                # Enforce clipboard 300s expiration
                clipboard_val = current_clipboard
                if time.time() - self._clipboard_update_time > 300:
                    clipboard_val = None
                    
                with self._lock:
                    self._last_snapshot = ContextSnapshot(
                        timestamp=time.time(),
                        active_window=title,
                        active_process=process_name,
                        clipboard=clipboard_val,
                        current_folder=None # Hard to perfectly extract explorer path without heavy hooks, deferring for now.
                    )
            except Exception as e:
                logger.debug(f"ContextDaemon loop error: {e}")
                
            # Run very slow so it doesn't eat CPU (ambient, low power)
            time.sleep(2)

    def get_snapshot(self) -> Optional[ContextSnapshot]:
        with self._lock:
            return self._last_snapshot

    def shutdown(self):
        self._running = False
        self._daemon_thread.join(timeout=2.0)

# Global singleton
context_service = ContextService()
