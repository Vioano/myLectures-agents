#!/usr/bin/env python3
"""Strict JSON-state gate for lecture animation reviews.

The gate is deliberately procedural. It does not decide taste for the reviewer;
it refuses incomplete review packages until the reviewer has acknowledged the
required skill documents, submitted enough concrete suspicion-led findings, and
the animation owner has answered every open issue with fix evidence.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "lecture-animation-review-gate-v1"
SKILL_DIR = Path(__file__).resolve().parents[1]

CORE_REQUIRED_DOCS = [
    "SKILL.md",
    "references/20-math-object-driven-animation.md",
    "references/30-visual-language-and-style.md",
    "references/40-production-loop-and-qc.md",
    "references/41-production-output-contract.md",
    "references/42-scene-contract-and-composer.md",
    "references/50-known-failures-and-fixes.md",
]

OPTIONAL_REQUIRED_DOCS = [
    "references/43-review-red-flag-rubric.md",
]

ABSTRACT_STANDARD_KEYS = [
    "stage_management_failure",
    "ambiguous_visual_object",
    "mathematical_identity_or_causality_failure",
    "timeline_visual_alignment_failure",
    "space_utilization_failure",
    "visual_hierarchy_failure",
    "pedagogical_example_failure",
]

RISK_TIERS = {
    "low": {
        "min_candidate_flags": 6,
        "min_ranked_aesthetic": 3,
        "min_abstract_standards": len(ABSTRACT_STANDARD_KEYS),
        "max_pardons_for_pass": 4,
        "max_pardon_rate_for_pass": 0.25,
        "min_fix_rounds_before_pass": 0,
    },
    "normal": {
        "min_candidate_flags": 8,
        "min_ranked_aesthetic": 4,
        "min_abstract_standards": len(ABSTRACT_STANDARD_KEYS),
        "max_pardons_for_pass": 3,
        "max_pardon_rate_for_pass": 0.20,
        "min_fix_rounds_before_pass": 0,
    },
    "dense": {
        "min_candidate_flags": 12,
        "min_ranked_aesthetic": 5,
        "min_abstract_standards": len(ABSTRACT_STANDARD_KEYS),
        "max_pardons_for_pass": 2,
        "max_pardon_rate_for_pass": 0.12,
        "min_fix_rounds_before_pass": 1,
    },
    "human-rejected": {
        "min_candidate_flags": 18,
        "min_ranked_aesthetic": 7,
        "min_abstract_standards": len(ABSTRACT_STANDARD_KEYS),
        "max_pardons_for_pass": 1,
        "max_pardon_rate_for_pass": 0.05,
        "min_fix_rounds_before_pass": 2,
    },
    "repeat-rejected": {
        "min_candidate_flags": 24,
        "min_ranked_aesthetic": 10,
        "min_abstract_standards": len(ABSTRACT_STANDARD_KEYS),
        "max_pardons_for_pass": 0,
        "max_pardon_rate_for_pass": 0.0,
        "min_fix_rounds_before_pass": 3,
    },
}

NO_PARDON_PATTERN_KEYS = {
    "ambiguous_unowned_fill",
    "bottom_formula_lane_collision",
    "duplicate_delta_omega",
    "duplicate_semantic_object",
    "formula_in_subtitle_lane",
    "formula_only_scene_without_visual_causality",
    "lingering_semantic_object",
    "ppt_like_static_derivation",
    "riemann_sum_named_but_not_visualized",
    "slow_fade_ghost",
    "stray_debug_rectangle",
    "subtitle_safe_zone_violation",
}

NO_PARDON_SOURCES = {"human_review", "accepted_agent_feedback"}

INSPECTION_KEYS = [
    "watched_review_mp4",
    "checked_qc_frames",
    "checked_source_code",
    "checked_timeline_alignment",
    "checked_regression_records",
    "checked_authoring_preflight",
]

OPEN_STATUSES = {"open", "revise", "blocked"}
NON_OPEN_STATUSES = {"fixed", "pardoned", "cleared", "not_applicable"}
ALL_FINDING_STATUSES = OPEN_STATUSES | NON_OPEN_STATUSES


class GateError(Exception):
    """Human-readable validation failure."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def safe_slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    value = re.sub(r"_+", "_", value).strip("._")
    return value or "unnamed"


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise GateError(f"{path}: file is not valid UTF-8: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise GateError(f"{path}: invalid JSON: {exc}") from exc


def is_macos_metadata(path: Path) -> bool:
    return path.name.startswith("._") or path.name == ".DS_Store"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def append_jsonl(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_to_repo(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def load_state(session: str | Path) -> tuple[Path, dict[str, Any]]:
    path = Path(session)
    if path.is_dir():
        path = path / "state.json"
    if not path.exists():
        raise GateError(f"state file not found: {path}")
    state = read_json(path)
    if state.get("schema") != SCHEMA:
        raise GateError(f"{path}: unexpected schema {state.get('schema')!r}")
    return path, state


def save_state(path: Path, state: dict[str, Any], event: dict[str, Any] | None = None) -> None:
    state["updated_at"] = utc_now()
    if event:
        state.setdefault("events", []).append(event)
    write_json(path, state)
    if event:
        event_path = path.parent / "events.jsonl"
        with event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def append_metrics_record(state_path: Path, state: dict[str, Any], record: dict[str, Any]) -> None:
    """Persist review/fix quality metrics outside chat context.

    Each session keeps its own append-only JSONL ledger, and the episode also
    gets an aggregate ledger so later agents can audit reviewer behavior across
    scenes without reopening every accepted review payload.
    """

    repo_root = Path(state["repo_root"]).resolve()
    episode_dir = (repo_root / state["episode"]).resolve()
    payload = {
        "at": utc_now(),
        "schema": "lecture-animation-review-metrics-v1",
        "session_id": state["session_id"],
        "scene_slug": state["scene_slug"],
        "review_id": state["review_id"],
        "risk_tier": state["risk_tier"],
        "round": state.get("round"),
        **record,
    }
    session_metrics = state_path.parent / "review_metrics.jsonl"
    episode_metrics = episode_dir / "review" / "gate" / "review_metrics.jsonl"
    append_jsonl(session_metrics, payload)
    append_jsonl(episode_metrics, payload)
    state.setdefault("metrics_history", []).append(payload)


def resolve_existing_path(
    value: Any,
    repo_root: Path,
    episode_dir: Path,
    session_dir: Path | None = None,
) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = Path(value)
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(repo_root / raw)
        candidates.append(episode_dir / raw)
        if session_dir:
            candidates.append(session_dir / raw)
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def add_doc(docs: list[dict[str, str]], repo_root: Path, path: Path, role: str) -> None:
    if not path.exists() or not path.is_file():
        return
    docs.append(
        {
            "path": relative_to_repo(path, repo_root),
            "sha256": sha256_file(path),
            "role": role,
        }
    )


def issue_relevant_to_scene(issue: dict[str, Any], scene_slug: str) -> bool:
    if issue.get("must_check_in_future") is True:
        future_required = True
    else:
        source = issue.get("source")
        future_required = source in {"human_review", "accepted_agent_feedback"}
    if issue.get("status") == "open":
        future_required = True
    if not future_required:
        return False

    scene_value = (
        issue.get("scene")
        or issue.get("scene_slug")
        or issue.get("scene_group")
        or issue.get("segment")
    )
    if not scene_value:
        return True
    scene_text = str(scene_value)
    scene_norm = scene_slug.lower()
    issue_norm = scene_text.lower().replace("-", "_")
    range_match = re.fullmatch(r"g(\d{3})_g(\d{3})", issue_norm)
    scene_group = re.match(r"g(\d{3})", scene_norm)
    if range_match and scene_group:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        current = int(scene_group.group(1))
        return start <= current <= end
    if re.fullmatch(r"g\d{3}", issue_norm) and scene_group:
        return scene_norm.startswith(issue_norm)
    return scene_text == scene_slug or scene_slug in scene_text or scene_text in scene_slug


def collect_required_documents(
    repo_root: Path,
    episode_dir: Path,
    scene_slug: str,
) -> list[dict[str, str]]:
    docs: list[dict[str, str]] = []
    for rel_path in CORE_REQUIRED_DOCS:
        add_doc(docs, repo_root, SKILL_DIR / rel_path, "skill_required")
    for rel_path in OPTIONAL_REQUIRED_DOCS:
        add_doc(docs, repo_root, SKILL_DIR / rel_path, "skill_optional_present")

    for folder, role in [
        ("review/human-feedback", "episode_human_feedback"),
        ("review/agent-feedback", "episode_agent_feedback"),
    ]:
        base = episode_dir / folder
        if base.exists():
            for path in sorted(base.glob("*.md")):
                if is_macos_metadata(path):
                    continue
                add_doc(docs, repo_root, path, role)

    issues_dir = episode_dir / "review" / "issues"
    if issues_dir.exists():
        for path in sorted(issues_dir.glob("*.json")):
            if is_macos_metadata(path):
                continue
            try:
                issue = read_json(path)
            except GateError:
                add_doc(docs, repo_root, path, "episode_issue_unreadable")
                continue
            if isinstance(issue, dict) and issue_relevant_to_scene(issue, scene_slug):
                add_doc(docs, repo_root, path, "episode_issue_regression")

    # Deduplicate by path while preserving order.
    seen: set[str] = set()
    unique_docs: list[dict[str, str]] = []
    for doc in docs:
        if doc["path"] in seen:
            continue
        seen.add(doc["path"])
        unique_docs.append(doc)
    return unique_docs


def init_session(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    episode_dir = (repo_root / args.episode).resolve()
    if not episode_dir.exists() or not episode_dir.is_dir():
        raise GateError(f"episode directory not found: {episode_dir}")
    if args.risk_tier not in RISK_TIERS:
        raise GateError(f"unknown risk tier: {args.risk_tier}")

    review_id = safe_slug(args.review_id)
    scene_slug = safe_slug(args.scene_slug)
    timestamp = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    session_id = safe_slug(args.session_id or f"{scene_slug}_{review_id}_{timestamp}")
    if args.state_root:
        state_root = Path(args.state_root).resolve()
    else:
        state_root = episode_dir / "review" / "gate" / scene_slug
    session_dir = state_root / session_id
    state_path = session_dir / "state.json"
    if state_path.exists() and not args.force:
        raise GateError(f"session already exists: {state_path}")

    state = {
        "schema": SCHEMA,
        "session_id": session_id,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "repo_root": repo_root.as_posix(),
        "episode": relative_to_repo(episode_dir, repo_root),
        "scene_slug": scene_slug,
        "review_id": review_id,
        "owner": args.owner,
        "reviewer": args.reviewer,
        "risk_tier": args.risk_tier,
        "thresholds": RISK_TIERS[args.risk_tier],
        "status": "initialized",
        "round": 1,
        "required_documents": collect_required_documents(repo_root, episode_dir, scene_slug),
        "open_issues": [],
        "fixed_pending_rereview": [],
        "accepted_reviews": [],
        "accepted_fixes": [],
        "events": [],
    }
    event = {
        "at": utc_now(),
        "type": "session_initialized",
        "session_id": session_id,
        "risk_tier": args.risk_tier,
    }
    save_state(state_path, state, event)
    print(state_path)
    return 0


def print_checklist(args: argparse.Namespace) -> int:
    state_path, state = load_state(args.session)
    print(f"session: {state['session_id']}")
    print(f"state: {state_path}")
    print(f"status: {state['status']}")
    print(f"risk_tier: {state['risk_tier']}")
    print("thresholds:")
    for key, value in state["thresholds"].items():
        print(f"  {key}: {value}")
    print("required_documents:")
    for index, doc in enumerate(state["required_documents"], start=1):
        print(f"  {index}. {doc['path']}")
        print(f"     role: {doc['role']}")
        print(f"     sha256: {doc['sha256']}")
    print("required_abstract_standards:")
    for key in ABSTRACT_STANDARD_KEYS:
        print(f"  - {key}")
    print("required_inspection_ticks:")
    for key in INSPECTION_KEYS:
        print(f"  - {key}")
    print("  - checked_layout_audit, unless a written not-applicable reason is submitted")
    print("reviewer_must_submit:")
    print("  - exact read confirmations for every required document above")
    print("  - one abstract-standard ledger entry per required standard")
    print("  - regression ledger entries for all required issue JSON files")
    print("  - candidate flags meeting the risk-tier count")
    print("  - ranked aesthetic/visual-guidance objections meeting the risk-tier count")
    print("  - audit artifacts and evidence paths")
    return 0


def confirm_read(args: argparse.Namespace) -> int:
    state_path, state = load_state(args.session)
    confirmations: list[dict[str, Any]] = []
    print("Type READ for each document only after reading it completely.")
    for doc in state["required_documents"]:
        print(f"\n{doc['path']}")
        print(f"sha256: {doc['sha256']}")
        answer = input("confirm full read by typing READ: ").strip()
        if answer != "READ":
            raise GateError(f"read confirmation aborted at {doc['path']}")
        confirmations.append(
            {
                "path": doc["path"],
                "sha256": doc["sha256"],
                "read_full": True,
                "reviewer": args.reviewer or state.get("reviewer"),
                "confirmed_at": utc_now(),
            }
        )
    output_path = state_path.parent / f"read_confirmations__{safe_slug(args.reviewer or 'reviewer')}.json"
    write_json(output_path, {"read_confirmations": confirmations})
    print(output_path)
    return 0


def template_review(args: argparse.Namespace) -> int:
    _, state = load_state(args.session)
    required_docs = [
        {
            "path": doc["path"],
            "sha256": doc["sha256"],
            "read_full": False,
            "reviewer": state.get("reviewer") or "",
        }
        for doc in state["required_documents"]
    ]
    regression_files = [
        doc["path"]
        for doc in state["required_documents"]
        if doc["role"] == "episode_issue_regression"
    ]
    inspection = {key: False for key in INSPECTION_KEYS}
    inspection["checked_layout_audit"] = False
    template = {
        "session_id": state["session_id"],
        "reviewer": state.get("reviewer") or "",
        "verdict": "revise",
        "artifacts": {
            "audit_report": "review/audits/<scene_slug>/<review_id>__<reviewer>__<branch>.md",
            "review_mp4": "exports/reviews/<scene_slug>/<review_id>.mp4",
            "qc_output": "exports/qc/<qc_id>/contact_sheet.png",
            "layout_audit": "review/audits/<scene_slug>/<layout_audit>.json",
            "source_files": ["src/<scene_slug>.py"],
            "timeline": "timeline.json",
            "formula_manifest": "formula-manifest.md",
            "stage_direction": "src/<scene_slug>.stage.md",
        },
        "layout_audit_not_applicable_reason": "",
        "stage_direction_not_applicable_reason": "",
        "read_confirmations": required_docs,
        "inspection": inspection,
        "ledgers": {
            "abstract_standards": [
                {
                    "standard_key": key,
                    "status": "candidate_found",
                    "evidence": "",
                }
                for key in ABSTRACT_STANDARD_KEYS
            ],
            "regressions": [
                {
                    "issue_file": issue_file,
                    "status": "checked",
                    "evidence": "",
                }
                for issue_file in regression_files
            ],
            "candidate_flags": [],
            "ranked_aesthetic": [],
        },
        "issues": [],
    }
    json.dump(template, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    print()
    return 0


def template_fix(args: argparse.Namespace) -> int:
    _, state = load_state(args.session)
    fixes = []
    for issue in state.get("open_issues", []):
        fixes.append(
            {
                "issue_id": issue["id"],
                "status": "fixed",
                "fix_notes": "",
                "changed_files": [],
                "after_evidence": {
                    "review_mp4": "",
                    "qc_frame": "",
                    "notes": "",
                },
                "pardon_reason": "",
            }
        )
    template = {
        "session_id": state["session_id"],
        "fixer": state.get("owner") or "",
        "artifacts": {
            "review_mp4": "exports/reviews/<scene_slug>/<review_id>_postfix.mp4",
            "qc_output": "exports/qc/<qc_id>_postfix/contact_sheet.png",
            "layout_audit": "review/audits/<scene_slug>/<layout_audit>_postfix.json",
        },
        "layout_audit_not_applicable_reason": "",
        "fixes": fixes,
    }
    json.dump(template, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    print()
    return 0


def validate_read_confirmations(state: dict[str, Any], submission: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    confirmations = submission.get("read_confirmations")
    if not isinstance(confirmations, list):
        return ["read_confirmations must be a list"]
    by_path: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(confirmations):
        if not isinstance(item, dict):
            errors.append(f"read_confirmations[{index}] must be an object")
            continue
        path = item.get("path")
        if not isinstance(path, str):
            errors.append(f"read_confirmations[{index}].path must be a string")
            continue
        by_path[path] = item
    for doc in state["required_documents"]:
        item = by_path.get(doc["path"])
        if not item:
            errors.append(f"missing read confirmation: {doc['path']}")
            continue
        if item.get("sha256") != doc["sha256"]:
            errors.append(f"sha256 mismatch for read confirmation: {doc['path']}")
        if item.get("read_full") is not True:
            errors.append(f"read_full must be true for: {doc['path']}")
    return errors


def validate_artifacts(
    state: dict[str, Any],
    submission: dict[str, Any],
    state_path: Path,
    *,
    for_fix: bool = False,
) -> list[str]:
    errors: list[str] = []
    repo_root = Path(state["repo_root"]).resolve()
    episode_dir = (repo_root / state["episode"]).resolve()
    artifacts = submission.get("artifacts")
    if not isinstance(artifacts, dict):
        return ["artifacts must be an object"]
    required_single = ["review_mp4", "qc_output"]
    if not for_fix:
        required_single.extend(["audit_report", "timeline", "formula_manifest"])
    for key in required_single:
        if not resolve_existing_path(artifacts.get(key), repo_root, episode_dir, state_path.parent):
            errors.append(f"artifacts.{key} path does not exist or is missing")

    if not for_fix:
        source_files = artifacts.get("source_files")
        if not isinstance(source_files, list) or not source_files:
            errors.append("artifacts.source_files must be a non-empty list")
        else:
            for index, value in enumerate(source_files):
                if not resolve_existing_path(value, repo_root, episode_dir, state_path.parent):
                    errors.append(f"artifacts.source_files[{index}] path does not exist")
        if not resolve_existing_path(artifacts.get("stage_direction"), repo_root, episode_dir, state_path.parent):
            if not submission.get("stage_direction_not_applicable_reason"):
                errors.append(
                    "artifacts.stage_direction is missing; provide stage_direction_not_applicable_reason if truly not applicable"
                )

    if not resolve_existing_path(artifacts.get("layout_audit"), repo_root, episode_dir, state_path.parent):
        if not submission.get("layout_audit_not_applicable_reason"):
            errors.append(
                "artifacts.layout_audit is missing; provide layout_audit_not_applicable_reason if truly not applicable"
            )
    return errors


def validate_inspection(submission: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    inspection = submission.get("inspection")
    if not isinstance(inspection, dict):
        return ["inspection must be an object"]
    for key in INSPECTION_KEYS:
        if inspection.get(key) is not True:
            errors.append(f"inspection.{key} must be true")
    if not submission.get("layout_audit_not_applicable_reason"):
        if inspection.get("checked_layout_audit") is not True:
            errors.append("inspection.checked_layout_audit must be true unless layout audit is not applicable")
    return errors


def validate_abstract_standards(submission: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ledgers = submission.get("ledgers")
    if not isinstance(ledgers, dict):
        return ["ledgers must be an object"]
    standards = ledgers.get("abstract_standards")
    if not isinstance(standards, list):
        return ["ledgers.abstract_standards must be a list"]
    by_key: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(standards):
        if not isinstance(item, dict):
            errors.append(f"ledgers.abstract_standards[{index}] must be an object")
            continue
        key = item.get("standard_key")
        if key not in ABSTRACT_STANDARD_KEYS:
            errors.append(f"unknown abstract standard at index {index}: {key!r}")
            continue
        by_key[key] = item
        if item.get("status") not in {"candidate_found", "cleared", "not_applicable"}:
            errors.append(f"abstract standard {key}: invalid status {item.get('status')!r}")
        if not item.get("evidence"):
            errors.append(f"abstract standard {key}: evidence is required")
    for key in ABSTRACT_STANDARD_KEYS:
        if key not in by_key:
            errors.append(f"missing abstract standard ledger entry: {key}")
    return errors


def validate_regressions(state: dict[str, Any], submission: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_issue_files = [
        doc["path"]
        for doc in state.get("required_documents", [])
        if doc.get("role") == "episode_issue_regression"
    ]
    ledgers = submission.get("ledgers")
    regressions = ledgers.get("regressions") if isinstance(ledgers, dict) else None
    if not isinstance(regressions, list):
        regressions = []
        if required_issue_files:
            errors.append("ledgers.regressions must be a list")
    by_file: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(regressions):
        if not isinstance(item, dict):
            errors.append(f"ledgers.regressions[{index}] must be an object")
            continue
        issue_file = item.get("issue_file")
        if not isinstance(issue_file, str):
            errors.append(f"ledgers.regressions[{index}].issue_file must be a string")
            continue
        by_file[issue_file] = item
        if item.get("status") not in {"checked", "repeated", "fixed", "pardoned", "not_applicable"}:
            errors.append(f"regression {issue_file}: invalid status {item.get('status')!r}")
        if item.get("status") == "pardoned" and regression_is_no_pardon(state, issue_file):
            errors.append(
                f"regression {issue_file}: human/accepted regression records cannot be pardoned; "
                "mark not_applicable with evidence or open a revise issue"
            )
        if not item.get("evidence"):
            errors.append(f"regression {issue_file}: evidence is required")
    for issue_file in required_issue_files:
        if issue_file not in by_file:
            errors.append(f"missing regression ledger entry for {issue_file}")
    return errors


def regression_is_no_pardon(state: dict[str, Any], issue_file: str) -> bool:
    repo_root = Path(state["repo_root"]).resolve()
    path = repo_root / issue_file
    if not path.exists():
        return True
    try:
        issue = read_json(path)
    except GateError:
        return True
    if not isinstance(issue, dict):
        return True
    return (
        issue.get("source") in NO_PARDON_SOURCES
        or issue.get("must_check_in_future") is True
        or str(issue.get("pattern_key") or issue.get("id") or "") in NO_PARDON_PATTERN_KEYS
    )


def finding_id(item: dict[str, Any], prefix: str, index: int) -> str:
    raw = item.get("id") or f"{prefix}_{index:03d}"
    return safe_slug(str(raw))


def validate_finding_list(
    items: Any,
    label: str,
    minimum: int,
    *,
    ranked: bool = False,
) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    normalized: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return [f"{label} must be a list"], []
    if len(items) < minimum:
        errors.append(f"{label} must contain at least {minimum} entries; got {len(items)}")
    ranks: set[int] = set()
    ids: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index - 1}] must be an object")
            continue
        issue_id = finding_id(item, "aesthetic" if ranked else "candidate", index)
        if issue_id in ids:
            errors.append(f"{label}: duplicate id {issue_id}")
        ids.add(issue_id)
        status = item.get("status")
        if status not in ALL_FINDING_STATUSES:
            errors.append(f"{label}.{issue_id}: invalid status {status!r}")
        for field in ["evidence", "problem", "impact"]:
            if not item.get(field):
                errors.append(f"{label}.{issue_id}: {field} is required")
        if not item.get("fix_target"):
            errors.append(f"{label}.{issue_id}: fix_target is required")
        if status == "pardoned" and not item.get("pardon_reason"):
            errors.append(f"{label}.{issue_id}: pardon_reason is required for pardoned status")
        if status in {"open", "revise", "blocked"} and not item.get("suggested_fix"):
            errors.append(f"{label}.{issue_id}: suggested_fix is required for open/revise/blocked status")
        if not ranked and item.get("standard_key") not in ABSTRACT_STANDARD_KEYS:
            errors.append(f"{label}.{issue_id}: standard_key must be one of the abstract standards")
        if ranked:
            rank = item.get("rank")
            if not isinstance(rank, int) or rank < 1:
                errors.append(f"{label}.{issue_id}: rank must be a positive integer")
            else:
                if rank in ranks:
                    errors.append(f"{label}: duplicate rank {rank}")
                ranks.add(rank)
        copied = dict(item)
        copied["id"] = issue_id
        normalized.append(copied)
    if ranked and ranks:
        expected = set(range(1, min(len(items), minimum) + 1))
        if not expected.issubset(ranks):
            missing = sorted(expected - ranks)
            errors.append(f"{label}: missing required early ranks {missing}")
    return errors, normalized


def normalize_issue_entries(submission: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    issues = submission.get("issues") or []
    if not isinstance(issues, list):
        return ["issues must be a list"], []
    normalized: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, issue in enumerate(issues, start=1):
        if not isinstance(issue, dict):
            errors.append(f"issues[{index - 1}] must be an object")
            continue
        issue_id = finding_id(issue, "issue", index)
        if issue_id in ids:
            errors.append(f"issues: duplicate id {issue_id}")
        ids.add(issue_id)
        status = issue.get("status")
        if status not in ALL_FINDING_STATUSES:
            errors.append(f"issues.{issue_id}: invalid status {status!r}")
        for field in ["evidence", "problem", "impact", "fix_target"]:
            if not issue.get(field):
                errors.append(f"issues.{issue_id}: {field} is required")
        if status == "pardoned" and not issue.get("pardon_reason"):
            errors.append(f"issues.{issue_id}: pardon_reason is required for pardoned status")
        if status in OPEN_STATUSES and not issue.get("suggested_fix"):
            errors.append(f"issues.{issue_id}: suggested_fix is required for open issue")
        copied = dict(issue)
        copied["id"] = issue_id
        normalized.append(copied)
    return errors, normalized


def finding_pattern_key(item: dict[str, Any]) -> str:
    raw = item.get("pattern_key") or item.get("id") or item.get("requirement") or ""
    return safe_slug(str(raw)).lower()


def is_no_pardon_finding(item: dict[str, Any]) -> bool:
    return (
        finding_pattern_key(item) in NO_PARDON_PATTERN_KEYS
        or item.get("source") in NO_PARDON_SOURCES
        or item.get("must_check_in_future") is True
    )


def compute_status_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in sorted(ALL_FINDING_STATUSES)}
    counts["missing"] = 0
    for item in items:
        status = item.get("status")
        if status in counts:
            counts[status] += 1
        else:
            counts["missing"] += 1
    return counts


def compute_review_metrics(
    state: dict[str, Any],
    submission: dict[str, Any],
    candidate_flags: list[dict[str, Any]],
    ranked_aesthetic: list[dict[str, Any]],
    explicit_issues: list[dict[str, Any]],
    open_issues: list[dict[str, Any]],
) -> dict[str, Any]:
    findings = [*candidate_flags, *ranked_aesthetic, *explicit_issues]
    counts = compute_status_counts(findings)
    total_findings = len(findings)
    pardon_count = counts.get("pardoned", 0)
    return {
        "record_type": "review",
        "accepted": False,
        "reviewer": submission.get("reviewer") or state.get("reviewer"),
        "verdict": submission.get("verdict"),
        "candidate_flag_count": len(candidate_flags),
        "ranked_aesthetic_count": len(ranked_aesthetic),
        "explicit_issue_count": len(explicit_issues),
        "total_finding_count": total_findings,
        "open_issue_count": len(open_issues),
        "status_counts": counts,
        "pardon_count": pardon_count,
        "pardon_rate": (pardon_count / total_findings) if total_findings else 0.0,
        "accepted_fix_rounds_before_review": len(state.get("accepted_fixes", [])),
        "accepted_review_rounds_before_review": len(state.get("accepted_reviews", [])),
    }


def validate_review_metrics_policy(
    state: dict[str, Any],
    submission: dict[str, Any],
    candidate_flags: list[dict[str, Any]],
    ranked_aesthetic: list[dict[str, Any]],
    explicit_issues: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    findings = [*candidate_flags, *ranked_aesthetic, *explicit_issues]
    for item in findings:
        if item.get("status") == "pardoned" and is_no_pardon_finding(item):
            errors.append(
                f"{finding_id(item, 'finding', 0)}: no-pardon finding {finding_pattern_key(item)!r} "
                "cannot be pardoned; mark fixed/not_applicable with evidence or leave it open"
            )

    verdict = submission.get("verdict")
    if verdict == "pass":
        verdict = "pass_for_user_review_pending"
    if verdict != "pass_for_user_review_pending":
        return errors

    thresholds = state.get("thresholds", {})
    max_pardons = int(thresholds.get("max_pardons_for_pass", 0))
    max_rate = float(thresholds.get("max_pardon_rate_for_pass", 0.0))
    min_fix_rounds = int(thresholds.get("min_fix_rounds_before_pass", 0))
    pardon_count = int(metrics["pardon_count"])
    pardon_rate = float(metrics["pardon_rate"])
    accepted_fix_rounds = int(metrics["accepted_fix_rounds_before_review"])

    if pardon_count > max_pardons:
        errors.append(
            "abnormal review pattern: pardon_count "
            f"{pardon_count} exceeds {state['risk_tier']} limit {max_pardons}; "
            "re-review and convert weak pardons to fixed/not_applicable/open findings"
        )
    if pardon_rate > max_rate:
        errors.append(
            "abnormal review pattern: pardon_rate "
            f"{pardon_rate:.3f} exceeds {state['risk_tier']} limit {max_rate:.3f}; "
            "re-review instead of passing with broad pardons"
        )
    if accepted_fix_rounds < min_fix_rounds:
        errors.append(
            "abnormal review pattern: pass requested after "
            f"{accepted_fix_rounds} accepted fix rounds; {state['risk_tier']} requires "
            f"at least {min_fix_rounds} fix/rereview loops before pass"
        )
    return errors


def collect_open_review_issues(
    state: dict[str, Any],
    submission: dict[str, Any],
    candidate_flags: list[dict[str, Any]],
    ranked_aesthetic: list[dict[str, Any]],
    explicit_issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    open_items: list[dict[str, Any]] = []
    for source_label, items in [
        ("candidate_flag", candidate_flags),
        ("ranked_aesthetic", ranked_aesthetic),
        ("explicit_issue", explicit_issues),
    ]:
        for item in items:
            if item.get("status") not in OPEN_STATUSES:
                continue
            issue_id = item["id"]
            if source_label == "ranked_aesthetic":
                standard_key = item.get("standard_key") or "visual_hierarchy_failure"
            else:
                standard_key = item.get("standard_key")
            open_items.append(
                {
                    "id": issue_id,
                    "source": "subagent_review",
                    "reviewer": submission.get("reviewer") or state.get("reviewer"),
                    "scene": state["scene_slug"],
                    "review_id": state["review_id"],
                    "severity": item.get("severity") or "major",
                    "status": "open",
                    "standard_key": standard_key,
                    "pattern_key": item.get("pattern_key") or issue_id,
                    "must_check_in_future": bool(item.get("must_check_in_future", False)),
                    "applies_to_authoring": bool(item.get("applies_to_authoring", False)),
                    "requirement": item.get("requirement") or "lecture-animation-pipeline strict review gate",
                    "evidence": item.get("evidence"),
                    "problem": item.get("problem"),
                    "impact": item.get("impact"),
                    "fix_target": item.get("fix_target"),
                    "suggested_fix": item.get("suggested_fix"),
                    "gate_source": source_label,
                }
            )
    return open_items


def write_issue_files(state: dict[str, Any], open_issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    repo_root = Path(state["repo_root"]).resolve()
    episode_dir = (repo_root / state["episode"]).resolve()
    issue_dir = episode_dir / "review" / "issues"
    issue_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, Any]] = []
    for issue in open_issues:
        filename = f"{safe_slug(state['scene_slug'])}_{safe_slug(state['review_id'])}_{safe_slug(issue['id'])}.json"
        path = issue_dir / filename
        payload = dict(issue)
        payload["created_at"] = utc_now()
        write_json(path, payload)
        summary = dict(issue)
        summary["issue_file"] = relative_to_repo(path, repo_root)
        written.append(summary)
    return written


def submit_review(args: argparse.Namespace) -> int:
    state_path, state = load_state(args.session)
    submission = read_json(Path(args.input))
    errors: list[str] = []

    if submission.get("session_id") != state["session_id"]:
        errors.append("session_id does not match gate state")
    verdict = submission.get("verdict")
    if verdict == "pass":
        verdict = "pass_for_user_review_pending"
    if verdict not in {"revise", "blocked", "pass_for_user_review_pending"}:
        errors.append("verdict must be revise, blocked, or pass_for_user_review_pending")

    errors.extend(validate_read_confirmations(state, submission))
    errors.extend(validate_artifacts(state, submission, state_path))
    errors.extend(validate_inspection(submission))
    errors.extend(validate_abstract_standards(submission))
    errors.extend(validate_regressions(state, submission))

    ledgers = submission.get("ledgers") if isinstance(submission.get("ledgers"), dict) else {}
    thresholds = state["thresholds"]
    candidate_errors, candidate_flags = validate_finding_list(
        ledgers.get("candidate_flags"),
        "ledgers.candidate_flags",
        int(thresholds["min_candidate_flags"]),
    )
    aesthetic_errors, ranked_aesthetic = validate_finding_list(
        ledgers.get("ranked_aesthetic"),
        "ledgers.ranked_aesthetic",
        int(thresholds["min_ranked_aesthetic"]),
        ranked=True,
    )
    issue_errors, explicit_issues = normalize_issue_entries(submission)
    errors.extend(candidate_errors)
    errors.extend(aesthetic_errors)
    errors.extend(issue_errors)

    open_issues = collect_open_review_issues(
        state,
        submission,
        candidate_flags,
        ranked_aesthetic,
        explicit_issues,
    )
    metrics = compute_review_metrics(
        state,
        submission,
        candidate_flags,
        ranked_aesthetic,
        explicit_issues,
        open_issues,
    )
    errors.extend(
        validate_review_metrics_policy(
            state,
            submission,
            candidate_flags,
            ranked_aesthetic,
            explicit_issues,
            metrics,
        )
    )
    if verdict == "pass_for_user_review_pending" and open_issues:
        errors.append("pass verdict cannot include open/revise/blocked findings")
    if verdict in {"revise", "blocked"} and not open_issues:
        errors.append(f"{verdict} verdict must include at least one open issue")

    if errors:
        metrics["accepted"] = False
        metrics["error_count"] = len(errors)
        metrics["errors"] = errors
        append_metrics_record(state_path, state, metrics)
        save_state(
            state_path,
            state,
            {
                "at": utc_now(),
                "type": "review_submission_rejected",
                "verdict": verdict,
                "error_count": len(errors),
                "pardon_count": metrics.get("pardon_count"),
                "pardon_rate": metrics.get("pardon_rate"),
            },
        )
        raise GateError("review submission rejected:\n- " + "\n- ".join(errors))

    accepted_path = state_path.parent / f"accepted_review_round_{int(state.get('round', 1)):02d}.json"
    write_json(accepted_path, submission)
    written_open_issues = write_issue_files(state, open_issues) if open_issues else []
    status = {
        "revise": "revision_required",
        "blocked": "blocked",
        "pass_for_user_review_pending": "pass_for_user_review_pending",
    }[str(verdict)]
    state["status"] = status
    state["last_verdict"] = verdict
    state["last_review_submission"] = relative_to_repo(accepted_path, Path(state["repo_root"]).resolve())
    state["open_issues"] = written_open_issues
    state["fixed_pending_rereview"] = []
    state.setdefault("accepted_reviews", []).append(state["last_review_submission"])
    metrics["accepted"] = True
    metrics["submission"] = state["last_review_submission"]
    metrics["written_open_issue_count"] = len(written_open_issues)
    append_metrics_record(state_path, state, metrics)
    event = {
        "at": utc_now(),
        "type": "review_submission_accepted",
        "verdict": verdict,
        "open_issue_count": len(written_open_issues),
        "pardon_count": metrics.get("pardon_count"),
        "pardon_rate": metrics.get("pardon_rate"),
        "submission": state["last_review_submission"],
    }
    save_state(state_path, state, event)
    print(f"accepted: {state_path}")
    print(f"status: {status}")
    print(f"open_issues: {len(written_open_issues)}")
    return 0


def validate_fix_submission(
    state: dict[str, Any],
    submission: dict[str, Any],
    state_path: Path,
) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    if submission.get("session_id") != state["session_id"]:
        errors.append("session_id does not match gate state")
    open_issues = state.get("open_issues") or []
    if not open_issues:
        errors.append("state has no open issues to fix")
        return errors, []
    fixes = submission.get("fixes")
    if not isinstance(fixes, list):
        errors.append("fixes must be a list")
        return errors, []
    by_issue = {issue["id"]: issue for issue in open_issues}
    submitted: dict[str, dict[str, Any]] = {}
    pardon_count = 0
    for index, fix in enumerate(fixes):
        if not isinstance(fix, dict):
            errors.append(f"fixes[{index}] must be an object")
            continue
        issue_id = fix.get("issue_id")
        if issue_id not in by_issue:
            errors.append(f"fixes[{index}].issue_id is not an open issue: {issue_id!r}")
            continue
        if issue_id in submitted:
            errors.append(f"duplicate fix for issue {issue_id}")
        submitted[str(issue_id)] = fix
        status = fix.get("status")
        if status not in {"fixed", "pardoned"}:
            errors.append(f"fix {issue_id}: status must be fixed or pardoned")
        if not fix.get("after_evidence"):
            errors.append(f"fix {issue_id}: after_evidence is required")
        if status == "pardoned":
            pardon_count += 1
            source_issue = by_issue.get(str(issue_id), {})
            if is_no_pardon_finding(source_issue):
                errors.append(f"fix {issue_id}: no-pardon issue cannot be pardoned")
        if status == "fixed":
            if not fix.get("fix_notes"):
                errors.append(f"fix {issue_id}: fix_notes are required")
            changed_files = fix.get("changed_files")
            if not isinstance(changed_files, list) or not changed_files:
                errors.append(f"fix {issue_id}: changed_files must be a non-empty list")
            else:
                repo_root = Path(state["repo_root"]).resolve()
                episode_dir = (repo_root / state["episode"]).resolve()
                for file_index, value in enumerate(changed_files):
                    if not resolve_existing_path(value, repo_root, episode_dir, state_path.parent):
                        errors.append(f"fix {issue_id}: changed_files[{file_index}] path does not exist")
        if status == "pardoned" and not fix.get("pardon_reason"):
            errors.append(f"fix {issue_id}: pardon_reason is required")
    max_fix_pardons = int(state.get("thresholds", {}).get("max_pardons_for_pass", 0))
    if pardon_count > max_fix_pardons:
        errors.append(
            "abnormal fix pattern: pardon_count "
            f"{pardon_count} exceeds {state['risk_tier']} per-round limit {max_fix_pardons}"
        )
    missing = sorted(set(by_issue) - set(submitted))
    if missing:
        errors.append(f"missing fixes for open issues: {missing}")
    extras = sorted(set(submitted) - set(by_issue))
    if extras:
        errors.append(f"unknown issue fixes submitted: {extras}")

    errors.extend(validate_artifacts(state, submission, state_path, for_fix=True))
    return errors, [submitted[issue_id] for issue_id in sorted(submitted)]


def compute_fix_metrics(
    state: dict[str, Any],
    submission: dict[str, Any],
    normalized_fixes: list[dict[str, Any]],
) -> dict[str, Any]:
    status_counts: dict[str, int] = {"fixed": 0, "pardoned": 0, "other": 0}
    raw_fixes = submission.get("fixes")
    total_submitted = len(raw_fixes) if isinstance(raw_fixes, list) else 0
    for fix in normalized_fixes:
        status = fix.get("status")
        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts["other"] += 1
    return {
        "record_type": "fix",
        "accepted": False,
        "fixer": submission.get("fixer") or state.get("owner"),
        "submitted_fix_count": total_submitted,
        "normalized_fix_count": len(normalized_fixes),
        "status_counts": status_counts,
        "pardon_count": status_counts["pardoned"],
        "pardon_rate": (status_counts["pardoned"] / len(normalized_fixes)) if normalized_fixes else 0.0,
    }


def update_issue_file_from_fix(
    state: dict[str, Any],
    issue: dict[str, Any],
    fix: dict[str, Any],
) -> None:
    issue_file = issue.get("issue_file")
    if not issue_file:
        return
    repo_root = Path(state["repo_root"]).resolve()
    path = repo_root / issue_file
    if not path.exists():
        return
    payload = read_json(path)
    if not isinstance(payload, dict):
        return
    payload["status"] = fix["status"]
    payload["fixed_at"] = utc_now()
    payload["fixed_by"] = fix.get("fixer") or fix.get("owner") or "animation_owner"
    payload["fix_notes"] = fix.get("fix_notes")
    payload["after_evidence"] = fix.get("after_evidence")
    if fix.get("pardon_reason"):
        payload["pardon_reason"] = fix["pardon_reason"]
    write_json(path, payload)


def submit_fix(args: argparse.Namespace) -> int:
    state_path, state = load_state(args.session)
    submission = read_json(Path(args.input))
    errors, normalized_fixes = validate_fix_submission(state, submission, state_path)
    metrics = compute_fix_metrics(state, submission, normalized_fixes)
    if errors:
        metrics["accepted"] = False
        metrics["error_count"] = len(errors)
        metrics["errors"] = errors
        append_metrics_record(state_path, state, metrics)
        save_state(
            state_path,
            state,
            {
                "at": utc_now(),
                "type": "fix_submission_rejected",
                "error_count": len(errors),
                "pardon_count": metrics.get("pardon_count"),
                "pardon_rate": metrics.get("pardon_rate"),
            },
        )
        raise GateError("fix submission rejected:\n- " + "\n- ".join(errors))

    open_by_id = {issue["id"]: issue for issue in state.get("open_issues", [])}
    for fix in normalized_fixes:
        update_issue_file_from_fix(state, open_by_id[fix["issue_id"]], fix)

    accepted_path = state_path.parent / f"accepted_fix_round_{int(state.get('round', 1)):02d}.json"
    write_json(accepted_path, submission)
    state["status"] = "ready_for_rereview"
    state["fixed_pending_rereview"] = state.get("open_issues", [])
    state["open_issues"] = []
    state["round"] = int(state.get("round", 1)) + 1
    state["last_fix_submission"] = relative_to_repo(accepted_path, Path(state["repo_root"]).resolve())
    state.setdefault("accepted_fixes", []).append(state["last_fix_submission"])
    metrics["accepted"] = True
    metrics["submission"] = state["last_fix_submission"]
    append_metrics_record(state_path, state, metrics)
    event = {
        "at": utc_now(),
        "type": "fix_submission_accepted",
        "fixed_issue_count": len(normalized_fixes),
        "pardon_count": metrics.get("pardon_count"),
        "pardon_rate": metrics.get("pardon_rate"),
        "submission": state["last_fix_submission"],
    }
    save_state(state_path, state, event)
    print(f"accepted: {state_path}")
    print("status: ready_for_rereview")
    print(f"fixed_pending_rereview: {len(state['fixed_pending_rereview'])}")
    return 0


def status(args: argparse.Namespace) -> int:
    state_path, state = load_state(args.session)
    if args.json:
        json.dump(state, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        print()
    else:
        print(f"state: {state_path}")
        print(f"session: {state['session_id']}")
        print(f"status: {state['status']}")
        print(f"round: {state.get('round')}")
        print(f"risk_tier: {state.get('risk_tier')}")
        print(f"required_documents: {len(state.get('required_documents', []))}")
        print(f"open_issues: {len(state.get('open_issues', []))}")
        print(f"fixed_pending_rereview: {len(state.get('fixed_pending_rereview', []))}")
        print(f"session_metrics: {state_path.parent / 'review_metrics.jsonl'}")
        print(
            "episode_metrics: "
            f"{Path(state['repo_root']).resolve() / state['episode'] / 'review' / 'gate' / 'review_metrics.jsonl'}"
        )
        if state.get("last_verdict"):
            print(f"last_verdict: {state['last_verdict']}")
        history = state.get("metrics_history") or []
        if history:
            last = history[-1]
            print(
                "last_metrics: "
                f"type={last.get('record_type')} accepted={last.get('accepted')} "
                f"pardon_count={last.get('pardon_count')} "
                f"pardon_rate={float(last.get('pardon_rate') or 0):.3f}"
            )
    if args.require_pass and state.get("status") != "pass_for_user_review_pending":
        raise GateError(
            "gate has not passed; expected status pass_for_user_review_pending, "
            f"got {state.get('status')}"
        )
    return 0


def print_metrics(args: argparse.Namespace) -> int:
    state_path, state = load_state(args.session)
    metrics_path = state_path.parent / "review_metrics.jsonl"
    records: list[dict[str, Any]] = []
    if metrics_path.exists():
        for line in metrics_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    if args.json:
        json.dump(records, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        print()
        return 0

    print(f"session: {state['session_id']}")
    print(f"metrics_file: {metrics_path}")
    print(f"records: {len(records)}")
    review_records = [item for item in records if str(item.get("record_type", "")).endswith("review")]
    fix_records = [item for item in records if str(item.get("record_type", "")).endswith("fix")]
    rejected = [item for item in records if item.get("accepted") is False]
    print(f"review_records: {len(review_records)}")
    print(f"fix_records: {len(fix_records)}")
    print(f"rejected_records: {len(rejected)}")
    for item in records:
        print(
            f"- round={item.get('round')} type={item.get('record_type')} "
            f"accepted={item.get('accepted')} verdict={item.get('verdict', '')} "
            f"findings={item.get('total_finding_count', item.get('normalized_fix_count', ''))} "
            f"open={item.get('open_issue_count', '')} "
            f"pardons={item.get('pardon_count')} "
            f"rate={float(item.get('pardon_rate') or 0):.3f}"
        )
        for error in item.get("errors") or []:
            print(f"  reject_reason: {error}")
    return 0


def backfill_metrics(args: argparse.Namespace) -> int:
    state_path, state = load_state(args.session)
    metrics_path = state_path.parent / "review_metrics.jsonl"
    if metrics_path.exists() and metrics_path.stat().st_size > 0 and not args.force:
        raise GateError(f"metrics file already exists; use --force to append backfill records: {metrics_path}")

    repo_root = Path(state["repo_root"]).resolve()
    records_written = 0
    for review_ref in state.get("accepted_reviews", []):
        path = repo_root / review_ref
        if not path.exists():
            continue
        submission = read_json(path)
        ledgers = submission.get("ledgers") if isinstance(submission.get("ledgers"), dict) else {}
        _, candidate_flags = validate_finding_list(
            ledgers.get("candidate_flags", []),
            "ledgers.candidate_flags",
            0,
        )
        _, ranked_aesthetic = validate_finding_list(
            ledgers.get("ranked_aesthetic", []),
            "ledgers.ranked_aesthetic",
            0,
            ranked=True,
        )
        _, explicit_issues = normalize_issue_entries(submission)
        open_issues = collect_open_review_issues(
            state,
            submission,
            candidate_flags,
            ranked_aesthetic,
            explicit_issues,
        )
        metrics = compute_review_metrics(
            state,
            submission,
            candidate_flags,
            ranked_aesthetic,
            explicit_issues,
            open_issues,
        )
        metrics["record_type"] = "backfill_review"
        metrics["accepted"] = True
        metrics["submission"] = review_ref
        append_metrics_record(state_path, state, metrics)
        records_written += 1

    for fix_ref in state.get("accepted_fixes", []):
        path = repo_root / fix_ref
        if not path.exists():
            continue
        submission = read_json(path)
        fixes = submission.get("fixes") if isinstance(submission.get("fixes"), list) else []
        normalized = [fix for fix in fixes if isinstance(fix, dict)]
        metrics = compute_fix_metrics(state, submission, normalized)
        metrics["record_type"] = "backfill_fix"
        metrics["accepted"] = True
        metrics["submission"] = fix_ref
        append_metrics_record(state_path, state, metrics)
        records_written += 1

    save_state(
        state_path,
        state,
        {
            "at": utc_now(),
            "type": "metrics_backfilled",
            "records_written": records_written,
        },
    )
    print(f"records_written: {records_written}")
    print(f"metrics_file: {metrics_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Suspicion-first review gate for myLectures animation segments."
    )
    parser.add_argument("--repo-root", default=".", help="repository root, default: current directory")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create a review gate session")
    init.add_argument("--episode", required=True, help="episode directory, relative to repo root")
    init.add_argument("--scene-slug", required=True)
    init.add_argument("--review-id", required=True)
    init.add_argument("--owner", required=True)
    init.add_argument("--reviewer", required=True)
    init.add_argument("--risk-tier", choices=sorted(RISK_TIERS), default="normal")
    init.add_argument("--session-id")
    init.add_argument("--state-root", help="override session parent directory")
    init.add_argument("--force", action="store_true", help="overwrite an existing state.json")
    init.set_defaults(func=init_session)

    checklist_cmd = sub.add_parser("checklist", help="print required docs and quotas")
    checklist_cmd.add_argument("--session", required=True)
    checklist_cmd.set_defaults(func=print_checklist)

    confirm = sub.add_parser("confirm-read", help="interactively confirm every required document")
    confirm.add_argument("--session", required=True)
    confirm.add_argument("--reviewer", required=True)
    confirm.set_defaults(func=confirm_read)

    review_template = sub.add_parser("template-review", help="print a review submission template")
    review_template.add_argument("--session", required=True)
    review_template.set_defaults(func=template_review)

    review_submit = sub.add_parser("submit-review", help="validate and accept a review submission")
    review_submit.add_argument("--session", required=True)
    review_submit.add_argument("--input", required=True, help="review submission JSON")
    review_submit.set_defaults(func=submit_review)

    fix_template = sub.add_parser("template-fix", help="print a fix submission template")
    fix_template.add_argument("--session", required=True)
    fix_template.set_defaults(func=template_fix)

    fix_submit = sub.add_parser("submit-fix", help="validate and accept a fix submission")
    fix_submit.add_argument("--session", required=True)
    fix_submit.add_argument("--input", required=True, help="fix submission JSON")
    fix_submit.set_defaults(func=submit_fix)

    status_cmd = sub.add_parser("status", help="print gate state")
    status_cmd.add_argument("--session", required=True)
    status_cmd.add_argument("--json", action="store_true")
    status_cmd.add_argument("--require-pass", action="store_true")
    status_cmd.set_defaults(func=status)

    metrics_cmd = sub.add_parser("metrics", help="print persisted review/fix quality metrics")
    metrics_cmd.add_argument("--session", required=True)
    metrics_cmd.add_argument("--json", action="store_true")
    metrics_cmd.set_defaults(func=print_metrics)

    backfill_cmd = sub.add_parser("backfill-metrics", help="append metrics records for prior accepted reviews/fixes")
    backfill_cmd.add_argument("--session", required=True)
    backfill_cmd.add_argument("--force", action="store_true")
    backfill_cmd.set_defaults(func=backfill_metrics)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except GateError as exc:
        print(f"review_gate: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
