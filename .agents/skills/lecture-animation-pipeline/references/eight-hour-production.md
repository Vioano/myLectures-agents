# Eight-hour production contract

This reference defines the default delivery contract for a complete lecture
episode from initialization to an upload-ready master. It controls scheduling,
work in progress, model routing, and escalation. It does not replace any
mathematical, audio, animation, review, finalization, or user-approval gate in
the canonical Skill.

## 1. Clock and terminal state

Run `preflight-pipeline-release` at repository scope before the episode exists.
`begin-delivery-clock` is then the first episode command. Its emitted timestamp is
`T0`; it creates the previously absent or empty episode directory before the
production mode, roster, source inventory, user authority, or any other
episode artifact is prepared. It rejects a nonempty project, so hidden setup
cannot precede the clock. The deadline is `T0 + 8:00` of active critical-path
production time.

```bash
EPISODE="videos/<episode-slug>"
DELIVERY_CLOCK="$EPISODE/review/evolution/delivery_clock.json"
python3 "$SKILL/scripts/pipeline_v2.py" begin-delivery-clock \
  --repo-root . --episode "$EPISODE" \
  --delivery-target-hours 8 --retrospective-reserve-minutes 45 \
  --preflight-receipt .pipeline-preflight.json \
  --max-production-agents 3 --max-frozen-candidates 2 \
  --output "$DELIVERY_CLOCK"
```

Pause the active clock only for:

- explicit `human_wait`, while a concrete review artifact or decision is in
  the user's hands;
- measured machine-offline time during which no agent can do safe alternative
  work.

Seal a `human_wait` request against the exact lecture draft, review MP4, or
decision artifact before pausing. A machine-offline pause requires sealed
verbatim user authority. Both transitions reject any active phase reservation
or active supervisor assignment, so excluded time cannot conceal concurrent
work. Record both pauses separately. Agent thinking, CLI invocation, rendering,
rerendering, coordination, context recovery, and avoidable idle time remain on
the clock. Parallel work counts by the union of active intervals, not by the
sum of agent-seconds.

`upload_ready` means that the exact approved scene sources have produced the
final native-4K episode, mixed and voice-only audio, corrected burned and
sidecar subtitles, required character overlays, final manifest, contact sheet,
hash/decode/duration/loudness/boundary checks, and clean portability evidence.
It does not mean uploaded, pushed, committed, or published. Those external
actions still require their normal authority.

The quantitative retrospective starts only after `upload_ready`. Its budget is
an additional 45 minutes and is not borrowed by production.

The first matched eight-hour calibration envelope is intentionally narrow: six
to seven independently reviewed scenes, at most nine minutes of approved
narration, at most one genuinely new representation family, and reuse of the
series' approved rendering/assets/ending grammar. Eight-to-nine-scene or
ten-to-twelve-minute episodes receive a normalized forecast until a matched
run proves that wider envelope. Initialization must measure those four scope
variables. A larger episode still keeps every quality gate,
but is reported as outside the matched envelope with a normalized forecast;
the supervisor may split delivery only at a real teaching boundary and may
not cut approved content merely to claim eight hours.

## 2. Fixed delivery windows

| Clock window | Limit | Required exit state |
|---|---:|---|
| Initialization and preflight | `T+00:00–00:20` | clean task scope; stable roster and worktrees; production mode; metric policy; episode tracker; open human regressions; tested CLI release; source and asset inventory |
| Lecture truth and approval gate | `T+00:20–00:45` | mathematical argument, beginner prerequisite chain, and provisional narration draft presented for explicit user approval; enter `human_wait` before downstream planning |
| Episode spine after approval | `T+00:45–01:00` | coarse storyboard, scene boundaries, cross-scene identities, fixed ending, batch ownership, risk map, and representative scene selected |
| Representative scene co-design | `T+01:00–02:00` | first-principles design; then exact scene script, listened audio, pronunciation mapping, reader/word timing; then final word-bound plan, screen-text contract, and independent Sol plan pass |
| Representative scene production | `T+02:00–03:30` | rendered voiced candidate; deterministic QC; author five-layer self-review; independent Sol five-layer review; candidate immediately available for user review; fan-out release classified |
| Controlled fan-out and rolling review | `T+03:30–06:00` | remaining scenes produced in waves; every delivered scene independently reviewed as soon as its self-review seals; no unresolved continuity blocker crosses a wave boundary |
| Closure repair window | `T+06:00–07:00` | all scene-level revise findings repaired, rerendered, self-reviewed, independently re-reviewed, and presented for human approval |
| Finalization to upload-ready | `T+07:00–08:00` | approved scenes assembled without internal retiming; final audio, subtitles, overlays, 4K master, independent finishing QC, hashes, manifest, contact sheet, and portability receipt |

