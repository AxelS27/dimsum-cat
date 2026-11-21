from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root — one level up from src/
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ASSETS_ROOT      = ROOT / "assets"
SPRITES_ROOT     = ASSETS_ROOT / "sprites"
ANIMATIONS_ROOT  = SPRITES_ROOT / "dimsum_cat" / "animations"
WATERMARK_PNG    = SPRITES_ROOT / "watermark.png"
CONTENT_ROOT     = ROOT / "content"
FRAME_NAMES      = ("frame_a.png", "frame_b.png", "frame_c.png", "frame_d.png")

# Base sprite frame hold — actual timing varies per frame for hand-animated feel
SPRITE_FRAME_MS = 220

# Padding added to each sprite (in original pixels) before upscaling.
# Gives side/top effects (burst lines, speech bubbles, cherry) breathing room.
SPRITE_PAD = 22

# Pre-upscale factor applied once at load time.
# Means per-frame resize is a downscale → sharp, not blurry.
SPRITE_UPSCALE = 1

# Named character anchor positions as (cx, cy) fractions of canvas.
# cy=0.60 puts the character center at 60% from top — visually centred on
# a vertical phone screen with text above and breathing room below.
POSITIONS: dict[str, tuple[float, float]] = {
    "center":      (0.50, 0.54),
    "center-high": (0.50, 0.44),
    "center-low":  (0.50, 0.64),
    "left":        (0.30, 0.54),
    "right":       (0.70, 0.54),
    "left-low":    (0.30, 0.64),
    "right-low":   (0.70, 0.64),
    "left-high":   (0.28, 0.44),
    "right-high":  (0.72, 0.44),
}

# (main_font_px, sub_font_px) at 720w canvas
TEXT_SIZES: dict[str, tuple[int, int]] = {
    "small":  (34, 22),
    "normal": (50, 30),
    "big":    (70, 38),
    "huge":   (92, 46),
}

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RichTextSpan:
    """One colored segment in a beat's optional visual text."""
    text: str
    color: str = "#2a2a2a"


@dataclass
class Accessory:
    """A sprite overlay composited on top of the character."""
    image: str              # path to PNG relative to story_dir or project root
    pos: str = "0.5,0.5"   # "cx,cy" fractions or named position key
    scale: float = 1.0
    flip_x: bool = False    # mirror horizontally
    rotate: float = 0.0     # degrees clockwise


@dataclass
class StoryBeat:
    """One moment in the video story."""
    time: float            # seconds from start
    text: str              # main text (large, prominent)
    sub: str = ""          # secondary line — pinyin, translation, reaction
    animation: str = ""    # switch to this animation (empty = keep previous)
    pos: str = "center"    # named position or "cx,cy" e.g. "0.3,0.7"
    scale: float = 1.0     # character scale multiplier
    text_size: str = "normal"  # small | normal | big | huge
    tts_speed: float | None = None        # override auto-detected speed
    tts_temperature: float | None = None  # override auto-detected temperature
    tts_delay: float = 0.0                # delay speech relative to this beat's visual time
    after_gap: float | None = None        # override root between_gap after this beat during retime
    rich_text:     list[RichTextSpan] = field(default_factory=list)
    rich_text_sub: list[RichTextSpan] = field(default_factory=list)
    bg_image:  str = ""    # per-beat background image path (overrides config.bg_image)
    character: str = ""    # per-beat character override (overrides config.default_character)
    flip_x:    bool  = False   # mirror character horizontally
    cat_rotate: float = 0.0   # extra rotation offset in degrees (added to organic)
    accessories: list[Accessory] = field(default_factory=list)  # sprite overlays
    sfx: list[dict] = field(default_factory=list)  # [{"file": "path.mp3", "volume": 0.8}]


@dataclass
class RenderConfig:
    beats: list[StoryBeat]
    default_animation: str
    output_name: str
    duration: float
    fps: int
    width: int
    height: int
    bg: str
    watermark: str
    story_dir:          Path | None = None   # folder containing story.json; output goes here
    title:              str  = ""            # video title (embedded in MP4 + IG caption)
    description:        str  = ""           # IG description / caption
    save_gif:           bool = False
    tts:                bool = False
    gpt_sovits_server:  str  = "http://127.0.0.1:9880"   # local GPT-SoVITS API server
    gpt_sovits_ref:     str  = ""                         # reference audio path for voice cloning
    gpt_sovits_speed:   float | None = None       # fixed speed for all beats (None = emotion-auto ~0.90). Lower = slower delivery.
    gpt_sovits_temperature: float | None = None   # fixed temp for all beats (None = auto per-emotion). Lower = more stable prosody.
    gpt_sovits_top_k:       int   | None = None   # fixed top_k for all beats (None = 15). Lower = more deterministic.
    gpt_sovits_top_p:       float | None = None   # nucleus sampling (None = 1.0). Lower = flatter, more stable prosody.
    gpt_sovits_rep_penalty: float | None = None   # fixed repetition_penalty (None = auto ~1.30). Lower = less raspy/forced.
    gpt_sovits_prompt_text: str = ""   # transcript of the reference audio — anchors voice/prosody. Empty = degraded ref-free mode.
    tts_pitch_normalize: bool  = False   # shift each clip to a common pitch register (fixes per-beat pitch drift)
    tts_pitch_target:    float = 0.0     # target F0 in Hz (0 = auto: median of clips)
    bg_music:           str  = ""
    bg_music_start:     str  = ""   # "SS:cs" — seconds:centiseconds, e.g. "12:50" = 12.50s
    bg_music_fade_in:   float = 0.0
    bg_volume:          float = 0.09  # background music volume (0.0–1.0)
    tts_volume:         float = 1.4   # TTS voice volume multiplier
    tts_pitch:          float = 1.0   # pitch multiplier (0.93 = ~7% lower, 1.07 = ~7% higher)
    bg_image:           str   = ""    # default background image path (overridden per-beat)
    default_character:  str   = "dimsum_cat"  # character used unless overridden per-beat
    intro_gap:          float = 0.8   # first retimed beat offset; set 0.0 for instant hook text
    between_gap:        float = 0.65  # retimed gap after each spoken beat
    silent_beat_dur:    float = 1.5   # retimed duration for silent/punctuation beats
