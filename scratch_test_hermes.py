import sys
import os
import time

sys.path.insert(0, os.path.abspath("."))

from config.config import config
from main import execute_assistant_turn

def test_aurora():
    print(f"Current Model in Config: {config.model_name}")
    chat_history = []
    
    user_prompt = "open edge and search for youtube"
    print(f"\n=== Testing Prompt: '{user_prompt}' ===")
    
    start_time = time.time()
    
    try:
        reply = execute_assistant_turn(user_prompt, chat_history, None, False, None)
    except Exception as e:
        print(f"Error during execution: {e}")
        reply = "Execution failed."
        
    end_time = time.time()
    
    print(f"\n=== Final Reply ===")
    print(reply)
    print(f"=== Total Turn Time: {end_time - start_time:.2f} seconds ===")
    
    print("\n=== Chat History State ===")
    for msg in chat_history[-3:]:
        print(f"{msg['role']}: {msg['content'][:200]}...")

if __name__ == "__main__":
    test_aurora()
