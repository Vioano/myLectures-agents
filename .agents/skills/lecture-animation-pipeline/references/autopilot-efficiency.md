## Start An Autopilot Batch

Before planning begins, the main agent must create one episode-level efficiency contract in the canonical production checkout. It fixes the eight-hour Initialization-to-upload-ready delivery target, a separate forty-five-minute retrospective reserve, cumulative token observations or ceilings, quality targets, workflow-v2 pre-production gates, and one canonical phase ledger shared by every worktree. Rerunning the command is idempotent while the contract is active and cannot reset consumed time or tokens.

The efficiency contract is necessary but not a complete startup. Before the
delivery clock leaves `initialization`, `seal-episode-startup --require-clean`
must bind it together with the stable roster, dedicated integration/producer
worktrees, main acceptance reviewer, supervisor, metric policy, exact user
startup brief, review-video delivery mode, and the canonical phase ledger.
`transition-delivery-clock --stage lecture_approval` keeps the approved lecture
draft as its `--artifact` and additionally rejects a missing or stale
`--startup-receipt`.

```bash
EFFICIENCY="$EPISODE/review/evolution/episode_efficiency_contract.json"
python3 "$SKILL/scripts/pipeline_v2.py" begin-episode-efficiency \
  --repo-root . --episode "$EPISODE" \
  --delivery-clock "$DELIVERY_CLOCK" \
  --delivery-target-hours 8 \
  --retrospective-reserve-minutes 45 \
  --output "$EFFICIENCY"
```

Compile one episode-wide operational switchboard during Initialization. `*` is
the explicit all-scenes scope, so the profile does not pre-empt the later
user-approved lecture or freeze an invented scene roster. The actor wildcards
allow the same profile to cover Sol owners and local
TTS/ASR. Normal production defaults cumulative token/cost budget to `enforce`
and active time and telemetry to `observe`, while quality and user review are
immutable `enforce` gates. A bounded model experiment may explicitly switch
token cost to `observe` or `off`; prior usage remains in the ledger.

```bash
METRIC_POLICY="$EPISODE/review/evolution/metric_policy.json"
METRIC_AUTHORITY="$EPISODE/review/evolution/metric_policy_authority.json"
python3 "$SKILL/scripts/pipeline_v2.py" seal-user-authority \
  --repo-root . --episode "$EPISODE" --decision authorize \
  --exact-user-text '<verbatim current user authorization>' \
  --output "$METRIC_AUTHORITY"

python3 "$SKILL/scripts/pipeline_v2.py" compile-metric-policy \
  --repo-root . --episode "$EPISODE" \
  --policy-id episode-default-r01 \
  --parent-contract "$EFFICIENCY" \
  --user-authority "$METRIC_AUTHORITY" \
  --phase planning --phase design --phase authoring --phase render \
  --phase review --phase repair --phase tts --phase asr \
  --phase finalization --phase retrospective --phase human_wait \
  --scene '*' --actor-model '*' --actor-role '*' --reasoning-effort '*' \
  --active-seconds 28800 --expires-hours 24 \
  --output "$METRIC_POLICY"
```

`seal-user-authority` writes the required
`lecture-animation-user-authority-v1` schema with the exact user text and the
unchanged quality/task-cap declarations; do not synthesize broader authority
than the user's words. Pass `--metric-policy-profile "$METRIC_POLICY"` to
every `phase-start` and `batch-status`. A later user-authorized change first
seals its new verbatim authority, then uses `update-metric-policy` to create a
new profile; it never rewrites the old profile or earlier events.

