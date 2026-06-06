import sqlite3
import os
from typing import Dict, Any, List
from tools.registry import registry, BaseTool
from config.logging import logger
from memory.memory import memory

@registry.register(
    name="action_history",
    description="Queries Aurora's historical action log to reflect on past actions, find failed tools, or summarize recent activity.",
    args_schema={
        "query_type": {
            "type": "string",
            "description": "The type of query: 'recent' (last N actions), 'failed' (recent failed actions).",
            "enum": ["recent", "failed"]
        },
        "limit": {
            "type": "integer",
            "description": "Number of actions to return (default 5, max 20)."
        }
    },
    risk_level="low"
)
class ActionHistoryTool(BaseTool):
    def execute(self, query_type: str = "recent", limit: int = 5) -> dict:
        limit = min(max(1, limit), 20)
        logger.info(f"ActionHistory: Querying '{query_type}' with limit {limit}")
        
        try:
            with memory._get_connection() as conn:
                cursor = conn.cursor()
                if query_type == "failed":
                    cursor.execute(
                        "SELECT timestamp, tool_name, args, status, result FROM action_history WHERE status = 'error' OR status = 'failed' ORDER BY timestamp DESC LIMIT ?",
                        (limit,)
                    )
                else:
                    cursor.execute(
                        "SELECT timestamp, tool_name, args, status, result FROM action_history ORDER BY timestamp DESC LIMIT ?",
                        (limit,)
                    )
                
                rows = cursor.fetchall()
                if not rows:
                    return {"success": True, "output": f"No {query_type} actions found."}
                
                output = f"--- {query_type.upper()} ACTION HISTORY ---\n"
                for i, row in enumerate(rows, 1):
                    output += f"{i}. [{row['timestamp']}] Tool: {row['tool_name']} | Status: {row['status']}\n"
                    output += f"   Args: {row['args']}\n"
                    output += f"   Result: {str(row['result'])[:200]}...\n"
                
                return {"success": True, "output": output}
                
        except Exception as e:
            logger.error(f"ActionHistory failed: {e}")
            return {"success": False, "output": f"Failed to retrieve action history: {e}"}
