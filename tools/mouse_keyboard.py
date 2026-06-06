"""
tools/mouse_keyboard.py
Phase 11 — GUI & Screen Control Tools

Provides Aurora with the ability to:
- Move the mouse to any screen coordinate
- Click, double-click, right-click at coordinates
- Type text and press keyboard keys / shortcuts
- Scroll the mouse wheel
- Drag from one point to another
- Get the current screen resolution

Safety:
  - pyautogui FAILSAFE is enabled — move mouse to top-left corner (0,0) to abort.
  - Lazy import: if pyautogui is not installed, all tools return a clear install message
    instead of crashing at module load time.
  - Bounds guard: click/move coordinates are validated against actual screen size,
    not silently clamped — hallucinated coordinates are rejected.
"""

import time
from tools.registry import registry, BaseTool
from config.logging import logger


# ─── Lazy pyautogui access ───────────────────────────────────────────────────

_pyautogui = None
_PYAUTOGUI_AVAILABLE = False

def _get_pyautogui():
    """Lazy-load pyautogui. Returns None (with a logged warning) if not installed."""
    global _pyautogui, _PYAUTOGUI_AVAILABLE
    if _PYAUTOGUI_AVAILABLE:
        return _pyautogui
    if _pyautogui is None:
        try:
            import pyautogui as _pag
            _pag.FAILSAFE = True
            _pag.PAUSE = 0.05
            _pyautogui = _pag
            _PYAUTOGUI_AVAILABLE = True
            logger.info("mouse_keyboard: pyautogui loaded successfully.")
        except ImportError:
            logger.warning(
                "mouse_keyboard: 'pyautogui' not installed — all automation tools disabled. "
                "Fix: pip install pyautogui pyperclip"
            )
    return _pyautogui


_NOT_INSTALLED = {
    "success": False,
    "output": (
        "pyautogui is not installed. Mouse and keyboard automation is disabled. "
        "Fix: pip install pyautogui pyperclip"
    )
}


def _check_bounds(x: int, y: int, pag) -> tuple[bool, str]:
    """
    Validate that (x, y) is within actual screen bounds.
    Returns (ok, error_message). Rejects instead of silently clamping so
    hallucinated coordinates don't accidentally click random screen positions.
    """
    screen_w, screen_h = pag.size()
    if not (0 <= x < screen_w) or not (0 <= y < screen_h):
        return False, (
            f"Coordinates ({x}, {y}) are outside screen bounds ({screen_w}x{screen_h}). "
            f"Use find_on_screen to get valid coordinates before clicking."
        )
    return True, ""


# ─────────────────────────────────────────────────────────────
# move_mouse
# ─────────────────────────────────────────────────────────────
@registry.register(
    name="move_mouse",
    description="Moves the mouse cursor to the specified (x, y) screen coordinates without clicking.",
    args_schema={
        "x": {"type": "string", "description": "Horizontal target coordinate in pixels, or 'center'."},
        "y": {"type": "string", "description": "Vertical target coordinate in pixels, or 'center'."},
        "duration": {"type": "number", "description": "Time in seconds to animate the movement (default 0.2)."}
    },
    risk_level="low"
)
class MoveMouseTool(BaseTool):
    def execute(self, x, y, duration: float = 0.25) -> dict:
        pag = _get_pyautogui()
        if pag is None:
            return _NOT_INSTALLED
        try:
            if str(x).strip().lower() == "center" or str(y).strip().lower() == "center":
                w, h = pag.size()
                x = w // 2 if str(x).strip().lower() == "center" else int(x)
                y = h // 2 if str(y).strip().lower() == "center" else int(y)
                
            ok, err = _check_bounds(int(x), int(y), pag)
            if not ok:
                logger.warning(f"MoveMouse: rejected — {err}")
                return {"success": False, "output": err}
            pag.moveTo(x=int(x), y=int(y), duration=duration)
            logger.info(f"MoveMouse: moved to ({x}, {y})")
            return {"success": True, "output": f"Mouse moved to ({x}, {y})."}
        except Exception as e:
            logger.error(f"MoveMouse failed: {e}")
            return {"success": False, "output": str(e)}


