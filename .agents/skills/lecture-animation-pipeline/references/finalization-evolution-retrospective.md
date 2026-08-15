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

## Finish An Approved Episode

Treat the exact user phrase `可以收尾了` as explicit approval of the currently
presented episode candidate and authority to run the standard finishing route.
The equivalent phrase `可以四K导出整集了` also authorizes the render/assembly
route, but does not by itself authorize a source/control commit unless the user
also says `提交`, `commit`, or `可以收尾了`.

Before acting, read `references/finalization.md` completely. Refuse to start if
any scene lacks durable human approval, any repair invalidated the approved
manifest, or the final source/audio/subtitle inputs cannot be resolved by hash.
Do not ask the user to repeat the standard options: use the latest approved
series precedent and report any discovered exception.

The standard route is one atomic evidence chain:

1. render every approved source scene at native `3840x2160p30`;
2. preserve approved scene-local timing and audio, then offset-assemble without
   silently retiming internal animation;
3. proofread the reader SRT against formal script/timeline text, burn it into
   video pixels, and keep the corrected reader SRT as an upload sidecar;
4. apply the approved BGM recipe and a restrained, word-locked series-character
   rhythm: resolve `confused`, `aha`, and `thinking` roles from the current
   mathematics; any number of simultaneous characters may be allowed when each
   has a specific teaching role and they support rather than compete with teaching;
   do not use a whole-episode count cap, but hard-fail formula/subtitle/active-
   object collisions, evidence-check rapid entrance windows, and require
   simultaneous characters to occupy disjoint safe regions; distinct
   overlapping cues additionally need an evidence-bound safe-area and visual-
   hierarchy verdict rather than a count-based rejection;
   every such verdict must use finalization-QC JSON that binds its exact
   overlay indices and hashes the reviewed frames or masks; pixel-overlap
   values must match the bound evidence rather than exist only as manifest
   assertions; the gate must decode common-dimension PNG frames/masks and
   recompute the intersections from pixels;
   every pointing gesture must machine-bind intrinsic asset direction, mirror
   state, resulting screen direction, and a mathematical target rectangle,
   then pass exact on/late-frame inspection instead of trusting the action name;
5. end every normal episode with one short spoken preview of the next
   mathematical topic and then the exact spoken line
   `我是结束乐队的键盘手，下个视频见`; require exactly one hash-bound Sumino
   overlay that starts before the aligned `我` and covers through `下个视频见`;
   its action is not fixed to `talking`, but must be nonempty, registered in the
   bound Sumino asset metadata, semantically appropriate for the current
   narration, and backed by the validated clip/asset hashes; never render the
   identity or farewell text on screen; the episode may preserve its final
   mathematical frame or use a separately approved ending visual;
6. require the finalization manifest to bind every character/action/semantic
   anchor/word window/protected rectangle/asset and clip hash, with a documented
   collision-evidence omission for any unused standard rhythm role;
7. run independent subtitle, sprite, media, decode, duration, loudness,
   boundary, hash, and scoped AppleDouble-cleanliness QC across both the
   delivery tree and episode review/evidence tree; then write one
   finalization manifest and contact sheet.

Unless the user explicitly names a different BGM or mix configuration, the
finishing trigger always reuses the established series BGM source and exact
validated mix recipe; do not omit music and do not ask the user to restate it.

`可以收尾了` additionally grants staging and committing only the already
approved episode source/control files and finalization receipts after every
finishing gate passes. It never grants push, upload, deletion of intermediates,
worktree cleanup, or replacement of the approved mathematical picture. A
failed finishing gate blocks commit and returns the bounded layer to its
original owner.

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

