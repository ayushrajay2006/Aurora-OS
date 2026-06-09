import time
from tools.analyze_screen import tool_instance as analyze_screen

def test_screen_analysis():
    print("Capturing and analyzing current screen...")
    
    start_time = time.time()
    result = analyze_screen.execute()
    end_time = time.time()
    
    print("\n--- SCREEN ANALYSIS RESULT ---")
    print(f"Latency: {end_time - start_time:.2f} seconds")
    if result["success"]:
        print("\nMetadata Output:")
        print("----------------")
        print(result["output"])
        print("----------------")
    else:
        print("Failed to analyze screen.")
        print(result.get("output", ""))

if __name__ == "__main__":
    test_screen_analysis()