Copy the unchanged hash-bound contract into each production worktree. Every `phase-start` requires `--episode "$EPISODE" --efficiency-contract "$EFFICIENCY"` plus explicit raw, uncached-input, output, and reasoning token allocations for that bounded task capsule. Batch-scoped work must also pass its sealed `--production-batch` contract and one exact member `--scene-slug`; a synthetic batch slug is rejected at start. For one shared action reused by several scenes, start one wrapper per covered scene and pass the same stable `--shared-work-key`, so scene coverage remains exact while the shared cost is deduplicated. The accounting identity excludes scene and run ID but binds episode, phase, phase purpose, actor model, actor role, and shared-work key. Before work starts, the CLI atomically records the reservation and identity. Episode or phase overage rejects a start only when the matching operational metric is `enforce`; `observe` and `off` preserve the same evidence without blocking. Every `phase-end` writes the actual event to the requested local ledger and, exactly once, to the canonical shared episode ledger, then releases the reservation. This makes concurrent work visible without turning an observation-only experiment into a production stop.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" phase-start \
  --repo-root . --episode "$EPISODE" \
  --efficiency-contract "$EFFICIENCY" \
  --delivery-clock "$DELIVERY_CLOCK" \
  --metric-policy-profile "$METRIC_POLICY" \
  --production-batch <production-batch.json> \
  --run-id <run-id> --scene-slug <exact-member-scene> \
  --phase <planning|design|authoring|render|review|repair|tts|asr|finalization|retrospective|human_wait> \
  --actor-model <model> \
  --active-seconds-allocation <max-active-wall-seconds> \
  --raw-token-allocation <max-raw> \
  --uncached-input-token-allocation <max-uncached> \
  --output-token-allocation <max-output> \
  --reasoning-token-allocation <max-reasoning> \
  --state <active-phase.json>
```

Treat each allocation as the maximum for one concrete deliverable, not as permission to consume the whole episode remainder. `human_wait` reserves zero active seconds and zero tokens. Active-time reservations use projected intervals, so genuinely parallel tasks overlap instead of being naively added. The supervisor may launch a short high-concurrency burst only when the union of projected active intervals and the sum of token reservations fit the sealed episode contract.
For workflow-v2 TTS/ASR phases, append the current
`--episode-readiness`; these phases create the exact audio/timing evidence used
by the final plan. For authoring and every render, append the independently
sealed `--visual-plan-review`, the exact audio-aligned `--scene-production`,
and a `post_tts` episode-readiness receipt. These inputs are phase-specific and
are not required while the author is still writing or independently reviewing
the plan.

Start each three-to-five-scene production batch only after the episode spine and batch plan pass their contracts. The batch command binds both planning artifacts and the already active episode efficiency contract, then starts its measured five-hour batch budget. Delivery active time begins at Initialization and ends at verified upload-ready finalization. Explicit `human_wait` and machine-offline pauses are excluded from active critical-path time but must be reported separately; they cannot hide agent work. The forty-five-minute retrospective begins after delivery and has its own reserve, so a compliant contract contains eight delivery hours plus that reserve. These are efficiency gates, never permission to skip quality gates.

The command is mandatory for every production subagent. A chat assignment, Markdown checklist, or valid-looking JSON does not authorize implementation. The subagent must receive the emitted production-batch contract and must stop if `begin-production-batch`, `compile-profile`, any design validator, `validate-scene-plan`, `validate-authoring-qc`, manifest verification, or review verification fails. The main agent must reject work produced outside this chain.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" begin-production-batch \
  --repo-root . --episode "$EPISODE" \
  --efficiency-contract "$EFFICIENCY" \
  --batch-id <batch-id> \
  --scenes <scene-a,scene-b,scene-c> \
  --episode-spine "$EPISODE/episode_visual_spine.json" \
  --batch-plan "$EPISODE/review/v2/<batch-id>/batch_visual_plan.json" \
  --production "$EPISODE/progressive_production.json" \
  --author-id <production-subagent-id> \
  --supervisor-session "$EPISODE/review/v2/supervisor_session.json" \
  --target-hours 5 \
  --output "$EPISODE/review/v2/<batch-id>.json"
```

