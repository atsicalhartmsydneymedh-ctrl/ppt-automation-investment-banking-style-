from __future__ import annotations

import hashlib
import json
import os
import copy
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib import error as url_error
from urllib import request as url_request


class NarrativeAIError(RuntimeError):
    pass


class NarrativeAIUnavailable(NarrativeAIError):
    pass


Transport = Callable[[dict[str, Any], dict[str, str]], dict[str, Any]]


@dataclass
class NarrativeAIResult:
    contract: dict[str, Any]
    source_payload: dict[str, Any]
    prompt: str
    schema: dict[str, Any]
    responses: list[dict[str, Any]]


def build_order_neutral_source_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    """Expose content and trace IDs, but no format, heading level, page, or source order."""
    records = []
    for block in parsed.get("blocks", []):
        original_id = str(block.get("id") or "").strip()
        content = _block_content(block) or "[empty source record]"
        if not original_id:
            continue
        source_id = _source_alias(original_id, content)
        records.append(
            {
                "source_id": source_id,
                "content": content,
                "order_neutral_key": hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
            }
        )
    records.sort(key=lambda record: (record["order_neutral_key"], record["source_id"]))
    return {
        "source_name": parsed.get("source_name"),
        "source_count": len(records),
        "ordering_policy": "semantic_only; opaque source aliases are hash-sorted and original order is unavailable",
        "source_records": records,
    }


