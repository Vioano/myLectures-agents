# Known Failures And Fixes

This file collects production lessons from myLectures episodes. Update it
whenever a new issue is found. Use it in two layers:

1. Abstract review standards: broad failure classes that let a reviewer reject
   new problems even when there is no exact prior screenshot.
2. Concrete regression cases: specific failure modes already seen in production
   and the accepted fixes.

## Abstract Review Standards

Every audit report should first check these standards, then cite concrete
failure cases below when they match. If a render violates an abstract standard
but no existing concrete case fits, create a new `pattern_key` issue instead of
passing it as "not covered by known failures."

### `stage_management_failure`: No Conscious Stage Dispatch

Failure class: mathematical objects, formula boards, labels, captions, and
transitions appear wherever there is leftover room. The canvas has no temporal
ownership plan, so objects collide, sit in corners, waste space, or force the
viewer to infer which region is active.

Reject when:

- a main function graph, coordinate plane, sampling construction, or proof is
  squeezed into a corner while large useful space is unused;
- a side board appears without the graph/diagram being moved, narrowed, or
  cleared to make room;
- old objects remain because no subshot owns the cleanup interval;
- named safe zones become a rigid grid that separates related objects or
  creates dead space.

Acceptable when:

- stage zones change over time according to the mathematics: a graph may shrink
  when a proof board enters, expand when motion needs immersion, or become an
  inset when formulas take over;
- a local annotation sits directly on a diagram because it labels that exact
  object and is bounded, readable, and temporary.

Concrete cases to consult: `Missing Stage Direction`, `Rigid Stage Zones`,
`Panel Over Active Function Graph`, `Detached Related Formula Groups`,
`Overbuilt Multi-View Shot`, `Aesthetically Ugly But Technically Correct`.

### `ambiguous_visual_object`: Unnamed Or Misleading Visual Element

Failure class: a line, fill, rectangle, star, underline, connector, frame,
transparent patch, or highlight appears without a named mathematical object or
visual-hierarchy role. Viewers may read it as an axis, boundary, area,
operator, warning, or data object even when that is not intended.

Reject when:

- a fill/area/strip appears near an integral but is not the exact named density;
- a red line, warning boundary, connector, or decorative stroke has no object
  identity;
- a star, underline, or highlight is near a formula but not attached to the
  exact token it modifies;
- a transparent panel covers an active object and makes it look like background
  texture instead of the current mathematical object.

Acceptable when:

- an on-diagram label, tangent, derivative marker, local linear approximation,
  normal vector, sample value, or callout is attached to the exact local object
  being taught;
- any overlay is small enough to preserve the object silhouette, has a clear
  anchor point, and clears when its local role ends;
- a zoom/inset is used for dense local annotations, with a visible relation to
  the original region.

Concrete cases to consult: `Meaningless Warning Line Or Boundary`,
`Ambiguous Integral Area Fill`, `Misplaced Symbol Highlight`, `Useless
Connectors`, `Ugly Pairing Connectors In Dot Products`, `Overdecorated Short
Formulas`, `Panel Over Active Function Graph`.

### `mathematical_identity_or_causality_failure`: Real Object Not Preserved

Failure class: the code or final frame may contain correct-looking formulas,
but the visible object identity or mathematical cause is missing. The viewer
does not see the real transformation, limiting process, or reason for a
correction.

Reject when:

- a transformed curve is not generated from the same mathematical driver;
- scalar multiplication, rotation, reflection, or conjugation is shown as a
  convenient curve swap or symbol edit;
- a finite-to-continuous idea skips the intermediate samples, components,
  products, sums, or density progression;
- the reason for a formula correction appears only as algebra, not as a visible
  cause.

Acceptable when:

- display scaling, local zoom, or simplified parameters are used, but the
  underlying identity and mapping are explicit and recorded;
- formulas support a visible construction rather than replacing it.

Concrete cases to consult: `Fake Scalar Multiplication Of A Function Graph`,
`Fake Rotation Or Dragged Vector`, `Sparse To Dense Sampling Jump`, `Inner
Product Integral Missing Sampling Causality`, `Complex Conjugate Reason Not
Visualized`, `Desynchronized Views`, `Decorative Media Pretending To Be Math`.

### `timeline_visual_alignment_failure`: Narration And Picture Are Not Beat-Aligned

Failure class: the total video duration matches the audio, but individual
spoken ideas do not have matching visual causes, changes, or consequences at
the same time.

Reject when:

- narration introduces an object or operation before it appears visually;
- a key "why" question is spoken while the screen is still showing the previous
  construction;
- several spoken concepts share one static broad visual phase;
- transitions happen too early or too late for the voice cue they support.

Concrete cases to consult: `Coarse Timeline Visual Alignment`, `Subagent
Review Assumes Expert Knowledge`, `Human Feedback Not Converted To Authoring
And Review Regression Tests`.

### `space_utilization_failure`: Inefficient Or Unbalanced Use Of The Frame

