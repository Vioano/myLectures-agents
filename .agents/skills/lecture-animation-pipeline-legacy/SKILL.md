---
name: lecture-animation-pipeline-legacy
description: Frozen backup of the pre-migration myLectures V0 lecture-animation workflow and its detailed philosophy, references, templates, and compatibility tools. Use only when the user explicitly asks for the legacy or backup pipeline, or when the canonical lecture-animation-pipeline retrieves a named legacy reference. Do not select this as the normal production entrypoint.
---

# Lecture Animation Pipeline Legacy Backup

This is the frozen backup of the former project-level V0 production protocol.
The canonical entrypoint is `../lecture-animation-pipeline/SKILL.md`. Preserve
this tree for historical reference and compatibility; do not evolve or invoke
it during normal production unless the user explicitly requests the legacy
workflow.

## Start Here

1. Read `references/00-overview-and-route-selection.md`.
2. Choose one audio route:
   - Read `references/10-voice-conversion-workflow.md` for the original-recording + vocal separation + voice conversion route.
   - Read `references/11-tts-workflow.md` for the rewritten-script + TTS route.
3. Before writing or revising a TTS `script.md`, read
   `references/12-script-authoring-feedback-loop.md`.
4. Before any Manim design or code, read:
   - `references/20-math-object-driven-animation.md`
   - `references/30-visual-language-and-style.md`
   - For formula-dense or stage-dense scenes, also read
     `references/42-scene-contract-and-composer.md` and create a
     scene-local `contract.yaml` before final animation code.
5. For unfamiliar visualization problems, read `references/21-visualization-cases.md`.
6. Before rendering or submitting a segment, read:
   - `references/40-production-loop-and-qc.md`
   - `references/41-production-output-contract.md`
   - `references/43-review-red-flag-rubric.md`
   - `references/50-known-failures-and-fixes.md`
7. When planning multiple agents or subagents for scene/episode work, read `references/70-parallel-agent-development.md`.
8. When updating this skill from project experience, read `references/60-skill-evolution-and-lessons.md`.

## Core Workflow

0. Confirm the working directory is `/Volumes/bocchi/myLectures`; video production directories must be created inside `videos/NNNN-slug/`, next to existing lessons. Do not create sibling worktrees such as `/Volumes/bocchi/myLectures-0002-*` for production files.
1. Inspect git status and keep unrelated user changes untouched.
2. Identify the source script, audio route, SRT/alignment, formula list, and target video directory.
3. If starting a new production directory, initialize the actual episode skeleton first: `README.md`, `script.md`, route-specific speaking rules, `formula-manifest.md`, `storyboard.md`, a clearly marked pre-audio `timeline.json`, `experiment-log.md`, `src/theme.py`, `scripts/`, `draft/`, `exports/README.md`, `assets/`, and `references/`.
4. Before writing or revising `script.md`, compile a script-authoring preflight
   from the episode's `review/human-feedback/`, `review/agent-feedback/`,
   `review/issues/*.json` entries with `source: human_review`,
   `source: accepted_agent_feedback`, `applies_to_script_authoring: true`, or
   `must_check_in_future: true`, plus `references/50-known-failures-and-fixes.md`.
   Record the applicable `pattern_key` entries and concrete avoidance choices
   in `experiment-log.md`. If the episode has a local script lint tool, extend
   it with hard regex or structural checks for reusable wording failures before
   synthesizing audio.
5. Build or update `formula-manifest.md` so important formulas from the source script are not lost.
6. Build or update `storyboard.md` and `timeline.json`; timeline is not an SRT translation, but a contract between narration, visuals, audio, character, sonification, and BGM suggestions.
   `storyboard.md` is the human-reviewable explanation of scene grouping and
   visual language. `timeline.json` is the precise animation/audio contract.
   Both must account for stage direction at their own granularity.
   Before writing new visual plans, compile an authoring preflight checklist
   from the episode's `review/human-feedback/`, `review/agent-feedback/`,
   `review/issues/*.json` entries with `source: human_review`,
   `source: accepted_agent_feedback`, or `must_check_in_future: true`, and
   `references/50-known-failures-and-fixes.md`. Record which `pattern_key`
   entries apply and how this shot will avoid them in `storyboard.md`,
   `timeline.json`, scene stage direction, or `experiment-log.md`.
