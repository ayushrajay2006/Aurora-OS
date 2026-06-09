from tools.registry import registry, BaseTool

@registry.register(
    name="ask_clarification",
    description="Internal tool to yield a structured clarification request back to the user when context resolution fails.",
    args_schema={
        "success": {"type": "boolean"},
        "requires_clarification": {"type": "boolean"},
        "output": {"type": "string"}
    },
    risk_level="low"
)
class AskClarificationTool(BaseTool):
    def execute(self, success: bool, requires_clarification: bool, output: str) -> dict:
        return {
            "success": success,
            "requires_clarification": requires_clarification,
            "output": output
        }
