# Production Output Contract

This file is the path, naming, render, review, QC, and final-stitch contract for video production. Follow it for new work. Leave legacy outputs in place unless a migration is part of the task.

## Canonical Video Directory

Each production video lives under `videos/NNNN-slug/`.

```text
videos/NNNN-slug/
  README.md                    optional local overview
  formula-manifest.md          tracked
  timeline.json                tracked
  experiment-log.md            tracked
  storyboard.md                optional production storyboard; see below
  src/
    theme.py                   tracked local style bridge
    <scene_slug>.py            tracked Manim scene source
    <scene_slug>.stage.md      optional tracked stage direction
    scenes/<scene_slug>/       optional componentized Manim scene package
  scripts/                     tracked video-local utilities
  assets/                      tracked episode-specific source/final assets when small and licensed
  references/                  tracked small references and notes; large audio/video references stay ignored
  review/
    assignments.md             tracked ownership and status table
    handoffs/                  tracked handoff notes
    audits/                    tracked strict subagent/independent audit reports
    gate/                      tracked compact review-gate JSON state
    human-feedback/            tracked user review feedback and regression notes
    agent-feedback/            tracked coordinator-accepted agent review lessons
    issues/                    tracked actionable review issues
  draft/                       ignored experiments, tests, temporary samples
  exports/
    audio/                     ignored confirmed full audio and derived voice cuts
    subtitles/                 ignored SRT/alignment for confirmed audio
    manim/                     ignored Manim render media root
    reviews/                   ignored muxed review MP4s and review-only audio mixes
    qc/                        ignored keyframes and contact sheets
    final/                     ignored stitched masters and upload candidates
```

Only the source/control files are normally committed. `draft/`, `exports/`, and Manim `media/` directories are generated and stay out of git unless the user explicitly asks for a specific artifact to be committed.

## Vault Versus Production Storyboard

The formal course version lives in the vault:

- `vault/videos/NNNN-slug/script.md`
- `vault/videos/NNNN-slug/storyboard.md`
- `vault/videos/NNNN-slug/notebook.ipynb`

The production directory may contain a local `storyboard.md` only when it is a working animation plan, derived from or pointing back to the vault version. For formula-dense implementation detail, prefer one of:

- `timeline.json` fields for short stage directions.
- `src/<scene_slug>.stage.md` for reusable scene-level choreography.
- A concise `STAGE_SCRIPT` constant or class docstring inside `src/<scene_slug>.py` when the choreography must stay beside code.

Do not scatter stage-direction notes in the video root. Root-level files should be the canonical shared artifacts listed above.

## Componentized Manim Scene Packages

For formula-dense or stage-dense Manim scenes, prefer:

```text
videos/NNNN-slug/src/scenes/<scene_slug>/
  contract.yaml        tracked local stage contract
  drivers.py           tracked mathematical state and shared parameters
  objects.py           tracked Mobject factories and registration
  layout.py            tracked zones, slots, protected regions, fitting helpers
  beats.py             tracked enter / transform / exit animation units
  composer.py          tracked thin Manim Scene entrypoint
  audit.py             tracked adapter to layout_check and QC anchors
  README.stage.md      optional tracked notes
```

The Manim render command should point to `composer.py`. Review MP4s, QC frames,
audit reports, issues, handoffs, generated exports, and the user-review commit
gate remain exactly as defined in this output contract.

For dense, formula-heavy, or previously human-rejected scenes, this package is
not merely preferred. The scene must pass
`tools/animation_preflight_gate.py --require-component-package` before final
render/review. A single Python file that combines drivers, object factories,
layout, beat scheduling, audit metadata, and several scene groups is a failed
source/control artifact even if it renders.

## Assets Versus Media

- `assets/`: human-curated or source assets for this episode. These may be tracked when they are small, licensed, and needed to reproduce the video.
- `shared/`: cross-episode assets.
- `media/`: Manim-generated cache/output. Treat it as generated. Do not place authored assets there.
- `exports/manim/`: the preferred media root for new Manim production renders.

If a legacy render created root-level `media/videos/...`, keep it as generated output. For new work, pass `--media_dir videos/NNNN-slug/exports/manim` unless there is a documented reason to use a variant media root.

## Naming

Use lowercase snake case.

