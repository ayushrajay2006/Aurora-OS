import os
import shutil
from tools.registry import registry, BaseTool
from config.logging import logger

@registry.register(
    name="delete_file",
    description="Deletes a file or folder at the specified absolute path.",
    args_schema={
        "path": {
            "type": "string",
            "description": "Absolute path to the file or directory/folder to delete."
        }
    },
    risk_level="high"
)
class DeleteFileTool(BaseTool):
    def execute(self, path: str) -> dict:
        logger.info(f"Received request to delete path: '{path}'")
        
        target_path = os.path.abspath(path.strip())
        
        if not os.path.exists(target_path):
            msg = f"Path '{target_path}' does not exist."
            logger.error(msg)
            return {"success": False, "output": msg}
            
        try:
            if os.path.isdir(target_path):
                # Delete folder recursively
                shutil.rmtree(target_path)
                msg = f"Successfully deleted directory and all its contents: '{target_path}'"
            else:
                # Delete file
                os.remove(target_path)
                msg = f"Successfully deleted file: '{target_path}'"
                
            logger.info(msg)
            return {"success": True, "output": msg}
        except Exception as e:
            msg = f"Failed to delete '{target_path}': {e}"
            logger.error(msg)
            return {"success": False, "output": msg}
