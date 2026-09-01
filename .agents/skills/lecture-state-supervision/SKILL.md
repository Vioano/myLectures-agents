---
name: lecture-state-supervision
description: Operate and observe the myLectures state-supervision control plane for long multi-agent episode production, including exact next-action routing, leases, parallel reservations, scoped context capsules, Human conflict decisions, evidence, gates, change impact, recovery, and Episode shadow-run telemetry. Use when starting, resuming, supervising, querying, changing, reviewing, or closing a supervised episode such as Episode 13. Do not use it as animation-authoring guidance.
---

# Lecture State Supervision

Use the supervision backend as the sole authority for production state, work
ownership, evidence lineage, scheduling and recovery. Human UI actions and Main
Agent commands are equivalent projections onto this backend; neither frontend
nor chat history is authoritative.

Read [the public operator guide](references/operator-guide.md) before the first
command in a Session. Do not read service source or internal
architecture merely to operate it.

For Episode 13, read [the shadow-run playbook](references/episode13-shadow-run.md)
at initialization and closeout. Read [the telemetry contract](references/telemetry-contract.md)
only when configuring instrumentation, freezing evidence or writing the
retrospective.

This folder is the complete installation unit. Before relying on a newly cloned
or updated copy, run `scripts/verify.sh` from this Skill root. The verification
must prove that copying only this folder provides the Agent CLI, persistent
backend, Human UI, tests and evaluation tools. A GitHub checkout can install
the Skill into a project with `scripts/install.sh /absolute/path/to/project`.
Do not depend on sibling repository code.

The public entrypoints are `scripts/runtime/supervise.py` for Agents and
`scripts/runtime/serve.py` for the Human UI. Resolve both from this Skill root
and pass the production checkout explicitly through `--repo-root`.

This Skill is the control plane. When a task capsule requests storyboard,
Manim, Remotion, rendering, review or finalization work, also use the canonical
`lecture-animation-pipeline` Skill for that bounded task. Do not paste the whole
animation Skill into unrelated state operations.

## Essential discipline

- Start with the attention-sized `next`. Follow the returned action; do not
  reconstruct or retain the entire episode graph in model context. Use targeted
  `explain` before the supervisor-only `next --details` escape hatch.
- The multi-scale schema is system-owned and fixed. Do not invent state levels,
  status labels or transition rules in a Session. Content and deliverable trees
  are grouping axes; only explicit task dependencies constrain execution.
- `begin` is the attention boundary. Work from its versioned context capsule
  and explicitly bound references. If required context is absent or stale,
  report a `gap`; do not guess or compensate with an unbounded repository read.
- Treat leases, expected versions, request IDs, hashes, validator pins and
  independent review as constraints, not suggestions.
- Heartbeats renew ownership but count as progress only when they bind new
  evidence or measurable resource use. Honor supervisor stops and use an
  explicit `replan` instead of looping locally.
- Record changes before editing accepted inputs or outputs. Let the system
  derive the blast radius; do not mark siblings stale by intuition.
- Do not interrupt a live task to chase review feedback. Review revisions arrive
  as deferred return tickets at an attention boundary; use `return-route` only
  for an explicit worker handoff.
- Use `route-switch` when the production method changes but its output contract
  remains stable. Use `change`/replan when the deliverable itself changes.
  A direct recording still has to satisfy the system-owned `narration_audio`
  decodability contract; do not ask a reviewer to waive malformed bytes.
- On reference hash drift, inspect the impact and use `reference-rebind`; never
  absorb changed guidance through an untracked reread.
- Programmatic validators establish narrow deterministic facts. Semantic and
  creative quality still require the assigned independent reviewer and the
  existing domain-specific production references supplied to that task.
- Never turn machine review into human authority. Stop at the explicit Human
  gate until the user decides.
- A high-confidence structured contract conflict is a fail-closed `gap`, not an
  invitation for an Agent to guess. Surface its source comparison to the Human;
  `gap-resolve` creates the scoped override consumed by the next author attempt
  and independent review capsule.
- When the ready frontier exceeds active author capacity, inspect the returned
  scaling advice. Register/bring online compatible authors, then use
  `dispatch-reserve` to bind distinct tasks to distinct Agents before they call
  `begin`. Prove parallelism with overlapping leases, not graph fan-out.
- Prefer cursor-based `events` and targeted `explain` for handoff and diagnosis.
  Use `overview` mainly when a human-readable hierarchy is actually needed.

## Episode closeout

Export the immutable state bundle, complete the long-run pack, and validate it
with `scripts/evaluation/check_run_pack.py --ready`. Preserve missing
measurements as `unknown`.
The Episode production Session records evidence but does not patch the Harness;
diagnosis and optimization belong to the later evaluation Session.
