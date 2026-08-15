## Choose A Production Mode

Record one mode in `episode_visual_spine.json` before production:

- `main_producer`: the main agent owns episode writing, coarse design, detailed scene design, and animation implementation. Subagents are used only for independent review. Missing `production_mode` in a legacy spine is interpreted as this mode.
- `parallel_batches`: the main agent still owns every episode-global artifact and decision: lecture, provisional narration, coarse storyboard/timeline, episode visual spine, batch partition, stable identities, human-feedback compilation, user communication, and acceptance review after each production subagent's sealed self-review. Production subagents own only bounded detailed batch/scene design, scene-local audio, implementation, and self-review. The main agent may additionally delegate an independent review pass, but may not delegate its acceptance responsibility.

In `parallel_batches`, never delegate an unbounded request such as “make the episode.” Before a subagent starts, the main agent must freeze the batch entry and exit contracts, including the boundary visual state, narration handoff at the selected lock level, required identity carriers, transition owner, explicitly free interior, and one audio handoff contract. The audio handoff fixes outgoing/incoming clause ownership, tail silence, maximum boundary drift, and a no-clipped-phoneme/no-split-mathematical-clause cut policy. Adjacent batches must share identical exit/entry audio-visual handoffs. The main agent may lock the first and last animation states or exact boundary narration while leaving internal choreography open.

The main agent must also freeze one episode-level `narration_style_contract` derived from the approved lecture, narration outline, prior episode scripts, and current human feedback. Every batch plan reproduces it exactly and adds scene-local style notes. Production subagents may refine wording only inside that contract and the independently approved visual plan; they may tune sentence rhythm before exact audio lock, but may not change the teaching voice, prerequisite order, mathematical claim ownership, terminology, stage logic, or viewer-facing boundary. Internal adjacency contracts must lock outgoing and incoming visual states, narration lock/text, handoff meaning, identity carriers, transition ownership, and explicitly free interior. A batch plan missing any of these fields must fail the CLI gate.

Before the first scene enters TTS, run the episode-level gate in
`references/preflight-portability-and-handoffs.md`. It blocks duplicated
boundary narration, unsafe rolling pace, missing novice prerequisite bridges,
screen-text/summary-connector overload, unstable pronunciation mappings, and a
missing or duplicated fixed ending before those failures multiply into audio,
subtitle, render, and assembly work. Rerun it after any narration, timing,
terminology, or ending change.
For just-in-time parallel production, use the documented `pre_tts`
`progressive_wave` scope: bind only the exact scenes entering the current audio
wave, plus the complete progressive tracker and the global fixed-ending source.
Do not fabricate exact narration for unfinished scenes merely to satisfy a
whole-episode denominator. After synthesis and listening, a post-TTS wave may
release only its exact covered scenes; finalization still requires a
full-episode post-TTS scene set.
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

Run simultaneous production subagents in separate Git worktrees under `/Volumes/bocchi/myLectures-worktrees/<agent-or-task>/`, each on its own `agent/...` branch. Never make several production subagents write concurrently in the canonical checkout, and never create ad-hoc sibling production directories such as `/Volumes/bocchi/myLectures-*`. Before `T0`, create exactly one empty `codex/...` integration worktree; it is the live control/review root for the task, while `/Volumes/bocchi/myLectures` remains the canonical promotion destination. The startup receipt binds both roles so an agent cannot mistake a temporary worktree for the final canonical filesystem. In parallel mode, `begin-production-batch` verifies that `--repo-root` is a direct child of the required worktree root and that the checked-out branch uses the `agent/...` prefix; a canonical-checkout or wrong-branch invocation fails before production starts.

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

Seal one stable roster for the episode; the main agent supervises, integrates,
and performs independent acceptance review. Set `max_subagents` from the live
runtime slots, cumulative cost budget, independent scene supply, and measured
reviewer capacity. The deterministic initial roster is
`min(coherent_batch_count, runtime_slots - 1, 4)`: three producers on a
four-slot host, or four on a wide episode with at least five slots and four
independent batches. The startup receipt rejects a smaller unexplained roster,
because roster discovery must not be delegated to later human correction. The
sealed ceiling may be any value from one through eight; every later identity
must pass the evidence-bound expansion gate below. Spawn the selected producers
once, retain their immutable agent IDs, and reuse them with `followup_task` plus
`supervisor_watch.py assign-task`. A subagent that returned `done` is idle and
reusable while it remains in the current task tree. Do not create a new
identity merely because a scene, review round, repair, recovery, or inventory
pass ended. A cancelled task also leaves its agent identity reusable; task
cancellation is never permission to discard an already opened session.

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
`author_self_review.json`. For historical workflow-v1 batches only, a low-cost animatic uses
`seal-animatic-checkpoint`, which hash-binds the current plan, profile, animatic,
zero-issue authoring QC, and contact sheet without pretending the animatic is a
frozen candidate. Workflow v2 does not create that animatic: the independent
visual-plan review is a planning gate, while optional Keynote/keyframe probes
remain attachments to that review and do not release production checkpoints.
Never run `freeze`, candidate rendering, or formal
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

Later bounded cycles for the same production batch—such as a historical
workflow-v1 animatic pass, a user-requested visual repair, or a current-policy rebind—must
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

