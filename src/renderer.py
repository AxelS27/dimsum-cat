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
    strip_emoji,
)
from src.sprite import organic, make_sprite_schedule, load_frames
from src.motion import resolve_motion_name, compute_motion
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


def _measure_rich_line(
    draw: ImageDraw.ImageDraw,
    spans: list[RichTextSpan],
    font,
) -> tuple[int, int]:
    width = 0
    height = 0
    for span in spans:
        w, h = measure(draw, span.text, font)
        width += w
        height = max(height, h)
    return width, height


def _wrap_rich_spans(
    draw: ImageDraw.ImageDraw,
    spans: list[RichTextSpan],
    font,
    max_w: int,
) -> list[list[RichTextSpan]]:
    """Break spans into rows that each fit within max_w, splitting at word boundaries."""
    from src.models import RichTextSpan as RS
    rows: list[list[RS]] = []
    current_row: list[RS] = []
    current_w = 0

    for span in spans:
        words = span.text.split(" ")
        for wi, word in enumerate(words):
            piece = word if wi == len(words) - 1 else word + " "
            w, _ = measure(draw, piece, font)
            if current_w + w > max_w and current_row:
                rows.append(current_row)
                current_row = []
                current_w = 0
                piece = piece.lstrip()  # trim leading space on new row
                w, _ = measure(draw, piece, font)
            if piece:
                current_row.append(RS(text=piece, color=span.color))
                current_w += w

    if current_row:
        rows.append(current_row)
    return rows or [[]]


