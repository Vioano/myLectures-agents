## Start A Scene

Set the skill and episode paths once:

```bash
SKILL=.agents/skills/lecture-animation-pipeline
EPISODE=videos/NNNN-slug
```

### 1. Compile A Small Scene Profile

```bash
python3 "$SKILL/scripts/pipeline_v2.py" compile-profile \
  --repo-root . \
  --episode "$EPISODE" \
  --scene-slug g002c_riemann_sum_limit \
    --output "$EPISODE/review/v2/g002c_riemann_sum_limit/scene_profile.json"
```

`compile-profile` also writes `active_policy.json` beside the profile. It includes every explicitly applicable human or accepted-agent regression without relying on prompt memory. Exact scene/group matches, explicit `applies_to_scenes` / `applies_to_tags`, and global issues enter the hash-bound policy. Loose keyword similarity remains retrieval-only and cannot invalidate unrelated scenes. `freeze-review` adds the policy automatically, and `verify-manifest` recomputes it from current issue files.

The compiled profile must have a positive authoritative duration. Use `timeline.scene_groups` when its timing is complete; otherwise `compile-profile` automatically binds `review/v2/<scene_slug>/timeline_fragment.json` and its hash. In the local fragment, rendered scene time is authoritative: prefer `scene_duration_seconds`, then `render_end`, before generic or narration-only duration fields. A null duration cannot enter the autopilot contract, because it would collapse stage validation, self-review probes, and blind-review checkpoints toward the opening frames.

Read that profile, not every old rule document. It contains the scene context, applicable rules, and relevant regressions, but deliberately withholds precedent hits.

- the current scene's narration, mathematical objects, driver, and inferred risk tags;
- the applicable subset of `references/rules.json`;
- only scene-relevant human/accepted-agent regressions;
- required author and reviewer evidence.

Add `--tags` only when inference misses a real property. Do not add tags to force a preferred verdict.

### 2. Force First-Principles Author Deliberation

Create a scene-specific challenge:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" begin-design \
  --profile path/to/scene_profile.json \
  --output path/to/design_challenge.json
```

Before reading old animation guidance or precedents, write `design_deliberation.json`. Model the novice, define the hidden relation and invariants, separate mathematical state `M`, display mapping `D`, and attention `A`, and propose materially different low-cost stage hypotheses. Do not render alternatives.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" validate-design-deliberation \
  --profile path/to/scene_profile.json \
  --challenge path/to/design_challenge.json \
  --deliberation path/to/design_deliberation.json \
  --output path/to/design_gate.json
```

The gate rejects generic reasoning, scene-independent templates, nearly identical candidates, missing novice-failure predictions, and deliberation that claims history was already consulted.

Autopilot contract v7 and later make this a **representation-space audit**, not a prose
brainstorm. Every scene compares at least two materially different
representation classes; `stage_dense`, `human_rejected`, and
`repeat_rejected` scenes compare at least three. One candidate must be the
smallest honest baseline. Each candidate names its real technical mechanism
(for example fixed 2D, local zoom, camera travel, 2D-to-3D reveal, projection
change, slice, or synchronized multi-view), the relation it newly reveals,
continuity carriers, complexity tier, why a simpler representation fails, its
overdesign risk, and a removal test. Distinct wording with the same visual
topology does not count as a distinct candidate. Each hypothesis therefore
also carries a structured `representation_signature`: scene-grounded primary
math objects, an enumerated stage topology, display-mapping modes, attention
handoff sequence, causal-chain objects, and identity carriers. Every
`contrast_against` record must name the actual changed axes and the visible
learner consequence. The CLI compares signatures directly, so relabeling the
same two-panel shot as “3D”, changing colors, or paraphrasing its prose cannot
manufacture another candidate.

The selected plan then carries a `representation_budget`. Every added visual
technique has exactly one primary value channel:

- `cognitive`: exposes a relation, comparison, scale, or local detail;
- `continuity`: preserves identity and orientation through a view change;
- `aesthetic_finish`: improves hierarchy, material coherence, rhythm, or
  professional finish without claiming new mathematics.

An aesthetic finish is legitimate, but it must remain non-primary,
semantically neutral, and outside protected mathematical regions. An element
with none of these value channels is unowned decoration and fails. The plan
must also record at least one deliberately rejected excess idea, so “use every
available technique” cannot pass as visual ambition. The goal is the minimum
complexity that is simultaneously mathematically honest, novice-readable, and
visually finished—not the minimum author effort and not the maximum spectacle.
The budget is cross-checked against the actual stage states: declared peak
view count must match, every supporting/context view needs an owned unique
learning job, and its view, mathematical object, display mapping, and driver
IDs must resolve to the plan. Camera, perspective, orbit, or 3D techniques must
also name the dimension/occlusion lost in the 2D baseline, why that baseline
fails, and the minimum motion that reveals the relation. “More dynamic” is not
evidence.

The budget must additionally include `visual_finish_contract`. The written
plan—and any optional supporting keyframe—may defer render resolution, dense
sampling, shading detail, render-only texture, and final easing. It may not
defer composition, object scale, primary/support/context hierarchy, contrast
roles, typography roles, line-weight roles, negative-space ownership, or
transition topology. Those belong to the reviewed plan, not to later animation
improvisation. Every stage state names the visual job of its negative space and
the generic Manim defaults it intentionally rejects. Runtime telemetry exports
one `visual_finish_check` per stage state, using a representative decoded frame
at full size and thumbnail size. Missing focal hierarchy, unreadable thumbnail
structure, unowned empty space, flat line/brightness hierarchy, debug-sketch
formula handoffs, or a claim that “formal rendering will make it beautiful”
blocks visual-plan approval and later authoring QC.

