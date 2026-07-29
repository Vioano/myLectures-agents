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
- Treat the episode narration outline and storyboard as provisional macro contracts. Only the active scene's script, audio, reader SRT, word-level SRT/alignment, and timeline fragment become exact timing contracts; do not invent timing from text or prematurely lock future scenes.
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
- Evolve during production through a hash-bound live-policy overlay. Human feedback invalidates the current profile and manifest immediately; do not wait for the episode boundary. Change global Skill code only when the feedback exposes a missing enforcement capability.
- Never let a production or review subagent skip a V2 CLI gate, replace a CLI output with hand-written prose, or continue from a failed/stale contract. The main agent owns assignment boundaries and verifies current hashes before accepting any subagent artifact.

## Choose A Production Mode

Record one mode in `episode_visual_spine.json` before production:

- `main_producer`: the main agent owns episode writing, coarse design, detailed scene design, and animation implementation. Subagents are used only for independent review. Missing `production_mode` in a legacy spine is interpreted as this mode.
- `parallel_batches`: the main agent still owns every episode-global artifact and decision: lecture, provisional narration, coarse storyboard/timeline, episode visual spine, batch partition, stable identities, human-feedback compilation, user communication, and acceptance review after each production subagent's sealed self-review. Production subagents own only bounded detailed batch/scene design, scene-local audio, implementation, and self-review. The main agent may additionally delegate an independent review pass, but may not delegate its acceptance responsibility.

In `parallel_batches`, never delegate an unbounded request such as “make the episode.” Before a subagent starts, the main agent must freeze the batch entry and exit contracts, including the boundary visual state, narration handoff at the selected lock level, required identity carriers, transition owner, explicitly free interior, and one audio handoff contract. The audio handoff fixes outgoing/incoming clause ownership, tail silence, maximum boundary drift, and a no-clipped-phoneme/no-split-mathematical-clause cut policy. Adjacent batches must share identical exit/entry audio-visual handoffs. The main agent may lock the first and last animation states or exact boundary narration while leaving internal choreography open.

The main agent must also freeze one episode-level `narration_style_contract` derived from the approved lecture, narration outline, prior episode scripts, and current human feedback. Every batch plan reproduces it exactly and adds scene-local style notes. Production subagents may refine wording only inside that contract: they may adjust sentence rhythm around the animatic, but may not change the teaching voice, prerequisite order, mathematical claim ownership, terminology, or viewer-facing boundary. Internal adjacency contracts must lock outgoing and incoming visual states, narration lock/text, handoff meaning, identity carriers, transition ownership, and explicitly free interior. A batch plan missing any of these fields must fail the CLI gate.

Before the first scene enters TTS, run the episode-level gate in
`references/preflight-portability-and-handoffs.md`. It blocks duplicated
boundary narration, unsafe rolling pace, missing novice prerequisite bridges,
screen-text/summary-connector overload, unstable pronunciation mappings, and a
missing or duplicated fixed ending before those failures multiply into audio,
subtitle, render, and assembly work. Rerun it after any narration, timing,
terminology, or ending change.
The gate derives bridge requirements from both declared concept load and
learner-facing terminology: the first use of terms such as `模式`, or a
discrete-to-continuous/integral transition, cannot bypass the novice bridge by
being labeled `normal`. It scans the complete bound Python source root, not
only the top-level composer, for literal viewer-facing text. Pronunciation
matching treats ASCII, LaTeX, and Unicode Greek spellings as the same formal
token. Every semantic or listening review binds distinct immutable author and
reviewer identities plus a separately hashed human/independent-review authority
record that names the exact review source, review kind, and authorized verdict;
a self-authored or wrong-scope pass is invalid. Each visible-text inventory
entry must point to the exact file inside the bound scene source root where the
literal occurs.

Run simultaneous production subagents in separate Git worktrees under `/Volumes/bocchi/myLectures-worktrees/<agent-or-task>/`, each on its own `agent/...` branch. Never make several production subagents write concurrently in the canonical checkout, and never create ad-hoc sibling production directories such as `/Volumes/bocchi/myLectures-*`. The main checkout remains the integration and final-review source of truth. In parallel mode, `begin-production-batch` verifies that `--repo-root` is a direct child of the required worktree root and that the checked-out branch uses the `agent/...` prefix; a canonical-checkout or wrong-branch invocation fails before production starts.

Before starting or resuming any parallel batch, mechanically synchronize the
complete canonical `lecture-animation-pipeline/` Skill tree into every reused
author worktree and compare its `references/rules.json` hash with the canonical
checkout. A copied script without the matching rule registry is stale and does
not count. `begin-production-batch` seals the complete `skill_tree_hash`;
`batch-status` now fails if that hash differs from the worktree's current Skill
tree, so a Skill upgrade requires a fresh batch contract and a full downstream
profile/QC/manifest/self-review rebind. The acceptance reviewer must invoke the
canonical main-checkout CLI (it may point `--repo-root` at the author worktree);
running the author's stale local CLI cannot grant `user_review_pending`.

The reused worktree's supervisor session is also a cache, not an authority.
Parallel `begin-production-batch` requires both `--supervisor-session` and
`--canonical-supervisor-session`; their sealed `session_hash` values must
match. The main agent first mutates the canonical session with
`supervisor_watch.py`, then synchronizes that exact file into the author
worktree. A stale local grant cannot authorize a fresh batch even if its
session id and author id still look correct.

The CLI remains a synchronous command-line program; the orchestration layer supplies background concurrency. Its modular storage layer serializes shared JSON/JSONL state across processes, writes JSON by same-filesystem atomic replacement, deduplicates attempts while holding the log lock, and rejects a new review submission if its persistent session changed during verification. Do not bypass these transitions by editing session, attempt, repair, or phase files directly. Production agents keep authoring state in their own worktrees; only the main agent imports accepted batch artifacts and performs canonical acceptance review.

Human feedback always routes through the main agent. Record it in episode feedback/issues, compile it through `compile-profile` into `active_policy.json`, and bind the resulting policy hash before authoring or review. A subagent implements or checks the compiled contract; it does not independently decide what the human intended.

### Group Ownership, Scene-Level Rolling Review

In `parallel_batches`, assign ownership by a coherent group of three to five adjacent review scenes, but execute handoff and acceptance one scene at a time.

Default to one stable roster of at most three production subagents for the episode; the main agent supervises, integrates, and performs independent acceptance review. Spawn those producers once, retain their immutable agent IDs, and reuse them with `followup_task` plus `supervisor_watch.py assign-task`. A subagent that returned `done` is idle and reusable while it remains in the current task tree. Do not create a new identity merely because a scene, review round, repair, recovery, or inventory pass ended.

- One production subagent owns one bounded group in one worktree and task branch. That owner keeps responsibility for the group's detailed design, internal adjacency, implementation, author self-review, and later repairs. Do not reassign individual scenes merely because review is rolling.
- The delivery and acceptance unit is one independently reviewable scene, not the whole group. As soon as one scene reaches a sealed current author self-review, the production subagent hands that scene to the main agent and continues the next owned scene instead of waiting for the rest of the group.
- The main agent begins acceptance review as soon as a scene arrives. A scene that reaches `user_review_pending` is presented to the user immediately as its own review video; do not wait for the other scenes in the group or combine them into a batch review video.
- Human `revise` returns the scene to the same production owner. That repair takes priority when it blocks continuity or a user decision; otherwise the owner may finish a safe checkpoint in the currently active scene before switching.
- Human approval permits the approved scene checkpoint to be committed on its production worktree branch while the remainder of the group continues. Integration to the canonical target branch still waits for the configured group/episode integration gate.
- Production subagents do not cross-review other groups and do not hold acceptance authority. Their required review work is author self-review of their own scene. The main agent owns independent acceptance review, CLI governance, issue routing, user presentation, and the decision to release the producer to the next group.
- Keep all available production slots occupied when safe work exists. Rolling review changes scheduling, not ownership: `group ownership -> scene author self-review -> main-agent acceptance -> user review -> same-owner repair or continued production`.

The main agent also owns **review-result delivery timing**. Do not message a
nonblocking `revise` to an author while that author is actively constructing the
next scene. Queue it with `supervisor_watch.py queue-review-todo`, naming the
scene currently in production as `wait_for_scene_slug`. The result remains
durable but hidden from the author until that current scene reaches the
appropriate sealed checkpoint. A formal candidate uses its sealed
`author_self_review.json`. A low-cost animatic must instead use
`seal-animatic-checkpoint`, which hash-binds the current plan, profile, animatic,
zero-issue authoring QC, and contact sheet without pretending the animatic is a
frozen candidate. Never run `freeze`, candidate rendering, or formal
author-self-review solely to release a deferred animatic todo. After either
checkpoint, run `mark-safe-checkpoint`, deliver the released todo with
`followup_task`, and record the actual delivery with
`acknowledge-review-delivery`. `assign-task` and `finish` reject undelivered
review todos. If the queued `wait_for_scene_slug` was a scheduling typo, correct
it before release with `retarget-review-todo`; this command preserves the
deferred state and appends an auditable retarget history, so never edit the
supervisor session JSON directly. A continuity-blocking or
user-decision-blocking result is marked
`interrupt_required` and must be delivered immediately; never defer a defect
that would invalidate the active scene's mathematical identity, entry state,
audio boundary, or user decision.

The orchestration layer must record the stable group owner, the complete sealed task queue, and the current per-scene state separately. A batch is not “done” merely because one scene passed, and a scene is not held back merely because its sibling scenes remain in production. When all current agents become idle but queued batches remain, assign the next queued task to an existing compatible agent; do not end the supervision turn.

Later bounded cycles for the same production batch—such as an accepted-design
animatic pass, a user-requested visual repair, or a current-policy rebind—must
reuse the original batch `task_key`, because `begin-production-batch` binds the
supervisor grant to the batch ID. After the prior cycle is explicitly
`completed` or `cancelled`, call `assign-task` with that same key, the new
bounded scope, and a concrete `--new-task-reason`. The supervisor records a
`batch_reopen` history entry and increments `reopen_count`; it must not silently
treat a historically used task key as an idempotent no-op. Reopening an active
or blocked cycle, changing the roster role, or omitting the reason is a hard
failure. A migrated session may contain a stale task-queue row still marked
active after its only owner has become reusable and moved to later recorded
work. The CLI may reconcile that state only when the stale row names the same
owner and no active or blocked assignment still holds the task key; it records
the previous state and reason in `stale_state_reconciliation` before reopening.
It must never reconcile another owner's task or a genuinely active holder.

