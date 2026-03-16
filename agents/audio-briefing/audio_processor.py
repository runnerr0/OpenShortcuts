#!/usr/bin/env python3
"""Podcast audio post-processor and mastering pipeline.

Applies broadcast-quality processing to podcast episodes:
  1. Noise reduction (FFT-based)
  2. Highpass filter (80 Hz — remove rumble)
  3. Lowpass filter (12 kHz — remove hiss/artifacts)
  4. Subtractive EQ (cut mud + boxiness)
  5. Compression (3:1, -24 dBFS threshold)
  6. Additive EQ (boost presence + articulation)
  7. De-essing (narrow cut at 6.5 kHz)
  8. Loudness normalization (-16 LUFS, -1 dBTP — Apple Podcasts standard)

Usage:
    # Process a single file
    python3 audio_processor.py episodes/podcast.mp3

    # Process with A/B comparison (keeps original)
    python3 audio_processor.py episodes/podcast.mp3 --compare

    # Process all episodes
    python3 audio_processor.py episodes/*.mp3

    # Custom LUFS target
    python3 audio_processor.py episodes/podcast.mp3 --lufs -14

    # Light processing (skip EQ, just normalize)
    python3 audio_processor.py episodes/podcast.mp3 --light
"""

import argparse
import json
import os
import subprocess
import sys
import shutil
import tempfile


