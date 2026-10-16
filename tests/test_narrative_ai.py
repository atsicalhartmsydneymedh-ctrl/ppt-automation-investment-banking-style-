import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from src.narrative_ai import (
    NarrativeAIUnavailable,
    build_ai_narrative_prompt,
    build_order_neutral_source_payload,
    build_restructure_report,
    generate_ai_deck_contract,
    sanitize_parsed_for_narrative,
    validate_ai_deck_contract,
)


def parsed_report() -> dict:
    return {
        "source_name": "report.docx",
        "blocks": [
            {"id": "b0001", "type": "heading", "level": 1, "page": 1, "text": "原始第一章"},
            {"id": "b0002", "type": "paragraph", "page": 1, "text": "证据甲支持比较结论。"},
            {"id": "b0003", "type": "table", "page": 8, "rows": [["对象", "数值"], ["A", "12%"]]},
            {"id": "b0004", "type": "paragraph", "page": 9, "text": "行动建议来自报告末尾。"},
        ],
    }


def valid_contract() -> dict:
    return {
        "schema_version": "2.0",
        "audience": "决策者",
        "purpose": "解释并支持决策",
        "communication_job": "让决策者理解比较结论并采取行动",
        "central_thesis": "证据甲和数据共同支持行动建议",
        "storyline": "比较结论 → 数据验证 → 行动建议",
        "major_restructure": True,
        "restructure_summary": "把报告首尾证据重新组合",
        "alternatives_considered": ["按对象", "按问题到行动"],
        "pages": [
            {
                "page_number": 1,
                "title": "证据与数据共同支持比较结论",
                "page_conclusion": "证据甲与12%的数据共同支持比较判断。",
                "narrative_role": "claim_and_evidence",
                "narrative_question": "结论是否成立？",
                "transition_from_previous": "开篇",
                "source_block_ids": ["b0001", "b0002", "b0003"],
                "supporting_points": ["证据甲", "A为12%"],
                "data_points": ["12%"],
                "semantic_relationship": "claim + evidence -> conclusion",
                "pagination_rationale": "三项内容服务同一判断",
                "reorganization_notes": "组合原报告前部和末尾表格",
            },
            {
                "page_number": 2,
                "title": "比较结论转化为行动建议",
                "page_conclusion": "应根据比较结论采取行动。",
                "narrative_role": "implication",
                "narrative_question": "下一步做什么？",
                "transition_from_previous": "由证据进入行动",
                "source_block_ids": ["b0004"],
                "supporting_points": ["采取行动"],
                "data_points": [],
                "semantic_relationship": "conclusion -> action",
                "pagination_rationale": "行动单独收束",
                "reorganization_notes": "将末尾建议作为收束",
            },
        ],
        "omitted_blocks": [],
        "allowed_reused_source_block_ids": [],
    }


