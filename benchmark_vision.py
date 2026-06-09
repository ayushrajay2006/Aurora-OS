import time
import requests
import json
import base64
import io
from PIL import ImageGrab
import subprocess

OLLAMA_HOST = "http://127.0.0.1:11434"
MODEL = "llava:latest"

def check_ollama():
    try:
        requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        return True
    except:
        return False

def get_memory_usage():
    try:
        res = subprocess.check_output(["ollama", "ps"], text=True)
        # Parse output for qwen2.5vl
        lines = res.splitlines()
        for line in lines[1:]:
            if MODEL in line:
                parts = line.split()
                # Example: NAME ID SIZE PROCESSOR UNTIL
                # qwen2.5vl:latest ... 6.0 GB 100% GPU 5 minutes
                if len(parts) >= 3:
                    size = parts[2] + " " + parts[3]
                    processor = parts[4] if len(parts) > 4 else "Unknown"
                    return size, processor
        return "Not loaded", "Unknown"
    except:
        return "Error", "Error"

def run_benchmark():
    if not check_ollama():
        print("Ollama is not running.")
        return

    print("Capturing primary screen...")
    screenshot = ImageGrab.grab()
    
    # Compress for API
    buffered = io.BytesIO()
    screenshot.convert("RGB").save(buffered, format="JPEG", quality=75)
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    print(f"Captured image size: {len(img_str)/1024:.2f} KB (Base64)")

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": "Describe what is on this screen in 10 words or less.",
                "images": [img_str]
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.1
        }
    }

    print(f"\nSending request to {MODEL}...")
    start_time = time.time()
    
    try:
        res = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=120)
        res.raise_for_status()
        end_time = time.time()
        
        data = res.json()
        content = data.get("message", {}).get("content", "")
        latency = end_time - start_time
        
        print("\n--- BENCHMARK RESULTS ---")
        print(f"Latency: {latency:.2f} seconds")
        print(f"Output: {content}")
        
        # Check memory immediately after request while it's still loaded
        size, processor = get_memory_usage()
        print(f"Memory Allocation: {size}")
        print(f"Processor: {processor}")
        print("-------------------------")
        
    except Exception as e:
        print(f"Error during benchmark: {e}")

if __name__ == "__main__":
    run_benchmark()
