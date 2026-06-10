import os
import time
import win32gui
from PIL import ImageGrab
from config.logging import logger

SCREENSHOTS_DIR = os.path.join("logs", "screenshots")

class ScreenshotService:
    def __init__(self):
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        
    def _save_image(self, img, prefix: str) -> str:
        timestamp = int(time.time() * 1000)
        filename = f"{prefix}_{timestamp}.png"
        filepath = os.path.join(SCREENSHOTS_DIR, filename)
        img.save(filepath)
        logger.debug(f"[Vision] Saved screenshot to {filepath}")
        return filepath
        
    def capture_screen(self) -> str:
        """Captures the entire primary display."""
        try:
            img = ImageGrab.grab()
            return self._save_image(img, "desktop"), 0, 0
        except Exception as e:
            logger.error(f"[Vision] Failed to capture screen: {e}")
            return "", 0, 0

    def capture_active_window(self) -> str:
        """Captures only the currently active foreground window."""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                logger.warning("[Vision] No active window found. Falling back to full screen.")
                return self.capture_screen()
                
            rect = win32gui.GetWindowRect(hwnd)
            # rect is (left, top, right, bottom)
            # Sometimes rect can be out of bounds for maximized windows
            # PIL ImageGrab handles standard tuples
            img = ImageGrab.grab(bbox=rect)
            return self._save_image(img, "active_window"), rect[0], rect[1]
        except Exception as e:
            logger.error(f"[Vision] Failed to capture active window: {e}. Falling back to full screen.")
            return self.capture_screen()

# Global singleton
screenshot_service = ScreenshotService()
