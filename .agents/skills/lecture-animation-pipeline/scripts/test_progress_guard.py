#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("progress_guard.py")
T0 = "2026-01-01T00:00:00+00:00"


class ProgressGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "episode"
        self.root.mkdir()
        self.state = self.root / "review" / "progress" / "repair.json"
        self.artifact = self.root / "candidate.txt"
        self.artifact.write_text("v1\n", encoding="utf-8")
        self.cli(
            "init",
            "--project-root", str(self.root),
            "--state", str(self.state),
            "--task-key", "g007-repair",
            "--phase", "repair",
            "--gate", "human_revise",
            "--next-minimal-action", "separate one spoken phrase",
            "--wall-budget-seconds", "1200",
            "--idle-budget-seconds", "300",
            "--dependency-wait-seconds", "240",
            "--now", T0,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=check,
        )

    def data(self) -> dict:
        return json.loads(self.state.read_text(encoding="utf-8"))

    def status(self, now: str, check: bool = True) -> dict:
        result = self.cli("status", "--state", str(self.state), "--now", now, check=check)
        return json.loads(result.stdout)

    def signal(self, event_type: str, now: str, *extra: str, check: bool = True) -> dict:
        result = self.cli(
            "signal", "--state", str(self.state), "--event-type", event_type,
            "--now", now, *extra, check=check,
        )
        return json.loads(result.stdout)

    def test_warning_then_hard_wall_budget_requires_reflection(self) -> None:
        state = self.data()
        state["config"]["idle_budget_seconds"] = 2000
        state.pop("guard_hash")
        # Re-seal through a harmless command is intentionally impossible;
        # initialize a second state with the needed threshold instead.
        self.state.unlink()
        self.cli(
            "init", "--project-root", str(self.root), "--state", str(self.state),
            "--task-key", "wall", "--phase", "render", "--gate", "candidate",
            "--next-minimal-action", "render once", "--wall-budget-seconds", "1200",
            "--idle-budget-seconds", "2000", "--now", T0,
        )
        self.assertEqual(self.status("2026-01-01T00:15:00+00:00")["status"], "warning")
        result = self.status("2026-01-01T00:20:00+00:00", check=False)
        self.assertEqual(result["status"], "reflection_required")
        self.assertIn("wall_budget_exceeded", {row["key"] for row in result["triggers"]})

    def test_idle_without_meaningful_output_is_nonzero_hard_stop(self) -> None:
        result = self.status("2026-01-01T00:05:00+00:00", check=False)
        self.assertEqual(result["status"], "reflection_required")
        self.assertIn("no_meaningful_output", {row["key"] for row in result["triggers"]})

    def test_three_changed_nonadvancing_checkpoints_trigger_churn(self) -> None:
        last = None
        for index, timestamp in enumerate(("00:01:00", "00:02:00", "00:03:00"), 2):
            self.artifact.write_text(f"v{index}\n", encoding="utf-8")
            last = self.cli(
                "checkpoint", "--state", str(self.state), "--kind", "qc_evidence",
                "--artifact", str(self.artifact), "--gate", "human_revise",
                "--summary", f"evidence {index}",
                "--next-minimal-action", "advance the repair gate",
                "--now", f"2026-01-01T{timestamp}+00:00", check=index < 4,
            )
        assert last is not None
        payload = json.loads(last.stdout)
        self.assertEqual(payload["status"], "reflection_required")
        self.assertIn(
            "artifact_growth_without_state_advance",
            {row["key"] for row in payload["triggers"]},
        )

    def test_gate_advance_resets_churn_and_revise(self) -> None:
        self.signal("revise", "2026-01-01T00:01:00+00:00")
        self.artifact.write_text("v2\n", encoding="utf-8")
        result = self.cli(
            "checkpoint", "--state", str(self.state), "--kind", "state_advance",
            "--artifact", str(self.artifact), "--gate", "render_ready", "--gate-advanced",
            "--summary", "repair gate advanced", "--next-minimal-action", "render once",
            "--now", "2026-01-01T00:02:00+00:00",
        )
        self.assertEqual(json.loads(result.stdout)["status"], "running")
        self.assertEqual(self.data()["live_counters"]["consecutive_revise"], 0)

    def test_revise_pattern_commitment_dependency_and_scope_triggers(self) -> None:
        self.signal("revise", "2026-01-01T00:01:00+00:00")
        result = self.signal("revise", "2026-01-01T00:02:00+00:00", check=False)
        self.assertEqual(result["status"], "reflection_required")

        cases = (
            ("pattern_recurrence", ("--pattern-key", "formula_collision")),
            ("delivery_commitment", ("--deadline", "2026-01-01T00:02:00+00:00")),
            ("dependency_wait", ("--note", "reviewer")),
            ("scope_expansion", ()),
        )
        for event, extra in cases:
            with self.subTest(event=event):
                self.tearDown()
                self.setUp()
                first = self.signal(event, "2026-01-01T00:01:00+00:00", *extra, check=False)
                if event == "pattern_recurrence":
                    first = self.signal(event, "2026-01-01T00:02:00+00:00", *extra, check=False)
                elif event == "dependency_wait":
                    first = self.status("2026-01-01T00:05:00+00:00", check=False)
                elif event == "delivery_commitment":
                    first = self.status("2026-01-01T00:02:00+00:00", check=False)
                self.assertEqual(first["status"], "reflection_required")

    def test_reflection_blocks_work_until_replan_and_resume(self) -> None:
        self.signal("scope_expansion", "2026-01-01T00:01:00+00:00", check=False)
        blocked = self.cli(
            "checkpoint", "--state", str(self.state), "--kind", "code_patch",
            "--artifact", str(self.artifact), "--gate", "human_revise",
            "--summary", "must block", "--next-minimal-action", "none",
            "--now", "2026-01-01T00:02:00+00:00", check=False,
        )
        self.assertEqual(blocked.returncode, 2)
        self.cli(
            "reflect", "--state", str(self.state),
            "--blocked-gate", "human_revise", "--window-output", "one rejected candidate",
            "--invalid-assumption", "more motion would fix spoken cadence",
            "--next-minimal-action", "repair only the audio cut",
            "--path-decision", "change_strategy",
            "--scope-boundary", "do not change approved animation source",
            "--now", "2026-01-01T00:03:00+00:00",
        )
        resumed = self.cli(
            "resume", "--state", str(self.state),
            "--next-minimal-action", "repair only the audio cut",
            "--now", "2026-01-01T00:04:00+00:00",
        )
        self.assertEqual(json.loads(resumed.stdout)["attempt"], 2)

    def test_state_hash_rejects_manual_edit_and_state_cannot_be_progress(self) -> None:
        state = self.data()
        state["current_gate"] = "forged"
        self.state.write_text(json.dumps(state), encoding="utf-8")
        tampered = self.cli("status", "--state", str(self.state), check=False)
        self.assertEqual(tampered.returncode, 2)
        self.assertIn("hash is invalid", tampered.stdout)

        self.tearDown()
        self.setUp()
        rejected = self.cli(
            "checkpoint", "--state", str(self.state), "--kind", "state_advance",
            "--artifact", str(self.state), "--gate", "next", "--gate-advanced",
            "--summary", "self", "--next-minimal-action", "none", check=False,
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("cannot count", rejected.stdout)

    def test_directory_checkpoint_and_exact_completion_evidence(self) -> None:
        package = self.root / "review" / "package"
        package.mkdir(parents=True)
        (package / "review.json").write_text("{}\n", encoding="utf-8")
        checkpoint = self.cli(
            "checkpoint", "--state", str(self.state), "--kind", "portable_handoff",
            "--artifact", str(package), "--gate", "handoff", "--gate-advanced",
            "--summary", "portable package", "--next-minimal-action", "complete",
            "--now", "2026-01-01T00:01:00+00:00",
        )
        self.assertEqual(json.loads(checkpoint.stdout)["changed"][0]["kind"], "directory")
        completed = self.cli(
            "complete", "--state", str(self.state), "--evidence", str(package),
            "--gate", "handed_off", "--now", "2026-01-01T00:02:00+00:00",
        )
        self.assertEqual(json.loads(completed.stdout)["status"], "completed")


if __name__ == "__main__":
    unittest.main()
