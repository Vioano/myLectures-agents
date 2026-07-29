# Evidence-Driven Evolution

## Replace Rule Accumulation With A Lifecycle

Do not turn every complaint into another permanent paragraph. Record the production outcome first, measure recurrence and reviewer misses, then change the smallest enforceable layer.

Use this lifecycle:

1. `observed`: one human or accepted-agent finding exists as an outcome event.
2. `candidate`: the pattern has a stable name, scope, and evidence location.
3. `active`: the pattern is severe enough or recurrent enough to compile into scene profiles.
4. `calibrated`: production data shows the rule catches real failures with acceptable time cost.
5. `merged` or `retired`: the rule duplicates a broader rule, produces noise, or fails to reduce recurrence.

The registry contains active rules. Raw examples remain in episode issue logs and historical review artifacts; they are retrieved by relevance instead of copied into the registry.

## Two-Speed Evolution During Production

This episode is also a V2 experiment, so evolution cannot wait until production ends. Use two layers:

1. **Immediate live policy:** every human or accepted-agent issue enters `review/issues/*.json`; `compile-profile` rebuilds the scene's hash-bound `active_policy.json`. Old manifests become stale before the next repair review. This is the fast regression loop.
2. **Global capability change:** edit the Skill, CLI, or rule registry only when the issue reveals a missing class of evidence or checker. Snapshot before the change and evaluate it on the next matched batch. This avoids rewriting hundreds of lines for a one-scene symptom while still activating every human correction immediately.

Never postpone a human regression until the next episode. Never promote every concrete symptom into another global paragraph.

## Promotion Gate

Promote a candidate only when all conditions hold:

- one blocker escaped to human review, or the same pattern recurred in at least two scenes;
- applicability can be stated as tags or a narrow structural condition;
- the rule has a concrete evidence contract, deterministic check, or both;
- a positive or negative benchmark can be located in the existing timeline/storyboard/source/review history;
- the rule does not duplicate an existing active rule.

Prefer these interventions in order:

1. strengthen a deterministic checker;
2. improve profile tag inference or history retrieval;
3. add a narrow conditional rule;
4. add prose only when the failure cannot be represented structurally.

## Metrics

Record one `events.jsonl` row after human review. Track at least:

- author and reviewer model/version;
- automatic and human verdict;
- reviewer findings, human findings, review rounds, render count, and elapsed minutes;
- `caught_by`: author, machine, reviewer, or human;
- pattern keys and exact manifest hash.

The report computes:

- human rejection rate;
- false-pass or pardon rate: automatic pass followed by human revise;
- zero-finding pass rate;
- findings per reviewer pass;
- accepted and rejected author self-review attempts, author findings plus machine-gate findings caught before independent handoff, and independent findings that escaped the immediately preceding accepted self-review;
- average review rounds, renders, and minutes;
- review attempts rejected by the CLI and average findings per attempt;
- recurrence and miss counts by pattern;
- reviewer health by model.

Do not rely on the manually entered `minutes` field for iteration comparisons. Use hash-stamped `phase-start` / `phase-end` records so authoring, repair, review, rendering, TTS, ASR, and human wait can be separated. Token-expected phases must also reach full token-observability coverage before claiming token-efficiency gains. Compare total observed tokens, uncached input tokens, phase token distribution, and tokens per active minute alongside wall time.

## Skill Iteration Baselines

Before changing the skill, snapshot the current production window. After producing a comparable scene batch with the new skill, snapshot again and compare the two files. Keep these under `review/evolution/baselines/` so later sessions do not depend on chat context.

Minimum comparison axes:

- quality: human rejection rate, automatic false-pass rate, and findings caught before human review;
- efficiency: measured authoring, review, repair, and total minutes; review attempts per scene; reviewer switches;
- repair efficiency: immediate next-candidate pass rate, incomplete-fix recurrence, repair-induced regression rate, and changed-artifact breadth per finding;
- review discovery efficiency: delayed `preexisting_missed` findings after a prior pass, first-round finding yield, and human false-pass rate;
- observability: whether human outcomes, phase timing, reviewer sessions, manifests, and source-log hashes exist.

