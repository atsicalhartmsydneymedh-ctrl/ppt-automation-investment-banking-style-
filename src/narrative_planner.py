from __future__ import annotations

import math
import re
from typing import Any

try:
    from .utils import extract_data_points, first_sentence, normalize_space
except ImportError:
    from utils import extract_data_points, first_sentence, normalize_space


DEFAULT_NARRATIVE = {
    "target_evidence_units": 6.0,
    "max_evidence_units": 9.0,
    "min_evidence_units": 2.0,
    "max_supporting_points": 10,
    "reorder_by_narrative_role": True,
}

ROLE_PRIORITY = {
    "opening_synthesis": 0,
    "foundation": 1,
    "comparison": 2,
    "evidence": 2,
    "mechanism": 2,
    "implication": 3,
    "closing_synthesis": 4,
}

ROLE_QUESTION = {
    "opening_synthesis": "这份材料最重要的判断是什么？",
    "foundation": "理解后续判断前，需要先建立什么共同背景？",
    "comparison": "关键对象之间有哪些真正重要的异同？",
    "evidence": "哪些事实和数据支撑这一判断？",
    "mechanism": "这些现象为什么发生，彼此如何作用？",
    "implication": "这些判断意味着什么，应当关注或采取什么行动？",
    "closing_synthesis": "综合前述证据，最终应带走什么结论？",
}


