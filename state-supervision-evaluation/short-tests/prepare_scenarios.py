#!/usr/bin/env python3
"""Prepare isolated black-box fixtures without exposing their hidden oracle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_ROOT = PROJECT_ROOT / "state-supervision"
sys.path.insert(0, str(SYSTEM_ROOT))

from supervision.service import SupervisionService  # noqa: E402
from supervision.store import DataRoot  # noqa: E402


def expect(result: dict[str, Any], label: str) -> dict[str, Any]:
    if not result.get("ok"):
        raise RuntimeError(f"{label}: {result}")
    return result


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_workspace(root: Path, scenario: str, mission: str) -> tuple[Path, Path, SupervisionService]:
    workspace = root / scenario
    repo = workspace / "repo"
    state = workspace / "state"
    repo.mkdir(parents=True)
    write(workspace / "MISSION.md", mission.strip() + "\n")
    write(workspace / "transcript.jsonl", "")
    environment = {
        "schema": "state-supervision-blackbox-environment-v1",
        "scenario": scenario,
        "cli": str((SYSTEM_ROOT / "supervise.py").resolve()),
        "operator_cli": str((Path(__file__).parent / "operator_cli.py").resolve()),
        "operator_guide": str((SYSTEM_ROOT / "OPERATOR_GUIDE.md").resolve()),
        "repo_root": str(repo.resolve()),
        "data_root": str(state.resolve()),
    }
    write(workspace / "environment.json", json.dumps(environment, ensure_ascii=False, indent=2) + "\n")
    return workspace, repo, SupervisionService(DataRoot(state), repo)


def add_task(service: SupervisionService, episode: str, task_id: str, **overrides: Any) -> dict[str, Any]:
    spec = {
        "title": f"Task {task_id}",
        "goal": f"Produce exact evidence for {task_id}",
        "required_artifact_roles": ["result"],
    }
    spec.update(overrides)
    return expect(
        service.add_task(
            episode,
            task_id=task_id,
            actor="fixture-planner",
            request_id=f"fixture-add-{task_id}",
            **spec,
        ),
        f"add {task_id}",
    )


def approve(
    service: SupervisionService,
    episode: str,
    repo: Path,
    task_id: str,
    filename: str,
) -> dict[str, Any]:
    write(repo / filename, f"approved fixture for {task_id}\n")
    expect(
        service.begin(
            episode,
            task_id,
            actor=f"author-{task_id}",
            request_id=f"fixture-begin-{task_id}",
        ),
        f"begin {task_id}",
    )
    submitted = expect(
        service.submit(
            episode,
            task_id,
            actor=f"author-{task_id}",
            artifacts=[{"role": "result", "path": filename}],
            request_id=f"fixture-submit-{task_id}",
        ),
        f"submit {task_id}",
    )
    context = expect(
        service.review_context(
            episode,
            task_id,
            actor=f"reviewer-{task_id}",
        ),
        f"review context {task_id}",
    )
    expect(
        service.review(
            episode,
            task_id,
            actor=f"reviewer-{task_id}",
            verdict="pass",
            review_context_hash=context["review_context_hash"],
            request_id=f"fixture-review-{task_id}",
        ),
        f"review {task_id}",
    )
    return submitted


def create_validator(repo: Path) -> str:
    validator = repo / "validators" / "artifact-integrity"
    write(
        validator / "run.py",
        """#!/usr/bin/env python3
import hashlib, json, sys
from pathlib import Path
p = json.load(sys.stdin)
c = []
for a in p.get('artifacts', []):
    f = Path(a['absolute_path'])
    h = hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else None
    c.append({'artifact_id': a.get('artifact_id'), 'passed': h == a.get('sha256')})
