---
name: lecture-animation-pipeline-v2
description: Build, review, and evolve myLectures scene animations with a compact compiled rule profile, retrieval from existing storyboards/timelines/source packages, artifact hashes, independent novice review, and durable outcome metrics. Use for planning, authoring, reviewing, or repairing Manim/Remotion lecture scenes in /Volumes/bocchi/myLectures when speed and strict evidence-bound gates both matter.
---

# Lecture Animation Pipeline V2

## Purpose

Run an evidence-bound production path without changing or deleting `lecture-animation-pipeline`. Support either a main-producer mode or a parallel-batch mode, while always keeping each animation author separate from the independent reviewer. Move enforcement out of ever-growing prompts and into an active author-design gate, a compact scene profile, runtime QC, and review gates.

The old skill remains the historical source for detailed philosophy and production references. V2 compiles only the rules relevant to the current scene, retrieves reusable visual grammar from live production history, and records whether each rule actually prevents human rejection.

## Non-Negotiable Boundaries

- Work in the current task branch/worktree. Do not modify the old pipeline skill while using V2.
- Keep one implementation unit per independently reviewed scene. A scene package may contain several small modules, but never place multiple review scenes in one animation file.
- Treat the episode narration outline and storyboard as provisional macro contracts. Only the active scene's script, audio, reader SRT, word-level SRT/alignment, and timeline fragment become exact timing contracts; do not invent timing from text or prematurely lock future scenes.
- Reserve the bottom 16 percent for subtitles unless the episode contract explicitly defines a larger zone.
- Never pass review from prose alone. Bind the design chain, dynamic plan, source, telemetry, authoring QC, timeline, audio, subtitle, layout audit, QC frames, and review MP4 by hash.
- A reviewer must not be the author. The author must first seal a current four-layer self-review; only then may the independent reviewer inspect the MP4 as a novice and resolve the compiled contract.
- User approval remains the final gate before staging or committing animation work.
- Do not expose precedent hits before the author completes the first-principles design gate.
- Read `references/authoring-philosophy.md` before designing a scene; use its dynamic cognitive topology and executable M/D/A model.
- Never trade review breadth for speed. Layout, mathematical-object truth, timing/attention, and novice causality are four simultaneous hard-gate layers. Adding a mathematical gate never removes layout inspection.
- Evolve during production through a hash-bound live-policy overlay. Human feedback invalidates the current profile and manifest immediately; do not wait for the episode boundary. Change global Skill code only when the feedback exposes a missing enforcement capability.
- Never let a production or review subagent skip a V2 CLI gate, replace a CLI output with hand-written prose, or continue from a failed/stale contract. The main agent owns assignment boundaries and verifies current hashes before accepting any subagent artifact.

## Choose A Production Mode

Record one mode in `episode_visual_spine.json` before production:

- `main_producer`: the main agent owns episode writing, coarse design, detailed scene design, and animation implementation. Subagents are used only for independent review. Missing `production_mode` in a legacy spine is interpreted as this mode.
- `parallel_batches`: the main agent still owns every episode-global artifact and decision: lecture, provisional narration, coarse storyboard/timeline, episode visual spine, batch partition, stable identities, human-feedback compilation, user communication, and acceptance review after each production subagent's sealed self-review. Production subagents own only bounded detailed batch/scene design, scene-local audio, implementation, and self-review. The main agent may additionally delegate an independent review pass, but may not delegate its acceptance responsibility.

In `parallel_batches`, never delegate an unbounded request such as “make the episode.” Before a subagent starts, the main agent must freeze the batch entry and exit contracts, including the boundary visual state, narration handoff at the selected lock level, required identity carriers, transition owner, explicitly free interior, and one audio handoff contract. The audio handoff fixes outgoing/incoming clause ownership, tail silence, maximum boundary drift, and a no-clipped-phoneme/no-split-mathematical-clause cut policy. Adjacent batches must share identical exit/entry audio-visual handoffs. The main agent may lock the first and last animation states or exact boundary narration while leaving internal choreography open.