After the initial roster, every new `spawn_agent` requires a sealed replacement authorization. The only normal reasons are: the old identity cannot be restored after a direct `followup_task` attempt, the parent task tree changed, the required model changed, or the agent suffered an unrecoverable failure. The gate first rejects replacement when any compatible idle roster member exists. The first `collaboration.list_agents` result after an app restart is only a current visibility snapshot: it may omit completed child identities that remain directly addressable by their canonical task paths. Never infer permanent loss from that list alone. Replacement never erases the old identity: the supervisor records cumulative identities, reuse count, replacement count, replacement reason, and churn ratio. More than three simultaneous subagents or more than one replacement requires a concrete recorded override; never use an override merely to increase throughput.

### Resume the Stable Roster After Shutdown

Treat shutdown recovery as roster reuse, not roster creation:

1. Read the episode shutdown checkpoint and verify every worktree, branch,
   handoff path, and handoff hash before running production.
2. Address each preserved canonical child id directly with `followup_task`,
   even when the first post-restart `list_agents` output shows only the main
   agent. Ask only for a context-restoration acknowledgement; do not let the
   child write or render during this probe.
3. Run `collaboration.list_agents` again after the probes. If the old ids
   respond, seal them as `restored` with
   `supervisor_watch.py seal-availability-snapshot`, keep the original roster,
   and resume from the exact handoff commands.
4. Authorize replacement only when the sealed snapshot contains a failed
   direct probe for that exact id (`target_not_found`, `target_unavailable`, or
   `unrecoverable_error`). `authorize-replacement` rejects a snapshot that
   lacks this probe evidence or says `restored`.
5. Never spawn a provisional replacement “to see whether it works.” If one was
   opened after a mistaken loss diagnosis, interrupt it before production,
   restore the original owner through `restore-original-identity`, and cancel
   any unused authorization through `cancel-replacement-authorization`.

The shutdown checkpoint must therefore preserve canonical child ids, worktree
paths, branches, per-owner handoff hashes, supervisor session path, deferred
review todos, and the exact next safe command. Chat summaries are supporting
context, not the recovery authority.

### Supervise Continuously, Report Only Milestones

When the user asks the main agent to watch, supervise, or keep subagents working, default to `continuous_low_noise`. Continue polling or waiting until every sealed assignment reaches a terminal state; do not end supervision merely because one agent emitted a routine update. Persist all events, but send a user-facing update only when:

- a review video or other requested artifact becomes ready for human review;
- a user decision, approval, or new authority is required;
- a major blocker changes scope, timeline, or the promised delivery;
- the user explicitly asks for status.

Do not narrate routine repairs, second-level evidence, hashes, gate internals, or ordinary heartbeats. The user may explicitly request detailed progress; only then start a session with a recorded verbose override and reason. Use the durable supervisor contract instead of relying on chat memory:

For lossless low-token transport, build a hash-bound task capsule on disk and
send only status, artifact paths/hashes, gate results, blockers, and next
action. Required CLI logs stay on disk; they are never omitted or replaced by a
chat summary. See `references/preflight-portability-and-handoffs.md`.

```bash
python3 "$SKILL/scripts/supervisor_watch.py" begin \
  --supervisor-agent-id MAIN_AGENT_SESSION_ID \
  --assignment 'AGENT_ID|ROLE|TASK_KEY|BOUNDED_SCOPE|MODEL' \
  --planned-task 'NEXT_TASK_KEY|ROLE|NEXT_BOUNDED_SCOPE' \
  --output "$EPISODE/review/v2/supervisor_session.json"
python3 "$SKILL/scripts/supervisor_watch.py" set-assignment \
  --session "$EPISODE/review/v2/supervisor_session.json" \
  --agent-id AGENT_ID --state completed
python3 "$SKILL/scripts/supervisor_watch.py" assign-task \
  --session "$EPISODE/review/v2/supervisor_session.json" \
  --agent-id AGENT_ID --role animation_author \
  --task-key NEXT_BATCH --scope 'NEXT_BOUNDED_SCOPE'
python3 "$SKILL/scripts/supervisor_watch.py" queue-review-todo \
  --session "$EPISODE/review/v2/supervisor_session.json" \
  --agent-id AGENT_ID --reviewed-scene-slug PREVIOUS_SCENE \
  --wait-for-scene-slug ACTIVE_SCENE --priority nonblocking \
  --review-artifact path/to/revise_review.json \
  --summary 'Bounded repair to deliver after the active scene self-review'
# If the scheduling slug was wrong, correct it without releasing the todo:
python3 "$SKILL/scripts/supervisor_watch.py" retarget-review-todo \
  --session "$EPISODE/review/v2/supervisor_session.json" \
  --todo-id REVIEW_TODO_ID --wait-for-scene-slug CORRECT_ACTIVE_SCENE \
  --reason 'Correct the scheduling slug before any checkpoint release.'
# If the owner was doing a separate independent-review task rather than
# authoring, first mark that assignment idle after its final review transaction,
# then release the deferred todo against that exact review evidence:
python3 "$SKILL/scripts/supervisor_watch.py" release-review-todo-after-review-task \
  --session "$EPISODE/review/v2/supervisor_session.json" \
  --todo-id REVIEW_TODO_ID \
  --completion-evidence path/to/final_review_submission.json \
  --reason 'The separate review task is complete and the owner is now idle.'
# A non-authoring impact-plan task may also release a queued result after the
# owner has stopped and the exact bounded plan is bound:
python3 "$SKILL/scripts/supervisor_watch.py" release-review-todo-after-planning-task \
  --session "$EPISODE/review/v2/supervisor_session.json" \
  --todo-id REVIEW_TODO_ID \
  --completion-evidence path/to/bounded_author_repair_impact_plan.json \
  --reason 'The planning task stopped and no authoring is in flight.'
# For an active low-cost animatic, seal exact current bytes without freeze:
python3 "$SKILL/scripts/supervisor_watch.py" seal-animatic-checkpoint \
  --agent-id AGENT_ID --scene-slug ACTIVE_SCENE \
  --plan path/to/scene_plan.json --profile path/to/profile.json \
  --animatic path/to/animatic.mp4 \
  --authoring-qc path/to/authoring_qc.json \
  --contact-sheet path/to/contact_sheet.png \
  --output path/to/animatic_author_checkpoint.json
python3 "$SKILL/scripts/supervisor_watch.py" mark-safe-checkpoint \
  --session "$EPISODE/review/v2/supervisor_session.json" \
  --agent-id AGENT_ID --scene-slug ACTIVE_SCENE \
  --evidence path/to/animatic_author_checkpoint.json
# For a formal frozen candidate, use its sealed author_self_review.json instead.
# Send the released todo with followup_task, then record that delivery:
python3 "$SKILL/scripts/supervisor_watch.py" acknowledge-review-delivery \
  --session "$EPISODE/review/v2/supervisor_session.json" \
  --todo-id REVIEW_TODO_ID --delivery-method followup_task \
  --delivery-note 'Sent the sealed repair contract after the active scene checkpoint.'
python3 "$SKILL/scripts/supervisor_watch.py" record \
  --session "$EPISODE/review/v2/supervisor_session.json" \
  --event-type routine_progress --agent-id AGENT_ID --summary 'Internal progress note'
python3 "$SKILL/scripts/supervisor_watch.py" status \
  --session "$EPISODE/review/v2/supervisor_session.json" --require-clean
```

Obey the returned disposition: `persist_only` stays out of commentary; `notify_user` is a milestone update. Before yielding a final response for a supervision task, run `status`. If `should_continue_monitoring` is true, keep waiting or assign pending work to an idle roster member; if `user_update_required` is true, report only those pending milestone events and acknowledge them after reporting. `--require-clean` rejects abnormal identity churn, pending replacement authorization, or reuse bypass. `finish` rejects active or blocked assignments, pending or blocked planned tasks, and unacknowledged milestone events. See `references/contracts.md` for the replacement evidence schema, event taxonomy, and state contract.

## Plan Progressively, Then Lock Progressively

Do not design the whole episode at equal detail in one pass, and do not jump from a finished `timeline.json` directly into isolated scene code. Use this required macro-to-micro planning chain:

1. **Lecture truth.** Finish the lecture notes and mathematical argument first.
2. **Provisional episode language.** Write only a coarse narration outline and coarse `storyboard.md`. Establish the teaching order, scene jobs, cross-scene identities, and approximate boundaries, but do not synthesize or align the whole episode.
3. **Whole-episode visual spine and batch plan.** The main agent seals `episode_visual_spine.json`, then plans the next three to five scenes in `batch_visual_plan.json`. In parallel mode it also locks the batch entry/exit and adjacent-scene handoffs before delegation. Both remain macro plans rather than beat-level choreography.
4. **Just-in-time scene co-design.** For the active scene, evolve the detailed visual plan and scene-local narration together. Build a low-cost mathematical animatic before locking wording. If a better visual explanation needs another clause, pause, or intermediate state, revise the local script now rather than forcing the animation under obsolete audio.
5. **Scene-local audio lock.** Only after the animatic explains the causal chain, seal `design_readiness.json`, lock that scene's script, synthesize its audio, generate reader SRT plus exact word-level SRT/alignment, and write its local timeline fragment. Select visual anchors from word timestamps, not sentence estimates. `phase-start --phase tts` and candidate/repair render phases reject work without that receipt; smoke and animatic renders remain cheap and unrestricted.
6. **Final scene production and review.** Compile the execution registry, author the scene, run deterministic QC, then enforce `author -> self-review -> independent review`. Every independent `revise` returns to repair and a new self-review.
7. **Final assembly.** After all scenes pass, concatenate scene audio/video and offset-merge the local reader SRT, word alignment, and timeline fragments into final episode artifacts. Assembly must not silently retime an approved scene.

The design-readiness gate treats 45-75 seconds as the normal scene target, warns above 75 seconds, and blocks scenes above 90 seconds. A longer scene may proceed only with a structured `scene_split_exception` that names at least two internal sections, their stage-state ownership, a real clearance checkpoint, and why splitting would damage novice continuity. Do not use the exception to protect a late monolithic design.

Use progressive locking:

- the episode layer locks teaching order, approximate scene boundaries, cross-scene object identity, and stable visual conventions, not exact audio;
- the batch layer locks continuity, transition ownership, reuse/variation, and relative complexity across neighboring scenes;
- the scene layer locks exact wording, audio, word timing, stage states, mathematical invariants, and attention transfers only after its animatic works;
- micro choreography may change after the animatic, but any semantic, timing, or planning change must update the owning artifact and invalidate downstream hashes.

