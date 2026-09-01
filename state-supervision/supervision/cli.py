"""Friendly Agent CLI: small verbs over one shared supervision backend."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from .core import DomainError, utc_now
from .service import SupervisionService
from .store import DataRoot


def repo_json_file(repo_root: str, raw_path: str) -> Any:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path(repo_root).expanduser() / path
    try:
        return json.loads(path.resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DomainError(
            "json_input_invalid",
            f"cannot read repository-relative JSON {raw_path}: {exc}",
            "json_input_repo_relative",
            allowed_next=("explain",),
            details={"path": raw_path, "repo_root": str(Path(repo_root).resolve())},
        ) from exc


def hydrate_json_arguments(arguments: argparse.Namespace) -> None:
    """Resolve every file-valued JSON argument against one documented root."""

    for field in ("budget", "spec", "selector"):
        value = getattr(arguments, field, None)
        if isinstance(value, str):
            setattr(arguments, field, repo_json_file(arguments.repo_root, value))


def _agent_operation(result: dict[str, Any], selected: dict[str, Any] | None) -> dict[str, Any]:
    """Compile one scheduler decision into an unambiguous logical operation."""

    if not selected:
        return {"verb": "wait", "arguments": {}, "returns": "a new state event"}
    action = selected.get("action")
    task = selected.get("task") or {}
    task_id = task.get("task_id")
    episode_id = result.get("episode_id")
    if action in {"work", "reclaim", "return_rework"}:
        return {
            "verb": "begin",
            "arguments": {
                "episode_id": episode_id,
                "task_id": task_id,
                "expected_version": selected.get("task_version"),
            },
            "returns": "exact version-bound context capsule and lease",
        }
    if action == "continue":
        return {
            "verb": "continue_current_lease",
            "arguments": {"task_id": task_id},
            "returns": "no new context unless the scope revision changed",
        }
    if action == "gate":
        return {
            "verb": "gate-run",
            "arguments": {
                "episode_id": episode_id,
                "task_id": task_id,
                "validators": [
                    item.get("validator_id") if isinstance(item, dict) else item
                    for item in selected.get("missing_validators", [])
                ],
            },
            "returns": "version-pinned gate receipts",
        }
    if action == "review":
        return {
            "verb": "review-context",
            "arguments": {"episode_id": episode_id, "task_id": task_id},
            "returns": "independent review capsule",
        }
    if action == "human_review":
        return {
            "verb": "wait_for_human",
            "arguments": {"task_id": task_id},
            "returns": "non-delegable user decision",
        }
    if action == "episode_replan":
        return {
            "verb": "replan",
            "arguments": {"episode_id": episode_id},
            "returns": "reasoned budget or route decision",
        }
    return {
        "verb": action,
        "arguments": {"episode_id": episode_id, "task_id": task_id},
        "returns": "operation-specific result",
    }


def agent_next_projection(result: dict[str, Any]) -> dict[str, Any]:
    """Default deterministic attention envelope; diagnostics remain opt-in."""

    selected = result.get("next")
    compact_selected = None
    if isinstance(selected, dict):
        task = selected.get("task") or {}
        task_budget = task.get("budget") or {}
        compact_selected = {
            "action": selected.get("action"),
            "focus": (
                {
                    key: task.get(key)
                    for key in (
                        "task_id",
                        "title",
                        "status",
                        "kind",
                        "role",
                        "content_unit_id",
                        "deliverable_id",
                        "scope_revision",
                    )
                }
                if task
                else None
            ),
            "operation": _agent_operation(result, selected),
            "why_now": {
                "deterministic_rank": selected.get("rank"),
                "critical_path": bool(task.get("critical_path")),
                "unlock_value": task.get("unlock_value"),
                "priority": task.get("priority"),
                "selection_policy": result.get("selection_policy"),
            },
            "execution_limits": {
                key: task_budget.get(key)
                for key in (
                    "soft_active_seconds",
                    "hard_active_seconds",
                    "max_attempts",
                    "max_no_progress_heartbeats",
                )
            },
            "missing_validators": [
                item.get("validator_id") if isinstance(item, dict) else item
                for item in selected.get("missing_validators", [])
            ],
            "return_ticket": selected.get("return_ticket"),
            "reasons": selected.get("reasons", []),
        }
    budget = result.get("budget_state") or {}
    other_actionable_count = len(result.get("other_actionable", []))
    excluded_count = len(result.get("excluded", []))
    return {
        "schema": "agent-attention-envelope-v2",
        "ok": result.get("ok", True),
        "status": result.get("status", "read_only"),
        "episode_id": result.get("episode_id"),
        "actor": result.get("actor"),
        "role": result.get("role"),
        "cursor": result.get("cursor"),
        "attention": compact_selected,
        "context_boundary": {
            "read_now": ["this envelope"],
            "read_on_begin": "exact context capsule with goal, contract, stop conditions, references, feedback and state cursor",
            "omitted_now": [
                "full topology",
                f"{excluded_count} scheduler-excluded tasks",
                f"{other_actionable_count} lower-ranked actionable tasks",
                "reference file contents before claim",
            ],
            "deferred_returns": result.get("deferred_returns", {}),
        },
        "budget_guard": {
            key: budget.get(key)
            for key in (
                "hard_stop",
                "production_envelope_exhausted",
                "closure_reserve_available",
            )
        },
        "incremental_read": {
            "verb": "events",
            "arguments": {"episode_id": result.get("episode_id"), "after": result.get("cursor")},
        },
        "targeted_diagnostic": {
            "verb": "explain",
            "arguments": {"episode_id": result.get("episode_id"), "target_id": "<target-id>"},
        },
    }


def parse_artifact(value: str) -> dict[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("artifact must use ROLE=PATH")
    role, path = value.split("=", 1)
    if not role.strip() or not path.strip():
        raise argparse.ArgumentTypeError("artifact must use non-empty ROLE=PATH")
    return {"role": role.strip(), "path": path.strip()}


def add_episode_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("episode_id", help="stable episode id")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="supervise",
        description="Deterministic lecture-production state supervision",
    )
    parser.add_argument(
        "--data-root",
        default=os.environ.get("LECTURE_STATE_ROOT", ".lecture-state"),
        help="runtime state directory (default: .lecture-state)",
    )
    parser.add_argument(
        "--repo-root",
        default=os.environ.get("LECTURE_REPO_ROOT", "."),
        help="repository root used to resolve artifact/reference paths",
    )
    parser.add_argument(
        "--actor",
        default=os.environ.get("LECTURE_ACTOR", "agent"),
        help="stable actor identity",
    )
    parser.add_argument("--request-id", help="idempotency key; reuse only for the exact same command")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    subparsers = parser.add_subparsers(dest="verb", required=True)

    command = subparsers.add_parser("episode-create", aliases=["init"], help="create an isolated episode store")
    add_episode_argument(command)
    command.add_argument("--title", required=True)
    command.add_argument("--mission", required=True)
    command.add_argument("--production-mode", default="supervised")
    command.add_argument("--budget", help="episode macro budget JSON, relative to --repo-root")

    command = subparsers.add_parser("episode-budget", help="reasoned macro budget replan")
    add_episode_argument(command)
    command.add_argument("--reason", required=True)
    command.add_argument("--budget", required=True, help="budget JSON, relative to --repo-root")

    command = subparsers.add_parser("dispatch-policy", help="configure bounded on-demand Agent concurrency")
    add_episode_argument(command)
    command.add_argument("--reason", required=True)
    command.add_argument("--max-active-authors", required=True, type=int)
    command.add_argument("--reviewer-capacity", required=True, type=int)
    command.add_argument("--mode", choices=["elastic", "fixed"], default="elastic")

    command = subparsers.add_parser(
        "dispatch-reserve",
        help="atomically reserve runnable tasks for distinct online Agents",
    )
    add_episode_argument(command)
    command.add_argument("--reason", required=True)
    command.add_argument(
        "--assignment",
        action="append",
        default=[],
        required=True,
        metavar="TASK_ID=AGENT_ID",
    )
    command.add_argument("--ttl-seconds", type=int, default=15 * 60)

    command = subparsers.add_parser(
        "agent-register",
        help="seal one stable roster identity and its machine-checkable capabilities",
    )
    add_episode_argument(command)
    command.add_argument("agent_id")
    command.add_argument("--role", required=True)
    command.add_argument("--capability", action="append", default=[], required=True)
    command.add_argument("--model", default="unspecified")
    command.add_argument(
        "--presence",
        choices=["planned", "online", "offline", "retired"],
        default="planned",
    )
    command.add_argument("--runtime-handle")

    command = subparsers.add_parser(
        "agent-presence",
        help="record a roster identity as planned, online, offline, or retired",
    )
    add_episode_argument(command)
    command.add_argument("agent_id")
    command.add_argument(
        "--presence",
        choices=["planned", "online", "offline", "retired"],
        required=True,
    )
    command.add_argument("--runtime-handle")

    command = subparsers.add_parser(
        "agent-probe",
        help="derive legal idle, illegal idle, productive work, or fake-busy risk",
    )
    add_episode_argument(command)
    command.add_argument("agent_id")

    subparsers.add_parser("episodes", help="list episode catalog")
    subparsers.add_parser("catalog-rebuild", help="rebuild the disposable episode catalog")

    command = subparsers.add_parser("wave-add", help="add a hierarchy wave")
    add_episode_argument(command)
    command.add_argument("wave_id")
    command.add_argument("--title", required=True)
    command.add_argument("--order", type=int, default=0)

    command = subparsers.add_parser("scene-add", help="add a scene under a wave")
    add_episode_argument(command)
    command.add_argument("scene_id")
    command.add_argument("--wave", required=True)
    command.add_argument("--title", required=True)
    command.add_argument("--order", type=int, default=0)

    command = subparsers.add_parser(
        "content-add",
        help="add one bounded content-scale unit such as a scene or animation beat",
    )
    add_episode_argument(command)
    command.add_argument("unit_id")
    command.add_argument("--title", required=True)
    command.add_argument("--kind", required=True)
    command.add_argument("--parent")
    command.add_argument("--order", type=int, default=0)

    command = subparsers.add_parser(
        "deliverable-add",
        help="add one deliverable-stream node; containment does not imply execution order",
    )
    add_episode_argument(command)
    command.add_argument("deliverable_id")
    command.add_argument("--title", required=True)
    command.add_argument("--parent")
    command.add_argument("--artifact-role", action="append", default=[])
    command.add_argument("--order", type=int, default=0)

    command = subparsers.add_parser("task-add", aliases=["add-task"], help="add one bounded task contract")
    add_episode_argument(command)
    command.add_argument("task_id", nargs="?")
    command.add_argument("--spec", help="JSON task spec relative to --repo-root; command flags override nothing")
    command.add_argument("--title")
    command.add_argument("--goal")
    command.add_argument("--wave")
    command.add_argument("--scene")
    command.add_argument("--content-unit")
    command.add_argument("--deliverable")
    command.add_argument(
        "--work-key",
        help="stable semantic obligation; duplicate live work keys are rejected",
    )
    command.add_argument("--kind", default="production")
    command.add_argument("--role", default="author")
    command.add_argument("--depends-on", action="append", default=[])
    command.add_argument("--reference", action="append", default=[])
    command.add_argument("--requires", action="append", default=[], help="required output artifact role")
    command.add_argument("--input-artifact", action="append", default=[])
    command.add_argument("--critical-path", action="store_true")
    command.add_argument("--unlock-value", type=int, default=0)
    command.add_argument("--priority", type=int, default=0)
    command.add_argument("--human-gate", action="store_true")
    command.add_argument("--tag", action="append", default=[])
    command.add_argument("--allow-side-effect", action="append", default=[])
    command.add_argument("--stop-condition", action="append", default=[])
    command.add_argument("--validator", action="append", default=[], help="pinned validator manifest path")

    command = subparsers.add_parser(
        "validator-rebind",
        help="replace one validator pin after an explicit version or code change",
    )
    add_episode_argument(command)
    command.add_argument("task_id")
    command.add_argument("validator_id")
    command.add_argument("--manifest", required=True)
    command.add_argument("--allow-canary", action="store_true")
    command.add_argument("--reason", required=True)

    command = subparsers.add_parser(
        "reference-rebind",
        help="adopt one reviewed reference revision and issue a fresh task capsule",
    )
    add_episode_argument(command)
    command.add_argument("task_id")
    command.add_argument("reference_id")
    command.add_argument("--path", required=True)
    command.add_argument("--reason", required=True)
    command.add_argument("--purpose")
    command.add_argument(
        "--selector",
        help="optional JSON selector relative to --repo-root; omitted preserves the prior selector",
    )
    command.add_argument(
        "--context-class",
        choices=["stable_rule", "task_template", "episode_material", "temporary_override", "runtime_fact"],
    )
    command.add_argument("--context-version")
    command.add_argument("--context-slot")
    command.add_argument("--assembly-mode", choices=["append", "replace"])
    command.add_argument("--precedence", type=int)
    command.add_argument("--scope")
    command.add_argument("--service-binding")
    command.add_argument("--mutable", action=argparse.BooleanOptionalAction, default=None)

    command = subparsers.add_parser("feedback-add", help="activate a reusable feedback rule")
    add_episode_argument(command)
    command.add_argument("feedback_id")
    command.add_argument("--pattern-key", required=True)
    command.add_argument("--instruction", required=True)
    command.add_argument("--source", default="human_review")
    command.add_argument("--applies-to", action="append", default=[])

    command = subparsers.add_parser("next", help="read the one best next action; never mutates domain state")
    add_episode_argument(command)
    command.add_argument("--role", default="agent", choices=["agent", "author", "reviewer", "human", "user"])
    command.add_argument("--details", action="store_true", help="include all alternatives and exclusions for supervisor diagnosis")

    command = subparsers.add_parser("begin", help="claim a task and receive its exact context capsule")
    add_episode_argument(command)
    command.add_argument("task_id")
    command.add_argument("--expected-version", type=int)

    command = subparsers.add_parser(
        "context-preview",
        help="compile the exact next context capsule without claiming the task",
    )
    add_episode_argument(command)
    command.add_argument("task_id")

    command = subparsers.add_parser(
        "context-override",
        help="append or replace one auditable runtime context block",
    )
    add_episode_argument(command)
    command.add_argument("task_id")
    command.add_argument("--instruction", required=True)
    command.add_argument("--label", default="临时要求")
    command.add_argument(
        "--scope",
        choices=["attempt", "task", "content_unit", "episode"],
        default="task",
    )
    command.add_argument(
        "--assembly-mode",
        choices=["append", "replace"],
        default="append",
    )
    command.add_argument("--context-slot", default="temporary.instructions")
    command.add_argument(
        "--delivery-policy",
        choices=["attention_boundary", "next_attempt", "immediate"],
        default="attention_boundary",
    )
    command.add_argument("--precedence", type=int, default=700)

    command = subparsers.add_parser("heartbeat", help="renew a live lease; notes alone are not progress")
    add_episode_argument(command)
    command.add_argument("task_id")
    command.add_argument("--generation", type=int)
    command.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="existing path/file:PATH, artifact ID, or event ID proving progress",
    )
    command.add_argument("--input-tokens", type=int, default=0)
    command.add_argument("--output-tokens", type=int, default=0)
    command.add_argument("--reasoning-tokens", type=int, default=0)
    command.add_argument("--note", default="")

    command = subparsers.add_parser("submit", help="submit exact content-addressed artifacts")
    add_episode_argument(command)
    command.add_argument("task_id")
    command.add_argument("--generation", type=int)
    command.add_argument("--artifact", action="append", type=parse_artifact, default=[], required=True)
    command.add_argument("--note", default="")

    command = subparsers.add_parser("gate-run", help="run one version-pinned hard quality gate")
    add_episode_argument(command)
    command.add_argument("task_id")
    command.add_argument("validator_id")

    command = subparsers.add_parser(
        "review-context",
        help="read the exact candidate, rules, feedback and evidence for review",
    )
    add_episode_argument(command)
    command.add_argument("task_id")

    command = subparsers.add_parser("review", help="independently review a candidate")
    add_episode_argument(command)
    command.add_argument("task_id")
    command.add_argument("--verdict", choices=["pass", "revise"], required=True)
    command.add_argument("--finding", action="append", default=[])
    command.add_argument("--note", default="")
    command.add_argument("--context-hash")
    command.add_argument(
        "--return-to",
        help="on revise, route the deferred return to this Agent; defaults to the original author",
    )

    command = subparsers.add_parser(
        "return-route",
        help="reroute one pending, attention-safe return ticket to another Agent",
    )
    add_episode_argument(command)
    command.add_argument("return_ticket_id")
    command.add_argument("--to", dest="to_actor", required=True)
    command.add_argument("--reason", required=True)

    command = subparsers.add_parser("human-decide", help="exercise the explicit user review gate")
    add_episode_argument(command)
    command.add_argument("task_id")
    command.add_argument("--verdict", choices=["approve", "revise"], required=True)
    command.add_argument("--note", default="")

    command = subparsers.add_parser("change", help="record a scope/artifact change and derive impact")
    add_episode_argument(command)
    command.add_argument("target_id")
    command.add_argument("--reason", required=True)
    command.add_argument("--kind", default="scope_change")

    command = subparsers.add_parser(
        "route-switch",
        help="atomically replace one production strategy behind the same output contract",
    )
    add_episode_argument(command)
    command.add_argument("replaced_task_id")
    command.add_argument("replacement_task_id")
    command.add_argument("--strategy", required=True, help="named replacement method, for example direct_recording")
    command.add_argument("--reason", required=True)
    command.add_argument(
        "--spec",
        required=True,
        help="replacement task JSON relative to --repo-root; title and goal required, stable output roles default to the old task",
    )

    command = subparsers.add_parser("gap", help="record missing context/capability and block safely")
    add_episode_argument(command)
    command.add_argument("task_id")
    command.add_argument("--reason", required=True)
    command.add_argument("--kind", default="missing_input")

    command = subparsers.add_parser("gap-resolve", help="resolve a known gap explicitly")
    add_episode_argument(command)
    command.add_argument("gap_id")
    command.add_argument("--resolution", required=True)

    command = subparsers.add_parser("replan", help="authorize a bounded budget/attempt replan")
    add_episode_argument(command)
    command.add_argument("task_id")
    command.add_argument("--reason", required=True)
    command.add_argument("--budget", help="budget JSON relative to --repo-root containing only supported fields")

    command = subparsers.add_parser("annotate", help="attach a human-visible note without silently mutating work")
    add_episode_argument(command)
    command.add_argument("target_id")
    command.add_argument("--body", required=True)
    command.add_argument("--severity", default="note", choices=["note", "info", "warning", "blocker"])

    command = subparsers.add_parser("observe", help="record usability, ambiguity, recovery, or context-test evidence")
    add_episode_argument(command)
    command.add_argument("--category", required=True)
    command.add_argument("--summary", required=True)
    command.add_argument("--task")
    command.add_argument("--severity", default="medium", choices=["low", "medium", "high", "critical"])
    command.add_argument("--expectation", default="")
    command.add_argument("--actual", default="")

    command = subparsers.add_parser("export", help="freeze a portable evidence bundle for retrospective evaluation")
    add_episode_argument(command)
    command.add_argument("--output", required=True)

    command = subparsers.add_parser("explain", help="read state, causes, evidence lineage, and allowed actions")
    add_episode_argument(command)
    command.add_argument("target_id", nargs="?")

    command = subparsers.add_parser(
        "overview",
        help="read the multi-scale content x deliverable projection and live work graph",
    )
    add_episode_argument(command)

    command = subparsers.add_parser("events", help="read only incremental events after a cursor")
    add_episode_argument(command)
    command.add_argument("--after", type=int, default=0)
    command.add_argument("--limit", type=int, default=500)

    command = subparsers.add_parser("scan", help="detect anomalies without changing state")
    add_episode_argument(command)
    command.add_argument("--deep", action="store_true", help="also hash every artifact")

    command = subparsers.add_parser("recover", help="preview or apply only safe local repairs")
    add_episode_argument(command)
    command.add_argument(
        "--apply",
        action="store_true",
        help="apply only repairs marked repairable; omission is a dry-run preview",
    )
    command.add_argument(
        "--deep",
        action="store_true",
        help="also verify artifact bytes before planning recovery",
    )
    return parser


def _task_spec(arguments: argparse.Namespace) -> dict[str, Any]:
    if arguments.spec is not None:
        if not isinstance(arguments.spec, dict):
            raise DomainError("invalid_task_spec", "task spec must be a JSON object", "task_spec_object")
        return dict(arguments.spec)
    if not arguments.task_id or not arguments.title or not arguments.goal:
        raise DomainError(
            "invalid_task_spec",
            "task-add needs task_id, --title, and --goal, or one --spec JSON file",
            "task_contract_explicit",
        )
    return {
        "task_id": arguments.task_id,
        "title": arguments.title,
        "goal": arguments.goal,
        "wave_id": arguments.wave,
        "scene_id": arguments.scene,
        "content_unit_id": arguments.content_unit,
        "deliverable_id": arguments.deliverable,
        "work_key": arguments.work_key,
        "kind": arguments.kind,
        "role": arguments.role,
        "dependencies": arguments.depends_on,
        "references": arguments.reference,
        "required_artifact_roles": arguments.requires,
        "input_artifact_ids": arguments.input_artifact,
        "critical_path": arguments.critical_path,
        "unlock_value": arguments.unlock_value,
        "priority": arguments.priority,
        "human_gate": arguments.human_gate,
        "tags": arguments.tag,
        "allowed_side_effects": arguments.allow_side_effect,
        "stop_conditions": arguments.stop_condition,
        "validators": arguments.validator,
    }


def dispatch(arguments: argparse.Namespace) -> dict[str, Any] | list[dict[str, Any]]:
    data_root = DataRoot(Path(arguments.data_root))
    service = SupervisionService(data_root, Path(arguments.repo_root))
    common = {"actor": arguments.actor, "request_id": arguments.request_id}
    verb = arguments.verb
    if verb in {"episode-create", "init"}:
        return service.create_episode(
            episode_id=arguments.episode_id,
            title=arguments.title,
            mission=arguments.mission,
            production_mode=arguments.production_mode,
            budget=arguments.budget,
            **common,
        )
    if verb == "episode-budget":
        return service.configure_episode_budget(
            arguments.episode_id,
            reason=arguments.reason,
            budget_patch=arguments.budget,
            **common,
        )
    if verb == "dispatch-policy":
        return service.configure_dispatch_policy(
            arguments.episode_id,
            reason=arguments.reason,
            max_active_authors=arguments.max_active_authors,
            reviewer_capacity=arguments.reviewer_capacity,
            mode=arguments.mode,
            **common,
        )
    if verb == "dispatch-reserve":
        assignments = []
        for value in arguments.assignment:
            task_id, separator, agent_id = str(value).partition("=")
            if not separator or not task_id.strip() or not agent_id.strip():
                raise DomainError(
                    "invalid_dispatch_assignment",
                    "each --assignment must be TASK_ID=AGENT_ID",
                    "dispatch_assignment_shape",
                )
            assignments.append(
                {"task_id": task_id.strip(), "agent_id": agent_id.strip()}
            )
        return service.reserve_dispatch_tasks(
            arguments.episode_id,
            reason=arguments.reason,
            assignments=assignments,
            ttl_seconds=arguments.ttl_seconds,
            **common,
        )
    if verb == "agent-register":
        return service.register_agent(
            arguments.episode_id,
            agent_id=arguments.agent_id,
            role=arguments.role,
            capabilities=arguments.capability,
            model=arguments.model,
            presence=arguments.presence,
            runtime_handle=arguments.runtime_handle,
            **common,
        )
    if verb == "agent-presence":
        return service.set_agent_presence(
            arguments.episode_id,
            arguments.agent_id,
            presence=arguments.presence,
            runtime_handle=arguments.runtime_handle,
            **common,
        )
    if verb == "agent-probe":
        return service.agent_probe(arguments.episode_id, arguments.agent_id)
    if verb == "episodes":
        return {"ok": True, "status": "read_only", "episodes": data_root.list_episodes()}
    if verb == "catalog-rebuild":
        return data_root.rebuild_catalog()
    if verb == "wave-add":
        return service.add_wave(arguments.episode_id, wave_id=arguments.wave_id, title=arguments.title, order=arguments.order, **common)
    if verb == "scene-add":
        return service.add_scene(
            arguments.episode_id,
            scene_id=arguments.scene_id,
            wave_id=arguments.wave,
            title=arguments.title,
            order=arguments.order,
            **common,
        )
    if verb == "content-add":
        return service.add_content_unit(
            arguments.episode_id,
            unit_id=arguments.unit_id,
            title=arguments.title,
            kind=arguments.kind,
            parent_unit_id=arguments.parent,
            order=arguments.order,
            **common,
        )
    if verb == "deliverable-add":
        return service.add_deliverable(
            arguments.episode_id,
            deliverable_id=arguments.deliverable_id,
            title=arguments.title,
            parent_deliverable_id=arguments.parent,
            artifact_roles=arguments.artifact_role,
            order=arguments.order,
            **common,
        )
    if verb in {"task-add", "add-task"}:
        spec = _task_spec(arguments)
        return service.add_task(arguments.episode_id, actor=arguments.actor, request_id=arguments.request_id, **spec)
    if verb == "validator-rebind":
        return service.rebind_validator(
            arguments.episode_id,
            arguments.task_id,
            arguments.validator_id,
            {
                "path": arguments.manifest,
                "allow_canary": arguments.allow_canary,
            },
            reason=arguments.reason,
            **common,
        )
    if verb == "reference-rebind":
        return service.rebind_reference(
            arguments.episode_id,
            arguments.task_id,
            arguments.reference_id,
            arguments.path,
            reason=arguments.reason,
            purpose=arguments.purpose,
            selector=arguments.selector,
            context_class=arguments.context_class,
            context_version=arguments.context_version,
            context_slot=arguments.context_slot,
            assembly_mode=arguments.assembly_mode,
            precedence=arguments.precedence,
            scope=arguments.scope,
            service_binding=arguments.service_binding,
            mutable=arguments.mutable,
            **common,
        )
    if verb == "feedback-add":
        return service.add_feedback(
            arguments.episode_id,
            feedback_id=arguments.feedback_id,
            pattern_key=arguments.pattern_key,
            instruction=arguments.instruction,
            source=arguments.source,
            applies_to=arguments.applies_to or ["*"],
            **common,
        )
    if verb == "next":
        result = service.next_action(arguments.episode_id, actor=arguments.actor, role=arguments.role)
        return result if arguments.details else agent_next_projection(result)
    if verb == "begin":
        return service.begin(
            arguments.episode_id,
            arguments.task_id,
            expected_version=arguments.expected_version,
            **common,
        )
    if verb == "context-preview":
        return service.preview_context(
            arguments.episode_id,
            arguments.task_id,
            actor=arguments.actor,
        )
    if verb == "context-override":
        return service.add_context_override(
            arguments.episode_id,
            arguments.task_id,
            actor=arguments.actor,
            instruction=arguments.instruction,
            label=arguments.label,
            scope=arguments.scope,
            assembly_mode=arguments.assembly_mode,
            context_slot=arguments.context_slot,
            delivery_policy=arguments.delivery_policy,
            precedence=arguments.precedence,
            request_id=arguments.request_id,
        )
    if verb == "heartbeat":
        return service.heartbeat(
            arguments.episode_id,
            arguments.task_id,
            generation=arguments.generation,
            evidence_refs=arguments.evidence,
            usage_delta={
                "input_tokens": arguments.input_tokens,
                "output_tokens": arguments.output_tokens,
                "reasoning_tokens": arguments.reasoning_tokens,
            },
            note=arguments.note,
            **common,
        )
    if verb == "submit":
        return service.submit(
            arguments.episode_id,
            arguments.task_id,
            artifacts=arguments.artifact,
            generation=arguments.generation,
            note=arguments.note,
            **common,
        )
    if verb == "gate-run":
        return service.run_gate(
            arguments.episode_id,
            arguments.task_id,
            arguments.validator_id,
            **common,
        )
    if verb == "review-context":
        return service.review_context(
            arguments.episode_id,
            arguments.task_id,
            actor=arguments.actor,
        )
    if verb == "review":
        return service.review(
            arguments.episode_id,
            arguments.task_id,
            verdict=arguments.verdict,
            findings=[{"description": item} for item in arguments.finding],
            note=arguments.note,
            review_context_hash=arguments.context_hash,
            return_to=arguments.return_to,
            **common,
        )
    if verb == "return-route":
        return service.reroute_return(
            arguments.episode_id,
            arguments.return_ticket_id,
            to_actor=arguments.to_actor,
            reason=arguments.reason,
            **common,
        )
    if verb == "human-decide":
        return service.human_decide(
            arguments.episode_id,
            arguments.task_id,
            verdict=arguments.verdict,
            note=arguments.note,
            **common,
        )
    if verb == "change":
        return service.change(
            arguments.episode_id,
            target_id=arguments.target_id,
            reason=arguments.reason,
            kind=arguments.kind,
            **common,
        )
    if verb == "route-switch":
        return service.switch_route(
            arguments.episode_id,
            arguments.replaced_task_id,
            arguments.replacement_task_id,
            strategy=arguments.strategy,
            reason=arguments.reason,
            replacement_spec=arguments.spec,
            **common,
        )
    if verb == "gap":
        return service.gap(
            arguments.episode_id,
            arguments.task_id,
            reason=arguments.reason,
            kind=arguments.kind,
            **common,
        )
    if verb == "gap-resolve":
        return service.resolve_gap(
            arguments.episode_id,
            arguments.gap_id,
            resolution=arguments.resolution,
            **common,
        )
    if verb == "replan":
        return service.replan(
            arguments.episode_id,
            arguments.task_id,
            reason=arguments.reason,
            budget_patch=arguments.budget,
            **common,
        )
    if verb == "annotate":
        return service.annotate(
            arguments.episode_id,
            target_id=arguments.target_id,
            body=arguments.body,
            severity=arguments.severity,
            **common,
        )
    if verb == "observe":
        return service.observe(
            arguments.episode_id,
            category=arguments.category,
            summary=arguments.summary,
            task_id=arguments.task,
            severity=arguments.severity,
            expectation=arguments.expectation,
            actual=arguments.actual,
            **common,
        )
    if verb == "export":
        return service.export(arguments.episode_id, Path(arguments.output))
    if verb == "explain":
        return service.explain(
            arguments.episode_id,
            arguments.target_id,
            actor=arguments.actor,
        )
    if verb == "overview":
        return {"ok": True, "status": "read_only", "overview": service.overview(arguments.episode_id)}
    if verb == "events":
        store = data_root.episode_store(arguments.episode_id)
        events = store.events_after(arguments.after, arguments.limit)
        return {
            "ok": True,
            "status": "read_only",
            "after": arguments.after,
            "cursor": events[-1]["seq"] if events else store.cursor(),
            "events": events,
        }
    if verb == "scan":
        return service.scan(arguments.episode_id, deep=arguments.deep)
    if verb == "recover":
        return service.recover(
            arguments.episode_id,
            actor=arguments.actor,
            apply=arguments.apply,
            deep=arguments.deep,
            request_id=arguments.request_id,
        )
    raise RuntimeError(f"unhandled verb {verb}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        hydrate_json_arguments(arguments)
        result = dispatch(arguments)
        indent = None if arguments.compact else 2
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=indent))
        if isinstance(result, dict) and result.get("ok") is False:
            return 2
        return 0
    except DomainError as error:
        result = {**error.as_result(), "command": arguments.verb, "occurred_at": utc_now()}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=None if arguments.compact else 2))
        return 2
    except Exception as error:
        result = {
            "ok": False,
            "status": "internal_error",
            "code": "internal_error",
            "command": arguments.verb,
            "message": str(error),
            "recovery": "Run scan/explain, preserve the episode database, and report this diagnostic.",
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=None if arguments.compact else 2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