The main agent must also freeze one episode-level `narration_style_contract` derived from the approved lecture, narration outline, prior episode scripts, and current human feedback. Every batch plan reproduces it exactly and adds scene-local style notes. Production subagents may refine wording only inside that contract: they may adjust sentence rhythm around the animatic, but may not change the teaching voice, prerequisite order, mathematical claim ownership, terminology, or viewer-facing boundary. Internal adjacency contracts must lock outgoing and incoming visual states, narration lock/text, handoff meaning, identity carriers, transition ownership, and explicitly free interior. A batch plan missing any of these fields must fail the CLI gate.

Run simultaneous production subagents in separate Git worktrees under `/Volumes/bocchi/myLectures-worktrees/<agent-or-task>/`, each on its own `agent/...` branch. Never make several production subagents write concurrently in the canonical checkout, and never create ad-hoc sibling production directories such as `/Volumes/bocchi/myLectures-*`. The main checkout remains the integration and final-review source of truth. In parallel mode, `begin-production-batch` verifies that `--repo-root` is a direct child of the required worktree root and that the checked-out branch uses the `agent/...` prefix; a canonical-checkout or wrong-branch invocation fails before production starts.

The CLI remains a synchronous command-line program; the orchestration layer supplies background concurrency. Its modular storage layer serializes shared JSON/JSONL state across processes, writes JSON by same-filesystem atomic replacement, deduplicates attempts while holding the log lock, and rejects a new review submission if its persistent session changed during verification. Do not bypass these transitions by editing session, attempt, repair, or phase files directly. Production agents keep authoring state in their own worktrees; only the main agent imports accepted batch artifacts and performs canonical acceptance review.

Human feedback always routes through the main agent. Record it in episode feedback/issues, compile it through `compile-profile` into `active_policy.json`, and bind the resulting policy hash before authoring or review. A subagent implements or checks the compiled contract; it does not independently decide what the human intended.

## Plan Progressively, Then Lock Progressively

Do not design the whole episode at equal detail in one pass, and do not jump from a finished `timeline.json` directly into isolated scene code. Use this required macro-to-micro planning chain:

1. **Lecture truth.** Finish the lecture notes and mathematical argument first.
2. **Provisional episode language.** Write only a coarse narration outline and coarse `storyboard.md`. Establish the teaching order, scene jobs, cross-scene identities, and approximate boundaries, but do not synthesize or align the whole episode.
3. **Whole-episode visual spine and batch plan.** The main agent seals `episode_visual_spine.json`, then plans the next three to five scenes in `batch_visual_plan.json`. In parallel mode it also locks the batch entry/exit and adjacent-scene handoffs before delegation. Both remain macro plans rather than beat-level choreography.
4. **Just-in-time scene co-design.** For the active scene, evolve the detailed visual plan and scene-local narration together. Build a low-cost mathematical animatic before locking wording. If a better visual explanation needs another clause, pause, or intermediate state, revise the local script now rather than forcing the animation under obsolete audio.
5. **Scene-local audio lock.** Only after the animatic explains the causal chain, lock that scene's script, synthesize its audio, generate reader SRT plus exact word-level SRT/alignment, and write its local timeline fragment. Select visual anchors from word timestamps, not sentence estimates.
6. **Final scene production and review.** Compile the execution registry, author the scene, run deterministic QC, then enforce `author -> self-review -> independent review`. Every independent `revise` returns to repair and a new self-review.
7. **Final assembly.** After all scenes pass, concatenate scene audio/video and offset-merge the local reader SRT, word alignment, and timeline fragments into final episode artifacts. Assembly must not silently retime an approved scene.

Use progressive locking:

- the episode layer locks teaching order, approximate scene boundaries, cross-scene object identity, and stable visual conventions, not exact audio;
- the batch layer locks continuity, transition ownership, reuse/variation, and relative complexity across neighboring scenes;
- the scene layer locks exact wording, audio, word timing, stage states, mathematical invariants, and attention transfers only after its animatic works;
- micro choreography may change after the animatic, but any semantic, timing, or planning change must update the owning artifact and invalidate downstream hashes.

