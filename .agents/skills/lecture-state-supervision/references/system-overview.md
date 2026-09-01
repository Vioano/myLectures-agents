# Lecture State Supervision

This directory contains the local-first state-management and supervision service
for long lecture-production runs.  It is intentionally separate from the active
`lecture-animation-pipeline` Skill.  This system is the new authority for work,
attention, evidence, leases, gates, and recovery; the legacy CLI is not copied
or dual-written.  Mature legacy checks may be re-exposed as isolated validators
whose evidence is normalized through the new event protocol.

The first implementation has no third-party runtime dependencies.  It uses one
SQLite/WAL event store per episode and a rebuildable catalog database.  Large
artifacts stay on disk; the database stores their paths, hashes, versions, and
producer/consumer lineage.

The public Agent interface is deliberately small:

```text
next -> begin -> heartbeat -> submit -> gate -> review -> human gate
  ^          deferred return <-/       \-> route switch / change / gap / replan
roster: agent-register -> agent-presence -> agent-probe
```

`agent-probe` does not equate a live process with useful work. It distinguishes
legal waiting, illegal idle, productive work, repeated-evidence/token-burn risk,
and duplicate semantic work. Task `work_key` identity and evidence hashes make
those decisions deterministic rather than model self-assessments.

From a project checkout, run the Agent CLI with:

```bash
python3 .agents/skills/lecture-state-supervision/scripts/runtime/supervise.py --help
```

Start the Web service with:

```bash
python3 .agents/skills/lecture-state-supervision/scripts/runtime/serve.py
```

The same runtime is published in the portable
[`myLectures-agents`](https://github.com/Vioano/myLectures-agents) bundle. A
fresh clone can be used directly or installed into an existing project:

```bash
git clone https://github.com/Vioano/myLectures-agents.git
cd myLectures-agents
./.agents/skills/lecture-state-supervision/scripts/verify.sh
./.agents/skills/lecture-state-supervision/scripts/install.sh /absolute/path/to/myLectures
```

`BUNDLE_MANIFEST.json` and `VERSION` at the Skill root identify the exact
portable build. The Skill folder itself contains the public instructions,
backend, Human UI, tests and evaluation tools; generated runtime state and
historical test results remain outside it.

Runtime databases are written below `.lecture-state/` by default and are not
version-controlled.  Durable evidence is exported explicitly into an episode's
review directory.

Operators should start with [operator-guide.md](operator-guide.md). Internal
authority and isolation boundaries are recorded in [architecture.md](architecture.md).
The cross-layer product sequence and durable issue inventory are maintained in
[product-roadmap.md](product-roadmap.md) and
[product-backlog.md](product-backlog.md).

## Human UI disclosure model

The Web UI is a decision surface, not a full-state dump. Its default layer is a
graphical production home: a layered live map shows the current frontier and its
direct upstream/downstream context, while one decision strip and three situation
summaries explain whether the system is moving or a human decision is required.
Human reminders, the decision strip, and node attention badges resolve to the
same task and open the same detail surface. The text work list stays collapsed;
structure, full topology, workstations, risk, events, and Agent JSON remain
secondary views. Main Agent commands and Human UI actions share the persistent
backend rather than relaying through frontend state.

The flow view uses three explicit scales. Macro mode is the default orientation.
Task mode applies a deterministic layered-DAG layout: dependency rank determines
columns, parallel tasks occupy rows, repeated fan-out dependencies share an
orthogonal bus, and edge labels appear only on hover or selection. Micro mode
expands one task's contract, lease, candidate, gates, review, and human authority.
The complete task graph remains available as a diagnostic option, not the default.