Artifact responsibilities are distinct. `storyboard.md` stays human-readable and coarse at episode scale. `progressive_production.json` records which scenes are provisional, designing, audio-aligned, approved, or assembled. Each audio-aligned scene freezes a `scene_production.json` containing its script, audio, reader SRT, word-level SRT/alignment, exact ASR transcript, timeline fragment, and sealed narration QC. `episode_visual_spine.json`, `batch_visual_plan.json`, and `scene_plan.json` remain the visual planning chain. A review candidate in progressive mode must include the exact scene production contract and compiled execution registry.

Use `prepare-design-readiness` after the low-cost animatic and `seal-design-readiness` after filling every stage, transition, muted-playback, and formula-memory check. Pass the sealed receipt to `phase-start --design-readiness ...` before TTS or any non-animatic render.
The same phase start must also receive the fresh episode-level
`--episode-readiness` receipt; its bound narration/audio/alignment,
pronunciation input, and ear evidence are rehashed before expensive work.
The pronunciation hard gate listens against the exact bound scene WAV with
ordered per-occurrence windows; an arbitrary or extracted file cannot stand in
for final scene audio. A human or independent reviewer must provide a
hash-bound pronunciation record for those exact windows. Novice bridges
require a hash-bound semantic review in addition to exact narration quotes.
Visible-text budgets are extracted from the exact scene source and must equal
the declared inventory rather than trusting self-reported counts.
Use a `pre_tts` episode-readiness receipt for initial synthesis: it seals the
spoken-form input without demanding future audio. After synthesis and listening,
rerun as `post_tts`; candidate/repair renders and finalization reject the
pre-TTS stage.

Before a scene may enter `audio_aligned`, create the exact ASR transcript and a narration QC draft, then seal both the audio and language checks through the CLI. The QC gate compares the approved script with the ASR transcript after punctuation/space normalization, verifies reader and word-level subtitle bounds, checks word alignment and timeline duration against decoded audio, enforces a maximum 0.25-second drift, requires complete playback, and records an audio-only novice teach-back and concrete confusion test. Merely having an audio file is not evidence that the scene is teachable or aligned.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" seal-narration-qc \
  --repo-root . --episode-spine "$EPISODE/episode_visual_spine.json" \
  --scene-slug <scene_slug> --script path/to/script.md --audio path/to/audio.wav \
  --reader-srt path/to/reader.srt --word-srt path/to/word.srt \
  --word-alignment path/to/word_alignment.json \
  --timeline-fragment path/to/timeline_fragment.json \
  --asr-transcript path/to/asr_transcript.txt \
  --review-draft path/to/narration_qc_draft.json \
  --output path/to/narration_qc.json
```

After writing either upstream JSON artifact, seal it deterministically instead of calculating hashes by hand:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" seal-planning-artifact --input path/to/episode_visual_spine.json
python3 "$SKILL/scripts/pipeline_v2.py" seal-planning-artifact --input path/to/batch_visual_plan.json
```

Initialize the progressive tracker from the coarse timeline, then reseal it whenever one scene advances. Whole-episode narration must remain `outline_draft`; whole-episode storyboard status remains `coarse` until final assembly.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" init-progressive-production \
  --repo-root . --episode "$EPISODE" \
  --lecture-notes path/to/lecture.md --narration-outline path/to/script-outline.md \
  --storyboard "$EPISODE/storyboard.md"
python3 "$SKILL/scripts/pipeline_v2.py" seal-progressive-production \
  --repo-root . --input "$EPISODE/progressive_production.json"
```

## Start An Autopilot Batch

Before planning begins, the main agent must create one episode-level efficiency contract in the canonical production checkout. It fixes the eight-hour active-time budget, cumulative token ceilings, quality targets, and one canonical phase ledger shared by every worktree. Rerunning the command is idempotent while the contract is active and cannot reset consumed time or tokens.

```bash
EFFICIENCY="$EPISODE/review/evolution/episode_efficiency_contract.json"
python3 "$SKILL/scripts/pipeline_v2.py" begin-episode-efficiency \
  --repo-root . --episode "$EPISODE" \
  --episode-target-hours 8 \
  --retrospective-reserve-minutes 45 \
  --output "$EFFICIENCY"
```

Copy the unchanged hash-bound contract into each production worktree. Every `phase-start` requires `--episode "$EPISODE" --efficiency-contract "$EFFICIENCY"` plus explicit raw, uncached-input, output, and reasoning token allocations for that bounded task capsule. Before work starts, the CLI atomically reserves those four amounts in the canonical episode reservation ledger. A concurrent start is rejected when completed use plus all active reservations plus the new request would exceed any episode ceiling. Every `phase-end` writes the actual event to the requested local ledger and, exactly once, to the canonical shared episode ledger, then releases the reservation; exceeding the task allocation is itself a hard failure. This makes concurrent work visible and budget-safe without waiting for branch integration.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" phase-start \
  --repo-root . --episode "$EPISODE" \
  --efficiency-contract "$EFFICIENCY" \
  --run-id <run-id> --scene-slug <scene-or-episode> \
  --phase <planning|design|authoring|render|review|repair|tts|asr|finalization|retrospective|human_wait> \
  --actor-model <model> \
  --active-seconds-allocation <max-active-wall-seconds> \
  --raw-token-allocation <max-raw> \
  --uncached-input-token-allocation <max-uncached> \
  --output-token-allocation <max-output> \
  --reasoning-token-allocation <max-reasoning> \
  --state <active-phase.json>
```

Treat each allocation as the maximum for one concrete deliverable, not as permission to consume the whole episode remainder. `human_wait` reserves zero active seconds and zero tokens. Active-time reservations use projected intervals, so genuinely parallel tasks overlap instead of being naively added. The supervisor may launch a short high-concurrency burst only when the union of projected active intervals and the sum of token reservations fit the sealed episode contract.

Start each three-to-five-scene production batch only after the episode spine and batch plan pass their contracts. The batch command binds both planning artifacts and the already active episode efficiency contract, then starts its measured five-hour batch budget. Complete-episode active time begins with planning and ends after standard finalization and retrospective. Explicit `human_wait` and machine-offline pauses are excluded from active critical-path time but must be reported separately; they cannot hide agent work. Reserve forty-five minutes of the eight hours for the retrospective, leaving seven hours fifteen minutes for planning through finalization. These are efficiency gates, never permission to skip quality gates.

The command is mandatory for every production subagent. A chat assignment, Markdown checklist, or valid-looking JSON does not authorize implementation. The subagent must receive the emitted production-batch contract and must stop if `begin-production-batch`, `compile-profile`, any design validator, `validate-scene-plan`, `validate-authoring-qc`, manifest verification, or review verification fails. The main agent must reject work produced outside this chain.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" begin-production-batch \
  --repo-root . --episode "$EPISODE" \
  --efficiency-contract "$EFFICIENCY" \
  --batch-id <batch-id> \
  --scenes <scene-a,scene-b,scene-c> \
  --episode-spine "$EPISODE/episode_visual_spine.json" \
  --batch-plan "$EPISODE/review/v2/<batch-id>/batch_visual_plan.json" \
  --production "$EPISODE/progressive_production.json" \
  --author-id <production-subagent-id> \
  --supervisor-session "$EPISODE/review/v2/supervisor_session.json" \
  --target-hours 5 \
  --output "$EPISODE/review/v2/<batch-id>.json"
