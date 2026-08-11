"""Decision-time progressive disclosure and evidence for learner-facing text.

The author sees a neutral reflection prompt *before* a visible string is
accepted into a scene contract.  Reflection is intentionally not a verdict:
the author must argue both for keeping the text and for removing/replacing it.
Formal registration remains deterministic and cannot be overridden by the
author's declaration.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

from .core import PipelineError, object_hash, utc_now
from .presentation_boundary import (
    presentation_boundary_risk_signals,
    presentation_boundary_violation,
)
from .storage import (
    append_jsonl_unlocked,
    atomic_write_text_unlocked,
    atomic_write_json_unlocked,
    load_json,
    load_json_unlocked,
    locked_paths,
    read_jsonl,
    read_jsonl_unlocked,
    write_json,
)


REGISTRATION_CONTRACT_VERSION = 1
PREREGISTRATION_SCHEMA = "lecture-animation-screen-text-preregistration-v1"
REFLECTION_DRAFT_SCHEMA = "lecture-animation-screen-text-reflection-draft-v1"
REFLECTION_SCHEMA = "lecture-animation-screen-text-reflection-v1"
REGISTRY_SCHEMA = "lecture-animation-screen-text-registry-v1"
ATTEMPT_SCHEMA = "lecture-animation-screen-text-registration-attempt-v1"
OBSERVATION_SCHEMA = "lecture-animation-screen-text-scene-observation-v1"
RECEIPT_SCHEMA = "lecture-animation-screen-text-registration-receipt-v1"
EXPERIMENT_SCHEMA = "lecture-animation-skill-experiment-v1"

SCREEN_TEXT_ROLES = {
    "math_formula",
    "object_label",
    "axis_or_tick",
    "parameter_value",
    "scene_title",
    "comparison_label",
    "transient_question",
}
NARRATION_EXEMPT_ROLES = {
    "math_formula",
    "object_label",
    "axis_or_tick",
    "parameter_value",
}


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _resolve(raw: str, root: Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else root / path


def _compact_visible_text(value: str) -> str:
    return re.sub(r"[\s，。！？、；：,.!?;:'\"“”‘’（）()\[\]{}]+", "", str(value))


def _valid_hashed_record(value: dict[str, Any], field: str) -> bool:
    payload = dict(value)
    expected = payload.pop(field, None)
    return bool(expected) and expected == object_hash(payload)


def _validate_profile(profile: dict[str, Any]) -> None:
    if not _valid_hashed_record(profile, "profile_hash"):
        raise PipelineError("compiled profile hash is invalid")
    if int(profile.get("autopilot_contract_version") or 0) < 8:
        raise PipelineError(
            "screen-text preregistration requires autopilot_contract_version >= 8"
        )
    gate = profile.get("screen_text_registration_gate")
    if not isinstance(gate, dict) or gate.get("contract_version") != 1:
        raise PipelineError("compiled profile does not carry the v1 screen-text gate")


def screen_text_gate_descriptor(
    profile: dict[str, Any], repo_root: Path
) -> dict[str, Any]:
    """Return the hash-bound gate instructions embedded in new profiles."""

    context = profile.get("context", {})
    episode = _resolve(str(context.get("episode", "")), repo_root)
    scene_slug = str(context.get("scene_slug", "")).strip()
    if not scene_slug:
        raise PipelineError("profile is missing context.scene_slug")
    registry_directory = episode / "review" / "v2" / scene_slug
    attempt_log = episode / "review" / "evolution" / "screen_text_registration_attempts.jsonl"
    return {
        "contract_version": REGISTRATION_CONTRACT_VERSION,
        "experiment_id": "screen-text-decision-gate-v1",
        "required": True,
        "decision_order": [
            "prepare-screen-text-registration",
            "seal-screen-text-reflection",
            "commit-screen-text-registration",
        ],
        "decision_time_disclosure": True,
        "neutral_reflection_required": True,
        "formal_registration_required_before_source_authoring": True,
        "registry_directory": _relative_or_absolute(registry_directory, repo_root),
        "registry_filename_rule": "screen_text_registry_<profile_hash_prefix_12>.json",
        "contract_filename_rule": "screen_text_contract_<profile_hash_prefix_12>.json",
        "attempt_log_path": _relative_or_absolute(attempt_log, repo_root),
        "missing_ledger_interpretation": "unknown_not_zero",
    }


def screen_text_registration_paths(
    profile: dict[str, Any], repo_root: Path
) -> tuple[Path, Path]:
    _validate_profile(profile)
    gate = profile["screen_text_registration_gate"]
    directory = _resolve(str(gate.get("registry_directory", "")), repo_root)
    registry = directory / f"screen_text_registry_{str(profile['profile_hash'])[:12]}.json"
    attempt_log = _resolve(str(gate.get("attempt_log_path", "")), repo_root)
    return registry, attempt_log


def screen_text_contract_path(profile: dict[str, Any], repo_root: Path) -> Path:
    registry, _ = screen_text_registration_paths(profile, repo_root)
    return registry.with_name(
        f"screen_text_contract_{str(profile['profile_hash'])[:12]}.json"
    )


def initialize_screen_text_registration(
    profile: dict[str, Any], repo_root: Path
) -> tuple[dict[str, Any], Path, Path, Path]:
    """Create the deterministic empty registry/contract for a new v8 profile.

    This makes a truthful zero-visible-literal scene representable and marks
    the episode ledger as observed even when no candidate text is proposed.
    Existing profile-bound registrations are preserved on recompilation.
    """

    registry_path, attempt_log = screen_text_registration_paths(profile, repo_root)
    contract_path = screen_text_contract_path(profile, repo_root)
    with locked_paths([registry_path, attempt_log, contract_path]):
        if registry_path.exists():
            registry = load_json_unlocked(registry_path)
            if not _valid_hashed_record(registry, "registry_hash"):
                raise PipelineError("existing screen-text registry hash is invalid")
            if registry.get("profile_hash") != profile.get("profile_hash"):
                raise PipelineError("existing screen-text registry belongs to another profile")
        else:
            registry = _registry_payload(
                profile=profile,
                registry_path=registry_path,
                attempt_log=attempt_log,
                items=[],
                repo_root=repo_root,
            )
            atomic_write_json_unlocked(registry_path, registry)
        if not attempt_log.exists():
            atomic_write_text_unlocked(attempt_log, "")
        contract_patch = _screen_text_contract_patch(profile, registry, repo_root)
        atomic_write_json_unlocked(contract_path, contract_patch)
        observation_seed = {
            "episode": profile.get("context", {}).get("episode"),
            "scene_slug": profile.get("context", {}).get("scene_slug"),
            "profile_hash": profile.get("profile_hash"),
        }
        observation_id = (
            "screen-text-scene-observation:" + object_hash(observation_seed)[:24]
        )
        existing_observation = next(
            (
                row
                for row in read_jsonl_unlocked(attempt_log)
                if row.get("observation_id") == observation_id
            ),
            None,
        )
        if existing_observation is not None:
            if not _valid_hashed_record(existing_observation, "observation_hash"):
                raise PipelineError("existing screen-text scene observation hash is invalid")
            if existing_observation.get("profile_hash") != profile.get("profile_hash"):
                raise PipelineError(
                    "existing screen-text scene observation belongs to another profile"
                )
        else:
            observation: dict[str, Any] = {
                "schema": OBSERVATION_SCHEMA,
                "contract_version": REGISTRATION_CONTRACT_VERSION,
                "observation_id": observation_id,
                "created_at": utc_now(),
                **observation_seed,
                "skill_tree_hash": profile.get("skill_tree_hash_at_profile_compile"),
                "live_policy_hash": profile.get("live_policy_hash"),
                "registry_path": _relative_or_absolute(registry_path, repo_root),
                "registry_hash": registry.get("registry_hash"),
                "contract_path": _relative_or_absolute(contract_path, repo_root),
                "status": "gate_initialized",
            }
            observation["observation_hash"] = object_hash(observation)
            append_jsonl_unlocked(attempt_log, observation)
    return registry, registry_path, attempt_log, contract_path


def _candidate_from_args(args: argparse.Namespace) -> dict[str, Any]:
    payload = str(args.payload).strip()
    constructor = str(args.constructor).strip()
    role = str(args.role).strip()
    if not payload or not constructor:
        raise PipelineError("constructor and payload must be non-empty")
    if role not in SCREEN_TEXT_ROLES:
        raise PipelineError(f"unsupported screen-text role: {role!r}")
    if int(args.count) < 1:
        raise PipelineError("count must be positive")
    return {
        "constructor": constructor,
        "payload": payload,
        "count": int(args.count),
        "role": role,
    }


def build_screen_text_preregistration(
    profile: dict[str, Any], candidate: dict[str, Any], repo_root: Path
) -> dict[str, Any]:
    _validate_profile(profile)
    registry, attempt_log = screen_text_registration_paths(profile, repo_root)
    signals = presentation_boundary_risk_signals(str(candidate.get("payload", "")))
    result: dict[str, Any] = {
        "schema": PREREGISTRATION_SCHEMA,
        "contract_version": REGISTRATION_CONTRACT_VERSION,
        "created_at": utc_now(),
        "episode": profile.get("context", {}).get("episode"),
        "scene_slug": profile.get("context", {}).get("scene_slug"),
        "profile_hash": profile.get("profile_hash"),
        "skill_tree_hash": profile.get("skill_tree_hash_at_profile_compile"),
        "live_policy_hash": profile.get("live_policy_hash"),
        "candidate": candidate,
        "risk_assessment": {
            "status": "reflection_required_not_a_verdict",
            "matched_signals": signals,
            "signal_count": len(signals),
            "applicable_rule_ids": ["BOUND-001"],
            "neutral_disclosure": (
                "这些匹配只是风险信号，不是判决。请同时检验两种可能：这段文字也许承载了"
                "数学对象无法独立呈现的学习信息；也可能只是在描述课程、制作流程、创作者"
                "身份或转场安排。"
            ),
            "keep_hypothesis": (
                "明确指出删掉这段文字后，学习者会失去哪一条不可由画面对象替代的信息。"
            ),
            "remove_or_replace_hypothesis": (
                "检验真实数学对象、动作、更短的局部标签或直接的学习问题，能否在不外化"
                "制作意图的情况下承担同一工作。"
            ),
            "anti_bias_instruction": (
                "不要因为出现风险信号就预设文字一定错误，也不要因为作者自称必要就预设"
                "它一定应该保留。"
            ),
        },
        "required_next_state": "reflected_keep_or_revise_or_remove",
        "registry_path": _relative_or_absolute(registry, repo_root),
        "attempt_log_path": _relative_or_absolute(attempt_log, repo_root),
    }
    result["preregistration_hash"] = object_hash(result)
    return result


def reflection_draft_data(preregistration: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": REFLECTION_DRAFT_SCHEMA,
        "preregistration_hash": preregistration.get("preregistration_hash"),
        "decision": "keep|revise|remove",
        "case_for_keep": "",
        "case_for_remove_or_replace": "",
        "learner_visible_information": "",
        "removal_test": "",
        "boundary_analysis": "",
        "revision_reason": "",
        "revised_payload": "",
        "removal_reason": "",
        "semantic_evidence": {
            "unique_visual_job": "",
            "necessity": "",
            "removal_failure": "",
            "clearance_condition": "",
            "anchor_type": "math_object_anchor|learner_question_anchor",
            "anchor_id": "",
            "duplicates_narration": "true|false",
            "externalizes_production_intent": "true|false",
        },
        "counterreflection": {
            "strongest_reason_keep_is_wrong": "",
            "strongest_reason_remove_is_wrong": "",
            "final_decision_after_counterreflection": "",
        },
    }


def _require_text(value: Any, label: str, minimum: int) -> str:
    text = str(value or "").strip()
    if len(text) < minimum:
        raise PipelineError(f"{label} must contain at least {minimum} characters")
    return text


def validate_preregistration(value: dict[str, Any]) -> None:
    if value.get("schema") != PREREGISTRATION_SCHEMA:
        raise PipelineError("preregistration schema is invalid")
    if not _valid_hashed_record(value, "preregistration_hash"):
        raise PipelineError("preregistration hash is invalid")
    candidate = value.get("candidate")
    if not isinstance(candidate, dict):
        raise PipelineError("preregistration candidate is missing")
    if str(candidate.get("role", "")) not in SCREEN_TEXT_ROLES:
        raise PipelineError("preregistration role is invalid")


def seal_screen_text_reflection(
    preregistration: dict[str, Any], draft: dict[str, Any]
) -> dict[str, Any]:
    validate_preregistration(preregistration)
    if draft.get("schema") != REFLECTION_DRAFT_SCHEMA:
        raise PipelineError("reflection input must use the reflection-draft schema")
    if draft.get("preregistration_hash") != preregistration.get("preregistration_hash"):
        raise PipelineError("reflection draft does not bind the preregistration")
    decision = str(draft.get("decision", "")).strip().lower()
    if decision not in {"keep", "revise", "remove"}:
        raise PipelineError("reflection decision must be keep, revise, or remove")
    case_for_keep = _require_text(draft.get("case_for_keep"), "case_for_keep", 12)
    case_for_remove = _require_text(
        draft.get("case_for_remove_or_replace"),
        "case_for_remove_or_replace",
        12,
    )
    if _compact_visible_text(case_for_keep) == _compact_visible_text(case_for_remove):
        raise PipelineError("keep and remove/replace cases must be materially different")
    common = {
        "case_for_keep": case_for_keep,
        "case_for_remove_or_replace": case_for_remove,
        "learner_visible_information": _require_text(
            draft.get("learner_visible_information"),
            "learner_visible_information",
            12,
        ),
        "removal_test": _require_text(draft.get("removal_test"), "removal_test", 12),
        "boundary_analysis": _require_text(
            draft.get("boundary_analysis"), "boundary_analysis", 12
        ),
    }
    semantic: dict[str, Any] | None = None
    revised_payload = ""
    revision_reason = ""
    removal_reason = ""
    if decision == "keep":
        raw_semantic = draft.get("semantic_evidence")
        if not isinstance(raw_semantic, dict):
            raise PipelineError("keep requires semantic_evidence")
        anchor_type = str(raw_semantic.get("anchor_type", "")).strip()
        anchor_id = _require_text(raw_semantic.get("anchor_id"), "anchor_id", 4)
        if anchor_type not in {"math_object_anchor", "learner_question_anchor"}:
            raise PipelineError(
                "semantic_evidence.anchor_type must be math_object_anchor or learner_question_anchor"
            )
        if raw_semantic.get("duplicates_narration") is not False:
            raise PipelineError("semantic_evidence must set duplicates_narration=false")
        if raw_semantic.get("externalizes_production_intent") is not False:
            raise PipelineError(
                "semantic_evidence must set externalizes_production_intent=false"
            )
        semantic = {
            "unique_visual_job": _require_text(
                raw_semantic.get("unique_visual_job"), "unique_visual_job", 12
            ),
            "necessity": _require_text(raw_semantic.get("necessity"), "necessity", 16),
            "removal_failure": _require_text(
                raw_semantic.get("removal_failure"), "removal_failure", 16
            ),
            "clearance_condition": _require_text(
                raw_semantic.get("clearance_condition"), "clearance_condition", 8
            ),
            "anchor_type": anchor_type,
            "anchor_id": anchor_id,
            "duplicates_narration": False,
            "externalizes_production_intent": False,
        }
    elif decision == "revise":
        revised_payload = _require_text(draft.get("revised_payload"), "revised_payload", 1)
        original = str(preregistration.get("candidate", {}).get("payload", "")).strip()
        if revised_payload == original:
            raise PipelineError("revised_payload must differ from the preregistered payload")
        revision_reason = _require_text(draft.get("revision_reason"), "revision_reason", 12)
    else:
        removal_reason = _require_text(draft.get("removal_reason"), "removal_reason", 12)

    risk_count = int(
        preregistration.get("risk_assessment", {}).get("signal_count", 0) or 0
    )
    counterreflection: dict[str, str] | None = None
    if decision == "keep" and risk_count:
        raw_counter = draft.get("counterreflection")
        if not isinstance(raw_counter, dict):
            raise PipelineError("risk-signalled keep requires counterreflection")
        final_decision = str(
            raw_counter.get("final_decision_after_counterreflection", "")
        ).strip().lower()
        if final_decision != "keep":
            raise PipelineError(
                "risk-signalled keep requires final_decision_after_counterreflection=keep; "
                "otherwise seal a revise/remove reflection"
            )
        counterreflection = {
            "strongest_reason_keep_is_wrong": _require_text(
                raw_counter.get("strongest_reason_keep_is_wrong"),
                "counterreflection.strongest_reason_keep_is_wrong",
                12,
            ),
            "strongest_reason_remove_is_wrong": _require_text(
                raw_counter.get("strongest_reason_remove_is_wrong"),
                "counterreflection.strongest_reason_remove_is_wrong",
                12,
            ),
            "final_decision_after_counterreflection": "keep",
        }

    result: dict[str, Any] = {
        "schema": REFLECTION_SCHEMA,
        "contract_version": REGISTRATION_CONTRACT_VERSION,
        "created_at": utc_now(),
        "preregistration_hash": preregistration.get("preregistration_hash"),
        "profile_hash": preregistration.get("profile_hash"),
        "scene_slug": preregistration.get("scene_slug"),
        "decision": decision,
        "reflected_state": f"reflected_{decision}",
        **common,
        "semantic_evidence": semantic,
        "revised_payload": revised_payload,
        "revision_reason": revision_reason,
        "removal_reason": removal_reason,
        "counterreflection": counterreflection,
    }
    result["reflection_hash"] = object_hash(result)
    return result


def validate_reflection(
    preregistration: dict[str, Any], reflection: dict[str, Any]
) -> None:
    validate_preregistration(preregistration)
    if reflection.get("schema") != REFLECTION_SCHEMA:
        raise PipelineError("reflection schema is invalid")
    if not _valid_hashed_record(reflection, "reflection_hash"):
        raise PipelineError("reflection hash is invalid")
    if reflection.get("preregistration_hash") != preregistration.get(
        "preregistration_hash"
    ):
        raise PipelineError("reflection does not bind the preregistration")
    if reflection.get("profile_hash") != preregistration.get("profile_hash"):
        raise PipelineError("reflection profile_hash changed")


def _formal_block_reasons(
    profile: dict[str, Any], preregistration: dict[str, Any], reflection: dict[str, Any]
) -> list[str]:
    if reflection.get("decision") != "keep":
        return []
    candidate = preregistration["candidate"]
    payload = str(candidate.get("payload", ""))
    role = str(candidate.get("role", ""))
    reasons: list[str] = []
    violation = presentation_boundary_violation(payload)
    if violation:
        reasons.append(f"presentation boundary: {violation}")
    compact_payload = _compact_visible_text(payload)
    compact_narration = _compact_visible_text(
        str(profile.get("context", {}).get("narration", ""))
    )
    if (
        role not in NARRATION_EXEMPT_ROLES
        and len(compact_payload) >= 4
        and compact_payload in compact_narration
    ):
        reasons.append("payload duplicates the spoken narration")
    chinese_count = len(re.findall(r"[\u3400-\u9fff]", payload))
    role_limits = {
        "object_label": 10,
        "axis_or_tick": 10,
        "parameter_value": 10,
        "comparison_label": 14,
        "scene_title": 24,
        "transient_question": 30,
    }
    if role in role_limits and chinese_count > role_limits[role]:
        reasons.append(
            f"payload exceeds the {role} learner-facing length limit ({chinese_count}>{role_limits[role]})"
        )
    return reasons


def _semantic_item(
    preregistration: dict[str, Any], reflection: dict[str, Any], attempt_id: str
) -> dict[str, Any]:
    candidate = preregistration["candidate"]
    semantic = reflection.get("semantic_evidence") or {}
    item: dict[str, Any] = {
        "constructor": candidate.get("constructor"),
        "payload": candidate.get("payload"),
        "count": candidate.get("count"),
        "role": candidate.get("role"),
        "unique_visual_job": semantic.get("unique_visual_job"),
        "necessity": semantic.get("necessity"),
        "removal_failure": semantic.get("removal_failure"),
        "clearance_condition": semantic.get("clearance_condition"),
        "duplicates_narration": False,
        "externalizes_production_intent": False,
        "registration_attempt_id": attempt_id,
        "preregistration_hash": preregistration.get("preregistration_hash"),
        "reflection_hash": reflection.get("reflection_hash"),
    }
    item[str(semantic.get("anchor_type"))] = semantic.get("anchor_id")
    item["registration_id"] = "screen-text-registration:" + object_hash(item)[:24]
    return item


def _registry_payload(
    *, profile: dict[str, Any], registry_path: Path, attempt_log: Path, items: list[dict[str, Any]], repo_root: Path
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": REGISTRY_SCHEMA,
        "contract_version": REGISTRATION_CONTRACT_VERSION,
        "episode": profile.get("context", {}).get("episode"),
        "scene_slug": profile.get("context", {}).get("scene_slug"),
        "profile_hash": profile.get("profile_hash"),
        "skill_tree_hash": profile.get("skill_tree_hash_at_profile_compile"),
        "live_policy_hash": profile.get("live_policy_hash"),
        "registry_path": _relative_or_absolute(registry_path, repo_root),
        "attempt_log_path": _relative_or_absolute(attempt_log, repo_root),
        "semantic_items": sorted(
            items,
            key=lambda item: (
                str(item.get("constructor", "")),
                str(item.get("payload", "")),
            ),
        ),
    }
    value["registry_hash"] = object_hash(value)
    return value


def _screen_text_contract_patch(
    profile: dict[str, Any], registry: dict[str, Any], repo_root: Path
) -> dict[str, Any]:
    registry_path = _resolve(str(registry.get("registry_path", "")), repo_root)
    baseline_path = registry_path.with_name("text_inventory_baseline.json")
    return {
        "mode": "exact",
        "baseline_path": _relative_or_absolute(baseline_path, repo_root),
        "purpose": (
            "Bind every learner-facing text payload to a preregistered learning job, "
            "reflection receipt, and exact source inventory."
        ),
        "semantic_items": registry.get("semantic_items", []),
        "dynamic_payload_policy": "runtime_registered",
        "dynamic_payload_count": 0,
        "narration_duplicate_payloads": [],
        "producer_intent_payloads": [],
        "registration_contract_version": REGISTRATION_CONTRACT_VERSION,
        "registration_registry_path": registry.get("registry_path"),
        "registration_registry_hash": registry.get("registry_hash"),
        "registration_attempt_log_path": registry.get("attempt_log_path"),
        "profile_hash": profile.get("profile_hash"),
        "skill_tree_hash": profile.get("skill_tree_hash_at_profile_compile"),
    }


def commit_screen_text_registration(
    *,
    repo_root: Path,
    profile: dict[str, Any],
    preregistration: dict[str, Any],
    reflection: dict[str, Any],
    output_path: Path,
    registry_override: Path | None = None,
    attempt_log_override: Path | None = None,
) -> tuple[dict[str, Any], int]:
    _validate_profile(profile)
    validate_reflection(preregistration, reflection)
    if profile.get("profile_hash") != preregistration.get("profile_hash"):
        raise PipelineError("preregistration was prepared for a different profile")
    if profile.get("context", {}).get("scene_slug") != preregistration.get("scene_slug"):
        raise PipelineError("preregistration was prepared for a different scene")
    canonical_registry, canonical_attempt_log = screen_text_registration_paths(
        profile, repo_root
    )
    # Make even blocked/withdrawn decisions traceable to an observed scene gate.
    # This is idempotent when compile-profile already initialized the profile.
    initialize_screen_text_registration(profile, repo_root)
    registry_path = (registry_override or canonical_registry).resolve()
    attempt_log = (attempt_log_override or canonical_attempt_log).resolve()
    contract_path = screen_text_contract_path(profile, repo_root).resolve()
    if registry_path != canonical_registry.resolve():
        raise PipelineError(
            f"screen-text registry must use the profile-bound path: {canonical_registry}"
        )
    if attempt_log != canonical_attempt_log.resolve():
        raise PipelineError(
            f"screen-text attempt log must use the profile-bound path: {canonical_attempt_log}"
        )

    decision = str(reflection.get("decision"))
    seed = {
        "profile_hash": profile.get("profile_hash"),
        "preregistration_hash": preregistration.get("preregistration_hash"),
        "reflection_hash": reflection.get("reflection_hash"),
        "decision": decision,
    }
    attempt_id = "screen-text-attempt:" + object_hash(seed)[:24]
    block_reasons = _formal_block_reasons(profile, preregistration, reflection)
    if decision == "revise":
        formal_status = "revision_required"
    elif decision == "remove":
        formal_status = "withdrawn"
    elif block_reasons:
        formal_status = "blocked"
    else:
        formal_status = "registered"
    attempt: dict[str, Any] = {
        "schema": ATTEMPT_SCHEMA,
        "contract_version": REGISTRATION_CONTRACT_VERSION,
        "attempt_id": attempt_id,
        "created_at": utc_now(),
        "episode": profile.get("context", {}).get("episode"),
        "scene_slug": profile.get("context", {}).get("scene_slug"),
        "profile_hash": profile.get("profile_hash"),
        "skill_tree_hash": profile.get("skill_tree_hash_at_profile_compile"),
        "live_policy_hash": profile.get("live_policy_hash"),
        "preregistration_hash": preregistration.get("preregistration_hash"),
        "reflection_hash": reflection.get("reflection_hash"),
        "payload_sha256": hashlib.sha256(
            str(preregistration.get("candidate", {}).get("payload", "")).encode("utf-8")
        ).hexdigest(),
        "risk_signal_count": int(
            preregistration.get("risk_assessment", {}).get("signal_count", 0) or 0
        ),
        "risk_signals": preregistration.get("risk_assessment", {}).get(
            "matched_signals", []
        ),
        "decision": decision,
        "reflection_complete": True,
        "counterreflection_complete": bool(reflection.get("counterreflection")),
        "formal_status": formal_status,
        "block_reasons": block_reasons,
        "revised_payload_sha256": (
            hashlib.sha256(str(reflection.get("revised_payload", "")).encode("utf-8")).hexdigest()
            if decision == "revise"
            else None
        ),
    }
    attempt["attempt_hash"] = object_hash(attempt)

    registry: dict[str, Any] | None = None
    semantic_item: dict[str, Any] | None = None
    receipt_status = formal_status
    with locked_paths([registry_path, attempt_log, contract_path, output_path]):
        existing_attempt = next(
            (
                row
                for row in read_jsonl_unlocked(attempt_log)
                if row.get("attempt_id") == attempt_id
            ),
            None,
        )
        if existing_attempt is not None:
            if existing_attempt.get("attempt_hash") != attempt.get("attempt_hash"):
                # created_at is excluded from the semantic retry identity but is
                # retained from the first durable attempt.
                candidate_retry = dict(attempt)
                candidate_retry["created_at"] = existing_attempt.get("created_at")
                candidate_retry["attempt_hash"] = object_hash(
                    {k: v for k, v in candidate_retry.items() if k != "attempt_hash"}
                )
                if candidate_retry.get("attempt_hash") != existing_attempt.get("attempt_hash"):
                    raise PipelineError("attempt_id collision with different registration evidence")
                attempt = existing_attempt
            else:
                attempt = existing_attempt
        append_attempt = existing_attempt is None

        if formal_status == "registered":
            semantic_item = _semantic_item(preregistration, reflection, attempt_id)
            existing_items: list[dict[str, Any]] = []
            if registry_path.exists():
                existing_registry = load_json_unlocked(registry_path)
                if not _valid_hashed_record(existing_registry, "registry_hash"):
                    raise PipelineError("existing screen-text registry hash is invalid")
                if existing_registry.get("profile_hash") != profile.get("profile_hash"):
                    raise PipelineError("existing screen-text registry belongs to a different profile")
                existing_items = list(existing_registry.get("semantic_items", []))
            key = (
                str(semantic_item.get("constructor", "")),
                str(semantic_item.get("payload", "")),
            )
            matching = [
                item
                for item in existing_items
                if (
                    str(item.get("constructor", "")),
                    str(item.get("payload", "")),
                )
                == key
            ]
            if matching and matching[0] != semantic_item:
                raise PipelineError(
                    "constructor/payload is already registered with different reflection evidence"
                )
            if not matching:
                existing_items.append(semantic_item)
            registry = _registry_payload(
                profile=profile,
                registry_path=registry_path,
                attempt_log=attempt_log,
                items=existing_items,
                repo_root=repo_root,
            )
        if append_attempt:
            append_jsonl_unlocked(attempt_log, attempt)
        if registry is not None:
            atomic_write_json_unlocked(registry_path, registry)
            atomic_write_json_unlocked(
                contract_path,
                _screen_text_contract_patch(profile, registry, repo_root),
            )

        receipt: dict[str, Any] = {
            "schema": RECEIPT_SCHEMA,
            "contract_version": REGISTRATION_CONTRACT_VERSION,
            "created_at": attempt.get("created_at"),
            "attempt_id": attempt_id,
            "attempt_hash": attempt.get("attempt_hash"),
            "scene_slug": preregistration.get("scene_slug"),
            "profile_hash": profile.get("profile_hash"),
            "skill_tree_hash": profile.get("skill_tree_hash_at_profile_compile"),
            "preregistration_hash": preregistration.get("preregistration_hash"),
            "reflection_hash": reflection.get("reflection_hash"),
            "decision": decision,
            "formal_status": receipt_status,
            "block_reasons": block_reasons,
            "semantic_item": semantic_item,
            "registry_path": _relative_or_absolute(registry_path, repo_root),
            "registry_hash": registry.get("registry_hash") if registry else None,
            "attempt_log_path": _relative_or_absolute(attempt_log, repo_root),
            "screen_text_contract_path": _relative_or_absolute(
                contract_path, repo_root
            ),
            "screen_text_contract_patch": (
                _screen_text_contract_patch(profile, registry, repo_root)
                if registry
                else None
            ),
            "next_action": (
                "copy screen_text_contract_patch into the scene plan before source authoring"
                if formal_status == "registered"
                else (
                    "prepare a new preregistration for revised_payload"
                    if formal_status == "revision_required"
                    else (
                        "do not create this visible text"
                        if formal_status == "withdrawn"
                        else "revise or remove the candidate; self-declaration cannot override the formal boundary"
                    )
                )
            ),
        }
        receipt["receipt_hash"] = object_hash(receipt)
        atomic_write_json_unlocked(output_path, receipt)
    return receipt, 0 if formal_status in {"registered", "withdrawn", "revision_required"} else 2


def validate_screen_text_registration_binding(
    profile: dict[str, Any], plan: dict[str, Any], repo_root: Path
) -> list[str]:
    if int(profile.get("autopilot_contract_version") or 0) < 8:
        return []
    contract = plan.get("screen_text_contract", {})
    if not isinstance(contract, dict):
        return ["screen_text_contract is missing"]
    errors = validate_screen_text_contract_registration(
        contract, repo_root, str(profile.get("context", {}).get("scene_slug", ""))
    )
    try:
        canonical_registry, canonical_log = screen_text_registration_paths(
            profile, repo_root
        )
    except PipelineError as exc:
        errors.append(str(exc))
        return errors
    if _resolve(str(contract.get("registration_registry_path", "")), repo_root).resolve() != canonical_registry.resolve():
        errors.append("screen-text registry path does not match the compiled profile")
    if _resolve(str(contract.get("registration_attempt_log_path", "")), repo_root).resolve() != canonical_log.resolve():
        errors.append("screen-text attempt log path does not match the compiled profile")
    if contract.get("profile_hash") != profile.get("profile_hash"):
        errors.append("screen-text contract profile_hash does not match the compiled profile")
    return errors


def _semantic_identity(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [dict(item) for item in items if isinstance(item, dict)],
        key=lambda item: (
            str(item.get("constructor", "")),
            str(item.get("payload", "")),
        ),
    )


def validate_screen_text_contract_registration(
    contract: dict[str, Any], repo_root: Path, scene_slug: str
) -> list[str]:
    if int(contract.get("registration_contract_version") or 0) < 1:
        return []
    errors: list[str] = []
    raw_registry_path = str(contract.get("registration_registry_path", "")).strip()
    raw_attempt_log = str(contract.get("registration_attempt_log_path", "")).strip()
    if not raw_registry_path or not raw_attempt_log:
        return ["screen-text registration requires registry and attempt-log paths"]
    registry_path = _resolve(raw_registry_path, repo_root)
    attempt_log = _resolve(raw_attempt_log, repo_root)
    try:
        registry = load_json(registry_path)
    except PipelineError as exc:
        return [f"cannot load screen-text registry: {exc}"]
    if registry.get("schema") != REGISTRY_SCHEMA:
        errors.append("screen-text registry schema is invalid")
    if not _valid_hashed_record(registry, "registry_hash"):
        errors.append("screen-text registry hash is invalid")
    if registry.get("registry_hash") != contract.get("registration_registry_hash"):
        errors.append("screen-text registry hash does not match the scene contract")
    if str(registry.get("scene_slug", "")) != str(scene_slug):
        errors.append("screen-text registry belongs to a different scene")
    if _semantic_identity(registry.get("semantic_items", [])) != _semantic_identity(
        contract.get("semantic_items", [])
    ):
        errors.append("scene semantic_items do not exactly match the formal registry")
    try:
        attempts = read_jsonl(attempt_log)
    except PipelineError as exc:
        errors.append(f"cannot load screen-text attempt log: {exc}")
        attempts = []
    attempts_by_id = {
        str(row.get("attempt_id")): row
        for row in attempts
        if row.get("schema") == ATTEMPT_SCHEMA
    }
    for item in registry.get("semantic_items", []):
        attempt_id = str(item.get("registration_attempt_id", ""))
        row = attempts_by_id.get(attempt_id)
        if row is None:
            errors.append(
                f"registered payload {item.get('payload')!r} has no durable attempt row"
            )
            continue
        if not _valid_hashed_record(row, "attempt_hash"):
            errors.append(f"screen-text attempt {attempt_id!r} hash is invalid")
        if row.get("formal_status") != "registered":
            errors.append(f"screen-text attempt {attempt_id!r} is not registered")
        if row.get("preregistration_hash") != item.get("preregistration_hash"):
            errors.append(f"screen-text attempt {attempt_id!r} preregistration changed")
        if row.get("reflection_hash") != item.get("reflection_hash"):
            errors.append(f"screen-text attempt {attempt_id!r} reflection changed")
    return errors


def _human_screen_text_escape(issue: dict[str, Any]) -> bool:
    if str(issue.get("source", "")) != "human_review":
        return False
    pattern = str(issue.get("pattern_key", "")).lower()
    standard = str(issue.get("standard_key", "")).lower()
    if any(token in pattern for token in ("scope_misinterpreted", "deleted_requested_spoken")):
        return False
    direct_patterns = {
        "summary_scene_exposes_production_process_and_persona",
        "presentation_boundary_failure",
        "episode_recap_process_title",
        "creator_persona_outro",
        "creator_intent_text_substitutes_for_animation",
    }
    if pattern in direct_patterns or any(
        token in pattern for token in ("producer_intent", "creator_intent", "process_title")
    ):
        return True
    evidence_blob = json.dumps(issue.get("evidence", {}), ensure_ascii=False).lower()
    return "presentation_boundary" in standard and any(
        token in evidence_blob
        for token in ("externalizes", "production process", "制作意图", "制作者意图")
    )


def _human_screen_text_overblock(issue: dict[str, Any]) -> bool:
    """Identify user findings that the gate removed necessary visible text.

    Audio-only scope corrections are deliberately excluded: this experiment
    governs learner-facing visible literals, not whether a requested spoken
    sign-off remains in the narration.
    """

    if str(issue.get("source", "")) != "human_review":
        return False
    pattern = str(issue.get("pattern_key", "")).lower()
    standard = str(issue.get("standard_key", "")).lower()
    if any(token in pattern for token in ("spoken", "audio", "narration")):
        return False
    direct_patterns = {
        "screen_text_gate_removed_necessary_learner_text",
        "screen_text_overblocked",
        "missing_required_screen_text",
        "necessary_learner_text_removed",
    }
    return pattern in direct_patterns or (
        "presentation_boundary" in standard
        and any(token in pattern for token in ("overblock", "missing_required"))
    )


def _explicit_escape_payloads(issue: dict[str, Any]) -> list[str] | None:
    evidence = issue.get("evidence", {})
    candidates = [
        issue.get("affected_visible_payloads"),
        issue.get("escaped_visible_payloads"),
        evidence.get("affected_visible_payloads") if isinstance(evidence, dict) else None,
        evidence.get("escaped_visible_payloads") if isinstance(evidence, dict) else None,
    ]
    for raw in candidates:
        if not isinstance(raw, list):
            continue
        payloads = sorted({str(value).strip() for value in raw if str(value).strip()})
        if payloads:
            return payloads
    return None


def _planned_scene_slugs(episode: Path) -> list[str] | None:
    timeline_path = episode / "timeline.json"
    if not timeline_path.is_file():
        return None
    try:
        timeline = load_json(timeline_path)
    except (PipelineError, OSError, json.JSONDecodeError):
        return None
    values: set[str] = set()
    for group in timeline.get("scene_groups", []):
        if not isinstance(group, dict):
            continue
        slug = str(group.get("scene_slug", "")).strip()
        if slug:
            values.add(slug)
    return sorted(values) if values else None


def screen_text_registration_metrics(
    episode: Path, issues: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    path = episode / "review" / "evolution" / "screen_text_registration_attempts.jsonl"
    issue_list = [issue for issue in issues if isinstance(issue, dict)]
    human_escapes = [issue for issue in issue_list if _human_screen_text_escape(issue)]
    human_overblocks = [
        issue for issue in issue_list if _human_screen_text_overblock(issue)
    ]
    escape_payload_lists = [_explicit_escape_payloads(issue) for issue in human_escapes]
    explicit_escape_payload_issue_count = sum(
        payloads is not None for payloads in escape_payload_lists
    )
    escape_payload_attribution_coverage = (
        round(explicit_escape_payload_issue_count / len(human_escapes), 4)
        if human_escapes
        else 1.0
    )
    escape_payload_count = (
        sum(len(payloads or []) for payloads in escape_payload_lists)
        if explicit_escape_payload_issue_count == len(human_escapes)
        else None
    )
    escape_payload_count_lower_bound = sum(
        len(payloads) if payloads is not None else 1
        for payloads in escape_payload_lists
    )
    escape_scenes = sorted(
        {
            str(issue.get("scene_slug", "")).strip()
            for issue in human_escapes
            if str(issue.get("scene_slug", "")).strip()
        }
    )
    overblock_scenes = sorted(
        {
            str(issue.get("scene_slug", "")).strip()
            for issue in human_overblocks
            if str(issue.get("scene_slug", "")).strip()
        }
    )
    planned_scenes = _planned_scene_slugs(episode)
    if not path.exists():
        return {
            "instrumentation_status": "unknown_not_instrumented",
            "attempt_log_path": str(path),
            "planned_scene_count": len(planned_scenes) if planned_scenes is not None else None,
            "instrumented_scene_count": None,
            "scene_gate_coverage": None,
            "unobserved_planned_scenes": None,
            "zero_candidate_scene_count": None,
            "attempt_count": None,
            "profile_skill_tree_hashes": None,
            "terminal_attempt_count": None,
            "terminal_coverage": None,
            "risk_signalled_attempt_count": None,
            "keep_decision_count": None,
            "revise_decision_count": None,
            "remove_decision_count": None,
            "registered_count": None,
            "formal_block_count": None,
            "prevented_before_source_count": None,
            "pre_source_prevention_rate": None,
            "human_screen_text_escape_issue_count": len(human_escapes),
            "human_screen_text_escape_scene_count": len(escape_scenes),
            "human_screen_text_escape_scenes": escape_scenes,
            "human_screen_text_escape_payload_count": escape_payload_count,
            "human_screen_text_escape_payload_count_lower_bound": escape_payload_count_lower_bound,
            "human_screen_text_escape_payload_attribution_coverage": escape_payload_attribution_coverage,
            "human_screen_text_overblock_issue_count": len(human_overblocks),
            "human_screen_text_overblock_scene_count": len(overblock_scenes),
            "human_screen_text_overblock_scenes": overblock_scenes,
            "human_escape_per_100_registered": None,
            "invalid_attempt_row_count": None,
            "missing_means_zero": False,
        }
    try:
        raw_rows = read_jsonl(path)
    except PipelineError as exc:
        return {
            "instrumentation_status": "invalid_unreadable_ledger",
            "attempt_log_path": str(path),
            "planned_scene_count": len(planned_scenes) if planned_scenes is not None else None,
            "instrumented_scene_count": None,
            "scene_gate_coverage": None,
            "unobserved_planned_scenes": None,
            "zero_candidate_scene_count": None,
            "attempt_count": None,
            "profile_skill_tree_hashes": None,
            "terminal_attempt_count": None,
            "terminal_coverage": None,
            "risk_signalled_attempt_count": None,
            "keep_decision_count": None,
            "revise_decision_count": None,
            "remove_decision_count": None,
            "registered_count": None,
            "formal_block_count": None,
            "prevented_before_source_count": None,
            "pre_source_prevention_rate": None,
            "human_screen_text_escape_issue_count": len(human_escapes),
            "human_screen_text_escape_scene_count": len(escape_scenes),
            "human_screen_text_escape_scenes": escape_scenes,
            "human_screen_text_escape_payload_count": escape_payload_count,
            "human_screen_text_escape_payload_count_lower_bound": escape_payload_count_lower_bound,
            "human_screen_text_escape_payload_attribution_coverage": escape_payload_attribution_coverage,
            "human_screen_text_overblock_issue_count": len(human_overblocks),
            "human_screen_text_overblock_scene_count": len(overblock_scenes),
            "human_screen_text_overblock_scenes": overblock_scenes,
            "human_escape_per_100_registered": None,
            "invalid_attempt_row_count": None,
            "ledger_error": str(exc),
            "missing_means_zero": False,
        }
    observations = [
        row for row in raw_rows if row.get("schema") == OBSERVATION_SCHEMA
    ]
    valid_observations = [
        row
        for row in observations
        if _valid_hashed_record(row, "observation_hash")
        and row.get("status") == "gate_initialized"
    ]
    latest_observation_by_scene: dict[str, dict[str, Any]] = {}
    for row in valid_observations:
        scene_slug = str(row.get("scene_slug", "")).strip()
        if scene_slug:
            latest_observation_by_scene[scene_slug] = row
    invalid_observation_count = len(observations) - len(valid_observations)
    instrumented_scenes = sorted(latest_observation_by_scene)
    planned_set = set(planned_scenes or [])
    unobserved_planned = (
        sorted(planned_set - set(instrumented_scenes))
        if planned_scenes is not None
        else None
    )
    scene_gate_coverage = (
        round(len(planned_set & set(instrumented_scenes)) / len(planned_set), 4)
        if planned_set
        else None
    )
    rows = [row for row in raw_rows if row.get("schema") == ATTEMPT_SCHEMA]
    unique: dict[str, dict[str, Any]] = {
        str(row.get("attempt_id") or object_hash(row)): row for row in rows
    }
    valid_rows = [row for row in unique.values() if _valid_hashed_record(row, "attempt_hash")]
    invalid_count = len(unique) - len(valid_rows)
    status_counts = Counter(str(row.get("formal_status", "")) for row in valid_rows)
    decision_counts = Counter(str(row.get("decision", "")) for row in valid_rows)
    terminal = sum(
        status_counts[value]
        for value in ("registered", "blocked", "withdrawn", "revision_required")
    )
    prevented = (
        status_counts["blocked"]
        + status_counts["withdrawn"]
        + status_counts["revision_required"]
    )
    registered = status_counts["registered"]
    attempted_latest_scenes = {
        str(row.get("scene_slug", "")).strip()
        for row in valid_rows
        if str(row.get("scene_slug", "")).strip()
        and latest_observation_by_scene.get(str(row.get("scene_slug", "")).strip(), {}).get(
            "profile_hash"
        )
        == row.get("profile_hash")
    }
    return {
        "instrumentation_status": (
            "observed"
            if valid_observations and not invalid_count and not invalid_observation_count
            else (
                "observed_with_invalid_rows"
                if valid_observations
                else "observed_without_scene_observations"
            )
        ),
        "attempt_log_path": str(path),
        "planned_scene_count": len(planned_scenes) if planned_scenes is not None else None,
        "instrumented_scene_count": len(instrumented_scenes),
        "instrumented_scenes": instrumented_scenes,
        "scene_gate_coverage": scene_gate_coverage,
        "unobserved_planned_scenes": unobserved_planned,
        "zero_candidate_scene_count": len(
            set(instrumented_scenes) - attempted_latest_scenes
        ),
        "scene_observation_row_count": len(valid_observations),
        "invalid_scene_observation_row_count": invalid_observation_count,
        "attempt_count": len(valid_rows),
        "profile_skill_tree_hashes": sorted(
            {
                str(row.get("skill_tree_hash"))
                for row in valid_rows
                if row.get("skill_tree_hash")
            }
        ),
        "terminal_attempt_count": terminal,
        "terminal_coverage": round(terminal / len(valid_rows), 4) if valid_rows else 1.0,
        "risk_signalled_attempt_count": sum(
            int(row.get("risk_signal_count", 0) or 0) > 0 for row in valid_rows
        ),
        "keep_decision_count": decision_counts["keep"],
        "revise_decision_count": decision_counts["revise"],
        "remove_decision_count": decision_counts["remove"],
        "registered_count": registered,
        "formal_block_count": status_counts["blocked"],
        "prevented_before_source_count": prevented,
        "pre_source_prevention_rate": round(prevented / len(valid_rows), 4)
        if valid_rows
        else 0.0,
        "human_screen_text_escape_issue_count": len(human_escapes),
        "human_screen_text_escape_scene_count": len(escape_scenes),
        "human_screen_text_escape_scenes": escape_scenes,
        "human_screen_text_escape_payload_count": escape_payload_count,
        "human_screen_text_escape_payload_count_lower_bound": escape_payload_count_lower_bound,
        "human_screen_text_escape_payload_attribution_coverage": escape_payload_attribution_coverage,
        "human_screen_text_overblock_issue_count": len(human_overblocks),
        "human_screen_text_overblock_scene_count": len(overblock_scenes),
        "human_screen_text_overblock_scenes": overblock_scenes,
        "human_escape_per_100_registered": round(
            100.0 * len(human_escapes) / registered, 3
        )
        if registered
        else (0.0 if not human_escapes else None),
        "invalid_attempt_row_count": invalid_count,
        "missing_means_zero": False,
    }


def screen_text_experiment_report(
    episode: Path, issues: Iterable[dict[str, Any]], repo_root: Path
) -> dict[str, Any]:
    experiment_path = (
        Path(__file__).resolve().parents[2]
        / "references"
        / "experiments"
        / "screen-text-preregistration-v1.json"
    )
    if not experiment_path.is_file():
        return {
            "experiment_id": "screen-text-decision-gate-v1",
            "status": "experiment_definition_missing",
            "current": screen_text_registration_metrics(episode, issues),
        }
    experiment = load_json(experiment_path)
    current = screen_text_registration_metrics(episode, issues)
    baseline = experiment.get("baseline", {})
    baseline_evidence_checks: list[dict[str, Any]] = []
    for item in baseline.get("evidence", []):
        if not isinstance(item, dict):
            continue
        evidence_path = _resolve(str(item.get("path", "")), repo_root)
        observed_sha = (
            hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            if evidence_path.is_file()
            else None
        )
        baseline_evidence_checks.append(
            {
                "path": item.get("path"),
                "expected_sha256": item.get("sha256"),
                "observed_sha256": observed_sha,
                "valid": observed_sha == item.get("sha256"),
            }
        )
    baseline_evidence_valid = bool(baseline_evidence_checks) and all(
        item["valid"] for item in baseline_evidence_checks
    )
    baseline_episode = str(baseline.get("episode", ""))
    current_episode = _relative_or_absolute(episode, repo_root)
    if not baseline_evidence_valid:
        status = "baseline_evidence_stale"
    elif current["instrumentation_status"] == "unknown_not_instrumented":
        status = (
            "baseline_only_not_instrumented"
            if current_episode == baseline_episode
            else "not_comparable_missing_current_instrumentation"
        )
    else:
        thresholds = experiment.get("success_thresholds", {})
        scene_coverage = current.get("scene_gate_coverage")
        meets = (
            current.get("terminal_coverage") == thresholds.get("terminal_coverage")
            and scene_coverage == thresholds.get("scene_gate_coverage")
            and current.get("human_screen_text_escape_issue_count")
            <= int(thresholds.get("max_human_escape_issue_count", 0))
            and current.get("human_screen_text_overblock_issue_count")
            <= int(thresholds.get("max_human_overblock_issue_count", 0))
            and int(current.get("invalid_attempt_row_count", 0) or 0) == 0
            and int(current.get("invalid_scene_observation_row_count", 0) or 0)
            == 0
        )
        status = "target_met" if meets else "target_not_met"
    baseline_escape_issues = baseline.get("human_screen_text_escape_issue_count")
    current_escape_issues = current.get("human_screen_text_escape_issue_count")
    comparison_observed = current.get("instrumentation_status") == "observed"
    escape_issue_delta = (
        int(current_escape_issues) - int(baseline_escape_issues)
        if comparison_observed
        and current_escape_issues is not None
        and baseline_escape_issues is not None
        else None
    )
    baseline_escape_payloads = baseline.get("human_screen_text_escape_payload_count")
    current_escape_payloads = current.get("human_screen_text_escape_payload_count")
    escape_payload_delta = (
        int(current_escape_payloads) - int(baseline_escape_payloads)
        if comparison_observed
        and current_escape_payloads is not None
        and baseline_escape_payloads is not None
        else None
    )
    return {
        "experiment_id": experiment.get("experiment_id"),
        "definition_path": _relative_or_absolute(experiment_path, repo_root),
        "definition_hash": object_hash(experiment),
        "active_from_autopilot_contract_version": experiment.get(
            "active_from_autopilot_contract_version"
        ),
        "status": status,
        "baseline": baseline,
        "baseline_evidence_valid": baseline_evidence_valid,
        "baseline_evidence_checks": baseline_evidence_checks,
        "current": current,
        "comparison": {
            "status": (
                "observed"
                if comparison_observed
                else "unknown_missing_current_instrumentation"
            ),
            "human_screen_text_escape_issue_delta": escape_issue_delta,
            "human_screen_text_escape_payload_delta": escape_payload_delta,
            "human_screen_text_escape_payload_attribution_coverage": (
                current.get("human_screen_text_escape_payload_attribution_coverage")
                if comparison_observed
                else None
            ),
            "human_screen_text_overblock_issue_count": (
                current.get("human_screen_text_overblock_issue_count")
                if comparison_observed
                else None
            ),
            "pre_source_prevention_count": (
                current.get("prevented_before_source_count")
                if comparison_observed
                else None
            ),
            "decision_gate_terminal_coverage": (
                current.get("terminal_coverage")
                if comparison_observed
                else None
            ),
            "scene_gate_coverage": (
                current.get("scene_gate_coverage")
                if comparison_observed
                else None
            ),
            "causal_interpretation": (
                "A lower post-gate human escape count plus observed pre-source prevention "
                "supports effectiveness; tooling on the baseline episode alone proves only instrumentation."
            ),
        },
        "success_thresholds": experiment.get("success_thresholds", {}),
        "missing_data_policy": "unknown_is_never_reported_as_zero",
    }


def command_prepare_screen_text_registration(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    profile = load_json(Path(args.profile))
    preregistration = build_screen_text_preregistration(
        profile, _candidate_from_args(args), repo_root
    )
    output = Path(args.output)
    draft_output = (
        Path(args.reflection_template_output)
        if args.reflection_template_output
        else output.with_name(output.stem + ".reflection_draft.json")
    )
    write_json(output, preregistration)
    write_json(draft_output, reflection_draft_data(preregistration))
    print(
        json.dumps(
            {
                "output": str(output),
                "preregistration_hash": preregistration["preregistration_hash"],
                "risk_assessment": preregistration["risk_assessment"],
                "reflection_template": str(draft_output),
                "next_command": "seal-screen-text-reflection",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_seal_screen_text_reflection(args: argparse.Namespace) -> int:
    preregistration = load_json(Path(args.preregistration))
    draft = load_json(Path(args.input))
    reflection = seal_screen_text_reflection(preregistration, draft)
    write_json(Path(args.output), reflection)
    print(
        json.dumps(
            {
                "output": args.output,
                "reflection_hash": reflection["reflection_hash"],
                "state": reflection["reflected_state"],
                "next_command": "commit-screen-text-registration",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_commit_screen_text_registration(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    profile = load_json(Path(args.profile))
    preregistration = load_json(Path(args.preregistration))
    reflection = load_json(Path(args.reflection))
    receipt, exit_code = commit_screen_text_registration(
        repo_root=repo_root,
        profile=profile,
        preregistration=preregistration,
        reflection=reflection,
        output_path=Path(args.output),
        registry_override=Path(args.registry).resolve() if args.registry else None,
        attempt_log_override=Path(args.attempt_log).resolve() if args.attempt_log else None,
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return exit_code


def add_screen_text_registration_subparsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    prepare = subparsers.add_parser(
        "prepare-screen-text-registration",
        help=(
            "pre-register one proposed visible string and disclose a neutral "
            "keep-versus-remove reflection prompt"
        ),
    )
    prepare.add_argument("--repo-root", default=".")
    prepare.add_argument("--profile", required=True)
    prepare.add_argument("--constructor", required=True)
    prepare.add_argument("--payload", required=True)
    prepare.add_argument("--count", type=int, default=1)
    prepare.add_argument("--role", choices=sorted(SCREEN_TEXT_ROLES), required=True)
    prepare.add_argument("--reflection-template-output")
    prepare.add_argument("--output", required=True)
    prepare.set_defaults(func=command_prepare_screen_text_registration)

    seal = subparsers.add_parser(
        "seal-screen-text-reflection",
        help="seal a two-sided keep/remove reflection without deciding the formal boundary",
    )
    seal.add_argument("--preregistration", required=True)
    seal.add_argument("--input", required=True)
    seal.add_argument("--output", required=True)
    seal.set_defaults(func=command_seal_screen_text_reflection)

    commit = subparsers.add_parser(
        "commit-screen-text-registration",
        help=(
            "formally register, revise, remove, or block a reflected visible string "
            "and append durable experiment telemetry"
        ),
    )
    commit.add_argument("--repo-root", default=".")
    commit.add_argument("--profile", required=True)
    commit.add_argument("--preregistration", required=True)
    commit.add_argument("--reflection", required=True)
    commit.add_argument("--registry")
    commit.add_argument("--attempt-log")
    commit.add_argument("--output", required=True)
    commit.set_defaults(func=command_commit_screen_text_registration)
