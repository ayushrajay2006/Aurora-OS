import time
from tools.registry import registry
import tools.control_app
import tools.keyboard_control
import tools.open_app
import tools.close_app

# Simulate main.py's execution loop for Test 5: "open edge close edge switch to edge"
# where switch_to_app should fail gracefully and stop execution.

actions = [
    {"tool_name": "open_app", "arguments": {"app_name": "msedge"}},
    {"tool_name": "wait_for_window", "arguments": {"app_name": "msedge"}},
    {"tool_name": "close_app", "arguments": {"app_name": "msedge"}},
    {"tool_name": "switch_to_app", "arguments": {"app_name": "msedge"}},
    {"tool_name": "type_text", "arguments": {"text": "hello"}},
    {"tool_name": "press_key", "arguments": {"key": "enter"}}
]

print("=== STARTING EXECUTION LOOP SIMULATION ===")
for idx, act in enumerate(actions, 1):
    tool_name = act.get("tool_name")
    args = act.get("arguments", {})
    
    print(f"     [*] Executing '{tool_name}' with args {args}...")
    res = registry.execute_tool(tool_name, args)
    print(f"     [Result] Success={res.get('success')}")
    print(f"     [Output]\n{res.get('output')}")
    
    if not res.get("success"):
        print("\n     [!] Execution halted.")
        print(f"     Failed step:\n     {tool_name}({args})")
        print(f"\n     Reason:\n     {res.get('output')}")
        skipped = [a.get("tool_name") for a in actions[idx:]]
        if skipped:
            print(f"\n     Skipped actions:\n     * " + "\n     * ".join(skipped))
        print()
        break
        
print("=== END OF EXECUTION ===")
