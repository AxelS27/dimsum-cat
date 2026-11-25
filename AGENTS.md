# DIMsum Cat — Agent & Pipeline Notes

## GPU Requirement

**All heavy processing MUST use GPU (CUDA).** The machine has an NVIDIA GeForce RTX 4060 Laptop GPU.

- PyTorch must be installed with CUDA support: `torch==2.6.0+cu124` (NOT the `+cpu` variant)
- Verify before any upscaling task: `python -c "import torch; print(torch.cuda.is_available())"`
- If CUDA shows `False`, reinstall: `pip install torch==2.6.0+cu124 torchvision==0.21.0+cu124 --index-url https://download.pytorch.org/whl/cu124 --force-reinstall --no-deps`
- Scripts that use ESRGAN (gridder, upscale_sprites, process_background) all auto-detect CUDA — no manual flag needed

## TTS Server

GPT-SoVITS runs as a local API server on `http://127.0.0.1:9880`.

- **Start it** from the project root: `.\start_tts.ps1`
- Installed at: `D:\v\GPT-SoVITS`
- Wait for the server to be ready before rendering with TTS
- Check status: `Invoke-WebRequest -Uri http://127.0.0.1:9880/tts -Method GET`

## Rendering Pipeline

```
story.yaml (or story.json) → video_generator.py → video.mp4 (with TTS + BGM)
```

- Start TTS server first if `tts: true` in story.yaml / story.json
- Render: `.venv\Scripts\python video_generator.py --story content/<category>/<name>`
- Output: `content/<category>/<name>/video.mp4`

## Sprite Pipeline (Gridder)

```
design PNG → scripts/gridder → crop → ESRGAN 4x (GPU) → remove_bg → animations/
```

- Config files: `scripts/gridder/configs/<design_stem>.json`
- For designs spanning full width (no left/right panel split): add `"wide_cols": [x1, x2, ...]` to config
- Output goes to `assets/sprites/<character>/animations/`
- Preview first: `python scripts/gridder <design.png> --preview`

## Characters (Character-Agnostic Studio)

**DIMsum Cat Studio** is a character-agnostic 2D animation framework for generating cute/funny short-form content (stories, POV, dance, comedy) for Instagram/TikTok/Shorts. There is no fixed main character — always check `assets/sprites/` for available characters and `assets/sprites/<character>/animations/` for their animations, and set `"character"` per story or per beat.

See `docs/PLAYBOOK.md` for full story, character, and content rules.

## Story & Subtitle Rules

- **Utamakan `text` (title utama) saja** — `100%` English, singkat, dan punchy.
- **Jangan terlalu sering pakai `sub`** — `sub` hanya dipakai untuk momen tertentu saja (misal bisikan, internal monologue, atau stage direction). Jika `text` sudah jelas, kosongkan/hapus `sub`.

## Workspace Hygiene (Wajib Dipatuhi)

- **Jangan tinggalkan file sampah atau preview** (`*_preview*.png`, `*crop_preview*/`, `debug_cells/`, `test_crop/`, `*.tmp`, `_tts_tmp/`) di dalam repo setelah selesai. Hapus semua file sementara sebelum mengakhiri task.
- **Gunakan `scripts/gridder`** + config JSON untuk memproses sprite baru. Jangan membuat script ad-hoc baru di `scripts/` untuk satu karakter saja.
- **File eksperimen sementara** (jika benar-benar diperlukan) harus ditaruh di `_scratch/` (sudah di-gitignore) dan tetap dibersihkan setelah selesai.
- **Cek `git status`** sebelum selesai memastikan tidak ada file sementara atau script sekali pakai yang tertinggal.
