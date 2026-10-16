from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image


def audit_effect_image(
    image_path: str | Path,
    style: dict[str, Any],
    page_structure: dict[str, Any] | None = None,
    aspect_ratio_tolerance: float = 0.005,
) -> dict[str, Any]:
    """Run measurable effect-image checks before human approval.

    This intentionally does not pretend that raster analysis can verify exact
    copy or font identity. Those remain explicit manual checks at approval.
    """
    path = Path(image_path)
    with Image.open(path) as source:
        image = source.convert("RGB")
    width, height = image.size
    expected_ratio = _expected_ratio(style)
    ratio_error = abs((width / height) / expected_ratio - 1)

    hard_palette = style.get("hard_constraints", {}).get("palette", {})
    roles = style.get("palette", {}).get("roles", {})
    allowed_hex = hard_palette.get("allowed_hex") or list(roles.values())
    allowed = [_rgb(value) for value in allowed_hex if _valid_hex(value)]
    background = _rgb(roles.get("background") or style.get("palette", {}).get("background_color") or "FFFFFF")
    distance_tolerance = float(hard_palette.get("nearest_color_distance", 58))
    max_unapproved_share = float(hard_palette.get("max_unapproved_accent_share", 0.10))

    sample = image.copy()
    sample.thumbnail((240, 160))
    dominant = _dominant_colors(sample, 16)
    pixel_total = sum(count for _, count in dominant) or 1
    unapproved_accent = 0
    for color, count in dominant:
        if _chroma(color) < 24:
            continue
        if allowed and min(_distance(color, candidate) for candidate in allowed) > distance_tolerance:
            unapproved_accent += count
    unapproved_share = unapproved_accent / pixel_total

    occupancy = _occupancy(sample, background)
    failures: list[str] = []
    warnings: list[str] = []
    if ratio_error > aspect_ratio_tolerance:
        failures.append(
            f"aspect_ratio_error={ratio_error:.4f} exceeds tolerance={aspect_ratio_tolerance:.4f}"
        )
    if allowed and unapproved_share > max_unapproved_share:
        failures.append(
            f"unapproved_accent_share={unapproved_share:.3f} exceeds reference limit={max_unapproved_share:.3f}"
        )
    if occupancy["foreground_share"] < 0.025 or occupancy["occupied_grid_share"] < 0.10:
        failures.append("image is materially blank or too sparse for the approved page content")

    topology_checks = _topology_checks(occupancy, page_structure or {})
    for check in topology_checks:
        if not check["passed"]:
            failures.append(check["message"])
    if occupancy["foreground_share"] > 0.78:
        warnings.append("foreground coverage is very high; inspect crowding, overlap, and readable type size")

    return {
        "schema_version": "1.0",
        "image": str(path),
        "passed": not failures,
        "hard_failures": failures,
        "warnings": warnings,
        "canvas": {
            "width": width,
            "height": height,
            "expected_ratio": round(expected_ratio, 6),
            "actual_ratio": round(width / height, 6),
            "ratio_error": round(ratio_error, 6),
        },
        "palette": {
            "policy": style.get("hard_constraints", {}).get("policy", "derived_from_reference_roles"),
            "allowed_hex": [value.upper().removeprefix("#") for value in allowed_hex if _valid_hex(value)],
            "dominant_colors": [
                {"hex": _hex(color), "share": round(count / pixel_total, 4)} for color, count in dominant[:10]
            ],
            "unapproved_accent_share": round(unapproved_share, 4),
            "max_unapproved_accent_share": max_unapproved_share,
        },
        "occupancy": occupancy,
        "topology_checks": topology_checks,
        "manual_approval_checks": [
            "approved title and evidence text are accurate and not garbled",
            "Chinese uses KaiTi; English, numbers, and punctuation use Arial",
            "title hierarchy and footer/source/page-number chrome follow the core reference",
            "matched mechanism topology and content relationships are visibly preserved",
            "no unintended overlap, clipping, tiny text, or unsupported decorative content",
        ],
    }


