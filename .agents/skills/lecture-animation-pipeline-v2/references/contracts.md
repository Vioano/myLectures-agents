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

For parallel production, the main agent writes the boundary contracts before delegation. The episode spine's `batch_partition` must cover every timeline scene exactly once, in order, with three to five scenes per batch. Each partition row fixes entry and exit compatibility keys, identity carriers, visual states, narration locks/text, shared handoff meanings, audio handoffs, and the explicitly free interior. Neighboring rows must use the same key, carriers, handoff meaning, and audio handoff at their shared boundary; the CLI rejects gaps, overlaps, reorderings, and incompatible handoffs. Each batch plan must reproduce its bound spine row and narration-style contract exactly. Internal adjacency contracts likewise fix outgoing/incoming visual states, narration meaning/text/lock, audio handoff, identity carriers, and the free interior. `begin-production-batch` also requires `--author-id` in parallel mode and binds that production subagent identity into the emitted contract.

Parallel `begin-production-batch` additionally verifies Git isolation: `--repo-root` must be the root of a dedicated checkout at `/Volumes/bocchi/myLectures-worktrees/<agent-or-task>/`, and its current branch must begin with `agent/`. The emitted batch contract records both worktree path and branch. The canonical checkout is reserved for main-agent planning, integration, and final review.

An `exact` narration lock preserves the clause verbatim. An `intent` lock permits wording changes only when the named mathematical object, causal claim, learner state, and handoff action remain unchanged; `freedom_inside` must state the allowed scope. Changing a fixed boundary state, compatibility key, carrier, or locked narration meaning is an upstream contract change and invalidates downstream hashes.

### Progressive Locking

`scene_plan.json` adds `planning_chain.episode_spine_hash` and `planning_chain.batch_plan_hash`. The review manifest includes both upstream artifacts. A changed spine or batch plan is a material contract change, requires downstream revalidation, and cannot use a diagnostic review as the final gate.

The planning resolution is therefore:

1. lecture notes plus provisional whole-episode narration and storyboard;
2. coarse whole-episode visual spine;
3. medium-detail three-to-five-scene batch plan;
4. just-in-time scene script and visual co-design;
5. low-cost animatic, then exact scene-local audio/SRT/word timing/timeline;
6. final authoring and review;
7. offset-based final assembly.

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

New profiles use the autopilot contract. `compile-profile` writes a sibling `active_policy.json`, then binds its `policy_hash` into the profile. The live policy contains explicitly applicable `human_review`, `accepted_agent_feedback`, and `must_check_in_future` issue records plus their four-layer gate routing. Exact scene/group, explicit scene/tag, and global matches are enforced; loose keyword matches remain retrieval-only so unrelated feedback cannot invalidate a frozen scene.

## Active Author Design Chain

The author cannot retrieve precedents before a first-principles gate passes.

1. `begin-design` creates `lecture-animation-design-challenge-v2` from the profile. It contains scene objects, narration, driver, risk tags, and regressions, but no precedent hits.
2. The author writes `lecture-animation-design-deliberation-v2` with `phase: first_principles` and `history_consulted: false`.
3. `validate-design-deliberation` creates `lecture-animation-design-gate-v2`.
4. `retrieve-design` creates `lecture-animation-precedent-packet-v2` from the validated problem signature.

The deliberation requires:

- `novice_model`: `known_before`, `likely_wrong_inference`, `needed_visual_evidence`, `success_prediction`;
- `problem_signature`: learner operation, invisible relation, invariant, perceptual target, working-memory burden;
- one or more `hypotheses`, with at least two for dense or rejected scenes;
- each hypothesis: stage logic, view mapping, math-state logic, attention logic, identity invariants, novice advantage, failure risk, mute-test prediction;
- exactly one selected hypothesis and a concrete selection reason.

The CLI rejects generic, scene-independent, or near-duplicate hypotheses. The precedent packet contains separate reviewed-production and old-skill-guidance hits. It never copies an entire guidance library into context.

## Dynamic Scene Plan

`lecture-animation-scene-plan-v2` binds the four design hashes and the selected hypothesis. It also requires:

