from __future__ import annotations

import re
from typing import Any

from utils import chunk_text, extract_data_points, first_sentence, normalize_space


DEFAULT_SEGMENTING = {
    "min_chars_per_slide": 350,
    "max_chars_per_slide": 1100,
    "max_supporting_points": 7,
}


def create_segments(parsed_document: dict[str, Any], config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    settings = DEFAULT_SEGMENTING | (config or {})
    blocks = _filter_reference_noise(parsed_document.get("blocks", []))
    sections = _blocks_to_sections(blocks)

    raw_segments: list[dict[str, Any]] = []
    for section in sections:
        raw_segments.extend(_section_to_segments(section, settings))

    merged = _merge_short_segments(raw_segments, settings["min_chars_per_slide"])
    for idx, segment in enumerate(merged, start=1):
        segment["slide_number"] = idx
        segment["id"] = f"s{idx:03d}"
    return merged


def _filter_reference_noise(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    in_references = False
    for block in blocks:
        text = _block_text(block)
        if block.get("type") == "heading" and _is_reference_heading(text):
            in_references = True
            continue
        if in_references and block.get("type") == "heading" and not _is_reference_heading(text):
            in_references = False
        if in_references:
            continue
        if _is_reference_noise(text):
            continue
        filtered.append(block)
    return filtered


def _is_reference_heading(text: str) -> bool:
    lower = normalize_space(text).lower()
    return any(token in lower for token in ("参考文献", "资料来源", "数据来源", "references", "bibliography", "sources"))


def _is_reference_noise(text: str) -> bool:
    clean = normalize_space(text)
    if not clean:
        return False
    lower = clean.lower()
    url_count = lower.count("http://") + lower.count("https://") + lower.count("www.")
    if url_count >= 1 and len(clean) < 260:
        return True
    if "访问时间" in clean and url_count >= 1:
        return True
    if len(clean) < 220 and any(domain in lower for domain in (".com", ".cn", ".org", ".edu", ".pdf")):
        return True
    return False


def segments_to_markdown(segments: list[dict[str, Any]]) -> str:
    lines = ["# Parsed Slide Content", ""]
    for segment in segments:
        lines.append(f"## Slide {segment['slide_number']}: {segment['title']}")
        lines.append("")
        lines.append(f"- Core message: {segment['core_message']}")
        lines.append(f"- Suggested visual: {segment['suggested_visual_type']}")
        if segment.get("data_points"):
            lines.append(f"- Data points: {', '.join(segment['data_points'])}")
        lines.append("")
        lines.append("Supporting information:")
        for point in segment.get("supporting_points", []):
            lines.append(f"- {point}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _blocks_to_sections(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current = {"title": "Executive Overview", "level": 1, "blocks": []}

    for block in blocks:
        if block.get("type") == "heading" and block.get("level", 2) <= 2:
            if current["blocks"]:
                sections.append(current)
            current = {
                "title": block.get("text") or "Untitled Section",
                "level": block.get("level", 2),
                "blocks": [block],
            }
        else:
            current["blocks"].append(block)

    if current["blocks"]:
        sections.append(current)

    return sections or [{"title": "Executive Overview", "level": 1, "blocks": blocks}]


def _section_to_segments(section: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    max_chars = settings["max_chars_per_slide"]
    blocks = _expand_large_blocks(section["blocks"], max_chars)

    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_len = 0
    for block in blocks:
        block_len = len(_block_text(block))
        should_split = current and current_len + block_len > max_chars
        if should_split:
            chunks.append(current)
            current = []
            current_len = 0
        current.append(block)
        current_len += block_len

    if current:
        chunks.append(current)

    segments = []
    for idx, chunk in enumerate(chunks, start=1):
        title = section["title"]
        if len(chunks) > 1:
            title = f"{title} ({idx}/{len(chunks)})"
        segments.append(_build_segment(title, chunk, settings))
    return segments


def _expand_large_blocks(blocks: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for block in blocks:
        if block.get("type") == "paragraph" and len(block.get("text", "")) > max_chars:
            for text in chunk_text(block["text"], max_chars):
                new_block = dict(block)
                new_block["text"] = text
                expanded.append(new_block)
        else:
            expanded.append(block)
    return expanded


def _build_segment(title: str, blocks: list[dict[str, Any]], settings: dict[str, Any]) -> dict[str, Any]:
    content_text = normalize_space(" ".join(_block_text(block) for block in blocks if block.get("type") != "heading"))
    full_text = content_text or normalize_space(" ".join(_block_text(block) for block in blocks))
    supporting_points = _supporting_points(blocks, settings["max_supporting_points"])
    visual_type = _suggest_visual_type(blocks, full_text)
    return {
        "title": title,
        "core_message": first_sentence(full_text) or title,
        "supporting_points": supporting_points,
        "data_points": extract_data_points(full_text),
        "suggested_visual_type": visual_type,
        "display_focus": _display_focus(visual_type),
        "source_block_ids": [block.get("id") for block in blocks if block.get("id")],
        "content_char_count": len(full_text),
    }


def _supporting_points(blocks: list[dict[str, Any]], limit: int) -> list[str]:
    points: list[str] = []
    for block in blocks:
        block_type = block.get("type")
        if block_type == "heading":
            continue
        if block_type == "list":
            points.extend(block.get("items", []))
        elif block_type == "table":
            rows = block.get("rows", [])
            if rows:
                header = rows[0]
                for row in rows[1:]:
                    item = " | ".join(cell for cell in row if cell)
                    if item:
                        points.append(item)
                if len(rows) == 1:
                    points.append("Table: " + " | ".join(header))
        else:
            text = block.get("text", "")
            for sentence in re.split(r"(?<=[.!?。！？])\s*", text):
                sentence = normalize_space(sentence)
                if sentence:
                    points.append(sentence)
        if len(points) >= limit:
            break

    deduped: list[str] = []
    for point in points:
        clean = normalize_space(point)
        if clean and clean not in deduped:
            deduped.append(clean)
        if len(deduped) >= limit:
            break
    return deduped


def _suggest_visual_type(blocks: list[dict[str, Any]], text: str) -> str:
    if any(block.get("type") == "table" for block in blocks):
        return "editable_table"
    lower = text.lower()
    if re.search(r"\b(phase|step|sequence|launch|roadmap|timeline)\b", lower):
        return "timeline_or_process"
    if re.search(r"\b(risk|mitigation|impact|priority)\b", lower):
        return "matrix"
    if extract_data_points(text):
        return "data_cards"
    if len(_supporting_points(blocks, 10)) >= 5:
        return "structured_bullets"
    return "two_column_story"


def _display_focus(visual_type: str) -> str:
    mapping = {
        "editable_table": "Use a compact table with clear column hierarchy.",
        "timeline_or_process": "Show sequence and dependencies across stages.",
        "matrix": "Compare issues by impact, priority, or mitigation path.",
        "data_cards": "Elevate quantitative proof points into metric cards.",
        "structured_bullets": "Group key messages into concise business bullets.",
        "two_column_story": "Pair the core claim with supporting rationale.",
    }
    return mapping.get(visual_type, "Use a structured business summary.")


def _block_text(block: dict[str, Any]) -> str:
    if block.get("type") == "list":
        return " ".join(block.get("items", []))
    if block.get("type") == "table":
        return " ".join(" ".join(row) for row in block.get("rows", []))
    return block.get("text", "")


def _merge_short_segments(segments: list[dict[str, Any]], min_chars: int) -> list[dict[str, Any]]:
    if not segments:
        return []

    merged: list[dict[str, Any]] = []
    buffer: dict[str, Any] | None = None
    for segment in segments:
        if buffer is None:
            buffer = dict(segment)
            continue

        if buffer["content_char_count"] < min_chars:
            buffer = _combine_segments(buffer, segment)
        else:
            merged.append(buffer)
            buffer = dict(segment)

    if buffer is not None:
        if merged and buffer["content_char_count"] < min_chars:
            merged[-1] = _combine_segments(merged[-1], buffer)
        else:
            merged.append(buffer)
    return merged


def _combine_segments(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    title = first["title"]
    if second["title"] not in title:
        title = f"{title} / {second['title']}"
    points = first.get("supporting_points", []) + second.get("supporting_points", [])
    data_points = first.get("data_points", []) + second.get("data_points", [])
    core_message = first.get("core_message") if first.get("supporting_points") else second.get("core_message")
    return {
        **first,
        "title": title,
        "core_message": core_message,
        "supporting_points": points[:8],
        "data_points": list(dict.fromkeys(data_points))[:6],
        "suggested_visual_type": first.get("suggested_visual_type") or second.get("suggested_visual_type"),
        "display_focus": first.get("display_focus") or second.get("display_focus"),
        "source_block_ids": first.get("source_block_ids", []) + second.get("source_block_ids", []),
        "content_char_count": first.get("content_char_count", 0) + second.get("content_char_count", 0),
    }