# ─────────────────────────────────────────────────────────────
# click
# ─────────────────────────────────────────────────────────────
@registry.register(
    name="click",
    description="Clicks the mouse at the specified (x, y) screen coordinates. Supports left, right, and middle buttons, and single or double clicks.",
    args_schema={
        "x": {"type": "string", "description": "Horizontal screen coordinate in pixels, or 'center' for middle of screen."},
        "y": {"type": "string", "description": "Vertical screen coordinate in pixels, or 'center' for middle of screen."},
        "button": {"type": "string", "description": "Mouse button to click: 'left' (default), 'right', or 'middle'."},
        "clicks": {"type": "integer", "description": "Number of clicks: 1 for single (default), 2 for double."},
        "duration": {"type": "number", "description": "Duration of mouse movement to target in seconds (default 0.15)."}
    },
    risk_level="medium"
)
class ClickTool(BaseTool):
    def execute(self, x, y, button: str = "left", clicks: int = 1, duration: float = 0.15) -> dict:
        pag = _get_pyautogui()
        if pag is None:
            return _NOT_INSTALLED
        try:
            if str(x).strip().lower() == "center" or str(y).strip().lower() == "center":
                w, h = pag.size()
                x = w // 2 if str(x).strip().lower() == "center" else int(x)
                y = h // 2 if str(y).strip().lower() == "center" else int(y)
            
            ok, err = _check_bounds(int(x), int(y), pag)
            if not ok:
                logger.warning(f"Click: rejected — {err}")
                return {"success": False, "output": err}
            button = button.lower() if button.lower() in ("left", "right", "middle") else "left"
            clicks = max(1, int(clicks))
            pag.click(x=int(x), y=int(y), clicks=clicks, button=button, duration=duration)
            click_type = "Double-click" if clicks == 2 else "Click"
            logger.info(f"Click: {click_type} ({button}) at ({x}, {y})")
            return {"success": True, "output": f"{click_type} ({button} button) at ({x}, {y})."}
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return {"success": False, "output": str(e)}


# ─────────────────────────────────────────────────────────────
# type_text
# ─────────────────────────────────────────────────────────────
@registry.register(
    name="type_text",
    description="Types the given text at the current cursor position, as if typed on a keyboard. Use after clicking on an input field. Supports Unicode.",
    args_schema={
        "text": {"type": "string", "description": "The text to type. Supports letters, numbers, symbols, and newlines (\\n)."},
        "interval": {"type": "number", "description": "Pause between each keystroke in seconds (default 0.04). Increase for slower, more reliable typing."},
        "clear_first": {"type": "boolean", "description": "If true, selects all existing text (Ctrl+A) and deletes it before typing (default false)."}
    },
    risk_level="medium"
)
class TypeTextTool(BaseTool):
    def execute(self, text: str, interval: float = 0.04, clear_first: bool = False) -> dict:
        pag = _get_pyautogui()
        if pag is None:
            return _NOT_INSTALLED
        try:
            import pyperclip
            if clear_first:
                pag.hotkey("ctrl", "a")
                time.sleep(0.1)
                pag.press("delete")
                time.sleep(0.05)
            # Always use clipboard+paste as primary method — handles all Unicode,
            # emojis, Hindi/Chinese text, symbols. pyautogui.typewrite() silently
            # drops anything outside ASCII range.
            pyperclip.copy(text)
            pag.hotkey("ctrl", "v")
            preview = text[:40] + "..." if len(text) > 40 else text
            logger.info(f"TypeText: pasted '{preview}'")
            return {"success": True, "output": f"Typed text: '{preview}'"}
        except Exception as e:
            # Last resort: pyautogui typewrite (ASCII only)
            try:
                if clear_first:
                    pag.hotkey("ctrl", "a")
                    time.sleep(0.1)
                    pag.press("delete")
                    time.sleep(0.05)
                pag.typewrite(text, interval=interval)
                preview = text[:40] + "..." if len(text) > 40 else text
                logger.info(f"TypeText (typewrite fallback): typed '{preview}'")
                return {"success": True, "output": f"Typed text: '{preview}'"}
            except Exception as e2:
                logger.error(f"TypeText failed: {e2}")
                return {"success": False, "output": str(e2)}


# ─────────────────────────────────────────────────────────────
# press_key
# ─────────────────────────────────────────────────────────────
@registry.register(
    name="press_key",
    description=(
        "Presses one or more keyboard keys. Supports single keys and combinations. "
        "Examples: 'enter', 'escape', 'ctrl+c', 'ctrl+shift+t', 'alt+f4', 'win+d', 'ctrl+alt+delete'. "
        "Key names: enter, escape, tab, space, backspace, delete, home, end, pageup, pagedown, "
        "up, down, left, right, f1-f12, ctrl, alt, shift, win."
    ),
    args_schema={
        "keys": {"type": "string", "description": "Key or key combination to press, e.g. 'enter', 'ctrl+c', 'alt+f4'."},
        "presses": {"type": "integer", "description": "Number of times to press the key (default 1)."}
    },
    risk_level="medium"
)
class PressKeyTool(BaseTool):
    def execute(self, keys: str, presses: int = 1) -> dict:
        pag = _get_pyautogui()
        if pag is None:
            return _NOT_INSTALLED
        try:
            presses = max(1, int(presses))
            keys_lower = keys.lower().strip()
            if "+" in keys_lower:
                parts = [k.strip() for k in keys_lower.split("+")]
                for _ in range(presses):
                    pag.hotkey(*parts)
                    if presses > 1:
                        time.sleep(0.1)
            else:
                pag.press(keys_lower, presses=presses, interval=0.1)
            logger.info(f"PressKey: pressed '{keys}' x{presses}")
            return {"success": True, "output": f"Pressed key(s): '{keys}' x{presses}."}
        except Exception as e:
            logger.error(f"PressKey failed: {e}")
            return {"success": False, "output": str(e)}


