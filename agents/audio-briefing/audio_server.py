#!/usr/bin/env python3
"""Audio Briefing agent — generates podcast-style audio from AI briefings.

Reuses the shared tools from morning-briefing. Adds:
- Two-host podcast script generation via LLM
- Text-to-speech via Voicebox (local Qwen3-TTS) or edge-tts fallback
- Audio stitching and MP3 output
- Podcast RSS feed with enclosures

Usage:
    # Start the server (Groq is free and fast)
    GROQ_API_KEY=gsk_... LLM_PROVIDER=groq python3 audio_server.py

    # Generate a topic podcast
    curl -X POST http://localhost:8091/podcast \
      -H "Content-Type: application/json" \
      -d '{"topic": "quantum computing"}'

    # Generate a morning briefing podcast
    curl -X POST http://localhost:8091/podcast \
      -H "Content-Type: application/json" \
      -d '{"type": "briefing", "latitude": 37.7749, "longitude": -122.4194}'

    # List episodes
    curl http://localhost:8091/episodes

    # Get RSS feed (for podcast apps)
    curl http://localhost:8091/feed

TTS Engines (checked in order):
    1. ElevenLabs — best quality, huge voice library, API key required
    2. Voicebox (local Qwen3-TTS) — voice cloning, runs on localhost:17493
    3. edge-tts (free Microsoft TTS) — fallback, no setup needed

    Set TTS_ENGINE=elevenlabs, voicebox, or edge-tts to force one.

Environment variables:
    LLM_PROVIDER: "openai", "anthropic", or "groq" (default: groq)
    GROQ_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY
    LLM_MODEL: Model override (default varies by provider)
    PORT: Server port (default: 8091)
    EPISODES_DIR: Where to save audio files (default: ./episodes)
    TTS_ENGINE: Force "elevenlabs", "voicebox", or "edge-tts" (default: auto-detect)
    ELEVENLABS_API_KEY: ElevenLabs API key
    ELEVENLABS_VOICE_A: Voice ID for Host A (default: Rachel)
    ELEVENLABS_VOICE_B: Voice ID for Host B (default: Adam)
    ELEVENLABS_MODEL: Model ID (default: eleven_multilingual_v2)
    VOICEBOX_URL: Voicebox API URL (default: http://localhost:17493)
    VOICEBOX_PROFILE_A: Voicebox profile ID for Host A
    VOICEBOX_PROFILE_B: Voicebox profile ID for Host B
    HOST_A_VOICE: edge-tts voice for Host A (default: en-US-JennyNeural)
    HOST_B_VOICE: edge-tts voice for Host B (default: en-US-GuyNeural)
"""

