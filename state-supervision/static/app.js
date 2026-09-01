const state = {
  episodes: [],
  episodeId: null,
  overview: null,
  next: null,
  scan: null,
  events: [],
  cursor: 0,
  selectedTaskId: null,
  detailMode: (() => {
    try { return localStorage.getItem("lecture-supervision-detail-mode") === "sidebar" ? "sidebar" : "peek"; }
    catch { return "peek"; }
  })(),
  peekAnchor: null,
  peekScope: "body",
  mediaDraftEpisode: null,
  mediaDrafts: [],
  detailDraftEpisode: null,
  detailDrafts: {},
  detailUiState: {},
  stream: null,
  refreshTimer: null,
  deltaWatchdogTimer: null,
  deltaWatchdogBusy: false,
  resyncTimer: null,
  resyncDelay: 1200,
  recoveryBusy: false,
  connectionPhase: "connecting",
  lastSuccessfulReconcileAt: null,
  uiFaults: new Map(),
  capsules: {},
  capsuleErrors: {},
  capsuleLoading: new Set(),
  expandedCapsules: new Set(),
  contextPreviews: {},
  contextPreviewErrors: {},
  contextPreviewLoading: new Set(),
  expandedContextTasks: new Set(),
  contextViewByTask: {},
  structureAxis: "content",
  agentDataMode: "next",
  agentDataAfter: 0,
  flow: {
    mode: "task",
    filter: "frontier",
    presentation: "layered",
    topologyExpanded: false,
    forecastZoom: 1.2,
    forecastAutoFit: false,
    transform: { x: 32, y: 32, k: 1 },
    layout: null,
    fittedEpisode: null,
    expandedForecastTaskIds: new Set(),
    transitionTaskIds: new Set(),
    transitionTimer: null,
  },
  floatingArtifactId: null,
  floatingMediaSignature: null,
  peekSignature: null,
  inspectorSignature: null,
  peekGeometry: null,
};

const FLOW_ZOOM_MIN = 0.08;
const FLOW_ZOOM_MAX = 3.2;
const FLOW_ZOOM_STEP = 1.2;
const FORECAST_ZOOM_MIN = 0.08;
const FORECAST_ZOOM_MAX = 3.2;
const FORECAST_ZOOM_STEP = 1.2;

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
let drawerReturnFocus = null;
let taskPeekReturnFocus = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
  } catch (error) {
    error.backendUnreachable = true;
    throw error;
  }
  const body = await response.json();
  if (!response.ok || body.ok === false) {
    const error = new Error(body.message || `${response.status} ${response.statusText}`);
    error.payload = body;
    error.backendResponseError = true;
    throw error;
  }
  return body;
}

function toast(message, type = "success") {
  const item = document.createElement("div");
  item.className = `toast ${type}`;
  item.textContent = message;
  $("#toastRegion").append(item);
  setTimeout(() => item.remove(), 4200);
}

function faultKind(scope, error, explicitKind = null) {
  if (explicitKind) return explicitKind;
  if (error?.backendUnreachable) return "backend_unreachable";
  if (error?.backendResponseError || ["后端连接", "后端同步", "增量校验", "实时连接", "初始加载"].includes(scope)) {
    return "backend_response";
  }
  return "interface";
}

function backendFaultEntries() {
  return [...state.uiFaults.entries()].filter(([, fault]) => String(fault?.kind || "").startsWith("backend_"));
}

function setConnectionPhase(phase) {
  state.connectionPhase = phase;
  const status = $("#streamStatus");
  if (!status) return;
  const label = status.querySelector("span");
  if (phase === "synced") {
    status.className = "live-state live";
    label.textContent = "同步";
  } else if (phase === "offline") {
    status.className = "live-state offline";
    label.textContent = "后端离线";
  } else if (phase === "reconciling") {
    status.className = "live-state reconnecting";
    label.textContent = "对账";
  } else {
    status.className = "live-state reconnecting";
    label.textContent = phase === "reconnecting" ? "重连" : "连接";
  }
}

function renderFrontendFaults() {
  const banner = $("#frontendFaultBanner");
  const summary = $("#frontendFaultSummary");
  const label = $("#frontendFaultLabel");
  const recoverButton = $("#frontendRecoverButton");
  if (!banner || !summary || !label || !recoverButton) return;
  const faults = [...state.uiFaults.entries()];
  banner.classList.toggle("hidden", faults.length === 0);
  if (!faults.length) return;
  const backendFaults = backendFaultEntries();
  const unreachable = backendFaults.some(([, fault]) => fault.kind === "backend_unreachable");
  recoverButton.disabled = state.recoveryBusy;
  if (backendFaults.length || state.recoveryBusy) {
    recoverButton.dataset.recoveryAction = "reconnect";
    if (state.recoveryBusy) {
      label.textContent = "RECONCILING";
      summary.textContent = "后端已经响应或正在重试；正在重新读取分集、任务、风险与事件游标。";
      recoverButton.textContent = "正在对账…";
      return;
    }
    const first = backendFaults[0]?.[1];
    label.textContent = unreachable ? "BACKEND OFFLINE" : "BACKEND RESPONSE ERROR";
    summary.textContent = unreachable
      ? "暂时无法连接后端；页面保留最后一次确认的状态，当前无法确认 Agent 是否仍在运行。请启动服务后重试连接。"
      : `后端已响应，但状态对账失败：${first?.message || "未知错误"}。页面保留最后一次确认的状态。`;
    recoverButton.textContent = "重试连接";
    return;
  }
  const labels = faults.slice(0, 2).map(([scope, fault]) => `${scope}: ${fault.message}`);
  label.textContent = "INTERFACE DEGRADED";
  summary.textContent = `${labels.join("；")}${faults.length > 2 ? `；另有 ${faults.length - 2} 项` : ""}。可重载当前界面；该操作不会重置后端状态。`;
  recoverButton.dataset.recoveryAction = "reload";
  recoverButton.textContent = "重载界面";
}

function reportFrontendFault(scope, error, options = {}) {
  const message = error?.message || String(error || "未知界面错误");
  const kind = faultKind(scope, error, options.kind);
  state.uiFaults.set(scope, { message, kind, observedAt: new Date().toISOString() });
  if (kind === "backend_unreachable") setConnectionPhase("offline");
  console.error(`[frontend:${scope}]`, error);
  renderFrontendFaults();
}

function clearFrontendFault(scope) {
  if (!state.uiFaults.delete(scope)) return;
  renderFrontendFaults();
}

function clearBackendFaults() {
  let changed = false;
  [...state.uiFaults.entries()].forEach(([scope, fault]) => {
    if (!String(fault?.kind || "").startsWith("backend_")) return;
    state.uiFaults.delete(scope);
    changed = true;
  });
  if (changed) renderFrontendFaults();
}

function guardedRender(scope, render) {
  try {
    render();
    clearFrontendFault(scope);
  } catch (error) {
    reportFrontendFault(scope, error);
  }
}

function statusLabel(status) {
  return {
    planned: "待执行",
    rework: "返工",
    working: "进行中",
    candidate: "待独立审查",
    user_review_pending: "待用户审片",
    approved: "已批准",
    blocked: "阻塞",
    cancelled: "已取消",
    superseded: "已替代",
  }[status] || status || "未知";
}

function actionLabel(action) {
  return {
    work: "开始任务",
    continue: "继续当前任务",
    reclaim: "恢复中断任务",
    return_rework: "领取延迟返修",
    gate: "运行硬门禁",
    review: "独立审查",
    human_review: "用户审片",
  }[action] || action;
}

function taskStatusLabel(task) {
  if (task.status === "candidate" && task.derived?.missing_validators?.length) return "等待硬门禁";
  return task.derived?.effective_state === "waiting" ? "等待依赖" : statusLabel(task.status);
}

function humanDecisionGaps(taskOrId) {
  const taskId = typeof taskOrId === "string" ? taskOrId : taskOrId?.task_id;
  return (state.overview?.gaps || []).filter((gap) =>
    gap.task_id === taskId
    && gap.status === "open"
    && (gap.requires_human || gap.kind === "contradictory_requirements")
  );
}

function taskHumanAttentionCount(task) {
  return Number(task?.status === "user_review_pending") + humanDecisionGaps(task).length;
}

function humanAttentionTasks() {
  return (state.overview?.tasks || [])
    .filter((task) => taskHumanAttentionCount(task) > 0)
    .sort((a, b) => Number(Boolean(b.critical_path)) - Number(Boolean(a.critical_path))
      || Number(b.priority || 0) - Number(a.priority || 0)
      || String(a.task_id).localeCompare(String(b.task_id)));
}

function episodePhaseLabel(phase) {
  return {
    initialized: "已初始化",
    planning: "规划中",
    producing: "制作中",
    producing_attention: "制作中 · 有待处理事项",
    reviewing: "审查中",
    user_review_pending: "等待你的审片",
    complete: "本轮完成",
    settled: "本轮完成",
  }[phase] || String(phase || "运行中").replaceAll("_", " ");
}

function taskCapsuleHash(task) {
  return task?.active_capsule_hash || task?.candidate?.capsule_hash || null;
}

function capsuleJson(value) {
  return escapeHtml(JSON.stringify(value ?? null, null, 2));
}

function contextClassLabel(value) {
  return {
    stable_rule: "稳定规则",
    task_template: "任务模板",
    episode_material: "本集材料",
    temporary_override: "临时变更",
    runtime_fact: "运行时事实",
  }[value] || value || "未分类";
}

function contextPayloadMarkup(record, { preview = false } = {}) {
  const payload = record?.payload || {};
  const task = payload.task || {};
  const budget = payload.context_budget || {};
  const manifest = payload.context_manifest || {};
  const blocks = payload.context_blocks || [];
  const references = payload.required_references || [];
  const feedback = payload.relevant_feedback || [];
  const counts = manifest.class_counts || {};
  const countItems = ["stable_rule", "task_template", "episode_material", "temporary_override", "runtime_fact"]
    .filter((key) => Number(counts[key] || 0) > 0)
    .map((key) => `<span class="context-count ${escapeHtml(key)}"><b>${counts[key]}</b>${contextClassLabel(key)}</span>`)
    .join("");
  const blockMarkup = blocks.map((block) => {
    const isBrief = block.content_mode === "brief";
    const displayMode = isBrief
      ? `摘要 ${Number(block.excerpt_chars || 0).toLocaleString()} / ${Number(block.original_chars || 0).toLocaleString()} 字`
      : `全文 · 版本 ${block.version || "1"}`;
    const briefNotice = isBrief ? `<div class="context-brief-note">
          <div><strong>长引用已折叠为确定性简报</strong><span>省略 ${Number(block.omitted_chars || 0).toLocaleString()} 字 · 需要完整约束时读取原文件</span></div>
          <p>${escapeHtml(block.rough_summary || "已保留文档结构与开头节选。")}</p>
          <code>${escapeHtml(block.source?.path || "原文件路径未记录")}</code>
        </div>` : "";
    return `<details class="context-block ${escapeHtml(block.context_class)} ${isBrief ? "brief" : "full"}">
      <summary><span class="context-block-kind">${escapeHtml(contextClassLabel(block.context_class))}</span><strong>${escapeHtml(block.label || block.block_id)}</strong><b>${escapeHtml(displayMode)}</b></summary>
      <div class="context-block-body">
        <dl><dt>原文件</dt><dd>${escapeHtml(block.source?.path || block.source?.id || block.source?.kind || "runtime")}</dd><dt>作用域</dt><dd>${escapeHtml(block.scope || "task")}</dd><dt>装配</dt><dd>${escapeHtml(block.assembly_mode || "append")} → ${escapeHtml(block.slot || "default")}</dd><dt>投递</dt><dd>${escapeHtml(block.delivery_policy || "on_begin")}</dd><dt>维护方式</dt><dd>${block.mutable === false ? "只读 · 需重绑定升级" : "显式版本变更"}</dd>${block.source?.service_binding ? `<dt>绑定服务</dt><dd>${escapeHtml(block.source.service_binding)}</dd>` : ""}</dl>
        ${block.supersedes?.length ? `<p class="context-supersedes">替代 ${escapeHtml(block.supersedes.join(", "))}</p>` : ""}
        ${briefNotice}
        <pre>${escapeHtml(block.content || "")}</pre>
      </div>
    </details>`;
  }).join("");
  return `<div class="capsule-exact context-exact">
    <div class="context-mode-note"><strong>${preview ? "领取前精确预览" : "实际签发快照"}</strong><span>${preview ? "不授予租约，不改变状态" : "不可变，可复现 Agent 当时所见"}</span></div>
    <div class="capsule-facts">
      <div><span>${preview ? "预览" : "胶囊"}</span><b>${escapeHtml(record.capsule_id || record.capsule_hash?.slice(0, 12) || "未签发")}</b></div>
      <div><span>任务版本</span><b>v${escapeHtml(payload.task_version ?? record.task_version ?? "-")}</b></div>
      <div><span>投喂规模</span><b>${escapeHtml(budget.used_chars ?? 0)} chars / ${escapeHtml(budget.used_files ?? 0)} refs${budget.brief_references ? ` · ${escapeHtml(budget.brief_references)} 摘要` : ""}</b></div>
      <div><span>状态游标</span><b>#${escapeHtml(payload.state_cursor ?? record.created_seq ?? "-")}</b></div>
    </div>
    ${countItems ? `<div class="context-counts">${countItems}</div>` : ""}
    ${manifest.conflict_count ? `<div class="context-conflict"><strong>${manifest.conflict_count} 个装配冲突</strong><pre>${capsuleJson(manifest.conflicts || [])}</pre></div>` : ""}
    <details class="assembled-prompt"><summary><span>Agent 将收到的完整正文</span><b>${escapeHtml((payload.assembled_prompt || "").length)} chars · 展开查看</b></summary><pre>${escapeHtml(payload.assembled_prompt || "尚未生成组合正文。")}</pre></details>
    <section class="context-block-list"><h4>上下文来源 <span>${blocks.length}</span></h4>${blockMarkup || `<p class="capsule-empty">旧版胶囊未记录分层来源。</p>`}</section>
    <section class="capsule-section"><h4>本步合同</h4><dl><dt>目标</dt><dd>${escapeHtml(task.goal || "-")}</dd><dt>输出</dt><dd><pre>${capsuleJson(task.output_contract || {})}</pre></dd><dt>停止条件</dt><dd>${escapeHtml((task.stop_conditions || []).join("；") || "-")}</dd></dl></section>
    ${!blocks.length ? `<section class="capsule-section"><h4>精确规则与输入 <span>${references.length}</span></h4>${references.map((reference, index) => `<details class="capsule-reference"><summary>${index + 1}. ${escapeHtml(reference.path || "reference")}</summary><div><p>${escapeHtml(reference.sha256 ? `SHA256 ${reference.sha256}` : "")}</p><pre>${escapeHtml(reference.content || "")}</pre></div></details>`).join("") || `<p class="capsule-empty">本步没有绑定文件。</p>`}</section>` : ""}
    ${!blocks.length ? `<section class="capsule-section"><h4>适用反馈与变更 <span>${feedback.length + (payload.open_changes || []).length}</span></h4>${feedback.map((item) => `<div class="capsule-feedback"><b>${escapeHtml(item.feedback_id || item.pattern_key || "feedback")}</b><p>${escapeHtml(item.instruction || item.body || JSON.stringify(item))}</p></div>`).join("") || `<p class="capsule-empty">没有额外反馈或变更。</p>`}</section>` : ""}
    <details class="capsule-raw"><summary>完整胶囊 JSON</summary><pre>${capsuleJson(payload)}</pre></details>
  </div>`;
}

function capsuleBodyMarkup(capsuleHash) {
  if (!capsuleHash) return `<div class="capsule-empty">任务领取后才会签发精确上下文。</div>`;
  if (state.capsuleLoading.has(capsuleHash)) return `<div class="capsule-loading">正在按需读取精确投喂内容…</div>`;
  if (state.capsuleErrors[capsuleHash]) return `<div class="capsule-error">读取失败：${escapeHtml(state.capsuleErrors[capsuleHash])}</div>`;
  const record = state.capsules[capsuleHash];
  if (!record) return `<div class="capsule-empty">展开后才读取；关闭时不占用页面信息密度。</div>`;
  return contextPayloadMarkup(record);
}

function capsuleDisclosureMarkup(capsuleHash, variant = "station") {
  if (!capsuleHash) return "";
  const open = state.expandedCapsules.has(capsuleHash) ? "open" : "";
  return `<details class="context-disclosure ${variant}-context" data-capsule-hash="${escapeHtml(capsuleHash)}" ${open}><summary><span>精确上下文投喂</span><b>${escapeHtml(capsuleHash.slice(0, 12))}</b></summary><div class="capsule-body">${capsuleBodyMarkup(capsuleHash)}</div></details>`;
}

function refreshCapsuleBodies(capsuleHash) {
  $$(`.context-disclosure[data-capsule-hash="${CSS.escape(capsuleHash)}"] .capsule-body`).forEach((body) => {
    body.innerHTML = capsuleBodyMarkup(capsuleHash);
  });
}

async function loadCapsule(capsuleHash) {
  if (!capsuleHash || state.capsules[capsuleHash] || state.capsuleLoading.has(capsuleHash)) return;
  state.capsuleLoading.add(capsuleHash);
  delete state.capsuleErrors[capsuleHash];
  refreshCapsuleBodies(capsuleHash);
  try {
    const result = await api(`/api/episodes/${encodeURIComponent(state.episodeId)}/capsules/${encodeURIComponent(capsuleHash)}`);
    state.capsules[capsuleHash] = result.capsule;
  } catch (error) {
    state.capsuleErrors[capsuleHash] = error.message;
  } finally {
    state.capsuleLoading.delete(capsuleHash);
    refreshCapsuleBodies(capsuleHash);
  }
}

function bindCapsuleDisclosures(root) {
  root?.querySelectorAll(".context-disclosure[data-capsule-hash]").forEach((details) => {
    const capsuleHash = details.dataset.capsuleHash;
    if (details.open) loadCapsule(capsuleHash);
    details.addEventListener("toggle", () => {
      if (details.open) {
        state.expandedCapsules.add(capsuleHash);
        loadCapsule(capsuleHash);
      } else {
        state.expandedCapsules.delete(capsuleHash);
      }
    });
  });
}

function contextDiffMarkup(diff) {
  const summary = diff?.summary || {};
  const changed = diff?.changed || [];
  const added = diff?.added || [];
  const removed = diff?.removed || [];
  return `<div class="context-diff">
    <div class="context-diff-summary"><span><b>${summary.added || 0}</b>新增</span><span><b>${summary.changed || 0}</b>变化</span><span><b>${summary.removed || 0}</b>移除</span><span><b>${summary.unchanged || 0}</b>未变</span></div>
    ${added.map((item) => `<div class="diff-row added"><b>新增</b><span>${escapeHtml(item.label || item.block_id)}</span></div>`).join("")}
    ${changed.map((item) => `<details class="diff-row changed"><summary><b>变化</b><span>${escapeHtml(item.after?.label || item.block_id)}</span></summary><div class="diff-columns"><pre>${escapeHtml(item.before?.content || "")}</pre><pre>${escapeHtml(item.after?.content || "")}</pre></div></details>`).join("")}
    ${removed.map((item) => `<div class="diff-row removed"><b>移除</b><span>${escapeHtml(item.label || item.block_id)}</span></div>`).join("")}
    ${!added.length && !changed.length && !removed.length ? `<p class="capsule-empty">预览与最近签发快照的内容块一致。</p>` : ""}
  </div>`;
}

function contextWorkspaceBodyMarkup(taskId) {
  if (state.contextPreviewLoading.has(taskId) && !state.contextPreviews[taskId]) return `<div class="capsule-loading">正在编译领取前精确预览…</div>`;
  if (state.contextPreviewErrors[taskId]) return `<div class="capsule-error">预览失败：${escapeHtml(state.contextPreviewErrors[taskId])}</div>`;
  const result = state.contextPreviews[taskId];
  if (!result) return `<div class="capsule-empty">展开后按需编译，不授予租约，也不改变任务状态。</div>`;
  const refreshing = state.contextPreviewLoading.has(taskId) ? `<div class="capsule-refreshing">状态已变化，正在增量校准预览；旧内容暂留以保护阅读位置。</div>` : "";
  const mode = state.contextViewByTask[taskId] || "preview";
  const issued = result.issued;
  const body = mode === "issued"
    ? (issued ? contextPayloadMarkup(issued) : `<div class="capsule-empty">这个任务尚未签发上下文。领取后会保留不可变快照。</div>`)
    : mode === "diff"
      ? contextDiffMarkup(result.diff)
      : contextPayloadMarkup({ ...result.preview, capsule_id: "PREVIEW" }, { preview: true });
  const task = (state.overview?.tasks || []).find((item) => item.task_id === taskId) || {};
  const replaceSlots = (result.preview?.payload?.context_blocks || [])
    .filter((item) => item.context_class !== "runtime_fact")
    .map((item) => `<option value="${escapeHtml(item.slot)}">${escapeHtml(item.slot)} · ${escapeHtml(item.label)}</option>`)
    .join("");
  return `<div class="context-workbench">${refreshing}
    <div class="context-view-tabs" role="tablist" aria-label="上下文查看方式">
      <button type="button" data-context-view="preview" class="${mode === "preview" ? "active" : ""}">领取前预览</button>
      <button type="button" data-context-view="issued" class="${mode === "issued" ? "active" : ""}">实际签发${issued ? "" : "（无）"}</button>
      <button type="button" data-context-view="diff" class="${mode === "diff" ? "active" : ""}">版本差异</button>
    </div>
    <div class="context-view-body">${body}</div>
    <details class="context-override-editor">
      <summary><span>新增临时要求或替换块</span><b>不会修改稳定规则</b></summary>
      <form data-context-override-form="${escapeHtml(taskId)}">
        <label>要求正文<textarea name="instruction" required placeholder="写清 Agent 需要新增或改写的要求"></textarea></label>
        <div class="context-form-grid">
          <label>生效范围<select name="scope"><option value="task">当前任务</option><option value="attempt">本次尝试</option><option value="content_unit">当前内容单元</option><option value="episode">本集</option></select></label>
          <label>装配方式<select name="assembly_mode"><option value="append">追加</option><option value="replace">完整替换指定块</option></select></label>
          <label>投递时机<select name="delivery_policy"><option value="attention_boundary">下个注意力边界</option><option value="next_attempt">下次领取</option><option value="immediate">立即中断并重领</option></select></label>
          <label>目标槽位<select name="context_slot"><option value="temporary.instructions">临时要求</option>${replaceSlots}</select></label>
        </div>
        <div class="context-editor-foot"><span>${task.status === "working" ? "任务进行中，默认在下一次心跳边界投递。" : "任务未领取，保存后会进入下一份预览。"}</span><button class="secondary-button" type="submit">保存上下文变更</button></div>
      </form>
    </details>
  </div>`;
}

function contextWorkspaceMarkup(task) {
  const open = state.expandedContextTasks.has(task.task_id) ? "open" : "";
  const issued = taskCapsuleHash(task);
  const overrideCount = (state.overview?.context_overrides || []).filter((item) => item.status === "active" && (item.task_id === task.task_id || item.scope === "episode" || (item.scope === "content_unit" && item.content_unit_id === task.content_unit_id))).length;
  const label = issued ? `已签发 / ${overrideCount} 临时` : `可预览 / ${overrideCount} 临时`;
  return `<details class="context-disclosure context-workspace inspector-context" data-context-task-id="${escapeHtml(task.task_id)}" ${open}><summary><span>本次上下文</span><b>${escapeHtml(label)}</b></summary><div class="context-workspace-body">${contextWorkspaceBodyMarkup(task.task_id)}</div></details>`;
}

function refreshContextWorkspace(taskId) {
  $$(`.context-workspace[data-context-task-id="${CSS.escape(taskId)}"] .context-workspace-body`).forEach((body) => {
    body.innerHTML = contextWorkspaceBodyMarkup(taskId);
    bindContextWorkbench(body, taskId);
  });
}

async function loadContextPreview(taskId, force = false) {
  if (!taskId || state.contextPreviewLoading.has(taskId) || (!force && state.contextPreviews[taskId])) return;
  state.contextPreviewLoading.add(taskId);
  delete state.contextPreviewErrors[taskId];
  refreshContextWorkspace(taskId);
  try {
    state.contextPreviews[taskId] = await api(`/api/episodes/${encodeURIComponent(state.episodeId)}/context-preview/${encodeURIComponent(taskId)}?actor=human-ui`);
  } catch (error) {
    state.contextPreviewErrors[taskId] = error.message;
  } finally {
    state.contextPreviewLoading.delete(taskId);
    refreshContextWorkspace(taskId);
  }
}

function bindContextWorkbench(root, taskId) {
  root?.querySelectorAll("[data-context-view]").forEach((button) => {
    button.onclick = () => {
      state.contextViewByTask[taskId] = button.dataset.contextView;
      refreshContextWorkspace(taskId);
    };
  });
  const form = root?.querySelector(`[data-context-override-form="${CSS.escape(taskId)}"]`);
  if (form) form.onsubmit = async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    await sendCommand("context.override", {
      task_id: taskId,
      instruction: String(data.get("instruction") || "").trim(),
      label: "临时要求",
      scope: data.get("scope"),
      assembly_mode: data.get("assembly_mode"),
      delivery_policy: data.get("delivery_policy"),
      context_slot: data.get("context_slot"),
    });
    delete state.contextPreviews[taskId];
    await loadContextPreview(taskId, true);
  };
}

function bindContextWorkspaces(root) {
  root?.querySelectorAll(".context-workspace[data-context-task-id]").forEach((details) => {
    const taskId = details.dataset.contextTaskId;
    if (details.open) loadContextPreview(taskId);
    details.addEventListener("toggle", () => {
      if (details.open) {
        state.expandedContextTasks.add(taskId);
        loadContextPreview(taskId);
      } else {
        state.expandedContextTasks.delete(taskId);
      }
    });
    bindContextWorkbench(details, taskId);
  });
}

