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

- Start TTS server first if `tts: true` in story.yaml / story.json (for `gpt_sovits`; `tts_engine: "edge"` needs no local server)
- **Agentic Workflow (AX) — Always follow when creating/editing videos:**
  1. Run `.venv\Scripts\python video_generator.py --describe` to get the live JSON catalog of characters, animations, music, SFX, camera/motion/VFX presets, and `beat_presets`.
  2. Write `story.yaml` (use `preset`, `bpm`, `scale_to`/`delay`, `text_anim`, and `attach_to` where helpful).
  3. Fast pre-flight check: `.venv\Scripts\python video_generator.py --story content/<category>/<name> --validate --json`
  4. Visual self-check (recommended): `--storyboard` generates `storyboard.png` for inspection via `read_file` (delete `storyboard.png` afterward if not needed).
  5. Render draft (`--preview`) or final: `.venv\Scripts\python video_generator.py --story content/<category>/<name>` (add `--json` for structured output).
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

- **Prioritize `text` (main title) only** — 100% English, short, and punchy.
- **Do NOT overuse `sub`** — use `sub` only for specific moments (e.g., whispers, internal monologue, or stage directions). If `text` is already clear, leave `sub` empty or omit it.

## Workspace Hygiene (Mandatory)

- **Do not leave scratch or preview files behind** (`*_preview*.png`, `storyboard*.png`, `*crop_preview*/`, `debug_cells/`, `test_crop/`, `*.tmp`, `_tts_tmp/`) in the repo after finishing. Delete all temporary files before ending the task.
- **Use `scripts/gridder`** + JSON configs to process new sprites. Do not create one-off ad-hoc scripts in `scripts/` for a single character.
- **Temporary experiment files** (if truly needed) must go in `_scratch/` (gitignored) and still be cleaned up afterward.
- **Check `git status`** before finishing to ensure no temporary files or one-off scripts remain.
