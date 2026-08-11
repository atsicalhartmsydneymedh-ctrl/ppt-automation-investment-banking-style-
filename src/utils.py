from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_inside_project(path: Path, project_root: Path = PROJECT_ROOT) -> Path:
    resolved = path.resolve()
    root = project_root.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Output path must stay inside project root: {root}") from exc
    return resolved


def resolve_output_dir(output_arg: str | None) -> Path:
    if output_arg:
        output_path = Path(output_arg)
        if not output_path.is_absolute():
            output_path = PROJECT_ROOT / output_path
    else:
        output_path = PROJECT_ROOT / "output"
    output_path = ensure_inside_project(output_path)
    return ensure_dir(output_path)


def setup_logging(log_dir: Path) -> logging.Logger:
    ensure_dir(log_dir)
    logger = logging.getLogger("ppt_automation_workflow")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"run_{timestamp}.log"

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.info("Logging to %s", log_path)
    return logger


def write_json(path: Path, data: Any) -> Path:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_text(path: Path, text: str) -> Path:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or PROJECT_ROOT / "config" / "defaults.json"
    if not path.exists():
        return {}
    return read_json(path)


def slugify(value: str, fallback: str = "slide") -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or fallback


def first_sentence(text: str, max_chars: int = 220) -> str:
    text = normalize_space(text)
    if not text:
        return ""
    match = re.search(r"(.+?[.!?。！？])(?:\s|$)", text)
    sentence = match.group(1) if match else text
    if len(sentence) <= max_chars:
        return sentence
    return sentence[: max_chars - 3].rstrip() + "..."


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def chunk_text(text: str, max_chars: int) -> list[str]:
    text = normalize_space(text)
    if len(text) <= max_chars:
        return [text] if text else []

    sentences = re.split(r"(?<=[.!?。！？])\s*", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for sentence in sentences:
        if current and current_len + len(sentence) + 1 > max_chars:
            chunks.append(" ".join(current).strip())
            current = []
            current_len = 0
        current.append(sentence)
        current_len += len(sentence) + 1
    if current:
        chunks.append(" ".join(current).strip())
    return chunks


def extract_data_points(text: str, limit: int = 6) -> list[str]:
    text = normalize_space(text)
    patterns = [
        r"(?:\$|USD\s*)\d+(?:[\.,]\d+)?\s*(?:m|bn|million|billion)?",
        r"\d+(?:\.\d+)?%",
        r"\b20\d{2}\b",
        r"\b\d+(?:\.\d+)?x\b",
        r"\b\d+\s*(?:to|-)\s*\d+\b",
    ]
    points: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            item = normalize_space(match)
            if item and item not in points:
                points.append(item)
            if len(points) >= limit:
                return points
    return points


def safe_read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="ignore")