These are scheduling limits, not quality allowances. A late stage records an
overrun and triggers the decision rules below; it does not erase evidence,
reset the clock, or weaken a gate.

The lecture gate is intentionally serial. Before the user approves the lecture
draft, do not create the timeline, detailed storyboard, grouping, final scene
scripts, TTS, or animation source. The wait is reported as `human_wait`; the
eight-hour active target assumes either prompt review at this gate or a longer
calendar turnaround. Pre-approval truth work uses `phase=planning` with the
only permitted early purpose, `phase_purpose=lecture_draft`; ordinary detailed
planning is blocked until `episode_spine`.

The lecture approval must consume the exact prior `human_wait` request and
record the verbatim user decision. It also seals the first executable scope
forecast: planned scene count, approved narration minutes, new representation
families, and whether accepted series grammar is reused. The clock classifies
the six-to-seven-scene/nine-minute envelope and exposes a normalized projected
upload-ready time when scope is wider. A bare text saying “approved” without
the pending request cannot advance the episode.

## 3. Representative scene before fan-out

Choose one scene that is central to the episode's visual grammar and has high
novice-causality or mathematical-object risk. Do not choose the easiest title,
transition, or recap scene merely to obtain an early pass.

Also name one risk-anchor scene per batch or genuinely distinct representation
family. Each anchor's detailed plan must pass independent Sol review before its
siblings may enter source authoring. Only the episode representative must reach
a rendered candidate before the ordinary reuse-path fan-out decision; batch
anchors do not create three redundant silent animatics.

Before the representative scene is accepted:

- production WIP is one scene;
- other agents may inventory assets, validate the lecture truth, prepare
  bounded deterministic infrastructure, or inspect precedents, but may not
  implement final scene animation;
- no whole-episode exact audio lock, replicated scene template, or multi-scene
  render fan-out is allowed.

Every fan-out path requires all four conditions on the same exact
candidate:

1. deterministic layout, source, timing, text, audio, and manifest checks pass;
2. the author seals the five-layer self-review;
3. an independent Sol reviewer passes the complete voiced candidate;
4. the user approves that exact candidate as both the representative scene and
   the episode's visual-language release.

Present the candidate immediately after the Sol pass. If the user is
unavailable, first let other owners finish only their already-running safe
risk-anchor plan, audio, asset, or deterministic checkpoint. Then close every
assignment and reservation before entering `human_wait`; while paused, no
agent work continues. No sibling source authoring begins. The one exact-hash
verdict is not requested twice: it is also the
representative scene's final per-scene human approval. A novel visual language,
novel representation family, or lower-cost composition experiment may require
more explicit feedback, but never a second ritual approval of unchanged bytes.

Every later scene still requires its own user review. No scene becomes
approved, committable, or eligible for final assembly before its human verdict.

## 4. Rolling waves and WIP limits

After representative-scene acceptance, plan adjacent scenes in waves of three
to five, but release and review one scene at a time.

- Active implementation/render WIP may not exceed the sealed
  `max_production_agents`; the default is three only on a four-slot host.
- The main Sol acceptance queue may not exceed the independently sealed
  `max_frozen_candidates`; its normal starting value is two.
  When it is full, producers finish evidence or plan/audio preparation but do
  not start new source.
- Each producer owns at most one actively edited scene. Its next owned scene
  may be in plan/audio preparation only.
- At most one unreviewed frozen candidate may wait behind each producer.
- At most one repair may be active per producer. A continuity-blocking repair
  preempts new implementation.
- Only the next wave receives detailed just-in-time narration, audio, and
  visual-plan work. Later waves remain coarse.
