from __future__ import annotations

import argparse
import dataclasses
import gc
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Force UTF-8 output so Korean text doesn't crash on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from src.models import (
    ActorConfig,
    RenderConfig,
    RichTextSpan,
    StoryBeat,
    ROOT,
    CONTENT_ROOT,
    TEXT_SIZES,
)
from src.utils import (
    find_ffmpeg,
    list_animations,
    slugify,
    strip_emoji,
    _recalculate_beat_times,
)
from src.renderer import render_video_frames, iter_video_frames
from src.sprite import load_frames
from src.tts import build_tts_audio
from src.output import (
    save_png_sequence,
    save_mp4,
    stream_to_mp4,
    save_gif,
    mux_audio_into_mp4,
    mix_audio_preview,
)

# ---------------------------------------------------------------------------
# Story loading
# ---------------------------------------------------------------------------

DEFAULT_STORY = [
    StoryBeat(time=0.0,  text="진짜..?",    sub="Really..?",
              animation="normal_talk",  pos="center",     scale=1.0,  text_size="big"),
    StoryBeat(time=3.0,  text="나 좋아해?", sub="You like me?",
              animation="shy_blush",    pos="right",      scale=1.25, text_size="huge"),
    StoryBeat(time=6.5,  text="ㅋㅋㅋ",     sub="lol",
              animation="excited_talk", pos="center-low", scale=0.85, text_size="normal"),
    StoryBeat(time=9.5,  text="❤",          sub="",
              animation="finger_heart", pos="center",     scale=1.4,  text_size="huge"),
]


def _resolve_story_path(raw: str, story_dir: Path) -> str:
    """Resolve a path that may be relative to the story folder or project root."""
    if not raw:
        return raw
    p = Path(raw)
    if p.is_absolute():
        return str(p)
    # Try relative to story folder first, then project root
    rel_to_story = (story_dir / p).resolve()
    if rel_to_story.exists():
        return str(rel_to_story)
    rel_to_root = (ROOT / p).resolve()
    return str(rel_to_root)


def _load_rich_text(raw: object) -> list[RichTextSpan]:
    if not isinstance(raw, list):
        return []
    spans: list[RichTextSpan] = []
    for item in raw:
        if isinstance(item, str):
            t = strip_emoji(item)
            if t:
                spans.append(RichTextSpan(text=t))
        elif isinstance(item, dict):
            text = strip_emoji(str(item.get("text", "")))
            if text:
                spans.append(RichTextSpan(text=text, color=str(item.get("color", "#2a2a2a"))))
    return spans


def _load_actors(raw: object) -> list[ActorConfig]:
    if not isinstance(raw, list):
        return []
    actors: list[ActorConfig] = []
    for a in raw:
        if isinstance(a, dict):
            actors.append(
                ActorConfig(
                    character        = str(a.get("character", "")),
                    animation        = str(a.get("animation", "")),
                    pos              = a.get("pos", "center"),
                    scale            = float(a.get("scale", 1.0)),
                    flip_x           = bool(a.get("flip_x", False)),
                    rotate           = float(a.get("rotate", 0.0)),
                    motion           = str(a.get("motion", "")),
                    motion_speed     = float(a.get("motion_speed", 1.0)),
                    motion_intensity = float(a.get("motion_intensity", 1.0)),
                    ground_shadow    = bool(a.get("ground_shadow", True)),
                    z_index          = int(a.get("z_index", 0)),
                    move_to          = a.get("move_to") or a.get("pos_to"),
                    path             = a.get("path") or a.get("waypoints"),
                    move_speed       = float(a.get("move_speed", 1.0)),
                    move_ease        = str(a.get("move_ease", "smooth")),
                    move_dur         = float(a["move_dur"]) if "move_dur" in a else None,
                    auto_tilt        = a.get("auto_tilt", True),
                    auto_flip        = bool(a.get("auto_flip", True)),
                    loop_path        = bool(a.get("loop_path", False)),
                )
            )
    return actors


def _load_vfx(raw: object) -> list[dict]:
    if isinstance(raw, str):
        return [{"type": raw.strip()}]
    if not isinstance(raw, list):
        return []
    res: list[dict] = []
    for item in raw:
        if isinstance(item, str):
            res.append({"type": item.strip()})
        elif isinstance(item, dict):
            res.append(item)
    return res