### 3. Retrieve Only Relevant Visual Grammar

After the design gate passes, retrieve reviewed production precedents and
narrow sections from the legacy backup:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" retrieve-design \
  --repo-root . \
  --profile path/to/scene_profile.json \
  --deliberation path/to/design_deliberation.json \
  --design-gate path/to/design_gate.json \
  --output path/to/precedent_packet.json
```

Search is driven by the learner operation, hidden relation, mathematical driver, identity invariant, and attention transfer, not by an effect name. Reuse, adapt, or reject each hit. A rejected historical scene is a counterexample, not a template. The repository remains authoritative; optional indexes are disposable caches.

Reviewed scenes may expose compact `visual_grammar.json` sidecars beside their source package. Each entry indexes a reusable representational solution by learner operation and hidden relation, then points back to exact code anchors and review evidence. `index-history` compiles these entries as `visual_grammar` records; `retrieve-design` may return them only after the first-principles gate. Add an entry for a genuinely reusable success instead of copying a growing catalogue into this file or loading every old example into context.

### 4. Write, Validate, And Independently Review The Dynamic Scene Plan

Before exact TTS, draft the visual scheme and narration clauses together; after the exact listened WAV and word alignment exist, finish the complete word-anchored `scene_plan.json` using `references/contracts.md`. Bind its `planning_chain` to the episode spine and active batch plan. Define cognitive regions as reusable roles, then define time-varying `stage_states` and `stage_transitions`, composition and visual-finish choices, clearances, formula memory, identity carriers, and exact clause handoffs. Optional Keynote/wireframe/keyframe probes may accompany the plan, but a reviewer must be able to judge the plan without treating those pictures as a substitute specification.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" extract-scene-production \
  --repo-root . --production "$EPISODE/progressive_production.json" \
  --scene-slug <scene_slug> --output path/to/scene_production.json

python3 "$SKILL/scripts/pipeline_v2.py" validate-scene-plan \
  --profile path/to/scene_profile.json \
  --plan path/to/scene_plan.json \
  --challenge path/to/design_challenge.json \
  --deliberation path/to/design_deliberation.json \
  --design-gate path/to/design_gate.json \
  --precedent-packet path/to/precedent_packet.json \
  --episode-spine "$EPISODE/episode_visual_spine.json" \
  --batch-plan "$EPISODE/review/v2/<batch-id>/batch_visual_plan.json" \
  --output path/to/scene_plan_validation.json

python3 "$SKILL/scripts/pipeline_v2.py" prepare-visual-plan-review \
  --repo-root . \
  --plan path/to/scene_plan.json \
  --scene-plan-validation path/to/scene_plan_validation.json \
  --scene-production path/to/scene_production.json \
  --author-agent-id PLAN_AUTHOR_SESSION \
  --reviewer independent-plan-reviewer \
  --reviewer-model CURRENT_MODEL \
  --reasoning-effort xhigh \
  --reviewer-agent-id INDEPENDENT_REVIEWER_SESSION \
  --probe keynote=path/to/optional_visual_probe.key \
  --probe keyframe=path/to/optional_risky_transition.png \
  --output path/to/visual_plan_review_draft.json
# The independent reviewer fills the derived checks, then seals the pass:
python3 "$SKILL/scripts/pipeline_v2.py" seal-visual-plan-review \
  --repo-root . \
  --plan path/to/scene_plan.json \
  --scene-plan-validation path/to/scene_plan_validation.json \
  --scene-production path/to/scene_production.json \
  --input path/to/visual_plan_review_draft.json \
  --output path/to/visual_plan_review.json
```

Failing deterministic validation or independent plan review means animation production has not begun and must not begin. Fix the visual scheme first; do not open Manim/Remotion source, build a full silent animatic, or patch layout symptoms while leaving a false plan behind. Exact narration, audio, and word alignment are inputs to this final plan review. If a later change affects wording, timing, semantics, stage topology, composition, object identity, or handoff meaning, invalidate the relevant receipts, update the plan, and repeat deterministic validation; material plan changes repeat the independent review.

After the plan review passes, compile one execution registry from that exact active-scene media contract. Scene code and telemetry must consume registry IDs instead of independently retyping object, driver, stage, formula, and word-anchor IDs.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" compile-scene-registry \
  --repo-root . --profile path/to/scene_profile.json --plan path/to/scene_plan.json \
  --scene-production path/to/scene_production.json --output path/to/scene_registry.json
```

## Author Efficiently

Follow the split passes in `references/authoring-philosophy.md`. Draft the
learning contract and provisional stage hypotheses first, then lock and listen
to the exact narration, WAV, and word alignment. Finish the detailed
word-anchored stage design and optional static probes from those exact inputs;
only then may the independent plan gate pass and the scene registry compile.
Mathematical animation, micro choreography, and deterministic preflight happen
only after those receipts exist.

Export runtime telemetry from the scene registry or frame analysis. Do not hand-author a passing audit. Then run:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" validate-authoring-qc \
  --profile path/to/scene_profile.json \
  --plan path/to/scene_plan.json \
  --telemetry path/to/runtime_telemetry.json \
  --output path/to/authoring_qc.json
```

