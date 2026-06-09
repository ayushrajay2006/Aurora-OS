from typing import Optional, Dict, Any
from config.logging import logger

class DesktopContext:
    """
    Lightweight, deterministic state tracker for desktop window control.
    Tracks the last opened app and the last focused app to resolve contextual
    references (like 'it', 'that', 'current app', etc.)
    """
    def __init__(self):
        self._last_opened_app: Optional[str] = None
        self._last_focused_app: Optional[str] = None

    def update_opened(self, app_name: str):
        self._last_opened_app = app_name
        logger.info(f"[DesktopContext] Updated last_opened_app to '{app_name}'")

    def update_focused(self, app_name: str):
        self._last_focused_app = app_name
        logger.info(f"[DesktopContext] Updated last_focused_app to '{app_name}'")

    def resolve_reference(self, reference: str) -> Dict[str, Any]:
        """
        Resolves generic references based on desktop state.
        Priority:
        1. last_focused_app
        2. last_opened_app
        
        Returns:
            Dict: {"resolved": str, "error": bool, "clarification": str}
        """
        ref_lower = reference.lower().strip()
        
        # Generic references that trigger context resolution
        contextual_keywords = {"it", "that", "this", "current app", "previous app", "the app", "the game"}
        
        if ref_lower not in contextual_keywords:
            return {"resolved": reference, "error": False, "clarification": None}

        if self._last_focused_app:
            logger.info(f"[DesktopContext] Resolved reference '{reference}' to last focused app: '{self._last_focused_app}'")
            return {"resolved": self._last_focused_app, "error": False, "clarification": None}
            
        if self._last_opened_app:
            logger.info(f"[DesktopContext] Resolved reference '{reference}' to last opened app: '{self._last_opened_app}'")
            return {"resolved": self._last_opened_app, "error": False, "clarification": None}

        # No context available
        msg = f"I'm not sure what '{reference}' refers to. Could you clarify which app you want to control?"
        logger.warning(f"[DesktopContext] Failed to resolve reference '{reference}'. No desktop context available.")
        return {"resolved": None, "error": True, "clarification": msg}

# Global singleton
desktop_context = DesktopContext()
