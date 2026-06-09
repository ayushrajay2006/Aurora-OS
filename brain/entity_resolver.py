import os
from typing import Tuple, Dict, Any, Optional

class EntityResolver:
    def get_folder_path(self, name: str) -> Optional[str]:
        name_clean = name.strip().lower()
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
        
        for key, val in mapping.items():
            if name_clean == key or name_clean == f"{key} folder" or name_clean == f"my {key}" or name_clean == f"my {key} folder":
                return val
        return None

    def resolve_file_entity(self, query: str) -> Optional[str]:
        path_clean = query.strip('\"\'')
        if os.path.isabs(path_clean) and os.path.exists(path_clean):
            return path_clean
            
        q = query.lower().strip()
        for prefix in ["my ", "the ", "a "]:
            if q.startswith(prefix):
                q = q[len(prefix):]
                
        user_profile = os.environ.get("USERPROFILE", "C:\\Users\\ayush")
        scan_roots = [
            os.path.join(user_profile, "Desktop"),
            os.path.join(user_profile, "Downloads"),
            os.path.join(user_profile, "Documents")
        ]
        
        keywords = [k for k in q.split() if k]
        if not keywords:
            return None
            
        matches = []
        for root_dir in scan_roots:
            if not os.path.exists(root_dir):
                continue
            for root, dirs, files in os.walk(root_dir):
                depth = root.replace(root_dir, "").count(os.sep)
                if depth > 2:
                    dirs.clear()
                    continue
                for file in files:
                    if all(kw in file.lower() for kw in keywords):
                        matches.append(os.path.join(root, file))
                        if len(matches) > 10:
                            break
                if len(matches) > 10:
                    break
                    
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            try:
                matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                return matches[0]
            except Exception:
                return matches[0]
        return None

    def resolve_entities_before_execution(self, tool_name: str, args: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        resolved_args = args.copy()
        
        # Desktop context pronoun resolution hook
        from brain.desktop_context import desktop_context
        
        target_field = None
        if tool_name in ["open_app", "switch_to_app", "minimize_app", "maximize_app", "restore_app", "close_app"]:
            target_field = "app_name"
        elif tool_name == "close_process":
            target_field = "process_name"
            
        if target_field and target_field in resolved_args:
            raw_target = resolved_args[target_field]
            if raw_target:
                resolution = desktop_context.resolve_reference(raw_target)
                if resolution.get("error"):
                    # Return the exact structured clarification object requested
                    return "ask_clarification", {
                        "success": False, 
                        "requires_clarification": True, 
                        "output": resolution.get("clarification", "Ambiguous reference.")
                    }
                else:
                    resolved_args[target_field] = resolution["resolved"]
                    
        # Refresh the variable in case it was resolved
        if target_field and target_field in resolved_args:
            raw_target = resolved_args[target_field]
        
        if tool_name == "open_app":
            app_name = resolved_args.get("app_name", "").strip()
            folder_path = self.get_folder_path(app_name)
            if folder_path or os.path.isdir(app_name):
                tool_name = "open_folder"
                resolved_args = {"path": folder_path if folder_path else app_name}
            else:
                from brain.app_resolver import app_resolver
                resolved_path = app_resolver.resolve_app(app_name)
                if resolved_path:
                    # Strictly enforce routing rules:
                    # .exe -> open_app
                    # folders -> open_folder
                    # documents/images -> open_file
                    if os.path.isabs(resolved_path):
                        if os.path.isdir(resolved_path):
                            tool_name = "open_folder"
                            resolved_args = {"path": resolved_path}
                        elif os.path.isfile(resolved_path):
                            if resolved_path.lower().endswith(".exe"):
                                tool_name = "open_app"
                                resolved_args["app_name"] = resolved_path
                            else:
                                tool_name = "open_file"
                                resolved_args = {"path": resolved_path}
                        else:
                            resolved_args["app_name"] = resolved_path
                    else:
                        # Non-absolute resolved target (e.g. "code.exe", "notepad.exe", "ms-settings:")
                        # Pass it directly so open_app doesn't re-run a full resolution pass
                        # that may fail when the short name isn't on PATH.
                        resolved_args["app_name"] = resolved_path
                    
        elif tool_name == "open_folder":
            path = resolved_args.get("path", "").strip()
            folder_path = self.get_folder_path(path)
            if folder_path:
                resolved_args["path"] = folder_path

        elif tool_name == "open_file":
            path = resolved_args.get("path", "").strip()
            file_path = self.resolve_file_entity(path)
            if file_path:
                resolved_args["path"] = file_path

        elif tool_name in ["close_app", "close_process", "switch_to_app", "minimize_app", "maximize_app", "restore_app"]:
            target_name = resolved_args.get("app_name") or resolved_args.get("process_name", "")
            from brain.app_resolver import app_resolver
            resolved_path = app_resolver.resolve_app(target_name)
            if resolved_path:
                exe_name = os.path.basename(resolved_path)
                if tool_name in ["close_app", "switch_to_app", "minimize_app", "maximize_app", "restore_app"]:
                    resolved_args["app_name"] = exe_name
                else:
                    resolved_args["process_name"] = exe_name

        return tool_name, resolved_args

entity_resolver = EntityResolver()
