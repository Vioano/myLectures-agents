#!/usr/bin/env python3
"""Deterministic timeout and stagnation guard for one lecture task."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "lecture-animation-progress-guard-v1"
HASH_FIELD = "guard_hash"
ACTIVE = {"running", "warning"}
MEANINGFUL_KINDS = {
    "code_patch",
    "scene_plan",
    "playable_review",
    "qc_evidence",
    "review_verdict",
    "issue_transition",
    "state_advance",
    "portable_handoff",
    "final_media",
}
SIGNAL_TYPES = {
    "revise",
    "pattern_recurrence",
    "delivery_commitment",
    "dependency_wait",
    "dependency_progress",
    "scope_expansion",
}
SKIP_PARTS = {".git", "__pycache__", ".ipynb_checkpoints"}


class GuardError(RuntimeError):
    pass


def parse_time(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GuardError(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise GuardError("timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat()


def object_hash(value: dict[str, Any]) -> str:
    payload = {key: item for key, item in value.items() if key != HASH_FIELD}
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def seal(value: dict[str, Any]) -> None:
    value[HASH_FIELD] = object_hash(value)


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuardError(f"invalid guard state {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise GuardError(f"unsupported guard state: {path}")
    if data.get(HASH_FIELD) != object_hash(data):
        raise GuardError(f"guard state hash is invalid: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    seal(data)
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if (
            path.is_file()
            and not path.name.startswith("._")
            and path.name != ".DS_Store"
            and path.suffix != ".pyc"
            and not any(part in SKIP_PARTS for part in path.parts)
        ):
            yield path


def artifact_snapshot(path: Path) -> dict[str, Any]:
    if path.is_file():
        return {
            "kind": "file",
            "sha256": sha256(path),
            "size": path.stat().st_size,
            "file_count": 1,
        }
    if not path.is_dir():
        raise GuardError(f"artifact does not exist: {path}")
    digest = hashlib.sha256()
    size = 0
    count = 0
    for file_path in clean_files(path):
        relative = file_path.relative_to(path).as_posix()
        file_hash = sha256(file_path)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
        size += file_path.stat().st_size
        count += 1
    if count == 0:
        raise GuardError(f"artifact directory is empty: {path}")
    return {
        "kind": "directory",
        "sha256": digest.hexdigest(),
        "size": size,
        "file_count": count,
    }


def project_root(state_path: Path, state: dict[str, Any]) -> Path:
    root = (state_path.parent / state["project_root_rel"]).resolve()
    if not root.is_dir():
        raise GuardError(f"project root does not exist: {root}")
    return root


def inside(root: Path, candidate: Path, state_path: Path) -> Path:
    resolved = candidate.expanduser().resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise GuardError(f"artifact must stay inside project root: {resolved}") from exc
    if not resolved.exists():
        raise GuardError(f"artifact does not exist: {resolved}")
    if resolved == state_path or (resolved.is_dir() and state_path.is_relative_to(resolved)):
        raise GuardError("the progress-guard state cannot count as meaningful output")
    return resolved


def seconds_between(start: str, end: datetime) -> float:
    return max(0.0, (end - parse_time(start)).total_seconds())


def triggers_at(state: dict[str, Any], now: datetime) -> tuple[list[dict[str, Any]], bool]:
    if state["status"] not in ACTIVE:
        return state.get("active_triggers", []), False
    config = state["config"]
    elapsed = seconds_between(state["attempt_started_at"], now)
    idle = seconds_between(state["last_meaningful_at"], now)
    triggers: list[dict[str, Any]] = []
    warning = elapsed >= config["wall_budget_seconds"] * config["warning_fraction"]
    if elapsed >= config["wall_budget_seconds"]:
        triggers.append({"key": "wall_budget_exceeded", "observed_seconds": elapsed})
    if idle >= config["idle_budget_seconds"]:
        triggers.append({"key": "no_meaningful_output", "observed_seconds": idle})
    counters = state["live_counters"]
    if counters["consecutive_revise"] >= 2:
        triggers.append({"key": "repeated_revise", "count": counters["consecutive_revise"]})
    recurring = sorted(
        key for key, count in counters["pattern_counts"].items() if count >= 2
    )
    if recurring:
        triggers.append({"key": "same_pattern_recurred", "pattern_keys": recurring})
    if counters["artifact_churn_without_gate"] >= 3:
        triggers.append(
            {
                "key": "artifact_growth_without_state_advance",
                "count": counters["artifact_churn_without_gate"],
            }
        )
    commitment = state.get("delivery_commitment")
    if commitment and now >= parse_time(commitment["deadline"]):
        triggers.append(
            {"key": "delivery_commitment_missed", "deadline": commitment["deadline"]}
        )
    dependency = state.get("dependency_wait")
    if dependency:
        waited = seconds_between(dependency["started_at"], now)
        if waited >= config["dependency_wait_seconds"]:
            triggers.append({"key": "dependency_wait_stale", "observed_seconds": waited})
    if counters["unapproved_scope_expansion"]:
        triggers.append({"key": "unapproved_scope_expansion"})
    return triggers, warning


def evaluate(state: dict[str, Any], now: datetime) -> None:
    prior = state["status"]
    triggers, warning = triggers_at(state, now)
    state["last_checked_at"] = iso(now)
    state["active_triggers"] = triggers
    if triggers:
        state["status"] = "reflection_required"
        if prior != "reflection_required":
            state["history"].append(
                {"event": "reflection_required", "at": iso(now), "triggers": triggers}
            )
    elif warning:
        state["status"] = "warning"
    elif prior in ACTIVE:
        state["status"] = "running"


def active_state(path: Path) -> dict[str, Any]:
    state = read_json(path)
    if state["status"] == "reflection_required":
        raise GuardError("reflection_required: submit the diagnostic reflection before continuing")
    if state["status"] not in ACTIVE:
        raise GuardError(f"guard is not active: {state['status']}")
    return state


def command_init(args: argparse.Namespace) -> int:
    output = Path(args.state).expanduser().resolve()
    root = Path(args.project_root).expanduser().resolve()
    now = parse_time(args.now)
    if output.exists():
        raise GuardError(f"guard state already exists: {output}")
    if not root.is_dir():
        raise GuardError(f"project root does not exist: {root}")
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise GuardError("guard state must live inside the episode project root") from exc
    if min(args.wall_budget_seconds, args.idle_budget_seconds, args.dependency_wait_seconds) <= 0:
        raise GuardError("all time budgets must be positive")
    if not 0 < args.warning_fraction < 1:
        raise GuardError("warning_fraction must be between zero and one")
    if not args.next_minimal_action.strip():
        raise GuardError("next_minimal_action must be nonempty")
    state = {
        "schema": SCHEMA,
        "revision": 1,
        "task_key": args.task_key,
        "phase": args.phase,
        "project_root_rel": os.path.relpath(root, output.parent),
        "status": "running",
        "attempt": 1,
        "attempt_started_at": iso(now),
        "last_meaningful_at": iso(now),
        "last_checked_at": iso(now),
        "current_gate": args.gate,
        "next_minimal_action": args.next_minimal_action,
        "config": {
            "wall_budget_seconds": args.wall_budget_seconds,
            "idle_budget_seconds": args.idle_budget_seconds,
            "dependency_wait_seconds": args.dependency_wait_seconds,
            "warning_fraction": args.warning_fraction,
        },
        "artifacts": {},
        "live_counters": {
            "consecutive_revise": 0,
            "pattern_counts": {},
            "artifact_churn_without_gate": 0,
            "unapproved_scope_expansion": False,
        },
        "delivery_commitment": None,
        "dependency_wait": None,
        "active_triggers": [],
        "reflections": [],
        "history": [{"event": "init", "at": iso(now), "gate": args.gate}],
    }
    write_json(output, state)
    print(json.dumps({"status": state["status"], "state": str(output)}, ensure_ascii=False))
    return 0


def command_checkpoint(args: argparse.Namespace) -> int:
    state_path = Path(args.state).expanduser().resolve()
    state = active_state(state_path)
    now = parse_time(args.now)
    root = project_root(state_path, state)
    if args.kind not in MEANINGFUL_KINDS:
        raise GuardError(f"unsupported meaningful-output kind: {args.kind}")
    changed: list[dict[str, Any]] = []
    for value in args.artifact:
        artifact = inside(root, Path(value), state_path)
        relative = artifact.relative_to(root).as_posix()
        snapshot = artifact_snapshot(artifact)
        previous = state["artifacts"].get(relative, {}).get("sha256")
        state["artifacts"][relative] = {**snapshot, "kind_of_progress": args.kind, "at": iso(now)}
        if snapshot["sha256"] != previous:
            changed.append({"path": relative, **snapshot})
    if not changed:
        state["history"].append(
            {"event": "checkpoint_no_change", "at": iso(now), "summary": args.summary}
        )
    else:
        state["last_meaningful_at"] = iso(now)
        state["next_minimal_action"] = args.next_minimal_action
        if args.gate_advanced:
            state["current_gate"] = args.gate
            state["live_counters"]["artifact_churn_without_gate"] = 0
            state["live_counters"]["consecutive_revise"] = 0
        else:
            state["live_counters"]["artifact_churn_without_gate"] += 1
        state["history"].append(
            {
                "event": "meaningful_checkpoint",
                "at": iso(now),
                "kind": args.kind,
                "gate": args.gate,
                "gate_advanced": args.gate_advanced,
                "summary": args.summary,
                "artifacts": changed,
            }
        )
    evaluate(state, now)
    write_json(state_path, state)
    print(
        json.dumps(
            {"status": state["status"], "changed": changed, "triggers": state["active_triggers"]},
            ensure_ascii=False,
        )
    )
    return 2 if state["status"] == "reflection_required" else 0


def command_signal(args: argparse.Namespace) -> int:
    state_path = Path(args.state).expanduser().resolve()
    state = active_state(state_path)
    now = parse_time(args.now)
    event = args.event_type
    if event not in SIGNAL_TYPES:
        raise GuardError(f"unsupported signal: {event}")
    counters = state["live_counters"]
    if event == "revise":
        counters["consecutive_revise"] += 1
    elif event == "pattern_recurrence":
        if not args.pattern_key:
            raise GuardError("pattern_recurrence requires --pattern-key")
        counts = counters["pattern_counts"]
        counts[args.pattern_key] = counts.get(args.pattern_key, 0) + 1
    elif event == "delivery_commitment":
        if not args.deadline:
            raise GuardError("delivery_commitment requires --deadline")
        state["delivery_commitment"] = {
            "deadline": iso(parse_time(args.deadline)),
            "note": args.note,
        }
    elif event == "dependency_wait":
        state["dependency_wait"] = {"started_at": iso(now), "note": args.note}
    elif event == "dependency_progress":
        state["dependency_wait"] = None
        state["last_meaningful_at"] = iso(now)
    elif event == "scope_expansion" and not args.approved:
        counters["unapproved_scope_expansion"] = True
    state["history"].append({"event": event, "at": iso(now), "note": args.note})
    evaluate(state, now)
    write_json(state_path, state)
    print(json.dumps({"status": state["status"], "triggers": state["active_triggers"]}, ensure_ascii=False))
    return 2 if state["status"] == "reflection_required" else 0


def command_status(args: argparse.Namespace) -> int:
    state_path = Path(args.state).expanduser().resolve()
    state = read_json(state_path)
    now = parse_time(args.now)
    evaluate(state, now)
    write_json(state_path, state)
    print(
        json.dumps(
            {
                "status": state["status"],
                "task_key": state["task_key"],
                "gate": state["current_gate"],
                "next_minimal_action": state["next_minimal_action"],
                "triggers": state["active_triggers"],
            },
            ensure_ascii=False,
        )
    )
    return 2 if state["status"] == "reflection_required" else 0


def command_reflect(args: argparse.Namespace) -> int:
    state_path = Path(args.state).expanduser().resolve()
    state = read_json(state_path)
    now = parse_time(args.now)
    if state["status"] != "reflection_required":
        raise GuardError("reflection is accepted only in reflection_required")
    reflection = {
        "id": f"reflection-{len(state['reflections']) + 1:03d}",
        "at": iso(now),
        "triggers": state["active_triggers"],
        "blocked_gate": args.blocked_gate,
        "window_output": args.window_output,
        "invalid_assumption": args.invalid_assumption,
        "next_minimal_action": args.next_minimal_action,
        "path_decision": args.path_decision,
        "scope_boundary": args.scope_boundary,
    }
    if any(not str(value).strip() for key, value in reflection.items() if key not in {"triggers"}):
        raise GuardError("every reflection answer must be nonempty")
    state["reflections"].append(reflection)
    state["status"] = "replanned"
    state["history"].append({"event": "reflection_submitted", **reflection})
    write_json(state_path, state)
    print(json.dumps({"status": "replanned", "reflection_id": reflection["id"]}, ensure_ascii=False))
    return 0


def command_resume(args: argparse.Namespace) -> int:
    state_path = Path(args.state).expanduser().resolve()
    state = read_json(state_path)
    now = parse_time(args.now)
    if state["status"] != "replanned":
        raise GuardError("resume requires a submitted reflection")
    if not args.next_minimal_action.strip():
        raise GuardError("next_minimal_action must be nonempty")
    state["revision"] += 1
    state["attempt"] += 1
    state["status"] = "running"
    state["attempt_started_at"] = iso(now)
    state["last_meaningful_at"] = iso(now)
    state["last_checked_at"] = iso(now)
    state["next_minimal_action"] = args.next_minimal_action
    state["active_triggers"] = []
    state["delivery_commitment"] = None
    state["dependency_wait"] = None
    state["live_counters"] = {
        "consecutive_revise": 0,
        "pattern_counts": {},
        "artifact_churn_without_gate": 0,
        "unapproved_scope_expansion": False,
    }
    state["history"].append(
        {"event": "resume_after_replan", "at": iso(now), "next_minimal_action": args.next_minimal_action}
    )
    write_json(state_path, state)
    print(json.dumps({"status": "running", "attempt": state["attempt"]}, ensure_ascii=False))
    return 0


def command_complete(args: argparse.Namespace) -> int:
    state_path = Path(args.state).expanduser().resolve()
    state = active_state(state_path)
    now = parse_time(args.now)
    root = project_root(state_path, state)
    evidence = inside(root, Path(args.evidence), state_path)
    state["last_meaningful_at"] = iso(now)
    evaluate(state, now)
    if state["status"] == "reflection_required":
        write_json(state_path, state)
        print(json.dumps({"status": state["status"], "triggers": state["active_triggers"]}, ensure_ascii=False))
        return 2
    snapshot = artifact_snapshot(evidence)
    state["status"] = "completed"
    state["current_gate"] = args.gate
    state["active_triggers"] = []
    state["history"].append(
        {
            "event": "complete",
            "at": iso(now),
            "gate": args.gate,
            "evidence": evidence.relative_to(root).as_posix(),
            **snapshot,
        }
    )
    write_json(state_path, state)
    print(json.dumps({"status": "completed", "evidence": str(evidence)}, ensure_ascii=False))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--project-root", required=True)
    init.add_argument("--state", required=True)
    init.add_argument("--task-key", required=True)
    init.add_argument("--phase", required=True)
    init.add_argument("--gate", required=True)
    init.add_argument("--next-minimal-action", required=True)
    init.add_argument("--wall-budget-seconds", type=int, default=1800)
    init.add_argument("--idle-budget-seconds", type=int, default=900)
    init.add_argument("--dependency-wait-seconds", type=int, default=900)
    init.add_argument("--warning-fraction", type=float, default=0.75)
    init.add_argument("--now")
    init.set_defaults(func=command_init)

    checkpoint = sub.add_parser("checkpoint")
    checkpoint.add_argument("--state", required=True)
    checkpoint.add_argument("--kind", required=True)
    checkpoint.add_argument("--artifact", action="append", required=True)
    checkpoint.add_argument("--gate", required=True)
    checkpoint.add_argument("--gate-advanced", action="store_true")
    checkpoint.add_argument("--summary", required=True)
    checkpoint.add_argument("--next-minimal-action", required=True)
    checkpoint.add_argument("--now")
    checkpoint.set_defaults(func=command_checkpoint)

    signal = sub.add_parser("signal")
    signal.add_argument("--state", required=True)
    signal.add_argument("--event-type", required=True)
    signal.add_argument("--pattern-key")
    signal.add_argument("--deadline")
    signal.add_argument("--note", default="")
    signal.add_argument("--approved", action="store_true")
    signal.add_argument("--now")
    signal.set_defaults(func=command_signal)

    status = sub.add_parser("status")
    status.add_argument("--state", required=True)
    status.add_argument("--now")
    status.set_defaults(func=command_status)

    reflect = sub.add_parser("reflect")
    reflect.add_argument("--state", required=True)
    reflect.add_argument("--blocked-gate", required=True)
    reflect.add_argument("--window-output", required=True)
    reflect.add_argument("--invalid-assumption", required=True)
    reflect.add_argument("--next-minimal-action", required=True)
    reflect.add_argument(
        "--path-decision",
        required=True,
        choices=["continue", "change_strategy", "deliver_intermediate", "request_scope_change", "wait_external"],
    )
    reflect.add_argument("--scope-boundary", required=True)
    reflect.add_argument("--now")
    reflect.set_defaults(func=command_reflect)

    resume = sub.add_parser("resume")
    resume.add_argument("--state", required=True)
    resume.add_argument("--next-minimal-action", required=True)
    resume.add_argument("--now")
    resume.set_defaults(func=command_resume)

    complete = sub.add_parser("complete")
    complete.add_argument("--state", required=True)
    complete.add_argument("--evidence", required=True)
    complete.add_argument("--gate", required=True)
    complete.add_argument("--now")
    complete.set_defaults(func=command_complete)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return int(args.func(args) or 0)
    except GuardError as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
