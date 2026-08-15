# V2 Data Contracts

Use JSON for gate inputs. The CLI rejects missing or stale evidence; prose review reports may accompany these files but cannot replace them.

## Progressive Planning Chain

V2 plans at three visual resolutions instead of attempting one equally detailed episode-wide pass.

### Episode Visual Spine

`episode_visual_spine.json` uses schema `lecture-animation-episode-visual-spine-v2`. It is the compact machine-readable companion to the human-readable, coarse whole-episode `storyboard.md`. Required content:

- the episode path plus hashes of the current `timeline.json` and `storyboard.md`;
- `production_mode`: `main_producer` or `parallel_batches`; a missing field is accepted only as the legacy `main_producer` default;
- in `parallel_batches`, a `main_agent_governance` object naming the main owner, global artifacts it owns, the human-feedback routing rule, and the mandatory CLI-gate rule;
- one episode-level `narration_style_contract` naming prior-script references, audience, voice, reasoning order, sentence and terminology rules, forbidden patterns, the audio-only success test, and the bounded freedom granted to production subagents;
- one concise `teaching_spine` for the episode;
- cross-scene mathematical-object identity carriers and stable visual conventions;
- one record for every timeline scene, with `scene_slug`, teaching role, primary objects, incoming learner state, outgoing learner state, transition intent, and `planning_status` of `provisional` or `frozen`;
- a canonical `spine_hash`.

The episode spine fixes teaching order, approximate scene boundaries, persistent object identity, and visual conventions. It must not expand into beat-level choreography or claim exact whole-episode audio timing.

### Batch Visual Plan

`batch_visual_plan.json` uses schema `lecture-animation-batch-visual-plan-v2`. Required content:

- `batch_id`, episode path, and the bound `episode_spine_hash`;
- exactly three to five scene records matching the production batch, each with continuity in, teaching job, stage strategy, continuity out, and a deliberate variation from neighboring scenes;
- shared identity carriers, transition contracts, and a short complexity-distribution decision;
- in `parallel_batches`, `main_agent_owner`, `cli_gate_policy: required_no_bypass`, an exact copy of the episode `narration_style_contract`, scene-local `narration_style_notes`, one main-authored `batch_entry_contract`, one `batch_exit_contract`, and explicit `adjacency_contracts` for neighboring scenes. Each boundary contract names its boundary scene, fixed visual state, narration lock level (`intent` or `exact`) and text, required identity carriers, transition owner, compatibility key, what the subagent may vary internally, and an `audio_handoff` fixing clause ownership, tail silence, maximum drift, and cut policy;
- a canonical `batch_plan_hash`.

The batch plan owns cross-scene continuity, transition responsibility, reuse versus variation, and relative cognitive load. It does not replace any scene plan.

For parallel production, the main agent writes the boundary contracts before delegation. The episode spine's `batch_partition` must cover every timeline scene exactly once, in order, with three to five scenes per batch. Each partition row fixes entry and exit compatibility keys, identity carriers, visual states, narration locks/text, shared handoff meanings, audio handoffs, and the explicitly free interior. Neighboring rows must use the same key, carriers, handoff meaning, and audio handoff at their shared boundary; the CLI rejects gaps, overlaps, reorderings, and incompatible handoffs. Each batch plan must reproduce its bound spine row and narration-style contract exactly. Internal adjacency contracts likewise fix outgoing/incoming visual states, narration meaning/text/lock, audio handoff, identity carriers, and the free interior. `begin-production-batch` also requires `--author-id` and `--supervisor-session` in parallel mode. The author must be an active `animation_author` or `production_author` in the v2 stable roster, and its frozen `task_key` must equal the batch id. The emitted production contract snapshots that roster grant; an unregistered replacement cannot begin production.

Parallel `begin-production-batch` additionally verifies Git isolation: `--repo-root` must be the root of a dedicated checkout at `/Volumes/bocchi/myLectures-worktrees/<agent-or-task>/`, and its current branch must begin with `agent/`. The emitted batch contract records both worktree path and branch. The canonical checkout is reserved for main-agent planning, integration, and final review.

The batch contract also seals the complete canonical Skill-tree hash. On every
resume and before any scene can be treated as sealed, the reused author
worktree must contain the same complete Skill tree as the canonical checkout.
`batch-status` rejects a changed Skill tree in active mode with
`production batch is stale for the current Skill tree`; `--historical` may only
inspect it and emits `HISTORICAL_SKILL_TREE_ADVANCED`. The repair is to
synchronize the full Skill tree, begin a fresh batch contract, and rebuild all
downstream rule-bound artifacts. Copying only the Python state machine or only
`SKILL.md` is not a valid synchronization.

In parallel mode the local supervisor-session file must be checked against the
canonical main-agent session at batch creation. Pass both
`--supervisor-session` and `--canonical-supervisor-session`; the command rejects
different sealed `session_hash` values before it reads the local grant. The
emitted batch binding records the canonical session path and hash so later
review can trace which central authorization was used.

An `exact` narration lock preserves the clause verbatim. An `intent` lock permits wording changes only when the named mathematical object, causal claim, learner state, and handoff action remain unchanged; `freedom_inside` must state the allowed scope. Changing a fixed boundary state, compatibility key, carrier, or locked narration meaning is an upstream contract change and invalidates downstream hashes.

### Progressive Locking

`scene_plan.json` adds `planning_chain.episode_spine_hash` and `planning_chain.batch_plan_hash`. The review manifest includes both upstream artifacts. A changed spine or batch plan is a material contract change, requires downstream revalidation, and cannot use a diagnostic review as the final gate.

When the coarse `timeline.scene_groups` row has no usable clock, profile compilation reads the scene-local `timeline_fragment.json`. The fallback clock is the rendered scene duration: `scene_duration_seconds`, then `render_end`, followed only then by generic or audio-duration fields. Narration duration cannot silently truncate visual cleanup, hold, or transition states.

The workflow-v2 planning resolution is therefore:

1. lecture notes plus provisional whole-episode narration and storyboard;
2. coarse whole-episode visual spine;
3. medium-detail three-to-five-scene batch plan;
4. just-in-time scene narration and detailed visual-scheme co-design, with no animation source;
5. exact scene-local script, listened audio, SRT, word timing, narration QC, and timeline;
6. complete word-anchored plan validation and independent visual-plan review, with optional Keynote/wireframe/keyframe evidence only;
7. execution-registry compilation, final animation authoring, and voiced review;
8. offset-based final assembly.

A time-based silent animatic is not a workflow-v2 planning stage. Static
probes may expose a risky composition or transition, but they cannot replace
any required plan field and cannot authorize TTS, authoring, or render work.

## Progressive Script And Audio Production

`progressive_production.json` uses schema `lecture-animation-progressive-production-v2`. It binds current lecture notes, a `narration_outline` whose status is `outline_draft`, a `storyboard` whose status is `coarse`, scene state records, and final assembly state. Scene states advance through `provisional`, `designing`, `audio_aligned`, `animation_candidate`, `user_approved`, and `assembled`.

At `audio_aligned` and later, a scene requires hash-current `script`, `audio`, `reader_srt`, `word_srt`, `word_alignment`, `timeline_fragment`, `asr_transcript`, and `narration_qc` artifacts plus positive `duration_seconds`. `narration_qc` is created only by `seal-narration-qc`; it binds the episode narration-style contract and all exact speech artifacts, requires full playback plus an audio-only novice assessment, checks normalized script/ASR equality and mathematical terms, and enforces subtitle/alignment/timeline duration drift no greater than 0.25 seconds. `extract-scene-production` copies one such row into immutable `lecture-animation-scene-production-v2`. It intentionally excludes other mutable scene rows, so progress elsewhere cannot invalidate an approved scene.

Final assembly may be marked `assembled` only when every scene is assembled and final audio, reader SRT, word-level SRT/alignment, and timeline artifacts exist. Local timestamps remain authoritative; assembly adds cumulative offsets rather than retiming scene internals.

## Compiled Scene Execution Registry

`compile-scene-registry` writes `lecture-animation-scene-execution-registry-v2` from the validated profile, final scene plan, and exact scene production contract. It contains mathematical objects, display mappings, visual bindings, stage and transition IDs, word anchors, formula choreography, clause locks, duration, and exact media hashes. Scene code consumes this registry and runtime telemetry exports its `registry_hash`. The review gate rejects independently retyped or stale runtime identities.

## Scene Profile

`compile-profile` writes the profile. Do not edit its rule subset by hand. Recompile when the timeline group, rule registry, or episode issues change.

Important fields:

- `profile_hash`: canonical SHA-256 of the profile content.
- `context`: episode, scene group, narration, duration, objects, and driver.
- `tags`: inferred and explicit applicability tags.
- `rules`: selected active rules from `rules.json`.
- `regressions`: ranked scene-relevant issue records, capped to avoid prompt flooding.
- `first_principles_seed`: scene role, driver, and mathematical objects; precedent hits are intentionally withheld.

New profiles use the autopilot contract. `compile-profile` writes a sibling `active_policy.json`, then binds its `policy_hash` into the profile. The live policy contains explicitly applicable `human_review`, `accepted_agent_feedback`, and `must_check_in_future` issue records plus their five-layer gate routing. Exact scene/group, explicit scene/tag, and global matches are enforced; loose keyword matches remain retrieval-only so unrelated feedback cannot invalidate a frozen scene.

An episode-wide umbrella issue must not be closed merely because one scene was repaired, and it must not stall repaired sibling scenes. Keep the umbrella `status` open until the whole declared scope is verified, and record explicit `scene_statuses` for progressive work. For a global issue, the current scene's entry is the hard-gate authority; a missing scene entry falls back to the umbrella status and therefore remains blocked. `resolved_pending_review` may release only that scene into author self-review and independent review. A revise verdict returns that scene entry to an open repair status, while the episode umbrella stays open until every scoped scene and the final assembly have passed.

`context.duration` must be positive before the profile receives an autopilot contract. `compile-profile` first uses the scene-group timing and otherwise binds the precise `review/v2/<scene_slug>/timeline_fragment.json`, recording its path and hash. Missing duration is a hard failure because all scene-state bounds, evidence probes, and independent-review checkpoints depend on it.

## Active Author Design Chain

The author cannot retrieve precedents before a first-principles gate passes.

1. `begin-design` creates `lecture-animation-design-challenge-v2` from the profile. It contains scene objects, narration, driver, risk tags, and regressions, but no precedent hits.
2. The author writes `lecture-animation-design-deliberation-v2` with `phase: first_principles` and `history_consulted: false`.
3. `validate-design-deliberation` creates `lecture-animation-design-gate-v2`.
4. `retrieve-design` creates `lecture-animation-precedent-packet-v2` from the validated problem signature.

The deliberation requires:

- `novice_model`: `known_before`, `likely_wrong_inference`, `needed_visual_evidence`, `success_prediction`;
- `problem_signature`: learner operation, invisible relation, invariant, perceptual target, working-memory burden;
- under autopilot v6, at least two hypotheses for every scene and at least
  three for dense or rejected scenes;
- each hypothesis: stage logic, view mapping, math-state logic, attention logic, identity invariants, novice advantage, failure risk, mute-test prediction;
- v6 hypothesis fields: a distinct `representation_class`, concrete
  `technical_mechanism`, `revealed_relation`, non-empty
  `continuity_carriers`, `complexity_tier` (`baseline`, `focused`, or
  `expanded`), `why_simpler_fails`, `overdesign_risk`, and `removal_test`;
- v6 `representation_signature`: scene-grounded
  `primary_math_object_ids`, enumerated `stage_topology`,
  `display_mapping_modes`, `attention_handoff_sequence`,
  `causal_chain_object_ids`, and `identity_carrier_ids`;
- one or more `contrast_against` records per candidate, naming another
  candidate, the structurally changed axes, and their visible learner
  consequence;
- at least one v6 hypothesis at the `baseline` tier, representing the smallest
  honest view rather than a knowingly incomplete straw man;
- exactly one selected hypothesis and a concrete selection reason.

The CLI rejects generic, scene-independent, lexically near-duplicate, or
representation-class duplicate hypotheses. The
precedent packet contains separate reviewed-production and legacy-guidance
hits. It never copies an entire guidance library into context.

## Dynamic Scene Plan

