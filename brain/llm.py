import subprocess
import time
import requests
import json
from typing import List, Dict, Any, Optional, Generator
from config.config import config
from config.logging import logger
from config.state import state_manager

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
        
        # Match standard absolute Windows or Unix paths pointing to PNG, JPG, or JPEG images
        image_path_pattern = re.compile(r"([a-zA-Z]:\\[^\s\"]+\.(?:png|jpg|jpeg))|(/[^\s\"]+\.(?:png|jpg|jpeg))", re.IGNORECASE)
        
        formatted_messages = []
        has_images = False
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            
            formatted_msg = {
                "role": role,
                "content": content
            }
            
            # Check for image paths in the message content text
            matches = image_path_pattern.findall(content)
            images = []
            for match in matches:
                path = next((m for m in match if m), "").strip()
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
        
        # Dynamic model selection based on visual content presence
        request_model = self.model
        if has_images:
            local_vision = config.local_vision_model.strip()
            if local_vision:
                request_model = local_vision
                logger.info(f"OllamaClient: Images detected in payload. Dynamically routing to local vision model: '{request_model}'")

        url = f"{self.host}/api/chat"
        payload = {
            "model": request_model,
            "messages": formatted_messages,
            "stream": stream,
            "options": {
                "temperature": 0.3
            }
        }
        
        try:
            if stream:
                return self._stream_response(url, payload)
            else:
                res = requests.post(url, json=payload, timeout=60)
                res.raise_for_status()
                return res.json().get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Ollama chat execution failed: {e}")
            raise

    def _stream_response(self, url: str, payload: Dict[str, Any]) -> Generator[str, None, None]:
        res = requests.post(url, json=payload, stream=True, timeout=60)
        res.raise_for_status()
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

    def check_connection(self) -> bool:
        if config.llm_provider == "gemini":
            if config.gemini_api_key.strip():
                return True
            logger.warning("Gemini API key is empty. Falling back to local Ollama connection check.")
            return self.ollama.check_connection()
        return self.ollama.check_connection()

    def attempt_auto_start(self) -> bool:
        if config.llm_provider == "gemini":
            return True
        return self.ollama.attempt_auto_start()

    def check_model_present(self, model_name: str) -> bool:
        if config.llm_provider == "gemini":
            return True
        return self.ollama.check_model_present(model_name)

    def get_installed_models(self) -> List[str]:
        return self.ollama.get_installed_models()

    def chat(self, messages: List[Dict[str, str]], stream: bool = False) -> Any:
        provider = config.llm_provider
        gemini_key = config.gemini_api_key.strip()
        
        if provider == "gemini" and gemini_key:
            try:
                if stream:
                    # Synchronously establish connection and verify status to catch errors (e.g. 429) early
                    res = self._get_gemini_stream_response(gemini_key, messages)
                    return self._parse_gemini_stream(res)
                else:
                    return self._chat_gemini_sync(gemini_key, messages)
            except Exception as e:
                logger.error(f"Gemini API request failed: {e}. Falling back to local Ollama.")
                return self.ollama.chat(messages, stream=stream)
        else:
            # Primary local Ollama
            try:
                return self.ollama.chat(messages, stream=stream)
            except Exception as e:
                if gemini_key:
                    logger.error(f"Local Ollama request failed: {e}. Falling back to Gemini API.")
                    try:
                        if stream:
                            res = self._get_gemini_stream_response(gemini_key, messages)
                            return self._parse_gemini_stream(res)
                        else:
                            return self._chat_gemini_sync(gemini_key, messages)
                    except Exception as ge:
                        logger.error(f"Gemini API fallback request also failed: {ge}")
                        raise
                else:
                    logger.error(f"Local Ollama request failed: {e}. No Gemini API key configured for fallback.")
                    raise

    def _chat_gemini_sync(self, api_key: str, messages: List[Dict[str, str]]) -> str:
        system_instruction, contents = self._prepare_gemini_payload(messages)
        
        model_name = config.gemini_model.strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3
            }
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
            "generationConfig": {
                "temperature": 0.3
            }
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
        import base64
        import re
        import os
        
        system_instruction = None
        contents = []
        
        # Match standard absolute Windows or Unix paths pointing to PNG, JPG, or JPEG images
        image_path_pattern = re.compile(r"([a-zA-Z]:\\[^\s\"]+\.(?:png|jpg|jpeg))|(/[^\s\"]+\.(?:png|jpg|jpeg))", re.IGNORECASE)
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if role == "system":
                system_instruction = {
                    "parts": [{"text": content}]
                }
            else:
                gemini_role = "model" if role == "assistant" else "user"
                parts = [{"text": content}]
                
                # Check for image paths in the message content text
                matches = image_path_pattern.findall(content)
                for match in matches:
                    # Find the first non-empty match group
                    path = next((m for m in match if m), "").strip()
                    if path and os.path.exists(path):
                        try:
                            logger.info(f"LlmClient: Attaching image file '{path}' to Gemini API request payload")
                            with open(path, "rb") as img_file:
                                encoded_image = base64.b64encode(img_file.read()).decode("utf-8")
                            
                            mime_type = "image/png"
                            if path.lower().endswith(".jpg") or path.lower().endswith(".jpeg"):
                                mime_type = "image/jpeg"
                                
                            parts.append({
                                "inlineData": {
                                    "mimeType": mime_type,
                                    "data": encoded_image
                                }
                            })
                        except Exception as e:
                            logger.error(f"LlmClient: Failed to read or encode image file '{path}': {e}")
                            
                contents.append({
                    "role": gemini_role,
                    "parts": parts
                })
        return system_instruction, contents

# Export global LLM client instance
llm_client = LlmClient()
