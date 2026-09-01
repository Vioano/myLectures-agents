# myLectures Agents and Supervision System

This repository is the portable Agent/Human control bundle for
[myLectures](https://github.com/Vioano/myLectures). It contains both the Agent
Skills and the runnable lecture-state-supervision backend—Python service, Agent
CLI, Human UI, tests and Episode evaluation tooling.

## Clone and verify

```bash
git clone https://github.com/Vioano/myLectures-agents.git
cd myLectures-agents
./scripts/verify-state-supervision-bundle.sh
```

The runtime uses Python 3.10+ and the standard library only. The verifier runs
the unit suite, installs the bundle into a clean temporary project, creates a
persistent episode, starts the HTTP service and checks both the Agent API and
Human UI.

## Use directly from this clone

Point state and artifact resolution at the production repository; the bundle
itself can remain read-only.

```bash
export LECTURE_PROJECT=/absolute/path/to/myLectures

python3 state-supervision/supervise.py \
  --repo-root "$LECTURE_PROJECT" \
  --data-root "$LECTURE_PROJECT/.lecture-state" \
  --help

python3 state-supervision/serve.py \
  --repo-root "$LECTURE_PROJECT" \
  --data-root "$LECTURE_PROJECT/.lecture-state"
```

Open `http://127.0.0.1:4321/`. Closing or restarting the browser does not stop
the backend or lose state; SQLite/WAL under `.lecture-state/` is authoritative.

## Install into an existing project

```bash
./scripts/install-state-supervision.sh /absolute/path/to/myLectures
cd /absolute/path/to/myLectures
python3 state-supervision/supervise.py --help
python3 state-supervision/serve.py
```

The installer copies only these components and adds `.lecture-state/` to the
target `.gitignore`:

| Path | Purpose |
|---|---|
| `.agents/skills/lecture-state-supervision/` | Project-level operating Skill |
| `state-supervision/` | Persistent backend, Agent CLI, Human UI and tests |
| `state-supervision-evaluation/` | PRE13/EP13 telemetry, stress and retrospective tools |

Generated runtime databases and previous test-result directories are not
published in the bundle.

## Other project Skills

| Path | Purpose |
|---|---|
| `AGENTS.md` | Shared collaboration, Git and quality rules |
| `.agents/skills/lecture-animation-pipeline/` | Current animation-production Skill |
| `.agents/skills/lecture-animation-pipeline-legacy/` | Frozen detailed references and compatibility tools |
| `.agents/skills/notebook-production-pipeline/` | Companion notebook workflow |

The publication source of truth remains the main myLectures repository and is
released through `scripts/sync-agents.sh` there.
