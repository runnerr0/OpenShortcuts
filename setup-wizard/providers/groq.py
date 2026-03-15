"""Groq provider — fast inference for LLMs and Whisper."""

import json
import urllib.request
import urllib.error

from .base import Provider


class GroqProvider(Provider):
    name = "Groq"
    slug = "groq"
    signup_url = "https://console.groq.com"
    docs_url = "https://console.groq.com/docs"
    capabilities = ["llm", "vision", "speech-to-text"]

    defaults = {
        "llm": {
            "endpoint": "https://api.groq.com/openai/v1/chat/completions",
            "model": "llama-3.3-70b-versatile",
        },
        "vision": {
            "endpoint": "https://api.groq.com/openai/v1/chat/completions",
            "model": "llama-3.2-90b-vision-preview",
        },
        "speech-to-text": {
            "endpoint": "https://api.groq.com/openai/v1/audio/transcriptions",
            "model": "whisper-large-v3",
        },
    }

    def get_setup_instructions(self):
        return [
            f"1. Open {self.signup_url} in your browser",
            "2. Sign in with Google, GitHub, or email",
            "3. Go to API Keys: https://console.groq.com/keys",
            '4. Click "Create API Key"',
            "5. Give it a name and click Submit",
            "6. Copy the key (starts with 'gsk_')",
            "",
            "Groq offers a generous free tier — great for getting started.",
        ]

    def validate_key(self, api_key):
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/models",
            headers={
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                model_count = len(data.get("data", []))
                return True, f"Valid! ({model_count} models available)"
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False, "Invalid API key"
            return False, f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            return False, f"Connection error: {e}"
