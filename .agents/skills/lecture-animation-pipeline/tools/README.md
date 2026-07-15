# Layout / Collision-Check Tools

Reusable helpers for catching element overlap before rendering a full scene,
plus the strict review gate used before user handoff.

## `animation_preflight_gate.py` — Design-stage source/control gate

Run this before final Manim code or review for formula-dense, diagram-dense, or
previously human-rejected scenes. It rejects the failure class where a scene
renders but still uses a monolithic source file, stale combined review paths,
no component package, no motion ledger, or no authoring preflight from user
feedback.

Required command shape after a human rejection:

```bash
python3 .agents/skills/lecture-animation-pipeline/tools/animation_preflight_gate.py \
  --repo-root /Volumes/bocchi/myLectures \
  --episode videos/NNNN-slug \
  --scene-slug s001_example \
  --risk-tier human-rejected \
  --require-component-package \
  --require-per-scene-review
```

The gate also runs `validate_scene_contract.py`, checks the scene-local package
contains `contract.yaml`, `drivers.py`, `objects.py`, `layout.py`, `beats.py`,
`composer.py`, and `audit.py`, verifies the composer has exactly one Manim
Scene class, and makes sure `objects.py` does not hide time scheduling.

## `review_gate.py` — Suspicion-first review state machine

Use this CLI for every animation review loop. It stores compact JSON state
under the episode's `review/gate/<scene_slug>/<session_id>/` directory by
default and rejects incomplete review or fix submissions.

Create a session:

```bash
python3 .agents/skills/lecture-animation-pipeline/tools/review_gate.py \
  --repo-root /Volumes/bocchi/myLectures \
  init \
  --episode videos/NNNN-slug \
  --scene-slug s001_example \
  --review-id s001_example_review_v01_720p30 \
  --owner codex \
  --reviewer subagent-review \
  --risk-tier normal
```

Reviewer workflow:

```bash
python3 .agents/skills/lecture-animation-pipeline/tools/review_gate.py \
  checklist --session videos/NNNN-slug/review/gate/s001_example/<session_id>/state.json

python3 .agents/skills/lecture-animation-pipeline/tools/review_gate.py \
  confirm-read --session videos/NNNN-slug/review/gate/s001_example/<session_id>/state.json \
  --reviewer subagent-review

python3 .agents/skills/lecture-animation-pipeline/tools/review_gate.py \
  template-review --session videos/NNNN-slug/review/gate/s001_example/<session_id>/state.json \
  > /tmp/review-submission.json

python3 .agents/skills/lecture-animation-pipeline/tools/review_gate.py \
  submit-review --session videos/NNNN-slug/review/gate/s001_example/<session_id>/state.json \
  --input /tmp/review-submission.json
```

Animation-owner repair workflow after an accepted `revise` or `blocked`
review:

```bash
python3 .agents/skills/lecture-animation-pipeline/tools/review_gate.py \
  template-fix --session videos/NNNN-slug/review/gate/s001_example/<session_id>/state.json \
  > /tmp/fix-submission.json

python3 .agents/skills/lecture-animation-pipeline/tools/review_gate.py \
  submit-fix --session videos/NNNN-slug/review/gate/s001_example/<session_id>/state.json \
  --input /tmp/fix-submission.json
```

The final machine gate before user handoff is:

```bash
python3 .agents/skills/lecture-animation-pipeline/tools/review_gate.py \
  status --session videos/NNNN-slug/review/gate/s001_example/<session_id>/state.json \
  --require-pass
```

Inspect the persisted review-behavior ledger:

```bash
python3 .agents/skills/lecture-animation-pipeline/tools/review_gate.py \
  metrics --session videos/NNNN-slug/review/gate/s001_example/<session_id>/state.json
```

When a session predates the metrics ledger, backfill summary records from the
already accepted review/fix payloads:

```bash
python3 .agents/skills/lecture-animation-pipeline/tools/review_gate.py \
  backfill-metrics --session videos/NNNN-slug/review/gate/s001_example/<session_id>/state.json
```

Every accepted or rejected review/fix submission appends one JSON line to:

```text
videos/NNNN-slug/review/gate/<scene_slug>/<session_id>/review_metrics.jsonl
videos/NNNN-slug/review/gate/review_metrics.jsonl
```

The ledger records candidate count, ranked-aesthetic count, open issue count,
fix/review round history, pardon count, pardon rate, whether the submission was
accepted, and rejection reasons. This file is the durable source for detecting
reviewer behavior drift; do not rely on chat memory for those statistics.

Submission success requires:

- exact read confirmations for every required document and SHA-256 printed by
  `checklist`;
- `inspection` ticks for review MP4, QC frames, source code, timeline
  alignment, regression records, authoring preflight, and layout audit when
  applicable;
- one ledger entry for each abstract standard in
  `references/50-known-failures-and-fixes.md`;
- coverage for all relevant `review/issues/*.json` regression records present
  at session creation;
