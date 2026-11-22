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
) -> None:
    """Draw a cute kawaii heart centered at (cx, cy)."""
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
    """Draw the classic anime red anger mark (💢) with curved bracket lines."""
    arm = size * 0.55
    thick = max(3, int(size * 0.22))
    # 4 curved bars radiating from center
    # Top-right bracket
    draw.arc([cx, cy - arm, cx + arm, cy], start=180, end=270, fill=fill, width=thick)
    # Top-left bracket
    draw.arc([cx - arm, cy - arm, cx, cy], start=270, end=360, fill=fill, width=thick)
    # Bottom-left bracket
    draw.arc([cx - arm, cy, cx, cy + arm], start=0, end=90, fill=fill, width=thick)
    # Bottom-right bracket
    draw.arc([cx, cy, cx + arm, cy + arm], start=90, end=180, fill=fill, width=thick)


def _draw_music_note(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    size: float,
    fill: tuple[int, int, int, int] = (255, 107, 129, 230),
) -> None:
    """Draw a cute musical eighth note ♪."""
    head_rx = size * 0.35
    head_ry = size * 0.25
    stem_h = size * 1.2
    thick = max(3, int(size * 0.18))
    # Tilted oval note head
    draw.ellipse([cx - head_rx, cy - head_ry, cx + head_rx, cy + head_ry], fill=fill)
    # Vertical stem
    stem_x = cx + head_rx * 0.7
    draw.line([(stem_x, cy), (stem_x, cy - stem_h)], fill=fill, width=thick)
    # Flag hook
    draw.arc([stem_x, cy - stem_h, stem_x + size * 0.6, cy - stem_h * 0.4], start=270, end=360, fill=fill, width=thick)


def _draw_question_mark(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    size: float,
    fill: tuple[int, int, int, int] = (253, 203, 110, 240),
) -> None:
    """Draw a cute rounded '?' mark."""
    r = size * 0.4
    thick = max(4, int(size * 0.22))
    draw.arc([cx - r, cy - size * 0.8, cx + r, cy - size * 0.1], start=180, end=360, fill=fill, width=thick)
    draw.line([(cx + r * 0.2, cy - size * 0.1), (cx, cy + size * 0.2)], fill=fill, width=thick)
    dot_r = thick * 0.8
    draw.ellipse([cx - dot_r, cy + size * 0.45, cx + dot_r, cy + size * 0.45 + dot_r * 2], fill=fill)


