# Short black-box tests

Short tests optimize for operation coverage and bug exposure, not for producing a lecture episode.

## Blind operator contract

- Start every operator in a fresh Session with no inherited turns.
- Give only a natural task, public service endpoint/CLI and side-effect boundary.
- Public `help`, `next`, `explain` and structured errors are allowed.
- Design documents, source, hidden expected path and previous results are forbidden.
- Run in a disposable state/artifact sandbox; never reuse real episode authority.
- Audit operator tool calls. Reading forbidden design/source material contaminates the run.

## Test families

1. Discoverability: find the next legal action and complete a tiny happy path.
2. Context precision: required rule present, irrelevant history absent, versions coherent.
3. Command safety: idempotent retry, malformed input, stale expected version and permission denial.
4. Concurrency: two writers, reordered independent commands and expired ownership.
5. Lineage/change: TTS-only change, semantic change, stale consumer and partial invalidation.
6. Recovery: dead worker, stale lease, projection drift, policy no-exit, bad plugin and service restart.
7. Handoff: a fresh Agent resumes from state without prior chat.
8. Trust/security: prompt injection in artifacts, cross-scope access and unauthorized side effects.
9. Fluid dispatch: cross-stage work, independent review and attention-boundary
   return tickets without forced interruption.
10. Route flexibility: replace a production method behind a stable deliverable
    contract while preserving lineage and sibling isolation.
11. Fixed multi-scale model: exercise content and deliverable projections while
    proving that containment never becomes an implicit dependency or a
    Session-authored state schema.

## How to expose defects

- Do not tell the operator which fault was injected.
- Repeat critical fixtures across fresh Sessions and compare normalized routes, not prose.
- Randomize entity IDs and scenario order.
- Keep a hidden deterministic oracle for invariants and expected blast radius.
- Record minority routes and route entropy; do not report only the successful majority.
- Mutation-test the interface by removing one `why`, hash, recovery hint or reference binding and confirm that the measured experience worsens.
- Compare equivalent fixtures against the legacy CLI where possible.

## Short-test success is not long-run proof

Short tests can prove local correctness, discoverability and bounded recovery. They cannot prove multi-hour stability, real production throughput, long-history compression, reviewer capacity, creative quality or final user experience. Those belong to an Episode long shadow run.

The pre-Episode-13 suite is stored under
`results/2026-08-30-pre-ep13/`. Its stress report is machine-readable; blind
operator workspaces retain the exact missions and final disposable state so a
later evaluator can distinguish a system defect from an operator judgment.
