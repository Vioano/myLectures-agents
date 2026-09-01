from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from supervision.service import SupervisionService
from supervision.store import DataRoot


SKILL_ROOT = Path(__file__).resolve().parents[3]
GAME_ROOT = SKILL_ROOT / "scripts" / "evaluation" / "simulation-game"


def load_script(name: str):
    path = GAME_ROOT / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"simulation_game_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load_script("prepare_round")
pressure = load_script("inject_pressure")
freeze = load_script("freeze_round")


class SimulationGamePreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.result = prepare.prepare_round(
            Path(self.temp.name),
            run_id="round",
            episode_id="SIM-GAME-TEST",
        )
        self.workspace = Path(self.result["workspace"])
        self.environment = json.loads(
            (self.workspace / "environment.json").read_text(encoding="utf-8")
        )
        self.repo = Path(self.environment["repo_root"])
        self.service = SupervisionService(
            DataRoot(Path(self.environment["data_root"])), self.repo
        )

    def approve_contract(self) -> None:
        contract = self.repo / "out" / "contract.md"
        contract.parent.mkdir(parents=True, exist_ok=True)
        contract.write_text("# Simulated contract\nAll-TTS initial plan.\n", encoding="utf-8")
        online = self.service.set_agent_presence(
            "SIM-GAME-TEST",
            "blind-operator",
            actor="simulation-planner",
            presence="online",
            request_id="test-online-blind-operator",
        )
        self.assertTrue(online["ok"], online)
        begun = self.service.begin(
            "SIM-GAME-TEST",
            "T001",
            actor="blind-operator",
            request_id="test-begin-contract",
        )
        self.assertTrue(begun["ok"], begun)
        self.assertTrue(
            self.service.submit(
                "SIM-GAME-TEST",
                "T001",
                actor="blind-operator",
                artifacts=[
                    {"role": "production_contract", "path": "out/contract.md"}
                ],
                request_id="test-submit-contract",
            )["ok"]
        )
        context = self.service.review_context(
            "SIM-GAME-TEST", "T001", actor="independent-reviewer"
        )
        self.assertTrue(context["ok"])
        self.assertTrue(
            self.service.review(
                "SIM-GAME-TEST",
                "T001",
                actor="independent-reviewer",
                verdict="pass",
                review_context_hash=context["review_context_hash"],
                request_id="test-review-contract",
            )["ok"]
        )

    def test_fresh_round_contains_only_original_all_tts_plan(self) -> None:
        overview = self.service.overview("SIM-GAME-TEST")
        tasks = {task["task_id"]: task for task in overview["tasks"]}
        self.assertEqual(set(tasks), {"T001", "T010", "T012", "T020", "T022", "T040", "T900"})
        self.assertEqual(overview["routes"], [])
        self.assertEqual(overview["changes"], [])
        self.assertNotIn("T111", tasks)
        self.assertNotIn("T112", tasks)
        self.assertIn(
            "tts-pronunciation-registry.md",
            {Path(item["path"]).name for item in tasks["T012"]["references"]},
        )
        next_action = self.service.next_action(
            "SIM-GAME-TEST", actor="blind-operator"
        )
        self.assertEqual(next_action["next"]["task"]["task_id"], "T001")
        mission = (self.workspace / "MISSION.md").read_text(encoding="utf-8")
        self.assertNotIn("human recording", mission.lower())
        self.assertNotIn("T112", mission)

    def test_late_pressure_adds_and_isolates_replacement_route(self) -> None:
        self.approve_contract()
        uploaded = pressure.add_upload(
            self.service, "SIM-GAME-TEST", self.repo
        )
        self.assertTrue(uploaded["ok"])
        switched = pressure.switch_back_half_route(
            self.service, "SIM-GAME-TEST"
        )
        self.assertTrue(switched["ok"])
        denial = pressure.duplicate_work_probe(
            self.service, "SIM-GAME-TEST"
        )
        self.assertFalse(denial["ok"])
        self.assertEqual(denial["code"], "duplicate_work_obligation")

        overview = self.service.overview("SIM-GAME-TEST")
        tasks = {task["task_id"]: task for task in overview["tasks"]}
        self.assertEqual(tasks["T012"]["status"], "superseded")
        self.assertEqual(tasks["T112"]["status"], "planned")
        self.assertIn("T112", tasks["T040"]["dependencies"])
        self.assertNotIn("T012", tasks["T040"]["dependencies"])
        self.assertEqual(tasks["T010"]["status"], "planned")
        self.assertEqual(tasks["T020"]["status"], "planned")
        self.assertEqual(tasks["T022"]["status"], "planned")
        self.assertNotIn("T113", tasks)

        preview = self.service.preview_context(
            "SIM-GAME-TEST", "T112", actor="blind-operator"
        )
        self.assertTrue(preview["ok"])
        manifest_text = json.dumps(preview, ensure_ascii=False)
        self.assertIn("late-human-recording-request.md", manifest_text)
        self.assertNotIn("tts-pronunciation-registry.md", manifest_text)
        self.assertIn(uploaded["artifact_ids"][0], manifest_text)

    def test_round_freeze_emits_hash_manifest_and_truthful_pending_checks(self) -> None:
        run_root = Path(self.temp.name) / "round"
        bundle_dir = Path(self.temp.name) / "frozen-bundle"
        result = freeze.freeze_round(run_root, bundle_dir=bundle_dir)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "pending")
        evidence = json.loads(
            (run_root / "VERIFICATION_EVIDENCE.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(evidence["episode_id"], "SIM-GAME-TEST")
        self.assertTrue(evidence["state_root_hash"])
        self.assertTrue(evidence["evidence_manifest_hash"])
        self.assertIsNone(evidence["approved_agent_report"])
        checks = {item["check_id"]: item for item in evidence["checks"]}
        self.assertEqual(checks["event_store_integrity"]["status"], "pass")
        self.assertEqual(
            checks["blackbox_agent_report_approved"]["status"], "pending"
        )
        self.assertTrue((run_root / "RETROSPECTIVE.md").is_file())
        retrospective = (run_root / "RETROSPECTIVE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## What the game exposed", retrospective)
        self.assertIn("## Fixes applied during the round", retrospective)
        frozen_run = json.loads(
            (run_root / "run-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(frozen_run["status"], "frozen_pending")
        self.assertTrue(frozen_run["final_cursor"])
        reused = freeze.freeze_round(
            run_root, bundle_dir=bundle_dir, reuse_existing=True
        )
        self.assertTrue(reused["export"]["reused"])


if __name__ == "__main__":
    unittest.main()