7. Design each shot from mathematical objects first, then choose display mappings, synchronized views, and any media textures.
8. Implement Manim with shared project theme helpers and `uv run manim`; use `GrowArrow` for primary directed mathematical objects.
9. Add or generate sound effects only at mathematical event times.
10. Render per-segment review videos before any final full merge, following the paths, commands, naming, and mux rules in `41-production-output-contract.md`.
11. Extract keyframes into the canonical QC directory and audit for math correctness, visual hierarchy, overlap, typography, color semantics, and fake-animation risk. For Manim scenes with formula/text panels, also run `tools/layout_check.py` through a scene-specific layout audit, save the JSON report under `review/audits/<scene_slug>/`, and treat overlap, out-of-frame, containment, or close-as-issue findings as blockers.
    Contract version 4 scenes must register every coexisting major formula/value
    row as an atomic temporal audit element. One aggregate formula `VGroup`
    cannot prove that its children do not collide. Version 4 also requires a
    derivation-memory comparison window and novice-comprehension checkpoints.
12. Update `experiment-log.md` with operation notes, decisions, failures, fixes, outputs, and QC frames.
13. Before writing final Manim code for a dense, formula-heavy, or
    human-rejected scene, run `tools/animation_preflight_gate.py` for exactly
    one scene slug. For human-rejected scenes use `--risk-tier human-rejected
    --require-component-package --require-per-scene-review`. The preflight must
    pass before render/review work continues; it rejects stale combined review
    references, monolithic source files, missing motion ledgers, missing
    authoring use of regression records, and formula-only visual plans.
14. Before any animation handoff or delivery, initialize or continue a
    `tools/review_gate.py` session for the scene and run the strict animation
    review gate below, using the reverse-burden red-flag ledger in
    `43-review-red-flag-rubric.md`. A self-review is not enough when a
    subagent or independent review pass is available. A review is not accepted
    until `review_gate.py submit-review` succeeds.
15. For explicitly parallel scene or episode work, use the current protocol in `70-parallel-agent-development.md`: branch and file ownership first, with production files kept in this repository.
16. Promote only distilled, reusable lessons into this skill using `60-skill-evolution-and-lessons.md`.
17. After `review_gate.py status --require-pass` succeeds, hand the review
    MP4, QC evidence, source/control paths, audit reports, gate state, and
    fixed issue queue to the user for final viewing. Do not stage or commit
    animation work yet.
18. Only after the user explicitly approves the review output for commit, run validation commands, clean AppleDouble metadata with `dot_clean .`, stage only relevant files, and commit the approved checkpoint.

## Strict Animation Review Gate

This gate applies to every animation task, including a single segment repair.
Do not rely on memory of this skill. Reread the animation philosophy and QC
references from top to bottom before designing, coding, rendering, or declaring
the work ready.

Use `tools/review_gate.py` as the hard receipt for review and repair state:

0. The animation owner first runs `tools/animation_preflight_gate.py` for one
   scene slug when the scene is formula-dense, stage-dense, or previously
   human-rejected. For a previously rejected scene, the required command shape
   is:
   `python3 .agents/skills/lecture-animation-pipeline-legacy/tools/animation_preflight_gate.py --repo-root . --episode videos/NNNN-slug --scene-slug <scene_slug> --risk-tier human-rejected --require-component-package --require-per-scene-review`.
   A failed preflight means the scene is not reviewable yet.
1. The animation owner creates a session with `review_gate.py init`, selecting
   a risk tier. Use `normal` for ordinary scenes, `dense` for formula/stage
   dense scenes, `human-rejected` after user rejection, and `repeat-rejected`
   after repeated user rejection of the same scene type.
2. The reviewer runs `review_gate.py checklist` and must explicitly confirm
   every listed document by path and SHA-256. The required list includes this
   skill, core animation/QC references, and any episode human-feedback,
   accepted agent-feedback, or relevant issue JSON records present at session
   creation.
3. The reviewer writes the Markdown audit report and submits structured JSON
   through `review_gate.py submit-review`. The CLI rejects the submission if
   read confirmations are missing, artifacts are missing, abstract standards
   are not covered, regression records are not checked, or the risk-tier
   quotas for candidate red flags and ranked aesthetic/visual-guidance
   objections are not met.
4. If the accepted review has open issues, the scene status is
   `revision_required` or `blocked`. The animation owner must repair, rerender,
   regenerate QC evidence, and submit `review_gate.py submit-fix`. Every open
   issue must be ticked as fixed or explicitly pardoned with evidence; missing
   issue fixes are rejected.
