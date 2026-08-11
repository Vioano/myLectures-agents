---
name: lecture-animation-pipeline
description: Build, review, finalize, and retrospect on myLectures scene animations with a compact compiled rule profile, retrieval from existing storyboards/timelines/source packages, artifact hashes, independent novice review, native-4K finishing, embedded-subtitle and Sumino sign-off QC, and durable outcome metrics. Use for planning, authoring, reviewing, repairing, post-approval finishing, or post-episode process evolution of Manim/Remotion lecture scenes in /Volumes/bocchi/myLectures when speed and strict evidence-bound gates both matter, including when the user says “可以收尾了” or “复盘一下”.
---

# Lecture Animation Pipeline

## Purpose

Run the canonical evidence-bound production path. Support either a main-producer mode or a parallel-batch mode, while always keeping each animation author separate from the independent reviewer. Move enforcement out of ever-growing prompts and into an active author-design gate, a compact scene profile, runtime QC, and review gates.

The pre-migration V0 workflow remains intact at
`../lecture-animation-pipeline-legacy/` as a legacy reference library. Use it
only for the detailed philosophy, production references, and compatibility
tools explicitly retrieved by this Skill; do not invoke it as the normal
production entrypoint. The canonical Skill compiles only the rules relevant to
the current scene, retrieves reusable visual grammar from live production
history, and records whether each rule actually prevents human rejection.
Internal filenames and schemas such as `pipeline_v2.py`, `review/v2/`, and
`*-v2` remain versioned protocol identifiers for historical compatibility;
users invoke this Skill without a version suffix.

## Non-Negotiable Boundaries

- Work in the current task branch/worktree. Do not modify the legacy backup
  during normal production; evolve this canonical Skill instead.
- Keep one implementation unit per independently reviewed scene. A scene package may contain several small modules, but never place multiple review scenes in one animation file.
- Treat the episode narration outline and storyboard as provisional macro contracts. For the active scene, first lock and listen to exact narration, then finish and independently pass the word-timed detailed visual-presentation plan before any animation implementation. Do not invent timing from text, prematurely lock future scenes, or author animation against estimated narration.
- Keynote slides, grayscale wireframes, and a small number of critical keyframes are optional visual-plan probes. They are review attachments only: they may expose composition or transition risk, but they never replace the complete scene plan, never authorize production, and must not grow into a full silent animatic.
- Reserve the bottom 16 percent for subtitles unless the episode contract explicitly defines a larger zone.
- Never pass review from prose alone. Bind the design chain, dynamic plan, source, telemetry, authoring QC, timeline, audio, subtitle, layout audit, QC frames, and review MP4 by hash.
- A reviewer must not be the author. The author must first seal a current
  five-layer self-review; only then may the independent reviewer inspect the
  MP4 as a novice and resolve the compiled contract.
- User approval remains the final gate before staging or committing animation work.
- Do not expose precedent hits before the author completes the first-principles design gate.
- Read `references/authoring-philosophy.md` before designing a scene; use its dynamic cognitive topology and executable M/D/A model.
- Never trade review breadth for speed. Layout, mathematical-object truth,
  timing/attention, novice causality, and visual finish are five simultaneous
  hard-gate layers. Adding a mathematical gate never removes composition or
  finish inspection.
- Evolve scene policy during production only through a hash-bound live-policy
  overlay. Human feedback invalidates the current profile and manifest
  immediately. Global Skill, CLI, schema, and test changes are legal only
  before `T0` or in the post-upload retrospective; a missing enforcement
  capability isolates the affected scene and uses the pinned last-known-good
  release without starting a live tooling project.
- Never let a production or review subagent skip a V2 CLI gate, replace a CLI output with hand-written prose, or continue from a failed/stale contract. The main agent owns assignment boundaries and verifies current hashes before accepting any subagent artifact.

## Consolidate Git State

Treat the exact user phrase `整理 Git 状态` as authority for one standard,
local, task-scoped consolidation pass. The scope is the current episode or
task and its worktrees; it expands to the whole repository only when the user
explicitly says so. The phrase means all of the following, in order:

1. Inventory the canonical checkout, current branch and commit, upstream,
   tracked/untracked/ignored changes, submodule state when applicable, and the
   exact task worktree list. Preserve unrelated dirty work instead of stashing,
   resetting, force-checking out, or cleaning it.
2. Resolve the accepted source/control branch and classify generated assets.
   Protected assets include the approved final MP4, native final segments,
   final mixed and voice-only WAVs, every approved scene WAV, reader/word
   subtitles and alignment, approved inputs/review packages, final manifest,
   QC/contact sheet, completion receipt, portability evidence, the canonical
   phase/outcome/review/repair ledgers, supervisor session, task capsules, and
   all human/accepted-agent feedback plus issue records needed for a truthful
   retrospective.
3. Promote the protected ignored/generated assets by exact hash into the
   canonical filesystem checkout at `/Volumes/bocchi/myLectures`. A temporary
   worktree checked out on `main` may be used to perform a safe merge, but it
   is not a substitute for the canonical directory and must not be reported as
   one. Promotion is copy-and-verify first; worktree removal supplies the later
   deletion half of a move.
4. Merge only already approved tracked source/control and retrospective
   evidence into local `main`, preferring fast-forward when possible. A merge
   conflict or ambiguous dirty overlap stops the merge and is reported rather
   than resolved by discarding bytes.
5. Run scoped AppleDouble cleanup, SHA-256 comparison, `ffprobe` on the final
   video, and `audit-portability --require-clean` from the canonical directory.
   A Git merge alone is never evidence that ignored audio or video survived.
6. After the canonical audit passes and a read-only unique-file inventory
   proves that every remaining task-worktree file is either hash-duplicated,
   obsolete intermediate output, or intentionally preserved elsewhere,
   remove the current task's producer and integration worktrees. This trigger
   authorizes that bounded worktree removal and deletion of the obsolete
   intermediate bytes inside those worktrees. It does not authorize deleting
   worktrees belonging to another episode or task.
7. Leave local branches in place unless branch deletion was separately
   requested. Report the resulting `main` commit, canonical checkout state,
   protected asset paths and hashes, removed worktree paths, retained branches,
   and any unresolved dirty state.

`整理 Git 状态` never authorizes push, upload, external Skill sync, deletion
of protected media/evidence, rewriting approved episode content, `git clean`,
`git reset --hard`, or deletion of unrelated work. If the user adds
`合并到主分支`, that restates the local merge step; it still does not grant a
push. See `references/preflight-portability-and-handoffs.md` for the promotion
and cleanup audit.

## Load Only The Active Phase

This file is the mandatory entrypoint. Read it completely, then load only the
references named for the current phase. Do not replay the whole production
history or read every reference as a ritual. A task capsule points to durable
artifacts by path and hash; it does not paste those artifacts into the prompt.

| Current work | Required references |
|---|---|
| New episode, initialization, or eight-hour scheduling | `references/eight-hour-production.md`, `references/preflight-portability-and-handoffs.md`, `references/orchestration-and-supervision.md`, and `references/autopilot-efficiency.md` |
| Production-mode choice, worktrees, stable roster, supervision, or restart | `references/orchestration-and-supervision.md` |
| Lecture, narration writing/review, TTS, alignment, screen text, or progressive locking | `references/narration-workflow.md`, `references/progressive-planning-and-audio.md`, and `references/preflight-portability-and-handoffs.md` |
| Efficiency contract, phase accounting, metric policy, or batch launch | `references/autopilot-efficiency.md` |
| Operational overrun, expired wrapper, metric recovery, or special continuation | `references/operational-recovery.md` in addition to the active-phase reference |
| Scene design, implementation, candidate freeze, self-review, independent review, or repair | `references/authoring-philosophy.md` and `references/scene-production-and-review.md` |
| User review, final assembly, upload-ready handoff, or process evolution | `references/finalization-evolution-retrospective.md` and `references/preflight-portability-and-handoffs.md` |
| User says `复盘一下` | `references/postmortem.md` and `references/evolution.md` |

`references/historical-episode-continuations.md` is cold storage. Read it only
when an existing receipt or command names one of its historical schemas. It is
never part of a new episode's startup context and never establishes a new
precedent.

## Executable Episode Startup