- `video_slug`: `NNNN-slug`, for example `0001-mpm-1-complex_numbers_tts`.
- `scene_slug`: segment range plus purpose, for example `s014_s018_matrix_action`.
- `scene_class`: PascalCase Manim class, for example `S014S018MatrixAction`.
- `render_id`: `<scene_slug>_vNN_<reason>`, for preserved variants.
- `review_id`: `<scene_slug>_review_vNN_<quality>[_reason]`, where quality is normally `720p30` or `1080p30`.
- `qc_id`: `<scene_slug>_vNN_<reason>` matching the review version.

Prefer zero-padded versions for new outputs: `v01`, `v02`, `v03`. Do not rename old outputs just to match this convention.

## Manim Render Standard

Use Manim Community Edition through `uv`.

Default segment review render:

```bash
uv run manim -qm --fps 30 --disable_caching \
  videos/NNNN-slug/src/<scene_slug>.py <SceneClass> \
  --media_dir videos/NNNN-slug/exports/manim
```

This produces a raw render like:

```text
videos/NNNN-slug/exports/manim/videos/<scene_slug>/720p30/<SceneClass>.mp4
```

Use `-ql --fps 30` only for quick smoke checks and layout experiments. A `-ql` render is not enough for review acceptance.

Use `-qh --fps 30` for final 1080p30 candidates. When the final
master/upload target is 4K, use `-qk --fps 30` or an explicit equivalent
`--resolution 3840,2160 --fps 30` so the source render is truly 2160p30.
Do not claim a 4K final from a simple upscale of 720p/1080p review files
unless the experiment log explicitly marks it as an upscaled delivery
workaround. Use 60 fps only when the motion genuinely benefits and record that
decision in `experiment-log.md`.

If a render variant must be preserved, set a variant media root:

```bash
--media_dir videos/NNNN-slug/exports/manim/<render_id>
```

Record every accepted render command, quality flag, fps, media root, and raw output path in `experiment-log.md`.

## Review MP4 Assembly

A review MP4 is the watchable artifact for human review. It must combine the rendered visual with the relevant voice window and any accepted sound-effect layer. Do not ask reviewers to inspect silent raw Manim output unless the task is explicitly visual-only.

Canonical destination:

```text
videos/NNNN-slug/exports/reviews/<scene_slug>/<review_id>.mp4
```

Review-only derived audio, such as voice cuts or local SFX mixes, may live beside the review MP4:

```text
videos/NNNN-slug/exports/reviews/<scene_slug>/<scene_slug>_voice_<segment_range>.wav
videos/NNNN-slug/exports/reviews/<scene_slug>/<scene_slug>_sfx_<segment_range>.wav
videos/NNNN-slug/exports/reviews/<scene_slug>/<scene_slug>_mix_<segment_range>.wav
```

Minimal voice-only mux pattern:

```bash
ffmpeg -y \
  -i <raw_manim_mp4> \
  -i <voice_or_mix_wav> \
  -map 0:v:0 -map 1:a:0 \
  -c:v libx264 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 \
  -shortest \
  videos/NNNN-slug/exports/reviews/<scene_slug>/<review_id>.mp4
```

When mixing voice and SFX, create or record the mix explicitly. Do not hide a nontrivial mix inside an unlogged one-off ffmpeg command.

Each review handoff must list:

- raw Manim path;
- review MP4 path;
- voice/audio source paths;
- exact mux or mix command;
- duration comparison between narration window and rendered video.

## QC Keyframes

Canonical destination:

```text
videos/NNNN-slug/exports/qc/<qc_id>/
```

Frame naming:

```text
frame_t000p00s.png
frame_t012p50s.png
frame_t101p00s.png
contact_sheet.png
```

Use `p` for the decimal separator so names are shell-safe and sortable.

Extraction tool: `ffmpeg`.

Single-frame pattern:

```bash
ffmpeg -y -ss 12.50 \
  -i videos/NNNN-slug/exports/reviews/<scene_slug>/<review_id>.mp4 \
  -frames:v 1 \
  videos/NNNN-slug/exports/qc/<qc_id>/frame_t012p50s.png
```

Contact-sheet pattern after extracting frames:

```bash
ffmpeg -y \
  -pattern_type glob -i 'videos/NNNN-slug/exports/qc/<qc_id>/frame_t*.png' \
  -vf "scale=480:-1,tile=3x3:padding=12:margin=12" \
  videos/NNNN-slug/exports/qc/<qc_id>/contact_sheet.png
```

Extract frames from the review MP4, not from silent raw video, whenever audio timing affects the edit. Extract from raw video only for visual-only layout debugging and record that exception.

Minimum frame set:

- opening state;
- every important formula reveal;
- every important mathematical transform;
- the densest frame in each subshot;
- transition frames where old and new objects overlap or clear;
- final state;
- every user-feedback fix point.

