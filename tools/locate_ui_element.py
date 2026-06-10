from tools.registry import registry, BaseTool
from vision.window_classifier import window_classifier
from config.state import state_manager

@registry.register(
    name="locate_ui_element",
    description="Locates the center coordinates of a UI element on the screen using OCR. Returns the absolute X and Y coordinates. Saves the coordinates to the system context for immediate use in subsequent tools.",
    args_schema={
        "text": {"type": "string", "description": "The exact text or substring to find on the screen."},
        "match_mode": {"type": "string", "description": "'exact' or 'contains'. Default is 'contains'.", "default": "contains"},
        "threshold": {"type": "number", "description": "Minimum confidence score (0.0 to 1.0). Default is 0.5.", "default": 0.5},
        "nth_match": {"type": "integer", "description": "If multiple matches exist, select the Nth match (1-indexed). Default is 1.", "default": 1}
    },
    risk_level="low"
)
class LocateUIElementTool(BaseTool):
    def execute(self, text: str, match_mode: str = "contains", threshold: float = 0.5, nth_match: int = 1, **kwargs) -> dict:
        try:
            # Get screen analysis (which now handles offset coordinates)
            result = window_classifier.analyze_current_screen()
            
            if not result.get("success"):
                return {"success": False, "error": "Screen analysis failed."}
                
            spatial_data = result.get("spatial_data", [])
            if not spatial_data:
                return {"success": False, "error": "No text detected on screen."}
                
            matches = []
            search_term = text.lower()
            
            for item in spatial_data:
                # Confidence gating
                if item["confidence"] < threshold:
                    continue
                    
                item_text = item["text"].lower()
                
                if match_mode == "exact":
                    if item_text == search_term:
                        matches.append(item)
                else:
                    if search_term in item_text:
                        matches.append(item)
                        
            if not matches:
                return {"success": False, "error": f"Text '{text}' not found on screen with confidence >= {threshold}."}
                
            if nth_match > len(matches):
                return {"success": False, "error": f"Requested match index {nth_match} but only found {len(matches)} matches."}
                
            target = matches[nth_match - 1]
            
            # Calculate absolute center coordinates
            center_x = int(target["x"] + (target["width"] / 2))
            center_y = int(target["y"] + (target["height"] / 2))
            
            # Cache the coordinates for immediate chaining
            state_manager.update_state(
                last_ui_x=center_x,
                last_ui_y=center_y
            )
            
            output = (f"Located '{target['text']}' (confidence: {target['confidence']:.2f}). "
                      f"Center coordinates: X={center_x}, Y={center_y}. "
                      f"These coordinates have been cached as 'last_x' and 'last_y'.")
                      
            return {
                "success": True,
                "output": output,
                "data": {
                    "x": center_x,
                    "y": center_y,
                    "confidence": target['confidence'],
                    "text": target['text']
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

tool_instance = LocateUIElementTool()
