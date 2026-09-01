from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json

from .helpers import ServiceCase


class ConcurrencyRecoveryTests(ServiceCase):
    def test_concurrent_begin_has_exactly_one_winner(self):
        self.add_task("T-Q")

        def begin(actor: str):
            return self.service.begin("EP", "T-Q", actor=actor, request_id=f"race-{actor}")

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(begin, ("Ada", "Bo")))
        winners = [result for result in results if result["ok"]]
        losers = [result for result in results if not result["ok"]]
        self.assertEqual(len(winners), 1, results)
        self.assertEqual(len(losers), 1, results)
        self.assertEqual(losers[0]["code"], "lease_conflict")
        lease, _ = self.data_root.episode_store("EP").get("lease", "lease:T-Q")
        self.assertEqual(lease["status"], "active")
        self.assertEqual(lease["owner"], winners[0]["lease"]["owner"])

    def test_restart_replay_is_semantically_stable(self):
        self.add_task("T-R")
        self.assertTrue(self.service.begin("EP", "T-R", actor="Ada", request_id="restart-begin")["ok"])
        before_next = self.service.next_action("EP", actor="Ada")
        before_explain = self.service.explain("EP", "T-R")
        from supervision.service import SupervisionService

        restarted = SupervisionService(
            self.data_root,
            self.repo,
            clock=self.clock,
            lease_seconds=60,
        )
        after_next = restarted.next_action("EP", actor="Ada")
        after_explain = restarted.explain("EP", "T-R")
        self.assertEqual(before_next, after_next)
        self.assertEqual(before_explain, after_explain)
        self.assertTrue(self.data_root.episode_store("EP").verify_integrity()["ok"])

    def test_projection_drift_rebuild_preserves_event_prefix(self):
        self.add_task("T-P")
        store = self.data_root.episode_store("EP")
        cursor = store.cursor()
        connection = store.connect()
        try:
            connection.execute("UPDATE aggregates SET state_hash='corrupt' WHERE aggregate_type='task' AND aggregate_id='T-P'")
            connection.commit()
        finally:
            connection.close()
        scan = self.service.scan("EP")
        self.assertTrue(any(item["kind"] == "projection_drift" for item in scan["anomalies"]))
        recovered = self.service.recover("EP", actor="supervisor", apply=True, request_id="projection-recover")
        self.assertTrue(recovered["ok"], recovered)
        self.assertTrue(store.verify_integrity()["ok"])
        self.assertGreaterEqual(store.cursor(), cursor)
        backup_dir = store.path.parent / "backups"
        self.assertTrue(any(backup_dir.glob("state-before-rebuild-*.db")))

    def test_missing_artifact_recovery_is_local(self):
        self.add_task("T-A")
        self.add_task("T-OTHER")
        self.approve_task("T-A")
        other_before, other_version = self.data_root.episode_store("EP").get("task", "T-OTHER")
        self.artifact.unlink()
        scan = self.service.scan("EP", deep=True)
        self.assertTrue(any(item["kind"] == "artifact_missing" for item in scan["anomalies"]))
        recovered = self.service.recover(
            "EP", actor="supervisor", apply=True, deep=True, request_id="artifact-recover"
        )
        self.assertTrue(recovered["ok"], recovered)
        task, _ = self.data_root.episode_store("EP").get("task", "T-A")
        self.assertEqual(task["status"], "blocked")
        other_after, other_version_after = self.data_root.episode_store("EP").get("task", "T-OTHER")
        self.assertEqual(other_before, other_after)
        self.assertEqual(other_version, other_version_after)

    def test_historical_artifact_drift_is_audit_only(self):
        self.add_task("T-HISTORY")
        approved = self.approve_task("T-HISTORY")
        artifact_id = approved["task"]["approved_artifact_ids"][0]
        changed = self.service.change(
            "EP",
            actor="human",
            target_id=artifact_id,
            reason="Replace the accepted historical result.",
            request_id="history-change",
        )
        self.assertTrue(changed["ok"], changed)
        self.artifact.write_bytes(b"new-working-bytes")

        scan = self.service.scan("EP", deep=True)
        finding = next(
            item
            for item in scan["anomalies"]
            if item["subject_id"] == artifact_id
        )
        self.assertEqual(finding["kind"], "historical_artifact_hash_drift")
        self.assertFalse(finding["repairable"])
        self.assertEqual(finding["facts"]["lineage"], "historical")
        task, _ = self.data_root.episode_store("EP").get("task", "T-HISTORY")
        self.assertEqual(task["status"], "rework")

    def test_current_artifact_failure_recovery_is_idempotent(self):
        self.add_task("T-CURRENT")
        self.approve_task("T-CURRENT")
        self.artifact.write_bytes(b"drifted-current-bytes")

        first = self.service.recover(
            "EP",
            actor="supervisor",
            apply=True,
            deep=True,
            request_id="current-drift-first",
        )
        self.assertTrue(first["ok"], first)
        task, _ = self.data_root.episode_store("EP").get("task", "T-CURRENT")
        self.assertEqual(task["status"], "blocked")
        self.assertEqual(len(task["blockers"]), 1)

        scan = self.service.scan("EP", deep=True)
        self.assertTrue(
            any(
                item["kind"] == "artifact_hash_drift_recorded"
                and not item["repairable"]
                for item in scan["anomalies"]
            ),
            scan,
        )
        second = self.service.recover(
            "EP",
            actor="supervisor",
            apply=True,
            deep=True,
            request_id="current-drift-second",
        )
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["status"], "no_safe_repairs")
        task, _ = self.data_root.episode_store("EP").get("task", "T-CURRENT")
        self.assertEqual(len(task["blockers"]), 1)

    def test_false_historical_artifact_block_restores_rework(self):
        self.add_task("T-FALSE-BLOCK")
        approved = self.approve_task("T-FALSE-BLOCK")
        artifact_id = approved["task"]["approved_artifact_ids"][0]
        changed = self.service.change(
            "EP",
            actor="human",
            target_id=artifact_id,
            reason="Make the accepted artifact historical.",
            request_id="false-block-change",
        )
        self.assertTrue(changed["ok"], changed)
        store = self.data_root.episode_store("EP")

        def inject_false_block(tx):
            task, version = tx.require("task", "T-FALSE-BLOCK")
            blocker = {
                "kind": "artifact_hash_drift",
                "artifact_id": artifact_id,
                "anomaly_id": "anomaly_old_history",
            }
            blocked = {
                **task,
                "status": "blocked",
                "blockers": [blocker, blocker],
            }
            tx.transition(
                "task",
                "T-FALSE-BLOCK",
                "LegacyFalseArtifactBlockInjected",
                {"fixture": True},
                blocked,
                expected_version=version,
            )
            return {"task": blocked}

        store.execute(
            request_id="inject-false-artifact-block",
            command_name="fixture.inject_false_artifact_block",
            actor="test",
            payload={"task_id": "T-FALSE-BLOCK"},
            handler=inject_false_block,
            occurred_at=self.clock(),
        )
        scan = self.service.scan("EP")
        self.assertTrue(
            any(
                item["kind"] == "historical_artifact_false_block"
                and item["repairable"]
                for item in scan["anomalies"]
            ),
            scan,
        )
        recovered = self.service.recover(
            "EP",
            actor="supervisor",
            apply=True,
            request_id="remove-false-artifact-block",
        )
        self.assertTrue(recovered["ok"], recovered)
        task, _ = store.get("task", "T-FALSE-BLOCK")
        self.assertEqual(task["status"], "rework")
        self.assertEqual(task["blockers"], [])
        repeated = self.service.recover(
            "EP",
            actor="supervisor",
            apply=True,
            request_id="remove-false-artifact-block-again",
        )
        self.assertTrue(repeated["ok"], repeated)
        self.assertEqual(repeated["status"], "no_safe_repairs")

    def test_attention_scan_is_a_successful_query_not_an_api_failure(self):
        self.add_task("T-SCAN")
        self.assertTrue(
            self.service.begin(
                "EP", "T-SCAN", actor="Ada", request_id="scan-begin"
            )["ok"]
        )
        self.clock.advance(61)
        scan = self.service.scan("EP")
        self.assertTrue(scan["ok"])
        self.assertFalse(scan["clean"])
        self.assertEqual(scan["status"], "attention")
        self.assertTrue(any(item["kind"] == "expired_lease" for item in scan["anomalies"]))

    def test_recovery_releases_legacy_blocked_descendant_after_upstream_reapproval(self):
        self.add_task("T-UPSTREAM")
        upstream = self.approve_task("T-UPSTREAM")
        self.add_task("T-DESCENDANT", dependencies=["T-UPSTREAM"])
        self.approve_task("T-DESCENDANT")
        changed = self.service.change(
            "EP",
            actor="human",
            target_id=upstream["task"]["approved_artifact_ids"][0],
            reason="Revise upstream evidence.",
            request_id="legacy-release-change",
        )
        self.artifact.write_bytes(b"reapproved-for-recovery")
        self.assertTrue(
            self.service.begin(
                "EP",
                "T-UPSTREAM",
                actor="Ada",
                request_id="legacy-release-begin",
            )["ok"]
        )
        self.assertTrue(
            self.service.submit(
                "EP",
                "T-UPSTREAM",
                actor="Ada",
                artifacts=[{"role": "result", "path": "result.bin"}],
                request_id="legacy-release-submit",
            )["ok"]
        )
        context = self.service.review_context("EP", "T-UPSTREAM", actor="Bo")
        self.assertTrue(
            self.service.review(
                "EP",
                "T-UPSTREAM",
                actor="Bo",
                verdict="pass",
                review_context_hash=context["review_context_hash"],
                request_id="legacy-release-review",
            )["ok"]
        )

        store = self.data_root.episode_store("EP")

        def inject_legacy_projection(tx):
            task, version = tx.require("task", "T-DESCENDANT")
            legacy_state = {
                **task,
                "status": "blocked",
                "blockers": [
                    {
                        "kind": "upstream_change",
                        "change_id": changed["change"]["change_id"],
                        "upstream_task_id": "T-UPSTREAM",
                    }
                ],
                "upstream_reapproval_receipts": [],
            }
            tx.transition(
                "task",
                "T-DESCENDANT",
                "LegacyBlockedProjectionInjected",
                {"fixture": True},
                legacy_state,
                expected_version=version,
            )
            return {"task": legacy_state}

        store.execute(
            request_id="inject-legacy-blocked-descendant",
            command_name="fixture.inject_legacy_projection",
            actor="test",
            payload={"task_id": "T-DESCENDANT"},
            handler=inject_legacy_projection,
            occurred_at=self.clock(),
        )
        scan = self.service.scan("EP")
        self.assertTrue(
            any(
                item["kind"] == "resolved_upstream_invalidation"
                and item["subject_id"] == "T-DESCENDANT"
                for item in scan["anomalies"]
            )
        )
        recovered = self.service.recover(
            "EP",
            actor="supervisor",
            apply=True,
            request_id="legacy-upstream-release-recover",
        )
        self.assertTrue(recovered["ok"], recovered)
        descendant, _ = store.get("task", "T-DESCENDANT")
        self.assertEqual(descendant["status"], "rework")
        self.assertEqual(descendant["blockers"], [])
        self.assertEqual(
            descendant["upstream_reapproval_receipts"][-1][
                "upstream_task_id"
            ],
            "T-UPSTREAM",
        )

    def test_frozen_export_is_reproducible_for_unchanged_state(self):
        self.add_task("T-E")
        first = self.service.export("EP", self.root / "export-one")
        second = self.service.export("EP", self.root / "export-two")
        self.assertTrue(first["ok"], first)
        self.assertTrue(second["ok"], second)
        self.assertEqual(first["manifest"]["manifest_hash"], second["manifest"]["manifest_hash"])
        self.assertEqual(first["manifest"]["state_root_hash"], second["manifest"]["state_root_hash"])

    def test_frozen_export_derives_episode13_flow_attention_and_quality_metrics(self):
        self.add_task("T-METRICS")
        self.clock.advance(5)
        begun = self.service.begin(
            "EP", "T-METRICS", actor="Ada", request_id="metrics-begin"
        )
        self.assertTrue(begun["ok"], begun)
        self.clock.advance(3)
        noted = self.service.annotate(
            "EP",
            actor="human-ui",
            target_id="T-METRICS",
            body="Preserve this exact Human correction in the next capsule.",
            request_id="metrics-annotation",
        )
        self.assertTrue(noted["ok"], noted)
        self.clock.advance(2)
        heartbeat = self.service.heartbeat(
            "EP",
            "T-METRICS",
            actor="Ada",
            usage_delta={"input_tokens": 10, "output_tokens": 5, "reasoning_tokens": 2},
            request_id="metrics-heartbeat",
        )
        self.assertTrue(heartbeat["ok"], heartbeat)
        self.assertIsNotNone(heartbeat.get("context_update"))
        self.clock.advance(4)
        submitted = self.service.submit(
            "EP",
            "T-METRICS",
            actor="Ada",
            artifacts=[{"role": "result", "path": "result.bin"}],
            request_id="metrics-submit",
        )
        self.assertTrue(submitted["ok"], submitted)
        context = self.service.review_context("EP", "T-METRICS", actor="Reviewer")
        reviewed = self.service.review(
            "EP",
            "T-METRICS",
            actor="Reviewer",
            verdict="pass",
            review_context_hash=context["review_context_hash"],
            request_id="metrics-review",
        )
        self.assertTrue(reviewed["ok"], reviewed)

        exported = self.service.export("EP", self.root / "metrics-export")
        self.assertTrue(exported["ok"], exported)
        metrics = exported["metrics"]
        lifecycle = metrics["time_and_flow"]["task_lifecycle"]["T-METRICS"]
        self.assertEqual(lifecycle["queue_wait_seconds"], 5.0)
        self.assertEqual(lifecycle["input_tokens"], 10)
        self.assertEqual(metrics["parallel_dispatch"]["max_concurrent_live_leases"], 1)
        self.assertEqual(metrics["human_activity"]["annotation_count"], 1)
        self.assertEqual(
            metrics["attention_delivery"]["annotation_delivery_latency_seconds_p50"],
            2.0,
        )
        self.assertEqual(metrics["attention_delivery"]["undelivered_annotation_ids_at_freeze"], [])
        self.assertEqual(metrics["quality_and_rework"]["first_review_pass_ratio"], 1.0)
        self.assertIn("human_active_review_minutes", metrics["unknown_metrics"])


if __name__ == "__main__":
    import unittest

    unittest.main()
