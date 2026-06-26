# Production Loop And QC

This file condenses the hard requirements for episode-style production. Use it for every segment.

## Required Pre-Work

Before animation:

- Read the route workflow.
- Read source script and SRT/alignment.
- Read `20-math-object-driven-animation.md`.
- Read `30-visual-language-and-style.md`.
- Read `41-production-output-contract.md`.
- Check `formula-manifest.md`, `storyboard.md`, `timeline.json`, and `experiment-log.md`.
- Read the episode's `review/human-feedback/` notes, accepted
  `review/agent-feedback/` notes, and `review/issues/*.json` entries with
  `source: human_review`, `source: accepted_agent_feedback`, or
  `must_check_in_future: true`.
- Convert applicable human-found and accepted-agent-found `pattern_key` entries
  into an authoring preflight checklist before writing stage direction or
  animation code.

## Formula Manifest

Important formulas from the source script must appear visually even if not spoken.

For each formula, track:

- formula or expression.
- source context.
- whether narration speaks it.
- time range in animation.
- timeline segment id.
- Manim scene or shot.
- display mode: main formula, corner cue, derivation, board writing, object label.
- status: `pending`, `implemented`, `verified`.

## Timeline

`timeline.json` must at least support:

- `segments`
- `visual`
- `audio`
- `character`
- `sonification`
- `bgm_suggestions`

Each segment should record:

- `id`, `start`, `end`
- narration/subtitle text
- source script segment
- visual action
- audio source
- sound effect triggers
- character state
- Manim scene or shot
- rhythm notes
- purpose in the main narrative
- transition in/out
- screen text purpose

Timeline is the core artifact for re-editing, audio replacement, BGM, and refinement.

## Storyboard Versus Timeline

`storyboard.md` is for human review and direct user edits. It should explain
the scene grouping clearly: which script segments form one larger shot, why
they belong together, what visual language carries across the group, what
mathematical objects and drivers are used, how the stage is occupied over time,
and what the reviewer should challenge.

`timeline.json` is for animation compilation, audio alignment, and exact
cross-checking. It must be detailed and time-specific: segment ids, larger
scene/group ids, start/end times, voice windows, objects, drivers, formulas,
entrances/exits, transitions, screen-text purpose, review anchors, and adjacent
continuity notes should be explicit enough for an agent or script to build and
audit the animation without guessing from prose.

Both files must consider stage direction. The storyboard explains it in
reader-facing language; the timeline pins it to exact timing and machine-usable
fields. A per-segment visual summary is not enough when several segments need
one continuous visual language.

## Stage Direction

Before implementing a formula-dense process sample, create a stage-direction document or equivalent timeline fields. It must be concrete enough that another animator can reconstruct the shot without guessing coordinates.

For each subshot, record:

- exact local time interval;
- layout mode, such as split diagram/formula, full-plane takeover, full derivation page, linked formula cluster, or center reveal;
- formula text and stage zone;
- diagram objects and their mathematical driver;
- panel/frame/underline/bare-formula hierarchy;
- entrance, exit, movement, transformation, opacity, and color changes;
- sprite position and occlusion policy;
- old objects that must clear before the next object enters;
- logical continuity between related formulas, such as a product formula becoming a coordinate map, a matrix column becoming a vector, or a rotation label becoming an algebraic conclusion.

If the shot would still make sense as a static PPT slide but not as a continuous derivation, the stage direction is incomplete. Lecture animation should feel closer to an expert writing and reorganizing a board than to unrelated cards appearing in one corner.

Named zones are aids, not cages. A zone may expand, shrink, become an inset, merge with another zone, or temporarily disappear. The QC question is not "did every object stay in its assigned box?" but "did the canvas allocation follow the mathematics and guide the eye without collisions or dead space?"

Do not start from blocks. Start from objects and relationships, then create temporary attention groups only when they help. A stage direction can say "no block here; the vector and formula remain connected by motion and color" if that is clearer than drawing or reserving a region.

Implementation-level choreography may live directly in the Manim scene as a structured `STAGE_SCRIPT` constant or class docstring when it specifies exact object entrances, exits, transforms, and spatial claims. Keep global philosophy in this skill and narrative intent in `storyboard.md`; keep code-local stage scripts concise and object-level so they cannot drift from the implementation. Do not scatter long prose comments through animation methods.

## Manim

- Use Manim Community Edition only: `uv run manim ...`.
- Use `41-production-output-contract.md` for canonical quality flags, fps, `--media_dir`, raw render paths, review MP4 naming, QC frame naming, and final stitching.
- Default segment review render is `-qm --fps 30 --disable_caching` with `--media_dir videos/NNNN-slug/exports/manim`.
- `-ql` is only for smoke checks; it is not a review-acceptance render.
- For final candidates, use 1080p30 by default unless the project records a reason for 60 fps.
- Prefer local reusable helpers in `src/theme.py`.
- Use `GrowArrow` for primary arrows.
- Use real parameters and updaters for transformations.
- Choose the minimal number of views needed; do not split the screen when one focused mathematical view is clearer.
- When multiple views show the same object, use one shared driver for curves, formulas, labels, sliders, media textures, and event cues.
- When using real media as texture/data, bind it to a stated mathematical map, signal transform, initial condition, or dataset.
- Avoid `Transform(a,b)` when viewers may read it as dragging instead of an operation-driven map.
- Render per-segment review videos; do not jump straight to one full merged video.
- Review MP4s must include the relevant voice window and accepted sound layers unless the task is explicitly visual-only.
- Extract QC frames from the review MP4 whenever audio timing affects the edit.

