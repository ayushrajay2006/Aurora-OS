import subprocess
import time
import requests
import json
import base64
import re
import os
from typing import List, Dict, Any, Optional, Generator
from config.config import config
from config.logging import logger
from config.state import state_manager

# ─────────────────────────────────────────────
# OpenRouter Client
# ─────────────────────────────────────────────
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
IMAGE_TAG_PATTERN = re.compile(r"<image>\s*(.*?)\s*</image>", re.IGNORECASE)

class OpenRouterClient:
    """Routes requests to OpenRouter using the best free models.
    - Text / planning  → qwen/qwen3-235b-a22b:free
    - Vision (images)  → qwen/qwen2.5-vl-72b-instruct:free
    """

    def _has_images(self, messages: List[Dict[str, str]]) -> bool:
        for msg in messages:
            if IMAGE_TAG_PATTERN.search(msg.get("content", "")):
                return True
        return False

    def _build_openrouter_messages(
        self, messages: List[Dict[str, str]], include_vision: bool
    ) -> List[Dict[str, Any]]:
        """Convert internal message format → OpenRouter/OpenAI format.
        If include_vision is True, image tags are converted to image_url parts.
        """
        result = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if not include_vision:
                # Strip image tags for text-only models
                clean = IMAGE_TAG_PATTERN.sub("", content).strip()
                result.append({"role": role, "content": clean})
                continue

            # Vision model: convert <image>path</image> → inline base64
            paths = IMAGE_TAG_PATTERN.findall(content)
            if not paths:
                result.append({"role": role, "content": content})
                continue

            parts: List[Dict[str, Any]] = []
            # Add text portion (strip image tags)
            text_part = IMAGE_TAG_PATTERN.sub("", content).strip()
            if text_part:
                parts.append({"type": "text", "text": text_part})

            for path in paths:
                path = path.strip()
                if path and os.path.exists(path):
                    try:
                        with open(path, "rb") as f:
                            encoded = base64.b64encode(f.read()).decode("utf-8")
                        mime = "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "image/png"
                        parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{encoded}"}
                        })
                        logger.info(f"OpenRouterClient: Attached image '{path}' to vision payload")
                    except Exception as e:
                        logger.error(f"OpenRouterClient: Failed to encode image '{path}': {e}")
                else:
                    logger.warning(f"OpenRouterClient: Image path not found: '{path}'")

            result.append({"role": role, "content": parts if parts else content})

        return result

    def chat(self, messages: List[Dict[str, str]], stream: bool = False) -> Any:
        api_key = config.openrouter_api_key.strip()
        if not api_key:
            raise ValueError("OpenRouter API key is not configured.")

        has_images = self._has_images(messages)
        if has_images:
            model = config.openrouter_vision_model
            logger.info(f"OpenRouterClient: Vision payload detected → routing to vision model: {model}")
        else:
            model = config.openrouter_text_model
            logger.info(f"OpenRouterClient: Text payload → routing to text model: {model}")

        or_messages = self._build_openrouter_messages(messages, include_vision=has_images)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://aurora-assistant.local",
            "X-Title": "Aurora AI Assistant"
        }
        payload = {
            "model": model,
            "messages": or_messages,
            "temperature": 0.3,
            "stream": stream
        }
        # Qwen3 models support extended thinking — disable it for voice assistant
        # speed (thinking tokens add 5-20s latency with no benefit for short commands)
        if not has_images:
            payload["include_reasoning"] = False


        if stream:
            res = requests.post(OPENROUTER_BASE_URL, headers=headers, json=payload, stream=True, timeout=60)
            res.raise_for_status()
            return self._stream_response(res)
        else:
            res = requests.post(OPENROUTER_BASE_URL, headers=headers, json=payload, timeout=60)
            res.raise_for_status()
            data = res.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return ""

    def _stream_response(self, res: requests.Response) -> Generator[str, None, None]:
        try:
            for line in res.iter_lines():
                if line:
                    decoded = line.decode("utf-8").strip()
                    if decoded.startswith("data: "):
                        json_str = decoded[6:]
                        if json_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(json_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            text = delta.get("content", "")
                            if text:
                                yield text
                        except Exception:
                            pass
        finally:
            res.close()

class OllamaClient:
    def __init__(self):
        self.host = config.ollama_host
        self.model = config.model_name

    def check_connection(self) -> bool:
        """Pings the Ollama service to check if it's running."""
        try:
            res = requests.get(f"{self.host}/api/tags", timeout=3)
            return res.status_code == 200
        except Exception:
            return False

    def attempt_auto_start(self) -> bool:
        """Attempts to launch Ollama serve in a detached background subprocess on Windows."""
        logger.info("Ollama offline. Attempting automatic startup...")
        try:
            # On Windows, creationflags=subprocess.CREATE_NO_WINDOW starts it without opening a CMD window
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000  # CREATE_NO_WINDOW
            )
            
            # Poll for up to 10 seconds for it to start
            for i in range(10):
                time.sleep(1)
                if self.check_connection():
                    logger.info("Ollama background service successfully started and connected.")
                    return True
                logger.debug(f"Waiting for Ollama to boot... {i+1}s")
            
            logger.error("Ollama auto-start failed. Port did not bind in time.")
            return False
        except Exception as e:
            logger.error(f"Failed to start Ollama subprocess: {e}")
            return False

    def check_model_present(self, model_name: str) -> bool:
        """Checks if the specified model is pulled in Ollama with strict tag validation."""
        try:
            res = requests.get(f"{self.host}/api/tags", timeout=3)
            if res.status_code != 200:
                return False
            
            data = res.json()
            models = data.get("models", [])
            
            target = model_name.lower()
            for m in models:
                name = m.get("name", "").lower()
                # 1. Exact match (e.g. "qwen2.5:7b" == "qwen2.5:7b")
                if name == target:
                    return True
                # 2. Base match if target has no tag and model has "latest" tag
                if ":" not in target and name == f"{target}:latest":
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking model presence: {e}")
            return False

    def get_installed_models(self) -> List[str]:
        """Returns a list of all locally pulled model names."""
        try:
            res = requests.get(f"{self.host}/api/tags", timeout=3)
            if res.status_code == 200:
                return [m.get("name", "") for m in res.json().get("models", [])]
            return []
        except Exception:
            return []

    def _prepare_ollama_payload(self, messages: List[Dict[str, str]]) -> tuple:
        import base64
        import re
        import os
        
        # Match image paths enclosed in <image>...</image> tags
        image_path_pattern = re.compile(r"<image>\s*(.*?)\s*</image>", re.IGNORECASE)
        
        formatted_messages = []
        has_images = False
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            
            clean_content = image_path_pattern.sub("", content).strip()
            formatted_msg = {
                "role": role,
                "content": clean_content
            }
            
            # Check for image paths in the message content text
            matches = image_path_pattern.findall(content)
            images = []
            for path in matches:
                path = path.strip()
                if path and os.path.exists(path):
                    try:
                        logger.info(f"OllamaClient: Attaching image file '{path}' to Ollama payload")
                        with open(path, "rb") as img_file:
                            encoded_image = base64.b64encode(img_file.read()).decode("utf-8")
                        images.append(encoded_image)
                        has_images = True
                    except Exception as e:
                        logger.error(f"OllamaClient: Failed to read or encode image file '{path}': {e}")
            
            if images:
                formatted_msg["images"] = images
                
            formatted_messages.append(formatted_msg)
            
        return formatted_messages, has_images

    def chat(self, messages: List[Dict[str, str]], stream: bool = False) -> Any:
        """
        Sends a conversation chat request to Ollama.
        Supports standard generation and streaming generation.
        """
        formatted_messages, has_images = self._prepare_ollama_payload(messages)
        
        # Determine if this is a heavy operation requiring the larger model
        is_heavy = False
        
        # 1. Check if we are in a multi-step tool execution loop
        for msg in messages:
            content = msg.get("content", "")
            if "Execution Results:" in content:
                is_heavy = True
                break
                
        # 2. Check if the latest user query contains complex keywords
        if not is_heavy and messages:
            latest_user_content = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    latest_user_content = msg.get("content", "").lower()
                    break
            
            heavy_keywords = [
                "summarize", "summary", "read file", "parse file", 
                "file content", "analyze", "explain in detail", 
                "deep dive", "write a code", "write a script", 
                "generate code", "debug", "error log", "refactor"
            ]
            if any(kw in latest_user_content for kw in heavy_keywords):
                is_heavy = True

        request_model = config.model_name
        if has_images:
            local_vision = config.local_vision_model.strip()
            if local_vision:
                request_model = local_vision
                logger.info(f"OllamaClient: Images detected in payload. Dynamically routing to local vision model: '{request_model}'")
        elif is_heavy:
            heavy_model = config.heavy_model or "qwen2.5:14b"
            request_model = heavy_model
            logger.info(f"OllamaClient: Complex/heavy task detected. Dynamically routing to: '{request_model}'")
        else:
            logger.info(f"OllamaClient: Simple task/chat. Dynamically routing to: '{request_model}'")

        url = f"{self.host}/api/chat"
        payload = {
            "model": request_model,
            "messages": formatted_messages,
            "stream": stream,
            "options": {
                "temperature": 0.3,
                "stop": ["<execution_results>", "Execution Results:"]
            }
        }
        
        try:
            if stream:
                res = requests.post(url, json=payload, stream=True, timeout=60)
                res.raise_for_status()
                return self._stream_response(res)
            else:
                res = requests.post(url, json=payload, timeout=60)
                res.raise_for_status()
                return res.json().get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Ollama chat execution failed: {e}")
            raise

    def _stream_response(self, res: requests.Response) -> Generator[str, None, None]:
        for line in res.iter_lines():
            if line:
                try:
                    chunk = json.loads(line.decode("utf-8"))
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                except Exception as e:
                    logger.warning(f"Failed to decode stream line: {e}")