`lecture-animation-scene-plan-v2` binds the four design hashes and the selected hypothesis. It also requires:

- `planning_chain`: the current `episode_spine_hash` and `batch_plan_hash`;
- `learning_contract`: novice start state, core claim, likely misconception, visible evidence, success test;
- `math_driver` and a novice-state causal ledger;
- typed `math_objects`, each with mathematical type, definition, real driver IDs, and parameters explicitly marked `math` or `display`;
- `display_mappings`, each naming its mathematical source, mapping mode, display-only parameters, preserved invariants, disclosed distortions, forbidden inferences, and validation method;
- v6 `local_zoom` mappings add `zoom_contract`: mathematical source parameter,
  `max_source_span_fraction` no greater than `0.15`, required context and zoom
  views, identity anchor, refinement goal, and—when the goal is
  `local_linearization` or `limit_behavior`—an approximation-error metric and
  at least three refinement samples;
- the zoom contract also binds `source_window_math` (coordinate space,
  context/source spans, exact driver ids, and math-state hash),
  `zoom_transform` (affine/nonlinear kind, scale/translation where
  applicable, orientation and scale policies), center plus boundary
  `correspondence_samples`, and an explicit boundary-correspondence
  requirement;
- `visual_bindings`, binding every primary visual object to exactly one mathematical object, display mapping, driver set, and runtime owner;
- v6 `representation_budget`: the selected representation class, the minimum
  sufficient visual claim, peak simultaneous view count, an empty
  `decorative_only_elements` list, at least one deliberately
  `rejected_excess`, and one or more owned techniques;
- every owned technique names a `value_channel` of `cognitive`, `continuity`,
  or `aesthetic_finish`, a concrete value claim, a removal-failure test, and
  QC checkpoint ids. It also binds real stage-region view ids, math-object
  ids, display-mapping ids, driver ids, one unique learning job, a hidden
  relation or prevented false inference, a counterfactual-without statement,
  and a non-redundancy record. Cognitive/continuity techniques require
  identity carriers. Aesthetic-finish techniques must be `never_primary`,
  declare no mathematical claim, and remain outside protected regions.
  Camera/3D/perspective techniques additionally declare the lost
  dimension/occlusion, why the 2D baseline fails, and the minimum motion
  contract;
- v6 `visual_finish_contract` inside the representation budget: scene-specific
  visual intent; focal, scale, typography, line-weight, contrast, material, and
  motion strategies; a thumbnail-readability prediction; the complete set of
  composition obligations already fixed by the detailed plan and optionally
  illustrated by supporting static probes; only permitted
  render-polish deferrals; at least two rejected generic defaults; and one
  negative-space job for every stage state;
- `stage_regions`: stable cognitive roles with teaching job, primary object, and detail strategy;
- `region_relations`, each with a stable `relation_id` and a declared visual encoding, plus `region_refinements` and `identity_map`;
- `stage_states`: time intervals with `math_state_id`, learner task, and active region placements;
- `stage_transitions`: transition interval, pedagogical trigger, focus transfer, `continuity_mode`, identity carriers, interpolation contract, context policy, continuity test, and M/D/A change vector/order. Use `identity_preserving` with one or more named carriers, or `full_clear` with an empty carrier list and an explicit continuity-break contract; never invent a carrier merely to satisfy the schema;
- beat-level knowledge-before, visual evidence, and permitted learner inference;
- for `repeat_rejected` scenes, a monotonic concept ledger on every beat: stable `beat_id`, exact `concepts_available_before`, at most one new concept by default, at least 1.2 seconds of settling time, pointing targets, and a non-symbolic `evidence_mode`;
- formula history and token choreography for formula-dense scenes, including non-geometric emphasis or an explicit restore policy;
- `clause_locks` for repeat-rejected scenes, binding each major spoken claim to one object and expected visible change;
- v7 `narrated_action_contracts`, one entry for every strong transformation
  term detected in the scene narration. Each entry reproduces the detected
  token, occurrence index, action kind, exact `word_anchor_id`, mathematical
  object, delivery mode, expected visible change, runtime evidence id, and
  `motion_not_duplicate_text` policy. Positive claims use enacted motion;
  negative claims use a visible counterexample or inhibition contrast. Text,
  formula replacement, or token highlighting cannot satisfy the contract;
  exact approved spoken synonyms are part of the contract surface. The
  canonical detector includes common forms such as `等比例伸缩`、`等比伸缩`、
  `等比缩放`、`拉伸` and `拉长`; a valid new synonym requires a detector
  regression and a fresh Skill-bound batch rather than a local bypass;
- v7 `screen_text_contract.semantic_items`, covering every literal payload in
  the frozen source inventory with constructor, count, permitted semantic
  role, a unique visual job, necessity, learner-visible removal failure,
  mathematical-object or learner-question anchor, and clearance condition.
  Extraction includes registered project wrappers such as `cn_text`; long
  explanatory prose, narration duplicates, episode/recap/process commentary,
  creator identity, next-video scheduling, and unregistered dynamic text are
  blockers regardless of author self-declaration;
- the episode `post_tts` readiness item must bind that exact machine-readable
  contract through `screen_text_semantic_contract_path`. The episode gate
  independently re-extracts the final source and rejects missing, stale, extra,
  or self-exempted text, so a scene without a formal final text contract cannot
  reach candidate render or handoff;
- one v6 precedent decision per retrieved hit (`reuse`, `adapt`, or `reject`),
  each with reason, planned influence, and evidence target; a global `no_fit`
  bypass is not accepted;
- regression prevention.
- `math_object_invariants` for every primary stage object: stable invariant id, exact mathematical claim, expected relation, runtime evidence type, and checkpoints.

New autopilot profiles use contract version 8. Version 8 preserves all v7
representation, narrated-action, semantic screen-text, and render-receipt
requirements and adds decision-time screen-text registration. Supported display modes are
`identity`, `uniform_scale`, `local_zoom`, `nonlinear_magnifier`, `projection`,
`sampling`, `log_length`, `pedagogical_parameter`,
`equivalent_deformation`, and `novel`. Modes that visually distort scale or
geometry must disclose the distortion and forbidden learner inferences.
`equivalent_deformation` also requires an equivalence basis; `novel` requires
a counterexample probe. Display-only parameters cannot drive mathematical
state. Version 4 made implementation-ready repair contracts and finding
lineage mandatory after every independent `revise`; version 6 adds
representation-space competition, owned visual-value budgets, and truthful
local-zoom evidence.

A region is not permanently tied to one rectangle. Bounds live in each `stage_state`, so a supporting region may retire and a selected region may be promoted smoothly into the released space.

Each active placement uses normalized `[left, bottom, right, top]`, a salience of `primary`, `supporting`, or `context`, and an honest `view_mapping`. Stage states must cover at least 85 percent of scene duration and stay above the subtitle zone. Unapproved overlap fails.

For each transition, the CLI derives:

- `M`: whether `math_state_id` changed;
- `D`: whether active regions, geometry, or view mappings changed;
- `A`: whether primary regions changed.

The declared `change_vector` must equal the computed vector. `M` changes require a real driver event. `D` changes require identity continuity. `A` changes require focus endpoints and context policy.

## Visual Grammar Sidecar

A reviewed scene may include `src/scenes/<scene_slug>/visual_grammar.json` as retrieval metadata, not as a second source implementation. Keep it compact and point back to live scene code.

Required fields:

- schema `lecture-animation-visual-grammar-v2` and matching `scene_slug`;
- one or more stable pattern ids;
- learner operations, hidden relation, identity invariant, attention transfer, and visual action;
- retrieval terms phrased both as the teaching problem and likely user language;
- exact source anchors with path, symbol or line locus, and mathematical role;
- bound review status and review artifact.

The history index emits one `visual_grammar` record per pattern. The cache may be deleted and rebuilt; the sidecar, code, and review artifact remain authoritative. Do not preload all entries before first-principles design.

## Runtime Authoring Telemetry

`lecture-animation-authoring-telemetry-v2` must come from `runtime_export` or `frame_analysis`, never a manual pass assertion. It contains:

- frame size, fps, and duration;
- ordered snapshots with `stage_state_id`, `math_state_id`, primary regions, visible objects, normalized bboxes, semantic roles, font sizes, opacity, containers, anchors, and focal status;
- narration/visual cues with timing, semantic end, transition duration, before/after M/D/A identifiers, declared change vector, driver event, and identity carrier;
- formula-row audits with single-expression typesetting, alignment anchors, before/after emphasis geometry, and temporal emphasis evidence (`onset`, `hold`, `recovery`, `box_trace=false`);
- stage-motion evidence for each stage transition: duration, continuous-path declaration, easing profile, midpoint time, and whether split segments have matched boundary velocity;
- cross-region relation encodings with route method, normalized path length, and protected-region crossing status;
- narrowly justified overlap exceptions.
- `math_object_bindings`, sampled from runtime, proving each primary visual object keeps the planned mathematical identity, mapping, driver set, and state across time;
- `display_mapping_checks`, proving preserved invariants, disclosing observed distortions, and reporting zero forbidden-inference violations.
- for v6 `local_zoom`, `zoom_contract_check`: source-span fraction, screen
  magnification, visible context/focus states, shared source identity and
  anchor, plus decreasing-span/error samples for local linearization or limit
  behavior;
- local-zoom runtime evidence repeats the exact driver ids and math-state hash
  and supplies observed coordinates for the planned center/boundary samples.
  The CLI recomputes affine coordinates and curve-to-tangent errors from
  sampled values rather than trusting author booleans or typed error numbers;
- v6 `representation_checks`, one per owned technique, binding its value
  channel to observed QC checkpoints, exact view/math-object/mapping/driver
  ids, removal-test observation, and verified identity carriers.
  Aesthetic-finish checks also prove non-primary salience, semantic neutrality,
  and zero protected-region overlap;
- `semantic_events` binding every repeat-rejected beat to distinct visible cause/result objects, introduced concept ids, action count, and a measured settle interval;
- `word_anchor_events` for every narrated action contract, including the exact
  action kind and delivery mode, a runtime/frame-analysis geometry source,
  zero duplicate screen-text ids, and measured before/after geometry. Rotation
  reports angle change; uniform scaling reports both axis ratios; reflection
  reports orientation signs; other actions report the corresponding visible
  displacement, shear, anisotropy, curvature, or magnification delta;
- independently positioned `layout_atoms`, captured only while actually present in the rendered scene, so separate labels and formula fragments cannot hide inside a passing parent bbox.

`validate-authoring-qc` creates `lecture-animation-authoring-qc-report-v2`. It fails on:

- out-of-frame, region overflow, subtitle intrusion, container overflow;
- unapproved overlap, cramped spacing, unreadable type;
- invisible declared focal objects and collisions between independently positioned formula/layout atoms;
- missing planned objects, focal overload, missing beat snapshots;
- missing transition-midpoint snapshots or incompatible stage states exposed during a handoff;
- formula handoffs that lack runtime serialization evidence, permit simultaneous occupancy, skip the declared empty gap, or switch the wrong formula identities;
- moving labels or markers that lack identity-binding samples or exceed their declared carrier distance;
- plotted points that lack explicit coordinate-map checks or miss a claimed axis value, equality point, sample, root, or intersection;
- visually compressed explanations whose required settling time was not propagated through the active scene's audio, reader/word subtitles, word alignment, and timeline fragment;
- late or too-early visuals, unjustified long transitions, stale objects;
- major clause-lock drift beyond 0.25 seconds;
- missing narrated-action anchors, action-kind or object drift, visual onset
  more than 0.08 seconds from the selected word, text-only delivery, duplicate
  screen prose, or geometry measurements that do not prove the narrated
  rotation/scale/reflection/shear/stretch/bend/translation/zoom;
- missing formula cues or attention handoffs;
- fragmented formula rows, alignment-anchor drift, unreadably fast traced-box emphasis, or emphasis geometry that fails to return to rest;
- stage motion shorter than the readable threshold, default-smooth stop-start halves, or a transition without a continuous-path declaration;
- missing relation encodings, long connectors, or connectors crossing protected graphs;
- mismatch between planned stage state and runtime state;
- mismatch between declared and computed M/D/A changes.
- missing cause-result checkpoints, concept-ledger drift, more than two simultaneous novice actions, formula-only evidence, or less than the planned novice settling interval.
- changed on-screen text inventory relative to the frozen approved predecessor;
- a frozen source-text payload missing from the semantic inventory, an
  explanatory sentence disguised as a label, a narration duplicate, creator
  or pipeline commentary on screen, or dynamic text without runtime
  registration;
