---
name: notebook-production-pipeline
description: Project-level workflow for creating, revising, reviewing, and iterating myLectures companion Jupyter notebooks in the PowerPack notebook repository. Use when planning or writing course notebooks from video scripts/storyboards, moving generated notebook drafts toward production quality, auditing notebook interactivity and execution, recording human/agent feedback as future regression checks, or updating the notebook-production skill itself.
---

# Notebook Production Pipeline

Use this skill as the project-level production protocol for the public-facing
PowerPack companion notebooks. It is a living v0 skill: update the references
whenever a reusable teaching rule, notebook failure mode, interaction rule, or
review mechanism is distilled from user feedback or real notebook production.

## Start Here

1. Read `references/00-overview-and-boundaries.md`.
2. Before planning notebook content, read:
   - `references/20-problem-driven-interactive-notebooks.md`
   - `references/21-exam-and-concept-alignment.md`
   - `references/22-exercise-taste-and-red-flags.md`
   - `references/23-feedback-hint-and-solution-design.md`
   - `references/30-interaction-and-style.md`
3. Before writing or revising a notebook, read:
   - `references/10-authoring-workflow.md`
   - `references/41-output-contract.md`
   - `references/42-notebook-contract-and-composer.md`
   - `references/50-known-failures-and-fixes.md`
4. For episodes 0001-0003, or when designing reusable pattern cards, read
   `references/24-notebook-case-library.md`.
5. Before handoff or approval, read `references/40-qc-and-review-gate.md` and
   `references/43-review-red-flag-rubric.md`, run
   `scripts/audit_notebook.py` on the target notebook, and open or create a
   `scripts/review_gate.py` session for the candidate.
6. When promoting project experience into this skill, read
   `references/60-skill-evolution-and-lessons.md`.

## Core Workflow

0. Confirm the working directory is `/Volumes/bocchi/myLectures`. The notebook
   content repository is `数学物理方法PowerPack-Notebooks/`, a nested Git
   repository currently ignored by the outer production repo.
1. Inspect Git status in both the outer repo and the notebook repo. Keep
   unrelated user changes untouched.
2. Identify the target episode, source video script/storyboard, course goal,
   intended reader, and target notebook path.
3. Move unsuitable generated attempts into an episode `draft/` directory rather
   than treating them as production notebooks.
4. Build a notebook contract before code when the work is a new production
   candidate or a rejected-direction repair. The contract must name the main
   student ability, pattern cards, section plan, exercise layers, cell
   modality, interaction budget, feedback design, exam alignment, red flags,
   and validation route.
5. Before authoring, compile an authoring preflight checklist from:
   - episode `review/human-feedback/`;
   - episode `review/agent-feedback/`;
   - episode `review/issues/*.json` with `source: human_review`,
     `source: accepted_agent_feedback`, or `must_check_in_future: true`;
   - this skill's `references/50-known-failures-and-fixes.md`.
6. Design from problem actions first, then choose Markdown, code checks,
   widgets, plots, and explanations. The notebook is an interactive problem
   session, concept diagnostic, exam trainer, and selective visualization aid.
7. Choose the lowest interaction level that serves the exercise. Markdown-only
   concept prompts are valid. Widgets are justified only when they improve
   feedback, structure recognition, or object manipulation.
8. Keep interactivity stable and purposeful. Avoid continuous redraws, noisy
   warnings, uncontrolled output height, hidden widget-state errors, and
   sliders that do not train a problem action.
9. Execute the notebook top-to-bottom with the notebook repo's `uv` environment.
10. Run the automatic notebook audit and save or cite the JSON result in the
   episode review area when the notebook is a review candidate.
11. Start the hard review receipt:
    `scripts/review_gate.py init --repo-root ... --notebook ... --review-id ...`.
    Then run `checklist` and use `template-review` so the reviewer starts from
    the required documents, risk tier, candidate-flag threshold, ranked-quality
    sweep, and regression list.
12. Run an independent review pass. The reviewer must inspect the notebook
    contract, source, executed outputs, interaction stability, exercise
    quality, feedback design, exam alignment, pattern cards, and
    known-regression checklist. The review must also check the presentation
    boundary: student-facing text must not expose production intent, skill
    compliance, review rationale, or widget-engineering workarounds. The
    default verdict is `revise` until enough specific candidate flags have
    been either fixed, explicitly pardoned, or marked not applicable with
    evidence.
13. Submit the review JSON with `scripts/review_gate.py submit-review`. If
    repairs are required, submit fix evidence with `submit-fix`; before
    handoff, run `scripts/review_gate.py status --require-pass`.
14. Record actionable findings under the episode review structure defined in
    `41-output-contract.md`. Write human feedback and accepted agent feedback as
    future regression checks, not just chat notes.
15. After automatic and independent review pass, hand the notebook path,
    executed validation command, audit path/output, issue status, and known
    limitations to the user for final direction. Do not infer final approval
    from an agent pass.
16. Promote only distilled reusable lessons into this skill using
    `60-skill-evolution-and-lessons.md`.

## Strict Notebook Review Gate

This gate applies to every notebook candidate, including small repairs.

The gate has two layers:

