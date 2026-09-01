# 状态监督产品问题台账

状态：持续维护

路线与排期：[`PRODUCT_ROADMAP.md`](PRODUCT_ROADMAP.md)

## 状态词汇

| 状态 | 含义 |
|---|---|
| `AUTO_VERIFIED` | 已实现且有自动测试；不等于用户已觉得好用 |
| `ACCEPTANCE_PENDING` | 已有实现或修复，但必须由真实浏览器/真实用户旅程验收 |
| `IN_PROGRESS` | 已进入当前迭代并有部分实现，但完整验收条件尚未满足 |
| `PLANNED` | 已进入路线图，尚未完成 |
| `DESIGN_DECISION` | 需要用原型或验收测试固定交互，不应靠聊天措辞猜测 |
| `LONG_SHADOW` | 只能在真实长生产中验证 |
| `RETIRED` | 明确被更好方案取代；保留原因与证据 |

优先级：P0 会破坏数据、权限、输入或生产连续性；P1 阻断主工作流或制造状态谎言；P2 降低理解和效率；P3 为视觉与增强。

## K — 后端状态、权威与韧性

| ID | P | 状态 | 要求与验收 |
|---|---:|---|---|
| K-01 | P0 | `ACCEPTANCE_PENDING` | 关闭、崩溃或重启前端不影响后端任务、租约和事件；重开从 cursor 续接。 |
| K-02 | P0 | `AUTO_VERIFIED` | Human UI 与 Agent API 是同一后端的等权命令入口，任何一端都不是状态权威。 |
| K-03 | P0 | `ACCEPTANCE_PENDING` | SSE 连接状态与事件 cursor 定期对账；“显示在线但漏事件”能自动恢复。 |
| K-04 | P0 | `AUTO_VERIFIED` | current lineage 与历史 lineage 分离；旧产物漂移只做历史审计，不得误阻塞当前任务。 |
| K-05 | P0 | `AUTO_VERIFIED` | 人类可撤销批准、重新批准；只失效因果后代，不伤害无关 sibling。 |
| K-06 | P1 | `AUTO_VERIFIED` | 临时路线替换保留稳定输出合同、change lineage、旧路线退役记录和局部恢复。 |
| K-07 | P0 | `AUTO_VERIFIED` | 所有 mutating command 版本绑定、幂等；重试同一 request ID 不产生重复动作。 |
| K-08 | P1 | `PLANNED` | denial 必须说明原因、合法恢复动作、所需权限和是否会中断 live lease。 |
| K-09 | P1 | `PLANNED` | UI 投影损坏可从事件重建；前端 local state 不能覆盖后端真相。 |
| K-10 | P1 | `PLANNED` | 人类决定、反馈投递、任务领取、返修和恢复形成可查询的因果日志。 |
| K-11 | P1 | `PLANNED` | 当前路线进度排除 cancelled/superseded 节点，历史路线单独归档。 |
| K-12 | P1 | `LONG_SHADOW` | 服务重启、长时断连、并发领取和重放在真实生产下不产生双租约或状态漂移。 |
| K-13 | P1 | `AUTO_VERIFIED` | review-context hash 只绑定候选、任务相关规则与依赖；全局 cursor 仅保留在响应 envelope。无关 sibling 批准不会使已签发上下文失效，相关标注仍会使其失效；两条回归与全量 62 项测试已通过。 |
| K-14 | P0 | `AUTO_VERIFIED` | lease 前投影结构化语义冲突，确定性内核保存冲突原文、来源、置信度和最小影响范围并创建 `gap`；显式 route supersession 不误报。PRE13 专项与全量 70 项测试通过。 |

## U — Human UI 交互安全

