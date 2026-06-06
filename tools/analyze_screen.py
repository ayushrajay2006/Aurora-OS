import os
from tools.registry import registry, BaseTool
from brain.llm import llm_client
from config.config import config
from config.logging import logger

@registry.register(
    name="analyze_screen",
    description="Analyzes the most recently captured screenshot to answer specific visual questions about what is on the screen.",
    args_schema={
        "query": {
            "type": "string",
            "description": "The question to answer about the screenshot (e.g. 'what is the title of the second video', 'what text is visible in the notepad window')."
        }
    },
    risk_level="low"
)
class AnalyzeScreenTool(BaseTool):
    def execute(self, query: str) -> dict:
        logger.info(f"Executing analyze_screen with query: '{query}'")
        try:
            # Resolve directory logs/
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            image_path = os.path.join(project_root, "logs", "active_screen.png")
            
            # Check if screenshot exists
            if not os.path.exists(image_path):
                # Proactively capture screenshot if it doesn't exist
                logger.info("Screenshot not found. Capturing screen first...")
                from PIL import ImageGrab
                img = ImageGrab.grab()
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                img.save(image_path, "PNG")
                
            logger.info(f"Analyzing screenshot at: {image_path}")
            
            # Construct a temporary message payload with the special <image> tag
            system_instruction = (
                "You are Aurora's visual analysis assistant. "
                "Analyze the provided screenshot carefully and answer the user's query. "
                "Be extremely precise, truthful, and concise. "
                "State only what is clearly visible. If you cannot read or find something, say so. "
                "Do NOT make up details or assume layout elements."
            )
            
            messages = [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Query: {query}\nHere is my screen capture: <image>{image_path}</image>"}
            ]
            
            # Run the inference
            # If Gemini is configured, it will use Gemini. If local is configured, it will use local llava.
            response = llm_client.chat(messages, stream=False)
            
            logger.info("Screenshot analysis completed successfully.")
            return {
                "success": True,
                "output": response,
                "analysis": response
            }
        except Exception as e:
            msg = f"Failed to analyze screenshot: {e}"
            logger.error(msg, exc_info=True)
            return {"success": False, "output": msg}