- collisions among automatically discovered `Text`, `Tex`, `MathTex`, `DecimalNumber`, or `Integer` descendants, even when the author forgot to register them manually.
- absent, failed, object-mismatched, or evidence-mismatched `math_invariant_checks` for any planned mathematical-object invariant.
- missing or drifted mathematical bindings, mismatched runtime drivers, display mappings applied to the wrong source, undisclosed visual distortions, or forbidden mathematical inferences caused by a screen optimization.
- a macroscopic source interval disguised as an infinitesimal, a local zoom
  without global context or identity continuity, or local-linearization
  samples whose tangent error does not improve as source scale shrinks;
- missing visual-value evidence, an owned technique whose removal test is not
  observable, or an aesthetic-finish element that becomes focal, implies
  mathematics, or overlaps protected content.
- missing `visual_finish_checks`, a plan or optional static probe that defers
  composition or hierarchy to animation authoring, unreadable thumbnail structure, unowned
  negative space, flat primary/support/context hierarchy, or unreviewed generic
  default styling.

The report includes `gate_coverage` for five independent mandatory layers:

- `layout`: frame, region, subtitle, typography, spacing, container, child-atom, and overlap evidence;
- `math_object`: object identity, driver relation, coordinates, formula operations, and declared invariants;
- `timing_attention`: cue locks, stage motion, stale-object exit, and attention handoffs;
- `novice_causality`: cause, visible action, result, concept order, and settling evidence.
- `visual_finish`: focal hierarchy, scale, contrast, typography and line-weight
  roles, negative-space ownership, material coherence, and thumbnail
  readability.

A pass requires all five. The mathematical-object layer extends layout
checking; it never replaces it, and semantic correctness never replaces visual
finish.

The telemetry and report are both hash-bound to the review manifest.

## Author Self-Review Falsification Probe

Contract version 5 requires a separate `lecture-animation-self-review-probe-v2` before the author receipt. `prepare-self-review-probe` derives the five layers, timestamps, object IDs, and risk-tier probe count from the frozen manifest and scene plan. `seal-self-review-probe` requires each probe to contain:

- expected and actually observed mathematical/display state;
- an explicit attempt to falsify the claimed correctness;
- a decoded frame that exists inside the frozen QC artifact, its verified on-disk SHA-256, and the exact frozen review-MP4 source SHA-256;
- an independent numeric measurement or coordinate recomputation with `expected_value`, `actual_value`, and `tolerance_value`; the CLI recomputes the pass result instead of trusting the submitted boolean;
- `falsification_not_found` only after that independent check passes.

Telemetry and `authoring_qc` cannot prove themselves. Probe ids and timestamps are selected from frozen plan anchors; moving them invalidates sealing. Selection is deterministic and time-stratified across complete claim-anchor pairs: stage states use their own midpoints, invariants use their own checkpoints, clause locks use their own spoken anchors, and beats use their own midpoints. A single probe uses the middle pair, while strict two-probe layers use the earliest and latest pairs. Across layers, every probe must use a distinct CLI-selected timestamp and decoded frame path; a shared authored anchor is resolved with a nearby frame while preserving the claim. Copied numeric claims across layers are rejected. Human-rejected and repeat-rejected scenes require two ranked adversarial probes per layer. Applicable open blocker/critical/major/high live-policy issues also block author handoff. The sealed probe is embedded in and hash-bound by `author_self_review.json`, so replacing either the candidate or the probe invalidates handoff.

The CLI also owns the semantic target. Each probe is compiled from a specific stage state, mathematical invariant or binding, clause lock, or novice-causality beat and freezes `claim_id`, `claim_type`, `object_ids`, `metric_id`, `comparator`, and timestamp. The author supplies adversarial observations and independent evidence but cannot replace a crowded formula target with an unrelated empty-space measurement. Numeric results are recomputed with `at_most`, `at_least`, or `within_absolute`.

## Scene-Plan Validation And Independent Visual-Plan Review

`validate-scene-plan --output ...` writes
`lecture-animation-scene-plan-validation-v1`. It binds the current profile,
plan, design challenge, deliberation, design gate, precedent packet, episode
spine, and batch plan by path and content hash. A passing receipt proves that
the detailed specification is structurally current; it is not an aesthetic or
novice review.

After scene-local TTS and ASR/alignment but before animation authoring or any
render, workflow v2 prepares and seals
`lecture-animation-visual-plan-review-v1`. Its reviewer agent id must differ
from the plan author's immutable agent id. The receipt binds the passing
scene-plan validation and current plan, and requires:

- one passing completeness check for learning contract; mathematical objects
  and real drivers; stage regions/states; transitions, clearance, and identity;
  composition/hierarchy/visual finish; screen text, formula memory, and
  negative space; and clause-to-state/audio handoffs;
- one passing quality check for novice causality, mathematical-object truth,
  stage choreography/attention, visual composition/finish, and production plus
  audio-handoff feasibility;
- concrete checks for every stage state and transition;
- a complete detailed plan, zero unresolved findings, and verdict
  `ready_for_animation_production`;
- an explicit acknowledgement that Keynote, grayscale wireframes, and
  keyframes are optional supporting evidence and cannot replace the plan.

Each optional probe binds kind, path, hash, purpose, and the exact plan sections
it tests. Zero probes is valid. A stack of polished keyframes with a missing
transition, clearance, identity, timing-handoff, or composition contract is
invalid.

Every `seal-visual-plan-review` submission appends one content-deduplicated
`lecture-animation-visual-plan-review-attempt-v1` row beside the review draft.
It preserves pass/revise/blocked, error count, probe count, reviewer identity,
and the exact plan, validation, and scene-production hashes. A probe-backed
rejection therefore remains evidence instead of disappearing when the plan is
fixed. Workflow-v2 authoring/render phase events also retain the visual-plan
review hash, its bound scene-production hash, and the explicitly supplied
scene-production hash. Retrospective metrics report review attempts, findings
caught before animation, probe-backed revise attempts, first-attempt passes,
and event/scene gate coverage. Missing historical telemetry remains `null`,
never an inferred pass.

New `begin-episode-efficiency` contracts use `workflow_gate_version: 2`.
TTS and ASR require episode readiness but intentionally precede the final
plan review so the plan can bind real word timing. `phase-start` then requires
`--visual-plan-review` before authoring or rendering. Authoring and every
render additionally require `--scene-production`, whose exact script,
listened audio, reader SRT,
word-level SRT/alignment, ASR transcript, narration QC, and timeline have
already reached `audio_aligned`; they also require a `post_tts`
episode-readiness receipt. Thus animation implementation cannot begin against
estimated narration. Any later wording, timing, semantic, stage, composition,
identity, or handoff change invalidates the corresponding hash-bound evidence;
material plan changes require another independent plan review.

The scene-complexity gate remains active. A duration up to 75 seconds is within
target; 75-90 seconds is a recorded warning; more than 90 seconds is blocked.
The only exception is a plan-owned `scene_split_exception` with a concrete
reason, at least two `internal_sections` bound to `stage_state_ids`, one or more
`clearance_checkpoints`, and a novice-continuity reason. The exception is
hash-bound to the plan and cannot be added as an untracked production note.

`lecture-animation-design-readiness-v2` and its low-cost animatic remain
readable only for historical workflow-v1 lineages. They cannot substitute for
the independent visual-plan review or exact scene-production gates in a new
workflow-v2 episode.

## Author Self-Review Receipt

`freeze-review` creates the candidate manifest first. `prepare-author-self-review` derives anchors, artifact hashes, object IDs, and prior findings so the author does not rewrite contract boilerplate. `seal-author-self-review` then validates and hashes `lecture-animation-author-self-review-v2` against that manifest. The receipt requires:

- owner, author model, author agent id, and a positive self-review round;
- one uninterrupted playback with audio monitored and one muted playback with teach-back and prediction;
- passing sweeps for all five hard-gate layers at every CLI-derived anchor;
- current hashes plus concrete observations for source, timeline, audio, SRT, review MP4, QC, telemetry, and authoring QC;
- a current sealed falsification probe for contract version 5;
- no open author findings and verdict `ready_for_independent_review`;
- after an independent `revise`, the exact previous-review hash and one timestamped resolution for every open finding.

The receipt is outside the review manifest to avoid a circular hash. Any replacement manifest invalidates it. `prepare-review-capsule`, `verify-review`, and `prepare-diagnostic-review` require the current receipt. Accepted and rejected author attempts append to `author_self_review_attempts.jsonl` with gate errors and finding counts; independent attempts append to `review_attempts.jsonl`.

## Review Manifest

`freeze-review` creates this file. Required artifact keys are:

- `profile`
- `episode_spine`
- `batch_plan`
- `design_challenge`
- `deliberation`
- `design_gate`
- `precedent_packet`
- `plan`
- `source`
- `timeline`
- `telemetry`
- `authoring_qc`
- `review_mp4`
- `qc`
- `layout_audit`
- `srt`
- `audio`
- `asr_transcript` and `narration_qc` for progressive scene-local audio;
- `text_inventory_baseline`
- `text_inventory_audit`
- `live_policy` for profiles with `autopilot_contract_version`.

Files receive a SHA-256. Directories receive a deterministic tree hash over relative path and file content, excluding AppleDouble files, cache files, and bytecode.

Profiles with `autopilot_contract_version >= 7` additionally require
`render_receipt`, schema `lecture-animation-render-receipt-v1`. Its
`receipt_hash` seals `scene_slug`, the frozen source SHA-256, frozen review-MP4
SHA-256, runtime-telemetry SHA-256, complete render command, concrete tool
versions, `reused_media=false`, a fresh media directory, and `rendered_at`.
`freeze-review` and `verify-manifest` reject a missing, stale, hand-edited, or
cross-scene receipt. This closes the gap where source and MP4 were each hashed
but no evidence proved that one produced the other.

Profiles with `autopilot_contract_version >= 8` additionally embed
`screen_text_registration_gate` and require the `screen_text_registry` review
artifact. Before a visible literal enters final source, it moves through:

```text
pre_registered
  -> reflected_keep | reflected_revise | reflected_remove
  -> registered | blocked | revision_required | withdrawn
```

`prepare-screen-text-registration` discloses deterministic risk signals as a
neutral prompt rather than a verdict. `seal-screen-text-reflection` requires
materially different keep and remove-or-replace cases; a risk-signalled keep
also requires counterreflection. `commit-screen-text-registration` appends a
hash-valid row to
`review/evolution/screen_text_registration_attempts.jsonl`. Only its
`registered` receipt may add a semantic item to the profile-specific registry.
`compile-profile` also appends one idempotent `gate_initialized` scene
observation to the same ledger. This makes a legitimate zero-candidate scene
measurable and lets the retrospective compare observed scenes with the planned
timeline instead of treating an empty ledger as complete coverage.
The item binds `registration_attempt_id`, `preregistration_hash`, and
`reflection_hash`. `scene_plan.json` must copy the complete latest
`screen_text_contract_patch`, including:

- `registration_contract_version: 1`;
- `registration_registry_path` and `registration_registry_hash`;
- `registration_attempt_log_path`;
- the compiled `profile_hash`;
- exact registered `semantic_items`.

Plan validation, post-TTS episode readiness, `freeze-review`, and
`verify-manifest` reload the registry and attempt ledger. They reject missing,
stale, fabricated, cross-profile, or source-divergent text lineage. The formal
presentation-boundary scan remains authoritative; author reflection cannot
self-exempt prohibited wording. The retrospective separately counts human
underblocking escapes and human overblocking findings, so the gate cannot meet
its quality target by simply deleting all visible text.

## Review Submission

Minimum accepted shape:

