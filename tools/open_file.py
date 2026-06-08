import os
from tools.registry import registry, BaseTool
from config.logging import logger

@registry.register(
    name="open_file",
    description="Opens a file using its absolute path with the default Windows application.",
    args_schema={
        "path": {
            "type": "string",
            "description": "The absolute path of the file to open."
        }
    },
    risk_level="medium"
)
class OpenFileTool(BaseTool):
    def execute(self, path: str) -> dict:
        path_clean = os.path.abspath(path.strip('\"\''))
        logger.info(f"OpenFileTool executing for path: '{path_clean}'")
        
        if not os.path.exists(path_clean):
            return {"success": False, "output": f"File not found: '{path_clean}'."}
        if os.path.isdir(path_clean):
            return {"success": False, "output": f"'{path_clean}' is a directory, not a file. Use open_folder tool instead."}
            
        try:
            os.startfile(path_clean)
            return {"success": True, "output": f"Successfully opened file: '{path_clean}'."}
        except Exception as e:
            msg = f"Failed to open file '{path_clean}': {e}"
            logger.error(msg)
            return {"success": False, "output": msg}