| ID | P | 状态 | 要求与验收 |
|---|---:|---|---|
| U-01 | P0 | `ACCEPTANCE_PENDING` | 点击 textarea 后光标持续存在；live delta 不抢焦点。 |
| U-02 | P0 | `ACCEPTANCE_PENDING` | 未提交输入、输入法组合态、文本选区和撤销栈不被刷新清空。 |
| U-03 | P0 | `ACCEPTANCE_PENDING` | 点击输入、已有标注、草稿托盘、阻塞项或 disclosure 不会滚到详情顶部。 |
| U-04 | P0 | `ACCEPTANCE_PENDING` | 状态与归属、上下文、证据、程序硬门禁、标注与变更均可正常展开/收起。 |
| U-05 | P0 | `ACCEPTANCE_PENDING` | 详情内部点击不被图节点的广域 click handler 误识别为重新打开任务。 |
| U-06 | P0 | `PLANNED` | 浏览器级测试在 live delta 下验证焦点、草稿、滚动和折叠状态，而非只做源码字符串检查。 |
| U-07 | P1 | `PLANNED` | 浮动媒体、任务气泡和侧栏有明确层级，不互相覆盖到无法操作。 |
| U-08 | P1 | `ACCEPTANCE_PENDING` | 前端错误区分界面异常、后端不可达和已恢复待对账；恢复不重置后端，且不会把“重载界面”伪装成“重启服务”。隔离浏览器故障注入已通过，待真实使用验收。 |
| U-09 | P2 | `PLANNED` | 键盘焦点、Esc 关闭、Tab 顺序、触控和鼠标交互一致。 |
| U-10 | P2 | `PLANNED` | 对所有输入型组件统一采用“编辑安全岛”约束。 |
| U-11 | P1 | `ACCEPTANCE_PENDING` | 后端离线时不得无证据声称 Agent 不受影响；服务恢复后自动执行 catalog、overview、scan 与 cursor 全量对账，成功后清除旧 fault，否则给出明确“重试连接”入口。隔离端口已验证自动恢复，待真实长运行验收。 |

## H — 主页面、导航与旧交互兼容

| ID | P | 状态 | 要求与验收 |
|---|---:|---|---|
| H-01 | P1 | `IN_PROGRESS` | 主页面一屏回答：正在发生什么、下一步、什么需要我、哪些文件可审。 |
| H-02 | P1 | `IN_PROGRESS` | “待你处理”通知直接进入操作对象，显示紧迫度、影响和截止边界。 |
| H-03 | P1 | `IN_PROGRESS` | 可审事项聚合为首页提醒和图上节点角标；点击后定位同一对象，文字列表只作辅助，不另造工单状态。 |
| H-04 | P1 | `ACCEPTANCE_PENDING` | 顶栏页面选择器清楚显示当前位置；流程、结构、工位、风险、日志为独立页面。 |
| H-05 | P2 | `ACCEPTANCE_PENDING` | 主图占据主要视口；辅助条、时间流、领取机制按需展开，不永久压缩画布。 |
| H-06 | P1 | `IN_PROGRESS` | “进度怎么样”“有可审片吗”“发我看”“把这个打回”通过 Main Agent 可完成。 |
| H-07 | P1 | `IN_PROGRESS` | 网页点击和 Main Agent 命令产生同类型、同权限、同审计级别的后端事件。 |
| H-08 | P2 | `PLANNED` | Main Agent 可按页面/节点讲解系统，并高亮当前讲到的位置。 |
| H-09 | P1 | `IN_PROGRESS` | 首次进入提供最短路径引导、空状态和“我现在该做什么”说明。 |
| H-10 | P2 | `PLANNED` | Main Agent 负责监督、解释与自然语言操作，不兼任全部生产、全部审查和逐条人工转述。 |
| H-11 | P0 | `AUTO_VERIFIED` | K-14 产生的未决冲突成为 Human 待处理项和节点角标；任一入口打开同一张来源对照裁决卡，Human 只解决选中的 gap，无关支路继续。前端静态契约与 PRE13 流程回归通过，真实浏览器接受度留给 Episode 13。 |

## G — 拓扑、时间与多视角画布

