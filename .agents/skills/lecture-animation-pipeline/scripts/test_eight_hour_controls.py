#!/usr/bin/env python3

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("pipeline_v2.py")
SPEC = importlib.util.spec_from_file_location("pipeline_v2_eight_hour", MODULE_PATH)
assert SPEC and SPEC.loader
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


class EightHourControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_capacity_trust_roots = json.loads(
            json.dumps(pipeline.DELIVERY_CAPACITY_REPLAN_TRUST_ROOTS)
        )
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        skill = self.root / ".agents" / "skills" / "lecture-animation-pipeline"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# pinned test skill\n", encoding="utf-8")

    def tearDown(self) -> None:
        pipeline.DELIVERY_CAPACITY_REPLAN_TRUST_ROOTS.clear()
        pipeline.DELIVERY_CAPACITY_REPLAN_TRUST_ROOTS.update(
            self.original_capacity_trust_roots
        )
        self.temp.cleanup()

    def write_json(self, path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def file_sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def write_unit_window_compatibility_chain(
        self,
        scene_slug: str = "g012_complete_local_expansion",
    ) -> tuple[Path, dict]:
        episode_identity = "videos/0011-mpm-11-analyticity"
        base = self.root / episode_identity / "review" / "v2"
        scene = base / scene_slug
        reviewer_scene = self.root / "independent" / scene_slug
        authority_path = base / "night_reviewer" / "episode-authority.json"
        authority_path.parent.mkdir(parents=True, exist_ok=True)
        authority_path.write_bytes(b"approved provisional episode authority\n")
        # The production trust root is deliberately exact.  Tests exercise the
        # same byte identity without weakening that production assertion.
        authority_sha = self.file_sha256(authority_path)

        script = scene / "narration" / "formal_script.txt"
        audio = scene / "narration" / "audio.wav"
        unit_plan = scene / "narration" / "tts_plan.json"
        registry = scene / "screen-registry.json"
        for path, payload in (
            (script, b"approved text\n"),
            (audio, b"RIFF unit-window audio"),
            (unit_plan, b'{"units":["u01"]}\n'),
            (registry, b'{"semantic_items":[]}\n'),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

        design_path = scene / "design.json"
        design = {
            "schema": pipeline.UNIT_WINDOW_DESIGN_SCHEMA,
            "scene_slug": scene_slug,
            "status": "candidate_for_distinct_unit_window_design_review_only",
            "authority_boundary": {
                "human_audio_pending": True,
                "word_alignment_available": False,
                "exact_seconds_claimed": False,
                "source_authoring_authorized": False,
                "render_authorized": False,
                "finalization_authorized": False,
            },
            "bindings": {
                "approved_text": {"sha256": self.file_sha256(script)},
                "decoded_audio": {"sha256": self.file_sha256(audio)},
                "tts_unit_plan": {"sha256": self.file_sha256(unit_plan)},
                "screen_text_registry": {"sha256": self.file_sha256(registry)},
            },
        }
        self.write_json(design_path, design)
        design_sha = self.file_sha256(design_path)

        static_path = scene / "static.json"
        checks = {
            key: True
            for key in (
                "all_exact_seconds_absent",
                "all_stage_actions_bound_to_approved_text_units",
                "all_windows_include_M_D_A",
                "all_windows_include_real_math_driver",
                "every_unit_covered_once",
                "screen_text_payloads_match_current_registry_byte_for_byte",
                "unit_order_matches_tts_plan_exactly",
            )
        }
        self.write_json(
            static_path,
            {
                "schema": "lecture-animation-approved-text-unit-window-static-audit-v1",
                "scene_slug": scene_slug,
                "design_sha256": design_sha,
                "verdict": "pass_for_distinct_unit_window_design_review_only",
                "checks": checks,
            },
        )
        static_sha = self.file_sha256(static_path)

        self_path = scene / "self.json"
        false_boundary = {
            key: False
            for key in (
                "exact_timing_approved",
                "finalization_authorized",
                "human_audio_approved",
                "render_authorized",
                "source_authoring_authorized",
            )
        }
        self.write_json(
            self_path,
            {
                "schema": "lecture-animation-approved-text-unit-window-author-self-review-v1",
                "scene_slug": scene_slug,
                "author_agent_id": "/root/author",
                "design_sha256": design_sha,
                "static_audit_sha256": static_sha,
                "decision": "pass_for_distinct_unit_window_design_review_only",
                "findings": [],
                "authorization_boundary": false_boundary,
            },
        )
        self_sha = self.file_sha256(self_path)

        technical_path = reviewer_scene / "technical.json"
        technical_boundary = {
            key: False
            for key in (
                "human_audio_approved",
                "word_alignment_available",
                "exact_timing_approved",
                "source_authoring_authorized",
                "render_authorized",
                "finalization_or_git_authorized",
            )
        }
        self.write_json(
            technical_path,
            {
                "schema": "lecture-animation-independent-approved-text-unit-window-design-technical-review-v1",
                "episode": episode_identity,
                "scene_slug": scene_slug,
                "reviewer_agent_id": "/root/reviewer",
                "candidate": {"sha256": design_sha},
                "author_chain": {
                    "static_audit": {"sha256": static_sha},
                    "author_self_review": {"sha256": self_sha},
                },
                "verdict": "PASS_FOR_DELEGATED_UNIT_WINDOW_VISUAL_DIRECTION_GATE_ONLY",
                "findings": [],
                "authorization_boundary": technical_boundary,
            },
        )
        technical_sha = self.file_sha256(technical_path)

        proxy_path = base / "night_reviewer" / "proxy.json"
        proxy_boundary = {
            "human_audio_approved": False,
            "word_alignment_available": False,
            "exact_timing_approved": False,
            "source_authoring_authorized_by_this_verdict_alone": False,
            "render_authorized_by_this_verdict_alone": False,
            "finalization_assembly_or_git_authorized": False,
        }
        self.write_json(
            proxy_path,
            {
                "schema": "lecture-animation-delegated-approved-text-unit-window-visual-direction-verdict-v1",
                "episode": episode_identity,
                "scene_slug": scene_slug,
                "verdict": "APPROVE_PROVISIONAL_UNIT_WINDOW_VISUAL_DIRECTION_HUMAN_AUDIO_AND_EXACT_TIMING_PENDING",
                "exact_bindings": {
                    "unit_window_design_sha256": design_sha,
                    "static_audit_sha256": static_sha,
                    "author_self_review_sha256": self_sha,
                    "distinct_technical_review_sha256": technical_sha,
                    "delegated_episode_provisional_authority_sha256": authority_sha,
                },
                "authorization": proxy_boundary,
            },
        )
        proxy_sha = self.file_sha256(proxy_path)

        production_path = scene / "production.json"
        self.write_json(
            production_path,
            {
                "schema": pipeline.UNIT_WINDOW_SCENE_PRODUCTION_SCHEMA,
                "episode": episode_identity,
                "scene_slug": scene_slug,
                "state": "approved_text_unit_windows_machine_pending",
                "exact_timing_available": False,
                "pending": {
                    "asr": True,
                    "exact_seconds": True,
                    "human_audio": True,
                    "word_alignment": True,
                },
                "artifacts": {
                    "unit_window_design": {"sha256": design_sha},
                    "proxy_direction": {"sha256": proxy_sha},
                    "audio": {"sha256": self.file_sha256(audio)},
                    "script": {"sha256": self.file_sha256(script)},
                    "tts_unit_plan": {"sha256": self.file_sha256(unit_plan)},
                    "screen_text_registry": {"sha256": self.file_sha256(registry)},
                },
            },
        )
        production_sha = self.file_sha256(production_path)

        release_path = scene / "release.json"
        release = {
            "schema": "lecture-animation-narration-animation-release-v1",
            "workflow_id": "test-unit-window-workflow",
            "candidate_hash": "candidate-g012",
            "verdict": "animation_authorized",
            "human_audio_gate": "user_authorized_machine_pending",
            "word_alignment_gate": "pending_not_required_for_unit_window_provisional_render",
            "unit_window_design": {"sha256": design_sha},
            "scene_production_inventory": {"sha256": production_sha},
            "distinct_unit_window_review": {"sha256": technical_sha},
            "delegated_visual_direction_gate": {"sha256": proxy_sha},
            "delegated_episode_provisional_authority": {"sha256": authority_sha},
            "forbidden_claims": [
                "human audio PASS",
                "ASR or word alignment available",
                "exact phrase or word seconds",
                "final candidate acceptance",
                "assembly, finalization or Git authorization",
            ],
        }
        self.write_json(release_path, release)
        release_sha = self.file_sha256(release_path)

        workflow_path = scene / "workflow.json"
        workflow = {
            "schema": "lecture-animation-narration-workflow-v2",
            "episode": episode_identity,
            "workflow_id": release["workflow_id"],
            "status": "animation_authorized",
            "current_candidate": {"candidate_hash": release["candidate_hash"]},
            "animation_release": {
                "path": pipeline.relative_or_absolute(release_path, self.root),
                "sha256": release_sha,
            },
        }
        workflow["state_hash"] = pipeline.object_hash(workflow)
        self.write_json(workflow_path, workflow)

        readiness_path = scene / "post-tts.json"
        readiness = {
            "schema": "lecture-animation-episode-readiness-receipt-v2",
            "episode": episode_identity,
            "status": "pass",
            "readiness_stage": "post_tts",
            "errors": [],
            "scenes": [{"scene_slug": scene_slug}],
        }
        readiness["receipt_hash"] = pipeline.object_hash(readiness)
        self.write_json(readiness_path, readiness)

        input_paths = {
            "unit_window_design": design_path,
            "static_audit": static_path,
            "author_self_review": self_path,
            "distinct_technical_review": technical_path,
            "delegated_visual_direction": proxy_path,
            "scene_production": production_path,
            "animation_release": release_path,
            "narration_workflow": workflow_path,
            "post_tts_readiness": readiness_path,
            "delegated_episode_provisional_authority": authority_path,
        }
        receipt = {
            "schema": pipeline.UNIT_WINDOW_PHASE_COMPATIBILITY_SCHEMA,
            "compiler": "pipeline_v2.seal-provisional-unit-window-phase-start-compatibility",
            "created_at": "2026-08-13T00:00:00+00:00",
            "episode": episode_identity,
            "scene_slug": scene_slug,
            "allowed_phases": ["authoring", "render"],
            "timing_authority": "approved_tts_unit_windows_only",
            "truth_boundary": {
                "human_audio_pending": True,
                "asr_pending": True,
                "word_alignment_pending": True,
                "exact_seconds_pending": True,
                "standard_visual_plan_claimed": False,
                "finalization_authorized": False,
                "assembly_authorized": False,
                "git_authorized": False,
            },
            "inputs": {
                key: pipeline.artifact_snapshot(path, self.root)
                for key, path in input_paths.items()
            },
        }
        receipt["inputs"]["delegated_episode_provisional_authority"][
            "sha256"
        ] = "165729e8bf552aeb5940e8fd33de7a02c49d9f84425679a896509456df9a544e"
        # Match every transitive user-authority binding to the production root.
        receipt["receipt_hash"] = pipeline.object_hash(receipt)
        return scene / "compatibility.json", receipt

    def test_unit_window_compatibility_is_narrow_and_hash_bound(self) -> None:
        path, receipt = self.write_unit_window_compatibility_chain()
        authority_binding = receipt["inputs"][
            "delegated_episode_provisional_authority"
        ]
        # The fixture bytes do not equal the immutable production user root;
        # patch only this one descriptor and its transitive records to prove
        # that validator rejects self-attestation unless the fixed root matches.
        errors = pipeline.validate_unit_window_phase_compatibility_data(
            receipt, self.root, receipt["scene_slug"]
        )
        self.assertTrue(
            any(
                "delegated_episode_provisional_authority is stale" in item
                for item in errors
            )
        )

        actual_authority_sha = self.file_sha256(
            self.root / authority_binding["path"]
        )
        receipt["inputs"]["delegated_episode_provisional_authority"][
            "sha256"
        ] = actual_authority_sha
        proxy_path = self.root / receipt["inputs"]["delegated_visual_direction"]["path"]
        proxy = pipeline.load_json(proxy_path)
        proxy["exact_bindings"][
            "delegated_episode_provisional_authority_sha256"
        ] = actual_authority_sha
        self.write_json(proxy_path, proxy)
        release_path = self.root / receipt["inputs"]["animation_release"]["path"]
        release = pipeline.load_json(release_path)
        release["delegated_episode_provisional_authority"]["sha256"] = actual_authority_sha
        self.write_json(release_path, release)
        # A semantically self-consistent clone still fails the immutable root.
        stale_errors = pipeline.validate_unit_window_phase_compatibility_data(
            receipt, self.root, receipt["scene_slug"]
        )
        self.assertTrue(any("delegated user authority" in item for item in stale_errors))
        legacy_errors = pipeline.validate_scene_production_data(
            pipeline.load_json(
                self.root / receipt["inputs"]["scene_production"]["path"]
            ),
            self.root,
            receipt["scene_slug"],
        )
        self.assertIn(
            "scene production schema must be lecture-animation-scene-production-v2",
            legacy_errors,
        )

        mutated = json.loads(json.dumps(receipt))
        mutated["truth_boundary"]["finalization_authorized"] = True
        mutated.pop("receipt_hash", None)
        mutated["receipt_hash"] = pipeline.object_hash(mutated)
        boundary_errors = pipeline.validate_unit_window_phase_compatibility_data(
            mutated, self.root, receipt["scene_slug"]
        )
        self.assertIn(
            "unit-window compatibility truth boundary is invalid",
            boundary_errors,
        )

        mutated = json.loads(json.dumps(receipt))
        mutated["inputs"]["distinct_technical_review"]["sha256"] = "f" * 64
        mutated.pop("receipt_hash", None)
        mutated["receipt_hash"] = pipeline.object_hash(mutated)
        drift_errors = pipeline.validate_unit_window_phase_compatibility_data(
            mutated, self.root, receipt["scene_slug"]
        )
        self.assertTrue(any("distinct_technical_review is stale" in item for item in drift_errors))

    def test_animation_release_rebind_only_accepts_exact_authority_supersession(self) -> None:
        root = self.root
        state_path = root / "videos/0011/review/v2/g012/narration_workflow.json"
        old_authority = root / "videos/0011/review/v2/night/old-authority.json"
        new_authority = root / "videos/0011/review/v2/night/new-authority.json"
        old_authority.parent.mkdir(parents=True, exist_ok=True)
        old_authority.write_bytes(b"old\n")
        new_authority.write_bytes(b"new\n")
        old_sha = self.file_sha256(old_authority)
        new_sha = self.file_sha256(new_authority)
        # Production exact roots are immutable; the test replaces module
        # constants only within this method and restores them in finally.
        original_old = "165729e8bf552aeb5940e8fd33de7a02c49d9f84425679a896509456df9a544e"
        original_new = "db7b677597cc0961255e2fc6972e53e637652956875bd3d1cd26aeaa6d4f4b48"
        release_dir = state_path.parent
        old_release = release_dir / "release-r01.json"
        new_release = release_dir / "release-r02.json"
        common = {
            "schema": "lecture-animation-narration-animation-release-v1",
            "workflow_id": "workflow-g012",
            "candidate_hash": "candidate-g012",
            "verdict": "animation_authorized",
            "human_audio_gate": "user_authorized_machine_pending",
            "word_alignment_gate": "pending_not_required_for_unit_window_provisional_render",
            "unit_window_design": {"sha256": "1" * 64},
            "scene_production_inventory": {"path": "x", "sha256": "2" * 64},
            "distinct_unit_window_review": {"sha256": "3" * 64},
            "delegated_visual_direction_gate": {"sha256": "4" * 64},
            "screen_text_registry": {"sha256": "5" * 64},
            "scope": "provisional",
            "forbidden_claims": ["final"],
            "invalidation_rule": "changed bytes invalidate",
            "post_tts_readiness": {"path": "y", "sha256": "6" * 64},
        }
        self.write_json(
            old_release,
            {
                **common,
                "delegated_episode_provisional_authority": {
                    "path": pipeline.relative_or_absolute(old_authority, root),
                    "sha256": old_sha,
                },
            },
        )
        self.write_json(
            new_release,
            {
                **common,
                "delegated_episode_provisional_authority": {
                    "path": pipeline.relative_or_absolute(new_authority, root),
                    "sha256": new_sha,
                },
            },
        )
        state = {
            "schema": "lecture-animation-narration-workflow-v2",
            "workflow_id": "workflow-g012",
            "episode": "videos/0011",
            "status": "animation_authorized",
            "revision": 1,
            "actors": {"coordinator": "/root"},
            "current_candidate": {"candidate_hash": "candidate-g012"},
            "animation_release": {
                "path": pipeline.relative_or_absolute(old_release, root),
                "sha256": self.file_sha256(old_release),
                "size": old_release.stat().st_size,
            },
            "history": [],
        }
        state["state_hash"] = pipeline.object_hash(state)
        self.write_json(state_path, state)
        # The command must reject any mutation of a protected release field
        # before it can write the workflow.  This remains true even when the
        # new authority descriptor is otherwise present.
        changed = json.loads(new_release.read_text())
        changed["scope"] = "broadened"
        self.write_json(new_release, changed)
        before = state_path.read_bytes()
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "changes protected field: scope",
        ):
            pipeline.command_rebind_narration_animation_release(
                SimpleNamespace(
                    repo_root=str(root),
                    state=str(state_path),
                    expected_state_hash=state["state_hash"],
                    actor_id="/root",
                    release=str(new_release),
                )
            )
        self.assertEqual(state_path.read_bytes(), before)

    def begin_clock(self, slug: str = "0100-eight-hour") -> tuple[Path, Path]:
        episode = self.root / "videos" / slug
        clock = episode / "review" / "evolution" / "delivery_clock.json"
        preflight_path = self.root / ".pipeline-preflight.json"
        preflight = {
            "schema": pipeline.PIPELINE_PREFLIGHT_SCHEMA,
            "created_at": "2026-08-01T00:00:00+00:00",
            "repo_root": str(self.root),
            "skill_tree_hash": pipeline.skill_tree_hash(self.root, None),
            "tests": list(pipeline.PIPELINE_PREFLIGHT_TESTS),
            "command": ["python3", "-m", "unittest"],
            "returncode": 0,
            "duration_seconds": 1.0,
            "stdout_sha256": "a" * 64,
            "stderr_sha256": "b" * 64,
            "status": "pass",
        }
        preflight["receipt_hash"] = pipeline.object_hash(preflight)
        self.write_json(preflight_path, preflight)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_begin_delivery_clock(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(episode),
                        delivery_target_hours=8.0,
                        retrospective_reserve_minutes=45.0,
                        preflight_receipt=str(preflight_path),
                        sol_review_model="gpt-5.6-sol",
                        output=str(clock),
                    )
                ),
                0,
            )
        return episode, clock

    def begin_efficiency(self, episode: Path, clock: Path) -> Path:
        output = episode / "review" / "evolution" / "efficiency.json"
        args = pipeline.build_parser().parse_args(
            [
                "begin-episode-efficiency",
                "--repo-root",
                str(self.root),
                "--episode",
                str(episode),
                "--delivery-clock",
                str(clock),
                "--output",
                str(output),
            ]
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(args.func(args), 0)
        return output

    def test_initialization_cannot_exit_with_a_prose_only_artifact(self) -> None:
        episode, clock = self.begin_clock("0100-startup-gate")
        prose = episode / "startup.md"
        prose.write_text("Roster and worktrees look ready.", encoding="utf-8")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "clean executable episode startup receipt",
        ):
            self.transition(
                clock,
                action="checkpoint",
                stage="lecture_approval",
                artifact=str(prose),
            )

    def write_idle_supervisor(self, episode: Path, *, active: bool = False) -> Path:
        path = episode / "review" / "v2" / "supervisor_session.json"
        assignments = {}
        tasks = {}
        if active:
            assignments["author-1"] = {
                "role": "animation_author",
                "task_key": "batch-a",
                "scope": "g001",
                "model": "gpt-5.6-sol",
                "state": "active",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            tasks["batch-a"] = {
                "state": "active",
                "current_agent_id": "author-1",
            }
        value = {
            "schema": "lecture-animation-supervisor-session-v2",
            "session_id": "eight-hour-test-supervisor",
            "supervisor_agent_id": "/root",
            "assignments": assignments,
            "task_queue": tasks,
        }
        value["session_hash"] = pipeline.object_hash(value)
        self.write_json(path, value)
        return path

    def transition(self, clock: Path, **overrides: object) -> int:
        values: dict[str, object] = {
            "repo_root": str(self.root),
            "clock": str(clock),
            "action": "resume",
            "stage": None,
            "reason": None,
            "artifact": None,
            "preflight_receipt": None,
            "startup_receipt": None,
            "efficiency_contract": None,
            "supervisor_session": None,
            "offline_evidence": None,
            "completion_receipt": None,
            "portability_receipt": None,
        }
        values.update(overrides)
        with contextlib.redirect_stdout(io.StringIO()):
            return pipeline.command_transition_delivery_clock(
                SimpleNamespace(**values)
            )

    def test_delivery_clock_refreshes_green_preflight_without_reset(self) -> None:
        episode, clock_path = self.begin_clock("0100-preflight-refresh")
        before = pipeline.load_json(clock_path)
        before_t0 = before["t0"]
        before_stage = before["current_stage"]
        before_board = json.loads(json.dumps(before["scene_board"]))

        skill_file = (
            self.root
            / ".agents"
            / "skills"
            / "lecture-animation-pipeline"
            / "SKILL.md"
        )
        skill_file.write_text(
            "# pinned test skill\n\nupdated gate implementation\n",
            encoding="utf-8",
        )
        stale_errors = pipeline.validate_delivery_clock(
            pipeline.load_json(clock_path), repo_root=self.root
        )
        self.assertIn(
            "pipeline preflight is stale for the current Skill tree",
            stale_errors,
        )

        fresh_preflight = self.root / ".pipeline-preflight-r02.json"
        fresh_receipt = {
            "schema": pipeline.PIPELINE_PREFLIGHT_SCHEMA,
            "created_at": "2026-08-01T00:00:00+00:00",
            "repo_root": str(self.root),
            "skill_tree_hash": pipeline.skill_tree_hash(self.root, None),
            "tests": list(pipeline.PIPELINE_PREFLIGHT_TESTS),
            "command": ["python3", "-m", "unittest"],
            "returncode": 0,
            "duration_seconds": 1.0,
            "stdout_sha256": "c" * 64,
            "stderr_sha256": "d" * 64,
            "status": "pass",
        }
        fresh_receipt["receipt_hash"] = pipeline.object_hash(fresh_receipt)
        self.write_json(fresh_preflight, fresh_receipt)
        self.assertEqual(
            self.transition(
                clock_path,
                action="refresh-preflight",
                reason=(
                    "Replace the stale receipt after a tested Skill gate fix."
                ),
                preflight_receipt=str(fresh_preflight),
            ),
            0,
        )
        after = pipeline.load_json(clock_path)
        self.assertEqual(after["t0"], before_t0)
        self.assertEqual(after["current_stage"], before_stage)
        self.assertEqual(after["scene_board"], before_board)
        self.assertEqual(len(after["preflight_refreshes"]), 1)
        self.assertEqual(
            pipeline.validate_delivery_clock(after, repo_root=self.root), []
        )

    def update_board(
        self,
        clock: Path,
        scene: str,
        state: str,
        *,
        evidence: Path | None = None,
        representative: bool = False,
        release: Path | None = None,
        outcome_log: Path | None = None,
        owner: str | None = None,
        self_review_attempt_log: Path | None = None,
        repair_reopen: bool = False,
    ) -> int:
        with contextlib.redirect_stdout(io.StringIO()):
            return pipeline.command_update_delivery_board(
                SimpleNamespace(
                    repo_root=str(self.root),
                    clock=str(clock),
                    scene_slug=scene,
                    state=state,
                    evidence=str(evidence) if evidence else None,
                    owner_agent_id=owner or f"owner-{scene}",
                    self_review_attempt_log=(
                        str(self_review_attempt_log)
                        if self_review_attempt_log
                        else None
                    ),
                    repair_reopen=repair_reopen,
                    human_outcome_log=(
                        str(outcome_log) if outcome_log else None
                    ),
                    representative=representative,
                    representative_release=str(release) if release else None,
                )
            )

    def seal_test_representative_release(
        self, episode: Path, clock: Path, scene: str
    ) -> dict[str, Path]:
        candidate = episode / "review" / f"{scene}.mp4"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(b"representative-candidate")
        manifest_path = episode / "review" / f"{scene}-manifest.json"
        manifest = {
            "schema": "lecture-animation-review-manifest-v2",
            "episode": pipeline.relative_or_absolute(episode, self.root),
            "scene_slug": scene,
            "artifacts": {
                "review_mp4": pipeline.artifact_snapshot(candidate, self.root)
            },
        }
        manifest["manifest_hash"] = pipeline.object_hash(manifest)
        self.write_json(manifest_path, manifest)
        self_review_path = episode / "review" / f"{scene}-self-review.json"
        self_review_draft = {
            "schema": "lecture-animation-author-self-review-v2",
            "scene_slug": scene,
            "manifest_hash": manifest["manifest_hash"],
            "owner": f"owner-{scene}",
            "author_agent_id": f"owner-{scene}",
            "author_model": "gpt-5.6-sol",
            "self_review_round": 1,
            "verdict": "ready_for_independent_review",
        }
        self_review = {
            **self_review_draft,
            "created_at": "2026-08-01T00:00:00+00:00",
        }
        self_review["self_review_hash"] = pipeline.object_hash(self_review)
        self.write_json(self_review_path, self_review)
        self_attempt_log = (
            episode / "review" / f"{scene}-self-review-attempts.jsonl"
        )
        self_attempt = {
            "schema": "lecture-animation-author-self-review-attempt-v2",
            "attempt_id": f"author-self-review:{scene}",
            "scene_slug": scene,
            "manifest_hash": manifest["manifest_hash"],
            "draft_hash": pipeline.object_hash(self_review_draft),
            "gate_accepted": True,
            "gate_errors": [],
            "verdict": "ready_for_independent_review",
        }
        self_attempt_log.write_text(
            json.dumps(self_attempt) + "\n", encoding="utf-8"
        )

        review_path = episode / "review" / f"{scene}-review.json"
        review = {
            "schema": "lecture-animation-review-v2",
            "scene_slug": scene,
            "verdict": "pass_for_user_review_pending",
            "owner": f"owner-{scene}",
            "reviewer": "independent-sol",
            "reviewer_model": "gpt-5.6-sol",
            "reviewer_agent_id": "independent-sol",
        }
        self.write_json(review_path, review)
        review_log = episode / "review" / f"{scene}-review_attempts.jsonl"
        session_id = f"session-{scene}"
        verification_key = pipeline.object_hash(
            {
                "manifest_hash": manifest["manifest_hash"],
                "submission_hash": pipeline.object_hash(review),
                "review_session_id": session_id,
                "gate_errors": [],
            }
        )
        attempt_id = "review:" + hashlib.sha1(
            verification_key.encode("utf-8")
        ).hexdigest()[:16]
        review_attempt = {
            "schema": "lecture-animation-review-attempt-v2",
            "attempt_id": attempt_id,
            "scene_slug": scene,
            "manifest_hash": manifest["manifest_hash"],
            "submission_hash": pipeline.object_hash(review),
            "review_session_id": session_id,
            "reviewer_model": "gpt-5.6-sol",
            "reviewer_tier": "frontier",
            "reviewer_agent_id": "independent-sol",
            "review_mode": "full_regression",
            "verdict": "pass_for_user_review_pending",
            "gate_accepted": True,
            "gate_errors": [],
            "verification_key": verification_key,
        }
        review_log.write_text(
            json.dumps(review_attempt) + "\n",
            encoding="utf-8",
        )
        session_path = episode / "review" / f"{scene}-review-session.json"
        session = {
            "schema": "lecture-animation-review-session-v2",
            "contract_version": 5,
            "session_id": session_id,
            "status": "active",
            "review_role": "acceptance",
            "episode_spine_hash": "test-spine-hash",
            "author_agent_id": f"owner-{scene}",
            "reviewer_agent_id": "independent-sol",
            "reviewer": "independent-sol",
            "reviewer_model": "gpt-5.6-sol",
            "reviewer_tier": "frontier",
            "applied_review_attempt_ids": [attempt_id],
        }
        session["session_hash"] = pipeline.object_hash(session)
        self.write_json(session_path, session)
        pass_path = episode / "review" / f"{scene}-sol-pass.json"
        clock_data = pipeline.load_json(clock)
        pass_receipt = {
            "schema": pipeline.SOL_CANDIDATE_PASS_SCHEMA,
            "compiler": "pipeline_v2.seal-sol-candidate-pass",
            "created_at": "2026-08-01T00:00:00+00:00",
            "episode": pipeline.relative_or_absolute(episode, self.root),
            "scene_slug": scene,
            "delivery_clock_t0": clock_data["t0"],
            "reviewer_model": "gpt-5.6-sol",
            "reviewer_tier": "frontier",
            "reviewer_agent_id": "independent-sol",
            "author_agent_id": f"owner-{scene}",
            "manifest": pipeline.artifact_snapshot(manifest_path, self.root),
            "manifest_hash": manifest["manifest_hash"],
            "self_review": pipeline.artifact_snapshot(
                self_review_path, self.root
            ),
            "self_review_hash": self_review["self_review_hash"],
            "self_review_attempt_log_path": pipeline.relative_or_absolute(
                self_attempt_log, self.root
            ),
            "self_review_attempt_id": self_attempt["attempt_id"],
            "self_review_attempt_hash": pipeline.object_hash(self_attempt),
            "review": pipeline.artifact_snapshot(review_path, self.root),
            "review_submission_hash": pipeline.object_hash(review),
            "review_session_path": pipeline.relative_or_absolute(
                session_path, self.root
            ),
            "review_session_id": session_id,
            "review_session_hash_at_pass": session["session_hash"],
            "review_attempt_log_path": pipeline.relative_or_absolute(
                review_log, self.root
            ),
            "review_attempt_id": attempt_id,
            "review_attempt_hash": pipeline.object_hash(review_attempt),
            "candidate": pipeline.artifact_snapshot(candidate, self.root),
            "verdict": "pass_for_user_review_pending",
        }
        pass_receipt["pass_hash"] = pipeline.object_hash(pass_receipt)
        self.write_json(pass_path, pass_receipt)
        outcome_log = episode / "review" / f"{scene}-outcomes.jsonl"
        outcome_log.write_text(
            json.dumps(
                {
                    "schema": "lecture-animation-outcome-v2",
                    "event_id": "representative-human-pass",
                    "scene_slug": scene,
                    "automatic_verdict": "pass_for_user_review_pending",
                    "human_verdict": "pass",
                    "manifest_hash": manifest["manifest_hash"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        release = episode / "review" / f"{scene}-representative_release.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_seal_representative_release(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(episode),
                        scene_slug=scene,
                        delivery_clock=str(clock),
                        sol_candidate_pass=str(pass_path),
                        outcome_log=str(outcome_log),
                        output=str(release),
                    )
                ),
                0,
            )
        return {
            "release": release,
            "manifest": manifest_path,
            "outcomes": outcome_log,
            "self_review": self_review_path,
            "self_attempts": self_attempt_log,
            "sol_pass": pass_path,
            "review_session": session_path,
            "candidate": candidate,
        }

    def prepare_finalization_stage(self, episode: Path, clock: Path) -> None:
        draft = episode / "lecture-draft.md"
        draft.write_text("Approved beginner-first lecture draft.", encoding="utf-8")
        with mock.patch(
            "pipeline_v2_lib.engine.validate_episode_startup_receipt",
            return_value=[],
        ):
            self.assertEqual(
                self.transition(
                    clock,
                    action="checkpoint",
                    stage="lecture_approval",
                    artifact=str(draft),
                    startup_receipt="startup-receipt.json",
                ),
                0,
            )
        approval = episode / "review" / "lecture-approval.json"
        approval_request = episode / "review" / "lecture-approval-request.json"
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.command_seal_human_wait_request(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(episode),
                    request_type="lecture_approval",
                    artifact=str(draft),
                    question="Please approve this exact beginner lecture draft.",
                    output=str(approval_request),
                )
            )
            pipeline.command_seal_user_approval(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(episode),
                    approval_type="lecture_draft",
                    artifact=str(draft),
                    human_wait_request=str(approval_request),
                    exact_user_text="通过，按这一版继续。",
                    planned_scene_count=6,
                    narration_minutes=8.5,
                    new_representation_families=1,
                    approved_grammar_reuse=True,
                    output=str(approval),
                )
            )
        self.assertEqual(
            self.transition(
                clock,
                action="checkpoint",
                stage="episode_spine",
                artifact=str(approval),
            ),
            0,
        )
        bundle = self.seal_test_representative_release(episode, clock, "g001")
        evidence = bundle["manifest"]
        self.update_board(clock, "g001", "queued", representative=True)
        self.update_board(clock, "g001", "plan_audio_locked", evidence=evidence)
        self.update_board(clock, "g001", "plan_sol_passed", evidence=evidence)
        self.assertEqual(
            self.transition(
                clock,
                action="checkpoint",
                stage="representative_design",
                artifact=str(evidence),
            ),
            0,
        )
        self.assertEqual(
            self.transition(
                clock,
                action="checkpoint",
                stage="representative_production",
                artifact=str(evidence),
            ),
            0,
        )
        self.update_board(clock, "g001", "authoring", evidence=evidence)
        self.update_board(clock, "g001", "rendered", evidence=evidence)
        self.update_board(
            clock,
            "g001",
            "self_review_passed",
            evidence=bundle["self_review"],
            self_review_attempt_log=bundle["self_attempts"],
        )
        self.update_board(
            clock, "g001", "sol_reviewed", evidence=bundle["sol_pass"]
        )
        self.update_board(
            clock,
            "g001",
            "approved",
            evidence=evidence,
            release=bundle["release"],
            outcome_log=bundle["outcomes"],
        )
        for stage in (
            "fanout",
            "closure",
            "finalization",
        ):
            self.assertEqual(
                self.transition(
                    clock,
                    action="checkpoint",
                    stage=stage,
                    artifact=str(evidence),
                ),
                0,
            )

    def test_clock_is_first_operation_idempotent_and_counts_all_active_gaps(self) -> None:
        episode, clock_path = self.begin_clock()
        clock = pipeline.load_json(clock_path)
        self.assertEqual(
            pipeline.delivery_clock_initial_hash(clock),
            clock["clock_hash"],
        )
        earlier = datetime.now(timezone.utc) - timedelta(seconds=10)
        clock["t0"] = earlier.isoformat()
        clock["created_at"] = earlier.isoformat()
        clock["active_intervals"][0]["started_at"] = earlier.isoformat()
        clock.pop("clock_hash", None)
        clock["clock_hash"] = pipeline.object_hash(clock)
        self.write_json(clock_path, clock)
        status = pipeline.delivery_clock_status_data(clock)
        self.assertGreaterEqual(status["active_seconds"], 9.0)

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_begin_delivery_clock(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(episode),
                        delivery_target_hours=8.0,
                        retrospective_reserve_minutes=45.0,
                        preflight_receipt=str(self.root / ".pipeline-preflight.json"),
                        sol_review_model="gpt-5.6-sol",
                        output=str(clock_path),
                    )
                ),
                0,
            )

        (episode / "hidden-prep.txt").write_text("late", encoding="utf-8")
        with self.assertRaisesRegex(
            pipeline.PipelineError, "after episode work began"
        ):
            pipeline.command_begin_delivery_clock(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(episode),
                    delivery_target_hours=8.0,
                    retrospective_reserve_minutes=45.0,
                    preflight_receipt=str(self.root / ".pipeline-preflight.json"),
                    sol_review_model="gpt-5.6-sol",
                    output=str(clock_path),
                )
            )

        late_episode = self.root / "videos" / "0101-late"
        late_episode.mkdir(parents=True)
        (late_episode / "storyboard.md").write_text("hidden", encoding="utf-8")
        with self.assertRaisesRegex(pipeline.PipelineError, "first episode operation"):
            pipeline.command_begin_delivery_clock(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(late_episode),
                    delivery_target_hours=8.0,
                    retrospective_reserve_minutes=45.0,
                    preflight_receipt=str(self.root / ".pipeline-preflight.json"),
                    sol_review_model="gpt-5.6-sol",
                    output=str(late_episode / "delivery_clock.json"),
                )
            )

        flexible_episode = self.root / "videos" / "0101-flexible"
        flexible_clock = flexible_episode / "delivery_clock.json"
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.command_begin_delivery_clock(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(flexible_episode),
                    delivery_target_hours=8.0,
                    retrospective_reserve_minutes=45.0,
                    preflight_receipt=str(self.root / ".pipeline-preflight.json"),
                    sol_review_model="gpt-5.6-sol",
                    max_production_agents=2,
                    max_frozen_candidates=1,
                    output=str(flexible_clock),
                )
            )
        flexible = pipeline.load_json(flexible_clock)
        self.assertEqual(flexible["max_production_agents"], 2)
        self.assertEqual(flexible["max_frozen_candidates"], 1)

    def test_delivery_forecast_moves_forward_with_stage_overrun(self) -> None:
        started = datetime.now(timezone.utc) - timedelta(hours=9)
        clock = {
            "status": "active",
            "current_stage": "closure",
            "t0": started.isoformat(),
            "active_intervals": [
                {"started_at": started.isoformat(), "ended_at": None}
            ],
            "pause_intervals": [],
            "delivery_target_seconds": 8 * 3600,
            "stage_deadline_seconds": dict(
                pipeline.DELIVERY_STAGE_DEADLINE_SECONDS
            ),
            "scope_forecast": {"normalized_delivery_hours": 8.0},
            "scene_board": {},
        }
        status = pipeline.delivery_clock_status_data(clock)
        self.assertGreaterEqual(
            status["projected_upload_ready_seconds"], 10 * 3600 - 1
        )
        self.assertGreaterEqual(
            status["projection_over_target_seconds"], 2 * 3600 - 1
        )
        self.assertTrue(status["schedule_at_risk"])
        self.assertEqual(
            status["forecast_basis"]["planned_tail_seconds"], 3600
        )

    def test_tts_and_asr_start_after_episode_spine_without_plan_cycle(self) -> None:
        self.assertEqual(
            pipeline.phase_minimum_delivery_stage("tts"),
            "episode_spine",
        )
        self.assertEqual(
            pipeline.phase_minimum_delivery_stage("asr"),
            "episode_spine",
        )
        self.assertEqual(
            pipeline.phase_minimum_delivery_stage("authoring"),
            "representative_production",
        )
        self.assertEqual(
            pipeline.phase_minimum_delivery_stage("render"),
            "representative_production",
        )
        self.assertLess(
            pipeline.DELIVERY_STAGE_SEQUENCE.index(
                pipeline.phase_minimum_delivery_stage("tts")
            ),
            pipeline.DELIVERY_STAGE_SEQUENCE.index("representative_design"),
            "exact audio must be producible before the word-timed plan gate",
        )

    def test_pause_resume_requires_sealed_request_and_no_concurrent_work(self) -> None:
        episode, clock = self.begin_clock("0102-pause")
        efficiency = self.begin_efficiency(episode, clock)
        supervisor = self.write_idle_supervisor(episode)
        draft = episode / "lecture_draft.md"
        draft.write_text("Beginner causal lecture draft", encoding="utf-8")
        request_path = episode / "review" / "human_wait_request.json"
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.command_seal_human_wait_request(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(episode),
                    request_type="lecture_approval",
                    artifact=str(draft),
                    question="Please approve this exact beginner lecture draft.",
                    output=str(request_path),
                )
            )

        state_path = episode / "review" / "active-design.json"
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(episode),
                    efficiency_contract=str(efficiency),
                    delivery_clock=str(clock),
                    run_id="active-before-human-wait",
                    scene_slug="g001",
                    phase="planning",
                    phase_purpose="lecture_draft",
                    actor_model="gpt-5.6-sol",
                    active_seconds_allocation=60,
                    raw_token_allocation=10,
                    uncached_input_token_allocation=1,
                    output_token_allocation=1,
                    reasoning_token_allocation=1,
                    state=str(state_path),
                )
            )
        with self.assertRaisesRegex(pipeline.PipelineError, "reservations are active"):
            self.transition(
                clock,
                action="pause-human",
                reason="Waiting for the exact lecture approval artifact.",
                artifact=str(request_path),
                efficiency_contract=str(efficiency),
                supervisor_session=str(supervisor),
            )
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.command_phase_end(
                SimpleNamespace(
                    state=str(state_path),
                    phase_log=str(episode / "review" / "planning.jsonl"),
                    result="completed",
                    manifest_hash="",
                    usage_file=None,
                    input_tokens=1,
                    cached_input_tokens=0,
                    output_tokens=1,
                    reasoning_tokens=1,
                )
            )

        draft.write_text("changed after request", encoding="utf-8")
        with self.assertRaisesRegex(pipeline.PipelineError, "changed after sealing"):
            self.transition(
                clock,
                action="pause-human",
                reason="Waiting for the exact lecture approval artifact.",
                artifact=str(request_path),
                efficiency_contract=str(efficiency),
                supervisor_session=str(supervisor),
            )
        fresh_request = episode / "review" / "human_wait_request_r02.json"
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.command_seal_human_wait_request(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(episode),
                    request_type="lecture_approval",
                    artifact=str(draft),
                    question="Please approve the corrected exact lecture draft.",
                    output=str(fresh_request),
                )
            )
        self.assertEqual(
            self.transition(
                clock,
                action="pause-human",
                reason="Waiting for the corrected lecture approval decision.",
                artifact=str(fresh_request),
                efficiency_contract=str(efficiency),
                supervisor_session=str(supervisor),
            ),
            0,
        )
        self.assertEqual(self.transition(clock, action="resume"), 0)

        offline_path = episode / "review" / "offline.json"
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.command_seal_machine_offline_evidence(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(episode),
                    exact_user_text="先暂停并保留 sessions，关机后再恢复。",
                    output=str(offline_path),
                )
            )
        active_supervisor = self.write_idle_supervisor(episode, active=True)
        with self.assertRaisesRegex(pipeline.PipelineError, "assignments are active"):
            self.transition(
                clock,
                action="pause-offline",
                reason="The host is being shut down by the user now.",
                efficiency_contract=str(efficiency),
                supervisor_session=str(active_supervisor),
                offline_evidence=str(offline_path),
            )
        self.write_idle_supervisor(episode, active=False)
        self.assertEqual(
            self.transition(
                clock,
                action="pause-offline",
                reason="The host is being shut down by the user now.",
                efficiency_contract=str(efficiency),
                supervisor_session=str(active_supervisor),
                offline_evidence=str(offline_path),
            ),
            0,
        )
        self.assertEqual(self.transition(clock, action="resume"), 0)
        final_status = pipeline.delivery_clock_status_data(
            pipeline.load_json(clock)
        )
        self.assertEqual(final_status["status"], "active")
        self.assertEqual(len(pipeline.load_json(clock)["pause_intervals"]), 2)

    def test_upload_ready_rejects_stale_or_mismatched_final_master(self) -> None:
        episode, clock = self.begin_clock("0103-upload")
        efficiency = self.begin_efficiency(episode, clock)
        supervisor = self.write_idle_supervisor(episode)
        self.prepare_finalization_stage(episode, clock)
        first = episode / "exports" / "final" / "episode.mp4"
        first.parent.mkdir(parents=True)
        first.write_bytes(b"approved-master")
        first_artifact = pipeline.artifact_snapshot(first, self.root)
        completion_path = episode / "episode_completion.json"
        completion = {
            "schema": "lecture-animation-episode-completion-v2",
            "episode": pipeline.relative_or_absolute(episode, self.root),
            "scene_outcomes": {},
            "final_artifacts": {"final_video": first_artifact},
        }
        completion["completion_hash"] = pipeline.object_hash(completion)
        self.write_json(completion_path, completion)

        second = episode / "exports" / "final" / "other.mp4"
        second.write_bytes(b"other-master")
        mismatch = {
            "schema": "lecture-animation-portability-audit-v2",
            "episode": pipeline.relative_or_absolute(episode, self.root),
            "status": "pass",
            "required_artifacts": {
                "final_video": pipeline.artifact_snapshot(second, self.root)
            },
        }
        mismatch["receipt_hash"] = pipeline.object_hash(mismatch)
        portability_path = episode / "review" / "portability.json"
        self.write_json(portability_path, mismatch)
        with self.assertRaisesRegex(
            pipeline.PipelineError, "completion receipt failed"
        ):
            self.transition(
                clock,
                action="upload-ready",
                efficiency_contract=str(efficiency),
                supervisor_session=str(supervisor),
                completion_receipt=str(completion_path),
                portability_receipt=str(portability_path),
            )

        self.assertEqual(pipeline.load_json(clock)["status"], "active")

    def test_representative_release_and_wip_caps_are_executable_gates(self) -> None:
        episode, clock = self.begin_clock("0106-wip")
        draft = episode / "lecture.md"
        draft.write_text("Approved beginner lecture.", encoding="utf-8")
        with mock.patch(
            "pipeline_v2_lib.engine.validate_episode_startup_receipt",
            return_value=[],
        ):
            self.transition(
                clock,
                action="checkpoint",
                stage="lecture_approval",
                artifact=str(draft),
                startup_receipt="startup-receipt.json",
            )
        approval = episode / "lecture-approval.json"
        approval_request = episode / "lecture-approval-request.json"
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.command_seal_human_wait_request(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(episode),
                    request_type="lecture_approval",
                    artifact=str(draft),
                    question="Please approve this exact beginner lecture draft.",
                    output=str(approval_request),
                )
            )
            pipeline.command_seal_user_approval(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(episode),
                    approval_type="lecture_draft",
                    artifact=str(draft),
                    human_wait_request=str(approval_request),
                    exact_user_text="通过，继续制作。",
                    planned_scene_count=6,
                    narration_minutes=8.5,
                    new_representation_families=1,
                    approved_grammar_reuse=True,
                    output=str(approval),
                )
            )
        self.transition(
            clock,
            action="checkpoint",
            stage="episode_spine",
            artifact=str(approval),
        )
        g001 = self.seal_test_representative_release(episode, clock, "g001")
        evidence = g001["manifest"]
        self.update_board(clock, "g001", "queued", representative=True)
        self.update_board(clock, "g001", "plan_audio_locked", evidence=evidence)
        self.update_board(clock, "g001", "plan_sol_passed", evidence=evidence)
        self.transition(
            clock,
            action="checkpoint",
            stage="representative_design",
            artifact=str(evidence),
        )
        self.transition(
            clock,
            action="checkpoint",
            stage="representative_production",
            artifact=str(evidence),
        )
        self.update_board(clock, "g001", "authoring", evidence=evidence)
        self.update_board(clock, "g001", "rendered", evidence=evidence)
        self.update_board(
            clock,
            "g001",
            "self_review_passed",
            evidence=g001["self_review"],
            self_review_attempt_log=g001["self_attempts"],
        )
        self.update_board(
            clock, "g001", "sol_reviewed", evidence=g001["sol_pass"]
        )
        self.update_board(
            clock,
            "g001",
            "approved",
            evidence=evidence,
            release=g001["release"],
            outcome_log=g001["outcomes"],
        )
        self.transition(
            clock,
            action="checkpoint",
            stage="fanout",
            artifact=str(g001["release"]),
        )

        self.update_board(clock, "g002", "queued")
        self.update_board(clock, "g002", "plan_audio_locked", evidence=evidence)
        self.update_board(clock, "g002", "plan_sol_passed", evidence=evidence)
        self.update_board(clock, "g002", "authoring", evidence=evidence)
        for scene in ("g003", "g004", "g005"):
            self.update_board(clock, scene, "queued")
            self.update_board(clock, scene, "plan_audio_locked", evidence=evidence)
            self.update_board(clock, scene, "plan_sol_passed", evidence=evidence)
        self.update_board(clock, "g003", "authoring", evidence=evidence)
        self.update_board(clock, "g004", "authoring", evidence=evidence)
        with self.assertRaisesRegex(pipeline.PipelineError, "3-producer limit"):
            self.update_board(clock, "g005", "authoring", evidence=evidence)

        self.update_board(clock, "g002", "rendered", evidence=evidence)
        self.update_board(clock, "g003", "rendered", evidence=evidence)
        with self.assertRaisesRegex(pipeline.PipelineError, "2-candidate limit"):
            self.update_board(clock, "g004", "rendered", evidence=evidence)

        g002 = self.seal_test_representative_release(episode, clock, "g002")
        self.update_board(
            clock,
            "g002",
            "self_review_passed",
            evidence=g002["self_review"],
            self_review_attempt_log=g002["self_attempts"],
        )
        self.update_board(
            clock, "g002", "sol_reviewed", evidence=g002["sol_pass"]
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError, "human-outcome-log"
        ):
            self.update_board(clock, "g002", "approved", evidence=g002["manifest"])
        self.update_board(
            clock,
            "g002",
            "approved",
            evidence=g002["manifest"],
            outcome_log=g002["outcomes"],
        )
        g002_candidate = episode / "review" / "g002.mp4"
        g002_candidate.write_bytes(b"changed-after-human-review")
        self.assertTrue(
            any(
                "approved candidate is stale" in error
                for error in pipeline.validate_delivery_clock(
                    pipeline.load_json(clock), repo_root=self.root
                )
            )
        )

        g002_candidate.write_bytes(b"representative-candidate")

        with g002["outcomes"].open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "schema": "lecture-animation-outcome-v2",
                        "event_id": "g002-later-human-revise",
                        "scene_slug": "g002",
                        "automatic_verdict": "pass_for_user_review_pending",
                        "human_verdict": "revise",
                        "manifest_hash": pipeline.load_json(
                            g002["manifest"]
                        )["manifest_hash"],
                    }
                )
                + "\n"
            )
        self.assertTrue(
            any(
                "latest human outcome is not a pass" in error
                for error in pipeline.validate_delivery_clock(
                    pipeline.load_json(clock), repo_root=self.root
                )
            )
        )

        issue = episode / "review" / "g002-human-revise.json"
        self.write_json(
            issue,
            {
                "id": "human-g002-reopen",
                "scene_slug": "g002",
                "source": "human_review",
                "status": "open",
                "problem": "The approved candidate needs one bounded visual repair.",
            },
        )
        self.update_board(
            clock,
            "g002",
            "authoring",
            evidence=issue,
            repair_reopen=True,
        )
        reopened = pipeline.load_json(clock)["scene_board"]["g002"]
        self.assertIsNone(reopened["human_approval"])
        self.assertIsNone(reopened["self_review_pass"])
        self.assertIsNone(reopened["sol_candidate_pass"])

        with self.assertRaisesRegex(pipeline.PipelineError, "schedule order"):
            self.transition(
                clock,
                action="checkpoint",
                stage="finalization",
                artifact=str(evidence),
            )
        with g001["outcomes"].open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "schema": "lecture-animation-outcome-v2",
                        "event_id": "g001-later-human-revise",
                        "scene_slug": "g001",
                        "automatic_verdict": "pass_for_user_review_pending",
                        "human_verdict": "revise",
                        "manifest_hash": pipeline.load_json(
                            g001["manifest"]
                        )["manifest_hash"],
                    }
                )
                + "\n"
            )
        self.assertTrue(
            any(
                "representative latest human outcome is not a pass" in error
                for error in pipeline.validate_delivery_clock(
                    pipeline.load_json(clock), repo_root=self.root
                )
            )
        )

    def test_sol_candidate_pass_invalidates_when_review_session_changes(self) -> None:
        episode, clock = self.begin_clock("0107-sol-session")
        bundle = self.seal_test_representative_release(
            episode, clock, "g001"
        )
        session = pipeline.load_json(bundle["review_session"])
        session["post_pass_mutation"] = "must invalidate old Sol pass"
        session.pop("session_hash", None)
        session["session_hash"] = pipeline.object_hash(session)
        self.write_json(bundle["review_session"], session)
        errors = pipeline.sol_candidate_pass_errors(
            pipeline.load_json(bundle["sol_pass"]),
            delivery_clock=pipeline.load_json(clock),
            repo_root=self.root,
            episode_identity=pipeline.relative_or_absolute(
                episode, self.root
            ),
            scene_slug="g001",
        )
        self.assertIn(
            "Sol candidate pass review session bytes are stale", errors
        )

    def test_generic_stale_phase_abandonment_uses_stable_grant_lineage(self) -> None:
        episode, clock = self.begin_clock("0104-abandon")
        efficiency = self.begin_efficiency(episode, clock)
        supervisor_path = episode / "review" / "v2" / "supervisor_session.json"
        supervisor = {
            "schema": "lecture-animation-supervisor-session-v2",
            "session_id": "stable-session-id",
            "supervisor_agent_id": "/root",
            "assignments": {
                "author-1": {
                    "role": "animation_author",
                    "task_key": "batch-a",
                    "scope": "g001",
                    "model": "gpt-5.6-sol",
                    "state": "active",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
            "task_queue": {
                "batch-a": {
                    "state": "active",
                    "current_agent_id": "author-1",
                }
            },
        }
        supervisor["session_hash"] = pipeline.object_hash(supervisor)
        self.write_json(supervisor_path, supervisor)
        grant = pipeline.validate_supervisor_production_grant(
            supervisor, "author-1", "batch-a"
        )
        batch_path = episode / "review" / "v2" / "batch-a.json"
        batch = {
            "schema": "lecture-animation-production-batch-v2",
            "episode": pipeline.relative_or_absolute(episode, self.root),
            "batch_id": "batch-a",
            "scenes": ["g001"],
            "author_id": "author-1",
            "supervisor_binding": {
                **grant,
                "canonical_session_hash": supervisor["session_hash"],
            },
            "supervisor_session_hash": supervisor["session_hash"],
            "grant_hash": grant["grant_hash"],
        }
        batch["batch_hash"] = pipeline.object_hash(batch)
        self.write_json(batch_path, batch)
        state_path = episode / "review" / "active-g001.json"
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(episode),
                    efficiency_contract=str(efficiency),
                    delivery_clock=str(clock),
                    production_batch=str(batch_path),
                    run_id="g001-stale-planning",
                    scene_slug="g001",
                    phase="planning",
                    phase_purpose="lecture_draft",
                    actor_model="gpt-5.6-sol",
                    actor_role="animation_author",
                    reasoning_effort="max",
                    active_seconds_allocation=60,
                    raw_token_allocation=10,
                    uncached_input_token_allocation=1,
                    output_token_allocation=1,
                    reasoning_token_allocation=1,
                    state=str(state_path),
                )
            )

        current = pipeline.load_json(supervisor_path)
        current["assignments"]["author-1"]["last_heartbeat_at"] = (
            datetime.now(timezone.utc) - timedelta(minutes=11)
        ).isoformat()
        current["assignments"]["author-1"]["updated_at"] = current[
            "assignments"
        ]["author-1"]["last_heartbeat_at"]
        current.pop("session_hash", None)
        current["session_hash"] = pipeline.object_hash(current)
        self.assertNotEqual(current["session_hash"], batch["supervisor_session_hash"])
        self.write_json(supervisor_path, current)

        stale_batch = dict(batch)
        stale_batch.pop("batch_hash", None)
        stale_batch["unexpected_mutation"] = True
        stale_batch["batch_hash"] = pipeline.object_hash(stale_batch)
        self.write_json(batch_path, stale_batch)

        phase_log = episode / "review" / "planning.jsonl"
        receipt_path = episode / "review" / "stale-abandonment.json"
        args = SimpleNamespace(
            repo_root=str(self.root),
            state=str(state_path),
            phase_log=str(phase_log),
            supervisor_session=str(supervisor_path),
            agent_id="author-1",
            reason="The stable owner missed heartbeat and direct health probing confirmed no response.",
            checkpoint=None,
            output=str(receipt_path),
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError, "sealed batch lineage"
        ):
            pipeline.command_abandon_stale_phase(args)
        self.write_json(batch_path, batch)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pipeline.command_abandon_stale_phase(args), 0)
            self.assertEqual(pipeline.command_abandon_stale_phase(args), 0)
        receipt = pipeline.load_json(receipt_path)
        self.assertFalse(receipt["token_observed"])
        self.assertIsNone(receipt["token_usage"])
        self.assertEqual(receipt["supervisor_session_id"], "stable-session-id")
        self.assertEqual(
            pipeline.load_json(state_path)["status"], "abandoned"
        )
        ledger = pipeline.load_json(
            pipeline.episode_efficiency_reservation_ledger(
                pipeline.load_json(efficiency)
            )
        )
        self.assertEqual(pipeline.active_reservation_ids(ledger), [])
        self.assertEqual(
            pipeline.load_json(supervisor_path)["assignments"]["author-1"][
                "state"
            ],
            "blocked",
        )
        event = pipeline.event_rows(phase_log)[0]
        self.assertFalse(event["token_observed"])
        self.assertEqual(event["token_source_kind"], "stale_wrapper_unknown")

    def test_observe_history_never_becomes_future_enforced_debt(self) -> None:
        self.assertEqual(
            pipeline.METRIC_POLICY_DEFAULTS["token_budget"]["mode"],
            "enforce",
        )
        episode, clock = self.begin_clock("0105-prospective")
        efficiency_path = self.begin_efficiency(episode, clock)
        contract = pipeline.load_json(efficiency_path)
        observed = {
            "schema": "lecture-animation-phase-event-v2",
            "event_id": "observed-overrun",
            "phase_instance_id": "observed-overrun",
            "phase": "authoring",
            "scene_slug": "g001",
            "result": "completed",
            "started_at": "2026-08-01T00:00:00+00:00",
            "ended_at": "2026-08-01T09:00:00+00:00",
            "duration_seconds": 9 * 3600,
            "input_tokens": 60_000_000,
            "cached_input_tokens": 0,
            "output_tokens": 1,
            "reasoning_tokens": 1,
            "token_observed": True,
            "metric_policy_modes": {
                "active_time": "observe",
                "token_budget": "observe",
            },
        }
        enforced = {
            **observed,
            "event_id": "future-enforced-small",
            "phase_instance_id": "future-enforced-small",
            "started_at": "2026-08-02T00:00:00+00:00",
            "ended_at": "2026-08-02T00:00:01+00:00",
            "duration_seconds": 1,
            "input_tokens": 1,
            "metric_policy_modes": {
                "active_time": "enforce",
                "token_budget": "enforce",
            },
        }
        status = pipeline.efficiency_status_from_rows(
            contract, [observed, enforced]
        )
        self.assertTrue(status["active_exceeded"])
        self.assertTrue(status["token_status"]["exceeded"])
        self.assertFalse(status["enforced_active_exceeded"])
        self.assertFalse(status["enforced_token_status"]["exceeded"])

    def test_close_policy_can_observe_time_but_never_waive_quality(self) -> None:
        episode, clock = self.begin_clock("0106-close-policy")
        efficiency_path = self.begin_efficiency(episode, clock)
        contract = pipeline.load_json(efficiency_path)
        phases = [
            "planning",
            "design",
            "authoring",
            "render",
            "review",
            "tts",
            "asr",
            "finalization",
            "retrospective",
        ]
        base = datetime(2026, 8, 1, tzinfo=timezone.utc)
        cursor = base
        rows = []
        for phase in phases:
            duration = 9 * 3600 if phase == "authoring" else 1
            ended = cursor + timedelta(seconds=duration)
            rows.append(
                {
                    "schema": "lecture-animation-phase-event-v2",
                    "event_id": f"close-policy-{phase}",
                    "phase_instance_id": f"close-policy-{phase}",
                    "phase": phase,
                    "scene_slug": "g001",
                    "result": "completed",
                    "started_at": cursor.isoformat(),
                    "ended_at": ended.isoformat(),
                    "duration_seconds": duration,
                    "input_tokens": 1,
                    "cached_input_tokens": 0,
                    "output_tokens": 1,
                    "reasoning_tokens": 1,
                    "token_observed": True,
                    "task_resource_limits": dict(
                        pipeline.DEFAULT_TASK_RESOURCE_LIMITS
                    ),
                    "token_allocation": {
                        "raw_input_plus_output_tokens": 2,
                        "uncached_input_tokens": 1,
                        "output_tokens": 1,
                        "reasoning_tokens": 1,
                    },
                    "prompt_bytes": 0,
                    "artifact_input_bytes": 0,
                    "files_read": 0,
                }
            )
            cursor = ended
        observe_modes = {
            metric: "observe"
            for metric in pipeline.METRIC_POLICY_DEFINITIONS
        }
        observe_modes["mathematical_truth"] = "enforce"
        observe_modes["novice_causality"] = "enforce"
        observe_modes["independent_review"] = "enforce"
        observe_modes["user_review"] = "enforce"
        clean_production = {
            "missing_phase_pairs_by_scene": {},
            "false_passes": 0,
        }
        human_issues = {
            "scene_rate": 0.0,
            "scenes": [],
            "scene_count": 0,
        }
        evaluation = pipeline.episode_efficiency_close_evaluation(
            contract,
            rows,
            {"g001"},
            clean_production,
            human_issues,
            [],
            observe_modes,
        )
        self.assertIn(
            "EPISODE_ACTIVE_BUDGET_EXCEEDED",
            evaluation["nonblocking_operational_errors"],
        )
        self.assertTrue(evaluation["compliant"])
        self.assertTrue(evaluation["quality_targets_met"])
        self.assertFalse(evaluation["workflow_target_met"])

        quality_failure = pipeline.episode_efficiency_close_evaluation(
            contract,
            rows,
            {"g001"},
            {**clean_production, "false_passes": 1},
            human_issues,
            [],
            observe_modes,
        )
        self.assertIn(
            "AUTOMATIC_FALSE_PASS_TARGET_EXCEEDED",
            quality_failure["quality_errors"],
        )
        self.assertFalse(quality_failure["compliant"])
        self.assertFalse(quality_failure["quality_targets_met"])

    def capacity_replan_fixture(
        self,
        slug: str = "0110-capacity-replan",
    ) -> tuple[Path, Path, Path, Path, str]:
        episode, clock_path = self.begin_clock(slug)
        clock = pipeline.load_json(clock_path)
        owner = "/root/batch-c"
        now = "2026-08-01T00:01:00+00:00"
        clock["scene_board"] = {
            "g010": {
                "state": "queued",
                "owner_agent_id": owner,
                "updated_at": now,
                "evidence": None,
                "history": [],
                "human_approval": None,
                "self_review_pass": None,
                "sol_candidate_pass": None,
                "repair_cycles": 0,
            },
            "g011": {
                "state": "queued",
                "owner_agent_id": owner,
                "updated_at": now,
                "evidence": None,
                "history": [],
                "human_approval": None,
                "self_review_pass": None,
                "sol_candidate_pass": None,
                "repair_cycles": 0,
            },
            "g_other": {
                "state": "queued",
                "owner_agent_id": "/root/other",
                "updated_at": now,
                "evidence": None,
                "history": [],
                "human_approval": None,
                "self_review_pass": None,
                "sol_candidate_pass": None,
                "repair_cycles": 0,
            },
        }
        clock.pop("clock_hash", None)
        clock["clock_hash"] = pipeline.object_hash(clock)
        self.write_json(clock_path, clock)

        sealed_user_authority_path = episode / "review" / "user-authority.json"
        self.write_json(
            sealed_user_authority_path,
            {
                "schema": "lecture-animation-delegated-episode-provisional-animation-authority-v1",
                "episode": clock["episode"],
                "result": "AUTHORIZE_PROVISIONAL_SOURCE_AND_REVIEW_RENDER_FOR_ELIGIBLE_EXACT_PLAN_SCENES",
                "mandatory_provisional_labels": {
                    "human_audio_pending": True,
                    "audio_pass_claim_allowed": False,
                    "render_kind": "provisional_review_candidate",
                    "user_wake_review_required": True,
                    "audio_or_timing_repair_may_require_rerender": True,
                    "final_render_or_authoritative_candidate_claim_allowed": False,
                },
                "strictly_not_authorized": [
                    "claiming human audio PASS",
                    "episode assembly or promotion",
                    "finalization",
                    "stage or commit",
                    "merge or push",
                    "publication or upload",
                ],
            },
        )
        authority_path = episode / "review" / "capacity-authority.json"
        user_authority_snapshot = pipeline.artifact_snapshot(
            sealed_user_authority_path, self.root
        )
        authority = {
            "schema": pipeline.DELIVERY_CAPACITY_REPLAN_AUTHORITY_SCHEMA,
            "episode": clock["episode"],
            "clock_path": pipeline.relative_or_absolute(clock_path, self.root),
            "expected_clock_hash": clock["clock_hash"],
            "owner_agent_id": owner,
            "scene_allowlist": ["g010", "g011"],
            "sealed_user_authority": user_authority_snapshot,
            "expected_sealed_user_authority": user_authority_snapshot,
            "requested_capacity": {"episode": 3, "owner": 2},
            "human_outcome_mutation": False,
            "scene_state_mutation": False,
            "finalization_authorized": False,
            "assembly_authorized": False,
            "git_authorized": False,
            "publication_authorized": False,
            "owner_reassignment_authorized": False,
        }
        authority["authority_hash"] = pipeline.object_hash(authority)
        self.write_json(authority_path, authority)
        inventory_rows = []
        for scene in ("g010", "g011"):
            workflow_path = episode / "review" / scene / "narration_workflow.json"
            release_path = episode / "review" / scene / "release.json"
            release_path.parent.mkdir(parents=True, exist_ok=True)
            workflow_id = f"test-{scene}-workflow"
            self.write_json(
                release_path,
                {
                    "schema": "lecture-animation-narration-animation-release-v1",
                    "workflow_id": workflow_id,
                    "candidate_hash": f"candidate-{scene}",
                    "verdict": "animation_authorized",
                    "human_audio_gate": "user_authorized_machine_pending",
                    "delegated_episode_provisional_authority": {
                        "path": user_authority_snapshot["path"],
                        "sha256": user_authority_snapshot["sha256"],
                    },
                },
            )
            workflow = {
                "schema": "lecture-animation-narration-workflow-v2",
                "workflow_id": workflow_id,
                "episode": clock["episode"],
                "scene_slug": scene,
                "status": "animation_authorized",
                "current_candidate": {
                    "candidate_hash": f"candidate-{scene}"
                },
                "animation_release": pipeline.artifact_snapshot(
                    release_path, self.root
                ),
            }
            workflow["state_hash"] = pipeline.object_hash(workflow)
            self.write_json(workflow_path, workflow)
            inventory_rows.append(
                {
                    "scene_slug": scene,
                    "workflow_status": "animation_authorized",
                    "workflow_path": pipeline.relative_or_absolute(
                        workflow_path, self.root
                    ),
                    "workflow_file_sha256": self.file_sha256(workflow_path),
                    "workflow_state_hash": workflow["state_hash"],
                    "release_path": pipeline.relative_or_absolute(
                        release_path, self.root
                    ),
                    "release_sha256": self.file_sha256(release_path),
                }
            )
        inventory_path = episode / "review" / "authoring-ready-inventory.json"
        self.write_json(
            inventory_path,
            {
                "schema": "lecture-animation-authoring-ready-inventory-v1",
                "episode": clock["episode"],
                "author_agent_id": owner,
                "truth_boundary": {
                    "human_audio_pending": True,
                    "word_alignment_pending": True,
                    "exact_timing_pending": True,
                    "source_created_by_this_inventory": False,
                    "render_started_by_this_inventory": False,
                    "finalization_authorized": False,
                },
                "scenes": inventory_rows,
            },
        )
        pipeline.DELIVERY_CAPACITY_REPLAN_TRUST_ROOTS[clock["episode"]] = {
            "user_authority": pipeline.artifact_snapshot(
                sealed_user_authority_path, self.root
            ),
            "authoring_ready_inventory": pipeline.artifact_snapshot(
                inventory_path, self.root
            ),
        }
        pipeline.DELIVERY_CAPACITY_REPLAN_TRUST_ROOTS[clock["episode"]][
            "user_authority"
        ]["repo_root"] = str(self.root.resolve())
        pipeline.DELIVERY_CAPACITY_REPLAN_TRUST_ROOTS[clock["episode"]][
            "authoring_ready_inventory"
        ]["repo_root"] = str(self.root.resolve())
        output_path = episode / "review" / "capacity-replan.json"
        return episode, clock_path, authority_path, output_path, owner

    def run_capacity_replan(
        self,
        clock_path: Path,
        authority_path: Path,
        output_path: Path,
        owner: str,
        *,
        expected_hash: str | None = None,
    ) -> int:
        current = pipeline.load_json(clock_path)
        authority = pipeline.load_json(authority_path)
        trusted_user_authority = pipeline.resolve_stored_path(
            authority["sealed_user_authority"]["path"], self.root
        )
        trusted_inventory = (
            clock_path.parents[1] / "authoring-ready-inventory.json"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            return pipeline.command_authorize_delivery_capacity_replan(
                SimpleNamespace(
                    repo_root=str(self.root),
                    clock=str(clock_path),
                    expected_clock_hash=expected_hash or current["clock_hash"],
                    authority=str(authority_path),
                    trusted_user_authority=str(trusted_user_authority),
                    trusted_user_authority_sha256=self.file_sha256(
                        trusted_user_authority
                    ),
                    trusted_authoring_ready_inventory=str(trusted_inventory),
                    trusted_authoring_ready_inventory_sha256=self.file_sha256(
                        trusted_inventory
                    ),
                    owner_agent_id=owner,
                    new_max_frozen_candidates=3,
                    new_owner_max_frozen_candidates=2,
                    reason="Release exact provisional authoring capacity only.",
                    output_replan=str(output_path),
                )
            )

    def capacity_trusted_args(
        self, clock_path: Path, authority_path: Path
    ) -> dict[str, str]:
        authority = pipeline.load_json(authority_path)
        trusted_user_authority = pipeline.resolve_stored_path(
            authority["sealed_user_authority"]["path"], self.root
        )
        trusted_inventory = (
            clock_path.parents[1] / "authoring-ready-inventory.json"
        )
        return {
            "trusted_user_authority": str(trusted_user_authority),
            "trusted_user_authority_sha256": self.file_sha256(
                trusted_user_authority
            ),
            "trusted_authoring_ready_inventory": str(trusted_inventory),
            "trusted_authoring_ready_inventory_sha256": self.file_sha256(
                trusted_inventory
            ),
        }

    def test_capacity_replan_is_targeted_monotonic_and_t0_stable(self) -> None:
        _, clock_path, authority_path, output_path, owner = (
            self.capacity_replan_fixture()
        )
        before = pipeline.load_json(clock_path)
        before_initial_hash = pipeline.delivery_clock_initial_hash(before)
        protected = {
            key: before.get(key)
            for key in (
                "scene_board",
                "status",
                "current_stage",
                "representative_scene",
                "representative_release",
                "t0",
                "created_at",
            )
        }

        self.assertEqual(
            self.run_capacity_replan(
                clock_path, authority_path, output_path, owner
            ),
            0,
        )
        after = pipeline.load_json(clock_path)
        self.assertEqual(after["max_frozen_candidates"], 3)
        self.assertEqual(after["max_frozen_candidates_at_t0"], 2)
        self.assertEqual(
            after["frozen_candidate_capacity_by_owner"][owner]["capacity"],
            2,
        )
        self.assertEqual(
            after["frozen_candidate_capacity_by_owner"][owner][
                "scene_allowlist"
            ],
            ["g010", "g011"],
        )
        self.assertEqual(
            pipeline.delivery_clock_initial_hash(after), before_initial_hash
        )
        self.assertEqual(
            {
                key: after.get(key)
                for key in protected
            },
            protected,
        )
        self.assertEqual(
            pipeline.validate_delivery_clock(after, repo_root=self.root), []
        )

        board = after["scene_board"]
        self.assertEqual(
            pipeline.delivery_board_overloaded_frozen_owners(
                after, board, ["g010", "g011"]
            ),
            [],
        )
        self.assertEqual(
            pipeline.delivery_board_overloaded_frozen_owners(
                after, board, ["g010", "g011", "g_other"]
            ),
            [],
        )
        board["g_other_2"] = {
            **board["g_other"],
            "owner_agent_id": "/root/other",
        }
        self.assertEqual(
            pipeline.delivery_board_overloaded_frozen_owners(
                after, board, ["g_other", "g_other_2"]
            ),
            ["/root/other"],
        )
        board["g012"] = {**board["g010"]}
        self.assertEqual(
            pipeline.delivery_board_overloaded_frozen_owners(
                after, board, ["g010", "g012"]
            ),
            [owner],
        )

    def test_capacity_replan_rejects_stale_cross_owner_and_forbidden_scope(self) -> None:
        _, clock_path, authority_path, output_path, owner = (
            self.capacity_replan_fixture("0111-capacity-negative")
        )
        with self.assertRaisesRegex(pipeline.PipelineError, "expected clock hash is stale"):
            self.run_capacity_replan(
                clock_path,
                authority_path,
                output_path,
                owner,
                expected_hash="0" * 64,
            )

        authority = pipeline.load_json(authority_path)
        authority["owner_agent_id"] = "/root/other"
        authority.pop("authority_hash", None)
        authority["authority_hash"] = pipeline.object_hash(authority)
        self.write_json(authority_path, authority)
        with self.assertRaisesRegex(pipeline.PipelineError, "another owner"):
            self.run_capacity_replan(
                clock_path, authority_path, output_path, owner
            )

        authority["owner_agent_id"] = owner
        authority["finalization_authorized"] = True
        authority.pop("authority_hash", None)
        authority["authority_hash"] = pipeline.object_hash(authority)
        self.write_json(authority_path, authority)
        with self.assertRaisesRegex(pipeline.PipelineError, "forbidden mutation"):
            self.run_capacity_replan(
                clock_path, authority_path, output_path, owner
            )

    def test_capacity_replan_rejects_authority_and_output_boundary_failures(self) -> None:
        _, clock_path, authority_path, output_path, owner = (
            self.capacity_replan_fixture("0112-capacity-authority")
        )
        authority = pipeline.load_json(authority_path)
        authority["unexpected_authority_power"] = True
        authority.pop("authority_hash", None)
        authority["authority_hash"] = pipeline.object_hash(authority)
        self.write_json(authority_path, authority)
        with self.assertRaisesRegex(pipeline.PipelineError, "schema is not closed"):
            self.run_capacity_replan(clock_path, authority_path, output_path, owner)

        authority.pop("unexpected_authority_power")
        authority["expected_sealed_user_authority"] = {
            **authority["sealed_user_authority"],
            "sha256": "f" * 64,
        }
        authority.pop("authority_hash", None)
        authority["authority_hash"] = pipeline.object_hash(authority)
        self.write_json(authority_path, authority)
        with self.assertRaisesRegex(pipeline.PipelineError, "binding differs"):
            self.run_capacity_replan(clock_path, authority_path, output_path, owner)

        authority["expected_sealed_user_authority"] = authority[
            "sealed_user_authority"
        ]
        authority.pop("authority_hash", None)
        authority["authority_hash"] = pipeline.object_hash(authority)
        self.write_json(authority_path, authority)
        with self.assertRaisesRegex(pipeline.PipelineError, "paths must be distinct"):
            self.run_capacity_replan(clock_path, authority_path, clock_path, owner)
        with self.assertRaisesRegex(pipeline.PipelineError, "paths must be distinct"):
            self.run_capacity_replan(
                clock_path, authority_path, authority_path, owner
            )
        outside = self.root / "outside-replan.json"
        with self.assertRaisesRegex(pipeline.PipelineError, "episode review"):
            self.run_capacity_replan(clock_path, authority_path, outside, owner)
        output_path.write_text("occupied\n", encoding="utf-8")
        with self.assertRaisesRegex(pipeline.PipelineError, "already exists"):
            self.run_capacity_replan(clock_path, authority_path, output_path, owner)

    def test_capacity_replan_rejects_changed_user_authority_semantics(self) -> None:
        _, clock_path, authority_path, output_path, owner = (
            self.capacity_replan_fixture("0115-capacity-user-authority")
        )
        authority = pipeline.load_json(authority_path)
        user_path = pipeline.resolve_stored_path(
            authority["sealed_user_authority"]["path"], self.root
        )
        user_authority = pipeline.load_json(user_path)
        for field, bad_value, expected_error in (
            ("schema", "wrong-schema", "schema is invalid"),
            ("episode", "videos/wrong", "another episode"),
            ("result", "AUTHORIZE_FINALIZATION", "result is invalid"),
        ):
            original = user_authority[field]
            user_authority[field] = bad_value
            self.write_json(user_path, user_authority)
            snapshot = pipeline.artifact_snapshot(user_path, self.root)
            authority["sealed_user_authority"] = snapshot
            authority["expected_sealed_user_authority"] = snapshot
            authority.pop("authority_hash", None)
            authority["authority_hash"] = pipeline.object_hash(authority)
            self.write_json(authority_path, authority)
            with self.assertRaisesRegex(
                pipeline.PipelineError,
                f"pinned root|{expected_error}",
            ):
                self.run_capacity_replan(
                    clock_path, authority_path, output_path, owner
                )
            user_authority[field] = original

        user_authority["mandatory_provisional_labels"][
            "human_audio_pending"
        ] = False
        self.write_json(user_path, user_authority)
        snapshot = pipeline.artifact_snapshot(user_path, self.root)
        authority["sealed_user_authority"] = snapshot
        authority["expected_sealed_user_authority"] = snapshot
        authority.pop("authority_hash", None)
        authority["authority_hash"] = pipeline.object_hash(authority)
        self.write_json(authority_path, authority)
        with self.assertRaisesRegex(
            pipeline.PipelineError, "pinned root|provisional labels"
        ):
            self.run_capacity_replan(
                clock_path, authority_path, output_path, owner
            )

    def test_capacity_replan_rejects_each_expanded_power(self) -> None:
        for index, field in enumerate(
            (
                "human_outcome_mutation",
                "scene_state_mutation",
                "finalization_authorized",
                "assembly_authorized",
                "git_authorized",
                "publication_authorized",
                "owner_reassignment_authorized",
            )
        ):
            with self.subTest(field=field):
                _, clock_path, authority_path, output_path, owner = (
                    self.capacity_replan_fixture(
                        f"012{index}-capacity-forbidden"
                    )
                )
                authority = pipeline.load_json(authority_path)
                authority[field] = True
                authority.pop("authority_hash", None)
                authority["authority_hash"] = pipeline.object_hash(authority)
                self.write_json(authority_path, authority)
                with self.assertRaisesRegex(
                    pipeline.PipelineError, "forbidden mutation"
                ):
                    self.run_capacity_replan(
                        clock_path, authority_path, output_path, owner
                    )

    def test_capacity_replan_rejects_wrong_episode_scene_and_decrease(self) -> None:
        _, clock_path, authority_path, output_path, owner = (
            self.capacity_replan_fixture("0113-capacity-targets")
        )
        authority = pipeline.load_json(authority_path)
        authority["episode"] = "videos/another-episode"
        authority.pop("authority_hash", None)
        authority["authority_hash"] = pipeline.object_hash(authority)
        self.write_json(authority_path, authority)
        with self.assertRaisesRegex(pipeline.PipelineError, "another episode"):
            self.run_capacity_replan(clock_path, authority_path, output_path, owner)

        clock = pipeline.load_json(clock_path)
        authority["episode"] = clock["episode"]
        authority["scene_allowlist"] = ["g010", "g_other"]
        authority.pop("authority_hash", None)
        authority["authority_hash"] = pipeline.object_hash(authority)
        self.write_json(authority_path, authority)
        with self.assertRaisesRegex(pipeline.PipelineError, "unowned scene"):
            self.run_capacity_replan(clock_path, authority_path, output_path, owner)

        authority["scene_allowlist"] = ["g010", "g011"]
        authority["requested_capacity"] = {"episode": 1, "owner": 1}
        authority.pop("authority_hash", None)
        authority["authority_hash"] = pipeline.object_hash(authority)
        self.write_json(authority_path, authority)
        with self.assertRaisesRegex(pipeline.PipelineError, "monotonic"):
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.command_authorize_delivery_capacity_replan(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        clock=str(clock_path),
                        expected_clock_hash=clock["clock_hash"],
                        authority=str(authority_path),
                        **self.capacity_trusted_args(clock_path, authority_path),
                        owner_agent_id=owner,
                        new_max_frozen_candidates=1,
                        new_owner_max_frozen_candidates=1,
                        reason="Attempt a forbidden capacity decrease now.",
                        output_replan=str(output_path),
                    )
                )

    def test_capacity_replan_is_repeatable_only_with_allowlist_superset(self) -> None:
        _, clock_path, authority_path, output_path, owner = (
            self.capacity_replan_fixture("0114-capacity-repeat")
        )
        self.assertEqual(
            self.run_capacity_replan(clock_path, authority_path, output_path, owner),
            0,
        )
        clock = pipeline.load_json(clock_path)
        clock["scene_board"]["g012"] = {
            **clock["scene_board"]["g010"],
            "owner_agent_id": owner,
        }
        clock.pop("clock_hash", None)
        clock["clock_hash"] = pipeline.object_hash(clock)
        self.write_json(clock_path, clock)
        inventory_path = clock_path.parents[1] / "authoring-ready-inventory.json"
        inventory = pipeline.load_json(inventory_path)
        g010_row = next(
            row for row in inventory["scenes"] if row["scene_slug"] == "g010"
        )
        g012_workflow_path = clock_path.parents[1] / "g012" / "narration_workflow.json"
        g012_release_path = clock_path.parents[1] / "g012" / "release.json"
        g012_release_path.parent.mkdir(parents=True, exist_ok=True)
        user_snapshot = pipeline.load_json(authority_path)[
            "sealed_user_authority"
        ]
        self.write_json(
            g012_release_path,
            {
                "schema": "lecture-animation-narration-animation-release-v1",
                "workflow_id": "test-g012-workflow",
                "candidate_hash": "candidate-g012",
                "verdict": "animation_authorized",
                "human_audio_gate": "user_authorized_machine_pending",
                "delegated_episode_provisional_authority": user_snapshot,
            },
        )
        g012_workflow = {
            "schema": "lecture-animation-narration-workflow-v2",
            "workflow_id": "test-g012-workflow",
            "episode": clock["episode"],
            "scene_slug": "g012",
            "status": "animation_authorized",
            "current_candidate": {"candidate_hash": "candidate-g012"},
            "animation_release": pipeline.artifact_snapshot(
                g012_release_path, self.root
            ),
        }
        g012_workflow["state_hash"] = pipeline.object_hash(g012_workflow)
        self.write_json(g012_workflow_path, g012_workflow)
        inventory["scenes"].append(
            {
                **g010_row,
                "scene_slug": "g012",
                "workflow_path": pipeline.relative_or_absolute(
                    g012_workflow_path, self.root
                ),
                "workflow_file_sha256": self.file_sha256(g012_workflow_path),
                "workflow_state_hash": g012_workflow["state_hash"],
                "release_path": pipeline.relative_or_absolute(
                    g012_release_path, self.root
                ),
                "release_sha256": self.file_sha256(g012_release_path),
            }
        )
        self.write_json(inventory_path, inventory)
        refreshed_inventory_root = pipeline.artifact_snapshot(
            inventory_path, self.root
        )
        refreshed_inventory_root["repo_root"] = str(self.root.resolve())
        pipeline.DELIVERY_CAPACITY_REPLAN_TRUST_ROOTS[clock["episode"]][
            "authoring_ready_inventory"
        ] = refreshed_inventory_root

        second_authority_path = output_path.with_name("capacity-authority-r02.json")
        second_output_path = output_path.with_name("capacity-replan-r02.json")
        authority = pipeline.load_json(authority_path)
        authority["expected_clock_hash"] = clock["clock_hash"]
        authority["scene_allowlist"] = ["g011", "g012"]
        authority["requested_capacity"] = {"episode": 4, "owner": 3}
        authority.pop("authority_hash", None)
        authority["authority_hash"] = pipeline.object_hash(authority)
        self.write_json(second_authority_path, authority)
        with self.assertRaisesRegex(pipeline.PipelineError, "cannot shrink"):
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.command_authorize_delivery_capacity_replan(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        clock=str(clock_path),
                        expected_clock_hash=clock["clock_hash"],
                        authority=str(second_authority_path),
                        **self.capacity_trusted_args(
                            clock_path, second_authority_path
                        ),
                        owner_agent_id=owner,
                        new_max_frozen_candidates=4,
                        new_owner_max_frozen_candidates=3,
                        reason="Expand exact capacity with a monotonic scene scope.",
                        output_replan=str(second_output_path),
                    )
                )

        authority["scene_allowlist"] = ["g010", "g011", "g012"]
        authority.pop("authority_hash", None)
        authority["authority_hash"] = pipeline.object_hash(authority)
        self.write_json(second_authority_path, authority)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_authorize_delivery_capacity_replan(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        clock=str(clock_path),
                        expected_clock_hash=clock["clock_hash"],
                        authority=str(second_authority_path),
                        **self.capacity_trusted_args(
                            clock_path, second_authority_path
                        ),
                        owner_agent_id=owner,
                        new_max_frozen_candidates=4,
                        new_owner_max_frozen_candidates=3,
                        reason="Expand exact capacity with a monotonic scene scope.",
                        output_replan=str(second_output_path),
                    )
                ),
                0,
            )
        after = pipeline.load_json(clock_path)
        self.assertEqual(
            after["frozen_candidate_capacity_by_owner"][owner][
                "scene_allowlist"
            ],
            ["g010", "g011", "g012"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