This gate owns low-level layout, subtitle safety, typography, overlap,
container overflow, cue timing, transition duration, stale objects, focal
overload, QC coverage, runtime M/D/A consistency, and representative visual
finish. Layout remains mandatory: the separate `layout_audit` must come from
runtime/frame evidence, cover at least three checkpoints, and contain zero
unresolved issues. The fifth `visual_finish` layer must inspect the opening,
peak explanation, major handoffs, and ending at full and thumbnail size. The
author should spend attention on mathematical expression, visual guidance,
semantic detail, and aesthetic rhythm.

Every new autopilot plan also declares typed `math_objects`, explicit `display_mappings`, `visual_bindings`, and `math_object_invariants`. Mathematical parameters and display-only parameters are separate namespaces. Every primary visual object names its mathematical source, real driver IDs, display mapping, and runtime owner. Telemetry exports sampled `math_object_bindings`, `display_mapping_checks`, and `math_invariant_checks`; a correct label attached to a wrongly placed point, a group center standing in for a mathematical coordinate, an analytic result substituted for a visible sum, or a formula appearing without its operation fails this layer even when layout passes.

A display optimization is allowed only through a declared mapping such as `local_zoom`, `nonlinear_magnifier`, `pedagogical_parameter`, or `equivalent_deformation`. The mapping must state preserved invariants, distorted quantities, forbidden learner inferences, and a runtime validation method. It may make an infinitesimal contour indentation visible, but it may not silently replace the mathematical epsilon with a screen radius. `novel` mappings need an additional counterexample probe; there is no free-form exemption.

In v6, `local_zoom` also carries a numeric zoom contract. The source interval
must remain genuinely local (at most 15 percent of its context span), the
global context and focused view must both be present, one identity anchor must
prove that the focused object is the same source object, and screen
magnification must exceed one. When the shot teaches local linearization or a
limit, runtime evidence must sample at least three decreasing source spans and
show non-increasing approximation error with a strict overall improvement.
Thus a huge `Delta x` labeled “small” cannot pass; the honest small increment
must be made readable by the display mapping.

The zoom contract additionally binds the source coordinate window, its
mathematical drivers and state hash, an explicit affine/nonlinear transform,
orientation and scale policies, and center plus boundary correspondence
samples. Runtime QC recomputes the mapped coordinates from that transform and
derives curve-to-tangent error from sampled curve and tangent values; it does
not accept `passed: true`, a self-reported magnification, or a typed error
sequence as proof. Context and inset using different math states, reversed
orientation, detached boundaries, or a screen radius substituted for the
mathematical increment are blockers.

Runtime telemetry also exports one `representation_check` per owned technique.
It binds the declared value channel to real QC checkpoints, records the
observed gain and removal-test result, and verifies identity carriers. An
`aesthetic_finish` check additionally proves that the finish never became the
primary focal object, made no mathematical claim, and did not overlap a
protected region. Correct mathematics without this visual-value evidence is
underdesigned; spectacle without it is overdesigned. Both fail.

For `repeat_rejected` scenes, the gate also requires an executable novice ledger rather than a role-play instruction. Every beat must introduce at most one concept by default, expose distinct cause and result objects, name what the learner can point to, allow at least 1.2 seconds after the decisive action to settle, and export a runtime `semantic_event`. Register separately positioned labels and formula fragments with `track_layout_atom`; a parent group bbox cannot pardon colliding children or an invisible focal result. QC contact sheets must include every cause-result checkpoint and every stage handoff, not only aesthetically convenient frames.

The novice ledger is backend evidence, never screen copy. It must not be rendered as explanatory prose. When repairing a user-rejected scene, freeze the accepted predecessor's exact `Text`/`Tex`/`MathTex`/numeric-label inventory before changing motion. `verify-text-inventory` blocks review if constructor counts, literal payloads, static character count, or dynamic payload count changes. Runtime snapshots also discover text descendants automatically, so a child label omitted from manual registration can still trigger a collision blocker.

The screen is not a second narration channel. In v7 and later every literal screen-text
payload must be listed in `screen_text_contract.semantic_items` with its
constructor, count, permitted role, one unique visual job, necessity,
learner-visible removal failure, mathematical-object or learner-question
anchor, and clearance condition. Formulas, object labels, axis/tick labels,
parameter values, compact titles, comparison labels, and brief transient
questions are permitted when the picture needs them. Literal extraction also
covers registered project wrappers such as `cn_text`. Explanatory sentences
that restate the voice, episode/recap/process commentary, creator identity,
next-video scheduling, and text whose only job is to announce what the
animation should have shown are blockers. Author self-declarations do not
override the deterministic boundary scan. `freeze-review` cross-checks this
semantic inventory against the actual source-text baseline; a relabeled
paragraph cannot pass. Episode `post_tts` readiness independently repeats the
same exact-inventory check through `screen_text_semantic_contract_path`, so a
scene that never produced a formal final scene plan cannot reach candidate
render or handoff. A scene-specific screen-text budget increase also requires
a duration-bound cap plus a persisted reason, transient-text plan, and semantic
contract path; raising the number alone is rejected.

