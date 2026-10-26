import unittest
import numpy as np
from pathlib import Path

from photo_finish.analysis import analyze_voice, choose_main, VisualMoment
from photo_finish.project import Source


class AnalysisTests(unittest.TestCase):
    def test_speech_length_does_not_change(self):
        samples = np.zeros(8000 * 12, dtype=np.float32)
        samples[8000:8000 * 5] = .04
        samples[8000 * 6:8000 * 11] = .6
        moments = analyze_voice(samples)
        self.assertEqual(len(moments), 6)
        self.assertEqual([m.time for m in moments], [0, 2, 4, 6, 8, 10])
        self.assertTrue(moments[0].pause)

    def test_main_override(self):
        cameras = (Source("side", Path("a")), Source("front", Path("b"), "main"))
        self.assertEqual(choose_main(cameras, {}), "front")

    def test_front_preferred_if_automatic(self):
        cameras = (Source("profile", Path("a")), Source("front", Path("b")))
        no_face = VisualMoment(False, 0, .35, .6, .1, .7)
        face = VisualMoment(True, .04, .95, .8, .2, .8)
        self.assertEqual(choose_main(cameras, {
            "profile": [no_face], "front": [face]}), "front")


if __name__ == "__main__":
    unittest.main()
