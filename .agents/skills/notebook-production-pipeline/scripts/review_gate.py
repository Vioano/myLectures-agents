#!/usr/bin/env python3
"""Hard review gate for myLectures PowerPack notebooks."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = "notebook-review-gate-v1"

CORE_REQUIRED_DOCS = [
    "SKILL.md",
    "references/20-problem-driven-interactive-notebooks.md",
    "references/21-exam-and-concept-alignment.md",
    "references/22-exercise-taste-and-red-flags.md",
    "references/23-feedback-hint-and-solution-design.md",
    "references/30-interaction-and-style.md",
    "references/40-qc-and-review-gate.md",
    "references/41-output-contract.md",
    "references/42-notebook-contract-and-composer.md",
    "references/43-review-red-flag-rubric.md",
    "references/50-known-failures-and-fixes.md",
]

ABSTRACT_STANDARD_KEYS = [
    "course_object_alignment_failure",
    "problem_driven_design_failure",
    "exam_alignment_failure",
    "feedback_design_failure",
    "cell_modality_failure",
    "pattern_card_failure",
    "demo_gallery_failure",
    "mathematical_causality_failure",
    "interaction_stability_failure",
    "output_hygiene_failure",
    "presentation_boundary_failure",
    "source_boundary_failure",
    "review_gate_bypass_failure",
]

INSPECTION_KEYS = [
    "checked_notebook_source",
    "checked_executed_outputs",
    "checked_auto_audit",
    "checked_interactions_or_static_fallback",
    "checked_exercise_quality",
    "checked_problem_driven_structure",
    "checked_exam_alignment",
    "checked_feedback_design",
    "checked_cell_modality",
    "checked_pattern_cards_or_not_applicable",
    "checked_regression_records",
    "checked_authoring_preflight",
]

RISK_TIERS = {
    "low": {"min_candidate_flags": 0, "min_ranked_quality": 1},
    "normal": {"min_candidate_flags": 5, "min_ranked_quality": 3},
    "interactive": {"min_candidate_flags": 8, "min_ranked_quality": 4},
    "human-rejected": {"min_candidate_flags": 12, "min_ranked_quality": 5},
    "repeat-rejected": {"min_candidate_flags": 18, "min_ranked_quality": 7},
}

RISK_TIER_ORDER = ["low", "normal", "interactive", "human-rejected", "repeat-rejected"]

FLAG_STATUSES = {"open", "fixed", "pardoned", "not_applicable"}
PASS_VERDICT = "pass_for_user_review_pending"
NONPASS_VERDICTS = {"revise", "blocked"}


class GateError(RuntimeError):
    pass


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def abs_path(value: str | Path, base: Path | None = None) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (base or Path.cwd()) / path
    return path.resolve()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        raise GateError(f"Invalid JSON in {path}: {exc}") from exc


def is_filesystem_metadata(path: Path) -> bool:
    return path.name.startswith("._") or path.name == ".DS_Store"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_event(state: dict[str, Any], event: str, details: dict[str, Any]) -> None:
    event_path = Path(state["events_path"])
    payload = {"time": now(), "event": event, **details}
    event_path.parent.mkdir(parents=True, exist_ok=True)
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def load_state(path: Path) -> dict[str, Any]:
    state = read_json(path)
    if state.get("schema") != SCHEMA:
        raise GateError(f"State schema mismatch in {path}: {state.get('schema')}")
    state["_state_path"] = str(path)
    return state


def save_state(state: dict[str, Any]) -> None:
    state_path = Path(state["_state_path"])
    clean = {key: value for key, value in state.items() if not key.startswith("_")}
    write_json(state_path, clean)


def doc_record(path: Path, kind: str) -> dict[str, str]:
    return {
        "path": str(path),
        "sha256": sha256(path),
        "kind": kind,
    }


def collect_required_docs(episode_dir: Path) -> list[dict[str, str]]:
    root = skill_dir()
    docs: list[dict[str, str]] = []
    for rel in CORE_REQUIRED_DOCS:
        path = root / rel
        if not path.exists():
            raise GateError(f"Missing required skill document: {path}")
        docs.append(doc_record(path, "skill_reference"))

    review_dir = episode_dir / "review"
    feedback_patterns = [
        ("human_feedback", "human-feedback/**/*.md"),
        ("agent_feedback", "agent-feedback/**/*.md"),
        ("issue_json", "issues/*.json"),
    ]
    if review_dir.exists():
        for kind, pattern in feedback_patterns:
            for path in sorted(review_dir.glob(pattern)):
                if path.is_file() and not is_filesystem_metadata(path):
                    docs.append(doc_record(path, kind))
    return docs


def min_risk_tier_from_episode(episode_dir: Path, requested: str) -> str:
    review_dir = episode_dir / "review"
    if not review_dir.exists():
        return requested
    has_human_feedback = any(
        path.is_file() and not is_filesystem_metadata(path)
        for path in (review_dir / "human-feedback").glob("**/*.md")
    )
    has_repeat_rejection = False
    for issue_path in (review_dir / "issues").glob("*.json"):
        if is_filesystem_metadata(issue_path):
            continue
        try:
            issue = read_json(issue_path)
        except GateError:
            continue
        source = issue.get("source")
        status = str(issue.get("status", "")).lower()
        if source == "human_review" or issue.get("must_check_in_future") is True:
            has_human_feedback = True
        if status in {"repeat_rejected", "reopened", "blocked"}:
            has_repeat_rejection = True
    minimum = "repeat-rejected" if has_repeat_rejection else "human-rejected" if has_human_feedback else requested
    return max([requested, minimum], key=RISK_TIER_ORDER.index)


def make_template(state: dict[str, Any]) -> dict[str, Any]:
    thresholds = state["thresholds"]
    return {
        "schema": "notebook-review-v1",
        "review_id": state["review_id"],
        "risk_tier": state["risk_tier"],
        "minimum_risk_tier": state.get("minimum_risk_tier", state["risk_tier"]),
        "risk_tier_downgrade_reason": "",
        "verdict": "revise",
        "read_confirmations": [
            {
                "path": doc["path"],
                "sha256": doc["sha256"],
                "summary": "",
            }
            for doc in state["required_docs"]
        ],
        "artifacts": {
            "notebook": state["notebook"],
            "executed_notebook": state["notebook"],
            "auto_audit_json": "",
            "review_report": "",
            "audit_not_applicable_reason": "",
        },
        "reviewer_independence": {
            "owner": state["owner"],
            "reviewer": state["reviewer"],
            "mode": "",
            "evidence": "",
            "subagent_session": "",
            "same_agent_exception_reason": "",
        },
        "inspection": {key: False for key in INSPECTION_KEYS},
        "abstract_standards": [
            {"standard_key": key, "status": "checked", "evidence": ""}
            for key in ABSTRACT_STANDARD_KEYS
        ],
        "regressions": [
            {"source_path": doc["path"], "checked": False, "evidence": ""}
            for doc in state["required_docs"]
            if doc["kind"] in {"human_feedback", "agent_feedback", "issue_json"}
        ],
        "candidate_flags": [
            {
                "id": f"{state['review_id']}-flag-{index + 1:02d}",
                "standard_key": "",
                "pattern_key": "",
                "severity": "",
                "evidence": "",
                "impact": "",
                "suggested_fix": "",
                "status": "open",
                "resolution_evidence": "",
                "pardon_reason": "",
            }
            for index in range(thresholds["min_candidate_flags"])
        ],
        "ranked_notebook_quality": [
            {
                "rank": index + 1,
                "title": "",
                "evidence": "",
                "status": "open",
                "resolution_evidence": "",
                "pardon_reason": "",
            }
            for index in range(thresholds["min_ranked_quality"])
        ],
        "issues": [],
        "notes": "",
    }


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def path_exists(value: str, base: Path | None = None) -> bool:
    if not nonempty(value):
        return False
    return abs_path(value, base).exists()


def load_audit_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if "status" in payload and "results" in payload:
        return payload
    if "status" in payload and "path" in payload:
        return {"status": payload["status"], "results": [payload]}
    if isinstance(payload, list):
        status = "pass"
        for result in payload:
            if result.get("status") == "blocked":
                status = "blocked"
                break
            if result.get("status") == "revise":
                status = "revise"
        return {"status": status, "results": payload}
    raise GateError(f"Unrecognized audit JSON shape: {path}")


def result_path_candidates(result: dict[str, Any], repo_root: Path) -> set[str]:
    candidates: set[str] = set()
    for key in ("absolute_path", "path"):
        value = result.get(key)
        if not nonempty(value):
            continue
        path = Path(value)
        if path.is_absolute():
            candidates.add(str(path.resolve()))
        else:
            candidates.add(str((repo_root / path).resolve()))
            candidates.add(str((Path.cwd() / path).resolve()))
    return candidates


def validate_read_confirmations(state: dict[str, Any], review: dict[str, Any], errors: list[str]) -> None:
    confirmations = review.get("read_confirmations", [])
    by_path = {str(abs_path(item.get("path", ""))): item for item in confirmations if item.get("path")}
    for doc in state["required_docs"]:
        key = str(abs_path(doc["path"]))
        item = by_path.get(key)
        if not item:
            errors.append(f"Missing read confirmation for {doc['path']}")
            continue
        if item.get("sha256") != doc["sha256"]:
            errors.append(f"SHA-256 mismatch for read confirmation: {doc['path']}")
        if not nonempty(item.get("summary")):
            errors.append(f"Read confirmation needs a summary: {doc['path']}")


def validate_artifacts(state: dict[str, Any], review: dict[str, Any], pass_requested: bool, errors: list[str]) -> None:
    artifacts = review.get("artifacts", {})
    notebook = artifacts.get("notebook") or state["notebook"]
    if str(abs_path(notebook)) != str(abs_path(state["notebook"])):
        errors.append("Artifact notebook path must match the gate target notebook")
    if not path_exists(notebook):
        errors.append(f"Notebook artifact does not exist: {notebook}")

    if pass_requested:
        if not path_exists(artifacts.get("review_report", "")):
            errors.append("Passing review requires an existing artifacts.review_report")
        audit_path = artifacts.get("auto_audit_json", "")
        if not path_exists(audit_path):
            errors.append("Passing review requires an existing artifacts.auto_audit_json")
        if path_exists(audit_path):
            try:
                audit_payload = load_audit_payload(abs_path(audit_path))
            except GateError as exc:
                errors.append(str(exc))
            else:
                if audit_payload.get("status") != "pass":
                    errors.append(
                        f"Passing review requires auto audit status pass; got {audit_payload.get('status')}"
                    )
                target = str(abs_path(state["notebook"]))
                repo_root = abs_path(state["repo_root"])
                target_results = [
                    result for result in audit_payload.get("results", [])
                    if target in result_path_candidates(result, repo_root)
                ]
                if not target_results:
                    errors.append("Auto audit JSON does not include the gate target notebook")
                else:
                    current_hash = sha256(abs_path(state["notebook"]))
                    for result in target_results:
                        if result.get("notebook_sha256") != current_hash:
                            errors.append("Auto audit JSON is stale: notebook_sha256 does not match current target notebook")


def validate_reviewer_independence(
    state: dict[str, Any], review: dict[str, Any], pass_requested: bool, errors: list[str]
) -> None:
    info = review.get("reviewer_independence", {})
    if not pass_requested:
        return
    if info.get("owner") != state["owner"]:
        errors.append("reviewer_independence.owner must match gate owner")
    if info.get("reviewer") != state["reviewer"]:
        errors.append("reviewer_independence.reviewer must match gate reviewer")
    mode = info.get("mode")
    if mode not in {"subagent", "independent_pass", "human_review"}:
        errors.append("Passing review requires reviewer_independence.mode: subagent, independent_pass, or human_review")
    if not nonempty(info.get("evidence")):
        errors.append("Passing review requires reviewer_independence.evidence")
    if state["risk_tier"] in {"human-rejected", "repeat-rejected"}:
        if state["owner"] == state["reviewer"] and not nonempty(info.get("same_agent_exception_reason")):
            errors.append("Human-rejected gates require a reviewer distinct from owner, or a same_agent_exception_reason")
        if mode == "subagent" and not nonempty(info.get("subagent_session")):
            errors.append("Subagent review mode requires reviewer_independence.subagent_session")


def validate_inspection(review: dict[str, Any], errors: list[str]) -> None:
    inspection = review.get("inspection", {})
    for key in INSPECTION_KEYS:
        if inspection.get(key) is not True:
            errors.append(f"Inspection item is not confirmed: {key}")


def validate_abstract_standards(review: dict[str, Any], errors: list[str]) -> None:
    rows = review.get("abstract_standards", [])
    by_key = {row.get("standard_key"): row for row in rows}
    for key in ABSTRACT_STANDARD_KEYS:
        row = by_key.get(key)
        if not row:
            errors.append(f"Missing abstract standard coverage: {key}")
        elif not nonempty(row.get("evidence")):
            errors.append(f"Abstract standard needs evidence: {key}")


def validate_regressions(state: dict[str, Any], review: dict[str, Any], errors: list[str]) -> None:
    required = [
        doc["path"]
        for doc in state["required_docs"]
        if doc["kind"] in {"human_feedback", "agent_feedback", "issue_json"}
    ]
    rows = review.get("regressions", [])
    by_path = {str(abs_path(row.get("source_path", ""))): row for row in rows if row.get("source_path")}
    for path in required:
        row = by_path.get(str(abs_path(path)))
        if not row:
            errors.append(f"Missing regression check for {path}")
        elif row.get("checked") is not True or not nonempty(row.get("evidence")):
            errors.append(f"Regression check needs checked=true and evidence: {path}")


def validate_candidate_flags(
    state: dict[str, Any], review: dict[str, Any], pass_requested: bool, errors: list[str]
) -> None:
    flags = review.get("candidate_flags", [])
    threshold = state["thresholds"]["min_candidate_flags"]
    if len(flags) < threshold:
        errors.append(f"Need at least {threshold} candidate flags; found {len(flags)}")

    seen_ids: set[str] = set()
    for index, flag in enumerate(flags, start=1):
        flag_id = flag.get("id") or f"candidate_flags[{index}]"
        if flag_id in seen_ids:
            errors.append(f"Duplicate candidate flag id: {flag_id}")
        seen_ids.add(flag_id)
        status = flag.get("status")
        if status not in FLAG_STATUSES:
            errors.append(f"{flag_id} has invalid status: {status}")
        if flag.get("standard_key") not in ABSTRACT_STANDARD_KEYS:
            errors.append(f"{flag_id} has missing or unknown standard_key")
        for key in ["evidence", "impact", "suggested_fix"]:
            if not nonempty(flag.get(key)):
                errors.append(f"{flag_id} needs {key}")
        if status == "fixed" and not nonempty(flag.get("resolution_evidence")):
            errors.append(f"{flag_id} fixed status needs resolution_evidence")
        if status == "pardoned" and not nonempty(flag.get("pardon_reason")):
            errors.append(f"{flag_id} pardoned status needs pardon_reason")
        if pass_requested and status == "open":
            errors.append(f"Passing review cannot have open candidate flag: {flag_id}")


def validate_ranked_quality(review: dict[str, Any], state: dict[str, Any], pass_requested: bool, errors: list[str]) -> None:
    rows = review.get("ranked_notebook_quality", [])
    threshold = state["thresholds"]["min_ranked_quality"]
    if len(rows) < threshold:
        errors.append(f"Need at least {threshold} ranked notebook-quality items; found {len(rows)}")
    expected_rank = 1
    for row in sorted(rows, key=lambda item: item.get("rank", 9999)):
        label = f"ranked_notebook_quality[{row.get('rank', '?')}]"
        if row.get("rank") != expected_rank:
            errors.append(f"Ranked quality items must be contiguous from 1; expected {expected_rank}")
            expected_rank += 1
            continue
        expected_rank += 1
        if not nonempty(row.get("title")) or not nonempty(row.get("evidence")):
            errors.append(f"{label} needs title and evidence")
        status = row.get("status")
        if status not in FLAG_STATUSES:
            errors.append(f"{label} has invalid status: {status}")
        if status == "fixed" and not nonempty(row.get("resolution_evidence")):
            errors.append(f"{label} fixed status needs resolution_evidence")
        if status == "pardoned":
            if not nonempty(row.get("pardon_reason")):
                errors.append(f"{label} pardoned status needs pardon_reason")
            if not nonempty(row.get("resolution_evidence")):
                errors.append(f"{label} pardoned status needs resolution_evidence")
        if status == "not_applicable" and not nonempty(row.get("resolution_evidence")):
            errors.append(f"{label} not_applicable status needs resolution_evidence")
        if pass_requested and status == "open":
            errors.append(f"Passing review cannot have open ranked quality item: {label}")


def validate_review(state: dict[str, Any], review: dict[str, Any]) -> tuple[bool, list[str], bool]:
    errors: list[str] = []
    verdict = review.get("verdict")
    if verdict not in {PASS_VERDICT, *NONPASS_VERDICTS}:
        errors.append(
            f"verdict must be {PASS_VERDICT!r}, 'revise', or 'blocked'; got {verdict!r}"
        )
    pass_requested = verdict == PASS_VERDICT

    if review.get("review_id") != state["review_id"]:
        errors.append("review_id does not match gate state")
    if review.get("risk_tier") != state["risk_tier"]:
        errors.append("risk_tier does not match gate state")
    if RISK_TIER_ORDER.index(state["risk_tier"]) < RISK_TIER_ORDER.index(state.get("minimum_risk_tier", state["risk_tier"])):
        errors.append("risk_tier is below minimum_risk_tier derived from episode feedback")

    validate_read_confirmations(state, review, errors)
    validate_artifacts(state, review, pass_requested, errors)
    validate_reviewer_independence(state, review, pass_requested, errors)
    validate_inspection(review, errors)
    validate_abstract_standards(review, errors)
    validate_regressions(state, review, errors)
    validate_candidate_flags(state, review, pass_requested, errors)
    validate_ranked_quality(review, state, pass_requested, errors)

    return not errors and pass_requested, errors, pass_requested


def command_init(args: argparse.Namespace) -> int:
    repo_root = abs_path(args.repo_root)
    notebook = abs_path(args.notebook)
    if args.risk_tier not in RISK_TIERS:
        raise GateError(f"Unknown risk tier {args.risk_tier!r}. Choose one of {sorted(RISK_TIERS)}")
    if not notebook.exists():
        raise GateError(f"Notebook does not exist: {notebook}")

    episode_dir = abs_path(args.episode_dir) if args.episode_dir else notebook.parent
    requested_risk_tier = args.risk_tier
    effective_risk_tier = min_risk_tier_from_episode(episode_dir, requested_risk_tier)
    state_dir = abs_path(args.state_root) if args.state_root else episode_dir / "review" / "gate" / args.review_id
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "state.json"

    state = {
        "schema": SCHEMA,
        "created_at": now(),
        "updated_at": now(),
        "repo_root": str(repo_root),
        "notebook": str(notebook),
        "episode_dir": str(episode_dir),
        "review_id": args.review_id,
        "risk_tier": effective_risk_tier,
        "requested_risk_tier": requested_risk_tier,
        "minimum_risk_tier": effective_risk_tier,
        "thresholds": RISK_TIERS[effective_risk_tier],
        "owner": args.owner,
        "reviewer": args.reviewer,
        "state_dir": str(state_dir),
        "events_path": str(state_dir / "events.jsonl"),
        "required_docs": collect_required_docs(episode_dir),
        "status": "initialized",
        "last_review": None,
        "_state_path": str(state_path),
    }
    save_state(state)
    append_event(state, "init", {"state": str(state_path)})
    print(str(state_path))
    return 0


def command_checklist(args: argparse.Namespace) -> int:
    state = load_state(abs_path(args.state))
    print(f"Review gate: {state['review_id']}")
    print(f"Notebook: {state['notebook']}")
    print(f"Risk tier: {state['risk_tier']} {state['thresholds']}")
    print("\nRequired readings:")
    for doc in state["required_docs"]:
        print(f"- [{doc['kind']}] {doc['path']} sha256={doc['sha256']}")
    print("\nInspection keys:")
    for key in INSPECTION_KEYS:
        print(f"- {key}")
    print("\nAbstract standards:")
    for key in ABSTRACT_STANDARD_KEYS:
        print(f"- {key}")
    return 0


def command_template_review(args: argparse.Namespace) -> int:
    state = load_state(abs_path(args.state))
    print(json.dumps(make_template(state), ensure_ascii=False, indent=2))
    return 0


def command_submit_review(args: argparse.Namespace) -> int:
    state_path = abs_path(args.state)
    state = load_state(state_path)
    review_path = abs_path(args.review_json)
    review = read_json(review_path)
    passed, errors, pass_requested = validate_review(state, review)

    review_copy = Path(state["state_dir"]) / "review.json"
    write_json(review_copy, review)
    state["updated_at"] = now()
    state["last_review"] = {
        "path": str(review_copy),
        "submitted_from": str(review_path),
        "time": now(),
        "verdict": review.get("verdict"),
        "pass_requested": pass_requested,
        "passed": passed,
        "errors": errors,
    }
    state["status"] = "passed" if passed else "revision_required"
    save_state(state)
    append_event(state, "submit-review", state["last_review"])

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"Review gate status: {state['status']}")
    return 0


def command_template_fix(args: argparse.Namespace) -> int:
    state = load_state(abs_path(args.state))
    template = {
        "schema": "notebook-review-fix-v1",
        "review_id": state["review_id"],
        "fix_id": "",
        "time": now(),
        "fixed_flags": [
            {
                "id": "",
                "status": "fixed",
                "evidence": "",
                "paths": [],
                "commands": [],
            }
        ],
        "notes": "",
    }
    print(json.dumps(template, ensure_ascii=False, indent=2))
    return 0


def command_submit_fix(args: argparse.Namespace) -> int:
    state = load_state(abs_path(args.state))
    fix_path = abs_path(args.fix_json)
    fix = read_json(fix_path)
    if fix.get("review_id") != state["review_id"]:
        raise GateError("fix review_id does not match gate state")
    if not nonempty(fix.get("fix_id")):
        raise GateError("fix_id is required")
    rows = fix.get("fixed_flags", [])
    if not isinstance(rows, list) or not rows:
        raise GateError("fixed_flags must be a non-empty list")
    last_review = state.get("last_review") or {}
    last_review_path = last_review.get("path")
    required_open_ids: set[str] = set()
    if last_review_path and Path(last_review_path).exists():
        review = read_json(Path(last_review_path))
        for flag in review.get("candidate_flags", []):
            if flag.get("status") == "open" and not nonempty(flag.get("id")):
                raise GateError("last review contains an open candidate flag without id")
            if flag.get("status") == "open" and nonempty(flag.get("id")):
                required_open_ids.add(flag["id"])
        for row in review.get("ranked_notebook_quality", []):
            if row.get("status") == "open":
                required_open_ids.add(f"ranked_notebook_quality[{row.get('rank')}]")
        for issue in review.get("issues", []):
            if issue.get("status") == "open" and not nonempty(issue.get("id")):
                raise GateError("last review contains an open issue without id")
            if issue.get("status") == "open" and nonempty(issue.get("id")):
                required_open_ids.add(issue["id"])
    issue_dir = Path(state["episode_dir"]) / "review" / "issues"
    if issue_dir.exists():
        for issue_path in issue_dir.glob("*.json"):
            if is_filesystem_metadata(issue_path):
                continue
            try:
                issue = read_json(issue_path)
            except GateError:
                continue
            if issue.get("status") == "open":
                if not nonempty(issue.get("id")):
                    raise GateError(f"open external issue lacks id: {issue_path}")
                required_open_ids.add(issue["id"])
    submitted_ids: set[str] = set()
    for row in rows:
        if not nonempty(row.get("id")) or not nonempty(row.get("evidence")):
            raise GateError("each fixed flag needs id and evidence")
        if row.get("status") not in {"fixed", "pardoned", "not_applicable"}:
            raise GateError("each fixed flag status must be fixed, pardoned, or not_applicable")
        if row.get("status") == "pardoned" and not nonempty(row.get("pardon_reason")):
            raise GateError("pardoned fixed flag needs pardon_reason")
        submitted_ids.add(row["id"])
    missing = sorted(required_open_ids - submitted_ids)
    if missing:
        raise GateError(f"submit-fix must address every open item from last review: {missing}")

    fix_dir = Path(state["state_dir"]) / "fixes"
    fix_dir.mkdir(parents=True, exist_ok=True)
    fix_copy = fix_dir / f"{fix['fix_id']}.json"
    write_json(fix_copy, fix)
    state["updated_at"] = now()
    state.setdefault("fixes", []).append(str(fix_copy))
    if state.get("status") != "passed":
        state["status"] = "fix_submitted"
    save_state(state)
    append_event(state, "submit-fix", {"path": str(fix_copy), "fix_id": fix["fix_id"]})
    print(str(fix_copy))
    return 0


def command_status(args: argparse.Namespace) -> int:
    state = load_state(abs_path(args.state))
    print(f"Review gate status: {state['status']}")
    last = state.get("last_review")
    if last:
        print(f"Last verdict: {last.get('verdict')}")
        print(f"Passed: {last.get('passed')}")
        errors = last.get("errors") or []
        if errors:
            print("Errors:")
            for error in errors:
                print(f"- {error}")
    if args.require_pass and state.get("status") != "passed":
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create a notebook review-gate state")
    init.add_argument("--repo-root", required=True)
    init.add_argument("--notebook", required=True)
    init.add_argument("--episode-dir")
    init.add_argument("--review-id", required=True)
    init.add_argument("--risk-tier", default="normal", choices=sorted(RISK_TIERS))
    init.add_argument("--owner", required=True)
    init.add_argument("--reviewer", required=True)
    init.add_argument("--state-root")
    init.set_defaults(func=command_init)

    checklist = sub.add_parser("checklist", help="Print required readings and checks")
    checklist.add_argument("--state", required=True)
    checklist.set_defaults(func=command_checklist)

    template_review = sub.add_parser("template-review", help="Emit a review JSON template")
    template_review.add_argument("--state", required=True)
    template_review.set_defaults(func=command_template_review)

    submit_review = sub.add_parser("submit-review", help="Validate and store a review JSON")
    submit_review.add_argument("--state", required=True)
    submit_review.add_argument("--review-json", required=True)
    submit_review.set_defaults(func=command_submit_review)

    template_fix = sub.add_parser("template-fix", help="Emit a fix JSON template")
    template_fix.add_argument("--state", required=True)
    template_fix.set_defaults(func=command_template_fix)

    submit_fix = sub.add_parser("submit-fix", help="Store fix evidence")
    submit_fix.add_argument("--state", required=True)
    submit_fix.add_argument("--fix-json", required=True)
    submit_fix.set_defaults(func=command_submit_fix)

    status = sub.add_parser("status", help="Show gate status")
    status.add_argument("--state", required=True)
    status.add_argument("--require-pass", action="store_true")
    status.set_defaults(func=command_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except GateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
