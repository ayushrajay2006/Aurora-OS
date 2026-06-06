import os
import urllib.request
import json
from typing import Dict, Any
from tools.registry import registry, BaseTool
from config.logging import logger
from memory.memory import memory
from memory.vector_db import vector_memory

@registry.register(
    name="run_diagnostics",
    description="Runs a full system health check on Aurora's backend (Ollama, Vector DB, SQLite, Internet, UI).",
    args_schema={},
    risk_level="low"
)
class RunDiagnosticsTool(BaseTool):
    def execute(self) -> dict:
        logger.info("Running full system diagnostics...")
        results = []
        all_passed = True
        
        # 1. Internet Check
        try:
            urllib.request.urlopen('http://google.com', timeout=2)
            results.append("Internet Connectivity: [PASS]")
        except:
            results.append("Internet Connectivity: [FAIL]")
            all_passed = False
            
        # 2. Ollama Check
        try:
            req = urllib.request.urlopen('http://localhost:11434/api/tags', timeout=2)
            if req.getcode() == 200:
                results.append("Ollama LLM Engine: [PASS]")
            else:
                results.append(f"Ollama LLM Engine: [FAIL] (Code {req.getcode()})")
                all_passed = False
        except:
            results.append("Ollama LLM Engine: [FAIL]")
            all_passed = False
            
        # 3. Vector DB Check
        if vector_memory.enabled:
            results.append("ChromaDB (Semantic Memory): [PASS]")
        else:
            results.append("ChromaDB (Semantic Memory): [FAIL]")
            all_passed = False
            
        # 4. SQLite DB Check
        try:
            with memory._get_connection() as conn:
                conn.execute("SELECT 1")
            results.append("SQLite (State Memory): [PASS]")
        except Exception as e:
            results.append(f"SQLite (State Memory): [FAIL] ({str(e)})")
            all_passed = False
            
        # 5. UI Control Check
        try:
            import pyautogui
            res = pyautogui.size()
            results.append(f"PyAutoGUI (Vision/Mouse Control): [PASS] ({res.width}x{res.height})")
        except Exception as e:
            results.append(f"PyAutoGUI (Vision/Mouse Control): [FAIL] ({str(e)})")
            all_passed = False
            
        output = "--- SYSTEM DIAGNOSTICS REPORT ---\n" + "\n".join(results)
        
        if all_passed:
            output += "\n\nStatus: ALL SYSTEMS NOMINAL."
        else:
            output += "\n\nStatus: WARNING. One or more subsystems failed."
            
        return {"success": True, "output": output}
