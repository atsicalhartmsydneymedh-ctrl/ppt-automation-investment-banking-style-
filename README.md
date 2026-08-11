# PPT Effect-Image Workflow

[中文说明](README_CN.md)

This workflow turns a report into high-density consulting slide effect images, then prepares an optional production handoff for reconstructing those approved images as editable PowerPoint slides. The effect image is the primary design artifact; editable PPT production works best when the image is paired with a fixed typography specification, an external asset pack, and a reconstruction prompt for GPT for PPT or another PowerPoint-capable AI.

## Core Principle

Do not move directly from report segmentation to image generation. Each slide must first become a complete reporting argument:

`report evidence -> page question -> content arrangement -> evidence specification -> composition decision -> visual design -> effect image -> asset decomposition -> rebuild package -> editable PPT`

The unit of pagination is a reporting question with a closed evidence loop, not a fixed character count or an original chapter boundary.

## Workflow Gates

### Gate 0: Core-Reference Style Contract

Read the declared core-reference PPT at the beginning of every run. Extract only:

- canvas size and aspect ratio;
- primary, support, neutral, and background colors;
- title, body, caption, and source typography;
- title hierarchy and conclusion-led title treatment;
- footer, source, and page-number conventions;
- typical information density and whitespace ratio.

Do not copy the reference deck's composition, grid, module geometry, or line language. Those are designed per page from the report content.

Output:

- `output/assets/core_reference_style.json`
- `output/assets/core_reference_style_prompt.md`

### Gate 1: Full-Report Content Map

Parse the complete report into addressable blocks and build a coverage map containing:

- chapter and subsection hierarchy;
- key conclusions and explanatory paragraphs;
- every source table and quantitative field;
- representative companies, examples, risks, and recommendations;
- source block IDs for traceability.

Before pagination, identify the major reporting questions and map every material block to one of them. Cross-chapter regrouping is allowed when it produces a clearer reporting argument.

Pass criteria:

- all material chapters are represented;
- no source table or major conclusion is silently dropped;
- repeated content is explicitly merged rather than duplicated.

### Gate 2: Deck-Level Storyline and Pagination

Define the whole deck before designing any page:

- one conclusion-led title per page;
- one primary question per page;
- two to four subordinate themes per page;
- the source sections and block IDs assigned to each page;
- a page-to-page narrative sequence;
- one primary semantic-diagram family for each page when the content contains a hierarchy, process, relationship, cycle, convergence, or decision path;
- a coverage audit showing where every material report block is used.

Prefer fewer, denser pages when requested, but do not combine unrelated themes merely to hit a page count.
Do not repeat the same primary semantic-diagram family on adjacent pages.

### Gate 3: Page Content Arrangement

Create a content arrangement draft before creating a visual design draft. For each page, specify:

- the exact point the page must prove;
- two to four subsection headings;
- two to three substantive bullets under each heading when the source supports them;
- the exact data, company, example, or comparison used as evidence;
- the relationship between each text section and its evidence visual;
- the reading order and relative space allocation.

Explanatory text must synthesize the topic. Charts support and verify that synthesis; chart descriptions are not a substitute for analysis.

Pass criteria:

- the page can be understood from text alone;
- every chart has an explicit claim to support;
- the page uses the assigned source material with no major omission;
- information density matches the core reference.

### Gate 4: Evidence-Visual Specification

Design each evidence visual before designing the overall page. Each visual must answer one precise question and include:

- visual form and why it fits the evidence;
- complete data fields and labels;
- axis, scale, ordering, units, and legend;
- annotations and the conclusion the reader should notice;
- its linked subsection heading;
- source note and asset requirements.

Use semantic visual forms such as dot plots, indexed timelines, DNA tracks, funnels, pyramids, process lanes, scale bars, decomposition bridges, or scenario paths. Do not default repeatedly to tables, cards, or generic bar charts.

Separate two visual layers:

- **semantic diagram layer:** SmartArt-like hierarchy, process, relationship, cycle, matrix, convergence, or segmentation shapes that explain how ideas relate;
- **quantitative evidence layer:** charts, axes, rulers, tables, and labels that preserve exact values.

SmartArt-like shapes must carry meaning. Do not replace precise quantitative charts with decorative pyramids, circles, arrows, or funnels.

For company logos and other brand assets, use official source files in the final artwork. AI-generated logo approximations may appear only in a layout draft and must be marked as placeholders.

### Gate 5: Page Visual Design Draft

Only after Gates 3 and 4 pass, define the page composition:

- page hierarchy and reading path;
- region dimensions and alignment anchors;
- placement of text, evidence, logos, dividers, and sources;
- exact color roles and typography from the current core reference;
- visual contrast and whitespace;
- the selected SmartArt-like semantic skeleton, including node meaning, direction, hierarchy, and text capacity;
- how quantitative evidence is embedded beside or inside that skeleton without losing scale accuracy;
- how this page differs structurally from adjacent pages.

The design draft must be detailed enough that another designer could reproduce the page without inventing missing charts or content.
Use `docs/smartart_visual_grammar.md` to select the page skeleton.

### Gate 4.5: Composition Decision

Before selecting the page layout, the deterministic planner creates a page-level decision contract:

`Communication Objective → Information Density → Design Intensity → Visual Strategy → Archetype → Spatial Narrative → Asset Strategy`

- Intensity 1–2: favor fast scanning, exact comparison, tables, matrices, and process structures. Do not force a hero visual.
- Intensity 3: use an analytical claim-to-proof reading path.
- Intensity 4–5: require a single visual proposition and a dominant geometry. Do not substitute equal cards, generic grids, or default SmartArt.

