#!/usr/bin/env python3
"""Create a production-shadow-run evaluation pack without touching the active Skill."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
import os
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = SKILL_ROOT / "scripts" / "evaluation" / "templates"
INSTALLED_PROJECT_ROOT = (
    SKILL_ROOT.parents[2]
    if SKILL_ROOT.parent.name == "skills" and SKILL_ROOT.parent.parent.name == ".agents"
    else Path.cwd()
)
RUNS = Path(
    os.environ.get(
        "LECTURE_STATE_EVALUATION_ROOT",
        str(INSTALLED_PROJECT_ROOT / "review" / "state-supervision" / "runs"),
    )
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def replace_tokens(value, replacements):
    if isinstance(value, dict):
        return {key: replace_tokens(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_tokens(item, replacements) for item in value]
    if isinstance(value, str):
        for token, replacement in replacements.items():
            value = value.replace(token, replacement)
    return value


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--episode-path", required=True)
    parser.add_argument("--session-ref", required=True)
    parser.add_argument("--system-version", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--runs-root", type=Path, default=RUNS)
    args = parser.parse_args()

    started_at = utc_now()
    timestamp = started_at.replace("-", "").replace(":", "").replace("T", "-").replace("Z", "")
    run_id = args.run_id or f"{args.episode_id}-{args.slug}-{timestamp}"
    run_dir = args.runs_root.resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "frozen-evidence").mkdir()

    replacements = {
        "__RUN_ID__": run_id,
        "__EPISODE_ID__": args.episode_id,
        "__EPISODE_SLUG__": args.slug,
        "__EPISODE_PATH__": args.episode_path,
        "__SESSION_REF__": args.session_ref,
        "__SYSTEM_VERSION__": args.system_version,
        "__STARTED_AT__": started_at,
    }

    manifest = replace_tokens(
        json.loads((TEMPLATES / "run-manifest.json").read_text(encoding="utf-8")),
        replacements,
    )
    handoff = replace_tokens(
        json.loads((TEMPLATES / "evaluation-handoff.json").read_text(encoding="utf-8")),
        replacements,
    )
    retrospective = replace_tokens(
        (TEMPLATES / "episode-run-retrospective.md").read_text(encoding="utf-8"),
        replacements,
    )

    write_json(run_dir / "run-manifest.json", manifest)
    write_json(run_dir / "evaluation-handoff.json", handoff)
    write_json(
        run_dir / "evidence-index.json",
        {
            "schema": "state-supervision-evidence-index-v1",
            "run_id": run_id,
            "generated_at": None,
            "entries": [],
        },
    )
    (run_dir / "observations.jsonl").write_text("", encoding="utf-8")
    (run_dir / "retrospective.md").write_text(retrospective, encoding="utf-8")

    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
