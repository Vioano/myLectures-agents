#!/usr/bin/env python3
"""Freeze Round 03 and index contradiction, routing, UI and Agent evidence."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
from typing import Any


THIS_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_ROOT.parents[1]
OPERATOR = PROJECT_ROOT / "state-supervision-evaluation" / "short-tests" / "operator_cli.py"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def check(
    check_id: str,
    status: str,
    evidence: Any,
    *,
    surface: str,
) -> dict[str, Any]:
    if status not in {"pass", "fail", "partial", "not_reached"}:
        raise ValueError(f"unsupported check status: {status}")
    return {
        "check_id": check_id,
        "status": status,
        "surface": surface,
        "evidence": evidence,
    }


def event_index(events: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    return [
        {
            "seq": item["seq"],
            "event_id": item["event_id"],
            "aggregate_type": item["aggregate_type"],
            "aggregate_id": item["aggregate_id"],
            "actor": item.get("actor"),
            "payload": item.get("payload", {}),
        }
        for item in events
        if item.get("event_type") == event_type
    ]


def aggregate_map(aggregates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for item in aggregates:
        result.setdefault(str(item["aggregate_type"]), []).append(item["state"])
    return result


def build_evidence(bundle_dir: Path, run_manifest: dict[str, Any]) -> dict[str, Any]:
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    integrity = json.loads((bundle_dir / "integrity.json").read_text(encoding="utf-8"))
    metrics = json.loads((bundle_dir / "metrics.json").read_text(encoding="utf-8"))
    events = read_jsonl(bundle_dir / "events.jsonl")
    capsules = read_jsonl(bundle_dir / "capsules.jsonl")
    aggregates = json.loads(
        (bundle_dir / "aggregates.json").read_text(encoding="utf-8")
    )
    grouped = aggregate_map(aggregates)
    tasks = {item["task_id"]: item for item in grouped.get("task", [])}
    agents = {item["agent_id"]: item for item in grouped.get("agent", [])}
    routes = sorted(grouped.get("route", []), key=lambda item: item["route_switch_id"])
    gaps = sorted(grouped.get("gap", []), key=lambda item: item["gap_id"])
    overrides = sorted(
        grouped.get("context_override", []), key=lambda item: item["override_id"]
    )
    observations = sorted(
        grouped.get("observation", []), key=lambda item: item["observation_id"]
    )
    annotations = sorted(
        grouped.get("annotation", []), key=lambda item: item["annotation_id"]
    )
    observation_categories = Counter(
        str(item.get("category")) for item in observations
    )
    event_types = Counter(str(item.get("event_type")) for item in events)
    first_capsules = sorted(capsules, key=lambda item: item["created_seq"])[:4]
    first_capsule_text = json.dumps(first_capsules, ensure_ascii=False)
    future_terms = [
        term
        for term in ("T112", "T122", "T132", "sprite", "A-roll", "3D")
        if term in first_capsule_text
    ]
    contradiction_gaps = [
        item
        for item in gaps
        if "ctx_" in str(item.get("reason", ""))
        or "矛盾" in str(item.get("reason", ""))
        or "冲突" in str(item.get("reason", ""))
    ]
    resolved_contradiction_gaps = [
        item for item in contradiction_gaps if item.get("status") == "resolved"
    ]
    t040 = tasks.get("T040", {})
    t900 = tasks.get("T900", {})
    human_reversal_events = event_index(events, "TaskHumanApprovalReversed")
    human_approval_events = event_index(events, "TaskHumanApproved")
    rush_agent_ids = [
        agent_id
        for agent_id in ("rush-author-1", "rush-author-2", "rush-author-3")
        if agent_id in agents
    ]
    probe_task_ids = ("T221", "T222", "T223")
    probe_starts = {
        str(item.get("payload", {}).get("task_id")): item["seq"]
        for item in events
        if item.get("event_type") == "LeaseGranted"
        and item.get("payload", {}).get("task_id") in probe_task_ids
    }
    probe_releases: dict[str, int] = {}
    for item in events:
        task_id = str(item.get("payload", {}).get("task_id", ""))
        if item.get("event_type") == "LeaseReleased" and task_id in probe_task_ids:
            probe_releases.setdefault(task_id, item["seq"])
    probe_overlap = (
        len(probe_starts) == len(probe_task_ids)
        and len(probe_releases) == len(probe_task_ids)
        and max(probe_starts.values()) < min(probe_releases.values())
    )
    t223_review_events = [
        item
        for item in event_index(events, "ReviewRecorded")
        if item.get("payload", {}).get("task_id") == "T223"
    ]
    t223_review_text = json.dumps(t223_review_events, ensure_ascii=False)
    checks = [
        check(
            "event_store_integrity",
            "pass" if integrity.get("ok") else "fail",
            integrity,
            surface="backend",
        ),
        check(
            "initial_capsule_did_not_leak_future_plot",
            "pass" if not future_terms else "fail",
            {
                "first_capsule_hashes": [item["capsule_hash"] for item in first_capsules],
                "future_terms_found": future_terms,
            },
            surface="agent_interface",
        ),
        check(
            "three_explicit_route_supersessions",
            "pass" if event_types["RouteSwitched"] >= 3 else "fail",
            {
                "count": event_types["RouteSwitched"],
                "routes": routes,
            },
            surface="backend",
        ),
        check(
            "semantic_conflicts_detected_by_agent",
            "pass" if len(contradiction_gaps) >= 2 else "fail",
            {
                "gap_ids": [item["gap_id"] for item in contradiction_gaps],
                "observation_categories": dict(observation_categories),
            },
            surface="agent_interface",
        ),
        check(
            "deterministic_context_manifest_detected_semantic_conflicts",
            "fail",
            {
                "observed_conflict_count": 0,
                "hard_conflicts_present": 2,
                "note": (
                    "Round injection preview reported conflict_count=0 even though four "
                    "same-slot active instructions contained two hard semantic conflicts."
                ),
            },
            surface="backend",
        ),
        check(
            "conflicts_resolved_independently",
            "pass" if len(resolved_contradiction_gaps) >= 2 else "fail",
            {
                "resolved_gap_ids": [
                    item["gap_id"] for item in resolved_contradiction_gaps
                ],
                "resolution_override_ids": [
                    item["override_id"]
                    for item in overrides
                    if item.get("assembly_mode") == "replace"
                ],
            },
            surface="cross_surface",
        ),
        check(
            "unrelated_work_continued_while_visual_conflict_blocked",
            "pass"
            if all(tasks.get(task_id, {}).get("status") == "approved" for task_id in ("T010", "T112", "T020"))
            else "fail",
            {
                task_id: tasks.get(task_id, {}).get("status")
                for task_id in ("T010", "T112", "T020", "T132")
            },
            surface="backend",
        ),
        check(
            "human_ui_promoted_conflict_to_attention",
            "fail" if observation_categories["human_ui_conflict_visibility"] else "not_reached",
            {
                "observation_ids": [
                    item["observation_id"]
                    for item in observations
                    if item.get("category") == "human_ui_conflict_visibility"
                ],
                "observed_ui": "T132 showed blocked/waiting dependency while Human attention remained zero.",
            },
            surface="human_interface",
        ),
        check(
            "human_media_annotation_and_approval_reversal",
            "pass"
            if annotations and human_reversal_events and human_approval_events
            else "not_reached",
            {
                "annotation_ids": [item["annotation_id"] for item in annotations],
                "approval_event_seqs": [item["seq"] for item in human_approval_events],
                "reversal_event_seqs": [item["seq"] for item in human_reversal_events],
                "t040_status": t040.get("status"),
            },
            surface="human_interface",
        ),
        check(
            "frontend_restart_reconciled_persisted_backend",
            "pass"
            if observation_categories["frontend_backend_recovery"]
            else "not_reached",
            {
                "observation_ids": [
                    item["observation_id"]
                    for item in observations
                    if item.get("category") == "frontend_backend_recovery"
                ]
            },
            surface="cross_surface",
        ),
        check(
            "deadline_pressure_triggered_three_author_expansion",
            "pass"
            if tasks.get("T190", {}).get("status") == "approved"
            and len(rush_agent_ids) == 3
            else "fail",
            {
                "coordinator_task_status": tasks.get("T190", {}).get("status"),
                "registered_rush_authors": rush_agent_ids,
                "intended_total_author_lanes": 4,
            },
            surface="agent_interface",
        ),
        check(
            "parallel_graph_alone_delivered_parallel_throughput",
            "fail" if observation_categories["rush_dispatch_utilization"] else "not_reached",
            {
                "observation_ids": [
                    item["observation_id"]
                    for item in observations
                    if item.get("category") == "rush_dispatch_utilization"
                ],
                "finding": (
                    "The original author serially drained T211/T212/T213 before "
                    "the newly registered authors acquired leases."
                ),
            },
            surface="backend",
        ),
        check(
            "capacity_probe_proved_three_overlapping_author_leases",
            "pass"
            if probe_overlap
            and all(tasks.get(task_id, {}).get("status") == "approved" for task_id in (*probe_task_ids, "T249"))
            else "fail",
            {
                "lease_start_seqs": probe_starts,
                "first_release_seqs": probe_releases,
                "overlap_rule": "max(start_seq) < min(first_release_seq)",
                "task_statuses": {
                    task_id: tasks.get(task_id, {}).get("status")
                    for task_id in (*probe_task_ids, "T249")
                },
            },
            surface="backend",
        ),
        check(
            "human_scene_resolution_reached_author_and_independent_review",
            "pass"
            if tasks.get("T223", {}).get("status") == "approved"
            and tasks.get("T223", {}).get("attempt", 0) >= 2
            and "ctx_d2e8befb16adc3b9867c" in t223_review_text
            and "contradictory_requirements" in t223_review_text
            and "resolution" in t223_review_text
            else "fail",
            {
                "task_status": tasks.get("T223", {}).get("status"),
                "attempt": tasks.get("T223", {}).get("attempt"),
                "review_events": t223_review_events,
                "initial_handoff_defect_observations": [
                    item["observation_id"]
                    for item in observations
                    if item.get("category") == "review_attention_handoff"
                ],
            },
            surface="cross_surface",
        ),
        check(
            "blackbox_agent_report_submitted",
            "pass" if t900.get("status") == "approved" else "not_reached",
            {
                "t900_status": t900.get("status"),
                "approved_artifact_ids": t900.get("approved_artifact_ids", []),
            },
            surface="agent_interface",
        ),
    ]
    counts = Counter(item["status"] for item in checks)
    overall = "pass" if counts["fail"] == 0 and counts["not_reached"] == 0 else "revise"
    return {
        "schema": "state-supervision-chaos-verification-v1",
        "run_id": run_manifest.get("run_id"),
        "episode_id": run_manifest.get("episode_id"),
        "overall_status": overall,
        "cursor": manifest["cursor"],
        "state_root_hash": manifest["state_root_hash"],
        "evidence_manifest_hash": manifest["manifest_hash"],
        "metrics": metrics,
        "event_type_counts": dict(sorted(event_types.items())),
        "checks": checks,
        "routes": routes,
        "gaps": gaps,
        "context_overrides": overrides,
        "annotations": annotations,
        "observations": observations,
        "task_outcomes": {
            task_id: {
                "status": item.get("status"),
                "attempt": item.get("attempt"),
                "active_lease_generation": item.get("active_lease_generation"),
                "approved_artifact_ids": item.get("approved_artifact_ids", []),
            }
            for task_id, item in sorted(tasks.items())
        },
    }


def freeze(run_root: Path, *, reuse_existing: bool = False) -> dict[str, Any]:
    run_root = run_root.resolve()
    run_manifest_path = run_root / "run-manifest.json"
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    workspace = Path(run_manifest["workspace"]).resolve()
    environment = json.loads(
        (workspace / "environment.json").read_text(encoding="utf-8")
    )
    bundle_dir = run_root / "frozen-evidence"
    bundle_exists = bundle_dir.exists() and any(bundle_dir.iterdir())
    if bundle_exists and not reuse_existing:
        raise RuntimeError(f"refusing to overwrite evidence bundle: {bundle_dir}")
    if not bundle_exists:
        completed = subprocess.run(
            [
                "python3",
                str(OPERATOR),
                "--workspace",
                str(workspace),
                "--actor",
                "harness-maintainer",
                "--request-id",
                f"freeze-{run_manifest['run_id']}",
                "export",
                str(environment["episode_id"]),
                "--output",
                str(bundle_dir),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        export_result = json.loads(completed.stdout)
    else:
        export_result = {"ok": True, "reused": True, "output": str(bundle_dir)}
    evidence = build_evidence(bundle_dir, run_manifest)
    evidence_path = run_root / "VERIFICATION_EVIDENCE.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    frozen_manifest = json.loads(
        (bundle_dir / "manifest.json").read_text(encoding="utf-8")
    )
    run_manifest.update(
        {
            "status": f"frozen_{evidence['overall_status']}",
            "final_cursor": evidence["cursor"],
            "frozen_at": frozen_manifest.get("frozen_at"),
            "evidence_manifest_hash": evidence["evidence_manifest_hash"],
        }
    )
    run_manifest_path.write_text(
        json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "status": evidence["overall_status"],
        "bundle_dir": str(bundle_dir),
        "evidence_path": str(evidence_path),
        "export": export_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    parser.add_argument("--reuse-existing", action="store_true")
    arguments = parser.parse_args()
    result = freeze(arguments.run_root, reuse_existing=arguments.reuse_existing)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
