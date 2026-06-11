import time
import statistics
import re
from tools.registry import registry
import tools.open_app
import tools.click_ui_element

def parse_breakdown(output_str: str) -> dict:
    metrics = {
        "screenshot_time": 0.0,
        "ocr_lookup_time": 0.0,
        "ocr_preprocessing_time": 0.0,
        "ocr_inference_time": 0.0,
        "match_time": 0.0,
        "move_time": 0.0,
        "click_time": 0.0,
        "verify_time": 0.0,
        "total_time": 0.0,
        "ocr_cached": False
    }
    
    match = re.search(r"Screenshot Capture:\s*([\d.]+)", output_str)
    if match: metrics["screenshot_time"] = float(match.group(1))
    
    match = re.search(r"OCR Cache Lookup:\s*([\d.]+)", output_str)
    if match: metrics["ocr_lookup_time"] = float(match.group(1))
    
    match = re.search(r"OCR Preprocessing:\s*([\d.]+)", output_str)
    if match: metrics["ocr_preprocessing_time"] = float(match.group(1))
    
    match = re.search(r"OCR Inference:\s*([\d.]+)", output_str)
    if match: metrics["ocr_inference_time"] = float(match.group(1))
    
    match = re.search(r"Text Matching:\s*([\d.]+)", output_str)
    if match: metrics["match_time"] = float(match.group(1))
    
    match = re.search(r"Mouse Movement:\s*([\d.]+)", output_str)
    if match: metrics["move_time"] = float(match.group(1))
    
    match = re.search(r"Click Execution:\s*([\d.]+)", output_str)
    if match: metrics["click_time"] = float(match.group(1))
    
    match = re.search(r"Verification:\s*([\d.]+)", output_str)
    if match: metrics["verify_time"] = float(match.group(1))
    
    match = re.search(r"Total Execution Time:\s*([\d.]+)", output_str)
    if match: metrics["total_time"] = float(match.group(1))
    
    match = re.search(r"OCR Cached:\s*(True|False)", output_str)
    if match: metrics["ocr_cached"] = (match.group(1) == "True")
    
    return metrics

def run_suite():
    # Minimize console window to prevent background scrolling from invalidating OCR cache via drop shadows
    import win32gui, win32con
    hwnd = win32gui.GetForegroundWindow()
    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    time.sleep(1)
    
    test_cases = [
        {"app": "notepad", "text": "File", "roi": ""},
        {"app": "notepad", "text": "New Window", "roi": ""},
        {"app": "edge", "text": "Chat", "roi": ""},
        {"app": "edge", "text": "Settings", "roi": ""},
        {"app": "code", "text": "Explorer", "roi": ""}
    ]
    
    all_results = {}
    
    for case in test_cases:
        app_name = case["app"]
        target_text = case["text"]
        roi = case["roi"]
        
        print(f"\n========================================")
        print(f"BENCHMARK: {app_name} -> '{target_text}' (ROI: {roi or 'Full'})")
        print(f"========================================")
        
        # 1. Setup / Launch App
        print(f"[*] Launching {app_name}...")
        registry.execute_tool("open_app", {"app_name": app_name})
        time.sleep(2.0) # Let it settle
        
        # 2. Warm-up runs (3)
        print(f"[*] Executing 3 Warm-up runs...")
        cold_start_latencies = []
        for w in range(3):
            t_start = time.time()
            res = registry.execute_tool("click_ui_element", {"text": target_text, "roi_ratio": roi, "threshold": 0.3})
            t_end = time.time()
            if not res.get("success"):
                print(f"  [Warm-up {w+1}] FAILED: {res.get('output')}")
            else:
                latency = (t_end - t_start) * 1000.0
                cold_start_latencies.append(latency)
                print(f"  [Warm-up {w+1}] SUCCESS: {latency:.2f} ms")
        
        # 3. Measured runs (10)
        print(f"[*] Executing 10 Measured runs...")
        run_metrics = []
        for m in range(10):
            res = registry.execute_tool("click_ui_element", {"text": target_text, "roi_ratio": roi, "threshold": 0.3})
            if res.get("success"):
                metrics = parse_breakdown(res["output"])
                run_metrics.append(metrics)
                print(f"  [Run {m+1}] SUCCESS: {metrics['total_time']:.2f} ms")
            else:
                print(f"  [Run {m+1}] FAILED: {res.get('output')}")
        
        # Calculate stats
        if run_metrics:
            totals = [rm["total_time"] for rm in run_metrics]
            avg_total = sum(totals) / len(totals)
            
            # Averages for components
            avg_screenshot = sum([rm["screenshot_time"] for rm in run_metrics]) / len(run_metrics)
            avg_lookup = sum([rm["ocr_lookup_time"] for rm in run_metrics]) / len(run_metrics)
            avg_ocr_prep = sum([rm["ocr_preprocessing_time"] for rm in run_metrics]) / len(run_metrics)
            avg_ocr_inf = sum([rm["ocr_inference_time"] for rm in run_metrics]) / len(run_metrics)
            avg_match = sum([rm["match_time"] for rm in run_metrics]) / len(run_metrics)
            avg_move = sum([rm["move_time"] for rm in run_metrics]) / len(run_metrics)
            avg_click = sum([rm["click_time"] for rm in run_metrics]) / len(run_metrics)
            avg_verify = sum([rm["verify_time"] for rm in run_metrics]) / len(run_metrics)
            
            hits = sum([1 for rm in run_metrics if rm["ocr_cached"]])
            hit_rate = hits / len(run_metrics)
            
            cold_latency = cold_start_latencies[0] if cold_start_latencies else 0.0
            ratio = cold_latency / avg_total if avg_total > 0 else 0.0
            
            all_results[f"{app_name}->{target_text}"] = {
                "min": min(totals),
                "max": max(totals),
                "avg": avg_total,
                "stddev": statistics.stdev(totals) if len(totals) > 1 else 0.0,
                "cold_start": cold_latency,
                "ratio": ratio,
                "hit_rate": hit_rate,
                "components": {
                    "screenshot": avg_screenshot,
                    "lookup": avg_lookup,
                    "ocr_prep": avg_ocr_prep,
                    "ocr_inf": avg_ocr_inf,
                    "match": avg_match,
                    "move": avg_move,
                    "click": avg_click,
                    "verify": avg_verify
                }
            }
            
            print(f"\n[Stats] Avg: {avg_total:.2f} ms | Min: {min(totals):.2f} ms | Max: {max(totals):.2f} ms")
            print(f"[Stats] Cold Start: {cold_latency:.2f} ms | Ratio: {ratio:.2f}x | Hit Rate: {hit_rate*100:.1f}%")
            
    # Remove ROI Experiment logic as it is now integrated natively into click_ui_element
    import json
    with open("benchmark_results.json", "w") as f:
        json.dump(all_results, f, indent=4)
        
    print("\nBenchmark Suite Completed! Results saved to benchmark_results.json")

if __name__ == "__main__":
    run_suite()