5. The reviewer then performs another full review round. The loop ends only
   when `submit-review` accepts a `pass_for_user_review_pending` verdict and
   `review_gate.py status --require-pass` succeeds.

`review_gate.py` must persist review-behavior metrics to disk, not only to
chat context. Every accepted or rejected review/fix submission is appended to
both the session ledger
`review/gate/<scene_slug>/<session_id>/review_metrics.jsonl` and the episode
ledger `review/gate/review_metrics.jsonl`. The metrics include candidate
counts, ranked-aesthetic counts, open issue counts, accepted fix/review rounds,
pardon counts, and pardon rate. Use `review_gate.py metrics --session ...` to
inspect the ledger before trusting a pass.

The state machine is also a hard quality gate. A `pass_for_user_review_pending`
submission is rejected if the selected risk tier has too many pardons, an
abnormally high pardon rate, or too few fix/rereview rounds. Human-review and
accepted-agent regression records, plus no-pardon classes such as subtitle
safe-zone violations, formula-in-subtitle-lane, duplicate semantic objects,
lingering objects, slow fade ghosts, ambiguous unowned fills, stray debug
rectangles, PPT-like formula-only derivations, and unvisualized Riemann sums,
cannot be pardoned. They must be fixed, proven not applicable, or left open as
`revise`/`blocked`.

The gate follows "suspicion first": even a polished render must produce enough
specific objections to satisfy the current risk tier. Objections may be fixed,
pardoned, or marked not applicable, but they must be named with evidence. This
keeps taste and visual-guidance review active instead of relying on a reviewer
to notice only obvious red lines.

For difficult, unfamiliar, formula-dense, or visually ambiguous tasks, search
the skill references and existing repository examples before implementation.
Use `rg` to find relevant scene code, stage directions, experiment logs,
handoffs, review outputs, and earlier episode patterns. Reuse the existing
visual language unless there is a recorded reason to depart from it.

The post-render reviewer must be a separate subagent or clearly separate
independent review pass. It must inspect all of the following, not just a
screenshot:

- review MP4, with the relevant voice track unless the task is explicitly
  visual-only;
- layout-check JSON or an explicit reason why no layout-check audit applies;
- Manim/Remotion/source code and mathematical drivers;
- stage direction, storyboard, formula manifest, and experiment log;
- `timeline.json`, SRT, alignment JSON, and audio duration for the segment;
- neighboring timeline segments, visual standards, and transition in/out logic.
- the animation owner's authoring preflight checklist proving that human-review
  findings were read before design/code and converted into avoidance decisions.

Before judging a render, the reviewer must build a regression checklist from
the episode's `review/human-feedback/` records, `review/agent-feedback/`
records, `review/issues/*.json` files with `source: human_review`,
`source: accepted_agent_feedback`, or `must_check_in_future: true`, and
`references/50-known-failures-and-fixes.md`. Previously human-found failures
and coordinator-accepted agent-found failures are not optional style notes. If
the current artifact repeats any such pattern, the verdict must be `revise` or
`blocked` even when no old subagent issue mentions it.

The reviewer must not stop at exact pattern matching. First audit the abstract
standards in `50-known-failures-and-fixes.md`, such as stage management,
ambiguous visual objects, mathematical identity/causality, timeline alignment,
space utilization, visual hierarchy, and pedagogical example adequacy. Then
use concrete known failures and human issue `pattern_key` entries as evidence
and calibration. If a render violates an abstract standard but no concrete
case exists yet, create a new issue JSON with a new `pattern_key`; do not pass
it just because the failure is new.

The review burden is reversed. The default verdict is `revise`, not `pass`.
For every formula-dense, diagram-dense, or previously human-rejected scene, the
reviewer must create a red-flag ledger before deciding the verdict. The ledger
must contain candidate violations for connector ownership, formula typography,
creator-intent text, derivation persistence, frame/chip use, fills/area-like
shapes, visualization adequacy, and beat alignment. A review with no candidate
flags is invalid. Every candidate must be `fixed`, `pardoned`, or
`not_applicable` with evidence; one unclosed candidate means `revise`.

