#!/usr/bin/env python3
"""Validate the structure and minimum handoff contract of an evaluation pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_FILES = (
    "run-manifest.json",
    "observations.jsonl",
    "retrospective.md",
    "evidence-index.json",
    "evaluation-handoff.json",
)

REQUIRED_STATE_EXPORT_FILES = (
    "manifest.json",
    "aggregates.json",
    "events.jsonl",
    "commands.jsonl",
    "capsules.jsonl",
    "integrity.json",
    "metrics.json",
)

OBSERVATION_REQUIRED = {
    "schema",
    "observation_id",
    "recorded_at",
    "run_id",
    "episode_id",
    "reporter",
    "surface",
    "category",
    "severity",
    "summary",
    "expected",
    "observed",
    "evidence_refs",
    "impact",
    "recovery",
    "status",
}

RETROSPECTIVE_HEADINGS = (
    "## 1. Production outcome and authority state",
    "## 2. Evidence coverage and unknowns",
    "## 4. Human interventions",
    "## 5. Agent-interface friendliness",
    "## 6. Context precision",
    "## 7. State stability, determinism and isolation",
    "## 8. Failure and recovery episodes",
    "## 9. Confounds and emergency changes",
    "## 10. Freeze and handoff declaration",
)


def load_json(path: Path, errors: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path.name}: {exc}")
        return None


def resolve_in_run(run_dir: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path.resolve() if path.is_absolute() else (run_dir / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--ready", action="store_true")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    for filename in REQUIRED_FILES:
        if not (run_dir / filename).is_file():
            errors.append(f"missing required file: {filename}")

    if errors:
        print(json.dumps({"status": "fail", "errors": errors, "warnings": warnings}, indent=2))
        return 1

    manifest = load_json(run_dir / "run-manifest.json", errors)
    handoff = load_json(run_dir / "evaluation-handoff.json", errors)
    evidence = load_json(run_dir / "evidence-index.json", errors)

    observation_ids: set[str] = set()
    observation_count = 0
    for line_number, raw_line in enumerate(
        (run_dir / "observations.jsonl").read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        observation_count += 1
        try:
            item = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            errors.append(f"observations.jsonl:{line_number}: {exc}")
            continue
        missing = sorted(OBSERVATION_REQUIRED - set(item))
        if missing:
            errors.append(f"observations.jsonl:{line_number}: missing {missing}")
        observation_id = item.get("observation_id")
        if observation_id in observation_ids:
            errors.append(f"observations.jsonl:{line_number}: duplicate observation_id {observation_id}")
        if observation_id:
            observation_ids.add(observation_id)

    retrospective = (run_dir / "retrospective.md").read_text(encoding="utf-8")
    for heading in RETROSPECTIVE_HEADINGS:
        if heading not in retrospective:
            errors.append(f"retrospective.md: missing heading {heading}")
    if "## Changes applied in this retrospective" in retrospective:
        errors.append("retrospective.md: production Session must not apply state-system optimization")

    if manifest:
        if manifest.get("schema") != "state-supervision-episode-run-manifest-v1":
            errors.append("run-manifest.json: unexpected schema")
        policy = manifest.get("evaluation_policy", {})
        if policy.get("system_optimization_by_production_session") is not False:
            errors.append("run-manifest.json: optimization boundary must remain false")
        if policy.get("collect_hidden_chain_of_thought") is not False:
            errors.append("run-manifest.json: hidden chain-of-thought collection must remain false")
        if policy.get("collect_unrelated_screen_or_keystroke_history") is not False:
            errors.append("run-manifest.json: unrelated screen/keystroke collection must remain false")

    if handoff:
        if handoff.get("schema") != "state-supervision-evaluation-handoff-v1":
            errors.append("evaluation-handoff.json: unexpected schema")
        if handoff.get("system_optimization_applied_by_production_session") is not False:
            confounds = handoff.get("confounds") or []
            emergency = handoff.get("emergency_system_changes") or []
            if not confounds or not emergency:
                errors.append("evaluation-handoff.json: emergency optimization requires confound and change evidence")
        if args.ready and handoff.get("status") != "evaluation_ready":
            errors.append("evaluation-handoff.json: --ready requires status=evaluation_ready")

    if args.ready:
        if manifest and not manifest.get("ended_at"):
            errors.append("run-manifest.json: --ready requires ended_at")
        if evidence and not evidence.get("generated_at"):
            errors.append("evidence-index.json: --ready requires generated_at")
        if "Pack status: `evaluation_ready`" not in retrospective:
            errors.append("retrospective.md: --ready requires frozen evaluation_ready declaration")
        if manifest:
            state_system = manifest.get("state_system") or {}
            if not state_system.get("version") or str(state_system.get("version")).startswith("__"):
                errors.append("run-manifest.json: --ready requires an exact frozen state-system version")
            instrumentation = manifest.get("instrumentation") or {}
            export_dir = resolve_in_run(run_dir, instrumentation.get("state_export_dir"))
            if export_dir is None:
                errors.append("run-manifest.json: --ready requires instrumentation.state_export_dir")
            elif not export_dir.is_dir():
                errors.append(f"missing frozen state export directory: {export_dir}")
            else:
                for filename in REQUIRED_STATE_EXPORT_FILES:
                    if not (export_dir / filename).is_file():
                        errors.append(f"missing frozen state export file: {filename}")
                metrics_path = export_dir / "metrics.json"
                integrity_path = export_dir / "integrity.json"
                if metrics_path.is_file():
                    metrics = load_json(metrics_path, errors)
                    if metrics:
                        if metrics.get("schema") != "lecture-state-supervision-export-metrics-v1":
                            errors.append("metrics.json: unexpected schema")
                        for section in (
                            "time_and_flow",
                            "parallel_dispatch",
                            "agent_activity",
                            "human_activity",
                            "attention_delivery",
                            "quality_and_rework",
                            "change_and_recovery",
                            "reliability",
                            "coverage",
                            "unknown_metrics",
                        ):
                            if section not in metrics:
                                errors.append(f"metrics.json: missing {section}")
                if integrity_path.is_file():
                    integrity = load_json(integrity_path, errors)
                    if integrity and integrity.get("ok") is not True:
                        errors.append("integrity.json: frozen state did not pass integrity verification")
        if handoff:
            authority = (handoff.get("production_outcome") or {}).get("user_authority_state")
            if authority in (None, "", "not_recorded"):
                errors.append("evaluation-handoff.json: --ready requires explicit user_authority_state")

    if observation_count == 0:
        warnings.append("no structured observations recorded; confirm this is real absence, not missing telemetry")

    report = {
        "status": "pass" if not errors else "fail",
        "run_dir": str(run_dir),
        "observation_count": observation_count,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
