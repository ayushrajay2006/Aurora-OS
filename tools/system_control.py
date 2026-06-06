import os
import subprocess
from typing import Dict, Any, Optional
from tools.registry import registry, BaseTool
from config.logging import logger

@registry.register(
    name="system_control",
    description="Manages core Windows system operations including power (shutdown, restart, sleep) and display (brightness).",
    args_schema={
        "action": {
            "type": "string",
            "description": "The action to perform: 'shutdown', 'restart', 'sleep', 'hibernate', 'sign_out', 'lock', 'brightness_up', 'brightness_down'.",
            "enum": ["shutdown", "restart", "sleep", "hibernate", "sign_out", "lock", "brightness_up", "brightness_down"]
        }
    },
    risk_level="critical"
)
class SystemControlTool(BaseTool):
    def execute(self, action: str) -> dict:
        action = action.lower().strip()
        logger.info(f"SystemControl: Executing '{action}'")

        try:
            if action == "shutdown":
                os.system("shutdown /s /t 0")
                return {"success": True, "output": "Initiating system shutdown."}
            elif action == "restart":
                os.system("shutdown /r /t 0")
                return {"success": True, "output": "Initiating system restart."}
            elif action == "sign_out":
                os.system("shutdown /l")
                return {"success": True, "output": "Initiating sign out."}
            elif action == "hibernate":
                os.system("shutdown /h")
                return {"success": True, "output": "Initiating system hibernation."}
            elif action == "sleep":
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                return {"success": True, "output": "Initiating system sleep."}
            elif action == "lock":
                os.system("rundll32.exe user32.dll,LockWorkStation")
                return {"success": True, "output": "System locked."}
            elif action in ["brightness_up", "brightness_down"]:
                return self._adjust_brightness(action)
            else:
                return {"success": False, "output": f"Unknown action: {action}"}
        except Exception as e:
            logger.error(f"SystemControl failed: {e}")
            return {"success": False, "output": f"Failed to execute {action}: {e}"}

    def _adjust_brightness(self, action: str) -> dict:
        try:
            import wmi
            w = wmi.WMI(namespace='wmi')
            methods = w.WmiMonitorBrightnessMethods()[0]
            current = w.WmiMonitorBrightness()[0].CurrentBrightness
            
            step = 10
            new_val = current + step if action == "brightness_up" else current - step
            new_val = max(0, min(100, new_val))
            
            methods.WmiSetBrightness(new_val, 0)
            return {"success": True, "output": f"Brightness set to {new_val}%."}
        except ImportError:
            return {"success": False, "output": "Failed to adjust brightness: 'wmi' module is not installed. Please run 'pip install WMI'."}
        except Exception as e:
            return {"success": False, "output": f"Failed to adjust brightness (desktop monitors may not support this): {e}"}