class LlmClient:
    def __init__(self):
        self.ollama = OllamaClient()
        self.openrouter = OpenRouterClient()

    def check_connection(self) -> bool:
        provider = config.llm_provider
        if provider == "openrouter":
            return bool(config.openrouter_api_key.strip())
        if provider == "gemini":
            if config.gemini_api_key.strip():
                return True
            logger.warning("Gemini API key is empty. Falling back to local Ollama connection check.")
            return self.ollama.check_connection()
        return self.ollama.check_connection()

    def attempt_auto_start(self) -> bool:
        provider = config.llm_provider
        if provider in ("openrouter", "gemini"):
            return True  # Cloud providers don't need a local process
        return self.ollama.attempt_auto_start()

    def check_model_present(self, model_name: str) -> bool:
        provider = config.llm_provider
        if provider in ("openrouter", "gemini"):
            return True  # Models are always available via cloud
        return self.ollama.check_model_present(model_name)

    def get_installed_models(self) -> List[str]:
        return self.ollama.get_installed_models()

    def chat(self, messages: List[Dict[str, str]], stream: bool = False) -> Any:
        provider = config.llm_provider
        or_key = config.openrouter_api_key.strip()
        gemini_key = config.gemini_api_key.strip()

        # Build fallback chain order based on primary provider
        chain = []
        if provider == "openrouter":
            chain = ["openrouter", "gemini", "local"]
        elif provider == "gemini":
            chain = ["gemini", "openrouter", "local"]
        else:
            chain = ["local", "openrouter", "gemini"]

        # Run through the chain until one succeeds
        errors = []
        for p in chain:
            if p == "openrouter" and or_key:
                try:
                    logger.info("LlmClient: Using OpenRouter.")
                    return self.openrouter.chat(messages, stream=stream)
                except Exception as e:
                    logger.error(f"OpenRouter request failed: {e}")
                    errors.append(f"OpenRouter: {e}")
            elif p == "gemini" and gemini_key:
                try:
                    logger.info("LlmClient: Using Gemini.")
                    if stream:
                        res = self._get_gemini_stream_response(gemini_key, messages)
                        return self._parse_gemini_stream(res)
                    else:
                        return self._chat_gemini_sync(gemini_key, messages)
                except Exception as e:
                    logger.error(f"Gemini request failed: {e}")
                    errors.append(f"Gemini: {e}")
            elif p == "local":
                try:
                    logger.info("LlmClient: Using local Ollama.")
                    return self.ollama.chat(messages, stream=stream)
                except Exception as e:
                    logger.error(f"Local Ollama request failed: {e}")
                    errors.append(f"Local Ollama: {e}")

        # If everything in the chain failed
        err_msg = f"All LLM providers in the fallback chain failed: {'; '.join(errors)}"
        logger.error(err_msg)
        raise RuntimeError(err_msg)

    def _chat_gemini_sync(self, api_key: str, messages: List[Dict[str, str]]) -> str:
        system_instruction, contents = self._prepare_gemini_payload(messages)
        model_name = config.gemini_model.strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": contents,
            "generationConfig": {"temperature": 0.3}
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        logger.debug(f"Gemini request sent to model {model_name}")
        res = requests.post(url, json=payload, timeout=30)
        res.raise_for_status()
        data = res.json()
        candidates = data.get("candidates", [])
        if candidates:
            return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return ""

    def _get_gemini_stream_response(self, api_key: str, messages: List[Dict[str, str]]) -> requests.Response:
        system_instruction, contents = self._prepare_gemini_payload(messages)
        model_name = config.gemini_model.strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?alt=sse&key={api_key}"
        payload = {
            "contents": contents,
            "generationConfig": {"temperature": 0.3}
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        logger.debug(f"Gemini streaming request sent to model {model_name}")
        res = requests.post(url, json=payload, stream=True, timeout=30)
        res.raise_for_status()
        return res

    def _parse_gemini_stream(self, res: requests.Response) -> Generator[str, None, None]:
        try:
            for line in res.iter_lines():
                if line:
                    decoded = line.decode("utf-8").strip()
                    if decoded.startswith("data: "):
                        json_str = decoded[6:]
                        try:
                            chunk = json.loads(json_str)
                            candidates = chunk.get("candidates", [])
                            if candidates:
                                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                                if text:
                                    yield text
                        except Exception:
                            pass
        finally:
            res.close()

    def _prepare_gemini_payload(self, messages: List[Dict[str, str]]):
        system_instruction = None
        contents = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            else:
                gemini_role = "model" if role == "assistant" else "user"
                clean_content = IMAGE_TAG_PATTERN.sub("", content).strip()
                parts = [{"text": clean_content}]
                matches = IMAGE_TAG_PATTERN.findall(content)
                for path in matches:
                    path = path.strip()
                    if path and os.path.exists(path):
                        try:
                            logger.info(f"LlmClient: Attaching image '{path}' to Gemini payload")
                            with open(path, "rb") as img_file:
                                encoded_image = base64.b64encode(img_file.read()).decode("utf-8")
                            mime_type = "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "image/png"
                            parts.append({"inlineData": {"mimeType": mime_type, "data": encoded_image}})
                        except Exception as e:
                            logger.error(f"LlmClient: Failed to encode image '{path}': {e}")
                contents.append({"role": gemini_role, "parts": parts})
        return system_instruction, contents

# Export global LLM client instance
llm_client = LlmClient()

