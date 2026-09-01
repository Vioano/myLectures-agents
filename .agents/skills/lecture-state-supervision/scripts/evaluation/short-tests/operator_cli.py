#!/usr/bin/env python3
"""Pinned black-box CLI wrapper with append-only command transcripts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def append_jsonl(path: Path, value: dict) -> None:
    encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(descriptor, encoded)
    finally:
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Operate one disposable state-supervision black-box fixture"
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--request-id")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a supervision command is required after --")

    workspace = args.workspace.resolve()
    environment = json.loads(
        (workspace / "environment.json").read_text(encoding="utf-8")
    )
    request_id = args.request_id or "bb_" + uuid.uuid4().hex
    invocation = [
        sys.executable,
        environment["cli"],
        "--data-root",
        environment["data_root"],
        "--repo-root",
        environment["repo_root"],
        "--actor",
        args.actor,
        "--request-id",
        request_id,
        *command,
    ]
    started_at = utc_now()
    completed = subprocess.run(invocation, text=True, capture_output=True, check=False)
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        parsed = None
    append_jsonl(
        workspace / "transcript.jsonl",
        {
            "schema": "state-supervision-blackbox-command-v1",
            "started_at": started_at,
            "completed_at": utc_now(),
            "actor": args.actor,
            "request_id": request_id,
            "command": command,
            "exit_code": completed.returncode,
            "result": parsed,
            "stderr": completed.stderr[:16000],
        },
    )
    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