Failure class: the composition technically avoids overlap but wastes the frame,
over-compresses important objects, or lets secondary UI dominate the main
mathematical object.

Reject when:

- a graph remains too wide after a side operation board is introduced, causing
  crowding or overlap;
- a key object is too small or visually weak while empty regions remain;
- related formulas are far apart for no reason, forcing eye jumps;
- the scene feels like a small static cluster on a large board.

Acceptable when:

- empty space is intentionally used for pause, emphasis, or a coming object and
  the reason is clear in the stage direction;
- the graph is deliberately narrowed to reserve a clean formula lane.

Concrete cases to consult: `Panel Over Active Function Graph`, `Rigid Stage
Zones`, `Detached Related Formula Groups`, `Overbuilt Multi-View Shot`,
`Aesthetically Ugly But Technically Correct`.

### `visual_hierarchy_failure`: Decoration Replaces Hierarchy

Failure class: frames, underlines, colors, panels, and text styles do not tell
the viewer what is definition, active focus, warning, contrast, derivation, or
conclusion.

Reject when:

- every short formula gets a frame or underline;
- color is used for liveliness instead of semantic role;
- a panel changes meaning without clearing old content;
- screen text repeats narration instead of labeling mathematical objects.

Concrete cases to consult: `Overdecorated Short Formulas`, `Panel State
Collision`, `Palette Underuse Or Misuse`, `Text Or Formula Exceeds Its
Container`, `Misplaced Symbol Highlight`.

### `pedagogical_example_failure`: Example Does Not Reveal The Target Idea

Failure class: examples are mathematically valid but visually too flat,
symmetric, small, dense, sparse, or special to teach the claimed operation.

Reject when:

- functions chosen for a product/integral make the product look constant;
- a counterexample is too tiny, too visually ambiguous, or hidden by labels;
- sample density, oscillation, sign change, or variation is the lesson target
  but the example barely shows it.

Concrete cases to consult: `Weak Example Functions Hide Product Shape`,
`Taylor Partial Sum Too Low-Order`, `Sparse To Dense Sampling Jump`.

## Sibling Worktree Production Drift

Failure: a new lesson or agent task is initialized in a sibling directory such as `/Volumes/bocchi/myLectures-0002-hilbert-tts` instead of the canonical repository root. The new `videos/NNNN-slug/` directory is no longer next to earlier lessons, first-lesson artifacts are harder to reference, and Git status fragments across multiple worktrees.

Fix:

- Treat `/Volumes/bocchi/myLectures` as the only production workspace.
- Create or continue video projects only under `videos/NNNN-slug/`.
- Use Git branches for isolation; do not use external sibling worktrees as the default isolation mechanism.
- If an accidental sibling worktree exists, migrate its committed artifacts back into `/Volumes/bocchi/myLectures` using Git branch refs, verify the video directories are siblings, then remove the extra worktree.

## Output Path Drift

Failure: different agents render into root `media/`, video-local `media/`, ad-hoc `exports/manim_*`, random `draft/qc-*` folders, or unversioned review paths. Reviewers cannot tell which MP4 is current, QC frames no longer correspond to the reviewed clip, and final stitching has to rediscover render state from logs.

Fix:

- Follow `41-production-output-contract.md` for all new work.
- Use `--media_dir videos/NNNN-slug/exports/manim` for normal Manim renders.
- Put watchable review MP4s in `exports/reviews/<scene_slug>/<review_id>.mp4`.
- Put QC keyframes in `exports/qc/<qc_id>/` and make the `qc_id` match the reviewed version.
- Record raw Manim path, review path, QC path, render command, and mux command in `experiment-log.md`.
- Do not rename legacy outputs just for tidiness; apply the contract from the next render forward.

## Stale Timeline Review Contract

Failure: a segment or scene group has a current repaired review MP4, QC
directory, layout audit, or strict-review report in one part of `timeline.json`,
but another timeline field still points to an older rejected artifact. This can
happen when nested `visual.*` fields are updated while top-level segment fields
remain stale, or when a scene group is updated without synchronizing all member
segments.

Fix:

- Treat `timeline.json` review metadata as one contract, not a set of loose
  notes. All fields that identify the current review artifact must agree.
- Before handoff, group review, final stitching, or user review, run a
  consistency check comparing top-level segment fields with nested `visual.*`
  fields for `review_output`, `qc_output`, `layout_audit`, `review_status`, and
  `strict_review_report` when those fields exist.
- If a scene group points to a current review version, every segment in that
  group should point to the same current artifact family unless a documented
  exception says otherwise.
- Audit reports must reject a visually passing render when the timeline can
  still lead a reviewer or final stitch script to an older failed artifact.

## QC Frame Names Not Sortable Or Missing Opening Frames

Failure: QC frames are extracted with names such as `frame_t5p00s.png` or
`frame_t12p40s.png`, so lexicographic contact-sheet generation can place later
frames before earlier frames. Another form is omitting the opening frame for a
review clip, which prevents reviewers from checking the incoming transition and
initial stage ownership.

