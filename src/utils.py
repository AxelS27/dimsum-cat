from __future__ import annotations

import math
import re
import shutil
import subprocess
from pathlib import Path

from PIL import ImageDraw, ImageFont

# Strips emoji and other Unicode symbols that Jua / system CJK fonts can't render.
# Covers the main emoji blocks; keeps all Latin, Korean, punctuation.
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF"   # misc symbols, transport, supplemental, chess
    "\U00002600-\U000027BF"    # misc symbols, dingbats
    "\U0000FE00-\U0000FE0F"    # variation selectors
    "\U000024C2"                # circled M
    "\U0001F100-\U0001F251"    # enclosed alphanumeric / ideographic supplement
    "]+",
    flags=re.UNICODE,
)

# Characters outside Jua's coverage that render as tofu boxes.
# Map to visually equivalent safe ASCII alternatives.
_UNSUPPORTED = str.maketrans({
    "—": "-",   # em dash  —
    "–": "-",   # en dash  –
    "‘": "'",   # left single quote
    "’": "'",   # right single quote
    "“": '"',   # left double quote
    "”": '"',   # right double quote
    "…": "...", # ellipsis …
})


def strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text).translate(_UNSUPPORTED).strip()

from src.models import POSITIONS, ANIMATIONS_ROOT, ROOT, SPRITE_FRAME_MS, StoryBeat

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

LOCAL_FONTS_DIR = ROOT / "assets" / "fonts"


def find_ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg  # type: ignore[import]
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        pass
    return shutil.which("ffmpeg")


def resolve_pos(pos: str | list | tuple) -> tuple[float, float]:
    """Resolve position from named presets, coordinates, or percentage numbers."""
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        x, y = float(pos[0]), float(pos[1])
        if x > 1.0:
            x /= 100.0
        if y > 1.0:
            y /= 100.0
        return x, y
    if isinstance(pos, str) and pos in POSITIONS:
        return POSITIONS[pos]
    try:
        parts = str(pos).split(",")
        x, y = float(parts[0].strip()), float(parts[1].strip())
        if x > 1.0:
            x /= 100.0
        if y > 1.0:
            y /= 100.0
        return x, y
    except (ValueError, IndexError):
        return POSITIONS["center"]


def find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        # Jua — cute rounded Korean font downloaded to project/fonts/
        LOCAL_FONTS_DIR / "Jua-Regular.ttf",
        # System CJK fallbacks that actually contain Hangul glyphs
        Path("C:/Windows/Fonts/msjhbd.ttc") if bold else Path("C:/Windows/Fonts/msjh.ttc"),
        Path("C:/Windows/Fonts/msyhbd.ttc") if bold else Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/seguisb.ttf") if bold else Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf") if bold else Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


def measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    if not text:
        return 0, 0
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0], b[3] - b[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if measure(draw, text, font)[0] <= max_w:
        return [text]
    if " " not in text:                         # CJK: split by character
        lines, cur = [], ""
        for ch in text:
            if cur and measure(draw, cur + ch, font)[0] > max_w:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines
    words = text.split()                        # Latin: split by word
    lines, cur = [], ""
    for w in words:
        candidate = w if not cur else f"{cur} {w}"
        if cur and measure(draw, candidate, font)[0] > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = candidate
    if cur:
        lines.append(cur)
    return lines


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_smooth(t: float) -> float:
    """Quintic smootherstep — zero velocity and zero acceleration at start and end."""
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def ease_in_out(t: float) -> float:
    """Cubic ease in-out with zero start and end velocity."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def ease_out_back(t: float) -> float:
    """Spring overshoot — punchy scale pop."""
    c1, c3 = 1.30, 2.30
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def get_ease_func(name: str) -> Callable[[float], float]:
    """Resolve easing curve function by name."""
    n = (name or "smooth").lower().strip()
    if n in ("smooth", "smootherstep", "quintic"):
        return ease_smooth
    elif n in ("in_out", "ease_in_out", "cubic_in_out"):
        return ease_in_out
    elif n in ("linear", "none"):
        return lambda t: max(0.0, min(1.0, t))
    elif n in ("snappy", "overshoot", "spring", "back"):
        return ease_out_back
    elif n in ("cubic", "ease_out", "fast_start"):
        return ease_out_cubic
    return ease_smooth


def list_animations() -> list[str]:
    if not ANIMATIONS_ROOT.exists():
        return []
    return sorted(p.name for p in ANIMATIONS_ROOT.iterdir() if p.is_dir())


def slugify(value: str) -> str:
    out = []
    for ch in value.lower().strip().replace(" ", "_"):
        if ch.isalnum() or ch in {"_", "-"}:
            out.append(ch)
    return "".join(out).strip("_") or "dimsum_cat"


def _audio_duration(ffmpeg: str, path: Path) -> float:
    """Return duration in seconds of an audio file using ffmpeg."""
    r = subprocess.run(
        [ffmpeg, "-i", str(path), "-f", "null", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    for line in r.stderr.decode(errors="replace").splitlines():
        if "Duration:" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return float(h) * 3600 + float(m) * 60 + float(s)
    return 0.0


def _recalculate_beat_times(
    beats: list[StoryBeat],
    clip_durations: dict[int, float],
    intro_gap: float = 0.8,
    between_gap: float = 0.65,
    silent_beat_dur: float = 1.5,
) -> tuple[list[StoryBeat], float]:
    """Retime beats so each scene ends shortly after its speech finishes.

    Beats with speech advance by (tts_delay + clip_duration + gap).
    Beats without speech (punctuation, silent) advance by silent_beat_dur.
    """
    import dataclasses
    new_beats: list[StoryBeat] = []
    t = intro_gap
    for i, beat in enumerate(beats):
        new_beats.append(dataclasses.replace(beat, time=t))
        dur = clip_durations.get(i, 0.0)
        gap = beat.after_gap if beat.after_gap is not None else between_gap
        delay = max(0.0, beat.tts_delay)
        t += (delay + dur + gap) if dur > 0 else silent_beat_dur
    return new_beats, t + 1.8   # trailing buffer — enough for last clip to finish
