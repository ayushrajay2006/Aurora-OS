import os
from aurora.config import config
from aurora.state import state_manager
from aurora.logging import logger

def test_phase1():
    print("--- VERIFYING PHASE 1: FOUNDATION & CORE PACKAGES ---")
    
    # 1. Test Configuration loading
    print(f"Ollama Host: {config.ollama_host}")
    print(f"Model Name: {config.model_name}")
    print(f"Logs Directory: {config.logs_dir}")
    print(f"Log File Path: {config.log_file_path}")
    print("Config loading: SUCCESS.")
    
    # 2. Test Logging
    logger.info("Initializing Phase 1 validation test.")
    logger.debug("Debug logs will write to file but not state_manager.")
    logger.warning("Testing warning pipe to StateManager.")
    
    # Verify that logs were written to the logs folder
    if os.path.exists(config.log_file_path):
        print(f"Log file exists at {config.log_file_path}: SUCCESS.")
    else:
        print("Log file missing: FAILED.")
        
    # 3. Test State Management (thread-safety & callbacks)
    state_updates = []
    def state_callback(state):
        state_updates.append(state.status)
        
    state_manager.register_callback(state_callback)
    
    # Update state
    state_manager.update_state(status="Validating Core Modules", model_name="qwen2.5:14b")
    state_manager.add_message("user", "Hello Aurora")
    state_manager.add_message("assistant", "Hello! State system is operational.")
    
    current_state = state_manager.get_state()
    print(f"Current State Status: {current_state.status}")
    print(f"Last State Callback Status Received: {state_updates[-1] if state_updates else 'None'}")
    
    # Check messages
    print(f"Messages count: {len(current_state.messages)}")
    for msg in current_state.messages:
        print(f"  [{msg['role']}]: {msg['content']}")
        
    # Check if StateLogHandler captured the logger.warning/logger.info
    print("Tool logs captured by state_manager:")
    for log in current_state.tool_logs:
        print(f"  {log}")
        
    # Verify that logs contains warning and info but not debug
    has_warning = any("warning" in log.lower() for log in current_state.tool_logs)
    has_debug = any("debug" in log.lower() for log in current_state.tool_logs)
    
    print(f"State log piping works (contains warning): {has_warning}")
    print(f"State log filtering works (excludes debug): {not has_debug}")
    
    if len(current_state.messages) == 2 and has_warning and not has_debug:
        print("\n--- PHASE 1 SYSTEM DIAGNOSTICS: ALL TESTS PASSED ---")
    else:
        print("\n--- PHASE 1 SYSTEM DIAGNOSTICS: FAILURES DETECTED ---")

if __name__ == "__main__":
    test_phase1()
