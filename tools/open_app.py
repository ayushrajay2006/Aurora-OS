from tools.registry import registry, BaseTool

@registry.register(
    name="open_app",
    description="Opens a Windows application by name.",
    args_schema={
        "app_name": {
            "type": "string",
            "description": "Name of the application to launch (e.g., chrome, notepad, discord, vscode)"
        }
    },
    risk_level="medium"
)
class OpenAppTool(BaseTool):
    def execute(self, app_name: str) -> dict:
        # Stub to be fully implemented in Phase 2
        return {"success": True, "output": f"Stub: request to open app '{app_name}' received."}
