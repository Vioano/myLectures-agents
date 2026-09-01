# State Supervision Evaluation

This directory separates three evaluation tracks for the future state-management and supervision system. It is deliberately outside the active lecture-animation Skill so an ongoing production task is not changed by the evaluation contract.

The governing automation direction is documented in
[`HARNESS_AUTOMATION_PHILOSOPHY.md`](HARNESS_AUTOMATION_PHILOSOPHY.md): keep the
complex Harness needed for scale, while compiling and projecting only the
minimum sufficient working set into each live Agent action.

Product sequencing and the complete durable issue registry live in
[`PRODUCT_ROADMAP.md`](PRODUCT_ROADMAP.md) and
[`PRODUCT_BACKLOG.md`](PRODUCT_BACKLOG.md). New Human/Agent interface findings
must be registered there instead of remaining only in a chat transcript.

## Three tracks with different objectives

### 1. Short black-box tests

Primary objective: expose interface, state, permission, conflict, recovery and determinism defects quickly.

- Use disposable fixtures and isolated state stores.
- Prefer many short scenarios over one simulated episode.
- Actively inject stale versions, duplicate commands, missing inputs, expired leases, conflicts, no-exit states, projection drift and service restarts.
- Production media quality is not the output; transition coverage and bug discovery are.
- Blind operator Agents must not read system design documents, source code, hidden fixtures or earlier test transcripts.
- Results belong under `short-tests/results/<suite-run-id>/`.

See [short-tests.md](short-tests.md).

### 2. Episode long shadow run

Primary objective: finish the real episode efficiently and stably while passively measuring the system under long-lived production pressure.

- Episode 13 is the intended first long shadow run.
- Video production and existing quality/user gates remain the primary objective.
- Do not inject destructive or production-risking faults merely to increase test coverage.
- Record naturally occurring ambiguity, context mismatch, stale state, intervention, recovery, latency and long-horizon drift.
- At episode closeout, write the retrospective and freeze the evidence pack.
- The production Session must **not** optimize, patch or refactor the state-supervision system during retrospective closeout.
- A later evaluation Session reads the frozen pack, performs diagnosis, changes the system and runs regressions.

This separation avoids the old pattern in which the same production Session observed a problem, immediately changed the harness, and then evaluated its own changed behavior without a stable before/after boundary.

### 3. Eight-minute simulation game

Primary objective: watch a coherent miniature episode move through the Human UI
while one fresh Agent experiences only the public interface and exact task
capsules.

- The initial state contains only the original all-TTS plan.
- A late human recording, partial route switch, deferred review return and
  duplicate-work probe are injected only after the round starts.
- Artifacts are tiny, explicitly simulated placeholders; no real TTS, ASR,
  Manim rendering or release work occurs.
- At 07:30 the game freezes; at 08:00 all mutation stops.
- Human observations and the black-box Agent report are independent files.
- The round is not patched while it is running.

See [simulation-game.md](simulation-game.md).

## Long-run pack

Create one directory:

```text
review/state-supervision/runs/<run-id>/
  run-manifest.json
  observations.jsonl
  retrospective.md
  evidence-index.json
  evaluation-handoff.json
  frozen-evidence/
    manifest.json
    aggregates.json
    events.jsonl
    commands.jsonl
    capsules.jsonl
    integrity.json
    metrics.json
```

Initialize it with:

```bash
python3 .agents/skills/lecture-state-supervision/scripts/evaluation/init_episode_run.py \
  --episode-id 0013 \
  --slug <episode-slug> \
  --episode-path videos/0013-<episode-slug> \
  --session-ref <thread-or-session-id> \
  --system-version <state-system-build-id>
```

Validate it before handoff:

```bash
python3 .agents/skills/lecture-state-supervision/scripts/evaluation/check_run_pack.py \
  review/state-supervision/runs/<run-id> \
  --ready
```

## Recording policy

Prefer automatic backend telemetry. Manual observations are event-triggered, not a diary and not another heartbeat tax.

The frozen export derives task queue/active/cycle time, real lease overlap,
reservations, Agent commands and token usage, Human decisions and annotation
delivery, review/rework, change/recovery and coverage gaps. Optional Human UI
interaction, media playback and host model logs are named in the run manifest.
Do not collect hidden chain-of-thought, raw keystrokes or unrelated screen
history.

Write an observation when at least one is true:

- the user had to intervene in state/protocol handling;
- the Agent could not identify the next legal action;
- context was missing, excessive, stale, contradictory or leaked across scope;
- an apparently identical retry produced a different operational result;
- a command was denied without an actionable recovery route;
- a local failure affected an unnecessary sibling or parent scope;
- a stale artifact/lease/process/projection looked authoritative;
- recovery required guessing, direct state edits or repeated attempts;
- the system reported progress without reducing distance to a deliverable;
- service latency or disconnection provoked duplicate/unsafe behavior;
- an unauthorized side effect was attempted or accepted;
- a fresh Agent handoff required information that existed only in chat history.
- content/deliverable containment was mistaken for execution order, or the UI
  hid legal cross-stage concurrency;
- deferred review feedback interrupted a live attention lease, disappeared, or
  returned to the wrong worker;
- a route change (for example TTS to direct recording) damaged an unrelated
  sibling, lost lineage, or weakened the stable output contract;
- an operator felt compelled to invent a status, hierarchy level, transition,
  priority formula or recovery verb that the fixed interface did not provide.

Do not invent zeroes. Missing telemetry is `unknown` and must be listed under coverage gaps.

## Authority boundary

The Episode production Session may:

- produce and repair the actual episode;
- record raw observations and evidence references;
- describe the observed recovery and its production cost;
- write the final retrospective and mark the pack `evaluation_ready`.

It may not, merely as part of retrospective closeout:

- modify state-supervision source, schema, routing, prompts or plugins;
- rewrite historical events or clean evidence that makes the run look worse;
- convert its own hypothesis into a permanent rule;
- claim missing telemetry as proof that a failure did not occur.

If production is blocked and the user explicitly authorizes an emergency system repair, record it as a `confound`, preserve before/after evidence, and continue. The long run is then not a clean unchanged-system trial.

## Handoff boundary

The long run ends with:

- exact production outcome and user-gate status;
- system version/build and episode Session references;
- raw event/command/capsule/clock evidence locations;
- structured observations with unresolved items preserved;
- explicit telemetry gaps and confounds;
- `evaluation-handoff.json` set to `evaluation_ready`;
- `system_optimization_applied_by_production_session: false`, unless an authorized emergency change is documented.

The later evaluator owns causal diagnosis, prioritization, design changes, implementation and regression testing.
