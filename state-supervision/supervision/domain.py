"""Pure domain helpers for scheduling, context compilation, and validation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable

from .core import DomainError, file_hash, object_hash


TASK_STATUSES = {
    "planned",
    "working",
    "candidate",
    "user_review_pending",
    "approved",
    "rework",
    "blocked",
    "cancelled",
    "superseded",
}
TERMINAL_TASK_STATUSES = {"approved", "cancelled", "superseded"}
LEASE_ACTIVE_STATUSES = {"active"}
MAX_CONTEXT_CHARS = 32 * 1024
MAX_CONTEXT_FILES = 16
MAX_INLINE_REFERENCE_CHARS = 12 * 1024
TARGET_REFERENCE_BRIEF_CHARS = 4 * 1024
REFERENCE_OUTLINE_LIMIT = 12
SCENE_TOKEN_PATTERN = re.compile(r"(?<![A-Za-z0-9])S0*(\d{1,3})(?![A-Za-z0-9])", re.IGNORECASE)


def parse_time(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def add_seconds(value: str, seconds: int) -> str:
    return (parse_time(value) + timedelta(seconds=seconds)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def lease_is_live(lease: dict[str, Any] | None, now: str) -> bool:
    return bool(
        lease
        and lease.get("status") == "active"
        and str(lease.get("expires_at", ""))
        and parse_time(str(lease["expires_at"])) > parse_time(now)
    )


def _scene_tokens(value: Any) -> list[str]:
    """Extract normalized scene identifiers without guessing ranges or prose."""

    return sorted({f"S{int(match)}" for match in SCENE_TOKEN_PATTERN.findall(str(value or ""))})


def task_contract_conflicts(task: dict[str, Any]) -> list[dict[str, Any]]:
    """Declare high-confidence contradictions inside one task contract.

    Structured scene ownership wins no automatic precedence over prose. When
    at least two independent contract fields consistently name another single
    scene, the Harness stops and asks Human to choose instead of making the
    Agent infer authority.
    """

    structured = _scene_tokens(task.get("scene_id"))
    if len(structured) != 1:
        return []
    structured_scene = structured[0]
    assertions: dict[str, list[str]] = {
        field: _scene_tokens(task.get(field))
        for field in ("work_key", "title", "goal")
    }
    votes: dict[str, list[str]] = {}
    for field, scene_ids in assertions.items():
        if len(scene_ids) == 1 and scene_ids[0] != structured_scene:
            votes.setdefault(scene_ids[0], []).append(field)
    if not votes:
        return []
    claimed_scene, fields = sorted(
        votes.items(), key=lambda item: (-len(item[1]), item[0])
    )[0]
    if len(fields) < 2:
        return []
    conflict_key = f"scene_authority:{structured_scene}:{claimed_scene}"
    if conflict_key in set(task.get("resolved_contract_conflict_keys", [])):
        return []
    sources = [
        {
            "field": "scene_id",
            "value": task.get("scene_id"),
            "scene_ids": [structured_scene],
        },
        *[
            {
                "field": field,
                "value": task.get(field),
                "scene_ids": [claimed_scene],
            }
            for field in fields
        ],
    ]
    return [
        {
            "kind": "contradictory_requirements",
            "conflict_key": conflict_key,
            "summary": (
                f"结构字段 scene_id 指向 {structured_scene}，但 "
                f"{', '.join(fields)} 一致指向 {claimed_scene}。"
            ),
            "confidence": "high",
            "requires_human": True,
            "sources": sources,
            "resolution_options": [structured_scene, claimed_scene],
        }
    ]


def dependency_cycle(tasks: dict[str, dict[str, Any]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(task_id: str) -> list[str] | None:
        if task_id in visiting:
            start = stack.index(task_id)
            return stack[start:] + [task_id]
        if task_id in visited:
            return None
        visiting.add(task_id)
        stack.append(task_id)
        for dependency_id in tasks.get(task_id, {}).get("dependencies", []):
            if dependency_id in tasks:
                found = visit(dependency_id)
                if found:
                    return found
        stack.pop()
        visiting.remove(task_id)
        visited.add(task_id)
        return None

    for task_id in sorted(tasks):
        found = visit(task_id)
        if found:
            return found
    return None


def task_blockers(
    task: dict[str, Any],
    tasks: dict[str, dict[str, Any]],
    gaps: list[dict[str, Any]],
    lease: dict[str, Any] | None,
    now: str,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    status = str(task.get("status", "unknown"))
    if status in TERMINAL_TASK_STATUSES:
        blockers.append({"kind": "terminal_status", "status": status})
    elif status in {"candidate", "user_review_pending"}:
        blockers.append({"kind": "awaiting_review", "status": status})
    elif status == "blocked":
        blockers.append({"kind": "blocked_status", "reasons": task.get("blockers", [])})
    for dependency_id in task.get("dependencies", []):
        dependency = tasks.get(dependency_id)
        if dependency is None:
            blockers.append({"kind": "missing_dependency", "task_id": dependency_id})
        elif dependency.get("status") != "approved":
            blockers.append(
                {
                    "kind": "dependency_not_approved",
                    "task_id": dependency_id,
                    "status": dependency.get("status"),
                }
            )
    for gap in gaps:
        if gap.get("task_id") == task.get("task_id") and gap.get("status") == "open":
            blockers.append({"kind": "open_gap", "gap_id": gap.get("gap_id"), "reason": gap.get("reason")})
    if lease_is_live(lease, now):
        blockers.append(
            {
                "kind": "live_lease",
                "owner": lease.get("owner"),
                "generation": lease.get("generation"),
                "expires_at": lease.get("expires_at"),
            }
        )
    return blockers


def scheduling_key(task: dict[str, Any]) -> tuple[int, int, int, int, str]:
    """Deterministic, system-computed rank; agents never score themselves."""

    return (
        -int(bool(task.get("critical_path", False))),
        -int(task.get("unlock_value", 0)),
        -int(task.get("priority", 0)),
        int(task.get("created_seq", 0)),
        str(task.get("task_id", "")),
    )


def resolve_repo_path(repo_root: Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()


def display_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def bind_reference(repo_root: Path, raw: dict[str, Any] | str) -> dict[str, Any]:
    descriptor = {"path": raw} if isinstance(raw, str) else dict(raw)
    raw_path = str(descriptor.get("path", "")).strip()
    if not raw_path:
        raise DomainError(
            "invalid_reference",
            "reference path is required",
            failed_invariant="reference_has_path",
        )
    path = resolve_repo_path(repo_root, raw_path)
    if not path.is_file():
        raise DomainError(
            "reference_missing",
            f"required reference does not exist: {raw_path}",
            failed_invariant="reference_exists",
            allowed_next=("change", "gap"),
            recovery="Restore the reference or update the task binding before work begins.",
            details={"path": raw_path},
        )
    reference_id = str(descriptor.get("reference_id") or descriptor.get("id") or "ref_" + object_hash(display_path(repo_root, path))[:16])
    context_class = str(
        descriptor.get("context_class")
        or descriptor.get("stability")
        or "episode_material"
    ).strip()
    if context_class not in {
        "stable_rule",
        "task_template",
        "episode_material",
        "temporary_override",
        "runtime_fact",
    }:
        raise DomainError(
            "invalid_context_class",
            f"unsupported context class: {context_class}",
            failed_invariant="context_class_known",
            allowed_next=("change",),
        )
    assembly_mode = str(descriptor.get("assembly_mode", "append")).strip()
    if assembly_mode not in {"append", "replace"}:
        raise DomainError(
            "invalid_context_assembly_mode",
            f"unsupported context assembly mode: {assembly_mode}",
            failed_invariant="context_assembly_mode_known",
            allowed_next=("change",),
        )
    return {
        "reference_id": reference_id,
        "path": display_path(repo_root, path),
        "sha256": file_hash(path),
        "required": bool(descriptor.get("required", True)),
        "purpose": str(descriptor.get("purpose", "Required task guidance")).strip(),
        "selector": descriptor.get("selector"),
        "context_class": context_class,
        "context_version": str(
            descriptor.get("context_version")
            or descriptor.get("version")
            or file_hash(path)[:12]
        ),
        "context_slot": str(
            descriptor.get("context_slot")
            or descriptor.get("slot")
            or f"reference:{reference_id}"
        ),
        "assembly_mode": assembly_mode,
        "precedence": int(descriptor.get("precedence", 100)),
        "scope": str(descriptor.get("scope", "task")),
        "service_binding": descriptor.get("service_binding"),
        "mutable": bool(
            descriptor.get(
                "mutable",
                context_class not in {"stable_rule", "task_template"},
            )
        ),
    }


def verify_reference(repo_root: Path, descriptor: dict[str, Any]) -> Path:
    path = resolve_repo_path(repo_root, str(descriptor.get("path", "")))
    if not path.is_file():
        raise DomainError(
            "reference_missing",
            f"bound reference is missing: {descriptor.get('path')}",
            failed_invariant="bound_reference_exists",
            allowed_next=("change", "gap"),
            details={"reference_id": descriptor.get("reference_id"), "path": descriptor.get("path")},
        )
    actual = file_hash(path)
    if actual != descriptor.get("sha256"):
        raise DomainError(
            "reference_drift",
            f"bound reference changed after the task was planned: {descriptor.get('path')}",
            failed_invariant="reference_hash_binding",
            allowed_next=("change", "reference-rebind"),
            recovery="Review the new reference, record its impact, and issue a fresh task capsule.",
            details={
                "reference_id": descriptor.get("reference_id"),
                "expected_sha256": descriptor.get("sha256"),
                "actual_sha256": actual,
            },
        )
    return path


def _selected_text(text: str, selector: Any) -> str:
    if not selector:
        return text
    if isinstance(selector, dict) and "line_start" in selector:
        lines = text.splitlines()
        start = max(1, int(selector.get("line_start", 1))) - 1
        end = min(len(lines), int(selector.get("line_end", len(lines))))
        return "\n".join(lines[start:end])
    return text


def _reference_outline(text: str) -> tuple[list[str], str]:
    headings: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("#"):
            continue
        title = line.lstrip("#").strip()
        if len(title) > 120:
            title = title[:117].rstrip() + "…"
        if title and title not in headings:
            headings.append(title)
        if len(headings) >= REFERENCE_OUTLINE_LIMIT:
            break
    if headings:
        summary = "文档结构包含：" + "；".join(headings)
        if len(headings) >= REFERENCE_OUTLINE_LIMIT:
            summary += "；其余章节未在摘要中展开"
        return headings, summary + "。"
    opening_lines = [line.strip() for line in text.splitlines() if line.strip()][:3]
    opening = " ".join(opening_lines)
    if len(opening) > 240:
        opening = opening[:237].rstrip() + "…"
    summary = "文档没有可提取的 Markdown 标题"
    if opening:
        summary += f"；开头内容为：{opening}"
    return [], summary + "。"


def _reference_budgets(desired: list[int], max_chars: int) -> list[int]:
    """Allocate inline budgets without allowing one large file to starve peers."""
    if not desired:
        return []
    available = max(0, int(max_chars))
    if sum(desired) <= available:
        return list(desired)
    budgets = [0 for _ in desired]
    pending = list(range(len(desired)))
    while pending and available > 0:
        share = available // len(pending)
        satisfied = [index for index in pending if desired[index] <= share]
        if not satisfied:
            for offset, index in enumerate(pending):
                allocation = share + (1 if offset < available % len(pending) else 0)
                budgets[index] = allocation
            break
        for index in satisfied:
            budgets[index] = desired[index]
            available -= desired[index]
            pending.remove(index)
    return budgets


def _reference_brief(
    *,
    text: str,
    path: str,
    sha256: str,
    budget: int,
) -> dict[str, Any]:
    headings, rough_summary = _reference_outline(text)
    prefix = (
        "[受限引用简报]\n"
        f"原文件路径：{path}\n"
        f"SHA256：{sha256}\n"
        "读取策略：本次只注入确定性结构摘要与开头节选；执行中需要完整约束时，按原路径读取原文。\n"
        f"粗略摘要：{rough_summary}\n\n"
        "开头节选：\n"
    )
    excerpt_capacity = max(0, budget - len(prefix) - 72)
    excerpt = text[:excerpt_capacity]
    while True:
        omitted = max(0, len(text) - len(excerpt))
        suffix = f"\n\n[节选结束；原文共 {len(text)} 字，当前节选 {len(excerpt)} 字，省略 {omitted} 字。]"
        overflow = len(prefix) + len(excerpt) + len(suffix) - budget
        if overflow <= 0 or not excerpt:
            break
        excerpt = excerpt[: max(0, len(excerpt) - overflow)]
    content = (prefix + excerpt + suffix)[: max(0, budget)]
    return {
        "content": content,
        "content_chars": len(content),
        "content_mode": "brief",
        "original_chars": len(text),
        "excerpt_chars": len(excerpt),
        "omitted_chars": max(0, len(text) - len(excerpt)),
        "rough_summary": rough_summary,
        "outline": headings,
        "retrieval_policy": "read_original_on_demand",
    }


def compile_capsule(
    *,
    repo_root: Path,
    episode: dict[str, Any],
    task: dict[str, Any],
    task_version: int,
    dependency_states: list[dict[str, Any]],
    relevant_feedback: list[dict[str, Any]],
    relevant_annotations: list[dict[str, Any]],
    open_changes: list[dict[str, Any]],
    why_now: dict[str, Any],
    cursor: int,
    context_overrides: list[dict[str, Any]] | None = None,
    preview: bool = False,
    max_chars: int = MAX_CONTEXT_CHARS,
    max_files: int = MAX_CONTEXT_FILES,
) -> dict[str, Any]:
    references = list(task.get("references", []))
    if len(references) > max_files:
        raise DomainError(
            "context_file_cap_exceeded",
            f"task binds {len(references)} references, above the cap of {max_files}",
            failed_invariant="context_file_cap",
            allowed_next=("change",),
            recovery="Narrow the explicit task reference set; do not ask the worker to search the whole repository.",
        )
    loaded_refs: list[tuple[dict[str, Any], str]] = []
    for descriptor in references:
        path = verify_reference(repo_root, descriptor)
        text = path.read_text(encoding="utf-8", errors="replace")
        selected = _selected_text(text, descriptor.get("selector"))
        loaded_refs.append((descriptor, selected))
    desired_budgets = [
        len(selected)
        if len(selected) <= MAX_INLINE_REFERENCE_CHARS
        else min(len(selected), TARGET_REFERENCE_BRIEF_CHARS)
        for _, selected in loaded_refs
    ]
    allocated_budgets = _reference_budgets(desired_budgets, max_chars)
    compiled_refs: list[dict[str, Any]] = []
    for (descriptor, selected), budget in zip(loaded_refs, allocated_budgets):
        if len(selected) <= budget and len(selected) <= MAX_INLINE_REFERENCE_CHARS:
            headings, rough_summary = _reference_outline(selected)
            compiled = {
                "content": selected,
                "content_chars": len(selected),
                "content_mode": "full",
                "original_chars": len(selected),
                "excerpt_chars": len(selected),
                "omitted_chars": 0,
                "rough_summary": rough_summary,
                "outline": headings,
                "retrieval_policy": "inline_full",
            }
        else:
            compiled = _reference_brief(
                text=selected,
                path=str(descriptor.get("path", "")),
                sha256=str(descriptor.get("sha256", "")),
                budget=budget,
            )
        compiled_refs.append({**descriptor, **compiled})
    used_reference_chars = sum(int(item.get("content_chars", 0)) for item in compiled_refs)
    task_contract = {
        key: task.get(key)
        for key in (
            "task_id",
            "wave_id",
            "scene_id",
            "content_unit_id",
            "deliverable_id",
            "title",
            "kind",
            "goal",
            "role",
            "output_contract",
            "allowed_side_effects",
            "budget",
            "stop_conditions",
            "required_validators",
            "scope_revision",
            "upstream_reapproval_receipts",
        )
    }
    blocks: list[dict[str, Any]] = []

    def add_block(
        *,
        block_id: str,
        context_class: str,
        label: str,
        content: str,
        source: dict[str, Any],
        slot: str,
        version: str,
        precedence: int,
        assembly_mode: str = "append",
        scope: str = "task",
        mutable: bool = False,
        delivery_policy: str = "on_begin",
        content_metadata: dict[str, Any] | None = None,
    ) -> None:
        block = {
                "block_id": block_id,
                "context_class": context_class,
                "label": label,
                "content": content,
                "content_hash": object_hash(content),
                "source": source,
                "slot": slot,
                "version": version,
                "precedence": precedence,
                "assembly_mode": assembly_mode,
                "scope": scope,
                "mutable": mutable,
                "delivery_policy": delivery_policy,
                "status": "active",
                "supersedes": [],
            }
        if content_metadata:
            block.update(content_metadata)
        blocks.append(block)

    add_block(
        block_id=f"task-contract:{task.get('task_id')}:r{task.get('scope_revision', 1)}",
        context_class="task_template",
        label="本步任务合同",
        content=stable_json(task_contract),
        source={"kind": "task", "id": task.get("task_id")},
        slot="task.contract",
        version=str(task.get("scope_revision", 1)),
        precedence=20,
    )
    for descriptor in compiled_refs:
        add_block(
            block_id=f"reference:{descriptor.get('reference_id')}",
            context_class=str(descriptor.get("context_class", "episode_material")),
            label=str(descriptor.get("purpose") or descriptor.get("path")),
            content=str(descriptor.get("content", "")),
            source={
                "kind": "reference",
                "id": descriptor.get("reference_id"),
                "path": descriptor.get("path"),
                "sha256": descriptor.get("sha256"),
                "selector": descriptor.get("selector"),
                "service_binding": descriptor.get("service_binding"),
            },
            slot=str(descriptor.get("context_slot") or f"reference:{descriptor.get('reference_id')}"),
            version=str(descriptor.get("context_version") or descriptor.get("sha256", "")[:12]),
            precedence=int(descriptor.get("precedence", 100)),
            assembly_mode=str(descriptor.get("assembly_mode", "append")),
            scope=str(descriptor.get("scope", "task")),
            mutable=bool(descriptor.get("mutable", True)),
            content_metadata={
                key: descriptor.get(key)
                for key in (
                    "content_mode",
                    "original_chars",
                    "excerpt_chars",
                    "omitted_chars",
                    "rough_summary",
                    "outline",
                    "retrieval_policy",
                )
            },
        )
    for item in relevant_feedback:
        add_block(
            block_id=f"feedback:{item.get('feedback_id')}",
            context_class=str(item.get("context_class", "episode_material")),
            label=str(item.get("pattern_key") or item.get("feedback_id") or "适用反馈"),
            content=str(item.get("instruction") or item.get("body") or item),
            source={"kind": "feedback", "id": item.get("feedback_id"), "source": item.get("source")},
            slot=str(item.get("context_slot") or f"feedback:{item.get('feedback_id')}"),
            version=str(item.get("context_version") or "1"),
            precedence=int(item.get("precedence", 300)),
            scope=str(item.get("scope", "episode")),
            mutable=False,
        )
    for item in relevant_annotations:
        location = item.get("location") or {}
        timecode = location.get("timecode")
        label_parts = ["人类标注", str(item.get("severity") or "note")]
        if timecode:
            label_parts.append(str(timecode))
        add_block(
            block_id=f"annotation:{item.get('annotation_id')}",
            context_class="human_feedback",
            label=" · ".join(label_parts),
            content=stable_json(
                {
                    "body": item.get("body"),
                    "severity": item.get("severity"),
                    "location": location or None,
                    "actor": item.get("actor"),
                    "created_at": item.get("created_at"),
                }
            ),
            source={
                "kind": "annotation",
                "id": item.get("annotation_id"),
                "target_id": item.get("target_id"),
                "target_kind": item.get("target_kind"),
            },
            slot=f"annotation:{item.get('annotation_id')}",
            version=str(item.get("context_version") or "1"),
            precedence=int(item.get("precedence", 450)),
            scope="task",
            mutable=True,
            delivery_policy=str(item.get("delivery_policy") or "on_begin"),
        )
    for item in open_changes:
        add_block(
            block_id=f"change:{item.get('change_id')}",
            context_class="temporary_override",
            label=str(item.get("kind") or "当前显式变更"),
            content=str(item.get("reason") or item),
            source={"kind": "change", "id": item.get("change_id")},
            slot=str(item.get("context_slot") or f"change:{item.get('change_id')}"),
            version=str(item.get("context_version") or "1"),
            precedence=int(item.get("precedence", 500)),
            assembly_mode=str(item.get("assembly_mode", "append")),
            scope=str(item.get("scope", "task")),
            mutable=True,
            delivery_policy=str(item.get("delivery_policy", "on_begin")),
        )
    predicted_attempt = int(task.get("attempt", 0))
    for item in context_overrides or task.get("context_overrides", []) or []:
        if item.get("status", "active") != "active":
            continue
        if int(item.get("effective_attempt", 0)) > predicted_attempt:
            continue
        add_block(
            block_id=str(item.get("override_id") or f"override:{object_hash(item)[:16]}"),
            context_class="temporary_override",
            label=str(item.get("label") or "临时要求"),
            content=str(item.get("instruction") or ""),
            source={"kind": "context_override", "id": item.get("override_id"), "actor": item.get("created_by")},
            slot=str(item.get("context_slot") or "temporary.instructions"),
            version=str(item.get("version", 1)),
            precedence=int(item.get("precedence", 700)),
            assembly_mode=str(item.get("assembly_mode", "append")),
            scope=str(item.get("scope", "task")),
            mutable=True,
            delivery_policy=str(item.get("delivery_policy", "attention_boundary")),
        )
    runtime_content = stable_json(
        {
            "why_now": why_now,
            "dependency_snapshot": dependency_states,
            "task_version": task_version,
            "state_cursor": cursor,
            "preview": preview,
        }
    )
    add_block(
        block_id=f"runtime:{task.get('task_id')}:{cursor}",
        context_class="runtime_fact",
        label="本次运行时事实",
        content=runtime_content,
        source={"kind": "state_projection", "cursor": cursor},
        slot="runtime.facts",
        version=str(cursor),
        precedence=900,
        mutable=False,
        delivery_policy="runtime",
    )

    resolved: list[dict[str, Any]] = []
    superseded: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = task_contract_conflicts(task)
    for block in sorted(blocks, key=lambda item: (int(item["precedence"]), item["block_id"])):
        if block["assembly_mode"] == "replace":
            targets = [item for item in resolved if item["slot"] == block["slot"]]
            if not targets:
                conflicts.append(
                    {
                        "kind": "replace_target_missing",
                        "block_id": block["block_id"],
                        "slot": block["slot"],
                    }
                )
            for target in targets:
                resolved.remove(target)
                superseded.append({**target, "status": "superseded", "superseded_by": block["block_id"]})
                block["supersedes"].append(target["block_id"])
        resolved.append(block)
    assembled_text = "\n\n".join(
        f"## {item['label']}\n{item['content']}" for item in resolved
    )
    class_counts = {
        key: sum(1 for item in resolved if item["context_class"] == key)
        for key in (
            "stable_rule",
            "task_template",
            "episode_material",
            "human_feedback",
            "temporary_override",
            "runtime_fact",
        )
    }
    payload = {
        "schema": "lecture-task-capsule-v2",
        "episode": {
            "episode_id": episode.get("episode_id"),
            "title": episode.get("title"),
            "mission": episode.get("mission"),
            "quality_policy": episode.get("quality_policy"),
        },
        "task": task_contract,
        "why_now": why_now,
        "dependency_snapshot": dependency_states,
        "required_references": compiled_refs,
        "relevant_feedback": relevant_feedback,
        "relevant_annotations": relevant_annotations,
        "open_changes": open_changes,
        "context_manifest": {
            "preview": preview,
            "class_counts": class_counts,
            "active_block_count": len(resolved),
            "superseded_block_count": len(superseded),
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "context_revision": int(task.get("context_revision", 0)),
            "issued_context_revision": int(task.get("issued_context_revision", 0)),
            "annotation_count": len(relevant_annotations),
            "annotation_ids": [
                item.get("annotation_id") for item in relevant_annotations
            ],
        },
        "context_blocks": resolved,
        "superseded_context_blocks": superseded,
        "assembled_prompt": assembled_text,
        "submission_contract": {
            "capsule_hash_is_implicit": True,
            "required_artifact_roles": task.get("output_contract", {}).get("required_artifact_roles", []),
            "do_not_expand_scope": True,
            "on_missing_context": "gap",
            "on_scope_change": "change",
        },
        "task_version": task_version,
        "state_cursor": cursor,
        "context_budget": {
            "max_chars": max_chars,
            "used_chars": used_reference_chars,
            "max_files": max_files,
            "used_files": len(compiled_refs),
            "full_references": sum(1 for item in compiled_refs if item.get("content_mode") == "full"),
            "brief_references": sum(1 for item in compiled_refs if item.get("content_mode") == "brief"),
            "omitted_source_chars": sum(int(item.get("omitted_chars", 0)) for item in compiled_refs),
        },
    }
    payload["semantic_hash"] = object_hash(payload)
    return payload


def relevant_feedback_for_task(
    task: dict[str, Any],
    feedback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    task_tags = set(task.get("tags", []))
    result: list[dict[str, Any]] = []
    for item in feedback:
        if item.get("status") != "active":
            continue
        applies_to = set(item.get("applies_to", []))
        if not applies_to or "*" in applies_to or task.get("task_id") in applies_to or task_tags & applies_to:
            result.append(
                {
                    "feedback_id": item.get("feedback_id"),
                    "pattern_key": item.get("pattern_key"),
                    "instruction": item.get("instruction"),
                    "source": item.get("source"),
                }
            )
    return sorted(result, key=lambda item: str(item.get("feedback_id")))


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
