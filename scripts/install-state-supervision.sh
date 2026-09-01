#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install the portable lecture-state-supervision bundle into an existing project.

Usage:
  ./scripts/install-state-supervision.sh /absolute/path/to/project

The installer copies the public Skill, Python backend, Human UI, tests and
evaluation tooling. It does not copy runtime databases or generated test runs.
Existing project files outside those three component directories are untouched.
EOF
}

if [[ $# -ne 1 || "$1" == "-h" || "$1" == "--help" ]]; then
  usage
  [[ $# -eq 1 ]] && exit 0
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_ROOT="$(cd "$1" 2>/dev/null && pwd)" || {
  echo "Target project must already exist: $1" >&2
  exit 2
}

if [[ "$TARGET_ROOT" == "/" || "$TARGET_ROOT" == "$HOME" ]]; then
  echo "Refusing an overly broad project target: $TARGET_ROOT" >&2
  exit 2
fi

for required in \
  ".agents/skills/lecture-state-supervision" \
  "state-supervision" \
  "state-supervision-evaluation"; do
  if [[ ! -e "$BUNDLE_ROOT/$required" ]]; then
    echo "Bundle is incomplete; missing $required" >&2
    exit 1
  fi
done

python3 - "$BUNDLE_ROOT" "$TARGET_ROOT" <<'PY'
from __future__ import annotations

import fnmatch
from pathlib import Path
import shutil
import sys

bundle_root = Path(sys.argv[1]).resolve()
target_root = Path(sys.argv[2]).resolve()

components = (
    Path(".agents/skills/lecture-state-supervision"),
    Path("state-supervision"),
    Path("state-supervision-evaluation"),
)


def ignored(directory: str, names: list[str]) -> set[str]:
    current = Path(directory).resolve()
    skipped = {
        name
        for name in names
        if name in {"__pycache__", ".DS_Store", "results"}
        or name.startswith("._")
        or fnmatch.fnmatch(name, "*.pyc")
    }
    evaluation_runs = bundle_root / "state-supervision-evaluation" / "runs"
    if current == evaluation_runs.resolve():
        skipped.update(name for name in names if name != "README.md")
    return skipped


for relative in components:
    source = bundle_root / relative
    destination = target_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignored)

gitignore = target_root / ".gitignore"
existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
lines = {line.strip() for line in existing.splitlines()}
rules = (
    ".lecture-state/",
    "state-supervision-evaluation/runs/*/",
    "state-supervision-evaluation/short-tests/results/",
    "state-supervision-evaluation/simulation-game/results/",
)
missing = [rule for rule in rules if rule not in lines]
if missing:
    separator = "" if not existing or existing.endswith("\n") else "\n"
    block = "\n# Lecture state supervision runtime and generated evaluations\n"
    gitignore.write_text(existing + separator + block + "\n".join(missing) + "\n", encoding="utf-8")
PY

python3 "$TARGET_ROOT/state-supervision/supervise.py" --help >/dev/null

VERSION="$(tr -d '[:space:]' < "$TARGET_ROOT/state-supervision/VERSION")"
echo "Installed lecture-state-supervision $VERSION into $TARGET_ROOT"
echo "Agent CLI: python3 $TARGET_ROOT/state-supervision/supervise.py --help"
echo "Human UI:  python3 $TARGET_ROOT/state-supervision/serve.py --repo-root $TARGET_ROOT --data-root $TARGET_ROOT/.lecture-state"
