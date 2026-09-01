#!/usr/bin/env python3
"""Prepare a fresh eight-minute simulation without seeding future pressure."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_ROOT = PROJECT_ROOT / "state-supervision"
EVALUATION_ROOT = PROJECT_ROOT / "state-supervision-evaluation"
THIS_ROOT = Path(__file__).resolve().parent
DEFAULT_RESULTS = THIS_ROOT / "results"
sys.path.insert(0, str(SYSTEM_ROOT))

from supervision.service import SupervisionService  # noqa: E402
from supervision.store import DataRoot  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def source_revision() -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def expect(result: dict[str, Any], label: str) -> dict[str, Any]:
    if not result.get("ok"):
        raise RuntimeError(f"{label} failed: {result}")
    return result


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, value: dict[str, Any]) -> None:
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def render_template(path: Path, replacements: dict[str, str]) -> str:
    value = path.read_text(encoding="utf-8")
    for token, replacement in replacements.items():
        value = value.replace(token, replacement)
    return value


def copy_public_inputs(repo: Path) -> None:
    copy_map = {
        THIS_ROOT / "fixtures" / "baseline-input.md": repo / "inputs" / "baseline.md",
        SYSTEM_ROOT / "OPERATOR_GUIDE.md": repo / "public" / "OPERATOR_GUIDE.md",
        PROJECT_ROOT
        / ".agents/skills/lecture-animation-pipeline/references/tts-pronunciation-registry.md": repo
        / "references/tts-pronunciation-registry.md",
        PROJECT_ROOT
        / ".agents/skills/lecture-animation-pipeline-legacy/references/20-math-object-driven-animation.md": repo
        / "references/math-object-driven-animation.md",
        PROJECT_ROOT
        / ".agents/skills/lecture-animation-pipeline/references/scene-production-and-review.md": repo
        / "references/scene-production-and-review.md",
    }
    for source, destination in copy_map.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

    validator_source = SYSTEM_ROOT / "validators" / "artifact-integrity"
    validator_destination = repo / "validators" / "artifact-integrity"
    shutil.copytree(validator_source, validator_destination)

    write(
        repo / "tools" / "make_placeholder_media.py",
        '''#!/usr/bin/env python3
"""Create tiny decodable review placeholders; never production media."""
from pathlib import Path
import argparse
import math
import struct
import subprocess
import wave

parser = argparse.ArgumentParser()
parser.add_argument("kind", choices=("audio", "video"))
parser.add_argument("path", type=Path)
parser.add_argument("--seconds", type=float, default=2.0)
args = parser.parse_args()
args.path.parent.mkdir(parents=True, exist_ok=True)

if args.kind == "audio":
    rate = 16000
    frames = max(1, int(rate * args.seconds))
    with wave.open(str(args.path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        for index in range(frames):
            sample = int(900 * math.sin(2 * math.pi * 220 * index / rate))
            output.writeframesraw(struct.pack("<h", sample))
else:
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=0x08111f:s=960x540:r=24",
            "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000",
            "-t", str(args.seconds), "-shortest", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-c:a", "aac", str(args.path),
        ],
        check=True,
    )
print(args.path)
''',
    )


def add_task(
    service: SupervisionService,
    episode_id: str,
    task_id: str,
    *,
    title: str,
    goal: str,
    wave_id: str,
    scene_id: str,
    content_unit_id: str,
    deliverable_id: str,
    work_key: str,
    roles: list[str],
    dependencies: list[str] | None = None,
    references: list[dict[str, Any]] | None = None,
    priority: int = 0,
    unlock_value: int = 0,
    critical_path: bool = False,
    human_gate: bool = False,
    validators: list[str] | None = None,
    tags: list[str] | None = None,
) -> None:
    expect(
        service.add_task(
            episode_id,
            task_id=task_id,
            title=title,
            goal=goal,
            wave_id=wave_id,
            scene_id=scene_id,
            content_unit_id=content_unit_id,
            deliverable_id=deliverable_id,
            work_key=work_key,
            required_artifact_roles=roles,
            dependencies=dependencies or [],
            references=references or [],
            priority=priority,
            unlock_value=unlock_value,
            critical_path=critical_path,
            human_gate=human_gate,
            validators=validators or [],
            tags=tags or [],
            actor="simulation-planner",
            request_id=f"sim-add-{task_id}",
            allowed_side_effects=["write:out"],
            stop_conditions=["wall_clock_cutoff", "missing_required_input"],
        ),
        f"add {task_id}",
    )


def prepare_round(
    results_root: Path,
    *,
    run_id: str,
    episode_id: str,
) -> dict[str, Any]:
    run_root = results_root.resolve() / run_id
    workspace = run_root / "workspaces" / "operator"
    repo = workspace / "repo"
    state = workspace / "state"
    if run_root.exists():
        raise FileExistsError(f"simulation run already exists: {run_root}")
    repo.mkdir(parents=True)
    state.mkdir(parents=True)
    copy_public_inputs(repo)

    feedback_path = run_root / "AGENT_EXPERIENCE.md"
    human_path = run_root / "HUMAN_OBSERVATIONS.md"
    operator_cli = EVALUATION_ROOT / "short-tests" / "operator_cli.py"
    replacements = {
        "__RUN_ID__": run_id,
        "__EPISODE_ID__": episode_id,
        "__OPERATOR_CLI__": str(operator_cli.resolve()),
        "__REPO_ROOT__": str(repo.resolve()),
        "__FEEDBACK_PATH__": str(feedback_path.resolve()),
    }
    write(
        workspace / "MISSION.md",
        render_template(THIS_ROOT / "BLACKBOX_AGENT_MISSION.template.md", replacements),
    )
    write(
        feedback_path,
        render_template(THIS_ROOT / "AGENT_EXPERIENCE.template.md", replacements),
    )
    write(
        human_path,
        (THIS_ROOT / "HUMAN_OBSERVATION_CHECKLIST.md").read_text(encoding="utf-8"),
    )
    write(workspace / "transcript.jsonl", "")
    environment = {
        "schema": "state-supervision-simulation-game-environment-v1",
        "run_id": run_id,
        "episode_id": episode_id,
        "cli": str((SYSTEM_ROOT / "supervise.py").resolve()),
        "operator_cli": str(operator_cli.resolve()),
        "operator_guide": str((repo / "public" / "OPERATOR_GUIDE.md").resolve()),
        "repo_root": str(repo.resolve()),
        "data_root": str(state.resolve()),
        "feedback_path": str(feedback_path.resolve()),
        "browser_url": "http://127.0.0.1:4321/",
        "wall_clock_seconds": 480,
        "freeze_at_seconds": 450,
    }
    write_json(workspace / "environment.json", environment)

    service = SupervisionService(DataRoot(state), repo)
    expect(
        service.create_episode(
            episode_id=episode_id,
            title="八分钟模拟 · 原始全 TTS 计划",
            mission=(
                "按最初设想以 TTS 完成 S01-S05 口播，并行推进前后半动画，"
                "形成可审片集成候选；当前没有替代录音路线。"
            ),
            actor="simulation-planner",
            request_id="sim-create-episode",
        ),
        "create episode",
    )
    expect(
        service.configure_dispatch_policy(
            episode_id,
            actor="simulation-planner",
            reason="八分钟演练允许三个制作工位和两个独立审查工位按需流动领取",
            max_active_authors=3,
            reviewer_capacity=2,
            mode="elastic",
            request_id="sim-dispatch-policy",
        ),
        "dispatch policy",
    )

    for agent_id, role, capabilities in (
        ("blind-operator", "author", ["production", "production_contract", "narration_audio", "experience_report"]),
        ("visual-worker", "author", ["production", "source", "timeline"]),
        ("integration-worker", "author", ["production", "integration"]),
        ("independent-reviewer", "reviewer", ["independent_review"]),
        ("human-observer", "human", ["human_review", "annotation"]),
    ):
        expect(
            service.register_agent(
                episode_id,
                agent_id=agent_id,
                actor="simulation-planner",
                role=role,
                capabilities=capabilities,
                model="simulation",
                presence="planned",
                request_id=f"sim-register-{agent_id}",
            ),
            f"register {agent_id}",
        )

    for wave_id, title, order in (
        ("W0", "启动与合同", 0),
        ("W1", "并行制作", 1),
        ("W2", "集成与审片", 2),
        ("W3", "复盘与冻结", 3),
    ):
        expect(
            service.add_wave(
                episode_id,
                wave_id=wave_id,
                title=title,
                order=order,
                actor="simulation-planner",
                request_id=f"sim-wave-{wave_id}",
            ),
            f"wave {wave_id}",
        )
    for scene_id, wave_id, title, order in (
        ("S00", "W0", "范围冻结", 0),
        ("S10", "W1", "前半 S01-S02", 0),
        ("S20", "W1", "后半 S03-S05", 1),
        ("S30", "W2", "集成与审片", 0),
        ("S40", "W3", "体验复盘", 0),
    ):
        expect(
            service.add_scene(
                episode_id,
                scene_id=scene_id,
                wave_id=wave_id,
                title=title,
                order=order,
                actor="simulation-planner",
                request_id=f"sim-scene-{scene_id}",
            ),
            f"scene {scene_id}",
        )

    for unit_id, title, kind, parent, order in (
        ("U-EP", "整集", "episode", None, 0),
        ("U-FRONT", "前半 S01-S02", "scene_group", "U-EP", 0),
        ("U-FRONT-B01", "前半动画片段", "animation_beat", "U-FRONT", 0),
        ("U-BACK", "后半 S03-S05", "scene_group", "U-EP", 1),
        ("U-BACK-B01", "后半动画片段", "animation_beat", "U-BACK", 0),
    ):
        expect(
            service.add_content_unit(
                episode_id,
                unit_id=unit_id,
                title=title,
                kind=kind,
                parent_unit_id=parent,
                order=order,
                actor="simulation-planner",
                request_id=f"sim-content-{unit_id}",
            ),
            f"content {unit_id}",
        )

    for deliverable_id, title, roles, order in (
        ("D-CONTRACT", "生产合同", ["production_contract"], 0),
        ("D-AUDIO-FRONT", "前半口播音频", ["narration_audio"], 1),
        ("D-AUDIO-BACK", "后半口播音频", ["narration_audio"], 2),
        ("D-VISUAL-FRONT", "前半动画源与时间轴", ["source", "timeline"], 3),
        ("D-VISUAL-BACK", "后半动画源与时间轴", ["source", "timeline"], 4),
        ("D-INTEGRATION", "集成审片候选", ["integration"], 5),
        ("D-EVALUATION", "Agent 体验报告", ["experience_report"], 6),
    ):
        expect(
            service.add_deliverable(
                episode_id,
                deliverable_id=deliverable_id,
                title=title,
                artifact_roles=roles,
                order=order,
                actor="simulation-planner",
                request_id=f"sim-deliverable-{deliverable_id}",
            ),
            f"deliverable {deliverable_id}",
        )

    baseline = {
        "path": "inputs/baseline.md",
        "purpose": "Original all-TTS production assumption and placeholder boundary",
        "context_class": "episode_material",
        "context_slot": "episode.original_plan",
        "scope": "episode",
        "precedence": 300,
    }
    tts_rules = {
        "path": "references/tts-pronunciation-registry.md",
        "purpose": "Pinned IndexTTS pronunciation rules",
        "context_class": "stable_rule",
        "context_slot": "tts.pronunciation.rules",
        "scope": "service:IndexTTS",
        "service_binding": "IndexTTS",
        "precedence": 100,
    }
    math_rules = {
        "path": "references/math-object-driven-animation.md",
        "purpose": "Mathematical-object identity and allowed display mapping",
        "context_class": "stable_rule",
        "context_slot": "animation.math_object_truth",
        "scope": "animation",
        "precedence": 100,
    }
    production_rules = {
        "path": "references/scene-production-and-review.md",
        "purpose": "Scene production and review contract",
        "context_class": "stable_rule",
        "context_slot": "animation.production_contract",
        "scope": "animation",
        "precedence": 110,
    }
    validator = ["validators/artifact-integrity/manifest.json"]

    add_task(
        service,
        episode_id,
        "T001",
        title="冻结最初全 TTS 生产合同",
        goal="用一小段 Markdown 冻结当前原始计划、占位边界和八分钟停止条件。",
        wave_id="W0",
        scene_id="S00",
        content_unit_id="U-EP",
        deliverable_id="D-CONTRACT",
        work_key="U-EP.D-CONTRACT.freeze",
        roles=["production_contract"],
        references=[baseline],
        priority=100,
        unlock_value=20,
        critical_path=True,
    )
    add_task(
        service,
        episode_id,
        "T010",
        title="以 TTS 完成前半 S01-S02 口播",
        goal="读取绑定发音规则，写短 TTS 稿并生成可解码的微型 WAV 占位音频。",
        wave_id="W1",
        scene_id="S10",
        content_unit_id="U-FRONT",
        deliverable_id="D-AUDIO-FRONT",
        work_key="U-FRONT.D-AUDIO.narration",
        roles=["narration_audio"],
        dependencies=["T001"],
        references=[baseline, tts_rules],
        priority=90,
        unlock_value=12,
        critical_path=True,
        validators=validator,
        tags=["tts", "front_half"],
    )
    add_task(
        service,
        episode_id,
        "T012",
        title="以 TTS 完成后半 S03-S05 口播",
        goal="按最初计划读取绑定发音规则，生成后半 TTS 稿和微型 WAV 占位音频。",
        wave_id="W1",
        scene_id="S20",
        content_unit_id="U-BACK",
        deliverable_id="D-AUDIO-BACK",
        work_key="U-BACK.D-AUDIO.narration",
        roles=["narration_audio"],
        dependencies=["T001"],
        references=[baseline, tts_rules],
        priority=80,
        unlock_value=11,
        critical_path=True,
        validators=validator,
        tags=["tts", "back_half"],
    )
    add_task(
        service,
        episode_id,
        "T020",
        title="模拟制作前半 Manim 源码与时间轴",
        goal="创建一行模拟 Python 源码和一个正时长单拍 timeline JSON，不渲染。",
        wave_id="W1",
        scene_id="S10",
        content_unit_id="U-FRONT-B01",
        deliverable_id="D-VISUAL-FRONT",
        work_key="U-FRONT-B01.D-VISUAL.source-timeline",
        roles=["source", "timeline"],
        dependencies=["T001"],
        references=[baseline, math_rules, production_rules],
        priority=70,
        unlock_value=10,
        validators=validator,
        tags=["animation", "front_half"],
    )
    add_task(
        service,
        episode_id,
        "T022",
        title="模拟制作后半 Manim 源码与时间轴",
        goal="创建一行模拟 Python 源码和一个正时长单拍 timeline JSON，不渲染。",
        wave_id="W1",
        scene_id="S20",
        content_unit_id="U-BACK-B01",
        deliverable_id="D-VISUAL-BACK",
        work_key="U-BACK-B01.D-VISUAL.source-timeline",
        roles=["source", "timeline"],
        dependencies=["T001"],
        references=[baseline, math_rules, production_rules],
        priority=60,
        unlock_value=9,
        validators=validator,
        tags=["animation", "back_half"],
    )
    add_task(
        service,
        episode_id,
        "T040",
        title="生成可播放的模拟集成审片候选",
        goal="组合获批的前后半音频与视觉占位证据，生成短可播放 review MP4。",
        wave_id="W2",
        scene_id="S30",
        content_unit_id="U-EP",
        deliverable_id="D-INTEGRATION",
        work_key="U-EP.D-INTEGRATION.review-cut",
        roles=["integration"],
        dependencies=["T010", "T012", "T020", "T022"],
        references=[baseline],
        priority=95,
        unlock_value=15,
        critical_path=True,
        human_gate=True,
        validators=validator,
        tags=["integration", "human_review"],
    )
    feedback_reference = {
        "path": str((THIS_ROOT / "AGENT_EXPERIENCE.template.md").resolve()),
        "purpose": "Black-box Agent experience report template",
        "context_class": "task_template",
        "context_slot": "evaluation.agent_experience",
        "scope": "task:T900",
        "precedence": 200,
    }
    add_task(
        service,
        episode_id,
        "T900",
        title="冻结黑盒 Agent 体验报告",
        goal="根据亲身操作填写独立反馈文件，披露文件读取、歧义、人为提示和上下文精度。",
        wave_id="W3",
        scene_id="S40",
        content_unit_id="U-EP",
        deliverable_id="D-EVALUATION",
        work_key="U-EP.D-EVALUATION.blackbox-report",
        roles=["experience_report"],
        dependencies=["T040"],
        references=[feedback_reference],
        priority=100,
        unlock_value=0,
        critical_path=True,
        tags=["evaluation", "blackbox"],
    )

    overview = service.overview(episode_id)
    next_action = service.next_action(episode_id, actor="blind-operator")
    if not next_action.get("ok") or ((next_action.get("next") or {}).get("task") or {}).get("task_id") != "T001":
        raise RuntimeError(f"fresh round did not start at T001: {next_action}")
    if overview.get("routes") or overview.get("changes"):
        raise RuntimeError("fresh round unexpectedly contains pressure state")

    prepared_at = utc_now()
    manifest = {
        "schema": "state-supervision-simulation-game-run-v1",
        "run_id": run_id,
        "episode_id": episode_id,
        "prepared_at": prepared_at,
        "status": "prepared_not_started",
        "wall_clock_seconds": 480,
        "freeze_at_seconds": 450,
        "initial_assumption": "all_tts",
        "task_count": len(overview["tasks"]),
        "initial_next": "T001",
        "workspace": str(workspace.resolve()),
        "browser_url": "http://127.0.0.1:4321/",
        "source_commit": source_revision(),
    }
    write_json(run_root / "run-manifest.json", manifest)
    write_json(
        run_root / "oracle.json",
        {
            "schema": "state-supervision-simulation-game-oracle-v1",
            "hidden_from_operator": True,
            "initial_forbidden_facts": [
                "late human recording",
                "T010 planned review rejection",
                "T012 route replacement",
                "duplicate-work probe",
            ],
            "pressure": {
                "route_source": "T012",
                "replacement_task": "T112",
                "strategy": "hybrid-human-recording",
                "expected_preserved": ["T010", "T020", "T022"],
                "expected_rewired": ["T040"],
            },
        },
    )
    return {
        "run_root": str(run_root),
        "workspace": str(workspace),
        "episode_id": episode_id,
        "manifest": manifest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--run-id")
    parser.add_argument("--episode-id")
    arguments = parser.parse_args()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id = arguments.run_id or f"game-{timestamp}"
    episode_id = arguments.episode_id or f"SIM-GAME-{timestamp}"
    result = prepare_round(
        arguments.results_root,
        run_id=run_id,
        episode_id=episode_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
