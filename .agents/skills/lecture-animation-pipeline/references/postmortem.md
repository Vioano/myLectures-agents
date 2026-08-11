# Post-Episode Retrospective Contract

## Trigger And Scope

The exact phrase `复盘一下` selects this workflow. It means: analyze the most
recently finished episode, produce a quantitative-first retrospective, apply
high-confidence improvements to the canonical pipeline, validate them, and
leave a durable local commit. The user does not need to restate which logs,
review records, Git evidence, or efficiency measures to inspect.

Resolve the episode from the current conversation and checkout. If neither
names it, select the newest episode with a valid completion receipt. For an
older episode whose approved master predates the completion-receipt migration
cutoff (`2026-07-24T00:00:00Z`), accept an approved final master plus a passing
portability receipt as legacy completion evidence and label that distinction.
A newer master without a matching completion receipt is `partial`, not legacy.
Ask only when two candidates are equally current.

"Valid" means current-release valid, not merely present. When more than one
approved upload master exists, the newest master by recorded creation time must
have its exact video SHA-256 bound by both the completion receipt and a passing
portability receipt. If either still names an older master, report
`stale_finalization_evidence_for_latest_master` and make `--require-finalized`
fail while preserving the bounded retrospective pack for diagnosis.

This trigger authorizes:

- read-only inspection of the episode, vault note, Git history, current Skill,
  review ledgers, production logs, finalization evidence, and final assets;
- creation or update of
  `review/evolution/postmortem.json` and
  `review/evolution/postmortem.md`;
- scoped changes to the canonical Skill, its references, checkers, schemas,
  tests, and governance paths when the evidence supports them;
- validation and one local commit containing only those retrospective changes.

It does not authorize push, upload, deletion of media or intermediate assets,
worktree removal, rewriting approved episode content, or unrelated repository
cleanup.

## Quantitative Evidence First

Start by running:

```bash
python3 .agents/skills/lecture-animation-pipeline/scripts/pipeline_v2.py \
  episode-retrospective \
  --repo-root . \
  --episode videos/NNNN-slug \
  --output videos/NNNN-slug/review/evolution/postmortem.json \
  --require-finalized
```

The JSON pack is an evidence index, not the final analysis. It must state its
coverage and unknowns before presenting any efficiency claim. At minimum,
report:

1. planned and observed scene counts;
2. outcome, phase, review, repair, human-feedback, and issue-ledger coverage;
3. critical-path minutes, aggregate agent-minutes, concurrency overlap, human
   wait, and phase distribution;
4. input, cached-input, output, and reasoning tokens with the applicable event
   denominator and coverage ratio;
5. avoidable retry time by declared purpose;
6. accepted, rejected, diagnostic, and full review attempts, reviewer switches,
   author self-review capture, human rejection rate, and automatic false-pass
   rate;
7. render/review-media counts and recurring issue patterns;
8. completion/finalization, portability, supervisor, and final-asset evidence.

If a source is absent, write `missing` or `unknown` and retain the denominator.
Never convert missing logs into zero cost, complete coverage, or successful
quality. Chat timestamps and remembered elapsed time are supporting evidence
only; use hash-stamped phase records for measured duration.

This applies to attempt counters as well as time and tokens. If review,
author-self-review, or repair ledgers are absent, their counts, rates, reviewer
switches, and finding averages must be `null`/`unknown_missing_ledger`, not
numeric zero. A retrospective remains mandatory after an episode overrun:
record the overrun on its timer and failed closeout instead of letting the
budget gate suppress the evidence-gathering phase.

Issue taxonomy is evidence coverage too. Report separate coverage ratios for
`pattern_key`, `standard_key`, `source`, `severity`, and `status`; a large
unclassified legacy tail may be described, but it must not be silently treated
as evidence that no recurring aesthetic, narration, or process pattern exists.

For episodes compiled with autopilot v8, the retrospective must also report
the `screen_text_preregistration_experiment` block. Read the canonical
`screen_text_registration_attempts.jsonl` ledger and distinguish:

- proposed literals that reached a terminal gate state;
- keep, revise, and remove decisions;
- deterministic formal blocks;
- total pre-source prevention (`revise + remove + blocked`);
- registered payloads and invalid attempt rows;
- learner-facing presentation-boundary issues later found by the user.
- planned-scene gate coverage, including scenes with zero proposed literals;
- user findings that the gate removed necessary learner-facing visible text.
- escaped payload count and attribution coverage. New human boundary issues
  must list exact literals in `affected_visible_payloads`; if any issue omits
  that list, the exact payload count stays `null` and only a lower bound is
  reported.

