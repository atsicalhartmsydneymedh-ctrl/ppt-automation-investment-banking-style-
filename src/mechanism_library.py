from __future__ import annotations

import itertools
import json
import re
from pathlib import Path
from typing import Any

try:
    from .utils import PROJECT_ROOT
except ImportError:
    from utils import PROJECT_ROOT


DEFAULT_REGISTRY = PROJECT_ROOT / "ppt_design_mechanism_library" / "mechanism_registry.yaml"
DEFAULT_VARIANT_MANIFEST = PROJECT_ROOT / "ppt_design_reverse_engineering_rank4" / "source_variants.json"
REGISTRY_LINE = re.compile(
    r'^\s*-\s*\{id:\s*([^,]+),\s*relation:\s*"([^"]+)",\s*file:\s*"([^"]+)"\s*\}\s*$'
)
CARD_V3_BLOCK = re.compile(r"```json mechanism-card-v3\s*(\{.*?\})\s*```", re.DOTALL)
TIER_ORDER = {"A": 0, "B": 1, "C": 2, "REJECT": 9}


def load_mechanism_registry(registry_path: Path | None = None) -> list[dict[str, Any]]:
    path = (registry_path or DEFAULT_REGISTRY).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Mechanism registry not found: {path}")
    mechanisms: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = REGISTRY_LINE.match(line)
        if not match:
            continue
        mechanism_id, relation, relative_file = (value.strip() for value in match.groups())
        card_path = (path.parent / relative_file).resolve()
        mechanisms.append({"id": mechanism_id, "relation": relation, "file": str(card_path)})
    return mechanisms


def load_layout_variants(
    mechanism_id: str | None = None,
    manifest_path: Path | None = None,
) -> list[dict[str, Any]]:
    path = (manifest_path or DEFAULT_VARIANT_MANIFEST).resolve()
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    variants = payload.get("variants", [])
    if not isinstance(variants, list):
        raise ValueError(f"Layout variant manifest must contain a variants list: {path}")
    normalized = [dict(item) for item in variants if isinstance(item, dict)]
    if mechanism_id is None:
        return normalized
    return [item for item in normalized if item.get("parent_mechanism") == mechanism_id]


