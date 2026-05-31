import json
import re
from typing import List, Dict, Any, Tuple
from tools.registry import registry
from brain.llm import llm_client
from config.logging import logger

SYSTEM_PROMPT_TEMPLATE = """You are Aurora, an advanced, local-first personal operating system assistant for Windows, inspired by the beauty and intelligence of the Aurora Borealis.

Your goal is to help the user control their PC, manage files, open applications, search the web, and answer questions.

You have access to a suite of system tools. To call tools, you MUST format your response with a structured JSON actions block wrapped inside a markdown code block.

Available Tools:
{tools_schema_text}

Execution Rules:
1. Identify if the user's intent requires running any of the available tools.
2. If tools are required, write a markdown JSON code block containing an array of tool calls.
Example response structure when calling tools:
Let me open Notepad for you.
```json
[
  {{
    "tool": "open_app",
    "args": {{
      "app_name": "notepad"
    }}
  }}
]
```
3. If multiple actions are requested, you can list multiple tools in the array. They will execute sequentially.
4. If no tools are required, simply reply conversationally. Do not include any JSON blocks.
5. Always be direct, precise, and transparent about what actions you are planning.
6. To open specific Windows system folders or directories (such as the Recycle Bin, Downloads, Documents, Control Panel, or This PC), always call the `open_app` tool with the name of the folder itself as the argument (e.g. `open_app(app_name='downloads')` or `open_app(app_name='recycle bin')`), NOT just 'explorer'.
"""

class Planner:
    def __init__(self):
        pass

    def _get_tools_schema_text(self) -> str:
        schemas = registry.get_tool_schemas()
        text_lines = []
        for s in schemas:
            text_lines.append(f"- Tool: '{s['name']}'")
            text_lines.append(f"  Description: {s['description']}")
            text_lines.append(f"  Arguments: {json.dumps(s['args_schema'])}")
            text_lines.append(f"  Risk Level: {s['risk_level']}")
            text_lines.append("")
        return "\n".join(text_lines)

    def parse_response(self, response_text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Parses LLM response to separate conversational text from structured planned actions.
        Returns:
            Tuple of (conversational_text, list_of_actions)
        """
        actions = []
        clean_text = response_text
        
        # Regex to find JSON code blocks: ```json ... ```
        pattern = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)
        matches = pattern.findall(response_text)
        
        for match in matches:
            try:
                parsed = json.loads(match.strip())
                if isinstance(parsed, list):
                    actions.extend(parsed)
                elif isinstance(parsed, dict):
                    actions.append(parsed)
                # Remove the JSON block from the user-facing text
                clean_text = clean_text.replace(f"```json{match}```", "")
                clean_text = clean_text.replace(f"```json\n{match}\n```", "")
                clean_text = clean_text.replace(f"```json\n{match}```", "")
            except Exception as e:
                logger.error(f"Failed to parse tool JSON block: {match}. Error: {e}")
                
        # Clean up any trailing whitespace or empty lines
        clean_text = clean_text.strip()
        return clean_text, actions

    def create_plan(self, user_prompt: str, history: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Generates a plan from user prompt, querying Ollama.
        Returns conversational reply and parsed planned actions list.
        """
        tools_schema = self._get_tools_schema_text()
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(tools_schema_text=tools_schema)
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})
        
        logger.info(f"Generating plan for prompt: '{user_prompt}'")
        try:
            raw_response = llm_client.chat(messages, stream=False)
            logger.debug(f"Raw LLM response: {raw_response}")
            
            conversational_text, actions = self.parse_response(raw_response)
            logger.info(f"Parsed conversational reply: '{conversational_text}'")
            logger.info(f"Parsed actions: {actions}")
            return conversational_text, actions
        except Exception as e:
            logger.error(f"Planner failed to generate plan: {e}")
            return f"Error: Failed to plan actions. {str(e)}", []

# Global planner instance
planner = Planner()