def load_story_file(path: Path, args: argparse.Namespace) -> RenderConfig:
    """Load story from either story.yaml, story.yml, or story.json.

    If a directory path is given, prefers story.yaml / story.yml over story.json.
    """
    if path.is_dir():
        candidates = [
            path / "story.yaml",
            path / "story.yml",
            path / "story.json",
        ]
        found = next((c for c in candidates if c.exists()), None)
        if not found:
            raise FileNotFoundError(f"No story.yaml, story.yml, or story.json found in {path}")
        path = found
    path = path.resolve()
    story_dir = path.parent

    raw_text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        import yaml
        data = yaml.safe_load(raw_text) or {}
    else:
        data = json.loads(raw_text) or {}
    raw_beats = data.get("beats", [])
    beats = [
        StoryBeat(
            time            = b["time"],
            text            = b.get("text", ""),
            sub             = b.get("sub", ""),
            tts_text        = str(b.get("tts_text", "")),
            animation       = b.get("animation", ""),
            pos             = b.get("pos", "center"),
            scale           = float(b.get("scale", 1.0)),
            text_size       = b.get("text_size", "normal"),
            tts_speed       = float(b["tts_speed"])       if b.get("tts_speed")       is not None else None,
            tts_temperature = float(b["tts_temperature"]) if b.get("tts_temperature") is not None else None,
            tts_delay       = float(b.get("tts_delay", 0.0)),
            after_gap       = float(b["after_gap"]) if "after_gap" in b else None,
            rich_text       = _load_rich_text(b.get("rich_text")),
            rich_text_sub   = _load_rich_text(b.get("rich_text_sub")),
            bg_image        = b.get("bg_image", ""),
            character       = b.get("character", ""),
            motion          = b.get("motion", ""),
            motion_speed    = float(b.get("motion_speed", 1.0)),
            motion_intensity = float(b.get("motion_intensity", 1.0)),
            camera          = b.get("camera", ""),
            camera_intensity = float(b.get("camera_intensity", 1.0)),
            transition      = b.get("transition", ""),
            transition_dur  = float(b.get("transition_dur", 0.22)),
            actors          = _load_actors(b.get("actors")),
            vfx             = _load_vfx(b.get("vfx")),
            ground_shadow   = bool(b.get("ground_shadow", True)),
            move_to         = b.get("move_to") or b.get("pos_to"),
            path            = b.get("path") or b.get("waypoints"),
            move_speed      = float(b.get("move_speed", 1.0)),
            move_ease       = str(b.get("move_ease", "smooth")),
            move_dur        = float(b["move_dur"]) if "move_dur" in b else None,
            auto_tilt       = b.get("auto_tilt", True),
            auto_flip       = bool(b.get("auto_flip", True)),
            loop_path       = bool(b.get("loop_path", False)),
        )
        for b in raw_beats
    ]
    output_name = data.get("output", args.output) or story_dir.name
    return RenderConfig(
        beats             = beats,
        default_animation = data.get("animation") or data.get("default_animation") or args.animation,
        output_name       = output_name,
        story_dir         = story_dir,
        title             = data.get("title", ""),
        description       = data.get("description", ""),
        duration          = float(data.get("duration", args.duration)),
        fps               = int(data.get("fps", args.fps)),
        width             = int(data.get("width", args.width)),
        height            = int(data.get("height", args.height)),
        bg                = data.get("bg", args.bg),
        bg_image          = _resolve_story_path(data.get("bg_image", ""), story_dir),
        default_character = data.get("character", "dimsum_cat"),
        watermark         = data.get("watermark", args.watermark),
        save_gif          = args.gif,
        tts               = data.get("tts", args.tts),
        gpt_sovits_ref    = _resolve_story_path(data.get("gpt_sovits_ref", args.gpt_sovits_ref), story_dir),
        gpt_sovits_server = data.get("gpt_sovits_server", args.gpt_sovits_server),
        gpt_sovits_speed  = float(data.get("gpt_sovits_speed", args.gpt_sovits_speed)),
        gpt_sovits_temperature = (float(data["gpt_sovits_temperature"]) if data.get("gpt_sovits_temperature") is not None else None),
        gpt_sovits_top_k       = (int(data["gpt_sovits_top_k"])         if data.get("gpt_sovits_top_k")       is not None else None),
        gpt_sovits_top_p       = (float(data["gpt_sovits_top_p"])       if data.get("gpt_sovits_top_p")       is not None else None),
        gpt_sovits_rep_penalty = (float(data["gpt_sovits_rep_penalty"]) if data.get("gpt_sovits_rep_penalty") is not None else None),
        gpt_sovits_prompt_text = data.get("gpt_sovits_prompt_text", ""),
        tts_pitch_normalize    = bool(data.get("tts_pitch_normalize", False)),
        tts_pitch_target       = float(data.get("tts_pitch_target", 0.0)),
        bg_music          = _resolve_story_path(data.get("bg_music", args.bg_music), story_dir),
        bg_music_start    = data.get("bg_music_start", ""),
        bg_volume         = float(data.get("bg_volume",  0.09)),
        tts_volume        = float(data.get("tts_volume", 1.4)),
        tts_pitch         = float(data.get("tts_pitch",  1.0)),
        bg_music_fade_in  = float(data.get("bg_music_fade_in", 0.0)),
        intro_gap         = float(data.get("intro_gap", 0.8)),
        between_gap       = float(data.get("between_gap", 0.65)),
        silent_beat_dur   = float(data.get("silent_beat_dur", 1.5)),
        save_frames       = getattr(args, "save_frames", False),
    )


