from tools.registry import registry
from brain.task_manager import task_manager

@registry.register(
    name="check_task_queue",
    description="Check the current status of background tasks, including running and queued tasks.",
    args_schema={},
    risk_level="low"
)
def check_task_queue(**kwargs):
    active = task_manager.get_active_task()
    queued = task_manager.get_queued_tasks()
    
    if not active and not queued:
        return {"success": True, "output": "No tasks are currently running or queued."}
        
    lines = []
    if active:
        lines.append(f"Currently Running Task:")
        lines.append(f"- ID: {active.task_id} | Tool: {active.tool_call.tool_name} | Status: {active.status} | Attempts: {active.attempts}")
        
    if queued:
        lines.append(f"\nQueued Tasks ({len(queued)}):")
        for i, t in enumerate(queued, 1):
            lines.append(f"{i}. ID: {t.task_id} | Tool: {t.tool_call.tool_name}")
            
    return {"success": True, "output": "\n".join(lines)}