The same review must include a ranked aesthetic/noise sweep before any pass:
`第一丑`, `第二丑`, `第三丑` or equivalent ranked candidates for the ugliest,
noisiest, most visually confusing, or weakest visual-guidance parts of the
render. List at least three candidates even when the render is otherwise close
to acceptable. Each ranked candidate must be `fixed`, `pardoned`, or
`not_applicable` with timestamp/QC/code evidence; a pardon must explain why it
is still clear to a novice viewer, not merely why it was convenient to leave.
For scene contracts, `tools/validate_scene_contract.py` enforces
`review_policy.requires_ranked_aesthetic_sweep: true`,
`minimum_ranked_aesthetic_flags`, and a closed `ranked_aesthetic_flags` list.
A review or contract missing this ranked sweep is invalid.

The reviewer must also verify that the animation owner used the same feedback
before implementation. If there is no authoring preflight checklist, or if the
checklist lists a human-found or accepted-agent-found `pattern_key` without a
concrete avoidance plan, the review verdict is `revise` regardless of the
rendered result.

The reviewer must check every applicable requirement in this skill and its
references, including real mathematical objects, honest display mappings,
shared drivers, minimal representation budget, full-frame temporal occupancy,
formula readability, layout collisions, typography, color semantics, coordinate
grid/axis alignment, unnecessary fills, unnecessary lines, unnecessary frames or
panels, stale labels, updater ghosts, review audio presence,
subtitle/audio/timeline alignment, canonical output paths, and continuity with
adjacent segments.

The review stance is "novice viewer plus extreme aesthetic pickiness." The
reviewer must not assume the audience already knows the mathematical conclusion.
Every narration beat should have a visible cause or consequence at the same
time; every sampled/discrete-to-continuous process should show enough gradual
progression for the viewer to infer the limit; every symbol structure must be
mathematically faithful, including brackets, ellipses, labels, and component
membership. Obvious ugliness, text spilling out of a container, cramped
composition, or a symbol that is technically present but visually misleading is
a review failure.

Findings must identify the violated abstract `standard_key`, any matching
concrete `pattern_key`, the requirement reference, and the concrete location,
such as segment id, timestamp, code path, timeline field, or QC frame. Vague
approval is not acceptable.

The reviewer must write feedback to tracked files inside the episode directory:

```text
videos/NNNN-slug/review/audits/<scene_slug>/<review_id>__<reviewer>__<branch_slug>.md
videos/NNNN-slug/review/issues/<scene_slug>_<review_id>_<issue_id>.json
```

Use the Markdown audit report for human-readable critique and the JSON issue
files for the repair queue. The report must include reviewer, owner, branch,
worktree path when relevant, reviewed commit, review MP4, QC frame directory,
source files, timeline/subtitle/audio files, adjacent segment ids, overall
verdict, an abstract-standards checklist, a concrete-regressions checklist, and
a numbered finding list. Each finding must include severity, `standard_key`,
`pattern_key` when applicable, requirement reference, evidence location, why it
matters, exact fix target, and status. The JSON issue must mirror the finding
so another agent can pick it up without rereading chat history.

This file structure is branch-friendly and worktree-compatible: review reports
are normal tracked source/control files under the episode, while MP4s, audio,
QC frames, and other large generated evidence stay in `exports/`. Branch names
with slashes should be normalized in filenames, for example
`codex/0002-s001` becomes `codex--0002-s001`.

If the reviewer finds any issue, including a small aesthetic problem, unclear
visual language, cramped composition, dead space misuse, awkward transition,
unjustified color, extra fill, extra line, or timing mismatch, the animation is
not deliverable. Revise, rerender, remux audio if needed, regenerate QC frames,
and repeat the review gate until it passes.

When a subagent or group reviewer finds a new failure pattern, the animation
owner or coordinator must decide whether it is reusable. If yes, promote it
from ordinary `source: subagent_review` into the same future-regression layer
as human feedback: write a short note under `review/agent-feedback/`, create or
update a `review/issues/*.json` record with `source:
accepted_agent_feedback`, `origin_source: subagent_review`, `accepted_by`,
`pattern_key`, `must_check_in_future: true`, evidence, impact, and authoring
preflight guidance, then promote the distilled rule to
`50-known-failures-and-fixes.md` or another appropriate reference when it
generalizes beyond the current shot.

Passing the strict review gate is not the final commit gate. After subagent or
independent review returns `pass`, the animation owner must present the review
MP4, QC/contact sheet, audio path, timeline path, source path, audit report, and
resolved issue list to the user for final viewing. Until the user explicitly
approves the output for commit, keep the changes uncommitted and mark the work
as `user_review_pending` or an equivalent non-final status. Do not infer user
approval from subagent approval.