async function loadEpisodes() {
  const result = await api("/api/episodes");
  state.episodes = result.episodes;
  const select = $("#episodeSelect");
  select.innerHTML = state.episodes
    .map((episode) => `<option value="${escapeHtml(episode.episode_id)}">${escapeHtml(episode.title)} · ${escapeHtml(episode.episode_id)}</option>`)
    .join("");
  if (!state.episodes.length) {
    $("#emptyState").classList.remove("hidden");
    $("#workspace").classList.add("hidden");
    return;
  }
  $("#emptyState").classList.add("hidden");
  $("#workspace").classList.remove("hidden");
  if (!state.episodeId) {
    try {
      const savedEpisodeId = localStorage.getItem("lecture-supervision-last-episode");
      if (savedEpisodeId && state.episodes.some((item) => item.episode_id === savedEpisodeId)) state.episodeId = savedEpisodeId;
    } catch { /* resume from the first episode when storage is unavailable */ }
  }
  if (!state.episodeId || !state.episodes.some((item) => item.episode_id === state.episodeId)) {
    state.episodeId = state.episodes[0].episode_id;
  }
  try { localStorage.setItem("lecture-supervision-last-episode", state.episodeId); } catch { /* selection remains session-local */ }
  select.value = state.episodeId;
  await loadEpisode();
}

async function loadEpisode({ preserveEvents = false } = {}) {
  if (!state.episodeId) return;
  const previousOverviewCursor = state.overview?.cursor;
  const [overviewResult, nextResult, scanResult] = await Promise.all([
    api(`/api/episodes/${encodeURIComponent(state.episodeId)}/overview`),
    api(`/api/episodes/${encodeURIComponent(state.episodeId)}/next?actor=human-ui&role=human`),
    api(`/api/episodes/${encodeURIComponent(state.episodeId)}/scan`),
  ]);
  const previousTasks = Object.fromEntries((state.overview?.tasks || []).map((task) => [task.task_id, task]));
  const nextOverview = overviewResult.overview;
  const transitionTaskIds = new Set();
  if (state.overview) {
    (nextOverview.tasks || []).forEach((task) => {
      const previous = previousTasks[task.task_id];
      if (!previous || previous.status !== task.status || previous.active_lease_generation !== task.active_lease_generation) {
        transitionTaskIds.add(task.task_id);
      }
    });
  }
  state.overview = nextOverview;
  if (transitionTaskIds.size) {
    state.flow.transitionTaskIds = transitionTaskIds;
    clearTimeout(state.flow.transitionTimer);
    state.flow.transitionTimer = setTimeout(() => {
      state.flow.transitionTaskIds.clear();
      document.querySelectorAll(".flow-edge-signal, .forecast-edge-signal").forEach((element) => element.remove());
      document.querySelectorAll(".state-transition, .forecast-node.recent").forEach((element) => element.classList.remove("state-transition", "recent"));
    }, 1800);
  }
  state.next = nextResult;
  state.scan = scanResult;
  state.cursor = Math.max(state.cursor, state.overview.cursor || 0);
  const contextTasksToRefresh = previousOverviewCursor !== undefined && previousOverviewCursor !== state.overview.cursor
    ? [...state.expandedContextTasks]
    : [];
  if (!preserveEvents) {
    const eventResult = await api(`/api/episodes/${encodeURIComponent(state.episodeId)}/events?after=0&limit=500`);
    state.events = eventResult.events;
    state.cursor = Math.max(state.cursor, eventResult.cursor || 0);
    if (!state.agentDataAfter) state.agentDataAfter = Math.max(0, state.cursor - 20);
  }
  renderAll();
  contextTasksToRefresh.forEach((taskId) => loadContextPreview(taskId, true));
  connectStream();
}

function renderAll() {
  if (!state.overview) return;
  guardedRender("顶栏状态", () => {
    const episode = state.overview.episode || {};
    $("#cursorValue").textContent = state.cursor;
    $("#episodeMission").textContent = episode.mission || "尚未记录分集任务。";
    const health = state.overview.health || "unknown";
    const systemHealth = $("#systemHealth");
    systemHealth.textContent = { attention: "需检查", degraded: "已降级" }[health] || "状态未知";
    systemHealth.className = `system-health ${health}${health === "healthy" ? " hidden" : ""}`;
    const workflowAttention = (state.overview.gaps || []).filter((item) => item.status === "open").length
      + (state.overview.changes || []).filter((item) => item.status !== "resolved").length;
    $("#riskBadge").textContent = (state.scan?.repairable_count || 0) + workflowAttention;
  });
  [
    ["范围树", renderHierarchy],
    ["人工提醒", renderHeaderAttention],
    ["当前动作", renderNext],
    ["生产指标", renderMetrics],
    ["任务工作面", renderBoard],
    ["风险面板", renderRisk],
    ["事件流", renderEvents],
    ["流程拓扑", renderFlow],
    ["Agent 工位", renderWorkstations],
    ["Agent 数据", renderTopology],
    ["任务详情", renderInspector],
    ["详情模式", renderDetailModeToggle],
  ].forEach(([scope, render]) => guardedRender(scope, render));
  guardedRender("任务气泡", () => {
    if (effectiveDetailMode() === "peek" && !$("#taskPeek")?.classList.contains("hidden") && state.selectedTaskId && state.peekAnchor) {
      const currentAnchor = currentTaskAnchor(state.selectedTaskId, state.peekScope, state.peekAnchor);
      if (currentAnchor) {
        const rect = currentAnchor.rect;
        state.peekAnchor = { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: rect.width, height: rect.height };
        taskPeekReturnFocus = currentAnchor.element;
      }
      const selectedTask = (state.overview.tasks || []).find((item) => item.task_id === state.selectedTaskId);
      const nextSignature = taskDetailSignature(selectedTask);
      if (nextSignature !== state.peekSignature) {
        renderTaskPeek(state.selectedTaskId, state.peekAnchor, { focus: false });
      }
    }
  });
  guardedRender("浮动审片", refreshFloatingMedia);
}

function renderHeaderAttention() {
  const button = $("#attentionButton");
  const label = $("#attentionLabel");
  const progress = $("#attentionProgress");
  const count = $("#attentionCount");
  if (!button || !label || !progress || !count) return;
  const tasks = humanAttentionTasks();
  const active = tasks.length > 0;
  const counts = state.overview?.counts || {};
  const activeTotal = Object.entries(counts)
    .filter(([status]) => !["cancelled", "superseded"].includes(status))
    .reduce((sum, [, value]) => sum + Number(value || 0), 0);
  const approved = Number(counts.approved || 0);
  const phase = state.overview?.scope?.episode_phase || "initialized";
  const complete = activeTotal > 0 && approved === activeTotal;
  button.classList.toggle("attention", active);
  button.classList.toggle("complete", !active && complete);
  label.textContent = active ? "待处理" : complete ? "已完成" : episodePhaseLabel(phase);
  progress.textContent = activeTotal ? `${approved}/${activeTotal}` : "—";
  count.textContent = tasks.length;
  count.classList.toggle("hidden", !active);
  button.setAttribute("aria-label", active
    ? `${tasks.length} 项等待你处理，当前完成 ${approved}/${activeTotal}，点击定位到第一项`
    : `${complete ? "本轮完成" : episodePhaseLabel(phase)}，当前完成 ${approved}/${activeTotal}，点击返回生产首页`);
  button.title = active
    ? `${tasks[0].task_id} · ${tasks[0].title}`
    : `${complete ? "本轮完成" : episodePhaseLabel(phase)} · ${approved}/${activeTotal}`;
}

function renderHierarchy() {
  const selected = state.selectedTaskId;
  const isContent = state.structureAxis === "content";
  const nodes = isContent
    ? (state.overview.scope?.content_units || [])
    : (state.overview.scope?.deliverables || []);
  const idKey = isContent ? "unit_id" : "deliverable_id";
  const parentKey = isContent ? "parent_unit_id" : "parent_deliverable_id";
  const taskKey = isContent ? "content_unit_id" : "deliverable_id";
  $("#axisContent").classList.toggle("active", isContent);
  $("#axisDeliverable").classList.toggle("active", !isContent);
  $("#hierarchyNote").textContent = isContent
    ? "内容树只表示对象包含关系，不表示先后。"
    : "交付物树只表示成果归属；显式依赖才决定执行顺序。";
  const byParent = {};
  nodes.forEach((node) => ((byParent[node[parentKey] || "__root__"] ||= []).push(node)));
  Object.values(byParent).forEach((items) => items.sort((a, b) => (Number(a.order || 0) - Number(b.order || 0)) || String(a[idKey]).localeCompare(String(b[idKey]))));
  const tasks = state.overview.tasks || [];
  const byTaskId = Object.fromEntries(tasks.map((task) => [task.task_id, task]));
  const renderTask = (task) => `<button class="tree-task ${selected === task.task_id ? "selected" : ""}" data-task-id="${escapeHtml(task.task_id)}" type="button">
      ${escapeHtml(task.title)}
      <small>${escapeHtml(task.task_id)} · ${escapeHtml(taskStatusLabel(task))}</small>
    </button>`;
  const renderNode = (node, depth = 0) => {
    const id = node[idKey];
    const children = byParent[id] || [];
    const directTasks = (node.direct_task_ids || []).map((taskId) => byTaskId[taskId]).filter(Boolean);
    const phase = node.derived?.phase || "empty";
    return `<details class="tree-scope depth-${Math.min(depth, 4)}" ${depth === 0 ? "open" : ""}>
      <summary><span class="scope-title">${escapeHtml(node.title || id)}</span><span class="scope-phase">${escapeHtml(phase)}</span><span class="tree-count">${node.derived?.total || 0}</span></summary>
      <div class="scope-children">${directTasks.map(renderTask).join("")}${children.map((child) => renderNode(child, depth + 1)).join("")}</div>
    </details>`;
  };
  const roots = byParent.__root__ || [];
  const knownIds = new Set(nodes.map((node) => node[idKey]));
  const unassigned = tasks.filter((task) => !task[taskKey] || !knownIds.has(task[taskKey]));
  const renderedRoots = roots.map((node) => renderNode(node)).join("");
  const renderedUnassigned = unassigned.length
    ? `<details class="tree-scope depth-0" open><summary><span class="scope-title">未分配</span><span class="scope-phase">attention</span><span class="tree-count">${unassigned.length}</span></summary><div class="scope-children">${unassigned.map(renderTask).join("")}</div></details>`
    : "";
  $("#hierarchyTree").innerHTML = renderedRoots || renderedUnassigned
    ? renderedRoots + renderedUnassigned
    : `<div class="lane-empty">本分集尚未建立双轴结构。</div>`;
  bindTaskSelectors();
}

function renderNext() {
  const root = $("#nextAction");
  const humanTasks = humanAttentionTasks();
  const selected = state.next?.next;
  root.className = "next-action";
  if (humanTasks.length) {
    const task = humanTasks[0];
    root.classList.add("attention");
    root.innerHTML = `
      <div class="next-compact">
        <i aria-hidden="true"></i>
        <strong>${humanTasks.length} 项待你处理</strong>
        <span><b>${escapeHtml(task.task_id)}</b> · ${escapeHtml(task.title)}</span>
        <button class="primary-button" data-focus-task-id="${escapeHtml(task.task_id)}" type="button">查看</button>
      </div>`;
    bindFocusTaskSelectors();
    return;
  }
  if (!selected) {
    root.classList.add("hidden");
    root.innerHTML = "";
    return;
  }
  if (!selected.task && selected.action === "episode_replan") {
    const reasons = (selected.reasons || []).map((item) => item.kind).join("、");
    root.classList.add("blocked");
    root.innerHTML = `
      <div class="next-compact"><i aria-hidden="true"></i><strong>整集硬停止</strong><span>需要重新规划预算</span><small>${escapeHtml(reasons || "整集硬预算已经触发")}</small></div>`;
    return;
  }
  const task = selected.task;
  root.classList.add("motion");
  root.innerHTML = `
    <div class="next-compact">
      <i aria-hidden="true"></i>
      <strong>正在推进</strong>
      <span><b>${escapeHtml(task.task_id)}</b> · ${escapeHtml(task.title)}</span>
      <small>${escapeHtml(actionLabel(selected.action))}</small>
      <button class="secondary-button" data-focus-task-id="${escapeHtml(task.task_id)}" type="button">定位</button>
    </div>`;
  bindFocusTaskSelectors();
}

function renderMetrics() {
  const counts = state.overview.counts || {};
  const effective = state.overview.effective_counts || {};
  const ready = effective.ready || 0;
  const systemReview = counts.candidate || 0;
  const humanReview = humanAttentionTasks().length;
  const activeTotal = Object.entries(counts)
    .filter(([status]) => !["cancelled", "superseded"].includes(status))
    .reduce((sum, [, value]) => sum + Number(value || 0), 0);
  const retired = Number(counts.cancelled || 0) + Number(counts.superseded || 0);
  const metrics = [
    ["系统正在推进", Number(counts.working || 0) + Number(systemReview), `${counts.working || 0} 制作中 · ${systemReview} 系统审查中`, "green"],
    ["待你处理", humanReview, humanReview ? "审片、授权或方向决定" : "当前无需人工操作", humanReview ? "amber" : ""],
    ["当前路线完成", `${counts.approved || 0}/${activeTotal}`, retired ? `${retired} 条旧路线已归档` : `${ready} 个任务已可执行 · ${counts.blocked || 0} 阻塞`, ""],
  ];
  $("#metricStrip").innerHTML = metrics.map(([label, value, detail, tone]) => `<div class="metric"><span>${label}</span><strong class="${tone}">${value}</strong><small>${detail}</small></div>`).join("");
}

function laneFor(task) {
  if (taskHumanAttentionCount(task)) return "human";
  if (["planned", "rework"].includes(task.status) && task.derived?.runnable) return "ready";
  if (["working", "candidate"].includes(task.status)) return "system";
  return "blocked";
}

function renderBoard() {
  const lanes = [
    ["system", "系统正在推进"],
    ["human", "待你处理"],
    ["ready", "接下来"],
  ];
  const tasks = state.overview.tasks || [];
  const taskMarkup = (task) => `<button class="task-card ${state.selectedTaskId === task.task_id ? "selected" : ""}" data-task-id="${escapeHtml(task.task_id)}" type="button">
    <span class="task-id">${escapeHtml(task.task_id)}</span>
    <h3>${escapeHtml(task.title)}</h3>
    <footer><span><i class="status-dot ${escapeHtml(task.derived?.effective_state || task.status)}"></i>${escapeHtml(taskStatusLabel(task))}</span><span>${escapeHtml(task.scene_id || "EP")}</span></footer>
  </button>`;
  const primary = lanes.map(([lane, title]) => {
    const items = tasks.filter((task) => laneFor(task) === lane);
    return `<div class="board-lane ${lane}">
      <div class="lane-title"><span>${title}</span><b>${items.length}</b></div>
      <div class="lane-body">
        ${items.slice(0, 3).map(taskMarkup).join("") || `<div class="lane-empty">暂无任务</div>`}
        ${items.length > 3 ? `<details class="lane-more"><summary>再看 ${items.length - 3} 项</summary><div>${items.slice(3).map(taskMarkup).join("")}</div></details>` : ""}
      </div>
    </div>`;
  }).join("");
  const secondary = tasks.filter((task) => !["system", "human", "ready"].includes(laneFor(task)));
  $("#taskBoard").innerHTML = `${primary}
    ${secondary.length ? `<details class="board-secondary"><summary><span>等待、阻塞与终态</span><b>${secondary.length}</b></summary><div class="board-secondary-grid">${secondary.map(taskMarkup).join("")}</div></details>` : ""}`;
  bindTaskSelectors();
}

function syncDrawerState() {
  const hierarchyOpen = $(".hierarchy-panel")?.classList.contains("open");
  const inspectorOpen = $(".inspector-panel")?.classList.contains("open");
  document.body.classList.toggle("drawer-open", Boolean(hierarchyOpen || inspectorOpen));
  $("#drawerScrim")?.classList.toggle("open", Boolean(hierarchyOpen || inspectorOpen));
  $("#scopeButton")?.setAttribute("aria-expanded", hierarchyOpen ? "true" : "false");
}

function closeDrawers() {
  const wasOpen = Boolean($(".hierarchy-panel")?.classList.contains("open") || $(".inspector-panel")?.classList.contains("open"));
  $(".hierarchy-panel")?.classList.remove("open");
  $(".inspector-panel")?.classList.remove("open");
  syncDrawerState();
  if (wasOpen) {
    const returnTarget = drawerReturnFocus?.isConnected && drawerReturnFocus !== document.body ? drawerReturnFocus : $("#flowViewport");
    returnTarget?.focus();
  }
  drawerReturnFocus = null;
}

function openHierarchy() {
  drawerReturnFocus = document.activeElement;
  $(".inspector-panel")?.classList.remove("open");
  $(".hierarchy-panel")?.classList.add("open");
  syncDrawerState();
  requestAnimationFrame(() => $("#closeHierarchy")?.focus());
}

function openInspector() {
  if (isGraphFullscreen() && state.selectedTaskId) {
    renderTaskPeek(state.selectedTaskId, state.peekAnchor || { left: window.innerWidth / 2, right: window.innerWidth / 2, top: window.innerHeight / 2, bottom: window.innerHeight / 2, width: 0, height: 0 });
    return;
  }
  hideTaskPeek();
  renderInspector();
  drawerReturnFocus = document.activeElement;
  $(".hierarchy-panel")?.classList.remove("open");
  $(".inspector-panel")?.classList.add("open");
  syncDrawerState();
  requestAnimationFrame(() => $("#closeInspector")?.focus());
}

function taskDecisionFacts(task) {
  const lease = (state.overview.leases || []).find((item) => item.task_id === task.task_id);
  const reservation = (state.overview.dispatch_reservations || []).find((item) => item.task_id === task.task_id && item.status === "active");
  const gaps = (state.overview.gaps || []).filter((item) => item.task_id === task.task_id && item.status === "open");
  const changes = (state.overview.changes || []).filter((item) => item.task_id === task.task_id && item.status !== "resolved");
  const routes = (state.overview.routes || []).filter((item) => [item.replaced_task_id, item.replacement_task_id, ...(item.rewired_task_ids || []), ...(item.invalidated_task_ids || [])].includes(task.task_id));
  const returns = (state.overview.returns || []).filter((item) => item.task_id === task.task_id);
  const artifacts = (state.overview.artifacts || []).filter((item) => item.producer_task_id === task.task_id);
  const gates = (state.overview.gates || []).filter((item) => item.task_id === task.task_id);
  const annotationTargets = new Set([task.task_id, ...artifacts.map((item) => item.artifact_id)]);
  const annotations = (state.overview.annotations || []).filter((item) => annotationTargets.has(item.target_id));
  const observations = (state.overview.observations || []).filter((item) => item.task_id === task.task_id);
  const blockers = task.derived?.blockers || [...(task.blockers || []), ...gaps.map((gap) => ({ kind: "open_gap", reason: gap.reason }))];
  const humanGaps = gaps.filter((gap) => gap.requires_human || gap.kind === "contradictory_requirements");
  const nextGate = humanGaps.length
    ? "等待你的冲突裁决"
    : task.status === "user_review_pending"
    ? "等待你的授权"
    : task.derived?.missing_validators?.length
      ? `运行 ${task.derived.missing_validators.length} 个硬门禁`
      : task.status === "candidate"
        ? "等待独立审查"
        : task.status === "working"
          ? "提交候选制品"
          : task.derived?.runnable
            ? "可以领取"
            : blockers.length
              ? "先解除阻塞"
              : "等待上游";
  return { lease, reservation, gaps, humanGaps, changes, routes, returns, artifacts, gates, annotations, observations, blockers, nextGate };
}

function taskDetailSignature(task) {
  if (!task) return "none";
  const facts = taskDecisionFacts(task);
  const overrides = (state.overview.context_overrides || []).filter((item) =>
    item.status === "active" && (
      item.task_id === task.task_id ||
      item.scope === "episode" ||
      (item.scope === "content_unit" && item.content_unit_id === task.content_unit_id)
    )
  );
  return JSON.stringify({ task, facts, overrides });
}

function isGraphFullscreen() {
  return Boolean(document.querySelector(".graph-fullscreen") || document.fullscreenElement?.matches?.("#flowViewport, #executionMapFrame"));
}

function effectiveDetailMode() {
  return isGraphFullscreen() ? "peek" : state.detailMode;
}

function detailModeToggleMarkup(mode = effectiveDetailMode(), locked = isGraphFullscreen()) {
  const sidebar = mode === "sidebar";
  const label = locked
    ? "全屏模式固定使用就近气泡"
    : `任务详情当前使用${sidebar ? "右侧栏" : "就近气泡"}；切换为${sidebar ? "就近气泡" : "右侧栏"}`;
  return `<span class="detail-mode-icon bubble" aria-hidden="true"><svg viewBox="0 0 18 18"><path d="M3 3.5h12v8H8l-3 3v-3H3z"/></svg></span>
    <span class="detail-mode-track" aria-hidden="true"><i></i></span>
    <span class="detail-mode-icon sidebar" aria-hidden="true"><svg viewBox="0 0 18 18"><rect x="2.5" y="3" width="13" height="12" rx="1.5"/><path d="M11 3v12"/></svg></span>
    <span class="sr-only">${escapeHtml(label)}</span>`;
}

function configureDetailModeToggle(toggle) {
  if (!toggle) return;
  const mode = effectiveDetailMode();
  const locked = isGraphFullscreen();
  toggle.dataset.mode = mode;
  toggle.setAttribute("role", "switch");
  toggle.setAttribute("aria-checked", mode === "sidebar" ? "true" : "false");
  toggle.setAttribute("aria-label", locked
    ? "全屏模式固定使用就近气泡"
    : `任务详情当前使用${mode === "sidebar" ? "右侧栏" : "就近气泡"}，点击切换`);
  toggle.title = toggle.getAttribute("aria-label");
  toggle.disabled = locked;
  toggle.innerHTML = detailModeToggleMarkup(mode, locked);
  toggle.onclick = () => setDetailMode(state.detailMode === "peek" ? "sidebar" : "peek");
}

function renderDetailModeToggle() {
  $$('[data-detail-mode-toggle], #inspectorDetailModeToggle, #taskPeekModeToggle').forEach(configureDetailModeToggle);
}

function setDetailMode(nextMode) {
  if (isGraphFullscreen()) {
    toast("全屏画布固定使用就近气泡；退出全屏后可切换右侧栏", "error");
    return;
  }
  if (!new Set(["peek", "sidebar"]).has(nextMode) || nextMode === state.detailMode) return;
  state.detailMode = nextMode;
  try { localStorage.setItem("lecture-supervision-detail-mode", nextMode); } catch { /* preference remains session-local */ }
  renderDetailModeToggle();
  if (state.selectedTaskId) {
    if (nextMode === "sidebar") {
      openInspector();
    } else {
      closeDrawers();
      renderInspector();
      const fallback = { left: window.innerWidth / 2, right: window.innerWidth / 2, top: window.innerHeight / 2, bottom: window.innerHeight / 2, width: 0, height: 0 };
      renderTaskPeek(state.selectedTaskId, state.peekAnchor || fallback);
    }
  }
  toast(`任务详情已切换为${nextMode === "peek" ? "就近气泡" : "右侧栏"}`);
}

function hideTaskPeek({ restoreFocus = false } = {}) {
  const peek = $("#taskPeek");
  if (!peek || peek.classList.contains("hidden")) return;
  captureTaskDetailSession(peek, peek.dataset.detailTaskId);
  peek.classList.add("hidden");
  peek.replaceChildren();
  delete peek.dataset.detailTaskId;
  state.peekSignature = null;
  if (restoreFocus && taskPeekReturnFocus?.isConnected) taskPeekReturnFocus.focus();
  taskPeekReturnFocus = null;
}

function ensureMediaDrafts() {
  if (state.mediaDraftEpisode === state.episodeId) return state.mediaDrafts;
  state.mediaDraftEpisode = state.episodeId;
  try {
    const raw = localStorage.getItem(`lecture-supervision-media-drafts:${state.episodeId}`);
    const parsed = raw ? JSON.parse(raw) : [];
    state.mediaDrafts = Array.isArray(parsed) ? parsed : [];
  } catch {
    state.mediaDrafts = [];
  }
  return state.mediaDrafts;
}

function persistMediaDrafts() {
  try {
    localStorage.setItem(`lecture-supervision-media-drafts:${state.episodeId}`, JSON.stringify(state.mediaDrafts));
  } catch { /* drafts remain available for this browser session */ }
}

function ensureDetailDrafts() {
  if (state.detailDraftEpisode === state.episodeId) return state.detailDrafts;
  state.detailDraftEpisode = state.episodeId;
  try {
    const raw = localStorage.getItem(`lecture-supervision-detail-drafts:${state.episodeId}`);
    const parsed = raw ? JSON.parse(raw) : {};
    state.detailDrafts = parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    state.detailDrafts = {};
  }
  return state.detailDrafts;
}

function persistDetailDrafts() {
  try {
    localStorage.setItem(`lecture-supervision-detail-drafts:${state.episodeId}`, JSON.stringify(state.detailDrafts));
  } catch { /* drafts remain available for this browser session */ }
}

function stageDetailFormSubmission(form, draftKey) {
  const textarea = form?.querySelector('textarea[name="body"]');
  const severity = form?.querySelector('select[name="severity"]');
  const saved = {
    body: textarea?.value || "",
    severity: severity?.value || "note",
  };
  const active = document.activeElement;
  form?.reset();
  if (active && form?.contains(active)) active.blur();
  delete ensureDetailDrafts()[draftKey];
  Object.values(state.detailUiState).forEach((snapshot) => {
    if (snapshot?.focus?.key === draftKey) snapshot.focus = null;
  });
  persistDetailDrafts();
  return () => {
    if (textarea) textarea.value = saved.body;
    if (severity) severity.value = saved.severity;
    ensureDetailDrafts()[draftKey] = saved;
    persistDetailDrafts();
    textarea?.focus({ preventScroll: true });
  };
}

