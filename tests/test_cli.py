import unittest
from unittest.mock import patch
from photo_finish.cli import main


class CliTests(unittest.TestCase):
    def test_requires_subcommand(self):
        with patch("sys.stderr"):
            with self.assertRaises(SystemExit) as err:
                main([])
        self.assertEqual(err.exception.code, 2)

    def test_rejects_missing_project(self):
        with patch("sys.stderr"):
            self.assertEqual(main(["inspect", "does-not-exist.json"]), 1)


if __name__ == "__main__":
    unittest.main()