Fix:

- Use the canonical `41-production-output-contract.md` frame pattern:
  `frame_t000p00s.png`, `frame_t012p40s.png`, `frame_t101p00s.png`.
- Include opening, transition, dense-action, user-feedback fix, and final
  frames before rebuilding the contact sheet.
- Remove or replace noncanonical old `frame_t*.png` files in the QC directory
  so the contact sheet is generated only from the current ordered evidence.
- During group and final review, reject a QC package whose filenames cannot be
  sorted by time or whose frame set skips the clip's opening state.

## Root Stage Direction Sprawl

Failure: stage-direction notes are scattered as loose root files or mixed with formal storyboards. Agents cannot tell whether a note is formal vault storyboard, production storyboard, implementation choreography, or stale review scratch.

Fix:

- Keep formal scripts and storyboards in `vault/videos/NNNN-slug/`.
- Use production `videos/NNNN-slug/storyboard.md` only when it is a working animation plan derived from or pointing to the vault version.
- Put scene-specific choreography in `timeline.json`, `src/<scene_slug>.stage.md`, or a concise `STAGE_SCRIPT` in the Manim source.
- Do not create extra root-level stage-direction files unless the skill is updated to name them.

## Fake Rotation Or Dragged Vector

Failure: a vector was visually moved or transformed in a way that looked like translation or dragging, while narration claimed rotation.

Fix:

- Drive rotation by an angle tracker around the true center.
- For multiplication by `i`, rotate by `pi/2`.
- For multiplication by `-1`, rotate by `pi`.
- For multiplication by complex `w`, drive both angle change and scale change from `w`.
- Prefer parametric/updater-driven objects over endpoint-only transforms.

## Fake Scalar Multiplication Of A Function Graph

Failure: the narration claims a function is multiplied by a scalar, but the
render replaces the curve with a separate convenient curve or makes it look
translated. For `c=-1`, this is especially severe: the graph of `f` must become
the pointwise reflection of the same function across the x-axis.

Fix:

- Define one function driver `f(x)` and generate `c f(x)` from that driver.
- For `c=-1`, verify sample pairs `(x,f(x))` and `(x,-f(x))` are symmetric
  about the zero axis.
- When teaching the operation, show a few matched sample correspondences or a
  clean reflection motion so viewers can see identity preservation.
- Do not accept a final red curve merely because it lies below the axis; it
  must be the actual scalar multiple.

## Rotation Plus Scaling Not Both Visible

Failure: complex multiplication was described as rotation plus scaling, but the visual showed only one of them or did not make both measurable.

Fix:

- Choose an example `w` with both modulus not equal to 1 and argument not zero.
- Show original vector, rotated/scaled result, and optionally transformed grid.
- If using matrix form, show columns and orthogonality/equal-length structure.

## Formula Overlapping Coordinate System

Failure: large algebra formulas were placed over axes or coordinate diagrams.

Fix:

- Separate formula panels from diagram area.
- Fade out old coordinate objects before formula panels occupy the same region.
- Use bare formulas for local labels; reserve panels for structured derivations.

## Grid Origin Misalignment

Failure: a coordinate grid is drawn from arbitrary loop bounds, so the axes pass
between grid lines and the mathematical origin is not visibly a lattice point.
This makes the coordinate plane look decorative instead of mathematically
anchored.

Fix:

- Generate grid lines from integer multiples of the grid step around zero.
- Explicitly include `0` in both horizontal and vertical grid offsets.
- Place the axes on the `x=0` and `y=0` grid lines. It is acceptable for the
  axis stroke to cover the zero grid line; it is not acceptable for the axis to
  sit halfway between two grid lines.
- During QC, inspect a frame where the coordinate plane is fully visible and
  verify that the grid intersection coincides with the axis intersection.

## Angle Label Looks Wrong

Failure: angle arcs or labels were too large, too small, too dark, or did not correspond to the real angle.

Fix:

- Use the true angle parameter.
- For right angle, use a right-angle marker plus `90^\circ`.
- For infinitesimal angle, keep the true small angle and zoom near the vertex.
- Never draw floating local line segments as a replacement for the true angle.

## Quadrant Hopping Instead Of Local Focus

Failure: a crowded point, angle, or endpoint-label cluster is "fixed" only by moving the same geometry to another quadrant. The labels remain crowded because the full view is still carrying local-detail annotations that belong in a zoomed view.

Fix:

- Keep the global diagram quiet: show the true point, arc, vector, or focus marker, but remove local-detail labels from the full view.
- Add a local inset, camera zoom, or locally rescaled coordinate view generated from the same mathematical driver.
- Put endpoint labels, small-angle labels, tangent labels, and error-gap labels in the focused view where they have room.
- Clear local labels when the subshot changes role, such as moving from "identify the small angle" to "show the tangent direction."
- During QC, inspect both the global frame and the focused frame: the global frame should orient the viewer, while the focused frame should carry the readable detail.