function detailFormKey(form, taskId) {
  return form?.dataset.draftKey || (form?.matches("[data-task-annotation-form]") ? `task:${taskId}` : null);
}

function captureTaskDetailSession(root, taskId) {
  if (!root || !taskId) return;
  const drafts = ensureDetailDrafts();
  const surface = root.id === "taskPeek" ? "peek" : root.id === "mediaDock" ? "media" : "sidebar";
  const scroll = root.querySelector(".task-peek-scroll, .media-dock-scroll") || root;
  const active = document.activeElement;
  const snapshot = {
    scrollTop: scroll.scrollTop,
    details: [...root.querySelectorAll("details")].map((item) => item.open),
    focus: null,
    media: {},
  };
  root.querySelectorAll("[data-task-annotation-form], [data-media-annotation-form]").forEach((form) => {
    const key = detailFormKey(form, taskId);
    if (!key) return;
    const textarea = form.querySelector('textarea[name="body"]');
    const severity = form.querySelector('select[name="severity"]');
    drafts[key] = { body: textarea?.value || "", severity: severity?.value || "note" };
    if (active && form.contains(active)) {
      snapshot.focus = {
        key,
        name: active.getAttribute("name"),
        start: typeof active.selectionStart === "number" ? active.selectionStart : null,
        end: typeof active.selectionEnd === "number" ? active.selectionEnd : null,
      };
    }
  });
  root.querySelectorAll("[data-media-review]").forEach((card) => {
    const media = card.querySelector("video, audio");
    if (!media) return;
    snapshot.media[card.dataset.artifactId] = {
      currentTime: Number(media.currentTime) || 0,
      paused: media.paused,
      annotationTime: card.dataset.annotationTime,
      annotationX: card.dataset.annotationX,
      annotationY: card.dataset.annotationY,
    };
  });
  state.detailUiState[`${surface}:${taskId}`] = snapshot;
  persistDetailDrafts();
}

function restoreTaskDetailSession(root, taskId) {
  if (!root || !taskId) return;
  const drafts = ensureDetailDrafts();
  const surface = root.id === "taskPeek" ? "peek" : root.id === "mediaDock" ? "media" : "sidebar";
  const snapshot = state.detailUiState[`${surface}:${taskId}`];
  root.querySelectorAll("[data-task-annotation-form], [data-media-annotation-form]").forEach((form) => {
    const key = detailFormKey(form, taskId);
    const draft = key ? drafts[key] : null;
    if (!draft) return;
    const textarea = form.querySelector('textarea[name="body"]');
    const severity = form.querySelector('select[name="severity"]');
    if (textarea) textarea.value = draft.body || "";
    if (severity) severity.value = draft.severity || "note";
  });
  if (!snapshot) return;
  root.querySelectorAll("details").forEach((item, index) => {
    if (index < snapshot.details.length) item.open = snapshot.details[index];
  });
  Object.entries(snapshot.media || {}).forEach(([artifactId, mediaState]) => {
    const card = root.querySelector(`[data-media-review][data-artifact-id="${CSS.escape(artifactId)}"]`);
    const media = card?.querySelector("video, audio");
    if (!card || !media) return;
    if (mediaState.annotationTime !== undefined) card.dataset.annotationTime = mediaState.annotationTime;
    if (mediaState.annotationX !== undefined) card.dataset.annotationX = mediaState.annotationX;
    if (mediaState.annotationY !== undefined) card.dataset.annotationY = mediaState.annotationY;
    const restoreMedia = () => {
      if (Number.isFinite(mediaState.currentTime)) media.currentTime = mediaState.currentTime;
      if (!mediaState.paused) media.play().catch(() => {});
    };
    if (media.readyState >= 1) restoreMedia();
    else media.addEventListener("loadedmetadata", restoreMedia, { once: true });
  });
  requestAnimationFrame(() => {
    const scroll = root.querySelector(".task-peek-scroll, .media-dock-scroll") || root;
    const restoreScroll = () => { scroll.scrollTop = snapshot.scrollTop || 0; };
    restoreScroll();
    requestAnimationFrame(restoreScroll);
    if (!snapshot.focus) return;
    const form = [...root.querySelectorAll("[data-task-annotation-form], [data-media-annotation-form]")]
      .find((item) => detailFormKey(item, taskId) === snapshot.focus.key);
    const field = form?.querySelector(`[name="${CSS.escape(snapshot.focus.name || "body")}"]`);
    field?.focus({ preventScroll: true });
    if (field && snapshot.focus.start !== null && typeof field.setSelectionRange === "function") {
      field.setSelectionRange(snapshot.focus.start, snapshot.focus.end);
    }
    restoreScroll();
  });
}

function mediaKindForArtifact(artifact) {
  const path = String(artifact.path || "").toLowerCase();
  const role = String(artifact.role || "").toLowerCase();
  if (/\.(mp4|m4v|mov|webm|ogv)$/.test(path) || /(video|review_mp4|cut)/.test(role)) return "video";
  if (/\.(wav|mp3|m4a|aac|flac|ogg|opus)$/.test(path) || /(audio|voice|tts|sound)/.test(role)) return "audio";
  return null;
}

function formatMediaTime(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  const totalMillis = Math.round(value * 1000);
  const hours = Math.floor(totalMillis / 3_600_000);
  const minutes = Math.floor((totalMillis % 3_600_000) / 60_000);
  const whole = Math.floor((totalMillis % 60_000) / 1000);
  const millis = totalMillis % 1000;
  return `${hours ? `${String(hours).padStart(2, "0")}:` : ""}${String(minutes).padStart(2, "0")}:${String(whole).padStart(2, "0")}.${String(millis).padStart(3, "0")}`;
}

function annotationLocationMarkup(annotation) {
  const location = annotation.location;
  if (!location || location.kind !== "media") return "";
  const position = location.position;
  return `<button type="button" class="annotation-location" data-seek-artifact="${escapeHtml(location.artifact_id)}" data-seek-time="${escapeHtml(location.time_seconds)}"${position ? ` data-seek-x="${escapeHtml(position.x)}" data-seek-y="${escapeHtml(position.y)}"` : ""}>${escapeHtml(location.timecode || formatMediaTime(location.time_seconds))}${position ? ` · x ${Math.round(position.x * 100)}% · y ${Math.round(position.y * 100)}%` : ""}</button>`;
}

function mediaReviewMarkup(artifacts, annotations, { floating = false } = {}) {
  const mediaArtifacts = artifacts.filter((artifact) => mediaKindForArtifact(artifact));
  if (!mediaArtifacts.length) return "";
  const drafts = ensureMediaDrafts();
  return `<section class="media-review-section">
    <div class="media-review-heading"><div><span class="eyebrow">MEDIA REVIEW</span><h4>音视频验收</h4></div><span>${mediaArtifacts.length} 个制品</span></div>
    ${mediaArtifacts.map((artifact) => {
      const kind = mediaKindForArtifact(artifact);
      const mediaUrl = `/api/episodes/${encodeURIComponent(state.episodeId)}/artifacts/${encodeURIComponent(artifact.artifact_id)}/media`;
      const artifactAnnotations = annotations.filter((item) => item.target_id === artifact.artifact_id);
      const player = kind === "video"
        ? `<div class="media-stage"><video controls playsinline preload="metadata" src="${escapeHtml(mediaUrl)}"></video><button class="media-position-layer hidden" data-media-position-layer type="button" aria-label="在画面上标记问题位置"></button><i class="media-position-marker hidden" data-media-position-marker></i></div>`
        : `<audio controls preload="metadata" src="${escapeHtml(mediaUrl)}"></audio>`;
      return `<article class="media-review-card" data-media-review data-artifact-id="${escapeHtml(artifact.artifact_id)}" data-media-kind="${kind}">
        <header><div><b>${escapeHtml(artifact.role || kind)}</b><span>${escapeHtml(artifact.status || "registered")}</span></div><div class="media-card-actions"><code>${escapeHtml(artifact.artifact_id)}</code>${floating ? "" : `<button type="button" data-open-media-float aria-label="在可拖动窗口中审片">↗ 浮动审片</button>`}</div></header>
        ${player}
        <div class="media-file-facts"><span title="${escapeHtml(artifact.path)}">${escapeHtml(artifact.path)}</span><code>${escapeHtml(String(artifact.sha256 || "").slice(0, 16))}</code></div>
        <div class="media-annotation-clock"><span>标注时间</span><b data-media-time>00:00.000</b><button type="button" data-use-current-time>取当前帧</button>${kind === "video" ? `<button type="button" data-mark-position>标记画面位置</button>` : ""}</div>
        <form class="media-annotation-form" data-media-annotation-form data-draft-key="media:${escapeHtml(artifact.artifact_id)}">
          <textarea name="body" required placeholder="这一秒或这个画面位置有什么问题？"></textarea>
          <div class="annotation-actions"><select name="severity"><option value="note">普通标注</option><option value="warning">警告</option><option value="blocker">阻塞</option></select><button class="secondary-button" type="button" data-add-media-draft>加入整集草稿</button><button class="primary-button" type="submit">立即提交</button></div>
        </form>
        <div class="media-existing-annotations">${artifactAnnotations.map((item) => `<div class="evidence-item"><div><b>${escapeHtml(item.severity)} · ${escapeHtml(item.actor)}</b>${annotationLocationMarkup(item)}</div>${escapeHtml(item.body)}</div>`).join("") || `<div class="media-empty">这个制品还没有时间点标注。</div>`}</div>
      </article>`;
    }).join("")}
    <div class="media-draft-tray"><div><b>整集标注草稿</b><span>可跨任务累积，看片结束后一次提交</span></div><strong data-media-draft-count>${drafts.length}</strong><button class="secondary-button" type="button" data-clear-media-drafts ${drafts.length ? "" : "disabled"}>清空</button><button class="primary-button" type="button" data-submit-media-drafts ${drafts.length ? "" : "disabled"}>集体提交</button></div>
  </section>`;
}

function renderTaskPeek(taskId, anchorRect, { focus = true } = {}) {
  const peek = $("#taskPeek");
  const task = (state.overview.tasks || []).find((item) => item.task_id === taskId);
  if (!peek || !task || !anchorRect) return;
  captureTaskDetailSession(peek, peek.dataset.detailTaskId);
  peek.innerHTML = `
    <div class="task-peek-head">
      <span class="task-peek-kicker">TASK PASSPORT · ${escapeHtml(task.task_id)}</span>
      <div class="task-peek-head-actions"><button id="taskPeekModeToggle" class="detail-mode-switch" data-detail-mode-toggle type="button"></button><button id="taskPeekClose" class="task-peek-close" type="button" aria-label="关闭任务气泡">×</button></div>
    </div>
    <div class="task-peek-scroll" tabindex="0">${taskDetailMarkup(task, { titleId: "taskPeekTitle" })}</div>`;
  peek.dataset.detailTaskId = taskId;
  state.peekSignature = taskDetailSignature(task);
  peek.classList.remove("hidden", "tail-left", "tail-right");
  peek.style.visibility = "hidden";
  if (!state.peekGeometry?.manual) {
    peek.style.left = "16px";
    peek.style.top = "16px";
  }
  requestAnimationFrame(() => {
    const gap = 16;
    if (state.peekGeometry?.manual) {
      const width = Math.min(state.peekGeometry.width || peek.offsetWidth, window.innerWidth - gap * 2);
      const height = Math.min(state.peekGeometry.height || peek.offsetHeight, window.innerHeight - gap * 2);
      peek.style.width = `${width}px`;
      peek.style.height = `${height}px`;
      peek.style.left = `${Math.max(gap, Math.min(window.innerWidth - width - gap, state.peekGeometry.left || gap))}px`;
      peek.style.top = `${Math.max(gap, Math.min(window.innerHeight - height - gap, state.peekGeometry.top || gap))}px`;
      peek.classList.add("detached");
      peek.style.visibility = "visible";
      installTaskPeekInteractions(peek);
      if (focus) $("#taskPeekClose")?.focus();
      return;
    }
    const width = peek.offsetWidth;
    const height = peek.offsetHeight;
    const roomRight = window.innerWidth - anchorRect.right;
    const placeRight = roomRight >= width + gap || anchorRect.left < width + gap;
    const left = placeRight
      ? Math.min(window.innerWidth - width - gap, anchorRect.right + gap)
      : Math.max(gap, anchorRect.left - width - gap);
    const top = Math.max(gap, Math.min(window.innerHeight - height - gap, anchorRect.top + anchorRect.height / 2 - 42));
    const tailY = Math.max(22, Math.min(height - 22, anchorRect.top + anchorRect.height / 2 - top));
    peek.style.left = `${left}px`;
    peek.style.top = `${top}px`;
    peek.style.setProperty("--peek-tail-y", `${tailY}px`);
    peek.classList.add(placeRight ? "tail-left" : "tail-right");
    peek.style.visibility = "visible";
    installTaskPeekInteractions(peek);
    if (focus) $("#taskPeekClose")?.focus();
  });
  $("#taskPeekClose").onclick = () => hideTaskPeek({ restoreFocus: true });
  bindTaskDetail(peek, task);
  restoreTaskDetailSession(peek, taskId);
  renderDetailModeToggle();
}

function installTaskPeekInteractions(peek) {
  const head = peek.querySelector(".task-peek-head");
  if (!head) return;
  head.onpointerdown = (event) => {
    if (event.button !== 0 || event.target.closest("button, input, select, textarea, a")) return;
    event.preventDefault();
    const rect = peek.getBoundingClientRect();
    const startWidth = rect.width;
    const startHeight = rect.height;
    const offsetX = event.clientX - rect.left;
    const offsetY = event.clientY - rect.top;
    head.setPointerCapture?.(event.pointerId);
    const move = (moveEvent) => {
      const width = startWidth;
      const height = startHeight;
      const left = Math.max(8, Math.min(window.innerWidth - width - 8, moveEvent.clientX - offsetX));
      const top = Math.max(8, Math.min(window.innerHeight - height - 8, moveEvent.clientY - offsetY));
      Object.assign(peek.style, { left: `${left}px`, top: `${top}px`, width: `${width}px`, height: `${height}px` });
      peek.classList.remove("tail-left", "tail-right");
      peek.classList.add("detached");
      state.peekGeometry = { manual: true, left, top, width, height };
    };
    const stop = () => {
      head.removeEventListener("pointermove", move);
      head.removeEventListener("pointerup", stop);
      head.removeEventListener("pointercancel", stop);
    };
    head.addEventListener("pointermove", move);
    head.addEventListener("pointerup", stop);
    head.addEventListener("pointercancel", stop);
  };
  peek.onpointerdown = (event) => {
    const rect = peek.getBoundingClientRect();
    if (event.clientX < rect.right - 22 || event.clientY < rect.bottom - 22) return;
    state.peekGeometry = { manual: true, left: rect.left, top: rect.top, width: rect.width, height: rect.height };
    peek.classList.remove("tail-left", "tail-right");
    peek.classList.add("detached");
  };
  peek.onpointerup = () => {
    if (!state.peekGeometry?.manual) return;
    const rect = peek.getBoundingClientRect();
    state.peekGeometry = { manual: true, left: rect.left, top: rect.top, width: rect.width, height: rect.height };
  };
  head.ondblclick = (event) => {
    if (event.target.closest("button")) return;
    state.peekGeometry = null;
    peek.classList.remove("detached");
    renderTaskPeek(state.selectedTaskId, state.peekAnchor, { focus: false });
    toast("任务气泡已重新锚定到节点");
  };
}

function taskAnchorScope(element) {
  if (element?.closest?.("#executionMap")) return "#executionMap";
  if (element?.closest?.("#flowViewport")) return "#flowViewport";
  if (element?.closest?.("#hierarchyTree")) return "#hierarchyTree";
  if (element?.closest?.("#workstationGrid")) return "#workstationGrid";
  if (element?.closest?.("#productionView")) return "#productionView";
  if (element?.closest?.("#flowTimeRibbon")) return "#flowTimeRibbon";
  return "body";
}

function currentTaskAnchor(taskId, scopeSelector, previousRect) {
  const candidates = $$(`${scopeSelector} [data-task-id="${CSS.escape(taskId)}"]`)
    .map((element) => ({ element, rect: element.getBoundingClientRect() }))
    .filter(({ rect }) => rect.width > 0 && rect.height > 0);
  if (!candidates.length) return null;
  const previousX = previousRect ? previousRect.left + previousRect.width / 2 : window.innerWidth / 2;
  const previousY = previousRect ? previousRect.top + previousRect.height / 2 : window.innerHeight / 2;
  return candidates.sort((a, b) => {
    const distanceA = Math.hypot(a.rect.left + a.rect.width / 2 - previousX, a.rect.top + a.rect.height / 2 - previousY);
    const distanceB = Math.hypot(b.rect.left + b.rect.width / 2 - previousX, b.rect.top + b.rect.height / 2 - previousY);
    return distanceA - distanceB;
  })[0];
}

function selectTask(taskId, anchorElement = null) {
  if (!taskId) return;
  const anchorScope = taskAnchorScope(anchorElement);
  const rect = anchorElement?.getBoundingClientRect?.();
  const previousRect = rect ? { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: rect.width, height: rect.height } : null;
  state.selectedTaskId = taskId;
  state.peekScope = anchorScope;
  renderAll();
  const currentAnchor = currentTaskAnchor(taskId, anchorScope, previousRect);
  const currentRect = currentAnchor?.rect;
  const anchorRect = currentRect ? { left: currentRect.left, right: currentRect.right, top: currentRect.top, bottom: currentRect.bottom, width: currentRect.width, height: currentRect.height } : previousRect;
  state.peekAnchor = anchorRect;
  taskPeekReturnFocus = currentAnchor?.element || anchorElement;
  if (effectiveDetailMode() === "sidebar" || !anchorRect) {
    openInspector();
    return;
  }
  closeDrawers();
  renderTaskPeek(taskId, anchorRect);
}

function bindTaskSelectors() {
  $$('[data-task-id]').forEach((button) => {
    if (button.closest?.("#taskPeek, #mediaDock, #inspectorBody")) return;
    button.onclick = () => selectTask(button.dataset.taskId, button);
  });
}

function focusTaskOnHome(taskId) {
  if (!taskId) return;
  state.flow.presentation = "layered";
  state.flow.expandedForecastTaskIds.add(taskId);
  activateView("production");
  renderExecutionPreview();
  requestAnimationFrame(() => {
    const viewport = $("#executionMap");
    const node = viewport?.querySelector(`[data-task-id="${CSS.escape(taskId)}"]`);
    if (!viewport || !node) {
      toast(`生产地图中暂时找不到 ${taskId}`, "error");
      return;
    }
    const viewportRect = viewport.getBoundingClientRect();
    const nodeRect = node.getBoundingClientRect();
    viewport.scrollLeft += nodeRect.left + nodeRect.width / 2 - (viewportRect.left + viewportRect.width / 2);
    viewport.scrollTop += nodeRect.top + nodeRect.height / 2 - (viewportRect.top + viewportRect.height / 2);
    node.focus({ preventScroll: true });
    selectTask(taskId, node);
  });
}

function bindFocusTaskSelectors() {
  $$('[data-focus-task-id]').forEach((button) => {
    button.onclick = (event) => {
      event.stopPropagation();
      focusTaskOnHome(button.dataset.focusTaskId);
    };
  });
}

function toggleTaskExpansion(taskId) {
  if (!taskId) return;
  const expanded = state.flow.expandedForecastTaskIds;
  const opening = !expanded.has(taskId);
  if (opening) expanded.add(taskId);
  else expanded.delete(taskId);
  state.flow.fittedKey = null;
  renderFlow();
  toast(`${taskId} 后续节点已${opening ? "展开" : "收起"}`);
}

function bindGraphTaskGestures(element) {
  let clickTimer = null;
  const inspect = () => selectTask(element.dataset.taskId, element);
  element.addEventListener("click", (event) => {
    event.stopPropagation();
    clearTimeout(clickTimer);
    clickTimer = window.setTimeout(inspect, 220);
  });
  element.addEventListener("dblclick", (event) => {
    event.preventDefault();
    event.stopPropagation();
    clearTimeout(clickTimer);
    toggleTaskExpansion(element.dataset.taskId);
  });
  element.addEventListener("keydown", (event) => {
    if (["Enter", " "].includes(event.key) && !event.shiftKey) {
      event.preventDefault();
      inspect();
    }
    if ((event.key === "Enter" && event.shiftKey) || event.key.toLowerCase() === "e") {
      event.preventDefault();
      toggleTaskExpansion(element.dataset.taskId);
    }
  });
}

function taskDetailMarkup(task, { titleId = "" } = {}) {
  const { lease, reservation, gaps, humanGaps, changes, routes, returns, artifacts, gates, annotations, observations, blockers, nextGate } = taskDecisionFacts(task);
  const attentionCount = blockers.length + changes.length + returns.filter((item) => item.status === "pending").length;
  return `
    <div class="object-heading">
      <span class="object-id">${escapeHtml(task.task_id)}</span>
      <h3${titleId ? ` id="${escapeHtml(titleId)}"` : ""}>${escapeHtml(task.title)}</h3>
      <p>${escapeHtml(task.goal)}</p>
      <span class="object-status"><i class="status-dot ${escapeHtml(task.derived?.effective_state || task.status)}"></i>${escapeHtml(taskStatusLabel(task))}</span>
    </div>
    <div class="task-decision-summary">
      <div><span>当前负责人</span><b>${escapeHtml(lease?.owner || (reservation ? `${reservation.reserved_for} · 已预留` : task.author) || "未领取")}</b></div>
      <div><span>下一道门</span><b>${escapeHtml(nextGate)}</b></div>
    </div>
    ${mediaReviewMarkup(artifacts, annotations)}
    ${humanGaps.map((gap) => `<section class="human-decision conflict-decision">
      <div class="decision-state-line"><span>合同冲突</span><b>需要你的裁决</b></div>
      <p>${escapeHtml(gap.reason || "任务合同包含不能同时成立的要求。")}</p>
      <div class="conflict-sources">
        ${(gap.sources || []).map((source) => `<div><span>${escapeHtml(source.field || "来源")}</span><code>${escapeHtml(source.value ?? "—")}</code></div>`).join("")}
      </div>
      <form data-resolve-gap-form data-gap-id="${escapeHtml(gap.gap_id)}">
        <textarea name="resolution" placeholder="明确哪一项是权威要求，以及另一项如何处理…" required></textarea>
        <button class="primary-button" type="submit">提交裁决并恢复流程</button>
      </form>
    </section>`).join("")}
    ${task.status === "user_review_pending" ? `<section class="human-decision"><strong>需要你的决定</strong><p>审查已经完成，只有你能批准最终进入下一状态。</p><div class="action-grid"><button data-human-approve class="primary-button" type="button">通过</button><button data-human-revise class="danger-button" type="button">打回</button></div></section>` : ""}
    ${task.status === "approved" ? `<section class="human-decision approval-reversal"><div class="decision-state-line"><span>当前结论</span><b>已批准</b></div><p>如果复看后改变主意，请显式撤销批准。系统会保留原批准记录、把本任务送回返修，并只让受影响的下游失效。</p><button data-revoke-approval class="danger-button" type="button">撤销批准并打回</button></section>` : ""}
    <details class="inspector-disclosure attention" ${attentionCount ? "open" : ""}>
      <summary><span>约束与回路</span><b>${attentionCount || "无异常"}</b></summary>
      <div class="disclosure-body">
        ${blockers.map((item) => `<div class="blocker-item">${escapeHtml(item.kind)}${item.reason ? ` · ${escapeHtml(item.reason)}` : ""}</div>`).join("") || `<div class="evidence-item">没有已知阻塞</div>`}
        ${changes.map((item) => `<div class="evidence-item">CHANGE · ${escapeHtml(item.reason)} · ${escapeHtml(item.status)}</div>`).join("")}
        ${routes.map((item) => `<div class="evidence-item">ROUTE · ${escapeHtml(item.replaced_task_id)} → ${escapeHtml(item.replacement_task_id)}<br>${escapeHtml(item.strategy)} · ${escapeHtml(item.status)}</div>`).join("")}
        ${returns.map((item) => `<div class="evidence-item">RETURN · ${escapeHtml(item.status)} → ${escapeHtml(item.assigned_to)}<br>${escapeHtml(item.delivery_policy)} · 不抢占当前租约</div>`).join("")}
      </div>
    </details>
    <details class="inspector-disclosure">
      <summary><span>状态与归属</span><b>${escapeHtml(task.wave_id || task.scene_id || "EP")}</b></summary>
      <div class="disclosure-body fact-list">
        <div class="fact-row"><span>版本</span><b>scope r${task.scope_revision || 1} · attempt ${task.attempt || 0}</b></div>
        <div class="fact-row"><span>所属</span><b>${escapeHtml(task.wave_id || "—")} / ${escapeHtml(task.scene_id || "—")}</b></div>
        <div class="fact-row"><span>双轴坐标</span><b>${escapeHtml(task.deliverable_id || "未分配交付物流")} × ${escapeHtml(task.content_unit_id || "未分配内容单元")}</b></div>
        <div class="fact-row"><span>租约</span><b>${lease ? `${escapeHtml(lease.status)} · g${lease.generation} · ${escapeHtml(lease.owner)}` : "无"}</b></div>
        <div class="fact-row"><span>依赖</span><b>${escapeHtml((task.dependencies || []).join(", ") || "无")}</b></div>
        <div class="fact-row"><span>上下文</span><b>${escapeHtml(task.active_capsule_hash ? task.active_capsule_hash.slice(0, 14) : "未签发")}</b></div>
        <div class="fact-row"><span>有效时间</span><b>${Math.round(task.active_seconds || 0)}s / ${task.budget?.hard_active_seconds || "—"}s</b></div>
        <div class="fact-row"><span>无进展心跳</span><b>${task.heartbeats_without_progress || 0} / ${task.budget?.max_no_progress_heartbeats || "—"}</b></div>
      </div>
    </details>
    ${contextWorkspaceMarkup(task)}
    <details class="inspector-disclosure">
      <summary><span>证据与制品</span><b>${(task.references || []).length + artifacts.length}</b></summary>
      <div class="disclosure-body">
        ${(task.references || []).map((item) => `<div class="evidence-item">REF · ${escapeHtml(item.path)}<br>${escapeHtml(item.sha256.slice(0, 16))}</div>`).join("")}
        ${artifacts.map((item) => `<div class="evidence-item">${escapeHtml(item.role)} · ${escapeHtml(item.status)}<br>${escapeHtml(item.path)}<br>${escapeHtml(item.sha256.slice(0, 16))}</div>`).join("")}
        ${!(task.references || []).length && !artifacts.length ? `<div class="evidence-item">尚无绑定证据</div>` : ""}
      </div>
    </details>
    <details class="inspector-disclosure">
      <summary><span>程序硬门禁</span><b>${gates.filter((item) => item.status === "pass").length}/${task.required_validators?.length || 0}</b></summary>
      <div class="disclosure-body">
        ${(task.required_validators || []).map((validator) => {
          const receipt = [...gates].reverse().find((item) => item.candidate_hash === task.candidate?.candidate_hash && item.validator_id === validator.validator_id && item.validator_sha256 === validator.sha256);
          return `<div class="evidence-item">${escapeHtml(validator.validator_id)} · v${escapeHtml(validator.version)} · ${escapeHtml(receipt?.status || "待运行")}<br>${escapeHtml(validator.sha256.slice(0, 16))}${receipt?.summary ? `<br>${escapeHtml(receipt.summary)}` : ""}</div>`;
        }).join("") || `<div class="evidence-item">本任务没有绑定程序硬门禁</div>`}
      </div>
    </details>
    <details class="inspector-disclosure">
      <summary><span>标注、变更与验证日志</span><b>${annotations.length + observations.length}</b></summary>
      <div class="disclosure-body">
        ${annotations.map((item) => `<div class="evidence-item"><div><b>${escapeHtml(item.severity)} · ${escapeHtml(item.actor)}</b>${annotationLocationMarkup(item)}</div>${escapeHtml(item.body)}</div>`).join("") || `<div class="evidence-item">尚无标注</div>`}
        ${observations.map((item) => `<article class="agent-observation"><header><b>VERIFY · ${escapeHtml(item.actor)}</b><span>${escapeHtml(item.category)} · ${escapeHtml(item.severity)}</span></header><strong>${escapeHtml(item.summary)}</strong>${item.expectation ? `<p><span>期望</span>${escapeHtml(item.expectation)}</p>` : ""}${item.actual ? `<details><summary>展开机器证据</summary><pre>${escapeHtml(item.actual)}</pre></details>` : ""}<footer>${escapeHtml(item.observation_id)}</footer></article>`).join("")}
        <form data-task-annotation-form data-draft-key="task:${escapeHtml(task.task_id)}" class="annotation-form">
          <textarea name="body" placeholder="说明你观察到的问题或要求…" required></textarea>
          <div class="annotation-actions"><select name="severity"><option value="note">普通标注</option><option value="warning">警告</option><option value="blocker">阻塞</option></select><button class="secondary-button" type="submit">写入</button></div>
        </form>
        <div class="action-grid secondary-actions"><button data-record-change class="secondary-button" type="button">记录变更</button><button data-record-gap class="secondary-button" type="button">报告缺口</button></div>
      </div>
    </details>`;
}

