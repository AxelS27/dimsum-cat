"""
vfx.py — Dynamic Kawaii Particle & Visual Effects Engine for DIMsum Cat.

Provides procedural, high-performance visual effects:
- floating_hearts: Cute pastel hearts floating upward with gentle horizontal sway
- sparkles / stars: Twinkling 4-point diamond anime stars
- sweat_drops: Manga/anime comic sweat drop sliding down near head
- anger_vein: Classic anime pulsing red anger cross mark 💢
- question_marks: Floating cute question bubbles
- music_notes: Bouncing musical notes drifting upward
"""
from __future__ import annotations

import math
from typing import Sequence
from PIL import Image, ImageDraw, ImageFilter


def _draw_heart(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    size: float,
    fill: tuple[int, int, int, int],
    rot_rad: float = 0.0,
) -> None:
    """Draw a cute kawaii heart centered at (cx, cy) with optional tilt angle."""
    if abs(rot_rad) < 0.02:
        r = size * 0.52
        c_y = cy - r * 0.35
        # Two top circular lobes
        draw.ellipse([cx - r, c_y - r * 0.6, cx, c_y + r * 0.6], fill=fill)
        draw.ellipse([cx, c_y - r * 0.6, cx + r, c_y + r * 0.6], fill=fill)
        # Bottom triangular wedge
        poly = [
            (cx - r * 0.98, c_y),
            (cx + r * 0.98, c_y),
            (cx, cy + r * 1.15),
        ]
        draw.polygon(poly, fill=fill)
    else:
        # Smooth chubby parametric heart with rotation
        scale = size / 32.0
        cos_r = math.cos(rot_rad)
        sin_r = math.sin(rot_rad)
        points = []
        for i in range(28):
            t = i * (2.0 * math.pi / 28)
            dx = 16.0 * (math.sin(t) ** 3) * scale
            dy = -(13.0 * math.cos(t) - 5.0 * math.cos(2.0 * t) - 2.0 * math.cos(3.0 * t) - math.cos(4.0 * t)) * scale
            rx = cx + dx * cos_r - dy * sin_r
            ry = cy + dx * sin_r + dy * cos_r
            points.append((rx, ry))
        draw.polygon(points, fill=fill)


def _draw_star_sparkle(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    size: float,
    fill: tuple[int, int, int, int],
    rot_rad: float = 0.0,
) -> None:
    """Draw a 4-point diamond star sparkle with concave curved feel."""
    outer = size
    inner = size * 0.22
    points = []
    for i in range(8):
        ang = rot_rad + i * (math.pi / 4.0)
        dist = outer if (i % 2 == 0) else inner
        px = cx + math.cos(ang) * dist
        py = cy + math.sin(ang) * dist
        points.append((px, py))
    draw.polygon(points, fill=fill)


def _draw_sweat_drop(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    size: float,
    fill: tuple[int, int, int, int] = (116, 185, 255, 230),
) -> None:
    """Draw an anime blue sweat drop sliding down."""
    r = size * 0.45
    # Main circular bottom
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
    # Pointed upper tip (tilted slightly)
    tip_x = cx - r * 0.4
    tip_y = cy - r * 1.7
    poly = [
        (cx - r * 0.85, cy - r * 0.2),
        (cx + r * 0.85, cy - r * 0.2),
        (tip_x, tip_y),
    ]
    draw.polygon(poly, fill=fill)
    # Gloss highlight
    hl_fill = (255, 255, 255, min(255, int(fill[3] * 0.9)))
    hl_r = r * 0.28
    draw.ellipse([cx + r * 0.15, cy - r * 0.45, cx + r * 0.15 + hl_r, cy - r * 0.45 + hl_r], fill=hl_fill)


