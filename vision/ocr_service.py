import easyocr
from config.logging import logger
import time
import cv2
import asyncio

USE_WINSDK_OCR = True

class OCRService:
    def __init__(self):
        self.reader = None
        self._is_loaded = False
        self._win_engine = None
        
    def _lazy_load(self):
        if USE_WINSDK_OCR:
            if not self._is_loaded:
                try:
                    import winsdk.windows.media.ocr as ocr
                    import winsdk.windows.globalization as globalization
                    lang = globalization.Language("en-US")
                    self._win_engine = ocr.OcrEngine.try_create_from_language(lang)
                    self._is_loaded = True
                    logger.info("[Vision] WinSDK OCR loaded successfully.")
                except Exception as e:
                    logger.error(f"[Vision] Failed to load WinSDK OCR: {e}")
            return

        if not self._is_loaded:
            logger.info("[Vision] Loading EasyOCR model into memory...")
            try:
                self.reader = easyocr.Reader(['en'], gpu=True, verbose=False)
            except Exception as e:
                logger.warning(f"[Vision] Failed to load EasyOCR with GPU, falling back to CPU: {e}")
                self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            self._is_loaded = True
            logger.info("[Vision] EasyOCR loaded successfully.")

    async def _winsdk_recognize(self, image_path: str):
        from winsdk.windows.storage import StorageFile
        from winsdk.windows.graphics.imaging import BitmapDecoder
        import os
        
        abs_path = os.path.abspath(image_path)
        file = await StorageFile.get_file_from_path_async(abs_path)
        stream = await file.open_async(0)
        decoder = await BitmapDecoder.create_async(stream)
        software_bitmap = await decoder.get_software_bitmap_async()
        
        result = await self._win_engine.recognize_async(software_bitmap)
        return result

    def extract_text(self, image_path: str, crop_region=None) -> dict:
        """
        Extracts text from an image path.
        Returns a dict: {"parsed": [...], "inference_time": float, "preprocessing_time": float}
        """
        self._lazy_load()
        
        if USE_WINSDK_OCR and self._win_engine:
            try:
                t0 = time.time()
                # Run async WinSDK inference
                result = asyncio.run(self._winsdk_recognize(image_path))
                t1 = time.time()
                
                parsed = []
                if result and result.lines:
                    for i in range(result.lines.size):
                        line = result.lines[i]
                        words = line.words
                        if words.size == 0:
                            continue
                            
                        x_coords = [words[j].bounding_rect.x for j in range(words.size)]
                        y_coords = [words[j].bounding_rect.y for j in range(words.size)]
                        r_coords = [words[j].bounding_rect.x + words[j].bounding_rect.width for j in range(words.size)]
                        b_coords = [words[j].bounding_rect.y + words[j].bounding_rect.height for j in range(words.size)]
                        
                        x = int(min(x_coords))
                        y = int(min(y_coords))
                        w = int(max(r_coords) - x)
                        h = int(max(b_coords) - y)
                        
                        box = [[x, y], [x+w, y], [x+w, y+h], [x, y+h]]
                        
                        # WinSDK returns bounding boxes on the full image.
                        # If a crop_region is specified, we must filter out boxes not in the crop region,
                        # and then we must subtract the crop_region offset so that get_spatial_text
                        # doesn't mistakenly double-add the offset!
                        if crop_region:
                            l, t, r, b = crop_region
                            center_x = x + w/2
                            center_y = y + h/2
                            if not (l <= center_x <= r and t <= center_y <= b):
                                continue
                            # Offset back to cropped-relative to match EasyOCR schema
                            box = [[bx - l, by - t] for bx, by in box]

                        parsed.append({
                            "text": line.text,
                            "confidence": 1.0,
                            "box": box
                        })
                
                t2 = time.time()
                return {
                    "parsed": parsed,
                    "preprocessing_time": (t1 - t0) * 1000.0,
                    "inference_time": (t2 - t1) * 1000.0
                }
            except Exception as e:
                logger.error(f"[Vision] WinSDK Extraction failed: {e}")
                return {"parsed": [], "inference_time": 0.0, "preprocessing_time": 0.0}

        # --- FALLBACK EASYOCR ---
        if not self.reader:
            return {"parsed": [], "inference_time": 0.0, "preprocessing_time": 0.0}
            
        try:
            t0 = time.time()
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError(f"Failed to load image {image_path}")
                
            if crop_region:
                l, t, r, b = crop_region
                h, w = img.shape[:2]
                l, r = max(0, l), min(w, r)
                t, b = max(0, t), min(h, b)
                img = img[t:b, l:r]
                
            t1 = time.time()
            
            # detail=1 returns (bbox, text, prob)
            results = self.reader.readtext(img, detail=1)
            t2 = time.time()
            
            parsed = []
            for (bbox, text, prob) in results:
                offset_box = []
                for pt in bbox:
                    cx = int(pt[0]) + (crop_region[0] if crop_region else 0)
                    cy = int(pt[1]) + (crop_region[1] if crop_region else 0)
                    offset_box.append([cx, cy])
                    
                parsed.append({
                    "text": text,
                    "confidence": float(prob),
                    "box": offset_box
                })
            
            return {
                "parsed": parsed,
                "preprocessing_time": (t1 - t0) * 1000.0,
                "inference_time": (t2 - t1) * 1000.0
            }
        except Exception as e:
            logger.error(f"[Vision] OCR Extraction failed: {e}")
            return {"parsed": [], "inference_time": 0.0, "preprocessing_time": 0.0}

    def get_spatial_text(self, image_path: str, offset_x: int = 0, offset_y: int = 0, roi_ratio: str = None) -> dict:
        """
        Extracts text and returns a structured list with absolute spatial coordinates.
        Returns: {"spatial_data": [...], "inference_time": float, "preprocessing_time": float}
        """
        crop_region = None
        if roi_ratio == "top_25_percent":
            img = cv2.imread(image_path)
            if img is not None:
                h, w = img.shape[:2]
                crop_region = (0, 0, w, int(h * 0.25))
        elif roi_ratio == "left_25_percent":
            img = cv2.imread(image_path)
            if img is not None:
                h, w = img.shape[:2]
                crop_region = (0, 0, int(w * 0.25), h)
                
        raw_results = self.extract_text(image_path, crop_region=crop_region)
        spatial_data = []
        for item in raw_results["parsed"]:
            box = item["box"]
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
            
        return {
            "spatial_data": spatial_data,
            "inference_time": raw_results["inference_time"],
            "preprocessing_time": raw_results["preprocessing_time"]
        }

    def get_raw_text(self, image_path: str) -> str:
        """Returns a single combined string of all extracted text."""
        self._lazy_load()
        if USE_WINSDK_OCR and self._win_engine:
            try:
                result = asyncio.run(self._winsdk_recognize(image_path))
                if result and result.lines:
                    return " ".join([result.lines[i].text for i in range(result.lines.size)])
                return ""
            except Exception as e:
                logger.error(f"[Vision] WinSDK Raw Extraction failed: {e}")
                return ""

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