```

Wrap every planning, design, authoring, render, review, repair, TTS, ASR, finalization, retrospective, and human-wait phase with the existing phase timer. Run `batch-status` during production. It reports measured active time, full/diagnostic review mix, artifact growth, missing phase telemetry, stale human-outcome logs, and cumulative episode token use. An exceeded active-work budget forces a root-cause process review; it never grants a visual pardon.

The default complete-episode cumulative token contract is:

- raw input plus output: at most `50,000,000`;
- uncached input: at most `2,000,000`;
- output: at most `300,000`;
- reasoning: at most `100,000`;
- warning threshold: `75%` of any limit.

This contract caps total episode consumption, not instantaneous rate. A short, useful high-concurrency burst is allowed only when completed use plus every active reservation remains within budget. At the warning threshold, `phase-start` and `phase-end` emit `TOKEN_BUDGET_NEAR_LIMIT` or `ACTIVE_BUDGET_NEAR_LIMIT`; finish the active checkpoint, stop optional exploration and repeated full-corpus rereads, compact the task capsules, and let the supervisor replan the remaining work. After a hard limit is exceeded, `phase-start` blocks new planning, design, authoring, initial TTS, and non-repair renders. Repair, independent review, finalization, and retrospective remain available so the episode can be made safe and audited; quality gates are never waived.

The state machine also protects future work before the total is exhausted:

- the first `195` minutes and `32%` of every token ceiling are unavailable to early planning/design/authoring/initial-production work, preserving review, repair, finalization, and retrospective capacity;
- the final `45` minutes and `7%` of every token ceiling remain unavailable until the retrospective phase;
- repair rerenders and classified post-readiness TTS retries may use the closure reserve, but cannot consume the retrospective reserve;
- a task that exceeds its own active-time or token allocation fails at `phase-end`, even when the episode total remains below the outer ceiling.
- an active reservation that has already outlived its allocation blocks new agent work until it is ended or explicitly reconciled; an overrun cannot disappear merely because its timer has not been closed.

The outer reserves are not enough by themselves. Every non-wait task is also charged to one sealed phase envelope before it starts:

| Budget bucket | Active-time envelope | Token fraction |
|---|---:|---:|
| planning | 45 min | 5% |
| design | 45 min | 10% |
| authoring | 75 min | 25% |
| render | 75 min | 20% |
| TTS | 25 min | 5% |
| ASR | 20 min | 3% |
| review | 60 min | 12% |
| repair | 30 min | 8% |
| finalization | 60 min | 5% |
| retrospective | 45 min | 7% |

Completed use plus every live reservation must fit both the episode/stage limit and the applicable phase envelope. The check and reservation write happen under the same multi-file lock, so concurrent workers cannot race through the same allowance. Candidate renders use the render envelope; repair rerenders, technical retries, pronunciation retries, post-readiness script changes, and reuse verification are charged to the repair envelope. A phase cannot monopolize another phase's allowance merely because the episode total remains under eight hours or the outer token ceilings. `phase-end` emits `PHASE_BUDGET_ENVELOPE_EXCEEDED` and returns nonzero if actual measured work nevertheless crosses the bound.

One task capsule may not reserve an entire phase. The default per-task hard limits are `1,500,000` raw input-plus-output tokens, `100,000` uncached input tokens, `20,000` output tokens, and `8,000` reasoning tokens. `phase-start` rejects a larger allocation; `phase-end` already fails when observed use exceeds that allocation. Short high-concurrency bursts therefore remain possible, but only as several independently bounded deliverables whose combined reservations still fit the phase and episode envelopes.

The same start gate rejects a declared capsule larger than `32 KiB` of assignment prompt, `256 KiB` of intentionally loaded text/structured artifacts, or `16` files. These three context-size fields are auditable claims, not inferred measurements; an agent must count them honestly and bind the durable artifacts on disk. The token delta remains the authoritative hard-cost observation. If a task needs more context, write an intermediate artifact, end the phase at a stable checkpoint, and start a fresh bounded task that references the artifact by path/hash. Do not evade the cap by replaying the same full context across several nominal tasks; cumulative and phase token limits still apply.

Use the following default critical-path allocation as a planning constraint, not as permission to lower quality:

- planning and approved narration spine: 45 minutes;
- batch visual design and animatics: 45 minutes;
- parallel production: 3 hours 15 minutes;
- independent review and repairs: 1 hour 30 minutes;
- subtitles, BGM, assembly, and finalization: 1 hour;
- retrospective: 45 minutes.

Previously accepted human issues with `must_check_in_future: true` are zero-tolerance regressions. If the same `pattern_key` later reappears as a current `human_review` issue, `batch-status` emits `KNOWN_HUMAN_REGRESSION_RECURRED`, and `batch-status --require-clean` fails. The episode may still be repaired and finalized, but it cannot be reported as process-compliant.

Do not claim that the eight-hour workflow has succeeded merely because the tooling was installed. The next matched episode must have complete phase/token telemetry, finish within all time and token limits, produce zero known-regression recurrences, produce zero automatic-pass-to-human-revise outcomes, and keep scene-local human-issue coverage below 25 percent without skipping any quality or user gate. A same-episode before/after snapshot proves tooling behavior only.

Use `batch-status --require-clean` before batch handoff so shared work recorded under inconsistent `phase_instance_id` values, missing token/phase evidence, stale human outcomes, semantic escapes, and artifact explosion become a nonzero gate rather than advisory prose. Use `--historical` only for post-integration analysis after the original worktree or planning hashes advanced; historical mode records those differences without pretending the batch is still live.

`phase-start` automatically snapshots cumulative Codex token usage from the current rollout when `CODEX_THREAD_ID` is available. For other workers, pass `--usage-file` pointing to cumulative OpenAI/Anthropic/Codex-compatible JSON or JSONL. Its active-time allocation and four token allocations reserve the maximum allowed for that task before the worker begins. `phase-end` records the deltas in both the local and canonical episode ledgers and releases the reservation; `PHASE_ACTIVE_TIME_ALLOCATION_EXCEEDED` or `PHASE_TOKEN_ALLOCATION_EXCEEDED` is nonzero even if the episode total has not yet crossed its ceiling. Every non-wait phase, including render, TTS, and ASR, participates in token-observability coverage. Missing evidence is never silently interpreted as observed zero.

## Start A Scene

Set the skill and episode paths once:

```bash
SKILL=.agents/skills/lecture-animation-pipeline
EPISODE=videos/NNNN-slug
```

### 1. Compile A Small Scene Profile

```bash
python3 "$SKILL/scripts/pipeline_v2.py" compile-profile \
  --repo-root . \
  --episode "$EPISODE" \
  --scene-slug g002c_riemann_sum_limit \
    --output "$EPISODE/review/v2/g002c_riemann_sum_limit/scene_profile.json"
```

`compile-profile` also writes `active_policy.json` beside the profile. It includes every explicitly applicable human or accepted-agent regression without relying on prompt memory. Exact scene/group matches, explicit `applies_to_scenes` / `applies_to_tags`, and global issues enter the hash-bound policy. Loose keyword similarity remains retrieval-only and cannot invalidate unrelated scenes. `freeze-review` adds the policy automatically, and `verify-manifest` recomputes it from current issue files.

The compiled profile must have a positive authoritative duration. Use `timeline.scene_groups` when its timing is complete; otherwise `compile-profile` automatically binds `review/v2/<scene_slug>/timeline_fragment.json` and its hash. In the local fragment, rendered scene time is authoritative: prefer `scene_duration_seconds`, then `render_end`, before generic or narration-only duration fields. A null duration cannot enter the autopilot contract, because it would collapse stage validation, self-review probes, and blind-review checkpoints toward the opening frames.

Read that profile, not every old rule document. It contains the scene context, applicable rules, and relevant regressions, but deliberately withholds precedent hits.

- the current scene's narration, mathematical objects, driver, and inferred risk tags;
- the applicable subset of `references/rules.json`;
- only scene-relevant human/accepted-agent regressions;
- required author and reviewer evidence.

Add `--tags` only when inference misses a real property. Do not add tags to force a preferred verdict.

### 2. Force First-Principles Author Deliberation

Create a scene-specific challenge:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" begin-design \
  --profile path/to/scene_profile.json \
  --output path/to/design_challenge.json
```

Before reading old animation guidance or precedents, write `design_deliberation.json`. Model the novice, define the hidden relation and invariants, separate mathematical state `M`, display mapping `D`, and attention `A`, and propose materially different low-cost stage hypotheses. Do not render alternatives.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" validate-design-deliberation \
  --profile path/to/scene_profile.json \
  --challenge path/to/design_challenge.json \
  --deliberation path/to/design_deliberation.json \
  --output path/to/design_gate.json
```

The gate rejects generic reasoning, scene-independent templates, nearly identical candidates, missing novice-failure predictions, and deliberation that claims history was already consulted.

Autopilot contract v7 makes this a **representation-space audit**, not a prose
brainstorm. Every scene compares at least two materially different
representation classes; `stage_dense`, `human_rejected`, and
`repeat_rejected` scenes compare at least three. One candidate must be the
smallest honest baseline. Each candidate names its real technical mechanism
(for example fixed 2D, local zoom, camera travel, 2D-to-3D reveal, projection
change, slice, or synchronized multi-view), the relation it newly reveals,
continuity carriers, complexity tier, why a simpler representation fails, its
overdesign risk, and a removal test. Distinct wording with the same visual
topology does not count as a distinct candidate. Each hypothesis therefore
also carries a structured `representation_signature`: scene-grounded primary
math objects, an enumerated stage topology, display-mapping modes, attention
handoff sequence, causal-chain objects, and identity carriers. Every
`contrast_against` record must name the actual changed axes and the visible
learner consequence. The CLI compares signatures directly, so relabeling the
same two-panel shot as “3D”, changing colors, or paraphrasing its prose cannot
manufacture another candidate.

The selected plan then carries a `representation_budget`. Every added visual
technique has exactly one primary value channel:

- `cognitive`: exposes a relation, comparison, scale, or local detail;
- `continuity`: preserves identity and orientation through a view change;
- `aesthetic_finish`: improves hierarchy, material coherence, rhythm, or
  professional finish without claiming new mathematics.

An aesthetic finish is legitimate, but it must remain non-primary,
semantically neutral, and outside protected mathematical regions. An element
with none of these value channels is unowned decoration and fails. The plan
must also record at least one deliberately rejected excess idea, so “use every
available technique” cannot pass as visual ambition. The goal is the minimum
complexity that is simultaneously mathematically honest, novice-readable, and
visually finished—not the minimum author effort and not the maximum spectacle.
The budget is cross-checked against the actual stage states: declared peak
view count must match, every supporting/context view needs an owned unique
learning job, and its view, mathematical object, display mapping, and driver
IDs must resolve to the plan. Camera, perspective, orbit, or 3D techniques must
also name the dimension/occlusion lost in the 2D baseline, why that baseline
fails, and the minimum motion that reveals the relation. “More dynamic” is not
evidence.

The budget must additionally include `visual_finish_contract`. A low-cost
animatic may defer render resolution, dense sampling, shading detail,
render-only texture, and final easing. It may not defer composition, object
scale, primary/support/context hierarchy, contrast roles, typography roles,
line-weight roles, negative-space ownership, or transition topology. Those are
the design. Every stage state names the visual job of its negative space and
the generic Manim defaults it intentionally rejects. Runtime telemetry exports
one `visual_finish_check` per stage state, using a representative decoded frame
at full size and thumbnail size. Missing focal hierarchy, unreadable thumbnail
structure, unowned empty space, flat line/brightness hierarchy, debug-sketch
formula handoffs, or a claim that “formal rendering will make it beautiful”
blocks design readiness.

### 3. Retrieve Only Relevant Visual Grammar

After the design gate passes, retrieve reviewed production precedents and
narrow sections from the legacy backup:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" retrieve-design \
  --repo-root . \
  --profile path/to/scene_profile.json \
  --deliberation path/to/design_deliberation.json \
  --design-gate path/to/design_gate.json \
  --output path/to/precedent_packet.json
```

Search is driven by the learner operation, hidden relation, mathematical driver, identity invariant, and attention transfer, not by an effect name. Reuse, adapt, or reject each hit. A rejected historical scene is a counterexample, not a template. The repository remains authoritative; optional indexes are disposable caches.

Reviewed scenes may expose compact `visual_grammar.json` sidecars beside their source package. Each entry indexes a reusable representational solution by learner operation and hidden relation, then points back to exact code anchors and review evidence. `index-history` compiles these entries as `visual_grammar` records; `retrieve-design` may return them only after the first-principles gate. Add an entry for a genuinely reusable success instead of copying a growing catalogue into this file or loading every old example into context.

### 4. Write And Validate The Dynamic Scene Plan

Before final animation code, draft `scene_plan.json` using `references/contracts.md`. Bind its `planning_chain` to the episode spine and active batch plan. Define cognitive regions as reusable roles, then define time-varying `stage_states` and `stage_transitions`. The low-cost animatic may use provisional timings. After the scene-local script and word alignment are locked, replace provisional anchors with exact word anchors and run the final plan validation below.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" validate-scene-plan \
  --profile path/to/scene_profile.json \
  --plan path/to/scene_plan.json \
  --challenge path/to/design_challenge.json \
  --deliberation path/to/design_deliberation.json \
  --design-gate path/to/design_gate.json \
  --precedent-packet path/to/precedent_packet.json \
  --episode-spine "$EPISODE/episode_visual_spine.json" \
  --batch-plan "$EPISODE/review/v2/<batch-id>/batch_visual_plan.json"
