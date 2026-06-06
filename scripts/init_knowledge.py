import sys
import os

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from memory.vector_db import vector_memory

def bootstrap_knowledge():
    if not vector_memory.enabled:
        print("Vector memory is not enabled. Please install chromadb.")
        return

    skills = [
        {
            "name": "maximize_window",
            "instructions": "To maximize the currently active window, use the press_key tool with keys='win+up'."
        },
        {
            "name": "minimize_window",
            "instructions": "To minimize the currently active window, use the press_key tool with keys='win+down'."
        },
        {
            "name": "copy_text",
            "instructions": "To copy selected text or items, use the press_key tool with keys='ctrl+c'."
        },
        {
            "name": "paste_text",
            "instructions": "To paste copied text or items, use the press_key tool with keys='ctrl+v'."
        },
        {
            "name": "select_all",
            "instructions": "To select all text or items in the current view, use the press_key tool with keys='ctrl+a'."
        },
        {
            "name": "close_window",
            "instructions": "To close the currently active window or application, use the press_key tool with keys='alt+f4'."
        },
        {
            "name": "switch_app",
            "instructions": "To switch to a different open application, use the press_key tool with keys='alt+tab'."
        },
        {
            "name": "open_settings",
            "instructions": "To open Windows Settings, use the open_app tool with app_name='settings'."
        },
        {
            "name": "open_task_manager",
            "instructions": "To open Task Manager, use the open_app tool with app_name='task manager' or press_key(keys='ctrl+shift+esc')."
        }
    ]

    print(f"Loading {len(skills)} base skills into Vector Memory...")
    for skill in skills:
        success = vector_memory.teach_skill(skill["name"], skill["instructions"], tags=["system", "shortcut"])
        if success:
            print(f"  [+] Loaded: {skill['name']}")
        else:
            print(f"  [-] Failed: {skill['name']}")

if __name__ == "__main__":
    bootstrap_knowledge()
