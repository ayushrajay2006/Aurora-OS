import uiautomation as auto
import json
import time
from brain.llm import llm_client
from config.config import config

def dump_ui_elements():
    desktop = auto.GetRootControl()
    active_window = None
    for win in desktop.GetChildren():
        if win.IsTopmost or win.HasKeyboardFocus:
            active_window = win
            break
            
    if not active_window:
        active_window = desktop
        
    elements = []
    element_id = 1
    
    def walk(ctrl, depth=0):
        nonlocal element_id
        if depth > 4: return
        try:
            name = ctrl.Name
            ctrl_type = ctrl.ControlTypeName
            rect = ctrl.BoundingRectangle
            
            # Only include elements that have a name or are obvious interactive types
            if (name or ctrl_type in ["ButtonControl", "EditControl", "ListItemControl", "MenuItemControl"]) and rect.width() > 0:
                elements.append({
                    "id": element_id,
                    "name": name,
                    "type": ctrl_type.replace("Control", ""),
                    "center_x": (rect.left + rect.right) // 2,
                    "center_y": (rect.top + rect.bottom) // 2
                })
                element_id += 1
                
            for child in ctrl.GetChildren():
                walk(child, depth + 1)
        except Exception:
            pass
            
    # Always include taskbar elements specifically
    try:
        taskbar = auto.Control(ClassName="Shell_TrayWnd")
        if taskbar.Exists(0, 0):
            walk(taskbar, depth=0)
    except: pass
    
    # Walk active window
    walk(active_window, depth=0)
    
    return elements

def test_semantic_search(query):
    print("Extracting UI elements...")
    t0 = time.time()
    elements = dump_ui_elements()
    print(f"Extracted {len(elements)} elements in {time.time()-t0:.2f}s")
    
    # Filter out empty names if there are too many elements to save context
    if len(elements) > 100:
        elements = [e for e in elements if e["name"]]
        
    # Take top 100
    elements = elements[:100]
    
    elements_json = json.dumps(elements, indent=2)
    
    prompt = f"""You are a UI automation assistant. The user wants to find: "{query}"

Here is a JSON list of visible UI elements on the screen:
{elements_json}

Which element ID best matches the user's request? 
Consider semantic meaning (e.g. "browser" -> "Google Chrome", "start" -> "Start Button").
Respond with ONLY the integer ID of the best match. If nothing matches, respond with 0."""

    print(f"Asking {config.model_name}...")
    res = llm_client.chat([{"role": "user", "content": prompt}], stream=False)
    print(f"LLM replied: {res}")
    
if __name__ == "__main__":
    test_semantic_search("taskbar")
    test_semantic_search("browser icon")
