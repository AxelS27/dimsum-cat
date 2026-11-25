from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

from src.utils import get_ease_func, lerp, resolve_pos

if TYPE_CHECKING:
    from src.models import ActorConfig


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

def motion_none(t: float, age: float, w_scale: float, speed: float = 1.0, intensity: float = 1.0) -> MotionState:
    """Completely stationary — zero bob, zero tilt, zero squash."""
    return MotionState()


def motion_breathe(t: float, age: float, w_scale: float, speed: float = 1.0, intensity: float = 1.0) -> MotionState:
    """Subtle, calm idle breathing without dizzying bounce or head-tilt."""
    s = speed
    i = intensity
    cycle = math.sin(t * 2.2 * s)
    return MotionState(
        bob_px=cycle * 1.5 * i * w_scale,
        drift_x=0.0,
        rot_deg=0.0,
        sq_x=1.0,
        sq_y=1.0,
        scale_mult=1.0 + cycle * 0.012 * i,
    )


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


def motion_walk(t: float, age: float, w_scale: float, speed: float = 1.0, intensity: float = 1.0) -> MotionState:
    """Rhythmic walking gait with cute footstep bobbing, step squash, and side-to-side sway."""
    s = speed
    i = intensity
    # Two steps per cycle (left step, right step)
    step_cycle = math.sin(t * math.pi * 3.6 * s)
    # Sharp footstep bounce — dips on contact, springs up on stride
    bob = -abs(step_cycle) * 16.0 * i * w_scale
    # Rhythmic swagger / head bob
    rot = math.sin(t * math.pi * 1.8 * s) * 4.0 * i
    # Squash on foot contact
    sq = -abs(step_cycle) * 0.045 * i
    breath = organic(t * s, freq=0.35, phase=0.0) * 0.020 * i
    return MotionState(
        bob_px=bob,
        drift_x=0.0,
        rot_deg=rot,
        sq_x=1.0 + sq,
        sq_y=1.0 - sq,
        scale_mult=1.0 + breath,
    )


def motion_float_walk(t: float, age: float, w_scale: float, speed: float = 1.0, intensity: float = 1.0) -> MotionState:
    """Dreamy, buoyant floating/hovering glide across space."""
    s = speed
    i = intensity
    bob = math.sin(age * 3.2 * s) * 14.0 * i * w_scale
    drift = math.cos(age * 1.6 * s) * 6.0 * i * w_scale
    rot = math.sin(age * 2.2 * s) * 3.5 * i
    sq = math.sin(age * 3.2 * s) * 0.025 * i
    breath = organic(t * s, freq=0.30, phase=1.0) * 0.020 * i
    return MotionState(
        bob_px=bob,
        drift_x=drift,
        rot_deg=rot,
        sq_x=1.0 + sq,
        sq_y=1.0 - sq,
        scale_mult=1.0 + breath,
    )


# ---------------------------------------------------------------------------
# Dynamic Actor Waypoint Trajectory & Auto-Tilt Physics
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TrajectoryState:
    """Dynamic movement and spatial trajectory state for an actor in a frame."""
    cx: float               # world X coordinate (0.0 to 1.0)
    cy: float               # world Y coordinate (0.0 to 1.0)
    vel_x: float            # velocity in X (units/sec)
    vel_y: float            # velocity in Y (units/sec)
    tilt_deg: float         # dynamic tilt angle (degrees) based on walk direction & velocity
    flip_x: bool            # effective flip_x (honoring auto_flip or manual flip_x)
    is_moving: bool         # whether actor is currently in motion


