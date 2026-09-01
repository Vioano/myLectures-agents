# Lecture State Supervision Architecture

## Authority boundary

This system is the only authority for episode work state, ownership, scheduling,
evidence lineage, quality-gate receipts, change impact and recovery. It does not
mirror or dual-write the legacy CLI state model.

Selective migration is intentionally narrow:

| Legacy material | New-system treatment |
| --- | --- |
| Proven hard check | Run as a version-pinned validator; normalize only its evidence |
| Stable invariant or failure case | Re-express as a new domain invariant or regression test |
| Historical episode data | Optional one-time read-only import with provenance |
| Legacy command/state schema | Do not copy or maintain compatibility |
| Legacy mutation authority | Never call it as a second state writer |

## Kernel and projections

Each episode owns one SQLite/WAL database. A command executes in one `BEGIN
IMMEDIATE` transaction and writes:

- immutable events with aggregate version and full `state_after` hash;
- current aggregate projections;
- an idempotency record keyed by request ID, actor, command and payload hash;
- context-capsule manifests and artifact-lineage edges when applicable.

No command spans two episode databases. The global catalog is a disposable
read model rebuilt from isolated episode stores. Large media stays on disk;
state contains exact path, SHA-256, size, producer and consumer lineage.
The Human UI serves a registered media artifact through a single-episode,
single-artifact HTTP byte-range endpoint. Playback therefore does not copy a
hundreds-of-megabytes file into JSON, SQLite or browser memory as one blob.

Events are the trusted prefix. Projections may be rebuilt only when the event
log verifies. Event corruption stops automatic recovery.

## Fixed multi-scale state model

“Macro” and “micro” are relative views, not two hard-coded state classes and
not states invented by a model at runtime. The architecture is fixed while the
system is designed; a fresh Session only instantiates validated content units,
deliverables and work packages through bounded commands.

The mental model is a typed work graph:

```text
W = (C, D, V, E_task, E_data, E_return, E_route, X, alpha)
```

- `C` is the bounded content-containment tree: episode → chapter/section →
  scene → animation beat. Its current maximum depth is four.
- `D` is the bounded deliverable-containment tree: for example contract,
  narration/audio, visual, QA, integration and release. Its current maximum
  depth is three.
- `V` is the set of executable work packages. Each task may be anchored at one
  coordinate `(content_unit_id, deliverable_id)`.
- `E_task` is execution dependency. Containment in `C` or `D` never creates an
  execution dependency.
- `E_data` is immutable artifact lineage; `E_return` is review/human feedback
  returning to work; `E_route` is a strategy replacement behind a stable output
  contract. These edge types remain distinct in storage and projections.
- `X` is the event-derived fact set: lifecycle, readiness, ownership, evidence,
  quality and health. A single overloaded “status” string is not asked to carry
  all of those meanings.
- `alpha` is deterministic aggregation. It projects leaf facts upward to a
  scene, deliverable, episode or UI lens without mutating lower-level truth.

A new content level is justified only when it has an independent scheduling,
evidence, review or invalidation boundary. An attempt is not another hierarchy
level; it is a lease generation over the same work package. These bounds keep
the model expressive without turning every Session into a schema designer.

Episode phase (`initialized`, `producing`, `producing_attention`,
`release_candidate`, `releasable`, and explicit release/retrospective
milestones) is a projection over work facts, not a stage barrier. One worker may
produce TTS while another authors a later scene; a reviewer may return an older
scene without rolling the whole episode backward.

A local failure changes only its causal descendants. Siblings and the episode
control plane remain usable. A changed accepted artifact invalidates the
producer and descendants, marks their candidate artifacts stale, and preserves
unrelated sibling approval.

## Attention allocation

`next` is a read-only deterministic scheduler. The system computes action class,
critical-path value, unlock value and configured priority; the Agent does not
fill in or calculate its own priority score.

Review returns are durable tickets with `attention_boundary` delivery. The
original author can continue a live lease; the return becomes the highest
priority repair only after that attention boundary. A supervisor can reroute
the ticket to a different worker without changing the review evidence.

`begin` issues a content-hashed capsule containing only:

- the exact task/output/side-effect contract;
- dependency state and required input artifacts;
- explicitly bound references after hash verification;
- applicable accepted feedback, open changes and gaps;
- the task budget and stop conditions;
- the pinned hard-validator descriptors.

Unbound repository history is absent. Missing or drifted required context fails
closed. An oversized but hash-valid text reference degrades deterministically to
a bounded reference brief: original path and hash, Markdown heading outline,
opening excerpt, source/excerpt/omission counts, and an explicit
`read_original_on_demand` policy. It does not fail the capsule, silently cut the
source, or ask a model to improvise a summary. The exact same brief appears in
Human preview and the issued Agent capsule. `reference-rebind` is the only
direct way to adopt a reviewed reference revision; it revokes stale work and
issues a new capsule revision. Agents
normally use `next`, one capsule, targeted `explain`, then cursor deltas; they
need not retain the full topology or Skill corpus.

Runtime decisions do not invoke a model to regenerate this state architecture.
State enums, legal transitions, scheduling ranks, aggregation and invalidation
are program rules. Models perform the semantic production/review work inside a
leased task and report evidence through the small interface.

## Time, tokens and local-optimum control

Leases separate ownership from task state and carry a monotonically increasing
generation. Only the current owner/generation can heartbeat or submit.

Heartbeats account active time and token deltas. A heartbeat is meaningful only
when it binds **novel content-addressed evidence**; notes, operational events,
and a previously seen file/artifact hash do not reset stagnation. The supervisor
hard-stops a task after its time/token/no-progress/attempt limits and requires a
reasoned `replan`.