| ID | P | 状态 | 要求与验收 |
|---|---:|---|---|
| G-01 | P1 | `ACCEPTANCE_PENDING` | 默认分层展示，避免 ComfyUI 式全图摊平；全图保留为可选诊断总览。 |
| G-02 | P1 | `PLANNED` | 展示当前节点之后的完整释放计划，包括“完成一个后并行启动三个”。 |
| G-03 | P1 | `PLANNED` | 动画制作中的真实并行、审查隔离、返修回路和 Sub Agent 明确可见。 |
| G-04 | P1 | `PLANNED` | 非线性依赖、路线替换、反馈回边和流动领取不能被画成固定阶段流水线。 |
| G-05 | P2 | `PLANNED` | 支持交付、内容、任务、Agent、时间、风险多个 lens，底层仍是一份状态。 |
| G-06 | P2 | `PLANNED` | 生产时间流可定位事件、计划变化和当前 attention boundary。 |
| G-07 | P2 | `PLANNED` | 大图提供小地图、视口框和点击/拖动定位。 |
| G-08 | P2 | `PLANNED` | 所有图统一 +/-、适配、全屏、双指平移、捏合缩放和灵敏度。 |
| G-09 | P2 | `PLANNED` | 字号和节点可读性随缩放有合理下限；提供文字/画布放大。 |
| G-10 | P1 | `ACCEPTANCE_PENDING` | 单击查看详情；双击或明确控件展开后续节点。必须消除一次手势触发两动作。 |
| G-11 | P2 | `PLANNED` | 气泡/侧栏 toggle 用图形和明确当前状态表达，不用“下次用侧栏”等歧义文案。 |
| G-12 | P2 | `PLANNED` | 气泡展示完整详情并内部滚动，可拖动、缩放、关闭；全屏默认使用气泡。 |
| G-13 | P2 | `PLANNED` | 结构页独占视口，不依赖全页纵向和横向滚动条读图。 |
| G-14 | P3 | `ACCEPTANCE_PENDING` | 状态变化时短暂边框微光；工作节点的真实上游输入沿边流动；待人处理用数字角标，动效严格绑定状态真相。 |
| G-15 | P2 | `PLANNED` | 聚焦节点时突出直接上下游和边语义，其余关系降噪但可恢复。 |

## C — 上下文、提示词与注意力透明度

| ID | P | 状态 | 要求与验收 |
|---|---:|---|---|
| C-01 | P1 | `PLANNED` | 节点详情可直接查看当前 Agent 实际将收到的有效上下文。 |
| C-02 | P1 | `PLANNED` | 区分长期稳定预置、继承后局部修改、临时追加、完整重写和运行时事实。 |
| C-03 | P1 | `PLANNED` | 显示组合顺序、来源路径、版本/哈希、适用范围和谁做了修改。 |
| C-04 | P1 | `AUTO_VERIFIED` | Agent 胶囊包含相关人类反馈原文，不只包含 ID。 |
| C-05 | P1 | `PLANNED` | Main Agent 收到压缩影响摘要，制作 Agent 在安全边界收到精确正文。 |
| C-06 | P1 | `AUTO_VERIFIED` | 非破坏前提的反馈等待下一 attention boundary；前提失效才中断 live lease。 |
| C-07 | P2 | `PLANNED` | 超长文件显示前段摘录、结构化粗略摘要、原路径和剩余长度，不显示“预览失败”即结束。 |
| C-08 | P2 | `PLANNED` | 用户可比较 baseline、局部改动与最终 effective context。 |
| C-09 | P1 | `PLANNED` | 反馈投递时机、目标 Agent、是否中断、是否已消费在日志和 UI 都可验证。 |
| C-10 | P2 | `LONG_SHADOW` | 记录 Agent 额外 explain/reread 次数，校准“最小充分”而非盲目最短。 |
| C-11 | P1 | `PLANNED` | 任务目标、required artifact roles、提交校验和 CLI 帮助保持一致；Agent 不需猜测文本与媒体证据究竟是否必交。 |
| C-12 | P0 | `AUTO_VERIFIED` | Human 对 gap 的 scoped override、来源和 resolution 同时进入下一次 author capsule 与独立 review capsule；通用 gap-resolution 与冲突专项回归均通过，投递延迟进入冻结 metrics。 |

## A — Agent 编排、并行与闲置合法性

