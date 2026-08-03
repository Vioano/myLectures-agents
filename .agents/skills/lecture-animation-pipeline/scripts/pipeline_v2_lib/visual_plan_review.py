"""Independent detailed-visual-plan review after audio lock and before production."""

from __future__ import annotations

from typing import Any

from .core import object_hash


PLAN_COMPLETENESS_AREAS = (
    "learning_contract",
    "math_objects_and_drivers",
    "stage_regions_and_states",
    "transitions_clearance_and_identity",
    "composition_hierarchy_and_visual_finish",
    "screen_text_formula_memory_and_negative_space",
    "clause_to_state_and_audio_handoff",
)

PLAN_REVIEW_DIMENSIONS = (
    "novice_causality",
    "mathematical_object_truth",
    "stage_choreography_and_attention",
    "visual_composition_and_finish",
    "production_and_audio_handoff_feasibility",
)

SUPPORTED_PROBE_KINDS = {"keynote", "keyframe", "wireframe"}


def _stage_state_id(item: dict[str, Any], index: int) -> str:
    return str(item.get("id") or item.get("state_id") or f"state_{index}")


def _transition_id(item: dict[str, Any], index: int) -> str:
    return str(
        item.get("transition_id")
        or f"{item.get('from_state', 'state')}->{item.get('to_state', index)}"
    )


