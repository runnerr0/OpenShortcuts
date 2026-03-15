# OpenShortcuts Roadmap

## MVP — What We're Shipping First

The MVP is a working collection of iOS Shortcuts with server-side agents,
documented well enough that someone can clone the repo and get running.

### Shortcuts (MVP)

| Shortcut | Status | Category |
|----------|--------|----------|
| Universal Transcribe | Done | Speech |
| Link Saver | Done | Productivity |
| Receipt Scanner | Done | Productivity |
| Morning Briefing (text) | Done | AI / Agents |

### Agent Infrastructure (MVP)

| Component | Status |
|-----------|--------|
| Agent architecture (4 hosting strategies) | Done |
| Morning Briefing agent (Bedrock, OpenAI, LangGraph, ECS) | Done |
| Shared tools (weather, news, calendar, commute) | Done |
| Setup wizard | Done |

### Still Needed for MVP

- [ ] End-to-end setup guide: clone → configure → install shortcut → working demo
- [ ] At least one agent strategy fully tested with real API keys
- [ ] Setup wizard generates working shortcut files
- [ ] Basic validation script for shortcut files

---

## Futures — Ideas Worth Building

These are validated ideas with clear architecture but not blocking the MVP.

### Audio Briefing / Personal Podcast Agent

**Concept**: Instead of text briefings, generate audio content delivered as
episodes in your personal podcast feed. Ask Siri for a podcast about any topic
and it shows up in your podcast app.

**Three tiers**:

| Tier | TTS Engine | Quality | Privacy | Cost |
|------|-----------|---------|---------|------|
| Local | Piper / Kokoro / F5-TTS | Good | Full privacy | Free |
| Cloud (ElevenLabs) | ElevenLabs API | Excellent | Cloud-processed | ~$5-22/mo |
| Cloud (NotebookLM) | Google NotebookLM | Best (two hosts) | Google-hosted | Free-$20/mo |

**Architecture**:
```
Shortcut: "Make me a podcast about [topic]"
    → Agent researches topic (web search, summarize)
    → Generates conversation script (two hosts discussing)
    → TTS engine renders audio (local or cloud)
    → ffmpeg converts to MP3
    → Drops into /var/www/podcast/episodes/
    → Python regenerates RSS feed.xml
    → Podcast app picks up new episode
```

**Podcast delivery**: Self-hosted RSS feed (nginx + static XML + MP3 files).
Apple Podcasts, Overcast, and Pocket Casts support private RSS URLs.
Add `<itunes:block>Yes</itunes:block>` to stay out of public directories.
Password-protect via nginx basic auth for true privacy.

See: `agents/audio-briefing/`

### More Shortcut Ideas

- **Clipboard Rewriter** — Rewrite clipboard contents (tone, grammar, translate)
- **Voice Structured Notes** — Dictate → structured markdown/JSON
- **Research Capture** — Save links with AI-generated summaries
- **Meeting Prep** — Summarize context before your next calendar event
- **Daily Digest** — End-of-day summary of what you did (calendar + git + notes)
- **Expense Logger** — Photo of receipt → structured expense entry
- **Quick Timer with Context** — "Remind me to check the laundry" → smart timer

### Infrastructure Ideas

- **Shortcut catalog website** — Browse and install via QR codes
- **Shared tool registry** — Reusable tool definitions across agents
- **Agent-to-agent communication** — Chain agents together
- **Webhook relay** — Ngrok/Cloudflare tunnel for home server access from anywhere