def create_narrative_plan(parsed: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create an editable, source-traceable storyline before slide pagination.

    Character count is used only to estimate overflow inside an editorial unit.
    Page boundaries are decided from narrative role, content relationship, and
    evidence load.
    """
    settings = DEFAULT_NARRATIVE | (config or {})
    blocks = list(parsed.get("blocks", []))
    usable, omitted = _partition_source_blocks(blocks)
    editorial_units = _editorial_units(usable)
    if settings["reorder_by_narrative_role"]:
        editorial_units = sorted(
            editorial_units,
            key=lambda unit: (ROLE_PRIORITY.get(unit["narrative_role"], 3), unit["source_order"]),
        )
    page_bundles = _allocate_pages(editorial_units, settings)
    target_pages = settings.get("target_page_count")
    if isinstance(target_pages, int) and target_pages > 0:
        page_bundles = _fit_target_page_count(page_bundles, target_pages, settings)
    pages = [_page_from_bundle(bundle, index, settings) for index, bundle in enumerate(page_bundles, start=1)]
    for index, page in enumerate(pages):
        previous_role = pages[index - 1]["narrative_role"] if index else None
        page["transition_from_previous"] = _transition(previous_role, page["narrative_role"])
    loads = [page["evidence_load"] for page in pages]
    brief = {
        "schema_version": "1.0",
        "communication_job": _communication_job(parsed, pages),
        "storyline": " → ".join(page["narrative_role"] for page in pages),
        "pagination_basis": "narrative role + relationship coherence + evidence load; character count is overflow-only",
        "page_count": len(pages),
        "evidence_load": {
            "min": round(min(loads), 2) if loads else 0,
            "max": round(max(loads), 2) if loads else 0,
            "average": round(sum(loads) / len(loads), 2) if loads else 0,
        },
        "editorial_units": editorial_units,
        "pages": pages,
        "omitted_blocks": omitted,
    }
    return brief


def build_narrative_planning_prompt(parsed: dict[str, Any], narrative_plan: dict[str, Any]) -> str:
    inventory = []
    for block in parsed.get("blocks", []):
        inventory.append(f"- {block.get('id')} [{block.get('type')}] {_block_text(block)[:360]}")
    candidate_pages = []
    for page in narrative_plan.get("pages", []):
        candidate_pages.append(
            f"- P{page['page_number']} | role={page['narrative_role']} | question={page['narrative_question']} | "
            f"claim={page['page_conclusion']} | sources={','.join(page['source_block_ids'])} | load={page['evidence_load']}"
        )
    return "\n".join(
        [
            "你是PPT内容总编。请先通读完整材料，再决定PPT讲什么、怎么讲，最后才分页。",
            "",
            "硬规则：",
            "1. 每页只有一个叙事任务和一个可由本页证据推出的结论。",
            "2. 允许重排原文顺序，但每次重排都必须让解释链更清楚；不得按字符数或原标题机械分页。",
            "3. 先形成背景/问题/比较/证据/机制/启示等逻辑链，再把内容分配到页面。",
            "4. 每个来源块只能分配一次，除非显式记录复用理由；删去的块必须记录原因。",
            "5. 内容关系优先于视觉形式。此阶段不得按表格、卡片、气泡等视觉类型决定分页。",
            "6. 页间证据负载尽量均衡；超载时拆论点，低载时只合并关系紧密且服务同一结论的内容。",
            "",
            f"传播任务候选：{narrative_plan.get('communication_job', '')}",
            "",
            "完整来源清单：",
            *inventory,
            "",
            "候选叙事分页（需要逐页复核，而不是直接照抄）：",
            *candidate_pages,
            "",
            "输出要求：返回完整deck_contract JSON，包含audience、purpose、storyline、pages、omitted_blocks和allowed_reused_source_block_ids。",
        ]
    ).strip() + "\n"


def narrative_pages_to_segments(narrative_plan: dict[str, Any]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for page in narrative_plan.get("pages", []):
        segments.append(
            {
                "slide_number": page["page_number"],
                "id": f"n{page['page_number']:03d}",
                "title": page["title"],
                "core_message": page["page_conclusion"],
                "supporting_points": page.get("supporting_points", []),
                "data_points": page.get("data_points", []),
                "suggested_visual_type": page.get("suggested_visual_type", "structured_bullets"),
                "display_focus": page.get("semantic_relationship", "claim -> evidence -> implication"),
                "source_block_ids": page.get("source_block_ids", []),
                "content_char_count": sum(len(str(item)) for item in page.get("supporting_points", [])),
                "evidence_load": page.get("evidence_load", 0),
                "narrative_role": page.get("narrative_role"),
                "narrative_question": page.get("narrative_question"),
            }
        )
    return segments


def _partition_source_blocks(blocks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    usable: list[dict[str, Any]] = []
    omitted: list[dict[str, str]] = []
    in_references = False
    for block in blocks:
        text = _block_text(block)
        if block.get("type") == "heading" and _is_reference_heading(text):
            in_references = True
        elif in_references and block.get("type") == "heading" and not _is_reference_heading(text):
            in_references = False
        if in_references or _is_reference_noise(text):
            if block.get("id"):
                omitted.append({"block_id": block["id"], "reason": "Reference list, URL-only record, or source-formatting noise."})
            continue
        usable.append(block)
    return usable, omitted


def _editorial_units(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[tuple[str, list[dict[str, Any]]]] = []
    preamble: list[dict[str, Any]] = []
    current: list[dict[str, Any]] | None = None
    current_title = ""
    for block in blocks:
        is_section_heading = _is_structural_heading(block)
        if is_section_heading:
            if current:
                sections.append((current_title, current))
            current_title = normalize_space(_block_text(block)) or "核心内容"
            current = [*preamble, block] if not sections else [block]
            preamble = []
        elif current is None:
            preamble.append(block)
        else:
            current.append(block)
    if current:
        sections.append((current_title, current))
    elif preamble:
        sections = _secondary_sections(preamble)
    sections = _attach_trailing_tables(sections)
    return [_make_unit(title, section_blocks, index) for index, (title, section_blocks) in enumerate(sections)]


def _make_unit(title: str, blocks: list[dict[str, Any]], source_order: int) -> dict[str, Any]:
    text = normalize_space(" ".join(_block_text(block) for block in blocks if block.get("type") != "heading"))
    full_text = text or normalize_space(" ".join(_block_text(block) for block in blocks))
    role = _classify_role(title, full_text)
    relationship = _infer_relationship(title, full_text, blocks)
    return {
        "id": f"u{source_order + 1:03d}",
        "title": title,
        "source_order": source_order,
        "narrative_role": role,
        "narrative_question": ROLE_QUESTION[role],
        "relationship": relationship,
        "source_block_ids": [block["id"] for block in blocks if block.get("id")],
        "supporting_points": _supporting_points(blocks, 30),
        "data_points": extract_data_points(full_text),
        "evidence_load": _unit_evidence_load(blocks),
        "char_count": len(full_text),
        "claim": first_sentence(full_text) or title,
        "blocks": blocks,
    }


def _allocate_pages(units: list[dict[str, Any]], settings: dict[str, Any]) -> list[list[dict[str, Any]]]:
    expanded = list(units)

    pages: list[list[dict[str, Any]]] = []
    for unit in expanded:
        if not pages:
            pages.append([unit])
            continue
        current = pages[-1]
        current_load = sum(item["evidence_load"] for item in current)
        same_job = all(item["narrative_role"] == unit["narrative_role"] for item in current)
        same_relation = all(item["relationship"] == unit["relationship"] for item in current)
        can_merge = (
            (same_job or same_relation)
            and current_load < settings["min_evidence_units"]
            and current_load + unit["evidence_load"] <= settings["max_evidence_units"]
        )
        if can_merge:
            current.append(unit)
        else:
            pages.append([unit])
    if len(pages) > 1:
        last_load = sum(item["evidence_load"] for item in pages[-1])
        previous_load = sum(item["evidence_load"] for item in pages[-2])
        if (
            last_load < settings["min_evidence_units"]
            and previous_load + last_load <= settings["max_evidence_units"]
            and pages[-1][0]["narrative_role"] == pages[-2][0]["narrative_role"]
        ):
            pages[-2].extend(pages.pop())
    return pages


def _fit_target_page_count(
    pages: list[list[dict[str, Any]]],
    target: int,
    settings: dict[str, Any],
) -> list[list[dict[str, Any]]]:
    result = [list(page) for page in pages]
    compatible_analysis = {"foundation", "comparison", "evidence", "mechanism"}
    while len(result) > target:
        candidates: list[tuple[float, int]] = []
        for index in range(len(result) - 1):
            left_role = result[index][0]["narrative_role"]
            right_role = result[index + 1][0]["narrative_role"]
            if left_role == "opening_synthesis" or right_role in {"implication", "closing_synthesis"}:
                continue
            if left_role == right_role:
                compatibility = 0
            elif left_role in compatible_analysis and right_role in compatible_analysis:
                compatibility = 2
            else:
                continue
            load = sum(unit["evidence_load"] for unit in result[index] + result[index + 1])
            candidates.append((compatibility + load / max(1.0, float(settings["max_evidence_units"])), index))
        if not candidates:
            break
        _, best_index = min(candidates)
        result[best_index].extend(result.pop(best_index + 1))
    return result


def _split_unit(unit: dict[str, Any], target: float) -> list[dict[str, Any]]:
    blocks = unit["blocks"]
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    load = 0.0
    for block in blocks:
        block_load = _block_load(block)
        if current and load + block_load > target and any(item.get("type") != "heading" for item in current):
            chunks.append(current)
            current = []
            load = 0.0
        current.append(block)
        load += block_load
    if current:
        chunks.append(current)
    result: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        child = _make_unit(f"{unit['title']}（{index}/{len(chunks)}）", chunk, unit["source_order"])
        child["id"] = f"{unit['id']}-{index}"
        child["narrative_role"] = unit["narrative_role"]
        child["narrative_question"] = unit["narrative_question"]
        child["relationship"] = unit["relationship"]
        result.append(child)
    return result


def _page_from_bundle(bundle: list[dict[str, Any]], page_number: int, settings: dict[str, Any]) -> dict[str, Any]:
    primary = bundle[0]
    source_ids = [block_id for unit in bundle for block_id in unit["source_block_ids"]]
    points = _dedupe([point for unit in bundle for point in unit["supporting_points"]])
    data = _dedupe([value for unit in bundle for value in unit["data_points"]])
    title = primary["title"] if len(bundle) == 1 else " / ".join(unit["title"] for unit in bundle)
    conclusion = primary["claim"]
    relationship = primary["relationship"] if all(unit["relationship"] == primary["relationship"] for unit in bundle) else "claim -> coordinated_evidence -> implication"
    return {
        "page_number": page_number,
        "title": title,
        "page_conclusion": conclusion,
        "narrative_role": primary["narrative_role"],
        "narrative_question": primary["narrative_question"],
        "editorial_unit_ids": [unit["id"] for unit in bundle],
        "source_block_ids": source_ids,
        "supporting_points": points[: int(settings["max_supporting_points"])],
        "data_points": data,
        "semantic_relationship": relationship,
        "suggested_visual_type": _suggest_visual_type(relationship, data, primary["blocks"]),
        "evidence_load": round(sum(unit["evidence_load"] for unit in bundle), 2),
        "pagination_rationale": "These source blocks serve one narrative question and remain within the evidence-load budget.",
    }


def _classify_role(title: str, text: str) -> str:
    value = f"{title} {text}".lower()
    rules = (
        ("opening_synthesis", ("摘要", "概览", "核心观点", "核心结论", "主要结论", "executive summary", "overview")),
        ("closing_synthesis", ("总结", "结语", "最终结论", "conclusion")),
        ("implication", ("建议", "策略", "启示", "展望", "风险", "行动", "recommend", "outlook", "implication")),
        ("foundation", ("背景", "定义", "概念", "介绍", "现状", "background", "definition", "context")),
        ("comparison", ("对比", "比较", "区别", "差异", "格局", "结构", "compare", "versus", "vs.")),
        ("mechanism", ("原因", "驱动", "机制", "影响因素", "why", "driver", "mechanism")),
        ("evidence", ("数据", "表现", "规模", "趋势", "历史", "测算", "performance", "trend", "data")),
    )
    for role, keywords in rules:
        if any(keyword in value for keyword in keywords):
            return role
    return "evidence"


def _infer_relationship(title: str, text: str, blocks: list[dict[str, Any]]) -> str:
    value = f"{title} {text}".lower()
    if any(block.get("type") == "table" for block in blocks):
        return "multiple_objects × shared_metrics -> comparison"
    if any(token in value for token in ("时间", "阶段", "历程", "年度", "季度", "timeline", "phase")):
        return "ordered_stages -> progression"
    if any(token in value for token in ("对比", "比较", "区别", "差异", "versus", "vs.")):
        return "peer_objects -> comparison"
    if any(token in value for token in ("原因", "驱动", "因素", "机制", "driver", "cause")):
        return "parallel_factors -> shared_outcome"
    if any(token in value for token in ("建议", "行动", "策略", "风险", "recommend", "action")):
        return "findings -> implications_or_actions"
    return "claim -> evidence -> implication"


def _suggest_visual_type(relationship: str, data: list[str], blocks: list[dict[str, Any]]) -> str:
    if "shared_metrics" in relationship or any(block.get("type") == "table" for block in blocks):
        return "editable_table"
    if "ordered_stages" in relationship:
        return "timeline_or_process"
    if "actions" in relationship:
        return "matrix"
    if data:
        return "data_cards"
    if "peer_objects" in relationship or "parallel_factors" in relationship:
        return "structured_bullets"
    return "two_column_story"


def _supporting_points(blocks: list[dict[str, Any]], limit: int) -> list[str]:
    points: list[str] = []
    for block in blocks:
        if block.get("type") == "heading":
            continue
        if block.get("type") == "list":
            points.extend(block.get("items", []))
        elif block.get("type") == "table":
            for row in block.get("rows", [])[1:]:
                points.append(" | ".join(cell for cell in row if cell))
        else:
            points.extend(re.split(r"(?<=[。！？.!?])\s*", str(block.get("text", ""))))
    return _dedupe([normalize_space(point) for point in points if normalize_space(point)])[:limit]


def _block_load(block: dict[str, Any]) -> float:
    kind = block.get("type")
    if kind == "heading":
        return 0.25
    if kind == "table":
        rows = block.get("rows", [])
        columns = max((len(row) for row in rows), default=0)
        return max(1.5, min(6.0, max(0, len(rows) - 1) * max(1, columns) / 4))
    if kind == "list":
        return max(1.0, len(block.get("items", [])) * 0.7)
    return max(0.75, math.ceil(len(_block_text(block)) / 260))


def _unit_evidence_load(blocks: list[dict[str, Any]]) -> float:
    tables = sum(1 for block in blocks if block.get("type") == "table")
    subheads = sum(1 for block in blocks if _is_secondary_heading(block))
    prefixes = {
        match.group(1).strip()
        for block in blocks
        if block.get("type") == "paragraph"
        for match in [re.match(r"^([^：:。]{2,20})[：:]", normalize_space(_block_text(block)))]
        if match
    }
    load = 1.0 + min(4, subheads) * 0.75 + min(5, len(prefixes)) * 0.8 + min(3, tables) * 1.25
    return round(min(12.0, max(1.0, load)), 2)


def _is_structural_heading(block: dict[str, Any]) -> bool:
    text = normalize_space(_block_text(block))
    if block.get("type") == "heading" and int(block.get("level", 2) or 2) <= 2:
        return True
    if block.get("type") != "paragraph" or not text or len(text) > 80:
        return False
    return bool(
        re.match(r"^(?:第[一二三四五六七八九十百0-9]+[章节篇部]|[一二三四五六七八九十]+[、.．]|\d+[、.．])", text)
        or re.match(r"^(?:chapter|section)\s+\d+", text, flags=re.IGNORECASE)
    )


def _is_secondary_heading(block: dict[str, Any]) -> bool:
    if block.get("type") == "list":
        items = block.get("items", [])
        return len(items) == 1 and len(normalize_space(str(items[0]))) <= 60
    text = normalize_space(_block_text(block))
    return block.get("type") == "paragraph" and len(text) <= 55 and text.endswith(("：", ":"))


def _secondary_sections(blocks: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    sections: list[tuple[str, list[dict[str, Any]]]] = []
    preamble: list[dict[str, Any]] = []
    current: list[dict[str, Any]] | None = None
    title = "核心内容"
    for block in blocks:
        if _is_secondary_heading(block):
            if current:
                sections.append((title, current))
            title = normalize_space(_block_text(block))
            current = [*preamble, block] if not sections else [block]
            preamble = []
        elif current is None:
            preamble.append(block)
        else:
            current.append(block)
    if current:
        sections.append((title, current))
    elif preamble:
        sections.append(("核心内容", preamble))
    return sections


def _attach_trailing_tables(
    sections: list[tuple[str, list[dict[str, Any]]]],
) -> list[tuple[str, list[dict[str, Any]]]]:
    if len(sections) < 2:
        return sections
    mutable = [(title, list(blocks)) for title, blocks in sections]
    trailing: list[dict[str, Any]] = []
    last_blocks = mutable[-1][1]
    while last_blocks and last_blocks[-1].get("type") == "table":
        trailing.append(last_blocks.pop())
    trailing.reverse()
    if not trailing:
        return mutable
    for table in trailing:
        table_tokens = _similarity_tokens(_block_text(table))
        scores: list[tuple[float, int]] = []
        for index, (title, section_blocks) in enumerate(mutable):
            section_text = title + " " + " ".join(_block_text(block) for block in section_blocks[:8])
            section_tokens = _similarity_tokens(section_text)
            overlap = len(table_tokens & section_tokens)
            score = overlap / max(1, len(table_tokens))
            scores.append((score, index))
        _, best_index = max(scores)
        mutable[best_index][1].append(table)
    return mutable


def _similarity_tokens(text: str) -> set[str]:
    normalized = normalize_space(text).lower()
    latin = set(re.findall(r"[a-z0-9%+-]{2,}", normalized))
    chinese_runs = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
    bigrams = {run[index : index + 2] for run in chinese_runs for index in range(len(run) - 1)}
    return latin | bigrams


def _communication_job(parsed: dict[str, Any], pages: list[dict[str, Any]]) -> str:
    source_name = parsed.get("source_name") or parsed.get("source_path") or "the source report"
    closing = pages[-1]["page_conclusion"] if pages else "understand the report"
    return f"By the end, the audience should understand the logic of {source_name} and retain this final takeaway: {closing}"


def _transition(previous_role: str | None, current_role: str) -> str:
    if previous_role is None:
        return "Open by establishing the first question the deck will answer."
    if previous_role == current_role:
        return "Continue the same narrative job with a distinct, non-overlapping claim."
    return f"Move from {previous_role} to {current_role} because the next page answers the question created by the prior evidence."


def _is_reference_heading(text: str) -> bool:
    value = normalize_space(text).lower()
    return any(token in value for token in ("参考文献", "资料来源", "数据来源", "references", "bibliography", "sources"))


def _is_reference_noise(text: str) -> bool:
    clean = normalize_space(text)
    lower = clean.lower()
    url_count = lower.count("http://") + lower.count("https://") + lower.count("www.")
    return bool(clean) and ((url_count >= 1 and len(clean) < 260) or (len(clean) < 220 and any(domain in lower for domain in (".com", ".cn", ".org", ".edu", ".pdf"))))


def _block_text(block: dict[str, Any]) -> str:
    if block.get("type") == "list":
        return " ".join(str(item) for item in block.get("items", []))
    if block.get("type") == "table":
        return " ".join(" ".join(str(cell) for cell in row) for row in block.get("rows", []))
    return str(block.get("text", ""))


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
