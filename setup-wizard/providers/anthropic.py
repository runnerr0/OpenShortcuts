"""Anthropic provider — Claude models via OpenAI-compatible proxy or direct API."""

import json
import urllib.request
import urllib.error

from .base import Provider


class AnthropicProvider(Provider):
    name = "Anthropic"
    slug = "anthropic"
    signup_url = "https://console.anthropic.com"
    docs_url = "https://docs.anthropic.com/en/docs"
    capabilities = ["llm", "vision"]

    defaults = {
        "llm": {
            "endpoint": "https://api.anthropic.com/v1/messages",
            "model": "claude-sonnet-4-6",
        },
        "vision": {
            "endpoint": "https://api.anthropic.com/v1/messages",
            "model": "claude-sonnet-4-6",
        },
    }

    def get_setup_instructions(self):
        return [
            f"1. Open {self.signup_url} in your browser",
            "2. Sign in or create an account",
            "3. Go to API Keys: https://console.anthropic.com/settings/keys",
            '4. Click "Create Key"',
            "5. Give it a name and click Create",
            "6. Copy the key (starts with 'sk-ant-')",
            "",
            "Note: Anthropic's API uses a different format than OpenAI.",
            "The shortcuts use an OpenAI-compatible format, so you may need",
            "a proxy like LiteLLM or an OpenAI-compatible gateway.",
            "If you have one, enter its URL when prompted.",
        ]

    def validate_key(self, api_key):
        """Validate by calling the messages API with minimal tokens."""
        body = json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "Hi"}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return True, "Valid!"
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False, "Invalid API key"
            if e.code == 429:
                return True, "Valid (rate limited, but key is accepted)"
            if e.code == 400:
                # Could be a valid key but bad request params
                try:
                    err = json.loads(e.read())
                    if "authentication" in str(err).lower():
                        return False, "Invalid API key"
                    return True, "Valid (key accepted)"
                except Exception:
                    return True, "Key format accepted"
            return False, f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            return False, f"Connection error: {e}"
