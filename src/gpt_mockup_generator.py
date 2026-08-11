from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from image_generator import _render_placeholder_slide
from utils import write_json, write_text


class MockupGenerationError(RuntimeError):
    pass


def generate_slide_mockups(
    plans: list[dict[str, Any]],
    output_dir: Path,
    config: dict[str, Any] | None = None,
    provider: str = "openai_cli",
    existing_image_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate or collect GPT-produced slide effect images.

    The normal production path is `openai_cli`, which uses the installed
    `$imagegen` fallback CLI and defaults to gpt-image-2. The built-in Codex
    `image_gen` tool cannot be invoked from a Python subprocess, so `prompt_only`
    writes all prompts for the agent/runtime to call explicitly.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    settings = (config or {}).get("image_generation", {})
    jobs = _build_jobs(plans, output_dir, settings)
    _write_prompt_artifacts(jobs, output_dir)

    if provider == "openai_cli":
        return _run_openai_cli(jobs, output_dir, settings)
    if provider == "existing":
        if existing_image_dir is None:
            raise MockupGenerationError("--image-dir is required when --mockup-provider existing is used.")
        return _collect_existing_images(plans, existing_image_dir, output_dir, jobs)
    if provider == "prompt_only":
        raise MockupGenerationError(
            "Prompt files were written, but no effect images were generated. "
            f"Use image2/GPT image generation and save outputs as {output_dir / 'slide_XX.png'}, "
            "or rerun with --mockup-provider openai_cli after setting OPENAI_API_KEY."
        )
    if provider == "placeholder":
        return _run_legacy_placeholder(plans, output_dir, settings, jobs)
    raise MockupGenerationError(f"Unsupported mockup provider: {provider}")


def _build_jobs(plans: list[dict[str, Any]], output_dir: Path, settings: dict[str, Any]) -> list[dict[str, Any]]:
    model = settings.get("model", "gpt-image-2")
    size = settings.get("size", "2048x1152")
    quality = settings.get("quality", "high")
    jobs = []
    for plan in plans:
        filename = f"slide_{plan['slide_number']:02d}.png"
        jobs.append(
            {
                "slide_number": plan["slide_number"],
                "title": plan["title"],
                "prompt": _strengthen_prompt(plan["image2_prompt"]),
                "model": model,
                "size": size,
                "quality": quality,
                "use_case": "productivity-visual",
                "out": filename,
                "output_path": str(output_dir / filename),
            }
        )
    return jobs


def _strengthen_prompt(prompt: str) -> str:
    return (
        prompt
        + " Treat this as a slide design effect image, not final editable text. "
        + "Make the page look like a polished real PowerPoint screenshot with crisp hierarchy, "
        + "consistent grid, high information density, and business-report styling. "
        + "Avoid fake UI chrome, watermarks, random logos, unreadable text blocks, and photo backgrounds."
    )


def _write_prompt_artifacts(jobs: list[dict[str, Any]], output_dir: Path) -> None:
    write_json(output_dir / "imagegen_jobs.json", jobs)
    jsonl_path = output_dir / "imagegen_jobs.jsonl"
    jsonl_path.write_text(
        "\n".join(json.dumps(_jsonl_job(job), ensure_ascii=False) for job in jobs) + "\n",
        encoding="utf-8",
    )

    lines = ["# GPT Image Prompt Log", ""]
    for job in jobs:
        lines.append(f"## Slide {job['slide_number']}: {job['title']}")
        lines.append("")
        lines.append(f"- Model: {job['model']}")
        lines.append(f"- Size: {job['size']}")
        lines.append(f"- Quality: {job['quality']}")
        lines.append(f"- Target: {job['output_path']}")
        lines.append("")
        lines.append(job["prompt"])
        lines.append("")
    write_text(output_dir / "image_prompts.md", "\n".join(lines).strip() + "\n")


def _jsonl_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "prompt": job["prompt"],
        "model": job["model"],
        "size": job["size"],
        "quality": job["quality"],
        "use_case": job["use_case"],
        "out": job["out"],
    }


def _run_openai_cli(jobs: list[dict[str, Any]], output_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    if not os.environ.get("OPENAI_API_KEY"):
        raise MockupGenerationError(
            "OPENAI_API_KEY is not set. The GPT image CLI cannot generate effect images. "
            f"Prompt jobs are available at {output_dir / 'imagegen_jobs.jsonl'}."
        )

    cli_path = _imagegen_cli_path()
    if not cli_path.exists():
        raise MockupGenerationError(f"Image generation CLI not found: {cli_path}")

    cmd = [
        sys.executable,
        str(cli_path),
        "generate-batch",
        "--input",
        str(output_dir / "imagegen_jobs.jsonl"),
        "--out-dir",
        str(output_dir),
        "--concurrency",
        str(settings.get("concurrency", 2)),
        "--force",
    ]
    completed = subprocess.run(
        cmd,
        cwd=output_dir.parent.parent,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise MockupGenerationError(
            "GPT image generation failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    paths = [Path(job["output_path"]) for job in jobs]
    _assert_images_exist(paths)
    return _result("openai_cli", paths, jobs, completed.stdout)


def _collect_existing_images(
    plans: list[dict[str, Any]],
    existing_image_dir: Path,
    output_dir: Path,
    jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    from shutil import copy2

    existing_image_dir = existing_image_dir.resolve()
    paths: list[Path] = []
    for plan in plans:
        filename = f"slide_{plan['slide_number']:02d}.png"
        source = existing_image_dir / filename
        if not source.exists():
            raise MockupGenerationError(f"Expected generated mockup missing: {source}")
        target = output_dir / filename
        if source.resolve() != target.resolve():
            copy2(source, target)
        paths.append(target)
    _assert_images_exist(paths)
    return _result("existing", paths, jobs, f"Collected images from {existing_image_dir}")


def _run_legacy_placeholder(
    plans: list[dict[str, Any]],
    output_dir: Path,
    settings: dict[str, Any],
    jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    width = int(settings.get("width", 1600))
    height = int(settings.get("height", 900))
    paths = []
    for plan in plans:
        path = output_dir / f"slide_{plan['slide_number']:02d}.png"
        _render_placeholder_slide(plan, path, width, height)
        paths.append(path)
    return _result("placeholder_legacy", paths, jobs, "Generated local placeholder images.")


def _result(provider: str, paths: list[Path], jobs: list[dict[str, Any]], message: str) -> dict[str, Any]:
    manifest = {
        "provider": provider,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "message": message,
        "images": [{"slide_number": job["slide_number"], "path": str(path)} for job, path in zip(jobs, paths)],
    }
    write_json(paths[0].parent / "mockup_manifest.json", manifest)
    return manifest


def _assert_images_exist(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise MockupGenerationError("Generated effect images are missing: " + ", ".join(missing))


def _imagegen_cli_path() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return codex_home / "skills" / ".system" / "imagegen" / "scripts" / "image_gen.py"
