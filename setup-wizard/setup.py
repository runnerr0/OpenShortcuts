#!/usr/bin/env python3
"""OpenShortcuts Setup Wizard

Interactive TUI that guides users through:
1. Selecting which shortcuts they want to install
2. Choosing and configuring their inference provider(s)
3. Validating API keys
4. Building personalized .shortcut files with keys embedded
5. Serving them via a short-lived local HTTP server with QR code

Usage:
    python3 setup.py

No dependencies required — uses only the Python standard library.
(Install `qrcode` for better terminal QR codes: pip install qrcode)
"""

import os
import sys
import tempfile
import time
import webbrowser

from providers.openai import OpenAIProvider
from providers.groq import GroqProvider
from providers.anthropic import AnthropicProvider
from providers.deepgram import DeepgramProvider
from providers.assemblyai import AssemblyAIProvider
from providers.ollama import OllamaProvider
from shortcut_builder import (
    get_available_shortcuts,
    get_required_capabilities,
    build_personalized_shortcut,
)
from qr_server import ShortcutServer


# --- Provider registry ---

ALL_PROVIDERS = [
    GroqProvider(),
    OpenAIProvider(),
    AnthropicProvider(),
    DeepgramProvider(),
    AssemblyAIProvider(),
    OllamaProvider(),
]

PROVIDER_BY_SLUG = {p.slug: p for p in ALL_PROVIDERS}


# --- TUI helpers ---

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_header(title):
    width = 56
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)
    print()


def print_box(lines, color=None):
    """Print text in a box."""
    max_len = max(len(line) for line in lines) if lines else 0
    border = "+" + "-" * (max_len + 2) + "+"
    print(border)
    for line in lines:
        print(f"| {line.ljust(max_len)} |")
    print(border)


def prompt_multi_select(title, options):
    """Let user select multiple items from a list.

    Args:
        title: prompt text
        options: list of (key, display_text) tuples

    Returns:
        list of selected keys
    """
    print(f"  {title}")
    print()
    for i, (key, text) in enumerate(options, 1):
        print(f"    [{i}] {text}")
    print()
    print("  Enter numbers separated by commas (e.g. 1,2,3)")
    print("  Or 'all' to select everything")
    print()

    while True:
        raw = input("  > ").strip().lower()
        if raw == "all":
            return [key for key, _ in options]
        if raw in ("q", "quit", "exit"):
            sys.exit(0)
        try:
            indices = [int(x.strip()) for x in raw.split(",")]
            selected = []
            for idx in indices:
                if 1 <= idx <= len(options):
                    selected.append(options[idx - 1][0])
                else:
                    print(f"    Invalid number: {idx}")
                    selected = []
                    break
            if selected:
                return selected
        except ValueError:
            print("    Please enter numbers separated by commas.")


def prompt_single_select(title, options):
    """Let user select one item from a list.

    Args:
        title: prompt text
        options: list of (key, display_text) tuples

    Returns:
        selected key
    """
    print(f"  {title}")
    print()
    for i, (key, text) in enumerate(options, 1):
        print(f"    [{i}] {text}")
    print()

    while True:
        raw = input("  > ").strip()
        if raw in ("q", "quit", "exit"):
            sys.exit(0)
        try:
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1][0]
            print(f"    Please enter 1-{len(options)}")
        except ValueError:
            print("    Please enter a number.")


