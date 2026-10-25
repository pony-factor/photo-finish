import unittest
from photo_finish.director import Shot, validate_shots


class DirectorTests(unittest.TestCase):
    def test_preserves_complete_original_time(self):
        shots = [Shot(0, 4, "front", "main"),
                 Shot(4, 13, "side", "side", True),
                 Shot(13, 25, "front", "main")]
        validate_shots(shots, 25)

    def test_rejects_removed_pauses(self):
        with self.assertRaisesRegex(ValueError, "gap"):
            validate_shots([Shot(0, 5, "front", "main"),
                            Shot(6, 10, "side", "side")], 10)

    def test_rejects_missing_tail(self):
        with self.assertRaisesRegex(ValueError, "omit"):
            validate_shots([Shot(0, 9, "front", "main")], 10)


if __name__ == "__main__":
    unittest.main()
