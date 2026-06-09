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
        output_str = (
            f"Active Window Title: {result.get('window_title', 'Unknown')}\n"
            f"Active Process: {result.get('process_name', 'Unknown')}\n"
            f"Extracted OCR Text: {result.get('ocr_text_visible', 'None')}"
        )
        
        return {
            "success": True,
            "output": output_str
        }

tool_instance = AnalyzeScreenTool()
