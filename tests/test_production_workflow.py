import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.production_workflow import (
    ProductionWorkflowError,
    approve_deck,
    approve_page,
    approve_image,
    generate_page,
    initialize_production_run,
    prepare_page,
    validate_deck_contract,
)


def sample_parsed() -> dict:
    return {
        "source_path": "C:/reports/sample.md",
        "source_name": "sample.md",
        "format": "md",
        "block_count": 4,
        "blocks": [
            {"id": "b0001", "type": "heading", "level": 1, "text": "市场判断"},
            {"id": "b0002", "type": "paragraph", "text": "市场增长12%，但竞争分化明显。"},
            {"id": "b0003", "type": "heading", "level": 1, "text": "行动建议"},
            {"id": "b0004", "type": "paragraph", "text": "优先推进高确定性客户并控制风险。"},
        ],
    }


def sample_style() -> dict:
    return {
        "template_name": "sample.pptx",
        "canvas": {"width_inches": 13.333, "height_inches": 7.5, "aspect_ratio": "16:9"},
        "palette": {"roles": {"primary": "183A59", "support": "2F80ED", "body": "111827", "background": "FFFFFF"}},
        "hard_constraints": {
            "policy": "dynamic_from_core_reference",
            "palette": {
                "allowed_hex": ["183A59", "2F80ED", "111827", "FFFFFF"],
                "nearest_color_distance": 58,
                "max_unapproved_accent_share": 0.10,
            },
        },
        "typography": {
            "title": {"font_family": "KaiTi", "size_pt": 28},
            "body": {"font_family": "KaiTi", "size_pt": 14},
            "caption": {"font_family": "Arial", "size_pt": 8},
        },
    }


def sample_ai_contract() -> dict:
    return {
        "schema_version": "2.0",
        "audience": "内部决策者",
        "purpose": "形成判断并支持行动",
        "communication_job": "让决策者理解市场判断并采取行动",
        "central_thesis": "增长与分化要求聚焦高确定性客户",
        "storyline": "市场判断 → 行动建议",
        "major_restructure": True,
        "restructure_summary": "把市场证据和行动建议重组为两步逻辑",
        "alternatives_considered": ["按原文", "判断到行动"],
        "pages": [
            {
                "page_number": 1,
                "title": "市场增长，但竞争分化加剧",
                "page_conclusion": "市场增长12%，但竞争分化明显。",
                "narrative_role": "claim_and_evidence",
                "narrative_question": "市场发生了什么？",
                "transition_from_previous": "开篇",
                "source_block_ids": ["b0001", "b0002"],
                "supporting_points": ["市场增长12%", "竞争分化明显"],
                "data_points": ["12%"],
                "semantic_relationship": "market evidence -> judgment",
                "pagination_rationale": "两个来源共同支持市场判断",
                "reorganization_notes": "把标题和证据合并",
            },
            {
                "page_number": 2,
                "title": "优先高确定性客户并控制风险",
                "page_conclusion": "优先推进高确定性客户并控制风险。",
                "narrative_role": "implication",
                "narrative_question": "下一步怎么做？",
                "transition_from_previous": "由判断进入行动",
                "source_block_ids": ["b0003", "b0004"],
                "supporting_points": ["优先高确定性客户", "控制风险"],
                "data_points": [],
                "semantic_relationship": "judgment -> action",
                "pagination_rationale": "行动建议收束全文",
                "reorganization_notes": "将行动内容集中收束",
            },
        ],
        "omitted_blocks": [],
        "allowed_reused_source_block_ids": [],
    }


def sample_config() -> dict:
    return {
        "narrative_ai": {
            "provider": "fixture",
            "fixture_contract": sample_ai_contract(),
            "target_page_count": 2,
        }
    }


def sample_project_brief() -> dict:
    return {
        "deck_type": "汇报型",
        "standalone_readability": "需要在没有讲解时基本可读",
        "audience": "内部决策者",
        "purpose": "形成判断并支持行动",
        "desired_decision": "确定下一步重点客户",
        "communication_job": "让决策者理解市场判断并采取行动",
        "core_conclusion": "增长与分化要求聚焦高确定性客户",
    }


