#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from pipeline_v2_lib import engine as pipeline
from pipeline_v2_lib.core import PipelineError, object_hash
from pipeline_v2_lib.screen_text_registration import (
    build_screen_text_preregistration,
    commit_screen_text_registration,
    initialize_screen_text_registration,
    reflection_draft_data,
    screen_text_experiment_report,
    screen_text_gate_descriptor,
    screen_text_registration_metrics,
    screen_text_registration_paths,
    seal_screen_text_reflection,
    validate_screen_text_registration_binding,
)
from pipeline_v2_lib.storage import read_jsonl


class ScreenTextRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temporary.name)
        self.episode = self.repo_root / "videos" / "0009-example"
        self.episode.mkdir(parents=True)
        (self.episode / "timeline.json").write_text(
            json.dumps(
                {
                    "scene_groups": [
                        {"id": "G001", "scene_slug": "g001_test", "duration": 20.0}
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        profile = {
            "schema": "lecture-animation-scene-profile-v2",
            "autopilot_contract_version": 8,
            "live_policy_hash": "a" * 64,
            "context": {
                "repo_root": str(self.repo_root),
                "episode": "videos/0009-example",
                "episode_slug": "0009-example",
                "scene_slug": "g001_test",
                "narration": "我们观察圆周上的切向小步怎样改变方向。",
            },
        }
        profile["screen_text_registration_gate"] = screen_text_gate_descriptor(
            profile, self.repo_root
        )
        profile["profile_hash"] = object_hash(profile)
        self.profile = profile

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def candidate(self, payload: str, role: str = "transient_question") -> dict:
        return {
            "constructor": "cn_text",
            "payload": payload,
            "count": 1,
            "role": role,
        }

    def completed_draft(self, preregistration: dict, decision: str) -> dict:
        draft = reflection_draft_data(preregistration)
        draft.update(
            {
                "decision": decision,
                "case_for_keep": "这段文字可能直接指出学习者此刻必须判断的数学关系。",
                "case_for_remove_or_replace": "数学对象本身或更短的局部标注也可能承担同一信息工作。",
                "learner_visible_information": "学习者需要在当前画面辨认奇点与围道收缩之间的关系。",
                "removal_test": "移除后静音观看，检查学习者能否说出当前必须回答的问题。",
                "boundary_analysis": "检查它是在标注数学对象，还是只在描述课程结构和讲解流程。",
            }
        )
        draft["semantic_evidence"] = {
            "unique_visual_job": "把当前需要判断的数学问题固定在奇点和围道旁边。",
            "necessity": "没有这条短问题，静音观看时无法确定围道收缩停下后要解释什么。",
            "removal_failure": "移除后学习者只能看到圆停止，却不能识别当前检验的是奇点造成的阻碍。",
            "clearance_condition": "奇点阻止收缩的动作完成后立即清场。",
            "anchor_type": "learner_question_anchor",
            "anchor_id": "singularity_shrink_question",
            "duplicates_narration": False,
            "externalizes_production_intent": False,
        }
        if decision == "revise":
            draft["revised_payload"] = "奇点为什么挡住围道？"
            draft["revision_reason"] = "改成直接指向数学对象的问题，删除课程流程措辞。"
        if decision == "remove":
            draft["removal_reason"] = "圆与红色奇点的真实动作已经完整承担这条信息。"
        return draft

    def test_preregistration_discloses_risk_without_prejudging(self) -> None:
        preregistration = build_screen_text_preregistration(
            self.profile,
            self.candidate("把这一集的因果链重新走一遍", "scene_title"),
            self.repo_root,
        )
        assessment = preregistration["risk_assessment"]
        self.assertGreater(assessment["signal_count"], 0)
        self.assertEqual(assessment["status"], "reflection_required_not_a_verdict")
        self.assertIn("不是判决", assessment["neutral_disclosure"])
        self.assertIn("keep_hypothesis", assessment)
        self.assertIn("remove_or_replace_hypothesis", assessment)
        draft = reflection_draft_data(preregistration)
        self.assertEqual(
            draft["semantic_evidence"]["duplicates_narration"], "true|false"
        )
        self.assertEqual(
            draft["semantic_evidence"]["externalizes_production_intent"],
            "true|false",
        )

    def test_profile_initialization_represents_zero_visible_literals(self) -> None:
        registry, registry_path, attempt_log, contract_path = (
            initialize_screen_text_registration(self.profile, self.repo_root)
        )
        self.assertEqual(registry["semantic_items"], [])
        self.assertTrue(registry_path.is_file())
        self.assertTrue(attempt_log.is_file())
        rows = read_jsonl(attempt_log)
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["schema"], "lecture-animation-screen-text-scene-observation-v1"
        )
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(contract["registration_registry_hash"], registry["registry_hash"])
        metrics = screen_text_registration_metrics(self.episode, [])
        self.assertEqual(metrics["instrumentation_status"], "observed")
        self.assertEqual(metrics["attempt_count"], 0)
        self.assertEqual(metrics["terminal_coverage"], 1.0)
        self.assertEqual(metrics["scene_gate_coverage"], 1.0)
        self.assertEqual(metrics["zero_candidate_scene_count"], 1)

    def test_compile_profile_and_prepare_cli_expose_the_gate(self) -> None:
        timeline = {
            "scene_groups": [
                {
                    "id": "G001",
                    "scene_slug": "g001_test",
                    "duration": 20.0,
                    "role": "Introduce one learner question.",
                    "math_objects": ["contour", "singularity"],
                    "driver": "radius",
                }
            ],
            "segments": [
                {
                    "id": "S001",
                    "scene_group": "G001",
                    "narration": "我们观察圆为什么不能继续缩小。",
                }
            ],
        }
        (self.episode / "timeline.json").write_text(
            json.dumps(timeline, ensure_ascii=False), encoding="utf-8"
        )
        scene_root = self.episode / "review" / "v2" / "g001_test"
        profile_path = scene_root / "scene_profile.json"
        policy_path = scene_root / "active_policy.json"
        self.assertEqual(
            pipeline.main(
                [
                    "compile-profile",
                    "--repo-root",
                    str(self.repo_root),
                    "--episode",
                    "videos/0009-example",
                    "--scene-slug",
                    "g001_test",
                    "--output",
                    str(profile_path),
                    "--live-policy-output",
                    str(policy_path),
                ]
            ),
            0,
        )
        compiled = json.loads(profile_path.read_text(encoding="utf-8"))
        self.assertEqual(compiled["autopilot_contract_version"], 8)
        registry_path, attempt_log = screen_text_registration_paths(
            compiled, self.repo_root
        )
        self.assertTrue(registry_path.is_file())
        self.assertTrue(attempt_log.is_file())
        preregistration_path = scene_root / "candidate.json"
        self.assertEqual(
            pipeline.main(
                [
                    "prepare-screen-text-registration",
                    "--repo-root",
                    str(self.repo_root),
                    "--profile",
                    str(profile_path),
                    "--constructor",
                    "cn_text",
                    "--payload",
                    "把这一集的因果链重新走一遍",
                    "--role",
                    "scene_title",
                    "--output",
                    str(preregistration_path),
                ]
            ),
            0,
        )
        prepared = json.loads(preregistration_path.read_text(encoding="utf-8"))
        self.assertGreater(prepared["risk_assessment"]["signal_count"], 0)
        self.assertTrue(
            preregistration_path.with_name(
                "candidate.reflection_draft.json"
            ).is_file()
        )

    def test_risk_signalled_keep_requires_counterreflection(self) -> None:
        preregistration = build_screen_text_preregistration(
            self.profile,
            self.candidate("把这一集的因果链重新走一遍", "scene_title"),
            self.repo_root,
        )
        draft = self.completed_draft(preregistration, "keep")
        with self.assertRaisesRegex(PipelineError, "counterreflection"):
            seal_screen_text_reflection(preregistration, draft)

    def test_formal_gate_blocks_producer_intent_after_two_sided_reflection(self) -> None:
        preregistration = build_screen_text_preregistration(
            self.profile,
            self.candidate("把这一集的因果链重新走一遍", "scene_title"),
            self.repo_root,
        )
        draft = self.completed_draft(preregistration, "keep")
        draft["counterreflection"] = {
            "strongest_reason_keep_is_wrong": "它可能只是在告诉观众作者准备总结，而没有提供新的数学信息。",
            "strongest_reason_remove_is_wrong": "如果删掉所有文字，观众可能不知道当前要综合哪些数学关系。",
            "final_decision_after_counterreflection": "keep",
        }
        reflection = seal_screen_text_reflection(preregistration, draft)
        receipt, exit_code = commit_screen_text_registration(
            repo_root=self.repo_root,
            profile=self.profile,
            preregistration=preregistration,
            reflection=reflection,
            output_path=self.episode / "blocked_receipt.json",
        )
        self.assertEqual(exit_code, 2)
        self.assertEqual(receipt["formal_status"], "blocked")
        self.assertTrue(receipt["block_reasons"])
        registry_path, attempt_log = screen_text_registration_paths(
            self.profile, self.repo_root
        )
        self.assertTrue(registry_path.exists())
        rows = read_jsonl(attempt_log)
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(row.get("schema", "").endswith("attempt-v1") for row in rows), 1)

    def test_revision_is_recorded_as_pre_source_prevention(self) -> None:
        preregistration = build_screen_text_preregistration(
            self.profile,
            self.candidate("把这一集的因果链重新走一遍", "scene_title"),
            self.repo_root,
        )
        reflection = seal_screen_text_reflection(
            preregistration, self.completed_draft(preregistration, "revise")
        )
        receipt, exit_code = commit_screen_text_registration(
            repo_root=self.repo_root,
            profile=self.profile,
            preregistration=preregistration,
            reflection=reflection,
            output_path=self.episode / "revision_receipt.json",
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(receipt["formal_status"], "revision_required")
        self.assertIsNone(receipt["screen_text_contract_patch"])
        metrics = screen_text_registration_metrics(self.episode, [])
        self.assertEqual(metrics["prevented_before_source_count"], 1)
        self.assertEqual(metrics["revise_decision_count"], 1)

    def test_legitimate_text_registers_idempotently_and_binds_plan(self) -> None:
        preregistration = build_screen_text_preregistration(
            self.profile,
            self.candidate("奇点为什么会阻止围道收缩？"),
            self.repo_root,
        )
        reflection = seal_screen_text_reflection(
            preregistration, self.completed_draft(preregistration, "keep")
        )
        first, first_code = commit_screen_text_registration(
            repo_root=self.repo_root,
            profile=self.profile,
            preregistration=preregistration,
            reflection=reflection,
            output_path=self.episode / "receipt_1.json",
        )
        second, second_code = commit_screen_text_registration(
            repo_root=self.repo_root,
            profile=self.profile,
            preregistration=preregistration,
            reflection=reflection,
            output_path=self.episode / "receipt_2.json",
        )
        self.assertEqual((first_code, second_code), (0, 0))
        self.assertEqual(first["receipt_hash"], second["receipt_hash"])
        registry_path, attempt_log = screen_text_registration_paths(
            self.profile, self.repo_root
        )
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertEqual(len(registry["semantic_items"]), 1)
        rows = read_jsonl(attempt_log)
        self.assertEqual(
            sum(row.get("schema", "").endswith("registration-attempt-v1") for row in rows),
            1,
        )
        plan = {
            "screen_text_contract": first["screen_text_contract_patch"]
        }
        self.assertEqual(
            validate_screen_text_registration_binding(
                self.profile, plan, self.repo_root
            ),
            [],
        )
        tampered = json.loads(json.dumps(plan))
        tampered["screen_text_contract"]["semantic_items"][0]["payload"] = "篡改"
        self.assertTrue(
            validate_screen_text_registration_binding(
                self.profile, tampered, self.repo_root
            )
        )

    def test_retrospective_experiment_distinguishes_missing_from_zero(self) -> None:
        issues = [
            {
                "source": "human_review",
                "scene_slug": "g001_test",
                "pattern_key": "summary_scene_exposes_production_process_and_persona",
                "affected_visible_payloads": [
                    "把这一集的因果链重新走一遍",
                    "我是结束乐队的键盘手，下个视频见",
                ],
            },
            {
                "source": "human_review",
                "scene_slug": "g001_test",
                "pattern_key": "screen_text_rejection_incorrectly_deleted_requested_spoken_outro",
                "standard_key": "presentation_boundary_scope_misinterpreted",
            },
            {
                "source": "human_review",
                "scene_slug": "g001_test",
                "pattern_key": "screen_text_gate_removed_necessary_learner_text",
                "standard_key": "presentation_boundary_overblock",
            },
        ]
        missing = screen_text_registration_metrics(self.episode, issues)
        self.assertEqual(missing["instrumentation_status"], "unknown_not_instrumented")
        self.assertIsNone(missing["attempt_count"])
        self.assertEqual(missing["human_screen_text_escape_issue_count"], 1)
        self.assertEqual(missing["human_screen_text_escape_payload_count"], 2)
        self.assertEqual(
            missing["human_screen_text_escape_payload_attribution_coverage"], 1.0
        )
        self.assertEqual(missing["human_screen_text_overblock_issue_count"], 1)
        missing_report = screen_text_experiment_report(
            self.episode, issues, Path(__file__).resolve().parents[4]
        )
        self.assertEqual(
            missing_report["comparison"]["status"],
            "unknown_missing_current_instrumentation",
        )
        self.assertIsNone(
            missing_report["comparison"][
                "human_screen_text_escape_issue_delta"
            ]
        )
        self.assertIsNone(
            missing_report["comparison"]["pre_source_prevention_count"]
        )
        preregistration = build_screen_text_preregistration(
            self.profile,
            self.candidate("奇点为什么会阻止围道收缩？"),
            self.repo_root,
        )
        reflection = seal_screen_text_reflection(
            preregistration, self.completed_draft(preregistration, "keep")
        )
        commit_screen_text_registration(
            repo_root=self.repo_root,
            profile=self.profile,
            preregistration=preregistration,
            reflection=reflection,
            output_path=self.episode / "receipt.json",
        )
        report = screen_text_experiment_report(
            self.episode, [], Path(__file__).resolve().parents[4]
        )
        self.assertEqual(report["status"], "target_met")
        self.assertEqual(report["current"]["registered_count"], 1)
        self.assertEqual(
            report["baseline"]["decision_gate_instrumentation_status"],
            "unknown_not_instrumented",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