def _dominant_colors(image: Image.Image, limit: int) -> list[tuple[tuple[int, int, int], int]]:
    quantized = image.quantize(colors=limit, method=Image.Quantize.MEDIANCUT).convert("RGB")
    colors = quantized.getcolors(maxcolors=image.width * image.height) or []
    return sorted(((color, count) for count, color in colors), key=lambda item: item[1], reverse=True)


def _occupancy(image: Image.Image, background: tuple[int, int, int]) -> dict[str, Any]:
    width, height = image.size
    pixels = image.load()
    foreground = [[False for _ in range(width)] for _ in range(height)]
    total_foreground = 0
    for y in range(height):
        for x in range(width):
            is_foreground = _distance(pixels[x, y], background) > 26
            foreground[y][x] = is_foreground
            total_foreground += int(is_foreground)
    grid_columns, grid_rows = 12, 7
    occupied = 0
    for row in range(grid_rows):
        y0, y1 = row * height // grid_rows, (row + 1) * height // grid_rows
        for column in range(grid_columns):
            x0, x1 = column * width // grid_columns, (column + 1) * width // grid_columns
            cell_total = max(1, (x1 - x0) * (y1 - y0))
            cell_foreground = sum(foreground[y][x] for y in range(y0, y1) for x in range(x0, x1))
            occupied += int(cell_foreground / cell_total >= 0.025)
    left = sum(foreground[y][x] for y in range(height) for x in range(width // 2)) / max(1, height * (width // 2))
    right = sum(foreground[y][x] for y in range(height) for x in range(width // 2, width)) / max(1, height * (width - width // 2))
    upper = sum(foreground[y][x] for y in range(height // 2) for x in range(width)) / max(1, (height // 2) * width)
    lower = sum(foreground[y][x] for y in range(height // 2, height) for x in range(width)) / max(1, (height - height // 2) * width)
    return {
        "foreground_share": round(total_foreground / max(1, width * height), 4),
        "occupied_grid_share": round(occupied / (grid_columns * grid_rows), 4),
        "left_foreground_share": round(left, 4),
        "right_foreground_share": round(right, 4),
        "upper_foreground_share": round(upper, 4),
        "lower_foreground_share": round(lower, 4),
    }


def _topology_checks(occupancy: dict[str, Any], structure: dict[str, Any]) -> list[dict[str, Any]]:
    positions = {str(group.get("position", "any")) for group in structure.get("groups", [])}
    checks: list[dict[str, Any]] = []
    if {"left", "right"}.issubset(positions):
        passed = occupancy["left_foreground_share"] >= 0.02 and occupancy["right_foreground_share"] >= 0.02
        checks.append(
            {
                "name": "side_by_side_group_occupancy",
                "passed": passed,
                "message": "approved left/right peer groups are not both visibly occupied",
            }
        )
    if {"top", "bottom"}.issubset(positions):
        passed = occupancy["upper_foreground_share"] >= 0.02 and occupancy["lower_foreground_share"] >= 0.02
        checks.append(
            {
                "name": "stacked_group_occupancy",
                "passed": passed,
                "message": "approved top/bottom groups are not both visibly occupied",
            }
        )
    return checks


def _expected_ratio(style: dict[str, Any]) -> float:
    canvas = style.get("canvas", {})
    width = float(canvas.get("width_inches") or 0)
    height = float(canvas.get("height_inches") or 0)
    if width > 0 and height > 0:
        return width / height
    ratio = str(canvas.get("aspect_ratio", "16:9"))
    if ":" in ratio:
        left, right = ratio.split(":", 1)
        try:
            return float(left) / float(right)
        except ValueError:
            pass
    return 16 / 9


def _valid_hex(value: Any) -> bool:
    normalized = str(value or "").upper().removeprefix("#")
    if len(normalized) != 6:
        return False
    try:
        int(normalized, 16)
        return True
    except ValueError:
        return False


def _rgb(value: str) -> tuple[int, int, int]:
    normalized = value.upper().removeprefix("#")
    return tuple(int(normalized[index : index + 2], 16) for index in (0, 2, 4))


def _hex(color: tuple[int, int, int]) -> str:
    return "{:02X}{:02X}{:02X}".format(*color)


def _distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def _chroma(color: tuple[int, int, int]) -> int:
    return max(color) - min(color)
