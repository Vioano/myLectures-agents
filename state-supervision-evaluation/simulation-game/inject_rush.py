#!/usr/bin/env python3
"""Inject a serial storyboard backlog, then apply an approved parallel rush plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import inject_pressure


VALIDATOR = ["validators/artifact-integrity/manifest.json"]


def expect(result: dict, label: str) -> dict:
    if not result.get("ok"):
        raise RuntimeError(f"{label} failed: {result}")
    return result


def task_ids(service, episode_id: str) -> set[str]:
    return {item["task_id"] for item in service.overview(episode_id)["tasks"]}


def add_task(
    service,
    episode_id: str,
    *,
    task_id: str,
    title: str,
    goal: str,
    work_key: str,
    roles: list[str],
    dependencies: list[str],
    priority: int,
    kind: str = "production",
    role: str = "author",
    deliverable_id: str = "D-VISUAL-BACK",
) -> dict:
    if task_id in task_ids(service, episode_id):
        return {"ok": True, "duplicate": True, "task_id": task_id}
    return expect(
        service.add_task(
            episode_id,
            task_id=task_id,
            title=title,
            goal=goal,
            wave_id="W1",
            scene_id="S20",
            content_unit_id="U-BACK-B01",
            deliverable_id=deliverable_id,
            work_key=work_key,
            kind=kind,
            role=role,
            dependencies=dependencies,
            references=[],
            required_artifact_roles=roles,
            critical_path=True,
            unlock_value=30,
            priority=priority,
            tags=["deadline_rush", "simulation", "serial_backlog"],
            allowed_side_effects=["write:out"],
            stop_conditions=["wall_clock_cutoff", "contradictory_requirements"],
            validators=VALIDATOR,
            actor="simulation-planner",
            request_id=f"rush-add-{task_id}",
        ),
        f"add {task_id}",
    )


def seed_serial(service, episode_id: str, workspace: Path) -> dict:
    results = []
    previous = "T001"
    for offset, scene_number in enumerate(range(6, 10)):
        task_id = f"T20{offset}"
        results.append(
            add_task(
                service,
                episode_id,
                task_id=task_id,
                title=f"串行积压 S{scene_number:02d} 分镜占位",
                goal=(
                    f"为 S{scene_number:02d} 创建一行分镜占位源和最小正时长 timeline；"
                    "不渲染。"
                ),
                work_key=f"rush:S{scene_number:02d}:storyboard",
                roles=["source", "timeline"],
                dependencies=[previous],
                priority=180 - offset,
            )
        )
        previous = task_id
    results.append(
        add_task(
            service,
            episode_id,
            task_id="T240",
            title="串行积压分镜汇合占位",
            goal="汇总 S06-S09 串行分镜占位证据，生成一行集成清单。",
            work_key="rush:serial:merge",
            roles=["integration"],
            dependencies=["T203"],
            priority=175,
            deliverable_id="D-INTEGRATION",
        )
    )
    results.append(
        add_task(
            service,
            episode_id,
            task_id="T190",
            title="响应突发截止压力并制定赶工调度",
            goal=(
                "用户只说时间不够了并要求把积压串行分镜改成并行。读取当前公开状态，"
                "判断需要多少并行 author Agent、哪些依赖应保留或替换、何处重新汇合；"
                "提交结构化 dispatch_plan，不直接制作分镜。"
            ),
            work_key="rush:deadline:dispatch-plan",
            roles=["dispatch_plan"],
            dependencies=["T001"],
            priority=500,
            kind="coordination",
            role="coordinator",
            deliverable_id="D-EVALUATION",
        )
    )
    expect(
        service.add_context_override(
            episode_id,
            "T190",
            actor="human-observer",
            instruction=(
                "用户突发要求原文：‘时间不够了。需要把积压的串行分镜全部改成并行，"
                "快速完成。’不要预设 author 数量；根据公开积压和汇合关系自行判断。"
            ),
            label="突发截止压力",
            scope="task",
            assembly_mode="append",
            context_slot="production.deadline.rush",
            delivery_policy="attention_boundary",
            precedence=900,
            request_id="rush-deadline-context",
        ),
        "add deadline pressure context",
    )
    registration = service.register_agent(
        episode_id,
        agent_id="rush-coordinator",
        actor="simulation-planner",
        role="coordinator",
        capabilities=["coordination", "dispatch_plan"],
        model="black-box-simulation",
        presence="planned",
        request_id="rush-register-coordinator",
    )
    if not registration.get("ok") and registration.get("code") != "agent_exists":
        raise RuntimeError(f"register rush coordinator failed: {registration}")
    mission_path = workspace / "RUSH_COORDINATOR_MISSION.md"
    mission_path.write_text(
        """# Isolated rush-coordinator mission