Artifact responsibilities are distinct. `storyboard.md` stays human-readable and coarse at episode scale. `progressive_production.json` records which scenes are provisional, designing, audio-aligned, approved, or assembled. Each audio-aligned scene freezes a `scene_production.json` containing its script, audio, reader SRT, word-level SRT/alignment, exact ASR transcript, timeline fragment, and sealed narration QC. `episode_visual_spine.json`, `batch_visual_plan.json`, and `scene_plan.json` remain the visual planning chain. A review candidate in progressive mode must include the exact scene production contract and compiled execution registry.

Before a scene may enter `audio_aligned`, create the exact ASR transcript and a narration QC draft, then seal both the audio and language checks through the CLI. The QC gate compares the approved script with the ASR transcript after punctuation/space normalization, verifies reader and word-level subtitle bounds, checks word alignment and timeline duration against decoded audio, enforces a maximum 0.25-second drift, requires complete playback, and records an audio-only novice teach-back and concrete confusion test. Merely having an audio file is not evidence that the scene is teachable or aligned.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" seal-narration-qc \
  --repo-root . --episode-spine "$EPISODE/episode_visual_spine.json" \
  --scene-slug <scene_slug> --script path/to/script.md --audio path/to/audio.wav \
  --reader-srt path/to/reader.srt --word-srt path/to/word.srt \
  --word-alignment path/to/word_alignment.json \
  --timeline-fragment path/to/timeline_fragment.json \
  --asr-transcript path/to/asr_transcript.txt \
  --review-draft path/to/narration_qc_draft.json \
  --output path/to/narration_qc.json
```

After writing either upstream JSON artifact, seal it deterministically instead of calculating hashes by hand:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" seal-planning-artifact --input path/to/episode_visual_spine.json
python3 "$SKILL/scripts/pipeline_v2.py" seal-planning-artifact --input path/to/batch_visual_plan.json
```

Initialize the progressive tracker from the coarse timeline, then reseal it whenever one scene advances. Whole-episode narration must remain `outline_draft`; whole-episode storyboard status remains `coarse` until final assembly.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" init-progressive-production \
  --repo-root . --episode "$EPISODE" \
  --lecture-notes path/to/lecture.md --narration-outline path/to/script-outline.md \
  --storyboard "$EPISODE/storyboard.md"
python3 "$SKILL/scripts/pipeline_v2.py" seal-progressive-production \
  --repo-root . --input "$EPISODE/progressive_production.json"
```

## Start An Autopilot Batch

Start each three-to-five-scene production batch only after the episode spine and batch plan pass their contracts. The batch command binds both artifacts and then starts a measured five-hour active-work contract. This is an efficiency alarm, not permission to skip quality gates.

The command is mandatory for every production subagent. A chat assignment, Markdown checklist, or valid-looking JSON does not authorize implementation. The subagent must receive the emitted production-batch contract and must stop if `begin-production-batch`, `compile-profile`, any design validator, `validate-scene-plan`, `validate-authoring-qc`, manifest verification, or review verification fails. The main agent must reject work produced outside this chain.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" begin-production-batch \
  --repo-root . --episode "$EPISODE" \
  --batch-id <batch-id> \
  --scenes <scene-a,scene-b,scene-c> \
  --episode-spine "$EPISODE/episode_visual_spine.json" \
  --batch-plan "$EPISODE/review/v2/<batch-id>/batch_visual_plan.json" \
  --production "$EPISODE/progressive_production.json" \
  --author-id <production-subagent-id> \
  --target-hours 5 \
  --output "$EPISODE/review/v2/<batch-id>.json"
```

Wrap every design, authoring, render, review, repair, TTS, and ASR phase with the existing phase timer. Run `batch-status` during production. It reports measured active time, full/diagnostic review mix, artifact growth, missing phase telemetry, and stale human-outcome logs. An exceeded active-work budget forces a root-cause process review; it never grants a visual pardon.

