# Programmatic Layout Proof of Concept Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build one editable slide from a machine-readable page contract, using only report-sourced data and deterministic text/chart/table rendering.

**Architecture:** A JSON page contract records the selected composition and content. A JavaScript module reads that contract, resolves proportional regions into exact positions, creates native PowerPoint text, charts, and a table, then exports PPTX, PNG, and layout JSON for visual and overflow QA.

**Tech Stack:** JavaScript ES modules, `@oai/artifact-tool`, native PowerPoint charts/tables.

---

### Task 1: Create the page contract

**Files:**
- Create: `tmp/programmatic_slide4_poc/page-contract.json`

**Steps:**
1. Record the 4:3 canvas, safe margins, typography, region ratios, and reading order.
2. Use only report-sourced event and valuation data.
3. Validate that every visible number is traceable to a source block.

### Task 2: Compile the contract into an editable slide

**Files:**
- Create: `tmp/programmatic_slide4_poc/build-slide.mjs`
- Create: `output/ftse_cac_dax_programmatic_poc_20260811/slide_04_programmatic.pptx`

**Steps:**
1. Initialize the artifact-tool workspace.
2. Build title, event evidence, native charts, valuation table, conclusion, and source note.
3. Use KaiTi for Chinese-facing text and Arial for numerical/chart labels.
4. Add a `[Sources]` block in speaker notes.

### Task 3: Render and verify

**Files:**
- Create: `output/ftse_cac_dax_programmatic_poc_20260811/slide_04_programmatic.png`
- Create: `output/ftse_cac_dax_programmatic_poc_20260811/slide_04_programmatic.layout.json`

**Steps:**
1. Render the slide and inspect it at full size.
2. Run overflow and presentation QA.
3. Fix clipping, wrapping, overlaps, or chart/table mismatches before delivery.