At final media delivery, first run `seal-upload-package` against the exact
viewer-facing bytes, then run `finalize-episode` with both the fresh
`--upload-package-receipt` and `--episode-readiness` receipt. It refuses to close the episode unless every
scene has one durable human-pass outcome, every issue JSON has a terminal
status, every scene has reached at least `audio_aligned`, every required final
artifact exists, and every parallel scene is covered by a supplied batch
contract. A parallel episode must also supply a v2 supervisor session already
closed by `supervisor_watch.py finish`; the command scans every
`review/v2/supervisor*.json`, so an open duplicate, active/blocked agent,
pending/blocked task, or unused replacement authorization blocks finalization.
It then atomically marks the progressive production scenes assembled, closes
the supplied batches, seals the final assembly, and writes one
media/production completion receipt. In the eight-hour workflow, use that
receipt to advance every already approved delivery-board row to `assembled`;
the terminal clock rejects a missing row or mismatched human outcome. This does
not yet prove the eight-hour complete workflow, because retrospective is still
outstanding. Do not hand-edit
`progressive_production.json` or leave batches or supervisor assignments active
after upload.

Before final delivery or worktree deletion, run `audit-portability
--require-clean`, and promote accepted ignored/generated assets into the
canonical checkout with `promote-scene`. A merged branch is not evidence that
audio, alignment, review media, or final video survived. Current authoritative
text must use repo-relative paths; historical absolute provenance needs a
current rebuild manifest that supersedes it.

Measure work phases rather than estimating total minutes from memory. Wrap planning, design, authoring, render, review, repair, TTS, ASR, finalization, retrospective, and human wait with `phase-start` / `phase-end`; render and TTS also require a classified `--phase-purpose`. Record actor role, model, reasoning effort, prompt/artifact bytes, files read, and available input/cache/output/reasoning token counts. Reused concurrent work must pass one stable `--shared-work-key`, which derives the same `phase_instance_id` and accounting identity across scene and run wrappers. For legacy reservations that predate those ledger fields, projection and statistics derive the identity from the bound timer state's shared-work key without rewriting the reservation or its original `phase_instance_id`. Probable legacy duplicates without recoverable state remain reported rather than silently multiplied. Planned scenes in `progressive_production.json` remain the denominator, and zero eligible phase events mean zero observability rather than complete coverage. `batch-status` separates accepted review rounds from gate-rejected submissions, classifies rejection/finding causes, and reports self-review capture rate, retry time, recursive artifact size, critical path, aggregate agent-seconds, concurrency overlap, and cumulative episode token ratios. At each skill change, write a pre-change and matched post-change record with `snapshot-iteration`, then use `compare-iterations`. If both snapshots name the same episode, the tool must label quality and efficiency `insufficient_data`; only tooling and observability changed under the same evidence window.
Only phase events ending with `result=completed` satisfy per-scene coverage;
design, authoring, render, and review are mandatory, and any scene that entered
repair, has a repair attempt, or received a durable revise/blocked outcome also
needs a completed repair phase.

## Retrospect On A Finished Episode

Treat the exact user phrase `复盘一下` as authority to run the standard
post-episode retrospective for the most recently finished episode in the
current task context. Do not ask the user to repeat which logs, metrics, review
records, or Git evidence to inspect. If the context names no episode, infer the
newest episode with a valid completion receipt or approved final master; ask
only when two candidates are equally current.

Before acting, read `references/postmortem.md` completely. Start with the
deterministic quantitative evidence pack:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" episode-retrospective \
  --repo-root . \
  --episode "$EPISODE" \
  --output "$EPISODE/review/evolution/postmortem.json" \
  --require-finalized
```

Then inspect the bounded evidence paths named by that pack and write
`$EPISODE/review/evolution/postmortem.md`. Report numbers before
interpretation: observability coverage, critical-path and aggregate-agent time,
phase/token distribution, retry time, review and repair rounds, human
false-passes, recurring issue patterns, artifact growth, and coordination
churn. Missing telemetry remains an explicit denominator or unknown; never
turn it into a zero. Missing review, author-self-review, or repair ledgers make
their derived counts and rates `null` with `unknown_missing_ledger` status.
Even if earlier work already exceeded an outer token ceiling, the mandatory
retrospective must still start within its own sealed phase envelope, preserve
the original overflow fields, and leave efficiency closeout failed rather than
silently skipping the analysis.

Classify root causes, rank bottlenecks by measured critical-path cost,
recurrence, quality risk, and implementation cost, then change the smallest
enforceable layer in this order: deterministic checker, inference/retrieval,
narrow conditional contract, prose. Apply high-confidence pipeline fixes,
tests, and documentation during the same retrospective; leave subjective
teaching or visual-taste choices as recommendations unless the user already
made them durable feedback. Snapshot the pre-change state, validate the
candidate, run an independent forward test on raw artifacts, and record the
post-change hypothesis for the next matched episode.

After the retrospective phase has ended, close the episode efficiency contract:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" close-episode-efficiency \
  --repo-root . --episode "$EPISODE" \
  --efficiency-contract "$EFFICIENCY" \
  --metric-policy-profile "$METRIC_POLICY" \
  --delivery-clock "$DELIVERY_CLOCK" \
  --completion-receipt "$EPISODE/episode_completion.json" \
  --output "$EPISODE/review/evolution/episode_efficiency_close.json"
```