`phase-start` automatically snapshots cumulative Codex token usage from the current rollout when `CODEX_THREAD_ID` is available. For other workers, pass `--usage-file` pointing to cumulative OpenAI/Anthropic/Codex-compatible JSON or JSONL. `phase-end` records the delta. Missing design/authoring/review/repair token evidence raises `TOKEN_TELEMETRY_INCOMPLETE`; zero is never silently interpreted as observed usage.

## Start A Scene

Set the skill and episode paths once:

```bash
SKILL=.agents/skills/lecture-animation-pipeline-v2
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

### 3. Retrieve Only Relevant Visual Grammar

After the design gate passes, retrieve reviewed production precedents and narrow sections from the old skill:

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

### 4. Write And Validate The Dynamic Scene Plan

Before final animation code, draft `scene_plan.json` using `references/contracts.md`. Bind its `planning_chain` to the episode spine and active batch plan. Define cognitive regions as reusable roles, then define time-varying `stage_states` and `stage_transitions`. The low-cost animatic may use provisional timings. After the scene-local script and word alignment are locked, replace provisional anchors with exact word anchors and run the final plan validation below.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" validate-scene-plan \
  --profile path/to/scene_profile.json \
  --plan path/to/scene_plan.json \
  --challenge path/to/design_challenge.json \
  --deliberation path/to/design_deliberation.json \
  --design-gate path/to/design_gate.json \
  --precedent-packet path/to/precedent_packet.json \
  --episode-spine "$EPISODE/episode_visual_spine.json" \
  --batch-plan "$EPISODE/review/v2/<batch-id>/batch_visual_plan.json"
```

Failing this gate means the scene is not ready for final rendering. Fix the orchestration file first; do not patch layout symptoms directly in Manim while leaving a false plan behind.

Extract the exact active-scene media contract and compile one execution registry. Scene code and telemetry must consume registry IDs instead of independently retyping object, driver, stage, formula, and word-anchor IDs.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" extract-scene-production \
  --repo-root . --production "$EPISODE/progressive_production.json" \
  --scene-slug <scene_slug> --output path/to/scene_production.json
python3 "$SKILL/scripts/pipeline_v2.py" compile-scene-registry \
  --repo-root . --profile path/to/scene_profile.json --plan path/to/scene_plan.json \
  --scene-production path/to/scene_production.json --output path/to/scene_registry.json
```

## Author Efficiently

Follow the six authoring passes in `references/authoring-philosophy.md`: learning contract, grayscale wireframe, mathematical animatic, regional refinement, micro choreography, deterministic preflight.

Export runtime telemetry from the scene registry or frame analysis. Do not hand-author a passing audit. Then run:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" validate-authoring-qc \
  --profile path/to/scene_profile.json \
  --plan path/to/scene_plan.json \
  --telemetry path/to/runtime_telemetry.json \
  --output path/to/authoring_qc.json
```

This gate owns low-level layout, subtitle safety, typography, overlap, container overflow, cue timing, transition duration, stale objects, focal overload, QC coverage, and runtime M/D/A consistency. Layout remains mandatory: the separate `layout_audit` must come from runtime/frame evidence, cover at least three checkpoints, and contain zero unresolved issues. The author should spend attention on mathematical expression, visual guidance, semantic detail, and aesthetic rhythm.

Every new autopilot plan also declares typed `math_objects`, explicit `display_mappings`, `visual_bindings`, and `math_object_invariants`. Mathematical parameters and display-only parameters are separate namespaces. Every primary visual object names its mathematical source, real driver IDs, display mapping, and runtime owner. Telemetry exports sampled `math_object_bindings`, `display_mapping_checks`, and `math_invariant_checks`; a correct label attached to a wrongly placed point, a group center standing in for a mathematical coordinate, an analytic result substituted for a visible sum, or a formula appearing without its operation fails this layer even when layout passes.

