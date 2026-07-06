# 项目协作约定

本文件给 Codex、Claude Code 和其他 agent 使用。`CLAUDE.md` 可以视为同一套规则的 Claude 版本；两边涉及项目结构、Git、清理和多 agent 协作的规则应保持同步。

## 项目定位

这是一个 B 站教学视频生产仓库，用来制作《数学物理方法》等系列课程。

- 视频重点使用 Manim、Remotion 或其他动画工具做可视化讲解。
- 每节课配套 Jupyter Notebook，用于练习、数值实验、补充推导和部分证明。
- 声音生产链路包含后期声音转换，目标是形成系列化、角色化的课程风格。
- 详细课程设定和问答见 `vault/init.md`。

## 成品呈现边界：不要外化制作意图

所有面向学生、观众或最终用户的成品，包括视频画面、字幕、TTS 文稿、Notebook 正文、网页界面和交互控件文案，都不能把 agent 的制作意图、审查口径、工程 workaround、设计哲学或“为什么这样做”的内部说明直接写到台前。成品文字应只承担内容本身的任务：提出问题、标注数学对象、给出操作指令、展示反馈、解释概念或给出必要结论。

典型禁止项包括：在画面或 Notebook 正文里写“这个 Notebook 不是……而是……”“这里不用 interact 是为了避免闪动”“这个动画想表达……”“为了符合 pipeline/skill/review gate……”“这个控件是稳定版”“下面只是反馈不是主内容”等作者意图或工程解释。学生/观众需要看到的是数学任务和对象关系，而不是制作过程的自我说明。

这些内容有自己的位置：`storyboard.md`、`timeline.json`、Notebook contract、scene contract、`experiment-log.md`、review 报告、issue JSON、代码注释或技能文档。写作和审查时必须做一次“台前/后台”检查：如果一句话是在解释 agent 为什么这样设计，而不是帮助学习者完成当前数学动作，就移到后台文件或删掉。反复出现的设计意图外化必须作为 `presentation_boundary_failure` 或对应技能里的同类失败记录进 human/agent feedback 和 future regression。

## 与 learning vault 的边界和同步

`/Volumes/bocchi/myLectures` 是视频课的 Git 生产仓库，负责动画代码、素材、渲染流程、项目分支和整体版本控制。`/Volumes/bocchi/myLectures/vault` 是独立的 Obsidian vault 子仓库，负责正式视频提纲、文案、分镜、Notebook 和 Obsidian 插件配置。`~/Documents/learning` 是用户的日常学习 vault，负责个人学习、读书笔记、灵感、推导、Zotero 上下文和长期能力追踪。

两边的默认关系是：**learning 做大脑，myLectures 做片场**。不要把整个 `~/Documents/learning` 同步、复制或嵌入进本仓库；不要用 symlink/硬链接共享同一批真实文件；不要把 learning 的 `.obsidian/`、`.agents/` 学习状态、复习队列或个人 MOC 当作本仓库的一部分提交。

制作知识内容时可以互相交流：如果用户提到 learning 中的文案、Clippings、概念笔记或课程笔记，agent 可以按需读取并提炼素材，然后在本仓库的 vault 子仓库中改写成正式生产文件，例如 `vault/videos/NNNN-slug/script.md`、`vault/videos/NNNN-slug/storyboard.md`、`vault/videos/NNNN-slug/NNNN-slug.md` 或配套 `notebook.ipynb`。正式视频版本以 vault 文件为准，必要时在稿件中记录素材来源。

视频制作中产生的长期知识沉淀，可以按用户要求回写到 learning 的概念笔记、课程笔记或复习记录；但不要把渲染产物、临时素材、项目脚本、Git 分支状态、Obsidian workspace 配置或视频生产流水线状态回写到 learning。

除非用户明确要求，myLectures 的 agent 不要主动修改 learning 的 `.agents/LEARNING_STATE.md`、学习队列、能力快照或日常学习计划。跨 vault 操作应只围绕知识内容、文案素材和可复用理解，其他方面保持隔离，少互相打扰。

## 仓库结构

