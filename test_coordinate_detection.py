import time
import pyautogui
from tools.registry import registry
from memory.memory import memory
from tools import locate_ui_element, mouse_control, control_app, open_app, open_website

def test_locator(app_name, open_tool, open_args, search_text, nth=1, match="contains"):
    print(f"\n=== Testing: {app_name} -> '{search_text}' ===")
    
    # Open the app/website
    print(f"[*] Opening {app_name}...")
    registry.execute_tool(open_tool, open_args)
    
    if open_tool == "open_app":
        registry.execute_tool("wait_for_window", {"app_name": app_name})
        registry.execute_tool("switch_to_app", {"app_name": app_name})
    
    time.sleep(3) # Wait for UI to render
    
    print(f"[*] Locating '{search_text}'...")
    res = registry.execute_tool("locate_ui_element", {
        "text": search_text,
        "match_mode": match,
        "threshold": 0.4,
        "nth_match": nth
    })
    
    if not res.get("success"):
        print(f"[FAIL] Could not locate '{search_text}': {res.get('error')}")
        return False
        
    print(f"[*] Output: {res.get('output')}")
    
    print("[*] Moving mouse to cached coordinates...")
    move_res = registry.execute_tool("move_mouse", {"x": "last_x", "y": "last_y"})
    
    if not move_res.get("success"):
        print(f"[FAIL] Mouse move failed: {move_res.get('error')}")
        return False
        
    print(f"[PASS] Successfully pointed at '{search_text}' in {app_name}.")
    
    if open_tool == "open_app":
        registry.execute_tool("close_app", {"app_name": app_name})
    return True

if __name__ == "__main__":
    print("Starting Coordinate Detection Validation...")
    
    tests = [
        ("notepad", "open_app", {"app_name": "notepad"}, "File", 1, "exact"),
        ("edge", "open_app", {"app_name": "msedge"}, "Settings", 1, "contains"),
        ("github", "open_website", {"url": "https://github.com"}, "Search", 1, "contains"),
        ("vscode", "open_app", {"app_name": "code"}, "Explorer", 1, "contains")
    ]
    
    for app_name, tool, args, text, nth, match in tests:
        test_locator(app_name, tool, args, text, nth, match)
        time.sleep(2)
