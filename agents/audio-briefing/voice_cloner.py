#!/usr/bin/env python3
"""YouTube-to-Voicebox voice cloner.

Downloads audio from a YouTube URL, transcribes it with word-level timestamps
via Groq Whisper, finds the best 30-second clip of continuous speech, and
creates a Voicebox voice profile from it.

Usage:
    python3 voice_cloner.py "https://www.youtube.com/watch?v=..." --name "Speaker Name"

    # Use a longer or shorter clip (default 30s)
    python3 voice_cloner.py "https://youtu.be/..." --name "Speaker" --duration 45

    # Skip first N seconds (e.g., skip intro)
    python3 voice_cloner.py "https://youtu.be/..." --name "Speaker" --skip-start 60

Requirements:
    - yt-dlp (brew install yt-dlp)
    - ffmpeg (brew install ffmpeg)
    - Groq API key in .env or GROQ_API_KEY env var
    - Voicebox running on localhost:17493
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

# Load .env from project root
def _load_dotenv():
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
            if key and key not in os.environ:
                os.environ[key] = value

_load_dotenv()

VOICEBOX_URL = os.environ.get("VOICEBOX_URL", "http://localhost:17493")


def download_audio(url, output_dir, skip_start=0):
    """Download audio from YouTube URL as mono 16kHz WAV."""
    print(f"\n[1/5] Downloading audio from YouTube...")
    output_path = os.path.join(output_dir, "full_audio.wav")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-x",                          # extract audio
        "--audio-format", "wav",
        "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000",  # mono 16kHz
        "-o", os.path.join(output_dir, "full_audio.%(ext)s"),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  yt-dlp stderr: {result.stderr[:500]}")
        raise RuntimeError(f"yt-dlp failed: {result.stderr[:200]}")

    if not os.path.exists(output_path):
        # yt-dlp sometimes names differently, find the wav
        for f in os.listdir(output_dir):
            if f.endswith(".wav"):
                output_path = os.path.join(output_dir, f)
                break

    # Get duration
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", output_path],
        capture_output=True, text=True,
    )
    duration = float(probe.stdout.strip())
    print(f"  Downloaded: {duration:.1f}s total")

    # Extract first 5 minutes (after skip_start) for transcription
    # to stay under Groq's 25MB limit (~960KB per 30s at 16kHz mono)
    max_chunk = 300  # 5 minutes
    chunk_path = os.path.join(output_dir, "chunk.wav")
    cmd = [
        "ffmpeg", "-y",
        "-i", output_path,
        "-ss", str(skip_start),
        "-t", str(max_chunk),
        "-ac", "1", "-ar", "16000",
        chunk_path,
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)

    chunk_size = os.path.getsize(chunk_path)
    print(f"  Chunk for transcription: {min(max_chunk, duration - skip_start):.0f}s ({chunk_size / 1024 / 1024:.1f}MB)")

    return output_path, chunk_path, duration


def transcribe(audio_path):
    """Transcribe audio with word-level timestamps via Groq Whisper."""
    print(f"\n[2/5] Transcribing with Groq Whisper...")

    from groq import Groq

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    with open(audio_path, "rb") as f:
        transcription = client.audio.transcriptions.create(
            file=f,
            model="whisper-large-v3-turbo",
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
            language="en",
            temperature=0.0,
        )

    # Parse the response
    if hasattr(transcription, 'model_dump'):
        data = transcription.model_dump()
    elif isinstance(transcription, dict):
        data = transcription
    else:
        data = json.loads(transcription) if isinstance(transcription, str) else {"text": str(transcription)}

    words = data.get("words", [])
    segments = data.get("segments", [])
    text = data.get("text", "")

    print(f"  Transcribed: {len(words)} words, {len(segments)} segments")
    print(f"  Full text preview: {text[:120]}...")

    return words, segments, text


def find_best_segment(words, segments, target_duration=30, skip_start=0):
    """Find the best continuous speech segment of target_duration seconds.

    Scores windows by:
    - Word density (more words = more speech = better voice sample)
    - Avoids gaps > 2 seconds (indicates pauses, music, or silence)
    """
    print(f"\n[3/5] Finding best {target_duration}s speech segment...")

    if not words:
        # Fallback to segments if no word-level timestamps
        if segments:
            best_start = segments[0].get("start", 0)
            print(f"  No word timestamps, using first segment at {best_start:.1f}s")
            return best_start + skip_start, segments[0].get("text", "")[:500]
        raise ValueError("No transcription data — cannot find speech segment")

    # Sliding window over words to find densest speech
    best_score = -1
    best_start = 0
    best_end = 0
    best_word_indices = (0, 0)
    best_max_gap = 0
    best_gap_penalty = 0

    for i in range(len(words)):
        w_start = words[i].get("start", 0)
        window_end = w_start + target_duration

        # Find all words in this window
        j = i
        while j < len(words) and words[j].get("start", 0) < window_end:
            j += 1

        if j <= i:
            continue

        window_words = words[i:j]
        word_count = len(window_words)

        # Check for large gaps (>2s) within the window
        window_max_gap = 0
        for k in range(1, len(window_words)):
            prev_end = window_words[k - 1].get("end", window_words[k - 1].get("start", 0) + 0.3)
            curr_start = window_words[k].get("start", 0)
            gap = curr_start - prev_end
            if gap > 0:
                window_max_gap = max(window_max_gap, gap)

        # Penalize windows with large gaps
        gap_penalty = max(0, window_max_gap - 2.0) * 10

        # Score = word count (simple and reliable) minus gap penalty
        score = word_count - gap_penalty

        if score > best_score:
            best_score = score
            best_start = w_start
            best_end = min(window_end, words[j - 1].get("end", window_end))
            best_word_indices = (i, j)
            best_max_gap = window_max_gap
            best_gap_penalty = gap_penalty

    # Extract reference text for the best segment
    ref_words = words[best_word_indices[0]:best_word_indices[1]]
    reference_text = " ".join(w.get("word", "").strip() for w in ref_words)

    actual_start = best_start + skip_start
    print(f"  Best segment: {actual_start:.1f}s - {actual_start + target_duration:.1f}s")
    print(f"  Word density: {len(ref_words)} words in {target_duration}s")
    print(f"  Max gap: {best_max_gap:.1f}s (penalty: {best_gap_penalty:.1f})")
    print(f"  Reference text: {reference_text[:100]}...")

    return actual_start, reference_text


def extract_clip(full_audio_path, start_time, duration, output_dir):
    """Extract the selected clip as a WAV file."""
    print(f"\n[4/5] Extracting {duration}s clip starting at {start_time:.1f}s...")

    clip_path = os.path.join(output_dir, "voice_sample.wav")
    cmd = [
        "ffmpeg", "-y",
        "-i", full_audio_path,
        "-ss", str(start_time),
        "-t", str(duration),
        "-ac", "1", "-ar", "16000",
        clip_path,
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)

    size = os.path.getsize(clip_path)
    print(f"  Clip saved: {clip_path} ({size / 1024:.0f}KB)")

    return clip_path


def create_voicebox_profile(name, clip_path, reference_text, language="en"):
    """Create a Voicebox voice profile and upload the audio sample."""
    print(f"\n[5/5] Creating Voicebox profile '{name}'...")

    # Step 1: Create empty profile
    profile_data = json.dumps({
        "name": name,
        "language": language,
        "description": f"Cloned from YouTube video",
    }).encode()

    req = urllib.request.Request(
        f"{VOICEBOX_URL}/profiles",
        data=profile_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        profile = json.loads(resp.read())

    profile_id = profile["id"]
    print(f"  Profile created: {profile_id}")

    # Step 2: Upload audio sample via multipart form
    boundary = "----VoiceCloner" + os.urandom(8).hex()
    body = b""

    # File field
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="file"; filename="voice_sample.wav"\r\n'.encode()
    body += b"Content-Type: audio/wav\r\n\r\n"
    with open(clip_path, "rb") as f:
        body += f.read()
    body += b"\r\n"

    # Reference text field
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="reference_text"\r\n\r\n'.encode()
    body += reference_text.encode()
    body += b"\r\n"

    body += f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{VOICEBOX_URL}/profiles/{profile_id}/samples",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        sample = json.loads(resp.read())

    print(f"  Sample uploaded: {sample.get('id', 'ok')}")
    print(f"\n{'='*60}")
    print(f"  PROFILE READY: {name}")
    print(f"  Profile ID:    {profile_id}")
    print(f"  Use in podcast server:")
    print(f"    VOICEBOX_PROFILE_A={profile_id}")
    print(f"{'='*60}\n")

    return profile_id


def main():
    parser = argparse.ArgumentParser(
        description="Clone a voice from YouTube for use in Voicebox podcasts",
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--name", required=True, help="Name for the voice profile")
    parser.add_argument("--duration", type=int, default=30, help="Clip duration in seconds (default: 30)")
    parser.add_argument("--skip-start", type=int, default=0, help="Skip first N seconds of video (e.g., skip intro)")
    parser.add_argument("--language", default="en", help="Language code (default: en)")
    parser.add_argument("--keep-files", action="store_true", help="Keep temporary audio files")

    args = parser.parse_args()

    # Validate Voicebox is running
    try:
        req = urllib.request.Request(f"{VOICEBOX_URL}/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            health = json.loads(resp.read())
            if not health.get("model_loaded"):
                print("ERROR: Voicebox model not loaded yet. Wait for it to finish loading.")
                sys.exit(1)
    except Exception:
        print(f"ERROR: Voicebox not reachable at {VOICEBOX_URL}")
        print("Start Voicebox first, then try again.")
        sys.exit(1)

    # Validate Groq API key
    if not os.environ.get("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY not set. Add it to .env or export it.")
        sys.exit(1)

    # Work in temp directory
    work_dir = tempfile.mkdtemp(prefix="voice_cloner_")
    print(f"Working directory: {work_dir}")

    try:
        # Pipeline
        full_audio, chunk_audio, total_duration = download_audio(args.url, work_dir, args.skip_start)
        words, segments, text = transcribe(chunk_audio)
        start_time, reference_text = find_best_segment(words, segments, args.duration, args.skip_start)
        clip_path = extract_clip(full_audio, start_time, args.duration, work_dir)
        profile_id = create_voicebox_profile(args.name, clip_path, reference_text, args.language)

        # Output for scripts/automation
        print(json.dumps({
            "profile_id": profile_id,
            "name": args.name,
            "clip_start": start_time,
            "clip_duration": args.duration,
            "reference_text_preview": reference_text[:200],
        }, indent=2))

    finally:
        if not args.keep_files:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)
            print(f"Cleaned up temp files")
        else:
            print(f"Temp files kept at: {work_dir}")


if __name__ == "__main__":
    main()