def _draw_anger_vein(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    size: float,
    fill: tuple[int, int, int, int] = (235, 60, 60, 240),
) -> None:
    """Draw a solid, seamless anime red anger mark (💢) with curved bracket lines."""
    thick = max(4, int(size * 0.22))
    arm = size * 0.48
    for dx, dy in [(1, -1), (-1, -1), (-1, 1), (1, 1)]:
        pts = []
        for i in range(12):
            ang = (i / 11.0) * (math.pi / 2.0)
            bx = cx + dx * arm * (1.0 - math.cos(ang))
            by = cy + dy * arm * (1.0 - math.sin(ang))
            pts.append((bx, by))
        for p_idx in range(len(pts) - 1):
            draw.line([pts[p_idx], pts[p_idx + 1]], fill=fill, width=thick)
        draw.ellipse([pts[0][0] - thick / 2, pts[0][1] - thick / 2, pts[0][0] + thick / 2, pts[0][1] + thick / 2], fill=fill)
        draw.ellipse([pts[-1][0] - thick / 2, pts[-1][1] - thick / 2, pts[-1][0] + thick / 2, pts[-1][1] + thick / 2], fill=fill)


def _draw_single_music_note(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    size: float,
    fill: tuple[int, int, int, int] = (255, 107, 129, 230),
) -> None:
    """Draw a cute, completely solid musical eighth note ♪ with seamless stem and flag."""
    head_rx = size * 0.40
    head_ry = size * 0.28
    thick = max(3, int(size * 0.16))
    stem_h = size * 1.25

    stem_x = cx + head_rx * 0.70
    stem_bottom = cy + head_ry * 0.2
    stem_top = cy - stem_h

    # 1. Tilted oval note head
    points = []
    tilt = -0.35  # ~ -20 degrees
    for i in range(24):
        ang = i * (2 * math.pi / 24)
        px = head_rx * math.cos(ang)
        py = head_ry * math.sin(ang)
        rx = px * math.cos(tilt) - py * math.sin(tilt) + cx
        ry = px * math.sin(tilt) + py * math.cos(tilt) + cy
        points.append((rx, ry))
    draw.polygon(points, fill=fill)

    # 2. Vertical stem
    draw.line([(stem_x, stem_bottom), (stem_x, stem_top)], fill=fill, width=thick)

    # 3. Solid, cute curved flag seamlessly attached to stem (zero gaps)
    flag_w = size * 0.55
    flag_h = size * 0.70
    poly = [
        (stem_x, stem_top),
        (stem_x + flag_w * 0.6, stem_top + flag_h * 0.1),
        (stem_x + flag_w, stem_top + flag_h * 0.45),
        (stem_x + flag_w * 0.75, stem_top + flag_h * 0.95),
        (stem_x + flag_w * 0.55, stem_top + flag_h * 0.70),
        (stem_x + thick, stem_top + flag_h * 0.45),
        (stem_x, stem_top + flag_h * 0.40),
    ]
    draw.polygon(poly, fill=fill)


def _draw_beamed_double_note(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    size: float,
    fill: tuple[int, int, int, int] = (72, 219, 251, 230),
) -> None:
    """Draw a cute pair of beamed double-eighth notes ♫ with solid bar and heads."""
    head_rx = size * 0.32
    head_ry = size * 0.22
    thick = max(3, int(size * 0.14))
    stem_h = size * 1.15
    span = size * 0.85

    x1 = cx - span * 0.5
    x2 = cx + span * 0.5
    y1 = cy
    y2 = cy - size * 0.20

    stem1_x = x1 + head_rx * 0.70
    stem2_x = x2 + head_rx * 0.70
    top1_y = y1 - stem_h
    top2_y = y2 - stem_h

    tilt = -0.35
    for hx, hy in [(x1, y1), (x2, y2)]:
        points = []
        for i in range(20):
            ang = i * (2 * math.pi / 20)
            px = head_rx * math.cos(ang)
            py = head_ry * math.sin(ang)
            rx = px * math.cos(tilt) - py * math.sin(tilt) + hx
            ry = px * math.sin(tilt) + py * math.cos(tilt) + hy
            points.append((rx, ry))
        draw.polygon(points, fill=fill)

    draw.line([(stem1_x, y1 + head_ry * 0.2), (stem1_x, top1_y)], fill=fill, width=thick)
    draw.line([(stem2_x, y2 + head_ry * 0.2), (stem2_x, top2_y)], fill=fill, width=thick)

    beam_thick = max(4, int(size * 0.22))
    draw.polygon([
        (stem1_x, top1_y),
        (stem2_x, top2_y),
        (stem2_x, top2_y + beam_thick),
        (stem1_x, top1_y + beam_thick),
    ], fill=fill)