# ─────────────────────────────────────────────────────────────
# scroll
# ─────────────────────────────────────────────────────────────
@registry.register(
    name="scroll",
    description="Scrolls the mouse wheel at the specified (x, y) screen position. Use direction 'up' or 'down'.",
    args_schema={
        "x": {"type": "string", "description": "Horizontal coordinate to scroll at, or 'center'."},
        "y": {"type": "string", "description": "Vertical coordinate to scroll at, or 'center'."},
        "direction": {"type": "string", "description": "'up' or 'down'."},
        "amount": {"type": "integer", "description": "Number of scroll ticks (default 3). More = further scroll."}
    },
    risk_level="low"
)
class ScrollTool(BaseTool):
    def execute(self, x, y, direction: str = "down", amount: int = 3) -> dict:
        pag = _get_pyautogui()
        if pag is None:
            return _NOT_INSTALLED
        try:
            if str(x).strip().lower() == "center" or str(y).strip().lower() == "center":
                w, h = pag.size()
                x = w // 2 if str(x).strip().lower() == "center" else int(x)
                y = h // 2 if str(y).strip().lower() == "center" else int(y)
            clicks = int(amount) if direction.strip().lower() == "up" else -int(amount)
            pag.scroll(clicks, x=int(x), y=int(y))
            logger.info(f"Scroll: {direction} x{amount} at ({x}, {y})")
            return {"success": True, "output": f"Scrolled {direction} {amount} ticks at ({x}, {y})."}
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return {"success": False, "output": str(e)}


# ─────────────────────────────────────────────────────────────
# drag
# ─────────────────────────────────────────────────────────────
@registry.register(
    name="drag",
    description="Clicks and drags the mouse from (start_x, start_y) to (end_x, end_y). Useful for sliders, drag-and-drop, or window resizing.",
    args_schema={
        "start_x": {"type": "string", "description": "Starting X coordinate, or 'center'."},
        "start_y": {"type": "string", "description": "Starting Y coordinate, or 'center'."},
        "end_x": {"type": "string", "description": "Ending X coordinate, or 'center'."},
        "end_y": {"type": "string", "description": "Ending Y coordinate, or 'center'."},
        "duration": {"type": "number", "description": "Time in seconds to complete the drag (default 0.5)."}
    },
    risk_level="medium"
)
class DragTool(BaseTool):
    def execute(self, start_x, start_y, end_x, end_y, duration: float = 0.5) -> dict:
        pag = _get_pyautogui()
        if pag is None:
            return _NOT_INSTALLED
        try:
            w, h = pag.size()
            start_x = w // 2 if str(start_x).strip().lower() == "center" else int(start_x)
            start_y = h // 2 if str(start_y).strip().lower() == "center" else int(start_y)
            end_x = w // 2 if str(end_x).strip().lower() == "center" else int(end_x)
            end_y = h // 2 if str(end_y).strip().lower() == "center" else int(end_y)
            
            ok1, err1 = _check_bounds(start_x, start_y, pag)
            ok2, err2 = _check_bounds(end_x, end_y, pag)
            if not ok1 or not ok2:
                err = err1 if not ok1 else err2
                logger.warning(f"Drag: rejected — {err}")
                return {"success": False, "output": err}
            
            pag.moveTo(start_x, start_y, duration=0.2)
            pag.dragTo(end_x, end_y, duration=float(duration), button="left")
            logger.info(f"Drag: ({start_x},{start_y}) -> ({end_x},{end_y})")
            return {"success": True, "output": f"Dragged from ({start_x},{start_y}) to ({end_x},{end_y})."}
        except Exception as e:
            logger.error(f"Drag failed: {e}")
            return {"success": False, "output": str(e)}


# ─────────────────────────────────────────────────────────────
# get_screen_size
# ─────────────────────────────────────────────────────────────
@registry.register(
    name="get_screen_size",
    description="Returns the current screen resolution (width and height in pixels). Useful before calculating coordinates for clicks.",
    args_schema={},
    risk_level="low"
)
class GetScreenSizeTool(BaseTool):
    def execute(self) -> dict:
        pag = _get_pyautogui()
        if pag is None:
            # Try ctypes fallback when pyautogui is missing
            try:
                import ctypes
                user32 = ctypes.windll.user32
                w = user32.GetSystemMetrics(0)
                h = user32.GetSystemMetrics(1)
                return {"success": True, "output": f"Screen size: {w} x {h} pixels.", "width": w, "height": h}
            except Exception:
                return _NOT_INSTALLED
        try:
            w, h = pag.size()
            logger.info(f"GetScreenSize: {w}x{h}")
            return {"success": True, "output": f"Screen size: {w} x {h} pixels.", "width": w, "height": h}
        except Exception as e:
            return {"success": False, "output": str(e)}