A display optimization is allowed only through a declared mapping such as `local_zoom`, `nonlinear_magnifier`, `pedagogical_parameter`, or `equivalent_deformation`. The mapping must state preserved invariants, distorted quantities, forbidden learner inferences, and a runtime validation method. It may make an infinitesimal contour indentation visible, but it may not silently replace the mathematical epsilon with a screen radius. `novel` mappings need an additional counterexample probe; there is no free-form exemption.

For `repeat_rejected` scenes, the gate also requires an executable novice ledger rather than a role-play instruction. Every beat must introduce at most one concept by default, expose distinct cause and result objects, name what the learner can point to, allow at least 1.2 seconds after the decisive action to settle, and export a runtime `semantic_event`. Register separately positioned labels and formula fragments with `track_layout_atom`; a parent group bbox cannot pardon colliding children or an invisible focal result. QC contact sheets must include every cause-result checkpoint and every stage handoff, not only aesthetically convenient frames.

The novice ledger is backend evidence, never screen copy. It must not be rendered as explanatory prose. When repairing a user-rejected scene, freeze the accepted predecessor's exact `Text`/`Tex`/`MathTex`/numeric-label inventory before changing motion. `verify-text-inventory` blocks review if constructor counts, literal payloads, static character count, or dynamic payload count changes. Runtime snapshots also discover text descendants automatically, so a child label omitted from manual registration can still trigger a collision blocker.

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

Do not compress a necessary visual state chain merely because the provisional narration window is short. Before scene audio lock, revise the local wording or add a pause freely. After lock, edit only that scene's audio and regenerate only its reader SRT, word alignment, and timeline fragment. Downstream scene-local time remains unchanged; final assembly recomputes global offsets. A review-only audio patch or a visual slowdown that no longer matches the scene production contract is invalid.

Do not optimize for a required number of review failures. Optimize for concrete evidence and low human rejection.

## Freeze The Review Candidate

Create one canonical review workspace per scene. Reuse `current/` for derived media instead of creating `v12`, `v13`, and growing frame directories; immutable attempt history belongs in JSONL logs.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" prepare-review-workspace \
  --repo-root . --episode "$EPISODE" --scene-slug <scene_slug>
```

After deterministic checks pass, bind the exact candidate. In progressive mode, output must be `review/v2/<scene_slug>/current/review_manifest.json` and include:

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

Any source, plan, timeline, audio, subtitle, audit, QC, or MP4 change invalidates the manifest. Re-freeze after rerendering.

## Seal Author Self-Review Before Independent Review

After freezing, do not let telemetry certify itself. First generate `self_review_probe.json`. For every hard-gate layer, the author must state the expected state, report the decoded state, actively try to falsify it, attach a real hashed frame inside the frozen QC artifact, bind it to the exact review-MP4 hash, and independently recompute or measure the claimed relation. The CLI opens the frame, recomputes its SHA-256, verifies containment in the manifest artifact, and numerically checks `abs(actual_value - expected_value) <= tolerance_value`; a self-filled `passed: true` cannot override that result. Human-rejected and repeat-rejected scenes require two ranked adversarial probes per layer. A generic pass, a telemetry-only claim, a nonexistent frame, a fabricated hash, or a missing coordinate/value recomputation is rejected before independent review.

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

After an independent `revise`, do not start editing from `suggested_fix` prose. The reviewer must first generate and seal `review_exhaustion.json`. It groups every symptom under exactly one `root_issue_id` and forces inspection of the full affected interval, source symbols, upstream causes, downstream symptoms, dependent artifacts, sibling paths, preservation requirements, predicted repair regressions, and all four hard-gate layers. The CLI rejects partial issue lists, duplicate root clusters, and findings left outside a cluster.

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

After repairing and freezing the new candidate, prepare and complete `repair_response.json`, then run the hard repair gate:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" prepare-repair-response \
  --repair-contract path/to/repair_contract.json \
  --current-manifest path/to/new_manifest.json \
  --output path/to/repair_response.json
python3 "$SKILL/scripts/pipeline_v2.py" verify-repair-response \
  --repair-contract path/to/repair_contract.json \
  --repair-response path/to/repair_response.json \
  --current-manifest path/to/new_manifest.json \
  --output path/to/repair_gate.json
```

