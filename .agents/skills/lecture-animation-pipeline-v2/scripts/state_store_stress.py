#!/usr/bin/env python3
"""Exercise the V2 JSON/JSONL state store under real process contention."""

from __future__ import annotations

import argparse
import json
import multiprocessing
from pathlib import Path
import tempfile

from pipeline_v2_lib.core import object_hash
from pipeline_v2_lib.review_state import commit_review_attempt
from pipeline_v2_lib.storage import append_unique_jsonl, load_json, read_jsonl, write_json


def append_worker(path: str, index: int, queue) -> None:
    try:
        _, appended = append_unique_jsonl(
            Path(path),
            {"verification_key": f"append-{index}", "index": index},
            key_field="verification_key",
        )
        queue.put({"kind": "append", "index": index, "accepted": appended})
    except Exception as exc:  # pragma: no cover - child process diagnostics
        queue.put({"kind": "append", "index": index, "error": str(exc)})


def review_worker(session_path: str, attempt_log: str, expected_hash: str, index: int, queue) -> None:
    try:
        commit_review_attempt(
            session_path=Path(session_path),
            attempt_log=Path(attempt_log),
            expected_session_hash=expected_hash,
            attempt={
                "attempt_id": f"review-{index}",
                "verification_key": f"review-key-{index}",
                "gate_accepted": True,
                "verdict": "revise",
                "submission_hash": f"review-hash-{index}",
                "findings_count": 1,
            },
            scene_slug=f"g{index:03d}",
            manifest_hash=f"manifest-{index}",
            calibration_performed=False,
            reviewer_anomalous=False,
        )
        queue.put({"kind": "review", "index": index, "accepted": True})
    except Exception as exc:  # pragma: no cover - child process diagnostics
        queue.put({"kind": "review", "index": index, "accepted": False, "error": str(exc)})


def run_stress(root: Path, workers: int) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    append_log = root / "append_attempts.jsonl"
    queue = multiprocessing.Queue()
    append_processes = [
        multiprocessing.Process(target=append_worker, args=(str(append_log), index, queue))
        for index in range(workers)
    ]
    for process in append_processes:
        process.start()
    for process in append_processes:
        process.join(30)
    append_results = [queue.get(timeout=5) for _ in append_processes]

    session_path = root / "review_session.json"
    review_log = root / "review_attempts.jsonl"
    session = {
        "schema": "lecture-animation-review-session-v2",
        "session_id": "state-store-stress",
        "scenes": [],
        "full_reviews": 0,
        "calibration_scene_interval": 5,
        "calibration_due": False,
        "revision": 0,
        "applied_review_attempt_ids": [],
        "pending_repairs": {},
    }
    session["session_hash"] = object_hash(session)
    write_json(session_path, session)
    review_processes = [
        multiprocessing.Process(
            target=review_worker,
            args=(str(session_path), str(review_log), session["session_hash"], index, queue),
        )
        for index in range(workers)
    ]
    for process in review_processes:
        process.start()
    for process in review_processes:
        process.join(30)
    review_results = [queue.get(timeout=5) for _ in review_processes]
    current = load_json(session_path)
    accepted_reviews = sum(item.get("accepted") is True for item in review_results)
    stale_reviews = sum("changed during verification" in str(item.get("error", "")) for item in review_results)
    valid = (
        all(process.exitcode == 0 for process in [*append_processes, *review_processes])
        and len(read_jsonl(append_log)) == workers
        and all(item.get("accepted") is True for item in append_results)
        and accepted_reviews == 1
        and stale_reviews == workers - 1
        and len(read_jsonl(review_log)) == 1
        and current.get("full_reviews") == 1
        and len(current.get("pending_repairs", {})) == 1
    )
    return {
        "schema": "lecture-animation-state-store-stress-v1",
        "backend": "fcntl+atomic-json+locked-jsonl",
        "workers": workers,
        "valid": valid,
        "unique_appends": len(read_jsonl(append_log)),
        "review_winners": accepted_reviews,
        "review_stale_rejections": stale_reviews,
        "session_full_reviews": current.get("full_reviews"),
        "pending_repairs": len(current.get("pending_repairs", {})),
        "sqlite_wal_required_for_current_single_host_workload": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--workspace-parent", type=Path, help="create and clean a temporary stress directory here")
    args = parser.parse_args()
    if args.workers < 2:
        raise SystemExit("--workers must be at least 2")
    if args.workspace and args.workspace_parent:
        raise SystemExit("use only one of --workspace or --workspace-parent")
    if args.workspace:
        result = run_stress(args.workspace.resolve(), args.workers)
    else:
        parent = args.workspace_parent.resolve() if args.workspace_parent else None
        if parent:
            parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="mylectures-v2-state-stress-", dir=parent) as temporary:
            result = run_stress(Path(temporary), args.workers)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["valid"] else 2)


if __name__ == "__main__":
    main()
