from __future__ import annotations

from pathlib import Path
import unittest


STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"


class HumanUIResilienceContractTests(unittest.TestCase):
    def test_detail_surfaces_are_not_registered_as_task_selectors(self) -> None:
        source = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("peek.dataset.detailTaskId", source)
        self.assertIn("dock.dataset.detailTaskId", source)
        self.assertIn("inspectorBody.dataset.detailTaskId", source)
        self.assertNotIn("peek.dataset.taskId", source)
        self.assertNotIn("dock.dataset.taskId", source)
        self.assertNotIn("inspectorBody.dataset.taskId", source)
        self.assertIn(
            'button.closest?.("#taskPeek, #mediaDock, #inspectorBody")',
            source,
        )

    def test_unrelated_deltas_do_not_replace_active_detail_dom(self) -> None:
        source = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("function taskDetailSignature(task)", source)
        self.assertIn("nextSignature !== state.peekSignature", source)
        self.assertIn("state.inspectorSignature === desiredSignature", source)
        self.assertIn("state.floatingMediaSignature === signature", source)

    def test_frontend_can_resume_without_resetting_persistent_backend(self) -> None:
        source = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
        markup = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("function guardedRender(scope, render)", source)
        self.assertIn("function recoverFrontend()", source)
        self.assertIn("lecture-supervision-last-episode", source)
        self.assertIn("scheduleFrontendResync", source)
        self.assertIn("function reconcileMissedDeltas()", source)
        self.assertIn("startDeltaWatchdog", source)
        self.assertIn("DELTA + VERIFY", source)
        self.assertIn('id="frontendFaultBanner"', markup)
        self.assertIn('id="frontendRecoverButton"', markup)

    def test_backend_outage_and_interface_fault_have_distinct_recovery_actions(self) -> None:
        source = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
        markup = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('connectionPhase: "connecting"', source)
        self.assertIn("function reconcileBackend(", source)
        self.assertIn("function runRecoveryAction()", source)
        self.assertIn('recoverButton.dataset.recoveryAction = "reconnect"', source)
        self.assertIn('recoverButton.dataset.recoveryAction = "reload"', source)
        self.assertIn('label.textContent = unreachable ? "BACKEND OFFLINE"', source)
        self.assertIn('recoverButton.textContent = "重试连接"', source)
        self.assertIn('recoverButton.textContent = "重载界面"', source)
        self.assertIn("当前无法确认 Agent 是否仍在运行", source)
        self.assertNotIn("后端状态与 Agent 运行不受影响", source)
        self.assertIn('id="frontendFaultLabel"', markup)
        self.assertNotIn("只重启界面", markup)

    def test_successful_reconnect_clears_all_backend_faults_after_full_reload(self) -> None:
        source = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

        reconcile_start = source.index("async function reconcileBackend(")
        reconcile_end = source.index("async function recoverFrontend()", reconcile_start)
        reconcile_source = source[reconcile_start:reconcile_end]
        self.assertIn("await loadEpisodes()", reconcile_source)
        self.assertIn("clearBackendFaults()", reconcile_source)
        self.assertIn('setConnectionPhase("synced")', reconcile_source)
        self.assertIn("state.lastSuccessfulReconcileAt", reconcile_source)
        self.assertIn('scheduleFrontendResync(0)', source)

    def test_recovery_requires_plain_language_preview_before_apply(self) -> None:
        source = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
        markup = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("function openRepairPreview()", source)
        self.assertIn('id="repairPreviewDialog"', markup)
        self.assertIn('id="repairPreviewApply"', markup)
        self.assertIn("扫描和核验都只读", markup)
        self.assertNotIn("window.confirm(`将应用", source)

    def test_terminal_overview_excludes_retired_routes_from_progress(self) -> None:
        source = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("本轮完成", source)
        self.assertIn("当前路线完成", source)
        self.assertIn('["cancelled", "superseded"].includes(status)', source)

    def test_production_home_keeps_the_live_graph_as_its_primary_surface(self) -> None:
        markup = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")

        production_start = markup.index('id="productionView"')
        flow_start = markup.index('id="flowView"')
        execution_map = markup.index('id="executionMap"')
        production_markup = markup[production_start:flow_start]
        self.assertLess(production_start, execution_map)
        self.assertLess(execution_map, flow_start)
        self.assertIn('id="attentionButton"', markup)
        self.assertIn('id="attentionProgress"', markup)
        self.assertIn('id="systemHealth"', markup)
        self.assertIn('id="homeFlowTitle" class="sr-only">生产图', markup)
        self.assertIn("文字工作列表", markup)
        self.assertNotIn('class="episode-overview"', markup)
        self.assertNotIn("不想找入口时，直接告诉主 Agent", markup)
        self.assertNotIn("需要逐项浏览时再展开", production_markup)
        self.assertNotIn("<em>展开</em>", production_markup)
        self.assertNotIn("LIVE PRODUCTION MAP", production_markup)
        self.assertNotIn("地图动效图例", production_markup)

    def test_attention_reminder_and_node_share_one_focus_path(self) -> None:
        source = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("function humanAttentionTasks()", source)
        self.assertIn("function renderHeaderAttention()", source)
        self.assertIn("function focusTaskOnHome(taskId)", source)
        self.assertIn("function bindFocusTaskSelectors()", source)
        self.assertIn('data-focus-task-id=', source)
        self.assertIn("focusTaskOnHome(task.task_id)", source)
        self.assertIn("forecast-attention-badge", source)
        self.assertIn("node-attention-badge", source)

    def test_contract_conflicts_are_first_class_human_decisions(self) -> None:
        source = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("function humanDecisionGaps(taskOrId)", source)
        self.assertIn("function taskHumanAttentionCount(task)", source)
        self.assertIn('gap.kind === "contradictory_requirements"', source)
        self.assertIn("data-resolve-gap-form", source)
        self.assertIn('sendCommand("gap.resolve"', source)
        self.assertIn("提交裁决并恢复流程", source)

    def test_motion_has_distinct_work_transition_and_human_attention_semantics(self) -> None:
        source = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
        styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

        self.assertIn('const consumesInput = task.status === "working"', source)
        self.assertIn("forecast-edge-active", source)
        self.assertIn("forecast-edge-signal", source)
        self.assertIn("state.flow.transitionTaskIds", source)
        self.assertIn("@keyframes forecast-flow", styles)
        self.assertIn("@keyframes forecast-signal", styles)
        self.assertIn("@media (prefers-reduced-motion: reduce)", styles)

    def test_submitted_detail_drafts_clear_before_live_rerender(self) -> None:
        source = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("function stageDetailFormSubmission(form, draftKey)", source)
        self.assertIn("form?.reset()", source)
        self.assertIn("snapshot.focus = null", source)
        media_submit = source.index("const payload = mediaAnnotationPayload(card)")
        media_send = source.index('await sendCommand("annotate", payload)', media_submit)
        self.assertLess(
            source.index("stageDetailFormSubmission(form, draftKey)", media_submit),
            media_send,
        )
        task_submit = source.index("const payload = {", media_send)
        task_send = source.index('await sendCommand("annotate", payload)', task_submit)
        self.assertLess(
            source.index("stageDetailFormSubmission(form, draftKey)", task_submit),
            task_send,
        )

    def test_active_lease_owner_is_not_duplicated_as_a_planned_assignment(self) -> None:
        source = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("const leasedOwners = new Set()", source)
        self.assertIn("leasedOwners.add(lease.owner)", source)
        self.assertIn(
            "if (leasedOwners.has(agent.agent_id) || reservedOwners.has(agent.agent_id)) return",
            source,
        )
        self.assertIn("reservation.reserved_for} · 预留", source)


if __name__ == "__main__":
    unittest.main()
