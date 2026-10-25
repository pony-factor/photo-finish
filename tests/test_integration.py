"""End-to-end FFmpeg smoke test using synthetic data, not a speech transcript."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from photo_finish.project import duration, load_project
from photo_finish.director import make_plan, validate_shots
from photo_finish.render import render
from photo_finish.sync import synchronize


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class IntegrationTests(unittest.TestCase):
    def test_synthetic_two_angle_lavalier_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            microphone = directory / "lav.wav"
            camera = directory / "front.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "sine=frequency=240:sample_rate=16000:duration=10",
                "-c:a", "pcm_s16le", str(microphone),
            ], check=True, capture_output=True)
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=12:duration=10",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(camera),
            ], check=True, capture_output=True)
            manifest = directory / "project.json"
            manifest.write_text(json.dumps({
                "audio": "lav.wav",
                "cameras": [
                    {"name": "front", "path": "front.mp4",
                     "role": "main", "offset_seconds": 0},
                    {"name": "alternate", "path": "front.mp4",
                     "role": "side", "offset_seconds": 0},
                ]
            }))
            project = load_project(manifest)
            offsets = synchronize(project)
            self.assertEqual(offsets, {"front": 0., "alternate": 0.})
            plan = make_plan(project, offsets)
            validate_shots(plan.shots, plan.duration)
            self.assertEqual(plan.main_camera, "front")
            self.assertEqual(plan.shots[0].start, 0)
            self.assertAlmostEqual(plan.shots[-1].end, 10., delta=.1)
            path = directory / "edited.mp4"
            render(project, plan, path, width=320, height=180,
                   fps=12, clean_audio=False)
            self.assertTrue(path.is_file())
            self.assertAlmostEqual(duration(path), duration(microphone), delta=.25)


if __name__ == "__main__":
    unittest.main()