- As soon as a scene's author self-review seals, the main Sol reviewer begins
  acceptance review while the producer advances to a safe checkpoint in the
  next owned scene.
- A nonblocking revise is delivered at that checkpoint. A mathematical,
  identity, handoff, user-decision, or continuity blocker interrupts
  immediately.
- Two scenes that repeat the same accepted human or Sol regression stop new
  fan-out until the episode visual grammar and affected plans are corrected.

The supervisor keeps a single ordered board with these states:
`queued -> plan_audio_locked -> plan_sol_passed -> authoring -> rendered ->
self_review_passed -> sol_reviewed -> user_reviewed -> approved -> assembled`.
No chat summary may advance a state.

The executable board uses the same sequence except that the accepted human
outcome advances `sol_reviewed` directly to `approved`; the outcome remains in
the bound release evidence. Use `update-delivery-board` for every transition.
It admits exactly one step, caps implementation WIP and the frozen acceptance
queue at the limits sealed in the delivery clock, and rejects sibling
`authoring` before the representative reaches `approved`.
`phase-start --phase authoring|render`
must bind the same `--delivery-clock` and match the admitted board state.

Every `sol_reviewed` transition first requires
`seal-sol-candidate-pass`. That compiler revalidates the current manifest and
self-review, the applied full-regression attempt, a frontier-tier reviewer,
and the exact Sol model pinned at T0. The representative's `approved`
transition additionally requires `seal-representative-release`, which consumes
that compiled pass plus the exact human outcome and current MP4. A hand-written
approval note cannot release fan-out.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" seal-representative-release \
  --repo-root . --episode "$EPISODE" --scene-slug <representative> \
  --delivery-clock "$DELIVERY_CLOCK" \
  --sol-candidate-pass <sol_candidate_pass.json> \
  --outcome-log <events.jsonl> \
  --output "$EPISODE/review/v2/representative_release.json"

python3 "$SKILL/scripts/pipeline_v2.py" update-delivery-board \
  --repo-root . --clock "$DELIVERY_CLOCK" \
  --scene-slug <scene> --state <next-state> --evidence <exact-artifact> \
  [--owner-agent-id <stable-owner>] \
  [--human-outcome-log <events.jsonl>]