import asyncio
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Load .env from project root (no external deps needed)
def _load_dotenv():
    """Load .env file from the repo root if it exists."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:  # don't override explicit env vars
                os.environ[key] = value

_load_dotenv()

# Add parent paths for shared tools (morning-briefing)
_mb_dir = os.path.join(os.path.dirname(__file__), "..", "morning-briefing")
sys.path.insert(0, _mb_dir)
sys.path.insert(0, os.path.join(_mb_dir, "ecs-container"))
from tools import TOOL_SCHEMAS, execute_tool, get_weather, get_news, web_search
from prompts import build_user_prompt

# Import podcast-specific prompts from this directory
# (import by file path to avoid shadowing morning-briefing/prompts.py)
import importlib.util
_podcast_prompts_path = os.path.join(os.path.dirname(__file__), "prompts.py")
_spec = importlib.util.spec_from_file_location("podcast_prompts", _podcast_prompts_path)
_podcast_prompts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_podcast_prompts)
PODCAST_SYSTEM_PROMPT = _podcast_prompts.PODCAST_SYSTEM_PROMPT
BRIEFING_PODCAST_PROMPT = _podcast_prompts.BRIEFING_PODCAST_PROMPT
TOPIC_PODCAST_PROMPT = _podcast_prompts.TOPIC_PODCAST_PROMPT
MORNING_TOUCH_PROMPT = _podcast_prompts.MORNING_TOUCH_PROMPT
DEEP_BRIEF_PROMPT = _podcast_prompts.DEEP_BRIEF_PROMPT

# --- Configuration ---

EPISODES_DIR = Path(os.environ.get("EPISODES_DIR", os.path.join(os.path.dirname(__file__), "episodes")))
VOICEBOX_URL = os.environ.get("VOICEBOX_URL", "http://localhost:17493")
VOICEBOX_PROFILE_A = os.environ.get("VOICEBOX_PROFILE_A", "")
VOICEBOX_PROFILE_B = os.environ.get("VOICEBOX_PROFILE_B", "")
HOST_A_VOICE = os.environ.get("HOST_A_VOICE", "en-US-JennyNeural")
HOST_B_VOICE = os.environ.get("HOST_B_VOICE", "en-US-GuyNeural")
ELEVENLABS_VOICE_A = os.environ.get("ELEVENLABS_VOICE_A", "Rachel")
ELEVENLABS_VOICE_B = os.environ.get("ELEVENLABS_VOICE_B", "Adam")
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
TTS_ENGINE = os.environ.get("TTS_ENGINE", "auto")


# --- TTS Engine Detection ---

def _check_voicebox():
    """Check if Voicebox is running and return available profiles."""
    try:
        req = urllib.request.Request(f"{VOICEBOX_URL}/health", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            health = json.loads(resp.read())

        req = urllib.request.Request(f"{VOICEBOX_URL}/profiles", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            profiles = json.loads(resp.read())

        return {
            "available": True,
            "model_loaded": health.get("model_loaded", False),
            "profiles": profiles,
        }
    except Exception:
        return {"available": False, "profiles": []}


def _detect_tts_engine():
    """Auto-detect the best available TTS engine."""
    if TTS_ENGINE in ("voicebox", "edge-tts", "elevenlabs"):
        return TTS_ENGINE

    # Auto-detect: prefer ElevenLabs if key is set, then Voicebox, then edge-tts
    if os.environ.get("ELEVENLABS_API_KEY"):
        return "elevenlabs"
    vb = _check_voicebox()
    if vb["available"]:
        return "voicebox"
    return "edge-tts"


# --- LLM Client Setup ---

def _get_client_and_model():
    """Get LLM client and model based on provider config."""
    from openai import OpenAI

    provider = os.environ.get("LLM_PROVIDER", "groq")

    if provider == "groq":
        client = OpenAI(
            api_key=os.environ.get("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
        )
        model = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
    elif provider == "openai":
        client = OpenAI()
        model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    else:
        raise ValueError(f"Unsupported provider for podcast: {provider}. Use groq or openai.")

    return client, model


def _clean_message(message):
    """Convert an OpenAI message to a dict, stripping unsupported fields."""
    d = message.model_dump()
    d.pop("annotations", None)
    return {k: v for k, v in d.items() if v is not None}


# --- Agent Loop ---

def _run_loop(client, model, system_prompt, user_prompt):
    """Agent loop: gather info with tools, then generate podcast script."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    for _ in range(5):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        message = choice.message
        messages.append(_clean_message(message))

        if not message.tool_calls:
            return message.content

        for tool_call in message.tool_calls:
            args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
            result = execute_tool(tool_call.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    return "Script generation timed out."


def _gather_briefing_data(latitude=None, longitude=None, preferences=None, location_name=None):
    """Pre-gather weather, news, and trending topics for briefing mode."""
    data_sections = []

    if latitude and longitude:
        try:
            weather = get_weather(latitude, longitude)
            data_sections.append(f"WEATHER DATA:\n{json.dumps(weather, indent=2)}")
        except Exception as e:
            data_sections.append(f"WEATHER: unavailable ({e})")

    try:
        news = get_news(category="general", count=8)
        data_sections.append(f"TOP TECH NEWS (Hacker News):\n{json.dumps(news, indent=2)}")
    except Exception as e:
        data_sections.append(f"TECH NEWS: unavailable ({e})")

    # Local news for the user's city
    city = location_name or "San Francisco"
    try:
        local = web_search(f"{city} local news today 2026", count=5)
        data_sections.append(f"LOCAL NEWS ({city.upper()}):\n{json.dumps(local, indent=2)}")
    except Exception as e:
        data_sections.append(f"LOCAL NEWS: unavailable ({e})")

    if preferences:
        try:
            trending = web_search(f"latest {preferences} news today", count=5)
            data_sections.append(f"TRENDING IN {preferences.upper()}:\n{json.dumps(trending, indent=2)}")
        except Exception as e:
            data_sections.append(f"TRENDING: unavailable ({e})")

    return "\n\n".join(data_sections)


def _gather_topic_research(topic):
    """Pre-gather research for a deep brief, organized by brief sections."""
    sections = {}

    # Section 1: Introduction — what it is, why it matters now
    print(f"  Research: introduction and context...")
    try:
        intro = web_search(f"what is {topic} explained 2026", count=5)
        sections["INTRODUCTION — What This Is and Why It Matters Now"] = json.dumps(intro, indent=2)
    except Exception as e:
        sections["INTRODUCTION"] = f"unavailable ({e})"

    # Section 2: Usage & Adoption — who's using it, how
    print(f"  Research: usage and adoption...")
    try:
        usage = web_search(f"{topic} adoption usage companies 2026", count=5)
        sections["USAGE & ADOPTION — Who Is Using This and How"] = json.dumps(usage, indent=2)
    except Exception as e:
        sections["USAGE & ADOPTION"] = f"unavailable ({e})"

    # Section 3: Community & Ecosystem Impact
    print(f"  Research: community and ecosystem impact...")
    try:
        impact = web_search(f"{topic} impact ecosystem community 2026", count=5)
        sections["COMMUNITY & ECOSYSTEM IMPACT"] = json.dumps(impact, indent=2)
    except Exception as e:
        sections["COMMUNITY & ECOSYSTEM IMPACT"] = f"unavailable ({e})"

    # Section 4: Implications — short and long term
    print(f"  Research: implications and predictions...")
    try:
        implications = web_search(f"{topic} implications future predictions 2026", count=5)
        sections["SHORT & LONG TERM IMPLICATIONS"] = json.dumps(implications, indent=2)
    except Exception as e:
        sections["IMPLICATIONS"] = f"unavailable ({e})"

    # Also grab latest news headlines
    try:
        news = get_news(category="general", count=5)
        sections["RELATED NEWS HEADLINES"] = json.dumps(news, indent=2)
    except Exception:
        pass

    # Format as structured research document
    parts = []
    for heading, data in sections.items():
        parts.append(f"=== {heading} ===\n{data}")

    research = "\n\n".join(parts)
    print(f"  Research complete ({len(research)} chars across {len(sections)} sections)")
    return research


def generate_podcast_script(topic=None, brief_type=None, latitude=None, longitude=None,
                            preferences=None, location_name=None):
    """Generate a two-host podcast script using LLM + tools.

    Args:
        topic: Topic string for topic/deep briefs (None for morning touch)
        brief_type: "morning_touch", "deep_brief", or "topic" (legacy)
        latitude/longitude: For weather in morning touch
        preferences: User interest areas
        location_name: City name for local news
    """
    client, model = _get_client_and_model()
    system = PODCAST_SYSTEM_PROMPT + "\n\nWrite the podcast script using ONLY the data provided below. Do NOT call any tools."

    # Determine brief type
    if brief_type is None:
        brief_type = "deep_brief" if topic else "morning_touch"

    if brief_type == "deep_brief" and topic:
        # Deep brief: structured research organized by brief sections
        print(f"  Deep brief: {topic}")
        research_data = _gather_topic_research(topic)

        user_prompt = DEEP_BRIEF_PROMPT.format(topic=topic)
        user_prompt += f"\n\nHere is the research data organized by brief section:\n\n{research_data}"

    elif brief_type == "topic" and topic:
        # Legacy topic mode: lighter research, less structured
        print(f"  Topic brief: {topic}")
        data_sections = []

        try:
            results = web_search(f"latest {topic} news today 2026", count=8)
            data_sections.append(f"WEB SEARCH RESULTS:\n{json.dumps(results, indent=2)}")
        except Exception as e:
            data_sections.append(f"WEB SEARCH: unavailable ({e})")

        try:
            news = get_news(category="general", count=5)
            data_sections.append(f"TOP NEWS:\n{json.dumps(news, indent=2)}")
        except Exception:
            pass

        research_data = "\n\n".join(data_sections)
        print(f"  Research gathered ({len(research_data)} chars)")

        user_prompt = TOPIC_PODCAST_PROMPT.format(topic=topic)
        user_prompt += f"\n\nHere is the research data to base the discussion on:\n\n{research_data}"

    else:
        # Morning touch: light daily briefing
        print("  Morning touch briefing...")
        briefing_data = _gather_briefing_data(latitude, longitude, preferences, location_name)
        print(f"  Data gathered ({len(briefing_data)} chars)")

        user_prompt = MORNING_TOUCH_PROMPT + f"\n\nHere is the data for today's briefing:\n\n{briefing_data}"

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]
    response = client.chat.completions.create(model=model, messages=messages)
    return response.choices[0].message.content


