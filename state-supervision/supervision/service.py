"""Application service exposing deterministic, friendly supervision operations."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import shutil
import sqlite3
import subprocess
from typing import Any, Callable
import wave

from .core import DomainError, file_hash, object_hash, require_identifier, utc_now
from .domain import (
    TERMINAL_TASK_STATUSES,
    TASK_STATUSES,
    add_seconds,
    bind_reference,
    compile_capsule,
    dependency_cycle,
    display_path,
    lease_is_live,
    parse_time,
    relevant_feedback_for_task,
    resolve_repo_path,
    scheduling_key,
    task_blockers,
    task_contract_conflicts,
    verify_reference,
)
from .store import DataRoot, EpisodeStore, Transaction
from .recovery import current_artifact_ids, scan_episode
from .exporter import export_episode
from .validators import bind_validator, execute_validator, verify_validator


DEFAULT_LEASE_SECONDS = 20 * 60
DEFAULT_TASK_BUDGET = {
    "soft_active_seconds": 60 * 60,
    "hard_active_seconds": 2 * 60 * 60,
    "max_no_progress_heartbeats": 3,
    "max_attempts": 4,
    "max_input_tokens": None,
    "max_output_tokens": None,
    "max_reasoning_tokens": None,
}
DEFAULT_EPISODE_BUDGET = {
    "soft_active_seconds": 10 * 60 * 60,
    "hard_active_seconds": 16 * 60 * 60,
    "closure_reserve_seconds": 2 * 60 * 60,
    "max_input_tokens": None,
    "max_output_tokens": None,
    "max_reasoning_tokens": None,
}
DISPATCH_MODES = {"elastic", "fixed"}
AGENT_PRESENCE_STATES = {"planned", "online", "offline", "retired"}
DEFAULT_AGENT_STALE_SECONDS = 10 * 60
MEANINGFUL_PROGRESS_EVENT_TYPES = {
    "ArtifactAccepted",
    "ArtifactRegistered",
    "ChangeResolved",
    "GapResolved",
    "QualityGateFailed",
    "QualityGatePassed",
    "ReviewRecorded",
    "RouteSwitched",
    "TaskApproved",
    "TaskDependencyRewired",
    "TaskHumanApproved",
    "TaskHumanApprovalReversed",
    "TaskHumanRevisionRequested",
    "TaskReferenceRebound",
    "TaskReleasedAfterUpstreamReapproval",
    "TaskRecoveredFromHistoricalArtifactFalseBlock",
    "TaskReplanned",
    "TaskRevisionRequested",
    "TaskScopeChanged",
    "TaskSubmitted",
    "TaskValidatorRebound",
}
CLOSURE_TASK_KINDS = {"review", "repair", "finalization", "integration", "retrospective", "release"}
REVIEW_TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".py",
    ".srt",
    ".vtt",
    ".tex",
    ".yaml",
    ".yml",
    ".csv",
}
MAX_REVIEW_INLINE_CHARS = 96 * 1024
MAX_CONTENT_UNIT_DEPTH = 4
MAX_DELIVERABLE_DEPTH = 3
CONTEXT_OVERRIDE_SCOPES = {"attempt", "task", "content_unit", "episode"}
CONTEXT_OVERRIDE_DELIVERY = {"attention_boundary", "next_attempt", "immediate"}
CONTEXT_OVERRIDE_MODES = {"append", "replace"}


def _task_work_key(
    *,
    explicit: str | None,
    task_id: str,
    content_unit_id: str | None,
    scene_id: str | None,
    wave_id: str | None,
    deliverable_id: str | None,
    kind: str,
    required_artifact_roles: list[str],
) -> str:
    """Return the durable obligation identity used to reject fake parallel work."""

    if explicit and explicit.strip():
        return require_identifier(explicit.strip(), "work_key")
    # Legacy/free-form tasks without a semantic scope stay unique by task id.
    # New multiscale tasks share a work key only when they claim the same
    # content/deliverable slot; this avoids guessing equivalence from titles.
    scope = content_unit_id or scene_id or wave_id or task_id
    output = deliverable_id or ".".join(required_artifact_roles) or kind
    return require_identifier(f"work:{scope}:{output}:{kind}", "work_key")


def _effective_work_key(task: dict[str, Any]) -> str:
    """Derive a deterministic key for pre-work-key task rows without rewriting them."""

    return _task_work_key(
        explicit=str(task.get("work_key") or ""),
        task_id=str(task.get("task_id")),
        content_unit_id=task.get("content_unit_id"),
        scene_id=task.get("scene_id"),
        wave_id=task.get("wave_id"),
        deliverable_id=task.get("deliverable_id"),
        kind=str(task.get("kind", "production")),
        required_artifact_roles=sorted(
            set(
                task.get("output_contract", {}).get(
                    "required_artifact_roles", []
                )
            )
        ),
    )


def _relevant_annotations_for_task(
    task: dict[str, Any],
    annotations: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Project open Human UI notes onto the exact producing task capsule."""

    task_id = str(task.get("task_id"))
    target_ids = {task_id}
    target_ids.update(
        str(artifact.get("artifact_id"))
        for artifact in artifacts
        if artifact.get("producer_task_id") == task_id
    )
    receipt_context: dict[str, dict[str, Any]] = {}
    for receipt in task.get("upstream_reapproval_receipts") or []:
        for annotation_id in receipt.get("annotation_ids") or []:
            receipt_context[str(annotation_id)] = {
                "delivery_via": "upstream_reapproval_receipt",
                "upstream_task_id": receipt.get("upstream_task_id"),
                "source_change_ids": receipt.get("source_change_ids", []),
                "released_at": receipt.get("released_at"),
            }
    relevant: list[dict[str, Any]] = []
    for annotation in annotations:
        if annotation.get("status", "open") != "open":
            continue
        annotation_id = str(annotation.get("annotation_id", ""))
        direct = str(annotation.get("target_id")) in target_ids
        inherited = annotation_id in receipt_context
        if not direct and not inherited:
            continue
        item = {
            key: annotation.get(key)
            for key in (
                "annotation_id",
                "target_id",
                "target_kind",
                "body",
                "severity",
                "location",
                "actor",
                "created_at",
                "delivery_policy",
                "delivery_state",
            )
        }
        # Legacy annotations predate delivery metadata. Normalize them at the
        # projection boundary so the signed capsule remains self-explanatory.
        item["delivery_policy"] = item.get("delivery_policy") or "on_begin"
        item["delivery_state"] = item.get("delivery_state") or "open"
        if inherited:
            item.update(receipt_context[annotation_id])
        relevant.append(item)
    return sorted(relevant, key=lambda item: str(item.get("annotation_id")))


def _agent_can_take(
    agent: dict[str, Any] | None,
    task: dict[str, Any],
    action: str,
) -> bool:
    """Apply the sealed roster contract without asking the model to self-score."""

    if agent is None or action in {"continue", "reclaim"}:
        return True
    capabilities = set(agent.get("capabilities") or [])
    role = str(agent.get("role", "agent"))
    if "*" in capabilities:
        return True
    if action == "human_review":
        return role in {"human", "user"} or "human_review" in capabilities
    if action in {"review", "gate"}:
        return role in {"reviewer", "supervisor"} or bool(
            capabilities & {"review", "quality_gate", action}
        )
    if action in {"work", "return_rework"}:
        return bool(
            capabilities
            & {
                str(task.get("role", "author")),
                str(task.get("kind", "production")),
            }
        ) or role == str(task.get("role", "author"))
    return False


