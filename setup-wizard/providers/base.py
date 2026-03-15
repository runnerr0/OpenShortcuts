"""Base provider class defining the interface for all API providers."""


class Provider:
    """Base class for inference providers.

    Each provider knows:
    - Its name, signup URL, and what capabilities it offers
    - How to walk a user through getting an API key
    - How to validate a key with a real API call
    - What endpoint/model defaults to use for each shortcut type
    """

    name = ""
    slug = ""
    signup_url = ""
    docs_url = ""
    capabilities = []  # e.g. ["llm", "vision", "speech-to-text"]
    supports_oauth = False

    # Default endpoint and model for each capability
    defaults = {}
    # e.g. {
    #     "llm": {"endpoint": "https://...", "model": "gpt-4o-mini"},
    #     "speech-to-text": {"endpoint": "https://...", "model": "whisper-1"},
    # }

    def get_setup_instructions(self):
        """Return step-by-step instructions for getting an API key."""
        raise NotImplementedError

    def validate_key(self, api_key):
        """Test the API key with a lightweight API call.

        Returns (success: bool, message: str).
        """
        raise NotImplementedError

    def get_config(self, api_key, capability):
        """Return the config dict for a given capability.

        Returns {"endpoint": str, "api_key": str, "model": str}.
        """
        if capability not in self.defaults:
            return None
        d = self.defaults[capability]
        return {
            "endpoint": d["endpoint"],
            "api_key": api_key,
            "model": d["model"],
        }