Wrap every planning, design, authoring, render, review, repair, TTS, ASR, finalization, retrospective, and human-wait phase with the existing phase timer. Run `batch-status` during production. It reports measured active time, full/diagnostic review mix, artifact growth, missing phase telemetry, stale human-outcome logs, and cumulative episode token use. An exceeded active-work budget forces a root-cause process review; it never grants a visual pardon.

The default complete-episode cumulative token contract is:

- raw input plus output: at most `50,000,000`;
- uncached input: at most `2,000,000`;
- output: at most `300,000`;
- reasoning: at most `100,000`;
- warning threshold: `75%` of any limit.

This contract measures total episode consumption, not instantaneous rate. A short, useful high-concurrency burst is allowed when the WIP contract and quality gates remain satisfied. At the warning threshold, `phase-start` and `phase-end` emit `TOKEN_BUDGET_NEAR_LIMIT` or `ACTIVE_BUDGET_NEAR_LIMIT`; finish the active checkpoint, stop optional exploration and repeated full-corpus rereads, compact the task capsules, and let the supervisor replan the remaining work. Operational limits block new work only when their user-authorized metric mode is `enforce`. In `off` or `observe`, overages and unknown telemetry remain visible but do not block TTS, authoring, rendering, repair, review, or finalization. Quality and user-review gates remain enforced in every mode.

Local TTS/ASR overrun recovery is a cold path. Load
`operational-recovery.md` only when measured evidence triggers it.

The state machine also protects future work before the total is exhausted:

- the first `225` minutes and `32%` of every token ceiling are unavailable to early planning/design/authoring/initial-production work, preserving review, repair, finalization, and retrospective capacity;
- the final `45` minutes and `7%` of every token ceiling remain unavailable until the retrospective phase;
- repair rerenders and classified post-readiness TTS retries may use the closure reserve, but cannot consume the retrospective reserve;
- a task that exceeds its own active-time or token allocation is always recorded at `phase-end`; it returns nonzero only when that operational metric is `enforce`, even when the episode total remains below the outer ceiling;
- an active reservation that has already outlived its allocation is always reported and must be ended or explicitly reconciled; it blocks new work only when active time is `enforce`, and it never disappears merely because its timer was not closed.

The outer reserves are not enough by themselves. Every non-wait task is also charged to one sealed phase envelope before it starts. Token dimensions are budgeted independently because reasoning, output, and cache-adjusted input do not have the same cost shape:

| Budget bucket | Active time | Raw | Uncached input | Output | Reasoning |
|---|---:|---:|---:|---:|---:|
| planning first pass | 45 min shared | 5% | 5% | 5% | 5% |
| planning quality repair | uses planning time | 2% | 5% | 9% | 8% |
| design | 45 min | 10% | 10% | 10% | 10% |
| authoring | 120 min | 25% | 25% | 25% | 25% |
| render | 45 min | 18% | 15% | 11% | 12% |
| TTS | 25 min | 5% | 5% | 5% | 5% |
| ASR | 20 min | 3% | 3% | 3% | 3% |
| review | 90 min | 12% | 12% | 12% | 12% |
| repair | 30 min | 8% | 8% | 8% | 8% |
| finalization | 60 min | 5% | 5% | 5% | 5% |
| retrospective | 45 min | 7% | 7% | 7% | 7% |

The planning first pass remains a hard 5-percent reasoning envelope. It may not spend the protected quality-repair reserve. When a quality gate returns `revise` or `blocked`, the supervisor may compile `lecture-animation-planning-quality-repair-contract-v1`, sealing the first-pass artifact hash, rejected gate, nonempty defect list, acceptance checks, and allowed paths. Only `phase-start --phase planning --phase-purpose quality_gate_repair --quality-repair-contract ...` may spend that reserve. The repair phase may roll forward the unused part of the first-pass envelope, but first-pass and planning-repair use together may never exceed their combined 13-percent reasoning completion envelope. If that combined envelope is exhausted while defects remain open, the state is `budget_replan_required`: stop and replan scope or resources; do not delete necessary content, weaken the quality gate, or mark the artifact accepted.

