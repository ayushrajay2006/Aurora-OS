import sys
import os
import time
import threading
import subprocess
import importlib

# Safe console helpers — no-op when running via pythonw.exe (no console attached)
def _cwrite(text: str):
    if sys.stdout:
        try:
            sys.stdout.write(text)
            sys.stdout.flush()
        except Exception:
            pass

def _cprint(*args, **kwargs):
    if sys.stdout:
        try:
            print(*args, **kwargs)
        except Exception:
            pass
from config.config import config
from config.logging import logger
from config.state import state_manager
from config.event_bus import event_bus
from brain.llm import llm_client
from brain.planner import planner, SYSTEM_PROMPT_TEMPLATE
from memory.memory import memory
from memory.vector_db import vector_memory
from tools.registry import registry
import brain.worker  # Initialize the background execution worker

TOOL_MODULES = [
    "tools.open_app",
    "tools.open_website",
    "tools.search_files",
    "tools.read_pdf",
    "tools.memory_control",
    "tools.delete_file",
    "tools.capture_screen",
    "tools.read_ocr",
    "tools.analyze_screen",
    "tools.mouse_keyboard",
    "tools.find_on_screen",
    "tools.teach_skill",
    "tools.system_control",
    "tools.manage_file",
    "tools.action_history",
    "tools.run_diagnostics",
    "tools.skill_discovery",
    "tools.remember_screen",
    "tools.task_queue"
]

def import_tool_modules():
    """Import tool modules dynamically so missing optional deps don't kill app startup."""
    for module_name in TOOL_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as e:
            logger.warning(f"Tool module '{module_name}' could not be loaded: {e}")

# Ensure tools are imported so they register themselves
import_tool_modules()

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

