import json
from tools.registry import registry, BaseTool
from vision.window_classifier import window_classifier

@registry.register(
    name="analyze_screen",
    description="Analyzes the user's screen using active window metadata and OCR. Use this whenever the user asks 'what is on my screen', 'read this popup', or 'what application is open'.",
    args_schema={},
    risk_level="low"
)
class AnalyzeScreenTool(BaseTool):

    def execute(self, **kwargs) -> dict:
        result = window_classifier.analyze_current_screen()
        
        # Build a structured response for the LLM to ingest
        return {
            "success": True,
            "output": {
                "window_title": result["window_title"],
                "process_name": result["process_name"],
                "ocr_text_visible": result["ocr_text_visible"],
                "spatial_data": result.get("spatial_data", []),
                "screenshot_path": result["screenshot_path"]
            }
        }

tool_instance = AnalyzeScreenTool()
