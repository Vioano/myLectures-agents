# Skill Evolution And Lessons

Use this file when turning video-specific experiment logs into reusable skill knowledge. The goal is to make the skill wiser without turning it into a raw diary.

## Memory Layers

Keep two layers separate:

- **Project experiment logs**: raw, local, chronological records in a video directory, such as `videos/NNNN-slug/experiment-log.md`. These may include commands, render paths, failed attempts, screenshots, user feedback, and uncertain reflections.
- **Skill references**: distilled, reusable rules that should guide future agents across videos. These must be concise, transferable, and tied to a production decision, QC check, route choice, failure mode, or visualization philosophy.

Do not move raw logs wholesale into the skill. Link or cite the source video/segment if useful, then write the distilled lesson.

## Promotion Criteria

Promote a lesson into the skill when at least one is true:

- It prevents a recurring or high-impact failure.
- It changes the animation philosophy, visual hierarchy, QC checklist, audio route, or workflow.
- It generalizes beyond one render or one scene.
- It exposes a non-obvious production constraint, such as Manim behavior, style consistency, route choice, or review technique.
- It provides a reusable visualization solution to a class of mathematical objects.
- It affects how future agents should plan, implement, review, or commit work.

Keep a note in the project log when:

- The observation is only about one local asset, path, render attempt, or machine state.
- The lesson is promising but not yet stable.
- The user preference may be episode-specific.
- The issue is already covered by the skill and only needs a source example.

## Where To Promote

Choose one target file:

- `20-math-object-driven-animation.md`: general visualization philosophy, real mathematical drivers, display optimization, shared drivers, media-bound transforms, sonification logic, and anti-fabrication audit.
- `21-visualization-cases.md`: reusable standard solutions to specific mathematical visualization problems.
- `30-visual-language-and-style.md`: palette, typography, formula hierarchy, text discipline, layout, and style semantics.
- `40-production-loop-and-qc.md`: required artifacts, timeline, experiment log, render process, audio workflow, and QC checklist.
- `41-production-output-contract.md`: canonical directory tree, output paths, naming, render commands, review muxing, QC extraction, final stitching, and source/generated git boundaries.
- `50-known-failures-and-fixes.md`: concrete failure modes with accepted fixes.
- `60-skill-evolution-and-lessons.md`: meta-rules for skill maintenance, promotion criteria, and reflection queues.
- `70-parallel-agent-development.md`: branch ownership, file ownership, review handoffs, integration order, and generated-output ownership for multi-agent work.

If a lesson changes several files, write the core rule in the most natural place and add only short cross-checks elsewhere. Avoid duplicating the same paragraph.

## Lesson Template

Use this structure for promoted lessons:

- **Source**: video id, scene, date, or user feedback context.
- **Trigger**: when this lesson applies.
- **Failure or observation**: what went wrong or what became clear.
- **Principle**: the reusable rule.
- **Implementation pattern**: what future agents should do.
- **QC check**: how to verify the lesson was followed.
- **Limits**: when not to apply it.

For `50-known-failures-and-fixes.md`, compress this into `Failure` and `Fix` sections.

## Reflection Queue

Use a short queue inside the project experiment log for ideas that are not ready to become rules. Promote only after review, repetition, or clear user confirmation.

Reflection queue item format:

```text
- Observation:
- Evidence:
- Risk if ignored:
- Proposed skill target:
- Promotion status: candidate | accepted | rejected
```

Do not keep a long reflection queue inside the skill. Once accepted, rewrite it as a rule. Once rejected, leave it in the project log.

## Do Not Include

Do not add these to the skill:

- Long command transcripts.
- Temporary render paths except as short source references.
- One-off output path variants unless they change the reusable output contract.
- Large screenshots or raw media.
- One-off emotional reactions without a reusable rule.
- Unverified personal preferences.
- Duplicate copies of project `experiment-log.md`.
- Detailed branch history or local machine cleanup notes unless they change the reusable workflow.

## Skill Update Workflow

When updating this skill:

1. Read the relevant project `experiment-log.md`, user feedback, and affected skill reference files.
2. Decide whether the lesson should stay local or be promoted.
3. Write the smallest reusable rule that changes future behavior.
4. Put the rule in the correct reference file.
5. Add a failure mode to `50-known-failures-and-fixes.md` only when there is a clear failure and accepted fix.
6. Add or update QC checks in `40-production-loop-and-qc.md` when the lesson must be verified every segment.
7. Run validation, clean AppleDouble metadata, stage only skill files, and commit.

## Forward Testing

For important philosophy changes, test the skill with a fresh prompt or subagent:

- Ask for a solution to a related but not identical visualization problem.
- Do not leak the expected answer.
- Judge whether the new answer follows the promoted rule without overfitting to an old example.
- If it fails, refine the skill rule, not the test prompt.