```text
vault/           Obsidian vault 子仓库；Obsidian 只打开这个目录
  .obsidian/     Obsidian 插件、主题和 vault 配置
  catalog.md     视频目录索引
  init.md        课程设定和问答
  templates/     笔记、脚本、分镜、Notebook 等模板
  videos/        每个视频的课程笔记目录，命名：编号-英文slug/
    NNNN-slug/
      NNNN-slug.md    主文件，包含 YAML frontmatter
      script.md        配音稿
      storyboard.md    分镜与动画设计
      notebook.ipynb   配套 Notebook 练习
videos/          每个视频的工程目录，命名：编号-英文slug/
  NNNN-slug/
    src/               本集专属动画源代码
    assets/            本集专属素材
    exports/           导出产物，不进入 Git，README 除外
lib/              跨视频复用的代码库，例如 Manim helper、Notebook 工具函数
shared/           跨视频复用的素材，例如角色 sprite、字体、音效、封面模板
scripts/          仓库级脚本，例如新建视频、批量渲染、发布检查、音频处理
.agents/          agent 协作、自动化流程和项目专用技能说明
```

## 视频生产流程

- 每个视频用 `vault/videos/NNNN-slug/NNNN-slug.md` 追踪状态，frontmatter 中维护 `id`、`title`、`status`、`collection`、`episode`、`tags` 等信息。
- 新建视频时同步更新 `vault/catalog.md`。
- 先在 vault 中写 `script.md` 和 `storyboard.md`，再进入动画代码。
- 本集一次性代码放在 `videos/NNNN-slug/src/`。
- 跨集复用代码放在 `lib/`，跨集复用素材放在 `shared/`。
- `exports/` 只放导出的视频、音频、封面和中间产物，默认不提交。

## 动画制作强制审查机制

每次做 Manim、Remotion 或其他课程动画，都必须先完整阅读 `.agents/skills/lecture-animation-pipeline/SKILL.md`，并从头到尾阅读其中关于动画制作哲学和 QC 的核心引用，至少包括 `references/20-math-object-driven-animation.md`、`references/30-visual-language-and-style.md`、`references/40-production-loop-and-qc.md`、`references/41-production-output-contract.md` 和 `references/50-known-failures-and-fixes.md`。不得只凭记忆、摘要或旧经验开工。

遇到难的、新的、公式密集的、视觉语言不确定的任务时，还要继续查找技能中指向的参考案例和仓库里已有的同类代码、分镜、review 输出，例如用 `rg` 搜索相似 scene、stage direction、experiment log 和 handoff。先理解既有做法，再决定是否复用、改造或明确偏离。

动手写动画前必须有明确的舞台调度：说明每个时间段主要数学对象、公式、坐标系、画面区域、颜色语义、进出场、转场逻辑和清场规则。不能把画面当作一个固定角落的重写板；必须按数学关系分配和重新分配整块画布。

`storyboard.md` 和 `timeline.json` 都必须考虑舞台调度，但职责不同。`storyboard.md` 是给人审核和修改的分镜说明，必须用清楚的自然语言解释大分镜怎么划分、为什么哪些 S 段要合并、每个大分镜的视觉语言、数学对象、舞台区域、转场逻辑和审查重点，方便用户直接改。`timeline.json` 是给 agent/脚本编译动画和对齐音频用的精确合同，必须按真实时间写清 segment、scene/group、对象、driver、入场/出场、公式、音频窗口、转场和审查锚点，不能只写笼统 visual action。

动画做完后，交付前必须开独立 subagent 或独立审查 pass，按 `.agents/skills/lecture-animation-pipeline/SKILL.md` 及其引用逐条严格检查。审查范围不能只看截图或 review 视频，还必须包括动画代码、stage direction、`timeline.json`、SRT/alignment、formula manifest、experiment log，以及该段与前后段的风格标准、时间衔接和转场逻辑。

涉及坐标平面、网格、采样点阵或背景格线时，默认要求网格与坐标轴严格对齐：原点必须是格点，横轴和纵轴必须正好压在对应网格线上，不能落在两条格线之间。任何故意偏移的网格都必须在 stage direction 和 experiment log 中说明数学理由，并在审查报告里复核。

subagent 审查要达到挑剔审片标准：明确指出不符合 skill 哪一条要求、发生在第几秒或哪个文件位置；检查是否存在数学对象不真实、假动画、公式或文字重叠、画面挤在角落、空间利用不足、视觉语言不清晰、无意义颜色填充、多余线段或框、陈旧对象残留、updater 残影、字幕/音频/时间轴不对齐、review 视频缺声音、输出路径不合规、与前后段风格或转场冲突等问题。

