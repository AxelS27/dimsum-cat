"""
preview_frames.py — Render one frame per beat for a given story.

Usage:
    python scripts/preview_frames.py --story content/story/delulu_math

Output:
    content/story/delulu_math/preview_frames/beat_00.png
    content/story/delulu_math/preview_frames/beat_01.png
    ...
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.models import Accessory, RenderConfig, RichTextSpan, StoryBeat


def _load_rich_text(raw: object) -> list[RichTextSpan]:
    if not isinstance(raw, list):
        return []
    spans = []
    for item in raw:
        if isinstance(item, dict):
            text = str(item.get("text", ""))
            if text:
                spans.append(RichTextSpan(text=text, color=str(item.get("color", "#2a2a2a"))))
    return spans


def render_beat_frame(
    beat: StoryBeat,
    default_animation: str,
    default_character: str,
    width: int,
    height: int,
    fps: int,
    bg: str,
    story_dir: Path,
    bg_image: str = "",
) -> "Image":
    from src.renderer import render_video_frames

    config = RenderConfig(
        beats=[beat],
        default_animation=beat.animation or default_animation,
        default_character=beat.character or default_character,
        output_name="preview",
        duration=0.5,
        fps=fps,
        width=width,
        height=height,
        bg=bg,
        bg_image=bg_image,
        watermark="",
        story_dir=story_dir,
    )
    frames = render_video_frames(config)
    return frames[-1]  # last frame = fade-in complete


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render one preview frame per beat for a story.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
  python scripts/preview_frames.py --story content/story/delulu_math
  python scripts/preview_frames.py --story content/kdrama/bon_appetit_ramyeon
""",
    )
    parser.add_argument(
        "--story", type=Path, required=True,
        help="Path to story folder (containing story.json) or directly to story.json",
    )
    args = parser.parse_args()

    story_path = args.story
    if story_path.is_dir():
        story_path = story_path / "story.json"
    story_path = story_path.resolve()
    story_dir  = story_path.parent

    data = json.loads(story_path.resolve().read_text(encoding="utf-8"))
    raw_beats = data.get("beats", [])

    width             = int(data.get("width",  1080))
    height            = int(data.get("height", 1920))
    fps               = int(data.get("fps",    24))
    bg                = data.get("bg", "#f8f4f0")
    from src.story import _resolve_story_path
    bg_image          = _resolve_story_path(data.get("bg_image", ""), story_dir)
    default_animation = data.get("animation", "normal_talk")
    default_character = data.get("character", "dimsum_cat")

    out_dir = story_dir / "preview_frames"
    out_dir.mkdir(exist_ok=True)

    print(f"Story   : {story_dir.name}")
    print(f"Beats   : {len(raw_beats)}")
    print(f"Output  : {out_dir}")
    print()

    # Walk forward to track the last seen animation (mirrors renderer behavior)
    last_anim = default_animation
    last_char = default_character

    for i, b in enumerate(raw_beats):
        anim = b.get("animation", "") or last_anim
        char = b.get("character", "") or last_char
        last_anim = anim
        last_char = char

        accessories = [
            Accessory(
                image   = a.get("image", ""),
                pos     = a.get("pos", "0.5,0.5"),
                scale   = float(a.get("scale", 1.0)),
                flip_x  = bool(a.get("flip_x", False)),
                rotate  = float(a.get("rotate", 0.0)),
            )
            for a in b.get("accessories", [])
            if a.get("image")
        ]

        beat = StoryBeat(
            time          = 0.0,
            text          = b.get("text", ""),
            sub           = b.get("sub", ""),
            animation     = anim,
            pos           = b.get("pos", "center"),
            scale         = float(b.get("scale", 1.0)),
            text_size     = b.get("text_size", "normal"),
            rich_text     = _load_rich_text(b.get("rich_text")),
            rich_text_sub = _load_rich_text(b.get("rich_text_sub")),
            character     = char,
            flip_x        = bool(b.get("flip_x", False)),
            cat_rotate    = float(b.get("cat_rotate", 0.0)),
            accessories   = accessories,
        )

        beat_bg_raw = b.get("bg_image", "")
        beat_bg = _resolve_story_path(beat_bg_raw, story_dir) if beat_bg_raw else bg_image
        frame = render_beat_frame(
            beat, default_animation, default_character,
            width, height, fps, bg, story_dir,
            bg_image=beat_bg,
        )

        out_path = out_dir / f"beat_{i:02d}.png"
        frame.save(out_path)

        label = beat.text[:35] if beat.text else "(silent)"
        print(f"  beat_{i:02d}.png  [{anim}]  {label}")

    print(f"\nDone — {len(raw_beats)} frames saved to:\n  {out_dir}")


if __name__ == "__main__":
    main()