function mediaAnnotationPayload(card) {
  const form = card.querySelector("[data-media-annotation-form]");
  const media = card.querySelector("video, audio");
  const body = String(new FormData(form).get("body") || "").trim();
  if (!body) {
    toast("先写下这一秒观察到的问题", "error");
    form.querySelector("textarea")?.focus();
    return null;
  }
  const seconds = Math.max(0, Number(card.dataset.annotationTime ?? media?.currentTime ?? 0) || 0);
  const location = {
    kind: "media",
    artifact_id: card.dataset.artifactId,
    time_seconds: seconds,
    timecode: formatMediaTime(seconds),
  };
  if (card.dataset.annotationX && card.dataset.annotationY) {
    location.position = { x: Number(card.dataset.annotationX), y: Number(card.dataset.annotationY) };
  }
  return {
    target_id: card.dataset.artifactId,
    body,
    severity: String(new FormData(form).get("severity") || "note"),
    location,
  };
}

function refreshMediaDraftControls() {
  const count = ensureMediaDrafts().length;
  $$('[data-media-draft-count]').forEach((element) => { element.textContent = count; });
  $$('[data-submit-media-drafts], [data-clear-media-drafts]').forEach((button) => { button.disabled = count === 0; });
}

function bindMediaReview(root) {
  root?.querySelectorAll("[data-media-review]").forEach((card) => {
    const media = card.querySelector("video, audio");
    const readout = card.querySelector("[data-media-time]");
    const marker = card.querySelector("[data-media-position-marker]");
    const layer = card.querySelector("[data-media-position-layer]");
    card.querySelector("[data-open-media-float]")?.addEventListener("click", () => openFloatingMedia(card.dataset.artifactId));
    const updateClock = () => {
      const seconds = Math.max(0, Number(media?.currentTime) || 0);
      card.dataset.annotationTime = String(seconds);
      if (readout) readout.textContent = formatMediaTime(seconds);
    };
    media?.addEventListener("loadedmetadata", updateClock);
    media?.addEventListener("timeupdate", updateClock);
    media?.addEventListener("seeked", updateClock);
    card.querySelector("[data-use-current-time]")?.addEventListener("click", () => {
      media?.pause();
      updateClock();
      toast(`已定位 ${readout?.textContent || "当前帧"}`);
    });
    card.querySelector("[data-mark-position]")?.addEventListener("click", () => {
      media?.pause();
      updateClock();
      layer?.classList.remove("hidden");
      card.classList.add("position-picking");
      toast("请直接点击视频画面中的问题位置");
    });
    layer?.addEventListener("click", (event) => {
      const rect = layer.getBoundingClientRect();
      const x = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
      const y = Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height));
      card.dataset.annotationX = String(x);
      card.dataset.annotationY = String(y);
      marker.style.left = `${x * 100}%`;
      marker.style.top = `${y * 100}%`;
      marker.classList.remove("hidden");
      layer.classList.add("hidden");
      card.classList.remove("position-picking");
      toast(`已标记画面位置 x ${Math.round(x * 100)}% · y ${Math.round(y * 100)}%`);
    });
    const form = card.querySelector("[data-media-annotation-form]");
    const draftKey = detailFormKey(form, state.selectedTaskId);
    form?.addEventListener("input", () => {
      ensureDetailDrafts()[draftKey] = {
        body: form.querySelector('textarea[name="body"]')?.value || "",
        severity: form.querySelector('select[name="severity"]')?.value || "note",
      };
      persistDetailDrafts();
    });
    form.onsubmit = async (event) => {
      event.preventDefault();
      const payload = mediaAnnotationPayload(card);
      if (!payload) return;
      const restoreDraft = stageDetailFormSubmission(form, draftKey);
      try {
        await sendCommand("annotate", payload);
      } catch (error) {
        restoreDraft();
        throw error;
      }
    };
    card.querySelector("[data-add-media-draft]")?.addEventListener("click", () => {
      const payload = mediaAnnotationPayload(card);
      if (!payload) return;
      ensureMediaDrafts().push({ ...payload, draft_id: `draft_${Date.now()}_${Math.random().toString(16).slice(2)}` });
      persistMediaDrafts();
      form.reset();
      delete ensureDetailDrafts()[draftKey];
      persistDetailDrafts();
      refreshMediaDraftControls();
      toast(`已加入整集草稿 · ${payload.location.timecode}`);
    });
  });
  root?.querySelectorAll("[data-submit-media-drafts]").forEach((button) => {
    button.onclick = async () => {
      const drafts = ensureMediaDrafts();
      if (!drafts.length) return;
      const annotations = drafts.map(({ draft_id, ...annotation }) => annotation);
      await sendCommand("annotate.batch", { annotations });
      state.mediaDrafts = [];
      persistMediaDrafts();
      refreshMediaDraftControls();
      toast(`${annotations.length} 条整集标注已集体提交`);
    };
  });
  root?.querySelectorAll("[data-clear-media-drafts]").forEach((button) => {
    button.onclick = () => {
      if (!state.mediaDrafts.length || !window.confirm(`清空 ${state.mediaDrafts.length} 条尚未提交的整集标注草稿？`)) return;
      state.mediaDrafts = [];
      persistMediaDrafts();
      refreshMediaDraftControls();
    };
  });
  root?.querySelectorAll("[data-seek-artifact]").forEach((button) => {
    button.onclick = () => {
      const card = root.querySelector(`[data-media-review][data-artifact-id="${CSS.escape(button.dataset.seekArtifact)}"]`);
      const media = card?.querySelector("video, audio");
      if (!card || !media) return;
      media.pause();
      media.currentTime = Math.max(0, Number(button.dataset.seekTime) || 0);
      card.dataset.annotationTime = String(media.currentTime);
      const marker = card.querySelector("[data-media-position-marker]");
      if (button.dataset.seekX && button.dataset.seekY && marker) {
        marker.style.left = `${Number(button.dataset.seekX) * 100}%`;
        marker.style.top = `${Number(button.dataset.seekY) * 100}%`;
        marker.classList.remove("hidden");
      }
      card.scrollIntoView({ block: "center", behavior: "smooth" });
    };
  });
  refreshMediaDraftControls();
}

function bindTaskDetail(root, task) {
  const form = root?.querySelector("[data-task-annotation-form]");
  if (form) {
    const draftKey = detailFormKey(form, task.task_id);
    form.addEventListener("input", () => {
      ensureDetailDrafts()[draftKey] = {
        body: form.querySelector('textarea[name="body"]')?.value || "",
        severity: form.querySelector('select[name="severity"]')?.value || "note",
      };
      persistDetailDrafts();
    });
    form.onsubmit = async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      const payload = {
        target_id: task.task_id,
        body: String(data.get("body") || ""),
        severity: String(data.get("severity") || "note"),
      };
      const restoreDraft = stageDetailFormSubmission(form, draftKey);
      try {
        await sendCommand("annotate", payload);
      } catch (error) {
        restoreDraft();
        throw error;
      }
    };
  }
  root?.querySelectorAll("[data-resolve-gap-form]").forEach((gapForm) => {
    gapForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const resolution = String(new FormData(gapForm).get("resolution") || "").trim();
      if (!resolution) return;
      await sendCommand("gap.resolve", {
        gap_id: gapForm.dataset.gapId,
        resolution,
      });
    });
  });
  root?.querySelector("[data-record-change]")?.addEventListener("click", () => promptAndSend("change", task.task_id, "描述需要改变的内容：", "reason"));
  root?.querySelector("[data-record-gap]")?.addEventListener("click", () => promptAndSend("gap", task.task_id, "缺少什么输入、能力或授权？", "reason", "task_id"));
  root?.querySelector("[data-human-approve]")?.addEventListener("click", () => sendCommand("human.decide", { task_id: task.task_id, verdict: "approve", note: "Approved in Human UI" }));
  root?.querySelector("[data-human-revise]")?.addEventListener("click", () => promptHumanRevise(task.task_id));
  root?.querySelector("[data-revoke-approval]")?.addEventListener("click", () => promptHumanApprovalReversal(task.task_id));
  bindCapsuleDisclosures(root);
  bindContextWorkspaces(root);
  bindMediaReview(root);
  root?.querySelectorAll("[data-detail-mode-toggle]").forEach(configureDetailModeToggle);
}

function ensureFloatingMediaDock() {
  let dock = $("#mediaDock");
  if (dock) return dock;
  dock = document.createElement("section");
  dock.id = "mediaDock";
  dock.className = "media-dock hidden";
  document.body.append(dock);
  return dock;
}

function openFloatingMedia(artifactId) {
  state.floatingArtifactId = artifactId;
  state.floatingMediaSignature = null;
  refreshFloatingMedia({ focus: true, force: true });
}

function closeFloatingMedia() {
  const dock = $("#mediaDock");
  if (dock && !dock.classList.contains("hidden")) captureTaskDetailSession(dock, dock.dataset.detailTaskId);
  state.floatingArtifactId = null;
  state.floatingMediaSignature = null;
  if (dock) delete dock.dataset.detailTaskId;
  dock?.classList.add("hidden");
}

function installFloatingMediaInteractions(dock) {
  const head = dock.querySelector(".media-dock-head");
  if (!head) return;
  head.onpointerdown = (event) => {
    if (event.button !== 0 || event.target.closest("button")) return;
    event.preventDefault();
    const rect = dock.getBoundingClientRect();
    const offsetX = event.clientX - rect.left;
    const offsetY = event.clientY - rect.top;
    head.setPointerCapture?.(event.pointerId);
    const move = (moveEvent) => {
      const width = dock.offsetWidth;
      const height = dock.offsetHeight;
      dock.style.left = `${Math.max(8, Math.min(window.innerWidth - width - 8, moveEvent.clientX - offsetX))}px`;
      dock.style.top = `${Math.max(8, Math.min(window.innerHeight - height - 8, moveEvent.clientY - offsetY))}px`;
      dock.style.right = "auto";
      dock.style.bottom = "auto";
    };
    const stop = () => {
      head.removeEventListener("pointermove", move);
      head.removeEventListener("pointerup", stop);
      head.removeEventListener("pointercancel", stop);
    };
    head.addEventListener("pointermove", move);
    head.addEventListener("pointerup", stop);
    head.addEventListener("pointercancel", stop);
  };
  dock.querySelector("[data-media-dock-smaller]")?.addEventListener("click", () => {
    dock.style.width = `${Math.max(420, dock.offsetWidth - 120)}px`;
    dock.style.height = `${Math.max(360, dock.offsetHeight - 90)}px`;
  });
  dock.querySelector("[data-media-dock-larger]")?.addEventListener("click", () => {
    dock.style.width = `${Math.min(window.innerWidth - 24, dock.offsetWidth + 120)}px`;
    dock.style.height = `${Math.min(window.innerHeight - 24, dock.offsetHeight + 90)}px`;
  });
  dock.querySelector("[data-media-dock-close]")?.addEventListener("click", closeFloatingMedia);
}

function refreshFloatingMedia({ focus = false, force = false } = {}) {
  if (!state.floatingArtifactId || !state.overview) return;
  const artifact = (state.overview.artifacts || []).find((item) => item.artifact_id === state.floatingArtifactId);
  if (!artifact || !mediaKindForArtifact(artifact)) {
    closeFloatingMedia();
    return;
  }
  const task = (state.overview.tasks || []).find((item) => item.task_id === artifact.producer_task_id);
  const annotations = state.overview.annotations || [];
  const dock = ensureFloatingMediaDock();
  const relevantAnnotations = annotations.filter((item) => item.target_id === artifact.artifact_id);
  const signature = JSON.stringify({
    artifact: [artifact.artifact_id, artifact.status, artifact.sha256, artifact.size, artifact.path],
    annotations: relevantAnnotations.map((item) => [item.annotation_id, item.status, item.severity, item.body, item.location]),
  });
  if (!force && state.floatingMediaSignature === signature && !dock.classList.contains("hidden")) return;
  captureTaskDetailSession(dock, dock.dataset.detailTaskId);
  dock.innerHTML = `<header class="media-dock-head"><div><span>FLOATING REVIEW</span><b>${escapeHtml(task?.task_id || artifact.producer_task_id || "制品")} · ${escapeHtml(artifact.role || mediaKindForArtifact(artifact))}</b></div><div class="media-dock-actions"><button type="button" data-media-dock-smaller aria-label="缩小浮动审片窗">−</button><button type="button" data-media-dock-larger aria-label="放大浮动审片窗">＋</button><button type="button" data-media-dock-close aria-label="关闭浮动审片窗">×</button></div></header><div class="media-dock-scroll">${mediaReviewMarkup([artifact], annotations, { floating: true })}</div>`;
  dock.dataset.detailTaskId = task?.task_id || artifact.producer_task_id || "media";
  state.floatingMediaSignature = signature;
  dock.classList.remove("hidden");
  bindMediaReview(dock);
  installFloatingMediaInteractions(dock);
  restoreTaskDetailSession(dock, dock.dataset.detailTaskId);
  if (focus) dock.querySelector("video, audio")?.focus({ preventScroll: true });
}

function renderInspector() {
  const task = (state.overview.tasks || []).find((item) => item.task_id === state.selectedTaskId);
  const inspectorBody = $("#inspectorBody");
  if (!inspectorBody) return;
  const desiredSignature = !task
    ? "empty"
    : effectiveDetailMode() === "peek"
      ? `peek:${task.task_id}`
      : `detail:${taskDetailSignature(task)}`;
  if (state.inspectorSignature === desiredSignature) return;
  captureTaskDetailSession(inspectorBody, inspectorBody?.dataset.detailTaskId);
  if (!task) {
    inspectorBody.innerHTML = `<div class="inspector-empty"><div class="selection-glyph">↗</div><h3>选择一个任务</h3><p>查看它为什么处于当前状态、消费了哪些上下文、允许执行哪些动作。</p></div>`;
    delete inspectorBody.dataset.detailTaskId;
    state.inspectorSignature = desiredSignature;
    return;
  }
  if (effectiveDetailMode() === "peek") {
    inspectorBody.innerHTML = `<div class="inspector-empty"><div class="selection-glyph">◌</div><h3>${escapeHtml(task.task_id)} 已在气泡中打开</h3><p>使用标题栏的图形开关可把同一份完整任务详情移到侧栏。</p></div>`;
    delete inspectorBody.dataset.detailTaskId;
    state.inspectorSignature = desiredSignature;
    return;
  }
  inspectorBody.innerHTML = taskDetailMarkup(task);
  inspectorBody.dataset.detailTaskId = task.task_id;
  state.inspectorSignature = desiredSignature;
  bindTaskDetail(inspectorBody, task);
  restoreTaskDetailSession(inspectorBody, task.task_id);
}

function requestText({ title, label, confirmLabel = "确认", danger = false }) {
  let dialog = $("#textRequestDialog");
  if (!dialog) {
    dialog = document.createElement("dialog");
    dialog.id = "textRequestDialog";
    dialog.className = "text-request-dialog";
    document.body.append(dialog);
  }
  return new Promise((resolve) => {
    dialog.innerHTML = `<form method="dialog"><header><span>HUMAN INPUT</span><h3>${escapeHtml(title)}</h3></header><label>${escapeHtml(label)}<textarea name="value" required autofocus></textarea></label><footer><button type="button" data-request-cancel>取消</button><button class="${danger ? "danger-button" : "primary-button"}" type="submit">${escapeHtml(confirmLabel)}</button></footer></form>`;
    const form = dialog.querySelector("form");
    const textarea = dialog.querySelector("textarea");
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      if (dialog.open) dialog.close();
      resolve(value);
    };
    dialog.querySelector("[data-request-cancel]").onclick = () => finish(null);
    dialog.oncancel = (event) => { event.preventDefault(); finish(null); };
    form.onsubmit = (event) => { event.preventDefault(); finish(textarea.value.trim() || null); };
    dialog.showModal();
    requestAnimationFrame(() => textarea.focus({ preventScroll: true }));
  });
}

async function promptAndSend(command, targetId, label, textField, targetField = "target_id") {
  const text = await requestText({ title: command === "gap" ? "报告缺口" : "记录变更", label, confirmLabel: "写入状态" });
  if (!text?.trim()) return;
  await sendCommand(command, { [targetField]: targetId, [textField]: text.trim() });
}

async function promptHumanRevise(taskId) {
  const note = await requestText({ title: "打回返修", label: "说明需要修改的内容：", confirmLabel: "确认打回", danger: true });
  if (!note?.trim()) return;
  await sendCommand("human.decide", { task_id: taskId, verdict: "revise", note: note.trim() });
}

async function promptHumanApprovalReversal(taskId) {
  const reason = await requestText({
    title: "撤销批准并打回",
    label: "说明为什么改变决定，以及需要修改什么：",
    confirmLabel: "撤销批准",
    danger: true,
  });
  if (!reason?.trim()) return;
  await sendCommand("change", {
    target_id: taskId,
    reason: reason.trim(),
    kind: "human_approval_reversed",
  });
}

async function sendCommand(command, argumentsPayload) {
  try {
    const result = await api("/api/command", {
      method: "POST",
      body: JSON.stringify({
        command,
        episode_id: state.episodeId,
        actor: "human-ui",
        request_id: `ui_${Date.now()}_${Math.random().toString(16).slice(2)}`,
        arguments: argumentsPayload,
      }),
    });
    toast(`${command} 已记录`, "success");
    await loadEpisode({ preserveEvents: true });
    return result;
  } catch (error) {
    toast(`${error.payload?.code || "操作失败"}：${error.message}`, "error");
    throw error;
  }
}

function renderRisk() {
  const scan = state.scan || { anomalies: [], repairable_count: 0, manual_count: 0 };
  const openGaps = (state.overview?.gaps || []).filter((item) => item.status === "open");
  const openChanges = (state.overview?.changes || []).filter((item) => item.status !== "resolved");
  const agentFindingKinds = new Set(["offline_unknown", "legal_idle", "effective_work", "fake_busy_duplicate_work", "stagnant_work"]);
  const historicalFindings = scan.anomalies.filter((item) => item.kind.startsWith("historical_artifact_"));
  const agentFindings = scan.anomalies.filter((item) => agentFindingKinds.has(item.kind));
  const currentFindings = scan.anomalies.filter((item) => !item.kind.startsWith("historical_artifact_") && !agentFindingKinds.has(item.kind));
  $("#riskSummary").innerHTML = `
    <div class="risk-stat"><span>当前链路发现</span><strong>${currentFindings.length}</strong><small>需要判断是否影响正在做的任务</small></div>
    <div class="risk-stat actionable"><span>可局部修复</span><strong>${scan.repairable_count || 0}</strong><small>点击“预览修复方案”后才能应用</small></div>
    <div class="risk-stat"><span>历史只读记录</span><strong>${historicalFindings.length}</strong><small>用于审计，不会阻塞当前生产</small></div>
    <div class="risk-stat"><span>Agent 信号待确认</span><strong>${agentFindings.length}</strong><small>不是故障结论；需要健康探测才能判断</small></div>`;
  const knownItems = [
    ...openGaps.map((item) => ({ kind: "known_gap", subject_id: item.task_id, proposed_action: item.reason, repairable: false, facts: { gap_id: item.gap_id, status: item.status } })),
    ...openChanges.map((item) => ({ kind: "known_change", subject_id: item.task_id, proposed_action: item.reason, repairable: false, facts: { change_id: item.change_id, status: item.status } })),
  ];
  $("#anomalyList").innerHTML = [...scan.anomalies, ...knownItems].map((item) => {
    const copy = riskCopy(item);
    const badge = item.repairable ? "可局部修复" : item.kind.startsWith("historical_artifact_") ? "历史只读" : item.kind.startsWith("known_") ? "已登记" : "需要判断";
    return `<article class="anomaly ${item.repairable ? "actionable" : ""}">
      <div class="anomaly-signal" data-tone="${escapeHtml(copy.tone)}"><i></i><span>${escapeHtml(copy.scope)}</span></div>
      <div class="anomaly-copy"><h3>${escapeHtml(copy.title)}</h3><p>${escapeHtml(copy.summary)}</p><small>对象：${escapeHtml(item.subject_id)}</small>
        <details><summary>查看技术证据</summary><pre>${escapeHtml(JSON.stringify({ kind: item.kind, proposed_action: item.proposed_action, facts: item.facts }, null, 2))}</pre></details>
      </div>
      <span class="repairable">${badge}</span>
    </article>`;
  }).join("") || `<div class="next-empty"><div><span class="eyebrow">NO ANOMALY</span><h2>当前状态没有需要处理的异常</h2><p>如需核对磁盘上的全部制品，再运行“完整制品核验”。</p></div></div>`;
}

