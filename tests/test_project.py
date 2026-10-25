import json
from pathlib import Path
import tempfile
import unittest
from photo_finish.project import load_project


class ManifestTests(unittest.TestCase):
    def test_any_camera_count_and_optional_slides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lav.wav").touch()
            for i in range(7):
                (root / f"{i}.mp4").touch()
            (root / "slides.mp4").touch()
            content = {"audio": "lav.wav",
                       "cameras": [{"path": f"{i}.mp4"} for i in range(7)],
                       "slides": {"path": "slides.mp4"}}
            (root / "project.json").write_text(json.dumps(content))
            loaded = load_project(root / "project.json")
            self.assertEqual(len(loaded.cameras), 7)
            self.assertEqual(loaded.cameras[0].role, "auto")
            self.assertEqual(loaded.slides.name, "slides")

    def test_reject_duplicate_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lav.wav").touch()
            (root / "cam.mp4").touch()
            (root / "project.json").write_text(json.dumps({
                "audio": "lav.wav", "cameras": [
                    {"path": "cam.mp4", "name": "same"},
                    {"path": "cam.mp4", "name": "same"}]}))
            with self.assertRaisesRegex(ValueError, "unique"):
                load_project(root / "project.json")


if __name__ == "__main__":
    unittest.main()