After the initial roster, every new `spawn_agent` requires a sealed replacement
or capacity authorization. The only normal reasons are: the old identity
cannot be restored after a direct `followup_task` attempt, the parent task tree
changed, the required model changed, the agent suffered an unrecoverable
failure, or measured candidate starvation justifies unused runtime capacity.
The gate first rejects replacement when any compatible reusable roster member
exists. The first `collaboration.list_agents` result after an app restart is
only a current visibility snapshot: it may omit completed child identities
that remain directly addressable by their canonical task paths. Never infer
permanent loss from that list alone. Replacement never erases the old identity:
the supervisor records cumulative identities, reuse count, replacement count,
replacement reason, and churn ratio. Exceeding the sealed roster or making
more than one replacement requires a concrete recorded override; never open a
new identity when a compatible preserved session can be reused.

Additive capacity is distinct from replacement. Seal a ceiling with
`begin --max-subagents`; it may exceed three only with a concrete capacity
override, and values above eight are invalid. If reviewer-starvation evidence
appears while that ceiling still has room, first seal a fresh availability
snapshot after probing the preserved current and retired IDs, then run
`seal-capacity-evidence` against the current delivery clock and episode
efficiency contract. Pass both receipts to
`authorize-capacity` before spawning. The receipt derives reviewer wait and
candidate-queue depth from the hash-bound delivery board, and derives cost
headroom from complete cumulative token telemetry plus active reservations;
callers cannot submit those numbers as narrative CLI parameters. Authorization
rejects a nonzero candidate queue, less than five measured wait minutes,
missing telemetry or cost headroom, a task outside the sealed pending queue, or
any reusable identity with the same normalized role and model. Reviewer wait
is active production time since the last review opportunity; authorized human
or machine-offline pauses do not count. A snapshot that restores a compatible
retired identity requires `restore-original-identity` and forbids additive
capacity. Registration revalidates both receipts and all bound source bytes.
The capacity receipt also runs the complete
delivery-clock validator and requires the clock, efficiency contract,
supervisor path, canonical repo, episode, `t0`, and reconstructed exact T0 clock
hash to share one lineage. After the child exists,
`register-capacity` consumes the one authorization and activates that exact
task. Unused authorization blocks
`finish` until explicitly cancelled. A closed-session restart may reuse only
the complete reusable set of non-retired IDs that were still in the closed
session's current roster. It automatically preserves the previously authorized
ceiling instead of treating those restored identities as a new initial spawn,
and it must preserve each reused ID's exact role and model. A retired ID must use the
evidence-bound `restore-original-identity` route; cumulative
`identity_history` alone is never revival authority. The restart cannot reset
the roster ledger with new names. Reviewer-wait and cost-headroom inputs must
be finite numbers; `NaN` and infinity are hard failures.

```bash
python3 "$SKILL/scripts/supervisor_watch.py" seal-availability-snapshot \
  --live-agent-id <busy-or-incompatible-agent-id> \
  --followup-attempt \
  '<retired-id>|target_unavailable|<direct followup evidence>' \
  --output "$EPISODE/review/v2/capacity_availability.json"

python3 "$SKILL/scripts/supervisor_watch.py" seal-capacity-evidence \
  --repo-root . --session "$SUPERVISOR" --delivery-clock "$DELIVERY_CLOCK" \
  --efficiency-contract "$EFFICIENCY_CONTRACT" \
  --output "$EPISODE/review/v2/capacity_evidence.json"

python3 "$SKILL/scripts/supervisor_watch.py" authorize-capacity \
  --session "$SUPERVISOR" --role animation_author \
  --task-key <pending-batch> --scope <exact-scope> --model <model> \
  --availability-snapshot \
  "$EPISODE/review/v2/capacity_availability.json" \
  --capacity-evidence "$EPISODE/review/v2/capacity_evidence.json" \
  --reason <bounded-production-reason>
```

`set-assignment` cannot enter `retired`; that state belongs only to the
evidence-bound replacement/restoration commands. It updates the matching task
row for every public transition. Once an identity is idle, completed, or
task-cancelled, `set-assignment` cannot reactivate or block it; only
`assign-task` may reopen work with the required history, reason, and reuse
accounting. `finish` rejects either an active
assignment or an active task row. This prevents an identity from being hidden
before a closed-session restart.

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

`begin --replace` is legal only when its output already contains a valid closed
supervisor session. The flag cannot be attached to a nonexistent path to bypass
the initial-roster gate.

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

Production subagents follow the same low-noise contract when reporting to the
main agent: report only a human-review-ready artifact, a decision/authority
request, a scope/timeline-changing blocker, or the concise status explicitly
requested by the main agent. Routine reads, edits, rerenders, hashes, CLI
transitions, and unchanged heartbeats stay in durable artifacts or supervisor
events. The main agent must not forward a subagent's verbose process narrative
to the user. This milestone-only behavior is the default for future long-running
production; detailed reporting requires an explicit user request for that run.

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

Obey the returned disposition: `persist_only` stays out of commentary; `notify_user` is a milestone update. Before yielding a final response for a supervision task, run `status`. If `should_continue_monitoring` is true, keep waiting or assign pending work to a compatible reusable roster member; if `user_update_required` is true, report only those pending milestone events and acknowledge them after reporting. `--require-clean` rejects abnormal identity churn, pending replacement authorization, or reuse bypass. `finish` rejects active or blocked assignments, pending or blocked planned tasks, and unacknowledged milestone events. See `references/contracts.md` for the replacement evidence schema, event taxonomy, and state contract.
