#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install the self-contained lecture-state-supervision Skill into a project.

Usage:
  <skill-folder>/scripts/install.sh /absolute/path/to/project

Only the lecture-state-supervision Skill folder is copied. Runtime databases,
historical evaluation results and unrelated project files are never copied.
EOF
}

if [[ $# -ne 1 || "$1" == "-h" || "$1" == "--help" ]]; then
  usage
  [[ $# -eq 1 ]] && exit 0
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_ROOT="$(cd "$1" 2>/dev/null && pwd)" || {
  echo "Target project must already exist: $1" >&2
  exit 2
}
TARGET_SKILL="$TARGET_ROOT/.agents/skills/lecture-state-supervision"

if [[ "$TARGET_ROOT" == "/" || "$TARGET_ROOT" == "$HOME" ]]; then
  echo "Refusing an overly broad project target: $TARGET_ROOT" >&2
  exit 2
fi

for required in \
  "SKILL.md" \
  "BUNDLE_MANIFEST.json" \
  "scripts/runtime/supervise.py" \
  "scripts/runtime/serve.py" \
  "scripts/evaluation/init_episode_run.py" \
  "references/operator-guide.md"; do
  if [[ ! -f "$SKILL_ROOT/$required" ]]; then
    echo "Skill is incomplete; missing $required" >&2
    exit 1
  fi
done

python3 - "$SKILL_ROOT" "$TARGET_SKILL" "$TARGET_ROOT" <<'PY'
from __future__ import annotations

import fnmatch
from pathlib import Path
import shutil
import sys

source = Path(sys.argv[1]).resolve()
destination = Path(sys.argv[2]).resolve()
target_root = Path(sys.argv[3]).resolve()


def ignored(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name == "__pycache__"
        or name == ".DS_Store"
        or name.startswith("._")
        or fnmatch.fnmatch(name, "*.pyc")
    }


if source != destination:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignored)

gitignore = target_root / ".gitignore"
existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
lines = {line.strip() for line in existing.splitlines()}
rules = (
    ".lecture-state/",
    "review/state-supervision/short-tests/results/**/*workspaces/",
    "review/state-supervision/short-tests/results/**/*oracle.json",
    "review/state-supervision/simulation-game/results/**/*workspaces/",
    "review/state-supervision/simulation-game/results/**/*oracle.json",
    "review/state-supervision/simulation-game/results/**/*frozen-evidence/",
)
missing = [rule for rule in rules if rule not in lines]
if missing:
    separator = "" if not existing or existing.endswith("\n") else "\n"
    block = "\n# Lecture state supervision runtime and generated evaluation internals\n"
    gitignore.write_text(existing + separator + block + "\n".join(missing) + "\n", encoding="utf-8")
PY

python3 "$TARGET_SKILL/scripts/runtime/supervise.py" --help >/dev/null

VERSION="$(tr -d '[:space:]' < "$TARGET_SKILL/VERSION")"
echo "Installed self-contained lecture-state-supervision $VERSION"
echo "Skill:     $TARGET_SKILL"
echo "Agent CLI: python3 $TARGET_SKILL/scripts/runtime/supervise.py --help"
echo "Human UI:  python3 $TARGET_SKILL/scripts/runtime/serve.py --repo-root $TARGET_ROOT --data-root $TARGET_ROOT/.lecture-state"
