#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import wave


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

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
            },
            "design_chain": {
                "challenge_hash": challenge["challenge_hash"],
                "deliberation_hash": pipeline.object_hash(deliberation),
                "design_gate_hash": gate["design_gate_hash"],
                "precedent_packet_hash": packet["precedent_packet_hash"],
            },
            "selected_hypothesis_id": gate["selected_hypothesis_id"],
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
        return {
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

        profile = self.make_profile()
        self.assertTrue(pipeline.validate_profile_hash(profile))
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
        plan = self.make_plan(profile, bundle)
        self.assertEqual(pipeline.validate_scene_plan_data(profile, plan), [])
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
        telemetry = self.make_telemetry(profile)
        qc = pipeline.validate_authoring_qc_data(profile, plan, telemetry)
        self.assertTrue(qc["valid"], qc["issues"])
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
            "source": source,
            "timeline": self.episode / "timeline.json",
            "telemetry": telemetry_path,
            "authoring_qc": authoring_qc_path,
            "review_mp4": self.episode / "review.mp4",
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
        for index in range(1, 9):
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
                "expected_value": 10.0,
                "actual_value": 10.2,
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
        false_numeric_probe["probes"][0]["independent_check"]["actual_value"] = 12.0
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
        self.assertEqual(len(prepared_self_review["coverage_sweeps"]), 4)
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
            "rules_registry_hash": pipeline.object_hash(pipeline.load_rules()),
            "status": "active",
            "scenes": [],
            "full_reviews": 0,
            "diagnostic_reviews": 0,
            "reviewer_switches": 0,
            "calibration_scene_interval": 5,
            "calibration_due": False,
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
        with self.assertRaises(pipeline.PipelineError):
            pipeline.command_begin_review_batch(
                SimpleNamespace(
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
        ]
        metrics = pipeline.phase_metrics(rows)
        self.assertEqual(len(metrics["unique_events"]), 2)
        self.assertEqual(metrics["aggregate_agent_seconds"], 30.0)
        self.assertEqual(metrics["critical_path_seconds"], 20.0)
        self.assertEqual(metrics["concurrency_overlap_seconds"], 10.0)
        self.assertEqual(metrics["token_usage"]["input_tokens"], 300)

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
        baseline_manifest = {
            "schema": "lecture-animation-review-manifest-v2",
            "scene_slug": "g002c_riemann_sum_limit",
            "manifest_hash": "baseline-manifest",
            "artifacts": {
                "source": pipeline.artifact_snapshot(source_file, self.root),
                "telemetry": pipeline.artifact_snapshot(telemetry_file, self.root),
                "review_mp4": pipeline.artifact_snapshot(review_mp4, self.root),
                "qc": pipeline.artifact_snapshot(qc_dir, self.root),
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
                "affected_artifacts": ["source", "telemetry", "review_mp4", "qc"],
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
        current_manifest = json.loads(json.dumps(baseline_manifest))
        current_manifest["manifest_hash"] = "current-manifest"
        for key in ("source", "telemetry", "review_mp4", "qc"):
            current_manifest["artifacts"][key]["sha256"] += "-v2"
        response = pipeline.repair_response_draft_data(contract, current_manifest)
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
        gate = pipeline.repair_gate_data(response, contract, current_manifest)
        self.assertTrue(gate["valid"])
        self.assertEqual(pipeline.validate_repair_gate_data(gate, response, contract, current_manifest), [])

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
                        run_id="run-1",
                        scene_slug="g002c_riemann_sum_limit",
                        phase="authoring",
                        actor_model="test-author-v1",
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
        self.assertEqual(len(rows), 1)
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

    def test_screen_text_inventory_includes_project_wrappers(self) -> None:
        source = self.episode / "src" / "scenes" / "wrapped_formula_scene"
        source.mkdir(parents=True, exist_ok=True)
        (source / "objects.py").write_text(
            "formula = role_formula(r'F(\\omega)=1', font_size=40)\n"
            "symbol = math_tex(r'\\omega', font_size=30)\n"
            "caption = label('频率', font_size=28)\n",
            encoding="utf-8",
        )
        inventory = pipeline.scan_screen_text_inventory(source, self.root)
        self.assertEqual(inventory["constructor_counts"]["role_formula"], 1)
        self.assertEqual(inventory["constructor_counts"]["math_tex"], 1)
        self.assertEqual(inventory["constructor_counts"]["label"], 1)
        self.assertGreater(inventory["static_character_count"], 0)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