Use the timeline and stage direction to choose exact timestamps. Do not only sample evenly spaced settled frames.

## Review Tracking

Use `review/` for tracked coordination documents.

- `review/assignments.md`: one row per segment range or scene, with owner, branch, source files, review output, QC output, and status.
- `review/handoffs/<agent>-<segments>.md`: short handoff with commands, paths, QC notes, known issues, and next action.
- `review/audits/<scene_slug>/<review_id>__<reviewer>__<branch_slug>.md`: strict subagent or independent audit report. The branch slug replaces `/` with `--`, so `codex/0002-s001` becomes `codex--0002-s001`.
- `review/gate/<scene_slug>/<session_id>/state.json`: compact machine state
  written by `tools/review_gate.py`. It records required-document hashes,
  review rounds, accepted review submissions, accepted fix submissions, open
  issues, and whether the scene has reached `pass_for_user_review_pending`.
  Large artifacts remain in `exports/`; gate state is source/control.
- `review/human-feedback/<date>-<scope>.md`: user review findings, screenshot or video evidence, repeated-pattern lessons, issue ids created from them, and authoring preflight expectations for future animation agents.
- `review/agent-feedback/<date>-<scope>.md`: subagent or group-review findings that the coordinator has accepted as reusable future guidance. Do not put every transient subagent comment here; promote only findings that prevent repeated authoring or review failures.
- `review/issues/*.json`: actionable review queue items. Check it before starting, rendering, handing off, or marking a segment done.

Review documents are source/control files, but for animation production they
must not be committed merely because a subagent audit passed. First hand the
current review MP4, QC/contact sheet, source/control paths, audit reports, and
issue status to the user for final viewing. Commit the animation source/control
changes only after the user explicitly approves the review output for commit.
Review MP4s and QC frames remain in `exports/`.

Audit reports must be concrete enough for the animation owner to repair the
scene without chat context. Each report must include:

- owner, reviewer, branch, reviewed commit, and worktree path if not the main checkout;
- reviewed scene ids and adjacent segment ids used for continuity checks;
- review MP4, voice/audio source, SRT/alignment, timeline, stage direction, formula manifest, source code, and QC frame paths;
- overall verdict: `pass`, `revise`, or `blocked`;
- a checklist mapping the review to this skill's requirements;
- a ranked aesthetic/noise ledger with at least three closed entries naming
  the first, second, and third ugliest/noisiest/least-clear visual candidates;
- numbered findings with severity, requirement reference, evidence location, impact, recommended fix, owner, and status.

When a finding is actionable, also create a JSON issue:

```json
{
  "id": "s001-opening-recap-v03-001",
  "source": "subagent_review",
  "reviewer": "subagent-review",
  "scene": "s001_opening_recap",
  "review_id": "s001_opening_recap_review_v03_720p30",
  "severity": "major",
  "status": "open",
  "pattern_key": "formula_axis_overlap",
  "must_check_in_future": true,
  "applies_to_authoring": true,
  "authoring_preflight_check": "Reserve a separate formula lane or clear the axis label before formula entry.",
  "requirement": "30-visual-language-and-style.md: Layout Discipline",
  "evidence": {
    "timestamp": 12.5,
    "file": "videos/NNNN-slug/src/s001_opening_recap.py",
    "line": 123,
    "qc_frame": "videos/NNNN-slug/exports/qc/s001_opening_recap_v03/frame_t012p50s.png"
  },
  "problem": "Formula overlaps the axis label during the transition.",
  "impact": "The viewer cannot read the mathematical relation at the narration beat.",
  "fix_target": [
    "videos/NNNN-slug/src/s001_opening_recap.py",
    "videos/NNNN-slug/src/s001_opening_recap.stage.md"
  ],
  "suggested_fix": "Clear the old axis label before the formula enters or move the formula to the right-side lane."
}
```

For human review findings, set `source` to `human_review` and include
`pattern_key`, `must_check_in_future: true`, `novice_viewer_risk`, and
`aesthetic_risk`. Also set `applies_to_authoring: true` unless the finding is
strictly about review logistics, and add `authoring_preflight_check` describing
what future animation agents must do before coding. Future animation authors
must read these records before storyboard/timeline/stage/code work. Future
auditors must search for matching `pattern_key` records before issuing a
`pass`. A repeat of a human-found pattern is a regression and blocks
acceptance.

