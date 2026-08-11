# Composition Decision Layer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a backwards-compatible page-level composition decision layer that selects the minimum necessary visual intensity before planning a slide.

**Architecture:** Introduce a small deterministic router used by `slide_planner`. It classifies the existing segment metadata into communication objective, information density, design intensity, visual strategy, archetype, spatial narrative, and asset strategy; the planner persists those fields and includes them in its Markdown and image-generation prompt.

**Tech Stack:** Python 3.12, standard library, existing JSON/Markdown artifacts.

---

### Task 1: Preserve a recoverable baseline

**Files:**
- Create: `backups/workflow_before_composition_decision_layer_20260811.zip`

**Step 1: Archive the current source, configuration, documentation, and dependency manifest.**

Run: `Compress-Archive -Path src,config,docs,README.md,requirements.txt -DestinationPath backups/workflow_before_composition_decision_layer_20260811.zip`

**Step 2: Verify the archive contains the baseline planner.**

Run: `Expand-Archive -LiteralPath backups/workflow_before_composition_decision_layer_20260811.zip -DestinationPath <temporary-directory>; Test-Path <temporary-directory>/src/slide_planner.py`

### Task 2: Add deterministic composition routing

**Files:**
- Create: `src/composition_router.py`
- Test: `tests/test_composition_router.py`

**Step 1: Write tests for utility, analytical, and narrative routing.**

**Step 2: Implement the smallest rule table that produces a complete decision contract.**

**Step 3: Run `python -m unittest discover -s tests -v`.**

### Task 3: Persist decisions in slide plans and prompts

**Files:**
- Modify: `src/slide_planner.py`
- Test: `tests/test_slide_planner.py`

**Step 1: Write a planner test asserting decision fields are exported and high-intensity prompts contain a visual proposition.**

**Step 2: Route each segment before selecting layout, build the layout from the decision, and render the decision fields in Markdown/prompt output.**

**Step 3: Run all unit tests.**

### Task 4: Document the operational workflow

**Files:**
- Modify: `README.md`
- Modify: `config/defaults.json`

**Step 1: Document the decision gate and artifact fields.**

**Step 2: Add an opt-out configuration switch that restores legacy layout routing.**

**Step 3: Run prompt-only smoke test and inspect generated slide plans.**

