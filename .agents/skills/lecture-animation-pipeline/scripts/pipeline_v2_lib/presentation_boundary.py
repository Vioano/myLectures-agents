"""Deterministic learner-facing text policy shared by planning and preflight."""

from __future__ import annotations

import re


PRODUCER_INTENT_LITERAL_MARKERS = (
    "这个动画",
    "本动画",
    "动画想表达",
    "为了帮助观众",
    "制作意图",
    "制作流程",
    "审查",
    "pipeline",
    "skill",
    "稳定版",
    "这里只是反馈",
    "这个控件",
    "这一集",
    "本集",
    "这节课",
    "本视频",
    "重新走一遍",
    "回顾一下",
    "总结一下",
    "今天先停",
    "下一集",
    "下个视频",
    "下期",
)

PRODUCER_INTENT_PATTERNS = (
    re.compile(r"把.{0,12}(因果链|知识点|内容).{0,8}(走一遍|回顾|总结)"),
    re.compile(r"(重新|再).{0,6}(走一遍|回顾|总结).{0,8}(内容|知识点|因果链)?"),
    re.compile(r"我是.{0,16}(键盘手|吉他手|贝斯手|鼓手|主唱|制作人|讲师|老师)"),
    re.compile(r"(下个|下一支|下一条).{0,4}视频.{0,4}见"),
)


def presentation_boundary_risk_signals(text: str) -> list[dict[str, str]]:
    """Return every deterministic producer/process-facing risk signal.

    The preregistration workflow deliberately presents these matches as
    *questions to investigate*, not as an authoring verdict.  The formal gate
    still uses :func:`presentation_boundary_violation` and therefore cannot be
    overridden by an author's self-description.
    """

    payload = str(text).strip()
    lowered = payload.lower()
    signals: list[dict[str, str]] = []
    for marker in PRODUCER_INTENT_LITERAL_MARKERS:
        if marker.lower() in lowered:
            signals.append(
                {
                    "signal_type": "literal_marker",
                    "matched_value": marker,
                    "reason": f"contains producer/process marker {marker!r}",
                }
            )
    for pattern in PRODUCER_INTENT_PATTERNS:
        if pattern.search(payload):
            signals.append(
                {
                    "signal_type": "pattern",
                    "matched_value": pattern.pattern,
                    "reason": f"matches producer/process pattern {pattern.pattern!r}",
                }
            )
    return signals


def presentation_boundary_violation(text: str) -> str | None:
    """Return the matched policy reason for producer/process-facing prose."""

    signals = presentation_boundary_risk_signals(text)
    return signals[0]["reason"] if signals else None
