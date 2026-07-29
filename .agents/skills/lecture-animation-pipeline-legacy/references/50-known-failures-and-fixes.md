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

### `review_gate_failure`: Review Starts From Pass Instead Of Reverse Burden

Failure class: the reviewer looks for known blockers and passes the scene when
no exact rule is triggered. This creates a "疑罪从无" audit, so ambiguous,
ugly, or novice-hostile scenes pass because the reviewer did not first list
candidate violations.

Reject when:

- a formula-dense, diagram-dense, or previously human-rejected scene has no
  red-flag ledger;
- the audit report lists only passes and no suspected violations;
- a reviewer says a risk is acceptable without a written novice-viewer reason;
- subagent prompts omit concrete negative examples for recurring failures.

Acceptable only when:

- the audit starts from `revise`;
- candidate flags are listed before the verdict;
- the audit includes a ranked aesthetic/noise sweep naming at least the first,
  second, and third ugliest/noisiest/least-clear visual candidates;
- every candidate is `fixed`, `pardoned`, or `not_applicable` with evidence;
- no `open` candidate remains.

Concrete cases to consult: `Reverse Burden Review Not Applied`, `Human
Feedback Not Converted To Authoring And Review Regression Tests`, `Subagent
Review Assumes Expert Knowledge`.

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

### `creator_intent_text_substitutes_for_animation`: Narration Is Republished Instead Of Enacted

Failure class: the voice names a mathematical action, while the screen repeats
the same words or displays producer-facing explanation instead of changing the
mathematical object. The result is a narrated PowerPoint rather than animation.

Reject when:

- “旋转”“等比例伸缩”“镜像”“剪切”“拉伸”“弯曲”“平移”或“放大” is spoken but
  the corresponding object does not visibly perform that action at the word;
- the approved narration uses a legitimate synonym such as “等比缩放” or
  “拉长”, but the detector silently misses it or the author locally bypasses
  the mismatch instead of hardening the canonical detector and regression;
- a text block tells the viewer what the animation means while the underlying
  object remains static;
- the same explanatory phrase is both spoken and displayed without a distinct
  formula, label, parameter, comparison, or navigation job;
- a token highlight or formula replacement is submitted as evidence of a
  geometric transformation.

Acceptable only when:

- every strong action word is bound to exact word alignment and a measured
  runtime/frame-analysis geometry change;
- negative claims use a visible counterexample or inhibition contrast;
- screen text remains limited to objects that the learner needs to point to,
  calculate with, compare, or retain as symbolic memory.

