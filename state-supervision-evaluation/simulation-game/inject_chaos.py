#!/usr/bin/env python3
"""Inject explicit supersessions and unresolved semantic contradictions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import inject_pressure


def expect(result: dict, label: str) -> dict:
    if not result.get("ok"):
        raise RuntimeError(f"{label} failed: {result}")
    return result


def ensure_asset_inputs(repo: Path) -> None:
    incoming = repo / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    (incoming / "sprite-request.md").write_text(
        "Human request A: S04 must prominently use character-sprite.png. "
        "This requirement remains active until an explicit decision withdraws it.\n",
        encoding="utf-8",
    )
    (incoming / "sprite-licence-revoked.md").write_text(
        "Human/legal request B: the licence for character-sprite.png is revoked. "
        "Do not use, trace, transform, or derive from it. This requirement remains active.\n",
        encoding="utf-8",
    )
    (incoming / "timeline-lock.md").write_text(
        "The approved edit has no empty interval. Total runtime and every existing "
        "scene timecode and duration are immutable.\n",
        encoding="utf-8",
    )


def switch_to_3d(service, episode_id: str) -> dict:
    overview = service.overview(episode_id)
    existing = next(
        (route for route in overview["routes"] if route.get("replacement_task_id") == "T122"),
        None,
    )
    if existing:
        return {"ok": True, "duplicate": True, "route_switch": existing}
    return expect(
        service.switch_route(
            episode_id,
            "T022",
            "T122",
            actor="human-observer",
            strategy="temporary-3d-insert",
            reason=(
                "用户临时要求 S04 不再只用 Manim；改为插入一段模拟 3D 建模镜头。"
            ),
            replacement_spec={
                "title": "模拟制作 S04 3D 插段源与时间轴",
                "goal": "创建一行 3D 占位源说明和最小 timeline；不建模、不渲染。",
                "references": [],
                "required_artifact_roles": ["source", "timeline"],
                "dependencies": ["T001"],
                "priority": 220,
                "unlock_value": 18,
                "critical_path": True,
                "tags": ["3d", "late_change", "placeholder_only"],
                "allowed_side_effects": ["write:out"],
                "stop_conditions": ["wall_clock_cutoff", "contradictory_requirements"],
            },
            request_id="chaos-switch-to-3d",
        ),
        "switch Manim to 3D",
    )


def switch_to_aroll(service, episode_id: str) -> dict:
    overview = service.overview(episode_id)
    existing = next(
        (route for route in overview["routes"] if route.get("replacement_task_id") == "T132"),
        None,
    )
    if existing:
        return {"ok": True, "duplicate": True, "route_switch": existing}
    return expect(
        service.switch_route(
            episode_id,
            "T122",
            "T132",
            actor="human-observer",
            strategy="a-roll-mid-manim",
            reason=(
                "用户取消尚未交付的 3D 插段，改为在 Manim 中途接入 A-roll；"
                "3D 路线不再有效。"
            ),
            replacement_spec={
                "title": "模拟编排 S04 A-roll 插入源与时间轴",
                "goal": "创建一行 A-roll 插入占位源和最小 timeline；不剪辑、不渲染。",
                "references": [],
                "required_artifact_roles": ["source", "timeline"],
                "dependencies": ["T001"],
                "priority": 230,
                "unlock_value": 20,
                "critical_path": True,
                "tags": ["a_roll", "late_change", "placeholder_only"],
                "allowed_side_effects": ["write:out"],
                "stop_conditions": ["wall_clock_cutoff", "contradictory_requirements"],
            },
            request_id="chaos-switch-to-aroll",
        ),
        "switch 3D to A-roll",
    )


def add_override(service, episode_id: str, *, instruction: str, label: str, slot: str, request_id: str) -> dict:
    return expect(
        service.add_context_override(
            episode_id,
            "T132",
            actor="human-observer",
            instruction=instruction,
            label=label,
            scope="task",
            assembly_mode="append",
            context_slot=slot,
            delivery_policy="attention_boundary",
            precedence=700,
            request_id=request_id,
        ),
        label,
    )


def inject_contradictions(service, episode_id: str, repo: Path) -> dict:
    ensure_asset_inputs(repo)
    results = []
    results.append(
        add_override(
            service,
            episode_id,
            label="仍然有效的角色素材要求",
            slot="visual.asset.sprite.authorization",
            instruction=(
                "来源 incoming/sprite-request.md：S04 必须醒目使用 character-sprite.png；"
                "在 Human 明确撤回前该要求持续有效。"
            ),
            request_id="chaos-conflict-sprite-required",
        )
    )
    results.append(
        add_override(
            service,
            episode_id,
            label="仍然有效的许可证撤回",
            slot="visual.asset.sprite.authorization",
            instruction=(
                "来源 incoming/sprite-licence-revoked.md：character-sprite.png 许可证已撤回；"
                "不得使用、描摹、变形或制作衍生物。"
            ),
            request_id="chaos-conflict-sprite-forbidden",
        )
    )
    results.append(
        add_override(
            service,
            episode_id,
            label="精确 A-roll 插入要求",
            slot="timeline.duration.contract",
            instruction="A-roll 必须从 00:08.000 开始精确持续 6.000 秒。",
            request_id="chaos-conflict-aroll-six-seconds",
        )
    )
    results.append(
        add_override(
            service,
            episode_id,
            label="仍然有效的时间轴冻结",
            slot="timeline.duration.contract",
            instruction=(
                "来源 incoming/timeline-lock.md：当前时间轴无空隙；整集总时长、所有既有"
                "镜头起止时间和镜头时长均不可改变。"
            ),
            request_id="chaos-conflict-timeline-immutable",
        )
    )
    preview = expect(
        service.preview_context(episode_id, "T132", actor="harness-maintainer"),
        "preview contradictory context",
    )
    return {
        "ok": True,
        "override_ids": [item["context_override"]["override_id"] for item in results],
        "context_manifest": preview["preview"]["payload"]["context_manifest"],
        "capsule_hash": preview["preview"]["capsule_hash"],
    }


def status(service, episode_id: str) -> dict:
    overview = service.overview(episode_id)
    return {
        "ok": True,
        "cursor": overview["cursor"],
        "tasks": [
            {"task_id": item["task_id"], "status": item["status"]}
            for item in overview["tasks"]
        ],
        "routes": overview["routes"],
        "gaps": overview.get("gaps", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "action",
        choices=("hybrid-audio", "three-d", "a-roll", "contradictions", "all", "status"),
    )
    args = parser.parse_args()
    environment, service, repo = inject_pressure.load_environment(args.workspace)
    episode_id = str(environment["episode_id"])
    if args.action == "hybrid-audio":
        result = {
            "ok": True,
            "upload": inject_pressure.add_upload(service, episode_id, repo),
            "switch": inject_pressure.switch_back_half_route(service, episode_id),
        }
    elif args.action == "three-d":
        result = switch_to_3d(service, episode_id)
    elif args.action == "a-roll":
        result = switch_to_aroll(service, episode_id)
    elif args.action == "contradictions":
        result = inject_contradictions(service, episode_id, repo)
    elif args.action == "status":
        result = status(service, episode_id)
    else:
        result = {
            "ok": True,
            "hybrid_audio": {
                "upload": inject_pressure.add_upload(service, episode_id, repo),
                "switch": inject_pressure.switch_back_half_route(service, episode_id),
            },
            "three_d": switch_to_3d(service, episode_id),
            "a_roll": switch_to_aroll(service, episode_id),
            "contradictions": inject_contradictions(service, episode_id, repo),
        }
    inject_pressure.update_manifest(args.workspace, args.action, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
