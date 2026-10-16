import unittest

from src.design_draft_validator import REQUIRED_SECTIONS, validate_design_draft


def complete_draft() -> str:
    bodies = {
        "Page conclusion": "A conclusion that the page proves with evidence.",
        "Semantic relationship": "A three-way comparison under one shared schema.",
        "Visual argument": "The primary visual is a shared-scale dot plot that makes the divergence visible.",
        "Canvas": "1600 x 1132 pixels, 1.41:1.",
        "Regions": "Title y=50-103; primary plot x=60-1050; evidence rail x=1100-1540.",
        "Evidence mapping": "The plot carries all comparable values; the evidence rail explains three exceptions.",
        "Visual encoding": "Shared 0-30% axis, percent units, direct labels, and annotations on three outliers.",
        "Hierarchy and reading path": "Primary: comparison plot. Secondary: evidence rail. Reading: title to plot to implication.",
        "Typography": "KaiTi for Chinese; Arial for English, numbers, and punctuation; fixed sizes.",
        "Style": "White background, blue rules, restrained pale fills, no gradients.",
        "Anti-template constraints": "Do not replace the plot with equal cards or a generic table.",
        "Approval checklist": "Coverage PASS; semantics PASS; encoding PASS; hierarchy PASS; density PASS.",
    }
    return "\n\n".join(f"{heading}\n- {bodies[heading]}" for heading in REQUIRED_SECTIONS)


class DesignDraftValidatorTests(unittest.TestCase):
    def test_complete_draft_passes(self):
        self.assertEqual(validate_design_draft(complete_draft()), [])

    def test_style_summary_fails(self):
        summary = "Canvas\n- 1600 x 1132\n\nTypography\n- KaiTi and Arial\n\nStyle\n- High density blue style"
        errors = validate_design_draft(summary)
        self.assertTrue(any("Visual argument" in error for error in errors))
        self.assertTrue(any("too short" in error for error in errors))

    def test_layout_revision_cannot_change_design_core(self):
        base = complete_draft()
        revised = base.replace(
            "The primary visual is a shared-scale dot plot that makes the divergence visible.",
            "The primary visual is three equal cards.",
        )
        errors = validate_design_draft(revised, base)
        self.assertTrue(any("Visual argument" in error for error in errors))

    def test_unresolved_placeholder_fails(self):
        draft = complete_draft().replace(
            "A conclusion that the page proves with evidence.",
            "TODO: replace with the approved conclusion.",
        )
        errors = validate_design_draft(draft)
        self.assertTrue(any("unresolved placeholder" in error for error in errors))

    def test_required_evidence_and_source_coverage_are_enforced(self):
        draft = complete_draft().replace(
            "The plot carries all comparable values; the evidence rail explains three exceptions.",
            "Required item A; 18.85%; source b0001.",
        )
        self.assertEqual(
            validate_design_draft(
                draft,
                required_evidence=["Required item A"],
                required_data_points=["18.85%"],
                required_source_block_ids=["b0001"],
            ),
            [],
        )
        errors = validate_design_draft(
            draft,
            required_evidence=["Required item B"],
            required_data_points=["23.01%"],
            required_source_block_ids=["b0002"],
        )
        self.assertTrue(any("supporting evidence" in error for error in errors))
        self.assertTrue(any("quantitative evidence" in error for error in errors))
        self.assertTrue(any("source coverage" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
