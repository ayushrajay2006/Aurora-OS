from typing import Dict, Any, List
from tools.registry import registry, BaseTool
from config.logging import logger
from memory.vector_db import vector_memory

@registry.register(
    name="skill_discovery",
    description="Allows Aurora to browse or search its own brain (Vector DB) to discover what skills and macros it knows.",
    args_schema={
        "action": {
            "type": "string",
            "description": "The discovery action: 'list' (shows all skill names), 'search' (semantic search for a skill), 'describe' (gets exact instructions for a skill name).",
            "enum": ["list", "search", "describe"]
        },
        "query": {
            "type": "string",
            "description": "The search query (for 'search') or the exact skill name (for 'describe')."
        }
    },
    risk_level="low"
)
class SkillDiscoveryTool(BaseTool):
    def execute(self, action: str, query: str = "") -> dict:
        if not vector_memory.enabled:
            return {"success": False, "output": "Vector memory (ChromaDB) is disabled."}
            
        logger.info(f"SkillDiscovery: action='{action}', query='{query}'")
        
        try:
            if action == "list":
                # Get all items from the collection
                all_data = vector_memory.collection.get()
                metadatas = all_data.get("metadatas", [])
                
                if not metadatas:
                    return {"success": True, "output": "No skills currently stored in memory."}
                    
                skill_names = [m.get("skill_name", "Unknown") for m in metadatas if m]
                # Format into a nice list
                output = "--- KNOWN SKILLS ---\n" + "\n".join([f"- {s}" for s in sorted(set(skill_names))])
                return {"success": True, "output": output}
                
            elif action == "search":
                if not query:
                    return {"success": False, "output": "Must provide a 'query' to search."}
                
                results = vector_memory.search_skills(query, n_results=5)
                if not results:
                    return {"success": True, "output": f"No skills found matching '{query}'."}
                    
                output = f"--- SEARCH RESULTS FOR '{query}' ---\n" + "\n\n".join(results)
                return {"success": True, "output": output}
                
            elif action == "describe":
                if not query:
                    return {"success": False, "output": "Must provide the exact skill 'query' to describe."}
                    
                # Exact match query via metadata
                results = vector_memory.collection.get(where={"skill_name": query})
                documents = results.get("documents", [])
                
                if not documents:
                    return {"success": False, "output": f"Skill '{query}' not found. Use 'list' to see available skills."}
                    
                return {"success": True, "output": documents[0]}
                
            else:
                return {"success": False, "output": f"Unknown action '{action}'."}
                
        except Exception as e:
            logger.error(f"SkillDiscovery failed: {e}")
            return {"success": False, "output": f"Failed to discover skills: {e}"}
