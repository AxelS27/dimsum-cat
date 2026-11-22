"""
camera.py — Virtual Cinematic Director Camera & Scene Transitions for DIMsum Cat.

Provides:
- Inter-Beat Smooth Camera Blending: Eliminates teleportation across beats within the same scene.
- Focus Target Locking: Camera tracks or zooms onto specific actors or coordinates.
- Tracking & Panning Shots: Dolly/follow shots tracking characters as they move.
- Reactive Character Sync: Camera shakes/bobs in lockstep with character motions.
- Cinematic Moves: crash_zoom, zoom_punch, slow_zoom_in, slow_zoom_out, whip_pan, dutch_tilt, sway, rumble.
- Static Camera: Rock-solid stationary camera for clean, stable scenes with smooth settle-in.
- Scene Transitions: crossfade, circle_wipe, dip_black, flash bloom.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable
from PIL import Image, ImageDraw

from src.models import CameraConfig
from src.utils import ease_out_back, ease_out_cubic, ease_smooth, ease_in_out, lerp


def _get_ease_func(ease_name: str) -> Callable[[float], float]:
    """Resolve easing curve function for camera moves."""
    name = (ease_name or "smooth").lower().strip()
    if name in ("smooth", "smootherstep", "quintic"):
        return ease_smooth
    elif name in ("in_out", "ease_in_out", "cubic_in_out"):
        return ease_in_out
    elif name in ("linear", "none"):
        return lambda t: max(0.0, min(1.0, t))
    elif name in ("snappy", "overshoot", "spring", "back"):
        return ease_out_back
    elif name in ("cubic", "ease_out", "fast_start"):
        return ease_out_cubic
    return ease_smooth


@dataclass(slots=True)
class CameraState:
    """Computed state of the virtual cinematic camera for one frame."""
    zoom: float = 1.0          # camera scale (>1.0 zooms in, <1.0 zooms out)
    center_x: float = 0.5      # normalized world X where camera looks (0.0 to 1.0)
    center_y: float = 0.5      # normalized world Y where camera looks (0.0 to 1.0)
    shake_x: float = 0.0       # rumble horizontal displacement in pixels
    shake_y: float = 0.0       # rumble vertical displacement in pixels
    roll_deg: float = 0.0      # camera Dutch tilt / roll in degrees
    pan_x: float = 0.0         # backward-compatible pan offset (center_x - 0.5)
    pan_y: float = 0.0         # backward-compatible pan offset (center_y - 0.5)

    def __post_init__(self) -> None:
        if self.pan_x != 0.0 and self.center_x == 0.5:
            self.center_x = 0.5 + self.pan_x
        else:
            self.pan_x = self.center_x - 0.5

        if self.pan_y != 0.0 and self.center_y == 0.5:
            self.center_y = 0.5 + self.pan_y
        else:
            self.pan_y = self.center_y - 0.5


def resolve_target_pos(
    target: str | list | tuple,
    actor_positions: dict[str, tuple[float, float]] | None = None,
) -> tuple[float, float] | None:
    """Resolve camera target from actor name or [x, y] coordinates."""
    if isinstance(target, (list, tuple)) and len(target) >= 2:
        return float(target[0]), float(target[1])
    if isinstance(target, str) and target:
        t_clean = target.strip()
        if actor_positions and t_clean in actor_positions:
            return actor_positions[t_clean]
        if "," in t_clean:
            try:
                parts = t_clean.split(",")
                return float(parts[0].strip()), float(parts[1].strip())
            except Exception:
                pass
    return None


# ---------------------------------------------------------------------------
# Cinematic Camera Computation with Continuous Slerp / Inter-Beat Blending
# ---------------------------------------------------------------------------

def compute_camera(
    camera_input: str | dict | CameraConfig,
    age: float,
    beat_dur: float,
    intensity: float = 1.0,
    actor_positions: dict[str, tuple[float, float]] | None = None,
    actor_motions: dict[str, tuple[float, float]] | None = None,
    cam_start: CameraState | None = None,
) -> CameraState:
    """Compute virtual camera state for the current frame with smooth inter-beat continuity."""
    if isinstance(camera_input, CameraConfig):
        cfg = camera_input
    elif isinstance(camera_input, dict):
        cfg = CameraConfig(
            type            = str(camera_input.get("type", "static")),
            target          = camera_input.get("target", ""),
            zoom            = float(camera_input.get("zoom", 1.0)),
            zoom_start      = float(camera_input["zoom_start"]) if "zoom_start" in camera_input else None,
            intensity       = float(camera_input.get("intensity", intensity)),
            speed           = float(camera_input.get("speed", 1.0)),
            ease            = str(camera_input.get("ease", "smooth")),
            roll            = float(camera_input.get("roll", 0.0)),
            pan_from        = camera_input.get("pan_from"),
            pan_to          = camera_input.get("pan_to"),
            reactive_actor  = str(camera_input.get("reactive_actor", "")),
            reactive_factor = float(camera_input.get("reactive_factor", 0.5)),
            duration        = float(camera_input["duration"]) if "duration" in camera_input else None,
        )
    elif isinstance(camera_input, str):
        c_str = camera_input.strip() or "static"
        cfg = CameraConfig(type=c_str, intensity=intensity)
    else:
        cfg = CameraConfig(type="static", intensity=intensity)

    cam_type = cfg.type.lower().strip()
    eff_intensity = cfg.intensity
    eff_speed = max(0.05, float(getattr(cfg, "speed", 1.0)))
    ease_func = _get_ease_func(getattr(cfg, "ease", "smooth"))
    dur = (cfg.duration if cfg.duration is not None else max(0.1, beat_dur)) / eff_speed

    # Initial anchor: carry over from end of previous beat (eliminates teleportation)
    if cam_start is not None:
        start_cx   = cam_start.center_x
        start_cy   = cam_start.center_y
        start_zoom = cam_start.zoom
        start_roll = cam_start.roll_deg
        prev_shake_x = cam_start.shake_x
        prev_shake_y = cam_start.shake_y
    else:
        start_cx   = 0.5
        start_cy   = 0.5
        start_zoom = 1.0
        start_roll = 0.0
        prev_shake_x = 0.0
        prev_shake_y = 0.0

    has_explicit_zoom = getattr(cfg, "explicit_zoom", False) or (isinstance(camera_input, dict) and "zoom" in camera_input)
    has_explicit_target = getattr(cfg, "explicit_target", False) or bool(cfg.target)

    # 1. Rock-solid Static Camera or Hold (Smoothly holds framing from previous beat)
    if cam_type in ("hold", "keep"):
        state = CameraState(zoom=start_zoom, center_x=start_cx, center_y=start_cy, roll_deg=start_roll)

    elif cam_type in ("static", "none", "steady"):
        if cam_start is None:
            target_zoom = cfg.zoom if has_explicit_zoom else 1.0
            target_pos = resolve_target_pos(cfg.target, actor_positions) or (0.5, 0.5)
            state = CameraState(zoom=target_zoom, center_x=target_pos[0], center_y=target_pos[1], roll_deg=cfg.roll)
        elif not has_explicit_zoom and not has_explicit_target:
            # User wants static framing: HOLD previous beat's zoom and center without snapping!
            decay = max(0.0, 1.0 - age / 0.30)
            state = CameraState(
                zoom     = start_zoom,
                center_x = start_cx,
                center_y = start_cy,
                roll_deg = lerp(start_roll, cfg.roll, min(1.0, age / 0.40)),
                shake_x  = prev_shake_x * decay,
                shake_y  = prev_shake_y * decay,
            )
        else:
            # Explicit target or zoom change
            settle_dur = (cfg.duration if cfg.duration is not None else max(0.6, beat_dur)) / eff_speed
            target_zoom = cfg.zoom if has_explicit_zoom else start_zoom
            target_pos = resolve_target_pos(cfg.target, actor_positions) or (start_cx, start_cy)
            prog = ease_func(min(1.0, age / settle_dur))
            state = CameraState(
                zoom     = lerp(start_zoom, target_zoom, prog),
                center_x = lerp(start_cx, target_pos[0], prog),
                center_y = lerp(start_cy, target_pos[1], prog),
                roll_deg = lerp(start_roll, cfg.roll, prog),
                shake_x  = prev_shake_x * (1.0 - prog),
                shake_y  = prev_shake_y * (1.0 - prog),
            )

    # 2. Crash Zoom (Snap-zooms directly from start position to target)
    elif cam_type in ("crash_zoom", "crash"):
        zoom_dur = (cfg.duration or 0.22) / eff_speed
        crash_ease = ease_out_back if getattr(cfg, "ease", "smooth") == "smooth" else ease_func
        prog = crash_ease(min(1.0, age / zoom_dur))
        target_pos = resolve_target_pos(cfg.target, actor_positions) or (0.5, 0.5)
        target_zoom = cfg.zoom if cfg.zoom != 1.0 else (1.35 * eff_intensity)

        zoom = lerp(start_zoom, target_zoom, prog)
        cx = lerp(start_cx, target_pos[0], prog)
        cy = lerp(start_cy, max(0.25, target_pos[1] - 0.05), prog)
        roll = lerp(start_roll, cfg.roll, prog)

        shake_y = 0.0
        if zoom_dur <= age < zoom_dur + 0.12:
            decay = 1.0 - (age - zoom_dur) / 0.12
            shake_y = math.sin((age - zoom_dur) * 55.0) * 8.0 * decay * eff_intensity

        state = CameraState(zoom=zoom, center_x=cx, center_y=cy, shake_y=shake_y, roll_deg=roll)

    # 3. Zoom Punch (Elastic beat punch)
    elif cam_type in ("zoom_punch", "punch"):
        punch_dur = (cfg.duration or 0.32) / eff_speed
        if age < punch_dur:
            prog = age / punch_dur
            spring = ease_out_back(prog)
            extra_zoom = max(0.0, (1.0 - spring)) * 0.07 * eff_intensity
        else:
            extra_zoom = 0.0
        target_pos = resolve_target_pos(cfg.target, actor_positions) or (start_cx, start_cy)
        cx = lerp(start_cx, target_pos[0], min(1.0, extra_zoom * 2.5))
        cy = lerp(start_cy, max(0.25, target_pos[1] - 0.05), min(1.0, extra_zoom * 2.5))
        zoom = lerp(start_zoom, 1.0, min(1.0, age / punch_dur)) + extra_zoom
        roll = lerp(start_roll, cfg.roll, min(1.0, age / punch_dur))
        state = CameraState(zoom=zoom, center_x=cx, center_y=cy, roll_deg=roll)

    # 4. Cinematic Slow Zoom In (Glides smoothly from previous camera state)
    elif cam_type in ("slow_zoom_in", "zoom_in", "push_in"):
        prog = ease_func(min(1.0, age / dur))
        target_pos = resolve_target_pos(cfg.target, actor_positions) or (start_cx, start_cy)
        target_zoom = cfg.zoom if has_explicit_zoom else (start_zoom + 0.10 * eff_intensity)
        zoom = lerp(start_zoom, target_zoom, prog)
        cx = lerp(start_cx, target_pos[0], prog)
        cy = lerp(start_cy, max(0.25, target_pos[1] - 0.04), prog)
        roll = lerp(start_roll, cfg.roll, prog)
        state = CameraState(zoom=zoom, center_x=cx, center_y=cy, roll_deg=roll)

    # 5. Cinematic Slow Zoom Out (Pull back towards wide shot)
    elif cam_type in ("slow_zoom_out", "zoom_out", "pull_back", "wide", "reset"):
        prog = ease_func(min(1.0, age / dur))
        target_pos = resolve_target_pos(cfg.target, actor_positions) or (0.5, 0.5)
        target_zoom = cfg.zoom if has_explicit_zoom else 1.0
        zoom = lerp(start_zoom, target_zoom, prog)
        cx = lerp(start_cx, target_pos[0], prog)
        cy = lerp(start_cy, target_pos[1], prog)
        roll = lerp(start_roll, cfg.roll, prog)
        state = CameraState(zoom=zoom, center_x=cx, center_y=cy, roll_deg=roll)

    # 6. Tracking Shot (Dolly follow target or from A to B)
    elif cam_type in ("tracking", "dolly", "follow"):
        prog = ease_func(min(1.0, age / dur))
        if cfg.target and actor_positions and str(cfg.target) in actor_positions:
            t_pos = actor_positions[str(cfg.target)]
            cx = lerp(start_cx, t_pos[0], prog)
            cy = lerp(start_cy, max(0.25, t_pos[1] - 0.04), prog)
        else:
            p_from = resolve_target_pos(cfg.pan_from, actor_positions) or (start_cx, start_cy)
            p_to = resolve_target_pos(cfg.pan_to, actor_positions) or (0.65, 0.55)
            cx = lerp(p_from[0], p_to[0], prog)
            cy = lerp(p_from[1], p_to[1], prog)
        target_zoom = cfg.zoom if has_explicit_zoom else max(1.10, start_zoom)
        zoom = lerp(start_zoom, target_zoom, min(1.0, prog * 2.0))
        roll = lerp(start_roll, cfg.roll, prog)
        state = CameraState(zoom=zoom, center_x=cx, center_y=cy, roll_deg=roll)

    # 7. Whip Pan (Swift motion-blur camera sweep)
    elif cam_type in ("whip_pan", "whip"):
        whip_dur = (cfg.duration or 0.24) / eff_speed
        prog = ease_func(min(1.0, age / whip_dur))
        p_from = resolve_target_pos(cfg.pan_from, actor_positions) or (start_cx, start_cy)
        p_to = resolve_target_pos(cfg.pan_to, actor_positions) or (0.70, 0.55)
        cx = lerp(p_from[0], p_to[0], prog)
        cy = lerp(p_from[1], p_to[1], prog)
        zoom = lerp(start_zoom, 1.05, prog) + math.sin(prog * math.pi) * 0.06 * eff_intensity
        roll = lerp(start_roll, cfg.roll, prog)
        state = CameraState(zoom=zoom, center_x=cx, center_y=cy, roll_deg=roll)

    # 8. Dutch Tilt (Dramatic angled camera with smooth tilt-in)
    elif cam_type in ("dutch_tilt", "dutch", "tilt"):
        settle_dur = (cfg.duration if cfg.duration is not None else max(0.6, beat_dur)) / eff_speed
        prog = ease_func(min(1.0, age / settle_dur))
        target_pos = resolve_target_pos(cfg.target, actor_positions) or (start_cx, start_cy)
        target_roll = cfg.roll if cfg.roll != 0.0 else (-4.5 * eff_intensity)
        target_zoom = cfg.zoom if has_explicit_zoom else start_zoom
        roll = lerp(start_roll, target_roll, prog)
        zoom = lerp(start_zoom, target_zoom, prog)
        cx = lerp(start_cx, target_pos[0], prog)
        cy = lerp(start_cy, target_pos[1], prog)
        state = CameraState(zoom=zoom, center_x=cx, center_y=cy, roll_deg=roll)

    # 9. Earthquake Rumble (Impact shake)
    elif cam_type in ("rumble", "shake"):
        rumble_dur = (cfg.duration or 0.35) / eff_speed
        if age < rumble_dur:
            decay = (1.0 - age / rumble_dur) ** 2
            sx = math.sin(age * 55.0) * 14.0 * decay * eff_intensity
            sy = math.cos(age * 47.0) * 11.0 * decay * eff_intensity
            zoom = lerp(start_zoom, 1.03, min(1.0, age * 5.0))
            cx = lerp(start_cx, 0.5, min(1.0, age / rumble_dur))
            cy = lerp(start_cy, 0.5, min(1.0, age / rumble_dur))
            state = CameraState(zoom=zoom, center_x=cx, center_y=cy, shake_x=sx, shake_y=sy, roll_deg=cfg.roll)
        else:
            state = CameraState(zoom=1.0, center_x=0.5, center_y=0.5, roll_deg=cfg.roll)

    # 10. Handheld / Buoyant Sway (Gentle organic breathing)
    elif cam_type in ("sway", "buoyant", "handheld", "vlog"):
        pan_x = math.sin(age * 1.5) * 0.008 * eff_intensity
        pan_y = math.cos(age * 1.2) * 0.006 * eff_intensity
        roll = math.sin(age * 1.1) * 0.4 * eff_intensity + cfg.roll
        cx = lerp(start_cx, 0.5, min(1.0, age * 2.0)) + pan_x
        cy = lerp(start_cy, 0.5, min(1.0, age * 2.0)) + pan_y
        zoom = lerp(start_zoom, 1.02, min(1.0, age * 2.0))
        state = CameraState(zoom=zoom, center_x=cx, center_y=cy, roll_deg=roll)

    else:
        state = CameraState(zoom=1.0, center_x=0.5, center_y=0.5, roll_deg=cfg.roll)

    # Reactive Character Coupling: Camera shivers/bobs in lockstep with actor
    # Uses smooth envelope fade-in (0.40s) so shake does not spike/shock at frame 0
    if cfg.reactive_actor and actor_motions and cfg.reactive_actor in actor_motions:
        drift_x, bob_px = actor_motions[cfg.reactive_actor]
        shake_env = ease_smooth(min(1.0, age / 0.40))
        state.shake_x += drift_x * cfg.reactive_factor * shake_env
        state.shake_y += bob_px * cfg.reactive_factor * shake_env

    return state


# ---------------------------------------------------------------------------
# Scene Transitions (All functions preserve RGBA mode)
# ---------------------------------------------------------------------------

def apply_transition(
    canvas: Image.Image,
    prev_canvas: Image.Image | None,
    transition_type: str,
    age: float,
    duration: float = 0.22,
) -> Image.Image:
    """Apply visual transition overlay or blend between previous and current scene.

    Returns RGBA Image to allow subsequent alpha compositing.
    """
    if canvas.mode != "RGBA":
        canvas = canvas.convert("RGBA")

    if transition_type in ("none", ""):
        return canvas

    prog = min(1.0, max(0.0, age / max(0.01, duration)))

    # Flash / Bloom impact
    if transition_type in ("flash", "bloom"):
        inv = (1.0 - prog) ** 1.8
        alpha = int(210 * inv)
        if alpha > 0:
            flash_layer = Image.new("RGBA", canvas.size, (255, 255, 255, alpha))
            canvas.alpha_composite(flash_layer)
        return canvas

    # Dip to black
    if transition_type in ("dip_black", "fade_black"):
        alpha = int(255 * (1.0 - ease_out_cubic(prog)))
        if alpha > 0:
            black_layer = Image.new("RGBA", canvas.size, (0, 0, 0, alpha))
            canvas.alpha_composite(black_layer)
        return canvas

    # Crossfade
    if transition_type in ("crossfade", "dissolve"):
        if prev_canvas is not None and prev_canvas.size == canvas.size:
            curr_alpha = int(255 * ease_out_cubic(prog))
            prev_alpha = 255 - curr_alpha
            c_prev = prev_canvas.convert("RGBA")
            c_prev.putalpha(prev_alpha)
            res = canvas.copy()
            res.alpha_composite(c_prev)
            return res
        return canvas

    # Circle Wipe / Iris Out
    if transition_type in ("circle_wipe", "iris"):
        w, h = canvas.size
        max_r = math.hypot(w, h) / 2.0
        cur_r = max_r * ease_out_back(prog)
        mask = Image.new("L", (w, h), 0)
        mdraw = ImageDraw.Draw(mask)
        cx, cy = w // 2, h // 2
        mdraw.ellipse([cx - cur_r, cy - cur_r, cx + cur_r, cy + cur_r], fill=255)
        transparent = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        return Image.composite(canvas, transparent, mask)

    return canvas
