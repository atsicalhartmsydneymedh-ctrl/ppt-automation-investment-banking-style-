from __future__ import annotations

from pathlib import Path
from typing import Any

from utils import write_json, write_text


def generate_slide_images(plans: list[dict[str, Any]], output_dir: Path, config: dict[str, Any] | None = None) -> list[dict[str, str]]:
    settings = (config or {}).get("image_generation", {})
    width = int(settings.get("width", 1600))
    height = int(settings.get("height", 900))
    output_dir.mkdir(parents=True, exist_ok=True)

    prompts: list[dict[str, str]] = []
    for plan in plans:
        prompt = plan["image2_prompt"]
        image_path = output_dir / f"slide_{plan['slide_number']:02d}.png"
        _render_placeholder_slide(plan, image_path, width, height)
        prompts.append(
            {
                "slide_number": str(plan["slide_number"]),
                "title": plan["title"],
                "provider": settings.get("provider", "local_placeholder"),
                "prompt": prompt,
                "image_path": str(image_path),
            }
        )

    write_json(output_dir / "image_prompts.json", prompts)
    write_text(output_dir / "image_prompts.md", _prompts_to_markdown(prompts))
    return prompts


def _render_placeholder_slide(plan: dict[str, Any], image_path: Path, width: int, height: int) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Pillow is required to generate slide images. Install requirements.txt.") from exc

    palette = plan["color_palette"]
    img = Image.new("RGB", (width, height), palette["background"])
    draw = ImageDraw.Draw(img)

    title_font = _font(44, bold=True)
    body_font = _font(26)
    small_font = _font(20)
    caption_font = _font(18)

    margin = 72
    accent = _hex(palette["accent"])
    primary = _hex(palette["primary"])
    surface = _hex(palette["surface"])
    text = _hex(palette["text"])
    secondary = _hex(palette["secondary"])

    draw.rectangle([0, 0, width, 22], fill=accent)
    draw.text((margin, 56), plan["title"], fill=primary, font=title_font)
    draw.text((margin, 118), _wrap(plan["objective"], 92)[0], fill=text, font=body_font)

    layout_name = plan["layout"]["name"]
    draw.rounded_rectangle([margin, 170, width - margin, 230], radius=10, fill=surface, outline=(221, 226, 235))
    draw.text((margin + 24, 187), layout_name, fill=primary, font=small_font)

    body_top = 270
    if "table" in layout_name.lower():
        _draw_table(draw, plan, margin, body_top, width - margin, height - 110, body_font, small_font)
    elif "process" in layout_name.lower():
        _draw_process(draw, plan, margin, body_top, width - margin, height - 130, body_font, small_font)
    elif "matrix" in layout_name.lower():
        _draw_matrix(draw, plan, margin, body_top, width - margin, height - 130, body_font, small_font)
    elif "metric" in layout_name.lower():
        _draw_metric_cards(draw, plan, margin, body_top, width - margin, height - 130, body_font, small_font)
    else:
        _draw_content_modules(draw, plan, margin, body_top, width - margin, height - 130, body_font, small_font)

    draw.text((margin, height - 56), "Generated preview; editable PPT is built from structured plan objects.", fill=secondary, font=caption_font)
    img.save(image_path)


def _draw_content_modules(draw: Any, plan: dict[str, Any], x1: int, y1: int, x2: int, y2: int, body_font: Any, small_font: Any) -> None:
    points = _body_points(plan)
    gap = 28
    card_w = int((x2 - x1 - 2 * gap) / 3)
    for idx in range(3):
        left = x1 + idx * (card_w + gap)
        right = left + card_w
        draw.rounded_rectangle([left, y1, right, y2], radius=18, fill=(255, 255, 255), outline=(218, 224, 233), width=2)
        draw.text((left + 26, y1 + 24), f"Insight {idx + 1}", fill=(24, 58, 89), font=body_font)
        for line_idx, line in enumerate(_wrap(points[idx] if idx < len(points) else "", 34)[:6]):
            draw.text((left + 26, y1 + 78 + line_idx * 34), line, fill=(17, 24, 39), font=small_font)


def _draw_table(draw: Any, plan: dict[str, Any], x1: int, y1: int, x2: int, y2: int, body_font: Any, small_font: Any) -> None:
    rows = max(4, min(7, len(_body_points(plan)) + 1))
    cols = 3
    row_h = int((y2 - y1) / rows)
    col_w = int((x2 - x1) / cols)
    headers = ["Issue", "Impact", "Implication"]
    points = _body_points(plan)
    for r in range(rows):
        for c in range(cols):
            left = x1 + c * col_w
            top = y1 + r * row_h
            fill = (24, 58, 89) if r == 0 else (255, 255, 255)
            outline = (218, 224, 233)
            draw.rectangle([left, top, left + col_w, top + row_h], fill=fill, outline=outline)
            if r == 0:
                draw.text((left + 18, top + 18), headers[c], fill=(255, 255, 255), font=small_font)
            elif c == 0 and r - 1 < len(points):
                for line_idx, line in enumerate(_wrap(points[r - 1], 30)[:2]):
                    draw.text((left + 18, top + 14 + line_idx * 26), line, fill=(17, 24, 39), font=small_font)


