from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.mechanism_library import get_mechanism, load_layout_variants, load_mechanism_registry  # noqa: E402
from src.page_structure import load_relation_taxonomy  # noqa: E402


def audit() -> dict[str, Any]:
    taxonomy = load_relation_taxonomy()
    group_relations = set(taxonomy["group_relations"])
    between_relations = set(taxonomy["between_group_relations"])
    requirements = set(taxonomy["requirements"])
    errors: list[str] = []
    cards = load_mechanism_registry()
    seen: set[str] = set()

    for item in cards:
        mechanism_id = item["id"]
        if mechanism_id in seen:
            errors.append(f"duplicate registry id: {mechanism_id}")
        seen.add(mechanism_id)
        mechanism = get_mechanism(mechanism_id)
        if not mechanism or not isinstance(mechanism.get("card_contract"), dict):
            errors.append(f"{mechanism_id}: missing v3 card contract")
            continue
        contract = mechanism["card_contract"]
        if contract.get("schema_version") != "3.0":
            errors.append(f"{mechanism_id}: wrong schema_version")
        if contract.get("id") != mechanism_id:
            errors.append(f"{mechanism_id}: embedded id mismatch")
        signature = contract.get("match_signature", {})
        if "weight_ratio" in json.dumps(signature, ensure_ascii=False):
            errors.append(f"{mechanism_id}: fixed region ratio leaked into match signature")
        if not set(signature.get("between_groups", [])) <= between_relations:
            errors.append(f"{mechanism_id}: unknown between-group relation")
        if not set(signature.get("requires", [])) <= requirements:
            errors.append(f"{mechanism_id}: unknown requirement")
        groups = signature.get("groups", [])
        if not groups:
            errors.append(f"{mechanism_id}: no group patterns")
        for index, group in enumerate(groups, start=1):
            if not set(group.get("relations", [])) <= group_relations:
                errors.append(f"{mechanism_id}: group {index} uses unknown relation")
            bounds = group.get("count", {})
            if int(bounds.get("min", 0)) < 1 or int(bounds.get("max", 0)) < int(bounds.get("min", 0)):
                errors.append(f"{mechanism_id}: invalid group {index} capacity")
        if contract.get("layout_contract", {}).get("sizing") != "adaptive":
            errors.append(f"{mechanism_id}: layout sizing must be adaptive")
        if not contract.get("layout_contract", {}).get("geometry"):
            errors.append(f"{mechanism_id}: missing layout geometry")
        if not contract.get("hard_fail"):
            errors.append(f"{mechanism_id}: missing hard-fail rules")

    variants = load_layout_variants()
    variant_ids: set[str] = set()
    for variant in variants:
        variant_id = str(variant.get("id", ""))
        if not re.fullmatch(r"R4-S\d{2}", variant_id):
            errors.append(f"invalid variant id: {variant_id}")
        if variant_id in variant_ids:
            errors.append(f"duplicate variant id: {variant_id}")
        variant_ids.add(variant_id)
        if variant.get("parent_mechanism") not in seen:
            errors.append(f"{variant_id}: unknown parent mechanism {variant.get('parent_mechanism')}")
        for field in ("relationship", "match", "data_contract", "layout_contract", "encoding_contract", "adaptation", "hard_fail", "source"):
            if not variant.get(field):
                errors.append(f"{variant_id}: missing {field}")
        if set(variant.get("source", {})) != {"reference_id"}:
            errors.append(f"{variant_id}: source metadata was not sanitized")

    return {
        "registered_cards": len(cards),
        "unique_ids": len(seen),
        "layout_variants": len(variants),
        "unique_variant_ids": len(variant_ids),
        "schema": "3.0",
        "errors": errors,
        "status": "pass" if not errors and len(cards) >= 68 and len(variants) == 41 else "fail",
    }


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "pass" else 1)
