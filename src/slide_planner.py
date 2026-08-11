from __future__ import annotations

from pathlib import Path
from typing import Any

from composition_router import route_composition
from utils import slugify, write_json, write_text


def create_slide_plans(segments: list[dict[str, Any]], config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    theme = (config or {}).get("theme", {})
    core_style = (config or {}).get("core_reference_style", {})
    composition_enabled = (config or {}).get("composition_decision", {}).get("enabled", True)
    plans: list[dict[str, Any]] = []
    for segment in segments:
        visual_type = segment.get("suggested_visual_type", "structured_bullets")
        decision = route_composition(segment) if composition_enabled else None
        layout = _layout_for_decision(decision, visual_type)
        plan = {
            "slide_number": segment["slide_number"],
            "title": segment["title"],
            "objective": segment["core_message"],
            "layout": layout,
            "text_arrangement": _text_arrangement(segment, layout),
            "visual_elements": _visual_elements(visual_type, segment),
            "core_reference_style": core_style,
            "core_reference_style_rules": _style_rules(core_style),
            "color_palette": _palette(theme, core_style),
            "typography": _typography(core_style),
            "image2_prompt": _image_prompt(segment, layout, visual_type, theme, core_style, decision),
            "segment_ref": segment["id"],
            "source_block_ids": segment.get("source_block_ids", []),
        }
        if decision:
            plan["composition_decision"] = decision
            plan["communication_objective"] = decision["communication_objective"]
            plan["information_density"] = decision["information_density"]
            plan["design_intensity"] = decision["design_intensity"]
            plan["visual_strategy"] = decision["visual_strategy"]
            plan["visual_proposition"] = decision["visual_proposition"]
            plan["design_archetype"] = decision["design_archetype"]
            plan["spatial_narrative"] = decision["spatial_narrative"]
            plan["asset_strategy"] = decision["asset_strategy"]
        plans.append(plan)
    return plans


def write_slide_plans(plans: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    paths: list[Path] = []
    write_json(output_dir / "all_slide_plans.json", plans)
    paths.append(output_dir / "all_slide_plans.json")

    for plan in plans:
        base = f"{plan['slide_number']:02d}_{slugify(plan['title'])}"
        json_path = output_dir / f"{base}.json"
        md_path = output_dir / f"{base}.md"
        write_json(json_path, plan)
        write_text(md_path, plan_to_markdown(plan))
        paths.extend([json_path, md_path])
    return paths


def plan_to_markdown(plan: dict[str, Any]) -> str:
    lines = [
        f"# Slide {plan['slide_number']}: {plan['title']}",
        "",
        f"Objective: {plan['objective']}",
        "",
        f"Layout: {plan['layout']['name']}",
        "",
        "Text arrangement:",
    ]
    for item in plan["text_arrangement"]:
        lines.append(f"- {item}")
    lines.append("")
    if plan.get("composition_decision"):
        decision = plan["composition_decision"]
        lines.extend(
            [
                "Composition decision:",
                f"- Communication objective: {decision['communication_objective']}",
                f"- Information density: {decision['information_density']['score']}/5 — {decision['information_density']['rationale']}",
                f"- Design intensity: {decision['design_intensity']['level']}/5 — {decision['design_intensity']['rationale']}",
                f"- Visual strategy: {decision['visual_strategy']}",
                f"- Archetype: {decision['design_archetype']}",
                f"- Visual proposition: {decision['visual_proposition']}",
                f"- Spatial narrative: {decision['spatial_narrative']['reading_path']}",
                "",
            ]
        )
    lines.append("Core-reference style rules:")
    for rule in plan.get("core_reference_style_rules", []):
        lines.append(f"- {rule}")
    lines.append("")
    lines.append("Visual elements:")
    for element in plan["visual_elements"]:
        lines.append(f"- {element}")
    lines.append("")
    lines.append("Image2 prompt:")
    lines.append("")
    lines.append(plan["image2_prompt"])
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def _layout_for_visual_type(visual_type: str) -> dict[str, str]:
    layouts = {
        "editable_table": {
            "name": "Title plus compact evidence table",
            "structure": "Title band, key takeaway strip, compact evidence table, bottom implication note",
        },
        "timeline_or_process": {
            "name": "Title plus horizontal process",
            "structure": "Title band, left context column, horizontal stage flow, right conclusion card",
        },
        "matrix": {
            "name": "Title plus 2x2 business matrix",
            "structure": "Title band, summary strip, 2x2 matrix, action callout",
        },
        "data_cards": {
            "name": "Title plus metric cards",
            "structure": "Title band, three metric cards, supporting bullet column, implication footer",
        },
        "structured_bullets": {
            "name": "Three-column insight grid",
            "structure": "Title band, three content modules, evidence badges, footer takeaway",
        },
        "two_column_story": {
            "name": "Two-column executive story",
            "structure": "Title band, left key message panel, right supporting proof panel",
        },
    }
    return layouts.get(visual_type, layouts["structured_bullets"])


def _layout_for_decision(decision: dict[str, Any] | None, visual_type: str) -> dict[str, str]:
    if not decision or decision["design_intensity"]["level"] < 4:
        return _layout_for_visual_type(visual_type)
    archetype = decision["design_archetype"]
    geometry = decision["spatial_narrative"]["dominant_geometry"]
    return {
        "name": f"{archetype} composition",
        "structure": f"Conclusion-led title band, single {geometry}, attached evidence, compact implication footer",
    }


def _text_arrangement(segment: dict[str, Any], layout: dict[str, str]) -> list[str]:
    points = segment.get("supporting_points", [])
    arranged = [f"Headline takeaway: {segment['core_message']}"]
    for idx, point in enumerate(points[:8], start=1):
        arranged.append(f"Body point {idx}: {point}")
    if segment.get("data_points"):
        arranged.append("Evidence badges: " + ", ".join(segment["data_points"][:4]))
    arranged.append(f"Layout structure: {layout['structure']}")
    return arranged


def _visual_elements(visual_type: str, segment: dict[str, Any]) -> list[str]:
    base = {
        "editable_table": ["Compact evidence table", "Light header row", "Right-side implication callout"],
        "timeline_or_process": ["Stage blocks", "Connector arrows", "Milestone labels"],
        "matrix": ["Quadrant grid", "Priority tags", "Action callout"],
        "data_cards": ["Metric cards", "Small proof-point badges", "Supporting bullet rail"],
        "structured_bullets": ["Three content modules", "Section icons", "Footer takeaway"],
        "two_column_story": ["Left message panel", "Right evidence panel", "Accent divider"],
    }
    elements = base.get(visual_type, base["structured_bullets"])
    if segment.get("data_points"):
        elements = elements + ["Data callouts for: " + ", ".join(segment["data_points"][:3])]
    return elements


def _palette(theme: dict[str, Any], core_style: dict[str, Any] | None = None) -> dict[str, str]:
    core_palette = (core_style or {}).get("palette", {})
    roles = core_palette.get("roles", {})
    palette_values = core_palette.get("dominant_colors", [])
    fill_values = core_palette.get("fill_colors", [])
    return {
        "primary": _hex_or_fallback([roles.get("primary", "")], _hex_or_fallback(palette_values, theme.get("primary", "#183A59"), 0), 0),
        "accent": _hex_or_fallback([roles.get("support", "")], _hex_or_fallback(palette_values, theme.get("accent", "#2F80ED"), 0), 0),
        "pale_blue": _hex_or_fallback([roles.get("pale_fill", "")], _hex_or_fallback(fill_values or palette_values, "#D2E4F2", 0), 0),
        "secondary": theme.get("secondary", "#6B7280"),
        "background": _hex_or_fallback([roles.get("background", "") or core_palette.get("background_color", "FFFFFF")], theme.get("background", "#F7F9FC"), 0),
        "surface": theme.get("surface", "#FFFFFF"),
        "text": _hex_or_fallback([roles.get("body", "")], _hex_or_fallback(palette_values, theme.get("text", "#111827"), 0), 0),
    }


def _hex_or_fallback(values: list[str], fallback: str, index: int) -> str:
    values = [value for value in values if value]
    if not values:
        return fallback
    value = values[min(index, len(values) - 1)]
    return f"#{value}" if len(value) == 6 and not value.startswith("#") else value


def _typography(core_style: dict[str, Any] | None = None) -> dict[str, str]:
    if core_style:
        typography = core_style.get("typography", {})
        title = typography.get("title", {})
        body = typography.get("body", {})
        return {
            "title": f"{title.get('font_family') or 'Reference title font'} {title.get('size_pt') or 'reference'}pt, upper-left aligned",
            "body": f"{body.get('font_family') or 'Reference body font'} {body.get('size_pt') or 'reference'}pt, compact research body",
            "caption": "Reference footer/source treatment, compact and muted",
        }
    return {
        "title": "Aptos Display 26-30pt bold",
        "body": "Aptos 11-15pt",
        "caption": "Aptos 8-9pt muted",
    }


def _style_rules(core_style: dict[str, Any] | None = None) -> list[str]:
    if not core_style:
        return ["No core-reference style contract is configured."]
    canvas = core_style.get("canvas", {})
    palette = core_style.get("palette", {})
    title = core_style.get("typography", {}).get("title", {})
    body = core_style.get("typography", {}).get("body", {})
    caption = core_style.get("typography", {}).get("caption", {})
    return [
        f"Core template: {core_style.get('template_name', 'declared core reference')}",
        f"Canvas: {canvas.get('aspect_ratio', 'reference ratio')} {canvas.get('width_inches', '?')}x{canvas.get('height_inches', '?')}in.",
        f"Palette: {palette.get('prompt_summary', 'use extracted reference palette')}.",
        f"Typography: title {title.get('font_family', 'reference title font')} {title.get('size_pt', 'reference')}pt; body {body.get('font_family', 'reference body font')} {body.get('size_pt', 'reference')}pt; caption {caption.get('font_family', 'reference caption font')} {caption.get('size_pt', 'reference')}pt.",
        core_style.get("title_system", {}).get("rule", ""),
        core_style.get("page_chrome", {}).get("rule", ""),
        core_style.get("density", {}).get("recommended_evidence_modules", ""),
    ]


def _image_prompt(
    segment: dict[str, Any],
    layout: dict[str, str],
    visual_type: str,
    theme: dict[str, Any],
    core_style: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
) -> str:
    palette = _palette(theme, core_style)
    primary = palette["primary"]
    accent = palette["accent"]
    canvas = (core_style or {}).get("canvas", {})
    aspect_ratio = canvas.get("aspect_ratio", "reference aspect ratio")
    style_rules = " ".join(rule for rule in _style_rules(core_style) if rule)
    points = "; ".join(segment.get("supporting_points", [])[:8])
    data = ", ".join(segment.get("data_points", [])[:4]) or "no oversized numeric callouts unless supported"
    composition_instruction = _composition_prompt_instruction(decision)
    return (
        f"Create a realistic {aspect_ratio} consulting slide effect image that follows this explicit core-reference "
        f"style contract: {style_rules} "
        "Use the stated canvas, title hierarchy, page chrome, and density rather than a generic "
        "consulting or SaaS style. "
        f"Use extracted primary color {primary}, support color {accent}, pale fill {palette['pale_blue']}, background {palette['background']}, and body text {palette['text']}. "
        f"Slide title: {segment['title']}. Objective: {segment['core_message']}. "
        f"Layout: {layout['name']} ({layout['structure']}). Visual type: {visual_type}. "
        f"Composition decision: {composition_instruction} "
        f"Use concise, legible text modules for these points: {points}. "
        f"Show data proof points as small cards or badges: {data}. "
        "Make the slide information-rich: use compact modules, tables, data cards, sidebars, or small callouts where appropriate. "
        "Avoid decorative clutter, avoid stock photos, avoid low-density empty layouts, avoid huge paragraphs, keep margins aligned."
    )


def _composition_prompt_instruction(decision: dict[str, Any] | None) -> str:
    if not decision:
        return "Use the legacy layout routing without an additional composition decision."
    intensity = decision["design_intensity"]["level"]
    spatial = decision["spatial_narrative"]
    if intensity >= 4:
        return (
            f"Design intensity {intensity}/5. Visual proposition: {decision['visual_proposition']} "
            f"Use {decision['design_archetype']} with {spatial['dominant_geometry']}; create one dominant visual anchor and attach evidence to it. "
            "Do not replace the composition with equal cards, a generic grid, or default SmartArt."
        )
    if intensity <= 2:
        return (
            f"Design intensity {intensity}/5. This is a restrained {decision['visual_strategy']} page. "
            f"Prioritize {spatial['reading_path']}. Do not invent a hero illustration or decorative metaphor."
        )
    return (
        f"Design intensity {intensity}/5. Use {decision['design_archetype']} and {spatial['dominant_geometry']}; "
        "make the claim and evidence easy to scan without turning every point into a card."
    )
