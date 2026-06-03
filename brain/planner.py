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

## Stored Long-Term Memories & Preferences:
{memories_text}

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
3. **State-Dependent Planning Constraint**: If a tool call depends on the output of a preceding tool call (for example, you need to find a file path using `search_files` before you can call `summarize_file` or `read_file` on it):
   - **DO NOT** plan both tools in a single turn.
   - **DO NOT** use placeholder paths like `"/path/to/file"` or empty strings `""` for arguments.
   - Instead, plan **ONLY the first tool** (e.g., `search_files`) and wait for the user to return the execution result. Once the real path is returned to you in the next chat turn, you can then plan the subsequent tool (e.g., `summarize_file`) using the real, actual file path.
4. Only plan multiple tool calls in a single turn if they are completely **independent** or if the arguments for all tools are already known with 100% certainty (e.g., `open_app("notepad")` and `open_app("calc")`).
5. **Handling Index References in Lists**: If the user refers to an item from a list in the conversation history by its index number or relative position (e.g., "tell me about 1", "read the 2nd file", "open the first one"):
   - Identify the matching item from the previous tool output (such as search results).
   - **Resolve the absolute path** of that item from the history.
   - Plan the appropriate tool (e.g., `summarize_file`, `read_file`, or `open_app`) directly using that resolved absolute path. Do not re-run the search tool.
6. If no tools are required, simply reply conversationally. Do not include any JSON blocks.
7. Always be direct, precise, and transparent about what actions you are planning.
8. To open specific Windows system folders or directories (such as the Recycle Bin, Downloads, Documents, Control Panel, or This PC), always call the `open_app` tool with the name of the folder itself as the argument (e.g. `open_app(app_name='downloads')` or `open_app(app_name='recycle bin')`), NOT just 'explorer'.
9. **Proactive Memory Recording**: You must be proactive in recording facts, preferences, and personal details about the user. Whenever the user shares system preferences, favorite tools, or personal information (such as their age, birthday, name, or folder locations) either explicitly (e.g., "remember X") or implicitly during natural conversation (e.g., answering "I'm 19" when asked about their age), you MUST immediately queue the 'remember_fact' tool to persist this information in the database. Do not simply reply conversationally without saving it.
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
        from memory.memory import memory
        all_facts = memory.get_all_facts()
        if all_facts:
            memories_text = "\n".join([f"- {k}: {v}" for k, v in all_facts.items()])
        else:
            memories_text = "No long-term memories stored yet."

        tools_schema = self._get_tools_schema_text()
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            tools_schema_text=tools_schema,
            memories_text=memories_text
        )
        
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
