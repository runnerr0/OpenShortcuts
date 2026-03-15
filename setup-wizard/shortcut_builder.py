"""Build personalized .shortcut files with API keys baked in.

Instead of relying on import questions (which require manual entry on iOS),
this module modifies the build scripts' output to embed the user's actual
credentials directly into the shortcut plist. The import questions are
removed so iOS doesn't re-prompt.
"""

import os
import plistlib
import shutil
import tempfile


# Map of shortcut slug -> (build script path relative to repo root, shortcut filename)
SHORTCUT_REGISTRY = {
    "universal-transcribe": {
        "name": "Universal Transcribe",
        "description": "Record audio and get instant transcriptions",
        "category": "speech",
        "build_script": "shortcuts/speech/universal-transcribe/build-shortcut.py",
        "shortcut_file": "shortcuts/speech/universal-transcribe/universal-transcribe.shortcut",
        "capability": "speech-to-text",
        "config_actions": {
            # ActionIndex in the plist where each config value lives
            "endpoint": 1,   # Text block for endpoint URL
            "api_key": 3,    # Text block for API key
            "model": 5,      # Text block for model name
        },
    },
    "link-saver": {
        "name": "Link Saver",
        "description": "Save and summarize links from Safari and social media",
        "category": "productivity",
        "build_script": "shortcuts/productivity/link-saver/build-shortcut.py",
        "shortcut_file": "shortcuts/productivity/link-saver/link-saver.shortcut",
        "capability": "llm",
        "config_actions": {
            "endpoint": 4,
            "api_key": 6,
            "model": 8,
        },
    },
    "receipt-scanner": {
        "name": "Receipt Scanner",
        "description": "Scan receipts and extract expense data with AI vision",
        "category": "productivity",
        "build_script": "shortcuts/productivity/receipt-scanner/build-shortcut.py",
        "shortcut_file": "shortcuts/productivity/receipt-scanner/receipt-scanner.shortcut",
        "capability": "vision",
        "config_actions": {
            "endpoint": 10,
            "api_key": 12,
            "model": 14,
        },
    },
}


def get_repo_root():
    """Find the repo root by walking up from this file."""
    path = os.path.dirname(os.path.abspath(__file__))
    while path != "/":
        if os.path.exists(os.path.join(path, ".git")):
            return path
        path = os.path.dirname(path)
    return os.path.dirname(os.path.abspath(__file__))


def build_personalized_shortcut(shortcut_slug, config, output_dir=None):
    """Build a .shortcut file with the user's config baked in.

    Args:
        shortcut_slug: key from SHORTCUT_REGISTRY
        config: dict with "endpoint", "api_key", "model"
        output_dir: where to write the personalized file (default: temp dir)

    Returns:
        Path to the generated .shortcut file.
    """
    if shortcut_slug not in SHORTCUT_REGISTRY:
        raise ValueError(f"Unknown shortcut: {shortcut_slug}")

    reg = SHORTCUT_REGISTRY[shortcut_slug]
    repo_root = get_repo_root()
    source_shortcut = os.path.join(repo_root, reg["shortcut_file"])

    if not os.path.exists(source_shortcut):
        # Try building it first
        build_script = os.path.join(repo_root, reg["build_script"])
        if os.path.exists(build_script):
            import subprocess
            subprocess.run(
                ["python3", build_script],
                cwd=os.path.dirname(build_script),
                capture_output=True,
            )

    if not os.path.exists(source_shortcut):
        raise FileNotFoundError(f"Shortcut file not found: {source_shortcut}")

    # Read the template shortcut
    with open(source_shortcut, "rb") as f:
        plist = plistlib.load(f)

    actions = plist["WFWorkflowActions"]
    action_map = reg["config_actions"]

    # Patch each config value into the corresponding Text action
    for key, action_idx in action_map.items():
        if key in config and config[key]:
            if action_idx < len(actions):
                action = actions[action_idx]
                params = action.get("WFWorkflowActionParameters", {})
                # Replace the text content — handle both plain strings
                # and WFTextTokenString types
                text_field = params.get("WFTextActionText")
                if isinstance(text_field, str):
                    params["WFTextActionText"] = config[key]
                elif isinstance(text_field, dict):
                    # It's a WFTextTokenString — replace with plain string
                    params["WFTextActionText"] = config[key]

    # Remove import questions so iOS doesn't re-prompt
    plist["WFWorkflowImportQuestions"] = []

    # Write to output directory
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="openshortcuts-")

    filename = os.path.basename(source_shortcut)
    output_path = os.path.join(output_dir, filename)

    with open(output_path, "wb") as f:
        plistlib.dump(plist, f, fmt=plistlib.FMT_BINARY)

    return output_path


def get_available_shortcuts():
    """Return the list of available shortcuts with metadata."""
    return SHORTCUT_REGISTRY


def get_required_capabilities(shortcut_slugs):
    """Given a list of shortcut slugs, return the set of capabilities needed."""
    caps = set()
    for slug in shortcut_slugs:
        if slug in SHORTCUT_REGISTRY:
            caps.add(SHORTCUT_REGISTRY[slug]["capability"])
    return caps