```

Failing this gate means the scene is not ready for final rendering. Fix the orchestration file first; do not patch layout symptoms directly in Manim while leaving a false plan behind.

Extract the exact active-scene media contract and compile one execution registry. Scene code and telemetry must consume registry IDs instead of independently retyping object, driver, stage, formula, and word-anchor IDs.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" extract-scene-production \
  --repo-root . --production "$EPISODE/progressive_production.json" \
  --scene-slug <scene_slug> --output path/to/scene_production.json
python3 "$SKILL/scripts/pipeline_v2.py" compile-scene-registry \
  --repo-root . --profile path/to/scene_profile.json --plan path/to/scene_plan.json \
  --scene-production path/to/scene_production.json --output path/to/scene_registry.json
```

## Author Efficiently

Follow the six authoring passes in `references/authoring-philosophy.md`: learning contract, grayscale wireframe, mathematical animatic, regional refinement, micro choreography, deterministic preflight.

Export runtime telemetry from the scene registry or frame analysis. Do not hand-author a passing audit. Then run:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" validate-authoring-qc \
  --profile path/to/scene_profile.json \
  --plan path/to/scene_plan.json \
  --telemetry path/to/runtime_telemetry.json \
  --output path/to/authoring_qc.json
```

This gate owns low-level layout, subtitle safety, typography, overlap,
container overflow, cue timing, transition duration, stale objects, focal
overload, QC coverage, runtime M/D/A consistency, and representative visual
finish. Layout remains mandatory: the separate `layout_audit` must come from
runtime/frame evidence, cover at least three checkpoints, and contain zero
unresolved issues. The fifth `visual_finish` layer must inspect the opening,
peak explanation, major handoffs, and ending at full and thumbnail size. The
author should spend attention on mathematical expression, visual guidance,
semantic detail, and aesthetic rhythm.

Every new autopilot plan also declares typed `math_objects`, explicit `display_mappings`, `visual_bindings`, and `math_object_invariants`. Mathematical parameters and display-only parameters are separate namespaces. Every primary visual object names its mathematical source, real driver IDs, display mapping, and runtime owner. Telemetry exports sampled `math_object_bindings`, `display_mapping_checks`, and `math_invariant_checks`; a correct label attached to a wrongly placed point, a group center standing in for a mathematical coordinate, an analytic result substituted for a visible sum, or a formula appearing without its operation fails this layer even when layout passes.

A display optimization is allowed only through a declared mapping such as `local_zoom`, `nonlinear_magnifier`, `pedagogical_parameter`, or `equivalent_deformation`. The mapping must state preserved invariants, distorted quantities, forbidden learner inferences, and a runtime validation method. It may make an infinitesimal contour indentation visible, but it may not silently replace the mathematical epsilon with a screen radius. `novel` mappings need an additional counterexample probe; there is no free-form exemption.

In v6, `local_zoom` also carries a numeric zoom contract. The source interval
must remain genuinely local (at most 15 percent of its context span), the
global context and focused view must both be present, one identity anchor must
prove that the focused object is the same source object, and screen
magnification must exceed one. When the shot teaches local linearization or a
limit, runtime evidence must sample at least three decreasing source spans and
show non-increasing approximation error with a strict overall improvement.
Thus a huge `Delta x` labeled “small” cannot pass; the honest small increment
must be made readable by the display mapping.

The zoom contract additionally binds the source coordinate window, its
mathematical drivers and state hash, an explicit affine/nonlinear transform,
orientation and scale policies, and center plus boundary correspondence
samples. Runtime QC recomputes the mapped coordinates from that transform and
derives curve-to-tangent error from sampled curve and tangent values; it does
not accept `passed: true`, a self-reported magnification, or a typed error
sequence as proof. Context and inset using different math states, reversed
orientation, detached boundaries, or a screen radius substituted for the
mathematical increment are blockers.

Runtime telemetry also exports one `representation_check` per owned technique.
It binds the declared value channel to real QC checkpoints, records the
observed gain and removal-test result, and verifies identity carriers. An
`aesthetic_finish` check additionally proves that the finish never became the
primary focal object, made no mathematical claim, and did not overlap a
protected region. Correct mathematics without this visual-value evidence is
underdesigned; spectacle without it is overdesigned. Both fail.

For `repeat_rejected` scenes, the gate also requires an executable novice ledger rather than a role-play instruction. Every beat must introduce at most one concept by default, expose distinct cause and result objects, name what the learner can point to, allow at least 1.2 seconds after the decisive action to settle, and export a runtime `semantic_event`. Register separately positioned labels and formula fragments with `track_layout_atom`; a parent group bbox cannot pardon colliding children or an invisible focal result. QC contact sheets must include every cause-result checkpoint and every stage handoff, not only aesthetically convenient frames.

The novice ledger is backend evidence, never screen copy. It must not be rendered as explanatory prose. When repairing a user-rejected scene, freeze the accepted predecessor's exact `Text`/`Tex`/`MathTex`/numeric-label inventory before changing motion. `verify-text-inventory` blocks review if constructor counts, literal payloads, static character count, or dynamic payload count changes. Runtime snapshots also discover text descendants automatically, so a child label omitted from manual registration can still trigger a collision blocker.

The screen is not a second narration channel. In v7 every literal screen-text
payload must be listed in `screen_text_contract.semantic_items` with its
constructor, count, permitted role, and one unique visual job. Formulas,
object labels, axis/tick labels, parameter values, compact titles, comparison
labels, and brief transient questions are permitted when the picture needs
them. Explanatory sentences that restate the voice, author/process commentary,
and text whose only job is to announce what the animation should have shown
are blockers. `freeze-review` cross-checks this semantic inventory against the
actual source-text baseline; a relabeled paragraph cannot pass.

Treat transformation words as executable cues, not captions. The CLI detects
strong narrated actions such as rotation, uniform scaling, reflection, shear,
stretch, bending, translation, and local zoom. Every occurrence must appear in
`narrated_action_contracts`, bind an exact word-alignment anchor, name the
mathematical object, and declare enacted motion, a counterexample, or a visible
inhibition contrast. Runtime evidence must measure the corresponding geometry:
for example, the word “旋转” changes the object's angle at that word, while
“等比例伸缩” changes both axis scales by the same ratio. Repeating “旋转” or
“等比例伸缩” on screen, highlighting the words, or swapping a formula is not
evidence. The timing tolerance is 0.08 seconds for these word-level actions.
Detection must follow the exact approved spoken surface, including common
equivalent phrases such as “等比缩放” and “拉长”; an authored action contract
whose spoken token is not detected is a hard failure, not an exemption. When a
legitimate spoken synonym is missing, extend the canonical detector and its
regression test, resync every active worktree, and reopen the batch under the
new Skill tree hash before continuing.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" freeze-text-inventory \
  --repo-root . \
  --scene-slug <scene_slug> \
  --baseline-label <approved-version> \
  --source path/to/src/scenes/<scene_slug> \
  --output path/to/screen_text_baseline.json

python3 "$SKILL/scripts/pipeline_v2.py" verify-text-inventory \
  --repo-root . \
  --scene-slug <scene_slug> \
  --source path/to/src/scenes/<scene_slug> \
  --baseline path/to/screen_text_baseline.json \
  --output path/to/screen_text_audit.json
```

For graph or formula-dense scenes, the runtime evidence must also include relation encodings, single-expression formula-row anchors, emphasis before/after geometry plus its onset/hold/recovery profile, clause locks, stage-motion easing evidence, and one snapshot inside every stage transition. When two equations reuse one screen slot, declare the handoff in `scene_plan.json` and execute it through `V2SceneRuntime.sequential_formula_handoff`; the runtime enforces an empty occupancy gap and `validate-authoring-qc` rejects missing, overlapping, or identity-drifted handoffs. Moving labels, braces, values, and markers must likewise declare an `identity_binding`; runtime snapshots sample carrier-dependent distance and reject detached dependents. This does not prove mathematical placement: points that claim an axis value, equality, sample, root, or intersection must also export independent `coordinate_checks` against the underlying coordinate map. A semantically correct but ugly cross-graph arrow, a fast partial-box highlight, a temporarily deformed equation, a stop-start section move, or an unaudited transition midpoint is a gate failure rather than optional polish.

Do not compress a necessary visual state chain merely because the provisional narration window is short. Before scene audio lock, revise the local wording or add a pause freely. After lock, edit only that scene's audio and regenerate only its reader SRT, word alignment, and timeline fragment. Downstream scene-local time remains unchanged; final assembly recomputes global offsets. A review-only audio patch or a visual slowdown that no longer matches the scene production contract is invalid.

### Prefer Visual Fidelity Over Assumed Render Limits

Do not simplify a named mathematical or physical object merely because a more
faithful version might cost more to render. The default production assumption
is that the available workstation has enough headroom for fine geometry,
dense sampling, smooth continuous gradients, high-resolution field textures,
and polished transitions. Rendering performance is not a quality budget unless
an actual measured render, memory, or decode failure proves otherwise.

When the narration names a concrete object such as a plate carrying a
temperature field, the scene must visibly construct that object and encode the
field from the same mathematical source at sufficient spatial and colour
resolution. A generic grid, coarse patch, or decorative gradient cannot stand
in for the named object. If optimization becomes necessary, first preserve the
mathematical identity, perceptual smoothness, and review checkpoints; record
the measured bottleneck and bounded fallback in the stage direction and
experiment log, then rerun the same five hard-gate layers. Never pre-emptively
lower modelling precision, sampling density, colour resolution, or visual
finish on an unmeasured performance assumption.

Do not optimize for a required number of review failures. Optimize for concrete evidence and low human rejection.

## Freeze The Review Candidate

Create one canonical review workspace per scene. Reuse `current/` for derived media instead of creating `v12`, `v13`, and growing frame directories; immutable attempt history belongs in JSONL logs.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" prepare-review-workspace \
  --repo-root . --episode "$EPISODE" --scene-slug <scene_slug>