def render_vfx_layer(
    canvas_size: tuple[int, int],
    vfx_specs: list[dict | str],
    t: float,
    age: float,
    anchor_positions: list[tuple[float, float]],
    w_scale: float = 1.0,
) -> Image.Image:
    """Render procedural particle VFX onto a transparent RGBA image."""
    width, height = canvas_size
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    if not vfx_specs:
        return layer

    # If anchor positions are empty, default to screen center-low
    if not anchor_positions:
        anchor_positions = [(width * 0.5, height * 0.6)]

    for raw_spec in vfx_specs:
        if isinstance(raw_spec, str):
            effect_type = raw_spec.lower().strip()
            intensity = 1.0
        else:
            effect_type = str(raw_spec.get("type", "")).lower().strip()
            intensity = float(raw_spec.get("intensity", 1.0))

        # ------------------------------------------------------------------
        # Floating Hearts
        # ------------------------------------------------------------------
        if effect_type in ("hearts", "floating_hearts", "heart"):
            heart_colors = [
                (255, 107, 129),  # coral pink
                (255, 159, 243),  # lilac pink
                (254, 202, 87),   # warm gold
                (238, 82, 83),    # deep rose
                (243, 104, 224),  # bright magenta
            ]
            num_hearts = int(6 * intensity)
            for i in range(num_hearts):
                # Pseudo-random deterministic offsets seeded by index
                seed = i * 2.39 + 1.1
                spawn_offset_x = (math.sin(seed * 7.1) * 0.35) * width
                # Upward drift velocity
                speed = 120.0 * w_scale * (0.8 + 0.4 * (i % 3))
                travel = (age * speed + seed * 180.0) % (height * 0.60)

                # Anchor to first character or canvas center
                ax, ay = anchor_positions[i % len(anchor_positions)]
                hx = ax + spawn_offset_x + math.sin(age * 3.5 + seed) * (28.0 * w_scale)
                hy = (ay + 40 * w_scale) - travel

                # Fade in when born, fade out towards the top
                norm_y = travel / (height * 0.60)
                alpha = int(240 * math.sin(norm_y * math.pi))
                if alpha <= 5:
                    continue

                col = heart_colors[i % len(heart_colors)]
                size = (26.0 + 14.0 * (i % 4)) * w_scale * (0.9 + 0.2 * math.sin(age * 5.0 + seed))
                _draw_heart(draw, hx, hy, size, (*col, min(255, alpha)))

        # ------------------------------------------------------------------
        # Sparkles / Twinkling Stars
        # ------------------------------------------------------------------
        elif effect_type in ("sparkles", "sparkle", "stars", "star"):
            star_colors = [
                (255, 234, 167),  # golden sunshine
                (255, 255, 255),  # pure white
                (129, 236, 236),  # soft cyan
                (253, 203, 110),  # amber glow
            ]
            num_stars = int(8 * intensity)
            for i in range(num_stars):
                seed = i * 3.17 + 0.8
                ax, ay = anchor_positions[i % len(anchor_positions)]
                radius_orbit = (70.0 + 90.0 * ((seed * 3) % 1.0)) * w_scale
                orbit_angle = seed * 4.0 + age * 1.2 * ((i % 2) * 2 - 1)
                sx = ax + math.cos(orbit_angle) * radius_orbit
                sy = ay + math.sin(orbit_angle) * radius_orbit * 0.7 - (30.0 * w_scale)

                pulse = 0.5 + 0.5 * math.sin(age * 9.0 + seed * 5.0)
                alpha = int(245 * (pulse ** 1.5))
                if alpha <= 10:
                    continue

                size = (18.0 + 16.0 * pulse) * w_scale
                col = star_colors[i % len(star_colors)]
                _draw_star_sparkle(draw, sx, sy, size, (*col, alpha), rot_rad=age * 2.0 + seed)

        # ------------------------------------------------------------------
        # Anime Sweat Drops
        # ------------------------------------------------------------------
        elif effect_type in ("sweat", "sweat_drops", "nervous"):
            for ax, ay in anchor_positions:
                # Place near top-right/top-left of head
                head_x = ax + (65.0 * w_scale)
                head_y = ay - (110.0 * w_scale)
                slide_cycle = (age * 1.6) % 1.0
                drop_y = head_y + (slide_cycle ** 1.3) * (50.0 * w_scale)
                alpha = int(230 * (1.0 - slide_cycle * 0.6))
                size = (28.0 + 8.0 * (1.0 - slide_cycle)) * w_scale
                _draw_sweat_drop(draw, head_x, drop_y, size, (116, 185, 255, alpha))

        # ------------------------------------------------------------------
        # Anime Anger Vein Mark 💢
        # ------------------------------------------------------------------
        elif effect_type in ("anger", "anger_vein", "angry"):
            for ax, ay in anchor_positions:
                head_x = ax + (75.0 * w_scale)
                head_y = ay - (125.0 * w_scale)
                pulse = 1.0 + 0.28 * abs(math.sin(age * 10.0))
                size = 32.0 * w_scale * pulse
                _draw_anger_vein(draw, head_x, head_y, size, (235, 59, 90, 245))

        # ------------------------------------------------------------------
        # Musical Notes 🎵
        # ------------------------------------------------------------------
        elif effect_type in ("music_notes", "music", "musical"):
            note_colors = [
                (255, 107, 129),
                (254, 202, 87),
                (72, 219, 251),
                (29, 209, 161),
            ]
            num_notes = int(5 * intensity)
            for i in range(num_notes):
                seed = i * 2.71 + 0.5
                speed = 95.0 * w_scale * (0.8 + 0.4 * (i % 2))
                travel = (age * speed + seed * 140.0) % (height * 0.50)
                ax, ay = anchor_positions[i % len(anchor_positions)]
                nx = ax + math.sin(age * 4.0 + seed) * (45.0 * w_scale) + ((seed * 11) % 1.0 - 0.5) * (140 * w_scale)
                ny = ay - travel
                norm_y = travel / (height * 0.50)
                alpha = int(240 * math.sin(norm_y * math.pi))
                if alpha <= 8:
                    continue
                size = (22.0 + 8.0 * (i % 3)) * w_scale
                col = note_colors[i % len(note_colors)]
                _draw_music_note(draw, nx, ny, size, (*col, alpha))

        # ------------------------------------------------------------------
        # Confused Question Marks ?
        # ------------------------------------------------------------------
        elif effect_type in ("question_marks", "question", "confused"):
            for idx, (ax, ay) in enumerate(anchor_positions):
                qx = ax + (55.0 * w_scale * ((idx % 2) * 2 - 1))
                qy = ay - (115.0 * w_scale) + math.sin(age * 5.0) * (10.0 * w_scale)
                size = 32.0 * w_scale
                _draw_question_mark(draw, qx, qy, size, (253, 203, 110, 240))

    return layer
