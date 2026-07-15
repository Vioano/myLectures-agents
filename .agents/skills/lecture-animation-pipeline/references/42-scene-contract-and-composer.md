# Scene Contract And Python Composer

Use this reference when a Manim shot is dense enough that one large `Scene`
would hide stage ownership, object identity, cleanup, and review evidence in
ad hoc code. The goal is not to build a new platform. The goal is to move the
existing production rules into a small, hard scene-local contract.

## Purpose

For formula-dense or stage-dense Manim scenes, write a scene-local
`contract.yaml` before final animation code. The contract declares the local
stage source of truth: which mathematical objects exist, which zones they own,
which beats enter, transform, or clear them, and which frames must be audited.

`timeline.json` remains the episode/audio/segment contract. `contract.yaml` is
the internal stage contract for one large Manim scene.

## When Required

Use the scene contract package when a shot has any of these:

- more than one layout mode;
- a live graph, coordinate plane, or diagram plus a formula board;
- repeated reuse of one formula lane, side board, or diagram pocket;
- more than three major mathematical objects;
- prior human or agent feedback about stage management, overlap, stale
  objects, unclear visual causality, or external-worker composition drift.

Small one-beat scenes may still use a single scene file when the stage
ownership is obvious and the normal stage-direction rules are enough.

## Scene Package Layout

Preferred layout for componentized Manim scenes:

```text
videos/NNNN-slug/src/scenes/<scene_slug>/
  contract.yaml        tracked local stage contract
  drivers.py           mathematical state and shared parameters
  objects.py           Mobject factories and registration only
  layout.py            named zones, slots, fitting helpers, protected regions
  beats.py             enter / transform / exit animation units
  composer.py          thin Manim Scene entrypoint and beat scheduler
  audit.py             adapter from contract data to layout_check inputs
  README.stage.md      optional tracked notes
```

The Manim render command should point to `composer.py`.

## Ownership Rules

- `contract.yaml` owns scene-local stage truth: object ids, zone ownership,
  beat timing, clear intervals, transform identity, audit frames, and any
  scene-local visual constraints that must be checked before render acceptance.
- `drivers.py` owns mathematical state, shared parameters, sampled data,
  formulas generated from math, and display-optimization notes.
- `objects.py` only creates and registers Mobjects. It does not schedule time.
- `layout.py` owns named zones, slots, reserved regions, and fitting helpers.
- `beats.py` owns enter, transform, focus, and exit animation units.
- `composer.py` loads the contract and schedules beats. It should stay thin.
- `audit.py` converts contract data into layout checks, protected-region
  checks, debug overlays, and QC anchor choices.

## Hard Rules

- `objects.py` must not call `self.play`, `self.wait`, `Scene.add`, or
  `Scene.remove`.
- `composer.py` should not contain raw coordinate guessing. Persistent
  placement belongs in `contract.yaml` and `layout.py`.
- Every major Mobject must have an `object_id` from `contract.yaml`.
- Every beat declares `local_time`, `owns_zones`, and
  `clear_before`/`clear_after`.
- Reusing a zone requires a clear interval or a declared `transform.identity`
  reason explaining why the new object preserves identity with the old one.
- Frames, chips, underlines, connectors, and classic-diagram conventions are
  not free decoration. Use optional contract fields such as `presentation`,
  `connectors`, `visual_reference`, and `overlap_policy` when a scene has
  repeated formula chips, long arrows, canonical diagrams, or shared slots.
- Formula-dense, diagram-dense, and previously human-rejected scenes must
  include a `review_policy.mode: reverse_burden` section with candidate red
  flags before final animation code. Missing red-flag policy is a design-stage
  failure, not a reviewer preference.
- Formula-dense, diagram-dense, and previously human-rejected scenes must also
  include `motion_ledger` and `authoring_preflight` sections. The motion ledger
  maps every key spoken anchor to the mathematical object, shared driver,
  visible change, and QC frame that will prove it. The authoring preflight
  lists the human-review or accepted-agent issue files read before coding and
  the concrete design response for each applicable `pattern_key`.
