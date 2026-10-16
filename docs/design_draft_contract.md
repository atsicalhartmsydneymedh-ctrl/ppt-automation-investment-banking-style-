# Page Visual Design Contract v1.0

This contract fixes the required form of every page-level visual design draft. A design draft is a production specification, not a style summary.

## Required sections

Every approved draft must contain all of the following headings:

1. `Page conclusion` — the single conclusion the page must prove.
2. `Semantic relationship` — comparison, causality, sequence, hierarchy, distribution, scenario decision, or another explicit relationship.
3. `Visual argument` — how the visual form proves the conclusion; identify the dominant argument, the matched excellent-PPT mechanism, its fit/reject conditions, slot capacity, source example, and the linked evidence forms that make up the argument.
4. `Canvas` — exact aspect ratio and dimensions.
5. `Regions` — exact coordinates or sufficiently precise proportional geometry for every major region.
6. `Evidence mapping` — every approved supporting point, quantitative callout, and assigned source block mapped to a region or evidence role; a source ID alone does not count as visual representation.
7. `Visual encoding` — chart or diagram grammar, shared scales, axes, units, series colors, labels, annotations, and approximation rules.
8. `Hierarchy and reading path` — primary, secondary, and tertiary visual anchors plus the intended reading sequence.
9. `Typography` — fixed fonts and sizes. Chinese uses KaiTi; English, numbers, and punctuation use Arial.
10. `Style` — palette, line, fill, whitespace, and page-chrome rules.
11. `Anti-template constraints` — page-specific prohibitions that prevent card-grid, SmartArt, or repeated-container fallback.
12. `Approval checklist` — coverage, semantic accuracy, drawable evidence, hierarchy, variety, density, and canvas checks.

The draft must describe the actual page. Statements such as “high density”, “consulting style”, “use cards”, or “reduce whitespace” do not count as a visual argument or visual encoding.

## Immutable design core

After a design draft is approved, these sections form the immutable design core:

- Page conclusion
- Semantic relationship
- Visual argument
- Evidence mapping
- Visual encoding
- Hierarchy and reading path
- Anti-template constraints

They may change only when the user explicitly asks to redesign the page or the evidence is found to be wrong. A request to improve density, alignment, spacing, typography, polish, or layout does not authorize rewriting the design core.

## Layout optimization patch

Layout optimization is an additive patch against an approved design draft. It may change only:

- region sizes and spacing;
- alignment and shared baselines;
- whitespace allocation;
- label placement and annotation proximity;
- typography within the fixed readable size hierarchy;
- line weight, restrained fills, and local emphasis;
- removal of redundant containers or repeated prose.

It must not:

- replace the primary visual;
- change the semantic relationship;
- convert charts or diagrams into generic cards or tables;
- delete axes, units, shared scales, annotations, or evidence links;
- promote secondary modules to equal visual weight;
- overwrite the full design draft with a shorter style summary.

Every patch must record:

```text
LAYOUT PATCH
Base draft: <path and version>
Goal: <specific layout problem>
Locked: conclusion; semantic relationship; primary visual; evidence mapping; visual encoding; hierarchy
Changes:
- before -> after -> reason
Unchanged core confirmation:
- ...
Regression checks:
- primary visual retained: PASS/FAIL
- evidence encoding retained: PASS/FAIL
- hierarchy retained or strengthened: PASS/FAIL
- no new generic container grammar: PASS/FAIL
```

After applying the patch, export a complete merged design draft containing all twelve required sections. Image generation may use only the merged draft, never the patch alone.

## High-density rule

“High density” is a layout-quality objective, not a new design mode. If the first result is sparse, retain the approved design core and improve comparison density through tighter geometry, more direct labels, better use of shared axes, removal of redundant prose, stronger evidence-to-claim proximity, and additional linked evidence forms when the approved evidence load requires them.

The high-density revision fails if it is shorter than the base design because required design detail was removed, or if it replaces visual encoding with a content checklist.