## Audio And Sonification

- Audio edits, SRT, and timeline must stay synchronized.
- Normalize voice audio used for review or final stitching.
- Mathematical sound effects should be short, clean, and tied to mathematical events.
- If Manim does not support the desired sound directly, export a mathematical event stream from the same code or timeline, then generate sound externally from that stream.
- Event streams should record time, event type, object id, position, and parameters such as angle, norm, curvature, level, or crossing count.
- External sound generation can use Python audio libraries, samplers, or ffmpeg; pitch, volume, pan, timbre, and decay should be derived from event parameters when the sound represents a mathematical object.
- Editorial sound effects for humor, character beats, or atmosphere are allowed, but record them separately as editorial/aesthetic cues. Do not present them as mathematical sonification.
- Record each sound effect trigger in timeline.
- BGM is optional during experiments, but give exact suggested entry/exit/fade/energy points.

## Character Sprites

- Use character sprites only when they support pacing or tone.
- Do not cover formulas or core diagrams.
- Search existing project assets before assuming a sprite exists.
- If using image generation or placeholder assets, record prompt, path, use, and final/reference status in `experiment-log.md`.
- When sprites are part of the episode style, `timeline.json` must record concrete sprite cues, not only `none_by_default`.
- For each visible sprite cue, record character, action, asset path or asset family, position, height, entrance/exit, purpose, and occlusion policy.
- Keep sprites as an editorial/pacing layer. They may point, react, or hold attention, but they must not pretend to be mathematical evidence.
- Hide or move sprites during formula-dense frames, axis transforms, or any moment where they would compete with the mathematical object.

## Experiment Log

Write while working, not after the fact. Record:

- commands and parameters.
- audio processing and render settings.
- design decisions.
- mathematical objects and display mappings.
- representation budget: why each extra view, media element, or synchronized channel is necessary.
- shared drivers for synchronized views and the channels they control.
- media sources, transform maps, and whether each media asset is mathematical, editorial, placeholder, or final.
- failed attempts and why they failed.
- user feedback and fixes.
- output paths.
- QC frame paths.
- review MP4 path and mux/mix command.
- raw Manim path, quality flag, fps, and media root.
- process reflections and next efficiency improvements.
- authoring preflight checklist from human feedback: which `pattern_key`
  records were read, which apply to the segment, and the concrete design/code
  decision used to avoid repeating them.
- skill promotion candidates: reusable lessons that may belong in `60-skill-evolution-and-lessons.md` or another skill reference.
- branch/subagent/worktree observations when used.

## QC Checklist

After every segment:

Run the audit in three layers before deciding a verdict:

1. **Abstract standards first.** Check the broad standards in
   `50-known-failures-and-fixes.md`: stage management, ambiguous visual
   objects, mathematical identity/causality, beat-level timeline alignment,
   space utilization, visual hierarchy, and pedagogical example adequacy. Each
   audit report should list the applicable `standard_key` results, even when
   no known concrete failure exactly matches.
2. **Concrete regressions second.** Read human-feedback notes, issue JSON, and
   known concrete failures. For each matching `pattern_key`, cite evidence and
   decide pass/fail. These cases calibrate the abstract standards; they do not
   limit them.
3. **Actionable findings last.** Every finding should name the violated
   `standard_key`, any matching concrete `pattern_key`, timestamp/QC frame or
   file line, why it matters to a novice viewer, and a specific repair path. If
   a problem violates an abstract standard but has no concrete case yet, create
   a new issue JSON with a new `pattern_key` and promote it after repair.

- Render succeeded.
- Audio track exists and duration is checked.
- Raw Manim render path follows the output contract.
- Review MP4 exists in the canonical `exports/reviews/<scene_slug>/` directory.
- Keyframes extracted.
- QC frames exist in the canonical `exports/qc/<qc_id>/` directory and include transition frames, not only settled frames.
- If a formula lane, side board, or diagram pocket is reused by two subshots,
  the QC frame set must include the outgoing state, the clear-out interval, and
  the incoming state. Long cross-fades of unrelated formula roles in the same
  slot are a blocker even when each settled frame is readable.
- Manim formula/text/panel-heavy scenes have a scene-specific `tools/layout_check.py`
  audit saved as JSON under `review/audits/<scene_slug>/`. Configure the audit
  to fail on overlap, out-of-frame objects, container overflow, and close
  warnings when objects visually press together. If the tool is not applicable,
  record why in `experiment-log.md` and compensate with explicit frame evidence.
