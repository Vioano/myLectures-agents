#!/usr/bin/env python3
"""Pure hard check for pinned candidate artifact bytes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    payload = json.load(sys.stdin)
    checks = []
    for artifact in payload.get("artifacts", []):
        path = Path(artifact["absolute_path"])
        exists = path.is_file()
        actual_hash = digest(path) if exists else None
        actual_size = path.stat().st_size if exists else None
        passed = exists and actual_hash == artifact.get("sha256") and actual_size == artifact.get("size")
        checks.append(
            {
                "check": "artifact_bytes",
                "artifact_id": artifact.get("artifact_id"),
                "path": artifact.get("path"),
                "passed": passed,
                "expected_sha256": artifact.get("sha256"),
                "actual_sha256": actual_hash,
                "expected_size": artifact.get("size"),
                "actual_size": actual_size,
            }
        )
    status = "pass" if checks and all(item["passed"] for item in checks) else "fail"
    json.dump(
        {
            "status": status,
            "summary": "all candidate artifacts match" if status == "pass" else "one or more candidate artifacts drifted",
            "checks": checks,
        },
        sys.stdout,
        ensure_ascii=False,
    )
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
