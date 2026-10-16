from __future__ import annotations

from typing import Any


EXPRESSIVE_KEYWORDS = (
    "ecosystem", "platform", "network", "capability", "supply chain", "growth",
    "expansion", "evolution", "journey", "生态", "平台", "网络", "能力", "供应链",
    "增长", "扩张", "演进", "历程",
)


def route_composition(segment: dict[str, Any], density_context: dict[str, float] | None = None) -> dict[str, Any]:
    """Return a complete, deterministic page-composition decision contract."""
    visual_type = segment.get("suggested_visual_type", "structured_bullets")
    text = " ".join(
        [segment.get("title", ""), segment.get("core_message", "")]
        + segment.get("supporting_points", [])
    ).lower()
    point_count = len(segment.get("supporting_points", []))
    char_count = int(segment.get("content_char_count", 0))
    density_score, evidence_load, density_rationale = _density_score(
        segment, point_count, char_count, bool(segment.get("data_points")), density_context
    )

    if visual_type == "editable_table":
        decision = _utility_decision("Structured Evidence / Table", "Evidence Table", density_score)
    elif visual_type == "timeline_or_process" and not _contains_expressive_intent(text):
        decision = _utility_decision("Utility / Process", "Multi-track Process", density_score)
    elif visual_type == "matrix":
        decision = _utility_decision("Structured Evidence / Matrix", "Process Matrix", density_score)
    elif _contains_expressive_intent(text):
        decision = _expressive_decision(text, density_score)
    elif visual_type == "data_cards":
        decision = _analytical_decision("Analytical / Data Storytelling", "Chart + Table Evidence", density_score)
    else:
        decision = _analytical_decision("Analytical / Claim + Proof", "Claim + Proof Split", density_score)
    decision["information_density"].update({"evidence_load": evidence_load, "rationale": density_rationale})
    return decision


def _density_score(
    segment: dict[str, Any],
    point_count: int,
    char_count: int,
    has_data: bool,
    context: dict[str, float] | None,
) -> tuple[int, float, str]:
    evidence_load = float(
        segment.get("evidence_load")
        or (len(segment.get("source_block_ids", [])) * 0.6 + point_count * 0.8 + len(segment.get("data_points", [])) + char_count / 500)
    )
    median = float((context or {}).get("median", evidence_load or 1))
    minimum = float((context or {}).get("min", evidence_load))
    maximum = float((context or {}).get("max", evidence_load))
    if maximum - minimum < 0.5:
        score = 3
    else:
        position = (evidence_load - minimum) / (maximum - minimum)
        score = max(1, min(5, 1 + round(position * 4)))
    rationale = (
        f"Evidence load {evidence_load:.2f} versus deck median {median:.2f}; "
        "this is a deck-relative pacing measure, not a character-count threshold."
    )
    return score, round(evidence_load, 2), rationale


def _utility_decision(strategy: str, archetype: str, density: int) -> dict[str, Any]:
    return {
        "communication_objective": "让读者快速查找、比较并核对关键信息。",
        "information_density": {"score": density, "rationale": "信息以精确比较和完整性为优先。"},
        "design_intensity": {"level": 2, "rationale": "任务要求高效扫描，克制设计优于主视觉。"},
        "visual_strategy": strategy,
        "visual_proposition": "not_required",
        "design_archetype": archetype,
        "spatial_narrative": {
            "dominant_geometry": "aligned rows and columns",
            "focal_point": "highlighted evidence or decision row",
            "reading_path": "title → highlighted evidence → rows or stages → source note",
        },
        "asset_strategy": {"mode": "native_shapes_and_data", "rationale": "不需要装饰性插画；优先保留数字、表头和对齐关系。"},
    }


def _analytical_decision(strategy: str, archetype: str, density: int) -> dict[str, Any]:
    return {
        "communication_objective": "用主张与可核验的证据支持一个清晰判断。",
        "information_density": {"score": density, "rationale": "需要同时承载结论、解释和数据证据。"},
        "design_intensity": {"level": 3, "rationale": "需要明确的阅读路径，但不应为形式牺牲证据可读性。"},
        "visual_strategy": strategy,
        "visual_proposition": "以结论为锚点，让证据沿同一阅读路径展开。",
        "design_archetype": archetype,
        "spatial_narrative": {
            "dominant_geometry": "claim-to-proof split",
            "focal_point": "the conclusion-led headline and primary evidence",
            "reading_path": "title → key claim → evidence → implication",
        },
        "asset_strategy": {"mode": "evidence_first", "rationale": "优先图表、数据和必要图标；不使用无信息功能的装饰资产。"},
    }


def _expressive_decision(text: str, density: int) -> dict[str, Any]:
    if any(token in text for token in ("map", "geograph", "footprint", "地图", "区域")):
        archetype, geometry = "Map + Evidence", "地图画布与附着证据"
    elif any(token in text for token in ("ecosystem", "platform", "生态", "平台")):
        archetype, geometry = "Integrated Ecosystem Canvas", "以中心为锚点的环绕生态"
    elif any(token in text for token in ("growth", "expansion", "evolution", "journey", "增长", "扩张", "演进", "历程")):
        archetype, geometry = "Growth Journey", "方向性增长路径"
    else:
        archetype, geometry = "Radial Capability Architecture", "中心与卫星能力网络"
    return {
        "communication_objective": "用一个可记忆的空间关系解释核心战略叙事。",
        "information_density": {"score": density, "rationale": "内容需要被统一为一个主导关系，而非并列模块。"},
        "design_intensity": {"level": 4, "rationale": "战略叙事受益于单一主视觉和空间叙事。"},
        "visual_strategy": "Narrative / Hero Composition",
        "visual_proposition": f"以 {geometry} 让观众一眼理解页面的核心关系。",
        "design_archetype": archetype,
        "spatial_narrative": {
            "dominant_geometry": geometry,
            "focal_point": "single central hero or directional anchor",
            "reading_path": "title → hero relationship → attached evidence → implication",
        },
        "asset_strategy": {"mode": "structural_visual", "rationale": "只使用承担信息结构的地图、插画或连接线；资产不是装饰。"},
    }


def _contains_expressive_intent(text: str) -> bool:
    return any(keyword in text for keyword in EXPRESSIVE_KEYWORDS)
