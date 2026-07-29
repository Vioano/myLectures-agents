#!/usr/bin/env python3
"""Durable low-noise supervision contract for V2 subagent work."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from pipeline_v2_lib.core import PipelineError, object_hash, utc_now
from pipeline_v2_lib.storage import (
    append_jsonl_unlocked,
    atomic_write_json_unlocked,
    load_json,
    load_json_unlocked,
    locked_paths,
    read_jsonl,
    read_jsonl_unlocked,
)


SCHEMA = "lecture-animation-supervisor-session-v2"
LEGACY_SCHEMA = "lecture-animation-supervisor-session-v1"
AVAILABILITY_SCHEMA = "lecture-animation-agent-availability-v1"
REPORTABLE_EVENT_TYPES = {
    "human_review_ready",
    "user_decision_required",
    "major_delivery_blocker",
    "explicit_status_request",
}
ROUTINE_EVENT_TYPES = {
    "agent_heartbeat",
    "routine_progress",
    "repair_detail",
    "timestamp_evidence",
    "hash_or_gate_detail",
}
ASSIGNMENT_STATES = {"active", "idle", "completed", "blocked", "cancelled", "retired"}
REUSABLE_STATES = {"idle", "completed"}
REPLACEMENT_REASONS = {
    "agent_unavailable",
    "task_tree_changed",
    "model_change_required",
    "unrecoverable_failure",
}
FOLLOWUP_OUTCOMES = {
    "restored",
    "target_not_found",
    "target_unavailable",
    "unrecoverable_error",
}
DEFAULT_MAX_SUBAGENTS = 3
DEFAULT_MAX_REPLACEMENTS = 1
MAX_AVAILABILITY_AGE_SECONDS = 15 * 60
REVIEW_TODO_STATES = {
    "deferred_until_safe_checkpoint",
    "interrupt_required",
    "ready_to_deliver",
    "delivered",
    "cancelled",
}
REVIEW_TODO_PRIORITIES = {
    "nonblocking",
    "continuity_blocking",
    "user_decision_blocking",
}
OPEN_REVIEW_TODO_STATES = REVIEW_TODO_STATES - {"delivered", "cancelled"}


def session_hash(session: dict[str, Any]) -> str:
    payload = dict(session)
    payload.pop("session_hash", None)
    return object_hash(payload)


def seal(session: dict[str, Any]) -> dict[str, Any]:
    result = dict(session)
    result["session_hash"] = session_hash(result)
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bound_file(path: Path) -> dict[str, Any]:
    """Bind a checkpoint artifact to its exact current bytes."""
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PipelineError(f"checkpoint artifact does not exist: {resolved}")
    return {
        "path": str(resolved),
        "sha256": sha256_file(resolved),
        "size": resolved.stat().st_size,
    }


def validate_bound_file(binding: dict[str, Any], label: str) -> None:
    """Reject a checkpoint whose bound artifact changed after sealing."""
    if not isinstance(binding, dict):
        raise PipelineError(f"animatic checkpoint {label} binding is invalid")
    path = Path(str(binding.get("path", ""))).expanduser().resolve()
    if not path.is_file():
        raise PipelineError(f"animatic checkpoint {label} artifact is missing: {path}")
    if int(binding.get("size", -1)) != path.stat().st_size:
        raise PipelineError(f"animatic checkpoint {label} size is stale")
    if str(binding.get("sha256", "")) != sha256_file(path):
        raise PipelineError(f"animatic checkpoint {label} hash is stale")


def validate_session(session: dict[str, Any]) -> None:
    schema = session.get("schema")
    if schema not in {SCHEMA, LEGACY_SCHEMA}:
        raise PipelineError("supervisor session schema is invalid")
    if session.get("session_hash") != session_hash(session):
        raise PipelineError("supervisor session hash is invalid or stale")
    if session.get("communication_mode") not in {"continuous_low_noise", "explicit_verbose_override"}:
        raise PipelineError("supervisor communication mode is invalid")
    assignments = session.get("assignments")
    if not isinstance(assignments, dict) or not assignments:
        raise PipelineError("supervisor session requires at least one assignment")
    for agent_id, assignment in assignments.items():
        if not str(agent_id).strip() or not isinstance(assignment, dict):
            raise PipelineError("supervisor assignments must be keyed by agent id")
        if assignment.get("state") not in ASSIGNMENT_STATES:
            raise PipelineError(f"invalid assignment state for {agent_id}")
        if not str(assignment.get("role", "")).strip() or not str(assignment.get("scope", "")).strip():
            raise PipelineError(f"assignment {agent_id} requires role and scope")
    if schema == SCHEMA:
        maximum = int(session.get("max_subagents", 0) or 0)
        if maximum < 1:
            raise PipelineError("supervisor max_subagents must be positive")
        if len(assignments) > maximum:
            raise PipelineError("supervisor roster exceeds max_subagents")
        if maximum > DEFAULT_MAX_SUBAGENTS and not str(session.get("capacity_override_reason", "")).strip():
            raise PipelineError("a roster above three subagents requires a recorded capacity override")
        if int(session.get("max_replacements", -1)) < 0:
            raise PipelineError("supervisor max_replacements cannot be negative")
        history = session.get("identity_history")
        if not isinstance(history, list) or not set(assignments) <= set(map(str, history)):
            raise PipelineError("supervisor identity_history must include the current roster")
        authorizations = session.get("replacement_authorizations")
        if not isinstance(authorizations, dict):
            raise PipelineError("supervisor replacement_authorizations must be an object")
        task_queue = session.get("task_queue")
        if not isinstance(task_queue, dict) or not task_queue:
            raise PipelineError("supervisor task_queue must contain the sealed episode work")
        for task_key, task in task_queue.items():
            if not str(task_key).strip() or not isinstance(task, dict):
                raise PipelineError("supervisor task_queue entries must be structured")
            if task.get("state") not in {"pending", "active", "completed", "blocked", "cancelled"}:
                raise PipelineError(f"supervisor task {task_key} has invalid state")
            if not str(task.get("role", "")).strip() or not str(task.get("scope", "")).strip():
                raise PipelineError(f"supervisor task {task_key} requires role and scope")
        for agent_id, assignment in assignments.items():
            if not str(assignment.get("task_key", "")).strip():
                raise PipelineError(f"assignment {agent_id} requires task_key")
            if not str(assignment.get("model", "")).strip():
                raise PipelineError(f"assignment {agent_id} requires model")
            if int(assignment.get("task_count", 0) or 0) < 1:
                raise PipelineError(f"assignment {agent_id} has invalid task_count")
            if int(assignment.get("reuse_count", -1) or 0) < 0:
                raise PipelineError(f"assignment {agent_id} has invalid reuse_count")
        review_todos = session.get("review_todos", {})
        if not isinstance(review_todos, dict):
            raise PipelineError("supervisor review_todos must be an object")
        retired_agent_ids = {
            str(item.get("agent_id"))
            for item in session.get("retired_identities", [])
            if isinstance(item, dict) and str(item.get("agent_id", "")).strip()
        }
        for todo_id, todo in review_todos.items():
            if not str(todo_id).strip() or not isinstance(todo, dict):
                raise PipelineError("supervisor review_todos entries must be structured")
            if todo.get("state") not in REVIEW_TODO_STATES:
                raise PipelineError(f"review todo {todo_id} has invalid state")
            if todo.get("priority") not in REVIEW_TODO_PRIORITIES:
                raise PipelineError(f"review todo {todo_id} has invalid priority")
            todo_agent_id = str(todo.get("agent_id", ""))
            if todo_agent_id not in assignments:
                if not (
                    todo.get("state") == "delivered"
                    and todo_agent_id in retired_agent_ids
                ):
                    raise PipelineError(f"review todo {todo_id} targets an unknown agent")
            if not str(todo.get("reviewed_scene_slug", "")).strip():
                raise PipelineError(f"review todo {todo_id} requires reviewed_scene_slug")
            artifact = todo.get("review_artifact")
            if not isinstance(artifact, dict) or not str(artifact.get("path", "")).strip():
                raise PipelineError(f"review todo {todo_id} requires a bound review artifact")
            if not str(artifact.get("sha256", "")).strip():
                raise PipelineError(f"review todo {todo_id} requires a review artifact hash")
            if todo.get("priority") == "nonblocking":
                if not str(todo.get("wait_for_scene_slug", "")).strip():
                    raise PipelineError(
                        f"nonblocking review todo {todo_id} requires wait_for_scene_slug"
                    )
                if todo.get("state") == "interrupt_required":
                    raise PipelineError(
                        f"nonblocking review todo {todo_id} cannot require interruption"
                    )
            elif todo.get("state") == "deferred_until_safe_checkpoint":
                raise PipelineError(
                    f"blocking review todo {todo_id} cannot be deferred"
                )


def parse_assignment(raw: str) -> tuple[str, dict[str, Any]]:
    parts = raw.split("|", 4)
    if len(parts) != 5 or any(not part.strip() for part in parts):
        raise PipelineError("--assignment must be AGENT_ID|ROLE|TASK_KEY|SCOPE|MODEL")
    agent_id, role, task_key, scope, model = (part.strip() for part in parts)
    now = utc_now()
    return agent_id, {
        "role": role,
        "task_key": task_key,
        "scope": scope,
        "model": model,
        "state": "active",
        "task_count": 1,
        "reuse_count": 0,
        "replacement_of": None,
        "assignment_history": [
            {"task_key": task_key, "scope": scope, "assigned_at": now, "kind": "initial"}
        ],
        "updated_at": now,
    }


def parse_planned_task(raw: str) -> tuple[str, dict[str, Any]]:
    parts = raw.split("|", 2)
    if len(parts) != 3 or any(not part.strip() for part in parts):
        raise PipelineError("--planned-task must be TASK_KEY|ROLE|SCOPE")
    task_key, role, scope = (part.strip() for part in parts)
    return task_key, {
        "role": role,
        "scope": scope,
        "state": "pending",
        "current_agent_id": None,
        "updated_at": utc_now(),
    }


def seal_availability_snapshot(args: argparse.Namespace) -> int:
    """Seal one collaboration.list_agents snapshot plus direct followup outcomes."""
    followup_attempts: dict[str, dict[str, str]] = {}
    for raw in args.followup_attempt:
        parts = raw.split("|", 2)
        if len(parts) != 3 or any(not part.strip() for part in parts):
            raise PipelineError(
                "--followup-attempt must be AGENT_ID|OUTCOME|EVIDENCE"
            )
        agent_id, outcome, evidence = (part.strip() for part in parts)
        if outcome not in FOLLOWUP_OUTCOMES:
            raise PipelineError(
                "followup outcome must be one of: " + ", ".join(sorted(FOLLOWUP_OUTCOMES))
            )
        if len(evidence) < 24:
            raise PipelineError("followup attempt requires concrete evidence")
        if agent_id in followup_attempts:
            raise PipelineError(f"duplicate followup attempt for {agent_id}")
        followup_attempts[agent_id] = {
            "outcome": outcome,
            "evidence": evidence,
        }
    live = list(dict.fromkeys(map(str, args.live_agent_id)))
    reusable = list(dict.fromkeys(map(str, args.reusable_agent_id)))
    if not set(reusable) <= set(live):
        raise PipelineError("reusable agent ids must be a subset of live agent ids")
    payload = {
        "schema": AVAILABILITY_SCHEMA,
        "source": "collaboration.list_agents",
        "captured_at": utc_now(),
        "live_agent_ids": live,
        "reusable_agent_ids": reusable,
        "followup_attempts": followup_attempts,
    }
    snapshot = dict(payload)
    snapshot["snapshot_hash"] = object_hash(payload)
    output = Path(args.output).expanduser().resolve()
    with locked_paths([output]):
        atomic_write_json_unlocked(output, snapshot)
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


def require_v2(session: dict[str, Any]) -> None:
    if session.get("schema") != SCHEMA:
        raise PipelineError("this roster operation requires a v2 supervisor session; start a new session")


def load_availability_snapshot(path: Path) -> dict[str, Any]:
    snapshot = load_json(path)
    if snapshot.get("schema") != AVAILABILITY_SCHEMA:
        raise PipelineError("availability snapshot schema is invalid")
    supplied_hash = snapshot.get("snapshot_hash")
    payload = dict(snapshot)
    payload.pop("snapshot_hash", None)
    if supplied_hash != object_hash(payload):
        raise PipelineError("availability snapshot hash is invalid or stale")
    if snapshot.get("source") != "collaboration.list_agents":
        raise PipelineError("availability snapshot must come from collaboration.list_agents")
    try:
        captured = datetime.fromisoformat(str(snapshot.get("captured_at", "")).replace("Z", "+00:00"))
        if captured.tzinfo is None:
            captured = captured.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - captured.astimezone(timezone.utc)).total_seconds()
    except ValueError as exc:
        raise PipelineError("availability snapshot captured_at is invalid") from exc
    if age < -30 or age > MAX_AVAILABILITY_AGE_SECONDS:
        raise PipelineError("availability snapshot is too old for replacement authorization")
    live = snapshot.get("live_agent_ids")
    reusable = snapshot.get("reusable_agent_ids")
    if not isinstance(live, list) or not isinstance(reusable, list):
        raise PipelineError("availability snapshot requires live_agent_ids and reusable_agent_ids")
    if not set(map(str, reusable)) <= set(map(str, live)):
        raise PipelineError("availability reusable_agent_ids must be a subset of live_agent_ids")
    return snapshot


def validate_availability_snapshot(path: Path, old_agent_id: str) -> dict[str, Any]:
    snapshot = load_availability_snapshot(path)
    reusable = snapshot.get("reusable_agent_ids", [])
    if old_agent_id in set(map(str, reusable)):
        raise PipelineError("old agent is still reusable; send followup_task instead of spawning a replacement")
    attempts = snapshot.get("followup_attempts")
    if not isinstance(attempts, dict):
        raise PipelineError(
            "replacement authorization requires sealed direct followup_task evidence"
        )
    attempt = attempts.get(old_agent_id)
    if not isinstance(attempt, dict):
        raise PipelineError(
            "replacement authorization requires a direct followup_task attempt for the old agent"
        )
    if attempt.get("outcome") == "restored":
        raise PipelineError("old agent was restored; replacement authorization is forbidden")
    if attempt.get("outcome") not in {
        "target_not_found",
        "target_unavailable",
        "unrecoverable_error",
    }:
        raise PipelineError("replacement followup outcome is invalid")
    if len(str(attempt.get("evidence", "")).strip()) < 24:
        raise PipelineError("replacement followup attempt lacks concrete evidence")
    return snapshot


def event_log_path(session_path: Path, session: dict[str, Any]) -> Path:
    raw = str(session.get("event_log", "")).strip()
    if not raw:
        raise PipelineError("supervisor session is missing event_log")
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (session_path.parent / path).resolve()


def begin(args: argparse.Namespace) -> int:
    output = Path(args.output).resolve()
    assignments: dict[str, dict[str, Any]] = {}
    for raw in args.assignment:
        agent_id, assignment = parse_assignment(raw)
        if agent_id in assignments:
            raise PipelineError(f"duplicate supervisor assignment: {agent_id}")
        assignments[agent_id] = assignment
    task_queue: dict[str, dict[str, Any]] = {}
    for raw in args.planned_task:
        task_key, task = parse_planned_task(raw)
        if task_key in task_queue:
            raise PipelineError(f"duplicate planned task: {task_key}")
        task_queue[task_key] = task
    for agent_id, assignment in assignments.items():
        task_key = str(assignment["task_key"])
        existing = task_queue.get(task_key)
        if existing and (existing["role"] != assignment["role"] or existing["scope"] != assignment["scope"]):
            raise PipelineError(f"initial assignment disagrees with planned task {task_key}")
        task_queue[task_key] = {
            "role": assignment["role"],
            "scope": assignment["scope"],
            "state": "active",
            "current_agent_id": agent_id,
            "updated_at": utc_now(),
        }
    mode = "explicit_verbose_override" if args.verbose_override else "continuous_low_noise"
    if args.verbose_override and not str(args.override_reason or "").strip():
        raise PipelineError("verbose supervision requires an explicit override reason")
    if args.max_subagents < 1:
        raise PipelineError("--max-subagents must be positive")
    if len(assignments) > args.max_subagents:
        raise PipelineError("initial roster exceeds --max-subagents")
    if args.max_subagents > DEFAULT_MAX_SUBAGENTS and len(str(args.capacity_override_reason or "").strip()) < 24:
        raise PipelineError("more than three subagents requires a concrete --capacity-override-reason")
    if args.max_replacements < 0:
        raise PipelineError("--max-replacements cannot be negative")
    session = seal(
        {
            "schema": SCHEMA,
            "session_id": args.session_id
            or "supervisor:" + hashlib.sha1(f"{args.supervisor_agent_id}|{utc_now()}".encode()).hexdigest()[:16],
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "closed_at": None,
            "supervisor_agent_id": args.supervisor_agent_id,
            "communication_mode": mode,
            "explicit_override_reason": args.override_reason if args.verbose_override else None,
            "reportable_event_types": sorted(REPORTABLE_EVENT_TYPES),
            "suppressed_event_types": sorted(ROUTINE_EVENT_TYPES),
            "event_log": args.event_log or "supervisor_events.jsonl",
            "roster_policy": "reuse_before_spawn",
            "max_subagents": args.max_subagents,
            "capacity_override_reason": args.capacity_override_reason,
            "max_replacements": args.max_replacements,
            "assignments": assignments,
            "task_queue": task_queue,
            "identity_history": sorted(assignments),
            "replacement_count": 0,
            "replacement_authorizations": {},
            "review_todos": {},
            "retired_identities": [],
            "acknowledged_event_ids": [],
        }
    )
    with locked_paths([output]):
        if output.exists():
            current = load_json_unlocked(output)
            validate_session(current)
            if not args.replace:
                raise PipelineError("supervisor session already exists; resume its roster instead of starting another")
            if not current.get("closed_at"):
                raise PipelineError("cannot replace an active supervisor session; reuse or explicitly replace one roster member")
            if len(str(args.replace_reason or "").strip()) < 24:
                raise PipelineError("restarting a closed supervisor session requires a concrete --replace-reason")
            session["restart_of_session_id"] = current.get("session_id")
            session["restart_reason"] = args.replace_reason
            session = seal(session)
        atomic_write_json_unlocked(output, session)
    print(json.dumps(status_payload(output, session), ensure_ascii=False, indent=2))
    return 0


def record(args: argparse.Namespace) -> int:
    session_path = Path(args.session).resolve()
    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        validate_session(session)
        if session.get("closed_at"):
            raise PipelineError("cannot append events to a closed supervisor session")
        if args.event_type not in REPORTABLE_EVENT_TYPES | ROUTINE_EVENT_TYPES:
            raise PipelineError("unknown supervisor event type")
        if args.agent_id and args.agent_id not in session["assignments"]:
            raise PipelineError("event agent id is outside the sealed supervisor assignment set")
        verbose = session["communication_mode"] == "explicit_verbose_override"
        user_visible = args.event_type in REPORTABLE_EVENT_TYPES or verbose
        event = {
            "schema": "lecture-animation-supervisor-event-v1",
            "event_id": args.event_id
            or "event:" + hashlib.sha1(
                f"{session['session_id']}|{args.event_type}|{args.agent_id}|{args.summary}|{utc_now()}".encode()
            ).hexdigest()[:16],
            "created_at": utc_now(),
            "session_id": session["session_id"],
            "event_type": args.event_type,
            "agent_id": args.agent_id,
            "scene_slug": args.scene_slug,
            "summary": args.summary,
            "artifact": args.artifact,
            "user_visible": user_visible,
            "delivery_disposition": "notify_user" if user_visible else "persist_only",
        }
        log_path = event_log_path(session_path, session)
        with locked_paths([log_path]):
            existing_ids = {row.get("event_id") for row in read_jsonl_unlocked(log_path)} if log_path.exists() else set()
            if event["event_id"] not in existing_ids:
                append_jsonl_unlocked(log_path, event)
        session["updated_at"] = utc_now()
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(event, ensure_ascii=False, indent=2))
    return 0


def set_assignment(args: argparse.Namespace) -> int:
    session_path = Path(args.session).resolve()
    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        validate_session(session)
        assignment = session["assignments"].get(args.agent_id)
        if assignment is None:
            raise PipelineError("assignment agent id is outside the sealed session")
        assignment["state"] = args.state
        assignment["updated_at"] = utc_now()
        assignment["note"] = args.note
        if session.get("schema") == SCHEMA:
            task = session.get("task_queue", {}).get(str(assignment.get("task_key")))
            if isinstance(task, dict) and args.state in {"active", "completed", "blocked", "cancelled"}:
                task["state"] = args.state
                task["current_agent_id"] = args.agent_id
                task["updated_at"] = utc_now()
        session["updated_at"] = utc_now()
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(status_payload(session_path, load_json(session_path)), ensure_ascii=False, indent=2))
    return 0


def open_review_todos_for_agent(
    session: dict[str, Any], agent_id: str
) -> list[dict[str, Any]]:
    return [
        todo
        for todo in session.get("review_todos", {}).values()
        if isinstance(todo, dict)
        and todo.get("agent_id") == agent_id
        and todo.get("state") in OPEN_REVIEW_TODO_STATES
    ]


def assign_task(args: argparse.Namespace) -> int:
    """Reuse one existing identity for its next bounded task."""
    session_path = Path(args.session).resolve()
    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        validate_session(session)
        require_v2(session)
        if session.get("closed_at"):
            raise PipelineError("cannot assign work in a closed supervisor session")
        assignment = session["assignments"].get(args.agent_id)
        if assignment is None:
            raise PipelineError("agent id is outside the sealed roster; replacement authorization is required")
        pending_review_todos = [
            todo
            for todo in open_review_todos_for_agent(session, args.agent_id)
            if todo.get("state") != "deferred_until_safe_checkpoint"
        ]
        if pending_review_todos:
            states = sorted({str(todo.get("state")) for todo in pending_review_todos})
            raise PipelineError(
                "agent has undelivered review todos "
                f"({', '.join(states)}); reach and seal the safe checkpoint, "
                "then deliver and acknowledge the review before assigning another task"
            )
        history = assignment.setdefault("assignment_history", [])
        task_key_was_used = any(
            str(item.get("task_key")) == args.task_key
            for item in history
            if isinstance(item, dict)
        )
        if task_key_was_used and assignment.get("state") not in REUSABLE_STATES:
            if (
                assignment.get("state") == "active"
                and str(assignment.get("task_key")) == args.task_key
                and assignment.get("role") == args.role
                and assignment.get("scope") == args.scope
            ):
                print(json.dumps(status_payload(session_path, session), ensure_ascii=False, indent=2))
                return 0
            raise PipelineError(
                "an active or blocked batch task cannot be reopened; finish the current cycle first"
            )
        if assignment.get("state") not in REUSABLE_STATES:
            raise PipelineError("agent must be idle or completed before it receives another task")
        if assignment.get("role") != args.role:
            raise PipelineError("reuse must preserve the roster role; replace the roster member only if the role is incompatible")
        task = session.get("task_queue", {}).get(args.task_key)
        if task_key_was_used:
            if len(str(args.new_task_reason or "").strip()) < 24:
                raise PipelineError(
                    "reopening a completed batch task requires a concrete --new-task-reason"
                )
            if not isinstance(task, dict):
                raise PipelineError("historical batch task is missing from the sealed task queue")
            if task.get("state") not in {"completed", "cancelled"}:
                active_holders = [
                    agent_id
                    for agent_id, candidate in session.get("assignments", {}).items()
                    if isinstance(candidate, dict)
                    and str(candidate.get("task_key")) == args.task_key
                    and candidate.get("state") in {"active", "blocked"}
                ]
                stale_same_owner = (
                    task.get("state") in {"active", "blocked"}
                    and task.get("current_agent_id") == args.agent_id
                    and not active_holders
                )
                if not stale_same_owner:
                    raise PipelineError(
                        "historical batch task must be completed or cancelled before it can be reopened"
                    )
                task["stale_state_reconciliation"] = {
                    "previous_state": task.get("state"),
                    "previous_agent_id": task.get("current_agent_id"),
                    "reason": args.new_task_reason,
                    "reconciled_at": utc_now(),
                }
            if task.get("role") != args.role:
                raise PipelineError("reopened batch task must preserve the sealed roster role")
            reopen_count = int(task.get("reopen_count", 0)) + 1
            task.update(
                {
                    "scope": args.scope,
                    "state": "pending",
                    "current_agent_id": None,
                    "reopen_count": reopen_count,
                    "reopened_reason": args.new_task_reason,
                    "updated_at": utc_now(),
                }
            )
        if task is None:
            if len(str(args.new_task_reason or "").strip()) < 24:
                raise PipelineError("task is outside the sealed queue; add a concrete --new-task-reason")
            task = {
                "role": args.role,
                "scope": args.scope,
                "state": "pending",
                "current_agent_id": None,
                "added_after_begin_reason": args.new_task_reason,
                "updated_at": utc_now(),
            }
            session["task_queue"][args.task_key] = task
        if task.get("state") != "pending":
            raise PipelineError("planned task must be pending before assignment")
        if task.get("role") != args.role or task.get("scope") != args.scope:
            raise PipelineError("assign-task role and scope must match the sealed task queue")
        now = utc_now()
        assignment.update(
            {
                "task_key": args.task_key,
                "scope": args.scope,
                "state": "active",
                "task_count": int(assignment.get("task_count", 1)) + 1,
                "reuse_count": int(assignment.get("reuse_count", 0)) + 1,
                "updated_at": now,
                "note": args.note,
            }
        )
        history.append(
            {
                "task_key": args.task_key,
                "scope": args.scope,
                "assigned_at": now,
                "kind": "batch_reopen" if task_key_was_used else "reuse",
                "note": args.note,
                **(
                    {"reopened_reason": args.new_task_reason}
                    if task_key_was_used
                    else {}
                ),
            }
        )
        task.update({"state": "active", "current_agent_id": args.agent_id, "updated_at": now})
        session["updated_at"] = now
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(status_payload(session_path, load_json(session_path)), ensure_ascii=False, indent=2))
    return 0


def queue_review_todo(args: argparse.Namespace) -> int:
    """Persist a review result without interrupting an active production scene."""
    session_path = Path(args.session).resolve()
    review_path = Path(args.review_artifact).expanduser().resolve()
    if not review_path.is_file():
        raise PipelineError(f"review artifact does not exist: {review_path}")
    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        validate_session(session)
        require_v2(session)
        if session.get("closed_at"):
            raise PipelineError("cannot queue review work in a closed supervisor session")
        assignment = session["assignments"].get(args.agent_id)
        if assignment is None:
            raise PipelineError("review todo agent id is outside the sealed roster")
        if assignment.get("state") != "active":
            raise PipelineError("review todo may be deferred only while the owner is actively producing")
        priority = args.priority
        if priority == "nonblocking":
            if not str(args.wait_for_scene_slug or "").strip():
                raise PipelineError(
                    "a nonblocking review todo requires --wait-for-scene-slug"
                )
            state = "deferred_until_safe_checkpoint"
        else:
            state = "interrupt_required"
        now = utc_now()
        todo_id = args.todo_id or "review-todo:" + hashlib.sha1(
            (
                f"{session['session_id']}|{args.agent_id}|"
                f"{args.reviewed_scene_slug}|{sha256_file(review_path)}|{now}"
            ).encode()
        ).hexdigest()[:16]
        existing = session.setdefault("review_todos", {}).get(todo_id)
        if existing is not None:
            raise PipelineError(f"review todo already exists: {todo_id}")
        todo = {
            "schema": "lecture-animation-supervisor-review-todo-v1",
            "todo_id": todo_id,
            "created_at": now,
            "updated_at": now,
            "agent_id": args.agent_id,
            "reviewed_scene_slug": args.reviewed_scene_slug,
            "wait_for_scene_slug": args.wait_for_scene_slug,
            "queued_during_task_key": assignment.get("task_key"),
            "priority": priority,
            "state": state,
            "summary": args.summary,
            "review_artifact": {
                "path": str(review_path),
                "sha256": sha256_file(review_path),
                "size": review_path.stat().st_size,
            },
            "safe_checkpoint": None,
            "delivered_at": None,
            "delivery_method": None,
            "delivery_note": None,
        }
        session["review_todos"][todo_id] = todo
        session["updated_at"] = now
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(todo, ensure_ascii=False, indent=2))
    return 0


def retarget_review_todo(args: argparse.Namespace) -> int:
    """Correct the awaited scene of an undelivered nonblocking review todo."""
    session_path = Path(args.session).resolve()
    reason = str(args.reason or "").strip()
    if len(reason) < 12:
        raise PipelineError("review todo retarget requires a concrete --reason")
    new_scene_slug = str(args.wait_for_scene_slug or "").strip()
    if not new_scene_slug:
        raise PipelineError("review todo retarget requires --wait-for-scene-slug")
    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        validate_session(session)
        require_v2(session)
        todo = session.get("review_todos", {}).get(args.todo_id)
        if not isinstance(todo, dict):
            raise PipelineError("review todo is missing")
        if todo.get("state") != "deferred_until_safe_checkpoint":
            raise PipelineError("only an undelivered deferred review todo may be retargeted")
        if todo.get("priority") != "nonblocking":
            raise PipelineError("only a nonblocking review todo may be retargeted")
        assignment = session["assignments"].get(todo.get("agent_id"))
        if assignment is None:
            raise PipelineError("review todo owner is outside the sealed roster")
        previous_scene_slug = str(todo.get("wait_for_scene_slug") or "").strip()
        if previous_scene_slug == new_scene_slug:
            raise PipelineError("review todo retarget must change the awaited scene")
        now = utc_now()
        todo.setdefault("retarget_history", []).append(
            {
                "previous_wait_for_scene_slug": previous_scene_slug,
                "new_wait_for_scene_slug": new_scene_slug,
                "reason": reason,
                "retargeted_at": now,
                "assignment_task_key": assignment.get("task_key"),
            }
        )
        todo["wait_for_scene_slug"] = new_scene_slug
        todo["updated_at"] = now
        session["updated_at"] = now
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(todo, ensure_ascii=False, indent=2))
    return 0


def release_review_todo_after_review_task(args: argparse.Namespace) -> int:
    """Release a deferred todo after its owner finishes a separate review task."""
    session_path = Path(args.session).resolve()
    evidence_path = Path(args.completion_evidence).expanduser().resolve()
    if not evidence_path.is_file():
        raise PipelineError(
            f"review-task completion evidence does not exist: {evidence_path}"
        )
    evidence = load_json(evidence_path)
    if evidence.get("schema") != "lecture-animation-review-v2":
        raise PipelineError(
            "review-task completion evidence must use lecture-animation-review-v2"
        )
    if evidence.get("verdict") not in {"pass", "revise"}:
        raise PipelineError("review-task completion evidence has no final verdict")
    if not str(evidence.get("manifest_hash", "")).strip():
        raise PipelineError("review-task completion evidence has no manifest hash")
    reason = str(args.reason or "").strip()
    if len(reason) < 12:
        raise PipelineError("review-task todo release requires a concrete --reason")

    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        validate_session(session)
        require_v2(session)
        todo = session.get("review_todos", {}).get(args.todo_id)
        if not isinstance(todo, dict):
            raise PipelineError("review todo is missing")
        if todo.get("state") != "deferred_until_safe_checkpoint":
            raise PipelineError("only an undelivered deferred review todo may be released")
        assignment = session["assignments"].get(todo.get("agent_id"))
        if assignment is None:
            raise PipelineError("review todo owner is outside the sealed roster")
        if assignment.get("state") not in {"idle", "completed"}:
            raise PipelineError(
                "review-task todo release requires an idle or completed owner"
            )
        if todo.get("queued_during_task_key") != assignment.get("task_key"):
            raise PipelineError(
                "review-task todo release requires the same completed task key"
            )
        if evidence.get("reviewer_agent_id") != todo.get("agent_id"):
            raise PipelineError(
                "review-task completion evidence reviewer does not match todo owner"
            )
        now = utc_now()
        todo["state"] = "ready_to_deliver"
        todo["safe_checkpoint"] = {
            "scene_slug": todo.get("wait_for_scene_slug"),
            "reached_at": now,
            "evidence_path": str(evidence_path),
            "evidence_sha256": sha256_file(evidence_path),
            "evidence_schema": "lecture-animation-review-v2",
            "evidence_hash": object_hash(evidence),
            "completed_review_task_key": assignment.get("task_key"),
            "release_reason": reason,
        }
        todo["updated_at"] = now
        session["updated_at"] = now
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(todo, ensure_ascii=False, indent=2))
    return 0


def release_review_todo_after_planning_task(args: argparse.Namespace) -> int:
    """Release a deferred todo after a non-authoring impact-plan task has stopped."""
    session_path = Path(args.session).resolve()
    evidence_path = Path(args.completion_evidence).expanduser().resolve()
    if not evidence_path.is_file():
        raise PipelineError(
            f"planning-task completion evidence does not exist: {evidence_path}"
        )
    evidence = load_json(evidence_path)
    if evidence.get("schema") != "lecture-animation-bounded-author-repair-impact-plan-v1":
        raise PipelineError(
            "planning-task completion evidence must use "
            "lecture-animation-bounded-author-repair-impact-plan-v1"
        )
    if evidence.get("state") != "awaiting_formal_repair_contract":
        raise PipelineError(
            "planning-task completion evidence must be awaiting_formal_repair_contract"
        )
    reason = str(args.reason or "").strip()
    if len(reason) < 12:
        raise PipelineError("planning-task todo release requires a concrete --reason")

    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        validate_session(session)
        require_v2(session)
        todo = session.get("review_todos", {}).get(args.todo_id)
        if not isinstance(todo, dict):
            raise PipelineError("review todo is missing")
        if todo.get("state") != "deferred_until_safe_checkpoint":
            raise PipelineError("only an undelivered deferred review todo may be released")
        assignment = session["assignments"].get(todo.get("agent_id"))
        if assignment is None:
            raise PipelineError("review todo owner is outside the sealed roster")
        if assignment.get("state") not in {"idle", "completed", "blocked"}:
            raise PipelineError(
                "planning-task todo release requires an idle, completed, or blocked owner"
            )
        history = assignment.get("assignment_history")
        if not isinstance(history, list) or not any(
            isinstance(row, dict)
            and row.get("task_key") == todo.get("queued_during_task_key")
            for row in history
        ):
            raise PipelineError(
                "planning-task todo release cannot prove the queued task in owner history"
            )
        if evidence.get("created_by") != todo.get("agent_id"):
            raise PipelineError(
                "planning-task completion evidence author does not match todo owner"
            )
        if evidence.get("scene_slug") != todo.get("wait_for_scene_slug"):
            raise PipelineError(
                "planning-task completion evidence scene does not match awaited scene"
            )
        now = utc_now()
        todo["state"] = "ready_to_deliver"
        todo["safe_checkpoint"] = {
            "scene_slug": todo.get("wait_for_scene_slug"),
            "reached_at": now,
            "evidence_path": str(evidence_path),
            "evidence_sha256": sha256_file(evidence_path),
            "evidence_schema": evidence.get("schema"),
            "evidence_hash": object_hash(evidence),
            "completed_planning_task_key": todo.get("queued_during_task_key"),
            "release_reason": reason,
        }
        todo["updated_at"] = now
        session["updated_at"] = now
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(todo, ensure_ascii=False, indent=2))
    return 0


def seal_animatic_checkpoint(args: argparse.Namespace) -> int:
    """Seal a low-cost animatic checkpoint without pretending it is a frozen candidate."""
    if not str(args.agent_id).strip() or not str(args.scene_slug).strip():
        raise PipelineError("animatic checkpoint requires agent id and scene slug")
    bindings = {
        "scene_plan": bound_file(Path(args.plan)),
        "profile": bound_file(Path(args.profile)),
        "animatic": bound_file(Path(args.animatic)),
        "authoring_qc": bound_file(Path(args.authoring_qc)),
        "contact_sheet": bound_file(Path(args.contact_sheet)),
    }
    authoring_qc = load_json(Path(bindings["authoring_qc"]["path"]))
    if authoring_qc.get("schema") != "lecture-animation-authoring-qc-report-v2":
        raise PipelineError(
            "animatic checkpoint authoring QC must use "
            "lecture-animation-authoring-qc-report-v2"
        )
    if authoring_qc.get("scene_slug") != args.scene_slug:
        raise PipelineError("animatic checkpoint authoring QC scene slug does not match")
    if authoring_qc.get("valid") is not True:
        raise PipelineError("animatic checkpoint requires valid authoring QC")
    if authoring_qc.get("issues"):
        raise PipelineError("animatic checkpoint authoring QC must have zero issues")
    report_hash = str(authoring_qc.get("report_hash", "")).strip()
    if not report_hash:
        raise PipelineError("animatic checkpoint authoring QC requires report_hash")

    payload = {
        "schema": "lecture-animation-animatic-author-checkpoint-v1",
        "agent_id": args.agent_id,
        "scene_slug": args.scene_slug,
        "verdict": "ready_for_independent_animatic_review",
        "sealed_at": utc_now(),
        "authoring_qc_report_hash": report_hash,
        "artifacts": bindings,
    }
    payload["checkpoint_hash"] = object_hash(payload)
    output = Path(args.output).expanduser().resolve()
    atomic_write_json_unlocked(output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def validate_safe_checkpoint_evidence(
    evidence: dict[str, Any],
    evidence_path: Path,
    agent_id: str,
    scene_slug: str,
) -> tuple[str, str]:
    """Validate either a formal candidate self-review or a low-cost animatic checkpoint."""
    schema = evidence.get("schema")
    if schema == "lecture-animation-author-self-review-v2":
        supplied_hash = str(evidence.get("self_review_hash", "")).strip()
        payload = dict(evidence)
        payload.pop("self_review_hash", None)
        if not supplied_hash or supplied_hash != object_hash(payload):
            raise PipelineError("safe checkpoint author self-review hash is invalid or stale")
        if evidence.get("verdict") != "ready_for_independent_review":
            raise PipelineError("safe checkpoint requires ready_for_independent_review")
        return schema, supplied_hash

    if schema != "lecture-animation-animatic-author-checkpoint-v1":
        raise PipelineError(
            "safe checkpoint evidence must be a sealed author self-review or "
            "lecture-animation-animatic-author-checkpoint-v1"
        )
    supplied_hash = str(evidence.get("checkpoint_hash", "")).strip()
    payload = dict(evidence)
    payload.pop("checkpoint_hash", None)
    if not supplied_hash or supplied_hash != object_hash(payload):
        raise PipelineError("safe checkpoint animatic checkpoint hash is invalid or stale")
    if evidence.get("verdict") != "ready_for_independent_animatic_review":
        raise PipelineError(
            "animatic safe checkpoint requires ready_for_independent_animatic_review"
        )
    if evidence.get("agent_id") != agent_id:
        raise PipelineError("animatic safe checkpoint agent id does not match")
    if evidence.get("scene_slug") != scene_slug:
        raise PipelineError("animatic safe checkpoint scene slug does not match")
    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, dict):
        raise PipelineError("animatic safe checkpoint artifacts are missing")
    required = {"scene_plan", "profile", "animatic", "authoring_qc", "contact_sheet"}
    if set(artifacts) != required:
        raise PipelineError("animatic safe checkpoint artifact set is incomplete")
    for label in sorted(required):
        validate_bound_file(artifacts[label], label)
    authoring_qc_path = Path(artifacts["authoring_qc"]["path"])
    authoring_qc = load_json(authoring_qc_path)
    if authoring_qc.get("valid") is not True or authoring_qc.get("issues"):
        raise PipelineError("animatic safe checkpoint authoring QC is no longer valid")
    if authoring_qc.get("scene_slug") != scene_slug:
        raise PipelineError("animatic safe checkpoint authoring QC scene slug is stale")
    if str(authoring_qc.get("report_hash", "")).strip() != str(
        evidence.get("authoring_qc_report_hash", "")
    ).strip():
        raise PipelineError("animatic safe checkpoint authoring QC report hash is stale")
    if sha256_file(evidence_path) == "":
        raise PipelineError("animatic safe checkpoint evidence cannot be empty")
    return schema, supplied_hash


def mark_safe_checkpoint(args: argparse.Namespace) -> int:
    """Release deferred review todos after sealed current-scene evidence."""
    session_path = Path(args.session).resolve()
    evidence_path = Path(args.evidence).expanduser().resolve()
    if not evidence_path.is_file():
        raise PipelineError(f"safe-checkpoint evidence does not exist: {evidence_path}")
    evidence = load_json(evidence_path)
    evidence_schema, evidence_hash = validate_safe_checkpoint_evidence(
        evidence,
        evidence_path,
        args.agent_id,
        args.scene_slug,
    )

    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        validate_session(session)
        require_v2(session)
        assignment = session["assignments"].get(args.agent_id)
        if assignment is None:
            raise PipelineError("safe checkpoint agent id is outside the sealed roster")
        matching = [
            todo
            for todo in session.get("review_todos", {}).values()
            if isinstance(todo, dict)
            and todo.get("agent_id") == args.agent_id
            and todo.get("state") == "deferred_until_safe_checkpoint"
            and todo.get("wait_for_scene_slug") == args.scene_slug
        ]
        if not matching:
            raise PipelineError(
                "no deferred review todo is waiting for this agent and scene checkpoint"
            )
        now = utc_now()
        checkpoint = {
            "scene_slug": args.scene_slug,
            "reached_at": now,
            "evidence_path": str(evidence_path),
            "evidence_sha256": sha256_file(evidence_path),
            "evidence_schema": evidence_schema,
            "evidence_hash": evidence_hash,
        }
        if evidence_schema == "lecture-animation-author-self-review-v2":
            checkpoint["self_review_hash"] = evidence_hash
        else:
            checkpoint["animatic_checkpoint_hash"] = evidence_hash
        for todo in matching:
            todo["state"] = "ready_to_deliver"
            todo["safe_checkpoint"] = checkpoint
            todo["updated_at"] = now
        session["updated_at"] = now
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(status_payload(session_path, load_json(session_path)), ensure_ascii=False, indent=2))
    return 0


def acknowledge_review_delivery(args: argparse.Namespace) -> int:
    """Record that the orchestrator actually sent one released review todo."""
    session_path = Path(args.session).resolve()
    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        validate_session(session)
        require_v2(session)
        todo = session.get("review_todos", {}).get(args.todo_id)
        if not isinstance(todo, dict):
            raise PipelineError("review todo is missing")
        if todo.get("state") not in {"ready_to_deliver", "interrupt_required"}:
            raise PipelineError(
                "only a released or blocking review todo may be acknowledged as delivered"
            )
        if len(str(args.delivery_note or "").strip()) < 12:
            raise PipelineError("review delivery requires a concrete --delivery-note")
        now = utc_now()
        todo.update(
            {
                "state": "delivered",
                "delivered_at": now,
                "updated_at": now,
                "delivery_method": args.delivery_method,
                "delivery_note": args.delivery_note,
            }
        )
        session["updated_at"] = now
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(todo, ensure_ascii=False, indent=2))
    return 0


def authorize_replacement(args: argparse.Namespace) -> int:
    """Authorize one exceptional new identity only after reuse has been ruled out."""
    session_path = Path(args.session).resolve()
    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        validate_session(session)
        require_v2(session)
        if session.get("closed_at"):
            raise PipelineError("cannot replace an agent in a closed supervisor session")
        old = session["assignments"].get(args.old_agent_id)
        if old is None:
            raise PipelineError("old agent id is outside the current roster")
        reusable = [
            agent_id
            for agent_id, item in session["assignments"].items()
            if agent_id != args.old_agent_id
            and item.get("role") == old.get("role")
            and item.get("state") in REUSABLE_STATES
        ]
        if reusable:
            raise PipelineError(
                "a compatible roster member is reusable; assign-task one of: " + ", ".join(sorted(reusable))
            )
        reason = args.reason
        availability_hash = None
        if reason in {"agent_unavailable", "task_tree_changed", "unrecoverable_failure"}:
            if not args.availability_snapshot:
                raise PipelineError(f"{reason} requires --availability-snapshot")
            snapshot = validate_availability_snapshot(Path(args.availability_snapshot), args.old_agent_id)
            availability_hash = snapshot.get("snapshot_hash")
        requested_model = str(args.new_model or old.get("model", "")).strip()
        if reason == "model_change_required":
            if not requested_model or requested_model == str(old.get("model", "")).strip():
                raise PipelineError("model_change_required needs --new-model different from the current model")
        replacement_count = int(session.get("replacement_count", 0) or 0)
        if replacement_count >= int(session.get("max_replacements", DEFAULT_MAX_REPLACEMENTS)):
            if len(str(args.budget_override_reason or "").strip()) < 24:
                raise PipelineError("replacement budget exhausted; a concrete --budget-override-reason is required")
        if len(str(args.evidence or "").strip()) < 24:
            raise PipelineError("replacement authorization requires concrete evidence")
        existing_pending = [
            key for key, row in session["replacement_authorizations"].items()
            if isinstance(row, dict) and row.get("status") == "authorized"
        ]
        if existing_pending:
            raise PipelineError("consume or cancel the pending replacement authorization first")
        now = utc_now()
        authorization_id = args.authorization_id or "replacement:" + hashlib.sha1(
            f"{session['session_id']}|{args.old_agent_id}|{reason}|{now}".encode()
        ).hexdigest()[:16]
        session["replacement_authorizations"][authorization_id] = {
            "authorization_id": authorization_id,
            "status": "authorized",
            "created_at": now,
            "old_agent_id": args.old_agent_id,
            "role": old.get("role"),
            "task_key": old.get("task_key"),
            "scope": old.get("scope"),
            "old_model": old.get("model"),
            "new_model": requested_model,
            "reason": reason,
            "evidence": args.evidence,
            "availability_snapshot_hash": availability_hash,
            "budget_override_reason": args.budget_override_reason,
        }
        session["updated_at"] = now
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(session["replacement_authorizations"][authorization_id], ensure_ascii=False, indent=2))
    return 0


def register_replacement(args: argparse.Namespace) -> int:
    session_path = Path(args.session).resolve()
    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        validate_session(session)
        require_v2(session)
        authorization = session["replacement_authorizations"].get(args.authorization_id)
        if not isinstance(authorization, dict) or authorization.get("status") != "authorized":
            raise PipelineError("replacement authorization is missing, stale, or already consumed")
        old_agent_id = str(authorization.get("old_agent_id"))
        old = session["assignments"].get(old_agent_id)
        if old is None:
            raise PipelineError("authorized old agent is no longer in the roster")
        if args.new_agent_id in session["assignments"] or args.new_agent_id in set(map(str, session["identity_history"])):
            raise PipelineError("new agent id is already known; use assign-task for a reusable identity")
        now = utc_now()
        old_snapshot = dict(old)
        old_snapshot.update({"agent_id": old_agent_id, "retired_at": now, "retirement_reason": authorization.get("reason")})
        session["retired_identities"].append(old_snapshot)
        del session["assignments"][old_agent_id]
        session["assignments"][args.new_agent_id] = {
            "role": authorization.get("role"),
            "task_key": authorization.get("task_key"),
            "scope": authorization.get("scope"),
            "model": authorization.get("new_model"),
            "state": "active",
            "task_count": 1,
            "reuse_count": 0,
            "replacement_of": old_agent_id,
            "assignment_history": [
                {
                    "task_key": authorization.get("task_key"),
                    "scope": authorization.get("scope"),
                    "assigned_at": now,
                    "kind": "replacement",
                    "authorization_id": args.authorization_id,
                }
            ],
            "updated_at": now,
        }
        session["identity_history"].append(args.new_agent_id)
        task = session.get("task_queue", {}).get(str(authorization.get("task_key")))
        if isinstance(task, dict):
            task["current_agent_id"] = args.new_agent_id
            task["updated_at"] = now
        for todo in session.get("review_todos", {}).values():
            if (
                isinstance(todo, dict)
                and todo.get("agent_id") == old_agent_id
                and todo.get("state") != "delivered"
            ):
                todo["agent_id"] = args.new_agent_id
                todo["updated_at"] = now
                todo["replacement_authorization_id"] = args.authorization_id
        session["replacement_count"] = int(session.get("replacement_count", 0)) + 1
        authorization["status"] = "consumed"
        authorization["consumed_at"] = now
        authorization["new_agent_id"] = args.new_agent_id
        session["updated_at"] = now
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(status_payload(session_path, load_json(session_path)), ensure_ascii=False, indent=2))
    return 0


def restore_original_identity(args: argparse.Namespace) -> int:
    """Restore a directly reusable original identity after a mistaken replacement."""
    session_path = Path(args.session).resolve()
    snapshot = load_availability_snapshot(Path(args.availability_snapshot))
    reusable = set(map(str, snapshot.get("reusable_agent_ids", [])))
    if args.original_agent_id not in reusable:
        raise PipelineError("original agent is not reusable in the fresh availability snapshot")
    followup = snapshot.get("followup_attempts", {}).get(args.original_agent_id)
    if not isinstance(followup, dict) or followup.get("outcome") != "restored":
        raise PipelineError("original identity restoration requires a sealed restored followup_task outcome")
    if args.replacement_agent_id in set(map(str, snapshot.get("live_agent_ids", []))):
        raise PipelineError("replacement agent is still live; interrupt it before restoring the original identity")
    if len(str(args.evidence or "").strip()) < 24:
        raise PipelineError("original-identity restoration requires concrete evidence")

    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        validate_session(session)
        require_v2(session)
        replacement = session["assignments"].get(args.replacement_agent_id)
        if replacement is None:
            raise PipelineError("replacement agent is outside the current roster")
        if replacement.get("replacement_of") != args.original_agent_id:
            raise PipelineError("replacement assignment is not bound to the requested original identity")
        retired_rows = session.get("retired_identities", [])
        original_index = next(
            (
                index
                for index, row in enumerate(retired_rows)
                if isinstance(row, dict) and row.get("agent_id") == args.original_agent_id
            ),
            None,
        )
        if original_index is None:
            raise PipelineError("retired original identity snapshot is missing")
        authorization_id = next(
            (
                key
                for key, row in session.get("replacement_authorizations", {}).items()
                if (
                    isinstance(row, dict)
                    and row.get("old_agent_id") == args.original_agent_id
                    and row.get("new_agent_id") == args.replacement_agent_id
                    and row.get("status") == "consumed"
                )
            ),
            None,
        )
        if authorization_id is None:
            raise PipelineError("consumed replacement authorization is missing")

        now = utc_now()
        original = dict(retired_rows.pop(original_index))
        original.pop("agent_id", None)
        original.pop("retired_at", None)
        original.pop("retirement_reason", None)
        original["state"] = "active"
        original["updated_at"] = now
        original.setdefault("assignment_history", []).append(
            {
                "task_key": original.get("task_key"),
                "scope": original.get("scope"),
                "assigned_at": now,
                "kind": "original_identity_restored",
                "reverted_authorization_id": authorization_id,
            }
        )

        replacement_snapshot = dict(replacement)
        replacement_snapshot.update(
            {
                "agent_id": args.replacement_agent_id,
                "state": "retired",
                "retired_at": now,
                "retirement_reason": "original_identity_directly_reusable",
            }
        )
        retired_rows.append(replacement_snapshot)
        del session["assignments"][args.replacement_agent_id]
        session["assignments"][args.original_agent_id] = original

        task = session.get("task_queue", {}).get(str(original.get("task_key")))
        if isinstance(task, dict) and task.get("current_agent_id") == args.replacement_agent_id:
            task["current_agent_id"] = args.original_agent_id
            task["updated_at"] = now
        for todo in session.get("review_todos", {}).values():
            if (
                isinstance(todo, dict)
                and todo.get("agent_id") == args.replacement_agent_id
                and todo.get("state") != "delivered"
            ):
                todo["agent_id"] = args.original_agent_id
                todo["updated_at"] = now
                todo["restored_original_agent_id"] = args.original_agent_id

        authorization = session["replacement_authorizations"][authorization_id]
        authorization["status"] = "reverted"
        authorization["reverted_at"] = now
        authorization["revert_evidence"] = args.evidence
        authorization["restore_availability_snapshot_hash"] = snapshot.get("snapshot_hash")
        session.setdefault("identity_restorations", []).append(
            {
                "restored_at": now,
                "original_agent_id": args.original_agent_id,
                "replacement_agent_id": args.replacement_agent_id,
                "authorization_id": authorization_id,
                "availability_snapshot_hash": snapshot.get("snapshot_hash"),
                "evidence": args.evidence,
            }
        )
        session["updated_at"] = now
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(status_payload(session_path, load_json(session_path)), ensure_ascii=False, indent=2))
    return 0


def cancel_replacement_authorization(args: argparse.Namespace) -> int:
    """Cancel an unused replacement authorization after the original identity is recovered."""
    session_path = Path(args.session).resolve()
    snapshot = load_availability_snapshot(Path(args.availability_snapshot))
    if len(str(args.evidence or "").strip()) < 24:
        raise PipelineError("replacement cancellation requires concrete evidence")
    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        validate_session(session)
        require_v2(session)
        authorization = session.get("replacement_authorizations", {}).get(args.authorization_id)
        if not isinstance(authorization, dict) or authorization.get("status") != "authorized":
            raise PipelineError("replacement authorization is missing, stale, or already consumed")
        old_agent_id = str(authorization.get("old_agent_id", ""))
        if old_agent_id not in set(map(str, snapshot.get("reusable_agent_ids", []))):
            raise PipelineError("authorized original agent is not reusable in the fresh availability snapshot")
        followup = snapshot.get("followup_attempts", {}).get(old_agent_id)
        if not isinstance(followup, dict) or followup.get("outcome") != "restored":
            raise PipelineError("replacement cancellation requires a sealed restored followup_task outcome")
        now = utc_now()
        authorization["status"] = "cancelled"
        authorization["cancelled_at"] = now
        authorization["cancel_evidence"] = args.evidence
        authorization["cancel_availability_snapshot_hash"] = snapshot.get("snapshot_hash")
        session["updated_at"] = now
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(status_payload(session_path, load_json(session_path)), ensure_ascii=False, indent=2))
    return 0


def acknowledge(args: argparse.Namespace) -> int:
    session_path = Path(args.session).resolve()
    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        validate_session(session)
        rows = read_jsonl(event_log_path(session_path, session))
        known = {row.get("event_id") for row in rows if row.get("user_visible")}
        unknown = sorted(set(args.event_id) - known)
        if unknown:
            raise PipelineError("cannot acknowledge unknown or suppressed events: " + ", ".join(unknown))
        acknowledged = set(map(str, session.get("acknowledged_event_ids", [])))
        acknowledged.update(args.event_id)
        session["acknowledged_event_ids"] = sorted(acknowledged)
        session["updated_at"] = utc_now()
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(status_payload(session_path, load_json(session_path)), ensure_ascii=False, indent=2))
    return 0


def status_payload(session_path: Path, session: dict[str, Any]) -> dict[str, Any]:
    validate_session(session)
    rows = read_jsonl(event_log_path(session_path, session)) if event_log_path(session_path, session).exists() else []
    acknowledged = set(map(str, session.get("acknowledged_event_ids", [])))
    pending = [row for row in rows if row.get("user_visible") and str(row.get("event_id")) not in acknowledged]
    active = [agent_id for agent_id, item in session["assignments"].items() if item.get("state") == "active"]
    blocked = [agent_id for agent_id, item in session["assignments"].items() if item.get("state") == "blocked"]
    reusable = [agent_id for agent_id, item in session["assignments"].items() if item.get("state") in REUSABLE_STATES]
    task_count = len(session.get("task_queue", {})) if session.get("schema") == SCHEMA else sum(
        int(item.get("task_count", 1) or 1) for item in session["assignments"].values()
    )
    reuse_count = sum(int(item.get("reuse_count", 0) or 0) for item in session["assignments"].values())
    if session.get("schema") == SCHEMA:
        reuse_count += sum(
            int(item.get("reuse_count", 0) or 0)
            for item in session.get("retired_identities", [])
            if isinstance(item, dict)
        )
    replacement_count = int(session.get("replacement_count", 0) or 0)
    task_queue = session.get("task_queue", {}) if session.get("schema") == SCHEMA else {}
    pending_tasks = sorted(
        key for key, row in task_queue.items() if isinstance(row, dict) and row.get("state") == "pending"
    )
    blocked_tasks = sorted(
        key for key, row in task_queue.items() if isinstance(row, dict) and row.get("state") == "blocked"
    )
    pending_authorizations = [
        key for key, row in session.get("replacement_authorizations", {}).items()
        if isinstance(row, dict) and row.get("status") == "authorized"
    ]
    review_todos = session.get("review_todos", {}) if session.get("schema") == SCHEMA else {}
    deferred_review_todos = sorted(
        key
        for key, row in review_todos.items()
        if isinstance(row, dict)
        and row.get("state") == "deferred_until_safe_checkpoint"
    )
    ready_review_todos = sorted(
        key
        for key, row in review_todos.items()
        if isinstance(row, dict) and row.get("state") == "ready_to_deliver"
    )
    interrupt_required_review_todos = sorted(
        key
        for key, row in review_todos.items()
        if isinstance(row, dict) and row.get("state") == "interrupt_required"
    )
    churn_ratio = replacement_count / max(1, task_count)
    warnings: list[str] = []
    replacement_budget = int(session.get("max_replacements", DEFAULT_MAX_REPLACEMENTS))
    active_replacement_count = sum(
        1
        for row in session.get("assignments", {}).values()
        if isinstance(row, dict) and row.get("replacement_of")
    )
    replacement_excess = max(0, active_replacement_count - replacement_budget)
    recorded_budget_overrides = sum(
        1
        for row in session.get("replacement_authorizations", {}).values()
        if (
            isinstance(row, dict)
            and row.get("status") == "consumed"
            and len(str(row.get("budget_override_reason", "")).strip()) >= 24
        )
    )
    if replacement_excess > recorded_budget_overrides:
        warnings.append("REPLACEMENT_BUDGET_EXCEEDED")
    active_churn_ratio = active_replacement_count / max(1, task_count)
    if active_churn_ratio > 0.25 and replacement_excess > recorded_budget_overrides:
        warnings.append("AGENT_IDENTITY_CHURN_ABNORMAL")
    if pending_authorizations and reusable:
        warnings.append("REUSABLE_AGENT_EXISTS_DURING_REPLACEMENT")
    return {
        "schema": "lecture-animation-supervisor-status-v1",
        "session_id": session["session_id"],
        "communication_mode": session["communication_mode"],
        "active_assignments": active,
        "blocked_assignments": blocked,
        "reusable_assignments": reusable,
        "pending_tasks": pending_tasks,
        "blocked_tasks": blocked_tasks,
        "deferred_review_todos": deferred_review_todos,
        "ready_review_todos": ready_review_todos,
        "interrupt_required_review_todos": interrupt_required_review_todos,
        "review_delivery_required": bool(
            ready_review_todos or interrupt_required_review_todos
        ),
        "should_continue_monitoring": bool(
            active
            or pending_tasks
            or blocked_tasks
            or deferred_review_todos
            or ready_review_todos
            or interrupt_required_review_todos
        ),
        "user_update_required": bool(pending),
        "pending_user_events": pending,
        "suppressed_event_count": sum(not bool(row.get("user_visible")) for row in rows),
        "roster_metrics": {
            "current_identity_count": len(session["assignments"]),
            "historical_identity_count": len(session.get("identity_history", session["assignments"])),
            "max_subagents": int(session.get("max_subagents", len(session["assignments"]))),
            "task_assignment_count": task_count,
            "reuse_count": reuse_count,
            "replacement_count": replacement_count,
            "active_replacement_count": active_replacement_count,
            "identity_churn_ratio": round(churn_ratio, 4),
            "pending_replacement_authorizations": pending_authorizations,
        },
        "roster_warnings": warnings,
        "roster_clean": not warnings and not pending_authorizations,
        "may_finish": not active
        and not blocked
        and not pending_tasks
        and not blocked_tasks
        and not pending
        and not pending_authorizations
        and not deferred_review_todos
        and not ready_review_todos
        and not interrupt_required_review_todos,
    }


def status(args: argparse.Namespace) -> int:
    session_path = Path(args.session).resolve()
    payload = status_payload(session_path, load_json(session_path))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.require_clean and not payload["roster_clean"]:
        return 2
    return 0


def finish(args: argparse.Namespace) -> int:
    session_path = Path(args.session).resolve()
    with locked_paths([session_path]):
        session = load_json_unlocked(session_path)
        payload = status_payload(session_path, session)
        if payload["active_assignments"]:
            raise PipelineError("cannot finish supervision while assignments remain active")
        if payload["blocked_assignments"]:
            raise PipelineError("cannot finish supervision while assignments remain blocked")
        if payload["pending_tasks"]:
            raise PipelineError("cannot finish supervision while planned tasks remain pending")
        if payload["blocked_tasks"]:
            raise PipelineError("cannot finish supervision while planned tasks remain blocked")
        if payload["pending_user_events"]:
            raise PipelineError("cannot finish supervision before reportable milestones are acknowledged")
        if (
            payload["deferred_review_todos"]
            or payload["ready_review_todos"]
            or payload["interrupt_required_review_todos"]
        ):
            raise PipelineError(
                "cannot finish supervision with undelivered review todos"
            )
        if payload["roster_metrics"]["pending_replacement_authorizations"]:
            raise PipelineError("cannot finish supervision with an unused replacement authorization")
        session["closed_at"] = utc_now()
        session["updated_at"] = utc_now()
        atomic_write_json_unlocked(session_path, seal(session))
    print(json.dumps(status_payload(session_path, load_json(session_path)), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    begin_parser = commands.add_parser("begin")
    begin_parser.add_argument("--supervisor-agent-id", required=True)
    begin_parser.add_argument(
        "--assignment", action="append", required=True, help="AGENT_ID|ROLE|TASK_KEY|SCOPE|MODEL"
    )
    begin_parser.add_argument(
        "--planned-task", action="append", default=[], help="TASK_KEY|ROLE|SCOPE; include the remaining sealed queue"
    )
    begin_parser.add_argument("--session-id")
    begin_parser.add_argument("--event-log")
    begin_parser.add_argument("--max-subagents", type=int, default=DEFAULT_MAX_SUBAGENTS)
    begin_parser.add_argument("--capacity-override-reason")
    begin_parser.add_argument("--max-replacements", type=int, default=DEFAULT_MAX_REPLACEMENTS)
    begin_parser.add_argument("--verbose-override", action="store_true")
    begin_parser.add_argument("--override-reason")
    begin_parser.add_argument("--replace", action="store_true")
    begin_parser.add_argument("--replace-reason")
    begin_parser.add_argument("--output", required=True)
    begin_parser.set_defaults(func=begin)

    availability_parser = commands.add_parser(
        "seal-availability-snapshot",
        help="seal collaboration.list_agents state plus direct followup_task outcomes",
    )
    availability_parser.add_argument("--live-agent-id", action="append", default=[])
    availability_parser.add_argument("--reusable-agent-id", action="append", default=[])
    availability_parser.add_argument(
        "--followup-attempt",
        action="append",
        default=[],
        help="AGENT_ID|OUTCOME|EVIDENCE",
    )
    availability_parser.add_argument("--output", required=True)
    availability_parser.set_defaults(func=seal_availability_snapshot)

    record_parser = commands.add_parser("record")
    record_parser.add_argument("--session", required=True)
    record_parser.add_argument("--event-type", required=True)
    record_parser.add_argument("--agent-id")
    record_parser.add_argument("--scene-slug")
    record_parser.add_argument("--summary", required=True)
    record_parser.add_argument("--artifact")
    record_parser.add_argument("--event-id")
    record_parser.set_defaults(func=record)

    assignment_parser = commands.add_parser("set-assignment")
    assignment_parser.add_argument("--session", required=True)
    assignment_parser.add_argument("--agent-id", required=True)
    assignment_parser.add_argument("--state", choices=sorted(ASSIGNMENT_STATES), required=True)
    assignment_parser.add_argument("--note")
    assignment_parser.set_defaults(func=set_assignment)

    reuse_parser = commands.add_parser("assign-task", help="reuse an idle roster identity for another bounded task")
    reuse_parser.add_argument("--session", required=True)
    reuse_parser.add_argument("--agent-id", required=True)
    reuse_parser.add_argument("--role", required=True)
    reuse_parser.add_argument("--task-key", required=True)
    reuse_parser.add_argument("--scope", required=True)
    reuse_parser.add_argument("--note")
    reuse_parser.add_argument("--new-task-reason")
    reuse_parser.set_defaults(func=assign_task)

    review_todo_parser = commands.add_parser(
        "queue-review-todo",
        help="persist an independent-review result and defer nonblocking delivery",
    )
    review_todo_parser.add_argument("--session", required=True)
    review_todo_parser.add_argument("--agent-id", required=True)
    review_todo_parser.add_argument("--reviewed-scene-slug", required=True)
    review_todo_parser.add_argument("--wait-for-scene-slug")
    review_todo_parser.add_argument(
        "--priority", choices=sorted(REVIEW_TODO_PRIORITIES), required=True
    )
    review_todo_parser.add_argument("--review-artifact", required=True)
    review_todo_parser.add_argument("--summary", required=True)
    review_todo_parser.add_argument("--todo-id")
    review_todo_parser.set_defaults(func=queue_review_todo)

    retarget_review_todo_parser = commands.add_parser(
        "retarget-review-todo",
        help=(
            "correct the awaited scene of an undelivered nonblocking review todo "
            "without releasing it"
        ),
    )
    retarget_review_todo_parser.add_argument("--session", required=True)
    retarget_review_todo_parser.add_argument("--todo-id", required=True)
    retarget_review_todo_parser.add_argument("--wait-for-scene-slug", required=True)
    retarget_review_todo_parser.add_argument("--reason", required=True)
    retarget_review_todo_parser.set_defaults(func=retarget_review_todo)

    release_after_review_parser = commands.add_parser(
        "release-review-todo-after-review-task",
        help=(
            "release a deferred todo only after its owner is idle and a separate "
            "independent-review task has final hash-bound evidence"
        ),
    )
    release_after_review_parser.add_argument("--session", required=True)
    release_after_review_parser.add_argument("--todo-id", required=True)
    release_after_review_parser.add_argument("--completion-evidence", required=True)
    release_after_review_parser.add_argument("--reason", required=True)
    release_after_review_parser.set_defaults(func=release_review_todo_after_review_task)

    release_after_planning_parser = commands.add_parser(
        "release-review-todo-after-planning-task",
        help=(
            "release a deferred todo only after an impact-plan owner has stopped "
            "and exact non-authoring completion evidence is bound"
        ),
    )
    release_after_planning_parser.add_argument("--session", required=True)
    release_after_planning_parser.add_argument("--todo-id", required=True)
    release_after_planning_parser.add_argument("--completion-evidence", required=True)
    release_after_planning_parser.add_argument("--reason", required=True)
    release_after_planning_parser.set_defaults(
        func=release_review_todo_after_planning_task
    )

    animatic_checkpoint_parser = commands.add_parser(
        "seal-animatic-checkpoint",
        help=(
            "seal a hash-bound low-cost animatic checkpoint without candidate freeze"
        ),
    )
    animatic_checkpoint_parser.add_argument("--agent-id", required=True)
    animatic_checkpoint_parser.add_argument("--scene-slug", required=True)
    animatic_checkpoint_parser.add_argument("--plan", required=True)
    animatic_checkpoint_parser.add_argument("--profile", required=True)
    animatic_checkpoint_parser.add_argument("--animatic", required=True)
    animatic_checkpoint_parser.add_argument("--authoring-qc", required=True)
    animatic_checkpoint_parser.add_argument("--contact-sheet", required=True)
    animatic_checkpoint_parser.add_argument("--output", required=True)
    animatic_checkpoint_parser.set_defaults(func=seal_animatic_checkpoint)

    checkpoint_parser = commands.add_parser(
        "mark-safe-checkpoint",
        help=(
            "release deferred review todos after a sealed current-scene "
            "self-review or animatic checkpoint"
        ),
    )
    checkpoint_parser.add_argument("--session", required=True)
    checkpoint_parser.add_argument("--agent-id", required=True)
    checkpoint_parser.add_argument("--scene-slug", required=True)
    checkpoint_parser.add_argument("--evidence", required=True)
    checkpoint_parser.set_defaults(func=mark_safe_checkpoint)

    delivery_parser = commands.add_parser(
        "acknowledge-review-delivery",
        help="record that a released review todo was sent to its production owner",
    )
    delivery_parser.add_argument("--session", required=True)
    delivery_parser.add_argument("--todo-id", required=True)
    delivery_parser.add_argument(
        "--delivery-method",
        choices=["followup_task", "send_message", "other"],
        default="followup_task",
    )
    delivery_parser.add_argument("--delivery-note", required=True)
    delivery_parser.set_defaults(func=acknowledge_review_delivery)

    authorize_parser = commands.add_parser(
        "authorize-replacement",
        help="authorize one exceptional new identity after ruling out followup reuse",
    )
    authorize_parser.add_argument("--session", required=True)
    authorize_parser.add_argument("--old-agent-id", required=True)
    authorize_parser.add_argument("--reason", choices=sorted(REPLACEMENT_REASONS), required=True)
    authorize_parser.add_argument("--new-model")
    authorize_parser.add_argument("--availability-snapshot")
    authorize_parser.add_argument("--evidence", required=True)
    authorize_parser.add_argument("--budget-override-reason")
    authorize_parser.add_argument("--authorization-id")
    authorize_parser.set_defaults(func=authorize_replacement)

    register_parser = commands.add_parser(
        "register-replacement",
        help="consume a replacement authorization after the exceptional agent is spawned",
    )
    register_parser.add_argument("--session", required=True)
    register_parser.add_argument("--authorization-id", required=True)
    register_parser.add_argument("--new-agent-id", required=True)
    register_parser.set_defaults(func=register_replacement)

    restore_parser = commands.add_parser(
        "restore-original-identity",
        help="restore a directly reusable original identity after a mistaken replacement",
    )
    restore_parser.add_argument("--session", required=True)
    restore_parser.add_argument("--original-agent-id", required=True)
    restore_parser.add_argument("--replacement-agent-id", required=True)
    restore_parser.add_argument("--availability-snapshot", required=True)
    restore_parser.add_argument("--evidence", required=True)
    restore_parser.set_defaults(func=restore_original_identity)

    cancel_replacement_parser = commands.add_parser(
        "cancel-replacement-authorization",
        help="cancel an unused replacement authorization after the original identity is recovered",
    )
    cancel_replacement_parser.add_argument("--session", required=True)
    cancel_replacement_parser.add_argument("--authorization-id", required=True)
    cancel_replacement_parser.add_argument("--availability-snapshot", required=True)
    cancel_replacement_parser.add_argument("--evidence", required=True)
    cancel_replacement_parser.set_defaults(func=cancel_replacement_authorization)

    acknowledge_parser = commands.add_parser("acknowledge")
    acknowledge_parser.add_argument("--session", required=True)
    acknowledge_parser.add_argument("--event-id", action="append", required=True)
    acknowledge_parser.set_defaults(func=acknowledge)

    status_parser = commands.add_parser("status")
    status_parser.add_argument("--session", required=True)
    status_parser.add_argument("--require-clean", action="store_true")
    status_parser.set_defaults(func=status)

    finish_parser = commands.add_parser("finish")
    finish_parser.add_argument("--session", required=True)
    finish_parser.set_defaults(func=finish)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except PipelineError as exc:
        raise SystemExit(f"supervisor gate failed: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
