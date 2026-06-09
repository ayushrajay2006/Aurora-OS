import win32gui
import win32process
import psutil
from config.logging import logger
from vision.screenshot_service import screenshot_service
from vision.ocr_service import ocr_service

class WindowClassifier:
    def get_active_window_info(self) -> dict:
        """Returns metadata about the active window: title, process name, process exe."""
        info = {
            "title": "",
            "process_name": "",
            "process_exe": "",
            "error": None
        }
        
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                info["error"] = "No active foreground window found."
                return info
                
            info["title"] = win32gui.GetWindowText(hwnd)
            
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid > 0:
                try:
                    proc = psutil.Process(pid)
                    info["process_name"] = proc.name()
                    info["process_exe"] = proc.exe()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                    
        except Exception as e:
            logger.error(f"[Vision] Failed to extract window metadata: {e}")
            info["error"] = str(e)
            
        return info

    def analyze_current_screen(self) -> dict:
        """
        Takes a screenshot of the active window and performs metadata extraction + OCR.
        Does NOT use a Vision Language Model.
        """
        logger.info("[Vision] Analyzing current screen using pure metadata + OCR...")
        
        # 1. Metadata extraction
        metadata = self.get_active_window_info()
        
        # 2. Screenshot
        img_path = screenshot_service.capture_active_window()
        
        # 3. OCR extraction
        ocr_text = ""
        if img_path:
            ocr_text = ocr_service.get_raw_text(img_path)
            
        return {
            "success": True,
            "window_title": metadata["title"],
            "process_name": metadata["process_name"],
            "ocr_text_visible": ocr_text,
            "screenshot_path": img_path
        }

# Global singleton
window_classifier = WindowClassifier()