- `planning_chain`: the current `episode_spine_hash` and `batch_plan_hash`;
- `learning_contract`: novice start state, core claim, likely misconception, visible evidence, success test;
- `math_driver` and a novice-state causal ledger;
- typed `math_objects`, each with mathematical type, definition, real driver IDs, and parameters explicitly marked `math` or `display`;
- `display_mappings`, each naming its mathematical source, mapping mode, display-only parameters, preserved invariants, disclosed distortions, forbidden inferences, and validation method;
- `visual_bindings`, binding every primary visual object to exactly one mathematical object, display mapping, driver set, and runtime owner;
- `stage_regions`: stable cognitive roles with teaching job, primary object, and detail strategy;
- `region_relations`, each with a stable `relation_id` and a declared visual encoding, plus `region_refinements` and `identity_map`;
- `stage_states`: time intervals with `math_state_id`, learner task, and active region placements;
- `stage_transitions`: transition interval, pedagogical trigger, focus transfer, `continuity_mode`, identity carriers, interpolation contract, context policy, continuity test, and M/D/A change vector/order. Use `identity_preserving` with one or more named carriers, or `full_clear` with an empty carrier list and an explicit continuity-break contract; never invent a carrier merely to satisfy the schema;
- beat-level knowledge-before, visual evidence, and permitted learner inference;
- for `repeat_rejected` scenes, a monotonic concept ledger on every beat: stable `beat_id`, exact `concepts_available_before`, at most one new concept by default, at least 1.2 seconds of settling time, pointing targets, and a non-symbolic `evidence_mode`;
- formula history and token choreography for formula-dense scenes, including non-geometric emphasis or an explicit restore policy;
- `clause_locks` for repeat-rejected scenes, binding each major spoken claim to one object and expected visible change;
- precedent decisions and regression prevention.
- `math_object_invariants` for every primary stage object: stable invariant id, exact mathematical claim, expected relation, runtime evidence type, and checkpoints.

New autopilot profiles use contract version 4. Supported display modes are `identity`, `uniform_scale`, `local_zoom`, `nonlinear_magnifier`, `projection`, `sampling`, `log_length`, `pedagogical_parameter`, `equivalent_deformation`, and `novel`. Modes that visually distort scale or geometry must disclose the distortion and forbidden learner inferences. `equivalent_deformation` also requires an equivalence basis; `novel` requires a counterexample probe. Display-only parameters cannot drive mathematical state. Version 4 additionally makes implementation-ready repair contracts and finding lineage mandatory after every independent `revise`.

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
- `semantic_events` binding every repeat-rejected beat to distinct visible cause/result objects, introduced concept ids, action count, and a measured settle interval;
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
- missing formula cues or attention handoffs;
- fragmented formula rows, alignment-anchor drift, unreadably fast traced-box emphasis, or emphasis geometry that fails to return to rest;
- stage motion shorter than the readable threshold, default-smooth stop-start halves, or a transition without a continuous-path declaration;
- missing relation encodings, long connectors, or connectors crossing protected graphs;
- mismatch between planned stage state and runtime state;
- mismatch between declared and computed M/D/A changes.
- missing cause-result checkpoints, concept-ledger drift, more than two simultaneous novice actions, formula-only evidence, or less than the planned novice settling interval.
- changed on-screen text inventory relative to the frozen approved predecessor;
- collisions among automatically discovered `Text`, `Tex`, `MathTex`, `DecimalNumber`, or `Integer` descendants, even when the author forgot to register them manually.
- absent, failed, object-mismatched, or evidence-mismatched `math_invariant_checks` for any planned mathematical-object invariant.
- missing or drifted mathematical bindings, mismatched runtime drivers, display mappings applied to the wrong source, undisclosed visual distortions, or forbidden mathematical inferences caused by a screen optimization.

The report includes `gate_coverage` for four independent mandatory layers:

