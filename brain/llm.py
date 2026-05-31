import subprocess
import time
import requests
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

    def chat(self, messages: List[Dict[str, str]], stream: bool = False) -> Any:
        """
        Sends a conversation chat request to Ollama.
        Supports standard generation and streaming generation.
        """
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
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
                except Exception:
                    pass

# Global Ollama client instance
llm_client = OllamaClient()