def execute_assistant_turn(user_input: str, chat_history: list, tts_manager, voice_output: bool, stt_manager=None) -> str:
    """Executes a single assistant turn: plans, executes tools, and returns final verbal reply."""
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
        
    knowledge_text = ""
    if vector_memory.enabled:
        relevant_skills = vector_memory.search_skills(user_input, n_results=2)
        if relevant_skills:
            knowledge_text = "## Relevant Documentation & Skills\n"
            for skill in relevant_skills:
                knowledge_text += f"- {skill}\n"
    
    MAX_STEPS = 8
    step = 1
    final_reply = ""
    consecutive_failures = 0   # tracks back-to-back tool failures for stuck detection
    last_failed_tool = None    # tracks which tool failed last for stuck detection
    past_actions = set()       # tracks action hashes for loop prevention interceptor
    
    while step <= MAX_STEPS:
        state_manager.update_state(status="Thinking")
        
        # Phase 6: Ambient Context Service Logic
        context_text = ""
        used_snapshot = None
        if len(chat_history) > 0 and chat_history[-1]["role"] == "user":
            user_prompt = chat_history[-1]["content"]
            context_keywords = {"this", "current", "here", "screen", "what am i", "summarize", "close", "read"}
            if any(kw in user_prompt.lower() for kw in context_keywords):
                from services.context_daemon import context_service
                used_snapshot = context_service.get_snapshot()
                if used_snapshot:
                    context_text = "\n## Ambient Context (User's Current Environment)\n"
                    if used_snapshot.active_window:
                        context_text += f"- Active Window: '{used_snapshot.active_window}'\n"
                    if used_snapshot.active_process:
                        context_text += f"- Active Process: '{used_snapshot.active_process}'\n"
                    if used_snapshot.clipboard:
                        clip_sample = used_snapshot.clipboard[:200] + ("..." if len(used_snapshot.clipboard) > 200 else "")
                        context_text += f"- Clipboard Contents: '{clip_sample}'\n"
                    if used_snapshot.current_folder:
                        context_text += f"- Current Folder: '{used_snapshot.current_folder}'\n"

        # Construct the prompts dynamically
        tools_schema = planner._get_tools_schema_text()
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            tools_schema_text=tools_schema,
            memories_text=memories_text,
            knowledge_text=knowledge_text
        )
        if context_text:
            system_prompt += context_text
        
        # Message list for this step (dynamically updated with complete history)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(chat_history)
        
        # Dynamic visual step header
        if step == 1:
            _cwrite("Aurora > ")
        else:
            _cwrite(f"\nAurora (Step {step}) > ")
        
        # Real-time token streaming with backtick-buffering filter
        full_text = ""
        buffer = ""
        json_started = False
        
        try:
            event_bus.publish("thinking_started", step=step)
            stream = llm_client.chat(messages, stream=True)
            for chunk in stream:
                full_text += chunk
                if json_started:
                    continue
                    
                buffer += chunk
                if "```json" in buffer:
                    json_started = True
                    parts = buffer.split("```json")
                    _cwrite(parts[0])
                    buffer = ""
                elif buffer.startswith("`") or "`" in buffer:
                    if len(buffer) < 7:
                        continue
                    else:
                        if not "```json".startswith(buffer[:len(buffer)]):
                            _cwrite(buffer)
                            buffer = ""
                else:
                    _cwrite(buffer)
                    buffer = ""
                    
            # Flush any remaining buffer if json wasn't started
            if buffer and not json_started:
                _cwrite(buffer)
            
            # Print newline to end the Aurora response line neatly
            _cprint()
            event_bus.publish("thinking_finished", step=step)
            
        except Exception as e:
            _cprint() # clear line
            logger.error(f"Ollama streaming chat failed: {e}", exc_info=True)
            _cprint(f"Aurora > Error communicating with LLM service: {e}")
            event_bus.publish("error_occurred", error=str(e), source="llm")
            if voice_output and tts_manager:
                tts_manager.speak("Sorry, I encountered an error communicating with my brain service.")
            break
            
        # Save assistant's raw generation (including JSON) to database and chat_history
        memory.save_message("assistant", full_text)
        chat_history.append({"role": "assistant", "content": full_text})
        
        # Parse the full text for actions
        _, actions, speech_text = planner.parse_response(full_text)
        
        # If there is conversational text, accumulate it and update state manager
        if speech_text:
            if final_reply:
                final_reply += "\n\n" + speech_text
            else:
                final_reply = speech_text
            state_manager.add_message("assistant", speech_text)
            
            # Speak intermediate responses immediately using the parsed speech text
            if voice_output and tts_manager:
                tts_manager.speak(speech_text)
        
        # Filter out null/None actions and validate coordinates
        valid_actions = []
        deferred_messages = []
        has_find_on_screen = False
        if actions:
            for act in actions:
                tool_name = act.get("tool")
                if tool_name and str(tool_name).lower() not in ["none", "null"]:
                    if tool_name == "find_on_screen":
                        has_find_on_screen = True
                    args = act.get("args", {})
                    # Discard dependent UI actions if coordinates aren't resolved yet
                    if tool_name in ("click", "move_mouse", "scroll", "type_text", "press_key", "drag"):
                        if has_find_on_screen:
                            logger.warning(f"Filter Action: Discarded '{tool_name}' because find_on_screen was called in the same turn. Forcing AI to wait for coordinates.")
                            deferred_messages.append(f"[System Notice] Action '{tool_name}' was deferred. You must wait for 'find_on_screen' to return coordinates first. Replan this action in the next turn.")
                            continue
                        # Validations for coordinate-based tools
                        if tool_name in ("click", "move_mouse", "scroll"):
                            x_val = args.get("x")
                            y_val = args.get("y")
                            is_x_valid = (str(x_val).strip().lstrip('-').isdigit() or str(x_val).strip().lower() == "center") if x_val not in (None, "", "null") else False
                            is_y_valid = (str(y_val).strip().lstrip('-').isdigit() or str(y_val).strip().lower() == "center") if y_val not in (None, "", "null") else False
                            if not is_x_valid or not is_y_valid:
                                logger.warning(f"Filter Action: Discarded '{tool_name}' because coordinates x='{x_val}', y='{y_val}' are invalid/empty.")
                                continue
                        if tool_name == "drag":
                            sx = args.get("start_x")
                            sy = args.get("start_y")
                            ex = args.get("end_x")
                            ey = args.get("end_y")
                            coords = (sx, sy, ex, ey)
                            is_valid = all((str(v).strip().lstrip('-').isdigit() or str(v).strip().lower() == "center") if v not in (None, "", "null") else False for v in coords)
                            if not is_valid:
                                logger.warning(f"Filter Action: Discarded '{tool_name}' because drag coordinates are invalid/empty.")
                                continue
                    valid_actions.append(act)
                    
        if not valid_actions:
            break
            
        # We have actions to execute!
        _cprint("\nPlanned Actions:")
        state_manager.set_planned_actions(valid_actions)
        
        tool_results = []
        for idx, act in enumerate(valid_actions, 1):
            tool_name = act.get("tool")
            args = act.get("args", {})
            
            # OpenClaw-style Loop Prevention Interceptor
            action_hash = f"{tool_name}:{str(args)}"
            if action_hash in past_actions and tool_name not in ["scroll", "press_key", "move_mouse"]:
                _cprint(f"     [!] Loop Interceptor: Blocked duplicate action '{tool_name}'")
                tool_results.append(f"[System Error: Loop detected. You have already executed '{tool_name}' with these exact arguments. Do NOT repeat it. Check the screen or try a different strategy.]")
                continue
            past_actions.add(action_hash)
            
            _cprint(f"  {idx}. Tool: '{tool_name}' | Arguments: {args}")
            event_bus.publish("task_progress", step=idx, total_steps=len(valid_actions), tool=tool_name, pct=round(idx / len(valid_actions), 2))
            
            # Log planned tool call
            action_id = f"act_{int(time.time())}_{step}_{idx}"
            memory.log_action(action_id, tool_name, args, "planned")
            
            # Safety gates based on risk level
            tool = registry.get_tool(tool_name)
            risk_level = tool.risk_level if tool else "low"
            threshold = config.get("safety_thresholds", {}).get(risk_level, "approve")
            
            cancelled = False
            if threshold == "approve":
                _cprint(f"     [!] CONFIRMATION REQUIRED: Aurora wants to run '{tool_name}' with args {args}.")
                if stt_manager and tts_manager:
                    user_confirm = "no"
                    
                    # Fetch preferred title from memory db (e.g. Boss)
                    user_title = memory.get_fact("preferred_title") or memory.get_fact("user_name") or "Boss"
                    
                    # Friendly mapping for actions
                    friendly_actions = {
                        "open_website": "open this website",
                        "open_app": "launch this application",
                        "search_files": "search your files",
                        "read_file": "read this file",
                        "delete_file": "delete this file",
                        "remember_fact": "save this preference"
                    }
                    action_phrase = friendly_actions.get(tool_name, f"execute {tool_name}")
                    
                    for attempt in range(2):
                        if attempt == 0:
                            tts_manager.speak(f"Ready to {action_phrase}, {user_title}. Should I go ahead?")
                        else:
                            tts_manager.speak(f"Sorry {user_title}, I didn't catch that. Please say yes or no.")
                        
                        _cwrite(f"         [Voice Confirmation - Attempt {attempt+1}] Speak 'yes' or 'no': ")
                        voice_confirm = stt_manager.listen_and_transcribe(timeout=5.0, phrase_time_limit=4.0).strip().lower()
                        _cprint(f"Received: '{voice_confirm}'")
                        
                        words = voice_confirm.split()
                        is_yes = any(w in words for w in ["yes", "yeah", "sure", "proceed", "ok", "okay", "y"]) or "yes" in voice_confirm or "yeah" in voice_confirm
                        is_no = any(w in words for w in ["no", "nope", "cancel", "stop", "n"]) or "no" in voice_confirm
                        
                        if is_yes:
                            tts_manager.speak("Proceeding.")
                            user_confirm = "yes"
                            break
                        elif is_no:
                            tts_manager.speak("Cancelled.")
                            user_confirm = "no"
                            break
                    else:
                        tts_manager.speak(f"No response received. Cancelling action, {user_title}.")
                        user_confirm = "no"
                else:
                    user_confirm = input("         Do you want to execute this action? (y/N): ").strip().lower() if sys.stdin else "no"
                if user_confirm not in ["y", "yes"]:
                    _cprint(f"     [-] Action '{tool_name}' cancelled by user.")
                    memory.update_action(action_id, "cancelled", {"output": "Cancelled by user confirmation."})
                    tool_results.append(f"- Tool '{tool_name}' cancelled by user.")
                    cancelled = True
                    
            elif threshold == "verify":
                _cprint(f"     [!] HIGH RISK ACTION: Aurora wants to run '{tool_name}' with args {args}.")
                expected_input = "DELETE" if "delete" in tool_name.lower() else "EXECUTE"
                if stt_manager and tts_manager:
                    user_confirm = "CANCEL"
                    
                    user_title = memory.get_fact("preferred_title") or memory.get_fact("user_name") or "Boss"
                    
                    for attempt in range(2):
                        if attempt == 0:
                            tts_manager.speak(f"This is a high-risk deletion, {user_title}. Please say {expected_input} to confirm, or cancel to abort.")
                        else:
                            tts_manager.speak(f"I didn't hear you, {user_title}. Please say {expected_input} or cancel.")
                            
                        _cwrite(f"         [Voice Confirmation - Attempt {attempt+1}] Speak '{expected_input}': ")
                        voice_confirm = stt_manager.listen_and_transcribe(timeout=5.0, phrase_time_limit=4.0).strip().upper()
                        _cprint(f"Received: '{voice_confirm}'")
                        
                        words = voice_confirm.split()
                        if expected_input in voice_confirm:
                            tts_manager.speak("Executing high risk action.")
                            user_confirm = expected_input
                            break
                        elif any(w in words for w in ["CANCEL", "ABORT", "NO"]) or any(w in voice_confirm for w in ["CANCEL", "ABORT"]):
                            tts_manager.speak("Aborted.")
                            user_confirm = "CANCEL"
                            break
                    else:
                        tts_manager.speak(f"No response received. Aborting action, {user_title}.")
                        user_confirm = "CANCEL"
                else:
                    user_confirm = input(f"         Please type '{expected_input}' to continue: ").strip() if sys.stdin else "CANCEL"
                if user_confirm != expected_input:
                    _cprint(f"     [-] Action '{tool_name}' aborted (verification mismatch).")
                    memory.update_action(action_id, "cancelled", {"output": "Aborted: verification mismatch."})
                    tool_results.append(f"- Tool '{tool_name}' aborted by user.")
                    cancelled = True
            
            if cancelled:
                continue
                
            # Create Task Object and Enqueue
            from brain.schemas import Task, ToolCall
            from brain.task_manager import task_manager
            
            task = Task(
                task_id=action_id,
                created_at=time.time(),
                tool_call=ToolCall(tool_name=tool_name, arguments=args, reasoning=""),
                context_snapshot=used_snapshot
            )
            
            task_manager.enqueue(task)
            _cprint(f"     [+] Task '{tool_name}' successfully added to the background queue.")
            tool_results.append(f"- Tool '{tool_name}' was queued for background execution. Task ID: {action_id}")
            
        results_text = "\n".join(tool_results)
        memory.save_message("user", f"Execution Results:\n{results_text}")
        chat_history.append({"role": "user", "content": f"Execution Results:\n{results_text}"})
        
        # We break the loop instead of iterating, returning control to the Voice/UI thread!
        break
        
    # Maintain chat history window size
    if len(chat_history) > 30:
        chat_history = chat_history[-30:]

    # Clean up active_screen.png if it exists at the end of the turn loop to save space and prevent re-uploading
    project_root = os.path.dirname(os.path.abspath(__file__))
    active_screen_path = os.path.join(project_root, "logs", "active_screen.png")
    if os.path.exists(active_screen_path):
        try:
            os.remove(active_screen_path)
            logger.info(f"Cleaned up active screen capture at {active_screen_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up active screen capture: {e}")

    return final_reply


