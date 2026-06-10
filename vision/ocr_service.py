import easyocr
from config.logging import logger

class OCRService:
    def __init__(self):
        self.reader = None
        self._is_loaded = False
        
    def _lazy_load(self):
        if not self._is_loaded:
            logger.info("[Vision] Loading EasyOCR model into memory...")
            # Use GPU if available, English only for speed
            try:
                self.reader = easyocr.Reader(['en'], gpu=True, verbose=False)
            except Exception as e:
                logger.warning(f"[Vision] Failed to load EasyOCR with GPU, falling back to CPU: {e}")
                self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            self._is_loaded = True
            logger.info("[Vision] EasyOCR loaded successfully.")

    def extract_text(self, image_path: str) -> list:
        """
        Extracts text from an image path.
        Returns a list of dicts: {"text": str, "confidence": float, "box": list}
        """
        self._lazy_load()
        if not self.reader:
            return []
            
        try:
            # detail=1 returns (bbox, text, prob)
            results = self.reader.readtext(image_path, detail=1)
            parsed = []
            for (bbox, text, prob) in results:
                parsed.append({
                    "text": text,
                    "confidence": float(prob),
                    "box": [[int(coord) for coord in pt] for pt in bbox]
                })
            return parsed
        except Exception as e:
            logger.error(f"[Vision] OCR Extraction failed: {e}")
            return []

    def get_spatial_text(self, image_path: str, offset_x: int = 0, offset_y: int = 0) -> list:
        """
        Extracts text and returns a structured list with absolute spatial coordinates.
        Format: {"text": str, "x": int, "y": int, "width": int, "height": int, "confidence": float}
        """
        raw_results = self.extract_text(image_path)
        spatial_data = []
        for item in raw_results:
            box = item["box"] # [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
            x_coords = [pt[0] for pt in box]
            y_coords = [pt[1] for pt in box]
            x1, x2 = min(x_coords), max(x_coords)
            y1, y2 = min(y_coords), max(y_coords)
            
            spatial_data.append({
                "text": item["text"],
                "x": x1 + offset_x,
                "y": y1 + offset_y,
                "width": x2 - x1,
                "height": y2 - y1,
                "confidence": item["confidence"]
            })
        return spatial_data

    def get_raw_text(self, image_path: str) -> str:
        """Returns a single combined string of all extracted text."""
        self._lazy_load()
        if not self.reader:
            return ""
            
        try:
            results = self.reader.readtext(image_path, detail=0)
            return " ".join(results)
        except Exception as e:
            logger.error(f"[Vision] Raw OCR Extraction failed: {e}")
            return ""

# Global singleton
ocr_service = OCRService()