def _draw_rich_line(
    draw: ImageDraw.ImageDraw,
    spans: list[RichTextSpan],
    font,
    x: int,
    y: int,
    alpha: int,
) -> None:
    cursor = x
    shadow_a = int(80 * alpha / 255)
    # First pass: drop shadow with matching stroke
    for span in spans:
        draw.text((cursor + 4, y + 4), span.text, font=font, fill=(0, 0, 0, shadow_a), stroke_width=7, stroke_fill=(0, 0, 0, shadow_a))
        cursor += measure(draw, span.text, font)[0]
    # Second pass: main text with crisp white outline
    cursor = x
    for span in spans:
        color = _parse_hex_color(span.color, (42, 42, 42))
        draw.text((cursor, y), span.text, font=font, fill=(*color, alpha), stroke_width=7, stroke_fill=(255, 255, 255, alpha))
        cursor += measure(draw, span.text, font)[0]


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
) -> None:
    """Render text directly on canvas — no card/box, drop shadow only."""
    rich_text     = rich_text     or []
    rich_text_sub = rich_text_sub or []
    if not text and not sub and not rich_text and not rich_text_sub:
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
    y = zone_top + max(0, (zone_h - total_h) // 2) + y_offset

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    # Instead of the closure trick, just draw inline:
    if rich_rows:
        for row in rich_rows:
            w, h = _measure_rich_line(draw, row, main_font)
            x = (canvas.width - w) // 2
            _draw_rich_line(draw, row, main_font, x, y, alpha)
            y += h + gap_ln
    else:
        for line in main_lines:
            w, h = measure(draw, line, main_font)
            x = (canvas.width - w) // 2
            shadow_a = int(80 * alpha / 255)
            draw.text((x + 4, y + 4), line, font=main_font, fill=(0, 0, 0, shadow_a), stroke_width=7, stroke_fill=(0, 0, 0, shadow_a))
            draw.text((x, y), line, font=main_font, fill=(42, 42, 42, alpha), stroke_width=7, stroke_fill=(255, 255, 255, alpha))
            y += h + gap_ln

    if rich_sub_rows:
        y += gap_blk
        for row in rich_sub_rows:
            w, h = _measure_rich_line(draw, row, sub_font)
            x = (canvas.width - w) // 2
            _draw_rich_line(draw, row, sub_font, x, y, alpha)
            y += h + gap_ln
    elif sub_lines:
        y += gap_blk
        for line in sub_lines:
            w, h = measure(draw, line, sub_font)
            x = (canvas.width - w) // 2
            shadow_a = int(70 * alpha / 255)
            draw.text((x + 3, y + 3), line, font=sub_font, fill=(0, 0, 0, shadow_a), stroke_width=5, stroke_fill=(0, 0, 0, shadow_a))
            draw.text((x, y), line, font=sub_font, fill=(30, 30, 30, alpha), stroke_width=5, stroke_fill=(255, 255, 255, alpha))
            y += h + gap_ln

    canvas.alpha_composite(layer)


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

    for idx in range(frame_start, frame_end):
        t = idx / config.fps
        beat_idx, beat = beat_at(t)
        age = t - beat.time

        # ----------------------------------------------------------------
        # Multi-Actor Staging & Motion Pre-Evaluation
        # ----------------------------------------------------------------
        actors = beat.get_actors(config.default_character, config.default_animation)
        sorted_actors = sorted(actors, key=lambda a: a.z_index)

        # Collect actor positions and evaluate motions for camera coupling
        actor_positions: dict[str, tuple[float, float]] = {}
        actor_motions: dict[str, tuple[float, float]] = {}
        for a in sorted_actors:
            ch = a.character or config.default_character
            an = a.animation or config.default_animation
            p = resolve_pos(a.pos)
            actor_positions[ch] = p
            mp = a.motion or resolve_motion_name(an, ch)
            ms = compute_motion(mp, t=t, age=age, w_scale=w_scale, speed=a.motion_speed, intensity=a.motion_intensity)
            actor_motions[ch] = (ms.drift_x, ms.bob_px)

        # ----------------------------------------------------------------
        # Beat Duration & Virtual Cinematic Director Camera
        # ----------------------------------------------------------------
        if beat_idx + 1 < len(beats):
            beat_dur = max(0.1, beats[beat_idx + 1].time - beat.time)
        else:
            beat_dur = max(0.1, config.duration - beat.time)

        cam_cfg = beat.get_camera_config()
        cam = compute_camera(
            cam_cfg,
            age=age,
            beat_dur=beat_dur,
            intensity=cam_cfg.intensity,
            actor_positions=actor_positions,
            actor_motions=actor_motions,
        )

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

        # Scene Transitions (Flash bloom, crossfade, circle wipe, dip_black)
        trans_type = getattr(beat, "transition", "") or ("flash" if beat_idx > 0 else "none")
        trans_dur = getattr(beat, "transition_dur", 0.22)
        if trans_type != "none" and age < trans_dur:
            canvas = apply_transition(canvas, None, trans_type, age, duration=trans_dur)

        # Accessories — composited BEFORE characters
        from pathlib import Path as _APath
        for acc in beat.accessories:
            ap = _APath(acc.image)
            if not ap.is_absolute():
                candidate = config.story_dir / ap if config.story_dir else None
                if candidate and candidate.exists():
                    ap = candidate
                else:
                    ap = ROOT / ap
            if not ap.exists():
                continue
            if ap.is_dir():
                num_frames = sorted(ap.glob("frame_[0-9][0-9].png"))
                if num_frames:
                    acc_frames = [Image.open(p).convert("RGBA") for p in num_frames]
                else:
                    from src.models import FRAME_NAMES as _FN
                    acc_frames = [Image.open(ap / f).convert("RGBA") for f in _FN if (ap / f).exists()]
                if not acc_frames:
                    continue
                frame_i = idx // max(1, config.fps // 2) % len(acc_frames)
                acc_img = acc_frames[frame_i]
            else:
                acc_img = Image.open(ap).convert("RGBA")
            target_w = max(1, int(config.width * acc.scale))
            ratio = target_w / acc_img.width
            acc_img = acc_img.resize((target_w, max(1, int(acc_img.height * ratio))), Image.Resampling.LANCZOS)
            if acc.flip_x:
                acc_img = acc_img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if abs(acc.rotate) > 0.3:
                acc_img = acc_img.rotate(-acc.rotate, expand=True, resample=Image.Resampling.BICUBIC)
            acc_pos = POSITIONS.get(acc.pos) if acc.pos in POSITIONS else None
            if acc_pos is None:
                try:
                    parts = str(acc.pos).split(",")
                    acc_pos = (float(parts[0]), float(parts[1]))
                except Exception:
                    acc_pos = (0.5, 0.5)
            ax = int(config.width  * acc_pos[0] - acc_img.width  // 2)
            ay = int(config.height * acc_pos[1] - acc_img.height // 2)
            ax0 = max(0, -ax); ax1 = min(acc_img.width,  config.width  - ax)
            ay0 = max(0, -ay); ay1 = min(acc_img.height, config.height - ay)
            if ax1 > ax0 and ay1 > ay0:
                canvas.alpha_composite(acc_img.crop((ax0, ay0, ax1, ay1)), (max(0, ax), max(0, ay)))

        # ----------------------------------------------------------------
        # Multi-Actor Staging & Ground Shadows (Virtual Camera Projected)
        # ----------------------------------------------------------------
        actor_anchors: list[tuple[float, float]] = []

        for actor in sorted_actors:
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

            # Target position and scale in world space
            target_cx, target_cy = resolve_pos(actor.pos)
            target_scale = actor.scale

            if age < ENTRANCE_DUR:
                prog = age / ENTRANCE_DUR
                spring = ease_out_back(prog)
                char_scale = target_scale * (0.60 + 0.40 * spring)
                rise = (1.0 - ease_out_cubic(prog)) * 0.07
            else:
                char_scale = target_scale
                rise = 0.0

            # Motion behavior physics
            motion_preset = actor.motion or resolve_motion_name(act_anim, act_char)
            motion_state = compute_motion(
                motion_preset,
                t=t,
                age=age,
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
            rot_deg = motion_state.rot_deg + cam.roll_deg + actor.rotate
            sq_x = motion_state.sq_x
            sq_y = motion_state.sq_y

            # Sprite scaling
            target_cat_w = config.width * 0.62 * char_scale
            sf = target_cat_w / (orig_w * SPRITE_UPSCALE)
            new_w = max(1, int(sprite.width  * sf * sq_x))
            new_h = max(1, int(sprite.height * sf * sq_y))
            sprite = sprite.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Flip character horizontally
            if actor.flip_x:
                sprite = sprite.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

            # Rotate
            if abs(rot_deg) > 0.3:
                sprite = sprite.rotate(rot_deg, expand=True, resample=Image.Resampling.BICUBIC)

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
                sh_alpha = int(75 * jump_factor)
                if sh_w > 8 and sh_h > 2 and sh_alpha > 5:
                    sh_img = Image.new("RGBA", (config.width, config.height), (0, 0, 0, 0))
                    sh_draw = ImageDraw.Draw(sh_img)
                    sh_cx = int(config.width * screen_cx)
                    sh_draw.ellipse(
                        [sh_cx - sh_w // 2, ground_screen_y - sh_h // 2, sh_cx + sh_w // 2, ground_screen_y + sh_h // 2],
                        fill=(20, 25, 35, sh_alpha),
                    )
                    sh_img = sh_img.filter(ImageFilter.GaussianBlur(radius=int(6 * w_scale)))
                    canvas.alpha_composite(sh_img)

            # Composite character sprite
            src_x0 = max(0, -sx);  src_x1 = min(sprite.width,  config.width  - sx)
            src_y0 = max(0, -sy);  src_y1 = min(sprite.height, config.height - sy)
            if src_x1 > src_x0 and src_y1 > src_y0:
                canvas.alpha_composite(
                    sprite.crop((src_x0, src_y0, src_x1, src_y1)),
                    (max(0, sx), max(0, sy)),
                )

            actor_anchors.append((config.width * screen_cx, config.height * screen_cy))

        # ----------------------------------------------------------------
        # Kawaii VFX Particle Overlay
        # ----------------------------------------------------------------
        if beat.vfx:
            vfx_img = render_vfx_layer(
                (config.width, config.height),
                beat.vfx,
                t=t,
                age=age,
                anchor_positions=actor_anchors,
                w_scale=w_scale,
            )
            canvas.alpha_composite(vfx_img)

        # ----------------------------------------------------------------
        # Speech Bubble / Text Overlay
        # ----------------------------------------------------------------
        TEXT_ENTRANCE = 0.28
        if age < TEXT_ENTRANCE:
            prog = age / TEXT_ENTRANCE
            spring = ease_out_back(prog)
            text_y_offset = int((1.0 - spring) * -22.0 * w_scale)
            text_alpha = min(255, int(255 * (prog ** 0.8))) if beat_idx > 0 else 255
        else:
            text_y_offset = 0
            text_alpha = 255
        draw_text_overlay(
            canvas, beat.text, beat.sub, beat.text_size,
            text_alpha, w_scale, beat.rich_text, beat.rich_text_sub,
            y_offset=text_y_offset,
        )

        # PNG watermark — centred near bottom
        if wm_img is not None:
            wx = (config.width - wm_img.width) // 2
            wy = config.height - wm_img.height - int(90 * w_scale)
            canvas.alpha_composite(wm_img, (wx, max(0, wy)))

        yield canvas.convert("RGB")


def render_video_frames(
    config: RenderConfig,
    frame_start: int = 0,
    frame_end: int | None = None,
) -> list[Image.Image]:
    """Backward-compatible helper returning a full list of frames."""
    return list(iter_video_frames(config, frame_start=frame_start, frame_end=frame_end))
