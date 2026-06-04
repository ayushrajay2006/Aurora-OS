import os
from tools.registry import registry, BaseTool
from PIL import ImageGrab
from config.logging import logger

@registry.register(
    name="take_screenshot",
    description="Captures a screenshot of the user's primary monitor (or all monitors) and saves it to a static path, overwriting the previous screenshot to save disk space.",
    args_schema={
        "all_screens": {
            "type": "boolean",
            "description": "If true, captures a combined view of all connected monitors. If false, captures only the primary monitor. Defaults to false."
        }
    },
    risk_level="low"
)
class TakeScreenshotTool(BaseTool):
    def execute(self, all_screens: bool = False) -> dict:
        logger.info(f"Executing take_screenshot: all_screens={all_screens}")
        try:
            # Grab screenshot
            img = ImageGrab.grab(all_screens=all_screens)
            
            # Resolve directory logs/
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logs_dir = os.path.join(project_root, "logs")
            os.makedirs(logs_dir, exist_ok=True)
            
            save_path = os.path.join(logs_dir, "active_screen.png")
            
            # Save the image, overwriting the previous one
            img.save(save_path, "PNG")
            
            abs_path = os.path.abspath(save_path)
            logger.info(f"Screenshot successfully saved to: {abs_path}")
            
            return {
                "success": True,
                "output": f"Successfully captured screen and saved to '{abs_path}' (size: {img.size[0]}x{img.size[1]}).",
                "image_path": abs_path
            }
        except Exception as e:
            msg = f"Failed to capture screenshot: {e}"
            logger.error(msg)
            return {"success": False, "output": msg}