- The same `review_policy` must include
  `requires_ranked_aesthetic_sweep: true`,
  `minimum_ranked_aesthetic_flags`, and a closed
  `ranked_aesthetic_flags` list. These ranked entries name the first, second,
  and third ugliest/noisiest/least-clear visual candidates and force each to be
  fixed or pardoned with novice-viewer evidence before pass.
- Protected regions must be listed in the contract and included in the audit.
- Updater and `always_redraw` objects need an explicit cleanup owner.
- A browser or HTML preview may read or edit the contract, but acceptance comes
  from Manim render, layout audit, review MP4, QC frames, and tracked issues.

## Validation Loop

Before final animation polish:

1. Write `contract.yaml`.
2. Run `tools/validate_scene_contract.py`.
3. For dense or human-rejected work, run
   `tools/animation_preflight_gate.py` for the exact scene slug. After a human
   rejection, use `--risk-tier human-rejected
   --require-component-package --require-per-scene-review`. Do not code around
   a failed preflight.
4. Render a layout skeleton or low-quality smoke render showing zones,
   placeholders, protected regions, beat ids, and audit-frame times.
5. Implement drivers, objects, layout helpers, beats, and the thin composer.
6. Run layout audit and extract QC frames from the review MP4 before handoff.

The first validator is structural only. It does not judge aesthetics, Manim
bounding boxes, math correctness, or novice-viewer clarity. Those remain
covered by `layout_check.py`, strict review, and human review.

When a human review finds a repeated production failure, prefer adding a small
contract-level assertion over relying on prompt wording. Examples:

- `presentation.uses_frame: true` requires a `frame_role` such as
  `conclusion`, `group_panel`, `contrast_pair`, `derivation_container`, or
  `warning`.
- `connectors.forbid_background_baseline: true` documents that arrows must be
  edge-to-edge and no decorative through-line is allowed.
- `visual_reference.classic_source` records the textbook convention for
  canonical diagrams such as punctured contours around singularities.
- `overlap_policy.max_unrelated_overlap_seconds` documents the longest allowed
  shared-slot overlap for unrelated objects.
- `review_policy.candidate_flags` records likely rule violations, their
  status, evidence, and repair or pardon decision before a scene can be passed.
- `review_policy.ranked_aesthetic_flags` records the mandatory ranked
  aesthetic/noise sweep. This prevents a technically correct but ugly or
  visually noisy render from passing because it did not match an existing
  named failure.
- `visual_strategy.requires_non_formula_visual: true` prevents a scene from
  becoming only symbolic algebra when the narration promises visual intuition.
- `formula_persistence.min_hold_seconds` documents how long a derivation must
  remain visible after it lands.
- Contract version 4 adds a derivation-memory contract for formula-dense
  scenes: `formula_persistence.derivation_memory_required`,
  `persistent_formula_ids`, and `comparison_window`. When usable canvas space
  remains, the animator must add later steps progressively instead of replacing
  the only formula slot and erasing the viewer's comparison memory.
- Contract version 4 also requires `audit.atomic_formula_elements` and
  `audit.formula_internal_overlap_check_required: true`. Every major formula or
  value row that can coexist must be registered as a separate temporal layout
  element. Wrapping several formulas in one `VGroup` is not collision evidence.
- Contract version 4 requires
  `visual_strategy.novice_comprehension_checkpoints`. Each checkpoint names a
  question a first-time viewer should be able to answer from the visible
  objects, the visible answer, and the QC frame that proves it.
- `presentation.math_renderer_required: true` forbids plain text fallback for
  mathematical tokens with subscripts, superscripts, hats, Greek letters, or
  angle brackets.
- `motion_ledger` prevents PPT-like narration by requiring a spoken beat to
  name a mathematical object, a driver, a visible change, and a QC frame.
- `authoring_preflight` prevents review-only learning by proving that the
  animator read and consumed user feedback before stage/code work began.

## Worker Boundaries

Low-cost or external agents may receive narrow tasks for one driver, one object
factory, one beat range, one validator failure, or one issue JSON repair. They
must not decide full scene composition, rewrite visual direction, or bypass the
contract. The coordinator owns contract acceptance, render acceptance, audit
acceptance, and merge decisions.
