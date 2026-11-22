from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable
from PIL import Image, ImageDraw

from src.utils import ease_out_back, ease_out_cubic, lerp


@dataclass(slots=True)
class CameraState:
    """Computed state of the virtual camera for one frame."""
    zoom: float = 1.0          # camera scale (>1.0 zooms in)
    pan_x: float = 0.0         # pan offset in normalized canvas fraction (-0.1 to +0.1)
    pan_y: float = 0.0         # pan offset in normalized canvas fraction
    shake_x: float = 0.0       # rumble horizontal displacement in pixels
    shake_y: float = 0.0       # rumble vertical displacement in pixels
    roll_deg: float = 0.0      # camera roll rotation in degrees


# ---------------------------------------------------------------------------
# Camera Presets
# ---------------------------------------------------------------------------

def cam_zoom_punch(age: float, beat_dur: float, intensity: float = 1.0) -> CameraState:
    """Snappy zoom punch on beat entry that springs back smoothly."""
    dur = 0.32
    if age < dur:
        prog = age / dur
        spring = ease_out_back(prog)
        extra_zoom = max(0.0, (1.0 - spring)) * 0.07 * intensity
    else:
        extra_zoom = 0.0
    return CameraState(zoom=1.0 + extra_zoom)


def cam_slow_zoom_in(age: float, beat_dur: float, intensity: float = 1.0) -> CameraState:
    """Subtle, continuous cinematic push-in across the beat."""
    dur = max(0.1, beat_dur)
    prog = min(1.0, age / dur)
    zoom = 1.0 + 0.05 * ease_out_cubic(prog) * intensity
    return CameraState(zoom=zoom)


def cam_slow_zoom_out(age: float, beat_dur: float, intensity: float = 1.0) -> CameraState:
    """Subtle, continuous cinematic pull-out across the beat."""
    dur = max(0.1, beat_dur)
    prog = min(1.0, age / dur)
    zoom = 1.05 - 0.05 * ease_out_cubic(prog) * intensity
    return CameraState(zoom=zoom)


def cam_rumble(age: float, beat_dur: float, intensity: float = 1.0) -> CameraState:
    """Decaying comedic camera rumble/shake (stomps, impacts, loud laughs)."""
    dur = 0.35
    if age < dur:
        decay = (1.0 - age / dur) ** 2
        sx = math.sin(age * 55.0) * 14.0 * decay * intensity
        sy = math.cos(age * 47.0) * 11.0 * decay * intensity
        zoom = 1.0 + 0.03 * decay * intensity
        return CameraState(zoom=zoom, shake_x=sx, shake_y=sy)
    return CameraState(zoom=1.0)


def cam_buoyant_sway(age: float, beat_dur: float, intensity: float = 1.0) -> CameraState:
    """Gentle handheld/floating camera drift (swamp, ocean, dream)."""
    pan_x = math.sin(age * 1.5) * 0.015 * intensity
    pan_y = math.cos(age * 1.2) * 0.012 * intensity
    roll = math.sin(age * 1.1) * 0.6 * intensity
    return CameraState(zoom=1.02, pan_x=pan_x, pan_y=pan_y, roll_deg=roll)


def cam_static(age: float, beat_dur: float, intensity: float = 1.0) -> CameraState:
    """Rock-solid stationary camera."""
    return CameraState(zoom=1.0)


CAMERA_REGISTRY: dict[str, Callable[[float, float, float], CameraState]] = {
    "zoom_punch": cam_zoom_punch,
    "punch": cam_zoom_punch,
    "slow_zoom_in": cam_slow_zoom_in,
    "zoom_in": cam_slow_zoom_in,
    "slow_zoom_out": cam_slow_zoom_out,
    "zoom_out": cam_slow_zoom_out,
    "rumble": cam_rumble,
    "shake": cam_rumble,
    "sway": cam_buoyant_sway,
    "buoyant": cam_buoyant_sway,
    "static": cam_static,
}


def compute_camera(
    camera_name: str,
    age: float,
    beat_dur: float,
    intensity: float = 1.0,
) -> CameraState:
    func = CAMERA_REGISTRY.get(camera_name, cam_zoom_punch)
    return func(age, beat_dur, intensity)


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

    if age >= duration or not transition_type:
        return canvas

    prog = min(1.0, age / duration)

    if transition_type in ("flash", "bloom", "default"):
        # Quick white light flash/bloom that fades out
        alpha = int(140 * ((1.0 - prog) ** 1.8))
        if alpha > 0:
            flash_overlay = Image.new("RGBA", canvas.size, (255, 255, 255, alpha))
            return Image.alpha_composite(canvas, flash_overlay)

    elif transition_type in ("crossfade", "dissolve"):
        if prev_canvas is not None:
            p_rgba = prev_canvas.convert("RGBA") if prev_canvas.mode != "RGBA" else prev_canvas
            return Image.blend(p_rgba, canvas, prog)

    elif transition_type in ("circle_wipe", "iris"):
        cx, cy = canvas.width // 2, canvas.height // 2
        max_r = math.hypot(cx, cy)
        current_r = int(max_r * ease_out_cubic(prog))
        if current_r < max_r and prev_canvas is not None:
            p_rgba = prev_canvas.convert("RGBA") if prev_canvas.mode != "RGBA" else prev_canvas
            mask = Image.new("L", canvas.size, 0)
            m_draw = ImageDraw.Draw(mask)
            m_draw.ellipse(
                (cx - current_r, cy - current_r, cx + current_r, cy + current_r),
                fill=255,
            )
            return Image.composite(canvas, p_rgba, mask)

    elif transition_type in ("dip_black",):
        half = duration / 2.0
        if age < half:
            alpha = int(255 * (age / half))
        else:
            alpha = int(255 * (1.0 - (age - half) / half))
        if alpha > 0:
            black_ov = Image.new("RGBA", canvas.size, (0, 0, 0, alpha))
            return Image.alpha_composite(canvas, black_ov)

    return canvas