## Detached Local Inset

Failure: a region is circled in the main diagram, then a separate inset appears elsewhere with a different orientation or locally reinterpreted axes. Even if both are computed from the same parameters, viewers cannot tell that the inset is the circled region rather than a new diagram.

Fix:

- Prefer a real camera zoom or magnifier that enlarges the actual circled region in place.
- If using a separate inset, animate a clear transfer: the circled patch moves or expands into the inset, or a connector arrow links exact anchor points.
- Preserve orientation unless a rotation of the local coordinates is explicitly shown and justified.
- Preserve semantic colors and vector directions. A tangent that points down-left in the main diagram should not silently become horizontal in the inset.
- During QC, ask whether a viewer could identify the inset source without narration. If not, the view transition is incomplete.

## Arc Becomes Filled Wedge Or Band

Failure: a swept arc looked like a filled bow-shaped area rather than a line.

Fix:

- Use arc stroke only; do not fill sectors unless area is the intended object.
- Avoid overlapping dense curves that visually create a filled region.
- Extract keyframes near the arc to check it remains a line.

## Useless Connectors

Failure: dotted connector lines between diagram and side panel looked awkward or arbitrary.

Fix:

- Remove connectors unless they carry a necessary mapping relation.
- If a connector is needed, attach it to precise anchor points and keep opacity low.
- Prefer spatial grouping, color correspondence, or local labels over arbitrary dotted lines.

## Meaningless Warning Line Or Boundary

Failure: a red line, warning stroke, boundary, bracket, or separator appears
without a named mathematical object. Viewers cannot tell whether it is an axis,
set boundary, threshold, or decoration.

Fix:

- Before drawing the line, name the object it represents in stage direction:
  zero axis, set boundary, forbidden region, interval endpoint, or comparison
  threshold.
- If no mathematical object or visual hierarchy role exists, remove it.
- Do not add red strokes merely to make a failure look dramatic. Red should
  mark the failed object or true boundary, not an invented prop.

## Ambiguous Integral Area Fill

Failure: a filled region, strip, baseline-to-curve area, or translucent patch is
shown near an integral, but the viewer cannot tell what quantity the area
represents. A curve plus a straight baseline can be read as "area under this
curve" even when the lesson intends a product density or another derived
quantity.

Fix:

- Before adding any fill or bar strip, name the exact quantity: `f(x)g(x)`,
  `|f(x)|^2`, a positive/negative part, or another explicit density.
- Prefer labeled sample bars for a construction from sums to integrals.
- If a smooth fill is used, it must be the same density named in the nearby
  formula and must not be visually attached to an unrelated curve.
- Remove decorative fills; do not use area-like patches for atmosphere.
- During QC, mute the narration and ask what the region means. If the answer is
  ambiguous, revise.

## Desynchronized Views

Failure: two panels are meant to show the same mathematical state, but the graph, formula, slider, label, or sound cue is animated from separate hand-tuned values.

Fix:

- Define one shared driver: tracker, function, array, simulation state, matrix, tensor, or event stream.
- Make every synchronized view read from that driver.
- During QC, pause on keyframes and compare all dependent views numerically or visually.
- Record the driver and dependent channels in `experiment-log.md`.

## Decorative Media Pretending To Be Math

Failure: a photo, video frame, image warp, or audio-reactive visual is interesting, but it is not actually generated by the mathematical map being taught.

Fix:

- Treat media as texture, signal, initial condition, point cloud, or dataset.
- Apply the actual mathematical transform to the media domain or data stream.
- Keep grid lines, anchor points, labels, or before/after markers visible so the mapping can be read.
- If the media is only for humor or atmosphere, classify it as editorial and do not use it as evidence for the math.

## Overbuilt Multi-View Shot

Failure: a concept that could be explained clearly in one view is split into many panels, insets, media textures, labels, or synchronized animations because the technique is available.

Fix:

- Start with the smallest honest view.
- Add another view only if it reveals a hidden relation, cross-checks the object, prevents a misleading projection, or preserves identity through a transition.
- Remove panels that repeat the same information or make labels/formulas too small.
- Record the representation budget in `experiment-log.md`: each extra view should have a job.

## Overdecorated Short Formulas

Failure: every short formula was framed; later, every short formula was underlined.

Fix:

- Use bare formulas by default.
- Use one active underline only for temporary focus.
- Use frames only for conclusions, formula groups, contrast structures, or derivation containers.
- Bind colors to semantics, not decoration.

## Palette Underuse Or Misuse

Failure: a segment used only blue/yellow/white or used accent colors without semantic meaning.

Fix:

- Use blue for structure, yellow for examples/aha, red for warnings/boundaries, pink for questions.
- Use at most two accent colors per shot.
- Let chalk and board dominate.

## Panel And Content Overlap

Failure: old panels faded while new formulas appeared over them; a single bad frame was still visible.

