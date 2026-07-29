#!/usr/bin/env python3

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("supervisor_watch.py")


class SupervisorWatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.session = self.root / "supervisor_session.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            check=check,
            capture_output=True,
            text=True,
        )

    def begin(self, *extra: str) -> dict:
        result = self.run_cli(
            "begin",
            "--supervisor-agent-id", "root-agent",
            "--assignment", "author-1|animation_author|batch-a|G007C repair|gpt-5.6-sol",
            "--output", str(self.session),
            *extra,
        )
        return json.loads(result.stdout)

    def write_review(self) -> Path:
        path = self.root / "review.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "lecture-animation-independent-review-v2",
                    "verdict": "revise",
                    "findings": [{"id": "f1", "status": "open"}],
                }
            ),
            encoding="utf-8",
        )
        return path

    def write_self_review(self) -> Path:
        from pipeline_v2_lib.core import object_hash

        payload = {
            "schema": "lecture-animation-author-self-review-v2",
            "verdict": "ready_for_independent_review",
            "manifest_hash": "a" * 64,
            "falsification_probe_hash": "b" * 64,
        }
        payload["self_review_hash"] = object_hash(payload)
        path = self.root / "author_self_review.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def write_animatic_artifacts(
        self, scene_slug: str = "g008a"
    ) -> tuple[Path, dict[str, Path]]:
        paths = {
            "plan": self.root / "scene_plan.json",
            "profile": self.root / "profile.json",
            "animatic": self.root / "animatic.mp4",
            "authoring_qc": self.root / "authoring_qc.json",
            "contact_sheet": self.root / "contact_sheet.png",
        }
        paths["plan"].write_text(
            json.dumps(
                {
                    "schema": "lecture-animation-scene-plan-v2",
                    "scene_slug": scene_slug,
                }
            ),
            encoding="utf-8",
        )
        paths["profile"].write_text(
            json.dumps({"schema": "lecture-animation-scene-profile-v2"}),
            encoding="utf-8",
        )
        paths["animatic"].write_bytes(b"low-cost-animatic")
        paths["contact_sheet"].write_bytes(b"contact-sheet")
        paths["authoring_qc"].write_text(
            json.dumps(
                {
                    "schema": "lecture-animation-authoring-qc-report-v2",
                    "scene_slug": scene_slug,
                    "valid": True,
                    "issues": [],
                    "report_hash": "c" * 64,
                }
            ),
            encoding="utf-8",
        )
        checkpoint = self.root / "animatic_checkpoint.json"
        self.run_cli(
            "seal-animatic-checkpoint",
            "--agent-id",
            "author-1",
            "--scene-slug",
            scene_slug,
            "--plan",
            str(paths["plan"]),
            "--profile",
            str(paths["profile"]),
            "--animatic",
            str(paths["animatic"]),
            "--authoring-qc",
            str(paths["authoring_qc"]),
            "--contact-sheet",
            str(paths["contact_sheet"]),
            "--output",
            str(checkpoint),
        )
        return checkpoint, paths

    def test_low_noise_is_default_and_routine_events_are_persisted_only(self) -> None:
        status = self.begin()
        self.assertEqual(status["communication_mode"], "continuous_low_noise")
        event = json.loads(
            self.run_cli(
                "record", "--session", str(self.session),
                "--event-type", "repair_detail", "--agent-id", "author-1",
                "--summary", "Adjusted one retained object checkpoint.",
            ).stdout
        )
        self.assertFalse(event["user_visible"])
        status = json.loads(self.run_cli("status", "--session", str(self.session)).stdout)
        self.assertTrue(status["should_continue_monitoring"])
        self.assertFalse(status["user_update_required"])
        self.assertEqual(status["suppressed_event_count"], 1)
        failed = self.run_cli("finish", "--session", str(self.session), check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("assignments remain active", failed.stderr)

    def test_review_ready_requires_user_update_and_acknowledgement(self) -> None:
        self.begin()
        event = json.loads(
            self.run_cli(
                "record", "--session", str(self.session),
                "--event-type", "human_review_ready", "--agent-id", "author-1",
                "--scene-slug", "g007c", "--summary", "G007C review video passed acceptance.",
                "--artifact", "/tmp/g007c-review.mp4",
            ).stdout
        )
        self.assertTrue(event["user_visible"])
        status = json.loads(self.run_cli("status", "--session", str(self.session)).stdout)
        self.assertTrue(status["user_update_required"])
        self.assertEqual(status["pending_user_events"][0]["event_id"], event["event_id"])
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "author-1", "--state", "completed",
        )
        blocked = self.run_cli("finish", "--session", str(self.session), check=False)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("milestones are acknowledged", blocked.stderr)
        self.run_cli(
            "acknowledge", "--session", str(self.session),
            "--event-id", event["event_id"],
        )
        final_status = json.loads(self.run_cli("finish", "--session", str(self.session)).stdout)
        self.assertTrue(final_status["may_finish"])

    def test_verbose_override_must_be_explicit_and_makes_routine_events_visible(self) -> None:
        failed = self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--assignment", "author-1|animation_author|batch-a|G007C repair|gpt-5.6-sol",
            "--verbose-override", "--output", str(self.session),
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("override reason", failed.stderr)
        self.begin("--verbose-override", "--override-reason", "User requested detailed progress")
        event = json.loads(
            self.run_cli(
                "record", "--session", str(self.session),
                "--event-type", "agent_heartbeat", "--agent-id", "author-1",
                "--summary", "Author is still running the repair pass.",
            ).stdout
        )
        self.assertTrue(event["user_visible"])

    def test_default_roster_cap_rejects_four_subagents(self) -> None:
        result = self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--assignment", "a1|animation_author|batch-a|G001-G003|gpt-5.6-sol",
            "--assignment", "a2|animation_author|batch-b|G004-G006|gpt-5.6-sol",
            "--assignment", "a3|animation_author|batch-c|G007-G009|gpt-5.6-sol",
            "--assignment", "a4|animation_author|batch-d|G010-G012|gpt-5.6-sol",
            "--output", str(self.session), check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exceeds --max-subagents", result.stderr)

    def test_completed_agent_is_reused_for_next_task(self) -> None:
        self.begin("--planned-task", "batch-b|animation_author|G008A-G008C")
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "author-1", "--state", "completed",
        )
        status = json.loads(
            self.run_cli(
                "assign-task", "--session", str(self.session),
                "--agent-id", "author-1", "--role", "animation_author",
                "--task-key", "batch-b", "--scope", "G008A-G008C",
            ).stdout
        )
        self.assertEqual(status["active_assignments"], ["author-1"])
        self.assertEqual(status["roster_metrics"]["historical_identity_count"], 1)
        self.assertEqual(status["roster_metrics"]["reuse_count"], 1)
        self.assertEqual(status["roster_metrics"]["replacement_count"], 0)

    def test_completed_batch_key_can_be_reopened_for_a_new_bounded_cycle(self) -> None:
        self.begin()
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "author-1", "--state", "completed",
        )
        missing_reason = self.run_cli(
            "assign-task", "--session", str(self.session),
            "--agent-id", "author-1", "--role", "animation_author",
            "--task-key", "batch-a",
            "--scope", "G001-G003 visual-finish animatic repair",
            check=False,
        )
        self.assertNotEqual(missing_reason.returncode, 0)
        self.assertIn("requires a concrete --new-task-reason", missing_reason.stderr)

        status = json.loads(
            self.run_cli(
                "assign-task", "--session", str(self.session),
                "--agent-id", "author-1", "--role", "animation_author",
                "--task-key", "batch-a",
                "--scope", "G001-G003 visual-finish animatic repair",
                "--new-task-reason",
                "Main review accepted a repaired design and opened the next bounded animatic cycle.",
            ).stdout
        )
        self.assertEqual(status["active_assignments"], ["author-1"])
        session = json.loads(self.session.read_text())
        assignment = session["assignments"]["author-1"]
        self.assertEqual(assignment["task_key"], "batch-a")
        self.assertEqual(assignment["assignment_history"][-1]["kind"], "batch_reopen")
        self.assertEqual(session["task_queue"]["batch-a"]["reopen_count"], 1)
        self.assertEqual(
            session["task_queue"]["batch-a"]["scope"],
            "G001-G003 visual-finish animatic repair",
        )

    def test_stale_same_owner_batch_state_is_reconciled_before_reopen(self) -> None:
        from pipeline_v2_lib.core import object_hash

        self.begin()
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "author-1", "--state", "completed",
        )
        session = json.loads(self.session.read_text())
        session["task_queue"]["batch-a"].update(
            {"state": "active", "current_agent_id": "author-1"}
        )
        session.pop("session_hash", None)
        session["session_hash"] = object_hash(session)
        self.session.write_text(json.dumps(session), encoding="utf-8")

        status = json.loads(
            self.run_cli(
                "assign-task", "--session", str(self.session),
                "--agent-id", "author-1", "--role", "animation_author",
                "--task-key", "batch-a",
                "--scope", "G001-G003 current-policy animatic repair",
                "--new-task-reason",
                "A migrated session left the old batch active although its sole owner is reusable.",
            ).stdout
        )
        self.assertEqual(status["active_assignments"], ["author-1"])
        session = json.loads(self.session.read_text())
        reconciliation = session["task_queue"]["batch-a"]["stale_state_reconciliation"]
        self.assertEqual(reconciliation["previous_state"], "active")
        self.assertEqual(reconciliation["previous_agent_id"], "author-1")
        self.assertEqual(session["task_queue"]["batch-a"]["reopen_count"], 1)

    def test_nonblocking_review_todo_waits_for_sealed_safe_checkpoint(self) -> None:
        self.begin("--planned-task", "batch-b|animation_author|G008A-G008C")
        todo = json.loads(
            self.run_cli(
                "queue-review-todo",
                "--session",
                str(self.session),
                "--agent-id",
                "author-1",
                "--reviewed-scene-slug",
                "g007c",
                "--wait-for-scene-slug",
                "g008a",
                "--priority",
                "nonblocking",
                "--review-artifact",
                str(self.write_review()),
                "--summary",
                "G007C needs a bounded nonblocking repair after G008A self-review.",
            ).stdout
        )
        self.assertEqual(todo["state"], "deferred_until_safe_checkpoint")
        status = json.loads(
            self.run_cli("status", "--session", str(self.session)).stdout
        )
        self.assertEqual(status["deferred_review_todos"], [todo["todo_id"]])
        self.assertFalse(status["review_delivery_required"])

        self.run_cli(
            "set-assignment",
            "--session",
            str(self.session),
            "--agent-id",
            "author-1",
            "--state",
            "completed",
        )
        allowed = self.run_cli(
            "assign-task",
            "--session",
            str(self.session),
            "--agent-id",
            "author-1",
            "--role",
            "animation_author",
            "--task-key",
            "batch-b",
            "--scope",
            "G008A-G008C",
        )
        self.assertEqual(allowed.returncode, 0)
        status = json.loads(allowed.stdout)
        self.assertEqual(status["active_assignments"], ["author-1"])
        self.assertEqual(status["deferred_review_todos"], [todo["todo_id"]])

        status = json.loads(
            self.run_cli(
                "mark-safe-checkpoint",
                "--session",
                str(self.session),
                "--agent-id",
                "author-1",
                "--scene-slug",
                "g008a",
                "--evidence",
                str(self.write_self_review()),
            ).stdout
        )
        self.assertEqual(status["ready_review_todos"], [todo["todo_id"]])
        self.assertTrue(status["review_delivery_required"])
        self.run_cli(
            "acknowledge-review-delivery",
            "--session",
            str(self.session),
            "--todo-id",
            todo["todo_id"],
            "--delivery-method",
            "followup_task",
            "--delivery-note",
            "Supervisor sent the sealed G007C repair contract after G008A self-review.",
        )
        status = json.loads(self.run_cli("status", "--session", str(self.session)).stdout)
        self.assertEqual(status["active_assignments"], ["author-1"])

    def test_nonblocking_review_todo_can_be_retargeted_before_release(self) -> None:
        self.begin()
        todo = json.loads(
            self.run_cli(
                "queue-review-todo",
                "--session",
                str(self.session),
                "--agent-id",
                "author-1",
                "--reviewed-scene-slug",
                "g007c",
                "--wait-for-scene-slug",
                "g008a-typo",
                "--priority",
                "nonblocking",
                "--review-artifact",
                str(self.write_review()),
                "--summary",
                "Deliver the earlier review after the current scene checkpoint.",
            ).stdout
        )
        retargeted = json.loads(
            self.run_cli(
                "retarget-review-todo",
                "--session",
                str(self.session),
                "--todo-id",
                todo["todo_id"],
                "--wait-for-scene-slug",
                "g008a",
                "--reason",
                "Correct the scheduling slug before any checkpoint is released.",
            ).stdout
        )
        self.assertEqual(retargeted["state"], "deferred_until_safe_checkpoint")
        self.assertEqual(retargeted["wait_for_scene_slug"], "g008a")
        self.assertEqual(
            retargeted["retarget_history"][0]["previous_wait_for_scene_slug"],
            "g008a-typo",
        )
        result = self.run_cli(
            "retarget-review-todo",
            "--session",
            str(self.session),
            "--todo-id",
            todo["todo_id"],
            "--wait-for-scene-slug",
            "g008a",
            "--reason",
            "A no-op retarget must be rejected by the supervisor.",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_review_task_completion_can_release_todo_only_after_owner_is_idle(self) -> None:
        self.begin()
        todo = json.loads(
            self.run_cli(
                "queue-review-todo",
                "--session",
                str(self.session),
                "--agent-id",
                "author-1",
                "--reviewed-scene-slug",
                "g012",
                "--wait-for-scene-slug",
                "g004-review-task",
                "--priority",
                "nonblocking",
                "--review-artifact",
                str(self.write_review()),
                "--summary",
                "Deliver G012 after the separate G004 review task finishes.",
            ).stdout
        )
        completion = self.root / "completed_review.json"
        payload = {
            "schema": "lecture-animation-review-v2",
            "verdict": "revise",
            "manifest_hash": "b" * 64,
            "reviewer_agent_id": "author-1",
            "findings": [{"finding_id": "g004-r01"}],
        }
        completion.write_text(json.dumps(payload), encoding="utf-8")
        blocked = self.run_cli(
            "release-review-todo-after-review-task",
            "--session",
            str(self.session),
            "--todo-id",
            todo["todo_id"],
            "--completion-evidence",
            str(completion),
            "--reason",
            "The separate review task has sealed final evidence.",
            check=False,
        )
        self.assertNotEqual(blocked.returncode, 0)
        self.run_cli(
            "set-assignment",
            "--session",
            str(self.session),
            "--agent-id",
            "author-1",
            "--state",
            "idle",
        )
        released = json.loads(
            self.run_cli(
                "release-review-todo-after-review-task",
                "--session",
                str(self.session),
                "--todo-id",
                todo["todo_id"],
                "--completion-evidence",
                str(completion),
                "--reason",
                "The separate review task has sealed final evidence.",
            ).stdout
        )
        self.assertEqual(released["state"], "ready_to_deliver")
        self.assertEqual(
            released["safe_checkpoint"]["completed_review_task_key"],
            "batch-a",
        )

    def test_planning_task_completion_can_release_todo_after_later_task_blocks(self) -> None:
        self.begin()
        todo = json.loads(
            self.run_cli(
                "queue-review-todo",
                "--session",
                str(self.session),
                "--agent-id",
                "author-1",
                "--reviewed-scene-slug",
                "g002",
                "--wait-for-scene-slug",
                "g005",
                "--priority",
                "nonblocking",
                "--review-artifact",
                str(self.write_review()),
                "--summary",
                "Deliver G002 after the non-authoring G005 impact plan stops.",
            ).stdout
        )
        plan = self.root / "impact_plan.json"
        plan.write_text(
            json.dumps(
                {
                    "schema": "lecture-animation-bounded-author-repair-impact-plan-v1",
                    "scene_slug": "g005",
                    "created_by": "author-1",
                    "state": "awaiting_formal_repair_contract",
                }
            ),
            encoding="utf-8",
        )
        self.run_cli(
            "set-assignment",
            "--session",
            str(self.session),
            "--agent-id",
            "author-1",
            "--state",
            "blocked",
        )
        released = json.loads(
            self.run_cli(
                "release-review-todo-after-planning-task",
                "--session",
                str(self.session),
                "--todo-id",
                todo["todo_id"],
                "--completion-evidence",
                str(plan),
                "--reason",
                "The G005 planning task stopped without any authoring in flight.",
            ).stdout
        )
        self.assertEqual(released["state"], "ready_to_deliver")
        self.assertEqual(
            released["safe_checkpoint"]["completed_planning_task_key"],
            "batch-a",
        )

    def test_nonblocking_todo_accepts_hash_bound_low_cost_animatic_checkpoint(self) -> None:
        self.begin()
        todo = json.loads(
            self.run_cli(
                "queue-review-todo",
                "--session",
                str(self.session),
                "--agent-id",
                "author-1",
                "--reviewed-scene-slug",
                "g007c",
                "--wait-for-scene-slug",
                "g008a",
                "--priority",
                "nonblocking",
                "--review-artifact",
                str(self.write_review()),
                "--summary",
                "Deliver the earlier review after the current animatic reaches its safe gate.",
            ).stdout
        )
        checkpoint, _ = self.write_animatic_artifacts()
        status = json.loads(
            self.run_cli(
                "mark-safe-checkpoint",
                "--session",
                str(self.session),
                "--agent-id",
                "author-1",
                "--scene-slug",
                "g008a",
                "--evidence",
                str(checkpoint),
            ).stdout
        )
        self.assertEqual(status["ready_review_todos"], [todo["todo_id"]])
        session = json.loads(self.session.read_text())
        safe = session["review_todos"][todo["todo_id"]]["safe_checkpoint"]
        self.assertEqual(
            safe["evidence_schema"],
            "lecture-animation-animatic-author-checkpoint-v1",
        )
        self.assertIn("animatic_checkpoint_hash", safe)

    def test_animatic_checkpoint_is_rejected_when_bound_animatic_changes(self) -> None:
        self.begin()
        self.run_cli(
            "queue-review-todo",
            "--session",
            str(self.session),
            "--agent-id",
            "author-1",
            "--reviewed-scene-slug",
            "g007c",
            "--wait-for-scene-slug",
            "g008a",
            "--priority",
            "nonblocking",
            "--review-artifact",
            str(self.write_review()),
            "--summary",
            "The checkpoint must remain bound to the exact reviewed animatic bytes.",
        )
        checkpoint, paths = self.write_animatic_artifacts()
        paths["animatic"].write_bytes(b"changed-after-seal")
        result = self.run_cli(
            "mark-safe-checkpoint",
            "--session",
            str(self.session),
            "--agent-id",
            "author-1",
            "--scene-slug",
            "g008a",
            "--evidence",
            str(checkpoint),
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("animatic", result.stderr)
        self.assertIn("stale", result.stderr)

    def test_animatic_checkpoint_rejects_invalid_authoring_qc(self) -> None:
        paths = {
            "plan": self.root / "scene_plan.json",
            "profile": self.root / "profile.json",
            "animatic": self.root / "animatic.mp4",
            "authoring_qc": self.root / "authoring_qc.json",
            "contact_sheet": self.root / "contact_sheet.png",
        }
        for label, path in paths.items():
            if label == "authoring_qc":
                path.write_text(
                    json.dumps(
                        {
                            "schema": "lecture-animation-authoring-qc-report-v2",
                            "scene_slug": "g008a",
                            "valid": False,
                            "issues": [{"id": "layout"}],
                            "report_hash": "d" * 64,
                        }
                    ),
                    encoding="utf-8",
                )
            else:
                path.write_bytes(label.encode())
        result = self.run_cli(
            "seal-animatic-checkpoint",
            "--agent-id",
            "author-1",
            "--scene-slug",
            "g008a",
            "--plan",
            str(paths["plan"]),
            "--profile",
            str(paths["profile"]),
            "--animatic",
            str(paths["animatic"]),
            "--authoring-qc",
            str(paths["authoring_qc"]),
            "--contact-sheet",
            str(paths["contact_sheet"]),
            "--output",
            str(self.root / "invalid_checkpoint.json"),
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("valid authoring QC", result.stderr)

    def test_blocking_review_todo_requires_immediate_delivery(self) -> None:
        self.begin()
        todo = json.loads(
            self.run_cli(
                "queue-review-todo",
                "--session",
                str(self.session),
                "--agent-id",
                "author-1",
                "--reviewed-scene-slug",
                "g007c",
                "--priority",
                "continuity_blocking",
                "--review-artifact",
                str(self.write_review()),
                "--summary",
                "The G007C exit state invalidates the active G008A entry contract.",
            ).stdout
        )
        self.assertEqual(todo["state"], "interrupt_required")
        status = json.loads(
            self.run_cli("status", "--session", str(self.session)).stdout
        )
        self.assertEqual(
            status["interrupt_required_review_todos"], [todo["todo_id"]]
        )
        self.assertTrue(status["review_delivery_required"])

    def test_finish_rejects_unassigned_planned_task(self) -> None:
        self.begin("--planned-task", "batch-b|animation_author|G008A-G008C")
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "author-1", "--state", "completed",
        )
        status = json.loads(self.run_cli("status", "--session", str(self.session)).stdout)
        self.assertEqual(status["pending_tasks"], ["batch-b"])
        self.assertTrue(status["should_continue_monitoring"])
        result = self.run_cli("finish", "--session", str(self.session), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("planned tasks remain pending", result.stderr)

    def test_replacement_is_blocked_when_compatible_agent_is_reusable(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--assignment", "author-1|animation_author|batch-a|G001-G003|gpt-5.6-sol",
            "--assignment", "author-2|animation_author|batch-b|G004-G006|gpt-5.6-sol",
            "--output", str(self.session),
        )
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "author-2", "--state", "completed",
        )
        result = self.run_cli(
            "authorize-replacement", "--session", str(self.session),
            "--old-agent-id", "author-1", "--reason", "model_change_required",
            "--new-model", "gpt-5.7-sol",
            "--evidence", "The active scene requires the explicitly approved replacement model.",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("compatible roster member is reusable", result.stderr)

    def test_unavailable_agent_replacement_requires_live_snapshot_and_is_recorded(self) -> None:
        self.begin()
        snapshot = {
            "schema": "lecture-animation-agent-availability-v1",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source": "collaboration.list_agents",
            "live_agent_ids": [],
            "reusable_agent_ids": [],
            "followup_attempts": {
                "author-1": {
                    "outcome": "target_not_found",
                    "evidence": "Direct followup_task returned that the canonical child target was not found.",
                }
            },
        }
        from pipeline_v2_lib.core import object_hash
        snapshot["snapshot_hash"] = object_hash(snapshot)
        snapshot_path = self.root / "availability.json"
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
        authorization = json.loads(
            self.run_cli(
                "authorize-replacement", "--session", str(self.session),
                "--old-agent-id", "author-1", "--reason", "task_tree_changed",
                "--availability-snapshot", str(snapshot_path),
                "--evidence", "The parent Codex task changed and the old child identity is absent from the live tree.",
            ).stdout
        )
        status = json.loads(
            self.run_cli(
                "register-replacement", "--session", str(self.session),
                "--authorization-id", authorization["authorization_id"],
                "--new-agent-id", "author-2",
            ).stdout
        )
        self.assertEqual(status["active_assignments"], ["author-2"])
        self.assertEqual(status["roster_metrics"]["historical_identity_count"], 2)
        self.assertEqual(status["roster_metrics"]["replacement_count"], 1)

    def test_replacement_rejects_visibility_snapshot_without_direct_followup_probe(self) -> None:
        self.begin()
        snapshot = {
            "schema": "lecture-animation-agent-availability-v1",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source": "collaboration.list_agents",
            "live_agent_ids": [],
            "reusable_agent_ids": [],
        }
        from pipeline_v2_lib.core import object_hash
        snapshot["snapshot_hash"] = object_hash(snapshot)
        snapshot_path = self.root / "availability-no-probe.json"
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
        result = self.run_cli(
            "authorize-replacement", "--session", str(self.session),
            "--old-agent-id", "author-1", "--reason", "agent_unavailable",
            "--availability-snapshot", str(snapshot_path),
            "--evidence", "The first list_agents snapshot did not display the original child identity.",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("direct followup_task evidence", result.stderr)

    def test_original_identity_can_be_restored_after_mistaken_replacement(self) -> None:
        self.begin()
        unavailable = json.loads(
            self.run_cli(
                "seal-availability-snapshot",
                "--followup-attempt",
                "author-1|target_not_found|Direct followup_task reported that the original target was not found.",
                "--output",
                str(self.root / "unavailable.json"),
            ).stdout
        )
        authorization = json.loads(
            self.run_cli(
                "authorize-replacement", "--session", str(self.session),
                "--old-agent-id", "author-1", "--reason", "agent_unavailable",
                "--availability-snapshot", str(self.root / "unavailable.json"),
                "--evidence", "A sealed direct followup probe reported the original identity unavailable.",
            ).stdout
        )
        self.run_cli(
            "register-replacement", "--session", str(self.session),
            "--authorization-id", authorization["authorization_id"],
            "--new-agent-id", "author-2",
        )
        restored_path = self.root / "restored.json"
        self.run_cli(
            "seal-availability-snapshot",
            "--live-agent-id", "author-1",
            "--reusable-agent-id", "author-1",
            "--followup-attempt",
            "author-1|restored|Direct followup_task revived the original canonical identity and prior context.",
            "--output", str(restored_path),
        )
        status = json.loads(
            self.run_cli(
                "restore-original-identity",
                "--session", str(self.session),
                "--original-agent-id", "author-1",
                "--replacement-agent-id", "author-2",
                "--availability-snapshot", str(restored_path),
                "--evidence", "The original identity was directly restored before the replacement performed production.",
            ).stdout
        )
        self.assertEqual(status["active_assignments"], ["author-1"])
        self.assertEqual(status["roster_metrics"]["active_replacement_count"], 0)
        self.assertEqual(status["roster_metrics"]["replacement_count"], 1)
        self.assertTrue(status["roster_clean"])

    def test_unused_replacement_authorization_can_be_cancelled_after_restore_probe(self) -> None:
        self.begin()
        unavailable_path = self.root / "unavailable.json"
        self.run_cli(
            "seal-availability-snapshot",
            "--followup-attempt",
            "author-1|target_unavailable|Direct followup_task could not activate the preserved canonical child identity.",
            "--output", str(unavailable_path),
        )
        authorization = json.loads(
            self.run_cli(
                "authorize-replacement", "--session", str(self.session),
                "--old-agent-id", "author-1", "--reason", "agent_unavailable",
                "--availability-snapshot", str(unavailable_path),
                "--evidence", "The sealed direct probe temporarily reported the original identity unavailable.",
            ).stdout
        )
        restored_path = self.root / "restored.json"
        self.run_cli(
            "seal-availability-snapshot",
            "--live-agent-id", "author-1",
            "--reusable-agent-id", "author-1",
            "--followup-attempt",
            "author-1|restored|A second direct followup_task restored the original identity before spawn.",
            "--output", str(restored_path),
        )
        status = json.loads(
            self.run_cli(
                "cancel-replacement-authorization",
                "--session", str(self.session),
                "--authorization-id", authorization["authorization_id"],
                "--availability-snapshot", str(restored_path),
                "--evidence", "The original identity recovered before any replacement agent was spawned.",
            ).stdout
        )
        self.assertEqual(status["roster_metrics"]["pending_replacement_authorizations"], [])
        self.assertTrue(status["roster_clean"])

    def test_finish_rejects_blocked_assignment(self) -> None:
        self.begin()
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "author-1", "--state", "blocked",
        )
        result = self.run_cli("finish", "--session", str(self.session), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("assignments remain blocked", result.stderr)


if __name__ == "__main__":
    unittest.main()