# --- Script Parser ---

def parse_script(script_text):
    """Parse HOST_A:/HOST_B: script into list of (speaker, text) tuples."""
    lines = []
    current_speaker = None
    current_text = []

    for line in script_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        match = re.match(r"^(HOST_[AB]):\s*(.+)", line)
        if match:
            if current_speaker and current_text:
                lines.append((current_speaker, " ".join(current_text)))
            current_speaker = match.group(1)
            current_text = [match.group(2)]
        elif current_speaker:
            current_text.append(line)

    if current_speaker and current_text:
        lines.append((current_speaker, " ".join(current_text)))

    return lines


# --- TTS: Voicebox ---

def _voicebox_generate(text, profile_id, output_path):
    """Generate speech via Voicebox API and save to file."""
    payload = json.dumps({
        "text": text,
        "profile_id": profile_id,
        "language": "en",
    }).encode()

    req = urllib.request.Request(
        f"{VOICEBOX_URL}/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())

    generation_id = result["id"]

    # Download the audio file
    audio_req = urllib.request.Request(f"{VOICEBOX_URL}/audio/{generation_id}")
    with urllib.request.urlopen(audio_req, timeout=30) as resp:
        audio_data = resp.read()

    with open(output_path, "wb") as f:
        f.write(audio_data)

    return result


def _voicebox_list_profiles():
    """List available Voicebox voice profiles."""
    req = urllib.request.Request(f"{VOICEBOX_URL}/profiles")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


# --- TTS: ElevenLabs ---

def _elevenlabs_generate(text, voice, output_path):
    """Generate speech via ElevenLabs API and save to file."""
    from elevenlabs import ElevenLabs

    client = ElevenLabs(api_key=os.environ.get("ELEVENLABS_API_KEY"))

    audio_generator = client.text_to_speech.convert(
        text=text,
        voice_id=voice,
        model_id=ELEVENLABS_MODEL,
        output_format="mp3_44100_128",
    )

    # The SDK returns a generator of bytes chunks
    with open(output_path, "wb") as f:
        for chunk in audio_generator:
            f.write(chunk)


def _elevenlabs_list_voices():
    """List available ElevenLabs voices."""
    from elevenlabs import ElevenLabs

    client = ElevenLabs(api_key=os.environ.get("ELEVENLABS_API_KEY"))
    response = client.voices.get_all()
    return [
        {
            "voice_id": v.voice_id,
            "name": v.name,
            "category": getattr(v, "category", "unknown"),
            "labels": dict(v.labels) if v.labels else {},
        }
        for v in response.voices
    ]


# --- TTS: edge-tts ---

async def _edge_tts_segment(text, voice, output_path):
    """Generate a single TTS audio segment using edge-tts."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


# --- Audio Generation (unified) ---

def _resolve_voicebox_profile(name_or_id, profiles):
    """Resolve a profile name or ID to a profile ID."""
    if not name_or_id:
        return None
    # Check if it's already a UUID
    for p in profiles:
        if p["id"] == name_or_id:
            return name_or_id
    # Try matching by name (case-insensitive, partial match)
    name_lower = name_or_id.lower()
    for p in profiles:
        if p["name"].lower() == name_lower or name_lower in p["name"].lower():
            return p["id"]
    return name_or_id  # Assume it's an ID even if not found


def _get_voicebox_profiles():
    """Resolve which Voicebox profiles to use for Host A and Host B."""
    profiles = _voicebox_list_profiles()
    if not profiles:
        raise ValueError("No Voicebox voice profiles found. Create at least one profile in the Voicebox app.")

    profile_a = _resolve_voicebox_profile(VOICEBOX_PROFILE_A, profiles) if VOICEBOX_PROFILE_A else None
    profile_b = _resolve_voicebox_profile(VOICEBOX_PROFILE_B, profiles) if VOICEBOX_PROFILE_B else None

    if profile_a and profile_b:
        return profile_a, profile_b

    # Auto-select: use first two profiles, or same profile for both
    profile_a = profile_a or profiles[0]["id"]
    profile_b = profile_b or (profiles[1]["id"] if len(profiles) > 1 else profiles[0]["id"])

    if len(profiles) == 1:
        print(f"  Only 1 Voicebox profile found — using it for both hosts")
    else:
        print(f"  Using profiles: Host A = {profiles[0]['name']}, Host B = {profiles[1]['name']}")

    return profile_a, profile_b


async def generate_audio(script_lines, output_path, engine):
    """Convert parsed script lines to a single MP3 file.

    Supports Voicebox (local Qwen3-TTS) or edge-tts as the TTS backend.
    """
    from pydub import AudioSegment

    segments = []
    temp_files = []

    # Resolve voice config based on engine
    if engine == "elevenlabs":
        voice_map = {"HOST_A": ELEVENLABS_VOICE_A, "HOST_B": ELEVENLABS_VOICE_B}
    elif engine == "voicebox":
        profile_a, profile_b = _get_voicebox_profiles()
        voice_map = {"HOST_A": profile_a, "HOST_B": profile_b}
    else:
        voice_map = {"HOST_A": HOST_A_VOICE, "HOST_B": HOST_B_VOICE}

    try:
        for i, (speaker, text) in enumerate(script_lines):
            voice = voice_map.get(speaker, voice_map["HOST_A"])
            ext = "wav" if engine == "voicebox" else "mp3"  # elevenlabs and edge-tts both output mp3
            temp_path = os.path.join(tempfile.gettempdir(), f"podcast_seg_{i}.{ext}")
            temp_files.append(temp_path)

            print(f"  TTS [{engine}] [{speaker}]: {text[:60]}...")

            if engine == "elevenlabs":
                _elevenlabs_generate(text, voice, temp_path)
                segment = AudioSegment.from_mp3(temp_path)
            elif engine == "voicebox":
                _voicebox_generate(text, voice, temp_path)
                segment = AudioSegment.from_wav(temp_path)
            else:
                await _edge_tts_segment(text, voice, temp_path)
                segment = AudioSegment.from_mp3(temp_path)

            segments.append(segment)

            # Short pause between speakers (300ms)
            segments.append(AudioSegment.silent(duration=300))

        if not segments:
            raise ValueError("No audio segments generated")

        # Stitch all segments
        combined = segments[0]
        for seg in segments[1:]:
            combined += seg

        # Export raw stitched audio as temporary WAV for post-processing
        import subprocess as _sp
        raw_path = output_path + ".raw.wav"
        combined.export(raw_path, format="wav")
        duration_sec = len(combined) / 1000

        # Post-processing: gentle EQ + loudness normalization
        # Clean chain — no dynaudnorm (causes pumping), no heavy compression
        # Lowpass at 10 kHz removes TTS high-frequency artifacts
        print(f"  Post-processing: mastering to -16 LUFS...")
        master_filter = (
            "highpass=f=80:poles=2,"
            "lowpass=f=10000:poles=2,"
            "equalizer=f=250:t=q:w=1.0:g=-3,"
            "equalizer=f=500:t=q:w=1.5:g=-2,"
            "equalizer=f=2500:t=q:w=1.0:g=1.5,"
            "loudnorm=I=-16:LRA=11:TP=-1"
        )
        _sp.run([
            "ffmpeg", "-hide_banner", "-y",
            "-i", raw_path,
            "-af", master_filter,
            "-ar", "48000",
            "-c:a", "libmp3lame", "-b:a", "128k",
            output_path,
        ], capture_output=True, text=True, check=True)

        # Clean up raw WAV
        try:
            os.unlink(raw_path)
        except OSError:
            pass

        file_size = os.path.getsize(output_path)

        return {
            "duration_seconds": round(duration_sec, 1),
            "file_size_bytes": file_size,
            "segments": len(script_lines),
            "tts_engine": engine,
            "mastered": True,
        }

    finally:
        for f in temp_files:
            try:
                os.unlink(f)
            except OSError:
                pass


# --- Episode Management ---

_episodes = []


def _save_episode(title, script_text, audio_info, filename):
    """Record episode metadata."""
    episode = {
        "title": title,
        "filename": filename,
        "script": script_text,
        "duration_seconds": audio_info["duration_seconds"],
        "file_size_bytes": audio_info["file_size_bytes"],
        "segments": audio_info["segments"],
        "tts_engine": audio_info.get("tts_engine", "unknown"),
        "created_at": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        "created_iso": datetime.now(timezone.utc).isoformat(),
    }
    _episodes.insert(0, episode)
    return episode


def _build_rss(base_url):
    """Build RSS 2.0 podcast feed."""
    items = ""
    for ep in _episodes:
        url = f"{base_url}/episodes/{ep['filename']}"
        items += f"""    <item>
      <title>{_xml_escape(ep['title'])}</title>
      <description>{_xml_escape(ep.get('script', '')[:500])}</description>
      <enclosure url="{url}" length="{ep['file_size_bytes']}" type="audio/mpeg"/>
      <pubDate>{ep['created_at']}</pubDate>
      <guid isPermaLink="false">{ep['filename']}</guid>
      <itunes:duration>{int(ep['duration_seconds'])}</itunes:duration>
    </item>
"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>My Private Briefing</title>
    <description>AI-generated personal briefings</description>
    <language>en-us</language>
    <lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
{items}  </channel>
</rss>"""


def _xml_escape(text):
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# --- HTTP Server ---

class PodcastHandler(BaseHTTPRequestHandler):

    def _send_json(self, status, data):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}

        if self.path == "/podcast":
            self._handle_podcast(body)
        else:
            self.send_error(404)

    def _handle_podcast(self, body):
        topic = body.get("topic", "").strip()
        req_type = body.get("type", "topic")
        latitude = body.get("latitude")
        longitude = body.get("longitude")
        preferences = body.get("preferences")
        location_name = body.get("location_name", body.get("city"))

        # Map request type to brief_type
        # Backward compat: "briefing" → "morning_touch", "topic" → "deep_brief"
        brief_type_map = {
            "briefing": "morning_touch",
            "morning_touch": "morning_touch",
            "deep_brief": "deep_brief",
            "topic": "topic",
        }
        brief_type = brief_type_map.get(req_type, "topic")

        # If topic provided with briefing type, upgrade to deep_brief
        if topic and brief_type == "morning_touch":
            brief_type = "deep_brief"

        if brief_type in ("topic", "deep_brief") and not topic:
            topic = "today's most interesting tech news"

        # Detect TTS engine at request time (Voicebox may start/stop)
        engine = _detect_tts_engine()

        try:
            # Step 1: Generate script
            print(f"\n{'='*60}")
            print(f"Generating {brief_type}: {topic or 'morning briefing'}")
            print(f"TTS engine: {engine}")
            print(f"{'='*60}")

            t0 = time.time()
            script_text = generate_podcast_script(
                topic=topic if brief_type in ("topic", "deep_brief") else None,
                brief_type=brief_type,
                latitude=latitude,
                longitude=longitude,
                preferences=preferences,
                location_name=location_name,
            )
            t_script = time.time() - t0
            print(f"\nScript generated in {t_script:.1f}s")
            print(f"\n--- SCRIPT ---\n{script_text}\n--- END ---\n")

            # Step 2: Parse script
            script_lines = parse_script(script_text)
            if not script_lines:
                self._send_json(500, {
                    "error": "Failed to parse podcast script — LLM didn't use HOST_A:/HOST_B: format",
                    "raw_script": script_text,
                })
                return

            # Step 3: Generate audio
            print(f"Generating audio ({len(script_lines)} segments via {engine})...")
            t0 = time.time()

            EPISODES_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            slug = re.sub(r"[^a-z0-9]+", "-", (topic or "briefing").lower())[:40]
            filename = f"{timestamp}-{slug}.mp3"
            output_path = EPISODES_DIR / filename

            audio_info = asyncio.run(generate_audio(script_lines, str(output_path), engine))
            t_audio = time.time() - t0
            print(f"Audio generated in {t_audio:.1f}s -> {output_path}")

            # Step 4: Save episode
            title = topic.title() if topic else "Morning Briefing"
            episode = _save_episode(title, script_text, audio_info, filename)

            self._send_json(200, {
                "status": "ok",
                "episode": {
                    "title": title,
                    "filename": filename,
                    "duration_seconds": audio_info["duration_seconds"],
                    "segments": audio_info["segments"],
                    "brief_type": brief_type,
                    "tts_engine": engine,
                    "script_time_seconds": round(t_script, 1),
                    "audio_time_seconds": round(t_audio, 1),
                },
                "play": f"open {output_path}",
                "feed": "http://localhost:8091/feed",
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json(500, {"error": str(e)})

    def do_GET(self):
        if self.path == "/health":
            engine = _detect_tts_engine()
            vb = _check_voicebox() if engine == "voicebox" else {"available": False}
            self._send_json(200, {
                "status": "healthy",
                "tts_engine": engine,
                "voicebox": vb,
                "episodes": len(_episodes),
            })
            return

        if self.path == "/episodes":
            self._send_json(200, {"episodes": _episodes})
            return

        if self.path == "/voices":
            engine = _detect_tts_engine()
            if engine == "elevenlabs":
                try:
                    voices = _elevenlabs_list_voices()
                    self._send_json(200, {
                        "engine": "elevenlabs",
                        "host_a": ELEVENLABS_VOICE_A,
                        "host_b": ELEVENLABS_VOICE_B,
                        "model": ELEVENLABS_MODEL,
                        "available_voices": voices,
                    })
                except Exception as e:
                    self._send_json(500, {"error": str(e)})
            elif engine == "voicebox":
                profiles = _voicebox_list_profiles()
                self._send_json(200, {"engine": "voicebox", "profiles": profiles})
            else:
                self._send_json(200, {
                    "engine": "edge-tts",
                    "host_a": HOST_A_VOICE,
                    "host_b": HOST_B_VOICE,
                })
            return

        if self.path == "/feed":
            host = self.headers.get("Host", "localhost:8091")
            base_url = f"http://{host}"
            rss = _build_rss(base_url).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(rss)))
            self.end_headers()
            self.wfile.write(rss)
            return

        # Serve episode audio files
        if self.path.startswith("/episodes/"):
            filename = self.path.split("/episodes/", 1)[1]
            filename = os.path.basename(filename)
            filepath = EPISODES_DIR / filename
            if filepath.exists() and filepath.suffix == ".mp3":
                data = filepath.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

        self.send_error(404)

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    port = int(os.environ.get("PORT", 8091))
    EPISODES_DIR.mkdir(parents=True, exist_ok=True)
    provider = os.environ.get("LLM_PROVIDER", "groq")
    engine = _detect_tts_engine()

    # Show Voicebox profile info if available
    vb_info = ""
    if engine == "voicebox":
        vb = _check_voicebox()
        profiles = vb.get("profiles", [])
        vb_info = f"  Profiles: {len(profiles)} available"
        if profiles:
            for p in profiles[:4]:
                vb_info += f"\n    - {p.get('name', 'unnamed')} ({p['id'][:8]}...)"

    server = HTTPServer(("0.0.0.0", port), PodcastHandler)

    print(f"""
+------------------------------------------------------+
|          Audio Briefing / Podcast Agent               |
+------------------------------------------------------+
|  Server:    http://localhost:{port}                     |
|  LLM:       {provider:<42} |
|  TTS:       {engine:<42} |
|  Episodes:  {str(EPISODES_DIR):<42} |
+------------------------------------------------------+
|  POST /podcast  {{"topic": "..."}}                     |
|  POST /podcast  {{"type": "briefing", "latitude": N}} |
|  GET  /health                                        |
|  GET  /voices   (list available voices)              |
|  GET  /episodes (list generated episodes)            |
|  GET  /feed     (RSS for podcast apps)               |
+------------------------------------------------------+""")
    if engine == "elevenlabs":
        print(f"\n  ElevenLabs voices: {ELEVENLABS_VOICE_A} (A), {ELEVENLABS_VOICE_B} (B)")
        print(f"  Model: {ELEVENLABS_MODEL}")
        print(f"  Tip: GET /voices to see all available voices")
    elif vb_info:
        print(f"\n  Voicebox:\n{vb_info}")
    elif engine == "edge-tts":
        print(f"\n  Voices: {HOST_A_VOICE} (A), {HOST_B_VOICE} (B)")
        print(f"  Tip: Set ELEVENLABS_API_KEY for higher quality voices")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
