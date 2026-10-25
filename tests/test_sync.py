import unittest
import numpy as np

from photo_finish.sync import HOP_SECONDS, energy_envelope, estimate_offset


class SyncTests(unittest.TestCase):
    def test_positive_camera_start_offset(self):
        rng = np.random.default_rng(4)
        phrase = rng.standard_normal(2000)
        master = phrase
        camera = phrase[35:]
        offset, correlation = estimate_offset(master, camera, max_lag_seconds=5)
        self.assertAlmostEqual(offset, 35 * HOP_SECONDS)
        self.assertGreater(correlation, .95)

    def test_negative_camera_start_offset(self):
        rng = np.random.default_rng(6)
        phrase = rng.standard_normal(2000)
        master = phrase[42:]
        camera = phrase
        offset, correlation = estimate_offset(master, camera, max_lag_seconds=5)
        self.assertAlmostEqual(offset, -42 * HOP_SECONDS)
        self.assertGreater(correlation, .95)

    def test_silence_cannot_synchronize(self):
        with self.assertRaisesRegex(ValueError, "uncertain"):
            estimate_offset(np.zeros(1000), np.zeros(1000), max_lag_seconds=5)

    def test_envelope_is_nontranscribing(self):
        samples = np.concatenate([np.zeros(8000), np.ones(8000) * .5])
        features = energy_envelope(samples)
        self.assertEqual(features.ndim, 1)
        self.assertGreater(float(np.max(features)), 0)


if __name__ == "__main__":
    unittest.main()
