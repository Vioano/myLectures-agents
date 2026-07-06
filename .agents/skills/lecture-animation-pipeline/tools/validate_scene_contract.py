#!/usr/bin/env python3
"""MVP structural validator for lecture-animation scene contracts.

The validator intentionally checks only the contract surface that can be
verified without Manim: required fields, id uniqueness, references, time
ranges, and audit-frame bounds. It prefers PyYAML when available, then falls
back to a small parser for the YAML subset used by the bundled template.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Any


class ContractError(Exception):
    pass


def strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    for i, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return line[:i]
    return line


def split_key_value(text: str) -> tuple[str, str] | None:
    in_single = False
    in_double = False
    for i, char in enumerate(text):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == ":" and not in_single and not in_double:
            return text[:i].strip(), text[i + 1 :].strip()
    return None


def split_inline_list(text: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    depth = 0
    in_single = False
    in_double = False
    for char in text:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char in "[{" and not in_single and not in_double:
            depth += 1
        elif char in "]}" and not in_single and not in_double:
            depth -= 1
        if char == "," and depth == 0 and not in_single and not in_double:
            items.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        items.append(tail)
    return items


def parse_scalar(text: str) -> Any:
    text = text.strip()
    if text == "":
        return None
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    if text.startswith("[") and text.endswith("]"):
        try:
            return ast.literal_eval(text)
        except Exception:
            inner = text[1:-1].strip()
            if not inner:
                return []
            return [parse_scalar(item) for item in split_inline_list(inner)]
    if (
        (text.startswith('"') and text.endswith('"'))
        or (text.startswith("'") and text.endswith("'"))
    ):
        try:
            return ast.literal_eval(text)
        except Exception:
            return text[1:-1]
    if re.fullmatch(r"[-+]?\d+", text):
        return int(text)
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?", text):
        return float(text)
    return text


def prepare_lines(text: str) -> list[tuple[int, str]]:
    parsed: list[tuple[int, str]] = []
    for line_number, raw in enumerate(text.splitlines(), start=1):
        without_comment = strip_comment(raw).rstrip()
        if not without_comment.strip():
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ContractError(f"line {line_number}: tabs are not supported")
        indent = len(without_comment) - len(without_comment.lstrip(" "))
        parsed.append((indent, without_comment.strip()))
    return parsed


def parse_simple_yaml(text: str) -> Any:
    lines = prepare_lines(text)
    if not lines:
        return {}

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines):
            return {}, index
        current_indent, content = lines[index]
        if current_indent < indent:
            return {}, index
        if content.startswith("- "):
            return parse_list(index, current_indent)
        return parse_map(index, current_indent)

    def parse_map(index: int, indent: int) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        while index < len(lines):
            current_indent, content = lines[index]
            if current_indent < indent:
                break
            if current_indent > indent:
                raise ContractError(f"unexpected indentation near: {content}")
            if content.startswith("- "):
                break
            pair = split_key_value(content)
            if pair is None:
                raise ContractError(f"expected key: value near: {content}")
            key, rest = pair
            if not key:
                raise ContractError(f"empty key near: {content}")
            index += 1
            if rest:
                result[key] = parse_scalar(rest)
            elif index < len(lines) and lines[index][0] > current_indent:
                value, index = parse_block(index, lines[index][0])
                result[key] = value
            else:
                result[key] = None
        return result, index

    def parse_list(index: int, indent: int) -> tuple[list[Any], int]:
        result: list[Any] = []
        while index < len(lines):
            current_indent, content = lines[index]
            if current_indent < indent:
                break
            if current_indent > indent:
                raise ContractError(f"unexpected indentation near: {content}")
            if not content.startswith("- "):
                break
            item_text = content[2:].strip()
            index += 1
            if item_text == "":
                if index < len(lines) and lines[index][0] > current_indent:
                    item, index = parse_block(index, lines[index][0])
                else:
                    item = None
            else:
                pair = split_key_value(item_text)
                if pair is not None and pair[0]:
                    key, rest = pair
                    item = {key: parse_scalar(rest) if rest else None}
                    if index < len(lines) and lines[index][0] > current_indent:
                        extra, index = parse_map(index, lines[index][0])
                        item.update(extra)
                else:
                    item = parse_scalar(item_text)
                    if index < len(lines) and lines[index][0] > current_indent:
                        raise ContractError(
                            f"scalar list item has nested block near: {item_text}"
                        )
            result.append(item)
        return result, index

    value, end_index = parse_block(0, lines[0][0])
    if end_index != len(lines):
        raise ContractError(f"could not parse all lines; stopped at {end_index + 1}")
    return value


def load_contract(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        return parse_simple_yaml(text)
    try:
        return yaml.safe_load(text)
    except Exception as exc:  # pragma: no cover - depends on optional PyYAML
        raise ContractError(f"YAML parse error: {exc}") from exc


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def as_list(value: Any, label: str, errors: list[str]) -> list[Any]:
    if isinstance(value, list):
        return value
    errors.append(f"{label} must be a list")
    return []


def as_mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    errors.append(f"{label} must be a mapping")
    return {}


def check_unique_dicts(items: list[Any], field: str, label: str, errors: list[str]) -> set[str]:
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index}] must be a mapping")
            continue
        value = item.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"{label}[{index}].{field} must be a non-empty string")
            continue
        if value in seen:
            errors.append(f"{label}.{field} duplicate: {value}")
        seen.add(value)
    return seen


def check_time_pair(value: Any, label: str, errors: list[str]) -> tuple[float, float] | None:
    if not isinstance(value, list) or len(value) != 2 or not all(is_number(v) for v in value):
        errors.append(f"{label} must be [start, end] with two numbers")
        return None
    start, end = float(value[0]), float(value[1])
    if start > end:
        errors.append(f"{label} must be ascending; got [{start}, {end}]")
    return start, end


def check_refs(values: Any, allowed: set[str], label: str, errors: list[str]) -> None:
    for index, value in enumerate(as_list(values or [], label, errors)):
        if not isinstance(value, str):
            errors.append(f"{label}[{index}] must be a string")
        elif value not in allowed:
            errors.append(f"{label}[{index}] references unknown id: {value}")


FRAME_ROLES = {
    "conclusion",
    "active_focus",
    "group_panel",
    "contrast_pair",
    "derivation_container",
    "warning",
}

REVIEW_FLAG_STATUSES = {"open", "fixed", "pardoned", "not_applicable"}


def check_style_constraints(value: Any, label: str, errors: list[str]) -> None:
    if value is None:
        return
    data = as_mapping(value, label, errors)
    if not data:
        return
    max_overlap = data.get("max_unrelated_overlap_seconds")
    if max_overlap is not None and (not is_number(max_overlap) or float(max_overlap) < 0):
        errors.append(f"{label}.max_unrelated_overlap_seconds must be a non-negative number")
    for field in ["connector_policy", "framed_formula_default"]:
        if field in data and not isinstance(data[field], str):
            errors.append(f"{label}.{field} must be a string")


def check_object_presentation(value: Any, label: str, errors: list[str]) -> None:
    if value is None:
        return
    data = as_mapping(value, label, errors)
    if not data:
        return
    uses_frame = data.get("uses_frame")
    if uses_frame is not None and not isinstance(uses_frame, bool):
        errors.append(f"{label}.uses_frame must be a boolean")
    frame_role = data.get("frame_role")
    if uses_frame:
        if not isinstance(frame_role, str) or not frame_role:
            errors.append(f"{label}.frame_role is required when uses_frame is true")
        elif frame_role not in FRAME_ROLES:
            allowed = ", ".join(sorted(FRAME_ROLES))
            errors.append(f"{label}.frame_role must be one of: {allowed}")
    elif frame_role is not None and frame_role not in FRAME_ROLES:
        allowed = ", ".join(sorted(FRAME_ROLES))
        errors.append(f"{label}.frame_role must be one of: {allowed}")
    if "formula_display" in data and not isinstance(data["formula_display"], str):
        errors.append(f"{label}.formula_display must be a string")


def check_object_connectors(value: Any, label: str, errors: list[str]) -> None:
    if value is None:
        return
    data = as_mapping(value, label, errors)
    if not data:
        return
    if "policy" in data and not isinstance(data["policy"], str):
        errors.append(f"{label}.policy must be a string")
    if "forbid_background_baseline" in data and not isinstance(data["forbid_background_baseline"], bool):
        errors.append(f"{label}.forbid_background_baseline must be a boolean")


def check_visual_reference(value: Any, label: str, errors: list[str]) -> None:
    if value is None:
        return
    data = as_mapping(value, label, errors)
    if not data:
        return
    for field in ["classic_source", "reason", "display_mapping", "math_identity", "forbidden_display"]:
        if field in data and (not isinstance(data[field], str) or not data[field]):
            errors.append(f"{label}.{field} must be a non-empty string")


def check_overlap_policy(value: Any, label: str, errors: list[str], default_max: float | None) -> None:
    if value is None:
        return
    data = as_mapping(value, label, errors)
    if not data:
        return
    max_overlap = data.get("max_unrelated_overlap_seconds")
    if max_overlap is None:
        return
    if not is_number(max_overlap) or float(max_overlap) < 0:
        errors.append(f"{label}.max_unrelated_overlap_seconds must be a non-negative number")
    elif default_max is not None and float(max_overlap) > default_max:
        errors.append(
            f"{label}.max_unrelated_overlap_seconds={max_overlap} exceeds "
            f"style_constraints.max_unrelated_overlap_seconds={default_max}"
        )


def check_review_policy(value: Any, label: str, errors: list[str]) -> None:
    if value is None:
        errors.append(f"{label} is required")
        return
    data = as_mapping(value, label, errors)
    if not data:
        return
    if data.get("mode") != "reverse_burden":
        errors.append(f"{label}.mode must be reverse_burden")
    min_flags = data.get("minimum_candidate_flags")
    if not isinstance(min_flags, int) or isinstance(min_flags, bool) or min_flags < 1:
        errors.append(f"{label}.minimum_candidate_flags must be a positive integer")
        min_flags = 1
    pass_requires_closed = data.get("pass_requires_all_flags_closed")
    if not isinstance(pass_requires_closed, bool):
        errors.append(f"{label}.pass_requires_all_flags_closed must be a boolean")
        pass_requires_closed = True
    requires_ranked_aesthetic = data.get("requires_ranked_aesthetic_sweep")
    if not isinstance(requires_ranked_aesthetic, bool):
        errors.append(f"{label}.requires_ranked_aesthetic_sweep must be a boolean")
        requires_ranked_aesthetic = False
    min_ranked_aesthetic = data.get("minimum_ranked_aesthetic_flags")
    if (
        not isinstance(min_ranked_aesthetic, int)
        or isinstance(min_ranked_aesthetic, bool)
        or min_ranked_aesthetic < 1
    ):
        errors.append(f"{label}.minimum_ranked_aesthetic_flags must be a positive integer")
        min_ranked_aesthetic = 3
    flags = as_list(data.get("candidate_flags", []), f"{label}.candidate_flags", errors)
    if len(flags) < int(min_flags):
        errors.append(
            f"{label}.candidate_flags has {len(flags)} entries; "
            f"minimum_candidate_flags is {min_flags}"
        )
    seen: set[str] = set()
    for index, flag in enumerate(flags):
        if not isinstance(flag, dict):
            errors.append(f"{label}.candidate_flags[{index}] must be a mapping")
            continue
        flag_id = flag.get("id")
        if not isinstance(flag_id, str) or not flag_id:
            errors.append(f"{label}.candidate_flags[{index}].id must be a non-empty string")
        elif flag_id in seen:
            errors.append(f"{label}.candidate_flags.id duplicate: {flag_id}")
        else:
            seen.add(flag_id)
        standard_key = flag.get("standard_key")
        if not isinstance(standard_key, str) or not standard_key:
            errors.append(
                f"{label}.candidate_flags[{index}].standard_key must be a non-empty string"
            )
        status = flag.get("status")
        if status not in REVIEW_FLAG_STATUSES:
            allowed = ", ".join(sorted(REVIEW_FLAG_STATUSES))
            errors.append(f"{label}.candidate_flags[{index}].status must be one of: {allowed}")
        elif pass_requires_closed and status == "open":
            errors.append(f"{label}.candidate_flags[{index}] is still open")
        for field in ["evidence", "authoring_response"]:
            if not isinstance(flag.get(field), str) or not flag.get(field):
                errors.append(f"{label}.candidate_flags[{index}].{field} must be a non-empty string")
        if status == "pardoned":
            reason = flag.get("pardon_reason")
            if not isinstance(reason, str) or not reason:
                errors.append(
                    f"{label}.candidate_flags[{index}].pardon_reason is required when status is pardoned"
                )
        repair_target = flag.get("repair_target", [])
        if not isinstance(repair_target, list):
            errors.append(f"{label}.candidate_flags[{index}].repair_target must be a list")
    aesthetic_flags = as_list(
        data.get("ranked_aesthetic_flags", []),
        f"{label}.ranked_aesthetic_flags",
        errors,
    )
    if requires_ranked_aesthetic and len(aesthetic_flags) < int(min_ranked_aesthetic):
        errors.append(
            f"{label}.ranked_aesthetic_flags has {len(aesthetic_flags)} entries; "
            f"minimum_ranked_aesthetic_flags is {min_ranked_aesthetic}"
        )
    ranked_ids: set[str] = set()
    ranks: set[int] = set()
    for index, flag in enumerate(aesthetic_flags):
        if not isinstance(flag, dict):
            errors.append(f"{label}.ranked_aesthetic_flags[{index}] must be a mapping")
            continue
        rank = flag.get("rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
            errors.append(f"{label}.ranked_aesthetic_flags[{index}].rank must be a positive integer")
        elif rank in ranks:
            errors.append(f"{label}.ranked_aesthetic_flags.rank duplicate: {rank}")
        else:
            ranks.add(rank)
        flag_id = flag.get("id")
        if not isinstance(flag_id, str) or not flag_id:
            errors.append(f"{label}.ranked_aesthetic_flags[{index}].id must be a non-empty string")
        elif flag_id in ranked_ids:
            errors.append(f"{label}.ranked_aesthetic_flags.id duplicate: {flag_id}")
        else:
            ranked_ids.add(flag_id)
        standard_key = flag.get("standard_key")
        if not isinstance(standard_key, str) or not standard_key:
            errors.append(
                f"{label}.ranked_aesthetic_flags[{index}].standard_key must be a non-empty string"
            )
        status = flag.get("status")
        if status not in REVIEW_FLAG_STATUSES:
            allowed = ", ".join(sorted(REVIEW_FLAG_STATUSES))
            errors.append(
                f"{label}.ranked_aesthetic_flags[{index}].status must be one of: {allowed}"
            )
        elif pass_requires_closed and status == "open":
            errors.append(f"{label}.ranked_aesthetic_flags[{index}] is still open")
        for field in ["evidence", "authoring_response"]:
            if not isinstance(flag.get(field), str) or not flag.get(field):
                errors.append(
                    f"{label}.ranked_aesthetic_flags[{index}].{field} must be a non-empty string"
                )
        if status == "pardoned":
            reason = flag.get("pardon_reason")
            if not isinstance(reason, str) or not reason:
                errors.append(
                    f"{label}.ranked_aesthetic_flags[{index}].pardon_reason is required when status is pardoned"
                )
        repair_target = flag.get("repair_target", [])
        if not isinstance(repair_target, list):
            errors.append(f"{label}.ranked_aesthetic_flags[{index}].repair_target must be a list")


def check_visual_strategy(value: Any, label: str, errors: list[str]) -> None:
    if value is None:
        errors.append(f"{label} is required")
        return
    data = as_mapping(value, label, errors)
    if not data:
        return
    requires_visual = data.get("requires_non_formula_visual")
    if not isinstance(requires_visual, bool):
        errors.append(f"{label}.requires_non_formula_visual must be a boolean")
    visuals = data.get("non_formula_visuals", [])
    if not isinstance(visuals, list):
        errors.append(f"{label}.non_formula_visuals must be a list")
        visuals = []
    if requires_visual and not visuals:
        errors.append(f"{label}.non_formula_visuals must not be empty when required")
    if not isinstance(data.get("formula_only_scene_allowed"), bool):
        errors.append(f"{label}.formula_only_scene_allowed must be a boolean")
    if not isinstance(data.get("novice_viewer_test"), str) or not data.get("novice_viewer_test"):
        errors.append(f"{label}.novice_viewer_test must be a non-empty string")


def check_formula_persistence(value: Any, label: str, errors: list[str]) -> None:
    if value is None:
        errors.append(f"{label} is required")
        return
    data = as_mapping(value, label, errors)
    if not data:
        return
    min_hold = data.get("min_hold_seconds")
    if min_hold is not None and (not is_number(min_hold) or float(min_hold) < 0):
        errors.append(f"{label}.min_hold_seconds must be a non-negative number")
    if not isinstance(data.get("premature_clear_forbidden_when_space_available"), bool):
        errors.append(
            f"{label}.premature_clear_forbidden_when_space_available must be a boolean"
        )


def check_top_level_presentation(value: Any, label: str, errors: list[str]) -> None:
    if value is None:
        errors.append(f"{label} is required")
        return
    data = as_mapping(value, label, errors)
    if not data:
        return
    for field in [
        "math_renderer_required",
        "allow_plain_text_math_tokens",
        "forbid_unowned_fills",
    ]:
        if not isinstance(data.get(field), bool):
            errors.append(f"{label}.{field} must be a boolean")


def validate_contract(contract: Any) -> list[str]:
    errors: list[str] = []
    root = as_mapping(contract, "contract", errors)
    if not root:
        return errors

    required = [
        "scene_id",
        "scene_class",
        "contract_version",
        "source",
        "review_policy",
        "visual_strategy",
        "formula_persistence",
        "presentation",
        "layout_modes",
        "zones",
        "drivers",
        "objects",
        "beats",
        "audit",
    ]
    for key in required:
        if key not in root:
            errors.append(f"missing required top-level field: {key}")

    for key in ["scene_id", "scene_class"]:
        if key in root and not isinstance(root[key], str):
            errors.append(f"{key} must be a string")
    if "contract_version" in root and not isinstance(root["contract_version"], int):
        errors.append("contract_version must be an integer")

    check_style_constraints(root.get("style_constraints"), "style_constraints", errors)
    check_review_policy(root.get("review_policy"), "review_policy", errors)
    check_visual_strategy(root.get("visual_strategy"), "visual_strategy", errors)
    check_formula_persistence(root.get("formula_persistence"), "formula_persistence", errors)
    check_top_level_presentation(root.get("presentation"), "presentation", errors)
    style_constraints = root.get("style_constraints") if isinstance(root.get("style_constraints"), dict) else {}
    max_unrelated_overlap = style_constraints.get("max_unrelated_overlap_seconds")
    default_max_overlap = float(max_unrelated_overlap) if is_number(max_unrelated_overlap) else None

    source = as_mapping(root.get("source", {}), "source", errors)
    if source:
        if not as_list(source.get("timeline_segments", []), "source.timeline_segments", errors):
            errors.append("source.timeline_segments must not be empty")
        check_time_pair(source.get("audio_window"), "source.audio_window", errors)

    zones = as_mapping(root.get("zones", {}), "zones", errors)
    zone_ids = set(zones.keys())
    if not zone_ids:
        errors.append("zones must not be empty")
    for zone_id, zone in zones.items():
        zone_map = as_mapping(zone, f"zones.{zone_id}", errors)
        rect = zone_map.get("rect")
        if not isinstance(rect, list) or len(rect) != 4 or not all(is_number(v) for v in rect):
            errors.append(f"zones.{zone_id}.rect must be a list of 4 numbers")

    drivers = as_list(root.get("drivers", []), "drivers", errors)
    if not drivers:
        errors.append("drivers must not be empty")
    driver_ids = check_unique_dicts(drivers, "id", "drivers", errors)

    objects = as_list(root.get("objects", []), "objects", errors)
    if not objects:
        errors.append("objects must not be empty")
    object_ids = check_unique_dicts(objects, "id", "objects", errors)
    for index, item in enumerate(objects):
        if not isinstance(item, dict):
            continue
        for field in ["factory", "driver", "zone", "role"]:
            if not isinstance(item.get(field), str) or not item.get(field):
                errors.append(f"objects[{index}].{field} must be a non-empty string")
        driver = item.get("driver")
        zone = item.get("zone")
        if isinstance(driver, str) and driver not in driver_ids:
            errors.append(f"objects[{index}].driver references unknown driver: {driver}")
        if isinstance(zone, str) and zone not in zone_ids:
            errors.append(f"objects[{index}].zone references unknown zone: {zone}")
        check_object_presentation(item.get("presentation"), f"objects[{index}].presentation", errors)
        check_object_connectors(item.get("connectors"), f"objects[{index}].connectors", errors)
        check_visual_reference(item.get("visual_reference"), f"objects[{index}].visual_reference", errors)

    layout_modes = as_list(root.get("layout_modes", []), "layout_modes", errors)
    if not layout_modes:
        errors.append("layout_modes must not be empty")
    for index, item in enumerate(layout_modes):
        if not isinstance(item, dict):
            errors.append(f"layout_modes[{index}] must be a mapping")
            continue
        if not isinstance(item.get("id"), str) or not item.get("id"):
            errors.append(f"layout_modes[{index}].id must be a non-empty string")
        check_time_pair(item.get("local_time"), f"layout_modes[{index}].local_time", errors)

    beats = as_list(root.get("beats", []), "beats", errors)
    if not beats:
        errors.append("beats must not be empty")
    check_unique_dicts(beats, "id", "beats", errors)
    for beat_index, beat in enumerate(beats):
        if not isinstance(beat, dict):
            errors.append(f"beats[{beat_index}] must be a mapping")
            continue
        time_pair = check_time_pair(
            beat.get("local_time"), f"beats[{beat_index}].local_time", errors
        )
        for field in ["owns_zones", "enter", "transform", "clear_before", "clear_after", "audit_frames"]:
            if field not in beat:
                errors.append(f"beats[{beat_index}].{field} is required")
        check_refs(beat.get("owns_zones"), zone_ids, f"beats[{beat_index}].owns_zones", errors)
        for field in ["enter", "clear_before", "clear_after"]:
            check_refs(beat.get(field, []), object_ids, f"beats[{beat_index}].{field}", errors)
        transforms = as_list(beat.get("transform", []), f"beats[{beat_index}].transform", errors)
        for transform_index, transform in enumerate(transforms):
            if not isinstance(transform, dict):
                errors.append(f"beats[{beat_index}].transform[{transform_index}] must be a mapping")
                continue
            for field in ["from", "to"]:
                ref = transform.get(field)
                if not isinstance(ref, str) or not ref:
                    errors.append(
                        f"beats[{beat_index}].transform[{transform_index}].{field} "
                        "must be a non-empty string"
                    )
                elif ref not in object_ids:
                    errors.append(
                        f"beats[{beat_index}].transform[{transform_index}].{field} "
                        f"references unknown object: {ref}"
                    )
        frames = as_list(beat.get("audit_frames", []), f"beats[{beat_index}].audit_frames", errors)
        check_overlap_policy(
            beat.get("overlap_policy"),
            f"beats[{beat_index}].overlap_policy",
            errors,
            default_max_overlap,
        )
        if time_pair is not None:
            start, end = time_pair
            for frame_index, frame in enumerate(frames):
                if not is_number(frame):
                    errors.append(f"beats[{beat_index}].audit_frames[{frame_index}] must be a number")
                    continue
                if float(frame) < start or float(frame) > end:
                    errors.append(
                        f"{beat.get('id', f'beats[{beat_index}]')}.audit_frames[{frame_index}]="
                        f"{frame} outside local_time [{start}, {end}]"
                    )

    audit = as_mapping(root.get("audit", {}), "audit", errors)
    protected_regions = audit.get("protected_regions", [])
    check_refs(protected_regions, zone_ids, "audit.protected_regions", errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path, help="Path to scene contract YAML")
    args = parser.parse_args(argv)

    try:
        contract = load_contract(args.contract)
        errors = validate_contract(contract)
    except (OSError, ContractError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1

    print(f"OK scene_contract: {contract.get('scene_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
