"""Smoke tests for the DIMsum Cat video engine."""
from __future__ import annotations

import unittest
from pathlib import Path

from src.camera import compute_camera
from src.models import ActorConfig, StoryBeat
from src.renderer import iter_video_frames
from src.story import build_parser, load_story_file, validate_story
from src.tts import _detect_emotion, _resolve_tts_lang, _should_speak
from src.vfx import render_vfx_layer


ROOT = Path(__file__).resolve().parent.parent


class EngineSmokeTests(unittest.TestCase):
    def test_get_actors_preserves_per_actor_vfx(self) -> None:
        vfx_payload = [{"type": "floating_hearts", "intensity": 1.2}]
        beat = StoryBeat(
            time=0.0,
            text="Hello",
            actors=[
                ActorConfig(
                    character="dimsum_cat",
                    animation="normal_talk",
                    vfx=vfx_payload,
                )
            ],
        )
        resolved = beat.get_actors(default_character="dimsum_cat", default_animation="normal_talk")
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].vfx, vfx_payload)

    def test_template_story_renders_frames(self) -> None:
        template_dir = ROOT / "content" / "_template"
        args = build_parser().parse_args([])
        config = load_story_file(template_dir, args)
        config.duration = 0.2
        config.fps = 10
        config.width = 360
        config.height = 640

        frames = list(iter_video_frames(config))
        self.assertEqual(len(frames), 2)
        for frame in frames:
            self.assertEqual(frame.size, (360, 640))

    def test_tts_lang_resolution_and_emotion(self) -> None:
        self.assertEqual(_resolve_tts_lang("Hello bestie!", "auto"), "en")
        self.assertEqual(_resolve_tts_lang("안녕 친구야", "auto"), "ko")
        self.assertEqual(_resolve_tts_lang("Hello!", "ko"), "ko")
        self.assertEqual(_resolve_tts_lang("안녕", "en"), "en")
        self.assertFalse(_should_speak("...."))
        self.assertTrue(_should_speak("Wait what?!"))
        speed, temp, _ = _detect_emotion("No way!!")
        self.assertGreater(temp, 1.4)
        self.assertGreater(speed, 0.9)

    def test_camera_and_vfx_smoke(self) -> None:
        cam = compute_camera({"type": "zoom_punch", "zoom": 1.25}, age=0.5, beat_dur=2.0)
        self.assertGreaterEqual(cam.zoom, 1.0)

        vfx_img = render_vfx_layer(
            canvas_size=(360, 640),
            vfx_specs=[{"type": "floating_hearts", "intensity": 1.0}],
            t=0.5,
            age=0.5,
            anchor_positions=[(180.0, 320.0)],
        )
        self.assertEqual(vfx_img.size, (360, 640))
        self.assertEqual(vfx_img.mode, "RGBA")

    def test_validate_story_catches_missing_animation_and_hangul(self) -> None:
        template_dir = ROOT / "content" / "_template"
        cfg = load_story_file(template_dir, build_parser().parse_args([]))
        # Template uses clean English text
        errs = validate_story(cfg)
        self.assertEqual(errs, [])

        cfg.beats[0].text = "안녕"
        cfg.beats[0].animation = "nonexistent_animation_xyz"
        errs2 = validate_story(cfg)
        self.assertTrue(any("Hangul" in e for e in errs2))
        self.assertTrue(any("missing animation" in e for e in errs2))


if __name__ == "__main__":
    unittest.main()
