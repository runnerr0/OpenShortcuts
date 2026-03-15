"""Deepgram provider — speech-to-text APIs."""

import json
import urllib.request
import urllib.error

from .base import Provider


class DeepgramProvider(Provider):
    name = "Deepgram"
    slug = "deepgram"
    signup_url = "https://console.deepgram.com/signup"
    docs_url = "https://developers.deepgram.com/docs"
    capabilities = ["speech-to-text"]

    defaults = {
        "speech-to-text": {
            "endpoint": "https://api.deepgram.com/v1/listen",
            "model": "nova-2",
        },
    }

    def get_setup_instructions(self):
        return [
            f"1. Open {self.signup_url} in your browser",
            "2. Sign in with Google, GitHub, or email",
            "3. Go to your Dashboard",
            '4. Navigate to "API Keys" in the left sidebar',
            '5. Click "Create a New API Key"',
            "6. Give it a name, select permissions, and click Create",
            "7. Copy the key",
            "",
            "Deepgram offers $200 free credit on signup.",
            "",
            "Note: Deepgram uses a different response format than OpenAI.",
            "The Universal Transcribe shortcut expects OpenAI-compatible format.",
            "Deepgram works best with a custom shortcut variant.",
        ]

    def validate_key(self, api_key):
        req = urllib.request.Request(
            "https://api.deepgram.com/v1/projects",
            headers={
                "Authorization": f"Token {api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                projects = data.get("projects", [])
                return True, f"Valid! ({len(projects)} project(s))"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return False, "Invalid API key"
            return False, f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            return False, f"Connection error: {e}"
