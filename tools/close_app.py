import os
import time
import subprocess
from typing import Dict, Any, Optional
from tools.registry import registry, BaseTool
from config.logging import logger
from brain.app_resolver import app_resolver

def is_process_running(exe_name: str) -> bool:
    try:
        res = subprocess.run(["tasklist", "/nh", "/fi", f"imagename eq {exe_name}"], capture_output=True, text=True, check=False)
        return exe_name.lower() in res.stdout.lower()
    except Exception:
        return False

def terminate_process_tree(exe_name: str, pid: Optional[int] = None) -> dict:
    if not exe_name and not pid:
        return {"success": False, "output": "Empty process name and PID."}
        
    if exe_name and not exe_name.lower().endswith(".exe") and not exe_name.lower().endswith(".msc"):
        exe_name += ".exe"
        
    if exe_name and exe_name.lower() in ["uninstall.exe", "unins000.exe", "setup.exe", "update.exe"]:
        logger.error(f"Refusing to terminate dangerous executable: {exe_name}")
        return {"success": False, "output": f"Refusing to terminate uninstaller/updater process: {exe_name}"}
        
    import psutil
    
    # 1. Match PIDs
    matching_pids = []
    if pid:
        try:
            if psutil.pid_exists(pid):
                matching_pids.append(pid)
        except Exception: pass
    elif exe_name:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == exe_name.lower():
                    matching_pids.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
    termination_attempted = False

    if not matching_pids:
        # Before attempting taskkill, confirm the process is actually running
        if exe_name and not is_process_running(exe_name):
            logger.info(f"[CloseApp] '{exe_name}' is not running. Nothing to terminate.")
            return {
                "success": False,
                "output": f"'{exe_name}' does not appear to be running.",
                "attempted": False,
                "pids": [],
                "still_exists": False
            }
        # Process detected by name but psutil didn't enumerate a PID — fall through to taskkill

    try:
        if pid:
            res = subprocess.run(["taskkill", "/f", "/t", "/pid", str(pid)], capture_output=True, text=True, check=False)
            termination_attempted = True
        elif exe_name:
            res = subprocess.run(["taskkill", "/f", "/t", "/im", exe_name], capture_output=True, text=True, check=False)
            termination_attempted = True

        # Verify termination — check PIDs when available, otherwise check by name
        for _ in range(15):
            time.sleep(0.2)

            if exe_name and not is_process_running(exe_name):
                # Confirmed gone by name check — authoritative
                return {
                    "success": True,
                    "output": f"Successfully closed '{exe_name}'.",
                    "attempted": termination_attempted,
                    "pids": matching_pids,
                    "still_exists": False
                }

            if matching_pids:
                still_running = False
                for p in matching_pids:
                    if psutil.pid_exists(p):
                        try:
                            proc = psutil.Process(p)
                            if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                                still_running = True
                                break
                        except Exception:
                            pass
                if not still_running:
                    # All original PIDs gone — double-check by name to be safe
                    if not is_process_running(exe_name):
                        return {
                            "success": True,
                            "output": f"Successfully closed '{exe_name}'.",
                            "attempted": termination_attempted,
                            "pids": matching_pids,
                            "still_exists": False
                        }

        # Timed out — process still alive
        return {
            "success": False,
            "output": f"Process '{exe_name}' still detected after termination attempt.",
            "attempted": termination_attempted,
            "pids": matching_pids,
            "still_exists": True
        }
    except Exception as e:
        msg = f"Failed to terminate process tree for '{exe_name}': {e}"
        logger.error(msg)
        return {"success": False, "output": msg, "attempted": termination_attempted, "pids": matching_pids, "still_exists": True}

@registry.register(
    name="close_app",
    description="Closes a running Windows application by name.",
    args_schema={
        "app_name": {
            "type": "string",
            "description": "Name of the application to close (e.g. Chrome, Discord, Steam)."
        }
    },
    risk_level="medium"
)
class CloseAppTool(BaseTool):
    def execute(self, app_name: str) -> dict:
        import json
        
        exe_name = None
        pid = None
        
        # 1. Check launch cache
        cache_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "launch_cache.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    cache = json.load(f)
                    if app_name.lower().strip() in cache:
                        exe_name = cache[app_name.lower().strip()]["exe_name"]
                        pid = cache[app_name.lower().strip()]["pid"]
            except Exception:
                pass
                
        # 2. Fallback to app_resolver
        if not exe_name:
            resolved_path = app_resolver.resolve_app(app_name)
            if resolved_path:
                exe_name = os.path.basename(resolved_path)
            else:
                exe_name = app_name
                
        res = terminate_process_tree(exe_name, pid)
        
        attempted = res.get("attempted", False)
        still_exists = res.get("still_exists", False)
        success = res.get("success", False)
        pids = res.get("pids", [])
        
        logger.info(f"\n[CloseApp]\nRequested: {app_name}\nResolved Process: {exe_name}\nPID: {', '.join(map(str, pids)) if pids else 'None'}\nTermination Attempted: {'Yes' if attempted else 'No'}\nProcess Still Exists: {'Yes' if still_exists else 'False'}\nResult: {'Success' if success else 'Failed'}\n")
        
        return res

@registry.register(
    name="close_process",
    description="Closes a running process by name.",
    args_schema={
        "process_name": {
            "type": "string",
            "description": "Name of the process or executable to close (e.g., Discord.exe, msedge.exe)."
        }
    },
    risk_level="medium"
)
class CloseProcessTool(BaseTool):
    def execute(self, process_name: str) -> dict:
        logger.info(f"CloseProcessTool executing for process_name: '{process_name}'")
        return terminate_process_tree(process_name)
