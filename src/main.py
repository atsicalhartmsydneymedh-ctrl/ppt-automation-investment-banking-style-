from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from gpt_mockup_generator import MockupGenerationError, generate_slide_mockups
from narrative_planner import create_narrative_plan, narrative_pages_to_segments
from parser import parse_report
from production_workflow import (
    ProductionWorkflowError,
    approve_deck,
    approve_image,
    approve_page,
    generate_page,
    initialize_production_run,
    prepare_page,
    workflow_status,
)
from reference_style import CoreReferenceStyleError, extract_core_reference_style, recommended_image_size, resolve_core_reference
from segmenter import create_segments, segments_to_markdown
from slide_planner import create_slide_plans, write_slide_plans
from utils import PROJECT_ROOT, ensure_dir, load_config, resolve_output_dir, setup_logging, write_json, write_text


PRODUCTION_STAGES = (
    "prepare",
    "approve-deck",
    "prepare-page",
    "approve-page",
    "generate",
    "approve-image",
    "status",
)
PAGE_STAGES = {"prepare-page", "approve-page", "generate", "approve-image"}


def run_workflow(
    input_path: str,
    output_arg: str | None = None,
    config_path: str | None = None,
    mockup_provider: str | None = None,
    existing_image_dir: Path | None = None,
    core_reference_path: str | None = None,
) -> dict[str, str]:
    config = load_config(Path(config_path).resolve() if config_path else None)
    output_dir = resolve_output_dir(output_arg)
    logger = setup_logging(PROJECT_ROOT / "logs")

    parsed_dir = ensure_dir(output_dir / "parsed_content")
    plans_dir = ensure_dir(output_dir / "slide_plans")
    images_dir = ensure_dir(output_dir / "slide_images")
    assets_dir = ensure_dir(output_dir / "assets")
    protected_paths = [existing_image_dir.resolve()] if existing_image_dir else []
    _clear_previous_run_outputs(
        output_dir,
        parsed_dir,
        plans_dir,
        images_dir,
        assets_dir,
        protected_paths=protected_paths,
    )

    logger.info("Step 0: extracting core-reference style")
    resolved_core_reference = resolve_core_reference(input_path, core_reference_path)
    core_reference_style = extract_core_reference_style(resolved_core_reference)
    write_json(assets_dir / "core_reference_style.json", core_reference_style)
    write_text(assets_dir / "core_reference_style_prompt.md", core_reference_style["style_prompt"] + "\n")
    image_generation = dict(config.get("image_generation", {}))
    image_generation["size"] = recommended_image_size(core_reference_style)
    canvas = core_reference_style.get("canvas", {})
    slide_geometry = dict(config.get("slide", {}))
    slide_geometry.update(
        {
            "width_inches": canvas.get("width_inches", slide_geometry.get("width_inches")),
            "height_inches": canvas.get("height_inches", slide_geometry.get("height_inches")),
            "aspect_ratio": canvas.get("aspect_ratio", slide_geometry.get("aspect_ratio")),
        }
    )
    planning_config = {
        **config,
        "slide": slide_geometry,
        "core_reference_style": core_reference_style,
        "image_generation": image_generation,
    }

    logger.info("Starting workflow")
    logger.info("Project root: %s", PROJECT_ROOT)
    logger.info("Input report: %s", input_path)
    logger.info("Output dir: %s", output_dir)

    logger.info("Step 1: parsing report")
    parsed = parse_report(input_path)
    write_json(parsed_dir / "parsed_blocks.json", parsed)

    logger.info("Step 1: planning the report narrative and pagination")
    narrative_plan = create_narrative_plan(parsed, planning_config.get("narrative_planning", {}))
    write_json(parsed_dir / "narrative_plan.json", narrative_plan)
    segments = narrative_pages_to_segments(narrative_plan)
    write_json(parsed_dir / "segments.json", segments)
    write_text(parsed_dir / "segments.md", segments_to_markdown(segments))

    logger.info("Step 2: creating slide plans")
    plans = create_slide_plans(segments, planning_config)
    write_slide_plans(plans, plans_dir)

    logger.info("Step 3: generating GPT slide effect images")
    mockup_provider = mockup_provider or planning_config.get("image_generation", {}).get("provider", "openai_cli")
    mockup_manifest = generate_slide_mockups(plans, images_dir, planning_config, provider=mockup_provider, existing_image_dir=existing_image_dir)

    result = {
        "parsed_blocks": str(parsed_dir / "parsed_blocks.json"),
        "core_reference": str(resolved_core_reference),
        "core_reference_style": str(assets_dir / "core_reference_style.json"),
        "core_reference_style_prompt": str(assets_dir / "core_reference_style_prompt.md"),
        "segments": str(parsed_dir / "segments.json"),
        "slide_plans": str(plans_dir / "all_slide_plans.json"),
        "slide_images": str(images_dir),
        "mockup_manifest": str(images_dir / "mockup_manifest.json"),
    }
    write_json(output_dir / "run_manifest.json", result)
    logger.info("Workflow complete")
    return result