# Backward-compatible alias
load_story_json = load_story_file


def config_from_args(args: argparse.Namespace) -> RenderConfig:
    # Build a single-beat story from simple CLI flags
    beat = StoryBeat(
        time      = 0,
        text      = args.text,
        sub       = args.sub,
        animation = args.animation,
        pos       = args.pos,
        scale     = args.scale,
        text_size = args.text_size,
    )
    output_name = args.output or slugify(args.text or args.animation)
    return RenderConfig(
        beats             = [beat],
        default_animation = args.animation,
        output_name       = output_name,
        duration          = args.duration,
        fps               = args.fps,
        width             = args.width,
        height            = args.height,
        bg                = args.bg,
        watermark         = args.watermark,
        save_gif          = args.gif,
        tts               = args.tts,
        gpt_sovits_ref    = args.gpt_sovits_ref,
        gpt_sovits_server = args.gpt_sovits_server,
        gpt_sovits_speed  = args.gpt_sovits_speed,
        bg_music          = args.bg_music,
        save_frames       = getattr(args, "save_frames", False),
    )


def config_demo(args: argparse.Namespace) -> RenderConfig:
    output_name = args.output or "demo_story"
    return RenderConfig(
        beats             = DEFAULT_STORY,
        default_animation = "normal_talk",
        output_name       = output_name,
        duration          = args.duration,
        fps               = args.fps,
        width             = args.width,
        height            = args.height,
        bg                = args.bg,
        watermark         = args.watermark,
        save_gif          = args.gif,
        tts               = args.tts,
        gpt_sovits_ref    = args.gpt_sovits_ref,
        gpt_sovits_server = args.gpt_sovits_server,
        gpt_sovits_speed  = args.gpt_sovits_speed,
        bg_music          = args.bg_music,
        save_frames       = getattr(args, "save_frames", False),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Render DIMsum Cat short-form vertical videos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Story mode (recommended):
  python video_generator.py --story my_story.json

Quick single-beat:
  python video_generator.py --text "你好" --sub "nǐ hǎo · Hello" --animation normal_talk

Demo (built-in 4-beat story):
  python video_generator.py --demo
""",
    )
    p.add_argument("--list-animations", action="store_true", help="List available animations and exit.")
    p.add_argument("--demo",   action="store_true", help="Render the built-in demo story.")
    p.add_argument("--story",  type=Path,           help="Path to a story JSON file.")

    # Single-beat quick mode
    p.add_argument("--text",      default="你好可爱",         help="Main text.")
    p.add_argument("--sub",       default="nǐ hǎo kě ài",   help="Secondary/translation text.")
    p.add_argument("--animation", default="normal_talk",     help="Animation name.")
    p.add_argument("--pos",       default="center",          help="Character position (named or cx,cy).")
    p.add_argument("--scale",     type=float, default=1.0,   help="Character scale multiplier.")
    p.add_argument("--text-size", dest="text_size", default="big",
                   choices=list(TEXT_SIZES), help="Text size preset.")

    # Shared output settings
    p.add_argument("--output",   default="",       help="Output folder name under output/.")
    p.add_argument("--duration", type=float, default=12.0,  help="Video duration in seconds.")
    p.add_argument("--fps",      type=int,   default=24,    help="Frames per second.")
    p.add_argument("--width",    type=int,   default=1080,  help="Canvas width.")
    p.add_argument("--height",   type=int,   default=1920,  help="Canvas height.")
    p.add_argument("--bg",       default="#f8f4f0",         help="Background hex color.")
    p.add_argument("--watermark", default="",               help="(unused — watermark.png is used instead)")
    p.add_argument("--gif",       action="store_true",        help="Also export a GIF preview.")
    p.add_argument("--save-frames", action="store_true", dest="save_frames", help="Save intermediate PNG frames to disk (default: False, streams directly to FFmpeg).")
    p.add_argument("--tts",              action="store_true",                   help="Add TTS voiceover.")
    p.add_argument("--gpt-sovits-ref",    default="",           dest="gpt_sovits_ref",
                                                               help="Reference audio for GPT-SoVITS voice cloning (3-10s).")
    p.add_argument("--gpt-sovits-server", default="http://127.0.0.1:9880", dest="gpt_sovits_server",
                                                               help="GPT-SoVITS API server URL.")
    p.add_argument("--gpt-sovits-speed",  default=0.88, type=float, dest="gpt_sovits_speed",
                                                               help="Speech speed for GPT-SoVITS (default 0.88).")
    p.add_argument("--bg-music",         default="",           dest="bg_music",
                                                               help="Path to background music file. Loops automatically.")
    p.add_argument("--tts-only",          action="store_true",  dest="tts_only",
                                                               help="Generate TTS audio clips only — skip video render.")
    p.add_argument("--audio-only",        action="store_true",  dest="audio_only",
                                                               help="Generate TTS + music mix as audio_preview.mp3 — skip video render.")
    p.add_argument("--from-beats",        action="store_true",  dest="from_beats",
                                                               help="Render using pregenerated clips in beats/ — skip TTS generation.")
    p.add_argument("--regen-beat",        type=int,             dest="regen_beat", default=None,
                                                               help="Regenerate only beat N (0-indexed) and save to beats/.")
    p.add_argument("--remix-audio",        action="store_true",  dest="remix_audio",
                                                               help="Re-mix audio only using existing beats/ and video.mp4 — skip frame rendering and TTS generation.")
    return p


def print_result(result: dict) -> None:
    frames_disp = result.get("frames_dir") or "(zero-disk streaming pipe)"
    print(f"  Frames : {frames_disp}")
    print(f"  MP4    : {result['mp4']}")
    if result.get("gif"):
        print(f"  GIF    : {result['gif']}")


def _beats_dir(out_base: Path) -> Path:
    return out_base / "beats"


def _beat_path(out_base: Path, i: int) -> Path:
    return _beats_dir(out_base) / f"beat_{i:02d}.mp3"


def _render_png_sequence_chunked(config: RenderConfig, frames_dir: Path, chunk_frames: int = 120) -> None:
    """Render frames in small batches so long 1080p videos do not exhaust RAM."""
    frames_dir.mkdir(parents=True, exist_ok=True)
    total_frames = max(1, int(config.duration * config.fps))
    for start in range(0, total_frames, chunk_frames):
        end = min(start + chunk_frames, total_frames)
        print(f"  Rendering frames {start:04d}-{end - 1:04d} / {total_frames - 1:04d}")
        frames = render_video_frames(config, frame_start=start, frame_end=end)
        for i, frame in enumerate(frames, start=start):
            frame.save(frames_dir / f"frame_{i:04d}.png")
        del frames
        gc.collect()


def _save_beats(tmp_dir: Path, out_base: Path, beats: list) -> None:
    """Copy generated clips from _tts_tmp to beats/ with readable names."""
    bd = _beats_dir(out_base)
    bd.mkdir(exist_ok=True)
    speak_idx = [i for i, b in enumerate(beats) if b.text.strip() and len(b.text.strip()) >= 2]
    for i in speak_idx:
        src = tmp_dir / f"beat_{i:02d}.mp3"
        if src.exists():
            shutil.copy2(src, _beat_path(out_base, i))


def render(config: RenderConfig, tts_only: bool = False, audio_only: bool = False,
           from_beats: bool = False, regen_beat: int | None = None,
           remix_audio: bool = False) -> dict:
    # Output goes into the story's own folder; fallback to content/<name>
    out_base = config.story_dir if config.story_dir else CONTENT_ROOT / config.output_name
    out_base.mkdir(parents=True, exist_ok=True)
    frames_dir = out_base / "frames"
    # Clear stale frames from previous renders so old frames don't extend duration.
    # Skip when remix_audio=True — we reuse the existing video.mp4 video stream.
    if frames_dir.exists() and not remix_audio:
        shutil.rmtree(frames_dir)
    if remix_audio:
        from_beats = True  # reuse beats/*.mp3, skip TTS generation
    mp4_path = out_base / "video.mp4"
    gif_path = out_base / "video.gif"

    # Resolve background music path early
    bg_music_path: Path | None = None
    if config.bg_music:
        p = Path(config.bg_music)
        bg_music_path = p if p.is_absolute() else ROOT / p
        if not bg_music_path.exists():
            print(f"  WARNING: bg_music not found: {bg_music_path}")
            bg_music_path = None

    # ── Phase 1: TTS pre-generation ──────────────────────────────────────────
    audio_path: Path | None = None
    tts_ok = False
    tmp_dir = out_base / "_tts_tmp"

    if regen_beat is not None and config.tts:
        # Regenerate only one specific beat, keep the rest from beats/
        bd = _beats_dir(out_base)
        bd.mkdir(exist_ok=True)
        tmp_dir.mkdir(exist_ok=True)
        beat = config.beats[regen_beat]
        from src.tts import _gpt_sovits_clip, _should_speak
        raw_tts = (getattr(beat, "tts_text", "") or beat.text).replace("~", "").strip()
        if _should_speak(raw_tts):
            tts_text = raw_tts
            print(f"  Regenerating beat {regen_beat}: {tts_text}")
            wav = tmp_dir / f"beat_{regen_beat:02d}.wav"
            _gpt_sovits_clip(
                tts_text, config.gpt_sovits_ref,
                wav, server=config.gpt_sovits_server,
                speed=beat.tts_speed if beat.tts_speed is not None else config.gpt_sovits_speed,
                temperature=beat.tts_temperature if beat.tts_temperature is not None else config.gpt_sovits_temperature,
                top_k=config.gpt_sovits_top_k,
                top_p=config.gpt_sovits_top_p,
                rep_penalty_override=config.gpt_sovits_rep_penalty,
                prompt_text=config.gpt_sovits_prompt_text,
            )
            import subprocess as _sp
            ffmpeg = find_ffmpeg()
            mp3 = tmp_dir / f"beat_{regen_beat:02d}.mp3"
            _sp.run([ffmpeg, "-y", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "128k", str(mp3)],
                    stdout=_sp.PIPE, stderr=_sp.PIPE)
            wav.unlink(missing_ok=True)
            # post-process
            tmp_p = tmp_dir / f"beat_{regen_beat:02d}_c.mp3"
            _sp.run([ffmpeg, "-y", "-i", str(mp3),
                     "-af", "highpass=f=120,equalizer=f=2500:width_type=o:width=2:g=2",
                     "-c:a", "libmp3lame", "-b:a", "128k", str(tmp_p)],
                    stdout=_sp.PIPE, stderr=_sp.PIPE)
            if tmp_p.exists():
                tmp_p.replace(mp3)
            shutil.copy2(mp3, _beat_path(out_base, regen_beat))
            print(f"  Saved → beats/beat_{regen_beat:02d}.mp3")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return {"frames_dir": None, "mp4": None, "gif": None}

    if from_beats and config.tts:
        # Use pregenerated clips from beats/ — copy to _tts_tmp for mixing
        bd = _beats_dir(out_base)
        tmp_dir.mkdir(exist_ok=True)
        for i in range(len(config.beats)):
            src = _beat_path(out_base, i)
            if src.exists():
                shutil.copy2(src, tmp_dir / f"beat_{i:02d}.mp3")
        tts_ok = build_tts_audio(
            config.beats, config.duration,
            out_path=out_base / f"{config.output_name}_audio.mp3",
            gpt_sovits_ref=config.gpt_sovits_ref,
            gpt_sovits_server=config.gpt_sovits_server,
            gpt_sovits_speed=config.gpt_sovits_speed,
            return_durations=True,
            tts_pitch=config.tts_pitch,
            pregenerated_dir=tmp_dir,
        )
        if isinstance(tts_ok, dict):
            clip_durations: dict[int, float] = tts_ok
            new_beats, new_duration = _recalculate_beat_times(
                config.beats, clip_durations,
                intro_gap=config.intro_gap,
                between_gap=config.between_gap,
                silent_beat_dur=config.silent_beat_dur,
            )
            config = dataclasses.replace(config, beats=new_beats, duration=new_duration)
            tts_ok = True
        audio_path = out_base / f"{config.output_name}_audio.mp3"
    elif config.tts:
        print("  Generating TTS audio...")
        audio_path = out_base / f"{config.output_name}_audio.mp3"
        tts_ok = build_tts_audio(
            config.beats, config.duration,
            out_path=audio_path,
            gpt_sovits_ref=config.gpt_sovits_ref,
            gpt_sovits_server=config.gpt_sovits_server,
            gpt_sovits_speed=config.gpt_sovits_speed,
            return_durations=True,
            tts_pitch=config.tts_pitch,
            gpt_sovits_temperature=config.gpt_sovits_temperature,
            gpt_sovits_top_k=config.gpt_sovits_top_k,
            gpt_sovits_top_p=config.gpt_sovits_top_p,
            gpt_sovits_rep_penalty=config.gpt_sovits_rep_penalty,
            gpt_sovits_prompt_text=config.gpt_sovits_prompt_text,
            pitch_normalize=config.tts_pitch_normalize,
            pitch_target=config.tts_pitch_target,
        )
        if isinstance(tts_ok, dict):
            clip_durations: dict[int, float] = tts_ok
            new_beats, new_duration = _recalculate_beat_times(
                config.beats, clip_durations,
                intro_gap=config.intro_gap,
                between_gap=config.between_gap,
                silent_beat_dur=config.silent_beat_dur,
            )
            config = dataclasses.replace(config, beats=new_beats, duration=new_duration)
            tts_ok = True

    if tts_only:
        _save_beats(tmp_dir, out_base, config.beats)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print("  TTS clips saved to beats/")
        for i, b in enumerate(config.beats):
            p = _beat_path(out_base, i)
            if p.exists():
                print(f"    beat_{i:02d}.mp3  →  {b.text[:40]}")
        return {"frames_dir": _beats_dir(out_base), "mp4": None, "gif": None}

    if audio_only:
        audio_out = out_base / "audio_preview.mp3"
        if tts_ok:
            mix_ok = build_tts_audio(
                config.beats, config.duration,
                out_path=audio_path,
                gpt_sovits_ref=config.gpt_sovits_ref,
                gpt_sovits_server=config.gpt_sovits_server,
                gpt_sovits_speed=config.gpt_sovits_speed,
                pregenerated_dir=out_base / "_tts_tmp",
                tts_pitch=config.tts_pitch,
            )
            shutil.rmtree(out_base / "_tts_tmp", ignore_errors=True)
            if mix_ok and audio_path:
                mix_audio_preview(
                    audio_path, audio_out,
                    bg_music=bg_music_path,
                    bg_music_start=config.bg_music_start,
                    bg_music_fade_in=config.bg_music_fade_in,
                    bg_volume=config.bg_volume,
                    tts_volume=config.tts_volume,
                )
                audio_path.unlink(missing_ok=True)
                suffix = " + music" if bg_music_path else ""
                print(f"  Audio preview saved{suffix}: {audio_out}")
        return {"frames_dir": None, "mp4": None, "gif": None, "audio": audio_out}

    # ── Phase 2: Render video frames with (retimed) config ───────────────────
    # Skipped when --remix-audio: reuse the existing video.mp4 video stream.
    if not remix_audio:
        if remix_audio and not mp4_path.exists():
            raise RuntimeError(f"--remix-audio requires an existing video.mp4 at {mp4_path}")
        frames = None
        if config.save_frames:
            _render_png_sequence_chunked(config, frames_dir)
            save_mp4(frames_dir, mp4_path, config.fps, title=config.title, description=config.description)
        else:
            total_frames = max(1, int(config.duration * config.fps))
            print(f"  Streaming {total_frames} frames directly to FFmpeg (Zero-Disk I/O)...")
            stream_to_mp4(
                iter_video_frames(config),
                mp4_path,
                config.fps,
                config.width,
                config.height,
                total_frames=total_frames,
                title=config.title,
                description=config.description,
            )

    # ── Phase 3: Mix TTS audio at retimed timestamps + mux ───────────────────
    if config.tts:
        if tts_ok:
            mix_ok = build_tts_audio(
                config.beats, config.duration,
                out_path=audio_path,
                gpt_sovits_ref=config.gpt_sovits_ref,
                gpt_sovits_server=config.gpt_sovits_server,
                gpt_sovits_speed=config.gpt_sovits_speed,
                pregenerated_dir=out_base / "_tts_tmp",
                tts_pitch=config.tts_pitch,
            )
            shutil.rmtree(out_base / "_tts_tmp", ignore_errors=True)
            if mix_ok:
                mux_audio_into_mp4(mp4_path, audio_path, bg_music=bg_music_path, bg_music_start=config.bg_music_start, bg_music_fade_in=config.bg_music_fade_in, bg_volume=config.bg_volume, tts_volume=config.tts_volume)
                audio_path.unlink(missing_ok=True)
                suffix = " + background music" if bg_music_path else ""
                print(f"  TTS muxed into MP4{suffix}.")
            else:
                print("  TTS mix failed — video saved without audio.")
        else:
            print("  TTS failed — video saved without audio.")
    elif bg_music_path:
        # Background music only (no TTS)
        print("  Adding background music...")
        silence = out_base / "_silence.mp3"
        ffmpeg = find_ffmpeg()
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi",
             "-i", f"anullsrc=r=44100:cl=stereo,atrim=duration={config.duration}",
             "-c:a", "libmp3lame", "-b:a", "64k", str(silence)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        )
        mux_audio_into_mp4(mp4_path, silence, bg_music=bg_music_path, bg_music_start=config.bg_music_start, bg_music_fade_in=config.bg_music_fade_in, bg_volume=config.bg_volume, tts_volume=config.tts_volume)
        silence.unlink(missing_ok=True)
        print("  Background music muxed into MP4.")

    gif_created = False
    if config.save_gif and frames is not None:
        save_gif(frames, gif_path, config.fps)
        gif_created = True

    return {"frames_dir": (frames_dir if config.save_frames else None), "mp4": mp4_path, "gif": gif_path if gif_created else None}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_animations:
        for name in list_animations():
            print(name)
        return

    tts_only    = getattr(args, "tts_only",    False)
    audio_only  = getattr(args, "audio_only",  False)
    from_beats  = getattr(args, "from_beats",  False)
    regen_beat  = getattr(args, "regen_beat",  None)
    remix_audio = getattr(args, "remix_audio", False)
    kwargs = dict(tts_only=tts_only, audio_only=audio_only, from_beats=from_beats, regen_beat=regen_beat, remix_audio=remix_audio)
    if args.demo:
        result = render(config_demo(args), **kwargs)
    elif args.story:
        result = render(load_story_json(args.story, args), **kwargs)
    else:
        result = render(config_from_args(args), **kwargs)

    print_result(result)


if __name__ == "__main__":
    main()