- When a graph, coordinate plane, sampled function, or other active diagram
  shares the frame with a formula panel or operation board, the layout audit
  must include protected diagram regions. A transparent panel or formula over
  an active graph is a collision when it prevents reading the active object.
  Direct on-diagram annotations are allowed only when they label the exact
  local mathematical object, have a clear anchor, preserve the main object
  silhouette, and clear when their local role ends.
- Authoring preflight exists and names the human-feedback and
  accepted-agent-feedback `pattern_key` records considered before
  storyboard/timeline/stage/code work.
- Regression records were read: `review/human-feedback/`,
  `review/agent-feedback/`, `review/issues/*.json` with `source:
  human_review`, `source: accepted_agent_feedback`, or
  `must_check_in_future: true`, and `50-known-failures-and-fixes.md`.
- Formulas are readable and not overlapping.
- Any text, formula, or label inside a frame, chip, bracket, or panel stays
  fully inside that container in active, dimmed, entering, and exiting states.
- Visual hierarchy follows formula/color rules.
- Coordinate grids and axes are mathematically aligned: the origin is a grid point, and the axes sit on grid lines unless an explicitly logged mathematical reason says otherwise.
- Stage direction exists for formula-dense shots and matches the rendered motion.
- The segment is understandable to a novice viewer without assuming they
  already know the target concept; visual causality is explicit.
- Narration, timeline, and visual action are checked at fine beat level, not
  merely by matching total duration.
- Every extra panel, inset, media element, or synchronized channel earns its space.
- Example functions and teaching parameters are visually adequate for the
  lesson target. If an operation depends on a product, density, sign change, or
  oscillation, the chosen example should make that quantity visibly change.
- Arrows start from correct origins and grow naturally.
- Curves, fields, rotations, and transforms are math-driven.
- Function scalar multiplication is pointwise. In particular, `-f` must be a
  visible reflection of the same `f` across the x-axis, with matching sample
  correspondences when the claim is being taught.
- No warning line, connector, bracket, frame, star, underline, or highlight may
  appear unless it has a named mathematical or hierarchy role. Decorative lines
  and floating symbol markers block acceptance.
- No filled area, translucent strip, or baseline-to-curve region may appear
  unless it is the exact named quantity being integrated or compared. Ambiguous
  integral-area cues block acceptance.
- Discrete-to-continuous or sparse-to-dense processes progress gradually enough
  to show the limiting idea; no single unexplained jump substitutes for the
  construction.
- Function inner-product visuals must show the causal chain when it is the
  lesson target: shared samples of `f` and `g`, sampled values as components,
  component products, a finite sum, monotone densification, and only then the
  limiting integral.
- Complex inner-product visuals must not introduce conjugation as a floating
  star or formula decoration. If the lesson claims conjugation is needed for
  length squared, the render must show why `f f` can fail and why
  `f^* f=|f|^2` is nonnegative.
- Vector, matrix, tuple, and component notation is visually faithful: ellipses
  and long columns that represent components remain inside the relevant
  brackets or have brackets that visibly extend to include them.
- Synchronized views agree because they read from one driver or one documented data stream.
- Media warps, image filters, video textures, or audio-derived visuals are generated from the stated mathematical map/computation.
- Character sprite cues are concrete, restrained, and outside formula/diagram safe areas.
- No fake animation has crept in.
- No stale panels, stale labels, or updater ghosts remain.
- Timeline matches output at the level of individual narration beats and
  transition cues; "roughly matches" is not sufficient for acceptance.
- Important formulas are marked implemented/verified.
- Experiment log has outputs and anti-fabrication audit.
- Review handoff or assignment is updated when multiple agents are involved.
- Subagent/independent audit `pass` has been handed to the user for final
  viewing; do not treat the segment as commit-ready until the user explicitly
  approves it.
- Any reusable lessons are either left as project-local reflections or promoted through `60-skill-evolution-and-lessons.md`.

## Minimum Deliverable

If a whole episode is too costly, deliver a complete process sample:

- real or converted voice audio.
- `timeline.json`.
- `formula-manifest.md`.
- Manim animation.
- exact sound effects.
- watchable combined video.
- `experiment-log.md`.
- self-review notes.
- at least one mathematical core segment.

## Final Report

Report:

- branch name.
- changed files.
- review/final video path.
- raw Manim path.
- QC frame/contact-sheet path.
- timeline path.
- formula manifest path.
- experiment log path.
- audio path.
- voice and audio processing notes.
- sound effect generation notes.
- BGM suggestions.
- validation performed.
- known issues.
- user review status: `pending`, `approved`, or `changes requested`.
- human-feedback regression status: records read, repeated patterns found or
  not found, any new human feedback promoted to issue JSON / known failure,
  and any valuable subagent/group-review feedback accepted as
  `accepted_agent_feedback`.
- commit status; do not commit animation source/control changes while user
  review is still `pending`.
- next refinement suggestions.