```

For every `approved` transition, `--evidence` is the exact frozen review
manifest and `--human-outcome-log` is mandatory. The command finds the
manifest-bound human pass, verifies the current review MP4 bytes, and stores
that approval in the board. A candidate mutation after approval invalidates
the clock. The representative additionally requires
`--representative-release` for the same manifest, outcome event, and candidate.

`transition-delivery-clock --action checkpoint` also advances exactly one
stage and requires an exit artifact. The `representative_design`, `fanout`,
and `finalization` checkpoints additionally verify the Sol-passed plan,
representative release, and all-scene approval state respectively. Its status
derives the 75-percent schedule warning and stage overrun from active clock
time rather than a chat estimate.

Use one supervisor session, the sealed number of long-lived batch tasks, and
the original scene owner for repairs. Reuse every compatible reusable roster
member before authorizing another identity; a cancelled batch does not cancel
the opened identity. The ceiling is flexible from one through eight, but start
with at most three producers and expand only from compiled evidence. When the
sealed cap has unused room, `authorize-capacity` still requires a fresh sealed
availability snapshot, an exact pending task, zero queued
candidates, at least five measured reviewer-wait minutes, positive cumulative
cost headroom, and no compatible reusable identity. Those measurements must
come from `seal-capacity-evidence`, which binds the current delivery board,
complete token telemetry, active reservations, and their current bytes;
it also proves that the clock, efficiency contract, supervisor, canonical
episode, and reconstructed exact `T0` clock hash share one lineage. Reviewer
wait counts active production time only, excluding human-wait and offline
pauses. A compatible current or restored-retired identity blocks expansion;
restore and reuse it instead. Caller-supplied queue/wait/headroom numbers are
forbidden. `register-capacity` revalidates both availability and capacity
receipts before it may add exactly one new identity. One
evidence-backed worker replacement is the default
episode maximum. A second supervisor session or second replacement is a
root-cause replan trigger, not routine scheduling; repeated identity churn
forfeits the expected context-reuse saving.

An active assignment must leave a durable heartbeat at least every ten active
minutes. `supervisor_watch.py status` lists stale owners under
`health_probe_required_assignments`; the supervisor probes them immediately
instead of silently letting an open timer consume the episode clock. If the
owner is gone, reconcile the exact wrapper within five further active minutes:
seal its last valid checkpoint, mark the interrupted phase abandoned or paused,
and leave unobservable token usage as `unknown`. Never extend a dead wrapper
with thread-wide token deltas, and never start a replacement before the old
ownership and timer are auditably closed.

## 5. Model routing

### Sol owns

- lecture truth, beginner causal chain, episode visual spine, and the
  representative scene's detailed visual plan;
- every independent detailed-plan review and final candidate review;
- broad composition, mathematical-object identity, attention choreography,
  or teaching-causality repair;
- cross-scene visual-language changes, final acceptance, and user-facing
  review recommendations;
- any task whose failure would invalidate several scenes or force expensive
  rerenders.

`Sol` here is a capability tier, not permission to reuse one identity. A Sol
agent that authored or edited the reviewed plan/candidate is recused; the
independent plan or candidate pass must come from a distinct Sol agent ID.
In the eight-hour path the acceptance reviewer is always frontier-tier Sol;
the generic light-reviewer certification route remains available only to a
legacy or separately authorized experiment and cannot advance this clock.

### A lower-cost model may own

- implementation from an already passed detailed plan and exact audio/timing
  contract;
- bounded local code changes with explicit object IDs, timestamps, protected
  regions, and acceptance frames;
- deterministic TTS/ASR orchestration, alignment packaging, rendering,
  extraction, inventories, manifests, contact sheets, and evidence collection;
- local visual polish whose mathematical semantics, stage topology, timing,
  and composition are already frozen.

A lower-cost model may propose a plan, but its proposal has no production
authority until Sol independently passes it.

At Initialization, a model tier is validated for candidate authoring only when
the latest comparable episode has complete scene phase-pair telemetry, zero
automatic-pass-to-human-revise outcomes, and the delivery target. Otherwise
use stable Sol-tier scene owners plus a distinct Sol acceptance reviewer.
Lower-cost models remain limited to deterministic or evidence-packaging work
until that evidence exists, unless the user explicitly declares a new model
experiment; such an experiment uses the novel-path representative gate above
and cannot grant its own plan or candidate pass.

### Mandatory Sol escalation

The first generalized visual or causal failure immediately upgrades the
affected scene to Sol. Generalized failures include:

- confused or inconsistent visual language;
- stage choreography, hierarchy, or composition requiring redesign rather
  than a localized correction;
- a novice causal gap where the result appears without the producing action;
- false mathematical identity, display mapping, or object correspondence;
- a repair whose effects span multiple stage states or neighboring scenes.

On escalation, freeze the current candidate and evidence, stop speculative
patching, and let Sol rewrite the bounded plan and repair contract. The
lower-cost owner may execute mechanical parts only after the new Sol plan
passes. A second generalized failure in that scene makes Sol the implementation
owner through human approval. The same generalized failure in two scenes stops
the wave and triggers a Sol correction of the shared visual grammar before any
further fan-out.

Local overlap, typo, asset-path, easing, or isolated timing defects do not by
themselves force a model upgrade when the repair contract is precise and the
underlying representation remains valid.

## 6. Operational metrics never authorize or block quality

At initialization, bind one user-controlled operational metric policy. Each
metric is independently `off`, `observe`, or `enforce`. The default production
run uses:

- active critical-path time: `observe`;
- cumulative token/cost budget: `enforce`; the user may explicitly select
  `observe` or `off` for a bounded model experiment without erasing usage;
- artifact growth and declared context size: `observe` through the metric
  switchboard;
- agent churn, render count, and unmeasured monetary cost: reported by the
  supervisor as observations until a real telemetry consumer exists; absence
  of telemetry is `unknown`, not a hidden gate;
- mathematical, novice, timing/attention, visual, audio, independent-review,
  and user-review gates: always `enforce` and not configurable as metrics.

An operational warning, missing token telemetry, exhausted token reservation,
or efficiency close failure must remain visible but must not block TTS,
authoring, rendering, repair, review, or finalization while that metric is
`off` or `observe`. It triggers a supervisor decision, not a quality pardon.
Unknown telemetry is recorded as `unknown`, never zero.

Switching a metric mode requires explicit user authority and a new hash-bound
policy. It never rewrites earlier events, refunds usage, or disables a quality
gate.

## 7. No CLI development on the production clock

Initialization pins and smoke-tests one known-good CLI/Skill hash. After `T0`:

- do not add CLI commands, refactor the state machine, migrate schemas, repair
  historical ledgers, or write new enforcement logic;
- do not change animation content merely to satisfy a faulty operational
  metric check;
- log every suspected tooling defect with the exact command, input hashes,
  error, and intended state, then route it to the post-delivery maintenance
  backlog;
- if an operational-metric command fails, record the incident and continue
  under the bound `off`/`observe` policy;
- if a quality-gate command fails, try the pinned last-known-good command and
  continue other independent safe work. Do not claim that scene passed until
  the real gate runs successfully;
- if no valid quality-gate path remains, stop only the affected scene, notify
  the supervisor, and redirect producers to independent scenes. Do not patch
  the CLI during production and do not fabricate a receipt.

Tool maintenance and migration begin after upload-ready or in a separate
explicit maintenance task that cannot mutate the active production contracts.

The pinned preflight smoke suite is run from the Skill `scripts/` directory
before `begin-delivery-clock`, so it cannot become a live production repair
loop:

```bash
python3 -m unittest \
  test_pipeline_v2_governance test_supervisor_watch \
  test_episode_ops test_eight_hour_controls
