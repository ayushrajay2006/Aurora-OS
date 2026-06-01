import os
import winreg
import subprocess
from typing import Optional, Dict, Any
from tools.registry import registry, BaseTool
from config.logging import logger

def search_registry_app_paths(app_name: str) -> Optional[str]:
    """Scans Windows Registry 'App Paths' to find the absolute executable path."""
    app_name_clean = app_name.lower().strip()
    
    # Try both HKEY_LOCAL_MACHINE and HKEY_CURRENT_USER
    for hkey in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        sub_key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        try:
            with winreg.OpenKey(hkey, sub_key_path) as key:
                info = winreg.QueryInfoKey(key)
                for i in range(info[0]): # Iterate through all subkeys
                    subkey_name = winreg.EnumKey(key, i)
                    # Match if app_name is contained in registry subkey (e.g. "chrome" in "chrome.exe")
                    name_without_ext = subkey_name.lower().replace(".exe", "")
                    if app_name_clean == name_without_ext or app_name_clean in name_without_ext:
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            try:
                                # Get the (Default) value which contains the executable path
                                path, _ = winreg.QueryValue(subkey, "")
                                if os.path.exists(path):
                                    return path
                            except Exception:
                                pass
        except Exception:
            pass
    return None

def search_start_menu(app_name: str) -> Optional[str]:
    """Recursively walks Windows Start Menu folders to find matching .lnk shortcut files."""
    paths = [
        os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), "Microsoft\\Windows\\Start Menu\\Programs"),
        os.path.join(os.environ.get("AppData", ""), "Microsoft\\Windows\\Start Menu\\Programs")
    ]
    
    app_name_clean = app_name.lower().strip()
    for base_path in paths:
        if not os.path.exists(base_path):
            continue
        for root, _, files in os.walk(base_path):
            for file in files:
                if file.lower().endswith(".lnk"):
                    shortcut_name = file[:-4].lower() # strip .lnk
                    # Match exact or partial names
                    if app_name_clean == shortcut_name or app_name_clean in shortcut_name:
                        shortcut_path = os.path.join(root, file)
                        if os.path.exists(shortcut_path):
                            return shortcut_path
    return None

def search_common_paths(app_name: str) -> Optional[str]:
    """Fallbacks for hardcoded popular applications on Windows."""
    app_name_clean = app_name.lower().strip()
    
    # Common system utilities, directories, and setting protocols
    system_utilities = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "paint": "mspaint.exe",
        "cmd": "cmd.exe",
        "powershell": "powershell.exe",
        "explorer": "explorer.exe",
        "task manager": "taskmgr.exe",
        "taskmanager": "taskmgr.exe",
        "taskmgr": "taskmgr.exe",
        "recycle bin": "explorer.exe shell:RecycleBinFolder",
        "recyclebin": "explorer.exe shell:RecycleBinFolder",
        "screenshots": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\default"), "Pictures", "Screenshots"),
        "screenshots folder": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\default"), "Pictures", "Screenshots"),
        "pictures": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\default"), "Pictures"),
        "pictures folder": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\default"), "Pictures"),
        "videos": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\default"), "Videos"),
        "videos folder": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\default"), "Videos"),
        "music": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\default"), "Music"),
        "music folder": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\default"), "Music"),
        "control panel": "control.exe",
        "controlpanel": "control.exe",
        "file explorer": "explorer.exe",
        "fileexplorer": "explorer.exe",
        "documents": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\default"), "Documents"),
        "downloads": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\default"), "Downloads"),
        "this pc": "explorer.exe shell:MyComputerFolder",
        "my computer": "explorer.exe shell:MyComputerFolder",
        "command prompt": "cmd.exe",
        "commandprompt": "cmd.exe",
        "settings": "start ms-settings:",
        "system settings": "start ms-settings:",
        "systemsettings": "start ms-settings:",
        "registry editor": "regedit.exe",
        "registryeditor": "regedit.exe",
        "regedit": "regedit.exe",
        "device manager": "devmgmt.msc",
        "devicemanager": "devmgmt.msc",
        "disk management": "diskmgmt.msc",
        "diskmanagement": "diskmgmt.msc",
        "snipping tool": "snippingtool.exe",
        "snippingtool": "snippingtool.exe",
        "microsoft edge": "msedge.exe",
        "microsoftedge": "msedge.exe",
        "edge": "msedge.exe",
        "vs code": "code.exe",
        "vscode": "code.exe",
        "visual studio code": "code.exe",
        "visualstudiocode": "code.exe"
    }
    
    if app_name_clean in system_utilities:
        return system_utilities[app_name_clean]
        
    # Popular manual installation paths
    common_installations = {
        "chrome": [
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
        ],
        "vscode": [
            os.path.join(os.environ.get("LocalAppData", ""), "Programs\\Microsoft VS Code\\Code.exe"),
            "C:\\Program Files\\Microsoft VS Code\\Code.exe"
        ],
        "discord": [
            os.path.join(os.environ.get("LocalAppData", ""), "Discord\\Update.exe") # update.exe runs discord
        ]
    }
    
    if app_name_clean in common_installations:
        for path in common_installations[app_name_clean]:
            if os.path.exists(path):
                return path
                
    return None

