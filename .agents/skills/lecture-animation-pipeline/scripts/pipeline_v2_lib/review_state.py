"""Transactional review-attempt and persistent-session state transitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import PipelineError, object_hash
from .storage import (
    append_jsonl_unlocked,
    atomic_write_json_unlocked,
    load_json_unlocked,
    locked_paths,
    read_jsonl_unlocked,
)


def _rehash_session(session: dict[str, Any]) -> dict[str, Any]:
    payload = dict(session)
    payload.pop("session_hash", None)
    payload["session_hash"] = object_hash(payload)
    return payload


def commit_review_attempt(
    *,
    session_path: Path,
    attempt_log: Path,
    expected_session_hash: str,
    attempt: dict[str, Any],
    scene_slug: str,
    manifest_hash: str,
    calibration_performed: bool,
    reviewer_anomalous: bool,
    review_mode: str = "full_regression",
) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    """Commit one review attempt and its session mutation as one locked action.

    The JSONL append and JSON replacement cannot be one filesystem transaction,
    so the session keeps applied attempt ids. Retrying after a crash repairs the
    session side without duplicating the attempt row.
    """

    verification_key = attempt.get("verification_key")
    attempt_id = str(attempt.get("attempt_id", ""))
    if not verification_key or not attempt_id:
        raise PipelineError("review attempt requires verification_key and attempt_id")
    with locked_paths([session_path, attempt_log]):
        session = load_json_unlocked(session_path)
        existing = next(
            (row for row in read_jsonl_unlocked(attempt_log) if row.get("verification_key") == verification_key),
            None,
        )
        stored = existing or attempt
        stored_attempt_id = str(stored.get("attempt_id", ""))
        applied = list(session.get("applied_review_attempt_ids", []))
        if existing is not None and stored_attempt_id in applied:
            return stored, False, session
        if existing is None and session.get("session_hash") != expected_session_hash:
            raise PipelineError(
                "review session changed during verification; reload the session and rerun verify-review"
            )
        if existing is None:
            append_jsonl_unlocked(attempt_log, attempt)

        if stored_attempt_id not in applied:
            applied.append(stored_attempt_id)
            session["applied_review_attempt_ids"] = applied
            session["last_review_attempt_id"] = stored_attempt_id
            accepted = stored.get("gate_accepted") is True
            session["review_submission_attempts"] = int(
                session.get("review_submission_attempts", 0) or 0
            ) + 1
            if accepted:
                session["last_manifest_hash"] = manifest_hash
                counter = "diagnostic_reviews" if review_mode == "diagnostic" else "full_reviews"
                session[counter] = int(session.get(counter, 0) or 0) + 1
                scenes = list(session.get("scenes", []))
                if review_mode != "diagnostic" and scene_slug not in scenes:
                    scenes.append(scene_slug)
                session["scenes"] = scenes
                session["calibration_due"] = (
                    False
                    if calibration_performed
                    else reviewer_anomalous
                    or len(scenes) >= int(session.get("calibration_scene_interval", 5) or 5)
                )
            else:
                session["gate_rejected_attempts"] = int(
                    session.get("gate_rejected_attempts", 0) or 0
                ) + 1
            pending_repairs = dict(session.get("pending_repairs", {}))
            if (
                review_mode != "diagnostic"
                and accepted
                and stored.get("verdict") == "revise"
            ):
                pending_repairs[scene_slug] = {
                    "review_hash": stored.get("submission_hash"),
                    "review_attempt_id": stored_attempt_id,
                    "findings_count": int(stored.get("findings_count", 0) or 0),
                    "manifest_hash": manifest_hash,
                }
            elif (
                review_mode != "diagnostic"
                and accepted
                and stored.get("verdict") == "pass_for_user_review_pending"
            ):
                pending_repairs.pop(scene_slug, None)
            session["pending_repairs"] = pending_repairs
            session["revision"] = int(session.get("revision", 0) or 0) + 1
            session = _rehash_session(session)
            atomic_write_json_unlocked(session_path, session)
        return stored, existing is None, session


def create_review_session(
    path: Path,
    session: dict[str, Any],
    *,
    replace: bool,
    replace_reason: str | None,
) -> dict[str, Any]:
    """Create or replace an active session without a check-then-write race."""

    with locked_paths([path]):
        if path.exists():
            current = load_json_unlocked(path)
            if current.get("status") == "active" and not replace:
                raise PipelineError("an active review session already exists; resume it or use --replace with a recorded reason")
        payload = dict(session)
        if replace:
            payload["replacement_reason"] = replace_reason
        payload.setdefault("revision", 0)
        payload.setdefault("applied_review_attempt_ids", [])
        payload.setdefault("pending_repairs", {})
        payload = _rehash_session(payload)
        atomic_write_json_unlocked(path, payload)
        return payload


def record_human_false_pass(path: Path, event_id: str) -> dict[str, Any]:
    """Update reviewer health under one locked read-modify-write transition."""

    with locked_paths([path]):
        session = load_json_unlocked(path)
        session["calibration_due"] = True
        session["human_false_passes"] = int(session.get("human_false_passes", 0) or 0) + 1
        session["last_human_rejection_event_id"] = event_id
        if session.get("reviewer_tier") == "light":
            session["certification_suspended"] = True
            session["escalation_required"] = True
        session["revision"] = int(session.get("revision", 0) or 0) + 1
        session = _rehash_session(session)
        atomic_write_json_unlocked(path, session)
        return session
