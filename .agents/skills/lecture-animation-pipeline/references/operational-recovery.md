# Operational recovery

Load this reference only after a normal episode has produced a concrete local
TTS/ASR overrun, an expired or stale wrapper, or an explicitly authorized
time-governed continuation. These transitions preserve the original evidence;
they are not startup steps and do not permit live CLI development.

## Deterministic local speech and alignment

Deterministic local speech synthesis is not an LLM continuation. In workflow
v2, when a scene already has a sealed independent visual-plan review and fresh
pre-TTS episode readiness,
`phase-start --phase tts --phase-purpose local_synthesis` may continue after an
episode model-token overrun only with an `actor-model` beginning `local:`, the
exact sentinel token reservation `1/0/0/0`, and a bound usage file whose actual
delta remains zero. It still consumes the ordinary TTS active-time envelope,
still requires listening, alignment, narration QC, voiced rendering, and
independent review, and it does not authorize any new model-backed writing or
animation work.

If measured local synthesis shows that the original TTS wall-time envelope is
too small, do not lower synthesis quality or shorten approved narration. Write
a reproducible projection from completed local-TTS durations and approved
character counts, include explicit headroom, then seal
`lecture-animation-local-active-time-replan-v1` against the active efficiency
contract and projection hash. Later local-synthesis phases may pass
`--local-active-time-replan`; the CLI accepts it only for guarded
`tts/local_synthesis`, requires the extension to equal the projection's
recommendation, and requires voice, seed, diffusion steps, CFG, normalization,
approved narration, and review gates to remain unchanged. The original
1,500-second envelope and measured overrun remain visible.

The same rule applies to deterministic local ASR/forced alignment through
`--phase asr --phase-purpose local_alignment`: use `actor-model local:*`, the
same `1/0/0/0` sentinel, explicit zero-delta telemetry, and the ordinary ASR
active-time envelope. ASR text remains timing evidence; approved narration
remains the learner-facing text truth.

## Stale ordinary phase wrapper

After a supervisor assignment has missed its ten-minute heartbeat and the
five-minute reconciliation window, use `abandon-stale-phase` for the exact
single-scene ordinary wrapper. The command checks the stable supervisor
session ID and immutable grant identity rather than the mutable current
session hash, preserves any supplied checkpoint, records active duration only
through the last heartbeat, leaves token usage `unknown`, atomically releases
the reservation, and blocks the vanished assignment. It never applies to a
time-governed overlay or a shared multi-scene wrapper. Reuse or replacement is
legal only after this receipt exists.

## Time-governed video-priority continuation

When the user explicitly authorizes video-priority continuation after the
episode crossed an original model-token or early-work ceiling, use
`lecture-animation-time-governed-budget-override-v1`. It is an
evidence-preserving overlay, never an edit, migration, reset, or replacement
of `lecture-animation-episode-efficiency-contract-v4`. The original contract
hash, canonical ledger revision, pre-existing reservations and event hashes,
and overflow fields are sealed in `original_overflow_snapshot`; later starts
and ends reject mutation or rollback of that baseline.

Create it only with `authorize-time-governed-budget-override`. The command
binds explicit user authority, one active hash-bound parent contract, the v2
supervisor session, and every sealed v2 production batch owning the scenes.
The authority must preserve overage evidence, quality gates, and default task
caps. Scope rows use `PHASE:PURPOSE:SCENE[,SCENE...]` and may cover only
`design`, `authoring`, or `render`; planning, TTS, ASR, review, finalization,
and retrospective are inadmissible. Workflow-v2 authoring/render still require
the exact independent visual-plan review, audio-aligned scene-production
receipt, and post-TTS readiness receipt.

The overlay is observed-only for model tokens: its metric profile sets
`token_budget.mode=off`, `charge_to_parent=false`, and
`telemetry=observed_only`. It has no positive episode or phase token allowance
and never writes the canonical v4 token ledger. It carries positive total and
per-phase active-time allowances of at most four hours and expires within six
hours. Active time, workflow/quality gates, user review, and declared context
limits remain enforced. Observed token deltas are checked against task caps
when available; missing telemetry stays `unknown` and is not charged while
token budgeting is off. No `authorized_overflow_fields` are accepted.

Every start binds the profile path/hash/snapshot, override hash, and exact
scene scope. Every end revalidates those snapshots under lock, writes the full
event only to the independent overlay log, appends a compact index to the
historical central log, releases the reservation, and returns nonzero for an
active-time failure. Closeout reports `override_used`; active reservations,
active-time failures, unfinished scopes, or unfinished batches are
noncompliant. The original v4 ledger and overrun remain immutable.