def search_drive_subfolders(app_name: str) -> Optional[str]:
    """Performs a fast, shallow search (up to 3 levels) on the active D: and C: drives for custom applications."""
    app_name_clean = app_name.lower().strip()
    if not app_name_clean.endswith(".exe"):
        app_name_clean += ".exe"
        
    scan_roots = [
        "D:\\Reality Escape",
        "D:\\Games",
        "D:\\SteamLibrary",
        "D:\\EpicGames",
        "D:\\",
        "C:\\Games"
    ]
    
    for base_path in scan_roots:
        if not os.path.exists(base_path):
            continue
        try:
            for root, dirs, files in os.walk(base_path):
                # Restrict search depth to 3 to keep it extremely fast (under 50ms)
                depth = root.replace(base_path, "").count(os.sep)
                if depth > 3:
                    dirs.clear()
                    continue
                for file in files:
                    if file.lower() == app_name_clean:
                        path = os.path.join(root, file)
                        if os.path.exists(path):
                            return path
        except Exception:
            pass
    return None

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
        logger.info(f"Attempting to resolve path for application: '{app_name}'")
        
        # 1. Try Registry App Paths
        resolved_path = search_registry_app_paths(app_name)
        if resolved_path:
            logger.debug(f"Resolved app path via registry: {resolved_path}")
        
        # 2. Try Start Menu Shortcuts
        if not resolved_path:
            resolved_path = search_start_menu(app_name)
            if resolved_path:
                logger.debug(f"Resolved app path via Start Menu: {resolved_path}")
                
        # 3. Try custom drive subfolders search
        if not resolved_path:
            resolved_path = search_drive_subfolders(app_name)
            if resolved_path:
                logger.debug(f"Resolved app path via drive search: {resolved_path}")
                
        # 4. Try Common Paths / Fallbacks
        if not resolved_path:
            resolved_path = search_common_paths(app_name)
            if resolved_path:
                logger.debug(f"Resolved app path via common paths: {resolved_path}")
                
        # Launch resolution
        if not resolved_path:
            # Last resort: Try launching directly by command name in standard PATH
            logger.warning(f"Could not locate absolute path for '{app_name}'. Attempting direct shell execution.")
            resolved_path = app_name.lower().strip()
            
        try:
            # Special case for Discord AppData Update launcher: needs arguments to boot properly
            if "discord" in app_name.lower() and resolved_path.endswith("Update.exe"):
                # Discord Update.exe needs --processStart=Discord.exe
                subprocess.Popen([resolved_path, "--processStart=Discord.exe"])
                return {"success": True, "output": f"Successfully launched Discord using updater."}
                
            # Standard launching using os.startfile (safer, handles .lnk files natively)
            if os.path.isabs(resolved_path):
                os.startfile(resolved_path)
            else:
                # System utilities in PATH like cmd or calc
                subprocess.Popen(resolved_path, shell=True)
                
            logger.info(f"Successfully launched: '{app_name}'")
            return {"success": True, "output": f"Successfully opened '{app_name}'."}
        except Exception as e:
            msg = f"Failed to open '{app_name}': {e}"
            logger.error(msg)
            return {"success": False, "output": msg}

