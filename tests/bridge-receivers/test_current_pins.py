"""Controls for the moving receiver pins beside the sealed 0.90.0 bridge proof."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from verify import check_current_pins


class CurrentPinsTests(unittest.TestCase):
    def test_adopted_floor_and_later_coherent_release_pass(self):
        check_current_pins("0.90.0", "0.90.0")
        check_current_pins("0.91.5", "0.91.5")

    def test_skew_downgrade_and_prerelease_fail(self):
        for cli, kit in (
            ("0.91.5", "0.91.4"),
            ("0.89.9", "0.89.9"),
            ("0.91.5-preview", "0.91.5-preview"),
            (None, None),
        ):
            with self.subTest(cli=cli, kit=kit), self.assertRaises(SystemExit):
                check_current_pins(cli, kit)


if __name__ == "__main__":
    unittest.main()
