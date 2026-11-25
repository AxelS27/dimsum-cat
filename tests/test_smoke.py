"""Smoke tests for the DIMsum Cat video engine."""
from __future__ import annotations

import unittest
from pathlib import Path

from src.models import ActorConfig, StoryBeat
from src.renderer import iter_video_frames
from src.story import build_parser, load_story_file


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


if __name__ == "__main__":
    unittest.main()
