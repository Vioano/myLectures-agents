#!/usr/bin/env python3
"""Seed a non-production Episode 13 readiness sandbox for the Human UI."""

from __future__ import annotations

import argparse
from pathlib import Path

from supervision.service import SupervisionService
from supervision.store import DataRoot


def expect(result: dict, label: str) -> dict:
    if not result.get("ok"):
        raise RuntimeError(f"{label} failed: {result}")
    return result


def review_candidate(
    service: SupervisionService,
    episode_id: str,
    task_id: str,
    *,
    reviewer: str,
    verdict: str,
    request_id: str,
    findings: list[dict] | None = None,
) -> dict:
    context = expect(
        service.review_context(episode_id, task_id, actor=reviewer),
        f"review context {task_id}",
    )
    return service.review(
        episode_id,
        task_id,
        actor=reviewer,
        verdict=verdict,
        findings=findings,
        review_context_hash=context["review_context_hash"],
        request_id=request_id,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default=".lecture-state")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--episode", default="ep13-multiscale-readiness")
    arguments = parser.parse_args()
    repo = Path(arguments.repo_root).resolve()
    service = SupervisionService(DataRoot(Path(arguments.data_root)), repo)
    episode_id = arguments.episode
    if any(item["episode_id"] == episode_id for item in service.data_root.list_episodes()):
        print(f"{episode_id} already exists")
        return 0
    guidance = "state-supervision/fixtures/demo/guidance.md"
    expect(
        service.create_episode(
            episode_id=episode_id,
            title="第 13 集 · 状态系统就绪沙盒",
            mission="在真实长测前验证注意力投喂、并发租约、独立审查、人工授权和局部恢复。",
            actor="system-planner",
            request_id="demo_episode_create",
        ),
        "episode",
    )
    for wave_id, title, order in (
        ("W0", "启动与合同", 0),
        ("W1", "口播与时间轴", 1),
        ("W2", "分镜制作与审查", 2),
        ("W3", "集成与交付", 3),
    ):
        expect(
            service.add_wave(
                episode_id,
                wave_id=wave_id,
                title=title,
                order=order,
                actor="system-planner",
                request_id=f"demo_wave_{wave_id}",
            ),
            wave_id,
        )
    for scene_id, wave_id, title, order in (
        ("S00", "W0", "范围冻结", 0),
        ("S10", "W1", "口播稿与 TTS 稿", 0),
        ("S20", "W2", "真实数学对象场景", 0),
        ("S21", "W2", "独立质量审查", 1),
        ("S30", "W3", "整集集成", 0),
    ):
        expect(
            service.add_scene(
                episode_id,
                scene_id=scene_id,
                wave_id=wave_id,
                title=title,
                order=order,
                actor="system-planner",
                request_id=f"demo_scene_{scene_id}",
            ),
            scene_id,
        )
    for unit_id, title, kind, parent, order in (
        ("U-EP", "第 13 集", "episode", None, 0),
        ("U-S01", "分镜 S01", "scene", "U-EP", 0),
        ("U-S01-B01", "动画片段 B01", "animation_beat", "U-S01", 0),
        ("U-S02", "分镜 S02", "scene", "U-EP", 1),
    ):
        expect(
            service.add_content_unit(
                episode_id,
                unit_id=unit_id,
                title=title,
                kind=kind,
                parent_unit_id=parent,
                order=order,
                actor="system-planner",
                request_id=f"demo_content_{unit_id}",
            ),
            unit_id,
        )
    for deliverable_id, title, order, roles in (
        ("D-CONTRACT", "范围与合同", 0, ["contract"]),
        ("D-AUDIO", "口播音频与时间轴", 1, ["tts_script", "narration_audio"]),
        ("D-VISUAL", "分镜与动画", 2, ["storyboard", "source"]),
        ("D-QA", "独立质量审查", 3, ["evidence"]),
        ("D-INTEGRATION", "音画集成", 4, ["integration"]),
        ("D-RELEASE", "发布授权", 5, ["release_note"]),
    ):
        expect(
            service.add_deliverable(
                episode_id,
                deliverable_id=deliverable_id,
                title=title,
                artifact_roles=roles,
                order=order,
                actor="system-planner",
                request_id=f"demo_deliverable_{deliverable_id}",
            ),
            deliverable_id,
        )
    task_specs = (
        dict(task_id="T001", title="冻结分集任务合同", goal="形成可哈希、可审查的分集任务合同。", wave_id="W0", scene_id="S00", content_unit_id="U-EP", deliverable_id="D-CONTRACT", required_artifact_roles=["contract"], critical_path=True, unlock_value=10, priority=10),
        dict(task_id="T010", title="将口播稿转换为 TTS 稿", goal="按已绑定发音规范处理公式与希腊字母，不改变口播稿。", wave_id="W1", scene_id="S10", content_unit_id="U-S01", deliverable_id="D-AUDIO", dependencies=["T001"], required_artifact_roles=["tts_script"], critical_path=True, unlock_value=8, priority=8, tags=["tts"]),
        dict(task_id="T020", title="设计 S01 真实数学对象驱动的分镜", goal="为 S01 建立数学身份、显示映射与舞台调度。", wave_id="W2", scene_id="S20", content_unit_id="U-S01", deliverable_id="D-VISUAL", dependencies=["T001"], required_artifact_roles=["storyboard"], critical_path=True, unlock_value=7, priority=7, tags=["math_object"]),
        dict(task_id="T025", title="推进 S02 分镜", goal="在 S01 的 TTS 尚未结束时并行推进独立的 S02 分镜。", wave_id="W2", scene_id="S20", content_unit_id="U-S02", deliverable_id="D-VISUAL", dependencies=["T001"], required_artifact_roles=["storyboard"], priority=6, tags=["math_object"]),
        dict(task_id="T030", title="制作 S01-B01 动画候选", goal="生成可独立审查的源代码候选与证据。", wave_id="W2", scene_id="S20", content_unit_id="U-S01-B01", deliverable_id="D-VISUAL", dependencies=["T001"], required_artifact_roles=["source"], unlock_value=6, priority=6),
        dict(task_id="T040", title="整合集成候选", goal="只消费通过审查的场景与音频制品。", wave_id="W3", scene_id="S30", content_unit_id="U-EP", deliverable_id="D-INTEGRATION", dependencies=["T010", "T030"], required_artifact_roles=["integration"], critical_path=True, unlock_value=5, priority=5),
        dict(task_id="T050", title="补齐 S01 来源证据", goal="在来源缺失时停止并显式报告缺口。", wave_id="W2", scene_id="S21", content_unit_id="U-S01", deliverable_id="D-QA", dependencies=["T001"], required_artifact_roles=["evidence"], priority=3),
        dict(task_id="T060", title="用户审片授权", goal="把候选和证据交给用户，等待明确授权。", wave_id="W3", scene_id="S30", content_unit_id="U-EP", deliverable_id="D-RELEASE", dependencies=["T001"], required_artifact_roles=["release_note"], human_gate=True, priority=9, kind="release", tags=["release_required"]),
    )
    for spec in task_specs:
        references = [
            {
                "path": guidance,
                "purpose": "Sandbox execution contract",
                "context_class": "episode_material",
                "context_slot": "episode.sandbox.contract",
                "scope": "episode",
                "mutable": True,
                "precedence": 300,
            }
        ]
        if "tts" in spec.get("tags", []):
            references.append(
                {
                    "path": ".agents/skills/lecture-animation-pipeline/references/tts-pronunciation-registry.md",
                    "purpose": "Canonical IndexTTS pronunciation registry",
                    "context_class": "stable_rule",
                    "context_version": "indextts-registry-v1",
                    "context_slot": "tts.pronunciation.rules",
                    "scope": "service:IndexTTS",
                    "service_binding": "IndexTTS",
                    "mutable": False,
                    "precedence": 100,
                }
            )
        expect(
            service.add_task(
                episode_id,
                actor="system-planner",
                request_id=f"demo_task_{spec['task_id']}",
                references=references,
                **spec,
            ),
            spec["task_id"],
        )
    expect(
        service.add_feedback(
            episode_id,
            feedback_id="FB-MATH-IDENTITY",
            pattern_key="math_object_identity_and_display_mapping",
            instruction="明确真实对象、显示映射和允许的视觉优化；不要把参数化本身当成语义真实性。",
            source="human_review",
            applies_to=["math_object"],
            actor="system-planner",
            request_id="demo_feedback_math",
        ),
        "feedback",
    )
    # Approve the startup contract so downstream work becomes meaningful.
    expect(service.begin(episode_id, "T001", actor="Ada", request_id="demo_begin_T001"), "begin T001")
    expect(
        service.submit(
            episode_id,
            "T001",
            actor="Ada",
            artifacts=[{"role": "contract", "path": "state-supervision/fixtures/demo/episode-contract.txt"}],
            request_id="demo_submit_T001",
        ),
        "submit T001",
    )
    expect(
        review_candidate(
            service,
            episode_id,
            "T001",
            reviewer="Bo",
            verdict="pass",
            request_id="demo_review_T001",
        ),
        "review T001",
    )
    # Keep one task actively leased.
    expect(service.begin(episode_id, "T010", actor="Ada", request_id="demo_begin_T010"), "begin T010")
    # A second worker advances another scene without waiting for the TTS route.
    expect(service.begin(episode_id, "T025", actor="Gita", request_id="demo_begin_T025"), "begin T025")
    # Show a rejected candidate that is ready for bounded rework.
    expect(service.begin(episode_id, "T020", actor="Cai", request_id="demo_begin_T020"), "begin T020")
    expect(
        service.submit(
            episode_id,
            "T020",
            actor="Cai",
            artifacts=[{"role": "storyboard", "path": "state-supervision/fixtures/demo/storyboard.md"}],
            request_id="demo_submit_T020",
        ),
        "submit T020",
    )
    expect(
        review_candidate(
            service,
            episode_id,
            "T020",
            reviewer="Reviewer-1",
            verdict="revise",
            findings=[{"severity": "major", "description": "显示映射尚未明确。"}],
            request_id="demo_review_T020",
        ),
        "review T020",
    )
    # Show a candidate awaiting independent review.
    expect(service.begin(episode_id, "T030", actor="Dai", request_id="demo_begin_T030"), "begin T030")
    expect(
        service.submit(
            episode_id,
            "T030",
            actor="Dai",
            artifacts=[{"role": "source", "path": "state-supervision/fixtures/demo/animation.py"}],
            request_id="demo_submit_T030",
        ),
        "submit T030",
    )
    # Show an explicit gap rather than silent guessing.
    expect(
        service.gap(
            episode_id,
            "T050",
            actor="Eve",
            reason="缺少可核验的来源 transcript。",
            kind="missing_source",
            request_id="demo_gap_T050",
        ),
        "gap T050",
    )
    # Reach the explicit Human gate.
    expect(service.begin(episode_id, "T060", actor="Fang", request_id="demo_begin_T060"), "begin T060")
    expect(
        service.submit(
            episode_id,
            "T060",
            actor="Fang",
            artifacts=[{"role": "release_note", "path": "state-supervision/fixtures/demo/release-note.md"}],
            request_id="demo_submit_T060",
        ),
        "submit T060",
    )
    expect(
        review_candidate(
            service,
            episode_id,
            "T060",
            reviewer="Reviewer-2",
            verdict="pass",
            request_id="demo_review_T060",
        ),
        "review T060",
    )
    expect(
        service.annotate(
            episode_id,
            actor="human-ui",
            target_id="T030",
            body="这里用于演示网页标注如何成为增量事件。",
            severity="note",
            request_id="demo_annotation_T030",
        ),
        "annotation",
    )
    print(f"seeded {episode_id} at {Path(arguments.data_root).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
