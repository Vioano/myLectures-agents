# Episode preflight, durable promotion, and portable rebuilds

This reference turns the main efficiency lessons from episodes 5 and 6 into
cheap gates that run before expensive TTS/render work and before temporary
worktrees are removed.

## 1. Episode readiness before TTS

Create `review/v2/episode_readiness.json` with schema
`lecture-animation-episode-readiness-v2`. It must list every planned scene in
order and bind the narration, duration or WAV, word alignment when available,
concept load, novice bridge, prerequisites, screen-text count, and summary
connector count. The episode section also binds:

- `fixed_ending`;
- `pronunciation_map` and `pronunciation_ear_check`;
- `required_concept_bridges` plus concrete `concept_bridges`;
- rolling pace warning/hard limits;
- screen-text and summary-connector budgets.

Example:

```json
{
  "schema": "lecture-animation-episode-readiness-v2",
  "readiness_stage": "post_tts",
  "author_id": "animation-author-agent-id",
  "fixed_ending": "我是结束乐队的键盘手，下个视频见。",
  "rolling_pace_warning_limit": 4.8,
  "rolling_pace_hard_limit": 5.5,
  "screen_text_budget": 12,
  "summary_connector_budget": 4,
  "sensitive_tokens": ["eta"],
  "pronunciation_map": {
    "eta": {
      "spoken_form": "伊塔",
      "scene_slug": "g011",
      "tts_input_path": "videos/NNNN-slug/review/v2/g011/tts_input.txt",
      "source_audio_path": "videos/NNNN-slug/exports/audio/scenes/g011.wav",
      "ear_evidence_path": "videos/NNNN-slug/exports/audio/scenes/g011.wav",
      "ear_review_path": "videos/NNNN-slug/review/v2/g011/pronunciation_review.json",
      "occurrences": 3,
      "occurrence_windows_seconds": [[31.84, 32.32], [36.16, 36.48], [40.0, 40.32]],
      "ear_check_results": [
        {"occurrence": 1, "window_seconds": [31.84, 32.32], "result": "pass"},
        {"occurrence": 2, "window_seconds": [36.16, 36.48], "result": "pass"},
        {"occurrence": 3, "window_seconds": [40.0, 40.32], "result": "pass"}
      ]
    }
  },
  "required_concept_bridges": ["mode", "discrete_to_continuous"],
  "concept_bridges": [
    {
      "bridge_id": "mode",
      "scene_slug": "g001",
      "term": "模式",
      "explanation": "先看两个可以直接指认的振动形状，再观察它们怎样分别变化",
      "concrete_referent": "两个具体振动形状",
      "learner_action": "指出两个形状分别怎样变化",
      "narration_quote": "先看两个可以直接指认的振动形状",
      "term_introduction_after_referent": true,
      "novice_bridge_review_path": "videos/NNNN-slug/review/v2/g001/novice_bridge_review.json"
    },
    {
      "bridge_id": "discrete_to_continuous",
      "scene_slug": "g004",
      "term": "连续积分",
      "explanation": "先看一排还留着间隔的频率点，再观察相邻点的间隔逐渐缩小",
      "concrete_referent": "间距逐渐缩小的频率格点",
      "learner_action": "指出格点间隔与每项权重一起变化",
      "narration_quote": "相邻频率点的间隔正在缩小",
      "term_introduction_after_referent": true,
      "novice_bridge_review_path": "videos/NNNN-slug/review/v2/g004/novice_bridge_review.json"
    }
  ],
  "scenes": [
    {
      "scene_slug": "g001",
      "scene_source_path": "videos/NNNN-slug/src/scenes/g001/composer.py",
      "scene_source_root": "videos/NNNN-slug/src/scenes/g001",
      "narration_path": "videos/NNNN-slug/review/v2/g001/narration.txt",
      "audio_path": "videos/NNNN-slug/exports/audio/scenes/g001.wav",
      "word_alignment": "videos/NNNN-slug/exports/audio/scenes/g001_alignment.json",
      "concept_load": "concept_heavy",
      "prerequisites": ["ordinary vector direction"],
      "new_terms": ["模式"],
      "novice_bridge": {
        "explanation": "先看两个可以直接指认的二维方向，再观察它们怎样分别变化",
        "concrete_referent": "两个可以直接指认的二维方向",
        "learner_action": "指出两个方向如何分别变化",
        "narration_quote": "先看这两个能分别变化的方向",
        "term_introduction_after_referent": true
      },
      "novice_bridge_review_path": "videos/NNNN-slug/review/v2/g001/novice_bridge_review.json",
      "screen_text_inventory": [
        {
          "text": "两个方向",
          "source_path": "videos/NNNN-slug/src/scenes/g001/scene.py"
        }
      ],
      "screen_text_count": 1,
      "summary_connector_inventory": [],
      "summary_connector_count": 0
    }
  ]
}
```

