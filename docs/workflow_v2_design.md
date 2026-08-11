# Workflow v2 Design: Evidence-First, Page-by-Page Effect Images

Date: 2026-07-28

## Why the Successful P1 Worked

The approved European-index page improved only after the workflow stopped treating the report as text to summarize and began treating it as evidence to arrange.

The successful sequence was:

1. restore the missing foundational topic: introduce FTSE 100, CAC 40, and DAX before comparing them;
2. regroup report Sections II and III into one coherent page question;
3. write dense, substantive explanatory copy before choosing charts;
4. assign a distinct evidence form to each analytical question;
5. specify the composition precisely: three parallel index modules, a full-width divider, lower-left rules evidence, and lower-right industry evidence with commentary;
6. generate one page and inspect it before proceeding.

Earlier drafts failed because they used chapter-length segmentation, generic layout archetypes, sparse summaries, repeated table/card grammar, and underspecified charts.

## Recommended Operating Model

The workflow should use three nested contracts.

### Deck Contract

Defines the audience, page count, reporting questions, narrative sequence, and full-report coverage.

### Page Contract

Defines the page conclusion, subsection structure, exact prose, evidence assignments, reading order, density, and source blocks.

### Evidence Contract

Defines the question answered by each visual, its full data model, chart grammar, axes, labels, annotations, source, and linked prose.

An image prompt is generated only after all three contracts are complete.

## Approval Logic

A page is ready for image generation only when:

- coverage: all assigned source material has been used or intentionally omitted with a reason;
- argument: the title, prose, and evidence form one closed reasoning chain;
- evidence: every chart is drawable without inventing data or structure;
- design: regions, proportions, hierarchy, and style roles are explicit;
- production: the effect image matches the reference canvas ratio within 0.5%;
- variety: the composition and primary evidence form are not duplicates of the previous page.

## Lessons to Reuse

- The core reference is a visual style contract, not a page-layout template.
- Page count should be decided after the full-report content map, not before it.
- Foundational introductions should not be skipped in a comparative presentation.
- Dense pages can still read cleanly when hierarchy is stronger than decoration.
- Evidence visuals should be selected by semantic question, not by convenience.
- Real logos are data-bearing evidence and require authentic assets.
- One-page approval loops cost less than repairing a weak batch.

## Editable-PPT Production Extension

The approved effect image is the visual source of truth, but it is not sufficient by itself for reliable editable-PPT reconstruction. The production extension adds two contracts after page approval.

### Asset Contract

Inventory all icons, maps, logos, photographs, illustrations, textures, and complex visual elements that cannot be reproduced reliably as native PowerPoint objects. For every asset, record its ID, filename, semantic purpose, placement, recommended size, source, license, and preferred insertion format. Provide transparent PNG files, optional SVG files, and a contact sheet. Authentic company logos must come from official sources; missing required assets must not be replaced by emoji, symbol fonts, or improvised geometry.

### Reconstruction Contract

Define the exact canvas size, font family, font size hierarchy, major-region coordinates, native-object boundaries, image-asset paths, overflow rules, and post-generation checks. Provide both absolute paths for the current machine and portable relative paths for the packaged delivery.

The recommended production path is:

`approved effect image -> asset decomposition -> fixed typography -> GPT for PPT rebuild prompt -> editable PPT -> render and QA`

Other PowerPoint-capable AI tools may reconstruct directly from the effect image, but the full asset and reconstruction contracts should still be supplied. The hybrid target is visual fidelity plus editable core information, not mandatory native reconstruction of every decorative element.
