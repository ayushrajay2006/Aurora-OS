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
CUSTOM_GAME_DIRS = [
    r"D:\Reality Escape",
]

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
        
        self.start_apps_cache = {}

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

    def _is_app_id(self, value: str) -> bool:
        return "!" in value or value.startswith("shell:AppsFolder\\") or value.startswith("Microsoft.") or value.startswith("com.")

    def _is_launchable_executable(self, value: str) -> bool:
        if not value:
            return False
        if os.path.isabs(value):
            return os.path.exists(value) and value.lower().endswith((".exe", ".msc"))
        return value.lower().endswith((".exe", ".msc"))

    def _is_preferred_target(self, value: str) -> bool:
        if not value:
            return False
        if os.path.isabs(value) and os.path.exists(value):
            return True
        if value.lower().endswith(".exe"):
            return True
        if value.startswith("steam://"):
            return False
        if "!" in value:
            return False
        return False

    def _merge_choices(self, choices_map: Dict[str, str], incoming: Dict[str, str]):
        for key, value in incoming.items():
            current = choices_map.get(key)
            if current is None:
                choices_map[key] = value
                continue
            if self._is_preferred_target(value) and not self._is_preferred_target(current):
                choices_map[key] = value

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
                    # Skip unambiguous non-game executables only
                    if any(x in file_lower for x in [
                        "unitycrashhandler", "crashreporter", "unins000",
                        "_setup", "redist", "vcredist", "dxwebsetup",
                        "dxsetup", "dotnetfx", "oalinst",
                        "quicksfv", "crs-", "crs_"
                    ]):
                        continue
                    exes.append(os.path.join(root, file))

        if not exes:
            return None

        # 1. Try exact/substring name match first
        clean_app = app_name.lower().replace(" ", "").replace("_", "").replace("-", "")
        for exe in exes:
            exe_name = os.path.basename(exe).lower().replace(".exe", "").replace(" ", "").replace("_", "").replace("-", "")
            if exe_name == clean_app or exe_name in clean_app or clean_app in exe_name:
                return exe

        # 2. If no name match, pick the largest exe (most likely the game binary)
        try:
            exes_with_size = [(e, os.path.getsize(e)) for e in exes]
            exes_with_size.sort(key=lambda x: x[1], reverse=True)
            largest = exes_with_size[0][0]
            logger.info(f"AppResolver: find_main_exe fallback to largest exe: {largest} ({exes_with_size[0][1] // 1024} KB)")
            return largest
        except Exception:
            return exes[0] if exes else None

    
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
            logger.warning("AppResolver: Steam not found in registry or common install paths.")
            return games
            
        lib_folders = [os.path.join(steam_path, "steamapps")]
        vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
        logger.info(f"AppResolver: Steam Base Path: {steam_path}")
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
            except Exception as e:
                logger.warning(f"AppResolver: Error parsing libraryfolders.vdf: {e}")
                
        logger.info(f"AppResolver: Found Steam Library Folders: {lib_folders}")

        for folder in lib_folders:
            if not os.path.exists(folder):
                continue
            manifests_found = 0
            discovered_here = 0
            for file in os.listdir(folder):
                if file.startswith("appmanifest_") and file.endswith(".acf"):
                    manifests_found += 1
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
                                    logger.info(f"AppResolver: Discovered Steam Game: '{game_name}' -> {main_exe}")
                                    games[game_name.lower().strip()] = main_exe
                                    discovered_here += 1
                                else:
                                    logger.info(f"AppResolver: No launchable exe matched for Steam game '{game_name}' in '{common_path}'")
                            else:
                                logger.info(f"AppResolver: Steam common path missing for '{game_name}': {common_path}")
                    except Exception as e:
                        logger.warning(f"AppResolver: Failed to parse {file}: {e}")
            logger.info(f"AppResolver: Scanned {manifests_found} manifests in {folder}; discovered {discovered_here} games")
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

    def scan_start_apps(self) -> Dict[str, str]:
        if self.start_apps_cache:
            return self.start_apps_cache
            
        apps = {}
        try:
            res = subprocess.run(['powershell', '-NoProfile', '-Command', 'Get-StartApps | Select-Object -Property Name, AppID | ConvertTo-Json'], capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                if isinstance(data, list):
                    for item in data:
                        name = item.get("Name")
                        app_id = item.get("AppID")
                        if name and app_id:
                            apps[name.lower().strip()] = app_id
                elif isinstance(data, dict):
                    name = data.get("Name")
                    app_id = data.get("AppID")
                    if name and app_id:
                        apps[name.lower().strip()] = app_id
        except Exception as e:
            logger.warning(f"Failed to scan Get-StartApps: {e}")
            
        self.start_apps_cache = apps
        return apps
        
    def scan_custom_game_dirs(self) -> Dict[str, str]:
        """Scans CUSTOM_GAME_DIRS for game folders and their main executables."""
        games = {}
        for root_dir in CUSTOM_GAME_DIRS:
            if not os.path.exists(root_dir):
                logger.warning(f"AppResolver: Custom game dir not found: {root_dir}")
                continue
            logger.info(f"AppResolver: Scanning custom game dir: {root_dir}")
            try:
                for item in os.listdir(root_dir):
                    full_path = os.path.join(root_dir, item)
                    if not os.path.isdir(full_path):
                        continue
                    main_exe = self.find_main_exe(full_path, item)
                    if main_exe:
                        logger.info(f"AppResolver: Custom game found: '{item}' -> {main_exe}")
                        games[item.lower().strip()] = main_exe
                    else:
                        logger.warning(f"AppResolver: No main exe found for custom game dir: '{item}' in {root_dir}")
            except Exception as e:
                logger.warning(f"AppResolver: Error scanning custom game dir {root_dir}: {e}")
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
            "visual studio code": "code.exe",
            "settings": "ms-settings:",
            "windows settings": "ms-settings:",
            "services": "services.msc",
            "event viewer": "eventvwr.msc",
            "resource monitor": "resmon.exe",
            "performance monitor": "perfmon.exe",
            "system information": "msinfo32.exe",
            "character map": "charmap.exe",
            "magnifier": "magnify.exe",
            "on screen keyboard": "osk.exe",
            "remote desktop": "mstsc.exe",
            "task scheduler": "taskschd.msc",
            "computer management": "compmgmt.msc",
            "local security policy": "secpol.msc",
            "group policy": "gpedit.msc",
        }

        logger.info(f"AppResolver: [QUERY] '{query}'")

        # Layer 1: Persistent Cache
        if query in self.cache:
            cached_path = self.cache[query]
            if self._is_preferred_target(cached_path) or self._is_app_id(cached_path):
                logger.info(f"AppResolver: [CACHE HIT] Resolved '{app_name}' -> {cached_path}")
                if self._is_preferred_target(cached_path):
                    return cached_path
                logger.info(f"AppResolver: Cache hit is AppID-style target for '{app_name}', continuing search for executable preference.")

        logger.info(f"AppResolver: [CACHE MISS] '{app_name}' not in cache. Commencing discovery.")

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

        # Layer 6.5: Custom Game Directories (e.g. D:\Reality Escape)
        custom_games = self.scan_custom_game_dirs()
        if query in custom_games:
            path = custom_games[query]
            self.add_to_cache(query, path)
            logger.info(f"AppResolver: Resolved '{app_name}' from Custom Game Dirs -> {path}")
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
            "vs code": [
                os.path.join(os.environ.get("LocalAppData", ""), "Programs\\Microsoft VS Code\\Code.exe"),
                "C:\\Program Files\\Microsoft VS Code\\Code.exe"
            ],
            "vscode": [
                os.path.join(os.environ.get("LocalAppData", ""), "Programs\\Microsoft VS Code\\Code.exe"),
                "C:\\Program Files\\Microsoft VS Code\\Code.exe"
            ],
            "visual studio code": [
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
        start_apps = self.scan_start_apps()
        custom_games = self.scan_custom_game_dirs()
        for d in [start_apps, system_utilities, registry_paths, start_menu_shortcuts, installed_apps, steam_games, epic_games, custom_games]:
            self._merge_choices(choices_map, d)

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

        if query in self.cache and self._is_app_id(self.cache[query]):
            fallback = self.cache[query]
            logger.info(f"AppResolver: Falling back to cached AppID target for '{app_name}' -> {fallback}")
            return fallback
            
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
            logger.info(f"AppResolver: Running fuzzy matching for '{query}'...")
            results = process.extract(query_clean, choices, scorer=fuzz.WRatio, limit=5)
            
            logger.info("AppResolver: Top candidates:")
            for match_str, score, _ in results:
                logger.info(f" - {match_str} (Score: {score:.1f})")
                
            best_match = results[0] if results else None
            if best_match:
                if best_match[1] >= threshold:
                    logger.info(f"AppResolver: Selected '{best_match[0]}' (Score: {best_match[1]:.1f})")
                    return best_match[0]
                else:
                    logger.warning(f"AppResolver: All candidates rejected (Highest score {best_match[1]:.1f} below threshold {threshold})")
        else:
            choices_lower = [c.lower() for c in choices]
            matches = difflib.get_close_matches(query_clean, choices_lower, n=1, cutoff=threshold/100.0)
            if matches:
                idx = choices_lower.index(matches[0])
                logger.info(f"AppResolver: Difflib fuzzy match for '{query}' -> '{choices[idx]}'")
                return choices[idx]
        return None

app_resolver = AppResolver()