def sanitize_parsed_for_narrative(
    parsed: dict[str, Any],
    excluded_content_patterns: list[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Create a PPT-only source copy with flagged fragments removed; never mutate the report parse."""
    patterns = [str(value).strip().lower() for value in excluded_content_patterns or [] if str(value).strip()]
    sanitized = copy.deepcopy(parsed)
    if not patterns:
        return sanitized, []
    blocks: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for original in sanitized.get("blocks", []):
        block = copy.deepcopy(original)
        removed: list[str] = []
        block_type = block.get("type")
        if block_type == "table":
            kept_rows = []
            for row in block.get("rows", []):
                row_text = " | ".join(str(cell).strip() for cell in row)
                if _matches_exclusion(row_text, patterns):
                    removed.append(row_text)
                else:
                    kept_rows.append(row)
            block["rows"] = kept_rows
        elif block_type == "list":
            kept_items = []
            for item in block.get("items", []):
                item_text = str(item).strip()
                if _matches_exclusion(item_text, patterns):
                    removed.append(item_text)
                elif item_text:
                    kept_items.append(item)
            block["items"] = kept_items
        else:
            kept_fragments = []
            for fragment in re.split(r"(?<=[。！？；])|(?:\r?\n)+", str(block.get("text", ""))):
                fragment = fragment.strip()
                if not fragment:
                    continue
                if _matches_exclusion(fragment, patterns):
                    removed.append(fragment)
                else:
                    kept_fragments.append(fragment)
            block["text"] = "".join(kept_fragments)
        if removed:
            exclusions.append(
                {
                    "block_id": block.get("id"),
                    "mode": "partial" if _block_content(block) else "full",
                    "reason": "matched the configured PPT-only exclusion policy",
                    "removed_fragments": removed,
                }
            )
        if _block_content(block):
            blocks.append(block)
    sanitized["blocks"] = blocks
    sanitized["block_count"] = len(blocks)
    sanitized["sanitization_policy"] = {
        "scope": "ppt_generation_copy_only",
        "original_report_unchanged": True,
        "excluded_content_patterns": excluded_content_patterns or [],
        "affected_block_count": len(exclusions),
    }
    return sanitized, exclusions


def build_ai_narrative_prompt(
    source_payload: dict[str, Any],
    settings: dict[str, Any] | None = None,
) -> str:
    settings = settings or {}
    target = settings.get("target_page_count")
    page_instruction = (
        f"输出恰好 {target} 页。"
        if isinstance(target, int) and target > 0
        else f"根据论证需要决定页数，通常控制在 {settings.get('min_page_count', 4)}–{settings.get('max_page_count', 12)} 页。"
    )
    project_brief = settings.get("project_brief") if isinstance(settings.get("project_brief"), dict) else {}
    brief_section = ""
    if project_brief:
        brief_section = (
            "项目简报（人工确认的上位约束，不得自行改写）：\n"
            + json.dumps(project_brief, ensure_ascii=False, indent=2)
            + "\n其中audience、purpose、communication_job、core_conclusion必须原样映射到输出合同；"
            "页面密度和叙述方式必须符合deck_type与standalone_readability。\n\n"
        )
    return (
        "你是PPT内容总编。你的任务不是整理原报告目录，而是通读全部内容后重新组织一条完整、累进、可讲述的PPT逻辑线。\n\n"
        + brief_section
        + "关键规则：\n"
        "1. 输入记录已经打乱，且不提供标题格式、章节级别、页码或原始顺序。不得按source_id编号恢复或模仿原文顺序。\n"
        "2. 先判断观众最终应理解什么，再确定故事线；分页是故事线的结果。\n"
        "3. 可以把来自原报告不同位置的内容组合到同一页，也可以把原来相邻的内容拆开。\n"
        "4. 每页只承担一个叙事任务、回答一个问题、推出一个结论；标题必须是观众可直接理解的结论型标题。\n"
        "5. supporting_points必须是对来源内容的准确压缩，不得编造事实、数字、对象或因果。\n"
        "6. 所有source_id必须恰好出现一次：要么分配到一页，要么进入omitted_blocks并写明理由；只有列入allowed_reused_source_block_ids后才可跨页复用。\n"
        "7. 先考虑至少两条候选叙事线，选择完整性、连贯性、证据匹配和页间推进最好的方案。\n"
        "8. 如果新结构明显跨越并重组了原材料内容，major_restructure写true，并清楚说明重组逻辑。\n"
        "9. 此阶段只做内容与叙事，不选择PPT模板、颜色、图表、卡片或排版素材。\n"
        f"10. {page_instruction}\n\n"
        "全文语义记录：\n"
        + json.dumps(source_payload, ensure_ascii=False, indent=2)
    )


def deck_contract_schema() -> dict[str, Any]:
    string_array = {"type": "array", "items": {"type": "string"}}
    page = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "page_number",
            "title",
            "page_conclusion",
            "narrative_role",
            "narrative_question",
            "transition_from_previous",
            "source_block_ids",
            "supporting_points",
            "data_points",
            "semantic_relationship",
            "pagination_rationale",
            "reorganization_notes",
        ],
        "properties": {
            "page_number": {"type": "integer", "minimum": 1},
            "title": {"type": "string", "minLength": 1},
            "page_conclusion": {"type": "string", "minLength": 1},
            "narrative_role": {"type": "string", "minLength": 1},
            "narrative_question": {"type": "string", "minLength": 1},
            "transition_from_previous": {"type": "string"},
            "source_block_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "supporting_points": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "data_points": string_array,
            "semantic_relationship": {"type": "string", "minLength": 1},
            "pagination_rationale": {"type": "string", "minLength": 1},
            "reorganization_notes": {"type": "string"},
        },
    }
    omitted = {
        "type": "object",
        "additionalProperties": False,
        "required": ["block_id", "reason"],
        "properties": {
            "block_id": {"type": "string"},
            "reason": {"type": "string", "minLength": 1},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "audience",
            "purpose",
            "communication_job",
            "central_thesis",
            "storyline",
            "major_restructure",
            "restructure_summary",
            "alternatives_considered",
            "pages",
            "omitted_blocks",
            "allowed_reused_source_block_ids",
        ],
        "properties": {
            "schema_version": {"type": "string"},
            "audience": {"type": "string", "minLength": 1},
            "purpose": {"type": "string", "minLength": 1},
            "communication_job": {"type": "string", "minLength": 1},
            "central_thesis": {"type": "string", "minLength": 1},
            "storyline": {"type": "string", "minLength": 1},
            "major_restructure": {"type": "boolean"},
            "restructure_summary": {"type": "string", "minLength": 1},
            "alternatives_considered": string_array,
            "pages": {"type": "array", "items": page, "minItems": 1},
            "omitted_blocks": {"type": "array", "items": omitted},
            "allowed_reused_source_block_ids": string_array,
        },
    }


def generate_ai_deck_contract(
    parsed: dict[str, Any],
    settings: dict[str, Any],
    transport: Transport | None = None,
) -> NarrativeAIResult:
    source_payload = build_order_neutral_source_payload(parsed)
    prompt = build_ai_narrative_prompt(source_payload, settings)
    schema = deck_contract_schema()
    provider = settings.get("provider", "openai_chat_completions")

    if provider == "fixture":
        fixture = settings.get("fixture_contract")
        if not isinstance(fixture, dict):
            fixture_path = settings.get("fixture_path")
            if fixture_path:
                fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        if not isinstance(fixture, dict):
            raise NarrativeAIError("fixture provider requires fixture_contract or fixture_path")
        responses = [{"provider": "fixture", "output_text": json.dumps(fixture, ensure_ascii=False)}]
        contract = fixture
    elif provider in {"openai_chat_completions", "deepseek_chat_completions"}:
        alias_to_original = _alias_to_original_map(parsed)
        alias_parsed = {"blocks": [{"id": alias} for alias in alias_to_original]}
        provider_schema = (
            _schema_with_source_id_enum(schema, list(alias_to_original))
            if settings.get("source_id_enum", False)
            else schema
        )
        contract, responses = _generate_with_chat_completions(
            prompt,
            provider_schema,
            settings,
            transport,
            provider,
        )
        contract = _normalize_source_coverage_bookkeeping(
            contract,
            set(alias_to_original),
            bool(settings.get("reconcile_missing_sources_as_omitted", False)),
        )
        alias_errors = validate_ai_deck_contract(contract, alias_parsed, settings)
        if alias_errors:
            repair_prompt = _repair_prompt(prompt, contract, alias_errors)
            contract, repair_responses = _generate_with_chat_completions(
                repair_prompt,
                provider_schema,
                settings,
                transport,
                provider,
            )
            responses.extend(repair_responses)
            contract = _normalize_source_coverage_bookkeeping(
                contract,
                set(alias_to_original),
                bool(settings.get("reconcile_missing_sources_as_omitted", False)),
            )
            repair_errors = validate_ai_deck_contract(contract, alias_parsed, settings)
            if repair_errors:
                raise NarrativeAIError("Repaired AI deck contract validation failed:\n- " + "\n- ".join(repair_errors))
        contract = _restore_original_source_ids(contract, alias_to_original)
    elif provider == "prompt_only":
        raise NarrativeAIUnavailable(
            "Narrative AI is configured as prompt_only. Configure provider=deepseek_chat_completions and "
            "DEEPSEEK_API_KEY; "
            "the workflow will not fall back to format- or character-based pagination."
        )
    else:
        raise NarrativeAIError(f"Unsupported narrative AI provider: {provider}")

    errors = validate_ai_deck_contract(contract, parsed, settings)
    if errors:
        raise NarrativeAIError("AI deck contract validation failed:\n- " + "\n- ".join(errors))
    return NarrativeAIResult(contract, source_payload, prompt, schema, responses)


def validate_ai_deck_contract(
    contract: dict[str, Any],
    parsed: dict[str, Any],
    settings: dict[str, Any] | None = None,
) -> list[str]:
    settings = settings or {}
    errors = _validate_json_schema(contract, deck_contract_schema())
    pages = contract.get("pages") if isinstance(contract, dict) else None
    if not isinstance(pages, list) or not pages:
        return ["contract must contain pages"]
    target = settings.get("target_page_count")
    if isinstance(target, int) and target > 0 and len(pages) != target:
        errors.append(f"page count {len(pages)} does not match target {target}")
    page_numbers = [page.get("page_number") for page in pages]
    if page_numbers != list(range(1, len(pages) + 1)):
        errors.append("page numbers must be continuous and ordered from 1")
    assigned: list[str] = []
    for page in pages:
        number = page.get("page_number", "?")
        for field in ("title", "page_conclusion", "narrative_question", "semantic_relationship", "pagination_rationale"):
            if not str(page.get(field) or "").strip():
                errors.append(f"page {number} is missing {field}")
        source_ids = page.get("source_block_ids")
        if not isinstance(source_ids, list) or not source_ids:
            errors.append(f"page {number} must contain source_block_ids")
        else:
            assigned.extend(str(value) for value in source_ids)
        points = page.get("supporting_points")
        if not isinstance(points, list) or not any(str(point).strip() for point in points):
            errors.append(f"page {number} must contain supporting_points")

    valid_ids = {str(block.get("id")) for block in parsed.get("blocks", []) if block.get("id")}
    omitted_records = contract.get("omitted_blocks") or []
    omitted: set[str] = set()
    for record in omitted_records:
        if not isinstance(record, dict) or not record.get("block_id") or not str(record.get("reason") or "").strip():
            errors.append("every omitted block must contain block_id and reason")
            continue
        omitted.add(str(record["block_id"]))
    allowed_reuse = set(str(value) for value in contract.get("allowed_reused_source_block_ids") or [])
    counts: dict[str, int] = {}
    for source_id in assigned:
        counts[source_id] = counts.get(source_id, 0) + 1
    for source_id, count in counts.items():
        if count > 1 and source_id not in allowed_reuse:
            errors.append(f"duplicate source assignment without approval: {source_id}")
    unknown = (set(assigned) | omitted | allowed_reuse) - valid_ids
    for source_id in sorted(unknown):
        errors.append(f"unknown source id: {source_id}")
    missing = valid_ids - set(assigned) - omitted
    for source_id in sorted(missing):
        errors.append(f"unassigned source id: {source_id}")
    overlap = set(assigned) & omitted
    for source_id in sorted(overlap):
        errors.append(f"source id is both assigned and omitted: {source_id}")
    if not str(contract.get("storyline") or "").strip():
        errors.append("storyline is required")
    if not str(contract.get("communication_job") or "").strip():
        errors.append("communication_job is required")
    brief = settings.get("project_brief") if isinstance(settings.get("project_brief"), dict) else {}
    expected_fields = {
        "audience": brief.get("audience"),
        "purpose": brief.get("purpose"),
        "communication_job": brief.get("communication_job"),
        "central_thesis": brief.get("core_conclusion"),
    }
    for field, expected in expected_fields.items():
        if expected and contract.get(field) != expected:
            errors.append(f"{field} must exactly match the approved project brief")
    return errors


def _validate_json_schema(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Validate the small JSON-Schema subset used by the narrative contract without another dependency."""
    errors: list[str] = []
    expected_type = schema.get("type")
    type_matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
    }
    if expected_type in type_matches and not type_matches[expected_type]:
        return [f"{path} must be {expected_type}"]
    if expected_type == "object":
        required = schema.get("required", [])
        for name in required:
            if name not in value:
                errors.append(f"{path} is missing required field: {name}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for name in value:
                if name not in properties:
                    errors.append(f"{path} contains unsupported field: {name}")
        for name, child_schema in properties.items():
            if name in value:
                errors.extend(_validate_json_schema(value[name], child_schema, f"{path}.{name}"))
    elif expected_type == "array":
        minimum = schema.get("minItems")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{path} must contain at least {minimum} item(s)")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(_validate_json_schema(item, item_schema, f"{path}[{index}]"))
    elif expected_type == "string":
        minimum = schema.get("minLength")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{path} must contain at least {minimum} character(s)")
    elif expected_type == "integer":
        minimum = schema.get("minimum")
        if isinstance(minimum, int) and value < minimum:
            errors.append(f"{path} must be at least {minimum}")
    return errors


def build_restructure_report(contract: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    order = {str(block.get("id")): index for index, block in enumerate(parsed.get("blocks", []), start=1) if block.get("id")}
    total = max(1, len(order))
    page_records = []
    medians: list[float] = []
    cross_source_pages = 0
    for page in contract.get("pages", []):
        positions = sorted(order[source_id] for source_id in page.get("source_block_ids", []) if source_id in order)
        span = positions[-1] - positions[0] if positions else 0
        median = positions[len(positions) // 2] if positions else 0
        medians.append(median)
        distant = span / total >= 0.25
        cross_source_pages += int(distant)
        page_records.append(
            {
                "page_number": page.get("page_number"),
                "title": page.get("title"),
                "source_block_ids": page.get("source_block_ids", []),
                "original_position_span": span,
                "combines_distant_source_material": distant,
                "reorganization_notes": page.get("reorganization_notes", ""),
            }
        )
    source_order_preserved = medians == sorted(medians)
    deterministic_major = cross_source_pages > 0 or not source_order_preserved
    major = bool(contract.get("major_restructure")) or deterministic_major
    return {
        "schema_version": "1.0",
        "major_restructure": major,
        "ai_declared_major_restructure": bool(contract.get("major_restructure")),
        "source_order_preserved": source_order_preserved,
        "cross_source_page_count": cross_source_pages,
        "new_storyline": contract.get("storyline"),
        "summary": contract.get("restructure_summary"),
        "pages": page_records,
        "omitted_blocks": contract.get("omitted_blocks", []),
        "reused_source_block_ids": contract.get("allowed_reused_source_block_ids", []),
        "user_notice": (
            "本次分页未沿用原报告章节结构，已根据全文论证关系进行较大重组。"
            if major
            else "本次分页主要调整了叙事表达，来源内容的整体次序变化有限。"
        ),
    }


def restructure_report_text(report: dict[str, Any]) -> str:
    lines = [
        "PAGINATION RESTRUCTURE REPORT",
        "",
        report.get("user_notice", ""),
        f"New storyline: {report.get('new_storyline', '')}",
        f"Summary: {report.get('summary', '')}",
        f"Source order preserved: {report.get('source_order_preserved')}",
        f"Pages combining distant source material: {report.get('cross_source_page_count', 0)}",
        "",
        "Page mapping:",
    ]
    for page in report.get("pages", []):
        lines.append(
            f"- P{page.get('page_number')} {page.get('title')}: sources={','.join(page.get('source_block_ids', []))}; "
            f"distant={page.get('combines_distant_source_material')}; {page.get('reorganization_notes', '')}"
        )
    if report.get("omitted_blocks"):
        lines.extend(["", "Omitted blocks:"])
        lines.extend(f"- {item.get('block_id')}: {item.get('reason')}" for item in report["omitted_blocks"])
    return "\n".join(lines).strip() + "\n"


def _generate_with_chat_completions(
    prompt: str,
    schema: dict[str, Any],
    settings: dict[str, Any],
    transport: Transport | None,
    provider: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    legacy_deepseek = provider == "deepseek_chat_completions"
    provider_name = "DeepSeek" if legacy_deepseek else str(settings.get("provider_name") or "Chat Completions")
    default_api_key_env = "DEEPSEEK_API_KEY" if legacy_deepseek else "PARATERA_API_KEY"
    default_model_env = "DEEPSEEK_NARRATIVE_MODEL" if legacy_deepseek else "PARATERA_NARRATIVE_MODEL"
    default_endpoint = (
        "https://api.deepseek.com/chat/completions"
        if legacy_deepseek
        else "https://llmapi.paratera.com/v1/chat/completions"
    )
    api_key_env = settings.get("api_key_env", default_api_key_env)
    api_key = os.environ.get(api_key_env) or _read_env_file_value(settings.get("env_file"), api_key_env)
    if not api_key:
        raise NarrativeAIUnavailable(
            f"{api_key_env} is not configured. Narrative pagination requires AI and will not use a heuristic fallback."
        )
    model_env = settings.get("model_env", default_model_env)
    model = settings.get("model") or os.environ.get(model_env) or _read_env_file_value(settings.get("env_file"), model_env)
    if not model:
        raise NarrativeAIUnavailable(
            f"Narrative AI model is not configured. Set narrative_ai.model or {model_env}."
        )
    schema_text = json.dumps(schema, ensure_ascii=False, indent=2)
    system_prompt = (
        "你是PPT叙事分页器。必须提交一个可由json.loads解析的JSON对象，不要输出Markdown代码块、解释或思考过程。"
        "输出必须严格符合用户提供的JSON Schema，不得增删字段。"
        "顶层格式示例：{\"schema_version\":\"2.0\",\"audience\":\"...\",\"purpose\":\"...\","
        "\"communication_job\":\"...\",\"central_thesis\":\"...\",\"storyline\":\"...\","
        "\"major_restructure\":true,\"restructure_summary\":\"...\",\"alternatives_considered\":[],"
        "\"pages\":[],\"omitted_blocks\":[],\"allowed_reused_source_block_ids\":[]}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": prompt + "\n\n必须遵守的JSON Schema：\n" + schema_text,
            },
        ],
        "stream": False,
        "max_tokens": int(settings.get("max_output_tokens", 16000)),
    }
    if "temperature" in settings or legacy_deepseek:
        payload["temperature"] = float(settings.get("temperature", 0.2))
    reasoning_effort = settings.get("reasoning_effort")
    if isinstance(reasoning_effort, str) and reasoning_effort in {"low", "high", "max"}:
        payload["reasoning_effort"] = reasoning_effort
    structured_output_mode = settings.get("structured_output_mode", "json_object")
    if structured_output_mode == "strict_tool_call":
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "submit_narrative_deck_contract",
                    "description": "Submit the complete five-page narrative deck contract after reading all source records.",
                    "strict": True,
                    "parameters": _strict_tool_schema(schema),
                },
            }
        ]
        payload["tool_choice"] = {
            "type": "function",
            "function": {"name": "submit_narrative_deck_contract"},
        }
    elif structured_output_mode == "json_object":
        payload["response_format"] = {"type": "json_object"}
    elif structured_output_mode == "json_schema":
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "narrative_deck_contract",
                "strict": True,
                "schema": schema,
            },
        }
    else:
        raise NarrativeAIError(f"Unsupported Chat Completions structured output mode: {structured_output_mode}")
    thinking = settings.get("thinking")
    if isinstance(thinking, str) and thinking in {"enabled", "disabled"}:
        payload["thinking"] = {"type": thinking}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    responses: list[dict[str, Any]] = []
    last_error: Exception | None = None
    retry_count = max(0, int(settings.get("format_retry_count", 1)))
    for attempt in range(retry_count + 1):
        if attempt:
            payload["messages"][-1]["content"] += (
                "\n\n上一次响应为空或不是有效JSON。请重新生成完整JSON对象，不要输出任何JSON以外的内容。"
            )
        if transport:
            response = transport(payload, headers)
        else:
            response = _http_post_json(
                settings.get("endpoint", default_endpoint),
                payload,
                headers,
                float(settings.get("timeout_seconds", 240)),
            )
        responses.append(response)
        try:
            output_text = _extract_chat_completion_text(response)
            return json.loads(output_text), responses
        except (NarrativeAIError, json.JSONDecodeError) as exc:
            last_error = exc
    raise NarrativeAIError(
        f"{provider_name} narrative AI returned empty or invalid JSON after the configured format retry."
    ) from last_error


