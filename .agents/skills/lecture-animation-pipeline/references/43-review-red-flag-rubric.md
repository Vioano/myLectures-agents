# Review Red Flag Rubric

This reference turns strict review into a reverse-burden process. The default
verdict is `revise`. A scene earns `pass` only after the reviewer first lists
candidate violations and then explicitly clears, fixes, or pardons every one.

## Core Rule

Do not review by asking "is there a known blocker?" Review by asking "which
rules does this almost violate?"

Every review must produce a red-flag ledger before the verdict:

- `candidate_flags`: suspected violations, including small ugliness and near
  misses;
- `status`: `open`, `fixed`, `pardoned`, or `not_applicable`;
- `pardon_reason`: required for every `pardoned` item;
- `evidence`: timestamp, QC frame, contract field, code path, or screenshot;
- `repair_target`: exact file or scene element when not pardoned.

Acceptance rule:

- `open` candidate count must be `0`.
- Every `pardoned` candidate must explain why the apparent violation is safe
  for a novice viewer and not merely convenient for the animator.
- A review with no candidate flags is invalid for formula-dense, diagram-dense,
  or previously human-rejected work. It means the reviewer did not look hard
  enough.
- A review must also produce a ranked aesthetic/noise ledger with at least
  three entries: `第一丑`, `第二丑`, and `第三丑`, or equivalent ranks for the
  ugliest, noisiest, or least visually guided parts of the render. These
  ranked entries are required even when ordinary candidate flags already look
  closed. A missing ranked aesthetic ledger is a review-gate failure.

## Minimum Candidate Sweep

For each scene, the reviewer must actively try to find issues in these groups:

1. **Meaning and ownership**
   - unowned dashed lines, connectors, arrows, baselines, braces, fills, rings,
     or panels;
   - connectors without named endpoints and a stated relation;
   - labels or markers whose mathematical object is not visually identifiable.
2. **Formula typography**
   - text fallback such as `c_1` instead of a rendered subscript;
   - formulas too small, clipped, or touching frames;
   - missing labels for major displayed formulas, especially transform versus
     inverse transform.
3. **Creator-intent text**
   - captions that expose the production critique instead of labeling a
     mathematical object;
   - screen text like "can compute, but..." when the visual should instead
     stage the mathematical contrast.
4. **Formula persistence and derivation continuity**
   - formulas disappearing while unused space remains;
   - proof steps flashing faster than a viewer can read;
   - a derived formula appearing without its predecessor still visible or
     transformed into it.
5. **Frames, chips, and panels**
   - frames around ordinary terms or every short formula;
   - frames that compress one-line formulas and reduce legibility;
   - panels whose hierarchy role is not declared in `contract.yaml`.
6. **Fills and area-like shapes**
   - any bow-shaped fill, translucent region, curve-to-baseline patch, or
     filled arrow/arc that is not the exact named quantity;
   - Manim opacity or stroke/fill side effects that make a curve look like an
     area.
7. **Visualization adequacy**
   - a scene that is only algebra while the narration claims intuition,
     projection, orthogonality, or coefficient extraction;
   - missing diagram, sample, vector, basis, component, cancellation, or
     reconstruction visual for a novice viewer.
8. **Timeline beat alignment**
   - each spoken operation must have a visible cause, change, or consequence
     at the same beat;
   - one broad static formula wall cannot cover multiple spoken ideas.
9. **Aesthetic noise and visual guidance**
   - repeated low-opacity grids, axes, guide lines, frames, or panel edges that
     collectively dominate the mathematical object;
   - a 3D or layered object whose depth is "proved" by drawing too many helper
     lines instead of using curves, labels, and restrained axes;
   - the viewer's first eye landing on clutter, boxes, or guide scaffolding
     instead of the current mathematical object;
   - any held frame that is technically correct but would be called ugly,
     amateurish, noisy, cramped, or visually indecisive.

## Negative Examples For Reviewers

These are regression examples. If a scene resembles one of them, the reviewer
must start from `revise` and only clear it with written evidence.

- Dotted lines run from a function graph toward coefficient chips. The lines
  cross each other, have no named endpoint relation, and do not transform into
  coordinates. Reject as `unowned_connector_spaghetti`.
- Coefficient chips show `c_1`, `c_2` as plain text with underscores instead
  of `c_1`, `c_2` rendered through LaTeX. Reject as `latex_fallback_math_text`.
