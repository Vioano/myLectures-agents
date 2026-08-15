#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import concurrent.futures
from datetime import datetime, timedelta
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import wave

from PIL import Image, ImageDraw

from pipeline_v2_lib.episode_ops import (
    _canonical_formal_occurrence_count,
    _formal_occurrence_count,
    run_episode_preflight,
)
from pipeline_v2_lib import engine as pipeline_engine


MODULE_PATH = Path(__file__).with_name("pipeline_v2.py")
SPEC = importlib.util.spec_from_file_location("pipeline_v2", MODULE_PATH)
assert SPEC and SPEC.loader
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


class PipelineV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_episode = self.root / "videos" / "0001-old-projection"
        self.episode = self.root / "videos" / "0002-limit"
        self.old_episode.mkdir(parents=True)
        self.episode.mkdir(parents=True)
        self._write_old_history()
        self._write_current_episode()
        self.efficiency_contract = (
            self.episode
            / "review"
            / "evolution"
            / "episode_efficiency_contract.json"
        )
        efficiency = pipeline.episode_efficiency_contract_data(
            self.root,
            self.episode,
            SimpleNamespace(
                episode_target_hours=8.0,
                retrospective_reserve_minutes=45.0,
                raw_token_budget=50_000_000,
                uncached_input_token_budget=2_000_000,
                output_token_budget=300_000,
                reasoning_token_budget=100_000,
                token_budget_warning_fraction=0.75,
                max_false_passes=0,
                max_known_regression_recurrences=0,
                max_human_issue_scene_rate=0.25,
            ),
        )
        self.write_json(self.efficiency_contract, efficiency)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_rule_registry_blocks_incomplete_final_media_coverage(self) -> None:
        rules = {
            rule["rule_id"]: rule
            for rule in pipeline.load_rules()["rules"]
        }
        rule = rules["ART-002"]
        self.assertEqual(rule["severity"], "blocker")
        self.assertIn("last aligned word", rule["requirement"])
        self.assertIn("Decoder EOF", rule["requirement"])
        self.assertIn(
            "final_assembly_video_stream_truncated_after_scene",
            rule["source_patterns"],
        )

    def test_git_state_consolidation_trigger_keeps_canonical_media_contract(
        self,
    ) -> None:
        skill_root = Path(__file__).resolve().parents[1]
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        handoff_text = (
            skill_root
            / "references/preflight-portability-and-handoffs.md"
        ).read_text(encoding="utf-8")
        for required in (
            "整理 Git 状态",
            "/Volumes/bocchi/myLectures",
            "audit-portability --require-clean",
            "remove the current task's producer and integration worktrees",
            "does not authorize push",
        ):
            self.assertIn(required, skill_text)
        self.assertIn("temporary worktree", handoff_text)
        self.assertIn("not the canonical", handoff_text)

    def test_skill_entrypoint_is_compact_phase_router_with_cold_history(self) -> None:
        skill_root = Path(__file__).resolve().parents[1]
        skill_path = skill_root / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")
        self.assertLessEqual(skill_path.stat().st_size, 24 * 1024)
        for required in (
            "Load Only The Active Phase",
            "Eight-Hour Delivery Contract",
            "quality_gates",
            "user_review",
            "references/eight-hour-production.md",
            "references/historical-episode-continuations.md",
        ):
            self.assertIn(required, skill_text)
        self.assertNotIn("For the historical Episode 8", skill_text)
        self.assertNotIn("Episode 9 has one evidence-preserving", skill_text)
        for reference in (
            "orchestration-and-supervision.md",
            "progressive-planning-and-audio.md",
            "autopilot-efficiency.md",
            "historical-episode-continuations.md",
            "scene-production-and-review.md",
            "finalization-evolution-retrospective.md",
            "eight-hour-production.md",
        ):
            self.assertTrue((skill_root / "references" / reference).is_file())

    def test_pronunciation_count_keeps_adjacent_unicode_greek_tokens(self) -> None:
        narration = r"e^{iθ} dθ，θ，theta，\theta；alphabet 不应命中。"
        self.assertEqual(_formal_occurrence_count(narration, "theta"), 5)
        self.assertEqual(_formal_occurrence_count(narration, "alpha"), 0)

    def test_registry_longest_match_keeps_composite_pronunciation_identities(self) -> None:
        registry = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "references/tts-pronunciation-registry.json"
            ).read_text(encoding="utf-8")
        )
        narration = "Res f 与 f 同时出现；i d theta 和 theta 各出现一次。"
        self.assertEqual(
            _canonical_formal_occurrence_count(narration, "res f", registry),
            1,
        )
        self.assertEqual(
            _canonical_formal_occurrence_count(narration, "f", registry),
            1,
        )
        self.assertEqual(
            _canonical_formal_occurrence_count(narration, "i d theta", registry),
            1,
        )
        self.assertEqual(
            _canonical_formal_occurrence_count(narration, "theta", registry),
            1,
        )

    def test_episode_preflight_requires_per_scene_pronunciation_bindings(self) -> None:
        scene_rows = []
        registry_source = (
            Path(__file__).resolve().parents[1]
            / "references/tts-pronunciation-registry.json"
        )
        registry_path = (
            self.root
            / ".agents/skills/lecture-animation-pipeline/references/tts-pronunciation-registry.json"
        )
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            registry_source.read_text(encoding="utf-8"), encoding="utf-8"
        )
        route_id = "indextts2-mlx8-zaojian-takagi-seed3407"
        for slug, narration_text in (
            ("g001", "令参数 θ 从零开始。"),
            ("g002", "再让 θ 走完一圈。小圈积分究竟读取了什么？"),
        ):
            scene_root = self.episode / "src" / slug
            source = scene_root / "scene.py"
            narration = self.episode / "review" / "v2" / slug / "narration.txt"
            tts_input = self.episode / "review" / "v2" / slug / "tts_input.txt"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("from manim import *\n", encoding="utf-8")
            narration.parent.mkdir(parents=True, exist_ok=True)
            narration.write_text(narration_text, encoding="utf-8")
            tts_input.write_text(narration_text.replace("θ", "theta"), encoding="utf-8")
            mapping = narration.with_name("tts_input_mapping.json")
            theta_start = narration_text.index("θ")
            mapping.write_text(
                json.dumps(
                    {
                        "schema": "lecture-animation-tts-input-mapping-v2",
                        "scene_slug": slug,
                        "route_id": route_id,
                        "formal_script_path": pipeline.relative_or_absolute(
                            narration, self.root
                        ),
                        "formal_script_sha256": hashlib.sha256(
                            narration.read_bytes()
                        ).hexdigest(),
                        "tts_input_path": pipeline.relative_or_absolute(
                            tts_input, self.root
                        ),
                        "tts_input_sha256": hashlib.sha256(
                            tts_input.read_bytes()
                        ).hexdigest(),
                        "occurrences": [
                            {
                                "token_key": "theta",
                                "formal_start": theta_start,
                                "formal_end": theta_start + 1,
                                "formal_surface": "θ",
                                "occurrence_index": 1,
                                "spoken_form": "theta",
                                "replacement_applied": True,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            scene_rows.append(
                {
                    "scene_slug": slug,
                    "scene_source_path": pipeline.relative_or_absolute(source, self.root),
                    "scene_source_root": pipeline.relative_or_absolute(scene_root, self.root),
                    "narration_path": pipeline.relative_or_absolute(narration, self.root),
                    "tts_input_path": pipeline.relative_or_absolute(tts_input, self.root),
                    "tts_input_mapping_path": pipeline.relative_or_absolute(
                        mapping, self.root
                    ),
                    "duration_seconds": 8.0,
                }
            )
        contract = {
            "schema": "lecture-animation-episode-readiness-v2",
            "readiness_stage": "pre_tts",
            "author_id": "pronunciation-author",
            "tts_route_id": route_id,
            "pronunciation_registry_path": pipeline.relative_or_absolute(
                registry_path, self.root
            ),
            "fixed_ending": "小圈积分究竟读取了什么？",
            "fixed_ending_contract": {
                "role": "learner_facing_math_question",
                "learner_job": "Leave the learner with one precise unresolved mathematical question.",
                "math_anchor": "small-contour integral",
                "externalizes_production_intent": False,
            },
            "sensitive_tokens": ["theta"],
            "pronunciation_map": {
                "theta": {
                    "bindings": [
                        {
                            "scene_slug": row["scene_slug"],
                            "spoken_form": "theta",
                            "tts_input_path": pipeline.relative_or_absolute(
                                self.episode / "review" / "v2" / row["scene_slug"] / "tts_input.txt",
                                self.root,
                            ),
                            "occurrences": 1,
                            "route_id": route_id,
                        }
                        for row in scene_rows
                    ]
                }
            },
            "scenes": scene_rows,
        }
        result = run_episode_preflight(self.root, self.episode, contract)
        self.assertEqual(result["status"], "pass", result["errors"])
        self.assertEqual(
            [row["scene_slug"] for row in result["pronunciation_evidence"]["theta"]["bindings"]],
            ["g001", "g002"],
        )

        single_binding = dict(contract)
        single_binding["pronunciation_map"] = {
            "theta": contract["pronunciation_map"]["theta"]["bindings"][0]
        }
        blocked = run_episode_preflight(self.root, self.episode, single_binding)
        self.assertEqual(blocked["status"], "blocked")
        self.assertTrue(
            any(
                "spans multiple scenes and requires one evidence object per scene" in error
                for error in blocked["errors"]
            )
        )

    def test_post_tts_episode_preflight_requires_exact_screen_text_semantics(self) -> None:
        scene_root = self.episode / "src" / "g001"
        source = scene_root / "scene.py"
        narration = self.episode / "review" / "v2" / "g001" / "narration.txt"
        semantics = (
            self.episode
            / "review"
            / "v2"
            / "g001"
            / "screen_text_semantic_contract.json"
        )
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            'from manim import *\nquestion = Text("积分读取什么？")\n',
            encoding="utf-8",
        )
        narration.parent.mkdir(parents=True, exist_ok=True)
        narration.write_text(
            "围道已经缩到奇点附近。积分究竟读取了什么？",
            encoding="utf-8",
        )
        base_contract = {
            "schema": "lecture-animation-episode-readiness-v2",
            "readiness_stage": "post_tts",
            "author_id": "screen-text-author",
            "fixed_ending": "积分究竟读取了什么？",
            "fixed_ending_contract": {
                "role": "learner_facing_math_question",
                "learner_job": "Leave the learner with one precise mathematical question.",
                "math_anchor": "small-contour integral",
                "externalizes_production_intent": False,
            },
            "scenes": [
                {
                    "scene_slug": "g001",
                    "scene_source_path": pipeline.relative_or_absolute(source, self.root),
                    "scene_source_root": pipeline.relative_or_absolute(scene_root, self.root),
                    "narration_path": pipeline.relative_or_absolute(narration, self.root),
                    "duration_seconds": 12.0,
                    "screen_text_inventory": [
                        {
                            "text": "积分读取什么？",
                            "source_path": pipeline.relative_or_absolute(source, self.root),
                        }
                    ],
                    "screen_text_count": 1,
                }
            ],
        }
        missing = run_episode_preflight(self.root, self.episode, base_contract)
        self.assertEqual(missing["status"], "blocked")
        self.assertTrue(
            any(
                "screen_text_semantic_contract_path" in error
                for error in missing["errors"]
            )
        )

        self.write_json(
            semantics,
            {
                "schema": "lecture-animation-screen-text-semantic-contract-v1",
                "semantic_items": [
                    {
                        "constructor": "Text",
                        "payload": "积分读取什么？",
                        "count": 1,
                        "role": "transient_question",
                        "unique_visual_job": "Name the unresolved quantity beside the small contour.",
                        "necessity": "The learner needs one explicit target while the contour contracts.",
                        "removal_failure": "Without it the final unknown is detached from the visible contour.",
                        "learner_question_anchor": "small-contour integral",
                        "clearance_condition": "Hold to scene end.",
                        "duplicates_narration": False,
                        "externalizes_production_intent": False,
                    }
                ],
            },
        )
        exact_contract = json.loads(json.dumps(base_contract))
        exact_contract["scenes"][0]["screen_text_semantic_contract_path"] = (
            pipeline.relative_or_absolute(semantics, self.root)
        )
        passed = run_episode_preflight(self.root, self.episode, exact_contract)
        self.assertEqual(passed["status"], "pass", passed["errors"])

        drifted = json.loads(json.dumps(exact_contract))
        drifted["scenes"][0]["screen_text_inventory"][0]["text"] = "另一句话"
        blocked = run_episode_preflight(self.root, self.episode, drifted)
        self.assertEqual(blocked["status"], "blocked")

    def test_strict_self_review_probes_span_full_scene_and_claim_sequence(self) -> None:
        duration = 110.0
        plan = {
            "stage_regions": [
                {"name": "left", "primary_object": "signal"},
                {"name": "right", "primary_object": "formula"},
            ],
            "stage_states": [
                {
                    "id": "opening",
                    "start": 0.0,
                    "end": 8.0,
                    "active_regions": [{"region": "left"}],
                },
                {
                    "id": "ending",
                    "start": 96.0,
                    "end": 110.0,
                    "active_regions": [{"region": "right"}],
                },
            ],
            "stage_transitions": [
                {"start": 7.5, "end": 8.5},
                {"start": 95.0, "end": 97.0},
            ],
            "math_object_invariants": [
                {"invariant_id": "opening-signal", "object_id": "signal", "checkpoints": [2.0]},
                {"invariant_id": "ending-formula", "object_id": "formula", "checkpoints": [104.0]},
            ],
            "clause_locks": [
                {"cue_id": "opening-clause", "object_id": "signal", "spoken_start": 1.0},
                {"cue_id": "ending-clause", "object_id": "formula", "spoken_start": 103.0},
            ],
            "beats": [
                {"beat_id": "opening-beat", "start": 0.0, "end": 6.0, "pointing_target_ids": ["signal"]},
                {"beat_id": "ending-beat", "start": 100.0, "end": 110.0, "pointing_target_ids": ["formula"]},
            ],
        }
        profile = {"tags": ["human_rejected"], "context": {"duration": duration}}
        manifest = {
            "manifest_hash": "strict-manifest",
            "scene_slug": "g010_strict_span",
            "artifacts": {"review_mp4": {"sha256": "review-sha"}},
        }

        draft = pipeline.self_review_probe_draft_data(manifest, profile, plan)
        by_layer: dict[str, list[dict[str, object]]] = {}
        for probe in draft["probes"]:
            by_layer.setdefault(str(probe["layer"]), []).append(probe)

        self.assertEqual(draft["minimum_probes_per_layer"], 2)
        all_selected_times = [
            float(probe["timestamp_seconds"]) for probe in draft["probes"]
        ]
        self.assertEqual(len(all_selected_times), len(set(all_selected_times)))
        for layer in pipeline.HARD_GATE_LAYERS:
            self.assertEqual(len(by_layer[layer]), 2)
            selected_times = [float(probe["timestamp_seconds"]) for probe in by_layer[layer]]
            self.assertLess(selected_times[0], duration / 3)
            self.assertGreater(selected_times[-1], duration * 2 / 3)

        self.assertEqual(
            [probe["claim_id"] for probe in by_layer["layout"]],
            ["stage-state:opening", "stage-state:ending"],
        )
        self.assertEqual(
            [probe["claim_id"] for probe in by_layer["math_object"]],
            ["math:opening-signal", "math:ending-formula"],
        )
        self.assertEqual(
            [probe["claim_id"] for probe in by_layer["timing_attention"]],
            ["clause-lock:opening-clause", "clause-lock:ending-clause"],
        )
        self.assertEqual(
            [probe["claim_id"] for probe in by_layer["novice_causality"]],
            ["beat:opening-beat", "beat:ending-beat"],
        )

        session = {
            "contract_version": pipeline.REVIEW_SESSION_CONTRACT_VERSION,
            "reviewer": "main-agent",
            "reviewer_model": "gpt-5-codex",
            "reasoning_effort": "xhigh",
            "reviewer_agent_id": "/root",
        }
        capsule = pipeline.review_capsule_data(manifest, profile, plan, session, {})
        challenge_times = [
            float(challenge["timestamp_seconds"]) for challenge in capsule["blind_challenges"]
        ]
        self.assertEqual(len(challenge_times), 3)
        self.assertLess(challenge_times[0], duration / 3)
        self.assertGreater(challenge_times[-1], duration * 2 / 3)
        self.assertEqual(challenge_times, sorted(challenge_times))

        plan_with_empty_beat = json.loads(json.dumps(plan))
        plan_with_empty_beat["beats"][0]["pointing_target_ids"] = []
        novice_claims = pipeline.self_review_claims(plan_with_empty_beat, "novice_causality")
        self.assertTrue(all(claim["object_ids"] for claim in novice_claims))
        self.assertNotIn("beat:opening-beat", [claim["claim_id"] for claim in novice_claims])

        plan_with_out_of_order_invariants = json.loads(json.dumps(plan))
        plan_with_out_of_order_invariants["math_object_invariants"] = [
            {
                "invariant_id": "late-surface",
                "object_id": "formula",
                "checkpoints": [82.0, 90.0, 96.0],
            },
            {
                "invariant_id": "early-kernel",
                "object_id": "signal",
                "checkpoints": [20.0, 25.0, 31.0],
            },
        ]
        paired_draft = pipeline.self_review_probe_draft_data(
            manifest, profile, plan_with_out_of_order_invariants
        )
        paired_math = [
            probe
            for probe in paired_draft["probes"]
            if probe["layer"] == "math_object"
        ]
        self.assertEqual(
            [
                (probe["claim_id"], probe["timestamp_seconds"])
                for probe in paired_math
            ],
            [("math:early-kernel", 20.0), ("math:late-surface", 96.0)],
        )

    def test_profile_uses_precise_scene_timing_when_coarse_timeline_is_null(self) -> None:
        timeline_path = self.episode / "timeline.json"
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        group = next(
            item
            for item in timeline["scene_groups"]
            if item["scene_slug"] == "g002c_riemann_sum_limit"
        )
        group["start"] = None
        group["end"] = None
        group["duration"] = None
        self.write_json(timeline_path, timeline)
        fragment = (
            self.episode
            / "review"
            / "v2"
            / "g002c_riemann_sum_limit"
            / "timeline_fragment.json"
        )
        self.write_json(
            fragment,
            {
                "schema": "scene-word-anchored-timeline-v2",
                "scene": "g002c_riemann_sum_limit",
                "audio_duration": 42.25,
                "duration_seconds": 42.75,
                "scene_duration_seconds": 43.1,
                "render_end": 43.0,
            },
        )

        profile = pipeline.compile_profile_data(
            self.root,
            self.episode,
            "g002c_riemann_sum_limit",
        )
        self.assertEqual(profile["context"]["start"], 0.0)
        self.assertEqual(profile["context"]["end"], 43.1)
        self.assertEqual(profile["context"]["duration"], 43.1)
        self.assertTrue(
            str(profile["context"]["timing_source"]).endswith(
                "review/v2/g002c_riemann_sum_limit/timeline_fragment.json"
            )
        )
        self.assertTrue(profile["context"]["timing_fragment_hash"])

    def test_profile_uses_precise_scene_timing_when_group_is_explicitly_provisional(self) -> None:
        timeline_path = self.episode / "timeline.json"
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        group = next(
            item
            for item in timeline["scene_groups"]
            if item["scene_slug"] == "g002c_riemann_sum_limit"
        )
        group["duration"] = 90.0
        group["planning_status"] = "provisional"
        self.write_json(timeline_path, timeline)
        fragment = (
            self.episode
            / "review"
            / "v2"
            / "g002c_riemann_sum_limit"
            / "timeline_fragment.json"
        )
        self.write_json(
            fragment,
            {
                "schema": "scene-word-anchored-timeline-v2",
                "scene": "g002c_riemann_sum_limit",
                "audio_duration": 42.25,
                "duration_seconds": 42.75,
                "scene_duration_seconds": 43.1,
                "render_end": 43.0,
            },
        )

        profile = pipeline.compile_profile_data(
            self.root,
            self.episode,
            "g002c_riemann_sum_limit",
        )
        self.assertEqual(profile["context"]["start"], 0.0)
        self.assertEqual(profile["context"]["end"], 43.1)
        self.assertEqual(profile["context"]["duration"], 43.1)
        self.assertTrue(
            str(profile["context"]["timing_source"]).endswith(
                "review/v2/g002c_riemann_sum_limit/timeline_fragment.json"
            )
        )
        self.assertTrue(profile["context"]["timing_fragment_hash"])

    def test_profile_prefers_exact_scene_local_narration_and_detects_spoken_variants(self) -> None:
        timeline_path = self.episode / "timeline.json"
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        group = next(
            item
            for item in timeline["scene_groups"]
            if item["scene_slug"] == "g002c_riemann_sum_limit"
        )
        for segment in timeline.get("segments", []):
            if segment.get("scene_group") == group["id"]:
                segment["narration"] = ""
        self.write_json(timeline_path, timeline)
        fragment = (
            self.episode
            / "review"
            / "v2"
            / "g002c_riemann_sum_limit"
            / "timeline_fragment.json"
        )
        self.write_json(
            fragment,
            {
                "schema": "scene-word-anchored-timeline-v2",
                "scene_slug": "g002c_riemann_sum_limit",
                "scene_duration_seconds": 43.1,
                "word_anchors": [
                    {
                        "anchor_id": "bend",
                        "start": 1.0,
                        "end": 2.0,
                        "text": "方格边逐点弯成曲线。",
                    },
                    {
                        "anchor_id": "reflect",
                        "start": 3.0,
                        "end": 4.0,
                        "text": "红边翻到下方，黄点跟着镜像。",
                    },
                ],
            },
        )

        profile = pipeline.compile_profile_data(
            self.root,
            self.episode,
            "g002c_riemann_sum_limit",
        )
        self.assertIn("逐点弯成曲线", profile["context"]["narration"])
        self.assertTrue(
            str(profile["context"]["narration_source"]).endswith(
                "review/v2/g002c_riemann_sum_limit/timeline_fragment.json#word_anchors"
            )
        )
        mentions = pipeline.narrated_action_mentions(profile["context"]["narration"])
        self.assertEqual(
            [(item["spoken_token"], item["action_kind"]) for item in mentions],
            [("弯成", "bend"), ("翻到", "reflect"), ("镜像", "reflect")],
        )

    def test_profile_prefers_approved_narration_artifact_over_anchor_summary(self) -> None:
        narration_dir = (
            self.episode
            / "review"
            / "v2"
            / "g002c_riemann_sum_limit"
            / "narration"
        )
        narration_dir.mkdir(parents=True, exist_ok=True)
        script = narration_dir / "script.md"
        script.write_text("同一个方形先旋转，再等比例伸缩。", encoding="utf-8")
        fragment = narration_dir / "timeline_fragment.json"
        self.write_json(
            fragment,
            {
                "schema": "lecture-animation-exact-scene-timeline-fragment-v1",
                "scene_slug": "g002c_riemann_sum_limit",
                "scene_duration_seconds": 43.1,
                "artifacts": {
                    "approved_narration": {
                        "path": pipeline.relative_or_absolute(script, self.root),
                    }
                },
                "word_anchors": [
                    {"anchor_id": "summary", "text": "这只是摘要，不是权威口播。"}
                ],
            },
        )

        profile = pipeline.compile_profile_data(
            self.root,
            self.episode,
            "g002c_riemann_sum_limit",
        )
        self.assertEqual(profile["context"]["narration"], "同一个方形先旋转，再等比例伸缩。")
        self.assertEqual(
            profile["context"]["narration_source"],
            pipeline.relative_or_absolute(script, self.root),
        )

    def test_narrated_action_mentions_cover_common_spoken_transform_synonyms(self) -> None:
        mentions = pipeline.narrated_action_mentions(
            "它先旋转，再等比缩放；不能只沿一个方向拉长。"
        )
        self.assertEqual(
            [
                (item["spoken_token"], item["action_kind"])
                for item in mentions
            ],
            [
                ("旋转", "rotate"),
                ("等比缩放", "uniform_scale"),
                ("拉长", "anisotropic_scale"),
            ],
        )

    def test_profile_retains_provisional_group_duration_before_fragment_exists(self) -> None:
        timeline_path = self.episode / "timeline.json"
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        group = next(
            item
            for item in timeline["scene_groups"]
            if item["scene_slug"] == "g002c_riemann_sum_limit"
        )
        group["duration"] = 90.0
        group["planning_status"] = "provisional"
        self.write_json(timeline_path, timeline)

        profile = pipeline.compile_profile_data(
            self.root,
            self.episode,
            "g002c_riemann_sum_limit",
        )
        self.assertEqual(profile["context"]["duration"], 90.0)
        self.assertEqual(
            profile["context"]["timing_source"],
            "timeline.scene_groups:provisional_fallback",
        )
        self.assertIsNone(profile["context"]["timing_fragment_hash"])

    def test_issue_tag_hits_are_sorted_for_reproducible_profile_hashes(self) -> None:
        hits = pipeline.issue_tag_hits(
            "complex formula integral transition",
            {"stage_dense", "formula_dense", "complex", "limit_process"},
        )
        self.assertEqual(hits, sorted(hits))

    def test_live_policy_semantic_hash_ignores_omitted_advisory_count(self) -> None:
        profile = pipeline.compile_profile_data(
            self.root,
            self.episode,
            "g002c_riemann_sum_limit",
        )
        policy = pipeline.compile_live_policy_data(self.episode, profile)
        legacy = json.loads(json.dumps(policy))
        legacy["implicit_advisory_matches_omitted"] = (
            int(legacy.get("implicit_advisory_matches_omitted", 0)) + 7
        )
        legacy_payload = dict(legacy)
        legacy_payload.pop("policy_hash", None)
        legacy["policy_hash"] = pipeline.object_hash(legacy_payload)

        self.assertTrue(pipeline.validate_live_policy_hash(policy))
        self.assertTrue(pipeline.validate_live_policy_hash(legacy))
        self.assertEqual(
            pipeline.live_policy_semantic_hash(policy),
            pipeline.live_policy_semantic_hash(legacy),
        )

    def test_scene_complexity_gate_blocks_unstructured_scene_above_ninety_seconds(self) -> None:
        profile = {"context": {"duration": 99.7}}
        plan: dict[str, object] = {}
        blocked = pipeline.scene_complexity_gate_data(profile, plan)
        self.assertEqual(blocked["status"], "split_required")
        self.assertTrue(blocked["exception_errors"])

        plan["scene_split_exception"] = {
            "reason": "One identity-preserving comparison must remain simultaneous across the complete representation chain.",
            "internal_sections": [
                {"section_id": "projection", "stage_state_ids": ["projection-state"]},
                {"section_id": "operator", "stage_state_ids": ["operator-state"]},
            ],
            "clearance_checkpoints": ["projection-to-operator-clearance"],
            "novice_continuity_reason": "Splitting would hide that the same function identity survives the representation change.",
        }
        accepted = pipeline.scene_complexity_gate_data(profile, plan)
        self.assertEqual(accepted["status"], "exception_accepted")
        self.assertEqual(accepted["exception_errors"], [])

    def test_outcomes_deduplicate_and_finalize_episode_closes_state_atomically(self) -> None:
        episode = self.root / "videos" / "0003-finalize"
        episode.mkdir(parents=True)
        notes = episode / "lecture.md"
        outline = episode / "outline.md"
        storyboard = episode / "storyboard.md"
        for path, payload in (
            (notes, "lecture truth\n"),
            (outline, "narration outline\n"),
            (storyboard, "coarse storyboard\n"),
        ):
            path.write_text(payload, encoding="utf-8")
        exact: dict[str, Path] = {}
        for key in pipeline.SCENE_EXACT_ARTIFACTS:
            path = episode / "scene" / f"{key}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
            exact[key] = path
        production_source = {
            "schema": "lecture-animation-progressive-production-v2",
            "episode": pipeline.relative_or_absolute(episode, self.root),
            "lecture_notes": {"path": pipeline.relative_or_absolute(notes, self.root)},
            "narration_outline": {
                "path": pipeline.relative_or_absolute(outline, self.root),
                "status": "outline_draft",
            },
            "storyboard": {
                "path": pipeline.relative_or_absolute(storyboard, self.root),
                "status": "coarse",
            },
            "scenes": [
                {
                    "scene_slug": "g001_finalize",
                    "state": "audio_aligned",
                    "narration_intent": "Close one fully approved scene with durable state evidence.",
                    "duration_seconds": 12.0,
                    "artifacts": {
                        key: {"path": pipeline.relative_or_absolute(path, self.root)}
                        for key, path in exact.items()
                    },
                }
            ],
            "assembly": {"status": "pending", "artifacts": {}},
        }
        production = pipeline.seal_progressive_production_data(production_source, self.root)
        production_path = episode / "progressive_production.json"
        self.write_json(production_path, production)
        issue_path = episode / "review" / "issues" / "closed.json"
        self.write_json(issue_path, {"id": "closed", "status": "verified_fixed"})
        event_log = episode / "review" / "evolution" / "events.jsonl"
        outcome_args = SimpleNamespace(
            episode=str(episode),
            event_log=str(event_log),
            review_session=None,
            scene_slug="g001_finalize",
            author_model="author-model",
            reviewer_model="reviewer-model",
            automatic_verdict="pass_for_user_review_pending",
            human_verdict="pass",
            caught_by="reviewer",
            pattern_key=[],
            review_rounds=2,
            reviewer_findings=1,
            machine_failures=0,
            human_findings=0,
            render_count=2,
            minutes=20.0,
            manifest_hash="manifest-final",
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pipeline.command_record_outcome(outcome_args), 0)
            self.assertEqual(pipeline.command_record_outcome(outcome_args), 0)
        self.assertEqual(len(pipeline.read_jsonl(event_log)), 1)

        final_paths: dict[str, Path] = {}
        for key in (
            "final_video",
            "final_audio",
            "final_srt",
            "final_word_srt",
            "final_word_alignment",
            "final_timeline",
        ):
            path = episode / "final" / f"{key}.artifact"
            path.parent.mkdir(parents=True, exist_ok=True)
            if key == "final_word_alignment":
                self.write_json(
                    path,
                    {
                        "schema": "test-alignment",
                        "aligned_tokens": [
                            {"text": "数", "start": 0.0, "end": 0.2},
                            {"text": "学", "start": 0.2, "end": 0.4},
                        ],
                    },
                )
            else:
                path.write_text(f"{key}\n", encoding="utf-8")
            final_paths[key] = path
        finalization_manifest = episode / "final" / "finalization_manifest.json"
        omission_evidence = {
            role: self.write_qc_evidence(
                episode / "final" / f"sprite_{role}_omission_evidence.json",
                "finalization fixture",
                evidence_kind="sprite_rhythm_omission",
                role=role,
                reason="The twelve-second fixture has no safe editorial beat.",
            )
            for role in ("confused", "aha", "thinking")
        }
        self.write_json(
            finalization_manifest,
            {
                "schema": "lecture-animation-approved-upload-master-v2",
                "upload_mp4": pipeline.relative_or_absolute(
                    final_paths["final_video"],
                    self.root,
                ),
                "upload_mp4_sha256": hashlib.sha256(
                    final_paths["final_video"].read_bytes()
                ).hexdigest(),
                "sprite_overlays": [],
                "sprite_rhythm_omissions": [
                    {
                        "role": role,
                        "reason": "The twelve-second fixture has no safe editorial beat.",
                        **omission_evidence[role],
                    }
                    for role in ("confused", "aha", "thinking")
                ],
                "sprite_pixel_qc": [],
            },
        )
        upload_package_receipt = episode / "final" / "upload_package_receipt.json"
        upload_receipt_payload = {
            "schema": "lecture-animation-upload-package-receipt-v1",
            "compiler": "pipeline_v2.seal-upload-package",
            "created_at": pipeline.utc_now(),
            "episode": pipeline.relative_or_absolute(episode, self.root),
            "final_video": {
                "path": pipeline.relative_or_absolute(final_paths["final_video"], self.root),
                "sha256": hashlib.sha256(final_paths["final_video"].read_bytes()).hexdigest(),
            },
            "final_audio": {
                "path": pipeline.relative_or_absolute(final_paths["final_audio"], self.root),
                "sha256": hashlib.sha256(final_paths["final_audio"].read_bytes()).hexdigest(),
            },
            "publication_srt": {
                "path": pipeline.relative_or_absolute(final_paths["final_srt"], self.root),
                "sha256": hashlib.sha256(final_paths["final_srt"].read_bytes()).hexdigest(),
            },
            "word_alignment": {
                "path": pipeline.relative_or_absolute(
                    final_paths["final_word_alignment"], self.root
                ),
                "sha256": hashlib.sha256(
                    final_paths["final_word_alignment"].read_bytes()
                ).hexdigest(),
            },
            "finalization_manifest": {
                "path": pipeline.relative_or_absolute(finalization_manifest, self.root),
                "sha256": hashlib.sha256(finalization_manifest.read_bytes()).hexdigest(),
            },
            "verdict": "pass",
        }
        upload_receipt_payload["receipt_hash"] = pipeline.object_hash(
            upload_receipt_payload
        )
        self.write_json(upload_package_receipt, upload_receipt_payload)
        narration = episode / "final" / "g001_narration.txt"
        narration.write_text(
            "先完成当前场景。小圈积分究竟读取奇点附近的什么信息？",
            encoding="utf-8",
        )
        scene_source = episode / "final" / "g001_scene.py"
        scene_source.write_text("from manim import *\n", encoding="utf-8")
        screen_text_semantics = (
            episode / "final" / "g001_screen_text_semantic_contract.json"
        )
        self.write_json(
            screen_text_semantics,
            {
                "schema": "lecture-animation-screen-text-semantic-contract-v1",
                "semantic_items": [],
            },
        )
        readiness_contract = episode / "review" / "v2" / "episode_readiness.json"
        self.write_json(
            readiness_contract,
            {
                "schema": "lecture-animation-episode-readiness-v2",
                "author_id": "author-test",
                "fixed_ending": "小圈积分究竟读取奇点附近的什么信息？",
                "fixed_ending_contract": {
                    "role": "learner_facing_math_question",
                    "learner_job": "Leave the learner with the exact unresolved mathematical question.",
                    "math_anchor": "small-contour local information",
                    "externalizes_production_intent": False,
                },
                "scenes": [
                    {
                        "scene_slug": "g001_finalize",
                        "scene_source_path": pipeline.relative_or_absolute(
                            scene_source, self.root
                        ),
                        "scene_source_root": pipeline.relative_or_absolute(
                            scene_source.parent, self.root
                        ),
                        "narration_path": pipeline.relative_or_absolute(narration, self.root),
                        "duration_seconds": 12.0,
                        "screen_text_semantic_contract_path": (
                            pipeline.relative_or_absolute(
                                screen_text_semantics, self.root
                            )
                        ),
                    }
                ],
            },
        )
        readiness_receipt = episode / "review" / "v2" / "episode_readiness_receipt.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_episode_preflight(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(episode),
                        contract=str(readiness_contract),
                        output=str(readiness_receipt),
                        require_clean=True,
                    )
                ),
                0,
        )
        receipt_path = episode / "episode_completion.json"
        with (
            mock.patch.object(
                pipeline_engine,
                "validate_upload_package_receipt",
                return_value={"receipt_hash": "canonical-fixture", "verdict": "pass"},
            ),
            mock.patch.object(
                pipeline_engine,
                "validate_finalization_manifest_contract",
                return_value={
                    "path": pipeline.relative_or_absolute(finalization_manifest, self.root),
                    "sha256": hashlib.sha256(finalization_manifest.read_bytes()).hexdigest(),
                    "sprite_overlay_count": 0,
                },
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(
                pipeline.command_finalize_episode(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(episode),
                        production=str(production_path),
                        episode_readiness=str(readiness_receipt),
                        episode_spine=None,
                        batch=[],
                        event_log=str(event_log),
                        finalization_manifest=str(finalization_manifest),
                        upload_package_receipt=str(upload_package_receipt),
                        output=str(receipt_path),
                        **{key: str(path) for key, path in final_paths.items()},
                    )
                ),
                0,
            )
        finalized = pipeline.load_json(production_path)
        self.assertEqual(finalized["scenes"][0]["state"], "assembled")
        self.assertEqual(finalized["assembly"]["status"], "assembled")
        self.assertTrue(pipeline.validate_hashed_record(pipeline.load_json(receipt_path), "completion_hash"))
        completion = pipeline.load_json(receipt_path)
        self.assertEqual(
            completion["finalization_manifest"]["sprite_overlay_count"],
            0,
        )

    def test_finalization_manifest_rejects_spoken_identity_without_sumino(self) -> None:
        final_dir = self.episode / "final-signoff"
        final_dir.mkdir(parents=True)
        video = final_dir / "final.mp4"
        video.write_bytes(b"fixture-video")
        srt = final_dir / "final.srt"
        srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n数学问题\n",
            encoding="utf-8",
        )
        preview = "下一期讨论留数"
        phrase = "我是结束乐队的键盘手下个视频见"
        aligned_text = preview + phrase
        alignment = final_dir / "alignment.json"
        self.write_json(
            alignment,
            {
                "schema": "test-alignment",
                "aligned_tokens": [
                    {
                        "text": character,
                        "start": index * 0.1,
                        "end": (index + 1) * 0.1,
                    }
                    for index, character in enumerate(aligned_text)
                ],
            },
        )
        manifest = final_dir / "manifest.json"
        omission_evidence = {
            role: self.write_qc_evidence(
                final_dir / f"sprite_{role}_omission_evidence.json",
                "missing signoff fixture",
                evidence_kind="sprite_rhythm_omission",
                role=role,
                reason="Fixture omission.",
            )
            for role in ("confused", "aha", "thinking")
        }
        self.write_json(
            manifest,
            {
                "schema": "lecture-animation-approved-upload-master-v2",
                "upload_mp4": pipeline.relative_or_absolute(video, self.root),
                "upload_mp4_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
                "next_episode_preview_text": preview,
                "sprite_overlays": [],
                "sprite_rhythm_omissions": [
                    {
                        "role": role,
                        "reason": "Fixture omission.",
                        **omission_evidence[role],
                    }
                    for role in ("confused", "aha", "thinking")
                ],
                "sprite_pixel_qc": [],
            },
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "requires exactly one mandatory sign-off sprite",
        ):
            pipeline.validate_finalization_manifest_contract(
                manifest,
                self.root,
                final_video=video,
                final_srt=srt,
                final_word_alignment=alignment,
            )

    def test_finalization_manifest_accepts_registered_sumino_action_without_override(self) -> None:
        final_dir = self.episode / "final-signoff-action-override"
        final_dir.mkdir(parents=True)
        video = final_dir / "final.mp4"
        video.write_bytes(b"fixture-video")
        srt = final_dir / "final.srt"
        srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n数学问题\n",
            encoding="utf-8",
        )
        preview = "下一期讨论留数"
        phrase = "我是结束乐队的键盘手下个视频见"
        aligned_text = preview + phrase
        alignment = final_dir / "alignment.json"
        self.write_json(
            alignment,
            {
                "schema": "test-alignment",
                "aligned_tokens": [
                    {
                        "text": character,
                        "start": index * 0.1,
                        "end": (index + 1) * 0.1,
                    }
                    for index, character in enumerate(aligned_text)
                ],
            },
        )
        clip = final_dir / "peek_rise.mov"
        clip.write_bytes(b"fixture-peek-rise-clip")
        asset_root = final_dir / "sprite-assets"
        asset_root.mkdir()
        (asset_root / "peek_rise.png").write_bytes(b"fixture-peek-rise-frame")
        self.write_json(
            asset_root / "metadata.json",
            {"actions": {"peek_rise": {"frames": ["peek_rise.png"]}}},
        )
        signoff_start = len(preview) * 0.1
        phrase_end = len(aligned_text) * 0.1
        manifest = final_dir / "manifest.json"
        base_overlay = {
            "character": "sumino",
            "action": "peek_rise",
            "semantic_anchor": "spoken keyboard-player identity",
            "mandatory_signoff": True,
            "word_anchor_start": signoff_start,
            "word_anchor_end": phrase_end,
            "global_start": signoff_start - 0.1,
            "global_end": phrase_end + 0.2,
            "clip": pipeline.relative_or_absolute(clip, self.root),
            "clip_sha256": hashlib.sha256(clip.read_bytes()).hexdigest(),
            "asset_root": pipeline.relative_or_absolute(asset_root, self.root),
            "asset_root_sha256": pipeline.artifact_snapshot(asset_root, self.root)[
                "sha256"
            ],
            "protected_rect": [48, 1400, 450, 1830],
            "subtitle_occlusion_policy": "above subtitle lane",
        }
        omission_evidence = {
            role: self.write_qc_evidence(
                final_dir / f"sprite_{role}_omission_evidence.json",
                "registered signoff fixture",
                evidence_kind="sprite_rhythm_omission",
                role=role,
                reason="Fixture omission.",
            )
            for role in ("confused", "aha", "thinking")
        }

        def pixel_evidence(index: int, overlay: dict[str, object]) -> dict[str, object]:
            return self.write_qc_evidence(
                final_dir / f"sprite_overlay_{index}_pixel_evidence.json",
                f"registered signoff overlay {index}",
                evidence_kind="sprite_pixel_qc",
                overlay_index=index,
                before_difference_yavg=0.0,
                on_difference_yavg=20.0,
                formula_overlap_pixels=0,
                subtitle_overlap_pixels=0,
                active_object_overlap_pixels=0,
                frame_window=[overlay["global_start"], overlay["global_end"]],
                protected_rect=overlay["protected_rect"],
                source_video_path=pipeline.relative_or_absolute(video, self.root),
                source_video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
            )

        base_pixel_evidence = pixel_evidence(1, base_overlay)
        self.write_json(
            manifest,
            {
                "schema": "lecture-animation-approved-upload-master-v2",
                "upload_mp4": pipeline.relative_or_absolute(video, self.root),
                "upload_mp4_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
                "next_episode_preview_text": preview,
                "sprite_overlays": [base_overlay],
                "sprite_rhythm_omissions": [
                    {
                        "role": role,
                        "reason": "Fixture omission.",
                        **omission_evidence[role],
                    }
                    for role in ("confused", "aha", "thinking")
                ],
                "sprite_pixel_qc": [
                    {
                        "overlay_index": 1,
                        "before_difference_yavg": 0.0,
                        "on_difference_yavg": 20.0,
                        "formula_overlap_pixels": 0,
                        "subtitle_overlap_pixels": 0,
                        "active_object_overlap_pixels": 0,
                        "status": "pass",
                        **base_pixel_evidence,
                    }
                ],
            },
        )
        override = final_dir / "override.json"
        self.write_json(
            override,
            {
                "schema": "lecture-animation-finalization-human-override-v1",
                "episode": pipeline.relative_or_absolute(self.episode, self.root),
                "issued_by": "user",
                "status": "authorized",
                "scope": "final_editorial_sprite_policy_only",
                "authorization_source": {
                    "kind": "explicit_user_instruction_in_current_codex_task",
                    "instructions": ["Sumino action follows scene semantics."],
                },
                "constraints": {
                    "sprite_count_policy": "no_whole_episode_cap",
                    "sprite_density_unit": "rolling_eight_second_entrance_window",
                    "simultaneous_sprite_policy": "disjoint_safe_regions_evidence_reviewed_semantics",
                    "mathematical_attention_priority": "hard_gate",
                    "identity_phrase": "我是结束乐队的键盘手，下个视频见",
                    "identity_character": "sumino",
                    "identity_character_count": 1,
                    "identity_action": "any_existing_semantically_appropriate_action",
                    "identity_action_talking_required": False,
                    "identity_window_coverage": "complete_word_aligned_signoff",
                    "identity_and_farewell_in_subtitles": False,
                    "identity_and_farewell_in_screen_text": False,
                },
            },
        )
        validated_without_override = pipeline.validate_finalization_manifest_contract(
            manifest,
            self.root,
            final_video=video,
            final_srt=srt,
            final_word_alignment=alignment,
            episode=self.episode,
        )
        self.assertEqual(
            validated_without_override["mandatory_signoff_action"],
            "peek_rise",
        )
        self.assertIsNone(
            validated_without_override["human_finalization_override"]
        )
        validated_with_historical_override = pipeline.validate_finalization_manifest_contract(
            manifest,
            self.root,
            final_video=video,
            final_srt=srt,
            final_word_alignment=alignment,
            episode=self.episode,
            finalization_override=override,
        )
        self.assertEqual(
            validated_with_historical_override["mandatory_signoff_action"],
            "peek_rise",
        )
        self.assertEqual(
            validated_with_historical_override["human_finalization_override"]["identity_action_policy"],
            "any_existing_semantically_appropriate_action",
        )

        unregistered = json.loads(manifest.read_text(encoding="utf-8"))
        unregistered["sprite_overlays"][0]["action"] = "not_registered"
        unregistered_path = final_dir / "manifest-unregistered.json"
        self.write_json(unregistered_path, unregistered)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "not registered in the bound asset metadata",
        ):
            pipeline.validate_finalization_manifest_contract(
                unregistered_path,
                self.root,
                final_video=video,
                final_srt=srt,
                final_word_alignment=alignment,
                episode=self.episode,
            )

        occluding = json.loads(manifest.read_text(encoding="utf-8"))
        occluding["sprite_pixel_qc"][0]["formula_overlap_pixels"] = 1
        occluding_path = final_dir / "manifest-occluding.json"
        self.write_json(occluding_path, occluding)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "evidence does not bind formula_overlap_pixels",
        ):
            pipeline.validate_finalization_manifest_contract(
                occluding_path,
                self.root,
                final_video=video,
                final_srt=srt,
                final_word_alignment=alignment,
                episode=self.episode,
            )

        generic = json.loads(manifest.read_text(encoding="utf-8"))
        generic_evidence_path = final_dir / "generic-self-report.json"
        self.write_json(
            generic_evidence_path,
            {"schema": "test", "status": "pass", "overlap_pixels": 0},
        )
        generic["sprite_pixel_qc"][0]["evidence_path"] = (
            pipeline.relative_or_absolute(generic_evidence_path, self.root)
        )
        generic["sprite_pixel_qc"][0]["evidence_sha256"] = hashlib.sha256(
            generic_evidence_path.read_bytes()
        ).hexdigest()
        generic_path = final_dir / "manifest-generic-self-report.json"
        self.write_json(generic_path, generic)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "evidence has the wrong schema",
        ):
            pipeline.validate_finalization_manifest_contract(
                generic_path,
                self.root,
                final_video=video,
                final_srt=srt,
                final_word_alignment=alignment,
                episode=self.episode,
            )

        valid_pixel_evidence_path = pipeline.resolve_stored_path(
            str(base_pixel_evidence["evidence_path"]), self.root
        )
        binary_evidence = json.loads(
            valid_pixel_evidence_path.read_text(encoding="utf-8")
        )
        fake_frame = final_dir / "fake-on-frame.bin"
        fake_frame.write_bytes(b"not an image")
        for artifact in binary_evidence["measurement_artifacts"]:
            if artifact["role"] == "on_frame":
                artifact["path"] = pipeline.relative_or_absolute(fake_frame, self.root)
                artifact["sha256"] = hashlib.sha256(fake_frame.read_bytes()).hexdigest()
        binary_evidence_path = final_dir / "binary-pixel-evidence.json"
        self.write_json(binary_evidence_path, binary_evidence)
        binary_manifest = json.loads(manifest.read_text(encoding="utf-8"))
        binary_manifest["sprite_pixel_qc"][0]["evidence_path"] = (
            pipeline.relative_or_absolute(binary_evidence_path, self.root)
        )
        binary_manifest["sprite_pixel_qc"][0]["evidence_sha256"] = hashlib.sha256(
            binary_evidence_path.read_bytes()
        ).hexdigest()
        binary_manifest_path = final_dir / "manifest-binary-pixel-evidence.json"
        self.write_json(binary_manifest_path, binary_manifest)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "pixel evidence is unreadable",
        ):
            pipeline.validate_finalization_manifest_contract(
                binary_manifest_path,
                self.root,
                final_video=video,
                final_srt=srt,
                final_word_alignment=alignment,
                episode=self.episode,
            )

        mask_evidence = json.loads(valid_pixel_evidence_path.read_text(encoding="utf-8"))
        white_formula_mask = final_dir / "white-formula-mask.png"
        Image.new("L", (64, 36), 255).save(white_formula_mask, format="PNG")
        for artifact in mask_evidence["measurement_artifacts"]:
            if artifact["role"] == "formula_mask":
                artifact["path"] = pipeline.relative_or_absolute(
                    white_formula_mask, self.root
                )
                artifact["sha256"] = hashlib.sha256(
                    white_formula_mask.read_bytes()
                ).hexdigest()
        mask_evidence_path = final_dir / "measured-formula-overlap-evidence.json"
        self.write_json(mask_evidence_path, mask_evidence)
        mask_manifest = json.loads(manifest.read_text(encoding="utf-8"))
        mask_manifest["sprite_pixel_qc"][0]["evidence_path"] = (
            pipeline.relative_or_absolute(mask_evidence_path, self.root)
        )
        mask_manifest["sprite_pixel_qc"][0]["evidence_sha256"] = hashlib.sha256(
            mask_evidence_path.read_bytes()
        ).hexdigest()
        mask_manifest_path = final_dir / "manifest-measured-formula-overlap.json"
        self.write_json(mask_manifest_path, mask_manifest)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "manifest formula_overlap_pixels does not match mask evidence",
        ):
            pipeline.validate_finalization_manifest_contract(
                mask_manifest_path,
                self.root,
                final_video=video,
                final_srt=srt,
                final_word_alignment=alignment,
                episode=self.episode,
            )

        uncapped = json.loads(manifest.read_text(encoding="utf-8"))
        base_overlay = uncapped["sprite_overlays"][0]
        base_pixel_qc = uncapped["sprite_pixel_qc"][0]
        for index in range(2, 14):
            overlay = dict(base_overlay)
            overlay.pop("mandatory_signoff", None)
            overlay["semantic_anchor"] = f"spaced teaching beat {index}"
            overlay["global_start"] = index * 10.0
            overlay["global_end"] = index * 10.0 + 1.0
            overlay["word_anchor_start"] = index * 10.0 + 0.1
            overlay["word_anchor_end"] = index * 10.0 + 0.5
            uncapped["sprite_overlays"].append(overlay)
            pixel_qc = dict(base_pixel_qc)
            pixel_qc["overlay_index"] = index
            pixel_qc.update(pixel_evidence(index, overlay))
            uncapped["sprite_pixel_qc"].append(pixel_qc)
        uncapped_path = final_dir / "manifest-uncapped-spaced.json"
        self.write_json(uncapped_path, uncapped)
        validated_uncapped = pipeline.validate_finalization_manifest_contract(
            uncapped_path,
            self.root,
            final_video=video,
            final_srt=srt,
            final_word_alignment=alignment,
            episode=self.episode,
        )
        self.assertEqual(validated_uncapped["sprite_overlay_count"], 13)
        self.assertEqual(validated_uncapped["rapid_entrance_window_count"], 0)

        simultaneous = json.loads(manifest.read_text(encoding="utf-8"))
        second_overlay = dict(base_overlay)
        second_overlay.pop("mandatory_signoff", None)
        second_overlay["semantic_anchor"] = "a distinct but compatible teaching cue"
        second_overlay["word_anchor_start"] = signoff_start + 0.1
        second_overlay["word_anchor_end"] = signoff_start + 0.5
        second_overlay["protected_rect"] = [3000, 1320, 3500, 1850]
        simultaneous["sprite_overlays"].append(second_overlay)
        second_pixel_qc = dict(base_pixel_qc)
        second_pixel_qc["overlay_index"] = 2
        second_pixel_qc.update(pixel_evidence(2, second_overlay))
        simultaneous["sprite_pixel_qc"].append(second_pixel_qc)
        simultaneous_path = final_dir / "manifest-simultaneous-unreviewed.json"
        self.write_json(simultaneous_path, simultaneous)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "lack a pass simultaneous-layout verdict",
        ):
            pipeline.validate_finalization_manifest_contract(
                simultaneous_path,
                self.root,
                final_video=video,
                final_srt=srt,
                final_word_alignment=alignment,
                episode=self.episode,
            )
        simultaneous_row = {
            "overlay_indices": [1, 2],
            "status": "pass",
            "semantic_reason": "Both reactions clarify different parts of one comparison.",
            "safe_area_evidence": "Disjoint left and right safe regions.",
            "visual_hierarchy_evidence": "Both remain smaller than the active formula.",
        }
        simultaneous_row.update(
            self.write_qc_evidence(
                final_dir / "sprite_simultaneous_1_2_evidence.json",
                "simultaneous sprite layout",
                evidence_kind="simultaneous_sprite_qc",
                overlay_indices=simultaneous_row["overlay_indices"],
                semantic_reason=simultaneous_row["semantic_reason"],
                safe_area_evidence=simultaneous_row["safe_area_evidence"],
                visual_hierarchy_evidence=simultaneous_row[
                    "visual_hierarchy_evidence"
                ],
            )
        )
        simultaneous["simultaneous_sprite_qc"] = [simultaneous_row]
        simultaneous_reviewed_path = final_dir / "manifest-simultaneous-reviewed.json"
        self.write_json(simultaneous_reviewed_path, simultaneous)
        validated_simultaneous = pipeline.validate_finalization_manifest_contract(
            simultaneous_reviewed_path,
            self.root,
            final_video=video,
            final_srt=srt,
            final_word_alignment=alignment,
            episode=self.episode,
        )
        self.assertEqual(validated_simultaneous["simultaneous_pair_count"], 1)
        self.assertEqual(
            validated_simultaneous["simultaneous_reviewed_pair_count"], 1
        )

        rapid = json.loads(manifest.read_text(encoding="utf-8"))
        for index, start in ((2, 10.0), (3, 12.0), (4, 14.0)):
            overlay = dict(base_overlay)
            overlay.pop("mandatory_signoff", None)
            overlay["semantic_anchor"] = f"rapid teaching beat {index}"
            overlay["global_start"] = start
            overlay["global_end"] = start + 1.0
            overlay["word_anchor_start"] = start + 0.1
            overlay["word_anchor_end"] = start + 0.5
            rapid["sprite_overlays"].append(overlay)
            pixel_qc = dict(base_pixel_qc)
            pixel_qc["overlay_index"] = index
            pixel_qc.update(pixel_evidence(index, overlay))
            rapid["sprite_pixel_qc"].append(pixel_qc)
        rapid_path = final_dir / "manifest-rapid-unreviewed.json"
        self.write_json(rapid_path, rapid)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "rapid sprite entrance window lacks a pass rhythm verdict",
        ):
            pipeline.validate_finalization_manifest_contract(
                rapid_path,
                self.root,
                final_video=video,
                final_srt=srt,
                final_word_alignment=alignment,
                episode=self.episode,
            )
        rapid_row = {
            "overlay_indices": [2, 3, 4],
            "status": "pass",
            "semantic_reason": "Three distinct reactions follow one compact comparison.",
        }
        rapid_row.update(
            self.write_qc_evidence(
                final_dir / "sprite_rapid_2_3_4_evidence.json",
                "rapid sprite rhythm",
                evidence_kind="sprite_rhythm_qc",
                overlay_indices=rapid_row["overlay_indices"],
                semantic_reason=rapid_row["semantic_reason"],
            )
        )
        rapid["sprite_rhythm_qc"] = [rapid_row]
        rapid_reviewed_path = final_dir / "manifest-rapid-reviewed.json"
        self.write_json(rapid_reviewed_path, rapid)
        validated_rapid = pipeline.validate_finalization_manifest_contract(
            rapid_reviewed_path,
            self.root,
            final_video=video,
            final_srt=srt,
            final_word_alignment=alignment,
            episode=self.episode,
        )
        self.assertEqual(validated_rapid["rapid_entrance_window_count"], 1)

    def test_finalization_manifest_rejects_pointing_away_from_target(self) -> None:
        final_dir = self.episode / "final-pointing"
        final_dir.mkdir(parents=True)
        video = final_dir / "final.mp4"
        video.write_bytes(b"fixture-video")
        srt = final_dir / "final.srt"
        srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n数学问题\n",
            encoding="utf-8",
        )
        alignment = final_dir / "alignment.json"
        self.write_json(
            alignment,
            {
                "schema": "test-alignment",
                "aligned_tokens": [
                    {"text": "数", "start": 0.0, "end": 0.2},
                    {"text": "学", "start": 0.2, "end": 0.4},
                ],
            },
        )
        clip = final_dir / "point.mov"
        clip.write_bytes(b"fixture-pointing-clip")
        asset_root = final_dir / "sprite-assets"
        asset_root.mkdir()
        (asset_root / "frame.png").write_bytes(b"fixture-frame")
        manifest = final_dir / "manifest.json"
        overlay = {
            "character": "sumino",
            "action": "point_right",
            "semantic_anchor": "point to the mathematical target",
            "word_anchor_start": 0.0,
            "word_anchor_end": 0.4,
            "global_start": 0.0,
            "global_end": 0.8,
            "clip": pipeline.relative_or_absolute(clip, self.root),
            "clip_sha256": hashlib.sha256(clip.read_bytes()).hexdigest(),
            "asset_root": pipeline.relative_or_absolute(asset_root, self.root),
            "asset_root_sha256": pipeline.artifact_snapshot(asset_root, self.root)[
                "sha256"
            ],
            "protected_rect": [48, 1400, 450, 1830],
            "subtitle_occlusion_policy": "above subtitle lane",
            "asset_facing_direction": "left",
            "mirrored_horizontally": False,
            "rendered_gesture_direction": "left",
            "gesture_target_rect": [520, 450, 2600, 1500],
        }
        omission_evidence = {
            role: self.write_qc_evidence(
                final_dir / f"sprite_{role}_omission_evidence.json",
                "directional gesture fixture",
                evidence_kind="sprite_rhythm_omission",
                role=role,
                reason="Fixture omission.",
            )
            for role in ("confused", "aha", "thinking")
        }
        pixel_evidence = self.write_qc_evidence(
            final_dir / "sprite_overlay_1_pixel_evidence.json",
            "directional gesture fixture",
            evidence_kind="sprite_pixel_qc",
            overlay_index=1,
            before_difference_yavg=0.0,
            on_difference_yavg=20.0,
            formula_overlap_pixels=0,
            subtitle_overlap_pixels=0,
            active_object_overlap_pixels=0,
            frame_window=[0.0, 0.8],
            protected_rect=overlay["protected_rect"],
            source_video_path=pipeline.relative_or_absolute(video, self.root),
            source_video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
        )
        self.write_json(
            manifest,
            {
                "schema": "lecture-animation-approved-upload-master-v2",
                "upload_mp4": pipeline.relative_or_absolute(video, self.root),
                "upload_mp4_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
                "sprite_overlays": [overlay],
                "sprite_rhythm_omissions": [
                    {
                        "role": role,
                        "reason": "Fixture omission.",
                        **omission_evidence[role],
                    }
                    for role in ("confused", "aha", "thinking")
                ],
                "sprite_pixel_qc": [
                    {
                        "overlay_index": 1,
                        "before_difference_yavg": 0.0,
                        "on_difference_yavg": 20.0,
                        "formula_overlap_pixels": 0,
                        "subtitle_overlap_pixels": 0,
                        "active_object_overlap_pixels": 0,
                        "status": "pass",
                        **pixel_evidence,
                    }
                ],
            },
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "points away from its declared mathematical target",
        ):
            pipeline.validate_finalization_manifest_contract(
                manifest,
                self.root,
                final_video=video,
                final_srt=srt,
                final_word_alignment=alignment,
            )

    def test_finalization_manifest_rejects_appledouble_in_delivery(self) -> None:
        final_dir = self.episode / "final-appledouble"
        final_dir.mkdir(parents=True)
        video = final_dir / "final.mp4"
        video.write_bytes(b"fixture-video")
        srt = final_dir / "final.srt"
        srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n数学问题\n",
            encoding="utf-8",
        )
        alignment = final_dir / "alignment.json"
        self.write_json(
            alignment,
            {
                "schema": "test-alignment",
                "aligned_tokens": [
                    {"text": "数", "start": 0.0, "end": 0.2},
                    {"text": "学", "start": 0.2, "end": 0.4},
                ],
            },
        )
        manifest = final_dir / "manifest.json"
        omission_evidence = {
            role: self.write_qc_evidence(
                final_dir / f"sprite_{role}_omission_evidence.json",
                "AppleDouble fixture",
                evidence_kind="sprite_rhythm_omission",
                role=role,
                reason="Fixture omission.",
            )
            for role in ("confused", "aha", "thinking")
        }
        self.write_json(
            manifest,
            {
                "schema": "lecture-animation-approved-upload-master-v2",
                "upload_mp4": pipeline.relative_or_absolute(video, self.root),
                "upload_mp4_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
                "sprite_overlays": [],
                "sprite_rhythm_omissions": [
                    {
                        "role": role,
                        "reason": "Fixture omission.",
                        **omission_evidence[role],
                    }
                    for role in ("confused", "aha", "thinking")
                ],
                "sprite_pixel_qc": [],
            },
        )
        (final_dir / "._foreign-sidecar").write_bytes(b"appledouble")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "contains AppleDouble files",
        ):
            pipeline.validate_finalization_manifest_contract(
                manifest,
                self.root,
                final_video=video,
                final_srt=srt,
                final_word_alignment=alignment,
                episode=self.episode,
            )

        (final_dir / "._foreign-sidecar").unlink()
        review_dir = self.episode / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "._review-sidecar").write_bytes(b"appledouble")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "contains AppleDouble files",
        ):
            pipeline.validate_finalization_manifest_contract(
                manifest,
                self.root,
                final_video=video,
                final_srt=srt,
                final_word_alignment=alignment,
                episode=self.episode,
            )

    def test_finalization_rule_registry_has_no_whole_episode_sprite_cap(self) -> None:
        rules = json.loads(
            (MODULE_PATH.parent.parent / "references/rules.json")
            .read_text(encoding="utf-8")
        )["rules"]
        final_rule = next(row for row in rules if row.get("rule_id") == "FINAL-002")
        requirement = str(final_rule.get("requirement", ""))
        self.assertIn("no whole-episode or same-screen overlay-count cap", requirement)
        self.assertIn("short-window entrance density", requirement)
        self.assertIn("disjoint safe regions", requirement)
        self.assertNotIn("more than twelve", requirement.lower())

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def write_qc_evidence(
        self,
        path: Path,
        label: str,
        *,
        evidence_kind: str,
        **bound_fields: object,
    ) -> dict[str, object]:
        artifact_roles = (
            (
                "before_reference_frame",
                "before_frame",
                "on_frame",
                "formula_mask",
                "subtitle_mask",
                "active_object_mask",
            )
            if evidence_kind == "sprite_pixel_qc"
            else ("review_frame",)
        )
        measurement_artifacts = []
        image_size = (64, 36)
        generated_images: dict[str, Image.Image] = {}
        if evidence_kind == "sprite_pixel_qc":
            generated_images = {
                role: Image.new(
                    "RGB" if role.endswith("frame") else "L",
                    image_size,
                    0,
                )
                for role in artifact_roles
            }
            rect = bound_fields["protected_rect"]
            scaled_rect = [
                max(0, min(image_size[0] - 1, round(float(rect[0]) / 3840 * image_size[0]))),
                max(0, min(image_size[1] - 1, round(float(rect[1]) / 2160 * image_size[1]))),
                max(0, min(image_size[0] - 1, round(float(rect[2]) / 3840 * image_size[0]))),
                max(0, min(image_size[1] - 1, round(float(rect[3]) / 2160 * image_size[1]))),
            ]
            if scaled_rect[2] <= scaled_rect[0]:
                scaled_rect[2] = min(image_size[0] - 1, scaled_rect[0] + 1)
            if scaled_rect[3] <= scaled_rect[1]:
                scaled_rect[3] = min(image_size[1] - 1, scaled_rect[1] + 1)
            ImageDraw.Draw(generated_images["on_frame"]).rectangle(
                scaled_rect,
                fill=(255, 255, 255),
            )
            before_pixels = list(
                generated_images["before_frame"].get_flattened_data()
            )
            on_pixels = list(generated_images["on_frame"].get_flattened_data())
            on_difference = sum(
                abs((299 * left[0] + 587 * left[1] + 114 * left[2]) / 1000 -
                    (299 * right[0] + 587 * right[1] + 114 * right[2]) / 1000)
                for left, right in zip(before_pixels, on_pixels)
            ) / len(before_pixels)
            bound_fields.update(
                {
                    "before_difference_yavg": 0.0,
                    "on_difference_yavg": on_difference,
                    "formula_overlap_pixels": 0,
                    "subtitle_overlap_pixels": 0,
                    "active_object_overlap_pixels": 0,
                    "pixel_difference_threshold": 18,
                    "frame_timestamps": {
                        "before_reference": max(
                            0.0, float(bound_fields["frame_window"][0]) - 2 / 30
                        ),
                        "before": max(
                            0.0, float(bound_fields["frame_window"][0]) - 1 / 30
                        ),
                        "on": (
                            float(bound_fields["frame_window"][0])
                            + float(bound_fields["frame_window"][1])
                        )
                        / 2,
                    },
                }
            )
        else:
            generated_images["review_frame"] = Image.new("RGB", image_size, 0)
        for role in artifact_roles:
            artifact_path = path.with_name(f"{path.stem}_{role}.png")
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            generated_images[role].save(artifact_path, format="PNG")
            measurement_artifacts.append(
                {
                    "role": role,
                    "path": pipeline.relative_or_absolute(artifact_path, self.root),
                    "sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                }
            )
        self.write_json(
            path,
            {
                "schema": "lecture-animation-finalization-qc-evidence-v1",
                "evidence_kind": evidence_kind,
                "label": label,
                "status": "pass",
                "measurement_tool": (
                    "pipeline_v2.sprite-pixel-audit-v1"
                    if evidence_kind == "sprite_pixel_qc"
                    else "fixture-review-audit-v1"
                ),
                "measurement_artifacts": measurement_artifacts,
                **bound_fields,
            },
        )
        result: dict[str, object] = {
            "evidence_path": pipeline.relative_or_absolute(path, self.root),
            "evidence_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        if evidence_kind == "sprite_pixel_qc":
            result.update(
                {
                    field: bound_fields[field]
                    for field in (
                        "before_difference_yavg",
                        "on_difference_yavg",
                        "formula_overlap_pixels",
                        "subtitle_overlap_pixels",
                        "active_object_overlap_pixels",
                    )
                }
            )
        return result

    @staticmethod
    def narration_style_contract() -> dict[str, object]:
        return {
            "contract_id": "novice-first-course-spine-v1",
            "reference_scripts": ["videos/0002/script.md", "videos/0003/script.md", "videos/0004/script.md"],
            "audience": "A first-time learner who knows the prior episode but not the current result.",
            "voice": "Calm conversational teacher language with precise mathematical causal responsibility.",
            "reasoning_order": "Motivation before operation, visible operation before formula, and formula before naming.",
            "sentence_rules": ["One new abstraction per short beat.", "Prefer concrete causal subjects over vague pronouns."],
            "terminology_rules": ["Keep course terminology stable.", "Speak mathematical symbols in natural language."],
            "forbidden_patterns": ["Production-process commentary.", "Unsupported advanced terminology or theorem dumping."],
            "audio_only_success_test": "A novice can teach back why each formula appears without seeing the animation.",
            "subagent_freedom": "Sentence rhythm and pauses may change after the animatic, but claims and prerequisites may not.",
        }

    def _write_old_history(self) -> None:
        timeline = {
            "scene_groups": [
                {
                    "id": "G003",
                    "scene_slug": "g003_projection_cells",
                    "duration": 24.0,
                    "role": "show projection coordinates becoming narrow frequency cells",
                    "math_objects": ["projection coefficient", "frequency cells", "partial sum"],
                    "driver": "cell width drives rectangle area and partial reconstruction",
                    "review_status": "pass_for_user_review_pending",
                    "risk_tier": "normal",
                }
            ],
            "segments": [
                {
                    "id": "S003",
                    "scene_group": "G003",
                    "narration": "Each projection coordinate becomes a visible frequency cell contribution.",
                }
            ],
        }
        self.write_json(self.old_episode / "timeline.json", timeline)
        (self.old_episode / "storyboard.md").write_text(
            "### G003 - Projection cells\nFrequency points expand into cells; their true areas accumulate into a partial reconstruction.\n",
            encoding="utf-8",
        )
        source = self.old_episode / "src" / "scenes" / "g003_projection_cells"
        source.mkdir(parents=True)
        (source / "composer.py").write_text(
            "class ProjectionCells:\n    driver = 'cell width and partial sum'\n",
            encoding="utf-8",
        )
        self.write_json(
            source / "visual_grammar.json",
            {
                "schema": "lecture-animation-visual-grammar-v2",
                "scene_slug": "g003_projection_cells",
                "patterns": [
                    {
                        "id": "identity_carrier_cross_view_transform",
                        "title": "Move the corresponding graph element into its formula role",
                        "learner_operations": ["compare corresponding elements in two views"],
                        "hidden_relation": "The graph measurement and formula token are the same quantity.",
                        "identity_invariant": "The mathematical quantity remains fixed across views.",
                        "attention_transfer": "The moving element carries attention between regions.",
                        "visual_action": "Move or morph the source element into the destination instead of drawing a long arrow.",
                        "prefer_over": ["a straight arrow crossing the graph"],
                        "retrieval_terms": ["corresponding elements", "identity carrier", "元素对应", "边移动边变形"],
                        "source_anchors": [
                            {
                                "path": "videos/0001-old-projection/src/scenes/g003_projection_cells/composer.py",
                                "symbol": "ProjectionCells",
                                "lines": "1-2",
                                "role": "Move a selected cell measurement into the matching formula token."
                            }
                        ],
                        "review_status": "pass_for_user_review_pending",
                        "review_artifact": "review/v2/g003_projection_cells/independent_review.md"
                    }
                ]
            },
        )

    def _write_current_episode(self) -> None:
        timeline = {
            "scene_groups": [
                {
                    "id": "G002C",
                    "scene_slug": "g002c_riemann_sum_limit",
                    "start": 20.0,
                    "end": 30.0,
                    "duration": 10.0,
                    "role": "show a Riemann sum refining into a continuous integral",
                    "math_objects": ["frequency points", "cells", "rectangles", "density curve"],
                    "driver": "L increases while Delta omega shrinks and the partial reconstruction converges",
                    "risk_tier": "repeat-rejected",
                },
                {
                    "id": "G002D",
                    "scene_slug": "g002d_normalization",
                    "start": 30.0,
                    "end": 40.0,
                    "duration": 10.0,
                    "role": "preserve the measure factor through normalization",
                    "math_objects": ["measure factor", "normalized coefficient"],
                    "driver": "normalization convention changes the visible coefficient factor",
                },
                {
                    "id": "G003",
                    "scene_slug": "g003_density",
                    "start": 40.0,
                    "end": 50.0,
                    "duration": 10.0,
                    "role": "interpret Fourier values as a continuous coordinate density",
                    "math_objects": ["density curve", "interval contribution"],
                    "driver": "interval width turns density height into contribution",
                },
            ],
            "segments": [
                {
                    "id": "S007",
                    "scene_group": "G002C",
                    "narration": "The frequency points become cells. Refining the cells turns the Riemann sum into an integral.",
                }
            ],
        }
        self.write_json(self.episode / "timeline.json", timeline)
        (self.episode / "storyboard.md").write_text(
            "### G002C - Riemann sum limit\nRefine frequency cells while preserving the density and reconstruction target.\n",
            encoding="utf-8",
        )
        issues = self.episode / "review" / "issues"
        self.write_json(
            issues / "g002c_missing_limit.json",
            {
                "id": "human-limit-1",
                "scene": "g002c_riemann_sum_limit",
                "source": "human_review",
                "severity": "blocker",
                "pattern_key": "riemann_sum_named_but_not_visualized",
                "must_check_in_future": True,
                "applies_to_authoring": True,
                "problem": "The formula changes, but no frequency cells refine.",
                "suggested_fix": "Show point, cell, area, refinement, and integral.",
            },
        )

    def make_profile(self) -> dict:
        return pipeline.compile_profile_data(
            self.root,
            self.episode,
            "g002c_riemann_sum_limit",
        )

    def make_design_bundle(self, profile: dict) -> tuple[dict, dict, dict, dict]:
        challenge = pipeline.build_design_challenge(profile)
        deliberation = {
            "schema": "lecture-animation-design-deliberation-v2",
            "challenge_hash": challenge["challenge_hash"],
            "author": "test-animation-author",
            "phase": "first_principles",
            "history_consulted": False,
            "novice_model": {
                "known_before": "The learner knows a finite Fourier sum uses discrete frequency points.",
                "likely_wrong_inference": "The learner may think the sum symbol simply changes into an integral by notation.",
                "needed_visual_evidence": "Frequency points must acquire cell widths and their rectangle areas must refine visibly.",
                "success_prediction": "The learner can predict that increasing L narrows cells and improves the integral approximation.",
            },
            "problem_signature": {
                "learner_operation": "Read a discrete frequency sum as accumulated interval contributions.",
                "invisible_relation": "The cell width Delta omega links each frequency sample to an area contribution.",
                "must_remain_invariant": "The same Gaussian density and reconstruction target remain identifiable.",
                "must_become_perceptible": "Cell refinement and area convergence must be visible before the integral appears.",
                "working_memory_burden": "The learner must retain the sum, cell width, density, and limit relation together.",
            },
            "hypotheses": [
                {
                    "id": "cell_atlas",
                    "representation_class": "split_2d_then_promotion",
                    "representation_signature": {
                        "primary_math_object_ids": ["cells", "rectangles", "density curve"],
                        "stage_topology": ["split_comparison", "sequential_promotion"],
                        "display_mapping_modes": ["identity", "uniform_scale"],
                        "attention_handoff_sequence": ["selected cell", "formula memory", "cell family"],
                        "causal_chain_object_ids": ["frequency points", "cells", "rectangles", "density curve"],
                        "identity_carrier_ids": ["cells", "density curve"],
                    },
                    "contrast_against": [
                        {
                            "hypothesis_id": "single_graph_baseline",
                            "changed_axes": ["stage_topology", "attention_handoff"],
                            "learner_visible_consequence": "The formula-term correspondence becomes pointable before the graph expands for global refinement.",
                        }
                    ],
                    "technical_mechanism": "Use one truthful graph/formula split, then continuously promote the graph after the local term is established.",
                    "revealed_relation": "One rectangle area and its formula term remain the same quantity while the whole partition refines.",
                    "continuity_carriers": ["selected cell color", "density curve", "Delta omega token"],
                    "complexity_tier": "focused",
                    "why_simpler_fails": "A static single graph cannot preserve both the local term correspondence and the later global refinement at readable scale.",
                    "overdesign_risk": "The supporting formula region could become a second focal panel after its memory job is complete.",
                    "removal_test": "Removing the split erases the visible term correspondence; keeping it forever crowds the global limit.",
                    "stage_logic": "Use a broad frequency graph with cells, plus a persistent formula memory region that later yields space.",
                    "view_mapping": "Map every frequency point to a truthful rectangle whose width is Delta omega and height is the density.",
                    "math_state_logic": "Increasing L recomputes cell count, width, and the numerical partial reconstruction from one driver.",
                    "attention_logic": "Follow one selected cell, then the whole refining family, then the limiting density curve.",
                    "identity_invariants": "Keep the selected cell color, density curve, and L driver continuous through promotion.",
                    "novice_advantage": "The learner can inspect both one contribution and the global convergence without a symbolic jump.",
                    "failure_risk": "Too many equally bright rectangles could compete with the selected cell and formula memory.",
                    "mute_test_prediction": "With narration muted, narrowing cells and converging area still communicate a Riemann limit.",
                    "selected": True,
                },
                {
                    "id": "phasor_accumulation",
                    "representation_class": "expanded_complex_multiview",
                    "representation_signature": {
                        "primary_math_object_ids": ["frequency points"],
                        "stage_topology": ["synchronized_multiview"],
                        "display_mapping_modes": ["projection"],
                        "attention_handoff_sequence": ["frequency pair", "complex vector endpoint"],
                        "causal_chain_object_ids": ["frequency points"],
                        "identity_carrier_ids": ["frequency points"],
                    },
                    "contrast_against": [
                        {
                            "hypothesis_id": "single_graph_baseline",
                            "changed_axes": [
                                "primary_math_objects",
                                "stage_topology",
                                "display_mapping_modes",
                                "causal_chain",
                            ],
                            "learner_visible_consequence": "Cancellation becomes visible, but the required interval-area relation becomes less direct.",
                        }
                    ],
                    "technical_mechanism": "Accumulate complex contribution vectors while a synchronized frequency strip identifies each source sample.",
                    "revealed_relation": "Complex cancellation and endpoint motion become visible, but interval width remains indirect.",
                    "continuity_carriers": ["vector colors", "endpoint marker", "frequency-pair highlight"],
                    "complexity_tier": "expanded",
                    "why_simpler_fails": "Without the synchronized frequency strip the phasor endpoint loses its sample provenance.",
                    "overdesign_risk": "Two animated views may teach cancellation instead of the required Riemann-cell limit.",
                    "removal_test": "Removing the complex plane improves economy without losing the interval-area claim required by this scene.",
                    "stage_logic": "Use a complex-plane running sum as the dominant view and keep frequency samples in a narrow side strip.",
                    "view_mapping": "Map each sampled complex contribution to a rotating vector and show the endpoint trajectory.",
                    "math_state_logic": "Adding symmetric frequencies changes the phasor endpoint while the bandwidth expands.",
                    "attention_logic": "Track the endpoint first, then reveal which frequency pair produced the latest displacement.",
                    "identity_invariants": "Preserve vector colors and the endpoint marker across each accumulated contribution.",
                    "novice_advantage": "The learner sees cancellation directly, but interval area is less immediately inspectable.",
                    "failure_risk": "The complex-vector story may obscure the specific Riemann-cell argument required here.",
                    "mute_test_prediction": "Without narration it reads as cancellation, not necessarily as a sum-to-integral limit.",
                    "selected": False,
                },
                {
                    "id": "single_graph_baseline",
                    "representation_class": "minimal_single_2d",
                    "representation_signature": {
                        "primary_math_object_ids": ["cells", "rectangles", "density curve"],
                        "stage_topology": ["single_view"],
                        "display_mapping_modes": ["identity", "uniform_scale"],
                        "attention_handoff_sequence": ["selected cell", "cell family"],
                        "causal_chain_object_ids": ["frequency points", "cells", "rectangles", "density curve"],
                        "identity_carrier_ids": ["cells", "density curve"],
                    },
                    "contrast_against": [
                        {
                            "hypothesis_id": "cell_atlas",
                            "changed_axes": ["stage_topology", "attention_handoff"],
                            "learner_visible_consequence": "The stage is simpler, but the exact formula-term ancestry must be inferred from narration.",
                        }
                    ],
                    "technical_mechanism": "Keep one frequency graph and refine rectangles in place with only a small selected-cell label.",
                    "revealed_relation": "The global Riemann refinement is visible in the smallest honest representation.",
                    "continuity_carriers": ["density curve", "selected cell color"],
                    "complexity_tier": "baseline",
                    "why_simpler_fails": "Anything simpler would replace the interval contributions with a symbolic formula change.",
                    "overdesign_risk": "The baseline may become too compressed to connect one rectangle area with its exact formula term.",
                    "removal_test": "Removing the selected-cell cue makes the global refinement visible but the local contribution unreadable.",
                    "stage_logic": "Use one full-width frequency graph with refining cells and one local selected-cell cue.",
                    "view_mapping": "Map every frequency point to its truthful rectangle on a single coordinate system.",
                    "math_state_logic": "Increasing L recomputes the whole partition from one driver without any view change.",
                    "attention_logic": "Follow the selected cell briefly, then the whole rectangle family.",
                    "identity_invariants": "Keep the density curve and selected cell generated from the same L-dependent partition.",
                    "novice_advantage": "The learner sees the global limit with minimal screen complexity.",
                    "failure_risk": "The formula-term correspondence may be too implicit for a first-time learner.",
                    "mute_test_prediction": "With narration muted, refinement is visible but the exact symbolic ancestry is not.",
                    "selected": False,
                },
            ],
            "selection_reason": "The cell atlas directly exposes the missing interval-width evidence while preserving formula memory and a clear promotion path.",
        }
        gate = pipeline.validate_design_deliberation_data(profile, challenge, deliberation)
        self.assertTrue(gate["valid"], gate["errors"])
        packet = pipeline.build_precedent_packet(self.root, profile, deliberation, gate, production_limit=3, guidance_limit=2)
        return challenge, deliberation, gate, packet

    def make_plan(self, profile: dict, bundle: tuple[dict, dict, dict, dict]) -> dict:
        challenge, deliberation, gate, packet = bundle
        return {
            "schema": "lecture-animation-scene-plan-v2",
            "profile_hash": profile["profile_hash"],
            "scene_slug": "g002c_riemann_sum_limit",
            "planning_chain": {
                "episode_spine_hash": "a" * 64,
                "batch_plan_hash": "b" * 64,
            },
            "screen_text_contract": {
                "mode": "exact",
                "baseline_path": "videos/0002-limit/review/v2/text_baseline.json",
                "purpose": "Freeze the accepted on-screen text inventory for this repeat-rejected scene.",
                "semantic_items": [],
                "dynamic_payload_policy": "runtime_registered",
                "dynamic_payload_count": 0,
                "narration_duplicate_payloads": [],
                "producer_intent_payloads": [],
                "registration_contract_version": 1,
                "registration_registry_path": "videos/0002-limit/review/v2/g002c_riemann_sum_limit/screen_text_registry_test.json",
                "registration_registry_hash": "c" * 64,
                "registration_attempt_log_path": "videos/0002-limit/review/evolution/screen_text_registration_attempts.jsonl",
                "profile_hash": profile["profile_hash"],
            },
            "narrated_action_contracts": [],
            "design_chain": {
                "challenge_hash": challenge["challenge_hash"],
                "deliberation_hash": pipeline.object_hash(deliberation),
                "design_gate_hash": gate["design_gate_hash"],
                "precedent_packet_hash": packet["precedent_packet_hash"],
            },
            "selected_hypothesis_id": gate["selected_hypothesis_id"],
            "representation_budget": {
                "selected_representation_class": "split_2d_then_promotion",
                "minimum_sufficient_claim": "Use only the temporary graph/formula split needed to establish one term, then release that space for the global refinement.",
                "peak_simultaneous_views": 2,
                "decorative_only_elements": [],
                "rejected_excess": [
                    {
                        "idea": "complex phasor side view",
                        "why_excess": "It adds cancellation motion but does not improve the interval-area explanation required here.",
                    }
                ],
                "visual_finish_contract": {
                    "visual_intent": "A deliberate graph-to-formula composition makes the selected interval contribution dominant before the global refinement.",
                    "primary_focal_strategy": "The selected cell is the brightest and thickest local object until the full partition becomes the primary refinement object.",
                    "scale_hierarchy": "The graph owns the largest span, the selected cell owns the strongest local scale, and formula memory remains compact support.",
                    "typography_hierarchy": "One compact title tier and one formula-memory tier remain subordinate to the active mathematical construction.",
                    "line_weight_hierarchy": "The selected cell and density curve use primary strokes; axes and inactive cells use quieter supporting strokes.",
                    "contrast_hierarchy": "Warm selected-cell contrast leads, the blue density curve supports identity, and inactive geometry stays low contrast.",
                    "material_coherence_strategy": "All graph marks share one restrained chalk-like material while formula memory uses the same brightness ladder.",
                    "motion_finish_strategy": "The graph promotion uses one continuous path and the formula retires only after its identity carrier is transferred.",
                    "thumbnail_readability_prediction": "At thumbnail size the selected cell is immediately primary in the split state and the refining graph is primary after promotion.",
                    "animatic_represents": [
                        "composition",
                        "object_scale",
                        "visual_hierarchy",
                        "contrast_roles",
                        "typography_roles",
                        "line_weight_roles",
                        "transition_topology",
                    ],
                    "allowed_polish_deferrals": [
                        "render_resolution",
                        "sampling_density",
                        "shading_detail",
                        "final_easing",
                    ],
                    "generic_default_rejections": [
                        "uniform line weight across axes, cells, and focal curve",
                        "formula and graph rendered at equal brightness and salience",
                    ],
                    "negative_space_jobs": [
                        {
                            "stage_state_id": "split_context",
                            "regions": ["between graph and formula"],
                            "job": "Separate the selected-cell action from formula memory while preserving a short identity handoff.",
                        },
                        {
                            "stage_state_id": "graph_promoted",
                            "regions": ["outer graph margins"],
                            "job": "Frame the full partition and keep the density envelope readable during refinement.",
                        },
                    ],
                },
                "techniques": [
                    {
                        "technique_id": "term_split_then_promote",
                        "technique_class": "dynamic_split_promotion",
                        "view_ids": ["graph", "formula"],
                        "math_object_ids": [
                            "frequency_partition_math",
                            "riemann_formula_math",
                        ],
                        "display_mapping_ids": [
                            "frequency_partition_view",
                            "riemann_formula_view",
                        ],
                        "driver_ids": ["L"],
                        "value_channel": "cognitive",
                        "value_claim": "The temporary split makes one cell-area/formula-term identity inspectable before the graph expands for the limit.",
                        "removal_failure": "Without the temporary formula memory, a novice must infer the symbolic ancestry from narration alone.",
                        "unique_learning_job": "Make the selected rectangle and its exact formula term simultaneously pointable.",
                        "hidden_relation_or_false_inference": "Prevent the false inference that the sum symbol becomes an integral by notation alone.",
                        "counterfactual_without": "Without the formula memory, the interval-area ancestry exists only in narration.",
                        "not_redundant_with": [],
                        "not_redundant_reason": "This is the only technique that externalizes the local cell-to-term identity before global refinement.",
                        "identity_carriers": ["frequency_cells", "selected cell color", "density curve"],
                        "evidence_checkpoint_ids": [
                            "split_context",
                            "split_context->graph_promoted",
                            "graph_promoted",
                        ],
                    }
                ],
            },
            "primary_question": "How does the finite frequency sum become a continuous integral?",
            "learning_contract": {
                "novice_start_state": "The learner recognizes a finite Fourier sum over discrete frequencies.",
                "core_claim": "Each sampled frequency represents an interval contribution whose refinement becomes an integral.",
                "likely_misconception": "The summation symbol may appear to turn into an integral by notation alone.",
                "visible_evidence": "Points expand into cells, cells produce rectangle areas, and refinement approaches the density curve.",
                "success_test": "The learner can use increasing L to predict smaller Delta omega and a better integral approximation.",
            },
            "math_driver": {
                "name": "L",
                "relation": "Delta omega = 2pi/L",
                "drives": ["cell width", "rectangle count", "partial sum"],
            },
            "math_objects": [
                {
                    "object_id": "frequency_partition_math",
                    "mathematical_type": "finite frequency partition",
                    "definition": "The sampled frequency partition with Delta omega equal to two pi divided by L.",
                    "driver_ids": ["L"],
                    "parameters": [
                        {"parameter_id": "L", "role": "math"},
                        {"parameter_id": "cell_width_screen", "role": "display"},
                    ],
                },
                {
                    "object_id": "riemann_formula_math",
                    "mathematical_type": "Riemann reconstruction expression",
                    "definition": "The finite reconstruction expression and its continuous integral limit.",
                    "driver_ids": [],
                    "parameters": [],
                },
            ],
            "display_mappings": [
                {
                    "mapping_id": "frequency_partition_view",
                    "source_object_id": "frequency_partition_math",
                    "mode": "uniform_scale",
                    "display_parameters": [
                        {"parameter_id": "cell_width_screen", "role": "display", "source_parameter_id": "L"}
                    ],
                    "verification": {
                        "preserved_invariants": ["partition order", "Delta omega relation"],
                        "distorted_quantities": [],
                        "forbidden_inferences": [],
                        "validation_method": "Recompute every displayed cell edge from the active L driver.",
                    },
                },
                {
                    "mapping_id": "riemann_formula_view",
                    "source_object_id": "riemann_formula_math",
                    "mode": "identity",
                    "display_parameters": [],
                    "verification": {
                        "preserved_invariants": ["formula token ancestry"],
                        "distorted_quantities": [],
                        "forbidden_inferences": [],
                        "validation_method": "Compare the rendered token ancestry with the planned expression states.",
                    },
                },
            ],
            "visual_bindings": [
                {
                    "visual_object_id": "frequency_cells",
                    "math_object_id": "frequency_partition_math",
                    "display_mapping_id": "frequency_partition_view",
                    "driver_ids": ["L"],
                    "runtime_owner": "V2SceneRuntime frequency cell registry",
                },
                {
                    "visual_object_id": "riemann_formula",
                    "math_object_id": "riemann_formula_math",
                    "display_mapping_id": "riemann_formula_view",
                    "driver_ids": [],
                    "runtime_owner": "V2SceneRuntime formula registry",
                },
            ],
            "math_object_invariants": [
                {
                    "invariant_id": "cells_follow_L",
                    "object_id": "frequency_cells",
                    "mathematical_claim": "Increasing L narrows every frequency cell without changing the density envelope.",
                    "expected_relation": "cell width equals two pi divided by L",
                    "evidence_type": "runtime_assertion",
                    "checkpoints": [2.5, 7.0],
                },
                {
                    "invariant_id": "formula_keeps_ancestry",
                    "object_id": "riemann_formula",
                    "mathematical_claim": "The finite sum retains its interval factor until the continuous integral is established.",
                    "expected_relation": "Delta omega becomes d omega only after cell refinement",
                    "evidence_type": "formula_handoff",
                    "checkpoints": [1.0, 4.0],
                },
            ],
            "novice_causal_steps": [
                {
                    "known_before": "Frequency samples are discrete points in a finite Fourier sum.",
                    "cause": "increase L",
                    "visible_action": "narrow and multiply the frequency cells",
                    "new_evidence": "The rectangle family keeps the same density envelope while individual widths shrink.",
                    "allowed_inference": "The accumulated cell areas approach a continuous frequency integral.",
                }
            ],
            "stage_regions": [
                {
                    "name": "graph",
                    "owner": "frequency cells",
                    "teaching_job": "Make local cell contributions and global refinement inspectable.",
                    "primary_object": "frequency_cells",
                    "detail_strategy": "rich",
                },
                {
                    "name": "formula",
                    "owner": "Riemann derivation",
                    "teaching_job": "Preserve symbolic ancestry while the graph performs the limit.",
                    "primary_object": "riemann_formula",
                    "detail_strategy": "supporting",
                },
            ],
            "region_relations": [
                {
                    "relation_id": "cells_to_formula",
                    "from": "graph",
                    "to": "formula",
                    "mathematical_relation": "Rectangle width and height instantiate the corresponding tokens in the finite sum.",
                    "visual_encoding": "temporal_sync",
                }
            ],
            "region_refinements": [
                {
                    "region": "graph",
                    "object_id": "frequency_cells",
                    "detail": "Selected cell plus truthful small-multiple rectangle family.",
                    "mathematical_meaning": "Each rectangle area is one Delta omega weighted frequency contribution.",
                    "novice_value": "The learner can inspect one term before reading the whole refinement.",
                },
                {
                    "region": "formula",
                    "object_id": "riemann_formula",
                    "detail": "Persistent aligned sum, cell contribution, and integral ancestry.",
                    "mathematical_meaning": "The Delta omega token remains visible until it becomes d omega.",
                    "novice_value": "The learner does not have to reconstruct earlier formula lines from memory.",
                },
            ],
            "identity_map": [
                {
                    "object_id": "frequency_cells",
                    "mathematical_identity": "The same sampled density partition under changing L.",
                    "persistent_cue": "Blue density curve and one warm selected cell remain continuous.",
                },
                {
                    "object_id": "riemann_formula",
                    "mathematical_identity": "The same reconstruction expression across sum and integral forms.",
                    "persistent_cue": "Token ancestry and horizontal alignment preserve formula identity.",
                },
            ],
            "attention_budget": {"max_simultaneous_focal_points": 1},
            "subtitle_safe_zone": {"bottom_fraction": 0.16, "owners": []},
            "stage_states": [
                {
                    "id": "split_context",
                    "start": 0.0,
                    "end": 4.5,
                    "math_state_id": "L=small",
                    "learner_task": "Connect one frequency cell area to one term of the finite sum.",
                    "active_regions": [
                        {
                            "region": "graph",
                            "bounds": [0.04, 0.20, 0.68, 0.94],
                            "salience": "primary",
                            "view_mapping": "Discrete samples and finite-width rectangles on the frequency axis.",
                        },
                        {
                            "region": "formula",
                            "bounds": [0.72, 0.58, 0.97, 0.94],
                            "salience": "supporting",
                            "view_mapping": "Aligned symbolic memory for the selected rectangle contribution.",
                        },
                    ],
                },
                {
                    "id": "graph_promoted",
                    "start": 4.5,
                    "end": 10.0,
                    "math_state_id": "L=large",
                    "learner_task": "Inspect global refinement after the local cell meaning is established.",
                    "active_regions": [
                        {
                            "region": "graph",
                            "bounds": [0.04, 0.20, 0.97, 0.94],
                            "salience": "primary",
                            "view_mapping": "The same frequency partition promoted to a full-width refinement view.",
                        }
                    ],
                },
            ],
            "stage_transitions": [
                {
                    "from_state": "split_context",
                    "to_state": "graph_promoted",
                    "start": 4.45,
                    "end": 5.20,
                    "from_focus_region": "graph",
                    "to_focus_region": "graph",
                    "change_vector": ["M", "D"],
                    "change_order": ["D", "M"],
                    "pedagogical_trigger": "The local rectangle meaning is established and global convergence becomes the new question.",
                    "math_driver_event": "L increases and recomputes Delta omega, cell count, and rectangle areas.",
                    "view_mapping_change": "The graph keeps object identity while expanding into the space released by formula memory.",
                    "context_policy": "The formula region retires after its Delta omega role is transferred to the selected cell.",
                    "identity_carriers": ["frequency_cells", "selected cell color", "density curve"],
                    "interpolation_contract": {
                        "geometry_path": "Interpolate the graph region bounds continuously into the released formula space.",
                        "identity_path": "Keep the selected cell and density curve as the same runtime objects.",
                        "view_mapping_path": "Rescale the frequency-axis display mapping without changing its mathematical identity.",
                        "context_release": "Fade formula memory only after the selected cell inherits the Delta omega role.",
                    },
                    "continuity_test": "A learner can track the selected cell continuously from split view into the promoted graph.",
                }
            ],
            "beats": [
                {
                    "beat_id": "cells_gain_width",
                    "start": 0.0,
                    "end": 4.5,
                    "narration_cue": "points become cells",
                    "active_objects": ["points", "cells"],
                    "visible_change": "points expand into cells",
                    "cause": "Delta omega gives each cell a width",
                    "knowledge_before": "The learner sees only sampled frequency points.",
                    "visual_evidence": "Each point expands into a disjoint interval with a visible width brace.",
                    "learner_inference": "A frequency sample can represent an interval contribution rather than an isolated coordinate.",
                    "concepts_available_before": [],
                    "concepts_introduced": ["interval_contribution"],
                    "max_new_concepts": 1,
                    "min_settle_seconds": 1.2,
                    "pointing_target_ids": ["selected_cell"],
                    "evidence_mode": "concrete_action",
                    "exit": ["point-only state"],
                },
                {
                    "beat_id": "cells_refine_to_integral",
                    "start": 4.5,
                    "end": 9.2,
                    "narration_cue": "refine into an integral",
                    "active_objects": ["rectangles", "density curve"],
                    "visible_change": "rectangles narrow and approach the curve",
                    "cause": "L increases",
                    "knowledge_before": "The learner knows one rectangle area corresponds to one sum term.",
                    "visual_evidence": "The full rectangle family refines while preserving the density envelope.",
                    "learner_inference": "The sum of shrinking interval contributions approaches the integral.",
                    "concepts_available_before": ["interval_contribution"],
                    "concepts_introduced": ["riemann_limit"],
                    "max_new_concepts": 1,
                    "min_settle_seconds": 1.2,
                    "pointing_target_ids": ["frequency_cells"],
                    "evidence_mode": "continuous_transform",
                    "exit": ["finite cell borders"],
                },
            ],
            "clause_locks": [
                {
                    "cue_id": "formula_delta",
                    "spoken_start": 0.5,
                    "spoken_clause": "cell width",
                    "object_id": "riemann_formula",
                    "expected_change": "Delta omega token receives focus with the selected cell.",
                },
                {
                    "cue_id": "graph_promote",
                    "spoken_start": 4.5,
                    "spoken_clause": "refine into an integral",
                    "object_id": "frequency_cells",
                    "expected_change": "The same cell family promotes and refines under increasing L.",
                },
            ],
            "history_decisions": [
                {
                    "history_record_id": hit["record_id"],
                    "decision": "adapt",
                    "reason": "Keep the mathematical cell-width driver and inspect its prior review state before adapting layout.",
                    "planned_influence": "Reuse its identity-carrier idea while retaining this scene's selected cell and dynamic promotion.",
                    "evidence_target": "split_term_checkpoint and promotion_midpoint",
                }
                for hit in packet["hits"]
            ],
            "regression_prevention": [
                {
                    "pattern_key": issue["pattern_key"],
                    "prevention": "Register the finite cells and their refinement as explicit beat-owned objects.",
                    "evidence_target": "QC frames at every refinement step",
                }
                for issue in profile["regressions"]
            ],
            "formula_history": ["finite Riemann sum", "cell contribution", "continuous integral"],
            "formula_choreography": [
                {
                    "cue_id": "formula_delta",
                    "spoken_anchor": "cell width",
                    "object_id": "riemann_formula",
                    "target_token": "Delta omega",
                    "visual_action": "Give the width token and selected rectangle one held scale pulse.",
                    "emphasis_mode": "scale_then_restore",
                    "rest_geometry_policy": "Restore the exact row bbox after the pulse.",
                },
                {
                    "cue_id": "formula_integral",
                    "spoken_anchor": "becomes an integral",
                    "object_id": "riemann_formula",
                    "target_token": "integral sign",
                    "visual_action": "Transform the retained sum ancestry, then give the integral sign one held scale pulse.",
                    "emphasis_mode": "scale_then_restore",
                    "rest_geometry_policy": "Restore the exact row bbox after the pulse.",
                },
            ],
            "causal_step_ids": ["finite_object", "refining_parameter", "intermediate_state", "limiting_object"],
        }

    def make_telemetry(self, profile: dict) -> dict:
        def graph_object(bounds: list[float]) -> dict:
            return {
                "id": "frequency_cells",
                "kind": "graph",
                "region": "graph",
                "semantic_role": "truthful Riemann cells and density envelope",
                "bbox": bounds,
                "opacity": 1.0,
                "focal": True,
            }

        formula_object = {
            "id": "riemann_formula",
            "kind": "formula",
            "region": "formula",
            "semantic_role": "persistent symbolic ancestry",
            "bbox": [0.74, 0.65, 0.95, 0.88],
            "opacity": 1.0,
            "focal": False,
            "font_px": 40,
        }
        selected_cell = {
            "id": "selected_cell",
            "kind": "marker",
            "region": "graph",
            "semantic_role": "one selected interval contribution",
            "bbox": [0.28, 0.30, 0.34, 0.72],
            "opacity": 1.0,
            "focal": False,
        }
        snapshots = []
        for time in (0.0, 2.5, 4.4, 4.5):
            snapshots.append(
                {
                    "time": time,
                    "stage_state_id": "split_context",
                    "math_state_id": "L=small",
                    "primary_regions": ["graph"],
                    "objects": [graph_object([0.06, 0.24, 0.66, 0.90]), dict(selected_cell), dict(formula_object)],
                }
            )
        for time in (4.825, 7.0, 9.8):
            snapshots.append(
                {
                    "time": time,
                    "stage_state_id": "graph_promoted",
                    "math_state_id": "L=large",
                    "primary_regions": ["graph"],
                    "objects": [graph_object([0.06, 0.24, 0.95, 0.90]), dict(selected_cell)],
                }
            )
        telemetry = {
            "schema": "lecture-animation-authoring-telemetry-v2",
            "profile_hash": profile["profile_hash"],
            "scene_slug": "g002c_riemann_sum_limit",
            "capture_source": {"mode": "runtime_export", "source_path": "src/scenes/g002c/audit.py"},
            "frame": {"width": 1920, "height": 1080, "fps": 30, "duration": 10.0},
            "thresholds": {
                "max_visual_lag_seconds": 0.25,
                "max_visual_lead_seconds": 0.35,
                "max_transition_seconds": 0.75,
                "max_linger_seconds": 0.5,
                "min_gap_normalized": 0.008,
            },
            "math_object_bindings": [
                {
                    "visual_object_id": "frequency_cells",
                    "math_object_id": "frequency_partition_math",
                    "display_mapping_id": "frequency_partition_view",
                    "driver_ids": ["L"],
                    "samples": [
                        {"time": 0.0, "math_state_id": "L=small", "driver_values": {"L": 8}, "passed": True},
                        {"time": 7.0, "math_state_id": "L=large", "driver_values": {"L": 32}, "passed": True},
                    ],
                },
                {
                    "visual_object_id": "riemann_formula",
                    "math_object_id": "riemann_formula_math",
                    "display_mapping_id": "riemann_formula_view",
                    "driver_ids": [],
                    "samples": [
                        {"time": 0.0, "math_state_id": "finite_sum", "driver_values": {}, "passed": True},
                        {"time": 4.0, "math_state_id": "integral_limit", "driver_values": {}, "passed": True},
                    ],
                },
            ],
            "display_mapping_checks": [
                {
                    "mapping_id": "frequency_partition_view",
                    "source_object_id": "frequency_partition_math",
                    "mode": "uniform_scale",
                    "passed": True,
                    "observed_preserved_invariants": ["partition order", "Delta omega relation"],
                    "observed_distortions": [],
                    "forbidden_inference_violations": [],
                },
                {
                    "mapping_id": "riemann_formula_view",
                    "source_object_id": "riemann_formula_math",
                    "mode": "identity",
                    "passed": True,
                    "observed_preserved_invariants": ["formula token ancestry"],
                    "observed_distortions": [],
                    "forbidden_inference_violations": [],
                },
            ],
            "representation_checks": [
                {
                    "technique_id": "term_split_then_promote",
                    "value_channel": "cognitive",
                    "passed": True,
                    "observed_checkpoint_ids": [
                        "split_context",
                        "split_context->graph_promoted",
                        "graph_promoted",
                    ],
                    "view_ids_observed": ["graph", "formula"],
                    "math_object_ids_observed": [
                        "frequency_partition_math",
                        "riemann_formula_math",
                    ],
                    "display_mapping_ids_observed": [
                        "frequency_partition_view",
                        "riemann_formula_view",
                    ],
                    "driver_ids_observed": ["L"],
                    "observed_value": "The selected cell remains identifiable while its formula memory retires and the same graph expands.",
                    "removal_test_observation": "The formula-term ancestry is no longer pointable when the temporary split is removed.",
                    "identity_carriers_verified": [
                        "frequency_cells",
                        "selected cell color",
                        "density curve",
                    ],
                }
            ],
            "visual_finish_checks": [
                {
                    "stage_state_id": "split_context",
                    "primary_object_ids": ["frequency_cells"],
                    "hierarchy_distinguishable": True,
                    "thumbnail_readable": True,
                    "negative_space_job_visible": True,
                    "animatic_composition_representative": True,
                    "generic_default_residue": [],
                    "observation": "At full and thumbnail size the warm selected cell is primary, formula memory is supporting, and the gap between them carries the identity handoff.",
                },
                {
                    "stage_state_id": "graph_promoted",
                    "primary_object_ids": ["frequency_cells"],
                    "hierarchy_distinguishable": True,
                    "thumbnail_readable": True,
                    "negative_space_job_visible": True,
                    "animatic_composition_representative": True,
                    "generic_default_residue": [],
                    "observation": "At full and thumbnail size the expanded partition and density envelope own the frame without stale formula residue or unowned empty space.",
                },
            ],
            "math_invariant_checks": [
                {
                    "invariant_id": "cells_follow_L",
                    "object_id": "frequency_cells",
                    "evidence_type": "runtime_assertion",
                    "passed": True,
                    "observed_relation": "Every measured cell width equals two pi divided by the active L.",
                    "samples": [
                        {"time": 2.5, "error": 0.0},
                        {"time": 7.0, "error": 0.0},
                    ],
                },
                {
                    "invariant_id": "formula_keeps_ancestry",
                    "object_id": "riemann_formula",
                    "evidence_type": "formula_handoff",
                    "passed": True,
                    "observed_relation": "The Delta omega token remains visible until the serialized integral handoff.",
                    "samples": [
                        {"time": 1.0, "visible": True},
                        {"time": 4.0, "visible": True},
                    ],
                },
            ],
            "snapshots": snapshots,
            "cues": [
                {
                    "cue_id": "formula_delta",
                    "object_id": "riemann_formula",
                    "change_type": "token attention transfer",
                    "spoken_start": 0.5,
                    "spoken_end": 1.0,
                    "visual_start": 0.45,
                    "visual_end": 1.2,
                    "semantic_end": 1.0,
                    "transition_seconds": 0.25,
                    "state_before": {"M": "L=small", "D": "split", "A": "sum token"},
                    "state_after": {"M": "L=small", "D": "split", "A": "Delta omega token"},
                    "change_vector": ["A"],
                    "from_region": "formula",
                    "to_region": "formula",
                },
                {
                    "cue_id": "formula_integral",
                    "object_id": "riemann_formula",
                    "change_type": "token ancestry transform",
                    "spoken_start": 3.7,
                    "spoken_end": 4.2,
                    "visual_start": 3.65,
                    "visual_end": 4.4,
                    "semantic_end": 4.2,
                    "transition_seconds": 0.35,
                    "state_before": {"M": "L=small", "D": "split", "A": "Delta omega token"},
                    "state_after": {"M": "L=small", "D": "split", "A": "integral token"},
                    "change_vector": ["A"],
                    "from_region": "formula",
                    "to_region": "formula",
                },
                {
                    "cue_id": "graph_promote",
                    "object_id": "frequency_cells",
                    "change_type": "driver refinement and semantic zoom",
                    "spoken_start": 4.5,
                    "spoken_end": 5.2,
                    "visual_start": 4.45,
                    "visual_end": 9.5,
                    "semantic_end": 9.2,
                    "transition_seconds": 0.65,
                    "state_before": {"M": "L=small", "D": "split graph", "A": "graph"},
                    "state_after": {"M": "L=large", "D": "promoted graph", "A": "graph"},
                    "change_vector": ["M", "D"],
                    "math_driver_event": "L increases and recomputes every frequency cell.",
                    "identity_carrier": "Selected cell color and density curve persist through the promotion.",
                },
            ],
            "formula_rows": [
                {
                    "object_id": "riemann_formula",
                    "row_id": "finite_sum",
                    "typesetting_mode": "single_expression",
                    "row_bbox": [0.74, 0.76, 0.95, 0.88],
                    "anchor_x_normalized": 0.80,
                },
                {
                    "object_id": "riemann_formula",
                    "row_id": "integral",
                    "typesetting_mode": "single_expression",
                    "row_bbox": [0.74, 0.65, 0.95, 0.75],
                    "anchor_x_normalized": 0.80,
                },
            ],
            "emphasis_checks": [
                {
                    "cue_id": "formula_delta",
                    "object_id": "riemann_formula",
                    "target_id": "Delta omega",
                    "mode": "scale_then_restore",
                    "before_bbox": [0.80, 0.80, 0.84, 0.84],
                    "after_bbox": [0.80, 0.80, 0.84, 0.84],
                },
                {
                    "cue_id": "formula_integral",
                    "object_id": "riemann_formula",
                    "target_id": "integral sign",
                    "mode": "scale_then_restore",
                    "before_bbox": [0.78, 0.68, 0.82, 0.74],
                    "after_bbox": [0.78, 0.68, 0.82, 0.74],
                },
            ],
            "emphasis_events": [
                {
                    "cue_id": "formula_delta",
                    "object_id": "riemann_formula",
                    "target_id": "Delta omega",
                    "mode": "scale_then_restore",
                    "onset_seconds": 0.30,
                    "hold_seconds": 0.18,
                    "recovery_seconds": 0.34,
                    "total_seconds": 0.82,
                    "start_time": 0.5,
                    "peak_time": 0.8,
                    "hold_end_time": 0.98,
                    "end_time": 1.32,
                    "restored": True,
                    "box_trace": False,
                    "target_scope": "whole_expression",
                    "proxy_layer": True,
                },
                {
                    "cue_id": "formula_integral",
                    "object_id": "riemann_formula",
                    "target_id": "integral sign",
                    "mode": "scale_then_restore",
                    "onset_seconds": 0.30,
                    "hold_seconds": 0.18,
                    "recovery_seconds": 0.34,
                    "total_seconds": 0.82,
                    "start_time": 5.5,
                    "peak_time": 5.8,
                    "hold_end_time": 5.98,
                    "end_time": 6.32,
                    "restored": True,
                    "box_trace": False,
                    "target_scope": "whole_expression",
                    "proxy_layer": True,
                },
            ],
            "motion_transitions": [
                {
                    "transition_id": "split_context->graph_promoted",
                    "start": 4.45,
                    "end": 5.20,
                    "duration": 0.75,
                    "rate_profile": "matched_sine_halves",
                    "continuous_path": True,
                    "midpoint_time": 4.825,
                    "matched_midpoint_velocity": True,
                }
            ],
            "relation_encodings": [
                {
                    "relation_id": "cells_to_formula",
                    "method": "temporal_sync",
                    "from_region": "graph",
                    "to_region": "formula",
                    "evidence_object_id": "frequency_cells",
                    "path_length_normalized": 0.0,
                    "crosses_protected_region": False
                }
            ],
            "allowed_overlaps": [],
            "semantic_events": [
                {
                    "beat_id": "cells_gain_width",
                    "start": 0.5,
                    "end": 2.5,
                    "settle_end": 4.0,
                    "settle_seconds": 1.5,
                    "cause_object_ids": ["riemann_formula"],
                    "result_object_ids": ["selected_cell"],
                    "concepts_introduced": ["interval_contribution"],
                    "action_count": 2,
                    "evidence_mode": "concrete_action",
                },
                {
                    "beat_id": "cells_refine_to_integral",
                    "start": 4.5,
                    "end": 7.0,
                    "settle_end": 8.5,
                    "settle_seconds": 1.5,
                    "cause_object_ids": ["selected_cell"],
                    "result_object_ids": ["frequency_cells"],
                    "concepts_introduced": ["riemann_limit"],
                    "action_count": 2,
                    "evidence_mode": "continuous_transform",
                },
            ],
        }
        for snapshot in telemetry["snapshots"]:
            snapshot["layout_atoms"] = [
                {
                    "atom_id": f"{item['id']}-atom",
                    "parent_object_id": item["id"],
                    "kind": "formula_fragment"
                    if item.get("kind") == "formula"
                    else "solid",
                    "bbox": list(item["bbox"]),
                    "opacity": item.get("opacity", 1.0),
                }
                for item in snapshot["objects"]
                if item.get("kind") in {"formula", "title", "body", "label", "tick_label"}
            ]
        return telemetry

    def test_history_profile_and_scene_plan(self) -> None:
        records = pipeline.build_history_records(self.root)
        hits = pipeline.search_history_records(records, "projection frequency cells partial sum", limit=4)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["episode"], self.old_episode.name)
        grammar_hits = pipeline.search_history_records(
            records,
            "compare corresponding elements across views by moving and morphing instead of a straight arrow",
            limit=4,
            record_types={"visual_grammar"},
        )
        self.assertTrue(grammar_hits)
        self.assertEqual(grammar_hits[0]["pattern_id"], "identity_carrier_cross_view_transform")
        self.assertTrue(grammar_hits[0]["source_anchors"])

        base_profile = self.make_profile()
        policy = pipeline.compile_live_policy_data(self.episode, base_profile)
        policy_path = self.episode / "review" / "v2" / "test_policy.json"
        self.write_json(policy_path, policy)
        profile = pipeline.attach_autopilot_contract(
            base_profile, policy, policy_path, self.root
        )
        self.assertTrue(pipeline.validate_profile_hash(profile))
        self.assertEqual(profile["autopilot_contract_version"], 8)
        self.assertIn("limit_process", profile["tags"])
        self.assertNotIn("history_hits", profile)
        self.assertEqual(profile["regressions"][0]["pattern_key"], "riemann_sum_named_but_not_visualized")

        bundle = self.make_design_bundle(profile)
        self.assertTrue(bundle[2]["valid"])
        self.assertTrue(bundle[3]["production_hits"])
        anchored = json.loads(json.dumps(bundle[1]))
        anchored["history_consulted"] = True
        gate = pipeline.validate_design_deliberation_data(profile, bundle[0], anchored)
        self.assertFalse(gate["valid"])
        duplicated = json.loads(json.dumps(bundle[1]))
        duplicated["hypotheses"][1] = dict(duplicated["hypotheses"][0])
        duplicated["hypotheses"][1]["id"] = "copy_of_cell_atlas"
        duplicated["hypotheses"][1]["selected"] = False
        gate = pipeline.validate_design_deliberation_data(profile, bundle[0], duplicated)
        self.assertTrue(any("too similar" in error for error in gate["errors"]))
        cosmetic_rewrite = json.loads(json.dumps(bundle[1]))
        cosmetic_rewrite["hypotheses"][1] = json.loads(
            json.dumps(cosmetic_rewrite["hypotheses"][0])
        )
        cosmetic_rewrite["hypotheses"][1].update(
            {
                "id": "same_layout_with_new_words",
                "representation_class": "cartesian_cell_equation_stage",
                "technical_mechanism": "Rephrase the same graph-and-formula split as a Cartesian cell stage with an equation board.",
                "stage_logic": "Place a Cartesian cell field beside an equation memory lane using different wording.",
                "view_mapping": "Render the same rectangles and formula in the same two-region arrangement.",
                "selected": False,
            }
        )
        cosmetic_rewrite["hypotheses"][1]["contrast_against"] = [
            {
                "hypothesis_id": "single_graph_baseline",
                "changed_axes": ["stage_topology", "attention_handoff"],
                "learner_visible_consequence": "The same split still makes the formula term pointable.",
            }
        ]
        gate = pipeline.validate_design_deliberation_data(
            profile, bundle[0], cosmetic_rewrite
        )
        self.assertTrue(
            any(
                "DESIGN_HYPOTHESIS_DUPLICATE_SIGNATURE" in error
                for error in gate["errors"]
            )
        )
        plan = self.make_plan(profile, bundle)
        self.assertEqual(pipeline.validate_scene_plan_data(profile, plan), [])
        unowned_decoration = json.loads(json.dumps(plan))
        unowned_decoration["representation_budget"]["decorative_only_elements"] = [
            "glowing border with no cognitive, continuity, or finish contract"
        ]
        self.assertTrue(
            any(
                "decorative-only" in error
                for error in pipeline.validate_scene_plan_data(profile, unowned_decoration)
            )
        )
        missing_finish_contract = json.loads(json.dumps(plan))
        missing_finish_contract["representation_budget"].pop("visual_finish_contract")
        self.assertTrue(
            any(
                "VISUAL_FINISH_CONTRACT_MISSING" in error
                for error in pipeline.validate_scene_plan_data(
                    profile, missing_finish_contract
                )
            )
        )
        distracting_finish = json.loads(json.dumps(plan))
        distracting_finish["representation_budget"]["techniques"].append(
            {
                "technique_id": "ambient_surface_finish",
                "technique_class": "material_finish",
                "view_ids": ["graph"],
                "math_object_ids": ["frequency_partition_math"],
                "display_mapping_ids": ["frequency_partition_view"],
                "driver_ids": [],
                "value_channel": "aesthetic_finish",
                "value_claim": "A restrained material treatment makes the graph feel intentionally finished.",
                "removal_failure": "Without it the stage reads as a raw default render rather than a coherent lesson.",
                "unique_learning_job": "Improve material coherence without adding a new focal object or mathematical claim.",
                "hidden_relation_or_false_inference": "No mathematical relation is added; the finish only supports visual hierarchy.",
                "counterfactual_without": "Without the finish, the mathematical view remains correct but visibly unfinished.",
                "not_redundant_with": ["term_split_then_promote"],
                "not_redundant_reason": "It changes material coherence while the other technique owns the cell-to-term explanation.",
                "identity_carriers": [],
                "evidence_checkpoint_ids": ["graph_promoted"],
                "focal_policy": "may_be_primary",
                "semantic_claim": "none",
                "protected_region_policy": "Stay outside every active graph and formula protected region.",
            }
        )
        self.assertTrue(
            any(
                "never_primary" in error
                for error in pipeline.validate_scene_plan_data(profile, distracting_finish)
            )
        )
        decorative_orbit = json.loads(json.dumps(plan))
        decorative_orbit["representation_budget"]["techniques"].append(
            {
                "technique_id": "decorative_orbit",
                "technique_class": "camera_orbit_3d",
                "view_ids": ["graph"],
                "math_object_ids": ["frequency_partition_math"],
                "display_mapping_ids": ["frequency_partition_view"],
                "driver_ids": ["L"],
                "value_channel": "cognitive",
                "value_claim": "Orbit the flat graph to make the shot feel more dynamic.",
                "removal_failure": "Removing the orbit changes style but does not remove mathematical information.",
                "unique_learning_job": "Add motion around the already readable two-dimensional frequency graph.",
                "hidden_relation_or_false_inference": "No lost depth relation is currently named by the scene.",
                "counterfactual_without": "The complete Riemann-cell explanation remains visible without the orbit.",
                "not_redundant_with": ["term_split_then_promote"],
                "not_redundant_reason": "It changes camera motion, although it does not add a new relation.",
                "identity_carriers": ["frequency_cells"],
                "evidence_checkpoint_ids": ["graph_promoted"],
            }
        )
        self.assertTrue(
            any(
                "THREE_D_NECESSITY_UNPROVEN" in error
                for error in pipeline.validate_scene_plan_data(profile, decorative_orbit)
            )
        )
        full_clear_plan = json.loads(json.dumps(plan))
        full_clear_transition = full_clear_plan["stage_transitions"][0]
        full_clear_transition["continuity_mode"] = "full_clear"
        full_clear_transition["identity_carriers"] = []
        full_clear_transition["view_mapping_change"] = "A full-clear continuity break retires the first object family before the next one enters."
        full_clear_transition["context_policy"] = "Full-clear every outgoing object before introducing the unrelated target state."
        full_clear_transition["interpolation_contract"]["identity_path"] = "No object identity crosses this declared full-clear boundary."
        self.assertEqual(pipeline.validate_scene_plan_data(profile, full_clear_plan), [])
        missing_mode_plan = json.loads(json.dumps(full_clear_plan))
        missing_mode_plan["stage_transitions"][0].pop("continuity_mode")
        self.assertTrue(
            any(
                "continuity_mode" in error
                for error in pipeline.validate_scene_plan_data(profile, missing_mode_plan)
            )
        )
        self.assertEqual(pipeline.validate_design_chain_data(profile, plan, *bundle), [])
        generic_no_fit = json.loads(json.dumps(plan))
        generic_no_fit["history_decisions"] = [
            {
                "decision": "no_fit",
                "reason": "None of the retrieved cases fit this scene, so ignore every individual hit.",
            }
        ]
        self.assertTrue(
            any(
                "one individual decision" in error
                for error in pipeline.validate_design_chain_data(
                    profile, generic_no_fit, *bundle
                )
            )
        )
        telemetry = self.make_telemetry(profile)
        qc = pipeline.validate_authoring_qc_data(profile, plan, telemetry)
        self.assertTrue(qc["valid"], qc["issues"])
        missing_representation_evidence = json.loads(json.dumps(telemetry))
        missing_representation_evidence["representation_checks"] = []
        qc = pipeline.validate_authoring_qc_data(
            profile, plan, missing_representation_evidence
        )
        self.assertTrue(
            any(
                item["code"] == "REPRESENTATION_EVIDENCE_MISSING"
                for item in qc["issues"]
            )
        )
        missing_visual_finish = json.loads(json.dumps(telemetry))
        missing_visual_finish["visual_finish_checks"] = []
        qc = pipeline.validate_authoring_qc_data(
            profile, plan, missing_visual_finish
        )
        self.assertTrue(
            any(
                item["code"] == "VISUAL_FINISH_EVIDENCE_MISSING"
                for item in qc["issues"]
            )
        )

        local_zoom_plan = json.loads(json.dumps(plan))
        local_zoom_mapping = local_zoom_plan["display_mappings"][0]
        local_zoom_mapping["mode"] = "local_zoom"
        local_zoom_mapping["verification"]["distorted_quantities"] = [
            "screen scale of the source interval"
        ]
        local_zoom_mapping["verification"]["forbidden_inferences"] = [
            "the displayed width is the mathematical increment"
        ]
        local_zoom_mapping["zoom_contract"] = {
            "source_parameter_id": "L",
            "max_source_span_fraction": 0.08,
            "requires_context_view": True,
            "requires_zoom_view": True,
            "identity_anchor": "selected_cell",
            "refinement_goal": "local_linearization",
            "approximation_error_metric": "maximum curve-to-tangent vertical error",
            "min_refinement_samples": 3,
            "source_window_math": {
                "coordinate_space_id": "frequency_axis",
                "context_span": 1.0,
                "source_span": 0.08,
                "driver_ids": ["L"],
                "math_state_hash": "local-state-hash-0001",
            },
            "zoom_transform": {
                "kind": "affine",
                "scale": [6.0, 6.0],
                "translation": [0.0, 0.0],
                "orientation_policy": "preserve",
                "scale_policy": "Uniformly magnify both coordinate directions.",
            },
            "correspondence_samples": [
                {
                    "sample_id": "zoom_center",
                    "role": "center",
                    "source_coordinate": [0.0, 0.0],
                },
                {
                    "sample_id": "zoom_left",
                    "role": "boundary_a",
                    "source_coordinate": [-0.04, 0.0],
                },
                {
                    "sample_id": "zoom_right",
                    "role": "boundary_b",
                    "source_coordinate": [0.04, 0.0],
                },
            ],
            "boundary_correspondence": True,
        }
        self.assertEqual(
            pipeline.validate_math_object_display_contract(local_zoom_plan, 6), []
        )
        local_zoom_telemetry = json.loads(json.dumps(telemetry))
        zoom_check = local_zoom_telemetry["display_mapping_checks"][0]
        zoom_check["mode"] = "local_zoom"
        zoom_check["observed_distortions"] = [
            "screen scale of the source interval"
        ]
        zoom_check["zoom_contract_check"] = {
            "source_span_fraction": 0.08,
            "driver_ids": ["L"],
            "math_state_hash": "local-state-hash-0001",
            "context_view_visible": True,
            "zoom_view_visible": True,
            "shared_anchor_verified": True,
            "same_source_identity_verified": True,
            "identity_anchor": "selected_cell",
            "coordinate_tolerance": 1e-9,
            "correspondence_samples": [
                {
                    "sample_id": "zoom_center",
                    "source_coordinate": [0.0, 0.0],
                    "observed_zoom_coordinate": [0.0, 0.0],
                },
                {
                    "sample_id": "zoom_left",
                    "source_coordinate": [-0.04, 0.0],
                    "observed_zoom_coordinate": [-0.24, 0.0],
                },
                {
                    "sample_id": "zoom_right",
                    "source_coordinate": [0.04, 0.0],
                    "observed_zoom_coordinate": [0.24, 0.0],
                },
            ],
            "refinement_samples": [
                {
                    "source_span": 0.08,
                    "curve_value": 0.012,
                    "tangent_value": 0.0,
                    "approximation_error": 0.012,
                },
                {
                    "source_span": 0.04,
                    "curve_value": 0.003,
                    "tangent_value": 0.0,
                    "approximation_error": 0.003,
                },
                {
                    "source_span": 0.02,
                    "curve_value": 0.0008,
                    "tangent_value": 0.0,
                    "approximation_error": 0.0008,
                },
            ],
        }
        qc = pipeline.validate_authoring_qc_data(
            profile, local_zoom_plan, local_zoom_telemetry
        )
        self.assertTrue(qc["valid"], qc["issues"])
        false_large_increment = json.loads(json.dumps(local_zoom_telemetry))
        false_large_increment["display_mapping_checks"][0]["zoom_contract_check"][
            "source_span_fraction"
        ] = 0.40
        false_large_increment["display_mapping_checks"][0]["zoom_contract_check"][
            "context_view_visible"
        ] = False
        false_large_increment["display_mapping_checks"][0]["zoom_contract_check"][
            "refinement_samples"
        ] = [
            {
                "source_span": 0.40,
                "curve_value": 0.20,
                "tangent_value": 0.0,
                "approximation_error": 0.20,
            },
            {
                "source_span": 0.30,
                "curve_value": 0.22,
                "tangent_value": 0.0,
                "approximation_error": 0.22,
            },
            {
                "source_span": 0.20,
                "curve_value": 0.25,
                "tangent_value": 0.0,
                "approximation_error": 0.25,
            },
        ]
        qc = pipeline.validate_authoring_qc_data(
            profile, local_zoom_plan, false_large_increment
        )
        codes = {item["code"] for item in qc["issues"]}
        self.assertIn("LOCAL_INCREMENT_NOT_SMALL", codes)
        self.assertIn("LOCAL_ZOOM_CONTEXT_MISSING", codes)
        self.assertIn("LOCAL_LINEARIZATION_NOT_CONVERGING", codes)
        wrong_correspondence = json.loads(json.dumps(local_zoom_telemetry))
        wrong_correspondence["display_mapping_checks"][0]["zoom_contract_check"][
            "correspondence_samples"
        ][1]["observed_zoom_coordinate"] = [-0.20, 0.0]
        qc = pipeline.validate_authoring_qc_data(
            profile, local_zoom_plan, wrong_correspondence
        )
        self.assertTrue(
            any(
                item["code"] == "LOCAL_ZOOM_BOUNDARY_MISMATCH"
                for item in qc["issues"]
            )
        )
        wrong_math_state = json.loads(json.dumps(local_zoom_telemetry))
        wrong_math_state["display_mapping_checks"][0]["zoom_contract_check"][
            "math_state_hash"
        ] = "different-local-state"
        qc = pipeline.validate_authoring_qc_data(
            profile, local_zoom_plan, wrong_math_state
        )
        self.assertTrue(
            any(
                item["code"] == "LOCAL_ZOOM_MATH_STATE_DRIFT"
                for item in qc["issues"]
            )
        )
        handoff_plan = json.loads(json.dumps(plan))
        handoff_plan["formula_handoffs"] = [
            {
                "handoff_id": "sum_to_integral",
                "outgoing_object_id": "riemann_sum",
                "incoming_object_id": "riemann_integral",
                "minimum_empty_gap_seconds": 0.03,
            }
        ]
        handoff_telemetry = json.loads(json.dumps(telemetry))
        handoff_telemetry["formula_handoffs"] = [
            {
                "handoff_id": "sum_to_integral",
                "outgoing_object_id": "riemann_sum",
                "incoming_object_id": "riemann_integral",
                "gap_seconds": 0.04,
                "overlap_seconds": 0.0,
                "serialized": True,
            }
        ]
        qc = pipeline.validate_authoring_qc_data(profile, handoff_plan, handoff_telemetry)
        self.assertTrue(qc["valid"], qc["issues"])
        overlapping_handoff = json.loads(json.dumps(handoff_telemetry))
        overlapping_handoff["formula_handoffs"][0]["gap_seconds"] = 0.0
        overlapping_handoff["formula_handoffs"][0]["overlap_seconds"] = 0.2
        overlapping_handoff["formula_handoffs"][0]["serialized"] = False
        qc = pipeline.validate_authoring_qc_data(profile, handoff_plan, overlapping_handoff)
        self.assertTrue(any(issue["code"] == "FORMULA_HANDOFF_OVERLAP" for issue in qc["issues"]))
        binding_plan = json.loads(json.dumps(plan))
        binding_plan["identity_bindings"] = [
            {
                "binding_id": "point_to_label",
                "relation": "the label follows the selected point",
                "max_distance_normalized": 0.04,
            }
        ]
        binding_telemetry = json.loads(json.dumps(telemetry))
        binding_telemetry["identity_bindings"] = [
            {
                "binding_id": "point_to_label",
                "relation": "the label follows the selected point",
                "max_distance_normalized": 0.04,
                "samples": [
                    {"time": 1.0, "distance_normalized": 0.02},
                    {"time": 4.0, "distance_normalized": 0.03},
                ],
            }
        ]
        qc = pipeline.validate_authoring_qc_data(profile, binding_plan, binding_telemetry)
        self.assertTrue(qc["valid"], qc["issues"])
        drifting_binding = json.loads(json.dumps(binding_telemetry))
        drifting_binding["identity_bindings"][0]["samples"][1]["distance_normalized"] = 0.2
        qc = pipeline.validate_authoring_qc_data(profile, binding_plan, drifting_binding)
        self.assertTrue(any(issue["code"] == "IDENTITY_BINDING_DRIFT" for issue in qc["issues"]))
        coordinate_plan = json.loads(json.dumps(plan))
        coordinate_plan["coordinate_checks"] = [
            {
                "check_id": "sample_on_axis",
                "object_id": "selected_cell",
                "relation": "the selected sample lies on its declared axis coordinate",
                "max_error_normalized": 0.001,
            }
        ]
        coordinate_telemetry = json.loads(json.dumps(telemetry))
        coordinate_telemetry["coordinate_checks"] = [
            {
                "check_id": "sample_on_axis",
                "object_id": "selected_cell",
                "time": 4.0,
                "relation": "the selected sample lies on its declared axis coordinate",
                "max_error_normalized": 0.001,
                "actual_point": [1.0, 0.0],
                "expected_point": [1.0, 0.0],
                "error_normalized": 0.0,
            }
        ]
        qc = pipeline.validate_authoring_qc_data(profile, coordinate_plan, coordinate_telemetry)
        self.assertTrue(qc["valid"], qc["issues"])
        drifting_coordinate = json.loads(json.dumps(coordinate_telemetry))
        drifting_coordinate["coordinate_checks"][0]["error_normalized"] = 0.02
        qc = pipeline.validate_authoring_qc_data(profile, coordinate_plan, drifting_coordinate)
        self.assertTrue(any(issue["code"] == "COORDINATE_DRIFT" for issue in qc["issues"]))
        missing_novice_event = json.loads(json.dumps(telemetry))
        missing_novice_event["semantic_events"] = []
        qc = pipeline.validate_authoring_qc_data(profile, plan, missing_novice_event)
        self.assertTrue(any(issue["code"] == "NOVICE_EVENT_MISSING" for issue in qc["issues"]))
        invisible_focal = json.loads(json.dumps(telemetry))
        invisible_focal["snapshots"][0]["objects"][0]["opacity"] = 0.0
        qc = pipeline.validate_authoring_qc_data(profile, plan, invisible_focal)
        self.assertTrue(any(issue["code"] == "FOCAL_OBJECT_INVISIBLE" for issue in qc["issues"]))
        orphaned = json.loads(json.dumps(telemetry))
        orphaned["snapshots"][0]["orphan_mobjects"] = [
            {"class_name": "Dot", "bbox": [0.4, 0.4, 0.41, 0.41], "opacity": 1.0}
        ]
        qc = pipeline.validate_authoring_qc_data(profile, plan, orphaned)
        self.assertTrue(any(issue["code"] == "UNOWNED_VISIBLE_MOBJECT" for issue in qc["issues"]))
        word_plan = json.loads(json.dumps(plan))
        word_plan["timing_contract_version"] = "word_anchor_v1"
        word_plan["word_alignment_source"] = {"path": "alignment.json", "sha256": "a" * 64, "scene_start": 100.0}
        word_plan["word_anchors"] = [
            {
                "anchor_id": f"w{index}",
                "token": "词",
                "absolute_start": 100.0 + index * 0.5,
                "absolute_end": 100.2 + index * 0.5,
                "local_start": index * 0.5,
                "visual_action": "change the matching object",
                "target_id": "Delta omega" if index == 1 else f"target-{index}",
                "evidence_type": "emphasis_event" if index == 1 else "runtime_action",
                "evidence_id": "formula_delta" if index == 1 else f"runtime-{index}",
            }
            for index in range(8)
        ]
        self.assertEqual(pipeline.validate_scene_plan_data(profile, word_plan), [])
        word_telemetry = json.loads(json.dumps(telemetry))
        word_telemetry["word_anchor_events"] = [
            {
                "anchor_id": f"w{index}",
                "planned_time": index * 0.5,
                "actual_time": index * 0.5,
                "action": "change",
                "target_id": "Delta omega" if index == 1 else f"target-{index}",
                "evidence_type": "emphasis_event" if index == 1 else "runtime_action",
                "evidence_id": "formula_delta" if index == 1 else f"runtime-{index}",
            }
            for index in range(8)
        ]
        qc = pipeline.validate_authoring_qc_data(profile, word_plan, word_telemetry)
        self.assertTrue(qc["valid"], qc["issues"])
        missing_word_evidence = json.loads(json.dumps(word_telemetry))
        missing_word_evidence["emphasis_events"] = [
            item for item in missing_word_evidence["emphasis_events"] if item["cue_id"] != "formula_delta"
        ]
        qc = pipeline.validate_authoring_qc_data(profile, word_plan, missing_word_evidence)
        self.assertTrue(any(issue["code"] == "WORD_ANCHOR_EVIDENCE_MISSING" for issue in qc["issues"]))
        wrong_word_target = json.loads(json.dumps(word_telemetry))
        wrong_word_target["emphasis_events"][0]["target_id"] = "wrong token"
        qc = pipeline.validate_authoring_qc_data(profile, word_plan, wrong_word_target)
        self.assertTrue(any(issue["code"] == "WORD_ANCHOR_EVIDENCE_TARGET" for issue in qc["issues"]))
        word_telemetry["word_anchor_events"][3]["actual_time"] += 0.2
        qc = pipeline.validate_authoring_qc_data(profile, word_plan, word_telemetry)
        self.assertTrue(any(issue["code"] == "WORD_ANCHOR_VISUAL_DRIFT" for issue in qc["issues"]))
        collided_atoms = json.loads(json.dumps(telemetry))
        collided_atoms["snapshots"][0]["layout_atoms"] = [
            {"atom_id": "formula_left", "parent_object_id": "riemann_formula", "kind": "formula_fragment", "bbox": [0.75, 0.70, 0.84, 0.80], "opacity": 1.0},
            {"atom_id": "formula_right", "parent_object_id": "riemann_formula", "kind": "formula_fragment", "bbox": [0.82, 0.72, 0.91, 0.82], "opacity": 1.0},
        ]
        qc = pipeline.validate_authoring_qc_data(profile, plan, collided_atoms)
        self.assertTrue(any(issue["code"] == "FORMULA_ATOM_COLLISION" for issue in qc["issues"]))
        missing_dense_atoms = json.loads(json.dumps(telemetry))
        for snapshot in missing_dense_atoms["snapshots"]:
            snapshot["layout_atoms"] = []
        qc = pipeline.validate_authoring_qc_data(profile, plan, missing_dense_atoms)
        self.assertTrue(any(issue["code"] == "LAYOUT_ATOM_COVERAGE_MISSING" for issue in qc["issues"]))
        missing_formula_rows = json.loads(json.dumps(telemetry))
        missing_formula_rows["formula_rows"] = []
        qc = pipeline.validate_authoring_qc_data(profile, plan, missing_formula_rows)
        self.assertTrue(
            any(issue["code"] == "FORMULA_ROW_AUDIT_COVERAGE_MISSING" for issue in qc["issues"])
        )
        drifted = json.loads(json.dumps(telemetry))
        drifted["emphasis_checks"][0]["after_bbox"][2] += 0.02
        qc = pipeline.validate_authoring_qc_data(profile, plan, drifted)
        self.assertTrue(any(issue["code"] == "EMPHASIS_GEOMETRY_DRIFT" for issue in qc["issues"]))
        boxed = json.loads(json.dumps(telemetry))
        boxed["emphasis_events"][0]["box_trace"] = True
        qc = pipeline.validate_authoring_qc_data(profile, plan, boxed)
        self.assertTrue(any(issue["code"] == "EMPHASIS_BOX_TRACE" for issue in qc["issues"]))
        jerky = json.loads(json.dumps(telemetry))
        jerky["motion_transitions"][0]["matched_midpoint_velocity"] = False
        qc = pipeline.validate_authoring_qc_data(profile, plan, jerky)
        self.assertTrue(any(issue["code"] == "STAGE_MOTION_MIDPOINT_JERK" for issue in qc["issues"]))
        crossing = json.loads(json.dumps(telemetry))
        crossing["relation_encodings"][0]["crosses_protected_region"] = True
        qc = pipeline.validate_authoring_qc_data(profile, plan, crossing)
        self.assertTrue(any(issue["code"] == "CONNECTOR_CROSSES_PROTECTED_REGION" for issue in qc["issues"]))
        unaudited = json.loads(json.dumps(telemetry))
        unaudited["snapshots"] = [item for item in unaudited["snapshots"] if item["time"] not in {4.5, 4.825}]
        qc = pipeline.validate_authoring_qc_data(profile, plan, unaudited)
        self.assertTrue(any(issue["code"] == "TRANSITION_MIDPOINT_UNAUDITED" for issue in qc["issues"]))
        telemetry["cues"][-1]["change_vector"] = ["D"]
        qc = pipeline.validate_authoring_qc_data(profile, plan, telemetry)
        self.assertTrue(any(issue["code"] == "MDA_VECTOR_MISMATCH" for issue in qc["issues"]))
        plan["stage_transitions"][0]["change_vector"] = ["D"]
        errors = pipeline.validate_scene_plan_data(profile, plan)
        self.assertTrue(any("computed M/D/A change" in error for error in errors))
        plan["stage_transitions"][0]["change_vector"] = ["M", "D"]
        plan["stage_states"][0]["active_regions"][0]["bounds"][1] = 0.05
        errors = pipeline.validate_scene_plan_data(profile, plan)
        self.assertTrue(any("subtitle" in error for error in errors))

    def test_manifest_review_and_stale_rejection(self) -> None:
        profile = self.make_profile()
        bundle = self.make_design_bundle(profile)
        challenge, deliberation, design_gate, precedent_packet = bundle
        plan = self.make_plan(profile, bundle)
        profile_path = self.episode / "review" / "v2" / "profile.json"
        plan_path = self.episode / "review" / "v2" / "plan.json"
        challenge_path = self.episode / "review" / "v2" / "challenge.json"
        deliberation_path = self.episode / "review" / "v2" / "deliberation.json"
        design_gate_path = self.episode / "review" / "v2" / "design_gate.json"
        precedent_path = self.episode / "review" / "v2" / "precedents.json"
        telemetry_path = self.episode / "review" / "v2" / "telemetry.json"
        authoring_qc_path = self.episode / "review" / "v2" / "authoring_qc.json"
        episode_spine_path = self.episode / "review" / "v2" / "review_episode_spine.json"
        self.write_json(profile_path, profile)
        self.write_json(plan_path, plan)
        self.write_json(challenge_path, challenge)
        self.write_json(deliberation_path, deliberation)
        self.write_json(design_gate_path, design_gate)
        self.write_json(precedent_path, precedent_packet)
        telemetry = self.make_telemetry(profile)
        authoring_qc = pipeline.validate_authoring_qc_data(profile, plan, telemetry)
        self.assertTrue(authoring_qc["valid"], authoring_qc["issues"])
        self.write_json(telemetry_path, telemetry)
        self.write_json(authoring_qc_path, authoring_qc)
        episode_spine = {
            "schema": "lecture-animation-episode-visual-spine-v2",
            "episode": pipeline.relative_or_absolute(self.episode, self.root),
            "production_mode": "main_producer",
        }
        episode_spine["spine_hash"] = pipeline.object_hash(episode_spine)
        self.write_json(episode_spine_path, episode_spine)

        source = self.episode / "src" / "scenes" / "g002c_riemann_sum_limit"
        source.mkdir(parents=True)
        (source / "composer.py").write_text("DRIVER = 'L'\n", encoding="utf-8")
        text_baseline_path = self.episode / "review" / "v2" / "text_baseline.json"
        text_audit_path = self.episode / "review" / "v2" / "text_audit.json"
        inventory = pipeline.scan_screen_text_inventory(source, self.root)
        text_baseline = {
            "schema": "lecture-animation-screen-text-baseline-v1",
            "scene_slug": "g002c_riemann_sum_limit",
            "baseline_label": "accepted-v1",
            "source_path": pipeline.relative_or_absolute(source, self.root),
            "source_sha256": pipeline.artifact_snapshot(source, self.root)["sha256"],
            "inventory": inventory,
        }
        text_baseline["baseline_hash"] = pipeline.object_hash(text_baseline)
        self.write_json(text_baseline_path, text_baseline)
        text_audit = {
            "schema": "lecture-animation-screen-text-audit-v1",
            "valid": True,
            "scene_slug": "g002c_riemann_sum_limit",
            "mode": "exact",
            "baseline_path": pipeline.relative_or_absolute(text_baseline_path, self.root),
            "baseline_hash": text_baseline["baseline_hash"],
            "candidate_source_path": pipeline.relative_or_absolute(source, self.root),
            "candidate_source_sha256": pipeline.artifact_snapshot(source, self.root)["sha256"],
            "baseline_inventory": {},
            "candidate_inventory": {},
            "errors": [],
        }
        text_audit["report_hash"] = pipeline.object_hash(text_audit)
        self.write_json(text_audit_path, text_audit)
        artifacts = {
            "profile": profile_path,
            "design_challenge": challenge_path,
            "deliberation": deliberation_path,
            "design_gate": design_gate_path,
            "precedent_packet": precedent_path,
            "plan": plan_path,
            "episode_spine": episode_spine_path,
            "source": source,
            "timeline": self.episode / "timeline.json",
            "telemetry": telemetry_path,
            "authoring_qc": authoring_qc_path,
            "review_mp4": self.episode / "review.mp4",
            "render_receipt": self.episode / "review" / "v2" / "render_receipt.json",
            "qc": self.episode / "qc",
            "layout_audit": self.episode / "layout.json",
            "emphasis_frame_audit": self.episode / "emphasis-frames.json",
            "srt": self.episode / "scene.srt",
            "audio": self.episode / "scene.wav",
            "text_inventory_baseline": text_baseline_path,
            "text_inventory_audit": text_audit_path,
        }
        artifacts["review_mp4"].write_bytes(b"fake-mp4-v1")
        artifacts["qc"].mkdir()
        (artifacts["qc"] / "frame.png").write_bytes(b"frame")
        for index in range(1, 13):
            (artifacts["qc"] / f"probe-{index:02d}.png").write_bytes(f"probe-frame-{index}".encode())
        self.write_json(artifacts["layout_audit"], {"valid": True})
        self.write_json(
            artifacts["emphasis_frame_audit"],
            {
                "schema": "lecture-animation-emphasis-frame-audit-v2",
                "scene_slug": "g002c_riemann_sum_limit",
                "valid": True,
                "events": [{"cue_id": "formula_delta", "valid": True}],
                "issues": [],
            },
        )
        artifacts["srt"].write_text("1\n00:00:00,000 --> 00:00:01,000\nline\n", encoding="utf-8")
        artifacts["audio"].write_bytes(b"fake-wave")
        render_receipt = {
            "schema": "lecture-animation-render-receipt-v1",
            "scene_slug": "g002c_riemann_sum_limit",
            "source_sha256": pipeline.artifact_snapshot(source, self.root)["sha256"],
            "review_mp4_sha256": pipeline.artifact_snapshot(artifacts["review_mp4"], self.root)["sha256"],
            "telemetry_sha256": pipeline.artifact_snapshot(telemetry_path, self.root)["sha256"],
            "render_command": ["uv", "run", "manim", "-qh", "composer.py", "Scene"],
            "tool_versions": {"manim": "test-1.0", "python": "test-3.12"},
            "reused_media": False,
            "fresh_media_directory": "videos/0007/review/fresh-render",
            "rendered_at": "2026-07-10T00:00:00+00:00",
        }
        render_receipt["receipt_hash"] = pipeline.object_hash(render_receipt)
        self.write_json(artifacts["render_receipt"], render_receipt)

        manifest = {
            "schema": "lecture-animation-review-manifest-v2",
            "created_at": "2026-07-10T00:00:00+00:00",
            "episode": pipeline.relative_or_absolute(self.episode, self.root),
            "scene_slug": "g002c_riemann_sum_limit",
            "profile_hash": profile["profile_hash"],
            "artifacts": {
                key: pipeline.artifact_snapshot(path, self.root) for key, path in sorted(artifacts.items())
            },
        }
        manifest["manifest_hash"] = pipeline.object_hash(manifest)
        self.assertEqual(pipeline.verify_manifest_data(manifest, self.root), [])
        stale_render_receipt = json.loads(json.dumps(render_receipt))
        stale_render_receipt["source_sha256"] = "stale-source"
        stale_render_receipt.pop("receipt_hash")
        stale_render_receipt["receipt_hash"] = pipeline.object_hash(stale_render_receipt)
        self.write_json(artifacts["render_receipt"], stale_render_receipt)
        stale_render_manifest = json.loads(json.dumps(manifest))
        stale_render_manifest["artifacts"]["render_receipt"] = pipeline.artifact_snapshot(
            artifacts["render_receipt"], self.root
        )
        stale_render_manifest.pop("manifest_hash")
        stale_render_manifest["manifest_hash"] = pipeline.object_hash(stale_render_manifest)
        self.assertTrue(
            any(
                "render receipt is not bound to the frozen source" in error
                for error in pipeline.verify_manifest_data(stale_render_manifest, self.root)
            )
        )
        self.write_json(artifacts["render_receipt"], render_receipt)
        falsification_probe = pipeline.self_review_probe_draft_data(manifest, profile, plan)
        for index, probe in enumerate(falsification_probe["probes"], 1):
            probe["expected_state"] = "The declared driver keeps the selected cell and its formula contribution on the same mathematical state."
            probe["actual_observed_state"] = "The decoded candidate frame shows the selected cell width, density height, and formula token in agreement."
            probe["falsification_attempt"] = "The author independently recomputed the cell width and tried to find a frame where the carrier or formula disagreed."
            frame_path = artifacts["qc"] / f"probe-{index:02d}.png"
            probe["evidence"]["frame_path"] = pipeline.relative_or_absolute(frame_path, self.root)
            probe["evidence"]["frame_sha256"] = hashlib.sha256(frame_path.read_bytes()).hexdigest()
            probe["independent_check"] = {
                "method": "Recompute Delta omega from L and compare the decoded frame coordinate with the formula value.",
                "expected": "The selected cell width equals two pi divided by the displayed L value.",
                "actual": "The independently measured width agrees with the computed value at this timestamp.",
                "tolerance": "0.5 screen pixels",
                "check_type": "numeric",
                "expected_value": 10.0 + index,
                "actual_value": 10.2 + index,
                "tolerance_value": 0.5,
                "passed": True,
            }
            probe["result"] = "falsification_not_found"
        falsification_probe["verdict"] = "probe_passed"
        falsification_probe["probe_hash"] = pipeline.object_hash(falsification_probe)
        self.assertEqual(
            pipeline.validate_self_review_probe_data(
                falsification_probe, manifest, profile, plan, repo_root=self.root
            ),
            [],
        )
        duplicate_frame_probe = json.loads(json.dumps(falsification_probe))
        duplicate_frame_probe["probes"][1]["evidence"] = json.loads(
            json.dumps(duplicate_frame_probe["probes"][0]["evidence"])
        )
        duplicate_frame_probe.pop("probe_hash")
        duplicate_frame_probe["probe_hash"] = pipeline.object_hash(duplicate_frame_probe)
        self.assertTrue(
            any(
                "distinct decoded frame" in error
                for error in pipeline.validate_self_review_probe_data(
                    duplicate_frame_probe, manifest, profile, plan, repo_root=self.root
                )
            )
        )
        moved_challenge_probe = json.loads(json.dumps(falsification_probe))
        moved_challenge_probe["probes"][0]["timestamp_seconds"] += 0.25
        moved_challenge_probe.pop("probe_hash")
        moved_challenge_probe["probe_hash"] = pipeline.object_hash(moved_challenge_probe)
        self.assertTrue(
            any(
                "CLI selected" in error
                for error in pipeline.validate_self_review_probe_data(
                    moved_challenge_probe, manifest, profile, plan, repo_root=self.root
                )
            )
        )
        retargeted_probe = json.loads(json.dumps(falsification_probe))
        retargeted_probe["probes"][0]["claim_id"] = "layout:unrelated-gap"
        retargeted_probe.pop("probe_hash")
        retargeted_probe["probe_hash"] = pipeline.object_hash(retargeted_probe)
        self.assertTrue(
            any(
                "semantic target" in error
                for error in pipeline.validate_self_review_probe_data(
                    retargeted_probe, manifest, profile, plan, repo_root=self.root
                )
            )
        )
        missing_frame_probe = json.loads(json.dumps(falsification_probe))
        missing_frame_probe["probes"][0]["evidence"]["frame_path"] = "missing/probe.png"
        missing_frame_probe.pop("probe_hash")
        missing_frame_probe["probe_hash"] = pipeline.object_hash(missing_frame_probe)
        self.assertTrue(
            any(
                "does not exist" in error
                for error in pipeline.validate_self_review_probe_data(
                    missing_frame_probe, manifest, profile, plan, repo_root=self.root
                )
            )
        )
        false_numeric_probe = json.loads(json.dumps(falsification_probe))
        false_numeric_probe["probes"][0]["independent_check"]["actual_value"] = 0.0
        false_numeric_probe.pop("probe_hash")
        false_numeric_probe["probe_hash"] = pipeline.object_hash(false_numeric_probe)
        self.assertTrue(
            any(
                "exceeds tolerance" in error
                for error in pipeline.validate_self_review_probe_data(
                    false_numeric_probe, manifest, profile, plan, repo_root=self.root
                )
            )
        )
        circular_probe = json.loads(json.dumps(falsification_probe))
        circular_probe["probes"][0]["evidence"]["artifact_key"] = "telemetry"
        circular_probe.pop("probe_hash")
        circular_probe["probe_hash"] = pipeline.object_hash(circular_probe)
        self.assertTrue(
            any(
                "cannot prove its own" in error
                for error in pipeline.validate_self_review_probe_data(
                    circular_probe, manifest, profile, plan, repo_root=self.root
                )
            )
        )
        self_review = {
            "schema": "lecture-animation-author-self-review-v2",
            "manifest_hash": manifest["manifest_hash"],
            "scene_slug": "g002c_riemann_sum_limit",
            "owner": "animation-author",
            "author_agent_id": "agent-author-001",
            "author_model": "test-author-v1",
            "self_review_round": 1,
            "falsification_probe_hash": falsification_probe["probe_hash"],
            "falsification_probe": falsification_probe,
            "continuous_playback": {
                "performed": True,
                "audio_monitored": True,
                "observation": "The selected cell remains synchronized with the spoken refinement cause through the complete playback.",
            },
            "muted_playback": {
                "performed": True,
                "teach_back": "The finite frequency cells narrow while their accumulated area approaches one fixed density curve.",
                "prediction": "Increasing L should create more narrow cells without changing the underlying density envelope.",
            },
            "coverage_sweeps": [
                {
                    "layer": layer,
                    "result": "pass",
                    "timestamps": timestamps,
                    "object_ids": ["frequency_cells", "riemann_formula"],
                    "observation": f"The author inspected every {layer} anchor and verified the same cause-result chain across the scene.",
                }
                for layer, timestamps in pipeline.review_coverage_anchors(plan, 10.0).items()
            ],
            "artifact_checks": [
                {
                    "artifact_key": key,
                    "sha256": manifest["artifacts"][key]["sha256"],
                    "observation": f"The frozen {key} artifact matches the candidate inspected during author self-review.",
                }
                for key in ("source", "timeline", "audio", "srt", "review_mp4", "qc", "telemetry", "authoring_qc")
            ],
            "findings": [],
            "repair_context": {"previous_review_hash": None, "resolutions": []},
            "verdict": "ready_for_independent_review",
        }
        self_review["self_review_hash"] = pipeline.object_hash(self_review)
        self.assertEqual(
            pipeline.validate_author_self_review_data(
                self_review, manifest, profile, plan, repo_root=self.root
            ),
            [],
        )
        stale_self_review = json.loads(json.dumps(self_review))
        stale_self_review["artifact_checks"][0]["sha256"] = "0" * 64
        stale_self_review.pop("self_review_hash")
        stale_self_review["self_review_hash"] = pipeline.object_hash(stale_self_review)
        self.assertTrue(
            any(
                "artifact check" in error
                for error in pipeline.validate_author_self_review_data(
                    stale_self_review, manifest, profile, plan, repo_root=self.root
                )
            )
        )

        reviewer_rules = [rule for rule in profile["rules"] if "reviewer" in rule.get("owners", [])]
        checks = []
        for index, rule in enumerate(reviewer_rules):
            checks.append(
                {
                    "rule_id": rule["rule_id"],
                    "status": "passed",
                    "evidence": {
                        "timestamp_seconds": min(9.0, 0.4 + index * 0.55),
                        "artifact_key": "review_mp4",
                        "object_id": f"object_{index}",
                        "observation": f"At this beat object {index} changes from the declared driver and hands its result to the next visible object.",
                        "novice_impact": f"This evidence makes causal step {index} readable without assuming the conclusion.",
                    },
                }
            )
        review = {
            "schema": "lecture-animation-review-v2",
            "manifest_hash": manifest["manifest_hash"],
            "owner": "animation-author",
            "reviewer": "independent-reviewer",
            "reviewer_model": "test-reviewer-v1",
            "reviewer_agent_id": "agent-reviewer-001",
            "review_round": 1,
            "verdict": "pass_for_user_review_pending",
            "novice_pass": {
                "summary": "The frequency cells visibly narrow until their accumulated areas become a continuous integral.",
                "visible_cause": "Increasing L drives cell width, cell count, and the displayed partial sum together.",
                "confusion": "The phase factor remains beside every rectangle, so no unexplained factor disappears during the limit.",
                "eye_guidance": "The selected cell leads the eye first, then the growing rectangle family, and finally the integral line.",
                "teach_back": "Narrower frequency cells preserve the density envelope while their accumulated areas approach the continuous integral.",
                "prediction": "If L increases, Delta omega decreases, more cells appear, and the partial sum more closely follows the integral.",
                "silent_teach_back": "With audio muted, the selected interval becomes a rectangle and the full rectangle family visibly refines toward the fixed curve.",
                "silent_prediction": "With audio muted, another increase in L should produce narrower rectangles and a closer match to the unchanged density curve.",
                "confusion_probes": [
                    {"timestamp_seconds": 1.0, "candidate_confusion": "The selected point might still look like an isolated coordinate.", "visible_anchor": "Its width brace and rectangle body establish a finite interval contribution.", "resolution_test": "Point to the two cell edges without using narration."},
                    {"timestamp_seconds": 4.8, "candidate_confusion": "The promotion might be mistaken for a different graph.", "visible_anchor": "The selected cell color and density curve persist through the promotion.", "resolution_test": "Track the same selected cell across the transition."},
                    {"timestamp_seconds": 8.0, "candidate_confusion": "The integral might appear only by symbolic replacement.", "visible_anchor": "All narrowing rectangles remain under the unchanged density envelope.", "resolution_test": "Predict the next rectangle width before the formula changes."},
                ],
                "first_confusion_timestamp": None,
                "verdict": "clear",
            },
            "checks": checks,
            "findings": [],
        }
        errors, health = pipeline.verify_review_data(review, manifest, profile, self.root, None)
        self.assertEqual(errors, [])
        self.assertFalse(health["anomalous"])
        shallow_novice = json.loads(json.dumps(review))
        shallow_novice["novice_pass"].pop("silent_teach_back")
        errors, _ = pipeline.verify_review_data(shallow_novice, manifest, profile, self.root, None)
        self.assertTrue(any("silent_teach_back" in error for error in errors))
        preclosed_review = json.loads(json.dumps(review))
        preclosed_review["findings"] = [{"finding_id": "R-preclosed", "status": "closed"}]
        errors, _ = pipeline.verify_review_data(preclosed_review, manifest, profile, self.root, None)
        self.assertTrue(any("must remain open" in error for error in errors))

        event_log = self.episode / "review" / "evolution" / "events.jsonl"
        event_log.parent.mkdir(parents=True, exist_ok=True)
        anomaly_rows = [
            {
                "event_id": f"miss-{index}",
                "reviewer_model": "test-reviewer-v1",
                "automatic_verdict": "pass_for_user_review_pending",
                "human_verdict": "revise" if index < 2 else "pass",
                "reviewer_findings": 0,
            }
            for index in range(4)
        ]
        event_log.write_text(
            "".join(json.dumps(row) + "\n" for row in anomaly_rows),
            encoding="utf-8",
        )
        errors, health = pipeline.verify_review_data(review, manifest, profile, self.root, event_log)
        self.assertTrue(health["anomalous"])
        self.assertTrue(any("calibration_recheck" in error for error in errors))
        review["calibration_recheck"] = {
            "performed": True,
            "trigger_event_ids": health["trigger_event_ids"],
            "rules_rechecked": [rule["rule_id"] for rule in reviewer_rules[:3]],
            "fresh_timestamps": [1.0, 4.0, 8.0],
            "result": "pass",
        }
        errors, _ = pipeline.verify_review_data(review, manifest, profile, self.root, event_log)
        self.assertEqual(errors, [])

        manifest_path = self.episode / "review" / "v2" / "manifest.json"
        review_path = self.episode / "review" / "v2" / "review.json"
        audit_log = self.episode / "review" / "evolution" / "review_attempts.jsonl"
        state_path = self.episode / "review" / "v2" / "state.json"
        self_review_path = self.episode / "review" / "v2" / "author_self_review.json"
        self_review_probe_path = self.episode / "review" / "v2" / "self_review_probe.json"
        self_review_draft_path = self.episode / "review" / "v2" / "author_self_review_draft.json"
        session_path = self.episode / "review" / "v2" / "review_session.json"
        self.write_json(manifest_path, manifest)
        self.write_json(review_path, review)
        self.write_json(self_review_path, self_review)
        self.write_json(self_review_probe_path, falsification_probe)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_prepare_author_self_review(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        manifest=str(manifest_path),
                        owner="animation-author",
                        author_agent_id="agent-author-001",
                        author_model="test-author-v1",
                        self_review_round=1,
                        self_review_probe=str(self_review_probe_path),
                        previous_review=None,
                        output=str(self_review_draft_path),
                    )
                ),
                0,
            )
        prepared_self_review = pipeline.load_json(self_review_draft_path)
        self.assertEqual(prepared_self_review["manifest_hash"], manifest["manifest_hash"])
        self.assertEqual(
            len(prepared_self_review["coverage_sweeps"]),
            len(pipeline.HARD_GATE_LAYERS),
        )
        self.assertEqual(len(prepared_self_review["artifact_checks"]), 8)
        self_review_attempt_log = self.episode / "review" / "evolution" / "author_self_review_attempts.jsonl"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_seal_author_self_review(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        manifest=str(manifest_path),
                        input=str(self_review_draft_path),
                        previous_review=None,
                        output=str(self_review_path),
                        attempt_log=str(self_review_attempt_log),
                    )
                ),
                2,
            )
        rejected_self_reviews = pipeline.event_rows(self_review_attempt_log)
        self.assertEqual(len(rejected_self_reviews), 1)
        self.assertFalse(rejected_self_reviews[0]["gate_accepted"])
        self.assertGreater(rejected_self_reviews[0]["machine_gate_findings"], 0)
        session = {
            "schema": "lecture-animation-review-session-v2",
            "created_at": "2026-07-10T00:00:00+00:00",
            "batch_id": "batch-test",
            "session_id": "review-session:test",
            "reviewer": "independent-reviewer",
            "reviewer_model": "test-reviewer-v1",
            "reviewer_agent_id": "agent-reviewer-001",
            "owner": "animation-author",
            "author_agent_id": "agent-author-001",
            "contract_version": pipeline.REVIEW_SESSION_CONTRACT_VERSION,
            "production_mode": "main_producer",
            "main_agent_id": "",
            "review_role": "acceptance",
            "episode_spine_hash": episode_spine["spine_hash"],
            "episode_spine_path": pipeline.relative_or_absolute(episode_spine_path, self.root),
            "rules_registry_hash": pipeline.object_hash(pipeline.load_rules()),
            "status": "active",
            "scenes": [],
            "full_reviews": 0,
            "diagnostic_reviews": 0,
            "reviewer_switches": 0,
            "calibration_scene_interval": 5,
            "calibration_due": False,
            "pending_repairs": {},
        }
        pipeline.save_review_session(session_path, session)
        with contextlib.redirect_stdout(io.StringIO()):
            result = pipeline.command_verify_review(
                SimpleNamespace(
                    repo_root=str(self.root),
                    manifest=str(manifest_path),
                    review=str(review_path),
                    author_self_review=str(self_review_path),
                    review_session=str(session_path),
                    event_log=str(event_log),
                    audit_log=str(audit_log),
                )
            )
        self.assertEqual(result, 0)
        attempts = pipeline.event_rows(audit_log)
        self.assertEqual(len(attempts), 1)
        self.assertTrue(attempts[0]["gate_accepted"])
        with contextlib.redirect_stdout(io.StringIO()):
            result = pipeline.command_verify_review(
                SimpleNamespace(
                    repo_root=str(self.root),
                    manifest=str(manifest_path),
                    review=str(review_path),
                    author_self_review=str(self_review_path),
                    review_session=str(session_path),
                    event_log=str(event_log),
                    audit_log=str(audit_log),
                )
            )
        self.assertEqual(result, 0)
        self.assertEqual(len(pipeline.event_rows(audit_log)), 1)

        capsule = pipeline.review_capsule_data(
            manifest,
            profile,
            plan,
            pipeline.load_review_session(session_path),
            self_review,
        )
        blind = {
            "schema": "lecture-animation-blind-review-v2",
            "capsule_hash": capsule["capsule_hash"],
            "reviewer": "independent-reviewer",
            "reviewer_model": "test-reviewer-v1",
            "reviewer_agent_id": "agent-reviewer-001",
            "novice_pass": review["novice_pass"],
            "challenge_responses": [
                {
                    "challenge_id": item["challenge_id"],
                    "observation": "The visible driver changes the named object, and the next state can be predicted without narration.",
                }
                for item in capsule["blind_challenges"]
            ],
        }
        receipt = pipeline.blind_review_receipt_data(capsule, blind, pipeline.load_review_session(session_path))
        bound_review = json.loads(json.dumps(review))
        bound_review["capsule_hash"] = capsule["capsule_hash"]
        bound_review["blind_receipt_hash"] = receipt["receipt_hash"]
        bound_review["worst_frame_candidates"] = [
            {
                "timestamp_seconds": value,
                "observation": "This candidate was inspected for composition, object ownership, and causal legibility.",
            }
            for value in (1.0, 4.0, 8.0)
        ]
        self.assertEqual(
            pipeline.validate_review_capsule_chain(
                bound_review,
                capsule,
                receipt,
                manifest,
                pipeline.load_review_session(session_path),
                self_review,
            ),
            [],
        )
        with contextlib.redirect_stdout(io.StringIO()):
            result = pipeline.command_gate_status(
                SimpleNamespace(
                    repo_root=str(self.root),
                    profile=str(profile_path),
                    plan=str(plan_path),
                    challenge=str(challenge_path),
                    deliberation=str(deliberation_path),
                    design_gate=str(design_gate_path),
                    precedent_packet=str(precedent_path),
                    manifest=str(manifest_path),
                    author_self_review=str(self_review_path),
                    previous_review=None,
                    review=str(review_path),
                    review_session=str(session_path),
                    event_log=str(event_log),
                    output=str(state_path),
                )
            )
        self.assertEqual(result, 0)
        state = pipeline.load_json(state_path)
        self.assertEqual(state["state"], "user_review_pending")
        self.assertTrue(state["permissions"]["may_show_user"])
        self.assertFalse(state["permissions"]["may_stage_or_commit"])

        review["checks"][0]["evidence"]["observation"] = "Checked MP4 and no issue"
        errors, _ = pipeline.verify_review_data(review, manifest, profile, self.root, None)
        self.assertTrue(any("generic" in error for error in errors))

        (source / "composer.py").write_text("DRIVER = 'changed'\n", encoding="utf-8")
        stale_errors = pipeline.verify_manifest_data(manifest, self.root)
        self.assertTrue(any("stale artifact" in error for error in stale_errors))

    def test_reviewer_anomaly_requires_calibration(self) -> None:
        rows = []
        for index in range(4):
            rows.append(
                {
                    "event_id": f"event-{index}",
                    "reviewer_model": "overpermissive-reviewer",
                    "automatic_verdict": "pass_for_user_review_pending",
                    "human_verdict": "revise" if index < 2 else "pass",
                    "reviewer_findings": 0,
                }
            )
        health = pipeline.reviewer_health(rows, "overpermissive-reviewer")
        self.assertTrue(health["anomalous"])
        self.assertGreater(health["false_pass_rate"], 0.20)
        self.assertEqual(health["zero_finding_pass_rate"], 1.0)

    def test_light_reviewer_requires_hash_bound_certification(self) -> None:
        episode_spine_path = self.episode / "review" / "v2" / "review_episode_spine.json"
        episode_spine = {
            "schema": "lecture-animation-episode-visual-spine-v2",
            "episode": pipeline.relative_or_absolute(self.episode, self.root),
            "production_mode": "parallel_batches",
            "main_agent_governance": {"owner": "review-agent-light-1"},
        }
        episode_spine["spine_hash"] = pipeline.object_hash(episode_spine)
        self.write_json(episode_spine_path, episode_spine)
        benchmark = {
            "schema": "lecture-animation-reviewer-benchmark-v2",
            "benchmark_id": "review-admission-v1",
            "rules_registry_hash": pipeline.object_hash(pipeline.load_rules()),
            "thresholds": {
                "critical_pattern_recall": 0.9,
                "repeat_failure_recall": 1.0,
                "false_pass_rate": 0.1,
                "false_positive_rate": 0.35,
            },
            "cases": [
                {
                    "case_id": "overlap",
                    "expected_verdict": "revise",
                    "required_pattern_keys": ["formula_overlap"],
                    "repeat_failure": True,
                },
                {
                    "case_id": "orphan",
                    "expected_verdict": "revise",
                    "required_pattern_keys": ["orphan_math_object"],
                    "repeat_failure": True,
                },
                {
                    "case_id": "timing",
                    "expected_verdict": "revise",
                    "required_pattern_keys": ["visual_audio_desync"],
                },
                {
                    "case_id": "clean",
                    "expected_verdict": "pass_for_user_review_pending",
                    "required_pattern_keys": [],
                },
            ],
        }
        benchmark["benchmark_hash"] = pipeline.object_hash(benchmark)
        submission = {
            "schema": "lecture-animation-reviewer-benchmark-submission-v2",
            "benchmark_hash": benchmark["benchmark_hash"],
            "reviewer_model": "gpt-5.6-terra",
            "reasoning_effort": "medium",
            "case_results": [
                {
                    "case_id": item["case_id"],
                    "verdict": item["expected_verdict"],
                    "found_pattern_keys": item["required_pattern_keys"],
                }
                for item in benchmark["cases"]
            ],
        }
        certification = pipeline.reviewer_certification_data(benchmark, submission)
        self.assertTrue(certification["eligible"])
        certification_path = self.episode / "review" / "v2" / "terra_certification.json"
        session_path = self.episode / "review" / "v2" / "light_review_session.json"
        self.write_json(certification_path, certification)
        with contextlib.redirect_stdout(io.StringIO()):
            result = pipeline.command_begin_review_batch(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode_spine=str(episode_spine_path),
                    review_role="acceptance",
                    batch_id="light-review-batch",
                    owner="animation-author",
                    author_agent_id="agent-author-001",
                    reviewer="independent-reviewer",
                    reviewer_model="gpt-5.6-terra",
                    reviewer_tier="light",
                    reasoning_effort="medium",
                    certification=str(certification_path),
                    escalation_model="gpt-5.6-sol",
                    reviewer_agent_id="review-agent-light-1",
                    calibration_scene_interval=5,
                    replace=False,
                    replace_reason=None,
                    output=str(session_path),
                )
            )
        self.assertEqual(result, 0)
        session = pipeline.load_review_session(session_path)
        self.assertEqual(session["certification_hash"], certification["certification_hash"])
        self.assertTrue(session["capsule_required"])
        session["applied_review_attempt_ids"] = ["review:preserve-me"]
        session["pending_repairs"] = {
            "g002_test": {
                "review_hash": "review-hash",
                "review_attempt_id": "review:preserve-me",
                "findings_count": 1,
                "manifest_hash": "rejected-manifest",
            }
        }
        pipeline.save_review_session(session_path, session)
        stale_session = pipeline.load_json(session_path)
        stale_session["rules_registry_hash"] = "stale-rules-registry"
        pipeline.save_review_session(session_path, stale_session)
        with self.assertRaisesRegex(pipeline.PipelineError, "stale for the current rules registry"):
            pipeline.load_review_session(session_path)
        migrated_path = self.episode / "review" / "v2" / "migrated_review_session.json"
        with contextlib.redirect_stdout(io.StringIO()):
            result = pipeline.command_migrate_review_session(
                SimpleNamespace(
                    repo_root=str(self.root),
                    input=str(session_path),
                    episode_spine=str(episode_spine_path),
                    reviewer="main-acceptance-reviewer",
                    owner=None,
                    author_agent_id=None,
                    reviewer_model="gpt-5.6-sol",
                    reviewer_tier="frontier",
                    reasoning_effort="xhigh",
                    reviewer_agent_id="review-agent-light-1",
                    reason="Move the active ledger to the frontier reviewer without losing verified repair history.",
                    output=str(migrated_path),
                )
            )
        self.assertEqual(result, 0)
        migrated = pipeline.load_review_session(migrated_path)
        self.assertEqual(migrated["applied_review_attempt_ids"], ["review:preserve-me"])
        self.assertIn("g002_test", migrated["pending_repairs"])
        self.assertEqual(migrated["reviewer_model"], "gpt-5.6-sol")
        self.assertEqual(len(migrated["migration_history"]), 1)
        reassigned_path = self.episode / "review" / "v2" / "reassigned_review_session.json"
        with contextlib.redirect_stdout(io.StringIO()):
            result = pipeline.command_migrate_review_session(
                SimpleNamespace(
                    repo_root=str(self.root),
                    input=str(migrated_path),
                    episode_spine=str(episode_spine_path),
                    reviewer="main-acceptance-reviewer",
                    owner="replacement-animation-author",
                    author_agent_id="agent-author-002",
                    reviewer_model="gpt-5.6-sol",
                    reviewer_tier="frontier",
                    reasoning_effort="xhigh",
                    reviewer_agent_id="review-agent-light-1",
                    reason="Reassign the unfinished scene group to a replacement author while preserving its repair ledger.",
                    output=str(reassigned_path),
                )
            )
        self.assertEqual(result, 0)
        reassigned = pipeline.load_review_session(reassigned_path)
        self.assertEqual(reassigned["owner"], "replacement-animation-author")
        self.assertEqual(reassigned["author_agent_id"], "agent-author-002")
        self.assertEqual(reassigned["applied_review_attempt_ids"], ["review:preserve-me"])
        self.assertIn("g002_test", reassigned["pending_repairs"])
        self.assertTrue(reassigned["migration_history"][-1]["author_reassigned"])
        with self.assertRaises(pipeline.PipelineError):
            pipeline.command_begin_review_batch(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode_spine=str(episode_spine_path),
                    review_role="acceptance",
                    batch_id="invalid-same-agent",
                    owner="animation-author",
                    author_agent_id="shared-agent-001",
                    reviewer="independent-reviewer",
                    reviewer_model="gpt-5.6-sol",
                    reviewer_tier="frontier",
                    reasoning_effort="high",
                    certification=None,
                    escalation_model="gpt-5.6-sol",
                    reviewer_agent_id="shared-agent-001",
                    calibration_scene_interval=5,
                    replace=False,
                    replace_reason=None,
                    output=str(self.episode / "review" / "v2" / "invalid_same_agent.json"),
                )
            )

    def test_phase_metrics_separate_critical_path_from_agent_seconds(self) -> None:
        rows = [
            {
                "event_id": "review-a",
                "phase_instance_id": "shared-review",
                "phase": "review",
                "started_at": "2026-07-10T00:00:00+00:00",
                "ended_at": "2026-07-10T00:00:10+00:00",
                "duration_seconds": 10.0,
                "input_tokens": 100,
            },
            {
                "event_id": "review-b",
                "phase_instance_id": "shared-review",
                "phase": "review",
                "started_at": "2026-07-10T00:00:00+00:00",
                "ended_at": "2026-07-10T00:00:10+00:00",
                "duration_seconds": 10.0,
                "input_tokens": 100,
            },
            {
                "event_id": "authoring",
                "phase_instance_id": "authoring-1",
                "phase": "authoring",
                "started_at": "2026-07-10T00:00:00+00:00",
                "ended_at": "2026-07-10T00:00:20+00:00",
                "duration_seconds": 20.0,
                "input_tokens": 200,
            },
            {
                "event_id": "authoring-shared-copy",
                "phase_instance_id": "authoring-copy",
                "run_id": "run-shared",
                "scene_slug": "g003",
                "phase": "authoring",
                "phase_purpose": "shared_design",
                "actor_model": "model",
                "actor_role": "author",
                "reasoning_effort": "high",
                "started_at": "2026-07-10T00:00:30+00:00",
                "ended_at": "2026-07-10T00:00:40+00:00",
                "duration_seconds": 10.0,
                "input_tokens": 50,
            },
            {
                "event_id": "authoring-shared-copy-2",
                "phase_instance_id": "authoring-copy-2",
                "run_id": "run-shared",
                "scene_slug": "g004",
                "phase": "authoring",
                "phase_purpose": "shared_design",
                "actor_model": "model",
                "actor_role": "author",
                "reasoning_effort": "high",
                "started_at": "2026-07-10T00:00:30+00:00",
                "ended_at": "2026-07-10T00:00:40+00:00",
                "duration_seconds": 10.0,
                "input_tokens": 50,
            },
        ]
        metrics = pipeline.phase_metrics(rows)
        self.assertEqual(len(metrics["unique_events"]), 4)
        self.assertEqual(metrics["aggregate_agent_seconds"], 50.0)
        self.assertEqual(metrics["critical_path_seconds"], 30.0)
        self.assertEqual(metrics["concurrency_overlap_seconds"], 20.0)
        self.assertEqual(metrics["token_usage"]["input_tokens"], 400)
        self.assertEqual(len(metrics["probable_shared_duplicates"]), 1)
        self.assertFalse(
            metrics["probable_shared_duplicates"][0]["deduplicated"]
        )

    def test_probable_shared_signature_without_state_is_diagnostic_only(
        self,
    ) -> None:
        rows = [
            {
                "event_id": f"legacy-{scene}",
                "phase_instance_id": f"legacy-instance-{scene}",
                "run_id": "same-run",
                "scene_slug": scene,
                "phase": "repair",
                "phase_purpose": "legacy-repair",
                "actor_model": "model",
                "actor_role": "author",
                "reasoning_effort": "high",
                "started_at": "2026-07-30T00:00:00+00:00",
                "ended_at": "2026-07-30T00:00:10+00:00",
                "duration_seconds": 10.0,
                "input_tokens": 100,
                "token_observed": True,
            }
            for scene in ("g001", "g002")
        ]
        metrics = pipeline.phase_metrics(rows)
        self.assertEqual(len(metrics["unique_events"]), 2)
        self.assertEqual(metrics["token_usage"]["input_tokens"], 200)
        self.assertEqual(
            len(metrics["probable_shared_duplicates"]),
            1,
        )

    def test_shared_accounting_observability_merge_is_order_independent(
        self,
    ) -> None:
        base = {
            "accounting_identity": "phase-accounting:shared:test",
            "phase": "review",
            "started_at": "2026-07-30T00:00:00+00:00",
            "ended_at": "2026-07-30T00:00:10+00:00",
            "duration_seconds": 10.0,
            "input_tokens": 100,
        }
        missing = {
            **base,
            "event_id": "event-b",
            "phase_instance_id": "legacy-b",
            "token_observed": False,
            "token_source_kind": "unavailable",
        }
        observed = {
            **base,
            "event_id": "event-a",
            "phase_instance_id": "legacy-a",
            "token_observed": True,
            "token_source_kind": "manual",
        }
        forward = pipeline.phase_metrics([missing, observed])
        reverse = pipeline.phase_metrics([observed, missing])
        self.assertEqual(
            forward["token_observability"],
            reverse["token_observability"],
        )
        self.assertEqual(
            forward["token_observability"],
            {
                "applicable": True,
                "expected_events": 1,
                "observed_events": 1,
                "coverage": 1.0,
                "missing_event_ids": [],
            },
        )
        self.assertEqual(
            forward["unique_events"][0]["token_source_kind"],
            "manual",
        )
        self.assertEqual(
            forward["unique_events"],
            reverse["unique_events"],
        )

    def test_shared_accounting_active_intervals_union_without_spanning_gaps(
        self,
    ) -> None:
        identity = "phase-accounting:shared:interval-test"
        rows = [
            {
                "event_id": "event-a",
                "accounting_identity": identity,
                "phase": "repair",
                "started_at": "2026-07-30T00:00:00+00:00",
                "ended_at": "2026-07-30T00:00:10+00:00",
                "duration_seconds": 10.0,
                "input_tokens": 100,
                "token_observed": True,
            },
            {
                "event_id": "event-b",
                "accounting_identity": identity,
                "phase": "repair",
                "started_at": "2026-07-30T00:00:05+00:00",
                "ended_at": "2026-07-30T00:00:15+00:00",
                "duration_seconds": 10.0,
                "input_tokens": 100,
                "token_observed": True,
            },
            {
                "event_id": "event-c",
                "accounting_identity": identity,
                "phase": "repair",
                "started_at": "2026-07-31T00:00:00+00:00",
                "ended_at": "2026-07-31T00:00:05+00:00",
                "duration_seconds": 5.0,
                "input_tokens": 100,
                "token_observed": True,
            },
            {
                "event_id": "event-d",
                "accounting_identity": identity,
                "phase": "repair",
                "started_at": "2026-07-31T00:01:00+00:00",
                "ended_at": None,
                "duration_seconds": 7.0,
                "input_tokens": 100,
                "token_observed": True,
            },
        ]
        metrics = pipeline.phase_metrics(rows)
        self.assertEqual(len(metrics["unique_events"]), 1)
        # 15 seconds for the overlapping pair, 5 for the next-day task,
        # and 7 conservatively unplaced seconds for the missing endpoint.
        self.assertEqual(metrics["aggregate_agent_seconds"], 27.0)
        self.assertEqual(metrics["critical_path_seconds"], 27.0)
        self.assertEqual(
            metrics["phase_wall_seconds"]["repair"],
            27.0,
        )
        self.assertEqual(metrics["token_usage"]["input_tokens"], 100)

    def test_single_shared_event_missing_endpoint_counts_unplaced_time(
        self,
    ) -> None:
        metrics = pipeline.phase_metrics(
            [
                {
                    "event_id": "missing-endpoint",
                    "accounting_identity": (
                        "phase-accounting:shared:missing-endpoint"
                    ),
                    "phase": "repair",
                    "started_at": "2026-07-31T00:01:00+00:00",
                    "ended_at": None,
                    "duration_seconds": 7.0,
                    "input_tokens": 10,
                    "token_observed": True,
                }
            ]
        )
        self.assertEqual(metrics["aggregate_agent_seconds"], 7.0)
        self.assertEqual(metrics["critical_path_seconds"], 7.0)
        self.assertEqual(metrics["phase_wall_seconds"]["repair"], 7.0)
        event = metrics["unique_events"][0]
        self.assertEqual(event["accounting_intervals"], [])
        self.assertEqual(
            event["accounting_unplaced_duration_seconds"],
            7.0,
        )

    def test_projected_active_seconds_uses_completed_accounting_intervals(
        self,
    ) -> None:
        identity = "phase-accounting:shared:projection-test"
        completed = [
            {
                "event_id": "completed-a",
                "accounting_identity": identity,
                "phase": "repair",
                "started_at": "2026-07-30T00:00:00+00:00",
                "ended_at": "2026-07-30T00:00:10+00:00",
                "duration_seconds": 10.0,
            },
            {
                "event_id": "completed-b",
                "accounting_identity": identity,
                "phase": "repair",
                "started_at": "2026-07-31T00:00:00+00:00",
                "ended_at": "2026-07-31T00:00:05+00:00",
                "duration_seconds": 5.0,
            },
            {
                "event_id": "completed-c",
                "accounting_identity": identity,
                "phase": "repair",
                "started_at": "2026-07-31T00:01:00+00:00",
                "ended_at": None,
                "duration_seconds": 7.0,
            },
        ]
        self.assertEqual(
            pipeline.projected_active_seconds(
                completed,
                {"reservations": {}},
                new_phase="human_wait",
                new_phase_purpose="",
                new_started_at="2026-07-31T00:02:00+00:00",
                new_active_seconds=0.0,
            ),
            22.0,
        )

    def test_shared_accounting_identity_separates_required_dimensions(
        self,
    ) -> None:
        base = {
            "episode": "videos/0008-mpm-8-cauchy_integral",
            "phase": "repair",
            "phase_purpose": "animatic_repair",
            "actor_model": "gpt-5.6-sol",
            "actor_role": "animation_author",
            "shared_work_key": "batch-a-animatic-repair",
        }
        expected = pipeline.shared_phase_accounting_identity(**base)
        variants = []
        for field, value in (
            ("episode", "videos/0009-other"),
            ("phase", "review"),
            ("phase_purpose", "repair_rerender"),
            ("actor_model", "gpt-5.6"),
            ("actor_role", "independent_reviewer"),
            ("shared_work_key", "batch-b-animatic-repair"),
        ):
            changed = dict(base)
            changed[field] = value
            variants.append(
                pipeline.shared_phase_accounting_identity(**changed)
            )
        self.assertEqual(len(set(variants)), len(variants))
        self.assertNotIn(expected, variants)

    def test_episode8_legacy_shared_repair_accounting_uses_state_paths(
        self,
    ) -> None:
        contract = pipeline.load_json(self.efficiency_contract)
        ledger = pipeline.empty_efficiency_reservation_ledger(contract)
        reservations = {}
        events = []
        batches = (
            ("ep8-batch-a-animatic-v02-repair", 4, 111),
            ("ep8-batch-b-animatic-v02-repair", 4, 222),
            ("ep8-batch-c-animatic-v02-repair", 4, 333),
        )
        for batch_index, (
            shared_key,
            scene_count,
            input_tokens,
        ) in enumerate(batches):
            for scene_index in range(scene_count):
                scene_slug = (
                    f"g{batch_index * 4 + scene_index + 1:03d}_ep8"
                )
                phase_instance_id = (
                    "phase-instance:shared:legacy-"
                    f"{batch_index}-{scene_index}"
                )
                state_path = (
                    self.episode
                    / "review"
                    / "v2"
                    / scene_slug
                    / "repair_phase_active.json"
                )
                self.write_json(
                    state_path,
                    {
                        "schema": "lecture-animation-phase-timer-v2",
                        "run_id": f"{scene_slug}-repair-run",
                        "scene_slug": scene_slug,
                        "phase": "repair",
                        "phase_purpose": "animatic_repair",
                        "actor_model": f"producer-{batch_index}",
                        "actor_role": "animation_author",
                        "shared_work_key": shared_key,
                        "phase_instance_id": phase_instance_id,
                    },
                )
                reservation_id = (
                    f"reservation:legacy-{batch_index}-{scene_index}"
                )
                reservations[reservation_id] = {
                    "reservation_id": reservation_id,
                    "status": "released",
                    "state_path": str(state_path),
                    "run_id": f"{scene_slug}-repair-run",
                    "scene_slug": scene_slug,
                    "phase": "repair",
                    "phase_instance_id": phase_instance_id,
                    "allocation": {
                        "raw_input_plus_output_tokens": input_tokens,
                        "uncached_input_tokens": input_tokens,
                        "output_tokens": 0,
                        "reasoning_tokens": 0,
                    },
                }
                second = batch_index * 20
                events.append(
                    {
                        "schema": "lecture-animation-phase-event-v2",
                        "event_id": (
                            f"phase:legacy-{batch_index}-{scene_index}"
                        ),
                        "run_id": f"{scene_slug}-repair-run",
                        "scene_slug": scene_slug,
                        "phase": "repair",
                        "phase_purpose": "animatic_repair",
                        "actor_model": f"producer-{batch_index}",
                        "actor_role": "animation_author",
                        "phase_instance_id": phase_instance_id,
                        "started_at": (
                            "2026-07-30T00:00:"
                            f"{second:02d}+00:00"
                        ),
                        "ended_at": (
                            "2026-07-30T00:00:"
                            f"{second + 10:02d}+00:00"
                        ),
                        "duration_seconds": 10.0,
                        "input_tokens": input_tokens,
                        "cached_input_tokens": 0,
                        "output_tokens": 0,
                        "reasoning_tokens": 0,
                        "token_observed": True,
                        "result": "completed",
                    }
                )
        ledger["reservations"] = reservations
        ledger["revision"] = len(reservations)
        ledger.pop("ledger_hash")
        ledger["ledger_hash"] = pipeline.object_hash(ledger)
        self.write_json(
            pipeline.episode_efficiency_reservation_ledger(contract),
            ledger,
        )

        original_phase_ids = [
            event["phase_instance_id"] for event in events
        ]
        status = pipeline.efficiency_status_from_rows(
            contract,
            events,
        )
        unique_repairs = [
            event
            for event in status["measured"]["unique_events"]
            if event["phase"] == "repair"
        ]
        self.assertEqual(len(unique_repairs), 3)
        self.assertEqual(
            status["measured"]["token_usage"]["input_tokens"],
            111 + 222 + 333,
        )
        enriched = pipeline.phase_rows_with_accounting(
            events,
            contract=contract,
            reservation_ledger=ledger,
        )
        self.assertEqual(
            len(
                {
                    event["accounting_identity"]
                    for event in enriched
                }
            ),
            3,
        )
        self.assertEqual(
            [event["phase_instance_id"] for event in enriched],
            original_phase_ids,
        )
        self.assertTrue(
            all("shared_work_key" not in event for event in events)
        )
        central_log = pipeline.episode_efficiency_central_log(
            contract
        )
        for event in events:
            pipeline.append_jsonl(central_log, event)
        production = pipeline.production_metrics(self.episode)
        self.assertEqual(production["phase_events"], 3)
        self.assertEqual(
            production["phase_agent_seconds"]["repair"],
            30.0,
        )
        self.assertEqual(
            production["token_usage"]["input_tokens"],
            111 + 222 + 333,
        )
        retrospective = pipeline.retrospective_evidence_data(
            self.root,
            self.episode,
        )
        self.assertEqual(
            retrospective["metrics"]["phase_agent_seconds"][
                "repair"
            ],
            30.0,
        )

    def test_token_observability_includes_render_tts_and_asr(self) -> None:
        rows = [
            {
                "event_id": f"phase-{phase}",
                "phase_instance_id": f"instance-{phase}",
                "phase": phase,
                "started_at": f"2026-07-10T00:00:0{index}+00:00",
                "ended_at": f"2026-07-10T00:00:0{index + 1}+00:00",
                "duration_seconds": 1.0,
                "token_observed": phase != "render",
            }
            for index, phase in enumerate(
                ("authoring", "render", "tts", "asr")
            )
        ]
        metrics = pipeline.phase_metrics(rows)
        self.assertEqual(
            metrics["token_observability"]["expected_events"],
            4,
        )
        self.assertEqual(
            metrics["token_observability"]["coverage"],
            0.75,
        )
        self.assertEqual(
            metrics["token_observability"]["missing_event_ids"],
            ["phase-render"],
        )

    def test_episode_token_budget_caps_total_volume_not_concurrency_rate(
        self,
    ) -> None:
        budget = pipeline.default_efficiency_budget()
        episode_seven = pipeline.token_budget_observation(
            {
                "input_tokens": 259_830_476,
                "cached_input_tokens": 253_572_864,
                "output_tokens": 746_168,
                "reasoning_tokens": 150_525,
            },
            budget,
        )
        self.assertFalse(episode_seven["within_budget"])
        self.assertEqual(
            episode_seven["exceeded"],
            [
                "output_tokens",
                "raw_input_plus_output_tokens",
                "reasoning_tokens",
                "uncached_input_tokens",
            ],
        )

        short_parallel_burst = pipeline.token_budget_observation(
            {
                "input_tokens": 39_000_000,
                "cached_input_tokens": 38_000_000,
                "output_tokens": 200_000,
                "reasoning_tokens": 60_000,
            },
            budget,
        )
        self.assertTrue(short_parallel_burst["within_budget"])
        self.assertEqual(short_parallel_burst["exceeded"], [])

        one_token_over = pipeline.token_budget_observation(
            {
                "input_tokens": 50_000_001,
                "cached_input_tokens": 50_000_001,
                "output_tokens": 0,
                "reasoning_tokens": 0,
            },
            budget,
        )
        self.assertIn(
            "raw_input_plus_output_tokens",
            one_token_over["exceeded"],
        )

    def test_known_human_regression_recurrence_is_detected(self) -> None:
        prior_issue = {
            "source": "human_review",
            "pattern_key": "matrix_columns_visually_collide",
            "must_check_in_future": True,
            "status": "fixed",
        }
        current_issue = {
            "source": "human_review",
            "pattern_key": "matrix_columns_visually_collide",
            "must_check_in_future": True,
            "status": "open",
        }
        self.write_json(
            self.old_episode
            / "review"
            / "issues"
            / "matrix-columns-collide.json",
            prior_issue,
        )
        self.write_json(
            self.episode
            / "review"
            / "issues"
            / "matrix-columns-collide-again.json",
            current_issue,
        )
        future_episode = self.root / "videos" / "0003-future"
        self.write_json(
            future_episode
            / "review"
            / "issues"
            / "matrix-columns-collide-later.json",
            prior_issue,
        )

        recurrences = pipeline.known_human_regression_recurrences(
            self.root,
            self.episode,
        )
        self.assertEqual(len(recurrences), 1)
        self.assertEqual(
            recurrences[0]["pattern_key"],
            "matrix_columns_visually_collide",
        )
        self.assertEqual(len(recurrences[0]["prior_issues"]), 1)

    def test_default_episode_efficiency_contract_is_eight_hours(self) -> None:
        parser = pipeline.build_parser()
        parsed = parser.parse_args(
            [
                "begin-episode-efficiency",
                "--episode",
                str(self.episode),
                "--delivery-clock",
                "delivery-clock.json",
                "--output",
                "efficiency.json",
            ]
        )
        self.assertIsNone(parsed.episode_target_hours)
        self.assertIsNone(parsed.delivery_target_hours)
        self.assertEqual(parsed.retrospective_reserve_minutes, 45.0)
        self.assertIsNone(parsed.closure_reserve_minutes)
        self.assertEqual(
            parsed.closure_token_reserve_fraction,
            0.32,
        )
        self.assertEqual(
            parsed.retrospective_token_reserve_fraction,
            0.07,
        )
        self.assertEqual(
            sum(pipeline.DEFAULT_PHASE_ACTIVE_SECONDS.values()),
            8.75 * 3600,
        )
        self.assertAlmostEqual(
            sum(
                pipeline.DEFAULT_PHASE_TOKEN_FRACTIONS_BY_FIELD[
                    "reasoning_tokens"
                ].values()
            ),
            1.0,
        )

    def test_delivery_target_keeps_retrospective_outside_eight_hours(self) -> None:
        parsed = pipeline.build_parser().parse_args(
            [
                "begin-episode-efficiency",
                "--episode",
                str(self.episode),
                "--delivery-clock",
                "delivery-clock.json",
                "--delivery-target-hours",
                "8",
                "--retrospective-reserve-minutes",
                "45",
                "--output",
                "efficiency.json",
            ]
        )
        budget = pipeline.efficiency_budget_data(parsed)
        self.assertEqual(budget["delivery_active_seconds"], 8 * 3600)
        self.assertEqual(budget["episode_active_seconds"], 8.75 * 3600)
        self.assertEqual(
            pipeline.validate_efficiency_budget_data(budget),
            [],
        )
        contract = {"budget": budget}
        self.assertEqual(
            pipeline.effective_efficiency_limits(
                contract, "finalization", "episode_assembly"
            )["active_seconds"],
            8 * 3600,
        )
        self.assertEqual(
            pipeline.effective_efficiency_limits(
                contract, "retrospective", "episode_postmortem"
            )["active_seconds"],
            8.75 * 3600,
        )
        self.assertEqual(
            pipeline.DEFAULT_PHASE_TOKEN_FRACTIONS_BY_FIELD[
                "reasoning_tokens"
            ]["planning"],
            0.05,
        )
        self.assertEqual(
            pipeline.DEFAULT_PHASE_TOKEN_FRACTIONS_BY_FIELD[
                "reasoning_tokens"
            ][pipeline.PLANNING_QUALITY_REPAIR_BUCKET],
            0.08,
        )
        self.assertEqual(
            pipeline.DEFAULT_PHASE_TOKEN_FRACTIONS_BY_FIELD[
                "reasoning_tokens"
            ]["render"],
            0.12,
        )
        self.assertEqual(parsed.raw_token_budget, 50_000_000)
        self.assertEqual(parsed.uncached_input_token_budget, 2_000_000)
        self.assertEqual(parsed.output_token_budget, 300_000)
        self.assertEqual(parsed.reasoning_token_budget, 100_000)

    def test_planning_quality_repair_contract_is_sealed_and_fresh(
        self,
    ) -> None:
        baseline = self.episode / "lecture.md"
        quality_gate = self.episode / "quality-gate.json"
        defect_manifest = self.episode / "planning-defects.json"
        baseline.write_text("first pass", encoding="utf-8")
        self.write_json(quality_gate, {"verdict": "revise"})
        self.write_json(
            defect_manifest,
            {
                "defects": [
                    {
                        "id": "scope-001",
                        "category": "scope",
                        "evidence": "the draft crosses the approved boundary",
                        "acceptance_checks": [
                            "forbidden next-episode topics are absent"
                        ],
                    }
                ]
            },
        )
        contract = pipeline.planning_quality_repair_contract_data(
            self.root,
            self.episode,
            baseline_path=baseline,
            quality_gate_path=quality_gate,
            defect_manifest_path=defect_manifest,
            allowed_paths=[
                pipeline.relative_or_absolute(baseline, self.root)
            ],
        )
        self.assertEqual(
            pipeline.validate_planning_quality_repair_contract(
                contract,
                self.root,
                self.episode,
            ),
            [],
        )
        baseline.write_text("mutated after sealing", encoding="utf-8")
        self.assertIn(
            "planning quality repair baseline_artifact hash is stale",
            pipeline.validate_planning_quality_repair_contract(
                contract,
                self.root,
                self.episode,
            ),
        )

    def test_planning_quality_repair_has_13k_completion_envelope(
        self,
    ) -> None:
        budget = pipeline.default_efficiency_budget()
        first_pass = pipeline.phase_token_limits(
            budget,
            "planning",
        )
        protected_repair = pipeline.phase_token_limits(
            budget,
            pipeline.PLANNING_QUALITY_REPAIR_BUCKET,
        )
        completion = pipeline.planning_completion_token_limits(
            budget,
        )
        self.assertEqual(first_pass["reasoning_tokens"], 5_000)
        self.assertEqual(
            protected_repair["reasoning_tokens"],
            8_000,
        )
        self.assertEqual(completion["reasoning_tokens"], 13_000)

    def test_discretionary_planning_cannot_spend_quality_repair_reserve(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "planning token envelope",
        ):
            pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(self.episode),
                    efficiency_contract=str(self.efficiency_contract),
                    run_id="planning-over-first-pass",
                    scene_slug="episode",
                    phase="planning",
                    phase_purpose=None,
                    actor_model="test-planner",
                    active_seconds_allocation=60,
                    raw_token_allocation=1,
                    uncached_input_token_allocation=0,
                    output_token_allocation=0,
                    reasoning_token_allocation=5_001,
                    state=str(
                        self.episode
                        / "planning-over-first-pass.json"
                    ),
                )
            )

    def test_episode_nine_design_continuation_preserves_failure_and_admits_exact_scope(
        self,
    ) -> None:
        episode = (
            self.root
            / "videos"
            / "0009-mpm-9-singularities_residues"
        )
        episode.mkdir(parents=True)
        efficiency_path = (
            episode
            / "review"
            / "evolution"
            / "episode_efficiency_contract.json"
        )
        efficiency = pipeline.episode_efficiency_contract_data(
            self.root,
            episode,
            SimpleNamespace(
                episode_target_hours=8.0,
                retrospective_reserve_minutes=45.0,
                raw_token_budget=50_000_000,
                uncached_input_token_budget=2_000_000,
                output_token_budget=300_000,
                reasoning_token_budget=100_000,
                token_budget_warning_fraction=0.75,
                max_false_passes=0,
                max_known_regression_recurrences=0,
                max_human_issue_scene_rate=0.25,
            ),
        )
        self.write_json(efficiency_path, efficiency)
        central_log = pipeline.episode_efficiency_central_log(
            efficiency
        )
        failure_event = {
            "schema": "lecture-animation-phase-event-v2",
            "event_id": "phase:ep9-global-design-overrun",
            "phase_instance_id": "phase-instance:ep9-global-design",
            "scene_slug": "episode",
            "phase": "design",
            "phase_purpose": "global_spine_and_batch_handoffs",
            "result": "completed",
            "started_at": "2026-07-31T00:00:00+00:00",
            "ended_at": "2026-07-31T00:00:10+00:00",
            "duration_seconds": 10.0,
            "input_tokens": 100,
            "cached_input_tokens": 100,
            "output_tokens": 35_967,
            "reasoning_tokens": 0,
            "token_observed": True,
            "token_allocation_exceeded": ["output_tokens"],
        }
        pipeline.append_jsonl(central_log, failure_event)
        authority_path = episode / "review" / "evolution" / "authority.json"
        self.write_json(
            authority_path,
            {
                "schema": "lecture-animation-user-authority-v1",
                "decision": "authorize",
                "scope": "episode_9_design_budget_continuation",
                "episode": pipeline.relative_or_absolute(
                    episode,
                    self.root,
                ),
                "exact_user_text": "授权继续。",
                "preserve_existing_overage_evidence": True,
                "quality_gates_unchanged": True,
            },
        )
        blocker_path = episode / "review" / "evolution" / "blocker.json"
        self.write_json(
            blocker_path,
            {
                "schema": "lecture-animation-major-delivery-blocker-v1",
                "blocked_phase": "design",
                "gate_result": "rejected",
                "exact_error": (
                    "phase-start allocation exceeds the design token "
                    "envelope: output_tokens"
                ),
            },
        )
        scene_groups = {
            "batch_a": ["g001", "g002", "g003"],
            "batch_b": ["g004", "g005", "g006"],
            "batch_c": ["g007", "g008", "g009"],
        }
        spine_path = episode / "episode_visual_spine.json"
        spine = {
            "production_mode": "parallel_batches",
            "scenes": [
                {"scene_slug": scene}
                for scenes in scene_groups.values()
                for scene in scenes
            ],
        }
        spine["spine_hash"] = pipeline.object_hash(spine)
        self.write_json(spine_path, spine)
        plan_paths = []
        assignments = {}
        for index, (batch_id, scenes) in enumerate(
            scene_groups.items(),
            start=1,
        ):
            plan_path = (
                episode
                / "review"
                / "v2"
                / batch_id
                / "batch_visual_plan.json"
            )
            plan = {
                "batch_id": batch_id,
                "scenes": [
                    {"scene_slug": scene} for scene in scenes
                ],
            }
            plan["batch_plan_hash"] = pipeline.object_hash(plan)
            self.write_json(plan_path, plan)
            plan_paths.append(plan_path)
            assignments[f"/root/ep9-author-{index}"] = {
                "task_key": batch_id,
                "state": "active",
            }
        supervisor_path = episode / "review" / "v2" / "supervisor.json"
        supervisor = {
            "session_id": "ep9-supervisor-r01",
            "supervisor_agent_id": "/root",
            "assignments": assignments,
        }
        supervisor["session_hash"] = pipeline.object_hash(supervisor)
        self.write_json(supervisor_path, supervisor)
        continuation = pipeline.design_budget_continuation_data(
            self.root,
            episode,
            efficiency_contract_path=efficiency_path,
            blocker_path=blocker_path,
            user_authority_path=authority_path,
            episode_spine_path=spine_path,
            batch_plan_paths=plan_paths,
            supervisor_session_path=supervisor_path,
            expires_hours=1,
        )
        self.assertEqual(
            pipeline.validate_design_budget_continuation(
                continuation,
                repo_root=self.root,
                episode=episode,
                efficiency_contract=efficiency,
            ),
            [],
        )
        continuation_path = (
            episode
            / "review"
            / "evolution"
            / "design_continuation.json"
        )
        self.write_json(continuation_path, continuation)
        batch_plan = pipeline.load_json(plan_paths[0])
        batch_path = (
            episode
            / "review"
            / "v2"
            / "batch_a"
            / "production_batch.json"
        )
        batch = {
            "schema": "lecture-animation-production-batch-v2",
            "episode": pipeline.relative_or_absolute(
                episode,
                self.root,
            ),
            "batch_id": "batch_a",
            "scenes": scene_groups["batch_a"],
            "batch_plan_hash": batch_plan["batch_plan_hash"],
            "episode_spine_hash": spine["spine_hash"],
            "author_id": "/root/ep9-author-1",
        }
        batch["batch_hash"] = pipeline.object_hash(batch)
        self.write_json(batch_path, batch)
        common = {
            "repo_root": str(self.root),
            "episode": str(episode),
            "efficiency_contract": str(efficiency_path),
            "production_batch": str(batch_path),
            "run_id": "ep9-g001-design",
            "scene_slug": "g001",
            "phase": "design",
            "phase_purpose": (
                pipeline.DESIGN_BUDGET_CONTINUATION_PHASE_PURPOSE
            ),
            "actor_model": "test-author",
            "actor_role": "animation_author",
            "active_seconds_allocation": 60,
            "raw_token_allocation": 300_000,
            "uncached_input_token_allocation": 30_000,
            "output_token_allocation": 5_000,
            "reasoning_token_allocation": 1_000,
            "prompt_bytes": 100,
            "artifact_input_bytes": 1_000,
            "files_read": 4,
        }
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "design token envelope: output_tokens",
        ):
            pipeline.command_phase_start(
                SimpleNamespace(
                    **common,
                    state=str(episode / "blocked-design.json"),
                )
            )
        state_path = episode / "continued-design.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_phase_start(
                    SimpleNamespace(
                        **common,
                        design_budget_continuation=str(
                            continuation_path
                        ),
                        state=str(state_path),
                    )
                ),
                0,
            )
        state = pipeline.load_json(state_path)
        self.assertEqual(
            state["base_phase_envelope_overflow_at_start"],
            ["output_tokens"],
        )
        self.assertTrue(
            state["design_budget_continuation_admission_applied"]
        )
        with contextlib.redirect_stdout(io.StringIO()):
            result = pipeline.command_phase_end(
                SimpleNamespace(
                    state=str(state_path),
                    phase_log=str(episode / "continued-design.jsonl"),
                    result="completed",
                    manifest_hash="",
                    usage_file=None,
                    input_tokens=100,
                    cached_input_tokens=100,
                    output_tokens=100,
                    reasoning_tokens=0,
                )
            )
        self.assertEqual(result, 0)
        ended = pipeline.load_json(state_path)
        self.assertTrue(
            ended["base_phase_envelope_status_at_end"]["exceeded"]
        )
        self.assertFalse(
            ended["phase_envelope_status_at_end"]["exceeded"]
        )

        reconciliation_ids = []
        for index, scene in enumerate(
            pipeline.DESIGN_BUDGET_CONTINUATION_RECONCILIATION_SCENES,
            start=1,
        ):
            event = {
                "schema": "lecture-animation-phase-event-v2",
                "event_id": f"phase:ep9-policy-restore-{index}",
                "phase_instance_id": (
                    f"phase-instance:ep9-policy-restore-{index}"
                ),
                "scene_slug": scene,
                "phase": "design",
                "phase_purpose": (
                    pipeline.DESIGN_BUDGET_CONTINUATION_PHASE_PURPOSE
                ),
                "actor_role": "animation_author_policy_restore",
                "result": "completed",
                "input_tokens": 1_200_000,
                "cached_input_tokens": 1_100_000,
                "output_tokens": 5_000,
                "reasoning_tokens": 1_000,
                "token_allocation_exceeded": [
                    "raw_input_plus_output_tokens",
                    "output_tokens",
                ],
            }
            pipeline.append_jsonl(central_log, event)
            reconciliation_ids.append(event["event_id"])
        reconciled = pipeline.design_budget_continuation_data(
            self.root,
            episode,
            efficiency_contract_path=efficiency_path,
            blocker_path=blocker_path,
            user_authority_path=authority_path,
            episode_spine_path=spine_path,
            batch_plan_paths=plan_paths,
            supervisor_session_path=supervisor_path,
            expires_hours=1,
            parent_continuation_path=continuation_path,
            reconciliation_event_ids=reconciliation_ids,
        )
        self.assertEqual(
            reconciled["additional_design_token_allowance"],
            pipeline.DESIGN_BUDGET_CONTINUATION_RECONCILED_ALLOWANCE,
        )
        self.assertEqual(
            pipeline.validate_design_budget_continuation(
                reconciled,
                repo_root=self.root,
                episode=episode,
                efficiency_contract=efficiency,
            ),
            [],
        )
        reconciled_path = episode / "review" / "evolution" / "reconciled.json"
        self.write_json(reconciled_path, reconciled)
        replacement_supervisor = pipeline.load_json(supervisor_path)
        replacement_supervisor.pop("session_hash", None)
        for index, assignment in enumerate(
            replacement_supervisor["assignments"].values(),
            start=1,
        ):
            assignment["replacement_of"] = f"/root/ep9_old_{index}"
        replacement_supervisor["session_hash"] = pipeline.object_hash(
            replacement_supervisor
        )
        self.write_json(supervisor_path, replacement_supervisor)
        compact_ids = []
        for index, scene in enumerate(
            pipeline.DESIGN_BUDGET_CONTINUATION_RECONCILIATION_SCENES,
            start=1,
        ):
            event = {
                "schema": "lecture-animation-phase-event-v2",
                "event_id": f"phase:ep9-compact-revision-{index}",
                "phase_instance_id": (
                    f"phase-instance:ep9-compact-revision-{index}"
                ),
                "scene_slug": scene,
                "phase": "design",
                "phase_purpose": (
                    pipeline.DESIGN_BUDGET_CONTINUATION_PHASE_PURPOSE
                ),
                "actor_role": "animation_author_scene_designer",
                "result": "completed",
                "input_tokens": 1_000_000,
                "cached_input_tokens": 950_000,
                "output_tokens": 5_000,
                "reasoning_tokens": 1_000,
                "token_allocation_exceeded": [
                    "raw_input_plus_output_tokens",
                ],
            }
            pipeline.append_jsonl(central_log, event)
            compact_ids.append(event["event_id"])
        compact_replan = pipeline.design_budget_continuation_data(
            self.root,
            episode,
            efficiency_contract_path=efficiency_path,
            blocker_path=blocker_path,
            user_authority_path=authority_path,
            episode_spine_path=spine_path,
            batch_plan_paths=plan_paths,
            supervisor_session_path=supervisor_path,
            expires_hours=1,
            parent_continuation_path=reconciled_path,
            compact_replan_event_ids=compact_ids,
        )
        self.assertEqual(
            compact_replan["additional_design_token_allowance"],
            pipeline.DESIGN_BUDGET_CONTINUATION_COMPACT_REPLAN_ALLOWANCE,
        )
        self.assertEqual(
            pipeline.validate_design_budget_continuation(
                compact_replan,
                repo_root=self.root,
                episode=episode,
                efficiency_contract=efficiency,
            ),
            [],
        )

    def test_planning_quality_repair_requires_sealed_contract(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "requires --quality-repair-contract",
        ):
            pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(self.episode),
                    efficiency_contract=str(self.efficiency_contract),
                    run_id="unsealed-quality-repair",
                    scene_slug="episode",
                    phase="planning",
                    phase_purpose="quality_gate_repair",
                    actor_model="test-planner",
                    active_seconds_allocation=60,
                    raw_token_allocation=1,
                    uncached_input_token_allocation=0,
                    output_token_allocation=0,
                    reasoning_token_allocation=1,
                    state=str(
                        self.episode
                        / "unsealed-quality-repair.json"
                    ),
                )
            )

    def test_efficiency_v3_migration_preserves_contract_and_ledger(
        self,
    ) -> None:
        old = pipeline.load_json(self.efficiency_contract)
        old.pop("contract_hash", None)
        old["schema"] = (
            "lecture-animation-episode-efficiency-contract-v3"
        )
        old["budget"]["schema"] = (
            "lecture-animation-efficiency-budget-v3"
        )
        old["budget"].pop("phase_token_fractions_by_field")
        old["budget"]["phase_token_fractions"] = dict(
            pipeline.DEFAULT_PHASE_TOKEN_FRACTIONS
        )
        old["contract_hash"] = pipeline.object_hash(old)
        self.write_json(self.efficiency_contract, old)
        ledger_path = pipeline.episode_efficiency_reservation_ledger(
            old
        )
        self.write_json(
            ledger_path,
            pipeline.empty_efficiency_reservation_ledger(old),
        )

        pipeline.command_migrate_episode_efficiency_v4(
            SimpleNamespace(input=str(self.efficiency_contract))
        )

        migrated = pipeline.load_json(self.efficiency_contract)
        ledger = pipeline.load_json(ledger_path)
        self.assertEqual(
            migrated["schema"],
            "lecture-animation-episode-efficiency-contract-v4",
        )
        self.assertEqual(
            migrated["budget"]["schema"],
            "lecture-animation-efficiency-budget-v4",
        )
        self.assertEqual(
            migrated["migration"]["from_contract_hash"],
            old["contract_hash"],
        )
        self.assertEqual(
            ledger["efficiency_contract_hash"],
            migrated["contract_hash"],
        )
        self.assertEqual(
            pipeline.validate_episode_efficiency_contract(migrated),
            [],
        )

    def test_phase_start_rejects_unbounded_task_capsule_resources(
        self,
    ) -> None:
        common = {
            "repo_root": str(self.root),
            "episode": str(self.episode),
            "efficiency_contract": str(self.efficiency_contract),
            "run_id": "oversized-task-capsule",
            "scene_slug": "g001",
            "phase": "authoring",
            "phase_purpose": None,
            "actor_model": "test-author",
            "active_seconds_allocation": 60,
            "uncached_input_token_allocation": 0,
            "output_token_allocation": 0,
            "reasoning_token_allocation": 0,
        }
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "raw_input_plus_output_tokens allocation exceeds hard limit",
        ):
            pipeline.command_phase_start(
                SimpleNamespace(
                    **common,
                    raw_token_allocation=(
                        pipeline.DEFAULT_TASK_RESOURCE_LIMITS[
                            "raw_input_plus_output_tokens"
                        ]
                        + 1
                    ),
                    state=str(self.episode / "oversized-token-task.json"),
                )
            )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "prompt_bytes exceeds hard limit",
        ):
            pipeline.command_phase_start(
                SimpleNamespace(
                    **common,
                    raw_token_allocation=1,
                    prompt_bytes=(
                        pipeline.DEFAULT_TASK_RESOURCE_LIMITS[
                            "prompt_bytes"
                        ]
                        + 1
                    ),
                    state=str(
                        self.episode / "oversized-context-task.json"
                    ),
                )
            )

    def test_phase_start_blocks_new_authoring_after_episode_token_cap(
        self,
    ) -> None:
        contract = pipeline.load_json(self.efficiency_contract)
        central_log = pipeline.episode_efficiency_central_log(contract)
        central_log.parent.mkdir(parents=True, exist_ok=True)
        central_log.write_text(
            json.dumps(
                {
                    "schema": "lecture-animation-phase-event-v2",
                    "event_id": "phase:already-over-budget",
                    "phase_instance_id": "phase-instance:over",
                    "scene_slug": "g001",
                    "phase": "authoring",
                    "result": "completed",
                    "started_at": "2026-07-28T00:00:00+00:00",
                    "ended_at": "2026-07-28T00:00:01+00:00",
                    "duration_seconds": 1.0,
                    "input_tokens": 50_000_001,
                    "cached_input_tokens": 50_000_001,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "token_observed": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "budget is exhausted",
        ):
            pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(self.episode),
                    efficiency_contract=str(
                        self.efficiency_contract
                    ),
                    run_id="run-over-budget",
                    scene_slug="g002c_riemann_sum_limit",
                    phase="authoring",
                    phase_purpose=None,
                    actor_model="test-author",
                    active_seconds_allocation=3_600,
                    raw_token_allocation=1_000,
                    uncached_input_token_allocation=500,
                    output_token_allocation=250,
                    reasoning_token_allocation=100,
                    state=str(
                        self.episode
                        / "review"
                        / "evolution"
                        / "blocked-authoring.json"
                    ),
                )
            )

    def test_phase_start_reservations_block_concurrent_phase_oversubscription(
        self,
    ) -> None:
        contract = pipeline.load_json(self.efficiency_contract)
        contract["budget"].update(
            {
                "raw_input_plus_output_tokens": 4_000,
                "uncached_input_tokens": 4_000,
                "output_tokens": 4_000,
                "reasoning_tokens": 4_000,
            }
        )
        contract.pop("contract_hash", None)
        contract["contract_hash"] = pipeline.object_hash(contract)
        self.write_json(self.efficiency_contract, contract)

        first_state = (
            self.episode
            / "review"
            / "evolution"
            / "reservation-first.json"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_phase_start(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        efficiency_contract=str(
                            self.efficiency_contract
                        ),
                        run_id="reservation-first",
                        scene_slug="g001",
                        phase="authoring",
                        phase_purpose=None,
                        actor_model="test-author",
                        active_seconds_allocation=3_600,
                        raw_token_allocation=600,
                        uncached_input_token_allocation=0,
                        output_token_allocation=0,
                        reasoning_token_allocation=0,
                        state=str(first_state),
                    )
                ),
                0,
            )

        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "authoring token envelope",
        ):
            pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(self.episode),
                    efficiency_contract=str(
                        self.efficiency_contract
                    ),
                    run_id="reservation-second",
                    scene_slug="g002",
                    phase="authoring",
                    phase_purpose=None,
                    actor_model="test-author",
                    active_seconds_allocation=3_600,
                    raw_token_allocation=500,
                    uncached_input_token_allocation=0,
                    output_token_allocation=0,
                    reasoning_token_allocation=0,
                    state=str(
                        self.episode
                        / "review"
                        / "evolution"
                        / "reservation-second.json"
                    ),
                )
            )
        ledger = pipeline.load_json(
            pipeline.episode_efficiency_reservation_ledger(
                pipeline.load_json(self.efficiency_contract)
            )
        )
        active = pipeline.active_token_reservations(ledger)
        self.assertEqual(
            active["raw_input_plus_output_tokens"],
            600,
        )

    def test_phase_start_blocks_single_phase_active_time_monopoly(
        self,
    ) -> None:
        contract = pipeline.load_json(self.efficiency_contract)
        central_log = pipeline.episode_efficiency_central_log(contract)
        central_log.parent.mkdir(parents=True, exist_ok=True)
        central_log.write_text(
            json.dumps(
                {
                    "schema": "lecture-animation-phase-event-v2",
                    "event_id": "phase:authoring-seventy-minutes",
                    "phase_instance_id": "phase-instance:authoring-long",
                    "scene_slug": "g001",
                    "phase": "authoring",
                    "phase_purpose": "",
                    "result": "completed",
                    "started_at": "2026-07-28T00:00:00+00:00",
                    "ended_at": "2026-07-28T01:10:00+00:00",
                    "duration_seconds": 4_200.0,
                    "input_tokens": 1,
                    "cached_input_tokens": 1,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "token_observed": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "authoring phase envelope",
        ):
            pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(self.episode),
                    efficiency_contract=str(
                        self.efficiency_contract
                    ),
                    run_id="authoring-time-envelope",
                    scene_slug="g002",
                    phase="authoring",
                    phase_purpose=None,
                    actor_model="test-author",
                    active_seconds_allocation=600,
                    raw_token_allocation=1,
                    uncached_input_token_allocation=0,
                    output_token_allocation=0,
                    reasoning_token_allocation=0,
                    state=str(
                        self.episode / "authoring-time-envelope.json"
                    ),
                )
            )

    def test_repair_retries_charge_repair_budget_bucket(self) -> None:
        self.assertEqual(
            pipeline.phase_budget_bucket(
                "render",
                "repair_rerender",
            ),
            "repair",
        )
        self.assertEqual(
            pipeline.phase_budget_bucket(
                "tts",
                "pronunciation_retry",
            ),
            "repair",
        )
        self.assertEqual(
            pipeline.phase_budget_bucket("render", "candidate"),
            "render",
        )
        self.assertEqual(
            pipeline.phase_budget_bucket(
                "planning",
                "quality_gate_repair",
            ),
            pipeline.PLANNING_QUALITY_REPAIR_BUCKET,
        )
        self.assertEqual(
            pipeline.phase_active_budget_bucket(
                "planning",
                "quality_gate_repair",
            ),
            "planning",
        )
        contract = {
            "budget": pipeline.default_efficiency_budget(),
        }
        self.assertEqual(
            pipeline.effective_efficiency_limits(
                contract,
                "asr",
                "pronunciation_retry",
            )["stage"],
            "closure",
        )

    def test_local_synthesis_admission_is_zero_model_token_and_narrow(
        self,
    ) -> None:
        sentinel = {
            "raw_input_plus_output_tokens": 1,
            "uncached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
        }
        self.assertTrue(
            pipeline.local_synthesis_admission(
                "tts",
                "local_synthesis",
                "local:mlx-indextts2",
                sentinel,
            )
        )
        self.assertFalse(
            pipeline.local_synthesis_admission(
                "tts",
                "local_synthesis",
                "gpt-5.6-sol",
                sentinel,
            )
        )
        self.assertFalse(
            pipeline.local_synthesis_admission(
                "tts",
                "local_synthesis",
                "local:mlx-indextts2",
                {**sentinel, "output_tokens": 1},
            )
        )
        over_budget = {
            "active_exceeded": False,
            "token_status": {
                "exceeded": ["raw_input_plus_output_tokens"]
            },
        }
        self.assertFalse(
            pipeline.phase_blocked_by_efficiency_budget(
                "tts",
                "local_synthesis",
                over_budget,
            )
        )
        self.assertTrue(
            pipeline.phase_blocked_by_efficiency_budget(
                "tts",
                "initial",
                over_budget,
            )
        )
        self.assertTrue(
            pipeline.local_alignment_admission(
                "asr",
                "local_alignment",
                "local:qwen-srt",
                sentinel,
            )
        )
        self.assertFalse(
            pipeline.local_alignment_admission(
                "asr",
                "local_alignment",
                "qwen-srt-cloud",
                sentinel,
            )
        )

    def test_mandatory_retrospective_starts_after_outer_token_overrun(
        self,
    ) -> None:
        contract = pipeline.load_json(self.efficiency_contract)
        central_log = pipeline.episode_efficiency_central_log(contract)
        central_log.parent.mkdir(parents=True, exist_ok=True)
        central_log.write_text(
            json.dumps(
                {
                    "schema": "lecture-animation-phase-event-v2",
                    "event_id": "phase:historical-outer-overrun",
                    "phase_instance_id": (
                        "phase-instance:historical-outer-overrun"
                    ),
                    "scene_slug": "g001",
                    "phase": "repair",
                    "phase_purpose": "repair_rerender",
                    "result": "completed",
                    "started_at": "2026-07-28T00:00:00+00:00",
                    "ended_at": "2026-07-28T00:00:10+00:00",
                    "duration_seconds": 10.0,
                    "input_tokens": 50_000_001,
                    "cached_input_tokens": 50_000_001,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "token_observed": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        state = (
            self.episode
            / "review"
            / "evolution"
            / "retrospective-after-overrun.json"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_phase_start(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        efficiency_contract=str(
                            self.efficiency_contract
                        ),
                        run_id="retrospective-after-overrun",
                        scene_slug="episode",
                        phase="retrospective",
                        phase_purpose="episode_evolution",
                        actor_model="test-retrospective-agent",
                        actor_role="main_producer",
                        reasoning_effort="high",
                        active_seconds_allocation=600,
                        raw_token_allocation=1_000,
                        uncached_input_token_allocation=100,
                        output_token_allocation=100,
                        reasoning_token_allocation=100,
                        prompt_bytes=0,
                        artifact_input_bytes=0,
                        files_read=0,
                        usage_file=None,
                        state=str(state),
                    )
                ),
                0,
            )
        timer = pipeline.load_json(state)
        self.assertTrue(
            timer[
                "mandatory_retrospective_overrun_admission_applied"
            ]
        )
        self.assertIn(
            "raw_input_plus_output_tokens",
            timer["base_episode_reservation_overflow_at_start"],
        )
        self.assertEqual(timer["reserve_stage"], "retrospective")

    def test_mandatory_retrospective_starts_after_outer_active_time_overrun(
        self,
    ) -> None:
        contract = pipeline.load_json(self.efficiency_contract)
        central_log = pipeline.episode_efficiency_central_log(contract)
        central_log.parent.mkdir(parents=True, exist_ok=True)
        central_log.write_text(
            json.dumps(
                {
                    "schema": "lecture-animation-phase-event-v2",
                    "event_id": "phase:historical-active-overrun",
                    "phase_instance_id": (
                        "phase-instance:historical-active-overrun"
                    ),
                    "scene_slug": "g001",
                    "phase": "repair",
                    "phase_purpose": "candidate_repair",
                    "result": "completed",
                    "started_at": "2026-07-28T00:00:00+00:00",
                    "ended_at": "2026-07-28T08:00:01+00:00",
                    "duration_seconds": 28_801.0,
                    "input_tokens": 1,
                    "cached_input_tokens": 1,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "token_observed": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        state = (
            self.episode
            / "review"
            / "evolution"
            / "retrospective-after-active-overrun.json"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_phase_start(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        efficiency_contract=str(
                            self.efficiency_contract
                        ),
                        run_id="retrospective-after-active-overrun",
                        scene_slug="episode",
                        phase="retrospective",
                        phase_purpose="episode_evolution",
                        actor_model="test-retrospective-agent",
                        actor_role="main_producer",
                        reasoning_effort="high",
                        active_seconds_allocation=600,
                        raw_token_allocation=1_000,
                        uncached_input_token_allocation=100,
                        output_token_allocation=100,
                        reasoning_token_allocation=100,
                        prompt_bytes=0,
                        artifact_input_bytes=0,
                        files_read=0,
                        usage_file=None,
                        state=str(state),
                    )
                ),
                0,
            )
        timer = pipeline.load_json(state)
        self.assertTrue(
            timer[
                "mandatory_retrospective_overrun_admission_applied"
            ]
        )
        self.assertTrue(timer["base_stage_active_overflow_at_start"])
        self.assertEqual(timer["reserve_stage"], "retrospective")

    def test_local_tts_active_time_replan_is_measured_and_narrow(
        self,
    ) -> None:
        contract = pipeline.load_json(self.efficiency_contract)
        projection_path = (
            self.episode / "review" / "evolution" / "tts_projection.json"
        )
        projection_path.parent.mkdir(parents=True, exist_ok=True)
        self.write_json(
            projection_path,
            {
                "schema": "lecture-animation-local-tts-budget-projection-v1",
                "quality_route_unchanged": True,
                "recommended_budget_seconds": 2621,
            },
        )
        replan = {
            "schema": "lecture-animation-local-active-time-replan-v1",
            "episode": pipeline.relative_or_absolute(
                self.episode, self.root
            ),
            "phase": "tts",
            "phase_purpose": "local_synthesis",
            "efficiency_contract_hash": contract["contract_hash"],
            "projection_path": pipeline.relative_or_absolute(
                projection_path, self.root
            ),
            "projection_sha256": hashlib.sha256(
                projection_path.read_bytes()
            ).hexdigest(),
            "baseline_active_seconds": contract["budget"][
                "phase_active_seconds"
            ]["tts"],
            "extended_active_seconds": 2621,
            "quality_parameters_unchanged": [
                "voice",
                "seed",
                "diffusion_steps",
                "cfg_rate",
                "normalization",
                "approved_narration",
                "review_gates",
            ],
        }
        replan["replan_hash"] = pipeline.object_hash(replan)
        self.assertEqual(
            pipeline.validate_local_active_time_replan(
                replan,
                repo_root=self.root,
                episode=self.episode,
                efficiency_contract=contract,
            ),
            [],
        )
        tampered = dict(replan)
        tampered["extended_active_seconds"] = 1501
        errors = pipeline.validate_local_active_time_replan(
            tampered,
            repo_root=self.root,
            episode=self.episode,
            efficiency_contract=contract,
        )
        self.assertIn("local active-time replan hash is invalid", errors)
        self.assertTrue(
            any(
                "projection recommendation" in error
                for error in errors
            )
        )

    def test_phase_envelopes_cannot_consume_reserved_stages(self) -> None:
        budget = pipeline.default_efficiency_budget()
        budget["phase_active_seconds"]["planning"] += 600
        budget["phase_active_seconds"]["finalization"] -= 600
        errors = pipeline.validate_efficiency_budget_data(budget)
        self.assertIn(
            "early phase active-time envelopes consume the closure reserve",
            errors,
        )

        budget = pipeline.default_efficiency_budget()
        budget["phase_token_fractions_by_field"]["reasoning_tokens"][
            "authoring"
        ] += 0.01
        budget["phase_token_fractions_by_field"]["reasoning_tokens"][
            "finalization"
        ] -= 0.01
        errors = pipeline.validate_efficiency_budget_data(budget)
        self.assertIn(
            "reasoning_tokens early phase token envelopes consume the closure reserve",
            errors,
        )

    def test_early_phase_cannot_consume_closure_token_reserve(
        self,
    ) -> None:
        contract = pipeline.load_json(self.efficiency_contract)
        contract["budget"].update(
            {
                "raw_input_plus_output_tokens": 1_000,
                "uncached_input_tokens": 1_000,
                "output_tokens": 1_000,
                "reasoning_tokens": 1_000,
            }
        )
        contract.pop("contract_hash", None)
        contract["contract_hash"] = pipeline.object_hash(contract)
        self.write_json(self.efficiency_contract, contract)
        central_log = pipeline.episode_efficiency_central_log(contract)
        central_log.parent.mkdir(parents=True, exist_ok=True)
        central_log.write_text(
            json.dumps(
                {
                    "schema": "lecture-animation-phase-event-v2",
                    "event_id": "phase:spent-early-budget",
                    "phase_instance_id": "phase-instance:spent",
                    "scene_slug": "g001",
                    "phase": "authoring",
                    "result": "completed",
                    "started_at": "2026-07-28T00:00:00+00:00",
                    "ended_at": "2026-07-28T00:00:01+00:00",
                    "duration_seconds": 1.0,
                    "input_tokens": 700,
                    "cached_input_tokens": 700,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "token_observed": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        common = {
            "repo_root": str(self.root),
            "episode": str(self.episode),
            "efficiency_contract": str(self.efficiency_contract),
            "scene_slug": "g002",
            "phase_purpose": None,
            "actor_model": "test-worker",
            "active_seconds_allocation": 60,
            "raw_token_allocation": 60,
            "uncached_input_token_allocation": 0,
            "output_token_allocation": 0,
            "reasoning_token_allocation": 0,
        }
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "reservation exceeds the remaining episode budget",
        ):
            pipeline.command_phase_start(
                SimpleNamespace(
                    **common,
                    run_id="early-reserve-blocked",
                    phase="authoring",
                    state=str(
                        self.episode / "early-reserve-blocked.json"
                    ),
                )
            )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_phase_start(
                    SimpleNamespace(
                        **common,
                        run_id="closure-reserve-allowed",
                        phase="review",
                        state=str(
                            self.episode
                            / "closure-reserve-allowed.json"
                        ),
                    )
                ),
                0,
            )

    def test_early_phase_cannot_consume_closure_time_reserve(
        self,
    ) -> None:
        contract = pipeline.load_json(self.efficiency_contract)
        central_log = pipeline.episode_efficiency_central_log(contract)
        central_log.parent.mkdir(parents=True, exist_ok=True)
        central_log.write_text(
            json.dumps(
                {
                    "schema": "lecture-animation-phase-event-v2",
                    "event_id": "phase:four-hours-forty",
                    "phase_instance_id": "phase-instance:four-forty",
                    "scene_slug": "g001",
                    "phase": "authoring",
                    "result": "completed",
                    "started_at": "2026-07-28T00:00:00+00:00",
                    "ended_at": "2026-07-28T04:40:00+00:00",
                    "duration_seconds": 16_800.0,
                    "input_tokens": 1,
                    "cached_input_tokens": 1,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "token_observed": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "active-time reservation exceeds the early stage limit",
        ):
            pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(self.episode),
                    efficiency_contract=str(
                        self.efficiency_contract
                    ),
                    run_id="early-time-blocked",
                    scene_slug="g002",
                    phase="authoring",
                    phase_purpose=None,
                    actor_model="test-worker",
                    active_seconds_allocation=600,
                    raw_token_allocation=1,
                    uncached_input_token_allocation=0,
                    output_token_allocation=0,
                    reasoning_token_allocation=0,
                    state=str(
                        self.episode / "early-time-blocked.json"
                    ),
                )
            )

    def test_overdue_active_reservation_blocks_new_work(
        self,
    ) -> None:
        first_state = self.episode / "overdue-first.json"
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(self.episode),
                    efficiency_contract=str(
                        self.efficiency_contract
                    ),
                    run_id="overdue-first",
                    scene_slug="g001",
                    phase="authoring",
                    phase_purpose=None,
                    actor_model="test-worker",
                    active_seconds_allocation=60,
                    raw_token_allocation=1,
                    uncached_input_token_allocation=0,
                    output_token_allocation=0,
                    reasoning_token_allocation=0,
                    state=str(first_state),
                )
            )
        contract = pipeline.load_json(self.efficiency_contract)
        ledger_path = (
            pipeline.episode_efficiency_reservation_ledger(contract)
        )
        ledger = pipeline.load_json(ledger_path)
        reservation = next(iter(ledger["reservations"].values()))
        reservation["created_at"] = "2020-01-01T00:00:00+00:00"
        ledger.pop("ledger_hash", None)
        ledger["ledger_hash"] = pipeline.object_hash(ledger)
        self.write_json(ledger_path, ledger)
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(self.episode),
                    efficiency_contract=str(
                        self.efficiency_contract
                    ),
                    run_id="overdue-second",
                    scene_slug="g002",
                    phase="authoring",
                    phase_purpose=None,
                    actor_model="test-worker",
                    active_seconds_allocation=60,
                    raw_token_allocation=1,
                    uncached_input_token_allocation=0,
                    output_token_allocation=0,
                    reasoning_token_allocation=0,
                    state=str(self.episode / "overdue-second.json"),
                )
            )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "unreconciled stale wrapper",
        ):
            pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(self.episode),
                    efficiency_contract=str(self.efficiency_contract),
                    run_id="overdue-same-scene",
                    scene_slug="g001",
                    phase="authoring",
                    phase_purpose=None,
                    actor_model="test-worker",
                    active_seconds_allocation=60,
                    raw_token_allocation=1,
                    uncached_input_token_allocation=0,
                    output_token_allocation=0,
                    reasoning_token_allocation=0,
                    state=str(self.episode / "overdue-same-scene.json"),
                )
            )

    def test_parallel_cli_starts_cannot_race_past_phase_token_envelope(
        self,
    ) -> None:
        contract = pipeline.load_json(self.efficiency_contract)
        contract["budget"].update(
            {
                "raw_input_plus_output_tokens": 4_000,
                "uncached_input_tokens": 4_000,
                "output_tokens": 4_000,
                "reasoning_tokens": 4_000,
            }
        )
        contract.pop("contract_hash", None)
        contract["contract_hash"] = pipeline.object_hash(contract)
        self.write_json(self.efficiency_contract, contract)

        processes = []
        for suffix in ("a", "b"):
            command = [
                "python3",
                str(MODULE_PATH),
                "phase-start",
                "--repo-root",
                str(self.root),
                "--episode",
                str(self.episode),
                "--efficiency-contract",
                str(self.efficiency_contract),
                "--run-id",
                f"parallel-reservation-{suffix}",
                "--scene-slug",
                f"g00{suffix}",
                "--phase",
                "authoring",
                "--actor-model",
                "test-author",
                "--active-seconds-allocation",
                "3600",
                "--raw-token-allocation",
                "600",
                "--uncached-input-token-allocation",
                "0",
                "--output-token-allocation",
                "0",
                "--reasoning-token-allocation",
                "0",
                "--state",
                str(
                    self.episode
                    / "review"
                    / "evolution"
                    / f"parallel-reservation-{suffix}.json"
                ),
            ]
            processes.append(
                subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            )
        results = [process.communicate(timeout=10) for process in processes]
        self.assertEqual(
            sorted(process.returncode for process in processes),
            [0, 2],
        )
        self.assertTrue(
            any(
                "authoring token envelope"
                in stderr
                for _, stderr in results
            )
        )

    def test_phase_end_fails_and_releases_when_task_allocation_is_exceeded(
        self,
    ) -> None:
        state = (
            self.episode
            / "review"
            / "evolution"
            / "allocation-overrun.json"
        )
        phase_log = (
            self.episode
            / "review"
            / "evolution"
            / "allocation-overrun.jsonl"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(self.episode),
                    efficiency_contract=str(
                        self.efficiency_contract
                    ),
                    run_id="allocation-overrun",
                    scene_slug="g001",
                    phase="authoring",
                    phase_purpose=None,
                    actor_model="test-author",
                    active_seconds_allocation=0.000001,
                    raw_token_allocation=100,
                    uncached_input_token_allocation=0,
                    output_token_allocation=0,
                    reasoning_token_allocation=0,
                    state=str(state),
                )
            )
            result = pipeline.command_phase_end(
                SimpleNamespace(
                    state=str(state),
                    phase_log=str(phase_log),
                    result="completed",
                    manifest_hash="",
                    usage_file=None,
                    input_tokens=1,
                    cached_input_tokens=1,
                    output_tokens=1,
                    reasoning_tokens=0,
                )
            )
        self.assertEqual(result, 2)
        event = pipeline.event_rows(phase_log)[0]
        self.assertEqual(
            event["token_allocation_exceeded"],
            ["output_tokens"],
        )
        self.assertTrue(event["active_allocation_exceeded"])
        ledger = pipeline.load_json(
            pipeline.episode_efficiency_reservation_ledger(
                pipeline.load_json(self.efficiency_contract)
            )
        )
        self.assertFalse(
            pipeline.active_token_reservations(ledger)[
                "raw_input_plus_output_tokens"
            ]
        )

    def test_phase_end_enriches_legacy_shared_rows_before_envelope_check(
        self,
    ) -> None:
        contract = pipeline.load_json(self.efficiency_contract)
        contract["budget"]["raw_input_plus_output_tokens"] = (
            2_000_000
        )
        contract.pop("contract_hash", None)
        contract["contract_hash"] = pipeline.object_hash(contract)
        self.write_json(self.efficiency_contract, contract)

        shared_key = "legacy-two-wrapper-design"
        legacy_state = (
            self.episode
            / "review"
            / "v2"
            / "g001"
            / "legacy-design-state.json"
        )
        legacy_instance = "phase-instance:shared:legacy-g001"
        self.write_json(
            legacy_state,
            {
                "schema": "lecture-animation-phase-timer-v2",
                "run_id": "legacy-g001-design",
                "scene_slug": "g001",
                "phase": "design",
                "phase_purpose": "",
                "actor_model": "test-author",
                "actor_role": "batch-designer",
                "shared_work_key": shared_key,
                "phase_instance_id": legacy_instance,
                "efficiency_contract_path": str(
                    self.efficiency_contract
                ),
            },
        )
        central_log = pipeline.episode_efficiency_central_log(
            contract
        )
        pipeline.append_jsonl(
            central_log,
            {
                "schema": "lecture-animation-phase-event-v2",
                "event_id": "phase:legacy-g001-design",
                "run_id": "legacy-g001-design",
                "scene_slug": "g001",
                "phase": "design",
                "phase_purpose": "",
                "actor_model": "test-author",
                "actor_role": "batch-designer",
                "phase_instance_id": legacy_instance,
                "started_at": "2026-07-30T00:00:00+00:00",
                "ended_at": "2026-07-30T00:00:10+00:00",
                "duration_seconds": 10.0,
                "input_tokens": 150_000,
                "cached_input_tokens": 150_000,
                "output_tokens": 0,
                "reasoning_tokens": 0,
                "token_observed": True,
                "result": "completed",
            },
        )
        ledger = pipeline.empty_efficiency_reservation_ledger(
            contract
        )
        ledger["reservations"] = {
            "reservation:legacy-g001": {
                "reservation_id": "reservation:legacy-g001",
                "status": "released",
                "state_path": str(legacy_state),
                "run_id": "legacy-g001-design",
                "scene_slug": "g001",
                "phase": "design",
                "phase_instance_id": legacy_instance,
                "allocation": {
                    "raw_input_plus_output_tokens": 150_000,
                    "uncached_input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                },
            }
        }
        ledger["revision"] = 1
        ledger.pop("ledger_hash")
        ledger["ledger_hash"] = pipeline.object_hash(ledger)
        self.write_json(
            pipeline.episode_efficiency_reservation_ledger(
                contract
            ),
            ledger,
        )

        current_state = (
            self.episode
            / "review"
            / "v2"
            / "g002"
            / "current-design-state.json"
        )
        phase_log = (
            self.episode
            / "review"
            / "v2"
            / "g002"
            / "phase_log.jsonl"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_phase_start(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        efficiency_contract=str(
                            self.efficiency_contract
                        ),
                        run_id="current-g002-design",
                        scene_slug="g002",
                        phase="design",
                        phase_purpose=None,
                        actor_model="test-author",
                        actor_role="batch-designer",
                        reasoning_effort="high",
                        active_seconds_allocation=60,
                        raw_token_allocation=150_000,
                        uncached_input_token_allocation=0,
                        output_token_allocation=0,
                        reasoning_token_allocation=0,
                        phase_instance_id=None,
                        shared_work_key=shared_key,
                        prompt_bytes=0,
                        artifact_input_bytes=0,
                        files_read=0,
                        usage_file=None,
                        state=str(current_state),
                    )
                ),
                0,
            )
            self.assertEqual(
                pipeline.command_phase_end(
                    SimpleNamespace(
                        state=str(current_state),
                        phase_log=str(phase_log),
                        result="completed",
                        manifest_hash="",
                        usage_file=None,
                        input_tokens=150_000,
                        cached_input_tokens=150_000,
                        output_tokens=0,
                        reasoning_tokens=0,
                    )
                ),
                0,
            )
        accounted = pipeline.phase_rows_with_accounting(
            pipeline.event_rows(central_log),
            contract=contract,
            reservation_ledger=pipeline.load_json(
                pipeline.episode_efficiency_reservation_ledger(
                    contract
                )
            ),
        )
        self.assertEqual(
            pipeline.phase_bucket_token_usage(
                accounted,
                "design",
            )["raw_input_plus_output_tokens"],
            150_000,
        )
        self.assertAlmostEqual(
            pipeline.phase_bucket_active_seconds(
                accounted,
                "design",
            ),
            10.0,
            delta=1.0,
        )

    def test_phase_start_rejects_batch_slug_and_binds_exact_member_scene(
        self,
    ) -> None:
        batch_path = (
            self.episode
            / "review"
            / "v2"
            / "batch_a"
            / "production_batch.json"
        )
        batch = {
            "schema": "lecture-animation-production-batch-v2",
            "batch_id": "batch_a",
            "episode": pipeline.relative_or_absolute(
                self.episode,
                self.root,
            ),
            "scenes": [
                "g001_exact_member",
                "g002_exact_member",
            ],
        }
        batch["batch_hash"] = pipeline.object_hash(batch)
        self.write_json(batch_path, batch)
        rejected_state = (
            self.episode
            / "review"
            / "evolution"
            / "batch-slug-rejected.json"
        )
        base = {
            "repo_root": str(self.root),
            "episode": str(self.episode),
            "efficiency_contract": str(
                self.efficiency_contract
            ),
            "production_batch": str(batch_path),
            "run_id": "batch-a-shared-design",
            "phase": "design",
            "phase_purpose": None,
            "actor_model": "test-author",
            "actor_role": "animation_author",
            "reasoning_effort": "high",
            "active_seconds_allocation": 60,
            "raw_token_allocation": 100,
            "uncached_input_token_allocation": 50,
            "output_token_allocation": 20,
            "reasoning_token_allocation": 10,
            "phase_instance_id": None,
            "shared_work_key": "shared-design",
            "prompt_bytes": 0,
            "artifact_input_bytes": 0,
            "files_read": 0,
            "usage_file": None,
        }
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "exact member",
        ):
            pipeline.command_phase_start(
                SimpleNamespace(
                    **base,
                    scene_slug="batch_a",
                    state=str(rejected_state),
                )
            )
        self.assertFalse(rejected_state.exists())

        accepted_state = (
            self.episode
            / "review"
            / "evolution"
            / "exact-member-accepted.json"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_phase_start(
                    SimpleNamespace(
                        **base,
                        scene_slug="g001_exact_member",
                        state=str(accepted_state),
                    )
                ),
                0,
            )
        state = pipeline.load_json(accepted_state)
        self.assertEqual(
            state["production_batch_id"],
            "batch_a",
        )
        self.assertEqual(
            state["production_batch_hash"],
            batch["batch_hash"],
        )
        self.assertEqual(
            state["scene_slug"],
            "g001_exact_member",
        )

    def test_raw_budget_replan_is_raw_only_single_accounting_and_three_keys(
        self,
    ) -> None:
        efficiency = pipeline.load_json(self.efficiency_contract)
        reservation_path = (
            pipeline.episode_efficiency_reservation_ledger(efficiency)
        )
        self.write_json(
            reservation_path,
            pipeline.empty_efficiency_reservation_ledger(efficiency),
        )
        central_log = pipeline.episode_efficiency_central_log(efficiency)
        central_log.parent.mkdir(parents=True, exist_ok=True)
        historical_overrun = {
                    "schema": "lecture-animation-phase-event-v2",
                    "event_id": "phase:raw-budget-already-failed",
                    "run_id": "historical-overrun",
                    "scene_slug": "g000_historical",
                    "phase": "authoring",
                    "started_at": "2026-07-30T00:00:00+00:00",
                    "ended_at": "2026-07-30T00:01:00+00:00",
                    "duration_seconds": 60,
                    "input_tokens": 50_000_001,
                    "cached_input_tokens": 50_000_001,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "token_observed": True,
                    "result": "completed",
                }
        review_near_envelope = {
            "schema": "lecture-animation-phase-event-v2",
            "event_id": "phase:review-near-envelope",
            "run_id": "review-near-envelope",
            "scene_slug": "g000_review",
            "phase": "review",
            "phase_purpose": "standard-review",
            "started_at": "2026-07-30T00:02:00+00:00",
            "ended_at": "2026-07-30T00:03:00+00:00",
            "duration_seconds": 60,
            "input_tokens": 5_999_900,
            "cached_input_tokens": 5_999_900,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "token_observed": True,
            "result": "completed",
        }
        central_log.write_text(
            "\n".join(
                json.dumps(row)
                for row in (
                    historical_overrun,
                    review_near_envelope,
                )
            )
            + "\n",
            encoding="utf-8",
        )
        scenes = [f"g00{index}_animatic" for index in range(1, 5)]
        batch_path = (
            self.episode / "review" / "v2" / "batch-a.json"
        )
        batch = {
            "schema": "lecture-animation-production-batch-v2",
            "efficiency_contract_version": 2,
            "episode_efficiency_contract_hash": efficiency[
                "contract_hash"
            ],
            "batch_id": "batch-a",
            "episode": pipeline.relative_or_absolute(
                self.episode,
                self.root,
            ),
            "scenes": scenes,
            "author_id": "author-a",
        }
        batch["batch_hash"] = pipeline.object_hash(batch)
        self.write_json(batch_path, batch)
        supervisor_path = (
            self.episode / "review" / "v2" / "supervisor.json"
        )
        supervisor = {
            "schema": "lecture-animation-supervisor-session-v2",
            "session_id": "supervisor:test",
            "supervisor_agent_id": "main-reviewer",
            "closed_at": None,
            "assignments": {
                "author-a": {
                    "state": "active",
                    "role": "production_author",
                    "task_key": "batch-a",
                    "scope": "four animatic scenes",
                    "model": "test-model",
                },
                "reviewer-a": {
                    "state": "active",
                    "role": "independent_reviewer",
                    "task_key": "review-batch-a-animatic-v02",
                    "scope": "independent review of batch-a",
                    "model": "test-review-model",
                }
            },
        }
        supervisor["session_hash"] = pipeline.object_hash(supervisor)
        self.write_json(supervisor_path, supervisor)

        def authorize(key: str, allowance: int = 1_500_000) -> Path:
            output = (
                self.episode
                / "review"
                / "evolution"
                / f"{key}.json"
            )
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.command_authorize_raw_budget_replan(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        efficiency_contract=str(
                            self.efficiency_contract
                        ),
                        production_batch=str(batch_path),
                        supervisor_session=str(supervisor_path),
                        authorizing_supervisor_agent_id="main-reviewer",
                        author_agent_id="author-a",
                        reviewer_actor_agent_id="reviewer-a",
                        scenes=",".join(scenes),
                        shared_work_key=key,
                        allowed_output_path=[
                            str(
                                self.episode
                                / "review"
                                / "v2"
                                / "animatic-review"
                            )
                        ],
                        raw_token_allowance=allowance,
                        expires_hours=6.0,
                        output=str(output),
                    )
                )
            return output

        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "1,500,000",
        ):
            authorize("too-large", 1_500_001)
        concurrent_keys = [
            "mandatory-review-a",
            "mandatory-review-b",
            "mandatory-review-c",
        ]
        concurrent_outputs = [
            (
                self.episode
                / "review"
                / "evolution"
                / f"{key}.json"
            )
            for key in concurrent_keys
        ]
        processes = [
            subprocess.Popen(
                [
                    "python3",
                    str(MODULE_PATH),
                    "authorize-raw-budget-replan",
                    "--repo-root",
                    str(self.root),
                    "--episode",
                    str(self.episode),
                    "--efficiency-contract",
                    str(self.efficiency_contract),
                    "--production-batch",
                    str(batch_path),
                    "--supervisor-session",
                    str(supervisor_path),
                    "--authorizing-supervisor-agent-id",
                    "main-reviewer",
                    "--author-agent-id",
                    "author-a",
                    "--reviewer-actor-agent-id",
                    "reviewer-a",
                    "--scenes",
                    ",".join(scenes),
                    "--shared-work-key",
                    key,
                    "--allowed-output-path",
                    str(
                        self.episode
                        / "review"
                        / "v2"
                        / "animatic-review"
                    ),
                    "--raw-token-allowance",
                    "1500000",
                    "--expires-hours",
                    "6",
                    "--output",
                    str(output),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for key, output in zip(
                concurrent_keys,
                concurrent_outputs,
            )
        ]
        process_results = [
            process.communicate(timeout=10)
            for process in processes
        ]
        self.assertEqual(
            [process.returncode for process in processes],
            [0, 0, 0],
            process_results,
        )
        overlay = concurrent_outputs[0]
        original_efficiency_hash = pipeline.load_json(
            self.efficiency_contract
        )["contract_hash"]
        original_batch_hash = pipeline.load_json(batch_path)[
            "batch_hash"
        ]

        def start(
            scene: str,
            *,
            raw: int = 100,
            phase: str = "review",
            purpose: str = (
                "mandatory_independent_animatic_review"
            ),
            actor: str = "reviewer-a",
            shared_key: str = "mandatory-review-a",
            active_seconds: float = 60,
            uncached: int = 0,
        ) -> Path:
            state = (
                self.episode
                / "review"
                / "evolution"
                / f"{scene}-raw-review.json"
            )
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.command_phase_start(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        efficiency_contract=str(
                            self.efficiency_contract
                        ),
                        production_batch=str(batch_path),
                        raw_budget_replan=str(overlay),
                        actor_agent_id=actor,
                        run_id=f"{scene}-review",
                        scene_slug=scene,
                        phase=phase,
                        phase_purpose=purpose,
                        actor_model="test-reviewer",
                        actor_role="independent_reviewer",
                        reasoning_effort="high",
                        active_seconds_allocation=active_seconds,
                        raw_token_allocation=raw,
                        uncached_input_token_allocation=uncached,
                        output_token_allocation=0,
                        reasoning_token_allocation=0,
                        phase_instance_id=None,
                        shared_work_key=shared_key,
                        prompt_bytes=0,
                        artifact_input_bytes=0,
                        files_read=0,
                        usage_file=None,
                        state=str(state),
                    )
                )
            return state

        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "phase=review",
        ):
            start(scenes[0], phase="design")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "mandatory_independent_animatic_review",
        ):
            start(scenes[0], purpose="ordinary_review")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "actor-agent-id",
        ):
            start(scenes[0], actor="wrong-reviewer")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "shared-work-key",
        ):
            start(scenes[0], shared_key="wrong-key")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "exact member",
        ):
            start("g999_outside")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "active-time reservation",
        ):
            start(scenes[0], active_seconds=3_601)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "hard limit",
        ):
            start(scenes[0], uncached=100_001)
        original_overlay = pipeline.load_json(overlay)
        tampered_overlay = dict(original_overlay)
        tampered_overlay["allowed_output_paths"] = [
            pipeline.relative_or_absolute(
                self.root / "outside",
                self.root,
            )
        ]
        self.write_json(overlay, tampered_overlay)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "hash is invalid",
        ):
            start(scenes[0])
        expired_overlay = dict(original_overlay)
        expired_overlay["expires_at"] = "2026-07-29T00:00:00+00:00"
        expired_overlay.pop("replan_hash", None)
        expired_overlay["replan_hash"] = pipeline.object_hash(
            expired_overlay
        )
        self.write_json(overlay, expired_overlay)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "expired",
        ):
            start(scenes[0])
        self.write_json(overlay, original_overlay)
        review_over_envelope = dict(review_near_envelope)
        review_over_envelope["event_id"] = (
            "phase:review-over-envelope"
        )
        review_over_envelope["input_tokens"] = 6_000_001
        review_over_envelope["cached_input_tokens"] = 6_000_001
        central_log.write_text(
            "\n".join(
                json.dumps(row)
                for row in (
                    historical_overrun,
                    review_over_envelope,
                )
            )
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "review token envelope",
        ):
            start(scenes[0])
        central_log.write_text(
            "\n".join(
                json.dumps(row)
                for row in (
                    historical_overrun,
                    review_near_envelope,
                )
            )
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "identical allocation",
        ):
            first_state = start(scenes[0])
            start(scenes[1], raw=99)
        states = [
            first_state,
            *[start(scene) for scene in scenes[1:]],
        ]
        ledger = pipeline.load_json(reservation_path)
        overlay_reservations = [
            row
            for row in ledger["reservations"].values()
            if row.get("raw_budget_replan_hash")
        ]
        self.assertEqual(len(overlay_reservations), 1)
        self.assertEqual(
            len(overlay_reservations[0]["wrapper_state_paths"]),
            4,
        )
        phase_log = (
            self.episode / "review" / "evolution" / "raw-review.jsonl"
        )
        review_output = (
            self.episode
            / "review"
            / "v2"
            / "animatic-review"
            / "independent-review.json"
        )
        self.write_json(
            review_output,
            {
                "verdict": "revise",
                "evidence": "mandatory independent animatic review",
            },
        )
        missing_output = review_output.with_name("missing.json")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "missing",
        ):
            pipeline.command_phase_end(
                SimpleNamespace(
                    state=str(states[0]),
                    phase_log=str(phase_log),
                    result="blocked",
                    manifest_hash="",
                    usage_file=None,
                    input_tokens=100,
                    cached_input_tokens=100,
                    output_tokens=0,
                    reasoning_tokens=0,
                    review_output=[str(missing_output)],
                )
            )
        outside_output = self.root / "outside-review.json"
        self.write_json(outside_output, {"verdict": "revise"})
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "outside",
        ):
            pipeline.command_phase_end(
                SimpleNamespace(
                    state=str(states[0]),
                    phase_log=str(phase_log),
                    result="blocked",
                    manifest_hash="",
                    usage_file=None,
                    input_tokens=100,
                    cached_input_tokens=100,
                    output_tokens=0,
                    reasoning_tokens=0,
                    review_output=[str(outside_output)],
                )
            )
        late_review_token = dict(review_near_envelope)
        late_review_token["event_id"] = "phase:late-review-token"
        late_review_token["input_tokens"] = 1
        late_review_token["cached_input_tokens"] = 1
        with central_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(late_review_token) + "\n")
        def end_overlay_state(state: Path, result: str) -> int:
            with contextlib.redirect_stdout(io.StringIO()):
                return pipeline.command_phase_end(
                    SimpleNamespace(
                        state=str(state),
                        phase_log=str(phase_log),
                        result=result,
                        manifest_hash="",
                        usage_file=None,
                        input_tokens=100,
                        cached_input_tokens=100,
                        output_tokens=0,
                        reasoning_tokens=0,
                        review_output=[str(review_output)],
                    )
                )

        results = ["blocked", "abandoned", "completed", "completed"]
        self.assertEqual(
            end_overlay_state(states[0], results[0]),
            2,
        )
        self.write_json(
            review_output,
            {
                "verdict": "pass",
                "evidence": "tampered after the first wrapper",
            },
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "tampered",
        ):
            end_overlay_state(states[1], results[1])
        self.write_json(
            review_output,
            {
                "verdict": "revise",
                "evidence": "mandatory independent animatic review",
            },
        )
        for state, result in zip(states[1:], results[1:]):
            self.assertEqual(
                end_overlay_state(state, result),
                2,
            )
        ledger = pipeline.load_json(reservation_path)
        overlay_reservations = [
            row
            for row in ledger["reservations"].values()
            if row.get("raw_budget_replan_hash")
        ]
        self.assertEqual(len(overlay_reservations), 1)
        self.assertEqual(
            overlay_reservations[0]["actual"][
                "raw_input_plus_output_tokens"
            ],
            100,
        )
        self.assertEqual(
            ledger["raw_budget_replans"]["mandatory-review-a"][
                "status"
            ],
            "consumed",
        )
        overlay_status = pipeline.raw_budget_replan_status(ledger)
        self.assertEqual(
            overlay_status["actual_raw_tokens"],
            100,
        )
        output_sha = pipeline.artifact_snapshot(
            review_output,
            self.root,
        )["sha256"]
        self.assertTrue(
            all(
                pipeline.load_json(state)["review_outputs"][0][
                    "sha256"
                ]
                == output_sha
                for state in states
            )
        )
        self.assertTrue(
            all(
                row["review_outputs"][0]["sha256"] == output_sha
                for row in pipeline.event_rows(phase_log)
            )
        )
        original_status = pipeline.efficiency_status_from_rows(
            efficiency,
            pipeline.event_rows(central_log),
            reservation_ledger=ledger,
        )
        self.assertIn(
            "raw_input_plus_output_tokens",
            original_status["token_status"]["exceeded"],
        )
        close_evaluation = (
            pipeline.episode_efficiency_close_evaluation(
                efficiency,
                pipeline.event_rows(central_log),
                set(scenes),
                {
                    "missing_phase_pairs_by_scene": {},
                    "false_passes": 0,
                },
                {
                    "scene_rate": 0.0,
                    "scenes": [],
                    "scene_count": 0,
                },
                [],
            )
        )
        self.assertIn(
            "EPISODE_TOKEN_BUDGET_EXCEEDED",
            close_evaluation["errors"],
        )
        self.assertFalse(close_evaluation["compliant"])
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "already exists|already authorized",
        ):
            authorize("mandatory-review-a")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "fourth",
        ):
            authorize("mandatory-review-d")
        self.assertEqual(
            pipeline.load_json(self.efficiency_contract)[
                "contract_hash"
            ],
            original_efficiency_hash,
        )
        self.assertEqual(
            pipeline.load_json(batch_path)["batch_hash"],
            original_batch_hash,
        )

    def test_animatic_repair_binds_open_issue_and_completion_artifacts(
        self,
    ) -> None:
        scene_slug = "g001_animatic_repair"
        batch_path = (
            self.episode
            / "review"
            / "v2"
            / "batch_a"
            / "production_batch.json"
        )
        batch = {
            "schema": "lecture-animation-production-batch-v2",
            "batch_id": "batch_a",
            "episode": pipeline.relative_or_absolute(
                self.episode,
                self.root,
            ),
            "scenes": [scene_slug],
        }
        batch["batch_hash"] = pipeline.object_hash(batch)
        self.write_json(batch_path, batch)
        issue_path = (
            self.episode
            / "review"
            / "issues"
            / "animatic-causality.json"
        )
        issue = {
            "schema": "lecture-animation-review-issue-v1",
            "issue_id": "animatic-causality",
            "scene_slug": scene_slug,
            "source": "independent_review",
            "severity": "critical",
            "verdict": "revise",
            "status": "open",
        }
        self.write_json(issue_path, issue)
        state_path = (
            self.episode
            / "review"
            / "evolution"
            / "animatic-repair-active.json"
        )
        phase_log = (
            self.episode
            / "review"
            / "evolution"
            / "animatic-repair.jsonl"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_phase_start(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        efficiency_contract=str(
                            self.efficiency_contract
                        ),
                        production_batch=str(batch_path),
                        run_id="animatic-repair-v02",
                        scene_slug=scene_slug,
                        phase="repair",
                        phase_purpose="animatic_repair",
                        actor_model="test-author",
                        actor_role="animation_author",
                        reasoning_effort="high",
                        active_seconds_allocation=60,
                        raw_token_allocation=100,
                        uncached_input_token_allocation=50,
                        output_token_allocation=20,
                        reasoning_token_allocation=10,
                        phase_instance_id=None,
                        shared_work_key=None,
                        prompt_bytes=0,
                        artifact_input_bytes=0,
                        files_read=1,
                        usage_file=None,
                        animatic_issue=[str(issue_path)],
                        previous_review=None,
                        repair_contract=None,
                        repair_execution_mode="same_author",
                        repair_actor_agent_id="author-a",
                        planned_verifier_agent_id="reviewer-b",
                        handoff_count=1,
                        state=str(state_path),
                    )
                ),
                0,
            )
        state = pipeline.load_json(state_path)
        self.assertTrue(state["animatic_repair"])
        self.assertEqual(
            state["animatic_repair_issue_ids"],
            ["animatic-causality"],
        )

        animatic = self.episode / "exports" / "animatic-v02.mp4"
        animatic.parent.mkdir(parents=True)
        animatic.write_bytes(b"animatic-v02")
        self_review = (
            self.episode
            / "review"
            / "audits"
            / scene_slug
            / "animatic-v02-self-review.md"
        )
        self_review.parent.mkdir(parents=True)
        self_review.write_text(
            "The repaired causal transform is visible frame by frame.\n",
            encoding="utf-8",
        )
        self.assertEqual(
                pipeline.command_phase_end(
                    SimpleNamespace(
                        state=str(state_path),
                        phase_log=str(phase_log),
                        result="completed",
                        manifest_hash="",
                        usage_file=None,
                        input_tokens=0,
                        cached_input_tokens=0,
                        output_tokens=0,
                        reasoning_tokens=0,
                        animatic_output=str(animatic),
                        animatic_self_review=str(self_review),
                    )
                ),
                0,
            )
        event = pipeline.event_rows(phase_log)[0]
        self.assertEqual(
            event["animatic_repair_issue_ids"],
            ["animatic-causality"],
        )
        self.assertEqual(
            event["animatic_output"]["sha256"],
            pipeline.artifact_snapshot(
                animatic,
                self.root,
            )["sha256"],
        )
        self.assertEqual(
            event["animatic_self_review"]["sha256"],
            pipeline.artifact_snapshot(
                self_review,
                self.root,
            )["sha256"],
        )

    def test_animatic_repair_budget_continuation_is_exact_outer_only_and_consumed(
        self,
    ) -> None:
        efficiency = pipeline.load_json(self.efficiency_contract)
        reservation_path = (
            pipeline.episode_efficiency_reservation_ledger(efficiency)
        )
        self.write_json(
            reservation_path,
            pipeline.empty_efficiency_reservation_ledger(efficiency),
        )
        central_log = pipeline.episode_efficiency_central_log(
            efficiency
        )
        central_log.parent.mkdir(parents=True, exist_ok=True)
        original_failure = {
            "schema": "lecture-animation-phase-event-v2",
            "event_id": "phase:raw-output-already-failed",
            "run_id": "historical-overrun",
            "scene_slug": "g000_historical",
            "phase": "authoring",
            "started_at": "2026-07-30T00:00:00+00:00",
            "ended_at": "2026-07-30T00:01:00+00:00",
            "duration_seconds": 60,
            # Episode 8 totals immediately before the honestly settled
            # batch-B repair.  Together with repair_envelope_failure below,
            # these reproduce the real pre-B ledger rather than a synthetic
            # single-dimension overrun.
            "input_tokens": 66_743_275,
            "cached_input_tokens": 65_238_152,
            "output_tokens": 292_441,
            "reasoning_tokens": 55_279,
            "token_observed": True,
            "result": "completed",
        }
        repair_envelope_failure = {
            "schema": "lecture-animation-phase-event-v2",
            "event_id": "phase:repair-envelope-already-failed",
            "run_id": "historical-repair-overrun",
            "scene_slug": "g000_historical_repair",
            "phase": "repair",
            "phase_purpose": "animatic_repair",
            "started_at": "2026-07-30T00:02:00+00:00",
            "ended_at": "2026-07-30T00:03:00+00:00",
            "duration_seconds": 60,
            "input_tokens": 4_000_001,
            "cached_input_tokens": 3_840_000,
            "output_tokens": 24_001,
            "reasoning_tokens": 8_001,
            "token_observed": True,
            "result": "completed",
        }
        central_log.write_text(
            "\n".join(
                json.dumps(row)
                for row in (
                    original_failure,
                    repair_envelope_failure,
                )
            )
            + "\n",
            encoding="utf-8",
        )
        supervisor_path = (
            self.episode / "review" / "v3" / "supervisor.json"
        )
        supervisor = {
            "schema": "lecture-animation-supervisor-session-v2",
            "session_id": "supervisor:ep8-repair-v03",
            "supervisor_agent_id": "/root",
            "closed_at": None,
            "assignments": {
                "/root/ep8_repair_v03_batch_b": {
                    "state": "active",
                    "role": "production_author",
                    "task_key": "batch_b",
                    "scope": "repair G006 and G008 animatics",
                    "model": "test-author",
                },
                "/root/ep8_repair_v03_batch_c": {
                    "state": "active",
                    "role": "production_author",
                    "task_key": "batch_c",
                    "scope": "repair G012 animatic",
                    "model": "test-author",
                },
            },
        }
        supervisor["session_hash"] = pipeline.object_hash(supervisor)
        self.write_json(supervisor_path, supervisor)
        batch_specs = {
            "batch_b": {
                "author": "/root/ep8_repair_v03_batch_b",
                "verifier": "/root/ep8_repair_v03_verifier_b",
                "batch_scenes": [
                    "g005_constant_function_calibration",
                    "g006_conjugate_path_dependence",
                    "g007_primitive_and_path_independence",
                    "g008_cauchy_theorem_local_rectangle",
                ],
                "scenes": [
                    "g006_conjugate_path_dependence",
                    "g008_cauchy_theorem_local_rectangle",
                ],
                "output_allowance": 16_000,
            },
            "batch_c": {
                "author": "/root/ep8_repair_v03_batch_c",
                "verifier": "/root/ep8_review_batch_c",
                "batch_scenes": [
                    "g009_mosaic_global_cancellation",
                    "g010_contour_deformation",
                    "g011_one_over_z_arrow_alignment",
                    "g012_singularity_winding_synthesis",
                ],
                "scenes": [
                    "g012_singularity_winding_synthesis",
                ],
                "output_allowance": 8_000,
            },
        }
        batch_paths: dict[str, Path] = {}
        issue_paths: dict[str, Path] = {}
        extra_issue_paths: dict[str, list[Path]] = {}
        output_roots: dict[str, Path] = {}
        for batch_id, spec in batch_specs.items():
            batch_path = (
                self.episode
                / "review"
                / "v3"
                / batch_id
                / "production_batch_repair_v03.json"
            )
            batch = {
                "schema": "lecture-animation-production-batch-v2",
                "efficiency_contract_version": 2,
                "episode_efficiency_contract_hash": efficiency[
                    "contract_hash"
                ],
                "batch_id": batch_id,
                "episode": pipeline.relative_or_absolute(
                    self.episode,
                    self.root,
                ),
                "scenes": spec["batch_scenes"],
                "author_id": spec["author"],
            }
            batch["batch_hash"] = pipeline.object_hash(batch)
            self.write_json(batch_path, batch)
            batch_paths[batch_id] = batch_path
            for scene in spec["scenes"]:
                issue_path = (
                    self.episode
                    / "review"
                    / "issues"
                    / f"{scene}-animatic-v02.json"
                )
                issue = {
                    "schema": "lecture-animation-review-issue-v1",
                    "id": f"{scene}-animatic-v02",
                    "scene": scene,
                    "source": "independent_review",
                    "severity": "critical",
                    "status": "open",
                }
                self.write_json(issue_path, issue)
                issue_paths[scene] = issue_path
                output_root = (
                    self.episode
                    / "review"
                    / "v3"
                    / batch_id
                    / scene
                    / "repair_v03"
                )
                output_roots[scene] = output_root
        second_g012_issue = (
            self.episode
            / "review"
            / "issues"
            / "g012-squashed-contour-animatic-v02.json"
        )
        self.write_json(
            second_g012_issue,
            {
                "schema": "lecture-animation-review-issue-v1",
                "id": "g012-squashed-contour-animatic-v02",
                "scene": "g012_singularity_winding_synthesis",
                "source": "independent_review",
                "severity": "critical",
                "status": "open",
            },
        )
        extra_issue_paths[
            "g012_singularity_winding_synthesis"
        ] = [second_g012_issue]

        def authorize(
            batch_id: str,
            *,
            output_allowance: int | None = None,
            key: str | None = None,
            scenes: list[str] | None = None,
        ) -> Path:
            spec = batch_specs[batch_id]
            continuation_path = (
                self.episode
                / "review"
                / "v3"
                / batch_id
                / f"{key or batch_id}-continuation.json"
            )
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.command_authorize_animatic_repair_budget_continuation(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        efficiency_contract=str(
                            self.efficiency_contract
                        ),
                        production_batch=str(batch_paths[batch_id]),
                        supervisor_session=str(supervisor_path),
                        authorizing_supervisor_agent_id="/root",
                        author_agent_id=spec["author"],
                        planned_verifier_agent_id=spec["verifier"],
                        scenes=",".join(
                            spec["scenes"] if scenes is None else scenes
                        ),
                        shared_work_key=key or f"ep8:{batch_id}:repair-v03",
                        animatic_issue=[
                            str(issue_paths[scene])
                            for scene in spec["scenes"]
                        ]
                        + [
                            str(path)
                            for scene in spec["scenes"]
                            for path in extra_issue_paths.get(scene, [])
                        ],
                        allowed_output_root=[
                            f"{scene}={output_roots[scene]}"
                            for scene in spec["scenes"]
                        ],
                        raw_token_allowance=1_500_000,
                        output_token_allowance=(
                            spec["output_allowance"]
                            if output_allowance is None
                            else output_allowance
                        ),
                        expires_hours=6.0,
                        output=str(continuation_path),
                    )
                )
            return continuation_path

        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "output allowance",
        ):
            authorize(
                "batch_b",
                output_allowance=16_001,
                key="too-much-output",
            )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "fixed Episode 8 repair scope",
        ):
            authorize(
                "batch_b",
                key="missing-scope-scene",
                scenes=["g006_conjugate_path_dependence"],
            )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "fixed Episode 8 repair scope",
        ):
            authorize(
                "batch_c",
                key="extra-scope-scene",
                scenes=[
                    "g011_one_over_z_arrow_alignment",
                    "g012_singularity_winding_synthesis",
                ],
            )
        continuation_b = authorize("batch_b")
        continuation_c = authorize("batch_c")
        ledger = pipeline.load_json(reservation_path)
        continuation_rows = ledger[
            "animatic_repair_budget_continuations"
        ]
        self.assertEqual(len(continuation_rows), 2)
        self.assertEqual(
            sum(
                row["raw_allowance_tokens"]
                for row in continuation_rows.values()
            ),
            3_000_000,
        )
        self.assertEqual(
            sum(
                row["output_allowance_tokens"]
                for row in continuation_rows.values()
            ),
            24_000,
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "already authorized|third key",
        ):
            authorize("batch_c", key="third-key")
        extension_paths: dict[str, Path] = {}
        for batch_id, parent in (
            ("batch_b", continuation_b),
            ("batch_c", continuation_c),
        ):
            extension_path = (
                self.episode
                / "review"
                / "v3"
                / batch_id
                / "animatic-repair-token-extension.json"
            )
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    pipeline.command_authorize_animatic_repair_token_extension(
                        SimpleNamespace(
                            repo_root=str(self.root),
                            episode=str(self.episode),
                            parent_continuation=str(parent),
                            output=str(extension_path),
                        )
                    ),
                    0,
                )
            extension_paths[batch_id] = extension_path

        def start(
            batch_id: str,
            scene: str,
            *,
            actor: str | None = None,
            issue_path: Path | None = None,
            use_extension: bool = True,
            allocation_overrides: dict[str, int] | None = None,
            active_seconds: float = 60,
            state_suffix: str = "",
            continuation_override: Path | None = None,
            extension_override: Path | None = None,
            batch_override: Path | None = None,
            recovery: Path | None = None,
            shared_key_override: str | None = None,
        ) -> Path:
            spec = batch_specs[batch_id]
            allocations = {
                "raw_token_allocation": 1_500_000,
                "uncached_input_token_allocation": 60_000,
                "output_token_allocation": spec["output_allowance"],
                "reasoning_token_allocation": 4_000,
            }
            allocations.update(allocation_overrides or {})
            state_root = (
                batch_override.parent / "phase-states"
                if batch_override is not None
                else output_roots[scene]
                if batch_id == "batch_c"
                else self.episode / "review" / "v3" / batch_id
            )
            state_path = (
                state_root
                / f"{scene}{state_suffix}-repair-active.json"
            )
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.command_phase_start(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        efficiency_contract=str(
                            self.efficiency_contract
                        ),
                        production_batch=str(
                            batch_override or batch_paths[batch_id]
                        ),
                        raw_budget_replan=None,
                        animatic_repair_budget_continuation=str(
                            continuation_override
                            or (
                                continuation_b
                                if batch_id == "batch_b"
                                else continuation_c
                            )
                        ),
                        animatic_repair_token_extension=(
                            str(
                                extension_override
                                or extension_paths[batch_id]
                            )
                            if use_extension
                            else None
                        ),
                        animatic_repair_recovery=(
                            str(recovery) if recovery else None
                        ),
                        actor_agent_id=None,
                        run_id=f"{batch_id}-{scene}-repair-v03",
                        scene_slug=scene,
                        phase="repair",
                        phase_purpose="animatic_repair",
                        actor_model="test-author",
                        actor_role="production_author",
                        reasoning_effort="high",
                        active_seconds_allocation=active_seconds,
                        **allocations,
                        phase_instance_id=None,
                        shared_work_key=(
                            shared_key_override
                            or f"ep8:{batch_id}:repair-v03"
                        ),
                        prompt_bytes=0,
                        artifact_input_bytes=0,
                        files_read=1,
                        usage_file=None,
                        animatic_issue=[
                            str(issue_path or issue_paths[scene])
                        ]
                        + (
                            []
                            if issue_path is not None
                            else [
                                str(path)
                                for path in extra_issue_paths.get(
                                    scene,
                                    [],
                                )
                            ]
                        ),
                        previous_review=None,
                        repair_contract=None,
                        repair_execution_mode="same_author",
                        repair_actor_agent_id=actor or spec["author"],
                        planned_verifier_agent_id=spec["verifier"],
                        handoff_count=1,
                        state=str(state_path),
                    )
                )
            return state_path

        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "repair actor",
        ):
            start(
                "batch_b",
                batch_specs["batch_b"]["scenes"][0],
                actor="wrong-author",
                state_suffix="-wrong-author",
            )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "repair token envelope",
        ):
            start(
                "batch_b",
                batch_specs["batch_b"]["scenes"][0],
                use_extension=False,
                state_suffix="-no-companion",
            )
        for field, value in {
            "raw_token_allocation": 1_500_001,
            "uncached_input_token_allocation": 60_001,
            "output_token_allocation": 16_001,
            "reasoning_token_allocation": 4_001,
        }.items():
            with self.assertRaisesRegex(
                pipeline.PipelineError,
                "hard limit|key cap|local token extension",
            ):
                start(
                    "batch_b",
                    batch_specs["batch_b"]["scenes"][0],
                    allocation_overrides={field: value},
                    state_suffix=f"-over-{field}",
                )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "600-second",
        ):
            start(
                "batch_b",
                batch_specs["batch_b"]["scenes"][0],
                active_seconds=1500,
                state_suffix="-active-not-extended",
            )
        issue_g006 = pipeline.load_json(
            issue_paths["g006_conjugate_path_dependence"]
        )
        issue_g006["status"] = "closed"
        self.write_json(
            issue_paths["g006_conjugate_path_dependence"],
            issue_g006,
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "stale|closed",
        ):
            start(
                "batch_b",
                "g006_conjugate_path_dependence",
                state_suffix="-closed-issue",
            )
        issue_g006["status"] = "open"
        self.write_json(
            issue_paths["g006_conjugate_path_dependence"],
            issue_g006,
        )
        original_continuation_b = pipeline.load_json(continuation_b)
        tampered_continuation_b = dict(original_continuation_b)
        tampered_continuation_b["future_output_allowance_tokens"] = 16_001
        self.write_json(continuation_b, tampered_continuation_b)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "hash is invalid",
        ):
            start(
                "batch_b",
                "g006_conjugate_path_dependence",
                state_suffix="-tampered",
            )
        self.write_json(continuation_b, original_continuation_b)
        original_extension_b = pipeline.load_json(
            extension_paths["batch_b"]
        )
        tampered_extension_b = dict(original_extension_b)
        tampered_extension_b["local_token_allowance"] = {
            **tampered_extension_b["local_token_allowance"],
            "reasoning_tokens": 4_001,
        }
        self.write_json(
            extension_paths["batch_b"],
            tampered_extension_b,
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "hash is invalid",
        ):
            start(
                "batch_b",
                "g006_conjugate_path_dependence",
                state_suffix="-tampered-extension",
            )
        self.write_json(
            extension_paths["batch_b"],
            original_extension_b,
        )

        states_b = [
            start("batch_b", scene)
            for scene in batch_specs["batch_b"]["scenes"]
        ]
        state_c = start(
            "batch_c",
            "g012_singularity_winding_synthesis",
        )
        ledger = pipeline.load_json(reservation_path)
        continuation_reservations = [
            row
            for row in ledger["reservations"].values()
            if row.get(
                "animatic_repair_budget_continuation_hash"
            )
        ]
        self.assertEqual(len(continuation_reservations), 2)
        self.assertEqual(
            len(
                continuation_reservations[0].get(
                    "wrapper_state_paths",
                    {},
                )
            )
            + len(
                continuation_reservations[1].get(
                    "wrapper_state_paths",
                    {},
                )
            ),
            3,
        )
        phase_log = (
            self.episode
            / "review"
            / "evolution"
            / "animatic-repair-continuation.jsonl"
        )

        def artifacts(scene: str) -> tuple[Path, Path]:
            root = output_roots[scene]
            root.mkdir(parents=True, exist_ok=True)
            animatic = root / "animatic-repair-v03.mp4"
            animatic.write_bytes(b"repair-v03")
            self_review = root / "animatic-repair-v03-self-review.md"
            self_review.write_text(
                "The bounded repair remains pending independent review.\n",
                encoding="utf-8",
            )
            return animatic, self_review

        def end(
            state: Path,
            result: str,
            animatic: Path | None,
            self_review: Path | None,
            *,
            input_tokens: int = 100,
            cached_input_tokens: int = 100,
            output_tokens: int = 10,
            reasoning_tokens: int = 0,
        ) -> int:
            with contextlib.redirect_stdout(io.StringIO()):
                return pipeline.command_phase_end(
                    SimpleNamespace(
                        state=str(state),
                        phase_log=str(phase_log),
                        result=result,
                        manifest_hash="",
                        usage_file=None,
                        input_tokens=input_tokens,
                        cached_input_tokens=cached_input_tokens,
                        output_tokens=output_tokens,
                        reasoning_tokens=reasoning_tokens,
                        animatic_output=(
                            str(animatic) if animatic else None
                        ),
                        animatic_self_review=(
                            str(self_review) if self_review else None
                        ),
                        review_output=[],
                    )
                )

        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "animatic-output",
        ):
            end(states_b[0], "blocked", None, None)
        outside = self.root / "outside"
        outside.mkdir()
        outside_animatic = outside / "animatic.mp4"
        outside_animatic.write_bytes(b"outside")
        inside_self_review = artifacts(
            "g006_conjugate_path_dependence"
        )[1]
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "outside the sealed scene output root",
        ):
            end(
                states_b[0],
                "blocked",
                outside_animatic,
                inside_self_review,
            )
        artifacts_b = [
            artifacts(scene)
            for scene in batch_specs["batch_b"]["scenes"]
        ]
        real_batch_b_actual = {
            "input_tokens": 12_005_157,
            "cached_input_tokens": 11_735_296,
            "output_tokens": 44_620,
            "reasoning_tokens": 11_860,
        }
        self.assertEqual(
            end(
                states_b[0],
                "blocked",
                *artifacts_b[0],
                **real_batch_b_actual,
            ),
            2,
        )
        completed_b0 = pipeline.load_json(states_b[0])
        self.assertTrue(
            completed_b0["phase_envelope_status_at_end"]["exceeded"]
        )
        self.assertFalse(
            completed_b0["phase_envelope_completion_exceeded"]
        )
        self.assertTrue(
            completed_b0[
                "animatic_repair_token_extension_status_at_end"
            ]["exceeded"]
        )
        self.assertIn(
            "PHASE_BUDGET_ENVELOPE_EXCEEDED",
            completed_b0["efficiency_status_at_end"]["alerts"],
        )
        ledger = pipeline.load_json(reservation_path)
        row_b = ledger[
            "animatic_repair_budget_continuations"
        ]["ep8:batch_b:repair-v03"]
        self.assertEqual(row_b["status"], "reserved")
        extension_row_b = ledger[
            "animatic_repair_token_extensions"
        ]["ep8:batch_b:repair-v03"]
        self.assertEqual(extension_row_b["status"], "reserved")
        self.assertEqual(
            extension_row_b["reservation_id"],
            row_b["reservation_id"],
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "not active",
        ):
            end(states_b[0], "blocked", *artifacts_b[0])
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "same actual token usage",
        ):
            end(
                states_b[1],
                "completed",
                *artifacts_b[1],
                input_tokens=12_005_158,
                cached_input_tokens=11_735_296,
                output_tokens=44_620,
                reasoning_tokens=11_860,
            )
        self.assertEqual(
            end(
                states_b[1],
                "completed",
                *artifacts_b[1],
                **real_batch_b_actual,
            ),
            2,
        )
        ledger_after_b = pipeline.load_json(reservation_path)
        settled_b_row = ledger_after_b[
            "animatic_repair_budget_continuations"
        ]["ep8:batch_b:repair-v03"]
        settled_b_reservation = ledger_after_b["reservations"][
            settled_b_row["reservation_id"]
        ]
        self.assertEqual(settled_b_reservation["status"], "released")
        self.assertEqual(
            settled_b_reservation["actual"],
            {
                "raw_input_plus_output_tokens": 12_049_777,
                "uncached_input_tokens": 269_861,
                "output_tokens": 44_620,
                "reasoning_tokens": 11_860,
            },
        )
        active_c_row = ledger_after_b[
            "animatic_repair_budget_continuations"
        ]["ep8:batch_c:repair-v03"]
        active_c_reservation = ledger_after_b["reservations"][
            active_c_row["reservation_id"]
        ]
        self.assertIsNone(active_c_reservation.get("actual"))

        # Match Episode 8's already-exhausted 4,912-second repair envelope.
        # The two B wrappers retain one accounting identity and therefore one
        # 4,852-second shared interval, added to the 60-second historical
        # repair interval above.
        central_rows = [
            json.loads(line)
            for line in central_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for row in central_rows:
            if row.get("accounting_identity") == completed_b0.get(
                "accounting_identity"
            ):
                row["started_at"] = "2026-07-30T00:04:00+00:00"
                row["ended_at"] = "2026-07-30T01:24:52+00:00"
                row["duration_seconds"] = 4_852
        central_log.write_text(
            "\n".join(json.dumps(row) for row in central_rows) + "\n",
            encoding="utf-8",
        )
        supervisor = pipeline.load_json(supervisor_path)
        supervisor["assignments"][
            "/root/ep8_repair_v03_batch_c"
        ]["state"] = "blocked"
        supervisor.pop("session_hash", None)
        supervisor["session_hash"] = pipeline.object_hash(supervisor)
        self.write_json(supervisor_path, supervisor)
        health_paths: list[Path] = []
        for sequence in (1, 2, 3):
            health_path = (
                self.episode
                / "review"
                / "v3"
                / "batch_c"
                / f"health-{sequence}.json"
            )
            self.write_json(
                health_path,
                {
                    "schema_version": (
                        "lecture-animation-worker-health-check-evidence-v1"
                    ),
                    "sequence": sequence,
                    "agent_id": "/root/ep8_repair_v03_batch_c",
                    "result": "no_response",
                    "requested_action": f"health probe {sequence}",
                    "artifact_progress": False,
                    "recorded_by": "/root",
                },
            )
            health_paths.append(health_path)
        feedback_path = (
            self.episode
            / "review"
            / "agent-feedback"
            / "g012-unresponsive.md"
        )
        feedback_path.parent.mkdir(parents=True, exist_ok=True)
        feedback_path.write_text(
            "Three probes found no response or artifact progress.\n",
            encoding="utf-8",
        )
        accepted_issue_path = (
            self.episode
            / "review"
            / "issues"
            / "g012-unresponsive.json"
        )
        self.write_json(
            accepted_issue_path,
            {
                "schema": "lecture-animation-review-issue-v1",
                "issue_id": "g012-unresponsive",
                "source": "accepted_agent_feedback",
                "scene_slug": "g012_singularity_winding_synthesis",
                "status": "open",
                "pattern_key": (
                    "repair_author_identity_unresponsive_without_artifact_progress"
                ),
            },
        )
        abandonment_path = (
            self.episode
            / "review"
            / "v3"
            / "batch_c"
            / "g012-abandonment.json"
        )
        abandon_args = SimpleNamespace(
            repo_root=str(self.root),
            state=str(state_c),
            blocked_supervisor=str(supervisor_path),
            health_check=[str(path) for path in health_paths],
            accepted_feedback=str(feedback_path),
            accepted_issue=str(accepted_issue_path),
            output=str(abandonment_path),
        )
        self.write_json(
            output_roots["g012_singularity_winding_synthesis"]
            / "rollout_totals_start.json",
            {"input_tokens": 0},
        )
        inside_health = (
            output_roots["g012_singularity_winding_synthesis"]
            / "abandonment-health-1.json"
        )
        self.write_json(
            inside_health,
            pipeline.load_json(health_paths[0]),
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "governance evidence must remain outside",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair(
                SimpleNamespace(
                    **{
                        **vars(abandon_args),
                        "health_check": [
                            str(inside_health),
                            str(health_paths[1]),
                            str(health_paths[2]),
                        ],
                    }
                )
            )
        inside_health.unlink()
        author_self_review = (
            output_roots["g012_singularity_winding_synthesis"]
            / "author_self_review.md"
        )
        author_self_review.write_text(
            "Claimed author progress.\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "attributable production progress",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair(
                abandon_args
            )
        author_self_review.unlink()
        old_progress = (
            output_roots["g012_singularity_winding_synthesis"]
            / "old-output.mp4"
        )
        old_progress.parent.mkdir(parents=True, exist_ok=True)
        old_progress.write_bytes(b"attributable-progress")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "attributable production progress",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair(
                abandon_args
            )
        old_progress.unlink()
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=2
        ) as executor:
            abandonment_results = list(
                executor.map(
                    lambda _: (
                        pipeline.command_abandon_unresponsive_animatic_repair(
                            abandon_args
                        )
                    ),
                    range(2),
                )
            )
        self.assertEqual(abandonment_results, [0, 0])
        abandonment = pipeline.load_json(abandonment_path)
        self.assertFalse(abandonment["token_observed"])
        self.assertIsNone(abandonment["actual"])
        self.assertFalse(abandonment["refund"])
        self.assertEqual(
            pipeline.event_rows(central_log)[-1]["token_source_kind"],
            "unresponsive_worker_unobservable",
        )
        alternate_health = health_paths[0].with_name(
            "health-1-alternate.json"
        )
        self.write_json(
            alternate_health,
            pipeline.load_json(health_paths[0]),
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "complete identical commit",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair(
                SimpleNamespace(
                    **{
                        **vars(abandon_args),
                        "health_check": [
                            str(alternate_health),
                            str(health_paths[1]),
                            str(health_paths[2]),
                        ],
                    }
                )
            )
        feedback_original = feedback_path.read_text(encoding="utf-8")
        feedback_path.write_text(
            feedback_original + "mismatched retry\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "complete identical commit",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair(
                abandon_args
            )
        feedback_path.write_text(feedback_original, encoding="utf-8")
        central_log_original = central_log.read_text(encoding="utf-8")
        central_lines = central_log_original.splitlines()
        central_log.write_text(
            "\n".join(central_lines[:-1]) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "exactly one committed abandonment event",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair(
                abandon_args
            )
        central_log.write_text(
            central_log_original,
            encoding="utf-8",
        )
        ledger_committed = pipeline.load_json(reservation_path)
        ledger_partial = json.loads(json.dumps(ledger_committed))
        ledger_partial["animatic_repair_budget_continuations"][
            "ep8:batch_c:repair-v03"
        ]["status"] = "reserved"
        ledger_partial.pop("ledger_hash", None)
        ledger_partial["ledger_hash"] = pipeline.object_hash(
            ledger_partial
        )
        self.write_json(reservation_path, ledger_partial)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "parent consumption write",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair(
                abandon_args
            )
        self.write_json(reservation_path, ledger_committed)
        state_committed = pipeline.load_json(state_c)
        state_partial = dict(state_committed)
        state_partial["status"] = "active"
        state_partial.pop("timer_hash", None)
        state_partial["timer_hash"] = pipeline.object_hash(state_partial)
        self.write_json(state_c, state_partial)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "sealed state is incomplete",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair(
                abandon_args
            )
        self.write_json(state_c, state_committed)
        ledger = pipeline.load_json(reservation_path)
        old_c_row = ledger[
            "animatic_repair_budget_continuations"
        ]["ep8:batch_c:repair-v03"]
        old_c_reservation = ledger["reservations"][
            old_c_row["reservation_id"]
        ]
        self.assertEqual(old_c_reservation["status"], "released")
        self.assertIsNone(old_c_reservation["actual"])
        self.assertFalse(old_c_reservation["token_observed"])
        self.assertTrue(
            all(
                row["status"] == "consumed"
                for row in ledger[
                    "animatic_repair_budget_continuations"
                ].values()
            )
        )
        self.assertTrue(
            all(
                row["status"] == "consumed"
                for row in ledger[
                    "animatic_repair_token_extensions"
                ].values()
            )
        )
        self.assertEqual(
            len(
                [
                    row
                    for row in ledger["reservations"].values()
                    if row.get(
                        "animatic_repair_token_extension_hash"
                    )
                ]
            ),
            2,
        )
        self.assertTrue(
            all(
                issue.get("status") == "open"
                for issue in (
                    pipeline.load_json(path)
                    for path in issue_paths.values()
                )
            )
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "consumed|already has a wrapper|active supervisor assignment",
        ):
            start(
                "batch_c",
                "g012_singularity_winding_synthesis",
                state_suffix="-no-refund",
            )
        status = pipeline.efficiency_status_from_rows(
            efficiency,
            pipeline.event_rows(central_log),
            reservation_ledger=ledger,
        )
        self.assertEqual(
            status["token_status"]["observed"],
            {
                "raw_input_plus_output_tokens": 83_109_495,
                "uncached_input_tokens": 1_934_985,
                "output_tokens": 361_062,
                "reasoning_tokens": 75_140,
            },
        )
        accounted_rows = pipeline.phase_rows_with_accounting(
            pipeline.event_rows(central_log),
            contract=efficiency,
            reservation_ledger=ledger,
        )
        self.assertGreaterEqual(
            pipeline.phase_bucket_active_seconds(
                accounted_rows,
                "repair",
            ),
            4_912,
        )
        self.assertIn(
            "raw_input_plus_output_tokens",
            status["token_status"]["exceeded"],
        )
        self.assertIn(
            "output_tokens",
            status["token_status"]["exceeded"],
        )
        close_evaluation = (
            pipeline.episode_efficiency_close_evaluation(
                efficiency,
                pipeline.event_rows(central_log),
                set(
                    batch_specs["batch_b"]["scenes"]
                    + batch_specs["batch_c"]["scenes"]
                ),
                {
                    "missing_phase_pairs_by_scene": {},
                    "false_passes": 0,
                },
                {
                    "scene_rate": 0.0,
                    "scenes": [],
                    "scene_count": 0,
                },
                [],
            )
        )
        self.assertIn(
            "EPISODE_TOKEN_BUDGET_EXCEEDED",
            close_evaluation["errors"],
        )
        self.assertFalse(close_evaluation["compliant"])

        replacement_root = (
            self.episode
            / "review"
            / "v3"
            / "batch_c_replacement"
            / "g012"
        )
        replacement_supervisor = (
            self.episode
            / "review"
            / "v3"
            / "batch_c_replacement"
            / "supervisor.json"
        )
        replacement_batch = replacement_supervisor.with_name(
            "production-batch.json"
        )
        replacement_continuation = replacement_supervisor.with_name(
            "continuation.json"
        )
        replacement_extension = replacement_supervisor.with_name(
            "extension.json"
        )
        replacement_args = SimpleNamespace(
            repo_root=str(self.root),
            episode=str(self.episode),
            abandonment=str(abandonment_path),
            replacement_author="/root/ep8_g012_replacement_author",
            planned_verifier="/root/ep8_review_batch_c",
            shared_work_key=(
                "ep8:g012-animatic-repair:replacement-01"
            ),
            allowed_output_root=str(replacement_root),
            supervisor_output=str(replacement_supervisor),
            production_batch_output=str(replacement_batch),
            continuation_output=str(replacement_continuation),
            extension_output=str(replacement_extension),
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "replacement author",
        ):
            pipeline.command_authorize_animatic_repair_replacement(
                SimpleNamespace(
                    **{
                        **vars(replacement_args),
                        "replacement_author": "/root/wrong",
                    }
                )
            )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "replacement verifier",
        ):
            pipeline.command_authorize_animatic_repair_replacement(
                SimpleNamespace(
                    **{
                        **vars(replacement_args),
                        "planned_verifier": "/root/wrong-verifier",
                    }
                )
            )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "shared-work-key",
        ):
            pipeline.command_authorize_animatic_repair_replacement(
                SimpleNamespace(
                    **{
                        **vars(replacement_args),
                        "shared_work_key": "replacement-02",
                    }
                )
            )
        replacement_root.mkdir(parents=True)
        preexisting_dir = replacement_root / "preexisting-directory"
        preexisting_dir.mkdir()
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "must not exist or must be an empty directory",
        ):
            pipeline.command_authorize_animatic_repair_replacement(
                replacement_args
            )
        preexisting_dir.rmdir()
        self.write_json(replacement_supervisor, {"partial": True})
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "output already exists",
        ):
            pipeline.command_authorize_animatic_repair_replacement(
                replacement_args
            )
        replacement_supervisor.unlink()
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=2
        ) as executor:
            replacement_results = list(
                executor.map(
                    lambda _: (
                        pipeline.command_authorize_animatic_repair_replacement(
                            replacement_args
                        )
                    ),
                    range(2),
                )
            )
        self.assertEqual(replacement_results, [0, 0])
        spent_abandonment = pipeline.load_json(abandonment_path)
        self.assertEqual(
            spent_abandonment["status"],
            "replacement_authorized",
        )
        ledger = pipeline.load_json(reservation_path)
        self.assertEqual(
            len(ledger["animatic_repair_budget_continuations"]),
            3,
        )
        self.assertEqual(
            ledger["animatic_repair_budget_continuations"][
                "ep8:g012-animatic-repair:replacement-01"
            ]["status"],
            "authorized",
        )
        changed_root = replacement_root.with_name("changed-root")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "command inputs",
        ):
            pipeline.command_authorize_animatic_repair_replacement(
                SimpleNamespace(
                    **{
                        **vars(replacement_args),
                        "allowed_output_root": str(changed_root),
                    }
                )
            )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "inside the exact episode",
        ):
            pipeline.command_authorize_animatic_repair_replacement(
                SimpleNamespace(
                    **{
                        **vars(replacement_args),
                        "episode": str(self.old_episode),
                    }
                )
            )
        ledger_spent = pipeline.load_json(reservation_path)
        ledger_before_recovery = json.loads(json.dumps(ledger_spent))
        del ledger_before_recovery[
            "animatic_repair_budget_continuations"
        ]["ep8:g012-animatic-repair:replacement-01"]
        del ledger_before_recovery[
            "animatic_repair_token_extensions"
        ]["ep8:g012-animatic-repair:replacement-01"]
        ledger_before_recovery[
            "animatic_repair_replacement_recoveries"
        ] = {}
        ledger_before_recovery["animatic_repair_abandonments"][
            "ep8:batch_c:repair-v03"
        ]["status"] = "consumed"
        ledger_before_recovery["animatic_repair_abandonments"][
            "ep8:batch_c:repair-v03"
        ]["receipt_hash"] = abandonment["receipt_hash"]
        ledger_before_recovery["animatic_repair_abandonments"][
            "ep8:batch_c:repair-v03"
        ].pop("replacement_shared_work_key", None)
        ledger_before_recovery.pop("ledger_hash", None)
        ledger_before_recovery["ledger_hash"] = pipeline.object_hash(
            ledger_before_recovery
        )
        self.write_json(reservation_path, ledger_before_recovery)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "continuation CAS row|recovery ledger CAS",
        ):
            pipeline.command_authorize_animatic_repair_replacement(
                replacement_args
            )
        self.write_json(reservation_path, ledger_spent)
        extension_saved = pipeline.load_json(replacement_extension)
        replacement_extension.unlink()
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "sealed outputs are missing",
        ):
            pipeline.command_authorize_animatic_repair_replacement(
                replacement_args
            )
        self.write_json(replacement_extension, extension_saved)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "spent|missing",
        ):
            pipeline.command_authorize_animatic_repair_replacement(
                SimpleNamespace(
                    **{
                        **vars(replacement_args),
                        "supervisor_output": str(
                            replacement_supervisor.with_name(
                                "second-supervisor.json"
                            )
                        ),
                    }
                )
            )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "requires --animatic-repair-recovery",
        ):
            start(
                "batch_c",
                "g012_singularity_winding_synthesis",
                actor="/root/ep8_g012_replacement_author",
                state_suffix="-replacement-missing-lineage",
                continuation_override=replacement_continuation,
                extension_override=replacement_extension,
                batch_override=replacement_batch,
                shared_key_override=(
                    "ep8:g012-animatic-repair:replacement-01"
                ),
            )
        for field, value in {
            "raw_token_allocation": 1_500_001,
            "uncached_input_token_allocation": 60_001,
            "output_token_allocation": 8_001,
            "reasoning_token_allocation": 4_001,
        }.items():
            with self.assertRaisesRegex(
                pipeline.PipelineError,
                "hard limit|key cap|local token extension",
            ):
                start(
                    "batch_c",
                    "g012_singularity_winding_synthesis",
                    actor="/root/ep8_g012_replacement_author",
                    state_suffix=f"-replacement-over-{field}",
                    continuation_override=replacement_continuation,
                    extension_override=replacement_extension,
                    batch_override=replacement_batch,
                    recovery=abandonment_path,
                    allocation_overrides={field: value},
                    active_seconds=600,
                    shared_key_override=(
                        "ep8:g012-animatic-repair:replacement-01"
                    ),
                )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "600-second",
        ):
            start(
                "batch_c",
                "g012_singularity_winding_synthesis",
                actor="/root/ep8_g012_replacement_author",
                state_suffix="-replacement-over-active",
                continuation_override=replacement_continuation,
                extension_override=replacement_extension,
                batch_override=replacement_batch,
                recovery=abandonment_path,
                active_seconds=1500,
                shared_key_override=(
                    "ep8:g012-animatic-repair:replacement-01"
                ),
            )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "shared-work-key",
        ):
            start(
                "batch_c",
                "g012_singularity_winding_synthesis",
                actor="/root/ep8_g012_replacement_author",
                state_suffix="-replacement-wrong-key",
                continuation_override=replacement_continuation,
                extension_override=replacement_extension,
                batch_override=replacement_batch,
                recovery=abandonment_path,
                active_seconds=600,
                shared_key_override="ep8:g012:not-recovery",
            )
        replacement_state = start(
            "batch_c",
            "g012_singularity_winding_synthesis",
            actor="/root/ep8_g012_replacement_author",
            state_suffix="-replacement",
            continuation_override=replacement_continuation,
            extension_override=replacement_extension,
            batch_override=replacement_batch,
            recovery=abandonment_path,
            active_seconds=600,
            shared_key_override=(
                "ep8:g012-animatic-repair:replacement-01"
            ),
        )
        replacement_state_record = pipeline.load_json(replacement_state)
        self.assertTrue(
            replacement_state_record[
                "animatic_repair_recovery_local_admission_applied"
            ]
        )
        self.assertEqual(
            replacement_state_record[
                "efficiency_status_at_start"
            ]["token_status"]["observed"],
            {
                "raw_input_plus_output_tokens": 83_109_495,
                "uncached_input_tokens": 1_934_985,
                "output_tokens": 361_062,
                "reasoning_tokens": 75_140,
            },
        )
        self.assertEqual(
            set(
                replacement_state_record[
                    "base_episode_reservation_overflow_at_start"
                ]
            ),
            {
                "raw_input_plus_output_tokens",
                "uncached_input_tokens",
                "output_tokens",
            },
        )
        self.assertEqual(
            set(
                replacement_state_record[
                    "base_phase_envelope_overflow_at_start"
                ]
            ),
            {
                "raw_input_plus_output_tokens",
                "uncached_input_tokens",
                "output_tokens",
                "reasoning_tokens",
            },
        )
        self.assertFalse(
            replacement_state_record[
                "base_stage_active_overflow_at_start"
            ]
        )
        self.assertTrue(
            replacement_state_record[
                "base_phase_active_overflow_at_start"
            ]
        )
        replacement_health_paths: list[Path] = []
        replacement_recovery_dir = (
            replacement_supervisor.parent / "recovery"
        )
        for sequence, result in (
            (1, "no_response"),
            (2, "no_response"),
            (3, "forced_interrupt_no_checkpoint"),
        ):
            health_path = (
                replacement_recovery_dir
                / f"health_check_{sequence:02d}.json"
            )
            health = {
                "schema_version": (
                    "lecture-animation-worker-health-check-evidence-v1"
                ),
                "sequence": sequence,
                "agent_id": "/root/ep8_g012_replacement_author",
                "result": result,
                "requested_action": f"replacement probe {sequence}",
                "artifact_progress": False,
                "recorded_by": "/root",
            }
            if sequence == 1:
                health["requested_at_approximate"] = (
                    "2026-07-30T03:46Z"
                )
            elif sequence == 2:
                health["requested_at"] = "2026-07-30T03:50:48Z"
            else:
                health["previous_status"] = "running"
                health["checkpoint_present"] = False
            self.write_json(health_path, health)
            replacement_health_paths.append(health_path)
        replacement_feedback = (
            self.episode
            / "review"
            / "agent-feedback"
            / "2026-07-30-g012-replacement-author-unresponsive.md"
        )
        replacement_feedback.parent.mkdir(parents=True, exist_ok=True)
        replacement_feedback.write_text(
            "Two no-response probes followed by a forced interrupt "
            "without a checkpoint.\n",
            encoding="utf-8",
        )
        replacement_issue = (
            self.episode
            / "review"
            / "issues"
            / (
                "agent_g012_replacement_identity_unresponsive_"
                "2026-07-30.json"
            )
        )
        self.write_json(
            replacement_issue,
            {
                "schema": "lecture-animation-review-issue-v1",
                "issue_id": (
                    "agent_g012_replacement_identity_unresponsive_"
                    "2026-07-30"
                ),
                "source": "accepted_agent_feedback",
                "origin_source": "supervisor_observation",
                "accepted_by": "/root",
                "scene_slug": "g012_singularity_winding_synthesis",
                "pattern_key": (
                    "replacement_repair_author_unresponsive_without_"
                    "artifact_progress"
                ),
                "must_check_in_future": True,
                "status": "open",
            },
        )
        replacement_abandonment = (
            replacement_recovery_dir
            / "replacement-01-abandonment.json"
        )
        replacement_abandon_args = SimpleNamespace(
            repo_root=str(self.root),
            state=str(replacement_state),
            supervisor=str(replacement_supervisor),
            health_check=[
                str(path) for path in replacement_health_paths
            ],
            accepted_feedback=str(replacement_feedback),
            accepted_issue=str(replacement_issue),
            output=str(replacement_abandonment),
        )
        replacement_root.mkdir(parents=True, exist_ok=True)
        claimed_progress = replacement_root / "claimed-progress.txt"
        claimed_progress.write_text("progress\n", encoding="utf-8")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "zero attributable author progress",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair_replacement(
                replacement_abandon_args
            )
        claimed_progress.unlink()
        allowed_rollout = (
            replacement_root / "rollout_totals_start.json"
        )
        self.write_json(allowed_rollout, {"input_tokens": 0})
        same_name_directory = replacement_root / "same-name-attack"
        same_name_directory.mkdir()
        same_name_file = (
            same_name_directory / replacement_state.name
        )
        same_name_file.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "non-control entry",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair_replacement(
                replacement_abandon_args
            )
        same_name_file.unlink()
        same_name_directory.rmdir()
        empty_subdirectory = replacement_root / "empty-subdirectory"
        empty_subdirectory.mkdir()
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "non-control entry",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair_replacement(
                replacement_abandon_args
            )
        empty_subdirectory.rmdir()
        hidden_file = replacement_root / ".hidden-progress"
        hidden_file.write_text("hidden\n", encoding="utf-8")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "non-control entry",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair_replacement(
                replacement_abandon_args
            )
        hidden_file.unlink()
        fake_appledouble = replacement_root / "._other-state.json"
        fake_appledouble.write_bytes(b"appledouble")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "non-control entry",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair_replacement(
                replacement_abandon_args
            )
        fake_appledouble.unlink()
        symlink_progress = replacement_root / "linked-progress"
        symlink_progress.symlink_to(replacement_health_paths[0])
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "non-control entry",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair_replacement(
                replacement_abandon_args
            )
        symlink_progress.unlink()
        original_state_bytes = replacement_state.read_bytes()
        renamed_state = replacement_root / "renamed-active-state.json"
        renamed_state.write_bytes(original_state_bytes)
        replacement_state.unlink()
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "canonical state path|recovery CAS",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair_replacement(
                SimpleNamespace(
                    **{
                        **vars(replacement_abandon_args),
                        "state": str(renamed_state),
                    }
                )
            )
        replacement_state.write_bytes(original_state_bytes)
        renamed_state.unlink()
        fake_third = pipeline.load_json(replacement_health_paths[2])
        fake_third["result"] = "no_response"
        fake_third.pop("previous_status")
        fake_third.pop("checkpoint_present")
        self.write_json(replacement_health_paths[2], fake_third)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "forced_interrupt_no_checkpoint",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair_replacement(
                replacement_abandon_args
            )
        fake_third["result"] = "forced_interrupt_no_checkpoint"
        fake_third["previous_status"] = "running"
        fake_third["checkpoint_present"] = False
        self.write_json(replacement_health_paths[2], fake_third)
        precise_first = pipeline.load_json(replacement_health_paths[0])
        approximate_time = precise_first.pop(
            "requested_at_approximate"
        )
        precise_first["requested_at"] = "2026-07-30T03:46:00Z"
        self.write_json(replacement_health_paths[0], precise_first)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "approximate|health evidence",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair_replacement(
                replacement_abandon_args
            )
        precise_first.pop("requested_at")
        precise_first["requested_at_approximate"] = approximate_time
        self.write_json(replacement_health_paths[0], precise_first)
        pre_event_log = central_log.read_bytes()
        pre_event_ledger = reservation_path.read_bytes()
        pre_event_state = replacement_state.read_bytes()
        replacement_state_record = pipeline.load_json(replacement_state)
        partial_event_id = (
            "phase:"
            + hashlib.sha1(
                (
                    str(
                        replacement_state_record[
                            "phase_instance_id"
                        ]
                    )
                    + "|replacement-01-unresponsive-abandonment"
                ).encode()
            ).hexdigest()[:16]
        )
        with central_log.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "schema": "lecture-animation-phase-event-v2",
                        "event_id": partial_event_id,
                        "result": "abandoned",
                    }
                )
                + "\n"
            )
        partial_event_log = central_log.read_bytes()
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "event without a receipt|partial",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair_replacement(
                replacement_abandon_args
            )
        self.assertEqual(central_log.read_bytes(), partial_event_log)
        self.assertEqual(reservation_path.read_bytes(), pre_event_ledger)
        self.assertEqual(replacement_state.read_bytes(), pre_event_state)
        central_log.write_bytes(pre_event_log)
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=2
        ) as executor:
            second_abandonment_results = list(
                executor.map(
                    lambda _: (
                        pipeline.command_abandon_unresponsive_animatic_repair_replacement(
                            replacement_abandon_args
                        )
                    ),
                    range(2),
                )
            )
        self.assertEqual(second_abandonment_results, [0, 0])
        second_abandonment = pipeline.load_json(
            replacement_abandonment
        )
        self.assertEqual(
            [row["result"] for row in second_abandonment["health_checks"]],
            [
                "no_response",
                "no_response",
                "forced_interrupt_no_checkpoint",
            ],
        )
        self.assertIn(
            "requested_at_approximate",
            second_abandonment["health_checks"][0],
        )
        self.assertNotIn(
            "requested_at",
            second_abandonment["health_checks"][0],
        )
        late_hidden_file = replacement_root / ".late-progress"
        late_hidden_file.write_text("late\n", encoding="utf-8")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "output root gained a non-control entry",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair_replacement(
                replacement_abandon_args
            )
        late_hidden_file.unlink()
        blocked_replacement_supervisor = pipeline.load_json(
            replacement_supervisor
        )
        self.assertEqual(
            blocked_replacement_supervisor["assignments"][
                "/root/ep8_g012_replacement_author"
            ]["state"],
            "blocked",
        )
        partial_supervisor = json.loads(
            json.dumps(blocked_replacement_supervisor)
        )
        partial_supervisor["assignments"][
            "/root/ep8_g012_replacement_author"
        ]["state"] = "active"
        partial_supervisor.pop("session_hash", None)
        partial_supervisor["session_hash"] = pipeline.object_hash(
            partial_supervisor
        )
        self.write_json(replacement_supervisor, partial_supervisor)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "supervisor block|blocked supervisor",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair_replacement(
                replacement_abandon_args
            )
        self.write_json(
            replacement_supervisor,
            blocked_replacement_supervisor,
        )
        second_abandonment_ledger = pipeline.load_json(
            reservation_path
        )
        partial_abandonment_ledger = json.loads(
            json.dumps(second_abandonment_ledger)
        )
        partial_abandonment_ledger[
            "animatic_repair_replacement_abandonments"
        ].pop("ep8:g012-animatic-repair:replacement-01")
        partial_abandonment_ledger.pop("ledger_hash", None)
        partial_abandonment_ledger["ledger_hash"] = (
            pipeline.object_hash(partial_abandonment_ledger)
        )
        self.write_json(
            reservation_path,
            partial_abandonment_ledger,
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "ledger fence",
        ):
            pipeline.command_abandon_unresponsive_animatic_repair_replacement(
                replacement_abandon_args
            )
        self.write_json(
            reservation_path,
            second_abandonment_ledger,
        )
        replacement_02_root = (
            self.episode
            / "review"
            / "v3"
            / "batch_c_replacement_02"
            / "g012"
        )
        replacement_02_supervisor = replacement_02_root.parent / (
            "supervisor.json"
        )
        replacement_02_batch = replacement_02_root.parent / (
            "production-batch.json"
        )
        replacement_02_continuation = replacement_02_root.parent / (
            "continuation.json"
        )
        replacement_02_extension = replacement_02_root.parent / (
            "extension.json"
        )
        replacement_02_args = SimpleNamespace(
            repo_root=str(self.root),
            episode=str(self.episode),
            abandonment=str(replacement_abandonment),
            replacement_author="/root/ep8_g012_replacement_author_02",
            planned_verifier="/root/ep8_review_batch_c",
            shared_work_key=(
                "ep8:g012-animatic-repair:replacement-02"
            ),
            allowed_output_root=str(replacement_02_root),
            supervisor_output=str(replacement_02_supervisor),
            production_batch_output=str(replacement_02_batch),
            continuation_output=str(replacement_02_continuation),
            extension_output=str(replacement_02_extension),
            required_attempt_ordinal=2,
        )
        preserved_ledger = pipeline.load_json(reservation_path)
        tampered_first_recovery = json.loads(
            json.dumps(preserved_ledger)
        )
        tampered_first_recovery[
            "animatic_repair_replacement_recoveries"
        ][abandonment["abandonment_hash"]]["status"] = "authorized"
        tampered_first_recovery.pop("ledger_hash", None)
        tampered_first_recovery["ledger_hash"] = pipeline.object_hash(
            tampered_first_recovery
        )
        self.write_json(reservation_path, tampered_first_recovery)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "replacement-01 recovery consumption",
        ):
            pipeline.command_authorize_animatic_repair_replacement(
                replacement_02_args
            )
        self.write_json(reservation_path, preserved_ledger)
        tampered_root_reservation = json.loads(
            json.dumps(preserved_ledger)
        )
        root_old_lineage = abandonment["old_lineage"]
        tampered_root_reservation["reservations"][
            root_old_lineage["reservation_id"]
        ]["actual"] = {
            "raw_input_plus_output_tokens": 0,
            "uncached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
        }
        tampered_root_reservation.pop("ledger_hash", None)
        tampered_root_reservation["ledger_hash"] = (
            pipeline.object_hash(tampered_root_reservation)
        )
        self.write_json(reservation_path, tampered_root_reservation)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "original batch-C abandonment|unknown-actual",
        ):
            pipeline.command_authorize_animatic_repair_replacement(
                replacement_02_args
            )
        self.write_json(reservation_path, preserved_ledger)
        preserved_root_receipt = pipeline.load_json(abandonment_path)
        tampered_root_receipt = json.loads(
            json.dumps(preserved_root_receipt)
        )
        tampered_root_receipt["actual"] = {
            "raw_input_plus_output_tokens": 0
        }
        tampered_root_receipt.pop("receipt_hash", None)
        tampered_root_receipt["receipt_hash"] = pipeline.object_hash(
            tampered_root_receipt
        )
        self.write_json(abandonment_path, tampered_root_receipt)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "root abandonment|actual",
        ):
            pipeline.command_authorize_animatic_repair_replacement(
                replacement_02_args
            )
        self.write_json(abandonment_path, preserved_root_receipt)
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=2
        ) as executor:
            replacement_02_results = list(
                executor.map(
                    lambda _: (
                        pipeline.command_authorize_animatic_repair_replacement(
                            replacement_02_args
                        )
                    ),
                    range(2),
                )
            )
        self.assertEqual(replacement_02_results, [0, 0])
        replacement_02_extension_record = pipeline.load_json(
            replacement_02_extension
        )
        self.assertEqual(
            replacement_02_extension_record[
                "max_active_seconds_allocation"
            ],
            1500,
        )
        self.assertEqual(
            replacement_02_extension_record["soft_checkpoints"],
            {
                "300": "read_complete_and_two_change_plan",
                "600": "source_patch_and_smoke_or_audit_started",
                "1200": "render_qc_and_self_review_underway",
                "1500": "hard_stop",
            },
        )
        replacement_02_continuation_record = pipeline.load_json(
            replacement_02_continuation
        )
        missing_attempt_02 = json.loads(
            json.dumps(replacement_02_continuation_record)
        )
        missing_attempt_02["replacement_recovery"].pop(
            "attempt_ordinal"
        )
        missing_attempt_02["replacement_recovery"].pop(
            "soft_checkpoints"
        )
        missing_attempt_02.pop("continuation_hash", None)
        missing_attempt_02["continuation_hash"] = pipeline.object_hash(
            missing_attempt_02
        )
        missing_attempt_02_errors = (
            pipeline.validate_animatic_repair_budget_continuation(
                missing_attempt_02,
                repo_root=self.root,
                episode=self.episode,
                efficiency_contract=efficiency,
                production_batch=pipeline.load_json(
                    replacement_02_batch
                ),
                supervisor_session=pipeline.load_json(
                    replacement_02_supervisor
                ),
                efficiency_contract_path=self.efficiency_contract,
                production_batch_path=replacement_02_batch,
                supervisor_session_path=replacement_02_supervisor,
                at_time=missing_attempt_02["created_at"],
            )
        )
        self.assertTrue(
            any(
                "attempt" in error or "soft-checkpoint" in error
                for error in missing_attempt_02_errors
            ),
            missing_attempt_02_errors,
        )
        nonlegacy_missing = pipeline.load_json(
            replacement_continuation
        )
        nonlegacy_missing["replacement_recovery"][
            "abandonment_path"
        ] = pipeline.relative_or_absolute(
            replacement_abandonment,
            self.root,
        )
        nonlegacy_missing["replacement_recovery"][
            "abandonment_hash"
        ] = second_abandonment["abandonment_hash"]
        nonlegacy_missing["replacement_recovery"].pop(
            "attempt_ordinal"
        )
        nonlegacy_missing["replacement_recovery"].pop(
            "soft_checkpoints"
        )
        nonlegacy_missing.pop("continuation_hash", None)
        nonlegacy_missing["continuation_hash"] = pipeline.object_hash(
            nonlegacy_missing
        )
        nonlegacy_errors = (
            pipeline.validate_animatic_repair_budget_continuation(
                nonlegacy_missing,
                repo_root=self.root,
                episode=self.episode,
                efficiency_contract=efficiency,
                production_batch=pipeline.load_json(replacement_batch),
                supervisor_session=pipeline.load_json(
                    replacement_supervisor
                ),
                efficiency_contract_path=self.efficiency_contract,
                production_batch_path=replacement_batch,
                supervisor_session_path=replacement_supervisor,
                at_time=nonlegacy_missing["created_at"],
            )
        )
        self.assertTrue(
            any(
                "attempt" in error or "soft-checkpoint" in error
                for error in nonlegacy_errors
            ),
            nonlegacy_errors,
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "1500-second|active allocation",
        ):
            start(
                "batch_c",
                "g012_singularity_winding_synthesis",
                actor="/root/ep8_g012_replacement_author_02",
                state_suffix="-replacement-02-over-active",
                continuation_override=replacement_02_continuation,
                extension_override=replacement_02_extension,
                batch_override=replacement_02_batch,
                recovery=replacement_abandonment,
                active_seconds=1501,
                shared_key_override=(
                    "ep8:g012-animatic-repair:replacement-02"
                ),
            )
        replacement_02_state = start(
            "batch_c",
            "g012_singularity_winding_synthesis",
            actor="/root/ep8_g012_replacement_author_02",
            state_suffix="-replacement-02",
            continuation_override=replacement_02_continuation,
            extension_override=replacement_02_extension,
            batch_override=replacement_02_batch,
            recovery=replacement_abandonment,
            active_seconds=1500,
            shared_key_override=(
                "ep8:g012-animatic-repair:replacement-02"
            ),
        )
        replacement_animatic = replacement_02_root / "animatic-v03.mp4"
        replacement_review = replacement_02_root / "self-review.md"
        replacement_02_root.mkdir(parents=True, exist_ok=True)
        replacement_animatic.write_bytes(b"replacement-02")
        replacement_review.write_text(
            "Pending independent review.\n",
            encoding="utf-8",
        )
        self.assertEqual(
            end(
                replacement_02_state,
                "completed",
                replacement_animatic,
                replacement_review,
                output_tokens=8_001,
            ),
            2,
        )
        completed_replacement = pipeline.load_json(
            replacement_02_state
        )
        self.assertTrue(
            completed_replacement["phase_envelope_status_at_end"][
                "exceeded"
            ]
        )
        self.assertTrue(
            completed_replacement["phase_envelope_status_at_end"][
                "active_exceeded"
            ]
        )
        self.assertFalse(
            completed_replacement[
                "phase_envelope_completion_exceeded"
            ]
        )
        self.assertIn(
            "PHASE_BUDGET_ENVELOPE_EXCEEDED",
            completed_replacement["efficiency_status_at_end"]["alerts"],
        )
        self.assertIn(
            "output_tokens",
            pipeline.event_rows(phase_log)[-1][
                "token_allocation_exceeded"
            ],
        )
        ledger = pipeline.load_json(reservation_path)
        recovery_rows = ledger[
            "animatic_repair_replacement_recoveries"
        ]
        self.assertEqual(len(recovery_rows), 2)
        self.assertEqual(
            ledger["animatic_repair_recovery_attempt_count"],
            2,
        )
        self.assertTrue(
            all(
                row["status"] == "consumed"
                for row in recovery_rows.values()
            )
        )
        replacement_02_recovery_row = recovery_rows[
            second_abandonment["abandonment_hash"]
        ]
        replacement_02_reservation = ledger["reservations"][
            replacement_02_recovery_row["reservation_id"]
        ]
        self.assertEqual(
            replacement_02_reservation["status"],
            "released",
        )
        self.assertEqual(
            replacement_02_reservation["actual"]["output_tokens"],
            8_001,
        )
        self.assertFalse(
            replacement_02_reservation.get("refunded", False)
        )
        for table_name in (
            "animatic_repair_budget_continuations",
            "animatic_repair_token_extensions",
        ):
            replacement_02_row = ledger[table_name][
                "ep8:g012-animatic-repair:replacement-02"
            ]
            self.assertEqual(replacement_02_row["status"], "consumed")
            self.assertFalse(
                replacement_02_row.get("refunded", False)
            )
        third_attempt_args = SimpleNamespace(
            **{
                **vars(replacement_02_args),
                "supervisor_output": str(
                    replacement_02_supervisor.with_name(
                        "third-supervisor.json"
                    )
                ),
            }
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "spent|attempt|maximum",
        ):
            pipeline.command_authorize_animatic_repair_replacement(
                third_attempt_args
            )

    def test_episode8_replacement_unresponsive_evidence_is_real_and_exact(
        self,
    ) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        episode = (
            repo_root / "videos/0008-mpm-8-cauchy_integral"
        )
        recovery = (
            episode
            / "review/v3/batch_c_replacement/recovery"
        )
        health = [
            pipeline.load_json(
                recovery / f"health_check_{sequence:02d}.json"
            )
            for sequence in (1, 2, 3)
        ]
        self.assertEqual(
            [row["result"] for row in health],
            [
                "no_response",
                "no_response",
                "forced_interrupt_no_checkpoint",
            ],
        )
        self.assertEqual(
            health[0]["requested_at_approximate"],
            "2026-07-30T03:46Z",
        )
        self.assertNotIn("requested_at", health[0])
        self.assertEqual(health[2]["previous_status"], "running")
        self.assertFalse(health[2]["checkpoint_present"])
        accepted_issue = pipeline.load_json(
            episode
            / "review/issues/"
            "agent_g012_replacement_identity_unresponsive_2026-07-30.json"
        )
        self.assertEqual(
            accepted_issue["pattern_key"],
            (
                "replacement_repair_author_unresponsive_without_"
                "artifact_progress"
            ),
        )
        if accepted_issue["status"] != "open":
            self.assertIn(
                accepted_issue["status"],
                {"verified_fixed", "human_approved", "resolved", "mitigated"},
            )
            resolution = accepted_issue["resolution_history"][-1]
            self.assertEqual(resolution["previous_status"], "open")
            self.assertEqual(resolution["new_status"], accepted_issue["status"])
            self.assertEqual(resolution["authority"], "user_final_episode_review")
            self.assertEqual(
                resolution["approved_episode_candidate"]["sha256"],
                "56ed7c80e2a70c1ad78b0b624a2868c032ab03bb1daddfb924fd3ba3da07b070",
            )
        self.assertTrue(accepted_issue["must_check_in_future"])
        feedback = (
            episode
            / "review/agent-feedback/"
            "2026-07-30-g012-replacement-author-unresponsive.md"
        )
        self.assertTrue(feedback.is_file())
        self.assertIn(
            "forced_interrupt_no_checkpoint",
            feedback.read_text(encoding="utf-8"),
        )
        active_state = (
            episode
            / "review/v3/"
            "g012_singularity_winding_synthesis_replacement/"
            "animatic_v03_repair_phase_active.json"
        )
        active_state_record = pipeline.load_json(active_state)
        continuation = pipeline.load_json(
            repo_root
            / active_state_record[
                "animatic_repair_budget_continuation_path"
            ]
        )
        output_root = (
            repo_root
            / continuation["allowed_output_roots_by_scene"][
                "g012_singularity_winding_synthesis"
            ]
        )
        self.assertEqual(
            pipeline.animatic_repair_zero_progress_violations(
                output_root=output_root,
                state_path=active_state,
                receipt_path=(
                    recovery / "replacement-01-abandonment.json"
                ),
                repo_root=repo_root,
            ),
            [],
        )
        recovery_receipt_path = (
            repo_root
            / active_state_record["animatic_repair_recovery_path"]
        )
        recovery_receipt = pipeline.load_json(recovery_receipt_path)
        extension_path = (
            repo_root
            / active_state_record[
                "animatic_repair_token_extension_path"
            ]
        )
        batch_path = (
            repo_root / active_state_record["production_batch_path"]
        )
        supervisor_path = (
            repo_root
            / recovery_receipt["replacement_authorization"][
                "supervisor_path"
            ]
        )
        # The original recovery receipt authorized replacement-01.  That
        # authorization was later consumed and replacement-01 was abandoned,
        # so validating the historical receipt against the current mutable
        # supervisor must now fail closed instead of pretending the earlier
        # supervisor binding is still live.
        self.assertEqual(
            pipeline.validate_animatic_repair_recovery_binding(
                recovery_receipt,
                repo_root=repo_root,
                episode=episode,
                receipt_path=recovery_receipt_path,
                continuation=continuation,
                continuation_path=(
                    repo_root
                    / active_state_record[
                        "animatic_repair_budget_continuation_path"
                    ]
                ),
                extension=pipeline.load_json(extension_path),
                extension_path=extension_path,
                production_batch=pipeline.load_json(batch_path),
                production_batch_path=batch_path,
                supervisor=pipeline.load_json(supervisor_path),
                supervisor_path=supervisor_path,
            ),
            [
                (
                    "animatic repair recovery replacement "
                    "supervisor_hash is stale"
                )
            ],
        )
        replacement_abandonment = pipeline.load_json(
            recovery / "g012_replacement_01_abandonment.json"
        )
        self.assertEqual(
            replacement_abandonment["schema"],
            (
                "lecture-animation-animatic-repair-"
                "replacement-abandonment-v1"
            ),
        )
        self.assertTrue(
            pipeline.validate_hashed_record(
                replacement_abandonment,
                "receipt_hash",
            )
        )
        self.assertEqual(
            replacement_abandonment["old_lineage"]["supervisor_path"],
            recovery_receipt["replacement_authorization"][
                "supervisor_path"
            ],
        )
        self.assertEqual(
            pipeline.load_json(supervisor_path)["session_hash"],
            replacement_abandonment["old_lineage"]["supervisor_hash"],
        )
        self.assertEqual(
            replacement_abandonment["status"],
            "replacement_authorized",
        )
        self.assertEqual(
            replacement_abandonment["replacement_authorization"][
                "attempt_ordinal"
            ],
            2,
        )
        self.assertFalse(replacement_abandonment["token_observed"])
        self.assertIsNone(replacement_abandonment["actual"])
        self.assertFalse(replacement_abandonment["refund"])

    def test_human_wait_ignores_resume_context_token_delta(
        self,
    ) -> None:
        state = (
            self.episode
            / "review"
            / "evolution"
            / "human-wait.json"
        )
        phase_log = (
            self.episode
            / "review"
            / "evolution"
            / "human-wait.jsonl"
        )
        usage_path = (
            self.episode
            / "review"
            / "evolution"
            / "human-wait-usage.json"
        )
        self.write_json(
            usage_path,
            {
                "input_tokens": 100,
                "cached_input_tokens": 50,
                "output_tokens": 10,
                "reasoning_tokens": 5,
            },
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_phase_start(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        efficiency_contract=str(
                            self.efficiency_contract
                        ),
                        run_id="human-wait",
                        scene_slug="episode",
                        phase="human_wait",
                        phase_purpose=None,
                        actor_model="human",
                        active_seconds_allocation=0,
                        raw_token_allocation=0,
                        uncached_input_token_allocation=0,
                        output_token_allocation=0,
                        reasoning_token_allocation=0,
                        prompt_bytes=0,
                        artifact_input_bytes=0,
                        files_read=0,
                        usage_file=str(usage_path),
                        state=str(state),
                    )
                ),
                0,
            )
            self.write_json(
                usage_path,
                {
                    "input_tokens": 50_000,
                    "cached_input_tokens": 20_000,
                    "output_tokens": 4_000,
                    "reasoning_tokens": 2_000,
                },
            )
            self.assertEqual(
                pipeline.command_phase_end(
                    SimpleNamespace(
                        state=str(state),
                        phase_log=str(phase_log),
                        result="completed",
                        manifest_hash="",
                        usage_file=None,
                    )
                ),
                0,
            )
        event = pipeline.event_rows(phase_log)[0]
        self.assertEqual(event["phase"], "human_wait")
        self.assertEqual(event["token_source_kind"], "human_wait_zero")
        self.assertEqual(event["token_allocation_exceeded"], [])
        self.assertEqual(event["input_tokens"], 0)
        self.assertEqual(event["cached_input_tokens"], 0)
        self.assertEqual(event["output_tokens"], 0)
        self.assertEqual(event["reasoning_tokens"], 0)

    def test_close_legacy_episode_efficiency_requires_full_measured_workflow(
        self,
    ) -> None:
        episode = self.root / "videos" / "0009-close-test"
        self.write_json(
            episode / "progressive_production.json",
            {"scenes": [{"scene_slug": "g001"}]},
        )
        contract_path = (
            episode
            / "review"
            / "evolution"
            / "episode_efficiency_contract.json"
        )
        args = SimpleNamespace(
            episode_target_hours=8.75,
            delivery_target_hours=None,
            delivery_clock=None,
            retrospective_reserve_minutes=45.0,
            raw_token_budget=50_000_000,
            uncached_input_token_budget=2_000_000,
            output_token_budget=300_000,
            reasoning_token_budget=100_000,
            token_budget_warning_fraction=0.75,
            max_false_passes=0,
            max_known_regression_recurrences=0,
            max_human_issue_scene_rate=0.25,
        )
        contract = pipeline.episode_efficiency_contract_data(
            self.root,
            episode,
            args,
        )
        self.write_json(contract_path, contract)
        self.write_json(
            pipeline.episode_efficiency_reservation_ledger(contract),
            pipeline.empty_efficiency_reservation_ledger(contract),
        )
        central_log = pipeline.episode_efficiency_central_log(contract)
        central_log.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for index, phase in enumerate(
            (
                "planning",
                "design",
                "authoring",
                "render",
                "review",
                "tts",
                "asr",
                "finalization",
                "retrospective",
            )
        ):
            rows.append(
                {
                    "schema": "lecture-animation-phase-event-v2",
                    "event_id": f"phase:complete-{phase}",
                    "phase_instance_id": f"phase-instance:{phase}",
                    "scene_slug": (
                        "g001"
                        if phase
                        in {
                            "design",
                            "authoring",
                            "render",
                            "review",
                            "tts",
                            "asr",
                        }
                        else "episode"
                    ),
                    "phase": phase,
                    "result": "completed",
                    "started_at": (
                        f"2026-07-28T00:00:{index:02d}+00:00"
                    ),
                    "ended_at": (
                        f"2026-07-28T00:00:{index + 1:02d}+00:00"
                    ),
                    "duration_seconds": 1.0,
                    "input_tokens": 100,
                    "cached_input_tokens": 80,
                    "output_tokens": 10,
                    "reasoning_tokens": 2,
                    "token_observed": True,
                    "token_allocation": {
                        "raw_input_plus_output_tokens": 1_000,
                        "uncached_input_tokens": 100,
                        "output_tokens": 100,
                        "reasoning_tokens": 20,
                    },
                    "prompt_bytes": 1_000,
                    "artifact_input_bytes": 4_000,
                    "files_read": 4,
                    "task_resource_limits": dict(
                        pipeline.DEFAULT_TASK_RESOURCE_LIMITS
                    ),
                }
            )
        central_log.write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        completion_path = episode / "episode_completion.json"
        final_video = episode / "exports" / "final" / "episode.mp4"
        final_video.parent.mkdir(parents=True, exist_ok=True)
        final_video.write_bytes(b"exact-upload-master")
        final_video_artifact = pipeline.artifact_snapshot(
            final_video, self.root
        )
        completion = {
            "schema": "lecture-animation-episode-completion-v2",
            "created_at": "2026-07-28T00:01:00+00:00",
            "episode": pipeline.relative_or_absolute(
                episode,
                self.root,
            ),
            "scene_outcomes": {"g001": {"event_id": "human-pass"}},
            "final_artifacts": {
                "final_video": final_video_artifact,
            },
        }
        completion["completion_hash"] = pipeline.object_hash(completion)
        self.write_json(completion_path, completion)
        output = (
            episode
            / "review"
            / "evolution"
            / "episode_efficiency_close.json"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_close_episode_efficiency(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(episode),
                        efficiency_contract=str(contract_path),
                        completion_receipt=str(completion_path),
                        delivery_clock=None,
                        metric_policy_profile=None,
                        output=str(output),
                    )
                ),
                0,
            )
        receipt = pipeline.load_json(output)
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(receipt["evaluation"]["compliant"])
        self.assertIsNone(receipt["evaluation"]["delivery_clock"])
        self.assertEqual(
            pipeline.load_json(contract_path)["status"],
            "completed",
        )

    def test_latest_human_revise_supersedes_an_older_pass(self) -> None:
        outcome_log = self.episode / "review" / "evolution" / "latest-outcome.jsonl"
        outcome_log.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                "schema": "lecture-animation-outcome-v2",
                "event_id": "pass-1",
                "scene_slug": "g001",
                "human_verdict": "pass",
                "manifest_hash": "manifest-a",
            },
            {
                "schema": "lecture-animation-outcome-v2",
                "event_id": "revise-2",
                "scene_slug": "g001",
                "human_verdict": "revise",
                "manifest_hash": "manifest-a",
            },
        ]
        outcome_log.write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        self.assertNotIn("g001", pipeline.latest_human_passes(outcome_log))

    def test_diagnostic_packet_is_hash_bound_and_cannot_grant_final_pass(self) -> None:
        profile = self.make_profile()
        previous_manifest = {
            "scene_slug": "g002c_riemann_sum_limit",
            "manifest_hash": "old-manifest",
            "artifacts": {
                "source": {"sha256": "source-v1", "size": 10},
                "review_mp4": {"sha256": "mp4-v1", "size": 20},
            },
        }
        current_manifest = {
            "scene_slug": "g002c_riemann_sum_limit",
            "manifest_hash": "new-manifest",
            "artifacts": {
                "source": {"sha256": "source-v2", "size": 11},
                "review_mp4": {"sha256": "mp4-v2", "size": 21},
            },
        }
        previous_review = {
            "manifest_hash": "old-manifest",
            "reviewer": "independent-reviewer",
            "verdict": "revise",
            "findings": [
                {
                    "finding_id": "R01",
                    "rule_id": "STAGE-003",
                    "severity": "major",
                    "timestamp_seconds": 4.2,
                    "object_id": "formula_old",
                    "problem": "Old and new formulae overlap during the handoff.",
                    "suggested_fix": "Retire the old formula before the replacement enters.",
                    "status": "open",
                }
            ],
        }
        session = {
            "schema": "lecture-animation-review-session-v2",
            "session_id": "review-session:test",
            "reviewer": "independent-reviewer",
            "reviewer_model": "test-reviewer-v1",
            "reviewer_agent_id": "agent-reviewer-001",
            "status": "active",
        }
        impact = {
            "schema": "lecture-animation-change-impact-v2",
            "previous_manifest_hash": "old-manifest",
            "current_manifest_hash": "new-manifest",
            "changed_artifacts": ["review_mp4", "source"],
            "changed_object_ids": ["formula_old"],
            "changed_windows": [[3.2, 5.2]],
            "changed_layers": ["layout", "timing_attention"],
            "semantic_contract_changed": False,
            "unchanged_contracts_asserted": True,
        }
        impact["impact_hash"] = pipeline.object_hash(impact)
        packet = pipeline.diagnostic_packet_data(
            previous_manifest, current_manifest, previous_review, profile, session, impact
        )
        self.assertTrue(pipeline.validate_hashed_record(packet, "packet_hash"))
        self.assertFalse(packet["may_grant_user_review_pending"])
        self.assertIn("source", packet["changed_artifacts"])
        submission = {
            "schema": "lecture-animation-diagnostic-review-v2",
            "packet_hash": packet["packet_hash"],
            "current_manifest_hash": "new-manifest",
            "reviewer": "independent-reviewer",
            "reviewer_model": "test-reviewer-v1",
            "reviewer_agent_id": "agent-reviewer-001",
            "verdict": "diagnostic_fix_verified",
            "finding_checks": [
                {
                    "finding_id": "R01",
                    "status": "fixed",
                    "timestamp_seconds": 4.2,
                    "observation": "The old formula fully exits before the replacement formula enters the same region.",
                }
            ],
            "regression_samples": [
                {
                    "timestamp_seconds": timestamp,
                    "observation": "The unchanged region preserves its original object identity and remains visually stable.",
                }
                for timestamp in packet["required_regression_samples"]
            ],
        }
        self.assertEqual(pipeline.verify_diagnostic_review_data(submission, packet, session), [])
        submission["requests_user_review_pending"] = True
        self.assertTrue(any("never grant" in error for error in pipeline.verify_diagnostic_review_data(submission, packet, session)))

    def test_repair_contract_requires_code_guidance_and_blocks_incomplete_response(self) -> None:
        evidence_root = self.episode / "repair-evidence"
        evidence_root.mkdir(parents=True)
        source_file = evidence_root / "composer.py"
        source_file.write_text("def animate_partial_sum():\n    pass\n", encoding="utf-8")
        review_mp4 = evidence_root / "review.mp4"
        review_mp4.write_bytes(b"review-video")
        qc_dir = evidence_root / "qc"
        qc_dir.mkdir()
        evidence_frames = []
        for index in range(1, 9):
            frame = qc_dir / f"evidence-{index:02d}.png"
            frame.write_bytes(f"evidence-frame-{index}".encode())
            evidence_frames.append(frame)
        telemetry_file = evidence_root / "telemetry.json"
        telemetry_file.write_text("{}\n", encoding="utf-8")
        live_policy_file = evidence_root / "live_policy.json"
        live_policy_file.write_text('{"rules": ["stage-clearance"]}\n', encoding="utf-8")
        baseline_manifest = {
            "schema": "lecture-animation-review-manifest-v2",
            "scene_slug": "g002c_riemann_sum_limit",
            "manifest_hash": "baseline-manifest",
            "artifacts": {
                "source": pipeline.artifact_snapshot(source_file, self.root),
                "telemetry": pipeline.artifact_snapshot(telemetry_file, self.root),
                "review_mp4": pipeline.artifact_snapshot(review_mp4, self.root),
                "qc": pipeline.artifact_snapshot(qc_dir, self.root),
                "live_policy": pipeline.artifact_snapshot(live_policy_file, self.root),
            },
        }
        finding = {
            "finding_id": "R01",
            "rule_id": "RECON-001",
            "severity": "blocker",
            "timestamp_seconds": 4.2,
            "object_id": "partial_sum",
            "problem": "The selected coefficient pair changes the curve before its carrier reaches the accumulator.",
            "impact": "A novice sees correlation rather than one coefficient pair causing one exact partial-sum update.",
            "status": "open",
            "lineage": {
                "classification": "repair_induced",
                "root_issue_id": "series-synthesis-causality",
                "parent_finding_id": "R00",
                "evidence": "The previous repair introduced simultaneous pair motion and the baseline candidate had no partial-sum carrier.",
            },
            "repair_guidance": {
                "source_anchors": [
                    {
                        "path": pipeline.relative_or_absolute(source_file, self.root),
                        "symbol": "animate_partial_sum",
                        "reason": "This function owns carrier landing and the accumulator replacement timing.",
                    }
                ],
                "mathematical_invariant": "One selected coefficient pair updates one persistent accumulator exactly once.",
                "required_changes": ["Delay the accumulator update until the selected pair lands at its destination."],
                "must_preserve": ["Preserve the existing coefficient values and symmetric-pair selection."],
                "affected_artifacts": ["source", "telemetry", "review_mp4", "qc", "live_policy"],
                "acceptance_tests": [
                    {
                        "test_id": "pair-ownership",
                        "method": "Decode the transfer window sequentially and compare landing with the next accumulator state.",
                        "expected_evidence": "The pair lands first, one curve changes next, and the result remains stable afterward.",
                    }
                ],
                "new_risks_to_probe": ["The serialized transfer may reduce the final settled comparison hold."],
            },
        }
        review = {
            "schema": "lecture-animation-review-v2",
            "manifest_hash": "baseline-manifest",
            "reviewer": "independent-reviewer",
            "reviewer_agent_id": "reviewer-001",
            "verdict": "revise",
            "findings": [finding],
        }
        exhaustion = pipeline.review_exhaustion_draft_data(review, baseline_manifest)
        cluster = exhaustion["clusters"][0]
        cluster["source_anchors"] = finding["repair_guidance"]["source_anchors"]
        cluster["upstream_causes"] = ["Carrier landing and accumulator replacement share one premature trigger event."]
        cluster["downstream_symptoms"] = ["The persistent curve changes before the selected coefficient visibly arrives."]
        cluster["dependent_artifacts"] = ["source", "telemetry", "review_mp4", "qc"]
        cluster["sibling_risks"] = ["Other coefficient-pair transfers may reuse the same premature trigger ordering."]
        cluster["must_preserve"] = finding["repair_guidance"]["must_preserve"]
        cluster["repair_induced_risks"] = finding["repair_guidance"]["new_risks_to_probe"]
        cluster["coverage_complete"] = True
        cluster["completeness_reason"] = "The whole transfer window, shared callback, sibling pairs, and all dependent outputs were inspected."
        evidence_index = 0
        for layer in pipeline.HARD_GATE_LAYERS:
            frame = evidence_frames[evidence_index]
            evidence_index += 1
            cluster["hard_gate_layers"][layer] = {
                "checked": True,
                "timestamps": [4.2],
                "observation": f"The reviewer checked the {layer} consequence at carrier landing and the following accumulator frame.",
                "evidence": [
                    {
                        "evidence_id": f"cluster-{layer}-1",
                        "artifact_key": "qc",
                        "source_artifact_key": "review_mp4",
                        "source_sha256": baseline_manifest["artifacts"]["review_mp4"]["sha256"],
                        "frame_path": pipeline.relative_or_absolute(frame, self.root),
                        "frame_sha256": hashlib.sha256(frame.read_bytes()).hexdigest(),
                        "timestamp_seconds": 4.2,
                        "object_ids": ["partial_sum"],
                        "observation": f"The decoded frame exposes the {layer} state at the carrier landing boundary.",
                    }
                ],
            }
        for search in exhaustion["unclustered_searches"]:
            frames = evidence_frames[evidence_index:evidence_index + 2]
            evidence_index += 2
            if len(frames) < 2:
                frames = evidence_frames[:2]
            search.update(
                performed=True,
                query=f"Search the full candidate for additional {search['layer']} symptoms sharing this trigger.",
                result="No additional root cause remained after checking the transfer family and neighboring settled states.",
                evidence=[
                    {
                        "evidence_id": f"search-{search['layer']}-{index}",
                        "artifact_key": "qc",
                        "source_artifact_key": "review_mp4",
                        "source_sha256": baseline_manifest["artifacts"]["review_mp4"]["sha256"],
                        "frame_path": pipeline.relative_or_absolute(frame, self.root),
                        "frame_sha256": hashlib.sha256(frame.read_bytes()).hexdigest(),
                        "timestamp_seconds": 2.0 + index,
                        "object_ids": ["partial_sum"],
                        "observation": f"This decoded frame checks the {search['layer']} sibling path outside the root interval.",
                    }
                    for index, frame in enumerate(frames, 1)
                ],
            )
        exhaustion["coverage_complete"] = True
        exhaustion["reviewer_statement"] = "Every open symptom is assigned to one root cause, and sibling code paths plus all four gate layers were checked."
        exhaustion["finding_classifications"] = [
            {
                "finding_id": finding["finding_id"],
                "origin_class": "pre_existing_review_miss",
                "detectable_in_prior_artifact": True,
                "prior_manifest_hash": "prior-manifest-hash-0001",
                "reason": "The unchanged trigger ordering and decoded evidence were available to the prior full review.",
            }
        ]
        exhaustion["unreviewed_surfaces"] = []
        exhaustion["reviewer_miss_count"] = 1
        exhaustion["verdict"] = "exhaustive_for_repair"
        exhaustion["exhaustion_hash"] = pipeline.object_hash(exhaustion)
        review["review_exhaustion"] = exhaustion
        self.assertEqual(
            pipeline.validate_review_exhaustion_data(
                exhaustion, review, baseline_manifest, repo_root=self.root
            ),
            [],
        )
        partial_exhaustion = json.loads(json.dumps(exhaustion))
        partial_exhaustion["clusters"][0]["sibling_risks"] = []
        partial_exhaustion.pop("exhaustion_hash")
        partial_exhaustion["exhaustion_hash"] = pipeline.object_hash(partial_exhaustion)
        self.assertTrue(
            any(
                "sibling_risks" in error
                for error in pipeline.validate_review_exhaustion_data(
                    partial_exhaustion, review, baseline_manifest, repo_root=self.root
                )
            )
        )
        contract = pipeline.repair_contract_data(review, baseline_manifest)
        self.assertEqual(
            pipeline.validate_repair_contract_data(
                contract, review, baseline_manifest, repo_root=self.root
            ),
            [],
        )
        rejected_author_review = {
            "schema": "lecture-animation-author-self-review-v2",
            "manifest_hash": baseline_manifest["manifest_hash"],
            "scene_slug": baseline_manifest["scene_slug"],
            "owner": "animation-author",
            "author_agent_id": "agent-author-001",
            "author_model": "test-author-v1",
            "self_review_round": 2,
            "findings": [
                {
                    "finding_id": finding["finding_id"],
                    "status": "open",
                    "severity": finding["severity"],
                    "timestamp_seconds": finding["timestamp_seconds"],
                    "object_id": finding["object_id"],
                    "rule_id": finding["rule_id"],
                    "problem": finding["problem"],
                }
            ],
            "verdict": "revise_before_independent_review",
        }
        rejected_draft_hash = pipeline.object_hash(rejected_author_review)
        author_attempt_verification_key = pipeline.object_hash(
            {
                "manifest_hash": baseline_manifest["manifest_hash"],
                "draft_hash": rejected_draft_hash,
                "previous_review_hash": None,
                "previous_author_self_review_hash": None,
            }
        )
        recomputed_author_gate_errors = [
            "author self-review cannot hand off with open findings",
            "author self-review verdict must be ready_for_independent_review",
        ]
        rejected_author_attempt = {
            "schema": "lecture-animation-author-self-review-attempt-v2",
            "attempt_id": (
                "author-self-review:"
                + hashlib.sha1(author_attempt_verification_key.encode()).hexdigest()[:16]
            ),
            "manifest_hash": baseline_manifest["manifest_hash"],
            "owner": rejected_author_review["owner"],
            "author_agent_id": rejected_author_review["author_agent_id"],
            "author_model": rejected_author_review["author_model"],
            "self_review_round": rejected_author_review["self_review_round"],
            "previous_review_hash": None,
            "previous_author_self_review_hash": None,
            "draft_hash": rejected_draft_hash,
            "findings_caught_before_handoff": 1,
            "machine_gate_findings": 2,
            "gate_errors": recomputed_author_gate_errors,
            "gate_accepted": False,
            "verdict": "self_review_revise",
            "verification_key": author_attempt_verification_key,
        }
        author_repair_plan = json.loads(json.dumps(review))
        author_repair_plan["schema"] = "lecture-animation-author-repair-plan-v1"
        author_repair_plan["author_self_review_hash"] = rejected_draft_hash
        for item in author_repair_plan["findings"]:
            source_finding = next(
                source
                for source in rejected_author_review["findings"]
                if source["finding_id"] == item["finding_id"]
            )
            item["source_author_finding_hash"] = pipeline.object_hash(source_finding)
            item["source_author_finding"] = json.loads(json.dumps(source_finding))
        author_repair_plan["review_exhaustion"]["review_core_hash"] = (
            pipeline.review_core_hash(author_repair_plan)
        )
        author_repair_plan["review_exhaustion"].pop("exhaustion_hash")
        author_repair_plan["review_exhaustion"]["exhaustion_hash"] = pipeline.object_hash(
            author_repair_plan["review_exhaustion"]
        )
        author_contract = pipeline.author_repair_contract_data(
            author_repair_plan,
            rejected_author_review,
            rejected_author_attempt,
            baseline_manifest,
        )
        self.assertEqual(
            pipeline.validate_author_repair_contract_data(
                author_contract,
                author_repair_plan,
                rejected_author_review,
                rejected_author_attempt,
                baseline_manifest,
                self.root,
                recomputed_gate_errors=recomputed_author_gate_errors,
            ),
            [],
        )
        substituted_author_plan = json.loads(json.dumps(author_repair_plan))
        substituted_author_plan["findings"][0]["problem"] = (
            "A substituted problem statement must not inherit the original finding identity."
        )
        self.assertTrue(
            any(
                "changed immutable source field problem" in error
                for error in pipeline.validate_author_repair_plan_data(
                    substituted_author_plan,
                    rejected_author_review,
                    baseline_manifest,
                    self.root,
                )
            )
        )
        missing_source_snapshot = json.loads(json.dumps(author_repair_plan))
        missing_source_snapshot["findings"][0].pop("source_author_finding")
        self.assertTrue(
            any(
                "exact source finding snapshot" in error
                for error in pipeline.validate_author_repair_plan_data(
                    missing_source_snapshot,
                    rejected_author_review,
                    baseline_manifest,
                    self.root,
                )
            )
        )
        missing_source_field = json.loads(json.dumps(author_repair_plan))
        missing_source_field["findings"][0].pop("problem")
        self.assertTrue(
            any(
                "omitted immutable source field problem" in error
                for error in pipeline.validate_author_repair_plan_data(
                    missing_source_field,
                    rejected_author_review,
                    baseline_manifest,
                    self.root,
                )
            )
        )
        forged_author_attempt = json.loads(json.dumps(rejected_author_attempt))
        forged_author_attempt["verification_key"] = "forged"
        self.assertTrue(
            any(
                "verification_key" in error
                for error in pipeline.validate_author_repair_contract_data(
                    author_contract,
                    author_repair_plan,
                    rejected_author_review,
                    forged_author_attempt,
                    baseline_manifest,
                    self.root,
                    recomputed_gate_errors=recomputed_author_gate_errors,
                )
            )
        )
        accepted_author_attempt = json.loads(json.dumps(rejected_author_attempt))
        accepted_author_attempt["gate_accepted"] = True
        accepted_author_attempt["verdict"] = "ready_for_independent_review"
        self.assertTrue(
            any(
                "gate-rejected" in error
                for error in pipeline.validate_author_repair_contract_data(
                    author_contract,
                    author_repair_plan,
                    rejected_author_review,
                    accepted_author_attempt,
                    baseline_manifest,
                    self.root,
                    recomputed_gate_errors=recomputed_author_gate_errors,
                )
            )
        )
        self.assertTrue(
            any(
                "canonical self-review gate recomputation" in error
                for error in pipeline.validate_author_repair_contract_data(
                    author_contract,
                    author_repair_plan,
                    rejected_author_review,
                    rejected_author_attempt,
                    baseline_manifest,
                    self.root,
                )
            )
        )
        current_manifest = json.loads(json.dumps(baseline_manifest))
        current_manifest["manifest_hash"] = "current-manifest"
        for key in ("source", "telemetry", "review_mp4", "qc"):
            current_manifest["artifacts"][key]["sha256"] += "-v2"
        execution = pipeline.repair_execution_data(
            contract,
            mode="same_author",
            repair_actor_agent_id="author-agent",
            planned_verifier_agent_id="fresh-reviewer",
            handoff_count=1,
        )
        response = pipeline.repair_response_draft_data(
            contract,
            current_manifest,
            repair_execution=execution,
        )
        resolution = response["resolutions"][0]
        resolution["diagnosis"] = "The accumulator update used the start of carrier motion instead of the carrier landing event."
        resolution["root_cause_addressed"] = "The repaired event ordering now makes carrier landing the sole trigger for the persistent accumulator update."
        resolution["code_changes"][0]["change"] = "Move the accumulator replacement after the carrier landing callback and retain one curve identity."
        resolution["changed_artifacts"] = ["source", "telemetry", "review_mp4", "qc"]
        resolution["acceptance_results"][0].update(
            status="passed",
            evidence="Sequential frames show landing at 4.20 seconds and the sole curve update on the following frame.",
        )
        resolution["preservation_checks"][0].update(
            status="passed",
            evidence="Runtime samples preserve every coefficient value and both selected symmetric indices.",
        )
        resolution["new_risk_checks"][0].update(
            status="passed",
            evidence="The final reconstructed curve remains stable for 1.40 seconds after the last update.",
        )
        resolution["status"] = "fixed"
        response["verdict"] = "repair_complete"
        self.assertEqual(pipeline.validate_repair_response_data(response, contract, current_manifest), [])
        explicitly_required = json.loads(json.dumps(contract))
        explicitly_required["findings"][0]["repair_guidance"]["required_changed_artifacts"] = ["live_policy"]
        explicitly_required.pop("contract_hash")
        explicitly_required["contract_hash"] = pipeline.object_hash(explicitly_required)
        explicitly_required_response = json.loads(json.dumps(response))
        explicitly_required_response["repair_contract_hash"] = explicitly_required["contract_hash"]
        self.assertTrue(
            any(
                "explicitly required artifacts were not updated: live_policy" in error
                for error in pipeline.validate_repair_response_data(
                    explicitly_required_response, explicitly_required, current_manifest
                )
            )
        )
        gate = pipeline.repair_gate_data(response, contract, current_manifest)
        self.assertTrue(gate["valid"])
        self.assertEqual(pipeline.validate_repair_gate_data(gate, response, contract, current_manifest), [])
        stale_contract = json.loads(json.dumps(contract))
        stale_contract["contract_hash"] = "0" * 64
        stale_gate = pipeline.repair_gate_data(response, stale_contract, current_manifest)
        self.assertFalse(stale_gate["valid"])
        self.assertIn("repair contract schema or hash is invalid", stale_gate["errors"])
        stale_contract_path = self.root / "stale-repair-contract.json"
        response_path = self.root / "repair-response.json"
        gate_path = self.root / "repair-gate.json"
        self.write_json(stale_contract_path, stale_contract)
        self.write_json(response_path, response)
        self.write_json(gate_path, gate)
        with self.assertRaisesRegex(
            pipeline.PipelineError, "contract schema or hash is invalid"
        ):
            pipeline.load_repair_bundle_for_self_review(
                SimpleNamespace(
                    repair_contract=str(stale_contract_path),
                    repair_response=str(response_path),
                    repair_gate=str(gate_path),
                    previous_author_self_review=None,
                ),
                review,
                current_manifest,
            )
        author_contract_path = self.root / "author-origin-contract.json"
        self.write_json(author_contract_path, author_contract)
        with self.assertRaisesRegex(
            pipeline.PipelineError, "cannot use an author-origin contract"
        ):
            pipeline.load_repair_bundle_for_self_review(
                SimpleNamespace(
                    repair_contract=str(author_contract_path),
                    repair_response=str(response_path),
                    repair_gate=str(gate_path),
                    previous_author_self_review=None,
                ),
                review,
                current_manifest,
            )
        direct_repair_self_review = {
            "schema": "lecture-animation-author-self-review-v2",
            "manifest_hash": current_manifest["manifest_hash"],
            "scene_slug": current_manifest["scene_slug"],
            "repair_context": {
                "previous_review_hash": pipeline.object_hash(review),
                "resolutions": [
                    {
                        "finding_id": finding["finding_id"],
                        "change": "The responsible transition now waits for the persistent carrier landing.",
                        "evidence_timestamps": [4.2],
                    }
                ],
            },
            "findings": [],
            "verdict": "ready_for_independent_review",
        }
        self.assertTrue(
            any(
                "contract, response, and gate must be supplied together" in error
                for error in pipeline.validate_author_self_review_data(
                    direct_repair_self_review,
                    current_manifest,
                    {"context": {"duration": 10.0}},
                    {},
                    previous_review=review,
                    require_hash=False,
                    repo_root=self.root,
                )
            )
        )
        parser = pipeline.build_parser()
        capsule_args = parser.parse_args(
            [
                "prepare-review-capsule",
                "--manifest", "manifest.json",
                "--author-self-review", "self-review.json",
                "--previous-review", "previous-review.json",
                "--repair-contract", "repair-contract.json",
                "--repair-response", "repair-response.json",
                "--repair-gate", "repair-gate.json",
                "--review-session", "session.json",
                "--output", "capsule.json",
            ]
        )
        self.assertEqual(capsule_args.previous_review, "previous-review.json")
        author_capsule_args = parser.parse_args(
            [
                "prepare-review-capsule",
                "--manifest", "manifest.json",
                "--author-self-review", "self-review.json",
                "--previous-author-self-review", "rejected-author-review.json",
                "--repair-contract", "author-repair-contract.json",
                "--repair-response", "repair-response.json",
                "--repair-gate", "repair-gate.json",
                "--review-session", "session.json",
                "--output", "capsule.json",
            ]
        )
        self.assertEqual(
            author_capsule_args.previous_author_self_review,
            "rejected-author-review.json",
        )
        author_contract_args = parser.parse_args(
            [
                "compile-author-repair-contract",
                "--repair-plan", "author-repair-plan.json",
                "--review-exhaustion", "review-exhaustion.json",
                "--author-self-review", "rejected-author-review.json",
                "--author-attempt-log", "author-attempts.jsonl",
                "--manifest", "manifest.json",
                "--output", "author-repair-contract.json",
            ]
        )
        self.assertEqual(
            author_contract_args.author_attempt_log,
            "author-attempts.jsonl",
        )
        self.assertEqual(
            author_contract_args.review_exhaustion,
            "review-exhaustion.json",
        )
        review_args = parser.parse_args(
            [
                "verify-review",
                "--manifest", "manifest.json",
                "--review", "review.json",
                "--author-self-review", "self-review.json",
                "--previous-review", "previous-review.json",
                "--repair-contract", "repair-contract.json",
                "--repair-response", "repair-response.json",
                "--repair-gate", "repair-gate.json",
                "--review-session", "session.json",
            ]
        )
        self.assertEqual(review_args.repair_gate, "repair-gate.json")

        broken = json.loads(json.dumps(response))
        broken["resolutions"][0]["new_risk_checks"][0]["evidence"] = ""
        self.assertTrue(
            any("new-risk" in error for error in pipeline.validate_repair_response_data(broken, contract, current_manifest))
        )

        unguided = json.loads(json.dumps(finding))
        unguided.pop("repair_guidance")
        self.assertTrue(pipeline.validate_repair_guidance(unguided, baseline_manifest))

    def test_phase_timer_and_iteration_snapshot_metrics(self) -> None:
        state_path = self.episode / "review" / "evolution" / "active_phase.json"
        phase_log = self.episode / "review" / "evolution" / "production_phases.jsonl"
        usage_path = self.episode / "review" / "evolution" / "usage.json"
        self.write_json(
            usage_path,
            {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 20, "reasoning_tokens": 5},
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_phase_start(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        efficiency_contract=str(
                            self.efficiency_contract
                        ),
                        run_id="run-1",
                        scene_slug="g002c_riemann_sum_limit",
                        phase="authoring",
                        actor_model="test-author-v1",
                        active_seconds_allocation=3_600,
                        raw_token_allocation=1_000,
                        uncached_input_token_allocation=500,
                        output_token_allocation=250,
                        reasoning_token_allocation=100,
                        usage_file=str(usage_path),
                        state=str(state_path),
                    )
                ),
                0,
            )
            self.write_json(
                usage_path,
                {"input_tokens": 350, "cached_input_tokens": 190, "output_tokens": 80, "reasoning_tokens": 25},
            )
            self.assertEqual(
                pipeline.command_phase_end(
                    SimpleNamespace(
                        state=str(state_path),
                        phase_log=str(phase_log),
                        result="completed",
                        manifest_hash="manifest-test",
                        usage_file=None,
                    )
                ),
                0,
            )
        rows = pipeline.event_rows(phase_log)
        central_rows = pipeline.event_rows(
            pipeline.episode_efficiency_central_log(
                pipeline.load_json(self.efficiency_contract)
            )
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(central_rows), 1)
        self.assertEqual(
            central_rows[0]["event_id"],
            rows[0]["event_id"],
        )
        self.assertEqual(rows[0]["phase"], "authoring")
        self.assertTrue(rows[0]["token_observed"])
        self.assertEqual(rows[0]["input_tokens"], 250)
        self.assertEqual(rows[0]["cached_input_tokens"], 150)
        self.assertEqual(rows[0]["output_tokens"], 60)
        self.assertEqual(rows[0]["reasoning_tokens"], 20)
        metrics = pipeline.production_metrics(self.episode)
        self.assertEqual(metrics["phase_events"], 1)
        self.assertTrue(metrics["observability"]["phase_timing_recorded"])
        self.assertEqual(metrics["observability"]["token_usage_coverage"], 1.0)
        self.assertEqual(metrics["phase_pair_scene_coverage"], 0.0)
        self.assertIn(
            "g002c_riemann_sum_limit",
            metrics["missing_phase_pairs_by_scene"],
        )

        shared_states = []
        for index, scene_slug in enumerate(
            ("g002c_riemann_sum_limit", "g002d_normalization"),
            start=1,
        ):
            shared_state = self.episode / "review" / "evolution" / f"{scene_slug}_shared.json"
            shared_states.append(shared_state)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    pipeline.command_phase_start(
                        SimpleNamespace(
                            repo_root=str(self.root),
                            episode=str(self.episode),
                            efficiency_contract=str(
                                self.efficiency_contract
                            ),
                            run_id=f"batch-shared-wrapper-{index}",
                            scene_slug=scene_slug,
                            phase="design",
                            phase_purpose=None,
                            actor_model="test-author-v1",
                            active_seconds_allocation=2_400,
                            raw_token_allocation=1_000,
                            uncached_input_token_allocation=500,
                            output_token_allocation=250,
                            reasoning_token_allocation=100,
                            actor_role="batch-designer",
                            reasoning_effort="high",
                            phase_instance_id=None,
                            shared_work_key="batch-spine-pass",
                            prompt_bytes=0,
                            artifact_input_bytes=0,
                            files_read=0,
                            usage_file=None,
                            state=str(shared_state),
                        )
                    ),
                    0,
                )
        shared_ids = {
            pipeline.load_json(path)["phase_instance_id"] for path in shared_states
        }
        accounting_ids = {
            pipeline.load_json(path)["accounting_identity"]
            for path in shared_states
        }
        self.assertEqual(len(shared_ids), 1)
        self.assertEqual(len(accounting_ids), 1)
        self.assertTrue(next(iter(shared_ids)).startswith("phase-instance:shared:"))
        ledger = pipeline.load_json(
            pipeline.episode_efficiency_reservation_ledger(
                pipeline.load_json(self.efficiency_contract)
            )
        )
        shared_reservations = [
            reservation
            for reservation in ledger["reservations"].values()
            if reservation.get("shared_work_key")
            == "batch-spine-pass"
        ]
        self.assertEqual(len(shared_reservations), 2)
        self.assertEqual(
            {
                reservation["accounting_identity"]
                for reservation in shared_reservations
            },
            accounting_ids,
        )
        self.assertTrue(
            all(
                reservation["shared_work_key"]
                == "batch-spine-pass"
                for reservation in shared_reservations
            )
        )
        self.assertEqual(
            pipeline.active_token_reservations(
                ledger,
                contract=pipeline.load_json(
                    self.efficiency_contract
                ),
            )["raw_input_plus_output_tokens"],
            1_000,
        )
        shared_identity = next(iter(accounting_ids))
        self.assertAlmostEqual(
            pipeline.projected_active_seconds(
                [],
                ledger,
                new_phase="design",
                new_phase_purpose="",
                new_started_at=pipeline.load_json(
                    shared_states[0]
                )["started_at"],
                new_active_seconds=2_400,
                contract=pipeline.load_json(
                    self.efficiency_contract
                ),
                new_accounting_identity=shared_identity,
            ),
            2_400.0,
            delta=1.0,
        )

    def test_episode_retrospective_reports_coverage_before_interpretation(self) -> None:
        supplement = {
            "schema": "lecture-animation-retrospective-supplement-v1",
            "evidence": {
                "reason": "test recovered evidence",
                "planned_scene_count": 1,
            },
        }
        supplement["supplement_hash"] = pipeline.object_hash(supplement)
        self.write_json(
            self.episode
            / "review"
            / "evolution"
            / "retrospective_supplement.json",
            supplement,
        )
        feedback_dir = self.episode / "review" / "human-feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)
        (feedback_dir / "real-feedback.md").write_text(
            "# Real feedback\n",
            encoding="utf-8",
        )
        (feedback_dir / "._real-feedback.md").write_text(
            "appledouble mirror",
            encoding="utf-8",
        )
        partial = pipeline.retrospective_evidence_data(self.root, self.episode)
        self.assertEqual(
            partial["schema"], "lecture-animation-episode-retrospective-v2"
        )
        self.assertEqual(partial["completion_status"], "partial")
        self.assertEqual(partial["issue_ledger"]["count"], 1)
        self.assertEqual(
            partial["issue_ledger"]["classification_coverage"][
                "pattern_key"
            ],
            1.0,
        )
        self.assertEqual(
            partial["issue_ledger"]["classification_coverage"][
                "standard_key"
            ],
            0.0,
        )
        self.assertEqual(partial["source_coverage"]["required_logs_observed"], 0)
        self.assertIsNone(
            partial["source_coverage"]["human_outcome_coverage"]
        )
        self.assertEqual(partial["feedback_count"], 1)
        self.assertEqual(
            partial["supplemental_production_evidence"][
                "planned_scene_count"
            ],
            1,
        )
        self.assertIn(
            "retrospective_supplement",
            partial["evidence_paths"],
        )
        self.assertFalse(
            any(
                "/._" in path
                for path in partial["evidence_paths"]["feedback"]
            )
        )
        self.assertGreater(
            len(partial["source_coverage"]["missing_sources"]), 0
        )
        self.assertTrue(
            partial["interpretation_contract"]["missing_is_not_zero"]
        )
        self.assertIsNone(partial["metrics"]["review_attempts"])
        self.assertIsNone(partial["metrics"]["scene_count"])
        self.assertIsNone(partial["metrics"]["outcome_events"])
        self.assertIsNone(partial["metrics"]["human_rejections"])
        self.assertIsNone(partial["metrics"]["false_passes"])
        self.assertIsNone(
            partial["coordination_summary"]["task_reopen_count"]
        )
        self.assertIsNone(
            partial["metrics"]["author_self_review_attempts"]
        )
        self.assertIsNone(partial["metrics"]["repair_attempts"])
        self.assertEqual(
            partial["efficiency_target"]["token_observation"][
                "observation_status"
            ],
            "unknown_no_token_telemetry",
        )
        self.assertIsNone(
            partial["efficiency_target"]["token_observation"]["observed"]
        )
        self.assertIsNone(
            partial["efficiency_target"]["token_observation"][
                "within_budget"
            ]
        )
        self.assertEqual(
            partial["screen_text_preregistration_experiment"]["comparison"][
                "status"
            ],
            "unknown_missing_current_instrumentation",
        )
        self.assertIsNone(
            partial["screen_text_preregistration_experiment"]["comparison"][
                "human_screen_text_escape_issue_delta"
            ]
        )
        self.assertEqual(
            partial["metrics"]["observability"][
                "ledger_metric_status"
            ]["review_attempts"],
            "unknown_missing_ledger",
        )
        self.assertTrue(
            pipeline.validate_hashed_record(partial, "retrospective_hash")
        )

        completion = {
            "schema": "lecture-animation-episode-completion-v2",
            "episode": self.episode.name,
            "created_at": "2026-07-24T00:00:00+00:00",
            "final_artifacts": {
                "final_video": {"sha256": "approved-v01-sha"},
            },
        }
        completion["completion_hash"] = pipeline.object_hash(completion)
        self.write_json(self.episode / "episode_completion.json", completion)
        output = self.episode / "review" / "evolution" / "postmortem.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_episode_retrospective(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        output=str(output),
                        require_finalized=True,
                    )
                ),
                0,
            )
        report = pipeline.load_json(output)
        self.assertEqual(report["completion_status"], "completion_receipt")
        self.assertTrue(
            pipeline.validate_hashed_record(report, "retrospective_hash")
        )

        # A later approved upload master is not finalized merely because an
        # older completion and portability receipt exist. Retrospective must
        # bind the current release lineage instead of accepting stale success.
        final_dir = self.episode / "exports" / "final" / "approved_v02"
        final_dir.mkdir(parents=True, exist_ok=True)
        self.write_json(
            final_dir / "approved_upload_master.json",
            {
                "schema": "lecture-animation-approved-upload-master-v2",
                "created_at": "2026-07-24T01:00:00+00:00",
                "approval_source": "user",
                "upload_mp4_sha256": "approved-v02-sha",
            },
        )
        portability = {
            "schema": "lecture-animation-portability-audit-v2",
            "created_at": "2026-07-24T00:30:00+00:00",
            "status": "pass",
            "required_artifacts": {
                "final_video": {"sha256": "approved-v01-sha"},
            },
        }
        portability["receipt_hash"] = pipeline.object_hash(portability)
        self.write_json(
            self.episode / "review" / "portability_v01.json",
            portability,
        )
        stale_report = pipeline.retrospective_evidence_data(
            self.root,
            self.episode,
        )
        self.assertEqual(
            stale_report["completion_status"],
            "stale_finalization_evidence_for_latest_master",
        )
        self.assertEqual(
            stale_report["finalization_lineage"][
                "latest_approved_master_video_sha256"
            ],
            "approved-v02-sha",
        )
        self.assertFalse(
            stale_report["finalization_lineage"][
                "completion_receipt_matches_latest_master"
            ]
        )
        self.assertFalse(
            stale_report["finalization_lineage"][
                "portability_receipt_matches_latest_master"
            ]
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_episode_retrospective(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        output=str(output),
                        require_finalized=True,
                    )
                ),
                2,
            )
        parser = pipeline.build_parser()
        parsed = parser.parse_args(
            [
                "episode-retrospective",
                "--episode",
                str(self.episode),
                "--output",
                str(output),
                "--require-finalized",
            ]
        )
        self.assertTrue(parsed.require_finalized)

    def test_episode_retrospective_legacy_completion_requires_old_master(self) -> None:
        final_dir = self.episode / "exports" / "final" / "approved_v01"
        final_dir.mkdir(parents=True, exist_ok=True)
        video = final_dir / "upload.mp4"
        video.write_bytes(b"legacy-video")
        approved = final_dir / "approved_upload_master.json"
        self.write_json(
            approved,
            {
                "schema": "lecture-animation-approved-upload-master-v2",
                "created_at": "2026-08-10T00:00:00+00:00",
                "approval_source": "user",
                "upload_mp4_sha256": "legacy-video-sha",
            },
        )
        portability = {
            "schema": "lecture-animation-portability-audit-v2",
            "created_at": "2026-08-10T00:01:00+00:00",
            "status": "pass",
            "required_artifacts": {
                "final_video": {"sha256": "legacy-video-sha"},
            },
        }
        portability["receipt_hash"] = pipeline.object_hash(portability)
        self.write_json(
            self.episode / "review" / "portability.json",
            portability,
        )
        current = pipeline.retrospective_evidence_data(self.root, self.episode)
        self.assertEqual(current["completion_status"], "partial")
        self.assertFalse(
            current["finalization_lineage"]["legacy_master_eligible"]
        )

        old = pipeline.load_json(approved)
        old["created_at"] = "2026-07-22T00:00:00+00:00"
        self.write_json(approved, old)
        legacy = pipeline.retrospective_evidence_data(self.root, self.episode)
        self.assertEqual(legacy["completion_status"], "legacy_approved_master")
        self.assertTrue(
            legacy["finalization_lineage"]["legacy_master_eligible"]
        )

    def test_episode_retrospective_discovers_nested_parallel_ledgers(self) -> None:
        nested = self.episode / "review" / "v2" / "batch_a" / "current"
        nested.mkdir(parents=True, exist_ok=True)
        rows = {
            "review_attempts.jsonl": {
                "schema": "lecture-animation-review-attempt-v2",
                "attempt_id": "nested-review-1",
                "verification_key": "nested-review-key-1",
                "scene_slug": "g001",
                "gate_accepted": True,
                "review_mode": "full_regression",
                "reviewer_agent_id": "reviewer-b",
                "findings_count": 1,
            },
            "author_self_review_attempts.jsonl": {
                "schema": "lecture-animation-author-self-review-attempt-v2",
                "attempt_id": "nested-self-1",
                "verification_key": "nested-self-key-1",
                "scene_slug": "g001",
                "manifest_hash": "manifest-1",
                "gate_accepted": True,
            },
            "production_phases.jsonl": {
                "schema": "lecture-animation-phase-event-v2",
                "event_id": "nested-phase-1",
                "phase_instance_id": "nested-phase-instance-1",
                "scene_slug": "g001",
                "phase": "design",
                "result": "completed",
                "started_at": "2026-07-24T00:00:00+00:00",
                "ended_at": "2026-07-24T00:01:00+00:00",
                "duration_seconds": 60.0,
                "token_observed": False,
            },
            "repair_attempts.jsonl": {
                "schema": "lecture-animation-repair-attempt-v2",
                "attempt_id": "nested-repair-1",
                "verification_key": "nested-repair-key-1",
                "scene_slug": "g001",
                "gate_accepted": True,
            },
        }
        for name, row in rows.items():
            (nested / name).write_text(
                json.dumps(row) + "\n", encoding="utf-8"
            )
        # A copied row in another ledger must not inflate the counts.
        duplicate = self.episode / "review" / "v2" / "batch_b"
        duplicate.mkdir(parents=True, exist_ok=True)
        (duplicate / "review_attempts.jsonl").write_text(
            json.dumps(rows["review_attempts.jsonl"]) + "\n",
            encoding="utf-8",
        )

        report = pipeline.retrospective_evidence_data(self.root, self.episode)
        self.assertEqual(report["metrics"]["scene_count"], 1)
        self.assertEqual(report["metrics"]["review_attempts"], 1)
        self.assertEqual(report["metrics"]["author_self_review_attempts"], 1)
        self.assertEqual(report["metrics"]["repair_attempts"], 1)
        self.assertEqual(report["metrics"]["phase_events"], 1)
        self.assertTrue(report["source_coverage"]["repair_log_observed"])
        self.assertEqual(report["source_coverage"]["required_logs_observed"], 3)
        self.assertIn(
            "review_attempts",
            report["evidence_paths"]["required_logs_observed"],
        )

    def test_episode_retrospective_counts_time_governed_phase_events(self) -> None:
        evolution = self.episode / "review" / "evolution"
        evolution.mkdir(parents=True, exist_ok=True)
        time_governed_phase = {
            "schema": "lecture-animation-time-governed-phase-event-v1",
            "event_id": "time-governed-phase-1",
            "phase_instance_id": "time-governed-phase-instance-1",
            "scene_slug": "g001",
            "phase": "authoring",
            "result": "completed",
            "started_at": "2026-07-24T00:00:00+00:00",
            "ended_at": "2026-07-24T00:02:00+00:00",
            "duration_seconds": 120.0,
            "input_tokens": 100,
            "cached_input_tokens": 80,
            "output_tokens": 20,
            "reasoning_tokens": 10,
            "token_observed": True,
        }
        (evolution / "episode_time_governed_phase_events.jsonl").write_text(
            json.dumps(time_governed_phase) + "\n",
            encoding="utf-8",
        )

        report = pipeline.retrospective_evidence_data(self.root, self.episode)

        self.assertEqual(report["metrics"]["phase_events"], 1)
        self.assertEqual(
            report["metrics"]["phase_agent_seconds"]["authoring"],
            120.0,
        )
        self.assertEqual(
            report["metrics"]["token_usage"]["output_tokens"],
            20,
        )
        self.assertTrue(
            report["metrics"]["observability"]["phase_timing_recorded"]
        )

    def test_same_episode_iteration_comparison_is_tooling_only(self) -> None:
        before = {
            "schema": "lecture-animation-skill-iteration-snapshot-v2",
            "episode": self.episode.name,
            "metrics": {
                "human_rejection_rate": 0.1,
                "false_pass_rate": 0.1,
                "average_findings_per_attempt": 1.0,
                "review_attempts_per_scene": 1.0,
                "review_mp4_per_scene": 1.0,
                "reviewer_switches": 0,
                "total_measured_minutes": 10.0,
                "observability": {
                    "human_outcomes_recorded": True,
                    "phase_timing_recorded": True,
                    "review_sessions_recorded": False,
                    "token_usage_coverage": 0.5,
                },
            },
        }
        before["snapshot_hash"] = pipeline.object_hash(before)
        after = json.loads(json.dumps(before))
        after.pop("snapshot_hash")
        after["metrics"]["human_rejection_rate"] = 0.2
        after["metrics"]["total_measured_minutes"] = 20.0
        after["metrics"]["observability"]["token_usage_coverage"] = 1.0
        after["snapshot_hash"] = pipeline.object_hash(after)
        before_path = self.root / "before-snapshot.json"
        after_path = self.root / "after-snapshot.json"
        output_path = self.root / "comparison.json"
        self.write_json(before_path, before)
        self.write_json(after_path, after)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_compare_iterations(
                    SimpleNamespace(
                        before=str(before_path),
                        after=str(after_path),
                        output=str(output_path),
                    )
                ),
                0,
            )
        comparison = pipeline.load_json(output_path)
        self.assertEqual(
            comparison["comparison_scope"],
            "same_episode_tooling_only",
        )
        self.assertFalse(comparison["production_window_comparable"])
        self.assertEqual(
            comparison["quality"]["verdict"],
            "insufficient_data",
        )
        self.assertEqual(
            comparison["efficiency"]["verdict"],
            "insufficient_data",
        )
        self.assertEqual(
            comparison["efficiency"]["deltas"]["total_measured_minutes"],
            10.0,
        )

    def test_reviewer_assisted_repair_requires_recusal_and_fresh_verifier(
        self,
    ) -> None:
        contract = {
            "schema": "lecture-animation-repair-contract-v2",
            "repair_execution_contract_version": 1,
            "reviewer_agent_id": "discovery-reviewer",
        }
        valid = pipeline.repair_execution_data(
            contract,
            mode="reviewer_assisted",
            repair_actor_agent_id="discovery-reviewer",
            planned_verifier_agent_id="fresh-verifier",
            handoff_count=0,
        )
        self.assertEqual(
            pipeline.validate_repair_execution_data(valid, contract),
            [],
        )

        same_reviewer = pipeline.repair_execution_data(
            contract,
            mode="reviewer_assisted",
            repair_actor_agent_id="discovery-reviewer",
            planned_verifier_agent_id="discovery-reviewer",
            handoff_count=0,
        )
        self.assertTrue(
            any(
                "repair actor is recused" in error
                for error in pipeline.validate_repair_execution_data(
                    same_reviewer,
                    contract,
                )
            )
        )

        disguised = pipeline.repair_execution_data(
            contract,
            mode="same_author",
            repair_actor_agent_id="discovery-reviewer",
            planned_verifier_agent_id="fresh-verifier",
            handoff_count=1,
        )
        self.assertTrue(
            any(
                "must use reviewer_assisted mode" in error
                for error in pipeline.validate_repair_execution_data(
                    disguised,
                    contract,
                )
            )
        )

    def test_design_readiness_blocks_expensive_production_until_animatic_is_frozen(self) -> None:
        profile = self.make_profile()
        bundle = self.make_design_bundle(profile)
        plan = self.make_plan(profile, bundle)
        authoring_qc = pipeline.validate_authoring_qc_data(
            profile, plan, self.make_telemetry(profile)
        )
        self.assertTrue(authoring_qc["valid"], authoring_qc["issues"])
        animatic = self.episode / "review" / "v2" / "animatic.mp4"
        animatic.parent.mkdir(parents=True, exist_ok=True)
        animatic.write_bytes(b"low-cost-animatic")
        animatic_sha = pipeline.artifact_snapshot(animatic, self.root)["sha256"]
        readiness = pipeline.design_readiness_draft_data(
            profile, plan, bundle[2], authoring_qc, animatic, animatic_sha
        )
        readiness["continuous_playback"] = {
            "performed": True,
            "observation": "The complete animatic preserves the selected cell and formula ancestry.",
        }
        readiness["muted_playback"] = {
            "performed": True,
            "teach_back": "The selected cell gains width and the refined cells become an integral.",
            "driver_prediction": "Increasing L narrows every frequency cell while preserving the density curve.",
        }
        for item in readiness["stage_state_checks"]:
            item.update(
                timestamp_seconds=1.0,
                visible_object_ids=["frequency_cells"],
                observation="The declared stage state uses its reserved region without subtitle intrusion.",
                passed=True,
            )
        for item in readiness["transition_checks"]:
            item.update(
                timestamp_seconds=4.825,
                continuity_observation="The selected cell remains the same object through the stage promotion.",
                passed=True,
            )
        readiness["formula_memory_check"] = {
            "performed": True,
            "simultaneous_rows": 3,
            "single_slot_only": False,
            "observation": "The finite sum, selected contribution, and integral ancestry remain visible together.",
        }
        readiness["design_frozen"] = True
        readiness["verdict"] = "ready_for_audio_lock"
        readiness["readiness_hash"] = pipeline.object_hash(readiness)
        self.assertEqual(
            pipeline.validate_design_readiness_data(
                readiness,
                profile,
                plan,
                bundle[2],
                authoring_qc,
                animatic_path=animatic,
                animatic_sha256=animatic_sha,
            ),
            [],
        )
        readiness_path = animatic.with_name("design_readiness.json")
        self.write_json(readiness_path, readiness)
        narration = animatic.with_name("narration.txt")
        narration.write_text(
            "先看有限格点如何变密。连续极限留下了哪一个积分对象？",
            encoding="utf-8",
        )
        episode_scene_source = self.episode / "src" / "episode_scene.py"
        episode_scene_source.parent.mkdir(exist_ok=True)
        episode_scene_source.write_text("from manim import *\n", encoding="utf-8")
        episode_screen_text_semantics = animatic.with_name(
            "episode_screen_text_semantic_contract.json"
        )
        self.write_json(
            episode_screen_text_semantics,
            {
                "schema": "lecture-animation-screen-text-semantic-contract-v1",
                "semantic_items": [],
            },
        )
        episode_contract = animatic.with_name("episode_readiness_contract.json")
        self.write_json(
            episode_contract,
            {
                "schema": "lecture-animation-episode-readiness-v2",
                "author_id": "author-test",
                "fixed_ending": "连续极限留下了哪一个积分对象？",
                "fixed_ending_contract": {
                    "role": "learner_facing_math_question",
                    "learner_job": "Leave one exact question about the resulting continuous object.",
                    "math_anchor": "continuous integral limit",
                    "externalizes_production_intent": False,
                },
                "scenes": [
                    {
                        "scene_slug": "g002c_riemann_sum_limit",
                        "scene_source_path": pipeline.relative_or_absolute(
                            episode_scene_source, self.root
                        ),
                        "scene_source_root": pipeline.relative_or_absolute(
                            episode_scene_source.parent, self.root
                        ),
                        "narration_path": pipeline.relative_or_absolute(narration, self.root),
                        "duration_seconds": 12.0,
                        "screen_text_semantic_contract_path": (
                            pipeline.relative_or_absolute(
                                episode_screen_text_semantics, self.root
                            )
                        ),
                    }
                ],
            },
        )
        episode_readiness = animatic.with_name("episode_readiness_receipt.json")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_episode_preflight(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        contract=str(episode_contract),
                        output=str(episode_readiness),
                        require_clean=True,
                    )
                ),
                0,
            )
        with self.assertRaisesRegex(Exception, "design-readiness"):
            pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(self.episode),
                    efficiency_contract=str(
                        self.efficiency_contract
                    ),
                    run_id="run-tts",
                    scene_slug="g002c_riemann_sum_limit",
                    phase="tts",
                    phase_purpose="initial",
                    episode_readiness=str(episode_readiness),
                    design_readiness=None,
                    actor_model="tts-worker",
                    active_seconds_allocation=1_200,
                    raw_token_allocation=1_000,
                    uncached_input_token_allocation=500,
                    output_token_allocation=250,
                    reasoning_token_allocation=100,
                    state=str(animatic.with_name("tts-state-missing.json")),
                )
            )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(self.episode),
                    efficiency_contract=str(
                        self.efficiency_contract
                    ),
                    run_id="run-tts",
                        scene_slug="g002c_riemann_sum_limit",
                        phase="tts",
                        phase_purpose="initial",
                        episode_readiness=str(episode_readiness),
                        design_readiness=str(readiness_path),
                        actor_model="tts-worker",
                        active_seconds_allocation=1_200,
                        raw_token_allocation=1_000,
                        uncached_input_token_allocation=500,
                        output_token_allocation=250,
                        reasoning_token_allocation=100,
                        state=str(animatic.with_name("tts-state.json")),
                    )
                ),
                0,
            )

    def test_keyframe_probe_cannot_replace_complete_visual_plan(self) -> None:
        profile = self.make_profile()
        bundle = self.make_design_bundle(profile)
        plan = self.make_plan(profile, bundle)
        plan_path = self.episode / "review" / "v2" / "scene_plan.json"
        self.write_json(plan_path, plan)
        artifact_paths = {
            "profile": self.episode / "review" / "v2" / "profile.json",
            "plan": plan_path,
            "challenge": self.episode / "review" / "v2" / "challenge.json",
            "deliberation": self.episode / "review" / "v2" / "deliberation.json",
            "design_gate": self.episode / "review" / "v2" / "design_gate.json",
            "precedent_packet": self.episode / "review" / "v2" / "precedent.json",
            "episode_spine": self.episode / "review" / "v2" / "spine.json",
            "batch_plan": self.episode / "review" / "v2" / "batch.json",
        }
        for key, path in artifact_paths.items():
            if key == "plan":
                continue
            self.write_json(path, {"artifact": key})
        validation = {
            "schema": "lecture-animation-scene-plan-validation-v1",
            "valid": True,
            "errors": [],
            "scene_slug": plan["scene_slug"],
            "profile_hash": profile["profile_hash"],
            "plan_hash": pipeline.object_hash(plan),
            "artifacts": {
                key: pipeline.artifact_snapshot(path, self.root)
                for key, path in artifact_paths.items()
            },
        }
        validation["validation_hash"] = pipeline.object_hash(validation)
        validation_path = plan_path.with_name("scene_plan_validation.json")
        self.write_json(validation_path, validation)
        validation_binding = pipeline.artifact_snapshot(validation_path, self.root)
        scene_production = {
            "schema": "lecture-animation-scene-production-v2",
            "scene_slug": plan["scene_slug"],
            "state": "audio_aligned",
        }
        scene_production["scene_production_hash"] = pipeline.object_hash(
            scene_production
        )
        scene_production_path = plan_path.with_name("scene_production.json")
        self.write_json(scene_production_path, scene_production)
        scene_production_binding = pipeline.artifact_snapshot(
            scene_production_path,
            self.root,
        )
        keyframe_path = plan_path.with_name("risky_transition_keyframe.png")
        keyframe_path.write_bytes(b"not-a-real-png-but-hash-bound-test-evidence")
        probe_evidence = [
            {
                "kind": "keyframe",
                "artifact": pipeline.artifact_snapshot(keyframe_path, self.root),
            }
        ]

        draft = pipeline.visual_plan_review_draft_data(
            plan,
            scene_plan_validation=validation,
            validation_binding=validation_binding,
            scene_production=scene_production,
            scene_production_binding=scene_production_binding,
            author_agent_id="plan-author",
            reviewer="independent-plan-reviewer",
            reviewer_model="frontier-reviewer",
            reasoning_effort="xhigh",
            reviewer_agent_id="plan-reviewer-session",
            probe_evidence=probe_evidence,
        )
        draft["probe_evidence"][0]["purpose"] = (
            "Inspect the riskiest transition midpoint for hierarchy and clearance."
        )
        draft["probe_evidence"][0]["plan_section_ids"] = [
            "transition:state_1->state_2"
        ]
        incomplete_errors = pipeline.validate_visual_plan_review_data(
            draft,
            plan,
            scene_plan_validation=validation,
            validation_binding=validation_binding,
            scene_production=scene_production,
            scene_production_binding=scene_production_binding,
            current_probe_evidence=probe_evidence,
            require_hash=False,
        )
        self.assertTrue(
            any("complete detailed plan" in error for error in incomplete_errors)
        )

        for item in draft["plan_completeness_checks"]:
            item["status"] = "pass"
            item["observation"] = (
                "The detailed plan names concrete objects, stage ownership, and executable evidence."
            )
        for item in draft["quality_dimension_checks"]:
            item["status"] = "pass"
            item["observation"] = (
                "The reviewer traced this dimension through the learner task and visible causal chain."
            )
        for item in draft["stage_state_checks"]:
            item.update(
                layout_and_focus_observation=(
                    "The primary object owns the declared region and the eye has one unambiguous target."
                ),
                learner_task_and_evidence_observation=(
                    "The learner task is supported by visible evidence before the corresponding inference."
                ),
                passed=True,
            )
        for item in draft["transition_checks"]:
            item.update(
                causal_trigger_observation=(
                    "The mathematical question makes the old allocation insufficient and triggers the move."
                ),
                identity_clearance_handoff_observation=(
                    "The identity carrier persists, stale objects clear, and the next focal region settles."
                ),
                passed=True,
            )
        draft["detailed_plan_complete"] = True
        draft["verdict"] = "ready_for_animation_production"
        self.assertEqual(
            pipeline.validate_visual_plan_review_data(
                draft,
                plan,
                scene_plan_validation=validation,
                validation_binding=validation_binding,
                scene_production=scene_production,
                scene_production_binding=scene_production_binding,
                current_probe_evidence=probe_evidence,
                require_hash=False,
            ),
            [],
        )
        duplicated = json.loads(json.dumps(draft))
        duplicated["plan_completeness_checks"].append(
            dict(duplicated["plan_completeness_checks"][0])
        )
        duplicate_errors = pipeline.validate_visual_plan_review_data(
            duplicated,
            plan,
            scene_plan_validation=validation,
            validation_binding=validation_binding,
            scene_production=scene_production,
            scene_production_binding=scene_production_binding,
            current_probe_evidence=probe_evidence,
            require_hash=False,
        )
        self.assertTrue(
            any("exactly once" in error for error in duplicate_errors)
        )
        sealed = dict(draft)
        sealed["review_hash"] = pipeline.object_hash(sealed)
        self.assertEqual(
            pipeline.validate_visual_plan_review_data(
                sealed,
                plan,
                scene_plan_validation=validation,
                validation_binding=validation_binding,
                scene_production=scene_production,
                scene_production_binding=scene_production_binding,
                current_probe_evidence=probe_evidence,
                require_hash=True,
            ),
            [],
        )

    def test_workflow_v2_blocks_animation_before_visual_plan_review(self) -> None:
        contract = pipeline.episode_efficiency_contract_data(
            self.root,
            self.episode,
            SimpleNamespace(
                workflow_gate_version=2,
                episode_target_hours=8.0,
                retrospective_reserve_minutes=45.0,
                raw_token_budget=50_000_000,
                uncached_input_token_budget=2_000_000,
                output_token_budget=300_000,
                reasoning_token_budget=100_000,
                token_budget_warning_fraction=0.75,
                max_false_passes=0,
                max_known_regression_recurrences=0,
                max_human_issue_scene_rate=0.25,
            ),
        )
        self.write_json(self.efficiency_contract, contract)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "requires --visual-plan-review",
        ):
            pipeline.command_phase_start(
                SimpleNamespace(
                    repo_root=str(self.root),
                    episode=str(self.episode),
                    efficiency_contract=str(self.efficiency_contract),
                    run_id="premature-animation",
                    scene_slug="g002c_riemann_sum_limit",
                    phase="authoring",
                    phase_purpose="final_animation",
                    actor_model="animation-author",
                    active_seconds_allocation=60,
                    raw_token_allocation=1,
                    uncached_input_token_allocation=0,
                    output_token_allocation=0,
                    reasoning_token_allocation=0,
                    state=str(self.episode / "premature-animation.json"),
                )
            )

    def test_retrospective_measures_visual_plan_gate_and_probe_backed_revise(self) -> None:
        central_log = pipeline.episode_efficiency_central_log(
            pipeline.load_json(self.efficiency_contract)
        )
        pipeline.append_jsonl(
            central_log,
            {
                "schema": "lecture-animation-phase-event-v2",
                "event_id": "phase:v2-plan-gated-authoring",
                "run_id": "v2-plan-gated-authoring",
                "phase_instance_id": "phase-instance:v2-plan-gated-authoring",
                "scene_slug": "g002c_riemann_sum_limit",
                "phase": "authoring",
                "phase_purpose": "final_animation",
                "workflow_gate_version": 2,
                "visual_plan_review_hash": "review-hash",
                "visual_plan_review_scene_production_hash": "scene-audio-hash",
                "scene_production_hash": "scene-audio-hash",
                "started_at": "2026-08-01T00:00:00+00:00",
                "ended_at": "2026-08-01T00:01:00+00:00",
                "duration_seconds": 60.0,
                "result": "completed",
                "token_observed": False,
            },
        )
        attempts_path = (
            self.episode
            / "review"
            / "v2"
            / "g002c_riemann_sum_limit"
            / "visual_plan_review_attempts.jsonl"
        )
        pipeline.append_jsonl(
            attempts_path,
            {
                "schema": "lecture-animation-visual-plan-review-attempt-v1",
                "attempt_id": "visual-plan-review:first-revise",
                "attempted_at": "2026-08-01T00:00:00+00:00",
                "scene_slug": "g002c_riemann_sum_limit",
                "probe_count": 1,
                "detailed_plan_complete": False,
                "gate_result": "revise",
                "error_count": 3,
            },
        )
        pipeline.append_jsonl(
            attempts_path,
            {
                "schema": "lecture-animation-visual-plan-review-attempt-v1",
                "attempt_id": "visual-plan-review:second-pass",
                "attempted_at": "2026-08-01T00:01:00+00:00",
                "scene_slug": "g002c_riemann_sum_limit",
                "probe_count": 1,
                "detailed_plan_complete": True,
                "gate_result": "pass",
                "error_count": 0,
            },
        )

        metrics = pipeline.production_metrics(self.episode)
        self.assertEqual(metrics["visual_plan_review_attempts"], 2)
        self.assertEqual(metrics["visual_plan_review_revise_attempts"], 1)
        self.assertEqual(
            metrics["visual_plan_review_findings_caught_before_animation"],
            3,
        )
        self.assertEqual(
            metrics["visual_plan_review_probe_backed_revise_attempts"],
            1,
        )
        self.assertEqual(metrics["visual_plan_review_first_attempt_passes"], 0)
        self.assertEqual(
            metrics["visual_plan_review_probe_substitution_false_passes"],
            0,
        )
        self.assertEqual(
            metrics["workflow_v2_visual_plan_gate_event_coverage"],
            1.0,
        )
        self.assertEqual(
            metrics["workflow_v2_visual_plan_gate_scene_coverage"],
            1.0,
        )
        self.assertEqual(
            metrics["workflow_v2_visual_plan_attempt_log_scene_coverage"],
            1.0,
        )
        self.assertEqual(
            metrics["workflow_v2_visual_plan_gate_missing_event_ids"],
            [],
        )

    def test_progressive_scene_audio_contract_and_execution_registry(self) -> None:
        notes = self.episode / "lecture-notes.md"
        outline = self.episode / "script-outline.md"
        script = self.episode / "scenes" / "g002c" / "script.md"
        audio = self.episode / "scenes" / "g002c" / "audio.wav"
        reader_srt = self.episode / "scenes" / "g002c" / "reader.srt"
        word_srt = self.episode / "scenes" / "g002c" / "words.srt"
        word_alignment = self.episode / "scenes" / "g002c" / "words.json"
        timeline_fragment = self.episode / "scenes" / "g002c" / "timeline.json"
        asr_transcript = self.episode / "scenes" / "g002c" / "asr.txt"
        narration_qc_draft = self.episode / "scenes" / "g002c" / "narration_qc_draft.json"
        narration_qc = self.episode / "scenes" / "g002c" / "narration_qc.json"
        episode_spine = self.episode / "episode_visual_spine.json"
        notes.write_text("Fourier transform lecture notes with the complete mathematical argument.\n", encoding="utf-8")
        outline.write_text("Coarse narration outline; individual scene wording remains provisional.\n", encoding="utf-8")
        script.parent.mkdir(parents=True)
        script.write_text("Frequency samples acquire widths and become interval contributions.\n", encoding="utf-8")
        with wave.open(str(audio), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(b"\x00\x00" * 16000)
        reader_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nFrequency samples acquire widths.\n", encoding="utf-8")
        word_srt.write_text("1\n00:00:00,000 --> 00:00:00,900\nFrequency samples acquire widths\n", encoding="utf-8")
        self.write_json(word_alignment, {"words": [{"word": "Frequency", "start": 0.0, "end": 0.9}]})
        self.write_json(timeline_fragment, {"scene_slug": "g002c_riemann_sum_limit", "duration_seconds": 1.0})
        asr_transcript.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")
        spine_data = {
            "schema": "lecture-animation-episode-visual-spine-v2",
            "episode": pipeline.relative_or_absolute(self.episode, self.root),
            "narration_style_contract": self.narration_style_contract(),
        }
        spine_data["spine_hash"] = pipeline.object_hash(spine_data)
        self.write_json(episode_spine, spine_data)
        self.write_json(
            narration_qc_draft,
            {
                "author_self_review": {
                    "perspective": "novice_audio_only",
                    "verdict": "pass",
                    "teach_back": "Frequency samples become contributions only after each sample receives an interval width.",
                    "likely_confusion": "A beginner may mistake the sample height itself for the full interval contribution.",
                    "style_compliance": "The sentence gives the visible reason before naming the resulting contribution.",
                    "claim_responsibility": "The interval width, not an unexplained formula change, causes the contribution.",
                },
                "audio_listening_review": {
                    "full_playback": True,
                    "natural_pacing": True,
                    "no_clipped_syllables": True,
                    "no_unedited_gaps": True,
                    "pronunciation_verified": True,
                    "verdict": "pass",
                    "observation": "The complete one-second test audio remains bounded and contains no clipped ending.",
                },
                "timeline_alignment_review": {
                    "word_level_checked": True,
                    "clause_anchors_checked": True,
                    "reader_subtitles_checked": True,
                    "math_terms_checked": True,
                    "max_anchor_drift_seconds": 0.1,
                    "verdict": "pass",
                    "observation": "All subtitle and word endpoints remain within the one-second audio contract.",
                },
            },
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_seal_narration_qc(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode_spine=str(episode_spine),
                        scene_slug="g002c_riemann_sum_limit",
                        script=str(script),
                        audio=str(audio),
                        reader_srt=str(reader_srt),
                        word_srt=str(word_srt),
                        word_alignment=str(word_alignment),
                        timeline_fragment=str(timeline_fragment),
                        asr_transcript=str(asr_transcript),
                        review_draft=str(narration_qc_draft),
                        output=str(narration_qc),
                    )
                ),
                0,
            )
        sealed_narration_qc = pipeline.load_json(narration_qc)
        self.assertEqual(
            pipeline.validate_narration_qc_data(sealed_narration_qc, self.root, "g002c_riemann_sum_limit"),
            [],
        )
        original_mtime = reader_srt.stat().st_mtime_ns
        os.utime(reader_srt, ns=(original_mtime + 1_000_000_000, original_mtime + 1_000_000_000))
        self.assertEqual(
            pipeline.validate_narration_qc_data(sealed_narration_qc, self.root, "g002c_riemann_sum_limit"),
            [],
        )
        asr_transcript.write_text("Frequency samples become unrelated values.\n", encoding="utf-8")
        self.assertTrue(
            any(
                "asr_transcript" in error or "ASR transcript" in error
                for error in pipeline.validate_narration_qc_data(
                    sealed_narration_qc,
                    self.root,
                    "g002c_riemann_sum_limit",
                )
            )
        )
        asr_transcript.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")

        initialized_path = self.episode / "progressive_initialized.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_init_progressive_production(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        episode=str(self.episode),
                        lecture_notes=pipeline.relative_or_absolute(notes, self.root),
                        narration_outline=pipeline.relative_or_absolute(outline, self.root),
                        storyboard=pipeline.relative_or_absolute(self.episode / "storyboard.md", self.root),
                        output=str(initialized_path),
                    )
                ),
                0,
            )
        initialized = pipeline.load_json(initialized_path)
        self.assertEqual(len(initialized["scenes"]), 3)
        self.assertTrue(all(row["state"] == "provisional" for row in initialized["scenes"]))

        production_path = self.episode / "progressive_production.json"
        production_source = {
            "schema": "lecture-animation-progressive-production-v2",
            "episode": pipeline.relative_or_absolute(self.episode, self.root),
            "lecture_notes": {"path": pipeline.relative_or_absolute(notes, self.root)},
            "narration_outline": {
                "path": pipeline.relative_or_absolute(outline, self.root),
                "status": "outline_draft",
            },
            "storyboard": {
                "path": pipeline.relative_or_absolute(self.episode / "storyboard.md", self.root),
                "status": "coarse",
            },
            "scenes": [
                {
                    "scene_slug": "g002c_riemann_sum_limit",
                    "state": "audio_aligned",
                    "narration_intent": "Show samples becoming interval contributions before the integral notation appears.",
                    "duration_seconds": 1.0,
                    "artifacts": {
                        "script": {"path": pipeline.relative_or_absolute(script, self.root)},
                        "audio": {"path": pipeline.relative_or_absolute(audio, self.root)},
                        "reader_srt": {"path": pipeline.relative_or_absolute(reader_srt, self.root)},
                        "word_srt": {"path": pipeline.relative_or_absolute(word_srt, self.root)},
                        "word_alignment": {"path": pipeline.relative_or_absolute(word_alignment, self.root)},
                        "timeline_fragment": {"path": pipeline.relative_or_absolute(timeline_fragment, self.root)},
                        "asr_transcript": {"path": pipeline.relative_or_absolute(asr_transcript, self.root)},
                        "narration_qc": {"path": pipeline.relative_or_absolute(narration_qc, self.root)},
                    },
                }
            ],
            "assembly": {"status": "pending", "artifacts": {}},
        }
        self.write_json(production_path, production_source)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_seal_progressive_production(
                    SimpleNamespace(repo_root=str(self.root), input=str(production_path), output=None)
                ),
                0,
            )
        production = pipeline.load_json(production_path)
        self.assertEqual(pipeline.validate_progressive_production_data(production, self.root, self.episode), [])

        scene_production_path = self.episode / "scene_production.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_extract_scene_production(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        production=str(production_path),
                        scene_slug="g002c_riemann_sum_limit",
                        output=str(scene_production_path),
                    )
                ),
                0,
            )
        scene_production = pipeline.load_json(scene_production_path)
        self.assertTrue(pipeline.validate_hashed_record(scene_production, "scene_production_hash"))

        profile = self.make_profile()
        plan = self.make_plan(profile, self.make_design_bundle(profile))
        registry = pipeline.scene_registry_data(profile, plan, scene_production)
        self.assertTrue(pipeline.validate_hashed_record(registry, "registry_hash"))
        self.assertEqual(registry["exact_media"]["word_alignment"]["sha256"], pipeline.artifact_snapshot(word_alignment, self.root)["sha256"])
        expected_state_ids = [item.get("state_id") or item.get("id") for item in plan.get("stage_states", [])]
        self.assertEqual(registry["stage_state_ids"], expected_state_ids)
        self.assertTrue(all(registry["stage_state_ids"]))
        expected_transition_ids = []
        for index, item in enumerate(plan.get("stage_transitions", [])):
            transition_id = item.get("transition_id") or item.get("id")
            if not transition_id:
                from_state = str(item.get("from_state", "")).strip()
                to_state = str(item.get("to_state", "")).strip()
                transition_id = f"{from_state}->{to_state}" if from_state and to_state else f"transition-{index + 1:02d}"
            expected_transition_ids.append(transition_id)
        self.assertEqual(registry["stage_transition_ids"], expected_transition_ids)
        self.assertTrue(all(registry["stage_transition_ids"]))

        production["scenes"][0]["state"] = "designing"
        production.pop("production_hash", None)
        production["production_hash"] = pipeline.object_hash(production)
        with self.assertRaises(pipeline.PipelineError):
            pipeline.scene_production_contract_data(production, "g002c_riemann_sum_limit")

    def test_exact_screen_text_inventory_blocks_explanatory_text_growth(self) -> None:
        source = self.episode / "src" / "scenes" / "g002c_riemann_sum_limit"
        source.mkdir(parents=True, exist_ok=True)
        candidate = source / "composer.py"
        candidate.write_text(
            "from manim import *\n"
            "formula = MathTex(r'x^2')\n"
            "label = Text('取样')\n",
            encoding="utf-8",
        )
        baseline_path = self.episode / "review" / "text_baseline.json"
        audit_path = self.episode / "review" / "text_audit.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_freeze_text_inventory(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        scene_slug="g002c_riemann_sum_limit",
                        baseline_label="approved-v1",
                        source=str(source),
                        output=str(baseline_path),
                    )
                ),
                0,
            )
            self.assertEqual(
                pipeline.command_verify_text_inventory(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        scene_slug="g002c_riemann_sum_limit",
                        source=str(source),
                        baseline=str(baseline_path),
                        output=str(audit_path),
                    )
                ),
                0,
            )
        candidate.write_text(
            candidate.read_text(encoding="utf-8") + "explanation = Text('为了帮助观众理解')\n",
            encoding="utf-8",
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_verify_text_inventory(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        scene_slug="g002c_riemann_sum_limit",
                        source=str(source),
                        baseline=str(baseline_path),
                        output=str(audit_path),
                    )
                ),
                2,
            )
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        self.assertFalse(audit["valid"])
        self.assertIn("screen text inventory changed: constructor_counts", audit["errors"])

    def test_narrated_transform_requires_word_locked_measured_motion(self) -> None:
        base_profile = self.make_profile()
        policy = pipeline.compile_live_policy_data(self.episode, base_profile)
        policy_path = self.episode / "review" / "v2" / "action_policy.json"
        self.write_json(policy_path, policy)
        profile = pipeline.attach_autopilot_contract(
            base_profile,
            policy,
            policy_path,
            self.root,
        )
        profile["context"]["narration"] = "它能旋转、等比例伸缩。"
        profile.pop("profile_hash", None)
        profile["profile_hash"] = pipeline.object_hash(profile)
        plan = self.make_plan(profile, self.make_design_bundle(profile))
        plan["timing_contract_version"] = "word_anchor_v1"
        plan["word_alignment_source"] = {
            "path": "alignment.json",
            "sha256": "a" * 64,
            "scene_start": 0.0,
        }
        plan["word_anchors"] = [
            {
                "anchor_id": "context-word",
                "token": "它",
                "absolute_start": 0.2,
                "absolute_end": 0.3,
                "local_start": 0.2,
                "visual_action": "identify the active square",
                "target_id": "selected_cell",
                "evidence_type": "runtime_action",
                "evidence_id": "identify-square",
            },
            {
                "anchor_id": "rotate-word",
                "token": "旋转",
                "absolute_start": 1.0,
                "absolute_end": 1.2,
                "local_start": 1.0,
                "visual_action": "rotate the same square visibly",
                "target_id": "selected_cell",
                "evidence_type": "runtime_action",
                "evidence_id": "rotate-square",
            },
            {
                "anchor_id": "scale-word",
                "token": "等比例伸缩",
                "absolute_start": 2.0,
                "absolute_end": 2.4,
                "local_start": 2.0,
                "visual_action": "uniformly scale the same square",
                "target_id": "selected_cell",
                "evidence_type": "runtime_action",
                "evidence_id": "scale-square",
            },
            {
                "anchor_id": "settle-word",
                "token": "。",
                "absolute_start": 3.0,
                "absolute_end": 3.1,
                "local_start": 3.0,
                "visual_action": "settle the transformed square",
                "target_id": "selected_cell",
                "evidence_type": "runtime_action",
                "evidence_id": "settle-square",
            },
        ]
        plan["narrated_action_contracts"] = [
            {
                "spoken_token": "旋转",
                "action_kind": "rotate",
                "occurrence_index": 1,
                "word_anchor_id": "rotate-word",
                "object_id": "selected_cell",
                "delivery_mode": "enacted_motion",
                "expected_visible_change": "The same square changes its measured orientation.",
                "screen_text_policy": "motion_not_duplicate_text",
                "evidence_id": "rotate-square",
                "measurement_contract": {"metric": "angle_delta_degrees"},
            },
            {
                "spoken_token": "等比例伸缩",
                "action_kind": "uniform_scale",
                "occurrence_index": 1,
                "word_anchor_id": "scale-word",
                "object_id": "selected_cell",
                "delivery_mode": "enacted_motion",
                "expected_visible_change": "The same square changes both axis scales by one ratio.",
                "screen_text_policy": "motion_not_duplicate_text",
                "evidence_id": "scale-square",
                "measurement_contract": {"metric": "axis_scale_ratios"},
            },
        ]
        self.assertEqual(pipeline.validate_scene_plan_data(profile, plan), [])
        telemetry = self.make_telemetry(profile)
        telemetry["word_anchor_events"] = [
            {
                "anchor_id": "rotate-word",
                "planned_time": 1.0,
                "actual_time": 1.0,
                "target_id": "selected_cell",
                "evidence_type": "runtime_action",
                "evidence_id": "rotate-square",
                "action_kind": "rotate",
                "delivery_mode": "enacted_motion",
                "geometry_source": "runtime_export",
                "text_only": False,
                "duplicate_text_ids": [],
                "action_measurement": {
                    "angle_before_degrees": 0.0,
                    "angle_after_degrees": 30.0,
                },
            },
            {
                "anchor_id": "scale-word",
                "planned_time": 2.0,
                "actual_time": 2.0,
                "target_id": "selected_cell",
                "evidence_type": "runtime_action",
                "evidence_id": "scale-square",
                "action_kind": "uniform_scale",
                "delivery_mode": "enacted_motion",
                "geometry_source": "frame_analysis",
                "text_only": False,
                "duplicate_text_ids": [],
                "action_measurement": {
                    "scale_x_ratio": 1.4,
                    "scale_y_ratio": 1.4,
                },
            },
            {
                "anchor_id": "context-word",
                "planned_time": 0.2,
                "actual_time": 0.2,
                "target_id": "selected_cell",
                "evidence_type": "runtime_action",
                "evidence_id": "identify-square",
            },
            {
                "anchor_id": "settle-word",
                "planned_time": 3.0,
                "actual_time": 3.0,
                "target_id": "selected_cell",
                "evidence_type": "runtime_action",
                "evidence_id": "settle-square",
            },
        ]
        qc = pipeline.validate_authoring_qc_data(profile, plan, telemetry)
        self.assertTrue(qc["valid"], qc["issues"])
        text_only = json.loads(json.dumps(telemetry))
        text_only["word_anchor_events"][0]["text_only"] = True
        text_only["word_anchor_events"][0]["duplicate_text_ids"] = ["rotate-caption"]
        self.assertEqual(profile["autopilot_contract_version"], 8)
        self.assertEqual(len(plan["narrated_action_contracts"]), 2)
        self.assertIs(text_only["word_anchor_events"][0]["text_only"], True)
        qc = pipeline.validate_authoring_qc_data(profile, plan, text_only)
        codes = {item["code"] for item in qc["issues"]}
        self.assertIn("NARRATED_ACTION_TEXT_ONLY", codes, qc)
        self.assertIn("NARRATED_ACTION_DUPLICATE_TEXT", codes, qc)
        anisotropic = json.loads(json.dumps(telemetry))
        anisotropic["word_anchor_events"][1]["action_measurement"]["scale_y_ratio"] = 0.8
        qc = pipeline.validate_authoring_qc_data(profile, plan, anisotropic)
        self.assertTrue(
            any(item["code"] == "NARRATED_UNIFORM_SCALE_ANISOTROPIC" for item in qc["issues"])
        )

    def test_screen_text_semantics_reject_narration_copy_and_creator_intent(self) -> None:
        profile = self.make_profile()
        profile["context"]["narration"] = "它能旋转。"
        profile["autopilot_contract_version"] = 7
        plan = {
            "screen_text_contract": {
                "semantic_items": [
                    {
                        "constructor": "Text",
                        "payload": "它能旋转",
                        "count": 1,
                        "role": "comparison_label",
                        "unique_visual_job": "Name the comparison state beside the square.",
                        "necessity": "The label identifies which compared state belongs to the rotating square.",
                        "removal_failure": "Without it the two comparison states cannot be assigned to their objects.",
                        "clearance_condition": "Clear after the comparison resolves.",
                        "math_object_anchor": "selected_cell",
                        "duplicates_narration": False,
                        "externalizes_production_intent": False,
                    },
                    {
                        "constructor": "Text",
                        "payload": "这个动画想表达旋转",
                        "count": 1,
                        "role": "scene_title",
                        "unique_visual_job": "Name the scene topic at the opening.",
                        "necessity": "The title is claimed to identify the learner question for this scene.",
                        "removal_failure": "Without it the opening question would not be explicit.",
                        "clearance_condition": "Clear when the first object appears.",
                        "learner_question_anchor": "what operation changes the square",
                        "duplicates_narration": False,
                        "externalizes_production_intent": False,
                    },
                ],
                "dynamic_payload_count": 0,
                "dynamic_payload_policy": "runtime_registered",
            }
        }
        inventory = {
            "signature": [
                {"constructor": "Text", "payloads": ["它能旋转"], "count": 1},
                {"constructor": "Text", "payloads": ["这个动画想表达旋转"], "count": 1},
            ],
            "dynamic_payload_count": 0,
        }
        errors = pipeline.validate_screen_text_semantics(profile, plan, inventory)
        self.assertTrue(any("duplicates the spoken narration" in error for error in errors))
        self.assertTrue(any("externalizes production intent" in error for error in errors))

    def test_screen_text_semantics_reject_episode_recap_and_creator_persona(self) -> None:
        profile = self.make_profile()
        profile["autopilot_contract_version"] = 7
        payloads = [
            "把这一集的因果链重新走一遍",
            "我是结束乐队的键盘手，下个视频见。",
        ]
        plan = {
            "screen_text_contract": {
                "semantic_items": [
                    {
                        "constructor": "cn_text",
                        "payload": payload,
                        "count": 1,
                        "role": "scene_title",
                        "unique_visual_job": "Attempt to title the summary state for the learner.",
                        "necessity": "The author claims this text is needed to identify the current state.",
                        "removal_failure": "The author claims removal would weaken the summary transition.",
                        "clearance_condition": "Clear after the state changes.",
                        "learner_question_anchor": "summary question",
                        "duplicates_narration": False,
                        "externalizes_production_intent": False,
                    }
                    for payload in payloads
                ],
                "dynamic_payload_count": 0,
                "dynamic_payload_policy": "runtime_registered",
            }
        }
        inventory = {
            "signature": [
                {"constructor": "cn_text", "payloads": [payload], "count": 1}
                for payload in payloads
            ],
            "dynamic_payload_count": 0,
        }
        errors = pipeline.validate_screen_text_semantics(profile, plan, inventory)
        for payload in payloads:
            self.assertTrue(
                any(payload in error and "externalizes production intent" in error for error in errors),
                errors,
            )

    def test_screen_text_inventory_includes_project_wrappers(self) -> None:
        source = self.episode / "src" / "scenes" / "wrapped_formula_scene"
        source.mkdir(parents=True, exist_ok=True)
        (source / "objects.py").write_text(
            "formula = role_formula(r'F(\\omega)=1', font_size=40)\n"
            "symbol = math_tex(r'\\omega', font_size=30)\n"
            "caption = label('频率', font_size=28)\n"
            "question = cn_text('小圈积分读取什么？', size=28)\n",
            encoding="utf-8",
        )
        inventory = pipeline.scan_screen_text_inventory(source, self.root)
        self.assertEqual(inventory["constructor_counts"]["role_formula"], 1)
        self.assertEqual(inventory["constructor_counts"]["math_tex"], 1)
        self.assertEqual(inventory["constructor_counts"]["label"], 1)
        self.assertEqual(inventory["constructor_counts"]["cn_text"], 1)
        self.assertGreater(inventory["static_character_count"], 0)

    def test_relevant_regressions_exclude_unaccepted_subagent_diagnostics(self) -> None:
        issues = self.episode / "review" / "issues"
        common = {
            "scene": "g002c_riemann_sum_limit",
            "severity": "critical",
            "problem": "An exact-scene regression candidate.",
            "suggested_fix": "Exercise the regression promotion boundary.",
        }
        self.write_json(
            issues / "pending_subagent_diagnostic.json",
            {
                **common,
                "id": "pending-subagent-diagnostic",
                "source": "subagent_review",
                "pattern_key": "pending_subagent_diagnostic",
                "accepted_by": None,
                "must_check_in_future": False,
                "pending_coordinator_promotion": True,
                "acceptance_authority": False,
                "applies_to_authoring": False,
            },
        )
        self.write_json(
            issues / "accepted_agent_regression.json",
            {
                **common,
                "id": "accepted-agent-regression",
                "source": "accepted_agent_feedback",
                "pattern_key": "accepted_agent_regression",
                "accepted_by": "coordinator",
                "must_check_in_future": False,
            },
        )
        self.write_json(
            issues / "human_regression.json",
            {
                **common,
                "id": "human-regression",
                "source": "human_review",
                "pattern_key": "human_regression",
                "must_check_in_future": False,
            },
        )
        self.write_json(
            issues / "explicit_future_regression.json",
            {
                **common,
                "id": "explicit-future-regression",
                "source": "subagent_review",
                "pattern_key": "explicit_future_regression",
                "accepted_by": None,
                "must_check_in_future": True,
            },
        )

        regressions, _ = pipeline.relevant_regressions(
            self.episode,
            {
                "id": "G002C",
                "scene_slug": "g002c_riemann_sum_limit",
            },
            {"always", "formula_dense"},
            limit=50,
        )
        patterns = {item["pattern_key"] for item in regressions}
        self.assertNotIn("pending_subagent_diagnostic", patterns)
        self.assertIn("human_regression", patterns)
        self.assertIn("accepted_agent_regression", patterns)
        self.assertIn("explicit_future_regression", patterns)

    def test_live_policy_and_math_object_gate_update_immediately(self) -> None:
        base_profile = self.make_profile()
        self.write_json(
            self.episode / "review" / "issues" / "unrelated_scene_formula_issue.json",
            {
                "id": "human-unrelated-1",
                "scene": "g099_unrelated_scene",
                "source": "human_review",
                "severity": "major",
                "pattern_key": "unrelated_integral_formula_issue",
                "must_check_in_future": True,
                "problem": "Another scene has a formula and integral transition failure.",
                "suggested_fix": "Repair that other scene without invalidating this one.",
            },
        )
        policy_path = self.episode / "review" / "v2" / "active_policy.json"
        policy = pipeline.compile_live_policy_data(self.episode, base_profile)
        self.write_json(policy_path, policy)
        profile = pipeline.attach_autopilot_contract(base_profile, policy, policy_path, self.root)
        self.assertTrue(pipeline.validate_profile_hash(profile))
        self.assertIn("human-limit-1", {entry["issue_id"] for entry in policy["entries"]})
        self.assertNotIn("human-unrelated-1", {entry["issue_id"] for entry in policy["entries"]})
        self.assertGreaterEqual(policy["implicit_advisory_matches_omitted"], 1)

        bundle = self.make_design_bundle(profile)
        plan = self.make_plan(profile, bundle)
        plan["math_object_invariants"] = [
            {
                "invariant_id": "cells_follow_L",
                "object_id": "frequency_cells",
                "mathematical_claim": "Increasing L narrows every frequency cell without changing the density envelope.",
                "expected_relation": "cell width equals two pi divided by L",
                "evidence_type": "runtime_assertion",
                "checkpoints": [2.5, 7.0],
            },
            {
                "invariant_id": "formula_keeps_ancestry",
                "object_id": "riemann_formula",
                "mathematical_claim": "The finite sum retains its interval factor until the continuous integral is established.",
                "expected_relation": "Delta omega becomes d omega only after cell refinement",
                "evidence_type": "formula_handoff",
                "checkpoints": [1.0, 4.0],
            },
        ]
        self.assertEqual(pipeline.validate_scene_plan_data(profile, plan), [])

        telemetry = self.make_telemetry(profile)
        telemetry["math_invariant_checks"] = [
            {
                "invariant_id": "cells_follow_L",
                "object_id": "frequency_cells",
                "evidence_type": "runtime_assertion",
                "passed": True,
                "observed_relation": "Every measured cell width equals two pi divided by the active L.",
                "samples": [{"time": 2.5, "error": 0.0}, {"time": 7.0, "error": 0.0}],
            },
            {
                "invariant_id": "formula_keeps_ancestry",
                "object_id": "riemann_formula",
                "evidence_type": "formula_handoff",
                "passed": True,
                "observed_relation": "The Delta omega token remains visible until the serialized integral handoff.",
                "samples": [{"time": 1.0, "visible": True}, {"time": 4.0, "visible": True}],
            },
        ]
        report = pipeline.validate_authoring_qc_data(profile, plan, telemetry)
        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(set(report["gate_coverage"]), set(pipeline.HARD_GATE_LAYERS))
        fake_binding = json.loads(json.dumps(telemetry))
        fake_binding["math_object_bindings"][0]["display_mapping_id"] = "riemann_formula_view"
        report = pipeline.validate_authoring_qc_data(profile, plan, fake_binding)
        self.assertTrue(any(item["code"] == "DISPLAY_MAPPING_DRIFT" for item in report["issues"]))
        misleading_mapping = json.loads(json.dumps(telemetry))
        misleading_mapping["display_mapping_checks"][0]["forbidden_inference_violations"] = [
            "screen width was read as the true mathematical interval width"
        ]
        report = pipeline.validate_authoring_qc_data(profile, plan, misleading_mapping)
        self.assertTrue(any(item["code"] == "DISPLAY_MAPPING_MISLEADS" for item in report["issues"]))
        telemetry["math_invariant_checks"][0]["passed"] = False
        report = pipeline.validate_authoring_qc_data(profile, plan, telemetry)
        self.assertTrue(any(item["code"] == "MATH_INVARIANT_FAILED" for item in report["issues"]))

        issue_path = self.episode / "review" / "issues" / "new_coordinate_failure.json"
        self.write_json(
            issue_path,
            {
                "id": "human-coordinate-2",
                "scene": "g002c_riemann_sum_limit",
                "source": "human_review",
                "severity": "blocker",
                "pattern_key": "point_misses_axis_coordinate",
                "must_check_in_future": True,
                "problem": "A selected point is visibly above its claimed axis coordinate.",
                "required_fix": "Bind the point center to the coordinate map and export an exact check.",
            },
        )
        refreshed = pipeline.compile_live_policy_data(self.episode, profile)
        self.assertNotEqual(refreshed["policy_hash"], policy["policy_hash"])
        self.assertIn("math_object", next(item for item in refreshed["entries"] if item["issue_id"] == "human-coordinate-2")["gate_layers"])

    def test_global_umbrella_issue_uses_scene_local_status_without_closing_episode_issue(self) -> None:
        base_profile = self.make_profile()
        scene_slug = base_profile["context"]["scene_slug"]
        self.write_json(
            self.episode / "review" / "issues" / "global_visual_audit.json",
            {
                "id": "human-global-visual-audit",
                "source": "human_review",
                "severity": "critical",
                "pattern_key": "creator_intent_text_substitutes_for_animation",
                "must_check_in_future": True,
                "global_scope": True,
                "status": "open",
                "scene_statuses": {
                    scene_slug: "resolved_pending_review",
                    "g099_unrepaired": "open",
                },
            },
        )
        policy = pipeline.compile_live_policy_data(self.episode, base_profile)
        entry = next(
            item
            for item in policy["entries"]
            if item["issue_id"] == "human-global-visual-audit"
        )
        self.assertEqual(entry["status"], "resolved_pending_review")
        self.assertEqual(entry["status_source"], "scene_status")
        self.assertEqual(entry["umbrella_status"], "open")
        self.assertEqual(pipeline.validate_pass_policy(policy), [])

        unrepaired_profile = json.loads(json.dumps(base_profile))
        unrepaired_profile["context"]["scene_slug"] = "g099_unrepaired"
        unrepaired_policy = pipeline.compile_live_policy_data(self.episode, unrepaired_profile)
        unrepaired_entry = next(
            item
            for item in unrepaired_policy["entries"]
            if item["issue_id"] == "human-global-visual-audit"
        )
        self.assertEqual(unrepaired_entry["status"], "open")
        self.assertTrue(pipeline.validate_pass_policy(unrepaired_policy))

    def test_four_layer_review_sweeps_and_adaptive_mode(self) -> None:
        self.assertEqual(
            pipeline.validate_layout_audit_data(
                {
                    "schema": "lecture-animation-layout-audit-v2",
                    "scene_slug": "g002c_riemann_sum_limit",
                    "capture_source": "runtime_export",
                    "snapshot_count": 5,
                    "issue_count": 0,
                    "issues": [],
                    "status": "pass",
                },
                "g002c_riemann_sum_limit",
            ),
            [],
        )
        self.assertTrue(
            pipeline.validate_layout_audit_data(
                {
                    "schema": "lecture-animation-layout-audit-v2",
                    "scene_slug": "g002c_riemann_sum_limit",
                    "capture_source": "runtime_export",
                    "snapshot_count": 5,
                    "issue_count": 1,
                    "issues": [{"code": "OVERLAP"}],
                    "status": "pass",
                },
                "g002c_riemann_sum_limit",
            )
        )
        profile = self.make_profile()
        bundle = self.make_design_bundle(profile)
        plan = self.make_plan(profile, bundle)
        plan["math_object_invariants"] = [
            {
                "invariant_id": "cells_follow_L",
                "object_id": "frequency_cells",
                "mathematical_claim": "Increasing L narrows the frequency partition.",
                "expected_relation": "cell width equals two pi divided by L",
                "evidence_type": "runtime_assertion",
                "checkpoints": [2.5, 7.0],
            }
        ]
        anchors = pipeline.review_coverage_anchors(plan, 10.0)
        review = {
            "coverage_sweeps": [
                {
                    "layer": layer,
                    "result": "pass",
                    "timestamps": times,
                    "object_ids": ["frequency_cells", "riemann_formula"],
                    "observation": f"The {layer} sweep follows every required checkpoint and finds one continuous evidence chain.",
                }
                for layer, times in anchors.items()
            ]
        }
        self.assertEqual(pipeline.validate_review_coverage_sweeps(review, plan, 10.0), [])
        review["coverage_sweeps"][0]["timestamps"] = [0.2]
        self.assertTrue(any("layout misses required anchor" in error for error in pipeline.validate_review_coverage_sweeps(review, plan, 10.0)))

        previous_manifest = {
            "scene_slug": "g002c_riemann_sum_limit",
            "manifest_hash": "old",
            "artifacts": {
                "plan": {"sha256": "plan-1", "size": 10},
                "source": {"sha256": "source-1", "size": 10},
                "review_mp4": {"sha256": "mp4-1", "size": 10},
            },
        }
        local_manifest = {
            "scene_slug": "g002c_riemann_sum_limit",
            "manifest_hash": "local",
            "artifacts": {
                "plan": {"sha256": "plan-1", "size": 10},
                "source": {"sha256": "source-2", "size": 11},
                "review_mp4": {"sha256": "mp4-2", "size": 11},
            },
        }
        previous_review = {"verdict": "revise"}
        session = {"session_id": "review-session:test"}
        strategy = pipeline.review_strategy_data(previous_manifest, local_manifest, previous_review, session, [])
        self.assertEqual(strategy["next_review_mode"], "full_regression")
        impact = {
            "schema": "lecture-animation-change-impact-v2",
            "previous_manifest_hash": "old",
            "current_manifest_hash": "local",
            "changed_artifacts": ["review_mp4", "source"],
            "changed_object_ids": ["frequency_cells"],
            "changed_windows": [[3.0, 5.0]],
            "changed_layers": ["layout"],
            "semantic_contract_changed": False,
            "unchanged_contracts_asserted": True,
        }
        impact["impact_hash"] = pipeline.object_hash(impact)
        strategy = pipeline.review_strategy_data(previous_manifest, local_manifest, previous_review, session, [], impact)
        self.assertEqual(strategy["next_review_mode"], "diagnostic")
        material_manifest = json.loads(json.dumps(local_manifest))
        material_manifest["artifacts"]["plan"] = {"sha256": "plan-2", "size": 11}
        strategy = pipeline.review_strategy_data(previous_manifest, material_manifest, previous_review, session, [])
        self.assertEqual(strategy["next_review_mode"], "full_regression")
        self.assertTrue(strategy["layout_gate_remains_mandatory"])
        rejected_attempts = [
            {
                "scene_slug": "g002c_riemann_sum_limit",
                "review_mode": "full_regression",
                "gate_accepted": False,
            }
            for _ in range(4)
        ]
        strategy = pipeline.review_strategy_data(
            previous_manifest,
            material_manifest,
            previous_review,
            session,
            rejected_attempts,
        )
        self.assertEqual(strategy["full_reviews_for_scene"], 0)
        self.assertFalse(strategy["root_cause_escalation_required"])

        governance_attempts = [
            {
                "scene_slug": "g002c_riemann_sum_limit",
                "revision_kind": "infra",
                "actual_execution": False,
                "result": "revise",
            }
            for _ in range(4)
        ]
        governance = pipeline.review_iteration_governance_data(
            "g002c_riemann_sum_limit", governance_attempts
        )
        self.assertTrue(governance["root_cause_reset_required"])
        self.assertFalse(governance["new_micro_revision_allowed"])
        self.assertIn("contract_or_infra_revision_limit", governance["triggers"])
        strategy = pipeline.review_strategy_data(
            previous_manifest,
            material_manifest,
            previous_review,
            session,
            governance_attempts,
        )
        self.assertTrue(strategy["root_cause_escalation_required"])
        self.assertFalse(strategy["micro_patch_allowed"])
        self.assertTrue(strategy["repair_requires_exhaustive_finding_bundle"])

    def test_progressive_planning_chain_is_hash_bound(self) -> None:
        with self.assertRaisesRegex(pipeline.PipelineError, "dedicated direct child worktree"):
            pipeline.parallel_worktree_identity(self.root)
        episode_path = pipeline.relative_or_absolute(self.episode, self.root)
        spine = {
            "schema": "lecture-animation-episode-visual-spine-v2",
            "episode": episode_path,
            "production_mode": "parallel_batches",
            "main_agent_governance": {
                "owner": "/root",
                "overview_artifacts": ["lecture", "narration_outline", "storyboard", "timeline", "episode_visual_spine"],
                "human_feedback_route": "The main agent compiles direct human feedback into live policy before delegation.",
                "cli_gate_policy": "required_no_bypass",
            },
            "narration_style_contract": self.narration_style_contract(),
            "timeline_sha256": pipeline.artifact_snapshot(self.episode / "timeline.json", self.root)["sha256"],
            "storyboard_sha256": pipeline.artifact_snapshot(self.episode / "storyboard.md", self.root)["sha256"],
            "teaching_spine": "Discrete frequency samples acquire interval weight and converge into one continuous reconstruction rule.",
            "cross_scene_identity_carriers": ["frequency_cells", "density_curve", "reconstruction_target"],
            "visual_conventions": {"frequency": "blue", "contribution": "gold"},
            "batch_partition": [
                {
                    "batch_id": "limit-batch",
                    "scenes": ["g002c_riemann_sum_limit", "g002d_normalization", "g003_density"],
                    "entry_compatibility_key": "selected-frequency-cell",
                    "exit_compatibility_key": "density-interval-ready",
                    "entry_identity_carriers": ["frequency_cells"],
                    "exit_identity_carriers": ["density_curve"],
                    "entry_fixed_visual_state": "Start with the selected frequency cell preserved from the preceding scene.",
                    "entry_narration_lock": "intent",
                    "entry_narration_text": "Continue from the selected frequency contribution into refinement.",
                    "entry_handoff_meaning": "A selected discrete contribution becomes the object refined in this batch.",
                    "entry_freedom_inside": "The subagent may design the internal refinement choreography and staging.",
                    "entry_audio_handoff": {
                        "outgoing_clause_owner": "previous-batch",
                        "incoming_clause_owner": "limit-batch",
                        "tail_silence_seconds": 0.3,
                        "max_boundary_drift_seconds": 0.25,
                        "cut_policy": "Finish the outgoing clause before the incoming scene starts speaking.",
                    },
                    "exit_fixed_visual_state": "End with the density curve and one interval contribution ready for continuation.",
                    "exit_narration_lock": "exact",
                    "exit_narration_text": "The transform value is a density; an interval supplies the contribution.",
                    "exit_handoff_meaning": "A continuous density and interval contribution are ready for the next batch.",
                    "exit_freedom_inside": "The subagent may choose the internal reveal while preserving the locked ending.",
                    "exit_audio_handoff": {
                        "outgoing_clause_owner": "limit-batch",
                        "incoming_clause_owner": "next-batch",
                        "tail_silence_seconds": 0.3,
                        "max_boundary_drift_seconds": 0.25,
                        "cut_policy": "Finish the outgoing clause before the incoming scene starts speaking.",
                    },
                }
            ],
            "scenes": [
                {
                    "scene_slug": "g002c_riemann_sum_limit",
                    "teaching_role": "Turn sampled frequency values into interval contributions.",
                    "primary_objects": ["frequency_cells", "density_curve"],
                    "incoming_learner_state": "The learner sees discrete Fourier frequency samples.",
                    "outgoing_learner_state": "The learner can predict a Riemann sum becoming an integral.",
                    "transition_intent": "Carry one selected cell into the continuous density view.",
                    "planning_status": "frozen",
                },
                {
                    "scene_slug": "g002d_normalization",
                    "teaching_role": "Keep the measure factor visible through normalization.",
                    "primary_objects": ["measure factor", "normalized coefficient"],
                    "incoming_learner_state": "The learner sees interval-weighted contributions.",
                    "outgoing_learner_state": "The learner recognizes the normalized coefficient convention.",
                    "transition_intent": "Carry the interval token into the normalized coefficient.",
                    "planning_status": "provisional",
                },
                {
                    "scene_slug": "g003_density",
                    "teaching_role": "Interpret the transform value as continuous coordinate density.",
                    "primary_objects": ["density curve", "interval contribution"],
                    "incoming_learner_state": "The learner recognizes the normalized frequency contribution.",
                    "outgoing_learner_state": "The learner can distinguish density height from interval mass.",
                    "transition_intent": "Promote the coefficient family into a continuous density curve.",
                    "planning_status": "provisional",
                },
            ],
        }
        spine["spine_hash"] = pipeline.object_hash(spine)
        self.assertEqual(pipeline.validate_episode_spine_data(spine, self.root, self.episode), [])

        batch_plan = {
            "schema": "lecture-animation-batch-visual-plan-v2",
            "batch_id": "limit-batch",
            "episode": episode_path,
            "episode_spine_hash": spine["spine_hash"],
            "main_agent_owner": "/root",
            "cli_gate_policy": "required_no_bypass",
            "narration_style_contract": self.narration_style_contract(),
            "scenes": [
                {
                    "scene_slug": slug,
                    "continuity_in": "Continue the same frequency object from the previous scene.",
                    "teaching_job": "Expose one necessary step of the sum-to-integral argument.",
                    "stage_strategy": "Promote the active mathematical object while preserving a compact memory view.",
                    "continuity_out": "Leave the reconstructed object ready for the next scene.",
                    "variation_from_neighbors": "Use a distinct dominant operation and avoid repeating the same split layout.",
                    "narration_style_notes": "Use novice-first causal language and introduce only this scene's one new operation.",
                }
                for slug in ("g002c_riemann_sum_limit", "g002d_normalization", "g003_density")
            ],
            "shared_identity_carriers": ["frequency_cells", "density_curve"],
            "transition_contracts": ["selected cell carries identity into the density view"],
            "batch_entry_contract": {
                "boundary_scene": "g002c_riemann_sum_limit",
                "fixed_visual_state": "Start with the selected frequency cell preserved from the preceding scene.",
                "narration_lock": "intent",
                "narration_text": "Continue from the selected frequency contribution into refinement.",
                "required_identity_carriers": ["frequency_cells"],
                "handoff_meaning": "A selected discrete contribution becomes the object refined in this batch.",
                "transition_owner": "/root",
                "compatibility_key": "selected-frequency-cell",
                "freedom_inside": "The subagent may design the internal refinement choreography and staging.",
                "audio_handoff": {
                    "outgoing_clause_owner": "previous-batch",
                    "incoming_clause_owner": "limit-batch",
                    "tail_silence_seconds": 0.3,
                    "max_boundary_drift_seconds": 0.25,
                    "cut_policy": "Finish the outgoing clause before the incoming scene starts speaking.",
                },
            },
            "batch_exit_contract": {
                "boundary_scene": "g003_density",
                "fixed_visual_state": "End with the density curve and one interval contribution ready for continuation.",
                "narration_lock": "exact",
                "narration_text": "The transform value is a density; an interval supplies the contribution.",
                "required_identity_carriers": ["density_curve"],
                "handoff_meaning": "A continuous density and interval contribution are ready for the next batch.",
                "transition_owner": "/root",
                "compatibility_key": "density-interval-ready",
                "freedom_inside": "The subagent may choose the internal reveal while preserving the locked ending.",
                "audio_handoff": {
                    "outgoing_clause_owner": "limit-batch",
                    "incoming_clause_owner": "next-batch",
                    "tail_silence_seconds": 0.3,
                    "max_boundary_drift_seconds": 0.25,
                    "cut_policy": "Finish the outgoing clause before the incoming scene starts speaking.",
                },
            },
            "adjacency_contracts": [
                {
                    "from_scene": "g002c_riemann_sum_limit",
                    "to_scene": "g002d_normalization",
                    "fixed_outgoing_visual_state": "The selected cell and its width remain visible at scene exit.",
                    "fixed_incoming_visual_state": "The same cell width enters the normalization formula at scene start.",
                    "visual_handoff": "Carry the selected cell width into the normalization formula.",
                    "narration_handoff": "The visible interval factor becomes the normalization factor.",
                    "narration_text": "The visible interval factor now becomes part of the normalization.",
                    "narration_lock": "intent",
                    "handoff_meaning": "The same interval factor changes role without changing identity.",
                    "identity_carriers": ["frequency_cells"],
                    "compatibility_key": "cell-to-normalization",
                    "transition_owner": "/root",
                    "freedom_inside": "The subagent may choose motion paths after preserving the cell identity.",
                    "audio_handoff": {
                        "outgoing_clause_owner": "g002c_riemann_sum_limit",
                        "incoming_clause_owner": "g002d_normalization",
                        "tail_silence_seconds": 0.2,
                        "max_boundary_drift_seconds": 0.25,
                        "cut_policy": "Do not split the interval-factor claim across an audio cut.",
                    },
                },
                {
                    "from_scene": "g002d_normalization",
                    "to_scene": "g003_density",
                    "fixed_outgoing_visual_state": "The normalized coefficient family remains visible at scene exit.",
                    "fixed_incoming_visual_state": "The same family is promoted into the density curve at scene start.",
                    "visual_handoff": "Promote the normalized coefficient family into the density curve.",
                    "narration_handoff": "Move from one normalized coefficient to continuous density.",
                    "narration_text": "One normalized coefficient now extends into a continuous density.",
                    "narration_lock": "intent",
                    "handoff_meaning": "The normalized family becomes a continuous density without replacement.",
                    "identity_carriers": ["density_curve"],
                    "compatibility_key": "normalization-to-density",
                    "transition_owner": "/root",
                    "freedom_inside": "The subagent may choose the promotion choreography while keeping the same family.",
                    "audio_handoff": {
                        "outgoing_clause_owner": "g002d_normalization",
                        "incoming_clause_owner": "g003_density",
                        "tail_silence_seconds": 0.2,
                        "max_boundary_drift_seconds": 0.25,
                        "cut_policy": "Do not split the coefficient-to-density claim across an audio cut.",
                    },
                },
            ],
            "complexity_distribution": "The first scene owns the dense construction; later scenes preserve it as compact visual memory.",
        }
        batch_plan["batch_plan_hash"] = pipeline.object_hash(batch_plan)
        scenes = [row["scene_slug"] for row in batch_plan["scenes"]]
        self.assertEqual(
            pipeline.validate_batch_visual_plan_data(batch_plan, spine, "limit-batch", scenes),
            [],
        )
        invalid_parallel_plan = dict(batch_plan)
        invalid_parallel_plan.pop("batch_entry_contract")
        invalid_parallel_plan.pop("batch_plan_hash", None)
        invalid_parallel_plan["batch_plan_hash"] = pipeline.object_hash(invalid_parallel_plan)
        self.assertTrue(
            any(
                "batch_entry_contract" in error
                for error in pipeline.validate_batch_visual_plan_data(invalid_parallel_plan, spine, "limit-batch", scenes)
            )
        )
        missing_handoff_plan = dict(batch_plan)
        missing_handoff_plan["adjacency_contracts"] = batch_plan["adjacency_contracts"][:1]
        missing_handoff_plan.pop("batch_plan_hash", None)
        missing_handoff_plan["batch_plan_hash"] = pipeline.object_hash(missing_handoff_plan)
        self.assertTrue(
            any(
                "every internal adjacent-scene handoff" in error
                for error in pipeline.validate_batch_visual_plan_data(missing_handoff_plan, spine, "limit-batch", scenes)
            )
        )
        style_drift_plan = json.loads(json.dumps(batch_plan))
        style_drift_plan["narration_style_contract"]["voice"] = "A different improvised voice that breaks episode continuity."
        style_drift_plan.pop("batch_plan_hash", None)
        style_drift_plan["batch_plan_hash"] = pipeline.object_hash(style_drift_plan)
        self.assertTrue(
            any(
                "exactly reproduce" in error
                for error in pipeline.validate_batch_visual_plan_data(style_drift_plan, spine, "limit-batch", scenes)
            )
        )
        bad_audio_handoff = json.loads(json.dumps(batch_plan))
        bad_audio_handoff["adjacency_contracts"][0]["audio_handoff"]["max_boundary_drift_seconds"] = 0.5
        bad_audio_handoff.pop("batch_plan_hash", None)
        bad_audio_handoff["batch_plan_hash"] = pipeline.object_hash(bad_audio_handoff)
        self.assertTrue(
            any(
                "no greater than 0.25" in error
                for error in pipeline.validate_batch_visual_plan_data(bad_audio_handoff, spine, "limit-batch", scenes)
            )
        )
        scene_plan = {
            "scene_slug": "g002c_riemann_sum_limit",
            "planning_chain": {
                "episode_spine_hash": spine["spine_hash"],
                "batch_plan_hash": batch_plan["batch_plan_hash"],
            },
        }
        self.assertEqual(pipeline.validate_scene_planning_chain(scene_plan, spine, batch_plan), [])
        scene_plan["planning_chain"]["batch_plan_hash"] = "stale"
        self.assertTrue(pipeline.validate_scene_planning_chain(scene_plan, spine, batch_plan))

    def test_parallel_production_requires_matching_stable_roster_grant(self) -> None:
        supervisor = {
            "schema": "lecture-animation-supervisor-session-v2",
            "session_id": "supervisor:test",
            "supervisor_agent_id": "/root",
            "closed_at": None,
            "assignments": {
                "author-a": {
                    "role": "animation_author",
                    "task_key": "batch-a",
                    "scope": "G001-G003 and their repairs",
                    "model": "gpt-5.6-sol",
                    "state": "active",
                }
            },
        }
        supervisor["session_hash"] = pipeline.object_hash(supervisor)
        grant = pipeline.validate_supervisor_production_grant(supervisor, "author-a", "batch-a")
        self.assertEqual(grant["author_id"], "author-a")
        self.assertEqual(grant["task_key"], "batch-a")
        with self.assertRaisesRegex(pipeline.PipelineError, "outside the sealed supervisor roster"):
            pipeline.validate_supervisor_production_grant(supervisor, "author-b", "batch-a")
        with self.assertRaisesRegex(pipeline.PipelineError, "task_key"):
            pipeline.validate_supervisor_production_grant(supervisor, "author-a", "batch-b")
        idle = json.loads(json.dumps(supervisor))
        idle["assignments"]["author-a"]["state"] = "completed"
        idle.pop("session_hash")
        idle["session_hash"] = pipeline.object_hash(idle)
        with self.assertRaisesRegex(pipeline.PipelineError, "active supervisor assignment"):
            pipeline.validate_supervisor_production_grant(idle, "author-a", "batch-a")

    def test_parallel_finalization_requires_closed_empty_supervisor_queue(self) -> None:
        supervisor = {
            "schema": "lecture-animation-supervisor-session-v2",
            "session_id": "supervisor:complete",
            "closed_at": "2026-07-21T12:00:00+00:00",
            "assignments": {
                "author-a": {"state": "completed"},
                "author-b": {"state": "completed"},
            },
            "task_queue": {
                "batch-a": {"state": "completed"},
                "batch-b": {"state": "completed"},
            },
            "replacement_authorizations": {},
            "capacity_authorizations": {},
            "identity_history": ["author-a", "author-b"],
            "replacement_count": 0,
            "capacity_expansion_count": 0,
        }
        supervisor["session_hash"] = pipeline.object_hash(supervisor)
        completion = pipeline.validate_supervisor_episode_completion(supervisor)
        self.assertEqual(completion["historical_identity_count"], 2)
        pending = json.loads(json.dumps(supervisor))
        pending["task_queue"]["batch-b"]["state"] = "pending"
        pending.pop("session_hash")
        pending["session_hash"] = pipeline.object_hash(pending)
        with self.assertRaisesRegex(pipeline.PipelineError, "unfinished roster work"):
            pipeline.validate_supervisor_episode_completion(pending)
        pending_capacity = json.loads(json.dumps(supervisor))
        pending_capacity["capacity_authorizations"]["capacity:one"] = {
            "status": "authorized"
        }
        pending_capacity.pop("session_hash")
        pending_capacity["session_hash"] = pipeline.object_hash(pending_capacity)
        with self.assertRaisesRegex(pipeline.PipelineError, "unfinished roster work"):
            pipeline.validate_supervisor_episode_completion(pending_capacity)

    def _independent_review_repair_round_fixture(
        self,
    ) -> dict[str, object]:
        skill_root = (
            self.root
            / ".agents"
            / "skills"
            / "lecture-animation-pipeline"
        )
        skill_root.mkdir(parents=True, exist_ok=True)
        (skill_root / "marker.txt").write_text(
            "test skill tree\n",
            encoding="utf-8",
        )
        efficiency = pipeline.load_json(self.efficiency_contract)
        reservation_path = (
            pipeline.episode_efficiency_reservation_ledger(efficiency)
        )
        scenes = [
            "g006_conjugate_path_dependence",
            "g008_cauchy_theorem_local_rectangle",
        ]
        spine_path = self.episode / "episode_visual_spine.json"
        spine = {
            "schema": "lecture-animation-episode-visual-spine-v2",
            "episode": pipeline.relative_or_absolute(
                self.episode,
                self.root,
            ),
            "production_mode": "parallel_batches",
        }
        spine["spine_hash"] = pipeline.object_hash(spine)
        self.write_json(spine_path, spine)
        parent_batch_path = (
            self.episode
            / "review"
            / "v3"
            / "batch_b"
            / "production_batch_repair_v03.json"
        )
        parent_batch = {
            "schema": "lecture-animation-production-batch-v2",
            "batch_id": "batch_b",
            "episode": pipeline.relative_or_absolute(
                self.episode,
                self.root,
            ),
            "scenes": ["g005", *scenes, "g007"],
            "episode_spine_hash": spine["spine_hash"],
            "episode_efficiency_contract_hash": efficiency[
                "contract_hash"
            ],
            "author_id": "old-author",
        }
        parent_batch["batch_hash"] = pipeline.object_hash(parent_batch)
        self.write_json(parent_batch_path, parent_batch)
        old_key = "episode:test:mandatory-repair:batch-b"
        parent_path = (
            parent_batch_path.parent / "continuation.json"
        )
        parent = {
            "schema": (
                pipeline.ANIMATIC_REPAIR_BUDGET_CONTINUATION_SCHEMA
            ),
            "shared_work_key": old_key,
            "exact_scenes": scenes,
            "production_batch": {
                "path": pipeline.relative_or_absolute(
                    parent_batch_path,
                    self.root,
                ),
                "hash": parent_batch["batch_hash"],
                "batch_id": "batch_b",
            },
        }
        parent["continuation_hash"] = pipeline.object_hash(parent)
        self.write_json(parent_path, parent)
        extension_path = parent_path.with_name("extension.json")
        extension = {
            "schema": pipeline.ANIMATIC_REPAIR_TOKEN_EXTENSION_SCHEMA,
            "parent_continuation": {
                "path": pipeline.relative_or_absolute(
                    parent_path,
                    self.root,
                ),
                "hash": parent["continuation_hash"],
            },
        }
        extension["extension_hash"] = pipeline.object_hash(extension)
        self.write_json(extension_path, extension)
        old_state_paths: dict[str, str] = {}
        for index, scene in enumerate(scenes):
            state_path = (
                self.episode
                / "review"
                / "v3"
                / "old"
                / f"{scene}.json"
            )
            self.write_json(
                state_path,
                {"duration_seconds": 3727.5 + index * 0.37},
            )
            old_state_paths[scene] = str(state_path.resolve())
        old_reservation_id = "reservation:old-consumed-batch-b"
        old_actual = {
            "raw_input_plus_output_tokens": 12_049_777,
            "uncached_input_tokens": 269_861,
            "output_tokens": 44_620,
            "reasoning_tokens": 11_860,
        }
        ledger = pipeline.empty_efficiency_reservation_ledger(efficiency)
        ledger.pop("ledger_hash")
        ledger["reservations"] = {
            old_reservation_id: {
                "reservation_id": old_reservation_id,
                "status": "released",
                "shared_work_key": old_key,
                "actual": old_actual,
                "wrapper_state_paths": old_state_paths,
            }
        }
        ledger["animatic_repair_budget_continuations"] = {
            old_key: {
                "shared_work_key": old_key,
                "status": "consumed",
                "continuation_hash": parent["continuation_hash"],
                "production_batch_hash": parent_batch["batch_hash"],
                "batch_id": "batch_b",
            }
        }
        ledger["animatic_repair_token_extensions"] = {
            old_key: {
                "shared_work_key": old_key,
                "status": "consumed",
                "extension_hash": extension["extension_hash"],
            }
        }
        ledger["revision"] = 8
        ledger["ledger_hash"] = pipeline.object_hash(ledger)
        self.write_json(reservation_path, ledger)
        proposal_path = (
            self.episode
            / "review"
            / "evolution"
            / "proposals"
            / "synthetic_independent_review_repair_round.md"
        )
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text(
            "Frozen independent-review repair round design.\n",
            encoding="utf-8",
        )
        issue_paths: dict[str, Path] = {}
        report_paths: dict[str, Path] = {}
        candidate_paths: dict[str, Path] = {}
        source_roots: dict[str, Path] = {}
        for index, scene in enumerate(scenes):
            candidate_path = (
                self.episode
                / "review"
                / "v3"
                / scene
                / "animatic_v03.mp4"
            )
            candidate_path.parent.mkdir(parents=True, exist_ok=True)
            candidate_path.write_bytes(
                f"candidate-{scene}".encode()
            )
            candidate_paths[scene] = candidate_path
            report_path = candidate_path.with_name(
                "independent_review_v03.md"
            )
            report_path.write_text(
                f"# Review {scene}\n\nVerdict: revise.\n",
                encoding="utf-8",
            )
            report_paths[scene] = report_path
            issue_path = (
                self.episode
                / "review"
                / "issues"
                / f"{scene}-v03.json"
            )
            issue = {
                "schema": "lecture-animation-review-issue-v1",
                "issue_id": f"{scene}-v03",
                "scene_slug": scene,
                "status": "open",
                "reviewer": "historical-discovery-reviewer-v03",
                "candidate": {
                    "path": pipeline.relative_or_absolute(
                        candidate_path,
                        self.root,
                    ),
                    "sha256": hashlib.sha256(
                        candidate_path.read_bytes()
                    ).hexdigest(),
                },
            }
            self.write_json(issue_path, issue)
            issue_paths[scene] = issue_path
            source_root = (
                self.root
                / "worktrees"
                / "old-batch-b"
                / "videos"
                / self.episode.name
                / "src"
                / "scenes"
                / scene
            )
            source_root.mkdir(parents=True, exist_ok=True)
            (source_root / "scene.py").write_text(
                f"SCENE = {index}\n",
                encoding="utf-8",
            )
            source_roots[scene] = source_root
        control_root = (
            self.episode
            / "review"
            / "v4"
            / "batch_b_independent_repair_r01"
        )
        output_roots = {
            scene: self.episode / "review" / "v4" / scene
            for scene in scenes
        }
        args = SimpleNamespace(
            repo_root=str(self.root),
            episode=str(self.episode),
            efficiency_contract=str(self.efficiency_contract),
            episode_spine=str(spine_path),
            parent_repair_batch=str(parent_batch_path),
            parent_continuation=str(parent_path),
            parent_extension=str(extension_path),
            design_authority=str(proposal_path),
            batch_lineage_root="batch_b",
            consumed_shared_work_key=old_key,
            released_reservation_id=old_reservation_id,
            authorizing_agent_id="/root",
            repair_author_agent_id="repair-author-v04",
            planned_verifier_agent_id="future-reviewer-v04",
            author_model="test-model",
            scenes=",".join(scenes),
            shared_work_key=(
                "episode:test:independent-review-repair:batch-b:r01"
            ),
            classification=[
                f"{scenes[0]}=incomplete_fix",
                f"{scenes[1]}=preexisting_missed",
            ],
            issue=[
                f"{scene}={issue_paths[scene]}" for scene in scenes
            ],
            review_report=[
                f"{scene}={report_paths[scene]}" for scene in scenes
            ],
            rejected_candidate=[
                f"{scene}={candidate_paths[scene]}" for scene in scenes
            ],
            source_root=[
                f"{scene}={source_roots[scene]}" for scene in scenes
            ],
            allowed_output_root=[
                f"{scene}={output_roots[scene]}" for scene in scenes
            ],
            control_root=str(control_root),
            supervisor_output=str(control_root / "supervisor.json"),
            production_batch_output=str(
                control_root / "production_batch.json"
            ),
            round_state_output=str(
                control_root / "round_state.json"
            ),
            expires_hours=6.0,
            output=str(control_root / "authority.json"),
        )
        return {
            "args": args,
            "scenes": scenes,
            "efficiency": efficiency,
            "reservation_path": reservation_path,
            "proposal_path": proposal_path,
            "issue_paths": issue_paths,
            "report_paths": report_paths,
            "candidate_paths": candidate_paths,
            "source_roots": source_roots,
            "control_root": control_root,
            "output_roots": output_roots,
        }

    def _terminal_abandoned_independent_review_repair_round(
        self,
    ) -> dict[str, object]:
        fixture = self._independent_review_repair_round_fixture()
        args = fixture["args"]
        assert isinstance(args, SimpleNamespace)
        scenes = fixture["scenes"]
        assert isinstance(scenes, list)
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.command_authorize_independent_review_repair_round(
                args
            )
        authority_path = Path(args.output)
        control_root = Path(fixture["control_root"])
        round_state_path = control_root / "round_state.json"
        wrapper_paths: dict[str, Path] = {}
        for scene in scenes:
            state_path = control_root / f"{scene}.json"
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.command_start_independent_review_repair_round_wrapper(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        authority=str(authority_path),
                        round_state=str(round_state_path),
                        state=str(state_path),
                        scene_slug=scene,
                        actor_agent_id="repair-author-v04",
                        actor_model="test-model",
                        reasoning_effort="high",
                        run_id=f"repair-r01-{scene}",
                        active_seconds_allocation=1800,
                        raw_token_allocation=1_500_000,
                        uncached_input_token_allocation=100_000,
                        output_token_allocation=20_000,
                        reasoning_token_allocation=8_000,
                        usage_file=str(
                            self.root / "missing-token-usage.jsonl"
                        ),
                    )
                )
            wrapper_paths[scene] = state_path
        for scene in scenes:
            state_path = wrapper_paths[scene]
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.command_end_independent_review_repair_round_wrapper(
                    SimpleNamespace(
                        repo_root=str(self.root),
                        authority=str(authority_path),
                        round_state=str(round_state_path),
                        state=str(state_path),
                        artifact_result="abandoned",
                        artifact=[],
                    )
                )
        return {
            **fixture,
            "authority_path": authority_path,
            "round_state_path": round_state_path,
            "wrapper_paths": wrapper_paths,
        }

    def _fresh_independent_review_bundle(
        self,
        *,
        authority_path: Path,
        final_receipt_path: Path,
        verdict: str,
    ) -> list[Path]:
        authority = pipeline.load_json(authority_path)
        receipt = pipeline.load_json(final_receipt_path)
        fresh_root = pipeline.resolve_stored_path(
            authority["fresh_review_root"],
            self.root,
        )
        fresh_root.mkdir(parents=True, exist_ok=True)
        layer_names = (
            "layout",
            "math_object",
            "timing_attention",
            "novice_causality",
            "visual_finish",
        )
        evidence_paths: list[Path] = []
        five_layers: dict[str, list[dict[str, str]]] = {}
        for layer in layer_names:
            path = fresh_root / f"{layer}.md"
            path.write_text(
                f"Fresh post-finalization {layer} evidence.\n",
                encoding="utf-8",
            )
            evidence_paths.append(path)
            snapshot = pipeline.artifact_snapshot(path, self.root)
            five_layers[layer] = [
                {
                    "path": snapshot["path"],
                    "sha256": snapshot["sha256"],
                    "finding": f"{layer} checked against both candidates",
                }
            ]
        created_at = (
            datetime.fromisoformat(receipt["created_at"])
            + timedelta(seconds=1)
        ).isoformat(timespec="seconds")
        wrapper_results = receipt["wrapper_results"]
        submission = {
            "schema": (
                pipeline.INDEPENDENT_REVIEW_REPAIR_ROUND_FRESH_REVIEW_SCHEMA
            ),
            "created_at": created_at,
            "reviewer_agent_id": authority[
                "planned_verifier_agent_id"
            ],
            "repair_author_agent_id": authority[
                "repair_author_agent_id"
            ],
            "author_recused": True,
            "verdict": verdict,
            "final_receipt": {
                "path": pipeline.relative_or_absolute(
                    final_receipt_path,
                    self.root,
                ),
                "hash": receipt["receipt_hash"],
            },
            "wrapper_hashes_by_scene": {
                row["scene_slug"]: row["wrapper_hash"]
                for row in wrapper_results
            },
            "candidate_hashes_by_scene": {
                row["scene_slug"]: row["artifact_snapshots"][0][
                    "sha256"
                ]
                for row in wrapper_results
            },
            "five_layer_review": five_layers,
        }
        submission["submission_hash"] = pipeline.object_hash(submission)
        submission_path = fresh_root / "fresh_review_submission.json"
        self.write_json(submission_path, submission)
        return [*evidence_paths, submission_path]

    def test_independent_review_repair_authority_rejects_clone_partial_symlink_and_tamper(
        self,
    ) -> None:
        fixture = self._independent_review_repair_round_fixture()
        args = fixture["args"]
        assert isinstance(args, SimpleNamespace)
        scenes = fixture["scenes"]
        assert isinstance(scenes, list)
        issue_paths = fixture["issue_paths"]
        assert isinstance(issue_paths, dict)

        cloned_issue = (
            self.episode / "review" / "issues" / "cloned-issue.json"
        )
        cloned_issue.write_bytes(Path(issue_paths[scenes[0]]).read_bytes())
        clone_args = SimpleNamespace(**vars(args))
        clone_args.issue = [
            (
                f"{scene}="
                f"{cloned_issue if scene == scenes[0] else issue_paths[scene]}"
            )
            for scene in scenes
        ]
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "stale, closed, cloned",
        ):
            pipeline.command_authorize_independent_review_repair_round(
                clone_args
            )

        partial_path = Path(args.output)
        partial_path.parent.mkdir(parents=True)
        partial_path.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "authorization is partial",
        ):
            pipeline.command_authorize_independent_review_repair_round(
                args
            )
        partial_path.unlink()

        symlink_target = self.episode / "review" / "v4" / "real-target"
        symlink_target.mkdir(parents=True)
        symlink_root = self.episode / "review" / "v4" / "linked-root"
        symlink_root.symlink_to(symlink_target, target_is_directory=True)
        symlink_args = SimpleNamespace(**vars(args))
        symlink_args.control_root = str(symlink_root)
        symlink_args.supervisor_output = str(symlink_root / "supervisor.json")
        symlink_args.production_batch_output = str(
            symlink_root / "batch.json"
        )
        symlink_args.round_state_output = str(symlink_root / "state.json")
        symlink_args.output = str(symlink_root / "authority.json")
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "symlink",
        ):
            pipeline.command_authorize_independent_review_repair_round(
                symlink_args
            )

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_authorize_independent_review_repair_round(
                    args
                ),
                0,
            )
        ledger_path = Path(fixture["reservation_path"])
        ledger = pipeline.load_json(ledger_path)
        old_reservation_id = args.released_reservation_id
        ledger["reservations"][old_reservation_id]["actual"][
            "raw_input_plus_output_tokens"
        ] -= 1
        ledger.pop("ledger_hash", None)
        ledger["revision"] += 1
        ledger["ledger_hash"] = pipeline.object_hash(ledger)
        self.write_json(ledger_path, ledger)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "idempotent authorization retry diverged",
        ):
            pipeline.command_authorize_independent_review_repair_round(
                args
            )

    def test_independent_review_repair_episode8_policy_is_v2_only_and_reuses_identities(
        self,
    ) -> None:
        policy = (
            pipeline.INDEPENDENT_REVIEW_REPAIR_EP8_BATCH_B_POLICY
        )
        workspace_root = MODULE_PATH.parents[4]
        proposal_path = (
            workspace_root / policy["design_authority_path"]
        )
        self.assertEqual(
            hashlib.sha256(proposal_path.read_bytes()).hexdigest(),
            policy["design_authority_sha256"],
        )
        real_issue_paths = {
            "g006_conjugate_path_dependence": (
                workspace_root
                / "videos/0008-mpm-8-cauchy_integral/review/issues/"
                "independent_g006_remaining_samples_bypass_conjugate_"
                "product_transit_animatic_v03_2026-07-30.json"
            ),
            "g008_cauchy_theorem_local_rectangle": (
                workspace_root
                / "videos/0008-mpm-8-cauchy_integral/review/issues/"
                "independent_g008_cr_zero_equations_preannounced_before_"
                "live_substitution_animatic_v03_2026-07-30.json"
            ),
        }
        for scene, issue_path in real_issue_paths.items():
            issue = pipeline.load_json(issue_path)
            current_issue_sha256 = hashlib.sha256(issue_path.read_bytes()).hexdigest()
            if current_issue_sha256 != policy["issue_sha256"][scene]:
                self.assertIn(
                    issue["status"],
                    {"verified_fixed", "human_approved", "resolved", "mitigated"},
                )
                resolution = issue["resolution_history"][-1]
                self.assertEqual(resolution["previous_status"], "open")
                self.assertEqual(resolution["new_status"], issue["status"])
                self.assertEqual(resolution["authority"], "user_final_episode_review")
            else:
                self.assertEqual(current_issue_sha256, policy["issue_sha256"][scene])
            self.assertEqual(
                issue["reviewer"],
                policy["discovery_reviewers_by_scene"][scene],
            )
            self.assertNotEqual(
                issue["reviewer"],
                policy["planned_verifier_agent_id"],
            )
        authority = {
            "episode": f"videos/{policy['episode']}",
            "batch_lineage_root": policy["batch_lineage_root"],
            "authorizing_agent_id": policy["authorizing_agent_id"],
            "repair_author_agent_id": policy[
                "repair_author_agent_id"
            ],
            "planned_verifier_agent_id": policy[
                "planned_verifier_agent_id"
            ],
            "discovery_reviewers_by_scene": dict(
                policy["discovery_reviewers_by_scene"]
            ),
            "exact_scenes": list(policy["exact_scenes"]),
            "consumed_shared_work_key": policy[
                "consumed_shared_work_key"
            ],
            "design_authority": {
                "path": policy["design_authority_path"],
                "sha256": policy["design_authority_sha256"],
            },
            "released_reservation": {
                "reservation_id": policy[
                    "released_reservation_id"
                ],
                "status": "released",
                "actual": dict(policy["released_actual"]),
                "refund": False,
            },
            "issue_bindings": [
                {
                    "scene_slug": scene,
                    "sha256": policy["issue_sha256"][scene],
                    "classification": policy["classifications"][scene],
                }
                for scene in policy["exact_scenes"]
            ],
            "review_report_bindings": [
                {
                    "scene_slug": scene,
                    "sha256": policy["review_report_sha256"][scene],
                }
                for scene in policy["exact_scenes"]
            ],
            "rejected_candidate_bindings": [
                {
                    "scene_slug": scene,
                    "sha256": policy[
                        "rejected_candidate_sha256"
                    ][scene],
                }
                for scene in policy["exact_scenes"]
            ],
        }
        self.assertEqual(
            pipeline.independent_review_repair_episode_policy_errors(
                authority
            ),
            [],
        )
        negative_mutations = [
            (
                "v1 proposal path",
                lambda row: row["design_authority"].update(
                    {
                        "path": (
                            "videos/0008-mpm-8-cauchy_integral/review/"
                            "evolution/proposals/"
                            "independent_review_repair_round_v1.md"
                        )
                    }
                ),
            ),
            (
                "v1 proposal hash",
                lambda row: row["design_authority"].update(
                    {
                        "sha256": (
                            "c66016e8d4038da61baf4a542efa63072af32c276faef65fa1bbd8f05a8eeb5b"
                        )
                    }
                ),
            ),
            (
                "retired v1 author",
                lambda row: row.update(
                    {
                        "repair_author_agent_id": (
                            "/root/ep8_g006_g008_v04_author"
                        )
                    }
                ),
            ),
            (
                "retired v1 verifier",
                lambda row: row.update(
                    {
                        "planned_verifier_agent_id": (
                            "/root/ep8_review_v03_b"
                        )
                    }
                ),
            ),
        ]
        for label, mutate in negative_mutations:
            attacked = json.loads(json.dumps(authority))
            mutate(attacked)
            with self.subTest(label=label):
                self.assertTrue(
                    pipeline.independent_review_repair_episode_policy_errors(
                        attacked
                    )
                )

    def test_independent_review_repair_unknown_usage_consumes_without_zero_or_refund(
        self,
    ) -> None:
        prepared = (
            self._terminal_abandoned_independent_review_repair_round()
        )
        scenes = prepared["scenes"]
        wrapper_paths = prepared["wrapper_paths"]
        assert isinstance(scenes, list)
        assert isinstance(wrapper_paths, dict)
        control_root = Path(prepared["control_root"])
        phase_log = control_root / "phase_events.jsonl"
        final_receipt = control_root / "final_receipt.json"
        final_args = SimpleNamespace(
            repo_root=str(self.root),
            authority=str(prepared["authority_path"]),
            round_state=str(prepared["round_state_path"]),
            wrapper_state=[
                str(wrapper_paths[scene]) for scene in scenes
            ],
            phase_log=str(phase_log),
            usage_file=None,
            raw_input_plus_output_tokens=None,
            uncached_input_tokens=None,
            output_tokens=None,
            reasoning_tokens=None,
            output=str(final_receipt),
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_finalize_independent_review_repair_round(
                    final_args
                ),
                2,
            )
        receipt = pipeline.load_json(final_receipt)
        self.assertEqual(receipt["budget_result"], "token_unobserved")
        self.assertIsNone(receipt["actual"])
        self.assertFalse(receipt["refund"])
        ledger = pipeline.load_json(Path(prepared["reservation_path"]))
        row = ledger["independent_review_repair_rounds"][
            receipt["lineage_counter_key"]
        ]
        reservation = ledger["reservations"][row["reservation_id"]]
        self.assertEqual(row["status"], "consumed")
        self.assertEqual(reservation["status"], "released")
        self.assertIsNone(reservation["actual"])
        self.assertFalse(reservation["refund"])
        self.assertTrue(
            all(
                pipeline.load_json(path)["status"] == "open"
                for path in prepared["issue_paths"].values()
            )
        )

    def test_independent_review_repair_overrun_and_orphan_event_fail_closed(
        self,
    ) -> None:
        prepared = (
            self._terminal_abandoned_independent_review_repair_round()
        )
        scenes = prepared["scenes"]
        wrapper_paths = prepared["wrapper_paths"]
        assert isinstance(scenes, list)
        assert isinstance(wrapper_paths, dict)
        control_root = Path(prepared["control_root"])
        phase_log = control_root / "phase_events.jsonl"
        first_wrapper = pipeline.load_json(wrapper_paths[scenes[0]])
        phase_log.write_text(
            json.dumps(
                {
                    "event_id": first_wrapper["event_id"],
                    "shared_actual": {"forged": 1},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        final_receipt = control_root / "final_receipt.json"
        final_args = SimpleNamespace(
            repo_root=str(self.root),
            authority=str(prepared["authority_path"]),
            round_state=str(prepared["round_state_path"]),
            wrapper_state=[
                str(wrapper_paths[scene]) for scene in scenes
            ],
            phase_log=str(phase_log),
            usage_file=None,
            raw_input_plus_output_tokens=1_500_001,
            uncached_input_tokens=100_000,
            output_tokens=20_000,
            reasoning_tokens=8_000,
            output=str(final_receipt),
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "event exists without its final receipt",
        ):
            pipeline.command_finalize_independent_review_repair_round(
                final_args
            )
        phase_log.unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_finalize_independent_review_repair_round(
                    final_args
                ),
                2,
            )
        receipt = pipeline.load_json(final_receipt)
        self.assertEqual(receipt["budget_result"], "local_overrun")
        self.assertEqual(
            receipt["actual"]["raw_input_plus_output_tokens"],
            1_500_001,
        )
        smaller_retry = SimpleNamespace(**vars(final_args))
        smaller_retry.raw_input_plus_output_tokens = 1_000
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "cannot replace the sealed shared actual",
        ):
            pipeline.command_finalize_independent_review_repair_round(
                smaller_retry
            )

    def test_independent_review_repair_round_is_one_shot_shared_and_fail_closed(
        self,
    ) -> None:
        fixture = self._independent_review_repair_round_fixture()
        args = fixture["args"]
        assert isinstance(args, SimpleNamespace)
        scenes = fixture["scenes"]
        assert isinstance(scenes, list)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_authorize_independent_review_repair_round(
                    args
                ),
                0,
            )
        authority_path = Path(args.output)
        authority = pipeline.load_json(authority_path)
        self.assertEqual(authority["round_index"], 1)
        self.assertEqual(
            authority["active_seconds_limit"],
            1800,
        )
        self.assertEqual(
            authority["soft_checkpoints"],
            pipeline.INDEPENDENT_REVIEW_REPAIR_ROUND_CHECKPOINTS,
        )
        self.assertEqual(
            authority["design_authority"]["sha256"],
            hashlib.sha256(
                Path(fixture["proposal_path"]).read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(
            authority["released_reservation"]["actual"][
                "raw_input_plus_output_tokens"
            ],
            12_049_777,
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_authorize_independent_review_repair_round(
                    args
                ),
                0,
            )
        reset_args = SimpleNamespace(**vars(args))
        reset_args.control_root = str(
            self.episode / "review" / "v4" / "new-thread-reset"
        )
        reset_args.supervisor_output = str(
            Path(reset_args.control_root) / "supervisor.json"
        )
        reset_args.production_batch_output = str(
            Path(reset_args.control_root) / "batch.json"
        )
        reset_args.round_state_output = str(
            Path(reset_args.control_root) / "state.json"
        )
        reset_args.output = str(
            Path(reset_args.control_root) / "authority.json"
        )
        reset_args.shared_work_key = "new-thread-new-key"
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "already exists for this original batch lineage",
        ):
            pipeline.command_authorize_independent_review_repair_round(
                reset_args
            )
        control_root = Path(fixture["control_root"])
        round_state_path = control_root / "round_state.json"
        wrapper_paths: dict[str, Path] = {}
        first_start = None
        for index, scene in enumerate(scenes):
            state_path = control_root / f"{scene}.json"
            start_args = SimpleNamespace(
                repo_root=str(self.root),
                authority=str(authority_path),
                round_state=str(round_state_path),
                state=str(state_path),
                scene_slug=scene,
                actor_agent_id="repair-author-v04",
                actor_model="test-model",
                reasoning_effort="high",
                run_id=f"repair-r01-{scene}",
                active_seconds_allocation=1501,
                raw_token_allocation=1_500_000,
                uncached_input_token_allocation=100_000,
                output_token_allocation=20_000,
                reasoning_token_allocation=8_000,
                usage_file=None,
            )
            if index == 0:
                first_start = start_args
            else:
                mismatch = SimpleNamespace(**vars(start_args))
                mismatch.output_token_allocation = 19_999
                with self.assertRaisesRegex(
                    pipeline.PipelineError,
                    "one allocation signature",
                ):
                    pipeline.command_start_independent_review_repair_round_wrapper(
                        mismatch
                    )
                model_drift = SimpleNamespace(**vars(start_args))
                model_drift.actor_model = "different-model"
                with self.assertRaisesRegex(
                    pipeline.PipelineError,
                    "allocation signature",
                ):
                    pipeline.command_start_independent_review_repair_round_wrapper(
                        model_drift
                    )
                reasoning_drift = SimpleNamespace(**vars(start_args))
                reasoning_drift.reasoning_effort = "low"
                with self.assertRaisesRegex(
                    pipeline.PipelineError,
                    "allocation signature",
                ):
                    pipeline.command_start_independent_review_repair_round_wrapper(
                        reasoning_drift
                    )
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    pipeline.command_start_independent_review_repair_round_wrapper(
                        start_args
                    ),
                    0,
                )
            wrapper_paths[scene] = state_path
        assert first_start is not None
        over_active = SimpleNamespace(**vars(first_start))
        over_active.state = str(control_root / "too-long.json")
        over_active.active_seconds_allocation = 1801
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "1800-second",
        ):
            pipeline.command_start_independent_review_repair_round_wrapper(
                over_active
            )
        output_roots = fixture["output_roots"]
        assert isinstance(output_roots, dict)
        source_bindings: list[str] = []
        artifact_paths: dict[str, list[Path]] = {}
        for scene in scenes:
            output_root = Path(output_roots[scene])
            source_root = output_root / "source"
            source_root.mkdir(parents=True)
            (source_root / "scene.py").write_text(
                f"# repaired {scene}\n",
                encoding="utf-8",
            )
            source_bindings.append(f"{scene}={source_root}")
            animatic = output_root / "animatic_v04.mp4"
            self_review = output_root / "self_review.md"
            animatic.write_bytes(f"v04-{scene}".encode())
            self_review.write_text(
                f"Self-review for {scene}.\n",
                encoding="utf-8",
            )
            artifact_paths[scene] = [animatic, self_review]
        late_checkpoint = SimpleNamespace(
            repo_root=str(self.root),
            authority=str(authority_path),
            round_state=str(round_state_path),
            checkpoint_seconds=300,
            elapsed_seconds=301,
            current_source_root=source_bindings,
            evidence=["late attack"],
            output=str(control_root / "checkpoint_0300.json"),
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "late or backdated",
        ):
            pipeline.command_record_independent_review_repair_round_checkpoint(
                late_checkpoint
            )
        for seconds in (300, 600, 1200, 1500, 1800):
            checkpoint_args = SimpleNamespace(
                **{
                    **vars(late_checkpoint),
                    "checkpoint_seconds": seconds,
                    "elapsed_seconds": seconds,
                    "evidence": [f"checkpoint {seconds} evidence"],
                    "output": str(
                        control_root / f"checkpoint_{seconds:04d}.json"
                    ),
                }
            )
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    pipeline.command_record_independent_review_repair_round_checkpoint(
                        checkpoint_args
                    ),
                    0,
                )
                self.assertEqual(
                    pipeline.command_record_independent_review_repair_round_checkpoint(
                        checkpoint_args
                    ),
                    0,
                )
            if seconds == 300:
                divergent_checkpoint = SimpleNamespace(
                    **{
                        **vars(checkpoint_args),
                        "evidence": ["replacement evidence attack"],
                    }
                )
                with self.assertRaisesRegex(
                    pipeline.PipelineError,
                    "divergent retry",
                ):
                    pipeline.command_record_independent_review_repair_round_checkpoint(
                        divergent_checkpoint
                    )
        first_scene = scenes[0]
        for index, scene in enumerate(scenes):
            end_args = SimpleNamespace(
                repo_root=str(self.root),
                authority=str(authority_path),
                round_state=str(round_state_path),
                state=str(wrapper_paths[scene]),
                artifact_result="complete",
                artifact=[
                    str(path) for path in artifact_paths[scene]
                ],
            )
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    pipeline.command_end_independent_review_repair_round_wrapper(
                        end_args
                    ),
                    0,
                )
            ledger = pipeline.load_json(
                Path(fixture["reservation_path"])
            )
            round_row = ledger[
                "independent_review_repair_rounds"
            ][authority["lineage_counter_key"]]
            reservation = ledger["reservations"][
                round_row["reservation_id"]
            ]
            self.assertEqual(reservation["status"], "active")
            self.assertIsNone(reservation["actual"])
            if index == 0:
                self.assertEqual(scene, first_scene)
        phase_log = control_root / "phase_events.jsonl"
        final_receipt = control_root / "final_receipt.json"
        final_args = SimpleNamespace(
            repo_root=str(self.root),
            authority=str(authority_path),
            round_state=str(round_state_path),
            wrapper_state=[
                str(wrapper_paths[scene]) for scene in scenes
            ],
            phase_log=str(phase_log),
            usage_file=None,
            raw_input_plus_output_tokens=1_000,
            uncached_input_tokens=500,
            output_tokens=200,
            reasoning_tokens=100,
            output=str(final_receipt),
        )
        checkpoint_1800 = control_root / "checkpoint_1800.json"
        checkpoint_1800_bytes = checkpoint_1800.read_bytes()
        checkpoint_1800.unlink()
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "checkpoint chain failed",
        ):
            pipeline.command_finalize_independent_review_repair_round(
                final_args
            )
        checkpoint_1800.write_bytes(checkpoint_1800_bytes)
        checkpoint_1200 = control_root / "checkpoint_1200.json"
        checkpoint_1200_bytes = checkpoint_1200.read_bytes()
        attacked_checkpoint = pipeline.load_json(checkpoint_1200)
        attacked_checkpoint["previous_checkpoint_hash"] = "forged-link"
        attacked_checkpoint.pop("checkpoint_hash", None)
        attacked_checkpoint["checkpoint_hash"] = pipeline.object_hash(
            attacked_checkpoint
        )
        self.write_json(checkpoint_1200, attacked_checkpoint)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "checkpoint chain failed",
        ):
            pipeline.command_finalize_independent_review_repair_round(
                final_args
            )
        checkpoint_1200.write_bytes(checkpoint_1200_bytes)
        chain_authority = pipeline.load_json(authority_path)
        chain_state = pipeline.load_json(round_state_path)
        chain_ledger = pipeline.load_json(
            Path(fixture["reservation_path"])
        )
        forged_state = json.loads(json.dumps(chain_state))
        forged_state["checkpoint_chain"][-1][
            "checkpoint_hash"
        ] = "forged-state-hash"
        self.assertTrue(
            pipeline.validate_independent_review_repair_checkpoint_chain(
                authority=chain_authority,
                round_state=forged_state,
                ledger=chain_ledger,
                repo_root=self.root,
                require_complete=True,
            )
        )
        forged_ledger = json.loads(json.dumps(chain_ledger))
        forged_ledger["independent_review_repair_rounds"][
            chain_authority["lineage_counter_key"]
        ]["checkpoint_hashes"][-1] = "forged-ledger-hash"
        self.assertTrue(
            pipeline.validate_independent_review_repair_checkpoint_chain(
                authority=chain_authority,
                round_state=chain_state,
                ledger=forged_ledger,
                repo_root=self.root,
                require_complete=True,
            )
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_finalize_independent_review_repair_round(
                    final_args
                ),
                0,
            )
        ledger = pipeline.load_json(Path(fixture["reservation_path"]))
        row = ledger["independent_review_repair_rounds"][
            authority["lineage_counter_key"]
        ]
        reservation = ledger["reservations"][row["reservation_id"]]
        self.assertEqual(reservation["status"], "released")
        self.assertEqual(
            reservation["actual"][
                "raw_input_plus_output_tokens"
            ],
            1_000,
        )
        self.assertFalse(reservation["refund"])
        events = pipeline.event_rows(phase_log)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["shared_actual"], events[1]["shared_actual"])
        self.assertEqual(
            events[0]["accounting_identity"],
            events[1]["accounting_identity"],
        )
        fresh_review_paths = self._fresh_independent_review_bundle(
            authority_path=authority_path,
            final_receipt_path=final_receipt,
            verdict="revise",
        )
        result_args = SimpleNamespace(
            repo_root=str(self.root),
            authority=str(authority_path),
            round_state=str(round_state_path),
            final_receipt=str(final_receipt),
            reviewer_agent_id="future-reviewer-v04",
            review_artifact=[
                str(path) for path in fresh_review_paths
            ],
            verdict="revise",
            output=str(control_root / "review_result.json"),
        )
        old_report_args = SimpleNamespace(**vars(result_args))
        old_report_args.review_artifact = [
            str(next(iter(fixture["report_paths"].values())))
        ]
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "sealed fresh review root",
        ):
            pipeline.command_record_independent_review_repair_round_result(
                old_report_args
            )
        forged_receipt_path = control_root / "forged_final_receipt.json"
        forged_receipt = pipeline.load_json(final_receipt)
        forged_receipt["actual"][
            "raw_input_plus_output_tokens"
        ] = 42
        forged_receipt.pop("receipt_hash", None)
        forged_receipt["receipt_hash"] = pipeline.object_hash(
            forged_receipt
        )
        self.write_json(forged_receipt_path, forged_receipt)
        forged_path_args = SimpleNamespace(**vars(result_args))
        forged_path_args.final_receipt = str(forged_receipt_path)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "alternate final receipt path",
        ):
            pipeline.command_record_independent_review_repair_round_result(
                forged_path_args
            )
        receipt_bytes = final_receipt.read_bytes()
        self.write_json(final_receipt, forged_receipt)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "exact consumed final receipt",
        ):
            pipeline.command_record_independent_review_repair_round_result(
                result_args
            )
        final_receipt.write_bytes(receipt_bytes)
        reservation_path = Path(fixture["reservation_path"])
        ledger_bytes = reservation_path.read_bytes()
        attacked_ledger = pipeline.load_json(reservation_path)
        attacked_row = attacked_ledger[
            "independent_review_repair_rounds"
        ][authority["lineage_counter_key"]]
        attacked_row.pop("final_receipt_hash", None)
        attacked_ledger.pop("ledger_hash", None)
        attacked_ledger["revision"] += 1
        attacked_ledger["ledger_hash"] = pipeline.object_hash(
            attacked_ledger
        )
        self.write_json(reservation_path, attacked_ledger)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "exact consumed final receipt",
        ):
            pipeline.command_record_independent_review_repair_round_result(
                result_args
            )
        reservation_path.write_bytes(ledger_bytes)
        phase_log_bytes = phase_log.read_bytes()
        phase_lines = phase_log_bytes.splitlines(keepends=True)
        phase_log.write_bytes(b"".join(phase_lines[:1]))
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "exact consumed final receipt",
        ):
            pipeline.command_record_independent_review_repair_round_result(
                result_args
            )
        phase_log.write_bytes(phase_log_bytes)
        fresh_review_paths = self._fresh_independent_review_bundle(
            authority_path=authority_path,
            final_receipt_path=final_receipt,
            verdict="revise",
        )
        result_args.review_artifact = [
            str(path) for path in fresh_review_paths
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_record_independent_review_repair_round_result(
                    result_args
                ),
                2,
            )
        result = pipeline.load_json(Path(result_args.output))
        self.assertEqual(
            result["terminal_state"],
            "root_cause_replan_required",
        )
        self.assertFalse(result["automatic_next_round_authorized"])

    def _time_governed_override_fixture(self) -> dict[str, Path | dict]:
        """Build a small, isolated v2 episode with an immutable old overrun."""
        episode = self.root / "videos" / "0009-mpm-9-singularities_residues"
        episode.mkdir(parents=True, exist_ok=True)
        efficiency_path = (
            episode / "review" / "evolution" / "episode_efficiency_contract.json"
        )
        efficiency = pipeline.episode_efficiency_contract_data(
            self.root,
            episode,
            SimpleNamespace(
                episode_target_hours=8.0,
                retrospective_reserve_minutes=45.0,
                raw_token_budget=50_000_000,
                uncached_input_token_budget=2_000_000,
                output_token_budget=300_000,
                reasoning_token_budget=100_000,
                token_budget_warning_fraction=0.75,
                max_false_passes=0,
                max_known_regression_recurrences=0,
                max_human_issue_scene_rate=0.25,
                workflow_gate_version=2,
            ),
        )
        self.write_json(efficiency_path, efficiency)
        ledger_path = pipeline.episode_efficiency_reservation_ledger(efficiency)
        self.write_json(
            ledger_path,
            pipeline.empty_efficiency_reservation_ledger(efficiency),
        )
        central_log = pipeline.episode_efficiency_central_log(efficiency)
        pipeline.append_jsonl(
            central_log,
            {
                "schema": "lecture-animation-phase-event-v2",
                "event_id": "phase:ep9-historical-outer-overrun",
                "phase_instance_id": "phase-instance:ep9-historical-outer-overrun",
                "scene_slug": "episode",
                "phase": "design",
                "phase_purpose": "global_spine_and_batch_handoffs",
                "result": "completed",
                "started_at": "2026-08-01T00:00:00+00:00",
                "ended_at": "2026-08-01T00:00:01+00:00",
                "duration_seconds": 1.0,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 300_001,
                "reasoning_tokens": 1,
                "token_observed": True,
                "token_source_kind": "manual",
                "token_allocation_exceeded": ["output_tokens"],
            },
        )
        authority_path = episode / "review" / "evolution" / "user-authority.json"
        self.write_json(
            authority_path,
            {
                "schema": "lecture-animation-user-authority-v1",
                "decision": "authorize",
                "episode": pipeline.relative_or_absolute(episode, self.root),
                "exact_user_text": "视频优先；不能 bypass",
                "preserve_existing_overage_evidence": True,
                "quality_gates_unchanged": True,
                "task_caps_unchanged": True,
            },
        )
        parent_path = episode / "review" / "evolution" / "parent-contract.json"
        parent = {
            "schema": "lecture-animation-time-governed-parent-v1",
            "status": "active",
            "episode": pipeline.relative_or_absolute(episode, self.root),
            "purpose": "video_priority_continuation",
            "lineage_root": "ep9-overrun-root",
        }
        parent["contract_hash"] = pipeline.object_hash(parent)
        self.write_json(parent_path, parent)
        supervisor_path = episode / "review" / "v2" / "supervisor_session.json"
        supervisor = {
            "schema": "lecture-animation-supervisor-session-v2",
            "session_id": "ep9-test-supervisor",
            "supervisor_agent_id": "/root",
            "assignments": {
                "/root/ep9-author": {
                    "state": "active",
                    "role": "animation_author",
                    "task_key": "ep9-batch-a",
                    "scope": "g001",
                    "model": "gpt-5.6-luna (reasoning_effort=max)",
                }
            },
        }
        supervisor["session_hash"] = pipeline.object_hash(supervisor)
        self.write_json(supervisor_path, supervisor)
        batch_path = episode / "review" / "v2" / "batch-a" / "production_batch.json"
        batch = {
            "schema": "lecture-animation-production-batch-v2",
            "episode": pipeline.relative_or_absolute(episode, self.root),
            "batch_id": "ep9-batch-a",
            "scenes": ["g001"],
            "author_id": "/root/ep9-author",
            "supervisor_session_hash": "pending",
            "grant_hash": "pending",
            "actor_model": "gpt-5.6-luna",
            "actor_role": "animation_author",
            "reasoning_effort": "max",
        }
        batch["supervisor_session_hash"] = supervisor["session_hash"]
        batch["grant_hash"] = pipeline.validate_supervisor_production_grant(
            supervisor,
            batch["author_id"],
            batch["batch_id"],
        )["grant_hash"]
        batch["batch_hash"] = pipeline.object_hash(batch)
        self.write_json(batch_path, batch)
        replacement_path = episode / "review" / "evolution" / "replacement-authorization.json"
        replacement = {
            "schema": pipeline.TIME_GOVERNED_REPLACEMENT_AUTH_SCHEMA,
            "status": "active",
            "episode": pipeline.relative_or_absolute(episode, self.root),
            "replacement_agent_id": "/root/ep9-author",
            "actor_model": "gpt-5.6-luna",
            "actor_role": "animation_author",
            "reasoning_effort": "max",
            "parent_contract_hash": parent["contract_hash"],
            "production_batch_hashes": [batch["batch_hash"]],
        }
        replacement["authorization_hash"] = pipeline.object_hash(replacement)
        self.write_json(replacement_path, replacement)
        metric_profile_path = (
            episode
            / "review"
            / "evolution"
            / "metric-policy-profile.json"
        )
        metric_profile = pipeline.metric_policy_profile_data(
            self.root,
            episode,
            policy_id="ep9-video-priority-metric-policy-r01",
            parent_contract_path=parent_path,
            user_authority_path=authority_path,
            phases=["design"],
            scenes=["g001"],
            actor_model="gpt-5.6-luna",
            actor_role="animation_author",
            reasoning_effort="max",
            active_seconds=120,
            expires_hours=1,
            metric_modes={
                "token_budget": "off",
                "active_time": "enforce",
            },
        )
        self.write_json(metric_profile_path, metric_profile)
        spec_path = episode / "review" / "evolution" / "time-override-spec.json"
        token_allowance = {
            "raw_input_plus_output_tokens": 500_000,
            "uncached_input_tokens": 100_000,
            "output_tokens": 400_000,
            "reasoning_tokens": 20_000,
        }
        self.write_json(
            spec_path,
            {
                "override_id": "ep9-video-priority-r01",
                "phase_scopes": [
                    "design:scene_detailed_visual_plan_and_audio:g001"
                ],
                "token_budget_mode": pipeline.TIME_GOVERNED_TOKEN_BUDGET_MODE,
                "active_seconds_allowance": 120,
                "phase_active_seconds_allowance": {"design": 120},
                "authorized_overflow_fields": [
                    # observed-only continuation never bridges token totals
                ],
                "expires_hours": 1,
            },
        )
        override_path = episode / "review" / "evolution" / "time-override.json"
        authorize_args = SimpleNamespace(
            repo_root=str(self.root),
            episode=str(episode),
            efficiency_contract=str(efficiency_path),
            user_authority=str(authority_path),
            metric_policy_profile=str(metric_profile_path),
            parent_contract=str(parent_path),
            replacement_authorization=str(replacement_path),
            production_batch=[str(batch_path)],
            supervisor_session=str(supervisor_path),
            spec=str(spec_path),
            override_id="",
            phase_scope=[],
            token_allowance=[],
            phase_token_allowance=[],
            active_seconds_allowance=None,
            phase_active_seconds=[],
            authorized_overflow_field=[],
            expires_hours=None,
            output=str(override_path),
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_authorize_time_governed_budget_override(
                    authorize_args
                ),
                0,
            )
        override = pipeline.load_json(override_path)
        return {
            "episode": episode,
            "efficiency_path": efficiency_path,
            "efficiency": efficiency,
            "ledger_path": ledger_path,
            "central_log": central_log,
            "batch_path": batch_path,
            "override_path": override_path,
            "override": override,
            "metric_profile_path": metric_profile_path,
        }

    def test_metric_policy_switchboard_keeps_operational_modes_independent(self) -> None:
        fixture = self._time_governed_override_fixture()
        parent_path = fixture["episode"] / "review" / "evolution" / "parent-contract.json"
        authority_path = fixture["episode"] / "review" / "evolution" / "user-authority.json"
        profile = pipeline.metric_policy_profile_data(
            self.root,
            fixture["episode"],
            policy_id="ep9-independent-metric-switches-r01",
            parent_contract_path=parent_path,
            user_authority_path=authority_path,
            phases=["design"],
            scenes=["g001"],
            actor_model="gpt-5.6-luna",
            actor_role="animation_author",
            reasoning_effort="max",
            active_seconds=120,
            expires_hours=1,
            metric_modes={
                "token_budget": "observe",
                "active_time": "observe",
                "telemetry": "off",
            },
        )
        self.assertEqual(
            pipeline.validate_metric_policy_profile(
                profile,
                repo_root=self.root,
                episode=fixture["episode"],
            ),
            [],
        )
        self.assertEqual(profile["metrics"]["token_budget"]["mode"], "observe")
        self.assertEqual(profile["metrics"]["active_time"]["mode"], "observe")
        self.assertEqual(profile["metrics"]["telemetry"]["mode"], "off")
        self.assertEqual(profile["metrics"]["quality_gates"]["mode"], "enforce")

        episode_profile_path = (
            fixture["episode"]
            / "review"
            / "evolution"
            / "episode-wide-metric-policy.json"
        )
        episode_profile = pipeline.metric_policy_profile_data(
            self.root,
            fixture["episode"],
            policy_id="ep9-episode-wide-switchboard-r01",
            parent_contract_path=parent_path,
            user_authority_path=authority_path,
            phases=["design", "authoring", "render", "tts", "asr"],
            scenes=["*"],
            actor_model="*",
            actor_role="*",
            reasoning_effort="*",
            active_seconds=8 * 3600,
            expires_hours=12,
        )
        self.write_json(episode_profile_path, episode_profile)
        self.assertEqual(
            {
                metric: episode_profile["metrics"][metric]["mode"]
                for metric in (
                    "token_budget",
                    "active_time",
                    "telemetry",
                    "quality_gates",
                    "user_review",
                )
            },
            {
                "token_budget": "enforce",
                "active_time": "observe",
                "telemetry": "observe",
                "quality_gates": "enforce",
                "user_review": "enforce",
            },
        )
        self.assertEqual(
            pipeline.validate_metric_policy_profile(
                episode_profile,
                repo_root=self.root,
                episode=fixture["episode"],
            ),
            [],
        )
        wildcard_binding = pipeline.resolve_metric_policy_profile(
            episode_profile_path,
            repo_root=self.root,
            episode=fixture["episode"],
            phase="tts",
            scene_slug="g001",
            actor_model="local:indextts2",
            actor_role="local_synthesis",
            reasoning_effort="none",
        )
        self.assertEqual(
            wildcard_binding["metric_policy_profile_hash"],
            episode_profile["policy_hash"],
        )
        narrow_errors = pipeline.time_governed_metric_policy_errors(
            episode_profile
        )
        self.assertTrue(any("token_budget" in error for error in narrow_errors))
        self.assertTrue(any("exact scene" in error for error in narrow_errors))
        self.assertTrue(any("exact actor_model" in error for error in narrow_errors))
        self.assertTrue(any("four hours" in error for error in narrow_errors))
        self.assertTrue(any("six hours" in error for error in narrow_errors))
        with self.assertRaises(pipeline.PipelineError):
            pipeline.metric_policy_profile_data(
                self.root,
                fixture["episode"],
                policy_id="ep9-invalid-quality-switch-r01",
                parent_contract_path=parent_path,
                user_authority_path=authority_path,
                phases=["design"],
                scenes=["g001"],
                actor_model="gpt-5.6-luna",
                actor_role="animation_author",
                reasoning_effort="max",
                active_seconds=120,
                expires_hours=1,
                metric_modes={"quality_gates": "off"},
            )
        with self.assertRaises(pipeline.PipelineError):
            pipeline.metric_policy_profile_data(
                self.root,
                fixture["episode"],
                policy_id="ep9-invalid-user-review-switch-r01",
                parent_contract_path=parent_path,
                user_authority_path=authority_path,
                phases=["design"],
                scenes=["g001"],
                actor_model="gpt-5.6-luna",
                actor_role="animation_author",
                reasoning_effort="max",
                active_seconds=120,
                expires_hours=1,
                metric_modes={"user_review": "observe"},
            )

        # The generic switchboard may vary operational modes independently,
        # but the time-governed overlay is a deliberately narrower consumer.
        self.assertEqual(
            pipeline.time_governed_metric_policy_errors(
                fixture["override"]["metric_policy_profile_snapshot"][
                    "metrics"
                ]
            ),
            [],
        )
        self.assertEqual(
            pipeline.time_governed_metric_policy_errors(
                fixture["override"]["metric_policy_profile_snapshot"]
            ),
            [],
        )
        observed_only_metrics = {
            key: dict(value)
            for key, value in fixture["override"][
                "metric_policy_profile_snapshot"
            ]["metrics"].items()
        }
        observed_only_metrics["active_time"]["mode"] = "observe"
        self.assertEqual(
            pipeline.time_governed_metric_policy_errors(
                observed_only_metrics
            ),
            ["time-governed metric policy active_time requires mode=enforce"],
        )

    def test_metric_policy_update_is_one_authorized_switchboard_operation(self) -> None:
        fixture = self._time_governed_override_fixture()
        base_path = fixture["metric_profile_path"]
        base = pipeline.load_json(base_path)
        authority_path = fixture["episode"] / "review" / "evolution" / "user-authority-next.json"
        self.write_json(
            authority_path,
            {
                "schema": "lecture-animation-user-authority-v1",
                "decision": "authorize",
                "episode": pipeline.relative_or_absolute(fixture["episode"], self.root),
                "exact_user_text": "本轮只观察 telemetry，token 不计入硬门槛",
                "preserve_existing_overage_evidence": True,
                "quality_gates_unchanged": True,
                "task_caps_unchanged": True,
            },
        )
        updated = pipeline.metric_policy_update_data(
            self.root,
            fixture["episode"],
            base_profile_path=base_path,
            user_authority_path=authority_path,
            policy_id="ep9-independent-metric-switches-r02",
            metric_modes={
                "token_budget": "off",
                "active_time": "on",
                "telemetry": "observe",
            },
            expires_hours=1,
        )
        self.assertEqual(
            pipeline.validate_metric_policy_profile(
                updated,
                repo_root=self.root,
                episode=fixture["episode"],
            ),
            [],
        )
        self.assertEqual(updated["metrics"]["token_budget"]["mode"], "off")
        self.assertEqual(updated["metrics"]["active_time"]["mode"], "enforce")
        self.assertEqual(updated["metrics"]["telemetry"]["mode"], "observe")
        self.assertEqual(
            pipeline.metric_policy_mode(updated, "active_time"),
            "enforce",
        )
        self.assertTrue(pipeline.metric_policy_enforces(updated, "active_time"))
        self.assertFalse(pipeline.metric_policy_enforces(updated, "token_budget"))
        self.assertNotEqual(updated["policy_hash"], base["policy_hash"])

        token_enabled = pipeline.metric_policy_update_data(
            self.root,
            fixture["episode"],
            base_profile_path=base_path,
            user_authority_path=authority_path,
            policy_id="ep9-token-enforced-r01",
            metric_modes={"token_budget": "on"},
            expires_hours=1,
        )
        self.assertEqual(
            token_enabled["metrics"]["token_budget"],
            {
                "mode": "enforce",
                "charge_to_parent": True,
                "telemetry": "required",
            },
        )

        # Updating one switch is a patch, not a reset to global defaults.  A
        # future profile may deliberately enforce token accounting; changing
        # only telemetry must preserve that independent decision.
        enforced_base = dict(base)
        enforced_base["metrics"] = {
            key: dict(value)
            for key, value in base["metrics"].items()
        }
        enforced_base["metrics"]["token_budget"].update(
            {"mode": "enforce", "telemetry": "required", "charge_to_parent": True}
        )
        enforced_base["policy_hash"] = pipeline.object_hash(
            {
                key: value
                for key, value in enforced_base.items()
                if key != "policy_hash"
            }
        )
        enforced_base_path = fixture["episode"] / "review" / "evolution" / "enforced-base-policy.json"
        self.write_json(enforced_base_path, enforced_base)
        patched = pipeline.metric_policy_update_data(
            self.root,
            fixture["episode"],
            base_profile_path=enforced_base_path,
            user_authority_path=authority_path,
            policy_id="ep9-independent-metric-switches-r03",
            metric_modes={"telemetry": "off"},
            expires_hours=1,
        )
        self.assertEqual(patched["metrics"]["token_budget"]["mode"], "enforce")
        self.assertEqual(patched["metrics"]["token_budget"]["telemetry"], "required")
        self.assertTrue(patched["metrics"]["token_budget"]["charge_to_parent"])
        self.assertEqual(patched["metrics"]["telemetry"]["mode"], "off")
        with self.assertRaises(pipeline.PipelineError):
            pipeline.metric_policy_update_data(
                self.root,
                fixture["episode"],
                base_profile_path=base_path,
                user_authority_path=authority_path,
                policy_id="ep9-invalid-hard-gate-r02",
                metric_modes={"quality_gates": "off"},
                expires_hours=1,
            )

        parsed = pipeline.build_parser().parse_args(
            [
                "update-metric-policy",
                "--repo-root",
                str(self.root),
                "--episode",
                str(fixture["episode"]),
                "--base-profile",
                str(base_path),
                "--user-authority",
                str(authority_path),
                "--policy-id",
                "ep9-cli-switch-r01",
                "--metric-mode",
                "active_time=on",
                "--output",
                str(fixture["episode"] / "review" / "evolution" / "cli-policy.json"),
            ]
        )
        self.assertIs(parsed.func, pipeline.command_update_metric_policy)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(parsed.func(parsed), 0)
        cli_policy = pipeline.load_json(Path(parsed.output))
        self.assertEqual(cli_policy["metrics"]["active_time"]["mode"], "enforce")

    def test_standalone_metric_policy_observes_overages_without_blocking(self) -> None:
        fixture = self._time_governed_override_fixture()
        episode = fixture["episode"]
        parent_path = episode / "review" / "evolution" / "parent-contract.json"
        authority_path = episode / "review" / "evolution" / "user-authority.json"
        profile_path = episode / "review" / "evolution" / "standalone-policy.json"
        profile = pipeline.metric_policy_profile_data(
            self.root,
            episode,
            policy_id="ep9-standalone-observe-r01",
            parent_contract_path=parent_path,
            user_authority_path=authority_path,
            phases=["design"],
            scenes=["g001"],
            actor_model="gpt-5.6-luna",
            actor_role="animation_author",
            reasoning_effort="max",
            active_seconds=120,
            expires_hours=1,
            metric_modes={
                "token_budget": "observe",
                "active_time": "observe",
                "telemetry": "off",
            },
        )
        self.write_json(profile_path, profile)
        state_path = episode / "review" / "evolution" / "standalone-state.json"
        start_args = SimpleNamespace(
            repo_root=str(self.root),
            episode=str(episode),
            efficiency_contract=str(fixture["efficiency_path"]),
            run_id="ep9-standalone-g001-design",
            scene_slug="g001",
            production_batch=str(fixture["batch_path"]),
            phase="design",
            phase_purpose="scene_detailed_visual_plan_and_audio",
            time_governed_budget_override=None,
            metric_policy_profile=str(profile_path),
            token_budget_mode=None,
            actor_model="gpt-5.6-luna",
            actor_role="animation_author",
            reasoning_effort="max",
            active_seconds_allocation=1,
            raw_token_allocation=1,
            uncached_input_token_allocation=1,
            output_token_allocation=1,
            reasoning_token_allocation=1,
            prompt_bytes=100,
            artifact_input_bytes=100,
            files_read=2,
            state=str(state_path),
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pipeline.command_phase_start(start_args), 0)
        started = pipeline.load_json(state_path)
        self.assertEqual(started["metric_policy_modes"]["token_budget"], "observe")
        self.assertFalse(started["metric_policy_enforcement"]["token_budget"])
        started.pop("timer_hash", None)
        started["started_at"] = (
            datetime.fromisoformat(started["started_at"])
            - timedelta(seconds=2)
        ).isoformat(timespec="seconds")
        started["timer_hash"] = pipeline.object_hash(started)
        self.write_json(state_path, started)
        phase_log = episode / "review" / "evolution" / "standalone-phases.jsonl"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_phase_end(
                    SimpleNamespace(
                        state=str(state_path),
                        phase_log=str(phase_log),
                        result="completed",
                        manifest_hash="",
                        usage_file=None,
                        input_tokens=0,
                        cached_input_tokens=0,
                        output_tokens=10,
                        reasoning_tokens=1,
                    )
                ),
                0,
            )
        ended = pipeline.load_json(state_path)
        self.assertTrue(
            "PHASE_TOKEN_ALLOCATION_EXCEEDED"
            in ended["efficiency_status_at_end"]["alerts"]
        )
        self.assertTrue(
            "PHASE_ACTIVE_TIME_ALLOCATION_EXCEEDED"
            in ended["efficiency_status_at_end"]["alerts"]
        )
        self.assertFalse(ended["metric_policy_enforced_failure"])
        self.assertIn(
            "PHASE_TOKEN_ALLOCATION_EXCEEDED",
            ended["metric_policy_nonblocking_alerts"],
        )
        self.assertIn(
            "PHASE_ACTIVE_TIME_ALLOCATION_EXCEEDED",
            ended["metric_policy_nonblocking_alerts"],
        )
        event = pipeline.event_rows(phase_log)[-1]
        self.assertTrue(event["token_allocation_exceeded"])
        self.assertEqual(event["metric_policy_modes"]["token_budget"], "observe")

    def test_batch_status_metric_policy_only_softens_operational_alerts(self) -> None:
        alerts = [
            "EPISODE_TOKEN_BUDGET_EXCEEDED",
            "ACTIVE_BUDGET_EXCEEDED",
            "TOKEN_TELEMETRY_INCOMPLETE",
            "KNOWN_HUMAN_REGRESSION_RECURRED",
            "HUMAN_OUTCOME_SCENES_MISSING",
        ]
        enforced, nonblocking = (
            pipeline.metric_policy_operational_alert_partition(
                alerts,
                {
                    "token_budget": "observe",
                    "active_time": "off",
                    "telemetry": "observe",
                    "quality_gates": "enforce",
                    "user_review": "enforce",
                },
            )
        )
        self.assertEqual(enforced, [])
        self.assertEqual(
            nonblocking,
            sorted(alerts[:3]),
        )
        self.assertNotIn("KNOWN_HUMAN_REGRESSION_RECURRED", nonblocking)
        self.assertNotIn("HUMAN_OUTCOME_SCENES_MISSING", nonblocking)
        parsed = pipeline.build_parser().parse_args(
            [
                "batch-status",
                "--batch",
                "batch.json",
                "--metric-policy-profile",
                "metric-policy.json",
            ]
        )
        self.assertEqual(parsed.metric_policy_profile, "metric-policy.json")

    def test_time_governed_override_schema_scope_expiry_and_history_are_bound(self) -> None:
        fixture = self._time_governed_override_fixture()
        override = fixture["override"]
        self.assertEqual(
            pipeline.validate_time_governed_budget_override(
                override,
                repo_root=self.root,
                episode=fixture["episode"],
                efficiency_contract=fixture["efficiency"],
            ),
            [],
        )
        self.assertEqual(
            pipeline.time_governed_override_scope(
                override,
                phase="design",
                phase_purpose="scene_detailed_visual_plan_and_audio",
                scene_slug="g001",
            )["scenes"],
            ["g001"],
        )
        expired = dict(override)
        expired["expires_at"] = "2020-01-01T00:00:00+00:00"
        expired["override_hash"] = pipeline.object_hash(expired)
        expired_errors = pipeline.validate_time_governed_budget_override(
            expired,
            repo_root=self.root,
            episode=fixture["episode"],
            efficiency_contract=fixture["efficiency"],
        )
        self.assertTrue(any("expired" in error for error in expired_errors))
        mutated_rows = pipeline.event_rows(fixture["central_log"])
        mutated_rows[0] = dict(mutated_rows[0])
        mutated_rows[0]["output_tokens"] += 1
        history_errors = pipeline.validate_time_governed_budget_override(
            override,
            repo_root=self.root,
            episode=fixture["episode"],
            efficiency_contract=fixture["efficiency"],
            current_ledger=pipeline.load_json(fixture["ledger_path"]),
            current_rows=mutated_rows,
        )
        self.assertTrue(
            any("historical phase event changed" in error for error in history_errors)
        )

    def test_time_governed_override_phase_start_end_and_parser_are_fail_closed(self) -> None:
        fixture = self._time_governed_override_fixture()
        episode = fixture["episode"]
        override_path = fixture["override_path"]
        old_ledger_bytes = Path(fixture["ledger_path"]).read_bytes()
        parser = pipeline.build_parser()
        parsed = parser.parse_args(
            [
                "phase-start",
                "--episode",
                str(episode),
                "--efficiency-contract",
                str(fixture["efficiency_path"]),
                "--run-id",
                "ep9-test-g001-design",
                "--scene-slug",
                "g001",
                "--production-batch",
                str(fixture["batch_path"]),
                "--phase",
                "design",
                "--phase-purpose",
                "scene_detailed_visual_plan_and_audio",
                "--time-governed-budget-override",
                str(override_path),
                "--metric-policy-profile",
                str(fixture["metric_profile_path"]),
                "--token-budget-mode",
                pipeline.TIME_GOVERNED_TOKEN_BUDGET_MODE,
                "--actor-model",
                "gpt-5.6-luna",
                "--active-seconds-allocation",
                "60",
                "--raw-token-allocation",
                "1000",
                "--uncached-input-token-allocation",
                "1",
                "--output-token-allocation",
                "10",
                "--reasoning-token-allocation",
                "1",
                "--state",
                str(episode / "review" / "evolution" / "design-state.json"),
            ]
        )
        self.assertEqual(parsed.time_governed_budget_override, str(override_path))
        common = dict(
            repo_root=str(self.root),
            episode=str(episode),
            efficiency_contract=str(fixture["efficiency_path"]),
            production_batch=str(fixture["batch_path"]),
            scene_slug="g001",
            phase="design",
            phase_purpose="scene_detailed_visual_plan_and_audio",
            time_governed_budget_override=str(override_path),
            metric_policy_profile=str(fixture["metric_profile_path"]),
            token_budget_mode=pipeline.TIME_GOVERNED_TOKEN_BUDGET_MODE,
            actor_model="gpt-5.6-luna",
            actor_role="animation_author",
            reasoning_effort="max",
            active_seconds_allocation=60,
            raw_token_allocation=None,
            uncached_input_token_allocation=None,
            output_token_allocation=None,
            reasoning_token_allocation=None,
            prompt_bytes=100,
            artifact_input_bytes=100,
            files_read=2,
        )
        state_path = episode / "review" / "evolution" / "design-state.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                pipeline.command_phase_start(
                    SimpleNamespace(
                        **common,
                        run_id="ep9-test-g001-design",
                        state=str(state_path),
                    )
                ),
                0,
            )
        state = pipeline.load_json(state_path)
        self.assertEqual(
            Path(fixture["ledger_path"]).read_bytes(),
            old_ledger_bytes,
            "observed-only phase-start must not rewrite the canonical v4 ledger",
        )
        self.assertTrue(state["time_governed_budget_override_admission_applied"])
        self.assertTrue(
            {"output_tokens"}.issubset(
                set(state["time_governed_original_overflow_fields"])
            )
        )
        local_log = episode / "review" / "evolution" / "design-phases.jsonl"
        self.assertEqual(
                pipeline.command_phase_end(
                    SimpleNamespace(
                        state=str(state_path),
                        phase_log=str(local_log),
                        result="completed",
                        manifest_hash="",
                        usage_file=None,
                        input_tokens=0,
                        cached_input_tokens=0,
                        output_tokens=10,
                        reasoning_tokens=1,
                    )
                ),
                0,
            )
        ended = pipeline.load_json(state_path)
        self.assertEqual(
            Path(fixture["ledger_path"]).read_bytes(),
            old_ledger_bytes,
            "observed-only phase-end must not rewrite the canonical v4 ledger",
        )
        self.assertFalse(ended["time_governed_budget_override_exceeded"])
        central_rows = pipeline.event_rows(fixture["central_log"])
        self.assertEqual(
            central_rows[-1]["schema"],
            pipeline.TIME_GOVERNED_PHASE_INDEX_SCHEMA,
        )
        self.assertTrue(central_rows[-1]["override_hash"])
        override_events = pipeline.event_rows(
            episode / "review" / "evolution" / "episode_time_governed_phase_events.jsonl"
        )
        self.assertFalse(override_events[-1]["time_governed_budget_override_exceeded"])
        ledger = pipeline.load_json(
            episode / "review" / "evolution" / "episode_time_governed_reservations.json"
        )
        self.assertEqual(
            ledger["overrides"][
                fixture["override"]["override_id"]
            ]["status"],
            "active",
        )

        unknown_state = episode / "review" / "evolution" / "design-state-unknown.json"
        unknown_usage = episode / "review" / "evolution" / "missing-token-usage.json"
        # The first completed event occupies this exact scope.  A second
        # phase-start is rejected rather than creating duplicate work; the
        # missing-token policy is checked directly below on an isolated status
        # sample so that the rejection cannot hide the observability rule.
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(
                pipeline.PipelineError,
                "scope already has a phase event",
            ):
                pipeline.command_phase_start(
                    SimpleNamespace(
                        **common,
                        run_id="ep9-test-g001-design-unknown",
                        usage_file=str(unknown_usage),
                        state=str(unknown_state),
                    )
                )
        unknown_rows = [
            {
                "event_id": "unknown-token-sample",
                "time_governed_budget_override_id": fixture["override"]["override_id"],
                "phase": "design",
                "token_observed": False,
                "raw_input_plus_output_tokens": 0,
                "uncached_input_tokens": 0,
                "output_tokens": 0,
                "reasoning_tokens": 0,
                "duration_seconds": 1.0,
            }
        ]
        unknown_status = pipeline.time_governed_override_budget_status(
            fixture["override"],
            rows=unknown_rows,
            ledger={"reservations": {}},
            extra_token_observed=False,
        )
        self.assertEqual(
            Path(fixture["ledger_path"]).read_bytes(),
            old_ledger_bytes,
            "unknown-token observed-only continuation must preserve the v4 ledger bytes",
        )
        self.assertFalse(unknown_rows[-1]["token_observed"])
        self.assertTrue(unknown_status["telemetry_missing"])
        # Token monitoring is explicitly off for this user-authorized
        # continuation: missing token telemetry remains unknown evidence but
        # does not consume or exhaust the time-governed overlay. Active-time
        # limits and all quality gates remain enforced separately.
        self.assertFalse(unknown_status["exceeded"])

    def test_time_governed_overlay_closeout_and_nested_supervisor_lineage_are_bound(self) -> None:
        fixture = self._time_governed_override_fixture()
        supervisor = pipeline.load_json(
            fixture["episode"] / "review" / "v2" / "supervisor_session.json"
        )
        batch = pipeline.load_json(fixture["batch_path"])
        grant = pipeline.validate_supervisor_production_grant(
            supervisor,
            batch["author_id"],
            batch["batch_id"],
        )
        nested = dict(batch)
        nested.update(
            {
                "supervisor_session_hash": None,
                "grant_hash": None,
                "actor_model": None,
                "actor_role": None,
                "reasoning_effort": None,
                "supervisor_binding": {
                    "canonical_session_hash": supervisor["session_hash"],
                    "grant_hash": grant["grant_hash"],
                    "role": grant["role"],
                    "model": "gpt-5.6-luna (reasoning_effort=max)",
                },
            }
        )
        lineage = pipeline.production_batch_lineage(nested)
        self.assertEqual(lineage["supervisor_session_hash"], supervisor["session_hash"])
        self.assertEqual(lineage["grant_hash"], grant["grant_hash"])
        self.assertEqual(lineage["actor_model"], "gpt-5.6-luna")
        self.assertEqual(lineage["reasoning_effort"], "max")
        self.assertEqual(
            pipeline.time_governed_batch_supervisor_lineage_errors(
                nested,
                lineage,
                supervisor,
            ),
            [],
        )
        mismatched = dict(nested)
        mismatched["reasoning_effort"] = "medium"
        mismatched_lineage = pipeline.production_batch_lineage(mismatched)
        self.assertTrue(
            any(
                "reasoning_effort" in error
                for error in pipeline.time_governed_batch_supervisor_lineage_errors(
                    mismatched,
                    mismatched_lineage,
                    supervisor,
                )
            )
        )

    def test_time_governed_overlay_missing_after_central_index_fails_closed(self) -> None:
        fixture = self._time_governed_override_fixture()
        overlay_path = pipeline.time_governed_reservation_ledger_path(
            fixture["episode"]
        )
        overlay_path.unlink()
        pipeline.append_jsonl(
            fixture["central_log"],
            {
                "schema": pipeline.TIME_GOVERNED_PHASE_INDEX_SCHEMA,
                "event_id": "phase:missing-overlay-evidence",
                "event_hash": "unknown",
                "override_id": fixture["override"]["override_id"],
                "override_hash": fixture["override"]["override_hash"],
                "source_event_log": "videos/0009-mpm-9-singularities_residues/review/evolution/episode_time_governed_phase_events.jsonl",
            },
        )
        status = pipeline.time_governed_overlay_close_status(
            self.root,
            fixture["episode"],
            fixture["efficiency"],
        )
        self.assertTrue(status["override_used"])
        self.assertTrue(status["noncompliant"])
        self.assertTrue(any("overlay is missing" in error for error in status["errors"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
