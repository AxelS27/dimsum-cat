"""
Extract sprites from finger_cleaning.png → experiments/animations/
Then runs gridder steps 2 (upscale) + 3 (remove bg).
"""
from pathlib import Path
from PIL import Image

ROOT      = Path(__file__).resolve().parent.parent
SRC       = ROOT / "random" / "finger_cleaning.png"
OUT_DIR   = ROOT / "experiments" / "animations"

# Pixel boundaries (detected from image analysis)
ROWS = [
    (47,  211),   # row 1
    (243, 419),   # row 2
    (451, 617),   # row 3
]
COLS = [
    (16,  155),   # col 1
    (159, 294),   # col 2
    (297, 435),   # col 3
    (438, 581),   # col 4
    (584, 718),   # col 5
    (721, 855),   # col 6
    (859, 993),   # col 7
    (996, 1130),  # col 8
]

# (row_idx, col_idx) → (anim_dir, frame_filename)
MAPPING = {
    # Row 1
    (0, 0): ("finger_marker",  "frame_a.png"),
    (0, 1): ("arrow",          "frame_a.png"),
    (0, 2): ("noticing",       "frame_a.png"),
    (0, 3): ("noticing",       "frame_b.png"),
    (0, 4): ("wiping",         "frame_a.png"),
    (0, 5): ("wiping",         "frame_b.png"),
    (0, 6): ("wiping",         "frame_c.png"),
    (0, 7): ("wiping",         "frame_d.png"),
    # Row 2
    (1, 0): ("spraying",       "frame_a.png"),
    (1, 1): ("spraying",       "frame_b.png"),
    (1, 2): ("spraying",       "frame_c.png"),
    (1, 3): ("spraying",       "frame_d.png"),
    (1, 4): ("inspect",        "frame_a.png"),
    (1, 5): ("inspect",        "frame_b.png"),
    (1, 6): ("inspect",        "frame_c.png"),
    (1, 7): ("inspect",        "frame_d.png"),
    # Row 3
    (2, 0): ("ending",         "frame_a.png"),
    (2, 1): ("ending",         "frame_b.png"),
    (2, 2): ("tiny_cloth",     "frame_a.png"),
    (2, 3): ("spray_bottle",   "frame_a.png"),
    (2, 4): ("sparkle",        "frame_a.png"),
    (2, 5): ("sparkle",        "frame_b.png"),
    (2, 6): ("heart",          "frame_a.png"),
    (2, 7): ("speech_bubble",  "frame_a.png"),
}

def main():
    img = Image.open(SRC).convert("RGBA")
    print(f"Source: {SRC}  ({img.width}x{img.height})")

    for (row_i, col_i), (anim, fname) in MAPPING.items():
        y0, y1 = ROWS[row_i]
        x0, x1 = COLS[col_i]
        anim_dir = OUT_DIR / anim
        anim_dir.mkdir(parents=True, exist_ok=True)
        out_path = anim_dir / fname
        img.crop((x0, y0, x1, y1)).save(str(out_path), "PNG")
        print(f"  {anim}/{fname}  ({x1-x0}x{y1-y0}px)")

    print(f"\nExtracted {len(MAPPING)} sprites → {OUT_DIR}")
    print("\nNext: run upscale + remove bg")
    print("  python scripts/gridder random/finger_cleaning.png --step 2 --out experiments/animations")
    print("  python scripts/gridder random/finger_cleaning.png --step 3 --out experiments/animations")

if __name__ == "__main__":
    main()