function riskCopy(item) {
  const copies = {
    historical_artifact_false_block: {
      title: "历史制品误阻塞了当前任务",
      summary: "系统将移除无效阻塞；如果没有其他阻塞，任务回到可返工状态。历史记录不会删除。",
      scope: "当前任务",
      tone: "danger",
    },
    historical_artifact_hash_drift: {
      title: "历史版本与磁盘文件不同",
      summary: "这是旧版本的审计记录，不属于当前候选，不会阻塞正在进行的任务。",
      scope: "历史证据",
      tone: "quiet",
    },
    historical_artifact_missing: {
      title: "历史版本的文件已不在原位置",
      summary: "保留这条审计发现，但不把它当作当前生产故障。",
      scope: "历史证据",
      tone: "quiet",
    },
    artifact_hash_drift: {
      title: "当前候选文件与签名不一致",
      summary: "当前候选不能继续流转；修复会隔离制品并只阻塞它的生产任务。",
      scope: "当前制品",
      tone: "danger",
    },
    artifact_missing: {
      title: "当前候选文件缺失",
      summary: "当前候选不能继续流转；修复会隔离制品并只阻塞它的生产任务。",
      scope: "当前制品",
      tone: "danger",
    },
    orphan_live_lease: {
      title: "任务已停止，但仍留有执行租约",
      summary: "修复只释放这张孤立租约，不会改动其他任务。",
      scope: "执行租约",
      tone: "warning",
    },
    expired_lease: {
      title: "执行租约已过期",
      summary: "修复会把该任务退回返工队列，等待重新领取。",
      scope: "执行租约",
      tone: "warning",
    },
    working_without_lease: {
      title: "任务显示执行中，但没有有效租约",
      summary: "修复会把该任务退回返工队列，防止出现假进行中状态。",
      scope: "执行状态",
      tone: "warning",
    },
    resolved_upstream_invalidation: {
      title: "上游已经重新批准，下游仍停在旧阻塞",
      summary: "修复会移除已满足的上游阻塞，让下游重新进入流动队列。",
      scope: "任务依赖",
      tone: "warning",
    },
    known_gap: {
      title: "任务已登记缺口",
      summary: String(item.proposed_action || "等待缺口解决。"),
      scope: "已知阻塞",
      tone: "warning",
    },
    known_change: {
      title: "任务有尚未闭合的变更",
      summary: String(item.proposed_action || "等待变更闭合。"),
      scope: "已知变更",
      tone: "warning",
    },
    offline_unknown: {
      title: "Agent 最近没有上报在线心跳",
      summary: "这只表示监督系统暂时没有新的在线信号，不等于 Agent 已停止；先做健康探测，再考虑替换。",
      scope: "Agent 在线信号",
      tone: "quiet",
    },
    fake_busy_duplicate_work: {
      title: "Agent 的工作可能是重复劳动",
      summary: "检测到它在生成已经存在的同类证据；需要人工确认任务是否真的新增了价值。",
      scope: "工作有效性",
      tone: "danger",
    },
    stagnant_work: {
      title: "Agent 长时间没有产生有效进展",
      summary: "租约仍在，但没有新的可验证证据。先检查阻塞与上下文，再决定返工或终止。",
      scope: "工作有效性",
      tone: "warning",
    },
  };
  return copies[item.kind] || {
    title: String(item.kind || "发现异常").replaceAll("_", " "),
    summary: item.repairable ? "可以在预览后执行局部恢复。" : "这是一条只读诊断，需要结合任务上下文判断。",
    scope: item.repairable ? "局部状态" : "诊断记录",
    tone: item.repairable ? "warning" : "quiet",
  };
}

function openRepairPreview() {
  const repairs = (state.scan?.anomalies || []).filter((item) => item.repairable);
  if (!repairs.length) {
    toast("当前没有可应用的局部修复", "error");
    return;
  }
  $("#repairPreviewList").innerHTML = repairs.map((item, index) => {
    const copy = riskCopy(item);
    return `<article><b>${index + 1}</b><div><strong>${escapeHtml(copy.title)}</strong><p>${escapeHtml(copy.summary)}</p><small>${escapeHtml(item.subject_id)} · ${escapeHtml(item.proposed_action)}</small></div></article>`;
  }).join("");
  $("#repairPreviewApply").textContent = `③ 应用以上 ${repairs.length} 项局部修复`;
  $("#repairPreviewDialog").showModal();
}

function renderEvents() {
  const events = [...state.events].sort((a, b) => b.seq - a.seq);
  $("#eventTimeline").innerHTML = events.map((event) => `
    <div class="event-row">
      <div class="event-seq">#${event.seq}</div>
      <div class="event-type">${escapeHtml(event.event_type)}</div>
      <div class="event-subject">${escapeHtml(event.aggregate_type)} · ${escapeHtml(event.aggregate_id)} · v${event.aggregate_version}</div>
      <div class="event-actor">${escapeHtml(event.actor)}</div>
    </div>`).join("") || `<div class="next-empty">暂无事件</div>`;
}

function graphClosure(taskId) {
  const tasks = state.overview?.tasks || [];
  const byId = Object.fromEntries(tasks.map((task) => [task.task_id, task]));
  const downstream = {};
  tasks.forEach((task) => (task.dependencies || []).forEach((dependency) => {
    (downstream[dependency] ||= []).push(task.task_id);
  }));
  const related = new Set(taskId ? [taskId] : []);
  const visit = (id, direction) => {
    const nextIds = direction === "up" ? (byId[id]?.dependencies || []) : (downstream[id] || []);
    nextIds.forEach((nextId) => {
      if (related.has(nextId)) return;
      related.add(nextId);
      visit(nextId, direction);
    });
  };
  if (taskId) { visit(taskId, "up"); visit(taskId, "down"); }
  return related;
}

function workSurfaceTaskIds() {
  const tasks = state.overview?.tasks || [];
  const byId = Object.fromEntries(tasks.map((task) => [task.task_id, task]));
  const downstream = {};
  tasks.forEach((task) => (task.dependencies || []).forEach((dependency) => ((downstream[dependency] ||= []).push(task.task_id))));
  const seeds = new Set();
  state.flow.expandedForecastTaskIds.forEach((taskId) => {
    if (byId[taskId]) seeds.add(taskId);
  });
  const nextTaskId = state.next?.next?.task?.task_id;
  if (nextTaskId && byId[nextTaskId]) seeds.add(nextTaskId);
  tasks.filter((task) => ["working", "candidate", "user_review_pending", "blocked", "rework"].includes(task.status)).forEach((task) => seeds.add(task.task_id));
  if (!seeds.size) tasks.filter((task) => task.derived?.runnable).slice(0, 3).forEach((task) => seeds.add(task.task_id));
  const visible = new Set(seeds);
  [...seeds].forEach((id) => {
    (byId[id]?.dependencies || []).forEach((dependency) => visible.add(dependency));
    (downstream[id] || []).forEach((child) => visible.add(child));
  });
  return visible;
}

function taskGraphLayout() {
  const allTasks = state.overview?.tasks || [];
  let visibleIds = new Set(allTasks.map((task) => task.task_id));
  if (state.flow.scopeTaskIds?.length) visibleIds = new Set(state.flow.scopeTaskIds);
  if (state.flow.filter === "frontier") {
    const frontier = workSurfaceTaskIds();
    visibleIds = new Set([...visibleIds].filter((id) => frontier.has(id)));
  }
  if (state.flow.filter === "focus" && state.selectedTaskId) {
    const closure = graphClosure(state.selectedTaskId);
    visibleIds = new Set([...visibleIds].filter((id) => closure.has(id)));
  }
  const tasks = allTasks.filter((task) => visibleIds.has(task.task_id));
  const byId = Object.fromEntries(tasks.map((task) => [task.task_id, task]));
  const rankMemo = {};
  const rankOf = (taskId, stack = new Set()) => {
    if (rankMemo[taskId] !== undefined) return rankMemo[taskId];
    if (stack.has(taskId)) return 0;
    const nextStack = new Set(stack).add(taskId);
    const dependencies = (byId[taskId]?.dependencies || []).filter((id) => byId[id]);
    const rank = dependencies.length ? 1 + Math.max(...dependencies.map((id) => rankOf(id, nextStack))) : 0;
    rankMemo[taskId] = rank;
    return rank;
  };
  tasks.forEach((task) => rankOf(task.task_id));

  const deliverableById = Object.fromEntries((state.overview?.scope?.deliverables || state.overview?.deliverables || []).map((item) => [item.deliverable_id, item]));
  const waveById = Object.fromEntries((state.overview?.hierarchy || []).map((item) => [item.wave_id, item]));
  const groupKey = (task) => task.deliverable_id || task.wave_id || "unassigned";
  const groups = {};
  tasks.forEach((task) => (groups[groupKey(task)] ||= []).push(task));
  const orderedGroupIds = Object.keys(groups).sort((a, b) => {
    const left = deliverableById[a] || waveById[a] || {};
    const right = deliverableById[b] || waveById[b] || {};
    return (Number(left.order || 0) - Number(right.order || 0)) || a.localeCompare(b);
  });
  const annotations = state.overview?.annotations || [];
  const artifactIdsByTask = {};
  (state.overview?.artifacts || []).forEach((artifact) => ((artifactIdsByTask[artifact.producer_task_id] ||= new Set()).add(artifact.artifact_id)));
  const returns = state.overview?.returns || [];
  const leases = Object.fromEntries((state.overview?.leases || []).map((item) => [item.task_id, item]));
  const nodeW = 268;
  const nodeH = 108;
  const colGap = 150;
  const rowGap = 16;
  const marginX = 78;
  const marginY = 56;
  const maxRank = Math.max(0, ...tasks.map((task) => rankMemo[task.task_id] || 0));
  const graphWidth = marginX * 2 + (maxRank + 1) * nodeW + maxRank * colGap;
  const groupOrder = Object.fromEntries(orderedGroupIds.map((id, index) => [id, index]));
  const byRank = {};
  tasks.forEach((task) => (byRank[rankMemo[task.task_id] || 0] ||= []).push(task));
  Object.values(byRank).forEach((items) => items.sort((left, right) => {
    const groupDelta = (groupOrder[groupKey(left)] ?? 999) - (groupOrder[groupKey(right)] ?? 999);
    if (groupDelta) return groupDelta;
    return `${left.content_unit_id || left.scene_id || ""}:${left.task_id}`.localeCompare(`${right.content_unit_id || right.scene_id || ""}:${right.task_id}`);
  }));
  const maxRows = Math.max(1, ...Object.values(byRank).map((items) => items.length));
  const graphHeight = marginY * 2 + maxRows * nodeH + Math.max(0, maxRows - 1) * rowGap;
  const columns = Array.from({ length: maxRank + 1 }, (_, rank) => ({
    x: marginX + rank * (nodeW + colGap),
    y: 36,
    title: rank === 0 ? "上游输入" : rank === maxRank ? "集成与交付" : `并行工作层 ${rank}`,
  }));
  const nodes = [];
  Object.entries(byRank).forEach(([rankText, items]) => {
    const rank = Number(rankText);
    const columnHeight = items.length * nodeH + Math.max(0, items.length - 1) * rowGap;
    const startY = marginY + (graphHeight - marginY * 2 - columnHeight) / 2;
    items.forEach((task, index) => {
      const groupId = groupKey(task);
      const group = deliverableById[groupId] || waveById[groupId] || { title: groupId };
      const annotationTargets = artifactIdsByTask[task.task_id] || new Set();
      const annotationCount = annotations.filter((item) => item.target_id === task.task_id || annotationTargets.has(item.target_id)).length;
      const taskReturns = returns.filter((item) => item.task_id === task.task_id && item.status === "pending");
      nodes.push({
        type: "task",
        id: task.task_id,
        task,
        groupTitle: group.title || groupId,
        x: marginX + rank * (nodeW + colGap),
        y: startY + index * (nodeH + rowGap),
        width: nodeW,
        height: nodeH,
        lease: leases[task.task_id],
        annotationCount,
        returnCount: taskReturns.length,
      });
    });
  });
  const nodeById = Object.fromEntries(nodes.map((node) => [node.id, node]));
  const edges = [];
  tasks.forEach((task) => (task.dependencies || []).forEach((dependencyId) => {
    if (!nodeById[dependencyId] || !nodeById[task.task_id]) return;
    const producer = byId[dependencyId];
    edges.push({
      id: `dep:${dependencyId}:${task.task_id}`,
      source: dependencyId,
      target: task.task_id,
      type: "data",
      label: (producer.output_contract?.required_artifact_roles || []).join(" · ") || "dependency",
    });
  }));
  (state.overview?.routes || []).forEach((route) => {
    if (!nodeById[route.replaced_task_id] || !nodeById[route.replacement_task_id]) return;
    edges.push({
      id: `route:${route.route_switch_id}`,
      source: route.replaced_task_id,
      target: route.replacement_task_id,
      type: "route",
      label: route.strategy,
    });
  });
  returns.filter((item) => item.status === "pending" && nodeById[item.task_id]).forEach((ticket) => {
    edges.push({ id: `return:${ticket.return_ticket_id}`, source: ticket.task_id, target: ticket.task_id, type: "review", label: `返修 → ${ticket.assigned_to}` });
  });
  return { type: "task", width: graphWidth, height: Math.max(420, graphHeight), nodes, edges, bands: [], columns };
}

function axisRanks(nodes, edges, idKey, parentKey) {
  const byId = Object.fromEntries(nodes.map((node) => [node[idKey], node]));
  const incoming = {};
  edges.forEach((edge) => ((incoming[edge.target_id] ||= []).push(edge.source_id)));
  const memo = {};
  const visit = (id, stack = new Set()) => {
    if (memo[id] !== undefined) return memo[id];
    if (stack.has(id)) return 0;
    const node = byId[id] || {};
    const parents = [...(incoming[id] || [])];
    if (node[parentKey]) parents.push(node[parentKey]);
    const valid = [...new Set(parents)].filter((parent) => byId[parent]);
    const rank = valid.length ? 1 + Math.max(...valid.map((parent) => visit(parent, new Set(stack).add(id)))) : 0;
    memo[id] = rank;
    return rank;
  };
  nodes.forEach((node) => visit(node[idKey]));
  return memo;
}

function macroGraphLayout() {
  const scope = state.overview?.scope || {};
  const deliverables = scope.deliverables || [];
  const contentUnits = scope.content_units || [];
  const nodeW = 250;
  const nodeH = 126;
  const colGap = 90;
  const rowGap = 22;
  const dRanks = axisRanks(deliverables, scope.deliverable_edges || [], "deliverable_id", "parent_deliverable_id");
  const cRanks = axisRanks(contentUnits, scope.content_edges || [], "unit_id", "parent_unit_id");
  const placeAxis = (items, ranks, idKey, yBase, prefix) => {
    const columns = {};
    items.forEach((item) => ((columns[ranks[item[idKey]] || 0] ||= []).push(item)));
    const nodes = [];
    Object.entries(columns).forEach(([rankText, column]) => {
      column.sort((a, b) => (Number(a.order || 0) - Number(b.order || 0)) || String(a[idKey]).localeCompare(String(b[idKey])));
      column.forEach((item, index) => nodes.push({
        type: "macro",
        axis: prefix,
        id: `${prefix}:${item[idKey]}`,
        scopeId: item[idKey],
        item,
        x: 64 + Number(rankText) * (nodeW + colGap),
        y: yBase + index * (nodeH + rowGap),
        width: nodeW,
        height: nodeH,
      }));
    });
    const height = Math.max(nodeH, ...nodes.map((node) => node.y + node.height - yBase));
    return { nodes, height };
  };
  const deliverableAxis = placeAxis(deliverables, dRanks, "deliverable_id", 100, "deliverable");
  const contentY = 100 + deliverableAxis.height + 150;
  const contentAxis = placeAxis(contentUnits, cRanks, "unit_id", contentY, "content");
  const nodes = [...deliverableAxis.nodes, ...contentAxis.nodes];
  const nodeByScope = Object.fromEntries(nodes.map((node) => [`${node.axis}:${node.scopeId}`, node]));
  const edges = [];
  const addAxisEdges = (items, dataEdges, axis, idKey, parentKey) => {
    items.forEach((item) => {
      if (item[parentKey] && nodeByScope[`${axis}:${item[parentKey]}`]) edges.push({ id: `contain:${axis}:${item[parentKey]}:${item[idKey]}`, source: `${axis}:${item[parentKey]}`, target: `${axis}:${item[idKey]}`, type: "control", label: "contains" });
    });
    dataEdges.forEach((edge) => {
      if (!nodeByScope[`${axis}:${edge.source_id}`] || !nodeByScope[`${axis}:${edge.target_id}`]) return;
      edges.push({ id: `macro:${axis}:${edge.source_id}:${edge.target_id}`, source: `${axis}:${edge.source_id}`, target: `${axis}:${edge.target_id}`, type: "data", label: (edge.artifact_roles || []).join(" · ") || `${edge.task_edges?.length || 0} task flows` });
    });
  };
  addAxisEdges(deliverables, scope.deliverable_edges || [], "deliverable", "deliverable_id", "parent_deliverable_id");
  addAxisEdges(contentUnits, scope.content_edges || [], "content", "unit_id", "parent_unit_id");
  const maxRank = Math.max(0, ...Object.values(dRanks), ...Object.values(cRanks));
  const width = Math.max(760, 64 * 2 + (maxRank + 1) * nodeW + maxRank * colGap);
  const height = contentY + contentAxis.height + 70;
  const bands = [
    { id: "deliverable-axis", title: "交付物流 · Deliverable axis", meta: "分组不代表阶段栅栏", x: 14, y: 46, width: width - 28, height: deliverableAxis.height + 98 },
    { id: "content-axis", title: "内容尺度 · Content axis", meta: "整集 → 章节 → 分镜 → 动画片段", x: 14, y: contentY - 54, width: width - 28, height: contentAxis.height + 98 },
  ];
  return { type: "macro", width, height, nodes, edges, bands, episodePhase: scope.episode_phase || "initialized" };
}

function microGraphLayout() {
  const task = (state.overview?.tasks || []).find((item) => item.task_id === state.selectedTaskId);
  if (!task) return { type: "micro", width: 1100, height: 420, nodes: [], edges: [], bands: [], empty: "先在总流程或任务流中选择一个任务。" };
  const lease = (state.overview?.leases || []).find((item) => item.task_id === task.task_id);
  const artifacts = (state.overview?.artifacts || []).filter((item) => item.producer_task_id === task.task_id);
  const gates = (state.overview?.gates || []).filter((item) => item.task_id === task.task_id);
  const returns = (state.overview?.returns || []).filter((item) => item.task_id === task.task_id);
  const changes = (state.overview?.changes || []).filter((item) => item.task_id === task.task_id && item.status !== "resolved");
  const gaps = (state.overview?.gaps || []).filter((item) => item.task_id === task.task_id && item.status === "open");
  const stages = [
    ["contract", "工作合同与上下文", `${task.references?.length || 0} refs · scope r${task.scope_revision || 1}`, ["planned", "rework"].includes(task.status)],
    ["lease", "租约与执行", lease ? `${lease.owner} · g${lease.generation} · ${lease.status}` : "尚未领取", task.status === "working"],
    ["candidate", "候选制品", `${artifacts.length} artifacts · ${task.candidate?.candidate_hash?.slice(0, 10) || "none"}`, task.status === "candidate"],
    ["gate", "程序硬门禁", `${gates.filter((item) => item.status === "pass").length}/${task.required_validators?.length || 0} passed`, task.status === "candidate" && Boolean(task.derived?.missing_validators?.length)],
    ["review", "独立语义审查", task.last_review_id || "waiting", task.status === "candidate" && !task.derived?.missing_validators?.length],
    ["human", "人工授权 / 接受", task.human_gate ? statusLabel(task.status) : "无需额外人审", ["user_review_pending", "approved"].includes(task.status)],
  ];
  const nodes = stages.map(([id, title, detail, active], index) => ({ type: "micro", id, title, detail, active, x: 42 + index * 286, y: 138, width: 236, height: 90 }));
  const edges = stages.slice(1).map((stage, index) => ({ id: `micro:${stages[index][0]}:${stage[0]}`, source: stages[index][0], target: stage[0], type: "data", label: index === 0 ? "capsule" : index === 1 ? "artifact" : "evidence" }));
  if (returns.some((item) => item.status === "pending")) {
    nodes.push({ type: "micro", id: "return", title: "延迟返修票", detail: `${returns.find((item) => item.status === "pending").assigned_to} · attention boundary`, active: task.status === "rework", x: 1190, y: 300, width: 236, height: 90, tone: "return" });
    edges.push({ id: "micro-review-return", source: "review", target: "return", type: "review", label: "revise" });
    edges.push({ id: "micro-return-contract", source: "return", target: "contract", type: "review", label: "deferred" });
  }
  if (changes.length || gaps.length) {
    nodes.push({ type: "micro", id: "exception", title: "变更 / 缺口", detail: `${changes.length} change · ${gaps.length} gap`, active: task.status === "blocked", x: 330, y: 300, width: 236, height: 90, tone: "blocked" });
    edges.push({ id: "micro-exception-contract", source: "exception", target: "contract", type: "review", label: "recompile" });
  }
  return { type: "micro", width: 1740, height: 470, nodes, edges, bands: [], task };
}

function roundedOrthogonalPath(points, radius = 12) {
  if (points.length < 2) return "";
  let path = `M ${points[0][0]} ${points[0][1]}`;
  for (let index = 1; index < points.length - 1; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const next = points[index + 1];
    const incomingLength = Math.hypot(current[0] - previous[0], current[1] - previous[1]);
    const outgoingLength = Math.hypot(next[0] - current[0], next[1] - current[1]);
    const bend = Math.min(radius, incomingLength / 2, outgoingLength / 2);
    const before = [
      current[0] - ((current[0] - previous[0]) / (incomingLength || 1)) * bend,
      current[1] - ((current[1] - previous[1]) / (incomingLength || 1)) * bend,
    ];
    const after = [
      current[0] + ((next[0] - current[0]) / (outgoingLength || 1)) * bend,
      current[1] + ((next[1] - current[1]) / (outgoingLength || 1)) * bend,
    ];
    path += ` L ${before[0]} ${before[1]} Q ${current[0]} ${current[1]} ${after[0]} ${after[1]}`;
  }
  const last = points.at(-1);
  return `${path} L ${last[0]} ${last[1]}`;
}

function graphEdgePath(source, target, edge) {
  if (source.id === target.id) {
    const left = source.x + source.width * 0.32;
    const right = source.x + source.width * 0.72;
    const y = source.y;
    return roundedOrthogonalPath([[right, y], [right, y - 48], [left, y - 48], [left, y]], 10);
  }
  const forward = target.x >= source.x;
  const sx = forward ? source.x + source.width : source.x + source.width * 0.5;
  const sy = forward ? source.y + source.height * 0.5 : source.y + source.height;
  const tx = forward ? target.x : target.x + target.width * 0.5;
  const ty = forward ? target.y + target.height * 0.5 : target.y + target.height;
  if (forward) {
    const channelX = sx + Math.max(48, (tx - sx) * 0.46);
    return roundedOrthogonalPath([[sx, sy], [channelX, sy], [channelX, ty], [tx, ty]], 12);
  }
  const floor = Math.max(source.y + source.height, target.y + target.height) + 58;
  return roundedOrthogonalPath([[sx, sy], [sx, floor], [tx, floor], [tx, ty]], 12);
}

function graphNodeMarkup(node) {
  if (node.type === "task") {
    const task = node.task;
    const scope = node.groupTitle || task.content_unit_id || task.scene_id || "episode";
    const progress = taskStateProgress(task);
    const transitioned = state.flow.transitionTaskIds.has(task.task_id);
    const attentionCount = taskHumanAttentionCount(task);
    return `<g class="flow-node status-${escapeHtml(task.status)} ${state.selectedTaskId === task.task_id ? "selected" : ""} ${transitioned ? "state-transition" : ""}" data-task-id="${escapeHtml(task.task_id)}" role="button" tabindex="0" aria-label="${escapeHtml(`${task.task_id} ${task.title}，${taskStatusLabel(task)}`)}">
      <foreignObject x="${node.x}" y="${node.y}" width="${node.width}" height="${node.height}">
        <div xmlns="http://www.w3.org/1999/xhtml" class="node-shell" style="--state-progress:${progress}%" title="状态轨迹：合同 → 制作 → 候选 → 审查 → 批准">
          <div class="node-top"><span>${escapeHtml(task.task_id)}</span><span class="node-state"><i class="status-dot ${escapeHtml(task.derived?.effective_state || task.status)}"></i>${escapeHtml(taskStatusLabel(task))}</span></div>
          ${attentionCount ? `<span class="node-attention-badge" aria-label="${attentionCount} 项待你处理">${attentionCount}</span>` : ""}
          <h3 title="${escapeHtml(task.title)}">${escapeHtml(task.title)}</h3>
          <p>${escapeHtml(task.goal)}</p>
          <div class="node-foot"><span>${escapeHtml(scope)}</span><span class="owner-chip">${node.lease?.status === "active" ? escapeHtml(node.lease.owner) : "未领取"}</span>${node.returnCount ? `<span class="return-count" title="待返回返修">↩${node.returnCount}</span>` : ""}${node.annotationCount ? `<span class="annotation-count" title="标注">✎${node.annotationCount}</span>` : ""}</div>
        </div>
      </foreignObject>
    </g>`;
  }
  if (node.type === "macro") {
    const derived = node.item.derived || {};
    return `<g class="flow-node macro-node" data-scope-axis="${escapeHtml(node.axis)}" data-scope-id="${escapeHtml(node.scopeId)}" role="button" tabindex="0" aria-label="${escapeHtml(`${node.item.title}，${derived.phase || "empty"}`)}">
      <foreignObject x="${node.x}" y="${node.y}" width="${node.width}" height="${node.height}">
        <div xmlns="http://www.w3.org/1999/xhtml" class="node-shell">
          <div class="node-top"><span>${escapeHtml(node.scopeId)}</span><span class="node-state">${escapeHtml(derived.phase || "empty")}</span></div>
          <h3 title="${escapeHtml(node.item.title)}">${escapeHtml(node.item.title)}</h3>
          <div class="macro-progress"><i style="width:${Math.round((derived.progress || 0) * 100)}%"></i></div>
          <div class="macro-metrics"><span>${derived.approved || 0}/${derived.total || 0} 已批准</span><span>${derived.ready || 0} 可执行</span><span>${(derived.active_agents || []).length} 人工作中</span></div>
        </div>
      </foreignObject>
    </g>`;
  }
  return `<g class="flow-node micro-node">
    <foreignObject x="${node.x}" y="${node.y}" width="${node.width}" height="${node.height}">
      <div xmlns="http://www.w3.org/1999/xhtml" class="micro-card ${node.active ? "active" : ""} ${escapeHtml(node.tone || "")}">
        <span>${escapeHtml(node.id)}</span><h3>${escapeHtml(node.title)}</h3><p>${escapeHtml(node.detail)}</p>
      </div>
    </foreignObject>
  </g>`;
}

function taskStateProgress(task) {
  const status = task?.status || "planned";
  return {
    planned: task?.derived?.runnable ? 18 : 8,
    working: 38,
    candidate: 58,
    rework: 48,
    blocked: 24,
    user_review_pending: 82,
    approved: 100,
    superseded: 0,
    cancelled: 0,
  }[status] ?? 8;
}