Treat transformation words as executable cues, not captions. The CLI detects
strong narrated actions such as rotation, uniform scaling, reflection, shear,
stretch, bending, translation, and local zoom. Every occurrence must appear in
`narrated_action_contracts`, bind an exact word-alignment anchor, name the
mathematical object, and declare enacted motion, a counterexample, or a visible
inhibition contrast. Runtime evidence must measure the corresponding geometry:
for example, the word “旋转” changes the object's angle at that word, while
“等比例伸缩” changes both axis scales by the same ratio. Repeating “旋转” or
“等比例伸缩” on screen, highlighting the words, or swapping a formula is not
evidence. The timing tolerance is 0.08 seconds for these word-level actions.
Detection must follow the exact approved spoken surface, including common
equivalent phrases such as “等比缩放” and “拉长”; an authored action contract
whose spoken token is not detected is a hard failure, not an exemption. When a
legitimate spoken synonym is missing, extend the canonical detector and its
regression test, resync every active worktree, and reopen the batch under the
new Skill tree hash before continuing.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" freeze-text-inventory \
  --repo-root . \
  --scene-slug <scene_slug> \
  --baseline-label <approved-version> \
  --source path/to/src/scenes/<scene_slug> \
  --output path/to/screen_text_baseline.json

python3 "$SKILL/scripts/pipeline_v2.py" verify-text-inventory \
  --repo-root . \
  --scene-slug <scene_slug> \
  --source path/to/src/scenes/<scene_slug> \
  --baseline path/to/screen_text_baseline.json \
  --output path/to/screen_text_audit.json
```

For graph or formula-dense scenes, the runtime evidence must also include relation encodings, single-expression formula-row anchors, emphasis before/after geometry plus its onset/hold/recovery profile, clause locks, stage-motion easing evidence, and one snapshot inside every stage transition. When two equations reuse one screen slot, declare the handoff in `scene_plan.json` and execute it through `V2SceneRuntime.sequential_formula_handoff`; the runtime enforces an empty occupancy gap and `validate-authoring-qc` rejects missing, overlapping, or identity-drifted handoffs. Moving labels, braces, values, and markers must likewise declare an `identity_binding`; runtime snapshots sample carrier-dependent distance and reject detached dependents. This does not prove mathematical placement: points that claim an axis value, equality, sample, root, or intersection must also export independent `coordinate_checks` against the underlying coordinate map. A semantically correct but ugly cross-graph arrow, a fast partial-box highlight, a temporarily deformed equation, a stop-start section move, or an unaudited transition midpoint is a gate failure rather than optional polish.

Static layout endpoints are insufficient for dynamically entering or
emphasized objects. Export the full live interval and swept bounds for every
moving/scaling text, formula, brace, bar, and panel; sample onset, motion
midpoint, settled hold, and exit against every simultaneously live protected
region. Any overlap in that interval blocks the candidate even when the first
and last contact-sheet frames are clean.

Do not compress a necessary visual state chain merely because the provisional narration window is short. Before scene audio lock, revise the local wording or add a pause freely. After lock, edit only that scene's audio and regenerate only its reader SRT, word alignment, and timeline fragment. Downstream scene-local time remains unchanged; final assembly recomputes global offsets. A review-only audio patch or a visual slowdown that no longer matches the scene production contract is invalid.

### Prefer Visual Fidelity Over Assumed Render Limits

Do not simplify a named mathematical or physical object merely because a more
faithful version might cost more to render. The default production assumption
is that the available workstation has enough headroom for fine geometry,
dense sampling, smooth continuous gradients, high-resolution field textures,
and polished transitions. Rendering performance is not a quality budget unless
an actual measured render, memory, or decode failure proves otherwise.

When the narration names a concrete object such as a plate carrying a
temperature field, the scene must visibly construct that object and encode the
field from the same mathematical source at sufficient spatial and colour
resolution. A generic grid, coarse patch, or decorative gradient cannot stand
in for the named object. If optimization becomes necessary, first preserve the
mathematical identity, perceptual smoothness, and review checkpoints; record
the measured bottleneck and bounded fallback in the stage direction and
experiment log, then rerun the same five hard-gate layers. Never pre-emptively
lower modelling precision, sampling density, colour resolution, or visual
finish on an unmeasured performance assumption.

Do not optimize for a required number of review failures. Optimize for concrete evidence and low human rejection.

## Freeze The Review Candidate

Create one canonical review workspace per scene. Reuse `current/` for derived media instead of creating `v12`, `v13`, and growing frame directories; immutable attempt history belongs in JSONL logs.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" prepare-review-workspace \
  --repo-root . --episode "$EPISODE" --scene-slug <scene_slug>
```

After deterministic checks pass, bind the exact candidate. In progressive mode, output must be `review/v2/<scene_slug>/current/review_manifest.json` and include:

For v7 and later profiles, `freeze-review` also requires a sealed
`render_receipt`. Independent hashes for `source` and `review_mp4` are not
proof that the video was rendered from that source. The receipt must bind the
exact source tree hash, complete render command, concrete tool versions,
fresh media directory, real runtime-telemetry hash, and resulting MP4 hash,
and must declare `reused_media=false`. Reusing an earlier MP4 after any source
behavior or screen-text change is a blocker even when regenerated telemetry,
contact sheets, or source-only text audits look valid. Author self-review must
also compare decoded non-subtitle video text and key visible actions back to
the bound source or declared assets.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" freeze-review \
  --repo-root . \
  --episode "$EPISODE" \
  --scene-slug g002c_riemann_sum_limit \
  --profile path/to/scene_profile.json \
  --artifact design_challenge=path/to/design_challenge.json \
  --artifact deliberation=path/to/design_deliberation.json \
  --artifact design_gate=path/to/design_gate.json \
  --artifact precedent_packet=path/to/precedent_packet.json \
  --artifact plan=path/to/scene_plan.json \
  --artifact episode_spine="$EPISODE/episode_visual_spine.json" \
  --artifact batch_plan="$EPISODE/review/v2/<batch-id>/batch_visual_plan.json" \
  --artifact source=path/to/scene/package \
  --artifact scene_production=path/to/scene_production.json \
  --artifact scene_registry=path/to/scene_registry.json \
  --artifact script=path/to/scene/script.md \
  --artifact timeline=path/to/scene/timeline.json \
  --artifact telemetry=path/to/runtime_telemetry.json \
  --artifact authoring_qc=path/to/authoring_qc.json \
  --artifact review_mp4="$EPISODE/review/v2/<scene_slug>/current/review.mp4" \
  --artifact qc="$EPISODE/review/v2/<scene_slug>/current/qc" \
  --artifact layout_audit=path/to/layout.json \
  --artifact srt=path/to/subtitles.srt \
  --artifact word_srt=path/to/word_level.srt \
  --artifact word_alignment=path/to/word_alignment.json \
  --artifact asr_transcript=path/to/asr_transcript.txt \
  --artifact narration_qc=path/to/narration_qc.json \
  --artifact audio=path/to/audio.wav \
  --artifact text_inventory_baseline=path/to/screen_text_baseline.json \
  --artifact text_inventory_audit=path/to/screen_text_audit.json \
  --output "$EPISODE/review/v2/<scene_slug>/current/review_manifest.json"
```

Any source, plan, timeline, audio, subtitle, audit, QC, render receipt, or MP4
change invalidates the manifest. Re-render into a fresh media directory,
rebuild the receipt, and re-freeze. A source change can never be cleared by
asserting that the old media is “visually unchanged.”

## Seal Author Self-Review Before Independent Review

After freezing, do not let telemetry certify itself. First generate `self_review_probe.json`. For every hard-gate layer, the author must state the expected state, report the decoded state, actively try to falsify it, attach a real hashed frame inside the frozen QC artifact, bind it to the exact review-MP4 hash, and independently recompute or measure the claimed relation. The CLI selects a complete claim-anchor pair: stage-state claims stay on their state, mathematical invariants stay on their own checkpoints, clause locks stay on their spoken anchor, and novice-causality claims stay on their beat. The author cannot retarget an easy empty region, reuse one decoded frame path or CLI timestamp for multiple probes, or copy the same numeric claim across layers. Claims without a concrete mathematical object are discarded; if a layer has no valid claim, the CLI falls back to the plan's declared object inventory rather than emitting an unsealable empty target. Probe selection is time-stratified across the complete claim-anchor sequence: one-probe scenes use the middle pair, while strict two-probe scenes use the earliest and latest pairs. When two layers share an authored anchor, the later probe samples a nearby frame without changing its semantic claim. The CLI opens the frame, recomputes its SHA-256, verifies containment in the manifest artifact, and recomputes the comparator result; a self-filled `passed: true` cannot override it. Human-rejected and repeat-rejected scenes require two ranked adversarial probes per layer. A generic pass, a telemetry-only claim, a nonexistent frame, a fabricated hash, a front-loaded probe set, or a missing coordinate/value recomputation is rejected before independent review.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" prepare-self-review-probe \
  --repo-root . \
  --manifest path/to/review_manifest.json \
  --output path/to/self_review_probe_draft.json
# Fill every probe from decoded frames and independent calculations.
python3 "$SKILL/scripts/pipeline_v2.py" seal-self-review-probe \
  --repo-root . \
  --manifest path/to/review_manifest.json \
  --input path/to/self_review_probe_draft.json \
  --output path/to/self_review_probe.json
python3 "$SKILL/scripts/pipeline_v2.py" prepare-author-self-review \
  --repo-root . \
  --manifest path/to/review_manifest.json \
  --self-review-probe path/to/self_review_probe.json \
  --owner ANIMATION_AGENT \
  --author-agent-id CURRENT_AGENT_ID \
  --author-model MODEL \
  --output path/to/author_self_review_draft.json
python3 "$SKILL/scripts/pipeline_v2.py" seal-author-self-review \
  --repo-root . \
  --manifest path/to/review_manifest.json \
  --input path/to/author_self_review_draft.json \
  --output path/to/author_self_review.json
```

If author self-review catches a real defect, do not weaken the self-review to
manufacture `ready_for_independent_review`, and do not edit directly from an
unsealed chat todo. Preserve the gate-rejected
`lecture-animation-author-self-review-v2` draft and its canonical
`author_self_review_attempts.jsonl` row. The main supervisor expands every
author finding into the same code-level guidance and exhaustive root-cause
plan required after an independent rejection, then compiles an
author-origin repair contract:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" compile-author-repair-contract \
  --repo-root . \
  --repair-plan path/to/author_repair_plan.json \
  --review-exhaustion path/to/review_exhaustion.json \
  --author-self-review path/to/gate_rejected_author_self_review_draft.json \
  --manifest path/to/rejected_manifest.json \
  --output path/to/author_repair_contract.json