def run_chat_loop(voice_input: bool = False, voice_output: bool = False):
    _cprint("\n[+] Aurora is fully operational!")
    if voice_input:
        _cprint("[+] Voice Input (Microphone) is active.")
    if voice_output:
        _cprint("[+] Voice Output (Text-to-Speech) is active.")
        
    tts_manager = None
    stt_manager = None
    if voice_output:
        from brain.voice_control import TextToSpeechManager
        tts_manager = TextToSpeechManager(
            rate=config.voice_rate,
            voice_index=config.voice_index,
            volume=config.voice_volume,
            voice_name=config.voice_name
        )
    if voice_input:
        from brain.voice_control import SpeechToTextManager
        stt_manager = SpeechToTextManager()
        stt_manager.adjust_for_noise()
        
    _cprint("Type your message to chat, or type 'exit' or 'quit' to close.")
    _cprint("-" * 60)
    
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
                    _cprint(f"\nUser (Voice) > {user_input}")
                else:
                    continue
            else:
                user_input = input("\nUser > ").strip() if sys.stdin else ""
                if not user_input:
                    continue
                    
            if user_input.lower() in ["exit", "quit"]:
                _cprint("Closing Aurora. Goodbye!")
                if voice_output and tts_manager:
                    tts_manager.speak("Goodbye.")
                break
                
            execute_assistant_turn(user_input, chat_history, tts_manager, voice_output, stt_manager=stt_manager)
            
        except (KeyboardInterrupt, EOFError, StopIteration):
            _cprint("\nClosing Aurora. Goodbye!")
            if voice_output and tts_manager:
                tts_manager.speak("Goodbye.")
            break
        except Exception as e:
            logger.error(f"Error in chat loop: {e}", exc_info=True)
            _cprint(f"Aurora > Encountered an error in the chat pipeline: {e}")


