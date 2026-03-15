# Audio Briefing / Personal Podcast Agent

> **Status**: Future — architecture documented, not yet implemented.

Generate audio content on demand and deliver it as episodes in your personal
podcast feed. Works with any podcast app that supports private RSS URLs.

## Use Cases

- **Morning Brief**: "Give me my morning update" → 3-5 min audio covering
  weather, calendar, news, commute (same data as text briefing, but spoken)
- **Topic Deep Dive**: "Make me a podcast about quantum computing" → 10-15 min
  two-host discussion researched and generated on the fly
- **Commute Digest**: "Summarize my day" → end-of-day recap as audio

## Architecture

```
┌──────────────┐      ┌─────────────────────────────┐      ┌──────────────┐
│  iOS Shortcut │ POST │  Agent Server (FastAPI)      │      │  Podcast Feed│
│              │─────►│                             │      │  (nginx)     │
│  "podcast    │      │  1. Parse topic/request     │      │              │
│   about X"   │      │  2. Research (web search)   │ MP3  │  feed.xml    │
│              │      │  3. Generate script         │─────►│  episodes/   │
│              │ 200  │  4. TTS → WAV → MP3         │      │    ep1.mp3   │
│              │◄─────│  5. Update RSS feed         │      │    ep2.mp3   │
│  "Episode    │      │  6. Return confirmation     │      │              │
│   queued"    │      │                             │      │              │
└──────────────┘      └─────────────────────────────┘      └──────────────┘
                                                                  │
                                                           ┌──────┴───────┐
                                                           │ Podcast App  │
                                                           │ (Overcast,   │
                                                           │  Apple, etc.)│
                                                           └──────────────┘
```

## TTS Options (Three Tiers)

### Tier 1: Local TTS (Full Privacy)

Run entirely on your hardware. No audio leaves your network.

| Engine | Quality | Multi-Speaker | Hardware | Notes |
|--------|---------|--------------|----------|-------|
| **Piper** | Good | Yes (swap voices) | CPU only, <1GB RAM | Fastest, lightest. Good for briefs. |
| **Kokoro** | Very Good | Yes | CPU or GPU, ~2GB | 82M params, near-commercial quality |
| **F5-TTS** | Excellent | Yes (voice cloning) | GPU recommended, 4GB+ | Zero-shot cloning from 15s sample |
| **Bark** | Very Good | Yes (speaker presets) | GPU, 8GB+ VRAM | Most natural prosody, slow |
| **Coqui XTTS v2** | Excellent | Yes (voice cloning) | GPU, 4GB+ | Best open-source cloning quality |

For a "two hosts discussing" format: generate Host A and Host B lines separately
with different voice models, then stitch with `pydub` or `ffmpeg`.

### Tier 2: Cloud TTS (ElevenLabs)

Best quality without NotebookLM. API-based, pay per character.

```python
from elevenlabs import ElevenLabs
client = ElevenLabs(api_key="...")

# Generate each host's lines with different voices
audio_host_a = client.text_to_speech.convert(
    text="So today we're diving into quantum computing...",
    voice_id="Rachel",
    model_id="eleven_multilingual_v2"
)
audio_host_b = client.text_to_speech.convert(
    text="Right, and what's fascinating is...",
    voice_id="Adam",
    model_id="eleven_multilingual_v2"
)
```

- 10,000 chars/month free, $5/mo for 30k, $22/mo for 100k
- ~10 min podcast ≈ 8,000-12,000 characters
- 29+ languages, instant voice cloning

### Tier 3: NotebookLM (Google)

Best podcast-style output. Google's two-host "Audio Overview" feature.

**Option A: Enterprise API** (official, alpha)
```
POST https://{LOCATION}-discoveryengine.googleapis.com/v1alpha/
  projects/{PROJECT}/locations/{LOCATION}/notebooks/{ID}/audioOverviews
```
Requires Google Cloud enterprise account.

**Option B: notebooklm-py** (unofficial Python library)
Uses undocumented APIs. No browser automation needed.

**Option C: notebooklm-podcast-automator** (Playwright)
FastAPI + headless browser. Upload sources, trigger generation, download audio.

- Free tier: 3 audio overviews/day
- Output: WAV (convert to MP3 with ffmpeg)
- Styles: Deep Dive, Brief, Critique, Debate
- 80+ languages

## Podcast Feed

Self-hosted RSS feed. Minimal setup:

```
/var/www/podcast/
  feed.xml          # RSS 2.0 with iTunes namespace
  artwork.jpg       # 3000x3000 show art
  episodes/
    2026-03-15-quantum-computing.mp3
    2026-03-14-morning-brief.mp3
```

**Password protection** (nginx basic auth):
```nginx
location /podcast/ {
    auth_basic "Personal Podcast";
    auth_basic_user_file /etc/nginx/.htpasswd;
    root /var/www;
}
```

Podcast apps that support authenticated feeds: Apple Podcasts, Overcast,
Pocket Casts, Podcast Addict. Spotify does NOT support private feeds.

**Feed generation**: Use Python `podgen` or `feedgen` library to regenerate
`feed.xml` whenever a new episode is added.

## Script Generation

The agent writes a conversation script before TTS. Example prompt:

```
Write a 5-minute podcast script between two hosts discussing [TOPIC].

Host A is curious and asks good questions.
Host B is knowledgeable and explains clearly.

Use the following research as source material:
{research_results}

Format as:
HOST_A: [line]
HOST_B: [line]
...
```

For personalized briefs, the agent uses the same tools as the Morning Briefing
agent (weather, calendar, news, commute) but formats output as a spoken script
instead of text.

## Dependencies

```
# Core
fastapi
uvicorn
podgen          # RSS feed generation
pydub           # Audio stitching
ffmpeg-python   # WAV → MP3 conversion

# Local TTS (pick one)
piper-tts       # Lightweight, CPU-only
kokoro          # High quality, small model
bark            # Most natural, needs GPU

# Cloud TTS (optional)
elevenlabs      # ElevenLabs API client

# NotebookLM (optional)
notebooklm-py   # Unofficial API client
# OR
playwright      # For browser automation approach
```
