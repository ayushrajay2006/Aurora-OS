from tools.registry import registry, BaseTool

@registry.register(
    name="open_website",
    description="Launches a website URL in the default browser.",
    args_schema={
        "url": {
            "type": "string",
            "description": "The website URL or shortcut name to open (e.g., https://youtube.com, gmail)"
        }
    },
    risk_level="medium"
)
class OpenWebsiteTool(BaseTool):
    def execute(self, url: str) -> dict:
        # Stub to be fully implemented in Phase 3
        return {"success": True, "output": f"Stub: request to open website '{url}' received."}
