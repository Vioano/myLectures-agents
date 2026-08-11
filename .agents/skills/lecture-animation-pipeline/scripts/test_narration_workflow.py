#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from pipeline_v2_lib.core import PipelineError, object_hash
from pipeline_v2_lib.narration_workflow import (
    command_freeze_narration_script,
    command_init_narration_workflow,
    command_lock_narration_tts_input,
    command_narration_workflow_status,
    command_open_post_animation_narration_repair,
    command_open_narration_drafting,
    command_rebind_narration_profile,
    command_record_narration_independent_review,
    command_record_narration_outline_review,
    command_record_narration_user_outcome,
    command_seal_narration_author_self_review,
    command_seal_narration_animation_release,
    validate_narration_workflow_for_phase,
)


class NarrationWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "review/narration_workflow.json"
        self.attempts = self.root / "review/narration_review_attempts.jsonl"
        self.profile = self._write_json(
            "profile.json",
            {
                "schema": "lecture-animation-audience-profile-v1",
                "profile_id": "mass_access_r01",
                "scope": {"binding_mode": "explicit_only", "global_default": False},
                "learner_snapshot": {"working_memory": "current cue plus previous cue"},
                "narration_policy": {"ambiguity": "fail closed"},
                "review_questions": ["Can the current object be recovered locally?"],
            },
        )
        self.contract = self._write_json("contract.json", {"schema": "writing-contract-v1"})
        self.outline = self._write_text("outline.md", "# outline\n")
        self.script_md = self._write_text("script.md", "# script\nA clear sentence.\n")
        self.script_json = self._write_json(
            "script.json",
            {
                "schema": "structured-script-v1",
                "source_script": {"path": "script.md", "sha256": self._sha(self.script_md)},
            },
        )
        self.static = self._write_json(
            "static.json",
            {"valid": True, "issue_count": 0, "rewrite_sha256": self._sha(self.script_json)},
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_text(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def _write_json(self, relative: str, value: dict) -> Path:
        return self._write_text(relative, json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def _run(self, command, **kwargs):
        defaults = {"repo_root": str(self.root), "state": str(self.state)}
        defaults.update(kwargs)
        with contextlib.redirect_stdout(io.StringIO()):
            return command(SimpleNamespace(**defaults))

    def _state(self) -> dict:
        return json.loads(self.state.read_text(encoding="utf-8"))

    def _init(self) -> dict:
        self._run(
            command_init_narration_workflow,
            workflow_id="episode-x-narration-r01",
            episode="episode-x",
            profile=str(self.profile),
            writing_contract=str(self.contract),
            outline=str(self.outline),
            author_id="author-a",
            reviewer_id="reviewer-b",
            coordinator_id="root",
            replace=False,
            reason=None,
        )
        return self._state()

    def _outline_pass(self) -> dict:
        state = self._state()
        review = self._write_json(
            "outline_review.json",
            {
                "verdict": "pass",
                "workflow_binding": {
                    "profile_sha256": state["profile"]["sha256"],
                    "outline_sha256": state["outline"]["sha256"],
                },
            },
        )
        self._run(
            command_record_narration_outline_review,
            expected_state_hash=state["state_hash"],
            actor_id="reviewer-b",
            review=str(review),
        )
        return self._state()

    def _freeze(self) -> dict:
        state = self._state()
        self._run(
            command_freeze_narration_script,
            expected_state_hash=state["state_hash"],
            actor_id="author-a",
            script_markdown=str(self.script_md),
            script_json=str(self.script_json),
            static_audit=str(self.static),
            candidate_label="r01",
        )
        return self._state()

    def _self_review(self) -> dict:
        state = self._state()
        review = self._write_json(
            "self_review.json",
            {
                "schema": "lecture-animation-narration-author-self-review-v1",
                "author_id": "author-a",
                "candidate_hash": state["current_candidate"]["candidate_hash"],
                "verdict": "pass",
                "checks": ["profile bound", "anchors complete", "all cues reread"],
            },
        )
        self._run(
            command_seal_narration_author_self_review,
            expected_state_hash=state["state_hash"],
            actor_id="author-a",
            review=str(review),
        )
        return self._state()

    def _independent(self, verdict: str) -> dict:
        state = self._state()
        report = self._write_json(
            f"independent_{verdict}.json",
            {
                "verdict": verdict,
                "workflow_binding": {
                    "workflow_id": state["workflow_id"],
                    "candidate_hash": state["current_candidate"]["candidate_hash"],
                    "profile_sha256": state["profile"]["sha256"],
                    "writing_contract_sha256": state["writing_contract"]["sha256"],
                },
            },
        )
        self._run(
            command_record_narration_independent_review,
            expected_state_hash=state["state_hash"],
            actor_id="reviewer-b",
            attempt_log=str(self.attempts),
            report=str(report),
            import_existing_candidate=False,
            script_markdown=None,
            script_json=None,
            static_audit=None,
            candidate_label=None,
        )
        return self._state()

    def _approved_and_tts_locked(self) -> dict:
        self._init()
        self._outline_pass()
        state = self._state()
        self._run(
            command_open_narration_drafting,
            expected_state_hash=state["state_hash"],
            actor_id="author-a",
            reason="start",
        )
        self._freeze()
        self._self_review()
        state = self._independent("pass_for_user_script_review_only")
        outcome = self._write_json(
            "outcome.json",
            {
                "schema": "lecture-animation-narration-user-outcome-v1",
                "human_text": "通过",
                "candidate_hash": state["current_candidate"]["candidate_hash"],
                "verdict": "pass",
            },
        )
        self._run(
            command_record_narration_user_outcome,
            expected_state_hash=state["state_hash"],
            actor_id="root",
            outcome=str(outcome),
        )
        state = self._state()
        preflight = self._write_json(
            "preflight.json",
            {"valid": True, "candidate_hash": state["current_candidate"]["candidate_hash"]},
        )
        self._run(
            command_lock_narration_tts_input,
            expected_state_hash=state["state_hash"],
            actor_id="root",
            preflight=str(preflight),
        )
        return self._state()

    def _animation_release(self) -> dict:
        state = self._state()
        readiness = self._write_json("readiness.json", {"status": "pass"})
        inventory = self._write_json("scene_production_inventory.json", {"status": "pass"})
        release = self._write_json(
            "animation_release.json",
            {
                "schema": "lecture-animation-narration-animation-release-v1",
                "workflow_id": state["workflow_id"],
                "candidate_hash": state["current_candidate"]["candidate_hash"],
                "verdict": "animation_authorized",
                "human_audio_gate": "passed",
                "post_tts_readiness": {"path": str(readiness), "sha256": self._sha(readiness)},
                "scene_production_inventory": {"path": str(inventory), "sha256": self._sha(inventory)},
                **(
                    {"repair_context_hash": state["post_animation_repair"]["repair_context_hash"]}
                    if state.get("post_animation_repair")
                    else {}
                ),
            },
        )
        self._run(
            command_seal_narration_animation_release,
            expected_state_hash=state["state_hash"],
            actor_id="root",
            release=str(release),
        )
        return self._state()

    def test_rejects_same_author_and_reviewer(self) -> None:
        with self.assertRaisesRegex(PipelineError, "must be different"):
            self._run(
                command_init_narration_workflow,
                workflow_id="x",
                episode="x",
                profile=str(self.profile),
                writing_contract=str(self.contract),
                outline=str(self.outline),
                author_id="same",
                reviewer_id="same",
                coordinator_id="root",
                replace=False,
                reason=None,
            )

    def test_normal_pass_flow_requires_exact_user_outcome_before_tts(self) -> None:
        self._init()
        self._outline_pass()
        state = self._state()
        self._run(
            command_open_narration_drafting,
            expected_state_hash=state["state_hash"],
            actor_id="author-a",
            reason="outline passed",
        )
        self._freeze()
        self._self_review()
        state = self._independent("pass_for_user_script_review_only")
        self.assertEqual(state["status"], "user_review_pending")

        preflight = self._write_json("preflight.json", {"valid": True, "candidate_hash": state["current_candidate"]["candidate_hash"]})
        with self.assertRaisesRegex(PipelineError, "before exact user script approval"):
            self._run(
                command_lock_narration_tts_input,
                expected_state_hash=state["state_hash"],
                actor_id="root",
                preflight=str(preflight),
            )

        bad_outcome = self._write_json(
            "bad_outcome.json",
            {"schema": "lecture-animation-narration-user-outcome-v1", "human_text": "通过", "candidate_hash": "wrong", "verdict": "pass"},
        )
        with self.assertRaisesRegex(PipelineError, "exact candidate"):
            self._run(
                command_record_narration_user_outcome,
                expected_state_hash=state["state_hash"],
                actor_id="root",
                outcome=str(bad_outcome),
            )

        outcome = self._write_json(
            "outcome.json",
            {"schema": "lecture-animation-narration-user-outcome-v1", "human_text": "通过", "candidate_hash": state["current_candidate"]["candidate_hash"], "verdict": "pass"},
        )
        self._run(
            command_record_narration_user_outcome,
            expected_state_hash=state["state_hash"],
            actor_id="root",
            outcome=str(outcome),
        )
        state = self._state()
        self.assertEqual(state["status"], "user_script_approved")
        self._run(
            command_lock_narration_tts_input,
            expected_state_hash=state["state_hash"],
            actor_id="root",
            preflight=str(preflight),
        )
        self.assertEqual(self._state()["status"], "tts_input_locked")

    def test_revise_preserves_attempt_and_reopens_only_for_author(self) -> None:
        self._init()
        self._outline_pass()
        state = self._state()
        self._run(command_open_narration_drafting, expected_state_hash=state["state_hash"], actor_id="author-a", reason="start")
        self._freeze()
        self._self_review()
        state = self._independent("revise")
        self.assertEqual(state["status"], "revision_required")
        self.assertEqual(len(self.attempts.read_text(encoding="utf-8").splitlines()), 1)
        with self.assertRaisesRegex(PipelineError, "bound narration author"):
            self._run(command_open_narration_drafting, expected_state_hash=state["state_hash"], actor_id="reviewer-b", reason="wrong role")
        self._run(command_open_narration_drafting, expected_state_hash=state["state_hash"], actor_id="author-a", reason="fix report")
        self.assertEqual(self._state()["status"], "drafting")

    def test_profile_hot_rebind_invalidates_downstream_and_preserves_history(self) -> None:
        self._init()
        self._outline_pass()
        state = self._state()
        self._run(command_open_narration_drafting, expected_state_hash=state["state_hash"], actor_id="author-a", reason="start")
        self._freeze()
        old = self._state()
        revised_profile_data = json.loads(self.profile.read_text(encoding="utf-8"))
        revised_profile_data["profile_id"] = "mass_access_r02"
        revised_profile = self._write_json("profile_r02.json", revised_profile_data)
        self._run(
            command_rebind_narration_profile,
            expected_state_hash=old["state_hash"],
            actor_id="root",
            profile=str(revised_profile),
            writing_contract=str(self.contract),
            outline=str(self.outline),
            reason="working-memory contract tightened",
        )
        state = self._state()
        self.assertEqual(state["status"], "profile_outline_locked")
        self.assertIsNone(state["current_candidate"])
        self.assertEqual(len(state["superseded_bindings"]), 1)
        self.assertGreater(len(state["history"]), len(old["history"]))

    def test_imports_legacy_review_as_revision_required(self) -> None:
        state = self._init()
        report = self._write_json(
            "legacy_review.json",
            {
                "verdict": "REVISE",
                "inputs": {
                    "rewrite_markdown": {"sha256": self._sha(self.script_md)},
                    "rewrite_json": {"sha256": self._sha(self.script_json)},
                    "repair_contract": {"sha256": self._sha(self.contract)},
                    "static_audit": {"sha256": self._sha(self.static)},
                },
            },
        )
        self._run(
            command_record_narration_independent_review,
            expected_state_hash=state["state_hash"],
            actor_id="reviewer-b",
            attempt_log=str(self.attempts),
            report=str(report),
            import_existing_candidate=True,
            script_markdown=str(self.script_md),
            script_json=str(self.script_json),
            static_audit=str(self.static),
            candidate_label="legacy-r11",
        )
        state = self._state()
        self.assertEqual(state["status"], "revision_required")
        self.assertEqual(state["author_self_review"]["migration"], "pre_state_machine_candidate")
        self.assertTrue(json.loads(self.attempts.read_text(encoding="utf-8"))["imported_legacy_evidence"])
        self._run(command_narration_workflow_status, require_state="revision_required")

    def test_animation_requires_post_tts_release(self) -> None:
        state = self._approved_and_tts_locked()
        with self.assertRaisesRegex(PipelineError, "must be animation_authorized"):
            validate_narration_workflow_for_phase(
                self.state,
                repo_root=self.root,
                phase="authoring",
            )
        state = self._animation_release()
        self.assertEqual(state["status"], "animation_authorized")
        validated = validate_narration_workflow_for_phase(
            self.state,
            repo_root=self.root,
            phase="render",
        )
        self.assertEqual(validated["state_hash"], state["state_hash"])
        self._write_json("readiness.json", {"status": "changed"})
        with self.assertRaisesRegex(PipelineError, "post_tts_readiness sha256"):
            validate_narration_workflow_for_phase(
                self.state,
                repo_root=self.root,
                phase="render",
            )

    def test_post_animation_performance_repair_preserves_script_but_invalidates_downstream(self) -> None:
        self._approved_and_tts_locked()
        state = self._animation_release()
        baseline = self._write_json("baseline_manifest.json", {"manifest_hash": "old"})
        authority = self._write_json(
            "repair_authority.json",
            {
                "schema": "lecture-animation-narration-user-authority-v1",
                "authorization": "post_animation_narration_repair",
                "workflow_id": state["workflow_id"],
                "candidate_hash": state["current_candidate"]["candidate_hash"],
                "human_text": "这句话重新配一下，动画不改。",
                "animation_source_change_allowed": False,
            },
        )
        invalidates = [
            "tts_audio", "asr", "word_alignment", "subtitles", "timeline",
            "scene_production", "visual_plan_binding", "scene_registry",
            "runtime_telemetry", "authoring_qc", "review_manifest",
            "author_self_review", "independent_review", "episode_assembly",
            "final_master_audit",
        ]
        repair = self._write_json(
            "repair.json",
            {
                "schema": "lecture-animation-post-animation-narration-repair-v1",
                "workflow_id": state["workflow_id"],
                "candidate_hash": state["current_candidate"]["candidate_hash"],
                "repair_kind": "performance_only",
                "reason": "pronunciation retake",
                "affected_scenes": ["g015"],
                "cue_windows": [{"scene_slug": "g015", "start": 1.0, "end": 2.0}],
                "animation_source_change_allowed": False,
                "invalidates": invalidates,
            },
        )
        old_candidate = state["current_candidate"]["candidate_hash"]
        self._run(
            command_open_post_animation_narration_repair,
            expected_state_hash=state["state_hash"],
            actor_id="root",
            repair=str(repair),
            user_authority=str(authority),
            baseline_manifest=str(baseline),
        )
        state = self._state()
        self.assertEqual(state["status"], "user_script_approved")
        self.assertEqual(state["current_candidate"]["candidate_hash"], old_candidate)
        self.assertIsNone(state["tts_lock"])
        self.assertIsNone(state["animation_release"])
        self.assertTrue(state["post_animation_repair"]["repair_context_hash"])

    def test_post_animation_script_change_reopens_full_review(self) -> None:
        self._approved_and_tts_locked()
        state = self._animation_release()
        baseline = self._write_json("baseline_manifest.json", {"manifest_hash": "old"})
        authority = self._write_json(
            "repair_authority.json",
            {
                "schema": "lecture-animation-narration-user-authority-v1",
                "authorization": "post_animation_narration_repair",
                "workflow_id": state["workflow_id"],
                "candidate_hash": state["current_candidate"]["candidate_hash"],
                "human_text": "口播文案需要重写，但不要先重做动画。",
                "animation_source_change_allowed": False,
            },
        )
        repair = self._write_json(
            "script_repair.json",
            {
                "schema": "lecture-animation-post-animation-narration-repair-v1",
                "workflow_id": state["workflow_id"],
                "candidate_hash": state["current_candidate"]["candidate_hash"],
                "repair_kind": "script_change",
                "reason": "remove ambiguous narration",
                "affected_scenes": ["g001"],
                "cue_windows": [{"scene_slug": "g001", "start": 0.0, "end": 4.0}],
                "animation_source_change_allowed": False,
                "invalidates": [
                    "tts_audio", "asr", "word_alignment", "subtitles", "timeline",
                    "scene_production", "visual_plan_binding", "scene_registry",
                    "runtime_telemetry", "authoring_qc", "review_manifest",
                    "author_self_review", "independent_review", "episode_assembly",
                    "final_master_audit",
                ],
            },
        )
        self._run(
            command_open_post_animation_narration_repair,
            expected_state_hash=state["state_hash"],
            actor_id="root",
            repair=str(repair),
            user_authority=str(authority),
            baseline_manifest=str(baseline),
        )
        state = self._state()
        self.assertEqual(state["status"], "revision_required")
        self.assertIsNone(state["current_candidate"])
        with self.assertRaisesRegex(PipelineError, "before exact user script approval"):
            preflight = self._write_json("blocked_preflight.json", {"valid": True})
            self._run(
                command_lock_narration_tts_input,
                expected_state_hash=state["state_hash"],
                actor_id="root",
                preflight=str(preflight),
            )


if __name__ == "__main__":
    unittest.main()
