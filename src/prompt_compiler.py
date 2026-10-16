from __future__ import annotations

import json
from typing import Any


def compile_effect_image_prompt(
    plan: dict[str, Any],
    content_arrangement: str,
    evidence_specification: str,
    design_draft: str,
    style_contract: str | dict[str, Any],
    mechanism: dict[str, Any] | None = None,
) -> str:
    """Compile approved page artifacts into the single effect-image prompt.

    The order below is intentional. It prevents a generic planner prompt or a
    reference deck from silently overriding an approved, page-specific design.
    """
    mechanism = mechanism or plan.get("mechanism_selection") or {}
    title = str(plan.get("title") or "").strip()
    objective = str(plan.get("core_message") or plan.get("objective") or "").strip()
    mechanism_block = _mechanism_block(mechanism)
    style_block = _style_block(style_contract)

    return f"""Create one polished, realistic PowerPoint slide effect image.

PAGE IDENTITY
- Approved title: {title}
- Approved conclusion/objective: {objective}
- Output exactly one slide; keep every approved fact, label, unit, comparison basis, and source qualifier accurate.

AUTHORITY AND CONFLICT RULES
1. The APPROVED VISUAL DESIGN DRAFT controls composition, regions, hierarchy, reading path, and visual encoding.
2. The APPROVED EVIDENCE SPECIFICATION controls exact facts, values, units, labels, caveats, and evidence-to-claim links.
3. The APPROVED CONTENT ARRANGEMENT controls narrative order and wording intent.
4. The REUSABLE LIBRARY MECHANISM supplies proven layout grammar from an excellent prior PPT; adapt its geometry to this page instead of copying its branding or content.
5. The CORE-REFERENCE STYLE CONTRACT controls only canvas, palette, typography, line/fill treatment, page chrome, and whitespace rhythm. It must never replace or rearrange the approved page design.
6. If two instructions conflict, follow the higher authority above. Never compress away required evidence to make the slide look sparse.

APPROVED VISUAL DESIGN DRAFT — PRIMARY LAYOUT AUTHORITY
{design_draft.strip()}

APPROVED EVIDENCE SPECIFICATION — FACTUAL AUTHORITY
{evidence_specification.strip()}

APPROVED CONTENT ARRANGEMENT — NARRATIVE AUTHORITY
{content_arrangement.strip()}

REUSABLE LIBRARY MECHANISM — PROVEN COMPOSITION GRAMMAR
{mechanism_block}

CORE-REFERENCE STYLE CONTRACT — STYLE TOKENS ONLY / HARD PROJECT STYLE CONSTRAINTS
{style_block}

FINAL PRODUCTION REQUIREMENTS
- Render a high-information-density consulting slide, but keep clear grouping, alignment, and whitespace between evidence modules.
- Preserve all items marked required in the design and evidence specifications; do not show only a sample of the approved evidence.
- Use KaiTi for Chinese and Arial for English, numbers, and punctuation.
- Use only the palette roles and allowed colors extracted from the declared core-reference PPT. Do not substitute a generic blue, red, gold, SaaS, or consulting palette.
- Title position, title/body/caption size hierarchy, footer/source/page-number treatment, line treatment, and content bounds must follow the same dynamic reference contract.
- Use real charts, comparison structures, timelines, matrices, or mapped evidence when specified. Do not substitute generic equal cards, a dashboard, default SmartArt, or decorative filler.
- Use direct labels and explicit units; do not invent numbers, icons, logos, categories, or sources.
- Keep the approved conclusion-led title on one line when feasible. Prevent clipping, overlap, overflow, tiny body text, and excessive empty space.
""".strip() + "\n"


def _mechanism_block(mechanism: dict[str, Any]) -> str:
    if not mechanism:
        return "No reusable mechanism was approved; follow the visual design draft directly."
    variant = mechanism.get("selected_layout_variant") or {}
    fields = (
        ("Mechanism", mechanism.get("id")),
        ("Semantic relation", mechanism.get("relation")),
        ("Use when", mechanism.get("match_when")),
        ("Reject when", mechanism.get("reject_when")),
        ("Slot contract", mechanism.get("slots")),
        ("Layout DNA", mechanism.get("layout_dna")),
        ("Mechanism-specific QA", mechanism.get("qa_specific")),
        ("Source example", mechanism.get("source")),
        ("Selected layout variant", f"{variant.get('id')} | {variant.get('name')}" if variant else None),
        ("Variant relationship", variant.get("relationship")),
        ("Variant layout contract", json.dumps(variant.get("layout_contract"), ensure_ascii=False) if variant else None),
        ("Variant encoding contract", json.dumps(variant.get("encoding_contract"), ensure_ascii=False) if variant else None),
        ("Variant adaptation", json.dumps(variant.get("adaptation"), ensure_ascii=False) if variant else None),
        ("Variant hard fails", json.dumps(variant.get("hard_fail"), ensure_ascii=False) if variant else None),
    )
    return "\n".join(f"- {label}: {value}" for label, value in fields if value)


def _style_block(style_contract: str | dict[str, Any]) -> str:
    if isinstance(style_contract, str):
        return style_contract.strip()
    hard = style_contract.get("hard_constraints") or {
        "policy": "dynamic_from_core_reference",
        "palette": {
            "roles": style_contract.get("palette", {}).get("roles", {}),
            "allowed_hex": list(
                dict.fromkeys(
                    [
                        *style_contract.get("palette", {}).get("roles", {}).values(),
                        *style_contract.get("palette", {}).get("dominant_colors", []),
                        *style_contract.get("palette", {}).get("fill_colors", []),
                    ]
                )
            ),
        },
        "typography": style_contract.get("typography", {}),
        "title_system": style_contract.get("title_system", {}),
        "page_chrome": style_contract.get("page_chrome", {}),
        "content_geometry": style_contract.get("content_geometry", {}),
        "line_treatment": style_contract.get("line_treatment", {}),
    }
    summary = style_contract.get("style_prompt", "Style extracted from the declared core-reference PPT.")
    return f"{summary}\nMACHINE-READABLE HARD STYLE CONTRACT\n{json.dumps(hard, ensure_ascii=False, indent=2)}"
