import threading
import time
from typing import Dict, Any
from config.logging import logger
from config.event_bus import event_bus
from brain.task_manager import task_manager
from tools.registry import registry
from brain.verification import verifier
from memory.memory import memory
from brain.planner import planner

ALLOW_SELF_HEALING = {
    "search_files",
    "open_app",
    "open_website",
    "web_search",
    "read_pdf",
    "summarize_file"
}

class ExecutionWorker:
    def __init__(self):
        self._running = True
        self._worker_thread = threading.Thread(target=self._run_loop, daemon=True, name="ExecutionWorker")
        self._worker_thread.start()

    def _run_loop(self):
        logger.info("ExecutionWorker started.")
        while self._running:
            try:
                task = task_manager.get_next_task()
                if not task:
                    continue
                
                tool_name = task.tool_call.tool_name
                args = task.tool_call.arguments
                
                task_manager.update_task_status(task.task_id, "started")
                event_bus.publish("task_started", task_id=task.task_id, tool_name=tool_name, args=args)
                
                MAX_RECOVERY = 2
                attempts = 0
                final_success = False
                final_output = ""
                
                while attempts <= MAX_RECOVERY and not final_success:
                    attempts += 1
                    task_manager.update_task_status(task.task_id, "executing", attempts=attempts)
                    
                    try:
                        res = registry.execute_tool(tool_name, args)
                        success = res.get("success", False)
                        output = res.get("output", "")
                    except Exception as e:
                        logger.error(f"Worker tool '{tool_name}' crashed: {e}", exc_info=True)
                        success = False
                        output = f"Critical tool execution error: {e}"
                        
                    task_manager.update_task_status(task.task_id, "verifying")
                    event_bus.publish("task_verifying", task_id=task.task_id, tool_name=tool_name)
                    
                    verify_res = verifier.verify(tool_name, args, output)
                    
                    if verify_res.success:
                        final_success = True
                        final_output = output
                        task_manager.update_task_status(task.task_id, "completed", verification_result=verify_res)
                        break
                    else:
                        if attempts <= MAX_RECOVERY:
                            task_manager.update_task_status(task.task_id, "recovering")
                            event_bus.publish("task_recovering", task_id=task.task_id, tool_name=tool_name, attempt=attempts)
                            
                            # Phase 5: Self-Healing Suggestion logic
                            if tool_name in ALLOW_SELF_HEALING:
                                logger.info(f"Task '{task.task_id}' failed. Requesting self-healing recovery plan...")
                                recovery_tool_call = planner.create_recovery_plan(tool_name, args, verify_res.evidence)
                                
                                if recovery_tool_call and recovery_tool_call.get("tool"):
                                    tool_name = recovery_tool_call.get("tool")
                                    args = recovery_tool_call.get("args", {})
                                    logger.info(f"Self-healing generated new task target: {tool_name} with args {args}")
                                    memory.update_action(task.task_id, f"recovery_attempt_{attempts}", {"output": f"Recovering to {tool_name}"})
                                else:
                                    logger.warning("Recovery aborted by planner.")
                                    task_manager.update_task_status(task.task_id, "failed", verification_result=verify_res)
                                    final_output = f"Execution returned: '{output}'. Verification failed: {verify_res.evidence}. Recovery aborted."
                                    break
                            else:
                                logger.info(f"Tool '{tool_name}' not in self-healing allowlist. Aborting.")
                                task_manager.update_task_status(task.task_id, "failed", verification_result=verify_res)
                                final_output = f"Execution returned: '{output}'. Verification failed: {verify_res.evidence}."
                                break
                            
                            time.sleep(1)
                        else:
                            task_manager.update_task_status(task.task_id, "failed", verification_result=verify_res)
                            final_output = f"Execution returned: '{output}'. Goal Verification failed: {verify_res.evidence}"
                
                # Log action to memory
                memory.update_action(task.task_id, "success" if final_success else "failed", {"success": final_success, "output": final_output})
                
                if final_success:
                    event_bus.publish("task_completed", task_id=task.task_id, tool_name=tool_name, output=final_output, confidence=verify_res.confidence if verify_res else 1.0)
                else:
                    event_bus.publish("task_failed", task_id=task.task_id, tool_name=tool_name, error=final_output, confidence=verify_res.confidence if verify_res else 0.0)
                    
                task_manager.mark_task_done()
                
            except Exception as e:
                logger.error(f"ExecutionWorker encountered error: {e}", exc_info=True)

    def shutdown(self):
        self._running = False
        self._worker_thread.join(timeout=2.0)

# Global singleton
execution_worker = ExecutionWorker()
