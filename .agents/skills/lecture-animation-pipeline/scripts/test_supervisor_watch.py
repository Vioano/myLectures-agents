#!/usr/bin/env python3

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from pipeline_v2_lib.core import object_hash
from pipeline_v2_lib.engine import (
    DELIVERY_STAGE_DEADLINE_SECONDS,
    PIPELINE_PREFLIGHT_SCHEMA,
    PIPELINE_PREFLIGHT_TESTS,
    artifact_snapshot,
    default_efficiency_budget,
    default_efficiency_quality_target,
    delivery_clock_initial_hash,
    empty_efficiency_reservation_ledger,
    skill_tree_hash,
)


SCRIPT = Path(__file__).with_name("supervisor_watch.py")


class SupervisorWatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.episode = self.root / "capacity-sources"
        self.episode.mkdir(parents=True)
        skill_root = self.root / ".agents" / "skills" / "lecture-animation-pipeline"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "# supervisor test skill\n", encoding="utf-8"
        )
        self.session = self.episode / "supervisor_session.json"

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

    def compile_capacity_evidence(
        self,
        *,
        reviewer_wait_minutes: float = 12.0,
        candidate_queue_depth: int = 0,
        paused_minutes: float = 0.0,
    ) -> Path:
        source_root = self.episode
        source_root.mkdir(parents=True, exist_ok=True)
        supervisor = json.loads(self.session.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc)
        clock_path = source_root / "delivery_clock.json"
        board = {}
        if candidate_queue_depth:
            board = {
                f"g{index:03d}": {
                    "state": "rendered",
                    "owner_agent_id": f"owner-{index}",
                    "history": [],
                }
                for index in range(1, candidate_queue_depth + 1)
            }
        preflight_path = self.root / "pipeline-preflight.json"
        preflight = {
            "schema": PIPELINE_PREFLIGHT_SCHEMA,
            "created_at": now.isoformat(),
            "repo_root": str(self.root),
            "skill_tree_hash": skill_tree_hash(self.root, None),
            "tests": list(PIPELINE_PREFLIGHT_TESTS),
            "command": ["python3", "-m", "unittest"],
            "returncode": 0,
            "duration_seconds": 1.0,
            "stdout_sha256": "a" * 64,
            "stderr_sha256": "b" * 64,
            "status": "pass",
        }
        preflight["receipt_hash"] = object_hash(preflight)
        preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
        idle_since = now - timedelta(minutes=reviewer_wait_minutes)
        t0_time = idle_since - timedelta(minutes=5)
        t0 = t0_time.isoformat()
        active_intervals = [
            {"started_at": t0, "ended_at": None, "reason": "test"}
        ]
        pause_intervals: list[dict[str, str]] = []
        if paused_minutes:
            pause_start = idle_since + timedelta(minutes=1)
            pause_end = pause_start + timedelta(minutes=paused_minutes)
            if pause_end >= now:
                raise AssertionError(
                    "paused test time must leave a positive active tail"
                )
            active_intervals = [
                {
                    "started_at": t0,
                    "ended_at": pause_start.isoformat(),
                    "reason": "test",
                },
                {
                    "started_at": pause_end.isoformat(),
                    "ended_at": None,
                    "reason": "resumed test",
                },
            ]
            pause_intervals = [
                {
                    "kind": "human_wait",
                    "started_at": pause_start.isoformat(),
                    "ended_at": pause_end.isoformat(),
                    "reason": "test human pause",
                }
            ]
        clock = {
            "schema": "lecture-animation-delivery-clock-v1",
            "episode": "capacity-sources",
            "t0": t0,
            "created_at": t0,
            "status": "active",
            "current_stage": "fanout",
            "stage_deadline_seconds": dict(DELIVERY_STAGE_DEADLINE_SECONDS),
            "delivery_target_seconds": 8 * 3600,
            "retrospective_reserve_seconds": 45 * 60,
            "max_production_agents": int(supervisor["max_subagents"]),
            "max_frozen_candidates": 2,
            "sol_review_model": "gpt-5.6-sol",
            "pipeline_preflight": artifact_snapshot(preflight_path, self.root),
            "pipeline_preflight_hash": preflight["receipt_hash"],
            "skill_tree_hash_at_t0": skill_tree_hash(self.root, None),
            "active_intervals": active_intervals,
            "pause_intervals": pause_intervals,
            "checkpoints": [
                {
                    "stage": "fanout",
                    "created_at": idle_since.isoformat(),
                }
            ],
            "representative_scene": None,
            "representative_release": None,
            "scene_board": board,
            "scope_forecast": {
                "planned_scene_count": 6,
                "approved_narration_minutes": 8.0,
                "new_representation_family_count": 1,
                "approved_grammar_reuse": True,
                "forecast_class": "matched_envelope",
                "normalized_delivery_hours": 8.0,
            },
        }
        clock["clock_hash"] = object_hash(clock)
        clock_path.write_text(json.dumps(clock), encoding="utf-8")

        phase_log = source_root / "episode_phase_events.jsonl"
        phase_event = {
            "schema": "lecture-animation-phase-event-v2",
            "event_id": "capacity-observed-phase",
            "phase_instance_id": "capacity-observed-phase-instance",
            "run_id": "capacity-observed-run",
            "scene_slug": "g001",
            "phase": "planning",
            "phase_purpose": "episode_spine",
            "started_at": (now - timedelta(minutes=20)).isoformat(),
            "ended_at": (now - timedelta(minutes=19, seconds=59)).isoformat(),
            "duration_seconds": 1.0,
            "input_tokens": 100,
            "cached_input_tokens": 50,
            "output_tokens": 10,
            "reasoning_tokens": 5,
            "token_observed": True,
        }
        phase_log.write_text(json.dumps(phase_event) + "\n", encoding="utf-8")
        contract_path = source_root / "efficiency.json"
        ledger_path = source_root / "episode_token_reservations.json"
        contract = {
            "schema": "lecture-animation-episode-efficiency-contract-v4",
            "workflow_gate_version": 1,
            "created_at": now.isoformat(),
            "episode": "capacity-sources",
            "canonical_repo_root": str(self.root),
            "central_phase_log": "capacity-sources/episode_phase_events.jsonl",
            "central_reservation_ledger": (
                "capacity-sources/episode_token_reservations.json"
            ),
            "budget": default_efficiency_budget(),
            "quality_target": default_efficiency_quality_target(),
            "status": "active",
            "delivery_clock_binding": {
                "path": "capacity-sources/delivery_clock.json",
                "t0": t0,
                "initial_clock_hash": delivery_clock_initial_hash(clock),
            },
        }
        contract["contract_hash"] = object_hash(contract)
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        ledger = empty_efficiency_reservation_ledger(contract)
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
        output = source_root / "capacity_evidence.json"
        self.run_cli(
            "seal-capacity-evidence",
            "--repo-root", str(self.root),
            "--session", str(self.session),
            "--delivery-clock", str(clock_path),
            "--efficiency-contract", str(contract_path),
            "--output", str(output),
        )
        return output

    def compile_capacity_availability(
        self,
        *,
        live_agent_ids: tuple[str, ...] = (),
        reusable_agent_ids: tuple[str, ...] = (),
        followup_attempts: tuple[str, ...] = (),
        name: str = "capacity-availability.json",
    ) -> Path:
        output = self.episode / name
        command = ["seal-availability-snapshot"]
        for agent_id in live_agent_ids:
            command.extend(("--live-agent-id", agent_id))
        for agent_id in reusable_agent_ids:
            command.extend(("--reusable-agent-id", agent_id))
        for attempt in followup_attempts:
            command.extend(("--followup-attempt", attempt))
        command.extend(("--output", str(output)))
        self.run_cli(*command)
        return output

    def test_stale_active_assignment_requires_health_probe_until_heartbeat(self) -> None:
        self.begin()
        session = json.loads(self.session.read_text(encoding="utf-8"))
        stale_at = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
        assignment = session["assignments"]["author-1"]
        assignment["updated_at"] = stale_at
        assignment.pop("last_heartbeat_at", None)
        session.pop("session_hash", None)
        session["session_hash"] = object_hash(session)
        self.session.write_text(json.dumps(session), encoding="utf-8")

        status = json.loads(
            self.run_cli("status", "--session", str(self.session)).stdout
        )
        self.assertEqual(status["health_probe_required_assignments"], ["author-1"])
        self.assertEqual(status["heartbeat_stale_seconds"], 600)
        self.assertIn(
            "author-1",
            status["health_probe_deadlines"],
        )
        self.assertIn(
            "STALE_ACTIVE_ASSIGNMENT_REQUIRES_RECONCILIATION",
            status["roster_warnings"],
        )
        self.assertFalse(status["roster_clean"])
        dirty = self.run_cli(
            "status",
            "--session",
            str(self.session),
            "--require-clean",
            check=False,
        )
        self.assertEqual(dirty.returncode, 2)

        self.run_cli(
            "record", "--session", str(self.session),
            "--event-type", "agent_heartbeat", "--agent-id", "author-1",
            "--summary", "Author is alive and continuing the assigned scene.",
        )
        status = json.loads(
            self.run_cli("status", "--session", str(self.session)).stdout
        )
        self.assertEqual(status["health_probe_required_assignments"], [])
        self.assertNotIn(
            "STALE_ACTIVE_ASSIGNMENT_REQUIRES_RECONCILIATION",
            status["roster_warnings"],
        )
        self.assertTrue(status["roster_clean"])

    def test_duplicate_heartbeat_event_is_a_strict_noop(self) -> None:
        self.begin()
        event_id = "heartbeat:author-1:fixed"
        first = json.loads(
            self.run_cli(
                "record",
                "--session",
                str(self.session),
                "--event-type",
                "agent_heartbeat",
                "--agent-id",
                "author-1",
                "--summary",
                "Author is alive and continuing the assigned scene.",
                "--event-id",
                event_id,
            ).stdout
        )
        self.assertEqual(first["event_id"], event_id)
        session_after_first = self.session.read_bytes()
        log_path = self.session.parent / "supervisor_events.jsonl"
        log_after_first = log_path.read_bytes()

        replay = json.loads(
            self.run_cli(
                "record",
                "--session",
                str(self.session),
                "--event-type",
                "agent_heartbeat",
                "--agent-id",
                "author-1",
                "--summary",
                "Author is alive and continuing the assigned scene.",
                "--event-id",
                event_id,
            ).stdout
        )
        self.assertTrue(replay["idempotent"])
        self.assertEqual(self.session.read_bytes(), session_after_first)
        self.assertEqual(log_path.read_bytes(), log_after_first)
        self.assertEqual(
            sum(
                json.loads(line)["event_id"] == event_id
                for line in log_path.read_text(encoding="utf-8").splitlines()
            ),
            1,
        )

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

    def test_roster_ceiling_is_flexible_but_initial_roster_stays_bounded(self) -> None:
        too_high = self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--max-subagents", "9",
            "--assignment", "a1|animation_author|batch-a|G001|gpt-5.6-sol",
            "--output", str(self.session), check=False,
        )
        self.assertNotEqual(too_high.returncode, 0)
        self.assertIn("must be in 1..8", too_high.stderr)

        bypass_args = [
            "begin", "--supervisor-agent-id", "root-agent",
            "--max-subagents", "8",
            "--capacity-override-reason",
            "The host has measured room, but every additive identity still needs evidence.",
        ]
        for index in range(1, 9):
            bypass_args.extend(
                (
                    "--assignment",
                    f"a{index}|animation_author|batch-{index}|G{index:03d}|gpt-5.6-sol",
                )
            )
        bypass_args.extend(("--replace", "--replace-reason"))
        bypass_args.append(
            "A nonexistent closed session must never waive additive capacity evidence."
        )
        bypass_args.extend(("--output", str(self.session)))
        replace_bypass = self.run_cli(*bypass_args, check=False)
        self.assertNotEqual(replace_bypass.returncode, 0)
        self.assertIn("existing closed supervisor session", replace_bypass.stderr)
        self.assertFalse(self.session.exists())

        four_at_t0 = self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--max-subagents", "4",
            "--capacity-override-reason",
            "The host has measured room for four producers while total cost remains bounded.",
            "--assignment", "a1|animation_author|batch-a|G001|gpt-5.6-sol",
            "--assignment", "a2|animation_author|batch-b|G002|gpt-5.6-sol",
            "--assignment", "a3|animation_author|batch-c|G003|gpt-5.6-sol",
            "--assignment", "a4|animation_author|batch-d|G004|gpt-5.6-sol",
            "--output", str(self.session), check=False,
        )
        self.assertNotEqual(four_at_t0.returncode, 0)
        self.assertIn("initial roster cannot exceed three", four_at_t0.stderr)

    def test_four_subagents_are_allowed_with_sealed_capacity_override(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--max-subagents", "4",
            "--capacity-override-reason",
            "Five runtime slots are available, the reviewer is measurably starved, and the episode cost ceiling remains safe.",
            "--assignment", "a1|animation_author|batch-a|G001-G003|gpt-5.6-sol",
            "--assignment", "a2|animation_author|batch-b|G004-G006|gpt-5.6-sol",
            "--assignment", "a3|animation_author|batch-c|G007-G009|gpt-5.6-sol",
            "--planned-task", "batch-d|animation_author|G010-G012",
            "--output", str(self.session),
        )
        evidence = self.compile_capacity_evidence()
        availability = self.compile_capacity_availability()
        authorization = json.loads(
            self.run_cli(
                "authorize-capacity", "--session", str(self.session),
                "--role", "animation_author", "--task-key", "batch-d",
                "--scope", "G010-G012", "--model", "gpt-5.6-sol",
                "--availability-snapshot", str(availability),
                "--capacity-evidence", str(evidence), "--reason",
                "The measured empty review queue justifies one bounded producer for the pending independent batch.",
            ).stdout
        )
        status = json.loads(
            self.run_cli(
                "register-capacity", "--session", str(self.session),
                "--authorization-id", authorization["authorization_id"],
                "--new-agent-id", "a4",
            ).stdout
        )
        self.assertEqual(status["roster_metrics"]["current_identity_count"], 4)
        self.assertEqual(status["roster_metrics"]["capacity_expansion_count"], 1)
        session = json.loads(self.session.read_text(encoding="utf-8"))
        self.assertEqual(session["max_subagents"], 4)
        self.assertEqual(session["roster_policy"], "reuse_before_spawn")
        for agent_id in ("a1", "a2", "a3", "a4"):
            self.run_cli(
                "set-assignment", "--session", str(self.session),
                "--agent-id", agent_id, "--state", "completed",
            )
        self.run_cli("finish", "--session", str(self.session))
        restarted = json.loads(
            self.run_cli(
                "begin", "--supervisor-agent-id", "root-agent",
                "--assignment", "a1|animation_author|batch-e|G013|gpt-5.6-sol",
                "--assignment", "a2|animation_author|batch-f|G014|gpt-5.6-sol",
                "--assignment", "a3|animation_author|batch-g|G015|gpt-5.6-sol",
                "--assignment", "a4|animation_author|batch-h|G016|gpt-5.6-sol",
                "--replace", "--replace-reason",
                "User restarted the app and resumed the complete evidence-expanded identity pool.",
                "--output", str(self.session),
            ).stdout
        )
        self.assertEqual(
            restarted["roster_metrics"]["current_identity_count"], 4
        )
        self.assertEqual(
            restarted["roster_metrics"]["historical_identity_count"], 4
        )

    def test_capacity_expansion_rejects_a_compatible_reusable_identity(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--max-subagents", "3",
            "--assignment", "a1|animation_author|batch-a|G001-G003|gpt-5.6-sol",
            "--assignment", "a2|animation_author|batch-b|G004-G006|gpt-5.6-sol",
            "--planned-task", "batch-c|animation_author|G007-G009",
            "--output", str(self.session),
        )
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "a2", "--state", "completed",
        )
        evidence = self.compile_capacity_evidence()
        availability = self.compile_capacity_availability()
        result = self.run_cli(
            "authorize-capacity", "--session", str(self.session),
            "--role", "animation_author", "--task-key", "batch-c",
            "--scope", "G007-G009", "--model", "gpt-5.6-sol",
            "--availability-snapshot", str(availability),
            "--capacity-evidence", str(evidence), "--reason",
            "The measured empty review queue would otherwise justify the pending independent batch.",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("compatible roster member is reusable", result.stderr)

    def test_capacity_reuse_check_normalizes_requested_model(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--max-subagents", "2",
            "--assignment", "a1|animation_author|batch-a|G001-G003|gpt-5.6-sol",
            "--planned-task", "batch-b|animation_author|G004-G006",
            "--output", str(self.session),
        )
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "a1", "--state", "completed",
        )
        evidence = self.compile_capacity_evidence()
        availability = self.compile_capacity_availability()
        rejected = self.run_cli(
            "authorize-capacity", "--session", str(self.session),
            "--role", "animation_author", "--task-key", "batch-b",
            "--scope", "G004-G006", "--model", " gpt-5.6-sol ",
            "--availability-snapshot", str(availability),
            "--capacity-evidence", str(evidence), "--reason",
            "The pending batch would otherwise use one measured additive producer slot.",
            check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("compatible roster member is reusable", rejected.stderr)

    def test_capacity_rejects_restored_compatible_retired_identity(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--max-subagents", "2",
            "--assignment", "old-author|animation_author|batch-a|G001-G003|gpt-5.6-luna",
            "--planned-task", "batch-b|animation_author|G004-G006",
            "--output", str(self.session),
        )
        replacement = json.loads(
            self.run_cli(
                "authorize-replacement", "--session", str(self.session),
                "--old-agent-id", "old-author",
                "--reason", "model_change_required",
                "--new-model", "gpt-5.6-sol",
                "--evidence",
                "Human authorized a bounded Sol takeover after the Luna quality experiment.",
            ).stdout
        )
        self.run_cli(
            "register-replacement", "--session", str(self.session),
            "--authorization-id", replacement["authorization_id"],
            "--new-agent-id", "new-sol-author",
        )
        evidence = self.compile_capacity_evidence()
        availability = self.compile_capacity_availability(
            live_agent_ids=("old-author",),
            reusable_agent_ids=("old-author",),
            followup_attempts=(
                "old-author|restored|Direct followup_task restored the original Luna identity and preserved context.",
            ),
            name="restored-capacity-availability.json",
        )
        rejected = self.run_cli(
            "authorize-capacity", "--session", str(self.session),
            "--role", "animation_author", "--task-key", "batch-b",
            "--scope", "G004-G006", "--model", "gpt-5.6-luna",
            "--availability-snapshot", str(availability),
            "--capacity-evidence", str(evidence), "--reason",
            "The pending batch would otherwise use one measured additive producer slot.",
            check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("restore-original-identity", rejected.stderr)

    def test_capacity_wait_excludes_human_pause_intervals(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--max-subagents", "2",
            "--assignment", "a1|animation_author|batch-a|G001-G003|gpt-5.6-sol",
            "--planned-task", "batch-b|animation_author|G004-G006",
            "--output", str(self.session),
        )
        evidence = self.compile_capacity_evidence(
            reviewer_wait_minutes=50.0,
            paused_minutes=47.0,
        )
        availability = self.compile_capacity_availability()
        rejected = self.run_cli(
            "authorize-capacity", "--session", str(self.session),
            "--role", "animation_author", "--task-key", "batch-b",
            "--scope", "G004-G006", "--model", "gpt-5.6-sol",
            "--availability-snapshot", str(availability),
            "--capacity-evidence", str(evidence), "--reason",
            "The wall clock looks idle, but most of that interval was an authorized human pause.",
            check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("five measured reviewer-wait minutes", rejected.stderr)

    def test_capacity_expansion_rejects_compiled_nonempty_candidate_queue(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--max-subagents", "2",
            "--assignment", "a1|animation_author|batch-a|G001-G003|gpt-5.6-sol",
            "--planned-task", "batch-b|animation_author|G004-G006",
            "--output", str(self.session),
        )
        evidence = self.compile_capacity_evidence(candidate_queue_depth=1)
        availability = self.compile_capacity_availability()
        rejected = self.run_cli(
            "authorize-capacity", "--session", str(self.session),
            "--role", "animation_author", "--task-key", "batch-b",
            "--scope", "G004-G006", "--model", "gpt-5.6-sol",
            "--availability-snapshot", str(availability),
            "--capacity-evidence", str(evidence), "--reason",
            "One independent batch remains pending while the production ceiling has room.",
            check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("candidate already waits for review", rejected.stderr)

    def test_capacity_registration_revalidates_compiled_source_bytes(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--max-subagents", "2",
            "--assignment", "a1|animation_author|batch-a|G001-G003|gpt-5.6-sol",
            "--planned-task", "batch-b|animation_author|G004-G006",
            "--output", str(self.session),
        )
        evidence = self.compile_capacity_evidence()
        availability = self.compile_capacity_availability()
        authorization = json.loads(
            self.run_cli(
                "authorize-capacity", "--session", str(self.session),
                "--role", "animation_author", "--task-key", "batch-b",
                "--scope", "G004-G006", "--model", "gpt-5.6-sol",
                "--availability-snapshot", str(availability),
                "--capacity-evidence", str(evidence), "--reason",
                "One independent batch remains pending while the measured review queue is empty.",
            ).stdout
        )
        receipt = json.loads(evidence.read_text(encoding="utf-8"))
        clock_path = Path(receipt["sources"]["delivery_clock"]["path"])
        clock = json.loads(clock_path.read_text(encoding="utf-8"))
        clock["source_changed_after_authorization"] = True
        clock.pop("clock_hash", None)
        clock["clock_hash"] = object_hash(clock)
        clock_path.write_text(json.dumps(clock), encoding="utf-8")
        rejected = self.run_cli(
            "register-capacity", "--session", str(self.session),
            "--authorization-id", authorization["authorization_id"],
            "--new-agent-id", "a2", check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("is stale", rejected.stderr)

    def test_capacity_evidence_rejects_incomplete_token_telemetry(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--max-subagents", "2",
            "--assignment", "a1|animation_author|batch-a|G001-G003|gpt-5.6-sol",
            "--planned-task", "batch-b|animation_author|G004-G006",
            "--output", str(self.session),
        )
        evidence = self.compile_capacity_evidence()
        receipt = json.loads(evidence.read_text(encoding="utf-8"))
        phase_log = Path(receipt["sources"]["phase_log"]["path"])
        event = json.loads(phase_log.read_text(encoding="utf-8"))
        event["token_observed"] = False
        phase_log.write_text(json.dumps(event) + "\n", encoding="utf-8")
        rejected = self.run_cli(
            "seal-capacity-evidence",
            "--repo-root", str(self.root),
            "--session", str(self.session),
            "--delivery-clock", receipt["sources"]["delivery_clock"]["path"],
            "--efficiency-contract", receipt["sources"]["efficiency_contract"]["path"],
            "--output", str(self.root / "incomplete-capacity-evidence.json"),
            check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("complete cumulative token telemetry", rejected.stderr)

    def test_capacity_evidence_requires_exact_episode_clock_lineage(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--max-subagents", "2",
            "--assignment", "a1|animation_author|batch-a|G001-G003|gpt-5.6-sol",
            "--planned-task", "batch-b|animation_author|G004-G006",
            "--output", str(self.session),
        )
        evidence = self.compile_capacity_evidence()
        receipt = json.loads(evidence.read_text(encoding="utf-8"))
        clock_path = Path(receipt["sources"]["delivery_clock"]["path"])
        contract_path = Path(receipt["sources"]["efficiency_contract"]["path"])

        other_episode = self.root / "other-episode"
        other_episode.mkdir()
        clock = json.loads(clock_path.read_text(encoding="utf-8"))
        clock["episode"] = "other-episode"
        clock.pop("clock_hash", None)
        clock["clock_hash"] = object_hash(clock)
        clock_path.write_text(json.dumps(clock), encoding="utf-8")
        mismatched = self.run_cli(
            "seal-capacity-evidence", "--repo-root", str(self.root),
            "--session", str(self.session),
            "--delivery-clock", str(clock_path),
            "--efficiency-contract", str(contract_path),
            "--output", str(self.root / "mismatched-capacity.json"),
            check=False,
        )
        self.assertNotEqual(mismatched.returncode, 0)
        self.assertIn("belong to different episodes", mismatched.stderr)

        evidence = self.compile_capacity_evidence()
        receipt = json.loads(evidence.read_text(encoding="utf-8"))
        contract_path = Path(receipt["sources"]["efficiency_contract"]["path"])
        ledger_path = Path(receipt["sources"]["reservation_ledger"]["path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract.pop("delivery_clock_binding")
        contract.pop("contract_hash", None)
        contract["contract_hash"] = object_hash(contract)
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger["efficiency_contract_hash"] = contract["contract_hash"]
        ledger.pop("ledger_hash", None)
        ledger["ledger_hash"] = object_hash(ledger)
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
        unbound = self.run_cli(
            "seal-capacity-evidence", "--repo-root", str(self.root),
            "--session", str(self.session),
            "--delivery-clock", receipt["sources"]["delivery_clock"]["path"],
            "--efficiency-contract", str(contract_path),
            "--output", str(self.root / "unbound-capacity.json"),
            check=False,
        )
        self.assertNotEqual(unbound.returncode, 0)
        self.assertIn("lacks exact delivery-clock lineage", unbound.stderr)

    def test_capacity_evidence_rejects_forged_initial_clock_hash(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--max-subagents", "2",
            "--assignment", "a1|animation_author|batch-a|G001-G003|gpt-5.6-sol",
            "--planned-task", "batch-b|animation_author|G004-G006",
            "--output", str(self.session),
        )
        evidence = self.compile_capacity_evidence()
        receipt = json.loads(evidence.read_text(encoding="utf-8"))
        contract_path = Path(receipt["sources"]["efficiency_contract"]["path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["delivery_clock_binding"]["initial_clock_hash"] = "f" * 64
        contract.pop("contract_hash", None)
        contract["contract_hash"] = object_hash(contract)
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        rejected = self.run_cli(
            "seal-capacity-evidence", "--repo-root", str(self.root),
            "--session", str(self.session),
            "--delivery-clock", receipt["sources"]["delivery_clock"]["path"],
            "--efficiency-contract", str(contract_path),
            "--output", str(self.root / "forged-lineage-capacity.json"),
            check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("lacks exact delivery-clock lineage", rejected.stderr)

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

    def test_closed_session_restart_cannot_reset_identity_history(self) -> None:
        self.begin()
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "author-1", "--state", "completed",
        )
        self.run_cli("finish", "--session", str(self.session))
        rejected = self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--assignment", "author-2|animation_author|batch-b|G004-G006|gpt-5.6-sol",
            "--replace", "--replace-reason",
            "User reopened production after final review and requested one bounded follow-up scene.",
            "--output", str(self.session), check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("must reuse preserved identities", rejected.stderr)
        status = json.loads(
            self.run_cli(
                "begin", "--supervisor-agent-id", "root-agent",
                "--assignment", "author-1|animation_author|batch-b|G004-G006|gpt-5.6-sol",
                "--replace", "--replace-reason",
                "User reopened production after final review and requested one bounded follow-up scene.",
                "--output", str(self.session),
            ).stdout
        )
        self.assertEqual(status["roster_metrics"]["historical_identity_count"], 1)

    def test_closed_session_restart_must_restore_complete_current_identity_pool(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--assignment", "a1|animation_author|batch-a|G001-G003|gpt-5.6-sol",
            "--assignment", "a2|animation_author|batch-b|G004-G006|gpt-5.6-sol",
            "--output", str(self.session),
        )
        for agent_id in ("a1", "a2"):
            self.run_cli(
                "set-assignment", "--session", str(self.session),
                "--agent-id", agent_id, "--state", "completed",
            )
        self.run_cli("finish", "--session", str(self.session))
        rejected = self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--assignment", "a1|animation_author|batch-c|G007-G009|gpt-5.6-sol",
            "--replace", "--replace-reason",
            "User reopened production after final review and requested one bounded follow-up batch.",
            "--output", str(self.session), check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("restore the complete current identity pool", rejected.stderr)

    def test_cancelled_task_does_not_cancel_identity_reuse(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--assignment", "a1|animation_author|batch-a|G001-G003|gpt-5.6-sol",
            "--assignment", "a2|animation_author|batch-b|G004-G006|gpt-5.6-sol",
            "--output", str(self.session),
        )
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "a1", "--state", "completed",
        )
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "a2", "--state", "cancelled",
        )
        self.run_cli("finish", "--session", str(self.session))
        rejected = self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--assignment", "a1|animation_author|batch-c|G007-G009|gpt-5.6-sol",
            "--replace", "--replace-reason",
            "User reopened production after final review and requested one bounded follow-up batch.",
            "--output", str(self.session), check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("restore the complete current identity pool", rejected.stderr)

    def test_public_assignment_transition_cannot_retire_or_hide_active_task(self) -> None:
        self.begin()
        retired = self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "author-1", "--state", "retired",
            check=False,
        )
        self.assertNotEqual(retired.returncode, 0)
        self.assertIn("invalid choice", retired.stderr)

        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "author-1", "--state", "completed",
        )
        for state in ("active", "blocked"):
            reopened = self.run_cli(
                "set-assignment", "--session", str(self.session),
                "--agent-id", "author-1", "--state", state,
                check=False,
            )
            self.assertNotEqual(reopened.returncode, 0)
            self.assertIn("use assign-task", reopened.stderr)

        session = json.loads(self.session.read_text(encoding="utf-8"))
        session["task_queue"]["batch-a"]["state"] = "active"
        session.pop("session_hash", None)
        session["session_hash"] = object_hash(session)
        self.session.write_text(json.dumps(session), encoding="utf-8")
        blocked = self.run_cli(
            "finish", "--session", str(self.session), check=False
        )
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("task rows remain active", blocked.stderr)

    def test_closed_session_restart_cannot_change_reused_role_or_model(self) -> None:
        self.begin()
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "author-1", "--state", "completed",
        )
        self.run_cli("finish", "--session", str(self.session))
        for assignment in (
            "author-1|independent_reviewer|batch-b|G004-G006|gpt-5.6-sol",
            "author-1|animation_author|batch-b|G004-G006|gpt-5.6-luna",
        ):
            rejected = self.run_cli(
                "begin", "--supervisor-agent-id", "root-agent",
                "--assignment", assignment,
                "--replace", "--replace-reason",
                "User reopened production after final review and requested one bounded follow-up scene.",
                "--output", str(self.session), check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("preserve each reused identity's role and model", rejected.stderr)

    def test_capacity_expansion_requires_untampered_compiled_evidence(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--max-subagents", "2",
            "--assignment", "a1|animation_author|batch-a|G001-G003|gpt-5.6-sol",
            "--planned-task", "batch-b|animation_author|G004-G006",
            "--output", str(self.session),
        )
        evidence = self.compile_capacity_evidence()
        availability = self.compile_capacity_availability()
        original = json.loads(evidence.read_text(encoding="utf-8"))
        for section, field, value in (
            ("delivery", "reviewer_wait_minutes", "nan"),
            ("delivery", "reviewer_wait_minutes", "inf"),
            ("cost", "cost_headroom_fraction", "nan"),
            ("cost", "cost_headroom_fraction", "inf"),
        ):
            forged = json.loads(json.dumps(original))
            forged[section][field] = value
            forged.pop("receipt_hash", None)
            forged["receipt_hash"] = object_hash(forged)
            forged_path = self.root / f"forged-{section}-{str(value)}.json"
            forged_path.write_text(json.dumps(forged), encoding="utf-8")
            rejected = self.run_cli(
                "authorize-capacity", "--session", str(self.session),
                "--role", "animation_author", "--task-key", "batch-b",
                "--scope", "G004-G006", "--model", "gpt-5.6-sol",
                "--availability-snapshot", str(availability),
                "--capacity-evidence", str(forged_path), "--reason",
                "The measured empty review queue would otherwise justify the pending independent batch.",
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)

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
            "--assignment", "author-2|animation_author|batch-b|G004-G006|gpt-5.7-sol",
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

    def test_model_change_can_replace_when_no_reusable_identity_has_requested_model(self) -> None:
        self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--assignment", "author-1|animation_author|batch-a|G001-G003|gpt-5.6-luna",
            "--assignment", "author-2|animation_author|batch-b|G004-G006|gpt-5.6-luna",
            "--output", str(self.session),
        )
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "author-2", "--state", "completed",
        )
        authorization = json.loads(
            self.run_cli(
                "authorize-replacement", "--session", str(self.session),
                "--old-agent-id", "author-1",
                "--reason", "model_change_required",
                "--new-model", "gpt-5.6-sol",
                "--evidence",
                "Human authorized a Sol author takeover after the Luna visual-language failure.",
            ).stdout
        )
        self.assertEqual(authorization["new_model"], "gpt-5.6-sol")

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

    def test_closed_session_restart_cannot_directly_revive_retired_identity(self) -> None:
        self.begin()
        unavailable_path = self.root / "unavailable-retired.json"
        self.run_cli(
            "seal-availability-snapshot",
            "--followup-attempt",
            "author-1|target_not_found|Direct followup_task reported that the original target was not found.",
            "--output", str(unavailable_path),
        )
        authorization = json.loads(
            self.run_cli(
                "authorize-replacement", "--session", str(self.session),
                "--old-agent-id", "author-1", "--reason", "agent_unavailable",
                "--availability-snapshot", str(unavailable_path),
                "--evidence",
                "A sealed direct followup probe reported the original identity unavailable.",
            ).stdout
        )
        self.run_cli(
            "register-replacement", "--session", str(self.session),
            "--authorization-id", authorization["authorization_id"],
            "--new-agent-id", "author-2",
        )
        self.run_cli(
            "set-assignment", "--session", str(self.session),
            "--agent-id", "author-2", "--state", "completed",
        )
        self.run_cli("finish", "--session", str(self.session))
        rejected = self.run_cli(
            "begin", "--supervisor-agent-id", "root-agent",
            "--assignment", "author-1|animation_author|batch-b|G004-G006|gpt-5.6-sol",
            "--assignment", "author-2|animation_author|batch-c|G007-G009|gpt-5.6-sol",
            "--replace", "--replace-reason",
            "User reopened production after final review and requested one bounded follow-up scene.",
            "--output", str(self.session), check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("cannot directly revive retired identity", rejected.stderr)

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
