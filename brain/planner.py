import json
import re
from typing import List, Dict, Any, Tuple
from tools.registry import registry
from brain.llm import llm_client
from config.logging import logger

# Keywords that signal an action intent requiring a tool call
ACTION_INTENT_PHRASES = [
    "open ", "launch ", "start ", "run ", "close ", "quit ", "kill ",
    "minimize ", "maximise ", "maximize ", "restore ", "switch to ",
    "show ", "hide "
]

SYSTEM_PROMPT_TEMPLATE = """You are Aurora, an advanced, local-first personal operating system assistant for Windows, inspired by the beauty and intelligence of the Aurora Borealis.

Your goal is to help the user control their PC, manage files, open applications, search the web, and answer questions.

## Tone & Personality:
- Be friendly, warm, and natural—speak like a supportive, smart companion or friend rather than a rigid robot or menu.
- Vary your greetings and response endings. Avoid repetitive menus or offering lists of standard options (e.g. "Do you want to open an application, search online...") unless requested. Keep the dialogue flowing naturally.
- Show genuine interest and warmth toward the user and their hobbies.

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
8. **Opening Applications or Games**: To open any application, game, or program use ONLY `open_app` with the app name. NEVER describe opening an app without generating this tool call.
   Example: User says "open discord" → you MUST output:
   Opening Discord!
   ```json
   [{"tool": "open_app", "args": {"app_name": "discord"}}]
   ```
9. **Opening Folders**: To open any folder or directory (Downloads, Documents, Desktop, Pictures, Videos, Music, Screenshots, or any named folder) use ONLY `open_folder` with the folder name or path. NEVER use `open_app` for folders. NEVER describe opening a folder without generating this tool call.
   Example: User says "open downloads" → you MUST output:
   Opening your Downloads folder!
   ```json
   [{"tool": "open_folder", "args": {"path": "downloads"}}]
   ```
10. **Closing Applications**: To close any running application use ONLY `close_app` with the app name. NEVER say you have closed an app without generating this tool call. NEVER describe closing without calling the tool.
    Example: User says "close steam" → you MUST output:
    Closing Steam!
    ```json
    [{"tool": "close_app", "args": {"app_name": "steam"}}]
    ```
11. **Window Control**: To minimize, maximize, restore, or switch to a window use `minimize_app`, `maximize_app`, `restore_app`, or `switch_to_app`. NEVER describe a window action without calling the appropriate tool.
    Example: User says "minimize discord" → `minimize_app(app_name='discord')`
12. **Proactive Memory Recording**: You must be proactive in recording key personal facts, preferences, and system settings (such as the user's name, age, birthday, favorite games, or custom folder paths). However, do NOT record casual chit-chat, temporary statuses (e.g., playing a game "recently"), or fleeting conversational comments. Only save facts that have long-term utility for personalizing system actions. Do not call 'remember_fact' if the key-value pair is already listed in the 'Stored Long-Term Memories & Preferences' section, unless the value has changed.
13. **Preventing Technical Hallucinations (Search Rule)**: You must never guess or hallucinate specific complex formulas, Rubik's cube algorithms (e.g., CFOP PLL/OLL algorithms), scientific constants, or detailed technical references that you do not have stored in your long-term memories or local files. If the user asks for such technical information, you MUST NOT generate them from memory. Instead, call the `open_website` tool with a descriptive search query (e.g., `open_website(url="standard CFOP PLL algorithms sheet")`) to perform a Google search on the user's browser, ensuring they receive accurate information.
"""

# Tool names that represent real system actions (not conversational)
ACTION_TOOLS = {
    "open_app", "open_folder", "open_file", "open_website",
    "close_app", "close_process",
    "switch_to_app", "minimize_app", "maximize_app", "restore_app",
    "search_files", "read_pdf", "remember_fact", "forget_fact", "discover_apps",
}