- `layout`: frame, region, subtitle, typography, spacing, container, child-atom, and overlap evidence;
- `math_object`: object identity, driver relation, coordinates, formula operations, and declared invariants;
- `timing_attention`: cue locks, stage motion, stale-object exit, and attention handoffs;
- `novice_causality`: cause, visible action, result, concept order, and settling evidence.

A pass requires all four. The mathematical-object layer extends layout checking; it never replaces it.

The telemetry and report are both hash-bound to the review manifest.

## Author Self-Review Falsification Probe

Contract version 5 requires a separate `lecture-animation-self-review-probe-v2` before the author receipt. `prepare-self-review-probe` derives the four layers, timestamps, object IDs, and risk-tier probe count from the frozen manifest and scene plan. `seal-self-review-probe` requires each probe to contain:

- expected and actually observed mathematical/display state;
- an explicit attempt to falsify the claimed correctness;
- a decoded frame that exists inside the frozen QC artifact, its verified on-disk SHA-256, and the exact frozen review-MP4 source SHA-256;
- an independent numeric measurement or coordinate recomputation with `expected_value`, `actual_value`, and `tolerance_value`; the CLI recomputes the pass result instead of trusting the submitted boolean;
- `falsification_not_found` only after that independent check passes.

Telemetry and `authoring_qc` cannot prove themselves. Human-rejected and repeat-rejected scenes require two ranked adversarial probes per layer. The sealed probe is embedded in and hash-bound by `author_self_review.json`, so replacing either the candidate or the probe invalidates handoff.

## Author Self-Review Receipt

`freeze-review` creates the candidate manifest first. `prepare-author-self-review` derives anchors, artifact hashes, object IDs, and prior findings so the author does not rewrite contract boilerplate. `seal-author-self-review` then validates and hashes `lecture-animation-author-self-review-v2` against that manifest. The receipt requires:

- owner, author model, author agent id, and a positive self-review round;
- one uninterrupted playback with audio monitored and one muted playback with teach-back and prediction;
- passing sweeps for all four hard-gate layers at every CLI-derived anchor;
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

Before a `revise` submission can verify, `prepare-review-exhaustion` and `seal-review-exhaustion` require `lecture-animation-review-exhaustion-v2`. Every finding remains `open` and appears exactly once under one `root_issue_id`; `fixed` or `closed` is illegal in an independent review because closure belongs to the repair response. Each root cluster records the complete affected interval, object IDs, existing source anchors, upstream causes, downstream symptoms, dependent artifacts, sibling risks, preservation requirements, repair-induced risks, and evidence from all four hard-gate layers. Every layer carries at least one real decoded QC frame. Each of the four unclustered searches carries at least two such frames, binding their on-disk SHA-256 and the frozen review-MP4 SHA-256. Partial lists, missing files, fabricated hashes, duplicate root clusters, or uncovered findings are rejected.

`compile-repair-contract` freezes every root cluster and every open finding, their lineage, code guidance, and the rejected manifest's artifact hashes. `prepare-repair-response` binds the author to a newly frozen candidate. Each response resolution must include a root-cause diagnosis, exact code-symbol changes, the actual changed artifacts, passing acceptance results, passing preservation checks, and passing probes for every predicted new risk. `verify-repair-response` writes `lecture-animation-repair-gate-v2`; a failed or stale gate blocks author self-review.

`review/evolution/repair_attempts.jsonl` or the explicitly selected attempt log records accepted and rejected repair gates. Full review attempts also record `finding_lineage_counts` and the hashes of the repair contract, response, and gate. These fields support immediate-fix rate, incomplete-fix recurrence, repair-induced regression rate, and delayed-discovery rate without reconstructing history from prose.

All mutable state transitions go through `pipeline_v2_lib.storage`. JSON files use a process lock plus same-directory temporary file, `fsync`, and atomic replacement. JSONL attempts use a process lock, one complete append, and a content-derived unique key. Review-attempt commit locks the attempt log and session together, stores applied attempt IDs for crash recovery, increments a session revision, and rejects a new submission whose expected session hash is stale. Retrying an already committed verification key is idempotent.

## Review Attempt Log And Derived State

