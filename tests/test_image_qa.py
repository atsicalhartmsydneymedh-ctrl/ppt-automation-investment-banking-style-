import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from src.image_qa import audit_effect_image


STYLE = {
    "canvas": {"width_inches": 13.333, "height_inches": 7.5},
    "palette": {"roles": {"primary": "B42025", "body": "222222", "background": "FFFFFF"}},
    "hard_constraints": {
        "policy": "dynamic_from_core_reference",
        "palette": {
            "allowed_hex": ["B42025", "222222", "FFFFFF"],
            "nearest_color_distance": 58,
            "max_unapproved_accent_share": 0.10,
        },
    },
}


class EffectImageQATests(unittest.TestCase):
    def test_side_by_side_structure_requires_both_regions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "slide.png"
            image = Image.new("RGB", (1600, 900), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((80, 100, 740, 800), fill="#B42025")
            image.save(path)
            structure = {
                "groups": [
                    {"id": "g1", "position": "left"},
                    {"id": "g2", "position": "right"},
                ]
            }
            report = audit_effect_image(path, STYLE, structure)
            self.assertFalse(report["passed"])
            self.assertTrue(any("left/right" in error for error in report["hard_failures"]))


if __name__ == "__main__":
    unittest.main()
