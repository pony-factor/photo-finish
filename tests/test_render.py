import unittest
from photo_finish.director import Shot
from photo_finish.render import video_filter


class RenderTests(unittest.TestCase):
    def test_main_remains_stable(self):
        command = video_filter(Shot(0, 5, "front", "main"), width=1920, height=1080, fps=30)
        self.assertNotIn("sin(", command)

    def test_side_pan_is_smooth(self):
        command = video_filter(Shot(0, 8, "profile", "side", True),
                               width=1920, height=1080, fps=30)
        self.assertIn("sin(", command)
        self.assertIn("crop=1920:1080", command)

    def test_slides_are_letterboxed_not_cropped(self):
        command = video_filter(Shot(0, 5, "slides", "slides"),
                               width=1920, height=1080, fps=30)
        self.assertIn("pad=1920:1080", command)


if __name__ == "__main__":
    unittest.main()
