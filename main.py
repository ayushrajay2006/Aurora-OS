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
import tools.delete_file
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

def run_chat_loop(voice_input: bool = False, voice_output: bool = False):
    print("\n[+] Aurora is fully operational!")
    if voice_input:
        print("[+] Voice Input (Microphone) is active.")
    if voice_output:
        print("[+] Voice Output (Text-to-Speech) is active.")
        
    tts_manager = None
    stt_manager = None
    if voice_output:
        from brain.voice_control import TextToSpeechManager
        tts_manager = TextToSpeechManager(
            rate=config.voice_rate,
            voice_index=config.voice_index,
            volume=config.voice_volume
        )
    if voice_input:
        from brain.voice_control import SpeechToTextManager
        stt_manager = SpeechToTextManager()
        stt_manager.adjust_for_noise()
        
    print("Type your message to chat, or type 'exit' or 'quit' to close.")
    print("-" * 60)
    
    if voice_output and tts_manager:
        tts_manager.speak("Aurora is ready.")
        
    # Load past database history for context
    history_records = memory.load_history(limit=30)
    chat_history = []
    for r in history_records:
        chat_history.append({"role": r["role"], "content": r["content"]})
        
    while True:
        try:
            if voice_input and stt_manager:
                user_input = stt_manager.listen_and_transcribe()
                if user_input:
                    print(f"\nUser (Voice) > {user_input}")
                else:
                    continue
            else:
                user_input = input("\nUser > ").strip()
                if not user_input:
                    continue
                    
            if user_input.lower() in ["exit", "quit"]:
                print("Closing Aurora. Goodbye!")
                if voice_output and tts_manager:
                    tts_manager.speak("Goodbye.")
                break
                
            # Log and save message
            memory.save_message("user", user_input)
            chat_history.append({"role": "user", "content": user_input})
            state_manager.add_message("user", user_input)
            
            state_manager.update_state(status="Thinking")
            
            # Retrieve long term memories to inject into system prompt
            all_facts = memory.get_all_facts()
            if all_facts:
                memories_text = "\n".join([f"- {k}: {v}" for k, v in all_facts.items()])
            else:
                memories_text = "No long-term memories stored yet."
            
            MAX_STEPS = 5
            step = 1
            final_reply = ""
            
            while step <= MAX_STEPS:
                state_manager.update_state(status="Thinking")
                
                # Construct the prompts dynamically
                tools_schema = planner._get_tools_schema_text()
                system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
                    tools_schema_text=tools_schema,
                    memories_text=memories_text
                )
                
                # Message list for this step (dynamically updated with complete history)
                messages = [{"role": "system", "content": system_prompt}]
                messages.extend(chat_history)
                
                # Dynamic visual step header
                if step == 1:
                    print("Aurora > ", end="", flush=True)
                else:
                    print(f"\nAurora (Step {step}) > ", end="", flush=True)
                
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
                    break
                    
                # Save assistant's raw generation (including JSON) to database and chat_history
                memory.save_message("assistant", full_text)
                chat_history.append({"role": "assistant", "content": full_text})
                
                # Parse the full text for actions
                reply, actions = planner.parse_response(full_text)
                
                # If there is conversational text, accumulate it and update state manager
                if reply:
                    if final_reply:
                        final_reply += "\n\n" + reply
                    else:
                        final_reply = reply
                    state_manager.add_message("assistant", reply)
                
                # Filter out null/None actions
                valid_actions = []
                if actions:
                    for act in actions:
                        tool_name = act.get("tool")
                        if tool_name and str(tool_name).lower() not in ["none", "null"]:
                            valid_actions.append(act)
                            
                if not valid_actions:
                    break
                    
                # We have actions to execute!
                print("\nPlanned Actions:")
                state_manager.set_planned_actions(valid_actions)
                
                tool_results = []
                for idx, act in enumerate(valid_actions, 1):
                    tool_name = act.get("tool")
                    args = act.get("args", {})
                    
                    print(f"  {idx}. Tool: '{tool_name}' | Arguments: {args}")
                    
                    # Log planned tool call
                    action_id = f"act_{int(time.time())}_{step}_{idx}"
                    memory.log_action(action_id, tool_name, args, "planned")
                    
                    # Safety gates based on risk level
                    tool = registry.get_tool(tool_name)
                    risk_level = tool.risk_level if tool else "low"
                    
                    cancelled = False
                    if risk_level == "medium":
                        print(f"     [!] CONFIRMATION REQUIRED: Aurora wants to run '{tool_name}' with args {args}.")
                        user_confirm = input("         Do you want to execute this action? (y/N): ").strip().lower()
                        if user_confirm not in ["y", "yes"]:
                            print(f"     [-] Action '{tool_name}' cancelled by user.")
                            memory.update_action(action_id, "cancelled", {"output": "Cancelled by user confirmation."})
                            tool_results.append(f"- Tool '{tool_name}' cancelled by user.")
                            cancelled = True
                            
                    elif risk_level == "high":
                        print(f"     [!] HIGH RISK ACTION: Aurora wants to run '{tool_name}' with args {args}.")
                        expected_input = "DELETE" if "delete" in tool_name.lower() else "EXECUTE"
                        user_confirm = input(f"         Please type '{expected_input}' to continue: ").strip()
                        if user_confirm != expected_input:
                            print(f"     [-] Action '{tool_name}' aborted (verification mismatch).")
                            memory.update_action(action_id, "cancelled", {"output": "Aborted: verification mismatch."})
                            tool_results.append(f"- Tool '{tool_name}' aborted by user.")
                            cancelled = True
                    
                    if cancelled:
                        continue
                        
                    # Execute tool
                    print(f"     [*] Executing '{tool_name}'...")
                    state_manager.update_state(status="Executing")
                    res = registry.execute_tool(tool_name, args)
                    success = res.get("success", False)
                    output = res.get("output", "")
                    
                    print(f"     [Result] Success={success} | Output='{output}'")
                    memory.update_action(action_id, "success" if success else "failed", res)
                    tool_results.append(f"- Tool '{tool_name}' completed. Success={success}. Output: {output}")
                    
                # Save execution results to database and chat_history
                results_text = "\n".join(tool_results)
                memory.save_message("user", f"Execution Results:\n{results_text}")
                chat_history.append({"role": "user", "content": f"Execution Results:\n{results_text}"})
                
                step += 1
                
            # Maintain chat history window size
            if len(chat_history) > 30:
                chat_history = chat_history[-30:]
                
            state_manager.update_state(status="Online")
            
            # Speak final response if voice output is active
            if voice_output and tts_manager and final_reply:
                tts_manager.speak(final_reply)
                
        except (KeyboardInterrupt, EOFError, StopIteration):
            print("\nClosing Aurora. Goodbye!")
            if voice_output and tts_manager:
                tts_manager.speak("Goodbye.")
            break
        except Exception as e:
            logger.error(f"Error in chat loop: {e}", exc_info=True)
            print(f"Aurora > Encountered an error in the chat pipeline: {e}")

def main():
    print_banner()
    logger.info("Starting Aurora...")
    
    # Simple CLI argument parsing
    import argparse
    parser = argparse.ArgumentParser(description="Aurora OS Assistant")
    parser.add_argument("--voice-in", action="store_true", help="Enable voice input (microphone)")
    parser.add_argument("--voice-out", action="store_true", help="Enable voice output (speech)")
    parser.add_argument("--voice", action="store_true", help="Enable both voice input and output")
    args, unknown = parser.parse_known_args()
    
    # Determine voice states by overriding config values with command line flags
    voice_in = config.voice_input_enabled or args.voice or args.voice_in
    voice_out = config.voice_output_enabled or args.voice or args.voice_out
    
    if not verify_ollama_setup():
        sys.exit(1)
        
    run_chat_loop(voice_in, voice_out)

if __name__ == "__main__":
    main()
