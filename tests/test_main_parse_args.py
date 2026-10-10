import argparse
import ast
import unittest
from pathlib import Path


def load_parse_args():
    source_path = Path(__file__).resolve().parents[1] / "src" / "main.py"
    module = ast.parse(source_path.read_text(), filename=str(source_path))
    function = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "parse_args"
    )
    namespace = {"argparse": argparse}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source_path), "exec"), namespace)
    return namespace["parse_args"]


parse_args = load_parse_args()


class ParseArgsTests(unittest.TestCase):
    def test_required_input_and_optional_defaults(self):
        args = parse_args(["--input", "report.md"])

        self.assertEqual(args.input, "report.md")
        self.assertEqual(args.output, "output")
        self.assertIsNone(args.config)
        self.assertIsNone(args.mockup_provider)
        self.assertIsNone(args.image_dir)
        self.assertIsNone(args.core_reference)

    def test_accepts_each_documented_mockup_provider(self):
        for provider in ("openai_cli", "prompt_only", "existing", "placeholder"):
            with self.subTest(provider=provider):
                args = parse_args(["--input", "report.pdf", "--mockup-provider", provider])
                self.assertEqual(args.mockup_provider, provider)

    def test_rejects_missing_required_input_and_unknown_provider(self):
        with self.assertRaises(SystemExit):
            parse_args([])
        with self.assertRaises(SystemExit):
            parse_args(["--input", "report.txt", "--mockup-provider", "remote"])

    def test_preserves_explicit_path_values(self):
        args = parse_args([
            "--input", "report.docx",
            "--output", "build/slides",
            "--config", "settings.json",
            "--image-dir", "images",
            "--core-reference", "template.pptx",
        ])

        self.assertEqual(args.output, "build/slides")
        self.assertEqual(args.config, "settings.json")
        self.assertEqual(args.image_dir, "images")
        self.assertEqual(args.core_reference, "template.pptx")


if __name__ == "__main__":
    unittest.main()