function setFlowTransform() {
  const world = document.querySelector("#flowWorld");
  if (!world) return;
  const { x, y, k } = state.flow.transform;
  world.setAttribute("transform", `translate(${x} ${y}) scale(${k})`);
  updateFlowMinimapViewport();
}

function reactFlowWheelDelta(event) {
  const unit = event.deltaMode === 1 ? 0.05 : event.deltaMode ? 1 : 0.002;
  return -event.deltaY * unit * (event.ctrlKey || event.metaKey ? 10 : 1);
}

function zoomFlowAt(nextZoom, anchor = {}) {
  const viewport = $("#flowViewport");
  if (!viewport) return;
  const rect = viewport.getBoundingClientRect();
  const px = Number.isFinite(anchor.clientX) ? anchor.clientX - rect.left : viewport.clientWidth / 2;
  const py = Number.isFinite(anchor.clientY) ? anchor.clientY - rect.top : viewport.clientHeight / 2;
  const oldZoom = state.flow.transform.k;
  const next = Math.max(FLOW_ZOOM_MIN, Math.min(FLOW_ZOOM_MAX, nextZoom));
  const worldX = (px - state.flow.transform.x) / oldZoom;
  const worldY = (py - state.flow.transform.y) / oldZoom;
  state.flow.transform.k = next;
  state.flow.transform.x = px - worldX * next;
  state.flow.transform.y = py - worldY * next;
  setFlowTransform();
}

async function toggleGraphFullscreen(element) {
  if (!element) return;
  const opening = !element.classList.contains("graph-fullscreen");
  $$(".graph-fullscreen").forEach((item) => item.classList.remove("graph-fullscreen"));
  element.classList.toggle("graph-fullscreen", opening);
  document.body.classList.toggle("graph-fullscreen-open", opening);
  if (opening) {
    $(".hierarchy-panel")?.classList.remove("open");
    $(".inspector-panel")?.classList.remove("open");
    syncDrawerState();
    renderInspector();
  }
  renderDetailModeToggle();
  window.setTimeout(() => {
    if (element.id === "flowViewport") fitFlow();
    if (element.id === "executionMapFrame") fitForecast();
    if (state.selectedTaskId) {
      if (opening) {
        const anchor = currentTaskAnchor(state.selectedTaskId, element.id === "flowViewport" ? "#flowViewport" : "#executionMap", state.peekAnchor);
        const rect = anchor?.rect || state.peekAnchor || { left: window.innerWidth / 2, right: window.innerWidth / 2, top: window.innerHeight / 2, bottom: window.innerHeight / 2, width: 0, height: 0 };
        state.peekAnchor = { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: rect.width, height: rect.height };
        renderTaskPeek(state.selectedTaskId, state.peekAnchor, { focus: false });
      } else if (state.detailMode === "sidebar" && !$("#taskPeek")?.classList.contains("hidden")) {
        openInspector();
      }
    }
  }, 80);
}

function updateFlowMinimapViewport() {
  const viewport = $("#flowViewport");
  const viewportRect = $("#flowMinimapViewport");
  const layout = state.flow.layout;
  if (!viewport || !viewportRect || !layout) return;
  const { x, y, k } = state.flow.transform;
  const left = Math.max(0, -x / k);
  const top = Math.max(0, -y / k);
  const right = Math.min(layout.width, (viewport.clientWidth - x) / k);
  const bottom = Math.min(layout.height, (viewport.clientHeight - y) / k);
  viewportRect.setAttribute("x", String(left));
  viewportRect.setAttribute("y", String(top));
  viewportRect.setAttribute("width", String(Math.max(0, right - left)));
  viewportRect.setAttribute("height", String(Math.max(0, bottom - top)));
}

function renderFlowMinimap(layout) {
  const minimap = $("#flowMinimap");
  if (!minimap) return;
  minimap.classList.toggle("hidden", !layout?.nodes?.length || layout.nodes.length <= 4);
  if (!layout?.nodes?.length) {
    minimap.innerHTML = "";
    return;
  }
  const nodes = Object.fromEntries(layout.nodes.map((node) => [node.id, node]));
  const bands = (layout.bands || []).map((band) => `<rect class="mini-band" x="${band.x}" y="${band.y}" width="${band.width}" height="${band.height}" rx="10"/>`).join("");
  const edges = (layout.edges || []).map((edge) => {
    const source = nodes[edge.source];
    const target = nodes[edge.target];
    if (!source || !target) return "";
    return `<line class="mini-edge" x1="${source.x + source.width / 2}" y1="${source.y + source.height / 2}" x2="${target.x + target.width / 2}" y2="${target.y + target.height / 2}"/>`;
  }).join("");
  const nodeMarkup = layout.nodes.map((node) => {
    const status = node.type === "task" ? node.task?.status : node.type === "macro" ? node.item?.derived?.phase : node.active ? "working" : "planned";
    return `<rect class="mini-node ${escapeHtml(status || "planned")}" x="${node.x}" y="${node.y}" width="${node.width}" height="${node.height}" rx="8"/>`;
  }).join("");
  minimap.innerHTML = `<svg viewBox="0 0 ${layout.width} ${layout.height}" preserveAspectRatio="xMidYMid meet" aria-hidden="true"><text class="mini-label" x="22" y="38">OVERVIEW</text>${bands}${edges}${nodeMarkup}<rect id="flowMinimapViewport" class="mini-viewport" rx="8"/></svg>`;
  updateFlowMinimapViewport();
}

function flowMinimapWorldPoint(event) {
  const svg = $("#flowMinimap svg");
  if (!svg?.getScreenCTM()) return null;
  const point = svg.createSVGPoint();
  point.x = event.clientX;
  point.y = event.clientY;
  return point.matrixTransform(svg.getScreenCTM().inverse());
}

function centerFlowAt(worldPoint) {
  const viewport = $("#flowViewport");
  if (!viewport || !worldPoint) return;
  state.flow.transform.x = viewport.clientWidth / 2 - worldPoint.x * state.flow.transform.k;
  state.flow.transform.y = viewport.clientHeight / 2 - worldPoint.y * state.flow.transform.k;
  setFlowTransform();
}

function fitFlow() {
  const viewport = $("#flowViewport");
  const layout = state.flow.layout;
  if (!viewport || !layout || !viewport.clientWidth || !viewport.clientHeight) return;
  const padding = 54;
  const k = Math.max(FLOW_ZOOM_MIN, Math.min(1.15, (viewport.clientWidth - padding * 2) / layout.width, (viewport.clientHeight - padding * 2) / layout.height));
  state.flow.transform = {
    k,
    x: (viewport.clientWidth - layout.width * k) / 2,
    y: (viewport.clientHeight - layout.height * k) / 2,
  };
  setFlowTransform();
  renderFlowMinimap(layout);
}

function updateFlowButtons() {
  const modes = { macro: "#flowMacroMode", task: "#flowTaskMode", micro: "#flowMicroMode" };
  Object.entries(modes).forEach(([mode, selector]) => $(selector)?.classList.toggle("active", state.flow.mode === mode));
  $("#flowShowAll")?.classList.toggle("active", state.flow.presentation === "overview");
  $("#flowShowFocus")?.classList.toggle("active", state.flow.presentation === "layered");
  $(".graph-more")?.classList.toggle("active", state.flow.presentation === "overview" || Boolean(state.flow.scopeTaskIds?.length));
}

function edgeDetailMarkup(edge, x, y, visible = false) {
  if (!edge.label) return "";
  const label = edge.label.slice(0, 24);
  const width = Math.min(164, Math.max(62, label.length * 6.2 + 20));
  return `<g class="edge-detail ${visible ? "visible" : ""}" transform="translate(${x} ${y})"><rect x="${-width / 2}" y="-12" width="${width}" height="24" rx="12"/><text text-anchor="middle" y="3">${escapeHtml(label)}</text></g>`;
}

function renderGraphEdges(layout, nodeById, related, focused) {
  const edgeIsSignalling = (edge) => state.flow.transitionTaskIds.has(edge.source) || state.flow.transitionTaskIds.has(edge.target);
  const sourceGroups = {};
  (layout.edges || []).forEach((edge) => {
    const source = nodeById[edge.source];
    const target = nodeById[edge.target];
    if (edge.type !== "data" || !source || !target || source.id === target.id || target.x <= source.x + source.width) return;
    (sourceGroups[edge.source] ||= []).push(edge);
  });
  const bundled = new Set();
  const output = [];
  Object.entries(sourceGroups).forEach(([sourceId, group], groupIndex) => {
    if (group.length < 2) return;
    const source = nodeById[sourceId];
    const targets = group.map((edge) => nodeById[edge.target]).filter(Boolean);
    const sourceX = source.x + source.width;
    const sourceY = source.y + source.height / 2;
    const minimumTargetX = Math.min(...targets.map((target) => target.x));
    const busX = Math.min(sourceX + 66 + (groupIndex % 3) * 10, minimumTargetX - 44);
    if (busX <= sourceX + 24) return;
    const targetYs = targets.map((target) => target.y + target.height / 2);
    const minimumY = Math.min(sourceY, ...targetYs);
    const maximumY = Math.max(sourceY, ...targetYs);
    const relatedBundle = !focused || group.some((edge) => related.has(edge.source) && related.has(edge.target));
    const trunk = `M ${sourceX} ${sourceY} H ${busX} M ${busX} ${minimumY} V ${maximumY}`;
    const signalBundle = group.some(edgeIsSignalling);
    output.push(`<g class="flow-edge-group bundle"><path class="flow-edge data bus ${relatedBundle ? "focused" : "dim"}" d="${trunk}"/>${signalBundle ? `<path class="flow-edge data bus flow-edge-signal" d="${trunk}"/>` : ""}<circle class="bus-junction" cx="${busX}" cy="${sourceY}" r="3"/></g>`);
    group.forEach((edge) => {
      const target = nodeById[edge.target];
      const targetX = target.x;
      const targetY = target.y + target.height / 2;
      const isRelated = !focused || (related.has(edge.source) && related.has(edge.target));
      const selected = [edge.source, edge.target].includes(state.selectedTaskId);
      const path = roundedOrthogonalPath([[busX, targetY], [targetX, targetY]], 0);
      output.push(`<g class="flow-edge-group"><title>${escapeHtml(`${edge.source} → ${edge.target}${edge.label ? ` · ${edge.label}` : ""}`)}</title><path class="flow-edge ${escapeHtml(edge.type)} ${isRelated ? "focused" : "dim"}" d="${path}" marker-end="url(#arrow-data)"/>${edgeIsSignalling(edge) ? `<path class="flow-edge ${escapeHtml(edge.type)} flow-edge-signal" d="${path}"/>` : ""}${edgeDetailMarkup(edge, (busX + targetX) / 2, targetY - 17, selected)}</g>`);
      bundled.add(edge.id);
    });
  });
  (layout.edges || []).forEach((edge) => {
    if (bundled.has(edge.id)) return;
    const source = nodeById[edge.source];
    const target = nodeById[edge.target];
    if (!source || !target) return;
    const isRelated = !focused || (related.has(edge.source) && related.has(edge.target));
    const marker = edge.type === "route" ? "route" : edge.type === "review" ? "review" : edge.type === "data" ? "data" : "control";
    const path = graphEdgePath(source, target, edge);
    const selected = [edge.source, edge.target].includes(state.selectedTaskId);
    const labelX = edge.source === edge.target ? source.x + source.width / 2 : (source.x + source.width + target.x) / 2;
    const labelY = edge.source === edge.target ? source.y - 64 : (source.y + source.height / 2 + target.y + target.height / 2) / 2 - 16;
    output.push(`<g class="flow-edge-group"><title>${escapeHtml(`${edge.source} → ${edge.target}${edge.label ? ` · ${edge.label}` : ""}`)}</title><path class="flow-edge ${escapeHtml(edge.type)} ${isRelated ? "focused" : "dim"}" d="${path}" marker-end="url(#arrow-${marker})"/>${edgeIsSignalling(edge) ? `<path class="flow-edge ${escapeHtml(edge.type)} flow-edge-signal" d="${path}"/>` : ""}${edgeDetailMarkup(edge, labelX, labelY, selected)}</g>`);
  });
  return output.join("");
}

function dependencyFrontiers(tasks) {
  const taskById = Object.fromEntries(tasks.map((task) => [task.task_id, task]));
  const satisfied = new Set(tasks.filter((task) => task.status === "approved").map((task) => task.task_id));
  const remaining = new Map(tasks
    .filter((task) => !["approved", "cancelled", "superseded"].includes(task.status))
    .map((task) => [task.task_id, task]));
  const frontiers = [];
  while (remaining.size) {
    const frontier = [...remaining.values()].filter((task) => (task.dependencies || []).every((dependencyId) => satisfied.has(dependencyId)));
    if (!frontier.length) break;
    frontier.sort((a, b) => Number(b.critical_path) - Number(a.critical_path) || Number(b.unlock_value || 0) - Number(a.unlock_value || 0) || Number(b.priority || 0) - Number(a.priority || 0) || a.task_id.localeCompare(b.task_id));
    frontiers.push(frontier);
    frontier.forEach((task) => {
      remaining.delete(task.task_id);
      satisfied.add(task.task_id);
    });
  }
  return {
    frontiers,
    unresolved: [...remaining.values()].map((task) => ({
      task,
      missing: (task.dependencies || []).filter((dependencyId) => !satisfied.has(dependencyId) && !taskById[dependencyId]),
    })),
  };
}

function forecastTaskSubset(tasks) {
  const currentTasks = tasks.filter((task) => !["approved", "cancelled", "superseded"].includes(task.status));
  const relevantTasks = tasks.filter((task) => !["cancelled", "superseded"].includes(task.status));
  if (!currentTasks.length) return relevantTasks.filter((task) => task.status === "approved");
  if (state.flow.presentation === "overview") return currentTasks;
  const byId = Object.fromEntries(relevantTasks.map((task) => [task.task_id, task]));
  const seeds = new Set(currentTasks
    .filter((task) => task.derived?.runnable || ["working", "candidate", "rework", "user_review_pending", "blocked"].includes(task.status))
    .map((task) => task.task_id));
  state.flow.expandedForecastTaskIds.forEach((taskId) => {
    if (byId[taskId]) seeds.add(taskId);
  });
  if (!seeds.size && currentTasks.length) seeds.add(currentTasks[0].task_id);
  const visible = new Set(seeds);
  seeds.forEach((taskId) => {
    (byId[taskId]?.dependencies || []).forEach((dependencyId) => {
      if (byId[dependencyId]) visible.add(dependencyId);
    });
    currentTasks.forEach((task) => {
      if ((task.dependencies || []).includes(taskId)) visible.add(task.task_id);
    });
  });
  return relevantTasks.filter((task) => visible.has(task.task_id));
}

function agentAssignmentsByTask() {
  const assignments = {};
  const leasedOwners = new Set();
  const reservedOwners = new Set();
  (state.overview?.leases || []).filter((lease) => lease.status === "active").forEach((lease) => {
    (assignments[lease.task_id] ||= []).push(lease.owner);
    leasedOwners.add(lease.owner);
  });
  (state.overview?.dispatch_reservations || []).filter((reservation) => reservation.status === "active").forEach((reservation) => {
    const label = `${reservation.reserved_for} · 预留`;
    if (!(assignments[reservation.task_id] || []).includes(label)) (assignments[reservation.task_id] ||= []).push(label);
    reservedOwners.add(reservation.reserved_for);
  });
  (state.overview?.agents || []).forEach((agent) => {
    if (leasedOwners.has(agent.agent_id) || reservedOwners.has(agent.agent_id)) return;
    const taskId = agent.derived?.next?.task?.task_id;
    if (!taskId) return;
    const label = `${agent.agent_id} · ${agent.presence === "online" ? "可领取" : "计划"}`;
    if (!(assignments[taskId] || []).includes(label)) (assignments[taskId] ||= []).push(label);
  });
  return assignments;
}

function dependencyForecastGraph(tasks) {
  const allActiveTasks = tasks.filter((task) => !["cancelled", "superseded"].includes(task.status));
  const activeTasks = forecastTaskSubset(tasks);
  const allById = Object.fromEntries(allActiveTasks.map((task) => [task.task_id, task]));
  const rankMemo = {};
  const rankOf = (taskId, stack = new Set()) => {
    if (rankMemo[taskId] !== undefined) return rankMemo[taskId];
    if (stack.has(taskId)) return 0;
    const dependencies = (allById[taskId]?.dependencies || []).filter((dependencyId) => allById[dependencyId]);
    const rank = dependencies.length ? 1 + Math.max(...dependencies.map((dependencyId) => rankOf(dependencyId, new Set(stack).add(taskId)))) : 0;
    rankMemo[taskId] = rank;
    return rank;
  };
  allActiveTasks.forEach((task) => rankOf(task.task_id));
  const visibleRanks = [...new Set(activeTasks.map((task) => rankMemo[task.task_id] || 0))].sort((a, b) => a - b);
  const displayRank = Object.fromEntries(visibleRanks.map((rank, index) => [rank, index]));
  const columns = {};
  activeTasks.forEach((task) => (columns[displayRank[rankMemo[task.task_id] || 0]] ||= []).push(task));
  Object.values(columns).forEach((items) => items.sort((a, b) => `${a.deliverable_id || ""}:${a.content_unit_id || ""}:${a.task_id}`.localeCompare(`${b.deliverable_id || ""}:${b.content_unit_id || ""}:${b.task_id}`)));
  const nodeWidth = 184;
  const nodeHeight = 62;
  const columnGap = 76;
  const rowGap = 12;
  const margin = 24;
  const ranks = Object.keys(columns).map(Number);
  const maxRank = Math.max(0, ...ranks);
  const maxRows = Math.max(1, ...Object.values(columns).map((items) => items.length));
  const height = Math.max(240, margin * 2 + maxRows * nodeHeight + (maxRows - 1) * rowGap);
  const width = margin * 2 + (maxRank + 1) * nodeWidth + maxRank * columnGap;
  const nodes = [];
  Object.entries(columns).forEach(([rankText, items]) => {
    const columnHeight = items.length * nodeHeight + Math.max(0, items.length - 1) * rowGap;
    const startY = (height - columnHeight) / 2;
    items.forEach((task, index) => nodes.push({
      task,
      x: margin + Number(rankText) * (nodeWidth + columnGap),
      y: startY + index * (nodeHeight + rowGap),
      width: nodeWidth,
      height: nodeHeight,
    }));
  });
  const nodeById = Object.fromEntries(nodes.map((node) => [node.task.task_id, node]));
  const assignments = agentAssignmentsByTask();
  const edges = [];
  activeTasks.forEach((task) => (task.dependencies || []).forEach((dependencyId) => {
    const source = nodeById[dependencyId];
    const target = nodeById[task.task_id];
    if (!source || !target) return;
    const sourceX = source.x + source.width;
    const sourceY = source.y + source.height / 2;
    const targetX = target.x;
    const targetY = target.y + target.height / 2;
    const middleX = (sourceX + targetX) / 2;
    const path = `M ${sourceX} ${sourceY} C ${middleX} ${sourceY}, ${middleX} ${targetY}, ${targetX} ${targetY}`;
    const consumesInput = task.status === "working";
    const transitioned = state.flow.transitionTaskIds.has(dependencyId) || state.flow.transitionTaskIds.has(task.task_id);
    edges.push(`<path class="forecast-edge" d="${path}" marker-end="url(#forecastArrow)"/>${consumesInput ? `<path class="forecast-edge forecast-edge-active" d="${path}"/>` : ""}${transitioned ? `<path class="forecast-edge forecast-edge-signal" d="${path}"/>` : ""}`);
  }));
  const nodeMarkup = nodes.map(({ task, x, y, width: nodeW, height: nodeH }) => {
    const roleClass = task.human_gate ? "human" : task.kind === "source" ? "animation" : task.kind === "tts_script" || task.kind === "narration_audio" ? "audio" : task.kind === "storyboard" ? "design" : task.kind === "integration" ? "integration" : "control";
    const phase = task.status === "approved" ? "approved" : task.status === "working" ? "working" : task.status === "candidate" || task.status === "user_review_pending" ? "reviewing" : task.derived?.runnable ? "ready" : "waiting";
    const title = task.title.length > 18 ? `${task.title.slice(0, 18)}…` : task.title;
    const agentLabel = (assignments[task.task_id] || []).slice(0, 2).join(" · ");
    const recent = state.flow.transitionTaskIds.has(task.task_id) ? "recent" : "";
    const selected = state.selectedTaskId === task.task_id ? "selected" : "";
    const attentionCount = taskHumanAttentionCount(task);
    const attention = attentionCount
      ? `<g class="forecast-attention-badge" transform="translate(${nodeW - 3} 5)" aria-label="${attentionCount} 项待你处理"><circle r="7"/><text text-anchor="middle" y="2.5">${attentionCount}</text></g>`
      : "";
    return `<g class="forecast-node ${roleClass} ${phase} ${recent} ${selected}" data-task-id="${escapeHtml(task.task_id)}" role="button" tabindex="0" aria-label="${escapeHtml(`${task.task_id} ${task.title}，${taskStatusLabel(task)}${attentionCount ? `，${attentionCount} 项待你处理` : ""}`)}" transform="translate(${x} ${y})"><title>${escapeHtml(task.task_id)} · ${escapeHtml(task.title)} · 仅等待 ${escapeHtml((task.dependencies || []).join(", ") || "无依赖")}</title><rect width="${nodeW}" height="${nodeH}" rx="7"/><circle cx="12" cy="14" r="3"/><text class="forecast-id" x="21" y="17">${escapeHtml(task.task_id)}</text><text class="forecast-title" x="10" y="35">${escapeHtml(title)}</text><text class="forecast-role" x="${nodeW - 10}" y="17" text-anchor="end">${escapeHtml(task.role || task.kind || "worker")}</text><text class="forecast-agent" x="10" y="52">${escapeHtml(agentLabel || (phase === "waiting" ? "等待依赖" : taskStatusLabel(task)))}</text>${attention}</g>`;
  }).join("");
  const baseWidth = Math.max(1080, width);
  const baseHeight = Math.max(240, height);
  const zoom = Math.max(FORECAST_ZOOM_MIN, Math.min(FORECAST_ZOOM_MAX, Number(state.flow.forecastZoom || 1)));
  const scaledWidth = Math.round(baseWidth * zoom);
  const scaledHeight = Math.round(baseHeight * zoom);
  return `<div class="execution-canvas" data-base-width="${baseWidth}" data-base-height="${baseHeight}" style="width:max(100%, ${scaledWidth}px);height:max(248px, ${scaledHeight}px)"><svg width="${scaledWidth}" height="${scaledHeight}" viewBox="0 0 ${width} ${height}" role="img" aria-label="任务按各自显式依赖异步释放；同一横向位置不构成阶段栅栏"><defs><marker id="forecastArrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M 1 1 L 8 5 L 1 9"/></marker></defs>${edges.join("")}${nodeMarkup}</svg></div>`;
}

function updateForecastZoomControls() {
  const zoom = Number(state.flow.forecastZoom || 1);
  const level = $("#forecastZoomLevel");
  if (level) {
    const percent = Math.round(zoom * 100);
    level.textContent = `${percent}%`;
    level.setAttribute("aria-label", `当前缩放 ${percent}%，点击重置`);
  }
  if ($("#forecastZoomOut")) $("#forecastZoomOut").disabled = zoom <= FORECAST_ZOOM_MIN + 0.001;
  if ($("#forecastZoomIn")) $("#forecastZoomIn").disabled = zoom >= FORECAST_ZOOM_MAX - 0.001;
}

function setForecastZoom(nextZoom, anchor = {}) {
  const viewport = $("#executionMap");
  const canvas = viewport?.querySelector(".execution-canvas");
  const svg = canvas?.querySelector("svg");
  if (!viewport || !canvas || !svg) return;
  const oldZoom = Number(state.flow.forecastZoom || 1);
  const zoom = Math.max(FORECAST_ZOOM_MIN, Math.min(FORECAST_ZOOM_MAX, Number(nextZoom || 1)));
  if (Math.abs(zoom - oldZoom) < 0.001) return;
  const baseWidth = Number(canvas.dataset.baseWidth || 1080);
  const baseHeight = Number(canvas.dataset.baseHeight || 240);
  const rect = viewport.getBoundingClientRect();
  const viewportX = Number.isFinite(anchor.clientX) ? Math.max(0, Math.min(viewport.clientWidth, anchor.clientX - rect.left)) : viewport.clientWidth / 2;
  const viewportY = Number.isFinite(anchor.clientY) ? Math.max(0, Math.min(viewport.clientHeight, anchor.clientY - rect.top)) : viewport.clientHeight / 2;
  const oldWidth = baseWidth * oldZoom;
  const oldHeight = baseHeight * oldZoom;
  const oldOffsetX = Math.max(0, (viewport.clientWidth - oldWidth) / 2);
  const oldOffsetY = Math.max(0, (viewport.clientHeight - oldHeight) / 2);
  const logicalX = (viewport.scrollLeft + viewportX - oldOffsetX) / oldZoom;
  const logicalY = (viewport.scrollTop + viewportY - oldOffsetY) / oldZoom;

  state.flow.forecastZoom = zoom;
  const scaledWidth = Math.round(baseWidth * zoom);
  const scaledHeight = Math.round(baseHeight * zoom);
  canvas.style.width = `max(100%, ${scaledWidth}px)`;
  canvas.style.height = `max(248px, ${scaledHeight}px)`;
  svg.setAttribute("width", scaledWidth);
  svg.setAttribute("height", scaledHeight);
  updateForecastZoomControls();

  requestAnimationFrame(() => {
    const newOffsetX = Math.max(0, (viewport.clientWidth - scaledWidth) / 2);
    const newOffsetY = Math.max(0, (viewport.clientHeight - scaledHeight) / 2);
    viewport.scrollLeft = Math.max(0, logicalX * zoom + newOffsetX - viewportX);
    viewport.scrollTop = Math.max(0, logicalY * zoom + newOffsetY - viewportY);
  });
}

