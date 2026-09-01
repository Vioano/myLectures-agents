from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from supervision.service import SupervisionService
from supervision.store import DataRoot


class FixedClock:
    def __init__(self, value: str = "2026-08-30T00:00:00.000Z"):
        self.value = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

    def __call__(self) -> str:
        return self.value.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


class ServiceCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="lecture-state-test-")
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.reference = self.repo / "guidance.md"
        self.reference.write_text("# Required guidance\nUse exact evidence.\n", encoding="utf-8")
        self.artifact = self.repo / "result.bin"
        self.artifact.write_bytes(b"deterministic-result")
        self.validator_dir = self.repo / "validators" / "integrity"
        self.validator_dir.mkdir(parents=True)
        self.validator_script = self.validator_dir / "run.py"
        self.validator_script.write_text(
            """#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import sys

payload = json.load(sys.stdin)
checks = []
for artifact in payload.get(\"artifacts\", []):
    path = Path(artifact[\"absolute_path\"])
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    checks.append({\"artifact_id\": artifact.get(\"artifact_id\"), \"passed\": actual == artifact.get(\"sha256\")})
status = \"pass\" if checks and all(item[\"passed\"] for item in checks) else \"fail\"
json.dump({\"status\": status, \"summary\": \"fixture integrity\", \"checks\": checks}, sys.stdout)
raise SystemExit(0 if status == \"pass\" else 2)
""",
            encoding="utf-8",
        )
        self.validator_manifest = self.validator_dir / "manifest.json"
        self.validator_manifest.write_text(
            json.dumps(
                {
                    "schema": "lecture-supervision-validator-v1",
                    "validator_id": "fixture-integrity",
                    "version": "1.0.0",
                    "status": "active",
                    "description": "Test exact artifact bytes",
                    "runner": {"command": ["python3", "run.py"], "timeout_seconds": 10},
                }
            ),
            encoding="utf-8",
        )
        self.clock = FixedClock()
        self.data_root = DataRoot(self.root / "state")
        self.service = SupervisionService(
            self.data_root,
            self.repo,
            clock=self.clock,
            lease_seconds=60,
        )
        result = self.service.create_episode(
            episode_id="EP",
            title="Test episode",
            mission="Exercise supervision invariants",
            actor="planner",
            request_id="create-episode",
        )
        self.assertTrue(result["ok"], result)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def add_task(self, task_id: str, **overrides):
        spec = {
            "title": f"Task {task_id}",
            "goal": f"Complete {task_id} with exact evidence",
            "references": ["guidance.md"],
            "required_artifact_roles": ["result"],
        }
        spec.update(overrides)
        result = self.service.add_task(
            "EP",
            task_id=task_id,
            actor="planner",
            request_id=f"add-{task_id}",
            **spec,
        )
        self.assertTrue(result["ok"], result)
        return result

    def approve_task(
        self,
        task_id: str,
        *,
        author: str = "Ada",
        reviewer: str = "Bo",
        role: str = "result",
        path: str = "result.bin",
    ):
        begin = self.service.begin("EP", task_id, actor=author, request_id=f"begin-{task_id}")
        self.assertTrue(begin["ok"], begin)
        submit = self.service.submit(
            "EP",
            task_id,
            actor=author,
            artifacts=[{"role": role, "path": path}],
            request_id=f"submit-{task_id}",
        )
        self.assertTrue(submit["ok"], submit)
        context = self.service.review_context("EP", task_id, actor=reviewer)
        self.assertTrue(context["ok"], context)
        review = self.service.review(
            "EP",
            task_id,
            actor=reviewer,
            verdict="pass",
            review_context_hash=context["review_context_hash"],
            request_id=f"review-{task_id}",
        )
        self.assertTrue(review["ok"], review)
        return review
