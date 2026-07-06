# Skill Evolution And Lessons

Use this file when turning notebook-specific feedback into reusable skill
knowledge.

## Memory Layers

Keep three layers separate:

- draft notes: why a generated attempt was archived;
- episode review records: human feedback, agent feedback, audits, and issues;
- skill references: distilled rules that should affect future notebooks.

Do not copy raw chats or long notebook diffs into the skill.

## Promotion Criteria

Promote a lesson when it:

- prevents a recurring or high-impact notebook failure;
- changes the production direction, exercise philosophy, interaction rules, or
  review gate;
- generalizes beyond one episode;
- captures a non-obvious constraint of Jupyter, widgets, static GitHub viewing,
  or this course's teaching style.

Keep it local when it is only about one draft, one typo, one temporary package
issue, or an unconfirmed preference.

## Where To Promote

- `20-problem-driven-interactive-notebooks.md`: top-level notebook teaching
  philosophy.
- `21-exam-and-concept-alignment.md`: exam abilities and pattern recognition.
- `22-exercise-taste-and-red-flags.md`: exercise design and bad patterns.
- `23-feedback-hint-and-solution-design.md`: hints, feedback, solutions, and
  cell modality.
- `24-notebook-case-library.md`: episode-specific design anchors and pattern
  cards.
- `30-interaction-and-style.md`: widgets, output stability, fonts, plots,
  prose, and interaction levels.
- `40-qc-and-review-gate.md`: automatic audit, review reports, issue queues,
  hard review receipts, issue queues, handoff requirements.
- `41-output-contract.md`: paths, draft/production semantics, Git boundaries.
- `43-review-red-flag-rubric.md`: risk tiers, reverse-burden candidate flags,
  ranked quality sweeps, and review receipt requirements.
- `42-notebook-contract-and-composer.md`: notebook contracts and worker
  boundaries.
- `50-known-failures-and-fixes.md`: abstract standards, concrete failures, and
  reusable pattern keys.
- `60-skill-evolution-and-lessons.md`: meta-rules for maintaining the skill.

## Lesson Template

Use this structure when promoting:

- Source:
- Trigger:
- Failure or observation:
- Principle:
- Implementation pattern:
- QC check:
- Limits:

For `50-known-failures-and-fixes.md`, compress into `Failure` and `Fix`.

## Update Workflow

1. Read the relevant user feedback, draft README, audit report, and issue JSON.
2. Decide whether the lesson is local or reusable.
3. Write the smallest reusable rule.
4. If the lesson changes review behavior, update the red-flag rubric and
   `review_gate.py` thresholds or templates together.
5. Put it in one reference file and add only short cross-checks elsewhere.
6. Run skill validation and any changed scripts.
7. Run `dot_clean` before checking Git status on `/Volumes`.
