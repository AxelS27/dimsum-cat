# DIMsum Cat Studio — Animation & Story Playbook

> Rule base for AI-assisted short-form animation generation.
> **DIMsum Cat Studio** is a character-agnostic 2D animation framework for generating cute/funny animated content (stories, POVs, dances, comedy) for Instagram/TikTok/Shorts.
> To create a new video: tell the AI your idea, reference this file, and it will output a complete `story.yaml` or `story.json` ready to render.

---

## How to Use

Tell the AI agent:
> "Buat animasi baru tentang [topic/idea] pakai karakter [character]. Ikuti rules di docs/PLAYBOOK.md."

### AI Generation Flow

1. **Run `--describe` first** (`python video_generator.py --describe`) to get the live JSON catalog of all characters, animations, music, SFX, camera types, motion presets, VFX, and semantic `beat_presets`
2. **Read** `content/_template/story.yaml` (or `story.json`) as the base
3. **Author** the story using `preset` (e.g. `panic_zoom`, `cute_blush`, `dance_drop`, `slapstick_hit`, `pov_whisper`, `dramatic_reveal`) or explicit fields
4. **Validate** with `--validate --json` and visually self-check beats with `--storyboard` (`storyboard.png`) before final render

The user saves it to `content/<category>/<name>/story.yaml` (or `story.json`) and renders with:
```bash
.venv/Scripts/python video_generator.py --story content/<category>/<name>
```

Asset paths in story files must use `../../../assets/` (three levels up from the story folder).

---

## Characters

Characters are modular folders in `assets/sprites/<character_name>/`. **There is no single fixed main character** — always inspect `assets/sprites/` to see all available characters (e.g. `dimsum_cat`, `taeho`, `bear_boy`, `bear_girl`, `bear_couple`, `capybara`, `duckling`, etc.) and set `"character": "<folder_name>"` at the root level or per beat.

### Multi-Character Support
Per beat, set `"character": "<folder_name>"` to switch the active character, or use `actors: [...]` to stage multiple characters on screen together:
```json
{ "animation": "happy_bounce", "character": "capybara", ... }
```

### Universal Character & Language Rules
- Visual `text` is always **English** (prominent, punchy, expressive English dialogue or caption).
- `sub` is **strictly optional**: Only use when there is a genuine secondary whisper, internal monologue, or stage direction (e.g. `*(internal panic)*` or `(whispering)`). **Do NOT add `sub` to every beat** — double subtitles cause viewer fatigue. If the main line is clear, omit `sub` completely!
- **100% English**: Visual `text`, optional `sub`, and `tts_text` are all **English** (no Korean/Hangul anywhere).
- **TTS voiceover**:
  - Currently `tts: false` by default while the English GPT-SoVITS voice model is still in progress.
  - For quick draft pacing tests, you can use `"tts": true, "tts_engine": "edge"` (uses `edge-tts`).
  - When `tts: true`, put English spoken lines in `tts_text` (or omit `tts_text` to fall back to `text`), with `"tts_lang": "en"`.