def run_voice_activation_loop(tts_manager, stt_manager, chat_history=None, turn_lock=None):
    _cprint("\n[+] Aurora Voice Activation Loop is active!")
    _cprint("[+] Waiting for wake word 'aurora'...")
    
    if chat_history is None:
        # Load past database history for context
        history_records = memory.load_history(limit=30)
        chat_history = []
        for r in history_records:
            chat_history.append({"role": r["role"], "content": r["content"]})
        
    state_manager.update_state(status="Sleeping")
    event_bus.publish("wake_status", active=False)
    
    if stt_manager:
        stt_manager.adjust_for_noise()
        
    # We want TTS notifications to always speak in this loop
    voice_output = tts_manager is not None
    
    if tts_manager:
        tts_manager.speak("Voice activation system ready.")
        
    is_active = False
    
    while True:
        try:
            if not is_active:
                # Sleep Mode: Continuous, low-overhead listening with short phrase limit (3 seconds)
                _cwrite("\r[Sleeping - Say 'hi aurora' to wake] ")
                
                wake_input = stt_manager.listen_and_transcribe(timeout=3.0, phrase_time_limit=3.0).strip().lower()
                if "aurora" in wake_input or "arora" in wake_input:
                    _cprint(f"\n[Waking Up] Detected wake word in: '{wake_input}'")
                    is_active = True
                    state_manager.update_state(status="Online")
                    event_bus.publish("wake_status", active=True)
                    user_title = memory.get_fact("preferred_title") or memory.get_fact("user_name") or "Boss"
                    greeting = f"Hey {user_title}, good to see you again. How can I help?"
                    if tts_manager:
                        tts_manager.speak(greeting)
                    else:
                        _cprint(f"Aurora > {greeting}")
                continue
            else:
                # Active Mode: Conversational Loop
                _cwrite("\r[Active - Speak command or 'bye aurora'] ")
                
                user_input = stt_manager.listen_and_transcribe(timeout=6.0, phrase_time_limit=10.0).strip()
                if not user_input:
                    continue
                    
                _cprint(f"\nUser (Voice) > {user_input}")
                
                # Check for sleep trigger
                cleaned_input = user_input.lower()
                if "bye aurora" in cleaned_input or "bye arora" in cleaned_input or cleaned_input in ["bye", "goodbye"]:
                    _cprint("Aurora > Goodbye. Going back to sleep.")
                    if tts_manager:
                        tts_manager.speak("Goodbye. Going back to sleep.")
                    is_active = False
                    state_manager.update_state(status="Sleeping")
                    event_bus.publish("wake_status", active=False)
                    continue
                
                # Execute assistant turn
                if turn_lock:
                    with turn_lock:
                        execute_assistant_turn(user_input, chat_history, tts_manager, voice_output, stt_manager=stt_manager)
                else:
                    execute_assistant_turn(user_input, chat_history, tts_manager, voice_output, stt_manager=stt_manager)
                
        except (KeyboardInterrupt, EOFError, StopIteration):
            _cprint("\nClosing Aurora Voice Activation Loop. Goodbye!")
            if tts_manager:
                tts_manager.speak("Goodbye.")
            break
        except Exception as e:
            logger.error(f"Error in voice activation loop: {e}", exc_info=True)
            _cprint(f"\n[!] Error: {e}")
            # Only speak error if it's a real unexpected error, not a stdout issue
            if tts_manager and not isinstance(e, AttributeError):
                tts_manager.speak("An unexpected error occurred in my voice system.")
            elif tts_manager and isinstance(e, AttributeError):
                logger.warning(f"Suppressed TTS for AttributeError in voice loop: {e}")
            time.sleep(1)


