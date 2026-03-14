# Universal Transcribe

A provider-agnostic iOS Shortcut that records audio on your device, sends it to any speech-to-text service, and copies the transcript to your clipboard.

## Why It Exists

Transcription is one of the most useful things you can do with a phone, but every provider has its own app or workflow. This shortcut gives you a single tap-to-transcribe flow that works with whichever STT backend you prefer.

## User-Facing Behavior

1. Tap the shortcut (Home Screen, Share Sheet, or Siri)
2. Speak
3. Wait a moment while audio is sent and transcribed
4. Your transcript is copied to the clipboard
5. A haptic vibration (iPhone) or notification (iPad) confirms it's ready to paste

## Internal Flow

```
┌─────────────┐
│ Record Audio │
└──────┬──────┘
       │
┌──────▼───────────┐
│ Store audio in    │
│ file variable     │
└──────┬───────────┘
       │
┌──────▼───────────┐
│ Read API key from │
│ shortcut input or │
│ text field         │
└──────┬───────────┘
       │
┌──────▼───────────┐
│ HTTP POST to      │
│ transcription     │
│ endpoint          │
│ (multipart/form)  │
└──────┬───────────┘
       │
┌──────▼───────────┐
│ Parse JSON        │
│ response          │
└──────┬───────────┘
       │
┌──────▼───────────┐
│ Extract transcript│
│ text field        │
└──────┬───────────┘
       │
┌──────▼───────────┐
│ Copy to clipboard │
└──────┬───────────┘
       │
┌──────▼───────────┐
│ If iPhone:        │
│   vibrate         │
│ Else:             │
│   show notification│
└─────────────────┘
```

## Inputs

| Input | Description |
|-------|-------------|
| Audio | Recorded via the built-in "Record Audio" action |

## Outputs

| Output | Description |
|--------|-------------|
| Clipboard | The transcribed text, ready to paste |

## Permissions Required

- **Microphone**: To record audio
- **Network**: To send audio to the transcription endpoint

## Setup

### 1. Choose a Provider

This shortcut works with any HTTP transcription endpoint. Tested providers:

| Provider | Endpoint | Response Field |
|----------|----------|---------------|
| OpenAI Whisper | `https://api.openai.com/v1/audio/transcriptions` | `text` |
| Groq Whisper | `https://api.groq.com/openai/v1/audio/transcriptions` | `text` |
| Deepgram | `https://api.deepgram.com/v1/listen` | `results.channels[0].alternatives[0].transcript` |
| Local server | Your own URL | Depends on implementation |

### 2. Get an API Key

Sign up with your chosen provider and generate an API key.

### 3. Configure the Shortcut

After installing, open the shortcut in edit mode and set:

1. **API Endpoint URL** - The transcription endpoint for your provider
2. **API Key** - Your key (stored locally in the shortcut, never shared)
3. **Model** (if applicable) - e.g. `whisper-large-v3` for Groq
4. **Response field path** - The JSON path to the transcript text (see table above)

### 4. Install

<!-- TODO: Add iCloud install link once shortcut is exported -->

*Install link coming soon.*

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| Endpoint URL | *(none)* | The HTTP endpoint to POST audio to |
| API Key | *(none)* | Bearer token for authentication |
| Model | `whisper-large-v3` | Model identifier (provider-dependent) |
| Response field | `text` | JSON key containing the transcript |
| Audio format | m4a | Recording format sent to the API |

## Privacy Notes

- **Audio is sent over the network** to whichever transcription endpoint you configure. It is not processed on-device.
- The API key is stored inside the shortcut on your device. It is only sent to the configured endpoint.
- No data is sent to any third party beyond the provider you choose.
- If you use a local server, audio never leaves your network.

## Known Limitations

- Recording length is limited by iOS Shortcuts' built-in Record Audio action.
- Some providers have file size limits (e.g. OpenAI Whisper: 25 MB).
- Deeply nested response fields (like Deepgram's) may require adjusting the "Get Dictionary Value" chain in the shortcut.
- No streaming support; the full audio is uploaded after recording finishes.
- Shortcut does not currently support selecting language; it relies on the provider's auto-detection.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Could not connect" | Check your endpoint URL and network connection |
| Empty clipboard | Verify the response field path matches your provider's JSON shape |
| Authentication error | Confirm your API key is valid and has the right permissions |
| Garbled transcript | Try a different model or check audio quality |