```

The command first verifies the frozen manifest and all bound artifacts. It
rejects an invented or accepted attempt, a plan that omits any
self-review finding, any attempt whose verification key, derived id, author
identity, finding count, or recorded gate errors do not match the rejected
draft, a non-canonical attempt-log path, a substituted source-finding hash or
exact `source_author_finding` snapshot, any changed copied source field, and
any deleted copied source field, and any non-exhaustive repair guidance. It reruns the rejected self-review gate
from the frozen manifest, profile, and plan and requires the recorded error list
to match exactly. `verify-repair-response` also refuses a stale or malformed
contract before it can emit a passing repair gate or accepted attempt. Run the normal
`prepare-repair-response` and `verify-repair-response` gates after the new
candidate is frozen. The replacement self-review must supply
`--previous-author-self-review` together with the repair contract, response,
and gate. This is the only author-self-review repair transition; it does not
grant independent acceptance.

After an independent `revise`, do not start editing from `suggested_fix` prose. The accepted attempt creates `pending_repairs[scene_slug]` in the persistent session. A later pass is impossible unless the author self-review binds the exact revise-review hash and supplies the sealed repair contract, response, and gate. The reviewer must first generate and seal `review_exhaustion.json`. It groups every symptom under exactly one `root_issue_id` and forces inspection of the full affected interval, source symbols, upstream causes, downstream symptoms, dependent artifacts, sibling paths, preservation requirements, predicted repair regressions, and all five hard-gate layers. The CLI rejects partial issue lists, duplicate root clusters, and findings left outside a cluster.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" prepare-review-exhaustion \
  --repo-root . \
  --review path/to/revise_review_draft.json \
  --manifest path/to/rejected_manifest.json \
  --output path/to/review_exhaustion_draft.json
# Complete the cluster search, seal it, then embed the sealed record as
# review_exhaustion in the final review submission.
python3 "$SKILL/scripts/pipeline_v2.py" seal-review-exhaustion \
  --repo-root . \
  --review path/to/revise_review_draft.json \
  --manifest path/to/rejected_manifest.json \
  --input path/to/review_exhaustion_draft.json \
  --output path/to/review_exhaustion.json
```

Only then compile the review into a repair contract. Every finding must already contain lineage, exact code anchors, the mathematical invariant, required code changes, behavior that must survive, affected artifacts, acceptance tests, and risks the repair could create. The repair contract snapshots root-cause clusters as well as individual findings, so the author repairs one cause comprehensively instead of chasing symptoms across rounds.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" compile-repair-contract \
  --repo-root . \
  --review path/to/revise_review.json \
  --manifest path/to/rejected_manifest.json \
  --output path/to/repair_contract.json
```

Choose and seal one repair-execution mode before touching the candidate:

- `same_author`: the original production author repairs the scene. This preserves clear ownership but records at least one review-to-author handoff.
- `repair_surgeon`: another production agent applies the repair from the sealed contract. This also records at least one handoff.
- `reviewer_assisted`: the discovery reviewer may directly apply a localized repair when translating the finding into prose would lose important visual, timing, or code context. The editor is then automatically recused from accepting that candidate; a different planned verifier must run the complete independent review. Direct editing never allows the reviewer to certify their own repair.

The mode, repair actor, editor set, planned verifier, and handoff count are part
of the sealed repair lineage. `phase-start --phase repair` and
`prepare-repair-response` must bind the same values; mismatches or a verifier
who edited the candidate are rejected. Use `reviewer_assisted` only when the
repair is localized and the reviewer already has the shortest faithful path
from evidence to code. Conceptual rewrites and broad scene redesigns remain
`same_author` or `repair_surgeon`. In a parallel episode where the main
acceptance reviewer performs the edit, start the fresh verifier with
`--review-role recusal_acceptance`. The CLI allows that exception only when the
main agent is the sealed repaired-candidate author, the verifier is different,
and the later self-review carries the matching `reviewer_assisted` execution
record. The main agent still controls the CLI and human-review gate; it does
not supply the independent verdict for its own edit.

A rejected low-cost animatic from a still-active historical workflow-v1 batch is not yet a frozen candidate and therefore does
not invent a full candidate repair contract. Wrap that bounded correction as
`phase-start --phase repair --phase-purpose animatic_repair`, pass its sealed
`--production-batch`, the exact scene slug, and every open scene-local
`--animatic-issue`. The start gate binds each issue hash and requires a
distinct planned verifier. Completion requires the repaired animatic MP4 and
its author self-review through `phase-end --animatic-output ...
--animatic-self-review ...`; it does not close the issues. A fresh independent
animatic review must verify them. Once a candidate is frozen, use the full
review-exhaustion, repair-contract, repair-response, and repair-gate lineage
below; `animatic_repair` cannot bypass candidate repair governance.

After repairing and freezing the new candidate, prepare and complete `repair_response.json`, then run the hard repair gate:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" prepare-repair-response \
  --repair-contract path/to/repair_contract.json \
  --current-manifest path/to/new_manifest.json \
  --repair-mode same_author \
  --repair-actor-agent-id production-agent-a \
  --planned-verifier-agent-id independent-reviewer \
  --handoff-count 1 \
  --output path/to/repair_response.json
python3 "$SKILL/scripts/pipeline_v2.py" verify-repair-response \
  --repair-contract path/to/repair_contract.json \
  --repair-response path/to/repair_response.json \
  --current-manifest path/to/new_manifest.json \
  --output path/to/repair_gate.json
```

The response must resolve every finding once, name changed code symbols and artifacts, pass every acceptance and preservation check, and probe every contracted new risk. Only then may `prepare-author-self-review` and `seal-author-self-review` run with `--previous-review`, `--repair-contract`, `--repair-response`, and `--repair-gate`. Missing or stale repair evidence blocks independent review. For frozen-candidate repair timing, `phase-start --phase repair` requires `--previous-review`, `--repair-contract`, `--repair-execution-mode`, `--repair-actor-agent-id`, `--planned-verifier-agent-id`, and `--handoff-count`; a completed frozen-candidate repair requires `phase-end --repair-response ... --repair-gate ... --current-manifest ...`. Repair attempts are appended to `repair_attempts.jsonl`; independent attempts record lineage counts, repair hashes, execution mode, editor identity, verifier identity, and handoff count, so later reports can distinguish missed old defects, repair-induced regressions, incomplete fixes, and handoff overhead.