```

After deterministic checks pass, bind the exact candidate. In progressive mode, output must be `review/v2/<scene_slug>/current/review_manifest.json` and include:

For v7 profiles, `freeze-review` also requires a sealed
`render_receipt`. Independent hashes for `source` and `review_mp4` are not
proof that the video was rendered from that source. The receipt must bind the
exact source tree hash, complete render command, concrete tool versions,
fresh media directory, real runtime-telemetry hash, and resulting MP4 hash,
and must declare `reused_media=false`. Reusing an earlier MP4 after any source
behavior or screen-text change is a blocker even when regenerated telemetry,
contact sheets, or source-only text audits look valid. Author self-review must
also compare decoded non-subtitle video text and key visible actions back to
the bound source or declared assets.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" freeze-review \
  --repo-root . \
  --episode "$EPISODE" \
  --scene-slug g002c_riemann_sum_limit \
  --profile path/to/scene_profile.json \
  --artifact design_challenge=path/to/design_challenge.json \
  --artifact deliberation=path/to/design_deliberation.json \
  --artifact design_gate=path/to/design_gate.json \
  --artifact precedent_packet=path/to/precedent_packet.json \
  --artifact plan=path/to/scene_plan.json \
  --artifact episode_spine="$EPISODE/episode_visual_spine.json" \
  --artifact batch_plan="$EPISODE/review/v2/<batch-id>/batch_visual_plan.json" \
  --artifact source=path/to/scene/package \
  --artifact scene_production=path/to/scene_production.json \
  --artifact scene_registry=path/to/scene_registry.json \
  --artifact script=path/to/scene/script.md \
  --artifact timeline=path/to/scene/timeline.json \
  --artifact telemetry=path/to/runtime_telemetry.json \
  --artifact authoring_qc=path/to/authoring_qc.json \
  --artifact review_mp4="$EPISODE/review/v2/<scene_slug>/current/review.mp4" \
  --artifact qc="$EPISODE/review/v2/<scene_slug>/current/qc" \
  --artifact layout_audit=path/to/layout.json \
  --artifact srt=path/to/subtitles.srt \
  --artifact word_srt=path/to/word_level.srt \
  --artifact word_alignment=path/to/word_alignment.json \
  --artifact asr_transcript=path/to/asr_transcript.txt \
  --artifact narration_qc=path/to/narration_qc.json \
  --artifact audio=path/to/audio.wav \
  --artifact text_inventory_baseline=path/to/screen_text_baseline.json \
  --artifact text_inventory_audit=path/to/screen_text_audit.json \
  --output "$EPISODE/review/v2/<scene_slug>/current/review_manifest.json"
```

Any source, plan, timeline, audio, subtitle, audit, QC, render receipt, or MP4
change invalidates the manifest. Re-render into a fresh media directory,
rebuild the receipt, and re-freeze. A source change can never be cleared by
asserting that the old media is “visually unchanged.”

## Seal Author Self-Review Before Independent Review

After freezing, do not let telemetry certify itself. First generate `self_review_probe.json`. For every hard-gate layer, the author must state the expected state, report the decoded state, actively try to falsify it, attach a real hashed frame inside the frozen QC artifact, bind it to the exact review-MP4 hash, and independently recompute or measure the claimed relation. The CLI selects a complete claim-anchor pair: stage-state claims stay on their state, mathematical invariants stay on their own checkpoints, clause locks stay on their spoken anchor, and novice-causality claims stay on their beat. The author cannot retarget an easy empty region, reuse one decoded frame path or CLI timestamp for multiple probes, or copy the same numeric claim across layers. Claims without a concrete mathematical object are discarded; if a layer has no valid claim, the CLI falls back to the plan's declared object inventory rather than emitting an unsealable empty target. Probe selection is time-stratified across the complete claim-anchor sequence: one-probe scenes use the middle pair, while strict two-probe scenes use the earliest and latest pairs. When two layers share an authored anchor, the later probe samples a nearby frame without changing its semantic claim. The CLI opens the frame, recomputes its SHA-256, verifies containment in the manifest artifact, and recomputes the comparator result; a self-filled `passed: true` cannot override it. Human-rejected and repeat-rejected scenes require two ranked adversarial probes per layer. A generic pass, a telemetry-only claim, a nonexistent frame, a fabricated hash, a front-loaded probe set, or a missing coordinate/value recomputation is rejected before independent review.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" prepare-self-review-probe \
  --repo-root . \
  --manifest path/to/review_manifest.json \
  --output path/to/self_review_probe_draft.json
# Fill every probe from decoded frames and independent calculations.
python3 "$SKILL/scripts/pipeline_v2.py" seal-self-review-probe \
  --repo-root . \
  --manifest path/to/review_manifest.json \
  --input path/to/self_review_probe_draft.json \
  --output path/to/self_review_probe.json
python3 "$SKILL/scripts/pipeline_v2.py" prepare-author-self-review \
  --repo-root . \
  --manifest path/to/review_manifest.json \
  --self-review-probe path/to/self_review_probe.json \
  --owner ANIMATION_AGENT \
  --author-agent-id CURRENT_AGENT_ID \
  --author-model MODEL \
  --output path/to/author_self_review_draft.json
python3 "$SKILL/scripts/pipeline_v2.py" seal-author-self-review \
  --repo-root . \
  --manifest path/to/review_manifest.json \
  --input path/to/author_self_review_draft.json \
  --output path/to/author_self_review.json
```

If author self-review catches a real defect, do not weaken the self-review to
manufacture `ready_for_independent_review`, and do not edit directly from an
unsealed chat todo. Preserve the gate-rejected
`lecture-animation-author-self-review-v2` draft and its canonical
`author_self_review_attempts.jsonl` row. The main supervisor expands every
author finding into the same code-level guidance and exhaustive root-cause
plan required after an independent rejection, then compiles an
author-origin repair contract:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" compile-author-repair-contract \
  --repo-root . \
  --repair-plan path/to/author_repair_plan.json \
  --review-exhaustion path/to/review_exhaustion.json \
  --author-self-review path/to/gate_rejected_author_self_review_draft.json \
  --manifest path/to/rejected_manifest.json \
  --output path/to/author_repair_contract.json
```

The command first verifies the frozen manifest and all bound artifacts. It
rejects an invented or accepted attempt, a plan that omits any
self-review finding, any attempt whose verification key, derived id, author
identity, finding count, or recorded gate errors do not match the rejected
draft, a non-canonical attempt-log path, a substituted source-finding hash or
exact `source_author_finding` snapshot, any changed copied source field, and
any deleted copied source field, and any non-exhaustive repair guidance. It reruns the rejected self-review gate
from the frozen manifest, profile, and plan and requires the recorded error list
to match exactly. `verify-repair-response` also refuses a stale or malformed
contract before it can emit a passing repair gate or accepted attempt. Run the normal
`prepare-repair-response` and `verify-repair-response` gates after the new
candidate is frozen. The replacement self-review must supply
`--previous-author-self-review` together with the repair contract, response,
and gate. This is the only author-self-review repair transition; it does not
grant independent acceptance.

After an independent `revise`, do not start editing from `suggested_fix` prose. The accepted attempt creates `pending_repairs[scene_slug]` in the persistent session. A later pass is impossible unless the author self-review binds the exact revise-review hash and supplies the sealed repair contract, response, and gate. The reviewer must first generate and seal `review_exhaustion.json`. It groups every symptom under exactly one `root_issue_id` and forces inspection of the full affected interval, source symbols, upstream causes, downstream symptoms, dependent artifacts, sibling paths, preservation requirements, predicted repair regressions, and all five hard-gate layers. The CLI rejects partial issue lists, duplicate root clusters, and findings left outside a cluster.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" prepare-review-exhaustion \
  --repo-root . \
  --review path/to/revise_review_draft.json \
  --manifest path/to/rejected_manifest.json \
  --output path/to/review_exhaustion_draft.json
# Complete the cluster search, seal it, then embed the sealed record as
# review_exhaustion in the final review submission.
python3 "$SKILL/scripts/pipeline_v2.py" seal-review-exhaustion \
  --repo-root . \
  --review path/to/revise_review_draft.json \
  --manifest path/to/rejected_manifest.json \
  --input path/to/review_exhaustion_draft.json \
  --output path/to/review_exhaustion.json
```

Only then compile the review into a repair contract. Every finding must already contain lineage, exact code anchors, the mathematical invariant, required code changes, behavior that must survive, affected artifacts, acceptance tests, and risks the repair could create. The repair contract snapshots root-cause clusters as well as individual findings, so the author repairs one cause comprehensively instead of chasing symptoms across rounds.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" compile-repair-contract \
  --repo-root . \
  --review path/to/revise_review.json \
  --manifest path/to/rejected_manifest.json \
  --output path/to/repair_contract.json
```

Choose and seal one repair-execution mode before touching the candidate:

- `same_author`: the original production author repairs the scene. This preserves clear ownership but records at least one review-to-author handoff.
- `repair_surgeon`: another production agent applies the repair from the sealed contract. This also records at least one handoff.
- `reviewer_assisted`: the discovery reviewer may directly apply a localized repair when translating the finding into prose would lose important visual, timing, or code context. The editor is then automatically recused from accepting that candidate; a different planned verifier must run the complete independent review. Direct editing never allows the reviewer to certify their own repair.

The mode, repair actor, editor set, planned verifier, and handoff count are part
of the sealed repair lineage. `phase-start --phase repair` and
`prepare-repair-response` must bind the same values; mismatches or a verifier
who edited the candidate are rejected. Use `reviewer_assisted` only when the
repair is localized and the reviewer already has the shortest faithful path
from evidence to code. Conceptual rewrites and broad scene redesigns remain
`same_author` or `repair_surgeon`. In a parallel episode where the main
acceptance reviewer performs the edit, start the fresh verifier with
`--review-role recusal_acceptance`. The CLI allows that exception only when the
main agent is the sealed repaired-candidate author, the verifier is different,
and the later self-review carries the matching `reviewer_assisted` execution
record. The main agent still controls the CLI and human-review gate; it does
not supply the independent verdict for its own edit.

After repairing and freezing the new candidate, prepare and complete `repair_response.json`, then run the hard repair gate:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" prepare-repair-response \
  --repair-contract path/to/repair_contract.json \
  --current-manifest path/to/new_manifest.json \
  --repair-mode same_author \
  --repair-actor-agent-id production-agent-a \
  --planned-verifier-agent-id independent-reviewer \
  --handoff-count 1 \
  --output path/to/repair_response.json
python3 "$SKILL/scripts/pipeline_v2.py" verify-repair-response \
  --repair-contract path/to/repair_contract.json \
  --repair-response path/to/repair_response.json \
  --current-manifest path/to/new_manifest.json \
  --output path/to/repair_gate.json
