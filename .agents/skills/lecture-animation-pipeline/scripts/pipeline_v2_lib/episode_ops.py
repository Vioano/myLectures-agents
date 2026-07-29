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
VISIBLE_TEXT_CONSTRUCTORS = {"Text", "MarkupText", "Paragraph"}
DEFAULT_FIXED_ENDING = "我是结束乐队的键盘手，下个视频见"
PORTABILITY_REQUIRED_ROLES = {
    "lecture",
    "source",
    "audio",
    "final_video",
    "final_srt",
    "final_manifest",
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


def _visible_text_literals(path: Path, label: str, errors: list[str]) -> list[str]:
    if path.suffix.lower() != ".py":
        errors.append(f"{label}: automatic visible-text inventory currently requires a Python scene")
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError as exc:
        errors.append(f"{label}: scene source cannot be parsed for visible text: {exc}")
        return []
    values: list[str] = []
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
        if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(
            node.args[0].value, str
        ):
            errors.append(
                f"{label}: dynamic {function_name}(...) text at line "
                f"{getattr(node, 'lineno', '?')} cannot bypass the frozen inventory"
            )
            continue
        values.append(node.args[0].value)
    return values


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


def _formal_occurrence_count(text: str, token: str) -> int:
    variants = PRONUNCIATION_TOKEN_VARIANTS.get(token.lower())
    if variants:
        escaped = sorted((re.escape(value) for value in variants), key=len, reverse=True)
        return len(
            re.findall(
                rf"(?<![A-Za-z])(?:{'|'.join(escaped)})(?![A-Za-z])",
                text,
                re.I,
            )
        )
    if re.fullmatch(r"[A-Za-z]+", token):
        return len(re.findall(rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", text, re.I))
    return text.count(token)


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
    author_id = str(contract.get("author_id", "")).strip()
    if not author_id:
        errors.append("readiness contract requires author_id")
    scene_results: list[dict[str, Any]] = []
    narration_by_scene: list[tuple[str, str]] = []
    pronunciation_map = {
        str(key).strip().lower(): value
        for key, value in dict(contract.get("pronunciation_map", {})).items()
        if str(key).strip()
    }
    sensitive_found: set[str] = set()
    pronunciation_evidence: dict[str, Any] = {}
    scene_audio_paths: dict[str, Path] = {}
    narration_lookup: dict[str, str] = {}
    scene_artifacts_lookup: dict[str, dict[str, Any]] = {}

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
        elif scene_source_root is None or not scene_source_root.is_dir():
            errors.append(
                f"{slug}: scene_source_root must name the complete scene source package"
            )
            source_visible_inventory = []
        elif scene_source_path != scene_source_root and scene_source_root not in scene_source_path.parents:
            errors.append(f"{slug}: scene_source_path must live inside scene_source_root")
            source_visible_inventory = []
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
            for source_file in sorted(scene_source_root.rglob("*.py")):
                if _clean_path(source_file):
                    source_values = _visible_text_literals(
                        source_file,
                        f"{slug}.scene_source_root:{source_file.relative_to(scene_source_root)}",
                        errors,
                    )
                    source_relative = _relative(source_file, repo_root)
                    source_visible_inventory.extend(
                        (value, source_relative) for value in source_values
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
                    author_id=author_id,
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
        screen_text_budget = int(item.get("screen_text_budget", contract.get("screen_text_budget", 12)) or 12)
        if screen_text_count > screen_text_budget:
            errors.append(
                f"{slug}: screen text count {screen_text_count} exceeds budget {screen_text_budget}"
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

    duplicate_boundaries: list[dict[str, Any]] = []
    for (left_slug, left), (right_slug, right) in zip(narration_by_scene, narration_by_scene[1:]):
        duplicates = _boundary_duplicates(left, right)
        if duplicates:
            duplicate_boundaries.append(
                {"left_scene": left_slug, "right_scene": right_slug, "clauses": duplicates}
            )
            errors.append(f"{left_slug}->{right_slug}: duplicate narration at scene boundary")

    all_narration = "\n".join(value for _, value in narration_by_scene)
    expected_ending = _normalized_clause(
        str(contract.get("fixed_ending", DEFAULT_FIXED_ENDING)).strip()
    )
    ending_count = _normalized_clause(all_narration).count(expected_ending) if expected_ending else 0
    if ending_count != 1:
        errors.append(f"fixed ending must appear exactly once; observed {ending_count}")

    missing_pronunciations = sorted(
        token for token in sensitive_found if token.lower() not in pronunciation_map
    )
    if missing_pronunciations:
        errors.append(
            "pronunciation map is missing sensitive tokens: " + ", ".join(missing_pronunciations)
        )
    for token in sorted(sensitive_found - set(missing_pronunciations)):
        mapping = pronunciation_map.get(token.lower())
        if not isinstance(mapping, dict):
            errors.append(f"pronunciation mapping for {token} must be an evidence-bound object")
            continue
        spoken_form = str(mapping.get("spoken_form", "")).strip()
        tts_input_raw = str(mapping.get("tts_input_path", "")).strip()
        ear_evidence_raw = str(mapping.get("ear_evidence_path", "")).strip()
        ear_review_raw = str(mapping.get("ear_review_path", "")).strip()
        scene_slug = str(mapping.get("scene_slug", "")).strip()
        source_audio_raw = str(mapping.get("source_audio_path", "")).strip()
        if not spoken_form or not tts_input_raw or not scene_slug:
            errors.append(
                f"pronunciation mapping for {token} requires spoken_form, scene_slug, "
                "and tts_input_path"
            )
            continue
        if scene_slug not in narration_lookup:
            errors.append(
                f"pronunciation mapping for {token} names unknown scene {scene_slug}"
            )
            continue
        formal_count = _formal_occurrence_count(narration_lookup[scene_slug], token)
        episode_formal_count = _formal_occurrence_count(all_narration, token)
        if formal_count != episode_formal_count:
            errors.append(
                f"pronunciation mapping for {token} must cover every occurrence in one bound scene; "
                f"{scene_slug} has {formal_count}, episode has {episode_formal_count}"
            )
        expected_count = int(mapping.get("occurrences", formal_count) or 0)
        if expected_count != formal_count or expected_count <= 0:
            errors.append(
                f"pronunciation mapping for {token} binds {expected_count} occurrences; narration has {formal_count}"
            )
        tts_input_path = _resolve(tts_input_raw, repo_root)
        if not tts_input_path.is_file():
            errors.append(f"TTS input for {token} does not exist")
            continue
        tts_input = tts_input_path.read_text(encoding="utf-8", errors="ignore")
        if tts_input.count(spoken_form) != expected_count:
            errors.append(
                f"TTS input for {token} must contain spoken form {spoken_form!r} exactly {expected_count} times"
            )
        if _formal_occurrence_count(tts_input, token):
            errors.append(f"TTS input still contains unresolved formal token {token}")
        if readiness_stage == "pre_tts":
            pronunciation_evidence[token] = {
                "formal_occurrences": formal_count,
                "spoken_form": spoken_form,
                "scene_slug": scene_slug,
                "tts_input": artifact_snapshot(tts_input_path, repo_root),
                "review_status": "pending_post_tts",
            }
            continue
        if not ear_evidence_raw or not source_audio_raw or not ear_review_raw:
            errors.append(
                f"post_tts pronunciation mapping for {token} requires source_audio_path, "
                "ear_evidence_path, and ear_review_path"
            )
            continue
        source_audio_path = _resolve(source_audio_raw, repo_root)
        ear_evidence_path = _resolve(ear_evidence_raw, repo_root)
        bound_scene_audio = scene_audio_paths.get(scene_slug)
        if (
            not tts_input_path.is_file()
            or not source_audio_path.is_file()
            or not ear_evidence_path.is_file()
        ):
            errors.append(f"pronunciation evidence files for {token} do not all exist")
            continue
        if bound_scene_audio is None or source_audio_path.resolve() != bound_scene_audio.resolve():
            errors.append(
                f"pronunciation mapping for {token} source_audio_path must equal the bound "
                f"scene audio_path"
            )
        if ear_evidence_path.resolve() != source_audio_path.resolve():
            errors.append(
                f"pronunciation mapping for {token} ear_evidence_path must be the bound "
                "final scene audio; shorter clips are review aids, not gate evidence"
            )
        try:
            source_duration = _wav_duration(source_audio_path)
            _wav_duration(ear_evidence_path)
        except (wave.Error, EOFError) as exc:
            errors.append(f"pronunciation evidence for {token} is not a decodable WAV: {exc}")
            source_duration = 0.0
        checks = mapping.get("ear_check_results", [])
        windows = mapping.get("occurrence_windows_seconds", [])
        normalized_windows: list[list[float]] = []
        if not isinstance(windows, list) or len(windows) != expected_count:
            errors.append(
                f"pronunciation mapping for {token} requires one occurrence window per occurrence"
            )
        else:
            previous_end = -1.0
            for index, raw_window in enumerate(windows, start=1):
                try:
                    start, end = map(float, raw_window)
                except (TypeError, ValueError):
                    errors.append(
                        f"pronunciation mapping for {token} occurrence window {index} is invalid"
                    )
                    continue
                if start < 0 or end <= start or end > source_duration or start < previous_end:
                    errors.append(
                        f"pronunciation mapping for {token} occurrence window {index} "
                        "must be ordered, non-overlapping, and inside the bound scene audio"
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
                f"pronunciation mapping for {token} requires ordered 1..N passing "
                "ear_check_results bound to the declared occurrence windows"
            )
        source_audio_snapshot = artifact_snapshot(source_audio_path, repo_root)
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
            label=f"pronunciation.{token}.ear_review",
            errors=errors,
            author_id=author_id,
            expected_review_kind="pronunciation",
        )
        pronunciation_evidence[token] = {
            "formal_occurrences": formal_count,
            "spoken_form": spoken_form,
            "scene_slug": scene_slug,
            "tts_input": artifact_snapshot(tts_input_path, repo_root),
            "source_audio": source_audio_snapshot,
            "ear_evidence": artifact_snapshot(ear_evidence_path, repo_root),
            "occurrence_windows_seconds": normalized_windows,
            "ear_check_results": checks,
        }
        if ear_review_result is not None:
            _, authority_snapshot = ear_review_result
            pronunciation_evidence[token]["ear_review"] = artifact_snapshot(
                ear_review_path, repo_root
            )
            pronunciation_evidence[token][
                "ear_review_authority"
            ] = authority_snapshot

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
        "fixed_ending_count": ending_count,
        "required_concept_bridges": sorted(required_bridges),
        "supplied_concept_bridges": sorted(supplied_bridges),
    }
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
    artifacts: list[dict[str, Any]] = []
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
    for evidence in dict(receipt.get("pronunciation_evidence", {})).values():
        if not isinstance(evidence, dict):
            continue
        artifacts.extend(
            evidence[key]
            for key in (
                "tts_input",
                "source_audio",
                "ear_evidence",
                "ear_review",
                "ear_review_authority",
            )
            if isinstance(evidence.get(key), dict)
        )
    for artifact in artifacts:
        path = _resolve(str(artifact.get("path", "")), repo_root)
        current = artifact_snapshot(path, repo_root)
        if current.get("sha256") != artifact.get("sha256"):
            raise PipelineError(
                f"episode readiness receipt is stale for {artifact.get('path')}"
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