function fitForecast() {
  const viewport = $("#executionMap");
  const canvas = viewport?.querySelector(".execution-canvas");
  if (!viewport || !canvas) return;
  const baseWidth = Number(canvas.dataset.baseWidth || 1080);
  const baseHeight = Number(canvas.dataset.baseHeight || 240);
  const availableWidth = Math.max(1, viewport.clientWidth - 32);
  const availableHeight = Math.max(1, viewport.clientHeight - 24);
  setForecastZoom(Math.min(availableWidth / baseWidth, availableHeight / baseHeight));
}

function eventHumanLabel(event) {
  const labels = {
    TaskBegan: "开始执行",
    TaskSubmitted: "提交候选",
    ReviewRecorded: "完成审查",
    TaskRevisionRequested: "返回返修",
    TaskApproved: "通过批准",
    LeaseGranted: "领取任务",
    RouteSwitched: "切换路线",
    ArtifactRegistered: "登记制品",
    GateReceiptRecorded: "硬门禁回执",
    AgentRegistered: "登记工位",
  };
  return labels[event.event_type] || event.event_type;
}

function renderFlowTimeRibbon() {
  const root = $("#flowTimeRibbon");
  if (!root || !state.overview) return;
  const recent = state.events.slice(-4);
  const nextTask = state.next?.next?.task;
  const history = recent.map((event) => `<button type="button" class="time-event" data-event-target="${escapeHtml(event.aggregate_type === "task" ? event.aggregate_id : "")}" title="${escapeHtml(event.event_type)}"><span>#${event.seq}</span><b>${escapeHtml(eventHumanLabel(event))}</b><small>${escapeHtml(event.aggregate_id)}</small></button>`).join("");
  root.innerHTML = `<div class="time-ribbon-label"><span class="eyebrow">LIVE TIME</span><b>生产时间流</b></div><div class="time-ribbon-track">${history || `<span class="time-ribbon-empty">尚无运行事件，等待第一项任务开始</span>`}<i class="time-now" title="当前事件游标">#${state.cursor}</i><div class="time-next"><span>下一释放</span><b>${escapeHtml(nextTask ? `${nextTask.task_id} · ${nextTask.title}` : "等待事件")}</b></div></div>`;
  root.querySelectorAll("[data-event-target]").forEach((button) => {
    if (!button.dataset.eventTarget) return;
    button.onclick = () => {
      selectTask(button.dataset.eventTarget, button);
    };
  });
}

function renderExecutionPreview() {
  const policyRoot = $("#dispatchPolicy");
  const mapRoot = $("#executionMap");
  const loopRoot = $("#dispatchLoop");
  if (!policyRoot || !mapRoot || !loopRoot || !state.overview) return;
  const tasks = state.overview.tasks || [];
  const visibleForecastTasks = forecastTaskSubset(tasks);
  const remainingTasks = tasks.filter((task) => !["approved", "cancelled", "superseded"].includes(task.status));
  renderFlowTimeRibbon();
  $("#executionPreviewTitle").textContent = state.flow.presentation === "overview" ? "完整执行拓扑" : "当前释放视野";
  const previewDescription = $("#homeFlowDescription");
  if (previewDescription) previewDescription.textContent = !remainingTasks.length
    ? `最终批准路径 · ${visibleForecastTasks.length} 项`
    : state.flow.presentation === "overview"
      ? `全部未结束任务 · ${visibleForecastTasks.length} 项`
      : `当前释放视野 · ${visibleForecastTasks.length} 项`;
  const { frontiers } = dependencyFrontiers(tasks);
  const policy = state.overview.dispatch_policy || {
    configured: false,
    mode: "unconfigured",
    max_active_authors: null,
    reviewer_capacity: null,
  };
  const activeAuthors = (state.overview.leases || []).filter((lease) => lease.status === "active").length;
  const agentRoster = state.overview.agents || [];
  const idleAnomalies = agentRoster.filter((agent) => ["idle_illegal", "working_nonproductive_risk", "fake_busy_duplicate_work"].includes(agent.derived?.classification));
  const peakWidth = Math.max(0, ...frontiers.map((frontier) => frontier.filter((task) => !task.human_gate).length));
  const plannedPeak = policy.configured ? Math.min(peakWidth, Number(policy.max_active_authors || 0)) : null;
  policyRoot.innerHTML = `<div class="dispatch-policy-title"><span>调度承诺</span><b class="${policy.configured ? "bound" : "unbound"}">${policy.configured ? "已登记" : "未配置"}</b></div>
    <dl>
      <div><dt>分配模式</dt><dd>${escapeHtml(policy.mode === "elastic" ? "按需弹性" : policy.mode === "fixed" ? "固定工位" : "未配置")}</dd></div>
      <div><dt>制作工位上限</dt><dd>${escapeHtml(policy.max_active_authors ?? "—")}</dd></div>
      <div><dt>独立审查容量</dt><dd>${escapeHtml(policy.reviewer_capacity ?? "—")}</dd></div>
      <div><dt>当前占用</dt><dd>${activeAuthors}</dd></div>
      <div><dt>预测峰值</dt><dd>${plannedPeak ?? "—"}</dd></div>
      <div><dt>闲置合法性</dt><dd>${agentRoster.length ? `${idleAnomalies.length} 异常 / ${agentRoster.length} 工位` : "等待登记 roster"}</dd></div>
    </dl>
    <p>${policy.configured ? "容量由状态内核执行；Agent 只在任务进入可领取前沿时创建。" : "拓扑只能说明可并行性，尚不能承诺实际 Agent 数。"}</p>`;
  mapRoot.innerHTML = dependencyForecastGraph(tasks);
  updateForecastZoomControls();
  if (state.flow.forecastAutoFit) requestAnimationFrame(fitForecast);
  const readyTasks = tasks.filter((task) => task.derived?.runnable);
  const freeSlots = policy.configured ? Math.max(0, Number(policy.max_active_authors || 0) - activeAuthors) : null;
  const nextTask = state.next?.next?.task;
  loopRoot.innerHTML = `<div class="dispatch-loop-title"><span>流动领取</span><b>事件驱动，不设阶段栅栏</b></div><div class="dispatch-loop-track">
    <div class="dispatch-loop-node"><span>依赖事件</span><b>任一上游批准即重新计算</b></div><i>→</i>
    <div class="dispatch-loop-node ready-pool"><span>Ready Pool · ${readyTasks.length}</span><b>${escapeHtml(readyTasks.map((task) => task.task_id).join(" · ") || "空")}</b></div><i>→</i>
    <div class="dispatch-loop-node"><span>next() 排序</span><b>${escapeHtml(nextTask ? `${nextTask.task_id} · ${nextTask.title}` : "无可领取项")}</b></div><i>→</i>
    <div class="dispatch-loop-node"><span>空闲工位</span><b>${freeSlots ?? "未配置"} / ${policy.max_active_authors ?? "—"}</b></div><i>→</i>
    <div class="dispatch-loop-node"><span>租约与审查</span><b>begin → submit → review</b></div><i class="loop-back">↺</i>
  </div><p>一个任务完成只释放它的直接下游；同列任务互不等待。空闲 Agent 每次只领取系统返回的一个最优任务。</p>`;
  mapRoot.querySelectorAll("[data-task-id]").forEach((node) => {
    bindGraphTaskGestures(node);
  });
}

function renderFlow() {
  const svg = $("#flowSvg");
  if (!svg || !state.overview) return;
  renderExecutionPreview();
  const layout = state.flow.mode === "macro" ? macroGraphLayout() : state.flow.mode === "micro" ? microGraphLayout() : taskGraphLayout();
  state.flow.layout = layout;
  const disclosure = $("#topologyDisclosure");
  if (disclosure) disclosure.open = state.flow.topologyExpanded;
  const empty = !layout.nodes.length;
  $("#flowEmpty").classList.toggle("hidden", !empty);
  $("#flowEmpty").textContent = layout.empty || "当前视图没有可绘制的节点。";
  const nodeById = Object.fromEntries(layout.nodes.map((node) => [node.id, node]));
  const related = state.selectedTaskId ? graphClosure(state.selectedTaskId) : new Set();
  const focused = state.flow.filter === "focus" && state.selectedTaskId && layout.type === "task";
  const bands = (layout.bands || []).map((band) => `<g><rect class="flow-wave-band" x="${band.x}" y="${band.y}" width="${band.width}" height="${band.height}" rx="10"/><text class="flow-wave-label" x="${band.x + 18}" y="${band.y + 25}">${escapeHtml(band.title)}</text><text class="flow-wave-meta" x="${band.x + band.width - 18}" y="${band.y + 24}" text-anchor="end">${escapeHtml(band.meta || "")}</text></g>`).join("");
  const columnGuides = (layout.columns || []).map((column) => `<g class="flow-rank"><text x="${column.x}" y="${column.y}">${escapeHtml(column.title)}</text><line x1="${column.x}" y1="${column.y + 16}" x2="${column.x + 268}" y2="${column.y + 16}"/></g>`).join("");
  const edges = renderGraphEdges(layout, nodeById, related, focused);
  const nodes = layout.nodes.map((node) => {
    const dim = focused && node.type === "task" && !related.has(node.id);
    return `<g class="${dim ? "dim" : ""}">${graphNodeMarkup(node)}</g>`;
  }).join("");
  const breadcrumb = layout.type === "micro" && layout.task ? `<text class="flow-breadcrumb" x="42" y="48">EPISODE / ${escapeHtml(layout.task.deliverable_id || layout.task.wave_id || "unassigned")} / ${escapeHtml(layout.task.content_unit_id || layout.task.scene_id || "episode")} / ${escapeHtml(layout.task.task_id)}</text>` : layout.type === "macro" ? `<text class="flow-breadcrumb" x="32" y="29">EPISODE · ${escapeHtml(state.overview.scope?.episode_phase || "initialized")} · semantic projection</text>` : "";
  svg.innerHTML = `<defs>
      <marker id="arrow-control" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path class="arrow-marker control" d="M 1 1 L 8 5 L 1 9"/></marker>
      <marker id="arrow-data" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path class="arrow-marker data" d="M 1 1 L 8 5 L 1 9"/></marker>
      <marker id="arrow-review" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path class="arrow-marker review" d="M 1 1 L 8 5 L 1 9"/></marker>
      <marker id="arrow-route" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path class="arrow-marker route" d="M 1 1 L 8 5 L 1 9"/></marker>
    </defs><g id="flowWorld" class="flow-world">${bands}${columnGuides}${breadcrumb}${edges}${nodes}</g>`;
  setFlowTransform();
  svg.querySelectorAll("[data-task-id]").forEach((element) => {
    bindGraphTaskGestures(element);
  });
  svg.querySelectorAll("[data-scope-id]").forEach((element) => {
    const activate = (event) => {
      event.stopPropagation();
      const axis = element.dataset.scopeAxis;
      const id = element.dataset.scopeId;
      const source = axis === "deliverable" ? state.overview.scope?.deliverables : state.overview.scope?.content_units;
      const scopeNode = (source || []).find((item) => (axis === "deliverable" ? item.deliverable_id : item.unit_id) === id);
      state.flow.scopeTaskIds = scopeNode?.task_ids || [];
      state.flow.mode = "task";
      state.flow.filter = "all";
      state.flow.topologyExpanded = true;
      state.selectedTaskId = scopeNode?.direct_task_ids?.[0] || scopeNode?.task_ids?.[0] || null;
      state.flow.fittedKey = null;
      activateView("flow");
    };
    element.addEventListener("click", activate);
    element.addEventListener("keydown", (event) => {
      if (!["Enter", " "].includes(event.key)) return;
      event.preventDefault();
      activate(event);
    });
  });
  updateFlowButtons();
  const contextTitle = state.flow.presentation === "overview"
    ? "完整总览"
    : layout.type === "macro" ? "结构层" : layout.type === "micro" ? `单任务 · ${layout.task?.task_id || "未选择"}` : "分层监控";
  const contextDetail = layout.type === "macro"
    ? "查看内容尺度与交付物流；分组不构成执行栅栏。"
    : state.flow.presentation === "overview"
      ? `${layout.nodes.length} 个节点 · ${layout.edges.length} 条显式关系 · 全局诊断模式`
      : `${layout.nodes.length} 个节点 · ${layout.edges.length} 条显式关系${state.selectedTaskId ? ` · 已聚焦 ${state.selectedTaskId}` : ""}`;
  $("#flowContextTitle").textContent = contextTitle;
  $("#flowContextDetail").textContent = contextDetail;
  $("#topologyDisclosureTitle").textContent = layout.type === "macro" ? "结构层" : layout.type === "micro" ? "单任务内部流程" : state.flow.presentation === "overview" ? "完整任务拓扑" : "当前任务层";
  $("#topologyDisclosureDetail").textContent = `${layout.nodes.length} 个节点 · ${layout.edges.length} 条关系${state.flow.topologyExpanded ? " · 正在查看" : " · 按需展开"}`;
  const fitKey = `${state.episodeId}:${state.flow.presentation}:${state.flow.mode}:${state.flow.filter}:${state.flow.scopeTaskIds?.join(",") || "all"}`;
  if (state.flow.topologyExpanded && state.flow.fittedKey !== fitKey && ($("#flowView").classList.contains("active") || $("#structureView").classList.contains("active"))) {
    state.flow.fittedKey = fitKey;
    setTimeout(fitFlow, 0);
  }
}