def get_loudness(filepath):
    """Measure loudness using ffmpeg loudnorm in print mode."""
    cmd = [
        "ffmpeg", "-hide_banner", "-i", filepath,
        "-af", "loudnorm=I=-16:LRA=11:TP=-1:print_format=json",
        "-f", "null", "/dev/null",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Parse the JSON output from loudnorm (appears in stderr)
    stderr = result.stderr
    try:
        json_start = stderr.rindex("{")
        json_end = stderr.rindex("}") + 1
        data = json.loads(stderr[json_start:json_end])
        return data
    except (ValueError, json.JSONDecodeError):
        return None


def _processing_filters(preset="full"):
    """Return the core processing filters (without loudnorm)."""
    filters = []

    if preset == "full":
        # Clean mastering chain — gentle EQ + loudnorm
        # Avoids dynaudnorm (pumps noise) and heavy compression (artifacts)
        filters.append("highpass=f=80:poles=2")
        filters.append("lowpass=f=10000:poles=2")    # 10 kHz — removes TTS artifacts
        filters.append("equalizer=f=250:t=q:w=1.0:g=-3")   # cut mud
        filters.append("equalizer=f=500:t=q:w=1.5:g=-2")   # cut boxiness
        filters.append("equalizer=f=2500:t=q:w=1.0:g=1.5") # presence boost

    elif preset == "aggressive":
        # Full mastering chain with compression — use with caution
        filters.append("afftdn=nf=-25:nt=w")
        filters.append("highpass=f=80:poles=2")
        filters.append("lowpass=f=12000:poles=2")
        filters.append("equalizer=f=250:t=q:w=1.0:g=-3")
        filters.append("equalizer=f=500:t=q:w=1.5:g=-2")
        filters.append("acompressor=threshold=0.063:ratio=3:attack=5:release=150:makeup=1:knee=6")
        filters.append("volume=-10dB")
        filters.append("equalizer=f=2500:t=q:w=1.0:g=2")
        filters.append("equalizer=f=4500:t=q:w=1.5:g=1.5")
        filters.append("equalizer=f=6500:t=q:w=3.0:g=-4")

    elif preset == "light":
        filters.append("highpass=f=80:poles=2")
        filters.append("acompressor=threshold=0.063:ratio=3:attack=5:release=150:makeup=1:knee=6")
        filters.append("volume=-10dB")

    elif preset == "dynaudnorm":
        # Dynamic audio normalizer — good for level-matching two speakers
        filters.append("highpass=f=80:poles=2")
        filters.append("lowpass=f=12000:poles=2")
        filters.append("dynaudnorm=f=150:g=15:p=0.95:m=10:s=5")

    return filters


def build_filter_chain(preset="full", lufs_target=-16):
    """Build the ffmpeg audio filter chain (single-pass)."""
    filters = _processing_filters(preset)
    # Loudness normalization — always last
    filters.append(f"loudnorm=I={lufs_target}:LRA=11:TP=-1")
    return ",".join(filters)


def build_two_pass_filter(filepath, preset="full", lufs_target=-16):
    """Build a two-pass loudnorm filter chain for highest quality."""
    chain_filters = _processing_filters(preset)

    processing = ",".join(chain_filters)
    loudnorm_measure = f"loudnorm=I={lufs_target}:LRA=11:TP=-1:print_format=json"

    if processing:
        pass1_filter = f"{processing},{loudnorm_measure}"
    else:
        pass1_filter = loudnorm_measure

    # Pass 1: Measure
    print(f"  Pass 1: Measuring loudness...")
    cmd = [
        "ffmpeg", "-hide_banner", "-i", filepath,
        "-af", pass1_filter,
        "-f", "null", "/dev/null",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    try:
        stderr = result.stderr
        json_start = stderr.rindex("{")
        json_end = stderr.rindex("}") + 1
        measured = json.loads(stderr[json_start:json_end])
    except (ValueError, json.JSONDecodeError):
        print(f"  Warning: Could not parse loudnorm measurements, falling back to single-pass")
        return None, None

    # Pass 2: Apply with measured values
    loudnorm_apply = (
        f"loudnorm=I={lufs_target}:LRA=11:TP=-1:linear=true"
        f":measured_I={measured['input_i']}"
        f":measured_LRA={measured['input_lra']}"
        f":measured_TP={measured['input_tp']}"
        f":measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}"
    )

    if processing:
        pass2_filter = f"{processing},{loudnorm_apply}"
    else:
        pass2_filter = loudnorm_apply

    return pass2_filter, measured


def process_file(filepath, output_path=None, preset="full", lufs_target=-16, two_pass=True):
    """Process a single audio file through the mastering chain."""
    if not os.path.exists(filepath):
        print(f"  ERROR: File not found: {filepath}")
        return None

    if output_path is None:
        base, ext = os.path.splitext(filepath)
        output_path = f"{base}_mastered{ext}"

    print(f"\n  Processing: {os.path.basename(filepath)}")
    print(f"  Preset: {preset} | Target: {lufs_target} LUFS | Two-pass: {two_pass}")

    # Measure original loudness
    original_loudness = get_loudness(filepath)
    if original_loudness:
        print(f"  Original: {original_loudness.get('input_i', '?')} LUFS, "
              f"TP: {original_loudness.get('input_tp', '?')} dBTP, "
              f"LRA: {original_loudness.get('input_lra', '?')} LU")

    if two_pass:
        filter_chain, measured = build_two_pass_filter(filepath, preset, lufs_target)
        if filter_chain is None:
            # Fallback to single-pass
            filter_chain = build_filter_chain(preset, lufs_target)
            print(f"  Using single-pass fallback")
        else:
            print(f"  Pass 1 measured: I={measured['input_i']}, "
                  f"TP={measured['input_tp']}, LRA={measured['input_lra']}")
    else:
        filter_chain = build_filter_chain(preset, lufs_target)

    # Apply the filter chain
    print(f"  {'Pass 2: ' if two_pass else ''}Applying mastering chain...")
    cmd = [
        "ffmpeg", "-hide_banner", "-y",
        "-i", filepath,
        "-af", filter_chain,
        "-ar", "48000",
        "-c:a", "libmp3lame", "-b:a", "128k",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ERROR: ffmpeg failed: {result.stderr[:300]}")
        return None

    # Measure output loudness
    output_loudness = get_loudness(output_path)
    if output_loudness:
        print(f"  Output:   {output_loudness.get('input_i', '?')} LUFS, "
              f"TP: {output_loudness.get('input_tp', '?')} dBTP, "
              f"LRA: {output_loudness.get('input_lra', '?')} LU")

    in_size = os.path.getsize(filepath)
    out_size = os.path.getsize(output_path)
    print(f"  Size: {in_size/1024:.0f}KB -> {out_size/1024:.0f}KB")
    print(f"  Output: {output_path}")

    return {
        "input": filepath,
        "output": output_path,
        "preset": preset,
        "original_lufs": original_loudness.get("input_i") if original_loudness else None,
        "output_lufs": output_loudness.get("input_i") if output_loudness else None,
        "original_tp": original_loudness.get("input_tp") if original_loudness else None,
        "output_tp": output_loudness.get("input_tp") if output_loudness else None,
    }


def process_segment(segment_path, speaker, output_path):
    """Process a single TTS segment with speaker-appropriate settings.

    This is the function used in the pipeline — processes each segment
    before stitching, so each speaker gets tailored treatment.

    Args:
        segment_path: Path to the raw TTS segment (WAV or MP3)
        speaker: "HOST_A" or "HOST_B" (for per-speaker processing)
        output_path: Where to save the processed segment
    """
    # Use the full processing chain + loudnorm per segment
    filters = _processing_filters("full")
    filters.append("loudnorm=I=-16:LRA=11:TP=-1")

    filter_chain = ",".join(filters)

    # Detect input format
    ext = os.path.splitext(segment_path)[1].lower()
    out_ext = os.path.splitext(output_path)[1].lower()

    cmd = [
        "ffmpeg", "-hide_banner", "-y",
        "-i", segment_path,
        "-af", filter_chain,
        "-ar", "48000",
    ]

    if out_ext == ".wav":
        cmd.extend(["-c:a", "pcm_s16le"])
    else:
        cmd.extend(["-c:a", "libmp3lame", "-b:a", "128k"])

    cmd.append(output_path)

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Podcast audio mastering — normalize, EQ, compress, and sweeten",
    )
    parser.add_argument("files", nargs="+", help="MP3 files to process")
    parser.add_argument("--preset", choices=["full", "light", "aggressive", "normalize", "dynaudnorm"],
                        default="full", help="Processing preset (default: full)")
    parser.add_argument("--lufs", type=int, default=-16,
                        help="Target LUFS (default: -16, Apple standard)")
    parser.add_argument("--compare", action="store_true",
                        help="Open both original and mastered for A/B comparison")
    parser.add_argument("--single-pass", action="store_true",
                        help="Use single-pass loudnorm (faster, slightly less accurate)")
    parser.add_argument("--suffix", default="_mastered",
                        help="Suffix for output files (default: _mastered)")

    args = parser.parse_args()

    results = []
    for filepath in args.files:
        base, ext = os.path.splitext(filepath)
        output_path = f"{base}{args.suffix}{ext}"

        result = process_file(
            filepath,
            output_path=output_path,
            preset=args.preset,
            lufs_target=args.lufs,
            two_pass=not args.single_pass,
        )

        if result:
            results.append(result)

            if args.compare:
                print(f"\n  Opening A/B comparison...")
                subprocess.run(["open", filepath])
                subprocess.run(["open", output_path])

    # Summary
    if results:
        print(f"\n{'='*60}")
        print(f"  MASTERING COMPLETE — {len(results)} files processed")
        print(f"{'='*60}")
        for r in results:
            delta = ""
            if r["original_lufs"] and r["output_lufs"]:
                try:
                    d = float(r["output_lufs"]) - float(r["original_lufs"])
                    delta = f" (Δ {d:+.1f} LU)"
                except ValueError:
                    pass
            print(f"  {os.path.basename(r['input'])}: {r['original_lufs']} → {r['output_lufs']} LUFS{delta}")
        print()


if __name__ == "__main__":
    main()
