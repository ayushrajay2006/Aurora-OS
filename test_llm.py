import sys
import os
import time
from typing import List, Dict, Any

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from brain.llm import llm_client
from brain.planner import planner

# Ensure all tools are registered!
from main import import_tool_modules
import_tool_modules()

def test_prompt(user_input: str):
    print(f"\n[{time.strftime('%H:%M:%S')}] TESTING PROMPT: {user_input}")
    print("-" * 50)
    
    chat_history = [{"role": "user", "content": user_input}]
    
    try:
        # Build prompt using exact logic from main.py
        from brain.planner import SYSTEM_PROMPT_TEMPLATE
        tools_schema = planner._get_tools_schema_text()
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            tools_schema_text=tools_schema,
            memories_text="No memories.",
            knowledge_text=""
        )
        
        # Message list for this step
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(chat_history)
        
        # Query the LLM
        print("Querying LLM (waiting for response)...")
        start_time = time.time()
        
        full_text = ""
        stream = llm_client.chat(messages, stream=True)
        for chunk in stream:
            full_text += chunk
            print(chunk, end="", flush=True)
            
        print(f"\n\n[Finished in {time.time() - start_time:.2f}s]")
        print("-" * 50)
        
        # Parse the response
        reply, actions, speech_text = planner.parse_response(full_text)
        print("PARSED REPLY:", reply.strip() if reply else "None")
        print("PARSED SPEECH:", speech_text)
        print("PARSED ACTIONS:")
        if not actions:
            print("  None")
        for act in actions:
            print(f"  - Tool: {act.get('tool')} | Args: {act.get('args')}")
            
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    test_prompts = [
        # Phase A - CORE REASONING
        "Show me all developer skills.",
        # Phase D - SELF DIAGNOSTICS
        "Run diagnostics.",
        # Phase E - FILE MANAGEMENT
        "Create folder AuroraTest",
        # Phase L - DEVELOPER MODE
        "Create Python virtual environment."
    ]
    
    if len(sys.argv) > 1:
        test_prompt(sys.argv[1])
    else:
        with open("test_results.log", "w", encoding="utf-8") as f:
            f.write("--- AUTOMATED LLM ACCEPTANCE SUITE ---\n\n")
            
        for prompt in test_prompts:
            try:
                # Redirect print to capture output
                import io
                from contextlib import redirect_stdout
                f_stream = io.StringIO()
                with redirect_stdout(f_stream):
                    test_prompt(prompt)
                
                output = f_stream.getvalue()
                print(f"[SUCCESS] Completed test: {prompt[:30]}...")
                with open("test_results.log", "a", encoding="utf-8") as f:
                    f.write(output + "\n\n")
            except Exception as e:
                print(f"[FAIL] Failed test: {prompt} - {e}")