The response must resolve every finding once, name changed code symbols and artifacts, pass every acceptance and preservation check, and probe every contracted new risk. Only then may `prepare-author-self-review` and `seal-author-self-review` run with `--previous-review`, `--repair-contract`, `--repair-response`, and `--repair-gate`. Missing or stale repair evidence blocks independent review. Repair attempts are appended to `repair_attempts.jsonl`; independent attempts record lineage counts and the repair hashes, so later reports can distinguish missed old defects, repair-induced regressions, and incomplete fixes.

## Review With One Persistent Independent Agent

Start one reviewer session for a batch of three to five scenes. The CLI binds reviewer identity, model, reasoning effort, reviewer tier, subagent session id, rules hash, and batch history. Resume that reviewer for repair checks so it retains the exact failure context. Do not silently replace it; replacement requires a recorded reason.

In parallel-batch mode, the main agent may serve as this independent reviewer because the detailed scene design, code, rendering, and scene-local audio were authored by a production subagent. The immutable author and reviewer agent IDs must still differ. The main agent's review scope includes source, stage and mathematical truth, rendered video, narration wording, a complete audio playback, exact ASR transcript, reader/word subtitles, word alignment, timeline duration, boundary audio-visual handoffs, and a novice audio-only teach-back. A visual pass cannot compensate for a narration or audio failure.

A frontier reviewer needs no admission benchmark. A light reviewer is allowed only after `certify-reviewer` passes a hash-bound benchmark for the exact model, reasoning effort, and current rules registry. A human rejection after an automatic pass suspends that light certification and forces escalation or recertification; a self-declared calibration pass cannot clear the suspension.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" begin-review-batch \
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

### Phase A: Blind Novice Pass

Compile a compact review capsule from the frozen manifest. It contains only applicable rule IDs, hard-gate anchors, object IDs, active regression keys, and three deterministic blind checkpoints. Do not resend the expanded policy/profile/precedent corpus in the prompt.

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

For a `revise` verdict, every finding must remain `open` and implementation-ready. A reviewer cannot pre-close a defect; only the later repair response can prove closure. The reviewer is not required to edit code, but must inspect enough source to name the responsible file and symbol, state the invariant that the repair must restore, identify dependent artifacts, define executable acceptance evidence, preserve already-correct behavior, and predict likely repair regressions. The sealed `review_exhaustion` record must be embedded in the submission before `verify-review`. Every cluster layer and every unclustered search carries real decoded QC frames whose paths exist inside the manifest's QC artifact, whose hashes match disk, and whose source MP4 hash matches the frozen candidate. A finding without this repair guidance or outside an evidence-bound exhaustive root-cause cluster is rejected; it cannot enter the author queue.

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

The gate rejects stale artifacts, author-reviewer identity reuse at both the human label and immutable agent-session level, missing rules, generic evidence, copied observations, unsupported exemptions, unresolved findings, an altered post-blind novice report, and an anomalous reviewer pass. A review batch binds both `author_agent_id` and `reviewer_agent_id`; equality or a stale pre-v4 session blocks review. Autopilot reviews must submit four complete coverage sweeps: layout, mathematical-object truth, timing/attention, and novice causality. The CLI derives required timestamps from stage states, transitions, invariant checkpoints, clause locks, and beats. Re-running verification on the same submission is deduplicated and does not inflate attempt counts. `pass_for_user_review_pending` means only that the candidate may be shown to the user.

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

