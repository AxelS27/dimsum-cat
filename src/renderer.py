from __future__ import annotations

import math
from typing import Iterator

from PIL import Image, ImageDraw, ImageFilter

from src.models import (
    ActorConfig,
    RenderConfig,
    RichTextSpan,
    StoryBeat,
    WATERMARK_PNG,
    TEXT_SIZES,
    SPRITE_UPSCALE,
    POSITIONS,
    ROOT,
)
from src.utils import (
    resolve_pos,
    find_font,
    measure,
    wrap_text,
    lerp,
    ease_out_cubic,
    ease_out_back,
    get_ease_func,
    strip_emoji,
)
from src.sprite import organic, make_sprite_schedule, load_frames
from src.motion import resolve_motion_name, compute_motion, eval_actor_trajectory, TrajectoryState
from src.camera import compute_camera, apply_transition
from src.vfx import render_vfx_layer


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_BG_IMAGE_CACHE: dict[str, Image.Image] = {}


def make_background(
    size: tuple[int, int],
    bg_hex: str,
    bg_image: str = "",
    story_dir: "Path | None" = None,
    zoom: float = 1.0,
    center_x: float = 0.5,
    center_y: float = 0.5,
    pan_x: float = 0.0,
    pan_y: float = 0.0,
    shake_x: float = 0.0,
    shake_y: float = 0.0,
) -> Image.Image:
    """Return background canvas with virtual camera center, zoom, and shake."""
    if bg_image:
        from pathlib import Path
        from src.models import ROOT
        p = Path(bg_image)
        if not p.is_absolute():
            p = (story_dir / bg_image) if story_dir else (ROOT / bg_image)

        # Cache oversized base (35% larger) so camera zoom/pan/track crops cleanly without borders
        ov_w, ov_h = int(size[0] * 1.35), int(size[1] * 1.35)
        cache_key_ov = f"{p}_ov_{ov_w}x{ov_h}"
        if cache_key_ov not in _BG_IMAGE_CACHE:
            img = Image.open(p).convert("RGBA")
            if img.size != (ov_w, ov_h):
                img = img.resize((ov_w, ov_h), Image.Resampling.LANCZOS)
            _BG_IMAGE_CACHE[cache_key_ov] = img

        base_ov = _BG_IMAGE_CACHE[cache_key_ov]

        eff_cx = center_x if (center_x != 0.5 or (pan_x == 0.0 and pan_y == 0.0)) else (0.5 + pan_x)
        eff_cy = center_y if (center_y != 0.5 or (pan_x == 0.0 and pan_y == 0.0)) else (0.5 + pan_y)

        if abs(zoom - 1.0) < 0.005 and abs(eff_cx - 0.5) < 0.001 and abs(eff_cy - 0.5) < 0.001 and abs(shake_x) < 0.5 and abs(shake_y) < 0.5:
            x0 = (ov_w - size[0]) // 2
            y0 = (ov_h - size[1]) // 2
            return base_ov.crop((x0, y0, x0 + size[0], y0 + size[1])).copy()

        # Camera transformed crop
        clamped_zoom = max(0.75, min(1.80, zoom))
        view_w = max(100, min(ov_w, int(size[0] / clamped_zoom)))
        view_h = max(100, min(ov_h, int(size[1] / clamped_zoom)))

        cx = ov_w * eff_cx + shake_x
        cy = ov_h * eff_cy + shake_y
        x0 = max(0, min(ov_w - view_w, int(cx - view_w / 2.0)))
        y0 = max(0, min(ov_h - view_h, int(cy - view_h / 2.0)))

        cropped = base_ov.crop((x0, y0, x0 + view_w, y0 + view_h))
        if cropped.size != size:
            return cropped.resize(size, Image.Resampling.BILINEAR)
        return cropped

    cache_key = f"solid:{size[0]}x{size[1]}:{bg_hex}"
    if cache_key in _BG_IMAGE_CACHE:
        return _BG_IMAGE_CACHE[cache_key].copy()

    hex_str = bg_hex.strip().lstrip("#")
    base = tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    canvas = Image.new("RGBA", size, (*base, 255))
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    lighter = tuple(min(255, c + 18) for c in base)
    ImageDraw.Draw(glow).ellipse(
        (-80, size[1] // 4, size[0] + 80, size[1] * 3 // 4),
        fill=(*lighter, 55),
    )
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(90)))
    _BG_IMAGE_CACHE[cache_key] = canvas
    return canvas.copy()


