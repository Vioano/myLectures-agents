"""Hard design-readiness receipt required before expensive audio and final renders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import object_hash


SCENE_DURATION_WARNING_SECONDS = 75.0
SCENE_DURATION_HARD_LIMIT_SECONDS = 90.0


def scene_complexity_gate_data(
    profile: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Decide whether one review scene is small enough to enter expensive production."""

    try:
        duration = float(profile.get("context", {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0
    exception = plan.get("scene_split_exception")
    exception_errors: list[str] = []
    if duration > SCENE_DURATION_HARD_LIMIT_SECONDS:
        if not isinstance(exception, dict):
            exception_errors.append("scene_split_exception is required")
        else:
            if len(str(exception.get("reason", "")).strip()) < 32:
                exception_errors.append("scene_split_exception.reason is too short")
            sections = exception.get("internal_sections")
            if not isinstance(sections, list) or len(sections) < 2:
                exception_errors.append("scene_split_exception requires at least two internal_sections")
            elif any(
                not isinstance(item, dict)
                or len(str(item.get("section_id", "")).strip()) < 2
                or not isinstance(item.get("stage_state_ids"), list)
                or not item.get("stage_state_ids")
                for item in sections
            ):
                exception_errors.append(
                    "every scene_split_exception internal section needs section_id and stage_state_ids"
                )
            checkpoints = exception.get("clearance_checkpoints")
            if not isinstance(checkpoints, list) or not checkpoints:
                exception_errors.append(
                    "scene_split_exception requires at least one clearance_checkpoint"
                )
            if len(str(exception.get("novice_continuity_reason", "")).strip()) < 24:
                exception_errors.append(
                    "scene_split_exception.novice_continuity_reason is too short"
                )
    if duration <= 0:
        status = "invalid_duration"
    elif duration <= SCENE_DURATION_WARNING_SECONDS:
        status = "within_target"
    elif duration <= SCENE_DURATION_HARD_LIMIT_SECONDS:
        status = "warning_long_scene"
    elif exception_errors:
        status = "split_required"
    else:
        status = "exception_accepted"
    return {
        "duration_seconds": duration,
        "warning_seconds": SCENE_DURATION_WARNING_SECONDS,
        "hard_limit_seconds": SCENE_DURATION_HARD_LIMIT_SECONDS,
        "status": status,
        "exception_errors": exception_errors,
        "exception_hash": object_hash(exception) if isinstance(exception, dict) else None,
    }


def _transition_id(item: dict[str, Any], index: int) -> str:
    return str(
        item.get("transition_id")
        or f"{item.get('from_state', 'state')}->{item.get('to_state', index)}"
    )


def design_readiness_draft_data(
    profile: dict[str, Any],
    plan: dict[str, Any],
    design_gate: dict[str, Any],
    authoring_qc: dict[str, Any],
    animatic_path: Path,
    animatic_sha256: str,
) -> dict[str, Any]:
    stage_states = [
        str(item.get("id") or item.get("state_id"))
        for item in plan.get("stage_states", [])
        if isinstance(item, dict) and (item.get("id") or item.get("state_id"))
    ]
    transitions = [
        _transition_id(item, index)
        for index, item in enumerate(plan.get("stage_transitions", []), 1)
        if isinstance(item, dict)
    ]
    return {
        "schema": "lecture-animation-design-readiness-v2",
        "scene_slug": plan.get("scene_slug") or profile.get("scene_slug"),
        "profile_hash": profile.get("profile_hash"),
        "plan_hash": plan.get("plan_hash") or object_hash(plan),
        "design_gate_hash": design_gate.get("gate_hash")
        or design_gate.get("design_gate_hash")
        or object_hash(design_gate),
        "authoring_qc_hash": authoring_qc.get("qc_hash") or object_hash(authoring_qc),
        "animatic": {
            "path": str(animatic_path.resolve()),
            "sha256": animatic_sha256,
        },
        "scene_complexity_gate": scene_complexity_gate_data(profile, plan),
        "continuous_playback": {
            "performed": False,
            "observation": "",
        },
        "muted_playback": {
            "performed": False,
            "teach_back": "",
            "driver_prediction": "",
        },
        "stage_state_checks": [
            {
                "stage_state_id": state_id,
                "timestamp_seconds": None,
                "visible_object_ids": [],
                "observation": "",
                "passed": False,
            }
            for state_id in stage_states
        ],
        "transition_checks": [
            {
                "transition_id": transition_id,
                "timestamp_seconds": None,
                "continuity_observation": "",
                "passed": False,
            }
            for transition_id in transitions
        ],
        "formula_memory_check": {
            "performed": False,
            "simultaneous_rows": 0,
            "single_slot_only": True,
            "observation": "",
        },
        "unresolved_design_issues": [],
        "design_frozen": False,
        "verdict": "draft",
    }


def validate_design_readiness_data(
    readiness: dict[str, Any],
    profile: dict[str, Any],
    plan: dict[str, Any],
    design_gate: dict[str, Any],
    authoring_qc: dict[str, Any],
    *,
    animatic_path: Path,
    animatic_sha256: str,
    require_hash: bool = True,
) -> list[str]:
    errors: list[str] = []
    expected = design_readiness_draft_data(
        profile, plan, design_gate, authoring_qc, animatic_path, animatic_sha256
    )
    if readiness.get("schema") != expected["schema"]:
        errors.append("design readiness schema is invalid")
    if require_hash:
        payload = dict(readiness)
        supplied_hash = payload.pop("readiness_hash", None)
        if supplied_hash != object_hash(payload):
            errors.append("design readiness hash is invalid")
    for field in (
        "scene_slug",
        "profile_hash",
        "plan_hash",
        "design_gate_hash",
        "authoring_qc_hash",
        "animatic",
        "scene_complexity_gate",
    ):
        if readiness.get(field) != expected.get(field):
            errors.append(f"design readiness is stale: {field}")
    complexity = readiness.get("scene_complexity_gate", {})
    if complexity.get("status") == "invalid_duration":
        errors.append("design readiness requires a positive authoritative scene duration")
    if complexity.get("status") == "split_required":
        errors.append(
            "scene exceeds 90 seconds and must be split before expensive production: "
            + "; ".join(map(str, complexity.get("exception_errors", [])))
        )
    if authoring_qc.get("valid") is not True:
        errors.append("design readiness requires a passing low-cost authoring QC artifact")
    if design_gate.get("valid") is not True:
        errors.append("design readiness requires a passing design deliberation gate")
    continuous = readiness.get("continuous_playback", {})
    if continuous.get("performed") is not True or len(
        str(continuous.get("observation", "")).strip()
    ) < 24:
        errors.append("design readiness requires concrete continuous-playback evidence")
    muted = readiness.get("muted_playback", {})
    if muted.get("performed") is not True:
        errors.append("design readiness requires a muted playback")
    for field in ("teach_back", "driver_prediction"):
        if len(str(muted.get(field, "")).strip()) < 24:
            errors.append(f"design readiness muted_playback.{field} is too short")
    expected_states = {
        item["stage_state_id"] for item in expected.get("stage_state_checks", [])
    }
    supplied_states = {
        str(item.get("stage_state_id")): item
        for item in readiness.get("stage_state_checks", [])
        if isinstance(item, dict)
    }
    if set(supplied_states) != expected_states:
        errors.append("design readiness must check every stage state exactly once")
    for state_id, item in supplied_states.items():
        if item.get("passed") is not True:
            errors.append(f"design readiness stage state {state_id} did not pass")
        if not isinstance(item.get("visible_object_ids"), list) or not item.get(
            "visible_object_ids"
        ):
            errors.append(f"design readiness stage state {state_id} needs visible objects")
        if len(str(item.get("observation", "")).strip()) < 20:
            errors.append(f"design readiness stage state {state_id} observation is too short")
        try:
            if float(item.get("timestamp_seconds")) < 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"design readiness stage state {state_id} timestamp is invalid")
    expected_transitions = {
        item["transition_id"] for item in expected.get("transition_checks", [])
    }
    supplied_transitions = {
        str(item.get("transition_id")): item
        for item in readiness.get("transition_checks", [])
        if isinstance(item, dict)
    }
    if set(supplied_transitions) != expected_transitions:
        errors.append("design readiness must check every stage transition exactly once")
    for transition_id, item in supplied_transitions.items():
        if item.get("passed") is not True:
            errors.append(f"design readiness transition {transition_id} did not pass")
        if len(str(item.get("continuity_observation", "")).strip()) < 20:
            errors.append(
                f"design readiness transition {transition_id} observation is too short"
            )
    if {"formula_dense", "stage_dense"} & set(profile.get("tags", [])):
        memory = readiness.get("formula_memory_check", {})
        required_rows = min(2, max(1, len(plan.get("formula_history", []))))
        if (
            memory.get("performed") is not True
            or int(memory.get("simultaneous_rows", 0) or 0) < required_rows
            or memory.get("single_slot_only") is not False
            or len(str(memory.get("observation", "")).strip()) < 20
        ):
            errors.append(
                "formula-dense design readiness must preserve simultaneous derivation memory"
            )
    if readiness.get("unresolved_design_issues") not in ([], None):
        errors.append("design readiness cannot contain unresolved design issues")
    if readiness.get("design_frozen") is not True:
        errors.append("design readiness must freeze the design before expensive production")
    if readiness.get("verdict") != "ready_for_audio_lock":
        errors.append("design readiness verdict must be ready_for_audio_lock")
    return errors
