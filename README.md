# OpenShortcuts

A curated library of reusable iOS Shortcuts that expose useful automation patterns around AI, speech-to-text, developer utilities, and knowledge capture.

Apple Shortcuts treated like real software artifacts: documented, versioned, categorized, configurable, and safe for others to install and reuse.

## What This Is

- **Installable shortcuts** that do genuinely useful work on iPhone and iPad
- **Clear documentation** so you can understand, configure, and troubleshoot each one
- **Repeatable patterns** for shortcuts that call external services (LLMs, speech-to-text APIs, webhooks, local servers)
- **A consistent framework** for adding new shortcuts instead of one-off blobs

## Shortcuts

### Speech

| Shortcut | Description |
|----------|-------------|
| [Universal Transcribe](shortcuts/speech/universal-transcribe/) | Record audio on iOS, send it to any transcription service, get text back on your clipboard |

### AI

*Coming soon*

### Developer

*Coming soon*

### Productivity

*Coming soon*

## Getting Started

1. Browse the [shortcuts/](shortcuts/) directory by category
2. Open the README for any shortcut you want to install
3. Follow the setup instructions (API keys, endpoint configuration, etc.)
4. Install the shortcut on your device

## Project Structure

```
OpenShortcuts/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── .gitignore
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── new-shortcut.md
│   │   └── bug-report.md
│   └── pull_request_template.md
├── shortcuts/
│   ├── speech/
│   │   └── universal-transcribe/
│   ├── ai/
│   ├── developer/
│   └── productivity/
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