The contract is persisted in every `slide_plans/*.json` and `.md` artifact and included in the image-generation prompt. Set `composition_decision.enabled` to `false` in a config file to restore the prior layout-only routing.

### Gate 6: Per-Page Effect Image

Generate one page at a time. Never batch-generate unreviewed pages.

For each page:

1. generate one effect image from the approved content, evidence, and design drafts;
2. compare it against all three drafts;
3. check content coverage, chart completeness, text-image correspondence, hierarchy, density, template style, and exact canvas ratio;
4. revise the draft or prompt and regenerate the same page;
5. continue only after the page is approved.

If the first design draft or effect image is visibly low-density, explicitly request a new **high-density design draft and high-density effect image**. Trigger this revision when the page contains excessive empty space, oversized cards or headings, only a few short statements, unused source evidence, decorative rather than explanatory charts, or materially lower density than the core-reference deck.

Recommended revision instruction:

> The first version is too low-density. Preserve the approved storyline, conclusions, and source-grounded evidence, then regenerate a high-density design draft and high-density effect image. Add meaningful information regions, data, examples, annotations, and stronger text-to-visual correspondence. Reduce unproductive whitespace and oversized containers, but do not manufacture density by shrinking text below readable sizes, adding decorative boxes, or inventing unsupported content. Maintain clear hierarchy, a closed evidence chain, and strong readability.

High density means more useful argument and evidence per page; it does not mean smaller type or more containers.

Save approved images under a run-specific folder such as:

`output/<run_id>/slide_images/slide_XX_<topic>.png`

### Gate 7: External Asset Decomposition

After an effect image is approved, inventory every visible element and classify it as either:

- a native PowerPoint object: text, fills, borders, separators, arrows, tables, simple charts, and basic geometry; or
- an external image asset: icons, maps, photographs, logos, illustrations, textures, complex decorative geometry, and any element that GPT for PPT cannot reproduce reliably.

For every required image asset:

- assign an asset ID, filename, meaning, placement, recommended size, insertion mode, and source;
- prefer official sources for company logos and licensed or public-domain sources for maps and reusable graphics;
- provide transparent PNG by default and SVG as an optional fallback;
- create a contact sheet for visual inspection;
- record source and license information;
- never replace a missing asset with emoji, Wingdings, Unicode symbols, or improvised geometry.

If a required asset cannot be read by the reconstruction tool, reconstruction must stop and request the missing upload instead of silently omitting or substituting it.

### Gate 8: Editable-PPT Rebuild Package

Prepare one rebuild package per approved page containing:

- the approved effect image;
- a GPT for PPT reconstruction prompt;
- fixed page dimensions, typography, font sizes, and major-region coordinates;
- an explicit boundary between native PowerPoint objects and external images;
- the PNG/SVG assets, asset manifest, contact sheet, and license notes;
- both absolute local paths and portable relative paths.

The default delivery font contract is KaiTi for Chinese and Arial for English, numbers, and punctuation. Disable automatic font shrinking.

### Gate 9: Reconstruction and QA

Reconstruct the page with GPT for PPT or another PowerPoint-capable AI. An AI may also rebuild directly from the effect image, but fidelity is substantially more reliable when it also receives the fixed typography specification and complete asset pack.

Verify:

- page size and major-region geometry;
- exact fonts and font sizes;
- external-asset completeness and image aspect ratio;
- native editability of text and core information objects;
- data accuracy, overflow, overlap, and clipping;
- visual correspondence with the approved effect image.

## Quality Checklist

- The title states a conclusion rather than naming a topic.
- Low-density first drafts are regenerated with an explicit high-density instruction before page approval.
- The page begins with the context the audience needs; it does not skip foundational report sections.
- Text contains substantive synthesis, not labels or chart narration.
- Every evidence visual has complete axes, values, units, annotations, and a linked claim.
- At least two visual languages are used when a dense page contains several evidence types.
- When the content contains a real relationship or process, the page uses a semantic diagram rather than arranging every idea as rectangular modules.
- SmartArt-like diagrams use the current reference palette and flat institutional styling; they do not use PowerPoint default gradients, bevels, shadows, or 3D effects.
- Representative companies use authentic logos when logos are required.
- Adjacent pages do not repeat the same composition.
- The core reference controls style, not content architecture.
- The exported image aspect ratio matches the core reference within 0.5%; otherwise regenerate or adapt it without distortion.
- Every non-native image element has a corresponding asset or an explicitly approved placeholder.
- Rebuild prompts define fixed font sizes and disable automatic font shrinking.
- Editable PPT reconstruction is treated as a separate production stage after effect-image approval.

## Run

```powershell
cd "path\to\report-to-consulting-slides"
python src/main.py --input "input\report.docx" --core-reference "input\core-reference.pptx" --output "output" --mockup-provider prompt_only
```

The deterministic runner currently prepares the style contract, parsed content, preliminary segments, and baseline slide prompts. The coverage audit, content arrangement, evidence specification, design review, and page-by-page approval gates are Codex-led editorial steps and must be completed before image generation.

## Outputs

- `output/assets/`: current core-reference style contract.
- `output/parsed_content/`: parsed report blocks and preliminary segments.
- `output/<run_id>/content_map/`: full-report coverage map and deck storyline.
- `output/<run_id>/content_arrangements/`: page-level content arrangements.
- `output/<run_id>/evidence_specs/`: chart and evidence specifications.
- `output/<run_id>/design_drafts/`: approved page visual designs.
- `output/<run_id>/slide_images/`: approved per-page effect images.
- `output/<run_id>/ppt_rebuild_packages/`: per-page typography specifications, prompts, asset manifests, PNG/SVG files, contact sheets, license notes, and portable ZIP packages.