```

The response must resolve every finding once, name changed code symbols and artifacts, pass every acceptance and preservation check, and probe every contracted new risk. Only then may `prepare-author-self-review` and `seal-author-self-review` run with `--previous-review`, `--repair-contract`, `--repair-response`, and `--repair-gate`. Missing or stale repair evidence blocks independent review. If phase timing is recorded, `phase-start --phase repair` also requires `--previous-review`, `--repair-contract`, `--repair-execution-mode`, `--repair-actor-agent-id`, `--planned-verifier-agent-id`, and `--handoff-count`; a completed repair phase requires `phase-end --repair-response ... --repair-gate ... --current-manifest ...`. Repair attempts are appended to `repair_attempts.jsonl`; independent attempts record lineage counts, repair hashes, execution mode, editor identity, verifier identity, and handoff count, so later reports can distinguish missed old defects, repair-induced regressions, incomplete fixes, and handoff overhead.

## Review With One Persistent Independent Agent

Start one reviewer session for a batch of three to five scenes. The CLI binds reviewer identity, model, reasoning effort, reviewer tier, subagent session id, rules hash, and batch history. Resume that reviewer for repair checks so it retains the exact failure context unless that reviewer edited the repaired candidate. In `reviewer_assisted` mode, the editor is recused and the sealed planned verifier must perform the complete independent review; use `recusal_acceptance` when the recused editor is the parallel episode's main agent. Do not silently replace a reviewer; replacement requires a recorded reason.

In parallel-batch mode, the main agent may serve as this independent reviewer because the detailed scene design, code, rendering, and scene-local audio were authored by a production subagent. The immutable author and reviewer agent IDs must still differ. The main agent's review scope includes source, stage and mathematical truth, rendered video, narration wording, a complete audio playback, exact ASR transcript, reader/word subtitles, word alignment, timeline duration, boundary audio-visual handoffs, and a novice audio-only teach-back. A visual pass cannot compensate for a narration or audio failure.

A frontier reviewer needs no admission benchmark. A light reviewer is allowed only after `certify-reviewer` passes a hash-bound benchmark for the exact model, reasoning effort, and current rules registry. A human rejection after an automatic pass suspends that light certification and forces escalation or recertification; a self-declared calibration pass cannot clear the suspension.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" begin-review-batch \
  --repo-root . \
  --episode-spine "$EPISODE/episode_visual_spine.json" \
  --review-role acceptance \
  --batch-id fourier-g003-g005 \
  --owner ANIMATION_AGENT \
  --author-agent-id ANIMATION_AGENT_SESSION_ID \
  --reviewer REVIEW_AGENT \
  --reviewer-model MODEL \
  --reviewer-tier light \
  --reasoning-effort medium \
  --certification path/to/reviewer_certification.json \
  --reviewer-agent-id SUBAGENT_SESSION_ID \
  --output "$EPISODE/review/v2/review_session.json"
```

Review-session contract v5 derives authority from the episode spine. In `parallel_batches` mode, only `main_agent_governance.owner` may hold `review-role acceptance` and grant `pass_for_user_review_pending`. Other independent reviewers must use `diagnostic_support`; they may report defects but cannot grant final acceptance. The session stores and rechecks the spine hash on every candidate.

If the episode spine, active reviewer model, or assigned production owner changes while verified repairs are still pending, do not start a blank session and do not rewrite the old review identity. Use `migrate-review-session`. It updates the spine/reviewer binding and, when both `--owner` and `--author-agent-id` are supplied, reassigns the author while preserving `applied_review_attempt_ids`, `pending_repairs`, and the original session id. The migration records the prior author/reviewer identity, reason, and exactly which repair ledgers were preserved. Any loss of attempts or pending repairs is a hard failure.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" migrate-review-session \
  --repo-root . \
  --input "$EPISODE/review/v2/review_session.json" \
  --episode-spine "$EPISODE/episode_visual_spine.json" \
  --owner REPLACEMENT_ANIMATION_AGENT \
  --author-agent-id REPLACEMENT_ANIMATION_AGENT_SESSION_ID \
  --reviewer MAIN_ACCEPTANCE_REVIEWER \
  --reviewer-model CURRENT_MODEL \
  --reviewer-tier frontier \
  --reasoning-effort xhigh \
  --reviewer-agent-id MAIN_AGENT_SESSION_ID \
  --reason "Rebind the active ledger after the episode spine or reviewer model changed." \
  --output "$EPISODE/review/v2/review_session_migrated.json"
```

### Phase A: Blind Novice Pass

Compile a compact review capsule from the frozen manifest. It contains only applicable rule IDs, hard-gate anchors, object IDs, active regression keys, and three deterministic time-stratified blind checkpoints selected near the centers of the early, middle, and late thirds. Do not resend the expanded policy/profile/precedent corpus in the prompt.

Give the reviewer only the review MP4 plus the capsule's blind checkpoints. Before exposing source, plan, or contracts, persist the novice answers and run `seal-blind-review`. The receipt binds those answers to the exact MP4, reviewer session, model, and reasoning effort.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" prepare-review-capsule \
  --repo-root . --manifest path/to/review_manifest.json \
  --author-self-review path/to/author_self_review.json \
  --review-session "$EPISODE/review/v2/review_session.json" \
  --output path/to/review_capsule.json
python3 "$SKILL/scripts/pipeline_v2.py" seal-blind-review \
  --capsule path/to/review_capsule.json \
  --blind-review path/to/blind_review.json \
  --review-session "$EPISODE/review/v2/review_session.json" \
  --output path/to/blind_review_receipt.json
```

- What changed on screen, and what caused it?
- Which object should the eye follow at each transition?
- Where would a viewer without the result already in mind become confused?
- Did a formula merely appear, or did the mathematical action produce it?

For a repeat-rejected scene, first replay with audio muted. The reviewer must submit a muted teach-back, a muted driver prediction, and at least three timestamped candidate-confusion probes with a visible anchor and a pointing/prediction resolution test. This is intentionally harder than saying "I understood": it forces the animation itself to carry the causal explanation.
- Teach the claim back in one sentence without echoing the narration.
- Predict what changes when the declared mathematical driver changes.

### Phase B: Informed Standards Pass

Then let the same reviewer resolve supporting artifacts named by the capsule. The reviewer must submit one check per applicable reviewer rule with timestamped object-level evidence, plus three distinct worst-frame candidates and the required `narration_review`. The narration review binds the sealed narration-QC hash, reports complete-playback and audio-only novice evidence, checks style/claim ownership and mathematical terminology, and verifies transcript/subtitle/alignment/timeline drift rather than trusting file existence. Use the JSON schema in `references/contracts.md`.

Before the transactional submission, run `verify-review --lint-only` until contract, hash, coverage, calibration, and evidence-binding errors are gone. Lint never appends an attempt or mutates the persistent review session; only the final non-lint submission counts as a review submission.

For a `revise` verdict, every finding must remain `open` and implementation-ready. A reviewer cannot pre-close a defect; only the later repair response can prove closure. The reviewer is not required to edit code, but must inspect enough source to name the responsible file and symbol, state the invariant that the repair must restore, identify dependent artifacts, define executable acceptance evidence, preserve already-correct behavior, and predict likely repair regressions. When the sealed repair execution uses `reviewer_assisted`, that reviewer becomes a repair co-author for the candidate and is barred from its acceptance review. The sealed `review_exhaustion` record must be embedded in the submission before `verify-review`. Every cluster layer and every unclustered search carries real decoded QC frames whose paths exist inside the manifest's QC artifact, whose hashes match disk, and whose source MP4 hash matches the frozen candidate. A finding without this repair guidance or outside an evidence-bound exhaustive root-cause cluster is rejected; it cannot enter the author queue.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" verify-review \
  --repo-root . \
  --manifest path/to/review_manifest.json \
  --author-self-review path/to/author_self_review.json \
  --review path/to/review_submission.json \
  --review-session "$EPISODE/review/v2/review_session.json" \
  --review-capsule path/to/review_capsule.json \
  --blind-receipt path/to/blind_review_receipt.json
```

The gate rejects stale artifacts, author-reviewer identity reuse at both the human label and immutable agent-session level, missing rules, generic evidence, copied observations, unsupported exemptions, unresolved findings, an altered post-blind novice report, and an anomalous reviewer pass. It also blocks author handoff and reviewer pass while an applicable live-policy issue remains open at blocker, critical, major, or high severity. Repair it, change the issue to an explicit resolved-pending-review state, and recompile/refreeze the policy/profile/manifest. A review batch binds both `author_agent_id` and `reviewer_agent_id`; equality or a stale pre-v5 session blocks review. Autopilot reviews must submit five complete coverage sweeps: layout, mathematical-object truth, timing/attention, novice causality, and visual finish. The CLI derives required timestamps from stage states, transitions, invariant checkpoints, clause locks, and beats. Re-running verification on the same submission is deduplicated and does not inflate attempt counts. `pass_for_user_review_pending` means only that the candidate may be shown to the user.

Derive the current state from evidence instead of editing a status field by hand:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" gate-status \
  --repo-root . \
  --profile path/to/scene_profile.json \
  --plan path/to/scene_plan.json \
  --challenge path/to/design_challenge.json \
  --deliberation path/to/design_deliberation.json \
  --design-gate path/to/design_gate.json \
  --precedent-packet path/to/precedent_packet.json \
  --manifest path/to/review_manifest.json \
  --author-self-review path/to/author_self_review.json \
  --review path/to/review_submission.json \
  --review-session "$EPISODE/review/v2/review_session.json" \
  --review-capsule path/to/review_capsule.json \
  --blind-receipt path/to/blind_review_receipt.json \
  --output path/to/scene_state.json
```

Only `user_review_pending` permits presentation to the user. `scene_state.json` is a derived, hash-stamped record; it does not grant commit permission.

When review returns `revise`, update the scene plan if stage logic changed, repair, rerun deterministic checks, rerender, re-freeze, then complete a new author self-review bound to the prior findings. Only after that passes may the same independent reviewer inspect the replacement. The loop is always `author -> self-review -> independent review -> repair -> self-review -> independent review`; a diagnostic pass never skips either self-review or the later full independent pass. Do not impose a fixed maximum number of full reviews. Before requesting diagnostic routing, write and seal `change_impact.json` with exact changed object IDs, time windows, hard-gate layers, and an explicit assertion that semantic contracts stayed fixed. Without valid impact proof, or after any profile/policy/plan/timing/audio/subtitle/text-contract change, the CLI requires another five-layer full review. Three repeated full-review loops trigger root-cause re-planning rather than a pardon.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" choose-review-mode \
  --previous-manifest path/to/old_manifest.json \
  --current-manifest path/to/new_manifest.json \
  --previous-review path/to/revise_review.json \
  --review-session "$EPISODE/review/v2/review_session.json" \
  --change-impact path/to/change_impact.json \
  --attempt-log "$EPISODE/review/evolution/review_attempts.jsonl" \
  --output path/to/review_strategy.json
