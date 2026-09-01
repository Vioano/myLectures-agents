# Progress and reflection guard

Use this guard for every bounded lecture-animation planning, narration, TTS,
alignment, design, authoring, render, review, repair, finalization,
consolidation, or retrospective task. The episode and scene pipelines say
which approvals exist. This guard prevents one active attempt from silently
consuming unreasonable time while producing no verifiable progress.

## Authority boundary

The task guard is deliberately separate from episode and scene approval
state. It may block the next production action, but it may not grant, advance,
revoke, or reinterpret a user/reviewer gate. A scene that is human-approved
stays approved when a later consolidation task times out; the consolidation
attempt must replan without rewriting the approved scene.

The operational transitions are:

`running -> warning -> reflection_required -> replanned -> running/completed`

`reflection_required` is a hard stop. Do not keep editing, rendering,
searching, reviewing, or launching micro-retries. Seal the required reflection,
choose a new path, and resume one new measured attempt. Commentary such as
“快好了” or a still-running process is not evidence of progress.

## Mandatory triggers

| Trigger | Default threshold | Meaning |
|---|---:|---|
| Wall-clock budget | warn at 75%; stop at 100% | The active attempt consumed its sealed allocation. |
| No meaningful output | 15 minutes | No changed code/plan, playable voiced review, QC evidence, review verdict, issue transition, state advance, portable handoff, or final media. |
| Repeated revise | 2 consecutive verdicts | A third micro-adjustment on the same strategy is forbidden. |
| Same regression | same `pattern_key` twice | Authoring or self-review strategy failed. |
| Artifact churn | 3 changed checkpoints without gate advance | File growth is not state progress. |
| Delivery commitment missed | at the declared deadline | Preserve the current playable intermediate and disclose the blocker. |
| Stale dependency wait | 15 minutes without progress | Replan, change the available tool/reviewer, or hand off a bounded intermediate. |
| Unapproved scope expansion | immediately | Return to the sealed task boundary. |

A meaningful checkpoint must contain changed, hashable bytes inside the
episode and must do one of these jobs: change executable source or a sealed
plan; produce a playable voiced review/final media artifact; add new QC or
review evidence; close/reopen a durable issue; advance a compiled gate; or
create a portable handoff. Rehashing the same bytes does not reset the idle
clock. Render caches, logs, probes, or screenshot piles count only when they
close an issue, advance a gate, or supply genuinely new QC/review evidence.
The guard state itself may never be checkpointed as progress.

## Required reflection

Answer all four diagnostic questions plus the scope boundary:

1. Which exact gate is blocked?
2. What verifiable output was produced during the last measured window?
3. Which assumption, tool, or strategy is probably wrong?
4. What is the next smallest falsifiable action?
5. What work remains explicitly out of scope?

Choose one path: continue with a falsifiable check, change strategy, deliver
the current intermediate, request a scope change, or wait for a real external
dependency. `resume` starts a new measured attempt. It preserves the prior
trigger and reflection and never resets episode-level cost or phase evidence.

## Commands

```bash
python3 "$SKILL/scripts/progress_guard.py" init \
  --project-root videos/NNNN-slug \
  --state videos/NNNN-slug/review/progress/<task-key>.json \
  --task-key <task-key> --phase repair --gate <current-gate> \
  --next-minimal-action '<one falsifiable action>' \
  --wall-budget-seconds 1800 --idle-budget-seconds 900

python3 "$SKILL/scripts/progress_guard.py" checkpoint \
  --state <guard.json> --kind playable_review --artifact <review.mp4> \
  --gate <gate> --gate-advanced --summary '<what changed>' \
  --next-minimal-action '<next action>'

python3 "$SKILL/scripts/progress_guard.py" signal \
  --state <guard.json> --event-type revise --note '<review id>'

python3 "$SKILL/scripts/progress_guard.py" status --state <guard.json>

python3 "$SKILL/scripts/progress_guard.py" reflect \
  --state <guard.json> --blocked-gate <gate> \
  --window-output '<verified output or none>' \
  --invalid-assumption '<failed assumption>' \
  --next-minimal-action '<smallest check>' \
  --path-decision change_strategy --scope-boundary '<explicit boundary>'

python3 "$SKILL/scripts/progress_guard.py" resume \
  --state <guard.json> --next-minimal-action '<same bounded action>'

python3 "$SKILL/scripts/progress_guard.py" complete \
  --state <guard.json> --evidence <accepted-or-handed-off-artifact> \
  --gate <terminal-gate>
```

Run `status` at every concise user-update interval, immediately before a new
render/review/repair attempt, before dispatching or accepting work, and before
claiming delivery readiness. Record every `revise`, repeated `pattern_key`,
delivery commitment, dependency wait, dependency progress, and scope change
when it occurs. A nonzero `status`, `checkpoint`, or `signal` result means the
hard stop is active; do not hide it behind a successful shell wrapper.
