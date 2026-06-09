import os
import json
from tools.registry import registry, BaseTool
from config.logging import logger
from brain.app_resolver import app_resolver

@registry.register(
    name="discover_apps",
    description="Diagnostic command that dumps all applications visible to the resolver.",
    args_schema={},
    risk_level="low"
)
class DiscoverAppsTool(BaseTool):
    def execute(self) -> dict:
        output_lines = []
        output_lines.append("=== Aurora Application Discovery Audit ===")
        
        # 1. Cached Applications
        output_lines.append("\n[Cached Applications]")
        for name, path in app_resolver.cache.items():
            output_lines.append(f" - {name} -> {path}")
            
        # 2. Start Menu Apps
        output_lines.append("\n[Start Menu]")
        for name, path in app_resolver.scan_start_menu().items():
            output_lines.append(f" - {name} -> {path}")
            
        # 3. Steam Games
        output_lines.append("\n[Steam Games]")
        for name, path in app_resolver.scan_steam_games().items():
            output_lines.append(f" - {name} -> {path}")
            
        # 4. Epic Games
        output_lines.append("\n[Epic Games]")
        for name, path in app_resolver.scan_epic_games().items():
            output_lines.append(f" - {name} -> {path}")
            
        # 5. UWP / Xbox Apps
        output_lines.append("\n[UWP / Xbox Apps]")
        if hasattr(app_resolver, 'scan_start_apps'):
            for name, path in app_resolver.scan_start_apps().items():
                output_lines.append(f" - {name} -> {path}")
        else:
            output_lines.append(" - (Get-StartApps scanning not implemented yet)")

        output_text = "\n".join(output_lines)
        
        try:
            report_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "APPLICATION_DISCOVERY_REPORT.md")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(output_text)
            logger.info(f"Discovery audit completed. Saved to {report_path}")
        except Exception as e:
            logger.error(f"Failed to write report: {e}")

        return {"success": True, "output": output_text}