A new episode may not rely on a chat plan for its startup. The only permitted
pre-`T0` mutation is Git bootstrap: create one dedicated integration worktree
under `/Volumes/bocchi/myLectures-worktrees/codex-<episode>` from the current
canonical commit, without creating episode content. Run repo preflight and
`begin-delivery-clock` from that integration worktree. The canonical checkout
at `/Volumes/bocchi/myLectures` remains the final promotion destination; the
dedicated integration worktree is the live control root until consolidation.

Before leaving the delivery clock's `initialization` stage, create and seal one
`lecture-animation-episode-startup-v1` contract with
`seal-episode-startup --require-clean`. It must bind:

- the exact user startup brief and all known human-feedback regressions;
- production mode, runtime slot count, main reviewer, stable producer IDs,
  dedicated worktree paths, unique branches, and author/reviewer separation;
- the pipeline preflight, delivery clock, efficiency contract, metric policy,
  and one supervisor session;
- one episode evidence root and shared phase ledger used by every worktree;
- source/assets inventories, the fixed-ending source, and the rule that every
  scene review video is delivered immediately at 1080p or better.

Start from
`references/episode-startup-contract.example.json`; replace every placeholder
with a live path, branch, stable agent ID, and current receipt. Then seal it:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" seal-episode-startup \
  --repo-root . --episode "$EPISODE" \
  --contract "$EPISODE/review/v2/episode_startup.json" \
  --output "$EPISODE/review/v2/episode_startup_receipt.json" \
  --require-clean
