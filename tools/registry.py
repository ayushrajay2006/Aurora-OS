from typing import Dict, Any, List, Callable, Optional, Type
import logging
from config.logging import logger

class BaseTool:
    name: str = ""
    description: str = ""
    args_schema: Dict[str, Any] = {}
    risk_level: str = "low" # "low", "medium", "high"

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Executes the tool with given arguments.
        Should return a dictionary with at least 'success' (bool) and 'output' (str) keys.
        """
        raise NotImplementedError("Each tool must implement its execute method.")

    def get_schema(self) -> Dict[str, Any]:
        """Returns tool schema for LLM model prompt ingestion."""
        return {
            "name": self.name,
            "description": self.description,
            "args_schema": self.args_schema,
            "risk_level": self.risk_level
        }

class FunctionTool(BaseTool):
    """Wraps standard decorated python functions into the BaseTool structure."""
    def __init__(self, func: Callable, name: str, description: str, args_schema: Dict[str, Any] = None, risk_level: str = "low"):
        self.func = func
        self.name = name
        self.description = description
        self.args_schema = args_schema or {}
        self.risk_level = risk_level

    def execute(self, **kwargs) -> Dict[str, Any]:
        try:
            res = self.func(**kwargs)
            if isinstance(res, dict) and "success" in res and "output" in res:
                return res
            return {"success": True, "output": str(res)}
        except Exception as e:
            logger.error(f"Error executing tool '{self.name}': {e}", exc_info=True)
            return {"success": False, "output": f"Error running tool '{self.name}': {str(e)}"}

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, name: str, description: str, args_schema: Dict[str, Any] = None, risk_level: str = "low"):
        """Decorator to register a tool class or simple function."""
        def decorator(item):
            # Case 1: Item is a class inheriting from BaseTool
            if isinstance(item, type) and issubclass(item, BaseTool):
                tool_instance = item()
                # Override parameters if provided in decorator
                if name: tool_instance.name = name
                if description: tool_instance.description = description
                if args_schema: tool_instance.args_schema = args_schema
                if risk_level: tool_instance.risk_level = risk_level
                
                self._tools[tool_instance.name] = tool_instance
                logger.debug(f"Registered class tool: {tool_instance.name}")
                return item
            
            # Case 2: Item is a standard python function
            elif callable(item):
                func_tool = FunctionTool(item, name, description, args_schema, risk_level)
                self._tools[name] = func_tool
                logger.debug(f"Registered function tool: {name}")
                return item
            
            else:
                raise TypeError("Only classes inheriting from BaseTool or callables can be registered as tools.")
        return decorator

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [tool.get_schema() for tool in self.list_tools()]

    def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Looks up and executes a tool by name with arguments."""
        tool = self.get_tool(name)
        if not tool:
            logger.error(f"Execution failed: Tool '{name}' not found in registry.")
            return {"success": False, "output": f"Tool '{name}' not found."}
        
        logger.info(f"Executing tool '{name}' with args: {args}")
        try:
            return tool.execute(**args)
        except Exception as e:
            logger.error(f"Uncaught exception running tool '{name}': {e}", exc_info=True)
            return {"success": False, "output": f"Uncaught exception running tool: {str(e)}"}

# Global tool registry instance
registry = ToolRegistry()
