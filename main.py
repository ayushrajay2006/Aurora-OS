import sys
import os
import time
from config.config import config
from config.logging import logger
from config.state import state_manager
from brain.llm import llm_client
from brain.planner import planner, SYSTEM_PROMPT_TEMPLATE
from memory.memory import memory
# Ensure tools are imported so they register themselves
import tools.open_app
import tools.open_website
import tools.search_files
import tools.read_pdf
import tools.memory_control
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
    print("\n[+] Aurora is fully operational!")
    print("Type your message to chat, or type 'exit' or 'quit' to close.")
    print("-" * 60)
    
    # Load past database history for context
    history_records = memory.load_history(limit=30)
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
            
            print("Aurora > ", end="", flush=True)
            state_manager.update_state(status="Thinking")
            
            # Retrieve long term memories to inject into system prompt
            all_facts = memory.get_all_facts()
            if all_facts:
                memories_text = "\n".join([f"- {k}: {v}" for k, v in all_facts.items()])
            else:
                memories_text = "No long-term memories stored yet."

            # Construct the prompts dynamically
            tools_schema = planner._get_tools_schema_text()
            system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
                tools_schema_text=tools_schema,
                memories_text=memories_text
            )
            
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(chat_history)
            messages.append({"role": "user", "content": user_input})
            
            # Real-time token streaming with backtick-buffering filter
            full_text = ""
            buffer = ""
            json_started = False
            
            try:
                stream = llm_client.chat(messages, stream=True)
                for chunk in stream:
                    full_text += chunk
                    if json_started:
                        continue
                        
                    buffer += chunk
                    if "```json" in buffer:
                        json_started = True
                        parts = buffer.split("```json")
                        sys.stdout.write(parts[0])
                        sys.stdout.flush()
                        buffer = ""
                    elif buffer.startswith("`") or "`" in buffer:
                        if len(buffer) < 7:
                            continue
                        else:
                            if not "```json".startswith(buffer[:len(buffer)]):
                                sys.stdout.write(buffer)
                                sys.stdout.flush()
                                buffer = ""
                    else:
                        sys.stdout.write(buffer)
                        sys.stdout.flush()
                        buffer = ""
                        
                # Flush any remaining buffer if json wasn't started
                if buffer and not json_started:
                    sys.stdout.write(buffer)
                    sys.stdout.flush()
                
                # Print newline to end the Aurora response line neatly
                print()
                
            except Exception as e:
                print() # clear line
                logger.error(f"Ollama streaming chat failed: {e}", exc_info=True)
                print(f"Aurora > Error communicating with LLM service: {e}")
                continue
                
            # Parse the full text for actions
            reply, actions = planner.parse_response(full_text)
            
            # Save to memory and state
            memory.save_message("assistant", reply)
            state_manager.add_message("assistant", reply)
            
            # Keep history buffer capped
            chat_history.append({"role": "user", "content": user_input})
            chat_history.append({"role": "assistant", "content": reply})
            if len(chat_history) > 30:
                chat_history = chat_history[-30:]
                
            if actions:
                print("\nPlanned Actions:")
                state_manager.set_planned_actions(actions)
                for idx, act in enumerate(actions, 1):
                    tool_name = act.get("tool")
                    args = act.get("args", {})
                    
                    # Ignore dummy/conversational None action blocks
                    if not tool_name or str(tool_name).lower() in ["none", "null"]:
                        continue
                        
                    print(f"  {idx}. Tool: '{tool_name}' | Arguments: {args}")
                    
                    # Log planned tool call
                    action_id = f"act_{int(time.time())}_{idx}"
                    memory.log_action(action_id, tool_name, args, "planned")
                    
                    # Safety gates based on risk level
                    tool = registry.get_tool(tool_name)
                    risk_level = tool.risk_level if tool else "low"
                    
                    if risk_level == "medium":
                        print(f"     [!] CONFIRMATION REQUIRED: Aurora wants to run '{tool_name}' with args {args}.")
                        user_confirm = input("         Do you want to execute this action? (y/N): ").strip().lower()
                        if user_confirm not in ["y", "yes"]:
                            print(f"     [-] Action '{tool_name}' cancelled by user.")
                            memory.update_action(action_id, "cancelled", {"output": "Cancelled by user confirmation."})
                            continue
                            
                    elif risk_level == "high":
                        print(f"     [!] HIGH RISK ACTION: Aurora wants to run '{tool_name}' with args {args}.")
                        expected_input = "DELETE" if "delete" in tool_name.lower() else "EXECUTE"
                        user_confirm = input(f"         Please type '{expected_input}' to continue: ").strip()
                        if user_confirm != expected_input:
                            print(f"     [-] Action '{tool_name}' aborted (verification mismatch).")
                            memory.update_action(action_id, "cancelled", {"output": "Aborted: verification mismatch."})
                            continue
                    
                    # Execute tool
                    print(f"     [*] Executing '{tool_name}'...")
                    state_manager.update_state(status="Executing")
                    res = registry.execute_tool(tool_name, args)
                    print(f"     [Result] Success={res.get('success')} | Output='{res.get('output')}'")
                    memory.update_action(action_id, "success" if res.get("success") else "failed", res)
                    
            state_manager.update_state(status="Online")
            
        except (KeyboardInterrupt, EOFError):
            print("\nClosing Aurora. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error in chat loop: {e}", exc_info=True)
            print(f"Aurora > Encountered an error in the chat pipeline: {e}")

def main():
    print_banner()
    logger.info("Starting Aurora...")
    
    if not verify_ollama_setup():
        sys.exit(1)
        
    run_chat_loop()

if __name__ == "__main__":
    main()