```json
{
  "schema": "lecture-animation-review-v2",
  "manifest_hash": "sha256 from review_manifest.json",
  "owner": "author identity",
  "reviewer": "independent reviewer identity",
  "reviewer_model": "model/version",
  "reasoning_effort": "medium",
  "capsule_hash": "hash from review_capsule.json",
  "blind_receipt_hash": "hash from blind_review_receipt.json",
  "review_round": 1,
  "verdict": "revise",
  "narration_review": {
    "narration_qc_hash": "hash from narration_qc.json",
    "full_audio_playback": true,
    "novice_audio_only_reviewed": true,
    "style_contract_checked": true,
    "exact_transcript_checked": true,
    "reader_subtitles_checked": true,
    "word_alignment_checked": true,
    "timeline_duration_checked": true,
    "math_terms_checked": true,
    "max_anchor_drift_seconds": 0.12,
    "audio_only_teach_back": "Concrete novice teach-back stated without relying on the picture.",
    "likely_novice_confusion": "Concrete remaining confusion probe and why the audio resolves it.",
    "style_compliance_observation": "Concrete comparison with the episode narration-style contract.",
    "claim_responsibility_observation": "Concrete check that every causal claim belongs to the correct mathematical object.",
    "audio_quality_observation": "Concrete full-playback observation about pacing, clipping, gaps, and pronunciation.",
    "transcript_fidelity_observation": "Concrete ASR/script and mathematical-term comparison.",
    "timeline_alignment_observation": "Concrete word/clause/timeline alignment observation with measured drift.",
    "novice_verdict": "clear",
    "verdict": "pass"
  },
  "novice_pass": {
    "summary": "What the scene appears to explain before reading the contract.",
    "visible_cause": "The visible cause-operation-result chain.",
    "confusion": "A concrete confusing point, or a concrete explanation of why the chain remains legible.",
    "eye_guidance": "Which object leads the eye at the decisive transitions.",
    "teach_back": "One sentence stating the conclusion and its visible cause without borrowing the script's wording.",
    "prediction": "A concrete prediction when the mathematical driver changes.",
    "silent_teach_back": "What the animation alone communicates with audio muted.",
    "silent_prediction": "What the animation alone makes the reviewer predict next.",
    "confusion_probes": [
      {
        "timestamp_seconds": 8.4,
        "candidate_confusion": "A concrete likely beginner misunderstanding.",
        "visible_anchor": "The exact object that is supposed to resolve it.",
        "resolution_test": "A pointing or prediction test that does not use hidden prior knowledge."
      }
    ],
    "first_confusion_timestamp": null,
    "verdict": "clear"
  },
  "checks": [
    {
      "rule_id": "CORE-001",
      "status": "passed",
      "evidence": {
        "timestamp_seconds": 12.4,
        "artifact_key": "review_mp4",
        "object_id": "frequency_cell_17",
        "observation": "Increasing L narrows this exact cell while the cell count and partial sum update in the same frame.",
        "novice_impact": "The limit is visible as refinement rather than a formula replacement."
      }
    }
  ],
  "coverage_sweeps": [
    {
      "layer": "layout",
      "result": "pass",
      "timestamps": [0.2, 8.4, 21.2, 39.7],
      "object_ids": ["main_graph", "formula_memory"],
      "observation": "Concrete full-video layout evidence at every CLI-required anchor."
    }
  ],
  "worst_frame_candidates": [
    {
      "timestamp_seconds": 8.4,
      "observation": "The densest frame remains legible, but this is the weakest spacing candidate."
    }
  ],
  "findings": [
    {
      "finding_id": "R01",
      "severity": "major",
      "rule_id": "STAGE-001",
      "timestamp_seconds": 31.7,
      "object_id": "inverse_formula",
      "problem": "The formula overlaps the active frequency cells.",
      "suggested_fix": "Move the formula to its reserved upper-right region.",
      "status": "open"
    }
  ]
}
```

Allowed verdicts are `revise` and `pass_for_user_review_pending`. A pass requires:

- novice verdict `clear`;
- a concrete teach-back and driver prediction, with no unresolved confusion timestamp;
- for repeat-rejected scenes, an audio-muted teach-back and prediction plus at least three distinct timestamped confusion probes;
- no failed rule checks;
- no open findings;
- one check for every rule owned by the reviewer;
- timestamped object-level evidence for visual and hybrid checks;
- a valid current manifest;
- reviewer identity different from owner identity.
- one complete sweep for each of `layout`, `math_object`, `timing_attention`, and `novice_causality`, covering every anchor derived from stage states, transitions, invariant checkpoints, clause locks, and beats.
- a valid compact review capsule, a blind-pass receipt sealed before contract inspection, and an unchanged `novice_pass` hash;
- at least three distinct timestamped worst-frame candidates.
- a `narration_review` bound to the current narration-QC hash, confirming complete audio playback, novice audio-only clarity, style and claim responsibility, exact transcript, reader subtitles, word alignment, timeline duration, mathematical terminology, and maximum observed drift no greater than 0.25 seconds.

`not_applicable` is accepted only for a conditional rule and requires a concrete reason. It is never accepted for an `always` rule.

If reviewer history is anomalous, the CLI requires `calibration_recheck`:

```json
{
  "calibration_recheck": {
    "performed": true,
    "trigger_event_ids": ["event id from events.jsonl"],
    "rules_rechecked": ["CORE-003", "STAGE-001", "VIS-002"],
    "fresh_timestamps": [8.4, 21.2, 39.7],
    "result": "pass"
  }
}
```

This is not a pardon. It is a durable second-pass record prompted by prior false passes, zero-finding streaks, or abnormal human rejection.

## Repair Contract And Finding Lineage

Every open finding in a `revise` review must contain both `lineage` and `repair_guidance`. `verify-review` rejects free-form findings that cannot be executed by the animation author.

```json
{
  "finding_id": "R06-02",
  "lineage": {
    "classification": "repair_induced",
    "root_issue_id": "series-synthesis-causality",
    "parent_finding_id": "R05-01",
    "evidence": "The truthful coefficient rewrite introduced simultaneous carriers that were absent in the rejected baseline."
  },
  "repair_guidance": {
    "source_anchors": [
      {
        "path": "videos/NNNN/src/scenes/scene/composer.py",
        "symbol": "animate_series_reconstruction",
        "reason": "This function owns coefficient transfer, accumulator updates, and settle timing."
      }
    ],
    "mathematical_invariant": "Each selected coefficient pair updates one persistent partial-sum accumulator exactly once.",
    "required_changes": ["Serialize each pair transfer and update the accumulator only after landing."],
    "must_preserve": ["Keep the existing coefficient values and conjugate-pair geometry unchanged."],
    "affected_artifacts": ["source", "telemetry", "review_mp4", "qc"],
    "acceptance_tests": [
      {
        "test_id": "pair-accumulator-ownership",
        "method": "Sequentially decode every transfer and compare its landing frame with the next accumulator state.",
        "expected_evidence": "One pair, one landing, one changed persistent curve, followed by a stable hold."
      }
    ],
    "new_risks_to_probe": ["Serialized transfers may compress the final hold or drift from word-level narration anchors."]
  }
}
```

Allowed lineage classes are:

- `initial_or_unknown`: initial candidate or evidence is not sufficient to assign causality;
- `preexisting_missed`: present in an earlier candidate but discovered later;
- `repair_induced`: absent before the repair and caused by the repair delta;
- `incomplete_fix`: the same root issue survived a claimed repair;
- `new_unrelated`: newly discovered and unrelated to the repair surface.

Before a `revise` submission can verify, `prepare-review-exhaustion` and `seal-review-exhaustion` require `lecture-animation-review-exhaustion-v2`. Every finding remains `open` and appears exactly once under one `root_issue_id`; `fixed` or `closed` is illegal in an independent review because closure belongs to the repair response. Each root cluster records the complete affected interval, object IDs, existing source anchors, upstream causes, downstream symptoms, dependent artifacts, sibling risks, preservation requirements, repair-induced risks, and evidence from all five hard-gate layers. Every layer carries at least one real decoded QC frame. Each of the five unclustered searches carries at least two such frames, binding their on-disk SHA-256 and the frozen review-MP4 SHA-256. Partial lists, missing files, fabricated hashes, duplicate root clusters, or uncovered findings are rejected.

`compile-repair-contract` freezes every root cluster and every open finding, their lineage, code guidance, and the rejected manifest's artifact hashes. `affected_artifacts` is the complete impact surface that must be revalidated; it does not imply that every listed artifact should mutate. When a reviewer knows that a specific artifact must change, it lists that subset separately in `required_changed_artifacts`. Governance inputs such as `live_policy` may therefore remain hash-stable while source, telemetry, rendered media, and QC evidence change. `prepare-repair-response` binds the author to a newly frozen candidate. Each response resolution must include a root-cause diagnosis, exact code-symbol changes, the actual changed artifacts, passing acceptance results, passing preservation checks, and passing probes for every predicted new risk. `verify-repair-response` writes `lecture-animation-repair-gate-v2`; a failed or stale gate blocks author self-review.

An author self-review that finds a real defect has its own formal rejection
transition; it cannot be converted into an informal edit todo. Preserve the
gate-rejected `lecture-animation-author-self-review-v2` draft and the exact
`lecture-animation-author-self-review-attempt-v2` row. The main supervisor
writes a `lecture-animation-author-repair-plan-v1` that expands every author
finding exactly once and binds each original finding object both by hash and
by an exact `source_author_finding` snapshot. Every source field must remain
present at the plan finding's top level and is immutable; a plan cannot keep
the finding id while deleting or substituting its problem,
severity, timestamp, object, pattern, or other original meaning. The main then runs
`compile-author-repair-contract`. The resulting
`lecture-animation-repair-contract-v2` has `origin: author_self_review` and
binds the rejected draft hash, canonical attempt id and attempt hash, author
agent id, baseline manifest, root-cause clusters, repair guidance, and
acceptance tests. The compiler recomputes the attempt verification key and
derived attempt id, checks author identity and finding counts, and refuses an
accepted, invented, mismatched, or gate-error-free attempt.
Only the episode's canonical
`review/evolution/author_self_review_attempts.jsonl` is authoritative. The
compiler first verifies the frozen manifest and every bound artifact, then
reloads the frozen profile and plan, reruns the rejected author
self-review gate, and requires its exact error list and count to match the
canonical row.
The repair plan may embed the sealed exhaustion record or pass it separately
with `--review-exhaustion`; the CLI validates its review-core and manifest
binding before embedding it into the compiled contract.
Pre-transition attempt rows that predate
`previous_author_self_review_hash` remain verifiable only through their exact
legacy three-field verification key; a current row cannot omit the new field.

After new media is frozen, the ordinary repair-response and repair-gate
commands remain mandatory. `verify-repair-response` rejects a stale or
malformed repair contract before it can write a passing gate or accepted
attempt. The replacement author self-review must pass
`--previous-author-self-review` together with the three repair-bundle paths.
Supplying both `--previous-review` and `--previous-author-self-review`,
omitting any bundle member, changing the rejection hash, or using a contract
with the wrong origin is a hard failure. This transition only restores
eligibility for independent review; it never grants acceptance.

`review/evolution/repair_attempts.jsonl` or the explicitly selected attempt log records accepted and rejected repair gates. Full review attempts also record `finding_lineage_counts` and the hashes of the repair contract, response, and gate. These fields support immediate-fix rate, incomplete-fix recurrence, repair-induced regression rate, and delayed-discovery rate without reconstructing history from prose.

All mutable state transitions go through `pipeline_v2_lib.storage`. JSON files use a process lock plus same-directory temporary file, `fsync`, and atomic replacement. JSONL attempts use a process lock, one complete append, and a content-derived unique key. Review-attempt commit locks the attempt log and session together, stores applied attempt IDs for crash recovery, increments a session revision, and rejects a new submission whose expected session hash is stale. Retrying an already committed verification key is idempotent.

The current backend is intentionally `fcntl` plus atomic JSON and locked JSONL. Run `scripts/state_store_stress.py` to exercise real process contention, stale-writer rejection, and pending-repair durability. SQLite/WAL is not required for the present single-Mac, low-write-rate CLI workload. Migrate when the system needs a shared cross-worktree scheduler or lease, atomic transactions across several unrelated state families, sustained concurrent readers and writers, or indexed querying large enough that JSONL scans become material. WAL does not replace evidence, role, or repair contracts.