def visual_plan_review_draft_data(
    plan: dict[str, Any],
    *,
    scene_plan_validation: dict[str, Any],
    validation_binding: dict[str, Any],
    scene_production: dict[str, Any],
    scene_production_binding: dict[str, Any],
    author_agent_id: str,
    reviewer: str,
    reviewer_model: str,
    reasoning_effort: str,
    reviewer_agent_id: str,
    probe_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a reviewer-owned checklist from the complete plan, not from media."""

    states = [
        _stage_state_id(item, index)
        for index, item in enumerate(plan.get("stage_states", []), 1)
        if isinstance(item, dict)
    ]
    transitions = [
        _transition_id(item, index)
        for index, item in enumerate(plan.get("stage_transitions", []), 1)
        if isinstance(item, dict)
    ]
    probes = []
    for item in probe_evidence:
        probes.append(
            {
                **item,
                "purpose": "",
                "plan_section_ids": [],
                "supporting_only": True,
            }
        )
    return {
        "schema": "lecture-animation-visual-plan-review-v1",
        "scene_slug": plan.get("scene_slug"),
        "plan_hash": plan.get("plan_hash") or object_hash(plan),
        "scene_plan_validation_hash": scene_plan_validation.get(
            "validation_hash"
        ),
        "scene_plan_validation": validation_binding,
        "scene_production_hash": scene_production.get("scene_production_hash"),
        "scene_production": scene_production_binding,
        "author_agent_id": author_agent_id,
        "reviewer": reviewer,
        "reviewer_model": reviewer_model,
        "reasoning_effort": reasoning_effort,
        "reviewer_agent_id": reviewer_agent_id,
        "plan_completeness_checks": [
            {"area": area, "status": "draft", "observation": ""}
            for area in PLAN_COMPLETENESS_AREAS
        ],
        "quality_dimension_checks": [
            {"dimension": dimension, "status": "draft", "observation": ""}
            for dimension in PLAN_REVIEW_DIMENSIONS
        ],
        "stage_state_checks": [
            {
                "stage_state_id": state_id,
                "layout_and_focus_observation": "",
                "learner_task_and_evidence_observation": "",
                "passed": False,
            }
            for state_id in states
        ],
        "transition_checks": [
            {
                "transition_id": transition_id,
                "causal_trigger_observation": "",
                "identity_clearance_handoff_observation": "",
                "passed": False,
            }
            for transition_id in transitions
        ],
        "probe_evidence": probes,
        "probe_policy": {
            "optional": True,
            "supporting_evidence_only": True,
            "cannot_replace_detailed_plan": True,
            "time_based_animatic_is_not_required": True,
        },
        "detailed_plan_complete": False,
        "unresolved_findings": [],
        "verdict": "draft",
    }


def validate_visual_plan_review_data(
    review: dict[str, Any],
    plan: dict[str, Any],
    *,
    scene_plan_validation: dict[str, Any],
    validation_binding: dict[str, Any],
    scene_production: dict[str, Any],
    scene_production_binding: dict[str, Any],
    current_probe_evidence: list[dict[str, Any]],
    require_hash: bool = True,
) -> list[str]:
    errors: list[str] = []
    if review.get("schema") != "lecture-animation-visual-plan-review-v1":
        errors.append("visual plan review schema is invalid")
    if require_hash:
        payload = dict(review)
        supplied_hash = payload.pop("review_hash", None)
        if supplied_hash != object_hash(payload):
            errors.append("visual plan review hash is invalid")

    expected_plan_hash = plan.get("plan_hash") or object_hash(plan)
    if review.get("scene_slug") != plan.get("scene_slug"):
        errors.append("visual plan review is bound to another scene")
    if review.get("plan_hash") != expected_plan_hash:
        errors.append("visual plan review is stale for the current detailed plan")
    if scene_plan_validation.get("valid") is not True:
        errors.append("visual plan review requires a passing scene-plan validation")
    if review.get("scene_plan_validation_hash") != scene_plan_validation.get(
        "validation_hash"
    ):
        errors.append("visual plan review scene-plan validation hash is stale")
    if review.get("scene_plan_validation") != validation_binding:
        errors.append("visual plan review scene-plan validation artifact is stale")
    if review.get("scene_production_hash") != scene_production.get(
        "scene_production_hash"
    ):
        errors.append("visual plan review exact scene-production hash is stale")
    if review.get("scene_production") != scene_production_binding:
        errors.append("visual plan review exact scene-production artifact is stale")
    if scene_production.get("scene_slug") != plan.get("scene_slug"):
        errors.append("visual plan review scene production is bound to another scene")

    author_id = str(review.get("author_agent_id", "")).strip()
    reviewer_id = str(review.get("reviewer_agent_id", "")).strip()
    if not author_id or not reviewer_id:
        errors.append("visual plan review requires author and reviewer agent identities")
    elif author_id == reviewer_id:
        errors.append("visual plan review must be independent from the plan author")
    for field in ("reviewer", "reviewer_model", "reasoning_effort"):
        if not str(review.get(field, "")).strip():
            errors.append(f"visual plan review requires {field}")

    completeness_rows = [
        item
        for item in review.get("plan_completeness_checks", [])
        if isinstance(item, dict)
    ]
    completeness = {
        str(item.get("area")): item
        for item in completeness_rows
    }
    if (
        len(completeness_rows) != len(PLAN_COMPLETENESS_AREAS)
        or set(completeness) != set(PLAN_COMPLETENESS_AREAS)
    ):
        errors.append("visual plan review must cover every detailed-plan area exactly once")
    for area, item in completeness.items():
        if item.get("status") != "pass":
            errors.append(f"visual plan review completeness area {area} did not pass")
        if len(str(item.get("observation", "")).strip()) < 24:
            errors.append(
                f"visual plan review completeness area {area} needs concrete evidence"
            )

    dimension_rows = [
        item
        for item in review.get("quality_dimension_checks", [])
        if isinstance(item, dict)
    ]
    dimensions = {
        str(item.get("dimension")): item
        for item in dimension_rows
    }
    if (
        len(dimension_rows) != len(PLAN_REVIEW_DIMENSIONS)
        or set(dimensions) != set(PLAN_REVIEW_DIMENSIONS)
    ):
        errors.append("visual plan review must cover every quality dimension exactly once")
    for dimension, item in dimensions.items():
        if item.get("status") != "pass":
            errors.append(f"visual plan review dimension {dimension} did not pass")
        if len(str(item.get("observation", "")).strip()) < 24:
            errors.append(
                f"visual plan review dimension {dimension} needs concrete evidence"
            )

    expected_states = {
        _stage_state_id(item, index)
        for index, item in enumerate(plan.get("stage_states", []), 1)
        if isinstance(item, dict)
    }
    supplied_state_rows = [
        item
        for item in review.get("stage_state_checks", [])
        if isinstance(item, dict)
    ]
    supplied_states = {
        str(item.get("stage_state_id")): item
        for item in supplied_state_rows
    }
    if (
        len(supplied_state_rows) != len(expected_states)
        or set(supplied_states) != expected_states
    ):
        errors.append("visual plan review must inspect every stage state exactly once")
    for state_id, item in supplied_states.items():
        if item.get("passed") is not True:
            errors.append(f"visual plan review stage state {state_id} did not pass")
        for field in (
            "layout_and_focus_observation",
            "learner_task_and_evidence_observation",
        ):
            if len(str(item.get(field, "")).strip()) < 20:
                errors.append(
                    f"visual plan review stage state {state_id} needs {field}"
                )

    expected_transitions = {
        _transition_id(item, index)
        for index, item in enumerate(plan.get("stage_transitions", []), 1)
        if isinstance(item, dict)
    }
    supplied_transition_rows = [
        item
        for item in review.get("transition_checks", [])
        if isinstance(item, dict)
    ]
    supplied_transitions = {
        str(item.get("transition_id")): item
        for item in supplied_transition_rows
    }
    if (
        len(supplied_transition_rows) != len(expected_transitions)
        or set(supplied_transitions) != expected_transitions
    ):
        errors.append("visual plan review must inspect every transition exactly once")
    for transition_id, item in supplied_transitions.items():
        if item.get("passed") is not True:
            errors.append(
                f"visual plan review transition {transition_id} did not pass"
            )
        for field in (
            "causal_trigger_observation",
            "identity_clearance_handoff_observation",
        ):
            if len(str(item.get(field, "")).strip()) < 20:
                errors.append(
                    f"visual plan review transition {transition_id} needs {field}"
                )

    supplied_probes = review.get("probe_evidence", [])
    if not isinstance(supplied_probes, list):
        errors.append("visual plan review probe_evidence must be a list")
        supplied_probes = []
    if len(supplied_probes) != len(current_probe_evidence):
        errors.append("visual plan review probe evidence set is stale")
    for index, expected in enumerate(current_probe_evidence):
        if index >= len(supplied_probes) or not isinstance(supplied_probes[index], dict):
            continue
        item = supplied_probes[index]
        for field in ("kind", "artifact"):
            if item.get(field) != expected.get(field):
                errors.append(
                    f"visual plan review probe {index + 1} {field} is stale"
                )
        if item.get("kind") not in SUPPORTED_PROBE_KINDS:
            errors.append(f"visual plan review probe {index + 1} kind is invalid")
        if item.get("supporting_only") is not True:
            errors.append(
                f"visual plan review probe {index + 1} must remain supporting evidence"
            )
        if len(str(item.get("purpose", "")).strip()) < 16:
            errors.append(f"visual plan review probe {index + 1} needs a purpose")
        section_ids = item.get("plan_section_ids")
        if not isinstance(section_ids, list) or not section_ids:
            errors.append(
                f"visual plan review probe {index + 1} must name plan sections"
            )

    expected_policy = {
        "optional": True,
        "supporting_evidence_only": True,
        "cannot_replace_detailed_plan": True,
        "time_based_animatic_is_not_required": True,
    }
    if review.get("probe_policy") != expected_policy:
        errors.append(
            "visual plan review must state that probes are optional supporting evidence"
        )
    if review.get("detailed_plan_complete") is not True:
        errors.append("visual plan review cannot pass without a complete detailed plan")
    if review.get("unresolved_findings") not in ([], None):
        errors.append("visual plan review cannot pass with unresolved findings")
    if review.get("verdict") != "ready_for_animation_production":
        errors.append(
            "visual plan review verdict must be ready_for_animation_production"
        )
    return errors
