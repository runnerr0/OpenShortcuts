"""OpenAI provider — GPT models, Whisper, DALL-E, vision."""

import json
import urllib.request
import urllib.error

from .base import Provider


class OpenAIProvider(Provider):
    name = "OpenAI"
    slug = "openai"
    signup_url = "https://platform.openai.com/signup"
    docs_url = "https://platform.openai.com/docs/api-reference"
    capabilities = ["llm", "vision", "speech-to-text"]

    defaults = {
        "llm": {
            "endpoint": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-4o-mini",
        },
        "vision": {
            "endpoint": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-4o-mini",
        },
        "speech-to-text": {
            "endpoint": "https://api.openai.com/v1/audio/transcriptions",
            "model": "whisper-1",
        },
    }

    def get_setup_instructions(self):
        return [
            f"1. Open {self.signup_url} in your browser",
            "2. Sign in or create an account",
            "3. Go to API Keys: https://platform.openai.com/api-keys",
            '4. Click "+ Create new secret key"',
            "5. Give it a name (e.g. 'OpenShortcuts') and click Create",
            "6. Copy the key (starts with 'sk-')",
            "",
            "Note: OpenAI requires a payment method on file.",
            "New accounts get $5 free credit for the first 3 months.",
        ]

    def validate_key(self, api_key):
        """Validate by listing models — lightweight, no cost."""
        req = urllib.request.Request(
            "https://api.openai.com/v1/models",
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
            if e.code == 429:
                return True, "Valid (rate limited, but key is accepted)"
            return False, f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            return False, f"Connection error: {e}"