Time-governed continuation is also a cold recovery path. Load
`operational-recovery.md` only after explicit user authority and concrete
historical overrun evidence.

Completed use plus every live reservation is always measured against the episode/stage limit and the applicable phase envelope. Candidate renders use the render envelope; repair rerenders, technical retries, pronunciation retries, post-readiness script changes, and reuse verification are charged to the repair envelope. A phase cannot silently monopolize another phase's allowance merely because the episode total remains under the delivery target or the outer token ceilings. `phase-end` emits `PHASE_BUDGET_ENVELOPE_EXCEEDED`; it returns nonzero for that operational overrun only when the applicable metric is `enforce`.

One task capsule should not reserve an entire phase. The default declared
maxima are `1,500,000` raw input-plus-output tokens, `100,000` uncached input
tokens, `20,000` output tokens, and `8,000` reasoning tokens. `phase-start`
always records a larger declaration and rejects it only when `token_budget` is
`enforce`; `phase-end` treats observed overrun the same way. Short
high-concurrency bursts therefore remain several independently bounded
deliverables without turning an observation-only experiment into a stop.

The context-size defaults are `32 KiB` of assignment prompt, `256 KiB` of
intentionally loaded text/structured artifacts, and `16` files. These are
auditable declarations, not inferred measurements. `phase-start` always
records an overage and rejects it only when `context_size` is `enforce`;
negative claims and nonzero human-wait claims remain structurally invalid in
every mode. Prefer a durable intermediate artifact and a fresh bounded task
when more context is genuinely needed, but do not split work solely to appease
an `off` or `observe` metric.

Use the stage windows, WIP limits, model routing, and timeout decisions in
`eight-hour-production.md`. The phase envelopes here are episode-wide
accounting buckets, not per-scene grants and not a second competing schedule.

Previously accepted human issues with `must_check_in_future: true` are zero-tolerance regressions. If the same `pattern_key` later reappears as a current `human_review` issue, `batch-status` emits `KNOWN_HUMAN_REGRESSION_RECURRED`, and `batch-status --require-clean` fails. The episode may still be repaired and finalized, but it cannot be reported as process-compliant.

Do not claim that the eight-hour workflow has succeeded merely because the tooling was installed. The next matched episode must have complete phase telemetry, reach upload-ready within the eight-hour delivery clock, complete the retrospective inside its separate reserve, produce zero known-regression recurrences, produce zero automatic-pass-to-human-revise outcomes, and keep scene-local human-issue coverage below 25 percent without skipping any quality or user gate. Token completeness is reported independently according to its metric mode; missing evidence is never zero. A same-episode before/after snapshot proves tooling behavior only.

Use `batch-status --require-clean` before batch handoff. Quality/evidence failures
such as inconsistent shared phase IDs, missing required scene-phase pairs,
stale human outcomes, and semantic escapes remain nonzero. Operational token,
aggregate telemetry, context-size, and artifact-growth alerts are nonzero only
when their sealed metric mode is `enforce`; in `off` or `observe` they remain
visible in `nonblocking_operational_alerts`. Use `--historical` only for post-integration
analysis after the original worktree or planning hashes advanced; historical
mode records those differences without pretending the batch is still live.

`phase-start` automatically snapshots cumulative Codex token usage from the current rollout when `CODEX_THREAD_ID` is available. For other workers, pass `--usage-file` pointing to cumulative OpenAI/Anthropic/Codex-compatible JSON or JSONL. Ordinary phases record their four explicit task-capsule allocations. A time-governed token-off phase omits/nulls those allocations and writes observed deltas to the independent overlay event log; an ordinary episode-wide `observe` profile retains full deltas in the canonical ledger without enforcing them. `PHASE_ACTIVE_TIME_ALLOCATION_EXCEEDED` is nonzero only when active time is `enforce`; otherwise it remains a nonblocking alert. Every non-wait phase, including render, TTS, and ASR, participates in token-observability coverage. Missing evidence is never silently interpreted as observed zero.