Every review submission remains durably logged, but only `gate_accepted: true` attempts increment `full_reviews` or `diagnostic_reviews`, update calibration scene counts, or trigger the three-round re-planning rule. Contract, hash, and evidence failures increment `gate_rejected_attempts` instead. Reports classify those failures separately from actual visual and mathematical findings so submission-format churn is not misreported as animation review work.

## Review Attempt Log And Derived State

`verify-review` appends one `lecture-animation-review-attempt-v2` row per unique submission and gate result to `review/evolution/review_attempts.jsonl`. Re-running the same verification produces the same `verification_key` and is deduplicated. Failed CLI gates are recorded as well as accepted reviews.

Use `verify-review --lint-only` while preparing the submission. It performs the same validation without appending an attempt or mutating the persistent session. This separates cheap JSON/hash/coverage correction from substantive accepted review rounds.

`gate-status` derives one of these states from the files that currently validate:

- `unprofiled`
- `profiled`
- `planned`
- `review_candidate_frozen`
- `author_self_review_passed`
- `revision_required`
- `user_review_pending`

Never advance a state by assertion. Independent review is permitted only from `author_self_review_passed`. After `revision_required`, repair and freeze a new manifest, then seal a new self-review bound to the prior independent findings before returning to either diagnostic or full independent review. The derived state file contains a `state_hash` and always keeps `may_stage_or_commit` false because only explicit human approval can grant that permission.

## Persistent Review Session

`begin-review-batch` writes `lecture-animation-review-session-v2` contract version 5. It requires both `author_agent_id` and `reviewer_agent_id`, rejects equality, and binds the author self-review to the same author session before any capsule or review can verify. It also binds `episode_spine_hash`, `production_mode`, `main_agent_id`, and `review_role`. In parallel production, only the spine's main agent may own `acceptance`; `diagnostic_support` can find defects but cannot grant a user-review pass. Pre-v5 sessions must be recreated. A full or diagnostic review must repeat the same `reviewer`, `reviewer_model`, `reasoning_effort`, and `reviewer_agent_id`. `reviewer_tier: light` additionally requires an eligible `lecture-animation-reviewer-certification-v2` bound to the exact model, effort, benchmark hash, and current rules hash. A human false pass suspends light certification. Replacing an active reviewer requires `--replace --replace-reason`.

`migrate-review-session` is the only supported way to rebind an active ledger after the episode spine, reviewer model, or assigned production owner changes. It preserves the session id, applied review-attempt ids, scenes, counters, and pending repair records, while appending a migration record containing the previous session hash, author/reviewer identity, spine hash, reason, and preserved ledgers. Author reassignment is atomic: both `--owner` and `--author-agent-id` are required, and the replacement author remains bound to every pending repair. The command re-runs author/reviewer governance against the current spine and fails if attempts or pending repairs change during migration. Starting a blank session to escape an existing repair lineage is invalid.

Every accepted full `revise` attempt creates a persistent `pending_repairs[scene_slug]` record containing the exact review hash, attempt id, manifest hash, and finding count. The next full pass must bind that exact review and provide valid repair-contract, repair-response, and repair-gate hashes. Omitting `--previous-review` cannot reset the scene to an initial-review path.

Review submissions therefore include:

```json
{
  "author_agent_id": "persistent-author-session-id",
  "reviewer": "independent-reviewer",
  "reviewer_model": "model-version",
  "reasoning_effort": "medium",
  "reviewer_agent_id": "persistent-subagent-session-id"
}
```

`lecture-animation-review-capsule-v2` is the compact execution contract for review. It contains applicable rule IDs and evidence fields, required object IDs, five-layer timestamps, active pattern keys, three deterministic time-stratified blind checkpoints selected near the centers of the early, middle, and late thirds, and the exact review-MP4 hash. `lecture-animation-blind-review-receipt-v2` seals the novice report before source and contracts are exposed.

## Diagnostic Repair Contract

`prepare-diagnostic-review` accepts only a prior `revise` review, a newly frozen manifest for the same scene, a current author self-review that resolves every prior finding, and a valid `lecture-animation-change-impact-v2`. The impact record must name exact changed objects, time windows, affected hard-gate layers, actual changed artifacts, and assert that semantic contracts stayed fixed. It is hash-bound to both manifests. Missing or invalid impact proof forces a full review.

`lecture-animation-diagnostic-review-v2` must contain one `finding_checks` row per prior finding and one `regression_samples` row at every packet timestamp. Evidence outside required windows is rejected. Its only verdicts are `revise` and `diagnostic_fix_verified`. It cannot produce `user_review_pending`; after a diagnostic pass the state machine still requires a fresh full review manifest and complete standards review.

`choose-review-mode` compares the two frozen manifests. Changes to policy, profile, design, plan, timeline, audio, subtitles, or text contracts require a new five-layer full review. If only implementation/render evidence changed under the same semantic contracts, a diagnostic review is eligible. This is adaptive routing, not a cap on full reviews. Three prior full reviews trigger root-cause re-planning instead of permission to stop inspecting the whole video.

## Phase And Iteration Records

### Durable Supervisor Communication Contract

`supervisor_watch.py begin` writes `lecture-animation-supervisor-session-v2`.
The default `communication_mode` is `continuous_low_noise`; changing it to
`explicit_verbose_override` requires an explicit user-supplied reason. Each
assignment freezes one immutable agent id, role, task key, bounded scope, and
model, then tracks task state independently from the subagent display name.
The default roster cap is three subagents, excluding the main supervisor. The
sealed cap is configurable from one through eight, but the initial roster may
contain at most three identities. Every later identity requires a compiled
capacity or replacement authorization; a larger cap is not advance permission
to spawn. The main agent normally uses the initial three slots for production
owners and remains the independent acceptance reviewer.

The session also seals `task_queue`. Initial assignments occupy active queue
rows; `--planned-task TASK_KEY|ROLE|SCOPE` adds later pending work. Assignment
completion updates both the roster member and its queue row. `status` keeps
`should_continue_monitoring` true while any task is active, pending, or blocked,
even if every current agent is momentarily idle. `finish` rejects pending or
blocked queue rows. Adding work after `begin` is exceptional and requires a
concrete reason; normal episode and batch work must be declared up front.

`assign-task` is the normal rolling transition. It accepts an `idle`,
`completed`, or task-`cancelled` roster identity, preserves its role, appends a
task-history row, and increments `reuse_count` without changing
`identity_history`. The orchestration
layer must send the corresponding `followup_task` to that same live agent. A
finished scene, repair, audit, or batch is not a reason to create another agent.

Independent-review results use the separate durable `review_todos` ledger.
`queue-review-todo` binds the exact review artifact by SHA-256, the stable
owner, reviewed scene, priority, and—when nonblocking—the scene currently being
authored. A nonblocking result enters
`deferred_until_safe_checkpoint`; it must not be sent to the author yet.
If the orchestration layer queued the wrong active-scene slug,
`retarget-review-todo` may correct only an undelivered nonblocking todo. It
preserves the deferred state, records the old and new slugs plus a concrete
reason, and never releases the result. Direct edits to the supervisor session
remain forbidden.
When the owner was temporarily running a separate independent-review task
rather than authoring, the orchestrator may mark that assignment idle only
after its final `lecture-animation-review-v2` transaction exists, then call
`release-review-todo-after-review-task`. The command verifies the idle/completed
owner, the unchanged queued task key, reviewer identity, final verdict,
manifest hash, and exact completion-evidence SHA before changing the todo to
`ready_to_deliver`. It cannot release a todo from an active authoring task and
does not replace `mark-safe-checkpoint` for candidate or animatic work.
Likewise, `release-review-todo-after-planning-task` is restricted to an exact
`lecture-animation-bounded-author-repair-impact-plan-v1` whose author and scene
match the queued owner and awaited scene. The owner must already be idle,
completed, or blocked, and the queued task key must remain in its sealed
assignment history. This is only for a stopped non-authoring planning pass; it
cannot release a todo while source, animatic, or candidate work is active.
`mark-safe-checkpoint` accepts only a hash-valid
`lecture-animation-author-self-review-v2` with verdict
`ready_for_independent_review` for the named active scene, then releases matching
todos to `ready_to_deliver`. The orchestrator sends the result with
`followup_task` and calls `acknowledge-review-delivery`. Continuity- or
user-decision-blocking results enter `interrupt_required` immediately.
`assign-task` rejects every owner with an undelivered review todo, and `finish`
rejects deferred, ready, or interrupt-required todos. Thus a review cannot be
lost, delivered mid-scene merely because it finished early, or bypassed when the
owner advances to another task.

Replacing one roster identity is one of two exceptional new-identity paths:
`authorize-replacement`, then `register-replacement`. The separate additive
path is defined below. Replacement authorization first checks that no
compatible reusable roster member exists. Accepted reason keys are
`agent_unavailable`, `task_tree_changed`, `model_change_required`, and
`unrecoverable_failure`.

After an app or machine restart, the first `collaboration.list_agents` result is
not proof that a completed child identity is gone. The orchestrator must first
send a no-write context-restoration probe through `followup_task` to every
preserved canonical child id. It then runs `collaboration.list_agents` again
and seals both observations with `seal-availability-snapshot`. The resulting
hash-bound `lecture-animation-agent-availability-v1` file contains
`live_agent_ids`, `reusable_agent_ids`, and one `followup_attempts` row per
probed id. Valid outcomes are `restored`, `target_not_found`,
`target_unavailable`, and `unrecoverable_error`.

Availability snapshots expire after fifteen minutes. For
`agent_unavailable`, `task_tree_changed`, and `unrecoverable_failure`,
replacement authorization rejects a missing probe, a `restored` outcome, or
any id still marked reusable; only the three explicit failure outcomes can
support those routes. A thread or checkpoint supplies context, but the direct
canonical child id remains the first recovery target. `model_change_required`
does not claim identity loss: it uses the current roster's compatible-reusable
check and must name a model different from the frozen current model. The
default replacement budget is one;
exceeding it requires a concrete recorded override.

If a replacement was registered before a directly reusable original identity
was discovered, stop the replacement before it writes. Seal the successful
`restored` probe, run `restore-original-identity`, and use
`cancel-replacement-authorization` for any authorization that was never
consumed. Restoration keeps the replacement in identity history, returns the
task queue and every undelivered review todo to the original owner, and leaves
delivered historical todos attributed to the identity that actually received
them.

Registration consumes exactly one authorization, retires rather than deletes
the prior identity, preserves its task ownership, and records the new immutable
agent id. Known identities cannot be registered again as if newly spawned.
Status reports current and historical identity counts, task count, reuse count,
replacement count, churn ratio, reusable members, and pending authorizations.
`--require-clean` returns nonzero for abnormal churn or an unresolved
authorization. `begin --replace` cannot discard an active session; a closed
session may be restarted only with a recorded reason and automatically carries
forward its already authorized capacity ceiling. `--replace` against a missing
output is invalid and cannot create a large first roster. Version-1 sessions
remain readable for historical status, but roster mutations require version 2.

Additive capacity has its own two receipts. `seal-availability-snapshot` must
first prove that no compatible current or retired identity is reusable;
restored retired IDs route through `restore-original-identity` instead.
`seal-capacity-evidence` then derives the empty candidate queue, active-time
reviewer wait excluding authorized pauses, cumulative cost headroom, and exact
delivery-clock genesis lineage. `authorize-capacity` binds both current
receipts, and `register-capacity` revalidates their unchanged bytes before one
pending task may receive one new identity.

Every observed event is appended to `supervisor_events.jsonl`. The fixed event
taxonomy is:

- user-visible milestones: `human_review_ready`, `user_decision_required`,
  `major_delivery_blocker`, `explicit_status_request`;
- persist-only operational events: `agent_heartbeat`, `routine_progress`,
  `repair_detail`, `timestamp_evidence`, `hash_or_gate_detail`.

In the default mode the CLI computes visibility from this taxonomy; an agent
cannot promote routine repair detail merely by choosing emphatic prose. `status`
returns `should_continue_monitoring`, `user_update_required`, the exact pending
milestone events, and `may_finish`. Reportable events must be acknowledged only
after they have been sent to the user. `finish` rejects both active assignments
or blocked assignments, unused replacement authorizations, and unacknowledged
milestones, preventing a supervision turn from ending after a routine heartbeat
while delegated work is still running.