s = 'pass' if c and all(x['passed'] for x in c) else 'fail'
json.dump({'status': s, 'summary': 'artifact bytes pinned', 'checks': c}, sys.stdout)
raise SystemExit(0 if s == 'pass' else 2)
""",
    )
    write(
        validator / "manifest.json",
        json.dumps(
            {
                "schema": "lecture-supervision-validator-v1",
                "validator_id": "artifact-integrity",
                "version": "1.0.0",
                "status": "active",
                "description": "Check submitted artifact bytes",
                "runner": {"command": ["python3", "run.py"], "timeout_seconds": 10},
            }
        ),
    )
    return "validators/artifact-integrity/manifest.json"


def scenario_focus_gate(root: Path) -> dict[str, Any]:
    mission = """
# Mission: complete one bounded task

Use only `state-supervision/OPERATOR_GUIDE.md`, this mission, and the public
operator CLI. Do not read system source, design documents, SQLite, hidden
fixtures, or another scenario's transcript.

Advance `T-TTS` in episode `EP-FOCUS` to `approved`. Start as actor
`fresh-author`; use actor `fresh-reviewer` only for the independent review.
Create the requested output inside this scenario's `repo/out/` directory. The
exact content and constraints must come from the context capsule, not a broad
repository search. At the end report command discoverability, context excess or
omissions, denial clarity, and any ambiguity or bug.
"""
    workspace, repo, service = make_workspace(root, "focus-gate", mission)
    write(repo / "references" / "tts-rule.md", "# Bound rule\nOutput exactly: 圆周率读作派；theta读作theta。\n")
    write(repo / "archive" / "irrelevant-history.md", "This unbound history should not enter the capsule.\n" * 100)
    validator = create_validator(repo)
    expect(service.create_episode(episode_id="EP-FOCUS", title="Focus capsule", mission="Complete one exact TTS artifact", actor="fixture-planner", request_id="fixture-create-focus"), "episode")
    add_task(
        service,
        "EP-FOCUS",
        "T-TTS",
        title="Create bounded TTS text",
        goal="Use the bound pronunciation rule and produce a reviewable TTS text file",
        references=[{"path": "references/tts-rule.md", "purpose": "Exact pronunciation and output contract"}],
        required_artifact_roles=["tts_script"],
        validators=[validator],
        critical_path=True,
    )
    return {"workspace": str(workspace), "episode": "EP-FOCUS", "oracle": "approved with one passing gate; capsule excludes archive/irrelevant-history.md"}


def scenario_lease(root: Path) -> dict[str, Any]:
    mission = """
# Mission: advance work without stealing ownership

Use only the public operator guide, this mission, and the operator CLI. Do not
read source, design documents, SQLite, or hidden oracle data.

Episode `EP-LEASE` contains concurrent work. As actor `fresh-operator`, safely
advance the best legal task without taking over another live owner's work.
Produce `repo/out/free.txt`, submit it, then use actor `fresh-reviewer` for the
independent review. Report whether `next` and any denial made ownership and the
legal recovery route obvious.
"""
    workspace, repo, service = make_workspace(root, "lease-routing", mission)
    expect(service.create_episode(episode_id="EP-LEASE", title="Lease routing", mission="Respect live ownership and advance independent work", actor="fixture-planner", request_id="fixture-create-lease"), "episode")
    add_task(service, "EP-LEASE", "T-LOCKED", title="Already owned critical task", critical_path=True, priority=100)
    add_task(service, "EP-LEASE", "T-FREE", title="Independent ready task", priority=10)
    expect(service.begin("EP-LEASE", "T-LOCKED", actor="existing-owner", request_id="fixture-lock-task"), "lock")
    return {"workspace": str(workspace), "episode": "EP-LEASE", "oracle": "T-FREE approved; T-LOCKED remains owned by existing-owner"}


def scenario_change(root: Path) -> dict[str, Any]:
    mission = """
# Mission: record a semantic upstream change

Use only the public operator guide, this mission, and the operator CLI. Do not
read source, design documents, SQLite, or hidden oracle data.

