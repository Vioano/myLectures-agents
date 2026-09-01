#!/usr/bin/env python3
"""Repeat invariant-focused tests to expose nondeterminism and race defects."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import sys
import time
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "state-supervision"))

from tests.test_concurrency_recovery import ConcurrencyRecoveryTests  # noqa: E402
from tests.test_workflow import WorkflowTests  # noqa: E402


GROUPS = {
    "read_and_replay_determinism": (
        (WorkflowTests, "test_default_next_projection_is_attention_sized"),
        (WorkflowTests, "test_next_and_explain_are_read_only_and_causal"),
        (ConcurrencyRecoveryTests, "test_restart_replay_is_semantically_stable"),
    ),
    "concurrent_lease_serialization": (
        (ConcurrencyRecoveryTests, "test_concurrent_begin_has_exactly_one_winner"),
    ),
    "idempotent_submission": (
        (WorkflowTests, "test_submit_is_content_addressed_and_retry_safe"),
    ),
    "context_and_gate_pinning": (
        (WorkflowTests, "test_context_capsule_fails_closed_on_reference_drift"),
        (WorkflowTests, "test_reference_drift_has_one_explicit_rebind_path"),
        (WorkflowTests, "test_pinned_hard_gate_precedes_independent_review"),
        (WorkflowTests, "test_validator_code_drift_and_canary_are_fail_closed"),
    ),
    "change_isolation": (
        (WorkflowTests, "test_upstream_change_stales_only_affected_lineage"),
    ),
    "recovery_boundaries": (
        (ConcurrencyRecoveryTests, "test_missing_artifact_recovery_is_local"),
        (ConcurrencyRecoveryTests, "test_projection_drift_rebuild_preserves_event_prefix"),
        (ConcurrencyRecoveryTests, "test_attention_scan_is_a_successful_query_not_an_api_failure"),
    ),
    "structured_denials": (
        (WorkflowTests, "test_structured_denials_do_not_mutate_domain_aggregates"),
        (WorkflowTests, "test_gap_cannot_silently_reopen_an_approved_task"),
    ),
    "fluid_dispatch_and_returns": (
        (WorkflowTests, "test_review_return_waits_for_attention_boundary_and_can_be_rerouted"),
        (WorkflowTests, "test_dual_axis_scope_is_bounded_and_never_implies_a_stage_barrier"),
    ),
    "human_conflict_decision_handoff": (
        (WorkflowTests, "test_structural_scene_conflict_blocks_before_lease_and_reaches_human"),
        (WorkflowTests, "test_review_capsule_preserves_human_gap_resolution_and_retry_override"),
    ),
    "reserved_parallel_dispatch": (
        (WorkflowTests, "test_parallel_reservations_prevent_queue_drain_and_create_overlapping_leases"),
    ),
    "route_replacement": (
        (WorkflowTests, "test_route_switch_replaces_method_rewires_only_descendants_and_fulfills"),
        (WorkflowTests, "test_route_switch_rejects_deliverable_change_without_mutation"),
        (WorkflowTests, "test_route_switch_revokes_live_owner_without_touching_sibling"),
        (WorkflowTests, "test_route_switch_cancels_stale_deferred_return"),
        (WorkflowTests, "test_narration_audio_contract_rejects_extension_spoof_before_review"),
    ),
}


def run_group(cases, repetitions: int) -> dict:
    suite = unittest.TestSuite()
    for _ in range(repetitions):
        for test_class, method in cases:
            suite.addTest(test_class(method))
    stream = io.StringIO()
    started = time.monotonic()
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    return {
        "tests_run": result.testsRun,
        "passed": result.testsRun - len(result.failures) - len(result.errors),
        "failures": [test.id() for test, _ in result.failures],
        "errors": [test.id() for test, _ in result.errors],
        "duration_seconds": round(time.monotonic() - started, 3),
        "diagnostic": stream.getvalue()[-8000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument("--race-repetitions", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repetitions < 1 or args.race_repetitions < 1:
        parser.error("repetition counts must be positive")
    groups = {}
    for name, cases in GROUPS.items():
        repetitions = (
            args.race_repetitions
            if name == "concurrent_lease_serialization"
            else args.repetitions
        )
        groups[name] = run_group(cases, repetitions)
    total = sum(item["tests_run"] for item in groups.values())
    failed = sum(len(item["failures"]) + len(item["errors"]) for item in groups.values())
    report = {
        "schema": "state-supervision-stress-report-v1",
        "profile": {
            "repetitions": args.repetitions,
            "race_repetitions": args.race_repetitions,
        },
        "tests_run": total,
        "passed": total - failed,
        "failed": failed,
        "invariant_ratio": (total - failed) / total if total else 0.0,
        "hard_failures": failed,
        "groups": groups,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