Compare these values with
`references/experiments/screen-text-preregistration-v1.json`. Episode 8 is the
pre-change baseline: it has one human boundary issue record containing two
escaped screen-text payloads, but no historical decision ledger. Therefore its
attempt, prevention, and gate-coverage values are unknown, not zero. The first
valid matched later episode must have 100% terminal attempt coverage, 100%
planned-scene gate coverage, zero invalid rows, zero human screen-text boundary
escapes, and zero human overblocking findings. Report how many candidates the
new gate prevented before source authoring and how many scenes legitimately had
zero candidates; otherwise a clean final video could hide either the same
costly repair loop or an unused gate.

## Evidence Reading Order

After the pack is generated, inspect only its named paths first:

1. completion receipt or legacy approved-master evidence;
2. portability receipt and finalization manifest;
3. `review/evolution/*.jsonl` phase, outcome, review, self-review, and repair
   ledgers;
4. human feedback, accepted-agent feedback, issue JSON, and finalization
   experiment logs;
5. supervisor session and task capsule records for handoff/churn questions;
6. storyboard, timeline, narration, audio/TTS/ASR manifests, and source history
   only where the measured bottleneck or quality escape requires them;
7. Git log/diff for when a retry, repair, or migration occurred.

Do not re-read the whole repository merely to sound thorough. Expand from the
bounded index only when a causal claim needs more evidence.

## Root-Cause Classification

Separate symptoms from the layer that allowed them:

- `curriculum_novice_curve`: prerequisites, concept bridges, abstraction order,
  or beginner cognitive load;
- `narration_tts_asr`: script ownership, boundary duplication, pace,
  pronunciation, synthesis, transcription, or subtitle repair;
- `visual_design_authoring`: stage topology, mathematical-object truth,
  visual hierarchy, text density, transition design, or implementation;
- `review_escape`: author/self-review or independent review missed a defect
  later found by the user;
- `repair_loop`: incomplete fix, repair-induced regression, stale evidence, or
  unnecessary rerender;
- `coordination_handoff`: duplicate work, lost context, identity churn,
  blocked roster, or missing ownership contract;
- `finalization_portability`: 4K assembly, subtitles, BGM, sprite/sign-off,
  final QC, canonical asset promotion, or rebuildability;
- `observability`: missing phase, token, attempt, outcome, or source-log
  evidence that prevents a trustworthy conclusion.

For every claimed bottleneck, give: measured signal, evidence path, root cause,
downstream cost, confidence, and the smallest prevention layer.

## Rank Improvements

Rank proposals with four separate fields:

- expected critical-path or token saving;
- recurrence and affected-scene breadth;
- quality risk if left unfixed;
- implementation and maintenance cost.

Prefer the smallest enforceable layer:

1. deterministic checker or runtime assertion;
2. inference, retrieval, or evidence-index improvement;
3. narrow conditional contract or schema field;
4. prose rule only when the failure cannot be represented structurally.

Do not call a change an improvement merely because the Skill grew. Merge or
retire rules that duplicate an existing evidence test or add reading cost
without reducing recurrence.

Apply high-confidence capability fixes during the retrospective. A
high-confidence fix has direct evidence, narrow scope, an executable
acceptance test, and no unresolved teaching or taste decision. Record
subjective alternatives in the report instead of silently choosing for the
user.

## Before/After Validation

Before editing the Skill, preserve a baseline with `snapshot-iteration` when
the historical Skill tree is resolvable. After editing:

1. run the full Skill CLI/unit test suite;
2. run focused regression tests for every changed checker or command;
3. ask a fresh independent subagent to use the raw trigger and relevant raw
   artifacts, without giving it the intended conclusion;
4. verify that it selects the canonical Skill, starts with quantities, exposes
   observability gaps, attributes causes without inventing data, and proposes
   bounded changes;
5. record the candidate hypothesis for comparison on the next matched episode.

A same-episode post-change snapshot proves only that the tooling runs against
the same evidence. It does not prove production efficiency improved; that
requires a comparable later episode or scene batch. `compare-iterations`
therefore reports same-episode quality and efficiency verdicts as
`insufficient_data` even when it preserves numerical deltas; time spent
running the retrospective itself is not a matched production regression.

## Durable Outputs And User Report

Keep one canonical pair per episode:

- `review/evolution/postmortem.json`: deterministic metrics, coverage,
  recurring patterns, completion evidence, and bounded evidence paths;
- `review/evolution/postmortem.md`: human analysis, bottleneck ranking,
  applied changes, deferred proposals, tests, and the next comparison
  hypothesis.

Re-running the retrospective updates this pair rather than creating numbered
copies. Preserve measured event ledgers and approved baselines, not duplicate
media.

The user-facing report follows this order:

1. measured results and coverage;
2. ranked bottlenecks;
3. causal analysis;
4. changes applied to the Skill and why;
5. tests and forward-test result;
6. remaining unknowns and what the next episode will measure.

Do not bury the numbers after a long process narrative.
