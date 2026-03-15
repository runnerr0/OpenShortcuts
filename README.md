# OpenShortcuts

A curated library of reusable iOS Shortcuts that expose useful automation patterns around AI, speech-to-text, developer utilities, and knowledge capture.

Apple Shortcuts treated like real software artifacts: documented, versioned, categorized, configurable, and safe for others to install and reuse.

**[Browse & Install Shortcuts →](https://runnerr0.github.io/OpenShortcuts/)**

## What This Is

- **Installable shortcuts** that do genuinely useful work on iPhone and iPad
- **Clear documentation** so you can understand, configure, and troubleshoot each one
- **Repeatable patterns** for shortcuts that call external services (LLMs, speech-to-text APIs, webhooks, local servers)
- **A consistent framework** for adding new shortcuts instead of one-off blobs

## Shortcuts

### Speech

| Shortcut | Description | Install |
|----------|-------------|---------|
| [Universal Transcribe](shortcuts/speech/universal-transcribe/) | Record audio, send to any STT service, get text on clipboard | [Install](shortcuts://import-shortcut?url=https%3A%2F%2Fraw.githubusercontent.com%2Frunnerr0%2FOpenShortcuts%2Fmain%2Fshortcuts%2Fspeech%2Funiversal-transcribe%2Funiversal-transcribe.shortcut&name=Universal%20Transcribe) |

### AI

| Shortcut | Description | Install |
|----------|-------------|---------|
| [Clipboard Rewriter](shortcuts/ai/clipboard-rewriter/) | Transform clipboard text via LLM: rewrite, simplify, grammar, translate | [Install](shortcuts://import-shortcut?url=https%3A%2F%2Fraw.githubusercontent.com%2Frunnerr0%2FOpenShortcuts%2Fmain%2Fshortcuts%2Fai%2Fclipboard-rewriter%2Fclipboard-rewriter.shortcut&name=Clipboard%20Rewriter) |

### Productivity

| Shortcut | Description | Install |
|----------|-------------|---------|
| [Voice to Structured Notes](shortcuts/productivity/voice-structured-notes/) | Record speech → transcribe → LLM structures into formatted Apple Note | [Install](shortcuts://import-shortcut?url=https%3A%2F%2Fraw.githubusercontent.com%2Frunnerr0%2FOpenShortcuts%2Fmain%2Fshortcuts%2Fproductivity%2Fvoice-structured-notes%2Fvoice-structured-notes.shortcut&name=Voice%20Structured%20Notes) |
| [Quick Research Capture](shortcuts/productivity/research-capture/) | Share a URL → LLM summarizes → appends to Research Log in Notes | [Install](shortcuts://import-shortcut?url=https%3A%2F%2Fraw.githubusercontent.com%2Frunnerr0%2FOpenShortcuts%2Fmain%2Fshortcuts%2Fproductivity%2Fresearch-capture%2Fresearch-capture.shortcut&name=Quick%20Research%20Capture) |
| [Voice to Reminders](shortcuts/productivity/voice-reminders/) | Speak naturally → LLM parses into tasks → creates iOS Reminders | [Install](shortcuts://import-shortcut?url=https%3A%2F%2Fraw.githubusercontent.com%2Frunnerr0%2FOpenShortcuts%2Fmain%2Fshortcuts%2Fproductivity%2Fvoice-reminders%2Fvoice-reminders.shortcut&name=Voice%20Reminders) |

### Developer

*Coming soon*

## Getting Started

1. **Browse** the shortcuts above or visit the [install catalog](https://runnerr0.github.io/OpenShortcuts/)
2. **Tap Install** on your iOS device — the Shortcuts app will open
3. **Configure** your API key and endpoint when prompted
4. **Use it** from Home Screen, widget, Share Sheet, or Siri

> Requires iOS 16+ with "Allow Untrusted Shortcuts" enabled in Settings > Shortcuts.

## Project Structure

```
OpenShortcuts/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── .gitignore
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── pull_request_template.md
├── shortcuts/
│   ├── speech/
│   │   └── universal-transcribe/
│   ├── ai/
│   │   └── clipboard-rewriter/
│   ├── developer/
│   └── productivity/
│       ├── voice-structured-notes/
│       ├── research-capture/
│       └── voice-reminders/
├── site/
│   └── index.html
├── docs/
│   ├── repo-roadmap.md
│   └── shortcut-template.md
└── assets/
    └── screenshots/
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on adding new shortcuts or improving existing ones.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