- enough candidate red flags and ranked aesthetic/visual-guidance objections
  for the selected risk tier;
- all open findings represented as issue JSON under `review/issues/`;
- a fix submission that covers every open issue before rereview.
- pardon counts and pardon rates under the selected risk-tier limits;
- no pardons for human-review regressions, accepted-agent regressions, or
  no-pardon classes such as subtitle safe-zone violations, formula-in-subtitle
  lane, duplicate semantic objects, lingering objects, slow fade ghosts,
  ambiguous unowned fills, stray debug rectangles, PPT-like formula-only
  derivations, and unvisualized Riemann sums;
- the selected risk tier's minimum fix/rereview loop count before a pass.

Risk tiers are intentionally strict:

- `low`: small repair, at least 6 candidate flags and 3 ranked aesthetic
  objections.
- `normal`: ordinary scene, at least 8 candidate flags and 4 ranked aesthetic
  objections.
- `dense`: formula/stage dense scene, at least 12 candidate flags and 5 ranked
  aesthetic objections.
- `human-rejected`: after user rejection, at least 18 candidate flags and 7
  ranked aesthetic objections.
- `repeat-rejected`: repeated failure pattern, at least 24 candidate flags and
  10 ranked aesthetic objections.

Additional pass limits:

- `low`: at most 4 pardons, pardon rate at most 25%, no minimum fix round.
- `normal`: at most 3 pardons, pardon rate at most 20%, no minimum fix round.
- `dense`: at most 2 pardons, pardon rate at most 12%, at least 1 fix/rereview
  loop before pass.
- `human-rejected`: at most 1 pardon, pardon rate at most 5%, at least 2
  fix/rereview loops before pass.
- `repeat-rejected`: no pardons, at least 3 fix/rereview loops before pass.

Do not add a separate policy YAML until the hardcoded thresholds and required
documents become hard to maintain. For now, taste and review standards live in
the skill Markdown files plus episode feedback/issues; the CLI enforces that
reviewers read and operationalize those files.

## `layout_check.py` — Generic collision-check library

Drop-in module. Import into any Manim scene and pass a dict of elements
plus their `(t_enter, t_exit)` ranges. Reports:

- **OVERLAP** — bounding boxes of two simultaneously-visible elements
  intersect in both horizontal and vertical extents.
- **CLOSE** — both horizontal and vertical gaps are below the configured
  thresholds (default `0.3` each, sum `< 0.4`).

Example use inside a scene:

```python
from layout_check import check_layout

elements = {"f_label": f_label, "R = 1": r_label, ...}
time_ranges = {"f_label": (5.0, 99), "R = 1": (25.5, 99), ...}
issues = check_layout(elements, time_ranges, times=[22, 26, 29, 32, 35, 38])
assert not issues, "Layout has overlaps"
```

The checker reads bounding boxes from the mobject's current position, so
it works after any `.move_to()`, `.next_to()`, `.to_corner()`, `.scale()`,
or updater-driven change.

Also exports `draw_bbox_overlay(scene, elements, colors)` for rendering
a visual debug frame with a bounding box and name tag per element.

## `example_layout_debug_scene.py` — Reference full-scene demo

A complete `LayoutDebug(Scene)` built for the S005–S007 Taylor-expansion
merged scene. Shows how to:

1. Register every graph element, axis, label, and narrative text.
2. Assign `(t_enter, t_exit)` ranges to each.
3. Render the full debug frame with `SurroundingRectangle` + name tags.
4. Run `check_layout` at a list of peak times and print results.

Copy this as a starting template for a new scene, replace the element
dictionary, and keep the same structure.

## When to run

- After placing all narrative text but before the final render.
- After repositioning any element in response to a QC-frame complaint.
- Whenever a merged scene packs more than 4 narrative elements at once.

A clean `check_layout` pass does NOT guarantee the frame looks good
(typography, palette, semantic color use, math-object alignment all
need separate QC), but it does catch the most common "two pieces of
text landed on top of each other" bugs.

## `validate_scene_contract.py` — Scene contract structural gate

Validates `contract.yaml` before a scene is treated as reviewable. The
validator checks ordinary scene structure and the reverse-burden review fields:

- `review_policy.mode: reverse_burden`
- enough `review_policy.candidate_flags`
- `review_policy.requires_ranked_aesthetic_sweep: true`
- at least three `review_policy.ranked_aesthetic_flags`, ranked as the
  ugliest/noisiest/least-clear visual candidates and each closed or pardoned
- no `open` candidate flags when `pass_requires_all_flags_closed` is true
- `visual_strategy` proving whether non-formula visuals are required
- `formula_persistence` for derivation hold/clear policy
- top-level `presentation` flags for math renderer and unowned fills

This script is intentionally stricter than the first layout smoke test. If it
fails after human feedback, treat the scene as design-stage `revise_required`,
not as a tooling nuisance.