def eval_actor_trajectory(
    actor: ActorConfig,
    age: float,
    beat_dur: float,
) -> TrajectoryState:
    """Compute actor's world coordinates, velocity, dynamic tilt, and orientation."""
    raw_path = getattr(actor, "path", None)
    raw_move_to = getattr(actor, "move_to", None)

    waypoints: list[tuple[float, float]] = []
    if raw_path and isinstance(raw_path, (list, tuple)) and len(raw_path) >= 2:
        waypoints = [resolve_pos(p) for p in raw_path]
    elif raw_move_to is not None:
        p_start = resolve_pos(actor.pos)
        p_end = resolve_pos(raw_move_to)
        waypoints = [p_start, p_end]
    else:
        # Stationary actor
        p = resolve_pos(actor.pos)
        return TrajectoryState(
            cx=p[0],
            cy=p[1],
            vel_x=0.0,
            vel_y=0.0,
            tilt_deg=0.0,
            flip_x=actor.flip_x,
            is_moving=False,
        )

    eff_speed = max(0.05, getattr(actor, "move_speed", 1.0))
    move_dur = (actor.move_dur if actor.move_dur is not None else max(0.1, beat_dur)) / eff_speed

    loop_path = getattr(actor, "loop_path", False)
    if loop_path:
        norm_t = (age % max(0.01, move_dur)) / max(0.01, move_dur)
    else:
        norm_t = min(1.0, max(0.0, age / max(0.01, move_dur)))

    ease_func = get_ease_func(getattr(actor, "move_ease", "smooth"))

    def _sample_point(t_val: float) -> tuple[float, float]:
        if len(waypoints) == 1:
            return waypoints[0]
        num_segs = len(waypoints) - 1
        scaled = t_val * num_segs
        seg_idx = min(num_segs - 1, max(0, int(scaled)))
        local_t = scaled - seg_idx
        u = ease_func(local_t)
        p0 = waypoints[seg_idx]
        p1 = waypoints[seg_idx + 1]
        return lerp(p0[0], p1[0], u), lerp(p0[1], p1[1], u)

    cx, cy = _sample_point(norm_t)

    # Velocity estimation via numerical forward step
    delta_t = 0.02
    step_val = delta_t / max(0.05, move_dur)
    next_t = min(1.0, norm_t + step_val) if not loop_path else (norm_t + step_val) % 1.0
    if next_t != norm_t:
        nx, ny = _sample_point(next_t)
        dt = (next_t - norm_t) * move_dur
        vel_x = (nx - cx) / max(0.001, dt)
        vel_y = (ny - cy) / max(0.001, dt)
    else:
        prev_t = max(0.0, norm_t - step_val)
        px, py = _sample_point(prev_t)
        dt = (norm_t - prev_t) * move_dur
        vel_x = (cx - px) / max(0.001, dt) * 0.1
        vel_y = (cy - py) / max(0.001, dt) * 0.1

    is_moving = (abs(vel_x) > 0.008 or abs(vel_y) > 0.008) and (norm_t < 1.0 or loop_path)

    # Auto-tilt: lean forward into movement direction (negative angle = lean right, positive angle = lean left)
    auto_tilt = getattr(actor, "auto_tilt", True)
    if isinstance(auto_tilt, (int, float)) and not isinstance(auto_tilt, bool):
        lean_factor = float(auto_tilt)
    else:
        lean_factor = 1.0 if auto_tilt else 0.0

    tilt_deg = -lean_factor * 7.5 * math.tanh(vel_x * 4.0)

    # Auto-flip: face movement direction (right = flip_x False, left = flip_x True)
    auto_flip = getattr(actor, "auto_flip", True)
    if auto_flip:
        if vel_x > 0.02:
            effective_flip = False
        elif vel_x < -0.02:
            effective_flip = True
        else:
            effective_flip = actor.flip_x
    else:
        effective_flip = actor.flip_x

    return TrajectoryState(
        cx=cx,
        cy=cy,
        vel_x=vel_x,
        vel_y=vel_y,
        tilt_deg=tilt_deg,
        flip_x=effective_flip,
        is_moving=is_moving,
    )


# ---------------------------------------------------------------------------
# Registry & Resolver
# ---------------------------------------------------------------------------

MotionFunc = Callable[[float, float, float, float, float], MotionState]

MOTION_REGISTRY: dict[str, MotionFunc] = {
    "none": motion_none,
    "static": motion_none,
    "still": motion_none,
    "breathe": motion_breathe,
    "idle": motion_breathe,
    "float_gentle": motion_float_gentle,
    "heavy_bounce": motion_heavy_bounce,
    "belly_laugh": motion_heavy_bounce,
    "snappy_hops": motion_snappy_hops,
    "swim_pulse": motion_swim_pulse,
    "organic_groove": motion_organic_groove,
    "default": motion_breathe,
    "panic_jitter": motion_panic_jitter,
    "proud_strut": motion_proud_strut,
    "sleepy_drift": motion_sleepy_drift,
    "walk": motion_walk,
    "walking": motion_walk,
    "pacing": motion_walk,
    "step": motion_walk,
    "float_walk": motion_float_walk,
    "glide": motion_float_walk,
    "hover": motion_float_walk,
}

# Auto-mapping when a beat does not explicitly specify "motion"
ANIMATION_MOTION_MAP: dict[str, str] = {
    # Animals
    "alligator": "float_gentle",
    "crocodile": "heavy_bounce",
    "ladybug": "snappy_hops",
    "jellyfish": "swim_pulse",
    # Emotive animations
    "panic": "panic_jitter",
    "sick_fever": "panic_jitter",
    "laughing_hard": "heavy_bounce",
    "sleepy_yawn": "sleepy_drift",
    "determined": "proud_strut",
    # Stationary poses & props
    "knockout": "none",
    "table": "none",
    "plate_empty": "none",
    "plate_full": "none",
    "plate_half": "none",
    "chalkboard": "none",
    "box_closed": "none",
    "box_prop": "none",
}

CHARACTER_MOTION_MAP: dict[str, str] = {
    "taeho": "proud_strut",
    "bear_props": "none",
    "props": "none",
}


def resolve_motion_name(anim_name: str = "", character: str = "") -> str:
    """Find the best matching motion preset based on animation or character name."""
    if anim_name in ANIMATION_MOTION_MAP:
        return ANIMATION_MOTION_MAP[anim_name]
    if character in CHARACTER_MOTION_MAP:
        return CHARACTER_MOTION_MAP[character]
    return "breathe"


def compute_motion(
    motion_name: str,
    t: float,
    age: float,
    w_scale: float,
    speed: float = 1.0,
    intensity: float = 1.0,
) -> MotionState:
    """Compute procedural physics state for given motion preset."""
    func = MOTION_REGISTRY.get(motion_name, motion_breathe)
    return func(t, age, w_scale, speed, intensity)