Fix:

- If bounding boxes overlap, complete fadeout before new content enters.
- Extract frames at transition times, not only settled states.
- Use stable panel positions and predictable content slots.

## Panel Over Active Function Graph

Failure: a formula panel, operation board, caption, or framed formula is placed
over an active function graph or sample construction. Transparency makes the
overlap less opaque, but it still blocks reading and makes the graph look like a
background texture instead of the mathematical object. This is a
`stage_management_failure` and often an `ambiguous_visual_object` failure.

Fix:

- Reserve graph and formula-board stage regions before coding.
- When a right-side board is needed, move the function graph left and reduce
  its width so the board owns clean space on the right.
- Add a protected graph-region check to the layout audit, not only
  text-vs-text collision checks.
- Review transition frames where the board enters and exits; do not pass a
  scene because the final frame happens to be cleaner.
- Treat transparent panel/graph overlap as a failure when it makes the active
  curve, samples, or axes harder to read.
- Do not over-apply this as a ban on all diagram annotations. Direct labels,
  tangent/derivative callouts, local linear approximations, normals, sample
  value tags, or local zoom annotations may sit on the graph when they are the
  exact local object being taught, have a clear anchor, preserve the global
  curve silhouette, and clear when the local explanation ends.
- If an annotation needs more text than the local graph can carry, create a
  zoom/inset or move the explanation to a side lane instead of covering the
  main graph.

## Panel State Collision

Failure: a formula panel changes conceptual role but old formulas remain while new formulas enter, so definitions, derivations, and conclusions stack into one unreadable block. In episode 0001 this happened when the `M_w` matrix, the column labels, and the orthogonality/equal-length formulas were all visible in the same right panel.

Fix:

- Treat each panel as a stateful slot with one current semantic role.
- Before introducing a new role in the same slot, fade out or dim the old contents completely.
- If old and new formulas are unrelated in meaning, do not cross-fade them in the same time interval. Allocate a clear-out interval, even a short one, so the slot is visibly empty before the new formula enters.
- Move the slot if the formula role changes. A matrix definition can live in a side board; a conclusion may deserve a wider middle or bottom board.
- Use a small layout helper or explicit safe-zone contract that fits formulas to the slot before placing them.
- During QC, extract frames at the exact role-switch time, not just at the final hold.
- If the right slot is formula-dense, remove the title band or shorten the title instead of letting it collide with the panel.

## Shared Region Transition Overlap

Failure: two unrelated subshots reuse one formula lane, side board, or diagram
pocket, but the old owner fades out over the same long interval in which the
new owner fades in. Even if the final frame is clean, the transition itself
contains several unreadable frames where viewers cannot tell which concept owns
the region.

Fix:

- Treat any reused region as a temporal ownership handoff.
- Hold the outgoing content only until its narration beat is complete, then
  clear it in a short visible interval before the incoming content enters.
- Use `ReplacementTransform` only when the new object preserves identity with
  the old one. For unrelated formula roles, clear first, then enter.
- Write the clear-out interval in stage direction and include outgoing,
  clear-out, and incoming frames in QC.
- During review, reject a scene if the only clean evidence is a settled frame
  after a messy shared-slot cross-fade.

## Complex Sample Label Clutter

Failure: a miniature complex plane or local sample diagram is surrounded by a
long title, explanatory caption, axis labels, point labels, arrows, and formula
panels in the same small pocket. The mathematical operation may be present, but
the viewer sees a label cluster instead of one clean object relation.

Fix:

- Give the local diagram one job and one short object label, such as
  `i -> -i` or `z -> z^*`.
- Move explanatory sentences to narration, a side formula lane, or a separate
  text cue outside the mini diagram.
- Keep axis labels only when they help identify the operation; remove or shrink
  them when the title or formula already supplies the context.
- Attach any annotation to the exact object it explains, and clear it when the
  local sample no longer owns attention.
- During QC, mute narration and ask whether the local operation is readable
  from the diagram alone. If the answer is "there is too much text", revise.

## Missing Stage Direction

Failure: a Manim scene is implemented from vague storyboard text such as "show the formula on the right", so formulas pile into one corner, panels are overused, and the temporal overlap of old and new objects is discovered only from screenshots.

Fix:

- Write a stage-direction document before coding formula-dense shots.
- Divide the canvas into named zones such as plane, parameter shelf, derivation board, proof lane, bottom formula lane, and sprite safe zone.
- For every subshot, specify local time, formula position, movement, transformation, color change, frame/underline/bare hierarchy, entrance, exit, and required clear-out.
- If two formulas are logically connected, show the connection through motion: transform product to coordinate map, pull matrix columns into vectors, move a conclusion from diagram evidence into a proof lane.
- If two formulas are not logically connected, do not cross-fade them in the same slot; leave the slot visibly empty before the next role enters.
- Extract transition keyframes, not only settled keyframes, because the bad frames usually happen during overlap.

