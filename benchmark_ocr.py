import time
import os
import glob
import cv2
import numpy as np
import tracemalloc
import asyncio
import json

# Candidates
try:
    from rapidocr_onnxruntime import RapidOCR
    rapid_engine = RapidOCR()
except Exception as e:
    rapid_engine = None
    print(f"RapidOCR init failed: {e}")

try:
    import winsdk.windows.media.ocr as ocr
    import winsdk.windows.globalization as globalization
    from winsdk.windows.storage import StorageFile
    from winsdk.windows.graphics.imaging import BitmapDecoder
    lang = globalization.Language("en-US")
    win_engine = ocr.OcrEngine.try_create_from_language(lang)
except Exception as e:
    win_engine = None
    print(f"WinSDK init failed: {e}")

# EasyOCR (load dynamically to measure cold start)
import easyocr

def measure_easyocr(images):
    print("\n--- Testing EasyOCR ---")
    tracemalloc.start()
    t0 = time.time()
    engine = easyocr.Reader(['en'], gpu=True)
    t1 = time.time()
    cold_start = t1 - t0
    print(f"Cold Start: {cold_start:.2f}s")
    
    warm_latencies = []
    found_targets = []
    for img_path in images:
        t_start = time.time()
        result = engine.readtext(img_path)
        t_end = time.time()
        warm_latencies.append(t_end - t_start)
        
        # Check for target "File" or "Settings"
        for bbox, text, conf in result:
            if "File" in text or "Settings" in text:
                found_targets.append({"text": text, "conf": conf, "box": str(bbox)})
                break

    avg_warm = sum(warm_latencies) / len(warm_latencies) if warm_latencies else 0
    print(f"Avg Warm Latency: {avg_warm:.2f}s")
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    return {
        "engine": "EasyOCR",
        "cold_start": cold_start,
        "avg_warm": avg_warm,
        "peak_mem_mb": peak / 10**6,
        "targets_found": len(found_targets)
    }

def measure_rapidocr(images):
    print("\n--- Testing RapidOCR ---")
    if not rapid_engine: return None
    
    # Measure "cold start" of inference
    tracemalloc.start()
    t0 = time.time()
    rapid_engine(images[0])
    t1 = time.time()
    cold_start = t1 - t0
    print(f"Cold Start (First Inference): {cold_start:.2f}s")
    
    warm_latencies = []
    found_targets = []
    for img_path in images[1:]:
        t_start = time.time()
        result, _ = rapid_engine(img_path)
        t_end = time.time()
        warm_latencies.append(t_end - t_start)
        
        if result:
            for bbox, text, conf in result:
                if "File" in text or "Settings" in text:
                    found_targets.append({"text": text, "conf": conf, "box": str(bbox)})
                    break

    avg_warm = sum(warm_latencies) / len(warm_latencies) if warm_latencies else 0
    print(f"Avg Warm Latency: {avg_warm:.2f}s")
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    return {
        "engine": "RapidOCR",
        "cold_start": cold_start,
        "avg_warm": avg_warm,
        "peak_mem_mb": peak / 10**6,
        "targets_found": len(found_targets)
    }

async def measure_winsdk(images):
    print("\n--- Testing WinSDK ---")
    if not win_engine: return None
    
    tracemalloc.start()
    
    async def process(img_path):
        file = await StorageFile.get_file_from_path_async(img_path)
        stream = await file.open_async(0)
        decoder = await BitmapDecoder.create_async(stream)
        software_bitmap = await decoder.get_software_bitmap_async()
        
        t_start = time.time()
        result = await win_engine.recognize_async(software_bitmap)
        t_end = time.time()
        return result, t_end - t_start
        
    # Cold start (First Inference)
    _, cold_start = await process(images[0])
    print(f"Cold Start (First Inference): {cold_start:.2f}s")
    
    warm_latencies = []
    found_targets = []
    for img_path in images[1:]:
        result, lat = await process(img_path)
        warm_latencies.append(lat)
        
        if result and result.lines:
            for line in result.lines:
                if "File" in line.text or "Settings" in line.text:
                    found_targets.append({"text": line.text})
                    break

    avg_warm = sum(warm_latencies) / len(warm_latencies) if warm_latencies else 0
    print(f"Avg Warm Latency: {avg_warm:.2f}s")
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    return {
        "engine": "WinSDK",
        "cold_start": cold_start,
        "avg_warm": avg_warm,
        "peak_mem_mb": peak / 10**6,
        "targets_found": len(found_targets)
    }


def main():
    image_files = glob.glob(r"D:\Aurora\logs\screenshots\*.png")[:5]
    if not image_files:
        print("No images found.")
        return
        
    print(f"Benchmarking on {len(image_files)} full-screen images...")
    
    results = []
    results.append(measure_easyocr(image_files))
    results.append(measure_rapidocr(image_files))
    results.append(asyncio.run(measure_winsdk(image_files)))
    
    print("\n\n=== FINAL RESULTS ===")
    for r in results:
        if r:
            print(f"[{r['engine']}]")
            print(f"  Cold Start: {r['cold_start']:.2f}s")
            print(f"  Warm Avg:   {r['avg_warm']:.2f}s")
            print(f"  Peak Mem:   {r['peak_mem_mb']:.2f} MB")
            print(f"  Targets:    {r['targets_found']} found")

if __name__ == "__main__":
    main()
