import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def run_tests():
    print("=== PHASE 1: Loading Dependencies & Tool Registry ===")
    try:
        import main
        main.import_tool_modules()
        from tools.registry import registry
        tools = registry.get_tool_schemas()
        print(f"Loaded {len(tools)} tools successfully.")
    except Exception as e:
        print(f"FAILED Phase 1: {e}")
        return

    print("\n=== PHASE 2: Database Initialization (SQLite & Vector) ===")
    try:
        from memory.memory import memory
        from memory.vector_db import vector_memory
        facts = memory.get_all_facts()
        print("SQLite memory OK.")
        res = vector_memory.search_skills("test", n_results=1)
        print("Vector DB search OK.")
    except Exception as e:
        print(f"FAILED Phase 2: {e}")
        return

    print("\n=== PHASE 3: Planner Parsing Engine ===")
    try:
        from brain.planner import planner
        
        # Test 1: Standard Markdown
        t1 = "```json\n[{\"tool\": \"open_app\", \"args\": {\"app_name\": \"test\"}}]\n```"
        _, a1, _, _ = planner.parse_response(t1)
        assert len(a1) == 1 and a1[0]["tool"] == "open_app", "Markdown parse failed"
        
        # Test 2: Custom XML tags
        t2 = "<json>[{\"name\": \"open_app\", \"args\": {\"app_name\": \"test\"}}]</json>"
        _, a2, _, _ = planner.parse_response(t2)
        assert len(a2) == 1 and a2[0]["tool"] == "open_app", "XML parse failed"
        
        # Test 3: Raw Dictionary missing array
        t3 = "{\n\"tool\": \"open_app\", \"args\": {\"app_name\": \"test\"}\n}"
        _, a3, _, _ = planner.parse_response(t3)
        assert len(a3) == 1 and a3[0]["tool"] == "open_app", "Raw dict parse failed"
        
        print("Planner parsing engine OK.")
    except Exception as e:
        print(f"FAILED Phase 3: {e}")
        return
        
    print("\n=== PHASE 4: Voice Control Engine Initialization ===")
    try:
        from brain.voice_control import TextToSpeechManager, SpeechToTextManager
        tts = TextToSpeechManager()
        stt = SpeechToTextManager()
        print("Voice engine modules loaded OK.")
    except Exception as e:
        print(f"FAILED Phase 4: {e}")
        return

    print("\n=== ALL PHASES PASSED ===")

if __name__ == "__main__":
    run_tests()