class NarrativeAITests(unittest.TestCase):
    def test_source_payload_excludes_format_and_original_order_metadata(self):
        payload = build_order_neutral_source_payload(parsed_report())
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn('"type"', serialized)
        self.assertNotIn('"level"', serialized)
        self.assertNotIn('"page"', serialized)
        self.assertIn("ordering_policy", payload)
        self.assertTrue(all(record["source_id"].startswith("s_") for record in payload["source_records"]))
        self.assertNotIn("b0001", serialized)

    def test_project_brief_is_injected_as_an_immutable_pagination_constraint(self):
        payload = build_order_neutral_source_payload(parsed_report())
        brief = {
            "deck_type": "汇报型",
            "standalone_readability": "基本可独立阅读",
            "audience": "决策者",
            "purpose": "解释并支持决策",
            "communication_job": "让决策者理解比较结论并采取行动",
            "core_conclusion": "证据甲和数据共同支持行动建议",
        }
        prompt = build_ai_narrative_prompt(payload, {"project_brief": brief, "target_page_count": 2})
        self.assertIn("项目简报", prompt)
        self.assertIn("基本可独立阅读", prompt)
        self.assertIn("不得自行改写", prompt)

    def test_sanitized_copy_removes_only_flagged_fragments_and_keeps_original_unchanged(self):
        parsed = parsed_report()
        parsed["blocks"][1]["text"] = "证据甲已经验证。旧口径为15%〔待核实〕。结论仍然成立。"
        sanitized, exclusions = sanitize_parsed_for_narrative(parsed, ["〔待核实"])
        clean_text = next(block["text"] for block in sanitized["blocks"] if block["id"] == "b0002")
        self.assertEqual(clean_text, "证据甲已经验证。结论仍然成立。")
        self.assertIn("〔待核实〕", parsed["blocks"][1]["text"])
        self.assertEqual(exclusions[0]["block_id"], "b0002")
        self.assertEqual(exclusions[0]["mode"], "partial")

    def test_contract_validator_requires_complete_unique_coverage(self):
        contract = valid_contract()
        contract["pages"][0]["source_block_ids"].remove("b0003")
        errors = validate_ai_deck_contract(contract, parsed_report(), {"target_page_count": 2})
        self.assertIn("unassigned source id: b0003", errors)

    def test_contract_validator_enforces_required_and_additional_schema_fields(self):
        contract = valid_contract()
        del contract["audience"]
        contract["unexpected"] = "not allowed"
        errors = validate_ai_deck_contract(contract, parsed_report(), {"target_page_count": 2})
        self.assertIn("$ is missing required field: audience", errors)
        self.assertIn("$ contains unsupported field: unexpected", errors)

    def test_contract_validator_requires_exact_project_brief_alignment(self):
        contract = valid_contract()
        brief = {
            "audience": "另一个观众",
            "purpose": contract["purpose"],
            "communication_job": contract["communication_job"],
            "core_conclusion": contract["central_thesis"],
        }
        errors = validate_ai_deck_contract(contract, parsed_report(), {"project_brief": brief})
        self.assertIn("audience must exactly match the approved project brief", errors)

    def test_fixture_provider_returns_strictly_valid_contract(self):
        result = generate_ai_deck_contract(
            parsed_report(),
            {"provider": "fixture", "fixture_contract": valid_contract(), "target_page_count": 2},
        )
        self.assertEqual(result.contract["pages"][0]["source_block_ids"], ["b0001", "b0002", "b0003"])

    def test_deepseek_provider_fails_closed_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(NarrativeAIUnavailable):
                generate_ai_deck_contract(
                    parsed_report(),
                    {"provider": "deepseek_chat_completions", "model": "test-model"},
                )

    def test_paratera_kimi_provider_uses_openai_json_output(self):
        source_payload = build_order_neutral_source_payload(parsed_report())
        alias_by_content = {record["content"]: record["source_id"] for record in source_payload["source_records"]}
        content_by_id = {
            "b0001": "原始第一章",
            "b0002": "证据甲支持比较结论。",
            "b0003": "对象 | 数值\nA | 12%",
            "b0004": "行动建议来自报告末尾。",
        }
        contract = valid_contract()
        for page in contract["pages"]:
            page["source_block_ids"] = [alias_by_content[content_by_id[value]] for value in page["source_block_ids"]]
        seen = {}

        def transport(request_payload, headers):
            seen["payload"] = request_payload
            seen["authorization"] = headers["Authorization"]
            return {
                "choices": [
                    {"message": {"role": "assistant", "content": json.dumps(contract, ensure_ascii=False)}}
                ]
            }

        with patch.dict(os.environ, {"PARATERA_API_KEY": "secret-for-test"}, clear=True):
            result = generate_ai_deck_contract(
                parsed_report(),
                {
                    "provider": "openai_chat_completions",
                    "provider_name": "Paratera Kimi K3",
                    "model": "Kimi-K3",
                    "target_page_count": 2,
                    "reasoning_effort": "high",
                },
                transport=transport,
            )

        self.assertEqual(result.contract["pages"][1]["source_block_ids"], ["b0004"])
        self.assertEqual(seen["payload"]["model"], "Kimi-K3")
        self.assertEqual(seen["payload"]["response_format"], {"type": "json_object"})
        self.assertEqual(seen["payload"]["reasoning_effort"], "high")
        self.assertNotIn("temperature", seen["payload"])
        self.assertNotIn("thinking", seen["payload"])
        self.assertEqual(seen["authorization"], "Bearer secret-for-test")

    def test_default_config_routes_pagination_to_deepseek(self):
        config = json.loads(Path("config/defaults.json").read_text(encoding="utf-8"))
        settings = config["narrative_ai"]
        self.assertEqual(settings["provider"], "deepseek_chat_completions")
        self.assertEqual(settings["model"], "deepseek-v4-pro")
        self.assertEqual(settings["api_key_env"], "DEEPSEEK_API_KEY")
        self.assertEqual(settings["endpoint"], "https://api.deepseek.com/chat/completions")

    def test_deepseek_provider_uses_json_output_and_restores_source_ids(self):
        payload = build_order_neutral_source_payload(parsed_report())
        aliases = [record["source_id"] for record in payload["source_records"]]
        contract = valid_contract()
        original_ids = ["b0001", "b0002", "b0003", "b0004"]
        alias_by_original = {
            original: next(
                record["source_id"]
                for record in payload["source_records"]
                if record["content"] == next(
                    item["text"] if item.get("type") != "table" else "\n".join(" | ".join(row) for row in item["rows"])
                    for item in parsed_report()["blocks"]
                    if item["id"] == original
                )
            )
            for original in original_ids
        }
        for page in contract["pages"]:
            page["source_block_ids"] = [alias_by_original[value] for value in page["source_block_ids"]]
        seen = {}

        def transport(request_payload, headers):
            seen["payload"] = request_payload
            seen["authorization"] = headers["Authorization"]
            return {
                "choices": [
                    {"message": {"role": "assistant", "content": json.dumps(contract, ensure_ascii=False)}}
                ]
            }

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret-for-test"}, clear=True):
            result = generate_ai_deck_contract(
                parsed_report(),
                {
                    "provider": "deepseek_chat_completions",
                    "model": "test-model",
                    "target_page_count": 2,
                },
                transport=transport,
            )
        self.assertEqual(result.contract["pages"][0]["source_block_ids"], ["b0001", "b0002", "b0003"])
        self.assertEqual(seen["payload"]["response_format"]["type"], "json_object")
        self.assertFalse(seen["payload"]["stream"])
        self.assertIn("JSON Schema", seen["payload"]["messages"][1]["content"])
        self.assertIn('"pages"', seen["payload"]["messages"][1]["content"])
        self.assertEqual(seen["authorization"], "Bearer secret-for-test")

    def test_deepseek_provider_retries_an_empty_json_response_once(self):
        payload = build_order_neutral_source_payload(parsed_report())
        aliases_by_content = {record["content"]: record["source_id"] for record in payload["source_records"]}
        contract = valid_contract()
        source_content = {
            "b0001": "原始第一章",
            "b0002": "证据甲支持比较结论。",
            "b0003": "对象 | 数值\nA | 12%",
            "b0004": "行动建议来自报告末尾。",
        }
        for page in contract["pages"]:
            page["source_block_ids"] = [aliases_by_content[source_content[value]] for value in page["source_block_ids"]]
        calls = []

        def transport(request_payload, _headers):
            calls.append(request_payload["messages"][-1]["content"])
            if len(calls) == 1:
                return {"choices": [{"message": {"role": "assistant", "content": ""}}]}
            return {"choices": [{"message": {"role": "assistant", "content": json.dumps(contract, ensure_ascii=False)}}]}

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret-for-test"}, clear=True):
            result = generate_ai_deck_contract(
                parsed_report(),
                {"provider": "deepseek_chat_completions", "model": "test-model", "target_page_count": 2},
                transport=transport,
            )
        self.assertEqual(len(calls), 2)
        self.assertIn("上一次响应为空", calls[1])
        self.assertEqual(result.contract["pages"][1]["source_block_ids"], ["b0004"])

    def test_deepseek_strict_tool_call_uses_beta_schema_and_parses_arguments(self):
        source_payload = build_order_neutral_source_payload(parsed_report())
        alias_by_content = {record["content"]: record["source_id"] for record in source_payload["source_records"]}
        content_by_id = {
            "b0001": "原始第一章",
            "b0002": "证据甲支持比较结论。",
            "b0003": "对象 | 数值\nA | 12%",
            "b0004": "行动建议来自报告末尾。",
        }
        contract = valid_contract()
        for page in contract["pages"]:
            page["source_block_ids"] = [alias_by_content[content_by_id[value]] for value in page["source_block_ids"]]
        contract["omitted_blocks"] = [
            {"block_id": contract["pages"][0]["source_block_ids"][0], "reason": "test overlap"}
        ]
        seen = {}

        def transport(request_payload, _headers):
            seen["payload"] = request_payload
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "submit_narrative_deck_contract",
                                        "arguments": json.dumps(contract, ensure_ascii=False),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret-for-test"}, clear=True):
            result = generate_ai_deck_contract(
                parsed_report(),
                {
                    "provider": "deepseek_chat_completions",
                    "model": "test-model",
                    "target_page_count": 2,
                    "structured_output_mode": "strict_tool_call",
                    "thinking": "disabled",
                    "source_id_enum": True,
                },
                transport=transport,
            )
        function = seen["payload"]["tools"][0]["function"]
        self.assertTrue(function["strict"])
        self.assertNotIn("minLength", json.dumps(function["parameters"]))
        allowed_ids = function["parameters"]["properties"]["pages"]["items"]["properties"]["source_block_ids"]["items"]["enum"]
        self.assertEqual(len(allowed_ids), 4)
        self.assertNotIn("response_format", seen["payload"])
        self.assertEqual(result.contract["pages"][0]["source_block_ids"], ["b0001", "b0002", "b0003"])
        self.assertEqual(result.contract["omitted_blocks"], [])

    def test_restructure_report_detects_cross_source_regrouping(self):
        report = build_restructure_report(valid_contract(), parsed_report())
        self.assertTrue(report["major_restructure"])
        self.assertIn("较大重组", report["user_notice"])


if __name__ == "__main__":
    unittest.main()
