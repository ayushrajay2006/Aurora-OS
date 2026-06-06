import os
import time
import json
from typing import Dict, Any
from tools.registry import registry, BaseTool
from config.logging import logger
from memory.memory import memory

@registry.register(
    name="remember_screen",
    description="Captures the current screen, extracts text (OCR), and saves the context to long-term memory so it can be recalled later.",
    args_schema={
        "context_label": {
            "type": "string",
            "description": "A short, memorable label for what is on screen (e.g., 'python_import_error', 'project_dashboard')."
        },
        "description": {
            "type": "string",
            "description": "A brief explanation of why this screen is being remembered."
        }
    },
    risk_level="medium"
)
class RememberScreenTool(BaseTool):
    def execute(self, context_label: str, description: str) -> dict:
        logger.info(f"RememberScreen: Saving context '{context_label}'")
        try:
            from tools.capture_screen import capture_screen_sync
            from tools.read_ocr import extract_text_from_image_sync
            
            # 1. Capture screen
            img_path = capture_screen_sync()
            if not img_path:
                return {"success": False, "output": "Failed to capture screenshot."}
                
            # 2. Extract OCR
            ocr_text = extract_text_from_image_sync(img_path)
            if not ocr_text:
                ocr_text = "[No text found on screen]"
                
            # 3. Save to Memory
            memory_key = f"screen_context_{context_label.lower().replace(' ', '_')}"
            
            memory_data = {
                "label": context_label,
                "description": description,
                "ocr_text": ocr_text,
                "image_path": img_path,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            memory.set_fact(memory_key, json.dumps(memory_data))
            
            return {
                "success": True, 
                "output": f"Successfully remembered screen context as '{memory_key}'. You can retrieve it later using the memory_control tool."
            }
            
        except ImportError as e:
            return {"success": False, "output": f"Missing dependency for screen capture/OCR: {e}"}
        except Exception as e:
            logger.error(f"RememberScreen failed: {e}", exc_info=True)
            return {"success": False, "output": f"Failed to remember screen: {e}"}
