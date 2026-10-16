from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from .utils import PROJECT_ROOT
except ImportError:
    from utils import PROJECT_ROOT


DEFAULT_TAXONOMY = PROJECT_ROOT / "ppt_design_mechanism_library" / "relation_taxonomy.json"


def load_relation_taxonomy(path: Path | None = None) -> dict[str, Any]:
    taxonomy_path = (path or DEFAULT_TAXONOMY).resolve()
    return json.loads(taxonomy_path.read_text(encoding="utf-8"))


def generate_page_structure(page: dict[str, Any]) -> dict[str, Any]:
    """Create the relationship-only page contract used for layout matching.

    Explicit page_structure/structure_hints always win. The fallback is
    deliberately conservative and produces a reviewable artifact rather than
    pretending to understand a complex page from keywords alone.
    """
    explicit = page.get("page_structure") or page.get("structure_hints")
    if isinstance(explicit, dict):
        structure = deepcopy(explicit)
    else:
        structure = _infer_structure(page)

    structure.setdefault("schema_version", "1.0")
    structure.setdefault("page_id", _page_id(page))
    structure.setdefault("sizing", "adaptive")
    structure.setdefault("requirements", [])
    structure.setdefault("forbids", [])
    structure.setdefault("inference", {})
    structure["inference"].setdefault("source", "explicit" if isinstance(explicit, dict) else "conservative_fallback")

    groups = structure.setdefault("groups", [])
    for index, group in enumerate(groups, start=1):
        group.setdefault("id", f"g{index}")
        group.setdefault("position", "any")
        group.setdefault("order", "none")
        group.setdefault("item_refs", [])
        group["item_count"] = int(group.get("item_count", len(group["item_refs"]) or 1))

    structure.setdefault(
        "between_groups",
        {"relation": "single_group" if len(groups) == 1 else "juxtaposed_peer", "mapping": "none"},
    )
    structure["between_groups"].setdefault("mapping", "none")

    errors = validate_page_structure(structure)
    if errors:
        raise ValueError("Invalid page structure: " + "; ".join(errors))
    return structure


def validate_page_structure(structure: dict[str, Any], taxonomy_path: Path | None = None) -> list[str]:
    taxonomy = load_relation_taxonomy(taxonomy_path)
    allowed_group_relations = set(taxonomy["group_relations"])
    allowed_between = set(taxonomy["between_group_relations"])
    allowed_mapping = set(taxonomy["mapping_modes"])
    allowed_order = set(taxonomy["order_modes"])
    allowed_requirements = set(taxonomy["requirements"])
    errors: list[str] = []

    if structure.get("sizing") != "adaptive":
        errors.append("sizing must be adaptive; exact region ratios belong to the design instance")
    groups = structure.get("groups")
    if not isinstance(groups, list) or not groups:
        errors.append("groups must contain at least one group")
        groups = []
    for index, group in enumerate(groups, start=1):
        relation = group.get("relation")
        if relation not in allowed_group_relations:
            errors.append(f"group {index} has unknown relation: {relation}")
        order = group.get("order", "none")
        if order not in allowed_order:
            errors.append(f"group {index} has invalid order mode: {order}")
        count = group.get("item_count")
        if not isinstance(count, int) or count < 1:
            errors.append(f"group {index} item_count must be a positive integer")

    between = structure.get("between_groups", {})
    if between.get("relation") not in allowed_between:
        errors.append(f"unknown between-group relation: {between.get('relation')}")
    if between.get("mapping", "none") not in allowed_mapping:
        errors.append(f"invalid mapping mode: {between.get('mapping')}")
    if len(groups) == 1 and between.get("relation") != "single_group":
        errors.append("a one-group page must use between_groups.relation=single_group")

    unknown_requirements = sorted(set(structure.get("requirements", [])) - allowed_requirements)
    if unknown_requirements:
        errors.append("unknown requirements: " + ", ".join(unknown_requirements))
    return errors


def matching_view(structure: dict[str, Any]) -> dict[str, Any]:
    """Remove source wording and retain only fields allowed to drive matching."""
    return {
        "schema_version": structure.get("schema_version", "1.0"),
        "page_id": structure.get("page_id"),
        "sizing": "adaptive",
        "between_groups": {
            "relation": structure.get("between_groups", {}).get("relation", "single_group"),
            "mapping": structure.get("between_groups", {}).get("mapping", "none"),
        },
        "groups": [
            {
                "id": group.get("id"),
                "position": group.get("position", "any"),
                "relation": group.get("relation"),
                "item_count": group.get("item_count", 1),
                "order": group.get("order", "none"),
                "item_refs": list(group.get("item_refs", [])),
            }
            for group in structure.get("groups", [])
        ],
        "requirements": list(structure.get("requirements", [])),
        "forbids": list(structure.get("forbids", [])),
    }


