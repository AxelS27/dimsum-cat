from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterator, Callable

from PIL import Image

from src.utils import find_ffmpeg


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def stream_to_mp4(
    frame_iterator: Iterator[Image.Image],
    mp4_path: Path,
    fps: int,
    width: int,
    height: int,
    total_frames: int | None = None,
    title: str = "",
    description: str = "",
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """Stream raw RGB video frames directly to FFmpeg stdin (Zero-Disk I/O).

    Encodes with h264_nvenc (NVIDIA GPU) at CQ 18.
    Eliminates intermediate PNG disk writes entirely.
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found. Run: pip install imageio-ffmpeg")
    mp4_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = []
    if title:
        metadata += ["-metadata", f"title={title}"]
    if description:
        metadata += ["-metadata", f"comment={description}"]

    first_frame = next(frame_iterator, None)
    if first_frame is None:
        return
    import itertools
    all_frames = itertools.chain([first_frame], frame_iterator)

    raw_mode = "RGBA" if first_frame.mode == "RGBA" else "RGB"
    pix_fmt = "rgba" if raw_mode == "RGBA" else "rgb24"

    cmd = [
        ffmpeg, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", pix_fmt,
        "-r", str(fps),
        "-i", "pipe:0",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "h264_nvenc",
        "-cq", "18",
        "-preset", "p4",
        "-rc", "vbr",
        "-pix_fmt", "yuv420p",
        *metadata,
        str(mp4_path),
    ]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    frame_count = 0
    try:
        for frame in all_frames:
            raw_bytes = frame.tobytes("raw", raw_mode) if frame.mode == raw_mode else frame.convert(raw_mode).tobytes("raw", raw_mode)
            proc.stdin.write(raw_bytes)
            frame_count += 1
            if progress_callback:
                progress_callback(frame_count, total_frames or frame_count)
            elif frame_count % (fps * 2) == 0 or (total_frames and frame_count == total_frames):
                pct = f" ({int(frame_count / total_frames * 100)}%)" if total_frames else ""
                print(f"  Streaming frame {frame_count:04d}/{total_frames or '?' :04d}{pct}")
        proc.stdin.close()
    except Exception as e:
        proc.kill()
        raise RuntimeError(f"Error streaming frames to ffmpeg: {e}") from e

    out, err = proc.communicate()
    if proc.returncode != 0:
        err_msg = err.decode("utf-8", errors="replace")
        raise RuntimeError(f"ffmpeg streaming failed (exit code {proc.returncode}):\n{err_msg}")


def save_png_sequence(frames: list[Image.Image], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(frames):
        frame.save(out_dir / f"frame_{i:04d}.png")


def save_mp4(
    frames_dir: Path,
    mp4_path: Path,
    fps: int,
    title: str = "",
    description: str = "",
) -> None:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found. Run: pip install imageio-ffmpeg")
    mp4_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = []
    if title:
        metadata += ["-metadata", f"title={title}"]
    if description:
        metadata += ["-metadata", f"comment={description}"]
    result = subprocess.run(
        [
            ffmpeg, "-y",
            "-framerate", str(fps),
            "-i", str(frames_dir / "frame_%04d.png"),
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v", "h264_nvenc",
            "-cq", "18",
            "-preset", "p4",
            "-rc", "vbr",
            "-pix_fmt", "yuv420p",
            *metadata,
            str(mp4_path),
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr.decode()}")


def save_gif(frames: list[Image.Image], path: Path, fps: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ms = int(1000 / fps)
    pal = [f.convert("P", palette=Image.Palette.ADAPTIVE) for f in frames]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=ms, loop=0, disposal=2)


def _parse_music_start(s: str) -> float:
    """Parse 'SS:cs' (seconds:centiseconds) to float seconds. '12:50' → 12.50s"""
    if not s:
        return 0.0
    parts = s.split(":")
    try:
        secs = int(parts[0])
        cs   = int(parts[1]) if len(parts) > 1 else 0
        return secs + cs / 100.0
    except (ValueError, IndexError):
        return 0.0


def mux_audio_into_mp4(
    mp4_path: Path,
    audio_path: Path,
    bg_music: Path | None = None,
    bg_volume: float = 0.09,
    bg_music_start: str = "",
    bg_music_fade_in: float = 0.0,
    tts_volume: float = 1.4,
    sfx_list: list[tuple[float, Path, float]] | None = None,
) -> None:
    """Mux TTS audio (+ optional background music and timed SFX) into MP4 in-place.

    bg_music loops automatically to match the video length.
    bg_volume controls the relative level of the background track (0–1).
    bg_music_start: "SS:cs" offset into the music file before looping.
    sfx_list: list of (timestamp_seconds, sfx_file_path, volume)
    """
    ffmpeg = find_ffmpeg()
    tmp = mp4_path.with_suffix(".tmp.mp4")

    input_args = ["-i", str(mp4_path), "-i", str(audio_path)]
    filter_nodes = []
    mix_nodes = []

    is_silence = "_silence" in audio_path.name
    if not is_silence:
        filter_nodes.append(f"[1]volume={tts_volume}[tts]")
        mix_nodes.append("[tts]")

    next_idx = 2
    if bg_music and bg_music.exists():
        start_sec = _parse_music_start(bg_music_start)
        ss_args = ["-ss", f"{start_sec:.3f}"] if start_sec > 0 else []
        input_args.extend(["-stream_loop", "-1", *ss_args, "-i", str(bg_music)])
        bgm_filt = f"[{next_idx}]volume={bg_volume}"
        if bg_music_fade_in > 0:
            bgm_filt += f",afade=t=in:st=0:d={bg_music_fade_in}"
        bgm_filt += "[bgm]"
        filter_nodes.append(bgm_filt)
        mix_nodes.append("[bgm]")
        next_idx += 1

    if sfx_list:
        for i, (t_sec, sfx_p, vol) in enumerate(sfx_list):
            if sfx_p and sfx_p.exists():
                input_args.extend(["-i", str(sfx_p)])
                delay_ms = max(0, int(t_sec * 1000))
                sfx_node = f"[sfx_{i}]"
                filter_nodes.append(f"[{next_idx}]adelay={delay_ms}|{delay_ms},volume={vol}{sfx_node}")
                mix_nodes.append(sfx_node)
                next_idx += 1

    if len(mix_nodes) == 1:
        fc = ";".join(filter_nodes) + f";{mix_nodes[0]}anull[aout]"
        cmd = [ffmpeg, "-y", *input_args, "-filter_complex", fc, "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(tmp)]
    elif len(mix_nodes) > 1:
        fc = ";".join(filter_nodes) + f";{''.join(mix_nodes)}amix=inputs={len(mix_nodes)}:normalize=0:dropout_transition=0[aout]"
        cmd = [ffmpeg, "-y", *input_args, "-filter_complex", fc, "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(tmp)]
    else:
        cmd = [ffmpeg, "-y", *input_args, "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(tmp)]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg mux failed:\n{result.stderr.decode()}")
    tmp.replace(mp4_path)


def mix_audio_preview(
    tts_path: Path,
    out_path: Path,
    bg_music: Path | None = None,
    bg_volume: float = 0.09,
    bg_music_start: str = "",
    bg_music_fade_in: float = 0.0,
    tts_volume: float = 1.4,
) -> None:
    """Mix TTS audio with optional bg_music into a standalone mp3 (no video)."""
    ffmpeg = find_ffmpeg()
    if bg_music and bg_music.exists():
        start_sec = _parse_music_start(bg_music_start)
        ss_args = ["-ss", f"{start_sec:.3f}"] if start_sec > 0 else []
        bgm_filter = f"[1]volume={bg_volume}"
        if bg_music_fade_in > 0:
            bgm_filter += f",afade=t=in:st=0:d={bg_music_fade_in}"
        result = subprocess.run(
            [ffmpeg, "-y",
             "-i", str(tts_path),
             "-stream_loop", "-1", *ss_args, "-i", str(bg_music),
             "-filter_complex",
             f"[0]volume={tts_volume}[tts];{bgm_filter}[bgm];"
             "[tts][bgm]amix=inputs=2:normalize=0:dropout_transition=0:duration=first[aout]",
             "-map", "[aout]",
             "-c:a", "libmp3lame", "-b:a", "128k",
             str(out_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    else:
        import shutil as _shutil
        _shutil.copy2(tts_path, out_path)
        return
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio mix failed:\n{result.stderr.decode()}")
