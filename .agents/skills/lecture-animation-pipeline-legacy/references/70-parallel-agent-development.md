# Parallel Agent Development

This protocol is the current working agreement for multi-agent production in
`/Volumes/bocchi/myLectures`. It is intentionally revisable: update it when a
real parallel run reveals a better boundary, merge pattern, or cleanup rule.

## Default Mode

Use the main checkout, `/Volumes/bocchi/myLectures`, for production work,
continuing an existing production thread, final integration, final review
renders, and canonical handoff notes.

Use Git branches for isolation. Do not create a temporary worktree just because
a branch is needed. A normal single-agent task can create, switch, commit, and
merge branches in the main checkout.

Production files must remain inside this repository. Do not create sibling
production directories or clones such as `/Volumes/bocchi/myLectures-0002-*`.
Each video remains under `videos/NNNN-slug/`.

## Branch And Task Boundaries

Each parallel agent gets a task branch and a narrow task boundary. Name branches
by owner and scope, for example:

```text
agent/s032-s033
agent/s034-s035
agent/0002-tts-timeline
```

Before assigning agents, write or update a short ownership map in the episode
handoff, `experiment-log.md`, or review notes. The map should state:

- branch name.
- scene or episode range.
- files the agent may edit.
- shared files the agent should avoid unless explicitly assigned.
- required render, QC, or validation proof.

Prefer scene-local files for parallel work. Shared files such as
`timeline.json`, `formula-manifest.md`, `pyproject.toml`, `uv.lock`, `lib/`, and
`shared/` should be owned by the coordinator or by exactly one assigned agent.

## Scene Package Ownership

For componentized Manim scenes:

- `contract.yaml` is owned by the coordinator or designated stage planner.
- `composer.py` is owned by the integration owner.
- `layout.py` may be edited only by the stage/layout owner.
- `drivers.py` may be assigned to a math-driver owner.
- `objects.py` or component files may be split by object family.
- `beats.py` may be split by explicit beat id ranges.
- `audit.py` may be owned by the reviewer or integration owner.

Low-cost or external agents should receive a task file that states:

- allowed paths;
- object ids or beat ids they may touch;
- forbidden files;
- acceptance commands;
- required proof artifacts.

They must not decide the full scene composition, rewrite visual direction, or
modify `timeline.json`, `formula-manifest.md`, shared style, or composer code
unless explicitly assigned.

Example narrow task:

```yaml
task_id: t_s014_objects_square
assignee_model: low_cost
branch: agent/s014-square-objects
scene: s014_s018_local_square_transform
allowed_paths:
  - videos/0000-demo/src/scenes/s014_s018_local_square_transform/objects.py
  - videos/0000-demo/src/scenes/s014_s018_local_square_transform/tests/test_objects.py
forbidden_paths:
  - videos/0000-demo/timeline.json
  - videos/0000-demo/formula-manifest.md
  - videos/0000-demo/src/scenes/s014_s018_local_square_transform/composer.py
  - videos/0000-demo/src/scenes/s014_s018_local_square_transform/contract.yaml
inputs:
  - videos/0000-demo/src/scenes/s014_s018_local_square_transform/contract.yaml
  - videos/0000-demo/src/scenes/s014_s018_local_square_transform/layout.py
  - videos/0000-demo/src/scenes/s014_s018_local_square_transform/drivers.py
deliverables:
  - implement make_source_square
  - implement make_transformed_square
  - ensure returned objects fit assigned zone
acceptance_commands:
  - uv run python .agents/skills/lecture-animation-pipeline-legacy/tools/validate_scene_contract.py videos/0000-demo/src/scenes/s014_s018_local_square_transform/contract.yaml
  - uv run pytest videos/0000-demo/src/scenes/s014_s018_local_square_transform/tests
```

For animation review, use tracked audit reports rather than chat-only feedback:

```text
videos/NNNN-slug/review/audits/<scene_slug>/<review_id>__<reviewer>__<branch_slug>.md
videos/NNNN-slug/review/issues/<scene_slug>_<review_id>_<issue_id>.json
```

