#!/usr/bin/env python3
"""Design-stage preflight gate for myLectures animation scenes.

This gate runs before Manim implementation or review.  It catches the failures
that are too easy to miss after a scene already renders: batched user-review
handoffs, monolithic scene files, missing authoring use of human feedback, and
formula-only motion plans without a visible mathematical driver.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = SKILL_DIR / "tools"

REQUIRED_COMPONENT_FILES = [
    "contract.yaml",
    "drivers.py",
    "objects.py",
    "layout.py",
    "beats.py",
    "composer.py",
    "audit.py",
]

MOTION_LEDGER_FIELDS = [
    "beat",
    "spoken_anchor",
    "math_object",
    "driver",
    "visible_change",
    "qc_frame",
]

AUTHORING_PREFLIGHT_FIELDS = [
    "regression_records",
    "avoidance_plan",
]

HUMAN_REJECTED_MIN_CANDIDATE_FLAGS = 18
HUMAN_REJECTED_MIN_AESTHETIC_FLAGS = 7


class PreflightError(Exception):
    """Human-readable preflight validation failure."""


def is_macos_metadata(path: Path) -> bool:
    return path.name.startswith("._") or path.name == ".DS_Store"


def load_yaml(path: Path) -> Any:
    try:
        import yaml  # type: ignore
    except ImportError:
        try:
            from validate_scene_contract import ContractError, parse_simple_yaml
        except Exception as exc:
            raise PreflightError(
                "PyYAML is not installed and the bundled YAML fallback could not be loaded"
            ) from exc
        try:
            return parse_simple_yaml(path.read_text(encoding="utf-8"))
        except ContractError as exc:
            raise PreflightError(f"{path}: could not parse YAML: {exc}") from exc
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PreflightError(f"{path}: could not parse YAML: {exc}") from exc


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise PreflightError(f"{path}: file is not valid UTF-8: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PreflightError(f"{path}: invalid JSON: {exc}") from exc


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def scene_matches_issue(scene_slug: str, issue: dict[str, Any]) -> bool:
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
    return (
        scene_text == scene_slug
        or scene_slug in scene_text
        or scene_text in scene_slug
    )


def collect_regression_issues(episode_dir: Path, scene_slug: str) -> list[Path]:
    issue_dir = episode_dir / "review" / "issues"
    if not issue_dir.exists():
        return []
    paths: list[Path] = []
    for path in sorted(issue_dir.glob("*.json")):
        if is_macos_metadata(path):
            continue
        issue = load_json(path)
        if not isinstance(issue, dict):
            continue
        source = issue.get("source")
        future = (
            source in {"human_review", "accepted_agent_feedback"}
            or issue.get("status") == "open"
            or (
                issue.get("must_check_in_future") is True
                and issue.get("applies_to_authoring") is True
            )
        )
        if future and scene_matches_issue(scene_slug, issue):
            paths.append(path)
    return paths


def python_class_names(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    except SyntaxError as exc:
        raise PreflightError(f"{path}: syntax error: {exc}") from exc
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if any(
                isinstance(base, ast.Name) and base.id.endswith("Scene")
                or isinstance(base, ast.Attribute) and base.attr.endswith("Scene")
                for base in node.bases
            ):
                names.append(node.name)
    return names


def forbidden_scene_calls(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    found: list[str] = []
    for needle in ["self.play(", "scene.play(", ".play(", "self.wait(", "scene.wait(", ".wait(", "self.add(", "scene.add(", "self.remove(", "scene.remove("]:
        if needle in text:
            found.append(needle)
    return sorted(set(found))


def check_component_package(
    repo_root: Path,
    episode_dir: Path,
    scene_slug: str,
    contract: dict[str, Any],
    require_component_package: bool,
) -> list[str]:
    errors: list[str] = []
    scene_dir = episode_dir / "src" / "scenes" / scene_slug
    if require_component_package and not scene_dir.exists():
        return [f"scene package missing: {rel(scene_dir, repo_root)}"]
    if not scene_dir.exists():
        return []

    for name in REQUIRED_COMPONENT_FILES:
        path = scene_dir / name
        if not path.exists():
            errors.append(f"required component file missing: {rel(path, repo_root)}")

    composer = scene_dir / "composer.py"
    if composer.exists():
        class_names = python_class_names(composer)
        if len(class_names) != 1:
            errors.append(
                f"{rel(composer, repo_root)} must define exactly one Manim Scene class; "
                f"found {class_names or 'none'}"
            )
        scene_class = contract.get("scene_class")
        if scene_class and class_names and scene_class not in class_names:
            errors.append(
                f"contract.scene_class={scene_class!r} does not match composer classes {class_names}"
            )

    for python_path in sorted(scene_dir.glob("*.py")):
        if python_path.name in {"composer.py", "__init__.py"} or is_macos_metadata(python_path):
            continue
        hidden_scene_classes = python_class_names(python_path)
        if hidden_scene_classes:
            errors.append(
                f"{rel(python_path, repo_root)} defines Manim Scene classes outside composer.py: "
                f"{hidden_scene_classes}; component packages may not hide a monolithic scene "
                "behind a thin composer adapter"
            )

    objects_py = scene_dir / "objects.py"
    if objects_py.exists():
        calls = forbidden_scene_calls(objects_py)
        if calls:
            errors.append(
                f"{rel(objects_py, repo_root)} contains scheduling calls forbidden in object factories: "
                + ", ".join(calls)
            )

    if isinstance(contract.get("contract_version"), int) and contract["contract_version"] >= 4:
        audit_contract = contract.get("audit") or {}
        atomic_ids = (
            audit_contract.get("atomic_formula_elements", [])
            if isinstance(audit_contract, dict)
            else []
        )
        audit_py = scene_dir / "audit.py"
        audit_text = audit_py.read_text(encoding="utf-8") if audit_py.exists() else ""
        if "atomic_formula_elements" not in audit_text:
            errors.append(
                f"{rel(audit_py, repo_root)} must pass atomic_formula_elements to the layout audit"
            )
        for element_id in atomic_ids if isinstance(atomic_ids, list) else []:
            if isinstance(element_id, str) and element_id not in audit_text:
                errors.append(
                    f"{rel(audit_py, repo_root)} does not register atomic formula element "
                    f"{element_id!r}"
                )
    return errors


def check_contract_design_fields(
    repo_root: Path,
    episode_dir: Path,
    scene_slug: str,
    contract: dict[str, Any],
    risk_tier: str,
) -> list[str]:
    errors: list[str] = []

    if contract.get("scene_id") != scene_slug:
        errors.append(f"contract.scene_id must equal scene slug {scene_slug!r}")

    audit = contract.get("audit") or {}
    if not isinstance(audit, dict):
        errors.append("audit must be a mapping")
    elif audit.get("review_scope") != "single_scene_primary":
        errors.append("audit.review_scope must be single_scene_primary")

    source = contract.get("source") or {}
    if not isinstance(source, dict) or not source.get("timeline_segments"):
        errors.append("source.timeline_segments must name the exact S segments")

    visual_strategy = contract.get("visual_strategy") or {}
    if not isinstance(visual_strategy, dict):
        errors.append("visual_strategy must be a mapping")
    else:
        if visual_strategy.get("requires_non_formula_visual") is not True:
            errors.append("visual_strategy.requires_non_formula_visual must be true")
        if visual_strategy.get("formula_only_scene_allowed") is not False:
            errors.append("visual_strategy.formula_only_scene_allowed must be false")

    motion = contract.get("motion_ledger")
    if not isinstance(motion, list) or not motion:
        errors.append("motion_ledger must be a non-empty list")
    else:
        for index, item in enumerate(motion):
            if not isinstance(item, dict):
                errors.append(f"motion_ledger[{index}] must be a mapping")
                continue
            for field in MOTION_LEDGER_FIELDS:
                if not isinstance(item.get(field), str) or not item.get(field):
                    errors.append(f"motion_ledger[{index}].{field} must be a non-empty string")

    preflight = contract.get("authoring_preflight")
    if not isinstance(preflight, dict):
        errors.append("authoring_preflight must be a mapping")
    else:
        for field in AUTHORING_PREFLIGHT_FIELDS:
            if field not in preflight:
                errors.append(f"authoring_preflight.{field} is required")
        regression_records = preflight.get("regression_records", [])
        if not isinstance(regression_records, list) or not regression_records:
            errors.append("authoring_preflight.regression_records must be a non-empty list")
        avoidance_plan = preflight.get("avoidance_plan", [])
        if not isinstance(avoidance_plan, list) or not avoidance_plan:
            errors.append("authoring_preflight.avoidance_plan must be a non-empty list")
        else:
            for index, item in enumerate(avoidance_plan):
                if not isinstance(item, dict):
                    errors.append(f"authoring_preflight.avoidance_plan[{index}] must be a mapping")
                    continue
                for field in ["pattern_key", "applies", "design_response", "qc_proof"]:
                    if field not in item:
                        errors.append(
                            f"authoring_preflight.avoidance_plan[{index}].{field} is required"
                        )

        required_issue_paths = [
            rel(path, repo_root) for path in collect_regression_issues(episode_dir, scene_slug)
        ]
        recorded_paths = {
            str(item.get("issue_file") or item.get("path") or item)
            for item in regression_records
        }
        missing = [path for path in required_issue_paths if path not in recorded_paths]
        if missing:
            errors.append(
                "authoring_preflight.regression_records is missing required issue files: "
                + ", ".join(missing)
            )

    policy = contract.get("review_policy") or {}
    if not isinstance(policy, dict):
        errors.append("review_policy must be a mapping")
    elif risk_tier in {"human-rejected", "repeat-rejected"}:
        min_candidates = policy.get("minimum_candidate_flags")
        min_aesthetic = policy.get("minimum_ranked_aesthetic_flags")
        if not isinstance(min_candidates, int) or min_candidates < HUMAN_REJECTED_MIN_CANDIDATE_FLAGS:
            errors.append(
                "human-rejected scenes require review_policy.minimum_candidate_flags >= "
                f"{HUMAN_REJECTED_MIN_CANDIDATE_FLAGS}"
            )
        if not isinstance(min_aesthetic, int) or min_aesthetic < HUMAN_REJECTED_MIN_AESTHETIC_FLAGS:
            errors.append(
                "human-rejected scenes require review_policy.minimum_ranked_aesthetic_flags >= "
                f"{HUMAN_REJECTED_MIN_AESTHETIC_FLAGS}"
            )

    return errors


def check_timeline_and_assignment(
    repo_root: Path,
    episode_dir: Path,
    scene_slug: str,
    contract: dict[str, Any],
    require_per_scene_review: bool,
) -> list[str]:
    errors: list[str] = []
    timeline_path = episode_dir / "timeline.json"
    if timeline_path.exists():
        timeline = load_json(timeline_path)
        if isinstance(timeline, dict):
            segments = contract.get("source", {}).get("timeline_segments", [])
            timeline_entries = timeline.get("segments")
            if not isinstance(timeline_entries, list):
                timeline_entries = timeline.get("scene_groups", [])
            for segment in segments if isinstance(segments, list) else []:
                matches = [
                    item
                    for item in timeline_entries
                    if isinstance(item, dict) and item.get("id") == segment
                ]
                if not matches:
                    errors.append(f"timeline segment not found: {segment}")
                    continue
                visual = matches[0].get("visual", {})
                source_code = str(visual.get("source_code", ""))
                if "first_five" in source_code or "s001_s022_first_five.py" in source_code:
                    errors.append(
                        f"timeline {segment} still points to discarded combined source: {source_code}"
                    )
                review_output = str(visual.get("review_output", ""))
                if require_per_scene_review and "g001_g005_first_five" in review_output:
                    errors.append(
                        f"timeline {segment} still points to combined review output: {review_output}"
                    )

    assignments = episode_dir / "review" / "assignments.md"
    if assignments.exists():
        text = assignments.read_text(encoding="utf-8")
        scene_lines = [line for line in text.splitlines() if scene_slug in line]
        for line in scene_lines:
            if "s001_s022_first_five.py" in line or "g001_g005_first_five" in line:
                errors.append(
                    f"review assignments for {scene_slug} still reference discarded combined pass"
                )

    return errors


def run_validate_scene_contract(contract_path: Path) -> list[str]:
    import subprocess

    result = subprocess.run(
        [sys.executable, (TOOLS_DIR / "validate_scene_contract.py").as_posix(), contract_path.as_posix()],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return []
    output = (result.stderr or result.stdout).strip()
    return [f"validate_scene_contract.py failed for {contract_path}: {output}"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--episode", required=True)
    parser.add_argument("--scene-slug", required=True)
    parser.add_argument(
        "--risk-tier",
        choices=["normal", "dense", "human-rejected", "repeat-rejected"],
        default="normal",
    )
    parser.add_argument("--require-component-package", action="store_true")
    parser.add_argument("--require-per-scene-review", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    episode_dir = (repo_root / args.episode).resolve()
    scene_dir = episode_dir / "src" / "scenes" / args.scene_slug
    contract_path = scene_dir / "contract.yaml"

    errors: list[str] = []
    if not episode_dir.exists():
        errors.append(f"episode directory not found: {rel(episode_dir, repo_root)}")
    if not contract_path.exists():
        errors.append(f"contract missing: {rel(contract_path, repo_root)}")

    contract: dict[str, Any] = {}
    if not errors:
        loaded = load_yaml(contract_path)
        if not isinstance(loaded, dict):
            errors.append("contract root must be a mapping")
        else:
            contract = loaded

    if contract:
        errors.extend(run_validate_scene_contract(contract_path))
        errors.extend(
            check_component_package(
                repo_root,
                episode_dir,
                args.scene_slug,
                contract,
                args.require_component_package,
            )
        )
        errors.extend(
            check_contract_design_fields(
                repo_root,
                episode_dir,
                args.scene_slug,
                contract,
                args.risk_tier,
            )
        )
        errors.extend(
            check_timeline_and_assignment(
                repo_root,
                episode_dir,
                args.scene_slug,
                contract,
                args.require_per_scene_review,
            )
        )

    result = {
        "scene_slug": args.scene_slug,
        "risk_tier": args.risk_tier,
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
    else:
        print(f"OK animation_preflight: {args.scene_slug}")

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