def _return_feedback(ticket: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Normalize one accepted return into exact, capsule-bound repair context."""

    if not ticket:
        return []
    ticket_id = str(ticket.get("return_ticket_id", "return"))
    result: list[dict[str, Any]] = []
    for index, finding in enumerate(ticket.get("findings") or [], start=1):
        if isinstance(finding, dict):
            instruction = str(
                finding.get("instruction")
                or finding.get("description")
                or "Address the exact bound review finding."
            )
        else:
            instruction = str(finding)
        result.append(
            {
                "feedback_id": f"{ticket_id}:finding:{index}",
                "source": "independent_review_return",
                "review_id": ticket.get("review_id"),
                "return_ticket_id": ticket.get("return_ticket_id"),
                "instruction": instruction,
                "finding": finding,
            }
        )
    if ticket.get("note"):
        result.append(
            {
                "feedback_id": f"{ticket_id}:note",
                "source": "independent_review_return",
                "review_id": ticket.get("review_id"),
                "return_ticket_id": ticket.get("return_ticket_id"),
                "instruction": str(ticket["note"]),
            }
        )
    return result


def _context_payload_diff(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    previous_blocks = {
        str(item.get("block_id")): item
        for item in (previous or {}).get("context_blocks", [])
    }
    current_blocks = {
        str(item.get("block_id")): item
        for item in current.get("context_blocks", [])
    }
    added = [
        current_blocks[key]
        for key in sorted(current_blocks.keys() - previous_blocks.keys())
    ]
    removed = [
        previous_blocks[key]
        for key in sorted(previous_blocks.keys() - current_blocks.keys())
    ]
    changed = [
        {
            "block_id": key,
            "before": previous_blocks[key],
            "after": current_blocks[key],
        }
        for key in sorted(previous_blocks.keys() & current_blocks.keys())
        if previous_blocks[key].get("content_hash")
        != current_blocks[key].get("content_hash")
        or previous_blocks[key].get("version")
        != current_blocks[key].get("version")
    ]
    unchanged = sorted(
        key
        for key in previous_blocks.keys() & current_blocks.keys()
        if key not in {item["block_id"] for item in changed}
    )
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged_block_ids": unchanged,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": len(unchanged),
        },
    }


def _relevant_context_overrides(
    overrides: list[dict[str, Any]],
    task: dict[str, Any],
    episode_id: str,
    attempt: int,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in overrides:
        if item.get("status", "active") != "active":
            continue
        if int(item.get("effective_attempt", 0)) > attempt:
            continue
        scope = str(item.get("scope", "task"))
        if scope == "episode" and item.get("episode_id") == episode_id:
            result.append(item)
        elif scope == "content_unit" and item.get("content_unit_id") == task.get(
            "content_unit_id"
        ):
            result.append(item)
        elif item.get("task_id") == task.get("task_id"):
            result.append(item)
    return sorted(
        result,
        key=lambda item: (
            int(item.get("precedence", 700)),
            str(item.get("override_id", "")),
        ),
    )


def _audio_contract_check(path: Path) -> dict[str, Any]:
    """Kernel-level proof that a narration artifact is real decodable audio."""

    suffix = path.suffix.lower()
    if suffix in {".wav", ".wave"}:
        try:
            with wave.open(str(path), "rb") as handle:
                frames = int(handle.getnframes())
                channels = int(handle.getnchannels())
                sample_rate = int(handle.getframerate())
                sample_width = int(handle.getsampwidth())
        except (EOFError, OSError, wave.Error) as exc:
            raise DomainError(
                "artifact_contract_failed",
                "narration_audio is not a decodable WAVE file",
                failed_invariant="narration_audio_decodable",
                allowed_next=("submit", "gap"),
                recovery="Supply a decodable recording; changing an extension is not sufficient.",
                details={"path": str(path), "probe": "python-wave", "error": str(exc)},
            ) from exc
        if frames <= 0 or channels <= 0 or sample_rate <= 0 or sample_width <= 0:
            raise DomainError(
                "artifact_contract_failed",
                "narration_audio contains no usable audio frames",
                failed_invariant="narration_audio_decodable",
                allowed_next=("submit", "gap"),
                details={
                    "path": str(path),
                    "frames": frames,
                    "channels": channels,
                    "sample_rate": sample_rate,
                    "sample_width": sample_width,
                },
            )
        return {
            "check": "narration_audio_decodable",
            "probe": "python-wave",
            "passed": True,
            "frames": frames,
            "channels": channels,
            "sample_rate": sample_rate,
            "sample_width": sample_width,
        }

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise DomainError(
            "artifact_probe_unavailable",
            "non-WAVE narration audio requires ffprobe for deterministic validation",
            failed_invariant="narration_audio_decodable",
            allowed_next=("submit", "gap"),
            recovery="Install ffprobe or supply a decodable WAVE recording.",
            details={"path": str(path), "suffix": suffix},
        )
    try:
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name,channels,sample_rate,duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DomainError(
            "artifact_probe_failed",
            "audio probe could not complete",
            failed_invariant="narration_audio_decodable",
            allowed_next=("submit", "gap"),
            details={"path": str(path), "error": str(exc)},
        ) from exc
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        payload = {}
    streams = payload.get("streams") if isinstance(payload, dict) else None
    if completed.returncode != 0 or not isinstance(streams, list) or not streams:
        raise DomainError(
            "artifact_contract_failed",
            "narration_audio has no decodable audio stream",
            failed_invariant="narration_audio_decodable",
            allowed_next=("submit", "gap"),
            recovery="Supply a decodable recording; changing an extension is not sufficient.",
            details={
                "path": str(path),
                "probe": "ffprobe",
                "exit_code": completed.returncode,
                "stderr": completed.stderr[:2000],
            },
        )
    stream = streams[0]
    return {
        "check": "narration_audio_decodable",
        "probe": "ffprobe",
        "passed": True,
        "codec_name": stream.get("codec_name"),
        "channels": stream.get("channels"),
        "sample_rate": stream.get("sample_rate"),
        "duration": stream.get("duration"),
    }


def _kernel_artifact_contract(role: str, path: Path) -> list[dict[str, Any]]:
    if role == "narration_audio":
        return [_audio_contract_check(path)]
    return []


def _normalized_budget(value: dict[str, Any] | None) -> dict[str, Any]:
    budget = {**DEFAULT_TASK_BUDGET, **(value or {})}
    soft = int(budget["soft_active_seconds"])
    hard = int(budget["hard_active_seconds"])
    if soft <= 0 or hard <= 0 or soft > hard:
        raise DomainError(
            "invalid_budget",
            "task budget requires 0 < soft_active_seconds <= hard_active_seconds",
            failed_invariant="task_time_budget_order",
        )
    if int(budget["max_no_progress_heartbeats"]) < 1 or int(budget["max_attempts"]) < 1:
        raise DomainError(
            "invalid_budget",
            "heartbeat and attempt limits must be positive",
            failed_invariant="task_budget_positive",
        )
    return budget


def _normalized_episode_budget(value: dict[str, Any] | None) -> dict[str, Any]:
    budget = {**DEFAULT_EPISODE_BUDGET, **(value or {})}
    soft = int(budget["soft_active_seconds"])
    hard = int(budget["hard_active_seconds"])
    reserve = int(budget["closure_reserve_seconds"])
    if soft <= 0 or hard <= 0 or soft > hard or reserve < 0 or reserve >= hard:
        raise DomainError(
            "invalid_episode_budget",
            "episode budget requires 0 < soft <= hard and 0 <= closure reserve < hard",
            failed_invariant="episode_budget_order",
        )
    return budget


def _dispatch_policy(episode: dict[str, Any]) -> dict[str, Any]:
    policy = episode.get("dispatch_policy") or {}
    return {
        "schema": "elastic-frontier-v1",
        "configured": bool(policy),
        "mode": str(policy.get("mode", "unconfigured")),
        "max_active_authors": policy.get("max_active_authors"),
        "reviewer_capacity": policy.get("reviewer_capacity"),
        "spawn_policy": str(policy.get("spawn_policy", "on_demand")),
        "revision": int(policy.get("revision", 0)),
        "reason": policy.get("reason"),
        "updated_at": policy.get("updated_at"),
    }


def _episode_usage(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    usage = {
        "active_seconds": sum(float(task.get("active_seconds", 0.0)) for task in tasks),
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
    }
    for task in tasks:
        resource = task.get("resource_usage") or {}
        for field in ("input_tokens", "output_tokens", "reasoning_tokens"):
            usage[field] += int(resource.get(field, 0))
    return usage


def _episode_budget_state(episode: dict[str, Any], tasks: list[dict[str, Any]]) -> dict[str, Any]:
    budget = _normalized_episode_budget(episode.get("budget"))
    usage = _episode_usage(tasks)
    hard_reasons: list[dict[str, Any]] = []
    if usage["active_seconds"] >= float(budget["hard_active_seconds"]):
        hard_reasons.append(
            {"kind": "episode_active_time_exhausted", "used": usage["active_seconds"], "limit": budget["hard_active_seconds"]}
        )
    for field, cap_field in (
        ("input_tokens", "max_input_tokens"),
        ("output_tokens", "max_output_tokens"),
        ("reasoning_tokens", "max_reasoning_tokens"),
    ):
        cap = budget.get(cap_field)
        if cap is not None and usage[field] >= int(cap):
            hard_reasons.append({"kind": "episode_token_budget_exhausted", "field": field, "used": usage[field], "limit": int(cap)})
    production_limit = int(budget["hard_active_seconds"]) - int(budget["closure_reserve_seconds"])
    episode_remaining = max(
        0.0, float(budget["hard_active_seconds"]) - usage["active_seconds"]
    )
    return {
        "budget": budget,
        "usage": usage,
        "soft_limit_reached": usage["active_seconds"] >= float(budget["soft_active_seconds"]),
        "hard_stop": bool(hard_reasons),
        "hard_stop_reasons": hard_reasons,
        "production_envelope_exhausted": usage["active_seconds"] >= production_limit,
        "production_active_seconds_limit": production_limit,
        "production_active_seconds_remaining": max(
            0.0, production_limit - usage["active_seconds"]
        ),
        "episode_active_seconds_remaining": episode_remaining,
        "closure_reserve_seconds": int(budget["closure_reserve_seconds"]),
        "closure_reserve_available": min(
            float(budget["closure_reserve_seconds"]), episode_remaining
        ),
    }


def _derived_episode_phase(
    episode: dict[str, Any],
    tasks: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
) -> str:
    explicit = str(episode.get("status", "active"))
    if explicit in {"released", "retrospective_complete"}:
        return explicit
    current = [
        task
        for task in tasks
        if task.get("status") not in {"cancelled", "superseded"}
    ]
    if not current or not any(
        int(task.get("attempt", 0)) > 0
        or task.get("status") not in {"planned"}
        for task in current
    ):
        return "initialized"
    if any(gap.get("status") == "open" for gap in gaps):
        return "producing_attention"
    release_tasks = [
        task
        for task in current
        if task.get("kind") in {"release", "finalization", "integration"}
        or "release_required" in task.get("tags", [])
    ]
    if release_tasks and all(
        task.get("status") == "approved" for task in release_tasks
    ) and all(task.get("status") == "approved" for task in current):
        return "releasable"
    if any(
        task.get("status") in {"candidate", "user_review_pending"}
        for task in release_tasks
    ):
        return "release_candidate"
    return "producing"


def _scope_phase(tasks: list[dict[str, Any]]) -> str:
    current = [
        task
        for task in tasks
        if task.get("status") not in {"cancelled", "superseded"}
    ]
    if not current:
        return "empty"
    statuses = {str(task.get("status")) for task in current}
    if all(status == "approved" for status in statuses):
        return "approved"
    if "blocked" in statuses and not statuses & {
        "working",
        "candidate",
        "user_review_pending",
    }:
        return "blocked"
    if statuses & {"candidate", "user_review_pending"} and not statuses & {
        "working",
        "rework",
    }:
        return "review"
    if all(
        int(task.get("attempt", 0)) == 0 and task.get("status") == "planned"
        for task in current
    ):
        return "not_started"
    return "active"


def _missing_validator_receipts(
    task: dict[str, Any], receipts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    candidate_hash = (task.get("candidate") or {}).get("candidate_hash")
    return [
        descriptor
        for descriptor in task.get("required_validators", [])
        if descriptor.get("required", True)
        and not any(
            receipt.get("task_id") == task.get("task_id")
            and receipt.get("candidate_hash") == candidate_hash
            and receipt.get("validator_id") == descriptor.get("validator_id")
            and receipt.get("validator_sha256") == descriptor.get("sha256")
            and receipt.get("status") == "pass"
            for receipt in receipts
        )
    ]


def _active_delta_seconds(lease: dict[str, Any], now: str, *, cap_at_expiry: bool = False) -> float:
    start = parse_time(str(lease.get("accounted_at") or lease.get("granted_at") or now))
    end = parse_time(now)
    if cap_at_expiry and lease.get("expires_at"):
        end = min(end, parse_time(str(lease["expires_at"])))
    return max(0.0, (end - start).total_seconds())


def _new_request_id(command: str, actor: str, now: str, payload: dict[str, Any]) -> str:
    return "req_" + object_hash(
        {"command": command, "actor": actor, "now": now, "payload": payload}
    )[:24]


class SupervisionService:
    def __init__(
        self,
        data_root: DataRoot,
        repo_root: Path,
        *,
        clock: Callable[[], str] = utc_now,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ):
        self.data_root = data_root
        self.repo_root = repo_root.resolve()
        self.clock = clock
        self.lease_seconds = int(lease_seconds)
        self.data_root.initialize()

    def _request_id(
        self,
        command: str,
        actor: str,
        payload: dict[str, Any],
        request_id: str | None,
        now: str,
    ) -> str:
        return request_id or _new_request_id(command, actor, now, payload)

    def _execute(
        self,
        episode_id: str,
        command: str,
        actor: str,
        payload: dict[str, Any],
        handler: Callable[[Transaction], dict[str, Any]],
        *,
        request_id: str | None,
        now: str | None = None,
    ) -> dict[str, Any]:
        instant = now or self.clock()
        store = self.data_root.episode_store(episode_id)
        result = store.execute(
            request_id=self._request_id(command, actor, payload, request_id, instant),
            command_name=command,
            actor=actor,
            payload=payload,
            handler=handler,
            occurred_at=instant,
        )
        if result.get("ok"):
            self.data_root.sync_episode(episode_id)
        return result

    def create_episode(
        self,
        *,
        episode_id: str,
        title: str,
        mission: str,
        actor: str,
        request_id: str | None = None,
        production_mode: str = "supervised",
        budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        episode_id = require_identifier(episode_id, "episode_id")
        if not title.strip() or not mission.strip():
            raise DomainError(
                "invalid_episode",
                "episode title and mission are required",
                failed_invariant="episode_intent_explicit",
            )
        now = self.clock()
        episode_budget = _normalized_episode_budget(budget)
        payload = {
            "episode_id": episode_id,
            "title": title.strip(),
            "mission": mission.strip(),
            "production_mode": production_mode,
            "budget": episode_budget,
        }
        store = self.data_root.episode_store(episode_id, must_exist=False)
        store.initialize()

        def handler(tx: Transaction) -> dict[str, Any]:
            current, _ = tx.get("episode", episode_id)
            if current is not None:
                raise DomainError(
                    "episode_exists",
                    f"episode {episode_id!r} already exists",
                    failed_invariant="episode_id_unique",
                    allowed_next=("explain", "episodes"),
                )
            state = {
                "episode_id": episode_id,
                "title": title.strip(),
                "mission": mission.strip(),
                "production_mode": production_mode,
                "status": "active",
                "budget": episode_budget,
                "budget_revision": 1,
                "quality_policy": {
                    "quality_gates_non_relaxable": True,
                    "independent_review_required": True,
                    "human_release_required": True,
                    "missing_telemetry_is_unknown": True,
                },
                "scope_model": {
                    "schema": "multi-scale-dual-axis-v1",
                    "content_unit_max_depth": MAX_CONTENT_UNIT_DEPTH,
                    "deliverable_max_depth": MAX_DELIVERABLE_DEPTH,
                    "containment_is_not_execution_order": True,
                    "only_work_packages_are_leased": True,
                },
                "created_at": now,
                "updated_at": now,
            }
            tx.transition("episode", episode_id, "EpisodeCreated", payload, state, expected_version=0)
            return {"episode": state}

        result = store.execute(
            request_id=self._request_id("episode.create", actor, payload, request_id, now),
            command_name="episode.create",
            actor=actor,
            payload=payload,
            handler=handler,
            occurred_at=now,
        )
        if result.get("ok"):
            self.data_root.register_episode(episode_id, title.strip(), store, verified_health="healthy")
        return result

    def configure_episode_budget(
        self,
        episode_id: str,
        *,
        actor: str,
        reason: str,
        budget_patch: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if not reason.strip():
            raise DomainError(
                "invalid_episode_replan",
                "episode budget change requires a reason",
                failed_invariant="episode_replan_reason_explicit",
            )
        unknown = sorted(set(budget_patch) - set(DEFAULT_EPISODE_BUDGET))
        if unknown:
            raise DomainError(
                "invalid_episode_budget_patch",
                "episode budget patch contains unsupported fields",
                failed_invariant="episode_budget_patch_allowlist",
                details={"unknown_fields": unknown},
            )
        now = self.clock()
        payload = {"reason": reason.strip(), "budget_patch": budget_patch}

        def handler(tx: Transaction) -> dict[str, Any]:
            episode, version = tx.require("episode", episode_id)
            prior = _normalized_episode_budget(episode.get("budget"))
            updated_budget = _normalized_episode_budget({**prior, **budget_patch})
            updated = {
                **episode,
                "budget": updated_budget,
                "budget_revision": int(episode.get("budget_revision", 1)) + 1,
                "last_budget_replan": {"actor": actor, "reason": reason.strip(), "at": now},
                "updated_at": now,
            }
            tx.transition(
                "episode",
                episode_id,
                "EpisodeBudgetReplanned",
                {"reason": reason.strip(), "previous_budget": prior, "updated_budget": updated_budget},
                updated,
                expected_version=version,
            )
            return {"episode": updated, "previous_budget": prior}

        return self._execute(
            episode_id,
            "episode.budget_replan",
            actor,
            payload,
            handler,
            request_id=request_id,
            now=now,
        )

    def configure_dispatch_policy(
        self,
        episode_id: str,
        *,
        actor: str,
        reason: str,
        max_active_authors: int,
        reviewer_capacity: int,
        mode: str = "elastic",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        mode = str(mode).strip().lower()
        if not reason.strip():
            raise DomainError(
                "invalid_dispatch_policy",
                "dispatch policy requires a reason",
                failed_invariant="dispatch_policy_reason_explicit",
            )
        if mode not in DISPATCH_MODES:
            raise DomainError(
                "invalid_dispatch_policy",
                f"unsupported dispatch mode {mode!r}",
                failed_invariant="dispatch_mode_allowlist",
                details={"allowed_modes": sorted(DISPATCH_MODES)},
            )
        author_limit = int(max_active_authors)
        reviewer_limit = int(reviewer_capacity)
        if not 1 <= author_limit <= 32 or not 1 <= reviewer_limit <= 16:
            raise DomainError(
                "invalid_dispatch_policy",
                "dispatch capacity is outside the bounded range",
                failed_invariant="dispatch_capacity_bounded",
                details={
                    "max_active_authors": author_limit,
                    "reviewer_capacity": reviewer_limit,
                    "author_range": [1, 32],
                    "reviewer_range": [1, 16],
                },
            )
        now = self.clock()
        payload = {
            "reason": reason.strip(),
            "mode": mode,
            "max_active_authors": author_limit,
            "reviewer_capacity": reviewer_limit,
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            episode, version = tx.require("episode", episode_id)
            previous = _dispatch_policy(episode)
            policy = {
                "schema": "elastic-frontier-v1",
                "mode": mode,
                "max_active_authors": author_limit,
                "reviewer_capacity": reviewer_limit,
                "spawn_policy": "on_demand",
                "revision": int(previous.get("revision", 0)) + 1,
                "reason": reason.strip(),
                "updated_at": now,
            }
            updated = {**episode, "dispatch_policy": policy, "updated_at": now}
            tx.transition(
                "episode",
                episode_id,
                "EpisodeDispatchPolicyConfigured",
                {"previous": previous, "policy": policy},
                updated,
                expected_version=version,
            )
            return {"episode": updated, "previous_policy": previous, "dispatch_policy": policy}

        return self._execute(
            episode_id,
            "episode.dispatch_policy",
            actor,
            payload,
            handler,
            request_id=request_id,
            now=now,
        )

    def reserve_dispatch_tasks(
        self,
        episode_id: str,
        *,
        actor: str,
        reason: str,
        assignments: list[dict[str, str]],
        ttl_seconds: int = 15 * 60,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Atomically bind runnable tasks to distinct online author identities."""

        if not reason.strip():
            raise DomainError(
                "dispatch_reservation_reason_required",
                "parallel reservations require an explicit scheduling reason",
                failed_invariant="dispatch_reservation_auditable",
            )
        ttl = int(ttl_seconds)
        if not 60 <= ttl <= 60 * 60:
            raise DomainError(
                "invalid_dispatch_reservation_ttl",
                "reservation TTL must be between 60 and 3600 seconds",
                failed_invariant="dispatch_reservation_ttl_bounded",
            )
        normalized = [
            {
                "task_id": require_identifier(str(item.get("task_id", "")), "task_id"),
                "agent_id": require_identifier(str(item.get("agent_id", "")), "agent_id"),
            }
            for item in assignments
        ]
        if not normalized:
            raise DomainError(
                "dispatch_assignments_required",
                "at least one task-to-Agent reservation is required",
                failed_invariant="dispatch_reservation_nonempty",
            )
        task_ids = [item["task_id"] for item in normalized]
        agent_ids = [item["agent_id"] for item in normalized]
        if len(task_ids) != len(set(task_ids)) or len(agent_ids) != len(set(agent_ids)):
            raise DomainError(
                "duplicate_dispatch_assignment",
                "one reservation batch may use each task and Agent only once",
                failed_invariant="dispatch_reservation_one_to_one",
            )
        now = self.clock()
        payload = {
            "reason": reason.strip(),
            "assignments": normalized,
            "ttl_seconds": ttl,
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            episode, _ = tx.require("episode", episode_id)
            policy = _dispatch_policy(episode)
            if not policy["configured"]:
                raise DomainError(
                    "dispatch_policy_required",
                    "configure bounded author capacity before reserving parallel work",
                    failed_invariant="dispatch_reservation_within_episode_capacity",
                    allowed_next=("dispatch-policy",),
                )
            if len(normalized) > int(policy["max_active_authors"]):
                raise DomainError(
                    "dispatch_reservation_capacity_exceeded",
                    "reservation batch exceeds configured author capacity",
                    failed_invariant="dispatch_reservation_within_episode_capacity",
                    details={
                        "requested": len(normalized),
                        "limit": policy["max_active_authors"],
                    },
                )
            tasks = {state["task_id"]: state for state, _ in tx.list("task")}
            agents = {state["agent_id"]: state for state, _ in tx.list("agent")}
            gaps = [state for state, _ in tx.list("gap")]
            leases = {state["task_id"]: state for state, _ in tx.list("lease")}
            existing_reservations = {
                state["task_id"]: (state, version)
                for state, version in tx.list("dispatch_reservation")
            }
            live_by_agent = {
                str(state.get("reserved_for")): state
                for state, _ in tx.list("dispatch_reservation")
                if lease_is_live(state, now)
                and state.get("task_id") not in set(task_ids)
            }
            live_lease_by_agent = {
                str(state.get("owner")): state
                for state, _ in tx.list("lease")
                if lease_is_live(state, now)
            }
            validated: list[tuple[dict[str, str], dict[str, Any], dict[str, Any]]] = []
            for assignment in normalized:
                task = tasks.get(assignment["task_id"])
                agent = agents.get(assignment["agent_id"])
                if task is None:
                    raise DomainError(
                        "task_not_found",
                        f"task {assignment['task_id']!r} does not exist",
                        failed_invariant="dispatch_reservation_task_exists",
                    )
                if agent is None:
                    raise DomainError(
                        "agent_not_registered",
                        f"Agent {assignment['agent_id']!r} is not registered",
                        failed_invariant="dispatch_reservation_agent_registered",
                    )
                if agent.get("presence") != "online":
                    raise DomainError(
                        "agent_not_online",
                        "only online Agents can receive a concrete reservation",
                        failed_invariant="dispatch_reservation_agent_online",
                        details={
                            "agent_id": assignment["agent_id"],
                            "presence": agent.get("presence"),
                        },
                    )
                if not _agent_can_take(agent, task, "work"):
                    raise DomainError(
                        "agent_capability_mismatch",
                        "reserved Agent is incompatible with the task contract",
                        failed_invariant="dispatch_reservation_capability_match",
                        details={
                            "agent_id": assignment["agent_id"],
                            "task_id": assignment["task_id"],
                            "capabilities": agent.get("capabilities", []),
                            "task_role": task.get("role"),
                            "task_kind": task.get("kind"),
                        },
                    )
                blockers = task_blockers(
                    task,
                    tasks,
                    gaps,
                    leases.get(assignment["task_id"]),
                    now,
                )
                if task.get("status") not in {"planned", "rework"} or blockers:
                    raise DomainError(
                        "dispatch_task_not_runnable",
                        "only currently runnable work can be reserved",
                        failed_invariant="dispatch_reservation_runnable_frontier",
                        details={
                            "task_id": assignment["task_id"],
                            "status": task.get("status"),
                            "blockers": blockers,
                        },
                    )
                if assignment["agent_id"] in live_by_agent:
                    raise DomainError(
                        "agent_already_reserved",
                        "Agent already owns another live task reservation",
                        failed_invariant="one_live_reservation_per_agent",
                        details={
                            "agent_id": assignment["agent_id"],
                            "task_id": live_by_agent[assignment["agent_id"]].get("task_id"),
                        },
                    )
                if assignment["agent_id"] in live_lease_by_agent:
                    raise DomainError(
                        "agent_attention_occupied",
                        "Agent already owns a live attention envelope",
                        failed_invariant="one_live_authoring_lease_per_agent",
                        details={
                            "agent_id": assignment["agent_id"],
                            "task_id": live_lease_by_agent[assignment["agent_id"]].get("task_id"),
                        },
                    )
                validated.append((assignment, task, agent))
            reserved: list[dict[str, Any]] = []
            for assignment, task, agent in validated:
                reservation_id = f"reservation:{assignment['task_id']}"
                existing, version = existing_reservations.get(
                    assignment["task_id"], (None, 0)
                )
                state = {
                    "reservation_id": reservation_id,
                    "episode_id": episode_id,
                    "task_id": assignment["task_id"],
                    "reserved_for": assignment["agent_id"],
                    "reserved_by": actor,
                    "status": "active",
                    "reason": reason.strip(),
                    "task_role": task.get("role"),
                    "agent_role": agent.get("role"),
                    "created_at": now,
                    "expires_at": add_seconds(now, ttl),
                }
                tx.transition(
                    "dispatch_reservation",
                    reservation_id,
                    "DispatchReservationCreated"
                    if existing is None
                    else "DispatchReservationReassigned",
                    {
                        "task_id": assignment["task_id"],
                        "reserved_for": assignment["agent_id"],
                        "reason": reason.strip(),
                    },
                    state,
                    expected_version=version,
                )
                reserved.append(state)
            return {
                "dispatch_reservations": reserved,
                "dispatch_policy": policy,
            }

        return self._execute(
            episode_id,
            "dispatch.reserve",
            actor,
            payload,
            handler,
            request_id=request_id,
            now=now,
        )

    def register_agent(
        self,
        episode_id: str,
        *,
        agent_id: str,
        actor: str,
        role: str,
        capabilities: list[str],
        model: str = "unspecified",
        presence: str = "planned",
        runtime_handle: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        agent_id = require_identifier(agent_id, "agent_id")
        normalized_presence = str(presence).strip().lower()
        if normalized_presence not in AGENT_PRESENCE_STATES:
            raise DomainError(
                "invalid_agent_presence",
                "agent presence is outside the sealed state set",
                failed_invariant="agent_presence_allowlist",
                details={"allowed": sorted(AGENT_PRESENCE_STATES)},
            )
        normalized_role = str(role).strip()
        normalized_capabilities = sorted(
            {str(item).strip() for item in capabilities if str(item).strip()}
        )
        if not normalized_role or not normalized_capabilities:
            raise DomainError(
                "invalid_agent_contract",
                "agent role and at least one capability are required",
                failed_invariant="agent_capability_contract_explicit",
            )
        now = self.clock()
        payload = {
            "agent_id": agent_id,
            "role": normalized_role,
            "capabilities": normalized_capabilities,
            "model": str(model).strip() or "unspecified",
            "presence": normalized_presence,
            "runtime_handle": runtime_handle,
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            tx.require("episode", episode_id)
            existing, _ = tx.get("agent", agent_id)
            if existing is not None:
                raise DomainError(
                    "agent_exists",
                    "agent identity is already in the stable roster",
                    failed_invariant="stable_agent_identity_unique",
                    allowed_next=("agent-presence", "agent-probe"),
                    details={"agent_id": agent_id},
                )
            state = {
                "episode_id": episode_id,
                **payload,
                "last_seen_at": (
                    now if normalized_presence == "online" else None
                ),
                "created_at": now,
                "updated_at": now,
            }
            tx.transition(
                "agent",
                agent_id,
                "AgentRegistered",
                payload,
                state,
                expected_version=0,
            )
            return {"agent": state}

        return self._execute(
            episode_id,
            "agent.register",
            actor,
            payload,
            handler,
            request_id=request_id,
            now=now,
        )

    def set_agent_presence(
        self,
        episode_id: str,
        agent_id: str,
        *,
        actor: str,
        presence: str,
        runtime_handle: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        agent_id = require_identifier(agent_id, "agent_id")
        normalized_presence = str(presence).strip().lower()
        if normalized_presence not in AGENT_PRESENCE_STATES:
            raise DomainError(
                "invalid_agent_presence",
                "agent presence is outside the sealed state set",
                failed_invariant="agent_presence_allowlist",
                details={"allowed": sorted(AGENT_PRESENCE_STATES)},
            )
        now = self.clock()
        payload = {
            "agent_id": agent_id,
            "presence": normalized_presence,
            "runtime_handle": runtime_handle,
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            current, version = tx.require("agent", agent_id)
            updated = {
                **current,
                "presence": normalized_presence,
                "runtime_handle": (
                    runtime_handle
                    if runtime_handle is not None
                    else current.get("runtime_handle")
                ),
                "last_seen_at": (
                    now
                    if normalized_presence == "online"
                    else current.get("last_seen_at")
                ),
                "updated_at": now,
            }
            tx.transition(
                "agent",
                agent_id,
                "AgentPresenceChanged",
                payload,
                updated,
                expected_version=version,
            )
            return {"agent": updated}

        return self._execute(
            episode_id,
            "agent.presence",
            actor,
            payload,
            handler,
            request_id=request_id,
            now=now,
        )

    def add_wave(
        self,
        episode_id: str,
        *,
        wave_id: str,
        title: str,
        actor: str,
        request_id: str | None = None,
        order: int = 0,
    ) -> dict[str, Any]:
        wave_id = require_identifier(wave_id, "wave_id")
        payload = {"wave_id": wave_id, "title": title.strip(), "order": int(order)}

        def handler(tx: Transaction) -> dict[str, Any]:
            tx.require("episode", episode_id)
            current, _ = tx.get("wave", wave_id)
            if current is not None:
                raise DomainError(
                    "wave_exists",
                    f"wave {wave_id!r} already exists",
                    failed_invariant="wave_id_unique",
                    allowed_next=("explain",),
                )
            state = {"wave_id": wave_id, "episode_id": episode_id, **payload, "status": "active"}
            tx.transition("wave", wave_id, "WaveAdded", payload, state, expected_version=0)
            return {"wave": state}

        return self._execute(episode_id, "wave.add", actor, payload, handler, request_id=request_id)

    def add_scene(
        self,
        episode_id: str,
        *,
        scene_id: str,
        wave_id: str,
        title: str,
        actor: str,
        request_id: str | None = None,
        order: int = 0,
    ) -> dict[str, Any]:
        scene_id = require_identifier(scene_id, "scene_id")
        wave_id = require_identifier(wave_id, "wave_id")
        payload = {"scene_id": scene_id, "wave_id": wave_id, "title": title.strip(), "order": int(order)}

        def handler(tx: Transaction) -> dict[str, Any]:
            tx.require("episode", episode_id)
            tx.require("wave", wave_id)
            current, _ = tx.get("scene", scene_id)
            if current is not None:
                raise DomainError(
                    "scene_exists",
                    f"scene {scene_id!r} already exists",
                    failed_invariant="scene_id_unique",
                    allowed_next=("explain",),
                )
            state = {"scene_id": scene_id, "episode_id": episode_id, **payload, "status": "active"}
            tx.transition("scene", scene_id, "SceneAdded", payload, state, expected_version=0)
            return {"scene": state}

        return self._execute(episode_id, "scene.add", actor, payload, handler, request_id=request_id)

    def add_content_unit(
        self,
        episode_id: str,
        *,
        unit_id: str,
        title: str,
        kind: str,
        actor: str,
        parent_unit_id: str | None = None,
        order: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        unit_id = require_identifier(unit_id, "unit_id")
        parent_unit_id = (
            require_identifier(parent_unit_id, "parent_unit_id")
            if parent_unit_id
            else None
        )
        if not title.strip() or not kind.strip():
            raise DomainError(
                "invalid_content_unit",
                "content unit title and kind are required",
                failed_invariant="content_unit_semantics_explicit",
            )
        payload = {
            "unit_id": unit_id,
            "title": title.strip(),
            "kind": kind.strip(),
            "parent_unit_id": parent_unit_id,
            "order": int(order),
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            episode, _ = tx.require("episode", episode_id)
            current, _ = tx.get("content_unit", unit_id)
            if current is not None:
                raise DomainError(
                    "content_unit_exists",
                    f"content unit {unit_id!r} already exists",
                    failed_invariant="content_unit_id_unique",
                    allowed_next=("explain",),
                )
            parent = None
            if parent_unit_id:
                parent, _ = tx.require("content_unit", parent_unit_id)
            depth = int((parent or {}).get("depth", 0)) + 1
            max_depth = int(
                episode.get("scope_model", {}).get(
                    "content_unit_max_depth", MAX_CONTENT_UNIT_DEPTH
                )
            )
            if depth > max_depth:
                raise DomainError(
                    "content_depth_exceeded",
                    "content hierarchy exceeds the configured semantic depth",
                    failed_invariant="content_hierarchy_bounded",
                    allowed_next=("explain",),
                    details={"depth": depth, "max_depth": max_depth},
                )
            now = self.clock()
            state = {
                "episode_id": episode_id,
                **payload,
                "depth": depth,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
            tx.transition(
                "content_unit",
                unit_id,
                "ContentUnitAdded",
                payload,
                state,
                expected_version=0,
            )
            return {"content_unit": state}

        return self._execute(
            episode_id,
            "content_unit.add",
            actor,
            payload,
            handler,
            request_id=request_id,
        )

    def add_deliverable(
        self,
        episode_id: str,
        *,
        deliverable_id: str,
        title: str,
        actor: str,
        parent_deliverable_id: str | None = None,
        order: int = 0,
        artifact_roles: list[str] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        deliverable_id = require_identifier(deliverable_id, "deliverable_id")
        parent_deliverable_id = (
            require_identifier(parent_deliverable_id, "parent_deliverable_id")
            if parent_deliverable_id
            else None
        )
        if not title.strip():
            raise DomainError(
                "invalid_deliverable",
                "deliverable title is required",
                failed_invariant="deliverable_semantics_explicit",
            )
        payload = {
            "deliverable_id": deliverable_id,
            "title": title.strip(),
            "parent_deliverable_id": parent_deliverable_id,
            "order": int(order),
            "artifact_roles": sorted(set(artifact_roles or [])),
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            episode, _ = tx.require("episode", episode_id)
            current, _ = tx.get("deliverable", deliverable_id)
            if current is not None:
                raise DomainError(
                    "deliverable_exists",
                    f"deliverable {deliverable_id!r} already exists",
                    failed_invariant="deliverable_id_unique",
                    allowed_next=("explain",),
                )
            parent = None
            if parent_deliverable_id:
                parent, _ = tx.require(
                    "deliverable", parent_deliverable_id
                )
            depth = int((parent or {}).get("depth", 0)) + 1
            max_depth = int(
                episode.get("scope_model", {}).get(
                    "deliverable_max_depth", MAX_DELIVERABLE_DEPTH
                )
            )
            if depth > max_depth:
                raise DomainError(
                    "deliverable_depth_exceeded",
                    "deliverable hierarchy exceeds the configured semantic depth",
                    failed_invariant="deliverable_hierarchy_bounded",
                    allowed_next=("explain",),
                    details={"depth": depth, "max_depth": max_depth},
                )
            now = self.clock()
            state = {
                "episode_id": episode_id,
                **payload,
                "depth": depth,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
            tx.transition(
                "deliverable",
                deliverable_id,
                "DeliverableAdded",
                payload,
                state,
                expected_version=0,
            )
            return {"deliverable": state}

        return self._execute(
            episode_id,
            "deliverable.add",
            actor,
            payload,
            handler,
            request_id=request_id,
        )

    def add_task(
        self,
        episode_id: str,
        *,
        task_id: str,
        title: str,
        goal: str,
        actor: str,
        request_id: str | None = None,
        wave_id: str | None = None,
        scene_id: str | None = None,
        content_unit_id: str | None = None,
        deliverable_id: str | None = None,
        work_key: str | None = None,
        kind: str = "production",
        role: str = "author",
        dependencies: list[str] | None = None,
        references: list[dict[str, Any] | str] | None = None,
        required_artifact_roles: list[str] | None = None,
        input_artifact_ids: list[str] | None = None,
        critical_path: bool = False,
        unlock_value: int = 0,
        priority: int = 0,
        human_gate: bool = False,
        tags: list[str] | None = None,
        allowed_side_effects: list[str] | None = None,
        budget: dict[str, Any] | None = None,
        stop_conditions: list[str] | None = None,
        validators: list[dict[str, Any] | str] | None = None,
    ) -> dict[str, Any]:
        task_id = require_identifier(task_id, "task_id")
        content_unit_id = (
            require_identifier(content_unit_id, "content_unit_id")
            if content_unit_id
            else None
        )
        deliverable_id = (
            require_identifier(deliverable_id, "deliverable_id")
            if deliverable_id
            else None
        )
        dependency_ids = [require_identifier(item, "dependency_id") for item in dependencies or []]
        bound_references = [bind_reference(self.repo_root, item) for item in references or []]
        bound_validators = [bind_validator(self.repo_root, item) for item in validators or []]
        normalized_budget = _normalized_budget(budget)
        required_roles = sorted(set(required_artifact_roles or []))
        normalized_work_key = _task_work_key(
            explicit=work_key,
            task_id=task_id,
            content_unit_id=content_unit_id,
            scene_id=scene_id,
            wave_id=wave_id,
            deliverable_id=deliverable_id,
            kind=kind,
            required_artifact_roles=required_roles,
        )
        payload = {
            "task_id": task_id,
            "title": title.strip(),
            "goal": goal.strip(),
            "wave_id": wave_id,
            "scene_id": scene_id,
            "content_unit_id": content_unit_id,
            "deliverable_id": deliverable_id,
            "work_key": normalized_work_key,
            "kind": kind,
            "role": role,
            "dependencies": dependency_ids,
            "references": bound_references,
            "required_artifact_roles": required_roles,
            "input_artifact_ids": sorted(set(input_artifact_ids or [])),
            "critical_path": bool(critical_path),
            "unlock_value": int(unlock_value),
            "priority": int(priority),
            "human_gate": bool(human_gate),
            "tags": sorted(set(tags or [])),
            "allowed_side_effects": sorted(set(allowed_side_effects or [])),
            "budget": normalized_budget,
            "stop_conditions": stop_conditions or [],
            "required_validators": bound_validators,
        }
        if not title.strip() or not goal.strip():
            raise DomainError(
                "invalid_task",
                "task title and goal are required",
                failed_invariant="task_contract_explicit",
            )

        def handler(tx: Transaction) -> dict[str, Any]:
            tx.require("episode", episode_id)
            if wave_id:
                tx.require("wave", wave_id)
            if scene_id:
                scene, _ = tx.require("scene", scene_id)
                if wave_id and scene.get("wave_id") != wave_id:
                    raise DomainError(
                        "hierarchy_mismatch",
                        "scene does not belong to the requested wave",
                        failed_invariant="scene_wave_consistency",
                    )
            if content_unit_id:
                tx.require("content_unit", content_unit_id)
            if deliverable_id:
                tx.require("deliverable", deliverable_id)
            existing, _ = tx.get("task", task_id)
            if existing is not None:
                raise DomainError(
                    "task_exists",
                    f"task {task_id!r} already exists",
                    failed_invariant="task_id_unique",
                    allowed_next=("explain", "change"),
                )
            tasks = {state["task_id"]: state for state, _ in tx.list("task")}
            duplicate_obligation = next(
                (
                    state
                    for state in tasks.values()
                    if _effective_work_key(state) == normalized_work_key
                    and state.get("status") not in {"cancelled", "superseded"}
                ),
                None,
            )
            if duplicate_obligation is not None:
                raise DomainError(
                    "duplicate_work_obligation",
                    "another task already owns this semantic work obligation",
                    failed_invariant="one_live_task_per_work_key",
                    allowed_next=("explain", "route-switch", "change"),
                    recovery=(
                        "Reuse or rework the existing task. If the production route changed, "
                        "switch the route so the old obligation is superseded atomically."
                    ),
                    details={
                        "work_key": normalized_work_key,
                        "existing_task_id": duplicate_obligation.get("task_id"),
                        "existing_status": duplicate_obligation.get("status"),
                    },
                )
            for dependency_id in dependency_ids:
                if dependency_id not in tasks:
                    raise DomainError(
                        "dependency_missing",
                        f"dependency task {dependency_id!r} does not exist",
                        failed_invariant="dependency_exists",
                        allowed_next=("task-add", "change"),
                    )
            for artifact_id in payload["input_artifact_ids"]:
                tx.require("artifact", artifact_id)
            now = self.clock()
            state = {
                "episode_id": episode_id,
                "task_id": task_id,
                "title": title.strip(),
                "goal": goal.strip(),
                "wave_id": wave_id,
                "scene_id": scene_id,
                "content_unit_id": content_unit_id,
                "deliverable_id": deliverable_id,
                "work_key": normalized_work_key,
                "kind": kind,
                "role": role,
                "status": "planned",
                "dependencies": dependency_ids,
                "references": bound_references,
                "input_artifact_ids": payload["input_artifact_ids"],
                "output_contract": {"required_artifact_roles": payload["required_artifact_roles"]},
                "critical_path": bool(critical_path),
                "unlock_value": int(unlock_value),
                "priority": int(priority),
                "human_gate": bool(human_gate),
                "tags": payload["tags"],
                "allowed_side_effects": payload["allowed_side_effects"],
                "budget": payload["budget"],
                "stop_conditions": payload["stop_conditions"],
                "required_validators": bound_validators,
                "blockers": [],
                "scope_revision": 1,
                "context_revision": 1,
                "issued_context_revision": 0,
                "context_overrides": [],
                "resolved_contract_conflict_keys": [],
                "attempt": 0,
                "active_seconds": 0.0,
                "heartbeats_without_progress": 0,
                "tokens_without_progress": 0,
                "progress_evidence_seen": [],
                "resource_usage": {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                },
                "author": None,
                "active_capsule_hash": None,
                "candidate": None,
                "approved_artifact_ids": [],
                "created_at": now,
                "updated_at": now,
            }
            contract_conflicts = task_contract_conflicts(state)
            conflict_gaps: list[dict[str, Any]] = []
            for conflict in contract_conflicts:
                gap_id = "gap_" + object_hash(
                    {
                        "episode_id": episode_id,
                        "task_id": task_id,
                        "conflict_key": conflict["conflict_key"],
                    }
                )[:20]
                conflict_gaps.append(
                    {
                        "gap_id": gap_id,
                        "episode_id": episode_id,
                        "task_id": task_id,
                        "kind": conflict["kind"],
                        "reason": conflict["summary"],
                        "status": "open",
                        "reported_by": "supervision-kernel",
                        "requires_human": True,
                        "confidence": conflict["confidence"],
                        "conflict_key": conflict["conflict_key"],
                        "sources": conflict["sources"],
                        "resolution_options": conflict["resolution_options"],
                        "created_at": now,
                    }
                )
            if conflict_gaps:
                state["status"] = "blocked"
                state["blockers"] = [
                    {
                        "kind": "open_gap",
                        "gap_id": gap["gap_id"],
                        "reason": gap["reason"],
                        "requires_human": True,
                    }
                    for gap in conflict_gaps
                ]
            candidate_tasks = {**tasks, task_id: state}
            cycle = dependency_cycle(candidate_tasks)
            if cycle:
                raise DomainError(
                    "dependency_cycle",
                    "task dependency would create a cycle",
                    failed_invariant="task_graph_acyclic",
                    allowed_next=("change",),
                    details={"cycle": cycle},
                )
            tx.transition("task", task_id, "TaskAdded", payload, state, expected_version=0)
            for gap_state in conflict_gaps:
                tx.transition(
                    "gap",
                    gap_state["gap_id"],
                    "ContractConflictDetected",
                    {
                        "task_id": task_id,
                        "conflict_key": gap_state["conflict_key"],
                        "sources": gap_state["sources"],
                    },
                    gap_state,
                    expected_version=0,
                )
            return {"task": state, "gaps": conflict_gaps}

        return self._execute(episode_id, "task.add", actor, payload, handler, request_id=request_id)

    def switch_route(
        self,
        episode_id: str,
        replaced_task_id: str,
        replacement_task_id: str,
        *,
        actor: str,
        strategy: str,
        reason: str,
        replacement_spec: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Atomically replace one production strategy behind a stable output contract."""

        replaced_task_id = require_identifier(replaced_task_id, "replaced_task_id")
        replacement_task_id = require_identifier(replacement_task_id, "replacement_task_id")
        if replaced_task_id == replacement_task_id:
            raise DomainError(
                "route_identity_conflict",
                "replacement task must have a new identity",
                failed_invariant="route_replacement_identity",
            )
        if not isinstance(replacement_spec, dict):
            raise DomainError(
                "invalid_route_spec",
                "replacement task spec must be a JSON object",
                failed_invariant="route_spec_object",
            )
        if not strategy.strip() or not reason.strip():
            raise DomainError(
                "invalid_route_switch",
                "route switch requires a named strategy and an explicit reason",
                failed_invariant="route_switch_auditable",
            )
        allowed_fields = {
            "title",
            "goal",
            "wave_id",
            "scene_id",
            "content_unit_id",
            "deliverable_id",
            "work_key",
            "kind",
            "role",
            "dependencies",
            "references",
            "required_artifact_roles",
            "input_artifact_ids",
            "critical_path",
            "unlock_value",
            "priority",
            "human_gate",
            "tags",
            "allowed_side_effects",
            "budget",
            "stop_conditions",
            "validators",
            "quality_equivalence",
        }
        unknown_fields = sorted(set(replacement_spec) - allowed_fields)
        if unknown_fields:
            raise DomainError(
                "invalid_route_spec",
                "replacement task spec contains unsupported fields",
                failed_invariant="route_spec_allowlist",
                details={"unknown_fields": unknown_fields},
            )
        title = str(replacement_spec.get("title", "")).strip()
        goal = str(replacement_spec.get("goal", "")).strip()
        if not title or not goal:
            raise DomainError(
                "invalid_route_spec",
                "replacement task spec requires title and goal",
                failed_invariant="route_replacement_contract_explicit",
            )
        bound_references = [
            bind_reference(self.repo_root, item)
            for item in replacement_spec.get("references", [])
        ]
        validators_were_explicit = "validators" in replacement_spec
        bound_validators = (
            [
                bind_validator(self.repo_root, item)
                for item in replacement_spec.get("validators", [])
            ]
            if validators_were_explicit
            else None
        )
        replacement_budget = (
            _normalized_budget(replacement_spec.get("budget"))
            if "budget" in replacement_spec
            else None
        )
        now = self.clock()
        payload = {
            "replaced_task_id": replaced_task_id,
            "replacement_task_id": replacement_task_id,
            "strategy": strategy.strip(),
            "reason": reason.strip(),
            "replacement_spec": {
                **replacement_spec,
                "references": bound_references,
                **(
                    {"validators": bound_validators}
                    if validators_were_explicit
                    else {}
                ),
                **({"budget": replacement_budget} if replacement_budget else {}),
            },
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            tx.require("episode", episode_id)
            replaced, replaced_version = tx.require("task", replaced_task_id)
            current_replacement, _ = tx.get("task", replacement_task_id)
            if current_replacement is not None:
                raise DomainError(
                    "task_exists",
                    f"replacement task {replacement_task_id!r} already exists",
                    failed_invariant="task_id_unique",
                    allowed_next=("explain",),
                )
            if replaced.get("status") in {"cancelled", "superseded"}:
                raise DomainError(
                    "route_source_terminal",
                    "a cancelled or already superseded task cannot be switched again",
                    failed_invariant="route_source_current",
                    allowed_next=("explain",),
                    details={"status": replaced.get("status")},
                )

            prior_roles = sorted(
                set(
                    replaced.get("output_contract", {}).get(
                        "required_artifact_roles", []
                    )
                )
            )
            replacement_roles = sorted(
                set(
                    replacement_spec.get(
                        "required_artifact_roles", prior_roles
                    )
                )
            )
            if not prior_roles:
                raise DomainError(
                    "route_contract_missing",
                    "route switching requires a stable, non-empty output contract",
                    failed_invariant="route_output_contract_explicit",
                    allowed_next=("change", "replan"),
                )
            if replacement_roles != prior_roles:
                raise DomainError(
                    "route_output_contract_incompatible",
                    "replacement strategy must preserve the exact output artifact roles",
                    failed_invariant="route_output_contract_stable",
                    allowed_next=("change", "replan"),
                    details={
                        "required_roles": prior_roles,
                        "replacement_roles": replacement_roles,
                    },
                    recovery=(
                        "Switch the producer behind the stable output slot, or record an "
                        "explicit graph replan when the deliverable itself changes."
                    ),
                )

            old_human_gate = bool(replaced.get("human_gate", False))
            new_human_gate = bool(
                replacement_spec.get("human_gate", old_human_gate)
            )
            if old_human_gate and not new_human_gate:
                raise DomainError(
                    "route_quality_contract_incompatible",
                    "replacement route may not remove an existing human gate",
                    failed_invariant="route_quality_not_weakened",
                    allowed_next=("change", "replan"),
                )

            old_validators = list(replaced.get("required_validators", []))
            replacement_validators = (
                list(bound_validators or [])
                if validators_were_explicit
                else old_validators
            )
            old_validator_ids = {
                item.get("validator_id")
                for item in old_validators
                if item.get("required", True)
            }
            replacement_validator_ids = {
                item.get("validator_id")
                for item in replacement_validators
                if item.get("required", True)
            }
            quality_equivalence = str(
                replacement_spec.get("quality_equivalence", "")
            ).strip()
            if old_validator_ids != replacement_validator_ids and not quality_equivalence:
                raise DomainError(
                    "route_quality_equivalence_required",
                    "changing hard-validator coverage requires an explicit equivalence rationale",
                    failed_invariant="route_quality_change_auditable",
                    allowed_next=("route-switch", "explain"),
                    details={
                        "previous_validator_ids": sorted(old_validator_ids),
                        "replacement_validator_ids": sorted(
                            replacement_validator_ids
                        ),
                    },
                )
            if old_validator_ids and not replacement_validator_ids:
                raise DomainError(
                    "route_quality_contract_incompatible",
                    "replacement route may not remove all required hard validators",
                    failed_invariant="route_quality_not_weakened",
                    allowed_next=("change", "replan"),
                )

            all_tasks = {
                state["task_id"]: (state, version)
                for state, version in tx.list("task")
            }
            replacement_dependencies = [
                require_identifier(item, "dependency_id")
                for item in replacement_spec.get(
                    "dependencies", replaced.get("dependencies", [])
                )
            ]
            if replaced_task_id in replacement_dependencies:
                raise DomainError(
                    "route_dependency_cycle",
                    "replacement task may not depend on the task it supersedes",
                    failed_invariant="route_replacement_independent",
                )
            for dependency_id in replacement_dependencies:
                if dependency_id not in all_tasks:
                    raise DomainError(
                        "dependency_missing",
                        f"dependency task {dependency_id!r} does not exist",
                        failed_invariant="dependency_exists",
                        allowed_next=("task-add", "route-switch"),
                    )

            wave_id = replacement_spec.get("wave_id", replaced.get("wave_id"))
            scene_id = replacement_spec.get(
                "scene_id", replaced.get("scene_id")
            )
            content_unit_id = replacement_spec.get(
                "content_unit_id", replaced.get("content_unit_id")
            )
            deliverable_id = replacement_spec.get(
                "deliverable_id", replaced.get("deliverable_id")
            )
            if wave_id:
                tx.require("wave", str(wave_id))
            if scene_id:
                scene, _ = tx.require("scene", str(scene_id))
                if wave_id and scene.get("wave_id") != wave_id:
                    raise DomainError(
                        "hierarchy_mismatch",
                        "replacement scene does not belong to its requested wave",
                        failed_invariant="scene_wave_consistency",
                    )
            if content_unit_id:
                tx.require("content_unit", str(content_unit_id))
            if deliverable_id:
                tx.require("deliverable", str(deliverable_id))

            input_artifact_ids = sorted(
                set(
                    replacement_spec.get(
                        "input_artifact_ids",
                        replaced.get("input_artifact_ids", []),
                    )
                )
            )
            for artifact_id in input_artifact_ids:
                tx.require("artifact", artifact_id)

            route_switch_id = "route_" + object_hash(
                {
                    "episode_id": episode_id,
                    "replaced_task_id": replaced_task_id,
                    "replacement_task_id": replacement_task_id,
                    "strategy": strategy.strip(),
                }
            )[:20]
            prior_route, _ = tx.get("route", route_switch_id)
            if prior_route is not None:
                return {
                    "duplicate_route_switch": True,
                    "route_switch": prior_route,
                    "task": current_replacement,
                }

            original_graph = {
                task_id: state for task_id, (state, _) in all_tasks.items()
            }
            direct_consumers = sorted(
                task_id
                for task_id, state in original_graph.items()
                if replaced_task_id in state.get("dependencies", [])
            )
            descendants: set[str] = set()
            frontier = [replaced_task_id]
            while frontier:
                upstream = frontier.pop()
                for candidate_id, candidate in original_graph.items():
                    if (
                        upstream in candidate.get("dependencies", [])
                        and candidate_id not in descendants
                    ):
                        descendants.add(candidate_id)
                        frontier.append(candidate_id)

            replacement_state = {
                "episode_id": episode_id,
                "task_id": replacement_task_id,
                "title": title,
                "goal": goal,
                "wave_id": wave_id,
                "scene_id": scene_id,
                "content_unit_id": content_unit_id,
                "deliverable_id": deliverable_id,
                "work_key": _task_work_key(
                    explicit=str(
                        replacement_spec.get("work_key")
                        or _effective_work_key(replaced)
                    ),
                    task_id=replacement_task_id,
                    content_unit_id=(str(content_unit_id) if content_unit_id else None),
                    scene_id=(str(scene_id) if scene_id else None),
                    wave_id=(str(wave_id) if wave_id else None),
                    deliverable_id=(str(deliverable_id) if deliverable_id else None),
                    kind=str(
                        replacement_spec.get(
                            "kind", replaced.get("kind", "production")
                        )
                    ),
                    required_artifact_roles=replacement_roles,
                ),
                "kind": str(
                    replacement_spec.get("kind", replaced.get("kind", "production"))
                ),
                "role": str(
                    replacement_spec.get("role", replaced.get("role", "author"))
                ),
                "status": "planned",
                "dependencies": replacement_dependencies,
                "references": bound_references,
                "input_artifact_ids": input_artifact_ids,
                "output_contract": {
                    "required_artifact_roles": replacement_roles
                },
                "critical_path": bool(
                    replacement_spec.get(
                        "critical_path", replaced.get("critical_path", False)
                    )
                ),
                "unlock_value": int(
                    replacement_spec.get(
                        "unlock_value", replaced.get("unlock_value", 0)
                    )
                ),
                "priority": int(
                    replacement_spec.get("priority", replaced.get("priority", 0))
                ),
                "human_gate": new_human_gate,
                "tags": sorted(
                    set(replacement_spec.get("tags", []))
                    | {f"route:{strategy.strip()}"}
                ),
                "allowed_side_effects": sorted(
                    set(replacement_spec.get("allowed_side_effects", []))
                ),
                "budget": replacement_budget
                or _normalized_budget(replaced.get("budget")),
                "stop_conditions": list(
                    replacement_spec.get("stop_conditions", [])
                ),
                "required_validators": replacement_validators,
                "blockers": [],
                "scope_revision": 1,
                "attempt": 0,
                "active_seconds": 0.0,
                "heartbeats_without_progress": 0,
                "tokens_without_progress": 0,
                "progress_evidence_seen": [],
                "resource_usage": {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                },
                "author": None,
                "active_capsule_hash": None,
                "candidate": None,
                "approved_artifact_ids": [],
                "route": {
                    "route_switch_id": route_switch_id,
                    "strategy": strategy.strip(),
                    "replaces_task_id": replaced_task_id,
                    "reason": reason.strip(),
                },
                "created_at": now,
                "updated_at": now,
            }

            prospective = {**original_graph, replacement_task_id: replacement_state}
            prospective[replaced_task_id] = {
                **replaced,
                "status": "superseded",
            }
            for consumer_id in direct_consumers:
                consumer = prospective[consumer_id]
                prospective[consumer_id] = {
                    **consumer,
                    "dependencies": list(
                        dict.fromkeys(
                            replacement_task_id if item == replaced_task_id else item
                            for item in consumer.get("dependencies", [])
                        )
                    ),
                }
            cycle = dependency_cycle(prospective)
            if cycle:
                raise DomainError(
                    "dependency_cycle",
                    "route replacement would create a dependency cycle",
                    failed_invariant="task_graph_acyclic",
                    allowed_next=("route-switch", "change"),
                    details={"cycle": cycle},
                )

            replaced_artifact_ids = sorted(
                set((replaced.get("candidate") or {}).get("artifact_ids", []))
                | set(replaced.get("approved_artifact_ids", []))
            )
            replaced_active_seconds = float(replaced.get("active_seconds", 0.0))
            replaced_lease_id = f"lease:{replaced_task_id}"
            replaced_lease, replaced_lease_version = tx.get(
                "lease", replaced_lease_id
            )
            if replaced_lease and replaced_lease.get("status") == "active":
                replaced_active_seconds += _active_delta_seconds(
                    replaced_lease, now
                )
                tx.transition(
                    "lease",
                    replaced_lease_id,
                    "LeaseRevokedByRouteSwitch",
                    {
                        "route_switch_id": route_switch_id,
                        "replacement_task_id": replacement_task_id,
                    },
                    {
                        **replaced_lease,
                        "status": "revoked",
                        "revoked_at": now,
                        "release_reason": "route_switch",
                        "accounted_at": now,
                    },
                    expected_version=replaced_lease_version,
                )

            cancelled_return_ticket_ids: list[str] = []
            for return_ticket, return_ticket_version in tx.list("return_ticket"):
                if (
                    return_ticket.get("task_id") != replaced_task_id
                    or return_ticket.get("status") != "pending"
                ):
                    continue
                cancelled_return_ticket_ids.append(
                    str(return_ticket["return_ticket_id"])
                )
                tx.transition(
                    "return_ticket",
                    str(return_ticket["return_ticket_id"]),
                    "DeferredReturnCancelledByRouteSwitch",
                    {
                        "route_switch_id": route_switch_id,
                        "replacement_task_id": replacement_task_id,
                    },
                    {
                        **return_ticket,
                        "status": "cancelled",
                        "cancelled_by": actor,
                        "cancelled_at": now,
                        "cancel_reason": "route_switch",
                        "replacement_task_id": replacement_task_id,
                        "updated_at": now,
                    },
                    expected_version=return_ticket_version,
                )

            superseded_state = {
                **replaced,
                "status": "superseded",
                "active_capsule_hash": None,
                "pending_return_ticket_id": None,
                "preferred_actor": None,
                "active_seconds": replaced_active_seconds,
                "superseded_by_task_id": replacement_task_id,
                "superseded_by_route_switch_id": route_switch_id,
                "superseded_at": now,
                "updated_at": now,
            }
            tx.transition(
                "task",
                replaced_task_id,
                "TaskRouteSuperseded",
                {
                    "route_switch_id": route_switch_id,
                    "replacement_task_id": replacement_task_id,
                    "strategy": strategy.strip(),
                    "reason": reason.strip(),
                },
                superseded_state,
                expected_version=replaced_version,
            )
            tx.transition(
                "task",
                replacement_task_id,
                "ReplacementRouteTaskAdded",
                {
                    "route_switch_id": route_switch_id,
                    "replaced_task_id": replaced_task_id,
                    "strategy": strategy.strip(),
                },
                replacement_state,
                expected_version=0,
            )

            for artifact_id in replaced_artifact_ids:
                artifact, artifact_version = tx.require("artifact", artifact_id)
                tx.transition(
                    "artifact",
                    artifact_id,
                    "ArtifactExcludedByRouteSwitch",
                    {
                        "route_switch_id": route_switch_id,
                        "replacement_task_id": replacement_task_id,
                    },
                    {
                        **artifact,
                        "status": "out_of_route",
                        "out_of_route_reason": reason.strip(),
                        "route_switch_id": route_switch_id,
                        "updated_at": now,
                    },
                    expected_version=artifact_version,
                )

            invalidated: list[str] = []
            rewired: list[str] = []
            for descendant_id in sorted(descendants):
                descendant, descendant_version = all_tasks[descendant_id]
                if descendant.get("status") in {"cancelled", "superseded"}:
                    continue
                is_direct = descendant_id in direct_consumers
                updated_dependencies = list(descendant.get("dependencies", []))
                if is_direct:
                    updated_dependencies = list(
                        dict.fromkeys(
                            replacement_task_id
                            if item == replaced_task_id
                            else item
                            for item in updated_dependencies
                        )
                    )
                    rewired.append(descendant_id)
                prior_artifact_ids = sorted(
                    set((descendant.get("candidate") or {}).get("artifact_ids", []))
                    | set(descendant.get("approved_artifact_ids", []))
                )
                needs_rework = descendant.get("status") in {
                    "working",
                    "candidate",
                    "user_review_pending",
                    "approved",
                }
                remaining_inputs = [
                    artifact_id
                    for artifact_id in descendant.get("input_artifact_ids", [])
                    if artifact_id not in replaced_artifact_ids
                ]
                updated_descendant = {
                    **descendant,
                    "dependencies": updated_dependencies,
                    "input_artifact_ids": remaining_inputs,
                    "active_capsule_hash": (
                        None
                        if needs_rework or is_direct
                        else descendant.get("active_capsule_hash")
                    ),
                    "candidate": None if needs_rework else descendant.get("candidate"),
                    "approved_artifact_ids": (
                        [] if needs_rework else descendant.get("approved_artifact_ids", [])
                    ),
                    "status": "rework" if needs_rework else descendant.get("status"),
                    "blockers": [
                        *descendant.get("blockers", []),
                        {
                            "kind": "route_switched",
                            "route_switch_id": route_switch_id,
                            "replaced_task_id": replaced_task_id,
                            "replacement_task_id": replacement_task_id,
                        },
                    ],
                    "updated_at": now,
                }
                tx.transition(
                    "task",
                    descendant_id,
                    (
                        "TaskInvalidatedByRouteSwitch"
                        if needs_rework
                        else "TaskDependencyRewired"
                    ),
                    {
                        "route_switch_id": route_switch_id,
                        "replaced_task_id": replaced_task_id,
                        "replacement_task_id": replacement_task_id,
                        "direct": is_direct,
                    },
                    updated_descendant,
                    expected_version=descendant_version,
                )
                if needs_rework:
                    invalidated.append(descendant_id)
                    for artifact_id in prior_artifact_ids:
                        artifact, artifact_version = tx.require(
                            "artifact", artifact_id
                        )
                        tx.transition(
                            "artifact",
                            artifact_id,
                            "ArtifactStaledByRouteSwitch",
                            {
                                "route_switch_id": route_switch_id,
                                "consumer_task_id": descendant_id,
                            },
                            {
                                **artifact,
                                "status": "stale",
                                "stale_reason": "route_switch",
                                "route_switch_id": route_switch_id,
                                "updated_at": now,
                            },
                            expected_version=artifact_version,
                        )
                descendant_lease_id = f"lease:{descendant_id}"
                descendant_lease, descendant_lease_version = tx.get(
                    "lease", descendant_lease_id
                )
                if descendant_lease and descendant_lease.get("status") == "active":
                    tx.transition(
                        "lease",
                        descendant_lease_id,
                        "LeaseRevokedByRouteSwitch",
                        {
                            "route_switch_id": route_switch_id,
                            "replacement_task_id": replacement_task_id,
                        },
                        {
                            **descendant_lease,
                            "status": "revoked",
                            "revoked_at": now,
                            "release_reason": "route_switch",
                            "accounted_at": now,
                        },
                        expected_version=descendant_lease_version,
                    )

            route_state = {
                "route_switch_id": route_switch_id,
                "episode_id": episode_id,
                "replaced_task_id": replaced_task_id,
                "replacement_task_id": replacement_task_id,
                "strategy": strategy.strip(),
                "reason": reason.strip(),
                "output_contract": {
                    "required_artifact_roles": prior_roles
                },
                "quality_equivalence": quality_equivalence or None,
                "status": "active",
                "rewired_task_ids": rewired,
                "invalidated_task_ids": invalidated,
                "cancelled_return_ticket_ids": cancelled_return_ticket_ids,
                "requested_by": actor,
                "created_at": now,
                "updated_at": now,
            }
            tx.transition(
                "route",
                route_switch_id,
                "RouteSwitched",
                route_state,
                route_state,
                expected_version=0,
            )
            return {
                "route_switch": route_state,
                "replaced_task": superseded_state,
                "replacement_task": replacement_state,
                "rewired_tasks": rewired,
                "invalidated_tasks": invalidated,
                "cancelled_return_tickets": cancelled_return_ticket_ids,
            }

        return self._execute(
            episode_id,
            "route.switch",
            actor,
            payload,
            handler,
            request_id=request_id,
            now=now,
        )

    def _fulfill_route_switches(
        self, tx: Transaction, task_id: str, now: str
    ) -> list[str]:
        fulfilled: list[str] = []
        for route, version in tx.list("route"):
            if (
                route.get("replacement_task_id") != task_id
                or route.get("status") != "active"
            ):
                continue
            updated = {
                **route,
                "status": "fulfilled",
                "fulfilled_at": now,
                "updated_at": now,
            }
            tx.transition(
                "route",
                route["route_switch_id"],
                "RouteReplacementFulfilled",
                {"replacement_task_id": task_id},
                updated,
                expected_version=version,
            )
            fulfilled.append(route["route_switch_id"])
        return fulfilled

    def _release_descendants_after_upstream_reapproval(
        self, tx: Transaction, task_id: str, now: str
    ) -> list[str]:
        """Release only invalidation blockers whose upstream is approved again.

        A downstream candidate invalidated by an upstream edit must be rebuilt,
        not silently restored. The persisted receipt lets both the worker and
        later evaluation tasks prove which change, Human annotations and Agent
        observations caused the new attempt.
        """

        task_rows = {
            state["task_id"]: (state, version)
            for state, version in tx.list("task")
        }
        upstream_row = task_rows.get(task_id)
        if upstream_row is None or upstream_row[0].get("status") != "approved":
            return []
        upstream_task = upstream_row[0]
        artifacts = [state for state, _ in tx.list("artifact")]
        annotation_ids = [
            str(item.get("annotation_id"))
            for item in _relevant_annotations_for_task(
                upstream_task,
                [state for state, _ in tx.list("annotation")],
                artifacts,
            )
            if item.get("annotation_id")
        ]
        observation_ids = sorted(
            str(state.get("observation_id"))
            for state, _ in tx.list("observation")
            if state.get("task_id") == task_id and state.get("observation_id")
        )
        resolved_change_ids = sorted(
            str(state.get("change_id"))
            for state, _ in tx.list("change")
            if state.get("task_id") == task_id
            and state.get("status") == "resolved"
            and state.get("change_id")
        )
        released: list[str] = []
        for descendant_id, (descendant, version) in sorted(task_rows.items()):
            if descendant.get("status") != "blocked":
                continue
            blockers = list(descendant.get("blockers") or [])
            if not any(
                blocker.get("kind") == "upstream_change"
                and blocker.get("upstream_task_id") == task_id
                for blocker in blockers
            ):
                continue
            remaining: list[dict[str, Any]] = []
            resolved_upstreams: list[str] = []
            for blocker in blockers:
                if blocker.get("kind") != "upstream_change":
                    remaining.append(blocker)
                    continue
                upstream_id = str(blocker.get("upstream_task_id") or "")
                upstream = task_rows.get(upstream_id, ({}, 0))[0]
                if upstream.get("status") == "approved":
                    resolved_upstreams.append(upstream_id)
                else:
                    remaining.append(blocker)
            prior_receipts = list(
                descendant.get("upstream_reapproval_receipts") or []
            )
            receipt = {
                "upstream_task_id": task_id,
                "resolved_upstream_task_ids": sorted(set(resolved_upstreams)),
                "source_change_ids": resolved_change_ids,
                "annotation_ids": annotation_ids,
                "observation_ids": observation_ids,
                "human_decision": upstream_task.get("human_decision"),
                "released_at": now,
            }
            updated = {
                **descendant,
                "status": "rework" if not remaining else "blocked",
                "blockers": remaining,
                "context_revision": int(descendant.get("context_revision", 1)) + 1,
                "active_capsule_hash": None,
                "pending_context_update": None,
                "upstream_reapproval_receipts": [*prior_receipts, receipt],
                "updated_at": now,
            }
            tx.transition(
                "task",
                descendant_id,
                "TaskReleasedAfterUpstreamReapproval",
                {
                    "upstream_task_id": task_id,
                    "resolved_upstream_task_ids": receipt[
                        "resolved_upstream_task_ids"
                    ],
                    "source_change_ids": resolved_change_ids,
                    "annotation_ids": annotation_ids,
                    "observation_ids": observation_ids,
                    "remaining_blockers": remaining,
                },
                updated,
                expected_version=version,
            )
            if not remaining:
                released.append(descendant_id)
        return released

    def add_feedback(
        self,
        episode_id: str,
        *,
        feedback_id: str,
        pattern_key: str,
        instruction: str,
        source: str,
        actor: str,
        applies_to: list[str] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        feedback_id = require_identifier(feedback_id, "feedback_id")
        payload = {
            "feedback_id": feedback_id,
            "pattern_key": pattern_key.strip(),
            "instruction": instruction.strip(),
            "source": source.strip(),
            "applies_to": sorted(set(applies_to or ["*"])),
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            tx.require("episode", episode_id)
            current, _ = tx.get("feedback", feedback_id)
            if current is not None:
                raise DomainError(
                    "feedback_exists",
                    f"feedback {feedback_id!r} already exists",
                    failed_invariant="feedback_id_unique",
                    allowed_next=("change",),
                )
            state = {**payload, "episode_id": episode_id, "status": "active", "created_at": self.clock()}
            tx.transition("feedback", feedback_id, "FeedbackActivated", payload, state, expected_version=0)
            return {"feedback": state}

        return self._execute(episode_id, "feedback.add", actor, payload, handler, request_id=request_id)

    def rebind_reference(
        self,
        episode_id: str,
        task_id: str,
        reference_id: str,
        path: str,
        *,
        actor: str,
        reason: str,
        purpose: str | None = None,
        selector: Any = None,
        context_class: str | None = None,
        context_version: str | None = None,
        context_slot: str | None = None,
        assembly_mode: str | None = None,
        precedence: int | None = None,
        scope: str | None = None,
        service_binding: str | None = None,
        mutable: bool | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Adopt a reviewed reference revision without silently widening context."""

        task_id = require_identifier(task_id, "task_id")
        reference_id = require_identifier(reference_id, "reference_id")
        if not str(path).strip():
            raise DomainError(
                "reference_rebind_path_required",
                "reference rebind requires a replacement path",
                failed_invariant="reference_rebind_path_explicit",
            )
        if not reason.strip():
            raise DomainError(
                "reference_rebind_reason_required",
                "reference rebind requires an explicit impact reason",
                failed_invariant="reference_rebind_auditable",
            )
        now = self.clock()
        payload = {
            "task_id": task_id,
            "reference_id": reference_id,
            "path": str(path).strip(),
            "reason": reason.strip(),
            "purpose": purpose.strip() if purpose is not None else None,
            "selector": selector,
            "context_class": context_class,
            "context_version": context_version,
            "context_slot": context_slot,
            "assembly_mode": assembly_mode,
            "precedence": precedence,
            "scope": scope,
            "service_binding": service_binding,
            "mutable": mutable,
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            task, task_version = tx.require("task", task_id)
            references = list(task.get("references", []))
            index = next(
                (
                    position
                    for position, item in enumerate(references)
                    if item.get("reference_id") == reference_id
                ),
                None,
            )
            if index is None:
                raise DomainError(
                    "reference_not_bound",
                    f"reference {reference_id!r} is not bound to task {task_id!r}",
                    failed_invariant="reference_rebind_existing_binding",
                    allowed_next=("explain", "change"),
                )
            previous = references[index]
            descriptor_input: dict[str, Any] = {
                "reference_id": reference_id,
                "path": str(path).strip(),
                "required": bool(previous.get("required", True)),
                "purpose": (
                    purpose.strip()
                    if purpose is not None
                    else previous.get("purpose", "Required task guidance")
                ),
                "selector": (
                    selector if selector is not None else previous.get("selector")
                ),
                "context_class": context_class or previous.get("context_class", "episode_material"),
                "context_version": context_version or previous.get("context_version"),
                "context_slot": context_slot or previous.get("context_slot"),
                "assembly_mode": assembly_mode or previous.get("assembly_mode", "append"),
                "precedence": precedence if precedence is not None else previous.get("precedence", 100),
                "scope": scope or previous.get("scope", "task"),
                "service_binding": service_binding or previous.get("service_binding"),
                "mutable": mutable if mutable is not None else previous.get("mutable", True),
            }
            descriptor = bind_reference(self.repo_root, descriptor_input)
            if previous == descriptor:
                return {
                    "unchanged": True,
                    "task": task,
                    "previous_reference": previous,
                    "reference": descriptor,
                }
            if task.get("status") in {"approved", "user_review_pending"}:
                raise DomainError(
                    "approved_contract_requires_change",
                    "record impact before changing a reference on accepted work",
                    failed_invariant="accepted_scope_change_is_explicit",
                    allowed_next=("change", "reference-rebind"),
                )
            if task.get("status") in {"cancelled", "superseded"}:
                raise DomainError(
                    "reference_rebind_terminal_task",
                    "a cancelled or superseded task cannot receive a new reference binding",
                    failed_invariant="reference_rebind_current_task",
                    allowed_next=("explain",),
                )
            references[index] = descriptor
            lease_id = f"lease:{task_id}"
            lease, lease_version = tx.get("lease", lease_id)
            active_seconds = float(task.get("active_seconds", 0.0))
            if lease and lease.get("status") == "active":
                active_seconds += _active_delta_seconds(lease, now)
                tx.transition(
                    "lease",
                    lease_id,
                    "LeaseRevokedByReferenceRebind",
                    {"task_id": task_id, "reference_id": reference_id},
                    {
                        **lease,
                        "status": "revoked",
                        "revoked_at": now,
                        "release_reason": "reference_rebind",
                        "accounted_at": now,
                    },
                    expected_version=lease_version,
                )
            candidate = task.get("candidate") or {}
            for artifact_id in candidate.get("artifact_ids", []):
                artifact, artifact_version = tx.require("artifact", artifact_id)
                tx.transition(
                    "artifact",
                    artifact_id,
                    "ArtifactStaledByReferenceRebind",
                    {"task_id": task_id, "reference_id": reference_id},
                    {
                        **artifact,
                        "status": "stale",
                        "stale_reason": "reference_rebind",
                        "updated_at": now,
                    },
                    expected_version=artifact_version,
                )
            updated = {
                **task,
                "status": "planned" if task.get("status") == "planned" else "rework",
                "references": references,
                "scope_revision": int(task.get("scope_revision", 1)) + 1,
                "context_revision": int(task.get("context_revision", 1)) + 1,
                "candidate": None,
                "active_capsule_hash": None,
                "approved_artifact_ids": [],
                "active_seconds": active_seconds,
                "blockers": [
                    *task.get("blockers", []),
                    {
                        "kind": "reference_rebound",
                        "reference_id": reference_id,
                        "reason": reason.strip(),
                    },
                ],
                "updated_at": now,
            }
            tx.transition(
                "task",
                task_id,
                "TaskReferenceRebound",
                {
                    "reference_id": reference_id,
                    "previous_sha256": previous.get("sha256"),
                    "replacement_sha256": descriptor.get("sha256"),
                    "reason": reason.strip(),
                },
                updated,
                expected_version=task_version,
            )
            return {
                "task": updated,
                "previous_reference": previous,
                "reference": descriptor,
            }

        return self._execute(
            episode_id,
            "reference.rebind",
            actor,
            payload,
            handler,
            request_id=request_id,
            now=now,
        )

    def rebind_validator(
        self,
        episode_id: str,
        task_id: str,
        validator_id: str,
        manifest: dict[str, Any] | str,
        *,
        actor: str,
        reason: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Explicitly replace a task's validator pin after drift or version upgrade."""
        task_id = require_identifier(task_id, "task_id")
        validator_id = require_identifier(validator_id, "validator_id")
        if not reason.strip():
            raise DomainError(
                "validator_rebind_reason_required",
                "validator rebind requires an explicit reason",
                failed_invariant="validator_rebind_auditable",
            )
        descriptor = bind_validator(self.repo_root, manifest)
        if descriptor["validator_id"] != validator_id:
            raise DomainError(
                "validator_identity_mismatch",
                "replacement manifest must keep the bound validator identity",
                failed_invariant="validator_rebind_identity",
                details={
                    "expected_validator_id": validator_id,
                    "actual_validator_id": descriptor["validator_id"],
                },
            )
        now = self.clock()
        payload = {
            "task_id": task_id,
            "validator_id": validator_id,
            "replacement": descriptor,
            "reason": reason.strip(),
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            task, task_version = tx.require("task", task_id)
            validators = list(task.get("required_validators", []))
            index = next(
                (
                    position
                    for position, item in enumerate(validators)
                    if item.get("validator_id") == validator_id
                ),
                None,
            )
            if index is None:
                raise DomainError(
                    "validator_not_bound",
                    f"validator {validator_id!r} is not bound to task {task_id!r}",
                    failed_invariant="validator_rebind_existing_binding",
                    allowed_next=("change", "task-add"),
                )
            previous = validators[index]
            if previous == descriptor:
                return {
                    "unchanged": True,
                    "task": task,
                    "previous_validator": previous,
                    "validator": descriptor,
                }
            if task.get("status") in {"approved", "user_review_pending"}:
                raise DomainError(
                    "approved_contract_requires_change",
                    "record impact before changing a validator on an accepted candidate",
                    failed_invariant="accepted_scope_change_is_explicit",
                    allowed_next=("change", "validator-rebind"),
                )
            validators[index] = descriptor
            lease_id = f"lease:{task_id}"
            lease, lease_version = tx.get("lease", lease_id)
            active_seconds = float(task.get("active_seconds", 0.0))
            if lease and lease.get("status") == "active":
                active_seconds += _active_delta_seconds(lease, now)
                tx.transition(
                    "lease",
                    lease_id,
                    "LeaseRevokedByValidatorRebind",
                    {"task_id": task_id, "reason": reason.strip()},
                    {
                        **lease,
                        "status": "revoked",
                        "revoked_at": now,
                        "release_reason": "validator_rebind",
                        "accounted_at": now,
                    },
                    expected_version=lease_version,
                )
            candidate = task.get("candidate") or {}
            for artifact_id in candidate.get("artifact_ids", []):
                artifact, artifact_version = tx.require("artifact", artifact_id)
                tx.transition(
                    "artifact",
                    artifact_id,
                    "ArtifactStaledByValidatorRebind",
                    {"task_id": task_id, "validator_id": validator_id},
                    {
                        **artifact,
                        "status": "stale",
                        "stale_reason": "validator_rebind",
                        "updated_at": now,
                    },
                    expected_version=artifact_version,
                )
            updated = {
                **task,
                "status": "planned" if task.get("status") == "planned" else "rework",
                "required_validators": validators,
                "scope_revision": int(task.get("scope_revision", 1)) + 1,
                "candidate": None,
                "active_capsule_hash": None,
                "approved_artifact_ids": [],
                "active_seconds": active_seconds,
                "blockers": [
                    {
                        "kind": "validator_rebound",
                        "validator_id": validator_id,
                        "reason": reason.strip(),
                    }
                ],
                "updated_at": now,
            }
            tx.transition(
                "task",
                task_id,
                "TaskValidatorRebound",
                {
                    "validator_id": validator_id,
                    "previous_sha256": previous.get("sha256"),
                    "replacement_sha256": descriptor.get("sha256"),
                    "reason": reason.strip(),
                },
                updated,
                expected_version=task_version,
            )
            return {
                "task": updated,
                "previous_validator": previous,
                "validator": descriptor,
            }

        return self._execute(
            episode_id,
            "validator.rebind",
            actor,
            payload,
            handler,
            request_id=request_id,
            now=now,
        )

    def _snapshot(self, store: EpisodeStore) -> dict[str, Any]:
        episode_rows = store.list("episode")
        return {
            "episode": episode_rows[0][0] if episode_rows else None,
            "waves": store.list("wave"),
            "scenes": store.list("scene"),
            "content_units": store.list("content_unit"),
            "deliverables": store.list("deliverable"),
            "tasks": store.list("task"),
            "agents": store.list("agent"),
            "dispatch_reservations": store.list("dispatch_reservation"),
            "leases": store.list("lease"),
            "artifacts": store.list("artifact"),
            "gaps": store.list("gap"),
            "changes": store.list("change"),
            "routes": store.list("route"),
            "returns": store.list("return_ticket"),
            "feedback": store.list("feedback"),
            "context_overrides": store.list("context_override"),
            "annotations": store.list("annotation"),
            "observations": store.list("observation"),
            "gates": store.list("gate"),
        }

    def preview_context(
        self,
        episode_id: str,
        task_id: str,
        *,
        actor: str = "human-ui",
    ) -> dict[str, Any]:
        """Compile the exact next capsule without granting a lease or mutating state."""

        task_id = require_identifier(task_id, "task_id")
        store = self.data_root.episode_store(episode_id)
        snapshot = self._snapshot(store)
        episode = snapshot["episode"]
        if episode is None:
            raise DomainError(
                "episode_not_found",
                f"episode {episode_id!r} does not exist",
                failed_invariant="episode_exists",
                http_status=404,
            )
        task_rows = {
            state["task_id"]: (state, version)
            for state, version in snapshot["tasks"]
        }
        if task_id not in task_rows:
            raise DomainError(
                "not_found",
                f"task {task_id!r} does not exist",
                failed_invariant="aggregate_exists",
                http_status=404,
            )
        task, task_version = task_rows[task_id]
        tasks = {key: state for key, (state, _) in task_rows.items()}
        preview_task = deepcopy(task)
        if task.get("status") in {"planned", "rework"}:
            preview_task.update(
                {
                    "status": "working",
                    "author": actor,
                    "attempt": int(task.get("attempt", 0)) + 1,
                    "issued_context_revision": int(task.get("context_revision", 1)),
                }
            )
        dependency_states = [
            {
                "task_id": dependency_id,
                "status": tasks[dependency_id].get("status"),
                "approved_artifact_ids": tasks[dependency_id].get(
                    "approved_artifact_ids", []
                ),
            }
            for dependency_id in task.get("dependencies", [])
            if dependency_id in tasks
        ]
        feedback = relevant_feedback_for_task(
            task, [state for state, _ in snapshot["feedback"]]
        )
        relevant_annotations = _relevant_annotations_for_task(
            task,
            [state for state, _ in snapshot["annotations"]],
            [state for state, _ in snapshot["artifacts"]],
        )
        open_changes = [
            {
                "change_id": state.get("change_id"),
                "kind": state.get("kind"),
                "reason": state.get("reason"),
                "artifact_id": state.get("artifact_id"),
                "context_slot": state.get("context_slot"),
                "assembly_mode": state.get("assembly_mode", "append"),
                "scope": state.get("scope", "task"),
                "delivery_policy": state.get("delivery_policy", "on_begin"),
            }
            for state, _ in snapshot["changes"]
            if state.get("task_id") == task_id
            and state.get("status") == "open"
        ]
        blockers = task_blockers(
            task,
            tasks,
            [state for state, _ in snapshot["gaps"]],
            next(
                (
                    state
                    for state, _ in snapshot["leases"]
                    if state.get("task_id") == task_id
                ),
                None,
            ),
            self.clock(),
        )
        cursor = store.cursor()
        payload = compile_capsule(
            repo_root=self.repo_root,
            episode=episode,
            task=preview_task,
            task_version=task_version + (
                1 if task.get("status") in {"planned", "rework"} else 0
            ),
            dependency_states=dependency_states,
            relevant_feedback=feedback,
            relevant_annotations=relevant_annotations,
            open_changes=open_changes,
            why_now={
                "critical_path": bool(task.get("critical_path")),
                "unlock_value": int(task.get("unlock_value", 0)),
                "priority": int(task.get("priority", 0)),
                "dependencies_satisfied": not any(
                    item.get("kind") == "dependency_not_approved"
                    for item in blockers
                ),
                "preview_for_actor": actor,
                "human_annotation_delivery": {
                    "boundary": "preview",
                    "count": len(relevant_annotations),
                    "annotation_ids": [
                        item.get("annotation_id") for item in relevant_annotations
                    ],
                },
                "blockers": blockers,
            },
            cursor=cursor,
            context_overrides=_relevant_context_overrides(
                [state for state, _ in snapshot["context_overrides"]],
                preview_task,
                episode_id,
                int(preview_task.get("attempt", 0)),
            ),
            preview=True,
        )
        preview_hash = object_hash(payload)
        latest = store.latest_capsule_for_task(task_id)
        return {
            "ok": True,
            "status": "read_only",
            "episode_id": episode_id,
            "task_id": task_id,
            "preview": {
                "capsule_hash": preview_hash,
                "payload": payload,
            },
            "issued": latest,
            "diff": _context_payload_diff(
                None if latest is None else latest.get("payload"), payload
            ),
            "preview_contract": {
                "mutates_state": False,
                "exact_if_claimed_at_cursor": cursor,
                "lease_owner_unbound": task.get("status") not in {"working"},
            },
        }

    def next_action(self, episode_id: str, *, actor: str, role: str = "agent") -> dict[str, Any]:
        now = self.clock()
        store = self.data_root.episode_store(episode_id)
        snapshot = self._snapshot(store)
        tasks = {state["task_id"]: state for state, _ in snapshot["tasks"]}
        versions = {state["task_id"]: version for state, version in snapshot["tasks"]}
        agents = {state["agent_id"]: state for state, _ in snapshot["agents"]}
        registered_agent = agents.get(actor)
        if registered_agent is not None:
            role = str(registered_agent.get("role", role))
        leases = {state["task_id"]: state for state, _ in snapshot["leases"]}
        reservations = {
            state["task_id"]: state
            for state, _ in snapshot["dispatch_reservations"]
            if lease_is_live(state, now)
        }
        gaps = [state for state, _ in snapshot["gaps"]]
        pending_returns = [
            state
            for state, _ in snapshot["returns"]
            if state.get("status") == "pending"
        ]
        return_by_task = {
            state["task_id"]: state for state in pending_returns
        }
        gate_receipts = [state for state, _ in snapshot["gates"]]
        budget_state = _episode_budget_state(snapshot["episode"], list(tasks.values()))
        dispatch_policy = _dispatch_policy(snapshot["episode"])
        active_author_leases = [lease for lease in leases.values() if lease_is_live(lease, now)]
        reserved_capacity = len(reservations)
        if budget_state["hard_stop"]:
            return {
                "ok": True,
                "status": "read_only",
                "episode_id": episode_id,
                "actor": actor,
                "role": role,
                "now": now,
                "cursor": store.cursor(),
                "next": {
                    "action": "episode_replan",
                    "subject": {"episode_id": episode_id, "title": snapshot["episode"].get("title")},
                    "reasons": budget_state["hard_stop_reasons"],
                    "rank": [-1],
                },
                "other_actionable": [],
                "excluded": [],
                "budget_state": budget_state,
                "selection_policy": "episode hard budget stop precedes all task scheduling",
            }
        candidates: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        action_rank = {
            "continue": 0,
            "gate": 1,
            "human_review": 2,
            "review": 3,
            "return_rework": 0.5,
            "reclaim": 4,
            "work": 5,
        }
        for task_id, task in tasks.items():
            status = task.get("status")
            lease = leases.get(task_id)
            reservation = reservations.get(task_id)
            action: str | None = None
            reasons: list[dict[str, Any]] = []
            if status == "working":
                if lease_is_live(lease, now):
                    if lease.get("owner") == actor:
                        action = "continue"
                    else:
                        reasons = [{"kind": "live_lease", "owner": lease.get("owner"), "expires_at": lease.get("expires_at")}]
                else:
                    action = "reclaim"
            elif status == "candidate":
                missing_validators = _missing_validator_receipts(task, gate_receipts)
                if missing_validators:
                    action = "gate"
                elif task.get("author") == actor:
                    reasons = [{"kind": "independence", "detail": "author cannot accept own candidate"}]
                else:
                    action = "review"
            elif status == "user_review_pending":
                if role in {"human", "user"}:
                    action = "human_review"
                else:
                    reasons = [{"kind": "human_authority_required"}]
            elif status in {"planned", "rework"}:
                reasons = task_blockers(task, tasks, gaps, lease, now)
                if reservation and reservation.get("reserved_for") != actor:
                    reasons.append(
                        {
                            "kind": "dispatch_reserved",
                            "reserved_for": reservation.get("reserved_for"),
                            "expires_at": reservation.get("expires_at"),
                        }
                    )
                return_ticket = return_by_task.get(task_id)
                if (
                    return_ticket
                    and return_ticket.get("assigned_to") not in {actor, "pool"}
                ):
                    reasons.append(
                        {
                            "kind": "return_reserved",
                            "assigned_to": return_ticket.get("assigned_to"),
                            "return_ticket_id": return_ticket.get(
                                "return_ticket_id"
                            ),
                            "delivery_policy": "attention_boundary",
                        }
                    )
                if (
                    budget_state["production_envelope_exhausted"]
                    and task.get("kind") not in CLOSURE_TASK_KINDS
                ):
                    reasons.append(
                        {
                            "kind": "closure_reserve_protected",
                            "production_limit": budget_state["production_active_seconds_limit"],
                        }
                    )
                capacity_consumed = len(active_author_leases) + (
                    0 if reservation and reservation.get("reserved_for") == actor else reserved_capacity
                )
                if (
                    dispatch_policy["configured"]
                    and capacity_consumed >= int(dispatch_policy["max_active_authors"])
                ):
                    reasons.append(
                        {
                            "kind": "dispatch_capacity_full",
                            "active": len(active_author_leases),
                            "reserved": reserved_capacity,
                            "limit": dispatch_policy["max_active_authors"],
                        }
                    )
                if not reasons:
                    action = "return_rework" if return_ticket else "work"
            else:
                reasons = task_blockers(task, tasks, gaps, lease, now)
                if not reasons:
                    reasons = [{"kind": "status_not_actionable", "status": status}]
            if action and not _agent_can_take(registered_agent, task, action):
                reasons = [
                    {
                        "kind": "agent_capability_mismatch",
                        "agent_id": actor,
                        "agent_role": role,
                        "task_role": task.get("role"),
                        "task_kind": task.get("kind"),
                    }
                ]
                action = None
            if action:
                reservation_affinity = (
                    0
                    if reservation and reservation.get("reserved_for") == actor
                    else 1
                )
                candidates.append(
                    {
                        "action": action,
                        "task": task,
                        "task_version": versions[task_id],
                        "rank": [action_rank[action], reservation_affinity, *scheduling_key(task)],
                        "missing_validators": missing_validators if status == "candidate" else [],
                        "return_ticket": return_by_task.get(task_id),
                        "dispatch_reservation": reservation,
                    }
                )
            else:
                excluded.append({"task_id": task_id, "title": task.get("title"), "status": status, "reasons": reasons})
        candidates.sort(key=lambda item: tuple(item["rank"]))
        selected = candidates[0] if candidates else None
        cursor = store.cursor()
        actor_has_live_work = any(
            lease_is_live(lease, now) and lease.get("owner") == actor
            for lease in leases.values()
        )
        actor_returns = [
            item
            for item in pending_returns
            if item.get("assigned_to") in {actor, "pool"}
        ]
        other_actionable = candidates[1:]
        if actor_has_live_work:
            # A live lease is an attention envelope. Keep deferred return
            # details out of the worker's context until that boundary closes.
            other_actionable = [
                item
                for item in other_actionable
                if item.get("action") != "return_rework"
            ]
        runnable_frontier = [
            task
            for task_id, task in tasks.items()
            if task.get("status") in {"planned", "rework"}
            and not task_blockers(task, tasks, gaps, leases.get(task_id), now)
        ]
        online_idle_agents = [
            agent
            for agent in agents.values()
            if agent.get("presence") == "online"
            and not any(
                lease_is_live(lease, now)
                and lease.get("owner") == agent.get("agent_id")
                for lease in leases.values()
            )
            and any(_agent_can_take(agent, task, "work") for task in runnable_frontier)
        ]
        configured_author_limit = (
            int(dispatch_policy["max_active_authors"])
            if dispatch_policy["configured"]
            else 1
        )
        target_author_lanes = min(
            configured_author_limit,
            len(active_author_leases) + len(runnable_frontier),
        )
        recommended_additional_authors = max(
            0,
            target_author_lanes
            - len(active_author_leases)
            - len(online_idle_agents),
        )
        return {
            "ok": True,
            "status": "read_only",
            "episode_id": episode_id,
            "actor": actor,
            "role": role,
            "now": now,
            "cursor": cursor,
            "next": selected,
            "other_actionable": other_actionable,
            "excluded": sorted(excluded, key=lambda item: item["task_id"]),
            "budget_state": budget_state,
            "dispatch_policy": dispatch_policy,
            "dispatch_reservations": sorted(
                reservations.values(), key=lambda item: str(item.get("task_id"))
            ),
            "dispatch_usage": {
                "active_authors": len(active_author_leases),
                "reserved_authors": reserved_capacity,
                "runnable_frontier": len(runnable_frontier),
                "target_author_lanes": target_author_lanes,
                "online_idle_compatible_authors": len(online_idle_agents),
                "recommended_additional_authors": recommended_additional_authors,
                "scaling_reason": (
                    "independent runnable work exceeds compatible online author supply"
                    if recommended_additional_authors
                    else "current compatible author supply covers the bounded frontier"
                ),
                "capacity_remaining": (
                    None
                    if not dispatch_policy["configured"]
                    else max(
                        0,
                        int(dispatch_policy["max_active_authors"])
                        - len(active_author_leases)
                        - reserved_capacity,
                    )
                ),
            },
            "deferred_returns": {
                "count": len(actor_returns),
                "delivery": (
                    "deferred_until_attention_boundary"
                    if actor_has_live_work and actor_returns
                    else "eligible_now"
                    if actor_returns
                    else "none"
                ),
                "ticket_ids": (
                    []
                    if actor_has_live_work
                    else [item["return_ticket_id"] for item in actor_returns]
                ),
            },
            "selection_policy": "continue current lease; then gates/review; honor explicit task reservations; then assigned returns before unreserved work; critical path, unlock value, priority, stable task id",
        }

    def agent_probe(self, episode_id: str, agent_id: str) -> dict[str, Any]:
        """Derive idle legality and productive-work health from durable evidence."""

        agent_id = require_identifier(agent_id, "agent_id")
        now = self.clock()
        store = self.data_root.episode_store(episode_id)
        snapshot = self._snapshot(store)
        agents = {state["agent_id"]: state for state, _ in snapshot["agents"]}
        agent = agents.get(agent_id)
        if agent is None:
            raise DomainError(
                "agent_not_registered",
                "idle legality requires a sealed roster identity",
                failed_invariant="agent_roster_required_for_idle_probe",
                allowed_next=("agent-register",),
                details={"agent_id": agent_id},
                http_status=404,
            )
        tasks = {state["task_id"]: state for state, _ in snapshot["tasks"]}
        live_leases = [
            state
            for state, _ in snapshot["leases"]
            if state.get("owner") == agent_id and lease_is_live(state, now)
        ]
        presence = str(agent.get("presence", "planned"))
        last_seen_at = agent.get("last_seen_at")
        stale = bool(
            presence == "online"
            and not live_leases
            and last_seen_at
            and (
                parse_time(now) - parse_time(str(last_seen_at))
            ).total_seconds() >= DEFAULT_AGENT_STALE_SECONDS
        )
        base = {
            "ok": True,
            "status": "read_only",
            "schema": "agent-idle-legality-v1",
            "episode_id": episode_id,
            "agent": agent,
            "now": now,
            "cursor": store.cursor(),
        }
        if presence in {"planned", "offline", "retired"}:
            return {
                **base,
                "classification": presence,
                "is_idle": None,
                "idle_legal": None,
                "productive": None,
                "reason_codes": [f"agent_{presence}"],
                "next": None,
                "evidence": {"live_leases": live_leases},
            }
        if stale:
            return {
                **base,
                "classification": "offline_unknown",
                "is_idle": None,
                "idle_legal": None,
                "productive": None,
                "reason_codes": ["presence_heartbeat_stale"],
                "next": None,
                "evidence": {
                    "last_seen_at": last_seen_at,
                    "stale_after_seconds": DEFAULT_AGENT_STALE_SECONDS,
                    "live_leases": [],
                },
            }
        if live_leases:
            lease = sorted(live_leases, key=lambda item: str(item.get("task_id")))[0]
            task = tasks.get(str(lease.get("task_id")), {})
            no_progress = int(task.get("heartbeats_without_progress", 0))
            token_use = int(task.get("tokens_without_progress", 0))
            work_key = _effective_work_key(task) if task else None
            duplicate_owner = next(
                (
                    other
                    for other in tasks.values()
                    if other.get("task_id") != task.get("task_id")
                    and work_key
                    and _effective_work_key(other) == work_key
                    and other.get("status") == "approved"
                ),
                None,
            )
            if duplicate_owner is not None:
                classification = "fake_busy_duplicate_work"
                reason_codes = ["work_obligation_already_satisfied"]
                productive = False
            elif no_progress > 0:
                classification = "working_nonproductive_risk"
                reason_codes = [
                    "no_novel_progress_evidence",
                    *(["token_burn_without_progress"] if token_use else []),
                ]
                productive = False
            else:
                classification = "working_productive"
                reason_codes = ["live_unique_obligation", "novelty_guard_clean"]
                productive = True
            next_result = self.next_action(
                episode_id,
                actor=agent_id,
                role=str(agent.get("role", "agent")),
            )
            return {
                **base,
                "classification": classification,
                "is_idle": False,
                "idle_legal": None,
                "productive": productive,
                "reason_codes": reason_codes,
                "next": next_result.get("next"),
                "evidence": {
                    "live_lease": lease,
                    "task_id": task.get("task_id"),
                    "work_key": work_key,
                    "heartbeats_without_progress": no_progress,
                    "last_progress_at": task.get("last_progress_at"),
                    "last_progress_evidence": task.get("last_progress_evidence", []),
                    "resource_usage": task.get("resource_usage", {}),
                    "tokens_without_progress": token_use,
                    "duplicate_owner_task_id": (
                        duplicate_owner.get("task_id")
                        if duplicate_owner is not None
                        else None
                    ),
                    "deferred_returns": next_result.get("deferred_returns"),
                },
            }

        next_result = self.next_action(
            episode_id,
            actor=agent_id,
            role=str(agent.get("role", "agent")),
        )
        selected = next_result.get("next")
        if selected and selected.get("action") == "episode_replan":
            classification = "blocked_by_supervision"
            idle_legal: bool | None = True
            reason_codes = ["episode_hard_stop"]
        elif selected is not None:
            classification = "idle_illegal"
            idle_legal = False
            reason_codes = [
                "compatible_actionable_work_exists",
                f"next_action:{selected.get('action')}",
            ]
        else:
            classification = "idle_legal"
            idle_legal = True
            exclusion_kinds = sorted(
                {
                    str(reason.get("kind"))
                    for item in next_result.get("excluded", [])
                    for reason in item.get("reasons", [])
                }
            )
            reason_codes = exclusion_kinds or ["no_pending_work"]
        return {
            **base,
            "classification": classification,
            "is_idle": True,
            "idle_legal": idle_legal,
            "productive": None,
            "reason_codes": reason_codes,
            "next": selected,
            "evidence": {
                "live_leases": [],
                "deferred_returns": next_result.get("deferred_returns"),
                "dispatch_usage": next_result.get("dispatch_usage"),
                "actionable_count": (
                    (1 if selected else 0)
                    + len(next_result.get("other_actionable", []))
                ),
                "excluded_count": len(next_result.get("excluded", [])),
            },
        }

    def begin(
        self,
        episode_id: str,
        task_id: str,
        *,
        actor: str,
        request_id: str | None = None,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        task_id = require_identifier(task_id, "task_id")
        now = self.clock()
        payload = {"task_id": task_id, "expected_version": expected_version}

        def handler(tx: Transaction) -> dict[str, Any]:
            episode, _ = tx.require("episode", episode_id)
            task, task_version = tx.require("task", task_id)
            registered_agent, _ = tx.get("agent", actor)
            if registered_agent is not None:
                if registered_agent.get("presence") != "online":
                    raise DomainError(
                        "agent_not_online",
                        "registered Agent must be online before claiming work",
                        failed_invariant="agent_presence_before_lease",
                        allowed_next=("agent-presence", "agent-probe"),
                        details={
                            "agent_id": actor,
                            "presence": registered_agent.get("presence"),
                        },
                    )
                if not _agent_can_take(
                    registered_agent,
                    task,
                    "return_rework"
                    if task.get("status") == "rework"
                    else "work",
                ):
                    raise DomainError(
                        "agent_capability_mismatch",
                        "registered Agent is not compatible with this task contract",
                        failed_invariant="agent_task_capability_match",
                        allowed_next=("next", "agent-probe"),
                        details={
                            "agent_id": actor,
                            "agent_role": registered_agent.get("role"),
                            "capabilities": registered_agent.get("capabilities"),
                            "task_role": task.get("role"),
                            "task_kind": task.get("kind"),
                        },
                    )
            reservation_id = f"reservation:{task_id}"
            reservation, reservation_version = tx.get(
                "dispatch_reservation", reservation_id
            )
            live_reservation = reservation if lease_is_live(reservation, now) else None
            if live_reservation and live_reservation.get("reserved_for") != actor:
                raise DomainError(
                    "dispatch_reserved",
                    "task is reserved for another online Agent",
                    failed_invariant="dispatch_reservation_owner_authority",
                    allowed_next=("next", "explain", "dispatch-reserve"),
                    details={
                        "task_id": task_id,
                        "reserved_for": live_reservation.get("reserved_for"),
                        "expires_at": live_reservation.get("expires_at"),
                    },
                )
            lease_id = f"lease:{task_id}"
            lease, lease_version = tx.get("lease", lease_id)
            return_ticket_row = next(
                (
                    (state, version)
                    for state, version in tx.list("return_ticket")
                    if state.get("task_id") == task_id
                    and state.get("status") == "pending"
                ),
                None,
            )
            if (
                return_ticket_row
                and return_ticket_row[0].get("assigned_to") not in {actor, "pool"}
            ):
                raise DomainError(
                    "return_reserved",
                    "this rework is reserved for its routed Agent",
                    failed_invariant="attention_safe_return_routing",
                    allowed_next=("next", "return-route", "explain"),
                    details={
                        "return_ticket_id": return_ticket_row[0].get(
                            "return_ticket_id"
                        ),
                        "assigned_to": return_ticket_row[0].get("assigned_to"),
                    },
                )
            if lease_is_live(lease, now):
                if lease.get("owner") == actor and task.get("status") == "working":
                    capsule = tx.connection.execute(
                        "SELECT * FROM capsules WHERE capsule_hash=?", (task.get("active_capsule_hash"),)
                    ).fetchone()
                    return {
                        "already_owned": True,
                        "task": task,
                        "lease": lease,
                        "capsule": None if capsule is None else {
                            "capsule_id": capsule["capsule_id"],
                            "capsule_hash": capsule["capsule_hash"],
                            "payload": __import__("json").loads(capsule["payload_json"]),
                        },
                    }
                raise DomainError(
                    "lease_conflict",
                    f"task {task_id!r} has a live lease owned by {lease.get('owner')}",
                    failed_invariant="single_active_lease",
                    allowed_next=("next", "explain"),
                    recovery="Wait until the reported expiry, then call next and begin only if the scheduler returns reclaim.",
                    details={"owner": lease.get("owner"), "generation": lease.get("generation"), "expires_at": lease.get("expires_at")},
                )
            dispatch_policy = _dispatch_policy(episode)
            active_author_leases = [
                state
                for state, _ in tx.list("lease")
                if state.get("task_id") != task_id and lease_is_live(state, now)
            ]
            live_unclaimed_reservations = [
                state
                for state, _ in tx.list("dispatch_reservation")
                if lease_is_live(state, now)
            ]
            actor_lease = next(
                (
                    state
                    for state in active_author_leases
                    if state.get("owner") == actor
                ),
                None,
            )
            if actor_lease is not None:
                raise DomainError(
                    "agent_attention_occupied",
                    "Agent already owns a live attention envelope",
                    failed_invariant="one_live_authoring_lease_per_agent",
                    allowed_next=("heartbeat", "submit", "next"),
                    details={
                        "agent_id": actor,
                        "task_id": actor_lease.get("task_id"),
                        "expires_at": actor_lease.get("expires_at"),
                    },
                )
            if (
                dispatch_policy["configured"]
                and (
                    len(active_author_leases)
                    + (
                        0
                        if live_reservation
                        and live_reservation.get("reserved_for") == actor
                        else len(live_unclaimed_reservations)
                    )
                )
                >= int(dispatch_policy["max_active_authors"])
            ):
                raise DomainError(
                    "dispatch_capacity_full",
                    "configured author capacity is already in use",
                    failed_invariant="dispatch_capacity_enforced",
                    allowed_next=("next", "explain", "dispatch-policy"),
                    recovery="Finish or release one active lease, or explicitly revise the episode dispatch policy.",
                    details={
                        "active": len(active_author_leases),
                        "reserved": len(live_unclaimed_reservations),
                        "limit": dispatch_policy["max_active_authors"],
                        "mode": dispatch_policy["mode"],
                    },
                )
            if task.get("status") not in {"planned", "rework", "working", "blocked"}:
                raise DomainError(
                    "invalid_transition",
                    f"task {task_id!r} cannot begin from status {task.get('status')!r}",
                    failed_invariant="task_begin_state",
                    allowed_next=("next", "explain"),
                    details={"status": task.get("status")},
                )
            task_budget = _normalized_budget(task.get("budget"))
            if int(task.get("attempt", 0)) >= int(task_budget["max_attempts"]):
                raise DomainError(
                    "attempt_budget_exhausted",
                    f"task {task_id!r} exhausted its bounded attempt budget",
                    failed_invariant="bounded_repair_attempts",
                    allowed_next=("replan", "explain"),
                    recovery="A supervisor must record a reasoned replan before more attempts are authorized.",
                    details={
                        "attempts": int(task.get("attempt", 0)),
                        "max_attempts": int(task_budget["max_attempts"]),
                    },
                )
            tasks = {state["task_id"]: state for state, _ in tx.list("task")}
            episode_budget_state = _episode_budget_state(episode, list(tasks.values()))
            if episode_budget_state["hard_stop"]:
                raise DomainError(
                    "episode_budget_exhausted",
                    "episode hard budget stops new work",
                    failed_invariant="episode_hard_budget",
                    allowed_next=("episode-budget", "explain"),
                    details={"reasons": episode_budget_state["hard_stop_reasons"]},
                )
            if (
                episode_budget_state["production_envelope_exhausted"]
                and task.get("kind") not in CLOSURE_TASK_KINDS
            ):
                raise DomainError(
                    "closure_reserve_protected",
                    "new production work would consume the reserved closure envelope",
                    failed_invariant="closure_reserve",
                    allowed_next=("next", "episode-budget"),
                    details={"budget_state": episode_budget_state},
                )
            gaps = [state for state, _ in tx.list("gap")]
            blockers = [item for item in task_blockers(task, tasks, gaps, None, now) if item.get("kind") != "blocked_status"]
            if task.get("status") == "blocked" or blockers:
                raise DomainError(
                    "task_blocked",
                    f"task {task_id!r} is not runnable",
                    failed_invariant="task_runnable",
                    allowed_next=("explain", "gap", "change"),
                    details={"blockers": blockers or task.get("blockers", [])},
                )
            dependency_states = [
                {
                    "task_id": dependency_id,
                    "status": tasks[dependency_id].get("status"),
                    "approved_artifact_ids": tasks[dependency_id].get("approved_artifact_ids", []),
                }
                for dependency_id in task.get("dependencies", [])
            ]
            feedback = relevant_feedback_for_task(task, [state for state, _ in tx.list("feedback")])
            if return_ticket_row:
                feedback = [*feedback, *_return_feedback(return_ticket_row[0])]
            relevant_annotations = _relevant_annotations_for_task(
                task,
                [state for state, _ in tx.list("annotation")],
                [state for state, _ in tx.list("artifact")],
            )
            open_changes = [
                {
                    "change_id": state.get("change_id"),
                    "kind": state.get("kind"),
                    "reason": state.get("reason"),
                    "artifact_id": state.get("artifact_id"),
                }
                for state, _ in tx.list("change")
                if state.get("task_id") == task_id and state.get("status") == "open"
            ]
            generation = int((lease or {}).get("generation", 0)) + 1
            carried_active_seconds = float(task.get("active_seconds", 0.0))
            if lease and lease.get("status") == "active" and not lease_is_live(lease, now):
                carried_active_seconds += _active_delta_seconds(lease, now, cap_at_expiry=True)
            predicted_task = deepcopy(task)
            predicted_task.update(
                {
                    "status": "working",
                    "author": actor,
                    "attempt": int(task.get("attempt", 0)) + 1,
                    "blockers": [],
                    "updated_at": now,
                    "last_activity_at": now,
                    "active_lease_generation": generation,
                    "active_seconds": carried_active_seconds,
                    "budget": task_budget,
                    "context_revision": int(task.get("context_revision", 1)),
                    "issued_context_revision": int(task.get("context_revision", 1)),
                    "pending_return_ticket_id": (
                        None
                        if return_ticket_row
                        else task.get("pending_return_ticket_id")
                    ),
                    "last_return_ticket_id": (
                        return_ticket_row[0].get("return_ticket_id")
                        if return_ticket_row
                        else task.get("last_return_ticket_id")
                    ),
                }
            )
            cursor = tx.connection.execute("SELECT COALESCE(MAX(seq), 0) AS seq FROM events").fetchone()["seq"]
            capsule_payload = compile_capsule(
                repo_root=self.repo_root,
                episode=episode,
                task=predicted_task,
                task_version=task_version + 1,
                dependency_states=dependency_states,
                relevant_feedback=feedback,
                relevant_annotations=relevant_annotations,
                open_changes=open_changes,
                why_now={
                    "critical_path": bool(task.get("critical_path")),
                    "unlock_value": int(task.get("unlock_value", 0)),
                    "priority": int(task.get("priority", 0)),
                    "dependencies_satisfied": True,
                    "human_annotation_delivery": {
                        "boundary": "begin",
                        "count": len(relevant_annotations),
                        "annotation_ids": [
                            item.get("annotation_id")
                            for item in relevant_annotations
                        ],
                    },
                    "return_ticket": (
                        {
                            "return_ticket_id": return_ticket_row[0].get(
                                "return_ticket_id"
                            ),
                            "assigned_to": return_ticket_row[0].get(
                                "assigned_to"
                            ),
                            "review_id": return_ticket_row[0].get("review_id"),
                        }
                        if return_ticket_row
                        else None
                    ),
                },
                cursor=int(cursor),
                context_overrides=_relevant_context_overrides(
                    [state for state, _ in tx.list("context_override")],
                    predicted_task,
                    episode_id,
                    int(predicted_task.get("attempt", 0)),
                ),
            )
            capsule_hash = object_hash(capsule_payload)
            predicted_task["active_capsule_hash"] = capsule_hash
            new_lease = {
                "lease_id": lease_id,
                "task_id": task_id,
                "owner": actor,
                "generation": generation,
                "status": "active",
                "granted_at": now,
                "last_heartbeat_at": now,
                "accounted_at": now,
                "expires_at": add_seconds(now, self.lease_seconds),
            }
            tx.transition(
                "lease",
                lease_id,
                "LeaseGranted" if lease is None else "LeaseReclaimed",
                {"task_id": task_id, "owner": actor, "generation": generation},
                new_lease,
                expected_version=lease_version,
            )
            task_event = tx.transition(
                "task",
                task_id,
                "TaskBegan" if task.get("status") != "working" else "TaskReclaimed",
                {"owner": actor, "lease_generation": generation, "capsule_hash": capsule_hash},
                predicted_task,
                expected_version=expected_version if expected_version is not None else task_version,
            )
            capsule = tx.save_capsule(task_id, task_event["aggregate_version"], capsule_payload)
            claimed_reservation = None
            if live_reservation and live_reservation.get("reserved_for") == actor:
                claimed_reservation = {
                    **live_reservation,
                    "status": "claimed",
                    "claimed_by": actor,
                    "claimed_at": now,
                }
                tx.transition(
                    "dispatch_reservation",
                    reservation_id,
                    "DispatchReservationClaimed",
                    {
                        "task_id": task_id,
                        "reserved_for": actor,
                        "lease_generation": generation,
                    },
                    claimed_reservation,
                    expected_version=reservation_version,
                )
            accepted_return = None
            if return_ticket_row:
                return_ticket, return_ticket_version = return_ticket_row
                accepted_return = {
                    **return_ticket,
                    "status": "accepted",
                    "accepted_by": actor,
                    "accepted_at": now,
                    "updated_at": now,
                }
                tx.transition(
                    "return_ticket",
                    return_ticket["return_ticket_id"],
                    "DeferredReturnAccepted",
                    {"task_id": task_id, "accepted_by": actor},
                    accepted_return,
                    expected_version=return_ticket_version,
                )
            return {
                "task": predicted_task,
                "lease": new_lease,
                "capsule": capsule,
                "dispatch_reservation": claimed_reservation,
                "accepted_return": accepted_return,
            }

        return self._execute(episode_id, "task.begin", actor, payload, handler, request_id=request_id, now=now)

    def heartbeat(
        self,
        episode_id: str,
        task_id: str,
        *,
        actor: str,
        generation: int | None = None,
        evidence_refs: list[str] | None = None,
        usage_delta: dict[str, int] | None = None,
        note: str = "",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        task_id = require_identifier(task_id, "task_id")
        now = self.clock()
        evidence = sorted(set(evidence_refs or []))
        usage = {
            "input_tokens": int((usage_delta or {}).get("input_tokens", 0)),
            "output_tokens": int((usage_delta or {}).get("output_tokens", 0)),
            "reasoning_tokens": int((usage_delta or {}).get("reasoning_tokens", 0)),
        }
        if any(value < 0 for value in usage.values()):
            raise DomainError(
                "invalid_usage_delta",
                "resource usage deltas cannot be negative",
                failed_invariant="monotonic_resource_usage",
            )
        payload = {
            "task_id": task_id,
            "generation": generation,
            "evidence_refs": evidence,
            "usage_delta": usage,
            "note": note.strip(),
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            task, task_version = tx.require("task", task_id)
            lease_id = f"lease:{task_id}"
            lease, lease_version = tx.require("lease", lease_id)
            if lease.get("status") != "active" or not lease_is_live(lease, now):
                raise DomainError(
                    "lease_expired",
                    "heartbeat authority has expired",
                    failed_invariant="heartbeat_requires_live_lease",
                    allowed_next=("begin", "explain"),
                    details={"current_lease": lease},
                )
            if lease.get("owner") != actor:
                raise DomainError(
                    "lease_owner_mismatch",
                    f"active lease is owned by {lease.get('owner')}, not {actor}",
                    failed_invariant="lease_owner_authority",
                    allowed_next=("explain",),
                    details={"owner": lease.get("owner"), "generation": lease.get("generation")},
                )
            if generation is not None and int(lease.get("generation", 0)) != int(generation):
                raise DomainError(
                    "stale_lease_generation",
                    "heartbeat refers to an obsolete lease generation",
                    failed_invariant="lease_generation_authority",
                    allowed_next=("explain", "begin"),
                    details={"expected_generation": lease.get("generation"), "provided_generation": generation},
                )
            if task.get("status") != "working":
                raise DomainError(
                    "invalid_transition",
                    f"heartbeat requires a working task, not {task.get('status')}",
                    failed_invariant="heartbeat_task_state",
                    allowed_next=("explain",),
                )
            validated_evidence: list[str] = []
            for reference in evidence:
                if reference.startswith("evt_"):
                    row = tx.connection.execute(
                        """
                        SELECT event_type, aggregate_type, aggregate_id, state_hash
                        FROM events WHERE event_id=?
                        """,
                        (reference,),
                    ).fetchone()
                    if row is None:
                        raise DomainError(
                            "progress_evidence_missing",
                            f"event evidence {reference!r} does not exist",
                            failed_invariant="meaningful_progress_evidence_exists",
                            allowed_next=("heartbeat", "submit"),
                        )
                    if row["event_type"] not in MEANINGFUL_PROGRESS_EVENT_TYPES:
                        raise DomainError(
                            "progress_evidence_not_meaningful",
                            f"event {reference!r} is operational activity, not progress evidence",
                            failed_invariant="progress_event_semantics_allowlist",
                            allowed_next=("heartbeat", "submit", "gap"),
                            details={"event_type": row["event_type"]},
                        )
                    validated_evidence.append(
                        "event:"
                        f"{row['event_type']}:{row['aggregate_type']}:"
                        f"{row['aggregate_id']}@sha256:{row['state_hash']}"
                    )
                elif reference.startswith("file:"):
                    path = resolve_repo_path(self.repo_root, reference.removeprefix("file:"))
                    if not path.is_file():
                        raise DomainError(
                            "progress_evidence_missing",
                            f"file progress evidence does not exist: {reference}",
                            failed_invariant="meaningful_progress_evidence_exists",
                            allowed_next=("heartbeat", "gap"),
                        )
                    validated_evidence.append(
                        f"file:{display_path(self.repo_root, path)}@sha256:{file_hash(path)}"
                    )
                else:
                    artifact, _ = tx.get("artifact", reference)
                    if artifact is not None:
                        validated_evidence.append(reference)
                        continue
                    path = resolve_repo_path(self.repo_root, reference)
                    if path.is_file():
                        validated_evidence.append(
                            f"file:{display_path(self.repo_root, path)}@sha256:{file_hash(path)}"
                        )
                        continue
                    raise DomainError(
                        "progress_evidence_missing",
                        f"progress evidence is neither an artifact ID, event ID, nor existing file: {reference}",
                        failed_invariant="meaningful_progress_evidence_exists",
                        allowed_next=("heartbeat", "submit", "gap"),
                    )
            task_budget = _normalized_budget(task.get("budget"))
            active_seconds = float(task.get("active_seconds", 0.0)) + _active_delta_seconds(lease, now)
            resource_usage = {
                field: int((task.get("resource_usage") or {}).get(field, 0)) + usage[field]
                for field in usage
            }
            seen_evidence = set(task.get("progress_evidence_seen", []))
            novel_evidence = [
                reference for reference in validated_evidence
                if reference not in seen_evidence
            ]
            meaningful_progress = bool(novel_evidence)
            no_progress = 0 if meaningful_progress else int(task.get("heartbeats_without_progress", 0)) + 1
            tokens_without_progress = (
                0
                if meaningful_progress
                else int(task.get("tokens_without_progress", 0))
                + sum(usage.values())
            )
            stop_reasons: list[dict[str, Any]] = []
            if active_seconds >= float(task_budget["hard_active_seconds"]):
                stop_reasons.append(
                    {
                        "kind": "active_time_budget_exhausted",
                        "used": active_seconds,
                        "limit": task_budget["hard_active_seconds"],
                    }
                )
            if no_progress >= int(task_budget["max_no_progress_heartbeats"]):
                stop_reasons.append(
                    {
                        "kind": "stagnation_threshold",
                        "heartbeats_without_progress": no_progress,
                        "limit": task_budget["max_no_progress_heartbeats"],
                    }
                )
            for field, cap_field in (
                ("input_tokens", "max_input_tokens"),
                ("output_tokens", "max_output_tokens"),
                ("reasoning_tokens", "max_reasoning_tokens"),
            ):
                cap = task_budget.get(cap_field)
                if cap is not None and resource_usage[field] >= int(cap):
                    stop_reasons.append(
                        {"kind": "token_budget_exhausted", "field": field, "used": resource_usage[field], "limit": int(cap)}
                    )
            checkpoint_due = active_seconds >= float(task_budget["soft_active_seconds"])
            updated_task = {
                **task,
                "last_activity_at": now,
                "updated_at": now,
                "active_seconds": active_seconds,
                "resource_usage": resource_usage,
                "heartbeats_without_progress": no_progress,
                "tokens_without_progress": tokens_without_progress,
                "progress_evidence_seen": sorted(
                    seen_evidence | set(novel_evidence)
                ),
                "checkpoint_due": checkpoint_due,
            }
            if meaningful_progress:
                updated_task["last_progress_at"] = now
                updated_task["last_progress_evidence"] = novel_evidence
            context_update_payload = None
            if stop_reasons:
                updated_task.update(
                    {
                        "status": "blocked",
                        "active_capsule_hash": None,
                        "blockers": [*task.get("blockers", []), *stop_reasons],
                        "supervision_stop": {"at": now, "reasons": stop_reasons},
                    }
                )
                updated_lease = {
                    **lease,
                    "status": "released",
                    "released_at": now,
                    "release_reason": "supervision_stop",
                    "accounted_at": now,
                }
                lease_event = "LeaseReleasedBySupervisor"
                task_event = "TaskSupervisionStopped"
            else:
                updated_lease = {
                    **lease,
                    "last_heartbeat_at": now,
                    "accounted_at": now,
                    "expires_at": add_seconds(now, self.lease_seconds),
                }
                lease_event = "LeaseRenewed"
                task_event = "TaskHeartbeat"
                if task.get("pending_context_update"):
                    pending_context_update = deepcopy(
                        task.get("pending_context_update") or {}
                    )
                    episode, _ = tx.require("episode", episode_id)
                    tasks = {
                        state["task_id"]: state for state, _ in tx.list("task")
                    }
                    dependency_states = [
                        {
                            "task_id": dependency_id,
                            "status": tasks[dependency_id].get("status"),
                            "approved_artifact_ids": tasks[dependency_id].get(
                                "approved_artifact_ids", []
                            ),
                        }
                        for dependency_id in task.get("dependencies", [])
                        if dependency_id in tasks
                    ]
                    feedback = relevant_feedback_for_task(
                        task, [state for state, _ in tx.list("feedback")]
                    )
                    relevant_annotations = _relevant_annotations_for_task(
                        task,
                        [state for state, _ in tx.list("annotation")],
                        [state for state, _ in tx.list("artifact")],
                    )
                    open_changes = [
                        {
                            "change_id": state.get("change_id"),
                            "kind": state.get("kind"),
                            "reason": state.get("reason"),
                            "artifact_id": state.get("artifact_id"),
                        }
                        for state, _ in tx.list("change")
                        if state.get("task_id") == task_id
                        and state.get("status") == "open"
                    ]
                    cursor = tx.connection.execute(
                        "SELECT COALESCE(MAX(seq), 0) AS seq FROM events"
                    ).fetchone()["seq"]
                    updated_task.update(
                        {
                            "issued_context_revision": int(
                                task.get("context_revision", 1)
                            ),
                            "pending_context_update": None,
                        }
                    )
                    context_update_payload = compile_capsule(
                        repo_root=self.repo_root,
                        episode=episode,
                        task=updated_task,
                        task_version=task_version + 1,
                        dependency_states=dependency_states,
                        relevant_feedback=feedback,
                        relevant_annotations=relevant_annotations,
                        open_changes=open_changes,
                        why_now={
                            "context_update": True,
                            "delivery_policy": "attention_boundary",
                            "pending_context_update": pending_context_update,
                            "human_annotation_delivery": {
                                "boundary": "heartbeat_attention_boundary",
                                "count": len(relevant_annotations),
                                "annotation_ids": [
                                    item.get("annotation_id")
                                    for item in relevant_annotations
                                ],
                            },
                            "critical_path": bool(task.get("critical_path")),
                            "unlock_value": int(task.get("unlock_value", 0)),
                            "priority": int(task.get("priority", 0)),
                        },
                        cursor=int(cursor),
                        context_overrides=_relevant_context_overrides(
                            [
                                state
                                for state, _ in tx.list("context_override")
                            ],
                            updated_task,
                            episode_id,
                            int(updated_task.get("attempt", 0)),
                        ),
                    )
                    updated_task["active_capsule_hash"] = object_hash(
                        context_update_payload
                    )
            tx.transition(
                "lease",
                lease_id,
                lease_event,
                {
                    "generation": lease.get("generation"),
                    "meaningful_progress": meaningful_progress,
                    "novel_evidence": novel_evidence,
                    "stop_reasons": stop_reasons,
                },
                updated_lease,
                expected_version=lease_version,
            )
            task_transition = tx.transition(
                "task",
                task_id,
                task_event,
                {
                    "note": note.strip(),
                    "evidence_refs": validated_evidence,
                    "meaningful_progress": meaningful_progress,
                    "novel_evidence": novel_evidence,
                    "active_seconds": active_seconds,
                    "usage_delta": usage,
                    "checkpoint_due": checkpoint_due,
                    "stop_reasons": stop_reasons,
                },
                updated_task,
                expected_version=task_version,
            )
            context_update = None
            if context_update_payload is not None:
                context_update = tx.save_capsule(
                    task_id,
                    task_transition["aggregate_version"],
                    context_update_payload,
                )
            return {
                "task": updated_task,
                "lease": updated_lease,
                "meaningful_progress": meaningful_progress,
                "observed_evidence": validated_evidence,
                "novel_evidence": novel_evidence,
                "supervision": {
                    "checkpoint_due": checkpoint_due,
                    "stopped": bool(stop_reasons),
                    "stop_reasons": stop_reasons,
                    "active_seconds": active_seconds,
                    "resource_usage": resource_usage,
                },
                "context_update": context_update,
            }

        return self._execute(episode_id, "task.heartbeat", actor, payload, handler, request_id=request_id, now=now)

    def _prepare_artifacts(self, artifacts: list[dict[str, str]]) -> list[dict[str, Any]]:
        prepared: list[dict[str, Any]] = []
        for descriptor in artifacts:
            role = str(descriptor.get("role", "")).strip()
            raw_path = str(descriptor.get("path", "")).strip()
            if not role or not raw_path:
                raise DomainError(
                    "invalid_artifact",
                    "each submitted artifact requires role and path",
                    failed_invariant="artifact_descriptor_complete",
                )
            path = resolve_repo_path(self.repo_root, raw_path)
            if not path.is_file():
                raise DomainError(
                    "artifact_missing",
                    f"submitted artifact does not exist: {raw_path}",
                    failed_invariant="artifact_exists",
                    allowed_next=("submit", "gap"),
                    details={"role": role, "path": raw_path},
                )
            stat = path.stat()
            prepared.append(
                {
                    "role": role,
                    "path": display_path(self.repo_root, path),
                    "absolute_path": str(path),
                    "sha256": file_hash(path),
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                }
            )
        return sorted(prepared, key=lambda item: (item["role"], item["path"]))

    def submit(
        self,
        episode_id: str,
        task_id: str,
        *,
        actor: str,
        artifacts: list[dict[str, str]],
        generation: int | None = None,
        note: str = "",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        task_id = require_identifier(task_id, "task_id")
        now = self.clock()
        prepared = self._prepare_artifacts(artifacts)
        payload = {
            "task_id": task_id,
            "generation": generation,
            "artifacts": [{key: item[key] for key in ("role", "path", "sha256", "size")} for item in prepared],
            "note": note.strip(),
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            task, task_version = tx.require("task", task_id)
            artifact_states: list[dict[str, Any]] = []
            for item in prepared:
                path = Path(item["absolute_path"])
                stat = path.stat() if path.exists() else None
                if stat is None or stat.st_size != item["size"] or stat.st_mtime_ns != item["mtime_ns"]:
                    raise DomainError(
                        "artifact_changed_during_submit",
                        f"artifact changed while it was being hashed: {item['path']}",
                        failed_invariant="artifact_snapshot_stable",
                        allowed_next=("submit",),
                    )
                artifact_id = "art_" + object_hash(
                    {"task_id": task_id, "role": item["role"], "sha256": item["sha256"]}
                )[:24]
                artifact_states.append(
                    {
                        "artifact_id": artifact_id,
                        "episode_id": episode_id,
                        "role": item["role"],
                        "path": item["path"],
                        "sha256": item["sha256"],
                        "size": item["size"],
                        "producer_task_id": task_id,
                        "status": "candidate",
                        "contract_checks": [],
                        "created_at": now,
                    }
                )
            artifact_ids = sorted(item["artifact_id"] for item in artifact_states)
            if task.get("status") in {"candidate", "user_review_pending", "approved"}:
                prior = sorted((task.get("candidate") or {}).get("artifact_ids", []))
                if prior == artifact_ids and task.get("author") == actor:
                    return {"duplicate_submission": True, "task": task, "artifacts": artifact_states}
            if task.get("status") != "working":
                raise DomainError(
                    "invalid_transition",
                    f"task {task_id!r} cannot submit from status {task.get('status')!r}",
                    failed_invariant="task_submit_state",
                    allowed_next=("begin", "explain"),
                    details={"status": task.get("status")},
                )
            lease_id = f"lease:{task_id}"
            lease, lease_version = tx.require("lease", lease_id)
            if not lease_is_live(lease, now):
                raise DomainError(
                    "lease_expired",
                    "submission lease has expired",
                    failed_invariant="submit_requires_live_lease",
                    allowed_next=("begin", "explain"),
                )
            if lease.get("owner") != actor:
                raise DomainError(
                    "lease_owner_mismatch",
                    f"active lease is owned by {lease.get('owner')}, not {actor}",
                    failed_invariant="lease_owner_authority",
                    allowed_next=("explain",),
                )
            if generation is not None and int(lease.get("generation", 0)) != int(generation):
                raise DomainError(
                    "stale_lease_generation",
                    "submission refers to an obsolete lease generation",
                    failed_invariant="lease_generation_authority",
                    allowed_next=("explain",),
                )
            capsule_hash = str(task.get("active_capsule_hash") or "")
            capsule = tx.connection.execute(
                "SELECT 1 FROM capsules WHERE capsule_hash=? AND task_id=?", (capsule_hash, task_id)
            ).fetchone()
            if capsule is None:
                raise DomainError(
                    "context_capsule_missing",
                    "task has no issued context capsule",
                    failed_invariant="work_bound_to_capsule",
                    allowed_next=("begin", "explain"),
                )
            for reference in task.get("references", []):
                verify_reference(self.repo_root, reference)
            required_roles = set(task.get("output_contract", {}).get("required_artifact_roles", []))
            provided_roles = {item["role"] for item in artifact_states}
            missing_roles = sorted(required_roles - provided_roles)
            if missing_roles:
                raise DomainError(
                    "output_contract_incomplete",
                    "submission is missing required artifact roles",
                    failed_invariant="output_contract_satisfied",
                    allowed_next=("submit", "gap"),
                    details={"missing_roles": missing_roles, "provided_roles": sorted(provided_roles)},
                )
            for artifact_state, item in zip(artifact_states, prepared, strict=True):
                artifact_state["contract_checks"] = _kernel_artifact_contract(
                    str(item["role"]), Path(str(item["absolute_path"]))
                )
            resolved_input_artifact_ids = set(task.get("input_artifact_ids", []))
            for dependency_id in task.get("dependencies", []):
                dependency, _ = tx.require("task", dependency_id)
                if dependency.get("status") != "approved":
                    raise DomainError(
                        "dependency_changed_during_work",
                        "a dependency is no longer approved for this submission",
                        failed_invariant="submission_dependency_snapshot_current",
                        allowed_next=("explain", "begin"),
                        details={
                            "dependency_task_id": dependency_id,
                            "status": dependency.get("status"),
                        },
                    )
                resolved_input_artifact_ids.update(
                    dependency.get("approved_artifact_ids", [])
                )
            created_artifacts: list[dict[str, Any]] = []
            for artifact in artifact_states:
                current, artifact_version = tx.get("artifact", artifact["artifact_id"])
                if current is None:
                    tx.transition(
                        "artifact",
                        artifact["artifact_id"],
                        "ArtifactRegistered",
                        {"task_id": task_id, "role": artifact["role"], "sha256": artifact["sha256"]},
                        artifact,
                        expected_version=0,
                    )
                    created_artifacts.append(artifact)
                elif current.get("sha256") != artifact.get("sha256") or current.get("producer_task_id") != task_id:
                    raise DomainError(
                        "artifact_identity_conflict",
                        "artifact identity collides with different provenance",
                        failed_invariant="content_addressed_artifact_identity",
                    )
                else:
                    created_artifacts.append(current)
            candidate = {
                "artifact_ids": artifact_ids,
                "candidate_hash": object_hash(
                    [{"artifact_id": item["artifact_id"], "sha256": item["sha256"], "role": item["role"]} for item in artifact_states]
                ),
                "submitted_at": now,
                "submitted_by": actor,
                "note": note.strip(),
                "capsule_hash": capsule_hash,
                "input_artifact_ids": sorted(resolved_input_artifact_ids),
            }
            active_seconds = float(task.get("active_seconds", 0.0)) + _active_delta_seconds(lease, now)
            updated_task = {
                **task,
                "status": "candidate",
                "candidate": candidate,
                "active_capsule_hash": None,
                "active_seconds": active_seconds,
                "heartbeats_without_progress": 0,
                "updated_at": now,
                "last_progress_at": now,
            }
            task_event = tx.transition(
                "task",
                task_id,
                "TaskSubmitted",
                candidate,
                updated_task,
                expected_version=task_version,
            )
            for change_state, change_version in tx.list("change"):
                if change_state.get("task_id") != task_id or change_state.get("status") != "open":
                    continue
                addressed = {
                    **change_state,
                    "status": "addressed_pending_review",
                    "addressed_by_candidate_hash": candidate["candidate_hash"],
                    "addressed_at": now,
                }
                tx.transition(
                    "change",
                    change_state["change_id"],
                    "ChangeAddressedByCandidate",
                    {"task_id": task_id, "candidate_hash": candidate["candidate_hash"]},
                    addressed,
                    expected_version=change_version,
                )
            released_lease = {
                **lease,
                "status": "released",
                "released_at": now,
                "release_reason": "candidate_submitted",
                "accounted_at": now,
            }
            tx.transition(
                "lease",
                lease_id,
                "LeaseReleased",
                {"reason": "candidate_submitted", "task_id": task_id},
                released_lease,
                expected_version=lease_version,
            )
            for upstream_id in sorted(resolved_input_artifact_ids):
                for downstream_id in artifact_ids:
                    tx.connection.execute(
                        """
                        INSERT OR IGNORE INTO artifact_edges(
                          upstream_artifact_id, downstream_artifact_id, relation, task_id, created_seq
                        ) VALUES (?, ?, 'consumed_to_produce', ?, ?)
                        """,
                        (upstream_id, downstream_id, task_id, task_event["seq"]),
                    )
            return {"task": updated_task, "artifacts": created_artifacts, "lease": released_lease}

        return self._execute(episode_id, "task.submit", actor, payload, handler, request_id=request_id, now=now)

    def _compile_review_capsule(
        self,
        *,
        episode: dict[str, Any],
        task: dict[str, Any],
        task_version: int,
        dependency_states: list[dict[str, Any]],
        feedback: list[dict[str, Any]],
        annotations: list[dict[str, Any]],
        open_changes: list[dict[str, Any]],
        gate_receipts: list[dict[str, Any]],
        artifacts: list[dict[str, Any]],
        context_overrides: list[dict[str, Any]],
        resolved_gaps: list[dict[str, Any]],
        actor: str,
        cursor: int,
    ) -> dict[str, Any]:
        resolved_gap_decisions = [
            {
                key: gap.get(key)
                for key in (
                    "gap_id",
                    "kind",
                    "reason",
                    "resolution",
                    "reported_by",
                    "resolved_by",
                    "created_at",
                    "resolved_at",
                )
            }
            for gap in sorted(
                resolved_gaps,
                key=lambda item: (
                    str(item.get("resolved_at", "")),
                    str(item.get("gap_id", "")),
                ),
            )
        ]
        base = compile_capsule(
            repo_root=self.repo_root,
            episode=episode,
            task=task,
            task_version=task_version,
            dependency_states=dependency_states,
            relevant_feedback=feedback,
            relevant_annotations=annotations,
            open_changes=open_changes,
            why_now={
                "action": "independent_review",
                "candidate_hash": (task.get("candidate") or {}).get(
                    "candidate_hash"
                ),
                "all_hard_gates_passed": True,
                "human_annotation_delivery": {
                    "boundary": "review_context",
                    "count": len(annotations),
                    "annotation_ids": [
                        item.get("annotation_id") for item in annotations
                    ],
                },
                "resolved_gap_decisions": resolved_gap_decisions,
            },
            cursor=cursor,
            context_overrides=context_overrides,
        )
        base.pop("semantic_hash", None)
        base.pop("submission_contract", None)
        # A review context must remain exact for the candidate and its relevant
        # rules without being invalidated by an unrelated event elsewhere in
        # the episode. The actual global cursor is returned in the response
        # envelope for incremental reads; it is deliberately not part of the
        # signed review capsule.
        base.pop("state_cursor", None)
        candidate_hash = (task.get("candidate") or {}).get("candidate_hash")
        for block in base.get("context_blocks", []):
            if block.get("slot") != "runtime.facts":
                continue
            block["block_id"] = (
                f"runtime:review:{task.get('task_id')}:{candidate_hash}:{task_version}"
            )
            block["content"] = json.dumps(
                {
                    "why_now": base.get("why_now"),
                    "dependency_snapshot": dependency_states,
                    "task_version": task_version,
                    "preview": False,
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            block["content_hash"] = object_hash(block["content"])
            block["source"] = {
                "kind": "review_projection",
                "task_id": task.get("task_id"),
                "candidate_hash": candidate_hash,
            }
            block["version"] = str(task_version)
        base["assembled_prompt"] = "\n\n".join(
            f"## {item['label']}\n{item['content']}"
            for item in base.get("context_blocks", [])
        )
        base.setdefault("context_manifest", {})["cursor_scope"] = (
            "response_envelope_only"
        )
        base["resolved_gap_decisions"] = resolved_gap_decisions
        remaining = MAX_REVIEW_INLINE_CHARS
        review_artifacts: list[dict[str, Any]] = []
        for artifact in sorted(artifacts, key=lambda item: item["artifact_id"]):
            path = resolve_repo_path(self.repo_root, str(artifact.get("path", "")))
            if not path.is_file() or file_hash(path) != artifact.get("sha256"):
                raise DomainError(
                    "candidate_artifact_drift",
                    f"candidate artifact changed or disappeared: {artifact.get('path')}",
                    failed_invariant="review_exact_candidate_hash",
                    allowed_next=("change", "submit"),
                    details={"artifact_id": artifact.get("artifact_id")},
                )
            descriptor = {
                key: artifact.get(key)
                for key in (
                    "artifact_id",
                    "role",
                    "path",
                    "sha256",
                    "size",
                    "producer_task_id",
                    "status",
                    "contract_checks",
                )
            }
            if path.suffix.lower() in REVIEW_TEXT_SUFFIXES:
                content = path.read_text(encoding="utf-8", errors="replace")
                if len(content) <= remaining:
                    descriptor["content"] = content
                    descriptor["content_chars"] = len(content)
                    remaining -= len(content)
                else:
                    descriptor["content_omitted"] = "review_inline_char_cap"
            else:
                descriptor["content_omitted"] = "binary_or_media_use_exact_path"
            review_artifacts.append(descriptor)
        exact_gates = [
            {
                key: receipt.get(key)
                for key in (
                    "gate_id",
                    "validator_id",
                    "validator_version",
                    "validator_sha256",
                    "status",
                    "summary",
                    "checks",
                )
            }
            for receipt in gate_receipts
            if receipt.get("task_id") == task.get("task_id")
            and receipt.get("candidate_hash") == candidate_hash
        ]
        return {
            **base,
            "schema": "lecture-review-capsule-v1",
            "reviewer": actor,
            "candidate": {
                "candidate_hash": candidate_hash,
                "author": task.get("author"),
                "submitted_at": (task.get("candidate") or {}).get("submitted_at"),
                "note": (task.get("candidate") or {}).get("note"),
            },
            "candidate_artifacts": review_artifacts,
            "hard_gate_receipts": exact_gates,
            "review_contract": {
                "independent_from_author": True,
                "review_exact_candidate_only": True,
                "record_findings_with_evidence": True,
                "machine_gates_do_not_replace_semantic_review": True,
                "human_authority_remains_separate": True,
            },
            "review_context_budget": {
                "max_inline_artifact_chars": MAX_REVIEW_INLINE_CHARS,
                "used_inline_artifact_chars": MAX_REVIEW_INLINE_CHARS - remaining,
            },
        }

    def review_context(
        self,
        episode_id: str,
        task_id: str,
        *,
        actor: str,
    ) -> dict[str, Any]:
        """Return the exact read-only attention capsule for one candidate review."""
        task_id = require_identifier(task_id, "task_id")
        store = self.data_root.episode_store(episode_id)
        snapshot = self._snapshot(store)
        task, task_version = store.get("task", task_id)
        if task is None:
            return DomainError(
                "not_found",
                f"task {task_id!r} does not exist",
                failed_invariant="aggregate_exists",
                allowed_next=("explain",),
                http_status=404,
            ).as_result()
        if task.get("status") != "candidate":
            return DomainError(
                "invalid_transition",
                "review context is available only for a submitted candidate",
                failed_invariant="review_candidate_state",
                allowed_next=("next", "explain"),
            ).as_result()
        if task.get("author") == actor:
            return DomainError(
                "review_independence_conflict",
                "candidate author cannot receive an acceptance-review capsule",
                failed_invariant="author_reviewer_independence",
                allowed_next=("next",),
            ).as_result()
        gates = [state for state, _ in snapshot["gates"]]
        missing = _missing_validator_receipts(task, gates)
        if missing:
            return DomainError(
                "quality_gate_incomplete",
                "review context is withheld until required hard gates pass",
                failed_invariant="required_quality_gates_pass",
                allowed_next=("gate-run", "next", "explain"),
                details={
                    "missing_validators": [
                        item.get("validator_id") for item in missing
                    ]
                },
            ).as_result()
        tasks = {state["task_id"]: state for state, _ in snapshot["tasks"]}
        dependency_states = [
            {
                "task_id": dependency_id,
                "status": tasks[dependency_id].get("status"),
                "approved_artifact_ids": tasks[dependency_id].get(
                    "approved_artifact_ids", []
                ),
            }
            for dependency_id in task.get("dependencies", [])
            if dependency_id in tasks
        ]
        artifact_by_id = {
            state["artifact_id"]: state for state, _ in snapshot["artifacts"]
        }
        artifacts = [
            artifact_by_id[artifact_id]
            for artifact_id in (task.get("candidate") or {}).get("artifact_ids", [])
            if artifact_id in artifact_by_id
        ]
        capsule = self._compile_review_capsule(
            episode=snapshot["episode"],
            task=task,
            task_version=task_version,
            dependency_states=dependency_states,
            feedback=relevant_feedback_for_task(
                task, [state for state, _ in snapshot["feedback"]]
            ),
            annotations=_relevant_annotations_for_task(
                task,
                [state for state, _ in snapshot["annotations"]],
                [state for state, _ in snapshot["artifacts"]],
            ),
            open_changes=[
                state
                for state, _ in snapshot["changes"]
                if state.get("task_id") == task_id
                and state.get("status") in {"open", "addressed_pending_review"}
            ],
            gate_receipts=gates,
            artifacts=artifacts,
            context_overrides=_relevant_context_overrides(
                [state for state, _ in snapshot["context_overrides"]],
                task,
                episode_id,
                int(task.get("attempt", 0)),
            ),
            resolved_gaps=[
                state
                for state, _ in snapshot["gaps"]
                if state.get("task_id") == task_id
                and state.get("status") == "resolved"
            ],
            actor=actor,
            cursor=store.cursor(),
        )
        return {
            "ok": True,
            "status": "read_only",
            "episode_id": episode_id,
            "task_id": task_id,
            "candidate_hash": (task.get("candidate") or {}).get("candidate_hash"),
            "review_context_hash": object_hash(capsule),
            "capsule": capsule,
            "cursor": store.cursor(),
            "allowed_next": ["review"],
        }

    def run_gate(
        self,
        episode_id: str,
        task_id: str,
        validator_id: str,
        *,
        actor: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Run one version-pinned hard validator and record its normalized receipt."""
        task_id = require_identifier(task_id, "task_id")
        validator_id = require_identifier(validator_id, "validator_id")
        now = self.clock()
        store = self.data_root.episode_store(episode_id)
        task, task_version = store.get("task", task_id)
        candidate_hash = ((task or {}).get("candidate") or {}).get("candidate_hash")
        payload = {
            "task_id": task_id,
            "validator_id": validator_id,
            "candidate_hash": candidate_hash,
        }
        command_name = "task.gate"
        resolved_request_id = self._request_id(
            command_name, actor, payload, request_id, now
        )
        prior = store.prior_command(
            request_id=resolved_request_id,
            command_name=command_name,
            actor=actor,
            payload=payload,
        )
        if prior is not None:
            return prior

        preflight_error: DomainError | None = None
        descriptor: dict[str, Any] | None = None
        result: dict[str, Any] | None = None
        existing_pass: dict[str, Any] | None = None
        try:
            if task is None:
                raise DomainError(
                    "not_found",
                    f"task {task_id!r} does not exist",
                    failed_invariant="aggregate_exists",
                    allowed_next=("explain",),
                    http_status=404,
                )
            if task.get("status") != "candidate" or not candidate_hash:
                raise DomainError(
                    "invalid_transition",
                    "hard gates run only against an exact submitted candidate",
                    failed_invariant="gate_candidate_state",
                    allowed_next=("next", "submit", "explain"),
                )
            descriptor = next(
                (
                    item
                    for item in task.get("required_validators", [])
                    if item.get("validator_id") == validator_id
                ),
                None,
            )
            if descriptor is None:
                raise DomainError(
                    "validator_not_bound",
                    f"validator {validator_id!r} is not bound to task {task_id!r}",
                    failed_invariant="gate_uses_planned_validator",
                    allowed_next=("change", "explain"),
                )
            verify_validator(self.repo_root, descriptor)
            existing_pass = next(
                (
                    state
                    for state, _ in store.list("gate")
                    if state.get("task_id") == task_id
                    and state.get("candidate_hash") == candidate_hash
                    and state.get("validator_id") == validator_id
                    and state.get("validator_sha256") == descriptor.get("sha256")
                    and state.get("status") == "pass"
                ),
                None,
            )
            if existing_pass is None:
                artifacts: list[dict[str, Any]] = []
                for artifact_id in task.get("candidate", {}).get("artifact_ids", []):
                    artifact, _ = store.get("artifact", artifact_id)
                    if artifact is None:
                        raise DomainError(
                            "candidate_artifact_missing",
                            f"candidate artifact state is missing: {artifact_id}",
                            failed_invariant="gate_candidate_artifacts_exist",
                            allowed_next=("change", "submit"),
                        )
                    path = resolve_repo_path(self.repo_root, str(artifact.get("path", "")))
                    artifacts.append(
                        {
                            **artifact,
                            "absolute_path": str(path),
                        }
                    )
                result = execute_validator(
                    self.repo_root,
                    descriptor,
                    {
                        "schema": "lecture-supervision-gate-input-v1",
                        "episode_id": episode_id,
                        "task_id": task_id,
                        "candidate_hash": candidate_hash,
                        "artifacts": artifacts,
                    },
                )
        except DomainError as error:
            preflight_error = error

        def handler(tx: Transaction) -> dict[str, Any]:
            if preflight_error is not None:
                raise preflight_error
            assert task is not None and descriptor is not None
            current_task, current_version = tx.require("task", task_id)
            current_candidate_hash = (current_task.get("candidate") or {}).get(
                "candidate_hash"
            )
            if current_version != task_version or current_candidate_hash != candidate_hash:
                raise DomainError(
                    "candidate_changed_during_gate",
                    "candidate changed while the validator was running",
                    failed_invariant="gate_exact_candidate_compare_and_swap",
                    allowed_next=("next", "gate-run", "explain"),
                    details={
                        "expected_task_version": task_version,
                        "actual_task_version": current_version,
                        "expected_candidate_hash": candidate_hash,
                        "actual_candidate_hash": current_candidate_hash,
                    },
                )
            current_descriptor = next(
                (
                    item
                    for item in current_task.get("required_validators", [])
                    if item.get("validator_id") == validator_id
                ),
                None,
            )
            if current_descriptor != descriptor:
                raise DomainError(
                    "validator_binding_changed",
                    "validator binding changed while the gate was running",
                    failed_invariant="gate_validator_compare_and_swap",
                    allowed_next=("next", "gate-run", "explain"),
                )
            verify_validator(self.repo_root, descriptor)
            if existing_pass is not None:
                return {"already_satisfied": True, "gate": existing_pass}
            assert result is not None
            gate_id = "gate_" + object_hash(
                {
                    "request_id": tx.request_id,
                    "task_id": task_id,
                    "candidate_hash": candidate_hash,
                    "validator_sha256": descriptor["sha256"],
                }
            )[:24]
            gate_state = {
                "gate_id": gate_id,
                "episode_id": episode_id,
                "task_id": task_id,
                "candidate_hash": candidate_hash,
                "validator_id": validator_id,
                "validator_version": descriptor["version"],
                "validator_sha256": descriptor["sha256"],
                "status": result["status"],
                "summary": str(result.get("summary", "")),
                "checks": result.get("checks", []),
                "runner": result.get("runner", {}),
                "actor": actor,
                "created_at": now,
            }
            event_type = {
                "pass": "QualityGatePassed",
                "fail": "QualityGateFailed",
                "error": "QualityGateErrored",
            }[result["status"]]
            tx.transition(
                "gate",
                gate_id,
                event_type,
                {
                    "task_id": task_id,
                    "candidate_hash": candidate_hash,
                    "validator_id": validator_id,
                    "validator_sha256": descriptor["sha256"],
                    "status": result["status"],
                },
                gate_state,
                expected_version=0,
            )
            return {"gate": gate_state}

        return self._execute(
            episode_id,
            command_name,
            actor,
            payload,
            handler,
            request_id=resolved_request_id,
            now=now,
        )

    def review(
        self,
        episode_id: str,
        task_id: str,
        *,
        actor: str,
        verdict: str,
        findings: list[dict[str, Any]] | None = None,
        note: str = "",
        review_context_hash: str | None = None,
        return_to: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        task_id = require_identifier(task_id, "task_id")
        verdict = verdict.strip().lower()
        if verdict not in {"pass", "revise"}:
            raise DomainError(
                "invalid_verdict",
                "review verdict must be pass or revise",
                failed_invariant="review_verdict_enum",
            )
        if return_to is not None:
            return_to = require_identifier(return_to, "return_to")
        now = self.clock()
        payload = {
            "task_id": task_id,
            "verdict": verdict,
            "findings": findings or [],
            "note": note.strip(),
            "review_context_hash": review_context_hash,
            "return_to": return_to,
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            episode, _ = tx.require("episode", episode_id)
            task, task_version = tx.require("task", task_id)
            if task.get("status") != "candidate":
                raise DomainError(
                    "invalid_transition",
                    f"task {task_id!r} cannot be reviewed from status {task.get('status')!r}",
                    failed_invariant="review_candidate_state",
                    allowed_next=("next", "explain"),
                )
            if task.get("author") == actor:
                raise DomainError(
                    "review_independence_conflict",
                    "candidate author cannot grant its acceptance review",
                    failed_invariant="author_reviewer_independence",
                    allowed_next=("next", "review-context"),
                )
            candidate = task.get("candidate") or {}
            gate_states = [state for state, _ in tx.list("gate")]
            if verdict == "pass":
                required_validators = [
                    item
                    for item in task.get("required_validators", [])
                    if item.get("required", True)
                ]
                for descriptor in required_validators:
                    verify_validator(self.repo_root, descriptor)
                missing = _missing_validator_receipts(
                    task, gate_states
                )
                if missing:
                    raise DomainError(
                        "quality_gate_incomplete",
                        "candidate cannot pass review until every required hard gate passes",
                        failed_invariant="required_quality_gates_pass",
                        allowed_next=("gate-run", "next", "explain"),
                        details={
                            "candidate_hash": candidate.get("candidate_hash"),
                            "missing_validators": [
                                {
                                    "validator_id": item.get("validator_id"),
                                    "version": item.get("version"),
                                    "sha256": item.get("sha256"),
                                }
                                for item in missing
                            ],
                        },
                    )
            artifact_ids = list(candidate.get("artifact_ids", []))
            artifacts: list[tuple[dict[str, Any], int]] = []
            for artifact_id in artifact_ids:
                artifact, version = tx.require("artifact", artifact_id)
                path = resolve_repo_path(self.repo_root, str(artifact.get("path", "")))
                if not path.is_file() or file_hash(path) != artifact.get("sha256"):
                    raise DomainError(
                        "candidate_artifact_drift",
                        f"candidate artifact changed or disappeared: {artifact.get('path')}",
                        failed_invariant="review_exact_candidate_hash",
                        allowed_next=("change", "submit"),
                        details={"artifact_id": artifact_id},
                    )
                artifacts.append((artifact, version))
            if not review_context_hash:
                raise DomainError(
                    "review_context_required",
                    "review must bind the exact reviewer context capsule",
                    failed_invariant="review_attention_capsule_bound",
                    allowed_next=("review-context", "next", "explain"),
                )
            all_tasks = {
                state["task_id"]: state for state, _ in tx.list("task")
            }
            dependency_states = [
                {
                    "task_id": dependency_id,
                    "status": all_tasks[dependency_id].get("status"),
                    "approved_artifact_ids": all_tasks[dependency_id].get(
                        "approved_artifact_ids", []
                    ),
                }
                for dependency_id in task.get("dependencies", [])
                if dependency_id in all_tasks
            ]
            cursor = tx.connection.execute(
                "SELECT COALESCE(MAX(seq), 0) AS seq FROM events"
            ).fetchone()["seq"]
            review_capsule = self._compile_review_capsule(
                episode=episode,
                task=task,
                task_version=task_version,
                dependency_states=dependency_states,
                feedback=relevant_feedback_for_task(
                    task, [state for state, _ in tx.list("feedback")]
                ),
                annotations=_relevant_annotations_for_task(
                    task,
                    [state for state, _ in tx.list("annotation")],
                    [state for state, _ in tx.list("artifact")],
                ),
                open_changes=[
                    state
                    for state, _ in tx.list("change")
                    if state.get("task_id") == task_id
                    and state.get("status")
                    in {"open", "addressed_pending_review"}
                ],
                gate_receipts=gate_states,
                artifacts=[artifact for artifact, _ in artifacts],
                context_overrides=_relevant_context_overrides(
                    [state for state, _ in tx.list("context_override")],
                    task,
                    episode_id,
                    int(task.get("attempt", 0)),
                ),
                resolved_gaps=[
                    state
                    for state, _ in tx.list("gap")
                    if state.get("task_id") == task_id
                    and state.get("status") == "resolved"
                ],
                actor=actor,
                cursor=int(cursor),
            )
            computed_review_context_hash = object_hash(review_capsule)
            if computed_review_context_hash != review_context_hash:
                raise DomainError(
                    "review_context_stale",
                    "review context does not match the current candidate and rules",
                    failed_invariant="review_attention_capsule_exact",
                    allowed_next=("review-context", "next", "explain"),
                    details={
                        "provided_review_context_hash": review_context_hash,
                        "current_review_context_hash": computed_review_context_hash,
                    },
                )
            review_id = "review_" + object_hash({"request_id": tx.request_id, "task_id": task_id})[:20]
            review_state = {
                "review_id": review_id,
                "episode_id": episode_id,
                "task_id": task_id,
                "candidate_hash": candidate.get("candidate_hash"),
                "reviewer": actor,
                "author": task.get("author"),
                "verdict": verdict,
                "findings": findings or [],
                "note": note.strip(),
                "review_context_hash": review_context_hash,
                "created_at": now,
            }
            tx.transition("review", review_id, "ReviewRecorded", payload, review_state, expected_version=0)
            saved_context = tx.save_capsule(task_id, task_version, review_capsule)
            if saved_context["capsule_hash"] != review_context_hash:
                raise DomainError(
                    "review_context_hash_mismatch",
                    "stored review context hash differs from the reviewed capsule",
                    failed_invariant="review_capsule_storage_exact",
                )
            if verdict == "pass":
                next_status = "user_review_pending" if task.get("human_gate") else "approved"
                updated_task = {
                    **task,
                    "status": next_status,
                    "last_review_id": review_id,
                    "approved_artifact_ids": artifact_ids if next_status == "approved" else task.get("approved_artifact_ids", []),
                    "updated_at": now,
                }
                for artifact, version in artifacts:
                    updated_artifact = {**artifact, "status": "approved" if next_status == "approved" else "user_review_pending", "review_id": review_id}
                    tx.transition(
                        "artifact",
                        artifact["artifact_id"],
                        "ArtifactAccepted" if next_status == "approved" else "ArtifactAwaitingHumanReview",
                        {"review_id": review_id},
                        updated_artifact,
                        expected_version=version,
                    )
                event_type = "TaskApproved" if next_status == "approved" else "TaskAwaitingHumanReview"
                change_status = "awaiting_human_review" if next_status == "user_review_pending" else "resolved"
            else:
                routed_actor = return_to or str(task.get("author") or "pool")
                routed_actor = require_identifier(routed_actor, "return_to")
                return_ticket_id = "return_" + object_hash(
                    {
                        "review_id": review_id,
                        "task_id": task_id,
                        "assigned_to": routed_actor,
                    }
                )[:20]
                return_ticket = {
                    "return_ticket_id": return_ticket_id,
                    "episode_id": episode_id,
                    "task_id": task_id,
                    "review_id": review_id,
                    "original_author": task.get("author"),
                    "assigned_to": routed_actor,
                    "routed_by": actor,
                    "status": "pending",
                    "delivery_policy": "attention_boundary",
                    "interrupt_active_lease": False,
                    "findings": findings or [],
                    "note": note.strip(),
                    "created_at": now,
                    "updated_at": now,
                }
                tx.transition(
                    "return_ticket",
                    return_ticket_id,
                    "DeferredReturnQueued",
                    {
                        "task_id": task_id,
                        "review_id": review_id,
                        "assigned_to": routed_actor,
                        "delivery_policy": "attention_boundary",
                    },
                    return_ticket,
                    expected_version=0,
                )
                updated_task = {
                    **task,
                    "status": "rework",
                    "last_review_id": review_id,
                    "blockers": [{"kind": "review_findings", "review_id": review_id}],
                    "active_capsule_hash": None,
                    "pending_return_ticket_id": return_ticket_id,
                    "preferred_actor": routed_actor,
                    "updated_at": now,
                }
                for artifact, version in artifacts:
                    updated_artifact = {**artifact, "status": "needs_rework", "review_id": review_id}
                    tx.transition(
                        "artifact",
                        artifact["artifact_id"],
                        "ArtifactNeedsRework",
                        {"review_id": review_id},
                        updated_artifact,
                        expected_version=version,
                    )
                event_type = "TaskRevisionRequested"
                change_status = "open"
            for change_state, change_version in tx.list("change"):
                if (
                    change_state.get("task_id") != task_id
                    or change_state.get("status") not in {"addressed_pending_review", "awaiting_human_review"}
                ):
                    continue
                updated_change = {
                    **change_state,
                    "status": change_status,
                    "review_id": review_id,
                    "resolved_at": now if change_status == "resolved" else None,
                }
                tx.transition(
                    "change",
                    change_state["change_id"],
                    "ChangeResolved" if change_status == "resolved" else (
                        "ChangeAwaitingHumanReview" if change_status == "awaiting_human_review" else "ChangeReopened"
                    ),
                    {"review_id": review_id, "verdict": verdict},
                    updated_change,
                    expected_version=change_version,
                )
            tx.transition(
                "task",
                task_id,
                event_type,
                {"review_id": review_id, "verdict": verdict},
                updated_task,
                expected_version=task_version,
            )
            fulfilled_routes = (
                self._fulfill_route_switches(tx, task_id, now)
                if verdict == "pass" and next_status == "approved"
                else []
            )
            released_downstream_tasks = (
                self._release_descendants_after_upstream_reapproval(
                    tx, task_id, now
                )
                if verdict == "pass" and next_status == "approved"
                else []
            )
            return {
                "task": updated_task,
                "review": review_state,
                "fulfilled_route_switches": fulfilled_routes,
                "released_downstream_tasks": released_downstream_tasks,
                "return_ticket": return_ticket if verdict == "revise" else None,
            }

        return self._execute(episode_id, "task.review", actor, payload, handler, request_id=request_id, now=now)

    def reroute_return(
        self,
        episode_id: str,
        return_ticket_id: str,
        *,
        actor: str,
        to_actor: str,
        reason: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        return_ticket_id = require_identifier(
            return_ticket_id, "return_ticket_id"
        )
        to_actor = require_identifier(to_actor, "to_actor")
        if not reason.strip():
            raise DomainError(
                "return_route_reason_required",
                "return rerouting requires an explicit reason",
                failed_invariant="return_routing_auditable",
            )
        now = self.clock()
        payload = {
            "return_ticket_id": return_ticket_id,
            "to_actor": to_actor,
            "reason": reason.strip(),
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            ticket, ticket_version = tx.require(
                "return_ticket", return_ticket_id
            )
            if ticket.get("status") != "pending":
                raise DomainError(
                    "return_ticket_not_pending",
                    "only a pending return can be rerouted",
                    failed_invariant="return_route_pending",
                    allowed_next=("explain",),
                    details={"status": ticket.get("status")},
                )
            if ticket.get("assigned_to") == to_actor:
                return {"unchanged": True, "return_ticket": ticket}
            task_id = str(ticket["task_id"])
            task, task_version = tx.require("task", task_id)
            updated_ticket = {
                **ticket,
                "assigned_to": to_actor,
                "rerouted_by": actor,
                "reroute_reason": reason.strip(),
                "rerouted_at": now,
                "updated_at": now,
            }
            tx.transition(
                "return_ticket",
                return_ticket_id,
                "DeferredReturnRerouted",
                payload,
                updated_ticket,
                expected_version=ticket_version,
            )
            updated_task = {
                **task,
                "preferred_actor": to_actor,
                "updated_at": now,
            }
            tx.transition(
                "task",
                task_id,
                "TaskReturnRerouted",
                payload,
                updated_task,
                expected_version=task_version,
            )
            return {"return_ticket": updated_ticket, "task": updated_task}

        return self._execute(
            episode_id,
            "return.reroute",
            actor,
            payload,
            handler,
            request_id=request_id,
            now=now,
        )

    def human_decide(
        self,
        episode_id: str,
        task_id: str,
        *,
        actor: str,
        verdict: str,
        note: str = "",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        task_id = require_identifier(task_id, "task_id")
        verdict = verdict.strip().lower()
        if verdict not in {"approve", "revise"}:
            raise DomainError("invalid_verdict", "human verdict must be approve or revise", "human_verdict_enum")
        now = self.clock()
        payload = {"task_id": task_id, "verdict": verdict, "note": note.strip()}

        def handler(tx: Transaction) -> dict[str, Any]:
            task, task_version = tx.require("task", task_id)
            if task.get("status") != "user_review_pending":
                raise DomainError(
                    "invalid_transition",
                    "human decision is only valid at user_review_pending",
                    failed_invariant="human_gate_state",
                    allowed_next=("explain",),
                )
            artifact_ids = list((task.get("candidate") or {}).get("artifact_ids", []))
            next_status = "approved" if verdict == "approve" else "rework"
            updated_task = {
                **task,
                "status": next_status,
                "approved_artifact_ids": artifact_ids if verdict == "approve" else task.get("approved_artifact_ids", []),
                "active_capsule_hash": None if verdict == "revise" else task.get("active_capsule_hash"),
                "blockers": [] if verdict == "approve" else [{"kind": "human_revision", "note": note.strip()}],
                "human_decision": {"actor": actor, "verdict": verdict, "note": note.strip(), "at": now},
                "updated_at": now,
            }
            for artifact_id in artifact_ids:
                artifact, version = tx.require("artifact", artifact_id)
                updated_artifact = {**artifact, "status": "approved" if verdict == "approve" else "needs_rework"}
                tx.transition(
                    "artifact",
                    artifact_id,
                    "ArtifactHumanApproved" if verdict == "approve" else "ArtifactHumanRevisionRequested",
                    payload,
                    updated_artifact,
                    expected_version=version,
                )
            for change_state, change_version in tx.list("change"):
                if change_state.get("task_id") != task_id or change_state.get("status") != "awaiting_human_review":
                    continue
                updated_change = {
                    **change_state,
                    "status": "resolved" if verdict == "approve" else "open",
                    "human_decision": verdict,
                    "resolved_at": now if verdict == "approve" else None,
                }
                tx.transition(
                    "change",
                    change_state["change_id"],
                    "ChangeHumanApproved" if verdict == "approve" else "ChangeReopened",
                    payload,
                    updated_change,
                    expected_version=change_version,
                )
            tx.transition(
                "task",
                task_id,
                "TaskHumanApproved" if verdict == "approve" else "TaskHumanRevisionRequested",
                payload,
                updated_task,
                expected_version=task_version,
            )
            fulfilled_routes = (
                self._fulfill_route_switches(tx, task_id, now)
                if verdict == "approve"
                else []
            )
            released_downstream_tasks = (
                self._release_descendants_after_upstream_reapproval(
                    tx, task_id, now
                )
                if verdict == "approve"
                else []
            )
            return {
                "task": updated_task,
                "fulfilled_route_switches": fulfilled_routes,
                "released_downstream_tasks": released_downstream_tasks,
            }

        return self._execute(episode_id, "task.human_decide", actor, payload, handler, request_id=request_id, now=now)

    def add_context_override(
        self,
        episode_id: str,
        task_id: str,
        *,
        actor: str,
        instruction: str,
        label: str = "临时要求",
        scope: str = "task",
        assembly_mode: str = "append",
        context_slot: str = "temporary.instructions",
        delivery_policy: str = "attention_boundary",
        precedence: int = 700,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Add an auditable runtime instruction without mutating stable rule packs."""

        task_id = require_identifier(task_id, "task_id")
        instruction = instruction.strip()
        label = label.strip() or "临时要求"
        scope = scope.strip()
        assembly_mode = assembly_mode.strip()
        context_slot = context_slot.strip()
        delivery_policy = delivery_policy.strip()
        if not instruction:
            raise DomainError(
                "context_override_instruction_required",
                "temporary context requires explicit instruction text",
                failed_invariant="context_override_content_explicit",
            )
        if scope not in CONTEXT_OVERRIDE_SCOPES:
            raise DomainError(
                "invalid_context_override_scope",
                f"unsupported context scope: {scope}",
                failed_invariant="context_override_scope_known",
            )
        if assembly_mode not in CONTEXT_OVERRIDE_MODES:
            raise DomainError(
                "invalid_context_override_mode",
                f"unsupported assembly mode: {assembly_mode}",
                failed_invariant="context_override_mode_known",
            )
        if delivery_policy not in CONTEXT_OVERRIDE_DELIVERY:
            raise DomainError(
                "invalid_context_delivery_policy",
                f"unsupported delivery policy: {delivery_policy}",
                failed_invariant="context_delivery_policy_known",
            )
        if assembly_mode == "replace" and not context_slot:
            raise DomainError(
                "context_replace_slot_required",
                "replacing context requires an explicit target slot",
                failed_invariant="context_replace_target_explicit",
            )
        now = self.clock()
        logical = {
            "episode_id": episode_id,
            "task_id": task_id,
            "instruction": instruction,
            "label": label,
            "scope": scope,
            "assembly_mode": assembly_mode,
            "context_slot": context_slot,
            "delivery_policy": delivery_policy,
            "precedence": int(precedence),
        }
        override_id = "ctx_" + object_hash(logical)[:20]
        payload = {**logical, "override_id": override_id}

        def handler(tx: Transaction) -> dict[str, Any]:
            task, task_version = tx.require("task", task_id)
            existing, _ = tx.get("context_override", override_id)
            if existing is not None:
                return {"duplicate_override": True, "context_override": existing, "task": task}
            if task.get("status") in {
                "candidate",
                "user_review_pending",
                "approved",
                "cancelled",
                "superseded",
            }:
                raise DomainError(
                    "context_override_requires_rework",
                    "submitted or terminal work must be reopened through an explicit scope change",
                    failed_invariant="accepted_output_not_silently_reprompted",
                    allowed_next=("change", "route-switch", "explain"),
                )
            current_attempt = int(task.get("attempt", 0))
            effective_attempt = (
                current_attempt
                if task.get("status") == "working"
                and delivery_policy == "attention_boundary"
                else current_attempt + 1
            )
            override_state = {
                **payload,
                "episode_id": episode_id,
                "content_unit_id": task.get("content_unit_id"),
                "version": 1,
                "status": "active",
                "effective_attempt": effective_attempt,
                "created_by": actor,
                "created_at": now,
            }
            tx.transition(
                "context_override",
                override_id,
                "ContextOverrideAdded",
                payload,
                override_state,
                expected_version=0,
            )
            updated_task = {
                **task,
                "context_revision": int(task.get("context_revision", 1)) + 1,
                "context_override_ids": [
                    *task.get("context_override_ids", []),
                    override_id,
                ],
                "updated_at": now,
            }
            lease_update = None
            if task.get("status") == "working" and delivery_policy == "immediate":
                lease_id = f"lease:{task_id}"
                lease, lease_version = tx.require("lease", lease_id)
                lease_update = {
                    **lease,
                    "status": "revoked",
                    "revoked_at": now,
                    "release_reason": "immediate_context_override",
                    "accounted_at": now,
                }
                tx.transition(
                    "lease",
                    lease_id,
                    "LeaseRevokedByContextOverride",
                    {"override_id": override_id},
                    lease_update,
                    expected_version=lease_version,
                )
                updated_task.update(
                    {
                        "status": "rework",
                        "active_capsule_hash": None,
                        "pending_context_update": None,
                    }
                )
            elif task.get("status") == "working" and delivery_policy == "attention_boundary":
                updated_task["pending_context_update"] = {
                    "override_id": override_id,
                    "delivery_policy": "attention_boundary",
                    "context_revision": updated_task["context_revision"],
                }
            tx.transition(
                "task",
                task_id,
                "TaskContextChanged",
                {
                    "override_id": override_id,
                    "delivery_policy": delivery_policy,
                    "assembly_mode": assembly_mode,
                    "scope": scope,
                },
                updated_task,
                expected_version=task_version,
            )
            return {
                "context_override": override_state,
                "task": updated_task,
                "lease": lease_update,
                "delivery": (
                    "next_heartbeat"
                    if updated_task.get("pending_context_update")
                    else "next_begin"
                ),
            }

        return self._execute(
            episode_id,
            "context.override",
            actor,
            payload,
            handler,
            request_id=request_id,
            now=now,
        )

    def change(
        self,
        episode_id: str,
        *,
        actor: str,
        target_id: str,
        reason: str,
        kind: str = "scope_change",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        target_id = require_identifier(target_id, "target_id")
        if not reason.strip():
            raise DomainError("invalid_change", "change reason is required", "change_reason_explicit")
        now = self.clock()
        payload = {"target_id": target_id, "reason": reason.strip(), "kind": kind.strip()}

        def handler(tx: Transaction) -> dict[str, Any]:
            task, task_version = tx.get("task", target_id)
            artifact, artifact_version = tx.get("artifact", target_id)
            if task is None and artifact is None:
                raise DomainError(
                    "change_target_missing",
                    f"change target {target_id!r} is neither a task nor an artifact",
                    failed_invariant="change_target_exists",
                    allowed_next=("explain",),
                    http_status=404,
                )
            if artifact is not None:
                task_id = str(artifact.get("producer_task_id"))
                task, task_version = tx.require("task", task_id)
                target_kind = "artifact"
            else:
                task_id = target_id
                target_kind = "task"
            logical = {"task_id": task_id, "artifact_id": target_id if target_kind == "artifact" else None, **payload}
            approval_reversed = (
                kind.strip() == "human_approval_reversed"
                and task.get("status") == "approved"
            )
            change_id = "change_" + object_hash(logical)[:20]
            prior, _ = tx.get("change", change_id)
            if prior is not None:
                return {"duplicate_change": True, "change": prior, "task": task}
            change_state = {
                "change_id": change_id,
                "episode_id": episode_id,
                "task_id": task_id,
                "artifact_id": target_id if target_kind == "artifact" else None,
                "target_kind": target_kind,
                "kind": kind.strip(),
                "reason": reason.strip(),
                "status": "open",
                "requested_by": actor,
                "created_at": now,
            }
            tx.transition("change", change_id, "ChangeRecorded", logical, change_state, expected_version=0)
            if artifact is not None:
                updated_artifact = {**artifact, "status": "superseded", "superseded_by_change_id": change_id}
                tx.transition(
                    "artifact", target_id, "ArtifactSuperseded", {"change_id": change_id}, updated_artifact,
                    expected_version=artifact_version,
                )
            direct_artifact_ids = sorted(
                set((task.get("candidate") or {}).get("artifact_ids", []))
                | set(task.get("approved_artifact_ids", []))
            )
            for produced_artifact_id in direct_artifact_ids:
                if produced_artifact_id == target_id and artifact is not None:
                    continue
                produced, produced_version = tx.require(
                    "artifact", produced_artifact_id
                )
                tx.transition(
                    "artifact",
                    produced_artifact_id,
                    "ArtifactStaledByProducerChange",
                    {"change_id": change_id, "task_id": task_id},
                    {
                        **produced,
                        "status": "stale",
                        "stale_reason": "producer_change",
                        "change_id": change_id,
                    },
                    expected_version=produced_version,
                )
            updated_task = {
                **task,
                "status": "rework" if task.get("status") != "planned" else "planned",
                "scope_revision": int(task.get("scope_revision", 1)) + 1,
                "context_revision": int(task.get("context_revision", 1)) + 1,
                "active_capsule_hash": None,
                "pending_context_update": None,
                "candidate": None,
                "approved_artifact_ids": [],
                "blockers": [{"kind": "open_change", "change_id": change_id}],
                "updated_at": now,
            }
            if approval_reversed:
                prior_decision = task.get("human_decision")
                updated_task["human_decision_history"] = [
                    *task.get("human_decision_history", []),
                    *([prior_decision] if prior_decision else []),
                ]
                updated_task["human_decision"] = {
                    "actor": actor,
                    "verdict": "approval_revoked",
                    "note": reason.strip(),
                    "at": now,
                    "change_id": change_id,
                }
            tx.transition(
                "task",
                task_id,
                "TaskHumanApprovalReversed" if approval_reversed else "TaskScopeChanged",
                {
                    "change_id": change_id,
                    "reason": reason.strip(),
                    "previous_human_decision": task.get("human_decision"),
                },
                updated_task,
                expected_version=task_version,
            )
            lease_id = f"lease:{task_id}"
            lease, lease_version = tx.get("lease", lease_id)
            if lease and lease.get("status") == "active":
                tx.transition(
                    "lease", lease_id, "LeaseRevoked", {"change_id": change_id},
                    {**lease, "status": "revoked", "revoked_at": now, "revoke_reason": "scope_change"},
                    expected_version=lease_version,
                )
            all_tasks = {state["task_id"]: (state, version) for state, version in tx.list("task")}
            descendants: set[str] = set()
            frontier = [task_id]
            while frontier:
                upstream = frontier.pop()
                for candidate_id, (candidate, _) in all_tasks.items():
                    if upstream in candidate.get("dependencies", []) and candidate_id not in descendants:
                        descendants.add(candidate_id)
                        frontier.append(candidate_id)
            invalidated: list[str] = []
            for descendant_id in sorted(descendants):
                descendant, version = all_tasks[descendant_id]
                if descendant.get("status") in {"working", "candidate", "user_review_pending", "approved"}:
                    updated = {
                        **descendant,
                        "status": "blocked",
                        "active_capsule_hash": None,
                        "candidate": None,
                        "approved_artifact_ids": [],
                        "blockers": [
                            *descendant.get("blockers", []),
                            {"kind": "upstream_change", "change_id": change_id, "upstream_task_id": task_id},
                        ],
                        "updated_at": now,
                    }
                    tx.transition(
                        "task", descendant_id, "TaskInvalidatedByUpstreamChange",
                        {"change_id": change_id, "upstream_task_id": task_id}, updated,
                        expected_version=version,
                    )
                    descendant_artifact_ids = sorted(
                        set((descendant.get("candidate") or {}).get("artifact_ids", []))
                        | set(descendant.get("approved_artifact_ids", []))
                    )
                    for descendant_artifact_id in descendant_artifact_ids:
                        descendant_artifact, descendant_artifact_version = tx.require(
                            "artifact", descendant_artifact_id
                        )
                        tx.transition(
                            "artifact",
                            descendant_artifact_id,
                            "ArtifactStaledByUpstreamChange",
                            {
                                "change_id": change_id,
                                "upstream_task_id": task_id,
                                "consumer_task_id": descendant_id,
                            },
                            {
                                **descendant_artifact,
                                "status": "stale",
                                "stale_reason": "upstream_change",
                                "change_id": change_id,
                            },
                            expected_version=descendant_artifact_version,
                        )
                    descendant_lease_id = f"lease:{descendant_id}"
                    descendant_lease, descendant_lease_version = tx.get("lease", descendant_lease_id)
                    if descendant_lease and descendant_lease.get("status") == "active":
                        tx.transition(
                            "lease",
                            descendant_lease_id,
                            "LeaseRevoked",
                            {"change_id": change_id, "upstream_task_id": task_id},
                            {
                                **descendant_lease,
                                "status": "revoked",
                                "revoked_at": now,
                                "revoke_reason": "upstream_change",
                            },
                            expected_version=descendant_lease_version,
                        )
                    invalidated.append(descendant_id)
            return {
                "change": change_state,
                "task": updated_task,
                "approval_reversed": approval_reversed,
                "invalidated_tasks": invalidated,
            }

        return self._execute(episode_id, "change.record", actor, payload, handler, request_id=request_id, now=now)

    def gap(
        self,
        episode_id: str,
        task_id: str,
        *,
        actor: str,
        reason: str,
        kind: str = "missing_input",
        sources: list[dict[str, Any]] | None = None,
        confidence: str | None = None,
        requires_human: bool | None = None,
        conflict_key: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        task_id = require_identifier(task_id, "task_id")
        if not reason.strip():
            raise DomainError("invalid_gap", "gap reason is required", "gap_reason_explicit")
        now = self.clock()
        human_required = (
            kind.strip() == "contradictory_requirements"
            if requires_human is None
            else bool(requires_human)
        )
        payload = {
            "task_id": task_id,
            "reason": reason.strip(),
            "kind": kind.strip(),
            "sources": sources or [],
            "confidence": confidence,
            "requires_human": human_required,
            "conflict_key": conflict_key,
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            task, task_version = tx.require("task", task_id)
            if task.get("status") not in {"planned", "rework", "working", "blocked"}:
                raise DomainError(
                    "gap_not_valid_for_state",
                    "record a change or review decision instead of attaching a work gap to this state",
                    failed_invariant="gap_work_state",
                    allowed_next=("change", "review", "human-decide", "explain"),
                    details={"task_status": task.get("status")},
                )
            gap_id = "gap_" + object_hash(payload)[:20]
            prior, _ = tx.get("gap", gap_id)
            if prior is not None:
                return {"duplicate_gap": True, "gap": prior, "task": task}
            gap_state = {
                "gap_id": gap_id,
                "episode_id": episode_id,
                "task_id": task_id,
                "kind": kind.strip(),
                "reason": reason.strip(),
                "status": "open",
                "reported_by": actor,
                "sources": sources or [],
                "confidence": confidence,
                "requires_human": human_required,
                "conflict_key": conflict_key,
                "created_at": now,
            }
            tx.transition("gap", gap_id, "GapRecorded", payload, gap_state, expected_version=0)
            updated_task = {
                **task,
                "status": "blocked",
                "active_capsule_hash": None,
                "blockers": [*task.get("blockers", []), {"kind": "open_gap", "gap_id": gap_id}],
                "updated_at": now,
            }
            tx.transition(
                "task", task_id, "TaskBlockedByGap", {"gap_id": gap_id}, updated_task,
                expected_version=task_version,
            )
            lease_id = f"lease:{task_id}"
            lease, lease_version = tx.get("lease", lease_id)
            if lease and lease.get("status") == "active":
                tx.transition(
                    "lease", lease_id, "LeaseReleased", {"gap_id": gap_id},
                    {**lease, "status": "released", "released_at": now, "release_reason": "gap"},
                    expected_version=lease_version,
                )
            return {"gap": gap_state, "task": updated_task}

        return self._execute(episode_id, "gap.record", actor, payload, handler, request_id=request_id, now=now)

    def resolve_gap(
        self,
        episode_id: str,
        gap_id: str,
        *,
        actor: str,
        resolution: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        gap_id = require_identifier(gap_id, "gap_id")
        if not resolution.strip():
            raise DomainError(
                "gap_resolution_required",
                "resolving a gap requires an explicit Human decision",
                failed_invariant="gap_resolution_explicit",
            )
        now = self.clock()
        payload = {"gap_id": gap_id, "resolution": resolution.strip()}

        def handler(tx: Transaction) -> dict[str, Any]:
            gap, gap_version = tx.require("gap", gap_id)
            if gap.get("status") == "resolved":
                return {"already_resolved": True, "gap": gap}
            task, task_version = tx.require("task", str(gap.get("task_id")))
            updated_gap = {**gap, "status": "resolved", "resolution": resolution.strip(), "resolved_by": actor, "resolved_at": now}
            tx.transition("gap", gap_id, "GapResolved", payload, updated_gap, expected_version=gap_version)
            override_logical = {
                "episode_id": episode_id,
                "task_id": task["task_id"],
                "gap_id": gap_id,
                "resolution": resolution.strip(),
            }
            override_id = "ctx_" + object_hash(override_logical)[:20]
            override_state = {
                "episode_id": episode_id,
                "task_id": task["task_id"],
                "content_unit_id": task.get("content_unit_id"),
                "override_id": override_id,
                "instruction": (
                    f"Human 对缺口 {gap_id} 的裁决：{resolution.strip()} "
                    "后续制作与独立审查必须引用并遵守这项裁决。"
                ),
                "label": f"Human 裁决 · {gap_id}",
                "scope": "task",
                "assembly_mode": "append",
                "context_slot": f"gap-resolution:{gap_id}",
                "delivery_policy": "next_attempt",
                "precedence": 850,
                "source_gap_id": gap_id,
                "version": 1,
                "status": "active",
                "effective_attempt": int(task.get("attempt", 0)) + 1,
                "created_by": actor,
                "created_at": now,
            }
            existing_override, _ = tx.get("context_override", override_id)
            if existing_override is None:
                tx.transition(
                    "context_override",
                    override_id,
                    "ContextOverrideAddedFromGapResolution",
                    {
                        "gap_id": gap_id,
                        "override_id": override_id,
                        "delivery_policy": "next_attempt",
                    },
                    override_state,
                    expected_version=0,
                )
            else:
                override_state = existing_override
            open_other = [
                state for state, _ in tx.list("gap")
                if state.get("task_id") == task.get("task_id")
                and state.get("status") == "open"
                and state.get("gap_id") != gap_id
            ]
            blockers = [item for item in task.get("blockers", []) if item.get("gap_id") != gap_id]
            resolved_conflict_keys = list(task.get("resolved_contract_conflict_keys", []))
            if gap.get("conflict_key") and gap.get("conflict_key") not in resolved_conflict_keys:
                resolved_conflict_keys.append(str(gap["conflict_key"]))
            updated_task = {
                **task,
                "status": "blocked" if open_other else "rework",
                "blockers": blockers,
                "context_revision": int(task.get("context_revision", 1)) + 1,
                "context_override_ids": list(
                    dict.fromkeys([*task.get("context_override_ids", []), override_id])
                ),
                "resolved_contract_conflict_keys": resolved_conflict_keys,
                "updated_at": now,
            }
            tx.transition(
                "task",
                task["task_id"],
                "TaskGapResolved",
                {"gap_id": gap_id, "context_override_id": override_id},
                updated_task,
                expected_version=task_version,
            )
            return {
                "gap": updated_gap,
                "task": updated_task,
                "context_override": override_state,
                "delivery": "next_begin",
            }

        return self._execute(episode_id, "gap.resolve", actor, payload, handler, request_id=request_id, now=now)

    def replan(
        self,
        episode_id: str,
        task_id: str,
        *,
        actor: str,
        reason: str,
        budget_patch: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        task_id = require_identifier(task_id, "task_id")
        if not reason.strip():
            raise DomainError("invalid_replan", "replan reason is required", "replan_reason_explicit")
        allowed_budget_fields = set(DEFAULT_TASK_BUDGET)
        patch = dict(budget_patch or {})
        unknown = sorted(set(patch) - allowed_budget_fields)
        if unknown:
            raise DomainError(
                "invalid_budget_patch",
                "replan contains unsupported budget fields",
                failed_invariant="budget_patch_allowlist",
                details={"unknown_fields": unknown},
            )
        now = self.clock()
        payload = {"task_id": task_id, "reason": reason.strip(), "budget_patch": patch}

        def handler(tx: Transaction) -> dict[str, Any]:
            task, task_version = tx.require("task", task_id)
            lease, _ = tx.get("lease", f"lease:{task_id}")
            if lease_is_live(lease, now):
                raise DomainError(
                    "replan_while_leased",
                    "replan requires the active worker lease to be released first",
                    failed_invariant="replan_outside_active_work",
                    allowed_next=("gap", "change", "next", "explain"),
                    recovery="Release the live lease through a justified gap/change, or wait for expiry and call next before replanning.",
                )
            previous_budget = _normalized_budget(task.get("budget"))
            updated_budget = _normalized_budget({**previous_budget, **patch})
            open_gaps = [
                state for state, _ in tx.list("gap")
                if state.get("task_id") == task_id and state.get("status") == "open"
            ]
            retained_blockers = [
                blocker for blocker in task.get("blockers", [])
                if blocker.get("kind") not in {
                    "active_time_budget_exhausted",
                    "stagnation_threshold",
                    "token_budget_exhausted",
                    "recovered_interruption",
                }
            ]
            next_status = "blocked" if open_gaps else "rework"
            replan_id = "replan_" + object_hash({"request_id": tx.request_id, **payload})[:20]
            replan_state = {
                "replan_id": replan_id,
                "episode_id": episode_id,
                "task_id": task_id,
                "reason": reason.strip(),
                "actor": actor,
                "previous_budget": previous_budget,
                "updated_budget": updated_budget,
                "created_at": now,
            }
            tx.transition("replan", replan_id, "TaskReplanAuthorized", payload, replan_state, expected_version=0)
            updated_task = {
                **task,
                "status": next_status,
                "budget": updated_budget,
                "budget_revision": int(task.get("budget_revision", 1)) + 1,
                "heartbeats_without_progress": 0,
                "checkpoint_due": False,
                "supervision_stop": None,
                "blockers": retained_blockers,
                "updated_at": now,
            }
            tx.transition(
                "task",
                task_id,
                "TaskReplanned",
                {"replan_id": replan_id, "reason": reason.strip()},
                updated_task,
                expected_version=task_version,
            )
            return {"task": updated_task, "replan": replan_state}

        return self._execute(episode_id, "task.replan", actor, payload, handler, request_id=request_id, now=now)

    def annotate(
        self,
        episode_id: str,
        *,
        actor: str,
        target_id: str,
        body: str,
        severity: str = "note",
        location: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        now = self.clock()
        descriptor = self._normalize_annotation_descriptor(
            target_id=target_id,
            body=body,
            severity=severity,
            location=location,
        )

        def handler(tx: Transaction) -> dict[str, Any]:
            annotation, duplicate = self._record_annotation(
                tx,
                episode_id=episode_id,
                actor=actor,
                descriptor=descriptor,
                now=now,
            )
            return {"duplicate_annotation": duplicate, "annotation": annotation}

        return self._execute(
            episode_id,
            "annotation.add",
            actor,
            descriptor,
            handler,
            request_id=request_id,
            now=now,
        )

    def annotate_batch(
        self,
        episode_id: str,
        *,
        actor: str,
        annotations: list[dict[str, Any]],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(annotations, list) or not 1 <= len(annotations) <= 200:
            raise DomainError(
                "invalid_annotation_batch",
                "annotation batch must contain between 1 and 200 items",
                failed_invariant="annotation_batch_bounded",
                http_status=400,
            )
        normalized = [
            self._normalize_annotation_descriptor(
                target_id=str(item.get("target_id", "")),
                body=str(item.get("body", "")),
                severity=str(item.get("severity", "note")),
                location=item.get("location"),
            )
            for item in annotations
        ]
        now = self.clock()
        payload = {"annotations": normalized}

        def handler(tx: Transaction) -> dict[str, Any]:
            created: list[dict[str, Any]] = []
            duplicate_count = 0
            for descriptor in normalized:
                annotation, duplicate = self._record_annotation(
                    tx,
                    episode_id=episode_id,
                    actor=actor,
                    descriptor=descriptor,
                    now=now,
                )
                created.append(annotation)
                duplicate_count += int(duplicate)
            return {
                "annotations": created,
                "created_count": len(created) - duplicate_count,
                "duplicate_count": duplicate_count,
            }

        return self._execute(
            episode_id,
            "annotation.batch",
            actor,
            payload,
            handler,
            request_id=request_id,
            now=now,
        )

    @staticmethod
    def _normalize_annotation_descriptor(
        *,
        target_id: str,
        body: str,
        severity: str,
        location: dict[str, Any] | None,
    ) -> dict[str, Any]:
        normalized_target = require_identifier(target_id, "target_id")
        normalized_body = body.strip()
        normalized_severity = severity.strip() or "note"
        if not normalized_body:
            raise DomainError(
                "invalid_annotation",
                "annotation body is required",
                failed_invariant="annotation_body_required",
                http_status=400,
            )
        if normalized_severity not in {"note", "warning", "blocker"}:
            raise DomainError(
                "invalid_annotation",
                "annotation severity must be note, warning, or blocker",
                failed_invariant="annotation_severity_known",
                http_status=400,
            )
        normalized_location: dict[str, Any] | None = None
        if location is not None:
            if not isinstance(location, dict):
                raise DomainError(
                    "invalid_annotation_location",
                    "annotation location must be an object",
                    failed_invariant="annotation_location_shape",
                    http_status=400,
                )
            raw_seconds = location.get("time_seconds")
            try:
                seconds = float(raw_seconds)
            except (TypeError, ValueError) as exc:
                raise DomainError(
                    "invalid_annotation_location",
                    "media annotation requires a numeric time_seconds",
                    failed_invariant="annotation_time_numeric",
                    http_status=400,
                ) from exc
            if not math.isfinite(seconds) or seconds < 0:
                raise DomainError(
                    "invalid_annotation_location",
                    "media annotation time_seconds must be finite and non-negative",
                    failed_invariant="annotation_time_bounded",
                    http_status=400,
                )
            normalized_location = {
                "kind": "media",
                "artifact_id": require_identifier(
                    str(location.get("artifact_id") or normalized_target),
                    "artifact_id",
                ),
                "time_seconds": round(seconds, 3),
                "timecode": str(location.get("timecode", "")).strip(),
            }
            position = location.get("position")
            if position is not None:
                if not isinstance(position, dict):
                    raise DomainError(
                        "invalid_annotation_location",
                        "media position must contain normalized x and y coordinates",
                        failed_invariant="annotation_position_shape",
                        http_status=400,
                    )
                try:
                    x = float(position.get("x"))
                    y = float(position.get("y"))
                except (TypeError, ValueError) as exc:
                    raise DomainError(
                        "invalid_annotation_location",
                        "media position x and y must be numeric",
                        failed_invariant="annotation_position_numeric",
                        http_status=400,
                    ) from exc
                if not all(math.isfinite(value) and 0 <= value <= 1 for value in (x, y)):
                    raise DomainError(
                        "invalid_annotation_location",
                        "media position x and y must be within 0 and 1",
                        failed_invariant="annotation_position_normalized",
                        http_status=400,
                    )
                normalized_location["position"] = {"x": round(x, 5), "y": round(y, 5)}
        return {
            "target_id": normalized_target,
            "body": normalized_body,
            "severity": normalized_severity,
            "location": normalized_location,
        }

    @staticmethod
    def _record_annotation(
        tx: Transaction,
        *,
        episode_id: str,
        actor: str,
        descriptor: dict[str, Any],
        now: str,
    ) -> tuple[dict[str, Any], bool]:
        target_id = str(descriptor["target_id"])
        found = None
        target_state: dict[str, Any] | None = None
        for kind in ("task", "artifact", "scene", "wave", "episode"):
            candidate_state, _ = tx.get(kind, target_id)
            if candidate_state is not None:
                found = kind
                target_state = candidate_state
                break
        if found is None:
            raise DomainError(
                "annotation_target_missing",
                f"annotation target {target_id!r} does not exist",
                failed_invariant="annotation_target_exists",
                allowed_next=("explain",),
                http_status=404,
            )
        location = descriptor.get("location")
        if location and (found != "artifact" or location.get("artifact_id") != target_id):
            raise DomainError(
                "invalid_annotation_location",
                "media annotation must target the same registered artifact it locates",
                failed_invariant="annotation_media_target_exact",
                http_status=400,
            )
        annotation_id = "note_" + object_hash({**descriptor, "actor": actor})[:20]
        prior, _ = tx.get("annotation", annotation_id)
        if prior is not None:
            return prior, True
        producer_task_id = None
        if found == "task":
            producer_task_id = target_id
        elif found == "artifact":
            producer_task_id = str((target_state or {}).get("producer_task_id") or "") or None
        producer_task = None
        producer_task_version = 0
        if producer_task_id:
            producer_task, producer_task_version = tx.get("task", producer_task_id)
        producer_status = str((producer_task or {}).get("status") or "")
        if producer_status == "working":
            delivery_policy = "attention_boundary"
            delivery_state = "pending_next_heartbeat"
        elif producer_status in {"candidate", "user_review_pending", "approved"}:
            delivery_policy = "after_explicit_reopen"
            delivery_state = "awaiting_explicit_reopen"
        else:
            delivery_policy = "on_begin"
            delivery_state = "queued_next_begin"
        annotation = {
            "annotation_id": annotation_id,
            "episode_id": episode_id,
            "target_id": target_id,
            "target_kind": found,
            "body": descriptor["body"],
            "severity": descriptor["severity"],
            "location": location,
            "actor": actor,
            "status": "open",
            "producer_task_id": producer_task_id,
            "delivery_policy": delivery_policy,
            "delivery_state": delivery_state,
            "created_at": now,
        }
        tx.transition(
            "annotation",
            annotation_id,
            "AnnotationAdded",
            {
                **descriptor,
                "producer_task_id": producer_task_id,
                "producer_task_status": producer_status or None,
                "delivery_policy": delivery_policy,
                "delivery_state": delivery_state,
                "interrupt_active_lease": False,
            },
            annotation,
            expected_version=0,
        )
        if producer_task is not None and producer_status == "working":
            pending = deepcopy(producer_task.get("pending_context_update") or {})
            annotation_ids = list(pending.get("annotation_ids") or [])
            if annotation_id not in annotation_ids:
                annotation_ids.append(annotation_id)
            context_revision = int(producer_task.get("context_revision", 1)) + 1
            pending.update(
                {
                    "delivery_policy": "attention_boundary",
                    "annotation_ids": annotation_ids,
                    "context_revision": context_revision,
                }
            )
            tx.transition(
                "task",
                producer_task_id,
                "TaskAnnotationAttentionScheduled",
                {
                    "annotation_id": annotation_id,
                    "delivery_policy": "attention_boundary",
                    "interrupt_active_lease": False,
                },
                {
                    **producer_task,
                    "context_revision": context_revision,
                    "pending_context_update": pending,
                    "updated_at": now,
                },
                expected_version=producer_task_version,
            )
        return annotation, False

    def observe(
        self,
        episode_id: str,
        *,
        actor: str,
        category: str,
        summary: str,
        task_id: str | None = None,
        severity: str = "medium",
        expectation: str = "",
        actual: str = "",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if not summary.strip():
            raise DomainError("invalid_observation", "observation summary is required", "observation_summary_explicit")
        if task_id:
            task_id = require_identifier(task_id, "task_id")
        now = self.clock()
        payload = {
            "category": category.strip(),
            "summary": summary.strip(),
            "task_id": task_id,
            "severity": severity.strip(),
            "expectation": expectation.strip(),
            "actual": actual.strip(),
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            tx.require("episode", episode_id)
            if task_id:
                tx.require("task", task_id)
            observation_id = "obs_" + object_hash({"request_id": tx.request_id, **payload})[:20]
            state = {
                "observation_id": observation_id,
                "episode_id": episode_id,
                "actor": actor,
                **payload,
                "status": "open",
                "created_at": now,
            }
            tx.transition("observation", observation_id, "EvaluationObservationRecorded", payload, state, expected_version=0)
            return {"observation": state}

        return self._execute(episode_id, "observation.record", actor, payload, handler, request_id=request_id, now=now)

    def export(self, episode_id: str, output_dir: Path) -> dict[str, Any]:
        return export_episode(self.data_root.episode_store(episode_id), output_dir)

    def explain(
        self,
        episode_id: str,
        target_id: str | None = None,
        *,
        actor: str | None = None,
    ) -> dict[str, Any]:
        store = self.data_root.episode_store(episode_id)
        snapshot = self._snapshot(store)
        now = self.clock()
        if target_id is None:
            return {"ok": True, "status": "read_only", "overview": self.overview(episode_id)}
        target_id = require_identifier(target_id, "target_id")
        found_kind: str | None = None
        state: dict[str, Any] | None = None
        version = 0
        for kind in (
            "task",
            "artifact",
            "gate",
            "change",
            "route",
            "return_ticket",
            "gap",
            "lease",
            "annotation",
            "content_unit",
            "deliverable",
            "scene",
            "wave",
            "episode",
        ):
            state, version = store.get(kind, target_id)
            if state is not None:
                found_kind = kind
                break
        if state is None or found_kind is None:
            return DomainError(
                "not_found",
                f"no state object named {target_id!r}",
                failed_invariant="explain_target_exists",
                allowed_next=("overview",),
                http_status=404,
            ).as_result()
        tasks = {item["task_id"]: item for item, _ in snapshot["tasks"]}
        gaps = [item for item, _ in snapshot["gaps"]]
        gates = [item for item, _ in snapshot["gates"]]
        leases = {item["task_id"]: item for item, _ in snapshot["leases"]}
        causal: dict[str, Any] = {}
        allowed_next: list[str] = []
        if found_kind == "task":
            blockers = task_blockers(state, tasks, gaps, leases.get(target_id), now)
            causal = {
                "blockers": blockers,
                "dependencies": [tasks.get(item) for item in state.get("dependencies", [])],
                "lease": leases.get(target_id),
                "gaps": [item for item in gaps if item.get("task_id") == target_id],
                "changes": [item for item, _ in snapshot["changes"] if item.get("task_id") == target_id],
                "routes": [
                    item
                    for item, _ in snapshot["routes"]
                    if target_id
                    in {
                        item.get("replaced_task_id"),
                        item.get("replacement_task_id"),
                    }
                    or target_id in item.get("rewired_task_ids", [])
                    or target_id in item.get("invalidated_task_ids", [])
                ],
                "return_tickets": [
                    item
                    for item, _ in snapshot["returns"]
                    if item.get("task_id") == target_id
                ],
                "artifacts": [
                    item for item, _ in snapshot["artifacts"]
                    if item.get("producer_task_id") == target_id
                ],
                "gates": [item for item in gates if item.get("task_id") == target_id],
                "annotations": _relevant_annotations_for_task(
                    state,
                    [item for item, _ in snapshot["annotations"]],
                    [item for item, _ in snapshot["artifacts"]],
                ),
                "observations": [
                    item
                    for item, _ in snapshot["observations"]
                    if item.get("task_id") == target_id
                ],
            }
            status = state.get("status")
            if status in {"planned", "rework"} and not blockers:
                allowed_next = ["begin"]
            elif status == "working":
                lease = leases.get(target_id)
                allowed_next = (
                    ["heartbeat", "submit", "change", "gap"]
                    if actor is not None and lease and lease.get("owner") == actor
                    else ["next", "explain"]
                )
            elif status == "candidate":
                allowed_next = (
                    ["gate-run"]
                    if _missing_validator_receipts(state, gates)
                    else ["review-context"]
                )
            elif status == "user_review_pending":
                allowed_next = ["human-decide"]
            elif status == "blocked":
                open_task_gaps = [
                    item
                    for item in gaps
                    if item.get("task_id") == target_id
                    and item.get("status") == "open"
                ]
                allowed_next = ["next", "explain", "change"]
                if open_task_gaps:
                    allowed_next.insert(0, "gap-resolve")
        with store.reader() as connection:
            rows = connection.execute(
                """
                SELECT seq, event_id, event_type, request_id, actor, occurred_at,
                       aggregate_version, payload_json
                FROM events
                WHERE aggregate_type=? AND aggregate_id=?
                ORDER BY seq DESC LIMIT 30
                """,
                (found_kind, target_id),
            ).fetchall()
            history = [
                {
                    "seq": row["seq"], "event_id": row["event_id"], "event_type": row["event_type"],
                    "request_id": row["request_id"], "actor": row["actor"], "occurred_at": row["occurred_at"],
                    "aggregate_version": row["aggregate_version"], "payload": __import__("json").loads(row["payload_json"]),
                }
                for row in rows
            ]
        return {
            "ok": True,
            "status": "read_only",
            "episode_id": episode_id,
            "target_kind": found_kind,
            "target_id": target_id,
            "actor": actor,
            "version": version,
            "state": state,
            "causal": causal,
            "allowed_next": allowed_next,
            "history": history,
        }

    def _scope_projection(
        self,
        *,
        episode: dict[str, Any],
        content_units: list[dict[str, Any]],
        deliverables: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        leases: dict[str, dict[str, Any]],
        gaps: list[dict[str, Any]],
        now: str,
    ) -> dict[str, Any]:
        task_by_id = {task["task_id"]: task for task in tasks}

        def summaries(
            nodes: list[dict[str, Any]],
            *,
            id_key: str,
            parent_key: str,
            task_key: str,
        ) -> list[dict[str, Any]]:
            children: dict[str | None, list[str]] = {}
            node_by_id = {str(node[id_key]): node for node in nodes}
            for node in nodes:
                parent = node.get(parent_key)
                children.setdefault(None if parent is None else str(parent), []).append(
                    str(node[id_key])
                )

            descendant_cache: dict[str, set[str]] = {}

            def descendants(node_id: str) -> set[str]:
                if node_id in descendant_cache:
                    return descendant_cache[node_id]
                found = {node_id}
                for child_id in children.get(node_id, []):
                    found.update(descendants(child_id))
                descendant_cache[node_id] = found
                return found

            result: list[dict[str, Any]] = []
            for node_id, node in node_by_id.items():
                covered = descendants(node_id)
                scoped_tasks = [
                    task
                    for task in tasks
                    if task.get(task_key) in covered
                ]
                current = [
                    task
                    for task in scoped_tasks
                    if task.get("status") not in {"cancelled", "superseded"}
                ]
                counts: dict[str, int] = {}
                for task in current:
                    status = str(task.get("status", "unknown"))
                    counts[status] = counts.get(status, 0) + 1
                approved = sum(
                    1 for task in current if task.get("status") == "approved"
                )
                active_agents = sorted(
                    {
                        str(leases[task["task_id"]].get("owner"))
                        for task in current
                        if task["task_id"] in leases
                        and lease_is_live(leases[task["task_id"]], now)
                    }
                )
                result.append(
                    {
                        **node,
                        "task_ids": sorted(task["task_id"] for task in scoped_tasks),
                        "direct_task_ids": sorted(
                            task["task_id"]
                            for task in scoped_tasks
                            if task.get(task_key) == node_id
                        ),
                        "derived": {
                            "phase": _scope_phase(scoped_tasks),
                            "counts": counts,
                            "approved": approved,
                            "total": len(current),
                            "progress": approved / len(current) if current else 0.0,
                            "ready": sum(
                                1
                                for task in current
                                if task.get("derived", {}).get("runnable")
                            ),
                            "active_agents": active_agents,
                        },
                    }
                )
            return sorted(
                result,
                key=lambda node: (
                    int(node.get("depth", 0)),
                    int(node.get("order", 0)),
                    str(node[id_key]),
                ),
            )

        def cross_edges(task_key: str) -> list[dict[str, Any]]:
            edge_map: dict[tuple[str, str], dict[str, Any]] = {}
            for consumer in tasks:
                target_scope = consumer.get(task_key)
                if not target_scope:
                    continue
                for dependency_id in consumer.get("dependencies", []):
                    producer = task_by_id.get(dependency_id)
                    if not producer:
                        continue
                    source_scope = producer.get(task_key)
                    if not source_scope or source_scope == target_scope:
                        continue
                    key = (str(source_scope), str(target_scope))
                    edge = edge_map.setdefault(
                        key,
                        {
                            "source_id": str(source_scope),
                            "target_id": str(target_scope),
                            "task_edges": [],
                            "artifact_roles": set(),
                        },
                    )
                    edge["task_edges"].append(
                        {
                            "producer_task_id": dependency_id,
                            "consumer_task_id": consumer["task_id"],
                        }
                    )
                    edge["artifact_roles"].update(
                        producer.get("output_contract", {}).get(
                            "required_artifact_roles", []
                        )
                    )
            return [
                {
                    **edge,
                    "task_edges": sorted(
                        edge["task_edges"],
                        key=lambda item: (
                            item["producer_task_id"],
                            item["consumer_task_id"],
                        ),
                    ),
                    "artifact_roles": sorted(edge["artifact_roles"]),
                }
                for _, edge in sorted(edge_map.items())
            ]

        cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for task in tasks:
            content_id = str(task.get("content_unit_id") or "unassigned")
            deliverable_id = str(task.get("deliverable_id") or "unassigned")
            cells.setdefault((content_id, deliverable_id), []).append(task)
        return {
            "schema": episode.get("scope_model", {}).get(
                "schema", "multi-scale-dual-axis-v1"
            ),
            "episode_phase": _derived_episode_phase(episode, tasks, gaps),
            "content_units": summaries(
                content_units,
                id_key="unit_id",
                parent_key="parent_unit_id",
                task_key="content_unit_id",
            ),
            "deliverables": summaries(
                deliverables,
                id_key="deliverable_id",
                parent_key="parent_deliverable_id",
                task_key="deliverable_id",
            ),
            "content_edges": cross_edges("content_unit_id"),
            "deliverable_edges": cross_edges("deliverable_id"),
            "cells": [
                {
                    "content_unit_id": content_id,
                    "deliverable_id": deliverable_id,
                    "task_ids": sorted(task["task_id"] for task in cell_tasks),
                    "phase": _scope_phase(cell_tasks),
                }
                for (content_id, deliverable_id), cell_tasks in sorted(cells.items())
            ],
        }

    def overview(self, episode_id: str) -> dict[str, Any]:
        store = self.data_root.episode_store(episode_id)
        snapshot = self._snapshot(store)
        integrity = store.verify_integrity()
        waves = [state for state, _ in snapshot["waves"]]
        scenes = [state for state, _ in snapshot["scenes"]]
        raw_tasks = [state for state, _ in snapshot["tasks"]]
        content_units = [state for state, _ in snapshot["content_units"]]
        deliverables = [state for state, _ in snapshot["deliverables"]]
        task_by_id = {task["task_id"]: task for task in raw_tasks}
        lease_by_task = {state["task_id"]: state for state, _ in snapshot["leases"]}
        gap_states = [state for state, _ in snapshot["gaps"]]
        gate_states = [state for state, _ in snapshot["gates"]]
        now = self.clock()
        tasks: list[dict[str, Any]] = []
        for task in raw_tasks:
            derived_blockers = task_blockers(
                task,
                task_by_id,
                gap_states,
                lease_by_task.get(task["task_id"]),
                now,
            )
            runnable = task.get("status") in {"planned", "rework"} and not derived_blockers
            if runnable:
                effective_state = "ready"
            elif task.get("status") in {"planned", "rework"}:
                effective_state = "waiting"
            else:
                effective_state = str(task.get("status", "unknown"))
            tasks.append(
                {
                    **task,
                    "work_key": _effective_work_key(task),
                    "derived": {
                        "runnable": runnable,
                        "effective_state": effective_state,
                        "blockers": derived_blockers,
                        "missing_validators": (
                            _missing_validator_receipts(task, gate_states)
                            if task.get("status") == "candidate"
                            else []
                        ),
                    },
                }
            )
        hierarchy: list[dict[str, Any]] = []
        wave_ids = {item["wave_id"] for item in waves}
        if any(task.get("wave_id") is None for task in tasks):
            waves.append({"wave_id": "unassigned", "title": "Unassigned", "order": 10_000, "status": "virtual"})
            wave_ids.add("unassigned")
        for wave in sorted(waves, key=lambda item: (int(item.get("order", 0)), item["wave_id"])):
            wave_id = wave["wave_id"]
            wave_scenes = [item for item in scenes if item.get("wave_id") == wave_id]
            scene_nodes: list[dict[str, Any]] = []
            if any((task.get("wave_id") or "unassigned") == wave_id and task.get("scene_id") is None for task in tasks):
                wave_scenes.append({"scene_id": f"{wave_id}:unassigned", "wave_id": wave_id, "title": "Wave tasks", "order": -1, "status": "virtual"})
            for scene in sorted(wave_scenes, key=lambda item: (int(item.get("order", 0)), item["scene_id"])):
                scene_id = scene["scene_id"]
                scene_tasks = [
                    task for task in tasks
                    if (task.get("wave_id") or "unassigned") == wave_id
                    and (task.get("scene_id") == scene_id or (scene_id.endswith(":unassigned") and task.get("scene_id") is None))
                ]
                scene_nodes.append({**scene, "tasks": sorted(scene_tasks, key=lambda item: scheduling_key(item))})
            hierarchy.append({**wave, "scenes": scene_nodes})
        counts: dict[str, int] = {}
        effective_counts: dict[str, int] = {}
        for task in tasks:
            counts[str(task.get("status", "unknown"))] = counts.get(str(task.get("status", "unknown")), 0) + 1
            effective = str(task.get("derived", {}).get("effective_state", "unknown"))
            effective_counts[effective] = effective_counts.get(effective, 0) + 1
        annotations = [state for state, _ in snapshot["annotations"]]
        open_gaps = [state for state, _ in snapshot["gaps"] if state.get("status") == "open"]
        macro_budget = _episode_budget_state(snapshot["episode"], raw_tasks)
        workflow_attention = bool(open_gaps) or any(
            state.get("status") != "resolved" for state, _ in snapshot["changes"]
        ) or macro_budget["soft_limit_reached"]
        with store.reader() as connection:
            artifact_edges = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT upstream_artifact_id, downstream_artifact_id,
                           relation, task_id, created_seq
                    FROM artifact_edges
                    ORDER BY created_seq, upstream_artifact_id,
                             downstream_artifact_id
                    """
                ).fetchall()
            ]
        scope_projection = self._scope_projection(
            episode=snapshot["episode"],
            content_units=content_units,
            deliverables=deliverables,
            tasks=tasks,
            leases=lease_by_task,
            gaps=gap_states,
            now=now,
        )
        agent_states = [state for state, _ in snapshot["agents"]]
        agents = []
        for agent in agent_states:
            probe = self.agent_probe(episode_id, str(agent["agent_id"]))
            agents.append(
                {
                    **agent,
                    "derived": {
                        "classification": probe.get("classification"),
                        "is_idle": probe.get("is_idle"),
                        "idle_legal": probe.get("idle_legal"),
                        "productive": probe.get("productive"),
                        "reason_codes": probe.get("reason_codes", []),
                        "next": probe.get("next"),
                        "evidence": probe.get("evidence", {}),
                    },
                }
            )
        agent_attention = any(
            item.get("derived", {}).get("classification")
            in {
                "idle_illegal",
                "working_nonproductive_risk",
                "fake_busy_duplicate_work",
                "offline_unknown",
            }
            for item in agents
        )
        return {
            "episode": snapshot["episode"],
            "dispatch_policy": _dispatch_policy(snapshot["episode"]),
            "health": "healthy" if integrity["ok"] and not workflow_attention and not agent_attention else "attention" if integrity["ok"] else "degraded",
            "integrity": integrity,
            "macro_budget": macro_budget,
            "counts": counts,
            "effective_counts": effective_counts,
            "hierarchy": hierarchy,
            "scope": scope_projection,
            "content_units": content_units,
            "deliverables": deliverables,
            "tasks": tasks,
            "agents": agents,
            "dispatch_reservations": [
                state for state, _ in snapshot["dispatch_reservations"]
            ],
            "leases": [state for state, _ in snapshot["leases"]],
            "artifacts": [state for state, _ in snapshot["artifacts"]],
            "artifact_edges": artifact_edges,
            "gates": gate_states,
            "changes": [state for state, _ in snapshot["changes"]],
            "context_overrides": [
                state for state, _ in snapshot["context_overrides"]
            ],
            "routes": [state for state, _ in snapshot["routes"]],
            "returns": [state for state, _ in snapshot["returns"]],
            "gaps": [state for state, _ in snapshot["gaps"]],
            "annotations": annotations,
            "observations": [
                state for state, _ in snapshot["observations"]
            ],
            "cursor": integrity["cursor"],
        }

    def scan(self, episode_id: str, *, deep: bool = False) -> dict[str, Any]:
        store = self.data_root.episode_store(episode_id)
        result = scan_episode(store, self.repo_root, now=self.clock(), deep=deep)
        proposals = {
            "idle_illegal": "dispatch_system_ranked_next_action",
            "working_nonproductive_risk": "checkpoint_reflect_or_replan",
            "fake_busy_duplicate_work": "stop_duplicate_and_reconcile_work_key",
            "offline_unknown": "probe_agent_health_before_replacement",
        }
        for agent, _ in store.list("agent"):
            probe = self.agent_probe(episode_id, str(agent["agent_id"]))
            classification = str(probe.get("classification"))
            if classification not in proposals:
                continue
            facts = {
                "classification": classification,
                "reason_codes": probe.get("reason_codes", []),
                "next_action": (probe.get("next") or {}).get("action"),
                "next_task_id": (probe.get("next") or {}).get("task", {}).get("task_id"),
                "evidence": probe.get("evidence", {}),
            }
            result["anomalies"].append(
                {
                    "anomaly_id": "anomaly_" + object_hash(
                        {
                            "kind": classification,
                            "subject_id": agent["agent_id"],
                            "facts": facts,
                        }
                    )[:20],
                    "kind": classification,
                    "subject_id": agent["agent_id"],
                    "severity": (
                        "high"
                        if classification == "fake_busy_duplicate_work"
                        else "medium"
                    ),
                    "repairable": False,
                    "proposed_action": proposals[classification],
                    "facts": facts,
                }
            )
        result["anomalies"].sort(
            key=lambda item: (str(item.get("kind")), str(item.get("subject_id")))
        )
        result["clean"] = not result["anomalies"]
        result["status"] = "healthy" if result["clean"] else "attention"
        result["repairable_count"] = sum(
            1 for item in result["anomalies"] if item.get("repairable")
        )
        result["manual_count"] = sum(
            1 for item in result["anomalies"] if not item.get("repairable")
        )
        return result

    def recover(
        self,
        episode_id: str,
        *,
        actor: str,
        apply: bool = False,
        deep: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        store = self.data_root.episode_store(episode_id)
        plan = scan_episode(store, self.repo_root, now=self.clock(), deep=deep)
        if not apply:
            return {
                **plan,
                "status": "dry_run",
                "planned_repairs": [
                    {
                        "anomaly_id": item["anomaly_id"],
                        "kind": item["kind"],
                        "subject_id": item["subject_id"],
                        "proposed_action": item["proposed_action"],
                    }
                    for item in plan["anomalies"]
                    if item["repairable"]
                ],
                "applied": [],
            }
        projection_kinds = {"projection_drift", "missing_projection", "orphan_projection"}
        projection_anomalies = [item for item in plan["anomalies"] if item["kind"] in projection_kinds]
        hard_integrity = [
            item for item in plan["anomalies"]
            if item["kind"].startswith("event_") or item["kind"] == "sqlite_integrity"
        ]
        if hard_integrity:
            return DomainError(
                "unsafe_recovery",
                "automatic recovery stopped because the event log itself is not trusted",
                failed_invariant="recover_only_from_trusted_event_log",
                allowed_next=("scan", "export"),
                recovery="Preserve/export evidence, then restore a verified backup or perform manual event-log forensics outside automatic recovery.",
                details={"anomalies": hard_integrity},
            ).as_result()
        projection_result = None
        if projection_anomalies:
            projection_result = store.rebuild_projections(apply=True)
            plan = scan_episode(store, self.repo_root, now=self.clock(), deep=deep)
        repairable = [
            item for item in plan["anomalies"]
            if item["repairable"] and item["kind"] not in projection_kinds
        ]
        now = self.clock()
        payload = {
            "deep": deep,
            "anomaly_ids": [item["anomaly_id"] for item in repairable],
            "scan_cursor": plan["cursor"],
        }

        def handler(tx: Transaction) -> dict[str, Any]:
            applied: list[dict[str, Any]] = []
            for anomaly in repairable:
                kind = anomaly["kind"]
                subject_id = anomaly["subject_id"]
                if kind in {"expired_lease", "working_without_lease"}:
                    task, task_version = tx.require("task", subject_id)
                    if task.get("status") == "working":
                        updated_task = {
                            **task,
                            "status": "rework",
                            "active_capsule_hash": None,
                            "blockers": [
                                *task.get("blockers", []),
                                {"kind": "recovered_interruption", "anomaly_id": anomaly["anomaly_id"]},
                            ],
                            "updated_at": now,
                        }
                        tx.transition(
                            "task", subject_id, "TaskRecoveredFromInterruptedWork",
                            {"anomaly_id": anomaly["anomaly_id"]}, updated_task,
                            expected_version=task_version,
                        )
                    lease_id = f"lease:{subject_id}"
                    lease, lease_version = tx.get("lease", lease_id)
                    if lease and lease.get("status") == "active":
                        tx.transition(
                            "lease", lease_id, "LeaseExpired",
                            {"anomaly_id": anomaly["anomaly_id"]},
                            {**lease, "status": "expired", "expired_at": now},
                            expected_version=lease_version,
                        )
                elif kind == "orphan_live_lease":
                    lease_id = f"lease:{subject_id}"
                    lease, lease_version = tx.require("lease", lease_id)
                    if lease.get("status") == "active":
                        tx.transition(
                            "lease", lease_id, "LeaseReleasedByRecovery",
                            {"anomaly_id": anomaly["anomaly_id"]},
                            {**lease, "status": "released", "released_at": now, "release_reason": "recovery"},
                            expected_version=lease_version,
                        )
                elif kind == "open_gap_not_blocking":
                    task, task_version = tx.require("task", subject_id)
                    updated = {
                        **task,
                        "status": "blocked",
                        "active_capsule_hash": None,
                        "blockers": [
                            *task.get("blockers", []),
                            {"kind": "recovered_open_gap", "gap_ids": anomaly["facts"].get("gap_ids", [])},
                        ],
                        "updated_at": now,
                    }
                    tx.transition(
                        "task", subject_id, "TaskBlockedByRecovery",
                        {"anomaly_id": anomaly["anomaly_id"]}, updated,
                        expected_version=task_version,
                    )
                elif kind == "resolved_upstream_invalidation":
                    released_tasks: list[str] = []
                    for upstream_task_id in anomaly["facts"].get(
                        "approved_upstream_task_ids", []
                    ):
                        released_tasks.extend(
                            self._release_descendants_after_upstream_reapproval(
                                tx, str(upstream_task_id), now
                            )
                        )
                    anomaly["released_task_ids"] = sorted(set(released_tasks))
                elif kind == "historical_artifact_false_block":
                    task, task_version = tx.require("task", subject_id)
                    obsolete = {
                        (
                            str(blocker.get("kind", "")),
                            str(blocker.get("artifact_id", "")),
                            str(blocker.get("anomaly_id", "")),
                        )
                        for blocker in anomaly["facts"].get("obsolete_blockers", [])
                    }
                    retained_blockers = [
                        blocker
                        for blocker in task.get("blockers", [])
                        if (
                            str(blocker.get("kind", "")),
                            str(blocker.get("artifact_id", "")),
                            str(blocker.get("anomaly_id", "")),
                        )
                        not in obsolete
                    ]
                    lease_id = f"lease:{subject_id}"
                    lease, lease_version = tx.get("lease", lease_id)
                    live_lease = lease_is_live(lease, now)
                    next_status = task.get("status")
                    next_capsule = task.get("active_capsule_hash")
                    if task.get("status") == "blocked" and not retained_blockers:
                        next_status = "working" if live_lease else "rework"
                        next_capsule = (
                            task.get("active_capsule_hash") if live_lease else None
                        )
                    if lease and lease.get("status") == "active" and not live_lease:
                        tx.transition(
                            "lease",
                            lease_id,
                            "LeaseExpired",
                            {"anomaly_id": anomaly["anomaly_id"]},
                            {**lease, "status": "expired", "expired_at": now},
                            expected_version=lease_version,
                        )
                    updated_task = {
                        **task,
                        "status": next_status,
                        "active_capsule_hash": next_capsule,
                        "blockers": retained_blockers,
                        "updated_at": now,
                    }
                    tx.transition(
                        "task",
                        subject_id,
                        "TaskRecoveredFromHistoricalArtifactFalseBlock",
                        {
                            "anomaly_id": anomaly["anomaly_id"],
                            "removed_blockers": anomaly["facts"].get(
                                "obsolete_blockers", []
                            ),
                            "restored_status": next_status,
                            "preserved_live_lease": live_lease,
                        },
                        updated_task,
                        expected_version=task_version,
                    )
                elif kind in {"artifact_missing", "artifact_hash_drift"}:
                    artifact, artifact_version = tx.require("artifact", subject_id)
                    producer = str(artifact.get("producer_task_id", ""))
                    task, task_version = tx.get("task", producer)
                    if task is None or subject_id not in current_artifact_ids(task):
                        continue
                    updated_artifact = {
                        **artifact,
                        "status": "missing" if kind == "artifact_missing" else "drifted",
                        "recovery_anomaly_id": anomaly["anomaly_id"],
                    }
                    tx.transition(
                        "artifact", subject_id,
                        "ArtifactMissingDetected" if kind == "artifact_missing" else "ArtifactHashDriftDetected",
                        {"anomaly_id": anomaly["anomaly_id"], "facts": anomaly["facts"]},
                        updated_artifact,
                        expected_version=artifact_version,
                    )
                    if task is not None:
                        blocker = {
                            "kind": kind,
                            "artifact_id": subject_id,
                            "anomaly_id": anomaly["anomaly_id"],
                        }
                        blockers = list(task.get("blockers", []))
                        if blocker not in blockers:
                            blockers.append(blocker)
                        updated_task = {
                            **task,
                            "status": "blocked",
                            "active_capsule_hash": None,
                            "blockers": blockers,
                            "updated_at": now,
                        }
                        tx.transition(
                            "task", producer, "TaskBlockedByArtifactFailure",
                            {"anomaly_id": anomaly["anomaly_id"], "artifact_id": subject_id}, updated_task,
                            expected_version=task_version,
                        )
                else:
                    continue
                applied.append(
                    {
                        "anomaly_id": anomaly["anomaly_id"],
                        "kind": kind,
                        "subject_id": subject_id,
                        **(
                            {
                                "released_task_ids": anomaly.get(
                                    "released_task_ids", []
                                )
                            }
                            if kind == "resolved_upstream_invalidation"
                            else {}
                        ),
                    }
                )
            return {"applied": applied, "projection_rebuild": projection_result}

        if not repairable:
            after = scan_episode(store, self.repo_root, now=self.clock(), deep=deep)
            return {**after, "status": "no_safe_repairs", "applied": [], "projection_rebuild": projection_result}
        result = self._execute(
            episode_id, "recovery.apply", actor, payload, handler, request_id=request_id, now=now
        )
        if result.get("ok"):
            result["post_scan"] = scan_episode(store, self.repo_root, now=self.clock(), deep=deep)
        return result
