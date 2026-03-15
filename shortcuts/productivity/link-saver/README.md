# Link Saver

Save and summarize links from any social media platform or website directly into Apple Notes — so you never lose them again.

## What It Does

Share a link from **any app** — Twitter/X, Reddit, YouTube, Instagram, TikTok, LinkedIn, Hacker News, Safari, or anywhere else — and this shortcut will:

1. Fetch the page content
2. Use AI to identify the platform, extract a title, author, and summary
3. Auto-tag with relevant topics
4. Append a structured entry to a **"Saved Links"** note in Apple Notes
5. Show a confirmation notification

Every saved link gets a clean, scannable entry with the date, source URL, platform tag, and a concise summary — all in one place.

## Example Output

Each entry in your "Saved Links" note looks like this:

```
───────────────────────────────────────
📅 Jan 15, 2025 at 3:42 PM
🔗 https://twitter.com/example/status/123456

Platform: Twitter/X
Title: Thread on how AI agents are changing developer workflows
Author: @example
Summary: A detailed thread exploring how AI-powered coding assistants
are reshaping software development. Covers productivity gains, common
pitfalls, and predictions for the next 2 years.
Tags: #AI #DevTools #Programming

═══════════════════════════════════════
```

## Setup

1. **Install the shortcut** by opening `link-saver.shortcut` on your iPhone/iPad
2. When prompted, enter:
   - **API Endpoint**: Your LLM provider's chat completions URL (default: OpenAI)
   - **API Key**: Your API key
   - **Model**: The model to use (default: `gpt-4o-mini`)

### Compatible Providers

Any OpenAI-compatible chat completions API:
- **OpenAI**: `https://api.openai.com/v1/chat/completions`
- **Groq**: `https://api.groq.com/openai/v1/chat/completions`
- **Anthropic (via proxy)**: Any OpenAI-compatible Anthropic proxy
- **Local (Ollama)**: `http://localhost:11434/v1/chat/completions`

## How to Use

1. Find a link you want to save in any app
2. Tap the **Share** button
3. Select **Link Saver** from the share sheet
4. Wait a moment for the AI to process
5. Done — check your "Saved Links" note in Apple Notes

## Supported Platforms

The AI automatically detects and tags links from:

- Twitter/X
- Reddit
- YouTube
- Instagram
- TikTok
- LinkedIn
- Mastodon
- Threads
- Bluesky
- Hacker News
- News articles
- Any website

## Customization

### Changing the Note Name

Edit the `build-shortcut.py` script and search for `"Saved Links"` — replace with your preferred note name, then rebuild.

### Adjusting the Summary Style

Modify the `system_prompt` variable in the build script to change what the AI extracts and how it formats the output.

## Building from Source

```bash
python3 build-shortcut.py
```

This generates `link-saver.shortcut` which can be AirDropped or opened on any iOS device.