- A formula table is titled only as a table, and the screen adds a caption like
  "can compute, but like a pile of integrals". Reject as
  `externalized_creator_critique_caption`. The formulas themselves should be
  labeled by mathematical role.
- Fourier series, Fourier transform, and inverse transform formulas appear
  together without labels identifying which is which. Reject as
  `unlabeled_major_formula_stack`.
- A finite-vector projection derivation appears, then vanishes immediately
  while the right side has empty room. Reject as
  `premature_derivation_clear_with_space_available`.
- A curve, arc, or arrow segment visually becomes a gray bow-shaped filled
  patch. Reject as `unowned_bow_shape_fill`.
- A term row wraps every short term in boxes. The boxes become stronger than
  the algebra and make one-line reading worse. Reject as
  `overboxed_formula_row_blocks_reading`.
- A whole scene is only symbolic manipulation while the lesson is supposed to
  teach a projection, basis expansion, orthogonality, or coefficient extraction
  visually. Reject as `formula_only_scene_without_visual_causality`.
- A stacked 3D basis or mode-decomposition object draws grid lines on every
  layer. The repeated guides dominate the curves and make the layer object
  noisy. Reject as `layer_grid_clutter_in_3d_basis_object`; for this class of
  object, default to no grid and at most restrained axes unless the grid is the
  exact mathematical object being taught.

## Design-Stage Gate

Before coding a scene, the author must write a design-stage red-flag ledger in
the stage direction or `contract.yaml`:

- expected red flags for this scene;
- concrete design choices that avoid each one;
- any intentionally pardoned risk and why it will still be clear to a novice;
- required QC frames that prove the avoidance.

If this design-stage ledger is missing, do not start Manim code. If a subagent
is asked to design or review a scene, include the negative examples above in
the prompt and require a red-flag ledger in its report.

## Contract Fields

Use these fields in `contract.yaml` for dense scenes:

```yaml
review_policy:
  mode: reverse_burden
  minimum_candidate_flags: 6
  minimum_ranked_aesthetic_flags: 3
  requires_ranked_aesthetic_sweep: true
  pass_requires_all_flags_closed: true
  ranked_aesthetic_flags:
    - rank: 1
      id: first_ugliest_or_noisiest_candidate
      standard_key: visual_hierarchy_failure
      status: open
      evidence: "timestamp/QC frame/code path"
      repair_target: ["objects.or.beats"]
      authoring_response: "fix or pardon with novice-viewer evidence"
    - rank: 2
      id: second_ugliest_or_noisiest_candidate
      standard_key: space_utilization_failure
      status: open
      evidence: "timestamp/QC frame/code path"
      repair_target: ["objects.or.beats"]
      authoring_response: "fix or pardon with novice-viewer evidence"
    - rank: 3
      id: third_ugliest_or_noisiest_candidate
      standard_key: ambiguous_visual_object
      status: open
      evidence: "timestamp/QC frame/code path"
      repair_target: ["objects.or.beats"]
      authoring_response: "fix or pardon with novice-viewer evidence"
  candidate_flags:
    - id: unowned_connector_spaghetti
      standard_key: ambiguous_visual_object
      status: open
      evidence: "dashed links from graph to coordinate chips"
      repair_target: ["objects.coordinate_slots", "beats.b02_coordinate_slots"]
      authoring_response: "replace with anchored one-to-one sample mapping or remove"
```

`open` means the scene cannot pass. `fixed` means the render and QC evidence
prove the issue was repaired. `pardoned` means the apparent violation remains
but has a precise, viewer-safe reason. `not_applicable` means the scene does
not contain that object class.

## Reviewer Prompt Addendum

Append this to subagent or independent-review prompts:

```text
Start from revise. Build a red-flag ledger before giving any verdict. You must
try to find problems in connector ownership, formula typography, creator-intent
text, formula persistence, frame overuse, fills/area-like shapes, visualization
adequacy, and beat alignment. Include at least six candidate flags for any
formula-dense or diagram-dense scene, even if you later pardon them. A pass
with zero candidate flags is invalid. Repeated human-found patterns are not
style preferences; one unpardoned repeat means revise.

In addition, list at least three ranked aesthetic/noise candidates before the
verdict: first ugliest/noisiest/least-clear, second, and third. Try hard to
find visual clutter even if the math is correct: excess grids, axes, helper
lines, boxes, panel borders, cramped labels, weak eye guidance, or visually
amateurish held frames. Each ranked candidate must be fixed, pardoned with a
novice-viewer reason, or marked not_applicable. A missing ranked list is an
invalid review.
```
