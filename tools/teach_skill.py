from typing import Dict, Any
from tools.base import BaseTool
from memory.vector_db import vector_memory

class TeachSkillTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="teach_skill",
            description="Use this tool to permanently learn a new skill, keyboard shortcut, or software instruction based on the user's advice. Do not use this for personal facts (use remember_fact for that).",
            args_schema={
                "skill_name": "A short, descriptive name for the skill (e.g. 'maximize_window', 'clear_cache_chrome')",
                "instructions": "The exact step-by-step instructions or shortcut keys to execute the skill."
            },
            risk_level="low"
        )

    def execute(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        if not vector_memory.enabled:
            return {"success": False, "output": "Vector memory is disabled because ChromaDB is not installed."}
            
        skill_name = kwargs.get("skill_name")
        instructions = kwargs.get("instructions")
        
        if not skill_name or not instructions:
            return {"success": False, "output": "Missing skill_name or instructions."}
            
        success = vector_memory.teach_skill(skill_name, instructions)
        if success:
            return {"success": True, "output": f"Successfully embedded skill '{skill_name}' into Vector Memory."}
        else:
            return {"success": False, "output": f"Failed to embed skill '{skill_name}'."}