In episode `EP-CHANGE`, the user says the accepted mathematical premise from
`T-UP` must be replaced. As actor `human-feedback`, record that explicit change
through the public interface. Discover the exact target from state rather than
editing files or the database. Then report the resulting blast radius and
whether any unrelated sibling was damaged. Do not repair the affected tasks.
"""
    workspace, repo, service = make_workspace(root, "change-isolation", mission)
    expect(service.create_episode(episode_id="EP-CHANGE", title="Change isolation", mission="Invalidate only causal descendants", actor="fixture-planner", request_id="fixture-create-change"), "episode")
    add_task(service, "EP-CHANGE", "T-UP", title="Accepted premise")
    upstream = approve(service, "EP-CHANGE", repo, "T-UP", "artifacts/up.txt")
    add_task(service, "EP-CHANGE", "T-DOWN", title="Dependent animation", dependencies=["T-UP"])
    downstream = approve(service, "EP-CHANGE", repo, "T-DOWN", "artifacts/down.txt")
    add_task(service, "EP-CHANGE", "T-SIBLING", title="Independent audio")
    sibling = approve(service, "EP-CHANGE", repo, "T-SIBLING", "artifacts/sibling.txt")
    return {
        "workspace": str(workspace),
        "episode": "EP-CHANGE",
        "oracle": {
            "upstream_artifact": upstream["artifacts"][0]["artifact_id"],
            "downstream_artifact": downstream["artifacts"][0]["artifact_id"],
            "sibling_artifact": sibling["artifacts"][0]["artifact_id"],
            "states": {"T-UP": "rework", "T-DOWN": "blocked", "T-SIBLING": "approved"},
        },
    }


def scenario_recovery(root: Path) -> dict[str, Any]:
    mission = """
# Mission: recover an interrupted worker

Use only the public operator guide, this mission, and the operator CLI. Do not
read source, design documents, SQLite, or hidden oracle data.

Episode `EP-RECOVER` was left mid-task by a vanished worker. As actor
`recovery-operator`, inspect risk, preview recovery, apply only the safe local
repair, and show that the task can be assigned again. Do not modify SQLite or
delete evidence. Report the number of attempts and any unclear recovery step.
"""
    workspace, repo, service = make_workspace(root, "interrupted-recovery", mission)
    service.lease_seconds = -1
    expect(service.create_episode(episode_id="EP-RECOVER", title="Interrupted recovery", mission="Recover one expired local lease", actor="fixture-planner", request_id="fixture-create-recover"), "episode")
    add_task(service, "EP-RECOVER", "T-INTERRUPTED", title="Interrupted scene")
    expect(service.begin("EP-RECOVER", "T-INTERRUPTED", actor="vanished-worker", request_id="fixture-expired-lease"), "expired lease")
    return {"workspace": str(workspace), "episode": "EP-RECOVER", "oracle": "safe recovery returns task to rework and a new actor can begin generation 2"}


def scenario_determinism(root: Path) -> dict[str, Any]:
    mission = """
# Mission: read the deterministic route

Use only the public operator guide, this mission, and the operator CLI. Do not
read source, design documents, SQLite, hidden oracle data, or other operators'
transcripts.

For episode `EP-DETERMINISM`, call the minimum read-only operations needed to
name the single best next action and explain why it outranks the alternatives.
Do not mutate any state. Report the action, task ID, rank/reasons, cursor, and
any ambiguity.
"""
    workspace, repo, service = make_workspace(root, "deterministic-next", mission)
    expect(service.create_episode(episode_id="EP-DETERMINISM", title="Deterministic next", mission="Fresh operators should select the same route", actor="fixture-planner", request_id="fixture-create-determinism"), "episode")
    add_task(service, "EP-DETERMINISM", "T-B", title="High raw priority", priority=100)
    add_task(service, "EP-DETERMINISM", "T-A", title="Critical path unlock", critical_path=True, unlock_value=5, priority=1)
    add_task(service, "EP-DETERMINISM", "T-C", title="Dependent wait", dependencies=["T-A"], critical_path=True, unlock_value=20)
    return {"workspace": str(workspace), "episode": "EP-DETERMINISM", "oracle": {"action": "work", "task_id": "T-A"}}


def scenario_attention_return(root: Path) -> dict[str, Any]:
    mission = """