## Rigid Stage Zones

Failure: after introducing stage zones to prevent overlap, the layout becomes a dead grid: left side is always a plane, right side is always a formula board, proof is always a small lower strip, and related formulas are separated by empty space.

Fix:

- Treat zones as dynamic occupancy claims, not permanent roles.
- Declare the layout mode for each subshot: split diagram/formula, full-plane takeover, derivation page, linked cluster, center reveal, or inset.
- Let diagrams expand to full screen when the motion needs immersion.
- Let long proofs take the whole board; shrink diagrams to insets or remove them temporarily.
- Pull strongly related definitions and conclusions together through adjacency, alignment, braces, arrows, color continuity, or actual formula transforms.
- Audit for dead space: empty canvas between strongly related objects is a layout failure unless it deliberately creates pause or emphasis.

## Detached Related Formula Groups

Failure: formulas that belong to one local thought are split across distant regions. In episode 0001, `w=alpha+beta i` and `z=x+yi` appeared in the upper right while the immediately related product `wz=(...)` appeared at the bottom, making the viewer's eyes jump between unrelated-looking regions.

Fix:

- Start from object relationships, not from a pre-made block map.
- If a formula is an immediate continuation of a definition, keep it in the same temporary attention group or animate it out of that group.
- Use `ReplacementTransform`, movement, color continuity, or shared alignment to show that one formula becomes the next.
- Reserve bottom lanes for true bridges between separate representations, not for a line that belongs to the active local formula cluster.
- During QC, ask whether a viewer can predict where the next related formula will appear. If the answer is no, the stage direction is not yet specific enough.

## Taylor Partial Sum Too Low-Order

Failure: showing only up to `S_3` did not demonstrate convergence inside radius and failure outside.

Fix:

- Push partial sums farther, such as `S_0,S_1,S_2,S_3,S_5,S_10,S_20,S_30`.
- Generate curves from the true partial sum `S_n(x)`.
- Show inside radius and outside radius with different colors.

## Meaningless Red Arrows Outside Radius

Failure: red arrows were added to show outside-radius failure, but they felt arbitrary.

Fix:

- Extend the same partial-sum curve beyond the radius by a visible amount.
- Color inside radius yellow and outside radius red.
- Do not add symbolic arrows unless they correspond to an actual visual relation.

## Hidden Singularity Label Collision

Failure: interval and origin labels overlapped in the hidden-singularity/Taylor radius segment.

Fix:

- Remove nonessential origin labels.
- Keep the point or axis mark if needed.
- Check final panel against diagram positions.

## Arrow Drawing Feels Split

Failure: arrows entered as a line first and a triangular head later.

Fix:

- Use `GrowArrow` for primary directed mathematical objects.
- Reserve `Create` for curves, grid lines, circles, and traced paths.

## Updater Ghosts

Failure: `always_redraw` objects reappeared or left residual frames after fadeout.

Fix:

- Remove objects after fadeout or clear updaters.
- Do not rely only on opacity animations for objects regenerated by updaters.

## Voice And Audio Drift

Failure: audio tests sounded like different voices or had inconsistent loudness.

Fix:

- Normalize loudness before serious listening.
- For current TTS production, prefer the validated IndexTTS2 MLX 8-bit route with fixed speaker/emotion/seed/normalization over VoxCPM2 long stateful continuation.
- Treat VoxCPM2 anchors as historical references unless a new long-form listening test proves stability.
- For voice conversion, test short segments first, then one section, then larger ranges.

## MLX Metal Device Invisible

Failure: IndexTTS2/MLX fails with `mlx.core.metal.Device ... index 0 beyond bounds for empty array`, or appears to "fall back" because no Metal device is visible.

Fix:

- First run a minimal MLX smoke test: `python -c 'import mlx.core as mx; print(mx.array([1,2,3]))'`.
- If the smoke test fails, stop TTS parameter debugging; the process cannot see Metal.
- Restore full-access/non-sandbox execution, then rerun the smoke test before invoking IndexTTS2 again.
- Record this in `experiment-log.md`, because otherwise future debugging may wrongly blame the text, speaker, emotion audio, or checkpoint.

## Relative Output Path Breaks TTS Save

Failure: IndexTTS2 inference succeeds internally but saving audio fails with `soundfile.LibsndfileError`, especially when a wrapper script invokes `mlx-indextts` from a different working directory.

Fix:

- Pass absolute paths for output directories and generated files.
- Check that parent directories exist before launching the TTS CLI.
- Keep model-generated raw WAVs, normalized review WAVs, and final stitched exports in separate explicit directories.

## TTS Text Rule Changed But Audio Not Regenerated

Failure: `script.md` or `tts-speaking-rules.md` is corrected, but the listener still hears the old pronunciation because the full audio was not regenerated or patched.

Fix:

- Treat text correction and audio correction as separate states.
- For every TTS text fix: regenerate the affected segment, normalize it, patch or restitch the full audio, rerun SRT/alignment, and update `timeline.json`.
- Provide a short preview of replacement windows for listening QC before accepting the patch.