- **Never use emoji in `text`** (fonts don't support color emoji glyphs). Emoji is OK in `description` and `pinned_comment`.

### Animations — ALWAYS Check the Folder

**Do not use any hardcoded animation list.** Always list the actual folder:
```
assets/sprites/<character_name>/animations/
```
New animations may be added at any time. Pick the ones that best fit the emotion of each beat from what actually exists. Use `--list-animations` CLI flag to see all available animations:
```bash
.venv/Scripts/python video_generator.py --list-animations
```

---

## Hashtag System

### Master Hashtags (used in ALL videos)
```
#dimsumcat #kawaii #fyp #foryou #viral #animation #cute #blowthisup #xyzbca #trending #coquette #softlife #catsoftiktok
```

### Per-Category Hashtags (add on top of master)

| Category | Extra Hashtags |
|----------|---------------|
| Story | `#crush #firstlove #lovestory #romance #relatable #storytime` |
| POV | `#pov #povstory #scenario #relatable #storytime` |
| Comedy / Slapstick | `#comedy #funny #memes #relatable #catmemes` |
| Interactive | `#interactive #minigame #challenge #fyp` |

### Description Format
```
[Your caption here] 🐱

[Master hashtags] [Category hashtags]
```

---

## Background Color Rules

Background color (`bg`) should always **match the mood of the video** — not locked to a category. Use this as a guide:

| Mood | Color | Hex |
|------|-------|-----|
| Warm & romantic | Soft peach | `#f5f0ec` |
| Dreamy / crush | Blush pink | `#fdf0f5` |
| Calm & gentle | Baby blue | `#f0f5fd` |
| Cozy / nostalgic | Warm cream | `#fef9f0` |
| Hype / energetic | Soft lavender | `#f5f0ff` |
| Tense / dramatic | Cool blue-grey | `#e8edf5` |
| Sad / emotional | Muted lilac | `#ede8f5` |
| Cheerful / playful | Mint green | `#f0fdf5` |
| Bold / confident | Pale rose | `#fff0f5` |

**Rule:** Pick the color that fits the *emotion of the story*, not the category. A POV video can be warm peach if it's romantic. A K-Drama recreate can be cool blue if it's a tense scene.

---

## Story Structure Rules

### Timing
- Total video: **15–25s** for Story/K-Drama, **10–20s** for POV/Tutorial/K-pop
- First beat at `0.0`
- Beat gaps: **2.5–4s** (auto-retimed by TTS)
- Last beat: ~2s before `duration` end

### Beat Count
- Story / Drama: **6–9 beats**
- POV: **4–6 beats**
- Comedy / Interactive: **4–7 beats**

### Beat Writing Rules
- `text`: short, punchy English — **max ~15–20 chars per line** for readability
- `sub`: strictly optional English secondary line (internal monologue, whisper, or stage direction) — omit when `text` is already clear
- `tts_text`: optional English spoken override when `tts: true` (falls back to `text` if omitted)
- Arc: setup → escalation → reaction → resolution/punchline
- End on a strong beat
- Silent dramatic pause: `"text": "...."` with `side_eye` or `sulking`

### Voice & Tone — Expressive & Relatable
Keep dialogue casual, punchy, and direct to the viewer:
- Conversational, punchy English ("Wait, seriously?", "No way...", "Hold on—")
- Reactions feel genuine and expressive, not scripted
- Energy matches a fun animated short, not a formal presentation

### Scale & Position
- Big moment: `scale 1.2–1.4`, `text_size: "huge"`
- Normal: `scale 1.0–1.1`, `text_size: "big"`
- Whisper/subdued: `scale 0.9–1.0`, `text_size: "normal"`
- Vary `pos` between beats for dynamism

---

## Content Categories

### 1. Story
Relatable love/crush or slice-of-life mini-story.

```
bg: match mood (see Background Color Rules)
tts: false
bg_music: ../../../assets/music/love_maybe.mp3
description: caption + master # + story #
```

Beat flow: Setup → Excited moment → Feeling → Twist → Disappointment → Silence → Resolve → Punchline

Suggested animation mood: expressive talking, excitement, embarrassment, side-eye, determination, cheering — check folder for actual names

---

### 2. POV
Relatable scenario. First beat opens with `"POV:"`.

```
bg: match mood (see Background Color Rules)
tts: false
bg_music: lo-fi track
first beat text: "POV:" + scenario
description: caption + master # + pov #
```

Beat flow: POV setup → Reaction → Escalation → Peak → Punchline

Suggested animation mood: shock, panic, escalating reaction, punchline — check folder for actual names

---

### 3. Dance / Rhythm
Characters dancing, grooving, or performing a cute rhythm loop synced to music.

```
bg: match mood (see Background Color Rules)
tts: false
bg_music: upbeat or viral track
description: caption + master # + #dance #cute #animation
```

Beat rules:
- Set `"bpm": <tempo>` (and optional `"beat_offset": 0.0`, `"auto_beat_zoom": 0.05`) at root to use `"beat": 0, 1, 2...` instead of manual seconds
- Sync beat timestamps and `camera: "zoom_punch"` to the music beat/drop
- Combine `motion` (`squash_bounce`, `sway_tilt`, `anticipate_hop`) with `vfx` (`music_notes`, `sparkles`, `floating_hearts`)
- Optional short English hype captions in `text`

---

### 4. Comedy / Interactive
Fast-paced slapstick, rhythm, or interactive mini-game videos.

```
bg: match mood (see Background Color Rules)
tts: false
bg_music: upbeat or playful track
description: caption + master # + comedy/interactive #
```

Beat rules:
- Time beats tightly to SFX or music rhythm
- High-energy animations, camera punches, and VFX bursts
- End on a strong punchline or payoff

---

## Available Positions
```
center · center-high · center-low
left · right · left-high · right-high · left-low · right-low
```

## Available Text Sizes
```
small · normal · big · huge
```

## TTS Emotion Auto-Detection
- Ends `!!` → excited, faster
- Ends `..` → subdued, slower
- Repeated syllables (두근두근) → lower repetition penalty
- Manual override: `"tts_speed"` and `"tts_temperature"` per beat

---

## Output Template

Save as `content/<name>/story.json`:

```json
{
  "title": "English title",
  "description": "Your caption 🐱\n\n#dimsumcat #kawaii #fyp #foryou #viral #animation #cute #blowthisup #xyzbca #trending #coquette #softlife #catsoftiktok\n[category hashtags here]",

  "animation": "normal_talk",
  "bg": "#f5f0ec",

  "tts": false,
  "tts_lang": "en",
  "gpt_sovits_ref": "",
  "gpt_sovits_server": "http://127.0.0.1:9880",
  "gpt_sovits_speed": 0.88,

  "bg_music": "../../../assets/music/love_maybe.mp3",

  "beats": [
    {
      "time": 0.0,
      "text": "English text",
      "animation": "normal_talk",
      "pos": "center",
      "scale": 1.0,
      "text_size": "big"
    }
  ]
}
```

---

## Pre-Render Checklist

- [ ] All `text` (and optional `sub`) fields are English — no Hangul on screen
- [ ] `tts` is `false` (until English GPT-SoVITS model is ready), or `tts_lang` is set appropriately
- [ ] No emoji in `text`
- [ ] Description has master # + category #
- [ ] `bg_music` path exists
- [ ] If `tts: true`: `gpt_sovits_ref` path exists and GPT-SoVITS server is running at port 9880
- [ ] Story folder created at `content/<category>/<name>/`
