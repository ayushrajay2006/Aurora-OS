import pydirectinput
import time
from tools.registry import registry, BaseTool

# Configure PyDirectInput defaults
pydirectinput.FAILSAFE = True
# PyDirectInput sometimes types too fast for some applications, 0.01 is a safe default
pydirectinput.PAUSE = 0.01

@registry.register(
    name="type_text",
    description="Types a sequence of text characters sequentially.",
    args_schema={
        "text": {"type": "string", "description": "The string of text to type."},
        "interval": {"type": "number", "description": "Seconds to pause between each character.", "default": 0.01}
    },
    risk_level="low"
)
class TypeTextTool(BaseTool):
    def execute(self, text: str, interval: float = 0.01, **kwargs) -> dict:
        try:
            # pydirectinput.typewrite types characters
            pydirectinput.typewrite(text, interval=interval)
            return {"success": True, "output": f"Typed text successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}

@registry.register(
    name="press_key",
    description="Presses and releases a single key (e.g., 'enter', 'tab', 'esc', 'space', 'backspace').",
    args_schema={
        "key": {"type": "string", "description": "The name of the key to press."}
    },
    risk_level="low"
)
class PressKeyTool(BaseTool):
    def execute(self, key: str, **kwargs) -> dict:
        try:
            pydirectinput.press(key)
            return {"success": True, "output": f"Pressed key: {key}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

@registry.register(
    name="hotkey",
    description="Executes a keyboard shortcut involving multiple keys (e.g., ['ctrl', 'c'], ['alt', 'tab']).",
    args_schema={
        "keys": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of keys to press sequentially and release in reverse order."
        }
    },
    risk_level="low"
)
class HotkeyTool(BaseTool):
    def execute(self, keys: list, **kwargs) -> dict:
        try:
            # pydirectinput doesn't have a hotkey() function out of the box that accepts a list easily,
            # wait, it does have hotkey.
            for key in keys:
                pydirectinput.keyDown(key)
            
            for key in reversed(keys):
                pydirectinput.keyUp(key)
                
            return {"success": True, "output": f"Executed hotkey: {'+'.join(keys)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

tool_type = TypeTextTool()
tool_press = PressKeyTool()
tool_hotkey = HotkeyTool()
