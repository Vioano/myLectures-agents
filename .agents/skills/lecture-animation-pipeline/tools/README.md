# Layout / Collision-Check Tools

Reusable helpers for catching element overlap before rendering a full scene,
plus the strict review gate used before user handoff.

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
