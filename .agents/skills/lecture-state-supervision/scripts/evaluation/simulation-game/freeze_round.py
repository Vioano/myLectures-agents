#!/usr/bin/env python3
"""Freeze one simulation round into raw evidence plus a concise audit index."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


THIS_ROOT = Path(__file__).resolve().parent
OPERATOR = THIS_ROOT.parent / "short-tests" / "operator_cli.py"

MILESTONE_EVENT_TYPES = {
    "RouteSwitched",
    "DeferredReturnQueued",
    "AnnotationAdded",
    "TaskAnnotationAttentionScheduled",
    "TaskHumanApprovalReversed",
    "TaskInvalidatedByUpstreamChange",
    "TaskAwaitingHumanReview",
    "TaskHumanApproved",
    "TaskReleasedAfterUpstreamReapproval",
    "ArtifactHashDriftDetected",
    "TaskBlockedByArtifactFailure",
    "LeaseReleasedByRecovery",
    "TaskRecoveredFromHistoricalArtifactFalseBlock",
    "TaskSubmitted",
    "ReviewRecorded",
    "ArtifactAccepted",
    "TaskApproved",
    "EvaluationObservationRecorded",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def one_check(
    check_id: str,
    passed: bool,
    evidence: Any,
    *,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "pending",
        "required": required,
        "evidence": evidence,
    }


def build_evidence(bundle_dir: Path, run_manifest: dict[str, Any]) -> dict[str, Any]:
    export_manifest = json.loads(
        (bundle_dir / "manifest.json").read_text(encoding="utf-8")
    )
    integrity = json.loads(
        (bundle_dir / "integrity.json").read_text(encoding="utf-8")
    )
    metrics = json.loads(
        (bundle_dir / "metrics.json").read_text(encoding="utf-8")
    )
    events = read_jsonl(bundle_dir / "events.jsonl")
    capsules = read_jsonl(bundle_dir / "capsules.jsonl")
    aggregates = json.loads(
        (bundle_dir / "aggregates.json").read_text(encoding="utf-8")
    )
    by_type: dict[str, list[dict[str, Any]]] = {}
    for item in aggregates:
        by_type.setdefault(str(item["aggregate_type"]), []).append(item["state"])
    tasks = {
        str(item["task_id"]): item for item in by_type.get("task", [])
    }
    observations = sorted(
        by_type.get("observation", []), key=lambda item: item["observation_id"]
    )
    annotations = sorted(
        by_type.get("annotation", []), key=lambda item: item["annotation_id"]
    )
    milestone_events = [
        {
            "seq": item["seq"],
            "event_id": item["event_id"],
            "event_type": item["event_type"],
            "aggregate_type": item["aggregate_type"],
            "aggregate_id": item["aggregate_id"],
            "actor": item.get("actor"),
            "payload": item.get("payload", {}),
        }
        for item in events
        if item.get("event_type") in MILESTONE_EVENT_TYPES
    ]
    capsule_index = [
        {
            "capsule_hash": item["capsule_hash"],
            "created_seq": item["created_seq"],
            "task_id": item["payload"].get("task", {}).get("task_id"),
            "task_version": item.get("task_version"),
            "annotation_ids": item["payload"].get("context_manifest", {}).get(
                "annotation_ids", []
            ),
            "annotation_delivery": item["payload"].get("why_now", {}).get(
                "human_annotation_delivery"
            ),
            "upstream_reapproval_receipts": item["payload"].get("task", {}).get(
                "upstream_reapproval_receipts", []
            ),
        }
        for item in capsules
        if item["payload"].get("task", {}).get("task_id") in {"T040", "T900"}
    ]
    event_types = {item["event_type"] for item in events}
    observation_categories = {
        str(item.get("category")) for item in observations
    }
    t040 = tasks.get("T040", {})
    t900 = tasks.get("T900", {})
    checks = [
        one_check(
            "event_store_integrity",
            bool(integrity.get("ok")),
            integrity,
        ),
        one_check(
            "initial_plan_then_late_route_switch",
            run_manifest.get("initial_assumption") == "all_tts"
            and "RouteSwitched" in event_types,
            {
                "initial_assumption": run_manifest.get("initial_assumption"),
                "route_switch_seqs": [
                    item["seq"]
                    for item in milestone_events
                    if item["event_type"] == "RouteSwitched"
                ],
            },
        ),
        one_check(
            "deferred_review_return",
            "DeferredReturnQueued" in event_types,
            [
                item
                for item in milestone_events
                if item["event_type"] == "DeferredReturnQueued"
            ],
        ),
        one_check(
            "human_annotation_delivery_audited",
            bool(annotations)
            and "agent_attention_delivery" in observation_categories,
            {
                "annotation_ids": [item["annotation_id"] for item in annotations],
                "observation_ids": [
                    item["observation_id"]
                    for item in observations
                    if item.get("category")
                    in {"agent_attention_delivery", "taxonomy_correction"}
                ],
            },
        ),
        one_check(
            "human_approval_reversal_and_reapproval",
            {
                "TaskHumanApprovalReversed",
                "TaskInvalidatedByUpstreamChange",
                "TaskHumanApproved",
            }.issubset(event_types)
            and t040.get("status") == "approved",
            {
                "t040_status": t040.get("status"),
                "event_seqs": [
                    item["seq"]
                    for item in milestone_events
                    if item["event_type"]
                    in {
                        "TaskHumanApprovalReversed",
                        "TaskInvalidatedByUpstreamChange",
                        "TaskHumanApproved",
                    }
                ],
            },
        ),
        one_check(
            "downstream_released_after_upstream_reapproval",
            "TaskReleasedAfterUpstreamReapproval" in event_types
            and bool(t900.get("upstream_reapproval_receipts")),
            {
                "t900_status": t900.get("status"),
                "receipts": t900.get("upstream_reapproval_receipts", []),
            },
        ),
        one_check(
            "frontend_editor_isolation_regression_logged",
            "human_ui_editor_isolation" in observation_categories,
            [
                item["observation_id"]
                for item in observations
                if item.get("category") == "human_ui_editor_isolation"
            ],
        ),
        one_check(
            "historical_artifact_false_block_recovered",
            "TaskRecoveredFromHistoricalArtifactFalseBlock" in event_types
            and "historical_artifact_false_block" in observation_categories,
            {
                "recovery_event_seqs": [
                    item["seq"]
                    for item in milestone_events
                    if item["event_type"]
                    == "TaskRecoveredFromHistoricalArtifactFalseBlock"
                ],
                "observation_ids": [
                    item["observation_id"]
                    for item in observations
                    if item.get("category") == "historical_artifact_false_block"
                ],
            },
        ),
        one_check(
            "review_annotation_lineage_gap_logged",
            "review_annotation_lineage_gap" in observation_categories,
            [
                item["observation_id"]
                for item in observations
                if item.get("category") == "review_annotation_lineage_gap"
            ],
        ),
        one_check(
            "blackbox_agent_report_approved",
            t900.get("status") == "approved",
            {
                "t900_status": t900.get("status"),
                "attempt": t900.get("attempt"),
                "approved_artifact_ids": t900.get("approved_artifact_ids", []),
            },
        ),
    ]
    required = [item for item in checks if item["required"]]
    overall = "pass" if all(item["status"] == "pass" for item in required) else "pending"
    return {
        "schema": "state-supervision-simulation-verification-v1",
        "run_id": run_manifest.get("run_id"),
        "episode_id": run_manifest.get("episode_id"),
        "overall_status": overall,
        "cursor": export_manifest["cursor"],
        "state_root_hash": export_manifest["state_root_hash"],
        "evidence_manifest_hash": export_manifest["manifest_hash"],
        "metrics": metrics,
        "checks": checks,
        "milestone_events": milestone_events,
        "capsule_index": capsule_index,
        "observations": observations,
    }


def render_retrospective(evidence: dict[str, Any]) -> str:
    lines = [
        f"# Simulation retrospective — {evidence['run_id']}",
        "",
        f"- Episode: `{evidence['episode_id']}`",
        f"- Final cursor: `{evidence['cursor']}`",
        f"- State root: `{evidence['state_root_hash']}`",
        f"- Evidence manifest: `{evidence['evidence_manifest_hash']}`",
        f"- Overall verification: **{evidence['overall_status']}**",
        "",
        "## Requirement checks",
        "",
    ]
    for item in evidence["checks"]:
        mark = "x" if item["status"] == "pass" else " "
        lines.append(f"- [{mark}] `{item['check_id']}` — {item['status']}")
    lines.extend(
        [
            "",
            "## What the game exposed",
            "",
            "1. **The floating inspector was not an input-safe island.** Live deltas",
            "   rebuilt its DOM, moved its scroll position and discarded unfinished",
            "   Human annotations. A broad task-node click selector also treated the",
            "   inspector itself as a graph node, so nearly any click reopened it.",
            "2. **Historical evidence could block current work.** A drifted artifact",
            "   from an older T900 attempt was promoted to a current hard blocker and",
            "   interrupted the live lease. The run recovered at event 214 and required",
            "   a fresh begin boundary before the black-box report could finish.",
            "3. **Annotation lineage was identifiable but not readable.** T900 begin",
            "   and review receipts named nine Human annotation IDs while omitting the",
            "   exact bodies. The isolated reviewer had to request an explicit explain",
            "   view, proving that IDs alone do not focus model attention.",
            "4. **The live monitor could look healthy while missing a delta.** The SSE",
            "   badge remained live after cursor 220 even though the backend had advanced.",
            "5. **Routing and review-context churn remain visible pressure points.** The",
            "   rehearsal recorded lease conflict, capability mismatch, stale mission",
            "   wording and context invalidation after evaluation observations.",
            "",
            "## Fixes applied during the round",
            "",
            "- Kept annotation drafts, focus and inspector scroll outside live rerenders;",
            "  narrowed graph-node activation so inspector controls remain interactive.",
            "- Split the Human UI from backend authority: the backend continues from its",
            "  event store if the page closes, while a restarted page reloads the cursor.",
            "- Made historical artifact drift audit-only and added an idempotent local",
            "  recovery that clears only the false blocker and records an explicit event.",
            "- Projected upstream reapproval annotations with their exact bodies into",
            "  downstream begin and independent-review context capsules.",
            "- Added a low-frequency cursor reconciliation watchdog beside the SSE stream.",
            "- Replaced the raw repair console with a scan -> preview -> apply maintenance",
            "  flow and kept technical JSON behind an expandable evidence disclosure.",
            "",
            "## Known follow-ups",
            "",
            "- Reconcile stale episode-mission wording with the authoritative active route.",
            "- Stop evaluation-only observations from invalidating an exact review context.",
            "- Improve capability-aware next-task ordering and lease-conflict explanation.",
            "- Separate agent heartbeat health from workflow failure in the Human UI.",
            "",
            "## Evidence navigation",
            "",
            "`VERIFICATION_EVIDENCE.json` contains exact event seqs, capsule hashes,",
            "annotation IDs, observation IDs and recovery receipts. The sibling",
            "`frozen-evidence/` directory is the hash-manifested raw export and is",
            "kept local by default rather than committed wholesale.",
            "",
        ]
    )
    return "\n".join(lines)


def materialize_approved_agent_report(
    bundle_dir: Path,
    environment: dict[str, Any],
    run_root: Path,
) -> dict[str, Any] | None:
    """Copy only the independently approved T900 report into the run index."""

    aggregates = json.loads(
        (bundle_dir / "aggregates.json").read_text(encoding="utf-8")
    )
    candidates = [
        item["state"]
        for item in aggregates
        if item.get("aggregate_type") == "artifact"
        and item.get("state", {}).get("producer_task_id") == "T900"
        and item.get("state", {}).get("role") == "experience_report"
        and item.get("state", {}).get("status") == "approved"
    ]
    if not candidates:
        return None
    approved = max(candidates, key=lambda item: str(item.get("created_at", "")))
    recorded_path = Path(str(approved["path"]))
    source = recorded_path if recorded_path.is_absolute() else Path(
        environment["repo_root"]
    ) / recorded_path
    payload = source.read_bytes()
    actual_hash = hashlib.sha256(payload).hexdigest()
    if actual_hash != approved["sha256"]:
        raise RuntimeError(
            "approved T900 report no longer matches its frozen artifact hash: "
            f"{actual_hash} != {approved['sha256']}"
        )
    target = run_root / "AGENT_EXPERIENCE.md"
    target.write_bytes(payload)
    return {
        "artifact_id": approved["artifact_id"],
        "review_id": approved.get("review_id"),
        "sha256": actual_hash,
        "source": str(source),
        "materialized_path": str(target),
    }


def freeze_round(
    run_root: Path,
    *,
    bundle_dir: Path | None = None,
    reuse_existing: bool = False,
) -> dict[str, Any]:
    run_root = run_root.resolve()
    manifest_path = run_root / "run-manifest.json"
    run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    workspace = Path(run_manifest["workspace"]).resolve()
    environment = json.loads(
        (workspace / "environment.json").read_text(encoding="utf-8")
    )
    bundle_dir = (bundle_dir or (run_root / "frozen-evidence")).resolve()
    bundle_exists = bundle_dir.exists() and any(bundle_dir.iterdir())
    if bundle_exists and not reuse_existing:
        raise RuntimeError(
            f"refusing to overwrite existing evidence bundle: {bundle_dir}"
        )
    if bundle_exists:
        export_result = {
            "ok": True,
            "reused": True,
            "output": str(bundle_dir),
        }
    else:
        command = [
            "python3",
            str(OPERATOR),
            "--workspace",
            str(workspace),
            "--actor",
            "harness-maintainer",
            "export",
            str(environment["episode_id"]),
            "--output",
            str(bundle_dir),
        ]
        completed = subprocess.run(
            command, check=True, capture_output=True, text=True
        )
        export_result = json.loads(completed.stdout)
    evidence = build_evidence(bundle_dir, run_manifest)
    approved_report = materialize_approved_agent_report(
        bundle_dir, environment, run_root
    )
    evidence["approved_agent_report"] = approved_report
    evidence_path = run_root / "VERIFICATION_EVIDENCE.json"
    retrospective_path = run_root / "RETROSPECTIVE.md"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    retrospective_path.write_text(
        render_retrospective(evidence), encoding="utf-8"
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
            "approved_agent_report_sha256": (
                approved_report or {}
            ).get("sha256"),
        }
    )
    manifest_path.write_text(
        json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "status": evidence["overall_status"],
        "bundle_dir": str(bundle_dir),
        "evidence_path": str(evidence_path),
        "retrospective_path": str(retrospective_path),
        "export": export_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    parser.add_argument("--bundle-dir", type=Path)
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="re-index an already frozen immutable evidence bundle",
    )
    arguments = parser.parse_args()
    result = freeze_round(
        arguments.run_root,
        bundle_dir=arguments.bundle_dir,
        reuse_existing=arguments.reuse_existing,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 3


if __name__ == "__main__":
    raise SystemExit(main())