“Idle” and “productive” are separate predicates. The stable roster records each
Agent's role, capabilities, presence and runtime handle. `agent-probe` derives
one of these evidence-backed classes without asking the Agent to describe its
own busyness:

- `idle_legal`: no compatible actionable task exists for this Agent, or capacity,
  dependencies, human authority, or an explicit external wait prevents pickup;
- `idle_illegal`: the Agent is online, owns no attention envelope, and a compatible
  system-ranked action is ready;
- `working_productive`: one live unique work obligation is held and the novelty
  guard is clean;
- `working_nonproductive_risk`: a lease exists but recent heartbeats add no new
  evidence, with token burn reported separately;
- `fake_busy_duplicate_work`: the obligation is already satisfied elsewhere;
- `planned`, `offline`, `retired`, or `offline_unknown`: presence is not silently
  reinterpreted as legal idle.

Every task has a stable `work_key`. A second task ID cannot create another live
copy of the same semantic obligation. Legitimate revision reuses the task after
a new review finding, upstream invalidation, or explicit replan; an alternative
method uses `route-switch`, which supersedes the old obligation atomically.

Episode budgets protect a closure reserve. Once the production envelope is
spent, new non-closure work is not scheduled even though review, repair,
integration and finalization can continue. A true hard cap stops the episode
queue and asks for an explicit macro replan.

## Quality authority

Kernel artifact contracts enforce non-negotiable type facts before candidate
registration. In particular, `narration_audio` must contain a decodable audio
stream (WAVE is parsed directly; other containers are probed with `ffprobe`).
The normalized check is stored on the artifact and exposed in review context.
This is not delegated to model judgment and cannot be omitted by a route spec.

Programmatic validators answer narrow deterministic questions. Task planning
pins the manifest and every declared/executable asset as one bundle hash.
Candidate hash, validator bundle hash and normalized result are joined in a gate
receipt. Review cannot pass while any required receipt is absent.

Validator lifecycle is `draft → canary → active → quarantined/retired`. Canary
use must be explicit. Drift fails closed; `validator-rebind` records a reason,
revokes stale work and increments task scope revision. Validators do not mutate
domain state directly.

Semantic, mathematical, visual and creative judgment remains with an
independent reviewer working from task-specific references. Machine review
cannot grant human release authority.

## Interfaces

The Agent interface is a small JSON CLI:

```text
next → begin → heartbeat → submit → gate → review → human gate
          ↑                 ↘ deferred return at attention boundary
          └ route switch / change / gap / replan
diagnosis: explain / events-after-cursor / scan / recover-preview
roster: agent-register / agent-presence / agent-probe
```

Structured denials contain the failed invariant, subject, current facts,
allowed next verbs and cursor. Denials do not mutate domain aggregates.
The default CLI `next` projection contains one action, one compact task identity,
counts and a cursor. Full alternatives/exclusions require the explicit
supervisor-only `--details` view; they are not paid into every worker context.

The Human interface reads the same backend and offers three lenses over the
same facts: macro scope flow, task/data/review/route topology and one task's
micro lifecycle. It also presents Agent workstations, evidence, annotations and
anomalies. Content/deliverable containment is visible but never drawn as a
false linear stage order. Human edits become commands/events; SSE sends only
deltas. The coordinate-free Agent projection omits layout coordinates entirely.

The flow monitor gives the topology canvas the viewport and projects supporting
time, scheduling and pickup facts as collapsible canvas overlays. Task details
have one semantic passport and two interchangeable readers: a node-adjacent
scrollable full-passport bubble and a persistent evidence sidebar. The graphical
reader switch exposes current UI state and moves the current passport
immediately; it never creates a second domain projection. Fullscreen forces the
bubble reader without mutating the stored non-fullscreen preference. Inspecting
a node and expanding its downstream topology are separate gestures, so a read
does not silently change graph membership.

Media review is part of that same passport. A single annotation command or one
atomic bounded batch binds a finding to an immutable artifact ID, millisecond
timecode and optional normalized frame coordinate. Episode-wide drafts remain
browser-local until submitted; after submission they become ordinary immutable
events and annotation projections visible to both the producer task and its
artifact. This keeps interactive review convenient without treating a mutable
filename, UI draft or video-player state as domain truth.

## Failure handling

- Lost response: retry the identical request ID and receive the stored result.
- Concurrent command: SQLite serialization plus aggregate compare-and-swap
  yields one winner and a structured loser.
- Dead worker: scan detects expired ownership; previewed recovery releases only
  that lease and returns only that task to rework.
- Projection drift: back up the database, replay the verified event prefix and
  rebuild projections.
- Missing/drifted artifact: mark only its producer/causal consumers unsafe.
- Production-route change: `route-switch` supersedes the old producer, cancels
  obsolete return tickets, preserves old evidence as out-of-route, rewires only
  causal consumers and cannot weaken output/validator/human-gate contracts.
  Stable artifact-role kernel checks remain in force across every strategy.
- Reference drift: fail closed until `reference-rebind` records the reviewed
  revision and invalidates the stale task attempt.
- Bad validator: record fail/error receipt; the candidate remains review-blocked.
- Event-log corruption: stop and require backup/forensic recovery.

## Current trust boundary

The first long test is local and cooperative. Actor IDs are stable accountability
identities, not cryptographic authentication; the harness must pin one actor ID
per Agent invocation. Validator processes have an executable allowlist, minimal
environment and timeout, but are not an operating-system security sandbox.
Untrusted extensions therefore remain quarantined/canary until independently
reviewed. These are explicit long-test observations, not silently assumed
security guarantees.
