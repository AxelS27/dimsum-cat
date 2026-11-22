from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class MotionState:
    """Computed procedural physics state for a character frame."""
    bob_px: float = 0.0        # vertical offset in pixels (scaled by w_scale)
    drift_x: float = 0.0       # horizontal offset in pixels (scaled by w_scale)
    rot_deg: float = 0.0       # rotation angle in degrees
    sq_x: float = 1.0          # horizontal squash/stretch factor
    sq_y: float = 1.0          # vertical squash/stretch factor
    scale_mult: float = 1.0    # breathing / size pulsation factor


# ---------------------------------------------------------------------------
# Organic Noise
# ---------------------------------------------------------------------------

def organic(t: float, freq: float = 1.0, phase: float = 0.0) -> float:
    """Multi-layer sine noise. Returns roughly in [-1, 1]."""
    return (
        0.50 * math.sin(t * freq * 1.000 + phase) +
        0.25 * math.sin(t * freq * 2.137 + phase * 1.7) +
        0.15 * math.sin(t * freq * 3.841 + phase * 0.9) +
        0.10 * math.sin(t * freq * 7.293 + phase * 2.3)
    )


# ---------------------------------------------------------------------------
# Motion Behavior Algorithms
# ---------------------------------------------------------------------------

def motion_float_gentle(t: float, age: float, w_scale: float, speed: float = 1.0, intensity: float = 1.0) -> MotionState:
    """Calm, buoyant water/swamp float with gentle horizontal drift."""
    s = speed
    i = intensity
    bob = math.sin(age * 2.8 * s) * 16.0 * i * w_scale
    drift = math.cos(age * 1.4 * s) * 8.0 * i * w_scale
    rot = math.sin(age * 1.6 * s) * 4.5 * i
    sq = math.sin(age * 2.8 * s) * 0.025 * i
    breath = organic(t * s, freq=0.30, phase=0.0) * 0.020 * i
    return MotionState(
        bob_px=bob,
        drift_x=drift,
        rot_deg=rot,
        sq_x=1.0 + sq,
        sq_y=1.0 - sq,
        scale_mult=1.0 + breath,
    )


def motion_heavy_bounce(t: float, age: float, w_scale: float, speed: float = 1.0, intensity: float = 1.0) -> MotionState:
    """Chunky belly-laugh bounce and heavy stomps."""
    s = speed
    i = intensity
    hop = abs(math.sin(age * 5.2 * s)) * -26.0 * i * w_scale
    bob = hop + 10.0 * i * w_scale
    rot = math.sin(age * 3.6 * s) * 8.5 * i
    sq = math.sin(age * 5.2 * s) * 0.060 * i
    breath = organic(t * s, freq=0.40, phase=1.0) * 0.020 * i
    return MotionState(
        bob_px=bob,
        drift_x=0.0,
        rot_deg=rot,
        sq_x=1.0 + sq,
        sq_y=1.0 - sq,
        scale_mult=1.0 + breath,
    )


def motion_snappy_hops(t: float, age: float, w_scale: float, speed: float = 1.0, intensity: float = 1.0) -> MotionState:
    """Tiny, eager, rapid excited hops with sharp head tilts (ladybugs, small pets)."""
    s = speed
    i = intensity
    hop_cycle = math.sin(age * 6.5 * s)
    bob = (hop_cycle * 14.0 + (abs(hop_cycle) - 0.5) * -12.0) * i * w_scale
    rot = math.sin(age * 4.8 * s) * 9.5 * i
    sq = hop_cycle * 0.045 * i
    breath = organic(t * s, freq=0.50, phase=2.0) * 0.030 * i
    return MotionState(
        bob_px=bob,
        drift_x=0.0,
        rot_deg=rot,
        sq_x=1.0 + sq,
        sq_y=1.0 - sq,
        scale_mult=1.0 + breath,
    )


def motion_swim_pulse(t: float, age: float, w_scale: float, speed: float = 1.0, intensity: float = 1.0) -> MotionState:
    """Fluid underwater pulse thrusting up and drifting down (jellyfish, sea creatures)."""
    s = speed
    i = intensity
    pulse = (math.sin(age * 2.0 * s) ** 2) * 36.0 * i * w_scale
    bob = -pulse + 14.0 * i * w_scale
    rot = math.sin(age * 1.3 * s) * 6.0 * i
    sq = -math.sin(age * 2.0 * s) * 0.080 * i
    breath = organic(t * s, freq=0.25, phase=3.0) * 0.025 * i
    return MotionState(
        bob_px=bob,
        drift_x=0.0,
        rot_deg=rot,
        sq_x=1.0 + sq,
        sq_y=1.0 - sq,
        scale_mult=1.0 + breath,
    )