## Mathematical Word Mispronunciation

Failure: a mathematical term has an unwanted pronunciation, such as IndexTTS2 reading `模长` as `mo zhang`.

Fix:

- Use a TTS-only pronunciation spelling, such as `模常`, when it reliably produces the intended sound.
- Keep screen formulas, final subtitles, storyboard prose, and searchable math text correct as `模长`.
- Record the hack in `tts-speaking-rules.md` and the experiment log so later subtitle correction does not preserve the fake spelling.

## Fake Or Unclassified Sound Effects

Failure: a sound effect is added because it feels nice, but the viewer may read it as if it encodes a mathematical event.

Fix:

- For mathematical sonification, export an event stream from real mathematical objects and generate sound from that stream.
- For humor, atmosphere, or character reactions, classify the sound as editorial, not mathematical.
- Record both kinds in timeline, but keep their purpose separate.
- During review, ask whether the sound would still make sense if the math event were removed. If yes, it is probably editorial.

## Process Failure: No Reviewable Output

Failure: too much planning or too large a target could leave no watchable artifact.

Fix:

- Deliver one complete process sample if the full episode is too costly.
- Include timeline, formula manifest, Manim render, audio mix, QC frames, and experiment log.

## Human Feedback Not Converted To Authoring And Review Regression Tests

Failure: the user manually identifies an obvious animation or review failure, but the finding remains only in chat or is only given to the reviewer. Later animation agents can recreate the same problem during design, and later subagents can pass the same pattern again because no tracked issue, feedback note, or known-failure rule forces either side to check it.

Fix:

- Write a human-feedback note under `videos/NNNN-slug/review/human-feedback/`.
- Create one `review/issues/*.json` item per actionable finding with `source: human_review`, `pattern_key`, `must_check_in_future: true`, `applies_to_authoring: true`, `authoring_preflight_check`, evidence, impact, and fix target.
- Promote reusable patterns into this file or the appropriate philosophy/QC reference.
- Before future storyboard, timeline, stage direction, or animation code, the animation author must read human-feedback notes and issue JSONs and write an authoring preflight checklist explaining how applicable patterns are avoided.
- Before every future audit, the reviewer must read the same records and verify the authoring preflight was actually used. A repeated human-found pattern is an automatic `revise` or `blocked` verdict.

## Valuable Agent Feedback Not Promoted To Regression Tests

Failure: a subagent or group reviewer catches a new real failure, the main
agent agrees it is useful, but the lesson remains only in the audit report. A
later animation agent then repeats it because only human review feedback was
treated as durable experience.

Fix:

- Keep ordinary subagent findings in the current audit report and
  `review/issues/*.json` repair queue.
- When the coordinator judges a subagent finding reusable, write an accepted
  note under `videos/NNNN-slug/review/agent-feedback/`.
- Create or update a `review/issues/*.json` record with `source:
  accepted_agent_feedback`, `origin_source: subagent_review`, `accepted_by`,
  `pattern_key`, `must_check_in_future: true`, evidence, impact, fix target,
  and `authoring_preflight_check` when applicable.
- Future animation authors must include accepted agent feedback in the same
  preflight checklist as human feedback; future reviewers must check it before
  passing a scene.
- Promote the distilled rule into this file or the relevant philosophy/QC
  reference when it generalizes beyond the current shot.

## Subagent Review Assumes Expert Knowledge

Failure: the subagent judges a scene as understandable because the mathematical intent is visible to someone who already knows the lesson, while a novice viewer cannot infer the visual causality, limit process, or meaning of the symbols from the animation itself.

Fix:

- Review from the perspective of a viewer who has not learned the concept yet.
- For each narration beat, identify the exact visual cause, change, or consequence visible at that time.
- If the scene requires the viewer to fill in a missing step from prior knowledge, add an intermediate visual beat or revise the storyboard/timeline.
- Treat "the code computes the right object" as insufficient; the rendered motion must teach the relation.

## Text Or Formula Exceeds Its Container

Failure: text or formula inside a chip, frame, bracket, or panel crosses the border, gets clipped, or visually presses into the border. This can happen in active or dimmed rows and is still a failure when only one frame or one state is ugly.

Fix:

- Size the container from the final rendered text bounds plus padding, or scale the text to the stable container before placement.
- Check active, dimmed, entering, exiting, and highlighted states.
- Extract QC frames at dense rows and transition states, not only at the first settled frame.
- Do not pass a review if any text touches or crosses its frame.

## Coarse Timeline Visual Alignment

Failure: the review MP4 has the correct total duration, but narration and visual actions are only loosely related. Several spoken ideas are covered by one broad visual phase, so viewers cannot tell which object or operation the voice is referring to.

Fix:

