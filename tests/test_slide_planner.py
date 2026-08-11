import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slide_planner import create_slide_plans, plan_to_markdown


class SlidePlannerCompositionTests(unittest.TestCase):
    def test_composition_decision_is_persisted_and_guides_hero_prompt(self):
        segment = {
            "slide_number": 1,
            "id": "s001",
            "title": "平台生态与增长网络",
            "core_message": "平台生态形成增长网络。",
            "supporting_points": ["连接供给和需求"],
            "data_points": [],
            "suggested_visual_type": "structured_bullets",
            "source_block_ids": [],
            "content_char_count": 600,
        }
        plan = create_slide_plans([segment])[0]
        self.assertEqual(plan["design_intensity"]["level"], 4)
        self.assertEqual(plan["design_archetype"], "Integrated Ecosystem Canvas")
        self.assertIn("Visual proposition:", plan["image2_prompt"])
        self.assertIn("Do not replace the composition with equal cards", plan["image2_prompt"])
        self.assertIn("Composition decision:", plan_to_markdown(plan))

    def test_legacy_layout_routing_can_be_restored(self):
        segment = {
            "slide_number": 1, "id": "s001", "title": "平台生态", "core_message": "生态", "supporting_points": [],
            "data_points": [], "suggested_visual_type": "structured_bullets", "source_block_ids": [], "content_char_count": 100,
        }
        plan = create_slide_plans([segment], {"composition_decision": {"enabled": False}})[0]
        self.assertNotIn("composition_decision", plan)
        self.assertEqual(plan["layout"]["name"], "Three-column insight grid")


if __name__ == "__main__":
    unittest.main()
