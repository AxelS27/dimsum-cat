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
class ActorConfig:
    """Configuration for an individual character actor on stage."""
    character: str = ""                     # character folder (e.g. "dimsum_cat", "taeho", "animals")
    animation: str = ""                     # animation folder inside character
    pos: str | list | tuple = "center"      # anchor position: [cx, cy] or preset string
    scale: float = 1.0                      # scale factor
    flip_x: bool = False                    # mirror horizontally
    rotate: float = 0.0                     # extra rotation degrees
    motion: str = ""                        # motion physics preset ("squash_bounce", "breathe", etc.)
    motion_speed: float = 1.0               # speed multiplier for motion
    motion_intensity: float = 1.0           # intensity multiplier for motion
    ground_shadow: bool = True              # whether to render dynamic contact shadow at feet
    z_index: int = 0                        # layer order (higher = drawn on top)


@dataclass
class Accessory:
    """A sprite overlay composited on top of the character."""
    image: str              # path to PNG relative to story_dir or project root
    pos: str = "0.5,0.5"   # "cx,cy" fractions or named position key
    scale: float = 1.0
    flip_x: bool = False    # mirror horizontally
    rotate: float = 0.0     # degrees clockwise


@dataclass
class CameraConfig:
    """Settings for the virtual cinematic director camera."""
    type: str = "static"                      # "static", "zoom_punch", "slow_zoom_in", "slow_zoom_out", "crash_zoom", "tracking", "whip_pan", "dutch_tilt", "sway", "rumble"
    target: str | list | tuple = ""           # actor character name ("dimsum_cat", "taeho") or [x, y] coordinates
    zoom: float = 1.0                         # target zoom factor (>1.0 = zoom in)
    zoom_start: float | None = None           # starting zoom factor (if interpolating)
    intensity: float = 1.0                    # movement/shake intensity multiplier
    speed: float = 1.0                        # camera move speed multiplier (lower = slower/gentler, e.g. 0.5 = 2x slower)
    ease: str = "smooth"                      # "smooth" (zero-jerk smootherstep), "in_out", "linear", "snappy"
    roll: float = 0.0                         # Dutch tilt angle in degrees
    pan_from: str | list | tuple | None = None # starting camera center [x, y]
    pan_to: str | list | tuple | None = None   # ending camera center [x, y]
    reactive_actor: str = ""                  # character name to sync camera motion/shake with
    reactive_factor: float = 0.5              # coupling strength (0.0 to 1.0)
    duration: float | None = None             # movement duration in seconds (None = beat_dur / speed)


@dataclass
class StoryBeat:
    """One moment in the video story."""
    time: float            # seconds from start
    text: str              # main text (large, prominent)
    sub: str = ""          # secondary line — pinyin, translation, reaction
    animation: str = ""    # switch to this animation (empty = keep previous)
    pos: str | list | tuple = "center"    # named position or "cx,cy" or [cx, cy]
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
    motion: str = ""                       # motion behavior preset name ("heavy_bounce", "float_gentle", etc.)
    motion_speed: float = 1.0              # speed multiplier for motion physics
    motion_intensity: float = 1.0          # intensity/amplitude multiplier for motion physics
    camera: str | dict | CameraConfig = "static"  # virtual camera preset or dict
    camera_intensity: float = 1.0          # strength of camera movement/shake
    transition: str = ""                   # scene transition ("flash", "crossfade", "circle_wipe", "dip_black", "none")
    transition_dur: float = 0.22           # duration of scene transition in seconds
    actors: list[ActorConfig] = field(default_factory=list)  # multi-character actors on stage
    vfx: list[dict] = field(default_factory=list)            # kawaii particle & visual FX triggers
    ground_shadow: bool = True                               # contact shadow toggle

    def get_camera_config(self) -> CameraConfig:
        """Resolve camera settings into a strongly-typed CameraConfig."""
        if isinstance(self.camera, CameraConfig):
            return self.camera
        if isinstance(self.camera, dict):
            return CameraConfig(
                type            = str(self.camera.get("type", "static")),
                target          = self.camera.get("target", ""),
                zoom            = float(self.camera.get("zoom", 1.0)),
                zoom_start      = float(self.camera["zoom_start"]) if "zoom_start" in self.camera else None,
                intensity       = float(self.camera.get("intensity", self.camera_intensity)),
                speed           = float(self.camera.get("speed", 1.0)),
                ease            = str(self.camera.get("ease", "smooth")),
                roll            = float(self.camera.get("roll", 0.0)),
                pan_from        = self.camera.get("pan_from"),
                pan_to          = self.camera.get("pan_to"),
                reactive_actor  = str(self.camera.get("reactive_actor", "")),
                reactive_factor = float(self.camera.get("reactive_factor", 0.5)),
                duration        = float(self.camera["duration"]) if "duration" in self.camera else None,
            )
        if isinstance(self.camera, str):
            c_str = self.camera.strip() or "static"
            return CameraConfig(type=c_str, intensity=self.camera_intensity)
        return CameraConfig(type="static", intensity=self.camera_intensity)

    def get_actors(self, default_character: str, default_animation: str) -> list[ActorConfig]:
        """Return list of active actors, resolving single-character beat fallback."""
        if self.actors:
            res: list[ActorConfig] = []
            for a in self.actors:
                res.append(ActorConfig(
                    character        = a.character or self.character or default_character,
                    animation        = a.animation or self.animation or default_animation,
                    pos              = a.pos,
                    scale            = a.scale,
                    flip_x           = a.flip_x,
                    rotate           = a.rotate if a.rotate != 0.0 else self.cat_rotate,
                    motion           = a.motion or self.motion,
                    motion_speed     = a.motion_speed if a.motion_speed != 1.0 else self.motion_speed,
                    motion_intensity = a.motion_intensity if a.motion_intensity != 1.0 else self.motion_intensity,
                    ground_shadow    = a.ground_shadow if a.ground_shadow is not None else self.ground_shadow,
                    z_index          = a.z_index,
                ))
            return res
        return [
            ActorConfig(
                character        = self.character or default_character,
                animation        = self.animation or default_animation,
                pos              = self.pos,
                scale            = self.scale,
                flip_x           = self.flip_x,
                rotate           = self.cat_rotate,
                motion           = self.motion,
                motion_speed     = self.motion_speed,
                motion_intensity = self.motion_intensity,
                ground_shadow    = self.ground_shadow,
                z_index          = 0,
            )
        ]


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
    save_frames:        bool  = False   # save intermediate PNG frames to disk (default: stream via pipe)
    intro_gap:          float = 0.8   # first retimed beat offset; set 0.0 for instant hook text
    between_gap:        float = 0.65  # retimed gap after each spoken beat
    silent_beat_dur:    float = 1.5   # retimed duration for silent/punctuation beats