```

It must be green before authoring. The larger historical compatibility suite
is still run in the retrospective; a missing ignored legacy-media fixture is
reported honestly but does not turn live production into a CLI repair task.

## 8. Quality gates that cannot be compressed

Every scene and final episode retain all of the following:

1. verified mathematical claims, object identities, invariants, and display
   mappings;
2. an audio-only beginner causal chain with prerequisites introduced before
   formal terminology;
3. exact scene script, formal-to-TTS mapping, full audio listening,
   occurrence-level pronunciation checks, ASR comparison, reader subtitles,
   word subtitles/alignment, and bounded timeline drift;
4. a complete word-anchored detailed visual plan covering stage states,
   transitions, attention, clearance, formula memory, screen-text necessity,
   composition, hierarchy, negative space, and visual finish;
5. independent Sol approval of that detailed plan before animation source;
6. real mathematical drivers and nonzero actions, not formula swaps or fake
   motion;
7. deterministic runtime/layout checks including overlap, frame bounds,
   container overflow, subtitle safety, protected mathematical regions,
   transition midpoints, stale objects, and text-source equality;
8. author self-review of layout, mathematical-object truth, timing/attention,
   novice causality, and visual finish against decoded MP4 frames;
9. independent Sol blind-novice and informed five-layer review of the voiced
   MP4, source, plan, timeline, audio, subtitles, and handoffs;
10. repair lineage followed by a fresh self-review and independent review for
    every revise;
11. explicit per-scene user review before approval or animation commit;
12. final assembly without silent scene retiming, plus independent 4K media,
    subtitle, audio, character, boundary, hash, cleanliness, and portability
    QC before upload-ready.

No deadline, cost setting, model experiment, concurrency decision, or user
absence removes one of these gates.

## 9. Timeout decisions

The supervisor checks forecast and exit evidence at every 30-minute boundary
and at each stage boundary.

### Forecast warning

Raise `schedule_at_risk` when either condition holds:

- 75 percent of a stage window is consumed and its required exit artifact is
  not yet in deterministic validation; or
- projected upload-ready time exceeds `T+08:00` by more than 15 minutes.

Respond in this order:

1. preserve and hash the current safe checkpoint;
2. stop optional exploration, speculative variants, duplicate renders, and
   future-wave detailed work;
3. reduce WIP to the scenes closest to an independently reviewable candidate;
4. reuse the accepted representative visual grammar where mathematically
   appropriate;
5. move open-ended design or generalized repair from the lower-cost model to
   Sol;
6. parallelize only independent, already planned work within the WIP cap;
7. split an overlong scene at a real mathematical clearance boundary rather
   than cutting necessary teaching content.

### Stage timeout

At a stage deadline:

- advance only if the required exit evidence actually passes;
- otherwise record the overrun, stop new downstream commitments, and let Sol
  choose one bounded recovery plan with owner, remaining scope, and revised
  forecast;
- never restart the episode clock, reopen passed content without evidence, or
  lower a quality threshold to restore the schedule;
- if the eight-hour target is no longer credible after the bounded recovery,
  report the revised upload-ready forecast and the blocking quality layer to
  the user immediately.

At `T+06:00`, no new scene representation may begin. Unstarted representation
work becomes an explicit schedule failure requiring Sol replan; the remaining
time is reserved for closure and finalization. At `T+07:00`, only already
approved scene inputs may enter assembly. A scene still awaiting independent
or human approval blocks the master; it is not omitted or silently accepted.

## 10. Minimal execution receipts

Keep the CLI-generated authoritative `delivery_clock.json` for the episode
with:

- `t0`, active intervals, pause intervals, current stage, stage deadlines, and
  projected upload-ready time;
- pinned Skill/CLI and metric-policy hashes;
- stable roster, model roles, worktrees, and WIP board;
- representative-scene identity and acceptance hashes;
- current scene artifact hashes, open blockers, escalation owner, and next
  legal action.

`delivery-clock-status` derives the approved scope forecast, normalized
projected upload-ready seconds, next legal stage, and active scene owners from
that receipt. These are forecast controls, not permission to omit blockers or
weaken quality gates.

Append detailed phase, review, render, and metric events to their normal logs,
but derive the current production status from this compact receipt and the
canonical scene evidence. Do not copy the same status manually into several
chat messages or mutable dashboards.

For a user decision, first compile the pending request, pause only after the
phase ledger and roster are idle, and resume from the same clock:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" seal-human-wait-request \
  --repo-root . --episode "$EPISODE" --request-type lecture_approval \
  --artifact <exact-draft-or-review-artifact> \
  --question '<exact decision requested from the user>' \
  --output "$EPISODE/review/evolution/human_wait_request.json"
python3 "$SKILL/scripts/pipeline_v2.py" transition-delivery-clock \
  --repo-root . --clock "$DELIVERY_CLOCK" --action pause-human \
  --reason '<why no safe production work can continue>' \
  --artifact "$EPISODE/review/evolution/human_wait_request.json" \
  --efficiency-contract "$EFFICIENCY" \
  --supervisor-session "$EPISODE/review/v2/supervisor_session.json"
# After the user answers:
python3 "$SKILL/scripts/pipeline_v2.py" seal-user-approval \
  --repo-root . --episode "$EPISODE" --approval-type lecture_draft \
  --artifact <exact-approved-draft> \
  --human-wait-request "$EPISODE/review/evolution/human_wait_request.json" \
  --exact-user-text '<verbatim user decision>' \
  --planned-scene-count <N> --narration-minutes <minutes> \
  --new-representation-families <N> --approved-grammar-reuse true \
  --output "$EPISODE/review/evolution/lecture_approval.json"
python3 "$SKILL/scripts/pipeline_v2.py" transition-delivery-clock \
  --repo-root . --clock "$DELIVERY_CLOCK" --action resume
```

At finalization, `finalize-episode` first marks the progressive production
tracker assembled and writes the canonical completion receipt. Then advance
each already approved delivery-board scene exactly once to `assembled`, using
that completion receipt as `--evidence`. Do not hand-edit the board or skip a
scene. Run the passing portability audit only after the canonical final bytes
are in place. The clock recompiles all three sources, compares the final-video
path and SHA-256 across the completion and portability receipts, and only then
enters `upload_ready`:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" transition-delivery-clock \
  --repo-root . --clock "$DELIVERY_CLOCK" --action upload-ready \
  --efficiency-contract "$EFFICIENCY" \
  --supervisor-session "$EPISODE/review/v2/supervisor_session.json" \
  --completion-receipt "$EPISODE/episode_completion.json" \
  --portability-receipt "$EPISODE/review/portability_audit.json"
```