subagent 审查必须按“抽象标准 -> 具体回归案例 -> 具体修复建议”的顺序组织。先根据 `.agents/skills/lecture-animation-pipeline/references/50-known-failures-and-fixes.md` 中的抽象标准逐条判断，例如舞台调度失败、意义不明或误导观众的视觉元素、数学对象身份/因果不真实、时间轴逐拍不对齐、空间利用效率低、视觉层级混乱、例子不服务教学目标等；再查本集 human-feedback、issue JSON 和 known failures 中的具体 `pattern_key` 作为依据；最后在报告中同时写出抽象 `standard_key`、具体 `pattern_key`、证据位置和修复路径。没有完全同款旧案例，也必须能根据抽象标准独立判断，不能因为“以前没列过”就放过。

公式、文字、面板、chip 或括号密集的 Manim 段，交给 subagent 前必须运行 `.agents/skills/lecture-animation-pipeline/tools/layout_check.py` 或等效的 scene-specific layout audit，并把 JSON 报告写到本集 `review/audits/<scene_slug>/`。检查必须覆盖 overlap、out-of-frame、container overflow 和 close-as-issue；任何一项失败都必须先修复、重渲、重新抽帧。若工具不适用，必须在 `experiment-log.md` 说明原因，并用明确 QC 帧补偿检查。

当函数图、坐标平面、采样点阵等主动数学对象与右侧运算板、公式板或说明文字同时出现时，必须先做舞台空间预留：图像区域要按需要左移、缩窄或让位，面板区域单独占位。layout audit 必须包含主动图像的 protected region；透明面板、公式或文字如果让活动函数图、采样点、坐标轴或局部构造难以读取，或把主数学对象降格成背景纹理，就算遮挡，不能通过。例子函数也必须为教学目标服务：讲函数乘积积分时，`f`、`g` 和乘积密度要有足够可见变化；任何面积、填充、条带必须明确对应被积分或比较的数学量，不能是意义不明的视觉装饰。

“遮挡”规则要智能执行，不是禁止所有图上标注。直接标注样本值、切线、导数、法向、局部线性近似、局部放大区域等，可以放在图上，但必须锚定到确切的数学对象，范围局部、文字短、轮廓可读、不会把主函数或采样过程变成背景，并且在局部说明结束后清场。如果需要较长解释或大面板，就必须移到侧边栏、底部公式 lane 或局部 inset，而不是盖在主图上。

subagent 的反馈必须写进本集 `review/audits/<scene_slug>/` 下的 Markdown 审查报告，报告文件名包含 review id、reviewer 和被审分支；需要拆成可修复队列的问题，同时写入 `review/issues/*.json`。每条反馈都要有严重度、skill 条款或引用、证据位置、影响、建议修复路径和当前状态，方便动画 agent 快速定位修改，也方便用户直接查看。

人工审片反馈会成为自动审查机制的一部分。用户每次指出的错误都必须写入本集 `review/human-feedback/` 的记录，并拆成 `review/issues/*.json`，带有 `source: human_review`、`pattern_key`、`must_check_in_future`、证据位置、影响、建议修复路径和当前状态；可复用的问题还必须同步到 `.agents/skills/lecture-animation-pipeline/references/50-known-failures-and-fixes.md` 或对应引用。之后任何 subagent 审查都必须先读取本集未关闭和已关闭的人审 issue、human-feedback 记录和 known failures，把它们当作回归测试；重复出现用户已经指出过的问题，一律判 `revise` 或 `blocked`，不能因为“整体能看懂”而放过。

subagent 或小组复审发现的新错误，如果主 agent 判断不是一次性小修、而是能防止后续复发的经验，也必须像人工反馈一样沉淀。记录位置为本集 `review/agent-feedback/`，并拆成 `review/issues/*.json`，建议使用 `source: accepted_agent_feedback`、`origin_source: subagent_review`、`accepted_by: <agent>`、`pattern_key`、`must_check_in_future: true`、`applies_to_authoring`、证据位置、影响和修复建议。可复用的抽象失败或具体案例还要同步到 `.agents/skills/lecture-animation-pipeline/references/50-known-failures-and-fixes.md` 或对应引用。未来制作和审查 agent 必须读取这些已接受的 agent 反馈；重复出现同一 `pattern_key` 时，按人工反馈同等标准打回。

同一套人工反馈也必须给制作动画的 agent 看。任何动画 agent 在写 storyboard、timeline、stage direction 或代码前，都必须先读取本集 `review/human-feedback/`、`review/issues/*.json` 中 `source: human_review` 或 `must_check_in_future: true` 的记录，以及 `50-known-failures-and-fixes.md`，整理成本次分镜的制作前规避清单。清单要写进 stage direction 或 `experiment-log.md`，逐条说明哪些 `pattern_key` 适用、采用什么构图/时间轴/代码保护来避免复现。没有制作前规避清单，不得开写动画代码；subagent 审查时也必须检查制作 agent 是否真的消费了这些反馈。

