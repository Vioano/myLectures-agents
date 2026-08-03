# Historical episode continuations

This file preserves exact recovery contracts for already-sealed historical
lineages. Load only the named block when a current receipt names its exact
schema. Never read this file during new-episode initialization, copy these
exceptions into a new contract, or treat them as general production policy.

## Episode 8 workflow-v1 recovery lineage

For the historical Episode 8 workflow-v1 lineage only, if the original
50-million raw ceiling has already failed before mandatory independent
animatic review is complete, the main supervisor may seal
`lecture-animation-raw-budget-replan-v1` with
`authorize-raw-budget-replan`. This is a narrow continuation overlay, not a
replacement efficiency contract: the original contract, batch hashes,
historical ledger rows, exceeded-budget alert, close failure, and final
process-compliance failure remain unchanged. It is valid only for
`phase=review` with
`phase-purpose=mandatory_independent_animatic_review`, one exact four-scene
production batch, its unchanged author, one distinct reviewer actor-agent-id,
one shared-work key, and named episode-local output paths. At most three keys
may be authorized, with at most 1,500,000 future raw tokens per key and
4,500,000 across the episode, expiring within six hours. Active time,
uncached input, output, reasoning, the review envelope, and task caps receive
no increase. The four scene wrappers must use the same allocation; the locked
episode ledger keeps one shared reservation and one actual. A `revise`
verdict consumes that actual and never refunds or resets the key. Budget
failure is never a quality exemption or permission to grant acceptance.
The overlay bridges only the already-failed episode-wide raw total: every
start and end still checks the unchanged six-million-token review raw
envelope. Completing any wrapper, including a blocked, abandoned, or
revise-producing review, also requires one or more existing
`phase-end --review-output` artifacts. The CLI hashes them into the timer and
event and rejects missing files or paths outside the overlay's allowed output
scope.

Episode 8 has one separate, narrower mandatory animatic-repair continuation
for the case where both the original episode-wide raw and output totals have
already failed. `authorize-animatic-repair-budget-continuation` writes
`lecture-animation-animatic-repair-budget-continuation-v1`; it does not reuse
or relax the independent-review raw overlay. It authorizes exactly two keys:
batch B belongs to `/root/ep8_repair_v03_batch_b` and covers only G006/G008
with at most 1,500,000 raw and 16,000 output tokens, while batch C belongs to
`/root/ep8_repair_v03_batch_c` and covers only G012 with at most 1,500,000 raw
and 8,000 output tokens. The episode continuation total is therefore at most
3,000,000 raw and 24,000 output tokens. Each key binds the unchanged batch
hash, active supervisor production grant, distinct planned verifier, exact
open issue paths/ids/hashes/scenes, one shared-work key, and per-scene output
roots, and expires within six hours.

Use it only with `phase-start --phase repair --phase-purpose animatic_repair
--animatic-repair-budget-continuation ...`. The exact scene wrappers share one
reservation and accounting identity. Only the already-failed outer raw and
output totals are bridged; active time, uncached input, reasoning, task caps,
the ordinary repair envelope, and every quality/review gate remain unchanged.
Every wrapper end, including blocked or abandoned work, still requires the
repaired animatic plus its self-review inside the sealed scene output root,
keeps the issue open for independent verification, and consumes rather than
refunds the key. The original efficiency contract, historical rows, exceeded
alerts, close failure, and final process-compliance failure remain visible.

When the unchanged repair token envelope has also already failed in all four
token dimensions, authorize the companion
`lecture-animation-animatic-repair-token-extension-v1` with
`authorize-animatic-repair-token-extension`. It is valid only together with
its exact parent continuation and inherits the parent's path/hash, key, scenes,
batch, author, verifier, issues, and expiry. Batch B's local caps are
1,500,000 raw, 60,000 uncached input, 16,000 output, and 4,000 reasoning
tokens; batch C's are 1,500,000, 60,000, 8,000, and 4,000 respectively.
Each key may reserve at most 600 active seconds, but receives zero active-time
extension and no task-cap increase. Pass both
`--animatic-repair-budget-continuation` and
`--animatic-repair-token-extension` to the exact repair wrappers. The
companion never creates a second reservation: it follows the parent
reservation and becomes reserved or consumed with it. Its local actual decides
whether this bounded continuation exceeded its authorization, while the
original repair-envelope failure, alerts, episode failure, and close failure
remain unchanged and visible.