`begin-episode-efficiency` must run in the canonical production checkout before planning. It writes `lecture-animation-episode-efficiency-contract-v4`, binding the repo-relative episode, canonical checkout root, shared episode phase ledger, eight-hour budget, token ceilings, a 195-minute closure reserve, a 45-minute retrospective reserve, 32-percent closure token reserves, 7-percent retrospective token reserves, field-specific phase token envelopes, and quality targets. An active contract is idempotent and cannot be recreated to reset prior consumption; an orphan nonempty central ledger also blocks a fresh contract.

`phase-start` requires the episode, active efficiency contract, one active-wall-time allocation, and four explicit task-capsule token allocations: raw input plus output, uncached input, output, and reasoning. Batch-scoped work additionally passes its sealed production-batch contract. The scene slug must be one exact member scene; shared batch work is wrapped once per covered scene with one stable shared-work key, which preserves per-scene coverage while deduplicating cost. A synthetic batch slug is rejected before a timer or reservation is created. New contracts default to `workflow_gate_version: 2`: TTS and ASR require episode readiness and intentionally run before final visual-plan review; authoring and render require the current independent visual-plan review plus the exact audio-aligned scene production reviewed with that plan, so animation cannot precede word timing or plan approval. Under one deterministic multi-file lock it reads completed usage and the canonical reservation ledger. Token reservations are summed; active-time reservations are projected as timestamped intervals so concurrent work overlaps rather than being double-counted. Early work is checked against the episode budget minus the closure reserve, closure work against the budget minus the retrospective reserve, and retrospective against the complete outer ceiling. The same atomic transition checks per-field phase envelopes. Reasoning uses planning 5 percent, protected planning quality repair 8, design 10, authoring 25, render 12, TTS 5, ASR 3, review 12, repair 8, finalization 5, and retrospective 7. Raw, uncached-input, and output allocations use their v4 field-specific fractions. Active time remains planning 45 minutes, design 45, authoring 75, render 75, TTS 25, ASR 20, review 60, repair 30, finalization 60, and retrospective 45.

`compile-planning-quality-repair-contract` writes `lecture-animation-planning-quality-repair-contract-v1`. It seals the rejected planning artifact, a `revise` or `blocked` quality-gate artifact, a nonempty defect manifest with evidence and acceptance checks, and the exact allowed paths. `phase-start --phase planning --phase-purpose quality_gate_repair` requires this fresh contract. The protected repair bucket shares the original 45-minute planning clock and can inherit only unused first-pass allowance; first-pass and quality-repair reasoning together are capped at 13 percent. Ordinary planning is still capped at 5 percent and cannot spend the repair reserve. Exhausting the combined completion envelope with open defects produces `budget_replan_required`, never a quality waiver.

`authorize-design-budget-continuation` writes the one-episode
`lecture-animation-design-budget-continuation-v1`. It is valid only for
`videos/0009-mpm-9-singularities_residues` after the sealed global design event
has already exceeded the original design output envelope and the exact user
authority says `授权继续。`. The record binds the unchanged efficiency contract,
failure event hash, blocker, visual spine, three batch-plan hashes, nine scene
slugs, and stable owner mapping. Its complete additional design allowance is
6,000,000 raw input-plus-output, 600,000 uncached input, 90,000 output, and
25,000 reasoning tokens; active time, task caps, outer token ceilings, closure
and retrospective reserves, author/reviewer separation, complete detailed-plan
review, and every quality gate receive no extension. `phase-start` requires
the contract through `--design-budget-continuation`, an exact fresh production
batch, phase `design`, and purpose
`scene_detailed_visual_plan_and_audio`. The timer carries both base and extended
limits, and `phase-end` preserves the base-envelope failure while succeeding
only if the extended envelope and ordinary task/outer limits pass. Changing the
authority, blocker, efficiency contract, spine, batch plans, owner, or scene
scope invalidates the continuation. The contract cannot be reused by another
episode or interpreted as a reset of earlier telemetry.

After the exact stable owners complete the three policy-restoration capsules,
one reconciled revision may bind the original continuation through
`--parent-continuation` plus exactly three `--reconciliation-event-id` values
in G001, G004, G007 order. Each event must be a completed
`animation_author_policy_restore` design event for
`scene_detailed_visual_plan_and_audio` with its original task-allocation
failure still present. The revision stores parent and event snapshots/hashes
and raises the total additional design allowance to 12,000,000 raw,
1,200,000 uncached input, 180,000 output, and 50,000 reasoning tokens. The
original 6,000,000/600,000/90,000/25,000 continuation remains valid and
unchanged; the reconciled revision still grants zero active-time extension,
does not change task caps or outer ceilings, and cannot erase any recorded
failure or relax any production/review gate.

One final compact-owner raw replan is available only after the supervisor has
sealed three replacement owners and the exact G001/G004/G007 compact revision
events each preserve a raw task-allocation failure. The command binds the
reconciled parent through `--parent-continuation` and takes exactly three
`--compact-replan-event-id` values in scene order. Its total additional design
allowance is 25,000,000 raw while uncached input, output, and reasoning remain
at 1,200,000, 180,000, and 50,000. It adds no active time, changes no task cap
or outer ceiling, preserves every predecessor failure, and cannot be chained
again.

`authorize-time-governed-budget-override` writes
`lecture-animation-time-governed-budget-override-v1` for an explicit
video-priority continuation. It is a hash-bound overlay, not a mutation or
replacement of the active v4 efficiency contract. The record seals the exact
user-authority artifact, an active parent-contract hash, the v2 supervisor
session, every authorized v2 production-batch hash, and the current canonical
ledger revision plus all historical reservation/event hashes. It also seals
`original_overflow_snapshot`, including early and outer overflow fields. A
later start/end must observe the same baseline bytes; append-only new evidence
is allowed, but rewriting or deleting a historical row is rejected.

The override scope is an exact set of
`PHASE:PURPOSE:SCENE[,SCENE...]` rows. Only `design`, `authoring`, and
`render` are allowed, with purpose values from the v1 allowlist. It cannot
authorize planning, TTS, ASR, review, finalization, or retrospective. The
generic `lecture-animation-metric-policy-v1` profile bound into the record
sets model-token budgeting to `off`/observed-only, so the overlay contains no
positive raw, uncached-input, output, or reasoning allowance and cannot charge
the parent v4 ledger. It carries only positive total and per-phase active
seconds (at most four hours; expiry at most six hours). The immutable default
task caps, workflow-gate version 2, outer budget, and quality-gate guarantees
are copied into the artifact and rechecked at every use. No authorized
overflow fields are accepted. The canonical v4 ledger remains byte/hash
immutable; full overlay events are written to the independent event log and
the canonical log receives only a compact index.

The generic profile is a single user-controlled switchboard, not a collection
of ad-hoc phase flags. `update-metric-policy` copies the existing signed scope,
actor lineage, parent contract, and active-time ceiling, applies only the
requested `--metric-mode METRIC=off|observe|enforce` changes (with `on`/`off`
aliases), binds a fresh authority artifact, and emits a new profile hash. The
previous profile stays valid historical evidence. Operational consumers must
read this shared mode; Skill hard gates such as quality gates, user review, and
post-TTS readiness remain enforced even when an operational metric is `off`.

`phase-start --time-governed-budget-override` validates the source hashes,
metric-policy profile, exact production-batch membership, user/parent/
supervisor authority, and scene scope before taking the locked reservation. It
preserves the base phase envelope and enforces only the sealed active-time
allowance; token allocations are omitted/null in observed-only mode while
declared context caps remain mandatory and observed token deltas are checked
against the default per-task token caps when available. Missing token telemetry
is retained as an explicit unknown observation but is not charged or enforced.
Authoring/render
still require the independent detailed-plan review, exact audio-aligned
scene-production receipt, and post-TTS readiness receipt. The independent
overlay ledger registers the override id/hash and original overflow before the
reservation is created; the canonical v4 ledger is never rewritten. `phase-end`
revalidates the same hashes and historical rows under the
lock, records the override binding and actual token/active-time status in the
independent event plus a compact central index, and releases the overlay
reservation. An active-time overrun is terminal non-compliance; missing token
telemetry remains unknown evidence only and does not block closeout. The command returns nonzero with
`time_governed_override_exceeded` when that status is true. Finalization and
closeout report `override_used` and reject active reservations, active-time
failures, unfinished scopes, or unfinished batches; this overlay is not a
quality waiver or compliance receipt.

Repair rerenders, technical retries, pronunciation retries, post-readiness script changes, and reuse verification charge the ordinary repair envelope rather than silently consuming initial render/TTS/ASR capacity. A rejected low-cost animatic from a historical workflow-v1 lineage uses `phase-purpose: animatic_repair`; workflow v2 instead repairs the written plan and repeats independent plan review before production. Frozen candidates still require the complete independent review-exhaustion and repair-contract lineage. A successful start creates both a hash-stamped active timer and an active reservation with actor role, model, reasoning effort, prompt bytes, artifact bytes, files read, token budget bucket, active-time budget bucket, phase envelope, and a reusable `phase_instance_id`. It snapshots cumulative token usage from `--usage-file`, `LECTURE_TOKEN_USAGE_FILE`, or the current Codex rollout discovered through `CODEX_THREAD_ID`. `phase-end` records the nonnegative delta in both the requested local log and the canonical shared ledger, releases the reservation, and fails when actual wall time or token use exceeded any reserved amount or the sealed phase envelope; explicit token arguments are a fallback for workers that expose usage only at completion. Shared concurrent work must pass the same `--shared-work-key`; the CLI derives the same deterministic instance ID and accounting identity across scene and run wrappers from episode, phase, phase purpose, actor model, actor role, and shared-work key. The reservation and event store the shared-work key, accounting identity, and timer state path. For legacy reservations missing the new fields, budget projection and statistics may derive them in memory from the timer state referenced by `state_path`; they must preserve the stored reservation and original `phase_instance_id` byte-for-byte. `human_wait` must reserve zero active time and zero tokens. Use one of: `planning`, `design`, `authoring`, `render`, `review`, `repair`, `tts`, `asr`, `finalization`, `retrospective`, `human_wait`.

Every non-wait start is additionally capped as one task capsule: 1,500,000 raw input-plus-output tokens, 100,000 uncached input tokens, 20,000 output tokens, 8,000 reasoning tokens, 32 KiB declared assignment prompt, 256 KiB declared text/structured artifact input, and 16 declared files read. Token allocations and measured deltas are hard cost controls. Context byte/file counts are auditable claims because the CLI cannot observe every model transport; false declarations invalidate the process evidence. Work larger than one capsule must stop at a hash-bound artifact checkpoint and resume as another bounded deliverable, without replaying the full corpus.

Every phase event records `token_observed`, `token_source_kind`, its reserved active time and tokens, any allocation overrun, and the efficiency-contract hash. Every non-wait phase is token-expected; reports expose coverage, missing event IDs, phase token totals, observed total tokens, and uncached input tokens. Missing usage is not converted into a trustworthy zero. At 75 percent, starts and ends emit active/token warnings. Completed use and active reservations are both charged at start time, preventing parallel workers from oversubscribing a budget that still looked available to each worker independently. Protected closure and retrospective reserves prevent early work from using resources required to finish the complete process. Once the shared ledger exceeds a hard limit, new planning, design, authoring, initial TTS, and non-repair renders are rejected; repair, review, finalization, and retrospective remain available for safe closure. In particular, an already exceeded outer token ceiling cannot suppress the mandatory retrospective: `phase-start` may admit that exact phase inside its sealed retrospective phase envelope, records `mandatory_retrospective_overrun_admission_applied` plus the original overflow fields, and leaves final efficiency closeout non-compliant. This is evidence-preserving closure, not a reset, extension, or quality pardon.