`verify-review` appends one `lecture-animation-review-attempt-v2` row per unique submission and gate result to `review/evolution/review_attempts.jsonl`. Re-running the same verification produces the same `verification_key` and is deduplicated. Failed CLI gates are recorded as well as accepted reviews.

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

`begin-review-batch` writes `lecture-animation-review-session-v2` contract version 4. It requires both `author_agent_id` and `reviewer_agent_id`, rejects equality, and binds the author self-review to the same author session before any capsule or review can verify. Pre-v4 sessions must be recreated. A full or diagnostic review must repeat the same `reviewer`, `reviewer_model`, `reasoning_effort`, and `reviewer_agent_id`. `reviewer_tier: light` additionally requires an eligible `lecture-animation-reviewer-certification-v2` bound to the exact model, effort, benchmark hash, and current rules hash. A human false pass suspends light certification. Replacing an active reviewer requires `--replace --replace-reason`.

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

`lecture-animation-review-capsule-v2` is the compact execution contract for review. It contains applicable rule IDs and evidence fields, required object IDs, four-layer timestamps, active pattern keys, three deterministic blind checkpoints, and the exact review-MP4 hash. `lecture-animation-blind-review-receipt-v2` seals the novice report before source and contracts are exposed.

## Diagnostic Repair Contract

`prepare-diagnostic-review` accepts only a prior `revise` review, a newly frozen manifest for the same scene, a current author self-review that resolves every prior finding, and a valid `lecture-animation-change-impact-v2`. The impact record must name exact changed objects, time windows, affected hard-gate layers, actual changed artifacts, and assert that semantic contracts stayed fixed. It is hash-bound to both manifests. Missing or invalid impact proof forces a full review.

`lecture-animation-diagnostic-review-v2` must contain one `finding_checks` row per prior finding and one `regression_samples` row at every packet timestamp. Evidence outside required windows is rejected. Its only verdicts are `revise` and `diagnostic_fix_verified`. It cannot produce `user_review_pending`; after a diagnostic pass the state machine still requires a fresh full review manifest and complete standards review.

`choose-review-mode` compares the two frozen manifests. Changes to policy, profile, design, plan, timeline, audio, subtitles, or text contracts require a new four-layer full review. If only implementation/render evidence changed under the same semantic contracts, a diagnostic review is eligible. This is adaptive routing, not a cap on full reviews. Three prior full reviews trigger root-cause re-planning instead of permission to stop inspecting the whole video.

## Phase And Iteration Records

`phase-start` creates a hash-stamped active timer with actor role, model, reasoning effort, prompt bytes, artifact bytes, files read, and a reusable `phase_instance_id`. It snapshots cumulative token usage from `--usage-file`, `LECTURE_TOKEN_USAGE_FILE`, or the current Codex rollout discovered through `CODEX_THREAD_ID`. `phase-end` records the nonnegative delta; explicit token arguments are a fallback for workers that expose usage only at completion. Shared concurrent work uses the same instance ID and is counted once. Use one of: `design`, `authoring`, `render`, `review`, `repair`, `tts`, `asr`, `human_wait`.

Every phase event records `token_observed` and `token_source_kind`. Design, authoring, review, and repair are token-expected phases. Reports expose coverage, missing event IDs, phase token totals, observed total tokens, and uncached input tokens. Missing usage is not converted into a trustworthy zero.

`snapshot-iteration` writes `lecture-animation-skill-iteration-snapshot-v2` with the skill tree hash, rules hash, source-log hashes, review behavior, human outcomes, reviewer switches, measured phase durations, and artifact counts. `compare-iterations` reports quality, efficiency, and observability separately. Missing human outcomes or phase timings remain explicit missing data and must not be converted into a favorable score.

`begin-production-batch` writes `lecture-animation-production-batch-v2` with scene slugs, skill hash, start time, five-hour active-work target, and one-day episode target. `batch-status` reports critical-path wall time, aggregate agent-seconds, concurrency overlap, token totals, full versus diagnostic review counts, review-artifact count, phase-telemetry gaps, and stale human outcome logs. Budget failure is an escalation signal, never a quality exemption.
