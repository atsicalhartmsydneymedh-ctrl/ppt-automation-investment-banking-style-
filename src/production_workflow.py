from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any

try:
    from .design_draft_validator import validate_design_draft
    from .gpt_mockup_generator import MockupGenerationError, generate_slide_mockups
    from .image_qa import audit_effect_image
    from .mechanism_library import get_mechanism, select_layout_variant, select_mechanism, select_mechanism_for_structure
    from .narrative_ai import (
        NarrativeAIError,
        NarrativeAIUnavailable,
        build_ai_narrative_prompt,
        build_order_neutral_source_payload,
        build_restructure_report,
        deck_contract_schema,
        generate_ai_deck_contract,
        sanitize_parsed_for_narrative,
        restructure_report_text,
    )
    from .page_structure import build_page_structure_prompt, generate_page_structure, matching_view, validate_page_structure
    from .prompt_compiler import compile_effect_image_prompt
    from .slide_planner import create_slide_plans, write_slide_plans
    from .utils import ensure_dir, read_json, write_json, write_text
except ImportError:
    from design_draft_validator import validate_design_draft
    from gpt_mockup_generator import MockupGenerationError, generate_slide_mockups
    from image_qa import audit_effect_image
    from mechanism_library import get_mechanism, select_layout_variant, select_mechanism, select_mechanism_for_structure
    from narrative_ai import (
        NarrativeAIError,
        NarrativeAIUnavailable,
        build_ai_narrative_prompt,
        build_order_neutral_source_payload,
        build_restructure_report,
        deck_contract_schema,
        generate_ai_deck_contract,
        sanitize_parsed_for_narrative,
        restructure_report_text,
    )
    from page_structure import build_page_structure_prompt, generate_page_structure, matching_view, validate_page_structure
    from prompt_compiler import compile_effect_image_prompt
    from slide_planner import create_slide_plans, write_slide_plans
    from utils import ensure_dir, read_json, write_json, write_text


class ProductionWorkflowError(RuntimeError):
    pass


PRODUCTION_DIRS = (
    "parsed_content",
    "assets",
    "content_map",
    "page_structures",
    "mechanism_matches",
    "content_arrangements",
    "evidence_specs",
    "design_drafts",
    "slide_plans",
    "slide_images",
    "approvals",
    "ppt_rebuild_packages",
)

UNRESOLVED_MARKERS = ("TODO", "TBD", "待补充", "待确认", "<fill", "[fill", "???")


