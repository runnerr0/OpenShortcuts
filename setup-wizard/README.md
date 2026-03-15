# OpenShortcuts Setup Wizard

A zero-dependency interactive setup tool that configures your API keys, builds personalized iOS Shortcuts, and transfers them to your phone via QR code — no manual key entry required.

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   Computer (setup.py)                     Phone                 │
│   ┌──────────────────┐                                          │
│   │ 1. Pick shortcuts │                                         │
│   │ 2. Pick provider  │                                         │
│   │ 3. Enter API key  │                                         │
│   │ 4. Validate key   │                                         │
│   │ 5. Build .shortcut│                                         │
│   │    files with keys │                                        │
│   │    baked in        │                                        │
│   │ 6. Start local    │     ┌──────────┐                        │
│   │    HTTP server ────┼────►  QR code  │                       │
│   │                    │     └────┬─────┘                       │
│   │                    │          │ scan                         │
│   │                    │     ┌────▼──────────────┐              │
│   │  serve .shortcut ◄─┼─────  phone downloads   │             │
│   │  file (one-time)   │     │  & installs shortcut│            │
│   │                    │     └───────────────────┘              │
│   │ 7. Auto-shutdown   │                                        │
│   └──────────────────┘                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
cd setup-wizard
python3 setup.py
```

No pip install needed. The wizard uses only Python standard library.

For scannable QR codes in the terminal (optional):
```bash
pip install qrcode
```

## What It Does

1. **Select shortcuts** — pick which ones you want (Universal Transcribe, Link Saver, Receipt Scanner)
2. **Choose provider** — select your AI inference provider (Groq, OpenAI, Anthropic, etc.)
3. **Enter API key** — guided setup with step-by-step instructions and browser auto-open
4. **Validate** — tests your key with a real API call before proceeding
5. **Build** — generates `.shortcut` files with your keys embedded (no import questions on iOS)
6. **QR transfer** — starts a short-lived local HTTP server, shows a QR code
7. **Install** — scan QR with your phone, tap to install, done

## Supported Providers

| Provider | LLM | Vision | Speech-to-Text | Free Tier |
|----------|-----|--------|----------------|-----------|
| Groq | yes | yes | yes | yes |
| OpenAI | yes | yes | yes | $5 credit |
| Anthropic | yes | yes | — | — |
| Deepgram | — | — | yes | $200 credit |
| AssemblyAI | — | — | yes | 100 hrs/mo |
| Ollama | yes | yes | — | local/free |

## Security

- **Short-lived server**: auto-shuts down after all files download or 120 seconds
- **LAN only by default**: server binds to your local network IP
- **Single-use tokens**: each download link works once
- **No cloud**: nothing leaves your network. Keys go from your terminal → your phone
- **No storage**: personalized shortcuts are built in a temp directory

## Architecture

```
setup-wizard/
├── setup.py              # Main TUI entry point
├── providers/
│   ├── base.py           # Provider interface
│   ├── openai.py         # OpenAI (GPT, Whisper, DALL-E)
│   ├── groq.py           # Groq (fast Llama, Whisper)
│   ├── anthropic.py      # Anthropic (Claude)
│   ├── deepgram.py       # Deepgram (speech-to-text)
│   ├── assemblyai.py     # AssemblyAI (speech-to-text)
│   └── ollama.py         # Ollama (local models)
├── shortcut_builder.py   # Reads .shortcut plists, patches in keys
├── qr_server.py          # Ephemeral HTTP server + QR generation
└── README.md
```

## Adding a New Provider

1. Create `providers/yourprovider.py` extending `Provider`
2. Define `capabilities`, `defaults`, `validate_key()`
3. Add it to `ALL_PROVIDERS` in `setup.py`

## Adding a New Shortcut

1. Add an entry to `SHORTCUT_REGISTRY` in `shortcut_builder.py`
2. Map the correct `ActionIndex` values for endpoint, api_key, and model
3. The wizard auto-discovers it
