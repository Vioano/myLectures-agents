# Episode shadow-run telemetry contract

Collect evidence that can change a future Harness decision. Prefer automatic,
append-only backend telemetry; manual observations are reserved for incidents
and judgments that raw events cannot explain.

## Required measures

### Flow and time

- Per-task creation, first begin, first submit, review-ready and approval time.
- Queue wait, active lease time, Human/gap wait, review wait, rework attempts,
  critical path and time to first reviewable artifact.
- Actual overlapping leases, ready-frontier size, reservation use, fan-in wait,
  author utilization and separate reviewer capacity.

### Agent interface and attention

- Stable Agent ID, role/capabilities and, when supplied by the host, model and
  reasoning effort.
- Commands, denials, retries, recovery verbs, extra `explain`/rereads, tool
  calls, input/output/reasoning tokens and tokens without meaningful progress.
- Capsule size, source blocks, context revision, omissions, stale/conflicting
  context, and whether the Agent needed information available only in chat.
- Human annotation/conflict-resolution creation time, target, delivery boundary,
  destination capsule and delivery latency for author and reviewer.
- State-changing Human intent, the coordinator's chosen public command/request
  IDs, intent-to-command latency, intended versus observed effect, and time to
  the first added live lease. This tests semantic routing without a permanent
  full-context monitoring Agent.

### Human effort and quality

- Review notification, open, playback and decision times when the UI can record
  them; annotation timecode/position/severity; approve, revise, reversal and
  batch-submit events.
- First-review pass rate, Human revision rate, reviewer disagreement, recurring
  `pattern_key`, late structural rework and automatic false pass.
- Human interventions needed for state/protocol handling, distinct from normal
  creative feedback.

### Change, recovery and delivery economics

- Route switches, conflicts, invalidated tasks/artifacts, superseded work,
  preserved work, blast radius and change-to-recovery time.
- Restarts, disconnects, cursor catch-up, stale submits, lease conflicts,
  idempotent retries, invariant failures and recovery duration.
- Approved media minutes per day, Human minutes per approved media minute,
  tokens per approved media minute and time to first reviewable artifact.

### Media interface

- Artifact size/duration, Range/seek latency, playback stalls and annotations
  bound to precise time and optional normalized frame position. Store references
  and performance events, not duplicate media bytes.

## Evidence and interpretation rules

- State export provides `events.jsonl`, `commands.jsonl`, `capsules.jsonl`,
  `aggregates.json`, `integrity.json` and derived `metrics.json`.
- Human UI interaction, media playback performance and host model metadata are
  separate optional logs named in `run-manifest.json`.
- Every retrospective claim links to raw evidence or is labelled inference.
- Missing evidence is `unknown`, never zero. List it in telemetry gaps.
- Do not collect hidden chain-of-thought, secrets, unrelated screen history,
  raw keystrokes or private files. Token counts and observable actions are
  enough for attention-efficiency analysis.
- Do not optimize only for shorter prompts. The target is the minimum sufficient
  capsule: low irrelevant context without increasing omissions, rereads,
  denials, rework or quality failures.