def _parse_hex_color(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    raw = value.strip().lstrip("#")
    if len(raw) != 6:
        return fallback
    try:
        return tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback


def _rich_space_width(draw: ImageDraw.ImageDraw, font, stroke_w: int = 7) -> int:
    """Calculates clean, natural space width between words matching standard typography."""
    return int(draw.textlength(" ", font=font))


def _flatten_spans_to_words(spans: list[RichTextSpan]) -> list[RichTextSpan]:
    """Convert spans into clean individual words preserving color."""
    words: list[RichTextSpan] = []
    for s in spans:
        for w in str(s.text).strip().split():
            if w:
                words.append(RichTextSpan(text=w, color=s.color))
    return words


def _measure_rich_line(
    draw: ImageDraw.ImageDraw,
    words: list[RichTextSpan],
    font,
    stroke_w: int = 7,
) -> tuple[int, int]:
    if not words:
        return 0, 0
    space_w = _rich_space_width(draw, font, stroke_w)
    width = sum(int(draw.textlength(w.text, font=font)) for w in words) + max(0, len(words) - 1) * space_w
    height = max(measure(draw, w.text, font)[1] for w in words)
    return width, height


def _wrap_rich_spans(
    draw: ImageDraw.ImageDraw,
    spans: list[RichTextSpan],
    font,
    max_w: int,
    stroke_w: int = 7,
) -> list[list[RichTextSpan]]:
    """Break spans into rows of words that each fit within max_w."""
    words = _flatten_spans_to_words(spans)
    if not words:
        return []

    space_w = _rich_space_width(draw, font, stroke_w)
    rows: list[list[RichTextSpan]] = []
    current_row: list[RichTextSpan] = []
    current_w = 0

    for word in words:
        w = int(draw.textlength(word.text, font=font))
        added_w = (space_w if current_row else 0) + w
        if current_w + added_w > max_w and current_row:
            rows.append(current_row)
            current_row = [word]
            current_w = w
        else:
            current_row.append(word)
            current_w += added_w

    if current_row:
        rows.append(current_row)
    return rows


def _draw_rich_line(
    draw: ImageDraw.ImageDraw,
    words: list[RichTextSpan],
    font,
    x: int,
    y: int,
    alpha: int,
    stroke_w: int = 7,
) -> None:
    if not words:
        return
    space_w = _rich_space_width(draw, font, stroke_w)
    shadow_a = int(80 * alpha / 255)

    # First pass: drop shadow with matching stroke
    cursor = x
    for word in words:
        draw.text((cursor + 4, y + 4), word.text, font=font, fill=(0, 0, 0, shadow_a), stroke_width=stroke_w, stroke_fill=(0, 0, 0, shadow_a))
        cursor += int(draw.textlength(word.text, font=font)) + space_w

    # Second pass: main text with crisp white outline
    cursor = x
    for word in words:
        color = _parse_hex_color(word.color, (42, 42, 42))
        draw.text((cursor, y), word.text, font=font, fill=(*color, alpha), stroke_width=stroke_w, stroke_fill=(255, 255, 255, alpha))
        cursor += int(draw.textlength(word.text, font=font)) + space_w


_TEXT_OVERLAY_CACHE: dict[tuple, tuple[Image.Image, int]] = {}


def draw_text_overlay(
    canvas: Image.Image,
    text: str,
    sub: str,
    size_key: str,
    alpha: int,
    w_scale: float,
    rich_text: list[RichTextSpan] | None = None,
    rich_text_sub: list[RichTextSpan] | None = None,
    y_offset: int = 0,
    x_offset: int = 0,
) -> None:
    """Render text directly on canvas — no card/box, drop shadow only."""
    rich_text     = rich_text     or []
    rich_text_sub = rich_text_sub or []
    if not text and not sub and not rich_text and not rich_text_sub:
        return

    # Fast cache lookup for steady-state frames (alpha=255, x_offset=0, y_offset=0)
    cache_key = None
    if alpha == 255 and y_offset == 0 and x_offset == 0:
        rt_key = tuple((s.text, s.color) for s in rich_text) if rich_text else ()
        rts_key = tuple((s.text, s.color) for s in rich_text_sub) if rich_text_sub else ()
        cache_key = (text, sub, size_key, round(w_scale, 3), rt_key, rts_key, canvas.width, canvas.height)
        cached = _TEXT_OVERLAY_CACHE.get(cache_key)
        if cached is not None:
            patch, paste_y = cached
            canvas.alpha_composite(patch, (0, paste_y))
            return

    main_px, sub_px = TEXT_SIZES.get(size_key, TEXT_SIZES["normal"])
    main_font = find_font(int(main_px * w_scale), bold=True)
    sub_font  = find_font(int(sub_px  * w_scale), bold=False)

    margin  = int(56 * w_scale)
    max_w   = canvas.width - margin * 2
    gap_ln  = int(10 * w_scale)   # between lines in a block
    gap_blk = int(20 * w_scale)   # between main and sub block

    proxy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    main_lines = [] if rich_text else (wrap_text(proxy, text, main_font, max_w) if text else [])
    sub_clean  = strip_emoji(sub) if sub else ""
    sub_lines  = [] if rich_text_sub else (wrap_text(proxy, sub_clean, sub_font, max_w) if sub_clean else [])

    rich_rows     = _wrap_rich_spans(proxy, rich_text,     main_font, max_w) if rich_text     else []
    rich_sub_rows = _wrap_rich_spans(proxy, rich_text_sub, sub_font,  max_w) if rich_text_sub else []

    # Measure total block height so we can vertically center in the text zone
    total_h = 0
    if rich_rows:
        for row in rich_rows:
            total_h += _measure_rich_line(proxy, row, main_font)[1] + gap_ln
    else:
        for line in main_lines:
            total_h += measure(proxy, line, main_font)[1] + gap_ln
    if rich_sub_rows:
        total_h += gap_blk
        for row in rich_sub_rows:
            total_h += _measure_rich_line(proxy, row, sub_font)[1] + gap_ln
    elif sub_lines:
        total_h += gap_blk
        for line in sub_lines:
            total_h += measure(proxy, line, sub_font)[1] + gap_ln

    # Text zone: top 27% of canvas — character lives below this
    zone_top = int(canvas.height * 0.06)
    zone_h   = int(canvas.height * 0.27)
    target_y = zone_top + max(0, (zone_h - total_h) // 2) + y_offset

    # Allocate only a compact vertical strip instead of a full 1080x1920 image
    pad_y = int(14 * w_scale)
    patch_h = total_h + pad_y * 2
    layer = Image.new("RGBA", (canvas.width, patch_h), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)
    y = pad_y

    if rich_rows:
        for row in rich_rows:
            w, h = _measure_rich_line(draw, row, main_font)
            x = (canvas.width - w) // 2 + x_offset
            _draw_rich_line(draw, row, main_font, x, y, alpha)
            y += h + gap_ln
    else:
        for line in main_lines:
            w, h = measure(draw, line, main_font)
            x = (canvas.width - w) // 2 + x_offset
            shadow_a = int(80 * alpha / 255)
            draw.text((x + 4, y + 4), line, font=main_font, fill=(0, 0, 0, shadow_a), stroke_width=7, stroke_fill=(0, 0, 0, shadow_a))
            draw.text((x, y), line, font=main_font, fill=(42, 42, 42, alpha), stroke_width=7, stroke_fill=(255, 255, 255, alpha))
            y += h + gap_ln

    if rich_sub_rows:
        y += gap_blk
        for row in rich_sub_rows:
            w, h = _measure_rich_line(draw, row, sub_font)
            x = (canvas.width - w) // 2 + x_offset
            _draw_rich_line(draw, row, sub_font, x, y, alpha)
            y += h + gap_ln
    elif sub_lines:
        y += gap_blk
        for line in sub_lines:
            w, h = measure(draw, line, sub_font)
            x = (canvas.width - w) // 2 + x_offset
            shadow_a = int(70 * alpha / 255)
            draw.text((x + 3, y + 3), line, font=sub_font, fill=(0, 0, 0, shadow_a), stroke_width=5, stroke_fill=(0, 0, 0, shadow_a))
            draw.text((x, y), line, font=sub_font, fill=(30, 30, 30, alpha), stroke_width=5, stroke_fill=(255, 255, 255, alpha))
            y += h + gap_ln

    paste_y = target_y - pad_y
    if cache_key is not None:
        _TEXT_OVERLAY_CACHE[cache_key] = (layer, paste_y)

    if paste_y >= 0 and paste_y + patch_h <= canvas.height:
        canvas.alpha_composite(layer, (0, paste_y))
    else:
        py0 = max(0, -paste_y)
        py1 = min(patch_h, canvas.height - paste_y)
        if py1 > py0:
            canvas.alpha_composite(layer.crop((0, py0, canvas.width, py1)), (0, max(0, paste_y)))


def _render_accessory(
    canvas: Image.Image,
    acc,
    config: RenderConfig,
    idx: int,
    actor_anchors: list[dict] | None = None,
) -> None:
    """Load, transform, and composite one Accessory onto canvas (optionally attached to an actor)."""
    from pathlib import Path as _APath
    ap = _APath(acc.image)
    if not ap.is_absolute():
        candidate = config.story_dir / ap if config.story_dir else None
        ap = candidate if (candidate and candidate.exists()) else (ROOT / ap)
    if not ap.exists():
        return
    if ap.is_dir():
        num_frames = sorted(ap.glob("frame_[0-9][0-9].png"))
        if num_frames:
            acc_frames = [Image.open(p).convert("RGBA") for p in num_frames]
        else:
            from src.models import FRAME_NAMES as _FN
            acc_frames = [Image.open(ap / f).convert("RGBA") for f in _FN if (ap / f).exists()]
        if not acc_frames:
            return
        frame_i = idx // max(1, config.fps // 2) % len(acc_frames)
        acc_img = acc_frames[frame_i]
    else:
        acc_img = Image.open(ap).convert("RGBA")

    eff_scale = acc.scale
    eff_flip = acc.flip_x
    eff_rot = acc.rotate
    anchor_px: tuple[float, float] | None = None

    attach_target = (getattr(acc, "attach_to", "") or "").strip()
    if attach_target and actor_anchors:
        match = next(
            (a for a in actor_anchors if a.get("character") == attach_target or str(a.get("index")) == attach_target),
            None,
        )
        if match is None:
            return
        eff_scale *= float(match.get("scale", 1.0))
        actor_flip = bool(match.get("flip_x", False))
        eff_flip = bool(eff_flip) ^ actor_flip
        actor_rot = float(match.get("rot_deg", 0.0))
        eff_rot += actor_rot
        off = getattr(acc, "offset", (0.0, 0.0)) or (0.0, 0.0)
        dx = float(off[0]) * match["sprite_size"][0] * (-1.0 if actor_flip else 1.0)
        dy = float(off[1]) * match["sprite_size"][1]
        if abs(actor_rot) > 0.1:
            rad = math.radians(-actor_rot)
            rx = dx * math.cos(rad) - dy * math.sin(rad)
            ry = dx * math.sin(rad) + dy * math.cos(rad)
            dx, dy = rx, ry
        anchor_px = (match["pos"][0] + dx, match["pos"][1] + dy)

    target_w = max(1, int(config.width * eff_scale))
    ratio = target_w / acc_img.width
    acc_img = acc_img.resize((target_w, max(1, int(acc_img.height * ratio))), Image.Resampling.BILINEAR)
    if eff_flip:
        acc_img = acc_img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if abs(eff_rot) > 0.3:
        acc_img = acc_img.rotate(-eff_rot, expand=True, resample=Image.Resampling.BILINEAR)

    if anchor_px is not None:
        ax = int(anchor_px[0] - acc_img.width // 2)
        ay = int(anchor_px[1] - acc_img.height // 2)
    else:
        acc_pos = POSITIONS.get(acc.pos) if acc.pos in POSITIONS else None
        if acc_pos is None:
            try:
                parts = str(acc.pos).split(",")
                acc_pos = (float(parts[0]), float(parts[1]))
            except Exception:
                acc_pos = (0.5, 0.5)
        ax = int(config.width * acc_pos[0] - acc_img.width // 2)
        ay = int(config.height * acc_pos[1] - acc_img.height // 2)

    ax0 = max(0, -ax); ax1 = min(acc_img.width, config.width - ax)
    ay0 = max(0, -ay); ay1 = min(acc_img.height, config.height - ay)
    if ax1 > ax0 and ay1 > ay0:
        canvas.alpha_composite(acc_img.crop((ax0, ay0, ax1, ay1)), (max(0, ax), max(0, ay)))


def iter_video_frames(
    config: RenderConfig,
    frame_start: int = 0,
    frame_end: int | None = None,
) -> Iterator[Image.Image]:
    total_frames = max(1, int(config.duration * config.fps))
    frame_end = total_frames if frame_end is None else min(frame_end, total_frames)
    w_scale = config.width / 720

    # Pre-load all animations referenced in beats/actors, keyed by (character, animation)
    anim_keys: set[tuple[str, str]] = {(config.default_character, config.default_animation)}
    for b in config.beats:
        for a in b.get_actors(config.default_character, config.default_animation):
            ch = a.character or config.default_character
            anim = a.animation or config.default_animation
            if anim:
                anim_keys.add((ch, anim))

    anim_cache: dict[tuple[str, str], tuple[list[Image.Image], tuple[int, int]]] = {}
    for ch, name in anim_keys:
        try:
            anim_cache[(ch, name)] = load_frames(name, character=ch)
        except Exception as e:
            if (config.default_character, config.default_animation) in anim_cache:
                anim_cache[(ch, name)] = anim_cache[(config.default_character, config.default_animation)]
            else:
                anim_cache[(ch, name)] = load_frames(config.default_animation, character=config.default_character)

    # Sort and ensure a beat at t=0
    beats = sorted(config.beats, key=lambda b: b.time)
    if not beats or beats[0].time > 0:
        first = beats[0] if beats else None
        first_actors = first.get_actors(config.default_character, config.default_animation) if first else []
        beats.insert(0, StoryBeat(
            time=0, text="",
            animation=config.default_animation,
            pos=first.pos if first else "center",
            scale=first.scale if first else 1.0,
            bg_image=first.bg_image if first else "",
            character=first.character if first else "",
            actors=first_actors,
        ))

    # Pre-compute irregular sprite schedule per (character, animation)
    sprite_schedules: dict[tuple[str, str], list[int]] = {
        key: make_sprite_schedule(total_frames, config.fps, len(frames))
        for key, (frames, _) in anim_cache.items()
    }

    # Load PNG watermark once, scaled to 42% of canvas width, semi-transparent
    from pathlib import Path as _Path
    from src.models import ROOT as _ROOT
    wm_img: Image.Image | None = None
    _wm_path = WATERMARK_PNG
    if config.watermark:
        _p = _Path(config.watermark)
        if not _p.is_absolute():
            _p = (config.story_dir / config.watermark) if config.story_dir else (_ROOT / config.watermark)
        if _p.exists():
            _wm_path = _p
    if _wm_path.exists():
        _wm = Image.open(_wm_path).convert("RGBA")
        wm_target_w = int(config.width * 0.42)
        wm_ratio    = wm_target_w / _wm.width
        _wm = _wm.resize(
            (wm_target_w, max(1, int(_wm.height * wm_ratio))),
            Image.Resampling.LANCZOS,
        )
        # Apply global transparency (keep existing alpha, just scale it down)
        import numpy as np
        arr = np.array(_wm, dtype=np.float32)
        arr[:, :, 3] *= 0.48          # 48% opacity — readable but not distracting
        wm_img = Image.fromarray(arr.astype(np.uint8), "RGBA")

    def beat_at(t: float) -> tuple[int, StoryBeat]:
        idx = 0
        for i, b in enumerate(beats):
            if b.time <= t:
                idx = i
        return idx, beats[idx]

    ENTRANCE_DUR = 0.35
    last_cam_state: CameraState | None = None
    last_beat_idx: int = -1
    beat_cam_start: CameraState | None = None
    prev_chars: set[str] = set()

    for idx in range(frame_start, frame_end):
        t = idx / config.fps
        beat_idx, beat = beat_at(t)
        age = t - beat.time

        # Track camera and actor continuity across beats in the same scene
        if beat_idx != last_beat_idx:
            if last_beat_idx >= 0 and last_cam_state is not None:
                prev_b = beats[last_beat_idx]
                prev_bg = prev_b.bg_image or config.bg_image
                curr_bg = beat.bg_image or config.bg_image

                # Hard cut if background changed or hard transition used
                is_scene_cut = (
                    prev_bg != curr_bg
                    or beat.transition in ("dip_black", "fade_black", "circle_wipe", "iris", "cut")
                    or getattr(beat.get_camera_config(), "type", "") == "cut"
                )
                beat_cam_start = None if is_scene_cut else last_cam_state
                prev_actors = prev_b.get_actors(config.default_character, config.default_animation)
                prev_chars = {a.character or config.default_character for a in prev_actors} if not is_scene_cut else set()
            elif beat_idx > 0 and last_beat_idx < 0:
                # Started mid-stream (chunk or preview)
                prev_b = beats[beat_idx - 1]
                prev_bg = prev_b.bg_image or config.bg_image
                curr_bg = beat.bg_image or config.bg_image
                is_scene_cut = (
                    prev_bg != curr_bg
                    or beat.transition in ("dip_black", "fade_black", "circle_wipe", "iris", "cut")
                    or getattr(beat.get_camera_config(), "type", "") == "cut"
                )
                beat_cam_start = None
                prev_actors = prev_b.get_actors(config.default_character, config.default_animation)
                prev_chars = {a.character or config.default_character for a in prev_actors} if not is_scene_cut else set()
            else:
                beat_cam_start = None
                prev_chars = set()
            last_beat_idx = beat_idx

        # ----------------------------------------------------------------
        # Beat Duration & Dynamic Actor Trajectory Pre-Evaluation
        # ----------------------------------------------------------------
        if beat_idx + 1 < len(beats):
            beat_dur = max(0.1, beats[beat_idx + 1].time - beat.time)
        else:
            beat_dur = max(0.1, config.duration - beat.time)

        actors = beat.get_actors(config.default_character, config.default_animation)
        sorted_actors = sorted(actors, key=lambda a: a.z_index)

        # Collect dynamic actor trajectory positions and evaluate motions for camera coupling
        actor_positions: dict[str, tuple[float, float]] = {}
        actor_motions: dict[str, tuple[float, float]] = {}
        actor_trajectories: dict[int, TrajectoryState] = {}
        for a_idx, a in enumerate(sorted_actors):
            ch = a.character or config.default_character
            an = a.animation or config.default_animation
            traj = eval_actor_trajectory(a, age=age, beat_dur=beat_dur)
            actor_trajectories[a_idx] = traj
            actor_positions[ch] = (traj.cx, traj.cy)
            mp = a.motion
            if not mp:
                mp = "walk" if traj.is_moving else resolve_motion_name(an, ch)
            ms = compute_motion(mp, t=t, age=age, w_scale=w_scale, speed=a.motion_speed, intensity=a.motion_intensity)
            actor_motions[ch] = (ms.drift_x, ms.bob_px)

        # ----------------------------------------------------------------
        # Virtual Cinematic Director Camera
        # ----------------------------------------------------------------
        cam_cfg = beat.get_camera_config()
        cam = compute_camera(
            cam_cfg,
            age=age,
            beat_dur=beat_dur,
            intensity=cam_cfg.intensity,
            actor_positions=actor_positions,
            actor_motions=actor_motions,
            cam_start=beat_cam_start,
        )
        last_cam_state = cam
        if config.bpm and config.bpm > 0 and config.auto_beat_zoom > 0.0:
            bt = t - config.beat_offset
            if bt >= 0.0:
                beat_period = 60.0 / config.bpm
                phase = (bt % beat_period) / beat_period
                cam.zoom += math.exp(-phase * 5.0) * config.auto_beat_zoom

        # ----------------------------------------------------------------
        # Compose Background with Virtual Camera
        # ----------------------------------------------------------------
        active_bg_image = beat.bg_image or config.bg_image
        canvas = make_background(
            (config.width, config.height), config.bg,
            bg_image=active_bg_image, story_dir=config.story_dir,
            zoom=cam.zoom, center_x=cam.center_x, center_y=cam.center_y,
            shake_x=cam.shake_x, shake_y=cam.shake_y,
        )

        # Scene Transitions: Default is "none"! Never flash white randomly!
        trans_type = getattr(beat, "transition", "") or "none"
        trans_dur = getattr(beat, "transition_dur", 0.22)
        if trans_type != "none" and age < trans_dur:
            canvas = apply_transition(canvas, None, trans_type, age, duration=trans_dur)

        # Unattached accessories — composited BEFORE characters
        for acc in beat.accessories:
            if not getattr(acc, "attach_to", ""):
                _render_accessory(canvas, acc, config, idx)

        # ----------------------------------------------------------------
        # Multi-Actor Staging & Ground Shadows (Virtual Camera Projected)
        # ----------------------------------------------------------------
        actor_anchors: list[dict] = []

        for a_idx, actor in enumerate(sorted_actors):
            if age < actor.delay:
                continue
            actor_age = age - actor.delay
            active_dur = max(0.05, beat_dur - actor.delay)
            kf_t = get_ease_func(actor.move_ease)(min(1.0, actor_age / active_dur))

            eff_opacity = max(0.0, min(1.0, actor.opacity))
            if actor.fade_in > 0.0 and actor_age < actor.fade_in:
                eff_opacity *= max(0.0, actor_age / actor.fade_in)
            rem_dur = max(0.0, beat_dur - age)
            if actor.fade_out > 0.0 and rem_dur < actor.fade_out:
                eff_opacity *= max(0.0, rem_dur / actor.fade_out)
            if eff_opacity <= 0.01:
                continue

            act_char = actor.character or config.default_character
            act_anim = actor.animation or config.default_animation
            cache_key = (act_char, act_anim)
            if cache_key not in anim_cache:
                anim_cache[cache_key] = load_frames(act_anim, character=act_char)
                sprite_schedules[cache_key] = make_sprite_schedule(total_frames, config.fps, len(anim_cache[cache_key][0]))

            sprite_frames, orig_size = anim_cache[cache_key]
            schedule = sprite_schedules[cache_key]
            sprite = sprite_frames[schedule[idx % len(schedule)]].copy()
            orig_w, orig_h = orig_size

            # Dynamic Trajectory (waypoints, movement path, auto-tilt, auto-flip)
            traj = actor_trajectories.get(a_idx) or eval_actor_trajectory(actor, age=actor_age, beat_dur=active_dur)
            target_cx, target_cy = traj.cx, traj.cy
            target_scale = lerp(actor.scale, actor.scale_to, kf_t) if actor.scale_to is not None else actor.scale
            extra_rotate = lerp(actor.rotate, actor.rotate_to, kf_t) if actor.rotate_to is not None else actor.rotate

            # Entrance bounce/pop only triggers for brand new appearances on stage
            is_new_actor = (act_char not in prev_chars) or (actor.delay > 0.0)
            if is_new_actor and actor_age < ENTRANCE_DUR:
                prog = actor_age / ENTRANCE_DUR
                spring = ease_out_back(prog)
                char_scale = target_scale * (0.60 + 0.40 * spring)
                rise = (1.0 - ease_out_cubic(prog)) * 0.07
            else:
                char_scale = target_scale
                rise = 0.0

            # Motion behavior physics (auto-select walk gait if actor is moving along a path)
            motion_preset = actor.motion
            if not motion_preset:
                motion_preset = "walk" if traj.is_moving else resolve_motion_name(act_anim, act_char)
            motion_state = compute_motion(
                motion_preset,
                t=t,
                age=actor_age,
                w_scale=w_scale,
                speed=actor.motion_speed,
                intensity=actor.motion_intensity,
            )
            bob_px = motion_state.bob_px
            world_cx = target_cx + (motion_state.drift_x / config.width)
            world_cy = target_cy + rise + (bob_px / config.height)

            # Virtual Camera 2D Projection:
            screen_cx = 0.5 + (world_cx - cam.center_x) * cam.zoom + (cam.shake_x / config.width)
            screen_cy = 0.5 + (world_cy - cam.center_y) * cam.zoom + (cam.shake_y / config.height)
            char_scale *= motion_state.scale_mult * cam.zoom
            # Auto-tilt in direction of movement + camera roll + manual/keyframed rotate + organic rot
            rot_deg = motion_state.rot_deg + traj.tilt_deg + cam.roll_deg + extra_rotate
            sq_x = motion_state.sq_x
            sq_y = motion_state.sq_y

            # Sprite scaling
            target_cat_w = config.width * 0.62 * char_scale
            sf = target_cat_w / (orig_w * SPRITE_UPSCALE)
            new_w = max(1, int(sprite.width  * sf * sq_x))
            new_h = max(1, int(sprite.height * sf * sq_y))
            sprite = sprite.resize((new_w, new_h), Image.Resampling.BILINEAR)

            # Dynamic orientation (auto-flip to face walking direction or manual flip)
            if traj.flip_x:
                sprite = sprite.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

            # Rotate
            if abs(rot_deg) > 0.3:
                sprite = sprite.rotate(rot_deg, expand=True, resample=Image.Resampling.BILINEAR)

            # Apply keyframed / fade opacity
            if eff_opacity < 0.999:
                r_c, g_c, b_c, a_c = sprite.split()
                a_c = a_c.point(lambda p, mult=eff_opacity: int(p * mult))
                sprite = Image.merge("RGBA", (r_c, g_c, b_c, a_c))

            # Anchor coordinates
            sx = int(config.width  * screen_cx - sprite.width  // 2)
            sy = int(config.height * screen_cy - sprite.height // 2)

            # Contact / Ground Shadow (in camera projected screen space)
            if actor.ground_shadow:
                ground_screen_y = int(config.height * (0.5 + (target_cy - cam.center_y) * cam.zoom) + sprite.height // 2 - int(24 * w_scale) + cam.shake_y)
                jump_px = max(0.0, -bob_px)
                jump_factor = 1.0 / (1.0 + jump_px / (45.0 * w_scale))
                sh_w = int(sprite.width * 0.58 * sq_x * jump_factor)
                sh_h = max(4, int(sh_w * 0.24 * sq_y * jump_factor))
                sh_alpha = int(75 * jump_factor * eff_opacity)
                if sh_w > 8 and sh_h > 2 and sh_alpha > 5:
                    blur_rad = max(1, int(6 * w_scale))
                    pad = blur_rad * 3
                    patch_w = sh_w + pad * 2
                    patch_h = sh_h + pad * 2
                    sh_patch = Image.new("RGBA", (patch_w, patch_h), (0, 0, 0, 0))
                    sh_draw = ImageDraw.Draw(sh_patch)
                    sh_draw.ellipse([pad, pad, pad + sh_w, pad + sh_h], fill=(20, 25, 35, sh_alpha))
                    sh_patch = sh_patch.filter(ImageFilter.GaussianBlur(radius=blur_rad))

                    sh_cx = int(config.width * screen_cx)
                    dst_x = sh_cx - sh_w // 2 - pad
                    dst_y = ground_screen_y - sh_h // 2 - pad

                    px0 = max(0, -dst_x)
                    py0 = max(0, -dst_y)
                    px1 = min(patch_w, config.width - dst_x)
                    py1 = min(patch_h, config.height - dst_y)
                    if px1 > px0 and py1 > py0:
                        canvas.alpha_composite(
                            sh_patch.crop((px0, py0, px1, py1)),
                            (max(0, dst_x), max(0, dst_y)),
                        )

            # Composite character sprite
            src_x0 = max(0, -sx);  src_x1 = min(sprite.width,  config.width  - sx)
            src_y0 = max(0, -sy);  src_y1 = min(sprite.height, config.height - sy)
            if src_x1 > src_x0 and src_y1 > src_y0:
                canvas.alpha_composite(
                    sprite.crop((src_x0, src_y0, src_x1, src_y1)),
                    (max(0, sx), max(0, sy)),
                )

            # Character head anchor calculation (calibrated to character sprite proportions)
            is_duck = ("duck" in act_char.lower())
            head_offset_ratio = 0.24 if is_duck else 0.30
            # If actor is lying down (knockout / fallen)
            if "knockout" in act_anim.lower():
                char_head_x = config.width * screen_cx + (int(sprite.width * 0.18) if not traj.flip_x else -int(sprite.width * 0.18))
                char_head_y = config.height * screen_cy - int(sprite.height * 0.08)
            else:
                char_head_x = config.width * screen_cx + (int(sprite.width * (0.05 if not is_duck else 0.02)) * (1.0 if not traj.flip_x else -1.0))
                char_head_y = config.height * screen_cy - int(sprite.height * head_offset_ratio)

            actor_anchors.append({
                "index": a_idx,
                "character": act_char,
                "pos": (config.width * screen_cx, config.height * screen_cy),
                "head_pos": (char_head_x, char_head_y),
                "sprite_size": (sprite.width, sprite.height),
                "flip_x": traj.flip_x,
                "w_scale": w_scale,
                "scale": char_scale,
                "rot_deg": rot_deg,
                "vfx": getattr(actor, "vfx", []),
            })

        # Attached accessories — composited AFTER characters so they follow actor motion
        for acc in beat.accessories:
            if getattr(acc, "attach_to", ""):
                _render_accessory(canvas, acc, config, idx, actor_anchors=actor_anchors)

        # ----------------------------------------------------------------
        # Kawaii VFX Particle Overlay (Per-Actor, Target-Filtered, or Free Position)
        # ----------------------------------------------------------------
        all_vfx: list[dict] = []
        for a_dict in actor_anchors:
            for v in a_dict.get("vfx", []):
                v_copy = dict(v)
                if "target" not in v_copy:
                    v_copy["target"] = a_dict["character"] or a_dict["index"]
                all_vfx.append(v_copy)
        for v in beat.vfx:
            if isinstance(v, str):
                all_vfx.append({"type": v})
            elif isinstance(v, dict):
                all_vfx.append(v)

        if all_vfx:
            vfx_img = render_vfx_layer(
                (config.width, config.height),
                all_vfx,
                t=t,
                age=age,
                anchor_positions=actor_anchors,
                w_scale=w_scale,
                beat_dur=beat_dur,
            )
            canvas.alpha_composite(vfx_img)

        # ----------------------------------------------------------------
        # Speech Bubble / Text Overlay (with optional Kinetic Typography)
        # ----------------------------------------------------------------
        t_anim = (getattr(beat, "text_anim", "") or "").strip().lower()
        disp_text = beat.text
        disp_rich = beat.rich_text
        text_x_offset = 0
        if t_anim == "typewriter" and beat.text:
            reveal_dur = min(max(0.25, len(beat.text) * 0.045), max(0.25, beat_dur * 0.7))
            frac = min(1.0, age / reveal_dur)
            n_chars = max(1, int(round(len(beat.text) * frac)))
            disp_text = beat.text[:n_chars]
            disp_rich = [] if n_chars < len(beat.text) else beat.rich_text
            text_y_offset = 0
            text_alpha = 255
        elif t_anim == "shake":
            text_x_offset = int(math.sin(age * 48.0) * 6.0 * w_scale)
            text_y_offset = int(math.cos(age * 39.0) * 5.0 * w_scale)
            text_alpha = 255
        else:
            TEXT_ENTRANCE = 0.34 if t_anim == "pop" else 0.28
            y_amp = -38.0 if t_anim == "pop" else -22.0
            if age < TEXT_ENTRANCE:
                prog = age / TEXT_ENTRANCE
                spring = ease_out_back(prog)
                text_y_offset = int((1.0 - spring) * y_amp * w_scale)
                text_alpha = min(255, int(255 * (prog ** 0.8))) if (beat_idx > 0 or t_anim == "pop") else 255
            else:
                text_y_offset = 0
                text_alpha = 255
        draw_text_overlay(
            canvas, disp_text, beat.sub, beat.text_size,
            text_alpha, w_scale, disp_rich, beat.rich_text_sub,
            y_offset=text_y_offset,
            x_offset=text_x_offset,
        )

        # PNG watermark — centred near bottom
        if wm_img is not None:
            wx = (config.width - wm_img.width) // 2
            wy = config.height - wm_img.height - int(90 * w_scale)
            canvas.alpha_composite(wm_img, (wx, max(0, wy)))

        yield canvas


def render_video_frames(
    config: RenderConfig,
    frame_start: int = 0,
    frame_end: int | None = None,
) -> list[Image.Image]:
    """Backward-compatible helper returning a full list of frames."""
    return list(iter_video_frames(config, frame_start=frame_start, frame_end=frame_end))
