#!/usr/bin/env python3
"""Evidence-bound helpers for lecture-animation-pipeline-v2."""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
from typing import Any, Iterable
import wave

from .core import PipelineError, canonical_json, object_hash, read_text, utc_now
from .governance import (
    review_session_governance,
    unresolved_policy_blockers,
    validate_pass_policy,
    validate_pending_repair_binding,
    validate_session_governance,
)
from .review_state import commit_review_attempt, create_review_session, record_human_false_pass
from .storage import (
    append_jsonl,
    append_unique_jsonl,
    atomic_write_json_unlocked,
    load_json,
    load_json_unlocked,
    locked_paths,
    read_jsonl,
    write_json,
)


SKILL_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = SKILL_ROOT / "references" / "rules.json"
AUTOPILOT_CONTRACT_VERSION = 5
REVIEW_SESSION_CONTRACT_VERSION = 5
HARD_GATE_LAYERS = ("layout", "math_object", "timing_attention", "novice_causality")
PROGRESSIVE_PLANNING_ARTIFACTS = {"episode_spine", "batch_plan"}
LIVE_POLICY_SOURCES = {"human_review", "accepted_agent_feedback"}
REPAIR_LINEAGE_CLASSES = {
    "initial_or_unknown",
    "preexisting_missed",
    "repair_induced",
    "incomplete_fix",
    "new_unrelated",
}
SELF_REVIEW_INDEPENDENT_SOURCES = {
    "decoded_review_frame",
    "qc_frame",
    "coordinate_recompute",
    "source_calculation",
    "word_alignment",
}
MATH_INVARIANT_EVIDENCE_TYPES = {
    "coordinate_check",
    "identity_binding",
    "formula_handoff",
    "semantic_event",
    "stage_snapshot",
    "runtime_assertion",
}
DISPLAY_MAPPING_MODES = {
    "identity",
    "uniform_scale",
    "local_zoom",
    "nonlinear_magnifier",
    "projection",
    "sampling",
    "log_length",
    "pedagogical_parameter",
    "equivalent_deformation",
    "novel",
}
DISPLAY_MAPPING_MODES_REQUIRING_DISTORTION_PROOF = {
    "local_zoom",
    "nonlinear_magnifier",
    "log_length",
    "pedagogical_parameter",
    "equivalent_deformation",
    "novel",
}
REQUIRED_ARTIFACTS = {
    "profile",
    "design_challenge",
    "deliberation",
    "design_gate",
    "precedent_packet",
    "plan",
    "source",
    "timeline",
    "telemetry",
    "authoring_qc",
    "review_mp4",
    "qc",
    "layout_audit",
    "emphasis_frame_audit",
    "srt",
    "audio",
    "text_inventory_baseline",
    "text_inventory_audit",
}
IGNORED_PARTS = {".git", "__pycache__", ".ipynb_checkpoints"}
IGNORED_NAMES = {".DS_Store"}
GENERIC_EVIDENCE = (
    "checked and no issue",
    "checked mp4",
    "looks good",
    "no problem found",
    "符合要求",
    "没有问题",
    "已检查",
    "整体通过",
    "未发现问题",
)
SEARCH_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "one", "or", "same", "scene", "show", "that", "the", "then",
    "this", "through", "to", "with", "while",
}

TAG_KEYWORDS = {
    "formula_dense": {
        "formula", "integral", "coefficient", "transform", "norm", "delta",
        "orthogonality", "completeness", "derivative", "projection", "公式", "积分",
        "系数", "变换", "归一化", "正交", "完备", "投影", "微分",
    },
    "stage_dense": {"panel", "inset", "dual", "split", "many", "面板", "双栏", "推导"},
    "limit_process": {
        "limit", "riemann", "densify", "refine", "narrow", "infinite", "epsilon",
        "gaussian proxy", "极限", "黎曼", "加密", "趋于", "收窄", "无穷",
    },
    "projection": {"projection", "coordinate", "inner product", "coefficient", "投影", "坐标", "内积", "系数"},
    "reconstruction": {"reconstruct", "inverse", "synthesis", "selector", "sifting", "重建", "逆变换", "合成", "筛选"},
    "graph": {
        "function", "curve", "axis", "spectrum", "sample", "frequency", "wave", "kernel",
        "函数", "曲线", "坐标轴", "频谱", "采样", "频率", "波", "核",
    },
    "complex": {"complex", "phase", "conjugate", "complex exponential", "复数指数", "复向量", "相位", "共轭"},
    "human_rejected": {"human-rejected", "human_rejected", "人工打回", "人审打回"},
    "repeat_rejected": {"repeat-rejected", "repeat_rejected", "反复打回", "重复打回"},
}


def clean_path(path: Path) -> bool:
    if path.name.startswith("._") or path.name in IGNORED_NAMES or path.suffix == ".pyc":
        return False
    return not any(part in IGNORED_PARTS for part in path.parts)


def relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve_stored_path(raw: str, root: Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else root / path


def stable_record_id(kind: str, episode: str, scene_slug: str, source: str) -> str:
    seed = f"{kind}|{episode}|{scene_slug}|{source}".encode("utf-8")
    return f"{kind}:{hashlib.sha1(seed).hexdigest()[:16]}"


def history_trust(review_status: Any) -> str:
    status = normalize_search_text(str(review_status))
    if any(token in status for token in ("pass_for_user", "approved", "published", "user_approved")):
        return "reviewed_positive"
    if any(token in status for token in ("revise", "reject", "failed", "blocked", "discarded")):
        return "rejected"
    return "unverified"


def normalize_search_text(value: str) -> str:
    value = value.lower().replace("ω", "omega").replace("δ", "delta").replace("π", "pi")
    return re.sub(r"\s+", " ", value).strip()


def query_terms(query: str) -> list[str]:
    query = normalize_search_text(query)
    terms: set[str] = {
        term for term in re.findall(r"[a-z0-9_+-]{2,}", query) if term not in SEARCH_STOPWORDS
    }
    for chunk in re.findall(r"[\u3400-\u9fff]+", query):
        terms.add(chunk)
        if len(chunk) >= 2:
            terms.update(chunk[index : index + 2] for index in range(len(chunk) - 1))
        if len(chunk) >= 3:
            terms.update(chunk[index : index + 3] for index in range(len(chunk) - 2))
    return sorted(terms, key=lambda item: (-len(item), item))


def excerpt_for(text: str, matched: list[str], width: int = 240) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    lowered = normalize_search_text(compact)
    positions = [lowered.find(term) for term in matched if lowered.find(term) >= 0]
    start = max(0, (min(positions) if positions else 0) - width // 3)
    return compact[start : start + width]


def storyboard_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?m)^###\s+(.+?)\s*$", text))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[match.end() : end].strip()))
    return sections


def markdown_guidance_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?m)^(##|###)\s+(.+?)\s*$", text))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(2).strip(), text[match.end() : end].strip()))
    return sections


def iter_episode_dirs(repo_root: Path) -> Iterable[Path]:
    videos = repo_root / "videos"
    if not videos.exists():
        return []
    return [path for path in sorted(videos.iterdir()) if path.is_dir() and clean_path(path)]


def build_history_records(repo_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for episode_dir in iter_episode_dirs(repo_root):
        episode = episode_dir.name
        groups: list[dict[str, Any]] = []
        timeline_path = episode_dir / "timeline.json"
        timeline: dict[str, Any] = {}
        if timeline_path.exists():
            try:
                timeline = load_json(timeline_path)
            except PipelineError:
                timeline = {}
            groups = timeline.get("scene_groups", []) if isinstance(timeline, dict) else []
            segments = timeline.get("segments", []) if isinstance(timeline, dict) else []
            narration_by_group: defaultdict[str, list[str]] = defaultdict(list)
            for segment in segments:
                narration_by_group[str(segment.get("scene_group", ""))].append(str(segment.get("narration", "")))
            for group in groups:
                group_id = str(group.get("id", ""))
                scene_slug = str(group.get("scene_slug") or group_id.lower())
                source = relative_or_absolute(timeline_path, repo_root)
                content = "\n".join(
                    [
                        str(group.get("role", "")),
                        str(group.get("driver", "")),
                        " ".join(map(str, group.get("math_objects", []))),
                        "\n".join(narration_by_group.get(group_id, [])),
                    ]
                )
                review_status = group.get("review_status", group.get("status", "unknown"))
                records.append(
                    {
                        "record_id": stable_record_id("scene_group", episode, scene_slug, source),
                        "record_type": "scene_group",
                        "episode": episode,
                        "scene_slug": scene_slug,
                        "title": f"{group_id} {group.get('role', scene_slug)}",
                        "source_paths": [source],
                        "content": content,
                        "review_status": review_status,
                        "risk_tier": group.get("risk_tier", "unknown"),
                        "trust_level": history_trust(review_status),
                        "negative_example": history_trust(review_status) == "rejected",
                    }
                )

        group_lookup = {str(group.get("id", "")).upper(): group for group in groups}
        storyboard_path = episode_dir / "storyboard.md"
        if storyboard_path.exists():
            for heading, body in storyboard_sections(read_text(storyboard_path)):
                group_match = re.match(r"(G\d+[A-Z]?)\b", heading, flags=re.IGNORECASE)
                group_id = group_match.group(1).upper() if group_match else ""
                group = group_lookup.get(group_id, {})
                scene_slug = str(group.get("scene_slug") or group_id.lower() or re.sub(r"\W+", "_", heading.lower()))
                source = relative_or_absolute(storyboard_path, repo_root)
                review_status = group.get("review_status", group.get("status", "unknown"))
                explicit_negative = bool(re.search(r"discard|supersed|reject|废弃|失效|打回", heading + " " + body, re.IGNORECASE))
                trust = "rejected" if explicit_negative else history_trust(review_status)
                records.append(
                    {
                        "record_id": stable_record_id("storyboard_scene", episode, scene_slug, source + heading),
                        "record_type": "storyboard_scene",
                        "episode": episode,
                        "scene_slug": scene_slug,
                        "title": heading,
                        "source_paths": [source],
                        "content": body,
                        "review_status": review_status,
                        "risk_tier": group.get("risk_tier", "unknown"),
                        "trust_level": trust,
                        "negative_example": trust == "rejected",
                    }
                )

        scenes_dir = episode_dir / "src" / "scenes"
        if scenes_dir.exists():
            for scene_dir in sorted(path for path in scenes_dir.iterdir() if path.is_dir() and clean_path(path)):
                files = [
                    path
                    for path in sorted(scene_dir.rglob("*"))
                    if path.is_file() and clean_path(path) and path.suffix.lower() in {".py", ".json", ".yaml", ".yml", ".md"}
                ]
                if not files:
                    continue
                chunks: list[str] = []
                for path in files:
                    chunks.append(path.name)
                    chunks.append(read_text(path, limit=60_000))
                source_paths = [relative_or_absolute(path, repo_root) for path in files]
                group = next((item for item in groups if item.get("scene_slug") == scene_dir.name), {})
                review_status = group.get("review_status", group.get("status", "unknown"))
                records.append(
                    {
                        "record_id": stable_record_id("scene_package", episode, scene_dir.name, source_paths[0]),
                        "record_type": "scene_package",
                        "episode": episode,
                        "scene_slug": scene_dir.name,
                        "title": f"scene package {scene_dir.name}",
                        "source_paths": source_paths,
                        "content": "\n".join(chunks),
                        "review_status": review_status,
                        "risk_tier": group.get("risk_tier", "unknown"),
                        "trust_level": history_trust(review_status),
                        "negative_example": history_trust(review_status) == "rejected",
                    }
                )

                grammar_path = scene_dir / "visual_grammar.json"
                if grammar_path.exists():
                    try:
                        grammar = load_json(grammar_path)
                    except PipelineError:
                        grammar = {}
                    patterns = grammar.get("patterns", []) if isinstance(grammar, dict) else []
                    for pattern in patterns:
                        if not isinstance(pattern, dict) or not pattern.get("id"):
                            continue
                        pattern_id = str(pattern["id"])
                        grammar_source = relative_or_absolute(grammar_path, repo_root)
                        anchor_paths = [
                            str(anchor.get("path"))
                            for anchor in pattern.get("source_anchors", [])
                            if isinstance(anchor, dict) and anchor.get("path")
                        ]
                        pattern_status = pattern.get("review_status", review_status)
                        pattern_content = "\n".join(
                            [
                                str(pattern.get("title", "")),
                                " ".join(map(str, pattern.get("learner_operations", []))),
                                str(pattern.get("hidden_relation", "")),
                                str(pattern.get("identity_invariant", "")),
                                str(pattern.get("attention_transfer", "")),
                                str(pattern.get("visual_action", "")),
                                " ".join(map(str, pattern.get("prefer_over", []))),
                                " ".join(map(str, pattern.get("retrieval_terms", []))),
                                json.dumps(pattern.get("source_anchors", []), ensure_ascii=False),
                            ]
                        )
                        records.append(
                            {
                                "record_id": stable_record_id(
                                    "visual_grammar", episode, scene_dir.name, grammar_source + "#" + pattern_id
                                ),
                                "record_type": "visual_grammar",
                                "episode": episode,
                                "scene_slug": scene_dir.name,
                                "title": str(pattern.get("title", pattern_id)),
                                "pattern_id": pattern_id,
                                "source_paths": [grammar_source, *anchor_paths],
                                "content": pattern_content,
                                "review_status": pattern_status,
                                "risk_tier": group.get("risk_tier", "unknown"),
                                "trust_level": history_trust(pattern_status),
                                "negative_example": history_trust(pattern_status) == "rejected",
                                "source_anchors": pattern.get("source_anchors", []),
                            }
                        )

        feedback_dir = episode_dir / "review" / "human-feedback"
        if feedback_dir.exists():
            for path in sorted(feedback_dir.glob("*.md")):
                if not clean_path(path):
                    continue
                content = read_text(path, limit=80_000)
                source = relative_or_absolute(path, repo_root)
                records.append(
                    {
                        "record_id": stable_record_id("human_feedback", episode, "", source),
                        "record_type": "human_feedback",
                        "episode": episode,
                        "scene_slug": "",
                        "title": path.stem,
                        "source_paths": [source],
                        "content": content,
                        "review_status": "human_feedback",
                        "risk_tier": "negative",
                        "trust_level": "rejected",
                        "negative_example": True,
                    }
                )

        issues_dir = episode_dir / "review" / "issues"
        if issues_dir.exists():
            for path in sorted(issues_dir.glob("*.json")):
                if not clean_path(path):
                    continue
                try:
                    issue = load_json(path)
                except PipelineError:
                    continue
                if not isinstance(issue, dict):
                    continue
                source = relative_or_absolute(path, repo_root)
                scene_slug = str(issue.get("scene", ""))
                content = "\n".join(
                    str(issue.get(key, ""))
                    for key in ("pattern_key", "standard_key", "problem", "impact", "suggested_fix", "evidence")
                )
                records.append(
                    {
                        "record_id": stable_record_id("review_issue", episode, scene_slug, source),
                        "record_type": "review_issue",
                        "episode": episode,
                        "scene_slug": scene_slug,
                        "title": str(issue.get("pattern_key") or issue.get("id") or path.stem),
                        "source_paths": [source],
                        "content": content,
                        "review_status": issue.get("status", "unknown"),
                        "risk_tier": issue.get("severity", "unknown"),
                        "trust_level": "rejected",
                        "negative_example": True,
                    }
                )
    old_references = repo_root / ".agents" / "skills" / "lecture-animation-pipeline" / "references"
    if old_references.exists():
        for path in sorted(old_references.glob("*.md")):
            if not clean_path(path):
                continue
            source = relative_or_absolute(path, repo_root)
            for heading, body in markdown_guidance_sections(read_text(path)):
                if len(body) < 40:
                    continue
                records.append(
                    {
                        "record_id": stable_record_id("guidance_reference", "pipeline-guidance", heading, source),
                        "record_type": "guidance_reference",
                        "episode": "pipeline-guidance",
                        "scene_slug": "",
                        "title": heading,
                        "source_paths": [source],
                        "content": body,
                        "review_status": "reference",
                        "risk_tier": "guidance",
                        "trust_level": "reference",
                        "negative_example": False,
                    }
                )
    return records


def search_history_records(
    records: list[dict[str, Any]],
    query: str,
    limit: int = 8,
    record_types: set[str] | None = None,
    exclude_episode: str | None = None,
) -> list[dict[str, Any]]:
    normalized_query = normalize_search_text(query)
    terms = query_terms(query)
    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    type_bonus = {
        "visual_grammar": 4.0,
        "scene_package": 3.0,
        "scene_group": 2.5,
        "storyboard_scene": 2.0,
        "guidance_reference": 1.5,
        "human_feedback": 0.5,
        "review_issue": 0.0,
    }
    for record in records:
        if record_types and record.get("record_type") not in record_types:
            continue
        if exclude_episode and record.get("episode") == exclude_episode:
            continue
        haystack = normalize_search_text(
            " ".join(
                [
                    str(record.get("title", "")),
                    str(record.get("scene_slug", "")),
                    " ".join(map(str, record.get("source_paths", []))),
                    str(record.get("content", "")),
                ]
            )
        )
        matched = [term for term in terms if term in haystack]
        if not matched and normalized_query not in haystack:
            continue
        score = type_bonus.get(str(record.get("record_type")), 0.0)
        if normalized_query and normalized_query in haystack:
            score += 15.0
        title = normalize_search_text(
            str(record.get("title", ""))
            + " "
            + str(record.get("scene_slug", ""))
            + " "
            + " ".join(map(str, record.get("source_paths", [])))
        )
        title_matches = 0
        for term in matched:
            score += min(5.0, 1.0 + len(term) * 0.35)
            if term in title:
                score += 2.0
                title_matches += 1
        if title_matches == 0:
            score *= 0.70
        trust_level = record.get("trust_level", history_trust(record.get("review_status")))
        if trust_level == "reviewed_positive":
            score += 3.0
        elif trust_level == "rejected":
            score -= 3.5
        elif trust_level != "reference":
            score -= 1.0
        scored.append((score, record, matched))
    scored.sort(key=lambda item: (-item[0], item[1].get("episode", ""), item[1].get("scene_slug", "")))
    hits: list[dict[str, Any]] = []
    for score, record, matched in scored[:limit]:
        hits.append(
            {
                "record_id": record["record_id"],
                "score": round(score, 3),
                "record_type": record["record_type"],
                "pattern_id": record.get("pattern_id"),
                "episode": record["episode"],
                "scene_slug": record.get("scene_slug", ""),
                "title": record.get("title", ""),
                "source_paths": record.get("source_paths", []),
                "review_status": record.get("review_status", "unknown"),
                "risk_tier": record.get("risk_tier", "unknown"),
                "trust_level": record.get("trust_level", history_trust(record.get("review_status"))),
                "negative_example": bool(record.get("negative_example")),
                "matched_terms": matched[:12],
                "excerpt": excerpt_for(str(record.get("content", "")), matched),
                "source_anchors": record.get("source_anchors", []),
            }
        )
    return hits


def load_rules() -> dict[str, Any]:
    registry = load_json(RULES_PATH)
    if registry.get("schema") != "lecture-animation-rules-v2":
        raise PipelineError("unexpected rules registry schema")
    return registry


def resolve_episode(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    path = path.resolve()
    if not path.exists():
        candidate = (repo_root / "videos" / raw).resolve()
        if candidate.exists():
            path = candidate
    if not path.is_dir():
        raise PipelineError(f"episode directory does not exist: {raw}")
    return path


def parse_explicit_tags(raw_values: list[str] | None) -> set[str]:
    tags: set[str] = set()
    for raw in raw_values or []:
        tags.update(part.strip() for part in raw.split(",") if part.strip())
    return tags


def infer_tags(group: dict[str, Any], narration: str, explicit: set[str]) -> list[str]:
    text = normalize_search_text(
        " ".join(
            [
                str(group.get("scene_slug", "")),
                str(group.get("role", "")),
                str(group.get("driver", "")),
                " ".join(map(str, group.get("math_objects", []))),
                str(group.get("risk_tier", "")),
                narration,
            ]
        )
    )
    tags = {"always"} | explicit
    for tag, keywords in TAG_KEYWORDS.items():
        if any(normalize_search_text(keyword) in text for keyword in keywords):
            tags.add(tag)
    if float(group.get("duration", 0.0) or 0.0) >= 60.0 or len(group.get("math_objects", [])) >= 4:
        tags.add("stage_dense")
    if len(re.findall(r"\b(?:int|sum|delta|omega|pi|F|f|c_n|e\^)", text)) >= 2:
        tags.add("formula_dense")
    risk = str(group.get("risk_tier", "")).lower().replace("-", "_")
    if risk:
        tags.add(risk)
    return sorted(tags)


def base_group_id(group_id: str) -> str:
    match = re.match(r"(G\d+)", group_id.upper())
    return match.group(1) if match else group_id.upper()


def issue_tag_hits(issue_text: str, tags: set[str]) -> list[str]:
    normalized = normalize_search_text(issue_text)
    hits: list[str] = []
    for tag in tags:
        keywords = TAG_KEYWORDS.get(tag, set())
        if any(normalize_search_text(keyword) in normalized for keyword in keywords):
            hits.append(tag)
    return hits


def relevant_regressions(episode_dir: Path, group: dict[str, Any], tags: set[str], limit: int = 12) -> tuple[list[dict[str, Any]], int]:
    issues_dir = episode_dir / "review" / "issues"
    if not issues_dir.exists():
        return [], 0
    scene_slug = str(group.get("scene_slug", "")).lower()
    group_id = str(group.get("id", "")).upper()
    group_base = base_group_id(group_id)
    ranked: list[tuple[float, dict[str, Any], Path, list[str]]] = []
    for path in sorted(issues_dir.glob("*.json")):
        if not clean_path(path):
            continue
        try:
            issue = load_json(path)
        except PipelineError:
            continue
        if not isinstance(issue, dict):
            continue
        blob = json.dumps(issue, ensure_ascii=False)
        issue_scene = str(issue.get("scene", "")).lower()
        filename = path.name.lower()
        exact = scene_slug and (scene_slug in issue_scene or scene_slug in filename)
        broad = group_base and (group_base.lower() in issue_scene or group_base.lower() in filename)
        global_scope = bool(issue.get("global_scope"))
        hits = issue_tag_hits(blob, tags)
        if not (exact or broad or global_scope or hits):
            continue
        score = 0.0
        if exact:
            score += 22.0
        elif broad:
            score += 6.0
        if global_scope:
            score += 4.0
        score += min(5.0, len(hits) * 1.5)
        if issue.get("source") == "human_review":
            score += 4.0
        elif issue.get("source") == "accepted_agent_feedback":
            score += 2.0
        if issue.get("must_check_in_future"):
            score += 2.0
        if issue.get("applies_to_authoring"):
            score += 1.0
        ranked.append((score, issue, path, hits))
    ranked.sort(key=lambda item: (-item[0], item[2].name))
    selected: list[dict[str, Any]] = []
    for score, issue, path, hits in ranked[:limit]:
        selected.append(
            {
                "issue_id": issue.get("id", path.stem),
                "pattern_key": issue.get("pattern_key", issue.get("standard_key", path.stem)),
                "standard_key": issue.get("standard_key"),
                "source": issue.get("source", "unknown"),
                "severity": issue.get("severity", "unknown"),
                "status": issue.get("status", "unknown"),
                "score": round(score, 3),
                "matched_tags": hits,
                "problem": issue.get("problem", ""),
                "suggested_fix": issue.get("suggested_fix", ""),
                "source_path": path.relative_to(episode_dir).as_posix(),
            }
        )
    return selected, max(0, len(ranked) - len(selected))


def infer_issue_gate_layers(issue: dict[str, Any]) -> list[str]:
    explicit = issue.get("gate_layers", [])
    if isinstance(explicit, list):
        selected = [str(value) for value in explicit if str(value) in HARD_GATE_LAYERS]
        if selected:
            return sorted(set(selected), key=HARD_GATE_LAYERS.index)
    blob = normalize_search_text(json.dumps(issue, ensure_ascii=False))
    layers: set[str] = set()
    if any(token in blob for token in ("layout", "overlap", "collision", "spacing", "subtitle", "布局", "重叠", "遮挡", "碰撞")):
        layers.add("layout")
    if any(token in blob for token in ("coordinate", "axis", "identity", "driver", "formula", "projection", "integral", "数学对象", "坐标", "数轴", "投影", "积分")):
        layers.add("math_object")
    if any(token in blob for token in ("timing", "audio", "srt", "pace", "fast", "slow", "transition", "时间", "口播", "节奏", "转场")):
        layers.add("timing_attention")
    if any(token in blob for token in ("novice", "comprehension", "causal", "explanatory text", "beginner", "新手", "看不懂", "因果", "文字")):
        layers.add("novice_causality")
    if not layers:
        layers.update(HARD_GATE_LAYERS)
    return sorted(layers, key=HARD_GATE_LAYERS.index)


def issue_match_scope(issue: dict[str, Any], path: Path, profile: dict[str, Any]) -> str | None:
    context = profile.get("context", {})
    scene_slug = str(context.get("scene_slug", "")).lower()
    group_base = base_group_id(str(context.get("scene_group", ""))).lower()
    issue_scene = str(issue.get("scene", "")).lower()
    filename = path.name.lower()
    if issue.get("global_scope"):
        return "global"
    explicit_scenes = {
        str(value).lower()
        for value in issue.get("applies_to_scenes", [])
        if str(value).strip()
    }
    explicit_tags = {
        str(value)
        for value in issue.get("applies_to_tags", [])
        if str(value).strip()
    }
    if scene_slug and scene_slug in explicit_scenes:
        return "explicit_scene"
    if group_base and group_base in explicit_scenes:
        return "explicit_group"
    if explicit_tags & set(profile.get("tags", [])):
        return "explicit_tag"
    if scene_slug and (scene_slug in issue_scene or scene_slug in filename):
        return "exact_scene"
    if group_base and (group_base in issue_scene or group_base in filename):
        return "group_family"
    blob = json.dumps(issue, ensure_ascii=False)
    return "implicit_risk_tag" if issue_tag_hits(blob, set(profile.get("tags", []))) else None


def compile_live_policy_data(episode_dir: Path, profile: dict[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    advisory_match_count = 0
    issues_dir = episode_dir / "review" / "issues"
    if issues_dir.exists():
        for path in sorted(issues_dir.glob("*.json")):
            if not clean_path(path):
                continue
            try:
                issue = load_json(path)
            except PipelineError:
                continue
            if not isinstance(issue, dict):
                continue
            match_scope = issue_match_scope(issue, path, profile)
            if not match_scope:
                continue
            source = str(issue.get("source", ""))
            if source not in LIVE_POLICY_SOURCES and not issue.get("must_check_in_future"):
                continue
            # Loose keyword similarity remains useful for retrieval, but it must
            # not invalidate unrelated frozen scenes. Only explicit, scene, group,
            # or global applicability enters the hash-bound live policy.
            if match_scope == "implicit_risk_tag":
                advisory_match_count += 1
                continue
            entries.append(
                {
                    "issue_id": issue.get("id", path.stem),
                    "pattern_key": issue.get("pattern_key", issue.get("standard_key", path.stem)),
                    "standard_key": issue.get("standard_key"),
                    "source": source or "must_check_in_future",
                    "severity": issue.get("severity", "unknown"),
                    "status": issue.get("status", "unknown"),
                    "match_scope": match_scope,
                    "gate_layers": infer_issue_gate_layers(issue),
                    "problem": issue.get("problem", ""),
                    "required_fix": issue.get("required_fix", issue.get("suggested_fix", "")),
                    "source_path": path.relative_to(episode_dir).as_posix(),
                    "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    entries.sort(key=lambda item: (str(item.get("pattern_key")), str(item.get("issue_id"))))
    required_patterns = sorted(
        {
            str(item.get("pattern_key"))
            for item in entries
            if item.get("pattern_key")
        }
    )
    policy: dict[str, Any] = {
        "schema": "lecture-animation-live-policy-v2",
        "contract_version": AUTOPILOT_CONTRACT_VERSION,
        "episode": episode_dir.name,
        "scene_slug": profile.get("context", {}).get("scene_slug"),
        "required_gate_layers": list(HARD_GATE_LAYERS),
        "entries": entries,
        "required_pattern_keys": required_patterns,
        "source_issue_count": len(entries),
        "implicit_advisory_matches_omitted": advisory_match_count,
    }
    policy["policy_hash"] = object_hash(policy)
    return policy


def validate_live_policy_hash(policy: dict[str, Any]) -> bool:
    payload = dict(policy)
    expected = payload.pop("policy_hash", None)
    return (
        policy.get("schema") == "lecture-animation-live-policy-v2"
        and bool(expected)
        and expected == object_hash(payload)
    )


def manifest_live_policy(manifest: dict[str, Any], repo_root: Path) -> dict[str, Any] | None:
    descriptor = manifest.get("artifacts", {}).get("live_policy", {})
    raw_path = str(descriptor.get("path", "")).strip()
    if not raw_path:
        return None
    return load_json(resolve_stored_path(raw_path, repo_root))


def attach_autopilot_contract(
    profile: dict[str, Any],
    policy: dict[str, Any],
    policy_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    result = dict(profile)
    result.pop("profile_hash", None)
    result["autopilot_contract_version"] = AUTOPILOT_CONTRACT_VERSION
    result["live_policy_hash"] = policy.get("policy_hash")
    result["live_policy_path"] = relative_or_absolute(policy_path, repo_root)
    result["live_policy_required_patterns"] = list(policy.get("required_pattern_keys", []))
    result["hard_gate_layers"] = list(HARD_GATE_LAYERS)
    result["profile_hash"] = object_hash(result)
    return result


def compile_profile_data(
    repo_root: Path,
    episode_dir: Path,
    scene_slug: str,
    explicit_tags: set[str] | None = None,
    regression_limit: int = 12,
) -> dict[str, Any]:
    timeline_path = episode_dir / "timeline.json"
    timeline = load_json(timeline_path)
    groups = timeline.get("scene_groups", [])
    group = next(
        (
            item
            for item in groups
            if str(item.get("scene_slug", "")).lower() == scene_slug.lower()
            or str(item.get("id", "")).lower() == scene_slug.lower()
        ),
        None,
    )
    if group is None:
        raise PipelineError(f"scene group not found in timeline: {scene_slug}")
    group_id = str(group.get("id", ""))
    segments = [item for item in timeline.get("segments", []) if str(item.get("scene_group", "")) == group_id]
    narration = "\n\n".join(str(item.get("narration", "")) for item in segments)
    tags = infer_tags(group, narration, explicit_tags or set())
    registry = load_rules()
    applicable_rules = [
        rule
        for rule in registry["rules"]
        if rule.get("status") == "active"
        and ("always" in rule.get("applies_when", []) or set(rule.get("applies_when", [])) & set(tags))
    ]
    selected_rules = [rule for rule in applicable_rules if "gate" not in rule.get("owners", [])]
    regressions, omitted = relevant_regressions(episode_dir, group, set(tags), limit=regression_limit)
    profile: dict[str, Any] = {
        "schema": "lecture-animation-scene-profile-v2",
        "rules_registry_hash": object_hash(registry),
        "context": {
            "repo_root": str(repo_root.resolve()),
            "episode": relative_or_absolute(episode_dir, repo_root),
            "episode_slug": episode_dir.name,
            "timeline": relative_or_absolute(timeline_path, repo_root),
            "scene_group": group_id,
            "scene_slug": group.get("scene_slug", scene_slug),
            "start": group.get("start"),
            "end": group.get("end"),
            "duration": group.get("duration"),
            "role": group.get("role", ""),
            "math_objects": group.get("math_objects", []),
            "driver": group.get("driver", ""),
            "risk_tier": group.get("risk_tier", "unknown"),
            "segment_ids": [item.get("id") for item in segments],
            "narration": narration,
        },
        "tags": tags,
        "rules": selected_rules,
        "author_rule_ids": [rule["rule_id"] for rule in selected_rules if "author" in rule.get("owners", [])],
        "reviewer_rule_ids": [rule["rule_id"] for rule in selected_rules if "reviewer" in rule.get("owners", [])],
        "gate_rule_ids": [rule["rule_id"] for rule in applicable_rules if "gate" in rule.get("owners", [])],
        "regressions": regressions,
        "regressions_omitted_by_relevance_cap": omitted,
        "first_principles_seed": {
            "role": group.get("role", ""),
            "driver": group.get("driver", ""),
            "math_objects": group.get("math_objects", []),
        },
        "required_outputs": {
            "author": [
                "design_challenge.json",
                "design_deliberation.json",
                "design_gate.json",
                "precedent_packet.json",
                "scene_plan.json",
                "scene source package",
                "runtime telemetry",
                "authoring QC report",
                "layout audit",
                "QC frames",
                "review MP4",
            ],
            "reviewer": ["blind novice pass", "rule checks", "findings", "verdict"],
        },
    }
    profile["profile_hash"] = object_hash(profile)
    return profile


def validate_profile_hash(profile: dict[str, Any]) -> bool:
    expected = profile.get("profile_hash")
    payload = dict(profile)
    payload.pop("profile_hash", None)
    return bool(expected) and expected == object_hash(payload)


def build_design_challenge(profile: dict[str, Any]) -> dict[str, Any]:
    context = profile.get("context", {})
    challenge: dict[str, Any] = {
        "schema": "lecture-animation-design-challenge-v2",
        "profile_hash": profile.get("profile_hash"),
        "scene_slug": context.get("scene_slug"),
        "first_principles_context": {
            "role": context.get("role", ""),
            "driver": context.get("driver", ""),
            "math_objects": context.get("math_objects", []),
            "narration": context.get("narration", ""),
            "risk_tags": profile.get("tags", []),
            "regression_patterns": [item.get("pattern_key") for item in profile.get("regressions", [])[:8]],
        },
        "required_reasoning": [
            "model the novice state and likely wrong inference",
            "state the hidden relation that must become perceptible",
            "separate mathematical-state, display-mapping, and attention changes",
            "propose materially different stage hypotheses before retrieval",
            "predict how each hypothesis could fail for a novice",
            "select by causal visibility and identity continuity",
        ],
        "history_withheld_until_gate": True,
    }
    challenge["challenge_hash"] = object_hash(challenge)
    return challenge


def validate_design_challenge_hash(challenge: dict[str, Any]) -> bool:
    expected = challenge.get("challenge_hash")
    payload = dict(challenge)
    payload.pop("challenge_hash", None)
    return bool(expected) and expected == object_hash(payload)


def candidate_token_set(candidate: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(candidate.get(key, ""))
        for key in (
            "stage_logic",
            "view_mapping",
            "math_state_logic",
            "attention_logic",
            "identity_invariants",
            "novice_advantage",
        )
    )
    return set(query_terms(text))


def validate_design_deliberation_data(
    profile: dict[str, Any],
    challenge: dict[str, Any],
    deliberation: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if challenge.get("schema") != "lecture-animation-design-challenge-v2" or not validate_design_challenge_hash(challenge):
        errors.append("design challenge is invalid or stale")
    if challenge.get("profile_hash") != profile.get("profile_hash"):
        errors.append("design challenge does not match the compiled profile")
    if deliberation.get("schema") != "lecture-animation-design-deliberation-v2":
        errors.append("deliberation schema must be lecture-animation-design-deliberation-v2")
    if deliberation.get("challenge_hash") != challenge.get("challenge_hash"):
        errors.append("deliberation challenge_hash does not match the active challenge")
    if deliberation.get("phase") != "first_principles" or deliberation.get("history_consulted") is not False:
        errors.append("deliberation must be a first_principles pass completed before history retrieval")
    if len(str(deliberation.get("author", "")).strip()) < 3:
        errors.append("deliberation requires an author identity")

    novice = deliberation.get("novice_model", {})
    novice_fields = ("known_before", "likely_wrong_inference", "needed_visual_evidence", "success_prediction")
    if not isinstance(novice, dict) or any(len(str(novice.get(key, "")).strip()) < 12 for key in novice_fields):
        errors.append("novice_model requires known state, wrong inference, needed evidence, and success prediction")
    signature = deliberation.get("problem_signature", {})
    signature_fields = (
        "learner_operation",
        "invisible_relation",
        "must_remain_invariant",
        "must_become_perceptible",
        "working_memory_burden",
    )
    if not isinstance(signature, dict) or any(len(str(signature.get(key, "")).strip()) < 10 for key in signature_fields):
        errors.append("problem_signature requires learner operation, hidden relation, invariant, perceptual target, and working-memory burden")

    hypotheses = deliberation.get("hypotheses", [])
    risk_tags = set(profile.get("tags", []))
    required_count = 2 if risk_tags & {"stage_dense", "human_rejected", "repeat_rejected"} else 1
    if not isinstance(hypotheses, list) or len(hypotheses) < required_count:
        errors.append(f"deliberation requires at least {required_count} lightweight stage hypotheses")
        hypotheses = []
    hypothesis_fields = (
        "stage_logic",
        "view_mapping",
        "math_state_logic",
        "attention_logic",
        "identity_invariants",
        "novice_advantage",
        "failure_risk",
        "mute_test_prediction",
    )
    selected_ids: list[str] = []
    candidate_ids: set[str] = set()
    token_sets: list[tuple[str, set[str]]] = []
    for candidate in hypotheses:
        if not isinstance(candidate, dict) or not candidate.get("id"):
            errors.append("each hypothesis requires a stable id")
            continue
        candidate_id = str(candidate["id"])
        if candidate_id in candidate_ids:
            errors.append("hypothesis ids must be unique")
        candidate_ids.add(candidate_id)
        if any(len(str(candidate.get(key, "")).strip()) < 10 for key in hypothesis_fields):
            errors.append(f"hypothesis {candidate_id!r} is missing concrete stage, M/D/A, novice, failure, or mute-test reasoning")
        if candidate.get("selected") is True:
            selected_ids.append(candidate_id)
        token_sets.append((candidate_id, candidate_token_set(candidate)))
    if len(selected_ids) != 1:
        errors.append("deliberation must select exactly one hypothesis")
    if len(str(deliberation.get("selection_reason", "")).strip()) < 20:
        errors.append("deliberation requires a concrete selection_reason")

    max_similarity = 0.0
    for index, (_, left) in enumerate(token_sets):
        for _, right in token_sets[index + 1 :]:
            union = left | right
            similarity = len(left & right) / len(union) if union else 1.0
            max_similarity = max(max_similarity, similarity)
            if similarity > 0.78:
                errors.append("stage hypotheses are lexically too similar to count as materially different")
                break

    context = profile.get("context", {})
    scene_terms = set(
        query_terms(
            " ".join(
                [
                    str(context.get("driver", "")),
                    " ".join(map(str, context.get("math_objects", []))),
                    str(context.get("role", "")),
                ]
            )
        )
    )
    deliberation_terms = set(query_terms(json.dumps(deliberation, ensure_ascii=False)))
    matched_scene_terms = sorted(scene_terms & deliberation_terms)
    required_matches = min(3, len(scene_terms))
    if len(matched_scene_terms) < required_matches:
        errors.append("deliberation is not specific enough to the current scene objects and mathematical driver")

    gate: dict[str, Any] = {
        "schema": "lecture-animation-design-gate-v2",
        "valid": not errors,
        "profile_hash": profile.get("profile_hash"),
        "challenge_hash": challenge.get("challenge_hash"),
        "deliberation_hash": object_hash(deliberation),
        "selected_hypothesis_id": selected_ids[0] if len(selected_ids) == 1 else None,
        "errors": errors,
        "stats": {
            "hypotheses": len(hypotheses),
            "matched_scene_terms": matched_scene_terms,
            "max_candidate_similarity": round(max_similarity, 4),
        },
    }
    gate["design_gate_hash"] = object_hash(gate)
    return gate


def validate_design_gate_hash(gate: dict[str, Any]) -> bool:
    expected = gate.get("design_gate_hash")
    payload = dict(gate)
    payload.pop("design_gate_hash", None)
    return bool(expected) and expected == object_hash(payload)


def build_precedent_packet(
    repo_root: Path,
    profile: dict[str, Any],
    deliberation: dict[str, Any],
    gate: dict[str, Any],
    production_limit: int = 6,
    guidance_limit: int = 4,
) -> dict[str, Any]:
    if not gate.get("valid") or not validate_design_gate_hash(gate):
        raise PipelineError("a valid first-principles design gate is required before precedent retrieval")
    if gate.get("deliberation_hash") != object_hash(deliberation):
        raise PipelineError("design gate does not match the supplied deliberation")
    signature = deliberation.get("problem_signature", {})
    selected = next(
        (item for item in deliberation.get("hypotheses", []) if item.get("id") == gate.get("selected_hypothesis_id")),
        {},
    )
    query = " ".join(
        [
            " ".join(str(signature.get(key, "")) for key in signature),
            str(selected.get("stage_logic", "")),
            str(selected.get("view_mapping", "")),
            str(selected.get("identity_invariants", "")),
        ]
    )
    records = build_history_records(repo_root)
    episode_slug = str(profile.get("context", {}).get("episode_slug", ""))
    production_hits = search_history_records(
        records,
        query,
        limit=production_limit,
        record_types={"scene_group", "storyboard_scene", "scene_package", "visual_grammar"},
        exclude_episode=episode_slug,
    )
    guidance_hits = search_history_records(
        records,
        query,
        limit=guidance_limit,
        record_types={"guidance_reference"},
    )
    packet: dict[str, Any] = {
        "schema": "lecture-animation-precedent-packet-v2",
        "profile_hash": profile.get("profile_hash"),
        "design_gate_hash": gate.get("design_gate_hash"),
        "query": query,
        "production_hits": production_hits,
        "guidance_hits": guidance_hits,
        "hits": production_hits + guidance_hits,
    }
    packet["precedent_packet_hash"] = object_hash(packet)
    return packet


def validate_precedent_packet_hash(packet: dict[str, Any]) -> bool:
    expected = packet.get("precedent_packet_hash")
    payload = dict(packet)
    payload.pop("precedent_packet_hash", None)
    return bool(expected) and expected == object_hash(payload)


def validate_design_chain_data(
    profile: dict[str, Any],
    plan: dict[str, Any],
    challenge: dict[str, Any],
    deliberation: dict[str, Any],
    gate: dict[str, Any],
    packet: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    expected_challenge = build_design_challenge(profile)
    if challenge.get("challenge_hash") != expected_challenge.get("challenge_hash"):
        errors.append("design challenge is stale for the compiled profile")
    expected_gate = validate_design_deliberation_data(profile, challenge, deliberation)
    if gate.get("design_gate_hash") != expected_gate.get("design_gate_hash") or not gate.get("valid"):
        errors.append("design gate is stale, invalid, or does not match the deliberation")
    if not validate_precedent_packet_hash(packet) or packet.get("design_gate_hash") != gate.get("design_gate_hash"):
        errors.append("precedent packet is invalid or not bound to the design gate")
    chain = plan.get("design_chain", {})
    expected_chain = {
        "challenge_hash": challenge.get("challenge_hash"),
        "deliberation_hash": object_hash(deliberation),
        "design_gate_hash": gate.get("design_gate_hash"),
        "precedent_packet_hash": packet.get("precedent_packet_hash"),
    }
    for key, value in expected_chain.items():
        if chain.get(key) != value:
            errors.append(f"scene plan design_chain.{key} does not match the validated design session")
    if plan.get("selected_hypothesis_id") != gate.get("selected_hypothesis_id"):
        errors.append("scene plan selected_hypothesis_id does not match the design gate")
    hit_ids = {str(item.get("record_id")) for item in packet.get("hits", []) if item.get("record_id")}
    decisions = plan.get("history_decisions", [])
    decision_ids = {str(item.get("history_record_id")) for item in decisions if isinstance(item, dict)}
    no_fit = any(
        isinstance(item, dict) and item.get("decision") == "no_fit" and len(str(item.get("reason", "")).strip()) >= 20
        for item in decisions
    )
    missing = sorted(hit_ids - decision_ids)
    if missing and not no_fit:
        errors.append("history_decisions omit precedent packet records: " + ", ".join(missing))
    return errors


def rectangles_overlap(left: list[float], right: list[float]) -> bool:
    return min(left[2], right[2]) > max(left[0], right[0]) and min(left[3], right[3]) > max(left[1], right[1])


def validate_math_object_display_contract(plan: dict[str, Any]) -> list[str]:
    """Validate typed mathematical objects separately from their screen mappings."""
    errors: list[str] = []
    math_objects = plan.get("math_objects", [])
    mappings = plan.get("display_mappings", [])
    bindings = plan.get("visual_bindings", [])
    if not isinstance(math_objects, list) or not math_objects:
        return ["autopilot v3 plans require typed math_objects"]
    if not isinstance(mappings, list) or not mappings:
        errors.append("autopilot v3 plans require explicit display_mappings")
        mappings = []
    if not isinstance(bindings, list) or not bindings:
        errors.append("autopilot v3 plans require visual_bindings")
        bindings = []

    object_map: dict[str, dict[str, Any]] = {}
    object_math_parameters: dict[str, set[str]] = {}
    object_display_parameters: dict[str, set[str]] = {}
    for item in math_objects:
        if not isinstance(item, dict):
            errors.append("each math_object must be structured")
            continue
        object_id = str(item.get("object_id", ""))
        if not object_id or object_id in object_map:
            errors.append("math_objects require unique object_id values")
            continue
        if len(str(item.get("mathematical_type", "")).strip()) < 3:
            errors.append(f"math_object {object_id!r} requires mathematical_type")
        if len(str(item.get("definition", "")).strip()) < 12:
            errors.append(f"math_object {object_id!r} requires a concrete definition")
        driver_ids = item.get("driver_ids", [])
        if not isinstance(driver_ids, list):
            errors.append(f"math_object {object_id!r} driver_ids must be a list")
            driver_ids = []
        parameters = item.get("parameters", [])
        if not isinstance(parameters, list):
            errors.append(f"math_object {object_id!r} parameters must be a list")
            parameters = []
        math_parameter_ids: set[str] = set()
        display_parameter_ids: set[str] = set()
        for parameter in parameters:
            if not isinstance(parameter, dict):
                errors.append(f"math_object {object_id!r} has an unstructured parameter")
                continue
            parameter_id = str(parameter.get("parameter_id", ""))
            role = str(parameter.get("role", ""))
            if not parameter_id or role not in {"math", "display"}:
                errors.append(f"math_object {object_id!r} parameters require parameter_id and role math/display")
                continue
            target = math_parameter_ids if role == "math" else display_parameter_ids
            if parameter_id in math_parameter_ids | display_parameter_ids:
                errors.append(f"math_object {object_id!r} repeats parameter {parameter_id!r}")
            target.add(parameter_id)
        illegal_drivers = sorted(set(map(str, driver_ids)) & display_parameter_ids)
        if illegal_drivers:
            errors.append(
                f"math_object {object_id!r} uses display-only parameters as mathematical drivers: {', '.join(illegal_drivers)}"
            )
        object_map[object_id] = item
        object_math_parameters[object_id] = math_parameter_ids
        object_display_parameters[object_id] = display_parameter_ids

    mapping_map: dict[str, dict[str, Any]] = {}
    for item in mappings:
        if not isinstance(item, dict):
            errors.append("each display_mapping must be structured")
            continue
        mapping_id = str(item.get("mapping_id", ""))
        source_object_id = str(item.get("source_object_id", ""))
        mode = str(item.get("mode", ""))
        if not mapping_id or mapping_id in mapping_map:
            errors.append("display_mappings require unique mapping_id values")
            continue
        if source_object_id not in object_map:
            errors.append(f"display_mapping {mapping_id!r} references an unknown math object")
        if mode not in DISPLAY_MAPPING_MODES:
            errors.append(f"display_mapping {mapping_id!r} uses unsupported mode {mode!r}")
        verification = item.get("verification", {})
        if not isinstance(verification, dict):
            errors.append(f"display_mapping {mapping_id!r} requires verification obligations")
            verification = {}
        preserved = verification.get("preserved_invariants", [])
        distorted = verification.get("distorted_quantities", [])
        forbidden = verification.get("forbidden_inferences", [])
        if not isinstance(preserved, list) or not preserved:
            errors.append(f"display_mapping {mapping_id!r} must name preserved_invariants")
        if not isinstance(distorted, list):
            errors.append(f"display_mapping {mapping_id!r} distorted_quantities must be a list")
        if not isinstance(forbidden, list):
            errors.append(f"display_mapping {mapping_id!r} forbidden_inferences must be a list")
        if len(str(verification.get("validation_method", "")).strip()) < 12:
            errors.append(f"display_mapping {mapping_id!r} requires a concrete validation_method")
        if mode in DISPLAY_MAPPING_MODES_REQUIRING_DISTORTION_PROOF:
            if not distorted:
                errors.append(f"display_mapping {mapping_id!r} must disclose its visual distortion")
            if not forbidden:
                errors.append(f"display_mapping {mapping_id!r} must name forbidden learner inferences")
        if mode == "equivalent_deformation" and len(str(verification.get("equivalence_basis", "")).strip()) < 12:
            errors.append(f"display_mapping {mapping_id!r} requires an equivalence_basis")
        if mode == "novel" and len(str(verification.get("counterexample_probe", "")).strip()) < 12:
            errors.append(f"novel display_mapping {mapping_id!r} requires a counterexample_probe")
        display_parameters = item.get("display_parameters", [])
        if not isinstance(display_parameters, list):
            errors.append(f"display_mapping {mapping_id!r} display_parameters must be a list")
            display_parameters = []
        for parameter in display_parameters:
            if not isinstance(parameter, dict):
                errors.append(f"display_mapping {mapping_id!r} has an unstructured display parameter")
                continue
            parameter_id = str(parameter.get("parameter_id", ""))
            source_parameter_id = str(parameter.get("source_parameter_id", ""))
            if not parameter_id or parameter.get("role") != "display":
                errors.append(f"display_mapping {mapping_id!r} parameters must be explicitly role=display")
            if source_object_id in object_map and source_parameter_id not in object_math_parameters.get(source_object_id, set()):
                errors.append(
                    f"display_mapping {mapping_id!r} display parameter {parameter_id!r} lacks a valid mathematical source"
                )
            if parameter_id in object_math_parameters.get(source_object_id, set()):
                errors.append(
                    f"display_mapping {mapping_id!r} reuses mathematical parameter {parameter_id!r} as a display parameter"
                )
        mapping_map[mapping_id] = item

    visual_ids: set[str] = set()
    bound_primary_ids: set[str] = set()
    for item in bindings:
        if not isinstance(item, dict):
            errors.append("each visual_binding must be structured")
            continue
        visual_id = str(item.get("visual_object_id", ""))
        math_object_id = str(item.get("math_object_id", ""))
        mapping_id = str(item.get("display_mapping_id", ""))
        if not visual_id or visual_id in visual_ids:
            errors.append("visual_bindings require unique visual_object_id values")
            continue
        if math_object_id not in object_map:
            errors.append(f"visual_binding {visual_id!r} references an unknown math object")
        if mapping_id not in mapping_map:
            errors.append(f"visual_binding {visual_id!r} references an unknown display mapping")
        elif str(mapping_map[mapping_id].get("source_object_id", "")) != math_object_id:
            errors.append(f"visual_binding {visual_id!r} mapping is bound to a different math object")
        planned_drivers = set(map(str, object_map.get(math_object_id, {}).get("driver_ids", [])))
        binding_drivers = set(map(str, item.get("driver_ids", [])))
        if binding_drivers != planned_drivers:
            errors.append(f"visual_binding {visual_id!r} driver_ids do not match its mathematical object")
        if len(str(item.get("runtime_owner", "")).strip()) < 4:
            errors.append(f"visual_binding {visual_id!r} requires a runtime_owner")
        visual_ids.add(visual_id)
        bound_primary_ids.add(visual_id)

    primary_ids = {
        str(item.get("primary_object"))
        for item in plan.get("stage_regions", [])
        if isinstance(item, dict) and item.get("primary_object")
    }
    missing_primary = sorted(primary_ids - bound_primary_ids)
    if missing_primary:
        errors.append("primary stage objects lack visual_bindings: " + ", ".join(missing_primary))
    return errors


def validate_scene_plan_data(profile: dict[str, Any], plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tags = set(profile.get("tags", []))
    active_rule_ids = {
        str(rule.get("rule_id"))
        for rule in profile.get("rules", [])
        if isinstance(rule, dict) and rule.get("status") == "active"
    }
    if plan.get("schema") != "lecture-animation-scene-plan-v2":
        errors.append("scene plan schema must be lecture-animation-scene-plan-v2")
    if plan.get("profile_hash") != profile.get("profile_hash"):
        errors.append("scene plan profile_hash does not match the compiled profile")
    expected_slug = profile.get("context", {}).get("scene_slug")
    if plan.get("scene_slug") != expected_slug:
        errors.append(f"scene_slug must be {expected_slug!r}")
    if int(profile.get("autopilot_contract_version") or 0) >= 2:
        planning_chain = plan.get("planning_chain", {})
        if not isinstance(planning_chain, dict) or any(
            len(str(planning_chain.get(key, "")).strip()) < 32
            for key in ("episode_spine_hash", "batch_plan_hash")
        ):
            errors.append("autopilot v2 scene plans must bind episode_spine_hash and batch_plan_hash")
    if int(profile.get("autopilot_contract_version") or 0) >= 3:
        errors.extend(validate_math_object_display_contract(plan))
    if "repeat_rejected" in tags:
        text_contract = plan.get("screen_text_contract", {})
        if (
            not isinstance(text_contract, dict)
            or text_contract.get("mode") != "exact"
            or len(str(text_contract.get("baseline_path", "")).strip()) < 8
            or len(str(text_contract.get("purpose", "")).strip()) < 20
        ):
            errors.append("repeat-rejected scenes require an exact screen_text_contract bound to a frozen baseline")
    if len(str(plan.get("primary_question", "")).strip()) < 12:
        errors.append("primary_question must state one concrete mathematical question")
    learning = plan.get("learning_contract", {})
    learning_fields = (
        "novice_start_state",
        "core_claim",
        "likely_misconception",
        "visible_evidence",
        "success_test",
    )
    if not isinstance(learning, dict) or any(len(str(learning.get(key, "")).strip()) < 12 for key in learning_fields):
        errors.append("learning_contract requires a concrete novice state, core claim, misconception, visible evidence, and success test")
    driver = plan.get("math_driver")
    if not isinstance(driver, dict) or not all(driver.get(key) for key in ("name", "relation", "drives")):
        errors.append("math_driver requires name, relation, and non-empty drives")
    causal_steps = plan.get("novice_causal_steps", [])
    causal_fields = ("known_before", "cause", "visible_action", "new_evidence", "allowed_inference")
    if not causal_steps or any(
        not isinstance(step, dict) or any(len(str(step.get(key, "")).strip()) < 8 for key in causal_fields)
        for step in causal_steps
    ):
        errors.append("novice_causal_steps require known_before, cause, visible_action, new_evidence, and allowed_inference")

    design_chain = plan.get("design_chain", {})
    if not isinstance(design_chain, dict) or any(
        len(str(design_chain.get(key, "")).strip()) < 16
        for key in ("challenge_hash", "deliberation_hash", "design_gate_hash", "precedent_packet_hash")
    ):
        errors.append("design_chain must bind the challenge, first-principles deliberation, design gate, and precedent packet")
    if not plan.get("selected_hypothesis_id"):
        errors.append("scene plan must name the selected first-principles hypothesis")

    regions = plan.get("stage_regions", [])
    region_names: list[str] = []
    if not regions:
        errors.append("stage_regions must declare at least one cognitive region")
    for region in regions:
        name = str(region.get("name", "")) if isinstance(region, dict) else ""
        owner = str(region.get("owner", "")) if isinstance(region, dict) else ""
        teaching_job = str(region.get("teaching_job", "")) if isinstance(region, dict) else ""
        primary_object = str(region.get("primary_object", "")) if isinstance(region, dict) else ""
        detail_strategy = str(region.get("detail_strategy", "")) if isinstance(region, dict) else ""
        if (
            not name
            or not owner
            or len(teaching_job) < 10
            or not primary_object
            or detail_strategy not in {"rich", "supporting", "minimal"}
        ):
            errors.append(
                "each stage region requires name, owner, teaching_job, primary_object, and detail_strategy"
            )
            continue
        if detail_strategy == "minimal" and len(str(region.get("detail_reason", "")).strip()) < 12:
            errors.append(f"minimal stage region {name!r} requires a concrete detail_reason")
        region_names.append(name)
    if len(region_names) != len(set(region_names)):
        errors.append("stage region names must be unique")

    relations = plan.get("region_relations", [])
    if len(region_names) > 1 and not relations:
        errors.append("region_relations must explain how the macro regions form one mathematical argument")
    for relation in relations:
        if not isinstance(relation, dict):
            errors.append("each region relation must be an object")
            continue
        source_region = str(relation.get("from", ""))
        target_region = str(relation.get("to", ""))
        if source_region not in region_names or target_region not in region_names or source_region == target_region:
            errors.append("region relation endpoints must name two different declared regions")
        if len(str(relation.get("mathematical_relation", "")).strip()) < 12:
            errors.append("region relation requires a concrete mathematical_relation")
        if "VIS-003" in active_rule_ids:
            if len(str(relation.get("relation_id", "")).strip()) < 4:
                errors.append("VIS-003 requires every region relation to have a relation_id")
            if relation.get("visual_encoding") not in {
                "shared_motion",
                "temporal_sync",
                "formula_bridge",
                "local_connector",
                "continuous_transform",
            }:
                errors.append("VIS-003 requires a disciplined visual_encoding for every region relation")

    refinements = plan.get("region_refinements", [])
    refined_regions = {
        str(item.get("region", ""))
        for item in refinements
        if isinstance(item, dict)
        and item.get("object_id")
        and len(str(item.get("detail", "")).strip()) >= 8
        and len(str(item.get("mathematical_meaning", "")).strip()) >= 12
        and len(str(item.get("novice_value", "")).strip()) >= 12
    }
    for region in regions:
        if isinstance(region, dict) and region.get("detail_strategy") in {"rich", "supporting"} and region.get("name") not in refined_regions:
            errors.append(f"stage region {region.get('name')!r} requires a semantically owned region_refinement")
    for item in refinements:
        if not isinstance(item, dict) or not item.get("object_id") or item.get("region") not in region_names:
            errors.append("region_refinement must name an object_id and target a declared stage region")
            break

    identity_map = plan.get("identity_map", [])
    if not identity_map or any(
        not isinstance(item, dict)
        or not item.get("object_id")
        or len(str(item.get("mathematical_identity", "")).strip()) < 8
        or len(str(item.get("persistent_cue", "")).strip()) < 8
        for item in identity_map
    ):
        errors.append("identity_map requires object_id, mathematical_identity, and persistent_cue for continuing objects")

    if profile.get("autopilot_contract_version"):
        invariant_duration = float(profile.get("context", {}).get("duration") or 0.0)
        invariants = plan.get("math_object_invariants", [])
        invariant_ids: set[str] = set()
        invariant_objects: set[str] = set()
        if not isinstance(invariants, list) or not invariants:
            errors.append("autopilot scenes require executable math_object_invariants")
            invariants = []
        for invariant in invariants:
            if not isinstance(invariant, dict):
                errors.append("each math_object_invariant must be a structured object")
                continue
            invariant_id = str(invariant.get("invariant_id", ""))
            object_id = str(invariant.get("object_id", ""))
            evidence_type = str(invariant.get("evidence_type", ""))
            checkpoints = invariant.get("checkpoints", [])
            if not invariant_id or invariant_id in invariant_ids:
                errors.append("math_object_invariant requires a unique invariant_id")
            if not object_id:
                errors.append(f"math_object_invariant {invariant_id!r} requires object_id")
            if len(str(invariant.get("mathematical_claim", "")).strip()) < 12:
                errors.append(f"math_object_invariant {invariant_id!r} requires a concrete mathematical_claim")
            if len(str(invariant.get("expected_relation", "")).strip()) < 10:
                errors.append(f"math_object_invariant {invariant_id!r} requires an expected_relation")
            if evidence_type not in MATH_INVARIANT_EVIDENCE_TYPES:
                errors.append(f"math_object_invariant {invariant_id!r} uses unsupported evidence_type")
            if not isinstance(checkpoints, list) or not checkpoints:
                errors.append(f"math_object_invariant {invariant_id!r} requires runtime checkpoints")
            else:
                for value in checkpoints:
                    try:
                        checkpoint = float(value)
                    except (TypeError, ValueError):
                        errors.append(f"math_object_invariant {invariant_id!r} has a non-numeric checkpoint")
                        continue
                    if checkpoint < 0 or (invariant_duration and checkpoint > invariant_duration + 0.25):
                        errors.append(f"math_object_invariant {invariant_id!r} checkpoint is outside the scene")
            invariant_ids.add(invariant_id)
            invariant_objects.add(object_id)
        primary_objects = {
            str(region.get("primary_object"))
            for region in regions
            if isinstance(region, dict) and region.get("primary_object")
        }
        uncovered_objects = sorted(primary_objects - invariant_objects)
        if uncovered_objects:
            errors.append(
                "math_object_invariants do not cover primary stage objects: " + ", ".join(uncovered_objects)
            )

    attention_budget = plan.get("attention_budget", {})
    try:
        max_focal = int(attention_budget.get("max_simultaneous_focal_points", 0))
    except (TypeError, ValueError):
        max_focal = 0
    if max_focal not in {1, 2}:
        errors.append("attention_budget.max_simultaneous_focal_points must be 1 or 2")
    if max_focal == 2 and len(str(attention_budget.get("comparison_reason", "")).strip()) < 12:
        errors.append("two simultaneous focal points require a concrete comparison_reason")

    subtitle = plan.get("subtitle_safe_zone", {})
    try:
        bottom_fraction = float(subtitle.get("bottom_fraction", 0.0))
    except (TypeError, ValueError):
        bottom_fraction = 0.0
    if bottom_fraction < 0.16:
        errors.append("subtitle_safe_zone.bottom_fraction must be at least 0.16")
    if subtitle.get("owners"):
        errors.append("subtitle safe zone must not have visual owners")
    duration = float(profile.get("context", {}).get("duration") or 0.0)

    stage_states = plan.get("stage_states", [])
    state_ids: list[str] = []
    state_intervals: list[tuple[float, float, str]] = []
    state_signatures: dict[str, dict[str, Any]] = {}
    if not stage_states:
        errors.append("stage_states must describe the time-varying cognitive topology")
    for state in stage_states:
        if not isinstance(state, dict):
            errors.append("each stage state must be an object")
            continue
        state_id = str(state.get("id", ""))
        try:
            state_start, state_end = float(state.get("start")), float(state.get("end"))
        except (TypeError, ValueError):
            errors.append(f"stage state {state_id!r} has invalid timing")
            continue
        if not state_id or state_start < 0 or state_end <= state_start or (duration and state_end > duration + 0.25):
            errors.append(f"stage state {state_id!r} has invalid identity or interval")
            continue
        if len(str(state.get("learner_task", "")).strip()) < 10:
            errors.append(f"stage state {state_id!r} requires a concrete learner_task")
        math_state_id = str(state.get("math_state_id", ""))
        if len(math_state_id) < 3:
            errors.append(f"stage state {state_id!r} requires a math_state_id")
        placements = state.get("active_regions", [])
        if not isinstance(placements, list) or not placements:
            errors.append(f"stage state {state_id!r} requires active_regions")
            continue
        parsed_placements: list[tuple[str, list[float], str]] = []
        for placement in placements:
            region = str(placement.get("region", "")) if isinstance(placement, dict) else ""
            bounds = placement.get("bounds") if isinstance(placement, dict) else None
            salience = str(placement.get("salience", "")) if isinstance(placement, dict) else ""
            view_mapping = str(placement.get("view_mapping", "")) if isinstance(placement, dict) else ""
            if region not in region_names or salience not in {"primary", "supporting", "context"} or len(view_mapping) < 8:
                errors.append(f"stage state {state_id!r} placement requires declared region, salience, and view_mapping")
                continue
            if not isinstance(bounds, list) or len(bounds) != 4:
                errors.append(f"stage state {state_id!r} region {region!r} requires four normalized bounds")
                continue
            try:
                values = [float(value) for value in bounds]
            except (TypeError, ValueError):
                errors.append(f"stage state {state_id!r} region {region!r} has non-numeric bounds")
                continue
            if not all(0.0 <= value <= 1.0 for value in values) or values[0] >= values[2] or values[1] >= values[3]:
                errors.append(f"stage state {state_id!r} region {region!r} has invalid bounds")
                continue
            if values[1] < bottom_fraction:
                errors.append(f"stage state {state_id!r} region {region!r} enters the subtitle safe zone")
            parsed_placements.append((region, values, salience))
        primary_regions = [region for region, _, salience in parsed_placements if salience == "primary"]
        if not primary_regions or len(primary_regions) > max_focal:
            errors.append(f"stage state {state_id!r} must have 1-{max_focal} primary regions")
        overlap_exceptions: set[tuple[str, str]] = set()
        for exception in state.get("allowed_region_overlaps", []):
            if not isinstance(exception, dict):
                errors.append(f"stage state {state_id!r} overlap exception must be structured")
                continue
            pair = tuple(sorted((str(exception.get("a", "")), str(exception.get("b", "")))))
            if pair[0] not in region_names or pair[1] not in region_names or len(str(exception.get("reason", "")).strip()) < 12:
                errors.append(f"stage state {state_id!r} overlap exception requires two regions and a concrete reason")
                continue
            overlap_exceptions.add(pair)
        for index, (left_name, left_bounds, _) in enumerate(parsed_placements):
            for right_name, right_bounds, _ in parsed_placements[index + 1 :]:
                if rectangles_overlap(left_bounds, right_bounds) and tuple(sorted((left_name, right_name))) not in overlap_exceptions:
                    errors.append(f"stage state {state_id!r} has unapproved region overlap: {left_name!r} and {right_name!r}")
        state_ids.append(state_id)
        state_intervals.append((state_start, state_end, state_id))
        state_signatures[state_id] = {
            "M": math_state_id,
            "D": [
                {
                    "region": region,
                    "bounds": [round(value, 6) for value in bounds],
                    "view_mapping": next(
                        (
                            str(item.get("view_mapping"))
                            for item in placements
                            if isinstance(item, dict) and item.get("region") == region
                        ),
                        "",
                    ),
                }
                for region, bounds, _ in sorted(parsed_placements, key=lambda item: item[0])
            ],
            "A": sorted(primary_regions),
        }
    if len(state_ids) != len(set(state_ids)):
        errors.append("stage state ids must be unique")
    ordered_states = sorted(state_intervals)
    if state_intervals != ordered_states:
        errors.append("stage states must be ordered by time")
    for previous, current in zip(ordered_states, ordered_states[1:]):
        if current[0] < previous[1] - 1e-6:
            errors.append(f"stage states overlap at {current[0]:.3f}s")
    state_covered = sum(end - start for start, end, _ in ordered_states)
    if duration and state_covered / duration < 0.85:
        errors.append(f"stage states cover only {state_covered / duration:.1%} of scene duration; require at least 85%")

    transitions = plan.get("stage_transitions", [])
    transition_pairs: set[tuple[str, str]] = set()
    state_interval_by_id = {state_id: (start, end) for start, end, state_id in ordered_states}
    for transition in transitions:
        if not isinstance(transition, dict):
            errors.append("each stage transition must be an object")
            continue
        source_state, target_state = str(transition.get("from_state", "")), str(transition.get("to_state", ""))
        source_focus, target_focus = str(transition.get("from_focus_region", "")), str(transition.get("to_focus_region", ""))
        if source_state not in state_ids or target_state not in state_ids or source_state == target_state:
            errors.append("stage transition endpoints must name two different stage states")
        try:
            transition_start = float(transition.get("start"))
            transition_end = float(transition.get("end"))
        except (TypeError, ValueError):
            transition_start = transition_end = -1.0
            errors.append("stage transition requires numeric start and end")
        if transition_start < 0 or transition_end <= transition_start or (duration and transition_end > duration + 0.25):
            errors.append("stage transition interval is invalid")
        if source_state in state_interval_by_id and target_state in state_interval_by_id:
            source_end = state_interval_by_id[source_state][1]
            target_start = state_interval_by_id[target_state][0]
            if transition_start > source_end + 0.05 or transition_end < target_start - 0.05:
                errors.append("stage transition interval must bridge the source and target state boundary")
        if source_focus not in region_names or target_focus not in region_names:
            errors.append("stage transition focus endpoints must name declared regions")
        transition_fields = ("pedagogical_trigger", "view_mapping_change", "context_policy", "continuity_test")
        if any(len(str(transition.get(key, "")).strip()) < 10 for key in transition_fields):
            errors.append("stage transition requires pedagogical trigger, view-mapping change, context policy, and continuity test")
        interpolation = transition.get("interpolation_contract", {})
        if not isinstance(interpolation, dict) or any(
            len(str(interpolation.get(key, "")).strip()) < 10
            for key in ("geometry_path", "identity_path", "view_mapping_path", "context_release")
        ):
            errors.append("stage transition requires geometry, identity, view-mapping, and context-release interpolation contracts")
        carriers = transition.get("identity_carriers", [])
        continuity_mode = transition.get(
            "continuity_mode",
            "identity_preserving" if isinstance(carriers, list) and carriers else "",
        )
        if not isinstance(carriers, list):
            errors.append("stage transition identity_carriers must be a list")
        elif continuity_mode == "identity_preserving" and not carriers:
            errors.append("identity-preserving stage transition requires at least one identity_carrier")
        elif continuity_mode == "full_clear" and carriers:
            errors.append("full-clear stage transition must not declare identity_carriers")
        elif continuity_mode == "full_clear":
            full_clear_contract = " ".join(
                str(value).lower()
                for value in (
                    transition.get("view_mapping_change", ""),
                    transition.get("context_policy", ""),
                    interpolation.get("identity_path", "") if isinstance(interpolation, dict) else "",
                )
            )
            if "full-clear" not in full_clear_contract and "no object identity" not in full_clear_contract:
                errors.append("full-clear stage transition must explicitly declare the continuity break")
        elif continuity_mode != "identity_preserving":
            errors.append("stage transition continuity_mode must be identity_preserving or full_clear")
        source_signature = state_signatures.get(source_state)
        target_signature = state_signatures.get(target_state)
        if source_signature and target_signature:
            actual_vector = [key for key in ("M", "D", "A") if source_signature[key] != target_signature[key]]
            declared_vector = transition.get("change_vector", [])
            if not isinstance(declared_vector, list) or set(map(str, declared_vector)) != set(actual_vector):
                errors.append(
                    f"stage transition {source_state!r} -> {target_state!r} declares {declared_vector!r} but computed M/D/A change is {actual_vector!r}"
                )
            if not actual_vector:
                errors.append(f"stage transition {source_state!r} -> {target_state!r} changes no M/D/A component")
            change_order = transition.get("change_order", [])
            if len(actual_vector) > 1 and (
                not isinstance(change_order, list) or set(map(str, change_order)) != set(actual_vector)
            ):
                errors.append("multi-component stage transition requires a change_order covering the computed M/D/A vector")
            if "M" in actual_vector and len(str(transition.get("math_driver_event", "")).strip()) < 10:
                errors.append("M-changing stage transition requires a concrete math_driver_event")
            if "D" in actual_vector and len(str(transition.get("view_mapping_change", "")).strip()) < 10:
                errors.append("D-changing stage transition requires a concrete view_mapping_change")
            if "A" in actual_vector and (
                source_focus not in source_signature["A"] or target_focus not in target_signature["A"]
            ):
                errors.append("A-changing stage transition focus endpoints must match the computed primary regions")
        transition_pairs.add((source_state, target_state))
    for previous, current in zip(ordered_states, ordered_states[1:]):
        if (previous[2], current[2]) not in transition_pairs:
            errors.append(f"missing stage transition {previous[2]!r} -> {current[2]!r}")

    beats = plan.get("beats", [])
    intervals: list[tuple[float, float]] = []
    repeat_rejected = "repeat_rejected" in tags
    introduced_concepts: set[str] = set()
    for beat in beats:
        required_beat_fields = (
            "start",
            "end",
            "narration_cue",
            "active_objects",
            "visible_change",
            "cause",
            "knowledge_before",
            "visual_evidence",
            "learner_inference",
        )
        if not isinstance(beat, dict) or not all(beat.get(key) not in (None, "", []) for key in required_beat_fields):
            errors.append(
                "every beat requires timing, cue, active_objects, visible_change, cause, knowledge_before, visual_evidence, and learner_inference"
            )
            continue
        try:
            start, end = float(beat["start"]), float(beat["end"])
        except (TypeError, ValueError):
            errors.append("beat start/end must be numeric")
            continue
        if start < 0 or end <= start or (duration and end > duration + 0.25):
            errors.append(f"invalid beat interval {start}-{end}")
            continue
        intervals.append((start, end))
        if repeat_rejected:
            beat_id = str(beat.get("beat_id", ""))
            available = beat.get("concepts_available_before", [])
            introduced = beat.get("concepts_introduced", [])
            pointing = beat.get("pointing_target_ids", [])
            evidence_mode = str(beat.get("evidence_mode", ""))
            try:
                settle = float(beat.get("min_settle_seconds", 0.0))
                max_new = int(beat.get("max_new_concepts", 0))
            except (TypeError, ValueError):
                settle, max_new = 0.0, 0
            if not beat_id or not isinstance(available, list) or not isinstance(introduced, list):
                errors.append("repeat-rejected beats require beat_id and structured concept ledgers")
            if set(map(str, available)) != introduced_concepts:
                errors.append(f"beat {beat_id!r} concepts_available_before does not equal the accumulated novice ledger")
            if max_new not in {1, 2} or len(introduced) > max_new:
                errors.append(f"beat {beat_id!r} exceeds its declared new-concept budget")
            if len(introduced) > 1 and len(str(beat.get("multi_concept_reason", "")).strip()) < 16:
                errors.append(f"beat {beat_id!r} introduces multiple concepts without a concrete coupling reason")
            if settle < 1.20:
                errors.append(f"beat {beat_id!r} allows only {settle:.2f}s settling; require at least 1.20s")
            if evidence_mode not in {"concrete_action", "comparison", "continuous_transform", "prediction_test"}:
                errors.append(f"beat {beat_id!r} requires novice-visible evidence, not formula-only presentation")
            if not isinstance(pointing, list) or not pointing:
                errors.append(f"beat {beat_id!r} requires at least one pointing_target_id")
            introduced_concepts.update(map(str, introduced))
    intervals.sort()
    for previous, current in zip(intervals, intervals[1:]):
        if current[0] < previous[1] - 1e-6:
            errors.append(f"beat intervals overlap at {current[0]:.3f}s")
    covered = sum(end - start for start, end in intervals)
    if duration and covered / duration < 0.85:
        errors.append(f"beat plan covers only {covered / duration:.1%} of scene duration; require at least 85%")

    decisions = plan.get("history_decisions", [])
    for item in decisions:
        if not isinstance(item, dict) or item.get("decision") not in {"reuse", "adapt", "reject", "no_fit"} or len(str(item.get("reason", ""))) < 12:
            errors.append("each history decision requires a valid decision and concrete reason")
            break

    required_patterns = {
        str(item.get("pattern_key"))
        for item in profile.get("regressions", [])
        if item.get("pattern_key")
    } | set(map(str, profile.get("live_policy_required_patterns", [])))
    prevention = plan.get("regression_prevention", [])
    prevented = {str(item.get("pattern_key")) for item in prevention if isinstance(item, dict) and item.get("prevention") and item.get("evidence_target")}
    missing_patterns = sorted(required_patterns - prevented)
    if missing_patterns:
        errors.append(f"regression_prevention missing pattern keys: {', '.join(missing_patterns)}")

    if "formula_dense" in tags and len(plan.get("formula_history", [])) < 2:
        errors.append("formula-dense scene requires at least two formula_history entries")
    if "formula_dense" in tags:
        choreography = plan.get("formula_choreography", [])
        if len(choreography) < 2 or any(
            not isinstance(item, dict)
            or not item.get("cue_id")
            or len(str(item.get("spoken_anchor", "")).strip()) < 4
            or not item.get("object_id")
            or not item.get("target_token")
            or len(str(item.get("visual_action", "")).strip()) < 8
            for item in choreography
        ):
            errors.append(
                "formula-dense scene requires at least two formula_choreography entries with cue, spoken anchor, object, token, and visual action"
            )
        if "FORM-003" in active_rule_ids and any(
            item.get("emphasis_mode") not in {"non_geometric", "scale_then_restore"}
            or len(str(item.get("rest_geometry_policy", "")).strip()) < 12
            for item in choreography
            if isinstance(item, dict)
        ):
            errors.append("FORM-003 requires an emphasis_mode and rest_geometry_policy for every formula cue")
    if "TIME-002" in active_rule_ids:
        clause_locks = plan.get("clause_locks", [])
        if len(clause_locks) < len(beats) or any(
            not isinstance(item, dict)
            or not item.get("cue_id")
            or not item.get("object_id")
            or len(str(item.get("spoken_clause", "")).strip()) < 6
            or len(str(item.get("expected_change", "")).strip()) < 8
            or item.get("spoken_start") is None
            for item in clause_locks
        ):
            errors.append("TIME-002 requires at least one structured clause_lock per planned beat")
    if plan.get("timing_contract_version") == "word_anchor_v1":
        source = plan.get("word_alignment_source", {})
        anchors = plan.get("word_anchors", [])
        if (
            not isinstance(source, dict)
            or len(str(source.get("path", "")).strip()) < 8
            or len(str(source.get("sha256", "")).strip()) != 64
            or source.get("scene_start") is None
        ):
            errors.append("word_anchor_v1 requires a hashed word_alignment_source and scene_start")
        if not isinstance(anchors, list) or len(anchors) < 4:
            errors.append("word_anchor_v1 requires at least four selected word anchors")
            anchors = []
        anchor_ids: set[str] = set()
        previous_start = -1.0
        for anchor in anchors:
            if not isinstance(anchor, dict):
                errors.append("each word anchor must be structured")
                continue
            anchor_id = str(anchor.get("anchor_id", ""))
            try:
                absolute_start = float(anchor.get("absolute_start"))
                absolute_end = float(anchor.get("absolute_end"))
                local_start = float(anchor.get("local_start"))
                scene_start = float(source.get("scene_start"))
            except (TypeError, ValueError):
                errors.append(f"word anchor {anchor_id!r} has invalid timing")
                continue
            if not anchor_id or anchor_id in anchor_ids:
                errors.append("word anchors require unique anchor_id values")
            if absolute_end <= absolute_start or abs(local_start - (absolute_start - scene_start)) > 0.002:
                errors.append(f"word anchor {anchor_id!r} is not derived from its absolute word timestamp")
            if local_start < previous_start:
                errors.append("word anchors must be ordered by local_start")
            if len(str(anchor.get("token", "")).strip()) < 1 or len(str(anchor.get("visual_action", "")).strip()) < 8:
                errors.append(f"word anchor {anchor_id!r} requires token and visual_action")
            evidence_type = str(anchor.get("evidence_type", ""))
            if len(str(anchor.get("target_id", "")).strip()) < 1:
                errors.append(f"word anchor {anchor_id!r} requires a target_id")
            if evidence_type not in {"runtime_action", "emphasis_event", "formula_handoff"}:
                errors.append(f"word anchor {anchor_id!r} has unsupported evidence_type {evidence_type!r}")
            if len(str(anchor.get("evidence_id", "")).strip()) < 1:
                errors.append(f"word anchor {anchor_id!r} requires an evidence_id")
            previous_start = local_start
            anchor_ids.add(anchor_id)
    if "limit_process" in tags:
        required_steps = {"finite_object", "refining_parameter", "intermediate_state", "limiting_object"}
        missing_steps = required_steps - set(map(str, plan.get("causal_step_ids", [])))
        if missing_steps:
            errors.append(f"limit process missing causal_step_ids: {', '.join(sorted(missing_steps))}")
    return errors


def bbox_overlap_area(left: list[float], right: list[float]) -> float:
    width = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    height = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    return width * height


def bbox_inside(inner: list[float], outer: list[float], padding: float = 0.0) -> bool:
    return (
        inner[0] >= outer[0] + padding
        and inner[1] >= outer[1] + padding
        and inner[2] <= outer[2] - padding
        and inner[3] <= outer[3] - padding
    )


def bbox_gap(left: list[float], right: list[float]) -> tuple[float, float]:
    horizontal = max(0.0, max(left[0], right[0]) - min(left[2], right[2]))
    vertical = max(0.0, max(left[1], right[1]) - min(left[3], right[3]))
    return horizontal, vertical


def validate_authoring_qc_data(
    profile: dict[str, Any],
    plan: dict[str, Any],
    telemetry: dict[str, Any],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    tags = set(profile.get("tags", []))
    active_rule_ids = {
        str(rule.get("rule_id"))
        for rule in profile.get("rules", [])
        if isinstance(rule, dict) and rule.get("status") == "active"
    }

    def add_issue(code: str, message: str, time: float | None = None, objects: list[str] | None = None) -> None:
        key = (code, None if time is None else round(time, 3), tuple(sorted(objects or [])), message)
        if key in seen:
            return
        seen.add(key)
        issue: dict[str, Any] = {"code": code, "severity": "blocker", "message": message}
        if time is not None:
            issue["time"] = round(time, 3)
        if objects:
            issue["objects"] = objects
        issues.append(issue)

    if telemetry.get("schema") != "lecture-animation-authoring-telemetry-v2":
        add_issue("TELEMETRY_SCHEMA", "telemetry schema must be lecture-animation-authoring-telemetry-v2")
    if telemetry.get("profile_hash") != profile.get("profile_hash"):
        add_issue("TELEMETRY_PROFILE", "telemetry profile_hash does not match the compiled profile")
    expected_slug = profile.get("context", {}).get("scene_slug")
    if telemetry.get("scene_slug") != expected_slug:
        add_issue("TELEMETRY_SCENE", f"telemetry scene_slug must be {expected_slug!r}")
    capture = telemetry.get("capture_source", {})
    if (
        not isinstance(capture, dict)
        or capture.get("mode") not in {"runtime_export", "frame_analysis"}
        or len(str(capture.get("source_path", "")).strip()) < 4
    ):
        add_issue("CAPTURE_SOURCE", "capture_source must identify a runtime_export or frame_analysis artifact; manual assertions are not accepted")

    frame = telemetry.get("frame", {})
    try:
        width = int(frame.get("width", 0))
        height = int(frame.get("height", 0))
        fps = float(frame.get("fps", 0.0))
        duration = float(frame.get("duration", 0.0))
    except (TypeError, ValueError):
        width = height = 0
        fps = duration = 0.0
    if width < 640 or height < 360 or fps <= 0 or duration <= 0:
        add_issue("FRAME_METADATA", "frame requires positive duration/fps and a render size of at least 640x360")
    profile_duration = float(profile.get("context", {}).get("duration") or 0.0)
    if profile_duration and abs(duration - profile_duration) > 0.5:
        add_issue("DURATION_MISMATCH", f"telemetry duration {duration:.3f}s differs from profile duration {profile_duration:.3f}s")

    thresholds = telemetry.get("thresholds", {})
    try:
        subtitle_fraction = float(plan.get("subtitle_safe_zone", {}).get("bottom_fraction", 0.16))
        min_gap = float(thresholds.get("min_gap_normalized", 0.008))
        max_visual_lag = float(thresholds.get("max_visual_lag_seconds", 0.25))
        max_visual_lead = float(thresholds.get("max_visual_lead_seconds", 0.35))
        max_transition = float(thresholds.get("max_transition_seconds", 0.75))
        max_linger = float(thresholds.get("max_linger_seconds", 0.50))
    except (TypeError, ValueError):
        subtitle_fraction, min_gap = 0.16, 0.008
        max_visual_lag, max_visual_lead, max_transition, max_linger = 0.25, 0.35, 0.75, 0.50
        add_issue("THRESHOLD_TYPE", "authoring telemetry thresholds must be numeric")
    if not (0.0 < min_gap <= 0.05):
        add_issue("MIN_GAP_THRESHOLD", "min_gap_normalized must be in (0, 0.05]")

    runtime_formula_handoffs = {
        str(item.get("handoff_id")): item
        for item in telemetry.get("formula_handoffs", [])
        if isinstance(item, dict) and item.get("handoff_id")
    }
    for planned_handoff in plan.get("formula_handoffs", []):
        if not isinstance(planned_handoff, dict):
            add_issue("FORMULA_HANDOFF_PLAN", "formula handoff contracts must be structured objects")
            continue
        handoff_id = str(planned_handoff.get("handoff_id", ""))
        event = runtime_formula_handoffs.get(handoff_id)
        if event is None:
            add_issue("FORMULA_HANDOFF_AUDIT_MISSING", f"formula handoff {handoff_id!r} has no runtime serialization evidence")
            continue
        try:
            required_gap = float(planned_handoff.get("minimum_empty_gap_seconds", 0.03))
            actual_gap = float(event.get("gap_seconds", -1.0))
            overlap = float(event.get("overlap_seconds", 1.0))
        except (TypeError, ValueError):
            required_gap, actual_gap, overlap = 0.03, -1.0, 1.0
        if not bool(event.get("serialized")) or overlap > 1e-6:
            add_issue("FORMULA_HANDOFF_OVERLAP", f"formula handoff {handoff_id!r} allows simultaneous equation occupancy")
        if actual_gap + 1e-6 < required_gap:
            add_issue("FORMULA_HANDOFF_GAP", f"formula handoff {handoff_id!r} has {actual_gap:.3f}s empty gap; requires {required_gap:.3f}s")
        if str(event.get("outgoing_object_id", "")) != str(planned_handoff.get("outgoing_object_id", "")):
            add_issue("FORMULA_HANDOFF_IDENTITY", f"formula handoff {handoff_id!r} outgoing identity does not match the plan")
        if str(event.get("incoming_object_id", "")) != str(planned_handoff.get("incoming_object_id", "")):
            add_issue("FORMULA_HANDOFF_IDENTITY", f"formula handoff {handoff_id!r} incoming identity does not match the plan")

    runtime_identity_bindings = {
        str(item.get("binding_id")): item
        for item in telemetry.get("identity_bindings", [])
        if isinstance(item, dict) and item.get("binding_id")
    }
    for planned_binding in plan.get("identity_bindings", []):
        if not isinstance(planned_binding, dict):
            add_issue("IDENTITY_BINDING_PLAN", "identity binding contracts must be structured objects")
            continue
        binding_id = str(planned_binding.get("binding_id", ""))
        event = runtime_identity_bindings.get(binding_id)
        if event is None:
            add_issue("IDENTITY_BINDING_MISSING", f"identity binding {binding_id!r} has no runtime evidence")
            continue
        try:
            planned_max = float(planned_binding.get("max_distance_normalized", 0.05))
            runtime_max = float(event.get("max_distance_normalized", -1.0))
        except (TypeError, ValueError):
            planned_max, runtime_max = 0.05, -1.0
        samples = event.get("samples", [])
        if not isinstance(samples, list) or len(samples) < 2:
            add_issue("IDENTITY_BINDING_SAMPLES", f"identity binding {binding_id!r} requires at least two runtime samples")
            continue
        if abs(runtime_max - planned_max) > 1e-6:
            add_issue("IDENTITY_BINDING_THRESHOLD", f"identity binding {binding_id!r} threshold differs from the plan")
        for sample in samples:
            try:
                distance = float(sample.get("distance_normalized"))
                sample_time = float(sample.get("time"))
            except (TypeError, ValueError, AttributeError):
                add_issue("IDENTITY_BINDING_SAMPLE", f"identity binding {binding_id!r} has malformed samples")
                break
            if distance > planned_max + 1e-6:
                add_issue("IDENTITY_BINDING_DRIFT", f"identity binding {binding_id!r} drifts {distance:.4f} beyond {planned_max:.4f}", time=sample_time)

    runtime_coordinate_checks = {
        str(item.get("check_id")): item
        for item in telemetry.get("coordinate_checks", [])
        if isinstance(item, dict) and item.get("check_id")
    }
    for planned_check in plan.get("coordinate_checks", []):
        if not isinstance(planned_check, dict):
            add_issue("COORDINATE_CHECK_PLAN", "coordinate checks must be structured objects")
            continue
        check_id = str(planned_check.get("check_id", ""))
        event = runtime_coordinate_checks.get(check_id)
        if event is None:
            add_issue("COORDINATE_CHECK_MISSING", f"coordinate check {check_id!r} has no runtime evidence")
            continue
        try:
            planned_max = float(planned_check.get("max_error_normalized", 0.002))
            runtime_max = float(event.get("max_error_normalized", -1.0))
            error = float(event.get("error_normalized", 1.0))
            event_time = float(event.get("time"))
        except (TypeError, ValueError):
            planned_max, runtime_max, error, event_time = 0.002, -1.0, 1.0, 0.0
        if abs(runtime_max - planned_max) > 1e-6:
            add_issue("COORDINATE_CHECK_THRESHOLD", f"coordinate check {check_id!r} threshold differs from the plan")
        if str(event.get("object_id", "")) != str(planned_check.get("object_id", "")):
            add_issue("COORDINATE_CHECK_IDENTITY", f"coordinate check {check_id!r} measures the wrong object")
        if error > planned_max + 1e-6:
            add_issue("COORDINATE_DRIFT", f"coordinate check {check_id!r} has error {error:.4f} beyond {planned_max:.4f}", time=event_time)

    if int(profile.get("autopilot_contract_version") or 0) >= 3:
        planned_math_objects = {
            str(item.get("object_id")): item
            for item in plan.get("math_objects", [])
            if isinstance(item, dict) and item.get("object_id")
        }
        planned_mappings = {
            str(item.get("mapping_id")): item
            for item in plan.get("display_mappings", [])
            if isinstance(item, dict) and item.get("mapping_id")
        }
        runtime_bindings = {
            str(item.get("visual_object_id")): item
            for item in telemetry.get("math_object_bindings", [])
            if isinstance(item, dict) and item.get("visual_object_id")
        }
        for binding in plan.get("visual_bindings", []):
            if not isinstance(binding, dict):
                continue
            visual_id = str(binding.get("visual_object_id", ""))
            math_object_id = str(binding.get("math_object_id", ""))
            mapping_id = str(binding.get("display_mapping_id", ""))
            event = runtime_bindings.get(visual_id)
            if event is None:
                add_issue("MATH_OBJECT_BINDING_MISSING", f"visual object {visual_id!r} has no runtime mathematical binding", objects=[visual_id])
                continue
            if str(event.get("math_object_id", "")) != math_object_id:
                add_issue("MATH_OBJECT_IDENTITY_DRIFT", f"visual object {visual_id!r} is bound to the wrong mathematical object", objects=[visual_id])
            if str(event.get("display_mapping_id", "")) != mapping_id:
                add_issue("DISPLAY_MAPPING_DRIFT", f"visual object {visual_id!r} uses a different display mapping than planned", objects=[visual_id])
            expected_drivers = set(map(str, planned_math_objects.get(math_object_id, {}).get("driver_ids", [])))
            actual_drivers = set(map(str, event.get("driver_ids", [])))
            if expected_drivers != actual_drivers:
                add_issue("MATH_DRIVER_DRIFT", f"visual object {visual_id!r} runtime drivers do not match its mathematical object", objects=[visual_id])
            samples = event.get("samples", [])
            if not isinstance(samples, list) or len(samples) < 2:
                add_issue("MATH_OBJECT_BINDING_SAMPLES", f"visual object {visual_id!r} requires at least two runtime binding samples", objects=[visual_id])
                continue
            for sample in samples:
                if not isinstance(sample, dict):
                    add_issue("MATH_OBJECT_BINDING_SAMPLE", f"visual object {visual_id!r} has a malformed binding sample", objects=[visual_id])
                    continue
                try:
                    sample_time = float(sample.get("time"))
                except (TypeError, ValueError):
                    sample_time = None
                    add_issue("MATH_OBJECT_BINDING_SAMPLE", f"visual object {visual_id!r} binding sample lacks numeric time", objects=[visual_id])
                if sample.get("passed") is not True:
                    add_issue("MATH_OBJECT_BINDING_FAILED", f"visual object {visual_id!r} failed a runtime binding assertion", time=sample_time, objects=[visual_id])
                driver_values = sample.get("driver_values", {})
                if not isinstance(driver_values, dict) or set(map(str, driver_values)) != expected_drivers:
                    add_issue("MATH_DRIVER_SAMPLE", f"visual object {visual_id!r} sample does not expose every mathematical driver", time=sample_time, objects=[visual_id])
                if len(str(sample.get("math_state_id", "")).strip()) < 3:
                    add_issue("MATH_STATE_SAMPLE", f"visual object {visual_id!r} sample lacks math_state_id", time=sample_time, objects=[visual_id])

        runtime_mapping_checks = {
            str(item.get("mapping_id")): item
            for item in telemetry.get("display_mapping_checks", [])
            if isinstance(item, dict) and item.get("mapping_id")
        }
        for mapping_id, mapping in planned_mappings.items():
            check = runtime_mapping_checks.get(mapping_id)
            if check is None:
                add_issue("DISPLAY_MAPPING_CHECK_MISSING", f"display mapping {mapping_id!r} has no runtime check")
                continue
            if str(check.get("source_object_id", "")) != str(mapping.get("source_object_id", "")):
                add_issue("DISPLAY_MAPPING_SOURCE_DRIFT", f"display mapping {mapping_id!r} measures the wrong source object")
            if str(check.get("mode", "")) != str(mapping.get("mode", "")):
                add_issue("DISPLAY_MAPPING_MODE_DRIFT", f"display mapping {mapping_id!r} runtime mode differs from the plan")
            if check.get("passed") is not True:
                add_issue("DISPLAY_MAPPING_FAILED", f"display mapping {mapping_id!r} failed its runtime verification")
            verification = mapping.get("verification", {}) if isinstance(mapping.get("verification"), dict) else {}
            expected_preserves = set(map(str, verification.get("preserved_invariants", [])))
            observed_preserves = set(map(str, check.get("observed_preserved_invariants", [])))
            if not expected_preserves <= observed_preserves:
                add_issue("DISPLAY_INVARIANT_UNVERIFIED", f"display mapping {mapping_id!r} did not verify every preserved invariant")
            expected_distortions = set(map(str, verification.get("distorted_quantities", [])))
            observed_distortions = set(map(str, check.get("observed_distortions", [])))
            if not expected_distortions <= observed_distortions:
                add_issue("DISPLAY_DISTORTION_UNDISCLOSED", f"display mapping {mapping_id!r} runtime evidence omits a declared distortion")
            violations = check.get("forbidden_inference_violations", [])
            if not isinstance(violations, list) or violations:
                add_issue("DISPLAY_MAPPING_MISLEADS", f"display mapping {mapping_id!r} permits a forbidden mathematical inference")

    regions = {str(item.get("name")): item for item in plan.get("stage_regions", []) if isinstance(item, dict) and item.get("name")}
    state_specs: dict[str, dict[str, Any]] = {}
    for state in plan.get("stage_states", []):
        if not isinstance(state, dict) or not state.get("id"):
            continue
        placements = {
            str(item.get("region")): item
            for item in state.get("active_regions", [])
            if isinstance(item, dict) and item.get("region")
        }
        state_specs[str(state["id"])] = {
            "start": float(state.get("start", 0.0)),
            "end": float(state.get("end", 0.0)),
            "math_state_id": str(state.get("math_state_id", "")),
            "placements": placements,
            "primary_regions": sorted(
                str(item.get("region"))
                for item in state.get("active_regions", [])
                if isinstance(item, dict) and item.get("salience") == "primary"
            ),
        }

    def planned_state_at(time: float) -> tuple[str, dict[str, Any]] | None:
        for state_id, spec in state_specs.items():
            if spec["start"] - 1e-6 <= time <= spec["end"] + 1e-6:
                return state_id, spec
        return None
    plan_object_ids = {
        str(item.get("primary_object")) for item in plan.get("stage_regions", []) if isinstance(item, dict) and item.get("primary_object")
    }
    plan_object_ids.update(
        str(item.get("object_id")) for item in plan.get("region_refinements", []) if isinstance(item, dict) and item.get("object_id")
    )
    plan_object_ids.update(
        str(item.get("object_id")) for item in plan.get("identity_map", []) if isinstance(item, dict) and item.get("object_id")
    )

    allowed_pairs: set[tuple[str, str]] = set()
    for item in telemetry.get("allowed_overlaps", []):
        if not isinstance(item, dict):
            add_issue("OVERLAP_EXCEPTION", "every allowed overlap must be a structured object")
            continue
        first, second = str(item.get("a", "")), str(item.get("b", ""))
        if not first or not second or first == second or len(str(item.get("reason", "")).strip()) < 12 or len(str(item.get("anchor_relation", "")).strip()) < 8:
            add_issue("OVERLAP_EXCEPTION", "allowed overlap requires two objects, a concrete reason, and an anchor_relation")
            continue
        allowed_pairs.add(tuple(sorted((first, second))))

    snapshots = telemetry.get("snapshots", [])
    if not isinstance(snapshots, list) or not snapshots:
        add_issue("SNAPSHOT_COVERAGE", "telemetry requires runtime snapshots")
        snapshots = []
    snapshot_times: list[float] = []
    object_ids_seen: set[str] = set()
    font_thresholds = {"title": 42.0, "formula": 34.0, "body": 28.0, "label": 26.0, "tick_label": 20.0}
    background_kinds = {"background", "grid", "axis", "curve", "graph", "plot", "marker"}
    solid_kinds = {"title", "formula", "body", "label", "tick_label", "panel"}
    max_focal = int(plan.get("attention_budget", {}).get("max_simultaneous_focal_points", 1) or 1)

    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            add_issue("SNAPSHOT_FORMAT", "each snapshot must be an object")
            continue
        try:
            time = float(snapshot.get("time"))
        except (TypeError, ValueError):
            add_issue("SNAPSHOT_TIME", "snapshot time must be numeric")
            continue
        snapshot_times.append(time)
        if time < 0 or (duration and time > duration + 0.05):
            add_issue("SNAPSHOT_TIME", "snapshot time is outside the scene", time=time)
        planned_state = planned_state_at(time)
        declared_state_id = str(snapshot.get("stage_state_id", ""))
        if planned_state is None:
            add_issue("STAGE_STATE_MISSING", "snapshot time is not covered by a planned stage state", time=time)
            active_region_bounds: dict[str, list[float]] = {}
        else:
            planned_state_id, state_spec = planned_state
            if declared_state_id != planned_state_id:
                add_issue("STAGE_STATE_MISMATCH", f"snapshot declares {declared_state_id!r} but plan expects {planned_state_id!r}", time=time)
            if str(snapshot.get("math_state_id", "")) != state_spec["math_state_id"]:
                add_issue("M_STATE_MISMATCH", "snapshot math_state_id does not match the planned M state", time=time)
            declared_primary = sorted(map(str, snapshot.get("primary_regions", [])))
            if declared_primary != state_spec["primary_regions"]:
                add_issue("A_STATE_MISMATCH", "snapshot primary_regions do not match the planned attention state", time=time)
            active_region_bounds = {
                region: [float(value) for value in item.get("bounds", [])]
                for region, item in state_spec["placements"].items()
                if len(item.get("bounds", [])) == 4
            }
        for orphan in snapshot.get("orphan_mobjects", []):
            if isinstance(orphan, dict) and float(orphan.get("opacity", 1.0)) > 0.05:
                add_issue(
                    "UNOWNED_VISIBLE_MOBJECT",
                    f"visible {orphan.get('class_name', 'Mobject')} has no tracked mathematical owner",
                    time=time,
                )
        raw_objects = snapshot.get("objects", [])
        if not isinstance(raw_objects, list):
            add_issue("OBJECT_FORMAT", "snapshot objects must be a list", time=time)
            continue
        objects: list[dict[str, Any]] = []
        object_by_id: dict[str, dict[str, Any]] = {}
        for item in raw_objects:
            if not isinstance(item, dict):
                add_issue("OBJECT_FORMAT", "snapshot object must be a structured object", time=time)
                continue
            object_id = str(item.get("id", ""))
            kind = str(item.get("kind", ""))
            region = str(item.get("region", ""))
            role = str(item.get("semantic_role", ""))
            bbox = item.get("bbox")
            if not object_id or not kind or region not in regions or len(role) < 4:
                add_issue("OBJECT_IDENTITY", "object requires id, kind, declared region, and semantic_role", time=time, objects=[object_id] if object_id else None)
                continue
            if not isinstance(bbox, list) or len(bbox) != 4:
                add_issue("OBJECT_BOUNDS", "object bbox must contain four normalized values", time=time, objects=[object_id])
                continue
            try:
                bounds = [float(value) for value in bbox]
                opacity = float(item.get("opacity", 1.0))
            except (TypeError, ValueError):
                add_issue("OBJECT_BOUNDS", "object bbox and opacity must be numeric", time=time, objects=[object_id])
                continue
            item = dict(item)
            item["bbox"] = bounds
            item["opacity"] = opacity
            objects.append(item)
            object_by_id[object_id] = item
            object_ids_seen.add(object_id)
            if item.get("focal") is True and opacity <= 0.10:
                add_issue("FOCAL_OBJECT_INVISIBLE", "the declared focal object is not visibly rendered", time=time, objects=[object_id])
            if bounds[0] < 0 or bounds[1] < 0 or bounds[2] > 1 or bounds[3] > 1 or bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
                add_issue("OUT_OF_FRAME", "object bbox is outside the normalized frame", time=time, objects=[object_id])
            if bounds[1] < subtitle_fraction and opacity > 0.05:
                add_issue("SUBTITLE_INTRUSION", "visible object enters the reserved subtitle zone", time=time, objects=[object_id])
            owner_bounds = active_region_bounds.get(region)
            if owner_bounds is None and opacity > 0.05:
                add_issue("INACTIVE_REGION_OBJECT", f"visible object belongs to inactive region {region!r}", time=time, objects=[object_id])
            elif owner_bounds and not bbox_inside(bounds, owner_bounds, padding=-0.002):
                add_issue("REGION_OVERFLOW", f"object leaves its declared region {region!r}", time=time, objects=[object_id])
            if kind in font_thresholds and opacity > 0.05:
                try:
                    font_px = float(item.get("font_px", 0.0)) * (1080.0 / max(height, 1))
                except (TypeError, ValueError):
                    font_px = 0.0
                threshold = float(thresholds.get(f"min_{kind}_px", font_thresholds[kind]))
                if font_px < threshold:
                    add_issue("TYPE_TOO_SMALL", f"{kind} renders at {font_px:.1f}px normalized to 1080p; require {threshold:.1f}px", time=time, objects=[object_id])

        focal_objects = [str(item.get("id")) for item in objects if item.get("focal") is True and item.get("opacity", 1.0) > 0.10]
        if len(focal_objects) > max_focal:
            add_issue("FOCAL_OVERLOAD", f"{len(focal_objects)} simultaneous focal objects exceed the attention budget {max_focal}", time=time, objects=focal_objects)

        for item in objects:
            container_id = str(item.get("container_id", ""))
            if container_id:
                container = object_by_id.get(container_id)
                if container is None:
                    add_issue("MISSING_CONTAINER", "declared container is absent from the snapshot", time=time, objects=[str(item.get("id")), container_id])
                else:
                    padding = float(item.get("container_padding", 0.004) or 0.004)
                    if not bbox_inside(item["bbox"], container["bbox"], padding=padding):
                        add_issue("CONTAINER_OVERFLOW", "object overflows its declared container", time=time, objects=[str(item.get("id")), container_id])

        for index, left in enumerate(objects):
            if left.get("opacity", 1.0) <= 0.05:
                continue
            for right in objects[index + 1 :]:
                if right.get("opacity", 1.0) <= 0.05:
                    continue
                left_id, right_id = str(left.get("id")), str(right.get("id"))
                pair = tuple(sorted((left_id, right_id)))
                container_pair = left.get("container_id") == right_id or right.get("container_id") == left_id
                anchored_pair = (
                    left.get("anchor_to") == right_id and len(str(left.get("overlap_reason", "")).strip()) >= 8
                ) or (
                    right.get("anchor_to") == left_id and len(str(right.get("overlap_reason", "")).strip()) >= 8
                )
                if pair in allowed_pairs or container_pair or anchored_pair:
                    continue
                left_kind, right_kind = str(left.get("kind")), str(right.get("kind"))
                overlap = bbox_overlap_area(left["bbox"], right["bbox"])
                if overlap > 0.00001 and not (left_kind in background_kinds and right_kind in background_kinds):
                    add_issue("UNAPPROVED_OVERLAP", f"objects overlap by normalized area {overlap:.5f}", time=time, objects=[left_id, right_id])
                    continue
                if left_kind in solid_kinds and right_kind in solid_kinds:
                    horizontal_gap, vertical_gap = bbox_gap(left["bbox"], right["bbox"])
                    horizontal_band_overlap = min(left["bbox"][3], right["bbox"][3]) > max(left["bbox"][1], right["bbox"][1])
                    vertical_band_overlap = min(left["bbox"][2], right["bbox"][2]) > max(left["bbox"][0], right["bbox"][0])
                    if (horizontal_band_overlap and horizontal_gap < min_gap) or (vertical_band_overlap and vertical_gap < min_gap):
                        add_issue("CRAMPED_SPACING", f"solid objects are closer than the normalized gap {min_gap:.3f}", time=time, objects=[left_id, right_id])

    if snapshot_times:
        if snapshot_times != sorted(snapshot_times) or len(snapshot_times) != len(set(snapshot_times)):
            add_issue("SNAPSHOT_ORDER", "snapshot times must be strictly increasing")
        if min(snapshot_times) > 0.5:
            add_issue("SNAPSHOT_OPENING", "QC snapshots do not cover the opening half-second")
        if duration and max(snapshot_times) < duration - 0.5:
            add_issue("SNAPSHOT_ENDING", "QC snapshots do not cover the ending half-second")
        for beat in plan.get("beats", []):
            try:
                start, end = float(beat.get("start")), float(beat.get("end"))
            except (TypeError, ValueError):
                continue
            if not any(start <= time <= end for time in snapshot_times):
                add_issue("BEAT_SNAPSHOT_MISSING", f"no QC snapshot covers beat {start:.3f}-{end:.3f}s")
        if "STAGE-004" in active_rule_ids:
            for handoff in plan.get("stage_transitions", []):
                try:
                    start, end = float(handoff.get("start")), float(handoff.get("end"))
                except (TypeError, ValueError, AttributeError):
                    continue
                if not any(start <= time <= end for time in snapshot_times):
                    add_issue(
                        "TRANSITION_MIDPOINT_UNAUDITED",
                        f"no runtime snapshot covers stage transition {start:.3f}-{end:.3f}s",
                        time=(start + end) / 2,
                    )

    missing_plan_objects = sorted(plan_object_ids - object_ids_seen)
    if missing_plan_objects:
        add_issue("PLANNED_OBJECT_MISSING", f"planned objects never appear in runtime telemetry: {', '.join(missing_plan_objects)}", objects=missing_plan_objects)

    cues = telemetry.get("cues", [])
    cue_ids: set[str] = set()
    handoff_pairs: set[tuple[str, str]] = set()
    if not isinstance(cues, list) or not cues:
        add_issue("CUE_COVERAGE", "telemetry requires narration-to-visual cue records")
        cues = []
    for cue in cues:
        if not isinstance(cue, dict):
            add_issue("CUE_FORMAT", "each cue must be a structured object")
            continue
        cue_id = str(cue.get("cue_id", ""))
        object_id = str(cue.get("object_id", ""))
        cue_ids.add(cue_id)
        if not cue_id or not object_id or len(str(cue.get("change_type", "")).strip()) < 4:
            add_issue("CUE_IDENTITY", "cue requires cue_id, object_id, and a concrete change_type", objects=[object_id] if object_id else None)
            continue
        if object_id not in object_ids_seen:
            add_issue("CUE_OBJECT_MISSING", "cue object never appears in runtime snapshots", objects=[object_id])
        try:
            spoken_start = float(cue.get("spoken_start"))
            spoken_end = float(cue.get("spoken_end"))
            visual_start = float(cue.get("visual_start"))
            visual_end = float(cue.get("visual_end"))
            semantic_end = float(cue.get("semantic_end", spoken_end))
            transition_seconds = float(cue.get("transition_seconds", 0.0))
        except (TypeError, ValueError):
            add_issue("CUE_TIMING", "cue timing values must be numeric", objects=[object_id])
            continue
        if min(spoken_start, visual_start) < 0 or spoken_end <= spoken_start or visual_end < visual_start or (duration and max(spoken_end, visual_end) > duration + 0.10):
            add_issue("CUE_TIMING", "cue interval is invalid or outside the scene", time=visual_start, objects=[object_id])
        lag = visual_start - spoken_start
        if lag > max_visual_lag:
            add_issue("VISUAL_LATE", f"visual evidence begins {lag:.3f}s after speech; maximum is {max_visual_lag:.3f}s", time=visual_start, objects=[object_id])
        if lag < -max_visual_lead and len(str(cue.get("preload_reason", "")).strip()) < 12:
            add_issue("VISUAL_TOO_EARLY", f"focal visual begins {-lag:.3f}s before speech without a preload reason", time=visual_start, objects=[object_id])
        if transition_seconds > max_transition and len(str(cue.get("duration_reason", "")).strip()) < 12:
            add_issue("TRANSITION_TOO_LONG", f"transition lasts {transition_seconds:.3f}s without mathematical justification", time=visual_start, objects=[object_id])
        if visual_end - semantic_end > max_linger and len(str(cue.get("linger_reason", "")).strip()) < 12:
            add_issue("STALE_OBJECT", f"object remains {visual_end - semantic_end:.3f}s after semantic ownership ends", time=semantic_end, objects=[object_id])
        before = cue.get("state_before", {})
        after = cue.get("state_after", {})
        if not isinstance(before, dict) or not isinstance(after, dict) or any(key not in before or key not in after for key in ("M", "D", "A")):
            add_issue("MDA_STATE_MISSING", "cue must export before/after identifiers for M, D, and A", time=visual_start, objects=[object_id])
        else:
            actual_vector = [key for key in ("M", "D", "A") if before.get(key) != after.get(key)]
            declared_vector = cue.get("change_vector", [])
            if not isinstance(declared_vector, list) or set(map(str, declared_vector)) != set(actual_vector):
                add_issue(
                    "MDA_VECTOR_MISMATCH",
                    f"cue declares {declared_vector!r} but before/after states compute {actual_vector!r}",
                    time=visual_start,
                    objects=[object_id],
                )
            if not actual_vector:
                add_issue("EMPTY_VISUAL_CHANGE", "cue changes no mathematical state, display mapping, or attention state", time=visual_start, objects=[object_id])
            if "M" in actual_vector and len(str(cue.get("math_driver_event", "")).strip()) < 10:
                add_issue("M_DRIVER_MISSING", "M-changing cue requires a real math_driver_event", time=visual_start, objects=[object_id])
            if "D" in actual_vector and len(str(cue.get("identity_carrier", "")).strip()) < 8:
                add_issue("D_IDENTITY_MISSING", "D-changing cue requires an identity_carrier", time=visual_start, objects=[object_id])
            if "A" in actual_vector and (
                len(str(cue.get("from_region", "")).strip()) < 2 or len(str(cue.get("to_region", "")).strip()) < 2
            ):
                add_issue("A_HANDOFF_MISSING", "A-changing cue requires from_region and to_region", time=visual_start, objects=[object_id])
        source_region = str(cue.get("from_region", ""))
        target_region = str(cue.get("to_region", ""))
        if source_region and target_region:
            handoff_pairs.add((source_region, target_region))

    def cue_starts_in_interval(cue: Any, start: float, end: float) -> bool:
        if not isinstance(cue, dict):
            return False
        for field in ("spoken_start", "visual_start"):
            try:
                value = float(cue.get(field, -1.0))
            except (TypeError, ValueError):
                continue
            if start <= value <= end:
                return True
        return False

    for beat in plan.get("beats", []):
        try:
            start, end = float(beat.get("start")), float(beat.get("end"))
        except (TypeError, ValueError):
            continue
        if not any(cue_starts_in_interval(cue, start, end) for cue in cues):
            add_issue("BEAT_CUE_MISSING", f"no runtime cue covers beat {start:.3f}-{end:.3f}s")

    if "repeat_rejected" in tags:
        events = [item for item in telemetry.get("semantic_events", []) if isinstance(item, dict)]
        event_by_beat = {str(item.get("beat_id", "")): item for item in events if item.get("beat_id")}
        for beat in plan.get("beats", []):
            beat_id = str(beat.get("beat_id", ""))
            event = event_by_beat.get(beat_id)
            if event is None:
                add_issue("NOVICE_EVENT_MISSING", f"beat {beat_id!r} has no runtime cause-result-settle event")
                continue
            try:
                event_start = float(event.get("start"))
                event_end = float(event.get("end"))
                settle_seconds = float(event.get("settle_seconds"))
                planned_start = float(beat.get("start"))
                planned_end = float(beat.get("end"))
                planned_settle = float(beat.get("min_settle_seconds"))
                action_count = int(event.get("action_count"))
            except (TypeError, ValueError):
                add_issue("NOVICE_EVENT_TIMING", f"beat {beat_id!r} has invalid runtime novice-event timing")
                continue
            if event_start < planned_start - 0.10 or event_end > planned_end + 0.10:
                add_issue("NOVICE_EVENT_DRIFT", f"beat {beat_id!r} runtime event leaves its planned narration window", time=event_start)
            if settle_seconds + 1e-6 < planned_settle:
                add_issue("NOVICE_SETTLE_TOO_SHORT", f"beat {beat_id!r} settles for {settle_seconds:.2f}s; require {planned_settle:.2f}s", time=event_end)
            if action_count > 2:
                add_issue("NOVICE_ACTION_OVERLOAD", f"beat {beat_id!r} asks the novice to track {action_count} simultaneous actions", time=event_start)
            causes = list(map(str, event.get("cause_object_ids", [])))
            results = list(map(str, event.get("result_object_ids", [])))
            if not causes or not results or set(causes) & set(results):
                add_issue("NOVICE_CAUSE_RESULT", f"beat {beat_id!r} must expose distinct cause and result objects", time=event_end)
            if list(map(str, event.get("concepts_introduced", []))) != list(map(str, beat.get("concepts_introduced", []))):
                add_issue("NOVICE_CONCEPT_DRIFT", f"beat {beat_id!r} runtime concepts differ from the plan", time=event_end)
            if event.get("evidence_mode") != beat.get("evidence_mode"):
                add_issue("NOVICE_EVIDENCE_MODE_DRIFT", f"beat {beat_id!r} runtime evidence mode differs from the plan", time=event_end)
            nearby = [snap for snap in snapshots if abs(float(snap.get("time", -99)) - event_end) <= 0.50]
            visible_ids = {
                str(obj.get("id"))
                for snap in nearby
                for obj in snap.get("objects", [])
                if isinstance(obj, dict) and float(obj.get("opacity", 1.0)) > 0.05
            }
            missing_evidence = sorted((set(causes) | set(results)) - visible_ids)
            if missing_evidence:
                add_issue("NOVICE_EVIDENCE_NOT_VISIBLE", f"beat {beat_id!r} checkpoint does not visibly contain: {', '.join(missing_evidence)}", time=event_end, objects=missing_evidence)

        for snapshot in snapshots:
            try:
                atom_time = float(snapshot.get("time"))
            except (TypeError, ValueError):
                continue
            atoms = [item for item in snapshot.get("layout_atoms", []) if isinstance(item, dict) and float(item.get("opacity", 1.0)) > 0.05]
            for index, left in enumerate(atoms):
                for right in atoms[index + 1 :]:
                    if left.get("parent_object_id") == right.get("parent_object_id") and left.get("kind") == right.get("kind") == "formula_fragment":
                        overlap = bbox_overlap_area(left.get("bbox", []), right.get("bbox", []))
                        if overlap > 0.00001:
                            add_issue("FORMULA_ATOM_COLLISION", f"independently positioned formula atoms overlap by {overlap:.5f}", time=atom_time, objects=[str(left.get("atom_id")), str(right.get("atom_id"))])
                    elif left.get("kind") in {"solid", "formula_fragment"} and right.get("kind") in {"solid", "formula_fragment"}:
                        overlap = bbox_overlap_area(left.get("bbox", []), right.get("bbox", []))
                        if overlap > 0.00001:
                            add_issue("LAYOUT_ATOM_COLLISION", f"independent visual atoms overlap by {overlap:.5f}", time=atom_time, objects=[str(left.get("atom_id")), str(right.get("atom_id"))])

    required_formula_cues = {
        str(item.get("cue_id")) for item in plan.get("formula_choreography", []) if isinstance(item, dict) and item.get("cue_id")
    }
    missing_formula_cues = sorted(required_formula_cues - cue_ids)
    if missing_formula_cues:
        add_issue("FORMULA_CUE_MISSING", f"formula choreography cues missing from telemetry: {', '.join(missing_formula_cues)}")

    if "TIME-002" in active_rule_ids:
        cue_map = {str(item.get("cue_id")): item for item in cues if isinstance(item, dict)}
        for lock in plan.get("clause_locks", []):
            cue_id = str(lock.get("cue_id", ""))
            object_id = str(lock.get("object_id", ""))
            cue = cue_map.get(cue_id)
            if cue is None:
                add_issue("CLAUSE_LOCK_MISSING", f"clause lock {cue_id!r} has no runtime cue", objects=[object_id] if object_id else None)
                continue
            if str(cue.get("object_id", "")) != object_id:
                add_issue("CLAUSE_LOCK_OBJECT", f"clause lock {cue_id!r} targets a different runtime object", objects=[object_id])
            try:
                planned_start = float(lock.get("spoken_start"))
                spoken_start = float(cue.get("spoken_start"))
                visual_start = float(cue.get("visual_start"))
            except (TypeError, ValueError):
                add_issue("CLAUSE_LOCK_TIMING", f"clause lock {cue_id!r} has invalid timing", objects=[object_id])
                continue
            if abs(spoken_start - planned_start) > 0.08:
                add_issue("CLAUSE_LOCK_DRIFT", f"runtime spoken start drifts from clause lock by {abs(spoken_start - planned_start):.3f}s", time=spoken_start, objects=[object_id])
            if abs(visual_start - spoken_start) > 0.25:
                add_issue("CLAUSE_VISUAL_DRIFT", f"major concept action is {abs(visual_start - spoken_start):.3f}s away from its spoken clause", time=visual_start, objects=[object_id])

    if plan.get("timing_contract_version") == "word_anchor_v1":
        planned_anchors = {
            str(item.get("anchor_id")): item
            for item in plan.get("word_anchors", [])
            if isinstance(item, dict) and item.get("anchor_id")
        }
        runtime_anchors = {
            str(item.get("anchor_id")): item
            for item in telemetry.get("word_anchor_events", [])
            if isinstance(item, dict) and item.get("anchor_id")
        }
        runtime_emphasis = {
            str(item.get("cue_id")): item
            for item in telemetry.get("emphasis_events", [])
            if isinstance(item, dict) and item.get("cue_id")
        }
        runtime_handoffs = {
            str(item.get("handoff_id")): item
            for item in telemetry.get("formula_handoffs", [])
            if isinstance(item, dict) and item.get("handoff_id")
        }
        for anchor_id, planned in planned_anchors.items():
            event = runtime_anchors.get(anchor_id)
            if event is None:
                add_issue("WORD_ANCHOR_MISSING", f"selected word anchor {anchor_id!r} has no runtime visual action")
                continue
            try:
                planned_time = float(planned.get("local_start"))
                declared_time = float(event.get("planned_time"))
                actual_time = float(event.get("actual_time"))
            except (TypeError, ValueError):
                add_issue("WORD_ANCHOR_TIMING", f"word anchor {anchor_id!r} has invalid runtime timing")
                continue
            if abs(declared_time - planned_time) > 0.002:
                add_issue("WORD_ANCHOR_CONTRACT_DRIFT", f"runtime word anchor {anchor_id!r} changed its selected source timestamp", time=actual_time)
            if abs(actual_time - planned_time) > 0.08:
                add_issue("WORD_ANCHOR_VISUAL_DRIFT", f"visual action for {anchor_id!r} is {abs(actual_time - planned_time):.3f}s away from the selected word", time=actual_time)
            planned_target = str(planned.get("target_id", ""))
            planned_evidence_type = str(planned.get("evidence_type", ""))
            planned_evidence_id = str(planned.get("evidence_id", ""))
            if str(event.get("target_id", "")) != planned_target:
                add_issue("WORD_ANCHOR_TARGET_DRIFT", f"runtime word anchor {anchor_id!r} targets a different visible object", time=actual_time, objects=[planned_target] if planned_target else None)
            if str(event.get("evidence_type", "")) != planned_evidence_type or str(event.get("evidence_id", "")) != planned_evidence_id:
                add_issue("WORD_ANCHOR_EVIDENCE_DRIFT", f"runtime word anchor {anchor_id!r} changed its evidence contract", time=actual_time, objects=[planned_target] if planned_target else None)
            if planned_evidence_type == "emphasis_event":
                evidence = runtime_emphasis.get(planned_evidence_id)
                if evidence is None:
                    add_issue("WORD_ANCHOR_EVIDENCE_MISSING", f"word anchor {anchor_id!r} has no matching emphasis event", time=planned_time, objects=[planned_target] if planned_target else None)
                else:
                    try:
                        evidence_time = float(evidence.get("start_time"))
                    except (TypeError, ValueError):
                        evidence_time = float("inf")
                    if str(evidence.get("target_id", "")) != planned_target:
                        add_issue("WORD_ANCHOR_EVIDENCE_TARGET", f"emphasis evidence for {anchor_id!r} targets the wrong formula part", time=planned_time, objects=[planned_target] if planned_target else None)
                    if abs(evidence_time - planned_time) > 0.08:
                        add_issue("WORD_ANCHOR_EVIDENCE_TIMING", f"emphasis evidence for {anchor_id!r} is not synchronized to its selected word", time=planned_time, objects=[planned_target] if planned_target else None)
            elif planned_evidence_type == "formula_handoff":
                evidence = runtime_handoffs.get(planned_evidence_id)
                if evidence is None:
                    add_issue("WORD_ANCHOR_EVIDENCE_MISSING", f"word anchor {anchor_id!r} has no matching formula handoff", time=planned_time, objects=[planned_target] if planned_target else None)
                else:
                    try:
                        evidence_time = float(evidence.get("start"))
                    except (TypeError, ValueError):
                        evidence_time = float("inf")
                    if abs(evidence_time - planned_time) > 0.08:
                        add_issue("WORD_ANCHOR_EVIDENCE_TIMING", f"formula handoff for {anchor_id!r} is not synchronized to its selected word", time=planned_time, objects=[planned_target] if planned_target else None)
        unexpected = sorted(set(runtime_anchors) - set(planned_anchors))
        if unexpected:
            add_issue("WORD_ANCHOR_UNPLANNED", "runtime exports unplanned word anchors: " + ", ".join(unexpected))

    if "VIS-003" in active_rule_ids:
        planned_relations = {
            str(item.get("relation_id")): item
            for item in plan.get("region_relations", [])
            if isinstance(item, dict) and item.get("relation_id")
        }
        runtime_relations = {
            str(item.get("relation_id")): item
            for item in telemetry.get("relation_encodings", [])
            if isinstance(item, dict) and item.get("relation_id")
        }
        for relation_id, relation in planned_relations.items():
            runtime = runtime_relations.get(relation_id)
            if runtime is None:
                add_issue("RELATION_ENCODING_MISSING", f"region relation {relation_id!r} has no runtime encoding")
                continue
            if runtime.get("method") != relation.get("visual_encoding"):
                add_issue("RELATION_ENCODING_DRIFT", f"region relation {relation_id!r} uses a different runtime method")
            try:
                length = float(runtime.get("path_length_normalized", 0.0))
            except (TypeError, ValueError):
                length = 1.0
            if runtime.get("crosses_protected_region") is True:
                add_issue("CONNECTOR_CROSSES_PROTECTED_REGION", f"relation {relation_id!r} crosses an active protected region")
            if runtime.get("method") == "local_connector" and length > 0.28:
                add_issue("CONNECTOR_TOO_LONG", f"relation {relation_id!r} connector length {length:.3f} exceeds 0.28 frame units")

    if "FORM-003" in active_rule_ids:
        formula_rows = [item for item in telemetry.get("formula_rows", []) if isinstance(item, dict)]
        required_formula_objects = {
            str(item.get("object_id"))
            for item in plan.get("formula_choreography", [])
            if isinstance(item, dict) and item.get("object_id")
        }
        audited_formula_objects = {str(item.get("object_id")) for item in formula_rows if item.get("object_id")}
        for object_id in sorted(required_formula_objects - audited_formula_objects):
            add_issue("FORMULA_ROW_AUDIT_MISSING", "formula object has no runtime row-integrity audit", objects=[object_id])
        anchors_by_object: dict[str, list[float]] = {}
        for row in formula_rows:
            object_id = str(row.get("object_id", ""))
            row_id = str(row.get("row_id", ""))
            if row.get("typesetting_mode") != "single_expression":
                add_issue("FORMULA_FRAGMENTED_TYPESETTING", "formula row is not rendered as one expression", objects=[object_id, row_id])
            try:
                anchors_by_object.setdefault(object_id, []).append(float(row.get("anchor_x_normalized")))
            except (TypeError, ValueError):
                add_issue("FORMULA_ANCHOR_MISSING", "formula row lacks a numeric alignment anchor", objects=[object_id, row_id])
        for object_id, anchors in anchors_by_object.items():
            if len(anchors) > 1 and max(anchors) - min(anchors) > 0.012:
                add_issue("FORMULA_ANCHOR_DRIFT", f"equation anchors drift by {max(anchors) - min(anchors):.4f}", objects=[object_id])
        emphasis_map = {
            str(item.get("cue_id")): item
            for item in telemetry.get("emphasis_checks", [])
            if isinstance(item, dict) and item.get("cue_id")
        }
        for choreography in plan.get("formula_choreography", []):
            cue_id = str(choreography.get("cue_id", ""))
            check = emphasis_map.get(cue_id)
            object_id = str(choreography.get("object_id", ""))
            if check is None:
                add_issue("EMPHASIS_AUDIT_MISSING", f"formula cue {cue_id!r} has no runtime geometry audit", objects=[object_id])
                continue
            if check.get("mode") != choreography.get("emphasis_mode"):
                add_issue("EMPHASIS_MODE_DRIFT", f"formula cue {cue_id!r} uses an undeclared emphasis mode", objects=[object_id])
            before, after = check.get("before_bbox"), check.get("after_bbox")
            if not isinstance(before, list) or not isinstance(after, list) or len(before) != 4 or len(after) != 4:
                add_issue("EMPHASIS_GEOMETRY_MISSING", f"formula cue {cue_id!r} lacks before/after geometry", objects=[object_id])
                continue
            drift = max(abs(float(left) - float(right)) for left, right in zip(before, after))
            if drift > 0.003:
                add_issue("EMPHASIS_GEOMETRY_DRIFT", f"formula cue {cue_id!r} leaves bbox drift {drift:.4f}", objects=[object_id])
        if "FORM-004" in active_rule_ids:
            event_map = {
                str(item.get("cue_id")): item
                for item in telemetry.get("emphasis_events", [])
                if isinstance(item, dict) and item.get("cue_id")
            }
            for choreography in plan.get("formula_choreography", []):
                cue_id = str(choreography.get("cue_id", ""))
                object_id = str(choreography.get("object_id", ""))
                event = event_map.get(cue_id)
                if event is None:
                    add_issue("EMPHASIS_TEMPORAL_AUDIT_MISSING", f"formula cue {cue_id!r} has no temporal emphasis evidence", objects=[object_id])
                    continue
                try:
                    total = float(event.get("total_seconds", 0.0))
                    hold = float(event.get("hold_seconds", 0.0))
                except (TypeError, ValueError):
                    total, hold = 0.0, 0.0
                if total < 0.65 or hold < 0.12:
                    add_issue("EMPHASIS_TOO_FAST", f"formula cue {cue_id!r} lacks a readable onset/hold/recovery profile", objects=[object_id])
                if bool(event.get("box_trace")):
                    add_issue("EMPHASIS_BOX_TRACE", f"formula cue {cue_id!r} uses a traced bounding box", objects=[object_id])
                if event.get("mode") == "scale_then_restore" and not bool(event.get("restored")):
                    add_issue("EMPHASIS_NOT_RESTORED", f"formula cue {cue_id!r} does not certify exact rest restoration", objects=[object_id])
                if event.get("mode") == "scale_then_restore" and event.get("target_scope") not in {"whole_expression", "formula_token"}:
                    add_issue("EMPHASIS_SCOPE_UNDECLARED", f"formula cue {cue_id!r} has no stable whole-expression or formula-token scope", objects=[object_id])
                if event.get("mode") == "scale_then_restore" and event.get("target_scope") == "formula_token" and not bool(event.get("proxy_layer")):
                    add_issue("EMPHASIS_TOKEN_WITHOUT_PROXY", f"formula cue {cue_id!r} scales a live formula token instead of an isolated proxy layer", objects=[object_id])
                for timing_key in ("start_time", "peak_time", "hold_end_time", "end_time"):
                    if not isinstance(event.get(timing_key), (int, float)):
                        add_issue("EMPHASIS_FRAME_TIMING_MISSING", f"formula cue {cue_id!r} lacks absolute {timing_key} evidence", objects=[object_id])
                        break

    if "STAGE-005" in active_rule_ids:
        runtime_motion = {
            str(item.get("transition_id")): item
            for item in telemetry.get("motion_transitions", [])
            if isinstance(item, dict) and item.get("transition_id")
        }
        allowed_profiles = {"sine_in_out", "matched_sine_halves", "smootherstep", "continuous_transform"}
        for transition in plan.get("stage_transitions", []):
            transition_id = f"{transition.get('from_state')}->{transition.get('to_state')}"
            event = runtime_motion.get(transition_id)
            if event is None:
                add_issue("STAGE_MOTION_AUDIT_MISSING", f"stage transition {transition_id!r} has no motion evidence")
                continue
            try:
                motion_duration = float(event.get("duration", 0.0))
                midpoint = float(event.get("midpoint_time"))
            except (TypeError, ValueError):
                motion_duration, midpoint = 0.0, -1.0
            if motion_duration < 0.65:
                add_issue("STAGE_MOTION_TOO_FAST", f"stage transition {transition_id!r} is too short to read")
            if event.get("rate_profile") not in allowed_profiles:
                add_issue("STAGE_MOTION_EASING", f"stage transition {transition_id!r} uses an unapproved stop-start easing profile")
            if not bool(event.get("continuous_path")):
                add_issue("STAGE_MOTION_DISCONTINUOUS", f"stage transition {transition_id!r} is not one continuous path")
            if event.get("rate_profile") == "matched_sine_halves" and not bool(event.get("matched_midpoint_velocity")):
                add_issue("STAGE_MOTION_MIDPOINT_JERK", f"stage transition {transition_id!r} does not match midpoint velocity")
            try:
                start, end = float(transition.get("start")), float(transition.get("end"))
            except (TypeError, ValueError):
                start, end = 0.0, 0.0
            if not (start <= midpoint <= end):
                add_issue("STAGE_MOTION_MIDPOINT", f"stage transition {transition_id!r} reports a midpoint outside its plan window")
    for handoff in plan.get("stage_transitions", []):
        if isinstance(handoff, dict) and "A" in handoff.get("change_vector", []):
            pair = (str(handoff.get("from_focus_region", "")), str(handoff.get("to_focus_region", "")))
            if pair not in handoff_pairs:
                add_issue("ATTENTION_HANDOFF_MISSING", f"planned attention handoff {pair[0]} -> {pair[1]} is absent from runtime cues")

    invariant_checks = {
        str(item.get("invariant_id")): item
        for item in telemetry.get("math_invariant_checks", [])
        if isinstance(item, dict) and item.get("invariant_id")
    }
    if profile.get("autopilot_contract_version"):
        for invariant in plan.get("math_object_invariants", []):
            invariant_id = str(invariant.get("invariant_id", ""))
            object_id = str(invariant.get("object_id", ""))
            check = invariant_checks.get(invariant_id)
            if check is None:
                add_issue(
                    "MATH_INVARIANT_MISSING",
                    f"math-object invariant {invariant_id!r} has no runtime evidence",
                    objects=[object_id] if object_id else None,
                )
                continue
            if str(check.get("object_id", "")) != object_id:
                add_issue("MATH_INVARIANT_OBJECT", f"math-object invariant {invariant_id!r} measures the wrong object", objects=[object_id])
            if str(check.get("evidence_type", "")) != str(invariant.get("evidence_type", "")):
                add_issue("MATH_INVARIANT_EVIDENCE", f"math-object invariant {invariant_id!r} uses the wrong evidence type", objects=[object_id])
            samples = check.get("samples", [])
            if not isinstance(samples, list) or not samples:
                add_issue("MATH_INVARIANT_SAMPLES", f"math-object invariant {invariant_id!r} has no runtime samples", objects=[object_id])
            if check.get("passed") is not True:
                add_issue("MATH_INVARIANT_FAILED", f"math-object invariant {invariant_id!r} failed its declared relation", objects=[object_id])
            if len(str(check.get("observed_relation", "")).strip()) < 10:
                add_issue("MATH_INVARIANT_OBSERVATION", f"math-object invariant {invariant_id!r} lacks an observed relation", objects=[object_id])

    gate_coverage = {
        "layout": {
            "snapshots": len(snapshots),
            "layout_atoms": sum(
                len(item.get("layout_atoms", [])) for item in snapshots if isinstance(item, dict)
            ),
            "passed": not any(
                issue["code"] in {
                    "OUT_OF_FRAME", "SUBTITLE_INTRUSION", "REGION_OVERFLOW", "CONTAINER_OVERFLOW",
                    "UNAPPROVED_OVERLAP", "CRAMPED_SPACING", "FORMULA_ATOM_COLLISION", "LAYOUT_ATOM_COLLISION",
                }
                for issue in issues
            ),
        },
        "math_object": {
            "planned_invariants": len(plan.get("math_object_invariants", [])),
            "runtime_invariants": len(invariant_checks),
            "typed_objects": len(plan.get("math_objects", [])),
            "visual_bindings": len(telemetry.get("math_object_bindings", [])),
            "display_mappings": len(telemetry.get("display_mapping_checks", [])),
            "passed": not any(
                str(issue["code"]).startswith(("MATH_INVARIANT", "MATH_OBJECT", "MATH_DRIVER", "MATH_STATE", "DISPLAY_"))
                or issue["code"] == "COORDINATE_DRIFT"
                for issue in issues
            ),
        },
        "timing_attention": {
            "cues": len(cues),
            "stage_transitions": len(plan.get("stage_transitions", [])),
            "passed": not any(
                issue["code"].startswith(("CUE_", "VISUAL_", "CLAUSE_", "STAGE_MOTION", "ATTENTION_", "STALE_"))
                for issue in issues
            ),
        },
        "novice_causality": {
            "planned_beats": len(plan.get("beats", [])),
            "semantic_events": len(telemetry.get("semantic_events", [])),
            "passed": not any(issue["code"].startswith("NOVICE_") for issue in issues),
        },
    }

    report: dict[str, Any] = {
        "schema": "lecture-animation-authoring-qc-report-v2",
        "valid": not issues,
        "profile_hash": profile.get("profile_hash"),
        "plan_hash": object_hash(plan),
        "telemetry_hash": object_hash(telemetry),
        "scene_slug": expected_slug,
        "capture_source": capture,
        "gate_coverage": gate_coverage,
        "issues": issues,
        "stats": {
            "snapshots": len(snapshots),
            "unique_objects": len(object_ids_seen),
            "cues": len(cues),
            "issues": len(issues),
        },
    }
    report["report_hash"] = object_hash(report)
    return report


def validate_authoring_qc_report_hash(report: dict[str, Any]) -> bool:
    expected = report.get("report_hash")
    payload = dict(report)
    payload.pop("report_hash", None)
    return bool(expected) and expected == object_hash(payload)


def validate_layout_audit_data(layout: dict[str, Any], scene_slug: str) -> list[str]:
    errors: list[str] = []
    if layout.get("schema") != "lecture-animation-layout-audit-v2":
        errors.append("layout_audit schema must be lecture-animation-layout-audit-v2")
    if layout.get("scene_slug") != scene_slug:
        errors.append("layout_audit scene_slug does not match the review scene")
    if layout.get("capture_source") not in {"runtime_export", "frame_analysis"}:
        errors.append("layout_audit must come from runtime_export or frame_analysis")
    try:
        snapshot_count = int(layout.get("snapshot_count", 0))
        issue_count = int(layout.get("issue_count", -1))
    except (TypeError, ValueError):
        snapshot_count, issue_count = 0, -1
    if snapshot_count < 3:
        errors.append("layout_audit requires at least three inspected snapshots")
    if issue_count != len(layout.get("issues", [])):
        errors.append("layout_audit issue_count does not match its issue list")
    if issue_count != 0 or layout.get("status") != "pass":
        errors.append("layout_audit contains unresolved layout failures")
    return errors


def artifact_snapshot(path: Path, repo_root: Path) -> dict[str, Any]:
    if not path.exists():
        raise PipelineError(f"artifact does not exist: {path}")
    if path.is_file():
        data = path.read_bytes()
        return {
            "path": relative_or_absolute(path, repo_root),
            "kind": "file",
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "file_count": 1,
            "mtime_ns": path.stat().st_mtime_ns,
        }
    digest = hashlib.sha256()
    total_size = 0
    file_count = 0
    latest_mtime = 0
    for child in sorted(item for item in path.rglob("*") if item.is_file() and clean_path(item)):
        relative = child.relative_to(path).as_posix()
        data = child.read_bytes()
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(data).digest())
        total_size += len(data)
        file_count += 1
        latest_mtime = max(latest_mtime, child.stat().st_mtime_ns)
    return {
        "path": relative_or_absolute(path, repo_root),
        "kind": "directory",
        "sha256": digest.hexdigest(),
        "size": total_size,
        "file_count": file_count,
        "mtime_ns": latest_mtime,
    }


def validate_bound_frame_evidence(
    evidence: dict[str, Any], manifest: dict[str, Any], repo_root: Path, prefix: str
) -> list[str]:
    """Verify that a claimed decoded frame is a real, hash-bound manifest artifact."""
    errors: list[str] = []
    artifacts = manifest.get("artifacts", {})
    artifact_key = str(evidence.get("artifact_key", ""))
    source_artifact_key = str(evidence.get("source_artifact_key", ""))
    artifact = artifacts.get(artifact_key, {})
    source_artifact = artifacts.get(source_artifact_key, {})
    if artifact_key not in artifacts:
        errors.append(f"{prefix}: evidence artifact is absent from the manifest")
        return errors
    if source_artifact_key not in artifacts:
        errors.append(f"{prefix}: evidence source artifact is absent from the manifest")
    elif evidence.get("source_sha256") != source_artifact.get("sha256"):
        errors.append(f"{prefix}: evidence source_sha256 is stale")
    frame_raw = str(evidence.get("frame_path", "")).strip()
    frame_sha = str(evidence.get("frame_sha256", "")).strip()
    if not frame_raw or not re.fullmatch(r"[0-9a-f]{64}", frame_sha):
        errors.append(f"{prefix}: frame_path and frame_sha256 are required")
        return errors
    frame_path = resolve_stored_path(frame_raw, repo_root).resolve()
    artifact_path = resolve_stored_path(str(artifact.get("path", "")), repo_root).resolve()
    if not frame_path.is_file():
        errors.append(f"{prefix}: evidence frame does not exist: {frame_raw}")
        return errors
    try:
        if artifact.get("kind") == "file":
            if frame_path != artifact_path:
                raise ValueError
        else:
            frame_path.relative_to(artifact_path)
    except ValueError:
        errors.append(f"{prefix}: evidence frame is outside the declared artifact")
    actual_sha = hashlib.sha256(frame_path.read_bytes()).hexdigest()
    if actual_sha != frame_sha:
        errors.append(f"{prefix}: evidence frame_sha256 does not match the file")
    return errors


SCREEN_TEXT_CONSTRUCTORS = {
    "Text",
    "MarkupText",
    "Tex",
    "MathTex",
    "DecimalNumber",
    "Integer",
    # Project wrappers are still screen-text constructors. Omitting them makes
    # the exact text gate report an empty inventory for real scene packages.
    "math_tex",
    "role_formula",
    "label",
}


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _literal_payload(node: ast.AST) -> str:
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return "<dynamic>"
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, complex, bool)) or value is None:
        return repr(value)
    return "<dynamic>"


def scan_screen_text_inventory(source_dir: Path, repo_root: Path) -> dict[str, Any]:
    if not source_dir.is_dir():
        raise PipelineError(f"screen-text source must be a directory: {source_dir}")
    entries: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    for path in sorted(source_dir.rglob("*.py")):
        if not clean_path(path):
            continue
        try:
            tree = ast.parse(read_text(path), filename=str(path))
        except SyntaxError as exc:
            parse_errors.append(f"{relative_or_absolute(path, repo_root)}:{exc.lineno}: {exc.msg}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            constructor = _call_name(node)
            if constructor not in SCREEN_TEXT_CONSTRUCTORS:
                continue
            payloads = [_literal_payload(arg) for arg in node.args]
            entries.append(
                {
                    "constructor": constructor,
                    "payloads": payloads,
                    "file": relative_or_absolute(path, repo_root),
                    "line": int(getattr(node, "lineno", 0)),
                }
            )
    signature = Counter(
        (entry["constructor"], tuple(entry["payloads"]))
        for entry in entries
    )
    return {
        "entries": entries,
        "constructor_counts": dict(sorted(Counter(entry["constructor"] for entry in entries).items())),
        "signature": [
            {"constructor": constructor, "payloads": list(payloads), "count": count}
            for (constructor, payloads), count in sorted(signature.items())
        ],
        "static_character_count": sum(
            len(payload)
            for entry in entries
            for payload in entry["payloads"]
            if payload != "<dynamic>"
        ),
        "dynamic_payload_count": sum(
            payload == "<dynamic>"
            for entry in entries
            for payload in entry["payloads"]
        ),
        "parse_errors": parse_errors,
    }


def command_freeze_text_inventory(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    source_dir = resolve_stored_path(args.source, repo_root).resolve()
    inventory = scan_screen_text_inventory(source_dir, repo_root)
    if inventory["parse_errors"]:
        raise PipelineError("cannot freeze text inventory with parse errors: " + " | ".join(inventory["parse_errors"]))
    baseline: dict[str, Any] = {
        "schema": "lecture-animation-screen-text-baseline-v1",
        "scene_slug": args.scene_slug,
        "baseline_label": args.baseline_label,
        "source_path": relative_or_absolute(source_dir, repo_root),
        "source_sha256": artifact_snapshot(source_dir, repo_root)["sha256"],
        "inventory": inventory,
    }
    baseline["baseline_hash"] = object_hash(baseline)
    write_json(Path(args.output), baseline)
    print(json.dumps({"valid": True, "output": args.output, "baseline_hash": baseline["baseline_hash"], "constructor_counts": inventory["constructor_counts"]}, ensure_ascii=False, indent=2))
    return 0


def command_verify_text_inventory(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    source_dir = resolve_stored_path(args.source, repo_root).resolve()
    baseline_path = resolve_stored_path(args.baseline, repo_root).resolve()
    baseline = load_json(baseline_path)
    baseline_payload = dict(baseline)
    expected_hash = baseline_payload.pop("baseline_hash", None)
    errors: list[str] = []
    if baseline.get("schema") != "lecture-animation-screen-text-baseline-v1":
        errors.append("baseline schema must be lecture-animation-screen-text-baseline-v1")
    if not expected_hash or expected_hash != object_hash(baseline_payload):
        errors.append("baseline_hash is invalid")
    if baseline.get("scene_slug") != args.scene_slug:
        errors.append("baseline scene_slug does not match candidate")
    candidate = scan_screen_text_inventory(source_dir, repo_root)
    if candidate["parse_errors"]:
        errors.extend(candidate["parse_errors"])
    baseline_inventory = baseline.get("inventory", {})
    for field in ("constructor_counts", "signature", "static_character_count", "dynamic_payload_count"):
        if candidate.get(field) != baseline_inventory.get(field):
            errors.append(f"screen text inventory changed: {field}")
    report: dict[str, Any] = {
        "schema": "lecture-animation-screen-text-audit-v1",
        "valid": not errors,
        "scene_slug": args.scene_slug,
        "mode": "exact",
        "baseline_path": relative_or_absolute(baseline_path, repo_root),
        "baseline_hash": expected_hash,
        "candidate_source_path": relative_or_absolute(source_dir, repo_root),
        "candidate_source_sha256": artifact_snapshot(source_dir, repo_root)["sha256"],
        "baseline_inventory": {
            "constructor_counts": baseline_inventory.get("constructor_counts", {}),
            "static_character_count": baseline_inventory.get("static_character_count", 0),
            "dynamic_payload_count": baseline_inventory.get("dynamic_payload_count", 0),
        },
        "candidate_inventory": {
            "constructor_counts": candidate.get("constructor_counts", {}),
            "static_character_count": candidate.get("static_character_count", 0),
            "dynamic_payload_count": candidate.get("dynamic_payload_count", 0),
        },
        "errors": errors,
    }
    report["report_hash"] = object_hash(report)
    write_json(Path(args.output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 2


def verify_manifest_data(manifest: dict[str, Any], repo_root: Path) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema") != "lecture-animation-review-manifest-v2":
        errors.append("manifest schema must be lecture-animation-review-manifest-v2")
    payload = dict(manifest)
    expected_hash = payload.pop("manifest_hash", None)
    if not expected_hash or expected_hash != object_hash(payload):
        errors.append("manifest_hash is invalid")
    artifacts = manifest.get("artifacts", {})
    required_artifacts = set(REQUIRED_ARTIFACTS)
    profile_for_requirements: dict[str, Any] | None = None
    if "profile" in artifacts:
        try:
            profile_for_requirements = load_json(
                resolve_stored_path(str(artifacts["profile"].get("path", "")), repo_root)
            )
        except PipelineError:
            profile_for_requirements = None
    if int((profile_for_requirements or {}).get("autopilot_contract_version") or 0) >= 2:
        required_artifacts.update(PROGRESSIVE_PLANNING_ARTIFACTS)
    try:
        episode_for_requirements = resolve_stored_path(str(manifest.get("episode", "")), repo_root)
        if (episode_for_requirements / "progressive_production.json").exists():
            required_artifacts.update({"scene_production", "scene_registry", "script", "word_srt", "word_alignment", "asr_transcript", "narration_qc"})
    except PipelineError:
        pass
    if "scene_production" in artifacts or "scene_registry" in artifacts:
        required_artifacts.update({"scene_production", "scene_registry", "script", "word_srt", "word_alignment", "asr_transcript", "narration_qc"})
    missing = sorted(required_artifacts - set(artifacts))
    if missing:
        errors.append(f"manifest missing required artifacts: {', '.join(missing)}")
    for key, expected in artifacts.items():
        try:
            current = artifact_snapshot(resolve_stored_path(str(expected.get("path", "")), repo_root), repo_root)
        except PipelineError as exc:
            errors.append(f"{key}: {exc}")
            continue
        for field in ("kind", "sha256", "size", "file_count"):
            if current.get(field) != expected.get(field):
                errors.append(f"{key}: stale artifact; {field} changed")
    if "profile" in artifacts and "plan" in artifacts:
        try:
            profile = load_json(resolve_stored_path(str(artifacts["profile"].get("path", "")), repo_root))
            plan = load_json(resolve_stored_path(str(artifacts["plan"].get("path", "")), repo_root))
            if not validate_profile_hash(profile):
                errors.append("profile semantic hash is invalid")
            if manifest.get("profile_hash") != profile.get("profile_hash"):
                errors.append("manifest profile_hash does not match profile artifact")
            if manifest.get("scene_slug") != profile.get("context", {}).get("scene_slug"):
                errors.append("manifest scene_slug does not match profile artifact")
            if profile.get("autopilot_contract_version"):
                if "live_policy" not in artifacts:
                    errors.append("autopilot manifest missing required artifact: live_policy")
                else:
                    policy = load_json(resolve_stored_path(str(artifacts["live_policy"].get("path", "")), repo_root))
                    episode_dir = resolve_stored_path(str(manifest.get("episode", "")), repo_root)
                    current_policy = compile_live_policy_data(episode_dir, profile)
                    if not validate_live_policy_hash(policy):
                        errors.append("live_policy hash is invalid")
                    if policy.get("policy_hash") != profile.get("live_policy_hash"):
                        errors.append("live_policy does not match profile live_policy_hash")
                    if policy.get("policy_hash") != current_policy.get("policy_hash"):
                        errors.append("live_policy is stale after human or accepted-agent feedback")
            if int(profile.get("autopilot_contract_version") or 0) >= 2:
                planning_keys = PROGRESSIVE_PLANNING_ARTIFACTS
                if planning_keys <= set(artifacts):
                    episode_dir = resolve_stored_path(str(manifest.get("episode", "")), repo_root)
                    spine = load_json(resolve_stored_path(str(artifacts["episode_spine"].get("path", "")), repo_root))
                    batch_plan = load_json(resolve_stored_path(str(artifacts["batch_plan"].get("path", "")), repo_root))
                    errors.extend(f"episode spine: {error}" for error in validate_episode_spine_data(spine, repo_root, episode_dir))
                    batch_scenes = [
                        str(item.get("scene_slug", ""))
                        for item in batch_plan.get("scenes", [])
                        if isinstance(item, dict)
                    ]
                    errors.extend(
                        f"batch plan: {error}"
                        for error in validate_batch_visual_plan_data(
                            batch_plan,
                            spine,
                            str(batch_plan.get("batch_id", "")),
                            batch_scenes,
                        )
                    )
                    errors.extend(f"planning chain: {error}" for error in validate_scene_planning_chain(plan, spine, batch_plan))
            errors.extend(f"plan: {error}" for error in validate_scene_plan_data(profile, plan))
            design_keys = {"design_challenge", "deliberation", "design_gate", "precedent_packet"}
            if design_keys <= set(artifacts):
                challenge = load_json(resolve_stored_path(str(artifacts["design_challenge"].get("path", "")), repo_root))
                deliberation = load_json(resolve_stored_path(str(artifacts["deliberation"].get("path", "")), repo_root))
                design_gate = load_json(resolve_stored_path(str(artifacts["design_gate"].get("path", "")), repo_root))
                precedent_packet = load_json(resolve_stored_path(str(artifacts["precedent_packet"].get("path", "")), repo_root))
                errors.extend(
                    f"design: {error}"
                    for error in validate_design_chain_data(
                        profile,
                        plan,
                        challenge,
                        deliberation,
                        design_gate,
                        precedent_packet,
                    )
                )
            if "telemetry" in artifacts and "authoring_qc" in artifacts:
                telemetry = load_json(resolve_stored_path(str(artifacts["telemetry"].get("path", "")), repo_root))
                stored_report = load_json(resolve_stored_path(str(artifacts["authoring_qc"].get("path", "")), repo_root))
                fresh_report = validate_authoring_qc_data(profile, plan, telemetry)
                if not validate_authoring_qc_report_hash(stored_report):
                    errors.append("authoring_qc report hash is invalid")
                if stored_report.get("report_hash") != fresh_report.get("report_hash"):
                    errors.append("authoring_qc report is stale or does not match telemetry")
                if not fresh_report.get("valid"):
                    codes = [str(item.get("code")) for item in fresh_report.get("issues", [])[:8]]
                    errors.append("authoring_qc failed: " + ", ".join(codes))
            if "scene_production" in artifacts and "scene_registry" in artifacts:
                scene_production = load_json(resolve_stored_path(str(artifacts["scene_production"].get("path", "")), repo_root))
                scene_registry = load_json(resolve_stored_path(str(artifacts["scene_registry"].get("path", "")), repo_root))
                scene_slug = str(manifest.get("scene_slug", ""))
                errors.extend(
                    f"scene production: {error}"
                    for error in validate_scene_production_data(scene_production, repo_root, scene_slug)
                )
                expected_registry = scene_registry_data(profile, plan, scene_production)
                if not validate_hashed_record(scene_registry, "registry_hash"):
                    errors.append("scene registry hash is invalid")
                if scene_registry.get("registry_hash") != expected_registry.get("registry_hash"):
                    errors.append("scene registry is stale for the current profile, plan, or scene media")
                exact_mapping = {
                    "script": "script",
                    "audio": "audio",
                    "srt": "reader_srt",
                    "word_srt": "word_srt",
                    "word_alignment": "word_alignment",
                    "timeline": "timeline_fragment",
                    "asr_transcript": "asr_transcript",
                    "narration_qc": "narration_qc",
                }
                for manifest_key, production_key in exact_mapping.items():
                    expected_sha = scene_production.get("artifacts", {}).get(production_key, {}).get("sha256")
                    actual_sha = artifacts.get(manifest_key, {}).get("sha256")
                    if expected_sha != actual_sha:
                        errors.append(f"{manifest_key} does not match the exact scene production contract")
                if "telemetry" in artifacts:
                    telemetry = load_json(resolve_stored_path(str(artifacts["telemetry"].get("path", "")), repo_root))
                    if telemetry.get("scene_registry_hash") != scene_registry.get("registry_hash"):
                        errors.append("runtime telemetry is not bound to the compiled scene registry")
            if "FORM-004" in {str(rule.get("rule_id")) for rule in profile.get("rules", [])}:
                frame_entry = artifacts.get("emphasis_frame_audit")
                if not isinstance(frame_entry, dict):
                    errors.append("FORM-004 requires an emphasis_frame_audit artifact")
                else:
                    frame_report = load_json(resolve_stored_path(str(frame_entry.get("path", "")), repo_root))
                    if frame_report.get("schema") != "lecture-animation-emphasis-frame-audit-v2":
                        errors.append("emphasis_frame_audit schema is invalid")
                    if not frame_report.get("valid"):
                        errors.append("emphasis_frame_audit contains failed intermediate frames")
            if profile.get("autopilot_contract_version") and "layout_audit" in artifacts:
                layout_report = load_json(resolve_stored_path(str(artifacts["layout_audit"].get("path", "")), repo_root))
                errors.extend(validate_layout_audit_data(layout_report, str(manifest.get("scene_slug", ""))))
        except PipelineError as exc:
            errors.append(f"profile/plan/authoring validation failed: {exc}")
    return errors


def verify_manifest_record_hash(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema") != "lecture-animation-review-manifest-v2":
        errors.append("manifest schema must be lecture-animation-review-manifest-v2")
    payload = dict(manifest)
    expected = payload.pop("manifest_hash", None)
    if not expected or expected != object_hash(payload):
        errors.append("manifest_hash is invalid")
    return errors


def event_rows(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path)


def canonical_review_attempt_rows(path: Path) -> list[dict[str, Any]]:
    """Read the canonical attempt log plus the one legacy split log, deduplicated."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in event_rows(path):
        key = str(row.get("verification_key") or row.get("attempt_id") or "")
        if key and key in seen:
            continue
        rows.append(row)
        if key:
            seen.add(key)
    for row in event_rows(path.with_name("review_audit.jsonl")):
        attempt_id = str(row.get("verification_key") or row.get("attempt_id", ""))
        if not attempt_id or attempt_id not in seen:
            rows.append(row)
            if attempt_id:
                seen.add(attempt_id)
    return rows


def validate_hashed_record(value: dict[str, Any], hash_field: str) -> bool:
    payload = dict(value)
    expected = payload.pop(hash_field, None)
    return bool(expected) and expected == object_hash(payload)


def hydrate_artifact_descriptor(value: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    if not isinstance(value, dict) or not str(value.get("path", "")).strip():
        raise PipelineError("artifact descriptor requires path")
    result = dict(value)
    path = resolve_stored_path(str(value["path"]), repo_root)
    snapshot = artifact_snapshot(path, repo_root)
    result.update({key: snapshot[key] for key in ("path", "kind", "sha256", "size", "file_count")})
    return result


def validate_artifact_descriptor(value: Any, repo_root: Path, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label} must be an artifact descriptor"]
    try:
        current = hydrate_artifact_descriptor(value, repo_root)
    except PipelineError as exc:
        return [f"{label}: {exc}"]
    errors: list[str] = []
    for field in ("kind", "sha256", "size", "file_count"):
        if value.get(field) != current.get(field):
            errors.append(f"{label} is stale: {field} changed")
    return errors


def normalize_spoken_text(text: str) -> str:
    spoken_lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", "".join(spoken_lines)).lower()


def audio_duration_seconds(path: Path) -> float:
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as handle:
                rate = handle.getframerate()
                if rate <= 0:
                    raise PipelineError(f"audio has invalid sample rate: {path}")
                return handle.getnframes() / float(rate)
        except (wave.Error, EOFError):
            pass
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise PipelineError(f"cannot measure audio duration: {path}: {proc.stderr.strip()}")
    try:
        duration = float(proc.stdout.strip())
    except ValueError as exc:
        raise PipelineError(f"ffprobe returned invalid audio duration for {path}") from exc
    if duration <= 0:
        raise PipelineError(f"audio duration must be positive: {path}")
    return duration


def srt_intervals(path: Path) -> list[tuple[float, float]]:
    def seconds(raw: str) -> float:
        hours, minutes, rest = raw.replace(",", ".").split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(rest)

    intervals: list[tuple[float, float]] = []
    for match in re.finditer(
        r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})",
        path.read_text(encoding="utf-8"),
    ):
        intervals.append((seconds(match.group(1)), seconds(match.group(2))))
    return intervals


def alignment_intervals(path: Path) -> list[tuple[float, float]]:
    data = load_json(path)
    candidates: Any = None
    for key in ("words", "aligned_tokens", "tokens", "segments"):
        if isinstance(data.get(key), list):
            candidates = data[key]
            break
    if not isinstance(candidates, list):
        return []
    intervals: list[tuple[float, float]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        start = item.get("start", item.get("start_seconds"))
        end = item.get("end", item.get("end_seconds"))
        try:
            intervals.append((float(start), float(end)))
        except (TypeError, ValueError):
            continue
    return intervals


def timeline_fragment_duration(path: Path) -> float:
    data = load_json(path)
    if isinstance(data.get("duration_seconds"), (int, float)):
        return float(data["duration_seconds"])
    ends = [
        float(item.get("end"))
        for item in data.get("segments", [])
        if isinstance(item, dict) and isinstance(item.get("end"), (int, float))
    ]
    if not ends:
        raise PipelineError("timeline fragment requires duration_seconds or numeric segment end times")
    return max(ends)


def narration_qc_data(
    repo_root: Path,
    scene_slug: str,
    episode_spine_path: Path,
    artifact_paths: dict[str, Path],
    review_draft: dict[str, Any],
) -> dict[str, Any]:
    spine = load_json(episode_spine_path)
    style = spine.get("narration_style_contract", {})
    result: dict[str, Any] = {
        "schema": "lecture-animation-scene-narration-qc-v2",
        "scene_slug": scene_slug,
        "episode_spine": artifact_snapshot(episode_spine_path, repo_root),
        "style_contract_hash": object_hash(style) if isinstance(style, dict) else None,
        "artifacts": {key: artifact_snapshot(path, repo_root) for key, path in artifact_paths.items()},
        "author_self_review": review_draft.get("author_self_review", {}),
        "audio_listening_review": review_draft.get("audio_listening_review", {}),
        "timeline_alignment_review": review_draft.get("timeline_alignment_review", {}),
    }
    audio_duration = audio_duration_seconds(artifact_paths["audio"])
    timeline_duration = timeline_fragment_duration(artifact_paths["timeline_fragment"])
    reader_intervals = srt_intervals(artifact_paths["reader_srt"])
    word_srt_intervals = srt_intervals(artifact_paths["word_srt"])
    word_intervals = alignment_intervals(artifact_paths["word_alignment"])
    script_text = artifact_paths["script"].read_text(encoding="utf-8")
    transcript_text = artifact_paths["asr_transcript"].read_text(encoding="utf-8")
    result["measured"] = {
        "audio_duration_seconds": round(audio_duration, 6),
        "timeline_duration_seconds": round(timeline_duration, 6),
        "reader_srt_end_seconds": round(max((end for _, end in reader_intervals), default=0.0), 6),
        "word_srt_end_seconds": round(max((end for _, end in word_srt_intervals), default=0.0), 6),
        "word_alignment_end_seconds": round(max((end for _, end in word_intervals), default=0.0), 6),
        "duration_delta_seconds": round(abs(audio_duration - timeline_duration), 6),
    }
    result["transcript_check"] = {
        "method": "exact_after_punctuation_and_whitespace_normalization",
        "script_normalized_sha256": hashlib.sha256(normalize_spoken_text(script_text).encode("utf-8")).hexdigest(),
        "transcript_normalized_sha256": hashlib.sha256(normalize_spoken_text(transcript_text).encode("utf-8")).hexdigest(),
        "exact_match": normalize_spoken_text(script_text) == normalize_spoken_text(transcript_text),
    }
    result["narration_qc_hash"] = object_hash(result)
    return result


def restore_sealed_artifact_mtime(
    current: dict[str, Any], sealed: Any
) -> dict[str, Any]:
    """Keep legacy QC hashes portable when only filesystem mtimes changed."""
    if not isinstance(sealed, dict):
        return current
    identity_fields = ("path", "kind", "sha256", "size", "file_count")
    if all(current.get(field) == sealed.get(field) for field in identity_fields):
        current = dict(current)
        current["mtime_ns"] = sealed.get("mtime_ns")
    return current


def validate_narration_qc_data(value: dict[str, Any], repo_root: Path, scene_slug: str) -> list[str]:
    errors: list[str] = []
    if value.get("schema") != "lecture-animation-scene-narration-qc-v2":
        return ["narration_qc schema must be lecture-animation-scene-narration-qc-v2"]
    if not validate_hashed_record(value, "narration_qc_hash"):
        errors.append("narration_qc hash is invalid")
    if value.get("scene_slug") != scene_slug:
        errors.append("narration_qc scene_slug does not match the production scene")
    spine_entry = value.get("episode_spine", {})
    errors.extend(validate_artifact_descriptor(spine_entry, repo_root, "narration_qc episode_spine"))
    try:
        spine = load_json(resolve_stored_path(str(spine_entry.get("path", "")), repo_root))
        errors.extend(validate_narration_style_contract(spine.get("narration_style_contract")))
        if value.get("style_contract_hash") != object_hash(spine.get("narration_style_contract", {})):
            errors.append("narration_qc style contract is stale")
    except PipelineError as exc:
        errors.append(str(exc))
    artifact_paths: dict[str, Path] = {}
    for key in ("script", "audio", "reader_srt", "word_srt", "word_alignment", "timeline_fragment", "asr_transcript"):
        descriptor = value.get("artifacts", {}).get(key)
        errors.extend(validate_artifact_descriptor(descriptor, repo_root, f"narration_qc {key}"))
        if isinstance(descriptor, dict) and descriptor.get("path"):
            try:
                artifact_paths[key] = resolve_stored_path(str(descriptor["path"]), repo_root)
            except PipelineError as exc:
                errors.append(str(exc))
    if len(artifact_paths) == 7:
        try:
            expected = narration_qc_data(
                repo_root,
                scene_slug,
                resolve_stored_path(str(spine_entry.get("path", "")), repo_root),
                artifact_paths,
                {
                    "author_self_review": value.get("author_self_review", {}),
                    "audio_listening_review": value.get("audio_listening_review", {}),
                    "timeline_alignment_review": value.get("timeline_alignment_review", {}),
                },
            )
            expected["episode_spine"] = restore_sealed_artifact_mtime(
                expected.get("episode_spine", {}), spine_entry
            )
            expected["artifacts"] = {
                key: restore_sealed_artifact_mtime(
                    descriptor, value.get("artifacts", {}).get(key)
                )
                for key, descriptor in expected.get("artifacts", {}).items()
            }
            expected.pop("narration_qc_hash", None)
            expected["narration_qc_hash"] = object_hash(expected)
            if expected.get("narration_qc_hash") != value.get("narration_qc_hash"):
                errors.append("narration_qc measurements or artifact bindings are stale")
        except (PipelineError, OSError, ValueError) as exc:
            errors.append(f"narration_qc cannot be recomputed: {exc}")
    measured = value.get("measured", {})
    if float(measured.get("duration_delta_seconds", 999.0)) > 0.25:
        errors.append("audio and timeline duration differ by more than 0.25 seconds")
    audio_duration = float(measured.get("audio_duration_seconds", 0.0) or 0.0)
    for key in ("reader_srt_end_seconds", "word_srt_end_seconds", "word_alignment_end_seconds"):
        end = float(measured.get(key, 0.0) or 0.0)
        if end <= 0 or end > audio_duration + 0.05:
            errors.append(f"{key} must be positive and remain inside the audio duration")
    if value.get("transcript_check", {}).get("exact_match") is not True:
        errors.append("ASR transcript must exactly match the spoken script after punctuation normalization")
    author = value.get("author_self_review", {})
    if author.get("perspective") != "novice_audio_only" or author.get("verdict") != "pass":
        errors.append("author narration self-review must pass from the novice_audio_only perspective")
    for key in ("teach_back", "likely_confusion", "style_compliance", "claim_responsibility"):
        if len(str(author.get(key, "")).strip()) < 16:
            errors.append(f"author_self_review.{key} requires concrete novice evidence")
    listening = value.get("audio_listening_review", {})
    for key in ("full_playback", "natural_pacing", "no_clipped_syllables", "no_unedited_gaps", "pronunciation_verified"):
        if listening.get(key) is not True:
            errors.append(f"audio_listening_review.{key} must be true")
    if listening.get("verdict") != "pass" or len(str(listening.get("observation", "")).strip()) < 16:
        errors.append("audio listening review requires a concrete passing observation")
    alignment = value.get("timeline_alignment_review", {})
    for key in ("word_level_checked", "clause_anchors_checked", "reader_subtitles_checked", "math_terms_checked"):
        if alignment.get(key) is not True:
            errors.append(f"timeline_alignment_review.{key} must be true")
    try:
        if float(alignment.get("max_anchor_drift_seconds", 999.0)) > 0.25:
            errors.append("timeline_alignment_review max anchor drift exceeds 0.25 seconds")
    except (TypeError, ValueError):
        errors.append("timeline_alignment_review requires numeric max_anchor_drift_seconds")
    if alignment.get("verdict") != "pass" or len(str(alignment.get("observation", "")).strip()) < 16:
        errors.append("timeline alignment review requires a concrete passing observation")
    return errors


def validate_progressive_production_data(
    contract: dict[str, Any],
    repo_root: Path,
    episode: Path,
) -> list[str]:
    errors: list[str] = []
    if contract.get("schema") != "lecture-animation-progressive-production-v2":
        errors.append("progressive production schema must be lecture-animation-progressive-production-v2")
    if not validate_hashed_record(contract, "production_hash"):
        errors.append("progressive production hash is invalid")
    try:
        stored_episode = resolve_stored_path(str(contract.get("episode", "")), repo_root)
        if stored_episode.resolve() != episode.resolve():
            errors.append("progressive production contract is bound to a different episode")
    except PipelineError as exc:
        errors.append(str(exc))
    for key in ("lecture_notes", "narration_outline", "storyboard"):
        errors.extend(validate_artifact_descriptor(contract.get(key), repo_root, key))
    if isinstance(contract.get("narration_outline"), dict) and contract["narration_outline"].get("status") != "outline_draft":
        errors.append("whole-episode narration must remain outline_draft until scene-local production")
    if isinstance(contract.get("storyboard"), dict) and contract["storyboard"].get("status") != "coarse":
        errors.append("whole-episode storyboard must be coarse rather than beat-locked")
    scenes = contract.get("scenes", [])
    if not isinstance(scenes, list) or not scenes:
        errors.append("progressive production requires scene records")
        scenes = []
    seen: set[str] = set()
    for row in scenes:
        if not isinstance(row, dict):
            errors.append("each progressive scene record must be an object")
            continue
        slug = str(row.get("scene_slug", ""))
        if not slug or slug in seen:
            errors.append(f"progressive scene_slug is missing or duplicated: {slug!r}")
        seen.add(slug)
        state = str(row.get("state", ""))
        if state not in PROGRESSIVE_SCENE_STATES:
            errors.append(f"scene {slug!r} has unsupported state {state!r}")
            continue
        if len(str(row.get("narration_intent", "")).strip()) < 8:
            errors.append(f"scene {slug!r} requires a concise narration_intent")
        artifacts = row.get("artifacts", {})
        if not isinstance(artifacts, dict):
            errors.append(f"scene {slug!r} artifacts must be an object")
            artifacts = {}
        if PROGRESSIVE_SCENE_STATES[state] >= PROGRESSIVE_SCENE_STATES["audio_aligned"]:
            for key in SCENE_EXACT_ARTIFACTS:
                errors.extend(validate_artifact_descriptor(artifacts.get(key), repo_root, f"scene {slug} {key}"))
            duration = row.get("duration_seconds")
            if not isinstance(duration, (int, float)) or float(duration) <= 0:
                errors.append(f"scene {slug!r} requires positive duration_seconds after audio alignment")
    assembly = contract.get("assembly", {})
    if not isinstance(assembly, dict) or assembly.get("status") not in {"pending", "assembled"}:
        errors.append("assembly status must be pending or assembled")
    elif assembly.get("status") == "assembled":
        for key in ("final_audio", "final_srt", "final_word_srt", "final_word_alignment", "final_timeline"):
            errors.extend(validate_artifact_descriptor(assembly.get("artifacts", {}).get(key), repo_root, f"assembly {key}"))
        if any(str(row.get("state")) != "assembled" for row in scenes if isinstance(row, dict)):
            errors.append("whole-episode assembly cannot seal before every scene is assembled")
    return errors


def seal_progressive_production_data(contract: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    result = json.loads(json.dumps(contract))
    result.pop("production_hash", None)
    for key in ("lecture_notes", "narration_outline", "storyboard"):
        result[key] = hydrate_artifact_descriptor(result.get(key, {}), repo_root)
    for row in result.get("scenes", []):
        artifacts = row.get("artifacts", {})
        row["artifacts"] = {
            key: hydrate_artifact_descriptor(value, repo_root)
            for key, value in artifacts.items()
        }
    assembly = result.get("assembly", {})
    if isinstance(assembly, dict):
        assembly["artifacts"] = {
            key: hydrate_artifact_descriptor(value, repo_root)
            for key, value in assembly.get("artifacts", {}).items()
        }
    result["production_hash"] = object_hash(result)
    return result


def scene_production_contract_data(
    production: dict[str, Any],
    scene_slug: str,
) -> dict[str, Any]:
    row = next(
        (item for item in production.get("scenes", []) if str(item.get("scene_slug")) == scene_slug),
        None,
    )
    if not isinstance(row, dict):
        raise PipelineError(f"scene not found in progressive production: {scene_slug}")
    if PROGRESSIVE_SCENE_STATES.get(str(row.get("state")), -1) < PROGRESSIVE_SCENE_STATES["audio_aligned"]:
        raise PipelineError("scene production cannot freeze before scene-local script, audio, reader SRT, word-level SRT/alignment, and timeline are exact")
    result = {
        "schema": "lecture-animation-scene-production-v2",
        "episode": production.get("episode"),
        "production_hash_at_extraction": production.get("production_hash"),
        "scene_slug": scene_slug,
        "state": row.get("state"),
        "narration_intent": row.get("narration_intent"),
        "duration_seconds": row.get("duration_seconds"),
        "artifacts": row.get("artifacts", {}),
    }
    result["scene_production_hash"] = object_hash(result)
    return result


def validate_scene_production_data(value: dict[str, Any], repo_root: Path, scene_slug: str) -> list[str]:
    errors: list[str] = []
    if value.get("schema") != "lecture-animation-scene-production-v2":
        errors.append("scene production schema must be lecture-animation-scene-production-v2")
    if not validate_hashed_record(value, "scene_production_hash"):
        errors.append("scene production hash is invalid")
    if value.get("scene_slug") != scene_slug:
        errors.append("scene production slug does not match review scene")
    if PROGRESSIVE_SCENE_STATES.get(str(value.get("state")), -1) < PROGRESSIVE_SCENE_STATES["audio_aligned"]:
        errors.append("scene production is not audio_aligned")
    for key in SCENE_EXACT_ARTIFACTS:
        errors.extend(validate_artifact_descriptor(value.get("artifacts", {}).get(key), repo_root, f"scene production {key}"))
    narration_entry = value.get("artifacts", {}).get("narration_qc", {})
    if isinstance(narration_entry, dict) and narration_entry.get("path"):
        try:
            narration_qc = load_json(resolve_stored_path(str(narration_entry["path"]), repo_root))
            errors.extend(validate_narration_qc_data(narration_qc, repo_root, scene_slug))
            for key in ("script", "audio", "reader_srt", "word_srt", "word_alignment", "timeline_fragment", "asr_transcript"):
                expected_sha = value.get("artifacts", {}).get(key, {}).get("sha256")
                qc_sha = narration_qc.get("artifacts", {}).get(key, {}).get("sha256")
                if expected_sha != qc_sha:
                    errors.append(f"scene production {key} differs from narration_qc")
        except (PipelineError, json.JSONDecodeError) as exc:
            errors.append(f"cannot validate narration_qc: {exc}")
    return errors


def scene_registry_data(profile: dict[str, Any], plan: dict[str, Any], scene_production: dict[str, Any]) -> dict[str, Any]:
    result = {
        "schema": "lecture-animation-scene-execution-registry-v2",
        "scene_slug": profile.get("context", {}).get("scene_slug"),
        "profile_hash": profile.get("profile_hash"),
        "plan_hash": object_hash(plan),
        "scene_production_hash": scene_production.get("scene_production_hash"),
        "duration_seconds": scene_production.get("duration_seconds"),
        "math_objects": plan.get("math_objects", []),
        "display_mappings": plan.get("display_mappings", []),
        "visual_bindings": plan.get("visual_bindings", []),
        "stage_state_ids": [item.get("state_id") for item in plan.get("stage_states", [])],
        "stage_transition_ids": [item.get("transition_id") for item in plan.get("stage_transitions", [])],
        "word_anchors": plan.get("word_anchors", []),
        "formula_choreography": plan.get("formula_choreography", []),
        "clause_locks": plan.get("clause_locks", []),
        "exact_media": scene_production.get("artifacts", {}),
    }
    result["registry_hash"] = object_hash(result)
    return result


def validate_narration_style_contract(value: Any, label: str = "narration_style_contract") -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    for key in (
        "contract_id",
        "audience",
        "voice",
        "reasoning_order",
        "audio_only_success_test",
        "subagent_freedom",
    ):
        if len(str(value.get(key, "")).strip()) < 12:
            errors.append(f"{label}.{key} must be concrete")
    for key in (
        "reference_scripts",
        "sentence_rules",
        "terminology_rules",
        "forbidden_patterns",
    ):
        entries = value.get(key, [])
        if not isinstance(entries, list) or not entries:
            errors.append(f"{label}.{key} must be a non-empty list")
        elif any(len(str(item).strip()) < 4 for item in entries):
            errors.append(f"{label}.{key} contains an empty or generic entry")
    return errors


def validate_audio_handoff(value: Any, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    for key in ("outgoing_clause_owner", "incoming_clause_owner", "cut_policy"):
        if len(str(value.get(key, "")).strip()) < 3:
            errors.append(f"{label}.{key} must be concrete")
    try:
        tail = float(value.get("tail_silence_seconds"))
        drift = float(value.get("max_boundary_drift_seconds"))
    except (TypeError, ValueError):
        errors.append(f"{label} requires numeric tail_silence_seconds and max_boundary_drift_seconds")
        return errors
    if not 0.0 <= tail <= 1.0:
        errors.append(f"{label}.tail_silence_seconds must be between 0 and 1 second")
    if not 0.0 < drift <= 0.25:
        errors.append(f"{label}.max_boundary_drift_seconds must be positive and no greater than 0.25 seconds")
    return errors


def validate_episode_spine_data(
    spine: dict[str, Any],
    repo_root: Path,
    episode: Path,
) -> list[str]:
    errors: list[str] = []
    if spine.get("schema") != "lecture-animation-episode-visual-spine-v2":
        errors.append("episode spine schema must be lecture-animation-episode-visual-spine-v2")
    if not validate_hashed_record(spine, "spine_hash"):
        errors.append("episode spine hash is invalid")
    stored_episode = resolve_stored_path(str(spine.get("episode", "")), repo_root)
    if stored_episode.resolve() != episode.resolve():
        errors.append("episode spine is bound to a different episode")
    errors.extend(validate_narration_style_contract(spine.get("narration_style_contract")))

    timeline_path = episode / "timeline.json"
    storyboard_path = episode / "storyboard.md"
    for key, path in (("timeline_sha256", timeline_path), ("storyboard_sha256", storyboard_path)):
        try:
            current_hash = artifact_snapshot(path, repo_root).get("sha256")
        except PipelineError as exc:
            errors.append(f"episode spine {key}: {exc}")
            continue
        if spine.get(key) != current_hash:
            errors.append(f"episode spine {key} is stale")

    if len(str(spine.get("teaching_spine", "")).strip()) < 30:
        errors.append("episode spine requires a concise teaching_spine")
    production_mode = str(spine.get("production_mode", "main_producer"))
    if production_mode not in {"main_producer", "parallel_batches"}:
        errors.append("episode spine production_mode must be main_producer or parallel_batches")
    if production_mode == "parallel_batches":
        governance = spine.get("main_agent_governance", {})
        if not isinstance(governance, dict):
            errors.append("parallel episode spine requires main_agent_governance")
            governance = {}
        if len(str(governance.get("owner", "")).strip()) < 2:
            errors.append("parallel episode spine requires a main-agent owner")
        overview = governance.get("overview_artifacts", [])
        required_overview = {"lecture", "narration_outline", "storyboard", "timeline", "episode_visual_spine"}
        if not isinstance(overview, list) or not required_overview <= {str(value) for value in overview}:
            errors.append("parallel episode spine main agent must own all overview artifacts")
        if len(str(governance.get("human_feedback_route", "")).strip()) < 20:
            errors.append("parallel episode spine requires a concrete human-feedback routing rule")
        if str(governance.get("cli_gate_policy", "")) != "required_no_bypass":
            errors.append("parallel episode spine must require V2 CLI gates without bypass")
    identities = spine.get("cross_scene_identity_carriers", [])
    if not isinstance(identities, list) or not identities:
        errors.append("episode spine requires cross_scene_identity_carriers")
    conventions = spine.get("visual_conventions", {})
    if not isinstance(conventions, dict) or not conventions:
        errors.append("episode spine requires stable visual_conventions")

    try:
        timeline = load_json(timeline_path)
    except PipelineError as exc:
        errors.append(str(exc))
        timeline = {}
    expected_scenes = {
        str(item.get("scene_slug", ""))
        for item in timeline.get("scene_groups", [])
        if item.get("scene_slug")
    }
    scene_rows = spine.get("scenes", [])
    if not isinstance(scene_rows, list):
        errors.append("episode spine scenes must be a list")
        scene_rows = []
    found_scenes: set[str] = set()
    required_fields = (
        "scene_slug",
        "teaching_role",
        "incoming_learner_state",
        "outgoing_learner_state",
        "transition_intent",
    )
    for row in scene_rows:
        if not isinstance(row, dict):
            errors.append("each episode spine scene must be an object")
            continue
        slug = str(row.get("scene_slug", ""))
        found_scenes.add(slug)
        if any(len(str(row.get(key, "")).strip()) < 8 for key in required_fields):
            errors.append(f"episode spine scene {slug!r} is missing a concrete teaching or continuity field")
        objects = row.get("primary_objects", [])
        if not isinstance(objects, list) or not objects:
            errors.append(f"episode spine scene {slug!r} requires primary_objects")
        if row.get("planning_status") not in {"provisional", "frozen"}:
            errors.append(f"episode spine scene {slug!r} planning_status must be provisional or frozen")
    if found_scenes != expected_scenes:
        errors.append("episode spine scenes must exactly cover timeline scene_groups")
    if production_mode == "parallel_batches":
        ordered_timeline_scenes = [
            str(item.get("scene_slug", ""))
            for item in timeline.get("scene_groups", [])
            if item.get("scene_slug")
        ]
        partitions = spine.get("batch_partition", [])
        if not isinstance(partitions, list) or not partitions:
            errors.append("parallel episode spine requires a complete batch_partition")
            partitions = []
        flattened: list[str] = []
        seen_batch_ids: set[str] = set()
        for index, row in enumerate(partitions):
            if not isinstance(row, dict):
                errors.append(f"batch_partition[{index}] must be an object")
                continue
            batch_id = str(row.get("batch_id", ""))
            if not batch_id or batch_id in seen_batch_ids:
                errors.append("parallel batch_partition requires unique non-empty batch_id values")
            seen_batch_ids.add(batch_id)
            batch_scenes = [str(value) for value in row.get("scenes", [])]
            if not 3 <= len(batch_scenes) <= 5:
                errors.append(f"batch_partition[{index}] must contain three to five scenes")
            flattened.extend(batch_scenes)
            for key in ("entry_compatibility_key", "exit_compatibility_key"):
                if len(str(row.get(key, "")).strip()) < 3:
                    errors.append(f"batch_partition[{index}] requires {key}")
            for key in ("entry_identity_carriers", "exit_identity_carriers"):
                carriers = row.get(key, [])
                if not isinstance(carriers, list) or not carriers:
                    errors.append(f"batch_partition[{index}] requires {key}")
            for prefix in ("entry", "exit"):
                for key in ("fixed_visual_state", "narration_text", "handoff_meaning", "freedom_inside"):
                    if len(str(row.get(f"{prefix}_{key}", "")).strip()) < 8:
                        errors.append(f"batch_partition[{index}] requires {prefix}_{key}")
                if row.get(f"{prefix}_narration_lock") not in {"intent", "exact"}:
                    errors.append(f"batch_partition[{index}] {prefix}_narration_lock must be intent or exact")
                errors.extend(
                    validate_audio_handoff(
                        row.get(f"{prefix}_audio_handoff"),
                        f"batch_partition[{index}].{prefix}_audio_handoff",
                    )
                )
        if flattened != ordered_timeline_scenes:
            errors.append("parallel batch_partition must cover every timeline scene exactly once and in order")
        for index in range(len(partitions) - 1):
            left = partitions[index] if isinstance(partitions[index], dict) else {}
            right = partitions[index + 1] if isinstance(partitions[index + 1], dict) else {}
            if left.get("exit_compatibility_key") != right.get("entry_compatibility_key"):
                errors.append(f"batch_partition boundary {index}->{index + 1} has incompatible keys")
            if left.get("exit_identity_carriers") != right.get("entry_identity_carriers"):
                errors.append(f"batch_partition boundary {index}->{index + 1} has incompatible identity carriers")
            if left.get("exit_handoff_meaning") != right.get("entry_handoff_meaning"):
                errors.append(f"batch_partition boundary {index}->{index + 1} has incompatible handoff meaning")
            if left.get("exit_audio_handoff") != right.get("entry_audio_handoff"):
                errors.append(f"batch_partition boundary {index}->{index + 1} has incompatible audio handoff")
    return errors


def validate_batch_visual_plan_data(
    batch_plan: dict[str, Any],
    spine: dict[str, Any],
    batch_id: str,
    scenes: list[str],
) -> list[str]:
    errors: list[str] = []
    if batch_plan.get("schema") != "lecture-animation-batch-visual-plan-v2":
        errors.append("batch visual plan schema must be lecture-animation-batch-visual-plan-v2")
    if not validate_hashed_record(batch_plan, "batch_plan_hash"):
        errors.append("batch visual plan hash is invalid")
    if batch_plan.get("batch_id") != batch_id:
        errors.append("batch visual plan batch_id does not match the production batch")
    if batch_plan.get("episode") != spine.get("episode"):
        errors.append("batch visual plan episode does not match the episode spine")
    if batch_plan.get("episode_spine_hash") != spine.get("spine_hash"):
        errors.append("batch visual plan is not bound to the current episode spine")
    if not 3 <= len(scenes) <= 5:
        errors.append("an autopilot production batch must contain three to five scenes")

    rows = batch_plan.get("scenes", [])
    if not isinstance(rows, list):
        errors.append("batch visual plan scenes must be a list")
        rows = []
    planned_slugs: list[str] = []
    required_fields = (
        "scene_slug",
        "continuity_in",
        "teaching_job",
        "stage_strategy",
        "continuity_out",
        "variation_from_neighbors",
        "narration_style_notes",
    )
    for row in rows:
        if not isinstance(row, dict):
            errors.append("each batch visual plan scene must be an object")
            continue
        slug = str(row.get("scene_slug", ""))
        planned_slugs.append(slug)
        if any(len(str(row.get(key, "")).strip()) < 8 for key in required_fields):
            errors.append(f"batch visual plan scene {slug!r} is missing a concrete continuity or staging field")
    if planned_slugs != scenes:
        errors.append("batch visual plan scenes must match production order exactly")
    spine_slugs = {
        str(item.get("scene_slug", ""))
        for item in spine.get("scenes", [])
        if isinstance(item, dict)
    }
    if not set(scenes) <= spine_slugs:
        errors.append("batch visual plan contains scenes absent from the episode spine")
    if not batch_plan.get("shared_identity_carriers"):
        errors.append("batch visual plan requires shared_identity_carriers")
    if not batch_plan.get("transition_contracts"):
        errors.append("batch visual plan requires transition_contracts")
    if len(str(batch_plan.get("complexity_distribution", "")).strip()) < 20:
        errors.append("batch visual plan requires a concrete complexity_distribution")
    production_mode = str(spine.get("production_mode", "main_producer"))
    if production_mode == "parallel_batches":
        expected_owner = str(spine.get("main_agent_governance", {}).get("owner", ""))
        if len(str(batch_plan.get("main_agent_owner", "")).strip()) < 2:
            errors.append("parallel batch plan requires main_agent_owner")
        elif str(batch_plan.get("main_agent_owner")) != expected_owner:
            errors.append("parallel batch plan main_agent_owner must match the episode spine")
        if batch_plan.get("cli_gate_policy") != "required_no_bypass":
            errors.append("parallel batch plan must require V2 CLI gates without bypass")
        errors.extend(validate_narration_style_contract(batch_plan.get("narration_style_contract"), "batch narration_style_contract"))
        if batch_plan.get("narration_style_contract") != spine.get("narration_style_contract"):
            errors.append("parallel batch plan narration_style_contract must exactly reproduce the episode contract")

        def validate_boundary_contract(value: Any, label: str, expected_scene: str) -> None:
            if not isinstance(value, dict):
                errors.append(f"parallel batch plan requires {label}")
                return
            if str(value.get("boundary_scene", "")) != expected_scene:
                errors.append(f"{label}.boundary_scene must match the batch boundary scene")
            required_text_fields = (
                "fixed_visual_state",
                "narration_text",
                "handoff_meaning",
                "compatibility_key",
                "freedom_inside",
            )
            if any(len(str(value.get(key, "")).strip()) < 8 for key in required_text_fields):
                errors.append(f"{label} is missing a concrete visual, narration, ownership, compatibility, or freedom field")
            if value.get("narration_lock") not in {"intent", "exact"}:
                errors.append(f"{label}.narration_lock must be intent or exact")
            errors.extend(validate_audio_handoff(value.get("audio_handoff"), f"{label}.audio_handoff"))
            if str(value.get("transition_owner", "")) != expected_owner:
                errors.append(f"{label}.transition_owner must be the main agent")
            carriers = value.get("required_identity_carriers", [])
            if not isinstance(carriers, list) or not carriers:
                errors.append(f"{label} requires identity carriers")

        validate_boundary_contract(batch_plan.get("batch_entry_contract"), "batch_entry_contract", scenes[0])
        validate_boundary_contract(batch_plan.get("batch_exit_contract"), "batch_exit_contract", scenes[-1])
        partition = next(
            (
                row
                for row in spine.get("batch_partition", [])
                if isinstance(row, dict) and str(row.get("batch_id", "")) == batch_id
            ),
            None,
        )
        if partition is None:
            errors.append("parallel batch plan is absent from the episode batch_partition")
        else:
            if [str(value) for value in partition.get("scenes", [])] != scenes:
                errors.append("parallel batch plan scenes must match its episode partition")
            entry = batch_plan.get("batch_entry_contract", {})
            exit_contract = batch_plan.get("batch_exit_contract", {})
            if isinstance(entry, dict):
                if entry.get("compatibility_key") != partition.get("entry_compatibility_key"):
                    errors.append("batch entry compatibility key differs from the episode spine")
                if entry.get("required_identity_carriers") != partition.get("entry_identity_carriers"):
                    errors.append("batch entry identity carriers differ from the episode spine")
                for key in ("fixed_visual_state", "narration_lock", "narration_text", "handoff_meaning", "freedom_inside"):
                    if entry.get(key) != partition.get(f"entry_{key}"):
                        errors.append(f"batch entry {key} differs from the episode spine")
                if entry.get("audio_handoff") != partition.get("entry_audio_handoff"):
                    errors.append("batch entry audio_handoff differs from the episode spine")
            if isinstance(exit_contract, dict):
                if exit_contract.get("compatibility_key") != partition.get("exit_compatibility_key"):
                    errors.append("batch exit compatibility key differs from the episode spine")
                if exit_contract.get("required_identity_carriers") != partition.get("exit_identity_carriers"):
                    errors.append("batch exit identity carriers differ from the episode spine")
                for key in ("fixed_visual_state", "narration_lock", "narration_text", "handoff_meaning", "freedom_inside"):
                    if exit_contract.get(key) != partition.get(f"exit_{key}"):
                        errors.append(f"batch exit {key} differs from the episode spine")
                if exit_contract.get("audio_handoff") != partition.get("exit_audio_handoff"):
                    errors.append("batch exit audio_handoff differs from the episode spine")
        adjacency = batch_plan.get("adjacency_contracts", [])
        if not isinstance(adjacency, list) or not adjacency:
            errors.append("parallel batch plan requires adjacency_contracts")
        else:
            found_pairs: set[tuple[str, str]] = set()
            for index, contract in enumerate(adjacency):
                if not isinstance(contract, dict):
                    errors.append(f"adjacency_contracts[{index}] must be an object")
                    continue
                required = (
                    "from_scene",
                    "to_scene",
                    "fixed_outgoing_visual_state",
                    "fixed_incoming_visual_state",
                    "visual_handoff",
                    "narration_handoff",
                    "narration_text",
                    "handoff_meaning",
                    "compatibility_key",
                    "transition_owner",
                    "freedom_inside",
                )
                if any(len(str(contract.get(key, "")).strip()) < 3 for key in required):
                    errors.append(f"adjacency_contracts[{index}] is incomplete")
                if contract.get("narration_lock") not in {"intent", "exact"}:
                    errors.append(f"adjacency_contracts[{index}].narration_lock must be intent or exact")
                errors.extend(
                    validate_audio_handoff(
                        contract.get("audio_handoff"),
                        f"adjacency_contracts[{index}].audio_handoff",
                    )
                )
                carriers = contract.get("identity_carriers", [])
                if not isinstance(carriers, list) or not carriers:
                    errors.append(f"adjacency_contracts[{index}] requires identity_carriers")
                if str(contract.get("transition_owner", "")) != expected_owner:
                    errors.append(f"adjacency_contracts[{index}].transition_owner must be the main agent")
                found_pairs.add((str(contract.get("from_scene", "")), str(contract.get("to_scene", ""))))
            expected_pairs = set(zip(scenes, scenes[1:]))
            if not expected_pairs <= found_pairs:
                errors.append("parallel batch plan must contract every internal adjacent-scene handoff")
    return errors


def validate_scene_planning_chain(
    plan: dict[str, Any],
    spine: dict[str, Any],
    batch_plan: dict[str, Any],
) -> list[str]:
    chain = plan.get("planning_chain", {})
    errors: list[str] = []
    if chain.get("episode_spine_hash") != spine.get("spine_hash"):
        errors.append("scene plan planning_chain.episode_spine_hash is stale")
    if chain.get("batch_plan_hash") != batch_plan.get("batch_plan_hash"):
        errors.append("scene plan planning_chain.batch_plan_hash is stale")
    planned_scenes = {
        str(item.get("scene_slug", ""))
        for item in batch_plan.get("scenes", [])
        if isinstance(item, dict)
    }
    if str(plan.get("scene_slug", "")) not in planned_scenes:
        errors.append("scene plan is not included in the bound batch visual plan")
    return errors


def command_seal_planning_artifact(args: argparse.Namespace) -> int:
    source = Path(args.input)
    payload = load_json(source)
    hash_fields = {
        "lecture-animation-episode-visual-spine-v2": "spine_hash",
        "lecture-animation-batch-visual-plan-v2": "batch_plan_hash",
    }
    hash_field = hash_fields.get(str(payload.get("schema", "")))
    if not hash_field:
        raise PipelineError("unsupported progressive planning artifact schema")
    payload.pop(hash_field, None)
    payload[hash_field] = object_hash(payload)
    output = Path(args.output) if args.output else source
    write_json(output, payload)
    print(json.dumps({"output": str(output), hash_field: payload[hash_field]}, ensure_ascii=False))
    return 0


def reviewer_certification_data(benchmark: dict[str, Any], submission: dict[str, Any]) -> dict[str, Any]:
    if benchmark.get("schema") != "lecture-animation-reviewer-benchmark-v2":
        raise PipelineError("reviewer benchmark schema is invalid")
    if not validate_hashed_record(benchmark, "benchmark_hash"):
        raise PipelineError("reviewer benchmark hash is invalid")
    current_rules_hash = object_hash(load_rules())
    if benchmark.get("rules_registry_hash") != current_rules_hash:
        raise PipelineError("reviewer benchmark is stale for the current rules registry")
    if submission.get("schema") != "lecture-animation-reviewer-benchmark-submission-v2":
        raise PipelineError("reviewer benchmark submission schema is invalid")
    if submission.get("benchmark_hash") != benchmark.get("benchmark_hash"):
        raise PipelineError("reviewer benchmark submission is bound to another benchmark")
    model = str(submission.get("reviewer_model", "")).strip()
    reasoning_effort = str(submission.get("reasoning_effort", "")).strip()
    if not model or not reasoning_effort:
        raise PipelineError("reviewer_model and reasoning_effort are required for certification")

    case_results = {
        str(item.get("case_id")): item
        for item in submission.get("case_results", [])
        if isinstance(item, dict) and item.get("case_id")
    }
    cases = [item for item in benchmark.get("cases", []) if isinstance(item, dict)]
    expected_ids = {str(item.get("case_id")) for item in cases}
    if set(case_results) != expected_ids:
        raise PipelineError("benchmark submission must answer every case exactly once")
    expected_patterns = 0
    found_patterns = 0
    failing_cases = 0
    false_passes = 0
    clean_cases = 0
    false_positives = 0
    repeat_expected = 0
    repeat_found = 0
    case_scores: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case.get("case_id"))
        result = case_results[case_id]
        expected_verdict = str(case.get("expected_verdict"))
        supplied_verdict = str(result.get("verdict"))
        required = {str(value) for value in case.get("required_pattern_keys", []) if str(value)}
        found = {str(value) for value in result.get("found_pattern_keys", []) if str(value)}
        matched = required & found
        expected_patterns += len(required)
        found_patterns += len(matched)
        is_repeat = bool(case.get("repeat_failure"))
        if is_repeat:
            repeat_expected += len(required)
            repeat_found += len(matched)
        if expected_verdict == "revise":
            failing_cases += 1
            false_passes += supplied_verdict != "revise"
        elif expected_verdict == "pass_for_user_review_pending":
            clean_cases += 1
            false_positives += supplied_verdict != "pass_for_user_review_pending"
        case_scores.append(
            {
                "case_id": case_id,
                "verdict_correct": supplied_verdict == expected_verdict,
                "required_patterns": sorted(required),
                "found_required_patterns": sorted(matched),
            }
        )
    recall = found_patterns / expected_patterns if expected_patterns else 1.0
    repeat_recall = repeat_found / repeat_expected if repeat_expected else 1.0
    false_pass_rate = false_passes / failing_cases if failing_cases else 0.0
    false_positive_rate = false_positives / clean_cases if clean_cases else 0.0
    thresholds = benchmark.get("thresholds", {})
    eligible = (
        recall >= float(thresholds.get("critical_pattern_recall", 0.90))
        and repeat_recall >= float(thresholds.get("repeat_failure_recall", 1.0))
        and false_pass_rate <= float(thresholds.get("false_pass_rate", 0.10))
        and false_positive_rate <= float(thresholds.get("false_positive_rate", 0.35))
    )
    certification: dict[str, Any] = {
        "schema": "lecture-animation-reviewer-certification-v2",
        "created_at": utc_now(),
        "reviewer_model": model,
        "reasoning_effort": reasoning_effort,
        "benchmark_hash": benchmark.get("benchmark_hash"),
        "rules_registry_hash": current_rules_hash,
        "eligible": eligible,
        "metrics": {
            "critical_pattern_recall": round(recall, 4),
            "repeat_failure_recall": round(repeat_recall, 4),
            "false_pass_rate": round(false_pass_rate, 4),
            "false_positive_rate": round(false_positive_rate, 4),
        },
        "case_scores": case_scores,
    }
    certification["certification_hash"] = object_hash(certification)
    return certification


def load_reviewer_certification(path: Path) -> dict[str, Any]:
    certification = load_json(path)
    if certification.get("schema") != "lecture-animation-reviewer-certification-v2":
        raise PipelineError("reviewer certification schema is invalid")
    if not validate_hashed_record(certification, "certification_hash"):
        raise PipelineError("reviewer certification hash is invalid")
    if certification.get("rules_registry_hash") != object_hash(load_rules()):
        raise PipelineError("reviewer certification is stale for the current rules registry")
    if not certification.get("eligible"):
        raise PipelineError("reviewer certification did not meet the admission thresholds")
    return certification


def command_seal_reviewer_benchmark(args: argparse.Namespace) -> int:
    benchmark = load_json(Path(args.input))
    if benchmark.get("schema") != "lecture-animation-reviewer-benchmark-v2":
        raise PipelineError("reviewer benchmark schema is invalid")
    cases = benchmark.get("cases", [])
    if not isinstance(cases, list) or len(cases) < 4:
        raise PipelineError("reviewer benchmark requires at least four cases")
    benchmark["rules_registry_hash"] = object_hash(load_rules())
    benchmark.pop("benchmark_hash", None)
    benchmark["benchmark_hash"] = object_hash(benchmark)
    output = Path(args.output) if args.output else Path(args.input)
    write_json(output, benchmark)
    print(json.dumps({"benchmark": str(output), "benchmark_hash": benchmark["benchmark_hash"]}, ensure_ascii=False))
    return 0


def command_certify_reviewer(args: argparse.Namespace) -> int:
    certification = reviewer_certification_data(load_json(Path(args.benchmark)), load_json(Path(args.submission)))
    write_json(Path(args.output), certification)
    print(json.dumps(certification, ensure_ascii=False, indent=2))
    return 0 if certification["eligible"] else 2


def review_capsule_data(
    manifest: dict[str, Any],
    profile: dict[str, Any],
    plan: dict[str, Any],
    session: dict[str, Any],
    author_self_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if int(profile.get("autopilot_contract_version") or 0) >= 3 and author_self_review is None:
        raise PipelineError("autopilot v3 review capsules require sealed author self-review")
    duration = float(profile.get("context", {}).get("duration") or 0.0)
    anchors = review_coverage_anchors(plan, duration)
    challenge_candidates = [
        (layer, timestamp)
        for layer, timestamps in anchors.items()
        for timestamp in timestamps
    ]
    challenge_candidates.sort(
        key=lambda item: hashlib.sha1(
            f"{manifest.get('manifest_hash')}|{item[0]}|{item[1]:.3f}".encode()
        ).hexdigest()
    )
    challenges = [
        {
            "challenge_id": f"blind-{index + 1}",
            "layer": layer,
            "timestamp_seconds": timestamp,
            "required_response": "state the visible cause, the changed object, and the next predictable state",
        }
        for index, (layer, timestamp) in enumerate(challenge_candidates[:3])
    ]
    required_rules = [
        {
            "rule_id": rule.get("rule_id"),
            "check_mode": rule.get("check_mode"),
            "evidence_fields": rule.get("evidence_fields", []),
        }
        for rule in profile.get("rules", [])
        if "reviewer" in rule.get("owners", [])
    ]
    object_ids = sorted(
        {
            str(value)
            for item in plan.get("math_object_invariants", [])
            if isinstance(item, dict)
            for value in (item.get("object_id"),)
            if value
        }
        | {
            str(region.get("primary_object"))
            for state in plan.get("stage_states", [])
            if isinstance(state, dict)
            for region in state.get("active_regions", [])
            if isinstance(region, dict) and region.get("primary_object")
        }
    )
    capsule: dict[str, Any] = {
        "schema": "lecture-animation-review-capsule-v2",
        "created_at": utc_now(),
        "manifest_hash": manifest.get("manifest_hash"),
        "author_self_review_hash": author_self_review.get("self_review_hash") if author_self_review else None,
        "scene_slug": manifest.get("scene_slug"),
        "session_id": session.get("session_id"),
        "reviewer_agent_id": session.get("reviewer_agent_id"),
        "reviewer_model": session.get("reviewer_model"),
        "reasoning_effort": session.get("reasoning_effort"),
        "reviewer_tier": session.get("reviewer_tier"),
        "duration": duration,
        "review_mp4": manifest.get("artifacts", {}).get("review_mp4", {}),
        "coverage_anchors": anchors,
        "required_rules": required_rules,
        "required_object_ids": object_ids,
        "required_pattern_keys": profile.get("live_policy_required_patterns", []),
        "blind_challenges": challenges,
        "worst_frame_candidates_required": 3,
        "blind_phase_must_be_sealed_before_contract_review": True,
    }
    capsule["capsule_hash"] = object_hash(capsule)
    return capsule


def blind_review_receipt_data(
    capsule: dict[str, Any], blind: dict[str, Any], session: dict[str, Any]
) -> dict[str, Any]:
    if capsule.get("schema") != "lecture-animation-review-capsule-v2" or not validate_hashed_record(capsule, "capsule_hash"):
        raise PipelineError("review capsule is invalid or stale")
    if blind.get("schema") != "lecture-animation-blind-review-v2":
        raise PipelineError("blind review schema is invalid")
    if blind.get("capsule_hash") != capsule.get("capsule_hash"):
        raise PipelineError("blind review is bound to another capsule")
    errors = validate_session_reviewer(session, blind)
    if errors:
        raise PipelineError("blind reviewer identity mismatch: " + " | ".join(errors))
    responses = {
        str(item.get("challenge_id")): item
        for item in blind.get("challenge_responses", [])
        if isinstance(item, dict)
    }
    expected = {str(item.get("challenge_id")) for item in capsule.get("blind_challenges", [])}
    if set(responses) != expected:
        raise PipelineError("blind review must answer every randomized checkpoint exactly once")
    for challenge_id, response in responses.items():
        if len(str(response.get("observation", "")).strip()) < 24:
            raise PipelineError(f"{challenge_id}: blind observation is too short")
    novice = blind.get("novice_pass", {})
    if not isinstance(novice, dict):
        raise PipelineError("blind review requires novice_pass")
    receipt: dict[str, Any] = {
        "schema": "lecture-animation-blind-review-receipt-v2",
        "created_at": utc_now(),
        "capsule_hash": capsule.get("capsule_hash"),
        "session_id": session.get("session_id"),
        "reviewer_agent_id": session.get("reviewer_agent_id"),
        "reviewer_model": session.get("reviewer_model"),
        "reasoning_effort": session.get("reasoning_effort"),
        "blind_submission_hash": object_hash(blind),
        "novice_pass_hash": object_hash(novice),
    }
    receipt["receipt_hash"] = object_hash(receipt)
    return receipt


def validate_review_capsule_chain(
    review: dict[str, Any],
    capsule: dict[str, Any],
    receipt: dict[str, Any],
    manifest: dict[str, Any],
    session: dict[str, Any],
    author_self_review: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    if capsule.get("schema") != "lecture-animation-review-capsule-v2" or not validate_hashed_record(capsule, "capsule_hash"):
        errors.append("review capsule is invalid or stale")
    if capsule.get("manifest_hash") != manifest.get("manifest_hash"):
        errors.append("review capsule is bound to another manifest")
    if author_self_review is None:
        errors.append("review capsule chain requires author self-review evidence")
    elif capsule.get("author_self_review_hash") != author_self_review.get("self_review_hash"):
        errors.append("review capsule is bound to another author self-review")
    if capsule.get("session_id") != session.get("session_id"):
        errors.append("review capsule is bound to another review session")
    if receipt.get("schema") != "lecture-animation-blind-review-receipt-v2" or not validate_hashed_record(receipt, "receipt_hash"):
        errors.append("blind review receipt is invalid")
    if receipt.get("capsule_hash") != capsule.get("capsule_hash"):
        errors.append("blind review receipt is bound to another capsule")
    if review.get("capsule_hash") != capsule.get("capsule_hash"):
        errors.append("full review is not bound to the compact capsule")
    if review.get("blind_receipt_hash") != receipt.get("receipt_hash"):
        errors.append("full review is not bound to the sealed blind pass")
    if object_hash(review.get("novice_pass", {})) != receipt.get("novice_pass_hash"):
        errors.append("novice_pass changed after the blind phase was sealed")
    candidates = review.get("worst_frame_candidates", [])
    if not isinstance(candidates, list) or len(candidates) < int(capsule.get("worst_frame_candidates_required", 3)):
        errors.append("full review must identify at least three timestamped worst-frame candidates")
    else:
        timestamps: set[float] = set()
        for item in candidates:
            try:
                timestamps.add(round(float(item.get("timestamp_seconds")), 3))
            except (TypeError, ValueError, AttributeError):
                errors.append("worst-frame candidate timestamp must be numeric")
            if len(str(item.get("observation", "")).strip()) < 20:
                errors.append("worst-frame candidate observation is too short")
        if len(timestamps) < 3:
            errors.append("worst-frame candidates must cover three distinct timestamps")
    return errors


def validate_change_impact_data(
    impact: dict[str, Any], previous_manifest: dict[str, Any], current_manifest: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if impact.get("schema") != "lecture-animation-change-impact-v2":
        errors.append("change impact schema is invalid")
    if not validate_hashed_record(impact, "impact_hash"):
        errors.append("change impact hash is invalid")
    if impact.get("previous_manifest_hash") != previous_manifest.get("manifest_hash"):
        errors.append("change impact previous_manifest_hash is stale")
    if impact.get("current_manifest_hash") != current_manifest.get("manifest_hash"):
        errors.append("change impact current_manifest_hash is stale")
    actual_changed = changed_manifest_artifacts(previous_manifest, current_manifest)
    if sorted(impact.get("changed_artifacts", [])) != actual_changed:
        errors.append("change impact changed_artifacts do not match the manifests")
    objects = impact.get("changed_object_ids", [])
    windows = impact.get("changed_windows", [])
    layers = set(impact.get("changed_layers", []))
    if not isinstance(objects, list) or not objects:
        errors.append("localized change impact requires changed_object_ids")
    if not isinstance(windows, list) or not windows:
        errors.append("localized change impact requires changed_windows")
    for window in windows if isinstance(windows, list) else []:
        try:
            valid_window = isinstance(window, list) and len(window) == 2 and float(window[1]) > float(window[0])
        except (TypeError, ValueError):
            valid_window = False
        if not valid_window:
            errors.append("every changed window must be [start, end] with end > start")
    if not layers or not layers <= set(HARD_GATE_LAYERS):
        errors.append("changed_layers must name one or more hard-gate layers")
    if impact.get("semantic_contract_changed") is not False:
        errors.append("diagnostic routing requires semantic_contract_changed=false")
    if impact.get("unchanged_contracts_asserted") is not True:
        errors.append("diagnostic routing requires unchanged_contracts_asserted=true")
    return errors


def load_review_session(path: Path) -> dict[str, Any]:
    session = load_json(path)
    if session.get("schema") != "lecture-animation-review-session-v2":
        raise PipelineError("review session schema is invalid")
    if not validate_hashed_record(session, "session_hash"):
        raise PipelineError("review session hash is invalid")
    if int(session.get("contract_version", 0) or 0) < REVIEW_SESSION_CONTRACT_VERSION:
        raise PipelineError("review session predates mandatory author/reviewer agent isolation; start a new batch")
    if not str(session.get("author_agent_id", "")).strip():
        raise PipelineError("review session is missing author_agent_id")
    if str(session.get("author_agent_id", "")).strip() == str(session.get("reviewer_agent_id", "")).strip():
        raise PipelineError("review session author_agent_id and reviewer_agent_id must differ")
    if session.get("review_role") not in {"acceptance", "diagnostic_support"}:
        raise PipelineError("review session is missing a valid review_role")
    if not str(session.get("episode_spine_hash", "")).strip():
        raise PipelineError("review session is missing episode_spine_hash")
    if session.get("rules_registry_hash") and session.get("rules_registry_hash") != object_hash(load_rules()):
        raise PipelineError("review session is stale for the current rules registry")
    return session


def save_review_session(path: Path, session: dict[str, Any]) -> None:
    payload = dict(session)
    payload.pop("session_hash", None)
    payload["session_hash"] = object_hash(payload)
    write_json(path, payload)


def validate_session_reviewer(session: dict[str, Any], review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if session.get("status") != "active":
        errors.append("review session is not active")
    if normalize_search_text(str(session.get("reviewer", ""))) != normalize_search_text(str(review.get("reviewer", ""))):
        errors.append("reviewer does not match the persistent review session")
    if str(session.get("reviewer_model", "")) != str(review.get("reviewer_model", "")):
        errors.append("reviewer_model does not match the persistent review session")
    if session.get("reasoning_effort") and str(session.get("reasoning_effort")) != str(review.get("reasoning_effort", "")):
        errors.append("reasoning_effort does not match the persistent review session")
    supplied_agent = str(review.get("reviewer_agent_id", ""))
    if not supplied_agent or supplied_agent != str(session.get("reviewer_agent_id", "")):
        errors.append("reviewer_agent_id must match the persistent review session")
    if session.get("reviewer_tier") == "light" and session.get("certification_suspended"):
        errors.append("light reviewer certification is suspended after a human false pass; escalate or recertify")
    return errors


def changed_manifest_artifacts(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    previous_artifacts = previous.get("artifacts", {})
    current_artifacts = current.get("artifacts", {})
    keys = set(previous_artifacts) | set(current_artifacts)
    return sorted(
        key
        for key in keys
        if previous_artifacts.get(key, {}).get("sha256") != current_artifacts.get(key, {}).get("sha256")
        or previous_artifacts.get(key, {}).get("size") != current_artifacts.get(key, {}).get("size")
    )


def finding_lineage_counts(findings: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(
        str(item.get("lineage", {}).get("classification", "initial_or_unknown"))
        for item in findings
        if isinstance(item, dict)
    )
    return {key: counts.get(key, 0) for key in sorted(REPAIR_LINEAGE_CLASSES) if counts.get(key, 0)}


def validate_repair_guidance(finding: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    finding_id = str(finding.get("finding_id", "")).strip() or "<missing>"
    lineage = finding.get("lineage", {})
    if not isinstance(lineage, dict):
        errors.append(f"{finding_id}: lineage must be an object")
        lineage = {}
    classification = str(lineage.get("classification", ""))
    if classification not in REPAIR_LINEAGE_CLASSES:
        errors.append(f"{finding_id}: lineage.classification is invalid")
    if len(str(lineage.get("root_issue_id", "")).strip()) < 3:
        errors.append(f"{finding_id}: lineage.root_issue_id is required")
    if len(str(lineage.get("evidence", "")).strip()) < 20:
        errors.append(f"{finding_id}: lineage.evidence must explain why this is old, induced, or unresolved")

    guidance = finding.get("repair_guidance", {})
    if not isinstance(guidance, dict):
        errors.append(f"{finding_id}: repair_guidance must be an object")
        guidance = {}
    anchors = guidance.get("source_anchors", [])
    if not isinstance(anchors, list) or not anchors:
        errors.append(f"{finding_id}: repair_guidance.source_anchors requires at least one code anchor")
    else:
        for index, anchor in enumerate(anchors, 1):
            if not isinstance(anchor, dict):
                errors.append(f"{finding_id}: source anchor {index} must be an object")
                continue
            if len(str(anchor.get("path", "")).strip()) < 4:
                errors.append(f"{finding_id}: source anchor {index} requires path")
            if len(str(anchor.get("symbol", "")).strip()) < 2:
                errors.append(f"{finding_id}: source anchor {index} requires symbol")
            if len(str(anchor.get("reason", "")).strip()) < 16:
                errors.append(f"{finding_id}: source anchor {index} requires a concrete reason")
    if len(str(guidance.get("mathematical_invariant", "")).strip()) < 16:
        errors.append(f"{finding_id}: repair_guidance.mathematical_invariant is too short")
    for field in ("required_changes", "must_preserve", "new_risks_to_probe"):
        values = guidance.get(field, [])
        if not isinstance(values, list) or not values or any(len(str(value).strip()) < 12 for value in values):
            errors.append(f"{finding_id}: repair_guidance.{field} requires concrete entries")
    affected = guidance.get("affected_artifacts", [])
    if not isinstance(affected, list) or not affected:
        errors.append(f"{finding_id}: repair_guidance.affected_artifacts cannot be empty")
    else:
        unknown = sorted(set(map(str, affected)) - set(manifest.get("artifacts", {})))
        if unknown:
            errors.append(f"{finding_id}: affected_artifacts are absent from the manifest: {', '.join(unknown)}")
    tests = guidance.get("acceptance_tests", [])
    if not isinstance(tests, list) or not tests:
        errors.append(f"{finding_id}: repair_guidance.acceptance_tests requires at least one test")
    else:
        test_ids: list[str] = []
        for index, test in enumerate(tests, 1):
            if not isinstance(test, dict):
                errors.append(f"{finding_id}: acceptance test {index} must be an object")
                continue
            test_id = str(test.get("test_id", "")).strip()
            test_ids.append(test_id)
            if len(test_id) < 3:
                errors.append(f"{finding_id}: acceptance test {index} requires test_id")
            if len(str(test.get("method", "")).strip()) < 16:
                errors.append(f"{finding_id}: acceptance test {index} requires a concrete method")
            if len(str(test.get("expected_evidence", "")).strip()) < 16:
                errors.append(f"{finding_id}: acceptance test {index} requires expected_evidence")
        if len(test_ids) != len(set(test_ids)):
            errors.append(f"{finding_id}: acceptance test IDs must be unique")
    return errors


def repair_contract_data(review: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    findings = [
        item for item in review.get("findings", [])
        if isinstance(item, dict)
    ]
    exhaustion = review.get("review_exhaustion", {})
    contract: dict[str, Any] = {
        "schema": "lecture-animation-repair-contract-v2",
        "created_at": utc_now(),
        "scene_slug": manifest.get("scene_slug"),
        "baseline_manifest_hash": manifest.get("manifest_hash"),
        "baseline_artifacts": {
            key: {field: value.get(field) for field in ("sha256", "size", "file_count")}
            for key, value in sorted(manifest.get("artifacts", {}).items())
        },
        "review_hash": object_hash(review),
        "reviewer": review.get("reviewer"),
        "reviewer_agent_id": review.get("reviewer_agent_id"),
        "review_exhaustion_hash": exhaustion.get("exhaustion_hash") if isinstance(exhaustion, dict) else None,
        "root_issue_clusters": [
            {
                "cluster_hash": object_hash(cluster),
                "root_issue_id": cluster.get("root_issue_id"),
                "finding_ids": cluster.get("finding_ids"),
                "affected_interval": cluster.get("affected_interval"),
                "object_ids": cluster.get("object_ids"),
                "source_anchors": cluster.get("source_anchors"),
                "upstream_causes": cluster.get("upstream_causes"),
                "downstream_symptoms": cluster.get("downstream_symptoms"),
                "dependent_artifacts": cluster.get("dependent_artifacts"),
                "sibling_risks": cluster.get("sibling_risks"),
                "must_preserve": cluster.get("must_preserve"),
                "repair_induced_risks": cluster.get("repair_induced_risks"),
            }
            for cluster in exhaustion.get("clusters", [])
            if isinstance(cluster, dict)
        ] if isinstance(exhaustion, dict) else [],
        "findings": [
            {
                "finding_id": item.get("finding_id"),
                "finding_hash": object_hash(item),
                "rule_id": item.get("rule_id"),
                "severity": item.get("severity"),
                "timestamp_seconds": item.get("timestamp_seconds"),
                "object_id": item.get("object_id"),
                "problem": item.get("problem"),
                "impact": item.get("impact"),
                "lineage": item.get("lineage"),
                "repair_guidance": item.get("repair_guidance"),
            }
            for item in findings
        ],
        "lineage_counts": finding_lineage_counts(findings),
    }
    contract["contract_hash"] = object_hash(contract)
    return contract


def validate_repair_contract_data(
    contract: dict[str, Any],
    review: dict[str, Any],
    manifest: dict[str, Any],
    repo_root: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if review.get("schema") != "lecture-animation-review-v2" or review.get("verdict") != "revise":
        errors.append("repair contract requires an independent revise review")
    if contract.get("schema") != "lecture-animation-repair-contract-v2":
        errors.append("repair contract schema is invalid")
    if not validate_hashed_record(contract, "contract_hash"):
        errors.append("repair contract hash is invalid")
    if contract.get("scene_slug") != manifest.get("scene_slug"):
        errors.append("repair contract scene_slug does not match the baseline manifest")
    if contract.get("baseline_manifest_hash") != manifest.get("manifest_hash"):
        errors.append("repair contract is bound to another baseline manifest")
    if contract.get("review_hash") != object_hash(review):
        errors.append("repair contract is bound to another independent review")
    exhaustion = review.get("review_exhaustion")
    if not isinstance(exhaustion, dict):
        errors.append("repair contract requires the review exhaustion record")
    else:
        errors.extend(
            validate_review_exhaustion_data(
                exhaustion, review, manifest, repo_root=repo_root
            )
        )
        if contract.get("review_exhaustion_hash") != exhaustion.get("exhaustion_hash"):
            errors.append("repair contract review_exhaustion_hash is stale")
        expected_clusters = {
            str(item.get("root_issue_id")): object_hash(item)
            for item in exhaustion.get("clusters", []) if isinstance(item, dict)
        }
        supplied_clusters = {
            str(item.get("root_issue_id")): str(item.get("cluster_hash"))
            for item in contract.get("root_issue_clusters", []) if isinstance(item, dict)
        }
        if supplied_clusters != expected_clusters:
            errors.append("repair contract must snapshot every root-issue cluster exactly once")
    open_findings = [
        item for item in review.get("findings", [])
        if isinstance(item, dict)
    ]
    for finding in open_findings:
        errors.extend(validate_repair_guidance(finding, manifest))
    expected = {str(item.get("finding_id")): object_hash(item) for item in open_findings}
    supplied = {
        str(item.get("finding_id")): str(item.get("finding_hash"))
        for item in contract.get("findings", []) if isinstance(item, dict)
    }
    if supplied != expected:
        errors.append("repair contract must snapshot every open finding exactly once")
    return errors


def changed_artifacts_from_repair_contract(contract: dict[str, Any], current_manifest: dict[str, Any]) -> list[str]:
    baseline = contract.get("baseline_artifacts", {})
    current = current_manifest.get("artifacts", {})
    keys = set(baseline) | set(current)
    return sorted(
        key for key in keys
        if baseline.get(key, {}).get("sha256") != current.get(key, {}).get("sha256")
        or baseline.get(key, {}).get("size") != current.get(key, {}).get("size")
    )


def repair_response_draft_data(contract: dict[str, Any], current_manifest: dict[str, Any]) -> dict[str, Any]:
    resolutions = []
    for finding in contract.get("findings", []):
        guidance = finding.get("repair_guidance", {})
        resolutions.append(
            {
                "finding_id": finding.get("finding_id"),
                "root_issue_id": finding.get("lineage", {}).get("root_issue_id"),
                "lineage_classification": finding.get("lineage", {}).get("classification"),
                "diagnosis": "",
                "root_cause_addressed": "",
                "code_changes": [
                    {"path": anchor.get("path"), "symbol": anchor.get("symbol"), "change": ""}
                    for anchor in guidance.get("source_anchors", [])
                ],
                "changed_artifacts": [],
                "acceptance_results": [
                    {"test_id": test.get("test_id"), "status": "not_run", "evidence": ""}
                    for test in guidance.get("acceptance_tests", [])
                ],
                "preservation_checks": [
                    {"requirement": value, "status": "not_run", "evidence": ""}
                    for value in guidance.get("must_preserve", [])
                ],
                "new_risk_checks": [
                    {"risk": value, "status": "not_run", "evidence": ""}
                    for value in guidance.get("new_risks_to_probe", [])
                ],
                "status": "draft",
            }
        )
    return {
        "schema": "lecture-animation-repair-response-v2",
        "repair_contract_hash": contract.get("contract_hash"),
        "baseline_manifest_hash": contract.get("baseline_manifest_hash"),
        "current_manifest_hash": current_manifest.get("manifest_hash"),
        "actual_changed_artifacts": changed_artifacts_from_repair_contract(contract, current_manifest),
        "resolutions": resolutions,
        "verdict": "draft",
    }


def validate_repair_response_data(
    response: dict[str, Any], contract: dict[str, Any], current_manifest: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if response.get("schema") != "lecture-animation-repair-response-v2":
        errors.append("repair response schema is invalid")
    if response.get("repair_contract_hash") != contract.get("contract_hash"):
        errors.append("repair response is bound to another repair contract")
    if response.get("baseline_manifest_hash") != contract.get("baseline_manifest_hash"):
        errors.append("repair response baseline manifest is stale")
    if response.get("current_manifest_hash") != current_manifest.get("manifest_hash"):
        errors.append("repair response is bound to another repaired candidate")
    actual_changed = changed_artifacts_from_repair_contract(contract, current_manifest)
    if sorted(response.get("actual_changed_artifacts", [])) != actual_changed:
        errors.append("repair response changed-artifact inventory is stale")
    contract_map = {
        str(item.get("finding_id")): item for item in contract.get("findings", []) if isinstance(item, dict)
    }
    response_map = {
        str(item.get("finding_id")): item for item in response.get("resolutions", []) if isinstance(item, dict)
    }
    if set(contract_map) != set(response_map):
        errors.append("repair response must resolve every contracted finding exactly once")
    for finding_id in sorted(set(contract_map) & set(response_map)):
        contracted = contract_map[finding_id]
        guidance = contracted.get("repair_guidance", {})
        resolution = response_map[finding_id]
        if resolution.get("root_issue_id") != contracted.get("lineage", {}).get("root_issue_id"):
            errors.append(f"{finding_id}: root_issue_id changed during repair")
        if resolution.get("lineage_classification") != contracted.get("lineage", {}).get("classification"):
            errors.append(f"{finding_id}: lineage classification changed during repair")
        for field in ("diagnosis", "root_cause_addressed"):
            if len(str(resolution.get(field, "")).strip()) < 20:
                errors.append(f"{finding_id}: {field} must explain the repair at root-cause level")
        changes = resolution.get("code_changes", [])
        if not isinstance(changes, list) or not changes:
            errors.append(f"{finding_id}: code_changes cannot be empty")
        else:
            for index, change in enumerate(changes, 1):
                if len(str(change.get("path", "")).strip()) < 4 or len(str(change.get("symbol", "")).strip()) < 2:
                    errors.append(f"{finding_id}: code change {index} requires path and symbol")
                if len(str(change.get("change", "")).strip()) < 16:
                    errors.append(f"{finding_id}: code change {index} is not concrete")
        changed = set(map(str, resolution.get("changed_artifacts", [])))
        required_changed = set(map(str, guidance.get("affected_artifacts", [])))
        if not changed or not changed <= set(actual_changed):
            errors.append(f"{finding_id}: changed_artifacts must be a non-empty subset of actual changes")
        if not required_changed <= changed:
            missing = sorted(required_changed - changed)
            errors.append(f"{finding_id}: required affected artifacts were not updated: {', '.join(missing)}")
        expected_tests = {str(item.get("test_id")) for item in guidance.get("acceptance_tests", [])}
        results = {
            str(item.get("test_id")): item for item in resolution.get("acceptance_results", []) if isinstance(item, dict)
        }
        if set(results) != expected_tests:
            errors.append(f"{finding_id}: acceptance_results must match the contract exactly")
        for test_id, result in results.items():
            if result.get("status") != "passed" or len(str(result.get("evidence", "")).strip()) < 16:
                errors.append(f"{finding_id}: acceptance test {test_id} lacks passing evidence")
        expected_preserve = set(map(str, guidance.get("must_preserve", [])))
        preserve = {
            str(item.get("requirement")): item for item in resolution.get("preservation_checks", []) if isinstance(item, dict)
        }
        if set(preserve) != expected_preserve:
            errors.append(f"{finding_id}: preservation_checks must match must_preserve exactly")
        for requirement, result in preserve.items():
            if result.get("status") != "passed" or len(str(result.get("evidence", "")).strip()) < 16:
                errors.append(f"{finding_id}: preservation check lacks evidence: {requirement}")
        expected_risks = set(map(str, guidance.get("new_risks_to_probe", [])))
        risks = {
            str(item.get("risk")): item for item in resolution.get("new_risk_checks", []) if isinstance(item, dict)
        }
        if set(risks) != expected_risks:
            errors.append(f"{finding_id}: new_risk_checks must match the contracted risks exactly")
        for risk, result in risks.items():
            if result.get("status") != "passed" or len(str(result.get("evidence", "")).strip()) < 16:
                errors.append(f"{finding_id}: new-risk check lacks evidence: {risk}")
        if resolution.get("status") != "fixed":
            errors.append(f"{finding_id}: resolution status must be fixed")
    if response.get("verdict") != "repair_complete":
        errors.append("repair response verdict must be repair_complete")
    return errors


def repair_gate_data(
    response: dict[str, Any], contract: dict[str, Any], current_manifest: dict[str, Any]
) -> dict[str, Any]:
    errors = validate_repair_response_data(response, contract, current_manifest)
    gate: dict[str, Any] = {
        "schema": "lecture-animation-repair-gate-v2",
        "created_at": utc_now(),
        "valid": not errors,
        "scene_slug": current_manifest.get("scene_slug"),
        "repair_contract_hash": contract.get("contract_hash"),
        "repair_response_hash": object_hash(response),
        "current_manifest_hash": current_manifest.get("manifest_hash"),
        "findings_resolved": len(contract.get("findings", [])),
        "lineage_counts": contract.get("lineage_counts", {}),
        "changed_artifacts": changed_artifacts_from_repair_contract(contract, current_manifest),
        "errors": errors,
    }
    gate["gate_hash"] = object_hash(gate)
    return gate


def validate_repair_gate_data(
    gate: dict[str, Any], response: dict[str, Any], contract: dict[str, Any], current_manifest: dict[str, Any]
) -> list[str]:
    expected = repair_gate_data(response, contract, current_manifest)
    errors: list[str] = []
    if gate.get("schema") != "lecture-animation-repair-gate-v2" or not validate_hashed_record(gate, "gate_hash"):
        errors.append("repair gate schema or hash is invalid")
    for field in ("valid", "scene_slug", "repair_contract_hash", "repair_response_hash", "current_manifest_hash", "findings_resolved", "lineage_counts", "changed_artifacts", "errors"):
        if gate.get(field) != expected.get(field):
            errors.append(f"repair gate is stale: {field}")
    if gate.get("valid") is not True:
        errors.append("repair gate did not pass")
    return errors


def review_strategy_data(
    previous_manifest: dict[str, Any],
    current_manifest: dict[str, Any],
    previous_review: dict[str, Any],
    session: dict[str, Any],
    prior_attempts: list[dict[str, Any]] | None = None,
    change_impact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    changed = changed_manifest_artifacts(previous_manifest, current_manifest)
    material_keys = {
        "profile", "live_policy", "deliberation", "design_gate", "precedent_packet",
        "episode_spine", "batch_plan", "plan", "scene_production", "scene_registry",
        "script", "timeline", "audio", "srt", "word_srt", "word_alignment", "asr_transcript", "narration_qc",
        "text_inventory_baseline", "text_inventory_audit",
    }
    material_changes = sorted(material_keys & set(changed))
    scene_slug = str(current_manifest.get("scene_slug", ""))
    scene_attempts = [
        row for row in (prior_attempts or [])
        if str(row.get("scene_slug", "")) == scene_slug and row.get("review_mode") in {None, "full_regression"}
    ]
    full_count = len(scene_attempts)
    policy_changed = "live_policy" in changed or "profile" in changed
    impact_errors = (
        validate_change_impact_data(change_impact, previous_manifest, current_manifest)
        if change_impact is not None
        else ["localized change impact proof was not supplied"]
    )
    if previous_review.get("verdict") != "revise":
        mode = "full_regression"
        reasons = ["previous review did not produce a localized revise finding set"]
    elif material_changes:
        mode = "full_regression"
        reasons = ["material contract artifacts changed: " + ", ".join(material_changes)]
    elif impact_errors:
        mode = "full_regression"
        reasons = ["diagnostic routing proof failed: " + " | ".join(impact_errors)]
    else:
        mode = "diagnostic"
        reasons = ["hash-bound impact proof localizes the repair while semantic contracts remain fixed"]
    escalation = full_count >= 3 and mode == "full_regression"
    if escalation:
        reasons.append("three or more prior full reviews require root-cause re-planning before another broad rerender loop")
    strategy: dict[str, Any] = {
        "schema": "lecture-animation-review-strategy-v2",
        "scene_slug": scene_slug,
        "previous_manifest_hash": previous_manifest.get("manifest_hash"),
        "current_manifest_hash": current_manifest.get("manifest_hash"),
        "review_session_id": session.get("session_id"),
        "changed_artifacts": changed,
        "material_changes": material_changes,
        "policy_changed": policy_changed,
        "change_impact_hash": change_impact.get("impact_hash") if change_impact else None,
        "change_impact_errors": impact_errors,
        "next_review_mode": mode,
        "reasons": reasons,
        "full_reviews_for_scene": full_count,
        "root_cause_escalation_required": escalation,
        "final_full_review_always_required": True,
        "layout_gate_remains_mandatory": True,
    }
    strategy["strategy_hash"] = object_hash(strategy)
    return strategy


def merged_windows(windows: list[tuple[float, float]], duration: float) -> list[list[float]]:
    normalized = sorted((max(0.0, start), min(duration, end)) for start, end in windows if end > start)
    merged: list[list[float]] = []
    for start, end in normalized:
        if merged and start <= merged[-1][1] + 0.15:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([round(start, 3), round(end, 3)])
    return merged


def timestamp_in_windows(timestamp: float, windows: list[list[float]]) -> bool:
    return any(float(start) <= timestamp <= float(end) for start, end in windows)


def diagnostic_packet_data(
    previous_manifest: dict[str, Any],
    current_manifest: dict[str, Any],
    previous_review: dict[str, Any],
    profile: dict[str, Any],
    session: dict[str, Any],
    change_impact: dict[str, Any],
    author_self_review: dict[str, Any] | None = None,
    margin: float = 1.0,
) -> dict[str, Any]:
    if int(profile.get("autopilot_contract_version") or 0) >= 3 and author_self_review is None:
        raise PipelineError("autopilot v3 diagnostic packets require sealed author self-review")
    if previous_review.get("manifest_hash") != previous_manifest.get("manifest_hash"):
        raise PipelineError("previous review is not bound to the previous manifest")
    if previous_review.get("verdict") != "revise":
        raise PipelineError("diagnostic review requires a previous revise verdict")
    if previous_manifest.get("scene_slug") != current_manifest.get("scene_slug"):
        raise PipelineError("diagnostic manifests must describe the same scene")
    if previous_manifest.get("manifest_hash") == current_manifest.get("manifest_hash"):
        raise PipelineError("diagnostic review requires a newly frozen candidate")
    impact_errors = validate_change_impact_data(change_impact, previous_manifest, current_manifest)
    if impact_errors:
        raise PipelineError("diagnostic change impact is invalid: " + " | ".join(impact_errors))
    findings = [
        item for item in previous_review.get("findings", [])
        if isinstance(item, dict)
    ]
    if not findings:
        raise PipelineError("diagnostic review requires at least one open prior finding")
    duration = float(profile.get("context", {}).get("duration") or 0.0)
    if duration <= 0:
        raise PipelineError("profile duration is required for diagnostic windows")
    windows: list[tuple[float, float]] = []
    normalized_findings: list[dict[str, Any]] = []
    for finding in findings:
        try:
            timestamp = float(finding.get("timestamp_seconds"))
        except (TypeError, ValueError) as exc:
            raise PipelineError("every diagnostic finding requires timestamp_seconds") from exc
        windows.append((timestamp - margin, timestamp + margin))
        normalized_findings.append(
            {
                "finding_id": finding.get("finding_id"),
                "rule_id": finding.get("rule_id"),
                "severity": finding.get("severity"),
                "timestamp_seconds": timestamp,
                "object_id": finding.get("object_id"),
                "problem": finding.get("problem"),
                "suggested_fix": finding.get("suggested_fix"),
            }
        )
    review_windows = merged_windows(windows, duration)
    sample_candidates = [duration * 0.2, duration * 0.5, duration * 0.8]
    regression_samples = [round(value, 3) for value in sample_candidates if not timestamp_in_windows(value, review_windows)][:2]
    if not regression_samples:
        regression_samples = [round(min(duration, review_windows[-1][1] + 0.25), 3)]
    changed = changed_manifest_artifacts(previous_manifest, current_manifest)
    if not changed:
        raise PipelineError("no artifact hash changed between diagnostic candidates")
    reviewer_rule_ids = sorted(
        str(rule.get("rule_id")) for rule in profile.get("rules", []) if "reviewer" in rule.get("owners", [])
    )
    packet = {
        "schema": "lecture-animation-diagnostic-packet-v2",
        "created_at": utc_now(),
        "scene_slug": current_manifest.get("scene_slug"),
        "session_id": session.get("session_id"),
        "reviewer_agent_id": session.get("reviewer_agent_id"),
        "previous_manifest_hash": previous_manifest.get("manifest_hash"),
        "current_manifest_hash": current_manifest.get("manifest_hash"),
        "author_self_review_hash": author_self_review.get("self_review_hash") if author_self_review else None,
        "changed_artifacts": changed,
        "change_impact_hash": change_impact.get("impact_hash"),
        "changed_object_ids": change_impact.get("changed_object_ids", []),
        "changed_layers": change_impact.get("changed_layers", []),
        "prior_findings": normalized_findings,
        "required_review_windows": review_windows,
        "required_regression_samples": regression_samples,
        "affected_rule_ids": reviewer_rule_ids,
        "review_mode": "incremental_fix_verification",
        "may_grant_user_review_pending": False,
        "full_regression_required_after_diagnostic_pass": True,
    }
    packet["packet_hash"] = object_hash(packet)
    return packet


def verify_diagnostic_review_data(
    submission: dict[str, Any], packet: dict[str, Any], session: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if packet.get("schema") != "lecture-animation-diagnostic-packet-v2" or not validate_hashed_record(packet, "packet_hash"):
        errors.append("diagnostic packet is invalid or stale")
    if submission.get("schema") != "lecture-animation-diagnostic-review-v2":
        errors.append("diagnostic submission schema is invalid")
    if submission.get("packet_hash") != packet.get("packet_hash"):
        errors.append("diagnostic submission is not bound to this packet")
    if submission.get("current_manifest_hash") != packet.get("current_manifest_hash"):
        errors.append("diagnostic submission is not bound to the current manifest")
    errors.extend(validate_session_reviewer(session, submission))
    expected = {str(item.get("finding_id")) for item in packet.get("prior_findings", [])}
    checks = submission.get("finding_checks", [])
    check_map = {str(item.get("finding_id")): item for item in checks if isinstance(item, dict)}
    if set(check_map) != expected:
        errors.append("diagnostic submission must check every prior finding exactly once")
    unresolved = []
    for finding_id, check in check_map.items():
        status = check.get("status")
        if status not in {"fixed", "not_fixed"}:
            errors.append(f"{finding_id}: status must be fixed or not_fixed")
        if status == "not_fixed":
            unresolved.append(finding_id)
        try:
            timestamp = float(check.get("timestamp_seconds"))
            if not timestamp_in_windows(timestamp, packet.get("required_review_windows", [])):
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"{finding_id}: evidence timestamp is outside required diagnostic windows")
        if len(str(check.get("observation", "")).strip()) < 16 or generic_observation(str(check.get("observation", ""))):
            errors.append(f"{finding_id}: observation is generic or too short")
    supplied_samples = submission.get("regression_samples", [])
    supplied_times = set()
    for item in supplied_samples:
        try:
            supplied_times.add(round(float(item.get("timestamp_seconds")), 3))
        except (TypeError, ValueError, AttributeError):
            pass
        if len(str(item.get("observation", "")).strip()) < 16:
            errors.append("regression sample observation is too short")
    required_times = {round(float(value), 3) for value in packet.get("required_regression_samples", [])}
    if not required_times <= supplied_times:
        errors.append("diagnostic submission is missing required unchanged-region regression samples")
    verdict = submission.get("verdict")
    if verdict not in {"revise", "diagnostic_fix_verified"}:
        errors.append("diagnostic verdict must be revise or diagnostic_fix_verified")
    if verdict == "diagnostic_fix_verified" and unresolved:
        errors.append("diagnostic pass contains unresolved findings")
    if verdict == "diagnostic_fix_verified" and submission.get("requests_user_review_pending") is True:
        errors.append("diagnostic review can never grant user_review_pending")
    return errors


def reviewer_health(rows: list[dict[str, Any]], reviewer_model: str) -> dict[str, Any]:
    relevant = [row for row in rows if str(row.get("reviewer_model", "")) == reviewer_model]
    human_reviewed = [row for row in relevant if row.get("human_verdict") in {"pass", "revise"}]
    automatic_passes = [row for row in relevant if str(row.get("automatic_verdict", "")).startswith("pass")]
    judged_automatic_passes = [row for row in automatic_passes if row.get("human_verdict") in {"pass", "revise"}]
    misses = [row for row in judged_automatic_passes if row.get("human_verdict") == "revise"]
    zero_finding_passes = [row for row in automatic_passes if int(row.get("reviewer_findings", 0) or 0) == 0]
    miss_rate = len(misses) / len(judged_automatic_passes) if judged_automatic_passes else 0.0
    zero_rate = len(zero_finding_passes) / len(automatic_passes) if automatic_passes else 0.0
    anomalous = (len(judged_automatic_passes) >= 3 and misses and miss_rate > 0.20) or (len(automatic_passes) >= 4 and zero_rate >= 0.80)
    triggers = misses[-5:] if misses else zero_finding_passes[-4:]
    return {
        "reviewer_model": reviewer_model,
        "samples": len(relevant),
        "human_reviewed": len(human_reviewed),
        "automatic_passes": len(automatic_passes),
        "automatic_passes_human_reviewed": len(judged_automatic_passes),
        "false_passes": len(misses),
        "false_pass_rate": round(miss_rate, 4),
        "zero_finding_pass_rate": round(zero_rate, 4),
        "anomalous": anomalous,
        "trigger_event_ids": [row.get("event_id") for row in triggers if row.get("event_id")],
    }


def generic_observation(text: str) -> bool:
    normalized = normalize_search_text(text)
    return any(pattern in normalized for pattern in GENERIC_EVIDENCE)


def dedupe_times(values: Iterable[float], tolerance: float = 0.08) -> list[float]:
    result: list[float] = []
    for value in sorted(values):
        if not result or abs(value - result[-1]) > tolerance:
            result.append(round(value, 3))
    return result


def review_coverage_anchors(plan: dict[str, Any], duration: float) -> dict[str, list[float]]:
    opening = min(0.2, max(0.0, duration / 4.0))
    ending = max(0.0, duration - 0.2)
    state_mids = [
        (float(item.get("start", 0.0)) + float(item.get("end", 0.0))) / 2.0
        for item in plan.get("stage_states", [])
        if isinstance(item, dict)
    ]
    transition_mids = [
        (float(item.get("start", 0.0)) + float(item.get("end", 0.0))) / 2.0
        for item in plan.get("stage_transitions", [])
        if isinstance(item, dict)
    ]
    invariant_times = [
        float(value)
        for item in plan.get("math_object_invariants", [])
        if isinstance(item, dict)
        for value in item.get("checkpoints", [])
    ]
    clause_times = [
        float(item.get("spoken_start"))
        for item in plan.get("clause_locks", [])
        if isinstance(item, dict) and isinstance(item.get("spoken_start"), (int, float))
    ]
    beat_mids = [
        (float(item.get("start", 0.0)) + float(item.get("end", 0.0))) / 2.0
        for item in plan.get("beats", [])
        if isinstance(item, dict)
    ]
    return {
        "layout": dedupe_times([opening, ending, *state_mids, *transition_mids]),
        "math_object": dedupe_times(invariant_times or state_mids or [duration / 2.0]),
        "timing_attention": dedupe_times([opening, ending, *transition_mids, *clause_times]),
        "novice_causality": dedupe_times(beat_mids or state_mids or [duration / 2.0]),
    }


def validate_review_coverage_sweeps(
    review: dict[str, Any],
    plan: dict[str, Any],
    duration: float,
) -> list[str]:
    errors: list[str] = []
    sweeps = review.get("coverage_sweeps", [])
    if not isinstance(sweeps, list):
        return ["coverage_sweeps must be a list"]
    sweep_map: dict[str, dict[str, Any]] = {}
    for sweep in sweeps:
        if not isinstance(sweep, dict):
            errors.append("every coverage sweep must be structured")
            continue
        layer = str(sweep.get("layer", ""))
        if layer not in HARD_GATE_LAYERS:
            errors.append(f"unknown coverage sweep layer: {layer or '<empty>'}")
            continue
        if layer in sweep_map:
            errors.append(f"duplicate coverage sweep layer: {layer}")
        sweep_map[layer] = sweep
    missing = sorted(set(HARD_GATE_LAYERS) - set(sweep_map))
    if missing:
        errors.append("review missing full-sweep layers: " + ", ".join(missing))
    anchors = review_coverage_anchors(plan, duration)
    for layer in HARD_GATE_LAYERS:
        sweep = sweep_map.get(layer)
        if sweep is None:
            continue
        if sweep.get("result") not in {"pass", "fail"}:
            errors.append(f"coverage sweep {layer} requires result pass or fail")
        observation = str(sweep.get("observation", "")).strip()
        if len(observation) < 20 or generic_observation(observation):
            errors.append(f"coverage sweep {layer} needs concrete visual evidence")
        object_ids = sweep.get("object_ids", [])
        if not isinstance(object_ids, list) or not object_ids:
            errors.append(f"coverage sweep {layer} requires inspected object_ids")
        supplied: list[float] = []
        for value in sweep.get("timestamps", []):
            try:
                timestamp = float(value)
            except (TypeError, ValueError):
                errors.append(f"coverage sweep {layer} contains a non-numeric timestamp")
                continue
            if timestamp < 0 or (duration and timestamp > duration + 0.25):
                errors.append(f"coverage sweep {layer} timestamp is outside the scene")
            supplied.append(timestamp)
        for anchor in anchors[layer]:
            if not any(abs(timestamp - anchor) <= 0.65 for timestamp in supplied):
                errors.append(f"coverage sweep {layer} misses required anchor {anchor:.3f}s")
    return errors


def planned_object_ids(plan: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(item.get("primary_object"))
            for item in plan.get("stage_regions", [])
            if isinstance(item, dict) and item.get("primary_object")
        }
        | {
            str(item.get("object_id"))
            for item in plan.get("math_object_invariants", [])
            if isinstance(item, dict) and item.get("object_id")
        }
        | {
            str(item.get("object_id"))
            for item in plan.get("math_objects", [])
            if isinstance(item, dict) and item.get("object_id")
        }
    )


def self_review_probe_draft_data(
    manifest: dict[str, Any], profile: dict[str, Any], plan: dict[str, Any]
) -> dict[str, Any]:
    duration = float(profile.get("context", {}).get("duration") or 0.0)
    object_ids = planned_object_ids(plan) or ["primary_math_object"]
    strict = bool({"human_rejected", "repeat_rejected"} & set(profile.get("tags", [])))
    minimum_per_layer = 2 if strict else 1
    probes: list[dict[str, Any]] = []
    for layer, timestamps in review_coverage_anchors(plan, duration).items():
        candidates = list(dict.fromkeys(round(float(value), 3) for value in timestamps))
        while len(candidates) < minimum_per_layer:
            fraction = (len(candidates) + 1) / (minimum_per_layer + 1)
            candidates.append(round(duration * fraction, 3))
        for index, timestamp in enumerate(candidates[:minimum_per_layer], 1):
            probes.append(
                {
                    "probe_id": f"{layer}-falsification-{index}",
                    "layer": layer,
                    "adversarial": strict,
                    "worst_frame_rank": index if strict else None,
                    "timestamp_seconds": timestamp,
                    "object_ids": object_ids,
                    "expected_state": "",
                    "actual_observed_state": "",
                    "falsification_attempt": "",
                    "evidence": {
                        "artifact_key": "qc",
                        "source_artifact_key": "review_mp4",
                        "source_sha256": manifest.get("artifacts", {}).get("review_mp4", {}).get("sha256"),
                        "source_kind": "decoded_review_frame",
                        "frame_path": "",
                        "frame_sha256": "",
                    },
                    "independent_check": {
                        "method": "",
                        "expected": "",
                        "actual": "",
                        "tolerance": "",
                        "check_type": "numeric",
                        "expected_value": None,
                        "actual_value": None,
                        "tolerance_value": None,
                        "passed": False,
                    },
                    "result": "draft",
                }
            )
    return {
        "schema": "lecture-animation-self-review-probe-v2",
        "manifest_hash": manifest.get("manifest_hash"),
        "scene_slug": manifest.get("scene_slug"),
        "strict_mode": strict,
        "minimum_probes_per_layer": minimum_per_layer,
        "probes": probes,
        "verdict": "draft",
    }


def validate_self_review_probe_data(
    probe: dict[str, Any],
    manifest: dict[str, Any],
    profile: dict[str, Any],
    plan: dict[str, Any],
    require_hash: bool = True,
    repo_root: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if probe.get("schema") != "lecture-animation-self-review-probe-v2":
        errors.append("self-review probe schema is invalid")
    if require_hash and not validate_hashed_record(probe, "probe_hash"):
        errors.append("self-review probe hash is invalid")
    if probe.get("manifest_hash") != manifest.get("manifest_hash"):
        errors.append("self-review probe is bound to another frozen candidate")
    if probe.get("scene_slug") != manifest.get("scene_slug"):
        errors.append("self-review probe scene_slug does not match the manifest")
    strict = bool({"human_rejected", "repeat_rejected"} & set(profile.get("tags", [])))
    minimum = 2 if strict else 1
    if int(probe.get("minimum_probes_per_layer", 0) or 0) != minimum:
        errors.append("self-review probe minimum does not match the risk tier")
    duration = float(profile.get("context", {}).get("duration") or 0.0)
    allowed_objects = set(planned_object_ids(plan))
    by_layer: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    probe_ids: list[str] = []
    evidence_hashes: list[str] = []
    numeric_claims: list[tuple[str, str, str]] = []
    expected_probe_rows = {
        str(item.get("probe_id")): item
        for item in self_review_probe_draft_data(manifest, profile, plan).get("probes", [])
    }
    for item in probe.get("probes", []):
        if not isinstance(item, dict):
            errors.append("self-review probes must be structured objects")
            continue
        layer = str(item.get("layer", ""))
        by_layer[layer].append(item)
        probe_id = str(item.get("probe_id", "")).strip()
        probe_ids.append(probe_id)
        if len(probe_id) < 5:
            errors.append("every self-review probe requires probe_id")
        try:
            timestamp = float(item.get("timestamp_seconds"))
            if timestamp < 0 or (duration and timestamp > duration + 0.25):
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"{probe_id or layer}: timestamp is outside the scene")
            timestamp = -1.0
        expected_probe = expected_probe_rows.get(probe_id)
        if expected_probe is None:
            errors.append(f"{probe_id or layer}: probe was not selected by the CLI challenge")
        elif abs(timestamp - float(expected_probe.get("timestamp_seconds", -999.0))) > 0.001:
            errors.append(f"{probe_id or layer}: timestamp was changed after the CLI selected it")
        object_ids = item.get("object_ids", [])
        if not isinstance(object_ids, list) or not object_ids:
            errors.append(f"{probe_id or layer}: object_ids cannot be empty")
        elif allowed_objects and not set(map(str, object_ids)) <= allowed_objects:
            errors.append(f"{probe_id or layer}: object_ids include objects absent from the plan")
        for field in ("expected_state", "actual_observed_state", "falsification_attempt"):
            value = str(item.get(field, "")).strip()
            if len(value) < 24 or generic_observation(value):
                errors.append(f"{probe_id or layer}: {field} needs concrete adversarial evidence")
        evidence = item.get("evidence", {})
        artifact_key = str(evidence.get("artifact_key", "")) if isinstance(evidence, dict) else ""
        source_kind = str(evidence.get("source_kind", "")) if isinstance(evidence, dict) else ""
        if source_kind not in SELF_REVIEW_INDEPENDENT_SOURCES:
            errors.append(f"{probe_id or layer}: evidence source is not independently observable")
        if artifact_key in {"telemetry", "authoring_qc"}:
            errors.append(f"{probe_id or layer}: telemetry cannot prove its own correctness")
        if isinstance(evidence, dict):
            evidence_hashes.append(str(evidence.get("frame_sha256", "")))
            errors.extend(
                validate_bound_frame_evidence(
                    evidence, manifest, (repo_root or Path.cwd()).resolve(), probe_id or layer
                )
            )
        independent = item.get("independent_check", {})
        if not isinstance(independent, dict) or independent.get("passed") is not True:
            errors.append(f"{probe_id or layer}: independent_check must pass")
        else:
            for field in ("method", "expected", "actual"):
                if len(str(independent.get(field, "")).strip()) < 16:
                    errors.append(f"{probe_id or layer}: independent_check.{field} is too short")
            if independent.get("tolerance") in (None, ""):
                errors.append(f"{probe_id or layer}: independent_check.tolerance is required")
            check_type = str(independent.get("check_type", ""))
            if check_type != "numeric":
                errors.append(f"{probe_id or layer}: independent_check.check_type must be numeric")
            else:
                numeric_claims.append(
                    (
                        normalize_search_text(str(independent.get("method", ""))),
                        str(independent.get("expected_value", "")),
                        str(independent.get("actual_value", "")),
                    )
                )
                try:
                    expected_value = float(independent.get("expected_value"))
                    actual_value = float(independent.get("actual_value"))
                    tolerance_value = float(independent.get("tolerance_value"))
                    if tolerance_value < 0:
                        raise ValueError
                    computed_pass = abs(actual_value - expected_value) <= tolerance_value
                    if independent.get("passed") is not computed_pass:
                        errors.append(f"{probe_id or layer}: independent_check.passed disagrees with recomputation")
                    if not computed_pass:
                        errors.append(f"{probe_id or layer}: independent numeric check exceeds tolerance")
                except (TypeError, ValueError):
                    errors.append(f"{probe_id or layer}: independent numeric values are invalid")
        if item.get("result") != "falsification_not_found":
            errors.append(f"{probe_id or layer}: result must be falsification_not_found before handoff")
        if strict and item.get("adversarial") is not True:
            errors.append(f"{probe_id or layer}: strict scenes require adversarial probes")
    if len(probe_ids) != len(set(probe_ids)) or any(not value for value in probe_ids):
        errors.append("self-review probe IDs must be unique and non-empty")
    if len(evidence_hashes) != len(set(evidence_hashes)) or any(not value for value in evidence_hashes):
        errors.append("every self-review probe must use a distinct decoded frame")
    if len(numeric_claims) >= 4 and len(set(numeric_claims)) / len(numeric_claims) < 0.75:
        errors.append("self-review numeric checks are excessively duplicated across hard-gate layers")
    for layer in HARD_GATE_LAYERS:
        if len(by_layer.get(layer, [])) < minimum:
            errors.append(f"self-review probe layer {layer} requires at least {minimum} probes")
        if strict:
            ranks = {item.get("worst_frame_rank") for item in by_layer.get(layer, [])}
            if not set(range(1, minimum + 1)) <= ranks:
                errors.append(f"self-review probe layer {layer} must rank its worst frames")
    unknown_layers = sorted(set(by_layer) - set(HARD_GATE_LAYERS))
    if unknown_layers:
        errors.append("self-review probe contains unknown layers: " + ", ".join(unknown_layers))
    if probe.get("verdict") != "probe_passed":
        errors.append("self-review probe verdict must be probe_passed")
    return errors


def review_core_hash(review: dict[str, Any]) -> str:
    core = dict(review)
    core.pop("review_exhaustion", None)
    return object_hash(core)


def review_exhaustion_draft_data(review: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in review.get("findings", []):
        if isinstance(finding, dict):
            root_id = str(finding.get("lineage", {}).get("root_issue_id", "")).strip()
            grouped[root_id].append(finding)
    clusters = []
    for root_id, findings in sorted(grouped.items()):
        timestamps = [float(item.get("timestamp_seconds", 0.0) or 0.0) for item in findings]
        clusters.append(
            {
                "root_issue_id": root_id,
                "finding_ids": [str(item.get("finding_id")) for item in findings],
                "affected_interval": {"start": min(timestamps), "end": max(timestamps)},
                "object_ids": sorted({str(item.get("object_id")) for item in findings if item.get("object_id")}),
                "source_anchors": [],
                "upstream_causes": [],
                "downstream_symptoms": [],
                "dependent_artifacts": [],
                "sibling_risks": [],
                "must_preserve": [],
                "repair_induced_risks": [],
                "hard_gate_layers": {
                    layer: {"checked": False, "timestamps": [], "observation": "", "evidence": []}
                    for layer in HARD_GATE_LAYERS
                },
                "coverage_complete": False,
                "coverage_gaps": [],
                "completeness_reason": "",
            }
        )
    return {
        "schema": "lecture-animation-review-exhaustion-v2",
        "manifest_hash": manifest.get("manifest_hash"),
        "scene_slug": manifest.get("scene_slug"),
        "review_core_hash": review_core_hash(review),
        "clusters": clusters,
        "unclustered_searches": [
            {"layer": layer, "performed": False, "query": "", "result": "", "evidence": []}
            for layer in HARD_GATE_LAYERS
        ],
        "coverage_complete": False,
        "reviewer_statement": "",
        "verdict": "draft",
    }


def validate_review_evidence_samples(
    samples: Any,
    manifest: dict[str, Any],
    repo_root: Path,
    prefix: str,
    minimum: int,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(samples, list) or len(samples) < minimum:
        return [f"{prefix}: requires at least {minimum} hash-bound frame evidence samples"]
    sample_ids: list[str] = []
    for index, sample in enumerate(samples, 1):
        item_prefix = f"{prefix} evidence {index}"
        if not isinstance(sample, dict):
            errors.append(f"{item_prefix}: must be a structured object")
            continue
        sample_ids.append(str(sample.get("evidence_id", "")).strip())
        try:
            if float(sample.get("timestamp_seconds")) < 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"{item_prefix}: timestamp_seconds must be non-negative")
        if not isinstance(sample.get("object_ids"), list) or not sample.get("object_ids"):
            errors.append(f"{item_prefix}: object_ids cannot be empty")
        if len(str(sample.get("observation", "")).strip()) < 20 or generic_observation(str(sample.get("observation", ""))):
            errors.append(f"{item_prefix}: observation needs concrete evidence")
        errors.extend(validate_bound_frame_evidence(sample, manifest, repo_root, item_prefix))
    if any(not value for value in sample_ids) or len(sample_ids) != len(set(sample_ids)):
        errors.append(f"{prefix}: evidence_id values must be unique and non-empty")
    return errors


def validate_review_exhaustion_data(
    exhaustion: dict[str, Any],
    review: dict[str, Any],
    manifest: dict[str, Any],
    require_hash: bool = True,
    repo_root: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    evidence_root = (repo_root or Path.cwd()).resolve()
    if exhaustion.get("schema") != "lecture-animation-review-exhaustion-v2":
        errors.append("review exhaustion schema is invalid")
    if require_hash and not validate_hashed_record(exhaustion, "exhaustion_hash"):
        errors.append("review exhaustion hash is invalid")
    if exhaustion.get("manifest_hash") != manifest.get("manifest_hash"):
        errors.append("review exhaustion is bound to another manifest")
    if exhaustion.get("scene_slug") != manifest.get("scene_slug"):
        errors.append("review exhaustion scene_slug does not match the manifest")
    if exhaustion.get("review_core_hash") != review_core_hash(review):
        errors.append("review exhaustion is bound to another review submission")
    open_findings = {
        str(item.get("finding_id")): item
        for item in review.get("findings", [])
        if isinstance(item, dict)
    }
    supplied_findings: list[str] = []
    supplied_roots: list[str] = []
    for cluster in exhaustion.get("clusters", []):
        if not isinstance(cluster, dict):
            errors.append("review exhaustion clusters must be structured objects")
            continue
        root_id = str(cluster.get("root_issue_id", "")).strip()
        supplied_roots.append(root_id)
        finding_ids = [str(value) for value in cluster.get("finding_ids", [])]
        supplied_findings.extend(finding_ids)
        if not root_id or not finding_ids:
            errors.append("each review exhaustion cluster requires root_issue_id and finding_ids")
        for finding_id in finding_ids:
            finding = open_findings.get(finding_id)
            if finding is None:
                errors.append(f"review exhaustion contains unknown finding {finding_id!r}")
            elif str(finding.get("lineage", {}).get("root_issue_id", "")).strip() != root_id:
                errors.append(f"{finding_id}: exhaustion root_issue_id disagrees with the finding lineage")
        interval = cluster.get("affected_interval", {})
        try:
            start = float(interval.get("start"))
            end = float(interval.get("end"))
            if start < 0 or end < start:
                raise ValueError
        except (TypeError, ValueError, AttributeError):
            errors.append(f"{root_id}: affected_interval is invalid")
        if not isinstance(cluster.get("object_ids"), list) or not cluster.get("object_ids"):
            errors.append(f"{root_id}: object_ids cannot be empty")
        anchors = cluster.get("source_anchors", [])
        if not isinstance(anchors, list) or not anchors:
            errors.append(f"{root_id}: source_anchors cannot be empty")
        else:
            for anchor in anchors:
                if not isinstance(anchor, dict) or any(
                    len(str(anchor.get(field, "")).strip()) < minimum
                    for field, minimum in (("path", 4), ("symbol", 2), ("reason", 16))
                ):
                    errors.append(f"{root_id}: every source anchor requires path, symbol, and reason")
                    continue
                anchor_path = resolve_stored_path(str(anchor.get("path")), evidence_root).resolve()
                if not anchor_path.is_file():
                    errors.append(f"{root_id}: source anchor path does not exist: {anchor.get('path')}")
        for field in (
            "upstream_causes", "downstream_symptoms", "sibling_risks",
            "must_preserve", "repair_induced_risks",
        ):
            values = cluster.get(field, [])
            if not isinstance(values, list) or not values or any(len(str(value).strip()) < 12 for value in values):
                errors.append(f"{root_id}: {field} requires concrete entries")
        dependent_artifacts = cluster.get("dependent_artifacts", [])
        if not isinstance(dependent_artifacts, list) or not dependent_artifacts:
            errors.append(f"{root_id}: dependent_artifacts cannot be empty")
        else:
            unknown_artifacts = sorted(set(map(str, dependent_artifacts)) - set(manifest.get("artifacts", {})))
            if unknown_artifacts:
                errors.append(f"{root_id}: dependent_artifacts are absent from the manifest: {', '.join(unknown_artifacts)}")
        layers = cluster.get("hard_gate_layers", {})
        for layer in HARD_GATE_LAYERS:
            row = layers.get(layer, {}) if isinstance(layers, dict) else {}
            if row.get("checked") is not True:
                errors.append(f"{root_id}: hard-gate layer {layer} was not checked")
            if not isinstance(row.get("timestamps"), list) or not row.get("timestamps"):
                errors.append(f"{root_id}: hard-gate layer {layer} needs timestamps")
            if len(str(row.get("observation", "")).strip()) < 20 or generic_observation(str(row.get("observation", ""))):
                errors.append(f"{root_id}: hard-gate layer {layer} needs concrete evidence")
            errors.extend(
                validate_review_evidence_samples(
                    row.get("evidence"), manifest, evidence_root, f"{root_id}: hard-gate layer {layer}", 1
                )
            )
        if cluster.get("coverage_complete") is not True:
            errors.append(f"{root_id}: cluster coverage must be complete")
        if not isinstance(cluster.get("coverage_gaps"), list):
            errors.append(f"{root_id}: coverage_gaps must be a list")
        if len(str(cluster.get("completeness_reason", "")).strip()) < 24:
            errors.append(f"{root_id}: completeness_reason is too short")
    if set(supplied_findings) != set(open_findings) or len(supplied_findings) != len(set(supplied_findings)):
        errors.append("review exhaustion must cluster every open finding exactly once")
    if len(supplied_roots) != len(set(supplied_roots)):
        errors.append("review exhaustion must use one cluster per root_issue_id")
    searches = {
        str(item.get("layer")): item
        for item in exhaustion.get("unclustered_searches", [])
        if isinstance(item, dict)
    }
    for layer in HARD_GATE_LAYERS:
        row = searches.get(layer, {})
        if row.get("performed") is not True:
            errors.append(f"review exhaustion missing unclustered search for {layer}")
        if len(str(row.get("query", "")).strip()) < 16 or len(str(row.get("result", "")).strip()) < 20:
            errors.append(f"review exhaustion search for {layer} is not concrete")
        errors.extend(
            validate_review_evidence_samples(
                row.get("evidence"), manifest, evidence_root, f"review exhaustion search for {layer}", 2
            )
        )
    if exhaustion.get("coverage_complete") is not True:
        errors.append("review exhaustion coverage_complete must be true")
    if len(str(exhaustion.get("reviewer_statement", "")).strip()) < 32:
        errors.append("review exhaustion requires a concrete reviewer completeness statement")
    if exhaustion.get("verdict") != "exhaustive_for_repair":
        errors.append("review exhaustion verdict must be exhaustive_for_repair")
    return errors


def validate_author_self_review_data(
    self_review: dict[str, Any],
    manifest: dict[str, Any],
    profile: dict[str, Any],
    plan: dict[str, Any],
    previous_review: dict[str, Any] | None = None,
    repair_contract: dict[str, Any] | None = None,
    repair_response: dict[str, Any] | None = None,
    repair_gate: dict[str, Any] | None = None,
    require_hash: bool = True,
    repo_root: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if self_review.get("schema") != "lecture-animation-author-self-review-v2":
        errors.append("author self-review schema must be lecture-animation-author-self-review-v2")
    if require_hash and not validate_hashed_record(self_review, "self_review_hash"):
        errors.append("author self-review hash is invalid")
    if self_review.get("manifest_hash") != manifest.get("manifest_hash"):
        errors.append("author self-review is bound to another frozen candidate")
    if self_review.get("scene_slug") != manifest.get("scene_slug"):
        errors.append("author self-review scene_slug does not match the manifest")
    owner = normalize_search_text(str(self_review.get("owner", "")))
    if not owner:
        errors.append("author self-review requires owner identity")
    if len(str(self_review.get("author_agent_id", "")).strip()) < 4:
        errors.append("author self-review requires author_agent_id")
    if len(str(self_review.get("author_model", "")).strip()) < 3:
        errors.append("author self-review requires author_model")
    try:
        if int(self_review.get("self_review_round", 0)) < 1:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("self_review_round must be a positive integer")

    if int(profile.get("autopilot_contract_version") or 0) >= 5:
        probe = self_review.get("falsification_probe")
        if not isinstance(probe, dict):
            errors.append("contract v5 author self-review requires a sealed falsification_probe")
        else:
            errors.extend(
                validate_self_review_probe_data(
                    probe, manifest, profile, plan, repo_root=repo_root
                )
            )
            if self_review.get("falsification_probe_hash") != probe.get("probe_hash"):
                errors.append("author self-review falsification_probe_hash is stale")

    continuous = self_review.get("continuous_playback", {})
    if not isinstance(continuous, dict) or continuous.get("performed") is not True or continuous.get("audio_monitored") is not True:
        errors.append("author self-review requires one continuous playback with audio monitored")
    elif len(str(continuous.get("observation", "")).strip()) < 24 or generic_observation(str(continuous.get("observation", ""))):
        errors.append("continuous playback requires concrete scene-specific observation")
    muted = self_review.get("muted_playback", {})
    if not isinstance(muted, dict) or muted.get("performed") is not True:
        errors.append("author self-review requires one muted playback")
    else:
        for field in ("teach_back", "prediction"):
            value = str(muted.get(field, "")).strip()
            if len(value) < 20 or generic_observation(value):
                errors.append(f"muted_playback.{field} requires concrete novice-visible evidence")

    duration = float(profile.get("context", {}).get("duration") or 0.0)
    errors.extend(validate_review_coverage_sweeps(self_review, plan, duration))
    failed_sweeps = [
        str(item.get("layer"))
        for item in self_review.get("coverage_sweeps", [])
        if isinstance(item, dict) and item.get("result") != "pass"
    ]
    if failed_sweeps:
        errors.append("author self-review cannot hand off with failed sweeps: " + ", ".join(failed_sweeps))

    required_artifact_keys = {"source", "timeline", "audio", "srt", "review_mp4", "qc", "telemetry", "authoring_qc"}
    if "scene_production" in manifest.get("artifacts", {}):
        required_artifact_keys.update({"scene_production", "scene_registry", "script", "word_srt", "word_alignment", "asr_transcript", "narration_qc"})
    artifact_checks = self_review.get("artifact_checks", [])
    artifact_map = {
        str(item.get("artifact_key")): item
        for item in artifact_checks
        if isinstance(item, dict) and item.get("artifact_key")
    } if isinstance(artifact_checks, list) else {}
    missing_artifacts = sorted(required_artifact_keys - set(artifact_map))
    if missing_artifacts:
        errors.append("author self-review missing artifact checks: " + ", ".join(missing_artifacts))
    for key in sorted(required_artifact_keys & set(artifact_map)):
        expected = str(manifest.get("artifacts", {}).get(key, {}).get("sha256", ""))
        if artifact_map[key].get("sha256") != expected:
            errors.append(f"author self-review artifact check {key!r} is stale")
        if len(str(artifact_map[key].get("observation", "")).strip()) < 12:
            errors.append(f"author self-review artifact check {key!r} requires a concrete observation")

    findings = self_review.get("findings", [])
    if not isinstance(findings, list):
        errors.append("author self-review findings must be a list")
        findings = []
    open_findings = [item for item in findings if isinstance(item, dict) and str(item.get("status", "open")) not in {"fixed", "closed"}]
    if open_findings:
        errors.append("author self-review cannot hand off with open findings")
    if self_review.get("verdict") != "ready_for_independent_review":
        errors.append("author self-review verdict must be ready_for_independent_review")

    try:
        policy = manifest_live_policy(manifest, (repo_root or Path.cwd()).resolve())
        if policy is not None:
            errors.extend(validate_pass_policy(policy))
    except PipelineError as exc:
        errors.append(f"cannot validate live-policy blockers during author self-review: {exc}")

    repair_context = self_review.get("repair_context", {})
    if previous_review is not None:
        if previous_review.get("schema") != "lecture-animation-review-v2" or previous_review.get("verdict") != "revise":
            errors.append("previous independent review must be a revise review")
        expected_previous_hash = object_hash(previous_review)
        if not isinstance(repair_context, dict) or repair_context.get("previous_review_hash") != expected_previous_hash:
            errors.append("repair self-review is not bound to the previous independent revise review")
        for field in ("repair_contract_hash", "repair_response_hash", "repair_gate_hash"):
            if not isinstance(repair_context, dict) or len(str(repair_context.get(field, "")).strip()) < 16:
                errors.append(f"repair self-review requires {field}")
        previous_findings = {
            str(item.get("finding_id"))
            for item in previous_review.get("findings", [])
            if isinstance(item, dict)
            and item.get("finding_id")
        }
        resolutions = {
            str(item.get("finding_id")): item
            for item in repair_context.get("resolutions", [])
            if isinstance(item, dict) and item.get("finding_id")
        } if isinstance(repair_context, dict) else {}
        if set(resolutions) != previous_findings:
            errors.append("repair self-review must resolve every previous open finding exactly once")
        for finding_id, resolution in resolutions.items():
            if len(str(resolution.get("change", "")).strip()) < 16:
                errors.append(f"repair resolution {finding_id!r} requires a concrete change")
            timestamps = resolution.get("evidence_timestamps", [])
            if not isinstance(timestamps, list) or not timestamps:
                errors.append(f"repair resolution {finding_id!r} requires timestamped evidence")
        supplied_bundle = (repair_contract, repair_response, repair_gate)
        if any(item is not None for item in supplied_bundle):
            if any(item is None for item in supplied_bundle):
                errors.append("repair contract, response, and gate must be supplied together")
            else:
                assert repair_contract is not None and repair_response is not None and repair_gate is not None
                if repair_contract.get("review_hash") != expected_previous_hash:
                    errors.append("repair contract is bound to another previous review")
                errors.extend(validate_repair_response_data(repair_response, repair_contract, manifest))
                errors.extend(validate_repair_gate_data(repair_gate, repair_response, repair_contract, manifest))
                if repair_context.get("repair_contract_hash") != repair_contract.get("contract_hash"):
                    errors.append("repair self-review contains a stale repair_contract_hash")
                if repair_context.get("repair_response_hash") != object_hash(repair_response):
                    errors.append("repair self-review contains a stale repair_response_hash")
                if repair_context.get("repair_gate_hash") != repair_gate.get("gate_hash"):
                    errors.append("repair self-review contains a stale repair_gate_hash")
    elif isinstance(repair_context, dict) and repair_context.get("previous_review_hash"):
        errors.append("initial self-review cannot claim an unverified previous review")
    return errors


def load_repair_bundle_for_self_review(
    args: argparse.Namespace, previous_review: dict[str, Any] | None, manifest: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    paths = (
        getattr(args, "repair_contract", None),
        getattr(args, "repair_response", None),
        getattr(args, "repair_gate", None),
    )
    if previous_review is None:
        if any(paths):
            raise PipelineError("initial self-review cannot supply a repair bundle")
        return None, None, None
    if not all(paths):
        raise PipelineError("repair self-review requires --repair-contract, --repair-response, and --repair-gate")
    contract, response, gate = (load_json(Path(value)) for value in paths)
    if contract.get("review_hash") != object_hash(previous_review):
        raise PipelineError("repair contract is bound to another previous review")
    errors = validate_repair_response_data(response, contract, manifest)
    errors.extend(validate_repair_gate_data(gate, response, contract, manifest))
    if errors:
        raise PipelineError("repair bundle failed: " + " | ".join(errors))
    return contract, response, gate


def verify_review_data(
    review: dict[str, Any],
    manifest: dict[str, Any],
    profile: dict[str, Any],
    repo_root: Path,
    event_log: Path | None,
) -> tuple[list[str], dict[str, Any]]:
    errors = verify_manifest_data(manifest, repo_root)
    if not validate_profile_hash(profile):
        errors.append("profile semantic hash is invalid")
    if manifest.get("profile_hash") != profile.get("profile_hash"):
        errors.append("review profile does not match manifest profile_hash")
    if review.get("schema") != "lecture-animation-review-v2":
        errors.append("review schema must be lecture-animation-review-v2")
    if review.get("manifest_hash") != manifest.get("manifest_hash"):
        errors.append("review manifest_hash does not match the frozen candidate")
    owner = normalize_search_text(str(review.get("owner", "")))
    reviewer = normalize_search_text(str(review.get("reviewer", "")))
    if not owner or not reviewer:
        errors.append("owner and reviewer identities are required")
    elif owner == reviewer:
        errors.append("reviewer must be independent from the animation owner")
    reviewer_model = str(review.get("reviewer_model", "")).strip()
    if not reviewer_model:
        errors.append("reviewer_model is required")
    try:
        if int(review.get("review_round", 0)) < 1:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("review_round must be a positive integer")

    novice = review.get("novice_pass", {})
    for field in ("summary", "visible_cause", "confusion", "eye_guidance", "teach_back", "prediction"):
        value = str(novice.get(field, "")).strip()
        if len(value) < 16 or generic_observation(value):
            errors.append(f"novice_pass.{field} needs concrete blind-review evidence")
    if novice.get("verdict") not in {"clear", "unclear"}:
        errors.append("novice_pass.verdict must be clear or unclear")
    confusion_time = novice.get("first_confusion_timestamp")
    if novice.get("verdict") == "clear" and confusion_time not in {None, ""}:
        errors.append("clear novice pass requires first_confusion_timestamp to be null")
    if novice.get("verdict") == "unclear":
        try:
            float(confusion_time)
        except (TypeError, ValueError):
            errors.append("unclear novice pass requires a numeric first_confusion_timestamp")
    if "repeat_rejected" in set(profile.get("tags", [])):
        for field in ("silent_teach_back", "silent_prediction"):
            value = str(novice.get(field, "")).strip()
            if len(value) < 20 or generic_observation(value):
                errors.append(f"novice_pass.{field} requires a concrete audio-muted comprehension probe")
        probes = novice.get("confusion_probes", [])
        if not isinstance(probes, list) or len(probes) < 3:
            errors.append("repeat-rejected review requires at least three timestamped confusion probes")
        else:
            probe_times: list[float] = []
            for probe in probes:
                if not isinstance(probe, dict):
                    errors.append("every confusion probe must be structured")
                    continue
                try:
                    probe_time = float(probe.get("timestamp_seconds"))
                except (TypeError, ValueError):
                    errors.append("confusion probe timestamp must be numeric")
                    continue
                probe_times.append(probe_time)
                if any(len(str(probe.get(key, "")).strip()) < 16 for key in ("candidate_confusion", "visible_anchor", "resolution_test")):
                    errors.append("confusion probe requires candidate_confusion, visible_anchor, and resolution_test")
            if len(set(round(value, 2) for value in probe_times)) < 3:
                errors.append("confusion probes must inspect three distinct timestamps")

    if "narration_qc" in manifest.get("artifacts", {}):
        narration_review = review.get("narration_review", {})
        try:
            narration_qc = load_json(
                resolve_stored_path(
                    str(manifest.get("artifacts", {}).get("narration_qc", {}).get("path", "")),
                    repo_root,
                )
            )
            if narration_review.get("narration_qc_hash") != narration_qc.get("narration_qc_hash"):
                errors.append("narration_review is not bound to the current narration_qc")
        except PipelineError as exc:
            errors.append(f"cannot load narration_qc for independent narration review: {exc}")
            narration_qc = {}
        for field in (
            "audio_only_teach_back",
            "likely_novice_confusion",
            "style_compliance_observation",
            "claim_responsibility_observation",
            "audio_quality_observation",
            "transcript_fidelity_observation",
            "timeline_alignment_observation",
        ):
            value = str(narration_review.get(field, "")).strip()
            if len(value) < 16 or generic_observation(value):
                errors.append(f"narration_review.{field} requires concrete independent evidence")
        for field in (
            "full_audio_playback",
            "novice_audio_only_reviewed",
            "style_contract_checked",
            "exact_transcript_checked",
            "reader_subtitles_checked",
            "word_alignment_checked",
            "timeline_duration_checked",
            "math_terms_checked",
        ):
            if narration_review.get(field) is not True:
                errors.append(f"narration_review.{field} must be true")
        if narration_review.get("novice_verdict") != "clear":
            errors.append("narration_review novice_verdict must be clear")
        if narration_review.get("verdict") != "pass":
            errors.append("narration_review verdict must be pass")
        try:
            if float(narration_review.get("max_anchor_drift_seconds", 999.0)) > 0.25:
                errors.append("independent narration review found anchor drift above 0.25 seconds")
        except (TypeError, ValueError):
            errors.append("narration_review requires numeric max_anchor_drift_seconds")

    if profile.get("autopilot_contract_version"):
        try:
            plan_entry = manifest.get("artifacts", {}).get("plan", {})
            plan = load_json(resolve_stored_path(str(plan_entry.get("path", "")), repo_root))
            duration = float(profile.get("context", {}).get("duration") or 0.0)
            errors.extend(validate_review_coverage_sweeps(review, plan, duration))
        except (PipelineError, TypeError, ValueError) as exc:
            errors.append(f"cannot validate four-layer review coverage: {exc}")

    artifacts = set(manifest.get("artifacts", {}))
    reviewer_rules = [rule for rule in profile.get("rules", []) if "reviewer" in rule.get("owners", [])]
    required_ids = {rule["rule_id"] for rule in reviewer_rules}
    checks = review.get("checks", [])
    if not isinstance(checks, list):
        checks = []
        errors.append("checks must be a list")
    check_map: dict[str, dict[str, Any]] = {}
    observations: list[str] = []
    for check in checks:
        rule_id = str(check.get("rule_id", ""))
        if rule_id in check_map:
            errors.append(f"duplicate rule check: {rule_id}")
        check_map[rule_id] = check
    missing_checks = sorted(required_ids - set(check_map))
    unknown_checks = sorted(set(check_map) - required_ids)
    if missing_checks:
        errors.append(f"review missing rule checks: {', '.join(missing_checks)}")
    if unknown_checks:
        errors.append(f"review contains non-applicable rule checks: {', '.join(unknown_checks)}")

    rule_by_id = {rule["rule_id"]: rule for rule in reviewer_rules}
    failed_checks: list[str] = []
    for rule_id in sorted(required_ids & set(check_map)):
        rule = rule_by_id[rule_id]
        check = check_map[rule_id]
        status = check.get("status")
        if status not in {"passed", "failed", "not_applicable"}:
            errors.append(f"{rule_id}: invalid status")
            continue
        if status == "failed":
            failed_checks.append(rule_id)
        if status == "not_applicable":
            if "always" in rule.get("applies_when", []):
                errors.append(f"{rule_id}: always-on rule cannot be not_applicable")
            if len(str(check.get("reason", "")).strip()) < 16:
                errors.append(f"{rule_id}: not_applicable requires a concrete reason")
            continue
        evidence = check.get("evidence", {})
        if not isinstance(evidence, dict):
            errors.append(f"{rule_id}: evidence must be an object")
            continue
        observation = str(evidence.get("observation", "")).strip()
        if len(observation) < 16 or generic_observation(observation):
            errors.append(f"{rule_id}: observation is generic or too short")
        else:
            observations.append(normalize_search_text(observation))
        artifact_key = str(evidence.get("artifact_key", ""))
        if artifact_key not in artifacts:
            errors.append(f"{rule_id}: evidence artifact_key is not in the manifest")
        for field in rule.get("evidence_fields", []):
            if evidence.get(field) in (None, "", []):
                errors.append(f"{rule_id}: evidence missing {field}")
        if rule.get("check_mode") in {"hybrid", "reviewer"}:
            try:
                timestamp = float(evidence.get("timestamp_seconds"))
                duration = float(profile.get("context", {}).get("duration") or 0.0)
                if timestamp < 0 or (duration and timestamp > duration + 0.5):
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f"{rule_id}: timestamp_seconds is outside the scene")

    if observations:
        unique_ratio = len(set(observations)) / len(observations)
        if len(observations) >= 5 and unique_ratio < 0.80:
            errors.append(f"review evidence is excessively duplicated ({unique_ratio:.0%} unique)")

    verdict = review.get("verdict")
    if verdict not in {"revise", "pass_for_user_review_pending"}:
        errors.append("verdict must be revise or pass_for_user_review_pending")
    findings = review.get("findings", [])
    if not isinstance(findings, list):
        errors.append("review findings must be a list")
        findings = []
    for finding in findings:
        if not isinstance(finding, dict):
            errors.append("every review finding must be a structured object")
        elif str(finding.get("status", "open")) != "open":
            errors.append("independent review findings must remain open; closure belongs in the repair response")
    open_findings = [item for item in findings if isinstance(item, dict)]
    if verdict == "revise":
        finding_ids = [str(item.get("finding_id", "")).strip() for item in open_findings if isinstance(item, dict)]
        if any(not value for value in finding_ids) or len(finding_ids) != len(set(finding_ids)):
            errors.append("every open review finding requires a unique finding_id")
        for finding in open_findings:
            if isinstance(finding, dict):
                errors.extend(validate_repair_guidance(finding, manifest))
        if int(profile.get("autopilot_contract_version") or 0) >= 5:
            exhaustion = review.get("review_exhaustion")
            if not isinstance(exhaustion, dict):
                errors.append("contract v5 revise review requires a sealed review_exhaustion record")
            else:
                errors.extend(
                    validate_review_exhaustion_data(
                        exhaustion, review, manifest, repo_root=repo_root
                    )
                )
    if verdict == "pass_for_user_review_pending":
        if novice.get("verdict") != "clear":
            errors.append("pass verdict requires novice_pass.verdict=clear")
        if failed_checks:
            errors.append(f"pass verdict contains failed checks: {', '.join(failed_checks)}")
        if open_findings:
            errors.append("pass verdict contains open findings")
        failed_sweeps = [
            str(item.get("layer"))
            for item in review.get("coverage_sweeps", [])
            if isinstance(item, dict) and item.get("result") == "fail"
        ]
        if failed_sweeps:
            errors.append("pass verdict contains failed coverage sweeps: " + ", ".join(failed_sweeps))
        try:
            policy = manifest_live_policy(manifest, repo_root)
            if policy is not None:
                errors.extend(validate_pass_policy(policy))
        except PipelineError as exc:
            errors.append(f"cannot validate live-policy blockers: {exc}")
    elif verdict == "revise" and not failed_checks and not open_findings:
        errors.append("revise verdict requires at least one failed check or open finding")

    health = reviewer_health(event_rows(event_log), reviewer_model) if event_log else reviewer_health([], reviewer_model)
    if verdict == "pass_for_user_review_pending" and health.get("anomalous"):
        calibration = review.get("calibration_recheck", {})
        trigger_ids = set(health.get("trigger_event_ids", []))
        supplied_ids = set(calibration.get("trigger_event_ids", [])) if isinstance(calibration, dict) else set()
        rules_rechecked = set(calibration.get("rules_rechecked", [])) if isinstance(calibration, dict) else set()
        timestamps = calibration.get("fresh_timestamps", []) if isinstance(calibration, dict) else []
        valid_times = set()
        for value in timestamps:
            try:
                valid_times.add(round(float(value), 3))
            except (TypeError, ValueError):
                pass
        if not (
            calibration.get("performed") is True
            and trigger_ids <= supplied_ids
            and len(rules_rechecked & required_ids) >= 3
            and len(valid_times) >= 3
            and calibration.get("result") in {"pass", "revise"}
        ):
            errors.append("reviewer history is anomalous; a complete calibration_recheck is required before pass")
    return errors, health


def command_index_history(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    records = build_history_records(repo_root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps({"records": len(records), "output": str(output)}, ensure_ascii=False))
    return 0


def command_search_history(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    if args.index:
        records = event_rows(Path(args.index))
    else:
        records = build_history_records(repo_root)
    record_types = set(args.types.split(",")) if args.types else None
    hits = search_history_records(records, args.query, limit=args.limit, record_types=record_types)
    if args.json:
        print(json.dumps({"query": args.query, "hits": hits}, ensure_ascii=False, indent=2))
    else:
        print(f"query: {args.query}\nhits: {len(hits)}")
        for index, hit in enumerate(hits, 1):
            marker = hit["trust_level"]
            print(f"\n{index}. [{hit['record_type']}] {hit['episode']} / {hit['scene_slug']} ({marker}, score={hit['score']})")
            print(f"   {hit['title']}")
            print(f"   paths: {', '.join(hit['source_paths'][:4])}")
            print(f"   review: {hit['review_status']} | risk: {hit['risk_tier']}")
            print(f"   match: {', '.join(hit['matched_terms'])}")
            print(f"   {hit['excerpt']}")
    return 0


def command_compile_profile(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    episode_dir = resolve_episode(repo_root, args.episode)
    profile = compile_profile_data(
        repo_root,
        episode_dir,
        args.scene_slug,
        explicit_tags=parse_explicit_tags(args.tags),
        regression_limit=args.regression_limit,
    )
    output = Path(args.output)
    policy_path = Path(args.live_policy_output) if getattr(args, "live_policy_output", None) else output.with_name("active_policy.json")
    policy = compile_live_policy_data(episode_dir, profile)
    write_json(policy_path, policy)
    profile = attach_autopilot_contract(profile, policy, policy_path, repo_root)
    write_json(output, profile)
    print(
        json.dumps(
            {
                "output": args.output,
                "profile_hash": profile["profile_hash"],
                "tags": profile["tags"],
                "rules": len(profile["rules"]),
                "regressions": len(profile["regressions"]),
                "regressions_omitted": profile["regressions_omitted_by_relevance_cap"],
                "live_policy": str(policy_path),
                "live_policy_hash": policy["policy_hash"],
                "mandatory_policy_entries": len(policy["entries"]),
                "mandatory_current_scene_patterns": len(policy["required_pattern_keys"]),
                "hard_gate_layers": profile["hard_gate_layers"],
                "precedents_withheld": True,
            },
            ensure_ascii=False,
        )
    )
    return 0


def command_seal_progressive_production(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    source = load_json(Path(args.input))
    sealed = seal_progressive_production_data(source, repo_root)
    episode = resolve_stored_path(str(sealed.get("episode", "")), repo_root)
    errors = validate_progressive_production_data(sealed, repo_root, episode)
    if errors:
        raise PipelineError("progressive production contract failed: " + " | ".join(errors))
    output = Path(args.output) if args.output else Path(args.input)
    write_json(output, sealed)
    print(json.dumps({"output": str(output), "production_hash": sealed["production_hash"]}, ensure_ascii=False))
    return 0


def command_init_progressive_production(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    episode = resolve_episode(repo_root, args.episode)
    timeline = load_json(episode / "timeline.json")
    segments_by_group: defaultdict[str, list[str]] = defaultdict(list)
    for segment in timeline.get("segments", []):
        if isinstance(segment, dict):
            segments_by_group[str(segment.get("scene_group", ""))].append(str(segment.get("narration", "")))
    scenes = []
    for group in timeline.get("scene_groups", []):
        if not isinstance(group, dict) or not group.get("scene_slug"):
            continue
        intent = str(group.get("role", "")).strip() or " ".join(segments_by_group[str(group.get("id", ""))]).strip()
        scenes.append(
            {
                "scene_slug": str(group["scene_slug"]),
                "state": "provisional",
                "narration_intent": intent,
                "artifacts": {},
            }
        )
    source = {
        "schema": "lecture-animation-progressive-production-v2",
        "episode": relative_or_absolute(episode, repo_root),
        "lecture_notes": {"path": args.lecture_notes},
        "narration_outline": {"path": args.narration_outline, "status": "outline_draft"},
        "storyboard": {"path": args.storyboard, "status": "coarse"},
        "scenes": scenes,
        "assembly": {"status": "pending", "artifacts": {}},
    }
    sealed = seal_progressive_production_data(source, repo_root)
    errors = validate_progressive_production_data(sealed, repo_root, episode)
    if errors:
        raise PipelineError("cannot initialize progressive production: " + " | ".join(errors))
    output = Path(args.output) if args.output else episode / "progressive_production.json"
    write_json(output, sealed)
    print(json.dumps({"output": str(output), "production_hash": sealed["production_hash"], "scenes": len(scenes)}, ensure_ascii=False))
    return 0


def command_seal_narration_qc(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    artifact_paths = {
        "script": resolve_stored_path(args.script, repo_root),
        "audio": resolve_stored_path(args.audio, repo_root),
        "reader_srt": resolve_stored_path(args.reader_srt, repo_root),
        "word_srt": resolve_stored_path(args.word_srt, repo_root),
        "word_alignment": resolve_stored_path(args.word_alignment, repo_root),
        "timeline_fragment": resolve_stored_path(args.timeline_fragment, repo_root),
        "asr_transcript": resolve_stored_path(args.asr_transcript, repo_root),
    }
    result = narration_qc_data(
        repo_root,
        args.scene_slug,
        resolve_stored_path(args.episode_spine, repo_root),
        artifact_paths,
        load_json(Path(args.review_draft)),
    )
    errors = validate_narration_qc_data(result, repo_root, args.scene_slug)
    if errors:
        raise PipelineError("narration QC failed: " + " | ".join(errors))
    write_json(Path(args.output), result)
    print(json.dumps({"output": args.output, "narration_qc_hash": result["narration_qc_hash"]}, ensure_ascii=False))
    return 0


def command_extract_scene_production(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    production = load_json(Path(args.production))
    episode = resolve_stored_path(str(production.get("episode", "")), repo_root)
    errors = validate_progressive_production_data(production, repo_root, episode)
    if errors:
        raise PipelineError("progressive production contract failed: " + " | ".join(errors))
    result = scene_production_contract_data(production, args.scene_slug)
    write_json(Path(args.output), result)
    print(json.dumps({"output": args.output, "scene_production_hash": result["scene_production_hash"]}, ensure_ascii=False))
    return 0


def command_compile_scene_registry(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    profile = load_json(Path(args.profile))
    plan = load_json(Path(args.plan))
    scene_production = load_json(Path(args.scene_production))
    scene_slug = str(profile.get("context", {}).get("scene_slug", ""))
    errors = [] if validate_profile_hash(profile) else ["profile hash is invalid"]
    errors.extend(validate_scene_plan_data(profile, plan))
    errors.extend(validate_scene_production_data(scene_production, repo_root, scene_slug))
    if errors:
        raise PipelineError("scene registry cannot compile: " + " | ".join(errors))
    result = scene_registry_data(profile, plan, scene_production)
    write_json(Path(args.output), result)
    print(json.dumps({"output": args.output, "registry_hash": result["registry_hash"]}, ensure_ascii=False))
    return 0


def command_prepare_review_workspace(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    episode = resolve_episode(repo_root, args.episode)
    root = episode / "review" / "v2" / args.scene_slug
    current = root / "current"
    for name in ("qc", "diagnostics"):
        (current / name).mkdir(parents=True, exist_ok=True)
    layout = {
        "schema": "lecture-animation-review-workspace-v2",
        "scene_slug": args.scene_slug,
        "current_root": relative_or_absolute(current, repo_root),
        "manifest": relative_or_absolute(current / "review_manifest.json", repo_root),
        "author_self_review": relative_or_absolute(current / "author_self_review.json", repo_root),
        "independent_review": relative_or_absolute(current / "independent_review.json", repo_root),
        "review_mp4": relative_or_absolute(current / "review.mp4", repo_root),
        "qc": relative_or_absolute(current / "qc", repo_root),
        "diagnostics": relative_or_absolute(current / "diagnostics", repo_root),
        "history_policy": "structured JSONL logs retain attempts; current derived media is replaced in place",
    }
    layout["workspace_hash"] = object_hash(layout)
    output = Path(args.output) if args.output else root / "workspace.json"
    write_json(output, layout)
    print(json.dumps(layout, ensure_ascii=False, indent=2))
    return 0


def command_compile_live_policy(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    episode_dir = resolve_episode(repo_root, args.episode)
    profile = load_json(Path(args.profile))
    if not validate_profile_hash(profile):
        raise PipelineError("compiled profile hash is invalid")
    policy = compile_live_policy_data(episode_dir, profile)
    write_json(Path(args.output), policy)
    print(
        json.dumps(
            {
                "output": args.output,
                "policy_hash": policy["policy_hash"],
                "entries": len(policy["entries"]),
                "required_pattern_keys": policy["required_pattern_keys"],
                "required_gate_layers": policy["required_gate_layers"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def command_begin_design(args: argparse.Namespace) -> int:
    profile = load_json(Path(args.profile))
    if not validate_profile_hash(profile):
        raise PipelineError("compiled profile hash is invalid")
    challenge = build_design_challenge(profile)
    write_json(Path(args.output), challenge)
    print(json.dumps({"output": args.output, "challenge_hash": challenge["challenge_hash"]}, ensure_ascii=False))
    return 0


def command_validate_design_deliberation(args: argparse.Namespace) -> int:
    profile = load_json(Path(args.profile))
    challenge = load_json(Path(args.challenge))
    deliberation = load_json(Path(args.deliberation))
    if not validate_profile_hash(profile):
        raise PipelineError("compiled profile hash is invalid")
    gate = validate_design_deliberation_data(profile, challenge, deliberation)
    write_json(Path(args.output), gate)
    print(json.dumps(gate, ensure_ascii=False, indent=2))
    return 0 if gate["valid"] else 2


def command_retrieve_design(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    profile = load_json(Path(args.profile))
    deliberation = load_json(Path(args.deliberation))
    gate = load_json(Path(args.design_gate))
    packet = build_precedent_packet(
        repo_root,
        profile,
        deliberation,
        gate,
        production_limit=args.production_limit,
        guidance_limit=args.guidance_limit,
    )
    write_json(Path(args.output), packet)
    print(
        json.dumps(
            {
                "output": args.output,
                "precedent_packet_hash": packet["precedent_packet_hash"],
                "production_hits": len(packet["production_hits"]),
                "guidance_hits": len(packet["guidance_hits"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


def command_validate_scene_plan(args: argparse.Namespace) -> int:
    profile = load_json(Path(args.profile))
    plan = load_json(Path(args.plan))
    challenge = load_json(Path(args.challenge))
    deliberation = load_json(Path(args.deliberation))
    gate = load_json(Path(args.design_gate))
    packet = load_json(Path(args.precedent_packet))
    errors: list[str] = []
    if not validate_profile_hash(profile):
        errors.append("compiled profile hash is invalid")
    errors.extend(validate_scene_plan_data(profile, plan))
    if int(profile.get("autopilot_contract_version") or 0) >= 2:
        spine = load_json(Path(args.episode_spine))
        batch_plan = load_json(Path(args.batch_plan))
        errors.extend(validate_scene_planning_chain(plan, spine, batch_plan))
    errors.extend(validate_design_chain_data(profile, plan, challenge, deliberation, gate, packet))
    result = {"valid": not errors, "errors": errors, "profile_hash": profile.get("profile_hash")}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


def command_validate_authoring_qc(args: argparse.Namespace) -> int:
    profile = load_json(Path(args.profile))
    plan = load_json(Path(args.plan))
    telemetry = load_json(Path(args.telemetry))
    plan_errors: list[str] = []
    if not validate_profile_hash(profile):
        plan_errors.append("compiled profile hash is invalid")
    plan_errors.extend(validate_scene_plan_data(profile, plan))
    if plan_errors:
        raise PipelineError("scene plan failed validation: " + " | ".join(plan_errors))
    report = validate_authoring_qc_data(profile, plan, telemetry)
    write_json(Path(args.output), report)
    print(
        json.dumps(
            {
                "valid": report["valid"],
                "output": args.output,
                "report_hash": report["report_hash"],
                "stats": report["stats"],
                "issues": report["issues"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["valid"] else 2


def parse_artifacts(raw_values: list[str]) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for raw in raw_values:
        if "=" not in raw:
            raise PipelineError(f"artifact must use key=path: {raw}")
        key, value = raw.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key or not value:
            raise PipelineError(f"artifact must use key=path: {raw}")
        if key in artifacts:
            raise PipelineError(f"duplicate artifact key: {key}")
        artifacts[key] = value
    return artifacts


def command_freeze_review(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    episode_dir = resolve_episode(repo_root, args.episode)
    raw_artifacts = parse_artifacts(args.artifact)
    raw_artifacts["profile"] = args.profile
    profile = load_json(resolve_stored_path(args.profile, repo_root))
    if not validate_profile_hash(profile):
        raise PipelineError("profile hash is invalid; recompile the profile")
    required_artifacts = set(REQUIRED_ARTIFACTS)
    progressive_path = episode_dir / "progressive_production.json"
    progressive_mode = progressive_path.exists()
    if progressive_mode:
        production = load_json(progressive_path)
        production_errors = validate_progressive_production_data(production, repo_root, episode_dir)
        if production_errors:
            raise PipelineError("progressive production tracker is invalid: " + " | ".join(production_errors))
        required_artifacts.update({"scene_production", "scene_registry", "script", "word_srt", "word_alignment", "asr_transcript", "narration_qc"})
        expected_output = episode_dir / "review" / "v2" / args.scene_slug / "current" / "review_manifest.json"
        if Path(args.output).resolve() != expected_output.resolve():
            raise PipelineError(f"progressive review manifests must use canonical current path: {expected_output}")
    if profile.get("autopilot_contract_version"):
        required_artifacts.add("live_policy")
        raw_artifacts.setdefault("live_policy", str(profile.get("live_policy_path", "")))
    if int(profile.get("autopilot_contract_version") or 0) >= 2:
        required_artifacts.update(PROGRESSIVE_PLANNING_ARTIFACTS)
    missing = sorted(required_artifacts - set(raw_artifacts))
    if missing:
        raise PipelineError(f"missing required artifacts: {', '.join(missing)}")
    if profile.get("context", {}).get("scene_slug") != args.scene_slug:
        raise PipelineError("profile scene_slug does not match freeze-review scene")
    if profile.get("autopilot_contract_version"):
        policy = load_json(resolve_stored_path(raw_artifacts["live_policy"], repo_root))
        current_policy = compile_live_policy_data(episode_dir, profile)
        if not validate_live_policy_hash(policy):
            raise PipelineError("live_policy hash is invalid")
        if policy.get("policy_hash") != profile.get("live_policy_hash"):
            raise PipelineError("live_policy does not match the compiled profile")
        if policy.get("policy_hash") != current_policy.get("policy_hash"):
            raise PipelineError("live_policy is stale; ingest human feedback and recompile the profile before repair")
    plan = load_json(resolve_stored_path(raw_artifacts["plan"], repo_root))
    plan_errors = validate_scene_plan_data(profile, plan)
    if int(profile.get("autopilot_contract_version") or 0) >= 2:
        spine = load_json(resolve_stored_path(raw_artifacts["episode_spine"], repo_root))
        batch_plan = load_json(resolve_stored_path(raw_artifacts["batch_plan"], repo_root))
        plan_errors.extend(validate_episode_spine_data(spine, repo_root, episode_dir))
        batch_scenes = [
            str(item.get("scene_slug", ""))
            for item in batch_plan.get("scenes", [])
            if isinstance(item, dict)
        ]
        plan_errors.extend(
            validate_batch_visual_plan_data(
                batch_plan,
                spine,
                str(batch_plan.get("batch_id", "")),
                batch_scenes,
            )
        )
        plan_errors.extend(validate_scene_planning_chain(plan, spine, batch_plan))
    challenge = load_json(resolve_stored_path(raw_artifacts["design_challenge"], repo_root))
    deliberation = load_json(resolve_stored_path(raw_artifacts["deliberation"], repo_root))
    design_gate = load_json(resolve_stored_path(raw_artifacts["design_gate"], repo_root))
    precedent_packet = load_json(resolve_stored_path(raw_artifacts["precedent_packet"], repo_root))
    plan_errors.extend(
        validate_design_chain_data(profile, plan, challenge, deliberation, design_gate, precedent_packet)
    )
    if plan_errors:
        raise PipelineError("scene plan failed validation: " + " | ".join(plan_errors))
    telemetry = load_json(resolve_stored_path(raw_artifacts["telemetry"], repo_root))
    stored_report = load_json(resolve_stored_path(raw_artifacts["authoring_qc"], repo_root))
    fresh_report = validate_authoring_qc_data(profile, plan, telemetry)
    if not validate_authoring_qc_report_hash(stored_report):
        raise PipelineError("authoring_qc report hash is invalid")
    if stored_report.get("report_hash") != fresh_report.get("report_hash"):
        raise PipelineError("authoring_qc report is stale; rerun validate-authoring-qc")
    if progressive_mode:
        scene_production = load_json(resolve_stored_path(raw_artifacts["scene_production"], repo_root))
        production_errors = validate_scene_production_data(scene_production, repo_root, args.scene_slug)
        if production_errors:
            raise PipelineError("scene production contract failed: " + " | ".join(production_errors))
        registry = load_json(resolve_stored_path(raw_artifacts["scene_registry"], repo_root))
        expected_registry = scene_registry_data(profile, plan, scene_production)
        if registry.get("registry_hash") != expected_registry.get("registry_hash") or not validate_hashed_record(registry, "registry_hash"):
            raise PipelineError("scene registry is stale; recompile it from the current plan and scene production contract")
        if telemetry.get("scene_registry_hash") != registry.get("registry_hash"):
            raise PipelineError("runtime telemetry must export the exact compiled scene_registry_hash")
        exact_mapping = {
            "script": "script",
            "audio": "audio",
            "srt": "reader_srt",
            "word_srt": "word_srt",
            "word_alignment": "word_alignment",
            "timeline": "timeline_fragment",
            "asr_transcript": "asr_transcript",
            "narration_qc": "narration_qc",
        }
        for artifact_key, production_key in exact_mapping.items():
            actual = artifact_snapshot(resolve_stored_path(raw_artifacts[artifact_key], repo_root), repo_root)
            expected_sha = scene_production.get("artifacts", {}).get(production_key, {}).get("sha256")
            if actual.get("sha256") != expected_sha:
                raise PipelineError(f"{artifact_key} does not match the exact scene production contract")
    if not fresh_report.get("valid"):
        codes = ", ".join(str(item.get("code")) for item in fresh_report.get("issues", [])[:8])
        raise PipelineError("authoring_qc failed: " + codes)
    text_baseline = load_json(resolve_stored_path(raw_artifacts["text_inventory_baseline"], repo_root))
    text_audit = load_json(resolve_stored_path(raw_artifacts["text_inventory_audit"], repo_root))
    baseline_payload = dict(text_baseline)
    baseline_hash = baseline_payload.pop("baseline_hash", None)
    audit_payload = dict(text_audit)
    audit_hash = audit_payload.pop("report_hash", None)
    source_snapshot = artifact_snapshot(resolve_stored_path(raw_artifacts["source"], repo_root), repo_root)
    if (
        text_baseline.get("schema") != "lecture-animation-screen-text-baseline-v1"
        or not baseline_hash
        or baseline_hash != object_hash(baseline_payload)
    ):
        raise PipelineError("text_inventory_baseline is invalid")
    if (
        text_audit.get("schema") != "lecture-animation-screen-text-audit-v1"
        or not audit_hash
        or audit_hash != object_hash(audit_payload)
        or not text_audit.get("valid")
    ):
        raise PipelineError("text_inventory_audit is invalid or failed")
    if text_audit.get("scene_slug") != args.scene_slug or text_audit.get("baseline_hash") != baseline_hash:
        raise PipelineError("text_inventory_audit is bound to a different scene or baseline")
    if text_audit.get("candidate_source_sha256") != source_snapshot.get("sha256"):
        raise PipelineError("text_inventory_audit is stale; source changed after exact text verification")
    if "FORM-004" in {str(rule.get("rule_id")) for rule in profile.get("rules", [])}:
        frame_report = load_json(resolve_stored_path(raw_artifacts["emphasis_frame_audit"], repo_root))
        if frame_report.get("schema") != "lecture-animation-emphasis-frame-audit-v2" or not frame_report.get("valid"):
            raise PipelineError("FORM-004 emphasis_frame_audit is missing, invalid, or failed")
    if profile.get("autopilot_contract_version"):
        layout_report = load_json(resolve_stored_path(raw_artifacts["layout_audit"], repo_root))
        layout_errors = validate_layout_audit_data(layout_report, args.scene_slug)
        if layout_errors:
            raise PipelineError("layout_audit failed: " + " | ".join(layout_errors))
    snapshots = {
        key: artifact_snapshot(resolve_stored_path(value, repo_root), repo_root)
        for key, value in sorted(raw_artifacts.items())
    }
    manifest: dict[str, Any] = {
        "schema": "lecture-animation-review-manifest-v2",
        "created_at": utc_now(),
        "episode": relative_or_absolute(episode_dir, repo_root),
        "scene_slug": args.scene_slug,
        "profile_hash": profile["profile_hash"],
        "artifacts": snapshots,
    }
    manifest["manifest_hash"] = object_hash(manifest)
    write_json(Path(args.output), manifest)
    print(json.dumps({"output": args.output, "manifest_hash": manifest["manifest_hash"], "artifacts": len(snapshots)}, ensure_ascii=False))
    return 0


def command_verify_manifest(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    manifest = load_json(Path(args.manifest))
    errors = verify_manifest_data(manifest, repo_root)
    print(json.dumps({"valid": not errors, "errors": errors, "manifest_hash": manifest.get("manifest_hash")}, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


def command_prepare_self_review_probe(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    manifest = load_json(Path(args.manifest))
    manifest_errors = verify_manifest_data(manifest, repo_root)
    if manifest_errors:
        raise PipelineError("cannot prepare a probe for a stale manifest: " + " | ".join(manifest_errors))
    profile = load_json(
        resolve_stored_path(str(manifest.get("artifacts", {}).get("profile", {}).get("path", "")), repo_root)
    )
    plan = load_json(
        resolve_stored_path(str(manifest.get("artifacts", {}).get("plan", {}).get("path", "")), repo_root)
    )
    probe = self_review_probe_draft_data(manifest, profile, plan)
    write_json(Path(args.output), probe)
    print(
        json.dumps(
            {
                "self_review_probe_draft": args.output,
                "probes": len(probe["probes"]),
                "minimum_per_layer": probe["minimum_probes_per_layer"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def command_seal_self_review_probe(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    manifest = load_json(Path(args.manifest))
    profile = load_json(
        resolve_stored_path(str(manifest.get("artifacts", {}).get("profile", {}).get("path", "")), repo_root)
    )
    plan = load_json(
        resolve_stored_path(str(manifest.get("artifacts", {}).get("plan", {}).get("path", "")), repo_root)
    )
    probe = load_json(Path(args.input))
    probe.pop("probe_hash", None)
    errors = validate_self_review_probe_data(
        probe, manifest, profile, plan, require_hash=False, repo_root=repo_root
    )
    if errors:
        raise PipelineError("self-review falsification probe failed: " + " | ".join(errors))
    probe["created_at"] = utc_now()
    probe["probe_hash"] = object_hash(probe)
    output = Path(args.output) if args.output else Path(args.input)
    write_json(output, probe)
    print(json.dumps({"self_review_probe": str(output), "probe_hash": probe["probe_hash"]}, ensure_ascii=False))
    return 0


def command_prepare_review_exhaustion(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    review = load_json(Path(args.review))
    manifest = load_json(Path(args.manifest))
    manifest_errors = verify_manifest_data(manifest, repo_root)
    if manifest_errors:
        raise PipelineError("cannot prepare exhaustion for a stale manifest: " + " | ".join(manifest_errors))
    exhaustion = review_exhaustion_draft_data(review, manifest)
    write_json(Path(args.output), exhaustion)
    print(
        json.dumps(
            {
                "review_exhaustion_draft": args.output,
                "clusters": len(exhaustion["clusters"]),
                "findings": sum(len(item["finding_ids"]) for item in exhaustion["clusters"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


def command_seal_review_exhaustion(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    review = load_json(Path(args.review))
    manifest = load_json(Path(args.manifest))
    exhaustion = load_json(Path(args.input))
    exhaustion.pop("exhaustion_hash", None)
    errors = validate_review_exhaustion_data(
        exhaustion, review, manifest, require_hash=False, repo_root=repo_root
    )
    if errors:
        raise PipelineError("review exhaustion failed: " + " | ".join(errors))
    exhaustion["created_at"] = utc_now()
    exhaustion["exhaustion_hash"] = object_hash(exhaustion)
    output = Path(args.output) if args.output else Path(args.input)
    write_json(output, exhaustion)
    print(json.dumps({"review_exhaustion": str(output), "exhaustion_hash": exhaustion["exhaustion_hash"]}, ensure_ascii=False))
    return 0


def command_prepare_author_self_review(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    manifest = load_json(Path(args.manifest))
    manifest_errors = verify_manifest_data(manifest, repo_root)
    if manifest_errors:
        raise PipelineError("cannot prepare self-review for a stale manifest: " + " | ".join(manifest_errors))
    profile = load_json(
        resolve_stored_path(str(manifest.get("artifacts", {}).get("profile", {}).get("path", "")), repo_root)
    )
    plan = load_json(
        resolve_stored_path(str(manifest.get("artifacts", {}).get("plan", {}).get("path", "")), repo_root)
    )
    duration = float(profile.get("context", {}).get("duration") or 0.0)
    object_ids = planned_object_ids(plan)
    probe_path = getattr(args, "self_review_probe", None)
    if int(profile.get("autopilot_contract_version") or 0) >= 5 and not probe_path:
        raise PipelineError("contract v5 prepare-author-self-review requires --self-review-probe")
    probe = load_json(Path(probe_path)) if probe_path else None
    if probe is not None:
        probe_errors = validate_self_review_probe_data(
            probe, manifest, profile, plan, repo_root=repo_root
        )
        if probe_errors:
            raise PipelineError("sealed self-review probe failed: " + " | ".join(probe_errors))
    previous_review = load_json(Path(args.previous_review)) if args.previous_review else None
    repair_contract, repair_response, repair_gate = load_repair_bundle_for_self_review(
        args, previous_review, manifest
    )
    resolutions = []
    if previous_review is not None:
        if previous_review.get("schema") != "lecture-animation-review-v2" or previous_review.get("verdict") != "revise":
            raise PipelineError("--previous-review must be an independent revise review")
        response_map = {
            str(item.get("finding_id")): item
            for item in (repair_response or {}).get("resolutions", [])
            if isinstance(item, dict)
        }
        for finding in previous_review.get("findings", []):
            if not isinstance(finding, dict):
                continue
            finding_id = str(finding.get("finding_id"))
            response_row = response_map.get(finding_id, {})
            changes = response_row.get("code_changes", [])
            resolutions.append(
                {
                    "finding_id": finding_id,
                    "change": " | ".join(
                        f"{item.get('path')}:{item.get('symbol')} {item.get('change')}"
                        for item in changes if isinstance(item, dict)
                    ),
                    "evidence_timestamps": [finding.get("timestamp_seconds")],
                    "root_issue_id": response_row.get("root_issue_id"),
                    "lineage_classification": response_row.get("lineage_classification"),
                }
            )
    required_artifact_keys = ["source", "timeline", "audio", "srt", "review_mp4", "qc", "telemetry", "authoring_qc"]
    if "scene_production" in manifest.get("artifacts", {}):
        required_artifact_keys.extend(["scene_production", "scene_registry", "script", "word_srt", "word_alignment", "asr_transcript", "narration_qc"])
    draft = {
        "schema": "lecture-animation-author-self-review-v2",
        "manifest_hash": manifest.get("manifest_hash"),
        "scene_slug": manifest.get("scene_slug"),
        "owner": args.owner,
        "author_agent_id": args.author_agent_id,
        "author_model": args.author_model,
        "self_review_round": args.self_review_round,
        "falsification_probe_hash": probe.get("probe_hash") if probe else None,
        "falsification_probe": probe,
        "continuous_playback": {"performed": False, "audio_monitored": False, "observation": ""},
        "muted_playback": {"performed": False, "teach_back": "", "prediction": ""},
        "coverage_sweeps": [
            {
                "layer": layer,
                "result": "fail",
                "timestamps": timestamps,
                "object_ids": object_ids,
                "observation": "",
            }
            for layer, timestamps in review_coverage_anchors(plan, duration).items()
        ],
        "artifact_checks": [
            {
                "artifact_key": key,
                "sha256": manifest.get("artifacts", {}).get(key, {}).get("sha256"),
                "observation": "",
            }
            for key in required_artifact_keys
        ],
        "findings": [],
        "repair_context": {
            "previous_review_hash": object_hash(previous_review) if previous_review else None,
            "repair_contract_hash": repair_contract.get("contract_hash") if repair_contract else None,
            "repair_response_hash": object_hash(repair_response) if repair_response else None,
            "repair_gate_hash": repair_gate.get("gate_hash") if repair_gate else None,
            "resolutions": resolutions,
        },
        "verdict": "draft",
    }
    write_json(Path(args.output), draft)
    print(
        json.dumps(
            {
                "author_self_review_draft": args.output,
                "manifest_hash": manifest.get("manifest_hash"),
                "coverage_anchors": sum(len(item["timestamps"]) for item in draft["coverage_sweeps"]),
                "prior_findings": len(resolutions),
            },
            ensure_ascii=False,
        )
    )
    return 0


def command_seal_author_self_review(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    manifest = load_json(Path(args.manifest))
    manifest_errors = verify_manifest_data(manifest, repo_root)
    if manifest_errors:
        raise PipelineError("cannot self-review a stale manifest: " + " | ".join(manifest_errors))
    profile = load_json(
        resolve_stored_path(str(manifest.get("artifacts", {}).get("profile", {}).get("path", "")), repo_root)
    )
    plan = load_json(
        resolve_stored_path(str(manifest.get("artifacts", {}).get("plan", {}).get("path", "")), repo_root)
    )
    draft = load_json(Path(args.input))
    draft.pop("self_review_hash", None)
    previous_review = load_json(Path(args.previous_review)) if args.previous_review else None
    repair_contract, repair_response, repair_gate = load_repair_bundle_for_self_review(
        args, previous_review, manifest
    )
    errors = validate_author_self_review_data(
        draft,
        manifest,
        profile,
        plan,
        previous_review=previous_review,
        repair_contract=repair_contract,
        repair_response=repair_response,
        repair_gate=repair_gate,
        require_hash=False,
        repo_root=repo_root,
    )
    episode = resolve_stored_path(str(manifest.get("episode", "")), repo_root)
    attempt_log = (
        Path(args.attempt_log)
        if args.attempt_log
        else episode / "review" / "evolution" / "author_self_review_attempts.jsonl"
    )
    previous_review_hash = object_hash(previous_review) if previous_review else None
    draft_hash = object_hash(draft)
    verification_key = object_hash(
        {
            "manifest_hash": manifest.get("manifest_hash"),
            "draft_hash": draft_hash,
            "previous_review_hash": previous_review_hash,
        }
    )
    attempt = {
        "schema": "lecture-animation-author-self-review-attempt-v2",
        "attempt_id": f"author-self-review:{hashlib.sha1(verification_key.encode()).hexdigest()[:16]}",
        "created_at": utc_now(),
        "scene_slug": manifest.get("scene_slug"),
        "manifest_hash": manifest.get("manifest_hash"),
        "owner": draft.get("owner"),
        "author_model": draft.get("author_model"),
        "author_agent_id": draft.get("author_agent_id"),
        "self_review_round": draft.get("self_review_round"),
        "previous_review_hash": previous_review_hash,
        "repair_contract_hash": repair_contract.get("contract_hash") if repair_contract else None,
        "repair_response_hash": object_hash(repair_response) if repair_response else None,
        "repair_gate_hash": repair_gate.get("gate_hash") if repair_gate else None,
        "draft_hash": draft_hash,
        "findings_caught_before_handoff": len(draft.get("findings", [])),
        "machine_gate_findings": len(errors),
        "gate_errors": errors,
        "gate_accepted": not errors,
        "verdict": draft.get("verdict") if not errors else "self_review_revise",
        "verification_key": verification_key,
    }
    stored_attempt, appended = append_unique_jsonl(
        attempt_log,
        attempt,
        key_field="verification_key",
    )
    existing = None if appended else stored_attempt
    if errors:
        print(
            json.dumps(
                {
                    "valid": False,
                    "errors": errors,
                    "attempt_log": str(attempt_log),
                    "deduplicated": existing is not None,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    sealed = dict(draft)
    sealed["created_at"] = utc_now()
    sealed["self_review_hash"] = object_hash(sealed)
    output = Path(args.output)
    write_json(output, sealed)
    print(
        json.dumps(
            {
                "author_self_review": str(output),
                "self_review_hash": sealed["self_review_hash"],
                "attempt_log": str(attempt_log),
                "deduplicated": existing is not None,
            },
            ensure_ascii=False,
        )
    )
    return 0


def command_prepare_review_capsule(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    manifest = load_json(Path(args.manifest))
    errors = verify_manifest_data(manifest, repo_root)
    if errors:
        raise PipelineError("cannot compile capsule from stale manifest: " + " | ".join(errors))
    profile = load_json(
        resolve_stored_path(str(manifest.get("artifacts", {}).get("profile", {}).get("path", "")), repo_root)
    )
    plan = load_json(
        resolve_stored_path(str(manifest.get("artifacts", {}).get("plan", {}).get("path", "")), repo_root)
    )
    self_review = load_json(Path(args.author_self_review))
    previous_review_path = getattr(args, "previous_review", None)
    previous_review = load_json(Path(previous_review_path)) if previous_review_path else None
    repair_contract, repair_response, repair_gate = load_repair_bundle_for_self_review(
        args, previous_review, manifest
    )
    self_review_errors = validate_author_self_review_data(
        self_review,
        manifest,
        profile,
        plan,
        previous_review=previous_review,
        repair_contract=repair_contract,
        repair_response=repair_response,
        repair_gate=repair_gate,
        repo_root=repo_root,
    )
    if self_review_errors:
        raise PipelineError("independent review is blocked by author self-review: " + " | ".join(self_review_errors))
    session = load_review_session(Path(args.review_session))
    if normalize_search_text(str(self_review.get("owner", ""))) != normalize_search_text(str(session.get("owner", ""))):
        raise PipelineError("author self-review owner does not match the review-session owner")
    if str(self_review.get("author_agent_id", "")).strip() != str(session.get("author_agent_id", "")).strip():
        raise PipelineError("author self-review agent does not match the review-session author agent")
    if str(self_review.get("author_agent_id", "")).strip() == str(session.get("reviewer_agent_id", "")).strip():
        raise PipelineError("review session is not independent from the author agent")
    capsule = review_capsule_data(manifest, profile, plan, session, self_review)
    write_json(Path(args.output), capsule)
    print(
        json.dumps(
            {
                "review_capsule": args.output,
                "capsule_hash": capsule["capsule_hash"],
                "rules": len(capsule["required_rules"]),
                "objects": len(capsule["required_object_ids"]),
                "blind_challenges": len(capsule["blind_challenges"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


def command_seal_blind_review(args: argparse.Namespace) -> int:
    session = load_review_session(Path(args.review_session))
    receipt = blind_review_receipt_data(load_json(Path(args.capsule)), load_json(Path(args.blind_review)), session)
    write_json(Path(args.output), receipt)
    print(json.dumps({"blind_receipt": args.output, "receipt_hash": receipt["receipt_hash"]}, ensure_ascii=False))
    return 0


def command_seal_change_impact(args: argparse.Namespace) -> int:
    previous = load_json(Path(args.previous_manifest))
    current = load_json(Path(args.current_manifest))
    impact = load_json(Path(args.input))
    impact["schema"] = "lecture-animation-change-impact-v2"
    impact["previous_manifest_hash"] = previous.get("manifest_hash")
    impact["current_manifest_hash"] = current.get("manifest_hash")
    impact["changed_artifacts"] = changed_manifest_artifacts(previous, current)
    impact.pop("impact_hash", None)
    impact["impact_hash"] = object_hash(impact)
    errors = validate_change_impact_data(impact, previous, current)
    if errors:
        raise PipelineError("change impact failed: " + " | ".join(errors))
    output = Path(args.output) if args.output else Path(args.input)
    write_json(output, impact)
    print(json.dumps({"change_impact": str(output), "impact_hash": impact["impact_hash"]}, ensure_ascii=False))
    return 0


def command_compile_repair_contract(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    review = load_json(Path(args.review))
    manifest = load_json(Path(args.manifest))
    contract = repair_contract_data(review, manifest)
    errors = validate_repair_contract_data(contract, review, manifest, repo_root=repo_root)
    if errors:
        raise PipelineError("repair contract failed: " + " | ".join(errors))
    write_json(Path(args.output), contract)
    print(
        json.dumps(
            {
                "repair_contract": args.output,
                "contract_hash": contract["contract_hash"],
                "findings": len(contract["findings"]),
                "lineage_counts": contract["lineage_counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_prepare_repair_response(args: argparse.Namespace) -> int:
    contract = load_json(Path(args.repair_contract))
    current_manifest = load_json(Path(args.current_manifest))
    if contract.get("schema") != "lecture-animation-repair-contract-v2" or not validate_hashed_record(contract, "contract_hash"):
        raise PipelineError("repair contract is invalid or stale")
    response = repair_response_draft_data(contract, current_manifest)
    write_json(Path(args.output), response)
    print(
        json.dumps(
            {
                "repair_response_draft": args.output,
                "findings": len(response["resolutions"]),
                "actual_changed_artifacts": response["actual_changed_artifacts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_verify_repair_response(args: argparse.Namespace) -> int:
    contract = load_json(Path(args.repair_contract))
    response = load_json(Path(args.repair_response))
    current_manifest = load_json(Path(args.current_manifest))
    gate = repair_gate_data(response, contract, current_manifest)
    write_json(Path(args.output), gate)
    attempt_log = Path(args.attempt_log) if args.attempt_log else Path(args.output).parent / "repair_attempts.jsonl"
    verification_key = object_hash(
        {
            "repair_contract_hash": contract.get("contract_hash"),
            "repair_response_hash": object_hash(response),
            "current_manifest_hash": current_manifest.get("manifest_hash"),
            "errors": gate["errors"],
        }
    )
    attempt = {
        "schema": "lecture-animation-repair-attempt-v2",
        "attempt_id": f"repair:{hashlib.sha1(verification_key.encode()).hexdigest()[:16]}",
        "created_at": utc_now(),
        "scene_slug": current_manifest.get("scene_slug"),
        "baseline_manifest_hash": contract.get("baseline_manifest_hash"),
        "current_manifest_hash": current_manifest.get("manifest_hash"),
        "repair_contract_hash": contract.get("contract_hash"),
        "repair_response_hash": object_hash(response),
        "gate_hash": gate.get("gate_hash"),
        "gate_accepted": gate.get("valid"),
        "findings_resolved": gate.get("findings_resolved"),
        "lineage_counts": gate.get("lineage_counts"),
        "changed_artifacts": gate.get("changed_artifacts"),
        "gate_errors": gate.get("errors"),
        "verification_key": verification_key,
    }
    stored_attempt, appended = append_unique_jsonl(
        attempt_log,
        attempt,
        key_field="verification_key",
    )
    existing = None if appended else stored_attempt
    print(
        json.dumps(
            {
                "valid": gate["valid"],
                "repair_gate": args.output,
                "gate_hash": gate["gate_hash"],
                "errors": gate["errors"],
                "attempt_log": str(attempt_log),
                "attempt_id": (existing or attempt)["attempt_id"],
                "deduplicated": existing is not None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if gate["valid"] else 2


def command_verify_review(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    manifest = load_json(Path(args.manifest))
    review = load_json(Path(args.review))
    profile_entry = manifest.get("artifacts", {}).get("profile", {})
    profile_path = resolve_stored_path(str(profile_entry.get("path", "")), repo_root)
    profile = load_json(profile_path)
    plan = load_json(
        resolve_stored_path(str(manifest.get("artifacts", {}).get("plan", {}).get("path", "")), repo_root)
    )
    author_self_review = load_json(Path(args.author_self_review))
    previous_review_path = getattr(args, "previous_review", None)
    previous_review = load_json(Path(previous_review_path)) if previous_review_path else None
    repair_contract, repair_response, repair_gate = load_repair_bundle_for_self_review(
        args, previous_review, manifest
    )
    episode = resolve_stored_path(str(manifest.get("episode", "")), repo_root)
    session_path = Path(args.review_session)
    session = load_review_session(session_path)
    event_log = Path(args.event_log) if args.event_log else episode / "review" / "evolution" / "events.jsonl"
    errors, health = verify_review_data(review, manifest, profile, repo_root, event_log)
    errors.extend(
        validate_author_self_review_data(
            author_self_review,
            manifest,
            profile,
            plan,
            previous_review=previous_review,
            repair_contract=repair_contract,
            repair_response=repair_response,
            repair_gate=repair_gate,
            repo_root=repo_root,
        )
    )
    if normalize_search_text(str(author_self_review.get("owner", ""))) != normalize_search_text(str(review.get("owner", ""))):
        errors.append("independent review owner does not match the sealed author self-review owner")
    author_agent_id = str(author_self_review.get("author_agent_id", "")).strip()
    reviewer_agent_id = str(review.get("reviewer_agent_id", "")).strip()
    if author_agent_id != str(session.get("author_agent_id", "")).strip():
        errors.append("author_agent_id does not match the persistent review session")
    if author_agent_id and author_agent_id == reviewer_agent_id:
        errors.append("reviewer_agent_id must differ from the sealed author_agent_id")
    errors.extend(validate_session_reviewer(session, review))
    errors.extend(
        validate_session_governance(
            session,
            manifest,
            repo_root,
            str(review.get("verdict", "")),
        )
    )
    errors.extend(
        validate_pending_repair_binding(
            session,
            str(manifest.get("scene_slug", "")),
            author_self_review,
            str(review.get("verdict", "")),
        )
    )
    if session.get("capsule_required"):
        capsule_path = getattr(args, "review_capsule", None)
        receipt_path = getattr(args, "blind_receipt", None)
        if not capsule_path or not receipt_path:
            errors.append("review capsule and sealed blind receipt are required by this review session")
        else:
            errors.extend(
                validate_review_capsule_chain(
                    review,
                    load_json(Path(capsule_path)),
                    load_json(Path(receipt_path)),
                    manifest,
                    session,
                    author_self_review,
                )
            )
    if review.get("verdict") == "pass_for_user_review_pending" and session.get("calibration_due"):
        if review.get("calibration_recheck", {}).get("performed") is not True:
            errors.append("review session requires a fresh calibration_recheck before another pass")
    explicit_attempt_log = getattr(args, "attempt_log", None) or getattr(args, "audit_log", None)
    audit_log = Path(explicit_attempt_log) if explicit_attempt_log else episode / "review" / "evolution" / "review_attempts.jsonl"
    failed_checks = [check for check in review.get("checks", []) if check.get("status") == "failed"]
    submission_hash = object_hash(review)
    verification_key = object_hash(
        {
            "manifest_hash": manifest.get("manifest_hash"),
            "submission_hash": submission_hash,
            "review_session_id": session.get("session_id"),
            "gate_errors": errors,
        }
    )
    attempt_seed = verification_key
    attempt = {
        "schema": "lecture-animation-review-attempt-v2",
        "attempt_id": f"review:{hashlib.sha1(attempt_seed.encode('utf-8')).hexdigest()[:16]}",
        "created_at": utc_now(),
        "episode": episode.name,
        "scene_slug": manifest.get("scene_slug"),
        "manifest_hash": manifest.get("manifest_hash"),
        "reviewer": review.get("reviewer"),
        "reviewer_model": review.get("reviewer_model"),
        "reasoning_effort": review.get("reasoning_effort"),
        "reviewer_tier": session.get("reviewer_tier", "legacy"),
        "review_round": review.get("review_round"),
        "verdict": review.get("verdict"),
        "gate_accepted": not errors,
        "gate_errors": errors,
        "findings_count": len(review.get("findings", [])),
        "finding_lineage_counts": finding_lineage_counts(review.get("findings", [])),
        "failed_checks_count": len(failed_checks),
        "calibration_recheck": bool(review.get("calibration_recheck", {}).get("performed")),
        "review_session_id": session.get("session_id"),
        "reviewer_agent_id": session.get("reviewer_agent_id"),
        "review_mode": "full_regression",
        "repair_contract_hash": author_self_review.get("repair_context", {}).get("repair_contract_hash"),
        "repair_response_hash": author_self_review.get("repair_context", {}).get("repair_response_hash"),
        "repair_gate_hash": author_self_review.get("repair_context", {}).get("repair_gate_hash"),
        "submission_hash": submission_hash,
        "verification_key": verification_key,
    }
    stored_attempt, appended, session = commit_review_attempt(
        session_path=session_path,
        attempt_log=audit_log,
        expected_session_hash=str(session.get("session_hash", "")),
        attempt=attempt,
        scene_slug=str(manifest.get("scene_slug", "")),
        manifest_hash=str(manifest.get("manifest_hash", "")),
        calibration_performed=bool(review.get("calibration_recheck", {}).get("performed")),
        reviewer_anomalous=bool(health.get("anomalous")),
    )
    existing = None if appended else stored_attempt
    print(
        json.dumps(
            {
                "valid": not errors,
                "errors": errors,
                "verdict": review.get("verdict"),
                "manifest_hash": manifest.get("manifest_hash"),
                "reviewer_health": health,
                "review_attempt_log": str(audit_log),
                "review_attempt_id": (existing or attempt)["attempt_id"],
                "deduplicated": existing is not None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not errors else 2


def command_begin_review_batch(args: argparse.Namespace) -> int:
    rules = load_rules()
    repo_root = Path(getattr(args, "repo_root", ".")).resolve()
    spine_path = resolve_stored_path(str(args.episode_spine), repo_root)
    spine = load_json(spine_path)
    if spine.get("schema") != "lecture-animation-episode-visual-spine-v2" or not validate_hashed_record(spine, "spine_hash"):
        raise PipelineError("begin-review-batch requires a valid hash-bound episode spine")
    governance_facts, governance_errors = review_session_governance(
        spine,
        reviewer_agent_id=str(args.reviewer_agent_id).strip(),
        author_agent_id=str(args.author_agent_id).strip(),
        review_role=str(args.review_role),
    )
    if governance_errors:
        raise PipelineError("review governance failed: " + " | ".join(governance_errors))
    reviewer_tier = getattr(args, "reviewer_tier", "frontier")
    reasoning_effort = getattr(args, "reasoning_effort", "medium")
    certification_hash = None
    if reviewer_tier == "light":
        certification_path = getattr(args, "certification", None)
        if not certification_path:
            raise PipelineError("light reviewer tier requires --certification")
        certification = load_reviewer_certification(Path(certification_path))
        if certification.get("reviewer_model") != args.reviewer_model:
            raise PipelineError("reviewer certification model does not match --reviewer-model")
        if certification.get("reasoning_effort") != reasoning_effort:
            raise PipelineError("reviewer certification reasoning effort does not match --reasoning-effort")
        certification_hash = certification.get("certification_hash")
    session = {
        "schema": "lecture-animation-review-session-v2",
        "created_at": utc_now(),
        "batch_id": args.batch_id,
        "session_id": f"review-session:{hashlib.sha1(f'{args.batch_id}|{args.reviewer_agent_id}|{utc_now()}'.encode()).hexdigest()[:16]}",
        "reviewer": args.reviewer,
        "reviewer_model": args.reviewer_model,
        "reviewer_tier": reviewer_tier,
        "reasoning_effort": reasoning_effort,
        "certification_hash": certification_hash,
        "certification_suspended": False,
        "escalation_model": getattr(args, "escalation_model", "gpt-5.6-sol"),
        "reviewer_agent_id": args.reviewer_agent_id,
        "owner": args.owner,
        "author_agent_id": args.author_agent_id,
        "episode_spine_path": relative_or_absolute(spine_path, repo_root),
        **governance_facts,
        "rules_registry_hash": object_hash(rules),
        "status": "active",
        "scenes": [],
        "full_reviews": 0,
        "diagnostic_reviews": 0,
        "reviewer_switches": 0,
        "calibration_scene_interval": args.calibration_scene_interval,
        "calibration_due": False,
        "capsule_required": True,
        "contract_version": REVIEW_SESSION_CONTRACT_VERSION,
        "revision": 0,
        "applied_review_attempt_ids": [],
        "pending_repairs": {},
    }
    if normalize_search_text(args.reviewer) == normalize_search_text(args.owner):
        raise PipelineError("reviewer must be independent from owner")
    if str(args.reviewer_agent_id).strip() == str(args.author_agent_id).strip():
        raise PipelineError("reviewer_agent_id must differ from author_agent_id")
    if args.replace and len(str(args.replace_reason or "").strip()) < 16:
        raise PipelineError("--replace requires a concrete --replace-reason")
    output = Path(args.output)
    session = create_review_session(
        output,
        session,
        replace=bool(args.replace),
        replace_reason=args.replace_reason,
    )
    print(json.dumps({"review_session": str(output), "session_id": session["session_id"]}, ensure_ascii=False))
    return 0


def command_choose_review_mode(args: argparse.Namespace) -> int:
    previous_manifest = load_json(Path(args.previous_manifest))
    current_manifest = load_json(Path(args.current_manifest))
    previous_review = load_json(Path(args.previous_review))
    session = load_review_session(Path(args.review_session))
    attempts = canonical_review_attempt_rows(Path(args.attempt_log)) if args.attempt_log else []
    change_impact = load_json(Path(args.change_impact)) if getattr(args, "change_impact", None) else None
    strategy = review_strategy_data(previous_manifest, current_manifest, previous_review, session, attempts, change_impact)
    write_json(Path(args.output), strategy)
    print(json.dumps(strategy, ensure_ascii=False, indent=2))
    return 2 if strategy["root_cause_escalation_required"] else 0


def command_prepare_diagnostic_review(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    previous_manifest = load_json(Path(args.previous_manifest))
    current_manifest = load_json(Path(args.current_manifest))
    previous_review = load_json(Path(args.previous_review))
    # The previous files are expected to have changed during repair. Preserve and
    # validate the frozen record itself rather than comparing it to the live tree.
    previous_errors = verify_manifest_record_hash(previous_manifest)
    current_errors = verify_manifest_data(current_manifest, repo_root)
    if previous_errors:
        raise PipelineError("previous manifest is stale: " + " | ".join(previous_errors))
    if current_errors:
        raise PipelineError("current manifest is stale: " + " | ".join(current_errors))
    profile_entry = current_manifest.get("artifacts", {}).get("profile", {})
    profile = load_json(resolve_stored_path(str(profile_entry.get("path", "")), repo_root))
    plan = load_json(
        resolve_stored_path(str(current_manifest.get("artifacts", {}).get("plan", {}).get("path", "")), repo_root)
    )
    author_self_review = load_json(Path(args.author_self_review))
    self_review_errors = validate_author_self_review_data(
        author_self_review,
        current_manifest,
        profile,
        plan,
        previous_review=previous_review,
        repo_root=repo_root,
    )
    if self_review_errors:
        raise PipelineError("diagnostic review is blocked by author self-review: " + " | ".join(self_review_errors))
    session = load_review_session(Path(args.review_session))
    change_impact = load_json(Path(args.change_impact))
    if normalize_search_text(str(previous_review.get("reviewer", ""))) != normalize_search_text(str(session.get("reviewer", ""))):
        raise PipelineError("diagnostic review must resume the reviewer who issued the prior findings")
    packet = diagnostic_packet_data(
        previous_manifest,
        current_manifest,
        previous_review,
        profile,
        session,
        change_impact,
        author_self_review,
        margin=args.margin,
    )
    write_json(Path(args.output), packet)
    print(
        json.dumps(
            {
                "diagnostic_packet": args.output,
                "packet_hash": packet["packet_hash"],
                "resume_reviewer_agent_id": session.get("reviewer_agent_id"),
                "required_windows": packet["required_review_windows"],
                "required_regression_samples": packet["required_regression_samples"],
                "full_regression_required_after_pass": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_verify_diagnostic_review(args: argparse.Namespace) -> int:
    packet = load_json(Path(args.packet))
    submission = load_json(Path(args.submission))
    session_path = Path(args.review_session)
    session = load_review_session(session_path)
    errors = verify_diagnostic_review_data(submission, packet, session)
    episode = Path(args.episode).resolve()
    attempt_log = Path(args.attempt_log) if args.attempt_log else episode / "review" / "evolution" / "review_attempts.jsonl"
    submission_hash = object_hash(submission)
    verification_key = object_hash(
        {
            "packet_hash": packet.get("packet_hash"),
            "submission_hash": submission_hash,
            "review_session_id": session.get("session_id"),
            "gate_errors": errors,
        }
    )
    seed = verification_key
    attempt = {
        "schema": "lecture-animation-review-attempt-v2",
        "attempt_id": f"review:{hashlib.sha1(seed.encode()).hexdigest()[:16]}",
        "created_at": utc_now(),
        "episode": episode.name,
        "scene_slug": packet.get("scene_slug"),
        "manifest_hash": packet.get("current_manifest_hash"),
        "reviewer": session.get("reviewer"),
        "reviewer_model": session.get("reviewer_model"),
        "reasoning_effort": session.get("reasoning_effort"),
        "reviewer_tier": session.get("reviewer_tier", "legacy"),
        "reviewer_agent_id": session.get("reviewer_agent_id"),
        "review_session_id": session.get("session_id"),
        "review_mode": "diagnostic",
        "verdict": submission.get("verdict"),
        "gate_accepted": not errors,
        "gate_errors": errors,
        "findings_count": sum(1 for item in submission.get("finding_checks", []) if item.get("status") == "not_fixed"),
        "failed_checks_count": 0,
        "calibration_recheck": False,
        "may_grant_user_review_pending": False,
        "submission_hash": submission_hash,
        "verification_key": verification_key,
    }
    stored_attempt, appended, session = commit_review_attempt(
        session_path=session_path,
        attempt_log=attempt_log,
        expected_session_hash=str(session.get("session_hash", "")),
        attempt=attempt,
        scene_slug=str(packet.get("scene_slug", "")),
        manifest_hash=str(packet.get("current_manifest_hash", "")),
        calibration_performed=False,
        reviewer_anomalous=False,
        review_mode="diagnostic",
    )
    existing = None if appended else stored_attempt
    result = {
        "valid": not errors,
        "errors": errors,
        "verdict": submission.get("verdict"),
        "state": "diagnostic_fix_verified" if not errors and submission.get("verdict") == "diagnostic_fix_verified" else "revision_required",
        "may_show_user": False,
        "next_required_action": "run_full_regression_review" if not errors and submission.get("verdict") == "diagnostic_fix_verified" else "repair_and_repeat_diagnostic_review",
        "review_attempt_log": str(attempt_log),
        "deduplicated": existing is not None,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


def command_gate_status(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    state = "unprofiled"
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    profile: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    author_self_review: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    health: dict[str, Any] = {}

    if args.profile:
        try:
            profile = load_json(resolve_stored_path(args.profile, repo_root))
            profile_errors = [] if validate_profile_hash(profile) else ["profile semantic hash is invalid"]
        except PipelineError as exc:
            profile_errors = [str(exc)]
        checks.append({"gate": "profile", "valid": not profile_errors, "errors": profile_errors})
        if profile_errors:
            errors.extend(profile_errors)
        else:
            state = "profiled"
    if args.plan:
        if profile is None or errors:
            plan_errors = ["valid profile is required before plan validation"]
        else:
            try:
                plan = load_json(resolve_stored_path(args.plan, repo_root))
                plan_errors = validate_scene_plan_data(profile, plan)
                design_paths = [
                    getattr(args, "challenge", None),
                    getattr(args, "deliberation", None),
                    getattr(args, "design_gate", None),
                    getattr(args, "precedent_packet", None),
                ]
                if not all(design_paths):
                    plan_errors.append("challenge, deliberation, design_gate, and precedent_packet are required for planned state")
                else:
                    plan_errors.extend(
                        validate_design_chain_data(
                            profile,
                            plan,
                            load_json(resolve_stored_path(str(design_paths[0]), repo_root)),
                            load_json(resolve_stored_path(str(design_paths[1]), repo_root)),
                            load_json(resolve_stored_path(str(design_paths[2]), repo_root)),
                            load_json(resolve_stored_path(str(design_paths[3]), repo_root)),
                        )
                    )
            except PipelineError as exc:
                plan_errors = [str(exc)]
        checks.append({"gate": "plan", "valid": not plan_errors, "errors": plan_errors})
        if plan_errors:
            errors.extend(plan_errors)
        else:
            state = "planned"
    if args.manifest:
        if state != "planned":
            manifest_errors = ["valid profile and plan are required before manifest validation"]
        else:
            try:
                manifest = load_json(resolve_stored_path(args.manifest, repo_root))
                manifest_errors = verify_manifest_data(manifest, repo_root)
            except PipelineError as exc:
                manifest_errors = [str(exc)]
        checks.append({"gate": "manifest", "valid": not manifest_errors, "errors": manifest_errors})
        if manifest_errors:
            errors.extend(manifest_errors)
        else:
            state = "review_candidate_frozen"
    if args.author_self_review:
        if manifest is None or profile is None or plan is None or state != "review_candidate_frozen":
            self_review_errors = ["valid profile, plan, and frozen manifest are required before author self-review"]
        else:
            try:
                author_self_review = load_json(resolve_stored_path(args.author_self_review, repo_root))
                previous_review = (
                    load_json(resolve_stored_path(args.previous_review, repo_root))
                    if getattr(args, "previous_review", None)
                    else None
                )
                self_review_errors = validate_author_self_review_data(
                    author_self_review,
                    manifest,
                    profile,
                    plan,
                    previous_review=previous_review,
                    repo_root=repo_root,
                )
            except PipelineError as exc:
                self_review_errors = [str(exc)]
        checks.append({"gate": "author_self_review", "valid": not self_review_errors, "errors": self_review_errors})
        if self_review_errors:
            errors.extend(self_review_errors)
        else:
            state = "author_self_review_passed"
    if args.review:
        if manifest is None or profile is None or author_self_review is None or state != "author_self_review_passed":
            review_errors = ["valid author self-review is required before independent review validation"]
        else:
            try:
                review = load_json(resolve_stored_path(args.review, repo_root))
                episode = resolve_stored_path(str(manifest.get("episode", "")), repo_root)
                event_log = Path(args.event_log) if args.event_log else episode / "review" / "evolution" / "events.jsonl"
                review_errors, health = verify_review_data(review, manifest, profile, repo_root, event_log)
                if not getattr(args, "review_session", None):
                    review_errors.append("review_session is required for review state validation")
                else:
                    session = load_review_session(Path(args.review_session))
                    review_errors.extend(validate_session_reviewer(session, review))
                    review_errors.extend(
                        validate_session_governance(
                            session,
                            manifest,
                            repo_root,
                            str(review.get("verdict", "")),
                        )
                    )
                    review_errors.extend(
                        validate_pending_repair_binding(
                            session,
                            str(manifest.get("scene_slug", "")),
                            author_self_review,
                            str(review.get("verdict", "")),
                        )
                    )
                    if session.get("capsule_required"):
                        capsule_path = getattr(args, "review_capsule", None)
                        receipt_path = getattr(args, "blind_receipt", None)
                        if not capsule_path or not receipt_path:
                            review_errors.append("review capsule and blind receipt are required for review state validation")
                        else:
                            review_errors.extend(
                                validate_review_capsule_chain(
                                    review,
                                    load_json(resolve_stored_path(capsule_path, repo_root)),
                                    load_json(resolve_stored_path(receipt_path, repo_root)),
                                    manifest,
                                    session,
                                    author_self_review,
                                )
                            )
            except PipelineError as exc:
                review_errors = [str(exc)]
        checks.append({"gate": "review", "valid": not review_errors, "errors": review_errors})
        if review_errors:
            errors.extend(review_errors)
        elif review and review.get("verdict") == "revise":
            state = "revision_required"
        else:
            state = "user_review_pending"

    result: dict[str, Any] = {
        "schema": "lecture-animation-gate-state-v2",
        "generated_at": utc_now(),
        "state": state,
        "valid": not errors,
        "checks": checks,
        "errors": errors,
        "profile_hash": profile.get("profile_hash") if profile else None,
        "manifest_hash": manifest.get("manifest_hash") if manifest else None,
        "reviewer_health": health,
        "permissions": {
            "may_author": state in {"planned", "review_candidate_frozen", "revision_required", "user_review_pending"},
            "may_request_review": state == "author_self_review_passed",
            "may_show_user": state == "user_review_pending",
            "may_stage_or_commit": False,
        },
    }
    payload = dict(result)
    result["state_hash"] = object_hash(payload)
    if args.output:
        write_json(Path(args.output), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


PHASES = {"design", "authoring", "render", "review", "repair", "tts", "asr", "human_wait"}
TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")
PROGRESSIVE_SCENE_STATES = {
    "provisional": 0,
    "designing": 1,
    "audio_aligned": 2,
    "animation_candidate": 3,
    "user_approved": 4,
    "assembled": 5,
}
SCENE_EXACT_ARTIFACTS = (
    "script",
    "audio",
    "reader_srt",
    "word_srt",
    "word_alignment",
    "timeline_fragment",
    "asr_transcript",
    "narration_qc",
)


def unique_phase_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("phase_instance_id") or row.get("event_id") or object_hash(row))
        previous = selected.get(key)
        if previous is None or float(row.get("duration_seconds", 0.0) or 0.0) > float(previous.get("duration_seconds", 0.0) or 0.0):
            selected[key] = row
    return list(selected.values())


def normalize_token_usage(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    candidates = [
        value,
        value.get("usage"),
        value.get("token_usage"),
        value.get("total_token_usage"),
        value.get("info", {}).get("total_token_usage") if isinstance(value.get("info"), dict) else None,
        value.get("payload", {}).get("info", {}).get("total_token_usage")
        if isinstance(value.get("payload"), dict) and isinstance(value.get("payload", {}).get("info"), dict)
        else None,
    ]
    for item in candidates:
        if not isinstance(item, dict) or not any(key in item for key in ("input_tokens", "prompt_tokens", "output_tokens", "completion_tokens")):
            continue
        return {
            "input_tokens": int(item.get("input_tokens", item.get("prompt_tokens", 0)) or 0),
            "cached_input_tokens": int(
                item.get("cached_input_tokens", item.get("cache_read_input_tokens", 0)) or 0
            ),
            "output_tokens": int(item.get("output_tokens", item.get("completion_tokens", 0)) or 0),
            "reasoning_tokens": int(
                item.get("reasoning_tokens", item.get("reasoning_output_tokens", 0)) or 0
            ),
        }
    return None


def latest_jsonl_token_usage(path: Path, max_bytes: int = 4 * 1024 * 1024) -> dict[str, int] | None:
    with path.open("rb") as handle:
        handle.seek(0, 2)
        position = handle.tell()
        buffer = b""
        while position > 0 and len(buffer) < max_bytes:
            size = min(65536, position, max_bytes - len(buffer))
            position -= size
            handle.seek(position)
            buffer = handle.read(size) + buffer
            for raw in reversed(buffer.splitlines()):
                try:
                    usage = normalize_token_usage(json.loads(raw))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if usage is not None:
                    return usage
    return None


def discover_codex_rollout(thread_id: str) -> Path | None:
    sessions = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "sessions"
    matches = list(sessions.rglob(f"*{thread_id}*.jsonl")) if sessions.exists() else []
    return max(matches, key=lambda path: path.stat().st_mtime_ns) if matches else None


def token_usage_snapshot(source: Path) -> dict[str, int] | None:
    if not source.exists():
        return None
    if source.suffix == ".jsonl":
        return latest_jsonl_token_usage(source)
    try:
        return normalize_token_usage(load_json(source))
    except PipelineError:
        return None


def resolve_token_usage_source(explicit: str | None = None) -> tuple[Path | None, str]:
    raw = explicit or os.environ.get("LECTURE_TOKEN_USAGE_FILE")
    if raw:
        return Path(raw).expanduser().resolve(), "usage_file"
    thread_id = os.environ.get("CODEX_THREAD_ID")
    if thread_id:
        path = discover_codex_rollout(thread_id)
        if path:
            return path, "codex_rollout"
    return None, "unavailable"


def interval_union_seconds(rows: list[dict[str, Any]]) -> float:
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


def phase_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    unique = unique_phase_events(rows)
    active = [row for row in unique if row.get("phase") != "human_wait"]
    phase_agent: Counter[str] = Counter()
    phase_wall: dict[str, float] = {}
    for row in unique:
        phase_agent[str(row.get("phase", "unknown"))] += float(row.get("duration_seconds", 0.0) or 0.0)
    for phase in phase_agent:
        phase_wall[phase] = interval_union_seconds([row for row in unique if str(row.get("phase")) == phase])
    token_usage: Counter[str] = Counter()
    for row in unique:
        for field in TOKEN_FIELDS:
            token_usage[field] += int(row.get(field, 0) or 0)
    token_observed = [row for row in active if row.get("token_observed") is True]
    token_expected = [row for row in active if str(row.get("phase")) in {"design", "authoring", "review", "repair"}]
    phase_tokens: dict[str, Counter[str]] = defaultdict(Counter)
    for row in unique:
        phase = str(row.get("phase", "unknown"))
        for field in TOKEN_FIELDS:
            phase_tokens[phase][field] += int(row.get(field, 0) or 0)
    aggregate = sum(float(row.get("duration_seconds", 0.0) or 0.0) for row in active)
    critical = interval_union_seconds(active)
    return {
        "unique_events": unique,
        "aggregate_agent_seconds": aggregate,
        "critical_path_seconds": critical,
        "concurrency_overlap_seconds": max(0.0, aggregate - critical),
        "human_wait_seconds": phase_agent.get("human_wait", 0.0),
        "phase_agent_seconds": dict(phase_agent),
        "phase_wall_seconds": phase_wall,
        "token_usage": dict(token_usage),
        "phase_token_usage": {phase: dict(counts) for phase, counts in sorted(phase_tokens.items())},
        "token_observability": {
            "expected_events": len(token_expected),
            "observed_events": sum(row.get("token_observed") is True for row in token_expected),
            "coverage": round(
                sum(row.get("token_observed") is True for row in token_expected) / len(token_expected), 4
            ) if token_expected else 1.0,
            "missing_event_ids": [
                row.get("event_id") for row in token_expected if row.get("token_observed") is not True
            ],
        },
    }


def command_phase_start(args: argparse.Namespace) -> int:
    if args.phase not in PHASES:
        raise PipelineError(f"unknown phase: {args.phase}")
    repair_binding: dict[str, Any] = {}
    if args.phase == "repair":
        contract_path = getattr(args, "repair_contract", None)
        review_path = getattr(args, "previous_review", None)
        if not contract_path or not review_path:
            raise PipelineError("repair phase requires --previous-review and --repair-contract")
        review = load_json(Path(review_path))
        contract = load_json(Path(contract_path))
        if review.get("verdict") != "revise":
            raise PipelineError("repair phase previous review must have verdict=revise")
        if contract.get("schema") != "lecture-animation-repair-contract-v2" or not validate_hashed_record(contract, "contract_hash"):
            raise PipelineError("repair phase requires a valid sealed repair contract")
        if contract.get("review_hash") != object_hash(review):
            raise PipelineError("repair contract is bound to another revise review")
        repair_binding = {
            "previous_review_path": str(Path(review_path).resolve()),
            "previous_review_hash": object_hash(review),
            "repair_contract_path": str(Path(contract_path).resolve()),
            "repair_contract_hash": contract.get("contract_hash"),
            "required_finding_ids": [
                str(item.get("finding_id"))
                for item in contract.get("findings", [])
                if isinstance(item, dict)
            ],
        }
    state_path = Path(args.state)
    with locked_paths([state_path]):
        if state_path.exists():
            existing = load_json_unlocked(state_path)
            if existing.get("status") == "active":
                raise PipelineError("phase timer is already active; end it before starting another")
        phase_instance_id = getattr(args, "phase_instance_id", None) or f"phase-instance:{hashlib.sha1(f'{args.run_id}|{args.scene_slug}|{args.phase}|{utc_now()}'.encode()).hexdigest()[:16]}"
        usage_source, usage_source_kind = resolve_token_usage_source(getattr(args, "usage_file", None))
        usage_baseline = token_usage_snapshot(usage_source) if usage_source else None
        state = {
            "schema": "lecture-animation-phase-timer-v2",
            "run_id": args.run_id,
            "scene_slug": args.scene_slug,
            "phase": args.phase,
            "actor_model": args.actor_model,
            "actor_role": getattr(args, "actor_role", "unspecified"),
            "reasoning_effort": getattr(args, "reasoning_effort", "unspecified"),
            "phase_instance_id": phase_instance_id,
            "prompt_bytes": int(getattr(args, "prompt_bytes", 0) or 0),
            "artifact_input_bytes": int(getattr(args, "artifact_input_bytes", 0) or 0),
            "files_read": int(getattr(args, "files_read", 0) or 0),
            "token_usage_source": str(usage_source) if usage_source else "",
            "token_usage_source_kind": usage_source_kind,
            "token_usage_baseline": usage_baseline,
            "started_at": utc_now(),
            "status": "active",
            **repair_binding,
        }
        state["timer_hash"] = object_hash(state)
        atomic_write_json_unlocked(state_path, state)
    print(json.dumps({"phase_state": str(state_path), "started_at": state["started_at"]}, ensure_ascii=False))
    return 0


def command_phase_end(args: argparse.Namespace) -> int:
    state_path = Path(args.state)
    phase_log = Path(args.phase_log)
    with locked_paths([state_path, phase_log]):
        state = load_json_unlocked(state_path)
        if state.get("schema") != "lecture-animation-phase-timer-v2" or not validate_hashed_record(state, "timer_hash"):
            raise PipelineError("phase timer is invalid or was edited")
        if state.get("status") != "active":
            raise PipelineError("phase timer is not active")
        repair_completion: dict[str, Any] = {}
        if state.get("phase") == "repair" and args.result == "completed":
            response_path = getattr(args, "repair_response", None)
            gate_path = getattr(args, "repair_gate", None)
            manifest_path = getattr(args, "current_manifest", None)
            if not response_path or not gate_path or not manifest_path:
                raise PipelineError(
                    "completed repair phase requires --repair-response, --repair-gate, and --current-manifest"
                )
            contract = load_json(Path(str(state.get("repair_contract_path", ""))))
            response = load_json(Path(response_path))
            gate = load_json(Path(gate_path))
            manifest = load_json(Path(manifest_path))
            repair_errors = validate_repair_response_data(response, contract, manifest)
            repair_errors.extend(validate_repair_gate_data(gate, response, contract, manifest))
            if repair_errors:
                raise PipelineError("repair phase cannot complete: " + " | ".join(repair_errors))
            repair_completion = {
                "repair_response_hash": object_hash(response),
                "repair_gate_hash": gate.get("gate_hash"),
                "repaired_manifest_hash": manifest.get("manifest_hash"),
                "findings_resolved": gate.get("findings_resolved"),
            }
        started = datetime.fromisoformat(str(state["started_at"]))
        ended = datetime.now(timezone.utc)
        duration = max(0.0, (ended - started).total_seconds())
        event_seed = "|".join(
            str(state.get(key, "")) for key in ("run_id", "scene_slug", "phase", "started_at")
        )
        event = {
        "schema": "lecture-animation-phase-event-v2",
        "event_id": f"phase:{hashlib.sha1(event_seed.encode()).hexdigest()[:16]}",
        "run_id": state.get("run_id"),
        "scene_slug": state.get("scene_slug"),
        "phase": state.get("phase"),
        "actor_model": state.get("actor_model"),
        "actor_role": state.get("actor_role"),
        "reasoning_effort": state.get("reasoning_effort"),
        "phase_instance_id": state.get("phase_instance_id"),
        "prompt_bytes": state.get("prompt_bytes", 0),
        "artifact_input_bytes": state.get("artifact_input_bytes", 0),
        "files_read": state.get("files_read", 0),
        "started_at": state.get("started_at"),
        "ended_at": ended.isoformat(timespec="seconds"),
        "duration_seconds": round(duration, 3),
        "manifest_hash": args.manifest_hash or "",
        "result": args.result,
        **repair_completion,
        }
        explicit_values = {field: getattr(args, field, None) for field in TOKEN_FIELDS}
        if any(value is not None for value in explicit_values.values()):
            usage = {field: int(explicit_values.get(field) or 0) for field in TOKEN_FIELDS}
            token_source_kind = "manual"
            token_observed = True
        else:
            source_raw = getattr(args, "usage_file", None) or state.get("token_usage_source")
            source = Path(source_raw).expanduser().resolve() if source_raw else None
            baseline = state.get("token_usage_baseline")
            current = token_usage_snapshot(source) if source else None
            if isinstance(baseline, dict) and isinstance(current, dict):
                usage = {field: max(0, int(current.get(field, 0)) - int(baseline.get(field, 0))) for field in TOKEN_FIELDS}
                token_source_kind = state.get("token_usage_source_kind", "usage_file")
                token_observed = True
            else:
                usage = {field: 0 for field in TOKEN_FIELDS}
                token_source_kind = "unavailable"
                token_observed = False
        event.update(usage)
        event["token_observed"] = token_observed
        event["token_source_kind"] = token_source_kind
        from .storage import append_jsonl_unlocked

        append_jsonl_unlocked(phase_log, event)
        state["status"] = "completed"
        state["ended_at"] = event["ended_at"]
        state["duration_seconds"] = event["duration_seconds"]
        state.pop("timer_hash", None)
        state["timer_hash"] = object_hash(state)
        atomic_write_json_unlocked(state_path, state)
    print(json.dumps({"phase_log": args.phase_log, "event_id": event["event_id"], "duration_seconds": event["duration_seconds"]}, ensure_ascii=False))
    return 0


def parallel_worktree_identity(repo_root: Path) -> tuple[str, str]:
    required_worktree_root = Path("/Volumes/bocchi/myLectures-worktrees").resolve()
    if repo_root.parent != required_worktree_root:
        raise PipelineError(
            "parallel production must run from a dedicated direct child worktree of "
            "/Volumes/bocchi/myLectures-worktrees/"
        )
    try:
        top_level = Path(
            subprocess.run(
                ["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        ).resolve()
        branch = subprocess.run(
            ["git", "-C", str(repo_root), "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, OSError) as exc:
        raise PipelineError(f"parallel production worktree Git identity cannot be verified: {exc}") from exc
    if top_level != repo_root:
        raise PipelineError("--repo-root must be the root of the dedicated production worktree")
    if not branch.startswith("agent/"):
        raise PipelineError("parallel production worktree branch must use the agent/... prefix")
    return str(repo_root), branch


def command_begin_production_batch(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    episode = resolve_episode(repo_root, args.episode)
    scenes = [value.strip() for value in args.scenes.split(",") if value.strip()]
    if not scenes:
        raise PipelineError("production batch requires at least one scene")
    spine_path = resolve_stored_path(args.episode_spine, repo_root)
    batch_plan_path = resolve_stored_path(args.batch_plan, repo_root)
    production_path = resolve_stored_path(args.production, repo_root)
    spine = load_json(spine_path)
    batch_plan = load_json(batch_plan_path)
    production = load_json(production_path)
    production_mode = str(spine.get("production_mode", "main_producer"))
    author_id = str(getattr(args, "author_id", "") or "").strip()
    production_worktree: str | None = None
    production_branch: str | None = None
    if production_mode == "parallel_batches":
        if not author_id:
            raise PipelineError("parallel production batch requires --author-id")
        if author_id == str(spine.get("main_agent_governance", {}).get("owner", "")):
            raise PipelineError("parallel production author must differ from the main-agent owner")
        production_worktree, production_branch = parallel_worktree_identity(repo_root)
    planning_errors = validate_episode_spine_data(spine, repo_root, episode)
    planning_errors.extend(validate_batch_visual_plan_data(batch_plan, spine, args.batch_id, scenes))
    planning_errors.extend(validate_progressive_production_data(production, repo_root, episode))
    production_scenes = {str(row.get("scene_slug")) for row in production.get("scenes", []) if isinstance(row, dict)}
    if not set(scenes) <= production_scenes:
        planning_errors.append("production batch scenes are missing from progressive_production.json")
    if planning_errors:
        raise PipelineError("progressive planning gate failed: " + " | ".join(planning_errors))
    contract: dict[str, Any] = {
        "schema": "lecture-animation-production-batch-v2",
        "batch_id": args.batch_id,
        "episode": relative_or_absolute(episode, repo_root),
        "scenes": scenes,
        "episode_spine_path": relative_or_absolute(spine_path, repo_root),
        "episode_spine_hash": spine.get("spine_hash"),
        "batch_plan_path": relative_or_absolute(batch_plan_path, repo_root),
        "batch_plan_hash": batch_plan.get("batch_plan_hash"),
        "production_path": relative_or_absolute(production_path, repo_root),
        "production_hash_at_start": production.get("production_hash"),
        "started_at": utc_now(),
        "target_active_seconds": round(float(args.target_hours) * 3600.0, 3),
        "episode_target_seconds": round(float(args.episode_target_hours) * 3600.0, 3),
        "skill_tree_hash": skill_tree_hash(repo_root, None),
        "hard_gate_layers": list(HARD_GATE_LAYERS),
        "production_mode": production_mode,
        "author_id": author_id or str(spine.get("main_agent_governance", {}).get("owner", "main_agent")),
        "production_worktree": production_worktree,
        "production_branch": production_branch,
        "main_agent_owner": batch_plan.get("main_agent_owner"),
        "cli_gate_policy": batch_plan.get("cli_gate_policy", "required_no_bypass"),
        "batch_entry_contract": batch_plan.get("batch_entry_contract"),
        "batch_exit_contract": batch_plan.get("batch_exit_contract"),
        "adjacency_contracts": batch_plan.get("adjacency_contracts", []),
        "status": "active",
    }
    contract["batch_hash"] = object_hash(contract)
    write_json(Path(args.output), contract)
    print(json.dumps(contract, ensure_ascii=False, indent=2))
    return 0


def command_batch_status(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    contract = load_json(Path(args.batch))
    if contract.get("schema") != "lecture-animation-production-batch-v2" or not validate_hashed_record(contract, "batch_hash"):
        raise PipelineError("production batch contract is invalid or was edited")
    if contract.get("production_mode") == "parallel_batches":
        current_worktree, current_branch = parallel_worktree_identity(repo_root)
        if current_worktree != contract.get("production_worktree") or current_branch != contract.get("production_branch"):
            raise PipelineError("parallel production batch is running from a different worktree or branch than its sealed contract")
    episode = resolve_stored_path(str(contract.get("episode", "")), repo_root)
    for path_key, hash_key, payload_hash_key in (
        ("episode_spine_path", "episode_spine_hash", "spine_hash"),
        ("batch_plan_path", "batch_plan_hash", "batch_plan_hash"),
    ):
        raw_path = str(contract.get(path_key, ""))
        if not raw_path:
            raise PipelineError(f"production batch is missing progressive planning binding: {path_key}")
        payload = load_json(resolve_stored_path(raw_path, repo_root))
        if payload.get(payload_hash_key) != contract.get(hash_key) or not validate_hashed_record(payload, payload_hash_key):
            raise PipelineError(f"production batch planning artifact is stale: {path_key}")
    production_path = resolve_stored_path(str(contract.get("production_path", "")), repo_root)
    production = load_json(production_path)
    production_errors = validate_progressive_production_data(production, repo_root, episode)
    if production_errors:
        raise PipelineError("progressive production tracker is invalid: " + " | ".join(production_errors))
    scenes = set(map(str, contract.get("scenes", [])))
    started = datetime.fromisoformat(str(contract.get("started_at")))

    def belongs_to_batch(row: dict[str, Any]) -> bool:
        if str(row.get("scene_slug", "")) not in scenes:
            return False
        if str(row.get("run_id", "")) == str(contract.get("batch_id", "")):
            return True
        if str(row.get("batch_id", "")) == str(contract.get("batch_id", "")):
            return True
        raw_time = row.get("created_at") or row.get("started_at")
        try:
            return datetime.fromisoformat(str(raw_time)) >= started
        except (TypeError, ValueError):
            return False

    batch_root = Path(args.batch).resolve().parent

    def merged_rows(paths: list[Path], loader: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in paths:
            for row in loader(path):
                identity = str(
                    row.get("attempt_id")
                    or row.get("event_id")
                    or row.get("phase_instance_id")
                    or object_hash(row)
                )
                if identity in seen:
                    continue
                seen.add(identity)
                rows.append(row)
        return rows

    def deduplicated(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            identity = str(
                row.get("attempt_id")
                or row.get("event_id")
                or row.get("phase_instance_id")
                or object_hash(row)
            )
            if identity not in seen:
                seen.add(identity)
                result.append(row)
        return result

    phases = deduplicated(
        [
            row
            for row in merged_rows(
                [episode / "review" / "evolution" / "production_phases.jsonl"],
                event_rows,
            )
            if belongs_to_batch(row)
        ]
        + [
            row
            for row in merged_rows(
                [batch_root / "production_phases.jsonl", batch_root / "phase_log.jsonl"],
                event_rows,
            )
            if str(row.get("scene_slug", "")) in scenes
        ]
    )
    attempts = deduplicated(
        [
            row
            for row in merged_rows(
                [episode / "review" / "evolution" / "review_attempts.jsonl"],
                canonical_review_attempt_rows,
            )
            if belongs_to_batch(row)
        ]
        + [
            row
            for row in merged_rows(
                [
                    episode / "review" / "v2" / scene / "review_attempts.jsonl"
                    for scene in scenes
                ],
                canonical_review_attempt_rows,
            )
            if str(row.get("scene_slug", "")) in scenes
        ]
    )
    author_self_reviews = [
        row for row in event_rows(episode / "review" / "evolution" / "author_self_review_attempts.jsonl")
        if belongs_to_batch(row)
    ]
    measured = phase_metrics(phases)
    phase_seconds = measured["phase_wall_seconds"]
    phase_agent_seconds = measured["phase_agent_seconds"]
    active_seconds = float(measured["critical_path_seconds"])
    aggregate_agent_seconds = float(measured["aggregate_agent_seconds"])
    human_wait_seconds = float(measured["human_wait_seconds"])
    wall_seconds = max(0.0, (datetime.now(timezone.utc) - started).total_seconds())
    full_reviews = sum(row.get("review_mode") in {None, "full_regression"} for row in attempts)
    diagnostics = sum(row.get("review_mode") == "diagnostic" for row in attempts)
    self_reviewed_manifests = {
        str(row.get("manifest_hash"))
        for row in author_self_reviews
        if row.get("manifest_hash") and row.get("gate_accepted")
    }
    post_self_review_attempts = [row for row in attempts if str(row.get("manifest_hash")) in self_reviewed_manifests]
    artifact_count = 0
    for scene in scenes:
        scene_root = episode / "review" / "v2" / scene
        if scene_root.exists():
            artifact_count += sum(1 for path in scene_root.iterdir() if clean_path(path))
    alerts: list[str] = []
    if active_seconds > float(contract.get("target_active_seconds", 0.0) or 0.0):
        alerts.append("ACTIVE_BUDGET_EXCEEDED")
    if full_reviews > max(2 * len(scenes), diagnostics + len(scenes)):
        alerts.append("FULL_REVIEW_LOOP_DOMINATES")
    if artifact_count > 20 * len(scenes):
        alerts.append("REVIEW_ARTIFACT_EXPLOSION")
    expected_phases = {"design", "authoring", "render", "review"}
    missing_phases = sorted(expected_phases - set(phase_agent_seconds))
    if missing_phases:
        alerts.append("PHASE_TELEMETRY_INCOMPLETE")
    token_observability = measured["token_observability"]
    if float(token_observability.get("coverage", 0.0)) < 1.0:
        alerts.append("TOKEN_TELEMETRY_INCOMPLETE")
    events_path = episode / "review" / "evolution" / "events.jsonl"
    feedback_root = episode / "review" / "human-feedback"
    newest_feedback = max((path.stat().st_mtime_ns for path in feedback_root.glob("*.md")), default=0) if feedback_root.exists() else 0
    if newest_feedback and (not events_path.exists() or newest_feedback > events_path.stat().st_mtime_ns):
        alerts.append("HUMAN_OUTCOME_LOG_STALE")
    scene_states = {
        str(row.get("scene_slug")): row.get("state")
        for row in production.get("scenes", [])
        if isinstance(row, dict) and str(row.get("scene_slug")) in scenes
    }
    for scene in scenes:
        scene_production_path = episode / "review" / "v2" / scene / "scene_production.json"
        if not scene_production_path.is_file():
            continue
        scene_production = load_json(scene_production_path)
        candidate_state = str(scene_production.get("state", ""))
        current_state = str(scene_states.get(scene, ""))
        if (
            scene_production.get("scene_slug") == scene
            and PROGRESSIVE_SCENE_STATES.get(candidate_state, -1)
            > PROGRESSIVE_SCENE_STATES.get(current_state, -1)
        ):
            scene_states[scene] = candidate_state

    result: dict[str, Any] = {
        "schema": "lecture-animation-production-batch-status-v2",
        "batch_id": contract.get("batch_id"),
        "scenes": sorted(scenes),
        "production_hash_at_start": contract.get("production_hash_at_start"),
        "current_production_hash": production.get("production_hash"),
        "scene_production_states": scene_states,
        "wall_seconds": round(wall_seconds, 3),
        "measured_active_seconds": round(active_seconds, 3),
        "aggregate_agent_seconds": round(aggregate_agent_seconds, 3),
        "concurrency_overlap_seconds": round(float(measured["concurrency_overlap_seconds"]), 3),
        "human_wait_seconds": round(human_wait_seconds, 3),
        "target_active_seconds": contract.get("target_active_seconds"),
        "phase_seconds": {key: round(value, 3) for key, value in sorted(phase_seconds.items())},
        "phase_agent_seconds": {key: round(value, 3) for key, value in sorted(phase_agent_seconds.items())},
        "token_usage": measured["token_usage"],
        "phase_token_usage": measured["phase_token_usage"],
        "token_observability": token_observability,
        "tokens_per_active_minute": round(
            (
                int(measured["token_usage"].get("input_tokens", 0) or 0)
                + int(measured["token_usage"].get("output_tokens", 0) or 0)
            ) / max(active_seconds / 60.0, 1e-9),
            3,
        ) if token_observability.get("observed_events") else None,
        "cache_hit_ratio": round(
            int(measured["token_usage"].get("cached_input_tokens", 0) or 0)
            / max(int(measured["token_usage"].get("input_tokens", 0) or 0), 1),
            4,
        ) if token_observability.get("observed_events") else None,
        "review_attempts": len(attempts),
        "author_self_review_attempts": len(author_self_reviews),
        "author_self_review_gate_rejections": sum(not bool(row.get("gate_accepted")) for row in author_self_reviews),
        "findings_caught_before_independent_handoff": sum(
            int(row.get("findings_caught_before_handoff", 0) or 0) for row in author_self_reviews
        ),
        "machine_findings_caught_before_independent_handoff": sum(
            int(row.get("machine_gate_findings", 0) or 0) for row in author_self_reviews
        ),
        "independent_findings_after_self_review": sum(
            int(row.get("findings_count", 0) or 0) for row in post_self_review_attempts
        ),
        "full_reviews": full_reviews,
        "diagnostic_reviews": diagnostics,
        "review_artifact_count": artifact_count,
        "missing_phase_telemetry": missing_phases,
        "alerts": alerts,
        "within_active_budget": "ACTIVE_BUDGET_EXCEEDED" not in alerts,
    }
    result["status_hash"] = object_hash(result)
    if args.output:
        write_json(Path(args.output), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if "ACTIVE_BUDGET_EXCEEDED" in alerts else 0


def skill_tree_hash(repo_root: Path, skill_ref: str | None) -> str:
    relative = ".agents/skills/lecture-animation-pipeline-v2"
    if skill_ref:
        result = subprocess.run(
            ["git", "rev-parse", f"{skill_ref}:{relative}"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise PipelineError(f"cannot resolve skill tree at {skill_ref}: {result.stderr.strip()}")
        return result.stdout.strip()
    return artifact_snapshot(repo_root / relative, repo_root)["sha256"]


def production_metrics(episode: Path) -> dict[str, Any]:
    evolution = episode / "review" / "evolution"
    outcomes = event_rows(evolution / "events.jsonl")
    attempts = canonical_review_attempt_rows(evolution / "review_attempts.jsonl")
    author_self_reviews = event_rows(evolution / "author_self_review_attempts.jsonl")
    phases = event_rows(evolution / "production_phases.jsonl")
    scenes = sorted({str(row.get("scene_slug")) for row in [*outcomes, *attempts, *phases] if row.get("scene_slug")})
    reviewers = [str(row.get("reviewer_agent_id") or row.get("reviewer") or "") for row in attempts]
    reviewer_switches = sum(1 for left, right in zip(reviewers, reviewers[1:]) if left and right and left != right)
    self_reviewed_manifests = {
        str(row.get("manifest_hash"))
        for row in author_self_reviews
        if row.get("manifest_hash") and row.get("gate_accepted")
    }
    post_self_review_attempts = [row for row in attempts if str(row.get("manifest_hash")) in self_reviewed_manifests]
    human_judged = [row for row in outcomes if row.get("human_verdict") in {"pass", "revise"}]
    human_rejected = [row for row in human_judged if row.get("human_verdict") == "revise"]
    auto_pass_judged = [row for row in human_judged if str(row.get("automatic_verdict", "")).startswith("pass")]
    false_pass = [row for row in auto_pass_judged if row.get("human_verdict") == "revise"]
    measured_phases = phase_metrics(phases)
    phase_totals = measured_phases["phase_wall_seconds"]
    reviews_root = episode / "exports" / "reviews"
    exports = (
        [
            path
            for path in reviews_root.rglob("*.mp4")
            if clean_path(path) and (not scenes or any(scene in path.as_posix() for scene in scenes))
        ]
        if reviews_root.exists()
        else []
    )
    scene_count = len(scenes)
    return {
        "scenes_observed": scenes,
        "scene_count": scene_count,
        "outcome_events": len(outcomes),
        "review_attempts": len(attempts),
        "author_self_review_attempts": len(author_self_reviews),
        "author_self_review_gate_rejections": sum(not bool(row.get("gate_accepted")) for row in author_self_reviews),
        "findings_caught_before_independent_handoff": sum(
            int(row.get("findings_caught_before_handoff", 0) or 0) for row in author_self_reviews
        ),
        "machine_findings_caught_before_independent_handoff": sum(
            int(row.get("machine_gate_findings", 0) or 0) for row in author_self_reviews
        ),
        "independent_findings_after_self_review": sum(
            int(row.get("findings_count", 0) or 0) for row in post_self_review_attempts
        ),
        "review_attempts_per_scene": round(len(attempts) / scene_count, 3) if scene_count else None,
        "accepted_review_attempts": sum(bool(row.get("gate_accepted")) for row in attempts),
        "rejected_review_attempts": sum(not bool(row.get("gate_accepted")) for row in attempts),
        "diagnostic_review_attempts": sum(row.get("review_mode") == "diagnostic" for row in attempts),
        "full_review_attempts": sum(row.get("review_mode") in {None, "full_regression"} for row in attempts),
        "average_findings_per_attempt": mean_or_zero([float(row.get("findings_count", 0) or 0) for row in attempts]),
        "unique_reviewers": len({value for value in reviewers if value}),
        "reviewer_switches": reviewer_switches,
        "human_judged": len(human_judged),
        "human_rejections": len(human_rejected),
        "human_rejection_rate": round(len(human_rejected) / len(human_judged), 4) if human_judged else None,
        "false_passes": len(false_pass),
        "false_pass_rate": round(len(false_pass) / len(auto_pass_judged), 4) if auto_pass_judged else None,
        "phase_events": len(measured_phases["unique_events"]),
        "phase_seconds": {key: round(value, 3) for key, value in sorted(phase_totals.items())},
        "phase_agent_seconds": {
            key: round(value, 3)
            for key, value in sorted(measured_phases["phase_agent_seconds"].items())
        },
        "critical_path_minutes": round(float(measured_phases["critical_path_seconds"]) / 60.0, 3),
        "aggregate_agent_minutes": round(float(measured_phases["aggregate_agent_seconds"]) / 60.0, 3),
        "concurrency_overlap_minutes": round(float(measured_phases["concurrency_overlap_seconds"]) / 60.0, 3),
        "total_measured_minutes": round(float(measured_phases["critical_path_seconds"]) / 60.0, 3),
        "token_usage": measured_phases["token_usage"],
        "phase_token_usage": measured_phases["phase_token_usage"],
        "total_observed_tokens": int(measured_phases["token_usage"].get("input_tokens", 0) or 0)
        + int(measured_phases["token_usage"].get("output_tokens", 0) or 0),
        "uncached_input_tokens": max(
            0,
            int(measured_phases["token_usage"].get("input_tokens", 0) or 0)
            - int(measured_phases["token_usage"].get("cached_input_tokens", 0) or 0),
        ),
        "cache_hit_ratio": round(
            int(measured_phases["token_usage"].get("cached_input_tokens", 0) or 0)
            / max(int(measured_phases["token_usage"].get("input_tokens", 0) or 0), 1),
            4,
        ) if measured_phases["token_observability"]["observed_events"] else None,
        "tokens_per_scene": round(
            (
                int(measured_phases["token_usage"].get("input_tokens", 0) or 0)
                + int(measured_phases["token_usage"].get("output_tokens", 0) or 0)
            ) / scene_count,
            3,
        ) if scene_count and measured_phases["token_observability"]["coverage"] == 1.0 else None,
        "review_mp4_count": len(exports),
        "review_mp4_per_scene": round(len(exports) / scene_count, 3) if scene_count else None,
        "observability": {
            "human_outcomes_recorded": bool(human_judged),
            "phase_timing_recorded": bool(phases),
            "review_sessions_recorded": any(row.get("review_session_id") for row in attempts),
            "token_usage_coverage": measured_phases["token_observability"]["coverage"],
        },
    }


def command_snapshot_iteration(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    episode = Path(args.episode).resolve()
    snapshot = {
        "schema": "lecture-animation-skill-iteration-snapshot-v2",
        "created_at": utc_now(),
        "iteration_id": args.iteration_id,
        "label": args.label,
        "hypothesis": args.hypothesis,
        "episode": episode.name,
        "skill_ref": args.skill_ref or "working-tree",
        "skill_tree_hash": skill_tree_hash(repo_root, args.skill_ref),
        "candidate_skill_tree_hash": skill_tree_hash(repo_root, None),
        "evaluation_status": "awaiting_matched_post_snapshot" if args.skill_ref else "observed_candidate_window",
        "rules_registry_hash": object_hash(load_rules()),
        "metrics": production_metrics(episode),
        "source_logs": {},
    }
    for name in (
        "events.jsonl",
        "review_attempts.jsonl",
        "author_self_review_attempts.jsonl",
        "review_audit.jsonl",
        "production_phases.jsonl",
    ):
        path = episode / "review" / "evolution" / name
        if path.exists():
            snapshot["source_logs"][name] = artifact_snapshot(path, repo_root)
    snapshot["snapshot_hash"] = object_hash(snapshot)
    write_json(Path(args.output), snapshot)
    print(json.dumps({"snapshot": args.output, "snapshot_hash": snapshot["snapshot_hash"], "metrics": snapshot["metrics"]}, ensure_ascii=False, indent=2))
    return 0


def comparison_dimension(before: dict[str, Any], after: dict[str, Any], keys: list[str], lower_is_better: set[str]) -> dict[str, Any]:
    deltas: dict[str, Any] = {}
    signals: list[int] = []
    for key in keys:
        left, right = before.get(key), after.get(key)
        if left is None or right is None:
            deltas[key] = None
            continue
        delta = round(float(right) - float(left), 4)
        deltas[key] = delta
        if delta:
            signals.append(-1 if (key in lower_is_better and delta > 0) or (key not in lower_is_better and delta < 0) else 1)
    verdict = "insufficient_data" if not signals else ("improved" if sum(signals) > 0 else "regressed" if sum(signals) < 0 else "mixed")
    return {"verdict": verdict, "deltas": deltas}


def command_compare_iterations(args: argparse.Namespace) -> int:
    before = load_json(Path(args.before))
    after = load_json(Path(args.after))
    if not validate_hashed_record(before, "snapshot_hash") or not validate_hashed_record(after, "snapshot_hash"):
        raise PipelineError("iteration snapshot hash is invalid")
    bm, am = before.get("metrics", {}), after.get("metrics", {})
    before_observability = bm.get("observability", {})
    after_observability = am.get("observability", {})
    token_comparable = (
        float(before_observability.get("token_usage_coverage", 0.0) or 0.0) == 1.0
        and float(after_observability.get("token_usage_coverage", 0.0) or 0.0) == 1.0
    )
    efficiency_keys = [
        "review_attempts_per_scene",
        "review_mp4_per_scene",
        "reviewer_switches",
        "total_measured_minutes",
    ]
    if token_comparable:
        efficiency_keys.extend(["total_observed_tokens", "uncached_input_tokens", "tokens_per_scene"])

    def observability_score(value: dict[str, Any]) -> float:
        return sum(bool(value.get(key)) for key in ("human_outcomes_recorded", "phase_timing_recorded", "review_sessions_recorded")) + float(value.get("token_usage_coverage", 0.0) or 0.0)

    result = {
        "schema": "lecture-animation-skill-iteration-comparison-v2",
        "created_at": utc_now(),
        "before_snapshot_hash": before.get("snapshot_hash"),
        "after_snapshot_hash": after.get("snapshot_hash"),
        "quality": comparison_dimension(bm, am, ["human_rejection_rate", "false_pass_rate", "average_findings_per_attempt"], {"human_rejection_rate", "false_pass_rate"}),
        "efficiency": comparison_dimension(
            bm,
            am,
            efficiency_keys,
            {"review_attempts_per_scene", "review_mp4_per_scene", "reviewer_switches", "total_measured_minutes", "total_observed_tokens", "uncached_input_tokens", "tokens_per_scene"},
        ),
        "observability": {
            "before": before_observability,
            "after": after_observability,
            "verdict": "improved" if observability_score(after_observability) > observability_score(before_observability) else "regressed" if observability_score(after_observability) < observability_score(before_observability) else "unchanged",
        },
        "token_efficiency_comparable": token_comparable,
        "warning": "Compare similar scene batches and equal production windows; token efficiency is compared only when both windows have complete token coverage.",
    }
    result["comparison_hash"] = object_hash(result)
    if args.output:
        write_json(Path(args.output), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_record_outcome(args: argparse.Namespace) -> int:
    episode_dir = Path(args.episode).resolve()
    event_log = Path(args.event_log) if args.event_log else episode_dir / "review" / "evolution" / "events.jsonl"
    seed = f"{args.scene_slug}|{args.manifest_hash}|{utc_now()}"
    event = {
        "schema": "lecture-animation-outcome-v2",
        "event_id": f"outcome:{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:16]}",
        "created_at": utc_now(),
        "episode": episode_dir.name,
        "scene_slug": args.scene_slug,
        "author_model": args.author_model,
        "reviewer_model": args.reviewer_model,
        "automatic_verdict": args.automatic_verdict,
        "human_verdict": args.human_verdict,
        "caught_by": args.caught_by,
        "pattern_keys": args.pattern_key or [],
        "review_rounds": args.review_rounds,
        "reviewer_findings": args.reviewer_findings,
        "machine_failures": args.machine_failures,
        "human_findings": args.human_findings,
        "render_count": args.render_count,
        "minutes": args.minutes,
        "manifest_hash": args.manifest_hash,
    }
    append_jsonl(event_log, event)
    if getattr(args, "review_session", None):
        session_path = Path(args.review_session)
        load_review_session(session_path)
        if args.human_verdict == "revise" and str(args.automatic_verdict).startswith("pass"):
            record_human_false_pass(session_path, event["event_id"])
    print(json.dumps({"event_log": str(event_log), "event_id": event["event_id"]}, ensure_ascii=False))
    return 0


def mean_or_zero(values: list[float]) -> float:
    return round(statistics.fmean(values), 3) if values else 0.0


def command_evolution_report(args: argparse.Namespace) -> int:
    rows = event_rows(Path(args.event_log))
    attempt_log = Path(args.review_attempt_log) if args.review_attempt_log else Path(args.event_log).with_name("review_attempts.jsonl")
    attempts = canonical_review_attempt_rows(attempt_log)
    author_self_review_log = (
        Path(args.author_self_review_log)
        if getattr(args, "author_self_review_log", None)
        else Path(args.event_log).with_name("author_self_review_attempts.jsonl")
    )
    author_self_reviews = event_rows(author_self_review_log)
    phase_log = Path(args.phase_log) if getattr(args, "phase_log", None) else Path(args.event_log).with_name("production_phases.jsonl")
    phases = event_rows(phase_log)
    human_reviewed = [row for row in rows if row.get("human_verdict") in {"pass", "revise"}]
    human_rejected = [row for row in human_reviewed if row.get("human_verdict") == "revise"]
    auto_pass = [row for row in rows if str(row.get("automatic_verdict", "")).startswith("pass")]
    judged_auto_pass = [row for row in auto_pass if row.get("human_verdict") in {"pass", "revise"}]
    false_pass = [row for row in judged_auto_pass if row.get("human_verdict") == "revise"]
    zero_finding_pass = [row for row in auto_pass if int(row.get("reviewer_findings", 0) or 0) == 0]

    pattern_stats: defaultdict[str, dict[str, Any]] = defaultdict(lambda: {"events": 0, "human_misses": 0, "caught_by": Counter()})
    for row in rows:
        for pattern in row.get("pattern_keys", []):
            item = pattern_stats[str(pattern)]
            item["events"] += 1
            item["caught_by"][str(row.get("caught_by", "unknown"))] += 1
            if str(row.get("automatic_verdict", "")).startswith("pass") and row.get("human_verdict") == "revise":
                item["human_misses"] += 1
    patterns = []
    for pattern, stats in pattern_stats.items():
        patterns.append(
            {
                "pattern_key": pattern,
                "events": stats["events"],
                "human_misses": stats["human_misses"],
                "caught_by": dict(stats["caught_by"]),
                "promotion_candidate": stats["events"] >= 2 or stats["human_misses"] >= 1,
            }
        )
    patterns.sort(key=lambda item: (-item["human_misses"], -item["events"], item["pattern_key"]))

    reviewer_models = sorted({str(row.get("reviewer_model", "")) for row in rows if row.get("reviewer_model")})
    accepted_attempts = [row for row in attempts if row.get("gate_accepted")]
    rejected_attempts = [row for row in attempts if not row.get("gate_accepted")]
    measured_phases = phase_metrics(phases)
    phase_totals = measured_phases["phase_wall_seconds"]
    reviewer_sequence = [str(row.get("reviewer_agent_id") or row.get("reviewer") or "") for row in attempts]
    reviewer_switches = sum(1 for left, right in zip(reviewer_sequence, reviewer_sequence[1:]) if left and right and left != right)
    self_reviewed_manifests = {
        str(row.get("manifest_hash"))
        for row in author_self_reviews
        if row.get("manifest_hash") and row.get("gate_accepted")
    }
    post_self_review_attempts = [row for row in attempts if str(row.get("manifest_hash")) in self_reviewed_manifests]
    report = {
        "schema": "lecture-animation-evolution-report-v2",
        "event_log": args.event_log,
        "review_attempt_log": str(attempt_log),
        "author_self_review_log": str(author_self_review_log),
        "phase_log": str(phase_log),
        "events": len(rows),
        "review_attempts": len(attempts),
        "author_self_review_attempts": len(author_self_reviews),
        "author_self_review_gate_rejections": sum(not bool(row.get("gate_accepted")) for row in author_self_reviews),
        "findings_caught_before_independent_handoff": sum(
            int(row.get("findings_caught_before_handoff", 0) or 0) for row in author_self_reviews
        ),
        "machine_findings_caught_before_independent_handoff": sum(
            int(row.get("machine_gate_findings", 0) or 0) for row in author_self_reviews
        ),
        "independent_findings_after_self_review": sum(
            int(row.get("findings_count", 0) or 0) for row in post_self_review_attempts
        ),
        "independent_revise_after_self_review_rate": round(
            sum(row.get("verdict") == "revise" for row in post_self_review_attempts) / len(post_self_review_attempts),
            4,
        ) if post_self_review_attempts else 0.0,
        "review_attempts_gate_accepted": len(accepted_attempts),
        "review_attempts_gate_rejected": len(rejected_attempts),
        "review_attempt_gate_rejection_rate": round(len(rejected_attempts) / len(attempts), 4) if attempts else 0.0,
        "average_findings_per_review_attempt": mean_or_zero([float(row.get("findings_count", 0) or 0) for row in attempts]),
        "diagnostic_review_attempts": sum(row.get("review_mode") == "diagnostic" for row in attempts),
        "full_review_attempts": sum(row.get("review_mode") in {None, "full_regression"} for row in attempts),
        "reviewer_switches": reviewer_switches,
        "human_reviewed": len(human_reviewed),
        "human_rejections": len(human_rejected),
        "human_rejection_rate": round(len(human_rejected) / len(human_reviewed), 4) if human_reviewed else 0.0,
        "automatic_passes": len(auto_pass),
        "automatic_passes_human_reviewed": len(judged_auto_pass),
        "false_passes": len(false_pass),
        "pardon_rate": round(len(false_pass) / len(judged_auto_pass), 4) if judged_auto_pass else 0.0,
        "zero_finding_pass_rate": round(len(zero_finding_pass) / len(auto_pass), 4) if auto_pass else 0.0,
        "average_review_rounds": mean_or_zero([float(row.get("review_rounds", 0) or 0) for row in rows]),
        "average_reviewer_findings": mean_or_zero([float(row.get("reviewer_findings", 0) or 0) for row in rows]),
        "average_render_count": mean_or_zero([float(row.get("render_count", 0) or 0) for row in rows]),
        "average_minutes": mean_or_zero([float(row.get("minutes", 0) or 0) for row in rows]),
        "measured_phase_events": len(measured_phases["unique_events"]),
        "measured_phase_seconds": {key: round(value, 3) for key, value in sorted(phase_totals.items())},
        "measured_total_minutes": round(float(measured_phases["critical_path_seconds"]) / 60.0, 3),
        "aggregate_agent_minutes": round(float(measured_phases["aggregate_agent_seconds"]) / 60.0, 3),
        "concurrency_overlap_minutes": round(float(measured_phases["concurrency_overlap_seconds"]) / 60.0, 3),
        "token_usage": measured_phases["token_usage"],
        "phase_token_usage": measured_phases["phase_token_usage"],
        "token_observability": measured_phases["token_observability"],
        "total_observed_tokens": int(measured_phases["token_usage"].get("input_tokens", 0) or 0)
        + int(measured_phases["token_usage"].get("output_tokens", 0) or 0),
        "uncached_input_tokens": max(
            0,
            int(measured_phases["token_usage"].get("input_tokens", 0) or 0)
            - int(measured_phases["token_usage"].get("cached_input_tokens", 0) or 0),
        ),
        "reviewers": [reviewer_health(rows, model) for model in reviewer_models],
        "patterns": patterns,
    }
    if args.output:
        write_json(Path(args.output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    text_freeze_parser = subparsers.add_parser(
        "freeze-text-inventory",
        help="freeze the exact on-screen text constructor inventory of an approved baseline",
    )
    text_freeze_parser.add_argument("--repo-root", default=".")
    text_freeze_parser.add_argument("--scene-slug", required=True)
    text_freeze_parser.add_argument("--baseline-label", required=True)
    text_freeze_parser.add_argument("--source", required=True)
    text_freeze_parser.add_argument("--output", required=True)
    text_freeze_parser.set_defaults(func=command_freeze_text_inventory)

    text_verify_parser = subparsers.add_parser(
        "verify-text-inventory",
        help="block candidate review when on-screen text differs from the frozen baseline",
    )
    text_verify_parser.add_argument("--repo-root", default=".")
    text_verify_parser.add_argument("--scene-slug", required=True)
    text_verify_parser.add_argument("--source", required=True)
    text_verify_parser.add_argument("--baseline", required=True)
    text_verify_parser.add_argument("--output", required=True)
    text_verify_parser.set_defaults(func=command_verify_text_inventory)

    index_parser = subparsers.add_parser("index-history", help="build a disposable JSONL index from live production history")
    index_parser.add_argument("--repo-root", default=".")
    index_parser.add_argument("--output", required=True)
    index_parser.set_defaults(func=command_index_history)

    search_parser = subparsers.add_parser("search-history", help="search live storyboards, timelines, source packages, and review records")
    search_parser.add_argument("--repo-root", default=".")
    search_parser.add_argument("--query", required=True)
    search_parser.add_argument("--limit", type=int, default=8)
    search_parser.add_argument("--index")
    search_parser.add_argument("--types", help="comma-separated record types")
    search_parser.add_argument("--json", action="store_true")
    search_parser.set_defaults(func=command_search_history)

    profile_parser = subparsers.add_parser("compile-profile", help="compile only the rules and regressions relevant to one timeline scene")
    profile_parser.add_argument("--repo-root", default=".")
    profile_parser.add_argument("--episode", required=True)
    profile_parser.add_argument("--scene-slug", required=True)
    profile_parser.add_argument("--tags", action="append", default=[])
    profile_parser.add_argument("--regression-limit", type=int, default=12)
    profile_parser.add_argument("--live-policy-output")
    profile_parser.add_argument("--output", required=True)
    profile_parser.set_defaults(func=command_compile_profile)

    production_init_parser = subparsers.add_parser(
        "init-progressive-production",
        help="initialize a coarse episode tracker from the current timeline without synthesizing future scenes",
    )
    production_init_parser.add_argument("--repo-root", default=".")
    production_init_parser.add_argument("--episode", required=True)
    production_init_parser.add_argument("--lecture-notes", required=True)
    production_init_parser.add_argument("--narration-outline", required=True)
    production_init_parser.add_argument("--storyboard", required=True)
    production_init_parser.add_argument("--output")
    production_init_parser.set_defaults(func=command_init_progressive_production)

    production_parser = subparsers.add_parser(
        "seal-progressive-production",
        help="seal the coarse episode plan plus independently evolving scene-local audio states",
    )
    production_parser.add_argument("--repo-root", default=".")
    production_parser.add_argument("--input", required=True)
    production_parser.add_argument("--output")
    production_parser.set_defaults(func=command_seal_progressive_production)

    narration_qc_parser = subparsers.add_parser(
        "seal-narration-qc",
        help="bind novice script review, full audio listening, exact ASR transcript, subtitles, word timing, and timeline duration",
    )
    narration_qc_parser.add_argument("--repo-root", default=".")
    narration_qc_parser.add_argument("--scene-slug", required=True)
    narration_qc_parser.add_argument("--episode-spine", required=True)
    narration_qc_parser.add_argument("--script", required=True)
    narration_qc_parser.add_argument("--audio", required=True)
    narration_qc_parser.add_argument("--reader-srt", required=True)
    narration_qc_parser.add_argument("--word-srt", required=True)
    narration_qc_parser.add_argument("--word-alignment", required=True)
    narration_qc_parser.add_argument("--timeline-fragment", required=True)
    narration_qc_parser.add_argument("--asr-transcript", required=True)
    narration_qc_parser.add_argument("--review-draft", required=True)
    narration_qc_parser.add_argument("--output", required=True)
    narration_qc_parser.set_defaults(func=command_seal_narration_qc)

    scene_production_parser = subparsers.add_parser(
        "extract-scene-production",
        help="freeze one audio-aligned scene without locking or moving the rest of the episode timeline",
    )
    scene_production_parser.add_argument("--repo-root", default=".")
    scene_production_parser.add_argument("--production", required=True)
    scene_production_parser.add_argument("--scene-slug", required=True)
    scene_production_parser.add_argument("--output", required=True)
    scene_production_parser.set_defaults(func=command_extract_scene_production)

    registry_parser = subparsers.add_parser(
        "compile-scene-registry",
        help="compile the plan and exact scene media into one execution registry consumed by code and telemetry",
    )
    registry_parser.add_argument("--repo-root", default=".")
    registry_parser.add_argument("--profile", required=True)
    registry_parser.add_argument("--plan", required=True)
    registry_parser.add_argument("--scene-production", required=True)
    registry_parser.add_argument("--output", required=True)
    registry_parser.set_defaults(func=command_compile_scene_registry)

    workspace_parser = subparsers.add_parser(
        "prepare-review-workspace",
        help="create canonical current review paths so derived media is replaced instead of versioned indefinitely",
    )
    workspace_parser.add_argument("--repo-root", default=".")
    workspace_parser.add_argument("--episode", required=True)
    workspace_parser.add_argument("--scene-slug", required=True)
    workspace_parser.add_argument("--output")
    workspace_parser.set_defaults(func=command_prepare_review_workspace)

    policy_parser = subparsers.add_parser(
        "compile-live-policy",
        help="compile all applicable human and accepted-agent feedback into an immediate hash-bound overlay",
    )
    policy_parser.add_argument("--repo-root", default=".")
    policy_parser.add_argument("--episode", required=True)
    policy_parser.add_argument("--profile", required=True)
    policy_parser.add_argument("--output", required=True)
    policy_parser.set_defaults(func=command_compile_live_policy)

    begin_design_parser = subparsers.add_parser(
        "begin-design",
        help="create a scene-specific first-principles challenge while withholding precedent hits",
    )
    begin_design_parser.add_argument("--profile", required=True)
    begin_design_parser.add_argument("--output", required=True)
    begin_design_parser.set_defaults(func=command_begin_design)

    deliberation_parser = subparsers.add_parser(
        "validate-design-deliberation",
        help="gate scene-specific novice reasoning and materially different visual hypotheses before retrieval",
    )
    deliberation_parser.add_argument("--profile", required=True)
    deliberation_parser.add_argument("--challenge", required=True)
    deliberation_parser.add_argument("--deliberation", required=True)
    deliberation_parser.add_argument("--output", required=True)
    deliberation_parser.set_defaults(func=command_validate_design_deliberation)

    retrieve_parser = subparsers.add_parser(
        "retrieve-design",
        help="retrieve reviewed production precedents and old-skill guidance only after the design gate passes",
    )
    retrieve_parser.add_argument("--repo-root", default=".")
    retrieve_parser.add_argument("--profile", required=True)
    retrieve_parser.add_argument("--deliberation", required=True)
    retrieve_parser.add_argument("--design-gate", required=True)
    retrieve_parser.add_argument("--production-limit", type=int, default=6)
    retrieve_parser.add_argument("--guidance-limit", type=int, default=4)
    retrieve_parser.add_argument("--output", required=True)
    retrieve_parser.set_defaults(func=command_retrieve_design)

    plan_parser = subparsers.add_parser("validate-scene-plan", help="validate stage orchestration against a compiled profile")
    plan_parser.add_argument("--profile", required=True)
    plan_parser.add_argument("--plan", required=True)
    plan_parser.add_argument("--challenge", required=True)
    plan_parser.add_argument("--deliberation", required=True)
    plan_parser.add_argument("--design-gate", required=True)
    plan_parser.add_argument("--precedent-packet", required=True)
    plan_parser.add_argument("--episode-spine", required=True)
    plan_parser.add_argument("--batch-plan", required=True)
    plan_parser.set_defaults(func=command_validate_scene_plan)

    authoring_parser = subparsers.add_parser(
        "validate-authoring-qc",
        help="reject runtime layout, typography, timing, transition, and stale-object failures before review",
    )
    authoring_parser.add_argument("--profile", required=True)
    authoring_parser.add_argument("--plan", required=True)
    authoring_parser.add_argument("--telemetry", required=True)
    authoring_parser.add_argument("--output", required=True)
    authoring_parser.set_defaults(func=command_validate_authoring_qc)

    freeze_parser = subparsers.add_parser("freeze-review", help="hash-bind the exact candidate sent to review")
    freeze_parser.add_argument("--repo-root", default=".")
    freeze_parser.add_argument("--episode", required=True)
    freeze_parser.add_argument("--scene-slug", required=True)
    freeze_parser.add_argument("--profile", required=True)
    freeze_parser.add_argument("--artifact", action="append", default=[], help="key=path; repeat for every artifact")
    freeze_parser.add_argument("--output", required=True)
    freeze_parser.set_defaults(func=command_freeze_review)

    manifest_parser = subparsers.add_parser("verify-manifest", help="reject stale or incomplete review artifacts")
    manifest_parser.add_argument("--repo-root", default=".")
    manifest_parser.add_argument("--manifest", required=True)
    manifest_parser.set_defaults(func=command_verify_manifest)

    probe_draft_parser = subparsers.add_parser(
        "prepare-self-review-probe",
        help="generate adversarial four-layer falsification probes from the frozen candidate",
    )
    probe_draft_parser.add_argument("--repo-root", default=".")
    probe_draft_parser.add_argument("--manifest", required=True)
    probe_draft_parser.add_argument("--output", required=True)
    probe_draft_parser.set_defaults(func=command_prepare_self_review_probe)

    probe_seal_parser = subparsers.add_parser(
        "seal-self-review-probe",
        help="reject self-review probes without independent frame and recomputation evidence",
    )
    probe_seal_parser.add_argument("--repo-root", default=".")
    probe_seal_parser.add_argument("--manifest", required=True)
    probe_seal_parser.add_argument("--input", required=True)
    probe_seal_parser.add_argument("--output")
    probe_seal_parser.set_defaults(func=command_seal_self_review_probe)

    self_review_draft_parser = subparsers.add_parser(
        "prepare-author-self-review",
        help="generate a hash-bound self-review draft with anchors, artifact hashes, and prior findings prefilled",
    )
    self_review_draft_parser.add_argument("--repo-root", default=".")
    self_review_draft_parser.add_argument("--manifest", required=True)
    self_review_draft_parser.add_argument("--owner", required=True)
    self_review_draft_parser.add_argument("--author-agent-id", required=True)
    self_review_draft_parser.add_argument("--author-model", required=True)
    self_review_draft_parser.add_argument("--self-review-round", type=int, default=1)
    self_review_draft_parser.add_argument("--self-review-probe", required=True)
    self_review_draft_parser.add_argument("--previous-review")
    self_review_draft_parser.add_argument("--repair-contract")
    self_review_draft_parser.add_argument("--repair-response")
    self_review_draft_parser.add_argument("--repair-gate")
    self_review_draft_parser.add_argument("--output", required=True)
    self_review_draft_parser.set_defaults(func=command_prepare_author_self_review)

    self_review_parser = subparsers.add_parser(
        "seal-author-self-review",
        help="bind the author's full self-review to the frozen candidate before independent review",
    )
    self_review_parser.add_argument("--repo-root", default=".")
    self_review_parser.add_argument("--manifest", required=True)
    self_review_parser.add_argument("--input", required=True)
    self_review_parser.add_argument("--previous-review")
    self_review_parser.add_argument("--repair-contract")
    self_review_parser.add_argument("--repair-response")
    self_review_parser.add_argument("--repair-gate")
    self_review_parser.add_argument("--attempt-log")
    self_review_parser.add_argument("--output", required=True)
    self_review_parser.set_defaults(func=command_seal_author_self_review)

    benchmark_seal_parser = subparsers.add_parser(
        "seal-reviewer-benchmark",
        help="bind a reviewer admission benchmark to the current rules registry",
    )
    benchmark_seal_parser.add_argument("--input", required=True)
    benchmark_seal_parser.add_argument("--output")
    benchmark_seal_parser.set_defaults(func=command_seal_reviewer_benchmark)

    certify_parser = subparsers.add_parser(
        "certify-reviewer",
        help="admit a light reviewer only after measured critical-failure recall and false-pass checks",
    )
    certify_parser.add_argument("--benchmark", required=True)
    certify_parser.add_argument("--submission", required=True)
    certify_parser.add_argument("--output", required=True)
    certify_parser.set_defaults(func=command_certify_reviewer)

    capsule_parser = subparsers.add_parser(
        "prepare-review-capsule",
        help="compile a compact hash-bound reviewer packet instead of replaying the full policy corpus",
    )
    capsule_parser.add_argument("--repo-root", default=".")
    capsule_parser.add_argument("--manifest", required=True)
    capsule_parser.add_argument("--author-self-review", required=True)
    capsule_parser.add_argument("--previous-review")
    capsule_parser.add_argument("--repair-contract")
    capsule_parser.add_argument("--repair-response")
    capsule_parser.add_argument("--repair-gate")
    capsule_parser.add_argument("--review-session", required=True)
    capsule_parser.add_argument("--output", required=True)
    capsule_parser.set_defaults(func=command_prepare_review_capsule)

    blind_parser = subparsers.add_parser(
        "seal-blind-review",
        help="seal novice observations before the reviewer may inspect contracts and source",
    )
    blind_parser.add_argument("--capsule", required=True)
    blind_parser.add_argument("--blind-review", required=True)
    blind_parser.add_argument("--review-session", required=True)
    blind_parser.add_argument("--output", required=True)
    blind_parser.set_defaults(func=command_seal_blind_review)

    review_parser = subparsers.add_parser("verify-review", help="validate independent evidence-bound review")
    review_parser.add_argument("--repo-root", default=".")
    review_parser.add_argument("--manifest", required=True)
    review_parser.add_argument("--review", required=True)
    review_parser.add_argument("--author-self-review", required=True)
    review_parser.add_argument("--previous-review")
    review_parser.add_argument("--repair-contract")
    review_parser.add_argument("--repair-response")
    review_parser.add_argument("--repair-gate")
    review_parser.add_argument("--review-session", required=True, help="persistent reviewer batch session")
    review_parser.add_argument("--review-capsule")
    review_parser.add_argument("--blind-receipt")
    review_parser.add_argument("--event-log")
    review_parser.add_argument("--attempt-log", help="canonical review_attempts.jsonl path")
    review_parser.add_argument("--audit-log", help=argparse.SUPPRESS)
    review_parser.set_defaults(func=command_verify_review)

    exhaustion_draft_parser = subparsers.add_parser(
        "prepare-review-exhaustion",
        help="group every revise finding by root cause and generate a completeness audit draft",
    )
    exhaustion_draft_parser.add_argument("--repo-root", default=".")
    exhaustion_draft_parser.add_argument("--review", required=True)
    exhaustion_draft_parser.add_argument("--manifest", required=True)
    exhaustion_draft_parser.add_argument("--output", required=True)
    exhaustion_draft_parser.set_defaults(func=command_prepare_review_exhaustion)

    exhaustion_seal_parser = subparsers.add_parser(
        "seal-review-exhaustion",
        help="block partial revise reports until root causes, siblings, artifacts, and all gate layers are exhausted",
    )
    exhaustion_seal_parser.add_argument("--repo-root", default=".")
    exhaustion_seal_parser.add_argument("--review", required=True)
    exhaustion_seal_parser.add_argument("--manifest", required=True)
    exhaustion_seal_parser.add_argument("--input", required=True)
    exhaustion_seal_parser.add_argument("--output")
    exhaustion_seal_parser.set_defaults(func=command_seal_review_exhaustion)

    batch_parser = subparsers.add_parser("begin-review-batch", help="bind one independent reviewer session to a scene batch")
    batch_parser.add_argument("--repo-root", default=".")
    batch_parser.add_argument("--episode-spine", required=True)
    batch_parser.add_argument(
        "--review-role",
        choices=["acceptance", "diagnostic_support"],
        default="acceptance",
        help="only acceptance review may grant pass_for_user_review_pending",
    )
    batch_parser.add_argument("--batch-id", required=True)
    batch_parser.add_argument("--owner", required=True)
    batch_parser.add_argument("--author-agent-id", required=True)
    batch_parser.add_argument("--reviewer", required=True)
    batch_parser.add_argument("--reviewer-model", required=True)
    batch_parser.add_argument("--reviewer-tier", choices=["frontier", "light"], default="frontier")
    batch_parser.add_argument("--reasoning-effort", choices=["low", "medium", "high", "xhigh"], default="medium")
    batch_parser.add_argument("--certification", help="required for --reviewer-tier light")
    batch_parser.add_argument("--escalation-model", default="gpt-5.6-sol")
    batch_parser.add_argument("--reviewer-agent-id", required=True)
    batch_parser.add_argument("--calibration-scene-interval", type=int, default=5)
    batch_parser.add_argument("--replace", action="store_true")
    batch_parser.add_argument("--replace-reason")
    batch_parser.add_argument("--output", required=True)
    batch_parser.set_defaults(func=command_begin_review_batch)

    mode_parser = subparsers.add_parser(
        "choose-review-mode",
        help="choose diagnostic or full review from changed hash-bound contracts without imposing a fixed review cap",
    )
    mode_parser.add_argument("--previous-manifest", required=True)
    mode_parser.add_argument("--current-manifest", required=True)
    mode_parser.add_argument("--previous-review", required=True)
    mode_parser.add_argument("--review-session", required=True)
    mode_parser.add_argument("--attempt-log")
    mode_parser.add_argument("--change-impact")
    mode_parser.add_argument("--output", required=True)
    mode_parser.set_defaults(func=command_choose_review_mode)

    diagnostic_parser = subparsers.add_parser(
        "prepare-diagnostic-review",
        help="compile hash-bound repair windows and regression samples for the same reviewer",
    )
    diagnostic_parser.add_argument("--repo-root", default=".")
    diagnostic_parser.add_argument("--previous-manifest", required=True)
    diagnostic_parser.add_argument("--current-manifest", required=True)
    diagnostic_parser.add_argument("--previous-review", required=True)
    diagnostic_parser.add_argument("--author-self-review", required=True)
    diagnostic_parser.add_argument("--review-session", required=True)
    diagnostic_parser.add_argument("--change-impact", required=True)
    diagnostic_parser.add_argument("--margin", type=float, default=1.0)
    diagnostic_parser.add_argument("--output", required=True)
    diagnostic_parser.set_defaults(func=command_prepare_diagnostic_review)

    diagnostic_verify_parser = subparsers.add_parser(
        "verify-diagnostic-review",
        help="verify repair findings and unchanged-region samples without granting final pass",
    )
    diagnostic_verify_parser.add_argument("--episode", required=True)
    diagnostic_verify_parser.add_argument("--packet", required=True)
    diagnostic_verify_parser.add_argument("--submission", required=True)
    diagnostic_verify_parser.add_argument("--review-session", required=True)
    diagnostic_verify_parser.add_argument("--attempt-log")
    diagnostic_verify_parser.set_defaults(func=command_verify_diagnostic_review)

    impact_parser = subparsers.add_parser(
        "seal-change-impact",
        help="bind localized repair objects, windows, and layers to two frozen manifests",
    )
    impact_parser.add_argument("--previous-manifest", required=True)
    impact_parser.add_argument("--current-manifest", required=True)
    impact_parser.add_argument("--input", required=True)
    impact_parser.add_argument("--output")
    impact_parser.set_defaults(func=command_seal_change_impact)

    repair_contract_parser = subparsers.add_parser(
        "compile-repair-contract",
        help="turn every independent revise finding into a hash-bound code-level repair contract",
    )
    repair_contract_parser.add_argument("--repo-root", default=".")
    repair_contract_parser.add_argument("--review", required=True)
    repair_contract_parser.add_argument("--manifest", required=True)
    repair_contract_parser.add_argument("--output", required=True)
    repair_contract_parser.set_defaults(func=command_compile_repair_contract)

    repair_response_parser = subparsers.add_parser(
        "prepare-repair-response",
        help="prepare the author's exact per-finding repair response against a newly frozen candidate",
    )
    repair_response_parser.add_argument("--repair-contract", required=True)
    repair_response_parser.add_argument("--current-manifest", required=True)
    repair_response_parser.add_argument("--output", required=True)
    repair_response_parser.set_defaults(func=command_prepare_repair_response)

    repair_verify_parser = subparsers.add_parser(
        "verify-repair-response",
        help="block self-review until every repair, preservation check, and new-risk probe has evidence",
    )
    repair_verify_parser.add_argument("--repair-contract", required=True)
    repair_verify_parser.add_argument("--repair-response", required=True)
    repair_verify_parser.add_argument("--current-manifest", required=True)
    repair_verify_parser.add_argument("--attempt-log")
    repair_verify_parser.add_argument("--output", required=True)
    repair_verify_parser.set_defaults(func=command_verify_repair_response)

    state_parser = subparsers.add_parser("gate-status", help="derive and persist state from profile, plan, manifest, and review evidence")
    state_parser.add_argument("--repo-root", default=".")
    state_parser.add_argument("--profile")
    state_parser.add_argument("--plan")
    state_parser.add_argument("--challenge")
    state_parser.add_argument("--deliberation")
    state_parser.add_argument("--design-gate")
    state_parser.add_argument("--precedent-packet")
    state_parser.add_argument("--manifest")
    state_parser.add_argument("--author-self-review")
    state_parser.add_argument("--previous-review")
    state_parser.add_argument("--review")
    state_parser.add_argument("--review-session")
    state_parser.add_argument("--review-capsule")
    state_parser.add_argument("--blind-receipt")
    state_parser.add_argument("--event-log")
    state_parser.add_argument("--output")
    state_parser.set_defaults(func=command_gate_status)

    outcome_parser = subparsers.add_parser("record-outcome", help="append a durable human/automatic review outcome event")
    outcome_parser.add_argument("--episode", required=True)
    outcome_parser.add_argument("--event-log")
    outcome_parser.add_argument("--review-session", help="mark calibration due after a human false pass")
    outcome_parser.add_argument("--scene-slug", required=True)
    outcome_parser.add_argument("--author-model", required=True)
    outcome_parser.add_argument("--reviewer-model", required=True)
    outcome_parser.add_argument("--automatic-verdict", choices=["revise", "pass_for_user_review_pending"], required=True)
    outcome_parser.add_argument("--human-verdict", choices=["pass", "revise", "pending"], required=True)
    outcome_parser.add_argument("--caught-by", choices=["author", "machine", "reviewer", "human"], required=True)
    outcome_parser.add_argument("--pattern-key", action="append", default=[])
    outcome_parser.add_argument("--review-rounds", type=int, default=1)
    outcome_parser.add_argument("--reviewer-findings", type=int, default=0)
    outcome_parser.add_argument("--machine-failures", type=int, default=0)
    outcome_parser.add_argument("--human-findings", type=int, default=0)
    outcome_parser.add_argument("--render-count", type=int, default=1)
    outcome_parser.add_argument("--minutes", type=float, default=0.0)
    outcome_parser.add_argument("--manifest-hash", default="")
    outcome_parser.set_defaults(func=command_record_outcome)

    phase_start_parser = subparsers.add_parser("phase-start", help="start one durable production phase timer")
    phase_start_parser.add_argument("--run-id", required=True)
    phase_start_parser.add_argument("--scene-slug", required=True)
    phase_start_parser.add_argument("--phase", choices=sorted(PHASES), required=True)
    phase_start_parser.add_argument("--actor-model", required=True)
    phase_start_parser.add_argument("--actor-role", default="unspecified")
    phase_start_parser.add_argument("--reasoning-effort", default="unspecified")
    phase_start_parser.add_argument("--phase-instance-id")
    phase_start_parser.add_argument("--prompt-bytes", type=int, default=0)
    phase_start_parser.add_argument("--artifact-input-bytes", type=int, default=0)
    phase_start_parser.add_argument("--files-read", type=int, default=0)
    phase_start_parser.add_argument("--usage-file", help="cumulative usage JSON/JSONL; Codex rollout is auto-discovered when omitted")
    phase_start_parser.add_argument("--previous-review", help="required when --phase repair")
    phase_start_parser.add_argument("--repair-contract", help="required when --phase repair")
    phase_start_parser.add_argument("--state", required=True)
    phase_start_parser.set_defaults(func=command_phase_start)

    phase_end_parser = subparsers.add_parser("phase-end", help="close a phase timer and append measured duration")
    phase_end_parser.add_argument("--state", required=True)
    phase_end_parser.add_argument("--phase-log", required=True)
    phase_end_parser.add_argument("--result", choices=["completed", "blocked", "abandoned"], default="completed")
    phase_end_parser.add_argument("--manifest-hash", default="")
    phase_end_parser.add_argument("--usage-file", help="override the usage source captured at phase-start")
    phase_end_parser.add_argument("--repair-response", help="required to complete a repair phase")
    phase_end_parser.add_argument("--repair-gate", help="required to complete a repair phase")
    phase_end_parser.add_argument("--current-manifest", help="required to complete a repair phase")
    for token_field in TOKEN_FIELDS:
        phase_end_parser.add_argument(f"--{token_field.replace('_', '-')}", type=int)
    phase_end_parser.set_defaults(func=command_phase_end)

    production_batch_parser = subparsers.add_parser(
        "begin-production-batch",
        help="start a hash-bound scene batch with a five-hour active-work budget",
    )
    production_batch_parser.add_argument("--repo-root", default=".")
    production_batch_parser.add_argument("--episode", required=True)
    production_batch_parser.add_argument("--batch-id", required=True)
    production_batch_parser.add_argument("--scenes", required=True, help="comma-separated scene slugs")
    production_batch_parser.add_argument("--episode-spine", required=True)
    production_batch_parser.add_argument("--batch-plan", required=True)
    production_batch_parser.add_argument("--production", required=True)
    production_batch_parser.add_argument("--author-id", help="immutable production author identity; required in parallel_batches mode")
    production_batch_parser.add_argument("--target-hours", type=float, default=5.0)
    production_batch_parser.add_argument("--episode-target-hours", type=float, default=24.0)
    production_batch_parser.add_argument("--output", required=True)
    production_batch_parser.set_defaults(func=command_begin_production_batch)

    seal_planning_parser = subparsers.add_parser(
        "seal-planning-artifact",
        help="write the canonical hash for an episode spine or batch visual plan",
    )
    seal_planning_parser.add_argument("--input", required=True)
    seal_planning_parser.add_argument("--output")
    seal_planning_parser.set_defaults(func=command_seal_planning_artifact)

    batch_status_parser = subparsers.add_parser(
        "batch-status",
        help="measure active time, review mix, artifact growth, and missing outcome telemetry for a production batch",
    )
    batch_status_parser.add_argument("--repo-root", default=".")
    batch_status_parser.add_argument("--batch", required=True)
    batch_status_parser.add_argument("--output")
    batch_status_parser.set_defaults(func=command_batch_status)

    report_parser = subparsers.add_parser("evolution-report", help="report rejection, false-pass, reviewer, and recurrence metrics")
    report_parser.add_argument("--event-log", required=True)
    report_parser.add_argument("--review-attempt-log")
    report_parser.add_argument("--author-self-review-log")
    report_parser.add_argument("--phase-log")
    report_parser.add_argument("--output")
    report_parser.set_defaults(func=command_evolution_report)

    snapshot_parser = subparsers.add_parser("snapshot-iteration", help="write an immutable quantitative skill-iteration baseline")
    snapshot_parser.add_argument("--repo-root", default=".")
    snapshot_parser.add_argument("--episode", required=True)
    snapshot_parser.add_argument("--iteration-id", required=True)
    snapshot_parser.add_argument("--label", required=True)
    snapshot_parser.add_argument("--hypothesis", required=True)
    snapshot_parser.add_argument("--skill-ref")
    snapshot_parser.add_argument("--output", required=True)
    snapshot_parser.set_defaults(func=command_snapshot_iteration)

    compare_parser = subparsers.add_parser("compare-iterations", help="compare quality, efficiency, and observability separately")
    compare_parser.add_argument("--before", required=True)
    compare_parser.add_argument("--after", required=True)
    compare_parser.add_argument("--output")
    compare_parser.set_defaults(func=command_compare_iterations)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except PipelineError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