Run:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" episode-preflight \
  --repo-root . \
  --episode "$EPISODE" \
  --contract "$EPISODE/review/v2/episode_readiness.json" \
  --output "$EPISODE/review/v2/episode_readiness_receipt.json" \
  --require-clean
```

The readiness contract has two non-circular stages. `pre_tts` requires the
exact source/narration, novice and visible-text evidence, sensitive-token map,
and TTS input with every formal token replaced by its spoken form; it does not
pretend that not-yet-generated audio has already been heard. Run the initial
TTS phase with that receipt. After synthesis and listening, change the stage to
`post_tts`, bind the exact scene WAV, windows, and independent pronunciation
review, and rerun preflight. Candidate/repair renders and episode finalization
require `post_tts`.

The gate hash-binds the contract, exact scene source, narration, audio,
alignment, TTS pronunciation input, and review evidence. Every novice-bridge
field must be an exact quote from the bound narration; descriptive self-report
is rejected. Semantic relevance is a hybrid gate: an independent reviewer or
human must write a hashed `lecture-animation-novice-bridge-review-v2` record
that binds the narration SHA, bridge hash, term list, verdict, and four
relevance checks. The review also binds `author_id`, a distinct `reviewer_id`,
its own canonical `review_hash`, and a separately hashed
`lecture-animation-human-review-authority-v2` (or equivalent independent
authority) record that authorizes that reviewer for the exact author, review
source, review kind, and pass verdict. Screen text is automatically extracted from every
literal `Text`, `MarkupText`, and `Paragraph` constructor in every Python file
under the hash-bound `scene_source_root`; `scene_source_path` must live inside
that root, every inventory `source_path` must also remain inside it, and the
declared inventory must match the extracted per-file multiset exactly. Dynamic
constructor text blocks until it is made auditable. Summary connectors remain
separately source-bound.

The gate blocks exact narration repeated across adjacent scene boundaries,
rolling or fallback average pace above the hard limit, concept-heavy scenes
without prerequisites and a narration-ordered concrete novice bridge, required
conceptual transitions without bound narration evidence, excessive screen text
or summary connectors, a missing or duplicated fixed ending, unresolved formal
tokens in TTS input, and missing per-occurrence ear results. Bridge inference
is not only declarative: the first learner-facing use of `模式` automatically
requires the `mode` bridge, and discrete-to-continuous or continuous-integral
phrasing automatically requires `discrete_to_continuous`, even when
`concept_load` is labeled `normal`.

Pronunciation matching canonicalizes ASCII, LaTeX, and Unicode Greek forms
(`eta`, `\eta`, `η`, and their supported peers) before counting occurrences.
Evidence must be a decodable WAV, must be the exact audio bound to the named
scene, and must carry ordered, non-overlapping 1..N time windows with one
result per occurrence. A hashed `lecture-animation-pronunciation-review-v2`
record from a human or independent reviewer must bind that audio SHA, token,
spoken form, windows, results, three listening checks, distinct author/reviewer
identities, and the authority record described above. A shorter extracted clip
may remain as a review aid, but it is not the hard-gate evidence. The gate
warns above 75 seconds and blocks above 90 seconds without a persisted split
exception.

Pass the fresh stage-appropriate receipt to every expensive phase:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" phase-start \
  --repo-root . --run-id RUN --scene-slug g001 --phase tts \
  --phase-purpose initial \
  --episode-readiness "$EPISODE/review/v2/episode_readiness_receipt.json" \
  --design-readiness "$EPISODE/review/v2/g001/design_readiness.json" \
  --actor-model MODEL --state "$EPISODE/review/evolution/g001-tts.json"
```

`phase-start` rehashes every bound input. TTS accepts `pre_tts` or `post_tts`;
candidate/repair rendering and `finalize-episode` require `post_tts`.
Finalization also requires a fresh receipt with a scene set exactly equal to
`progressive_production.json`. Editing a narration, alignment, TTS input, or
ear-evidence file after preflight makes the receipt stale and blocks downstream
work.

This gate is not a substitute for listening or novice review. It cheaply
removes predictable failures before they become audio, subtitle, animation, and
assembly rework. Rerun it whenever narration order, audio timing, terminology,
or the ending changes.

## 2. Lossless low-token subagent handoffs

Do not transmit large source files, CLI logs, or repeated policy prose through
chat. Put the complete bounded state on disk and send only its path and hash.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" build-task-capsule \
  --repo-root . \
  --scene-slug g001 \
  --role animation_author \
  --task "implement the sealed scene and self-review it" \
  --artifact plan="$EPISODE/review/v2/g001/scene_plan.json" \
  --artifact audio="$EPISODE/exports/audio/scenes/g001.wav" \
  --gate design_readiness=pass \
  --output "$EPISODE/review/v2/g001/task_capsule.json"