When review returns `revise`, update the scene plan if stage logic changed, repair, rerun deterministic checks, rerender, re-freeze, then complete a new author self-review bound to the prior findings. Only after that passes may the same independent reviewer inspect the replacement. The loop is always `author -> self-review -> independent review -> repair -> self-review -> independent review`; a diagnostic pass never skips either self-review or the later full independent pass. Do not impose a fixed maximum number of full reviews. Before requesting diagnostic routing, write and seal `change_impact.json` with exact changed object IDs, time windows, hard-gate layers, and an explicit assertion that semantic contracts stayed fixed. Without valid impact proof, or after any profile/policy/plan/timing/audio/subtitle/text-contract change, the CLI requires another four-layer full review. Three repeated full-review loops trigger root-cause re-planning rather than a pardon.

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

The resulting packet is executable scope rather than another prompt: every open finding receives a required time window; the CLI adds unchanged-region regression samples; changed artifact hashes and reviewer identity are fixed. `verify-diagnostic-review` rejects omitted findings, evidence outside the required windows, absent regression samples, reviewer switches, and attempts to grant final pass. A diagnostic pass yields only `diagnostic_fix_verified`; a fresh four-layer full review of the new candidate remains mandatory before `user_review_pending`. Never inherit a pass from an older MP4.

## Present For User Review

Present each scene separately even when several are ready together. Include:

- review MP4;
- QC/contact sheet;
- scene profile and plan;
- timeline, audio, and subtitle paths;
- source package and layout audit;
- manifest and review result;
- remaining limitations, if any.

Do not combine scene videos before scene-level approval. Do not stage or commit until the user explicitly approves.

## Evolve From Outcomes, Not Rule Volume

Immediately after human feedback, before touching animation code:

1. write each finding to `review/issues/*.json` with `source: human_review`, `must_check_in_future: true`, and the affected scene;
2. rerun `compile-profile`, which refreshes `active_policy.json` and invalidates the old manifest;
3. update the plan's regression prevention and mathematical invariants where applicable;
4. only then repair and review again.

Also append one durable outcome event; do not leave new human feedback only in Markdown or chat:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" record-outcome \
  --episode "$EPISODE" \
  --scene-slug g002c_riemann_sum_limit \
  --author-model MODEL \
  --reviewer-model MODEL \
  --automatic-verdict pass_for_user_review_pending \
  --human-verdict revise \
  --caught-by human \
  --pattern-key formula_overlap \
  --review-rounds 2 \
  --reviewer-findings 3 \
  --human-findings 1 \
  --render-count 3 \
  --minutes 74
```

At a scene batch or episode boundary:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" evolution-report \
  --event-log "$EPISODE/review/evolution/events.jsonl"
```

Follow `references/evolution.md`. New feedback enters as an event and candidate pattern first. Promote a rule only when severity or recurrence justifies it, its applicability is narrow enough to compile, and it has a concrete evidence contract or machine check. Merge or retire rules that add reading cost without reducing recurrence.

Measure work phases rather than estimating total minutes from memory. Wrap design, authoring, render, review, repair, TTS, ASR, and human wait with `phase-start` / `phase-end`; record actor role, model, reasoning effort, prompt/artifact bytes, files read, and available input/cache/output/reasoning token counts. Reused concurrent work must share one `phase_instance_id`. `batch-status` reports wall critical path, aggregate agent-seconds, concurrency overlap, and token totals separately, so one shared review is not counted once per scene. At each skill change, write a pre-change and matched post-change record with `snapshot-iteration`, then use `compare-iterations`.

## Resources

- `scripts/pipeline_v2.py`: backward-compatible CLI entrypoint and domain command adapters.
- `scripts/pipeline_v2_lib/core.py`: dependency-free hashes, timestamps, errors, and canonical serialization.
- `scripts/pipeline_v2_lib/storage.py`: process locks, atomic JSON replacement, locked JSONL append/deduplication, and read-modify-write primitives.
- `scripts/pipeline_v2_lib/review_state.py`: persistent review-session and attempt transactions.
- `references/authoring-philosophy.md`: novice-centered layered cognitive staging, dynamic stage topology, and executable M/D/A visual grammar.
- `references/rules.json`: single machine-readable rule registry.
- `references/contracts.md`: scene-plan, manifest, and review submission contracts.
- `references/evolution.md`: rule lifecycle and metric-driven compaction.
