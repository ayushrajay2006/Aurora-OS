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
    
    # Common system utilities & folder navigation commands
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
        "control panel": "control.exe",
        "file explorer": "explorer.exe",
        "documents": "explorer.exe shell:Personal",
        "downloads": "explorer.exe shell:Downloads",
        "this pc": "explorer.exe shell:MyComputerFolder",
        "my computer": "explorer.exe shell:MyComputerFolder"
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
    description="Opens a Windows application by name.",
    args_schema={
        "app_name": {
            "type": "string",
            "description": "Name of the application to launch (e.g., Chrome, Discord, VS Code, Notepad, Calculator)"
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