## Reference Map

- `00-overview-and-route-selection.md`: project boundaries, route choice, and required shared artifacts.
- `10-voice-conversion-workflow.md`: original oral recording route copied and split from the existing flow exploration.
- `11-tts-workflow.md`: TTS route copied from the TTS exploration document.
- `12-script-authoring-feedback-loop.md`: script-stage human feedback, hard lint gates, claim responsibility checks, and notebook boundary rules before TTS synthesis.
- `20-math-object-driven-animation.md`: mathematical-object-driven animation philosophy and anti-fabrication audit.
- `21-visualization-cases.md`: standard solutions to visualization philosophy test cases.
- `30-visual-language-and-style.md`: Blackboard Kessoku palette, formula hierarchy, frames/underlines/colors, and screen text rules.
- `40-production-loop-and-qc.md`: timeline, formula manifest, rendering, audio, sonification, experiment log, and final reporting requirements.
- `41-production-output-contract.md`: canonical video directory tree, Manim render commands, review MP4 assembly, QC frames, final stitching, naming, and git boundaries.
- `42-scene-contract-and-composer.md`: minimal scene-local contract and Python composer structure for formula-dense or stage-dense Manim scenes.
- `43-review-red-flag-rubric.md`: reverse-burden review protocol, candidate red-flag ledger, negative examples, and subagent prompt addendum.
- `50-known-failures-and-fixes.md`: issues already encountered in episode 0001 and the accepted fixes.
- `60-skill-evolution-and-lessons.md`: rules for promoting raw project logs into reusable skill knowledge without bloating the skill.
- `70-parallel-agent-development.md`: current, revisable protocol for multi-agent scene and episode development with branch ownership, review handoffs, and production-in-repo discipline.

## Tools (in `tools/`)

Reusable utilities shared across scenes and agents. See `tools/README.md`
for full usage examples.

- `tools/layout_check.py` - Generic collision-check library. Import into any
  Manim scene and pass a dict of elements + `(t_enter, t_exit)` ranges to
  catch OVERLAP and CLOSE issues at peak times before rendering.
- `tools/example_layout_debug_scene.py` - Reference full-scene demo
  showing how to register elements, assign time ranges, render a
  bounding-box debug frame, and run the checker. Use as a template when
  packing more than 4 narrative elements into a single scene.
- `tools/validate_scene_contract.py` - MVP structural validator for
  scene-local `contract.yaml` files used by componentized Python composer
  scenes.
- `tools/review_gate.py` - JSON-state CLI for suspicion-first review loops.
  It enforces required document read confirmations, abstract-standard
  coverage, concrete regression coverage, minimum candidate findings, ranked
  aesthetic objections, issue-file creation, fix submission, and final
  `pass_for_user_review_pending` status before user handoff.

## Non-Negotiables

- Never replace a real mathematical transformation with an invented motion.
- Prefer multiple coherent representations when one view is not enough; preserve object identity across formulas, diagrams, projections, slices, camera moves, and dynamic processes.
- Do not overbuild: use the fewest views, media elements, and synchronized channels that make the concept clear. If one focused window explains the concept honestly, do not split the screen just to show technique.
- Use one shared mathematical driver for synchronized views whenever possible; if a curve, formula, slider, media texture, and sound cue show the same state, they must read from the same parameter or event stream.
- Real media can be used for intuition or humor only when it is bound to a mathematical domain or data stream; a warped photo, video frame, or sound must follow the stated map/computation if viewers are meant to learn math from it.
- Do not let visual clarity justify mathematical lying; use display mappings, local zoom, sampling, opacity, and pedagogical parameters honestly.
- Important formulas from the source script must appear visually even if the narration does not read them aloud.
- Do not overuse screen text. The screen carries mathematical objects, formulas, coordinates, arrows, trajectories, and visual relations.
- Use `shared/style/STYLE.md`, `shared/style/tokens.json`, and local `src/theme.py`; do not invent colors per scene.
- Follow `41-production-output-contract.md` for all new render paths, review MP4s, QC frames, final stitches, and review tracking files.
- Keep `exports/` generated outputs out of git unless the user explicitly asks otherwise.
- Keep production inside the repository root. Branch isolation is Git state, not a separate sibling filesystem tree.
