"""Observable anomaly detection and narrowly scoped recovery planning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import file_hash, object_hash
from .domain import dependency_cycle, lease_is_live, resolve_repo_path
from .store import EpisodeStore


CURRENT_ARTIFACT_STATUSES = {"candidate", "user_review_pending", "approved"}
ARTIFACT_FAILURE_KINDS = {"artifact_missing", "artifact_hash_drift"}


def current_artifact_ids(task: dict[str, Any] | None) -> set[str]:
    """Return only the artifact ids that belong to a task's active lineage.

    A task in rework/working can retain historical candidate fields in an old
    projection.  Those ids are evidence, not current production authority.  A
    blocked task is allowed to retain the candidate that caused the block so a
    real current-artifact failure remains diagnosable.
    """

    if not task or task.get("status") not in CURRENT_ARTIFACT_STATUSES | {"blocked"}:
        return set()
    candidate = task.get("candidate") or {}
    return {
        str(artifact_id)
        for artifact_id in [
            *candidate.get("artifact_ids", []),
            *task.get("approved_artifact_ids", []),
        ]
        if artifact_id
    }


def anomaly_id(kind: str, subject_id: str, facts: dict[str, Any]) -> str:
    return "anomaly_" + object_hash({"kind": kind, "subject_id": subject_id, "facts": facts})[:20]


def scan_episode(
    store: EpisodeStore,
    repo_root: Path,
    *,
    now: str,
    deep: bool = False,
) -> dict[str, Any]:
    integrity = store.verify_integrity()
    anomalies: list[dict[str, Any]] = []
    for error in integrity["errors"]:
        kind = str(error.get("kind"))
        subject = str(error.get("aggregate_id", "event-store"))
        anomalies.append(
            {
                "anomaly_id": anomaly_id(kind, subject, error),
                "kind": kind,
                "subject_id": subject,
                "severity": "critical" if kind not in {"projection_drift", "missing_projection", "orphan_projection"} else "high",
                "repairable": kind in {"projection_drift", "missing_projection", "orphan_projection"},
                "proposed_action": "rebuild_projection" if kind in {"projection_drift", "missing_projection", "orphan_projection"} else "restore_or_forensics",
                "facts": error,
            }
        )
    tasks = {state["task_id"]: state for state, _ in store.list("task")}
    leases = {state["task_id"]: state for state, _ in store.list("lease")}
    artifacts = {state["artifact_id"]: state for state, _ in store.list("artifact")}
    gaps = [state for state, _ in store.list("gap")]
    cycle = dependency_cycle(tasks)
    if cycle:
        facts = {"cycle": cycle}
        anomalies.append(
            {
                "anomaly_id": anomaly_id("dependency_cycle", cycle[0], facts),
                "kind": "dependency_cycle",
                "subject_id": cycle[0],
                "severity": "critical",
                "repairable": False,
                "proposed_action": "human_replan",
                "facts": facts,
            }
        )
    for task_id, task in sorted(tasks.items()):
        active_artifact_ids = current_artifact_ids(task)
        obsolete_artifact_blockers = [
            blocker
            for blocker in task.get("blockers", [])
            if blocker.get("kind") in ARTIFACT_FAILURE_KINDS
            and str(blocker.get("artifact_id", "")) not in active_artifact_ids
        ]
        for dependency_id in task.get("dependencies", []):
            if dependency_id not in tasks:
                facts = {"missing_dependency": dependency_id}
                anomalies.append(
                    {
                        "anomaly_id": anomaly_id("missing_dependency", task_id, facts),
                        "kind": "missing_dependency",
                        "subject_id": task_id,
                        "severity": "high",
                        "repairable": False,
                        "proposed_action": "human_replan",
                        "facts": facts,
                    }
                )
        lease = leases.get(task_id)
        if task.get("status") == "working" and not lease_is_live(lease, now):
            kind = "expired_lease" if lease else "working_without_lease"
            facts = {"lease": lease}
            anomalies.append(
                {
                    "anomaly_id": anomaly_id(kind, task_id, facts),
                    "kind": kind,
                    "subject_id": task_id,
                    "severity": "high",
                    "repairable": True,
                    "proposed_action": "return_task_to_rework",
                    "facts": facts,
                }
            )
        if (
            lease_is_live(lease, now)
            and task.get("status") != "working"
            and not (task.get("status") == "blocked" and obsolete_artifact_blockers)
        ):
            facts = {"task_status": task.get("status"), "lease": lease}
            anomalies.append(
                {
                    "anomaly_id": anomaly_id("orphan_live_lease", task_id, facts),
                    "kind": "orphan_live_lease",
                    "subject_id": task_id,
                    "severity": "high",
                    "repairable": True,
                    "proposed_action": "release_orphan_lease",
                    "facts": facts,
                }
            )
        if task.get("status") == "blocked" and obsolete_artifact_blockers:
            facts = {
                "obsolete_blockers": obsolete_artifact_blockers,
                "current_artifact_ids": sorted(active_artifact_ids),
                "lease": lease,
            }
            anomalies.append(
                {
                    "anomaly_id": anomaly_id(
                        "historical_artifact_false_block", task_id, facts
                    ),
                    "kind": "historical_artifact_false_block",
                    "subject_id": task_id,
                    "severity": "high",
                    "repairable": True,
                    "proposed_action": "remove_obsolete_artifact_blockers",
                    "facts": facts,
                }
            )
        open_gaps = [gap for gap in gaps if gap.get("task_id") == task_id and gap.get("status") == "open"]
        if open_gaps and task.get("status") != "blocked":
            facts = {"gap_ids": [gap["gap_id"] for gap in open_gaps], "task_status": task.get("status")}
            anomalies.append(
                {
                    "anomaly_id": anomaly_id("open_gap_not_blocking", task_id, facts),
                    "kind": "open_gap_not_blocking",
                    "subject_id": task_id,
                    "severity": "high",
                    "repairable": True,
                    "proposed_action": "block_task",
                    "facts": facts,
                }
            )
        if task.get("status") == "blocked":
            approved_upstreams = sorted(
                {
                    str(blocker.get("upstream_task_id"))
                    for blocker in task.get("blockers", [])
                    if blocker.get("kind") == "upstream_change"
                    and tasks.get(str(blocker.get("upstream_task_id")), {}).get(
                        "status"
                    )
                    == "approved"
                }
            )
            if approved_upstreams:
                facts = {
                    "approved_upstream_task_ids": approved_upstreams,
                    "blockers": task.get("blockers", []),
                }
                anomalies.append(
                    {
                        "anomaly_id": anomaly_id(
                            "resolved_upstream_invalidation", task_id, facts
                        ),
                        "kind": "resolved_upstream_invalidation",
                        "subject_id": task_id,
                        "severity": "medium",
                        "repairable": True,
                        "proposed_action": "release_resolved_upstream_blockers",
                        "facts": facts,
                    }
                )
    for task_id, lease in sorted(leases.items()):
        if task_id not in tasks:
            facts = {"lease_id": lease.get("lease_id")}
            anomalies.append(
                {
                    "anomaly_id": anomaly_id("lease_without_task", task_id, facts),
                    "kind": "lease_without_task",
                    "subject_id": task_id,
                    "severity": "critical",
                    "repairable": False,
                    "proposed_action": "manual_forensics",
                    "facts": facts,
                }
            )
    if deep:
        for artifact_id, artifact in sorted(artifacts.items()):
            producer_task_id = str(artifact.get("producer_task_id", ""))
            producer_task = tasks.get(producer_task_id)
            in_current_lineage = artifact_id in current_artifact_ids(producer_task)
            recorded_blockers = [
                blocker
                for blocker in (producer_task or {}).get("blockers", [])
                if blocker.get("kind") in ARTIFACT_FAILURE_KINDS
                and str(blocker.get("artifact_id", "")) == artifact_id
            ]
            path = resolve_repo_path(repo_root, str(artifact.get("path", "")))
            if not path.is_file():
                if not in_current_lineage:
                    kind = "historical_artifact_missing"
                elif recorded_blockers:
                    kind = "artifact_missing_recorded"
                else:
                    kind = "artifact_missing"
                facts = {
                    "path": artifact.get("path"),
                    "producer_task_id": producer_task_id,
                    "artifact_status": artifact.get("status"),
                    "lineage": "current" if in_current_lineage else "historical",
                    "already_isolated": bool(recorded_blockers),
                }
                anomalies.append(
                    {
                        "anomaly_id": anomaly_id(kind, artifact_id, facts),
                        "kind": kind,
                        "subject_id": artifact_id,
                        "severity": "critical" if in_current_lineage else "medium",
                        "repairable": in_current_lineage and not recorded_blockers,
                        "proposed_action": (
                            "mark_artifact_missing_and_block_producer"
                            if in_current_lineage and not recorded_blockers
                            else "current_failure_already_isolated"
                            if in_current_lineage
                            else "retain_historical_lineage_finding"
                        ),
                        "facts": facts,
                    }
                )
            else:
                actual = file_hash(path)
                if actual != artifact.get("sha256"):
                    if not in_current_lineage:
                        kind = "historical_artifact_hash_drift"
                    elif recorded_blockers:
                        kind = "artifact_hash_drift_recorded"
                    else:
                        kind = "artifact_hash_drift"
                    facts = {
                        "path": artifact.get("path"),
                        "expected_sha256": artifact.get("sha256"),
                        "actual_sha256": actual,
                        "producer_task_id": producer_task_id,
                        "artifact_status": artifact.get("status"),
                        "lineage": "current" if in_current_lineage else "historical",
                        "already_isolated": bool(recorded_blockers),
                    }
                    anomalies.append(
                        {
                            "anomaly_id": anomaly_id(kind, artifact_id, facts),
                            "kind": kind,
                            "subject_id": artifact_id,
                            "severity": "critical" if in_current_lineage else "medium",
                            "repairable": in_current_lineage and not recorded_blockers,
                            "proposed_action": (
                                "mark_artifact_drifted_and_block_producer"
                                if in_current_lineage and not recorded_blockers
                                else "current_failure_already_isolated"
                                if in_current_lineage
                                else "retain_historical_lineage_finding"
                            ),
                            "facts": facts,
                        }
                    )
    return {
        "ok": True,
        "clean": not anomalies,
        "status": "healthy" if not anomalies else "attention",
        "cursor": integrity["cursor"],
        "deep": deep,
        "anomalies": anomalies,
        "repairable_count": sum(1 for item in anomalies if item["repairable"]),
        "manual_count": sum(1 for item in anomalies if not item["repairable"]),
    }