There is one non-artifact abandonment path for an unresponsive Episode 8 G012
repair author. `abandon-unresponsive-animatic-repair` accepts the exact active
state, its now-blocked sealed supervisor, three ordered no-response health
checks, and the accepted feedback/issue evidence. A health check canonically
uses `schema_version:
lecture-animation-worker-health-check-evidence-v1`, sequence `1..3`, the old
agent id, `result: no_response`, a nonempty requested action,
`artifact_progress: false`, and `recorded_by: /root` (legacy evidence using
`schema` is read compatibly). Health checks, accepted feedback, and the
accepted issue must live outside the old author's sealed output root. Inside
that root the scanner permits only the exact bound active phase-state path,
`rollout_totals_start.json`, AppleDouble mirrors, and the command's own receipt
path; every other file is treated as attributable progress. Thus an obsolete
or renamed author self-review cannot masquerade as abandonment governance.
Otherwise the command
atomically writes an immutable abandonment receipt and phase event with
`token_observed: false`, `token_source_kind:
unresponsive_worker_unobservable`, and `actual: null`; consumes the old parent
and extension, releases their reservation, preserves both content issues
open, grants no refund, and permanently fences the old state and shared key.
No fake MP4 or self-review is permitted or required. An identical retry is
idempotent only after rechecking every input path/hash and reconciling the
unique event, sealed state, released reservation, consumed parent/extension,
ledger fence, and still-open content issues. Missing or partial writes fail
closed rather than returning success.

`authorize-animatic-repair-replacement` may spend that receipt exactly once.
It atomically creates a fresh supervisor authorizing only
`/root/ep8_g012_replacement_author`, a fresh G012-only production batch, and a
fresh continuation plus companion for verifier `/root/ep8_review_batch_c`.
The first recovery key is
`ep8:g012-animatic-repair:replacement-01`; its independent local admission is
1,500,000 raw, 60,000 uncached input, 8,000 output, 4,000 reasoning, and 600
active seconds, expiring within six hours. For this exact recovery wrapper
only, the parent bridges raw/output while the companion's complete local
allowance admits all four token dimensions and the 600-second task even when
the unchanged episode closure-stage or repair envelopes are already failed.
The phase state and phase end must still expose those base token/active
overflows and their alerts; this is local admission, not a larger base
contract, task cap, refund, or allowance for another key. It inherits the two
unchanged open G012 content issues and does not erase, refund, or convert the
old unknown actual into zero. The allowed author output root must be absent or
an empty directory, remain inside the episode, and contain none of the four fresh
control-plane outputs; each supervisor/batch/continuation/extension output path
must also be distinct and absent. An identical authorization retry rechecks
the original episode, author, verifier, key, output root and output paths,
every sealed hash/contract, the recovery CAS row, continuation/extension rows,
abandonment fence, and old no-refund consumption. A spent receipt with missing
ledger state or any partial output fails closed. Start the fresh wrapper with
the fresh batch, continuation,
extension, and `--animatic-repair-recovery <abandonment-receipt>`. The locked
ledger validates the complete receipt/supervisor/batch/continuation/extension
lineage and consumes the one recovery only when its G012 wrapper ends.

If that exact replacement-01 author is still running but produces no
checkpoint or attributable output, use
`abandon-unresponsive-animatic-repair-replacement`; do not hand-edit its
supervisor or fabricate a third timeout. The command accepts exactly two
ordered `no_response` records followed by
`forced_interrupt_no_checkpoint` with `previous_status: running` and
`checkpoint_present: false`. The first probe's
`requested_at_approximate` must remain approximate and must not be converted
to a precise `requested_at`. It also binds the exact accepted feedback
`review/agent-feedback/2026-07-30-g012-replacement-author-unresponsive.md`,
the exact open accepted issue
`review/issues/agent_g012_replacement_identity_unresponsive_2026-07-30.json`,
the two still-open G012 content issues, and a zero-progress author output
root. That scan permits only the exact bound active phase-state path, its
same-directory `._` AppleDouble mirror, optional exact-root
`rollout_totals_start.json`, and the command's exact receipt path. A same-name
file elsewhere, any other AppleDouble/hidden file, directory, or symlink is
author progress and fails closed. Under one lock it validates and blocks the active supervisor
assignment using the forced-interrupt evidence, abandons the phase, releases
the reservation with `actual: null` and `token_observed: false`, consumes the
replacement-01 parent/extension/recovery without refund, writes one event and
one immutable fence, and preserves all earlier failure state. Identical retries
reconcile every evidence byte, sealed supervisor/state/hash, event, ledger
row, and open issue; partial writes fail closed.
The CLI state path is not self-authorizing: while holding the ledger lock, the
command requires the recovery row `state_path`, reservation `state_path`, and
the reservation/parent/extension `wrapper_state_paths` to equal that exact
absolute path. A copied or renamed state cannot replace the canonical active
state. Before any write, the command also requires zero existing records for
its deterministic event id; an event without its receipt is a partial
transition and fails closed instead of being appended twice.