`authorize-raw-budget-replan` writes
`lecture-animation-raw-budget-replan-v1` only after the unchanged episode
ledger already exceeds its original raw-input-plus-output ceiling. It binds
the exact episode, efficiency-contract path/hash, production-batch path/hash,
four scenes in sealed order, batch author, distinct reviewer actor-agent-id,
supervisor authority, one shared-work key, episode-local allowed output paths,
and an expiry no later than six hours. It authorizes only
`review:mandatory_independent_animatic_review`. The episode may contain at
most three keys, no key may exceed 1,500,000 future raw tokens, and their total
may not exceed 4,500,000. All non-raw allowance increases are exactly zero.
Four scene wrappers share one locked reservation, reproduce one allocation,
and report the same actual; the ledger retains that actual once and consumes
the key after all four wrappers end. Revision or abandonment never refunds the
key. The original 50-million failure remains in `batch-status`, and neither
finalization nor `close-episode-efficiency` may treat the overlay as compliance
evidence. Budget failure is an escalation signal, never a quality exemption.
The overlay exempts only the episode-wide raw-total start check; it never
exempts the unchanged review raw envelope at either phase start or phase end.
Every overlay wrapper end requires at least one repeated
`--review-output`. Each output must exist, contain a real file, and resolve
inside one of the sealed allowed output paths. Its artifact snapshot is stored
in both the phase event and completed timer. Blocked, abandoned, and
revise-producing reviews remain valid outcomes, consume the same single raw
actual, and receive no refund.

`authorize-animatic-repair-budget-continuation` writes the independent schema
`lecture-animation-animatic-repair-budget-continuation-v1`; it never widens
`lecture-animation-raw-budget-replan-v1`. Authorization requires the unchanged
active efficiency contract and a canonical ledger in which both the original
raw-input-plus-output and output totals have already failed. The only valid
scopes are Episode 8 repair batch B, authored by
`/root/ep8_repair_v03_batch_b` for exact scenes G006/G008, and repair batch C,
authored by `/root/ep8_repair_v03_batch_c` for exact scene G012. Batch B may
authorize at most 1,500,000 future raw and 16,000 future output tokens; batch C
may authorize at most 1,500,000 raw and 8,000 output tokens. Exactly two keys
and at most 3,000,000 raw plus 24,000 output tokens are permitted episode-wide.

Each immutable continuation binds the production-batch path/hash and author,
an active supervisor production grant and authority hash, a distinct planned
verifier, one stable shared-work key, every exact open issue path/id/hash/scene,
and one episode-local allowed output root per scene. It expires within six
hours. `phase-start --phase repair --phase-purpose animatic_repair` must pass
the sealed continuation and the exact bound issue set, author, verifier, scene,
batch, and shared-work key. The scene wrappers reuse one reservation and
allocation signature. The start gate ignores only the already-failed outer raw
and output totals; it still enforces the original active-time limit, uncached
input and reasoning totals, task caps, and the unchanged repair phase envelope.
Every phase end, including `blocked` or `abandoned`, requires both the animatic
output and self-review under that scene's sealed root and rechecks that the
issues are still open and hash-identical. Any outcome consumes the key after
its exact wrappers finish and never closes or refunds an issue. The original
budget failure remains a `batch-status` and `close-episode-efficiency` failure.

If all four original repair phase token-envelope fields are already exceeded,
`authorize-animatic-repair-token-extension` may seal the independent companion
`lecture-animation-animatic-repair-token-extension-v1`. It binds the exact
parent continuation path/hash, shared key, strict repair scenes, complete
batch hash, author, planned verifier, open issue snapshots, and identical
expiry. Its fixed local allowances are B = 1,500,000 raw / 60,000 uncached /
16,000 output / 4,000 reasoning and C = 1,500,000 / 60,000 / 8,000 / 4,000.
The per-key active allocation is capped at 600 seconds, with zero active-time,
episode-total, base-envelope, or task-cap increase. Phase start requires both
parent and companion. Only those exact wrappers use the local token admission
instead of the already-failed base repair token envelope. The companion is
attached to the parent's existing reservation and accounting identity; it
cannot create an independent reservation and mirrors the parent's
reserved/consumed state without refund. Phase end records local actual and
uses local overrun to decide the bounded continuation result, while retaining
the original repair-envelope exceeded status, alert, episode budget failure,
and final close/process-compliance failure.

`abandon-unresponsive-animatic-repair` is a one-scene emergency transition,
not a general `phase-end` substitute. It is restricted to the active Episode 8
G012 wrapper owned by `/root/ep8_repair_v03_batch_c`, whose assignment must
already be blocked in the same sealed supervisor. Inputs are the state, blocked
supervisor, exactly three ordered worker-health JSON files, the accepted
feedback Markdown, the open accepted-agent-feedback issue, and the receipt
output. Canonical health evidence has:

```yaml
schema_version: lecture-animation-worker-health-check-evidence-v1
sequence: 1 # then 2 and 3
agent_id: /root/ep8_repair_v03_batch_c
result: no_response
requested_action: <nonempty bounded probe>
artifact_progress: false
recorded_by: /root
```

For compatibility the reader also accepts the same schema string under
`schema`, but new evidence writes `schema_version`. Under one lock the command
revalidates the active state, old continuation/extension/batch, blocked
supervisor identity, health evidence, accepted evidence, two unchanged open
content issues, and ledger reservation. All health checks, accepted feedback,
and the accepted issue must resolve outside the old author output root. The
only files permitted inside that root are the exact bound phase-state path,
the exact filename `rollout_totals_start.json`, AppleDouble mirrors, and the
command's own receipt path. Every other file—including any author
self-review, handoff, media, QC image, source file, renamed governance note, or
obsolete workaround—is attributable progress and blocks abandonment.

On success it appends one unique abandonment event and writes
`lecture-animation-animatic-repair-abandonment-v1`. Both record
`token_observed: false`; the event uses
`token_source_kind: unresponsive_worker_unobservable`; the receipt and released
reservation retain `actual: null`. The command consumes the old parent and
extension, releases the active reservation, records `refund: false`, keeps all
issues open, and seals an abandonment fence that prevents reuse of the old
state, key, or authorization. It does not require or manufacture an animatic
or self-review. A retry with the identical receipt path and lineage returns the
same receipt only after re-hashing all three health files, feedback, accepted
issue, blocked supervisor, old batch/parent/extension and revalidating the
sealed state, unique event, released unknown-actual reservation, consumed
parent/extension, no-refund fence, and unchanged open content issues.
Mismatched input paths or bytes, a duplicate/missing event, or any partial
state/ledger write fails closed.

`authorize-animatic-repair-replacement` consumes one such unspent receipt by
compare-and-swap. It accepts only replacement author
`/root/ep8_g012_replacement_author`, planned verifier
`/root/ep8_review_batch_c`, scene G012, and shared key
`ep8:g012-animatic-repair:replacement-01`. In one locked transition it writes:

- a fresh v2 supervisor whose only production assignment is that replacement;
- a fresh v2 G012-only production batch;
- a fresh v1 continuation inheriting the two content issue snapshots;
- a fresh v1 companion token extension; and
- the spent replacement binding in the abandonment receipt and episode ledger.

The recovery admission is independent of the already-consumed ordinary B/C
continuation-key count but does not refund or reset either old key. Its exact
caps are 1,500,000 raw input-plus-output, 60,000 uncached input, 8,000 output,
4,000 reasoning, and 600 active seconds; expiry is no later than six hours.
For this exact hash-bound recovery wrapper only, the parent supplies the
raw/output continuation and the companion supplies complete local admission
for all four token dimensions plus the 600-second task allocation. Therefore a
pre-existing episode closure-stage overflow or repair token/active-envelope
overflow cannot reject the replacement a second time. The phase state records
the unmodified base episode reservation overflow, repair token overflow, and
stage/repair active overflow; phase end retains the corresponding status and
alerts. No base ceiling, phase envelope, task cap, or other shared key is
expanded.
The allowed author output root must be episode-local and either absent or an
empty directory. Any pre-existing file or subdirectory rejects authorization.
The four control-plane output paths must be distinct, absent, episode-local,
and outside that author root.
The old `actual: null`, original episode failures, repair-envelope failure,
alerts, and close/process-compliance failure remain unchanged. Only one
first-level replacement may be authorized for the abandonment hash and G012;
concurrent
identical calls converge idempotently, while another key, author, verifier,
output set, or second recovery fails. A retry of a spent receipt also
revalidates the original episode, output root, every output path and hash,
supervisor grant, batch, continuation, extension, recovery CAS row,
continuation/extension ledger rows, abandonment fence, and old consumed
no-refund rows. A receipt written before its ledger CAS, a missing recovery
row, or any partial output is not idempotent success and fails closed.

The replacement `phase-start` must additionally pass
`--animatic-repair-recovery <abandonment-receipt>`. Under the same reservation
lock it revalidates receipt hash and spent status, old abandonment hash, fresh
supervisor/batch/continuation/extension hashes, author, verifier, shared key,
issue hashes, expiry, and the recovery CAS row. The fresh phase state stores
the recovery receipt and abandonment hashes. Normal continuations reject the
flag, and replacement continuations reject its absence. Phase end consumes
the recovery row with its parent and extension; revision or failure never
creates another recovery.

`abandon-unresponsive-animatic-repair-replacement` is the only second-level
abandonment transition. It accepts the exact active replacement-01 state and
supervisor, exactly two ordered `no_response` health files, then one
`forced_interrupt_no_checkpoint` file with `previous_status: running` and
`checkpoint_present: false`. The first probe must carry
`requested_at_approximate` and no invented precise `requested_at`. It binds
the exact accepted feedback
`review/agent-feedback/2026-07-30-g012-replacement-author-unresponsive.md`,
the exact open accepted issue
`review/issues/agent_g012_replacement_identity_unresponsive_2026-07-30.json`,
the two unchanged open content issues, and a zero-progress old author output
root. The scanner permits only the exact bound active phase-state path, that
file's same-directory `._` AppleDouble mirror, optional exact-root
`rollout_totals_start.json`, and the command's exact receipt path. Path
equality is exact: a same-name file under another directory is rejected.
Every other regular or hidden file, directory, and symlink is rejected. In the
same locked compare-and-swap it validates the
forced interrupt, changes the still-active supervisor assignment to
`blocked`, seals the state and event, releases the reservation with
`token_observed: false` and `actual: null`, consumes the replacement-01
continuation, extension, and recovery row without refund, and creates a
second-level abandonment fence. The receipt binds the final blocked supervisor
hash; the supervisor binds the immutable interrupt evidence, avoiding a
cyclic hash dependency. Identical retries revalidate all evidence and every
committed row. Missing, stale, duplicated, or partially written state fails
closed.
The supplied state path must exactly equal the recovery row's `state_path`,
the reservation's `state_path`, and the sole G012 value in the
reservation/parent/extension `wrapper_state_paths`. Copying a valid state to a
new filename and deleting the canonical path is rejected. Before mutation the
command derives its deterministic event id and requires that id to be absent
from the central log; a crash-left event without a receipt is detected as a
partial write and is never appended again.

`authorize-animatic-repair-second-replacement` spends that receipt once and
only for author `/root/ep8_g012_replacement_author_02`, verifier
`/root/ep8_review_batch_c`, scene G012, and key
`ep8:g012-animatic-repair:replacement-02`. It atomically creates four fresh
episode-local control artifacts and requires a fresh empty output root. Its
token caps remain 1,500,000 raw input-plus-output, 60,000 uncached input,
8,000 output, and 4,000 reasoning. Its exact local active cap is 1,500 seconds,
with sealed checkpoints `300: read_complete_and_two_change_plan`,
`600: source_patch_and_smoke_or_audit_started`,
`1200: render_qc_and_self_review_underway`, and `1500: hard_stop`. An
allocation of 1,501 seconds fails. The 1,500-second cap cannot be used by any
ordinary continuation or replacement-01. The ledger's replacement-attempt
count may move from one to two only; two is terminal and no replacement-03
authorization exists. Old unknown usage, no-refund rows, episode failures,
repair-envelope failures, and alerts remain visible.
Authorization reopens the root batch-C abandonment receipt under the same lock
and checks its bound path/hash, unknown actual, false token observation, and
no refund. It also rechecks the root released reservation, consumed
parent/extension, replacement-authorized no-refund fence, and the
replacement-01 recovery row's `consumed`, `refunded: false`, and
`second_level_abandonment_hash` fields. Re-hashing a tampered ledger or root
receipt does not authorize replacement-02.
Legacy read compatibility applies only when a valid
`lecture-animation-animatic-repair-abandonment-v1` receipt authorizes the
exact replacement-01 author, shared key, and abandonment hash. In that one
lineage, absent `attempt_ordinal` and `soft_checkpoints` read as `1` and `{}`.
An explicit mismatch is never defaulted. Replacement-02 and unrelated
recovery lineages require both fields explicitly and exactly.