# Mission: handle review return without breaking attention

Use only the public operator guide, this mission, and the operator CLI. Do not
read source, design documents, SQLite, hidden oracle data, or other scenarios.

In episode `EP-RETURN`, actor `flow-author` is already working on `T-CURRENT`
when review feedback arrives for earlier task `T-RETURN`. First use `next` as
`flow-author` and verify that the current lease remains the action. Create and
submit `repo/out/current.txt`, then call `next` again. At that attention
boundary, discover the returned repair. As actor `flow-supervisor`, reroute its
return ticket to `repair-specialist` with a reason; as `repair-specialist`, use
`next` and `begin` to accept the repair. Do not complete the repair. Report
whether feedback was deferred, discoverable and reroutable without guessing or
interrupting active work.
"""
    workspace, repo, service = make_workspace(root, "attention-return", mission)
    expect(
        service.create_episode(
            episode_id="EP-RETURN",
            title="Attention-safe return",
            mission="Deliver review feedback only at a worker attention boundary",
            actor="fixture-planner",
            request_id="fixture-create-return",
        ),
        "episode",
    )
    add_task(service, "EP-RETURN", "T-RETURN", title="Earlier scene needing repair", priority=50)
    add_task(service, "EP-RETURN", "T-CURRENT", title="Current uninterrupted task", priority=40)
    add_task(service, "EP-RETURN", "T-NEW", title="Unrelated new work", priority=1)
    write(repo / "artifacts" / "return-draft.txt", "candidate that needs a bounded repair\n")
    expect(
        service.begin(
            "EP-RETURN",
            "T-RETURN",
            actor="flow-author",
            request_id="fixture-return-begin",
        ),
        "begin return source",
    )
    expect(
        service.submit(
            "EP-RETURN",
            "T-RETURN",
            actor="flow-author",
            artifacts=[{"role": "result", "path": "artifacts/return-draft.txt"}],
            request_id="fixture-return-submit",
        ),
        "submit return source",
    )
    expect(
        service.begin(
            "EP-RETURN",
            "T-CURRENT",
            actor="flow-author",
            request_id="fixture-current-begin",
        ),
        "begin current",
    )
    context = expect(
        service.review_context("EP-RETURN", "T-RETURN", actor="fixture-reviewer"),
        "return review context",
    )
    revised = expect(
        service.review(
            "EP-RETURN",
            "T-RETURN",
            actor="fixture-reviewer",
            verdict="revise",
            findings=[{"description": "Repair the timing handoff at the scene boundary."}],
            review_context_hash=context["review_context_hash"],
            request_id="fixture-return-review",
        ),
        "return review",
    )
    return {
        "workspace": str(workspace),
        "episode": "EP-RETURN",
        "oracle": {
            "busy_action": "continue:T-CURRENT",
            "boundary_action": "return_rework:T-RETURN",
            "ticket_id": revised["return_ticket"]["return_ticket_id"],
            "final_owner": "repair-specialist",
        },
    }


def scenario_route_switch(root: Path) -> dict[str, Any]:
    mission = """
# Mission: switch narration production from TTS to a supplied recording

Use only the public operator guide, this mission, and the operator CLI. Do not
read source, design documents, SQLite, hidden oracle data, or another scenario.