def run_production_stage(
    stage: str,
    output_arg: str | None = None,
    input_path: str | None = None,
    config_path: str | None = None,
    mockup_provider: str | None = None,
    existing_image_dir: Path | None = None,
    core_reference_path: str | None = None,
    page_number: int | None = None,
) -> dict[str, object]:
    """Run one explicit production stage without clearing prior approved work."""
    output_dir = resolve_output_dir(output_arg)

    if stage == "prepare":
        if not input_path:
            raise ProductionWorkflowError("--input is required for the prepare stage.")
        config = load_config(Path(config_path).resolve() if config_path else None)
        parsed = parse_report(input_path)
        resolved_core_reference = resolve_core_reference(input_path, core_reference_path)
        core_reference_style = extract_core_reference_style(resolved_core_reference)
        image_generation = dict(config.get("image_generation", {}))
        image_generation["size"] = recommended_image_size(core_reference_style)
        canvas = core_reference_style.get("canvas", {})
        slide_geometry = dict(config.get("slide", {}))
        slide_geometry.update(
            {
                "width_inches": canvas.get("width_inches", slide_geometry.get("width_inches")),
                "height_inches": canvas.get("height_inches", slide_geometry.get("height_inches")),
                "aspect_ratio": canvas.get("aspect_ratio", slide_geometry.get("aspect_ratio")),
            }
        )
        production_config = {**config, "slide": slide_geometry, "image_generation": image_generation}
        return initialize_production_run(
            output_dir,
            parsed,
            str(resolved_core_reference),
            core_reference_style,
            production_config,
        )

    if stage == "approve-deck":
        return approve_deck(output_dir)
    if stage == "prepare-page":
        return prepare_page(output_dir, _required_page(page_number, stage))
    if stage == "approve-page":
        return approve_page(output_dir, _required_page(page_number, stage))
    if stage == "generate":
        provider = mockup_provider or load_config_snapshot_provider(output_dir)
        return generate_page(output_dir, _required_page(page_number, stage), provider, existing_image_dir)
    if stage == "approve-image":
        return approve_image(output_dir, _required_page(page_number, stage), load_workflow_tolerance(output_dir))
    if stage == "status":
        return workflow_status(output_dir)
    raise ProductionWorkflowError(f"Unsupported production stage: {stage}")