def _draw_music_note(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    size: float,
    fill: tuple[int, int, int, int] = (255, 107, 129, 230),
    is_double: bool = False,
) -> None:
    """Draw a cute kawaii musical note (single ♪ or paired ♫)."""
    if is_double:
        _draw_beamed_double_note(draw, cx, cy, size, fill)
    else:
        _draw_single_music_note(draw, cx, cy, size, fill)


def _draw_question_mark(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    size: float,
    fill: tuple[int, int, int, int] = (255, 255, 255, 255),
    stroke_fill: tuple[int, int, int, int] = (30, 39, 46, 255),
    stroke_w: int = 4,
) -> None:
    """Draw a cute, completely solid rounded cartoon '?' mark with high contrast outline and drop shadow."""
    font_size = max(24, int(size * 1.55))
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("assets/fonts/Jua-Regular.ttf", font_size)
    except Exception:
        font = None

    if font:
        bbox = draw.textbbox((0, 0), "?", font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = cx - tw / 2.0 - bbox[0]
        y = cy - th / 2.0 - bbox[1]
        # Soft dark drop shadow for maximum comic punch
        shadow_a = int(stroke_fill[3] * 0.40) if len(stroke_fill) > 3 else 100
        draw.text((x + 2, y + 2), "?", font=font, fill=(0, 0, 0, shadow_a), stroke_width=stroke_w + 1, stroke_fill=(0, 0, 0, shadow_a))
        # Main text with crisp outline
        draw.text(
            (x, y),
            "?",
            font=font,
            fill=fill,
            stroke_width=stroke_w,
            stroke_fill=stroke_fill,
        )
    else:
        r = size * 0.4
        thick = max(4, int(size * 0.22))
        draw.arc([cx - r, cy - size * 0.8, cx + r, cy - size * 0.1], start=180, end=360, fill=fill, width=thick)
        draw.line([(cx + r * 0.2, cy - size * 0.1), (cx, cy + size * 0.2)], fill=fill, width=thick)
        dot_r = thick * 0.8
        draw.ellipse([cx - dot_r, cy + size * 0.45, cx + dot_r, cy + size * 0.45 + dot_r * 2], fill=fill)


def _parse_vfx_color(val: object, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    """Parse color from hex string (#RRGGBB), RGB tuple, or color name."""
    if isinstance(val, (tuple, list)) and len(val) >= 3:
        return (int(val[0]), int(val[1]), int(val[2]))
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("#") and len(s) in (4, 7):
            try:
                raw = s[1:]
                if len(raw) == 3:
                    raw = "".join(c * 2 for c in raw)
                return tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                return fallback
        COLOR_NAMES = {
            "white": (255, 255, 255),
            "black": (20, 20, 20),
            "charcoal": (30, 39, 46),
            "yellow": (255, 221, 89),
            "gold": (254, 202, 87),
            "cyan": (72, 219, 251),
            "blue": (41, 128, 185),
            "red": (235, 59, 90),
            "coral": (255, 107, 129),
            "pink": (255, 159, 243),
            "green": (29, 209, 161),
            "orange": (243, 156, 18),
            "purple": (155, 89, 182),
        }
        return COLOR_NAMES.get(s.lower(), fallback)
    return fallback


def _normalize_anchor_data(
    raw_anchors: Sequence[tuple[float, float] | dict],
    canvas_size: tuple[int, int],
    w_scale: float = 1.0,
) -> list[dict]:
    width, height = canvas_size
    normalized: list[dict] = []
    for idx, item in enumerate(raw_anchors):
        if isinstance(item, dict):
            pos = item.get("pos", (width * 0.5, height * 0.6))
            head_pos = item.get("head_pos", (pos[0], pos[1] - 110.0 * w_scale))
            flip_x = bool(item.get("flip_x", False))
            char_name = str(item.get("character", "")).lower().strip()
            actor_id = str(item.get("id", "")).lower().strip() or char_name
            normalized.append({
                "index": item.get("index", idx),
                "id": actor_id,
                "character": char_name,
                "pos": pos,
                "head_pos": head_pos,
                "flip_x": flip_x,
            })
        elif isinstance(item, (tuple, list)) and len(item) >= 2:
            pos = (float(item[0]), float(item[1]))
            head_pos = (pos[0], pos[1] - 110.0 * w_scale)
            normalized.append({
                "index": idx,
                "character": "",
                "pos": pos,
                "head_pos": head_pos,
                "flip_x": False,
            })
    return normalized


def _parse_vfx_radius(
    spec: dict,
    canvas_size: tuple[int, int],
    w_scale: float = 1.0,
    default: tuple[float, float] = (160.0, 100.0),
) -> tuple[float, float]:
    """Parse radius or spread parameter from spec, supporting scalar or [rx, ry]."""
    width, height = canvas_size
    rad_raw = spec.get("radius") or spec.get("spread")
    if rad_raw is None:
        return (default[0] * w_scale, default[1] * w_scale)
    if isinstance(rad_raw, (list, tuple)) and len(rad_raw) >= 2:
        rx, ry = float(rad_raw[0]), float(rad_raw[1])
        if 0.0 < rx <= 1.0:
            rx *= width
        else:
            rx *= w_scale
        if 0.0 < ry <= 1.0:
            ry *= height
        else:
            ry *= w_scale
        return (rx, ry)
    elif isinstance(rad_raw, (int, float)):
        r = float(rad_raw)
        if 0.0 < r <= 1.0:
            rx = r * width
            ry = r * height * 0.6
        else:
            rx = r * w_scale
            ry = r * w_scale * 0.65
        return (rx, ry)
    return (default[0] * w_scale, default[1] * w_scale)


def _resolve_spec_targets(
    spec: dict,
    actors: list[dict],
    canvas_size: tuple[int, int],
    w_scale: float = 1.0,
    is_ambient: bool = False,
) -> list[dict]:
    width, height = canvas_size

    # 1. Explicit free position `pos`
    if "pos" in spec and spec["pos"] is not None:
        pos_raw = spec["pos"]
        if isinstance(pos_raw, (list, tuple)) and len(pos_raw) >= 2:
            px, py = float(pos_raw[0]), float(pos_raw[1])
            if 0.0 <= px <= 1.0 and 0.0 <= py <= 1.0:
                px *= width
                py *= height
        elif isinstance(pos_raw, str):
            from src.utils import resolve_pos
            px, py = resolve_pos(pos_raw, width, height)
        else:
            px, py = width * 0.5, height * 0.6

        if "offset" in spec and isinstance(spec["offset"], (list, tuple)) and len(spec["offset"]) >= 2:
            px += float(spec["offset"][0]) * w_scale
            py += float(spec["offset"][1]) * w_scale

        return [{
            "index": -1,
            "character": "custom_pos",
            "pos": (px, py),
            "head_pos": (px, py),
            "flip_x": bool(spec.get("flip_x", False)),
        }]

    # 2. Explicit target actor (e.g. "capybara", "duckling", 0, 1, or "all")
    if "target" in spec and spec["target"] is not None:
        raw_target = str(spec["target"]).lower().strip()
        if raw_target in ("all", "*"):
            matched = list(actors)
        else:
            matched = []
            for act in actors:
                if (
                    raw_target == str(act["index"])
                    or (act.get("id") and raw_target == act["id"])
                    or (act["character"] and raw_target in act["character"])
                ):
                    matched.append(act)
        if matched:
            results = []
            for act in matched:
                act_copy = dict(act)
                if "offset" in spec and isinstance(spec["offset"], (list, tuple)) and len(spec["offset"]) >= 2:
                    ox = float(spec["offset"][0]) * w_scale
                    oy = float(spec["offset"][1]) * w_scale
                    act_copy["pos"] = (act_copy["pos"][0] + ox, act_copy["pos"][1] + oy)
                    act_copy["head_pos"] = (act_copy["head_pos"][0] + ox, act_copy["head_pos"][1] + oy)
                results.append(act_copy)
            return results

    # 3. No explicit pos or target:
    if is_ambient:
        if actors:
            return actors
        return [{
            "index": 0,
            "character": "stage",
            "pos": (width * 0.5, height * 0.6),
            "head_pos": (width * 0.5, height * 0.45),
            "flip_x": False,
        }]

    # For character-specific effects, target the primary actor (never duplicate across all!)
    if actors:
        primary = dict(actors[0])
        if "offset" in spec and isinstance(spec["offset"], (list, tuple)) and len(spec["offset"]) >= 2:
            ox = float(spec["offset"][0]) * w_scale
            oy = float(spec["offset"][1]) * w_scale
            primary["pos"] = (primary["pos"][0] + ox, primary["pos"][1] + oy)
            primary["head_pos"] = (primary["head_pos"][0] + ox, primary["head_pos"][1] + oy)
        return [primary]

    return [{
        "index": 0,
        "character": "default",
        "pos": (width * 0.5, height * 0.6),
        "head_pos": (width * 0.5, height * 0.45),
        "flip_x": False,
    }]


def render_vfx_layer(
    canvas_size: tuple[int, int],
    vfx_specs: list[dict | str],
    t: float,
    age: float,
    anchor_positions: Sequence[tuple[float, float] | dict],
    w_scale: float = 1.0,
    beat_dur: float = 3.0,
) -> Image.Image:
    """Render procedural particle VFX onto a transparent RGBA image."""
    width, height = canvas_size
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    if not vfx_specs:
        return layer

    actors = _normalize_anchor_data(anchor_positions, canvas_size, w_scale)

    for raw_spec in vfx_specs:
        if isinstance(raw_spec, str):
            spec = {"type": raw_spec.lower().strip()}
        elif isinstance(raw_spec, dict):
            spec = raw_spec
        else:
            continue

        effect_type = str(spec.get("type", "")).lower().strip()
        intensity = float(spec.get("intensity", 1.0))

        # ------------------------------------------------------------------
        # ------------------------------------------------------------------
        # Floating Hearts (Curving & fanning out sideways + natural sway)
        # ------------------------------------------------------------------
        if effect_type in ("hearts", "floating_hearts", "heart"):
            targets = _resolve_spec_targets(spec, actors, canvas_size, w_scale, is_ambient=True)
            rad_x, rad_y = _parse_vfx_radius(spec, canvas_size, w_scale, default=(200.0, 140.0))
            if spec.get("color"):
                heart_colors = [_parse_vfx_color(spec.get("color"), (255, 107, 129))]
            else:
                heart_colors = [
                    (255, 107, 129),  # coral pink
                    (255, 159, 243),  # lilac pink
                    (254, 202, 87),   # warm gold
                    (238, 82, 83),    # deep rose
                    (243, 104, 224),  # bright magenta
                ]
            num_hearts = int(spec.get("count", 8) * intensity)
            for i in range(num_hearts):
                seed = i * 2.71 + 0.9
                # Independent lifecycle per heart (2.2s to 3.8s)
                lifetime = 2.2 + 1.4 * ((seed * 3.7) % 1.0)
                # Phase offset so hearts are naturally staggered (not all in sync)
                phase = (seed * 1.618) % 1.0
                t_cycle = (age + phase * lifetime) % lifetime
                progress = t_cycle / lifetime  # 0.0 to 1.0

                # Lifecycle alpha: smooth fade-in, peak, fade-out
                cycle_alpha = math.sin(progress * math.pi)

                # Staggered end-of-beat fade out
                if beat_dur > 1.5:
                    fade_end = beat_dur - 0.2 - ((seed * 4.9) % 1.0) * 1.0
                    death_fade = max(0.0, min(1.0, (fade_end - age) / 0.4)) if age > (fade_end - 0.4) else 1.0
                else:
                    death_fade = 1.0

                alpha = int(245 * (cycle_alpha ** 0.75) * death_fade)
                if alpha <= 6:
                    continue

                tgt = targets[i % len(targets)]
                # Spawn location: scattered around character's torso/head
                spawn_offset_x = (((seed * 5.3) % 1.0 - 0.5) * 2.0) * (rad_x * 0.40)
                spawn_x = tgt["pos"][0] + spawn_offset_x
                spawn_y = tgt["head_pos"][1] + int(20.0 * w_scale)

                # Upward float distance (drifts up to ~45% of screen height)
                travel_y = progress * (height * 0.45)

                # Horizontal drift: Fans out to the left or right as it rises!
                # Even/odd seeds naturally distribute left and right
                side_bias = -1.0 if (i % 2 == 0) else 1.0
                drift_strength = 0.5 + 0.5 * ((seed * 6.1) % 1.0)
                # As progress increases, the heart curves further left or right
                drift_x = side_bias * (progress ** 1.2) * (rad_x * 1.35 * drift_strength)

                # Gentle organic sway on top of the outward curve
                sway = math.sin(progress * 4.0 * math.pi + seed * 2.5) * (26.0 * w_scale)

                hx = spawn_x + drift_x + sway
                hy = spawn_y - travel_y

                # Tilt matches direction of drift and sway
                tilt_rad = (side_bias * 0.18 * progress) + (math.cos(progress * 4.0 * math.pi + seed * 2.5) * 0.15)

                base_sz = (24.0 + 12.0 * (i % 4)) * w_scale
                size = base_sz * (0.8 + 0.3 * cycle_alpha)

                col = heart_colors[i % len(heart_colors)]
                _draw_heart(draw, hx, hy, size, (*col, alpha), rot_rad=tilt_rad)

        # ------------------------------------------------------------------
        # Sparkles / Twinkling Stars (Asynchronous anime shimmer)
        # ------------------------------------------------------------------
        elif effect_type in ("sparkles", "sparkle", "stars", "star"):
            is_ambient = ("target" not in spec and "pos" not in spec)
            targets = _resolve_spec_targets(spec, actors, canvas_size, w_scale, is_ambient=is_ambient)
            rad_x, rad_y = _parse_vfx_radius(spec, canvas_size, w_scale, default=(170.0, 130.0))
            if spec.get("color"):
                star_colors = [_parse_vfx_color(spec.get("color"), (255, 234, 167))]
            else:
                star_colors = [
                    (255, 234, 167),  # golden sunshine
                    (255, 255, 255),  # pure white
                    (129, 236, 236),  # soft cyan
                    (253, 203, 110),  # amber glow
                    (255, 179, 186),  # pastel pink sparkle
                ]
            num_stars = int(spec.get("count", 10) * intensity)
            for tgt in targets:
                for i in range(num_stars):
                    seed = i * 3.41 + 0.77
                    # Independent twinkle lifetime (0.75s to 1.45s) per star
                    star_lifetime = 0.75 + 0.70 * ((seed * 4.3) % 1.0)
                    phase = (seed * 1.83) % 1.0
                    t_cycle = (age + phase * star_lifetime) % star_lifetime
                    progress = t_cycle / star_lifetime

                    # Star flash pulse: quick burst in, twinkle, fade out
                    pulse = math.sin(progress * math.pi)
                    alpha = int(255 * (pulse ** 1.35))
                    if alpha <= 8:
                        continue

                    # Scattered positions around character (head, body, hands)
                    offset_x = (((seed * 7.9) % 1.0 - 0.5) * 2.0) * rad_x
                    offset_y = (((seed * 5.1) % 1.0 - 0.5) * 2.0) * rad_y

                    # Gentle upward drift during each twinkle
                    float_y = progress * (18.0 * w_scale)

                    sx = tgt["head_pos"][0] + offset_x
                    sy = (tgt["head_pos"][1] + int(20.0 * w_scale)) + offset_y - float_y

                    base_sz = float(spec.get("size", 20.0)) * w_scale
                    # Star sizes vary: some subtle glints, some bold sparkles
                    size_mod = 0.6 + 0.8 * ((i % 5) / 4.0)
                    size = (base_sz * size_mod) * (0.4 + 0.8 * pulse)

                    rot_speed = 1.5 + (seed % 1.0) * 2.5
                    rot = seed * 2.0 + age * rot_speed * ((i % 2) * 2 - 1)
                    col = star_colors[i % len(star_colors)]
                    _draw_star_sparkle(draw, sx, sy, size, (*col, alpha), rot_rad=rot)

        # ------------------------------------------------------------------
        # Knockout Dizzy Stars (Circling around head)
        # ------------------------------------------------------------------
        elif effect_type in ("knockout", "dizzy"):
            targets = _resolve_spec_targets(spec, actors, canvas_size, w_scale, is_ambient=False)
            rad_x, rad_y = _parse_vfx_radius(spec, canvas_size, w_scale, default=(90.0, 38.0))
            star_colors = [
                (255, 234, 167),
                (254, 202, 87),
                (255, 255, 255),
            ]
            num_stars = int(spec.get("count", 4) * intensity)
            for tgt in targets:
                for i in range(num_stars):
                    angle_offset = (i / num_stars) * 2.0 * math.pi
                    orbit_angle = age * 3.5 + angle_offset
                    sx = tgt["head_pos"][0] + math.cos(orbit_angle) * rad_x
                    sy = (tgt["head_pos"][1] - 15.0 * w_scale) + math.sin(orbit_angle) * rad_y
                    pulse = 0.7 + 0.3 * math.sin(age * 7.0 + i)
                    alpha = int(245 * pulse)
                    size = (18.0 * w_scale) * pulse
                    col = star_colors[i % len(star_colors)]
                    _draw_star_sparkle(draw, sx, sy, size, (*col, alpha), rot_rad=age * 4.0)

        # ------------------------------------------------------------------
        # Anime Sweat Drops
        # ------------------------------------------------------------------
        elif effect_type in ("sweat", "sweat_drops", "nervous"):
            targets = _resolve_spec_targets(spec, actors, canvas_size, w_scale, is_ambient=False)
            fill_rgb = _parse_vfx_color(spec.get("color"), (116, 185, 255))
            base_sz = float(spec.get("size", 28.0)) * w_scale * intensity
            for tgt in targets:
                sign_x = -1.0 if tgt["flip_x"] else 1.0
                head_x = tgt["head_pos"][0] + (sign_x * 25.0 * w_scale)
                head_y = tgt["head_pos"][1] + (8.0 * w_scale)
                slide_cycle = (age * 1.6) % 1.0
                drop_y = head_y + (slide_cycle ** 1.3) * (45.0 * w_scale)
                alpha = int(235 * (1.0 - slide_cycle * 0.55))
                size = (base_sz + 8.0 * (1.0 - slide_cycle))
                _draw_sweat_drop(draw, head_x, drop_y, size, (*fill_rgb, alpha))

        # ------------------------------------------------------------------
        # Anime Anger Vein Mark 💢
        # ------------------------------------------------------------------
        elif effect_type in ("anger", "anger_vein", "angry"):
            targets = _resolve_spec_targets(spec, actors, canvas_size, w_scale, is_ambient=False)
            fill_rgb = _parse_vfx_color(spec.get("color"), (235, 59, 90))
            base_sz = float(spec.get("size", 38.0)) * w_scale * intensity
            for tgt in targets:
                sign_x = -1.0 if tgt["flip_x"] else 1.0
                head_x = tgt["head_pos"][0] + (sign_x * 25.0 * w_scale)
                head_y = tgt["head_pos"][1] - (5.0 * w_scale)
                pulse = 1.0 + 0.28 * abs(math.sin(age * 10.0))
                size = base_sz * pulse
                _draw_anger_vein(draw, head_x, head_y, size, (*fill_rgb, 245))

        # ------------------------------------------------------------------
        # Musical Notes 🎵 (Staggered lifecycles & smooth lifecycle fading)
        # ------------------------------------------------------------------
        elif effect_type in ("music_notes", "music", "musical"):
            is_ambient = ("target" not in spec and "pos" not in spec)
            targets = _resolve_spec_targets(spec, actors, canvas_size, w_scale, is_ambient=is_ambient)
            rad_x, rad_y = _parse_vfx_radius(spec, canvas_size, w_scale, default=(360.0, 220.0))
            
            custom_colors = spec.get("colors")
            if custom_colors and isinstance(custom_colors, list):
                note_colors = [_parse_vfx_color(c, (255, 107, 129)) for c in custom_colors]
            elif spec.get("color"):
                note_colors = [_parse_vfx_color(spec.get("color"), (255, 107, 129))]
            else:
                note_colors = [
                    (255, 107, 129),  # coral pink
                    (254, 202, 87),   # gold
                    (72, 219, 251),   # sky cyan
                    (29, 209, 161),   # mint green
                    (255, 159, 243),  # lavender
                ]

            num_notes = int(spec.get("count", 8) * intensity)
            for i in range(num_notes):
                seed = i * 2.71 + 0.5
                # Unique independent period/lifetime per note (2.2s to 3.8s)
                note_lifetime = 2.2 + 1.4 * ((seed * 3.3) % 1.0)
                # Phase offset so notes are naturally scattered across the sky from t=0 (never in sync!)
                phase = (seed * 1.73) % 1.0

                # Current position inside note's cycle
                t_cycle = (age + phase * note_lifetime) % note_lifetime
                progress = t_cycle / note_lifetime

                # Smooth lifecycle alpha: fade in at bottom, peak in middle, fade out at top
                cycle_alpha = math.sin(progress * math.pi)

                # Staggered disappearing near beat end:
                # Each note fades out individually at a different moment before beat ends
                if beat_dur > 1.5:
                    fade_end = beat_dur - 0.2 - ((seed * 4.9) % 1.0) * 1.3
                    death_fade = max(0.0, min(1.0, (fade_end - age) / 0.5)) if age > (fade_end - 0.5) else 1.0
                else:
                    death_fade = 1.0

                alpha = int(245 * (cycle_alpha ** 0.8) * death_fade)
                if alpha <= 6:
                    continue

                # Upward drift tied to note's individual progress
                drift_y = progress * (height * 0.50)
                tgt = targets[i % len(targets)]

                # Spread across radius_x
                norm_offset = ((seed * 7.7) % 1.0 - 0.5) * 2.0  # -1.0 to +1.0
                sway = math.sin(age * 3.8 + seed) * (35.0 * w_scale)
                nx = tgt["pos"][0] + (norm_offset * rad_x) + sway
                ny = tgt["head_pos"][1] - drift_y

                base_size = float(spec.get("size", 26.0)) * w_scale
                size = (base_size + 8.0 * (i % 3)) * (0.8 + 0.3 * cycle_alpha)
                col = note_colors[i % len(note_colors)]
                _draw_music_note(draw, nx, ny, size, (*col, alpha), is_double=(i % 3 == 1))

        # ------------------------------------------------------------------
        # Confused Question Marks ? (High contrast, large size & custom colors)
        # ------------------------------------------------------------------
        elif effect_type in ("question_marks", "question", "confused"):
            targets = _resolve_spec_targets(spec, actors, canvas_size, w_scale, is_ambient=False)
            num_marks = int(spec.get("count", 2) * intensity)

            # High contrast colors: default bright warm gold with bold dark charcoal outline
            fill_rgb = _parse_vfx_color(spec.get("color"), (255, 234, 167))
            stroke_rgb = _parse_vfx_color(spec.get("stroke_color") or spec.get("stroke"), (30, 39, 46))
            stroke_w = max(2, int(spec.get("stroke_width", 4) * w_scale))
            base_size = float(spec.get("size", 54.0)) * w_scale * intensity

            for tgt in targets:
                sign_x = -1.0 if tgt["flip_x"] else 1.0
                for i in range(num_marks):
                    seed = i * 2.4 + 0.8
                    pop = min(1.0, max(0.0, (age * 4.0 - i * 0.25)))
                    if pop <= 0:
                        continue
                    off_x = (sign_x * (20.0 + i * 32.0) * w_scale)
                    off_y = -(22.0 + i * 36.0) * w_scale + math.sin(age * 5.0 + seed) * (6.0 * w_scale)
                    qx = tgt["head_pos"][0] + off_x
                    qy = tgt["head_pos"][1] + off_y
                    size = (base_size + 8.0 * (i % 2)) * pop
                    alpha = int(250 * pop)
                    _draw_question_mark(
                        draw,
                        qx,
                        qy,
                        size,
                        fill=(*fill_rgb, alpha),
                        stroke_fill=(*stroke_rgb, alpha),
                        stroke_w=stroke_w,
                    )

    return layer