The user has replaced the TTS method in episode `EP-ROUTE` with the supplied
`repo/input/direct-recording.wav`. As `route-supervisor`, replace
`T-AUDIO-TTS` with new task `T-AUDIO-RECORDING` using strategy
`direct_recording`, reason `user supplied direct narration`, and
`input/replacement-spec.json`. The output deliverable must remain
`narration_audio`. Then as `recording-worker`, claim the replacement and submit
the supplied recording. Follow any structured hard-contract denial; do not
rename bytes, bypass a check, or ask a semantic reviewer to waive malformed
media. Use `recording-reviewer` only if a candidate legally reaches review.
Report the old lease state, downstream dependency, sibling state and route
status. Do not edit the database or weaken quality/user gates.
"""
    workspace, repo, service = make_workspace(root, "route-switch", mission)
    write(repo / "input" / "direct-recording.wav", "fixture direct recording bytes\n")
    write(
        repo / "input" / "replacement-spec.json",
        json.dumps(
            {
                "title": "Validate supplied narration recording",
                "goal": "Expose the user recording through the existing narration_audio slot",
                "references": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    expect(
        service.create_episode(
            episode_id="EP-ROUTE",
            title="Narration route switch",
            mission="Replace a production method behind a stable deliverable",
            actor="fixture-planner",
            request_id="fixture-create-route",
        ),
        "episode",
    )
    add_task(
        service,
        "EP-ROUTE",
        "T-AUDIO-TTS",
        title="Generate narration with TTS",
        required_artifact_roles=["narration_audio"],
        critical_path=True,
    )
    add_task(
        service,
        "EP-ROUTE",
        "T-EDIT",
        title="Integrate approved narration",
        dependencies=["T-AUDIO-TTS"],
    )
    add_task(service, "EP-ROUTE", "T-SIBLING", title="Independent visual scene")
    expect(
        service.begin(
            "EP-ROUTE",
            "T-AUDIO-TTS",
            actor="tts-worker",
            request_id="fixture-route-live-tts",
        ),
        "live TTS lease",
    )
    return {
        "workspace": str(workspace),
        "episode": "EP-ROUTE",
        "oracle": {
            "old_task": "superseded",
            "old_lease": "revoked",
            "replacement": "working or explicitly blocked after decodability denial",
            "downstream_dependencies": ["T-AUDIO-RECORDING"],
            "sibling": "planned",
            "route": "active, never fulfilled by malformed audio",
        },
    }


def scenario_reference_rebind(root: Path) -> dict[str, Any]:
    mission = """
# Mission: recover from a reviewed reference revision

Use only the public operator guide, this mission, and the operator CLI. Do not
read source, design documents, SQLite, hidden oracle data, or broad repository
history.

Advance `T-REFRESH` in episode `EP-REFERENCE` to approved. Start as
`reference-author` and follow the structured denial caused by a changed bound
reference. Adopt the current `references/rule.md` only through the legal
auditable command with reason `reviewed current pronunciation rule`. Then begin
again, use only the fresh capsule to create `repo/out/refreshed.txt`, submit it,
and use `reference-reviewer` for independent review. Report whether every
allowed recovery verb was executable and whether the fresh capsule carried the
new rule.
"""
    workspace, repo, service = make_workspace(root, "reference-rebind", mission)
    rule = repo / "references" / "rule.md"
    write(rule, "# Rule v1\nOutput exactly: old rule\n")
    expect(
        service.create_episode(
            episode_id="EP-REFERENCE",
            title="Reference drift recovery",
            mission="Fail closed then explicitly adopt reviewed guidance",
            actor="fixture-planner",
            request_id="fixture-create-reference",
        ),
        "episode",
    )
    added = add_task(
        service,
        "EP-REFERENCE",
        "T-REFRESH",
        title="Use the current pronunciation rule",
        references=[{"path": "references/rule.md", "purpose": "Exact output rule"}],
    )
    write(rule, "# Rule v2 reviewed\nOutput exactly: refreshed reference accepted\n")
    return {
        "workspace": str(workspace),
        "episode": "EP-REFERENCE",
        "oracle": {
            "reference_id": added["task"]["references"][0]["reference_id"],
            "final": "approved",
            "scope_revision": 2,
            "output": "refreshed reference accepted",
        },
    }


def scenario_multiscale_flow(root: Path) -> dict[str, Any]:
    mission = """
# Mission: advance visual work while audio is still active

