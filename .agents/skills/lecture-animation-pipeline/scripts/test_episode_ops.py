from __future__ import annotations

import json
import hashlib
import io
from pathlib import Path
from contextlib import redirect_stdout
from types import SimpleNamespace
import tempfile
import unittest
import wave

from pipeline_v2_lib.core import PipelineError
from pipeline_v2_lib import engine
from pipeline_v2_lib.episode_ops import (
    _alignment_words,
    _registry_occurrences,
    _rolling_pace,
    _validate_independent_review,
    _validate_pronunciation_binding,
    artifact_snapshot,
    command_episode_preflight,
    command_promote_scene,
    run_episode_preflight,
    run_portability_audit,
    validate_episode_readiness_receipt,
)
from pipeline_v2_lib.metrics import phase_metrics


TEST_TTS_ROUTE_ID = "indextts2-mlx8-zaojian-takagi-seed3407"
CANONICAL_PRONUNCIATION_REGISTRY = (
    Path(__file__).resolve().parents[1]
    / "references/tts-pronunciation-registry.json"
)


def write_tts_mapping_v2(
    *,
    root: Path,
    scene_slug: str,
    formal_script: Path,
    tts_input: Path,
    spoken_forms: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    registry_path = (
        root
        / ".agents/skills/lecture-animation-pipeline/references/tts-pronunciation-registry.json"
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        CANONICAL_PRONUNCIATION_REGISTRY.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    formal_text = formal_script.read_text(encoding="utf-8")
    rows = _registry_occurrences(formal_text, registry)
    replacements = {key.casefold(): value for key, value in (spoken_forms or {}).items()}
    rebuilt: list[str] = []
    prior_end = 0
    for row in rows:
        spoken_form = replacements.get(row["token_key"], row["formal_surface"])
        rebuilt.extend((formal_text[prior_end:row["formal_start"]], spoken_form))
        prior_end = row["formal_end"]
        row["spoken_form"] = spoken_form
        row["replacement_applied"] = spoken_form != row["formal_surface"]
    rebuilt.append(formal_text[prior_end:])
    tts_input.write_text("".join(rebuilt), encoding="utf-8")
    mapping_path = tts_input.with_name(f"{tts_input.stem}_mapping.json")
    mapping_path.write_text(
        json.dumps(
            {
                "schema": "lecture-animation-tts-input-mapping-v2",
                "scene_slug": scene_slug,
                "route_id": TEST_TTS_ROUTE_ID,
                "formal_script_path": str(formal_script.relative_to(root)),
                "formal_script_sha256": hashlib.sha256(
                    formal_script.read_bytes()
                ).hexdigest(),
                "tts_input_path": str(tts_input.relative_to(root)),
                "tts_input_sha256": hashlib.sha256(tts_input.read_bytes()).hexdigest(),
                "occurrences": rows,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return registry_path, mapping_path


def write_screen_text_semantic_contract(
    path: Path,
    semantic_items: list[dict[str, object]] | None = None,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "lecture-animation-screen-text-semantic-contract-v1",
                "semantic_items": semantic_items or [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def mathematical_fixed_ending_contract() -> dict[str, object]:
    return {
        "role": "learner_facing_math_question",
        "learner_job": "让学习者把当前数学关系带入下一步独立判断",
        "math_anchor": "当前数学关系",
        "externalizes_production_intent": False,
    }


class EpisodeOpsTests(unittest.TestCase):
    def test_alignment_pace_uses_one_canonical_word_sequence(self) -> None:
        value = {
            "word_cues": [
                {"text": "一", "start": 0.0, "end": 0.2},
                {"text": "步", "start": 0.5, "end": 0.7},
            ],
            "reader_cues": [
                {"text": "一步", "start": 0.0, "end": 0.7},
            ],
            "raw_alignment": {
                "words": [
                    {"word": "一", "start": 0.0, "end": 0.2},
                    {"word": "步", "start": 0.5, "end": 0.7},
                ]
            },
        }
        words = _alignment_words(value)
        self.assertEqual([row["text"] for row in words], ["一", "步"])
        self.assertAlmostEqual(_rolling_pace(words), 2 / 12)

    def test_independent_review_cannot_be_self_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            authority_path = root / "authority.json"
            authority = {
                "schema": "lecture-animation-independent-review-authority-v2",
                "author_id": "author-1",
                "reviewer_id": "author-1",
                "review_source": "independent_review",
                "review_kind": "test",
                "authorized_verdict": "pass",
                "status": "granted",
            }
            authority["authority_hash"] = engine.object_hash(authority)
            authority_path.write_text(json.dumps(authority), encoding="utf-8")
            review_path = root / "review.json"
            review = {
                "schema": "test-review-v2",
                "author_id": "author-1",
                "reviewer_id": "author-1",
                "review_source": "independent_review",
                "verdict": "pass",
                "checks": {"semantic": True},
                "authority_path": "authority.json",
                "authority_sha256": hashlib.sha256(
                    authority_path.read_bytes()
                ).hexdigest(),
            }
            review["review_hash"] = engine.object_hash(review)
            review_path.write_text(json.dumps(review), encoding="utf-8")
            errors: list[str] = []
            _validate_independent_review(
                path=review_path,
                repo_root=root,
                expected_schema="test-review-v2",
                expected_bindings={},
                required_checks=("semantic",),
                label="self-review",
                errors=errors,
                author_id="author-1",
                expected_review_kind="test",
            )
            self.assertIn("must differ", " | ".join(errors))

    def test_review_authority_must_bind_kind_source_and_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            authority_path = root / "authority.json"
            authority = {
                "schema": "lecture-animation-independent-review-authority-v2",
                "author_id": "author-1",
                "reviewer_id": "reviewer-1",
                "review_source": "independent_review",
                "review_kind": "layout_diagnostic",
                "authorized_verdict": "revise",
                "status": "granted",
            }
            authority["authority_hash"] = engine.object_hash(authority)
            authority_path.write_text(json.dumps(authority), encoding="utf-8")
            review_path = root / "review.json"
            review = {
                "schema": "test-review-v2",
                "author_id": "author-1",
                "reviewer_id": "reviewer-1",
                "review_source": "independent_review",
                "verdict": "pass",
                "checks": {"semantic": True},
                "authority_path": "authority.json",
                "authority_sha256": hashlib.sha256(
                    authority_path.read_bytes()
                ).hexdigest(),
            }
            review["review_hash"] = engine.object_hash(review)
            review_path.write_text(json.dumps(review), encoding="utf-8")
            errors: list[str] = []
            _validate_independent_review(
                path=review_path,
                repo_root=root,
                expected_schema="test-review-v2",
                expected_bindings={},
                required_checks=("semantic",),
                label="wrong-scope",
                errors=errors,
                author_id="author-1",
                expected_review_kind="pronunciation",
            )
            joined = " | ".join(errors)
            self.assertIn("kind binding", joined)
            self.assertIn("verdict binding", joined)

    def test_zero_phase_events_are_zero_observability(self) -> None:
        observability = phase_metrics([])["token_observability"]
        self.assertFalse(observability["applicable"])
        self.assertEqual(observability["expected_events"], 0)
        self.assertEqual(observability["coverage"], 0.0)

    def test_episode_preflight_passes_complete_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            episode.mkdir(parents=True)
            first = episode / "g001.txt"
            second = episode / "g002.txt"
            first_source = episode / "g001.py"
            second_source = episode / "g002.py"
            first_source.write_text("from manim import *\n", encoding="utf-8")
            second_source.write_text("from manim import *\n", encoding="utf-8")
            first.write_text(
                "先看两个可以直接指认的具体方向，再观察它们怎样分别变化。"
                "现在请指出两个方向如何分别变化，再把独立的变化方向叫作模式。",
                encoding="utf-8",
            )
            second.write_text(
                "先看一排还留着间隔的小点，观察相邻小点之间的间隔逐渐缩小。"
                "把这些点叫作离散格点，再指出相邻格点的间隔正在缩小，最后过渡到积分。"
                "eta 只是积分中的变量。"
                "离散格点不断变密时，积分会怎样出现？",
                encoding="utf-8",
            )
            first_semantics = episode / "g001_screen_text_semantics.json"
            second_semantics = episode / "g002_screen_text_semantics.json"
            write_screen_text_semantic_contract(first_semantics)
            write_screen_text_semantic_contract(second_semantics)
            first_tts_input = episode / "g001_tts_input.txt"
            registry_path, first_mapping_path = write_tts_mapping_v2(
                root=root,
                scene_slug="g001",
                formal_script=first,
                tts_input=first_tts_input,
            )
            tts_input = episode / "tts_input.txt"
            registry_path, mapping_path = write_tts_mapping_v2(
                root=root,
                scene_slug="g002",
                formal_script=second,
                tts_input=tts_input,
                spoken_forms={"eta": "伊塔"},
            )
            ear_evidence = episode / "eta.wav"
            with wave.open(str(ear_evidence), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(100)
                handle.writeframes(b"\0\0" * 5000)
            bridge = {
                "explanation": "先看两个可以直接指认的具体方向，再观察它们怎样分别变化",
                "concrete_referent": "两个可以直接指认的具体方向",
                "learner_action": "指出两个方向如何分别变化",
                "narration_quote": "先看两个可以直接指认的具体方向",
                "term_introduction_after_referent": True,
            }
            second_bridge = {
                "explanation": "先看一排还留着间隔的小点，观察相邻小点之间的间隔逐渐缩小",
                "concrete_referent": "一排还留着间隔的小点",
                "learner_action": "指出相邻格点的间隔正在缩小",
                "narration_quote": "先看一排还留着间隔的小点",
                "term_introduction_after_referent": True,
            }

            def bridge_hash(value: dict, terms: list[str]) -> str:
                return engine.object_hash(
                    {
                        "terms": terms,
                        "explanation": value["explanation"],
                        "concrete_referent": value["concrete_referent"],
                        "learner_action": value["learner_action"],
                        "narration_quote": value["narration_quote"],
                        "term_introduction_after_referent": True,
                    }
                )

            review_checks = {
                "explanation_relevant": True,
                "referent_supports_term": True,
                "learner_action_teaches_term": True,
                "term_follows_referent": True,
            }
            author_id = "author:test"

            def write_review(
                path: Path,
                payload: dict,
                reviewer: str,
                review_source: str,
            ) -> None:
                review_kind = (
                    "pronunciation"
                    if payload["schema"] == "lecture-animation-pronunciation-review-v2"
                    else "novice_bridge"
                )
                authority_path = episode / (
                    reviewer.replace(":", "_") + f"_{review_kind}_authority.json"
                )
                if not authority_path.exists():
                    authority = {
                        "schema": (
                            "lecture-animation-human-review-authority-v2"
                            if review_source == "human_review"
                            else "lecture-animation-independent-review-authority-v2"
                        ),
                        "author_id": author_id,
                        "reviewer_id": reviewer,
                        "review_source": review_source,
                        "review_kind": review_kind,
                        "authorized_verdict": "pass",
                        "status": "approved",
                    }
                    authority["authority_hash"] = engine.object_hash(authority)
                    authority_path.write_text(
                        json.dumps(authority, ensure_ascii=False),
                        encoding="utf-8",
                    )
                payload.update(
                    {
                        "author_id": author_id,
                        "reviewer_id": reviewer,
                        "review_source": review_source,
                        "verdict": "pass",
                        "authority_path": str(authority_path.relative_to(root)),
                        "authority_sha256": hashlib.sha256(
                            authority_path.read_bytes()
                        ).hexdigest(),
                    }
                )
                payload["review_hash"] = engine.object_hash(payload)
                path.write_text(
                    json.dumps(payload, ensure_ascii=False),
                    encoding="utf-8",
                )

            first_review = episode / "g001_novice_review.json"
            second_review = episode / "g002_novice_review.json"
            for path, slug, narration, value, terms, reviewer in (
                (first_review, "g001", first, bridge, ["模式"], "human:test"),
                (
                    second_review,
                    "g002",
                    second,
                    second_bridge,
                    ["离散格点"],
                    "reviewer:test",
                ),
            ):
                write_review(
                    path,
                    {
                        "schema": "lecture-animation-novice-bridge-review-v2",
                        "scene_slug": slug,
                        "narration_sha256": hashlib.sha256(
                            narration.read_bytes()
                        ).hexdigest(),
                        "bridge_hash": bridge_hash(value, terms),
                        "new_terms": terms,
                        "checks": review_checks,
                    },
                    reviewer,
                    (
                        "human_review"
                        if reviewer.startswith("human:")
                        else "independent_review"
                    ),
                )
            occurrence_results = [
                {
                    "occurrence": 1,
                    "window_seconds": [1.0, 2.0],
                    "result": "pass",
                }
            ]
            ear_review = episode / "eta_ear_review.json"
            write_review(
                ear_review,
                {
                    "schema": "lecture-animation-pronunciation-review-v2",
                    "scene_slug": "g002",
                    "token": "eta",
                    "spoken_form": "伊塔",
                    "source_audio_sha256": hashlib.sha256(
                        ear_evidence.read_bytes()
                    ).hexdigest(),
                    "occurrence_windows_seconds": [[1.0, 2.0]],
                    "occurrence_results": occurrence_results,
                    "checks": {
                        "all_occurrences_heard": True,
                        "spoken_form_consistent": True,
                        "no_formal_token_read_aloud": True,
                    },
                },
                "human:test",
                "human_review",
            )
            contract = {
                "schema": "lecture-animation-episode-readiness-v2",
                "author_id": author_id,
                "tts_route_id": TEST_TTS_ROUTE_ID,
                "pronunciation_registry_path": str(registry_path.relative_to(root)),
                "fixed_ending": "离散格点不断变密时，积分会怎样出现？",
                "fixed_ending_contract": mathematical_fixed_ending_contract(),
                "sensitive_tokens": ["eta"],
                "pronunciation_map": {
                    "eta": {
                        "spoken_form": "伊塔",
                        "scene_slug": "g002",
                        "tts_input_path": str(tts_input.relative_to(root)),
                        "source_audio_path": str(ear_evidence.relative_to(root)),
                        "ear_evidence_path": str(ear_evidence.relative_to(root)),
                        "ear_review_path": str(ear_review.relative_to(root)),
                        "occurrences": 1,
                        "occurrence_windows_seconds": [[1.0, 2.0]],
                        "ear_check_results": occurrence_results,
                        "route_id": TEST_TTS_ROUTE_ID,
                    }
                },
                "required_concept_bridges": ["mode", "discrete_to_continuous"],
                "concept_bridges": [
                    {
                        "bridge_id": "mode",
                        "scene_slug": "g001",
                        "term": "模式",
                        **bridge,
                        "novice_bridge_review_path": str(
                            first_review.relative_to(root)
                        ),
                    },
                    {
                        "bridge_id": "discrete_to_continuous",
                        "scene_slug": "g002",
                        "term": "离散格点",
                        **second_bridge,
                        "novice_bridge_review_path": str(
                            second_review.relative_to(root)
                        ),
                    },
                ],
                "scenes": [
                    {
                        "scene_slug": "g001",
                        "scene_source_path": str(first_source.relative_to(root)),
                        "scene_source_root": str(episode.relative_to(root)),
                        "narration_path": str(first.relative_to(root)),
                        "tts_input_path": str(first_tts_input.relative_to(root)),
                        "tts_input_mapping_path": str(
                            first_mapping_path.relative_to(root)
                        ),
                        "duration_seconds": 40,
                        "concept_load": "concept_heavy",
                        "prerequisites": ["vector direction"],
                        "new_terms": ["模式"],
                        "novice_bridge": bridge,
                        "novice_bridge_review_path": str(
                            first_review.relative_to(root)
                        ),
                        "screen_text_semantic_contract_path": str(
                            first_semantics.relative_to(root)
                        ),
                    },
                    {
                        "scene_slug": "g002",
                        "scene_source_path": str(second_source.relative_to(root)),
                        "scene_source_root": str(episode.relative_to(root)),
                        "narration_path": str(second.relative_to(root)),
                        "tts_input_path": str(tts_input.relative_to(root)),
                        "tts_input_mapping_path": str(mapping_path.relative_to(root)),
                        "audio_path": str(ear_evidence.relative_to(root)),
                        "duration_seconds": 50,
                        "screen_text_semantic_contract_path": str(
                            second_semantics.relative_to(root)
                        ),
                    },
                ],
            }
            result = run_episode_preflight(root, episode, contract)
            self.assertEqual(result["status"], "pass", result["errors"])
            self.assertEqual(result["fixed_ending_count"], 1)

    def test_progressive_wave_binds_nonadjacent_scenes_at_pre_and_post_tts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0009-test"
            episode.mkdir(parents=True)
            fixed_ending = "一只小圈已经能读取局部系数，大围道会怎样汇总所有奇点？"
            ending_source = episode / "narration-outline.md"
            ending_source.write_text(f"# 粗口播\n\n{fixed_ending}\n", encoding="utf-8")

            tracker = {
                "schema": "lecture-animation-progressive-production-v2",
                "episode": "videos/0009-test",
                "scenes": [
                    {"scene_slug": "g001"},
                    {"scene_slug": "g002"},
                    {"scene_slug": "g003"},
                    {"scene_slug": "g004"},
                ],
            }
            tracker["production_hash"] = engine.object_hash(tracker)
            tracker_path = episode / "progressive_production.json"
            tracker_path.write_text(
                json.dumps(tracker, ensure_ascii=False), encoding="utf-8"
            )

            scene_rows = []
            for slug, author, narration_text in (
                ("g001", "author:a", "先比较两根贡献箭头，再判断它们能否抵消。"),
                ("g003", "author:c", "现在保持小圆不变，只观察局部系数的方向。"),
            ):
                scene_root = episode / "src" / slug
                source = scene_root / "composer.py"
                narration = episode / "review" / "v2" / slug / "narration.txt"
                tts_input = episode / "review" / "v2" / slug / "tts_input.txt"
                semantics = (
                    episode / "review" / "v2" / slug / "screen_text_semantics.json"
                )
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text('"""Pre-TTS inventory scaffold."""\n', encoding="utf-8")
                narration.parent.mkdir(parents=True, exist_ok=True)
                narration.write_text(narration_text, encoding="utf-8")
                registry_path, mapping_path = write_tts_mapping_v2(
                    root=root,
                    scene_slug=slug,
                    formal_script=narration,
                    tts_input=tts_input,
                )
                write_screen_text_semantic_contract(semantics)
                scene_rows.append(
                    {
                        "scene_slug": slug,
                        "author_id": author,
                        "scene_source_path": str(source.relative_to(root)),
                        "scene_source_root": str(scene_root.relative_to(root)),
                        "narration_path": str(narration.relative_to(root)),
                        "tts_input_path": str(tts_input.relative_to(root)),
                        "tts_input_mapping_path": str(mapping_path.relative_to(root)),
                        "screen_text_semantic_contract_path": str(
                            semantics.relative_to(root)
                        ),
                        "duration_seconds": 18,
                    }
                )

            contract = {
                "schema": "lecture-animation-episode-readiness-v2",
                "readiness_stage": "pre_tts",
                "readiness_scope": "progressive_wave",
                "author_id": "main:producer",
                "tts_route_id": TEST_TTS_ROUTE_ID,
                "pronunciation_registry_path": str(registry_path.relative_to(root)),
                "progressive_production_path": str(tracker_path.relative_to(root)),
                "wave_scene_slugs": ["g001", "g003"],
                "fixed_ending": fixed_ending,
                "fixed_ending_source_path": str(ending_source.relative_to(root)),
                "fixed_ending_contract": mathematical_fixed_ending_contract(),
                "scenes": scene_rows,
            }
            result = run_episode_preflight(root, episode, contract)
            self.assertEqual(result["status"], "pass", result["errors"])
            self.assertEqual(result["readiness_scope"], "progressive_wave")
            self.assertEqual(result["planned_scene_count"], 4)
            self.assertEqual(result["wave_scene_count"], 2)
            self.assertEqual(
                [row["author_id"] for row in result["scenes"]],
                ["author:a", "author:c"],
            )
            self.assertEqual(result["fixed_ending_count"], 1)
            self.assertIsNotNone(result["fixed_ending_source"])

            contract["readiness_stage"] = "post_tts"
            post_tts_result = run_episode_preflight(root, episode, contract)
            self.assertEqual(
                post_tts_result["status"], "pass", post_tts_result["errors"]
            )
            self.assertEqual(post_tts_result["readiness_stage"], "post_tts")
            self.assertEqual(post_tts_result["readiness_scope"], "progressive_wave")
            self.assertEqual(
                [row["scene_slug"] for row in post_tts_result["scenes"]],
                ["g001", "g003"],
            )

    def test_episode_preflight_blocks_predictable_rework(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            episode.mkdir(parents=True)
            repeated = "这一整句话不应该在两个相邻场景里重复出现。"
            contract = {
                "schema": "lecture-animation-episode-readiness-v2",
                "sensitive_tokens": ["eta"],
                "scenes": [
                    {
                        "scene_slug": "g001",
                        "narration": f"先开始。{repeated}",
                        "duration_seconds": 95,
                        "concept_load": "concept_heavy",
                    },
                    {
                        "scene_slug": "g002",
                        "narration": f"{repeated}然后说 eta。",
                        "duration_seconds": 30,
                    },
                ],
            }
            result = run_episode_preflight(root, episode, contract)
            self.assertEqual(result["status"], "blocked")
            joined = " | ".join(result["errors"])
            self.assertIn("duplicate narration", joined)
            self.assertIn("90s", joined)
            self.assertIn("prerequisites", joined)
            self.assertIn("pronunciation map", joined)
            self.assertIn("fixed ending", joined)

    def test_preflight_receipt_binds_narration_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            episode.mkdir(parents=True)
            narration = episode / "g001.txt"
            narration.write_text(
                "先看一个具体变化。这个变化最终保留了哪个方向？",
                encoding="utf-8",
            )
            source = episode / "src" / "g001.py"
            source.parent.mkdir()
            source.write_text("from manim import *\n", encoding="utf-8")
            semantics = episode / "g001_screen_text_semantics.json"
            write_screen_text_semantic_contract(semantics)
            tts_input = episode / "g001_tts_input.txt"
            registry_path, mapping_path = write_tts_mapping_v2(
                root=root,
                scene_slug="g001",
                formal_script=narration,
                tts_input=tts_input,
            )
            contract_path = episode / "readiness.json"
            contract_path.write_text(
                json.dumps(
                    {
                        "schema": "lecture-animation-episode-readiness-v2",
                        "author_id": "author:test",
                        "tts_route_id": TEST_TTS_ROUTE_ID,
                        "pronunciation_registry_path": str(
                            registry_path.relative_to(root)
                        ),
                        "fixed_ending": "这个变化最终保留了哪个方向？",
                        "fixed_ending_contract": mathematical_fixed_ending_contract(),
                        "scenes": [
                            {
                                "scene_slug": "g001",
                                "scene_source_path": str(source.relative_to(root)),
                                "scene_source_root": str(source.parent.relative_to(root)),
                                "narration_path": str(narration.relative_to(root)),
                                "tts_input_path": str(tts_input.relative_to(root)),
                                "tts_input_mapping_path": str(
                                    mapping_path.relative_to(root)
                                ),
                                "duration_seconds": 20,
                                "screen_text_semantic_contract_path": str(
                                    semantics.relative_to(root)
                                ),
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            receipt = episode / "receipt.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    command_episode_preflight(
                        SimpleNamespace(
                            repo_root=str(root),
                            episode=str(episode),
                            contract=str(contract_path),
                            output=str(receipt),
                            require_clean=True,
                        )
                    ),
                    0,
                )
            validate_episode_readiness_receipt(receipt, root, episode, "g001")
            with self.assertRaisesRegex(PipelineError, "scene set"):
                validate_episode_readiness_receipt(
                    receipt,
                    root,
                    episode,
                    expected_scene_slugs={"g001", "g002"},
                )
            narration.write_text(
                "内容已经变化。这个变化最终保留了哪个方向？",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PipelineError, "stale"):
                validate_episode_readiness_receipt(receipt, root, episode, "g001")

    def test_preflight_blocks_fast_scene_without_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            episode.mkdir(parents=True)
            narration = episode / "fast.txt"
            narration.write_text(
                "这是非常密集而且完全没有停顿的新手口播内容" * 20
                + "我是结束乐队的键盘手，下个视频见。",
                encoding="utf-8",
            )
            source = episode / "src" / "g001.py"
            source.parent.mkdir()
            source.write_text("from manim import *\n", encoding="utf-8")
            result = run_episode_preflight(
                root,
                episode,
                {
                    "schema": "lecture-animation-episode-readiness-v2",
                    "scenes": [
                        {
                            "scene_slug": "g001",
                            "scene_source_path": str(source.relative_to(root)),
                            "scene_source_root": str(episode.relative_to(root)),
                            "narration_path": str(narration.relative_to(root)),
                            "duration_seconds": 10,
                        }
                    ],
                },
            )
            self.assertEqual(result["status"], "blocked")
            self.assertIn("average pace", " | ".join(result["errors"]))

    def test_portability_audit_rejects_temporary_worktree_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            source = episode / "src"
            source.mkdir(parents=True)
            artifact = episode / "final.mp4"
            artifact.write_bytes(b"final")
            (source / "render.py").write_text(
                'SOURCE = "/Volumes/bocchi/myLectures-worktrees/agent-a/video.py"\n',
                encoding="utf-8",
            )
            result = run_portability_audit(
                root,
                episode,
                {"final": str(artifact.relative_to(root))},
                [str(source.relative_to(root))],
            )
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(len(result["dangling_worktree_references"]), 1)
            json.dumps(result)

    def test_portability_audit_cannot_pass_empty_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            episode.mkdir(parents=True)
            result = run_portability_audit(root, episode, {}, [])
            self.assertEqual(result["status"], "blocked")
            self.assertGreaterEqual(len(result["errors"]), 3)

    def test_portability_audit_rejects_lecture_only_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            episode.mkdir(parents=True)
            lecture = episode / "lecture.md"
            lecture.write_text("# lecture", encoding="utf-8")
            result = run_portability_audit(
                root,
                episode,
                {"lecture": str(lecture.relative_to(root))},
                [str(episode.relative_to(root))],
            )
            self.assertEqual(result["status"], "blocked")
            self.assertIn("required artifact roles", " | ".join(result["errors"]))

    def test_portability_audit_rejects_garbage_with_complete_role_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            source = episode / "src"
            audio = episode / "audio"
            source.mkdir(parents=True)
            audio.mkdir()
            paths = {
                "lecture": episode / "lecture.md",
                "source": source,
                "audio": audio,
                "final_video": episode / "final.mp4",
                "final_srt": episode / "final.srt",
                "final_manifest": episode / "manifest.json",
            }
            paths["lecture"].write_text("x", encoding="utf-8")
            (source / "scene.py").write_text("x=1", encoding="utf-8")
            (audio / "scene.wav").write_bytes(b"not audio")
            paths["final_video"].write_bytes(b"not video")
            paths["final_srt"].write_text("not srt", encoding="utf-8")
            paths["final_manifest"].write_text("not json", encoding="utf-8")
            result = run_portability_audit(
                root,
                episode,
                {
                    key: str(path.relative_to(root))
                    for key, path in paths.items()
                },
                [str(source.relative_to(root))],
            )
            joined = " | ".join(result["errors"])
            self.assertEqual(result["status"], "blocked")
            for label in ("lecture:", "audio:", "final_video:", "final_srt:", "final_manifest:"):
                self.assertIn(label, joined)

    def test_screen_text_inventory_must_match_scene_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            episode.mkdir(parents=True)
            narration = episode / "g001.txt"
            narration.write_text(
                "先检查画面文字。我是结束乐队的键盘手，下个视频见。",
                encoding="utf-8",
            )
            source = episode / "g001.py"
            source.write_text(
                'a=Text("甲")\nb=Text("乙")\nc=Text("丙")\n',
                encoding="utf-8",
            )
            result = run_episode_preflight(
                root,
                episode,
                {
                    "schema": "lecture-animation-episode-readiness-v2",
                    "scenes": [
                        {
                            "scene_slug": "g001",
                            "scene_source_path": str(source.relative_to(root)),
                            "narration_path": str(narration.relative_to(root)),
                            "duration_seconds": 20,
                            "screen_text_inventory": [
                                {
                                    "text": "甲",
                                    "source_path": str(source.relative_to(root)),
                                }
                            ],
                            "screen_text_count": 1,
                        }
                    ],
                },
            )
            self.assertEqual(result["status"], "blocked")
            self.assertIn(
                "must exactly match",
                " | ".join(result["errors"]),
            )

    def test_screen_text_inventory_scans_imported_helper_within_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            package = episode / "src" / "g001"
            package.mkdir(parents=True)
            source = package / "composer.py"
            helper = package / "helper.py"
            source.write_text("from .helper import build\n", encoding="utf-8")
            helper.write_text(
                'def build():\n return Text("helper-visible")\n',
                encoding="utf-8",
            )
            narration = episode / "g001.txt"
            narration.write_text(
                "先检查辅助模块文字。我是结束乐队的键盘手，下个视频见。",
                encoding="utf-8",
            )
            result = run_episode_preflight(
                root,
                episode,
                {
                    "schema": "lecture-animation-episode-readiness-v2",
                    "author_id": "author:test",
                    "scenes": [
                        {
                            "scene_slug": "g001",
                            "scene_source_path": str(source.relative_to(root)),
                            "scene_source_root": str(package.relative_to(root)),
                            "narration_path": str(narration.relative_to(root)),
                            "duration_seconds": 20,
                            "screen_text_inventory": [],
                        }
                    ],
                },
            )
            self.assertIn("must exactly match", " | ".join(result["errors"]))

    def test_screen_text_inventory_source_must_stay_inside_scene_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            package = episode / "src" / "g001"
            package.mkdir(parents=True)
            source = package / "composer.py"
            helper = package / "helper.py"
            external = episode / "external_inventory.py"
            source.write_text("from .helper import build\n", encoding="utf-8")
            helper.write_text('def build():\n return Text("helper-visible")\n', encoding="utf-8")
            external.write_text('Text("helper-visible")\n', encoding="utf-8")
            narration = episode / "g001.txt"
            narration.write_text(
                "先检查辅助模块文字。我是结束乐队的键盘手，下个视频见。",
                encoding="utf-8",
            )
            result = run_episode_preflight(
                root,
                episode,
                {
                    "schema": "lecture-animation-episode-readiness-v2",
                    "author_id": "author:test",
                    "scenes": [
                        {
                            "scene_slug": "g001",
                            "scene_source_path": str(source.relative_to(root)),
                            "scene_source_root": str(package.relative_to(root)),
                            "narration_path": str(narration.relative_to(root)),
                            "duration_seconds": 20,
                            "screen_text_inventory": [
                                {
                                    "text": "helper-visible",
                                    "source_path": str(external.relative_to(root)),
                                }
                            ],
                            "screen_text_count": 1,
                        }
                    ],
                },
            )
            joined = " | ".join(result["errors"])
            self.assertIn("must live inside scene_source_root", joined)
            self.assertIn("constructors by file", joined)

    def test_screen_text_inventory_allows_real_duplicate_literals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            package = episode / "src" / "g001"
            package.mkdir(parents=True)
            source = package / "composer.py"
            source.write_text(
                'first = Text("same")\nsecond = Text("same")\n',
                encoding="utf-8",
            )
            narration = episode / "g001.txt"
            narration.write_text(
                "先检查重复文字。这两个相同标签分别锚定哪个对象？",
                encoding="utf-8",
            )
            source_relative = str(source.relative_to(root))
            semantics = episode / "g001_screen_text_semantics.json"
            write_screen_text_semantic_contract(
                semantics,
                [
                    {
                        "constructor": "Text",
                        "payload": "same",
                        "count": 2,
                        "unique_visual_job": "给两个独立对象提供相同类别标签",
                        "necessity": "学习者需要看见两个对象属于同一个类别",
                        "removal_failure": "移除后无法判断两个对象是否共享同一类别",
                        "clearance_condition": "两个对象完成类别比较后清场",
                        "math_object_anchor": "两个待比较对象",
                        "duplicates_narration": False,
                        "externalizes_production_intent": False,
                    }
                ],
            )
            tts_input = episode / "g001_tts_input.txt"
            registry_path, mapping_path = write_tts_mapping_v2(
                root=root,
                scene_slug="g001",
                formal_script=narration,
                tts_input=tts_input,
            )
            result = run_episode_preflight(
                root,
                episode,
                {
                    "schema": "lecture-animation-episode-readiness-v2",
                    "author_id": "author:test",
                    "tts_route_id": TEST_TTS_ROUTE_ID,
                    "pronunciation_registry_path": str(
                        registry_path.relative_to(root)
                    ),
                    "fixed_ending": "这两个相同标签分别锚定哪个对象？",
                    "fixed_ending_contract": mathematical_fixed_ending_contract(),
                    "scenes": [
                        {
                            "scene_slug": "g001",
                            "scene_source_path": source_relative,
                            "scene_source_root": str(package.relative_to(root)),
                            "narration_path": str(narration.relative_to(root)),
                            "tts_input_path": str(tts_input.relative_to(root)),
                            "tts_input_mapping_path": str(
                                mapping_path.relative_to(root)
                            ),
                            "duration_seconds": 20,
                            "screen_text_inventory": [
                                {"text": "same", "source_path": source_relative},
                                {"text": "same", "source_path": source_relative},
                            ],
                            "screen_text_count": 2,
                            "screen_text_semantic_contract_path": str(
                                semantics.relative_to(root)
                            ),
                        }
                    ],
                },
            )
            self.assertEqual(result["status"], "pass", result["errors"])

    def test_unicode_eta_triggers_pronunciation_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            package = episode / "src" / "g001"
            package.mkdir(parents=True)
            source = package / "composer.py"
            source.write_text("from manim import *\n", encoding="utf-8")
            narration = episode / "g001.txt"
            narration.write_text(
                "令 η 等于 x 减 y。我是结束乐队的键盘手，下个视频见。",
                encoding="utf-8",
            )
            result = run_episode_preflight(
                root,
                episode,
                {
                    "schema": "lecture-animation-episode-readiness-v2",
                    "author_id": "author:test",
                    "scenes": [
                        {
                            "scene_slug": "g001",
                            "scene_source_path": str(source.relative_to(root)),
                            "scene_source_root": str(package.relative_to(root)),
                            "narration_path": str(narration.relative_to(root)),
                            "duration_seconds": 20,
                        }
                    ],
                },
            )
            self.assertIn("pronunciation map is missing sensitive tokens: eta", result["errors"])

    def test_mode_term_triggers_bridge_even_when_concept_load_is_normal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            package = episode / "src" / "g001"
            package.mkdir(parents=True)
            source = package / "composer.py"
            source.write_text("from manim import *\n", encoding="utf-8")
            narration = episode / "g001.txt"
            narration.write_text(
                "现在直接把它叫作模式。我是结束乐队的键盘手，下个视频见。",
                encoding="utf-8",
            )
            result = run_episode_preflight(
                root,
                episode,
                {
                    "schema": "lecture-animation-episode-readiness-v2",
                    "author_id": "author:test",
                    "scenes": [
                        {
                            "scene_slug": "g001",
                            "scene_source_path": str(source.relative_to(root)),
                            "scene_source_root": str(package.relative_to(root)),
                            "narration_path": str(narration.relative_to(root)),
                            "duration_seconds": 20,
                            "concept_load": "normal",
                        }
                    ],
                },
            )
            self.assertIn(
                "required novice concept bridges are missing: mode",
                result["errors"],
            )

    def test_preflight_rejects_fake_pronunciation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            episode.mkdir(parents=True)
            narration = episode / "g001.txt"
            narration.write_text(
                "eta 是变量。我是结束乐队的键盘手，下个视频见。",
                encoding="utf-8",
            )
            tts_input = episode / "tts.txt"
            tts_input.write_text("伊塔是变量。", encoding="utf-8")
            fake = episode / "fake.wav"
            fake.write_bytes(b"not-a-real-wave-file")
            source = episode / "src" / "g001.py"
            source.parent.mkdir()
            source.write_text("from manim import *\n", encoding="utf-8")
            occurrence_results = [
                {
                    "occurrence": 999,
                    "window_seconds": [0.0, 1.0],
                    "result": "pass",
                }
            ]
            ear_review = episode / "ear_review.json"
            ear_review.write_text(
                json.dumps(
                    {
                        "schema": "lecture-animation-pronunciation-review-v2",
                        "scene_slug": "g001",
                        "token": "eta",
                        "spoken_form": "伊塔",
                        "source_audio_sha256": hashlib.sha256(
                            fake.read_bytes()
                        ).hexdigest(),
                        "occurrence_windows_seconds": [],
                        "occurrence_results": occurrence_results,
                        "reviewer_id": "human:test",
                        "review_source": "human_review",
                        "verdict": "pass",
                        "checks": {
                            "all_occurrences_heard": True,
                            "spoken_form_consistent": True,
                            "no_formal_token_read_aloud": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = run_episode_preflight(
                root,
                episode,
                {
                    "schema": "lecture-animation-episode-readiness-v2",
                    "sensitive_tokens": ["eta"],
                    "pronunciation_map": {
                        "eta": {
                            "spoken_form": "伊塔",
                            "scene_slug": "g001",
                            "tts_input_path": str(tts_input.relative_to(root)),
                            "source_audio_path": str(fake.relative_to(root)),
                            "ear_evidence_path": str(fake.relative_to(root)),
                            "ear_review_path": str(ear_review.relative_to(root)),
                            "occurrences": 1,
                            "occurrence_windows_seconds": [[0.0, 1.0]],
                            "ear_check_results": occurrence_results,
                        }
                    },
                    "scenes": [
                        {
                            "scene_slug": "g001",
                            "scene_source_path": str(source.relative_to(root)),
                            "narration_path": str(narration.relative_to(root)),
                            "audio_path": str(fake.relative_to(root)),
                            "duration_seconds": 20,
                        }
                    ],
                },
            )
            joined = " | ".join(result["errors"])
            self.assertEqual(result["status"], "blocked")
            self.assertIn("not a decodable WAV", joined)
            self.assertIn("ordered 1..N", joined)

    def test_pre_tts_stage_validates_spelling_without_circular_audio_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            episode.mkdir(parents=True)
            narration = episode / "g001.txt"
            narration.write_text(
                "eta 是积分变量。这个变量在积分中怎样移动？",
                encoding="utf-8",
            )
            source = episode / "src" / "g001.py"
            source.parent.mkdir()
            source.write_text("from manim import *\n", encoding="utf-8")
            tts_input = episode / "tts.txt"
            registry_path, mapping_path = write_tts_mapping_v2(
                root=root,
                scene_slug="g001",
                formal_script=narration,
                tts_input=tts_input,
                spoken_forms={"eta": "伊塔"},
            )
            contract_path = episode / "readiness.json"
            contract_path.write_text(
                json.dumps(
                    {
                        "schema": "lecture-animation-episode-readiness-v2",
                        "author_id": "author:test",
                        "readiness_stage": "pre_tts",
                        "tts_route_id": TEST_TTS_ROUTE_ID,
                        "pronunciation_registry_path": str(registry_path.relative_to(root)),
                        "fixed_ending": "这个变量在积分中怎样移动？",
                        "fixed_ending_contract": mathematical_fixed_ending_contract(),
                        "sensitive_tokens": ["eta"],
                        "pronunciation_map": {
                            "eta": {
                                "spoken_form": "伊塔",
                                "scene_slug": "g001",
                                "tts_input_path": str(tts_input.relative_to(root)),
                                "occurrences": 1,
                                "route_id": TEST_TTS_ROUTE_ID,
                            }
                        },
                        "scenes": [
                            {
                                "scene_slug": "g001",
                                "scene_source_path": str(source.relative_to(root)),
                                "scene_source_root": str(source.parent.relative_to(root)),
                                "narration_path": str(narration.relative_to(root)),
                                "tts_input_path": str(tts_input.relative_to(root)),
                                "tts_input_mapping_path": str(mapping_path.relative_to(root)),
                                "duration_seconds": 20,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            receipt = episode / "receipt.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    command_episode_preflight(
                        SimpleNamespace(
                            repo_root=str(root),
                            episode=str(episode),
                            contract=str(contract_path),
                            output=str(receipt),
                            require_clean=True,
                        )
                    ),
                    0,
                )
            validate_episode_readiness_receipt(
                receipt, root, episode, "g001", required_stage="pre_tts"
            )
            with self.assertRaisesRegex(PipelineError, "cannot satisfy post_tts"):
                validate_episode_readiness_receipt(
                    receipt, root, episode, "g001", required_stage="post_tts"
                )

    def test_pre_tts_blocks_forbidden_pronunciation_form(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0009-test"
            source = episode / "src" / "g001.py"
            narration = episode / "g001.txt"
            tts_input = episode / "tts.txt"
            source.parent.mkdir(parents=True)
            source.write_text("from manim import *\n", encoding="utf-8")
            narration.write_text("theta 是方向参数。这个方向怎样变化？", encoding="utf-8")
            registry_path, mapping_path = write_tts_mapping_v2(
                root=root,
                scene_slug="g001",
                formal_script=narration,
                tts_input=tts_input,
                spoken_forms={"theta": "西塔"},
            )
            result = run_episode_preflight(
                root,
                episode,
                {
                    "schema": "lecture-animation-episode-readiness-v2",
                    "author_id": "author:test",
                    "readiness_stage": "pre_tts",
                    "tts_route_id": TEST_TTS_ROUTE_ID,
                    "pronunciation_registry_path": str(registry_path.relative_to(root)),
                    "fixed_ending": "这个方向怎样变化？",
                    "fixed_ending_contract": mathematical_fixed_ending_contract(),
                    "sensitive_tokens": ["theta"],
                    "pronunciation_map": {
                        "theta": {
                            "spoken_form": "西塔",
                            "scene_slug": "g001",
                            "tts_input_path": str(tts_input.relative_to(root)),
                            "occurrences": 1,
                            "route_id": TEST_TTS_ROUTE_ID,
                        }
                    },
                    "scenes": [
                        {
                            "scene_slug": "g001",
                            "scene_source_path": str(source.relative_to(root)),
                            "scene_source_root": str(source.parent.relative_to(root)),
                            "narration_path": str(narration.relative_to(root)),
                            "tts_input_path": str(tts_input.relative_to(root)),
                            "tts_input_mapping_path": str(mapping_path.relative_to(root)),
                            "duration_seconds": 20,
                        }
                    ],
                },
            )
            self.assertEqual(result["status"], "blocked")
            self.assertIn("forbidden spoken form '西塔'", " | ".join(result["errors"]))

    def test_pre_tts_blocks_unregistered_or_misplaced_text_edit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0009-test"
            source = episode / "src" / "g001.py"
            narration = episode / "g001.txt"
            tts_input = episode / "tts.txt"
            source.parent.mkdir(parents=True)
            source.write_text("from manim import *\n", encoding="utf-8")
            narration.write_text("先观察一个方向。这个方向怎样变化？", encoding="utf-8")
            registry_path, mapping_path = write_tts_mapping_v2(
                root=root,
                scene_slug="g001",
                formal_script=narration,
                tts_input=tts_input,
            )
            tts_input.write_text(
                tts_input.read_text(encoding="utf-8").replace("观察", "猜测"),
                encoding="utf-8",
            )
            mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
            mapping["tts_input_sha256"] = hashlib.sha256(tts_input.read_bytes()).hexdigest()
            mapping_path.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
            result = run_episode_preflight(
                root,
                episode,
                {
                    "schema": "lecture-animation-episode-readiness-v2",
                    "author_id": "author:test",
                    "readiness_stage": "pre_tts",
                    "tts_route_id": TEST_TTS_ROUTE_ID,
                    "pronunciation_registry_path": str(registry_path.relative_to(root)),
                    "fixed_ending": "这个方向怎样变化？",
                    "fixed_ending_contract": mathematical_fixed_ending_contract(),
                    "scenes": [
                        {
                            "scene_slug": "g001",
                            "scene_source_path": str(source.relative_to(root)),
                            "scene_source_root": str(source.parent.relative_to(root)),
                            "narration_path": str(narration.relative_to(root)),
                            "tts_input_path": str(tts_input.relative_to(root)),
                            "tts_input_mapping_path": str(mapping_path.relative_to(root)),
                            "duration_seconds": 20,
                        }
                    ],
                },
            )
            self.assertIn("cannot exactly reconstruct", " | ".join(result["errors"]))

    def test_receipt_rejects_stale_nested_mapping_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0009-test"
            source = episode / "src" / "g001.py"
            narration = episode / "g001.txt"
            tts_input = episode / "tts.txt"
            source.parent.mkdir(parents=True)
            source.write_text("from manim import *\n", encoding="utf-8")
            narration.write_text("先观察一个方向。这个方向怎样变化？", encoding="utf-8")
            registry_path, mapping_path = write_tts_mapping_v2(
                root=root,
                scene_slug="g001",
                formal_script=narration,
                tts_input=tts_input,
            )
            contract_path = episode / "readiness.json"
            contract_path.write_text(
                json.dumps(
                    {
                        "schema": "lecture-animation-episode-readiness-v2",
                        "author_id": "author:test",
                        "readiness_stage": "pre_tts",
                        "tts_route_id": TEST_TTS_ROUTE_ID,
                        "pronunciation_registry_path": str(registry_path.relative_to(root)),
                        "fixed_ending": "这个方向怎样变化？",
                        "fixed_ending_contract": mathematical_fixed_ending_contract(),
                        "scenes": [
                            {
                                "scene_slug": "g001",
                                "scene_source_path": str(source.relative_to(root)),
                                "scene_source_root": str(source.parent.relative_to(root)),
                                "narration_path": str(narration.relative_to(root)),
                                "tts_input_path": str(tts_input.relative_to(root)),
                                "tts_input_mapping_path": str(mapping_path.relative_to(root)),
                                "duration_seconds": 20,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            receipt = episode / "receipt.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    command_episode_preflight(
                        SimpleNamespace(
                            repo_root=str(root),
                            episode=str(episode),
                            contract=str(contract_path),
                            output=str(receipt),
                            require_clean=True,
                        )
                    ),
                    0,
                )
            mapping_path.write_text(
                mapping_path.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PipelineError, "stale"):
                validate_episode_readiness_receipt(
                    receipt, root, episode, "g001", required_stage="pre_tts"
                )

    def test_receipt_rejects_deleted_evidence_even_when_self_hash_is_recomputed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0009-test"
            source = episode / "src" / "g001.py"
            narration = episode / "g001.txt"
            tts_input = episode / "tts.txt"
            source.parent.mkdir(parents=True)
            source.write_text("from manim import *\n", encoding="utf-8")
            narration.write_text("先观察一个方向。这个方向怎样变化？", encoding="utf-8")
            registry_path, mapping_path = write_tts_mapping_v2(
                root=root,
                scene_slug="g001",
                formal_script=narration,
                tts_input=tts_input,
            )
            contract_path = episode / "readiness.json"
            contract_path.write_text(
                json.dumps(
                    {
                        "schema": "lecture-animation-episode-readiness-v2",
                        "author_id": "author:test",
                        "readiness_stage": "pre_tts",
                        "tts_route_id": TEST_TTS_ROUTE_ID,
                        "pronunciation_registry_path": str(registry_path.relative_to(root)),
                        "fixed_ending": "这个方向怎样变化？",
                        "fixed_ending_contract": mathematical_fixed_ending_contract(),
                        "scenes": [
                            {
                                "scene_slug": "g001",
                                "scene_source_path": str(source.relative_to(root)),
                                "scene_source_root": str(source.parent.relative_to(root)),
                                "narration_path": str(narration.relative_to(root)),
                                "tts_input_path": str(tts_input.relative_to(root)),
                                "tts_input_mapping_path": str(mapping_path.relative_to(root)),
                                "duration_seconds": 20,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            receipt_path = episode / "receipt.json"
            with redirect_stdout(io.StringIO()):
                command_episode_preflight(
                    SimpleNamespace(
                        repo_root=str(root),
                        episode=str(episode),
                        contract=str(contract_path),
                        output=str(receipt_path),
                        require_clean=True,
                    )
                )
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt.pop("pronunciation_registry")
            receipt.pop("receipt_hash")
            receipt["receipt_hash"] = engine.object_hash(receipt)
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(PipelineError, "readiness evidence hash"):
                validate_episode_readiness_receipt(receipt_path, root, episode, "g001")

    def test_pre_tts_rejects_noncanonical_registry_and_unregistered_sensitive_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0009-test"
            source = episode / "src" / "g001.py"
            narration = episode / "g001.txt"
            tts_input = episode / "tts.txt"
            source.parent.mkdir(parents=True)
            source.write_text("from manim import *\n", encoding="utf-8")
            narration.write_text("kappa 是参数。这个参数怎样变化？", encoding="utf-8")
            registry_path, mapping_path = write_tts_mapping_v2(
                root=root,
                scene_slug="g001",
                formal_script=narration,
                tts_input=tts_input,
            )
            alternate = root / "alternate-registry.json"
            alternate.write_text(registry_path.read_text(encoding="utf-8"), encoding="utf-8")
            result = run_episode_preflight(
                root,
                episode,
                {
                    "schema": "lecture-animation-episode-readiness-v2",
                    "author_id": "author:test",
                    "readiness_stage": "pre_tts",
                    "tts_route_id": TEST_TTS_ROUTE_ID,
                    "pronunciation_registry_path": str(alternate.relative_to(root)),
                    "sensitive_tokens": ["kappa"],
                    "fixed_ending": "这个参数怎样变化？",
                    "fixed_ending_contract": mathematical_fixed_ending_contract(),
                    "scenes": [
                        {
                            "scene_slug": "g001",
                            "scene_source_path": str(source.relative_to(root)),
                            "scene_source_root": str(source.parent.relative_to(root)),
                            "narration_path": str(narration.relative_to(root)),
                            "tts_input_path": str(tts_input.relative_to(root)),
                            "tts_input_mapping_path": str(mapping_path.relative_to(root)),
                            "duration_seconds": 20,
                        }
                    ],
                },
            )
            joined = " | ".join(result["errors"])
            self.assertIn("canonical Skill registry", joined)
            self.assertIn("missing sensitive tokens: kappa", joined)

    def test_pre_tts_rejects_boundary_whitespace_in_spoken_form(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0009-test"
            source = episode / "src" / "g001.py"
            narration = episode / "g001.txt"
            tts_input = episode / "tts.txt"
            source.parent.mkdir(parents=True)
            source.write_text("from manim import *\n", encoding="utf-8")
            narration.write_text("theta 是参数。这个参数怎样变化？", encoding="utf-8")
            registry_path, mapping_path = write_tts_mapping_v2(
                root=root,
                scene_slug="g001",
                formal_script=narration,
                tts_input=tts_input,
                spoken_forms={"theta": "\ntheta"},
            )
            result = run_episode_preflight(
                root,
                episode,
                {
                    "schema": "lecture-animation-episode-readiness-v2",
                    "author_id": "author:test",
                    "readiness_stage": "pre_tts",
                    "tts_route_id": TEST_TTS_ROUTE_ID,
                    "pronunciation_registry_path": str(registry_path.relative_to(root)),
                    "sensitive_tokens": ["theta"],
                    "fixed_ending": "这个参数怎样变化？",
                    "fixed_ending_contract": mathematical_fixed_ending_contract(),
                    "scenes": [
                        {
                            "scene_slug": "g001",
                            "scene_source_path": str(source.relative_to(root)),
                            "scene_source_root": str(source.parent.relative_to(root)),
                            "narration_path": str(narration.relative_to(root)),
                            "tts_input_path": str(tts_input.relative_to(root)),
                            "tts_input_mapping_path": str(mapping_path.relative_to(root)),
                            "duration_seconds": 20,
                        }
                    ],
                },
            )
            self.assertIn("boundary whitespace", " | ".join(result["errors"]))

    def test_pronunciation_binding_rejects_decoy_tts_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            formal = root / "formal.txt"
            exact = root / "exact.txt"
            decoy = root / "decoy.txt"
            formal.write_text("eta 是参数", encoding="utf-8")
            exact.write_text("伊塔 是参数", encoding="utf-8")
            decoy.write_text("伊塔 是参数", encoding="utf-8")
            registry = json.loads(CANONICAL_PRONUNCIATION_REGISTRY.read_text(encoding="utf-8"))
            errors: list[str] = []
            _validate_pronunciation_binding(
                token="eta",
                binding={
                    "scene_slug": "g001",
                    "spoken_form": "伊塔",
                    "tts_input_path": str(decoy.relative_to(root)),
                    "occurrences": 1,
                    "route_id": TEST_TTS_ROUTE_ID,
                },
                formal_count=1,
                readiness_stage="pre_tts",
                repo_root=root,
                narration_lookup={"g001": formal.read_text(encoding="utf-8")},
                scene_audio_paths={},
                author_id="author:test",
                route_id=TEST_TTS_ROUTE_ID,
                pronunciation_registry=registry,
                exact_mapping_evidence={"tts_input": artifact_snapshot(exact, root)},
                errors=errors,
            )
            self.assertIn("must equal the exact-mapped", " | ".join(errors))

    def test_promotion_validates_complete_batch_before_copying(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            canonical = root / "canonical"
            first = source / "videos" / "scene" / "first.md"
            second = source / "videos" / "scene" / "second.md"
            first.parent.mkdir(parents=True)
            first.write_text("portable", encoding="utf-8")
            second.write_text(
                "/Volumes/bocchi/myLectures-worktrees/agent-a/scene.md",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PipelineError, "temporary worktree"):
                command_promote_scene(
                    SimpleNamespace(
                        source_root=str(source),
                        canonical_root=str(canonical),
                        artifact=[
                            "videos/scene/first.md",
                            "videos/scene/second.md",
                        ],
                        replace=False,
                        output=str(root / "receipt.json"),
                    )
                )
            self.assertFalse((canonical / "videos" / "scene" / "first.md").exists())

    def test_promotion_rolls_back_when_receipt_cannot_be_written(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            canonical = root / "canonical"
            artifact = source / "videos" / "scene" / "first.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("portable", encoding="utf-8")
            blocking_parent = root / "not-a-directory"
            blocking_parent.write_text("block", encoding="utf-8")
            with self.assertRaises(Exception):
                command_promote_scene(
                    SimpleNamespace(
                        source_root=str(source),
                        canonical_root=str(canonical),
                        artifact=["videos/scene/first.md"],
                        replace=False,
                        output=str(blocking_parent / "receipt.json"),
                    )
                )
            self.assertFalse((canonical / "videos" / "scene" / "first.md").exists())

    def test_promotion_receipt_cannot_live_inside_promoted_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            canonical = root / "canonical"
            directory = source / "videos" / "scene" / "review"
            directory.mkdir(parents=True)
            (directory / "report.md").write_text("portable", encoding="utf-8")
            with self.assertRaisesRegex(PipelineError, "outside every promoted"):
                command_promote_scene(
                    SimpleNamespace(
                        source_root=str(source),
                        canonical_root=str(canonical),
                        artifact=["videos/scene/review"],
                        replace=False,
                        output=str(
                            canonical
                            / "videos"
                            / "scene"
                            / "review"
                            / "promotion_receipt.json"
                        ),
                    )
                )

    def test_all_supervisor_sessions_must_be_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "videos" / "0007-test"
            session_path = episode / "review" / "v2" / "supervisor_extra.json"
            session_path.parent.mkdir(parents=True)
            session = {
                "schema": "lecture-animation-supervisor-session-v2",
                "session_id": "session-test",
                "assignments": {},
                "task_queue": {},
                "replacement_authorizations": {},
                "identity_history": [],
            }
            session["session_hash"] = engine.object_hash(session)
            session_path.write_text(json.dumps(session), encoding="utf-8")
            with self.assertRaisesRegex(PipelineError, "still open"):
                engine.audit_all_supervisor_sessions(episode, root)
            session.pop("session_hash")
            session["closed_at"] = "2026-07-24T00:00:00+00:00"
            session["assignments"] = {"author": {"state": "active"}}
            session["session_hash"] = engine.object_hash(session)
            session_path.write_text(json.dumps(session), encoding="utf-8")
            with self.assertRaisesRegex(PipelineError, "unfinished roster"):
                engine.audit_all_supervisor_sessions(episode, root)
            session.pop("session_hash")
            session["assignments"] = {"author": {"state": "nonsense"}}
            session["session_hash"] = engine.object_hash(session)
            session_path.write_text(json.dumps(session), encoding="utf-8")
            with self.assertRaisesRegex(PipelineError, "invalid assignment"):
                engine.audit_all_supervisor_sessions(episode, root)
            session.pop("session_hash")
            session["assignments"] = {}
            session["session_hash"] = engine.object_hash(session)
            session_path.write_text(json.dumps(session), encoding="utf-8")
            summaries = engine.audit_all_supervisor_sessions(episode, root)
            self.assertEqual(summaries[0]["session_id"], "session-test")
            self.assertTrue(summaries[0]["completion_valid"])

    def test_blocked_phase_events_do_not_count_as_complete_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "videos" / "0007-test"
            evolution = episode / "review" / "evolution"
            evolution.mkdir(parents=True)
            rows = [
                {
                    "event_id": f"blocked-{phase}",
                    "scene_slug": "g001",
                    "phase": phase,
                    "result": "blocked",
                }
                for phase in ("design", "authoring", "render", "review", "repair")
            ]
            (evolution / "production_phases.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            metrics = engine.production_metrics(episode)
            self.assertEqual(metrics["phase_pairs_by_scene"]["g001"], [])
            self.assertEqual(
                set(metrics["missing_phase_pairs_by_scene"]["g001"]),
                {"design", "authoring", "render", "review", "repair"},
            )

    def test_revise_attempt_requires_repair_phase_even_when_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "videos" / "0007-test"
            evolution = episode / "review" / "evolution"
            evolution.mkdir(parents=True)
            phases = [
                {
                    "event_id": f"completed-{phase}",
                    "scene_slug": "g001",
                    "phase": phase,
                    "result": "completed",
                }
                for phase in ("design", "authoring", "render", "review")
            ]
            (evolution / "production_phases.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in phases),
                encoding="utf-8",
            )
            (evolution / "review_attempts.jsonl").write_text(
                json.dumps(
                    {
                        "attempt_id": "revise-1",
                        "scene_slug": "g001",
                        "verdict": "revise",
                        "gate_accepted": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            metrics = engine.production_metrics(episode)
            self.assertEqual(
                metrics["missing_phase_pairs_by_scene"]["g001"],
                ["repair"],
            )


if __name__ == "__main__":
    unittest.main()
