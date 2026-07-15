#!/usr/bin/env python3
"""Focused process-safety tests for the modular V2 state store."""

from __future__ import annotations

import json
import multiprocessing
from pathlib import Path
import tempfile
import unittest

from pipeline_v2_lib.core import object_hash
from pipeline_v2_lib.review_state import commit_review_attempt
from pipeline_v2_lib.storage import append_unique_jsonl, load_json, read_jsonl, write_json


def append_worker(path: str, index: int) -> None:
    append_unique_jsonl(
        Path(path),
        {"verification_key": f"key-{index}", "index": index},
        key_field="verification_key",
    )


def review_worker(session_path: str, attempt_log: str, expected_hash: str, index: int, queue) -> None:
    try:
        commit_review_attempt(
            session_path=Path(session_path),
            attempt_log=Path(attempt_log),
            expected_session_hash=expected_hash,
            attempt={
                "attempt_id": f"attempt-{index}",
                "verification_key": f"key-{index}",
                "gate_accepted": True,
            },
            scene_slug=f"g{index:03d}",
            manifest_hash=f"manifest-{index}",
            calibration_performed=False,
            reviewer_anomalous=False,
        )
        queue.put((index, "accepted"))
    except Exception as exc:  # pragma: no cover - exercised in child processes
        queue.put((index, str(exc)))


class StorageConcurrencyTests(unittest.TestCase):
    def test_parallel_jsonl_appends_remain_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "attempts.jsonl"
            processes = [multiprocessing.Process(target=append_worker, args=(str(path), index)) for index in range(32)]
            for process in processes:
                process.start()
            for process in processes:
                process.join(10)
                self.assertEqual(process.exitcode, 0)
            rows = read_jsonl(path)
            self.assertEqual(len(rows), 32)
            self.assertEqual({row["index"] for row in rows}, set(range(32)))

    def test_unique_append_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "attempts.jsonl"
            row = {"verification_key": "same", "value": 1}
            self.assertTrue(append_unique_jsonl(path, row, key_field="verification_key")[1])
            self.assertFalse(append_unique_jsonl(path, row, key_field="verification_key")[1])
            self.assertEqual(read_jsonl(path), [row])

    def test_review_session_rejects_stale_concurrent_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session_path = root / "session.json"
            attempt_log = root / "attempts.jsonl"
            session = {
                "schema": "lecture-animation-review-session-v2",
                "session_id": "session-1",
                "scenes": [],
                "full_reviews": 0,
                "calibration_scene_interval": 5,
                "calibration_due": False,
                "revision": 0,
            }
            session["session_hash"] = object_hash(session)
            write_json(session_path, session)
            first = {
                "attempt_id": "attempt-1",
                "verification_key": "key-1",
                "gate_accepted": True,
            }
            stored, appended, current = commit_review_attempt(
                session_path=session_path,
                attempt_log=attempt_log,
                expected_session_hash=session["session_hash"],
                attempt=first,
                scene_slug="g001",
                manifest_hash="manifest-1",
                calibration_performed=False,
                reviewer_anomalous=False,
            )
            self.assertTrue(appended)
            retry_stored, retry_appended, retry_session = commit_review_attempt(
                session_path=session_path,
                attempt_log=attempt_log,
                expected_session_hash=session["session_hash"],
                attempt=first,
                scene_slug="g001",
                manifest_hash="manifest-1",
                calibration_performed=False,
                reviewer_anomalous=False,
            )
            self.assertFalse(retry_appended)
            self.assertEqual(retry_stored["attempt_id"], stored["attempt_id"])
            self.assertEqual(retry_session["full_reviews"], current["full_reviews"])
            with self.assertRaisesRegex(Exception, "changed during verification"):
                commit_review_attempt(
                    session_path=session_path,
                    attempt_log=attempt_log,
                    expected_session_hash=session["session_hash"],
                    attempt={
                        "attempt_id": "attempt-2",
                        "verification_key": "key-2",
                        "gate_accepted": True,
                    },
                    scene_slug="g002",
                    manifest_hash="manifest-2",
                    calibration_performed=False,
                    reviewer_anomalous=False,
                )

    def test_parallel_review_writers_cannot_lose_session_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session_path = root / "session.json"
            attempt_log = root / "attempts.jsonl"
            session = {
                "schema": "lecture-animation-review-session-v2",
                "session_id": "session-parallel",
                "scenes": [],
                "full_reviews": 0,
                "calibration_scene_interval": 5,
                "calibration_due": False,
                "revision": 0,
            }
            session["session_hash"] = object_hash(session)
            write_json(session_path, session)
            queue = multiprocessing.Queue()
            processes = [
                multiprocessing.Process(
                    target=review_worker,
                    args=(str(session_path), str(attempt_log), session["session_hash"], index, queue),
                )
                for index in (1, 2)
            ]
            for process in processes:
                process.start()
            for process in processes:
                process.join(10)
                self.assertEqual(process.exitcode, 0)
            results = [queue.get(timeout=2) for _ in processes]
            accepted = [index for index, result in results if result == "accepted"]
            rejected = [index for index, result in results if "changed during verification" in result]
            self.assertEqual(len(accepted), 1)
            self.assertEqual(len(rejected), 1)
            current = load_json(session_path)
            self.assertEqual(current["full_reviews"], 1)
            self.assertEqual(len(read_jsonl(attempt_log)), 1)

            retry = rejected[0]
            review_worker(str(session_path), str(attempt_log), current["session_hash"], retry, queue)
            self.assertEqual(queue.get(timeout=2), (retry, "accepted"))
            current = load_json(session_path)
            self.assertEqual(current["full_reviews"], 2)
            self.assertEqual(len(read_jsonl(attempt_log)), 2)


if __name__ == "__main__":
    unittest.main()
