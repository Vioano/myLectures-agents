#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/lecture-state-skill.XXXXXX")"
SERVER_PID=""

cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -rf -- "$TMP_ROOT"
}
trap cleanup EXIT INT TERM

required=(
  "SKILL.md"
  "BUNDLE_MANIFEST.json"
  "references/operator-guide.md"
  "scripts/runtime/supervise.py"
  "scripts/runtime/serve.py"
  "scripts/runtime/static/index.html"
  "scripts/evaluation/init_episode_run.py"
  "scripts/install.sh"
)
for relative in "${required[@]}"; do
  if [[ ! -f "$SKILL_ROOT/$relative" ]]; then
    echo "Skill verification failed: missing $relative" >&2
    exit 1
  fi
done

python3 "$SKILL_ROOT/scripts/runtime/supervise.py" --help >/dev/null
python3 "$SKILL_ROOT/scripts/evaluation/init_episode_run.py" --help >/dev/null

# Prove the only installation unit needed is this Skill directory.
PROJECT_ROOT="$TMP_ROOT/project"
mkdir -p "$PROJECT_ROOT"
"$SKILL_ROOT/scripts/install.sh" "$PROJECT_ROOT" >/dev/null
INSTALLED_SKILL="$PROJECT_ROOT/.agents/skills/lecture-state-supervision"

(
  cd "$INSTALLED_SKILL/scripts/runtime"
  python3 -m unittest discover -s . -t .
)
python3 "$INSTALLED_SKILL/scripts/evaluation/init_episode_run.py" --help >/dev/null

CLI=(
  python3 "$INSTALLED_SKILL/scripts/runtime/supervise.py"
  --data-root "$PROJECT_ROOT/.lecture-state"
  --repo-root "$PROJECT_ROOT"
  --actor skill-verifier
  --compact
)

"${CLI[@]}" episode-create skill-smoke \
  --title "Self-contained Skill smoke test" \
  --mission "Prove one copied Skill folder provides state, API and UI" \
  >"$TMP_ROOT/create.json"
"${CLI[@]}" episodes >"$TMP_ROOT/episodes.json"
"${CLI[@]}" next skill-smoke >"$TMP_ROOT/next.json"

python3 - "$TMP_ROOT/create.json" "$TMP_ROOT/episodes.json" "$TMP_ROOT/next.json" <<'PY'
import json
from pathlib import Path
import sys

created, episodes, next_action = [json.loads(Path(path).read_text()) for path in sys.argv[1:]]
assert created.get("ok") is True, created
assert any(item.get("episode_id") == "skill-smoke" for item in episodes.get("episodes", [])), episodes
assert next_action.get("ok") is True, next_action
PY

PORT="$(python3 - <<'PY'
import socket
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    print(listener.getsockname()[1])
PY
)"

python3 "$INSTALLED_SKILL/scripts/runtime/serve.py" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --data-root "$PROJECT_ROOT/.lecture-state" \
  --repo-root "$PROJECT_ROOT" \
  >"$TMP_ROOT/server.log" 2>&1 &
SERVER_PID="$!"

python3 - "$PORT" <<'PY'
from __future__ import annotations

import json
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

port = int(sys.argv[1])
base = f"http://127.0.0.1:{port}"
last_error = None
for _ in range(80):
    try:
        with urlopen(base + "/api/health", timeout=1) as response:
            health = json.load(response)
        with urlopen(base + "/api/episodes", timeout=1) as response:
            episodes = json.load(response)
        with urlopen(base + "/", timeout=1) as response:
            index = response.read().decode("utf-8")
        assert health.get("ok") is True, health
        assert any(item.get("episode_id") == "skill-smoke" for item in episodes.get("episodes", [])), episodes
        assert "Lecture Supervision" in index, "Human UI shell did not load"
        break
    except (AssertionError, OSError, URLError, ValueError) as error:
        last_error = error
        time.sleep(0.1)
else:
    raise SystemExit(f"HTTP/UI smoke test failed: {last_error}")
PY

VERSION="$(tr -d '[:space:]' < "$SKILL_ROOT/VERSION")"
echo "PASS self-contained lecture-state-supervision Skill $VERSION"
echo "PASS Skill-only install, Agent CLI, persistent backend, Human UI and evaluation tooling"
