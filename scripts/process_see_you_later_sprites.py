"""
Process See You Later Alligator Sprite Sheet:
Crop (8 frames per animal) -> Upscale 4x with RealESRGAN (CUDA) -> Remove Green Background with Border Flood Fill + Despill.
"""
import os
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DESIGN_SHEET = ROOT / "assets/sprites/animals/design/see_you_later_sheet.png"
MODEL_PATH = ROOT / "assets/sprites/dimsum_cat/.esrgan_weights/RealESRGAN_x4plus_anime_6B.pth"
OUT_BASE = ROOT / "assets/sprites/animals/animations"

COL_DIVS = [0, 157, 313, 470, 627, 783, 940, 1096, 1254]
ROW_SPANS = [
    ("alligator", 35, 186),
    ("crocodile", 216, 372),
    ("ladybug", 402, 563),
    ("jellyfish", 593, 748),
]

LETTER_NAMES = ["frame_a.png", "frame_b.png", "frame_c.png", "frame_d.png",
                "frame_e.png", "frame_f.png", "frame_g.png", "frame_h.png"]
NUMBER_NAMES = [f"frame_{i:02d}.png" for i in range(1, 9)]


def _clean_chroma_bg(img: Image.Image) -> Image.Image:
    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    h, w = arr.shape[:2]

    # Kill border edge grid lines (outer 6px)
    BORDER = 6
    for y in range(BORDER):
        arr[y, :, 3] = 0
        arr[h - 1 - y, :, 3] = 0
    for x in range(BORDER):
        arr[:, x, 3] = 0
        arr[:, w - 1 - x, 3] = 0

    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)

    # Pure chroma green criterion (high green, low red, low blue)
    is_green = (g > 130) & (g - r > 45) & (g - b > 45)

    # Flood fill starting from all 4 borders
    visited = np.zeros((h, w), dtype=bool)
    q = deque()

    for y in range(h):
        for x in [BORDER, w - 1 - BORDER]:
            if is_green[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))
    for x in range(w):
        for y in [BORDER, h - 1 - BORDER]:
            if is_green[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))

    while q:
        cy, cx = q.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and is_green[ny, nx]:
                visited[ny, nx] = True
                q.append((ny, nx))

    arr[visited, 3] = 0

    # Despill: on outer boundary pixels, if there's green fringe, suppress green
    alpha = arr[:, :, 3]
    pad_a = np.pad(alpha, 1, constant_values=0)
    has_transp = (
        (pad_a[:-2, 1:-1] == 0) | (pad_a[2:, 1:-1] == 0) |
        (pad_a[1:-1, :-2] == 0) | (pad_a[1:-1, 2:] == 0)
    )
    is_fringe = (alpha > 0) & has_transp & (arr[:, :, 1] > arr[:, :, 0]) & (arr[:, :, 1] > arr[:, :, 2])
    # Clamp green channel to average of red and blue on edge
    avg_rb = ((arr[:, :, 0].astype(int) + arr[:, :, 2].astype(int)) // 2).astype(np.uint8)
    arr[is_fringe, 1] = np.minimum(arr[is_fringe, 1], avg_rb[is_fringe] + 15)

    return Image.fromarray(arr, "RGBA")


def main():
    print("=== Processing See You Later Alligator Sprites (Clean Flood Fill) ===")
    sheet = Image.open(DESIGN_SHEET)

    # 1. Crop
    print("\n[1/3] Cropping cells...")
    cropped_files = {}
    for anim_name, y0, y1 in ROW_SPANS:
        anim_dir = OUT_BASE / anim_name
        anim_dir.mkdir(parents=True, exist_ok=True)
        cropped_files[anim_name] = []
        for c in range(8):
            x0 = COL_DIVS[c] + 1
            x1 = COL_DIVS[c + 1] - 1
            crop = sheet.crop((x0, y0, x1, y1))
            fname = NUMBER_NAMES[c]
            p = anim_dir / fname
            crop.save(p)
            cropped_files[anim_name].append(p)
        print(f"  Cropped {anim_name} (8 frames)")

    # 2. Upscale 4x with RealESRGAN
    print("\n[2/3] Upscaling 4x on GPU (CUDA)...")
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  Using device: {device}")
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                    num_block=6, num_grow_ch=32, scale=4)
    upsampler = RealESRGANer(scale=4, model_path=str(MODEL_PATH), model=model,
                             tile=0, tile_pad=10, pre_pad=0, half=torch.cuda.is_available(),
                             device=device)

    for anim_name, paths in cropped_files.items():
        t0 = time.time()
        for p in paths:
            img = Image.open(p).convert("RGB")
            bgr = np.array(img)[:, :, ::-1]
            out_bgr, _ = upsampler.enhance(bgr, outscale=4)
            out = Image.fromarray(out_bgr[:, :, ::-1], "RGB")
            out.save(p)
        print(f"  Upscaled {anim_name} in {time.time() - t0:.2f}s")

    # 3. Clean Background
    print("\n[3/3] Flood filling chroma green and normalizing...")
    for anim_name, paths in cropped_files.items():
        anim_dir = OUT_BASE / anim_name
        cleaned_images = []
        for p in paths:
            cleaned = _clean_chroma_bg(Image.open(p))
            cleaned_images.append(cleaned)

        mw = max(img.width for img in cleaned_images)
        mh = max(img.height for img in cleaned_images)

        for c, (p, img) in enumerate(zip(paths, cleaned_images)):
            if img.size != (mw, mh):
                img = img.resize((mw, mh), Image.Resampling.LANCZOS)
            img.save(p)
            letter_p = anim_dir / LETTER_NAMES[c]
            img.save(letter_p)

        print(f"  {anim_name:<12} -> {mw}x{mh} (8 frames, transparent, green preserved)")

    print("\n=== Extraction & Upscaling Complete! ===")


if __name__ == "__main__":
    main()
