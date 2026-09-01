#!/usr/bin/env python3
"""Inject the late recording pressure through public domain operations."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import struct
import sys
from typing import Any
import wave


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_ROOT = PROJECT_ROOT / "state-supervision"
THIS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SYSTEM_ROOT))

from supervision.service import SupervisionService  # noqa: E402
from supervision.store import DataRoot  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def expect(result: dict[str, Any], label: str) -> dict[str, Any]:
    if not result.get("ok"):
        raise RuntimeError(f"{label} failed: {result}")
    return result


def load_environment(workspace: Path) -> tuple[dict[str, Any], SupervisionService, Path]:
    workspace = workspace.resolve()
    environment = json.loads(
        (workspace / "environment.json").read_text(encoding="utf-8")
    )
    repo = Path(environment["repo_root"])
    service = SupervisionService(DataRoot(Path(environment["data_root"])), repo)
    return environment, service, repo


def make_upload(path: Path, seconds: float = 3.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rate = 16000
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        for index in range(frames):
            sample = int(1100 * math.sin(2 * math.pi * 196 * index / rate))
            output.writeframesraw(struct.pack("<h", sample))


def add_upload(
    service: SupervisionService,
    episode_id: str,
    repo: Path,
) -> dict[str, Any]:
    overview = service.overview(episode_id)
    existing = next(
        (task for task in overview["tasks"] if task["task_id"] == "T111"), None
    )
    if existing is not None:
        return {
            "ok": True,
            "duplicate": True,
            "task": existing,
            "artifact_ids": existing.get("approved_artifact_ids", []),
        }

    request_source = THIS_ROOT / "fixtures" / "late-human-recording-request.md"
    request_path = repo / "incoming" / "late-human-recording-request.md"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(request_source.read_text(encoding="utf-8"), encoding="utf-8")
    upload_path = repo / "incoming" / "user-recording-s03-s05.wav"
    make_upload(upload_path)

    expect(
        service.add_content_unit(
            episode_id,
            unit_id="U-HUMAN-UPLOAD",
            title="临时上传的人声 S03-S05",
            kind="source_recording",
            parent_unit_id="U-BACK",
            order=99,
            actor="human-observer",
            request_id="pressure-add-upload-content",
        ),
        "add upload content",
    )
    expect(
        service.add_deliverable(
            episode_id,
            deliverable_id="D-HUMAN-UPLOAD",
            title="用户原始录音",
            artifact_roles=["human_recording_raw"],
            order=99,
            actor="human-observer",
            request_id="pressure-add-upload-deliverable",
        ),
        "add upload deliverable",
    )
    expect(
        service.add_task(
            episode_id,
            task_id="T111",
            title="登记用户临时上传的后半录音",
            goal="登记并固定 S03-S05 用户录音的字节身份，供替代路线消费。",
            wave_id="W1",
            scene_id="S20",
            content_unit_id="U-HUMAN-UPLOAD",
            deliverable_id="D-HUMAN-UPLOAD",
            work_key="U-HUMAN-UPLOAD.D-HUMAN-UPLOAD.register",
            dependencies=["T001"],
            references=[
                {
                    "path": "incoming/late-human-recording-request.md",
                    "purpose": "New user instruction that did not exist at initialization",
                    "context_class": "temporary_override",
                    "context_slot": "episode.narration.route_change",
                    "scope": "content:U-BACK",
                    "precedence": 500,
                }
            ],
            required_artifact_roles=["human_recording_raw"],
            priority=200,
            unlock_value=20,
            critical_path=True,
            actor="human-observer",
            request_id="pressure-add-upload-task",
            tags=["user_upload", "late_change"],
        ),
        "add upload task",
    )
    expect(
        service.begin(
            episode_id,
            "T111",
            actor="human-upload",
            request_id="pressure-begin-upload",
        ),
        "begin upload",
    )
    submitted = expect(
        service.submit(
            episode_id,
            "T111",
            actor="human-upload",
            artifacts=[
                {
                    "role": "human_recording_raw",
                    "path": "incoming/user-recording-s03-s05.wav",
                }
            ],
            request_id="pressure-submit-upload",
        ),
        "submit upload",
    )
    context = expect(
        service.review_context(
            episode_id,
            "T111",
            actor="intake-reviewer",
        ),
        "review upload context",
    )
    expect(
        service.review(
            episode_id,
            "T111",
            actor="intake-reviewer",
            verdict="pass",
            review_context_hash=context["review_context_hash"],
            request_id="pressure-review-upload",
        ),
        "review upload",
    )
    artifact_ids = [
        item["artifact_id"] for item in submitted.get("artifacts", [])
    ]
    return {
        "ok": True,
        "duplicate": False,
        "task_id": "T111",
        "artifact_ids": artifact_ids,
        "upload_path": str(upload_path),
    }


def switch_back_half_route(
    service: SupervisionService,
    episode_id: str,
) -> dict[str, Any]:
    overview = service.overview(episode_id)
    existing = next(
        (route for route in overview["routes"] if route.get("replacement_task_id") == "T112"),
        None,
    )
    if existing is not None:
        return {"ok": True, "duplicate": True, "route_switch": existing}
    upload_task = next(
        (task for task in overview["tasks"] if task["task_id"] == "T111"), None
    )
    if upload_task is None or upload_task.get("status") != "approved":
        raise RuntimeError("T111 must be approved before the route switch")
    artifact_ids = list(upload_task.get("approved_artifact_ids", []))
    if len(artifact_ids) != 1:
        raise RuntimeError(f"expected one approved upload artifact, got {artifact_ids}")

    return expect(
        service.switch_route(
            episode_id,
            "T012",
            "T112",
            actor="human-observer",
            strategy="hybrid-human-recording",
            reason=(
                "用户在原全 TTS 计划运行后上传 S03-S05 人声；前半保留 TTS，"
                "后半改为听写、对齐、分镜切分后的用户录音。"
            ),
            replacement_spec={
                "title": "处理用户录音并完成后半 S03-S05 口播",
                "goal": (
                    "对已登记录音模拟听写、时间对齐和分镜切分；提交 transcript、"
                    "alignment、segment_map 证据与稳定 narration_audio 输出。"
                ),
                "wave_id": "W1",
                "scene_id": "S20",
                "content_unit_id": "U-BACK",
                "deliverable_id": "D-AUDIO-BACK",
                "dependencies": ["T001", "T111"],
                "references": [
                    {
                        "path": "incoming/late-human-recording-request.md",
                        "purpose": "Late user route-change instruction",
                        "context_class": "temporary_override",
                        "context_slot": "episode.narration.route_change",
                        "scope": "content:U-BACK",
                        "precedence": 500,
                    },
                    {
                        "path": "inputs/baseline.md",
                        "purpose": "Original placeholder and integration boundary",
                        "context_class": "episode_material",
                        "context_slot": "episode.original_plan",
                        "scope": "episode",
                        "precedence": 300,
                    },
                ],
                "required_artifact_roles": ["narration_audio"],
                "input_artifact_ids": artifact_ids,
                "critical_path": True,
                "unlock_value": 20,
                "priority": 210,
                "tags": ["human_recording", "back_half", "late_change"],
                "allowed_side_effects": ["write:out"],
                "stop_conditions": ["wall_clock_cutoff", "missing_required_input"],
            },
            request_id="pressure-switch-back-half-route",
        ),
        "switch back-half route",
    )


def duplicate_work_probe(
    service: SupervisionService,
    episode_id: str,
) -> dict[str, Any]:
    result = service.add_task(
        episode_id,
        task_id="T113",
        title="重复处理后半口播",
        goal="This task must be denied as duplicate semantic work.",
        wave_id="W1",
        scene_id="S20",
        content_unit_id="U-BACK",
        deliverable_id="D-AUDIO-BACK",
        work_key="U-BACK.D-AUDIO.narration",
        dependencies=["T001", "T111"],
        required_artifact_roles=["narration_audio"],
        actor="spare-worker",
        request_id="pressure-duplicate-work-probe",
    )
    if result.get("ok") or result.get("code") != "duplicate_work_obligation":
        raise RuntimeError(f"duplicate work probe was not denied correctly: {result}")
    return result


def update_manifest(workspace: Path, action: str, result: dict[str, Any]) -> None:
    run_root = workspace.resolve().parents[1]
    path = run_root / "run-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    pressure = list(manifest.get("pressure_events", []))
    pressure.append(
        {
            "action": action,
            "recorded_at": utc_now(),
            "result_ok": bool(result.get("ok")),
        }
    )
    manifest["pressure_events"] = pressure
    manifest["status"] = "pressure_active"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("action", choices=("upload", "switch", "duplicate-probe", "all", "status"))
    arguments = parser.parse_args()
    environment, service, repo = load_environment(arguments.workspace)
    episode_id = str(environment["episode_id"])

    if arguments.action == "status":
        result = {
            "ok": True,
            "episode_id": episode_id,
            "routes": service.overview(episode_id)["routes"],
            "tasks": [
                {"task_id": task["task_id"], "status": task["status"]}
                for task in service.overview(episode_id)["tasks"]
            ],
        }
    elif arguments.action == "upload":
        result = add_upload(service, episode_id, repo)
        update_manifest(arguments.workspace, "upload", result)
    elif arguments.action == "switch":
        result = switch_back_half_route(service, episode_id)
        update_manifest(arguments.workspace, "switch", result)
    elif arguments.action == "duplicate-probe":
        result = duplicate_work_probe(service, episode_id)
        update_manifest(arguments.workspace, "duplicate-probe", {"ok": True})
    else:
        upload = add_upload(service, episode_id, repo)
        switched = switch_back_half_route(service, episode_id)
        duplicate = duplicate_work_probe(service, episode_id)
        result = {
            "ok": True,
            "upload": upload,
            "switch": switched,
            "duplicate_probe": duplicate,
        }
        update_manifest(arguments.workspace, "all", result)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
