import os
import sys
import time
import json
import statistics
import psutil
import pygetwindow as gw
from typing import Dict, List, Any

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vision.screenshot_service import screenshot_service
from vision.ocr_service import ocr_service
from vision.window_classifier import window_classifier

AUDIT_RESULTS_FILE = "vision_audit_results.json"

def get_system_metrics() -> tuple[float, float]:
    process = psutil.Process()
    ram_mb = process.memory_info().rss / (1024 * 1024)
    cpu_percent = process.cpu_percent(interval=0.1)
    return ram_mb, cpu_percent

def run_vision_cycle() -> Dict[str, Any]:
    metrics = {}
    ram_before, cpu_before = get_system_metrics()
    metrics["ram_before_mb"] = ram_before
    
    t0 = time.perf_counter()
    window_info = window_classifier.get_active_window_info()
    img_path = screenshot_service.capture_active_window()
    t1 = time.perf_counter()
    metrics["capture_time"] = t1 - t0
    
    t2 = time.perf_counter()
    ocr_results = []
    if img_path:
        ocr_results = ocr_service.extract_text(img_path)
    t3 = time.perf_counter()
    metrics["ocr_time"] = t3 - t2
    
    ram_after, cpu_during = get_system_metrics()
    metrics["ram_after_mb"] = ram_after
    metrics["cpu_during"] = cpu_during
    
    total_chars = sum(len(item["text"]) for item in ocr_results)
    avg_conf = statistics.mean([item["confidence"] for item in ocr_results]) if ocr_results else 0.0
    
    metrics["window_title"] = window_info.get("title", "")
    metrics["process_name"] = window_info.get("process_name", "")
    metrics["ocr_char_count"] = total_chars
    metrics["ocr_avg_confidence"] = avg_conf
    metrics["total_latency"] = metrics["capture_time"] + metrics["ocr_time"]
    metrics["pass"] = bool(metrics["window_title"] or total_chars > 0)
    
    return metrics

def force_focus(title_substring: str) -> bool:
    try:
        windows = gw.getWindowsWithTitle(title_substring)
        if windows:
            win = windows[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(2)
            return True
    except Exception as e:
        print(f"Failed to focus {title_substring}: {e}")
    return False

def audit_target(name: str, window_title: str) -> Dict[str, Any]:
    print(f"\n{'='*50}\nTesting Target: {name}\n{'='*50}")
    
    if not force_focus(window_title):
        print(f"Skipping {name} - Could not find/focus window with '{window_title}'")
        return None
        
    runs = []
    for i in range(5):
        print(f"  Run {i+1}/5...")
        time.sleep(1)
        res = run_vision_cycle()
        runs.append(res)
        
    latencies = [r["total_latency"] for r in runs]
    avg_latency = statistics.mean(latencies)
    best_latency = min(latencies)
    worst_latency = max(latencies)
    std_dev = statistics.stdev(latencies) if len(latencies) > 1 else 0.0
    
    avg_conf = statistics.mean([r["ocr_avg_confidence"] for r in runs])
    avg_chars = statistics.mean([r["ocr_char_count"] for r in runs])
    passes = sum(1 for r in runs if r["pass"])
    
    print(f"\n--- Results for {name} ---")
    print(f"Avg Latency: {avg_latency:.2f}s (Best: {best_latency:.2f}s, Worst: {worst_latency:.2f}s, StdDev: {std_dev:.2f}s)")
    print(f"Avg Confidence: {avg_conf:.2f}")
    
    return {
        "target": name,
        "runs": runs,
        "aggregated": {
            "avg_latency": avg_latency,
            "best_latency": best_latency,
            "worst_latency": worst_latency,
            "std_dev_latency": std_dev,
            "avg_confidence": avg_conf,
            "avg_chars": avg_chars,
            "passes": passes,
            "sample_title": runs[0]["window_title"],
            "sample_process": runs[0]["process_name"]
        }
    }

def main():
    print("Pre-loading EasyOCR Model...")
    ocr_service._lazy_load()
    
    targets = {
        "Notepad": "Notepad",
        "VS Code": "Antigravity IDE",
        "Discord": "Discord",
        "Steam": "Steam",
        "YouTube": "YouTube", # Assumes YouTube is open in a browser tab
        "GitHub": "GitHub", # Assumes GitHub is open in a browser tab
        "Gmail": "Gmail",
        "God of War": "God of War",
        "Palworld": "Pal"
    }
    
    results = {}
    for name, title in targets.items():
        res = audit_target(name, title)
        if res:
            results[name] = res
            
    with open(AUDIT_RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nAudit complete! Results saved to {AUDIT_RESULTS_FILE}")

if __name__ == "__main__":
    main()
