import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from composition_router import route_composition


class CompositionRouterTests(unittest.TestCase):
    def test_table_content_routes_to_restrained_utility(self):
        decision = route_composition({"suggested_visual_type": "editable_table", "content_char_count": 900})
        self.assertEqual(decision["design_intensity"]["level"], 2)
        self.assertEqual(decision["visual_proposition"], "not_required")
        self.assertEqual(decision["design_archetype"], "Evidence Table")

    def test_data_content_routes_to_analytical_evidence(self):
        decision = route_composition({"suggested_visual_type": "data_cards", "data_points": ["12%"], "content_char_count": 500})
        self.assertEqual(decision["design_intensity"]["level"], 3)
        self.assertEqual(decision["design_archetype"], "Chart + Table Evidence")

    def test_ecosystem_content_routes_to_hero_composition(self):
        decision = route_composition({"title": "平台生态", "suggested_visual_type": "structured_bullets", "content_char_count": 700})
        self.assertEqual(decision["design_intensity"]["level"], 4)
        self.assertEqual(decision["design_archetype"], "Integrated Ecosystem Canvas")
        self.assertIn("中心", decision["visual_proposition"])


if __name__ == "__main__":
    unittest.main()
