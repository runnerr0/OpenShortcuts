"""Ollama provider — local/self-hosted LLMs with OpenAI-compatible API."""

import json
import urllib.request
import urllib.error

from .base import Provider


class OllamaProvider(Provider):
    name = "Ollama (Local)"
    slug = "ollama"
    signup_url = "https://ollama.com/download"
    docs_url = "https://github.com/ollama/ollama/blob/main/docs/api.md"
    capabilities = ["llm", "vision"]

    defaults = {
        "llm": {
            "endpoint": "http://localhost:11434/v1/chat/completions",
            "model": "llama3.2",
        },
        "vision": {
            "endpoint": "http://localhost:11434/v1/chat/completions",
            "model": "llava",
        },
    }

    def get_setup_instructions(self):
        return [
            "Ollama runs locally — no API key needed!",
            "",
            f"1. Download Ollama from {self.signup_url}",
            "2. Install and start Ollama",
            "3. Pull a model: ollama pull llama3.2",
            "4. For vision: ollama pull llava",
            "",
            "Your phone must be on the same network as your computer.",
            "Replace 'localhost' with your computer's LAN IP address",
            "when configuring the shortcut endpoint.",
            "",
            "No API key is required — leave it blank or enter 'ollama'.",
        ]

    def validate_key(self, api_key, host="http://localhost:11434"):
        """Check if Ollama is running and list available models."""
        req = urllib.request.Request(f"{host}/api/tags")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]
                if models:
                    return True, f"Running! Models: {', '.join(models[:5])}"
                return True, "Running, but no models pulled yet. Run: ollama pull llama3.2"
        except Exception:
            return False, "Cannot reach Ollama. Is it running? (ollama serve)"
