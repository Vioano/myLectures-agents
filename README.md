# myLectures Agents and Supervision System

This repository is the portable Agent/Human control bundle for
[myLectures](https://github.com/Vioano/myLectures). It contains both the Agent
Skills. `lecture-state-supervision` is self-contained: its own folder includes
the Python service, Agent CLI, Human UI, tests and Episode evaluation tooling.

## Clone and verify

```bash
git clone https://github.com/Vioano/myLectures-agents.git
cd myLectures-agents
./.agents/skills/lecture-state-supervision/scripts/verify.sh
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

python3 .agents/skills/lecture-state-supervision/scripts/runtime/supervise.py \
  --repo-root "$LECTURE_PROJECT" \
  --data-root "$LECTURE_PROJECT/.lecture-state" \
  --help

python3 .agents/skills/lecture-state-supervision/scripts/runtime/serve.py \
  --repo-root "$LECTURE_PROJECT" \
  --data-root "$LECTURE_PROJECT/.lecture-state"
```

Open `http://127.0.0.1:4321/`. Closing or restarting the browser does not stop
the backend or lose state; SQLite/WAL under `.lecture-state/` is authoritative.

## Install into an existing project

```bash
./.agents/skills/lecture-state-supervision/scripts/install.sh /absolute/path/to/myLectures
cd /absolute/path/to/myLectures
python3 .agents/skills/lecture-state-supervision/scripts/runtime/supervise.py --help
python3 .agents/skills/lecture-state-supervision/scripts/runtime/serve.py
```

The installer copies exactly one component and adds runtime/evaluation ignores
to the target `.gitignore`:

| Path | Purpose |
|---|---|
| `.agents/skills/lecture-state-supervision/` | Complete Skill: instructions, runtime, UI, tests and evaluation tools |

No sibling runtime directory is required. Generated databases and project test
evidence stay outside the Skill under `.lecture-state/` and
`review/state-supervision/`.

## Other project Skills

| Path | Purpose |
|---|---|
| `AGENTS.md` | Shared collaboration, Git and quality rules |
| `.agents/skills/lecture-animation-pipeline/` | Current animation-production Skill |
| `.agents/skills/lecture-animation-pipeline-legacy/` | Frozen detailed references and compatibility tools |
| `.agents/skills/notebook-production-pipeline/` | Companion notebook workflow |

The publication source of truth remains the main myLectures repository and is
released through `scripts/sync-agents.sh` there.
