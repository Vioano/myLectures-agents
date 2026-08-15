"""Profile-bound narration authoring and independent-review state machine.

The narration workflow deliberately lives outside ``engine.py``.  The engine
only installs these subcommands; all permissions, evidence validation, hot
profile rebinding, and state transitions remain testable in this module.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

from .core import PipelineError, object_hash, utc_now
from .storage import (
    append_jsonl_unlocked,
    atomic_write_json_unlocked,
    load_json,
    load_json_unlocked,
    locked_paths,
    read_jsonl_unlocked,
)


SCHEMA = "lecture-animation-narration-workflow-v2"
LEGACY_SCHEMAS = {"lecture-animation-narration-workflow-v1"}
AUTHOR_STATES = {"outline_reviewed", "revision_required"}
REVIEW_VERDICTS = {
    "revise": "revision_required",
    "pass": "user_review_pending",
    "pass_for_user_script_review_only": "user_review_pending",
    "pass_for_user_review_pending": "user_review_pending",
}
TERMINAL_STATES = {"tts_input_locked", "animation_authorized"}
ANIMATION_RELEASE_SCHEMA = "lecture-animation-narration-animation-release-v1"
POST_ANIMATION_REPAIR_SCHEMA = "lecture-animation-post-animation-narration-repair-v1"
USER_AUTHORITY_SCHEMA = "lecture-animation-narration-user-authority-v1"
POST_ANIMATION_REPAIR_KINDS = {"performance_only", "script_change"}
POST_ANIMATION_INVALIDATIONS = {
    "tts_audio",
    "asr",
    "word_alignment",
    "subtitles",
    "timeline",
    "scene_production",
    "visual_plan_binding",
    "scene_registry",
    "runtime_telemetry",
    "authoring_qc",
    "review_manifest",
    "author_self_review",
    "independent_review",
    "episode_assembly",
    "final_master_audit",
}


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise PipelineError(f"cannot read narration workflow artifact {path}: {exc}") from exc


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _snapshot(root: Path, value: str | Path, *, require_json: bool = False) -> dict[str, Any]:
    path = _resolve(root, value)
    if not path.is_file():
        raise PipelineError(f"narration workflow artifact does not exist: {path}")
    snapshot: dict[str, Any] = {
        "path": _relative(path, root),
        "sha256": _sha256(path),
        "size": path.stat().st_size,
    }
    if require_json:
        data = load_json(path)
        if not isinstance(data, dict):
            raise PipelineError(f"narration workflow JSON must be an object: {path}")
        snapshot["data"] = data
    return snapshot


def _artifact_data(snapshot: dict[str, Any]) -> dict[str, Any]:
    data = snapshot.get("data")
    if not isinstance(data, dict):
        raise PipelineError("internal narration workflow artifact is missing parsed JSON")
    return data


def validate_audience_profile(data: dict[str, Any]) -> None:
    if data.get("schema") != "lecture-animation-audience-profile-v1":
        raise PipelineError("audience profile schema must be lecture-animation-audience-profile-v1")
    if not str(data.get("profile_id", "")).strip():
        raise PipelineError("audience profile requires profile_id")
    scope = data.get("scope")
    if not isinstance(scope, dict) or scope.get("binding_mode") != "explicit_only":
        raise PipelineError("audience profile must use explicit_only binding")
    if scope.get("global_default") is not False:
        raise PipelineError("audience profile cannot silently become a global default")
    learner = data.get("learner_snapshot")
    if not isinstance(learner, dict) or not learner.get("working_memory"):
        raise PipelineError("audience profile requires an explicit learner working-memory model")
    if not isinstance(data.get("narration_policy"), dict):
        raise PipelineError("audience profile requires narration_policy")
    questions = data.get("review_questions")
    if not isinstance(questions, list) or not questions:
        raise PipelineError("audience profile requires review_questions")


def _validate_actors(author: str, reviewer: str, coordinator: str) -> None:
    values = {"author": author.strip(), "reviewer": reviewer.strip(), "coordinator": coordinator.strip()}
    if any(not value for value in values.values()):
        raise PipelineError("narration workflow author, reviewer, and coordinator ids are required")
    if values["author"] == values["reviewer"]:
        raise PipelineError("narration author and independent reviewer must be different actors")


def _rehash(state: dict[str, Any]) -> dict[str, Any]:
    payload = dict(state)
    payload.pop("state_hash", None)
    payload["state_hash"] = object_hash(payload)
    return payload


def _event(
    state: dict[str, Any],
    *,
    event_type: str,
    actor_id: str,
    from_state: str | None,
    to_state: str,
    evidence: dict[str, Any] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "sequence": len(state.get("history", [])) + 1,
        "event_type": event_type,
        "actor_id": actor_id,
        "from_state": from_state,
        "to_state": to_state,
        "recorded_at": utc_now(),
        "evidence": evidence or {},
    }
    if note:
        row["note"] = note
    row["event_hash"] = object_hash(row)
    state.setdefault("history", []).append(row)
    state["status"] = to_state
    state["revision"] = int(state.get("revision", 0)) + 1
    state["updated_at"] = row["recorded_at"]
    return row


def _load_current(state_path: Path, expected_hash: str) -> dict[str, Any]:
    state = load_json_unlocked(state_path)
    if not isinstance(state, dict) or state.get("schema") not in {SCHEMA, *LEGACY_SCHEMAS}:
        raise PipelineError("invalid narration workflow state")
    if state.get("state_hash") != expected_hash:
        raise PipelineError("narration workflow changed; reload state and retry with the current state_hash")
    return state


def _verify_descriptor(root: Path, value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PipelineError(f"{label} must be an artifact descriptor")
    raw_path = str(value.get("path", "")).strip()
    expected_sha = str(value.get("sha256", "")).strip()
    if not raw_path or not expected_sha:
        raise PipelineError(f"{label} requires path and sha256")
    path = _resolve(root, raw_path)
    if not path.is_file():
        raise PipelineError(f"{label} does not exist: {path}")
    if _sha256(path) != expected_sha:
        raise PipelineError(f"{label} sha256 does not match current bytes")
    return {
        "path": _relative(path, root),
        "sha256": expected_sha,
        "size": path.stat().st_size,
    }


def validate_narration_workflow_for_phase(
    path: Path,
    *,
    repo_root: Path,
    phase: str,
) -> dict[str, Any]:
    state = load_json(path)
    if not isinstance(state, dict) or state.get("schema") not in {SCHEMA, *LEGACY_SCHEMAS}:
        raise PipelineError("invalid narration workflow state")
    if state.get("state_hash") != _rehash(state).get("state_hash"):
        raise PipelineError("narration workflow state_hash mismatch")
    for label in ("profile", "writing_contract", "outline"):
        errors = _verify_snapshot(repo_root, state.get(label, {}), label)
        if errors:
            raise PipelineError("narration workflow is stale: " + " | ".join(errors))
    expected_state = (
        "tts_input_locked" if phase in {"tts", "asr"} else "animation_authorized"
    )
    if state.get("status") != expected_state:
        raise PipelineError(
            f"narration workflow must be {expected_state} before {phase}; "
            f"actual state is {state.get('status')}"
        )
    candidate = state.get("current_candidate") or {}
    if expected_state == "tts_input_locked":
        tts_lock = state.get("tts_lock")
        if not isinstance(tts_lock, dict):
            raise PipelineError("tts_input_locked narration lacks a TTS lock")
        if tts_lock.get("candidate_hash") != candidate.get("candidate_hash"):
            raise PipelineError("narration TTS lock belongs to another candidate")
        errors = _verify_snapshot(repo_root, tts_lock.get("preflight", {}), "tts_lock.preflight")
        if errors:
            raise PipelineError("narration TTS lock is stale: " + " | ".join(errors))
    if expected_state == "animation_authorized":
        release = state.get("animation_release")
        if not isinstance(release, dict) or not release.get("sha256"):
            raise PipelineError("animation-authorized narration lacks a sealed release")
        errors = _verify_snapshot(repo_root, release, "animation_release")
        if errors:
            raise PipelineError("narration animation release is stale: " + " | ".join(errors))
        release_data = load_json(_resolve(repo_root, release.get("path", "")))
        if release_data.get("schema") != ANIMATION_RELEASE_SCHEMA:
            raise PipelineError("narration animation release schema is invalid")
        if release_data.get("workflow_id") != state.get("workflow_id"):
            raise PipelineError("narration animation release belongs to another workflow")
        if release_data.get("candidate_hash") != candidate.get("candidate_hash"):
            raise PipelineError("narration animation release belongs to another candidate")
        _verify_descriptor(
            repo_root,
            release_data.get("post_tts_readiness"),
            "animation_release.post_tts_readiness",
        )
        _verify_descriptor(
            repo_root,
            release_data.get("scene_production_inventory"),
            "animation_release.scene_production_inventory",
        )
        repair = state.get("post_animation_repair")
        if isinstance(repair, dict) and release_data.get("repair_context_hash") != repair.get(
            "repair_context_hash"
        ):
            raise PipelineError("narration animation release repair context is stale")
    return state


def _assert_actor(state: dict[str, Any], role: str, actor_id: str) -> None:
    expected = state.get("actors", {}).get(role)
    if expected != actor_id:
        raise PipelineError(f"only the bound narration {role} may perform this transition")


def _verify_snapshot(root: Path, snapshot: dict[str, Any], label: str) -> list[str]:
    path = _resolve(root, snapshot.get("path", ""))
    errors: list[str] = []
    if not path.is_file():
        return [f"{label} is missing: {path}"]
    actual_size = path.stat().st_size
    actual_sha = _sha256(path)
    if actual_size != snapshot.get("size"):
        errors.append(f"{label} size changed")
    if actual_sha != snapshot.get("sha256"):
        errors.append(f"{label} sha256 changed")
    return errors


def _validate_structured_script(script_md: dict[str, Any], script_json: dict[str, Any]) -> None:
    data = _artifact_data(script_json)
    source = data.get("source_script")
    if not isinstance(source, dict) or source.get("sha256") != script_md.get("sha256"):
        raise PipelineError("structured narration script is not bound to the exact Markdown script")


def _validate_static_audit(audit: dict[str, Any], script_json: dict[str, Any]) -> None:
    data = _artifact_data(audit)
    if data.get("valid") is not True or int(data.get("issue_count", 0) or 0) != 0:
        raise PipelineError("narration static audit must be valid with zero issues")
    if data.get("rewrite_sha256") != script_json.get("sha256"):
        raise PipelineError("narration static audit is not bound to the exact structured script")


def _candidate(
    *,
    state: dict[str, Any],
    script_md: dict[str, Any],
    script_json: dict[str, Any],
    static_audit: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    payload = {
        "label": label,
        "script_markdown": {key: script_md[key] for key in ("path", "sha256", "size")},
        "script_json": {key: script_json[key] for key in ("path", "sha256", "size")},
        "static_audit": {key: static_audit[key] for key in ("path", "sha256", "size")},
        "profile_sha256": state["profile"]["sha256"],
        "writing_contract_sha256": state["writing_contract"]["sha256"],
        "outline_sha256": state["outline"]["sha256"],
        "frozen_at": utc_now(),
    }
    payload["candidate_hash"] = object_hash(payload)
    return payload


def _normalize_verdict(value: Any) -> tuple[str, str]:
    normalized = str(value or "").strip().lower()
    state = REVIEW_VERDICTS.get(normalized)
    if state is None:
        raise PipelineError(f"unsupported narration independent-review verdict: {value!r}")
    return normalized, state


def _report_binds_candidate(
    report: dict[str, Any],
    state: dict[str, Any],
    candidate: dict[str, Any],
    *,
    allow_legacy_import: bool,
) -> None:
    binding = report.get("workflow_binding")
    if isinstance(binding, dict):
        required = {
            "workflow_id": state["workflow_id"],
            "candidate_hash": candidate["candidate_hash"],
            "profile_sha256": state["profile"]["sha256"],
            "writing_contract_sha256": state["writing_contract"]["sha256"],
        }
        for key, expected in required.items():
            if binding.get(key) != expected:
                raise PipelineError(f"independent review workflow_binding {key} does not match current candidate")
        return
    if not allow_legacy_import:
        raise PipelineError("independent review lacks current workflow_binding")
    inputs = report.get("inputs")
    if not isinstance(inputs, dict):
        raise PipelineError("legacy independent review lacks inputs")
    checks = {
        "rewrite_markdown": candidate["script_markdown"]["sha256"],
        "rewrite_json": candidate["script_json"]["sha256"],
        "repair_contract": state["writing_contract"]["sha256"],
        "static_audit": candidate["static_audit"]["sha256"],
    }
    for key, expected in checks.items():
        value = inputs.get(key)
        if not isinstance(value, dict) or value.get("sha256") != expected:
            raise PipelineError(f"legacy independent review input {key} does not match imported candidate")


def _append_attempt(
    attempt_log: Path,
    *,
    state: dict[str, Any],
    report_snapshot: dict[str, Any],
    candidate: dict[str, Any],
    verdict: str,
    resulting_state: str,
    reviewer_id: str,
    imported: bool,
) -> dict[str, Any]:
    row = {
        "schema": "lecture-animation-narration-review-attempt-v1",
        "workflow_id": state["workflow_id"],
        "candidate_hash": candidate["candidate_hash"],
        "profile_sha256": state["profile"]["sha256"],
        "reviewer_id": reviewer_id,
        "report": {key: report_snapshot[key] for key in ("path", "sha256", "size")},
        "verdict": verdict,
        "resulting_state": resulting_state,
        "imported_legacy_evidence": imported,
        "recorded_at": utc_now(),
    }
    row["attempt_id"] = f"narration-review:{object_hash(row)[:16]}"
    existing = next(
        (item for item in read_jsonl_unlocked(attempt_log) if item.get("attempt_id") == row["attempt_id"]),
        None,
    )
    if existing is not None:
        return existing
    append_jsonl_unlocked(attempt_log, row)
    return row


def command_init_narration_workflow(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    state_path = _resolve(root, args.state)
    profile = _snapshot(root, args.profile, require_json=True)
    validate_audience_profile(_artifact_data(profile))
    contract = _snapshot(root, args.writing_contract, require_json=True)
    outline = _snapshot(root, args.outline)
    _validate_actors(args.author_id, args.reviewer_id, args.coordinator_id)
    with locked_paths([state_path]):
        if state_path.exists() and not args.replace:
            raise PipelineError("narration workflow state already exists; use --replace with --reason")
        if state_path.exists() and args.replace and not args.reason:
            raise PipelineError("replacing narration workflow state requires --reason")
        now = utc_now()
        state: dict[str, Any] = {
            "schema": SCHEMA,
            "workflow_id": args.workflow_id,
            "episode": args.episode,
            "status": "queued",
            "revision": 0,
            "actors": {
                "author": args.author_id,
                "reviewer": args.reviewer_id,
                "coordinator": args.coordinator_id,
            },
            "profile": {key: profile[key] for key in ("path", "sha256", "size")},
            "profile_id": _artifact_data(profile)["profile_id"],
            "writing_contract": {key: contract[key] for key in ("path", "sha256", "size")},
            "outline": {key: outline[key] for key in ("path", "sha256", "size")},
            "created_at": now,
            "updated_at": now,
            "history": [],
            "current_candidate": None,
            "author_self_review": None,
            "independent_review": None,
            "user_outcome": None,
            "tts_lock": None,
            "animation_release": None,
            "post_animation_repair": None,
        }
        _event(
            state,
            event_type="profile_outline_bound",
            actor_id=args.coordinator_id,
            from_state=None,
            to_state="profile_outline_locked",
            evidence={
                "profile_sha256": profile["sha256"],
                "writing_contract_sha256": contract["sha256"],
                "outline_sha256": outline["sha256"],
            },
            note=args.reason if args.replace else None,
        )
        state = _rehash(state)
        atomic_write_json_unlocked(state_path, state)
    print_json(state)
    return 0


def command_record_narration_outline_review(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    state_path = _resolve(root, args.state)
    review = _snapshot(root, args.review, require_json=True)
    data = _artifact_data(review)
    with locked_paths([state_path]):
        state = _load_current(state_path, args.expected_state_hash)
        _assert_actor(state, "reviewer", args.actor_id)
        if state["status"] != "profile_outline_locked":
            raise PipelineError("outline review requires profile_outline_locked state")
        if str(data.get("verdict", "")).strip().lower() not in {"pass", "approved"}:
            raise PipelineError("outline review must have a pass verdict")
        binding = data.get("workflow_binding", {})
        if binding.get("profile_sha256") != state["profile"]["sha256"] or binding.get("outline_sha256") != state["outline"]["sha256"]:
            raise PipelineError("outline review is not bound to current profile and outline")
        state["outline_review"] = {key: review[key] for key in ("path", "sha256", "size")}
        _event(
            state,
            event_type="outline_review_passed",
            actor_id=args.actor_id,
            from_state="profile_outline_locked",
            to_state="outline_reviewed",
            evidence={"review_sha256": review["sha256"]},
        )
        state = _rehash(state)
        atomic_write_json_unlocked(state_path, state)
    print_json(state)
    return 0


def command_open_narration_drafting(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    state_path = _resolve(root, args.state)
    with locked_paths([state_path]):
        state = _load_current(state_path, args.expected_state_hash)
        _assert_actor(state, "author", args.actor_id)
        if state["status"] not in AUTHOR_STATES:
            raise PipelineError("drafting may open only after outline review or an independent revision request")
        previous = state["status"]
        _event(
            state,
            event_type="drafting_opened",
            actor_id=args.actor_id,
            from_state=previous,
            to_state="drafting",
            evidence={"based_on_review_sha256": (state.get("independent_review") or {}).get("sha256")},
            note=args.reason,
        )
        state = _rehash(state)
        atomic_write_json_unlocked(state_path, state)
    print_json(state)
    return 0


def _freeze_candidate_from_args(root: Path, state: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    missing = [
        name
        for name in ("script_markdown", "script_json", "static_audit", "candidate_label")
        if not getattr(args, name, None)
    ]
    if missing:
        raise PipelineError(
            "importing an existing narration candidate requires " + ", ".join(missing)
        )
    script_md = _snapshot(root, args.script_markdown)
    script_json = _snapshot(root, args.script_json, require_json=True)
    static_audit = _snapshot(root, args.static_audit, require_json=True)
    _validate_structured_script(script_md, script_json)
    _validate_static_audit(static_audit, script_json)
    return _candidate(
        state=state,
        script_md=script_md,
        script_json=script_json,
        static_audit=static_audit,
        label=args.candidate_label,
    )


def command_freeze_narration_script(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    state_path = _resolve(root, args.state)
    with locked_paths([state_path]):
        state = _load_current(state_path, args.expected_state_hash)
        _assert_actor(state, "author", args.actor_id)
        if state["status"] != "drafting":
            raise PipelineError("freezing a narration script requires drafting state")
        candidate = _freeze_candidate_from_args(root, state, args)
        state["current_candidate"] = candidate
        state["author_self_review"] = None
        state["independent_review"] = None
        state["user_outcome"] = None
        state["tts_lock"] = None
        state["animation_release"] = None
        _event(
            state,
            event_type="script_candidate_frozen",
            actor_id=args.actor_id,
            from_state="drafting",
            to_state="script_candidate_frozen",
            evidence={"candidate_hash": candidate["candidate_hash"]},
        )
        state = _rehash(state)
        atomic_write_json_unlocked(state_path, state)
    print_json(state)
    return 0


def command_seal_narration_author_self_review(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    state_path = _resolve(root, args.state)
    review = _snapshot(root, args.review, require_json=True)
    data = _artifact_data(review)
    with locked_paths([state_path]):
        state = _load_current(state_path, args.expected_state_hash)
        _assert_actor(state, "author", args.actor_id)
        if state["status"] != "script_candidate_frozen":
            raise PipelineError("author self-review requires script_candidate_frozen state")
        candidate = state.get("current_candidate") or {}
        if data.get("schema") != "lecture-animation-narration-author-self-review-v1":
            raise PipelineError("invalid narration author self-review schema")
        if data.get("author_id") != args.actor_id or data.get("candidate_hash") != candidate.get("candidate_hash"):
            raise PipelineError("author self-review is not bound to author and exact candidate")
        if str(data.get("verdict", "")).lower() != "pass" or not data.get("checks"):
            raise PipelineError("author self-review must pass and contain concrete checks")
        state["author_self_review"] = {key: review[key] for key in ("path", "sha256", "size")}
        _event(
            state,
            event_type="author_self_review_passed",
            actor_id=args.actor_id,
            from_state="script_candidate_frozen",
            to_state="author_self_review_passed",
            evidence={"review_sha256": review["sha256"], "candidate_hash": candidate["candidate_hash"]},
        )
        state = _rehash(state)
        atomic_write_json_unlocked(state_path, state)
    print_json(state)
    return 0


def command_record_narration_independent_review(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    state_path = _resolve(root, args.state)
    attempt_log = _resolve(root, args.attempt_log)
    report = _snapshot(root, args.report, require_json=True)
    report_data = _artifact_data(report)
    with locked_paths([state_path, attempt_log]):
        state = _load_current(state_path, args.expected_state_hash)
        _assert_actor(state, "reviewer", args.actor_id)
        imported = bool(args.import_existing_candidate)
        if imported:
            if state["status"] != "profile_outline_locked":
                raise PipelineError("legacy candidate import requires profile_outline_locked state")
            candidate = _freeze_candidate_from_args(root, state, args)
            state["current_candidate"] = candidate
            state["author_self_review"] = {
                "migration": "pre_state_machine_candidate",
                "note": "Imported only to preserve an already completed independent review; future candidates require author self-review.",
            }
        else:
            if state["status"] != "author_self_review_passed":
                raise PipelineError("independent review requires author_self_review_passed state")
            candidate = state.get("current_candidate") or {}
        verdict, resulting_state = _normalize_verdict(report_data.get("verdict"))
        _report_binds_candidate(report_data, state, candidate, allow_legacy_import=imported)
        attempt = _append_attempt(
            attempt_log,
            state=state,
            report_snapshot=report,
            candidate=candidate,
            verdict=verdict,
            resulting_state=resulting_state,
            reviewer_id=args.actor_id,
            imported=imported,
        )
        previous = state["status"]
        state["independent_review"] = {key: report[key] for key in ("path", "sha256", "size")}
        state["last_review_attempt_id"] = attempt["attempt_id"]
        _event(
            state,
            event_type="independent_review_recorded",
            actor_id=args.actor_id,
            from_state=previous,
            to_state=resulting_state,
            evidence={
                "review_sha256": report["sha256"],
                "candidate_hash": candidate["candidate_hash"],
                "attempt_id": attempt["attempt_id"],
                "verdict": verdict,
            },
            note="legacy evidence imported into the new state machine" if imported else None,
        )
        state = _rehash(state)
        atomic_write_json_unlocked(state_path, state)
    print_json(state)
    return 0


def command_rebind_narration_profile(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    state_path = _resolve(root, args.state)
    profile = _snapshot(root, args.profile, require_json=True)
    validate_audience_profile(_artifact_data(profile))
    contract = _snapshot(root, args.writing_contract, require_json=True)
    outline = _snapshot(root, args.outline)
    with locked_paths([state_path]):
        state = _load_current(state_path, args.expected_state_hash)
        _assert_actor(state, "coordinator", args.actor_id)
        if state["status"] in TERMINAL_STATES:
            raise PipelineError("a TTS-locked narration cannot be hot-rebound; start a new workflow revision")
        previous = state["status"]
        invalidated = {
            "profile": state.get("profile"),
            "writing_contract": state.get("writing_contract"),
            "outline": state.get("outline"),
            "current_candidate": state.get("current_candidate"),
            "author_self_review": state.get("author_self_review"),
            "independent_review": state.get("independent_review"),
            "user_outcome": state.get("user_outcome"),
        }
        state.setdefault("superseded_bindings", []).append({
            "recorded_at": utc_now(),
            "reason": args.reason,
            "artifacts": invalidated,
        })
        state["profile"] = {key: profile[key] for key in ("path", "sha256", "size")}
        state["profile_id"] = _artifact_data(profile)["profile_id"]
        state["writing_contract"] = {key: contract[key] for key in ("path", "sha256", "size")}
        state["outline"] = {key: outline[key] for key in ("path", "sha256", "size")}
        state["outline_review"] = None
        state["current_candidate"] = None
        state["author_self_review"] = None
        state["independent_review"] = None
        state["user_outcome"] = None
        state["tts_lock"] = None
        state["animation_release"] = None
        _event(
            state,
            event_type="profile_hot_rebound",
            actor_id=args.actor_id,
            from_state=previous,
            to_state="profile_outline_locked",
            evidence={
                "profile_sha256": profile["sha256"],
                "writing_contract_sha256": contract["sha256"],
                "outline_sha256": outline["sha256"],
            },
            note=args.reason,
        )
        state = _rehash(state)
        atomic_write_json_unlocked(state_path, state)
    print_json(state)
    return 0


def command_record_narration_user_outcome(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    state_path = _resolve(root, args.state)
    outcome = _snapshot(root, args.outcome, require_json=True)
    data = _artifact_data(outcome)
    with locked_paths([state_path]):
        state = _load_current(state_path, args.expected_state_hash)
        _assert_actor(state, "coordinator", args.actor_id)
        if state["status"] != "user_review_pending":
            raise PipelineError("user outcome may be recorded only from user_review_pending")
        candidate = state.get("current_candidate") or {}
        if data.get("schema") != "lecture-animation-narration-user-outcome-v1":
            raise PipelineError("invalid narration user outcome schema")
        if not str(data.get("human_text", "")).strip():
            raise PipelineError("narration user outcome must preserve the user's exact words")
        if data.get("candidate_hash") != candidate.get("candidate_hash"):
            raise PipelineError("narration user outcome is not bound to the exact candidate")
        verdict = str(data.get("verdict", "")).strip().lower()
        if verdict not in {"pass", "revise"}:
            raise PipelineError("narration user outcome verdict must be pass or revise")
        resulting_state = "user_script_approved" if verdict == "pass" else "revision_required"
        state["user_outcome"] = {key: outcome[key] for key in ("path", "sha256", "size")}
        _event(
            state,
            event_type="user_script_outcome_recorded",
            actor_id=args.actor_id,
            from_state="user_review_pending",
            to_state=resulting_state,
            evidence={"outcome_sha256": outcome["sha256"], "candidate_hash": candidate["candidate_hash"], "verdict": verdict},
        )
        state = _rehash(state)
        atomic_write_json_unlocked(state_path, state)
    print_json(state)
    return 0


def command_lock_narration_tts_input(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    state_path = _resolve(root, args.state)
    preflight = _snapshot(root, args.preflight, require_json=True)
    data = _artifact_data(preflight)
    with locked_paths([state_path]):
        state = _load_current(state_path, args.expected_state_hash)
        _assert_actor(state, "coordinator", args.actor_id)
        if state["status"] != "user_script_approved":
            raise PipelineError("TTS input cannot lock before exact user script approval")
        if data.get("valid") is not True and data.get("status") != "pass":
            raise PipelineError("narration TTS preflight must pass")
        candidate = state.get("current_candidate") or {}
        if data.get("candidate_hash") != candidate.get("candidate_hash"):
            raise PipelineError("narration TTS preflight is not bound to the exact approved candidate")
        state["tts_lock"] = {
            "candidate_hash": candidate["candidate_hash"],
            "preflight": {key: preflight[key] for key in ("path", "sha256", "size")},
            "locked_at": utc_now(),
        }
        _event(
            state,
            event_type="tts_input_locked",
            actor_id=args.actor_id,
            from_state="user_script_approved",
            to_state="tts_input_locked",
            evidence={"candidate_hash": candidate["candidate_hash"], "preflight_sha256": preflight["sha256"]},
        )
        state = _rehash(state)
        atomic_write_json_unlocked(state_path, state)
    print_json(state)
    return 0


def command_seal_narration_animation_release(args: argparse.Namespace) -> int:
    """Authorize animation only after exact approved narration audio/timing exists."""

    root = Path(args.repo_root).resolve()
    state_path = _resolve(root, args.state)
    release = _snapshot(root, args.release, require_json=True)
    data = _artifact_data(release)
    with locked_paths([state_path]):
        state = _load_current(state_path, args.expected_state_hash)
        _assert_actor(state, "coordinator", args.actor_id)
        if state["status"] != "tts_input_locked":
            raise PipelineError(
                "animation release requires tts_input_locked; normal production "
                "cannot animate before the user-approved script is synthesized, "
                "checked, aligned, and rebound"
            )
        candidate = state.get("current_candidate") or {}
        if data.get("schema") != ANIMATION_RELEASE_SCHEMA:
            raise PipelineError(f"animation release schema must be {ANIMATION_RELEASE_SCHEMA}")
        if data.get("workflow_id") != state.get("workflow_id"):
            raise PipelineError("animation release belongs to another narration workflow")
        if data.get("candidate_hash") != candidate.get("candidate_hash"):
            raise PipelineError("animation release is not bound to the approved script candidate")
        if str(data.get("verdict", "")).strip().lower() != "animation_authorized":
            raise PipelineError("animation release verdict must be animation_authorized")
        _verify_descriptor(root, data.get("post_tts_readiness"), "post_tts_readiness")
        _verify_descriptor(root, data.get("scene_production_inventory"), "scene_production_inventory")
        audio_gate = str(data.get("human_audio_gate", "")).strip()
        if audio_gate not in {"passed", "user_authorized_machine_pending"}:
            raise PipelineError(
                "animation release human_audio_gate must be passed or "
                "user_authorized_machine_pending"
            )
        if audio_gate == "user_authorized_machine_pending" and not str(
            data.get("machine_acceptance_authority", "")
        ).strip():
            raise PipelineError(
                "machine-only audio continuation requires exact user authority"
            )
        repair = state.get("post_animation_repair")
        if isinstance(repair, dict):
            if data.get("repair_context_hash") != repair.get("repair_context_hash"):
                raise PipelineError(
                    "post-animation narration release is not bound to the active repair context"
                )
        state["animation_release"] = {
            key: release[key] for key in ("path", "sha256", "size")
        }
        _event(
            state,
            event_type="narration_animation_authorized",
            actor_id=args.actor_id,
            from_state="tts_input_locked",
            to_state="animation_authorized",
            evidence={
                "candidate_hash": candidate.get("candidate_hash"),
                "release_sha256": release["sha256"],
                "human_audio_gate": audio_gate,
                "repair_context_hash": (repair or {}).get("repair_context_hash"),
            },
        )
        state = _rehash(state)
        atomic_write_json_unlocked(state_path, state)
    print_json(state)
    return 0


def command_rebind_narration_animation_release(args: argparse.Namespace) -> int:
    """Rebind one authorized candidate to fresh, non-broadening release evidence."""

    root = Path(args.repo_root).resolve()
    state_path = _resolve(root, args.state)
    release = _snapshot(root, args.release, require_json=True)
    data = _artifact_data(release)
    with locked_paths([state_path]):
        state = _load_current(state_path, args.expected_state_hash)
        _assert_actor(state, "coordinator", args.actor_id)
        if state["status"] != "animation_authorized":
            raise PipelineError(
                "animation release rebind requires animation_authorized state"
            )
        candidate = state.get("current_candidate") or {}
        current_release = state.get("animation_release") or {}
        current_data = _artifact_data(
            _snapshot(root, current_release.get("path", ""), require_json=True)
        )
        if data.get("schema") != ANIMATION_RELEASE_SCHEMA:
            raise PipelineError(
                f"animation release schema must be {ANIMATION_RELEASE_SCHEMA}"
            )
        if (
            data.get("workflow_id") != state.get("workflow_id")
            or data.get("candidate_hash") != candidate.get("candidate_hash")
            or data.get("verdict") != "animation_authorized"
            or data.get("human_audio_gate") != "user_authorized_machine_pending"
        ):
            raise PipelineError(
                "animation release rebind changes workflow, candidate, verdict or audio gate"
            )
        for key in (
            "workflow_id",
            "candidate_hash",
            "verdict",
            "human_audio_gate",
            "word_alignment_gate",
            "unit_window_design",
            "scene_production_inventory",
            "distinct_unit_window_review",
            "delegated_visual_direction_gate",
            "screen_text_registry",
            "scope",
            "forbidden_claims",
            "invalidation_rule",
        ):
            if data.get(key) != current_data.get(key):
                raise PipelineError(
                    f"animation release rebind changes protected field: {key}"
                )
        old_authority = current_data.get(
            "delegated_episode_provisional_authority", {}
        )
        new_authority = data.get(
            "delegated_episode_provisional_authority", {}
        )
        if (
            old_authority.get("sha256")
            != "165729e8bf552aeb5940e8fd33de7a02c49d9f84425679a896509456df9a544e"
            or new_authority.get("sha256")
            != "db7b677597cc0961255e2fc6972e53e637652956875bd3d1cd26aeaa6d4f4b48"
        ):
            raise PipelineError(
                "animation release rebind is not the exact G012-G015 authority supersession"
            )
        _verify_descriptor(root, new_authority, "delegated_episode_provisional_authority")
        authority_data = _artifact_data(
            _snapshot(root, new_authority.get("path", ""), require_json=True)
        )
        if (
            authority_data.get("schema")
            != "lecture-animation-delegated-unit-window-machine-pending-provisional-animation-authority-v1"
            or authority_data.get("episode") != state.get("episode")
            or not any(
                f"/{scene}/" in f"/{_relative(state_path, root)}/"
                for scene in authority_data.get("scene_scope", [])
            )
            or authority_data.get("supersession", {}).get(
                "superseded_authority_sha256"
            )
            != old_authority.get("sha256")
        ):
            raise PipelineError("animation release rebind authority is invalid")
        _verify_descriptor(root, data.get("post_tts_readiness"), "post_tts_readiness")
        _verify_descriptor(
            root,
            data.get("scene_production_inventory"),
            "scene_production_inventory",
        )
        state["animation_release"] = {
            key: release[key] for key in ("path", "sha256", "size")
        }
        _event(
            state,
            event_type="narration_animation_release_rebound",
            actor_id=args.actor_id,
            from_state="animation_authorized",
            to_state="animation_authorized",
            evidence={
                "candidate_hash": candidate.get("candidate_hash"),
                "previous_release_sha256": current_release.get("sha256"),
                "release_sha256": release.get("sha256"),
                "superseding_authority_sha256": new_authority.get("sha256"),
            },
        )
        state = _rehash(state)
        atomic_write_json_unlocked(state_path, state)
    print_json(state)
    return 0


def command_open_post_animation_narration_repair(args: argparse.Namespace) -> int:
    """Open the exceptional path for narration repair after animation exists."""

    root = Path(args.repo_root).resolve()
    state_path = _resolve(root, args.state)
    repair = _snapshot(root, args.repair, require_json=True)
    repair_data = _artifact_data(repair)
    authority = _snapshot(root, args.user_authority, require_json=True)
    authority_data = _artifact_data(authority)
    baseline = _snapshot(root, args.baseline_manifest)
    with locked_paths([state_path]):
        state = _load_current(state_path, args.expected_state_hash)
        _assert_actor(state, "coordinator", args.actor_id)
        if state["status"] != "animation_authorized":
            raise PipelineError(
                "post-animation narration repair may open only from an exact "
                "animation-authorized lineage"
            )
        candidate = state.get("current_candidate") or {}
        if repair_data.get("schema") != POST_ANIMATION_REPAIR_SCHEMA:
            raise PipelineError(f"repair schema must be {POST_ANIMATION_REPAIR_SCHEMA}")
        repair_kind = str(repair_data.get("repair_kind", "")).strip()
        if repair_kind not in POST_ANIMATION_REPAIR_KINDS:
            raise PipelineError(
                "post-animation narration repair_kind must be performance_only or script_change"
            )
        if repair_data.get("workflow_id") != state.get("workflow_id"):
            raise PipelineError("repair belongs to another narration workflow")
        if repair_data.get("candidate_hash") != candidate.get("candidate_hash"):
            raise PipelineError("repair is not bound to the current script candidate")
        affected_scenes = repair_data.get("affected_scenes")
        cue_windows = repair_data.get("cue_windows")
        if not isinstance(affected_scenes, list) or not affected_scenes:
            raise PipelineError("post-animation narration repair requires affected_scenes")
        if not isinstance(cue_windows, list) or not cue_windows:
            raise PipelineError("post-animation narration repair requires exact cue_windows")
        invalidations = set(repair_data.get("invalidates", []))
        missing_invalidations = POST_ANIMATION_INVALIDATIONS - invalidations
        if missing_invalidations:
            raise PipelineError(
                "post-animation narration repair must invalidate all downstream evidence: "
                + ", ".join(sorted(missing_invalidations))
            )
        source_change_allowed = repair_data.get("animation_source_change_allowed")
        if source_change_allowed not in {True, False}:
            raise PipelineError("repair must explicitly declare animation_source_change_allowed")
        if authority_data.get("schema") != USER_AUTHORITY_SCHEMA:
            raise PipelineError(f"user authority schema must be {USER_AUTHORITY_SCHEMA}")
        if authority_data.get("authorization") != "post_animation_narration_repair":
            raise PipelineError("user authority does not authorize post-animation narration repair")
        if authority_data.get("workflow_id") != state.get("workflow_id"):
            raise PipelineError("user authority belongs to another narration workflow")
        if authority_data.get("candidate_hash") != candidate.get("candidate_hash"):
            raise PipelineError("user authority is not bound to the current candidate")
        if not str(authority_data.get("human_text", "")).strip():
            raise PipelineError("post-animation repair must preserve the user's exact words")
        if source_change_allowed and authority_data.get("animation_source_change_allowed") is not True:
            raise PipelineError("animation source changes require explicit user authority")
        context = {
            "repair_kind": repair_kind,
            "repair": {key: repair[key] for key in ("path", "sha256", "size")},
            "user_authority": {key: authority[key] for key in ("path", "sha256", "size")},
            "baseline_manifest": {key: baseline[key] for key in ("path", "sha256", "size")},
            "affected_scenes": affected_scenes,
            "cue_windows": cue_windows,
            "animation_source_change_allowed": source_change_allowed,
            "invalidates": sorted(invalidations),
            "opened_at": utc_now(),
        }
        context["repair_context_hash"] = object_hash(context)
        state.setdefault("superseded_bindings", []).append(
            {
                "recorded_at": utc_now(),
                "reason": "post_animation_narration_repair",
                "artifacts": {
                    "tts_lock": state.get("tts_lock"),
                    "animation_release": state.get("animation_release"),
                    "baseline_manifest": context["baseline_manifest"],
                },
            }
        )
        state["post_animation_repair"] = context
        state["tts_lock"] = None
        state["animation_release"] = None
        previous = state["status"]
        if repair_kind == "performance_only":
            resulting_state = "user_script_approved"
        else:
            resulting_state = "revision_required"
            state["current_candidate"] = None
            state["author_self_review"] = None
            state["independent_review"] = None
            state["user_outcome"] = None
        _event(
            state,
            event_type="post_animation_narration_repair_opened",
            actor_id=args.actor_id,
            from_state=previous,
            to_state=resulting_state,
            evidence={
                "repair_kind": repair_kind,
                "repair_context_hash": context["repair_context_hash"],
                "baseline_manifest_sha256": baseline["sha256"],
                "animation_source_change_allowed": source_change_allowed,
            },
            note=str(repair_data.get("reason", "")).strip() or None,
        )
        state = _rehash(state)
        atomic_write_json_unlocked(state_path, state)
    print_json(state)
    return 0


def command_narration_workflow_status(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    state_path = _resolve(root, args.state)
    state = load_json(state_path)
    errors: list[str] = []
    if not isinstance(state, dict) or state.get("schema") not in {SCHEMA, *LEGACY_SCHEMAS}:
        raise PipelineError("invalid narration workflow state")
    expected_hash = state.get("state_hash")
    recomputed = _rehash(state).get("state_hash")
    if expected_hash != recomputed:
        errors.append("state_hash mismatch")
    for label in ("profile", "writing_contract", "outline"):
        errors.extend(_verify_snapshot(root, state.get(label, {}), label))
    candidate = state.get("current_candidate")
    if isinstance(candidate, dict):
        for label in ("script_markdown", "script_json", "static_audit"):
            errors.extend(_verify_snapshot(root, candidate.get(label, {}), f"candidate.{label}"))
    release = state.get("animation_release")
    if isinstance(release, dict):
        errors.extend(_verify_snapshot(root, release, "animation_release"))
    repair = state.get("post_animation_repair")
    if isinstance(repair, dict):
        for label in ("repair", "user_authority", "baseline_manifest"):
            errors.extend(_verify_snapshot(root, repair.get(label, {}), f"post_animation_repair.{label}"))
    if args.require_state and state.get("status") != args.require_state:
        errors.append(f"required state is {args.require_state}, actual is {state.get('status')}")
    report = {
        "valid": not errors,
        "state_path": _relative(state_path, root),
        "workflow_id": state.get("workflow_id"),
        "status": state.get("status"),
        "state_hash": state.get("state_hash"),
        "profile_id": state.get("profile_id"),
        "candidate_hash": (candidate or {}).get("candidate_hash"),
        "errors": errors,
    }
    print_json(report)
    return 0 if not errors else 2


def print_json(value: Any) -> None:
    import json

    print(json.dumps(value, ensure_ascii=False, indent=2))


def _add_state_mutation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--state", required=True)
    parser.add_argument("--expected-state-hash", required=True)
    parser.add_argument("--actor-id", required=True)


def _add_candidate_args(parser: argparse.ArgumentParser, *, required: bool = True) -> None:
    parser.add_argument("--script-markdown", required=required)
    parser.add_argument("--script-json", required=required)
    parser.add_argument("--static-audit", required=required)
    parser.add_argument("--candidate-label", required=required)


def add_narration_workflow_subparsers(subparsers: argparse._SubParsersAction) -> None:
    init = subparsers.add_parser("init-narration-workflow", help="bind an explicit audience profile and narration outline")
    init.add_argument("--repo-root", default=".")
    init.add_argument("--state", required=True)
    init.add_argument("--workflow-id", required=True)
    init.add_argument("--episode", required=True)
    init.add_argument("--profile", required=True)
    init.add_argument("--writing-contract", required=True)
    init.add_argument("--outline", required=True)
    init.add_argument("--author-id", required=True)
    init.add_argument("--reviewer-id", required=True)
    init.add_argument("--coordinator-id", required=True)
    init.add_argument("--replace", action="store_true")
    init.add_argument("--reason")
    init.set_defaults(func=command_init_narration_workflow)

    outline = subparsers.add_parser("record-narration-outline-review", help="record an independent outline/profile pass")
    _add_state_mutation_args(outline)
    outline.add_argument("--review", required=True)
    outline.set_defaults(func=command_record_narration_outline_review)

    drafting = subparsers.add_parser("open-narration-drafting", help="open authoring after outline approval or revise")
    _add_state_mutation_args(drafting)
    drafting.add_argument("--reason", required=True)
    drafting.set_defaults(func=command_open_narration_drafting)

    freeze = subparsers.add_parser("freeze-narration-script", help="freeze one exact script candidate")
    _add_state_mutation_args(freeze)
    _add_candidate_args(freeze)
    freeze.set_defaults(func=command_freeze_narration_script)

    self_review = subparsers.add_parser("seal-narration-author-self-review", help="seal author self-review of the frozen script")
    _add_state_mutation_args(self_review)
    self_review.add_argument("--review", required=True)
    self_review.set_defaults(func=command_seal_narration_author_self_review)

    independent = subparsers.add_parser("record-narration-independent-review", help="record immutable independent narration review")
    _add_state_mutation_args(independent)
    independent.add_argument("--attempt-log", required=True)
    independent.add_argument("--report", required=True)
    independent.add_argument("--import-existing-candidate", action="store_true")
    _add_candidate_args(independent, required=False)
    independent.set_defaults(func=command_record_narration_independent_review)

    rebind = subparsers.add_parser("rebind-narration-profile", help="hot-rebind profile/contract and invalidate downstream approvals")
    _add_state_mutation_args(rebind)
    rebind.add_argument("--profile", required=True)
    rebind.add_argument("--writing-contract", required=True)
    rebind.add_argument("--outline", required=True)
    rebind.add_argument("--reason", required=True)
    rebind.set_defaults(func=command_rebind_narration_profile)

    outcome = subparsers.add_parser("record-narration-user-outcome", help="record the user's exact script verdict")
    _add_state_mutation_args(outcome)
    outcome.add_argument("--outcome", required=True)
    outcome.set_defaults(func=command_record_narration_user_outcome)

    tts = subparsers.add_parser("lock-narration-tts-input", help="lock exact user-approved text for TTS")
    _add_state_mutation_args(tts)
    tts.add_argument("--preflight", required=True)
    tts.set_defaults(func=command_lock_narration_tts_input)

    release = subparsers.add_parser(
        "seal-narration-animation-release",
        help=(
            "authorize animation after the approved script has exact TTS, ASR, "
            "alignment, subtitle, timeline, and narration-QC bindings"
        ),
    )
    _add_state_mutation_args(release)
    release.add_argument("--release", required=True)
    release.set_defaults(func=command_seal_narration_animation_release)

    release_rebind = subparsers.add_parser(
        "rebind-narration-animation-release",
        help=(
            "rebind an already-authorized candidate to the exact superseding "
            "G012-G015 unit-window provisional authority"
        ),
    )
    _add_state_mutation_args(release_rebind)
    release_rebind.add_argument("--release", required=True)
    release_rebind.set_defaults(func=command_rebind_narration_animation_release)

    repair = subparsers.add_parser(
        "open-post-animation-narration-repair",
        help=(
            "open the explicit exceptional path for narration repair after "
            "animation exists; never use this as the normal authoring route"
        ),
    )
    _add_state_mutation_args(repair)
    repair.add_argument("--repair", required=True)
    repair.add_argument("--user-authority", required=True)
    repair.add_argument("--baseline-manifest", required=True)
    repair.set_defaults(func=command_open_post_animation_narration_repair)

    status = subparsers.add_parser("narration-workflow-status", help="verify narration workflow state and frozen bytes")
    status.add_argument("--repo-root", default=".")
    status.add_argument("--state", required=True)
    status.add_argument("--require-state")
    status.set_defaults(func=command_narration_workflow_status)
