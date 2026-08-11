"""Episode-level readiness, portability, and compact handoff operations."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Iterable
import wave

from .core import PipelineError, object_hash, utc_now
from .presentation_boundary import presentation_boundary_violation
from .screen_text_registration import validate_screen_text_contract_registration
from .storage import load_json, write_json


TEXT_SUFFIXES = {
    ".ass",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".sh",
    ".srt",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
WORKTREE_REFERENCE = re.compile(
    r"(?:/Volumes/[^/\s]+/)?myLectures-worktrees/[^\"'\s)>\]}]+"
)
TOKEN_PATTERN = re.compile(r"[\u3400-\u9fff]|[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:\.\d+)?")
SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;])\s*|\n{2,}")
SRT_TIMESTAMP = re.compile(
    r"(?m)^\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+"
    r"\d{2}:\d{2}:\d{2},\d{3}\s*$"
)
# Keep episode-level readiness inventory in lockstep with the execution-side
# screen-text scanner.  The scoped scene snapshots use project wrappers such
# as ``formula`` and ``label``; treating only bare Text/MarkupText calls as
# visible text silently produced an empty inventory and made the formal
# registry appear stale.  Wrapper payloads are always their first argument;
# style/position arguments are not learner-facing text.
VISIBLE_TEXT_CONSTRUCTORS = {
    "Text",
    "MarkupText",
    "Paragraph",
    "Tex",
    "MathTex",
    "DecimalNumber",
    "Integer",
    "math_tex",
    "role_formula",
    "formula",
    "label",
    "cn_text",
}
VISIBLE_TEXT_WRAPPERS = {
    "math_tex",
    "role_formula",
    "formula",
    "label",
    "cn_text",
}
DEFAULT_FIXED_ENDING = ""
PORTABILITY_REQUIRED_ROLES = {
    "lecture",
    "source",
    "audio",
    "final_video",
    "final_srt",
    "final_manifest",
}
EPISODE_STARTUP_SCHEMA = "lecture-animation-episode-startup-v1"
EPISODE_STARTUP_RECEIPT_SCHEMA = "lecture-animation-episode-startup-receipt-v1"
EPISODE_STARTUP_REQUIRED_RECEIPTS = {
    "pipeline_preflight": "lecture-animation-pipeline-preflight-v1",
    "delivery_clock": "lecture-animation-delivery-clock-v1",
    "efficiency_contract": "lecture-animation-episode-efficiency-contract-v4",
    "metric_policy": "lecture-animation-metric-policy-v1",
    "supervisor_session": "lecture-animation-supervisor-session-v2",
}
EPISODE_STARTUP_REQUIRED_DECISIONS = {
    "human_feedback_inventory_complete",
    "source_inventory_complete",
    "asset_inventory_complete",
    "fixed_ending_source_locked",
    "reviewer_author_separation_locked",
    "per_scene_review_delivery_locked",
    "canonical_evidence_root_locked",
}
PRONUNCIATION_SENSITIVE_TOKENS = (
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "eta",
    "theta",
    "lambda",
    "mu",
    "nu",
    "xi",
    "pi",
    "rho",
    "sigma",
    "tau",
    "phi",
    "chi",
    "psi",
    "omega",
)
PRONUNCIATION_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2]
    / "references/tts-pronunciation-registry.json"
)
PRONUNCIATION_TOKEN_VARIANTS = {
    "alpha": ("alpha", r"\alpha", "α"),
    "beta": ("beta", r"\beta", "β"),
    "gamma": ("gamma", r"\gamma", "γ"),
    "delta": ("delta", r"\delta", "δ"),
    "epsilon": ("epsilon", r"\epsilon", "ε"),
    "eta": ("eta", r"\eta", "η"),
    "theta": ("theta", r"\theta", "θ"),
    "lambda": ("lambda", r"\lambda", "λ"),
    "mu": ("mu", r"\mu", "μ"),
    "nu": ("nu", r"\nu", "ν"),
    "xi": ("xi", r"\xi", "ξ"),
    "pi": ("pi", r"\pi", "π"),
    "rho": ("rho", r"\rho", "ρ"),
    "sigma": ("sigma", r"\sigma", "σ"),
    "tau": ("tau", r"\tau", "τ"),
    "phi": ("phi", r"\phi", "φ"),
    "chi": ("chi", r"\chi", "χ"),
    "psi": ("psi", r"\psi", "ψ"),
    "omega": ("omega", r"\omega", "ω"),
}
PRONUNCIATION_MACHINE_ACCEPTANCE_MODE = "asr_machine_user_authorized"
AUTO_NOVICE_BRIDGE_TERMS = {
    "模式": "mode",
    "离散到连续": "discrete_to_continuous",
    "连续积分": "discrete_to_continuous",
}


def _resolve(path: str | Path, root: Path) -> Path:
    value = Path(path)
    return value.resolve() if value.is_absolute() else (root / value).resolve()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise PipelineError(f"artifact is outside the repository: {path}") from exc


def _clean_path(path: Path) -> bool:
    return (
        not path.name.startswith("._")
        and path.name not in {".DS_Store"}
        and "__pycache__" not in path.parts
        and ".git" not in path.parts
    )


def artifact_snapshot(path: Path, repo_root: Path) -> dict[str, Any]:
    if not path.exists():
        raise PipelineError(f"artifact does not exist: {path}")
    if path.is_file():
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        return {
            "path": _relative(path, repo_root),
            "kind": "file",
            "sha256": digest.hexdigest(),
            "size": size,
            "file_count": 1,
        }
    digest = hashlib.sha256()
    size = 0
    count = 0
    for child in sorted(item for item in path.rglob("*") if item.is_file() and _clean_path(item)):
        child_digest = hashlib.sha256()
        child_size = 0
        with child.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                child_digest.update(chunk)
                child_size += len(chunk)
        digest.update(child.relative_to(path).as_posix().encode("utf-8") + b"\0")
        digest.update(child_digest.digest())
        size += child_size
        count += 1
    return {
        "path": _relative(path, repo_root),
        "kind": "directory",
        "sha256": digest.hexdigest(),
        "size": size,
        "file_count": count,
    }


def _git_worktree_identity(path: Path) -> tuple[Path | None, str | None, str | None]:
    """Return top-level, branch, and common Git directory for one worktree."""

    if not path.is_dir():
        return None, None, None

    def run(*args: str) -> str | None:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            check=False,
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip()
        return value if result.returncode == 0 and value else None

    top_raw = run("rev-parse", "--show-toplevel")
    branch = run("branch", "--show-current")
    common_raw = run("rev-parse", "--git-common-dir")
    top = Path(top_raw).resolve() if top_raw else None
    common = None
    if common_raw:
        common_value = Path(common_raw)
        common = (
            common_value.resolve()
            if common_value.is_absolute()
            else (path / common_value).resolve()
        )
    return top, branch, str(common) if common else None


def validate_episode_startup_contract(
    contract: dict[str, Any],
    *,
    repo_root: Path,
    episode: Path,
) -> list[str]:
    """Validate the one executable Initialization exit contract.

    This deliberately checks the live Git/worktree topology instead of trusting
    a prose roster.  It is sealed after the delivery clock starts and before
    lecture work leaves Initialization.
    """

    errors: list[str] = []
    expected_episode = _relative(episode, repo_root)
    if contract.get("schema") != EPISODE_STARTUP_SCHEMA:
        errors.append(f"schema must be {EPISODE_STARTUP_SCHEMA}")
    if contract.get("episode") != expected_episode:
        errors.append("episode binding does not match the startup checkout")
    if contract.get("production_mode") not in {"main_producer", "parallel_batches"}:
        errors.append("production_mode must be main_producer or parallel_batches")

    main_agent_id = str(contract.get("main_agent_id", "") or "").strip()
    reviewer_id = str(contract.get("acceptance_reviewer_agent_id", "") or "").strip()
    if not main_agent_id:
        errors.append("main_agent_id is required")
    if not reviewer_id:
        errors.append("acceptance_reviewer_agent_id is required")

    startup_brief = _resolve(contract.get("startup_brief_path", ""), repo_root)
    if (
        not startup_brief.is_file()
        or startup_brief.suffix.lower() != ".md"
        or len(startup_brief.read_text(encoding="utf-8", errors="ignore").strip()) < 120
    ):
        errors.append("startup_brief_path must bind a nontrivial Markdown brief")

    decisions = contract.get("startup_decisions")
    if not isinstance(decisions, dict):
        errors.append("startup_decisions must be an object")
        decisions = {}
    for key in sorted(EPISODE_STARTUP_REQUIRED_DECISIONS):
        if decisions.get(key) is not True:
            errors.append(f"startup decision is not locked: {key}")
    if decisions.get("review_delivery_mode") != "per_scene_immediate_1080p_or_better":
        errors.append(
            "review_delivery_mode must be per_scene_immediate_1080p_or_better"
        )
    if decisions.get("human_feedback_route") != "main_agent_compile_before_authoring":
        errors.append(
            "human_feedback_route must be main_agent_compile_before_authoring"
        )

    evidence_root = _resolve(contract.get("canonical_evidence_root", ""), repo_root)
    try:
        evidence_root.relative_to(episode.resolve())
    except ValueError:
        errors.append("canonical_evidence_root must live inside the episode")
    if not evidence_root.is_dir():
        errors.append("canonical_evidence_root must already exist")
    phase_ledger = _resolve(contract.get("canonical_phase_ledger", ""), repo_root)
    try:
        phase_ledger.relative_to(evidence_root.resolve())
    except ValueError:
        errors.append("canonical_phase_ledger must live inside canonical_evidence_root")
    if not phase_ledger.exists():
        errors.append("canonical_phase_ledger must already exist, even when empty")

    worktree_root = _resolve(contract.get("worktree_root", ""), repo_root)
    if worktree_root.name != "myLectures-worktrees" or not worktree_root.is_dir():
        errors.append("worktree_root must be the existing myLectures-worktrees directory")

    canonical_top, _, canonical_common = _git_worktree_identity(repo_root)
    if canonical_top != repo_root.resolve() or not canonical_common:
        errors.append("repo_root must be a Git worktree root")

    integration_path = _resolve(contract.get("integration_worktree", ""), repo_root)
    integration_branch = str(contract.get("integration_branch", "") or "").strip()
    if integration_path.parent != worktree_root.resolve():
        errors.append("integration_worktree must be a direct child of worktree_root")
    top, branch, common = _git_worktree_identity(integration_path)
    if top != integration_path.resolve() or common != canonical_common:
        errors.append("integration_worktree is not attached to the canonical Git repository")
    if branch != integration_branch or not integration_branch.startswith("codex/"):
        errors.append("integration worktree branch must match and use the codex/... prefix")

    runtime_slots = contract.get("runtime_slots")
    planned_batch_count = contract.get("planned_batch_count")
    if not isinstance(runtime_slots, int) or runtime_slots < 2:
        errors.append("runtime_slots must be an integer of at least 2")
        runtime_slots = 0
    if not isinstance(planned_batch_count, int) or planned_batch_count < 1:
        errors.append("planned_batch_count must be a positive integer")
        planned_batch_count = 0

    roster = contract.get("producer_roster")
    if not isinstance(roster, list):
        errors.append("producer_roster must be a list")
        roster = []
    if contract.get("production_mode") == "parallel_batches" and not roster:
        errors.append("parallel_batches requires at least one producer")
    if contract.get("production_mode") == "main_producer" and roster:
        errors.append("main_producer must not declare production subagents")
    if runtime_slots and len(roster) > runtime_slots - 1:
        errors.append("producer roster leaves no runtime slot for the main reviewer")
    recommended = min(planned_batch_count, max(runtime_slots - 1, 0), 4)
    if (
        contract.get("production_mode") == "parallel_batches"
        and len(roster) < recommended
        and len(str(contract.get("capacity_reason", "") or "").strip()) < 24
    ):
        errors.append(
            "producer roster is below the deterministic startup recommendation "
            "without a concrete capacity_reason"
        )

    agent_ids: set[str] = set()
    worktrees: set[str] = set()
    branches: set[str] = set()
    for index, row in enumerate(roster):
        if not isinstance(row, dict):
            errors.append(f"producer_roster[{index}] must be an object")
            continue
        agent_id = str(row.get("agent_id", "") or "").strip()
        path = _resolve(row.get("worktree", ""), repo_root)
        declared_branch = str(row.get("branch", "") or "").strip()
        if not agent_id or agent_id in agent_ids:
            errors.append(f"producer_roster[{index}] has a missing or duplicate agent_id")
        if agent_id in {main_agent_id, reviewer_id}:
            errors.append(f"producer_roster[{index}] violates author/reviewer separation")
        if str(path) in worktrees or path.parent != worktree_root.resolve():
            errors.append(f"producer_roster[{index}] has a duplicate or misplaced worktree")
        if declared_branch in branches or not declared_branch.startswith("agent/"):
            errors.append(f"producer_roster[{index}] branch must be unique and use agent/...")
        row_top, row_branch, row_common = _git_worktree_identity(path)
        if row_top != path.resolve() or row_common != canonical_common:
            errors.append(f"producer_roster[{index}] worktree is not attached to canonical Git")
        if row_branch != declared_branch:
            errors.append(f"producer_roster[{index}] live branch differs from the contract")
        agent_ids.add(agent_id)
        worktrees.add(str(path))
        branches.add(declared_branch)

    receipts = contract.get("required_receipts")
    if not isinstance(receipts, dict):
        errors.append("required_receipts must be an object")
        receipts = {}
    receipt_snapshots: dict[str, dict[str, Any]] = {}
    receipt_payloads: dict[str, dict[str, Any]] = {}
    for name, schema in EPISODE_STARTUP_REQUIRED_RECEIPTS.items():
        raw = receipts.get(name)
        path = _resolve(raw or "", repo_root)
        try:
            payload = load_json(path)
            receipt_payloads[name] = payload
            receipt_snapshots[name] = artifact_snapshot(path, repo_root)
        except PipelineError as exc:
            errors.append(f"required_receipts.{name}: {exc}")
            continue
        if payload.get("schema") != schema:
            errors.append(f"required_receipts.{name} has the wrong schema")
    preflight = receipt_payloads.get("pipeline_preflight", {})
    if preflight and preflight.get("status") != "pass":
        errors.append("pipeline_preflight must be green")
    clock = receipt_payloads.get("delivery_clock", {})
    if clock:
        if clock.get("episode") != expected_episode:
            errors.append("delivery_clock is bound to another episode")
        if clock.get("status") != "active" or clock.get("current_stage") != "initialization":
            errors.append("delivery_clock must still be active in initialization")
        if int(clock.get("max_production_agents", -1) or -1) < len(roster):
            errors.append(
                "delivery_clock max_production_agents is smaller than the sealed roster"
            )
    efficiency = receipt_payloads.get("efficiency_contract", {})
    if efficiency and efficiency.get("episode") != expected_episode:
        errors.append("efficiency_contract is bound to another episode")
    policy = receipt_payloads.get("metric_policy", {})
    if policy and policy.get("episode") != expected_episode:
        errors.append("metric_policy is bound to another episode")
    supervisor = receipt_payloads.get("supervisor_session", {})
    if supervisor:
        if supervisor.get("supervisor_agent_id") != main_agent_id:
            errors.append("supervisor_session main agent differs from the startup contract")
        known_agents = set(supervisor.get("identity_history", []) or []) | set(
            (supervisor.get("assignments", {}) or {}).keys()
        )
        missing_agents = sorted(agent_ids - known_agents)
        if missing_agents:
            errors.append(
                "supervisor_session is missing producer identities: "
                + ", ".join(missing_agents)
            )

    contract["_startup_receipt_snapshots"] = receipt_snapshots
    return errors


def run_episode_startup_preflight(
    *,
    repo_root: Path,
    episode: Path,
    contract_path: Path,
) -> dict[str, Any]:
    contract = load_json(contract_path)
    working = json.loads(json.dumps(contract))
    errors = validate_episode_startup_contract(
        working,
        repo_root=repo_root,
        episode=episode,
    )
    snapshots = working.pop("_startup_receipt_snapshots", {})
    result = {
        "schema": EPISODE_STARTUP_RECEIPT_SCHEMA,
        "created_at": utc_now(),
        "episode": _relative(episode, repo_root),
        "status": "blocked" if errors else "pass",
        "errors": errors,
        "contract": artifact_snapshot(contract_path, repo_root),
        "production_mode": contract.get("production_mode"),
        "main_agent_id": contract.get("main_agent_id"),
        "acceptance_reviewer_agent_id": contract.get("acceptance_reviewer_agent_id"),
        "producer_count": len(contract.get("producer_roster", []) or []),
        "runtime_slots": contract.get("runtime_slots"),
        "integration_worktree": contract.get("integration_worktree"),
        "canonical_evidence_root": contract.get("canonical_evidence_root"),
        "required_receipts": snapshots,
    }
    result["receipt_hash"] = object_hash(result)
    return result


def validate_episode_startup_receipt(
    receipt_path: Path,
    *,
    repo_root: Path,
    episode: Path,
) -> list[str]:
    errors: list[str] = []
    try:
        receipt = load_json(receipt_path)
    except PipelineError as exc:
        return [str(exc)]
    if receipt.get("schema") != EPISODE_STARTUP_RECEIPT_SCHEMA:
        errors.append("startup receipt has the wrong schema")
    expected_hash = receipt.get("receipt_hash")
    hash_input = dict(receipt)
    hash_input.pop("receipt_hash", None)
    if expected_hash != object_hash(hash_input):
        errors.append("startup receipt hash is invalid")
    if receipt.get("status") != "pass" or receipt.get("errors"):
        errors.append("startup receipt is not a clean pass")
    if receipt.get("episode") != _relative(episode, repo_root):
        errors.append("startup receipt is bound to another episode")
    contract_snapshot = receipt.get("contract")
    if not isinstance(contract_snapshot, dict):
        errors.append("startup receipt has no contract snapshot")
        return errors
    contract_path = _resolve(contract_snapshot.get("path", ""), repo_root)
    try:
        current_snapshot = artifact_snapshot(contract_path, repo_root)
    except PipelineError as exc:
        errors.append(str(exc))
        return errors
    if any(
        current_snapshot.get(field) != contract_snapshot.get(field)
        for field in ("path", "sha256", "size", "file_count")
    ):
        errors.append("startup contract changed after the receipt was sealed")
        return errors
    fresh = run_episode_startup_preflight(
        repo_root=repo_root,
        episode=episode,
        contract_path=contract_path,
    )
    if fresh.get("status") != "pass":
        errors.extend(f"current startup contract: {error}" for error in fresh["errors"])
    return errors


def command_seal_episode_startup(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    episode = _resolve(args.episode, repo_root)
    result = run_episode_startup_preflight(
        repo_root=repo_root,
        episode=episode,
        contract_path=_resolve(args.contract, repo_root),
    )
    write_json(_resolve(args.output, repo_root), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if args.require_clean and result["status"] == "blocked" else 0


def _load_contract(path: Path) -> dict[str, Any]:
    data = load_json(path)
    if data.get("schema") != "lecture-animation-episode-readiness-v2":
        raise PipelineError("readiness contract schema must be lecture-animation-episode-readiness-v2")
    return data


def _normalized_clause(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).lower()


def _sentences(value: str) -> list[str]:
    return [part.strip() for part in SENTENCE_SPLIT.split(value) if part.strip()]


def _boundary_duplicates(left: str, right: str) -> list[str]:
    left_tail = _sentences(left)[-3:]
    right_head = _sentences(right)[:3]
    duplicates: list[str] = []
    for left_clause in left_tail:
        normalized_left = _normalized_clause(left_clause)
        if len(normalized_left) < 10:
            continue
        for right_clause in right_head:
            if normalized_left == _normalized_clause(right_clause):
                duplicates.append(left_clause)
    return duplicates


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / max(handle.getframerate(), 1)


def _alignment_words(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if (
            any(key in value for key in ("word", "text", "token"))
            and any(key in value for key in ("start", "start_time", "start_seconds"))
            and any(key in value for key in ("end", "end_time", "end_seconds"))
        ):
            rows.append(value)
        else:
            # Formalized alignment manifests can retain several equivalent
            # timing representations (word_cues, reader_cues, raw_alignment).
            # Pace belongs to one canonical token sequence, not the union of
            # every audit copy. Prefer the most precise declared sequence and
            # recurse generically only for legacy shapes that have none.
            for canonical_key in ("word_cues", "words", "tokens", "segments"):
                canonical = value.get(canonical_key)
                if isinstance(canonical, list) and canonical:
                    return _alignment_words(canonical)
            for child in value.values():
                rows.extend(_alignment_words(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(_alignment_words(child))
    return rows


def _time_value(row: dict[str, Any], keys: Iterable[str]) -> float | None:
    for key in keys:
        if key not in row:
            continue
        try:
            value = float(row[key])
        except (TypeError, ValueError):
            continue
        if value > 1000:
            value /= 1000.0
        return value
    return None


def _rolling_pace(words: list[dict[str, Any]], window_seconds: float = 12.0) -> float:
    timed: list[tuple[float, int]] = []
    for row in words:
        start = _time_value(row, ("start", "start_time", "start_seconds"))
        if start is None:
            continue
        text = str(row.get("word") or row.get("text") or row.get("token") or "")
        timed.append((start, max(1, len(TOKEN_PATTERN.findall(text)))))
    timed.sort()
    maximum = 0.0
    right = 0
    token_sum = 0
    for left, (start, _) in enumerate(timed):
        if right < left:
            right = left
        while right < len(timed) and timed[right][0] < start + window_seconds:
            token_sum += timed[right][1]
            right += 1
        maximum = max(maximum, token_sum / window_seconds)
        token_sum -= timed[left][1]
    return maximum


def _pronunciation_tokens(text: str, contract: dict[str, Any]) -> set[str]:
    explicit = {
        str(value).strip().lower()
        for value in contract.get("sensitive_tokens", [])
        if str(value).strip()
    }
    for token in PRONUNCIATION_SENSITIVE_TOKENS:
        if _formal_occurrence_count(text, token):
            explicit.add(token)
    return explicit


def _bridge_errors(
    bridge: Any,
    narration: str,
    terms: list[str],
    prefix: str,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(bridge, dict):
        return [f"{prefix}: novice_bridge must be an evidence-bound object"]
    for key, minimum in (
        ("explanation", 20),
        ("concrete_referent", 8),
        ("learner_action", 8),
        ("narration_quote", 8),
    ):
        value = str(bridge.get(key, "")).strip()
        if len(value) < minimum:
            errors.append(f"{prefix}: novice_bridge.{key} is too short or missing")
        elif value not in narration:
            errors.append(
                f"{prefix}: novice_bridge.{key} must be an exact quote from the narration"
            )
    if bridge.get("term_introduction_after_referent") is not True:
        errors.append(f"{prefix}: novice_bridge must affirm term_introduction_after_referent=true")
    quote = str(bridge.get("narration_quote", "")).strip()
    quote_index = narration.find(quote) if quote else -1
    if quote and quote_index < 0:
        errors.append(f"{prefix}: novice_bridge.narration_quote is absent from the narration")
    for term in terms:
        term_index = narration.find(term)
        if term_index < 0:
            errors.append(f"{prefix}: declared new term {term!r} is absent from the narration")
        elif quote_index >= 0 and quote_index >= term_index:
            errors.append(
                f"{prefix}: concrete narration quote must occur before new term {term!r}"
            )
        referent = str(bridge.get("concrete_referent", "")).strip()
        referent_index = narration.find(referent) if referent else -1
        if term_index >= 0 and referent_index >= term_index:
            errors.append(
                f"{prefix}: concrete_referent quote must occur before new term {term!r}"
            )
    return errors


def _bridge_evidence_hash(bridge: dict[str, Any], terms: list[str]) -> str:
    return object_hash(
        {
            "terms": terms,
            "explanation": str(bridge.get("explanation", "")).strip(),
            "concrete_referent": str(bridge.get("concrete_referent", "")).strip(),
            "learner_action": str(bridge.get("learner_action", "")).strip(),
            "narration_quote": str(bridge.get("narration_quote", "")).strip(),
            "term_introduction_after_referent": bridge.get(
                "term_introduction_after_referent"
            ),
        }
    )


def _evidence_inventory_count(
    *,
    rows: Any,
    repo_root: Path,
    allowed_root: Path,
    label: str,
    errors: list[str],
    artifacts: dict[str, Any],
) -> int:
    if rows in (None, []):
        return 0
    if not isinstance(rows, list):
        errors.append(f"{label} inventory must be a list")
        return 0
    count = 0
    seen: Counter[tuple[str, str]] = Counter()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"{label}[{index}] must bind text to a source_path")
            continue
        text = str(row.get("text", "")).strip()
        source_raw = str(row.get("source_path", "")).strip()
        if not text or not source_raw:
            errors.append(f"{label}[{index}] requires text and source_path")
            continue
        identity = (text, source_raw)
        seen[identity] += 1
        source = _resolve(source_raw, repo_root)
        if source != allowed_root and allowed_root not in source.parents:
            errors.append(
                f"{label}[{index}] source_path must live inside scene_source_root"
            )
            continue
        if not source.is_file():
            errors.append(f"{label}[{index}] source_path does not exist: {source_raw}")
            continue
        source_text = source.read_text(encoding="utf-8", errors="ignore")
        if text not in source_text:
            errors.append(f"{label}[{index}] text is absent from {source_raw}")
            continue
        if source_text.count(text) < seen[identity]:
            errors.append(
                f"{label}[{index}] occurrence exceeds the source text multiplicity"
            )
            continue
        try:
            artifacts[f"{label.rsplit('.', 1)[-1]}_{index}"] = artifact_snapshot(
                source, repo_root
            )
        except PipelineError as exc:
            errors.append(f"{label}[{index}]: {exc}")
            continue
        count += 1
    return count


def _visible_text_records(
    path: Path,
    label: str,
    errors: list[str],
) -> list[dict[str, str]]:
    if path.suffix.lower() != ".py":
        errors.append(f"{label}: automatic visible-text inventory currently requires a Python scene")
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError as exc:
        errors.append(f"{label}: scene source cannot be parsed for visible text: {exc}")
        return []
    records: list[dict[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr
            if isinstance(node.func, ast.Attribute)
            else ""
        )
        if function_name not in VISIBLE_TEXT_CONSTRUCTORS:
            continue
        # Runtime-registered project wrappers may intentionally carry a
        # dynamic payload (for example ``label(f"n={n}")``).  The semantic
        # contract binds static payloads; dynamic payload count/registration is
        # enforced by the execution-side scanner and registry.  Do not turn a
        # legitimate runtime payload into a false static mismatch here.  Bare
        # constructors remain strict: a dynamic Text/MathTex payload cannot
        # bypass the frozen inventory.
        if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(
            node.args[0].value, str
        ):
            if function_name not in VISIBLE_TEXT_WRAPPERS:
                errors.append(
                    f"{label}: dynamic {function_name}(...) text at line "
                    f"{getattr(node, 'lineno', '?')} cannot bypass the frozen inventory"
                )
            continue
        records.append(
            {
                "constructor": function_name,
                "payload": node.args[0].value,
            }
        )
    return records


def _visible_text_literals(path: Path, label: str, errors: list[str]) -> list[str]:
    return [
        record["payload"]
        for record in _visible_text_records(path, label, errors)
    ]


def _validate_episode_screen_text_semantics(
    *,
    path: Path,
    repo_root: Path,
    source_records: list[dict[str, str]],
    slug: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(
            f"{slug}: post_tts readiness requires a machine-readable "
            "screen_text_semantic_contract_path"
        )
        return None
    try:
        payload = load_json(path)
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"{slug}: screen text semantic contract cannot be loaded: {exc}")
        return None
    contract = (
        payload.get("screen_text_contract")
        if isinstance(payload, dict) and isinstance(payload.get("screen_text_contract"), dict)
        else payload
    )
    if isinstance(contract, dict):
        errors.extend(
            f"{slug}: screen-text registration: {error}"
            for error in validate_screen_text_contract_registration(
                contract, repo_root, slug
            )
        )
    semantic_items = contract.get("semantic_items", []) if isinstance(contract, dict) else []
    if not isinstance(semantic_items, list):
        errors.append(f"{slug}: screen text semantic contract requires semantic_items")
        return payload if isinstance(payload, dict) else None

    actual = Counter(
        (str(record.get("constructor", "")), str(record.get("payload", "")))
        for record in source_records
    )
    planned: Counter[tuple[str, str]] = Counter()
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(semantic_items):
        label = f"{slug}.screen_text_semantic_contract.semantic_items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        key = (str(item.get("constructor", "")), str(item.get("payload", "")))
        try:
            count = int(item.get("count", 0))
        except (TypeError, ValueError):
            count = 0
        if not all(key) or count < 1 or key in seen:
            errors.append(
                f"{label} requires a unique constructor/payload pair and positive count"
            )
        seen.add(key)
        planned[key] += max(count, 0)
        if len(str(item.get("unique_visual_job", "")).strip()) < 12:
            errors.append(f"{label} requires unique_visual_job")
        if len(str(item.get("necessity", "")).strip()) < 16:
            errors.append(f"{label} requires learner-facing necessity")
        if len(str(item.get("removal_failure", "")).strip()) < 16:
            errors.append(f"{label} requires concrete removal_failure")
        if len(str(item.get("clearance_condition", "")).strip()) < 8:
            errors.append(f"{label} requires clearance_condition")
        if not (
            str(item.get("math_object_anchor", "")).strip()
            or str(item.get("learner_question_anchor", "")).strip()
        ):
            errors.append(
                f"{label} must bind math_object_anchor or learner_question_anchor"
            )
        if item.get("duplicates_narration") is not False:
            errors.append(f"{label} must set duplicates_narration=false")
        if item.get("externalizes_production_intent") is not False:
            errors.append(f"{label} must set externalizes_production_intent=false")
        violation = presentation_boundary_violation(key[1])
        if violation:
            errors.append(
                f"{label} violates the learner-facing presentation boundary: {violation}"
            )
    if actual != planned:
        missing = sorted((actual - planned).elements())
        extra = sorted((planned - actual).elements())
        if missing:
            errors.append(
                f"{slug}: screen text semantic contract misses source payloads: {missing}"
            )
        if extra:
            errors.append(
                f"{slug}: screen text semantic contract contains absent payloads: {extra}"
            )
    return payload if isinstance(payload, dict) else None


def _validate_independent_review(
    *,
    path: Path,
    repo_root: Path,
    expected_schema: str,
    expected_bindings: dict[str, Any],
    required_checks: tuple[str, ...],
    label: str,
    errors: list[str],
    author_id: str,
    expected_review_kind: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if not path.is_file():
        errors.append(f"{label}: independent review evidence does not exist")
        return None
    try:
        review = load_json(path)
    except PipelineError as exc:
        errors.append(f"{label}: independent review evidence is invalid: {exc}")
        return None
    if review.get("schema") != expected_schema:
        errors.append(f"{label}: independent review schema is invalid")
    reviewer_id = str(review.get("reviewer_id", "")).strip()
    if reviewer_id == "":
        errors.append(f"{label}: independent review requires reviewer_id")
    if review.get("author_id") != author_id:
        errors.append(f"{label}: review author_id does not match the production author")
    if reviewer_id == author_id:
        errors.append(f"{label}: reviewer_id must differ from author_id")
    if review.get("review_source") not in {"human_review", "independent_review"}:
        errors.append(f"{label}: review_source must be human_review or independent_review")
    if review.get("verdict") != "pass":
        errors.append(f"{label}: independent review verdict must be pass")
    review_payload = dict(review)
    review_hash = review_payload.pop("review_hash", None)
    if review_hash != object_hash(review_payload):
        errors.append(f"{label}: independent review hash is invalid or stale")
    for key, expected in expected_bindings.items():
        if review.get(key) != expected:
            errors.append(f"{label}: independent review binding {key} is stale or mismatched")
    checks = review.get("checks", {})
    if not isinstance(checks, dict) or any(checks.get(key) is not True for key in required_checks):
        errors.append(
            f"{label}: independent review is missing required semantic checks: "
            + ", ".join(required_checks)
        )
    authority_raw = str(review.get("authority_path", "")).strip()
    if not authority_raw:
        errors.append(f"{label}: independent review requires authority_path")
        return None
    authority_path = _resolve(authority_raw, repo_root)
    try:
        authority = load_json(authority_path)
        authority_snapshot = artifact_snapshot(authority_path, repo_root)
    except PipelineError as exc:
        errors.append(f"{label}: review authority is invalid: {exc}")
        return None
    authority_payload = dict(authority)
    authority_hash = authority_payload.pop("authority_hash", None)
    if authority_hash != object_hash(authority_payload):
        errors.append(f"{label}: review authority hash is invalid or stale")
    if authority.get("schema") not in {
        "lecture-animation-human-review-authority-v2",
        "lecture-animation-independent-review-authority-v2",
    }:
        errors.append(f"{label}: review authority schema is invalid")
    if authority.get("author_id") != author_id or authority.get("reviewer_id") != reviewer_id:
        errors.append(f"{label}: review authority identity binding is mismatched")
    expected_authority_schema = (
        "lecture-animation-human-review-authority-v2"
        if review.get("review_source") == "human_review"
        else "lecture-animation-independent-review-authority-v2"
    )
    if authority.get("schema") != expected_authority_schema:
        errors.append(f"{label}: review authority schema does not match review_source")
    if authority.get("review_source") != review.get("review_source"):
        errors.append(f"{label}: review authority source binding is mismatched")
    if authority.get("review_kind") != expected_review_kind:
        errors.append(f"{label}: review authority kind binding is mismatched")
    if authority.get("authorized_verdict") != review.get("verdict"):
        errors.append(f"{label}: review authority verdict binding is mismatched")
    if authority.get("status") not in {"active", "approved", "granted"}:
        errors.append(f"{label}: review authority is not active or approved")
    if review.get("authority_sha256") != authority_snapshot["sha256"]:
        errors.append(f"{label}: review authority SHA binding is stale")
    return review, authority_snapshot


def _validate_machine_pronunciation_review(
    *,
    path: Path,
    repo_root: Path,
    expected_bindings: dict[str, Any],
    label: str,
    errors: list[str],
) -> dict[str, Any] | None:
    """Validate an explicit user-authorized ASR acceptance record.

    This is not a human-listening pass.  It is a deliberately separate
    evidence type used only when the episode contract carries an explicit user
    authority saying that ASR is the machine acceptance for this production
    pass.  The final user audio review therefore remains pending in the
    receipt and cannot be inferred from this record.
    """
    if not path.is_file():
        errors.append(f"{label}: machine pronunciation review does not exist")
        return None
    try:
        review = load_json(path)
    except PipelineError as exc:
        errors.append(f"{label}: machine pronunciation review is invalid: {exc}")
        return None
    if review.get("schema") != "lecture-animation-pronunciation-machine-review-v1":
        errors.append(f"{label}: machine pronunciation review schema is invalid")
    if review.get("verdict") != "pass":
        errors.append(f"{label}: machine pronunciation review verdict must be pass")
    if review.get("machine_method") not in {"asr", "asr_alignment"}:
        errors.append(f"{label}: machine pronunciation review must name ASR")
    if review.get("human_listening_pass") is not False:
        errors.append(
            f"{label}: machine pronunciation review must explicitly keep human listening pending"
        )
    payload = dict(review)
    stored_hash = payload.pop("review_hash", None)
    if stored_hash != object_hash(payload):
        errors.append(f"{label}: machine pronunciation review hash is invalid or stale")
    for key, expected in expected_bindings.items():
        if review.get(key) != expected:
            errors.append(f"{label}: machine review binding {key} is stale or mismatched")
    checks = review.get("checks", {})
    required = (
        "exact_audio_bound",
        "occurrence_windows_bound",
        "asr_surface_checked",
        "no_forbidden_form_detected",
    )
    if not isinstance(checks, dict) or any(checks.get(key) is not True for key in required):
        errors.append(
            f"{label}: machine pronunciation review is missing required checks: "
            + ", ".join(required)
        )
    return review


def _formal_occurrence_count(text: str, token: str) -> int:
    variants = PRONUNCIATION_TOKEN_VARIANTS.get(token.lower())
    if variants:
        count = 0
        for value in variants:
            if len(value) == 1 and not value.isascii():
                # Unicode Greek glyphs remain distinct tokens even when
                # adjacent to Latin differential or exponential notation,
                # such as iθ and dθ.
                count += text.count(value)
            else:
                left_guard = r"(?<![A-Za-z])" if value.startswith("\\") else r"(?<![A-Za-z\\])"
                count += len(
                    re.findall(
                        rf"{left_guard}{re.escape(value)}(?![A-Za-z])",
                        text,
                        re.I,
                    )
                )
        return count
    if re.fullmatch(r"[A-Za-z]+", token):
        return len(re.findall(rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", text, re.I))
    if token.isascii():
        return len(
            re.findall(
                rf"(?<![A-Za-z\\]){re.escape(token)}(?![A-Za-z])",
                text,
                re.I,
            )
        )
    return text.count(token)


def _canonical_formal_occurrence_count(
    text: str,
    token: str,
    pronunciation_registry: dict[str, Any] | None = None,
) -> int:
    """Count a token using the registry's longest-match identity rules.

    The legacy counter is intentionally kept for backwards-compatible unit
    tests and callers that only have the compact Greek-token table.  Readiness
    contracts, however, have an exact pronunciation registry in scope.  In
    that path a composite identity such as ``Res f`` or ``i d theta`` must
    occupy its span before the atomic ``f``/``i``/``theta`` tokens are counted.
    Without this boundary, a valid mapping is reported as both unresolved and
    over-counted.
    """
    if isinstance(pronunciation_registry, dict) and pronunciation_registry.get("tokens"):
        folded = token.casefold()
        return sum(
            1
            for row in _registry_occurrences(text, pronunciation_registry)
            if row.get("token_key") == folded
        )
    return _formal_occurrence_count(text, token)


def _load_pronunciation_registry(
    path: Path,
    errors: list[str],
) -> dict[str, Any]:
    try:
        registry = load_json(path)
    except PipelineError as exc:
        errors.append(f"canonical TTS pronunciation registry is unavailable: {exc}")
        return {}
    if registry.get("schema") != "lecture-animation-tts-pronunciation-registry-v1":
        errors.append("canonical TTS pronunciation registry has an invalid schema")
    if not isinstance(registry.get("routes"), dict) or not isinstance(
        registry.get("tokens"), dict
    ):
        errors.append("canonical TTS pronunciation registry requires routes and tokens")
    return registry


def _token_matches(text: str, token: str) -> list[tuple[int, int]]:
    variants = PRONUNCIATION_TOKEN_VARIANTS.get(token.casefold(), (token,))
    matches: list[tuple[int, int]] = []
    for variant in variants:
        if variant.isascii():
            pattern = re.compile(
                rf"(?<![A-Za-z\\]){re.escape(variant)}(?![A-Za-z])",
                re.I,
            )
            matches.extend((match.start(), match.end()) for match in pattern.finditer(text))
        else:
            start = 0
            while True:
                index = text.find(variant, start)
                if index < 0:
                    break
                matches.append((index, index + len(variant)))
                start = index + len(variant)
    return matches


def _registry_occurrences(
    text: str,
    pronunciation_registry: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[tuple[int, int, str]] = []
    for token in dict(pronunciation_registry.get("tokens", {})):
        candidates.extend(
            (start, end, str(token).casefold())
            for start, end in _token_matches(text, str(token))
        )
    # Longest token wins at the same start. This makes composite identities such
    # as ``i d theta`` and ``Res f`` authoritative over their atomic parts.
    candidates.sort(key=lambda row: (row[0], -(row[1] - row[0]), row[2]))
    selected: list[dict[str, Any]] = []
    occupied_until = -1
    counts: Counter[str] = Counter()
    for start, end, token in candidates:
        if start < occupied_until:
            continue
        counts[token] += 1
        selected.append(
            {
                "token_key": token,
                "formal_start": start,
                "formal_end": end,
                "formal_surface": text[start:end],
                "occurrence_index": counts[token],
            }
        )
        occupied_until = end
    return selected


def _validate_tts_input_mapping(
    *,
    mapping_path: Path,
    formal_script_path: Path,
    tts_input_path: Path,
    scene_slug: str,
    route_id: str,
    pronunciation_registry: dict[str, Any],
    repo_root: Path,
    errors: list[str],
) -> dict[str, Any] | None:
    label = f"{scene_slug}.tts_input_mapping"
    try:
        mapping = load_json(mapping_path)
    except PipelineError as exc:
        errors.append(f"{label} is invalid: {exc}")
        return None
    if mapping.get("schema") != "lecture-animation-tts-input-mapping-v2":
        errors.append(f"{label} must use lecture-animation-tts-input-mapping-v2")
        return None
    if mapping.get("scene_slug") != scene_slug:
        errors.append(f"{label} scene binding is mismatched")
    if mapping.get("route_id") != route_id:
        errors.append(f"{label} route binding is mismatched")
    routes = dict(pronunciation_registry.get("routes", {}))
    if not route_id or route_id not in routes:
        errors.append(f"{label} names an unregistered exact TTS route")

    expected_paths = {
        "formal_script_path": formal_script_path,
        "tts_input_path": tts_input_path,
    }
    for key, expected_path in expected_paths.items():
        raw = str(mapping.get(key, "")).strip()
        if not raw or _resolve(raw, repo_root) != expected_path.resolve():
            errors.append(f"{label} {key} binding is mismatched")

    formal_text = formal_script_path.read_text(encoding="utf-8")
    tts_text = tts_input_path.read_text(encoding="utf-8")
    formal_snapshot = artifact_snapshot(formal_script_path, repo_root)
    tts_snapshot = artifact_snapshot(tts_input_path, repo_root)
    if mapping.get("formal_script_sha256") != formal_snapshot["sha256"]:
        errors.append(f"{label} formal script SHA binding is stale")
    if mapping.get("tts_input_sha256") != tts_snapshot["sha256"]:
        errors.append(f"{label} TTS input SHA binding is stale")

    rows = mapping.get("occurrences", [])
    if not isinstance(rows, list):
        errors.append(f"{label}.occurrences must be a list")
        rows = []
    normalized: list[dict[str, Any]] = []
    prior_end = 0
    token_counts: Counter[str] = Counter()
    reconstructed: list[str] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"{label} occurrence {index} must be an object")
            continue
        token_key = str(row.get("token_key", "")).strip().casefold()
        spoken_form = str(row.get("spoken_form", ""))
        formal_surface = str(row.get("formal_surface", ""))
        try:
            start = int(row.get("formal_start"))
            end = int(row.get("formal_end"))
        except (TypeError, ValueError):
            errors.append(f"{label} occurrence {index} has invalid character offsets")
            continue
        if start < prior_end or end <= start or end > len(formal_text):
            errors.append(
                f"{label} occurrence {index} must be ordered, non-overlapping, and in bounds"
            )
            continue
        if formal_text[start:end] != formal_surface:
            errors.append(f"{label} occurrence {index} formal surface does not match its span")
        token_policy = dict(pronunciation_registry.get("tokens", {})).get(token_key)
        if not isinstance(token_policy, dict):
            errors.append(f"{label} occurrence {index} uses unregistered token {token_key!r}")
        else:
            route_policy = dict(pronunciation_registry.get("routes", {})).get(
                route_id, {}
            )
            allowed = {
                str(value)
                for value in dict(route_policy).get("candidate_forms", {}).get(
                    token_key, []
                )
            }
            forbidden = {
                str(value).strip().casefold()
                for value in token_policy.get("forbidden_forms", [])
            }
            if spoken_form != spoken_form.strip() or any(ord(char) < 32 for char in spoken_form):
                errors.append(
                    f"{label} occurrence {index} spoken form contains boundary whitespace or controls"
                )
            elif spoken_form.casefold() in forbidden:
                errors.append(
                    f"{label} occurrence {index} uses forbidden spoken form {spoken_form!r}"
                )
            elif spoken_form not in allowed:
                errors.append(
                    f"{label} occurrence {index} uses unregistered spoken form {spoken_form!r}"
                )
        token_counts[token_key] += 1
        if row.get("occurrence_index") != token_counts[token_key]:
            errors.append(
                f"{label} occurrence {index} has a non-canonical occurrence_index"
            )
        if bool(row.get("replacement_applied")) != (formal_surface != spoken_form):
            errors.append(f"{label} occurrence {index} replacement_applied is false evidence")
        reconstructed.append(formal_text[prior_end:start])
        reconstructed.append(spoken_form)
        prior_end = end
        normalized.append(
            {
                "token_key": token_key,
                "formal_start": start,
                "formal_end": end,
                "formal_surface": formal_surface,
                "spoken_form": spoken_form,
                "occurrence_index": token_counts[token_key],
            }
        )
    reconstructed.append(formal_text[prior_end:])
    if "".join(reconstructed) != tts_text:
        errors.append(
            f"{label} cannot exactly reconstruct the TTS input; an unregistered or misplaced edit exists"
        )

    expected = _registry_occurrences(formal_text, pronunciation_registry)
    observed = [
        {
            key: row[key]
            for key in (
                "token_key",
                "formal_start",
                "formal_end",
                "formal_surface",
                "occurrence_index",
            )
        }
        for row in normalized
    ]
    if observed != expected:
        errors.append(
            f"{label} occurrence inventory does not exactly cover canonical sensitive tokens"
        )

    folded_tts = tts_text.casefold()
    for token_key, token_policy in dict(pronunciation_registry.get("tokens", {})).items():
        if not isinstance(token_policy, dict):
            continue
        for forbidden in token_policy.get("forbidden_forms", []):
            forbidden_text = str(forbidden).strip()
            if forbidden_text and forbidden_text.casefold() in folded_tts:
                errors.append(
                    f"{label} TTS input contains forbidden form {forbidden_text!r} "
                    f"registered for {token_key}"
                )
    return {
        "mapping": artifact_snapshot(mapping_path, repo_root),
        "formal_script": formal_snapshot,
        "tts_input": tts_snapshot,
        "route_id": route_id,
        "occurrences": normalized,
        "status": "candidate_pending_exact_scene_ear_review",
    }


def _validate_pronunciation_binding(
    *,
    token: str,
    binding: dict[str, Any],
    formal_count: int,
    readiness_stage: str,
    repo_root: Path,
    narration_lookup: dict[str, str],
    scene_audio_paths: dict[str, Path],
    author_id: str,
    route_id: str,
    pronunciation_registry: dict[str, Any],
    exact_mapping_evidence: dict[str, Any] | None,
    acceptance_mode: str = "human_or_independent",
    errors: list[str],
) -> dict[str, Any] | None:
    scene_slug = str(binding.get("scene_slug", "")).strip()
    label = f"pronunciation mapping for {token}"
    if scene_slug:
        label += f" in {scene_slug}"
    spoken_form = str(binding.get("spoken_form", "")).strip()
    tts_input_raw = str(binding.get("tts_input_path", "")).strip()
    ear_evidence_raw = str(binding.get("ear_evidence_path", "")).strip()
    ear_review_raw = str(binding.get("ear_review_path", "")).strip()
    machine_review_raw = str(binding.get("machine_review_path", "")).strip()
    source_audio_raw = str(binding.get("source_audio_path", "")).strip()
    if not spoken_form or not tts_input_raw or not scene_slug:
        errors.append(
            f"{label} requires spoken_form, scene_slug, and tts_input_path"
        )
        return None
    token_policy = dict(pronunciation_registry.get("tokens", {})).get(
        token.lower()
    )
    if not isinstance(token_policy, dict):
        errors.append(f"{label} is not registered in the canonical TTS registry")
    else:
        forbidden = {
            str(value).strip().casefold()
            for value in token_policy.get("forbidden_forms", [])
        }
        route_policy = dict(pronunciation_registry.get("routes", {})).get(
            route_id, {}
        )
        allowed = {
            str(value)
            for value in dict(route_policy).get("candidate_forms", {}).get(
                token.lower(), []
            )
        }
        if spoken_form != spoken_form.strip() or any(ord(char) < 32 for char in spoken_form):
            errors.append(f"{label} spoken form contains boundary whitespace or controls")
        elif spoken_form.casefold() in forbidden:
            errors.append(
                f"{label} uses forbidden spoken form {spoken_form!r}"
            )
        elif spoken_form not in allowed:
            errors.append(
                f"{label} uses unregistered spoken form {spoken_form!r}"
            )
    binding_route_id = str(binding.get("route_id", "")).strip()
    if not route_id or binding_route_id != route_id:
        errors.append(
            f"{label} must bind the exact canonical TTS route {route_id!r}"
        )
    if scene_slug not in narration_lookup:
        errors.append(f"{label} names unknown scene {scene_slug}")
        return None
    expected_count = int(binding.get("occurrences", formal_count) or 0)
    if expected_count != formal_count or expected_count <= 0:
        errors.append(
            f"{label} binds {expected_count} occurrences; narration has {formal_count}"
        )
    tts_input_path = _resolve(tts_input_raw, repo_root)
    if not tts_input_path.is_file():
        errors.append(f"TTS input for {token} in {scene_slug} does not exist")
        return None
    mapped_tts_input = (
        exact_mapping_evidence.get("tts_input")
        if isinstance(exact_mapping_evidence, dict)
        else None
    )
    if not isinstance(mapped_tts_input, dict):
        errors.append(f"{label} lacks exact scene TTS mapping evidence")
    else:
        binding_snapshot = artifact_snapshot(tts_input_path, repo_root)
        if (
            binding_snapshot.get("path") != mapped_tts_input.get("path")
            or binding_snapshot.get("sha256") != mapped_tts_input.get("sha256")
        ):
            errors.append(
                f"{label} tts_input_path must equal the exact-mapped scene TTS input"
            )
    tts_input = tts_input_path.read_text(encoding="utf-8", errors="ignore")
    mapped_rows = (
        exact_mapping_evidence.get("occurrences", [])
        if isinstance(exact_mapping_evidence, dict)
        else []
    )
    token_rows = [
        row
        for row in mapped_rows
        if isinstance(row, dict)
        and str(row.get("token_key", "")).casefold() == token.casefold()
    ]
    if token_rows:
        observed_spoken_count = sum(
            1 for row in token_rows if str(row.get("spoken_form", "")) == spoken_form
        )
    else:
        # Keep a conservative fallback for legacy callers that do not carry
        # exact mapping evidence.  Post-TTS readiness normally takes the
        # registry-bound branch above.
        observed_spoken_count = tts_input.count(spoken_form)
    if observed_spoken_count != expected_count:
        errors.append(
            f"TTS input for {token} in {scene_slug} must contain spoken form "
            f"{spoken_form!r} exactly {expected_count} times"
        )
    unresolved_formal_count = _canonical_formal_occurrence_count(
        tts_input,
        token,
        pronunciation_registry,
    )
    if mapped_rows:
        # Subtract every exact mapped spoken span that still contains the
        # target token.  This covers literal routes (``f``), composite
        # identities (``i d theta``), and approved alternatives such as
        # ``Res f`` -> ``residue f``.  Counting each replacement under the
        # same longest-match registry prevents a composite from leaking its
        # atomic children while still exposing an extra, unmapped occurrence.
        mapped_spoken_count = sum(
            _canonical_formal_occurrence_count(
                str(row.get("spoken_form", "")),
                token,
                pronunciation_registry,
            )
            for row in mapped_rows
            if isinstance(row, dict)
        )
        unresolved_formal_count -= mapped_spoken_count
    elif spoken_form.casefold() == token.casefold():
        unresolved_formal_count -= expected_count
    unresolved_formal_count = max(0, unresolved_formal_count)
    if unresolved_formal_count > 0:
        errors.append(
            f"TTS input for {token} in {scene_slug} still contains the unresolved formal token"
        )
    evidence: dict[str, Any] = {
        "formal_occurrences": formal_count,
        "spoken_form": spoken_form,
        "scene_slug": scene_slug,
        "route_id": route_id,
        "tts_input": artifact_snapshot(tts_input_path, repo_root),
    }
    if readiness_stage == "pre_tts":
        evidence["review_status"] = "pending_post_tts"
        return evidence
    required_review_path = (
        machine_review_raw
        if acceptance_mode == PRONUNCIATION_MACHINE_ACCEPTANCE_MODE
        else ear_review_raw
    )
    if not ear_evidence_raw or not source_audio_raw or not required_review_path:
        review_label = (
            "machine_review_path"
            if acceptance_mode == PRONUNCIATION_MACHINE_ACCEPTANCE_MODE
            else "ear_review_path"
        )
        errors.append(
            f"post_tts {label} requires source_audio_path, ear_evidence_path, "
            f"and {review_label}"
        )
        return evidence
    source_audio_path = _resolve(source_audio_raw, repo_root)
    ear_evidence_path = _resolve(ear_evidence_raw, repo_root)
    bound_scene_audio = scene_audio_paths.get(scene_slug)
    if not source_audio_path.is_file() or not ear_evidence_path.is_file():
        errors.append(f"pronunciation evidence files for {token} in {scene_slug} do not all exist")
        return evidence
    if bound_scene_audio is None or source_audio_path.resolve() != bound_scene_audio.resolve():
        errors.append(
            f"{label} source_audio_path must equal the bound scene audio_path"
        )
    if ear_evidence_path.resolve() != source_audio_path.resolve():
        errors.append(
            f"{label} ear_evidence_path must be the bound final scene audio; "
            "shorter clips are review aids, not gate evidence"
        )
    try:
        source_duration = _wav_duration(source_audio_path)
        _wav_duration(ear_evidence_path)
    except (wave.Error, EOFError) as exc:
        errors.append(
            f"pronunciation evidence for {token} in {scene_slug} is not a decodable WAV: {exc}"
        )
        source_duration = 0.0
    checks = binding.get("ear_check_results", [])
    windows = binding.get("occurrence_windows_seconds", [])
    normalized_windows: list[list[float]] = []
    if not isinstance(windows, list) or len(windows) != expected_count:
        errors.append(f"{label} requires one occurrence window per occurrence")
    else:
        previous_end = -1.0
        for index, raw_window in enumerate(windows, start=1):
            try:
                start, end = map(float, raw_window)
            except (TypeError, ValueError):
                errors.append(f"{label} occurrence window {index} is invalid")
                continue
            if start < 0 or end <= start or end > source_duration or start < previous_end:
                errors.append(
                    f"{label} occurrence window {index} must be ordered, "
                    "non-overlapping, and inside the bound scene audio"
                )
            normalized_windows.append([start, end])
            previous_end = end
    expected_occurrences = list(range(1, expected_count + 1))
    observed_occurrences = [
        row.get("occurrence") for row in checks if isinstance(row, dict)
    ] if isinstance(checks, list) else []
    normalized_check_windows: list[list[float] | None] = []
    if isinstance(checks, list):
        for row in checks:
            raw_window = row.get("window_seconds") if isinstance(row, dict) else None
            try:
                start, end = map(float, raw_window)
                normalized_check_windows.append([start, end])
            except (TypeError, ValueError):
                normalized_check_windows.append(None)
    if (
        not isinstance(checks, list)
        or len(checks) != expected_count
        or any(not isinstance(row, dict) or row.get("result") != "pass" for row in checks)
        or observed_occurrences != expected_occurrences
        or normalized_check_windows != normalized_windows
    ):
        errors.append(
            f"{label} requires ordered 1..N passing ear_check_results bound "
            "to the declared occurrence windows"
        )
    source_audio_snapshot = artifact_snapshot(source_audio_path, repo_root)
    ear_review_result = None
    machine_review = None
    if acceptance_mode == PRONUNCIATION_MACHINE_ACCEPTANCE_MODE:
        machine_review_path = _resolve(machine_review_raw, repo_root)
        machine_review = _validate_machine_pronunciation_review(
            path=machine_review_path,
            repo_root=repo_root,
            expected_bindings={
                "scene_slug": scene_slug,
                "token": token,
                "spoken_form": spoken_form,
                "source_audio_sha256": source_audio_snapshot["sha256"],
                "occurrence_windows_seconds": normalized_windows,
                "occurrence_results": checks,
            },
            label=f"pronunciation.{token}.{scene_slug}.machine_review",
            errors=errors,
        )
    else:
        ear_review_path = _resolve(ear_review_raw, repo_root)
        ear_review_result = _validate_independent_review(
            path=ear_review_path,
            repo_root=repo_root,
            expected_schema="lecture-animation-pronunciation-review-v2",
            expected_bindings={
                "scene_slug": scene_slug,
                "token": token,
                "spoken_form": spoken_form,
                "source_audio_sha256": source_audio_snapshot["sha256"],
                "occurrence_windows_seconds": normalized_windows,
                "occurrence_results": checks,
            },
            required_checks=(
                "all_occurrences_heard",
                "spoken_form_consistent",
                "no_formal_token_read_aloud",
            ),
            label=f"pronunciation.{token}.{scene_slug}.ear_review",
            errors=errors,
            author_id=author_id,
            expected_review_kind="pronunciation",
        )
    evidence.update(
        {
            "source_audio": source_audio_snapshot,
            "ear_evidence": artifact_snapshot(ear_evidence_path, repo_root),
            "occurrence_windows_seconds": normalized_windows,
            "ear_check_results": checks,
        }
    )
    if ear_review_result is not None:
        _, authority_snapshot = ear_review_result
        evidence["ear_review"] = artifact_snapshot(ear_review_path, repo_root)
        evidence["ear_review_authority"] = authority_snapshot
    if machine_review is not None:
        evidence["machine_review"] = artifact_snapshot(
            _resolve(machine_review_raw, repo_root),
            repo_root,
        )
        evidence["acceptance_mode"] = PRONUNCIATION_MACHINE_ACCEPTANCE_MODE
    return evidence


def run_episode_preflight(
    repo_root: Path,
    episode: Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    readiness_stage = str(contract.get("readiness_stage", "post_tts")).strip()
    if readiness_stage not in {"pre_tts", "post_tts"}:
        errors.append("readiness_stage must be pre_tts or post_tts")
    readiness_scope = str(contract.get("readiness_scope", "full_episode")).strip()
    if readiness_scope not in {"full_episode", "progressive_wave"}:
        errors.append("readiness_scope must be full_episode or progressive_wave")
    author_id = str(contract.get("author_id", "")).strip()
    if not author_id:
        errors.append("readiness contract requires author_id")
    registry_raw = str(contract.get("pronunciation_registry_path", "")).strip()
    canonical_registry_path = (
        repo_root
        / ".agents/skills/lecture-animation-pipeline/references/tts-pronunciation-registry.json"
    )
    registry_path = canonical_registry_path
    if registry_raw and _resolve(registry_raw, repo_root) != canonical_registry_path.resolve():
        errors.append(
            "pronunciation_registry_path must name the canonical Skill registry"
        )
    route_id = str(contract.get("tts_route_id", "")).strip()
    pronunciation_acceptance_mode = str(
        contract.get("pronunciation_acceptance_mode", "human_or_independent")
    ).strip()
    pronunciation_acceptance_authority: dict[str, Any] | None = None
    if pronunciation_acceptance_mode == PRONUNCIATION_MACHINE_ACCEPTANCE_MODE:
        authority_raw = str(
            contract.get("pronunciation_acceptance_authority_path", "")
        ).strip()
        if not authority_raw:
            errors.append(
                "ASR machine pronunciation acceptance requires "
                "pronunciation_acceptance_authority_path"
            )
        else:
            authority_path = _resolve(authority_raw, repo_root)
            try:
                authority = load_json(authority_path)
            except PipelineError as exc:
                errors.append(f"pronunciation acceptance authority is invalid: {exc}")
                authority = {}
            if authority.get("schema") != "lecture-animation-user-authority-v1":
                errors.append(
                    "pronunciation acceptance authority schema must be "
                    "lecture-animation-user-authority-v1"
                )
            if authority.get("decision") not in {"authorize", "approve", "continue"}:
                errors.append("pronunciation acceptance authority is not explicit")
            if authority.get("episode") != _relative(episode, repo_root):
                errors.append("pronunciation acceptance authority episode is invalid")
            if not str(authority.get("exact_user_text", "") or "").strip():
                errors.append("pronunciation acceptance authority text is missing")
            if authority.get("asr_machine_acceptance") is not True:
                errors.append(
                    "pronunciation acceptance authority must explicitly set "
                    "asr_machine_acceptance=true"
                )
            if authority.get("human_review_pending") is not True:
                errors.append(
                    "pronunciation acceptance authority must preserve pending human review"
                )
            if authority.get("quality_gates_unchanged") is not True:
                errors.append(
                    "pronunciation acceptance authority must preserve quality gates"
                )
            if authority_path.is_file():
                pronunciation_acceptance_authority = artifact_snapshot(
                    authority_path, repo_root
                )
    elif pronunciation_acceptance_mode != "human_or_independent":
        errors.append(
            "unknown pronunciation_acceptance_mode: "
            + pronunciation_acceptance_mode
        )
    registry_required = bool(
        readiness_stage == "pre_tts"
        or route_id
        or contract.get("pronunciation_map")
        or contract.get("sensitive_tokens")
    )
    pronunciation_registry = (
        _load_pronunciation_registry(registry_path, errors)
        if registry_required
        else {}
    )
    if route_id and route_id not in dict(pronunciation_registry.get("routes", {})):
        errors.append("readiness contract names an unregistered exact tts_route_id")
    scene_results: list[dict[str, Any]] = []
    narration_by_scene: list[tuple[str, str]] = []
    pronunciation_map = {
        str(key).strip().lower(): value
        for key, value in dict(contract.get("pronunciation_map", {})).items()
        if str(key).strip()
    }
    if pronunciation_map and not route_id:
        errors.append("pronunciation evidence requires a registered exact tts_route_id")
    sensitive_found: set[str] = set()
    pronunciation_evidence: dict[str, Any] = {}
    tts_mapping_evidence: dict[str, Any] = {}
    scene_audio_paths: dict[str, Path] = {}
    narration_lookup: dict[str, str] = {}
    scene_artifacts_lookup: dict[str, dict[str, Any]] = {}
    scene_author_lookup: dict[str, str] = {}
    progressive_artifact: dict[str, Any] | None = None
    progressive_scene_order: dict[str, int] = {}
    progressive_scene_count = 0

    if readiness_scope == "progressive_wave":
        progressive_raw = str(contract.get("progressive_production_path", "")).strip()
        if not progressive_raw:
            errors.append("progressive_wave readiness requires progressive_production_path")
        else:
            progressive_path = _resolve(progressive_raw, repo_root)
            try:
                progressive = load_json(progressive_path)
                progressive_artifact = artifact_snapshot(progressive_path, repo_root)
            except PipelineError as exc:
                errors.append(f"progressive production tracker is invalid: {exc}")
                progressive = {}
            if progressive.get("schema") != "lecture-animation-progressive-production-v2":
                errors.append(
                    "progressive production schema must be lecture-animation-progressive-production-v2"
                )
            progressive_payload = dict(progressive)
            progressive_hash = progressive_payload.pop("production_hash", None)
            if not progressive_hash or progressive_hash != object_hash(progressive_payload):
                errors.append("progressive production hash is invalid")
            tracker_rows = progressive.get("scenes", [])
            if not isinstance(tracker_rows, list) or not tracker_rows:
                errors.append("progressive production tracker requires scenes")
                tracker_rows = []
            tracker_slugs = [
                str(row.get("scene_slug", "")).strip()
                for row in tracker_rows
                if isinstance(row, dict) and str(row.get("scene_slug", "")).strip()
            ]
            if len(tracker_slugs) != len(set(tracker_slugs)):
                errors.append("progressive production tracker contains duplicate scene slugs")
            progressive_scene_order = {
                slug: index for index, slug in enumerate(tracker_slugs)
            }
            progressive_scene_count = len(tracker_slugs)

    scenes = contract.get("scenes", [])
    if not isinstance(scenes, list) or not scenes:
        errors.append("readiness contract must declare at least one scene")
        scenes = []
    seen_slugs: set[str] = set()
    for index, item in enumerate(scenes):
        if not isinstance(item, dict):
            errors.append(f"scene[{index}] must be an object")
            continue
        slug = str(item.get("scene_slug", "")).strip()
        if not slug:
            errors.append(f"scene[{index}] is missing scene_slug")
            continue
        if slug in seen_slugs:
            errors.append(f"duplicate scene_slug in readiness contract: {slug}")
        seen_slugs.add(slug)
        scene_author_id = str(item.get("author_id", author_id)).strip()
        if not scene_author_id:
            errors.append(f"{slug}: scene author_id is missing")
            scene_author_id = author_id
        scene_author_lookup[slug] = scene_author_id
        scene_artifacts: dict[str, Any] = {}
        scene_source_raw = str(item.get("scene_source_path", "")).strip()
        scene_source_root_raw = str(item.get("scene_source_root", "")).strip()
        scene_source_path = _resolve(scene_source_raw, repo_root) if scene_source_raw else None
        scene_source_root = (
            _resolve(scene_source_root_raw, repo_root)
            if scene_source_root_raw
            else None
        )
        if scene_source_path is None or not scene_source_path.is_file():
            errors.append(f"{slug}: scene_source_path must name the exact scene source file")
            source_visible_inventory: list[tuple[str, str]] = []
            source_visible_records: list[dict[str, str]] = []
        elif scene_source_root is None or not scene_source_root.is_dir():
            errors.append(
                f"{slug}: scene_source_root must name the complete scene source package"
            )
            source_visible_inventory = []
            source_visible_records = []
        elif scene_source_path != scene_source_root and scene_source_root not in scene_source_path.parents:
            errors.append(f"{slug}: scene_source_path must live inside scene_source_root")
            source_visible_inventory = []
            source_visible_records = []
        else:
            try:
                scene_artifacts["scene_source"] = artifact_snapshot(
                    scene_source_path, repo_root
                )
                scene_artifacts["scene_source_root"] = artifact_snapshot(
                    scene_source_root, repo_root
                )
            except PipelineError as exc:
                errors.append(f"{slug}: {exc}")
            source_visible_inventory = []
            source_visible_records = []
            for source_file in sorted(scene_source_root.rglob("*.py")):
                if _clean_path(source_file):
                    source_rows = _visible_text_records(
                        source_file,
                        f"{slug}.scene_source_root:{source_file.relative_to(scene_source_root)}",
                        errors,
                    )
                    source_relative = _relative(source_file, repo_root)
                    source_visible_inventory.extend(
                        (row["payload"], source_relative) for row in source_rows
                    )
                    source_visible_records.extend(
                        {
                            "constructor": row["constructor"],
                            "payload": row["payload"],
                            "source_path": source_relative,
                        }
                        for row in source_rows
                    )
            for value, source_relative in source_visible_inventory:
                violation = presentation_boundary_violation(value)
                if violation:
                    errors.append(
                        f"{slug}: visible text {value!r} violates the learner-facing "
                        f"presentation boundary in {source_relative}: {violation}"
                    )
        narration = ""
        narration_path_raw = str(item.get("narration_path", "")).strip()
        if narration_path_raw:
            narration_path = _resolve(narration_path_raw, repo_root)
            if not narration_path.is_file():
                errors.append(f"{slug}: narration_path does not exist: {narration_path_raw}")
            else:
                narration = narration_path.read_text(encoding="utf-8", errors="ignore")
                scene_artifacts["narration"] = artifact_snapshot(narration_path, repo_root)
        elif item.get("narration"):
            narration = str(item["narration"])
            errors.append(f"{slug}: inline narration is not hash-bound; use narration_path")
        else:
            errors.append(f"{slug}: narration_path or narration is required")
        narration_by_scene.append((slug, narration))
        narration_lookup[slug] = narration
        sensitive_found.update(_pronunciation_tokens(narration, contract))

        tts_input_raw = str(item.get("tts_input_path", "")).strip()
        tts_input_path: Path | None = None
        requires_compiled_tts_input = (
            readiness_stage == "pre_tts" or bool(route_id) or bool(pronunciation_map)
        )
        if requires_compiled_tts_input and not tts_input_raw:
            errors.append(f"{slug}: readiness requires tts_input_path")
        elif tts_input_raw:
            tts_input_path = _resolve(tts_input_raw, repo_root)
            if not tts_input_path.is_file():
                errors.append(f"{slug}: tts_input_path does not exist: {tts_input_raw}")
                tts_input_path = None
            else:
                scene_artifacts["tts_input"] = artifact_snapshot(
                    tts_input_path, repo_root
                )
        mapping_raw = str(item.get("tts_input_mapping_path", "")).strip()
        if tts_input_path is not None:
            if not mapping_raw:
                errors.append(f"{slug}: tts_input_mapping_path is required with tts_input_path")
            elif not narration_path_raw:
                errors.append(f"{slug}: exact TTS mapping requires narration_path")
            else:
                mapping_path = _resolve(mapping_raw, repo_root)
                if not mapping_path.is_file():
                    errors.append(
                        f"{slug}: tts_input_mapping_path does not exist: {mapping_raw}"
                    )
                else:
                    mapping_evidence = _validate_tts_input_mapping(
                        mapping_path=mapping_path,
                        formal_script_path=_resolve(narration_path_raw, repo_root),
                        tts_input_path=tts_input_path,
                        scene_slug=slug,
                        route_id=route_id,
                        pronunciation_registry=pronunciation_registry,
                        repo_root=repo_root,
                        errors=errors,
                    )
                    if mapping_evidence is not None:
                        tts_mapping_evidence[slug] = mapping_evidence
                        sensitive_found.update(
                            row["token_key"]
                            for row in mapping_evidence["occurrences"]
                        )
                        scene_artifacts["tts_input_mapping"] = mapping_evidence[
                            "mapping"
                        ]

        duration = float(item.get("duration_seconds", 0.0) or 0.0)
        audio_raw = str(item.get("audio_path", "")).strip()
        if audio_raw:
            audio_path = _resolve(audio_raw, repo_root)
            if not audio_path.is_file():
                errors.append(f"{slug}: audio_path does not exist: {audio_raw}")
            else:
                scene_artifacts["audio"] = artifact_snapshot(audio_path, repo_root)
                scene_audio_paths[slug] = audio_path
                if duration <= 0 and audio_path.suffix.lower() == ".wav":
                    duration = _wav_duration(audio_path)
        if duration <= 0:
            errors.append(f"{slug}: duration_seconds or readable WAV audio_path is required")
        if duration > 90:
            exception = item.get("scene_split_exception")
            if not isinstance(exception, dict) or len(str(exception.get("reason", "")).strip()) < 12:
                errors.append(f"{slug}: {duration:.3f}s exceeds 90s without a persisted split exception")
        elif duration > 75:
            warnings.append(f"{slug}: {duration:.3f}s exceeds the 75s high-risk threshold")

        concept_load = str(item.get("concept_load", "normal")).strip().lower()
        if concept_load in {"high", "concept_heavy"}:
            if not item.get("prerequisites"):
                errors.append(f"{slug}: concept-heavy scene is missing explicit prerequisites")
            new_terms = [
                str(value).strip()
                for value in item.get("new_terms", [])
                if str(value).strip()
            ]
            if not new_terms:
                errors.append(f"{slug}: concept-heavy scene is missing explicit new_terms")
            novice_bridge = item.get("novice_bridge")
            errors.extend(_bridge_errors(novice_bridge, narration, new_terms, slug))
            novice_review_raw = str(item.get("novice_bridge_review_path", "")).strip()
            if not novice_review_raw:
                errors.append(
                    f"{slug}: concept-heavy scene requires novice_bridge_review_path"
                )
            elif isinstance(novice_bridge, dict) and scene_artifacts.get("narration"):
                novice_review_path = _resolve(novice_review_raw, repo_root)
                review_result = _validate_independent_review(
                    path=novice_review_path,
                    repo_root=repo_root,
                    expected_schema="lecture-animation-novice-bridge-review-v2",
                    expected_bindings={
                        "scene_slug": slug,
                        "narration_sha256": scene_artifacts["narration"]["sha256"],
                        "bridge_hash": _bridge_evidence_hash(
                            novice_bridge, new_terms
                        ),
                        "new_terms": new_terms,
                    },
                    required_checks=(
                        "explanation_relevant",
                        "referent_supports_term",
                        "learner_action_teaches_term",
                        "term_follows_referent",
                    ),
                    label=f"{slug}.novice_bridge_review",
                    errors=errors,
                    author_id=scene_author_id,
                    expected_review_kind="novice_bridge",
                )
                if review_result is not None:
                    _, authority_snapshot = review_result
                    scene_artifacts["novice_bridge_review"] = artifact_snapshot(
                        novice_review_path, repo_root
                    )
                    scene_artifacts[
                        "novice_bridge_review_authority"
                    ] = authority_snapshot

        screen_text_count = _evidence_inventory_count(
            rows=item.get("screen_text_inventory"),
            repo_root=repo_root,
            allowed_root=scene_source_root or repo_root,
            label=f"{slug}.screen_text_inventory",
            errors=errors,
            artifacts=scene_artifacts,
        )
        declared_visible_inventory: list[tuple[str, str]] = []
        if isinstance(item.get("screen_text_inventory", []), list):
            for row in item.get("screen_text_inventory", []):
                if not isinstance(row, dict):
                    continue
                source_raw = str(row.get("source_path", "")).strip()
                if not source_raw:
                    continue
                try:
                    normalized_source = _relative(
                        _resolve(source_raw, repo_root), repo_root
                    )
                except PipelineError:
                    normalized_source = source_raw
                declared_visible_inventory.append(
                    (str(row.get("text", "")), normalized_source)
                )
        if Counter(declared_visible_inventory) != Counter(source_visible_inventory):
            errors.append(
                f"{slug}: screen_text_inventory must exactly match all literal "
                "Text/MarkupText/Paragraph constructors by file in scene_source_root"
            )
        declared_screen_text_count = int(item.get("screen_text_count", screen_text_count) or 0)
        if declared_screen_text_count != screen_text_count:
            errors.append(
                f"{slug}: screen_text_count {declared_screen_text_count} does not match "
                f"evidence inventory count {screen_text_count}"
            )
        default_screen_text_budget = int(contract.get("screen_text_budget", 12) or 12)
        screen_text_budget = int(
            item.get("screen_text_budget", default_screen_text_budget)
            or default_screen_text_budget
        )
        if screen_text_budget > default_screen_text_budget:
            exception = item.get("screen_text_budget_exception")
            duration_bound_cap = max(
                default_screen_text_budget,
                int(duration / 5.0) + 1,
            )
            if (
                not isinstance(exception, dict)
                or len(str(exception.get("reason", "")).strip()) < 24
                or len(str(exception.get("transient_text_plan", "")).strip()) < 16
                or len(str(exception.get("semantic_contract_path", "")).strip()) < 8
            ):
                errors.append(
                    f"{slug}: an increased screen_text_budget requires a reason, "
                    "transient_text_plan, and semantic_contract_path"
                )
            if screen_text_budget > duration_bound_cap:
                errors.append(
                    f"{slug}: screen_text_budget {screen_text_budget} exceeds the "
                    f"duration-bound cap {duration_bound_cap}"
                )
        if screen_text_count > screen_text_budget:
            errors.append(
                f"{slug}: screen text count {screen_text_count} exceeds budget {screen_text_budget}"
            )
        if readiness_stage == "post_tts":
            semantics_raw = str(
                item.get("screen_text_semantic_contract_path", "")
            ).strip()
            if not semantics_raw:
                errors.append(
                    f"{slug}: post_tts readiness requires "
                    "screen_text_semantic_contract_path"
                )
            else:
                semantics_path = _resolve(semantics_raw, repo_root)
                semantics = _validate_episode_screen_text_semantics(
                    path=semantics_path,
                    repo_root=repo_root,
                    source_records=source_visible_records,
                    slug=slug,
                    errors=errors,
                )
                if semantics is not None:
                    scene_artifacts["screen_text_semantic_contract"] = (
                        artifact_snapshot(semantics_path, repo_root)
                    )
        connector_count = _evidence_inventory_count(
            rows=item.get("summary_connector_inventory"),
            repo_root=repo_root,
            allowed_root=scene_source_root or repo_root,
            label=f"{slug}.summary_connector_inventory",
            errors=errors,
            artifacts=scene_artifacts,
        )
        declared_connector_count = int(
            item.get("summary_connector_count", connector_count) or 0
        )
        if declared_connector_count != connector_count:
            errors.append(
                f"{slug}: summary_connector_count {declared_connector_count} does not match "
                f"evidence inventory count {connector_count}"
            )
        connector_budget = int(contract.get("summary_connector_budget", 4) or 4)
        if connector_count > connector_budget:
            errors.append(
                f"{slug}: summary connector count {connector_count} exceeds budget {connector_budget}"
            )

        alignment_pace = None
        alignment_raw = str(item.get("word_alignment", "")).strip()
        if alignment_raw:
            alignment_path = _resolve(alignment_raw, repo_root)
            if not alignment_path.is_file():
                errors.append(f"{slug}: word_alignment does not exist: {alignment_raw}")
            else:
                scene_artifacts["word_alignment"] = artifact_snapshot(alignment_path, repo_root)
                alignment_pace = _rolling_pace(_alignment_words(load_json(alignment_path)))
                hard_limit = float(contract.get("rolling_pace_hard_limit", 5.5) or 5.5)
                warning_limit = float(contract.get("rolling_pace_warning_limit", 4.8) or 4.8)
                if alignment_pace > hard_limit:
                    errors.append(
                        f"{slug}: rolling pace {alignment_pace:.3f} tokens/s exceeds {hard_limit:.3f}"
                    )
                elif alignment_pace > warning_limit:
                    warnings.append(
                        f"{slug}: rolling pace {alignment_pace:.3f} tokens/s exceeds {warning_limit:.3f}"
                    )

        average_pace = len(TOKEN_PATTERN.findall(narration)) / duration if duration > 0 else None
        if alignment_pace is None and average_pace is not None:
            hard_limit = float(contract.get("rolling_pace_hard_limit", 5.5) or 5.5)
            warning_limit = float(contract.get("rolling_pace_warning_limit", 4.8) or 4.8)
            if average_pace > hard_limit:
                errors.append(
                    f"{slug}: average pace {average_pace:.3f} tokens/s exceeds {hard_limit:.3f}; "
                    "word alignment is required to localize the repair"
                )
            elif average_pace > warning_limit:
                warnings.append(
                    f"{slug}: average pace {average_pace:.3f} tokens/s exceeds {warning_limit:.3f}"
                )
        scene_results.append(
            {
                "scene_slug": slug,
                "author_id": scene_author_id,
                "duration_seconds": round(duration, 3),
                "average_tokens_per_second": round(average_pace, 3) if average_pace is not None else None,
                "rolling_tokens_per_second": (
                    round(alignment_pace, 3) if alignment_pace is not None else None
                ),
                "concept_load": concept_load,
                "screen_text_count": screen_text_count,
                "summary_connector_count": connector_count,
                "artifacts": scene_artifacts,
            }
        )
        scene_artifacts_lookup[slug] = scene_artifacts

    wave_scene_slugs = [slug for slug, _ in narration_by_scene]
    if readiness_scope == "progressive_wave":
        declared_wave = [
            str(value).strip()
            for value in contract.get("wave_scene_slugs", [])
            if str(value).strip()
        ]
        if declared_wave != wave_scene_slugs:
            errors.append(
                "progressive_wave wave_scene_slugs must exactly match scenes in order"
            )
        missing_from_tracker = sorted(
            set(wave_scene_slugs) - set(progressive_scene_order)
        )
        if missing_from_tracker:
            errors.append(
                "progressive wave scenes are missing from progressive production: "
                + ", ".join(missing_from_tracker)
            )
        ordered_positions = [
            progressive_scene_order[slug]
            for slug in wave_scene_slugs
            if slug in progressive_scene_order
        ]
        if ordered_positions != sorted(ordered_positions):
            errors.append("progressive wave scenes must follow episode scene order")

    duplicate_boundaries: list[dict[str, Any]] = []
    for (left_slug, left), (right_slug, right) in zip(narration_by_scene, narration_by_scene[1:]):
        if readiness_scope == "progressive_wave":
            left_index = progressive_scene_order.get(left_slug)
            right_index = progressive_scene_order.get(right_slug)
            if left_index is None or right_index != left_index + 1:
                continue
        duplicates = _boundary_duplicates(left, right)
        if duplicates:
            duplicate_boundaries.append(
                {"left_scene": left_slug, "right_scene": right_slug, "clauses": duplicates}
            )
            errors.append(f"{left_slug}->{right_slug}: duplicate narration at scene boundary")

    all_narration = "\n".join(value for _, value in narration_by_scene)
    fixed_ending_raw = str(contract.get("fixed_ending", DEFAULT_FIXED_ENDING)).strip()
    fixed_ending_contract = contract.get("fixed_ending_contract", {})
    if not fixed_ending_raw:
        errors.append("readiness contract requires an explicit learner-facing fixed_ending")
    if (
        not isinstance(fixed_ending_contract, dict)
        or fixed_ending_contract.get("role") not in {
            "mathematical_conclusion",
            "learner_facing_math_question",
        }
        or len(str(fixed_ending_contract.get("learner_job", "")).strip()) < 16
        or len(str(fixed_ending_contract.get("math_anchor", "")).strip()) < 4
        or fixed_ending_contract.get("externalizes_production_intent") is not False
    ):
        errors.append(
            "fixed_ending_contract must bind a learner-facing mathematical role, "
            "learner_job, math_anchor, and externalizes_production_intent=false"
        )
    ending_violation = presentation_boundary_violation(fixed_ending_raw)
    if ending_violation:
        errors.append(
            f"fixed ending violates the learner-facing presentation boundary: {ending_violation}"
        )
    fixed_ending_source_artifact: dict[str, Any] | None = None
    ending_text = all_narration
    if readiness_scope == "progressive_wave":
        fixed_ending_source_raw = str(
            contract.get("fixed_ending_source_path", "")
        ).strip()
        if not fixed_ending_source_raw:
            errors.append("progressive_wave readiness requires fixed_ending_source_path")
            ending_text = ""
        else:
            fixed_ending_source_path = _resolve(fixed_ending_source_raw, repo_root)
            try:
                fixed_ending_source_path.resolve().relative_to(episode.resolve())
            except ValueError:
                errors.append("fixed_ending_source_path must live inside the episode")
            if not fixed_ending_source_path.is_file():
                errors.append("fixed_ending_source_path does not exist")
                ending_text = ""
            else:
                ending_text = fixed_ending_source_path.read_text(
                    encoding="utf-8", errors="ignore"
                )
                fixed_ending_source_artifact = artifact_snapshot(
                    fixed_ending_source_path, repo_root
                )
    expected_ending = _normalized_clause(fixed_ending_raw)
    ending_count = _normalized_clause(ending_text).count(expected_ending) if expected_ending else 0
    if ending_count != 1:
        errors.append(f"fixed ending must appear exactly once; observed {ending_count}")

    registered_tokens = {
        str(token).casefold()
        for token in dict(pronunciation_registry.get("tokens", {}))
    }
    unregistered_sensitive = sorted(
        token for token in sensitive_found if token.casefold() not in registered_tokens
    )
    if unregistered_sensitive:
        errors.append(
            "canonical TTS registry is missing sensitive tokens: "
            + ", ".join(unregistered_sensitive)
        )
    missing_pronunciations = (
        []
        if readiness_stage == "pre_tts"
        else sorted(
            token for token in sensitive_found if token.lower() not in pronunciation_map
        )
    )
    if missing_pronunciations:
        errors.append(
            "pronunciation map is missing sensitive tokens: " + ", ".join(missing_pronunciations)
        )
    for token in sorted(
        token
        for token in sensitive_found - set(missing_pronunciations)
        if token.lower() in pronunciation_map
    ):
        mapping = pronunciation_map.get(token.lower())
        if not isinstance(mapping, dict):
            errors.append(f"pronunciation mapping for {token} must be an evidence-bound object")
            continue
        scene_counts = {
            scene_slug: _canonical_formal_occurrence_count(
                narration,
                token,
                pronunciation_registry,
            )
            for scene_slug, narration in narration_lookup.items()
            if _canonical_formal_occurrence_count(
                narration,
                token,
                pronunciation_registry,
            )
            > 0
        }
        raw_bindings = mapping.get("bindings")
        if raw_bindings is None:
            bindings: list[Any] = [mapping]
        elif not isinstance(raw_bindings, list) or not raw_bindings:
            errors.append(
                f"pronunciation mapping for {token}.bindings must be a non-empty list"
            )
            continue
        else:
            bindings = raw_bindings
        if len(scene_counts) > 1 and raw_bindings is None:
            errors.append(
                f"pronunciation mapping for {token} spans multiple scenes and requires "
                "one evidence object per scene in bindings"
            )
        bound_slugs = [
            str(binding.get("scene_slug", "")).strip()
            for binding in bindings
            if isinstance(binding, dict)
        ]
        if len(bound_slugs) != len(set(bound_slugs)):
            errors.append(
                f"pronunciation mapping for {token} contains duplicate scene bindings"
            )
        missing_scene_bindings = sorted(set(scene_counts) - set(bound_slugs))
        extra_scene_bindings = sorted(set(bound_slugs) - set(scene_counts))
        if missing_scene_bindings:
            errors.append(
                f"pronunciation mapping for {token} is missing scene bindings: "
                + ", ".join(missing_scene_bindings)
            )
        if extra_scene_bindings:
            errors.append(
                f"pronunciation mapping for {token} contains scene bindings without "
                "formal occurrences: " + ", ".join(extra_scene_bindings)
            )
        binding_evidence: list[dict[str, Any]] = []
        for binding in bindings:
            if not isinstance(binding, dict):
                errors.append(
                    f"pronunciation mapping for {token} contains a non-object binding"
                )
                continue
            scene_slug = str(binding.get("scene_slug", "")).strip()
            evidence = _validate_pronunciation_binding(
                token=token,
                binding=binding,
                formal_count=scene_counts.get(scene_slug, 0),
                readiness_stage=readiness_stage,
                repo_root=repo_root,
                narration_lookup=narration_lookup,
                scene_audio_paths=scene_audio_paths,
                author_id=scene_author_lookup.get(scene_slug, author_id),
                route_id=route_id,
                pronunciation_registry=pronunciation_registry,
                exact_mapping_evidence=tts_mapping_evidence.get(scene_slug),
                acceptance_mode=pronunciation_acceptance_mode,
                errors=errors,
            )
            if evidence is not None:
                binding_evidence.append(evidence)
        pronunciation_evidence[token] = {
            "formal_occurrences": sum(scene_counts.values()),
            "bindings": binding_evidence,
        }

    required_bridges = {
        str(value).strip()
        for value in contract.get("required_concept_bridges", [])
        if str(value).strip()
    }
    auto_bridge_requirements: dict[str, tuple[int, str, str]] = {}
    for term, bridge_id in AUTO_NOVICE_BRIDGE_TERMS.items():
        for scene_index, (scene_slug, narration) in enumerate(narration_by_scene):
            if term not in narration:
                continue
            previous = auto_bridge_requirements.get(bridge_id)
            candidate = (scene_index, scene_slug, term)
            if previous is None or candidate[0] < previous[0]:
                auto_bridge_requirements[bridge_id] = candidate
            break
    required_bridges.update(auto_bridge_requirements)
    supplied_bridges: set[str] = set()
    for item in contract.get("concept_bridges", []):
        if not isinstance(item, dict):
            continue
        bridge_id = str(item.get("bridge_id", "")).strip()
        scene_slug = str(item.get("scene_slug", "")).strip()
        term = str(item.get("term", bridge_id)).strip()
        if not bridge_id or scene_slug not in narration_lookup:
            continue
        bridge_errors = _bridge_errors(item, narration_lookup[scene_slug], [term], bridge_id)
        automatic_requirement = auto_bridge_requirements.get(bridge_id)
        if automatic_requirement is not None:
            _, required_scene, required_term = automatic_requirement
            if scene_slug != required_scene or term != required_term:
                bridge_errors.append(
                    f"{bridge_id}: automatic novice term {required_term!r} must be "
                    f"bridged at its first scene {required_scene}"
                )
        review_raw = str(item.get("novice_bridge_review_path", "")).strip()
        if not review_raw:
            bridge_errors.append(
                f"{bridge_id}: concept bridge requires novice_bridge_review_path"
            )
        else:
            narration_artifact = scene_artifacts_lookup.get(scene_slug, {}).get(
                "narration"
            )
            if isinstance(narration_artifact, dict):
                review_path = _resolve(review_raw, repo_root)
                review_result = _validate_independent_review(
                    path=review_path,
                    repo_root=repo_root,
                    expected_schema="lecture-animation-novice-bridge-review-v2",
                    expected_bindings={
                        "scene_slug": scene_slug,
                        "narration_sha256": narration_artifact["sha256"],
                        "bridge_hash": _bridge_evidence_hash(item, [term]),
                        "new_terms": [term],
                    },
                    required_checks=(
                        "explanation_relevant",
                        "referent_supports_term",
                        "learner_action_teaches_term",
                        "term_follows_referent",
                    ),
                    label=f"{bridge_id}.novice_bridge_review",
                    errors=bridge_errors,
                    author_id=author_id,
                    expected_review_kind="novice_bridge",
                )
                if review_result is not None:
                    _, authority_snapshot = review_result
                    scene_artifacts_lookup[scene_slug][
                        f"concept_bridge_review_{bridge_id}"
                    ] = artifact_snapshot(review_path, repo_root)
                    scene_artifacts_lookup[scene_slug][
                        f"concept_bridge_review_authority_{bridge_id}"
                    ] = authority_snapshot
        if bridge_errors:
            errors.extend(bridge_errors)
        else:
            supplied_bridges.add(bridge_id)
    missing_bridges = sorted(required_bridges - supplied_bridges)
    if missing_bridges:
        errors.append("required novice concept bridges are missing: " + ", ".join(missing_bridges))

    result = {
        "schema": "lecture-animation-episode-readiness-receipt-v2",
        "created_at": utc_now(),
        "episode": _relative(episode, repo_root),
        "readiness_stage": readiness_stage,
        "readiness_scope": readiness_scope,
        "author_id": author_id,
        "contract_hash": object_hash(contract),
        "status": "blocked" if errors else ("warn" if warnings else "pass"),
        "errors": errors,
        "warnings": warnings,
        "scenes": scene_results,
        "duplicate_boundaries": duplicate_boundaries,
        "pronunciation_tokens_found": sorted(sensitive_found),
        "pronunciation_tokens_mapped": sorted(pronunciation_map),
        "pronunciation_evidence": pronunciation_evidence,
        "pronunciation_acceptance_mode": pronunciation_acceptance_mode,
        "pronunciation_acceptance_authority": pronunciation_acceptance_authority,
        "tts_route_id": route_id,
        "pronunciation_registry": (
            artifact_snapshot(registry_path, repo_root)
            if pronunciation_registry and route_id
            else None
        ),
        "tts_input_mapping_evidence": tts_mapping_evidence,
        "fixed_ending_count": ending_count,
        "fixed_ending_source": fixed_ending_source_artifact,
        "progressive_production": progressive_artifact,
        "planned_scene_count": progressive_scene_count if readiness_scope == "progressive_wave" else len(scene_results),
        "wave_scene_count": len(scene_results),
        "required_concept_bridges": sorted(required_bridges),
        "supplied_concept_bridges": sorted(supplied_bridges),
    }
    evidence_payload = dict(result)
    evidence_payload.pop("created_at", None)
    result["readiness_evidence_hash"] = object_hash(evidence_payload)
    result["receipt_hash"] = object_hash(result)
    return result


def command_episode_preflight(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    episode = _resolve(args.episode, repo_root)
    contract_path = _resolve(args.contract, repo_root)
    contract = _load_contract(contract_path)
    result = run_episode_preflight(repo_root, episode, contract)
    result.pop("receipt_hash", None)
    result["contract_artifact"] = artifact_snapshot(contract_path, repo_root)
    result["receipt_hash"] = object_hash(result)
    write_json(_resolve(args.output, repo_root), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if args.require_clean and result["status"] == "blocked" else 0


def validate_episode_readiness_receipt(
    receipt_path: Path,
    repo_root: Path,
    episode: Path,
    scene_slug: str | None = None,
    expected_scene_slugs: set[str] | None = None,
    required_stage: str | None = None,
) -> dict[str, Any]:
    receipt = load_json(receipt_path)
    payload = dict(receipt)
    stored_hash = payload.pop("receipt_hash", None)
    if (
        receipt.get("schema") != "lecture-animation-episode-readiness-receipt-v2"
        or stored_hash != object_hash(payload)
        or receipt.get("status") == "blocked"
        or receipt.get("errors")
        or receipt.get("episode") != _relative(episode, repo_root)
    ):
        raise PipelineError("episode readiness receipt is invalid or blocked")
    receipt_evidence = dict(receipt)
    receipt_evidence.pop("created_at", None)
    receipt_evidence.pop("receipt_hash", None)
    stored_evidence_hash = receipt_evidence.pop("readiness_evidence_hash", None)
    receipt_evidence.pop("contract_artifact", None)
    if not stored_evidence_hash or stored_evidence_hash != object_hash(receipt_evidence):
        raise PipelineError(
            "episode readiness receipt payload does not match its readiness evidence hash"
        )
    artifacts: list[dict[str, Any]] = []

    def collect_artifacts(value: Any) -> None:
        if isinstance(value, dict):
            if {
                "path",
                "kind",
                "sha256",
            }.issubset(value):
                artifacts.append(value)
                return
            for child in value.values():
                collect_artifacts(child)
        elif isinstance(value, list):
            for child in value:
                collect_artifacts(child)

    if not isinstance(receipt.get("contract_artifact"), dict):
        raise PipelineError("episode readiness receipt is missing its contract artifact binding")
    artifacts.append(receipt["contract_artifact"])
    for scene in receipt.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        if not isinstance(scene.get("artifacts", {}).get("narration"), dict):
            raise PipelineError(
                f"episode readiness scene {scene.get('scene_slug')} lacks narration hash binding"
            )
        artifacts.extend(
            value
            for value in dict(scene.get("artifacts", {})).values()
            if isinstance(value, dict)
        )
    collect_artifacts(receipt.get("pronunciation_registry"))
    collect_artifacts(receipt.get("pronunciation_acceptance_authority"))
    collect_artifacts(receipt.get("tts_input_mapping_evidence", {}))
    collect_artifacts(receipt.get("pronunciation_evidence", {}))
    for artifact in artifacts:
        path = _resolve(str(artifact.get("path", "")), repo_root)
        current = artifact_snapshot(path, repo_root)
        if current.get("sha256") != artifact.get("sha256"):
            raise PipelineError(
                f"episode readiness receipt is stale for {artifact.get('path')}"
            )
    contract_path = _resolve(str(receipt["contract_artifact"].get("path", "")), repo_root)
    contract = _load_contract(contract_path)
    current = run_episode_preflight(repo_root, episode, contract)
    if current.get("readiness_evidence_hash") != receipt.get("readiness_evidence_hash"):
        raise PipelineError(
            "episode readiness receipt does not match a fresh canonical preflight"
        )
    scene_slugs = {
        str(item.get("scene_slug"))
        for item in receipt.get("scenes", [])
        if isinstance(item, dict)
    }
    if scene_slug and scene_slug not in scene_slugs:
        raise PipelineError(f"episode readiness receipt does not cover scene {scene_slug}")
    stage = str(receipt.get("readiness_stage", "")).strip()
    if stage not in {"pre_tts", "post_tts"}:
        raise PipelineError("episode readiness receipt has an invalid readiness_stage")
    if required_stage and stage != required_stage:
        raise PipelineError(
            f"episode readiness receipt stage {stage} cannot satisfy {required_stage}"
        )
    if expected_scene_slugs is not None and scene_slugs != expected_scene_slugs:
        missing = sorted(expected_scene_slugs - scene_slugs)
        extra = sorted(scene_slugs - expected_scene_slugs)
        raise PipelineError(
            "episode readiness receipt scene set does not match production; "
            f"missing={missing}, extra={extra}"
        )
    return receipt


def _parse_named_paths(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise PipelineError(f"expected NAME=PATH, received: {raw}")
        name, path = raw.split("=", 1)
        name, path = name.strip(), path.strip()
        if not name or not path or name in result:
            raise PipelineError(f"invalid or duplicate named path: {raw}")
        result[name] = path
    return result


def _text_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        if root.suffix.lower() in TEXT_SUFFIXES and root.stat().st_size <= 5 * 1024 * 1024:
            yield root
        return
    for path in root.rglob("*"):
        if (
            path.is_file()
            and _clean_path(path)
            and path.suffix.lower() in TEXT_SUFFIXES
            and path.stat().st_size <= 5 * 1024 * 1024
        ):
            yield path


def _validate_portability_roles(
    *,
    repo_root: Path,
    episode: Path,
    required_artifacts: dict[str, str],
    artifacts: dict[str, Any],
    errors: list[str],
) -> None:
    lecture = _resolve(required_artifacts.get("lecture", ""), repo_root)
    if (
        not lecture.is_file()
        or lecture.suffix.lower() not in {".md", ".txt"}
        or len(lecture.read_text(encoding="utf-8", errors="ignore").strip()) < 100
    ):
        errors.append("lecture: expected a nontrivial Markdown/text lecture")

    source = _resolve(required_artifacts.get("source", ""), repo_root)
    code_suffixes = {".py", ".js", ".jsx", ".ts", ".tsx", ".ipynb"}
    source_files = (
        [
            path
            for path in source.rglob("*")
            if path.is_file()
            and _clean_path(path)
            and path.suffix.lower() in code_suffixes
            and path.stat().st_size > 0
        ]
        if source.is_dir()
        else []
    )
    if not source_files:
        errors.append("source: expected a nonempty source directory with executable code")

    audio = _resolve(required_artifacts.get("audio", ""), repo_root)
    audio_files = (
        [audio]
        if audio.is_file()
        else sorted(path for path in audio.rglob("*.wav") if path.is_file())
        if audio.is_dir()
        else []
    )
    if not audio_files:
        errors.append("audio: expected at least one WAV scene-audio file")
    else:
        for path in audio_files:
            try:
                if _wav_duration(path) <= 0.1:
                    errors.append(f"audio: WAV is empty or too short: {_relative(path, repo_root)}")
            except (wave.Error, EOFError) as exc:
                errors.append(f"audio: undecodable WAV {_relative(path, repo_root)}: {exc}")

    final_video = _resolve(required_artifacts.get("final_video", ""), repo_root)
    ffprobe = shutil.which("ffprobe")
    if not final_video.is_file() or final_video.suffix.lower() != ".mp4":
        errors.append("final_video: expected an MP4 file")
    elif not ffprobe:
        errors.append("final_video: ffprobe is required for decode validation")
    else:
        probe = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_type,width,height:format=duration",
                "-of",
                "json",
                str(final_video),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        try:
            decoded = json.loads(probe.stdout) if probe.returncode == 0 else {}
            streams = decoded.get("streams", [])
            duration = float(decoded.get("format", {}).get("duration", 0.0) or 0.0)
        except (json.JSONDecodeError, TypeError, ValueError):
            streams, duration = [], 0.0
        if not streams or duration <= 0:
            errors.append("final_video: ffprobe did not find a decodable video stream")

    final_srt = _resolve(required_artifacts.get("final_srt", ""), repo_root)
    if (
        not final_srt.is_file()
        or final_srt.suffix.lower() != ".srt"
        or not SRT_TIMESTAMP.search(
            final_srt.read_text(encoding="utf-8", errors="ignore")
        )
    ):
        errors.append("final_srt: expected a nonempty SRT with at least one valid cue")

    manifest_path = _resolve(required_artifacts.get("final_manifest", ""), repo_root)
    try:
        manifest = load_json(manifest_path)
    except PipelineError as exc:
        errors.append(f"final_manifest: invalid JSON manifest: {exc}")
        return
    if not str(manifest.get("schema", "")).startswith("lecture-animation-"):
        errors.append("final_manifest: schema must be a lecture-animation manifest")
    if str(manifest.get("episode", "")) != episode.name:
        errors.append("final_manifest: episode binding does not match the audited episode")
    if float(manifest.get("duration_seconds", 0.0) or 0.0) <= 0:
        errors.append("final_manifest: duration_seconds must be positive")
    video_hash = artifacts.get("final_video", {}).get("sha256")
    if manifest.get("upload_mp4_sha256") != video_hash:
        errors.append("final_manifest: upload_mp4_sha256 does not match final_video")
    srt_hash = artifacts.get("final_srt", {}).get("sha256")
    manifest_srt_hashes = {
        manifest.get("burned_subtitle_source_sha256"),
        manifest.get("publication_srt_sha256"),
    }
    if srt_hash not in manifest_srt_hashes:
        errors.append(
            "final_manifest: subtitle SHA does not match final_srt"
        )


def run_portability_audit(
    repo_root: Path,
    episode: Path,
    required_artifacts: dict[str, str],
    authoritative_roots: list[str],
) -> dict[str, Any]:
    errors: list[str] = []
    if not required_artifacts:
        errors.append("portability audit requires at least one required artifact")
    if not authoritative_roots:
        errors.append("portability audit requires at least one authoritative root")
    artifacts: dict[str, Any] = {}
    missing_roles = sorted(PORTABILITY_REQUIRED_ROLES - set(required_artifacts))
    if missing_roles:
        errors.append(
            "portability audit is missing required artifact roles: " + ", ".join(missing_roles)
        )
    for name, raw in required_artifacts.items():
        path = _resolve(raw, repo_root)
        try:
            path.relative_to(episode.resolve())
        except ValueError:
            errors.append(f"{name}: required artifact must live inside the episode directory")
        try:
            snapshot = artifact_snapshot(path, repo_root)
            artifacts[name] = snapshot
            if int(snapshot.get("file_count", 0) or 0) < 1 or int(
                snapshot.get("size", 0) or 0
            ) < 1:
                errors.append(f"{name}: required artifact is empty")
        except PipelineError as exc:
            errors.append(f"{name}: {exc}")
    if not missing_roles:
        _validate_portability_roles(
            repo_root=repo_root,
            episode=episode,
            required_artifacts=required_artifacts,
            artifacts=artifacts,
            errors=errors,
        )

    roots: list[dict[str, Any]] = []
    dangling_references: list[dict[str, Any]] = []
    for raw in authoritative_roots:
        root = _resolve(raw, repo_root)
        if not root.exists():
            errors.append(f"authoritative root does not exist: {raw}")
            continue
        if not root.is_dir():
            errors.append(f"authoritative root must be a directory, not a single file: {raw}")
            continue
        try:
            root.relative_to(episode.resolve())
        except ValueError:
            errors.append(f"authoritative root must live inside the episode directory: {raw}")
        try:
            root_relative = _relative(root, repo_root)
        except PipelineError as exc:
            errors.append(str(exc))
            continue
        scanned = 0
        for path in _text_files(root):
            scanned += 1
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in WORKTREE_REFERENCE.finditer(text):
                dangling_references.append(
                    {
                        "path": _relative(path, repo_root),
                        "reference": match.group(0),
                    }
                )
        roots.append({"path": root_relative, "text_files_scanned": scanned})
        if scanned == 0:
            errors.append(f"authoritative root contains no auditable text files: {raw}")
    source_raw = required_artifacts.get("source")
    if source_raw:
        source_path = _resolve(source_raw, repo_root)
        root_paths = [_resolve(raw, repo_root) for raw in authoritative_roots]
        if not any(
            root.is_dir()
            and (source_path == root or root in source_path.parents)
            for root in root_paths
        ):
            errors.append(
                "the required source artifact is not covered by an authoritative root"
            )
    if dangling_references:
        errors.append(
            f"authoritative sources contain {len(dangling_references)} temporary worktree references"
        )

    result = {
        "schema": "lecture-animation-portability-audit-v2",
        "compiler": "pipeline_v2.audit-portability",
        "created_at": utc_now(),
        "episode": _relative(episode, repo_root),
        "status": "blocked" if errors else "pass",
        "errors": errors,
        "required_artifacts": artifacts,
        "authoritative_roots": roots,
        "dangling_worktree_references": dangling_references,
    }
    result["receipt_hash"] = object_hash(result)
    return result


def command_audit_portability(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    episode = _resolve(args.episode, repo_root)
    result = run_portability_audit(
        repo_root,
        episode,
        _parse_named_paths(args.required_artifact),
        args.authoritative_root or [],
    )
    write_json(_resolve(args.output, repo_root), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if args.require_clean and result["status"] == "blocked" else 0


def command_build_task_capsule(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    artifacts = {
        name: artifact_snapshot(_resolve(raw, repo_root), repo_root)
        for name, raw in _parse_named_paths(args.artifact).items()
    }
    gates = _parse_named_paths(args.gate)
    result = {
        "schema": "lecture-animation-task-capsule-v2",
        "created_at": utc_now(),
        "scene_slug": args.scene_slug,
        "role": args.role,
        "task": args.task,
        "artifacts": artifacts,
        "gates": gates,
        "report_contract": [
            "status",
            "artifact_paths",
            "artifact_hashes",
            "gate_results",
            "blockers",
            "next_action",
        ],
    }
    result["capsule_hash"] = object_hash(result)
    write_json(_resolve(args.output, repo_root), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_promote_scene(args: argparse.Namespace) -> int:
    source_root = Path(args.source_root).resolve()
    canonical_root = Path(args.canonical_root).resolve()
    if source_root == canonical_root:
        raise PipelineError("source_root and canonical_root must differ")
    relative_artifacts = [Path(value) for value in args.artifact]
    if not relative_artifacts:
        raise PipelineError("promote-scene requires at least one --artifact")
    for relative in relative_artifacts:
        if relative.is_absolute() or ".." in relative.parts:
            raise PipelineError(f"promoted artifact must be a safe relative path: {relative}")
        if not (source_root / relative).exists():
            raise PipelineError(f"promoted artifact does not exist: {source_root / relative}")
    output_path = Path(args.output).resolve()
    for relative in relative_artifacts:
        destination = (canonical_root / relative).resolve()
        if output_path == destination or destination in output_path.parents:
            raise PipelineError(
                "promotion receipt must live outside every promoted destination"
            )

    promoted: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="lecture-promote-") as temporary:
        staging = Path(temporary) / "staging"
        backups = Path(temporary) / "backups"
        prepared: list[dict[str, Any]] = []
        for relative in relative_artifacts:
            source = source_root / relative
            candidate = staging / relative
            candidate.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, candidate)
            else:
                shutil.copy2(source, candidate)
            for text_path in _text_files(candidate):
                text = text_path.read_text(encoding="utf-8", errors="ignore")
                if WORKTREE_REFERENCE.search(text):
                    raise PipelineError(
                        f"promoted text contains a temporary worktree reference: {relative}"
                    )
            destination = canonical_root / relative
            if destination.exists() and not args.replace:
                raise PipelineError(f"canonical destination already exists: {destination}")
            prepared.append(
                {
                    "relative": relative,
                    "source": source,
                    "candidate": candidate,
                    "destination": destination,
                    "source_snapshot": artifact_snapshot(source, source_root),
                }
            )
        moved_destinations: list[Path] = []
        backed_up: list[tuple[Path, Path]] = []
        try:
            for item in prepared:
                destination = item["destination"]
                if destination.exists():
                    backup = backups / item["relative"]
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(destination), str(backup))
                    backed_up.append((backup, destination))
            for item in prepared:
                destination = item["destination"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(item["candidate"]), str(destination))
                moved_destinations.append(destination)
                canonical_snapshot = artifact_snapshot(destination, canonical_root)
                if canonical_snapshot["sha256"] != item["source_snapshot"]["sha256"]:
                    raise PipelineError(
                        f"promoted artifact hash mismatch: {item['relative'].as_posix()}"
                    )
                promoted.append(
                    {
                        "relative_path": item["relative"].as_posix(),
                        "source": item["source_snapshot"],
                        "canonical": canonical_snapshot,
                    }
                )
            result = {
                "schema": "lecture-animation-promotion-receipt-v2",
                "created_at": utc_now(),
                "source_root_name": source_root.name,
                "canonical_root_name": canonical_root.name,
                "promoted": promoted,
            }
            result["receipt_hash"] = object_hash(result)
            write_json(output_path, result)
        except Exception:
            for destination in reversed(moved_destinations):
                if destination.is_dir():
                    shutil.rmtree(destination)
                elif destination.exists():
                    destination.unlink()
            for backup, destination in reversed(backed_up):
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(backup), str(destination))
            raise
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def add_episode_ops_subparsers(subparsers: argparse._SubParsersAction) -> None:
    startup = subparsers.add_parser(
        "seal-episode-startup",
        help=(
            "seal the executable Initialization exit: stable roster, dedicated "
            "worktrees, reviewer separation, user constraints, and one evidence root"
        ),
    )
    startup.add_argument("--repo-root", default=".")
    startup.add_argument("--episode", required=True)
    startup.add_argument("--contract", required=True)
    startup.add_argument("--output", required=True)
    startup.add_argument("--require-clean", action="store_true")
    startup.set_defaults(func=command_seal_episode_startup)

    preflight = subparsers.add_parser(
        "episode-preflight",
        help="block TTS/final rendering on duplicate narration, pace, novice, duration, text, ending, and pronunciation failures",
    )
    preflight.add_argument("--repo-root", default=".")
    preflight.add_argument("--episode", required=True)
    preflight.add_argument("--contract", required=True)
    preflight.add_argument("--output", required=True)
    preflight.add_argument("--require-clean", action="store_true")
    preflight.set_defaults(func=command_episode_preflight)

    portability = subparsers.add_parser(
        "audit-portability",
        help="prove that canonical rebuild inputs exist and authoritative files do not depend on temporary worktrees",
    )
    portability.add_argument("--repo-root", default=".")
    portability.add_argument("--episode", required=True)
    portability.add_argument("--required-artifact", action="append", required=True)
    portability.add_argument("--authoritative-root", action="append", required=True)
    portability.add_argument("--output", required=True)
    portability.add_argument("--require-clean", action="store_true")
    portability.set_defaults(func=command_audit_portability)

    capsule = subparsers.add_parser(
        "build-task-capsule",
        help="create a compact hash-bound disk handoff for lossless low-token subagent coordination",
    )
    capsule.add_argument("--repo-root", default=".")
    capsule.add_argument("--scene-slug", required=True)
    capsule.add_argument("--role", required=True)
    capsule.add_argument("--task", required=True)
    capsule.add_argument("--artifact", action="append", default=[])
    capsule.add_argument("--gate", action="append", default=[])
    capsule.add_argument("--output", required=True)
    capsule.set_defaults(func=command_build_task_capsule)

    promote = subparsers.add_parser(
        "promote-scene",
        help="copy reviewed artifacts into the canonical checkout with relative paths and verified hashes",
    )
    promote.add_argument("--source-root", required=True)
    promote.add_argument("--canonical-root", required=True)
    promote.add_argument("--artifact", action="append", default=[])
    promote.add_argument("--replace", action="store_true")
    promote.add_argument("--output", required=True)
    promote.set_defaults(func=command_promote_scene)