| ID | P | 状态 | 要求与验收 |
|---|---:|---|---|
| A-01 | P1 | `PLANNED` | 显示完整计划、Ready Pool、最佳下一任务、并行容量、当前占用和释放条件。 |
| A-02 | P1 | `AUTO_VERIFIED` | 区分合法闲置与存在可匹配 Ready 任务时的非法闲置。 |
| A-03 | P1 | `AUTO_VERIFIED` | 区分有进展工作与重复证据/空烧 token。 |
| A-04 | P1 | `AUTO_VERIFIED` | 已完成或语义重复任务不能为“看起来不闲置”再次分配。 |
| A-05 | P1 | `PLANNED` | meaningful progress 必须减少到用户交付目标的距离。 |
| A-06 | P1 | `PLANNED` | 真实 Agent 数量、每个 Sub Agent 当前任务和审查隔离在 Human UI 可见。 |
| A-07 | P1 | `PLANNED` | 任务完成即释放直接下游；同列/同阶段任务无需互等。 |
| A-08 | P2 | `PLANNED` | 稳定 roster 与能力匹配；作者容量和独立审查容量分开。 |
| A-09 | P1 | `AUTO_VERIFIED` | Agent API 默认给唯一 best-next、最小胶囊、合法 recovery 和一次提交入口。 |
| A-10 | P2 | `PLANNED` | 任务按确定性、创造性、复用性和错误扩散成本路由模型。 |
| A-11 | P2 | `PLANNED` | 场景记录 exact-spec、co-design、autonomous 三种 `automation_mode`，允许混用。 |
| A-12 | P1 | `LONG_SHADOW` | 真实生产测量队列等待、并行利用率、重复工作、token-without-progress 和 idle 判定误报。 |
| A-13 | P0 | `AUTO_VERIFIED` | coordinator 的扩容建议生成 scoped dispatch reservation，防止旧 author 串行吃完新释放支路；三名兼容 author 获得三项独立预留，三条 lease 在首个 release 前真实重叠，错误领取被拒绝。 |

## M — 音视频验收与人类决定

| ID | P | 状态 | 要求与验收 |
|---|---:|---|---|
| M-01 | P1 | `AUTO_VERIFIED` | 大型本地音视频用 Range 流式播放，不需整文件装入 Codex 内置播放器。 |
| M-02 | P1 | `PLANNED` | 主页面/任务详情直接进入可审媒体，不必从 Finder 打开。 |
| M-03 | P1 | `AUTO_VERIFIED` | 标注绑定精确时间和可选归一化画面坐标。 |
| M-04 | P1 | `AUTO_VERIFIED` | 支持单条立即提交和跨任务整集草稿批量提交。 |
| M-05 | P0 | `ACCEPTANCE_PENDING` | live delta 不清空标注输入，不改变播放时间、草稿或媒体卡滚动。 |
| M-06 | P2 | `PLANNED` | 浮动播放器可拖动、调整尺寸、最小化和恢复，不限于小气泡/全屏。 |
| M-07 | P2 | `PLANNED` | 浮动播放器内仍可标记时间与画面位置。 |
| M-08 | P1 | `PLANNED` | Human UI 明确提供批准、打回、撤销批准、重新批准及其影响预览。 |
| M-09 | P1 | `AUTO_VERIFIED` | 批准撤销产生审计事件并局部失效下游；重新批准产生恢复 receipt。 |
| M-10 | P1 | `PLANNED` | Agent 体验报告验证每条标注是否、何时、通过哪个 capsule 被看到和执行。 |
| M-11 | P1 | `PLANNED` | 短反馈、问号、可能重复项都保留；只能由人类显式撤回，可分类等待澄清。 |
| M-12 | P2 | `PLANNED` | 媒体卡显示制品版本、hash、当前决定、返修代数和对应任务 lineage。 |

## R — 风险、恢复与可理解运维

| ID | P | 状态 | 要求与验收 |
|---|---:|---|---|
| R-01 | P1 | `PLANNED` | 风险卡用人话解释发生了什么、当前影响、建议动作和安全边界。 |
| R-02 | P1 | `PLANNED` | 当前阻塞、历史审计和 Agent 健康信号分开显示。 |
| R-03 | P1 | `AUTO_VERIFIED` | 扫描与核验只读；安全修复必须先预览再应用。 |
| R-04 | P1 | `AUTO_VERIFIED` | 不使用原生 `window.confirm` 处理高价值修复。 |
| R-05 | P1 | `PLANNED` | 预览显示目标对象、当前 lineage、将产生的事件、幂等键和回退方式。 |
| R-06 | P1 | `AUTO_VERIFIED` | 历史误阻塞恢复是显式、幂等、可审计事件。 |
| R-07 | P2 | `PLANNED` | 页面先给安全推荐，再按需展开内部 JSON/分类。 |
| R-08 | P2 | `LONG_SHADOW` | 验证恢复不会把局部故障升级成全局重置或静默丢失生产证据。 |

