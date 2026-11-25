from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from src.models import StoryBeat
from src.utils import find_ffmpeg, _audio_duration

# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

_VOWEL_SYLLABLE = {
    0:'아',1:'애',2:'야',3:'얘',4:'어',5:'에',6:'여',7:'예',
    8:'오',9:'와',10:'왜',11:'외',12:'요',13:'우',14:'워',
    15:'웨',16:'위',17:'유',18:'으',19:'의',20:'이',
}


def _elongate_korean(text: str, repeats: int = 2) -> str:
    """Append the last syllable's vowel sound repeated — 다 → 다아아."""
    clean = text.rstrip("!?~. ")
    suffix = text[len(clean):]
    for i in range(len(clean) - 1, -1, -1):
        code = ord(clean[i])
        if 0xAC00 <= code <= 0xD7A3:
            vowel_idx = ((code - 0xAC00) // 28) % 21
            vowel_syl = _VOWEL_SYLLABLE.get(vowel_idx, "")
            if vowel_syl:
                return clean + vowel_syl * repeats + suffix
            break
    return text


def _should_speak(text: str) -> bool:
    """Skip beats with no meaningful speech (punctuation-only, zzz, etc.)."""
    clean = text.strip()
    return bool(clean) and len(clean) >= 2 and not all(c in ".…zZ!? " for c in clean)


def _korean_syllable_count(text: str) -> int:
    return sum(1 for c in text if '가' <= c <= '힣')


def _detect_emotion(text: str) -> tuple[float, float, float]:
    """Return (speed_factor, temperature, repetition_penalty) based on emotion."""
    t = text.strip()
    if t.endswith("!!") or t.endswith("!!!"):
        return 0.97, 1.60, 1.10
    if t.endswith("!"):
        # Short sentences (≤6 Korean syllables) don't benefit from high temp —
        # they already sound energetic and high temp causes wobble on short clips.
        if _korean_syllable_count(t) <= 6:
            return 0.90, 1.10, 1.30  # treat as neutral
        return 0.93, 1.40, 1.20
    if t in ("....", "...", "…"):
        return 0.80, 0.85, 1.40
    if ".." in t or "…" in t:
        return 0.85, 0.95, 1.35
    return 0.90, 1.25, 1.30


def _has_repetition(text: str) -> bool:
    """Detect onomatopoeia or repeated syllable patterns like 두근두근, ㅋㅋㅋ."""
    import re
    # Check for Korean syllable repetition (e.g. 두근두근, 하하하)
    return bool(re.search(r'(.{1,3})\1', text))


def _measure_f0(path: Path, sr: int = 16000) -> float:
    """Median fundamental frequency (Hz) via librosa pYIN. 0.0 if unvoiced.

    pYIN is robust to the octave errors that plague raw autocorrelation, so it's
    reliable enough to drive pitch normalization.
    """
    import librosa, numpy as np  # type: ignore[import]
    y, _ = librosa.load(str(path), sr=sr)
    f0, _, _ = librosa.pyin(y, fmin=80, fmax=500, sr=sr, frame_length=2048)
    fv = f0[~np.isnan(f0)]
    return float(np.median(fv)) if len(fv) else 0.0


def _pitch_shift_file(ffmpeg: str, path: Path, semitones: float) -> None:
    """Shift a clip's pitch by N semitones in place (SR-aware phase vocoder)."""
    import librosa, soundfile as sf  # type: ignore[import]
    y, sr = librosa.load(str(path), sr=None)   # native sample rate (GPT-SoVITS = 32000)
    y2 = librosa.effects.pitch_shift(y, sr=sr, n_steps=semitones)
    tmp_wav = path.with_suffix(".pnshift.wav")
    tmp_mp3 = path.with_suffix(".pnshift.mp3")
    sf.write(str(tmp_wav), y2, sr)
    subprocess.run([ffmpeg, "-y", "-i", str(tmp_wav), "-c:a", "libmp3lame", "-b:a", "128k", str(tmp_mp3)],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    tmp_wav.unlink(missing_ok=True)
    if tmp_mp3.exists():
        tmp_mp3.replace(path)


def _resolve_tts_lang(text: str, lang: str = "auto") -> str:
    """Resolve GPT-SoVITS text_lang ('ko' or 'en'). 'auto' picks 'ko' if Hangul is present, else 'en'."""
    norm = (lang or "auto").strip().lower()
    if norm in ("ko", "en"):
        return norm
    return "ko" if any("가" <= c <= "힣" for c in text) else "en"


def _gpt_sovits_clip(
    text: str,
    ref_audio: str,
    path: Path,
    server: str = "http://127.0.0.1:9880",
    speed: float | None = None,
    temperature: float | None = None,
    top_k: int | None = None,
    top_p: float | None = None,
    rep_penalty_override: float | None = None,
    prompt_text: str = "",
    text_lang: str = "auto",
    prompt_lang: str = "ko",
) -> None:
    """Generate one clip via local GPT-SoVITS API server."""
    import requests  # type: ignore[import]
    auto_speed, auto_temp, auto_rep = _detect_emotion(text)
    # Lower repetition_penalty for onomatopoeia so repeated syllables don't get cut
    if rep_penalty_override is not None:
        rep_penalty = rep_penalty_override
    else:
        rep_penalty = 1.05 if _has_repetition(text) else auto_rep
    resolved_lang = _resolve_tts_lang(text, text_lang)
    resp = requests.post(f"{server}/tts", json={
        "text": text,
        "text_lang": resolved_lang,
        "ref_audio_path": ref_audio,
        "prompt_lang": prompt_lang or "ko",
        "prompt_text": prompt_text,
        "speed_factor":       speed       if speed       is not None else auto_speed,
        "temperature":        temperature if temperature is not None else auto_temp,
        "repetition_penalty": rep_penalty,
        "top_k": top_k if top_k is not None else 15,
        "top_p": top_p if top_p is not None else 1.0,
        "streaming_mode": False,
        "batch_size": 1,
    }, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"GPT-SoVITS error {resp.status_code}: {resp.text}")
    path.with_suffix(".wav").write_bytes(resp.content)


def build_tts_audio(
    beats: list,
    duration: float,
    out_path: Path,
    gpt_sovits_ref: str = "",
    gpt_sovits_server: str = "http://127.0.0.1:9880",
    gpt_sovits_speed: float | None = None,
    return_durations: bool = False,
    pregenerated_dir: Path | None = None,
    tts_pitch: float = 1.0,
    gpt_sovits_temperature: float | None = None,
    gpt_sovits_top_k: int | None = None,
    gpt_sovits_top_p: float | None = None,
    gpt_sovits_rep_penalty: float | None = None,
    gpt_sovits_prompt_text: str = "",
    pitch_normalize: bool = False,
    pitch_target: float = 0.0,
    tts_lang: str = "auto",
    tts_prompt_lang: str = "ko",
) -> bool | dict:
    """Generate a timed audio track from beat texts using ffmpeg filter_complex.

    Uses GPT-SoVITS (local voice cloning) for TTS generation.
    Clips are mixed at the correct timestamps via ffmpeg adelay+amix — no ffprobe needed.
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("  TTS skipped: ffmpeg not found")
        return False

    tmp_dir = pregenerated_dir if pregenerated_dir else out_path.parent / "_tts_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Collect indices + beats that need speech
    speak_beats = [(i, b) for i, b in enumerate(beats) if _should_speak(getattr(b, "tts_text", "") or b.text)]
    if not speak_beats:
        print("  TTS skipped: no speakable beats")
        if not pregenerated_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return False

    # ── Generate clips (skipped if pregenerated_dir is provided) ────────────
    if not pregenerated_dir:
        ref, server, speed = gpt_sovits_ref, gpt_sovits_server, gpt_sovits_speed
        if not ref:
            print("  TTS skipped: gpt_sovits_ref not set")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return False
        try:
            for i, b in speak_beats:
                raw_tts = getattr(b, "tts_text", "") or b.text
                tts_text = raw_tts.replace("~", "").strip()
                print(f"    GPT-SoVITS: {tts_text}")
                temp = b.tts_temperature if b.tts_temperature is not None else gpt_sovits_temperature
                sp = b.tts_speed if b.tts_speed is not None else speed
                _gpt_sovits_clip(tts_text, ref, tmp_dir / f"beat_{i:02d}.wav",
                                 server=server,
                                 speed=sp,
                                 temperature=temp,
                                 top_k=gpt_sovits_top_k,
                                 top_p=gpt_sovits_top_p,
                                 rep_penalty_override=gpt_sovits_rep_penalty,
                                 prompt_text=gpt_sovits_prompt_text,
                                 text_lang=tts_lang,
                                 prompt_lang=tts_prompt_lang)
        except Exception as e:
            print(f"  TTS (GPT-SoVITS) failed: {e}")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return False
        for i, _ in speak_beats:
            wav = tmp_dir / f"beat_{i:02d}.wav"
            if wav.exists():
                subprocess.run(
                    [ffmpeg, "-y", "-i", str(wav),
                     "-c:a", "libmp3lame", "-b:a", "128k",
                     str(tmp_dir / f"beat_{i:02d}.mp3")],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                wav.unlink(missing_ok=True)

    # ── Post-process clips ────────────────────────────────────────────────────
    # highpass=f=120 → cuts breath/mendesah low-freq rumble
    # equalizer=f=2500 → gentle presence boost for consonant clarity
    if not pregenerated_dir:
        for i, _ in speak_beats:
            p = tmp_dir / f"beat_{i:02d}.mp3"
            if not p.exists():
                continue
            tmp_p = tmp_dir / f"beat_{i:02d}_c.mp3"
            subprocess.run(
                [ffmpeg, "-y", "-i", str(p),
                 "-af", "highpass=f=120,equalizer=f=2500:width_type=o:width=2:g=2",
                 "-c:a", "libmp3lame", "-b:a", "128k", str(tmp_p)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            if tmp_p.exists():
                tmp_p.replace(p)

    # pitch shift only if tts_pitch != 1.0
    if not pregenerated_dir and abs(tts_pitch - 1.0) > 0.001:
        sr = int(44100 * tts_pitch)
        tempo = 1.0 / tts_pitch
        pitch_filter = f"asetrate={sr},aresample=44100,atempo={tempo:.6f}"
        for i, _ in speak_beats:
            p = tmp_dir / f"beat_{i:02d}.mp3"
            if not p.exists():
                continue
            tmp_p = tmp_dir / f"beat_{i:02d}_c.mp3"
            subprocess.run(
                [ffmpeg, "-y", "-i", str(p),
                 "-af", pitch_filter,
                 "-c:a", "libmp3lame", "-b:a", "128k", str(tmp_p)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            if tmp_p.exists():
                tmp_p.replace(p)

    # ── Pitch normalization — unify register across independently-generated clips ──
    # Each GPT-SoVITS clip is sampled independently, so register drifts ±2 semitones
    # between beats. Measure F0 (pYIN) and shift each clip to a common target.
    if not pregenerated_dir and pitch_normalize:
        import math, statistics
        f0s: dict[int, float] = {}
        for i, _ in speak_beats:
            p = tmp_dir / f"beat_{i:02d}.mp3"
            if p.exists():
                f0s[i] = _measure_f0(p)
        voiced = [v for v in f0s.values() if v > 0]
        if voiced:
            target = pitch_target if pitch_target > 0 else statistics.median(voiced)
            for i, _ in speak_beats:
                f0 = f0s.get(i, 0.0)
                if f0 <= 0:
                    continue
                semis = 12.0 * math.log2(target / f0)
                if abs(semis) < 0.5:
                    continue   # already close — leave untouched to avoid artifacts
                semis = max(-3.0, min(3.0, semis))
                _pitch_shift_file(ffmpeg, tmp_dir / f"beat_{i:02d}.mp3", semis)
                print(f"    pitch-normalized beat {i:02d}: {f0:.0f}Hz -> {target:.0f}Hz")

    # ── Collect clips that were actually written ──────────────────────────────
    clip_list = [
        (i, b) for i, b in speak_beats
        if (tmp_dir / f"beat_{i:02d}.mp3").exists()
    ]

    if not clip_list:
        print("  TTS skipped: no clips generated")
        if not pregenerated_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return False

    # ── Phase 1 mode: measure durations and return them (no mix yet) ─────────
    if return_durations:
        durations = {
            i: _audio_duration(ffmpeg, tmp_dir / f"beat_{i:02d}.mp3")
            for i, _ in clip_list
        }
        return durations

    # ── Fade-out each clip (only if it overflows into the next beat) ─────────
    for idx, (i, beat) in enumerate(clip_list):
        p = tmp_dir / f"beat_{i:02d}.mp3"
        start_time = beat.time + max(0.0, getattr(beat, "tts_delay", 0.0))
        next_time = clip_list[idx + 1][1].time if idx + 1 < len(clip_list) else duration
        max_dur = next_time - start_time - 0.05
        if max_dur <= 0:
            continue
        clip_dur = _audio_duration(ffmpeg, p)
        if clip_dur <= max_dur:
            continue  # clip fits naturally — don't touch it
        trim_dur = max_dur
        fade_dur = min(0.12, trim_dur * 0.08)
        tmp_p = tmp_dir / f"beat_{i:02d}_t.mp3"
        subprocess.run(
            [ffmpeg, "-y", "-i", str(p),
             "-af", f"atrim=end={trim_dur:.3f},afade=t=out:st={trim_dur - fade_dur:.3f}:d={fade_dur:.3f}",
             "-c:a", "libmp3lame", "-b:a", "128k", str(tmp_p)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if tmp_p.exists():
            tmp_p.replace(p)

    # Build ffmpeg command using filter_complex — no ffprobe needed.
    # anullsrc creates the silent base; each clip gets adelay to shift it to
    # the correct beat timestamp; amix combines everything.
    ffmpeg_inputs: list[str] = []
    filter_parts = [
        f"anullsrc=r=44100:cl=stereo,atrim=duration={duration}[base]"
    ]
    mix_labels = ["[base]"]

    for j, (i, beat) in enumerate(clip_list):
        p = tmp_dir / f"beat_{i:02d}.mp3"
        delay_ms = int((beat.time + max(0.0, getattr(beat, "tts_delay", 0.0))) * 1000)
        ffmpeg_inputs += ["-i", str(p)]
        filter_parts.append(f"[{j}]adelay={delay_ms}|{delay_ms}[a{j}]")
        mix_labels.append(f"[a{j}]")

    n = len(mix_labels)
    filter_parts.append(
        f"{''.join(mix_labels)}amix=inputs={n}:normalize=0:duration=first"
    )
    filter_complex = ";".join(filter_parts)

    result = subprocess.run(
        [ffmpeg, "-y"] + ffmpeg_inputs + [
            "-filter_complex", filter_complex,
            "-c:a", "libmp3lame", "-b:a", "128k",
            str(out_path),
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    # Clean up tmp_dir only if we own it (not pregenerated_dir from render())
    if not pregenerated_dir:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if result.returncode != 0:
        print(f"  TTS audio mix failed:\n{result.stderr.decode()}")
        return False

    return True
