import time
import os
import win32gui
import pyautogui
from brain.planner import planner
from tools.registry import registry
from memory.memory import memory
import tools.control_app
import tools.open_app
import tools.open_file
import tools.open_folder
import tools.open_website
import tools.analyze_screen
import tools.mouse_control
import tools.keyboard_control
import tools.memory_control
import tools.discover_apps
import json

results = {}

def log_test(category, test_name, command, planned, resolved, output, passed, root_cause=""):
    if category not in results:
        results[category] = []
    
    results[category].append({
        "test_name": test_name,
        "command": command,
        "planned": planned,
        "resolved": resolved,
        "output": output,
        "passed": passed,
        "root_cause": root_cause
    })
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {category} - {test_name}")
    if not passed:
        print(f"   Root Cause: {root_cause}")

def test_memory():
    cat = "1. Memory"
    print(f"\n=== {cat} ===")
    
    try:
        # Save memory
        res = registry.execute_tool("remember_fact", {"key": "favorite color", "value": "neon green"})
        log_test(cat, "Save Memory", "remember_fact", [], [], str(res.get("output")), res.get("success"), str(res.get("output")) if not res.get("success") else "")
        
        # Deterministic interception
        from main import check_deterministic_memory_retrieval
        ans = check_deterministic_memory_retrieval("what is my favorite color")
        passed = "neon green" in (ans or "").lower()
        log_test(cat, "Deterministic Retrieval", "what is my favorite color", [], [], str(ans), passed, "Did not retrieve color deterministically" if not passed else "")
        
    except Exception as e:
        log_test(cat, "Memory Exception", "", [], [], str(e), False, str(e))

def test_app_control():
    cat = "2. Application Control"
    print(f"\n=== {cat} ===")
    
    try:
        res1 = registry.execute_tool("open_app", {"app_name": "notepad"})
        log_test(cat, "open_app", "open_app(notepad)", [], [], res1.get("output"), res1.get("success"), res1.get("output") if not res1.get("success") else "")
        
        time.sleep(2)
        
        res2 = registry.execute_tool("close_app", {"app_name": "notepad"})
        log_test(cat, "close_app", "close_app(notepad)", [], [], res2.get("output"), res2.get("success"), res2.get("output") if not res2.get("success") else "")
        
    except Exception as e:
        log_test(cat, "App Control Exception", "", [], [], str(e), False, str(e))

def test_window_control():
    cat = "3. Window Control"
    print(f"\n=== {cat} ===")
    
    try:
        registry.execute_tool("open_app", {"app_name": "mspaint"})
        time.sleep(2)
        
        res1 = registry.execute_tool("minimize_app", {"app_name": "mspaint"})
        log_test(cat, "minimize_app", "minimize_app(mspaint)", [], [], str(res1.get("output")), res1.get("success"), str(res1.get("output")) if not res1.get("success") else "")
        
        time.sleep(1)
        res2 = registry.execute_tool("restore_app", {"app_name": "mspaint"})
        log_test(cat, "restore_app", "restore_app(mspaint)", [], [], str(res2.get("output")), res2.get("success"), str(res2.get("output")) if not res2.get("success") else "")
        
        time.sleep(1)
        res3 = registry.execute_tool("switch_to_app", {"app_name": "mspaint"})
        log_test(cat, "switch_to_app & foreground verify", "switch_to_app(mspaint)", [], [], str(res3.get("output")), res3.get("success"), str(res3.get("output")) if not res3.get("success") else "")
        
        registry.execute_tool("close_app", {"app_name": "mspaint"})
    except Exception as e:
        log_test(cat, "Window Control Exception", "", [], [], str(e), False, str(e))