## P — Harness 哲学、自动化杠杆与演化

| ID | P | 状态 | 要求与验收 |
|---|---:|---|---|
| P-01 | P1 | `PLANNED` | 不砍掉复杂性；把复杂性放到内核、领域编译器、验证器、案例库和恢复机制。 |
| P-02 | P1 | `PLANNED` | 单次 Agent 调用只消费最小充分工作集，而不是整套 Harness 文档。 |
| P-03 | P1 | `PLANNED` | 确定性不变量进入代码/schema；创造性视觉判断保留给强模型和真实 probe。 |
| P-04 | P2 | `PLANNED` | 人工精细分镜 + 简单 Skill 保留为质量基线、案例来源和失败降级，不是最终形态。 |
| P-05 | P2 | `PLANNED` | 建设通用状态内核 + 数学动画领域编译器 + 可复用视觉语法/偏好评估器。 |
| P-06 | P2 | `PLANNED` | 新问题按观察、候选、校准、合并/退役演化，不直接堆进永久提示词。 |
| P-07 | P1 | `LONG_SHADOW` | 统计人类分钟/获批分钟、产量/天、token/获批分钟和首轮人审通过率。 |
| P-08 | P1 | `LONG_SHADOW` | 统计 automatic false pass、晚期结构返工、额外 reread、恢复成本和 Main Agent 转述负担。 |
| P-09 | P1 | `AUTO_VERIFIED` | PRE13-01、PRE13-02、全量 70 项测试和 580 次聚焦压力断言通过；版本以 `state-supervision-pre13-2026-09-01` tag 冻结。Episode 13 生产 Session 不热修系统，只记录自然问题，后续评估 Session 再优化。 |
| P-10 | P2 | `PLANNED` | 每个新增机制必须以质量不下降前提下的成本/产量收益“付租金”。 |

## V — 视觉语言、可读性与性能

| ID | P | 状态 | 要求与验收 |
|---|---:|---|---|
| V-01 | P2 | `PLANNED` | 借鉴 Archify 的架构层次、对齐、关系线、留白与聚焦，不照搬全图平铺。 |
| V-02 | P2 | `PLANNED` | 保留架构图质感、ComfyUI 可探索性、多层级、多视角和时间流。 |
| V-03 | P2 | `PLANNED` | 统一字号、节点密度、颜色语义和状态表达；文字不依赖高倍浏览器缩放才能读。 |
| V-04 | P3 | `PLANNED` | 状态微光和数据流动只在真实事件发生时短暂出现。 |
| V-05 | P2 | `PLANNED` | 长上下文默认只展示摘录、摘要和原路径，可按需加载全文。 |
| V-06 | P2 | `PLANNED` | 常用屏幕尺寸下一页呈现一个主任务，不依赖全局纵向滚动。 |
| V-07 | P2 | `LONG_SHADOW` | 大图、长事件流和 4K 媒体在真实生产规模下有明确性能预算和降级策略。 |

## 新问题登记模板

```text
ID: <category-next-number>
Observed at: <event/cursor/page/task/artifact>
User-visible failure: <what the Human or Agent could not do or understand>
State truth affected: <yes/no/unknown>
Data or authority risk: <yes/no>
Reproduction: <short deterministic path>
Expected behavior: <observable acceptance criterion>
Dependencies: <IDs>
Priority/status: <P0-P3> / <state>
Evidence: <log, screenshot, test, capsule or file path>
```

登记后不直接把描述写成永久规则。先确定它是交互缺陷、投影缺陷、状态不变量缺陷、领域能力缺口还是一次性偏好，再进入对应 Phase。
