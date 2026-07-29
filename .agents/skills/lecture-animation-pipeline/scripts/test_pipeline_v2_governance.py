#!/usr/bin/env python3
"""Hard-gate tests for reviewer roles, blockers, and repair binding."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from pipeline_v2_lib import engine as pipeline
from pipeline_v2_lib.core import object_hash
from pipeline_v2_lib.governance import (
    review_session_governance,
    unresolved_policy_blockers,
    validate_pass_policy,
    validate_pending_repair_binding,
    validate_session_governance,
)


class GovernanceTests(unittest.TestCase):
    def test_parallel_batch_rejects_stale_local_supervisor_copy(self) -> None:
        with self.assertRaisesRegex(
            pipeline.PipelineError, "local supervisor session is stale"
        ):
            pipeline.require_matching_canonical_supervisor_session(
                {"session_hash": "old"},
                {"session_hash": "canonical"},
            )
        pipeline.require_matching_canonical_supervisor_session(
            {"session_hash": "same"},
            {"session_hash": "same"},
        )

    def test_parallel_acceptance_is_reserved_for_main_agent(self) -> None:
        spine = {
            "schema": "lecture-animation-episode-visual-spine-v2",
            "production_mode": "parallel_batches",
            "main_agent_governance": {"owner": "/root"},
        }
        spine["spine_hash"] = object_hash(spine)
        facts, errors = review_session_governance(
            spine,
            reviewer_agent_id="/root/worker-reviewer",
            author_agent_id="/root/worker-author",
            review_role="acceptance",
        )
        self.assertTrue(any("main agent" in error for error in errors))
        facts, errors = review_session_governance(
            spine,
            reviewer_agent_id="/root",
            author_agent_id="/root/worker-author",
            review_role="acceptance",
        )
        self.assertEqual(errors, [])
        self.assertEqual(facts["main_agent_id"], "/root")
        facts, errors = review_session_governance(
            spine,
            reviewer_agent_id="/root/fresh-verifier",
            author_agent_id="/root",
            review_role="recusal_acceptance",
        )
        self.assertEqual(errors, [])
        self.assertEqual(facts["review_role"], "recusal_acceptance")
        _, errors = review_session_governance(
            spine,
            reviewer_agent_id="/root/fresh-verifier",
            author_agent_id="/root/worker-author",
            review_role="recusal_acceptance",
        )
        self.assertTrue(any("main agent" in error for error in errors))

    def test_diagnostic_support_cannot_grant_final_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spine_path = root / "spine.json"
            spine = {
                "schema": "lecture-animation-episode-visual-spine-v2",
                "production_mode": "parallel_batches",
                "main_agent_governance": {"owner": "/root"},
            }
            spine["spine_hash"] = object_hash(spine)
            spine_path.write_text(json.dumps(spine), encoding="utf-8")
            session = {
                "author_agent_id": "/root/worker-author",
                "reviewer_agent_id": "/root/worker-reviewer",
                "production_mode": "parallel_batches",
                "main_agent_id": "/root",
                "review_role": "diagnostic_support",
                "episode_spine_hash": spine["spine_hash"],
            }
            manifest = {"artifacts": {"episode_spine": {"path": str(spine_path)}}}
            errors = validate_session_governance(
                session, manifest, root, "pass_for_user_review_pending"
            )
            self.assertTrue(any("cannot grant" in error for error in errors))

    def test_open_major_live_policy_issue_blocks_handoff(self) -> None:
        policy = {
            "entries": [
                {
                    "issue_id": "human-layout-1",
                    "severity": "major",
                    "status": "open_regression_check_required",
                },
                {"issue_id": "minor-note", "severity": "minor", "status": "open"},
                {"issue_id": "fixed-major", "severity": "major", "status": "resolved_pending_user_review"},
            ]
        }
        blockers = unresolved_policy_blockers(policy)
        self.assertEqual([item["issue_id"] for item in blockers], ["human-layout-1"])
        self.assertTrue(any("human-layout-1" in error for error in validate_pass_policy(policy)))

    def test_pending_revise_requires_exact_formal_repair_binding(self) -> None:
        session = {
            "pending_repairs": {
                "g001": {"review_hash": "review-hash", "findings_count": 2}
            }
        }
        errors = validate_pending_repair_binding(
            session,
            "g001",
            {"repair_context": {}},
            "pass_for_user_review_pending",
        )
        self.assertGreaterEqual(len(errors), 4)
        errors = validate_pending_repair_binding(
            session,
            "g001",
            {
                "repair_context": {
                    "previous_review_hash": "review-hash",
                    "repair_contract_hash": "c" * 64,
                    "repair_response_hash": "r" * 64,
                    "repair_gate_hash": "g" * 64,
                }
            },
            "pass_for_user_review_pending",
        )
        self.assertEqual(errors, [])

    def test_repair_phase_cannot_start_as_an_untracked_generic_timer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0001-test"
            episode.mkdir(parents=True)
            contract_path = (
                episode
                / "review"
                / "evolution"
                / "episode_efficiency_contract.json"
            )
            contract = {
                "schema": "lecture-animation-episode-efficiency-contract-v3",
                "created_at": "2026-07-28T00:00:00+00:00",
                "episode": "videos/0001-test",
                "canonical_repo_root": str(root.resolve()),
                "central_phase_log": (
                    "videos/0001-test/review/evolution/"
                    "episode_phase_events.jsonl"
                ),
                "central_reservation_ledger": (
                    "videos/0001-test/review/evolution/"
                    "episode_token_reservations.json"
                ),
                "budget": pipeline.default_efficiency_budget(),
                "quality_target": (
                    pipeline.default_efficiency_quality_target()
                ),
                "status": "active",
            }
            contract["contract_hash"] = object_hash(contract)
            contract_path.parent.mkdir(parents=True)
            contract_path.write_text(
                json.dumps(contract),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(Exception, "previous-review"):
                pipeline.command_phase_start(
                    SimpleNamespace(
                        repo_root=str(root),
                        episode=str(episode),
                        efficiency_contract=str(contract_path),
                        run_id="run-1",
                        scene_slug="g001",
                        phase="repair",
                        actor_model="author-model",
                        active_seconds_allocation=3_600,
                        raw_token_allocation=1_000,
                        uncached_input_token_allocation=500,
                        output_token_allocation=250,
                        reasoning_token_allocation=100,
                        actor_role="author",
                        reasoning_effort="high",
                        phase_instance_id=None,
                        prompt_bytes=0,
                        artifact_input_bytes=0,
                        files_read=0,
                        usage_file=None,
                        previous_review=None,
                        repair_contract=None,
                        state=str(root / "repair-state.json"),
                    )
                )


if __name__ == "__main__":
    unittest.main()
