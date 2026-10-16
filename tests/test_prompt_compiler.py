import unittest

from src.prompt_compiler import compile_effect_image_prompt


class PromptCompilerTests(unittest.TestCase):
    def test_approved_design_and_library_mechanism_are_prompt_authorities(self):
        prompt = compile_effect_image_prompt(
            {"title": "结论标题", "objective": "页面结论"},
            "CONTENT UNIQUE ORDER",
            "EVIDENCE UNIQUE VALUE 18.85%",
            "DESIGN UNIQUE LAYOUT: shared-axis plot plus event windows",
            "STYLE UNIQUE: navy palette",
            {
                "id": "R2-L14",
                "relation": "long_time_series + dated_event_windows -> comparative_response",
                "layout_dna": "主折线/柱图 + 事件窗口 + 情景表",
                "source": "rank2 deck slide 20",
            },
        )

        self.assertIn("APPROVED VISUAL DESIGN DRAFT — PRIMARY LAYOUT AUTHORITY", prompt)
        self.assertIn("DESIGN UNIQUE LAYOUT", prompt)
        self.assertIn("EVIDENCE UNIQUE VALUE 18.85%", prompt)
        self.assertIn("CONTENT UNIQUE ORDER", prompt)
        self.assertIn("R2-L14", prompt)
        self.assertIn("STYLE TOKENS ONLY", prompt)
        self.assertIn("KaiTi", prompt)
        self.assertIn("Arial", prompt)

    def test_dynamic_reference_palette_is_a_hard_constraint(self):
        prompt = compile_effect_image_prompt(
            {"title": "结论", "objective": "目标"},
            "content",
            "evidence",
            "design",
            {
                "style_prompt": "red reference",
                "palette": {"roles": {"primary": "B42025", "support": "D97706", "background": "FFFDF7"}},
                "hard_constraints": {
                    "policy": "dynamic_from_core_reference",
                    "palette": {"allowed_hex": ["B42025", "D97706", "FFFDF7"]},
                },
            },
        )
        self.assertIn("HARD PROJECT STYLE CONSTRAINTS", prompt)
        self.assertIn("dynamic_from_core_reference", prompt)
        self.assertIn("B42025", prompt)
        self.assertIn("Do not substitute a generic blue", prompt)


if __name__ == "__main__":
    unittest.main()