def close_process_by_name(name: str) -> dict:
    """Closes a process or application on Windows by name using taskkill with fuzzy and substring matching."""
    name_clean = name.strip()
    if not name_clean:
        return {"success": False, "output": "Empty process name provided."}

    # Gather potential executable names to terminate
    targets = []
    
    # 1. Direct matching
    targets.append(name_clean)
    if not name_clean.lower().endswith(".exe"):
        targets.append(f"{name_clean}.exe")
        
    # 2. Handle common hardcoded aliases
    alias_map = {
        "epic games launcher": "EpicGamesLauncher.exe",
        "epicgameslauncher": "EpicGamesLauncher.exe",
        "epic games": "EpicGamesLauncher.exe",
        "epicgames": "EpicGamesLauncher.exe",
        "epic": "EpicGamesLauncher.exe",
        "chrome": "chrome.exe",
        "discord": "Discord.exe",
        "vs code": "Code.exe",
        "vscode": "Code.exe",
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "task manager": "taskmgr.exe",
        "taskmanager": "taskmgr.exe",
        "taskmgr": "taskmgr.exe"
    }
    alias_key = name_clean.lower()
    if alias_key in alias_map:
        alias_target = alias_map[alias_key]
        if alias_target not in targets:
            targets.append(alias_target)

    # 3. Dynamic running process scanning (substring and word-based matching)
    try:
        # Fetch all running processes using tasklist
        res = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            lines = res.stdout.strip().split("\n")
            running_exes = []
            for line in lines:
                if not line.strip():
                    continue
                # Split CSV row: e.g. "taskhostw.exe","2468","Services","0","15,232 K"
                parts = [p.strip('"') for p in line.split(",")]
                if parts:
                    exe_name = parts[0]
                    if exe_name.lower().endswith(".exe") and exe_name not in running_exes:
                        running_exes.append(exe_name)
                        
            # Fuzzy match running processes
            cleaned_search = name_clean.lower().replace(" ", "")
            search_words = [w.lower() for w in name_clean.split() if len(w) >= 3]
            
            for exe in running_exes:
                exe_lower = exe.lower()
                exe_no_ext = exe_lower.replace(".exe", "")
                exe_clean = exe_no_ext.replace(" ", "").replace("_", "").replace("-", "")
                
                # Check 3.1: Search term (without spaces) is inside the process name (without spaces/extensions) or vice versa
                if cleaned_search in exe_clean or exe_clean in cleaned_search:
                    if exe not in targets:
                        targets.append(exe)
                        continue
                        
                # Check 3.2: Any search word of length >= 3 matches a running process name
                for word in search_words:
                    if word in exe_clean:
                        if exe not in targets:
                            targets.append(exe)
                            break
    except Exception as e:
        logger.error(f"Failed to scan running processes: {e}")

    # Remove duplicates but keep order
    unique_targets = []
    for t in targets:
        if t not in unique_targets:
            unique_targets.append(t)
            
    logger.info(f"Resolved process targets for '{name}': {unique_targets}")
    
    # Run taskkill for each target
    success_count = 0
    errors = []
    
    for target in unique_targets:
        try:
            # /f forces termination, /im specifies image name
            res = subprocess.run(
                ["taskkill", "/f", "/im", target],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                success_count += 1
                logger.info(f"Successfully closed process matching: '{target}'")
            elif "Access is denied" in res.stderr:
                errors.append(f"'{target}': Access was denied. This usually means the application (like Task Manager) is running with administrator/elevated privileges and requires Aurora's host terminal to be run as Administrator to terminate it.")
            elif "not found" in res.stderr.lower():
                # Process not running - only log if it's the direct user input name
                if target.lower() == name_clean.lower() or target.lower() == f"{name_clean.lower()}.exe":
                    errors.append(f"'{target}': Process not found or not running.")
            else:
                errors.append(f"'{target}': {res.stderr.strip()}")
        except Exception as e:
            errors.append(f"Failed to execute taskkill for '{target}': {e}")
            
    if success_count > 0:
        return {
            "success": True,
            "output": f"Successfully closed running instances of '{name}'."
        }
    else:
        # If nothing succeeded, return failure details
        unique_errors = []
        for err in errors:
            if err not in unique_errors:
                unique_errors.append(err)
        err_msg = "; ".join(unique_errors) if unique_errors else "Process not found or not running."
        return {
            "success": False,
            "output": f"Could not close '{name}': {err_msg}"
        }

@registry.register(
    name="close_app",
    description="Closes a running Windows application or process by name.",
    args_schema={
        "app_name": {
            "type": "string",
            "description": "Name of the application or process to close (e.g., Chrome, Discord, Epic Games Launcher, Notepad)"
        }
    },
    risk_level="medium"
)
class CloseAppTool(BaseTool):
    def execute(self, app_name: str) -> dict:
        logger.info(f"Attempting to close application: '{app_name}'")
        return close_process_by_name(app_name)

@registry.register(
    name="close_process",
    description="Closes a running process by name.",
    args_schema={
        "process_name": {
            "type": "string",
            "description": "Name of the process or executable to close (e.g., chrome.exe, Discord.exe, EpicGamesLauncher.exe)"
        }
    },
    risk_level="medium"
)
class CloseProcessTool(BaseTool):
    def execute(self, process_name: str) -> dict:
        logger.info(f"Attempting to close process: '{process_name}'")
        return close_process_by_name(process_name)