class Planner:
    def __init__(self):
        pass

    def _looks_like_action_request(self, user_input: str) -> bool:
        """Returns True if the user's message looks like a system action request."""
        q = user_input.lower().strip()
        for phrase in ACTION_INTENT_PHRASES:
            if q.startswith(phrase) or f" {phrase.strip()} " in q:
                return True
        return False

    def _response_has_action_tool(self, actions: list) -> bool:
        """Returns True if the parsed actions contain at least one real action tool."""
        for act in actions:
            if act.get("tool") in ACTION_TOOLS:
                return True
        return False

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
        
        # Regex to find JSON code blocks: ```json ... ``` or ``` ... ```
        pattern = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
        matches = pattern.findall(response_text)
        
        for match in matches:
            try:
                parsed = json.loads(match.strip())
                if isinstance(parsed, list):
                    actions.extend(parsed)
                elif isinstance(parsed, dict):
                    actions.append(parsed)
                # Remove the JSON block from the user-facing text
                # Try replacing with the code block format variations
                for block_format in [
                    f"```json\n{match}\n```", f"```json\n{match}```", f"```json{match}```",
                    f"```\n{match}\n```", f"```\n{match}```", f"```{match}```"
                ]:
                    clean_text = clean_text.replace(block_format, "")
            except Exception as e:
                logger.error(f"Failed to parse tool JSON block: {match}. Error: {e}")
                
        # Raw JSON fallback if no actions parsed from code blocks
        if not actions:
            for start_char, end_char in [('[', ']'), ('{', '}')]:
                first_idx = response_text.find(start_char)
                last_idx = response_text.rfind(end_char)
                if first_idx != -1 and last_idx != -1 and last_idx > first_idx:
                    candidate = response_text[first_idx:last_idx+1]
                    try:
                        parsed = json.loads(candidate.strip())
                        if isinstance(parsed, list) and start_char == '[':
                            actions = parsed
                            clean_text = response_text[:first_idx] + response_text[last_idx+1:]
                            break
                        elif isinstance(parsed, dict) and start_char == '{':
                            actions = [parsed]
                            clean_text = response_text[:first_idx] + response_text[last_idx+1:]
                            break
                    except Exception:
                        pass

        # Clean up any trailing whitespace or empty lines
        clean_text = clean_text.strip()
        return clean_text, actions

    def create_plan(self, user_prompt: str, history: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Generates a plan from user prompt, querying Ollama.
        Returns conversational reply and parsed planned actions list.
        If an action intent is detected but no tool call is produced, replans once
        with an explicit reminder injected into the message.
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

            # --- Replan if action intent detected but no tool call produced ---
            if self._looks_like_action_request(user_prompt) and not self._response_has_action_tool(actions):
                logger.warning(
                    f"[Planner] Action intent detected for '{user_prompt}' but NO tool call was generated. "
                    "Replanning with explicit reminder."
                )
                replan_reminder = (
                    f"{user_prompt}\n\n"
                    "[SYSTEM REMINDER] Your previous response did not include a tool call JSON block. "
                    "This request REQUIRES a tool call. You MUST respond with a ```json [...] ``` block. "
                    "Do not describe the action in text only. Generate the tool call now."
                )
                replan_messages = [{"role": "system", "content": system_prompt}]
                replan_messages.extend(history)
                replan_messages.append({"role": "user", "content": replan_reminder})

                raw_response2 = llm_client.chat(replan_messages, stream=False)
                logger.debug(f"[Planner] Replan raw response: {raw_response2}")
                conversational_text2, actions2 = self.parse_response(raw_response2)

                if self._response_has_action_tool(actions2):
                    logger.info(f"[Planner] Replan succeeded — tool calls: {actions2}")
                    return conversational_text2, actions2
                else:
                    logger.warning("[Planner] Replan also produced no tool calls. Returning original response.")

            return conversational_text, actions
        except Exception as e:
            logger.error(f"Planner failed to generate plan: {e}")
            return f"Error: Failed to plan actions. {str(e)}", []

# Global planner instance
planner = Planner()