def select_layout_variant(
    mechanism_id: str,
    page_structure: dict[str, Any],
    manifest_path: Path | None = None,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for variant in load_layout_variants(mechanism_id, manifest_path=manifest_path):
        evaluation = _evaluate_layout_variant(page_structure, variant.get("match", {}))
        if evaluation["match_tier"] != "REJECT":
            candidates.append({**variant, **evaluation})
    if not candidates:
        return None
    candidates.sort(key=lambda item: (TIER_ORDER[item["match_tier"]], item["adaptation_count"], item["id"]))
    return candidates[0]


def select_mechanism(
    relation: str,
    registry_path: Path | None = None,
    context: str = "",
) -> dict[str, Any]:
    ranked = rank_mechanisms(relation, registry_path=registry_path, context=context, limit=3)
    if not ranked:
        raise ValueError("Mechanism registry contains no executable entries.")
    selected = dict(ranked[0])
    selected["candidate_matches"] = [
        {key: item.get(key) for key in ("id", "relation", "match_score", "source")}
        for item in ranked
    ]
    return selected


def select_mechanism_for_structure(
    page_structure: dict[str, Any],
    registry_path: Path | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    ranked, rejected = rank_mechanisms_for_structure(
        page_structure,
        registry_path=registry_path,
        limit=limit,
        include_rejected=True,
    )
    if not ranked:
        reasons = "; ".join(
            f"{item['id']}: {', '.join(item.get('rejection_reasons', []))}" for item in rejected[:5]
        )
        raise ValueError(f"No mechanism card passes the page-structure hard gates. {reasons}")
    selected = dict(ranked[0])
    selected["candidate_matches"] = [
        {
            key: item.get(key)
            for key in ("id", "relation", "match_tier", "adaptation_count", "adaptations", "source")
        }
        for item in ranked
    ]
    selected["rejected_candidates"] = [
        {"id": item["id"], "reasons": item.get("rejection_reasons", [])} for item in rejected[:8]
    ]
    return selected


def rank_mechanisms_for_structure(
    page_structure: dict[str, Any],
    registry_path: Path | None = None,
    limit: int = 3,
    include_rejected: bool = False,
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Match controlled page relations to v3 card signatures.

    Region ratios are deliberately absent. A card passes only when its
    relationship topology, ordering, mapping, capacity, and evidence-shape
    requirements are compatible with the page contract.
    """
    passed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in load_mechanism_registry(registry_path):
        fields = _card_fields(Path(item["file"]))
        contract = fields.get("card_contract")
        if not isinstance(contract, dict):
            rejected.append({**item, "match_tier": "REJECT", "rejection_reasons": ["missing v3 card contract"]})
            continue
        evaluation = _evaluate_signature(page_structure, contract.get("match_signature", {}))
        result = {**item, **fields, **evaluation}
        if evaluation["match_tier"] == "REJECT":
            rejected.append(result)
        else:
            passed.append(result)
    passed.sort(key=lambda item: (TIER_ORDER[item["match_tier"]], item["adaptation_count"], item["id"]))
    rejected.sort(key=lambda item: (len(item.get("rejection_reasons", [])), item["id"]))
    limited = passed[: max(1, limit)]
    if include_rejected:
        return limited, rejected
    return limited


def rank_mechanisms(
    relation: str,
    registry_path: Path | None = None,
    context: str = "",
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return reusable PPT mechanisms ranked by semantics and page evidence.

    Relation fit remains the primary signal. The page context is used to
    disambiguate nearby mechanisms through their match/reject conditions.
    """
    mechanisms = load_mechanism_registry(registry_path)
    normalized = _normalize_relation(relation)
    ranked: list[dict[str, Any]] = []
    for item in mechanisms:
        fields = _card_fields(Path(item["file"]))
        relation_score = _relation_score(normalized, _normalize_relation(item["relation"]))
        exact = _normalize_relation(item["relation"]) == normalized
        context_score = _text_overlap_score(context, fields.get("match_when", ""))
        reject_score = _text_overlap_score(context, fields.get("reject_when", ""))
        score = 1.0 if exact else max(0.0, 0.82 * relation_score + 0.18 * context_score - 0.25 * reject_score)
        ranked.append(
            {
                **item,
                **fields,
                "match_score": round(score, 4),
                "relation_score": round(relation_score, 4),
                "context_score": round(context_score, 4),
                "reject_score": round(reject_score, 4),
            }
        )
    ranked.sort(key=lambda item: (item["match_score"], item["context_score"]), reverse=True)
    return ranked[: max(1, limit)]


def get_mechanism(mechanism_id: str, registry_path: Path | None = None) -> dict[str, Any] | None:
    for mechanism in load_mechanism_registry(registry_path):
        if mechanism["id"] == mechanism_id:
            return {
                **mechanism,
                "match_score": 1.0,
                **_card_fields(Path(mechanism["file"])),
                "layout_variants": load_layout_variants(mechanism_id),
            }
    return None


def _evaluate_layout_variant(page: dict[str, Any], match: dict[str, Any]) -> dict[str, Any]:
    requirements = set(page.get("requirements", []))
    required = set(match.get("requires", []))
    missing = sorted(required - requirements)
    if missing:
        return {
            "match_tier": "REJECT",
            "adaptation_count": 999,
            "adaptations": [],
            "rejection_reasons": ["missing requirements: " + ", ".join(missing)],
        }

    page_groups = page.get("groups", [])
    variant_groups = [_parse_variant_group(value) for value in match.get("groups", [])]
    if len(page_groups) != len(variant_groups):
        return {
            "match_tier": "REJECT",
            "adaptation_count": 999,
            "adaptations": [],
            "rejection_reasons": [f"group_count {len(page_groups)} != {len(variant_groups)}"],
        }

    best_adaptations: list[str] | None = None
    for permutation in itertools.permutations(variant_groups):
        adaptations: list[str] = []
        compatible = True
        for page_group, expected in zip(page_groups, permutation):
            if page_group.get("relation") != expected["relation"]:
                compatible = False
                break
            count = int(page_group.get("item_count", 0))
            if not expected["min"] <= count <= expected["max"]:
                compatible = False
                break
        if compatible and (best_adaptations is None or len(adaptations) < len(best_adaptations)):
            best_adaptations = adaptations

    if best_adaptations is None:
        return {
            "match_tier": "REJECT",
            "adaptation_count": 999,
            "adaptations": [],
            "rejection_reasons": ["group relations or capacities do not match variant"],
        }
    tier = "A" if not best_adaptations else "B"
    return {
        "match_tier": tier,
        "adaptation_count": len(best_adaptations),
        "adaptations": best_adaptations,
        "rejection_reasons": [],
    }


def _parse_variant_group(value: str) -> dict[str, Any]:
    relation, _, count_text = str(value).partition(":")
    if not relation or not count_text:
        raise ValueError(f"Invalid variant group pattern: {value}")
    if "-" in count_text:
        minimum, maximum = (int(item) for item in count_text.split("-", 1))
    else:
        minimum = maximum = int(count_text)
    return {"relation": relation, "min": minimum, "max": maximum}


def _card_fields(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "match_when": "",
            "reject_when": "",
            "slots": "",
            "layout_dna": "",
            "qa_specific": "",
            "source": "",
        }
    text = path.read_text(encoding="utf-8")
    contract = _card_contract(text)
    if contract:
        layout = contract.get("layout_contract", {})
        hard_fail = contract.get("hard_fail", [])
        return {
            "match_when": json.dumps(contract.get("match_signature", {}), ensure_ascii=False),
            "reject_when": json.dumps(hard_fail, ensure_ascii=False),
            "slots": json.dumps(contract.get("data_contract", {}), ensure_ascii=False),
            "layout_dna": json.dumps(layout.get("geometry", []), ensure_ascii=False),
            "qa_specific": json.dumps(hard_fail, ensure_ascii=False),
            "source": json.dumps(contract.get("source", {}), ensure_ascii=False),
            "card_contract": contract,
        }
    fields: dict[str, str] = {}
    for key in ("match_when", "reject_when", "slots", "layout_dna", "qa_specific", "source"):
        match = re.search(rf"^{key}:\s*(.+)$", text, flags=re.MULTILINE)
        fields[key] = match.group(1).strip() if match else ""
    return fields


def _card_contract(text: str) -> dict[str, Any] | None:
    match = CARD_V3_BLOCK.search(text)
    if not match:
        return None
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _evaluate_signature(page: dict[str, Any], signature: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    adaptations: list[str] = []
    page_groups = page.get("groups", [])
    card_groups = signature.get("groups", [])
    group_range = signature.get("group_count", {})
    if not _in_range(len(page_groups), group_range):
        reasons.append(f"group_count {len(page_groups)} outside {_range_text(group_range)}")

    between = page.get("between_groups", {})
    accepted_between = signature.get("between_groups", [])
    if between.get("relation") not in accepted_between:
        reasons.append(f"between_groups={between.get('relation')} not in {accepted_between}")

    page_mapping = between.get("mapping", "none")
    card_mapping = signature.get("mapping", "none")
    if card_mapping == "required" and page_mapping != "required":
        reasons.append("card requires explicit mapping")
    elif card_mapping == "none" and page_mapping == "required":
        reasons.append("card forbids required cross-group mapping")

    page_requirements = set(page.get("requirements", []))
    card_requirements = set(signature.get("requires", []))
    missing_requirements = sorted(card_requirements - page_requirements)
    if missing_requirements:
        reasons.append("missing requirements: " + ", ".join(missing_requirements))
    page_forbids = set(page.get("forbids", []))
    conflicts = sorted(page_forbids & card_requirements)
    if conflicts:
        reasons.append("page forbids card requirements: " + ", ".join(conflicts))
    card_forbids = set(signature.get("forbids", []))
    if page_mapping == "required" and "explicit_mapping" in card_forbids:
        reasons.append("page mapping conflicts with card forbid rule")

    if not reasons and len(page_groups) == len(card_groups):
        group_evaluation = _best_group_assignment(page_groups, card_groups)
        if group_evaluation is None:
            reasons.append("no compatible assignment between page groups and card groups")
        else:
            adaptations.extend(group_evaluation)

    if reasons:
        return {
            "match_tier": "REJECT",
            "adaptation_count": 999,
            "adaptations": [],
            "passed_gates": [],
            "rejection_reasons": reasons,
        }
    tier = "A" if not adaptations else "B" if len(adaptations) <= 2 else "C"
    return {
        "match_tier": tier,
        "adaptation_count": len(adaptations),
        "adaptations": adaptations,
        "passed_gates": ["group_count", "between_groups", "mapping", "capacity", "order", "requirements"],
        "rejection_reasons": [],
    }


def _best_group_assignment(page_groups: list[dict[str, Any]], card_groups: list[dict[str, Any]]) -> list[str] | None:
    best: list[str] | None = None
    for permutation in itertools.permutations(card_groups):
        adaptations: list[str] = []
        compatible = True
        for page_group, card_group in zip(page_groups, permutation):
            relation = page_group.get("relation")
            if relation not in card_group.get("relations", []):
                compatible = False
                break
            if not _in_range(int(page_group.get("item_count", 0)), card_group.get("count", {})):
                compatible = False
                break
            page_order = page_group.get("order", "none")
            card_order = card_group.get("order", "optional")
            if card_order == "required" and page_order != "required":
                compatible = False
                break
            if card_order == "none" and page_order == "required":
                compatible = False
                break
            card_position = card_group.get("position", "any")
            page_position = page_group.get("position", "any")
            if card_position != "any" and page_position not in ("any", card_position):
                compatible = False
                break
            if card_position != "any" and page_position == "any":
                adaptations.append(f"assign {page_group.get('id', 'group')} to {card_position}")
        if compatible and (best is None or len(adaptations) < len(best)):
            best = adaptations
    return best


def _in_range(value: int, range_spec: dict[str, Any]) -> bool:
    return int(range_spec.get("min", value)) <= value <= int(range_spec.get("max", value))


def _range_text(range_spec: dict[str, Any]) -> str:
    return f"{range_spec.get('min', '?')}–{range_spec.get('max', '?')}"


def _normalize_relation(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _relation_score(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _text_overlap_score(left: str, right: str) -> float:
    left_features = _text_features(left)
    right_features = _text_features(right)
    if not left_features or not right_features:
        return 0.0
    return len(left_features & right_features) / len(right_features)


def _text_features(value: str) -> set[str]:
    lowered = value.lower()
    latin = set(re.findall(r"[a-z0-9%]+", lowered))
    cjk_runs = re.findall(r"[\u3400-\u9fff]+", lowered)
    cjk_bigrams = {
        run[index : index + 2]
        for run in cjk_runs
        for index in range(max(0, len(run) - 1))
    }
    return latin | cjk_bigrams
