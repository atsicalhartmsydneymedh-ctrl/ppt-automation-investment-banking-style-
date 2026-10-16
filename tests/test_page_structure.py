import unittest

from src.page_structure import build_page_structure_prompt, generate_page_structure, matching_view, validate_page_structure


class PageStructureTests(unittest.TestCase):
    def test_explicit_structure_preserves_relationships_but_not_fixed_region_ratio(self):
        page = {
            "page_number": 5,
            "page_structure": {
                "sizing": "adaptive",
                "between_groups": {"relation": "juxtaposed_peer", "mapping": "none"},
                "groups": [
                    {
                        "id": "g1",
                        "position": "left",
                        "relation": "parallel_equal",
                        "item_count": 5,
                        "order": "none",
                        "item_refs": ["p1", "p2", "p3", "p4", "p5"],
                    },
                    {
                        "id": "g2",
                        "position": "right",
                        "relation": "progressive",
                        "item_count": 4,
                        "order": "required",
                        "item_refs": ["q1", "q2", "q3", "q4"],
                    },
                ],
                "requirements": [],
                "forbids": ["explicit_mapping"],
            },
        }
        structure = generate_page_structure(page)
        self.assertEqual(structure["page_id"], "page_05")
        self.assertEqual(structure["sizing"], "adaptive")
        self.assertNotIn("weight_ratio", structure["between_groups"])
        self.assertEqual(structure["groups"][0]["item_count"], 5)

    def test_matching_view_excludes_visible_content_text(self):
        page = {
            "page_number": 1,
            "page_structure": {
                "sizing": "adaptive",
                "between_groups": {"relation": "single_group", "mapping": "none"},
                "groups": [
                    {
                        "id": "g1",
                        "relation": "parallel_equal",
                        "item_count": 3,
                        "order": "none",
                        "item_refs": ["supporting_points[0]", "supporting_points[1]", "supporting_points[2]"],
                        "visible_text": "不应进入匹配",
                    }
                ],
                "requirements": [],
                "forbids": [],
            },
        }
        view = matching_view(generate_page_structure(page))
        self.assertNotIn("visible_text", str(view))
        self.assertIn("supporting_points[0]", str(view))

    def test_validation_rejects_fixed_sizing_and_unknown_relation(self):
        errors = validate_page_structure(
            {
                "sizing": "fixed_50_50",
                "between_groups": {"relation": "single_group", "mapping": "none"},
                "groups": [{"relation": "industry_specific_relation", "item_count": 2, "order": "none"}],
                "requirements": [],
            }
        )
        self.assertTrue(any("sizing must be adaptive" in error for error in errors))
        self.assertTrue(any("unknown relation" in error for error in errors))

    def test_fallback_is_conservative_and_reviewable(self):
        structure = generate_page_structure(
            {
                "page_number": 1,
                "suggested_visual_type": "structured_bullets",
                "supporting_points": ["A", "B", "C"],
            }
        )
        self.assertEqual(structure["groups"][0]["relation"], "parallel_equal")
        self.assertTrue(structure["inference"]["review_required"])

    def test_visual_type_does_not_drive_structure_inference(self):
        structure = generate_page_structure(
            {
                "page_number": 1,
                "suggested_visual_type": "matrix",
                "title": "三个同等重要的观察",
                "supporting_points": ["观察A", "观察B", "观察C"],
            }
        )
        self.assertEqual(structure["groups"][0]["relation"], "parallel_equal")

    def test_ai_prompt_uses_approved_content_and_forbids_visual_type_routing(self):
        prompt = build_page_structure_prompt(
            {
                "page_number": 2,
                "title": "页面结论",
                "supporting_points": ["要点A", "要点B"],
                "suggested_visual_type": "matrix",
            }
        )
        self.assertIn("要点A", prompt)
        self.assertIn("不要根据行业", prompt)
        self.assertIn("suggested_visual_type", prompt)
        self.assertNotIn('"suggested_visual_type": "matrix"', prompt)


if __name__ == "__main__":
    unittest.main()
