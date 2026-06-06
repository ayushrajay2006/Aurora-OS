import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from brain.planner import planner
import main
main.import_tool_modules()

def test_scenario(name, prompt, expected_tools):
    print(f"\n[{name}]")
    print(f"Prompt: '{prompt}'")
    try:
        reply, actions, speech = planner.create_plan(prompt, [])
        tools_called = [a.get("tool") for a in actions]
        
        print(f"Reply: {reply}")
        print(f"Speech: {speech}")
        print(f"Tools Generated: {tools_called}")
        
        success = True
        for expected in expected_tools:
            if expected not in tools_called:
                print(f"  [X] Failed: Expected tool '{expected}' was not generated.")
                success = False
                
        if success:
            print("  [OK] Passed")
    except Exception as e:
        print(f"  [X] Exception: {e}")

if __name__ == "__main__":
    print("=== RUNNING E2E LLM CAPABILITY TESTS ===")
    
    test_scenario(
        name="Opening and Closing Apps",
        prompt="open notepad and then close calc",
        expected_tools=["open_app", "close_process"]
    )
    
    test_scenario(
        name="Finding and Summarizing Docs",
        prompt="search for my project report and summarize it",
        expected_tools=["search_files"] # Due to State-Dependent Planning Constraint, it should ONLY search first!
    )
    
    test_scenario(
        name="Vision and Screen Analysis",
        prompt="what is on my screen right now?",
        expected_tools=["analyze_screen"] # take_screenshot is optional since analyze_screen auto-captures
    )
    
    test_scenario(
        name="Mouse and Keyboard Controls",
        prompt="click on the center of the screen and type hello",
        expected_tools=["click", "type_text"]
    )
    
    test_scenario(
        name="System Folders",
        prompt="open my documents folder",
        expected_tools=["open_app"]
    )
    
    print("\n=== TESTS COMPLETE ===")
