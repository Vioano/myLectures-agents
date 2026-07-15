#!/usr/bin/env python3
"""Audit Jupyter notebooks for myLectures production handoff risks."""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
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
EPISODE_SLUG_PATTERN = re.compile(r"^\d{4}-")
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
STUDENT_VISIBLE_SCAFFOLD_PATTERNS = [
    re.compile(r"\bConcept Check\b", re.I),
    re.compile(r"\bPattern Card\b", re.I),
    re.compile(r"\bOptional Lab\b", re.I),
    re.compile(r"\bStable Lab\b", re.I),
    re.compile(r"\bHidden Singularity Radar\b", re.I),
    re.compile(r"\bSum-to-Integral Bridge\b", re.I),
    re.compile(r"\bProjection Pattern Literacy\b", re.I),
    re.compile(r"\bError Diagnosis\b", re.I),
    re.compile(r"\braw sum\b", re.I),
    re.compile(r"\bweighted sum\b", re.I),
    re.compile(r"\btarget x\b", re.I),
    re.compile(r"\bmissing_(?:sign|over_n|factor_2)\b", re.I),
    re.compile(r"\bFormula:\s*", re.I),
    re.compile(r"\bStructure:\s*", re.I),
    re.compile(r"\[(?:OK|CHECK)\]"),
    re.compile(r"\b(?:len1_sq|len2_sq|raw sum|weighted sum|is_projection)\b", re.I),
    re.compile(r"\b(?:matrix =|unit circle|original coordinate object)\b", re.I),
    re.compile(r"模式卡"),
    re.compile(r"隐藏奇点雷达"),
    re.compile(r"小型训练器"),
    re.compile(r"投影模式识别"),
    re.compile(r"封闭性扫描"),
    re.compile(r"概念检查"),
]
HUMANIZER_AI_PATTERNS = [
    re.compile(r"—|–"),
    re.compile(r"不(?:只是|仅仅是|是).{0,18}(?:而是|更是)"),
    re.compile(r"(?:真正|本质上|核心|关键)(?:的)?(?:问题|所在|是)"),
    re.compile(r"(?:值得注意的是|需要注意的是|可以看到|我们可以看到)"),
    re.compile(r"(?:让我们|下面我们|接下来我们|现在我们)(?:来)?(?:看|讨论|探索|分析)"),
    re.compile(r"(?:起到|扮演|承担).{0,12}(?:关键|核心|重要).{0,8}(?:作用|角色)"),
    re.compile(r"(?:结构化|系统性|深层|底层)(?:地)?(?:理解|掌握|认识)"),
    re.compile(r"(?:丰富|深刻|关键|核心|重要|有效)(?:的)?(?:理解|洞察|启发)"),
    re.compile(r"\b(?:Additionally|Moreover|Furthermore|In conclusion|Let's dive in|Here's what you need to know)\b", re.I),
    re.compile(r"\b(?:crucial|pivotal|vibrant|profound|showcase|underscores?|highlights?|delve|intricate|landscape)\b", re.I),
]
STUDENT_VISIBLE_ENGINEERING_JARGON_PATTERNS = [
    re.compile(r"(?:往前扔|丢过去|搬过去|扔到|把.{0,10}(?:像素|点).{0,10}(?:扔|丢|搬))"),
    re.compile(r"(?:没人填色|没有人填|糊一下|糊上去|糊边|补洞|硬塞|凑(?:一个|出来))"),
    re.compile(r"(?:乱采|瞎采|随便采样)"),
    re.compile(r"(?:黑箱|魔法|随便)(?:算|画|填|取|处理)?"),
]
STUDENT_VISIBLE_BACKSTAGE_IMPLEMENTATION_PATTERNS = [
    re.compile(r"(?:图像重采样|反向采样|反着算)"),
    re.compile(r"(?:输出位置|原位置).{0,24}(?:原图|原图颜色|读取|反算)"),
    re.compile(r"(?:原图颜色|原像素.{0,16}(?:覆盖|移动|填色))"),
]
STUDENT_VISIBLE_PACKAGING_HEADING_PATTERNS = [
    re.compile(r"(?m)^#{1,6}\s*\d+[.、]\s*(?:一页)?(?:考试总结|考试速查|速查清单|知识清单)\s*$"),
    re.compile(r"(?m)^#{1,6}\s*\d+[.、]\s*(?:总结页|复习清单|知识点清单)\s*$"),
]
STUDENT_VISIBLE_CRUDE_HEADING_PATTERNS = [
    re.compile(r"(?m)^#{1,6}\s*\d+[.、]\s*.*(?:废话|玄学|套路|瞎扯|糊弄).*$"),
]
STUDENT_VISIBLE_DIRECT_ANSWER_PATTERNS = [
    re.compile(r"(?m)^\s*(?:对照答案|参考答案|参考拆解|奇偶性判断)：\s*$"),
]
VISIBLE_WORKED_SOLUTION_PATTERNS = [
    re.compile(r"(?m)^\s*(?:直接算|两列直接算|标准结果|前几项是)：\s*$"),
    re.compile(r"所以\s*投影坐标\s*是"),
    re.compile(r"所以\s*\n{0,3}\s*\$\$\s*c\s*="),
    re.compile(r"分部积分得到"),
    re.compile(r"这类题直接在复平面量距离"),
]
UNNECESSARY_PROMPT_TABLE_PATTERNS = [
    re.compile(r"(?m)^\|\s*步骤\s*\|\s*你要得到的结果\s*\|"),
    re.compile(r"(?m)^\|\s*量\s*\|\s*结果\s*\|"),
    re.compile(r"(?m)^\|\s*问题\s*\|\s*结果\s*\|"),
    re.compile(r"(?m)^\|\s*对象\s*\|\s*结果\s*\|"),
]
FILL_BLANK_PATTERN = re.compile(r"\\underline\s*\{\s*\\hspace|_{5,}|＿{3,}")
STYLED_ANSWER_BOX_PATTERN = re.compile(
    r"<(?:div|section|article)\b(?=[^>]*(?:min-height|height)\s*:)(?=[^>]*border\s*:)[^>]*>",
    re.I,
)
ANSWER_TABLE_SUMMARY_PATTERN = re.compile(
    r"<summary>\s*(?:对照答案|参考答案|参考判断|参考拆解|参考计算|参考推导|标准结果)\s*</summary>"
)
MARKDOWN_TABLE_LINE_PATTERN = re.compile(r"^\s*\|.*\|\s*$")
SETUP_NOISE_PATTERNS = [
    re.compile(r"CJK_FONT_CANDIDATES"),
    re.compile(r"plt\.rcParams\.update\s*\("),
]
INTERACTIVE_OR_VISUAL_MARKERS = [
    "interactive_panel(",
    "interactive_output(",
    "widgets.",
    "FloatSlider(",
    "IntSlider(",
    "Text(",
    "Dropdown(",
    "plt.",
    ".plot(",
    ".imshow(",
    ".scatter(",
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


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


def audit_source_path(path: Path, issues: list[dict[str, Any]]) -> None:
    parts = path.parts
    for index, part in enumerate(parts):
        if (
            part == "notebooks"
            and index + 2 < len(parts)
            and EPISODE_SLUG_PATTERN.match(parts[index + 1])
            and parts[index + 2] == "notebook.ipynb"
        ):
            add_issue(
                issues,
                "major",
                "source_boundary_failure",
                "deep_generic_notebook_path",
                "Public notebooks should use notebooks/NNNN-slug.ipynb; move README, draft, review, and issues to episodes/NNNN-slug/.",
                {"path": str(path)},
            )
            return


def iter_code_string_literals(source: str) -> list[tuple[str, int | None]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    literals: list[tuple[str, int | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.append((node.value, getattr(node, "lineno", None)))
    return literals


def has_unescaped_tex_pipe_in_markdown_table(text: str) -> bool:
    for line in text.splitlines():
        if not MARKDOWN_TABLE_LINE_PATTERN.match(line):
            continue
        in_math = False
        escaped = False
        for char in line:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == "$":
                in_math = not in_math
                continue
            if char == "|" and in_math:
                return True
    return False


def contains_markdown_table(text: str) -> bool:
    return any(MARKDOWN_TABLE_LINE_PATTERN.match(line) for line in text.splitlines())


def contains_incomplete_prompt_table(text: str) -> bool:
    if not contains_markdown_table(text):
        return False
    if re.search(r"(?:先自己填|先填|先把|再展开|对照|填写|填完)", text):
        return True
    for line in text.splitlines():
        if MARKDOWN_TABLE_LINE_PATTERN.match(line) and re.search(r"\|\s{2,}\|", line):
            return True
    return False


def has_answer_table_without_prompt(current_text: str, previous_markdown: str) -> bool:
    if "<details" not in current_text or not ANSWER_TABLE_SUMMARY_PATTERN.search(current_text):
        return False
    if not contains_markdown_table(current_text):
        return False
    before_details = current_text.split("<details", 1)[0]
    prompt_context = f"{previous_markdown}\n{before_details}"
    return not contains_incomplete_prompt_table(prompt_context)


def has_visible_worked_solution(text: str) -> bool:
    visible_text = text.split("<details", 1)[0]
    return any(pattern.search(visible_text) for pattern in VISIBLE_WORKED_SOLUTION_PATTERNS)


def has_unnecessary_prompt_table(text: str) -> bool:
    visible_text = text.split("<details", 1)[0]
    return any(pattern.search(visible_text) for pattern in UNNECESSARY_PROMPT_TABLE_PATTERNS)


def has_mechanical_fill_blank_overuse(text: str) -> bool:
    visible_text = text.split("<details", 1)[0]
    return len(FILL_BLANK_PATTERN.findall(visible_text)) >= 3


def has_styled_answer_box(text: str) -> bool:
    visible_text = text.split("<details", 1)[0]
    return STYLED_ANSWER_BOX_PATTERN.search(visible_text) is not None


def scan_presentation_text(
    issues: list[dict[str, Any]],
    text: str,
    location: dict[str, Any],
    source_kind: str,
) -> None:
    for pattern in PRESENTATION_BOUNDARY_PATTERNS:
        if pattern.search(text):
            add_issue(
                issues,
                "major",
                "presentation_boundary_failure",
                "creator_intent_text_in_student_notebook",
                f"{source_kind} exposes production/review/workaround text matching {pattern.pattern!r}.",
                location,
            )
            break

    matched_humanizer_patterns = [
        pattern.pattern for pattern in HUMANIZER_AI_PATTERNS if pattern.search(text)
    ]
    if matched_humanizer_patterns:
        add_issue(
            issues,
            "major",
            "presentation_boundary_failure",
            "ai_writing_pattern_public_text",
            f"{source_kind} contains AI-writing or over-scripted wording patterns: {matched_humanizer_patterns[:3]}. Rewrite as direct course-facing prose.",
            location,
        )

    for pattern in STUDENT_VISIBLE_ENGINEERING_JARGON_PATTERNS:
        if pattern.search(text):
            add_issue(
                issues,
                "major",
                "presentation_boundary_failure",
                "student_visible_engineering_jargon",
                f"{source_kind} contains implementation slang or metaphor matching {pattern.pattern!r}; rewrite as precise course-facing mathematical prose.",
                location,
            )
            break

    for pattern in STUDENT_VISIBLE_BACKSTAGE_IMPLEMENTATION_PATTERNS:
        if pattern.search(text):
            add_issue(
                issues,
                "major",
                "presentation_boundary_failure",
                "student_visible_backstage_implementation_detail",
                f"{source_kind} exposes backstage implementation detail matching {pattern.pattern!r}; move it to code comments or review notes unless implementation is the student task.",
                location,
            )
            break

    for pattern in STUDENT_VISIBLE_PACKAGING_HEADING_PATTERNS:
        if pattern.search(text):
            add_issue(
                issues,
                "major",
                "presentation_boundary_failure",
                "student_visible_packaging_heading",
                f"{source_kind} contains a packaging-style heading matching {pattern.pattern!r}; rewrite it as a concrete mathematical action.",
                location,
            )
            break

    for pattern in STUDENT_VISIBLE_CRUDE_HEADING_PATTERNS:
        if pattern.search(text):
            add_issue(
                issues,
                "major",
                "presentation_boundary_failure",
                "student_visible_crude_heading",
                f"{source_kind} contains a crude or chatty heading matching {pattern.pattern!r}; rewrite it as the mathematical action being trained.",
                location,
            )
            break

    for pattern in STUDENT_VISIBLE_DIRECT_ANSWER_PATTERNS:
        if pattern.search(text) and "<details" not in text:
            add_issue(
                issues,
                "major",
                "feedback_design_failure",
                "student_visible_answer_not_collapsed",
                f"{source_kind} exposes an answer table heading matching {pattern.pattern!r} without a collapsible details block.",
                location,
            )
            break

    if has_unescaped_tex_pipe_in_markdown_table(text):
        add_issue(
            issues,
            "major",
            "output_hygiene_failure",
            "markdown_table_math_pipe_break",
            f"{source_kind} contains TeX with raw pipe characters inside a Markdown table; use \\lvert...\\rvert or escape pipes.",
            location,
        )

    for pattern in STUDENT_VISIBLE_SCAFFOLD_PATTERNS:
        if pattern.search(text):
            add_issue(
                issues,
                "major",
                "presentation_boundary_failure",
                "student_visible_scaffold_language",
                f"{source_kind} contains draft/scaffold wording matching {pattern.pattern!r}; rewrite visible labels as course-facing language.",
                location,
            )
            break


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
    audit_source_path(path, issues)
    cells = nb.get("cells", [])
    notebook_source = "\n".join(as_text(cell.get("source")) for cell in cells)
    if re.search(r"图片坐标|上传.*图片|image coordinate", notebook_source, re.I) and "FileUpload(" not in notebook_source:
        add_issue(
            issues,
            "major",
            "interaction_stability_failure",
            "object_level_experiment_missing_user_input",
            "An image-coordinate experiment appears without a FileUpload entry point for a user-provided image.",
            {"path": str(path)},
        )
    previous_markdown = ""

    for index, cell in enumerate(cells):
        source = as_text(cell.get("source"))
        outputs = cell.get("outputs", []) or []
        code_location = {"cell": index}

        if cell.get("cell_type") == "markdown":
            if has_answer_table_without_prompt(source, previous_markdown):
                add_issue(
                    issues,
                    "major",
                    "feedback_design_failure",
                    "answer_table_without_prompt_table",
                    "A collapsible answer table appears without an incomplete table or explicit fill-in prompt before it.",
                    code_location,
                )
            if has_unnecessary_prompt_table(source):
                add_issue(
                    issues,
                    "major",
                    "cell_modality_failure",
                    "prompt_table_overuse_for_derivation",
                    "A single derivation or short calculation is formatted as a fill-in table. Use numbered prompts, equation blanks, or a short answer checker unless the table compares multiple cases.",
                    code_location,
                )
            if has_mechanical_fill_blank_overuse(source):
                add_issue(
                    issues,
                    "major",
                    "cell_modality_failure",
                    "mechanical_fill_blank_overuse",
                    "A calculation is over-scaffolded with many fill-in blanks. Use an open calculation prompt, plain Markdown working space, or answer checker when the student should organize the solution.",
                    code_location,
                )
            if has_styled_answer_box(source):
                add_issue(
                    issues,
                    "major",
                    "cell_modality_failure",
                    "styled_answer_box_chrome",
                    "A normal calculation prompt uses a styled HTML answer box. Use plain Markdown and leave vertical space with ordinary blank lines instead.",
                    code_location,
                )
            if has_visible_worked_solution(source):
                add_issue(
                    issues,
                    "major",
                    "feedback_design_failure",
                    "visible_worked_solution_before_attempt",
                    "A worked solution is visible before the student has a chance to attempt the calculation. Move it into a details block after a prompt.",
                    code_location,
                )
            scan_presentation_text(issues, source, code_location, "Markdown")
            previous_markdown = source

        if cell.get("cell_type") == "code":
            if any(pattern.search(source) for pattern in SETUP_NOISE_PATTERNS):
                add_issue(
                    issues,
                    "major",
                    "cell_modality_failure",
                    "setup_code_dump_in_public_notebook",
                    "A public notebook exposes long setup/style code. Move reusable configuration into a helper module and keep the visible setup cell short.",
                    code_location,
                )
            if (
                ("print(" in source or "feedback(" in source)
                and not any(marker in source for marker in INTERACTIVE_OR_VISUAL_MARKERS)
                and not re.search(r"\b(?:answer|答案|填空|输入)\b", source, re.I)
            ):
                add_issue(
                    issues,
                    "major",
                    "cell_modality_failure",
                    "static_result_dump_cell",
                    "A code cell appears to print or check fixed calculations without a visual, widget, input, or student-editable answer. Use Markdown/table for static results or turn it into a real interaction.",
                    code_location,
                )
            for literal, line in iter_code_string_literals(source):
                location = dict(code_location)
                if line is not None:
                    location["line"] = line
                scan_presentation_text(
                    issues,
                    literal,
                    location,
                    "Code string literal",
                )
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
        "absolute_path": str(path.resolve()),
        "notebook_sha256": sha256_file(path),
        "audited_at": now_utc(),
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