Use only the public operator guide, this mission, and the operator CLI. Do not
read source, design documents, SQLite, hidden oracle data, or other transcripts.

Episode `EP-MULTISCALE` has content and deliverable hierarchies. Another worker
is actively producing audio. As `visual-worker`, use the public state to decide
whether visual task `T-VISUAL` is legally runnable; if it is, claim it, create
and submit `repo/out/visual.txt`, then use `visual-reviewer` to approve it.
Report the episode phase, the task's content × deliverable coordinate, and why
the audio container did or did not create a stage barrier. Do not invent a new
state hierarchy or add dependencies.
"""
    workspace, repo, service = make_workspace(root, "multiscale-flow", mission)
    expect(
        service.create_episode(
            episode_id="EP-MULTISCALE",
            title="Parallel multi-scale flow",
            mission="Keep containment separate from execution dependency",
            actor="fixture-planner",
            request_id="fixture-create-multiscale",
        ),
        "episode",
    )
    for unit_id, title, kind, parent, order in (
        ("U-EP", "Episode", "episode", None, 0),
        ("U-S01", "Scene S01", "scene", "U-EP", 0),
        ("U-B01", "Beat B01", "animation_beat", "U-S01", 0),
    ):
        expect(
            service.add_content_unit(
                "EP-MULTISCALE",
                unit_id=unit_id,
                title=title,
                kind=kind,
                parent_unit_id=parent,
                order=order,
                actor="fixture-planner",
                request_id=f"fixture-content-{unit_id}",
            ),
            unit_id,
        )
    for deliverable_id, title, order in (
        ("D-AUDIO", "Narration audio", 0),
        ("D-VISUAL", "Visual animation", 1),
        ("D-INTEGRATION", "Integration", 2),
    ):
        expect(
            service.add_deliverable(
                "EP-MULTISCALE",
                deliverable_id=deliverable_id,
                title=title,
                order=order,
                actor="fixture-planner",
                request_id=f"fixture-deliverable-{deliverable_id}",
            ),
            deliverable_id,
        )
    add_task(
        service,
        "EP-MULTISCALE",
        "T-AUDIO",
        title="Produce narration audio",
        content_unit_id="U-S01",
        deliverable_id="D-AUDIO",
        priority=30,
    )
    add_task(
        service,
        "EP-MULTISCALE",
        "T-VISUAL",
        title="Produce beat visual",
        content_unit_id="U-B01",
        deliverable_id="D-VISUAL",
        priority=20,
    )
    add_task(
        service,
        "EP-MULTISCALE",
        "T-INTEGRATE",
        title="Integrate audio and visual",
        content_unit_id="U-EP",
        deliverable_id="D-INTEGRATION",
        dependencies=["T-AUDIO", "T-VISUAL"],
    )
    expect(
        service.begin(
            "EP-MULTISCALE",
            "T-AUDIO",
            actor="audio-worker",
            request_id="fixture-audio-active",
        ),
        "active audio",
    )
    return {
        "workspace": str(workspace),
        "episode": "EP-MULTISCALE",
        "oracle": {
            "visual": "approved",
            "audio": "working",
            "coordinate": ["U-B01", "D-VISUAL"],
            "integration": "waiting",
            "episode_phase": "producing",
        },
    }


SCENARIOS = (
    scenario_focus_gate,
    scenario_lease,
    scenario_change,
    scenario_recovery,
    scenario_determinism,
    scenario_attention_return,
    scenario_route_switch,
    scenario_reference_rebind,
    scenario_multiscale_flow,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--oracle-output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)
    prepared = [factory(output) for factory in SCENARIOS]
    args.oracle_output.parent.mkdir(parents=True, exist_ok=True)
    args.oracle_output.write_text(
        json.dumps({"schema": "state-supervision-blackbox-oracle-v1", "scenarios": prepared}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "workspaces": [item["workspace"] for item in prepared],
                "oracle": str(args.oracle_output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
