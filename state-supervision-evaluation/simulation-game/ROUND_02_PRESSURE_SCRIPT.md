# Round 02 · 双界面连续性压力演练

> 本文件只给 game master 和事后评估使用。盲测 Agent 不得读取本文件、源码、
> 数据库、旧轮报告或隐藏 oracle。演练只使用占位制品，不做真实动画、TTS、ASR
> 或 4K 渲染。

## 目标

本轮不再重复验证“系统能不能把八个任务跑完”，而是验证一个反馈闭环是否真的
贯穿四个表面且保持同一事实：

1. Human Interface 产生审批、撤销和精确音视频标注；
2. 持久后端记录可因果查询的命令、事件、制品、决定和投递边界；
3. Agent Interface 只在合法注意力边界收到原文、位置、时间和变更原因；
4. 制作 Agent 采取返修动作后，Human Interface 能恢复并展示同一结果。

同时验证前端与后端相互独立：页面刷新不得打断后端；隔离后端重启不得丢状态，
页面必须诚实区分“界面重载”“重试连接”和“服务未运行”。

## 八分钟上限

| 时间窗 | 动作 | 压力点 | 必须留下的证据 |
| --- | --- | --- | --- |
| 00:00–00:45 | 从全 TTS 初始计划创建新分集并完成 T001。 | 初始状态不得预知后半录音、返修或故障。 | 初始 overview、cursor、任务图。 |
| 00:45–01:45 | 并行释放音频、动画任务；盲测 Agent 领取 T010。 | 并发领取、幂等提交、非阶段栅栏。 | lease、capsule hash、命令与事件。 |
| 01:45–02:30 | T010 提交后先去做另一项工作，独立审查再打回。 | 返修不能中断当前 lease，只能在下一注意力边界投递。 | review return、当前 lease、deferred reason。 |
| 02:30–03:20 | 临时上传后半人声，把 T012 切到 T112。 | 原系统无压力剧情先验；旧 TTS 路线失效但前半和视觉工作保持有效。 | route switch、失效范围、替代胶囊。 |
| 03:20–04:10 | 打开 T040 气泡，滚到媒体标注区，保持输入焦点和未提交草稿；后台继续产生 delta。 | 任何 delta 都不得抢焦点、清空输入、重置气泡滚动或折叠状态。 | delta 前后 value、activeElement、scrollTop、details.open。 |
| 04:10–05:00 | 用网页提交一条带时间与归一化画面坐标的返修意见；先批准，随后明确撤销批准。 | UI 必须有自然入口；批准、撤销、返修意见是不同命令，不能靠覆盖历史实现。 | annotation/change/decision ID、原文、时间、x/y、event seq。 |
| 05:00–05:45 | 让盲测 Agent 在持有其他 lease 时继续工作，再到下一边界领取返修。 | 报告反馈究竟在中途打断还是任务边界进入；胶囊必须含原文而不只是 ID。 | delivery boundary、capsule manifest、Agent action。 |
| 05:45–06:35 | 用 Main Agent/公开 CLI 完成一次与网页等权的重批或再次打回，并让制作 Agent 返修提交。 | 两个入口写入同一后端、同一权限与审计模型；重复 request ID 必须幂等。 | 两种 origin 的 canonical event 与最终状态。 |
| 06:35–07:15 | 仅刷新/重载页面，后台继续产生事件；随后在隔离端口短暂重启后端。 | 前端故障不影响后端；后端重启后从 cursor 续接，页面不得显示伪成功。 | 重载期间事件、重连 cursor、状态库 last_seq、UI 文案。 |
| 07:15–08:00 | 停止引入剧情，冻结并对账。 | 未完成也必须按时停止并诚实报告。 | Human、Agent、Backend、cross-surface 四份结果。 |

## Human Interface 验收

- 首页五秒内能回答：谁在工作、什么待我处理、哪条路线改变、下一步是什么。
- 待处理提醒与节点未读角标指向同一任务，点击任一入口都聚焦同一节点。
- 气泡可滚动；输入、滚动、折叠、拖动/尺寸状态不被实时 delta 重置。
- 音视频标注保留媒体时间和可选归一化画面坐标。
- 批准、打回、撤销批准和重新批准均有明确入口与当前状态，动作/状态不混淆。
- 服务离线时不得把“只重启界面”包装成可恢复后端的按钮；恢复后能自动或明确重连。

## Agent Interface 验收

- 盲测 Agent 只读生成的 `MISSION.md`、`environment.json`、公开 wrapper/help、
  task capsule 与任务绑定引用。
- 每条人类反馈都报告：ID、原文、分类、时间、x/y、产生事件、进入胶囊的 hash、
  投递边界、被哪个动作消费。
- 正在执行的 lease 不因新反馈被抢占；高优先级反馈在下一个合法注意力边界出现。
- capsule 必须交付正文和绑定上下文，不能只有 annotation/change ID。
- Agent 不依赖聊天历史也能判断 Human 最终权限和合法下一动作。

## Backend 与恢复验收

- 后端压力套件的读取确定性、并发 lease、幂等、route switch、恢复边界全部通过。
- 前端重载期间后端事件继续递增，重连后从旧 cursor 补齐且无重复副作用。
- 后端进程重启后 catalog、episode DB、last_seq、lease 与决定历史保持一致。
- 网页动作和公开 CLI 动作都落为可查询的 canonical command/event；来源不同，
  权限与状态转移规则相同。
- 任何失败都能从 command → event → capsule → Agent action 追溯，不以截图替代日志。

## 输出

- `BACKEND_STRESS_REPORT.json`
- `HUMAN_INTERFACE_REPORT.md`
- `AGENT_EXPERIENCE.md`
- `CROSS_SURFACE_TRACE.json`
- `VERIFICATION_EVIDENCE.json`
- `RETROSPECTIVE.md`

所有报告必须区分：已自动验证、浏览器实测、Agent 自报、只做静态检查、未验证。
演练期间不修源码；冻结证据后再把缺陷排入 backlog。