def _draw_process(draw: Any, plan: dict[str, Any], x1: int, y1: int, x2: int, y2: int, body_font: Any, small_font: Any) -> None:
    points = _body_points(plan)[:4] or ["Assess", "Design", "Build", "Scale"]
    gap = 34
    box_w = int((x2 - x1 - gap * (len(points) - 1)) / len(points))
    top = y1 + 120
    for idx, point in enumerate(points):
        left = x1 + idx * (box_w + gap)
        right = left + box_w
        draw.rounded_rectangle([left, top, right, top + 170], radius=18, fill=(255, 255, 255), outline=(47, 128, 237), width=3)
        draw.ellipse([left + 20, top + 20, left + 62, top + 62], fill=(47, 128, 237))
        draw.text((left + 34, top + 27), str(idx + 1), fill=(255, 255, 255), font=small_font)
        for line_idx, line in enumerate(_wrap(point, 24)[:3]):
            draw.text((left + 20, top + 78 + line_idx * 30), line, fill=(17, 24, 39), font=small_font)
        if idx < len(points) - 1:
            mid_y = top + 85
            draw.line([right + 8, mid_y, right + gap - 8, mid_y], fill=(47, 128, 237), width=5)


def _draw_matrix(draw: Any, plan: dict[str, Any], x1: int, y1: int, x2: int, y2: int, body_font: Any, small_font: Any) -> None:
    mid_x = int((x1 + x2) / 2)
    mid_y = int((y1 + y2) / 2)
    draw.rectangle([x1, y1, x2, y2], fill=(255, 255, 255), outline=(218, 224, 233), width=2)
    draw.line([mid_x, y1, mid_x, y2], fill=(218, 224, 233), width=3)
    draw.line([x1, mid_y, x2, mid_y], fill=(218, 224, 233), width=3)
    labels = ["High impact", "Quick win", "Monitor", "Mitigate"]
    coords = [(x1, y1), (mid_x, y1), (x1, mid_y), (mid_x, mid_y)]
    points = _body_points(plan)
    for idx, (left, top) in enumerate(coords):
        draw.text((left + 26, top + 22), labels[idx], fill=(24, 58, 89), font=body_font)
        text = points[idx] if idx < len(points) else "Prioritized action area"
        for line_idx, line in enumerate(_wrap(text, 48)[:3]):
            draw.text((left + 26, top + 76 + line_idx * 30), line, fill=(17, 24, 39), font=small_font)


def _draw_metric_cards(draw: Any, plan: dict[str, Any], x1: int, y1: int, x2: int, y2: int, body_font: Any, small_font: Any) -> None:
    metrics = plan.get("text_arrangement", [])[-2:-1]
    data_text = metrics[0].replace("Evidence badges: ", "") if metrics else "Proof points"
    cards = [item.strip() for item in data_text.split(",") if item.strip()][:3]
    while len(cards) < 3:
        cards.append("Key metric")
    gap = 28
    card_w = int((x2 - x1 - 2 * gap) / 3)
    for idx, metric in enumerate(cards):
        left = x1 + idx * (card_w + gap)
        draw.rounded_rectangle([left, y1, left + card_w, y1 + 180], radius=20, fill=(255, 255, 255), outline=(47, 128, 237), width=3)
        draw.text((left + 28, y1 + 34), metric, fill=(47, 128, 237), font=body_font)
        draw.text((left + 28, y1 + 96), "Business proof point", fill=(107, 114, 128), font=small_font)
    _draw_content_modules(draw, plan, x1, y1 + 230, x2, y2, body_font, small_font)


def _prompts_to_markdown(prompts: list[dict[str, str]]) -> str:
    lines = ["# Image2 Prompt Log", ""]
    for item in prompts:
        lines.append(f"## Slide {item['slide_number']}: {item['title']}")
        lines.append("")
        lines.append(f"- Provider: {item['provider']}")
        lines.append(f"- Image: {item['image_path']}")
        lines.append("")
        lines.append(item["prompt"])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _body_points(plan: dict[str, Any]) -> list[str]:
    points = []
    for item in plan.get("text_arrangement", []):
        if item.startswith("Body point"):
            points.append(item.split(": ", 1)[-1])
    return points


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        if sum(len(item) for item in current) + len(current) + len(word) > width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines or [""]


def _font(size: int, bold: bool = False) -> Any:
    try:
        from PIL import ImageFont

        candidates = [
            "arialbd.ttf" if bold else "arial.ttf",
            "Aptos.ttf",
            "Calibri.ttf",
        ]
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
        return ImageFont.load_default()
    except Exception:
        return None


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
