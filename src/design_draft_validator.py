from __future__ import annotations

import argparse
from pathlib import Path
import re


REQUIRED_SECTIONS = (
    "Page conclusion",
    "Semantic relationship",
    "Visual argument",
    "Canvas",
    "Regions",
    "Evidence mapping",
    "Visual encoding",
    "Hierarchy and reading path",
    "Typography",
    "Style",
    "Anti-template constraints",
    "Approval checklist",
)

DESIGN_CORE_SECTIONS = (
    "Page conclusion",
    "Semantic relationship",
    "Visual argument",
    "Evidence mapping",
    "Visual encoding",
    "Hierarchy and reading path",
    "Anti-template constraints",
)

UNRESOLVED_MARKERS = ("TODO", "TBD", "待补充", "待确认", "<fill", "[fill", "???")


def validate_design_draft(
    text: str,
    base_text: str | None = None,
    required_evidence: list[str] | None = None,
    required_source_block_ids: list[str] | None = None,
    required_data_points: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    sections = _parse_sections(text)

    upper_text = text.upper()
    if any(marker.upper() in upper_text for marker in UNRESOLVED_MARKERS):
        errors.append("design draft contains an unresolved placeholder")

    for heading in REQUIRED_SECTIONS:
        body = sections.get(heading, "").strip()
        if not body:
            errors.append(f"missing or empty required section: {heading}")

    if len(text.strip()) < 900:
        errors.append("design draft is too short to be a production specification")

    encoding = sections.get("Visual encoding", "")
    if encoding and not any(token in encoding.lower() for token in ("axis", "scale", "unit", "label", "annotation", "坐标", "尺度", "单位", "标签", "标注")):
        errors.append("Visual encoding must specify drawable encoding details")

    hierarchy = sections.get("Hierarchy and reading path", "")
    if hierarchy and not any(token in hierarchy.lower() for token in ("primary", "first", "reading", "第一", "主视觉", "阅读")):
        errors.append("Hierarchy and reading path must identify the primary visual or reading order")

    if base_text is not None:
        base_sections = _parse_sections(base_text)
        for heading in DESIGN_CORE_SECTIONS:
            if sections.get(heading, "").strip() != base_sections.get(heading, "").strip():
                errors.append(f"layout-only revision changed locked design core: {heading}")
        if len(text.strip()) < len(base_text.strip()) * 0.85:
            errors.append("layout-only revision removed too much design detail")

    evidence_mapping = sections.get("Evidence mapping", "")
    for item in required_evidence or []:
        if not _normalized_contains(evidence_mapping, item):
            errors.append(f"design draft omits required supporting evidence: {item}")
    for value in required_data_points or []:
        if not _normalized_contains(evidence_mapping, value):
            errors.append(f"design draft omits required quantitative evidence: {value}")
    for block_id in required_source_block_ids or []:
        if not _normalized_contains(evidence_mapping, block_id):
            errors.append(f"design draft omits source coverage mapping for {block_id}")

    return errors


def _normalized_contains(haystack: str, needle: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r"\s+", "", str(value)).casefold()

    return normalize(needle) in normalize(haystack)


def _parse_sections(text: str) -> dict[str, str]:
    aliases = {heading.lower(): heading for heading in REQUIRED_SECTIONS}
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        candidate = raw_line.strip().lstrip("#").strip().rstrip(":：").strip()
        heading = aliases.get(candidate.lower())
        if heading:
            current = heading
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(raw_line)
    return {heading: "\n".join(lines).strip() for heading, lines in sections.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a page visual design draft contract.")
    parser.add_argument("draft", type=Path)
    parser.add_argument("--base", type=Path, help="Approved base draft for a layout-only revision")
    args = parser.parse_args()

    text = args.draft.read_text(encoding="utf-8")
    base_text = args.base.read_text(encoding="utf-8") if args.base else None
    errors = validate_design_draft(text, base_text)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: design draft contract is complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
