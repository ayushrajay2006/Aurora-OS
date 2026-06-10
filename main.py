import sys
import os
import time
import re
from typing import Optional, List, Dict, Any
from config.config import config
from config.logging import logger
from config.state import state_manager
from brain.llm import llm_client
from brain.planner import planner, SYSTEM_PROMPT_TEMPLATE
from memory.memory import memory
# Ensure tools are imported so they register themselves
import tools.open_app
import tools.open_file
import tools.open_folder
import tools.close_app
import tools.open_website
import tools.search_files
import tools.read_pdf
import tools.memory_control
import tools.discover_apps
import tools.control_app
import tools.analyze_screen
from tools.registry import registry

def print_banner():
    banner = """
+-----------------------------------------+
|           AURORA V2 - FOUNDATION        |
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

def check_deterministic_memory_retrieval(user_input: str) -> Optional[str]:
    query_clean = user_input.lower().strip()
    
    # If the user is trying to store a memory, do NOT intercept.
    storage_phrases = ["remember that", "remember my", "save that", "save my", "store that", "store my", "set my", "remember to"]
    if any(phrase in query_clean for phrase in storage_phrases):
        return None
        
    # Check if this is a question/retrieval
    retrieval_indicators = ["what", "where", "who", "when", "tell", "show", "recall", "get", "retrieve", "know", "?", "project folder", "my project"]
    if not any(indicator in query_clean for indicator in retrieval_indicators):
        return None
        
    from memory.memory import memory
    facts = memory.get_all_facts()
    if not facts:
        return None
        
    best_match_key = None
    best_match_value = None
    
    for key, value in facts.items():
        # Split key by underscore
        key_words = key.lower().split('_')
        # Check if all words of the key are present in the query
        if all(word in query_clean for word in key_words):
            if best_match_key is None or len(key) > len(best_match_key):
                best_match_key = key
                best_match_value = value
                
    if best_match_key:
        display_key = best_match_key.replace('_', ' ')
        display_key = display_key[0].upper() + display_key[1:]
        return f"{display_key} is {best_match_value}."
        
    return None

def rank_search_results(matches: list, query: str) -> list:
    query_clean = query.lower().strip()
    keywords = [k for k in query_clean.split() if k]
    
    ranked = []
    for m in matches:
        filename = m["filename"].lower()
        name_no_ext = os.path.splitext(filename)[0]
        
        score = 0
        if name_no_ext == query_clean:
            score += 500
        if query_clean in filename:
            score += 100
        for kw in keywords:
            if kw in filename:
                score += 10
                
        ranked.append((score, m.get("mtime", 0.0), m))
        
    ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [item[2] for item in ranked]

def handle_search_continuation(matches: list, query: str):
    num_results = len(matches)
    if num_results == 0:
        return
        
    if num_results == 1:
        match = matches[0]
        print(f"\n     [?] Found 1 match: '{match['filename']}'. Would you like to open it? (y/N): ", end="", flush=True)
        user_choice = input().strip().lower()
        if user_choice in ["y", "yes"]:
            print(f"     [*] Executing 'open_file' for '{match['absolute_path']}'...")
            open_res = registry.execute_tool("open_file", {"path": match["absolute_path"]})
            print(f"     [Result] Success={open_res.get('success')} | Output='{open_res.get('output')}'")
            
    elif 2 <= num_results <= 5:
        print(f"\n     [?] Found {num_results} matches. Which one would you like to open?")
        for idx, match in enumerate(matches, 1):
            print(f"       {idx}. {match['filename']} ({match['absolute_path']})")
        print("       Enter number to open (or press Enter to skip): ", end="", flush=True)
        user_input = input().strip()
        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < num_results:
                match = matches[idx]
                print(f"     [*] Executing 'open_file' for '{match['absolute_path']}'...")
                open_res = registry.execute_tool("open_file", {"path": match["absolute_path"]})
                print(f"     [Result] Success={open_res.get('success')} | Output='{open_res.get('output')}'")
                
    else:
        ranked_matches = rank_search_results(matches, query)
        print(f"\n     [?] Found {num_results} matches (ranked by relevance and modification date).")
        print("     Showing top 5 matches. Which one would you like to open?")
        display_count = min(5, len(ranked_matches))
        for idx in range(display_count):
            match = ranked_matches[idx]
            print(f"       {idx + 1}. {match['filename']} ({match['absolute_path']})")
        print("       Enter number to open (or press Enter to skip): ", end="", flush=True)
        user_input = input().strip()
        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < display_count:
                match = ranked_matches[idx]
                print(f"     [*] Executing 'open_file' for '{match['absolute_path']}'...")
                open_res = registry.execute_tool("open_file", {"path": match["absolute_path"]})
                print(f"     [Result] Success={open_res.get('success')} | Output='{open_res.get('output')}'")

def sanitize_assistant_reply(text: str) -> str:
    # Remove any markdown code blocks
    text_clean = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Remove any leftover ticks
    text_clean = text_clean.replace("```", "")
    # Clean up double newlines
    text_clean = re.sub(r"\n{3,}", "\n\n", text_clean)
    return text_clean.strip()

def run_chat_loop():
    print("\n[+] Aurora is fully operational!")
    print("Type your message to chat, or type 'exit' or 'quit' to close.")
    print("-" * 60)
    
    # Load past database history for context
    history_records = memory.load_history(limit=30)
    chat_history = []
    for r in history_records:
        chat_history.append({"role": r["role"], "content": r["content"]})
        
    from typing import Optional

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
            
            # Check for deterministic memory retrieval first
            memory_answer = check_deterministic_memory_retrieval(user_input)
            if memory_answer:
                print(f"Aurora > {memory_answer}")
                memory.save_message("assistant", memory_answer)
                state_manager.add_message("assistant", memory_answer)
                chat_history.append({"role": "user", "content": user_input})
                chat_history.append({"role": "assistant", "content": memory_answer})
                if len(chat_history) > 30:
                    chat_history = chat_history[-30:]
                continue
                
            # Intercept pending search context continuation
            import urllib.parse
            import webbrowser
            global pending_search_context
            if 'pending_search_context' not in globals():
                pending_search_context = None
                
            if pending_search_context:
                site = pending_search_context
                query = urllib.parse.quote(user_input.strip())
                pending_search_context = None
                
                urls = {
                    "youtube": f"https://www.youtube.com/results?search_query={query}",
                    "google": f"https://www.google.com/search?q={query}",
                    "gmail": f"https://mail.google.com/mail/u/0/#search/{query}",
                    "github": f"https://github.com/search?q={query}",
                    "reddit": f"https://www.reddit.com/search/?q={query}",
                    "wikipedia": f"https://en.wikipedia.org/wiki/Special:Search?search={query}"
                }
                
                target_url = urls.get(site, f"https://www.google.com/search?q={query}")
                print(f"Aurora > Opening {site} search for '{user_input}'...")
                try:
                    webbrowser.open(target_url)
                except Exception as e:
                    logger.error(f"Failed to open browser: {e}")
                    
                chat_history.append({"role": "user", "content": user_input})
                chat_history.append({"role": "assistant", "content": f"Opening {site} search for '{user_input}'."})
                continue
                
            # Check for initial search context start
            if user_input.lower().startswith("search "):
                site = user_input[7:].strip().lower()
                if site in ["youtube", "google", "gmail", "github", "reddit", "wikipedia"]:
                    pending_search_context = site
                    reply = f"What would you like to search on {site.capitalize()}?"
                    print(f"Aurora > {reply}")
                    chat_history.append({"role": "user", "content": user_input})
                    chat_history.append({"role": "assistant", "content": reply})
                    continue

            # Deterministic direct tool execution for exact no-arg diagnostics.
            # Deterministic direct tool execution for application discovery.
            command = user_input.lower().strip()

            if command in [
                "discover_apps",
                "discover apps",
                "list apps",
                "list installed apps",
                "what apps are installed",
                "what games are installed",
            ]:
                print("Aurora > Running application discovery audit...")

                res = registry.execute_tool("discover_apps", {})

                output = res.get("output", "")

                print(output)

                memory.save_message("assistant", output)
                state_manager.add_message("assistant", output)

                chat_history.append({"role": "user", "content": user_input})
                chat_history.append({"role": "assistant", "content": output})

                if len(chat_history) > 30:
                    chat_history = chat_history[-30:]

                continue

            print("Aurora > ", end="", flush=True)
            state_manager.update_state(status="Thinking")
            
            # Retrieve long term memories to inject into system prompt
            all_facts = memory.get_all_facts()
            if all_facts:
                memories_text = "\n".join([f"- {k}: {v}" for k, v in all_facts.items()])
            else:
                memories_text = "No long-term memories stored yet."

            is_action_request = planner._looks_like_action_request(user_input)
            
            if is_action_request:
                # Use robust non-streaming planner with truthfulness enforcement
                reply, actions = planner.create_plan(user_input, chat_history)
                print(reply)
            else:
                # Use real-time streaming for conversational requests
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
            
            reply_sanitized = sanitize_assistant_reply(reply)
            
            # Save to memory and state
            memory.save_message("assistant", reply_sanitized)
            state_manager.add_message("assistant", reply_sanitized)
            
            # Keep history buffer capped
            chat_history.append({"role": "user", "content": user_input})
            chat_history.append({"role": "assistant", "content": reply_sanitized})
            if len(chat_history) > 30:
                chat_history = chat_history[-30:]
                
            if actions:
                print("\nPlanned Actions:")
                state_manager.set_planned_actions(actions)
                for idx, act in enumerate(actions, 1):
                    tool_name = act.get("tool_name") or act.get("tool")
                    args = act.get("arguments") or act.get("args") or {}
                    
                    if not tool_name:
                        logger.error(f"Execution failed: Tool name missing from action: {act}")
                        print(f"     [!] Invalid schema: Action missing tool name. Action object: {act}")
                        continue
                        
                    print(f"\n[SCHEMA]")
                    print(f"Received Action: {act}")
                    print(f"Resolved Tool: {tool_name}")
                    print(f"Resolved Arguments: {args}\n")
                    
                    # Ignore dummy/conversational None action blocks
                    if str(tool_name).lower() in ["none", "null"]:
                        continue
                        
                    # Hook Entity Resolution Layer
                    from brain.entity_resolver import entity_resolver
                    tool_name, args = entity_resolver.resolve_entities_before_execution(tool_name, args)
                    
                    print(f"  {idx}. Resolved Action: '{tool_name}' | Arguments: {args}")
                    
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
                    
                    if tool_name == "search_files" and res.get("success"):
                        matches = res.get("data", {}).get("matches", [])
                        if matches:
                            handle_search_continuation(matches, args.get("query", ""))
                            
                    elif tool_name == "analyze_screen" and res.get("success"):
                        print(f"Aurora > ", end="", flush=True)
                        state_manager.update_state(status="Summarizing")
                        
                        sys_prompt = "You have just executed 'analyze_screen'. The system has returned the extracted active window title, process name, and OCR text. Your job is to concisely answer the user's original question based on this data. Be conversational, natural, and friendly. Do not output JSON."
                        analysis_msgs = [
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": user_input},
                            {"role": "system", "content": f"Tool Output:\n{res.get('output')}"}
                        ]
                        
                        full_analysis = ""
                        try:
                            stream = llm_client.chat(analysis_msgs, stream=True)
                            for chunk in stream:
                                full_analysis += chunk
                                sys.stdout.write(chunk)
                                sys.stdout.flush()
                            print()
                            
                            # Log the final conversational answer
                            reply_sanitized = sanitize_assistant_reply(full_analysis)
                            memory.save_message("assistant", reply_sanitized)
                            state_manager.add_message("assistant", reply_sanitized)
                            chat_history.append({"role": "assistant", "content": reply_sanitized})
                        except Exception as e:
                            print(f"\n[!] Error generating analysis: {e}")
                    
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
    
    print("Registered Tools:")
    for t_name in sorted(registry.get_all_tools().keys()):
        print(f" - {t_name}")
        
    if not verify_ollama_setup():
        sys.exit(1)
        
    run_chat_loop()

if __name__ == "__main__":
    main()
