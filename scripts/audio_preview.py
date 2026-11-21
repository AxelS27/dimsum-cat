"""
audio_preview.py — Generate audio preview for a story (TTS + SFX + bg music).

Usage:
    python scripts/audio_preview.py --story content/interactive/finger_cleaning

Output:
    content/interactive/finger_cleaning/audio_preview.mp3
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.utils import find_ffmpeg
from src.output import _parse_music_start


def mix_sfx_track(
    beats: list[dict],
    duration: float,
    story_dir: Path,
    out_path: Path,
    ffmpeg: str,
) -> bool:
    """Build a silent base + SFX clips at beat timestamps → single mp3."""
    sfx_entries = []
    for b in beats:
        beat_time = float(b.get("time", 0))
        for sfx in b.get("sfx", []):
            fp = Path(sfx["file"])
            if not fp.is_absolute():
                candidate = story_dir / fp
                fp = candidate if candidate.exists() else ROOT / fp
            if fp.exists():
                sfx_entries.append({
                    "file": fp,
                    "time": beat_time + float(sfx.get("delay", 0.0)),
                    "volume": float(sfx.get("volume", 1.0)),
                })

    if not sfx_entries:
        return False

    # Build ffmpeg filter_complex: silent base + each sfx with adelay
    inputs = []
    filter_parts = [f"anullsrc=r=44100:cl=stereo,atrim=duration={duration}[base]"]
    mix_labels = ["[base]"]

    for j, entry in enumerate(sfx_entries):
        delay_ms = int(entry["time"] * 1000)
        vol = entry["volume"]
        inputs += ["-i", str(entry["file"])]
        filter_parts.append(
            f"[{j}]volume={vol},adelay={delay_ms}|{delay_ms}[sfx{j}]"
        )
        mix_labels.append(f"[sfx{j}]")

    n = len(mix_labels)
    filter_parts.append(
        f"{''.join(mix_labels)}amix=inputs={n}:normalize=0:duration=first"
    )

    result = subprocess.run(
        [ffmpeg, "-y"] + inputs + [
            "-filter_complex", ";".join(filter_parts),
            "-c:a", "libmp3lame", "-b:a", "128k",
            str(out_path),
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        print(f"  SFX mix failed:\n{result.stderr.decode()[-500:]}")
        return False
    return True


def mix_final(
    layers: list[tuple[Path, float, str]],  # (file, volume, start offset)
    duration: float,
    out_path: Path,
    ffmpeg: str,
) -> None:
    """Mix multiple audio layers into final mp3."""
    inputs = []
    filter_parts = [f"anullsrc=r=44100:cl=stereo,atrim=duration={duration}[base]"]
    mix_labels = ["[base]"]

    for j, (fp, vol, start) in enumerate(layers):
        start_sec = _parse_music_start(start)
        ss_args = ["-ss", f"{start_sec:.3f}"] if start_sec > 0 else []
        inputs += ["-stream_loop", "-1", *ss_args, "-i", str(fp)]
        filter_parts.append(f"[{j}]volume={vol},atrim=duration={duration}[l{j}]")
        mix_labels.append(f"[l{j}]")

    n = len(mix_labels)
    filter_parts.append(
        f"{''.join(mix_labels)}amix=inputs={n}:normalize=0:duration=first"
    )

    result = subprocess.run(
        [ffmpeg, "-y"] + inputs + [
            "-filter_complex", ";".join(filter_parts),
            "-c:a", "libmp3lame", "-b:a", "128k",
            str(out_path),
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Final mix failed:\n{result.stderr.decode()[-500:]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--story", type=Path, required=True)
    args = parser.parse_args()

    story_path = args.story
    if story_path.is_dir():
        story_path = story_path / "story.json"
    story_path = story_path.resolve()
    story_dir  = story_path.parent

    data     = json.loads(story_path.read_text(encoding="utf-8"))
    beats    = data.get("beats", [])
    duration = float(data.get("duration", 20.0))
    bg_music_rel  = data.get("bg_music", "")
    bg_volume     = float(data.get("bg_volume", 0.09))
    bg_music_start = data.get("bg_music_start", "")
    tts_enabled   = data.get("tts", False)
    tts_volume    = float(data.get("tts_volume", 1.4))

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        sys.exit("ffmpeg not found")

    out_dir = story_dir
    tmp_dir = story_dir / "_audio_tmp"
    tmp_dir.mkdir(exist_ok=True)

    print(f"Story   : {story_dir.name}")
    print(f"Duration: {duration}s  |  TTS: {tts_enabled}  |  BG vol: {bg_volume}")

    layers: list[tuple[Path, float, str]] = []

    # --- TTS ---
    if tts_enabled:
        from src.tts import build_tts_audio, _gpt_sovits_clip, _should_speak
        from src.models import StoryBeat

        beat_objs = [
            StoryBeat(
                time=float(b.get("time", 0)),
                text=b.get("text", ""),
                tts_speed=b.get("tts_speed"),
                tts_temperature=b.get("tts_temperature"),
                tts_delay=float(b.get("tts_delay", 0.0)),
                after_gap=float(b["after_gap"]) if b.get("after_gap") is not None else None,
            )
            for b in beats
        ]

        # Resolve ref audio to absolute path so TTS server can find it
        ref_raw = data.get("gpt_sovits_ref", "")
        ref_path = Path(ref_raw)
        if ref_raw and not ref_path.is_absolute():
            candidate = story_dir / ref_path
            ref_path = candidate if candidate.exists() else ROOT / ref_path
        ref_abs = str(ref_path.resolve()) if ref_path.exists() else ref_raw

        # Generate individual beat clips → beats/ folder
        beats_dir = out_dir / "beats"
        beats_dir.mkdir(exist_ok=True)
        server  = data.get("gpt_sovits_server", "http://127.0.0.1:9880")
        tts_ok  = True
        speak_beats = [(i, b) for i, b in enumerate(beat_objs) if _should_speak(b.text)]

        for i, b in speak_beats:
            out_clip = beats_dir / f"beat_{i:02d}.mp3"
            if out_clip.exists():
                print(f"  beat_{i:02d}.mp3 already exists, skipping")
                continue
            try:
                print(f"    GPT-SoVITS beat_{i:02d}: {b.text}")
                _gpt_sovits_clip(
                    b.text.replace("~", "").strip(),
                    ref_abs,
                    beats_dir / f"beat_{i:02d}",
                    server=server,
                    speed=b.tts_speed,
                    temperature=b.tts_temperature,
                )
                # Convert wav → mp3
                wav = beats_dir / f"beat_{i:02d}.wav"
                if wav.exists():
                    subprocess.run(
                        [ffmpeg, "-y", "-i", str(wav),
                         "-c:a", "libmp3lame", "-b:a", "128k", str(out_clip)],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    )
                    wav.unlink(missing_ok=True)
            except Exception as e:
                print(f"  TTS beat_{i:02d} failed: {e}")
                tts_ok = False
                break

        if tts_ok and speak_beats:
            from src.utils import _recalculate_beat_times

            intro_gap       = float(data.get("intro_gap", 0.8))
            between_gap     = float(data.get("between_gap", 0.65))
            silent_beat_dur = float(data.get("silent_beat_dur", 1.5))

            tts_out = tmp_dir / "tts.mp3"

            # Measure clip durations → retime beats (JSON times are 0.0 placeholders)
            clip_durations = build_tts_audio(
                beat_objs, duration, tts_out,
                pregenerated_dir=beats_dir,
                return_durations=True,
            )
            if isinstance(clip_durations, dict):
                beat_objs, duration = _recalculate_beat_times(
                    beat_objs, clip_durations,
                    intro_gap=intro_gap,
                    between_gap=between_gap,
                    silent_beat_dur=silent_beat_dur,
                )

            ok = build_tts_audio(
                beat_objs, duration, tts_out,
                pregenerated_dir=beats_dir,
            )
            if ok:
                layers.append((tts_out, tts_volume, ""))
                print(f"  TTS mixed from beats/ ({len(speak_beats)} clips)")
            else:
                print("  TTS mix failed")
        else:
            print("  TTS skipped")
    else:
        print("  TTS disabled in story.json")

    # --- SFX ---
    sfx_out = tmp_dir / "sfx.mp3"
    has_sfx = mix_sfx_track(beats, duration, story_dir, sfx_out, ffmpeg)
    if has_sfx:
        layers.append((sfx_out, 1.0, ""))
        print("  SFX mixed: wipe.mp3 + spray.mp3")
    else:
        print("  No SFX entries found")

    # --- BG music ---
    if bg_music_rel:
        bg_path = Path(bg_music_rel)
        if not bg_path.is_absolute():
            bg_path = story_dir / bg_path
        if bg_path.exists():
            layers.append((bg_path, bg_volume, bg_music_start))
            start_label = f" @ {bg_music_start}" if bg_music_start else ""
            print(f"  BG music: {bg_path.name}{start_label}")

    if not layers:
        sys.exit("Nothing to mix — no TTS, SFX, or bg music found")

    # --- Final mix ---
    final_out = out_dir / "audio_preview.mp3"
    print(f"\nMixing {len(layers)} layer(s)...")

    # Simple mix: all layers with their volumes
    inputs_cmd = []
    filter_p = [f"anullsrc=r=44100:cl=stereo,atrim=duration={duration}[base]"]
    mix_l = ["[base]"]
    for j, (fp, vol, start) in enumerate(layers):
        start_sec = _parse_music_start(start)
        ss_args = ["-ss", f"{start_sec:.3f}"] if start_sec > 0 else []
        inputs_cmd += ["-stream_loop", "-1", *ss_args, "-i", str(fp)]
        filter_p.append(f"[{j}]volume={vol},atrim=duration={duration}[l{j}]")
        mix_l.append(f"[l{j}]")
    n = len(mix_l)
    filter_p.append(f"{''.join(mix_l)}amix=inputs={n}:normalize=0:duration=first")

    result = subprocess.run(
        [ffmpeg, "-y"] + inputs_cmd + [
            "-filter_complex", ";".join(filter_p),
            "-c:a", "libmp3lame", "-b:a", "128k",
            str(final_out),
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        sys.exit(f"Mix failed:\n{result.stderr.decode()[-500:]}")

    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"\nDone -> {final_out}")


if __name__ == "__main__":
    main()
