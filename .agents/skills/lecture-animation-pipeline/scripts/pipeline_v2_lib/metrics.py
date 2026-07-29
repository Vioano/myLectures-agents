"""Production and review metrics for the canonical lecture animation pipeline."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Iterable


TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")


def interval_union_seconds(rows: Iterable[dict[str, Any]]) -> float:
    intervals: list[tuple[datetime, datetime]] = []
    for row in rows:
        try:
            start = datetime.fromisoformat(str(row.get("started_at")))
            end = datetime.fromisoformat(str(row.get("ended_at")))
        except (TypeError, ValueError):
            continue
        if end > start:
            intervals.append((start, end))
    intervals.sort(key=lambda item: item[0])
    merged: list[list[datetime]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return sum((end - start).total_seconds() for start, end in merged)


def phase_event_identity(row: dict[str, Any]) -> str:
    return str(row.get("phase_instance_id") or row.get("event_id") or repr(sorted(row.items())))


def probable_shared_phase_signature(row: dict[str, Any]) -> tuple[Any, ...] | None:
    """Detect legacy shared work recorded once per scene with different instance IDs."""
    if not row.get("run_id") or not row.get("started_at") or not row.get("ended_at"):
        return None
    return (
        str(row.get("run_id")),
        str(row.get("phase")),
        str(row.get("phase_purpose", "")),
        str(row.get("actor_model", "")),
        str(row.get("actor_role", "")),
        str(row.get("reasoning_effort", "")),
        str(row.get("started_at")),
        str(row.get("ended_at")),
        round(float(row.get("duration_seconds", 0.0) or 0.0), 3),
        tuple(int(row.get(field, 0) or 0) for field in TOKEN_FIELDS),
    )


def unique_phase_events_with_diagnostics(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = phase_event_identity(row)
        previous = by_id.get(key)
        if previous is None or float(row.get("duration_seconds", 0.0) or 0.0) > float(
            previous.get("duration_seconds", 0.0) or 0.0
        ):
            by_id[key] = row

    selected: list[dict[str, Any]] = []
    by_shared_signature: dict[tuple[Any, ...], dict[str, Any]] = {}
    probable_duplicates: list[dict[str, Any]] = []
    for row in by_id.values():
        signature = probable_shared_phase_signature(row)
        if signature is None:
            selected.append(row)
            continue
        previous = by_shared_signature.get(signature)
        if previous is None:
            by_shared_signature[signature] = row
            selected.append(row)
            continue
        probable_duplicates.append(
            {
                "kept_event_id": previous.get("event_id"),
                "dropped_event_id": row.get("event_id"),
                "kept_phase_instance_id": previous.get("phase_instance_id"),
                "dropped_phase_instance_id": row.get("phase_instance_id"),
                "phase": row.get("phase"),
                "scene_slugs": sorted(
                    {
                        str(previous.get("scene_slug", "")),
                        str(row.get("scene_slug", "")),
                    }
                    - {""}
                ),
            }
        )
    return selected, probable_duplicates


def unique_phase_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return unique_phase_events_with_diagnostics(rows)[0]


def phase_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    unique, probable_duplicates = unique_phase_events_with_diagnostics(rows)
    active = [row for row in unique if row.get("phase") != "human_wait"]
    phase_agent: Counter[str] = Counter()
    phase_wall: dict[str, float] = {}
    purpose_agent: Counter[str] = Counter()
    for row in unique:
        phase = str(row.get("phase", "unknown"))
        phase_agent[phase] += float(row.get("duration_seconds", 0.0) or 0.0)
        purpose = str(row.get("phase_purpose", "")).strip()
        if purpose:
            purpose_agent[f"{phase}:{purpose}"] += float(row.get("duration_seconds", 0.0) or 0.0)
    for phase in phase_agent:
        phase_wall[phase] = interval_union_seconds(
            [row for row in unique if str(row.get("phase")) == phase]
        )
    token_usage: Counter[str] = Counter()
    phase_tokens: dict[str, Counter[str]] = defaultdict(Counter)
    for row in unique:
        phase = str(row.get("phase", "unknown"))
        for field in TOKEN_FIELDS:
            value = int(row.get(field, 0) or 0)
            token_usage[field] += value
            phase_tokens[phase][field] += value
    # Every non-wait phase may be driven by an agent or model invocation.
    # Excluding render, TTS, and ASR made "100% token coverage" compatible
    # with missing some of the most expensive work.
    token_expected = list(active)
    aggregate = sum(float(row.get("duration_seconds", 0.0) or 0.0) for row in active)
    critical = interval_union_seconds(active)
    active_total = max(sum(phase_wall.values()), 1e-9)
    hotspots = [
        {
            "phase": phase,
            "wall_seconds": round(seconds, 3),
            "share_of_phase_wall": round(seconds / active_total, 4),
        }
        for phase, seconds in sorted(phase_wall.items(), key=lambda item: (-item[1], item[0]))
        if phase != "human_wait"
    ]
    retry_purposes = {
        "pronunciation_retry",
        "script_change_after_readiness",
        "technical_retry",
        "repair_rerender",
    }
    avoidable_retry_seconds = sum(
        float(row.get("duration_seconds", 0.0) or 0.0)
        for row in active
        if str(row.get("phase_purpose", "")) in retry_purposes
    )
    return {
        "unique_events": unique,
        "probable_shared_duplicates": probable_duplicates,
        "aggregate_agent_seconds": aggregate,
        "critical_path_seconds": critical,
        "concurrency_overlap_seconds": max(0.0, aggregate - critical),
        "human_wait_seconds": phase_agent.get("human_wait", 0.0),
        "phase_agent_seconds": dict(phase_agent),
        "phase_wall_seconds": phase_wall,
        "phase_purpose_agent_seconds": dict(purpose_agent),
        "phase_hotspots": hotspots,
        "avoidable_retry_seconds": avoidable_retry_seconds,
        "token_usage": dict(token_usage),
        "phase_token_usage": {
            phase: dict(counts) for phase, counts in sorted(phase_tokens.items())
        },
        "token_observability": {
            "applicable": bool(token_expected),
            "expected_events": len(token_expected),
            "observed_events": sum(row.get("token_observed") is True for row in token_expected),
            "coverage": round(
                sum(row.get("token_observed") is True for row in token_expected)
                / len(token_expected),
                4,
            )
            if token_expected
            else 0.0,
            "missing_event_ids": [
                row.get("event_id")
                for row in token_expected
                if row.get("token_observed") is not True
            ],
        },
    }


GATE_ERROR_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("stale_or_hash", ("stale", "hash", "another manifest", "another frozen candidate")),
    ("identity_or_authority", ("agent_id", "owner", "review role", "authority", "reviewer")),
    ("repair_binding", ("repair", "pending_repairs", "previous review")),
    ("artifact_or_evidence", ("artifact", "frame", "evidence", "source anchor", "qc")),
    (
        "schema_or_contract",
        ("schema", "contract", "requires", "missing", "must remain open", "coverage sweep", "coverage"),
    ),
    ("layout", ("layout", "overlap", "subtitle", "bbox", "spacing", "out of frame")),
    ("math_object", ("math", "invariant", "coordinate", "driver", "mapping")),
    ("timing_attention", ("timing", "timestamp", "anchor", "attention", "transition")),
    ("novice_causality", ("novice", "teach-back", "teach back", "causality", "prediction")),
)


def classify_gate_error(message: str) -> str:
    normalized = str(message).lower()
    for category, patterns in GATE_ERROR_PATTERNS:
        if any(pattern in normalized for pattern in patterns):
            return category
    return "other"


def classify_gate_errors(errors: Iterable[str]) -> dict[str, int]:
    counts: Counter[str] = Counter(classify_gate_error(error) for error in errors)
    return dict(sorted(counts.items()))


def classify_finding(finding: dict[str, Any]) -> str:
    joined = " ".join(
        str(finding.get(key, ""))
        for key in (
            "standard_key",
            "pattern_key",
            "problem",
            "impact",
            "suggested_fix",
        )
    )
    category = classify_gate_error(joined)
    return "visual_or_semantic" if category in {"other", "schema_or_contract"} else category


def classify_findings(findings: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter(
        classify_finding(finding) for finding in findings if isinstance(finding, dict)
    )
    return dict(sorted(counts.items()))