- `scripts/audit_notebook.py` checks execution and output hygiene.
- `scripts/review_gate.py` records the hard review receipt: required reading,
  artifact existence, abstract standards, regression checks, candidate red
  flags, ranked notebook-quality sweep, repair evidence, and final pass status.

The review stance is suspicion-first. A clean-looking notebook is not accepted
because the reviewer saw no obvious issue. The reviewer must actively collect
enough candidate flags for the risk tier and close each one by fix, explicit
pardon, or not-applicable evidence. A zero-flag review is valid only for very
small low-risk changes and must say why the threshold was lowered.

The reviewer must build a regression checklist from human feedback, accepted
agent feedback, open/closed issue JSON, and `50-known-failures-and-fixes.md`.
Previously user-found failures are not optional style notes. If the notebook
repeats one, the verdict is `revise` or `blocked`.

The reviewer must audit abstract standards first, then concrete regressions,
then actionable findings:

- course-object alignment;
- problem-driven design and exam alignment;
- pedagogical sequence and exercise design;
- feedback, hints, and solution quality;
- mathematical honesty and visible computational causality;
- runnable top-to-bottom execution;
- output hygiene and interaction stability;
- visual/readability consistency with the course style;
- source/generated/draft boundary correctness;
- hard-gate compliance and issue repair traceability;
- user-facing polish and novice-reader clarity.
- presentation boundary: no creator-intent, review-gate, pipeline, or
  implementation-workaround prose in student-facing notebook cells.

Every finding must include `standard_key`, `pattern_key` when applicable,
requirement reference, evidence location, impact, suggested fix, and status.
Use Markdown audit reports for human critique and JSON issue files for repair
queues.

Every review must also include a ranked notebook-quality sweep. Name at least
the worst three candidates, such as the most confusing exercise, most unstable
output, most decorative widget, noisiest cell, weakest static-viewing fallback,
or least course-aligned section. Ranking forces the reviewer to compare the
notebook against itself instead of writing a polite generic approval.

Passing this gate is not a final content decision. User direction can still
change the notebook philosophy. Keep the skill iterative and expect upcoming
rules to revise this v0 scaffold.

## Reference Map

- `00-overview-and-boundaries.md`: repo boundaries, notebook role, and draft
  semantics.
- `10-authoring-workflow.md`: source-to-notebook workflow and required planning
  artifacts.
- `20-problem-driven-interactive-notebooks.md`: notebook philosophy: video
  builds viewpoint, notebook tests it through problems.
- `21-exam-and-concept-alignment.md`: ability targets, pattern recognition,
  and exam-style concept alignment.
- `22-exercise-taste-and-red-flags.md`: exercise layers, interaction levels,
  and bad exercise patterns.
- `23-feedback-hint-and-solution-design.md`: answer checks, hint ladders,
  solutions, and cell modality.
- `24-notebook-case-library.md`: design anchors for episodes 0001-0003 and
  reusable pattern cards.
- `30-interaction-and-style.md`: widget, output, typography, plot, and style
  rules.
- `40-qc-and-review-gate.md`: automatic audit, independent review, issue queue,
  and user handoff.
- `41-output-contract.md`: canonical notebook repo paths and review-control
  files.
- `42-notebook-contract-and-composer.md`: notebook-local contract for
  abilities, exercise layers, interaction budget, feedback, and review anchors.
- `43-review-red-flag-rubric.md`: reverse-burden review rubric, risk tiers,
  candidate flags, ranked quality sweep, and hard-receipt contract.
- `50-known-failures-and-fixes.md`: abstract standards and concrete notebook
  regressions.
- `60-skill-evolution-and-lessons.md`: how to promote user feedback and project
  observations into reusable rules.

## Tools

- `scripts/audit_notebook.py`: scan executed or source notebooks for cell
  errors, widget-state errors, noisy warnings, raw `interact` usage, unstable
  sliders, and output hygiene risks.
- `scripts/review_gate.py`: create and validate a JSON-state review gate for a
  notebook candidate. Use `init`, `checklist`, `template-review`,
  `submit-review`, `template-fix`, `submit-fix`, and `status --require-pass`.

## Non-Negotiables

- Do not publish a notebook that is merely an AI-generated demo collection.
- Do not replace course goals with flashy widgets.
- Do not use an interaction unless the student action teaches a specific idea.
- Do not make Jupyter mean "every exercise needs code." Static Markdown
  concept prompts are valid when they are the right teaching form.
- Do not hide exam training behind visualization. The notebook must test
  whether the student can use the video's structure in problems.
- Do not present a visualization before the student has predicted, computed,
  or identified what it is checking.
- Do not let repeated warnings, print dumps, or output height changes make a
  notebook unstable.
- Do not explain implementation workarounds, review philosophy, or production
  intent in student-facing notebook prose. Put those details in contracts,
  review reports, issue JSON, code comments, or skill docs.
- Do not commit or present draft notebooks as production notebooks.
- Do not ignore human feedback. Convert reusable human findings into issue JSON
  and future authoring preflight checks.
- Do not hand off a production candidate without a passing hard review receipt,
  unless the handoff explicitly says the gate is blocked and why.
- Keep the PowerPack notebook repo and the video production repo boundaries
  clear.
