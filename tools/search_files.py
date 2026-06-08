import os
import time
from typing import List, Dict, Any
from tools.registry import registry, BaseTool
from config.logging import logger

# Directories to ignore to prevent slow walks and permission blocks
IGNORE_DIRS = {
    "appdata", ".git", ".venv", "venv", "node_modules", 
    "__pycache__", ".idea", ".vscode", "local settings",
    "overwolf", "steamlibrary", "epicgames",
    "program files", "program files (x86)", "windows", "system32"
}

@registry.register(
    name="search_files",
    description="Locates files on the computer's key directories (Desktop, Documents, Downloads, and D: drive) matching query keywords.",
    args_schema={
        "query": {
            "type": "string",
            "description": "Keywords to search for in filenames (e.g. DBMS notes, resume, CN PDF)"
        }
    },
    risk_level="low"
)
class SearchFilesTool(BaseTool):
    def execute(self, query: str) -> dict:
        logger.info(f"FileSystem Search initiated for query: '{query}'")
        start_time = time.time()
        
        # 1. Resolve key scan directories dynamically
        user_profile = os.environ.get("USERPROFILE", "C:\\Users\\ayush")
        scan_roots = [
            os.path.join(user_profile, "Desktop"),
            os.path.join(user_profile, "Downloads"),
            os.path.join(user_profile, "Documents"),
            os.path.join(user_profile, "Pictures"),
            os.path.join(user_profile, "Videos"),
            os.path.join(user_profile, "Music"),
            "D:\\"
        ]
        
        # Normalize keywords
        keywords = [k.lower().strip() for k in query.split() if k.strip()]
        if not keywords:
            return {"success": False, "output": "Search query was empty or invalid."}
            
        logger.debug(f"Search keywords: {keywords}")
        matches = []
        
        # 2. Perform optimized search across scan roots
        for base_path in scan_roots:
            if not os.path.exists(base_path):
                continue
            
            logger.debug(f"Scanning directory: {base_path}")
            try:
                for root, dirs, files in os.walk(base_path):
                    # Filter out ignored directories to prevent walking them
                    dirs[:] = [d for d in dirs if d.lower() not in IGNORE_DIRS]
                    
                    # Restrict root drives scan depth to 3 levels to maintain high speed (under 1 sec)
                    depth = root.replace(base_path, "").count(os.sep)
                    if depth > 3:
                        dirs.clear() # Stop walking deeper
                        continue
                        
                    for file in files:
                        file_lower = file.lower()
                        # Match if ALL query keywords are present in the filename
                        if all(kw in file_lower for kw in keywords):
                            full_path = os.path.join(root, file)
                            try:
                                stats = os.stat(full_path)
                                size_kb = round(stats.st_size / 1024, 2)
                                mtime = stats.st_mtime
                                mod_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
                            except Exception:
                                size_kb = 0.0
                                mtime = 0.0
                                mod_time = "Unknown"
                                
                            matches.append({
                                "filename": file,
                                "absolute_path": full_path,
                                "size_kb": size_kb,
                                "mtime": mtime,
                                "last_modified": mod_time
                            })
                            
                            # Safeguard: Cap matches to prevent memory bloat in prompts
                            if len(matches) >= 20:
                                break
                    if len(matches) >= 20:
                        break
            except Exception as e:
                logger.warning(f"Error scanning files under {base_path}: {e}")
                
        duration = round(time.time() - start_time, 3)
        logger.info(f"FileSystem Search completed in {duration} seconds. Found {len(matches)} matches.")
        
        if not matches:
            return {
                "success": True,
                "output": f"No files found matching '{query}'. (Scanned in {duration}s)"
            }
            
        # Format output beautifully
        output_lines = [f"Found {len(matches)} matching file(s) in {duration}s:\n"]
        for idx, match in enumerate(matches, 1):
            output_lines.append(f"{idx}. {match['filename']}")
            output_lines.append(f"   Path: {match['absolute_path']}")
            output_lines.append(f"   Size: {match['size_kb']} KB | Modified: {match['last_modified']}\n")
            
        return {
            "success": True,
            "output": "\n".join(output_lines),
            "data": {"matches": matches}
        }
