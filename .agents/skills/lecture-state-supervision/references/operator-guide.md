# Lecture Supervision Operator Guide

Use this guide to operate the public interface. You do not need the service
source, database schema, or architecture document.

## Invocation

From the repository root:

```bash
python3 .agents/skills/lecture-state-supervision/scripts/runtime/supervise.py \
  --data-root <state-root> \
  --repo-root <repository-root> \
  --actor <stable-actor-id> \
  --request-id <unique-idempotency-key> \
  <command> ...
```

Global flags precede the command. Reuse a request ID only when retrying the
exact same actor, command, and payload. Artifact, reference, validator and JSON
file arguments are all resolved relative to `--repo-root` unless absolute.
JSON on stdout is authoritative.

## Normal attention loop

1. `next EPISODE` returns one system-ranked action and its reasons. It is
   read-only and attention-sized; do not score the whole task graph yourself.
   Use targeted `explain` first. `next EPISODE --details` is a supervisor
   diagnostic escape hatch, not the normal work loop.
2. For `work` or `reclaim`, run `begin EPISODE TASK`. The returned context
   capsule is the exact working context. Do not replace it with a full Skill or
   repository reread.
   Use read-only `context-preview EPISODE TASK` when a human or supervisor needs
   to inspect that exact capsule before the task is claimed. Oversized text
   references appear as deterministic briefs with their original path, hash,
   structural summary, opening excerpt and omitted character count; the worker
   receives that same brief and can read the pinned original on demand.
3. While working, run `heartbeat EPISODE TASK --generation N` with new
   `--evidence PATH` (or `file:PATH`, artifact ID, event ID) and token deltas.
   Notes alone are not progress. Reusing an already-seen content hash is also
   not progress, and routine operational events are rejected as evidence.
4. Run `submit EPISODE TASK --generation N --artifact ROLE=PATH` for exact
   content-addressed outputs.
5. For `gate`, run `gate-run EPISODE TASK VALIDATOR_ID` for each item in
   `missing_validators`.
6. For `review`, switch to a stable actor different from the candidate author,
   call `review-context EPISODE TASK`, inspect only its bound rules and exact
   artifacts, then run `review EPISODE TASK --context-hash HASH --verdict
   pass|revise`. A review cannot bypass required hard gates or use stale context.
7. For `human_review`, stop and expose the candidate in the Human UI. Only an
   actual human actor runs `human-decide`.
8. When a review returns work, keep the current live lease. The system delivers
   the durable `return_rework` ticket at the next attention boundary; do not
   interrupt yourself by polling the review details while busy.
9. Call `next` again. Do not infer that a successful command finishes the
   episode.

Use `explain EPISODE [TARGET]` when the next action or a denial is unclear. Use
`events EPISODE --after CURSOR` for incremental changes; avoid repeatedly
loading full history.

## Human flow monitor

The flow monitor is canvas-first. The live-time ribbon, scheduling policy and
pickup loop remain available as collapsed overlays; opening them must not
resize the topology canvas or introduce page-level scrolling.

Selecting a task opens one of two projections of the same task passport:

- **Bubble** is the default canvas-preserving surface beside the selected node.
  It contains the complete task passport in a bounded, vertically scrollable
  window, so the upper decision facts remain visible first and all context,
  evidence, gates, media and mutation controls remain reachable below.
- **Sidebar** is the durable inspection surface for context, evidence, gates,
  annotations and mutation commands.

Both surfaces contain the same graphical bubble/switch/sidebar control. It is a
state indicator and an immediate toggle: changing it moves the current passport
to the selected projection and also saves the browser preference. Fullscreen
canvas mode forces the bubble projection without overwriting that saved
preference. Closing either surface does not mutate task state.

On a topology canvas, a single click or tap inspects the node without changing
which nodes are visible. A double click or double tap expands or contracts that
node's downstream neighborhood. Keyboard users press Enter to inspect and
Shift+Enter (or `e`) to expand. This separates semantic inspection from topology
navigation.

### In-browser media review

Registered audio and video artifacts appear inside the task passport. The
browser uses the artifact media endpoint with HTTP byte ranges and
`preload=metadata`; even a large 4K file stays on disk and is streamed only for
the requested playback window instead of being read into page memory in full.
The endpoint serves only the exact artifact ID registered to the episode and
rejects a missing or size-drifted file.

Pause or seek to a time, optionally choose **mark image position** and click the
video frame, then write the finding. **Submit now** records one annotation
immediately. **Add to episode draft** keeps it in browser-local draft storage so
findings from several tasks can be submitted atomically with **Submit batch**
after the complete episode review. Every submitted media annotation binds the
artifact ID, millisecond timecode and optional normalized x/y position; it does
not merely point at a mutable filename or the producer task.

## Command meanings

