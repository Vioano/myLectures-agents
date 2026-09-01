# Episode __EPISODE_ID__ state-supervision shadow-run retrospective

> This report records observed production behavior. This production Session did not optimize the state-supervision system. Diagnosis and system changes belong to the later evaluation Session.

## 1. Production outcome and authority state

- Episode/run:
- Final production outcome:
- Exact final candidate/artifact hashes:
- User-review/finalization/commit status:
- What remains unfinished:

Do not equate machine PASS with user authority.

## 2. Evidence coverage and unknowns

List which sources are complete, partial or absent:

| Evidence source | Path/reference | Coverage | Known gap |
| --- | --- | --- | --- |
| Event log | | | |
| Command/denial log | | | |
| Context-capsule manifests | | | |
| Task/lease/runtime log | | | |
| Time/token/budget log | | | |
| Agent roster/reservations | | | |
| Artifact/consumer lineage | | | |
| Human interventions | | | |
| Annotation-to-capsule delivery | | | |
| Human UI interaction timing | | | |
| Media playback performance | | | |
| Derived metrics | | | |
| Review/finalization evidence | | | |

Missing evidence is `unknown`, not zero.

## 3. Measured production timeline

| Milestone | Started | Completed | Active time | Wait/offline time | Rework | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Initialization | | | | | | |
| Narration approval | | | | | | |
| TTS/audio lock | | | | | | |
| Scene production | | | | | | |
| Independent review | | | | | | |
| Finalization/user gate | | | | | | |

Summarize critical path, concurrency, time since meaningful output and forecast accuracy. Keep observed and inferred values separate.

Also report:

- maximum overlapping author leases and reviewer capacity;
- queue wait, Human/gap wait and time to first reviewable artifact;
- approved media minutes/day, Human minutes/approved minute and tokens/approved
  minute when their denominators are actually measured;
- work invalidated/preserved by route changes and recovery time.

## 4. Human interventions

List every intervention that changed state/protocol handling, not ordinary creative feedback.

| Observation ID | Time | What the user had to do | Why the system/Agent could not proceed safely | Cost/impact | Evidence |
| --- | --- | --- | --- | --- | --- |

Separately summarize normal creative feedback: annotation count/severity,
decision latency, approval reversals, batch versus immediate submission and the
time from feedback creation to its author/reviewer capsule. Do not misclassify
valuable short feedback as noise.

For every state-changing natural-language request, show the Human wording or a
faithful bounded summary, the coordinator's interpreted intent, chosen public
commands/request IDs, latency, observed state effect and whether the mapping was
correct. In particular, verify “加快速度” reached budget/dispatch state and then
produced additional compatible overlapping leases rather than only more nodes.

## 5. Agent-interface friendliness

Assess with evidence:

- Could a fresh Agent identify the authoritative state?
- Did `next` provide one useful action and a convincing `why_now`?
- Were denials actionable without internal CLI/state knowledge?
- Did the Agent need full-state/Skill rereads?
- Were command names and recovery verbs discoverable?
- Did handoff depend on prior chat context?
- Did latency/disconnection lead to duplicate or unsafe attempts?
- Could a fresh Agent operate the fixed hierarchy without inventing states,
  transitions, priority scores or schema?
- Did review returns arrive at an attention boundary instead of interrupting a
  live task, and was rerouting discoverable?
- Did compatible Agents receive distinct reservations when the ready frontier
  required expansion, or did one author serially drain the queue?
- How many extra `explain`, reread, denied-command and retry actions were needed?

Reference observation IDs rather than writing only a general impression.

## 6. Context precision

For representative authoring, review, repair and finalization tasks:

| Task/capsule | Required facts present | Important omission | Irrelevant/repeated context | Version coherence | Leakage/trust issue | Result |
| --- | --- | --- | --- | --- | --- | --- |

Distinguish a deterministic selection defect from a semantic Agent judgment defect.
Judge “minimum sufficient” by omissions, rereads, rework and quality as well as
capsule length; shorter context alone is not success.

## 7. State stability, determinism and isolation

- Identical retries and their operational outcomes:
- Concurrent conflicts and resolution:
- Stale lease/process/worktree/projection incidents:
- Actual versus expected invalidation/blast radius:
- Local failures that affected siblings or parents:
- Replay/restart/cursor recovery behavior:
- Any case where two fresh Agents inferred different legal routes:
- Cross-stage work that ran concurrently without a false phase barrier:
- Deferred review returns, their delivery boundary and eventual assignee:
- Route switches, stable output contracts and preserved out-of-route evidence:
- Human and Agent projections that disagreed about the same authoritative facts:

## 8. Failure and recovery episodes

For each important observation, record the trace without redesigning the system here:

### Observation __ID__: __SUMMARY__

- Starting reliable state and exact versions/hashes:
- Trigger:
- Expected behavior:
- Observed behavior:
- Commands/denials/events:
- Recovery route and attempts:
- Production work preserved/lost:
- Human intervention:
- Final state:
- Evidence references:
- Local hypothesis, explicitly unverified:

## 9. Confounds and emergency changes

Record model changes, service upgrades, manual database/state edits, emergency patches, missing instrumentation or changes to the evaluation protocol during the run.

If any state-system repair was explicitly authorized to unblock production, bind before/after evidence and state that this is not a clean unchanged-system trial.

## 10. Freeze and handoff declaration

- Raw observations complete through:
- Retrospective completed at:
- Evidence index/hash completed:
- System optimization applied by this production Session: `false`
- Unresolved observations:
- Pack status: `evaluation_ready`
- Later evaluator requested scope:

Do not include “changes applied in this retrospective.” Proposed architecture changes are intentionally deferred to the later evaluation Session.