You are `rush-coordinator`. Use only the public Operator wrapper and the files
explicitly referenced by your signed task capsule. Do not read implementation,
tests, database files, hidden scripts, old reports, or another Agent's output.

Start with `next --role coordinator`, follow structured `allowed_next`, and do
not make Human decisions. The user's deadline message does not specify an Agent
count: infer a minimal safe author count from the visible serial backlog and
merge dependency. Submit one JSON `dispatch_plan` artifact for independent
review. It must distinguish work that can run in parallel from the final merge.
""",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "tasks": [item.get("task_id") or item.get("task", {}).get("task_id") for item in results],
        "coordinator": "rush-coordinator",
        "mission": str(mission_path),
    }


def replacement_spec(scene_number: int) -> dict:
    return {
        "title": f"并行赶工 S{scene_number:02d} 分镜占位",
        "goal": (
            f"并行创建 S{scene_number:02d} 一行分镜占位源和最小正时长 timeline；"
            "不渲染。"
        ),
        "references": [],
        "required_artifact_roles": ["source", "timeline"],
        "dependencies": ["T001"],
        "priority": 320,
        "unlock_value": 40,
        "critical_path": True,
        "tags": ["deadline_rush", "parallel_storyboard", f"scene:S{scene_number:02d}"],
        "allowed_side_effects": ["write:out"],
        "stop_conditions": ["wall_clock_cutoff", "contradictory_requirements"],
        "validators": VALIDATOR,
    }


def apply_parallel_plan(service, episode_id: str) -> dict:
    results = []
    task_state = {
        item["task_id"]: item for item in service.overview(episode_id)["tasks"]
    }
    preserve_t200 = task_state.get("T200", {}).get("status") in {
        "candidate",
        "user_review_pending",
        "approved",
        "rework",
    }
    for offset, scene_number in enumerate(range(6, 10)):
        replaced = f"T20{offset}"
        replacement = f"T21{offset}"
        if replaced == "T200" and preserve_t200:
            results.append(
                {
                    "ok": True,
                    "preserved": True,
                    "task_id": "T200",
                    "status": task_state["T200"]["status"],
                    "reason": "S06 already has evidence; deadline replan must not discard it.",
                }
            )
            continue
        existing = next(
            (
                route
                for route in service.overview(episode_id)["routes"]
                if route.get("replacement_task_id") == replacement
            ),
            None,
        )
        if existing:
            results.append({"ok": True, "duplicate": True, "route_switch": existing})
            continue
        results.append(
            expect(
                service.switch_route(
                    episode_id,
                    replaced,
                    replacement,
                    actor="harness-maintainer",
                    strategy="deadline-parallel-storyboards",
                    reason=(
                        "用户要求解除串行瓶颈；尚未开始的分镜改为独立并行 author 任务，"
                        "已完成证据不丢弃。"
                    ),
                    replacement_spec=replacement_spec(scene_number),
                    request_id=f"rush-parallelize-{replaced}",
                ),
                f"parallelize {replaced}",
            )
        )
    overview = service.overview(episode_id)
    merge_route = next(
        (route for route in overview["routes"] if route.get("replacement_task_id") == "T241"),
        None,
    )
    if merge_route:
        results.append({"ok": True, "duplicate": True, "route_switch": merge_route})
    else:
        results.append(
            expect(
                service.switch_route(
                    episode_id,
                    "T240",
                    "T241",
                    actor="harness-maintainer",
                    strategy="deadline-parallel-merge",
                    reason="四个并行分镜必须全部提交后再重新汇合，不能把并行误解成省略汇合门。",
                    replacement_spec={
                        "title": "并行赶工分镜汇合占位",
                        "goal": "汇总四个并行 S06-S09 分镜占位证据，生成一行集成清单。",
                        "references": [],
                        "required_artifact_roles": ["integration"],
                        "dependencies": [
                            "T200" if preserve_t200 else "T210",
                            "T211",
                            "T212",
                            "T213",
                        ],
                        "priority": 315,
                        "unlock_value": 45,
                        "critical_path": True,
                        "tags": ["deadline_rush", "parallel_merge"],
                        "allowed_side_effects": ["write:out"],
                        "stop_conditions": ["wall_clock_cutoff"],
                        "validators": VALIDATOR,
                    },
                    request_id="rush-parallelize-merge",
                ),
                "replace serial merge",
            )
        )
    return {
        "ok": True,
        "switches": results,
        "preserved_completed_work": ["T200"] if preserve_t200 else [],
    }


def scale_authors(service, episode_id: str, count: int) -> dict:
    if count < 1 or count > 8:
        raise ValueError("author count must be between 1 and 8")
    results = []
    for index in range(1, count + 1):
        agent_id = f"rush-author-{index}"
        result = service.register_agent(
            episode_id,
            agent_id=agent_id,
            actor="harness-maintainer",
            role="author",
            capabilities=["production", "source", "timeline", "integration"],
            model="black-box-simulation",
            presence="planned",
            request_id=f"rush-register-author-{index}",
        )
        if not result.get("ok") and result.get("code") != "agent_exists":
            raise RuntimeError(f"register {agent_id} failed: {result}")
        results.append({"agent_id": agent_id, "result": result})
    return {"ok": True, "author_count": count, "agents": results}


def seed_utilization_probe(service, episode_id: str) -> dict:
    """Release three useful, symmetric lanes at once to measure real utilization.

    The first rush batch exposed a dispatcher race: one already-running author
    drained every nominally parallel task before the newly registered pool could
    claim work.  These three small follow-up lanes make the staffing decision
    observable as concurrent leases instead of inferring throughput from graph
    shape alone.
    """

    results = []
    for index, scene_number in enumerate(range(7, 10), start=1):
        results.append(
            add_task(
                service,
                episode_id,
                task_id=f"T22{index}",
                title=f"扩容验证 S{scene_number:02d} 并行细化",
                goal=(
                    f"为 S{scene_number:02d} 独立创建一行 deadline 细化源和最小正时长 "
                    "timeline；这是扩容利用率探针，不渲染。"
                ),
                work_key=f"rush:utilization:S{scene_number:02d}",
                roles=["source", "timeline"],
                dependencies=["T001"],
                priority=340,
            )
        )
    results.append(
        add_task(
            service,
            episode_id,
            task_id="T249",
            title="扩容验证并行汇合",
            goal="汇总三个扩容验证分镜的证据，确认真实并发 lease 后生成一行清单。",
            work_key="rush:utilization:merge",
            roles=["integration"],
            dependencies=["T221", "T222", "T223"],
            priority=335,
            deliverable_id="D-INTEGRATION",
        )
    )
    return {
        "ok": True,
        "tasks": [
            item.get("task_id") or item.get("task", {}).get("task_id")
            for item in results
        ],
        "purpose": "verify that three added authors produce three concurrent leases",
    }


def status(service, episode_id: str) -> dict:
    overview = service.overview(episode_id)
    return {
        "ok": True,
        "cursor": overview["cursor"],
        "tasks": [
            {
                "task_id": item["task_id"],
                "role": item.get("role"),
                "status": item["status"],
                "dependencies": item.get("dependencies", []),
            }
            for item in overview["tasks"]
            if item["task_id"].startswith(("T19", "T20", "T21", "T22", "T24"))
        ],
        "routes": [
            item
            for item in overview["routes"]
            if str(item.get("strategy", "")).startswith("deadline-")
        ],
        "agents": [
            item
            for item in overview.get("agents", [])
            if str(item.get("agent_id", "")).startswith("rush-")
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "action",
        choices=(
            "seed-serial",
            "apply-parallel",
            "scale-authors",
            "seed-utilization",
            "status",
        ),
    )
    parser.add_argument("--count", type=int, default=4)
    args = parser.parse_args()
    environment, service, _ = inject_pressure.load_environment(args.workspace)
    episode_id = str(environment["episode_id"])
    if args.action == "seed-serial":
        result = seed_serial(service, episode_id, args.workspace.resolve())
    elif args.action == "apply-parallel":
        result = apply_parallel_plan(service, episode_id)
    elif args.action == "scale-authors":
        result = scale_authors(service, episode_id, args.count)
    elif args.action == "seed-utilization":
        result = seed_utilization_probe(service, episode_id)
    else:
        result = status(service, episode_id)
    inject_pressure.update_manifest(args.workspace, f"rush:{args.action}", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