def prompt_text(prompt, default=None, secret=False):
    """Prompt for text input."""
    suffix = f" [{default}]" if default else ""
    try:
        if secret:
            import getpass
            value = getpass.getpass(f"  {prompt}{suffix}: ")
        else:
            value = input(f"  {prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)

    return value if value else default


# --- Main wizard flow ---

def step_select_shortcuts():
    """Step 1: Choose which shortcuts to install."""
    clear_screen()
    print_header("OpenShortcuts Setup Wizard")

    shortcuts = get_available_shortcuts()
    options = [
        (slug, f"{info['name']} — {info['description']}")
        for slug, info in shortcuts.items()
    ]

    selected = prompt_multi_select(
        "Which shortcuts do you want to install?",
        options,
    )

    print()
    print(f"  Selected: {', '.join(selected)}")
    return selected


def step_select_provider(capabilities_needed):
    """Step 2: Choose an inference provider."""
    clear_screen()
    print_header("Choose Your Provider")

    cap_list = ", ".join(sorted(capabilities_needed))
    print(f"  Your shortcuts need these capabilities: {cap_list}")
    print()

    # Filter providers that support at least one needed capability
    compatible = []
    for provider in ALL_PROVIDERS:
        supported = set(provider.capabilities) & capabilities_needed
        if supported:
            caps_text = ", ".join(sorted(supported))
            extra = ""
            missing = capabilities_needed - set(provider.capabilities)
            if missing:
                extra = f" (missing: {', '.join(sorted(missing))})"
            compatible.append((
                provider.slug,
                f"{provider.name} — supports: {caps_text}{extra}",
            ))

    if not compatible:
        print("  No providers found for the required capabilities.")
        sys.exit(1)

    slug = prompt_single_select(
        "Which provider do you want to use?",
        compatible,
    )

    return PROVIDER_BY_SLUG[slug]


def step_configure_provider(provider):
    """Step 3: Walk through provider setup and get API key."""
    clear_screen()
    print_header(f"Setting Up {provider.name}")

    instructions = provider.get_setup_instructions()
    print_box(instructions)
    print()

    # Open signup URL in browser
    open_browser = prompt_text(
        f"Open {provider.signup_url} in your browser? (y/n)",
        default="y",
    )
    if open_browser.lower() in ("y", "yes"):
        webbrowser.open(provider.signup_url)
        print()
        print("  Browser opened. Follow the steps above to get your API key.")
        print("  Come back here when you have it.")
        print()

    # Get the API key
    if provider.slug == "ollama":
        api_key = prompt_text("Enter API key (or press Enter for none)", default="ollama")
    else:
        api_key = prompt_text("Paste your API key here", secret=True)

    if not api_key:
        print("  No API key provided. Skipping validation.")
        return api_key

    # Validate
    print()
    print("  Validating key...", end=" ", flush=True)
    success, message = provider.validate_key(api_key)

    if success:
        print(f"OK — {message}")
    else:
        print(f"FAILED — {message}")
        retry = prompt_text("Try a different key? (y/n)", default="y")
        if retry.lower() in ("y", "yes"):
            return step_configure_provider(provider)
        print("  Continuing with unvalidated key...")

    return api_key


def step_build_shortcuts(selected_slugs, provider, api_key):
    """Step 4: Build personalized .shortcut files."""
    clear_screen()
    print_header("Building Your Shortcuts")

    output_dir = tempfile.mkdtemp(prefix="openshortcuts-")
    built_files = []

    for slug in selected_slugs:
        shortcuts = get_available_shortcuts()
        info = shortcuts[slug]
        capability = info["capability"]

        # Get the right config for this shortcut's capability
        config_dict = provider.get_config(api_key, capability)
        if config_dict is None:
            print(f"  SKIP: {info['name']} — {provider.name} doesn't support {capability}")
            continue

        print(f"  Building {info['name']}...", end=" ", flush=True)

        try:
            output_path = build_personalized_shortcut(slug, config_dict, output_dir)
            print(f"OK")
            built_files.append({
                "name": info["name"],
                "description": info["description"],
                "filename": os.path.basename(output_path),
                "path": output_path,
            })
        except Exception as e:
            print(f"ERROR: {e}")

    print()
    print(f"  Built {len(built_files)} shortcut(s) in {output_dir}")
    return built_files


def step_serve_and_show_qr(built_files, timeout=120):
    """Step 5: Start the server and show QR code."""
    clear_screen()
    print_header("Install on Your iPhone")

    if not built_files:
        print("  No shortcuts were built. Nothing to serve.")
        return

    server = ShortcutServer(built_files, timeout=timeout)
    url, qr_text = server.start()

    print(f"  Server running at: {url}")
    print(f"  Auto-shutdown in {timeout} seconds or after all downloads.")
    print()

    if qr_text:
        print("  Scan this QR code with your iPhone camera:")
        print()
        for line in qr_text.split("\n"):
            print(f"    {line}")
        print()
    else:
        print("  +---------------------------------------------------------+")
        print("  |                                                         |")
        print(f"  |  Open this URL on your phone:                           |")
        print(f"  |  {url.ljust(53)} |")
        print("  |                                                         |")
        print("  |  Or install 'qrcode' for a scannable QR code:           |")
        print("  |  pip install qrcode                                     |")
        print("  |                                                         |")
        print("  +---------------------------------------------------------+")
        print()

    print("  Shortcuts available for download:")
    for sf in built_files:
        print(f"    - {sf['name']}")
    print()
    print("  Waiting for downloads... (Ctrl+C to stop)")
    print()

    try:
        while server.is_alive():
            downloaded = len(server.downloaded)
            total = len(server.tokens)
            if downloaded > 0:
                print(f"\r  Progress: {downloaded}/{total} downloaded", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        server.shutdown()

    print()
    print(f"  Done! {len(server.downloaded)}/{len(server.tokens)} shortcuts downloaded.")


def main():
    """Run the full setup wizard."""
    try:
        # Step 1: Select shortcuts
        selected_slugs = step_select_shortcuts()
        if not selected_slugs:
            print("  No shortcuts selected. Exiting.")
            return

        # Step 2: Determine capabilities needed and pick a provider
        capabilities = get_required_capabilities(selected_slugs)
        provider = step_select_provider(capabilities)

        # Step 3: Configure the provider (get API key)
        api_key = step_configure_provider(provider)

        # Step 4: Build personalized shortcuts
        built_files = step_build_shortcuts(selected_slugs, provider, api_key)

        # Step 5: Serve and show QR code
        step_serve_and_show_qr(built_files)

    except KeyboardInterrupt:
        print("\n\n  Setup cancelled.")
        sys.exit(0)


if __name__ == "__main__":
    main()