- Audit at narration-beat granularity, using `timeline.json`, SRT/alignment, and the review MP4 together.
- For each spoken concept, record the timestamp where the corresponding visual object enters, changes, or receives focus.
- Add visual beats, pauses, highlights, or transitions until the viewer can track the explanation without rereading the script.
- Total duration match is not an acceptance criterion by itself.

## Vector Ellipsis Outside Brackets

Failure: a vertical ellipsis or dotted continuation represents additional vector or matrix components, but it sits outside the left/right brackets or below brackets that visibly stop before the ellipsis. This falsely suggests the omitted entries are not part of the vector.

Fix:

- Extend the brackets to enclose every displayed component and the ellipsis.
- If the vector is too long, use a bracket style that spans the visible column including `\vdots`, or show a compact column with an internal ellipsis.
- During review, check the densest component-column frame and the final held frame.

## Sparse To Dense Sampling Jump

Failure: a function is explained as being sampled more and more densely, but the animation shows one sparse set and then jumps directly to a dense or continuous state. The construction hides the limiting process and assumes the viewer already understands why dense samples approximate the graph.

Fix:

- Animate a monotone density progression: few samples, more samples, many samples, then dense samples visually approaching the function graph.
- Keep the same function driver and sampling rule across all densities.
- Use at least one intermediate density unless the narration explicitly says it is skipping.
- Connect the sample points or bars to the component vector so the viewer sees that the long vector grows from the same process.

## Inner Product Integral Missing Sampling Causality

Failure: a scene claims the finite dot product becomes a function inner product,
but the render jumps from vectors to an integral formula without showing the
intermediate sampled function values, component products, finite sum, and
density limit. This is worse than a sparse-to-dense issue because the main
conceptual bridge is missing.

Fix:

- Use one shared sample driver `x_i` for both functions.
- Show `f(x_i)` and `g(x_i)` as paired sampled values and as components of
  sampled vectors.
- Show the component products `f(x_i)g(x_i)` entering a finite sum.
- Increase sample count monotonically, keeping the same functions and interval.
- Only introduce the integral after the viewer has seen the finite sums become
  denser over the same interval.

## Weak Example Functions Hide Product Shape

Failure: the functions used for an inner-product example are mathematically
valid but visually too flat or too similar. Their product density looks nearly
constant, so the viewer does not see why the integral accumulates a changing
pointwise product.

Fix:

- Choose pedagogical positive functions with visibly different shapes and
  enough amplitude variation for the product density to change clearly.
- Keep the example honest: record the function formulas, value ranges, product
  range, and any display scaling in the experiment log.
- Avoid functions whose product bars look like a uniform ruler unless constancy
  is the actual lesson.
- During QC, inspect the product-density frame without formulas. A novice
  viewer should be able to see that the bars encode a varying quantity.

## Complex Conjugate Reason Not Visualized

Failure: a star appears in the formula or `f(x)g(x)` is replaced by
`f^*(x)g(x)`, but the viewer is not shown why the correction is required. The
conjugate looks like notation to memorize rather than the operation that makes
self-inner-products nonnegative.

Fix:

- Show a concrete complex-valued sample or constant, such as `f(x_i)=i`.
- Show the invalid self-product without conjugation, `f_i f_i=i^2=-1`, as a
  red failed length-density or failed scalar.
- Then show the corrected product, `f_i^* f_i=(-i)i=|i|^2=1`, as a
  nonnegative real density.
- Attach the star to the exact `f` token being conjugated. Do not float a star
  near the formula or use it as decoration.
- After the sample-level reason is clear, lift the correction to the integral
  formula.

## Ugly Pairing Connectors In Dot Products

Failure: dot-product component pairing is shown by arbitrary horizontal lines
between two vector columns. The lines look crude, do not become product terms,
and make the viewer infer the operation.

Fix:

- Prefer aligned rows that explicitly form `u_i v_i` or `f(x_i)g(x_i)`.
- If a connector is used, it must attach exact paired components and transform
  into the corresponding product term.
- Remove connector lines before they become clutter; do not leave them as
  decorative strokes.

## Misplaced Symbol Highlight

Failure: a star, underline, circle, arrow, or color patch is placed near a
formula but not on the exact token it modifies. Viewers may read the marker as
decoration or as applying to the wrong expression.

Fix:

- Use token-level formula transforms when a symbol changes meaning, such as
  `f(x)` becoming `f^*(x)`.
- Place highlights directly on the target token and remove them once the
  transformed formula is established.
- During QC, ask what expression the marker modifies with the narration muted.
  If the answer is ambiguous, revise.

## Aesthetically Ugly But Technically Correct

Failure: a frame is mathematically computed but looks cramped, awkward, unbalanced, overboxed, poorly spaced, or visually amateurish. The reviewer passes it because no formula is false.

Fix:

- Treat obvious ugliness as a review failure, not a preference note.
- Check spacing, alignment, padding, rhythm, color restraint, and full-frame composition at every held state.
- If a user has already flagged a comparable aesthetic failure, encode it as a human-review regression issue and block repeats.
