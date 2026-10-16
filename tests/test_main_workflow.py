import contextlib
import io
import unittest

from src.main import parse_args


class MainWorkflowCliTests(unittest.TestCase):
    def test_production_prepare_is_the_default(self):
        args = parse_args(["--input", "report.md"])
        self.assertEqual(args.mode, "production")
        self.assertEqual(args.stage, "prepare")

    def test_generate_requires_a_page_number_at_parse_time(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parse_args(["--stage", "generate"])

    def test_legacy_mode_preserves_old_provider_options(self):
        args = parse_args(["--mode", "legacy", "--input", "report.md", "--mockup-provider", "placeholder"])
        self.assertEqual(args.mode, "legacy")
        self.assertEqual(args.mockup_provider, "placeholder")


if __name__ == "__main__":
    unittest.main()
