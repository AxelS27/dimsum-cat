"""Smoke tests for the DIMsum Cat video engine."""
from __future__ import annotations

import unittest
from pathlib import Path

from src.camera import compute_camera
from src.models import Accessory, ActorConfig, StoryBeat
from src.output import _video_encoder_args
from src.renderer import _fast_resize, _fast_rotate, iter_video_frames
from src.story import build_parser, describe_capabilities, load_story_file, render_storyboard, validate_story
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

    def test_actor_keyframes_delay_and_opacity_render(self) -> None:
        template_dir = ROOT / "content" / "_template"
        cfg = load_story_file(template_dir, build_parser().parse_args([]))
        cfg.duration = 0.6
        cfg.fps = 10
        cfg.width = 360
        cfg.height = 640
        cfg.beats = [
            StoryBeat(
                time=0.0,
                text="Keyframe test",
                animation="normal_talk",
                scale=0.8,
                scale_to=1.4,
                cat_rotate=0.0,
                rotate_to=15.0,
                opacity=0.9,
                fade_in=0.2,
                fade_out=0.2,
                delay=0.2,
            )
        ]
        frames = list(iter_video_frames(cfg))
        self.assertEqual(len(frames), 6)
        self.assertEqual(frames[0].size, (360, 640))

    def test_bpm_beat_resolution_and_auto_beat_zoom(self) -> None:
        import json, tempfile
        story_data = {
            "title": "Dance Beat Test",
            "duration": 1.0,
            "fps": 10,
            "width": 360,
            "height": 640,
            "bpm": 120,
            "beat_offset": 0.1,
            "auto_beat_zoom": 0.06,
            "beats": [
                {"beat": 0, "text": "One!", "animation": "normal_talk"},
                {"beat": 1, "text": "Two!", "animation": "normal_talk"},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "story.json"
            p.write_text(json.dumps(story_data), encoding="utf-8")
            cfg = load_story_file(p, build_parser().parse_args([]))
            self.assertAlmostEqual(cfg.beats[0].time, 0.1)
            self.assertAlmostEqual(cfg.beats[1].time, 0.6)
            frames = list(iter_video_frames(cfg))
            self.assertEqual(len(frames), 10)

    def test_kinetic_typography_modes_render(self) -> None:
        template_dir = ROOT / "content" / "_template"
        cfg = load_story_file(template_dir, build_parser().parse_args([]))
        cfg.duration = 0.6
        cfg.fps = 10
        cfg.width = 360
        cfg.height = 640
        cfg.beats = [
            StoryBeat(time=0.0, text="Typewriter!", animation="normal_talk", text_anim="typewriter"),
            StoryBeat(time=0.2, text="PANIC!!", animation="normal_talk", text_anim="shake"),
            StoryBeat(time=0.4, text="POP!", animation="normal_talk", text_anim="pop"),
        ]
        frames = list(iter_video_frames(cfg))
        self.assertEqual(len(frames), 6)

    def test_attached_accessory_renders_on_actor(self) -> None:
        template_dir = ROOT / "content" / "_template"
        cfg = load_story_file(template_dir, build_parser().parse_args([]))
        cfg.duration = 0.2
        cfg.fps = 10
        cfg.width = 360
        cfg.height = 640
        cfg.beats = [
            StoryBeat(
                time=0.0,
                text="With prop!",
                animation="normal_talk",
                motion="squash_bounce",
                accessories=[
                    Accessory(
                        image="assets/sprites/watermark.png",
                        scale=0.2,
                        attach_to="dimsum_cat",
                        offset=(0.0, -0.35),
                    )
                ],
            )
        ]
        frames = list(iter_video_frames(cfg))
        self.assertEqual(len(frames), 2)

    def test_fast_resize_and_rotate_preserve_rgba(self) -> None:
        from PIL import Image
        img = Image.new("RGBA", (40, 20), (255, 100, 50, 200))
        resized = _fast_resize(img, (80, 40))
        self.assertEqual(resized.size, (80, 40))
        self.assertEqual(resized.mode, "RGBA")
        rotated = _fast_rotate(resized, 30.0)
        self.assertEqual(rotated.mode, "RGBA")
        self.assertGreater(rotated.width, 80)
        self.assertGreater(rotated.height, 40)

    def test_describe_and_presets_and_storyboard(self) -> None:
        import json, tempfile
        caps = describe_capabilities()
        self.assertIn("dimsum_cat", caps["characters"])
        self.assertIn("panic_zoom", caps["beat_presets"])
        self.assertIn("typewriter", caps["text_anims"])

        # Fuzzy suggestion on typo
        template_dir = ROOT / "content" / "_template"
        cfg = load_story_file(template_dir, build_parser().parse_args([]))
        cfg.beats[0].animation = "normal_talkk"
        errs = validate_story(cfg)
        self.assertTrue(any("Did you mean" in e and "normal_talk" in e for e in errs))

        # Preset expansion + storyboard generation
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "story.json"
            p.write_text(
                json.dumps({
                    "title": "Preset Test",
                    "duration": 2.0,
                    "beats": [
                        {"time": 0.0, "text": "Wait!", "animation": "normal_talk", "preset": "panic_zoom"},
                        {"time": 1.0, "text": "Yay!", "animation": "normal_talk", "preset": "dance_drop"},
                    ],
                }),
                encoding="utf-8",
            )
            pcfg = load_story_file(p, build_parser().parse_args([]))
            self.assertEqual(pcfg.beats[0].text_anim, "shake")
            self.assertEqual(pcfg.beats[1].motion, "heavy_bounce")
            sb_path = render_storyboard(pcfg, Path(tmp) / "storyboard.png")
            self.assertTrue(sb_path.exists())

    def test_video_encoder_args_returns_valid_codec(self) -> None:
        from src.utils import find_ffmpeg
        ffmpeg = find_ffmpeg() or "ffmpeg"
        args = _video_encoder_args(ffmpeg)
        self.assertIn("-c:v", args)
        self.assertTrue("h264_nvenc" in args or "libx264" in args)


if __name__ == "__main__":
    unittest.main()
