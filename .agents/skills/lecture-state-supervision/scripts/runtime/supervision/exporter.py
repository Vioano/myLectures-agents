"""Freeze portable, reviewable evidence without exposing mutable SQLite internals."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .core import canonical_json, file_hash, object_hash
from .store import EpisodeStore


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(canonical_json(row) + "\n" for row in rows)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _seconds_between(start: Any, end: Any) -> float | None:
    start_time = _parse_time(start)
    end_time = _parse_time(end)
    if start_time is None or end_time is None:
        return None
    return round(max(0.0, (end_time - start_time).total_seconds()), 3)


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return round(float(ordered[index]), 3)


def _max_lease_concurrency(events: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    """Measure actual overlapping author ownership, not graph fan-out."""

    open_intervals: dict[str, dict[str, Any]] = {}
    intervals: list[dict[str, Any]] = []
    terminal_events = {
        "LeaseReleased",
        "LeaseReleasedBySupervisor",
        "LeaseReleasedByRecovery",
        "LeaseRevoked",
        "LeaseRevokedByContextOverride",
        "LeaseRevokedByReferenceRebind",
        "LeaseRevokedByRouteSwitch",
        "LeaseRevokedByValidatorRebind",
        "LeaseExpired",
    }
    for event in events:
        lease_id = str(event.get("aggregate_id") or "")
        event_type = event.get("event_type")
        if event_type in {"LeaseGranted", "LeaseReclaimed"}:
            if lease_id in open_intervals:
                prior = open_intervals.pop(lease_id)
                prior["ended_at"] = event.get("occurred_at")
                prior["duration_seconds"] = _seconds_between(
                    prior.get("started_at"), prior.get("ended_at")
                )
                intervals.append(prior)
            state = event.get("state_after") or {}
            open_intervals[lease_id] = {
                "lease_id": lease_id,
                "task_id": state.get("task_id") or (event.get("payload") or {}).get("task_id"),
                "owner": state.get("owner") or (event.get("payload") or {}).get("owner"),
                "generation": state.get("generation"),
                "started_at": event.get("occurred_at"),
                "ended_at": None,
                "duration_seconds": None,
            }
        elif event_type in terminal_events and lease_id in open_intervals:
            interval = open_intervals.pop(lease_id)
            interval["ended_at"] = event.get("occurred_at")
            interval["duration_seconds"] = _seconds_between(
                interval.get("started_at"), interval.get("ended_at")
            )
            intervals.append(interval)
    intervals.extend(open_intervals.values())

    boundaries: list[tuple[datetime, int]] = []
    for interval in intervals:
        start = _parse_time(interval.get("started_at"))
        end = _parse_time(interval.get("ended_at"))
        if start is None:
            continue
        boundaries.append((start, 1))
        if end is not None:
            boundaries.append((end, -1))
    # End before start at the same timestamp so adjacent leases do not look concurrent.
    active = 0
    maximum = 0
    for _, delta in sorted(boundaries, key=lambda item: (item[0], item[1])):
        active += delta
        maximum = max(maximum, active)
    return maximum, intervals


def _capsule_delivery_latency(
    annotations: list[dict[str, Any]], capsules: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    serialized_capsules = [
        (item, canonical_json(item.get("payload") or {})) for item in capsules
    ]
    deliveries: list[dict[str, Any]] = []
    undelivered: list[str] = []
    for annotation in annotations:
        annotation_id = str(annotation.get("annotation_id") or "")
        if not annotation_id:
            continue
        delivered = next(
            (
                capsule
                for capsule, serialized in serialized_capsules
                if annotation_id in serialized
                and (
                    _parse_time(capsule.get("created_at")) is None
                    or _parse_time(annotation.get("created_at")) is None
                    or _parse_time(capsule.get("created_at"))
                    >= _parse_time(annotation.get("created_at"))
                )
            ),
            None,
        )
        if delivered is None:
            undelivered.append(annotation_id)
            continue
        deliveries.append(
            {
                "annotation_id": annotation_id,
                "producer_task_id": annotation.get("producer_task_id"),
                "delivery_policy": annotation.get("delivery_policy"),
                "capsule_id": delivered.get("capsule_id"),
                "delivered_at": delivered.get("created_at"),
                "latency_seconds": _seconds_between(
                    annotation.get("created_at"), delivered.get("created_at")
                ),
            }
        )
    return deliveries, undelivered


def export_episode(store: EpisodeStore, output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    integrity = store.verify_integrity()
    if not integrity["ok"]:
        return {
            "ok": False,
            "status": "denied",
            "code": "export_integrity_failure",
            "message": "event/projection integrity must pass before freezing an evidence bundle",
            "failed_invariant": "freeze_only_verified_state",
            "details": integrity,
        }
    with store.reader() as connection:
        aggregates = [
            {
                "aggregate_type": row["aggregate_type"],
                "aggregate_id": row["aggregate_id"],
                "version": row["version"],
                "state": json.loads(row["state_json"]),
                "state_hash": row["state_hash"],
                "updated_seq": row["updated_seq"],
                "updated_at": row["updated_at"],
            }
            for row in connection.execute(
                "SELECT * FROM aggregates ORDER BY aggregate_type, aggregate_id"
            )
        ]
        events = [
            {
                "seq": row["seq"],
                "event_id": row["event_id"],
                "request_id": row["request_id"],
                "ordinal": row["ordinal"],
                "aggregate_type": row["aggregate_type"],
                "aggregate_id": row["aggregate_id"],
                "aggregate_version": row["aggregate_version"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload_json"]),
                "state_after": json.loads(row["state_after_json"]),
                "state_hash": row["state_hash"],
                "actor": row["actor"],
                "occurred_at": row["occurred_at"],
            }
            for row in connection.execute("SELECT * FROM events ORDER BY seq")
        ]
        commands = [
            {
                "request_id": row["request_id"],
                "command_name": row["command_name"],
                "actor": row["actor"],
                "payload_hash": row["payload_hash"],
                "status": row["status"],
                "result": json.loads(row["result_json"]),
                "created_at": row["created_at"],
                "completed_at": row["completed_at"],
            }
            for row in connection.execute("SELECT * FROM commands ORDER BY created_at, request_id")
        ]
        capsules = [
            {
                "capsule_id": row["capsule_id"],
                "capsule_hash": row["capsule_hash"],
                "task_id": row["task_id"],
                "task_version": row["task_version"],
                "payload": json.loads(row["payload_json"]),
                "created_seq": row["created_seq"],
                "created_at": row["created_at"],
            }
            for row in connection.execute("SELECT * FROM capsules ORDER BY created_seq")
        ]
    event_counts = Counter(str(event["event_type"]) for event in events)
    command_counts = Counter(str(command["command_name"]) for command in commands)
    denials = Counter(
        str(command["result"].get("code", "unknown"))
        for command in commands
        if command["status"] == "denied"
    )
    commands_by_actor: dict[str, Counter[str]] = defaultdict(Counter)
    denials_by_actor: dict[str, Counter[str]] = defaultdict(Counter)
    for command in commands:
        actor = str(command.get("actor") or "unknown")
        commands_by_actor[actor][str(command["command_name"])] += 1
        if command["status"] == "denied":
            denials_by_actor[actor][str(command["result"].get("code", "unknown"))] += 1

    task_states = [item["state"] for item in aggregates if item["aggregate_type"] == "task"]
    review_states = [item["state"] for item in aggregates if item["aggregate_type"] == "review"]
    annotation_states = [
        item["state"] for item in aggregates if item["aggregate_type"] == "annotation"
    ]
    gap_states = [item["state"] for item in aggregates if item["aggregate_type"] == "gap"]
    feedback_states = [item["state"] for item in aggregates if item["aggregate_type"] == "feedback"]
    change_states = [item["state"] for item in aggregates if item["aggregate_type"] == "change"]
    observation_states = [
        item["state"] for item in aggregates if item["aggregate_type"] == "observation"
    ]
    agent_states = [item["state"] for item in aggregates if item["aggregate_type"] == "agent"]
    reservation_states = [
        item["state"]
        for item in aggregates
        if item["aggregate_type"] == "dispatch_reservation"
    ]

    events_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("aggregate_type") == "task":
            events_by_task[str(event.get("aggregate_id"))].append(event)
    task_lifecycle: dict[str, dict[str, Any]] = {}
    observed_queue_waits: list[float] = []
    observed_cycles: list[float] = []
    for task in task_states:
        task_id = str(task.get("task_id"))
        task_events = events_by_task.get(task_id, [])

        def first_time(*event_types: str) -> str | None:
            return next(
                (
                    str(event.get("occurred_at"))
                    for event in task_events
                    if event.get("event_type") in event_types
                ),
                None,
            )

        created_at = first_time("TaskAdded", "ReplacementRouteTaskAdded") or task.get("created_at")
        began_at = first_time("TaskBegan", "TaskReclaimed")
        submitted_at = first_time("TaskSubmitted")
        review_ready_at = first_time("TaskAwaitingHumanReview", "TaskApproved")
        approved_at = first_time("TaskApproved", "TaskHumanApproved")
        queue_wait = _seconds_between(created_at, began_at)
        cycle_seconds = _seconds_between(created_at, approved_at)
        if queue_wait is not None:
            observed_queue_waits.append(queue_wait)
        if cycle_seconds is not None:
            observed_cycles.append(cycle_seconds)
        usage = task.get("resource_usage") or {}
        task_lifecycle[task_id] = {
            "status": task.get("status"),
            "author": task.get("author"),
            "created_at": created_at,
            "first_begin_at": began_at,
            "first_submit_at": submitted_at,
            "first_review_ready_at": review_ready_at,
            "first_approved_at": approved_at,
            "queue_wait_seconds": queue_wait,
            "cycle_to_approval_seconds": cycle_seconds,
            "active_seconds": round(float(task.get("active_seconds", 0.0)), 3),
            "attempts": int(task.get("attempt", 0)),
            "input_tokens": int(usage.get("input_tokens", 0)),
            "output_tokens": int(usage.get("output_tokens", 0)),
            "reasoning_tokens": int(usage.get("reasoning_tokens", 0)),
            "tokens_without_progress": int(task.get("tokens_without_progress", 0)),
        }

    max_concurrent_leases, lease_intervals = _max_lease_concurrency(events)
    deliveries, undelivered_annotations = _capsule_delivery_latency(
        annotation_states, capsules
    )
    delivery_latencies = [
        float(item["latency_seconds"])
        for item in deliveries
        if item.get("latency_seconds") is not None
    ]
    capsule_chars = [
        int(item["payload"].get("context_budget", {}).get("used_chars", 0))
        for item in capsules
    ]
    review_counts = Counter(str(review.get("verdict") or "unknown") for review in review_states)
    reviews_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for review in review_states:
        reviews_by_task[str(review.get("task_id") or "unknown")].append(review)
    first_review_pass_count = sum(
        1
        for task_reviews in reviews_by_task.values()
        if sorted(task_reviews, key=lambda item: str(item.get("created_at") or ""))[0].get("verdict")
        == "pass"
    )
    gap_waits = [
        value
        for value in (
            _seconds_between(gap.get("created_at"), gap.get("resolved_at"))
            for gap in gap_states
            if gap.get("status") == "resolved"
        )
        if value is not None
    ]
    media_annotations = [
        item for item in annotation_states if (item.get("location") or {}).get("kind") == "media"
    ]
    total_tokens = {
        field: sum(
            int((task.get("resource_usage") or {}).get(field, 0)) for task in task_states
        )
        for field in ("input_tokens", "output_tokens", "reasoning_tokens")
    }
    unknown_metrics = [
        "approved_media_minutes",
        "human_active_review_minutes",
        "human_minutes_per_approved_media_minute",
        "tokens_per_approved_media_minute",
        "media_seek_latency_and_playback_stalls",
        "frontend_disconnect_and_reconnect_latency",
        "model_name_and_reasoning_effort_per_agent",
    ]
    metrics = {
        "schema": "lecture-state-supervision-export-metrics-v1",
        "cursor": integrity["cursor"],
        "event_count": len(events),
        "event_counts": dict(sorted(event_counts.items())),
        "command_count": len(commands),
        "command_counts": dict(sorted(command_counts.items())),
        "denial_counts": dict(sorted(denials.items())),
        "capsule_count": len(capsules),
        "capsule_context_chars": sum(capsule_chars),
        "task_active_seconds": {
            task["task_id"]: float(task.get("active_seconds", 0.0)) for task in task_states
        },
        "task_attempts": {task["task_id"]: int(task.get("attempt", 0)) for task in task_states},
        "supervision_stop_count": sum(1 for task in task_states if task.get("supervision_stop")),
        "observation_count": len(observation_states),
        "time_and_flow": {
            "task_lifecycle": task_lifecycle,
            "observed_queue_wait_seconds_total": round(sum(observed_queue_waits), 3),
            "observed_queue_wait_seconds_p50": _percentile(observed_queue_waits, 0.5),
            "observed_queue_wait_seconds_p95": _percentile(observed_queue_waits, 0.95),
            "observed_cycle_to_approval_seconds_p50": _percentile(observed_cycles, 0.5),
            "observed_cycle_to_approval_seconds_p95": _percentile(observed_cycles, 0.95),
            "task_active_seconds_total": round(
                sum(float(task.get("active_seconds", 0.0)) for task in task_states), 3
            ),
            "gap_wait_seconds_total": round(sum(gap_waits), 3),
            "gap_wait_seconds_p95": _percentile(gap_waits, 0.95),
        },
        "parallel_dispatch": {
            "max_concurrent_live_leases": max_concurrent_leases,
            "lease_intervals": lease_intervals,
            "reservation_count": len(reservation_states),
            "reservation_status_counts": dict(
                sorted(Counter(str(item.get("status") or "unknown") for item in reservation_states).items())
            ),
            "registered_agent_count": len(agent_states),
            "agent_presence_counts": dict(
                sorted(Counter(str(item.get("presence") or "unknown") for item in agent_states).items())
            ),
        },
        "agent_activity": {
            "commands_by_actor": {
                actor: dict(sorted(counts.items()))
                for actor, counts in sorted(commands_by_actor.items())
            },
            "denials_by_actor": {
                actor: dict(sorted(counts.items()))
                for actor, counts in sorted(denials_by_actor.items())
            },
            "resource_usage": total_tokens,
            "tokens_without_progress": sum(
                int(task.get("tokens_without_progress", 0)) for task in task_states
            ),
        },
        "human_activity": {
            "annotation_count": len(annotation_states),
            "annotation_severity_counts": dict(
                sorted(Counter(str(item.get("severity") or "unknown") for item in annotation_states).items())
            ),
            "human_decision_count": event_counts["TaskHumanApproved"]
            + event_counts["TaskHumanRevisionRequested"]
            + event_counts["TaskHumanApprovalReversed"],
            "approval_reversal_count": event_counts["TaskHumanApprovalReversed"],
            "human_gap_resolution_count": sum(
                1 for gap in gap_states if gap.get("requires_human") and gap.get("status") == "resolved"
            ),
            "feedback_rule_count": len(feedback_states),
            "observation_category_counts": dict(
                sorted(
                    Counter(
                        str(item.get("category") or "unknown")
                        for item in observation_states
                    ).items()
                )
            ),
            "human_intent_routing_count": sum(
                1
                for item in observation_states
                if item.get("category") == "human_intent_routing"
            ),
        },
        "attention_delivery": {
            "capsule_context_chars_average": (
                round(sum(capsule_chars) / len(capsule_chars), 3) if capsule_chars else None
            ),
            "capsule_context_chars_p50": _percentile([float(value) for value in capsule_chars], 0.5),
            "capsule_context_chars_p95": _percentile([float(value) for value in capsule_chars], 0.95),
            "annotation_deliveries": deliveries,
            "annotation_delivery_latency_seconds_p50": _percentile(delivery_latencies, 0.5),
            "annotation_delivery_latency_seconds_p95": _percentile(delivery_latencies, 0.95),
            "undelivered_annotation_ids_at_freeze": undelivered_annotations,
            "contract_conflict_count": event_counts["ContractConflictDetected"],
            "gap_resolution_override_count": event_counts[
                "ContextOverrideAddedFromGapResolution"
            ],
        },
        "quality_and_rework": {
            "review_count": len(review_states),
            "review_verdict_counts": dict(sorted(review_counts.items())),
            "first_review_pass_count": first_review_pass_count,
            "reviewed_task_count": len(reviews_by_task),
            "first_review_pass_ratio": (
                round(first_review_pass_count / len(reviews_by_task), 6)
                if reviews_by_task
                else None
            ),
            "tasks_with_multiple_attempts": sum(
                1 for task in task_states if int(task.get("attempt", 0)) > 1
            ),
            "human_revision_count": event_counts["TaskHumanRevisionRequested"],
        },
        "change_and_recovery": {
            "change_count": len(change_states),
            "route_switch_count": event_counts["RouteSwitchRecorded"],
            "task_scope_change_count": event_counts["TaskScopeChanged"],
            "recovery_command_count": command_counts["episode.recover"],
            "supervision_stop_count": sum(1 for task in task_states if task.get("supervision_stop")),
        },
        "reliability": {
            "denied_command_count": sum(denials.values()),
            "denial_ratio": round(sum(denials.values()) / len(commands), 6) if commands else 0.0,
            "integrity_ok": bool(integrity.get("ok")),
            "structured_observation_count": len(observation_states),
        },
        "media_review": {
            "media_annotation_count": len(media_annotations),
            "positioned_media_annotation_count": sum(
                1 for item in media_annotations if (item.get("location") or {}).get("position")
            ),
            "distinct_annotated_artifact_count": len(
                {
                    (item.get("location") or {}).get("artifact_id")
                    for item in media_annotations
                    if (item.get("location") or {}).get("artifact_id")
                }
            ),
        },
        "coverage": {
            "event_log": "complete",
            "command_log": "complete",
            "capsule_manifest_log": "complete",
            "aggregate_projection": "complete",
            "artifact_lineage": "complete",
            "human_ui_interaction_log": "external_or_unknown",
            "media_playback_performance_log": "external_or_unknown",
            "model_runtime_metadata": "external_or_unknown",
        },
        "unknown_metrics": unknown_metrics,
    }
    files = {
        "aggregates.json": json.dumps(aggregates, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        "events.jsonl": _jsonl(events),
        "commands.jsonl": _jsonl(commands),
        "capsules.jsonl": _jsonl(capsules),
        "integrity.json": json.dumps(integrity, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        "metrics.json": json.dumps(metrics, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    }
    for name, content in files.items():
        _atomic_write(output_dir / name, content)
    file_manifest = {
        name: {"sha256": file_hash(output_dir / name), "bytes": (output_dir / name).stat().st_size}
        for name in sorted(files)
    }
    episode = next((item["state"] for item in aggregates if item["aggregate_type"] == "episode"), {})
    manifest_payload = {
        "schema": "lecture-state-supervision-evidence-bundle-v1",
        "episode_id": episode.get("episode_id"),
        "episode_title": episode.get("title"),
        "frozen_at": events[-1]["occurred_at"] if events else None,
        "cursor": integrity["cursor"],
        "files": file_manifest,
        "state_root_hash": object_hash(
            [
                {
                    "aggregate_type": item["aggregate_type"],
                    "aggregate_id": item["aggregate_id"],
                    "version": item["version"],
                    "state_hash": item["state_hash"],
                }
                for item in aggregates
            ]
        ),
    }
    manifest = {**manifest_payload, "manifest_hash": object_hash(manifest_payload)}
    _atomic_write(output_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return {
        "ok": True,
        "status": "frozen",
        "output_dir": str(output_dir),
        "manifest": manifest,
        "metrics": metrics,
    }