制作前规避清单的读取范围包括人工反馈和已接受的 agent 反馈：`review/human-feedback/`、`review/agent-feedback/`、`review/issues/*.json` 中 `source: human_review`、`source: accepted_agent_feedback` 或 `must_check_in_future: true` 的记录，以及 `50-known-failures-and-fixes.md`。普通未采纳的 subagent 临时意见不自动升级为永久规则；一旦主 agent 采纳并标记 `accepted_agent_feedback`，后续就必须按回归测试执行。

subagent 审片必须站在完全不懂该数学内容的观众视角，而不是默认观众已经知道结论。只要时间轴和画面动作没有逐拍对应、视觉因果需要靠先验知识补齐、采样过程跳步、符号结构误导、或画面有明显丑陋和不专业的地方，即使数学代码看似正确也必须打回。

真实数学对象和真实变换是硬门槛。审查报告必须明确核对关键变换的数学驱动和样本对应关系：例如函数乘 `-1` 必须是同一个 `f` 关于 x 轴的点wise 反射，内积从向量到函数必须能看见采样值成为分量、分量乘积求和、采样变密并过渡到积分，复函数共轭必须能看见它如何把自内积变成非负的 `|f|^2`。如果画面只是换了一条曲线、放了一个星号、画了几条线或摆了公式，而没有展示数学因果，一律判 `revise`。

只要 subagent 或自查发现任何问题，哪怕只是轻微丑陋、节奏不顺、转场别扭、颜色语义含糊或空间利用不充分，都不能标记为完成；必须回炉修改、重新渲染、重新抽帧、重新审查。

subagent 复审通过后，动画仍然不能直接提交。必须先把 review MP4、QC 帧或 contact sheet、音频路径、时间轴路径、代码路径、审查报告和已修复 issue 队列交给用户最终审片；只有用户明确说“通过”“可以提交”“commit”或同等意思后，agent 才能 stage/commit 这组动画改动。用户审片 gate 之前，`review/assignments.md` 可以写 `user_review_pending` 或类似状态，但不能把这组工作当作最终完成提交。

最终交付必须附上 review MP4、QC 帧或 contact sheet、音频路径、时间轴路径、代码路径、已执行的审查结论，以及是否已通过用户审片。

## Python 与 Manim

- Python 环境统一使用 `uv` 管理。
- 依赖写入 `pyproject.toml` 和 `uv.lock`。
- 运行命令优先使用 `uv run ...`。
- 本项目 Manim 使用 Manim Community Edition，命令入口是 `uv run manim ...`。
- 不要混用 ManimGL 或 `manimgl`。
- `.venv` 是本地环境入口，不提交。当前仓库位于 `/Volumes` 外接盘时，`.venv` 可以是指向 macOS 原生路径的符号链接，以避免 AppleDouble 元数据干扰安装。

## Git 约定

- 本仓库应保持 Git 化；如发现不是 Git 仓库，先初始化 Git，再继续修改。
- 本仓库本地 Git 用户建议配置为 `nikolastar <staryxyx@gmail.com>`。
- 每完成一组有意义的修改，都要及时 `git commit`，方便随时回滚。
- 动画生产例外：subagent 复审通过后，必须先等用户最终审片并明确批准提交；用户审片前不得 stage/commit 该组动画改动。
- 提交前必须运行 `git status --short`，确认只提交本次任务相关文件。
- 只 stage 当前任务相关文件，不要混入用户或其他工具造成的无关改动。
- 提交信息要简短明确，说明本次改动的目的。
- 不要提交临时文件、系统元数据文件、缓存、密钥或大体积生成物，除非用户明确要求。
- 不要提交 `._*`、`.DS_Store`、`.ipynb_checkpoints/`、`exports/*`、`.venv/`。
- 如果工作树里有用户或其他工具造成的无关改动，不要回退它们，也不要混入当前提交。
- `vault/` 是独立 Git 仓库/submodule。Obsidian Git 只在 `vault/` 内提交和推送课程笔记；外层项目 Git 只记录 `vault` 指向的 commit。需要固定“项目代码 + 文案版本”时，先在 `vault/` 内 commit/push，再在外层仓库 stage 并 commit `vault` 的 submodule 指针。
## 外部同步（myLectures-agents）

