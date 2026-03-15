"""AssemblyAI provider — speech-to-text and audio intelligence."""

import json
import urllib.request
import urllib.error

from .base import Provider


class AssemblyAIProvider(Provider):
    name = "AssemblyAI"
    slug = "assemblyai"
    signup_url = "https://www.assemblyai.com/dashboard/signup"
    docs_url = "https://www.assemblyai.com/docs"
    capabilities = ["speech-to-text"]

    defaults = {
        "speech-to-text": {
            "endpoint": "https://api.assemblyai.com/v2/transcript",
            "model": "best",
        },
    }

    def get_setup_instructions(self):
        return [
            f"1. Open {self.signup_url} in your browser",
            "2. Sign up with Google, GitHub, or email",
            "3. Your API key is shown on the Dashboard immediately",
            "4. Copy the key from the dashboard",
            "",
            "AssemblyAI offers free tier with 100 hours/month.",
            "",
            "Note: AssemblyAI uses an async transcription model.",
            "It requires a different shortcut flow than real-time providers.",
        ]

    def validate_key(self, api_key):
        # Use the /v2/transcript endpoint with a GET to list recent transcripts
        req = urllib.request.Request(
            "https://api.assemblyai.com/v2/transcript?limit=1",
            headers={
                "Authorization": api_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                json.loads(resp.read())
                return True, "Valid!"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return False, "Invalid API key"
            return False, f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            return False, f"Connection error: {e}"