### Independent-review-discovered repair-round contract

`authorize-independent-review-repair-round` is a one-shot compare-and-swap
for defects first reported by the independent reviewer after an ordinary
repair key has already been consumed. It writes
`lecture-animation-independent-review-repair-round-authority-v1`, a fresh
`lecture-animation-supervisor-session-v2`, a fresh
`lecture-animation-production-batch-v2`, and
`lecture-animation-independent-review-repair-round-state-v1`. All four
control outputs, each scene output root, and the new shared key must be fresh.
The counter key is `(episode, original_batch_lineage_root)` and its maximum is
one. Renaming the issue or batch, changing thread/worktree, or selecting
another shared key cannot create a second round.

The Episode 8 authorization additionally freezes proposal
`videos/0008-mpm-8-cauchy_integral/review/evolution/proposals/independent_review_repair_round_v2.md`
at SHA-256
`69a353138e77455c2b30e7d6adfc387b17b4f4a63d05e7c8058d85df32779d07`;
authorizer `/root`; reused repair author `/root/repair_budget_replan_impl`;
future verifier `/root/repair_budget_replan_review`; exact G006/G008 scope;
the two open issue path/id/hash tuples; two v03 report hashes; two rejected
candidate hashes; two complete v03 source-tree hashes; and a fresh,
episode-local, non-symlink post-finalization review root. The exact issues and
reports separately bind historical discovery reviewer
`/root/ep8_review_v03_b`. That historical identity remains admissible only in
the immutable discovery bundle and must differ from the future verifier. The
v1 proposal path/hash and `/root/ep8_g006_g008_v04_author` are rejected rather
than read-compatible fallbacks. It reopens the consumed continuation and
extension rows plus released parent reservation under the ledger lock. Their
sealed actual is 12,049,777 raw input-plus-output, 269,861 uncached input,
44,620 output, and 11,860 reasoning tokens. The observed prior active duration
is approximately 3,728 seconds. Exact retries rehash all inputs and revalidate
those consumed/released/no-refund rows. Re-hashing a changed ledger, copying an
issue under another filename, or presenting a partial output set fails closed.

`start-independent-review-repair-wrapper` accepts only the sealed repair
author and one of the two exact scenes. The first wrapper creates one
deterministic shared reservation; the second must attach to it with the
identical full execution signature: actor identity, model, reasoning effort,
phase, purpose, role, allocation, active allocation, token-source kind/path,
baseline, accounting identity, and phase-instance ID. The expected accounting
identity and execution-signature hash are recomputed rather than inherited
from wrapper one. The common local caps are 1,500,000 raw
input-plus-output, 100,000 uncached input, 20,000 output, 8,000 reasoning, and
1,800 active seconds. An allocation of 1,501 active seconds is valid; 1,801 is
not. No base episode, stage, phase-envelope, or ordinary task-cap value is
increased.

`record-independent-review-repair-checkpoint` accepts only the ordered
schedule:

```yaml
300: issues_reports_read_and_two_scene_change_preservation_plan
600: source_patches_and_scene_specific_causal_fixes_present
1200: both_smoke_renders_and_math_layout_audits_started
1500: both_30fps_animatics_dense_qc_contact_sheets_and_key_frames_ready
1800: both_self_reviews_and_artifact_snapshots_sealed_hard_stop
```

Each `lecture-animation-independent-review-repair-round-checkpoint-v1` binds
the authority hash, elapsed claim, requirement, both current source-tree
snapshots, both output-root snapshots, concrete evidence, and the previous
checkpoint hash. The round state and ledger store the forward chain.
Duplicate exact commands are idempotent; replacement evidence, skipped order,
late wall-clock submission, elapsed regression, output escape, or a checkpoint
file not represented in the state chain fails closed. A completed two-scene
round cannot finalize without the 1,800-second hard-stop checkpoint. Under the
finalizer lock, all five checkpoint paths are reopened and rehashed as one
complete entity chain. Schema, self-hash, exact schedule, authority and
lineage, previous-hash link, elapsed/requirement pair, current source/output
snapshots, and exact state/ledger hash equality are revalidated. Missing,
altered, duplicated, skipped, orphaned, partial, forged-state, or forged-ledger
checkpoint evidence fails closed.

`end-independent-review-repair-wrapper` writes only a terminal wrapper state
and scene-local artifact snapshots. Both wrappers must already share the
reservation. A complete result requires real artifacts within its exact
output root; abandoned or blocked remains a separate artifact result. Wrapper
end never writes actual usage, releases the reservation, consumes the round,
closes an issue, or grants a refund.

`finalize-independent-review-repair-round` is the only accounting commit. It
requires both exact terminal wrapper states and unchanged open discovery
issues. It derives one shared actual from all four explicit dimensions or one
shared usage-baseline delta. If neither is observable, it stores
`token_observed: false` and `actual: null`. In one locked transition it appends
two scene phase events carrying the same accounting identity, reservation,
allocation, actual, and budget result; writes
`lecture-animation-independent-review-repair-round-final-v1`; releases the
reservation once; and marks the lineage round consumed once. Aggregate
accounting deduplicates the two event wrappers by that shared identity.
`artifact_result` never substitutes for `budget_result`. `local_overrun` and
`token_unobserved` persist all evidence, release and consume without refund,
keep both issues open, and return nonzero.

The finalizer preflights both its requested phase log and canonical central
log. Any one-sided event, receipt without exactly two matching events,
released reservation without receipt, partial ledger/state write, changed
explicit actual on retry, or duplicate accounting row fails closed. Path
escapes, symlinks, changed source/issue/report/candidate bytes, cloned issue
identity, early release, and any full execution-signature drift are rejected
before any successful transition.

`record-independent-review-repair-result` accepts only the frozen verifier,
the exact consumed final receipt path/hash stored in round state and ledger,
and one sealed review submission beneath the authority's fresh review root.
It reopens the released reservation and both canonical logs and requires exact
receipt actual/budget/accounting equality plus exactly two matching scene
events in each log. An alternate self-hashed receipt, missing ledger row,
partial event set, or changed actual is rejected.

The fresh submission must be created after finalization by the frozen verifier
with explicit author recusal. It binds the final receipt, both terminal wrapper
hashes, both terminal candidate hashes, and nonempty evidence for each of the
five hard review layers; every evidence row binds a supplied artifact path and
hash inside the fresh root. Discovery issues/reports/candidates/source
snapshots, pre-finalization files, symlinks, outside-root paths, and any hash
already present in the authority discovery bundle are rejected. A pass records
`independent_review_complete`; a revise records the terminal state
`root_cause_replan_required`, returns nonzero, and explicitly sets
`automatic_next_round_authorized: false`. There is no r02 transition.

`snapshot-iteration` writes `lecture-animation-skill-iteration-snapshot-v2` with the skill tree hash, rules hash, source-log hashes, review behavior, human outcomes, reviewer switches, measured phase durations, and artifact counts. `compare-iterations` reports quality, efficiency, and observability separately. Missing human outcomes or phase timings remain explicit missing data and must not be converted into a favorable score. A comparison whose two snapshots name the same episode is `same_episode_tooling_only`: quality and efficiency verdicts remain `insufficient_data` while raw deltas and observability changes stay visible.

`begin-production-batch` writes `lecture-animation-production-batch-v2` with scene slugs, skill hash, start time, a five-hour batch target, and the hash of the preexisting episode efficiency contract. The default complete-episode contract is eight hours of measured active critical-path time, including a reserved forty-five-minute retrospective; `human_wait` and machine-offline pauses remain separate. The cumulative token limits are 50,000,000 raw input-plus-output tokens, 2,000,000 uncached input tokens, 300,000 output tokens, and 100,000 reasoning tokens, with an advisory warning at 75 percent. These limits constrain episode totals rather than concurrency rate. `batch-status` reads the canonical shared ledger named by that contract rather than waiting for worktree merges.

`batch-status` reports batch and episode critical-path time, aggregate agent-seconds, concurrency overlap, token totals and ratios, full versus diagnostic review counts, review-artifact count, phase-telemetry gaps, stale human outcomes, and recurrence of previously accepted human-review regressions. `EPISODE_ACTIVE_BUDGET_EXCEEDED` and `EPISODE_TOKEN_BUDGET_EXCEEDED` are hard failures. `TOKEN_BUDGET_NEAR_LIMIT` is advisory and requires task compaction and replanning. When a prior `must_check_in_future` `pattern_key` appears again as a current human-review issue, `KNOWN_HUMAN_REGRESSION_RECURRED` makes `--require-clean` fail. `--require-clean` also turns duplicate shared-phase identities, incomplete phase/token evidence, stale human outcomes, semantic escapes, and artifact explosion into a nonzero gate. `--historical` permits read-only post-integration analysis when the original worktree or planning hashes have advanced, while recording those differences as alerts. Budget failure is an escalation signal, never a quality exemption.

`record-outcome` derives `outcome_key` from the complete outcome payload and appends it exactly once, so retrying a command does not inflate human-review counts. `finalize-episode` is the only normal media/production close transition. It requires one durable human-pass outcome per scene, terminal issue statuses, scene-local exact artifacts, required final media/timing artifacts, a `--finalization-manifest`, and complete batch coverage in parallel mode. The finalization manifest must bind the exact upload MP4, every editorial character clip and asset hash, word window, semantic anchor, protected rectangle, standard rhythm cue or evidence-backed omission, and one before/on pixel-difference row per overlay. The final alignment must contain a short next-topic preview followed by the exact phrase `我是结束乐队的键盘手，下个视频见`; the CLI requires exactly one Sumino carrier covering that complete sign-off word window while the identity/farewell remain absent from the final SRT. The action is not fixed to `talking`; it must be nonempty, registered in the bound Sumino asset metadata, semantically appropriate for the narration, and pass every clip/asset, timing, protected-region, pixel-QC, density, subtitle, and screen-text gate. Parallel completion additionally requires the v2 supervisor session to have passed `finish`, with no active/blocked assignment, pending/blocked task, or unused replacement authorization. The completion receipt records historical identity and replacement counts plus the finalization-manifest hash and sprite verdict. Finalization atomically marks scenes `assembled`, closes supplied batch contracts, seals the final assembly, and writes `lecture-animation-episode-completion-v2`. A missing outcome, stale open issue, provisional scene, missing file, uncovered parallel scene, live supervisor roster, stale sprite hash, missing pixel evidence, or absent mandatory sign-off blocks completion.

For every directional sprite action, the same manifest additionally records
`asset_facing_direction`, the explicit `mirrored_horizontally` boolean,
`rendered_gesture_direction`, and `gesture_target_rect`. The gate derives the
rendered direction from the asset direction and mirror state and requires the
target rectangle to lie completely inward along that direction. It also scans
both the final delivery package and episode review/evidence tree for
AppleDouble `._*` files and blocks closure when any remain. These mechanical
checks supplement, rather than replace, exact
on/late-frame independent review of the actual gesture and target.

After the retrospective phase, `close-episode-efficiency` is the final process-compliance transition. It validates the contract-bound terminal delivery clock, exact completion/portability final-video path and SHA-256, zero active reservations, the canonical phase ledger, required global phases through retrospective, per-scene phase pairs, token observability, active time, all four token ceilings, valid task-capsule resource evidence on every completed non-wait event, zero known-regression recurrence, zero automatic false pass, and human-issue scene rate below the sealed quality threshold. Quality, human-review, finalization-lineage, and active-reservation integrity errors always fail. Operational errors fail only when their bound metric mode is `enforce`; otherwise they remain explicit nonblocking evidence. The receipt's independent `workflow_target_met` and `eight_hour_delivery_met` fields must both be true before claiming success. A policy-compliant close atomically marks the contract completed and writes `lecture-animation-episode-efficiency-close-v1`; no mode erases prior usage. Tool installation or a same-episode snapshot is not evidence of success without this receipt from a matched future episode.

Retrospective completion evidence is release-lineage specific. If a newer
approved upload master exists than the video hash carried by either the episode
completion receipt or the latest passing portability receipt,
`episode-retrospective --require-finalized` must fail with
`stale_finalization_evidence_for_latest_master`; an older successful receipt
cannot certify a replacement publication master.