```

Subagent messages contain only:

1. status;
2. artifact paths and hashes;
3. gate results;
4. blockers;
5. next action.

Required CLI output remains durable on disk and is never summarized away. A
receiver verifies hashes before acting. Spawn with only the context needed for
the bounded task; reuse the stable episode roster instead of repeatedly
forking full history.

## 3. Promote accepted scene assets before deleting a worktree

An accepted scene is not durable merely because its branch was merged. Generated
audio, review media, alignment files, and manifests may be ignored by Git.
Promote every required path from the producer worktree into the canonical
checkout, then verify source/destination hashes:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" promote-scene \
  --source-root /Volumes/bocchi/myLectures-worktrees/agent-batch-a \
  --canonical-root /Volumes/bocchi/myLectures \
  --artifact videos/NNNN-slug/exports/audio/scenes/g001.wav \
  --artifact videos/NNNN-slug/review/v2/g001 \
  --output "$EPISODE/review/v2/promotion_receipts/g001.json"
```

The command rejects unsafe relative paths and promoted text that still names a
temporary worktree. Use `--replace` only when the replacement is the reviewed
candidate and the prior hash is already recorded.

Promotion and receipt creation are one transaction. The receipt must live
outside every promoted destination, because adding it inside a promoted
directory would immediately invalidate the directory hash. If the receipt
cannot be written, every replaced destination is restored and every newly
promoted destination is removed.

Keep one current review package per scene or final episode. Older generated
review variants may be removed after their issue history and accepted findings
have been preserved as text records.

## 4. Portability audit before final delivery or worktree cleanup

Define the smallest authoritative rebuild set:

- lecture, narration, storyboard, timeline, scene plans, and source;
- final scene audio, reader/word subtitles, alignment, and timeline fragments;
- reusable assets, BGM configuration, sprite sources, fonts or font manifest;
- final native segments or a deterministic native-render route;
- final video, final sidecar subtitles, manifests, and acceptance receipts.

Then run:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" audit-portability \
  --repo-root . \
  --episode "$EPISODE" \
  --required-artifact lecture="$EPISODE/lecture.md" \
  --required-artifact source="$EPISODE/src" \
  --required-artifact audio="$EPISODE/exports/audio/scenes" \
  --required-artifact final_video="$EPISODE/exports/final/upload.mp4" \
  --required-artifact final_srt="$EPISODE/exports/final/reader.srt" \
  --required-artifact final_manifest="$EPISODE/exports/final/manifest.json" \
  --authoritative-root "$EPISODE/src" \
  --authoritative-root "$EPISODE/scripts" \
  --authoritative-root "$EPISODE/review/v2/current" \
  --output "$EPISODE/review/v2/portability_receipt.json" \
  --require-clean
```

The receipt requires all six semantic roles (`lecture`, `source`, `audio`,
`final_video`, `final_srt`, and `final_manifest`), requires every artifact and
authoritative directory to live inside the episode, requires the source role to
be covered by a nonempty authoritative text directory, hashes the paths, and
blocks temporary-worktree references inside authoritative text. A lecture-only
or single-file-root audit cannot pass. Role names are not enough: the lecture
must be nontrivial text, source must contain executable code, scene audio must
contain decodable WAV files, the final MP4 must pass `ffprobe`, the SRT must
contain valid cues, and the manifest must bind the episode, positive duration,
final-video SHA, and subtitle SHA. Historical manifests may preserve old
provenance, but a current repo-relative rebuild manifest must supersede them.
Never delete a worktree until the canonical checkout passes this audit and a
read-only inventory proves that all remaining unique files are obsolete,
duplicated by hash, or intentionally preserved elsewhere.

## 5. Metrics and completion integrity

Planned scenes from `progressive_production.json` are the denominator even when
they emitted no events. Zero phase/token events mean zero observability, not
100 percent coverage. Only phase events with `result=completed` count toward
coverage. Every scene requires completed design, authoring, render, and review
pairs. A scene requires a completed repair pair if it emitted a repair event,
has a repair-attempt record, or any durable review/outcome record says
`revise`, `blocked`, `rejected`, or otherwise carries pending repairs. Omitting
the repair timer cannot erase the requirement.

At finalization, scan every `review/v2/supervisor*.json`, not merely the session
named on the command line. Any invalid/open session, any illegal assignment,
task, or replacement state, or a closed session that still contains active
assignments, queued tasks, or authorized replacements, blocks completion. The
completion receipt records all scanned sessions, final artifact hashes, issue
closure, scene outcomes, and measured production telemetry.

## 6. Reusable finishing route

The per-episode wrapper may provide paths and scene-class mappings, but it must
call the standard finalization contract in `finalization.md`. Before the
expensive 4K render, preflight fonts, subtitle renderer, BGM source and recipe,
sprite sources, audio channel layout, ending-name cue, and expected output
paths. Cache only immutable overlays and record their hashes. Do not copy an
old episode-specific script and silently retain its absolute worktree paths.