This is the final process-compliance transition. Quality, human outcome,
scene-phase, and regression errors always fail. Token, time, aggregate
telemetry, and context-size errors fail only when their sealed mode is
`enforce`; otherwise the receipt records them under
`nonblocking_operational_errors` and may close without replaying production.
The receipt separately exposes `workflow_target_met` and
`eight_hour_delivery_met`: both must be true before claiming the eight-hour
workflow succeeded, regardless of exit code. No mode resets or erases usage.

`复盘一下` authorizes read-only repository analysis plus scoped edits, tests,
and a local commit of the retrospective and resulting Skill/tooling
improvements. It does not authorize pushing, uploading, deleting media,
removing worktrees, or changing already approved episode content.

## Resources

- `scripts/pipeline_v2_lib/narration_workflow.py`: profile-bound narration
  authoring/review state, exact user outcome, TTS lock, animation release, and
  exceptional post-animation narration repair.
- `references/narration-workflow.md`: narration lifecycle, permissions,
  evidence contract, and downstream invalidation rules.
- `references/audience-profiles/registry.json`: explicit audience profile
  registry with no global default.

- `scripts/pipeline_v2.py`: backward-compatible CLI entrypoint and domain command adapters.
- `scripts/pipeline_v2_lib/core.py`: dependency-free hashes, timestamps, errors, and canonical serialization.
- `scripts/pipeline_v2_lib/storage.py`: process locks, atomic JSON replacement, locked JSONL append/deduplication, and read-modify-write primitives.
- `scripts/pipeline_v2_lib/review_state.py`: persistent review-session and attempt transactions.
- `scripts/pipeline_v2_lib/governance.py`: main-agent review authority, live-policy blocker, and pending-repair gates.
- `scripts/pipeline_v2_lib/visual_plan_review.py`: workflow-v2 independent complete-plan gate; optional Keynote/keyframes are supporting evidence only.
- `scripts/pipeline_v2_lib/design_readiness.py`: historical workflow-v1 low-cost-animatic compatibility gate; it cannot authorize new workflow-v2 production.
- `scripts/pipeline_v2_lib/episode_ops.py`: episode readiness, compact task capsules, canonical promotion, and rebuild-portability gates.
- `scripts/pipeline_v2_lib/metrics.py`: phase deduplication, retry/hotspot metrics, and review error classification.
- `scripts/supervisor_watch.py`: durable continuous-monitoring state, low-noise milestone classification, and finish gate for subagent supervision.
- `scripts/state_store_stress.py`: multi-process contention and crash-safety diagnostic for the file state backend.
- `references/authoring-philosophy.md`: novice-centered layered cognitive staging, dynamic stage topology, and executable M/D/A visual grammar.
- `references/rules.json`: single machine-readable rule registry.
- `references/contracts.md`: scene-plan, manifest, and review submission contracts.
- `references/evolution.md`: rule lifecycle and metric-driven compaction.
- `references/postmortem.md`: quantitative-first post-episode retrospective,
  bottleneck attribution, bounded Skill evolution, and the `复盘一下` trigger.
- `references/preflight-portability-and-handoffs.md`: cheap episode gates,
  lossless low-token coordination, canonical asset promotion, and worktree-safe
  rebuild audits.
- `references/finalization.md`: post-approval 4K, burned-subtitle, Sumino,
  BGM, independent-QC, manifest, and commit contract triggered by `可以收尾了`.
