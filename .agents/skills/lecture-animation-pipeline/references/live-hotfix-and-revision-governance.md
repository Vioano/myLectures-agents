# Live hotfix and revision governance

Use this contract when production discovers a missing enforcement capability,
or when review/repair begins to repeat instead of converging.

## Authority boundary

Only the canonical V2 CLI may advance delivery-board authority. A handwritten
preview, manifest, nonce, wrapper, or reviewer JSON is diagnostic evidence; it
cannot authorize authoring, rendering, repair, approval, or finalization.

Keep the pinned core immutable after `T0`. A live repair is an episode-local
plugin with:

- one declared blocker and bounded capability;
- pinned core version and exact plugin bytes;
- actual end-to-end canary, not synthetic fixtures alone;
- success, failure, cleanup, and rollback receipts;
- explicit enabled/disabled state in the episode contract;
- no copied scene-specific executor or duplicated authority semantics.

The plugin remains provisional throughout the episode. Retrospective decides
whether to promote it into the core, retain it as optional, or delete it.

## Exhaustive review before repair

Stopping unsafe execution is fail-fast. Reviewing is not. After the first
blocker, continue read-only inspection across mathematics, object identity,
layout, timing/attention, audio/word rhythm, visual finish, evidence, and
infrastructure. Seal:

- all findings currently discoverable;
- the full coverage matrix and evidence;
- explicit unreviewed surfaces and why they remain unavailable;
- one classification per finding: `pre_existing_review_miss`,
  `newly_introduced_by_repair`, or `runtime_only`;
- root-cause clusters, sibling risks, preservation requirements, and
  repair-induced risks.

Do not release individual findings to the author as repair instructions. The
author receives one hash-bound repair bundle only after review exhaustion.

## Circuit breaker

Track contract/infra, scene-source, and media revisions independently. Enter
`ROOT_CAUSE_RESET_REQUIRED` when any threshold is reached:

- four contract, evidence, validator, or infrastructure revisions;
- two failed real executions;
- two detectable author misses;
- two reviewer misses on bytes already available to the prior review.

While tripped, freeze candidate bytes. Do not create another numbered micro
revision. Produce one root-cause report, decide whether the defect belongs to
the scene adapter, hotfix plugin, or pinned core, and replan before continuing.

## Observable progress

Seal a real canary before scene fan-out. It must exercise MathTex identity and
matching transforms, decoded object evidence, exact audio mux, ffprobe frame
count, internal staging, cross-volume promotion, AppleDouble rejection, and
failure-media preservation. If no playable canary exists within the episode's
sealed milestone, trip the same root-cause reset instead of extending the
contract chain.