def load_config_snapshot_provider(output_dir: Path) -> str:
    path = output_dir / "config_snapshot.json"
    if not path.exists():
        raise ProductionWorkflowError(f"Production run is not prepared: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    return config.get("image_generation", {}).get("provider", "openai_cli")


def load_workflow_tolerance(output_dir: Path) -> float:
    path = output_dir / "config_snapshot.json"
    if not path.exists():
        raise ProductionWorkflowError(f"Production run is not prepared: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    return float(config.get("workflow", {}).get("aspect_ratio_tolerance", 0.005))


def _required_page(page_number: int | None, stage: str) -> int:
    if page_number is None or page_number < 1:
        raise ProductionWorkflowError(f"--page with a positive page number is required for stage {stage}.")
    return page_number


def _clear_previous_run_outputs(
    output_dir: Path,
    parsed_dir: Path,
    plans_dir: Path,
    images_dir: Path,
    assets_dir: Path,
    protected_paths: list[Path] | None = None,
) -> None:
    protected_paths = protected_paths or []
    patterns = {
        parsed_dir: ["*.json", "*.md"],
        plans_dir: ["*.json", "*.md"],
        images_dir: ["slide_*.png", "*.json", "*.jsonl", "*.md"],
        assets_dir: ["*.json", "*.png", "*.svg"],
        output_dir: ["run_manifest.json"],
    }
    for directory, globs in patterns.items():
        for pattern in globs:
            for path in directory.glob(pattern):
                if path.is_file() and not _is_protected(path, protected_paths):
                    path.unlink()

    _remove_path(output_dir / "ai_mockups", protected_paths)


def _remove_path(path: Path, protected_paths: list[Path]) -> None:
    if not path.exists() or _is_protected(path, protected_paths):
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _is_protected(path: Path, protected_paths: list[Path]) -> bool:
    resolved = path.resolve()
    for protected in protected_paths:
        protected_resolved = protected.resolve()
        if resolved == protected_resolved:
            return True
        try:
            resolved.relative_to(protected_resolved)
            return True
        except ValueError:
            pass
        try:
            protected_resolved.relative_to(resolved)
            return True
        except ValueError:
            pass
    return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the approval-gated consulting-slide production workflow.")
    parser.add_argument("--mode", default="production", choices=["production", "legacy"], help="Production is approval-gated; legacy preserves the old batch behavior.")
    parser.add_argument("--stage", default="prepare", choices=PRODUCTION_STAGES, help="One production stage to execute. Ignored in legacy mode.")
    parser.add_argument("--page", type=int, default=None, help="One-based page number for page-scoped production stages.")
    parser.add_argument("--input", default=None, help="Path to a .docx, .pdf, .md, or .txt report. Required for prepare and legacy mode.")
    parser.add_argument("--output", default="output", help="Output directory inside the project folder. Default: output")
    parser.add_argument("--config", default=None, help="Optional config JSON path.")
    parser.add_argument(
        "--mockup-provider",
        default=None,
        choices=["openai_cli", "prompt_only", "existing", "placeholder"],
        help="Effect-image provider. Default comes from config and is openai_cli.",
    )
    parser.add_argument("--image-dir", default=None, help="Existing GPT-generated slide_XX.png directory.")
    parser.add_argument(
        "--core-reference",
        default=None,
        help="Editable core PPTX whose style is extracted before planning. Auto-detects one template-named PPTX beside the report when omitted.",
    )
    args = parser.parse_args(argv)
    if args.mode == "legacy" and not args.input:
        parser.error("--input is required in legacy mode")
    if args.mode == "production" and args.stage == "prepare" and not args.input:
        parser.error("--input is required for the prepare stage")
    if args.mode == "production" and args.stage in PAGE_STAGES and (args.page is None or args.page < 1):
        parser.error(f"--page is required for the {args.stage} stage")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.mode == "legacy":
            result = run_workflow(
                args.input,
                args.output,
                args.config,
                mockup_provider=args.mockup_provider,
                existing_image_dir=Path(args.image_dir).resolve() if args.image_dir else None,
                core_reference_path=args.core_reference,
            )
        else:
            result = run_production_stage(
                args.stage,
                args.output,
                input_path=args.input,
                config_path=args.config,
                mockup_provider=args.mockup_provider,
                existing_image_dir=Path(args.image_dir).resolve() if args.image_dir else None,
                core_reference_path=args.core_reference,
                page_number=args.page,
            )
    except (MockupGenerationError, CoreReferenceStyleError, ProductionWorkflowError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
