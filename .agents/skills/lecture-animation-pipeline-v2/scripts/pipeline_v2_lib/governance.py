"""Governance rules that must remain independent from the CLI presentation layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import object_hash
from .storage import load_json


BLOCKING_SEVERITIES = {"blocker", "critical", "major", "high"}
PASS_REVIEW_ROLES = {"acceptance"}


def unresolved_policy_blockers(policy: dict[str, Any]) -> list[dict[str, Any]]:
    """Return applicable, still-open issues that forbid a candidate handoff."""

    blockers: list[dict[str, Any]] = []
    for entry in policy.get("entries", []):
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status", "unknown")).strip().lower().replace("-", "_")
        severity = str(entry.get("severity", "unknown")).strip().lower()
        if status.startswith("open") and severity in BLOCKING_SEVERITIES:
            blockers.append(entry)
    return blockers


def validate_pass_policy(policy: dict[str, Any]) -> list[str]:
    blockers = unresolved_policy_blockers(policy)
    if not blockers:
        return []
    labels = ", ".join(
        f"{item.get('issue_id')}[{item.get('severity')}:{item.get('status')}]"
        for item in blockers
    )
    return [
        "pass is blocked by applicable unresolved live-policy issues: " + labels
        + "; repair them, update issue status, and recompile/freeze the candidate"
    ]


def review_session_governance(
    spine: dict[str, Any],
    *,
    reviewer_agent_id: str,
    author_agent_id: str,
    review_role: str,
) -> tuple[dict[str, Any], list[str]]:
    """Compile immutable reviewer-role facts from the episode spine."""

    errors: list[str] = []
    production_mode = str(spine.get("production_mode", "main_producer"))
    governance = spine.get("main_agent_governance", {})
    main_agent_id = str(governance.get("owner", "")).strip() if isinstance(governance, dict) else ""
    if review_role not in {"acceptance", "diagnostic_support"}:
        errors.append("review_role must be acceptance or diagnostic_support")
    if reviewer_agent_id == author_agent_id:
        errors.append("reviewer_agent_id must differ from author_agent_id")
    if production_mode == "parallel_batches":
        if not main_agent_id:
            errors.append("parallel review requires main_agent_governance.owner")
        elif review_role == "acceptance" and reviewer_agent_id != main_agent_id:
            errors.append("parallel acceptance review must be performed by the episode main agent")
    return (
        {
            "production_mode": production_mode,
            "main_agent_id": main_agent_id,
            "review_role": review_role,
            "episode_spine_hash": spine.get("spine_hash"),
        },
        errors,
    )


def validate_session_governance(
    session: dict[str, Any],
    manifest: dict[str, Any],
    repo_root: Path,
    verdict: str,
) -> list[str]:
    """Recheck that the live frozen spine still authorizes this reviewer."""

    errors: list[str] = []
    descriptor = manifest.get("artifacts", {}).get("episode_spine", {})
    raw_path = str(descriptor.get("path", "")).strip()
    if not raw_path:
        return ["review manifest is missing the episode_spine governance artifact"]
    spine_path = Path(raw_path)
    if not spine_path.is_absolute():
        spine_path = repo_root / spine_path
    try:
        spine = load_json(spine_path)
    except Exception as exc:  # converted to a stable gate error for callers
        return [f"cannot load episode_spine governance artifact: {exc}"]
    payload = dict(spine)
    expected_hash = payload.pop("spine_hash", None)
    if not expected_hash or expected_hash != object_hash(payload):
        errors.append("episode_spine governance hash is invalid")
    facts, fact_errors = review_session_governance(
        spine,
        reviewer_agent_id=str(session.get("reviewer_agent_id", "")),
        author_agent_id=str(session.get("author_agent_id", "")),
        review_role=str(session.get("review_role", "")),
    )
    errors.extend(fact_errors)
    for field in ("production_mode", "main_agent_id", "review_role", "episode_spine_hash"):
        if session.get(field) != facts.get(field):
            errors.append(f"review session governance is stale: {field}")
    if verdict == "pass_for_user_review_pending" and session.get("review_role") not in PASS_REVIEW_ROLES:
        errors.append("diagnostic_support reviewers cannot grant pass_for_user_review_pending")
    return errors


def validate_pending_repair_binding(
    session: dict[str, Any],
    scene_slug: str,
    author_self_review: dict[str, Any],
    verdict: str,
) -> list[str]:
    """Prevent a fresh self-review from bypassing a recorded revise verdict."""

    pending = session.get("pending_repairs", {}).get(scene_slug)
    if not pending or verdict != "pass_for_user_review_pending":
        return []
    context = author_self_review.get("repair_context", {})
    errors: list[str] = []
    if context.get("previous_review_hash") != pending.get("review_hash"):
        errors.append("pass is bound to an unresolved revise review; author self-review must use that previous review")
    for field in ("repair_contract_hash", "repair_response_hash", "repair_gate_hash"):
        if len(str(context.get(field, "")).strip()) < 16:
            errors.append(f"pending revise review requires {field} before another pass")
    return errors
