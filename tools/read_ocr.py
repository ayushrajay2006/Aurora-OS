import os
from tools.registry import registry, BaseTool
from PIL import Image
import pytesseract
from config.logging import logger

@registry.register(
    name="read_image_text",
    description="Performs Optical Character Recognition (OCR) to extract text from a local screenshot or image file using Tesseract.",
    args_schema={
        "image_path": {
            "type": "string",
            "description": "The absolute file path of the image or screenshot to extract text from."
        }
    },
    risk_level="low"
)
class ReadImageTextTool(BaseTool):
    def execute(self, image_path: str) -> dict:
        logger.info(f"Executing read_image_text: '{image_path}'")
        try:
            if not os.path.exists(image_path):
                return {
                    "success": False,
                    "output": f"Image file not found at: '{image_path}'."
                }
                
            img = Image.open(image_path)
            
            # Perform OCR
            text = pytesseract.image_to_string(img)
            
            clean_text = text.strip()
            if not clean_text:
                return {
                    "success": True,
                    "output": "No text was detected in the specified image."
                }
                
            logger.info("OCR successfully completed.")
            return {
                "success": True,
                "output": f"Extracted OCR Text:\n{clean_text}",
                "text": clean_text
            }
            
        except (pytesseract.TesseractNotFoundError, FileNotFoundError, pytesseract.TesseractError) as e:
            msg = (
                "Local Tesseract OCR engine is not installed or configured on your system. "
                "To use local text extraction, please install Tesseract OCR from GitHub "
                "(https://github.com/UB-Mannheim/tesseract/wiki), add it to your Windows PATH, "
                "or ask Aurora to analyze your screen using cloud-based Gemini vision instead."
            )
            logger.warning(f"Tesseract OCR not found: {e}")
            return {"success": False, "output": msg}
        except Exception as e:
            msg = f"Failed to perform OCR on image: {e}"
            logger.error(msg)
            return {"success": False, "output": msg}