## Review With One Persistent Independent Agent

Start one reviewer session for a batch of three to five scenes. The CLI binds reviewer identity, model, reasoning effort, reviewer tier, subagent session id, rules hash, and batch history. Resume that reviewer for repair checks so it retains the exact failure context unless that reviewer edited the repaired candidate. In `reviewer_assisted` mode, the editor is recused and the sealed planned verifier must perform the complete independent review; use `recusal_acceptance` when the recused editor is the parallel episode's main agent. Do not silently replace a reviewer; replacement requires a recorded reason.

In parallel-batch mode, the main agent may serve as this independent reviewer because the detailed scene design, code, rendering, and scene-local audio were authored by a production subagent. The immutable author and reviewer agent IDs must still differ. The main agent's review scope includes source, stage and mathematical truth, rendered video, narration wording, a complete audio playback, exact ASR transcript, reader/word subtitles, word alignment, timeline duration, boundary audio-visual handoffs, and a novice audio-only teach-back. A visual pass cannot compensate for a narration or audio failure.

A frontier reviewer needs no admission benchmark. A light reviewer is allowed only after `certify-reviewer` passes a hash-bound benchmark for the exact model, reasoning effort, and current rules registry. A human rejection after an automatic pass suspends that light certification and forces escalation or recertification; a self-declared calibration pass cannot clear the suspension.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" begin-review-batch \
  --repo-root . \
  --episode-spine "$EPISODE/episode_visual_spine.json" \
  --review-role acceptance \
  --batch-id fourier-g003-g005 \
  --owner ANIMATION_AGENT \
  --author-agent-id ANIMATION_AGENT_SESSION_ID \
  --reviewer REVIEW_AGENT \
  --reviewer-model MODEL \
  --reviewer-tier light \
  --reasoning-effort medium \
  --certification path/to/reviewer_certification.json \
  --reviewer-agent-id SUBAGENT_SESSION_ID \
  --output "$EPISODE/review/v2/review_session.json"
```

Review-session contract v5 derives authority from the episode spine. In `parallel_batches` mode, only `main_agent_governance.owner` may hold `review-role acceptance` and grant `pass_for_user_review_pending`. Other independent reviewers must use `diagnostic_support`; they may report defects but cannot grant final acceptance. The session stores and rechecks the spine hash on every candidate.

If the episode spine, active reviewer model, or assigned production owner changes while verified repairs are still pending, do not start a blank session and do not rewrite the old review identity. Use `migrate-review-session`. It updates the spine/reviewer binding and, when both `--owner` and `--author-agent-id` are supplied, reassigns the author while preserving `applied_review_attempt_ids`, `pending_repairs`, and the original session id. The migration records the prior author/reviewer identity, reason, and exactly which repair ledgers were preserved. Any loss of attempts or pending repairs is a hard failure.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" migrate-review-session \
  --repo-root . \
  --input "$EPISODE/review/v2/review_session.json" \
  --episode-spine "$EPISODE/episode_visual_spine.json" \
  --owner REPLACEMENT_ANIMATION_AGENT \
  --author-agent-id REPLACEMENT_ANIMATION_AGENT_SESSION_ID \
  --reviewer MAIN_ACCEPTANCE_REVIEWER \
  --reviewer-model CURRENT_MODEL \
  --reviewer-tier frontier \
  --reasoning-effort xhigh \
  --reviewer-agent-id MAIN_AGENT_SESSION_ID \
  --reason "Rebind the active ledger after the episode spine or reviewer model changed." \
  --output "$EPISODE/review/v2/review_session_migrated.json"
```

### Phase A: Blind Novice Pass

Compile a compact review capsule from the frozen manifest. It contains only applicable rule IDs, hard-gate anchors, object IDs, active regression keys, and three deterministic time-stratified blind checkpoints selected near the centers of the early, middle, and late thirds. Do not resend the expanded policy/profile/precedent corpus in the prompt.

Give the reviewer only the review MP4 plus the capsule's blind checkpoints. Before exposing source, plan, or contracts, persist the novice answers and run `seal-blind-review`. The receipt binds those answers to the exact MP4, reviewer session, model, and reasoning effort.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" prepare-review-capsule \
  --repo-root . --manifest path/to/review_manifest.json \
  --author-self-review path/to/author_self_review.json \
  --review-session "$EPISODE/review/v2/review_session.json" \
  --output path/to/review_capsule.json
python3 "$SKILL/scripts/pipeline_v2.py" seal-blind-review \
  --capsule path/to/review_capsule.json \
  --blind-review path/to/blind_review.json \
  --review-session "$EPISODE/review/v2/review_session.json" \
  --output path/to/blind_review_receipt.json
