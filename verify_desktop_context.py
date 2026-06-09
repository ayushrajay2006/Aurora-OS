import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools.registry import registry
from brain.entity_resolver import entity_resolver
from brain.desktop_context import desktop_context

# Initialize tools
import tools.open_app
import tools.control_app
import tools.close_app
import tools.ask_clarification

def run_command(tool_name: str, args: dict):
    print(f"\n[Command] -> {tool_name} {args}")
    
    # Run entity resolution first
    resolved_tool, resolved_args = entity_resolver.resolve_entities_before_execution(tool_name, args)
    print(f"  [Resolver] Mapped to: {resolved_tool} with args: {resolved_args}")
    
    tool = registry.get_tool(resolved_tool)
    if not tool:
        print(f"  [ERROR] Tool {resolved_tool} not found.")
        return
        
    res = registry.execute_tool(resolved_tool, resolved_args)
    print(f"  [Result] Success: {res.get('success')} | Output: {res.get('output')}")
    
    print(f"  [Context] Last Opened: {desktop_context._last_opened_app} | Last Focused: {desktop_context._last_focused_app}")
    time.sleep(1) # Allow windows to settle

def main():
    print("--- STARTING VERIFICATION SUITE ---")
    
    # Scenario 1
    print("\n\n=== SCENARIO 1 ===")
    run_command("open_app", {"app_name": "steam"})
    run_command("minimize_app", {"app_name": "steam"})
    run_command("restore_app", {"app_name": "steam"})
    run_command("maximize_app", {"app_name": "steam"})
    
    # Scenario 2
    print("\n\n=== SCENARIO 2 ===")
    run_command("open_app", {"app_name": "edge"})
    run_command("switch_to_app", {"app_name": "steam"})
    run_command("switch_to_app", {"app_name": "edge"})
    
    # Scenario 3
    print("\n\n=== SCENARIO 3 ===")
    run_command("open_app", {"app_name": "discord"})
    run_command("minimize_app", {"app_name": "it"})
    run_command("restore_app", {"app_name": "it"})
    
    # Scenario 4
    print("\n\n=== SCENARIO 4 ===")
    run_command("close_app", {"app_name": "steam"})
    run_command("close_app", {"app_name": "discord"})
    run_command("close_app", {"app_name": "edge"})
    
    print("\n--- VERIFICATION SUITE COMPLETE ---")

if __name__ == "__main__":
    main()