function actorInitials(actor) {
  return String(actor || "?").split(/[-_.:]/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "?";
}

function stationTaskMarkup(task, kicker, extra = "") {
  return `<div class="station-task-block"><button class="station-task" data-task-id="${escapeHtml(task.task_id)}" type="button"><span class="task-kicker">${escapeHtml(kicker)} · ${escapeHtml(task.task_id)}</span><strong>${escapeHtml(task.title)}</strong><small><span>${escapeHtml(taskStatusLabel(task))}</span><span>${escapeHtml(task.content_unit_id || task.scene_id || "EP")}</span></small></button>${extra}</div>`;
}

function renderWorkstations() {
  if (!state.overview || !$("#workstationGrid")) return;
  const tasks = state.overview.tasks || [];
  const taskById = Object.fromEntries(tasks.map((task) => [task.task_id, task]));
  const activeLeases = (state.overview.leases || []).filter((lease) => lease.status === "active");
  const pendingReturns = (state.overview.returns || []).filter((item) => item.status === "pending");
  const roster = state.overview.agents || [];
  const rosterById = Object.fromEntries(roster.map((agent) => [agent.agent_id, agent]));
  const eventsByActor = {};
  [...state.events].sort((a, b) => b.seq - a.seq).forEach((event) => {
    if ((eventsByActor[event.actor] ||= []).length < 4) eventsByActor[event.actor].push(event);
  });
  const workstationActors = [...new Set([...roster.map((agent) => agent.agent_id), ...activeLeases.map((lease) => lease.owner)])].sort();
  const ready = tasks.filter((task) => task.derived?.runnable);
  const review = tasks.filter((task) => task.status === "candidate");
  const human = tasks.filter((task) => task.status === "user_review_pending");
  const productive = roster.filter((agent) => agent.derived?.classification === "working_productive").length;
  const illegalIdle = roster.filter((agent) => agent.derived?.classification === "idle_illegal").length;
  const fakeBusy = roster.filter((agent) => ["working_nonproductive_risk", "fake_busy_duplicate_work"].includes(agent.derived?.classification)).length;
  $("#workstationSummary").innerHTML = [
    ["登记工位", roster.length], ["有效工作", productive], ["非法闲置", illegalIdle], ["假忙 / 停滞", fakeBusy],
  ].map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`).join("");
  const classLabels = {
    planned: ["planned", "等待启动"],
    online: ["online", "在线"],
    offline: ["offline", "离线"],
    retired: ["retired", "已退役"],
    offline_unknown: ["unknown", "在线状态未知"],
    idle_legal: ["idle-legal", "合法闲置"],
    idle_illegal: ["idle-illegal", "非法闲置"],
    working_productive: ["working", "有效工作"],
    working_nonproductive_risk: ["nonproductive", "无新进展"],
    fake_busy_duplicate_work: ["fake-busy", "重复劳动"],
    blocked_by_supervision: ["blocked", "监督阻断"],
    unregistered_active: ["working", "未登记运行"],
  };
  const stations = workstationActors.map((actor) => {
    const leases = activeLeases.filter((lease) => lease.owner === actor);
    const actorReturns = pendingReturns.filter((item) => item.assigned_to === actor);
    const recent = eventsByActor[actor] || [];
    const agent = rosterById[actor];
    const classification = agent?.derived?.classification || (leases.length ? "unregistered_active" : agent?.presence || "offline_unknown");
    const [stateClass, stateLabel] = classLabels[classification] || ["unknown", classification];
    const reasonCodes = agent?.derived?.reason_codes || [];
    const suggestedTask = agent?.derived?.next?.task;
    const body = leases.map((lease) => {
      const task = taskById[lease.task_id];
      return task ? stationTaskMarkup(task, `g${lease.generation}`, `${capsuleDisclosureMarkup(taskCapsuleHash(task), "station")}<div class="station-lease-expiry">租约截止 ${escapeHtml(lease.expires_at || "—")}</div>`) : "";
    }).join("") || (suggestedTask ? stationTaskMarkup(suggestedTask, `系统建议 · ${agent?.derived?.next?.action || "work"}`) : `<div class="lane-empty">当前无领取项</div>`);
    return `<article class="workstation agent-desk ${escapeHtml(stateClass)}"><header class="workstation-head"><div class="agent-avatar">${escapeHtml(actorInitials(actor))}</div><div><h3>${escapeHtml(actor)}</h3><p>${escapeHtml(agent?.role || "unregistered")} · ${leases.length} LEASE · ${actorReturns.length} RETURN</p></div><span class="desk-state">${escapeHtml(stateLabel)}</span></header><div class="workstation-body">${body}${reasonCodes.length ? `<div class="agent-legality-reasons">${reasonCodes.map((reason) => `<span>${escapeHtml(reason)}</span>`).join("")}</div>` : ""}${actorReturns.map((ticket) => `<div class="station-return">↩ 等待注意力边界：${escapeHtml(taskById[ticket.task_id]?.title || ticket.task_id)}<br/>来自 ${escapeHtml(ticket.review_id)} · 不抢占当前租约</div>`).join("")}<div class="station-events">${recent.map((event) => `<div class="station-event"><span>#${event.seq}</span><b>${escapeHtml(event.event_type)} · ${escapeHtml(event.aggregate_id)}</b></div>`).join("") || `<div class="lane-empty">暂无事件</div>`}</div></div></article>`;
  });
  if (review.length) stations.push(`<article class="workstation review-desk"><header class="workstation-head"><div class="agent-avatar">QA</div><div><h3>独立审查台</h3><p>AUTHOR / REVIEWER SEPARATION</p></div><span class="desk-state">${review.length} waiting</span></header><div class="workstation-body">${review.map((task) => stationTaskMarkup(task, task.derived?.missing_validators?.length ? "先运行硬门禁" : "等待独立审查")).join("")}</div></article>`);
  if (human.length) stations.push(`<article class="workstation human-desk"><header class="workstation-head"><div class="agent-avatar">H</div><div><h3>用户审片台</h3><p>NON-DELEGABLE AUTHORITY</p></div><span class="desk-state">${human.length} waiting</span></header><div class="workstation-body">${human.map((task) => stationTaskMarkup(task, "等待用户授权")).join("")}</div></article>`);
  if (ready.length) stations.push(`<article class="workstation queue-desk"><header class="workstation-head"><div class="agent-avatar">Q</div><div><h3>流动领取队列</h3><p>SYSTEM-RANKED READY FRONTIER</p></div><span class="desk-state">${ready.length} ready</span></header><div class="workstation-body">${ready.slice(0, 8).map((task) => stationTaskMarkup(task, task.pending_return_ticket_id ? "优先返修" : "可领取")).join("")}</div></article>`);
  $("#workstationGrid").innerHTML = stations.join("") || `<div class="next-empty"><div><span class="eyebrow">NO ACTIVE STATION</span><h2>当前没有活跃工位</h2><p>查看流程拓扑中的等待依赖和阻塞。</p></div></div>`;
  $("#workstationGrid").querySelectorAll("[data-task-id]").forEach((button) => {
    button.onclick = () => selectTask(button.dataset.taskId, button);
  });
  bindCapsuleDisclosures($("#workstationGrid"));
}

function fullTopologyProjection() {
  const tasks = state.overview?.tasks || [];
  const leases = Object.fromEntries((state.overview?.leases || []).map((item) => [item.task_id, { owner: item.owner, generation: item.generation, status: item.status, expires_at: item.expires_at }]));
  return {
    episode_id: state.episodeId,
    cursor: state.overview?.cursor || 0,
    health: state.overview?.health,
    episode_phase: state.overview?.scope?.episode_phase,
    macro_budget: state.overview?.macro_budget,
    scope: {
      schema: state.overview?.scope?.schema,
      content_units: (state.overview?.scope?.content_units || []).map((item) => ({ unit_id: item.unit_id, parent_unit_id: item.parent_unit_id, phase: item.derived?.phase, task_ids: item.task_ids })),
      deliverables: (state.overview?.scope?.deliverables || []).map((item) => ({ deliverable_id: item.deliverable_id, parent_deliverable_id: item.parent_deliverable_id, phase: item.derived?.phase, task_ids: item.task_ids })),
      content_edges: state.overview?.scope?.content_edges || [],
      deliverable_edges: state.overview?.scope?.deliverable_edges || [],
    },
    next: state.next?.next ? {
      action: state.next.next.action,
      task_id: state.next.next.task?.task_id || null,
      episode_id: state.next.next.subject?.episode_id || state.episodeId,
    } : null,
    agents: (state.overview?.agents || []).map((agent) => ({
      agent_id: agent.agent_id,
      role: agent.role,
      capabilities: agent.capabilities,
      presence: agent.presence,
      classification: agent.derived?.classification,
      idle_legal: agent.derived?.idle_legal,
      productive: agent.derived?.productive,
      reason_codes: agent.derived?.reason_codes || [],
      next_action: agent.derived?.next?.action || null,
      next_task_id: agent.derived?.next?.task?.task_id || null,
    })),
    tasks: tasks.map((task) => ({
      task_id: task.task_id,
      wave_id: task.wave_id,
      scene_id: task.scene_id,
      content_unit_id: task.content_unit_id,
      deliverable_id: task.deliverable_id,
      work_key: task.work_key,
      status: task.status,
      dependencies: task.dependencies,
      runnable: Boolean(task.derived?.runnable),
      blockers: task.derived?.blockers || task.blockers,
      lease: leases[task.task_id] || null,
      candidate_artifacts: task.candidate?.artifact_ids || [],
      approved_artifacts: task.approved_artifact_ids || [],
      missing_validators: (task.derived?.missing_validators || []).map((item) => item.validator_id),
      gate_receipts: (state.overview?.gates || [])
        .filter((item) => item.task_id === task.task_id && item.candidate_hash === task.candidate?.candidate_hash)
        .map((item) => ({ validator_id: item.validator_id, status: item.status, validator_sha256: item.validator_sha256 })),
      scope_revision: task.scope_revision,
    })),
    route_switches: (state.overview?.routes || []).map((item) => ({ route_switch_id: item.route_switch_id, replaced_task_id: item.replaced_task_id, replacement_task_id: item.replacement_task_id, status: item.status, strategy: item.strategy })),
    deferred_returns: (state.overview?.returns || []).map((item) => ({ return_ticket_id: item.return_ticket_id, task_id: item.task_id, assigned_to: item.assigned_to, status: item.status, delivery_policy: item.delivery_policy })),
  };
}

function agentOperation(selected) {
  if (!selected) return { verb: "wait", arguments: {}, returns: "a new state event" };
  const taskId = selected.task?.task_id;
  const expectedVersion = selected.task_version ?? null;
  if (["work", "reclaim", "return_rework"].includes(selected.action)) {
    return {
      verb: "begin",
      arguments: { episode_id: state.episodeId, task_id: taskId, expected_version: expectedVersion },
      returns: "exact version-bound context capsule and lease",
    };
  }
  if (selected.action === "continue") return { verb: "continue_current_lease", arguments: { task_id: taskId }, returns: "no new context unless the scope revision changed" };
  if (selected.action === "gate") return { verb: "gate-run", arguments: { episode_id: state.episodeId, task_id: taskId, validators: (selected.missing_validators || []).map((item) => item.validator_id || item) }, returns: "version-pinned gate receipts" };
  if (selected.action === "review") return { verb: "review-context", arguments: { episode_id: state.episodeId, task_id: taskId }, returns: "independent review capsule" };
  if (selected.action === "human_review") return { verb: "wait_for_human", arguments: { task_id: taskId }, returns: "non-delegable user decision" };
  if (selected.action === "episode_replan") return { verb: "replan", arguments: { episode_id: state.episodeId }, returns: "reasoned budget or route decision" };
  return { verb: selected.action, arguments: { episode_id: state.episodeId, task_id: taskId }, returns: "operation-specific result" };
}

function topologyProjection() {
  const full = fullTopologyProjection();
  const modelContract = {
    schema: state.overview?.scope?.schema || "multi-scale-dual-axis-v1",
    state_schema_owner: "system_design",
    runtime_schema_generation: false,
    containment_implies_execution_order: false,
  };
  if (state.agentDataMode === "full") return { model_contract: modelContract, ...full };

  if (state.agentDataMode === "delta") {
    const events = state.events.filter((event) => event.seq > state.agentDataAfter).slice(-80);
    return {
      schema: "agent-delta-envelope-v1",
      episode_id: state.episodeId,
      read_after: state.agentDataAfter,
      cursor: full.cursor,
      events: events.map((event) => ({ seq: event.seq, event_type: event.event_type, aggregate_type: event.aggregate_type, aggregate_id: event.aggregate_id, aggregate_version: event.aggregate_version, actor: event.actor })),
      unchanged_state_omitted: true,
      next_read: { verb: "events", arguments: { episode_id: state.episodeId, after: full.cursor } },
    };
  }

  const selected = state.next?.next || null;
  const selectedTask = selected?.task || null;
  if (state.agentDataMode === "next") {
    return {
      schema: "agent-attention-envelope-v2",
      episode_id: state.episodeId,
      cursor: full.cursor,
      episode_phase: full.episode_phase,
      model_contract: modelContract,
      attention: selected ? {
        action: selected.action,
        focus: selectedTask ? {
          task_id: selectedTask.task_id,
          title: selectedTask.title,
          status: selectedTask.status,
          role: selectedTask.role,
          content_unit_id: selectedTask.content_unit_id,
          deliverable_id: selectedTask.deliverable_id,
          scope_revision: selectedTask.scope_revision,
        } : null,
        operation: agentOperation(selected),
        why_now: {
          deterministic_rank: selected.rank || null,
          critical_path: Boolean(selectedTask?.critical_path),
          unlock_value: selectedTask?.unlock_value ?? null,
          priority: selectedTask?.priority ?? null,
          selection_policy: state.next?.selection_policy,
        },
        execution_limits: selectedTask?.budget ? {
          soft_active_seconds: selectedTask.budget.soft_active_seconds,
          hard_active_seconds: selectedTask.budget.hard_active_seconds,
          max_attempts: selectedTask.budget.max_attempts,
          max_no_progress_heartbeats: selectedTask.budget.max_no_progress_heartbeats,
        } : null,
        missing_validators: (selected.missing_validators || []).map((item) => item.validator_id || item),
        return_ticket: selected.return_ticket || null,
      } : null,
      context_boundary: {
        read_now: ["this envelope"],
        read_on_begin: "exact context capsule with goal, contract, stop conditions, references, feedback and state cursor",
        omitted_now: ["full topology", `${state.next?.excluded?.length || 0} scheduler-excluded tasks`, `${state.next?.other_actionable?.length || 0} lower-ranked actionable tasks`, "reference file contents before claim"],
        deferred_returns: state.next?.deferred_returns || {},
      },
      budget_guard: state.next?.budget_state ? {
        hard_stop: state.next.budget_state.hard_stop,
        production_envelope_exhausted: state.next.budget_state.production_envelope_exhausted,
        closure_reserve_available: state.next.budget_state.closure_reserve_available,
      } : null,
      incremental_read: { verb: "events", arguments: { episode_id: state.episodeId, after: full.cursor } },
      targeted_diagnostic: { verb: "explain", arguments: { episode_id: state.episodeId, target_id: "<target-id>" } },
    };
  }

  const targetId = state.selectedTaskId || selectedTask?.task_id || null;
  const target = full.tasks.find((task) => task.task_id === targetId) || null;
  const neighborhood = new Set(target ? [target.task_id, ...(target.dependencies || [])] : []);
  full.tasks.forEach((task) => {
    if ((task.dependencies || []).includes(targetId)) neighborhood.add(task.task_id);
  });
  return {
    schema: "agent-focus-projection-v1",
    episode_id: state.episodeId,
    cursor: full.cursor,
    model_contract: modelContract,
    target_task_id: targetId,
    tasks: full.tasks.filter((task) => neighborhood.has(task.task_id)),
    route_switches: full.route_switches.filter((route) => neighborhood.has(route.replaced_task_id) || neighborhood.has(route.replacement_task_id)),
    deferred_returns: full.deferred_returns.filter((ticket) => neighborhood.has(ticket.task_id)),
    incremental_read: `events ${state.episodeId} --after ${full.cursor}`,
  };
}

function renderTopology() {
  const labels = {
    next: "默认只给一个确定动作、选择原因、执行预算和上下文边界；领取后才签发精确胶囊。",
    focus: "只读取选中任务、直接依赖与直接消费者；适合局部诊断和交接。",
    delta: "只返回上次 cursor 之后的事件，未变化状态不重复进入上下文。",
    full: "全量无坐标拓扑仅用于规划、迁移与监督诊断，不应常驻普通 Agent 上下文。",
  };
  $("#agentDataIntro").textContent = labels[state.agentDataMode];
  $("#agentDataNext").classList.toggle("active", state.agentDataMode === "next");
  $("#agentDataFocus").classList.toggle("active", state.agentDataMode === "focus");
  $("#agentDataDelta").classList.toggle("active", state.agentDataMode === "delta");
  $("#agentDataFull").classList.toggle("active", state.agentDataMode === "full");
  $("#topologyPre").textContent = JSON.stringify(topologyProjection(), null, 2);
}

function scheduleFrontendResync(delay = state.resyncDelay) {
  if (state.resyncTimer || document.visibilityState === "hidden") return;
  state.resyncTimer = window.setTimeout(async () => {
    state.resyncTimer = null;
    const recovered = await reconcileBackend({ source: "automatic" });
    if (recovered) {
      state.resyncDelay = 1200;
      return;
    }
    state.resyncDelay = Math.min(12000, Math.round(state.resyncDelay * 1.8));
    scheduleFrontendResync(state.resyncDelay);
  }, delay);
}

async function reconcileBackend({ source = "manual" } = {}) {
  if (state.recoveryBusy) return false;
  state.recoveryBusy = true;
  setConnectionPhase("reconciling");
  renderFrontendFaults();
  try {
    await loadEpisodes();
    state.lastSuccessfulReconcileAt = new Date().toISOString();
    state.resyncDelay = 1200;
    clearBackendFaults();
    setConnectionPhase("synced");
    renderFrontendFaults();
    if (source === "manual") toast("已与持久后端重新对账；任务状态和事件游标没有被重置");
    return true;
  } catch (error) {
    reportFrontendFault("后端连接", error);
    if (!error?.backendUnreachable) setConnectionPhase("reconnecting");
    if (source === "manual") toast("仍无法完成后端对账；请确认服务已启动后再重试", "error");
    return false;
  } finally {
    state.recoveryBusy = false;
    renderFrontendFaults();
  }
}

async function recoverFrontend() {
  state.stream?.close();
  clearTimeout(state.refreshTimer);
  clearTimeout(state.resyncTimer);
  clearInterval(state.deltaWatchdogTimer);
  state.refreshTimer = null;
  state.resyncTimer = null;
  try {
    await loadEpisodes();
    [...state.uiFaults.entries()].forEach(([scope, fault]) => {
      if (fault?.kind === "interface") state.uiFaults.delete(scope);
    });
    clearBackendFaults();
    setConnectionPhase("synced");
    renderFrontendFaults();
    toast("界面已重新载入；后端任务状态没有被重置");
  } catch (error) {
    reportFrontendFault("后端连接", error);
    scheduleFrontendResync();
  }
}

async function runRecoveryAction() {
  const action = $("#frontendRecoverButton")?.dataset.recoveryAction;
  if (action === "reconnect" || backendFaultEntries().length) {
    const recovered = await reconcileBackend({ source: "manual" });
    if (!recovered) scheduleFrontendResync();
    return;
  }
  await recoverFrontend();
}

async function reconcileMissedDeltas() {
  if (state.deltaWatchdogBusy || !state.episodeId || document.visibilityState !== "visible") return;
  state.deltaWatchdogBusy = true;
  try {
    const delta = await api(`/api/episodes/${encodeURIComponent(state.episodeId)}/events?after=${state.cursor}&limit=200`);
    if (!delta.events?.length) return;
    const known = new Set(state.events.map((event) => event.event_id));
    state.events.push(...delta.events.filter((event) => !known.has(event.event_id)));
    state.events = state.events.slice(-500);
    state.cursor = Math.max(state.cursor, delta.cursor || 0);
    await loadEpisode({ preserveEvents: true });
  } catch (error) {
    reportFrontendFault("增量校验", error);
    scheduleFrontendResync();
  } finally {
    state.deltaWatchdogBusy = false;
  }
}

function startDeltaWatchdog() {
  clearInterval(state.deltaWatchdogTimer);
  state.deltaWatchdogTimer = setInterval(reconcileMissedDeltas, 3000);
}

function connectStream() {
  state.stream?.close();
  if (!state.episodeId) return;
  const status = $("#streamStatus");
  setConnectionPhase("connecting");
  const stream = new EventSource(`/api/stream?episode=${encodeURIComponent(state.episodeId)}&after=${state.cursor}`);
  state.stream = stream;
  stream.onopen = () => {
    status.title = "DELTA + VERIFY：实时事件流，并由持久后端每 3 秒校验一次 cursor";
    clearFrontendFault("实时连接");
    if (backendFaultEntries().length) {
      setConnectionPhase("reconciling");
      scheduleFrontendResync(0);
    } else {
      setConnectionPhase("synced");
    }
  };
  stream.addEventListener("delta", (message) => {
    try {
      const delta = JSON.parse(message.data);
      const known = new Set(state.events.map((event) => event.event_id));
      state.events.push(...delta.events.filter((event) => !known.has(event.event_id)));
      state.events = state.events.slice(-500);
      state.cursor = Math.max(state.cursor, delta.cursor || 0);
      $("#cursorValue").textContent = state.cursor;
      clearTimeout(state.refreshTimer);
      state.refreshTimer = setTimeout(() => loadEpisode({ preserveEvents: true }).catch((error) => {
        reportFrontendFault("后端同步", error);
        scheduleFrontendResync();
      }), 120);
    } catch (error) {
      reportFrontendFault("增量事件", error);
      scheduleFrontendResync();
    }
  });
  stream.onerror = () => {
    setConnectionPhase("reconnecting");
    scheduleFrontendResync(0);
  };
  startDeltaWatchdog();
}

function activateView(viewName, trigger = null, options = {}) {
  const target = $(`#${viewName}View`);
  if (!target) return;
  const tab = trigger || $(`.view-tab[data-view="${viewName}"]`);
  $$(".view-tab").forEach((item) => item.classList.toggle("active", item === tab));
  $$(".view").forEach((view) => view.classList.remove("active"));
  target.classList.add("active");
  $(".main-stage")?.classList.toggle("structure-mode", viewName === "structure");
  $(".main-stage")?.classList.toggle("flow-mode", viewName === "flow");
  $(".main-stage")?.classList.toggle("production-mode", viewName === "production");
  const label = tab?.dataset.label || {
    production: "生产首页",
    flow: "流程监控",
    structure: "结构地图",
    workstations: "Agent 工位",
    risk: "风险与恢复",
    events: "增量事件",
    topology: "Agent 数据",
  }[viewName] || viewName;
  if ($("#currentViewLabel")) $("#currentViewLabel").textContent = label;
  $("#viewSwitcher")?.removeAttribute("open");
  $("#headerTools")?.removeAttribute("open");
  const disclosure = $("#topologyDisclosure");
  if (viewName === "structure") {
    $("#structureGraphHost")?.append(disclosure);
    if (!options.preserveFlowMode) state.flow.mode = "macro";
    state.flow.presentation = "layered";
    state.flow.topologyExpanded = true;
    state.flow.fittedKey = null;
    disclosure.open = true;
    const structureTitles = {
      macro: ["结构地图", "内容尺度与交付物流的双轴投影；归属不构成执行栅栏。"],
      task: ["任务依赖地图", "查看显式依赖、返修与数据交付关系；坐标只服务于阅读。"],
      micro: ["单任务微流程", "查看当前任务内部的领取、执行、审查、返修与恢复循环。"],
    };
    const [title, description] = structureTitles[state.flow.mode] || structureTitles.macro;
    $("#structurePageTitle").textContent = title;
    $("#structurePageDescription").textContent = description;
    renderFlow();
    setTimeout(fitFlow, 0);
  } else if (viewName === "flow") {
    $("#flowGraphHost")?.append(disclosure);
    if (state.flow.mode === "macro") state.flow.mode = "task";
    state.flow.topologyExpanded = true;
    state.flow.fittedKey = null;
    disclosure.open = true;
    renderFlow();
    setTimeout(fitFlow, 0);
  } else if (viewName === "production") {
    state.flow.presentation = "layered";
    renderExecutionPreview();
  }
  if (viewName === "workstations") renderWorkstations();
  hideTaskPeek();
  closeDrawers();
}

function bindGlobalEvents() {
  $("#frontendRecoverButton").onclick = runRecoveryAction;
  $("#episodeSelect").onchange = async (event) => {
    state.episodeId = event.target.value;
    try { localStorage.setItem("lecture-supervision-last-episode", state.episodeId); } catch { /* selection remains session-local */ }
    state.selectedTaskId = null;
    state.peekAnchor = null;
    state.peekScope = "body";
    state.peekSignature = null;
    state.inspectorSignature = null;
    state.floatingMediaSignature = null;
    state.floatingArtifactId = null;
    state.mediaDraftEpisode = null;
    state.mediaDrafts = [];
    state.events = [];
    state.cursor = 0;
    state.capsules = {};
    state.capsuleErrors = {};
    state.capsuleLoading = new Set();
    state.expandedCapsules = new Set();
    state.contextPreviews = {};
    state.contextPreviewErrors = {};
    state.contextPreviewLoading = new Set();
    state.expandedContextTasks = new Set();
    state.contextViewByTask = {};
    state.flow.mode = "task";
    state.flow.scopeTaskIds = null;
    state.flow.filter = "frontier";
    state.flow.presentation = "layered";
    state.flow.topologyExpanded = false;
    state.flow.forecastZoom = 1.2;
    state.flow.forecastAutoFit = false;
    state.flow.expandedForecastTaskIds = new Set();
    state.flow.fittedKey = null;
    state.agentDataMode = "next";
    state.agentDataAfter = 0;
    hideTaskPeek();
    closeDrawers();
    await loadEpisode();
  };
  $("#attentionButton").onclick = () => {
    const task = humanAttentionTasks()[0];
    if (task) focusTaskOnHome(task.task_id);
    else activateView("production");
  };
  $("#refreshButton").onclick = () => {
    $("#headerTools")?.removeAttribute("open");
    loadEpisode({ preserveEvents: true });
  };
  $("#collapseAll").onclick = () => $$(".hierarchy-tree details").forEach((item) => { item.open = false; });
  $("#scopeButton").onclick = () => {
    $("#headerTools")?.removeAttribute("open");
    openHierarchy();
  };
  $("#flowScopeButton").onclick = () => { $(".graph-more")?.removeAttribute("open"); openHierarchy(); };
  $("#closeHierarchy").onclick = closeDrawers;
  $("#drawerScrim").onclick = closeDrawers;
  $("#axisContent").onclick = () => { state.structureAxis = "content"; renderHierarchy(); };
  $("#axisDeliverable").onclick = () => { state.structureAxis = "deliverable"; renderHierarchy(); };
  $("#agentDataNext").onclick = () => { state.agentDataMode = "next"; renderTopology(); };
  $("#agentDataFocus").onclick = () => {
    if (!state.selectedTaskId && !state.next?.next?.task?.task_id) { toast("先选择一个任务", "error"); return; }
    state.agentDataMode = "focus";
    renderTopology();
  };
  $("#agentDataDelta").onclick = () => { state.agentDataMode = "delta"; renderTopology(); };
  $("#agentDataFull").onclick = () => { state.agentDataMode = "full"; renderTopology(); };
  $("#closeInspector").onclick = () => {
    closeDrawers();
  };
  $$(".view-tab").forEach((tab) => {
    tab.onclick = () => activateView(tab.dataset.view, tab);
  });
  $("#flowTaskMode").onclick = () => {
    state.flow.mode = "task";
    if (!state.flow.scopeTaskIds?.length) state.flow.filter = "frontier";
    state.flow.topologyExpanded = true;
    state.flow.fittedKey = null;
    activateView("structure", null, { preserveFlowMode: true });
  };
  $("#flowMicroMode").onclick = () => {
    if (!state.selectedTaskId) { toast("先选择一个任务，再查看微流程", "error"); return; }
    state.flow.mode = "micro";
    state.flow.topologyExpanded = true;
    state.flow.fittedKey = null;
    activateView("structure", null, { preserveFlowMode: true });
  };
  $("#flowShowAll").onclick = () => { $(".graph-more")?.removeAttribute("open"); state.flow.presentation = "overview"; state.flow.mode = "task"; state.flow.filter = "all"; state.flow.scopeTaskIds = null; state.flow.topologyExpanded = true; state.flow.fittedKey = null; renderFlow(); setTimeout(fitFlow, 0); };
  $("#flowShowFocus").onclick = () => {
    state.flow.presentation = "layered";
    state.flow.mode = "task";
    state.flow.filter = "frontier";
    state.flow.scopeTaskIds = null;
    state.flow.topologyExpanded = false;
    state.flow.fittedKey = null;
    renderFlow();
    setTimeout(fitFlow, 0);
  };
  $("#flowZoomIn").onclick = () => zoomFlowAt(state.flow.transform.k * FLOW_ZOOM_STEP);
  $("#flowZoomOut").onclick = () => zoomFlowAt(state.flow.transform.k / FLOW_ZOOM_STEP);
  $("#flowFit").onclick = () => { $(".graph-more")?.removeAttribute("open"); fitFlow(); };
  $("#flowFullscreen").onclick = () => toggleGraphFullscreen($("#flowViewport"));
  $("#forecastZoomIn").onclick = () => { state.flow.forecastAutoFit = false; setForecastZoom(state.flow.forecastZoom * FORECAST_ZOOM_STEP); };
  $("#forecastZoomOut").onclick = () => { state.flow.forecastAutoFit = false; setForecastZoom(state.flow.forecastZoom / FORECAST_ZOOM_STEP); };
  $("#forecastZoomLevel").onclick = () => { state.flow.forecastAutoFit = false; setForecastZoom(1); };
  $("#forecastFit").onclick = () => { state.flow.forecastAutoFit = true; fitForecast(); };
  $("#forecastFullscreen").onclick = () => toggleGraphFullscreen($("#executionMapFrame"));
  $("#topologyDisclosure").addEventListener("toggle", (event) => {
    state.flow.topologyExpanded = event.currentTarget.open;
    if (state.flow.topologyExpanded) setTimeout(fitFlow, 0);
    if ($("#topologyDisclosureDetail") && state.flow.layout) {
      $("#topologyDisclosureDetail").textContent = `${state.flow.layout.nodes.length} 个节点 · ${state.flow.layout.edges.length} 条关系${state.flow.topologyExpanded ? " · 正在查看" : " · 按需展开"}`;
    }
  });
  const flowViewport = $("#flowViewport");
  let flowDrag = null;
  flowViewport.addEventListener("pointerdown", (event) => {
    if (event.target.closest?.(".flow-node")) return;
    hideTaskPeek();
    flowDrag = { pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY, x: state.flow.transform.x, y: state.flow.transform.y };
    flowViewport.setPointerCapture(event.pointerId);
    flowViewport.classList.add("dragging");
  });
  flowViewport.addEventListener("pointermove", (event) => {
    if (!flowDrag || flowDrag.pointerId !== event.pointerId) return;
    state.flow.transform.x = flowDrag.x + event.clientX - flowDrag.clientX;
    state.flow.transform.y = flowDrag.y + event.clientY - flowDrag.clientY;
    setFlowTransform();
  });
  const stopFlowDrag = (event) => {
    if (!flowDrag || flowDrag.pointerId !== event.pointerId) return;
    flowDrag = null;
    flowViewport.classList.remove("dragging");
  };
  flowViewport.addEventListener("pointerup", stopFlowDrag);
  flowViewport.addEventListener("pointercancel", stopFlowDrag);
  flowViewport.addEventListener("wheel", (event) => {
    event.preventDefault();
    if (!event.ctrlKey && !event.metaKey) {
      state.flow.transform.x -= event.deltaX;
      state.flow.transform.y -= event.deltaY;
      setFlowTransform();
      return;
    }
    zoomFlowAt(state.flow.transform.k * Math.pow(2, reactFlowWheelDelta(event)), event);
  }, { passive: false });
  const flowMinimap = $("#flowMinimap");
  let minimapDrag = null;
  const navigateFromMinimap = (event) => centerFlowAt(flowMinimapWorldPoint(event));
  flowMinimap.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    event.stopPropagation();
    hideTaskPeek();
    minimapDrag = event.pointerId;
    flowMinimap.setPointerCapture(event.pointerId);
    navigateFromMinimap(event);
  });
  flowMinimap.addEventListener("pointermove", (event) => {
    if (minimapDrag !== event.pointerId) return;
    event.preventDefault();
    event.stopPropagation();
    navigateFromMinimap(event);
  });
  const stopMinimapDrag = (event) => {
    if (minimapDrag !== event.pointerId) return;
    minimapDrag = null;
  };
  flowMinimap.addEventListener("pointerup", stopMinimapDrag);
  flowMinimap.addEventListener("pointercancel", stopMinimapDrag);
  const executionMap = $("#executionMap");
  executionMap.addEventListener("pointerdown", (event) => {
    if (!event.target.closest?.("[data-task-id]")) hideTaskPeek();
  });
  executionMap.addEventListener("wheel", (event) => {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    state.flow.forecastAutoFit = false;
    setForecastZoom(state.flow.forecastZoom * Math.pow(2, reactFlowWheelDelta(event)), {
      clientX: event.clientX,
      clientY: event.clientY,
    });
  }, { passive: false });
  executionMap.addEventListener("keydown", (event) => {
    if (["+", "="].includes(event.key)) { event.preventDefault(); state.flow.forecastAutoFit = false; setForecastZoom(state.flow.forecastZoom * FORECAST_ZOOM_STEP); }
    if (["-", "_"].includes(event.key)) { event.preventDefault(); state.flow.forecastAutoFit = false; setForecastZoom(state.flow.forecastZoom / FORECAST_ZOOM_STEP); }
    if (event.key === "0") { event.preventDefault(); state.flow.forecastAutoFit = false; setForecastZoom(1); }
    if (event.key.toLowerCase() === "f") { event.preventDefault(); state.flow.forecastAutoFit = true; fitForecast(); }
  });
  let forecastResizeTimer = null;
  window.addEventListener("resize", () => {
    updateFlowMinimapViewport();
    if (!state.flow.forecastAutoFit) return;
    clearTimeout(forecastResizeTimer);
    forecastResizeTimer = setTimeout(fitForecast, 120);
  });
  document.addEventListener("fullscreenchange", () => {
    window.setTimeout(() => {
      if (document.fullscreenElement === $("#flowViewport")) fitFlow();
      if (document.fullscreenElement === $("#executionMapFrame")) fitForecast();
      if (!document.fullscreenElement) {
        updateFlowMinimapViewport();
        updateForecastZoomControls();
      }
    }, 80);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !document.querySelector(".graph-fullscreen")) return;
    const fullscreenGraph = document.querySelector(".graph-fullscreen");
    fullscreenGraph?.classList.remove("graph-fullscreen");
    document.body.classList.remove("graph-fullscreen-open");
    renderDetailModeToggle();
    window.setTimeout(() => {
      if (fullscreenGraph?.id === "flowViewport") fitFlow();
      if (fullscreenGraph?.id === "executionMapFrame") fitForecast();
      if (state.selectedTaskId && state.detailMode === "sidebar" && !$("#taskPeek")?.classList.contains("hidden")) openInspector();
    }, 80);
  });
  $("#scanButton").onclick = async () => {
    state.scan = await api(`/api/episodes/${encodeURIComponent(state.episodeId)}/scan`);
    renderRisk();
    toast("快速扫描完成");
  };
  $("#deepScanButton").onclick = async () => {
    state.scan = await api(`/api/episodes/${encodeURIComponent(state.episodeId)}/scan?deep=true`);
    renderRisk();
    toast("制品哈希核验完成");
  };
  $("#riskReturnButton").onclick = () => activateView("production");
  $("#repairButton").onclick = openRepairPreview;
  $("#repairPreviewClose").onclick = () => $("#repairPreviewDialog").close();
  $("#repairPreviewCancel").onclick = () => $("#repairPreviewDialog").close();
  $("#repairPreviewDialog").oncancel = (event) => { event.preventDefault(); $("#repairPreviewDialog").close(); };
  $("#repairPreviewApply").onclick = async () => {
    const button = $("#repairPreviewApply");
    button.disabled = true;
    try {
      await sendCommand("recover", { apply: true, deep: Boolean(state.scan?.deep) });
      $("#repairPreviewDialog").close();
      state.scan = await api(`/api/episodes/${encodeURIComponent(state.episodeId)}/scan${state.scan?.deep ? "?deep=true" : ""}`);
      renderRisk();
    } finally {
      button.disabled = false;
    }
  };
  $("#copyTopology").onclick = async () => {
    const projection = topologyProjection();
    await navigator.clipboard.writeText(JSON.stringify(projection, null, 2));
    if (state.agentDataMode === "delta") {
      state.agentDataAfter = state.cursor;
      renderTopology();
    }
    toast("Agent 拓扑 JSON 已复制");
  };
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (!$("#taskPeek")?.classList.contains("hidden")) {
      hideTaskPeek({ restoreFocus: true });
      return;
    }
    closeDrawers();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") return;
    reconcileBackend({ source: "visibility" }).then((recovered) => {
      if (!recovered) scheduleFrontendResync();
    });
  });
}

window.addEventListener("error", (event) => reportFrontendFault("脚本运行", event.error || new Error(event.message)));
window.addEventListener("unhandledrejection", (event) => reportFrontendFault("异步操作", event.reason));
guardedRender("交互绑定", bindGlobalEvents);
loadEpisodes().then(() => {
  state.lastSuccessfulReconcileAt = new Date().toISOString();
  setConnectionPhase("synced");
}).catch((error) => {
  reportFrontendFault("后端连接", error);
  toast(`加载失败：${error.message}`, "error");
  scheduleFrontendResync();
});
