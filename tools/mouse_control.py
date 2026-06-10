import pydirectinput
import time
from tools.registry import registry, BaseTool

# Configure PyDirectInput defaults
pydirectinput.FAILSAFE = True

@registry.register(
    name="move_mouse",
    description="Moves the mouse cursor to the specified absolute x and y coordinates on the screen.",
    args_schema={
        "x": {"type": ["integer", "string"], "description": "Absolute x-coordinate to move to. Can be 'last_x' to use the cached coordinate from locate_ui_element."},
        "y": {"type": ["integer", "string"], "description": "Absolute y-coordinate to move to. Can be 'last_y' to use the cached coordinate from locate_ui_element."}
    },
    risk_level="low"
)
class MoveMouseTool(BaseTool):
    def execute(self, x, y, **kwargs) -> dict:
        try:
            from config.state import state_manager
            
            if isinstance(x, str) and x == "last_x":
                x = state_manager.get_state().last_ui_x
            if isinstance(y, str) and y == "last_y":
                y = state_manager.get_state().last_ui_y
                
            if x is None or y is None:
                return {"success": False, "error": "Coordinates were not cached. Run locate_ui_element first."}
                
            pydirectinput.moveTo(int(x), int(y))
            return {"success": True, "output": f"Mouse moved to ({x}, {y})"}
        except Exception as e:
            return {"success": False, "error": str(e)}

@registry.register(
    name="scroll",
    description="Scrolls the mouse wheel up or down. A positive value scrolls up, and a negative value scrolls down.",
    args_schema={
        "amount": {"type": "integer", "description": "Amount to scroll. Positive for up, negative for down."}
    },
    risk_level="low"
)
class ScrollTool(BaseTool):
    def execute(self, amount: int, **kwargs) -> dict:
        try:
            # pydirectinput doesn't natively support scroll very well, but let's try
            # If pydirectinput's scroll doesn't work, we fallback to pyautogui or similar if needed.
            # actually pydirectinput does not implement scroll. Let's use pyautogui for scrolling if needed,
            # or simulate up/down arrow keys.
            import pyautogui
            pyautogui.scroll(amount)
            return {"success": True, "output": f"Scrolled by {amount}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

# --- SAFE_MODE Internal Functions (Not exposed to planner yet) ---
# When exposed, these will require explicit user confirmation.

def internal_click(button="left", double=False):
    """Internal function for clicking. Requires SAFE_MODE confirmation when exposed."""
    if double:
        pydirectinput.doubleClick(button=button)
    else:
        pydirectinput.click(button=button)

def internal_drag(start_x, start_y, end_x, end_y):
    """Internal function for dragging. Requires SAFE_MODE confirmation when exposed."""
    pydirectinput.moveTo(start_x, start_y)
    pydirectinput.mouseDown()
    time.sleep(0.1)
    pydirectinput.moveTo(end_x, end_y)
    time.sleep(0.1)
    pydirectinput.mouseUp()

tool_move = MoveMouseTool()
tool_scroll = ScrollTool()
