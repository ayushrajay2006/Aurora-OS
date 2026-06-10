import os
import json
import time
from typing import List, Tuple
from tools.registry import registry, BaseTool
from config.logging import logger
from brain.app_resolver import app_resolver
from brain.desktop_context import desktop_context

try:
    import psutil
    import win32gui
    import win32process
    import win32con
    import win32api
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

def get_pids_for_app(app_name: str) -> List[int]:
    """Resolves an app name to active PIDs using cache or direct search."""
    # 1. Try launch cache
    cache_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "launch_cache.json")
    exe_name = None
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cache = json.load(f)
            query = app_name.lower().strip()
            if query in cache:
                exe_name = cache[query].get("exe_name")
        except Exception:
            pass
            
    # 2. Try app_resolver directly
    if not exe_name:
        resolved_path = app_resolver.resolve_app(app_name)
        if resolved_path:
            # For UWP or Steam URLs we might not have a clean exe_name easily here, but we can try
            if not resolved_path.startswith("steam://") and "!" not in resolved_path:
                exe_name = os.path.basename(resolved_path).lower()
                if not exe_name.endswith(".exe"):
                    exe_name += ".exe"

    if not exe_name:
        # Fallback assumption
        exe_name = app_name.lower().strip()
        if not exe_name.endswith(".exe"):
            exe_name += ".exe"

    pids = []
    for p in psutil.process_iter(['name', 'pid']):
        try:
            if p.info['name'] and p.info['name'].lower() == exe_name:
                pids.append(p.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    return pids

def get_hwnds_for_pids(pids: List[int]) -> List[int]:
    """Finds all visible windows belonging to the given PIDs."""
    hwnds = []
    def callback(hwnd, hwnds_list):
        if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
            if found_pid in pids:
                hwnds_list.append(hwnd)
        return True
    win32gui.EnumWindows(callback, hwnds)
    return hwnds

class ControlAppBase(BaseTool):
    def force_set_foreground_window(self, hwnd: int) -> bool:
        """Forces a window to the foreground by bypassing OS locks using AttachThreadInput."""
        try:
            current_fg = win32gui.GetForegroundWindow()
            if current_fg == hwnd:
                return True
                
            if current_fg:
                fg_thread, _ = win32process.GetWindowThreadProcessId(current_fg)
                my_thread = win32api.GetCurrentThreadId()
                
                if fg_thread != my_thread:
                    try:
                        win32process.AttachThreadInput(my_thread, fg_thread, True)
                        win32gui.SetForegroundWindow(hwnd)
                        win32process.AttachThreadInput(my_thread, fg_thread, False)
                        return True
                    except Exception:
                        pass
                        
            # Fallback
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as e:
            logger.warning(f"force_set_foreground_window failed: {e}")
            return False

    def execute_control(self, app_name: str, action: str) -> dict:
        if not HAS_DEPS:
            return {"success": False, "output": "Missing required dependencies (psutil, pywin32)."}
            
        logger.info(f"[{action.capitalize()}App] Requested: {app_name}")
        pids = get_pids_for_app(app_name)
        if not pids:
            msg = f"Could not find any running processes for '{app_name}'."
            logger.warning(f"[{action.capitalize()}App] {msg}")
            return {"success": False, "output": msg}
            
        hwnds = get_hwnds_for_pids(pids)
        if not hwnds:
            msg = f"Found processes for '{app_name}' but no visible windows to control."
            logger.warning(f"[{action.capitalize()}App] {msg}")
            return {"success": False, "output": msg}
            
        # Target the real main windows, filtering out tool windows, empty wrappers, and off-screen rects
        real_hwnds = []
        for h in hwnds:
            title = win32gui.GetWindowText(h).strip()
            if not title:
                continue
                
            style = win32api.GetWindowLong(h, win32con.GWL_STYLE)
            ex_style = win32api.GetWindowLong(h, win32con.GWL_EXSTYLE)
            
            if ex_style & win32con.WS_EX_TOOLWINDOW:
                continue
                
            rect = win32gui.GetWindowRect(h)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            if width <= 0 or height <= 0:
                if not win32gui.IsIconic(h):
                    continue
                    
            real_hwnds.append(h)
            
        target_hwnd = real_hwnds[0] if real_hwnds else (hwnds[0] if hwnds else None)
        
        if not target_hwnd:
            msg = f"Found processes for '{app_name}' but no valid main window to control."
            logger.warning(f"[{action.capitalize()}App] {msg}")
            return {"success": False, "output": msg}
        
        
        logger.info(f"[{action.capitalize()}App] Found HWND: {target_hwnd} for PIDs: {pids}")

        try:
            if action == "minimize":
                win32gui.ShowWindow(target_hwnd, win32con.SW_MINIMIZE)
                time.sleep(0.5)
                # Verify
                if win32gui.IsIconic(target_hwnd):
                    return {"success": True, "output": f"Successfully minimized '{app_name}'."}
                else:
                    return {"success": False, "output": f"Window API call completed but window was not minimized."}
                    
            elif action == "maximize":
                win32gui.ShowWindow(target_hwnd, win32con.SW_MAXIMIZE)
                self.force_set_foreground_window(target_hwnd)
                time.sleep(0.5)
                # Verify
                if win32gui.GetForegroundWindow() == target_hwnd:
                    desktop_context.update_focused(app_name)
                    return {"success": True, "output": f"Successfully maximized '{app_name}'."}
                else:
                    return {"success": False, "output": f"Window API call completed but failed to maximize."}

            elif action == "restore":
                win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                self.force_set_foreground_window(target_hwnd)
                time.sleep(0.5)
                # Verify
                if win32gui.GetForegroundWindow() == target_hwnd or not win32gui.IsIconic(target_hwnd):
                    desktop_context.update_focused(app_name)
                    return {"success": True, "output": f"Successfully restored '{app_name}'."}
                else:
                    return {"success": False, "output": f"Window API call completed but failed to restore."}

            elif action == "switch":
                if win32gui.IsIconic(target_hwnd):
                    win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                self.force_set_foreground_window(target_hwnd)
                time.sleep(0.5)
                # Verify
                # Verify by checking if the foreground window belongs to the app's PIDs
                fg_hwnd = win32gui.GetForegroundWindow()
                _, fg_pid = win32process.GetWindowThreadProcessId(fg_hwnd) if fg_hwnd else (0, 0)
                
                if fg_pid in pids or fg_hwnd == target_hwnd:
                    desktop_context.update_focused(app_name)
                    return {"success": True, "output": f"Successfully switched to '{app_name}'."}
                else:
                    return {"success": False, "output": f"Window API call completed but failed to switch foreground."}

        except Exception as e:
            msg = f"Failed to {action} '{app_name}': {e}"
            logger.error(f"[{action.capitalize()}App] {msg}")
            return {"success": False, "output": msg}
            
        return {"success": False, "output": "Unknown action."}

@registry.register(
    name="switch_to_app",
    description="Brings the specified application window to the foreground.",
    args_schema={"app_name": {"type": "string"}},
    risk_level="low"
)
class SwitchToAppTool(ControlAppBase):
    def execute(self, app_name: str) -> dict:
        return self.execute_control(app_name, "switch")

@registry.register(
    name="minimize_app",
    description="Minimizes the specified application window.",
    args_schema={"app_name": {"type": "string"}},
    risk_level="low"
)
class MinimizeAppTool(ControlAppBase):
    def execute(self, app_name: str) -> dict:
        return self.execute_control(app_name, "minimize")

@registry.register(
    name="maximize_app",
    description="Maximizes the specified application window.",
    args_schema={"app_name": {"type": "string"}},
    risk_level="low"
)
class MaximizeAppTool(ControlAppBase):
    def execute(self, app_name: str) -> dict:
        return self.execute_control(app_name, "maximize")

@registry.register(
    name="restore_app",
    description="Restores the specified application window from a minimized state.",
    args_schema={"app_name": {"type": "string"}},
    risk_level="low"
)
class RestoreAppTool(ControlAppBase):
    def execute(self, app_name: str) -> dict:
        return self.execute_control(app_name, "restore")

@registry.register(
    name="wait_for_window",
    description="Waits for an application to launch and fully render its window on screen. Always use this between opening an app and interacting with it.",
    args_schema={"app_name": {"type": "string"}},
    risk_level="low"
)
class WaitForWindowTool(ControlAppBase):
    def execute(self, app_name: str, timeout: int = 10) -> dict:
        if not HAS_DEPS:
            return {"success": False, "output": "Missing required dependencies."}
            
        logger.info(f"[WaitWindow] Waiting for '{app_name}' (timeout: {timeout}s)...")
        start_time = time.time()
        
        process_pass = False
        visible_pass = False
        foreground_pass = False
        
        pids = []
        target_hwnd = None
        
        while time.time() - start_time < timeout:
            if not process_pass:
                pids = get_pids_for_app(app_name)
                if pids:
                    process_pass = True
                    
            if process_pass and not visible_pass:
                hwnds = get_hwnds_for_pids(pids)
                if hwnds:
                    # Filter real hwnds
                    real_hwnds = []
                    for h in hwnds:
                        title = win32gui.GetWindowText(h).strip()
                        if title:
                            ex_style = win32api.GetWindowLong(h, win32con.GWL_EXSTYLE)
                            if not (ex_style & win32con.WS_EX_TOOLWINDOW):
                                rect = win32gui.GetWindowRect(h)
                                width = rect[2] - rect[0]
                                height = rect[3] - rect[1]
                                if width > 0 and height > 0 or win32gui.IsIconic(h):
                                    real_hwnds.append(h)
                    target_hwnd = real_hwnds[0] if real_hwnds else (hwnds[0] if hwnds else None)
                    if target_hwnd:
                        visible_pass = True
                        
            if visible_pass and not foreground_pass:
                if win32gui.GetForegroundWindow() == target_hwnd:
                    foreground_pass = True
                    break # We have all 3!
            
            time.sleep(0.5)
            
        # Compile result
        output_msg = (
            f"Wait results for '{app_name}':\n"
            f"* Process: {'PASS' if process_pass else 'FAIL'}\n"
            f"* Visible Window: {'NOT TESTED' if not process_pass else ('PASS' if visible_pass else 'FAIL')}\n"
            f"* Foreground: {'NOT TESTED' if not visible_pass else ('PASS' if foreground_pass else 'FAIL')}"
        )
        
        # Determine success condition. The user requires wait_for_window to ensure readiness.
        # If it doesn't get to visible, it's definitely a failure. 
        # Foreground isn't strictly required to pass `wait_for_window` if `switch_to_app` runs next, but `switch_to_app` will fix foreground.
        # Actually wait, let's consider it success if the visible window exists, since switch_to_app is called after.
        success = visible_pass
        
        return {"success": success, "output": output_msg}

tool_switch = SwitchToAppTool()
tool_min = MinimizeAppTool()
tool_max = MaximizeAppTool()
tool_restore = RestoreAppTool()
tool_wait = WaitForWindowTool()