```

For `parallel_batches`, the deterministic starting producer count is
`min(coherent_batch_count, runtime_slots - 1, 4)`: one runtime slot remains for
the main acceptance reviewer. A smaller roster requires a concrete capacity
reason in the startup contract; a larger roster requires the later compiled
capacity-expansion path. This means a four-slot host normally starts three
producers, while a sufficiently independent wide episode on a five-or-more-slot
host normally starts four. Do not make the user discover or correct the roster
after production begins.

The `lecture_approval` delivery-clock checkpoint still binds the approved
lecture draft through `--artifact`, and additionally requires the clean startup
receipt through `--startup-receipt`. Until both pass, subagents may inspect or
prepare bounded inventories, but they may not receive source-authoring
authority. Send each retained agent a hash-bound task capsule rather than a
full chat-history fork. See
`references/orchestration-and-supervision.md` for the exact topology and
`references/preflight-portability-and-handoffs.md` for the shared evidence root.

## Eight-Hour Delivery Contract

For a new episode, `begin-delivery-clock` is the first episode command. It
creates the empty episode directory, starts Initialization from no video
project, and ends only when the verified upload package is ready.
The target is eight hours of production critical-path time. The retrospective
has its own forty-five-minute budget after upload-ready delivery; it is not
taken out of the eight production hours. Explicit user wait and host-offline
time are reported separately and do not conceal agent work.

Run the schedule, ownership, model-routing, escalation, and no-live-CLI-repair
rules in `references/eight-hour-production.md`. The clock is an operational
constraint, never a quality waiver. If the schedule is missed, record the miss
and replan model, concurrency, scope presentation, or process. Never shorten
approved teaching content, lower render fidelity, skip listening, skip any of
the five review layers, or bypass user review to make the number look green.

## Production Authority

Choose and seal exactly one production mode in `episode_visual_spine.json`:

- `main_producer`: the main agent authors; a distinct agent independently
  reviews.
- `parallel_batches`: the main agent owns the lecture, global visual grammar,
  batch contracts, integration, acceptance review, and user communication.
  Initialization seals a stable production-agent limit suited to the current
  runtime, cost budget, scene independence, and reviewer capacity. On a
  four-slot host the normal shape is one main reviewer plus three producers;
  another run may deliberately use fewer or more, from one through eight.
  Start with the producer count sealed by the executable startup contract,
  normally three on a four-slot host and up to four for a wide episode with at
  least five slots and four coherent independent batches. A larger sealed
  ceiling is not spawn permission: reuse every opened compatible identity,
  including one whose task was cancelled, and add a new identity only after
  fresh availability and compiled reviewer-starvation/cost evidence prove
  reuse unavailable.
  Producers own bounded coherent scene groups in separate `agent/...`
  worktrees.

In parallel mode, keep identities and worktrees stable. Reuse completed agents
with `followup_task`; do not pay repeated context-loading costs by replacing
them after every scene. Assign one concrete artifact at a time, with exact
input paths, hashes, output paths, acceptance checks, and stopping conditions.
One author owns later repairs for its scene, but the main reviewer—not the
author—decides acceptance.

Before dispatch, give each producer its current task plus an ordered set of
compatible, already-safe `--preassigned-task` rows. The producer reads that
queue with `agent-plan` and, before becoming idle, must call
`complete-and-claim-next` with hash-bound completion evidence. The transition
either atomically activates the next preauthorized task or opens a durable
work request that the producer must immediately send to the main agent. It
never permits arbitrary self-selection, role/model changes, or bypass of the
scene's planning, audio, boundary, authoring, review, or user gates. An open
work request blocks supervisor `finish`.

Production rolls scene by scene. As soon as one scene has a current sealed
author self-review, the main agent reviews it while that owner advances safe
work on the next scene. Present each `user_review_pending` 1080p-or-better
video immediately. Do not wait for an entire group, and do not use low-
resolution human-review renders when rendering is not the bottleneck.

Production independence means separate bounded ownership, worktree/source,
scene-local locks, implementation, and review evidence. Content continuity
means adjacent learner state, mathematical identity carriers, narration/audio
handoff, and visual exit/entry state agree. The main-authored boundary handoff
contract unifies them: `adjacency_contracts` inside a batch and matching
`batch_exit_contract`/`batch_entry_contract` across batches freeze the shared
edge while `freedom_inside` leaves the interior independent. Therefore only an
unresolved defect that crosses a scene's exact dependency boundary may block
dependent implementation; other contract-ready scenes and non-authoring safe
work continue.

Report only important milestones by default: a new blocker requiring a user
decision, a scene ready for human review, a human verdict applied, final
assembly ready, or delivery complete. Subagents follow the same rule. Status
messages are not production artifacts and must not interrupt useful work.

## Progressive Episode Path

The whole episode remains coarse until its scenes are ready. Do not lock all
future narration, audio, or timeline merely to satisfy a denominator. For each
wave, independently lock exact narration, pronunciation, scene audio,
alignment, subtitles, detailed visual plan, and boundary handoff before that
scene enters implementation. A post-TTS `progressive_wave` receipt may release
only the exact covered scenes; final assembly still requires a full-episode
post-TTS receipt covering the final scene set.

Before the first TTS wave, validate episode-level prerequisite order,
terminology, pronunciation mapping, boundary narration, concept-bridge
ownership, and the fixed ending. Rerun the affected readiness gate after any
change to narration, timing, terminology, audio, screen text, or ending. ASR
is timing evidence, not narration truth. Every formal token used in TTS has an
explicit tested spoken form; ambiguous symbols are never left to provider
guesswork.

Narration uses the profile-bound state machine in
`references/narration-workflow.md`. An explicit audience profile, frozen
script candidate, author self-review, distinct independent review, and exact
user approval are required before TTS input can lock. TTS lock is not animation
authority. New episodes use workflow gate v3: TTS/ASR require
`tts_input_locked`, while animation authoring/render require
`animation_authorized`, sealed from current post-TTS readiness and the exact
scene-production inventory. The normal route is always script approval before
animation.

Changing narration after animation exists is a named exceptional repair, not
a shortcut and not the next episode's default. It requires exact user
authority, the current approved media lineage, affected scenes and cue
windows, and complete downstream invalidation. A wording change reopens the
full author -> independent reviewer -> user script gate; delivery-only repair
may retain exact script approval but still rebuilds audio, ASR, alignment,
subtitles, timeline, planning bindings, QC, review manifests, and final
assembly. Animation source stays frozen unless the user explicitly authorizes
source changes.

## Scene State Machine

Use the canonical CLI under `scripts/pipeline_v2.py`; do not hand-edit receipts
or replace failed gates with prose. A normal scene advances only through:

`profile compiled -> first-principles design -> exact script author/reviewer/user
approval -> TTS/listening/ASR/alignment lock -> narration animation release ->
final word-timed detailed plan -> independent plan review
-> authoring -> candidate freeze ->
five-layer author self-review -> distinct five-layer independent review ->
user_review_pending -> human approve/revise`.

The five simultaneous hard layers are:

1. layout and legibility;
2. mathematical-object truth;
3. timing and attention;
4. novice causal continuity;
5. visual finish and identity consistency.

A pass requires the real review MP4 and current hashes for source, plan,
profile, audio, alignment, subtitles, authoring QC, timeline, QC frames,
manifest, self-review, and reviewer evidence. A changed upstream byte
invalidates downstream receipts. Human `revise` reopens the same scene and
records a durable issue; human `approve` is required before staging or
committing that animation.

## Operational Metrics And Quality Gates

At Initialization, compile one user-authorized metric-policy profile. Token,
active-time, and telemetry controls are independent operational metrics with
`off`, `observe`, or `enforce` modes. Normal production defaults cumulative
token/cost control to `enforce`; a bounded model experiment may explicitly
select `observe` or `off` without erasing prior usage. Even in `off`, preserve known evidence;
unknown usage stays `null`, never fake zero. `quality_gates` and `user_review`
are always `enforce` and cannot be changed by that switchboard.

An operational overrun must not start an unscheduled CLI repair project inside
the episode. Record it, apply the sealed policy, finish the nearest safe
checkpoint, and follow the escalation/replan rule. If the pinned quality path
cannot run, stop that affected scene and reforecast while independent scenes
continue; global pipeline repair waits for a separate post-upload maintenance
or retrospective task. Never add an episode-specific override when a generic
policy or reconciliation transition is the missing abstraction.

## Finish, Upload-Ready Handoff, And Retrospective

After every scene is human-approved, follow
`references/finalization-evolution-retrospective.md`: native final renders,
assembly, subtitles, BGM, sprite/QC treatment, completion evidence, and the
portable upload package. Final media and evidence are protected assets. Do not
claim upload-ready from a Git merge, a low-resolution proxy, or unverified
ignored files.

`可以收尾了` authorizes the documented post-approval finishing path, not an
upload or destructive cleanup. `复盘一下` authorizes the bounded retrospective
and local Skill/CLI/test evolution described in `references/postmortem.md`; it
does not authorize push, upload, protected-media deletion, or worktree removal.

## Resources

- `references/eight-hour-production.md`: eight-hour critical path, ownership,
  model routing, WIP, escalation, and timeboxes.
- `references/orchestration-and-supervision.md`: production modes, worktrees,
  stable roster, rolling review, pause/resume, and concise reporting.
- `references/progressive-planning-and-audio.md`: progressive lecture,
  narration, TTS, alignment, pronunciation, and screen-text gates.
- `references/autopilot-efficiency.md`: efficiency contract, metric policy,
  phase accounting, context caps, and batch commands.
- `references/operational-recovery.md`: cold-path local TTS/ASR overrun and
  time-governed continuation rules; do not load during a normal startup.
- `references/historical-episode-continuations.md`: cold historical recovery
  contracts; load only when an exact existing schema requires them.
- `references/authoring-philosophy.md`: dynamic cognitive topology and M/D/A
  design model.
- `references/scene-production-and-review.md`: scene profile, detailed plan,
  implementation, candidate freeze, self-review, review, and repair.
- `references/preflight-portability-and-handoffs.md`: readiness, boundary,
  portability, promotion, and cleanup gates.
- `references/finalization-evolution-retrospective.md`: user review,
  finalization, policy evolution, and retrospective entrypoints.
- `references/postmortem.md`: bounded retrospective procedure.
- `references/evolution.md`: outcome-driven policy evolution.
- `references/rules.json`: structured rule registry.
- `references/failure_pattern_library.json`: rejected visual patterns.
- `scripts/pipeline_v2.py`: canonical CLI entrypoint.
- `scripts/render_scene.py`: native/proxy rendering helper.
- `scripts/render_native_review.py`: native-fidelity review render helper.
- `scripts/runtime_qc.py`: runtime telemetry helper.
