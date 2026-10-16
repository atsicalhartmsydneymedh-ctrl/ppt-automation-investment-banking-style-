# Codex Automation Entry

Use this project as a Codex-led editorial and effect-image workspace.

## Current Stage-Gated Entry

The default entry point is resumable and approval-gated. It never batch-generates effect images.

```powershell
# 1. Parse the report, inspect the core reference, and create the editable deck contract.
powershell -ExecutionPolicy Bypass -File scripts\run_latest_report.ps1 -Stage prepare -CoreReference "input\核心参考-模板.pptx" -Output "output\my_run"

# 2. After reviewing content_map\deck_contract.json, approve deck pagination and source coverage.
powershell -ExecutionPolicy Bypass -File scripts\run_latest_report.ps1 -Stage approve-deck -Output "output\my_run"

# 3. Prepare, review, and approve exactly one page's content/evidence/design contracts.
powershell -ExecutionPolicy Bypass -File scripts\run_latest_report.ps1 -Stage prepare-page -Page 1 -Output "output\my_run"
powershell -ExecutionPolicy Bypass -File scripts\run_latest_report.ps1 -Stage approve-page -Page 1 -Output "output\my_run"

# 4. Generate exactly one effect image; without an API key this creates a prompt checkpoint.
powershell -ExecutionPolicy Bypass -File scripts\run_latest_report.ps1 -Stage generate -Page 1 -Output "output\my_run"

# 5. After visual review, record aspect-ratio and human approval.
powershell -ExecutionPolicy Bypass -File scripts\run_latest_report.ps1 -Stage approve-image -Page 1 -Output "output\my_run"

# Inspect resumable state and next actions at any time.
powershell -ExecutionPolicy Bypass -File scripts\run_latest_report.ps1 -Stage status -Output "output\my_run"
```

The previous character-segmentation and batch-image path remains available only as an explicit compatibility mode:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_latest_report.ps1 -Legacy -CoreReference "input\核心参考-模板.pptx"
```

## Manual Preparation

Put the report and the current core-reference PPT in `input/`, then start the production preparation stage:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_latest_report.ps1 -Stage prepare -CoreReference "input\核心参考-模板.pptx" -Output "output\my_run"
```

The script selects the newest supported report, extracts the current template's style contract, creates an order-neutral semantic source payload, and asks DeepSeek through its Chat Completions endpoint for a JSON deck contract. The result is then checked against the full local schema. It does not approve final pagination or authorize image generation. If the configured narrative AI is unavailable, it stops with `narrative_ai_required` and creates no heuristic deck contract.

## Required Codex Sequence

1. **Read the complete report and reference PPT.**
   Save the style contract and parsed source blocks.
2. **Build a full-report content map.**
   Inventory all chapters, conclusions, tables, examples, companies, risks, and recommendations with source block IDs.
3. **Define deck-level reporting questions with narrative AI.**
   Give the AI all semantic source records without heading formats or original ordering. It may regroup material across any chapter boundary. Validate complete source coverage, unique assignment, one conclusion per page, and a cumulative storyline before approving the page count. Save the automatic restructuring report.
4. **Create one page's content arrangement.**
   Write the conclusion title, subsection headings, substantive bullets, exact evidence, and text-to-evidence links.
5. **Create the page's evidence specifications.**
   Define the page's SmartArt-like semantic skeleton separately from its quantitative evidence. For each chart, define complete data, axes, scales, annotations, source, and supported claim.
6. **Create the page's visual design draft.**
   Apply the current reference's palette, typography, title hierarchy, footer, and density. Design the page composition from its content rather than copying the reference layout.
7. **Present the drafts for review.**
   Do not generate an effect image until content coverage, evidence completeness, and layout are accepted.
8. **Generate exactly one effect image.**
   Review it against the three approved drafts and verify the output aspect ratio against the current core reference. Refine and regenerate the same page until approved.
9. **Lock the page and inventory external assets.**
   Save the approved image, then classify every visible element as a native PowerPoint object or an external image asset. Build the icon, map, logo, photo, and illustration manifest before reconstruction.
10. **Prepare the editable-PPT rebuild package.**
    Add fixed font sizes, major-region coordinates, native-object boundaries, transparent PNG/SVG assets, a contact sheet, source/license notes, and a GPT for PPT reconstruction prompt with absolute and portable relative paths.
11. **Reconstruct and QA the editable PPT when requested.**
    GPT for PPT is the recommended reconstruction path, although another PowerPoint-capable AI may rebuild from the approved image and package. Verify fonts, sizes, asset completeness, editability, overflow, and visual fidelity.
12. **Finish with a deck-wide audit.**
    Check report coverage, cross-page repetition, visual-form variety, style consistency, sources, external assets, and reconstruction status.

## Hard Stops

- Do not batch-generate effect images.
- Do not paginate by character count alone.
- Do not use heading styles, chapter numbering, document page numbers, source order, or table position as pagination rules.
- Do not silently fall back to deterministic pagination when narrative AI is unavailable or invalid.
- Do not skip report foundations merely to foreground later comparisons.
- Do not treat charts as decoration or use chart descriptions as analysis.
- Do not reduce source tables to a few convenient numbers without a recorded coverage decision.
- Do not reuse the same table/card composition across consecutive pages.
- Do not use generic rectangular modules when a pyramid, ladder, process lane, cycle, convergence, radial relationship, or decision path expresses the logic more clearly.
- Do not use SmartArt-like shapes as decoration or as a substitute for accurate quantitative charts.
- Do not use PowerPoint default SmartArt gradients, bevels, 3D effects, or heavy shadows.
- Do not treat AI-generated company logos as final assets.
- Do not approve an image whose canvas ratio differs from the core reference by more than 0.5%.
- Do not reconstruct an editable PPT before its effect image, typography specification, and asset contract are approved.
- Do not replace missing icons, maps, logos, or illustrations with emoji, symbol fonts, or improvised geometry.

## Per-Page Approval Record

For each page, retain:

- assigned report sections and source block IDs;
- approved content arrangement;
- approved evidence specifications;
- approved visual design draft;
- effect-image prompt or generation record;
- approved image path;
- native-object versus image-asset classification;
- asset manifest, PNG/SVG paths, contact sheet, and license notes;
- fixed typography and GPT for PPT reconstruction prompt;
- editable-PPT render and QA record when reconstruction is requested;
- unresolved source or asset issues.

This record is what makes a successful page reproducible on a later report and a different core-reference PPT.