The audit report belongs to the episode, not to a temporary checkout. If a
reviewer works from an approved temporary worktree, the report must still record
the source branch, reviewer branch, worktree path, reviewed commit, and artifact
paths. After integration, regenerate accepted review outputs from the canonical
checkout when practical and add a new audit report for the integrated artifact.

## Recommended Flow

From the canonical checkout:

```bash
cd /Volumes/bocchi/myLectures
git status --short
git switch main
git pull --ff-only
git switch -c agent/s032-s033
```

On the task branch:

```bash
git status --short
# edit only assigned files
dot_clean .
git status --short
git add <assigned files>
git commit -m "Add S032-S033 animation scene"
```

For integration:

```bash
cd /Volumes/bocchi/myLectures
git status --short
git switch <integration-branch>
git merge agent/s032-s033
```

After the merge, run the relevant render/QC from the integrated checkout and
record the canonical output paths in the episode log or handoff.

## External Agents

External CLI agents or subagents should be read-only by default. If an external
agent must write production files, first switch this repository to the assigned
task branch and explicitly limit the allowed paths.

External agents must not own full-shot visual direction for lecture animation.
The coordinator owns composition, stage ownership, mathematical object identity,
reference frames, and visual hierarchy. A Qoder/Pi/cheap-model worker may
implement a bounded local object, mechanical Manim code, render/QC extraction,
or a narrow repair only after the coordinator has written a concrete stage
contract.

Before assigning a writing external animation task, the coordinator must provide
all of the following in the prompt or stage file:

- exact scene group, segment window, and allowed source/control files;
- one current stage direction that states canvas ownership by time interval;
- allowed mathematical objects and forbidden extra objects;
- reference frame target or precise final-frame contract;
- which objects must be cleared before each handoff;
- explicit typography/underline/frame rules from `30-visual-language-and-style.md`;
- current human-feedback and accepted-agent-feedback `pattern_key` entries that
  must not recur;
- stop conditions: if composition, object ownership, or visual hierarchy is
  ambiguous, the worker must stop and ask instead of inventing a layout.

Do not give prompts like "design this scene", "make a nice animation", or broad
storyboard paragraphs to an external worker. These prompts delegate the
director role and have produced unusable topic maps, crowded label piles, stale
objects, and arbitrary underlines. If an external worker returns a render that
fails stage ownership or math-object-driven direction, stop repairing that
render and return to coordinator-owned redesign; do not keep prompting the
worker to patch the bad composition.

Use a temporary worktree only when the user or coordinator explicitly approves
it for a concrete concurrency problem that cannot be handled by ordinary branch
handoff. Even then, do not treat that checkout as a second production source of
truth; merge the branch back into `/Volumes/bocchi/myLectures` and regenerate
accepted review/final outputs from the integrated checkout when practical.

## Output Ownership

Generated outputs from an external or temporary checkout are proof artifacts,
not the canonical final output. Agents may render local review clips or QC
frames to demonstrate progress, but the integrated checkout should produce the
accepted review/final artifacts when practical.

Do not commit generated `exports/*` unless the user explicitly asks. If a
temporary render matters, record its path and timestamp in the handoff or
experiment log, then regenerate from the integrated checkout after merge.
Commit tracked audit reports, handoffs, assignments, and issue JSON files when
they are part of the review state.

## Merge And Cleanup Checklist

For each parallel branch:

- `dot_clean .` before commit.
- `git status --short` shows only assigned changes before commit.
- branch has a meaningful commit.
- handoff records branch, changed files, proof outputs, and open issues.
- strict audit report exists for visible animation work, or the handoff records
  why the task was non-animation or explicitly visual-only.
- integration branch merges the task branch.
- integration render/QC is run when the change affects visible output.
- task branch is deleted after merge unless follow-up work is expected.
- any explicitly approved temporary worktree is removed after acceptance.

## Limits And Open Questions

This file describes the current preferred protocol, not a permanent law.
Revise it after actual parallel production runs, especially when:

- many episodes are developed in parallel rather than many scenes in one
  episode.
- generated artifacts need a durable cross-branch review index.
- shared timeline/formula ownership creates recurring merge conflicts.
- subagent supervision needs a stronger assignment or completion-signaling
  format.
- final integration should happen on an integration branch instead of `main`.