def verify_runtime_deps():
    """Verify all required and optional runtime dependencies are present."""
    missing = []
    try:
        import speech_recognition
    except ImportError:
        missing.append("SpeechRecognition (pip install SpeechRecognition)")
    try:
        import pyaudio
    except ImportError:
        missing.append("pyaudio (pip install pyaudio)")
    try:
        import pyautogui
    except ImportError:
        missing.append("pyautogui (pip install pyautogui)")
    try:
        import pyperclip
    except ImportError:
        missing.append("pyperclip (pip install pyperclip)")
    try:
        import pyttsx3
    except ImportError:
        missing.append("pyttsx3 (pip install pyttsx3)")
        
    if missing:
        _cprint("\n" + "="*50)
        _cprint("[!] Missing packages detected. Aurora will start in degraded mode:")
        for pkg in missing:
            _cprint(f"    - {pkg}")
        _cprint("="*50 + "\n")

def main():
    print_banner()
    logger.info("Starting Aurora...")
    verify_runtime_deps()
    
    # Simple CLI argument parsing
    import argparse
    parser = argparse.ArgumentParser(description="Aurora OS Assistant")
    parser.add_argument("--voice-in", action="store_true", help="Enable voice input (microphone)")
    parser.add_argument("--voice-out", action="store_true", help="Enable voice output (speech)")
    parser.add_argument("--voice", action="store_true", help="Enable both voice input and output")
    parser.add_argument("--wake", action="store_true", help="Launch in voice activation sleep/wake mode")
    parser.add_argument("--orb", action="store_true", help="Launch the permanent Tauri orb interface (default)")
    parser.add_argument("--chat", action="store_true", help="Launch in console chat mode instead of orb")
    args, unknown = parser.parse_known_args()
    
    # Determine mode flags
    use_orb = not args.chat
    voice_in = config.voice_input_enabled or args.voice or args.voice_in or args.wake or use_orb
    voice_out = config.voice_output_enabled or args.voice or args.voice_out or args.wake or use_orb
    wake_mode = config.voice_wake_enabled or args.wake or use_orb
    
    if not verify_ollama_setup():
        event_bus.publish("error_occurred", error="Ollama unavailable", source="startup")
        sys.exit(1)
    
    event_bus.publish("system_ready", model=config.model_name, voice=config.voice_name)
        
    if use_orb:
        from core.orb_coordinator import run_orb_mode
        run_orb_mode(execute_assistant_turn, run_voice_activation_loop)
    elif wake_mode:
        from core.orb_coordinator import build_tts_manager, build_stt_manager
        tts_manager = build_tts_manager()
        stt_manager = build_stt_manager()
        run_voice_activation_loop(tts_manager, stt_manager)
    else:
        run_chat_loop(voice_in, voice_out)
    
    event_bus.publish("system_shutdown", reason="normal_exit")

if __name__ == "__main__":
    main()
