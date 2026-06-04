import os
import json

DEFAULT_CONFIG = {
    "ollama_host": "http://localhost:11434",
    "model_name": "qwen2.5:14b",
    "fallback_model": "qwen2.5:7b",
    "db_path": os.path.join("memory", "memory.db"),
    "logs_dir": "logs",
    "log_file": "aurora.log",
    "safety_thresholds": {
        "low": "execute",
        "medium": "approve",
        "high": "verify"
    },
    "voice_input_enabled": False,
    "voice_output_enabled": False,
    "voice_rate": 180,
    "voice_index": 1,
    "voice_volume": 1.0
}

class Config:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.settings = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_settings = json.load(f)
                    self.settings.update(user_settings)
            except Exception:
                pass
        else:
            self.save()

    def save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except Exception:
            pass

    def get(self, key, default=None):
        return self.settings.get(key, default)

    @property
    def ollama_host(self) -> str:
        return self.get("ollama_host")

    @property
    def model_name(self) -> str:
        return self.get("model_name")

    @property
    def fallback_model(self) -> str:
        return self.get("fallback_model")

    @property
    def db_path(self) -> str:
        return self.get("db_path")

    @property
    def logs_dir(self) -> str:
        return self.get("logs_dir")

    @property
    def log_file_path(self) -> str:
        return os.path.join(self.logs_dir, self.get("log_file"))

    @property
    def safety_thresholds(self) -> dict:
        return self.get("safety_thresholds")

    @property
    def voice_input_enabled(self) -> bool:
        return self.get("voice_input_enabled")

    @property
    def voice_output_enabled(self) -> bool:
        return self.get("voice_output_enabled")

    @property
    def voice_rate(self) -> int:
        return self.get("voice_rate")

    @property
    def voice_index(self) -> int:
        return self.get("voice_index")

    @property
    def voice_volume(self) -> float:
        return self.get("voice_volume")

# Global config instance
config = Config()
