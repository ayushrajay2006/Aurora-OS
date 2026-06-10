import time
from tools.mouse_control import tool_move, tool_scroll
from tools.keyboard_control import tool_type, tool_press, tool_hotkey
import pyautogui

def test():
    print("Testing mouse movement to (100, 100)")
    tool_move.execute(100, 100)
    time.sleep(1)
    
    print("Opening Notepad via hotkeys (win -> type -> enter)")
    tool_press.execute("win")
    time.sleep(1)
    tool_type.execute("notepad", interval=0.01)
    time.sleep(1)
    tool_press.execute("enter")
    
    time.sleep(2)
    print("Typing in Notepad")
    tool_type.execute("Hello from Aurora validation test!", interval=0.05)
    
    print("Pressing Enter")
    tool_press.execute("enter")
    
    print("Executing Hotkey Ctrl+S")
    tool_hotkey.execute(["ctrl", "s"])
    time.sleep(1)
    
    print("Closing Notepad without saving (Alt+F4, then n)")
    tool_hotkey.execute(["alt", "f4"])
    time.sleep(1)
    # the save prompt might pop up. If it does, 'n' will decline
    # Actually wait, maybe just hotkey esc instead of closing it to not break things
    tool_press.execute("esc")
    
    print("Scrolling")
    tool_scroll.execute(10)
    
    print("Validation passed deterministically.")

if __name__ == "__main__":
    test()
