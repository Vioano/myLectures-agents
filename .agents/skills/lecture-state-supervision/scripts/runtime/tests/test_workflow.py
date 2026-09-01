from __future__ import annotations

import wave

from supervision.cli import agent_next_projection
from supervision.core import DomainError

from .helpers import ServiceCase


class WorkflowTests(ServiceCase):
    def test_oversized_reference_compiles_to_deterministic_brief(self):
        long_reference = self.repo / "long-guidance.md"
        long_reference.write_text(
            "# Production contract\n"
            "Opening constraint must remain visible.\n\n"
            "## Timing rules\n"
            + "Use evidence-bearing progress and preserve exact lineage.\n" * 1200
            + "\n## Review rules\nIndependent review remains mandatory.\n",
            encoding="utf-8",
        )
        self.add_task(
            "T-LONG-CONTEXT",
            references=[
                {
                    "path": "long-guidance.md",
                    "purpose": "Complete production and review rules",
                    "context_class": "stable_rule",
                    "mutable": False,
                }
            ],
        )

        preview = self.service.preview_context("EP", "T-LONG-CONTEXT")
        self.assertTrue(preview["ok"], preview)
        payload = preview["preview"]["payload"]
        reference = payload["required_references"][0]
        self.assertEqual(reference["content_mode"], "brief")
        self.assertEqual(reference["retrieval_policy"], "read_original_on_demand")
        self.assertGreater(reference["omitted_chars"], 0)
        self.assertIn("Production contract", reference["rough_summary"])
        self.assertIn("Opening constraint must remain visible", reference["content"])
        self.assertIn("原文件路径：long-guidance.md", reference["content"])
        self.assertLessEqual(payload["context_budget"]["used_chars"], payload["context_budget"]["max_chars"])
        block = next(item for item in payload["context_blocks"] if item["block_id"].startswith("reference:"))
        self.assertEqual(block["content_mode"], "brief")
        self.assertEqual(block["source"]["path"], "long-guidance.md")
        self.assertEqual(block["content"], reference["content"])

        begun = self.service.begin(
            "EP", "T-LONG-CONTEXT", actor="Ada", request_id="begin-long-context"
        )
        self.assertTrue(begun["ok"], begun)
        issued = begun["capsule"]["payload"]["required_references"][0]
        self.assertEqual(issued["content"], reference["content"])
        self.assertEqual(issued["sha256"], reference["sha256"])

    def test_many_oversized_references_cannot_starve_later_sources(self):
        references = []
        for index in range(12):
            path = self.repo / f"long-{index:02d}.md"
            path.write_text(
                f"# Rule set {index:02d}\nUnique opening marker {index:02d}.\n"
                + f"Constraint {index:02d} remains source-bound.\n" * 700,
                encoding="utf-8",
            )
            references.append({"path": path.name, "purpose": f"Rule set {index:02d}"})
        self.add_task("T-MANY-LONG-CONTEXT", references=references)

        preview = self.service.preview_context("EP", "T-MANY-LONG-CONTEXT")
        self.assertTrue(preview["ok"], preview)
        payload = preview["preview"]["payload"]
        compiled = payload["required_references"]
        self.assertEqual(len(compiled), len(references))
        self.assertTrue(all(item["content_mode"] == "brief" for item in compiled))
        self.assertTrue(all(item["content_chars"] > 0 for item in compiled))
        for index, item in enumerate(compiled):
            self.assertIn(f"原文件路径：long-{index:02d}.md", item["content"])
            self.assertIn(f"Unique opening marker {index:02d}", item["content"])
        self.assertLessEqual(payload["context_budget"]["used_chars"], payload["context_budget"]["max_chars"])

    def test_context_preview_is_exact_layered_and_read_only(self):
        self.add_task(
            "T-CONTEXT",
            references=[
                {
                    "path": "guidance.md",
                    "purpose": "IndexTTS2 pronunciation rules",
                    "context_class": "stable_rule",
                    "context_version": "indextts2-v7",
                    "context_slot": "tts.service.rules",
                    "service_binding": "IndexTTS2",
                    "mutable": False,
                }
            ],
        )
        store = self.data_root.episode_store("EP")
        before = store.cursor()
        preview = self.service.preview_context("EP", "T-CONTEXT")
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(store.cursor(), before)
        payload = preview["preview"]["payload"]
        self.assertEqual(payload["schema"], "lecture-task-capsule-v2")
        self.assertTrue(payload["context_manifest"]["preview"])
        self.assertEqual(payload["context_manifest"]["class_counts"]["stable_rule"], 1)
        self.assertIn("# Required guidance", payload["assembled_prompt"])
        stable = next(
            item
            for item in payload["context_blocks"]
            if item["context_class"] == "stable_rule"
        )
        self.assertEqual(stable["version"], "indextts2-v7")
        self.assertEqual(stable["source"]["service_binding"], "IndexTTS2")

    def test_context_override_can_replace_one_stable_slot_without_mutating_source(self):
        original = self.reference.read_text(encoding="utf-8")
        self.add_task(
            "T-REPLACE-CONTEXT",
            references=[
                {
                    "path": "guidance.md",
                    "purpose": "Stable pronunciation rules",
                    "context_class": "stable_rule",
                    "context_slot": "tts.service.rules",
                    "context_version": "v7",
                    "mutable": False,
                }
            ],
        )
        added = self.service.add_context_override(
            "EP",
            "T-REPLACE-CONTEXT",
            actor="human-ui",
            instruction="Use the episode-specific pronunciation rewrite.",
            assembly_mode="replace",
            context_slot="tts.service.rules",
            scope="task",
            delivery_policy="next_attempt",
            request_id="replace-tts-context",
        )
        self.assertTrue(added["ok"], added)
        preview = self.service.preview_context("EP", "T-REPLACE-CONTEXT")
        payload = preview["preview"]["payload"]
        active_slots = [item["slot"] for item in payload["context_blocks"]]
        self.assertEqual(active_slots.count("tts.service.rules"), 1)
        replacement = next(
            item
            for item in payload["context_blocks"]
            if item["slot"] == "tts.service.rules"
        )
        self.assertEqual(replacement["context_class"], "temporary_override")
        self.assertTrue(replacement["supersedes"])
        self.assertEqual(payload["context_manifest"]["conflict_count"], 0)
        self.assertEqual(self.reference.read_text(encoding="utf-8"), original)

    def test_attention_boundary_override_issues_new_capsule_on_heartbeat(self):
        self.add_task("T-HOT-CONTEXT")
        begun = self.service.begin(
            "EP", "T-HOT-CONTEXT", actor="Ada", request_id="hot-context-begin"
        )
        self.assertTrue(begun["ok"], begun)
        old_hash = begun["capsule"]["capsule_hash"]
        changed = self.service.add_context_override(
            "EP",
            "T-HOT-CONTEXT",
            actor="human-ui",
            instruction="Read theta in English for this task.",
            scope="task",
            delivery_policy="attention_boundary",
            request_id="hot-context-change",
        )
        self.assertTrue(changed["ok"], changed)
        self.assertEqual(changed["delivery"], "next_heartbeat")
        heartbeat = self.service.heartbeat(
            "EP",
            "T-HOT-CONTEXT",
            actor="Ada",
            request_id="hot-context-heartbeat",
        )
        self.assertTrue(heartbeat["ok"], heartbeat)
        self.assertIsNotNone(heartbeat["context_update"])
        self.assertNotEqual(heartbeat["context_update"]["capsule_hash"], old_hash)
        self.assertIn(
            "Read theta in English",
            heartbeat["context_update"]["payload"]["assembled_prompt"],
        )
        self.assertIsNone(heartbeat["task"].get("pending_context_update"))
        self.assertEqual(
            heartbeat["task"]["issued_context_revision"],
            heartbeat["task"]["context_revision"],
        )

    def test_structural_scene_conflict_blocks_before_lease_and_reaches_human(self):
        self.assertTrue(
            self.service.add_wave(
                "EP", wave_id="W1", title="Production", actor="planner"
            )["ok"]
        )
        self.assertTrue(
            self.service.add_scene(
                "EP",
                scene_id="S20",
                wave_id="W1",
                title="Back half",
                actor="planner",
            )["ok"]
        )
        created = self.add_task(
            "T-SCENE-CONFLICT",
            title="扩容验证 S09 并行细化",
            goal="为 S09 独立创建源文件与时间轴。",
            scene_id="S20",
            wave_id="W1",
            work_key="rush:utilization:S09",
        )
        self.assertEqual(created["task"]["status"], "blocked")
        self.assertEqual(len(created["gaps"]), 1)
        gap = created["gaps"][0]
        self.assertEqual(gap["kind"], "contradictory_requirements")
        self.assertTrue(gap["requires_human"])
        self.assertEqual(gap["confidence"], "high")
        self.assertEqual(
            {item["field"] for item in gap["sources"]},
            {"scene_id", "work_key", "title", "goal"},
        )

        preview = self.service.preview_context("EP", "T-SCENE-CONFLICT")
        self.assertTrue(preview["ok"], preview)
        manifest = preview["preview"]["payload"]["context_manifest"]
        self.assertEqual(manifest["conflict_count"], 1)
        self.assertEqual(manifest["conflicts"][0]["conflict_key"], gap["conflict_key"])

        denied = self.service.begin(
            "EP", "T-SCENE-CONFLICT", actor="Ada", request_id="conflict-begin-denied"
        )
        self.assertFalse(denied["ok"], denied)
        self.assertEqual(denied["code"], "task_blocked")
        overview = self.service.overview("EP")
        self.assertFalse(
            any(item.get("task_id") == "T-SCENE-CONFLICT" for item in overview["leases"])
        )

    def test_review_capsule_preserves_human_gap_resolution_and_retry_override(self):
        self.add_task("T-DECISION-HANDOFF")
        first = self.service.begin(
            "EP",
            "T-DECISION-HANDOFF",
            actor="Ada",
            request_id="decision-handoff-begin-1",
        )
        self.assertTrue(first["ok"], first)
        blocked = self.service.gap(
            "EP",
            "T-DECISION-HANDOFF",
            actor="Ada",
            kind="contradictory_requirements",
            reason="The task contract names both S09 and S20 as authoritative.",
            request_id="decision-handoff-gap",
        )
        self.assertTrue(blocked["ok"], blocked)
        gap_id = blocked["gap"]["gap_id"]
        resolved = self.service.resolve_gap(
            "EP",
            gap_id,
            actor="human-ui",
            resolution="Human decision: S09 is authoritative; S20 is invalid. Preserve this decision for review.",
            request_id="decision-handoff-resolve",
        )
        self.assertTrue(resolved["ok"], resolved)
        override = resolved["context_override"]
        self.assertEqual(override["source_gap_id"], gap_id)
        self.assertEqual(override["delivery_policy"], "next_attempt")
        second = self.service.begin(
            "EP",
            "T-DECISION-HANDOFF",
            actor="Ada",
            request_id="decision-handoff-begin-2",
        )
        self.assertTrue(second["ok"], second)
        self.assertIn(
            "Human decision: S09 is authoritative",
            second["capsule"]["payload"]["assembled_prompt"],
        )
        submitted = self.service.submit(
            "EP",
            "T-DECISION-HANDOFF",
            actor="Ada",
            artifacts=[{"role": "result", "path": "result.bin"}],
            request_id="decision-handoff-submit",
        )
        self.assertTrue(submitted["ok"], submitted)

        context = self.service.review_context(
            "EP", "T-DECISION-HANDOFF", actor="Bo"
        )
        self.assertTrue(context["ok"], context)
        capsule = context["capsule"]
        override_blocks = [
            item
            for item in capsule["context_blocks"]
            if item.get("source", {}).get("id")
            == override["override_id"]
        ]
        self.assertEqual(len(override_blocks), 1)
        self.assertEqual(
            capsule["resolved_gap_decisions"][0]["gap_id"], gap_id
        )
        self.assertEqual(
            capsule["resolved_gap_decisions"][0]["resolution"],
            "Human decision: S09 is authoritative; S20 is invalid. Preserve this decision for review.",
        )
        self.assertIn(
            "resolved_gap_decisions", capsule["why_now"]
        )
        reviewed = self.service.review(
            "EP",
            "T-DECISION-HANDOFF",
            actor="Bo",
            verdict="pass",
            review_context_hash=context["review_context_hash"],
            request_id="decision-handoff-review",
        )
        self.assertTrue(reviewed["ok"], reviewed)

    def test_agent_probe_distinguishes_planned_illegal_idle_and_fake_busy_risk(self):
        self.add_task("T-TTS", role="tts_editor", kind="tts_script")
        registered = self.service.register_agent(
            "EP",
            agent_id="Ada",
            actor="planner",
            role="author",
            capabilities=["tts_editor"],
            model="fixture",
            presence="planned",
            request_id="register-Ada",
        )
        self.assertTrue(registered["ok"], registered)
        self.assertEqual(self.service.agent_probe("EP", "Ada")["classification"], "planned")
        online = self.service.set_agent_presence(
            "EP",
            "Ada",
            actor="planner",
            presence="online",
            request_id="online-Ada",
        )
        self.assertTrue(online["ok"], online)
        idle = self.service.agent_probe("EP", "Ada")
        self.assertEqual(idle["classification"], "idle_illegal")
        self.assertFalse(idle["idle_legal"])
        self.assertEqual(idle["next"]["task"]["task_id"], "T-TTS")
        self.assertIn(
            "idle_illegal",
            {item["kind"] for item in self.service.scan("EP")["anomalies"]},
        )
        self.assertTrue(
            self.service.begin(
                "EP", "T-TTS", actor="Ada", request_id="Ada-begin-TTS"
            )["ok"]
        )
        self.assertEqual(
            self.service.agent_probe("EP", "Ada")["classification"],
            "working_productive",
        )
        heartbeat = self.service.heartbeat(
            "EP",
            "T-TTS",
            actor="Ada",
            usage_delta={"input_tokens": 40, "output_tokens": 10},
            request_id="Ada-empty-heartbeat",
        )
        self.assertTrue(heartbeat["ok"], heartbeat)
        risk = self.service.agent_probe("EP", "Ada")
        self.assertEqual(risk["classification"], "working_nonproductive_risk")
        self.assertIn("token_burn_without_progress", risk["reason_codes"])
        self.assertIn(
            "working_nonproductive_risk",
            {item["kind"] for item in self.service.scan("EP")["anomalies"]},
        )

    def test_agent_capabilities_limit_ready_work_without_self_scoring(self):
        self.add_task("T-AUDIO", role="tts_editor", kind="tts_script")
        self.service.register_agent(
            "EP",
            agent_id="VisualAgent",
            actor="planner",
            role="author",
            capabilities=["animation_author"],
            presence="online",
            request_id="register-visual",
        )
        probe = self.service.agent_probe("EP", "VisualAgent")
        self.assertEqual(probe["classification"], "idle_legal")
        self.assertIn("agent_capability_mismatch", probe["reason_codes"])

    def test_duplicate_semantic_work_is_rejected_even_with_a_new_task_id(self):
        self.add_task("T-ORIGINAL", work_key="scene:S01:animation")
        duplicate = self.service.add_task(
            "EP",
            task_id="T-LOOKS-BUSY",
            title="Repeat finished-looking work",
            goal="Redo the same obligation under a different id",
            actor="planner",
            work_key="scene:S01:animation",
            references=["guidance.md"],
            required_artifact_roles=["result"],
            request_id="add-duplicate-work",
        )
        self.assertFalse(duplicate["ok"])
        self.assertEqual(duplicate["code"], "duplicate_work_obligation")

    def test_repeated_evidence_hash_does_not_reset_no_progress_counter(self):
        self.add_task(
            "T-NOVELTY",
            budget={"max_no_progress_heartbeats": 3},
        )
        self.assertTrue(
            self.service.begin(
                "EP", "T-NOVELTY", actor="Ada", request_id="begin-novelty"
            )["ok"]
        )
        first = self.service.heartbeat(
            "EP",
            "T-NOVELTY",
            actor="Ada",
            evidence_refs=["file:result.bin"],
            request_id="novel-evidence-first",
        )
        self.assertTrue(first["meaningful_progress"])
        repeated = self.service.heartbeat(
            "EP",
            "T-NOVELTY",
            actor="Ada",
            evidence_refs=["file:result.bin"],
            usage_delta={"input_tokens": 100, "output_tokens": 25},
            request_id="novel-evidence-repeated",
        )
        self.assertFalse(repeated["meaningful_progress"])
        self.assertEqual(repeated["task"]["heartbeats_without_progress"], 1)
        self.assertEqual(repeated["novel_evidence"], [])

    def test_operational_event_cannot_masquerade_as_progress(self):
        added = self.add_task("T-EVENT-NOISE")
        operational_event = added["events"][0]["event_id"]
        self.assertTrue(
            self.service.begin(
                "EP",
                "T-EVENT-NOISE",
                actor="Ada",
                request_id="begin-event-noise",
            )["ok"]
        )
        heartbeat = self.service.heartbeat(
            "EP",
            "T-EVENT-NOISE",
            actor="Ada",
            evidence_refs=[operational_event],
            request_id="heartbeat-event-noise",
        )
        self.assertFalse(heartbeat["ok"])
        self.assertEqual(heartbeat["code"], "progress_evidence_not_meaningful")

    def test_dispatch_policy_is_durable_visible_and_enforced(self):
        self.add_task("T-A")
        self.add_task("T-B")
        configured = self.service.configure_dispatch_policy(
            "EP",
            actor="planner",
            reason="Bound the black-box author pool",
            max_active_authors=1,
            reviewer_capacity=1,
            mode="elastic",
            request_id="dispatch-one",
        )
        self.assertTrue(configured["ok"], configured)
        self.assertEqual(configured["dispatch_policy"]["max_active_authors"], 1)
        self.assertTrue(self.service.begin("EP", "T-A", actor="Ada", request_id="begin-T-A")["ok"])
        next_for_bo = self.service.next_action("EP", actor="Bo")
        self.assertIsNone(next_for_bo["next"])
        t_b_exclusion = next(item for item in next_for_bo["excluded"] if item["task_id"] == "T-B")
        self.assertTrue(any(reason["kind"] == "dispatch_capacity_full" for reason in t_b_exclusion["reasons"]))
        denied = self.service.begin("EP", "T-B", actor="Bo", request_id="begin-T-B-denied")
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["code"], "dispatch_capacity_full")
        overview = self.service.overview("EP")
        self.assertTrue(overview["dispatch_policy"]["configured"])
        self.assertEqual(overview["dispatch_policy"]["max_active_authors"], 1)
        expanded = self.service.configure_dispatch_policy(
            "EP",
            actor="planner",
            reason="Exercise two independent work packages",
            max_active_authors=2,
            reviewer_capacity=1,
            mode="elastic",
            request_id="dispatch-two",
        )
        self.assertEqual(expanded["dispatch_policy"]["revision"], 2)
        self.assertTrue(self.service.begin("EP", "T-B", actor="Bo", request_id="begin-T-B")["ok"])

    def test_parallel_reservations_prevent_queue_drain_and_create_overlapping_leases(self):
        for task_id in ("T-P1", "T-P2", "T-P3", "T-UNRESERVED"):
            self.add_task(task_id, role="author", kind="production")
        configured = self.service.configure_dispatch_policy(
            "EP",
            actor="planner",
            reason="Use three author lanes for the deadline frontier",
            max_active_authors=3,
            reviewer_capacity=1,
            request_id="parallel-policy",
        )
        self.assertTrue(configured["ok"], configured)
        scaling = self.service.next_action("EP", actor="planner")["dispatch_usage"]
        self.assertEqual(scaling["target_author_lanes"], 3)
        self.assertEqual(scaling["recommended_additional_authors"], 3)
        for index in range(1, 4):
            registered = self.service.register_agent(
                "EP",
                agent_id=f"author-{index}",
                actor="planner",
                role="author",
                capabilities=["author"],
                presence="online",
                request_id=f"register-author-{index}",
            )
            self.assertTrue(registered["ok"], registered)
        reserved = self.service.reserve_dispatch_tasks(
            "EP",
            actor="planner",
            reason="The user said time is short; fan the independent backlog out now",
            assignments=[
                {"task_id": f"T-P{index}", "agent_id": f"author-{index}"}
                for index in range(1, 4)
            ],
            ttl_seconds=600,
            request_id="reserve-three-authors",
        )
        self.assertTrue(reserved["ok"], reserved)
        self.assertEqual(len(reserved["dispatch_reservations"]), 3)

        original = self.service.next_action("EP", actor="original-author")
        self.assertIsNone(original["next"])
        self.assertEqual(original["dispatch_usage"]["reserved_authors"], 3)
        denied_unreserved = self.service.begin(
            "EP",
            "T-UNRESERVED",
            actor="original-author",
            request_id="original-cannot-drain",
        )
        self.assertFalse(denied_unreserved["ok"], denied_unreserved)
        self.assertEqual(denied_unreserved["code"], "dispatch_capacity_full")
        denied_reserved = self.service.begin(
            "EP", "T-P2", actor="author-1", request_id="wrong-reservation-owner"
        )
        self.assertFalse(denied_reserved["ok"], denied_reserved)
        self.assertEqual(denied_reserved["code"], "dispatch_reserved")

        begun = []
        for index in range(1, 4):
            next_action = self.service.next_action("EP", actor=f"author-{index}")
            self.assertEqual(next_action["next"]["task"]["task_id"], f"T-P{index}")
            result = self.service.begin(
                "EP",
                f"T-P{index}",
                actor=f"author-{index}",
                request_id=f"begin-reserved-{index}",
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["dispatch_reservation"]["status"], "claimed")
            begun.append(result)
        overview = self.service.overview("EP")
        active = [item for item in overview["leases"] if item["status"] == "active"]
        self.assertEqual(
            {(item["task_id"], item["owner"]) for item in active},
            {(f"T-P{index}", f"author-{index}") for index in range(1, 4)},
        )
        self.assertEqual(
            {item["status"] for item in overview["dispatch_reservations"]},
            {"claimed"},
        )

    def test_default_next_projection_is_attention_sized(self):
        self.add_task("T-NEXT", critical_path=True)
        self.add_task("T-BLOCKED", dependencies=["T-NEXT"])
        full = self.service.next_action("EP", actor="Ada")
        compact = agent_next_projection(full)
        self.assertEqual(compact["schema"], "agent-attention-envelope-v2")
        self.assertEqual(compact["attention"]["focus"]["task_id"], "T-NEXT")
        self.assertEqual(compact["attention"]["operation"]["verb"], "begin")
        self.assertNotIn("goal", compact["attention"]["focus"])
        self.assertNotIn("references", compact["attention"]["focus"])
        self.assertNotIn("excluded", compact)
        self.assertIn("1 scheduler-excluded tasks", compact["context_boundary"]["omitted_now"])
        self.assertEqual(compact["incremental_read"]["arguments"]["after"], full["cursor"])

    def test_next_and_explain_are_read_only_and_causal(self):
        self.add_task("T-R", critical_path=True)
        self.add_task("T-B", dependencies=["T-R"])
        self.add_task("T-L", priority=20)
        leased = self.service.begin("EP", "T-L", actor="Bo", request_id="lease-T-L")
        self.assertTrue(leased["ok"], leased)
        store = self.data_root.episode_store("EP")
        versions_before = {state["task_id"]: version for state, version in store.list("task")}
        first = self.service.next_action("EP", actor="Ada")
        second = self.service.next_action("EP", actor="Ada")
        self.assertEqual(first["next"]["task"]["task_id"], "T-R")
        self.assertEqual(first["next"]["task"]["task_id"], second["next"]["task"]["task_id"])
        reasons = {item["task_id"]: item["reasons"] for item in first["excluded"]}
        self.assertTrue(any(reason["kind"] == "dependency_not_approved" for reason in reasons["T-B"]))
        self.assertTrue(any(reason["kind"] == "live_lease" for reason in reasons["T-L"]))
        explanation = self.service.explain("EP", "T-B")
        self.assertTrue(explanation["ok"])
        self.assertTrue(any(item["kind"] == "dependency_not_approved" for item in explanation["causal"]["blockers"]))
        versions_after = {state["task_id"]: version for state, version in store.list("task")}
        self.assertEqual(versions_before, versions_after)

    def test_lease_conflict_expiry_and_stale_generation(self):
        self.add_task("T-R")
        first = self.service.begin("EP", "T-R", actor="Ada", request_id="begin-Ada")
        self.assertTrue(first["ok"])
        heartbeat = self.service.heartbeat(
            "EP",
            "T-R",
            actor="Ada",
            generation=1,
            evidence_refs=["file:result.bin"],
            request_id="heartbeat-Ada",
        )
        self.assertTrue(heartbeat["ok"], heartbeat)
        denied = self.service.begin("EP", "T-R", actor="Bo", request_id="begin-Bo-too-early")
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["code"], "lease_conflict")
        self.clock.advance(61)
        reclaimed = self.service.begin("EP", "T-R", actor="Bo", request_id="begin-Bo-after-expiry")
        self.assertTrue(reclaimed["ok"], reclaimed)
        self.assertEqual(reclaimed["lease"]["generation"], 2)
        stale = self.service.heartbeat(
            "EP", "T-R", actor="Ada", generation=1, request_id="stale-Ada-heartbeat"
        )
        self.assertFalse(stale["ok"])
        self.assertIn(stale["code"], {"lease_owner_mismatch", "stale_lease_generation"})
        leases = self.data_root.episode_store("EP").list("lease")
        self.assertEqual(sum(1 for state, _ in leases if state["status"] == "active"), 1)

    def test_submit_is_content_addressed_and_retry_safe(self):
        self.add_task("T-S")
        self.assertTrue(self.service.begin("EP", "T-S", actor="Ada", request_id="begin-T-S")["ok"])
        first = self.service.submit(
            "EP",
            "T-S",
            actor="Ada",
            artifacts=[{"role": "result", "path": "result.bin"}],
            request_id="submit-T-S",
        )
        self.assertTrue(first["ok"], first)
        replay = self.service.submit(
            "EP",
            "T-S",
            actor="Ada",
            artifacts=[{"role": "result", "path": "result.bin"}],
            request_id="submit-T-S",
        )
        self.assertTrue(replay["ok"])
        self.assertTrue(replay["idempotent_replay"])
        duplicate = self.service.submit(
            "EP",
            "T-S",
            actor="Ada",
            artifacts=[{"role": "result", "path": "result.bin"}],
            request_id="submit-T-S-new-request",
        )
        self.assertTrue(duplicate["ok"])
        self.assertTrue(duplicate["duplicate_submission"])
        store = self.data_root.episode_store("EP")
        self.assertEqual(len(store.list("artifact")), 1)
        submit_events = [event for event in store.events_after() if event["event_type"] == "TaskSubmitted"]
        self.assertEqual(len(submit_events), 1)

    def test_change_and_gap_are_durable_and_explainable(self):
        self.add_task("T-C")
        self.add_task("T-G", priority=50)
        self.add_task("T-U", priority=1)
        self.assertTrue(self.service.begin("EP", "T-C", actor="Ada", request_id="begin-T-C")["ok"])
        submitted = self.service.submit(
            "EP",
            "T-C",
            actor="Ada",
            artifacts=[{"role": "result", "path": "result.bin"}],
            request_id="submit-T-C",
        )
        artifact_id = submitted["artifacts"][0]["artifact_id"]
        change = self.service.change(
            "EP",
            actor="human",
            target_id=artifact_id,
            reason="replace the unverified formula frame",
            request_id="change-A1",
        )
        self.assertTrue(change["ok"], change)
        gap = self.service.gap(
            "EP",
            "T-G",
            actor="Ada",
            reason="source transcript is missing",
            request_id="gap-T-G",
        )
        self.assertTrue(gap["ok"], gap)
        next_action = self.service.next_action("EP", actor="Bo")
        self.assertNotEqual(next_action["next"]["task"]["task_id"], "T-G")
        explanation = self.service.explain("EP", "T-C")
        self.assertEqual(explanation["causal"]["changes"][0]["reason"], "replace the unverified formula frame")
        self.assertEqual(self.service.explain("EP", "T-G")["causal"]["gaps"][0]["reason"], "source transcript is missing")

    def test_upstream_change_stales_only_affected_lineage(self):
        self.add_task("T-UP")
        upstream = self.approve_task("T-UP")
        upstream_artifact = upstream["task"]["approved_artifact_ids"][0]
        self.add_task("T-DOWN", dependencies=["T-UP"])
        downstream = self.approve_task("T-DOWN")
        downstream_artifact = downstream["task"]["approved_artifact_ids"][0]
        self.add_task("T-SIBLING")
        sibling = self.approve_task("T-SIBLING")
        sibling_artifact = sibling["task"]["approved_artifact_ids"][0]

        changed = self.service.change(
            "EP",
            actor="human",
            target_id=upstream_artifact,
            reason="Replace the upstream mathematical premise",
            request_id="change-upstream-lineage",
        )
        self.assertTrue(changed["ok"], changed)
        self.assertEqual(changed["invalidated_tasks"], ["T-DOWN"])
        store = self.data_root.episode_store("EP")
        upstream_state, _ = store.get("task", "T-UP")
        downstream_state, _ = store.get("task", "T-DOWN")
        sibling_state, _ = store.get("task", "T-SIBLING")
        self.assertEqual(upstream_state["status"], "rework")
        self.assertIsNone(upstream_state["candidate"])
        self.assertEqual(downstream_state["status"], "blocked")
        self.assertIsNone(downstream_state["candidate"])
        self.assertEqual(sibling_state["status"], "approved")
        self.assertEqual(store.get("artifact", upstream_artifact)[0]["status"], "superseded")
        self.assertEqual(store.get("artifact", downstream_artifact)[0]["status"], "stale")
        self.assertEqual(store.get("artifact", sibling_artifact)[0]["status"], "approved")

        self.artifact.write_bytes(b"reapproved-upstream-result")
        began = self.service.begin(
            "EP", "T-UP", actor="Ada", request_id="reapprove-upstream-begin"
        )
        self.assertTrue(began["ok"], began)
        submitted = self.service.submit(
            "EP",
            "T-UP",
            actor="Ada",
            artifacts=[{"role": "result", "path": "result.bin"}],
            request_id="reapprove-upstream-submit",
        )
        context = self.service.review_context("EP", "T-UP", actor="Bo")
        reapproved = self.service.review(
            "EP",
            "T-UP",
            actor="Bo",
            verdict="pass",
            review_context_hash=context["review_context_hash"],
            request_id="reapprove-upstream-review",
        )
        self.assertEqual(reapproved["released_downstream_tasks"], ["T-DOWN"])
        downstream_state, _ = store.get("task", "T-DOWN")
        self.assertEqual(downstream_state["status"], "rework")
        self.assertEqual(downstream_state["blockers"], [])
        self.assertEqual(
            downstream_state["upstream_reapproval_receipts"][-1][
                "source_change_ids"
            ],
            [changed["change"]["change_id"]],
        )
        downstream_begin = self.service.begin(
            "EP", "T-DOWN", actor="Ada", request_id="downstream-rebuild-begin"
        )
        self.assertTrue(downstream_begin["ok"], downstream_begin)
        self.assertEqual(
            downstream_begin["capsule"]["payload"]["task"][
                "upstream_reapproval_receipts"
            ][-1]["upstream_task_id"],
            "T-UP",
        )

    def test_gap_cannot_silently_reopen_an_approved_task(self):
        self.add_task("T-FINAL")
        self.approve_task("T-FINAL")
        store = self.data_root.episode_store("EP")
        before, version = store.get("task", "T-FINAL")
        denied = self.service.gap(
            "EP",
            "T-FINAL",
            actor="Ada",
            reason="late uncertainty",
            request_id="gap-after-approval",
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["code"], "gap_not_valid_for_state")
        after, after_version = store.get("task", "T-FINAL")
        self.assertEqual(before, after)
        self.assertEqual(version, after_version)

    def test_human_can_explicitly_reverse_approval_with_auditable_rework_context(self):
        self.add_task("T-HUMAN-REVERSE", human_gate=True)
        self.assertTrue(
            self.service.begin(
                "EP", "T-HUMAN-REVERSE", actor="Ada", request_id="reverse-begin-1"
            )["ok"]
        )
        submitted = self.service.submit(
            "EP",
            "T-HUMAN-REVERSE",
            actor="Ada",
            artifacts=[{"role": "result", "path": "result.bin"}],
            request_id="reverse-submit-1",
        )
        self.assertTrue(submitted["ok"], submitted)
        context = self.service.review_context(
            "EP", "T-HUMAN-REVERSE", actor="Bo"
        )
        reviewed = self.service.review(
            "EP",
            "T-HUMAN-REVERSE",
            actor="Bo",
            verdict="pass",
            review_context_hash=context["review_context_hash"],
            request_id="reverse-review-1",
        )
        self.assertEqual(reviewed["task"]["status"], "user_review_pending")
        approved = self.service.human_decide(
            "EP",
            "T-HUMAN-REVERSE",
            actor="human-ui",
            verdict="approve",
            note="First viewing passed.",
            request_id="reverse-human-approve",
        )
        self.assertEqual(approved["task"]["status"], "approved")
        self.add_task(
            "T-HUMAN-DOWN", dependencies=["T-HUMAN-REVERSE"]
        )
        self.approve_task("T-HUMAN-DOWN")
        artifact_id = approved["task"]["approved_artifact_ids"][0]
        annotation = self.service.annotate(
            "EP",
            actor="human-ui",
            target_id=artifact_id,
            body="At 00:00.405 the hierarchy is still unclear.",
            severity="blocker",
            location={
                "artifact_id": artifact_id,
                "time_seconds": 0.405,
                "timecode": "00:00.405",
                "position": {"x": 0.42, "y": 0.31},
            },
            request_id="reverse-human-note",
        )
        self.assertEqual(
            annotation["annotation"]["delivery_policy"],
            "after_explicit_reopen",
        )
        self.assertEqual(
            self.data_root.episode_store("EP").get("task", "T-HUMAN-REVERSE")[0]["status"],
            "approved",
        )

        reversed_result = self.service.change(
            "EP",
            actor="human-ui",
            target_id="T-HUMAN-REVERSE",
            reason="Second viewing rejects the frame hierarchy; revise the annotated frame.",
            kind="human_approval_reversed",
            request_id="reverse-human-change",
        )
        self.assertTrue(reversed_result["ok"], reversed_result)
        self.assertTrue(reversed_result["approval_reversed"])
        self.assertEqual(reversed_result["task"]["status"], "rework")
        self.assertEqual(
            reversed_result["task"]["human_decision"]["verdict"],
            "approval_revoked",
        )
        self.assertEqual(
            reversed_result["task"]["human_decision_history"][-1]["verdict"],
            "approve",
        )
        store = self.data_root.episode_store("EP")
        self.assertEqual(store.get("artifact", artifact_id)[0]["status"], "stale")
        event_types = [event["event_type"] for event in store.events_after()]
        self.assertIn("TaskHumanApprovalReversed", event_types)

        rework = self.service.begin(
            "EP", "T-HUMAN-REVERSE", actor="Ada", request_id="reverse-begin-2"
        )
        self.assertTrue(rework["ok"], rework)
        capsule = rework["capsule"]["payload"]
        self.assertIn("At 00:00.405", capsule["assembled_prompt"])
        self.assertIn("Second viewing rejects", capsule["assembled_prompt"])
        self.assertEqual(
            capsule["why_now"]["human_annotation_delivery"]["boundary"],
            "begin",
        )
        self.assertEqual(capsule["context_manifest"]["annotation_count"], 1)

        observed = self.service.observe(
            "EP",
            actor="Ada",
            task_id="T-HUMAN-REVERSE",
            category="attention_delivery",
            severity="high",
            summary="Consumed the exact Human annotation at the rework begin boundary.",
            expectation="The event, signed capsule, and action log must agree.",
            actual=(
                f"annotation_id={annotation['annotation']['annotation_id']}; "
                "boundary=begin; interrupt_active_lease=false"
            ),
            request_id="reverse-attention-observation",
        )
        overview = self.service.overview("EP")
        self.assertIn(
            observed["observation"]["observation_id"],
            [item["observation_id"] for item in overview["observations"]],
        )
        self.assertEqual(
            overview["observations"][0]["task_id"],
            "T-HUMAN-REVERSE",
        )
        explained = self.service.explain("EP", "T-HUMAN-REVERSE")
        self.assertEqual(
            explained["causal"]["annotations"][0]["annotation_id"],
            annotation["annotation"]["annotation_id"],
        )
        self.assertEqual(
            explained["causal"]["observations"][0]["observation_id"],
            observed["observation"]["observation_id"],
        )

        revised_path = self.repo / "result-v2.bin"
        revised_path.write_bytes(b"human-approved-revision")
        resubmitted = self.service.submit(
            "EP",
            "T-HUMAN-REVERSE",
            actor="Ada",
            artifacts=[{"role": "result", "path": "result-v2.bin"}],
            request_id="reverse-submit-2",
        )
        self.assertTrue(resubmitted["ok"], resubmitted)
        second_context = self.service.review_context(
            "EP", "T-HUMAN-REVERSE", actor="Bo"
        )
        second_review = self.service.review(
            "EP",
            "T-HUMAN-REVERSE",
            actor="Bo",
            verdict="pass",
            review_context_hash=second_context["review_context_hash"],
            request_id="reverse-review-2",
        )
        self.assertEqual(second_review["task"]["status"], "user_review_pending")
        second_approval = self.service.human_decide(
            "EP",
            "T-HUMAN-REVERSE",
            actor="human-ui",
            verdict="approve",
            note="The revision now satisfies the Human gate.",
            request_id="reverse-human-approve-2",
        )
        self.assertEqual(
            second_approval["released_downstream_tasks"],
            ["T-HUMAN-DOWN"],
        )
        downstream, _ = store.get("task", "T-HUMAN-DOWN")
        self.assertEqual(downstream["status"], "rework")
        receipt = downstream["upstream_reapproval_receipts"][-1]
        self.assertIn(
            annotation["annotation"]["annotation_id"],
            receipt["annotation_ids"],
        )
        self.assertIn(
            observed["observation"]["observation_id"],
            receipt["observation_ids"],
        )
        downstream_begin = self.service.begin(
            "EP",
            "T-HUMAN-DOWN",
            actor="Ada",
            request_id="reverse-downstream-begin-2",
        )
        self.assertEqual(
            downstream_begin["capsule"]["payload"]["task"][
                "upstream_reapproval_receipts"
            ][-1]["upstream_task_id"],
            "T-HUMAN-REVERSE",
        )
        downstream_capsule = downstream_begin["capsule"]["payload"]
        inherited = downstream_capsule["relevant_annotations"]
        self.assertEqual(len(inherited), 1)
        self.assertEqual(
            inherited[0]["annotation_id"],
            annotation["annotation"]["annotation_id"],
        )
        self.assertEqual(
            inherited[0]["delivery_via"],
            "upstream_reapproval_receipt",
        )
        self.assertEqual(
            inherited[0]["upstream_task_id"],
            "T-HUMAN-REVERSE",
        )
        self.assertIn("At 00:00.405", downstream_capsule["assembled_prompt"])

        downstream_submission = self.service.submit(
            "EP",
            "T-HUMAN-DOWN",
            actor="Ada",
            artifacts=[{"role": "result", "path": "result.bin"}],
            request_id="reverse-downstream-submit-2",
        )
        self.assertTrue(downstream_submission["ok"], downstream_submission)
        downstream_review_context = self.service.review_context(
            "EP", "T-HUMAN-DOWN", actor="Bo"
        )
        self.assertEqual(
            downstream_review_context["capsule"]["relevant_annotations"][0][
                "annotation_id"
            ],
            annotation["annotation"]["annotation_id"],
        )
        self.assertEqual(
            downstream_review_context["capsule"]["why_now"][
                "human_annotation_delivery"
            ]["count"],
            1,
        )

    def test_structured_denials_do_not_mutate_domain_aggregates(self):
        self.add_task("T-D")
        self.approve_task("T-D")
        store = self.data_root.episode_store("EP")
        task_version = store.get("task", "T-D")[1]
        cursor = store.cursor()
        terminal = self.service.begin("EP", "T-D", actor="Ada", request_id="deny-terminal")
        self.assertFalse(terminal["ok"])
        self.assertEqual(terminal["code"], "invalid_transition")
        missing_gap = self.service.gap(
            "EP", "T-X", actor="Ada", reason="missing", request_id="deny-gap-missing"
        )
        self.assertFalse(missing_gap["ok"])
        missing_change = self.service.change(
            "EP", actor="Ada", target_id="A-X", reason="change", request_id="deny-change-missing"
        )
        self.assertFalse(missing_change["ok"])
        self.assertEqual(store.get("task", "T-D")[1], task_version)
        self.assertEqual(store.cursor(), cursor)
        for denial in (terminal, missing_gap, missing_change):
            self.assertTrue(denial["failed_invariant"])
            self.assertIn("allowed_next", denial)
            self.assertIn("subject", denial)

    def test_context_capsule_fails_closed_on_reference_drift(self):
        self.add_task("T-REF")
        self.reference.write_text("changed guidance\n", encoding="utf-8")
        result = self.service.begin("EP", "T-REF", actor="Ada", request_id="drifted-reference")
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "reference_drift")
        task, _ = self.data_root.episode_store("EP").get("task", "T-REF")
        self.assertEqual(task["status"], "planned")

    def test_reference_drift_has_one_explicit_rebind_path(self):
        added = self.add_task("T-REF-REBIND")
        original = added["task"]["references"][0]
        self.reference.write_text(
            "# Reviewed guidance v2\nUse exact evidence and preserve lineage.\n",
            encoding="utf-8",
        )
        denied = self.service.begin(
            "EP",
            "T-REF-REBIND",
            actor="Ada",
            request_id="reference-rebind-denied-begin",
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["code"], "reference_drift")
        self.assertIn("reference-rebind", denied["allowed_next"])

        rebound = self.service.rebind_reference(
            "EP",
            "T-REF-REBIND",
            original["reference_id"],
            "guidance.md",
            actor="supervisor",
            reason="Adopt the reviewed v2 guidance after impact inspection",
            context_class="stable_rule",
            context_version="reviewed-guidance-v2",
            context_slot="service.reviewed.guidance",
            scope="service:reviewer",
            service_binding="reviewer",
            mutable=False,
            request_id="reference-rebind-adopt-v2",
        )
        self.assertTrue(rebound["ok"], rebound)
        self.assertNotEqual(
            rebound["reference"]["sha256"], original["sha256"]
        )
        self.assertEqual(rebound["task"]["scope_revision"], 2)
        self.assertEqual(rebound["reference"]["context_class"], "stable_rule")
        self.assertEqual(rebound["reference"]["context_version"], "reviewed-guidance-v2")
        self.assertEqual(rebound["reference"]["context_slot"], "service.reviewed.guidance")
        self.assertFalse(rebound["reference"]["mutable"])
        begun = self.service.begin(
            "EP",
            "T-REF-REBIND",
            actor="Ada",
            request_id="reference-rebind-fresh-begin",
        )
        self.assertTrue(begun["ok"], begun)
        self.assertIn(
            "preserve lineage",
            begun["capsule"]["payload"]["required_references"][0]["content"],
        )

    def test_pinned_hard_gate_precedes_independent_review(self):
        review_text = self.repo / "review.txt"
        review_text.write_text("exact candidate text\n", encoding="utf-8")
        (self.repo / "irrelevant.txt").write_text(
            "unbound context must remain absent\n", encoding="utf-8"
        )
        self.add_task(
            "T-GATE",
            validators=["validators/integrity/manifest.json"],
        )
        self.assertTrue(
            self.service.begin(
                "EP", "T-GATE", actor="Ada", request_id="gate-begin"
            )["ok"]
        )
        submitted = self.service.submit(
            "EP",
            "T-GATE",
            actor="Ada",
            artifacts=[{"role": "result", "path": "review.txt"}],
            request_id="gate-submit",
        )
        self.assertTrue(submitted["ok"], submitted)
        scheduled = self.service.next_action("EP", actor="Bo")
        self.assertEqual(scheduled["next"]["action"], "gate")
        denied = self.service.review(
            "EP",
            "T-GATE",
            actor="Bo",
            verdict="pass",
            request_id="review-before-gate",
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["code"], "quality_gate_incomplete")
        passed = self.service.run_gate(
            "EP",
            "T-GATE",
            "fixture-integrity",
            actor="gate-worker",
            request_id="run-gate",
        )
        self.assertTrue(passed["ok"], passed)
        self.assertEqual(passed["gate"]["status"], "pass")
        replay = self.service.run_gate(
            "EP",
            "T-GATE",
            "fixture-integrity",
            actor="gate-worker",
            request_id="run-gate",
        )
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(self.service.next_action("EP", actor="Bo")["next"]["action"], "review")
        store = self.data_root.episode_store("EP")
        cursor_before_context = store.cursor()
        context = self.service.review_context("EP", "T-GATE", actor="Bo")
        self.assertTrue(context["ok"], context)
        self.assertEqual(store.cursor(), cursor_before_context)
        rendered_context = __import__("json").dumps(context, ensure_ascii=False)
        self.assertIn("Use exact evidence.", rendered_context)
        self.assertIn("exact candidate text", rendered_context)
        self.assertNotIn("unbound context must remain absent", rendered_context)
        missing_context = self.service.review(
            "EP",
            "T-GATE",
            actor="Bo",
            verdict="pass",
            request_id="review-without-context",
        )
        self.assertFalse(missing_context["ok"])
        self.assertEqual(missing_context["code"], "review_context_required")
        review = self.service.review(
            "EP",
            "T-GATE",
            actor="Bo",
            verdict="pass",
            review_context_hash=context["review_context_hash"],
            request_id="review-after-gate",
        )
        self.assertTrue(review["ok"], review)

    def test_unrelated_sibling_approval_does_not_stale_review_context(self):
        first_path = self.repo / "review-first.bin"
        sibling_path = self.repo / "review-sibling.bin"
        first_path.write_bytes(b"first-candidate")
        sibling_path.write_bytes(b"sibling-candidate")
        self.add_task("T-REVIEW-FIRST")
        self.add_task("T-REVIEW-SIBLING")

        self.assertTrue(
            self.service.begin(
                "EP", "T-REVIEW-FIRST", actor="Ada", request_id="review-first-begin"
            )["ok"]
        )
        self.assertTrue(
            self.service.submit(
                "EP",
                "T-REVIEW-FIRST",
                actor="Ada",
                artifacts=[{"role": "result", "path": "review-first.bin"}],
                request_id="review-first-submit",
            )["ok"]
        )
        self.assertTrue(
            self.service.begin(
                "EP",
                "T-REVIEW-SIBLING",
                actor="Cy",
                request_id="review-sibling-begin",
            )["ok"]
        )
        self.assertTrue(
            self.service.submit(
                "EP",
                "T-REVIEW-SIBLING",
                actor="Cy",
                artifacts=[{"role": "result", "path": "review-sibling.bin"}],
                request_id="review-sibling-submit",
            )["ok"]
        )

        first_context = self.service.review_context(
            "EP", "T-REVIEW-FIRST", actor="Bo"
        )
        sibling_context = self.service.review_context(
            "EP", "T-REVIEW-SIBLING", actor="Bo"
        )
        self.assertNotIn("state_cursor", first_context["capsule"])
        self.assertEqual(
            first_context["capsule"]["context_manifest"]["cursor_scope"],
            "response_envelope_only",
        )
        sibling_review = self.service.review(
            "EP",
            "T-REVIEW-SIBLING",
            actor="Bo",
            verdict="pass",
            review_context_hash=sibling_context["review_context_hash"],
            request_id="review-sibling-pass",
        )
        self.assertTrue(sibling_review["ok"], sibling_review)

        first_review = self.service.review(
            "EP",
            "T-REVIEW-FIRST",
            actor="Bo",
            verdict="pass",
            review_context_hash=first_context["review_context_hash"],
            request_id="review-first-pass-after-sibling",
        )
        self.assertTrue(first_review["ok"], first_review)

    def test_relevant_annotation_stales_review_context(self):
        annotated_path = self.repo / "review-annotated.bin"
        annotated_path.write_bytes(b"annotated-candidate")
        self.add_task("T-REVIEW-ANNOTATED")
        self.assertTrue(
            self.service.begin(
                "EP",
                "T-REVIEW-ANNOTATED",
                actor="Ada",
                request_id="review-annotated-begin",
            )["ok"]
        )
        submitted = self.service.submit(
            "EP",
            "T-REVIEW-ANNOTATED",
            actor="Ada",
            artifacts=[{"role": "result", "path": "review-annotated.bin"}],
            request_id="review-annotated-submit",
        )
        self.assertTrue(submitted["ok"], submitted)
        context = self.service.review_context(
            "EP", "T-REVIEW-ANNOTATED", actor="Bo"
        )
        artifact_id = submitted["task"]["candidate"]["artifact_ids"][0]
        annotation = self.service.annotate(
            "EP",
            actor="human-ui",
            target_id=artifact_id,
            body="This exact candidate now has a review note.",
            severity="warning",
            request_id="review-annotated-note",
        )
        self.assertTrue(annotation["ok"], annotation)
        stale = self.service.review(
            "EP",
            "T-REVIEW-ANNOTATED",
            actor="Bo",
            verdict="pass",
            review_context_hash=context["review_context_hash"],
            request_id="review-annotated-stale",
        )
        self.assertFalse(stale["ok"], stale)
        self.assertEqual(stale["code"], "review_context_stale")

    def test_validator_code_drift_and_canary_are_fail_closed(self):
        self.add_task(
            "T-DRIFT",
            validators=["validators/integrity/manifest.json"],
        )
        self.assertTrue(
            self.service.begin(
                "EP", "T-DRIFT", actor="Ada", request_id="drift-begin"
            )["ok"]
        )
        self.assertTrue(
            self.service.submit(
                "EP",
                "T-DRIFT",
                actor="Ada",
                artifacts=[{"role": "result", "path": "result.bin"}],
                request_id="drift-submit",
            )["ok"]
        )
        self.validator_script.write_text(
            self.validator_script.read_text(encoding="utf-8") + "\n# drift\n",
            encoding="utf-8",
        )
        denied = self.service.run_gate(
            "EP",
            "T-DRIFT",
            "fixture-integrity",
            actor="gate-worker",
            request_id="drifted-gate",
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["code"], "validator_drift")
        rebound = self.service.rebind_validator(
            "EP",
            "T-DRIFT",
            "fixture-integrity",
            "validators/integrity/manifest.json",
            actor="supervisor",
            reason="Adopt the audited replacement bundle after drift detection",
            request_id="rebind-validator",
        )
        self.assertTrue(rebound["ok"], rebound)
        self.assertEqual(rebound["task"]["status"], "rework")
        self.assertIsNone(rebound["task"]["candidate"])
        self.assertEqual(rebound["task"]["scope_revision"], 2)

        import json
        from supervision.core import DomainError

        manifest = json.loads(self.validator_manifest.read_text(encoding="utf-8"))
        manifest["status"] = "canary"
        manifest["version"] = "2.0.0-canary"
        self.validator_manifest.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(DomainError) as context:
            self.service.add_task(
                "EP",
                task_id="T-CANARY-DENIED",
                title="Denied canary",
                goal="Must require explicit canary opt-in",
                actor="planner",
                request_id="add-canary-denied",
                validators=["validators/integrity/manifest.json"],
            )
        self.assertEqual(context.exception.code, "validator_not_active")
        accepted = self.service.add_task(
            "EP",
            task_id="T-CANARY",
            title="Explicit canary",
            goal="Exercise a planned canary only",
            actor="planner",
            request_id="add-canary",
            validators=[
                {
                    "path": "validators/integrity/manifest.json",
                    "allow_canary": True,
                }
            ],
        )
        self.assertTrue(accepted["ok"], accepted)
        self.assertTrue(accepted["task"]["required_validators"][0]["canary"])

    def test_supervisor_stops_stagnant_local_loop_and_requires_replan(self):
        self.add_task(
            "T-LOOP",
            budget={
                "soft_active_seconds": 10,
                "hard_active_seconds": 100,
                "max_no_progress_heartbeats": 2,
                "max_attempts": 2,
            },
        )
        self.assertTrue(self.service.begin("EP", "T-LOOP", actor="Ada", request_id="loop-begin")["ok"])
        self.clock.advance(5)
        first = self.service.heartbeat("EP", "T-LOOP", actor="Ada", request_id="loop-hb-1")
        self.assertTrue(first["ok"])
        self.assertFalse(first["supervision"]["stopped"])
        self.clock.advance(5)
        second = self.service.heartbeat("EP", "T-LOOP", actor="Ada", request_id="loop-hb-2")
        self.assertTrue(second["ok"])
        self.assertTrue(second["supervision"]["stopped"])
        self.assertEqual(second["task"]["status"], "blocked")
        replan = self.service.replan(
            "EP",
            "T-LOOP",
            actor="supervisor",
            reason="Switch method after two evidence-free intervals",
            budget_patch={"hard_active_seconds": 140},
            request_id="loop-replan",
        )
        self.assertTrue(replan["ok"], replan)
        self.assertEqual(replan["task"]["status"], "rework")

    def test_route_switch_replaces_method_rewires_only_descendants_and_fulfills(self):
        old_audio = self.repo / "old.wav"
        recording = self.repo / "recording.wav"
        for path, value in ((old_audio, 1), (recording, 2)):
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(16000)
                handle.writeframes((value.to_bytes(2, "little", signed=True)) * 160)
        self.add_task(
            "T-AUDIO-TTS",
            required_artifact_roles=["narration_audio"],
        )
        approved_audio = self.approve_task(
            "T-AUDIO-TTS", role="narration_audio", path="old.wav"
        )
        old_audio_id = approved_audio["task"]["approved_artifact_ids"][0]
        self.add_task(
            "T-EDIT",
            dependencies=["T-AUDIO-TTS"],
            input_artifact_ids=[old_audio_id],
        )
        approved_edit = self.approve_task("T-EDIT")
        edit_artifact_id = approved_edit["task"]["approved_artifact_ids"][0]
        self.add_task("T-SIBLING")
        approved_sibling = self.approve_task("T-SIBLING")
        sibling_artifact_id = approved_sibling["task"]["approved_artifact_ids"][0]

        switched = self.service.switch_route(
            "EP",
            "T-AUDIO-TTS",
            "T-AUDIO-RECORDING",
            actor="supervisor",
            strategy="direct_recording",
            reason="User supplied a direct narration recording instead of TTS",
            replacement_spec={
                "title": "Ingest direct narration recording",
                "goal": "Validate and expose the supplied recording as narration audio",
                "references": [],
            },
            request_id="switch-to-direct-recording",
        )
        self.assertTrue(switched["ok"], switched)
        self.assertEqual(switched["rewired_tasks"], ["T-EDIT"])
        self.assertEqual(switched["invalidated_tasks"], ["T-EDIT"])
        store = self.data_root.episode_store("EP")
        old_task, _ = store.get("task", "T-AUDIO-TTS")
        replacement, _ = store.get("task", "T-AUDIO-RECORDING")
        edit, _ = store.get("task", "T-EDIT")
        sibling, _ = store.get("task", "T-SIBLING")
        self.assertEqual(old_task["status"], "superseded")
        self.assertEqual(replacement["status"], "planned")
        self.assertEqual(
            replacement["output_contract"]["required_artifact_roles"],
            ["narration_audio"],
        )
        self.assertEqual(edit["status"], "rework")
        self.assertEqual(edit["dependencies"], ["T-AUDIO-RECORDING"])
        self.assertNotIn(old_audio_id, edit["input_artifact_ids"])
        self.assertEqual(sibling["status"], "approved")
        self.assertEqual(store.get("artifact", old_audio_id)[0]["status"], "out_of_route")
        self.assertEqual(store.get("artifact", edit_artifact_id)[0]["status"], "stale")
        self.assertEqual(store.get("artifact", sibling_artifact_id)[0]["status"], "approved")
        self.assertEqual(
            self.service.next_action("EP", actor="Recorder")["next"]["task"]["task_id"],
            "T-AUDIO-RECORDING",
        )

        approved_replacement = self.approve_task(
            "T-AUDIO-RECORDING",
            author="Recorder",
            reviewer="Reviewer",
            role="narration_audio",
            path="recording.wav",
        )
        self.assertTrue(approved_replacement["ok"], approved_replacement)
        route, _ = store.get(
            "route", switched["route_switch"]["route_switch_id"]
        )
        self.assertEqual(route["status"], "fulfilled")
        self.assertEqual(
            self.service.next_action("EP", actor="Editor")["next"]["task"]["task_id"],
            "T-EDIT",
        )

    def test_narration_audio_contract_rejects_extension_spoof_before_review(self):
        fake = self.repo / "fake.wav"
        fake.write_bytes(b"this is text, not a wave stream")
        self.add_task(
            "T-FAKE-AUDIO",
            required_artifact_roles=["narration_audio"],
        )
        self.assertTrue(
            self.service.begin(
                "EP", "T-FAKE-AUDIO", actor="Recorder", request_id="fake-audio-begin"
            )["ok"]
        )
        denied = self.service.submit(
            "EP",
            "T-FAKE-AUDIO",
            actor="Recorder",
            artifacts=[{"role": "narration_audio", "path": "fake.wav"}],
            request_id="fake-audio-submit",
        )
        self.assertFalse(denied["ok"], denied)
        self.assertEqual(denied["code"], "artifact_contract_failed")
        self.assertEqual(denied["failed_invariant"], "narration_audio_decodable")
        task, _ = self.data_root.episode_store("EP").get("task", "T-FAKE-AUDIO")
        self.assertEqual(task["status"], "working")
        self.assertIsNone(task["candidate"])

    def test_review_return_waits_for_attention_boundary_and_can_be_rerouted(self):
        self.add_task("T-FIRST", priority=20)
        self.add_task("T-FLOW", priority=10)
        self.add_task("T-POOL", priority=1)
        self.assertTrue(
            self.service.begin(
                "EP", "T-FIRST", actor="Ada", request_id="return-first-begin"
            )["ok"]
        )
        submitted = self.service.submit(
            "EP",
            "T-FIRST",
            actor="Ada",
            artifacts=[{"role": "result", "path": "result.bin"}],
            request_id="return-first-submit",
        )
        self.assertTrue(submitted["ok"], submitted)
        self.assertTrue(
            self.service.begin(
                "EP", "T-FLOW", actor="Ada", request_id="return-flow-begin"
            )["ok"]
        )
        context = self.service.review_context("EP", "T-FIRST", actor="Bo")
        revised = self.service.review(
            "EP",
            "T-FIRST",
            actor="Bo",
            verdict="revise",
            findings=[{"description": "Fix the timing handoff"}],
            review_context_hash=context["review_context_hash"],
            request_id="return-first-review",
        )
        self.assertTrue(revised["ok"], revised)
        ticket = revised["return_ticket"]
        self.assertEqual(ticket["assigned_to"], "Ada")
        self.assertEqual(ticket["delivery_policy"], "attention_boundary")
        self.assertFalse(ticket["interrupt_active_lease"])

        while_busy = self.service.next_action("EP", actor="Ada")
        self.assertEqual(while_busy["next"]["action"], "continue")
        self.assertEqual(while_busy["next"]["task"]["task_id"], "T-FLOW")
        self.assertEqual(
            while_busy["deferred_returns"]["delivery"],
            "deferred_until_attention_boundary",
        )
        self.assertEqual(while_busy["deferred_returns"]["ticket_ids"], [])
        self.assertFalse(
            any(
                item.get("task", {}).get("task_id") == "T-FIRST"
                or item.get("return_ticket")
                for item in while_busy["other_actionable"]
            ),
            while_busy,
        )
        other_actor = self.service.next_action("EP", actor="Cy")
        self.assertEqual(other_actor["next"]["task"]["task_id"], "T-POOL")
        reserved = next(
            item for item in other_actor["excluded"] if item["task_id"] == "T-FIRST"
        )
        self.assertTrue(
            any(reason["kind"] == "return_reserved" for reason in reserved["reasons"])
        )

        self.assertTrue(
            self.service.submit(
                "EP",
                "T-FLOW",
                actor="Ada",
                artifacts=[{"role": "result", "path": "result.bin"}],
                request_id="return-flow-submit",
            )["ok"]
        )
        at_boundary = self.service.next_action("EP", actor="Ada")
        self.assertEqual(at_boundary["next"]["action"], "return_rework")
        self.assertEqual(at_boundary["next"]["task"]["task_id"], "T-FIRST")

        rerouted = self.service.reroute_return(
            "EP",
            ticket["return_ticket_id"],
            actor="supervisor",
            to_actor="Cy",
            reason="Move the repair to the available timing specialist",
            request_id="reroute-return-to-cy",
        )
        self.assertTrue(rerouted["ok"], rerouted)
        self.assertNotEqual(
            self.service.next_action("EP", actor="Ada")["next"]["task"]["task_id"],
            "T-FIRST",
        )
        for_cy = self.service.next_action("EP", actor="Cy")
        self.assertEqual(for_cy["next"]["action"], "return_rework")
        self.assertEqual(for_cy["next"]["task"]["task_id"], "T-FIRST")
        accepted = self.service.begin(
            "EP", "T-FIRST", actor="Cy", request_id="accept-rerouted-return"
        )
        self.assertTrue(accepted["ok"], accepted)
        self.assertEqual(accepted["accepted_return"]["status"], "accepted")
        repair_feedback = accepted["capsule"]["payload"]["relevant_feedback"]
        self.assertTrue(
            any(
                item.get("instruction") == "Fix the timing handoff"
                and item.get("return_ticket_id") == ticket["return_ticket_id"]
                for item in repair_feedback
            ),
            repair_feedback,
        )

    def test_dual_axis_scope_is_bounded_and_never_implies_a_stage_barrier(self):
        for unit_id, title, kind, parent, order in (
            ("U-EP", "Episode", "episode", None, 0),
            ("U-CH", "Chapter", "chapter", "U-EP", 0),
            ("U-SC", "Scene", "scene", "U-CH", 0),
            ("U-BEAT", "Animation beat", "beat", "U-SC", 0),
        ):
            result = self.service.add_content_unit(
                "EP",
                unit_id=unit_id,
                title=title,
                kind=kind,
                parent_unit_id=parent,
                order=order,
                actor="planner",
                request_id=f"add-{unit_id}",
            )
            self.assertTrue(result["ok"], result)
        denied_depth = self.service.add_content_unit(
            "EP",
            unit_id="U-TOO-DEEP",
            title="Too deep",
            kind="operation",
            parent_unit_id="U-BEAT",
            actor="planner",
            request_id="add-too-deep",
        )
        self.assertFalse(denied_depth["ok"])
        self.assertEqual(denied_depth["code"], "content_depth_exceeded")
        for deliverable_id, title, order in (
            ("D-AUDIO", "Narration audio", 0),
            ("D-VISUAL", "Visual animation", 1),
            ("D-INTEGRATION", "Integration", 2),
        ):
            result = self.service.add_deliverable(
                "EP",
                deliverable_id=deliverable_id,
                title=title,
                order=order,
                actor="planner",
                request_id=f"add-{deliverable_id}",
            )
            self.assertTrue(result["ok"], result)
        self.add_task(
            "T-AUDIO",
            content_unit_id="U-SC",
            deliverable_id="D-AUDIO",
            priority=30,
        )
        self.add_task(
            "T-VISUAL",
            content_unit_id="U-SC",
            deliverable_id="D-VISUAL",
            priority=20,
        )
        self.add_task(
            "T-INTEGRATE",
            content_unit_id="U-EP",
            deliverable_id="D-INTEGRATION",
            dependencies=["T-AUDIO", "T-VISUAL"],
        )
        self.assertTrue(
            self.service.begin(
                "EP", "T-AUDIO", actor="AudioAgent", request_id="begin-audio"
            )["ok"]
        )
        other_agent = self.service.next_action("EP", actor="VisualAgent")
        self.assertEqual(other_agent["next"]["task"]["task_id"], "T-VISUAL")
        overview = self.service.overview("EP")
        self.assertEqual(overview["scope"]["schema"], "multi-scale-dual-axis-v1")
        self.assertEqual(overview["scope"]["episode_phase"], "producing")
        deliverable_edges = {
            (edge["source_id"], edge["target_id"])
            for edge in overview["scope"]["deliverable_edges"]
        }
        self.assertIn(("D-AUDIO", "D-INTEGRATION"), deliverable_edges)
        self.assertIn(("D-VISUAL", "D-INTEGRATION"), deliverable_edges)

    def test_route_switch_rejects_deliverable_change_without_mutation(self):
        self.add_task(
            "T-TTS-SCRIPT",
            required_artifact_roles=["tts_script"],
        )
        store = self.data_root.episode_store("EP")
        before, version = store.get("task", "T-TTS-SCRIPT")
        denied = self.service.switch_route(
            "EP",
            "T-TTS-SCRIPT",
            "T-RECORDING",
            actor="supervisor",
            strategy="direct_recording",
            reason="Attempt to replace a script deliverable with audio",
            replacement_spec={
                "title": "Use direct recording",
                "goal": "Produce narration audio",
                "required_artifact_roles": ["narration_audio"],
            },
            request_id="deny-incompatible-route",
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["code"], "route_output_contract_incompatible")
        after, after_version = store.get("task", "T-TTS-SCRIPT")
        self.assertEqual(before, after)
        self.assertEqual(version, after_version)
        self.assertIsNone(store.get("task", "T-RECORDING")[0])

    def test_route_switch_revokes_live_owner_without_touching_sibling(self):
        self.add_task("T-LIVE")
        self.add_task("T-FREE")
        self.assertTrue(
            self.service.begin(
                "EP", "T-LIVE", actor="Ada", request_id="route-live-begin"
            )["ok"]
        )
        switched = self.service.switch_route(
            "EP",
            "T-LIVE",
            "T-LIVE-ALT",
            actor="supervisor",
            strategy="alternate_method",
            reason="The original production method is no longer available",
            replacement_spec={
                "title": "Alternate method",
                "goal": "Produce the same result through the alternate method",
                "references": ["guidance.md"],
            },
            request_id="route-live-switch",
        )
        self.assertTrue(switched["ok"], switched)
        store = self.data_root.episode_store("EP")
        lease, _ = store.get("lease", "lease:T-LIVE")
        sibling, _ = store.get("task", "T-FREE")
        self.assertEqual(lease["status"], "revoked")
        self.assertEqual(lease["release_reason"], "route_switch")
        self.assertEqual(sibling["status"], "planned")

    def test_route_switch_cancels_stale_deferred_return(self):
        self.add_task("T-OLD-ROUTE")
        self.assertTrue(
            self.service.begin(
                "EP", "T-OLD-ROUTE", actor="Ada", request_id="old-route-begin"
            )["ok"]
        )
        self.assertTrue(
            self.service.submit(
                "EP",
                "T-OLD-ROUTE",
                actor="Ada",
                artifacts=[{"role": "result", "path": "result.bin"}],
                request_id="old-route-submit",
            )["ok"]
        )
        context = self.service.review_context(
            "EP", "T-OLD-ROUTE", actor="Reviewer"
        )
        revised = self.service.review(
            "EP",
            "T-OLD-ROUTE",
            actor="Reviewer",
            verdict="revise",
            findings=[{"description": "The method cannot satisfy the source."}],
            review_context_hash=context["review_context_hash"],
            request_id="old-route-revise",
        )
        ticket_id = revised["return_ticket"]["return_ticket_id"]
        switched = self.service.switch_route(
            "EP",
            "T-OLD-ROUTE",
            "T-NEW-ROUTE",
            actor="supervisor",
            strategy="new_method",
            reason="Replace the failed method instead of returning obsolete rework",
            replacement_spec={
                "title": "New route",
                "goal": "Produce the same result through the replacement route",
                "references": ["guidance.md"],
            },
            request_id="cancel-return-with-route-switch",
        )
        self.assertTrue(switched["ok"], switched)
        self.assertEqual(switched["cancelled_return_tickets"], [ticket_id])
        ticket, _ = self.data_root.episode_store("EP").get(
            "return_ticket", ticket_id
        )
        self.assertEqual(ticket["status"], "cancelled")
        self.assertEqual(ticket["replacement_task_id"], "T-NEW-ROUTE")
        next_for_ada = self.service.next_action("EP", actor="Ada")
        self.assertEqual(next_for_ada["next"]["task"]["task_id"], "T-NEW-ROUTE")


if __name__ == "__main__":
    import unittest

    unittest.main()
