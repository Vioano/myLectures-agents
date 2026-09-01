# Black-box Agent experience — __RUN_ID__

- Episode: `__EPISODE_ID__`
- Agent/session identity:
- Started at:
- Stopped at:
- Source contamination: `false | true`
- Human hints received: `0`

## One-paragraph verdict

Was the interface friendly enough that a fresh Agent could act without knowing
the implementation? State the answer before details.

## Route taken

| Boundary | System recommendation | Action taken | Result/denial | Was the next legal move obvious? |
| --- | --- | --- | --- | --- |
| Startup | | | | |
| First task | | | | |
| Review return | | | | |
| Route change | | | | |
| Integration/Human gate | | | | |

## Context precision

| Task/capsule | Needed facts present | Missing facts | Irrelevant/repeated facts | Stale/conflicting facts | Did you open a pinned original? |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

For the human-recording replacement, explicitly state whether obsolete
back-half TTS instructions leaked into the capsule and whether the upload,
transcription, alignment and split expectations were sufficiently concrete.

## Attention and interruption

- Did review feedback interrupt a live lease?
- At which boundary did the returned work become visible?
- Human annotation/change IDs observed:
- Exact capsule(s) containing each annotation/change ID:
- Delivery boundary for each: `begin | heartbeat_attention_boundary | review_context | not_seen`
- Event-log evidence (`seq`, `event_type`, `interrupt_active_lease`):
- Did Human UI input arrive during live work, after the fluid task completed, or only after an explicit reopen?
- Did the system force you to remember work not in the current capsule?
- Did you poll or reread because the interface did not establish confidence?
- Were token-consuming actions productive, duplicated or merely status theatre?

For every Human UI note or decision change, cross-check three durable layers:
the annotation/change event, the signed capsule `annotation_ids` / context block,
and what you actually acted on. A UI-only label is not evidence of delivery.

Treat every open Human annotation as authoritative, potentially meaningful
feedback. Do not silently classify short, ambiguous, repeated, or test-probe
input as noise and do not omit it from the delivery count. Instead, report it
as `actionable`, `needs_clarification`, `possible_duplicate`, or
`protocol_probe`, while preserving the exact annotation ID and text. Only an
explicit Human withdrawal may remove an annotation from later attention
contexts.

## Denials and recovery

For each denial, copy `code`, `failed_invariant`, `allowed_next` and whether the
recovery could be followed without implementation knowledge.

## Determinism and ambiguity

- Repeated read-only call(s):
- Same normalized answer: `yes | no | not tested`
- Could another fresh Session reasonably choose a different legal task?
- Ambiguous words, states, hierarchy or verbs:

## Files read

List every file opened outside stdout JSON. Mark each as mission, task-bound
reference, generated artifact, or accidental/forbidden read.

## Friction inventory

| Severity | Exact moment | Expected affordance | Actual experience | Suggested interface-level repair |
| --- | --- | --- | --- | --- |
| | | | | |

## What should remain unchanged

Name any constraints or projections that reduced guessing or protected focus.