def _http_post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = url_request.Request(url, data=body, headers=headers, method="POST")
    try:
        with url_request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except url_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise NarrativeAIError(f"Narrative AI request failed with HTTP {exc.code}: {detail}") from exc
    except url_error.URLError as exc:
        raise NarrativeAIError(f"Narrative AI request failed: {exc.reason}") from exc


def _extract_chat_completion_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise NarrativeAIError("Chat Completions response did not contain any completion choices.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
    if isinstance(tool_calls, list) and tool_calls:
        function = tool_calls[0].get("function") if isinstance(tool_calls[0], dict) else None
        arguments = function.get("arguments") if isinstance(function, dict) else None
        if isinstance(arguments, str) and arguments.strip():
            return arguments
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise NarrativeAIError("Chat Completions response did not contain a non-empty JSON result.")
    return content


def _strict_tool_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Remove commonly unsupported strict-tool keywords; local validation remains stricter."""
    unsupported = {"minLength", "maxLength", "minItems", "maxItems"}
    converted: dict[str, Any] = {}
    for key, value in schema.items():
        if key in unsupported:
            continue
        if isinstance(value, dict):
            converted[key] = _strict_tool_schema(value)
        elif isinstance(value, list):
            converted[key] = [
                _strict_tool_schema(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            converted[key] = value
    return converted


def _schema_with_source_id_enum(schema: dict[str, Any], source_ids: list[str]) -> dict[str, Any]:
    specialized = copy.deepcopy(schema)
    enum = sorted(source_ids)
    page_properties = specialized["properties"]["pages"]["items"]["properties"]
    page_properties["source_block_ids"]["items"]["enum"] = enum
    omitted_properties = specialized["properties"]["omitted_blocks"]["items"]["properties"]
    omitted_properties["block_id"]["enum"] = enum
    specialized["properties"]["allowed_reused_source_block_ids"]["items"]["enum"] = enum
    return specialized


def _normalize_source_coverage_bookkeeping(
    contract: dict[str, Any],
    valid_ids: set[str],
    reconcile_missing_as_omitted: bool,
) -> dict[str, Any]:
    """Keep narrative choices intact while resolving invalid IDs and source-ledger overlap."""
    normalized = copy.deepcopy(contract)
    for page in normalized.get("pages", []):
        page["source_block_ids"] = [
            str(source_id)
            for source_id in page.get("source_block_ids", [])
            if str(source_id) in valid_ids
        ]
    assigned = {
        str(source_id)
        for page in normalized.get("pages", [])
        for source_id in page.get("source_block_ids", [])
    }
    normalized["omitted_blocks"] = [
        record
        for record in normalized.get("omitted_blocks", [])
        if isinstance(record, dict)
        and str(record.get("block_id")) in valid_ids
        and str(record.get("block_id")) not in assigned
    ]
    normalized["allowed_reused_source_block_ids"] = [
        str(source_id)
        for source_id in normalized.get("allowed_reused_source_block_ids", [])
        if str(source_id) in valid_ids
    ]
    if reconcile_missing_as_omitted:
        omitted = {str(record.get("block_id")) for record in normalized["omitted_blocks"]}
        for source_id in sorted(valid_ids - assigned - omitted):
            normalized["omitted_blocks"].append(
                {
                    "block_id": source_id,
                    "reason": "未进入最终五页叙事；由本地来源账本登记为本次试验未采用。",
                }
            )
    return normalized


def _repair_prompt(original_prompt: str, contract: dict[str, Any], errors: list[str]) -> str:
    return (
        original_prompt
        + "\n\n上一次输出没有通过确定性校验。请保持原有叙事质量，只修复下列错误，并重新输出完整合同：\n- "
        + "\n- ".join(errors)
        + "\n\n上一次合同：\n"
        + json.dumps(contract, ensure_ascii=False, indent=2)
    )


def _block_content(block: dict[str, Any]) -> str:
    if block.get("type") == "list":
        return "\n".join(str(item).strip() for item in block.get("items", []) if str(item).strip())
    if block.get("type") == "table":
        return "\n".join(" | ".join(str(cell).strip() for cell in row) for row in block.get("rows", []))
    return str(block.get("text", "")).strip()


def _matches_exclusion(text: str, patterns: list[str]) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in patterns)


def _source_alias(original_id: str, content: str) -> str:
    digest = hashlib.sha256(f"{original_id}\0{content}".encode("utf-8")).hexdigest()[:16]
    return f"s_{digest}"


def _alias_to_original_map(parsed: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for block in parsed.get("blocks", []):
        original_id = str(block.get("id") or "").strip()
        if not original_id:
            continue
        content = _block_content(block) or "[empty source record]"
        result[_source_alias(original_id, content)] = original_id
    return result


def _restore_original_source_ids(contract: dict[str, Any], alias_to_original: dict[str, str]) -> dict[str, Any]:
    restored = json.loads(json.dumps(contract, ensure_ascii=False))
    for page in restored.get("pages", []):
        page["source_block_ids"] = [alias_to_original.get(value, value) for value in page.get("source_block_ids", [])]
    for record in restored.get("omitted_blocks", []):
        record["block_id"] = alias_to_original.get(record.get("block_id"), record.get("block_id"))
    restored["allowed_reused_source_block_ids"] = [
        alias_to_original.get(value, value) for value in restored.get("allowed_reused_source_block_ids", [])
    ]
    return restored


def _read_env_file_value(env_file: Any, key: str) -> str | None:
    if not env_file:
        return None
    path = Path(str(env_file))
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.is_file():
        return None
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip().strip('"').strip("'") or None
    return None
