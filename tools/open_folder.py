import os
from tools.registry import registry, BaseTool
from config.logging import logger

@registry.register(
    name="open_folder",
    description="Opens a Windows folder/directory using Windows Explorer.",
    args_schema={
        "path": {
            "type": "string",
            "description": "The absolute path or name of the folder to open (e.g. downloads, documents, desktop, pictures, videos, music or a direct path)."
        }
    },
    risk_level="medium"
)
class OpenFolderTool(BaseTool):
    def execute(self, path: str) -> dict:
        path_clean = path.strip('\"\'')
        logger.info(f"OpenFolderTool executing for path/alias: '{path_clean}'")
        
        resolved_path = path_clean
        user_profile = os.environ.get("USERPROFILE", "C:\\Users\\ayush")
        mapping = {
            "downloads": os.path.join(user_profile, "Downloads"),
            "documents": os.path.join(user_profile, "Documents"),
            "desktop": os.path.join(user_profile, "Desktop"),
            "pictures": os.path.join(user_profile, "Pictures"),
            "videos": os.path.join(user_profile, "Videos"),
            "music": os.path.join(user_profile, "Music"),
            "screenshots": os.path.join(user_profile, "Pictures", "Screenshots")
        }
        
        resolved_path = ""
        path_lower = path_clean.lower()
        
        # 0. Check if it's already an absolute path
        if os.path.isabs(path_clean) and os.path.exists(path_clean) and os.path.isdir(path_clean):
            resolved_path = os.path.abspath(path_clean)
            logger.info(f"Absolute path provided and exists. Skipping discovery. Selected:\n{resolved_path}")
            return {"success": True, "output": f"Successfully opened folder: '{resolved_path}'"}
            
        base_name = path_lower[:-7].strip() if path_lower.endswith(" folder") else path_lower
        
        if base_name in mapping:
            resolved_path = mapping[base_name]
        else:
            # 2. Advanced Folder Discovery with Exact Ranking
            logger.info(f"Alias not found. Commencing discovery for folder: '{path_clean}'")
            scan_roots = [
                os.path.join(user_profile, "Downloads"),
                os.path.join(user_profile, "Documents"),
                os.path.join(user_profile, "Desktop")
            ]
            
            # Check for OneDrive
            onedrive_path = os.path.join(user_profile, "OneDrive")
            if os.path.exists(onedrive_path):
                scan_roots.append(onedrive_path)
                
            from rapidfuzz import fuzz
            
            logger.info(f"[FolderResolver]\nQuery: {path_clean}")
            candidates = []
            
            query_words = [w for w in base_name.split() if w]
            base_name_exact = path_clean[:-7].strip() if path_lower.endswith(" folder") else path_clean
            
            for root_dir in scan_roots:
                if not os.path.exists(root_dir):
                    continue
                try:
                    for root, dirs, files in os.walk(root_dir):
                        depth = root.replace(root_dir, "").count(os.sep)
                        if depth > 2:
                            dirs.clear()
                            continue
                        for d in dirs:
                            d_lower = d.lower()
                            score = 0
                            
                            # Exact folder name: 100
                            if d == base_name_exact:
                                score = 100
                            # Case-insensitive exact: 95
                            elif d_lower == base_name:
                                score = 95
                            # Contains all query words: 80
                            elif all(w in d_lower for w in query_words):
                                score = 80
                            # Contains some query words: 60
                            elif any(w in d_lower for w in query_words):
                                score = 60
                            else:
                                # Fuzzy match: 40
                                f_score = fuzz.WRatio(base_name, d_lower)
                                if f_score > 80.0:
                                    score = 40
                                    
                            if score > 0:
                                full_path = os.path.join(root, d)
                                candidates.append((full_path, score))
                                if len(candidates) > 100:
                                    break
                        if len(candidates) > 100:
                            break
                except Exception:
                    pass
                    
            if candidates:
                # Deduplicate by path, keeping highest score
                best_scores = {}
                for c_path, c_score in candidates:
                    if c_path not in best_scores or c_score > best_scores[c_path]:
                        best_scores[c_path] = c_score
                
                candidates = [(k, v) for k, v in best_scores.items()]
                candidates.sort(key=lambda x: x[1], reverse=True)
                
                logger.info("Candidates:\n" + "\n".join([f"{c[0]} (Score: {c[1]})" for c in candidates[:10]]))
                
                top_score = candidates[0][1]
                runner_up = candidates[1][1] if len(candidates) > 1 else 0
                
                # Auto-open logic
                if top_score >= 90 or (top_score >= 80 and runner_up <= 50):
                    resolved_path = candidates[0][0]
                else:
                    logger.info("Ambiguous results. Presenting choices.")
                    msg = "Found multiple matching folders. Please specify which one you meant:\n"
                    for idx, (upath, uscore) in enumerate(candidates[:5], 1):
                        msg += f"{idx}. {upath} (Score: {uscore})\n"
                    return {"success": False, "output": msg}
            
        resolved_path = os.path.abspath(resolved_path)
        logger.info(f"Selected:\n{resolved_path}")
        logger.info(f"Exists: {os.path.exists(resolved_path)}")
        
        if not os.path.exists(resolved_path):
            return {"success": False, "output": f"Folder not found: '{resolved_path}'."}
        if not os.path.isdir(resolved_path):
            return {"success": False, "output": f"'{resolved_path}' is a file, not a folder. Use open_file tool instead."}
            
        try:
            os.startfile(resolved_path)
            return {"success": True, "output": f"Successfully opened folder: '{resolved_path}'."}
        except Exception as e:
            msg = f"Failed to open folder '{resolved_path}': {e}"
            logger.error(msg)
            return {"success": False, "output": msg}
