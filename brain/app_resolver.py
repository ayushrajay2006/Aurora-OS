import os
import json
import winreg
import subprocess
import re
from typing import Optional, Dict, Any, List
from config.logging import logger

try:
    from rapidfuzz import fuzz, process
    HAS_RAPIDFUZZ = True
except ImportError:
    import difflib
    HAS_RAPIDFUZZ = False

CACHE_FILE = os.path.join("data", "app_cache.json")

class AppResolver:
    def __init__(self):
        self.cache: Dict[str, str] = {}
        self.load_cache()

    def load_cache(self):
        os.makedirs("data", exist_ok=True)
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception:
                self.cache = {}

    def save_cache(self):
        os.makedirs("data", exist_ok=True)
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=4)
        except Exception:
            pass

    def add_to_cache(self, query: str, path: str):
        self.cache[query.strip().lower()] = path
        self.save_cache()

    def resolve_lnk_powershell(self, lnk_path: str) -> Optional[str]:
        try:
            cmd = f"(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk_path}').TargetPath"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=2, check=False)
            if res.returncode == 0:
                target = res.stdout.strip()
                if target and os.path.exists(target) and target.lower().endswith(".exe"):
                    return target
        except Exception:
            pass
        return None

    def scan_start_menu(self) -> Dict[str, str]:
        shortcuts = {}
        paths = [
            os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), "Microsoft\\Windows\\Start Menu\\Programs"),
            os.path.join(os.environ.get("AppData", ""), "Microsoft\\Windows\\Start Menu\\Programs")
        ]
        for base_path in paths:
            if not os.path.exists(base_path):
                continue
            for root, _, files in os.walk(base_path):
                for file in files:
                    if file.lower().endswith(".lnk"):
                        name_clean = file[:-4].lower().strip()
                        lnk_path = os.path.join(root, file)
                        shortcuts[name_clean] = lnk_path
        return shortcuts

    def scan_registry_app_paths(self) -> Dict[str, str]:
        app_paths = {}
        sub_key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        for hkey in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            try:
                with winreg.OpenKey(hkey, sub_key_path) as key:
                    info = winreg.QueryInfoKey(key)
                    for i in range(info[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                try:
                                    path, _ = winreg.QueryValue(subkey, "")
                                    path_clean = path.strip('\"\'')
                                    if os.path.exists(path_clean) and path_clean.lower().endswith(".exe"):
                                        app_paths[subkey_name.lower().replace(".exe", "")] = path_clean
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass
        return app_paths

    def scan_registry_uninstall(self) -> Dict[str, str]:
        apps = {}
        sub_key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        for hkey in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for sam in [winreg.KEY_READ, winreg.KEY_READ | winreg.KEY_WOW64_32KEY, winreg.KEY_READ | winreg.KEY_WOW64_64KEY]:
                try:
                    with winreg.OpenKeyEx(hkey, sub_key_path, 0, sam) as key:
                        info = winreg.QueryInfoKey(key)
                        for i in range(info[0]):
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                with winreg.OpenKeyEx(key, subkey_name, 0, sam) as subkey:
                                    try:
                                        display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                        try:
                                            display_icon, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                                            icon_path = display_icon.split(",")[0].strip('\"\'')
                                            
                                            # Avoid picking uninstallers as the main app
                                            exe_name_lower = os.path.basename(icon_path).lower()
                                            if os.path.exists(icon_path) and icon_path.lower().endswith(".exe"):
                                                if not any(x in exe_name_lower for x in ["uninstall", "unins", "setup", "helper"]):
                                                    apps[display_name.lower().strip()] = icon_path
                                                    continue
                                        except Exception:
                                            pass
                                        
                                        install_loc, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                                        install_loc_clean = install_loc.strip('\"\'')
                                        if install_loc_clean and os.path.exists(install_loc_clean):
                                            main_exe = self.find_main_exe(install_loc_clean, display_name)
                                            if main_exe:
                                                apps[display_name.lower().strip()] = main_exe
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                except Exception:
                    pass
        return apps

    def find_main_exe(self, folder_path: str, app_name: str) -> Optional[str]:
        exes = []
        for root, dirs, files in os.walk(folder_path):
            depth = root.replace(folder_path, "").count(os.sep)
            if depth > 2:
                dirs.clear()
                continue
            for file in files:
                if file.lower().endswith(".exe"):
                    file_lower = file.lower()
                    if any(x in file_lower for x in ["unitycrashhandler", "crashreporter", "unins", "setup", "register", "launcher", "helper", "config", "tool"]):
                        continue
                    exes.append(os.path.join(root, file))
        if not exes:
            return None
        
        clean_app = app_name.lower().replace(" ", "").replace("_", "").replace("-", "")
        for exe in exes:
            exe_name = os.path.basename(exe).lower().replace(".exe", "").replace(" ", "").replace("_", "").replace("-", "")
            if exe_name == clean_app or exe_name in clean_app or clean_app in exe_name:
                return exe
        return None

    def scan_steam_games(self) -> Dict[str, str]:
        games = {}
        steam_path = None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                path, _ = winreg.QueryValueEx(key, "SteamPath")
                if path and os.path.exists(path):
                    steam_path = os.path.normpath(path)
        except Exception:
            pass
            
        if not steam_path:
            for p in [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam", r"D:\Steam"]:
                if os.path.exists(p):
                    steam_path = p
                    break
                    
        if not steam_path:
            return games
            
        lib_folders = [os.path.join(steam_path, "steamapps")]
        vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf_path):
            try:
                with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                paths = re.findall(r'"path"\s+"([^"]+)"', content)
                for p in paths:
                    p_norm = os.path.normpath(p.replace("\\\\", "\\"))
                    apps_path = os.path.join(p_norm, "steamapps")
                    if os.path.exists(apps_path) and apps_path not in lib_folders:
                        lib_folders.append(apps_path)
            except Exception:
                pass
                
        for folder in lib_folders:
            if not os.path.exists(folder):
                continue
            for file in os.listdir(folder):
                if file.startswith("appmanifest_") and file.endswith(".acf"):
                    acf_path = os.path.join(folder, file)
                    try:
                        with open(acf_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        name_match = re.search(r'"name"\s+"([^"]+)"', content)
                        dir_match = re.search(r'"installdir"\s+"([^"]+)"', content)
                        if name_match and dir_match:
                            game_name = name_match.group(1)
                            install_dir = dir_match.group(1)
                            common_path = os.path.join(folder, "common", install_dir)
                            if os.path.exists(common_path):
                                main_exe = self.find_main_exe(common_path, game_name)
                                if main_exe:
                                    games[game_name.lower().strip()] = main_exe
                    except Exception:
                        pass
        return games

    def scan_epic_games(self) -> Dict[str, str]:
        games = {}
        manifest_dir = r"C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests"
        if os.path.exists(manifest_dir):
            try:
                for file in os.listdir(manifest_dir):
                    if file.endswith(".item"):
                        path = os.path.join(manifest_dir, file)
                        try:
                            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                                data = json.load(f)
                            display_name = data.get("DisplayName")
                            install_location = data.get("InstallLocation")
                            launch_executable = data.get("LaunchExecutable")
                            if display_name and install_location and launch_executable:
                                exe_path = os.path.join(install_location, launch_executable)
                                if os.path.exists(exe_path):
                                    games[display_name.lower().strip()] = exe_path
                        except Exception:
                            pass
            except Exception:
                pass
        return games

    def resolve_app(self, app_name: str) -> Optional[str]:
        query = app_name.strip().lower()
        if not query:
            return None
            
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
            "control panel": "control.exe",
            "controlpanel": "control.exe",
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
            "visual studio code": "code.exe"
        }

        # Layer 1: Persistent Cache
        if query in self.cache:
            cached_path = self.cache[query]
            if os.path.exists(cached_path) or not os.path.isabs(cached_path):
                logger.info(f"AppResolver: Resolved '{app_name}' from Persistent Cache -> {cached_path}")
                return cached_path

        # Check system utilities directly first (if they don't need absolute paths)
        if query in system_utilities:
            # Add to cache and return
            self.add_to_cache(query, system_utilities[query])
            logger.info(f"AppResolver: Resolved '{app_name}' from System Utilities -> {system_utilities[query]}")
            return system_utilities[query]

        # Layer 2: Start Menu Shortcuts
        start_menu_shortcuts = self.scan_start_menu()
        if query in start_menu_shortcuts:
            resolved = self.resolve_lnk_powershell(start_menu_shortcuts[query])
            if resolved:
                self.add_to_cache(query, resolved)
                logger.info(f"AppResolver: Resolved '{app_name}' from Start Menu -> {resolved}")
                return resolved

        # Layer 3: Registry App Paths
        registry_paths = self.scan_registry_app_paths()
        if query in registry_paths:
            path = registry_paths[query]
            self.add_to_cache(query, path)
            logger.info(f"AppResolver: Resolved '{app_name}' from Registry App Paths -> {path}")
            return path

        # Layer 4: Registry Installed Applications
        installed_apps = self.scan_registry_uninstall()
        if query in installed_apps:
            path = installed_apps[query]
            self.add_to_cache(query, path)
            logger.info(f"AppResolver: Resolved '{app_name}' from Registry Uninstall -> {path}")
            return path

        # Layer 5: Steam Libraries
        steam_games = self.scan_steam_games()
        if query in steam_games:
            path = steam_games[query]
            self.add_to_cache(query, path)
            logger.info(f"AppResolver: Resolved '{app_name}' from Steam -> {path}")
            return path

        # Layer 6: Epic Games manifests
        epic_games = self.scan_epic_games()
        if query in epic_games:
            path = epic_games[query]
            self.add_to_cache(query, path)
            logger.info(f"AppResolver: Resolved '{app_name}' from Epic Games -> {path}")
            return path

        # Common hardcoded install locations for popular apps
        common_installations = {
            "chrome": [
                "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
            ],
            "discord": [
                os.path.join(os.environ.get("LocalAppData", ""), "Discord\\Update.exe")
            ],
            "vscode": [
                os.path.join(os.environ.get("LocalAppData", ""), "Programs\\Microsoft VS Code\\Code.exe"),
                "C:\\Program Files\\Microsoft VS Code\\Code.exe"
            ]
        }
        if query in common_installations:
            for path in common_installations[query]:
                if os.path.exists(path):
                    self.add_to_cache(query, path)
                    logger.info(f"AppResolver: Resolved '{app_name}' from Common Installations -> {path}")
                    return path

        # Layer 7: Fuzzy / Substring Matching
        choices_map = {}
        for d in [system_utilities, registry_paths, start_menu_shortcuts, installed_apps, steam_games, epic_games]:
            for k, v in d.items():
                choices_map[k] = v

        choices = list(choices_map.keys())
        match_key = self.fuzzy_match_choices(query, choices)
        
        selected_result = None
        resolution_source = None
        
        if match_key:
            target = choices_map[match_key]
            if target.lower().endswith(".lnk"):
                resolved = self.resolve_lnk_powershell(target)
                if resolved:
                    self.add_to_cache(query, resolved)
                    selected_result = resolved
                    resolution_source = "Fuzzy Match (Shortcut)"
            else:
                self.add_to_cache(query, target)
                selected_result = target
                resolution_source = "Fuzzy Match (Executable)"

        # Add the required logging block
        if selected_result:
            logger.info(f"[Resolver]\nQuery: {query}\nCandidates: {len(choices)}\nSelected result: {selected_result}\nResolution source: {resolution_source}")
            return selected_result
            
        logger.warning(f"[Resolver]\nQuery: {query}\nCandidates: {len(choices)}\nSelected result: None\nResolution source: Failed")
        return None

    def fuzzy_match_choices(self, query: str, choices: List[str], threshold: float = 85.0) -> Optional[str]:
        if not choices:
            return None
        query_clean = query.lower().strip()
        
        for choice in choices:
            if query_clean == choice.lower():
                logger.info(f"AppResolver: Exact choice match found for '{query}': '{choice}'")
                return choice
        for choice in choices:
            if query_clean in choice.lower() or choice.lower() in query_clean:
                logger.info(f"AppResolver: Substring match found for '{query}': '{choice}'")
                return choice

        if HAS_RAPIDFUZZ:
            match = process.extractOne(query_clean, choices, scorer=fuzz.WRatio)
            if match:
                logger.info(f"AppResolver: Fuzzy match for '{query}' -> '{match[0]}' (Score: {match[1]:.1f})")
                if match[1] >= threshold:
                    return match[0]
                else:
                    logger.warning(f"AppResolver: Match rejected (below threshold {threshold})")
        else:
            choices_lower = [c.lower() for c in choices]
            matches = difflib.get_close_matches(query_clean, choices_lower, n=1, cutoff=threshold/100.0)
            if matches:
                idx = choices_lower.index(matches[0])
                logger.info(f"AppResolver: Difflib fuzzy match for '{query}' -> '{choices[idx]}'")
                return choices[idx]
        return None

app_resolver = AppResolver()
