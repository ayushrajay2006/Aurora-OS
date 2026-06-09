import os
import subprocess
import time
import psutil
import shutil
from typing import Optional, Dict, Any
from tools.registry import registry, BaseTool
from config.logging import logger
from brain.app_resolver import app_resolver
from brain.desktop_context import desktop_context
import json

@registry.register(
    name="open_app",
    description="Opens a Windows application or common system folder by name.",
    args_schema={
        "app_name": {
            "type": "string",
            "description": "Name of the application or folder to launch (e.g., Chrome, Discord, VS Code, Notepad, Calculator, Downloads, Documents, Pictures, Screenshots)"
        }
    },
    risk_level="medium"
)
class OpenAppTool(BaseTool):
    def execute(self, app_name: str) -> dict:
        logger.info(f"OpenAppTool executing for app_name: '{app_name}'")

        app_name_clean = app_name.strip('\"\'')

        # Accept direct executable names like code.exe without forcing a second
        # resolver round-trip that can downgrade confidence.
        if os.path.isabs(app_name_clean) and os.path.exists(app_name_clean):
            resolved_path = app_name_clean
            logger.info(f"OpenAppTool using direct absolute path: {resolved_path}")
        elif app_name_clean.lower().endswith((".exe", ".msc")) and shutil.which(app_name_clean):
            resolved_path = app_name_clean
            logger.info(f"OpenAppTool using executable available on PATH: {resolved_path}")
        elif app_name_clean.startswith("steam://") or "!" in app_name_clean:
            resolved_path = app_name_clean
            logger.info(f"OpenAppTool using direct URI/AppID target: {resolved_path}")
        else:
            resolved_path = app_resolver.resolve_app(app_name)

        if not resolved_path:
            msg = f"Could not confidently resolve application '{app_name}'. Please provide the exact name or path."
            logger.error(msg)
            return {"success": False, "output": msg}

        try:
            resolved_path_clean = resolved_path.strip('\"\'')
            
            pids_before = set(psutil.pids())
            exe_name = None
            
            # Special case for UWP apps / Xbox games from Get-StartApps
            if "!" in resolved_path_clean and not os.path.exists(resolved_path_clean) and not resolved_path_clean.startswith("steam://"):
                logger.info(f"Launching UWP AppID: {resolved_path_clean}")
                os.startfile(f"shell:AppsFolder\\{resolved_path_clean}")
                exe_name = resolved_path_clean
                
            # Special case for Steam URIs
            elif resolved_path_clean.startswith("steam://"):
                logger.info(f"Launching Steam URI: {resolved_path_clean}")
                os.startfile(resolved_path_clean)
                exe_name = resolved_path_clean
                
            # Special case for Discord AppData Update launcher: needs arguments to boot properly
            elif "discord" in app_name.lower() and resolved_path_clean.endswith("Update.exe"):
                subprocess.Popen([resolved_path_clean, "--processStart=Discord.exe"], shell=False)
                exe_name = "discord.exe"
            else:
                exe_name = os.path.basename(resolved_path_clean).lower()
                os.startfile(resolved_path_clean)
                
            # Wait a bit for process to spawn
            time.sleep(1.5)
            
            pids_after = set(psutil.pids())
            new_pids = pids_after - pids_before
            
            # Since UWP apps / Steam URLs might not immediately register matching exe names in psutil directly,
            # or they might spawn background services, we consider the os.startfile success as passing for them,
            # but still try to cache PIDs if possible.
            exe_running = False
            if exe_name and not exe_name.startswith("steam://") and "!" not in exe_name:
                if not exe_name.endswith(".exe"):
                    exe_name += ".exe"
                for p in psutil.process_iter(['name']):
                    try:
                        if p.info['name'] and p.info['name'].lower() == exe_name:
                            exe_running = True
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                        
                if not new_pids and not exe_running:
                    msg = f"Failed to verify launch of '{app_name}'. No new processes or matching windows found."
                    logger.error(msg)
                    return {"success": False, "output": msg}
            else:
                exe_running = True # Bypass strict process name check for UWP/Steam URLs
                
            # Store launch cache for close_app
            cache_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "launch_cache.json")
            cache_data = {}
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r") as f:
                        cache_data = json.load(f)
                except Exception:
                    pass
            
            cache_data[app_name.lower().strip()] = {
                "exe_name": exe_name,
                "pid": list(new_pids)[0] if new_pids else None
            }
            if exe_name and "!" not in exe_name and not exe_name.startswith("steam://"):
                cache_data[exe_name.lower().strip()] = cache_data[app_name.lower().strip()]
                
            try:
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                with open(cache_file, "w") as f:
                    json.dump(cache_data, f, indent=4)
            except Exception as e:
                logger.warning(f"Failed to write launch_cache.json: {e}")
                
            logger.info(f"Successfully verified launch: '{app_name}'")
            desktop_context.update_opened(app_name)
            return {"success": True, "output": f"Successfully opened '{app_name}'."}
        except Exception as e:
            msg = f"Failed to open '{app_name}': {e}"
            logger.error(msg)
            return {"success": False, "output": msg}
