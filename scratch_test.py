import sys
import os
import time

# Ensure we can import from Aurora root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools.mouse_keyboard import GetScreenSizeTool, MoveMouseTool, ClickTool, TypeTextTool, PressKeyTool
from tools.capture_screen import TakeScreenshotTool
from tools.find_on_screen import FindOnScreenTool
from tools.analyze_screen import AnalyzeScreenTool
from brain.llm import llm_client

def test_automation():
    print("========================================")
    print("   AURORA AUTOMATION & VISION TEST      ")
    print("========================================\n")

    # 1. Screen size
    print("[1/5] Testing screen resolution detection...")
    size_tool = GetScreenSizeTool()
    res = size_tool.execute()
    print(f"Result: {res}\n")
    if not res.get("success"):
        print("FAIL: Cannot get screen size. Aborting.")
        return

    # 2. Mouse Move
    print("[2/5] Testing mouse movement (moving to center of screen)...")
    w = res.get("width", 1920)
    h = res.get("height", 1080)
    move_tool = MoveMouseTool()
    print(move_tool.execute(x=w//2, y=h//2, duration=0.5))
    print()

    # 3. Keyboard
    print("[3/5] Testing keyboard (pressing Windows key to open start menu)...")
    key_tool = PressKeyTool()
    print(key_tool.execute(keys="win"))
    time.sleep(1) # wait for start menu
    print("Closing start menu...")
    print(key_tool.execute(keys="escape"))
    print()

    # 4. Find on screen (UIA / Vision)
    print("[4/5] Testing UI element finding (looking for 'Taskbar')...")
    find_tool = FindOnScreenTool()
    find_res = find_tool.execute(query="Taskbar")
    print(f"Result: {find_res}\n")

    # 5. Screen Analysis (Llava)
    print("[5/5] Testing Vision AI (Llava)...")
    if not llm_client.check_model_present("llava:latest"):
        print("WARNING: llava:latest is not installed in Ollama. Skipping Vision AI test.")
    else:
        capture_tool = TakeScreenshotTool()
        print("Capturing screen...")
        capture_res = capture_tool.execute()
        print(f"Capture: {capture_res}")
        
        analyze_tool = AnalyzeScreenTool()
        print("Analyzing screen with llava:latest...")
        analyze_res = analyze_tool.execute(query="Describe what you see on the screen briefly.")
        print(f"Result: {analyze_res}")

if __name__ == "__main__":
    test_automation()