class ProductionWorkflowTests(unittest.TestCase):
    def test_prepare_stops_without_ai_and_does_not_create_heuristic_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            config = {
                "narrative_ai": {
                    "provider": "deepseek_chat_completions",
                    "model": "test-model",
                }
            }
            with patch.dict(os.environ, {}, clear=True):
                result = initialize_production_run(
                    output,
                    sample_parsed(),
                    "C:/templates/sample.pptx",
                    sample_style(),
                    config,
                )
            self.assertEqual(result["status"], "narrative_ai_required")
            self.assertFalse((output / "content_map" / "deck_contract.json").exists())
            self.assertTrue((output / "content_map" / "narrative_ai_prompt.txt").exists())

    def test_prepare_creates_contracts_without_generating_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = initialize_production_run(output, sample_parsed(), "C:/templates/sample.pptx", sample_style(), sample_config())

            self.assertTrue((output / "content_map" / "deck_contract.json").exists())
            self.assertTrue((output / "content_map" / "full_report_content_map.txt").exists())
            self.assertTrue((output / "content_map" / "narrative_source_payload.json").exists())
            self.assertTrue((output / "content_map" / "restructure_report.json").exists())
            self.assertTrue(list((output / "page_structures").glob("page_*.json")))
            self.assertTrue((output / "workflow_state.json").exists())
            self.assertFalse(list((output / "slide_images").glob("*.png")))
            self.assertEqual(result["status"], "prepared")

    def test_prepare_writes_project_brief_sanitized_copy_and_title_readthrough(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            parsed = sample_parsed()
            parsed["blocks"][1]["text"] = "市场增长12%。旧口径为15%〔待核实〕。竞争分化明显。"
            config = sample_config()
            config["project_brief"] = sample_project_brief()
            config["narrative_ai"]["excluded_content_patterns"] = ["〔待核实"]

            initialize_production_run(output, parsed, "C:/templates/sample.pptx", sample_style(), config)

            raw_text = (output / "parsed_content" / "parsed_blocks_raw.json").read_text(encoding="utf-8")
            clean_text = (output / "parsed_content" / "parsed_blocks.json").read_text(encoding="utf-8")
            prompt = (output / "content_map" / "narrative_ai_prompt.txt").read_text(encoding="utf-8")
            contract = json.loads((output / "content_map" / "deck_contract.json").read_text(encoding="utf-8"))
            self.assertIn("〔待核实〕", raw_text)
            self.assertNotIn("〔待核实〕", clean_text)
            self.assertIn("项目简报", prompt)
            self.assertEqual(contract["project_brief"]["deck_type"], "汇报型")
            self.assertTrue((output / "content_map" / "narrative_exclusions.json").exists())
            self.assertIn("Continuous readthrough", (output / "content_map" / "storyline_readthrough.txt").read_text(encoding="utf-8"))

    def test_deck_validation_requires_complete_unique_source_coverage(self):
        parsed = sample_parsed()
        contract = {
            "pages": [
                {"page_number": 1, "title": "判断", "page_conclusion": "市场增长但竞争分化。", "source_block_ids": ["b0001", "b0002"]},
                {"page_number": 2, "title": "建议", "page_conclusion": "优先高确定性客户。", "source_block_ids": ["b0002", "b0003"]},
            ],
            "omitted_blocks": [],
            "allowed_reused_source_block_ids": [],
        }
        errors = validate_deck_contract(contract, parsed)
        self.assertTrue(any("duplicate source assignment" in error for error in errors))
        self.assertTrue(any("unassigned source block: b0004" in error for error in errors))

    def test_page_approval_requires_deck_approval_and_valid_design_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            initialize_production_run(output, sample_parsed(), "C:/templates/sample.pptx", sample_style(), sample_config())

            with self.assertRaises(ProductionWorkflowError):
                prepare_page(output, 1)

            approve_deck(output)
            page_result = prepare_page(output, 1)
            self.assertEqual(page_result["page_number"], 1)
            self.assertTrue(Path(page_result["design_draft"]).exists())
            self.assertTrue(Path(page_result["page_structure"]).exists())
            self.assertTrue(Path(page_result["mechanism_match"]).exists())
            match_record = json.loads(Path(page_result["mechanism_match"]).read_text(encoding="utf-8"))
            self.assertEqual(match_record["page_structure"]["sizing"], "adaptive")
            self.assertIn("selected_card", match_record)
            design_text = Path(page_result["design_draft"]).read_text(encoding="utf-8")
            self.assertIn("Excellent-PPT library match", design_text)
            self.assertIn("b0001", design_text)

            approval = approve_page(output, 1)
            self.assertEqual(approval["status"], "approved")

            state = json.loads((output / "workflow_state.json").read_text(encoding="utf-8"))
            self.assertIsNotNone(state["pages"]["1"]["page_approved_at"])

    def test_generation_is_one_page_and_prompt_only_is_a_successful_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            initialize_production_run(output, sample_parsed(), "C:/templates/sample.pptx", sample_style(), sample_config())
            approve_deck(output)
            prepare_page(output, 1)

            with self.assertRaises(ProductionWorkflowError):
                generate_page(output, 1, "prompt_only")

            approve_page(output, 1)
            result = generate_page(output, 1, "prompt_only")
            self.assertEqual(result["status"], "prompt_ready")
            self.assertTrue((output / "slide_images" / "imagegen_jobs.jsonl").exists())
            compiled_path = output / "slide_images" / "page_01_compiled_prompt.txt"
            self.assertTrue(compiled_path.exists())
            compiled = compiled_path.read_text(encoding="utf-8")
            self.assertIn("APPROVED VISUAL DESIGN DRAFT", compiled)
            self.assertIn("APPROVED EVIDENCE SPECIFICATION", compiled)
            self.assertIn("REUSABLE LIBRARY MECHANISM", compiled)
            self.assertEqual(result["compiled_prompt"], str(compiled_path))
            self.assertFalse((output / "slide_images" / "slide_01.png").exists())

    def test_changed_page_contract_invalidates_approval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            initialize_production_run(output, sample_parsed(), "C:/templates/sample.pptx", sample_style(), sample_config())
            approve_deck(output)
            prepare_page(output, 1)
            approve_page(output, 1)

            design_path = output / "design_drafts" / "page_01.txt"
            design_path.write_text(design_path.read_text(encoding="utf-8") + "\nChanged after approval.\n", encoding="utf-8")
            with self.assertRaises(ProductionWorkflowError):
                generate_page(output, 1, "prompt_only")

    def test_changed_deck_contract_invalidates_all_page_approvals(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            initialize_production_run(output, sample_parsed(), "C:/templates/sample.pptx", sample_style(), sample_config())
            approve_deck(output)
            prepare_page(output, 1)
            approve_page(output, 1)

            contract_path = output / "content_map" / "deck_contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["purpose"] = "Changed purpose after the first approval."
            contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
            approve_deck(output)

            with self.assertRaises(ProductionWorkflowError):
                generate_page(output, 1, "prompt_only")

    def test_image_approval_checks_reference_aspect_ratio(self):
        from PIL import Image, ImageDraw

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            initialize_production_run(output, sample_parsed(), "C:/templates/sample.pptx", sample_style(), sample_config())
            approve_deck(output)
            prepare_page(output, 1)
            approve_page(output, 1)

            image_path = output / "slide_images" / "slide_01.png"
            valid = Image.new("RGB", (1600, 900), "white")
            draw = ImageDraw.Draw(valid)
            draw.rectangle((120, 120, 1480, 220), fill="#183A59")
            draw.rectangle((120, 280, 760, 760), fill="#2F80ED")
            draw.rectangle((820, 280, 1480, 760), outline="#183A59", width=12)
            valid.save(image_path)
            approval = approve_image(output, 1)
            self.assertEqual(approval["status"], "approved")
            self.assertTrue(Path(approval["visual_qa"]).exists())

            invalid_ratio = valid.resize((1600, 1000))
            invalid_ratio.save(image_path)
            with self.assertRaises(ProductionWorkflowError):
                approve_image(output, 1)

    def test_image_approval_rejects_blank_or_off_palette_images(self):
        from PIL import Image, ImageDraw

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            initialize_production_run(output, sample_parsed(), "C:/templates/sample.pptx", sample_style(), sample_config())
            approve_deck(output)
            prepare_page(output, 1)
            approve_page(output, 1)
            image_path = output / "slide_images" / "slide_01.png"

            Image.new("RGB", (1600, 900), "white").save(image_path)
            with self.assertRaisesRegex(ProductionWorkflowError, "blank or too sparse"):
                approve_image(output, 1)

            off_palette = Image.new("RGB", (1600, 900), "white")
            draw = ImageDraw.Draw(off_palette)
            draw.rectangle((100, 100, 1500, 800), fill="#16A34A")
            off_palette.save(image_path)
            with self.assertRaisesRegex(ProductionWorkflowError, "unapproved_accent_share"):
                approve_image(output, 1)


if __name__ == "__main__":
    unittest.main()