For subagent or group-review findings that the coordinator accepts as reusable
guidance, write a short note under `review/agent-feedback/` and create or update
a JSON issue with `source: accepted_agent_feedback`, `origin_source:
subagent_review`, `accepted_by`, `pattern_key`, `must_check_in_future: true`,
evidence, impact, fix target, and `authoring_preflight_check` when applicable.
After promotion, these records have the same authoring and audit force as human
feedback. Ordinary unpromoted `source: subagent_review` issues remain part of
the current repair queue, but do not automatically become permanent regression
tests.

Do not mark `review/assignments.md` as accepted while any open audit issue for
that scene remains. Also do not mark the scene as user-review-ready until
`tools/review_gate.py status --require-pass` succeeds for the current review
session.

After all audit issues are resolved and the strict audit verdict is `pass`,
the next status should be a user-review state such as `user_review_pending`.
Use final accepted wording only after the user has viewed the review artifact
and explicitly approved the commit.

## Final Stitching

Do not jump from scene work directly to a final full episode without accepted segment reviews.

Use:

```text
videos/NNNN-slug/exports/final/segments/
videos/NNNN-slug/exports/final/<video_slug>_master_vNN_1080p30.mp4
videos/NNNN-slug/exports/final/<video_slug>_upload_vNN_bilibili_1080p30.mp4
videos/NNNN-slug/exports/final/<video_slug>_master_vNN_2160p30.mp4
videos/NNNN-slug/exports/final/<video_slug>_upload_vNN_bilibili_2160p30.mp4
```

Segment files in `exports/final/segments/` should be numbered in playback order:

```text
001_s001_opening.mp4
002_s002_core_question.mp4
003_s003_roadmap.mp4
```

Use ffmpeg concat demuxer or an equivalent scripted stitch, and record:

- segment list path;
- source review/final segment paths;
- full audio/subtitle path;
- output path;
- codec, resolution, fps, audio sample rate, and duration.

Concat demuxer pattern:

```text
file 'segments/001_s001_opening.mp4'
file 'segments/002_s002_core_question.mp4'
file 'segments/003_s003_roadmap.mp4'
```

```bash
ffmpeg -y \
  -f concat -safe 0 \
  -i videos/NNNN-slug/exports/final/segments/concat.txt \
  -c:v libx264 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 \
  videos/NNNN-slug/exports/final/<video_slug>_master_vNN_1080p30.mp4
```

Preview/review files may be 720p30 or 1080p30 for iteration speed, but final
master/upload candidates should use a higher resolution than the preview when
the user requests final clarity. For 4K delivery, use 3840x2160, normally
2160p30 for this course unless a documented reason chooses 60 fps. Project
default upload candidate remains H.264 MP4, `yuv420p`, AAC audio at 48 kHz.
Verify current Bilibili upload requirements before final publishing if the
platform constraints matter.

## Exports Semantics

`exports/` means "generated artifact that has entered the production chain", not "committed source".

- `exports/audio/` and `exports/subtitles/`: confirmed audio/subtitle intermediates used by timeline, review, or final stitch.
- `exports/manim/`: raw Manim render output and caches.
- `exports/reviews/`: human-reviewable muxed clips.
- `exports/qc/`: keyframes/contact sheets.
- `exports/final/`: stitched masters and upload candidates.

`draft/` means experiments, failed attempts, temporary listening samples, short tests, and disposable scratch outputs.

Both `exports/` and `draft/` are ignored by default. The distinction is production confidence, not git status.

## Pre-Handoff Checklist

Before handing off a segment:

- `timeline.json` points to the scene and audio sources used.
- For dense or human-rejected scenes, `tools/animation_preflight_gate.py` has
  passed for the exact `scene_slug`; the source path points to
  `src/scenes/<scene_slug>/composer.py`, not a combined multi-scene file.
- `formula-manifest.md` marks implemented formulas, and only marks `verified` after review.
- Manim render command is recorded.
- Review MP4 exists under `exports/reviews/<scene_slug>/`.
- QC frames exist under `exports/qc/<qc_id>/`.
- `experiment-log.md` records outputs, render settings, QC findings, and known issues.
- `review/assignments.md` or `review/handoffs/` is updated when multiple agents are involved.
- `review/gate/<scene_slug>/<session_id>/state.json` exists, accepted the
  latest review/fix loop, and passes `tools/review_gate.py status
  --require-pass`.
- `git status --short` is checked, and only source/control files are staged.

For animation source/control changes, this checklist is a handoff boundary, not
automatic commit permission. If user review is still pending, do not stage or
commit; report the clean status and wait for explicit user approval.
