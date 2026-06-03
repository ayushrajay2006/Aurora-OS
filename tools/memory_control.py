from tools.registry import registry, BaseTool
from memory.memory import memory
from config.logging import logger

@registry.register(
    name="remember_fact",
    description="Saves or updates a long-term preference or fact about the user or their system.",
    args_schema={
        "key": {
            "type": "string",
            "description": "The preference key (lowercase, snake_case, e.g. 'preferred_browser', 'user_name', 'favorite_game')."
        },
        "value": {
            "type": "string",
            "description": "The value of the preference (e.g. 'chrome', 'Badithe Ayush Rajay', 'sekiro')."
        }
    },
    risk_level="low"
)
class RememberFactTool(BaseTool):
    def execute(self, key: str, value: str) -> dict:
        key_clean = key.strip().lower().replace(" ", "_")
        value_clean = value.strip()
        logger.info(f"Executing remember_fact: '{key_clean}' = '{value_clean}'")
        try:
            memory.set_fact(key_clean, value_clean)
            return {
                "success": True,
                "output": f"Successfully remembered: '{key_clean}' = '{value_clean}'."
            }
        except Exception as e:
            msg = f"Failed to save memory fact '{key_clean}': {e}"
            logger.error(msg)
            return {"success": False, "output": msg}

@registry.register(
    name="forget_fact",
    description="Deletes a previously remembered fact or preference from memory.",
    args_schema={
        "key": {
            "type": "string",
            "description": "The preference key to delete (e.g. 'preferred_browser', 'favorite_game')."
        }
    },
    risk_level="low"
)
class ForgetFactTool(BaseTool):
    def execute(self, key: str) -> dict:
        key_clean = key.strip().lower().replace(" ", "_")
        logger.info(f"Executing forget_fact for key: '{key_clean}'")
        try:
            existing = memory.get_fact(key_clean)
            if not existing:
                return {
                    "success": True,
                    "output": f"Fact key '{key_clean}' was not found in memory (nothing to delete)."
                }
            memory.delete_fact(key_clean)
            return {
                "success": True,
                "output": f"Successfully forgot fact key: '{key_clean}'."
            }
        except Exception as e:
            msg = f"Failed to delete memory fact '{key_clean}': {e}"
            logger.error(msg)
            return {"success": False, "output": msg}