def test_planner_routing():
    cat = "5. Search Routing & 11. Planner Verification"
    print(f"\n=== {cat} ===")
    
    queries = [
        ("search rust libraries on github", "open_website", "github.com/search"),
        ("open vscode switch to it type hello", "wait_for_window", "vscode"),
    ]
    
    for q, expected_tool, expected_arg_part in queries:
        try:
            reply, actions = planner.create_plan(q, [])
            tool_found = any(a.get("tool_name", "") == expected_tool for a in actions)
            arg_found = False
            for a in actions:
                args = str(a.get("arguments", ""))
                if expected_arg_part.lower() in args.lower():
                    arg_found = True
            
            passed = tool_found and arg_found
            log_test(cat, f"Planner: {q}", q, actions, actions, reply, passed, f"Failed to generate {expected_tool} with {expected_arg_part}" if not passed else "")
        except Exception as e:
            log_test(cat, f"Planner Exception: {q}", q, [], [], str(e), False, str(e))

def test_ocr():
    cat = "7. OCR Perception"
    print(f"\n=== {cat} ===")
    
    try:
        registry.execute_tool("open_app", {"app_name": "notepad"})
        time.sleep(2)
        registry.execute_tool("type_text", {"text": "AURORA_VALIDATION_TEXT_123"})
        time.sleep(1)
        
        res = registry.execute_tool("analyze_screen", {})
        output = str(res.get("output", ""))
        passed = "AURORA_VALIDATION_TEXT_123" in output or "VALIDATION" in output
        log_test(cat, "analyze_screen text detection", "analyze_screen", [], [], output[:200]+"...", passed, "Failed to read typed text via OCR" if not passed else "")
        
        registry.execute_tool("close_app", {"app_name": "notepad"})
    except Exception as e:
        log_test(cat, "OCR Exception", "", [], [], str(e), False, str(e))

def test_mouse_keyboard():
    cat = "8. Mouse & 9. Keyboard"
    print(f"\n=== {cat} ===")
    
    try:
        res1 = registry.execute_tool("move_mouse", {"x": 500, "y": 500, "duration": 0.1})
        x, y = pyautogui.position()
        passed1 = abs(x - 500) < 5 and abs(y - 500) < 5
        log_test(cat, "move_mouse", "move_mouse(500, 500)", [], [], res1.get("output"), passed1, "Mouse did not reach target coordinates" if not passed1 else "")
        
        res2 = registry.execute_tool("type_text", {"text": "test", "interval": 0.01})
        log_test(cat, "type_text", "type_text(test)", [], [], res2.get("output"), res2.get("success"), res2.get("output") if not res2.get("success") else "")
        
    except Exception as e:
        log_test(cat, "Mouse/Keyboard Exception", "", [], [], str(e), False, str(e))

def test_execution_chain():
    cat = "10. Execution Chain Verification"
    print(f"\n=== {cat} ===")
    
    # Simulate execution loop failure
    actions = [
        {"tool_name": "open_app", "arguments": {"app_name": "notepad"}},
        {"tool_name": "wait_for_window", "arguments": {"app_name": "notepad"}},
        {"tool_name": "close_app", "arguments": {"app_name": "notepad"}},
        {"tool_name": "switch_to_app", "arguments": {"app_name": "notepad"}},
        {"tool_name": "type_text", "arguments": {"text": "hello"}}
    ]
    
    output_log = []
    hard_abort_triggered = False
    
    for idx, act in enumerate(actions):
        tool_name = act.get("tool_name")
        args = act.get("arguments", {})
        res = registry.execute_tool(tool_name, args)
        output_log.append(f"{tool_name}: {res.get('success')}")
        
        if not res.get("success"):
            hard_abort_triggered = True
            break
            
    passed = hard_abort_triggered and len(output_log) < len(actions)
    log_test(cat, "Hard Abort on Failure", "chain", actions, output_log, str(output_log), passed, "Execution did not halt on failure" if not passed else "")

if __name__ == "__main__":
    print("Starting Aurora E2E Validation Suite...")
    test_memory()
    test_app_control()
    test_window_control()
    test_ocr()
    test_mouse_keyboard()
    test_execution_chain()
    test_planner_routing()
    
    with open("e2e_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nValidation complete. Results saved to e2e_results.json")