Treat each axis independently. A change that lowers review time but raises false passes is not an improvement. A change with no matched human outcomes is `insufficient_data`, not a success. Use similar scene counts and risk tiers; otherwise record the comparison as exploratory.

Diagnostic review attempts and full regression attempts are separate metrics. Diagnostic checks should reduce repeated context and token cost, but they never count as final passes. Track how often diagnostic repair succeeds, how often the subsequent full review finds regressions, and whether persistent reviewer sessions reduce reviewer switching without increasing false passes.

Do not infer issue lineage from chat after the episode. Every revise finding carries a root issue ID and one of `initial_or_unknown`, `preexisting_missed`, `repair_induced`, `incomplete_fix`, or `new_unrelated`. The repair contract and repair response bind that classification to exact manifests. A later reviewer may correct the classification only by opening a new finding with concrete cross-version evidence; silent reclassification is forbidden.

Do not cap full reviews at an arbitrary number. Use `choose-review-mode` to route local unchanged-contract repairs to diagnostics and material changes to full four-layer review. If a scene reaches three full reviews, treat that as evidence that the plan, live policy, or authoring contract is wrong; require root-cause re-planning rather than relaxing review coverage.

Do not target a fixed rejection count. A healthy pipeline may pass a strong scene on the first attempt. Treat an agent as anomalous when it repeatedly passes with no findings while humans still reject, or when its false-pass rate exceeds the configured threshold after enough samples. The review CLI must then demand a recorded calibration recheck.

Author self-review is a prefilter, not independent certification. Measure its escape rate: later independent or human findings whose layer and timestamp were declared clean by the author probe. CLI-selected anchors, distinct hash-bound frames, non-duplicated numeric claims, and open-blocker conflict checks reduce self-confirmation, but the episode acceptance reviewer remains mandatory.

Review metrics are valid only when reviewer authority is valid. Contract v5 records `acceptance` versus `diagnostic_support`, binds the episode-spine main agent, and records per-scene pending repairs after accepted revise attempts. Report wrong-authority attempts, unresolved-policy passes, stale concurrent writers, and missing repair bindings as separate CLI rejection classes.

Keep the file state backend while the process-safety stress test passes on the production host and state writes remain low volume. Reconsider SQLite/WAL when coordination becomes a shared multi-worktree queue or one logical transition must atomically update more than the review-attempt/session pair.

## Compaction

During production, keep exactly one canonical `review/v2/<scene>/current/` workspace for derived MP4s, QC frames, diagnostic frames, and review JSON. Replace these files after each candidate freeze. Preserve attempt history in `review_attempts.jsonl`, `author_self_review_attempts.jsonl`, manifests referenced by approved human outcomes, and issue records, not in dozens of `vNN` media directories. `prepare-review-workspace` creates this layout, and progressive `freeze-review` rejects noncanonical manifest destinations.

At an episode boundary:

1. Read `postmortem.md` and run `episode-retrospective` to create the bounded
   quantitative evidence pack.
2. Run `evolution-report` when a deeper per-reviewer or per-pattern table is
   needed.
3. Rank patterns by human misses, recurrence, critical-path cost, and quality
   risk.
4. Promote only the few highest-value candidates.
5. Merge rules with the same evidence test and applicability.
6. Retire rules that have not triggered, are consistently marked not
   applicable, or add review time without catching failures.
7. Re-run profile compilation tests so a typical scene still receives a small
   rule subset.

The goal is not a larger skill. The goal is a shorter path from a newly observed failure to a measurable checker, and then removal of checks that no longer earn their cost.

## Reusable Visual Grammar

The existing production corpus is the visual grammar store:

- `storyboard.md` records the intended teaching action and stage design;
- `timeline.json` records mathematical objects, drivers, timing, and review state;
- `src/scenes/<slug>/` records implementation and contract details;
- review MP4s, QC frames, and issue logs record whether the design worked.

Search this corpus live. Store only record identifiers and reuse decisions in new scene plans. Never copy old media or source into a parallel pattern library merely to make it searchable. A disposable index is allowed for speed and must be reproducible from repository files.