`AGENTS.md` 和 `.agents/skills/lecture-animation-pipeline/` 会同步到独立的公开 GitHub 仓库 [Vioano/myLectures-agents](https://github.com/Vioano/myLectures-agents)。同步清单在 `scripts/sync-agents-manifest.txt`，同步脚本在 `scripts/sync-agents.sh`。

- agent 修改了清单中列出的文件后，应提醒用户运行 `scripts/sync-agents.sh` 同步到外部仓库。
- agent 不要自动执行同步脚本，同步操作由用户决定。
- 如需添加更多文件到同步范围，编辑 `scripts/sync-agents-manifest.txt` 加一行路径即可。

## macOS 外置盘清理

本仓库位于 `/Volumes` 外接盘时，macOS 可能留下 AppleDouble 元数据文件，例如 `._AGENTS.md`、`._videos`。

- 定期在仓库根目录运行 `dot_clean .`，尤其是在复制文件、渲染素材、批量生成文件、提交前或切换分支前后。
- 运行 `dot_clean .` 后再执行 `git status --short`，确认没有 `._*`、`.DS_Store` 等垃圾文件进入待提交列表。
- `.gitignore` 已忽略常见 macOS 垃圾文件，但仍建议清理，避免外置盘目录里长期堆积无用元数据。

## 多 Agent / 多 Subagent 工作流

支持多个 agent 或 subagent 协作。生产正本的唯一工作区是 `/Volumes/bocchi/myLectures`；并行开发需要多个 checkout 时，临时 worktree 默认统一放在 `/Volumes/bocchi/myLectures-worktrees/`，不要散落创建任意 `/Volumes/bocchi/myLectures-*` 目录。

推荐目录形态：

```text
/Volumes/bocchi/myLectures-worktrees/
  claude-code-第x集分镜1-10/
  codex-subagent-第x集分镜11-20/
  审核/
```

这些目录只是临时并行 checkout，不是新的生产目录。最终代码和文档必须通过分支 merge 回 `/Volumes/bocchi/myLectures` 的目标分支；最终 review/final 输出应在合并后的主生产 checkout 中重新生成或明确登记。

- 每个 agent 从最新 `main` 创建自己的任务分支，例如 `codex/<short-task>`、`agent/<name>-<short-task>`。
- 不同 agent 不要共用同一个任务分支。
- 单 agent 连续生产时，默认在 `/Volumes/bocchi/myLectures` 内切换/创建分支，不必创建 worktree。
- 明确并行开发多个分镜、多集或独立审查任务时，可以使用 `git worktree`；每个 agent 一个任务分支、一个临时 worktree、一个明确文件范围。
- 创建 worktree 时默认使用 `/Volumes/bocchi/myLectures-worktrees/<agent-or-task>/`，例如 `git worktree add /Volumes/bocchi/myLectures-worktrees/codex-subagent-第x集分镜11-20 -b agent/codex-epx-s011-s020 main`。
- 不要创建其他仓库同级生产目录，例如 `/Volumes/bocchi/myLectures-0002-*`、`/Volumes/bocchi/myLectures-qoder-*`；也不要把 `/Volumes/bocchi/myLectures-worktrees/` 下的临时 checkout 当成长期正本。
- 新建或继续任意视频工程时，目录必须落在本仓库内部：`/Volumes/bocchi/myLectures/videos/NNNN-slug/`。例如第二课 TTS 工程应是 `videos/0002-mpm-2-hilbert_space_tts/`，和 `videos/0001-mpm-1-complex_numbers_tts/` 同级。
- 如确实需要让外部 CLI/subagent 做探索，优先让它在当前分支或临时分支上做只读审计；需要写文件时，先切到对应任务分支，并限定文件范围。写入完成后由主 agent 在当前仓库内 review、test、commit。
- 每个分支只修改自己任务范围内的文件；共享文件如 `vault/catalog.md`、`pyproject.toml`、`uv.lock`、`lib/` 以及 `vault` submodule 指针需要格外小心，提交前检查冲突风险。
- 每个 agent 在自己的分支上完成一组有意义修改后及时 commit。
- 合并前在任务分支运行 `dot_clean .`、`git status --short` 和必要的测试或渲染检查；如果任务在临时 worktree 中完成，先在该 worktree 内完成这些检查和提交。
- 合并时先更新 `main`，再将任务分支 merge 或 rebase 到最新 `main`，解决冲突后再合并回 `main`。
- 合并完成后在主生产 checkout 再次运行 `git status --short`，确认工作树干净；用 `git worktree list` 检查 `/Volumes/bocchi/myLectures-worktrees/` 下是否还有已完成的临时 worktree，完成后用 `git worktree remove <path>` 清理。
