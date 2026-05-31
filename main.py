import sys
import os
import time
from config.config import config
from config.logging import logger
from config.state import state_manager
from brain.llm import llm_client
from brain.planner import planner
from memory.memory import memory
# Ensure tools are imported so they register themselves
import tools.open_app
import tools.open_website
from tools.registry import registry

def print_banner():
    banner = """
+-----------------------------------------+
|           AURORA V1 - FOUNDATION        |
+-----------------------------------------+
| Status: Starting                        |
| Memory: Active                          |
| Voice: Disabled                         |
| Vision: Disabled                        |
+-----------------------------------------+
"""
    print(banner)

def verify_ollama_setup() -> bool:
    print("[*] Checking connectivity to Ollama API...")
    state_manager.update_state(status="Checking Ollama")
    
    if not llm_client.check_connection():
        print("[!] Ollama service is unavailable.")
        if llm_client.attempt_auto_start():
            print("[+] Successfully started Ollama daemon automatically.")
        else:
            print("\n" + "="*50)
            print("ERROR: Ollama is not running on your computer.")
            print("Please open the Ollama application manually or run:")
            print("    ollama serve")
            print("in a terminal, then restart Aurora.")
            print("="*50 + "\n")
            state_manager.update_state(status="Offline / Error")
            return False
            
    # Check configured model presence
    model_name = config.model_name
    print(f"[*] Checking presence of model: {model_name}...")
    if not llm_client.check_model_present(model_name):
        print("\n" + "="*50)
        print(f"ERROR: Model '{model_name}' is not installed in Ollama.")
        print(f"Please run the following command in a command prompt:")
        print(f"    ollama pull {model_name}")
        print("Once the download completes, restart Aurora to continue.")
        print("="*50 + "\n")
        state_manager.update_state(status="Model Missing")
        return False
        
    print(f"[+] Model '{model_name}' is available.")
    state_manager.update_state(status="Online", model_name=model_name)
    return True

def run_chat_loop():
    print("\n[+] Jarvis (Aurora V1) Foundation is fully operational!")
    print("Type your message to chat, or type 'exit' or 'quit' to close.")
    print("-" * 60)
    
    # Load past database history for context
    history_records = memory.load_history(limit=10)
    chat_history = []
    for r in history_records:
        chat_history.append({"role": r["role"], "content": r["content"]})
        
    while True:
        try:
            user_input = input("\nUser > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("Closing Aurora. Goodbye!")
                break
                
            # Log and save message
            memory.save_message("user", user_input)
            state_manager.add_message("user", user_input)
            
            print("Aurora > Thinking...", end="\r")
            state_manager.update_state(status="Thinking")
            
            # Request plan from Planner
            reply, actions = planner.create_plan(user_input, chat_history)
            
            # Print response
            print("Aurora >", reply)
            memory.save_message("assistant", reply)
            state_manager.add_message("assistant", reply)
            
            # Keep history buffer capped
            chat_history.append({"role": "user", "content": user_input})
            chat_history.append({"role": "assistant", "content": reply})
            if len(chat_history) > 20:
                chat_history = chat_history[-20:]
                
            if actions:
                print("\nPlanned Actions:")
                state_manager.set_planned_actions(actions)
                for idx, act in enumerate(actions, 1):
                    tool_name = act.get("tool")
                    args = act.get("args", {})
                    print(f"  {idx}. Tool: '{tool_name}' | Arguments: {args}")
                    
                    # Log planned tool call
                    action_id = f"act_{int(time.time())}_{idx}"
                    memory.log_action(action_id, tool_name, args, "planned")
                    
                    # Execute tool stub (Phase 1 does not run them, just demonstrates registry routing)
                    print(f"     [*] Executing '{tool_name}' stub...")
                    state_manager.update_state(status="Executing")
                    res = registry.execute_tool(tool_name, args)
                    print(f"     [Result] Success={res.get('success')} | Output='{res.get('output')}'")
                    memory.update_action(action_id, "success" if res.get("success") else "failed", res)
                    
            state_manager.update_state(status="Online")
            
        except KeyboardInterrupt:
            print("\nClosing Aurora. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error in chat loop: {e}", exc_info=True)
            print(f"Aurora > Encountered an error in the chat pipeline: {e}")

def main():
    print_banner()
    logger.info("Starting Jarvis (Aurora V1) Foundation...")
    
    if not verify_ollama_setup():
        sys.exit(1)
        
    run_chat_loop()

if __name__ == "__main__":
    main()
