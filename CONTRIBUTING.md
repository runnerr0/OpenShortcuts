# Contributing to OpenShortcuts

Thanks for your interest in contributing! This guide explains how to add new shortcuts or improve existing ones.

## Adding a New Shortcut

1. **Pick a category**: `speech`, `ai`, `developer`, or `productivity`. If none fit, propose a new one in an issue first.

2. **Create a folder** under `shortcuts/<category>/<shortcut-name>/`.

3. **Write a README** following the template in [docs/shortcut-template.md](docs/shortcut-template.md). Every shortcut must document:
   - What it does and why it exists
   - Workflow summary (user-facing behavior)
   - Internal flow (step-by-step what the shortcut does)
   - Inputs, outputs, and permissions required
   - Setup steps and configuration options
   - Privacy notes (what data goes where)
   - Known limitations

4. **Include the shortcut file** or an iCloud install link.

5. **Add screenshots** to `assets/screenshots/<shortcut-name>/` if helpful.

6. **Open a pull request** using the PR template.

## Improving an Existing Shortcut

- Fix documentation errors or gaps
- Add screenshots or examples
- Add support for additional providers or configurations
- Report issues using the bug report template

## Guidelines

- Keep READMEs clear and complete. A shortcut is not done until someone else can install and configure it without asking you questions.
- Note all external service dependencies and data flows.
- Do not commit API keys, tokens, or secrets.
- Test shortcuts on a real device before submitting.

## Questions?

Open an issue and we'll help you out.
