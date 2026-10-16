import unittest

from src.narrative_planner import build_narrative_planning_prompt, create_narrative_plan


def sample_report() -> dict:
    return {
        "source_name": "专题报告.docx",
        "blocks": [
            {"id": "b1", "type": "heading", "level": 1, "text": "行动建议"},
            {"id": "b2", "type": "paragraph", "text": "建议优先配置高确定性方向。"},
            {"id": "b3", "type": "heading", "level": 1, "text": "背景与定义"},
            {"id": "b4", "type": "paragraph", "text": "四类指数的编制目标并不相同。"},
            {"id": "b5", "type": "heading", "level": 1, "text": "核心对比"},
            {"id": "b6", "type": "table", "rows": [["指数", "收益", "波动"], ["A", "12%", "18%"], ["B", "8%", "11%"]]},
            {"id": "b7", "type": "heading", "level": 1, "text": "参考文献"},
            {"id": "b8", "type": "paragraph", "text": "https://example.com/data.pdf"},
        ],
    }


class NarrativePlannerTests(unittest.TestCase):
    def test_orders_by_story_role_and_preserves_source_coverage(self):
        result = create_narrative_plan(sample_report())
        roles = [page["narrative_role"] for page in result["pages"]]
        self.assertLess(roles.index("foundation"), roles.index("comparison"))
        self.assertLess(roles.index("comparison"), roles.index("implication"))
        assigned = {block_id for page in result["pages"] for block_id in page["source_block_ids"]}
        omitted = {record["block_id"] for record in result["omitted_blocks"]}
        self.assertEqual(assigned | omitted, {f"b{index}" for index in range(1, 9)})
        self.assertFalse(assigned & omitted)

    def test_page_contract_records_narrative_basis_and_evidence_load(self):
        result = create_narrative_plan(sample_report())
        self.assertIn("narrative role", result["pagination_basis"])
        for page in result["pages"]:
            self.assertGreater(page["evidence_load"], 0)
            self.assertTrue(page["narrative_question"])
            self.assertTrue(page["pagination_rationale"])

    def test_prompt_explicitly_forbids_character_count_pagination(self):
        plan = create_narrative_plan(sample_report())
        prompt = build_narrative_planning_prompt(sample_report(), plan)
        self.assertIn("不得按字符数", prompt)
        self.assertIn("完整来源清单", prompt)
        self.assertIn("deck_contract JSON", prompt)

    def test_numbered_paragraph_headings_work_without_word_heading_styles(self):
        report = {
            "source_name": "unstyled.docx",
            "blocks": [
                {"id": "b1", "type": "paragraph", "text": "专题标题"},
                {"id": "b2", "type": "paragraph", "text": "一、核心结论"},
                {"id": "b3", "type": "paragraph", "text": "结论证据。"},
                {"id": "b4", "type": "paragraph", "text": "二、结构对比"},
                {"id": "b5", "type": "paragraph", "text": "对象A：结构不同。"},
                {"id": "b6", "type": "paragraph", "text": "三、表现数据"},
                {"id": "b7", "type": "paragraph", "text": "数据支持判断。"},
                {"id": "b8", "type": "paragraph", "text": "四、行动建议"},
                {"id": "b9", "type": "paragraph", "text": "建议采取行动。"},
                {"id": "b10", "type": "table", "rows": [["结构指标", "对象A"], ["规则", "不同"]]},
            ],
        }
        result = create_narrative_plan(report)
        self.assertEqual(len(result["pages"]), 4)
        self.assertEqual(result["pages"][0]["narrative_role"], "opening_synthesis")
        comparison_page = next(page for page in result["pages"] if "结构对比" in page["title"])
        self.assertIn("b10", comparison_page["source_block_ids"])


if __name__ == "__main__":
    unittest.main()