def initialize_production_run(
    output_dir: Path,
    parsed: dict[str, Any],
    core_reference_path: str,
    core_reference_style: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    for dirname in PRODUCTION_DIRS:
        ensure_dir(output_dir / dirname)

    raw_parsed = parsed
    project_brief = config.get("project_brief", {}) if isinstance(config.get("project_brief"), dict) else {}
    configured_ai = config.get("narrative_ai", {})
    ai_settings = {**configured_ai, "project_brief": project_brief}
    parsed, exclusions = sanitize_parsed_for_narrative(
        raw_parsed,
        ai_settings.get("excluded_content_patterns", []),
    )
    write_json(output_dir / "parsed_content" / "parsed_blocks_raw.json", raw_parsed)
    write_json(output_dir / "parsed_content" / "parsed_blocks.json", parsed)
    write_json(output_dir / "content_map" / "project_brief.json", project_brief)
    write_json(output_dir / "content_map" / "narrative_exclusions.json", exclusions)
    write_json(output_dir / "assets" / "core_reference_style.json", core_reference_style)
    write_text(
        output_dir / "assets" / "core_reference_style_prompt.md",
        (core_reference_style.get("style_prompt") or _style_prompt(core_reference_style)).strip() + "\n",
    )
    write_json(output_dir / "config_snapshot.json", config)

    inventory = _source_inventory(parsed)
    write_json(output_dir / "content_map" / "source_inventory.json", inventory)
    write_text(output_dir / "content_map" / "full_report_content_map.txt", _content_map_text(parsed))
    source_payload = build_order_neutral_source_payload(parsed)
    narrative_prompt = build_ai_narrative_prompt(source_payload, ai_settings)
    narrative_schema = deck_contract_schema()
    write_json(output_dir / "content_map" / "narrative_source_payload.json", source_payload)
    write_text(output_dir / "content_map" / "narrative_ai_prompt.txt", narrative_prompt)
    write_json(output_dir / "content_map" / "narrative_deck_contract_schema.json", narrative_schema)

    contract_path = output_dir / "content_map" / "deck_contract.json"
    contract: dict[str, Any] | None = None
    if contract_path.exists():
        existing = read_json(contract_path)
        if existing.get("pagination_method") != "ai_full_report_semantic_reorganization":
            raise ProductionWorkflowError(
                "An existing non-AI deck_contract.json is present. It was not overwritten. "
                "Use a new output directory or move the old contract before rerunning AI pagination."
            )
        contract = existing
    else:
        try:
            ai_result = generate_ai_deck_contract(parsed, ai_settings)
        except NarrativeAIUnavailable as exc:
            return _narrative_ai_pending_manifest(
                output_dir,
                parsed,
                core_reference_path,
                str(exc),
            )
        except NarrativeAIError as exc:
            raise ProductionWorkflowError(str(exc)) from exc
        write_json(output_dir / "content_map" / "narrative_ai_responses.json", ai_result.responses)
        contract = _enrich_ai_deck_contract(ai_result.contract, project_brief)
        write_json(contract_path, contract)
        restructure = build_restructure_report(contract, parsed)
        write_json(output_dir / "content_map" / "restructure_report.json", restructure)
        write_text(output_dir / "content_map" / "restructure_report.txt", restructure_report_text(restructure))
        write_text(output_dir / "content_map" / "storyline_readthrough.txt", _storyline_readthrough_text(contract))
    if contract is None:
        raise ProductionWorkflowError("Narrative AI did not produce a deck contract.")
    for page in contract.get("pages", []):
        structure = generate_page_structure(page)
        page["page_structure"] = structure
        write_json(output_dir / "page_structures" / f"page_{page['page_number']:02d}.json", structure)
        write_text(
            output_dir / "page_structures" / f"page_{page['page_number']:02d}_prompt.txt",
            build_page_structure_prompt(page),
        )
    write_json(contract_path, contract)

    state_path = output_dir / "workflow_state.json"
    state = read_json(state_path) if state_path.exists() else _new_state(parsed, core_reference_path)
    state["updated_at"] = _now()
    state["status"] = "prepared" if not state.get("deck_approved_at") else state.get("status", "deck_approved")
    write_json(state_path, state)

    manifest = {
        "mode": "production",
        "status": state["status"],
        "source_report": parsed.get("source_path"),
        "core_reference": str(core_reference_path),
        "workflow_state": str(state_path),
        "deck_contract": str(contract_path),
        "source_inventory": str(output_dir / "content_map" / "source_inventory.json"),
        "project_brief": str(output_dir / "content_map" / "project_brief.json"),
        "storyline_readthrough": str(output_dir / "content_map" / "storyline_readthrough.txt"),
        "restructure_report": str(output_dir / "content_map" / "restructure_report.json"),
        "next_action": "Review deck_contract.json, then run the approve-deck stage.",
    }
    write_json(output_dir / "run_manifest.json", manifest)
    return manifest


def validate_deck_contract(contract: dict[str, Any], parsed: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    pages = contract.get("pages") or []
    if not pages:
        return ["deck contract must contain at least one page"]

    valid_ids = {block.get("id") for block in parsed.get("blocks", []) if block.get("id")}
    assigned: list[str] = []
    page_numbers: list[int] = []
    for index, page in enumerate(pages, start=1):
        page_number = page.get("page_number")
        if not isinstance(page_number, int) or page_number < 1:
            errors.append(f"page {index} has an invalid page_number")
        else:
            page_numbers.append(page_number)
        for field in ("title", "page_conclusion", "source_block_ids"):
            value = page.get(field)
            if value is None or value == "" or (field == "source_block_ids" and not isinstance(value, list)):
                errors.append(f"page {page_number or index} is missing {field}")
        if _contains_unresolved_marker(str(page.get("title", ""))) or _contains_unresolved_marker(str(page.get("page_conclusion", ""))):
            errors.append(f"page {page_number or index} contains an unresolved placeholder")
        assigned.extend(page.get("source_block_ids") or [])
        mechanism_id = page.get("mechanism_id")
        if not mechanism_id or get_mechanism(str(mechanism_id)) is None:
            errors.append(f"page {page_number or index} must select a valid mechanism_id")
        if page.get("page_structure"):
            for error in validate_page_structure(page["page_structure"]):
                errors.append(f"page {page_number or index} structure: {error}")

    if len(page_numbers) != len(set(page_numbers)):
        errors.append("page_number values must be unique")
    if page_numbers and sorted(page_numbers) != list(range(1, len(page_numbers) + 1)):
        errors.append("page_number values must form a continuous sequence starting at 1")

    omitted_records = contract.get("omitted_blocks") or []
    omitted: set[str] = set()
    for record in omitted_records:
        block_id = record.get("block_id") if isinstance(record, dict) else None
        reason = record.get("reason") if isinstance(record, dict) else None
        if not block_id or not reason or _contains_unresolved_marker(str(reason)):
            errors.append("every omitted block must include a final block_id and reason")
            continue
        omitted.add(block_id)

    for block_id in sorted((set(assigned) | omitted) - valid_ids):
        errors.append(f"unknown source block: {block_id}")
    for block_id in sorted(valid_ids - set(assigned) - omitted):
        errors.append(f"unassigned source block: {block_id}")

    allowed_reuse = set(contract.get("allowed_reused_source_block_ids") or [])
    for block_id, count in Counter(assigned).items():
        if count > 1 and block_id not in allowed_reuse:
            errors.append(f"duplicate source assignment without reuse approval: {block_id}")

    return errors


def approve_deck(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    parsed = _required_json(output_dir / "parsed_content" / "parsed_blocks.json")
    contract = _required_json(output_dir / "content_map" / "deck_contract.json")
    errors = validate_deck_contract(contract, parsed)
    if errors:
        raise ProductionWorkflowError("Deck contract approval failed:\n- " + "\n- ".join(errors))

    state = _load_state(output_dir)
    previous_hash = state.get("deck_contract_hash")
    current_hash = _file_hash(output_dir / "content_map" / "deck_contract.json")
    if previous_hash and previous_hash != current_hash:
        state["pages"] = {page_number: _new_page_state() for page_number in state.get("pages", {})}
    state["deck_approved_at"] = _now()
    state["deck_contract_hash"] = current_hash
    state["status"] = "deck_approved"
    state["updated_at"] = _now()
    for page in contract["pages"]:
        state.setdefault("pages", {}).setdefault(str(page["page_number"]), _new_page_state())
    _save_state(output_dir, state)
    return {"status": "approved", "page_count": len(contract["pages"]), "approved_at": state["deck_approved_at"]}


def prepare_page(output_dir: Path, page_number: int) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    state = _load_state(output_dir)
    if not state.get("deck_approved_at"):
        raise ProductionWorkflowError("Deck contract must be approved before preparing a page.")
    _assert_deck_approval_current(output_dir, state)

    contract = _required_json(output_dir / "content_map" / "deck_contract.json")
    page = _find_page(contract, page_number)
    parsed = _required_json(output_dir / "parsed_content" / "parsed_blocks.json")
    style = _required_json(output_dir / "assets" / "core_reference_style.json")
    config = _required_json(output_dir / "config_snapshot.json")
    planning_config = {**config, "core_reference_style": style}

    segment = _page_to_segment(page)
    plan = create_slide_plans([segment], planning_config)[0]
    structure = generate_page_structure(page)
    structure_path = output_dir / "page_structures" / f"page_{page_number:02d}.json"
    write_json(structure_path, structure)
    write_text(
        output_dir / "page_structures" / f"page_{page_number:02d}_prompt.txt",
        build_page_structure_prompt(page),
    )
    try:
        auto_match = select_mechanism_for_structure(matching_view(structure), limit=3)
    except ValueError as exc:
        auto_match = {
            "id": None,
            "match_tier": "NO_MATCH",
            "candidate_matches": [],
            "rejected_candidates": [],
            "error": str(exc),
        }

    approved_id = page.get("mechanism_id") or auto_match.get("id")
    mechanism = get_mechanism(str(approved_id)) if approved_id else None
    if mechanism is None:
        raise ProductionWorkflowError(f"No valid mechanism can be prepared for page {page_number}.")
    approved_candidate = next(
        (
            item
            for item in auto_match.get("candidate_matches", [])
            if item.get("id") == mechanism["id"]
        ),
        None,
    )
    mechanism["match_tier"] = (
        auto_match.get("match_tier") if auto_match.get("id") == mechanism["id"] else (approved_candidate or {}).get("match_tier", "OVERRIDE")
    )
    mechanism["adaptations"] = (approved_candidate or auto_match).get("adaptations", [])
    mechanism["selected_layout_variant"] = select_layout_variant(mechanism["id"], matching_view(structure))
    mechanism["retrieval_audit"] = {
        "matching_basis": "page_structure",
        "page_structure": str(structure_path),
        "auto_selected_id": auto_match.get("id"),
        "approved_mechanism_id": mechanism["id"],
        "approved_override": auto_match.get("id") != mechanism["id"],
        "match_tier": mechanism["match_tier"],
        "adaptations": mechanism.get("adaptations", []),
        "selected_layout_variant": (mechanism.get("selected_layout_variant") or {}).get("id"),
        "candidate_matches": auto_match.get("candidate_matches", []),
        "rejected_candidates": auto_match.get("rejected_candidates", []),
        "error": auto_match.get("error"),
    }
    match_record = {
        "page_id": structure["page_id"],
        "page_structure": matching_view(structure),
        "selected_card": mechanism["id"],
        "match_tier": mechanism["match_tier"],
        "approved_override": mechanism["retrieval_audit"]["approved_override"],
        "adaptations": mechanism.get("adaptations", []),
        "selected_layout_variant": (mechanism.get("selected_layout_variant") or {}).get("id"),
        "slot_binding": {
            group.get("id", f"g{index}"): group.get("item_refs", [])
            for index, group in enumerate(structure.get("groups", []), start=1)
        },
        "candidates": auto_match.get("candidate_matches", []),
        "rejected_candidates": auto_match.get("rejected_candidates", []),
        "error": auto_match.get("error"),
    }
    match_path = output_dir / "mechanism_matches" / f"page_{page_number:02d}.json"
    write_json(match_path, match_record)
    plan["mechanism_selection"] = mechanism
    plan["page_structure"] = structure
    plan["mechanism_match_record"] = str(match_path)
    plan["image2_prompt"] += (
        f" Mechanism library selection: {mechanism['id']} for relation {mechanism['relation']}. "
        f"Layout DNA: {mechanism['layout_dna']}. QA: {mechanism['qa_specific']}."
    )
    all_plans_path = output_dir / "slide_plans" / "all_slide_plans.json"
    all_plans = read_json(all_plans_path) if all_plans_path.exists() else []
    all_plans = [item for item in all_plans if item.get("slide_number") != page_number]
    all_plans.append(plan)
    all_plans.sort(key=lambda item: item["slide_number"])
    write_slide_plans(all_plans, output_dir / "slide_plans")

    content_path = output_dir / "content_arrangements" / f"page_{page_number:02d}.txt"
    evidence_path = output_dir / "evidence_specs" / f"page_{page_number:02d}.txt"
    design_path = output_dir / "design_drafts" / f"page_{page_number:02d}.txt"
    _write_text_if_missing(content_path, _content_arrangement_text(page))
    _write_text_if_missing(evidence_path, _evidence_spec_text(page))
    source_records = _assigned_source_records(page, parsed)
    _write_text_if_missing(design_path, _design_draft_text(page, plan, style, source_records))

    page_state = state.setdefault("pages", {}).setdefault(str(page_number), _new_page_state())
    page_state["page_prepared_at"] = _now()
    state["status"] = f"page_{page_number}_prepared"
    state["updated_at"] = _now()
    _save_state(output_dir, state)
    return {
        "page_number": page_number,
        "content_arrangement": str(content_path),
        "evidence_spec": str(evidence_path),
        "design_draft": str(design_path),
        "page_structure": str(structure_path),
        "mechanism_match": str(match_path),
        "slide_plan": str(_plan_json_path(output_dir, page_number)),
        "next_action": f"Review the three page contracts, then run approve-page --page {page_number}.",
    }


def approve_page(output_dir: Path, page_number: int) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    state = _load_state(output_dir)
    if not state.get("deck_approved_at"):
        raise ProductionWorkflowError("Deck contract must be approved before page approval.")
    _assert_deck_approval_current(output_dir, state)

    content_path = output_dir / "content_arrangements" / f"page_{page_number:02d}.txt"
    evidence_path = output_dir / "evidence_specs" / f"page_{page_number:02d}.txt"
    design_path = output_dir / "design_drafts" / f"page_{page_number:02d}.txt"
    contract = _required_json(output_dir / "content_map" / "deck_contract.json")
    page = _find_page(contract, page_number)
    errors: list[str] = []
    for label, path in (("content arrangement", content_path), ("evidence specification", evidence_path), ("design draft", design_path)):
        if not path.exists():
            errors.append(f"missing {label}: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        if _contains_unresolved_marker(text):
            errors.append(f"{label} contains an unresolved placeholder")
    if design_path.exists():
        errors.extend(
            validate_design_draft(
                design_path.read_text(encoding="utf-8"),
                required_evidence=page.get("supporting_points", []),
                required_source_block_ids=page.get("source_block_ids", []),
                required_data_points=page.get("data_points", []),
            )
        )
    if content_path.exists() and evidence_path.exists() and design_path.exists():
        errors.extend(_validate_page_artifacts_against_contract(page, content_path, evidence_path, design_path))
    if errors:
        raise ProductionWorkflowError("Page approval failed:\n- " + "\n- ".join(errors))

    page_state = state.setdefault("pages", {}).setdefault(str(page_number), _new_page_state())
    page_state["page_approved_at"] = _now()
    page_state["contract_hashes"] = {
        "content_arrangement": _file_hash(content_path),
        "evidence_spec": _file_hash(evidence_path),
        "design_draft": _file_hash(design_path),
        "page_structure": _file_hash(output_dir / "page_structures" / f"page_{page_number:02d}.json"),
        "mechanism_match": _file_hash(output_dir / "mechanism_matches" / f"page_{page_number:02d}.json"),
        "slide_plan": _file_hash(_plan_json_path(output_dir, page_number)),
    }
    state["status"] = f"page_{page_number}_approved"
    state["updated_at"] = _now()
    _save_state(output_dir, state)
    approval = {
        "page_number": page_number,
        "status": "approved",
        "approved_at": page_state["page_approved_at"],
        "contracts": [
            str(content_path),
            str(evidence_path),
            str(design_path),
            str(output_dir / "page_structures" / f"page_{page_number:02d}.json"),
            str(output_dir / "mechanism_matches" / f"page_{page_number:02d}.json"),
        ],
    }
    write_json(output_dir / "approvals" / f"page_{page_number:02d}_contracts.json", approval)
    return approval


def generate_page(
    output_dir: Path,
    page_number: int,
    provider: str,
    existing_image_dir: Path | None = None,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    state = _load_state(output_dir)
    page_state = state.get("pages", {}).get(str(page_number), {})
    if not page_state.get("page_approved_at"):
        raise ProductionWorkflowError("Page contracts must be approved before image generation.")
    _assert_deck_approval_current(output_dir, state)
    _assert_page_approval_current(output_dir, page_number, page_state)

    plan = dict(_required_json(_plan_json_path(output_dir, page_number)))
    config = _required_json(output_dir / "config_snapshot.json")
    content_path = output_dir / "content_arrangements" / f"page_{page_number:02d}.txt"
    evidence_path = output_dir / "evidence_specs" / f"page_{page_number:02d}.txt"
    design_path = output_dir / "design_drafts" / f"page_{page_number:02d}.txt"
    style = _required_json(output_dir / "assets" / "core_reference_style.json")
    compiled_prompt = compile_effect_image_prompt(
        plan,
        content_path.read_text(encoding="utf-8"),
        evidence_path.read_text(encoding="utf-8"),
        design_path.read_text(encoding="utf-8"),
        style,
        mechanism=plan.get("mechanism_selection"),
    )
    plan["image2_prompt"] = compiled_prompt
    compiled_prompt_path = output_dir / "slide_images" / f"page_{page_number:02d}_compiled_prompt.txt"
    write_text(compiled_prompt_path, compiled_prompt)
    try:
        result = generate_slide_mockups(
            [plan],
            output_dir / "slide_images",
            config,
            provider=provider,
            existing_image_dir=existing_image_dir,
        )
    except MockupGenerationError as exc:
        if provider != "prompt_only":
            raise
        result = {
            "provider": "prompt_only",
            "status": "prompt_ready",
            "message": str(exc),
            "prompt_jobs": str(output_dir / "slide_images" / "imagegen_jobs.jsonl"),
        }
    result = {**result, "compiled_prompt": str(compiled_prompt_path)}

    image_path = output_dir / "slide_images" / f"slide_{page_number:02d}.png"
    page_state = state.setdefault("pages", {}).setdefault(str(page_number), _new_page_state())
    page_state["image_status"] = "generated" if image_path.exists() else "prompt_ready"
    page_state["image_path"] = str(image_path) if image_path.exists() else None
    page_state["image_generated_at"] = _now() if image_path.exists() else None
    state["status"] = f"page_{page_number}_{page_state['image_status']}"
    state["updated_at"] = _now()
    _save_state(output_dir, state)
    return result


def approve_image(output_dir: Path, page_number: int, tolerance: float = 0.005) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    state = _load_state(output_dir)
    page_state = state.get("pages", {}).get(str(page_number), {})
    if not page_state.get("page_approved_at"):
        raise ProductionWorkflowError("Page contracts must be approved before image approval.")
    _assert_deck_approval_current(output_dir, state)
    _assert_page_approval_current(output_dir, page_number, page_state)
    image_value = page_state.get("image_path")
    image_path = Path(image_value) if image_value else output_dir / "slide_images" / f"slide_{page_number:02d}.png"
    if not image_path.exists():
        raise ProductionWorkflowError(f"Effect image not found: {image_path}")

    style = _required_json(output_dir / "assets" / "core_reference_style.json")
    structure = _required_json(output_dir / "page_structures" / f"page_{page_number:02d}.json")
    qa_report = audit_effect_image(image_path, style, structure, tolerance)
    qa_path = output_dir / "approvals" / f"page_{page_number:02d}_visual_qa.json"
    write_json(qa_path, qa_report)
    if not qa_report["passed"]:
        raise ProductionWorkflowError("Effect image QA failed:\n- " + "\n- ".join(qa_report["hard_failures"]))

    page_state = state.setdefault("pages", {}).setdefault(str(page_number), _new_page_state())
    page_state["image_approved_at"] = _now()
    page_state["image_dimensions"] = qa_report["canvas"]
    page_state["visual_qa"] = str(qa_path)
    state["status"] = f"page_{page_number}_image_approved"
    state["updated_at"] = _now()
    _save_state(output_dir, state)
    approval = {
        "page_number": page_number,
        "status": "approved",
        "image": str(image_path),
        "dimensions": page_state["image_dimensions"],
        "visual_qa": str(qa_path),
        "manual_checks_acknowledged_by_approval_stage": qa_report["manual_approval_checks"],
        "approved_at": page_state["image_approved_at"],
    }
    write_json(output_dir / "approvals" / f"page_{page_number:02d}_image.json", approval)
    return approval


def workflow_status(output_dir: Path) -> dict[str, Any]:
    state = _load_state(output_dir)
    state["next_actions"] = _next_actions(state)
    return state


def _enrich_ai_deck_contract(contract: dict[str, Any], project_brief: dict[str, Any] | None = None) -> dict[str, Any]:
    enriched = dict(contract)
    project_brief = project_brief or {}
    enriched["schema_version"] = "3.0"
    enriched["pagination_method"] = "ai_full_report_semantic_reorganization"
    enriched["project_brief"] = project_brief
    pages: list[dict[str, Any]] = []
    for original in contract.get("pages", []):
        page = dict(original)
        page["deck_type"] = project_brief.get("deck_type")
        page["standalone_readability"] = project_brief.get("standalone_readability")
        page["evidence_load"] = round(
            min(
                12.0,
                len(page.get("supporting_points", [])) * 0.8
                + len(page.get("data_points", []))
                + len(page.get("source_block_ids", [])) * 0.25,
            ),
            2,
        )
        structure = generate_page_structure(page)
        page["page_structure"] = structure
        page["suggested_visual_type"] = _visual_type_from_structure(structure)
        try:
            mechanism = select_mechanism_for_structure(matching_view(structure))
            page["mechanism_id"] = mechanism["id"]
            page["mechanism_match_status"] = "structure_match"
        except ValueError:
            relationship = page.get("semantic_relationship", "claim -> evidence -> implication")
            mechanism = select_mechanism(relationship, context=_page_mechanism_context(page))
            page["mechanism_id"] = mechanism["id"]
            page["mechanism_match_status"] = "legacy_fallback_review_required"
        pages.append(page)
    enriched["pages"] = pages
    enriched["approval_note"] = (
        "AI reorganized the full report without using source format or source order. "
        "Review the storyline, cross-source regrouping, exact claims, source coverage, and omissions before approval."
    )
    return enriched


def _storyline_readthrough_text(contract: dict[str, Any]) -> str:
    titles = [str(page.get("title", "")).strip() for page in contract.get("pages", [])]
    lines = ["STORYLINE TITLE READTHROUGH", "", f"Storyline: {contract.get('storyline', '')}", "", "Page titles:"]
    lines.extend(f"{index}. {title}" for index, title in enumerate(titles, start=1))
    lines.extend(["", "Continuous readthrough:", " → ".join(titles), ""])
    return "\n".join(lines)


def _visual_type_from_structure(structure: dict[str, Any]) -> str:
    relations = {group.get("relation") for group in structure.get("groups", [])}
    if relations & {"time_series", "temporal_sequence", "ordered_sequence", "progressive", "cumulative"}:
        return "timeline_or_process"
    if relations & {"matrix", "shared_metrics_comparison"}:
        return "editable_table"
    if relations & {"cycle", "network", "hierarchy"}:
        return "structured_bullets"
    if len(structure.get("groups", [])) >= 2:
        return "two_column_story"
    return "structured_bullets"


def _narrative_ai_pending_manifest(
    output_dir: Path,
    parsed: dict[str, Any],
    core_reference_path: str,
    reason: str,
) -> dict[str, Any]:
    state_path = output_dir / "workflow_state.json"
    state = read_json(state_path) if state_path.exists() else _new_state(parsed, core_reference_path)
    state["status"] = "narrative_ai_required"
    state["updated_at"] = _now()
    state["narrative_ai_blocker"] = reason
    write_json(state_path, state)
    manifest = {
        "mode": "production",
        "status": "narrative_ai_required",
        "source_report": parsed.get("source_path"),
        "core_reference": str(core_reference_path),
        "workflow_state": str(state_path),
        "narrative_source_payload": str(output_dir / "content_map" / "narrative_source_payload.json"),
        "narrative_prompt": str(output_dir / "content_map" / "narrative_ai_prompt.txt"),
        "narrative_schema": str(output_dir / "content_map" / "narrative_deck_contract_schema.json"),
        "blocker": reason,
        "next_action": "Configure narrative AI and rerun prepare. No heuristic deck contract was created.",
    }
    write_json(output_dir / "run_manifest.json", manifest)
    return manifest


def _page_to_segment(page: dict[str, Any]) -> dict[str, Any]:
    return {
        "slide_number": page["page_number"],
        "id": f"page-{page['page_number']:02d}",
        "title": page["title"],
        "core_message": page["page_conclusion"],
        "supporting_points": page.get("supporting_points", []),
        "data_points": page.get("data_points", []),
        "suggested_visual_type": page.get("suggested_visual_type", "structured_bullets"),
        "source_block_ids": page.get("source_block_ids", []),
        "content_char_count": sum(len(str(value)) for value in page.get("supporting_points", [])),
    }


def _content_arrangement_text(page: dict[str, Any]) -> str:
    lines = [
        f"PAGE {page['page_number']} CONTENT ARRANGEMENT",
        "",
        f"Conclusion title: {page['title']}",
        f"Page conclusion: {page['page_conclusion']}",
        f"Semantic relationship: {page.get('semantic_relationship', 'claim -> evidence -> implication')}",
        "",
        "Supporting themes and exact evidence:",
    ]
    for index, point in enumerate(page.get("supporting_points", []), start=1):
        lines.append(f"{index}. {point}")
    if not page.get("supporting_points"):
        lines.append("1. The approved conclusion is supported directly by the assigned source blocks.")
    lines.extend(
        [
            "",
            "Source blocks: " + ", ".join(page.get("source_block_ids", [])),
            "Reading order: conclusion title → primary evidence → supporting explanation → implication/source note.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _evidence_spec_text(page: dict[str, Any]) -> str:
    data = page.get("data_points", [])
    lines = [
        f"PAGE {page['page_number']} EVIDENCE SPECIFICATION",
        "",
        f"Question answered: What evidence proves that {page['page_conclusion']}",
        f"Primary relationship: {page.get('semantic_relationship', 'claim -> evidence -> implication')}",
        f"Recommended evidence form: {page.get('suggested_visual_type', 'structured_bullets')}",
        "",
        "Quantitative evidence:",
    ]
    if data:
        lines.extend(f"- {value}: retain the exact unit, comparison basis, and source context." for value in data)
    else:
        lines.append("- No standalone quantitative value was extracted; do not invent numbers or axes.")
    lines.extend(
        [
            "",
            "Evidence-to-claim links:",
            *[f"- {point} → supports the page conclusion." for point in page.get("supporting_points", [])],
            "",
            "Source blocks: " + ", ".join(page.get("source_block_ids", [])),
            "Drawability rule: labels, units, categories, ordering, and annotations must come from the assigned source material.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _design_draft_text(
    page: dict[str, Any],
    plan: dict[str, Any],
    style: dict[str, Any],
    source_records: list[dict[str, str]],
) -> str:
    canvas = style.get("canvas", {})
    width = canvas.get("width_inches", 13.333)
    height = canvas.get("height_inches", 7.5)
    ratio = canvas.get("aspect_ratio", "16:9")
    decision = plan.get("composition_decision", {})
    spatial = decision.get("spatial_narrative", {})
    relationship = page.get("semantic_relationship", "claim -> evidence -> implication")
    archetype = decision.get("design_archetype", plan["layout"]["name"])
    geometry = spatial.get("dominant_geometry", plan["layout"]["structure"])
    points = page.get("supporting_points", [])
    data_points = page.get("data_points", [])
    mechanism = plan.get("mechanism_selection", {})
    retrieval = mechanism.get("retrieval_audit", {})
    candidates = ", ".join(
        f"{item.get('id')}:{item.get('match_tier', 'unknown')}"
        for item in retrieval.get("candidate_matches", [])
    ) or "no passing structural candidate recorded"
    density = _density_contract(
        float(page.get("evidence_load") or (len(source_records) * 0.6 + len(points) * 0.8 + len(data_points)))
    )
    evidence_lines = [f"  {index}. {point}" for index, point in enumerate(points, start=1)]
    if not evidence_lines:
        evidence_lines = ["  1. Use the assigned source records below; no unsupported claim may be added."]
    data_lines = [f"  - {value}: preserve exact value, sign, unit, time basis, and comparison basis." for value in data_points]
    if not data_lines:
        data_lines = ["  - No standalone value is approved; do not invent numbers, axes, or rankings."]
    source_lines = [
        f"  - {record['block_id']} [{record['type']}]: {record['preview']}"
        for record in source_records
    ]
    mechanism_lines = [
        f"  - Reusable mechanism: {mechanism.get('id', 'none')} | relation pattern: {mechanism.get('card_contract', {}).get('relation_pattern', relationship)}",
        f"  - Matching basis: page_structure; match tier: {mechanism.get('match_tier', 'unknown')}; candidate shortlist: {candidates}",
        f"  - Required adaptations: {mechanism.get('adaptations', []) or 'none'}",
        f"  - Approved override of automatic match: {retrieval.get('approved_override', False)}",
        f"  - Library source example: {mechanism.get('source', 'not recorded')}",
        f"  - Match signature: {mechanism.get('match_when', 'not recorded')}",
        f"  - Hard fails: {mechanism.get('reject_when', 'not recorded')}",
        f"  - Data contract: {mechanism.get('slots', 'derive slots from the approved evidence inventory')}",
        f"  - Layout DNA to reuse: {mechanism.get('layout_dna', geometry)}",
        f"  - Selected source-layout variant: {(mechanism.get('selected_layout_variant') or {}).get('id', 'none')} | {(mechanism.get('selected_layout_variant') or {}).get('name', 'no exact variant match')}",
        f"  - Variant layout contract: {(mechanism.get('selected_layout_variant') or {}).get('layout_contract', 'use the generic mechanism geometry')}",
        "  - Adaptation rule: preserve topology and content relations; calculate exact region sizes from the current content load after matching.",
    ]
    encoding = _visual_encoding_contract(page.get("suggested_visual_type", "structured_bullets"), data_points)
    sections = {
        "Page conclusion": f"- The slide must prove this approved conclusion without adding a second thesis: {page['page_conclusion']}\n- Approved title: {page['title']}\n- Keep the title conclusion-led and on one line when feasible.",
        "Semantic relationship": f"- Governing relationship: {relationship}.\n- Every evidence module must have an explicit role in that relationship. Do not promote an item merely to fill space or create symmetry.\n- The conclusion must remain visually derivable from the evidence rather than appearing as an unsupported headline.",
        "Visual argument": "\n".join(
            [
                f"- Primary composition grammar: adapt the approved library mechanism {mechanism.get('id', 'none')} and its layout DNA to the evidence on this page.",
                f"- The planner archetype {archetype} and geometry {geometry} are secondary hierarchy hints only; if they conflict with the approved mechanism, the mechanism wins.",
                f"- Evidence load is {density['level']}: use {density['modules']} linked evidence forms inside the argument instead of forcing all content into one sparse object.",
                "- The page may combine a primary comparison/chart/matrix with attached annotations, an exception strip, or an implication rail when the evidence requires it; these are parts of one argument, not unrelated cards.",
                "- Excellent-PPT library match and adaptation contract:",
                *mechanism_lines,
            ]
        ),
        "Canvas": f"Use the core-reference canvas exactly: {width} x {height} inches, aspect ratio {ratio}. Preserve equal safe margins and keep the title, source note, and all evidence inside the slide boundary.",
        "Regions": "\n".join(
            [
                f"- Density target: {density['level']}; target {density['modules']} linked evidence forms and account for all {len(source_records)} assigned source blocks.",
                f"- {density['regions']}",
                "- Region sizes are computed after the mechanism is matched. Preserve the matched topology while adapting left/right or top/bottom space to actual content load; do not use fixed ratios as a match criterion.",
                "- Align region edges to a shared grid; use whitespace between semantic groups, not as an excuse for low information density.",
            ]
        ),
        "Evidence mapping": "\n".join(
            [
                f"- Required supporting evidence — all {len(points)} items must be visibly represented:",
                *evidence_lines,
                f"- Exact quantitative inventory — all {len(data_points)} approved callouts must be accounted for:",
                *data_lines,
                f"- Source coverage ledger — all {len(source_records)} assigned blocks must be mapped, consolidated, or explicitly treated as context:",
                *source_lines,
                "- Place each supporting statement beside the visual mark, row, column, window, or region that it explains. A source block ID by itself is not evidence representation.",
            ]
        ),
        "Visual encoding": f"- {encoding}\n- Use direct labels and explicit units. Color may emphasize meaning but may not be the only encoding.\n- Keep comparable series on a shared scale and shared definition; annotate exceptions and caveats directly where the audience encounters them.",
        "Hierarchy and reading path": f"- Primary: mechanism {mechanism.get('id', 'none')} and its comparison/relationship marks.\n- Secondary: attached evidence, exceptions, and explanatory annotations.\n- Tertiary: implication, methodology caveat, and source.\n- Reading path: {spatial.get('reading_path', 'title → primary relationship → evidence → implication')}. The evidence-bearing visual is encountered before commentary, while numeric proof remains close enough to scan without cross-page lookup.",
        "Typography": "Chinese text uses KaiTi. English, numbers, and punctuation use Arial. Match the core-reference title/body sizes where available; never auto-shrink. Keep the title on one line, use compact readable body copy, and solve overflow by editing wording, region size, or spacing.",
        "Style": f"Follow the dynamic core-reference palette exactly: {style.get('palette', {}).get('roles', {})}. Also preserve its title system, page chrome, observed line treatment {style.get('line_treatment', {})}, content bounds, and whitespace rhythm. Do not introduce any default project color or unrelated accent hue. The core reference controls style but must not override this page's approved regions or mechanism.",
        "Anti-template constraints": f"Do not replace the matched {mechanism.get('id', 'library mechanism')} with the generic planner archetype {archetype}, equal cards, a generic dashboard, a generic table, or default SmartArt. Do not show only one proof point per subject when more approved evidence exists. Do not invent icons, logos, categories, numbers, or symmetrical filler. Do not separate evidence from the claim it supports, and do not let decorative assets compete with the evidence.",
        "Approval checklist": f"- Coverage: {len(points)}/{len(points)} supporting items, {len(data_points)}/{len(data_points)} quantitative callouts, and {len(source_records)}/{len(source_records)} source blocks are accounted for in this specification.\n- Library reuse: mechanism {mechanism.get('id', 'none')} has an explicit source, fit condition, reject condition, slots, layout DNA, and adaptation rule.\n- Semantics: the approved relationship is visible. Encoding: labels, units, scales, comparisons, and annotations are drawable.\n- Hierarchy: one argument dominates while {density['modules']} evidence forms remain coordinated. Density: evidence fills the page without crowding.\n- Production: aspect ratio, KaiTi + Arial typography, source note, overlap, overflow, and minimum readable type checks all pass.",
    }
    return "\n\n".join(f"{heading}\n{body}" for heading, body in sections.items()) + "\n"


def _assigned_source_records(page: dict[str, Any], parsed: dict[str, Any]) -> list[dict[str, str]]:
    block_index = {block.get("id"): block for block in parsed.get("blocks", [])}
    records: list[dict[str, str]] = []
    for block_id in page.get("source_block_ids", []):
        block = block_index.get(block_id, {})
        preview = " ".join(_block_text(block).split())[:220]
        records.append(
            {
                "block_id": str(block_id),
                "type": str(block.get("type", "missing")),
                "preview": preview or "[empty source block]",
            }
        )
    return records


def _density_contract(evidence_load: float) -> dict[str, str]:
    if evidence_load >= 8:
        return {
            "level": f"high ({evidence_load:.1f} evidence units)",
            "modules": "one primary evidence field plus two or three tightly attached evidence forms",
            "regions": "Give the primary relationship first claim on space, then allocate remaining space by evidence importance. If independent claims remain, split the page instead of shrinking type.",
        }
    if evidence_load >= 4:
        return {
            "level": f"balanced ({evidence_load:.1f} evidence units)",
            "modules": "one primary evidence field plus one or two attached supporting forms",
            "regions": "Allocate space adaptively according to item count, label length, and the matched relationship topology; keep source and implication subordinate but visible.",
        }
    return {
        "level": f"focused ({evidence_load:.1f} evidence units)",
        "modules": "one primary evidence field with directly attached explanation",
        "regions": "Let the primary relationship occupy the necessary canvas without inflating a small evidence set into oversized cards; retain deliberate whitespace from the reference style.",
    }


def _visual_encoding_contract(visual_type: str, data_points: list[str]) -> str:
    contracts = {
        "editable_table": "Use shared row definitions and consistent columns; retain all values and units, highlight only decision-relevant differences, and expose missing or non-comparable values explicitly.",
        "matrix": "Define both axes, row/column categories, cell encoding, legend, and exception annotations; keep like-for-like cells directly comparable.",
        "data_cards": "Convert comparable quantities into a shared-axis chart, dot plot, bars, or aligned mini-series where possible; reserve callout boxes for interpretations, not for replacing the data structure.",
        "timeline_or_process": "Use one ordered time or stage axis with explicit dates/stages, milestone labels, duration or window encoding, and dependency/transition annotations.",
        "structured_bullets": "Use a comparable profile, factor stack, evidence gallery, or other mapped structure; attach each claim to a quantitative or sourced proof mark instead of presenting prose bullets alone.",
        "two_column_story": "Use a shared comparison schema across both sides with aligned labels, scales, and a visible synthesis bridge; avoid two unrelated text columns.",
    }
    base = contracts.get(visual_type, contracts["structured_bullets"])
    if data_points:
        return f"{base} Approved quantitative callouts: {', '.join(data_points)}."
    return base


def _page_mechanism_context(page: dict[str, Any]) -> str:
    values = [
        str(page.get("title", "")),
        str(page.get("page_conclusion") or page.get("core_message") or ""),
        str(page.get("suggested_visual_type", "")),
        *[str(item) for item in page.get("supporting_points", [])],
        *[str(item) for item in page.get("data_points", [])],
    ]
    return "\n".join(value for value in values if value)


def _source_inventory(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for block in parsed.get("blocks", []):
        text = _block_text(block)
        records.append(
            {
                "block_id": block.get("id"),
                "type": block.get("type"),
                "page": block.get("page"),
                "preview": text[:240],
                "char_count": len(text),
            }
        )
    return records


def _content_map_text(parsed: dict[str, Any]) -> str:
    lines = ["FULL REPORT CONTENT MAP", "", f"Source: {parsed.get('source_path')}", f"Blocks: {parsed.get('block_count', 0)}", ""]
    for record in _source_inventory(parsed):
        page = f" page={record['page']}" if record.get("page") else ""
        lines.append(f"- {record['block_id']} [{record['type']}{page}] {record['preview']}")
    return "\n".join(lines).strip() + "\n"


def _block_text(block: dict[str, Any]) -> str:
    if block.get("type") == "list":
        return " ".join(block.get("items", []))
    if block.get("type") == "table":
        return " | ".join(" / ".join(row) for row in block.get("rows", []))
    return str(block.get("text", ""))


def _style_prompt(style: dict[str, Any]) -> str:
    canvas = style.get("canvas", {})
    return (
        f"Core reference {style.get('template_name', 'template')}; canvas {canvas.get('aspect_ratio', 'reference ratio')}; "
        "Chinese KaiTi; English, numbers, and punctuation Arial; preserve extracted palette, title hierarchy, density, and page chrome."
    )


def _semantic_relationship(visual_type: str) -> str:
    return {
        "editable_table": "multiple_objects × comparable_capabilities -> encoded_coverage",
        "timeline_or_process": "macro_phases over shared_time_axis + discrete_milestones",
        "matrix": "process_stages × participants -> responsibilities_or_actions",
        "data_cards": "multiple_reasons -> shared_claim, each_reason -> compact_evidence",
        "structured_bullets": "multiple_reasons -> shared_claim, each_reason -> compact_evidence",
        "two_column_story": "proposition_A + proposition_B -> shared_thesis",
    }.get(visual_type, "claim -> evidence -> implication")


def _new_state(parsed: dict[str, Any], core_reference_path: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "mode": "production",
        "status": "prepared",
        "created_at": _now(),
        "updated_at": _now(),
        "source_report": parsed.get("source_path"),
        "core_reference": str(core_reference_path),
        "deck_approved_at": None,
        "deck_contract_hash": None,
        "pages": {},
    }


def _new_page_state() -> dict[str, Any]:
    return {
        "page_prepared_at": None,
        "page_approved_at": None,
        "contract_hashes": {},
        "image_status": "not_started",
        "image_path": None,
        "image_generated_at": None,
        "image_approved_at": None,
    }


def _load_state(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "workflow_state.json"
    if not path.exists():
        raise ProductionWorkflowError(f"Production run is not prepared: {path}")
    return read_json(path)


def _save_state(output_dir: Path, state: dict[str, Any]) -> None:
    write_json(output_dir / "workflow_state.json", state)


def _required_json(path: Path) -> Any:
    if not path.exists():
        raise ProductionWorkflowError(f"Required workflow file is missing: {path}")
    return read_json(path)


def _find_page(contract: dict[str, Any], page_number: int) -> dict[str, Any]:
    for page in contract.get("pages", []):
        if page.get("page_number") == page_number:
            return page
    raise ProductionWorkflowError(f"Page {page_number} is not present in the approved deck contract.")


def _plan_json_path(output_dir: Path, page_number: int) -> Path:
    candidates = sorted((output_dir / "slide_plans").glob(f"{page_number:02d}_*.json"))
    candidates = [path for path in candidates if path.name != "all_slide_plans.json"]
    if not candidates:
        return output_dir / "slide_plans" / f"{page_number:02d}_page.json"
    return candidates[0]


def _write_text_if_missing(path: Path, text: str) -> None:
    if not path.exists():
        write_text(path, text)


def _validate_page_artifacts_against_contract(
    page: dict[str, Any],
    content_path: Path,
    evidence_path: Path,
    design_path: Path,
) -> list[str]:
    errors: list[str] = []
    content = content_path.read_text(encoding="utf-8")
    evidence = evidence_path.read_text(encoding="utf-8")
    design = design_path.read_text(encoding="utf-8")
    for value, label in (
        (page["title"], "approved title"),
        (page["page_conclusion"], "approved conclusion"),
        (page.get("semantic_relationship", ""), "approved semantic relationship"),
    ):
        if value and value not in content + evidence + design:
            errors.append(f"page artifacts do not preserve the {label}")
    for block_id in page.get("source_block_ids", []):
        if block_id not in content or block_id not in evidence or block_id not in design:
            errors.append(f"page artifacts do not preserve source mapping for {block_id}")
    if page["page_conclusion"] not in design:
        errors.append("design draft does not preserve the approved page conclusion")
    if page.get("semantic_relationship") and page["semantic_relationship"] not in design:
        errors.append("design draft does not preserve the approved semantic relationship")
    return errors


def _assert_deck_approval_current(output_dir: Path, state: dict[str, Any]) -> None:
    approved_hash = state.get("deck_contract_hash")
    current_hash = _file_hash(output_dir / "content_map" / "deck_contract.json")
    if not approved_hash or approved_hash != current_hash:
        raise ProductionWorkflowError("Deck contract changed after approval; run approve-deck again.")


def _assert_page_approval_current(output_dir: Path, page_number: int, page_state: dict[str, Any]) -> None:
    approved = page_state.get("contract_hashes") or {}
    paths = {
        "content_arrangement": output_dir / "content_arrangements" / f"page_{page_number:02d}.txt",
        "evidence_spec": output_dir / "evidence_specs" / f"page_{page_number:02d}.txt",
        "design_draft": output_dir / "design_drafts" / f"page_{page_number:02d}.txt",
        "page_structure": output_dir / "page_structures" / f"page_{page_number:02d}.json",
        "mechanism_match": output_dir / "mechanism_matches" / f"page_{page_number:02d}.json",
        "slide_plan": _plan_json_path(output_dir, page_number),
    }
    for key, path in paths.items():
        if approved.get(key) != _file_hash(path):
            raise ProductionWorkflowError(f"Page {page_number} {key} changed after approval; run approve-page again.")


def _file_hash(path: Path) -> str:
    if not path.exists():
        raise ProductionWorkflowError(f"Required approved file is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contains_unresolved_marker(text: str) -> bool:
    upper = text.upper()
    return any(marker.upper() in upper for marker in UNRESOLVED_MARKERS)


def _expected_ratio(style: dict[str, Any]) -> float:
    canvas = style.get("canvas", {})
    width = canvas.get("width_inches")
    height = canvas.get("height_inches")
    if width and height:
        return float(width) / float(height)
    ratio = str(canvas.get("aspect_ratio", "16:9"))
    if ":" in ratio:
        left, right = ratio.split(":", 1)
        try:
            return float(left) / float(right)
        except ValueError:
            pass
    return 16 / 9


def _next_actions(state: dict[str, Any]) -> list[str]:
    if not state.get("deck_approved_at"):
        return ["Review content_map/deck_contract.json and run approve-deck."]
    actions: list[str] = []
    for page_number, page_state in sorted(state.get("pages", {}).items(), key=lambda item: int(item[0])):
        if not page_state.get("page_prepared_at"):
            actions.append(f"Prepare page {page_number}.")
        elif not page_state.get("page_approved_at"):
            actions.append(f"Review and approve page {page_number} contracts.")
        elif page_state.get("image_status") == "not_started":
            actions.append(f"Generate exactly page {page_number}.")
        elif page_state.get("image_status") == "prompt_ready":
            actions.append(f"Generate or provide the effect image for page {page_number}.")
        elif not page_state.get("image_approved_at"):
            actions.append(f"Review and approve the effect image for page {page_number}.")
    return actions or ["All prepared pages and images are approved; proceed to rebuild packaging or deck-wide audit."]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
