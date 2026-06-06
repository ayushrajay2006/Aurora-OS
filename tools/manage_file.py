import os
import shutil
import zipfile
from typing import Dict, Any
from tools.registry import registry, BaseTool
from config.logging import logger

@registry.register(
    name="manage_file",
    description="Performs advanced file and folder operations: rename, move, copy, create_folder, zip, unzip.",
    args_schema={
        "action": {
            "type": "string",
            "description": "The action to perform: 'rename', 'move', 'copy', 'create_folder', 'zip', 'unzip'.",
            "enum": ["rename", "move", "copy", "create_folder", "zip", "unzip"]
        },
        "source_path": {
            "type": "string",
            "description": "The absolute path to the source file or directory."
        },
        "destination_path": {
            "type": "string",
            "description": "The absolute path to the destination file or directory. For 'create_folder', this is the path to create. For 'rename', this is the new name or new absolute path. For 'zip', this is the output .zip file path."
        }
    },
    risk_level="high"
)
class ManageFileTool(BaseTool):
    def execute(self, action: str, source_path: str, destination_path: str) -> dict:
        action = action.lower().strip()
        logger.info(f"ManageFile: '{action}' on '{source_path}' -> '{destination_path}'")
        
        try:
            if action == "create_folder":
                os.makedirs(destination_path, exist_ok=True)
                return {"success": True, "output": f"Successfully created folder: {destination_path}"}
                
            if not os.path.exists(source_path):
                return {"success": False, "output": f"Source path does not exist: {source_path}"}
                
            if action == "rename":
                # If destination is just a name, construct full path
                if not os.path.isabs(destination_path):
                    destination_path = os.path.join(os.path.dirname(source_path), destination_path)
                os.rename(source_path, destination_path)
                return {"success": True, "output": f"Successfully renamed to: {destination_path}"}
                
            elif action == "move":
                shutil.move(source_path, destination_path)
                return {"success": True, "output": f"Successfully moved to: {destination_path}"}
                
            elif action == "copy":
                if os.path.isdir(source_path):
                    shutil.copytree(source_path, destination_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(source_path, destination_path)
                return {"success": True, "output": f"Successfully copied to: {destination_path}"}
                
            elif action == "zip":
                if not destination_path.endswith('.zip'):
                    destination_path += '.zip'
                with zipfile.ZipFile(destination_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    if os.path.isdir(source_path):
                        for root, _, files in os.walk(source_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                zipf.write(file_path, os.path.relpath(file_path, source_path))
                    else:
                        zipf.write(source_path, os.path.basename(source_path))
                return {"success": True, "output": f"Successfully zipped to: {destination_path}"}
                
            elif action == "unzip":
                if not source_path.endswith('.zip'):
                    return {"success": False, "output": "Source must be a .zip file."}
                os.makedirs(destination_path, exist_ok=True)
                with zipfile.ZipFile(source_path, 'r') as zipf:
                    zipf.extractall(destination_path)
                return {"success": True, "output": f"Successfully unzipped to: {destination_path}"}
                
            else:
                return {"success": False, "output": f"Unknown action: {action}"}
                
        except Exception as e:
            logger.error(f"ManageFile failed: {e}")
            return {"success": False, "output": f"Failed to execute {action}: {e}"}
