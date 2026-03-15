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

#### Recommended: Native Podcast Models (no stitching needed)

These models generate multi-speaker dialogue in a single pass with natural
turn-taking, backchannels, and even laughter/sighs.

| Engine | Params | Speakers | Hardware | Quality | Notes |
|--------|--------|----------|----------|---------|-------|
| **[Dia](https://github.com/nari-labs/dia)** | 1.6B | 2 native | GPU, ~10GB VRAM | Excellent | Built to replicate NotebookLM. Use `[S1]`/`[S2]` tags. Generates laughter, coughs inline. Apache 2.0. |
| **[Sesame CSM](https://github.com/SesameAILabs/csm)** | 1B | 2 native | GPU | Very Good | Uses previous dialogue turns as context for coherent back-and-forth. Apache 2.0. |

#### Alternative: High-Quality Per-Voice Models (stitch with pydub/ffmpeg)

Generate each host's lines separately with different voices, then concatenate.

| Engine | Params | Voice Clone | Hardware | Quality | Notes |
|--------|--------|-------------|----------|---------|-------|
| **[Chatterbox](https://github.com/resemble-ai/chatterbox)** | 350-500M | Yes (5s) | GPU (AMD too) | Excellent | Beats ElevenLabs in blind tests. Emotion control. MIT. |
| **[Orpheus](https://github.com/canopyai/Orpheus-TTS)** | 3B | Yes | GPU, 12GB+ | Excellent | Inline emotion tags (`<laugh>`, `<sigh>`). 8 built-in voices. Apache 2.0. |
| **[F5-TTS](https://github.com/SWivid/F5-TTS)** | 335M | Yes (best) | GPU, ~5GB | Excellent | Best open-source voice cloning quality. MIT. |
| **[Kokoro](https://github.com/hexgrad/kokoro)** | 82M | No | CPU or GPU | Very Good | Best quality-to-size ratio. 54 voices, 8 languages. Apache 2.0. |

#### CPU-Only Options (Raspberry Pi / NAS)

| Engine | Voice Clone | Quality | Notes |
|--------|-------------|---------|-------|
| **[Piper](https://github.com/OHF-Voice/piper1-gpl)** | No | Good | Fastest. Runs on RPi 4 at 95% realtime. Dozens of voices. |
| **[NeuTTS Air](https://github.com/neuphonic/neutts)** | Yes (3s) | Good | 748M on Qwen backbone. Q4 GGUF uses 400-600MB RAM. Runs on RPi 5. Apache 2.0. |
| **[Kokoro](https://github.com/hexgrad/kokoro)** | No | Very Good | 82M params. Also runs on CPU. Best quality without GPU. |

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

The agent writes a conversation script before TTS. The format depends on the
TTS engine:

**For Dia (recommended local)** — uses `[S1]`/`[S2]` tags directly:
```
[S1] So today we're diving into quantum computing. What's the big deal?
[S2] Well, the simplest way to think about it is that regular computers
use bits — zeros and ones. Quantum computers use qubits, which can be
both at the same time. (laughs) I know, it sounds like magic.
[S1] That does sound like magic. So what can you actually do with that?
```

**For stitch-based engines** (Chatterbox, Orpheus, Kokoro, ElevenLabs):
```
HOST_A: So today we're diving into quantum computing. What's the big deal?
HOST_B: Well, the simplest way to think about it...
```
Each host's lines are rendered separately and concatenated with crossfades.

**Agent prompt for script generation:**
```
Write a {duration}-minute podcast script between two hosts discussing [TOPIC].

Host A (the curious one) asks good questions and reacts naturally.
Host B (the expert) explains clearly with analogies.

Incorporate these research findings as source material:
{research_results}

Make it conversational — include reactions, brief agreements ("right", "exactly"),
and natural transitions. This will be read by TTS, so avoid visual formatting.
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
pydub           # Audio stitching (for multi-voice concatenation)
ffmpeg-python   # WAV → MP3 conversion

# Local TTS — Native podcast (pick one)
dia-tts         # Best: 2-speaker dialogue in one pass, 10GB VRAM
# OR sesame-csm  # Conversational awareness, GPU required

# Local TTS — Per-voice stitch (pick one)
chatterbox-tts  # Beats ElevenLabs in blind tests, GPU
orpheus-tts     # Most emotionally expressive, 12GB+ VRAM
f5-tts          # Best voice cloning, 5GB VRAM
kokoro          # Best without GPU, 82M params, CPU-capable

# Local TTS — CPU-only (pick one)
piper-tts       # Fastest, runs on Raspberry Pi
# neutts        # Voice cloning on CPU, 400-600MB RAM

# Cloud TTS (optional)
elevenlabs      # ElevenLabs API client ($5-22/mo)

# NotebookLM (optional)
notebooklm-py   # Unofficial API client (free tier: 3/day)
# OR
playwright      # For browser automation approach
```