`authorize-animatic-repair-second-replacement` is the sole consumer of that
second-level receipt. It authorizes only
`/root/ep8_g012_replacement_author_02`, verifier
`/root/ep8_review_batch_c`, and key
`ep8:g012-animatic-repair:replacement-02`, with four fresh control outputs and
a fresh G012 output root. Token caps remain 1,500,000 raw, 60,000 uncached
input, 8,000 output, and 4,000 reasoning. Only this exact hash-bound wrapper
has a 1,500-second local active cap, with sealed soft checkpoints at 300
seconds (`read_complete_and_two_change_plan`), 600
(`source_patch_and_smoke_or_audit_started`), and 1,200
(`render_qc_and_self_review_underway`), followed by a 1,500-second hard stop.
An allocation of 1,501 seconds is rejected. No other wrapper inherits that
time, and the recovery-attempt ledger is permanently bounded at two; there is
no replacement-03.
Before replacement-02 authorization, the lock also reopens the original
batch-C abandonment receipt and revalidates its path/hash, `actual: null`,
`token_observed: false`, and `refund: false`; the original released
reservation, consumed parent/extension, and no-refund fence; and the
replacement-01 recovery row's consumed/no-refund binding to the second-level
abandonment hash.
Read compatibility is narrow: only a valid original-abandonment receipt
authorizing the exact replacement-01 author/key/hash may interpret a missing
`attempt_ordinal` as `1` and missing `soft_checkpoints` as `{}`. Explicitly
wrong values are rejected. Replacement-02 and every other lineage must carry
the explicit ordinal and complete checkpoint schedule.

Episode 8 batch B has one distinct
`independent-review-discovered repair round` for the two defects found only
after the consumed G006/G008 v03 repair was independently reviewed. Its
design authority is frozen at
`videos/0008-mpm-8-cauchy_integral/review/evolution/proposals/independent_review_repair_round_v2.md`
with SHA-256
`69a353138e77455c2b30e7d6adfc387b17b4f4a63d05e7c8058d85df32779d07`.
`authorize-independent-review-repair-round` binds the original batch-lineage
root, the already-consumed parent key and released reservation, both open
issue files, both v03 review reports, both rejected candidates, and complete
v03 source snapshots. The immutable discovery evidence separately binds its
historical reviewer `/root/ep8_review_v03_b`; that identity is not the future
verifier and must never be copied into the new review authority. The round
also freezes authorizer `/root`, reused repair author
`/root/repair_budget_replan_impl`, future independent verifier
`/root/repair_budget_replan_review`, exact scenes G006/G008, a fresh
supervisor, a fresh two-scene production batch, fresh control paths, fresh
scene output roots, and a fresh post-finalization independent-review root.
The v1 proposal and `/root/ep8_g006_g008_v04_author` are rejected rather than
compatibility fallbacks; `/root/ep8_review_v03_b` is accepted only as the
historical discovery reviewer sealed in the exact v03 evidence, never as the
new verifier. The old actual remains
immutable at 12,049,777 raw input-plus-output, 269,861 uncached input, 44,620
output, and 11,860 reasoning tokens, with approximately 3,728 active seconds.
It is never revived, refunded, reduced, or replaced.