- `change EPISODE TARGET --reason TEXT`: record a scope or artifact change and
  derive its invalidation impact. Never silently edit accepted work.
- `gap EPISODE TASK --reason TEXT`: stop a task on missing input, capability,
  authority or contradictory requirements. A Human-required conflict stays
  fail-closed. `gap-resolve` records the explicit decision and automatically
  creates a scoped next-attempt context override that must reach both the author
  and independent reviewer capsules.
- `replan EPISODE TASK --reason TEXT [--budget JSON]`: explicitly authorize a
  bounded new attempt after stagnation or a local hard stop.
- `episode-budget EPISODE --reason TEXT --budget JSON`: adjust the macro budget
  only with an auditable reason.
- `agent-register EPISODE AGENT --role ROLE --capability CAP`: seal a reusable
  roster identity. Use `agent-presence` for planned/online/offline/retired state
  and `agent-probe` to read legal idle, illegal idle, productive work or a
  fake-busy/stagnation risk. The probe is derived from capabilities, Ready Pool,
  leases, deferred returns, evidence novelty and capacity; the Agent does not
  self-report whether it is busy.
- `dispatch-reserve EPISODE --reason TEXT --assignment TASK=AGENT ...`: bind a
  ready task to each intended compatible online author before pickup. The
  reservation protects author capacity from serial queue draining, expires if
  unused and becomes `claimed` only when that exact Agent obtains the lease.
  Use the `next` response's dispatch usage and scaling advice to decide how many
  authors to activate; verify real parallelism with overlapping leases.
- `validator-rebind EPISODE TASK VALIDATOR_ID --manifest PATH --reason TEXT`:
  adopt a new pinned validator bundle after a detected change. Add
  `--allow-canary` only for an intentional canary task.
- `reference-rebind EPISODE TASK REFERENCE_ID --path PATH --reason TEXT`:
  adopt one reviewed reference revision after hash drift. It creates a fresh
  scope/capsule revision; it never silently trusts changed guidance.
- `context-preview EPISODE TASK`: compile the exact next layered context without
  granting a lease or mutating state. Stable service rules, task contracts,
  episode material, temporary overrides and runtime facts remain separately
  identified in the returned manifest.
- `context-override EPISODE TASK --instruction TEXT`: add a versioned runtime
  instruction without editing the stable rule source. Use `--assembly-mode
  append` for an extra requirement, or `--assembly-mode replace --context-slot
  SLOT` for an explicit full replacement. Scope and delivery are mandatory
  machine-readable choices; an in-flight replacement defaults to the next
  attention boundary rather than silently interrupting the Agent.
- `route-switch EPISODE OLD_TASK NEW_TASK --strategy NAME --reason TEXT
  --spec JSON`: replace a production method (for example TTS with a supplied
  recording) only behind the same output artifact contract. It cannot remove
  required validators or a Human gate. A `narration_audio` submission must also
  pass the kernel's deterministic decodability contract before it can become a
  candidate; a filename extension or reviewer opinion cannot bypass it.
- `return-route EPISODE RETURN_ID --to ACTOR --reason TEXT`: reroute pending
  review work while preserving its findings. Returns are delivered only at an
  attention boundary.
- `content-add`, `deliverable-add`, and `task-add` instantiate the fixed
  multi-scale model during planning. Content/deliverable containment is
  grouping, never implicit execution order; only explicit task dependencies
  schedule work.
  Give reusable production obligations a stable `--work-key`; a different task
  ID cannot be used to repeat the same work merely to occupy an Agent. Revisions
  reuse the existing task, while alternative methods use `route-switch`.
- `scan EPISODE [--deep]`: read anomalies. `ok:true` means the scan completed;
  `clean:false` means it found risks.
- `recover EPISODE [--deep]`: preview safe local repairs. Add `--apply` only
  after inspecting the plan. Event-log corruption is never auto-repaired.
- `overview EPISODE`: multi-scale content × deliverable projection and live
  topology. Agents should prefer `next`, targeted `explain`, and cursor-based
  `events` during normal work.

The state schema and aggregation rules are fixed by the system. An operator
does not derive a new hierarchy or invent state labels from first principles;
it chooses only among the legal commands and facts returned by the interface.

## Reading denials

A denial is expected control flow and does not mutate domain state. Read:

- `code` and `failed_invariant` for the exact reason;
- `subject` and `details` for the current conflicting object/version;
- `allowed_next` for legal recovery verbs;
- `cursor` to resume incremental reads.

Do not edit SQLite, reuse another actor's lease, fabricate evidence, weaken a
quality gate, or repeat a denied command without changing the stated cause.

## Long-run observation

Record an `observe` event only when the interface is ambiguous, context is
missing/excessive/stale, a recovery route fails, identical retries diverge, or
human protocol intervention becomes necessary. Ordinary progress is already
captured by events and evidence-bearing heartbeats.