def build_page_structure_prompt(page: dict[str, Any], taxonomy_path: Path | None = None) -> str:
    """Build the AI instruction used to turn approved content into match elements."""
    taxonomy = load_relation_taxonomy(taxonomy_path)
    payload = {
        "page_number": page.get("page_number") or page.get("slide_number"),
        "title": page.get("title"),
        "page_conclusion": page.get("page_conclusion") or page.get("core_message"),
        "supporting_points": page.get("supporting_points", []),
        "data_points": page.get("data_points", []),
    }
    return (
        "请只根据页面已批准内容之间的关系生成page_structure JSON。\n"
        "不要根据行业、品牌、页面关键词、suggested_visual_type、颜色或现成卡片名称选版式。\n"
        "先判断内容组数量，再判断组间关系、组内关系、是否有顺序、是否需要逐项映射和项目数量。\n"
        "sizing固定写adaptive；不要输出weight_ratio或固定区域比例。\n"
        "如果关系不能确认，使用最保守关系并在inference.review_required写true；不得虚构因果、层级或映射。\n"
        "允许的group relation："
        + ", ".join(taxonomy["group_relations"])
        + "。\n允许的between-group relation："
        + ", ".join(taxonomy["between_group_relations"])
        + "。\n允许的requirements："
        + ", ".join(taxonomy["requirements"])
        + "。\n\n页面内容：\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n\n只输出合法JSON，不输出解释。"
    )


def _infer_structure(page: dict[str, Any]) -> dict[str, Any]:
    content = _page_content_text(page)
    lowered = content.lower()
    point_refs = [f"supporting_points[{index}]" for index, _ in enumerate(page.get("supporting_points", []))]
    point_count = max(1, len(point_refs))
    has_dates = bool(re.search(r"(?:19|20)\d{2}(?:年|[-/.]\d{1,2})?|\bT[+-]?\d+\b", content, flags=re.IGNORECASE))
    has_series_language = any(token in lowered for token in ("趋势", "走势", "历年", "过去", "以来", "同比", "环比", "time series"))
    has_event_windows = any(token in lowered for token in ("事件窗口", "危机期间", "冲击期间", "恢复时间", "回撤区间"))

    if has_dates and has_event_windows:
        return _one_group(
            page,
            "time_series",
            point_count,
            point_refs,
            order="required",
            requirements=["time_axis", "dated_events", "numeric_series"],
        )
    if has_dates and has_series_language and len(page.get("data_points", [])) >= 2:
        return _one_group(
            page,
            "time_series",
            point_count,
            point_refs,
            order="required",
            requirements=["time_axis", "numeric_series"],
        )
    if any(token in lowered for token in ("循环", "闭环", "反馈", "反复迭代", "feedback loop")):
        return _one_group(page, "cycle", point_count, point_refs, order="required", requirements=["feedback_edges"])
    if any(token in lowered for token in ("共同指标", "统一口径", "同一维度", "横向比较", "shared metrics")):
        return _one_group(
            page,
            "shared_metrics_comparison",
            point_count,
            point_refs,
            requirements=["shared_scale"],
        )
    if any(token in lowered for token in ("逐项对应", "分别对应", "交叉矩阵", "行列", "matrix")):
        return _one_group(page, "matrix", point_count, point_refs, requirements=["precise_matrix"])
    if has_dates:
        return _one_group(page, "temporal_sequence", point_count, point_refs, order="required", requirements=["time_axis"])
    if any(token in lowered for token in ("阶段", "步骤", "首先", "其次", "随后", "最后")):
        return _one_group(page, "ordered_sequence", point_count, point_refs, order="required")
    return _one_group(page, "parallel_equal", point_count, point_refs)


def _one_group(
    page: dict[str, Any],
    relation: str,
    item_count: int,
    item_refs: list[str],
    order: str = "none",
    requirements: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "page_id": _page_id(page),
        "sizing": "adaptive",
        "between_groups": {"relation": "single_group", "mapping": "none"},
        "groups": [
            {
                "id": "g1",
                "position": "any",
                "relation": relation,
                "item_count": item_count,
                "order": order,
                "item_refs": item_refs,
            }
        ],
        "requirements": requirements or [],
        "forbids": [],
        "inference": {"source": "conservative_fallback", "review_required": True},
    }


def _page_id(page: dict[str, Any]) -> str:
    number = int(page.get("page_number") or page.get("slide_number") or 1)
    return f"page_{number:02d}"


def _page_content_text(page: dict[str, Any]) -> str:
    values: list[str] = [str(page.get("title", "")), str(page.get("page_conclusion", ""))]
    values.extend(str(value) for value in page.get("supporting_points", []))
    values.extend(str(value) for value in page.get("data_points", []))
    return "\n".join(value for value in values if value)