def motion_organic_groove(t: float, age: float, w_scale: float, speed: float = 1.0, intensity: float = 1.0) -> MotionState:
    """Classic Dimsum Cat playful bounce and rhythmic head tilt."""
    s = speed
    i = intensity
    bounce_cycle = math.sin(t * math.pi * 3.8 * s)
    bob = (bounce_cycle * 14.0 + organic(t * s, freq=0.90, phase=0.00) * 8.0) * i * w_scale
    rot = (math.sin(t * math.pi * 1.9 * s + 0.5) * 4.5 + organic(t * s, freq=0.55, phase=1.80) * 2.2) * i
    sq = bounce_cycle * 0.040 * i
    breath = organic(t * s, freq=0.35, phase=3.77) * 0.022 * i
    return MotionState(
        bob_px=bob,
        drift_x=0.0,
        rot_deg=rot,
        sq_x=1.0 + sq,
        sq_y=1.0 - sq,
        scale_mult=1.0 + breath,
    )


def motion_panic_jitter(t: float, age: float, w_scale: float, speed: float = 1.0, intensity: float = 1.0) -> MotionState:
    """Fast jittery trembling and high-frequency shiver (panic, cold, fever)."""
    s = speed
    i = intensity
    bob = (math.sin(age * 24.0 * s) * 5.0 + math.sin(age * 17.3 * s) * 3.0) * i * w_scale
    drift = math.sin(age * 21.0 * s) * 4.0 * i * w_scale
    rot = math.sin(age * 19.5 * s) * 4.0 * i
    sq = math.sin(age * 22.0 * s) * 0.03 * i
    breath = math.sin(age * 8.0 * s) * 0.035 * i
    return MotionState(
        bob_px=bob,
        drift_x=drift,
        rot_deg=rot,
        sq_x=1.0 + sq,
        sq_y=1.0 - sq,
        scale_mult=1.0 + breath,
    )


def motion_proud_strut(t: float, age: float, w_scale: float, speed: float = 1.0, intensity: float = 1.0) -> MotionState:
    """Confident, deliberate rhythmic sway and authoritative posture (Tae-ho the King)."""
    s = speed
    i = intensity
    step = math.sin(age * 3.2 * s)
    bob = (-abs(step) * 18.0 + 6.0) * i * w_scale
    rot = step * 6.0 * i
    sq = -step * 0.035 * i
    breath = organic(t * s, freq=0.30, phase=1.5) * 0.025 * i
    return MotionState(
        bob_px=bob,
        drift_x=0.0,
        rot_deg=rot,
        sq_x=1.0 + sq,
        sq_y=1.0 - sq,
        scale_mult=1.0 + breath,
    )


def motion_sleepy_drift(t: float, age: float, w_scale: float, speed: float = 1.0, intensity: float = 1.0) -> MotionState:
    """Slow drowsy nodding, heavy eyelids, and relaxed breathing."""
    s = speed
    i = intensity
    bob = math.sin(age * 1.2 * s) * 10.0 * i * w_scale
    rot = (math.sin(age * 0.8 * s) * 3.0 + 1.5) * i
    sq = math.sin(age * 1.2 * s) * 0.020 * i
    breath = math.sin(age * 1.2 * s) * 0.035 * i
    return MotionState(
        bob_px=bob,
        drift_x=0.0,
        rot_deg=rot,
        sq_x=1.0 + sq,
        sq_y=1.0 - sq,
        scale_mult=1.0 + breath,
    )


# ---------------------------------------------------------------------------
# Registry & Resolver
# ---------------------------------------------------------------------------

MotionFunc = Callable[[float, float, float, float, float], MotionState]

MOTION_REGISTRY: dict[str, MotionFunc] = {
    "float_gentle": motion_float_gentle,
    "heavy_bounce": motion_heavy_bounce,
    "belly_laugh": motion_heavy_bounce,
    "snappy_hops": motion_snappy_hops,
    "swim_pulse": motion_swim_pulse,
    "organic_groove": motion_organic_groove,
    "default": motion_organic_groove,
    "panic_jitter": motion_panic_jitter,
    "proud_strut": motion_proud_strut,
    "sleepy_drift": motion_sleepy_drift,
}

# Auto-mapping when a beat does not explicitly specify "motion"
ANIMATION_MOTION_MAP: dict[str, str] = {
    # Animals
    "alligator": "float_gentle",
    "crocodile": "heavy_bounce",
    "ladybug": "snappy_hops",
    "jellyfish": "swim_pulse",
    # Emotive Dimsum Cat animations
    "panic": "panic_jitter",
    "sick_fever": "panic_jitter",
    "laughing_hard": "heavy_bounce",
    "sleepy_yawn": "sleepy_drift",
    "determined": "proud_strut",
}

CHARACTER_MOTION_MAP: dict[str, str] = {
    "taeho": "proud_strut",
}


def resolve_motion_name(anim_name: str = "", character: str = "") -> str:
    """Find the best matching motion preset based on animation or character name."""
    if anim_name in ANIMATION_MOTION_MAP:
        return ANIMATION_MOTION_MAP[anim_name]
    if character in CHARACTER_MOTION_MAP:
        return CHARACTER_MOTION_MAP[character]
    return "organic_groove"


def compute_motion(
    motion_name: str,
    t: float,
    age: float,
    w_scale: float,
    speed: float = 1.0,
    intensity: float = 1.0,
) -> MotionState:
    """Compute procedural physics state for given motion preset."""
    func = MOTION_REGISTRY.get(motion_name, motion_organic_groove)
    return func(t, age, w_scale, speed, intensity)
