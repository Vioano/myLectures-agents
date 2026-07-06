#!/usr/bin/env python3
"""Audit Jupyter notebooks for myLectures production handoff risks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


WARNING_PATTERNS = [
    re.compile(r"Font .* does not have a glyph", re.I),
    re.compile(r"Glyph .* missing from font", re.I),
    re.compile(r"Traceback", re.I),
    re.compile(r"TypeError|ValueError|NameError|ImportError|ModuleNotFoundError", re.I),
    re.compile(r"Exception", re.I),
]

RAW_INTERACT_PATTERN = re.compile(r"(?<![A-Za-z0-9_])(?:widgets\.)?interact\s*\(")
PRESENTATION_BOUNDARY_PATTERNS = [
    re.compile(r"Stable Interaction Pattern", re.I),
    re.compile(r"stable (?:widget|slider|interaction|output)", re.I),
    re.compile(r"fixed[- ]height", re.I),
    re.compile(r"continuous_update", re.I),
    re.compile(r"raw interact|not using interact|不用\s*`?interact", re.I),
    re.compile(r"warning/output|旧草稿|production candidate|review gate|pipeline|audit", re.I),
    re.compile(r"这个\s*Notebook\s*(?:不是|的目标|的核心)", re.I),
    re.compile(r"输出(?:区|面板)高度固定|避免.*闪动|重算不会挤动", re.I),
]


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "".join(as_text(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def collect_output_text(output: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in ("text", "ename", "evalue", "traceback"):
        chunks.append(as_text(output.get(key)))
    data = output.get("data", {})
    if isinstance(data, dict):
        for value in data.values():
            chunks.append(as_text(value))
    return "\n".join(chunk for chunk in chunks if chunk)


def add_issue(
    issues: list[dict[str, Any]],
    severity: str,
    standard_key: str,
    pattern_key: str,
    message: str,
    location: dict[str, Any],
) -> None:
    issues.append(
        {
            "severity": severity,
            "standard_key": standard_key,
            "pattern_key": pattern_key,
            "message": message,
            "location": location,
        }
    )


def audit_notebook(path: Path, output_size_limit: int) -> dict[str, Any]:
    try:
        nb = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report parse failure as audit JSON
        return {
            "path": str(path),
            "status": "blocked",
            "issues": [
                {
                    "severity": "blocker",
                    "standard_key": "source_boundary_failure",
                    "pattern_key": "invalid_notebook_json",
                    "message": f"Could not parse notebook JSON: {exc}",
                    "location": {"path": str(path)},
                }
            ],
        }

    issues: list[dict[str, Any]] = []
    cells = nb.get("cells", [])

    for index, cell in enumerate(cells):
        source = as_text(cell.get("source"))
        outputs = cell.get("outputs", []) or []
        code_location = {"cell": index}

        if cell.get("cell_type") == "markdown":
            for pattern in PRESENTATION_BOUNDARY_PATTERNS:
                if pattern.search(source):
                    add_issue(
                        issues,
                        "major",
                        "presentation_boundary_failure",
                        "creator_intent_text_in_student_notebook",
                        f"Markdown exposes production/review/workaround text matching {pattern.pattern!r}.",
                        code_location,
                    )
                    break

        if cell.get("cell_type") == "code":
            if RAW_INTERACT_PATTERN.search(source):
                add_issue(
                    issues,
                    "major",
                    "interaction_stability_failure",
                    "raw_interact_usage",
                    "Raw interact(...) can resize output and rerun continuously; prefer fixed-height interactive_output.",
                    code_location,
                )
            if "continuous_update=True" in source:
                add_issue(
                    issues,
                    "major",
                    "interaction_stability_failure",
                    "continuous_slider_redraw",
                    "A widget explicitly redraws continuously. Use continuous_update=False unless smooth motion is required and tested.",
                    code_location,
                )
            if (
                ("FloatSlider(" in source or "IntSlider(" in source)
                and "continuous_update=False" not in source
            ):
                add_issue(
                    issues,
                    "minor",
                    "interaction_stability_failure",
                    "slider_missing_continuous_update_false",
                    "A slider cell does not explicitly set continuous_update=False.",
                    code_location,
                )

        for output_index, output in enumerate(outputs):
            location = {"cell": index, "output": output_index}
            if output.get("output_type") == "error":
                add_issue(
                    issues,
                    "blocker",
                    "output_hygiene_failure",
                    "cell_error_output",
                    "Notebook cell contains an error output.",
                    location,
                )
            text = collect_output_text(output)
            for pattern in WARNING_PATTERNS:
                if pattern.search(text):
                    add_issue(
                        issues,
                        "major",
                        "output_hygiene_failure",
                        "warning_or_traceback_output",
                        f"Output contains noisy warning/error text matching {pattern.pattern!r}.",
                        location,
                    )
                    break

    widget_state = (
        nb.get("metadata", {})
        .get("widgets", {})
        .get("application/vnd.jupyter.widget-state+json", {})
        .get("state", {})
    )
    if isinstance(widget_state, dict):
        for model_id, model in widget_state.items():
            outputs = model.get("state", {}).get("outputs", []) if isinstance(model, dict) else []
            for output_index, output in enumerate(outputs):
                location = {"widget_model": model_id, "output": output_index}
                if output.get("output_type") == "error":
                    add_issue(
                        issues,
                        "blocker",
                        "interaction_stability_failure",
                        "hidden_widget_state_error",
                        "Widget state contains an error output.",
                        location,
                    )
                text = collect_output_text(output)
                for pattern in WARNING_PATTERNS:
                    if pattern.search(text):
                        add_issue(
                            issues,
                            "major",
                            "interaction_stability_failure",
                            "hidden_widget_warning_output",
                            f"Widget state contains noisy warning/error text matching {pattern.pattern!r}.",
                            location,
                        )
                        break

    size_bytes = path.stat().st_size
    if size_bytes > output_size_limit:
        add_issue(
            issues,
            "minor",
            "output_hygiene_failure",
            "large_saved_notebook",
            f"Notebook is {size_bytes} bytes, above limit {output_size_limit}. Confirm saved outputs are intentional.",
            {"path": str(path), "size_bytes": size_bytes},
        )

    status = "pass"
    if any(issue["severity"] == "blocker" for issue in issues):
        status = "blocked"
    elif any(issue["severity"] in {"major", "minor"} for issue in issues):
        status = "revise"

    return {
        "path": str(path),
        "status": status,
        "cell_count": len(cells),
        "size_bytes": size_bytes,
        "issue_count": len(issues),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebooks", nargs="+", type=Path)
    parser.add_argument("--output-size-limit", type=int, default=5_000_000)
    parser.add_argument("--json", action="store_true", help="Emit raw JSON only.")
    args = parser.parse_args()

    results = [audit_notebook(path, args.output_size_limit) for path in args.notebooks]
    payload = {"status": "pass", "results": results}
    if any(result["status"] == "blocked" for result in results):
        payload["status"] = "blocked"
    elif any(result["status"] == "revise" for result in results):
        payload["status"] = "revise"

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"status: {payload['status']}")
        for result in results:
            print(f"- {result['path']}: {result['status']} ({result['issue_count']} issues)")
            for issue in result["issues"]:
                print(
                    f"  [{issue['severity']}] {issue['standard_key']}/"
                    f"{issue['pattern_key']}: {issue['message']}"
                )

    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