```

- What changed on screen, and what caused it?
- Which object should the eye follow at each transition?
- Where would a viewer without the result already in mind become confused?
- Did a formula merely appear, or did the mathematical action produce it?

For a repeat-rejected scene, first replay with audio muted. The reviewer must submit a muted teach-back, a muted driver prediction, and at least three timestamped candidate-confusion probes with a visible anchor and a pointing/prediction resolution test. This is intentionally harder than saying "I understood": it forces the animation itself to carry the causal explanation.
- Teach the claim back in one sentence without echoing the narration.
- Predict what changes when the declared mathematical driver changes.

### Phase B: Informed Standards Pass

Then let the same reviewer resolve supporting artifacts named by the capsule. The reviewer must submit one check per applicable reviewer rule with timestamped object-level evidence, plus three distinct worst-frame candidates and the required `narration_review`. The narration review binds the sealed narration-QC hash, reports complete-playback and audio-only novice evidence, checks style/claim ownership and mathematical terminology, and verifies transcript/subtitle/alignment/timeline drift rather than trusting file existence. Use the JSON schema in `references/contracts.md`.

Before the transactional submission, run `verify-review --lint-only` until contract, hash, coverage, calibration, and evidence-binding errors are gone. Lint never appends an attempt or mutates the persistent review session; only the final non-lint submission counts as a review submission.

For a `revise` verdict, every finding must remain `open` and implementation-ready. A reviewer cannot pre-close a defect; only the later repair response can prove closure. The reviewer is not required to edit code, but must inspect enough source to name the responsible file and symbol, state the invariant that the repair must restore, identify dependent artifacts, define executable acceptance evidence, preserve already-correct behavior, and predict likely repair regressions. When the sealed repair execution uses `reviewer_assisted`, that reviewer becomes a repair co-author for the candidate and is barred from its acceptance review. The sealed `review_exhaustion` record must be embedded in the submission before `verify-review`. Every cluster layer and every unclustered search carries real decoded QC frames whose paths exist inside the manifest's QC artifact, whose hashes match disk, and whose source MP4 hash matches the frozen candidate. A finding without this repair guidance or outside an evidence-bound exhaustive root-cause cluster is rejected; it cannot enter the author queue.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" verify-review \
  --repo-root . \
  --manifest path/to/review_manifest.json \
  --author-self-review path/to/author_self_review.json \
  --review path/to/review_submission.json \
  --review-session "$EPISODE/review/v2/review_session.json" \
  --review-capsule path/to/review_capsule.json \
  --blind-receipt path/to/blind_review_receipt.json
```

The gate rejects stale artifacts, author-reviewer identity reuse at both the human label and immutable agent-session level, missing rules, generic evidence, copied observations, unsupported exemptions, unresolved findings, an altered post-blind novice report, and an anomalous reviewer pass. It also blocks author handoff and reviewer pass while an applicable live-policy issue remains open at blocker, critical, major, or high severity. Repair it, change the issue to an explicit resolved-pending-review state, and recompile/refreeze the policy/profile/manifest. A review batch binds both `author_agent_id` and `reviewer_agent_id`; equality or a stale pre-v5 session blocks review. Autopilot reviews must submit five complete coverage sweeps: layout, mathematical-object truth, timing/attention, novice causality, and visual finish. The CLI derives required timestamps from stage states, transitions, invariant checkpoints, clause locks, and beats. Re-running verification on the same submission is deduplicated and does not inflate attempt counts. `pass_for_user_review_pending` means only that the candidate may be shown to the user.

Derive the current state from evidence instead of editing a status field by hand:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" gate-status \
  --repo-root . \
  --profile path/to/scene_profile.json \
  --plan path/to/scene_plan.json \
  --challenge path/to/design_challenge.json \
  --deliberation path/to/design_deliberation.json \
  --design-gate path/to/design_gate.json \
  --precedent-packet path/to/precedent_packet.json \
  --manifest path/to/review_manifest.json \
  --author-self-review path/to/author_self_review.json \
  --review path/to/review_submission.json \
  --review-session "$EPISODE/review/v2/review_session.json" \
  --review-capsule path/to/review_capsule.json \
  --blind-receipt path/to/blind_review_receipt.json \
  --output path/to/scene_state.json
```

Only `user_review_pending` permits presentation to the user. `scene_state.json` is a derived, hash-stamped record; it does not grant commit permission.

When review returns `revise`, update the scene plan if stage logic changed, repair, rerun deterministic checks, rerender, re-freeze, then complete a new author self-review bound to the prior findings. Only after that passes may the same independent reviewer inspect the replacement. The loop is always `author -> self-review -> independent review -> repair -> self-review -> independent review`; a diagnostic pass never skips either self-review or the later full independent pass. Do not impose a fixed maximum number of full reviews. Before requesting diagnostic routing, write and seal `change_impact.json` with exact changed object IDs, time windows, hard-gate layers, and an explicit assertion that semantic contracts stayed fixed. Without valid impact proof, or after any profile/policy/plan/timing/audio/subtitle/text-contract change, the CLI requires another five-layer full review. Three repeated full-review loops trigger root-cause re-planning rather than a pardon.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" choose-review-mode \
  --previous-manifest path/to/old_manifest.json \
  --current-manifest path/to/new_manifest.json \
  --previous-review path/to/revise_review.json \
  --review-session "$EPISODE/review/v2/review_session.json" \
  --change-impact path/to/change_impact.json \
  --attempt-log "$EPISODE/review/evolution/review_attempts.jsonl" \
  --output path/to/review_strategy.json
```

The resulting packet is executable scope rather than another prompt: every open finding receives a required time window; the CLI adds unchanged-region regression samples; changed artifact hashes and reviewer identity are fixed. `verify-diagnostic-review` rejects omitted findings, evidence outside the required windows, absent regression samples, reviewer switches, and attempts to grant final pass. A diagnostic pass yields only `diagnostic_fix_verified`; a fresh five-layer full review of the new candidate remains mandatory before `user_review_pending`. Never inherit a pass from an older MP4.