The original batch-lineage root—not a new batch id, issue id, thread,
worktree, or shared key—owns the one-shot counter. At most one automatic round
may exist for that lineage. Its single shared reservation admits at most
1,500,000 raw, 100,000 uncached input, 20,000 output, 8,000 reasoning tokens,
and 1,800 active seconds. Thus 1,501 active seconds is valid and 1,801 is
rejected. Both scene wrappers must use the same allocation signature, token
source, baseline, actual, accounting identity, and reservation, as well as the
same actor identity, model, reasoning effort, phase, purpose, role, and
phase-instance ID. Record sealed forward-hash checkpoints at 300, 600, 1,200,
1,500, and 1,800 seconds; each binds the previous checkpoint plus current
source and output snapshots. The 1,800-second record is a hard stop and is
required before a pair of completed artifacts can finalize. Finalization must
reopen and rehash all five exact checkpoint files under the lock, validate
their complete ordered previous-hash chain and source/output snapshots, and
reconcile their hashes with both round state and ledger. An in-memory final
checkpoint reference is not proof of the chain.

Wrapper end records only that scene's artifact result and immutable artifact
snapshots. It must not release the reservation, populate actual usage, consume
the round, close either issue, or refund anything. Only
`finalize-independent-review-repair-round`, given both exact terminal
wrappers, may append the same actual to both phase events, count it once,
release the shared reservation, and consume the lineage round. Artifact
result and budget result remain separate. Unknown token telemetry is
`actual: null`, never fake zero; unknown usage and local overrun still persist,
release, consume, keep both issues open, grant no refund, and return nonzero.
An event without its receipt, a partial control-plane write, early release,
changed source/issue/report/candidate bytes, cloned issue identity, symlink or
path escape, altered retry actual, or mismatched wrapper allocation fails
closed. `record-independent-review-repair-result` accepts only the exact final
receipt path and hash already sealed in round state and ledger, then reconciles
its actual and budget result with the released reservation and exactly two
matching events in both canonical logs. It also requires one sealed review
submission inside the fresh review root, created after finalization, by the
frozen verifier with explicit author recusal. That submission must bind the
exact final receipt, both terminal wrapper hashes, both new candidate hashes,
and evidence for all five hard review layers. Discovery reports, discovery
inputs, pre-finalization files, and artifacts outside the fresh root cannot be
reused as “fresh” review evidence. Any further `revise` is terminal
`root_cause_replan_required`; no automatic r02 exists.

## Episode 9 design-continuation lineage

Episode 9 has one evidence-preserving design continuation for the already
recorded global-spine/batch-contract output overrun. It exists only because the
user explicitly authorized continued production after the exact blocker was
reported. `authorize-design-budget-continuation` seals that authority, the
unchanged active efficiency contract, the immutable failed design event, the
blocker artifact, the episode spine, exactly three batch plans, and the stable
three-owner supervisor roster. It adds at most 6,000,000 raw, 600,000
uncached-input, 90,000 output, and 25,000 reasoning tokens to the design phase
envelope, with zero active-time extension. Outer episode/stage ceilings,
per-task caps, detailed-plan review, audio/timing locks, all five hard-gate
layers, and user review remain unchanged. Every admitted timer records both the
extended envelope and the original failed base envelope; the historical
`PHASE_BUDGET_ENVELOPE_EXCEEDED` event remains immutable, so final efficiency
closeout cannot present the episode as compliant with the original design
allocation. Use the continuation only with the exact Episode 9 member scene,
its fresh production batch, `--phase design`, and
`--phase-purpose scene_detailed_visual_plan_and_audio`. It is not a generic
budget reset or precedent for another episode.

If and only if the first three stable owners have each completed the exact
G001/G004/G007 policy-restoration capsule and all three resulting phase events
record a task-allocation overrun, the supervisor may issue one reconciled
revision with `--parent-continuation` and the three event IDs in scene order.
The revision keeps the original contract and every task failure immutable, but
raises the total additional design allowance to 12,000,000 raw, 1,200,000
uncached-input, 180,000 output, and 50,000 reasoning tokens. It still adds zero
active time, changes no per-task cap, and grants no authoring, render, review,
or quality-gate exception. This is a measured correction for the mandatory
policy-restoration transport cost, not a second reset or a reusable extension.

If those full-history owners are then replaced through the sealed supervisor
replacement workflow and the exact G001/G004/G007 compact revision events each
still exceed the immutable raw task allocation, one final raw-only design
replan may bind the reconciled parent plus those three events in scene order.
It raises total additional design raw allowance to 25,000,000 while leaving
the reconciled 1,200,000 uncached, 180,000 output, and 50,000 reasoning
allowances unchanged. Active time, per-task caps, outer ceilings, and all
quality gates remain unchanged. No further design continuation tier exists.
