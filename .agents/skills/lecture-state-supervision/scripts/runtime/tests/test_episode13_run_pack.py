from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[3]
EVALUATION_SCRIPTS = SKILL_ROOT / "scripts" / "evaluation"


class Episode13RunPackTests(unittest.TestCase):
    def test_ready_pack_requires_and_accepts_frozen_metrics_bundle(self):
        with tempfile.TemporaryDirectory(prefix="episode13-pack-test-") as temporary:
            runs_root = Path(temporary) / "runs"
            initialized = subprocess.run(
                [
                    sys.executable,
                    str(EVALUATION_SCRIPTS / "init_episode_run.py"),
                    "--episode-id",
                    "0013",
                    "--slug",
                    "fixture",
                    "--episode-path",
                    "videos/0013-fixture",
                    "--session-ref",
                    "fixture-session",
                    "--system-version",
                    "state-supervision-pre13-fixture",
                    "--run-id",
                    "fixture-run",
                    "--runs-root",
                    str(runs_root),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            run_dir = Path(initialized.stdout.strip())

            manifest_path = run_dir / "run-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["ended_at"] = "2026-09-01T01:00:00Z"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            handoff_path = run_dir / "evaluation-handoff.json"
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
            handoff["status"] = "evaluation_ready"
            handoff["production_outcome"]["user_authority_state"] = "user_review_pending"
            handoff_path.write_text(
                json.dumps(handoff, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            evidence_path = run_dir / "evidence-index.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["generated_at"] = "2026-09-01T01:00:00Z"
            evidence_path.write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            export_dir = run_dir / "frozen-evidence"
            for filename, payload in {
                "manifest.json": {},
                "aggregates.json": [],
                "integrity.json": {"ok": True},
                "metrics.json": {
                    "schema": "lecture-state-supervision-export-metrics-v1",
                    "time_and_flow": {},
                    "parallel_dispatch": {},
                    "agent_activity": {},
                    "human_activity": {},
                    "attention_delivery": {},
                    "quality_and_rework": {},
                    "change_and_recovery": {},
                    "reliability": {},
                    "coverage": {},
                    "unknown_metrics": [],
                },
            }.items():
                (export_dir / filename).write_text(
                    json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8"
                )
            for filename in ("events.jsonl", "commands.jsonl", "capsules.jsonl"):
                (export_dir / filename).write_text("", encoding="utf-8")

            checked = subprocess.run(
                [
                    sys.executable,
                    str(EVALUATION_SCRIPTS / "check_run_pack.py"),
                    str(run_dir),
                    "--ready",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)


if __name__ == "__main__":
    unittest.main()
