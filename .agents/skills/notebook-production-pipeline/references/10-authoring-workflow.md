# Authoring Workflow

Use this file when creating or revising a notebook.

## Required Inputs

Before writing cells, identify:

- episode id and slug;
- source video script/storyboard or final episode summary;
- target student after watching the video;
- main learning objective;
- main student ability, written as "Student can ...";
- prerequisite assumptions;
- formulas or constructions that need hands-on reinforcement;
- problem actions that belong in the notebook rather than the video;
- exam-style abilities to train;
- concept diagnoses and common wrong answers to expose;
- pattern cards, if the episode contains a reusable mother structure;
- interaction budget.

## Notebook Plan

Create or update a concise plan before implementation. It may live in the
notebook README, a review handoff, or a local planning note while the workflow
is still evolving.

The plan should include:

- main ability;
- core course object or reusable pattern;
- sequence of sections;
- each section's exercise layer;
- each cell's modality: Markdown, hint, answer check, widget, plot, or object
  lab;
- each exercise's purpose and feedback route;
- each widget's reason to exist, if any;
- what students are expected to explain, decide, compute, diagnose, transfer,
  change, observe, or prove;
- validation command;
- known open questions for user direction.

For new production candidates or rejected-direction repairs, write the fuller
contract in `review/notebook-contract.md` using
`42-notebook-contract-and-composer.md`.

## Authoring Preflight

Before writing notebook code, read:

- `review/human-feedback/`;
- `review/agent-feedback/`;
- `review/issues/*.json` records with `source: human_review`,
  `source: accepted_agent_feedback`, or `must_check_in_future: true`;
- this skill's `50-known-failures-and-fixes.md`.

Write a short checklist naming applicable `pattern_key` records and how the new
notebook will avoid them. If no review directory exists yet, state that no
episode-local feedback exists and use the skill-level known failures.

## Section Structure

Prefer a narrow problem path:

1. ability target;
2. short concept recall or diagnostic;
3. concept discrimination;
4. standard calculation;
5. feedback or error diagnosis;
6. variant transfer;
7. optional high-value interaction or extension;
8. compact exam summary.

Avoid many equal-weight demonstrations. A student should know which cells are
the main path and which are optional.

## Code Cell Rules

- Keep setup, helpers, widgets, and exercises separated.
- Prefer deterministic functions over hidden notebook state.
- Use small named helper functions when several cells share a mathematical
  object.
- Keep long symbolic derivations or numerical experiments behind a clear
  section heading.
- Do not save huge outputs in committed production notebooks unless needed for
  static viewing.

## Execution

Execute from the notebook repository:

```bash
uv run jupyter nbconvert --execute --to notebook --output /tmp/<name>.ipynb <path/to/notebook.ipynb>
```

Then audit:

```bash
uv run python /Volumes/bocchi/myLectures/.agents/skills/notebook-production-pipeline/scripts/audit_notebook.py /tmp/<name>.ipynb
```