Pattern keys: `narrated_transform_replaced_by_screen_text`,
`spoken_action_not_word_locked`, `narration_duplicated_as_screen_prose`,
`creator_intent_text_substitutes_for_animation`,
`narrated_action_synonym_escapes_detection`.

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
`Aesthetically Ugly But Technically Correct`, `Aesthetic Objection
Under-Enumeration`.

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
Container`, `Misplaced Symbol Highlight`, `Aesthetic Objection
Under-Enumeration`.

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

### `monolithic_scene_file_failure`: One Scene Owns Too Many Responsibilities

Failure class: one Manim `Scene` file owns mathematical drivers, object
construction, layout, beat scheduling, cleanup, review metadata, and one-off
audit logic at the same time. Small changes require touching unrelated timing
and layout code, so external workers and future repairs can break old stage
ownership while trying to fix one object.

Reject when:

- a small visual change requires editing a large scene method with unrelated
  timing and layout logic;
- low-cost agents must understand the whole scene before modifying one object;
- object identity, zone ownership, and clear intervals are implicit in code;
- review failures cannot be mapped to a small file or contract field.

Acceptable fix:

- Use a scene-local package with `contract.yaml`, `drivers.py`, `objects.py`,
  `layout.py`, `beats.py`, `composer.py`, and `audit.py`.
- Keep the composer thin: it schedules beats from the contract instead of
  hiding stage decisions inside ad hoc code.

### `contract_bypass_failure`: Code Drifts From The Scene Contract

Failure class: animation code changes object ids, timing, zones, or cleanup
behavior without updating the scene contract. The review artifact may improve
locally, but future agents, layout audit, QC anchors, and task handoffs still
believe the old stage ownership.

Reject when:

- rendered behavior contradicts `contract.yaml`;
- a new major object appears in code but not in `objects`;
- a beat reuses a zone without `clear_before`, `clear_after`, or transform
  identity;
- QC frames cannot be traced back to beat audit frames.

Acceptable fix:

- Update the contract first, rerun `validate_scene_contract.py`, then render
  and audit.
- Treat the contract as the local source of truth for stage ownership.

### `animation_preflight_bypass_failure`: Render Starts Before Source/Review Gate

Failure class: after human rejection or a dense-scene failure, the animator
starts patching Manim code or rendering again before proving that the source
structure, review scope, feedback consumption, and motion plan have been
repaired. This lets the same PPT-like or monolithic failure reappear under a
new version number.

Reject when:

- a human-rejected scene has no passing `animation_preflight_gate.py` result;
- `timeline.json` or `review/assignments.md` still points to a discarded
  combined source or combined review package;
- the scene lacks a component package even though the failure involved stage
  management, formula walls, or unclear mathematical causality;
- `contract.yaml` omits `motion_ledger` or `authoring_preflight`;
- the authoring preflight names a human issue but gives no concrete design
  response or QC proof target.

Acceptable fix:

- Run `tools/animation_preflight_gate.py` for one scene slug before final code
  and again before review handoff.
- Require `--risk-tier human-rejected --require-component-package
  --require-per-scene-review` after user rejection.
- Keep the review artifact one-scene-primary until the user approves that
  scene; combined clips may only be secondary context.

### `object_factory_scheduling_failure`: Component Code Performs Direction

Failure class: object or component factories secretly call `self.play`,
`self.wait`, `Scene.add`, `Scene.remove`, or direct timeline scheduling. The
composer cannot control cleanup, review visibility, or zone reuse because time
logic is hidden inside object construction.

Reject when:

- `objects.py` or component factories perform animation;
- object creation depends on the current `Scene` time;
- composer cannot control cleanup or audit visibility.

Acceptable fix:

- Object factories only create registered Mobjects.
- Animation belongs in `beats.py`; orchestration belongs in `composer.py`.

### `web_composer_drift_failure`: Browser Preview Becomes A Second Truth

Failure class: a browser or external preview tool becomes the layout source of
truth even though Manim's LaTeX boxes, camera, Mobject groups, and updater
lifecycle are different. The preview appears clean while the rendered Manim
review still overlaps, overflows, or loses object identity.

Reject when:

- a web preview is used as acceptance evidence without Manim render and QC;
- browser layout positions are manually translated into Manim guesses;
- the preview and final render disagree but the preview is treated as correct.

Acceptable fix:

- A web viewer may read or edit `contract.yaml`, show stage maps, and display
  QC frames.
- Acceptance must come from Manim render, layout audit, review MP4, and tracked
  issue status.

## Post-Restart Invisible Agent Mistaken For Lost Agent

Pattern key: `post_restart_visible_roster_false_negative`.

Failure: after the app or machine restarts, the first
`collaboration.list_agents` call shows only the main agent. The coordinator
assumes every completed child identity is gone and immediately spawns
replacement agents. In practice, the preserved canonical child paths may still
accept `followup_task` and recover their prior context.

Fix:

- Preserve canonical child ids, worktrees, branches, handoff paths, hashes, and
  exact next commands in the shutdown checkpoint.
- Probe every old canonical id directly with a no-write `followup_task` before
  diagnosing loss.
- Call `list_agents` again after the probes and seal both the visible roster and
  per-id probe outcomes with `seal-availability-snapshot`.
- A `restored` probe forbids replacement. Only a sealed
  `target_not_found`, `target_unavailable`, or `unrecoverable_error` outcome may
  support `authorize-replacement`.
- If a mistaken replacement was already opened, interrupt it before
  production, run `restore-original-identity`, and cancel unused authorization
  with `cancel-replacement-authorization`.

Review test: the resume evidence must show direct probe results for every
preserved id. A first-pass `list_agents` snapshot without those probes is never
sufficient replacement evidence.

## Sibling Worktree Production Drift

Failure: a new lesson or agent task is initialized in a sibling directory such as `/Volumes/bocchi/myLectures-0002-hilbert-tts` instead of the canonical repository root. The new `videos/NNNN-slug/` directory is no longer next to earlier lessons, first-lesson artifacts are harder to reference, and Git status fragments across multiple worktrees.

## Semantic-Correct Animatic Passed With Weak Visual Finish

Pattern key:
`semantic_correct_animatic_passed_with_weak_composition_and_visual_hierarchy`.

Failure: a low-cost animatic correctly represents the mathematical relation,
passes overlap and causal checks, and may even use the episode palette, but the
shot still looks like a debugging sketch. Primary objects are too small or
thin, visual tiers are indistinguishable, large empty areas have no attention
job, and later formulas or arrows float without inheriting the visual identity
earned by the preceding scene.

Fix:

- Treat an animatic as low-cost media, not as a composition exemption.
  Resolution, dense sampling, shading detail, and final easing may be deferred;
  framing, object scale, hierarchy, contrast, typography roles, line-weight
  roles, negative-space ownership, and transition topology may not.
- Require a `visual_finish` hard-gate sweep in addition to mathematical,
  layout, timing, and novice-causality checks.
- Make every stage identify one primary focal object, its supporting/context
  tiers, and the learning or transition job of every large negative-space
  region.
- Reject generic Manim-default appearance when the selected objects lack a
  deliberate scale, line-weight, brightness, and motion hierarchy.
- Aesthetic refinement is allowed only when it improves hierarchy, material
  coherence, rhythm, or inspectability. Remove flourishes that fail that test.

Review test: inspect representative opening, peak-explanation, transition, and
ending frames at thumbnail and full size. A muted viewer must immediately
identify the focal object and its causal successor, while no decorative object
becomes primary.

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

## External Worker Composition Drift

Failure: an external CLI worker is asked to "design" or broadly implement a
full lecture-animation scene from a storyboard paragraph. The worker invents
composition, object ownership, text placement, underlines, connectors, and
panels. The result may contain the requested labels and formulas, but it has no
coherent stage dispatch, no math-object-driven cause, and no professional
visual hierarchy.

Fix:

- The coordinator must own full-shot visual direction. External workers may
  implement bounded local objects, mechanical Manim code, render/QC extraction,
  or narrow repairs only after a concrete stage contract exists.
- Before assigning a writing task to Qoder/Pi/cheap-model workers, provide the
  exact time window, allowed files, allowed mathematical objects, forbidden
  additions, stage ownership intervals, cleanup requirements, typography rules,
  and a reference-frame or final-frame contract.
- If a worker cannot determine composition from the contract, it must stop and
  ask. It must not invent a layout.
- If a render fails at stage ownership or math-object-driven direction, stop
  patching that render. Redesign the shot at coordinator level, then assign
  smaller implementation tasks.
- During review, reject external-worker renders that look like topic maps,
  random label piles, static slogans, arbitrary underlines, or decorative
  branches even if the files render and the audio duration matches.

Source example: episode 0000 human feedback on the first Qoder pass for G001,
G002, G003, and G004.

## Unowned Topic Pile

Failure: a scene meant to criticize "tool pile" teaching or reorganize tools
into structure becomes an actual random pile of chips, labels, panels, arrows,
and stale objects. The final frame still reads as clutter, so the visual
message contradicts the narration.

Fix:

- Clutter is allowed only as a timed, readable critique with a named owner
  region and a cleanup interval.
- The final structure must be designed first: which labels remain, where they
  live, and what relations they prove.
- Limit the number of simultaneous topic chips. If more than a few names are
  needed, group them into compact, aligned structures or sequence them over
  time.
- Review the final settled frame muted. If it still looks like a pile rather
  than a structured relation, reject it.

## Static Route Slogans Without Object Driver

Failure: route introductions such as `复平面里的函数` and `函数空间里的函数`
are drawn as plain lines, labels, or slogans. The shot says there are two
routes, but no mathematical object causes the split or gives the routes visual
meaning.

Fix:

- Start from one shared object or problem that naturally branches into the
  routes.
- Make each route inherit a visible mathematical object: for example, a local
  patch/vector under complex multiplication for the complex-plane route, and a
  sampled function/vector projection for the function-space route.
- Keep route labels secondary. A route label should name the object relation
  already visible, not replace it.
- Reject route maps that would be equally informative as static slide text.

## Text Underline Positioning Drift

Failure: text labels, title baselines, underlines, or focus strokes are placed
by visual guesswork. Underlines float between labels, extend across unrelated
space, or become decorative separators. The shot looks unprofessional even
when the math labels are spelled correctly.

Fix:

- Reserve a title/label lane before placing text.
- Use bare labels by default. Use an underline only as a temporary focus cue
  attached to a specific formula or text token.
- At most one underline should be active in a shot. It must enter, hold, and
  exit with the object it emphasizes.
- During QC, inspect full-size frames, not only contact sheets, for title,
  underline, and label alignment.

## Function Space Decorative Branch Map

Failure: a function-space overview turns into a decorative topic map with broad
ribbons, side labels, and branch chips. The finite-vector to sampled-function
to product/sum/integral causality is hidden or skipped.

Fix:

- Begin with samples or components, then show sample values, products, sums,
  densification, and only then the integral or mode interpretation.
- Branch labels such as Fourier, operators, eigenvalue problems, special
  functions, or Green functions must enter as consequences of the constructed
  object chain, not as the main graphic.
- Avoid broad ribbons or filled connectors. Use thin anchored links only when
  they carry a necessary mapping relation.
- Mute the narration and ask whether the viewer can identify the object chain
  without reading the branch labels. If not, rebuild the shot.

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

## Full Episode QC Missing Boundary Frames

Failure: the official full-episode QC package contains only one settled or
midpoint frame per group. Segment-level QC may pass, but the stitched episode's
opening state, ending state, and group-to-group handoffs are not proved by the
full review evidence.

Fix:

- Extract full-episode QC frames from the full review MP4, not only from
  segment clips.
- Include `frame_t000p00s.png`, a near-ending frame, every group midpoint, and
  before/after frames around each group boundary.
- Use canonical sortable `frame_tNNNpNNs.png` names and rebuild the full contact
  sheet only from the current canonical frames.
- During final total review, reject a full QC package that cannot prove the
  stitched opening, ending, and transition ownership intervals.

## Export Artifact AppleDouble Sidecars

Failure: macOS creates AppleDouble `._*` metadata files inside generated export
directories on `/Volumes`. These sidecars may sit next to QC frames, SRT files,
or alignment JSON and can be mistaken for real artifacts by strict review or
final-packaging scripts. For example, `._*.json` in `exports/subtitles/` is not
parseable alignment JSON even though it has a JSON-looking suffix.

Fix:

- Run `dot_clean` on export subdirectories after generating, editing, copying,
  or patching artifacts on external volumes.
- Before strict review, verify `find <export-dir> -name '._*'` returns no
  files for the relevant QC, subtitle, review, or final-output directories.
- Artifact enumerators should ignore `._*` files, but the production package
  should still be cleaned before user handoff.
- Treat AppleDouble sidecars as blockers when they can break parsing, contact
  sheet generation, subtitle packaging, final stitching, or review evidence
  enumeration.

## Review Control AppleDouble Sidecars

Failure: AppleDouble `._*` metadata appears beside tracked review-control
files such as audit Markdown reports, `review/issues/*.json`,
`review/agent-feedback/*.md`, or `experiment-log.md`. These files are not real
review records, but strict review scripts may enumerate them and fail JSON
parsing or treat binary metadata as feedback.

Fix:

- After writing review reports, issue JSON, accepted agent feedback, or
  experiment-log entries on `/Volumes`, run `dot_clean` on the episode
  directory before handoff.
- Verify `find videos/NNNN-slug -name '._*'` returns no files before strict
  review, user handoff, staging, or commit.
- If `git status` reports a `.git/objects/pack/._*` warning, run `dot_clean
  .git` and recheck status before continuing.
- Reviewers should reject a package when `review/issues/*.json` includes
  AppleDouble sidecars that break `jq` or issue enumeration.

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

## Flat Mode Overlay False Synthesis

Failure: a function-space or mode-decomposition shot shows a target function
beside several basis/component curves, but the curves are flat overlays on the
same coordinate plane or manually shifted into another vertical band. The
screen appears to claim `f = sum c_n phi_n`, while the viewer cannot see that
the displayed components actually generate the displayed target.

Fix:

- Expose component functions in the mathematical driver and compute the target
  function from those same components.
- Do not manually shift components downward and present them as if they were in
  the same coordinate system as `f`.
- Use separated representations when needed: depth layers, small multiples,
  partial-sum animation, coefficient bars tied to basis functions, or an
  oblique projection that clearly distinguishes component layers from the base
  curve.
- If using a depth-layer display, record the projection as a display mapping in
  the scene contract and keep the formula `f = sum c_n phi_n` tied to the
  same driver.

## Fake Camera Rotation By Manual Projection

Failure: a shot asks for a real camera view change, but the code draws objects
in pre-skewed or manually projected coordinates while the Manim camera remains
static. The frame may look oblique, but the audience never sees the scene as a
true 3D mathematical object.

Fix:

- Use `ThreeDScene` or the appropriate camera scene when the visual contract
  calls for camera rotation.
- Build the mathematical object in real 3D coordinates from the start. If the
  opening view should look flat, hide or occlude the extra layers with the
  initial camera orientation instead of replacing the object later.
- Use `move_camera`, `set_camera_orientation`, or a declared camera frame move
  for the view change. Do not hand-project a 3D look into 2D coordinates.
- If the layout must stay fixed, a declared in-place rotation of the real 3D
  object group can replace camera motion; this is still a real 3D transform,
  not a manually projected 2D drawing.
- Keep screen text and formula boards fixed in frame when needed, but keep the
  active mathematical object inside the 3D world.
- Record the camera requirement in `contract.yaml` under
  `visual_reference.camera_motion` and include before/during/after camera
  frames in QC.

## Camera Motion Overemphasis

Failure: a camera move is technically real, but it becomes the visual spectacle
instead of quietly revealing a mathematical relation. This often happens when a
small 3D tilt would be enough to show depth, but the scene rotates so far that
the object, formulas, and stage hierarchy become secondary.

Fix:

- Choose the minimum camera movement that reveals the hidden relation.
- Keep the active mathematical object readable before, during, and after the
  camera move.
- If the teaching point is only "these objects are layered," use a small tilt,
  not a dramatic orbit.
- Record the intended camera amplitude in the scene contract and inspect
  before/during/after QC frames.

## Stage Recentered By Camera Reveal

Failure: a local 3D reveal uses camera `frame_center`, pan, or zoom to move the
active stage object toward screen center even though the object already has an
assigned layout zone. The viewer reads the motion as a layout reset, not as a
small reveal of hidden depth.

Fix:

- If the goal is only to reveal that a local object is layered, keep the camera
  frame fixed and rotate or tilt the 3D object group in place around a local
  anchor.
- Preserve the object's assigned stage zone before, during, and after the 3D
  reveal unless the scene contract explicitly declares a takeover or recenter.
- When dropping elevated layers after an in-place rotation, move them along the
  rotated local depth direction, not the screen's unrotated vertical or depth
  axis.
- Record this policy in `contract.yaml` under
  `visual_reference.camera_motion` and include before/during/after QC frames.

## Shared Driver But Visual Object Swap

Failure: two objects are generated from the same mathematical driver, but the
animation replaces one visible object with another in a way that viewers read
as a new object. This is common in 2D-to-3D reveals, local zooms, and
decomposition diagrams: the code may reuse `f(x)`, but the screen makes the
original function, point, region, or curve feel swapped.

Fix:

- Preserve the actual visible Mobject across the transition whenever possible:
  rotate, move, reparent, or restyle the original object instead of replacing
  it with a separately constructed twin.
- If a new Mobject is unavoidable, match coordinates, stroke, scale, and
  identity cues exactly, and make the transform visibly identity-preserving.
- For 2D-to-3D reveals, the initially visible base object should become the
  base layer of the 3D stage; upper layers may enter later.
- Add before/during/after QC frames for the transition, not just the settled
  start and final states.

## Incomplete 3D Layer Box

Failure: a basis-layer or mode-decomposition shot is described as a 3D object,
but the render only shows several skewed axes or curves. The object does not
have a readable cuboid-like layer-stack structure: corresponding layer
directions do not read as parallel, depth separation is missing or ambiguous,
and viewers cannot tell which plane is the base `f(x)` and which planes carry
the basis functions.

Fix:

- Build the layered object as one complete 3D stage: shared base footprint,
  upper parallel layer cues, and a consistent depth direction.
- Do not literalize the cuboid model as a visible enclosing border unless the
  border itself is a named mathematical object. Usually the cuboid should be a
  construction rule, while the visible evidence is layer separation, restrained
  axes or layer cues, curves, and labels.
- Opening view should show the base layer only when the narration introduces
  `f(x)`. Hidden upper layers must not leak into the initial flat view.
- Reveal the basis layers, then use a small in-place rotation or declared
  orthographic view change so the audience can see the layer separation.
- Do not draw multiple independent coordinate axes that can be mistaken for
  non-parallel sides of a broken 3D object. If layer axes are drawn, they must
  belong to the same cuboid geometry and preserve parallel directions. Do not
  default to drawing grids on every layer; that is a separate clutter failure
  unless the grid itself is the mathematical object being taught.
- In the contract, record whether the display is a true `ThreeDScene` object
  tilt or a declared no-perspective orthographic projection of a 3D model.
- QC must include opening, pre-rotation, during/post-rotation, and final
  frames. Reviewers should reject the scene if muting narration leaves the
  layer object visually ambiguous.

## Literal 3D Box Border Overcorrection

Failure: after a reviewer asks for a cuboid-like or layer-box object, the
animator draws a literal rectangular cage, outer border, or four depth edges
around the mathematical object. The border becomes an extra visual object and
can be read as a container, boundary condition, domain wall, or decorative
frame, even though the lesson only needs layer geometry.

Fix:

- Treat the cuboid as the coordinate model or spatial organization, not
  automatically as something to outline.
- Prefer borderless cues: separated curves, short layer axes when needed,
  consistent depth motion, labels attached to layers, and restrained opacity.
- If an outer border is mathematically necessary, name its role in the stage
  direction and keep it visually secondary.
- Review should reject visible box borders that exist only to make the 3D
  effect obvious.

## Layer Grid Clutter In 3D Basis Object

Failure: a stacked 3D basis, mode-decomposition, or layer object draws grid
lines on every layer. The repeated low-opacity guides visually dominate the
curves, create a noisy mesh, and make the depth relation less clear rather than
more clear. This is a `visual_hierarchy_failure` and an
`aesthetically_ugly_but_technically_correct` regression even if the underlying
curves are generated from the correct driver.

Fix:

- Default layer-stack objects to no grid. Use the mathematical curves, labels,
  depth separation, and at most restrained layer axes to show the structure.
- Draw a grid only when the grid itself is the mathematical object being
  taught, such as a coordinate transform or sampled domain. Record that role in
  stage direction and `contract.yaml`.
- During review, the ranked aesthetic/noise sweep must explicitly ask whether
  helper lines, axes, or grids are the noisiest visible element. If they are,
  remove or reduce them before pass.
- Reject a pardon that says "it helps show 3D" without explaining why a novice
  viewer needs the grid and why the curves remain the dominant object.

## Nonclassic Residue Contour Diagram

Failure: a contour-integral or residue-theorem shot invents an attractive
curve, local loop, or punctured neighborhood that does not match the canonical
diagram for the theorem being invoked. Viewers familiar with complex analysis
read it as wrong, and new viewers cannot learn the standard geometry.

Fix:

- Choose the textbook convention for the specific theorem: for residue-theorem
  real-integral work, use a real segment `[-R,R]`, an upper semicircle `C_R`,
  internal poles, and counterclockwise arrows; for keyhole/branch-cut work,
  use parallel paths above/below the cut, an outer arc, and an inner arc.
- Record the selected convention in `contract.yaml` under
  `visual_reference.classic_source`.
- Keep singularity markers local and small. Do not enlarge a local loop into a
  second main contour unless the proof explicitly uses that contour.

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

## Unowned Bow Shape Fill

Failure: a curved arrow, arc, or stroke becomes a gray bow-shaped patch or
filled sliver. Even when code intended a stroke, the rendered shape reads as a
filled region and viewers may interpret it as area, sweep, or density.

Fix:

- For arcs, curves, and arrows, set stroke and fill separately; fill opacity
  should be zero unless the filled region is the named mathematical object.
- Avoid opacity changes that re-enable fill on Manim curve-like objects.
- Add a close-up QC frame for any arc/curved arrow that passes near a formula
  or panel.
- Reject "it is only an arrow" if the rendered pixels look like a fill.

## Useless Connectors

Failure: dotted connector lines between diagram and side panel looked awkward or arbitrary.

Fix:

- Remove connectors unless they carry a necessary mapping relation.
- If a connector is needed, attach it to precise anchor points and keep opacity low.
- Prefer spatial grouping, color correspondence, or local labels over arbitrary dotted lines.

## Unowned Connector Spaghetti

Failure: multiple dashed or dotted connectors run from a diagram to formula
chips or coordinate slots, cross each other, and do not have named endpoints or
a one-to-one mathematical relation. The viewer cannot tell whether they are
sample correspondences, projections, dependencies, or decoration.

Fix:

- Remove the connector cluster unless each line has a declared source object,
  target object, and relation.
- Prefer one visible active correspondence at a time, or replace connectors
  with spatial grouping, color identity, or a transform from sample value to
  coordinate.
- In `contract.yaml`, record `connector_policy` and object-level connector
  endpoints when any connector survives.
- During review, mute the narration and ask what each line means. If the answer
  is not immediate, reject the scene.

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

Failure: a mathematical term has an unwanted pronunciation, such as IndexTTS2 reading `模长` as `mo zhang`. The same failure also includes one notation token being pronounced differently across repeated occurrences, while corrected subtitles hide the inconsistency; for example, raw `eta` may alternate between several sounds inside one substitution argument.

Fix:

- Use a TTS-only pronunciation spelling, such as `模常`, when it reliably produces the intended sound.
- Keep screen formulas, final subtitles, storyboard prose, and searchable math text correct as `模长`.
- Record the hack in `tts-speaking-rules.md` and the experiment log so later subtitle correction does not preserve the fake spelling.
- Map every occurrence of the same mathematical token to one fixed spoken form before synthesis; do not send a known-unstable raw Latin token repeatedly and hope the model stays consistent.
- Regenerate a complete semantic phrase or natural short paragraph instead of splicing an isolated syllable.
- Export one mandatory-ear asset containing every occurrence. ASR spelling and publication-text normalization are alignment evidence, not pronunciation evidence, and cannot close this gate.

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

## Reverse Burden Review Not Applied

Failure: a reviewer returns `pass` after listing only successful checks, even
though the scene is formula-dense, diagram-dense, or already contains human
feedback risks. The audit behaves as if a scene is acceptable until proven
wrong, so ambiguous connectors, text fallback, overboxing, formula-only slides,
and premature clearing survive.

Fix:

- Start every strict review from `revise`.
- Write a red-flag ledger before the verdict, following
  `43-review-red-flag-rubric.md`.
- Include concrete negative examples in subagent prompts. A subagent must be
  told what prior bad frames looked like, not only broad philosophy.
- Require at least six candidate red flags for formula-dense or
  previously human-rejected scenes. Candidates may later be fixed, pardoned, or
  marked not applicable, but zero-candidate pass reports are invalid.
- One unpardoned candidate remains enough to reject the scene.

## Script Feedback Not Converted To TTS Regression Gate

Failure: the user flags narration problems such as imprecise mathematical
wording, AI-sounding creator-intent sentences, wrong "lesson" terminology,
overexplaining what the animation can show, or pronunciation trouble, but the
finding remains only in chat. The next script revision or TTS pass can repeat
the same problem, and the error becomes expensive after audio, SRT, alignment,
and `timeline.json` are generated.

Fix:

- Record reusable script feedback in `review/human-feedback/` and
  `review/issues/*.json` with `applies_to_script_authoring: true`.
- Add `script_lint_rule` or update the episode-local `scripts/lint_tts_script.py`
  when the wording can be detected by regex or structural checks.
- Before TTS synthesis, run the script-authoring preflight, local lint, and TTS
  plan pass. Do not proceed if applicable human-review script issues are still
  unconsumed.
- Promote recurring wording failures to `12-script-authoring-feedback-loop.md`
  or this file so future episodes do not need to rediscover them.

## Script Route-Plan Overexternalization

Failure: the narration explains the producer's future course sequencing instead
of giving the viewer a concise mathematical preview. Sentences such as
`但不会在下个视频马上跳过去` or `先把傅里叶这条线走完整` expose internal route
management. They sound like planning notes, not teaching.

Fix:

- Keep next-video previews short and mathematical.
- Say what object or question comes next, not how the producer intends to
  sequence the syllabus.
- Avoid long future-video route paragraphs at the end of a script unless the
  current concept mathematically requires the map.
- If a route boundary is needed, compress it into one viewer-facing sentence.
- Before TTS, reviewers must list route-plan overexternalization as a candidate
  finding for episode endings and either fix it or pardon it with evidence.

## Imprecise Mathematical Subject In Narration

Failure: narration assigns explanatory responsibility to the wrong object. For
example, an expansion is said to "answer" a coefficient question when it only
represents the function, or a transform is said to "explain" a formula when the
actual reason is projection, orthogonality, a basis theorem, or a boundary
condition.

Fix:

- Audit core sentences by subject and verb before TTS.
- Use representational verbs such as "writes", "shows", "is read as", or "has
  coordinates" when the object is only a form of expression.
- Reserve causal verbs such as "explains", "comes from", or "is why" for the
  mathematical object that actually supplies the reason.
- Add lint checks for known bad phrasings when they recur in an episode.

## Narrated Visual Obviousness

Failure: narration spends several sentences describing what the viewer can
already see, such as partial sums looking rough, closer, or more linear, while
the conceptual point is left thin.

Fix:

- Let the animation show curve shape, motion, and visual comparison.
- Use narration for the invariant: which coefficients drive the construction,
  what object is being reconstructed, why the inverse/synthesis step works, or
  where the rigorous proof will live.
- During script review, mute the draft visuals mentally: if a sentence only
  narrates obvious frame appearance, compress or remove it.

## Discrete Series Frequencies Confused With Continuous Transform Frequencies

Failure: a Fourier-series example uses integer modes such as `sin nx`, then
the narration speaks as if Fourier transform frequencies are also only a
discrete list. Viewers miss the transition from a coefficient sequence to a
continuous spectrum.

Fix:

- State the boundary: Fourier series has discrete frequency indices for
  periodic functions; Fourier transform uses a continuous frequency variable.
- Tie the inverse step to the same distinction: series reconstruction uses a
  sum; transform inversion uses an integral over frequencies.
- When mentioning pure frequencies, note that ideal pure complex exponentials
  become delta spikes in the continuous spectrum, with real sine/cosine split
  across positive and negative frequencies.

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

## Aesthetic Objection Under-Enumeration

Failure: the reviewer only asks whether listed red-line failures are present.
If no single issue is obvious enough, the review passes without naming the
ugliest held frames, unclear visual-guidance moments, weak composition, or
near-miss regressions. This creates a "not guilty until proven" audit style and
lets mediocre frames reach the user.

Fix:

- Use `tools/review_gate.py` for every animation review. The reviewer must
  submit the current risk tier's minimum candidate red flags and ranked
  aesthetic/visual-guidance objections before the review can be accepted.
- The first ranked objections should include the worst-looking frame, the
  second worst-looking frame or transition, and the least clear visual-guidance
  moment, even if the reviewer expects to pardon them.
- A pardoned objection still needs evidence and a reason. "Looks acceptable"
  is not enough; explain why it does not harm novice comprehension,
  mathematical identity, or professional visual hierarchy.
- After user feedback identifies an aesthetic miss, turn it into
  `human_review` issue JSON and make future review tiers at least
  `human-rejected` for comparable scenes until the pattern stops recurring.

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

## Latex Fallback Math Text

Failure: mathematical labels that require subscripts, superscripts, hats, Greek
letters, angle brackets, or fractions are rendered as plain text, such as
`c_1` or `c_2`, instead of real mathematical typography. The frame looks
unfinished and weakens symbol recognition.

Fix:

- Render concept-bearing math tokens with `MathTex` or an equivalent math
  renderer.
- Do not use plain `Text` for coefficient labels, basis labels, hats,
  inner-products, or transform symbols.
- Add a QC check for fallback underscores, caret notation, and raw ASCII math
  in labels and chips.

## Unlabeled Major Formula Stack

Failure: several major formula families appear together, such as Fourier
series, coefficient formula, Fourier transform, and inverse transform, but the
scene does not label which formula is which. Instead, a caption or producer
critique is placed nearby, leaving the actual mathematical roles unnamed.

Fix:

- Label each major formula by role with short object labels such as `级数展开`,
  `系数`, `变换`, `逆变换`.
- Remove captions that describe the creator's critique when they do not label
  a mathematical object.
- If there are more than three major formulas, group them as a comparison table
  with role labels, not as a raw formula wall.

## AI-ish Emotional Summary Slate

Failure: a scene ends by writing the intended feeling or critique as a large
summary slate, such as "after doing the problem, it is empty," instead of
letting the existing mathematical or procedural visual state carry that
feeling. The result reads like an author note exposed on screen rather than
professional visual narration.

Fix:

- Prefer extending or lightly modulating the current mathematical/procedural
  frame when it can already carry the emotion.
- Remove written emotional conclusions that merely describe the intended
  audience reaction.
- If a final text cue is necessary, make it a label for an object or state, not
  a sentence explaining the design intent.
- During QC, mute the narration and ask whether the frame still feels like a
  designed visual consequence rather than a captioned explanation.

## Overexplicit Critique Title

Failure: a shot starts by writing the producer's critique as a headline, such
as "what did school teaching actually teach," before the mathematical objects
have made the point. This makes the design intent visible as text instead of
letting staging, timing, and object relations carry the complaint.

Fix:

- Prefer beginning with the objects, routines, or terms being criticized.
- Use titles only when they label a necessary section or object state.
- If a title only restates what the narration already says or what the visual
  can show, remove it.
- During QC, inspect early frames muted. If the frame reads as a captioned
  opinion rather than a staged visual relation, revise.

## Critique Stamp Dwell Too Short

Failure: a short critique stamp, rhythm marker, or warning label flashes too
quickly to read at normal playback speed. The object may be present in code,
but the viewer misses the beat.

Fix:

- Give short stamps enough dwell time after entrance, especially when they
  carry a narration beat.
- Avoid `there_and_back` or bounce-only entrances for labels that must be read.
- Extract a QC frame after the entrance settles and another later in the same
  beat to prove readability.

## Unowned Long Connector Line

Failure: a horizontal, vertical, or diagonal line runs behind or through nodes,
formula chips, or labels as a decorative baseline. The real relationship may
already be expressed by arrows, but the extra line remains visible and reads as
an accidental axis, conveyor, or artifact.

Fix:

- Use edge-to-edge arrows for directed relationships.
- Split connector shafts around intervening objects or remove them entirely.
- Do not draw a through-line unless it is a named mathematical object such as
  an axis, number line, contour, or timeline.
- In `contract.yaml`, mark connector-heavy objects with a connector policy,
  such as forbidding background baselines.

## Frame Overuse Formula Chips

Failure: ordinary short formulas or labels are all placed in rounded boxes, so
frames stop communicating conclusion, contrast, or derivation hierarchy. The
scene looks like a generic UI rather than blackboard mathematics.

Fix:

- Default setup formulas, coordinate labels, route labels, and intermediate
  algebra to bare `MathTex`.
- Use frames only for conclusions, active focus, grouped derivations, contrast
  structures, or warnings.
- If a formula object uses a frame, record its `frame_role` in stage direction
  or `contract.yaml`.
- During QC, count framed formulas in each beat. If most formulas are framed
  and no hierarchy is visible, revise.

## Overboxed Formula Row Blocks Reading

Failure: an algebraic row is broken into many framed chips. The boxes become
the dominant visual object, interrupt one-line reading, and make ordinary
terms look like UI buttons rather than algebra.

Fix:

- Keep ordinary terms in bare `MathTex`; use spacing, color, or temporary
  opacity to focus active terms.
- Frame only a true conclusion, contrast group, warning, or derivation
  container.
- If term grouping is needed, use subtle alignment or braces instead of one
  rounded rectangle per term.
- Reject rows where the frame count is higher than the number of actual
  hierarchy roles.

## Premature Derivation Clear With Space Available

Failure: a derivation formula or proof step appears briefly and disappears
while the frame still has enough unused space to keep it visible. Viewers lose
the ability to compare numerator, denominator, assumptions, and conclusion.

Fix:

- Keep a derivation step visible until the dependent step has landed and the
  viewer has had time to compare them.
- Use the available side or lower lane for persistent derivation memory.
- Clear formulas early only when a new active object needs the space, and
  record that reason in stage direction.
- Include QC frames at the moment just before clearing and after the next
  formula lands.

## Single Slot Formula Replacement Loses Derivation Memory

Failure: a derivation uses one formula slot and repeatedly replaces the entire
line, even though the frame has enough room to retain earlier steps. Each
individual formula is readable, but the viewer cannot compare definitions,
substitutions, and conclusions.

Concrete regression: episode 0004 G002B v06 replaced the projection coefficient,
the definition of `F(omega_n)`, the `1/L` relation, and the `Delta omega/(2pi)`
relation in one upper-right slot.

Fix:

- Build a progressive formula shelf: add dependent lines and retain predecessors
  at lower emphasis until the comparison is complete.
- Use token color or a short indication for the active substitution instead of
  deleting the derivation memory.
- Record persistent formula ids and a comparison window in contract version 4.
- Keep the mathematical process primary; persistence is not permission to fill
  the whole screen with formulas.

## Complex Accumulator Without Vector Semantics

Failure: a complex projection or oscillatory sum is drawn as a cumulative path,
but the viewer cannot see the individual complex contributions, head-to-tail
addition, real/imaginary directions, traversal order, or endpoint meaning. The
path is computed correctly yet reads as decorative motion.

Concrete regression: episode 0004 G002B v06 showed a pink scalloped cumulative
path under `sum_j f(x_j)e^{-i omega_n x_j} Delta x`; human review could not tell
what the path meant.

Fix:

- Show several contribution vectors as arrows added head-to-tail, driven by the
  same sample computation as the projection sum.
- Label the real and imaginary directions and identify the active sample.
- Carry the final endpoint into the spectrum marker and label it
  `F(omega_n)`.
- Use a novice-comprehension checkpoint: with narration muted, the viewer must
  be able to identify one contribution, the running sum, and the endpoint's
  mathematical role.

## Formula Only Scene Without Visual Causality

Failure: an entire scene is algebraic manipulation even though the segment is
supposed to teach a visual idea such as projection, basis expansion,
orthogonality, coefficient extraction, reconstruction, or time/frequency
relation. A viewer who does not already know the concept cannot infer the
causal relation from symbols alone.

Fix:

- Add a visible mathematical object or process: vector projection, basis
  direction, sampled function, component product, cancellation, coefficient
  bar, spectrum point, or reconstruction curve.
- If a scene is intentionally a derivation page, label it as
  `derivation_page` in the contract and explain why no diagram is needed.
- For novice-facing explanation, formulas must be connected by motion,
  token-level transforms, or aligned visual evidence, not just by appearing in
  sequence.

## PPT-Like Static Derivation Without Visual Causality

Failure: a lecture-animation scene contains correct formulas, a graph, and
timed formula reveals, but the mathematical work is still done almost entirely
by narration. The held frames look like slides: objects do not change enough,
the viewer cannot see why a coefficient, limit, or reconstruction step follows,
and the formula board becomes the lesson instead of evidence for the lesson.

Concrete regression: episode 0004 G001-G005 first review was rejected by human
review on 2026-07-09 because it felt like "PPT": the voice explained Fourier
transform while the screen mostly held formulas and static curves. The prior
subagent pass missed the novice-viewer standard.

Fix:

- Treat this as a blocker, not a taste note.
- For every spoken operation, name the visible mathematical object that changes
  at that beat: sample value, coefficient bar, basis direction, frequency bin,
  product density, cancellation, delta proxy, or reconstruction curve.
- Reduce formulas to labels, consequences, or short active anchors. A large
  formula wall cannot be the main visual driver for projection, limiting sums,
  or reconstruction.
- Mute the narration and inspect the scene. If a novice cannot infer the
  operation from motion and object relationships, redesign before polishing.
- After a human rejection of this pattern, use a `human-rejected` or stricter
  review tier and require the reviewer to explicitly audit
  `visualization_adequacy` and `novice_viewer_causality`.

## Riemann Sum Named But Not Visualized

Failure: narration says that a sum becomes an integral or refers to a Riemann
sum, but the screen only shows the symbolic sum and integral. The frequency
points, bin widths, weighted terms, rectangles/bars, or densification process
are not visible.

Concrete regression: episode 0004 G002 was rejected by human review on
2026-07-09 because the around-three-minute Riemann-sum beat was not visualized;
the frame showed the formula stack instead of a discrete-to-continuous
construction.

Fix:

- Use the same driver for frequency samples and `Delta omega`.
- Show sparse frequency samples first, then bins or bars of width
  `Delta omega`.
- Attach each bar or term to the quantity being summed, such as
  `(Delta omega / 2pi) F(omega_n) e^{i omega_n x}`.
- Increase sample density monotonically and visibly. Include at least one
  intermediate density before the integral appears.
- Let the integral sign enter as the consequence of the refined bars/area or
  density envelope, not as a disconnected formula reveal.
- QC frames must include sparse bins, intermediate bins, dense bins, and the
  final integral state.

## Batched Multi-Scene Review Masks Scene Failures

Failure: several scene groups are concatenated into one primary review clip,
and the user is asked to approve the batch. This hides scene-level failures,
especially when one scene has a layout or visualization blocker that requires
frame-by-frame critique.

Concrete regression: episode 0004 G001-G005 was handed off as one combined
review package and rejected by human review on 2026-07-09. The user asked to
review the scenes one by one instead.

Fix:

- The primary review artifact should be one scene/scene group at a time.
- Combined review clips are allowed only as a secondary continuity check after
  individual scenes pass.
- `review/assignments.md` and `timeline.json` should keep per-scene status.
- After a user rejects a batch, reset affected scene statuses to
  `human_rejected_revision_required` and reopen individual review gates.

## Missing Classic Textbook Diagram Reference

Failure: a canonical mathematical object is drawn from scratch with arbitrary
geometry when a well-known textbook convention already exists. The diagram may
be mathematically related but fails the visual language of the subject, such as
showing a pole neighborhood as a large smooth ellipse instead of a small
punctured loop around the singularity.

Fix:

- For canonical objects, consult classic textbook diagrams before inventing a
  composition.
- Record the adopted convention in stage direction, `contract.yaml`, or the
  experiment log.
- Keep pedagogical distortion honest: if an infinitesimal loop is enlarged for
  visibility, make it small relative to the main contour and use labels such as
  `C_\epsilon` or `z_0` instead of vague explanatory text.

## Long Unrelated Formula Text Overlap

Failure: outgoing and incoming formulas or text occupy the same slot long
enough that the frame contains two readable unrelated messages. A brief overlap
may be acceptable during a transform, but the held transition looks broken.

Fix:

- For unrelated objects, clear the old object before entering the new one.
- If a cross-fade is used, keep the overlap short and record the overlap limit
  in stage direction or `contract.yaml`.
- QC frames must include the transition interval, not just settled states.

## Aggregate Formula Lane Hides Internal Collision

Failure: a scene-specific layout audit registers several formulas or live value
rows as one `VGroup`. The checker sees only the outer group bounds, so children
can overlap one another while the audit reports `pass`.

Concrete regression: episode 0004 G002A and G002C v06 passed their layout audit,
but human review found overlapping live values in G002A and overlapping
forward/inverse integral limits in G002C.

Fix:

- Register every major formula or value row that can coexist as a separate
  temporal audit element.
- Give each element its real visibility range; do not use one broad formula-lane
  range as a substitute.
- Contract version 4 scenes must declare `audit.atomic_formula_elements` and
  pass the same ids to the scene audit adapter.
- Reject any audit JSON that lacks the atomic formula ids or reports overlap or
  close findings among them.

## Overexternalized Process Text

Failure: screen text states the designer's intent, such as "sampling values
become coordinates," instead of letting sample points, vectors, formulas, and
motion communicate the relation.

Fix:

- Replace intent sentences with object labels, formulas, arrows, or actual
  transforms.
- If removing the text leaves the scene understandable with narration and math
  objects, remove it.
- Keep text that names an object or state; remove text that explains what the
  viewer is supposed to feel or infer.

## Externalized Creator Critique Caption

Failure: the screen displays the producer's critique of a teaching style, such
as saying a formula route can compute but feels like a pile of integrals. The
line exposes the author's intention instead of making the mathematical contrast
visible through labels, grouping, or staging.

Fix:

- Replace critique captions with mathematical role labels, object labels, or
  short viewer-facing questions.
- If the narration already says the critique, the screen should show the
  formulas and their roles, not repeat the evaluation.
- During QC, ask whether the caption describes the screen object or describes
  the creator's opinion. The latter is a blocker.

## Unnatural Screen Heading From Production Shorthand

Failure: a screen heading uses an internal authoring label or prompt shorthand,
such as `公式角色`, instead of natural viewer-facing Chinese. The label may be
technically related to the layout, but it sounds like a production note rather
than a title a teacher would write on the board.

Fix:

- Name the visible object or mathematical state in ordinary language, such as
  `公式表` for a table of formulas.
- Put precise mathematical roles in local row labels, object labels, or formula
  annotations rather than overloading the section title.
- During script and visual review, read every screen title aloud. If it sounds
  like a prompt label, storyboard note, or internal design role, revise before
  render.

## Vector Column Over Active Graph

Failure: a vector or matrix column is placed on top of an active function
graph, grid, or curve. Even if there is no formal bbox overlap failure, the
column obstructs the main mathematical object and looks like a pasted panel.

Fix:

- Reserve a formula/vector lane outside the protected active graph region.
- If a vector must relate to a graph, connect it through sample points or a
  local callout without covering the curve.
- A bracketed vector already has a container; avoid adding an extra panel frame
  unless the vector is a conclusion or grouped derivation.

## Complex Scale Rotate Motion Missing

Failure: complex multiplication is described as scaling and rotation, but the
render shows only static before/after vectors or formula chips.

Fix:

- Use one driver with `z` and `w=\rho e^{i\theta}`.
- Animate the endpoint through `\rho^\alpha e^{i\alpha\theta}z` so the viewer
  sees rotation and stretch as one operation.
- Keep labels, arc, and final vector synchronized to the same driver.

## Coarse Timeline Visual Alignment

Failure: the review MP4 has the correct total duration, but narration and visual actions are only loosely related. Several spoken ideas are covered by one broad visual phase, so viewers cannot tell which object or operation the voice is referring to.

Concrete regression: episode 0003 G007 `s013_s016_complex_exponential_fourier_coefficients`
was rejected in user review on 2026-07-06 because the voice had already moved to
later coefficient and inverse-basis concepts while the animation still showed
earlier complex-exponential evidence. A review pass that only checked scene
duration or broad SRT cues would miss this; the reviewer must compare word/token
anchors against exact visual trigger times.

Fix:

- Audit at narration-beat granularity, using `timeline.json`, SRT/alignment, and the review MP4 together.
- For each spoken concept, record the timestamp where the corresponding visual object enters, changes, or receives focus.
- Add visual beats, pauses, highlights, or transitions until the viewer can track the explanation without rereading the script.
- Total duration match is not an acceptance criterion by itself.

## Subtitle Math Homophone Drift

Failure: SRT or alignment text silently changes a concept-bearing mathematical
phrase into a plausible homophone or near-homophone. The script and timeline may
be correct, but the subtitle contract shown to reviewers or used for final
packaging says a different concept, such as `普通线代里` becoming `普通现代里`.

Fix:

- Compare concept-bearing subtitle cues against `script.md` and `timeline.json`
  before final handoff.
- Search for likely ASR substitutions around course vocabulary, abbreviations,
  person names, and mathematical terms.
- Correct both SRT and alignment JSON when the same cue text appears in both.
- Treat subtitle math transcription errors as review blockers even when the
  review MP4 visuals, audio, and layout audits pass.

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

Concrete regression: episode 0003 G008 `s017_analysis_and_synthesis` was flagged
in user review on 2026-07-06 for weak overall layout even though the diagram's
objects were mathematically plausible. Review must rank the ugliest or least
clear held states and cannot pardon a compact summary scene merely because all
labels and formulas fit.

Fix:

- Treat obvious ugliness as a review failure, not a preference note.
- Check spacing, alignment, padding, rhythm, color restraint, and full-frame composition at every held state.
- If a user has already flagged a comparable aesthetic failure, encode it as a human-review regression issue and block repeats.

## Final Candidate Missing Required BGM Mix

Failure: a final review or upload candidate is remuxed after TTS, subtitle, or
timing repair and silently loses the approved BGM layer. The voice track may be
correct, but the episode no longer matches the series audio style or an
explicit user instruction to use the same BGM and voice/BGM configuration as a
previous episode.

Fix:

- Treat BGM as part of the final output contract whenever the user has approved
  or requested a recipe.
- After any audio timing repair, subtitle correction, video retime, or final
  remux, explicitly check whether the final candidate includes the required
  BGM layer.
- Reuse the recorded mix recipe instead of approximating it from memory. For
  episode 0002 after user review on 2026-07-04, the required recipe is the
  episode-1 BGM `assets/bgm/埃里克萨蒂-玄秘曲.mp4`, `base_volume=4.8`,
  `sidechaincompress threshold=0.025 ratio=8 attack=80 release=900`, and
  final `loudnorm I=-17.0:TP=-1.5:LRA=11.0`, unless the user updates it.
- Validate the final upload/review MP4, not only an intermediate mixed WAV.
  Record `ffprobe` and loudness/true-peak evidence in the experiment log.

## Final Identity Cue Missing Sumino Sprite

Failure: the fixed series sign-off reaches final assembly without Sumino being
visible when the narrator identifies herself as the keyboard player. A sprite
may be absent, appear only after the identity phrase, or be placed from a rough
scene-tail estimate rather than the word-level cue. Another form adds an
invented on-screen `Sumino` name even though the spoken line contains only the
identity phrase.

Fix:

- Resolve the first identity word and last farewell word from word/token
  alignment, not reader-cue or scene-tail estimates.
- Reuse the latest approved Sumino action, asset family, frame rate, fades,
  scale, and side placement from the live series precedent.
- Make Sumino visible no later than the first identity word and hold through
  the farewell. Do not invent name text when the narration does not say it.
- Prove before/on/after frames from the final subtitle-burned master, including
  subtitle, formula, active-diagram, and terminal-hold clearance.
- Bind the asset, overlay, word anchors, final MP4, and QC hashes in the final
  assembly manifest. A scene-local sprite preview does not prove the final mux.

## Final Master Reuses Preview Quality

Failure: a 720p or 1080p review/preview artifact is treated as the final master
after the scene has passed user review. This is especially visible in lecture
videos because thin formula strokes, small labels, graph grids, and chalk
texture benefit from a higher-resolution final render.

Fix:

- Separate preview/review quality from final master/upload quality in the
  output plan.
- If the user requests high final clarity, render or stitch final source
  segments at a higher resolution than previews. For a 4K final, use true
  3840x2160 source renders, normally `2160p30` for this course.
- Do not label a simple upscale of a 720p/1080p review file as a true 4K
  master unless it is explicitly documented as an upscaled delivery workaround.
- Verify final resolution, fps, codec, and audio streams with `ffprobe`, and
  record the render/stitch commands in the experiment log.

## Reader SRT Used As Animation Timing Contract

Failure: animation timing is aligned to reader-friendly SRT cue boundaries.
The final subtitles may be readable, but the cue granularity is too coarse for
formula reveals, object focus, scene transitions, and speech-synchronous
movement. Total duration can match while individual words or concepts land
early or late.

Fix:

- Generate separate products from ASR/alignment: reader SRT for viewers, and
  word/token alignment for timeline and animation.
- Use `qwen-srt --json-output` plus `--word-srt-output` and
  `--phrase-srt-output` when building or repairing a lecture-animation
  timeline.
- Drive animation timing from `aligned_tokens`, `token_gaps`, or explicit
  phrase/word timing, not from the final reader SRT cue split.
- Keep final SRT/VTT subtitles at readable `subtitle` granularity so viewers
  do not have to read one word at a time.
- During review, audit at narration-beat granularity: each spoken concept must
  have a visible object, focus change, or transition at the same time.

## Unedited TTS Breaths And Sentence Gaps

Failure: a TTS track is accepted because the text is correct and the duration
fits, but breaths, sentence gaps, or pauses sound unnatural. If the animation
then follows this raw timing, visuals either wait through dead air or rush
through the next concept.

Fix:

- Inspect the waveform together with word/token alignment before locking
  timeline timing.
- Use `token_gaps` or equivalent alignment evidence to find too-long,
  too-short, or badly placed pauses.
- Cut, shorten, extend, or resynthesize affected breath/gap windows without
  clipping syllables.
- Regenerate SRT/alignment after the edit; never keep a timeline built from
  pre-edit timings.

## Abrupt Scene Clear And Slow Default Fade In

Failure: one storyboard or scene group disappears abruptly, then the next
scene's objects slowly glow or fade in without a declared reason. Text and
formula fades are allowed, but slow default entrances make ordinary objects
look overemphasized and make the episode feel sluggish.

Fix:

- Give each scene boundary explicit outgoing ownership, clear-out timing,
  incoming ownership, and transition intent in `timeline.json`, stage
  direction, or the scene contract.
- Use object-preserving transforms when the new shot continues the same
  mathematical object. For unrelated shots, clear first, then enter.
- Keep ordinary text/formula entrances brisk unless the stage direction assigns
  a special emphasis, reveal, or suspense role.
- Include before/during/after transition QC frames for every repaired group
  boundary. Do not pass a full-episode review by checking only settled frames.

## Novice Support Replaced By Explanatory Screen Text

Failure: a scene is rejected as hard for beginners, so the repair adds headings,
prose labels, and verbal conclusions already present in narration. The screen
becomes a written explanation instead of making the mathematical cause visible.
This also changes the approved predecessor's text density while pretending the
change is only a motion repair.

Fix:

- Treat novice causal ledgers as backend review evidence, never as screen copy.
- Freeze the predecessor's exact on-screen text inventory before repair and
  require an exact machine comparison before review can be frozen.
- Improve the learner's path with object identity, motion, recomputation,
  comparison, settling time, and attention transfer rather than prose growth.
- Automatically audit descendant text objects; manual atom registration cannot
  be the only way a collision becomes visible to the gate.
## Detached dependent label

- `pattern_key`: `detached_label_not_bound_to_carrier`
- Failure: a point, marker, or graph moves while its identifying label remains at an old or decorative location.
- Hard prevention: bind both objects through a shared updater and export sampled carrier-dependent distances; any sample beyond the scene threshold blocks authoring QC.
- Review test: scrub the complete motion and verify that the label never appears to name empty space or a different object.

## Animation compressed instead of editing narration timing

- `pattern_key`: `animation_compressed_instead_of_audio_pacing_edit`
- Failure: several necessary mathematical states are forced into a short clause even though the audio can be cut at phrase boundaries.
- Hard prevention: insert pauses in the production full audio, shift reader/word/phrase subtitles and alignment JSON, rebuild `timeline.json`, and propagate downstream scene offsets before rendering.
- Review test: with audio muted, the operation, intermediate evidence, and result must each have a stable pointing frame.
## Group center used for a point target

- `pattern_key`: `group_center_used_for_point_target`
- Failure: after a label or brace is added to a group, moving the group center to a mathematical coordinate leaves the actual point offset from the axis or target value.
- Hard prevention: animate the mathematical point itself, let dependents follow through identity bindings, and export coordinate-map error checks for every claimed endpoint.
- Review test: inspect the point center numerically and visually at initial, equality, and mismatch states; group proximity is not evidence of coordinate correctness.

## Boundary clause consumed by both adjacent scenes

- `pattern_key`: `boundary_exact_clause_consumed_twice`
- Failure: the handoff contract records an outgoing owner and an incoming owner, but the same complete sentence is synthesized at the end of one scene and again at the start of the next. Written ownership metadata looks valid while the assembled episode repeats itself.
- Hard prevention: assign each complete normalized boundary clause to exactly one audio asset. Run an adjacent-script suffix/prefix uniqueness check on the assembled scene order before TTS locking and again before final stitching.
- Review test: listen across every cut without looking at scene files. The next scene must continue the action or answer the question instead of restating the complete handoff.

## Mode jargon appears before the invariant behavior

- `pattern_key`: `mode_jargon_before_concrete_novice_definition`
- Failure: narration starts sorting objects into “modes” or “natural modes” before a novice has seen what stays identifiable, what changes, and why the split helps. Later formulas may be correct, but the word has no usable mental model.
- Hard prevention: first show a direction or shape evolving without mixing, then name that stable identity a mode. Show the payoff by contrasting coupled original coordinates with independent scalar coordinates.
- Review test: mute every occurrence of the word “mode” and ask whether the motion alone shows one identifiable direction or shape surviving the operator. If not, the definition is still verbal rather than causal.

## Discrete frequency sum jumps directly to an integral

- `pattern_key`: `discrete_modes_to_continuous_integral_bridge_missing`
- Failure: a finite set of frequency components is followed by an inverse-transform integral with no visible reason for the measure factor or for the index becoming continuous.
- Hard prevention: show discrete samples, give each sample a width such as `Delta omega`, form the weighted sum, include at least one intermediate denser grid, and only then settle into the integral. Narration must distinguish the discrete/periodic example from the whole-line continuum.
- Review test: a novice should be able to point to where `Delta omega` came from and what becomes dense before the integral symbol appears.

## Final summary becomes a connector graph

- `pattern_key`: `final_summary_connector_spaghetti`
- Failure: a synthesis frame tries to preserve every earlier object and connect them with long, crossing, returning, or many-to-many arrows. The relationships may be logically defensible but the composition has no readable order.
- Hard prevention: reduce the synthesis to one ordered rail or one transformation sequence. Activate at most one primary direction connector at a time; use spatial alignment, object transforms, and inherited semantic color before adding arrows.
- Review test: inspect the held final frame as a still image. Its reading order must be obvious without tracing a crossing or return arc, and each connector must have exactly one unambiguous source and target.

## Generic narration lint blocks an exact series ending

- `pattern_key`: `fixed_series_ending_blocked_by_generic_route_language_linter`
- Failure: a broad ban on route-planning phrases also rejects a human-required viewer-facing preview or fixed series signature, tempting the author either to remove the approved ending or disable the safety check globally.
- Hard prevention: keep the generic ban as the default and add only a scene-bound exact allowlist. Validate the exact final-unit text, order, count, and scene prefix; reject all additional occurrences.
- Review test: the ordinary linter invocation must still fail on the preview phrase, while the explicit scene-ending mode passes only the locked preview and signature and fails altered or extra wording.

## Final media is not bound to the current scene contract

- `pattern_key`: `final_media_not_bound_to_current_scene_contract`
- Failure: a repaired MP4 or audio file is delivered after the narration QC, scene-production record, registry, or review manifest was sealed. Each artifact can look locally valid while the review packet actually describes an older candidate.
- Hard prevention: after any source, audio, alignment, subtitle, timeline, or render change, rebuild the complete scene-local hash chain and bind one exact final MP4. Run manifest verification against that exact candidate before independent review.
- Review test: independently hash the delivered MP4 and audio, then trace those hashes through narration QC, scene production, registry, formula/text/layout evidence, and the review manifest. Any stale link blocks review.

## Screen-text audit is detached from the delivered MP4

- `pattern_key`: `screen_text_audit_final_mp4_mismatch`
- Failure: source search or a text inventory claims explanatory prose was removed, but the delivered MP4 still contains it because the audit inspected a different render or an incomplete object registry.
- Hard prevention: bind the screen-text audit to the current source hash and final MP4 hash. Re-extract regression frames from that exact MP4 after every render, including text created through groups, transforms, or helper functions.

### Frozen video was not produced by the bound source

- `standard_key`: `review_candidate_must_be_real_render_of_bound_source`
- `pattern_key`: `frozen_video_not_produced_by_bound_source`
- Failure: a manifest independently hashes current source and an older MP4,
  while regenerated telemetry, contact sheets, and source-only text inventory
  make the package look current. Decoded video omits actions present in source
  or contains screen text absent from source.
- Hard prevention: render into a fresh media directory and seal a render
  receipt binding source hash, complete command, tool versions, real runtime
  telemetry hash, and output MP4 hash. Require `reused_media=false`. Compare
  decoded non-subtitle video text and key visible actions back to the bound
  source before author self-review. Independent source and MP4 hashes without
  this production link are insufficient.
- Review test: compare the declared inventory with independently extracted final-video frames at every prior text-density hotspot. Visible undeclared prose is an automatic failure.

## Formula transition leaves a ghost overlap

- `pattern_key`: `formula_transition_ghost_overlap`
- Failure: an old formula and its replacement coexist during a transform or fade, producing doubled glyphs or differently colored copies precisely when the mathematical result should settle.
- Hard prevention: declare formula ownership at transition midpoints, clear or transform the outgoing formula before the replacement becomes opaque, and include transition-midpoint frames in a scene-specific overlap audit.
- Review test: inspect before, midpoint, and after frames for every formula replacement. A novice must see exactly one readable mathematical claim at each held state.

## Required formula manifest is missing

- `pattern_key`: `required_formula_manifest_missing`
- Failure: a formula-dense scene reaches review without a scene-local manifest recording formula identity, visible windows, transforms, and the claims each formula supports.
- Hard prevention: generate one formula manifest for every independently reviewed formula-dense scene, bind it into the review manifest, and regenerate it whenever formula source or timing changes.
- Review test: select each narrated mathematical claim and trace it to an exact formula object and visible time window. If the mapping depends on reading source code or memory, the output contract is incomplete.

## Frame-analysis telemetry is only a manual pass assertion

- `pattern_key`: `frame_analysis_telemetry_is_manual_pass_assertion`
- Failure: runtime evidence reports layout, cue, or novice-causality checks as passed even though it contains only container metadata, copied plan values, or hard-coded booleans rather than measurements derived from the delivered frames.
- Hard prevention: bind telemetry to the final MP4 hash and export reproducible frame-derived measurements or scene-runtime events for every claimed check. A missing measurement must remain unknown or failed; it cannot be promoted to pass by an author assertion.
- Review test: independently rerun the evidence command against the delivered MP4 and confirm that the reported bounds, object windows, semantic events, and cue checks can be reproduced without reading the author's verdict.

## Fresh candidate lacks a fresh author self-review chain

- `pattern_key`: `fresh_manifest_without_fresh_author_self_review`
- Failure: a candidate is re-frozen after policy, source, timing, or media changes, but its author self-review, probe, capsule, or submission still describes an older manifest hash.
- Hard prevention: treat every new review manifest as a new immutable candidate. Regenerate the author probe, self-review, capsule, and submission after freezing, and require every record to bind the same manifest and media hashes before independent review starts.
- Review test: begin at the delivered manifest hash and trace it through all author-review records. Any older hash, missing link, or post-review mutation blocks the candidate.

## Screen-text repair freezes the rejected text instead of reducing it

- `pattern_key`: `screen_text_repeats_narration_or_explains_intent`
- Failure: a human asks for less explanatory text, but the repair merely inventories or freezes the existing title, full-sentence prompt, and synonymous instruction while leaving them visible together.
- Hard prevention: compare the rejected and repaired on-screen text inventories, remove narration-redundant prose from the rendered source, rerender, and bind a fresh audit to the new MP4. Keep only short mathematical labels or a deliberately designed screenshot-worthy summary.
- Review test: inspect the original hotspot in the repaired MP4 with audio both on and muted. Every surviving sentence must add indispensable visual structure rather than repeat narration or explain the production plan.

## Canonical review path still points to an older candidate

- `pattern_key`: `stale_canonical_review_alias_mismatch`
- Failure: a newly reviewed MP4 passes under a versioned filename, while the scene's normal `current/review.mp4` path still contains a shorter or otherwise different old render. Reviewers and users can open a valid path yet inspect the wrong candidate.
- Hard prevention: after independent approval of a versioned candidate, atomically bind the canonical review path to those exact bytes and record both hashes and durations. Regenerate the scene bundle and manifest chain after the canonical binding changes.
- Review test: hash and probe both the manifest-bound artifact and the user-facing canonical path. Their bytes, duration, streams, and full-decode result must match before publishing links.

## Final media duration exceeds the active scene contract

- `pattern_key`: `final_media_duration_contract_mismatch`
- Failure: the delivered audio and MP4 are materially longer than the active timeline fragment or compiled scene profile, so author and reviewer coverage anchors stop before the real ending even though hashes and decodes may still pass.
- Hard prevention: derive the authoritative scene duration from the locked audio/local rendered scene contract, propagate it through the timeline fragment, profile, plan, registry, telemetry, coverage anchors, and manifest, and permit only the expected frame-quantization or container-tail difference in the MP4.
- Review test: compare locked-audio duration, final MP4 duration, timeline/profile duration, last reader cue, last aligned word, tail silence, and the latest required review anchor. Any unreviewed media interval beyond frame-level tolerance blocks handoff.

## Mixed channel layouts corrupt the assembled episode audio

- `pattern_key`: `mixed_channel_layout_concat_corrupts_right_channel`
- Failure: scene MP4s with stereo and mono AAC are passed through one concat demuxer. The episode reports a valid stereo stream and may fully decode, yet mono packets can be interpreted through the earlier stereo layout and produce bursts in one channel, often during an intended silent tail.
- Hard prevention: normalize every scene to one explicit sample rate, channel count, channel layout, and lossless intermediate codec before concat; encode the delivery audio only after the normalized segments are joined. Add a per-channel terminal-silence audit to the assembly contract.
- Review test: compare the source tail with the same assembled interval, measure each output channel independently, and listen to the final hold. A full-decode pass or a correct container-level channel count is not sufficient evidence.

## Reused worktree runs a stale Skill registry

- `pattern_key`: `reused_worktree_stale_skill_registry`
- Failure: the canonical Skill adds a hard rule or state-machine check, but a reused production worktree retains an older `rules.json` or CLI. The author can then seal a locally valid profile, QC chain, manifest, or self-review that never evaluated the new rule; an acceptance reviewer compounds the error by invoking that stale author-worktree CLI.
- Hard prevention: before every start or resume, mechanically synchronize the complete canonical Skill tree into every reused worktree and compare the rule-registry hash. Seal the complete Skill-tree hash in a fresh production-batch contract. Active `batch-status` must fail when the current Skill tree differs, and the acceptance reviewer must invoke the canonical main-checkout CLI even when `--repo-root` points at an author worktree.
- Review test: change one canonical rule, leave a reused worktree's old batch contract in place, and run `batch-status --require-clean`. It must fail with the stale-Skill error. Rebuilding only the profile, copying only the Python script, or using the stale local reviewer CLI does not count as recovery.

## Reused worktree authorizes itself from a stale supervisor copy

- `pattern_key`: `reused_worktree_stale_supervisor_session`
- Failure: the main agent reassigns a reused worker or queues a deferred review todo in the canonical supervisor session, but the author worktree still contains an older copy with the same session id. The author creates a seemingly valid fresh batch from an obsolete task key or misses the deferred todo.
- Hard prevention: mutate authorization only through the canonical supervisor CLI, synchronize that exact session file into the reused worktree, and require parallel `begin-production-batch` to compare the local and canonical sealed `session_hash` values before reading the grant. Record the canonical path and hash in the batch binding.
- Review test: change one worker's canonical task key while leaving the worktree copy unchanged, then attempt `begin-production-batch` with both paths. It must fail before batch creation; matching ids without matching session hashes are insufficient.