```

The resulting packet is executable scope rather than another prompt: every open finding receives a required time window; the CLI adds unchanged-region regression samples; changed artifact hashes and reviewer identity are fixed. `verify-diagnostic-review` rejects omitted findings, evidence outside the required windows, absent regression samples, reviewer switches, and attempts to grant final pass. A diagnostic pass yields only `diagnostic_fix_verified`; a fresh five-layer full review of the new candidate remains mandatory before `user_review_pending`. Never inherit a pass from an older MP4.

## Present For User Review

Present each scene separately even when several are ready together. Include:

- review MP4;
- QC/contact sheet;
- scene profile and plan;
- timeline, audio, and subtitle paths;
- source package and layout audit;
- manifest and review result;
- remaining limitations, if any.

Do not combine scene videos before scene-level approval. Do not stage or commit until the user explicitly approves.

## Finish An Approved Episode

Treat the exact user phrase `可以收尾了` as explicit approval of the currently
presented episode candidate and authority to run the standard finishing route.
The equivalent phrase `可以四K导出整集了` also authorizes the render/assembly
route, but does not by itself authorize a source/control commit unless the user
also says `提交`, `commit`, or `可以收尾了`.

Before acting, read `references/finalization.md` completely. Refuse to start if
any scene lacks durable human approval, any repair invalidated the approved
manifest, or the final source/audio/subtitle inputs cannot be resolved by hash.
Do not ask the user to repeat the standard options: use the latest approved
series precedent and report any discovered exception.

The standard route is one atomic evidence chain:

1. render every approved source scene at native `3840x2160p30`;
2. preserve approved scene-local timing and audio, then offset-assemble without
   silently retiming internal animation;
3. proofread the reader SRT against formal script/timeline text, burn it into
   video pixels, and keep the corrected reader SRT as an upload sidecar;
4. apply the approved BGM recipe and restrained editorial sprite cues;
5. hard-bind Sumino's visible sign-off layer to the word-level identity/name
   cue in the fixed ending, never merely to the last scene's approximate tail;
6. run independent subtitle, sprite, media, decode, duration, loudness,
   boundary, and hash QC; then write one finalization manifest and contact
   sheet.

Unless the user explicitly names a different BGM or mix configuration, the
finishing trigger always reuses the established series BGM source and exact
validated mix recipe; do not omit music and do not ask the user to restate it.

`可以收尾了` additionally grants staging and committing only the already
approved episode source/control files and finalization receipts after every
finishing gate passes. It never grants push, upload, deletion of intermediates,
worktree cleanup, or replacement of the approved mathematical picture. A
failed finishing gate blocks commit and returns the bounded layer to its
original owner.

## Evolve From Outcomes, Not Rule Volume

Immediately after human feedback, before touching animation code:

1. write each finding to `review/issues/*.json` with `source: human_review`, `must_check_in_future: true`, and the affected scene;
2. rerun `compile-profile`, which refreshes `active_policy.json` and invalidates the old manifest;
3. update the plan's regression prevention and mathematical invariants where applicable;
4. only then repair and review again.

Also append one durable outcome event; do not leave new human feedback only in Markdown or chat:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" record-outcome \
  --episode "$EPISODE" \
  --scene-slug g002c_riemann_sum_limit \
  --author-model MODEL \
  --reviewer-model MODEL \
  --automatic-verdict pass_for_user_review_pending \
  --human-verdict revise \
  --caught-by human \
  --pattern-key formula_overlap \
  --review-rounds 2 \
  --reviewer-findings 3 \
  --human-findings 1 \
  --render-count 3 \
  --minutes 74
```

At a scene batch or episode boundary:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" evolution-report \
  --event-log "$EPISODE/review/evolution/events.jsonl"
```

Follow `references/evolution.md`. New feedback enters as an event and candidate pattern first. Promote a rule only when severity or recurrence justifies it, its applicability is narrow enough to compile, and it has a concrete evidence contract or machine check. Merge or retire rules that add reading cost without reducing recurrence.

At final media delivery, run `finalize-episode` with the fresh
`--episode-readiness` receipt. It refuses to close the episode unless every
scene has one durable human-pass outcome, every issue JSON has a terminal
status, every scene has reached at least `audio_aligned`, every required final
artifact exists, and every parallel scene is covered by a supplied batch
contract. A parallel episode must also supply a v2 supervisor session already
closed by `supervisor_watch.py finish`; the command scans every
`review/v2/supervisor*.json`, so an open duplicate, active/blocked agent,
pending/blocked task, or unused replacement authorization blocks finalization.
It then atomically marks scenes assembled, closes the supplied batches, seals
the final assembly, and writes one media/production completion receipt. This
does not yet prove the eight-hour complete workflow, because retrospective is
still outstanding. Do not hand-edit
`progressive_production.json` or leave batches or supervisor assignments active
after upload.

Before final delivery or worktree deletion, run `audit-portability
--require-clean`, and promote accepted ignored/generated assets into the
canonical checkout with `promote-scene`. A merged branch is not evidence that
audio, alignment, review media, or final video survived. Current authoritative
text must use repo-relative paths; historical absolute provenance needs a
current rebuild manifest that supersedes it.

Measure work phases rather than estimating total minutes from memory. Wrap planning, design, authoring, render, review, repair, TTS, ASR, finalization, retrospective, and human wait with `phase-start` / `phase-end`; render and TTS also require a classified `--phase-purpose`. Record actor role, model, reasoning effort, prompt/artifact bytes, files read, and available input/cache/output/reasoning token counts. Reused concurrent work must pass one stable `--shared-work-key`, which derives the same `phase_instance_id` across scene wrappers; probable legacy duplicates remain reported rather than silently multiplied. Planned scenes in `progressive_production.json` remain the denominator, and zero eligible phase events mean zero observability rather than complete coverage. `batch-status` separates accepted review rounds from gate-rejected submissions, classifies rejection/finding causes, and reports self-review capture rate, retry time, recursive artifact size, critical path, aggregate agent-seconds, concurrency overlap, and cumulative episode token ratios. At each skill change, write a pre-change and matched post-change record with `snapshot-iteration`, then use `compare-iterations`.
Only phase events ending with `result=completed` satisfy per-scene coverage;
design, authoring, render, and review are mandatory, and any scene that entered
repair, has a repair attempt, or received a durable revise/blocked outcome also
needs a completed repair phase.

## Retrospect On A Finished Episode

Treat the exact user phrase `复盘一下` as authority to run the standard
post-episode retrospective for the most recently finished episode in the
current task context. Do not ask the user to repeat which logs, metrics, review
records, or Git evidence to inspect. If the context names no episode, infer the
newest episode with a valid completion receipt or approved final master; ask
only when two candidates are equally current.

Before acting, read `references/postmortem.md` completely. Start with the
deterministic quantitative evidence pack:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" episode-retrospective \
  --repo-root . \
  --episode "$EPISODE" \
  --output "$EPISODE/review/evolution/postmortem.json" \
  --require-finalized
```

Then inspect the bounded evidence paths named by that pack and write
`$EPISODE/review/evolution/postmortem.md`. Report numbers before
interpretation: observability coverage, critical-path and aggregate-agent time,
phase/token distribution, retry time, review and repair rounds, human
false-passes, recurring issue patterns, artifact growth, and coordination
churn. Missing telemetry remains an explicit denominator or unknown; never
turn it into a zero.

Classify root causes, rank bottlenecks by measured critical-path cost,
recurrence, quality risk, and implementation cost, then change the smallest
enforceable layer in this order: deterministic checker, inference/retrieval,
narrow conditional contract, prose. Apply high-confidence pipeline fixes,
tests, and documentation during the same retrospective; leave subjective
teaching or visual-taste choices as recommendations unless the user already
made them durable feedback. Snapshot the pre-change state, validate the
candidate, run an independent forward test on raw artifacts, and record the
post-change hypothesis for the next matched episode.

After the retrospective phase has ended, close the episode efficiency contract:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" close-episode-efficiency \
  --repo-root . --episode "$EPISODE" \
  --efficiency-contract "$EFFICIENCY" \
  --completion-receipt "$EPISODE/episode_completion.json" \
  --output "$EPISODE/review/evolution/episode_efficiency_close.json"
```

This is the final process-compliance gate. It requires the completion receipt,
all required global phases through retrospective, complete scene phase pairs,
complete token telemetry, time and token totals within budget, zero known
regression recurrence, zero automatic false pass, and scene-local human issue
coverage below the sealed threshold. On failure it writes a failed audit but
keeps the contract active; it cannot reset or erase prior usage. Only a valid
`lecture-animation-episode-efficiency-close-v1` receipt proves that the
eight-hour workflow succeeded.

`复盘一下` authorizes read-only repository analysis plus scoped edits, tests,
and a local commit of the retrospective and resulting Skill/tooling
improvements. It does not authorize pushing, uploading, deleting media,
removing worktrees, or changing already approved episode content.

## Resources

- `scripts/pipeline_v2.py`: backward-compatible CLI entrypoint and domain command adapters.
- `scripts/pipeline_v2_lib/core.py`: dependency-free hashes, timestamps, errors, and canonical serialization.
- `scripts/pipeline_v2_lib/storage.py`: process locks, atomic JSON replacement, locked JSONL append/deduplication, and read-modify-write primitives.
- `scripts/pipeline_v2_lib/review_state.py`: persistent review-session and attempt transactions.
- `scripts/pipeline_v2_lib/governance.py`: main-agent review authority, live-policy blocker, and pending-repair gates.
- `scripts/pipeline_v2_lib/design_readiness.py`: low-cost animatic design lock required before expensive TTS and final renders.
- `scripts/pipeline_v2_lib/episode_ops.py`: episode readiness, compact task capsules, canonical promotion, and rebuild-portability gates.
- `scripts/pipeline_v2_lib/metrics.py`: phase deduplication, retry/hotspot metrics, and review error classification.
- `scripts/supervisor_watch.py`: durable continuous-monitoring state, low-noise milestone classification, and finish gate for subagent supervision.
- `scripts/state_store_stress.py`: multi-process contention and crash-safety diagnostic for the file state backend.
- `references/authoring-philosophy.md`: novice-centered layered cognitive staging, dynamic stage topology, and executable M/D/A visual grammar.
- `references/rules.json`: single machine-readable rule registry.
- `references/contracts.md`: scene-plan, manifest, and review submission contracts.
- `references/evolution.md`: rule lifecycle and metric-driven compaction.
- `references/postmortem.md`: quantitative-first post-episode retrospective,
  bottleneck attribution, bounded Skill evolution, and the `复盘一下` trigger.
- `references/preflight-portability-and-handoffs.md`: cheap episode gates,
  lossless low-token coordination, canonical asset promotion, and worktree-safe
  rebuild audits.
- `references/finalization.md`: post-approval 4K, burned-subtitle, Sumino,
  BGM, independent-QC, manifest, and commit contract triggered by `可以收尾了`.
