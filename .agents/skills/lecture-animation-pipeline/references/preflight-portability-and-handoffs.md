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

At `post_tts`, each scene additionally binds
`screen_text_semantic_contract_path`. The referenced JSON may be a standalone
contract or a v7 scene plan containing `screen_text_contract`; its
`semantic_items` must exactly match every final-source
`Text`/`MarkupText`/`Paragraph`/registered wrapper literal by constructor,
payload, and count. Every item must state its unique visual job, necessity,
removal failure, mathematical-object or learner-question anchor, and clearance
condition, with narration duplication and production-intent flags explicitly
false. Missing, stale, extra, or self-exempted text blocks post-TTS readiness.

Example:

```json
{
  "schema": "lecture-animation-episode-readiness-v2",
  "readiness_stage": "post_tts",
  "author_id": "animation-author-agent-id",
  "fixed_ending": "那么，小圈积分究竟读取了奇点附近的哪一部分信息？",
  "fixed_ending_contract": {
    "role": "learner_facing_math_question",
    "learner_job": "带着关于小圈积分所提取局部信息的问题离开本段推导",
    "math_anchor": "小圈积分与奇点局部信息",
    "externalizes_production_intent": false
  },
  "rolling_pace_warning_limit": 4.8,
  "rolling_pace_hard_limit": 5.5,
  "screen_text_budget": 12,
  "summary_connector_budget": 4,
  "sensitive_tokens": ["eta"],
  "pronunciation_map": {
    "theta": {
      "bindings": [
        {
          "spoken_form": "theta",
          "scene_slug": "g003",
          "tts_input_path": "videos/NNNN-slug/review/v2/g003/tts_input.txt",
          "source_audio_path": "videos/NNNN-slug/exports/audio/scenes/g003.wav",
          "ear_evidence_path": "videos/NNNN-slug/exports/audio/scenes/g003.wav",
          "ear_review_path": "videos/NNNN-slug/review/v2/g003/pronunciation_review.json",
          "occurrences": 2,
          "occurrence_windows_seconds": [[31.84, 32.32], [36.16, 36.48]],
          "ear_check_results": [
            {"occurrence": 1, "window_seconds": [31.84, 32.32], "result": "pass"},
            {"occurrence": 2, "window_seconds": [36.16, 36.48], "result": "pass"}
          ]
        },
        {
          "spoken_form": "theta",
          "scene_slug": "g011",
          "tts_input_path": "videos/NNNN-slug/review/v2/g011/tts_input.txt",
          "source_audio_path": "videos/NNNN-slug/exports/audio/scenes/g011.wav",
          "ear_evidence_path": "videos/NNNN-slug/exports/audio/scenes/g011.wav",
          "ear_review_path": "videos/NNNN-slug/review/v2/g011/pronunciation_review.json",
          "occurrences": 1,
          "occurrence_windows_seconds": [[40.0, 40.32]],
          "ear_check_results": [
            {"occurrence": 1, "window_seconds": [40.0, 40.32], "result": "pass"}
          ]
        }
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
exact current source scaffold/narration, novice and visible-text evidence,
sensitive-token map, and TTS input with every formal token replaced by its
spoken form; it does not pretend that not-yet-generated audio has already been
heard. A whole-episode lock uses `readiness_scope: full_episode`. A progressive
episode may instead use `readiness_scope: progressive_wave` at either stage:
`wave_scene_slugs` must exactly match the bound scene rows in episode order,
every row supplies its scene-specific `author_id` and `tts_input_path`, and the
contract hash-binds the complete `progressive_production.json` plus a
`fixed_ending_source_path` inside the episode that contains the one fixed
ending exactly once. Nonadjacent scenes in the same parallel wave are not
treated as adjacent narration boundaries; their true boundary is checked when
the missing neighboring scene joins a later wave. This permits just-in-time
scene narration and scene-local audio locking without pretending that
unfinished scenes have exact scripts. Run the initial TTS phase with the fresh
`pre_tts` wave receipt. After synthesis and listening, change that same exact
wave to `post_tts`, bind every covered scene's exact WAV, windows, independent
pronunciation review, and final machine-readable screen-text semantic
contract, and rerun preflight. A post-TTS wave receipt authorizes candidate or
repair work only for its exact covered scenes. Episode finalization still
requires a `post_tts` receipt whose scene set exactly equals the complete final
production set; a wave receipt cannot finalize the episode.

The episode-wide screen-text budget is a default, not an invitation to hide
long scenes behind an arbitrary larger number. A scene-specific increase must
remain below the duration-bound cap and persist a
`screen_text_budget_exception` with a concrete reason, transient-text clearing
plan, and semantic-contract path. Otherwise the increase itself is a blocker.

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
source, review kind, and pass verdict. Screen text is automatically extracted
from every literal `Text`, `MarkupText`, `Paragraph`, and registered project
wrapper such as `cn_text` in every Python file
under the hash-bound `scene_source_root`; `scene_source_path` must live inside
that root, every inventory `source_path` must also remain inside it, and the
declared inventory must match the extracted per-file multiset exactly. Dynamic
constructor text blocks until it is made auditable. Every semantic item must
also declare its necessity, the learner-visible failure caused by removal, a
mathematical-object or learner-question anchor, and its clearance condition.
The gate independently rejects episode recap/process labels, next-video
scheduling, creator identity, and persona farewells even when an author marks
them as learner-facing. Summary connectors remain separately source-bound.

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
Every scene TTS input must also bind a
`lecture-animation-tts-input-mapping-v2` file compiled by
`scripts/compile_tts_input_mapping.py`. Its Unicode character offsets,
formal surfaces, occurrence indices, and spoken forms must be ordered and
non-overlapping; replaying them against the hash-bound formal script must
reconstruct `tts_input.txt` byte for byte. The compiler and preflight consume
`references/tts-pronunciation-registry.json`, reject any known forbidden or
unregistered candidate, require a registered exact route, and include the
registry, mapping, and input hashes in the readiness receipt. Composite tokens
such as `i d theta` or `Res f` own their spans, so their internal atomic tokens
cannot be double-replaced. The registry stores candidates and known failures;
it does not turn any spelling into a cross-context listening pass.
If a token occurs in more than one scene, `pronunciation_map.<token>.bindings`
must contain one evidence object for every affected scene; a single global
spoken-form declaration cannot stand in for per-scene, per-occurrence
listening.
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

Episode-specific TTS renderers must call the same canonical receipt validator
before plan-only output, raw-cache inspection, directory creation, or
inference. They must compare the runtime engine/model/quantization, CLI hash,
speaker hash, emotion-reference hash, seed, and every synthesis parameter with
the route fingerprint sealed in the registry and receipt. A raw WAV is reusable
only with a matching provenance sidecar bound to the exact TTS input, mapping,
and route fingerprint. Direct bottom-level CLI output is diagnostic only until
it enters this evidence chain.

This gate is not a substitute for listening or novice review. It cheaply
removes predictable failures before they become audio, subtitle, animation, and
assembly rework. Rerun it whenever narration order, audio timing, terminology,
or the ending changes.

## 2. Lossless low-token subagent handoffs

Before the first handoff, seal `lecture-animation-episode-startup-v1`. Its
`canonical_evidence_root` and `canonical_phase_ledger` are the only shared
episode evidence destinations for the live run; every producer worktree keeps
scene-local working evidence but writes the same phase event exactly once to
that shared ledger. The startup contract also binds the retained agent IDs and
worktrees, so a task capsule cannot silently authorize a replacement identity
or a checkout outside `/Volumes/bocchi/myLectures-worktrees`.

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

The exact user phrase `整理 Git 状态` invokes the complete local consolidation
contract in the canonical Skill: inventory the current task scope, promote all
protected generated assets to `/Volumes/bocchi/myLectures`, merge approved
tracked source/control to local `main`, pass the canonical portability audit,
and only then remove that task's producer/integration worktrees. A temporary
worktree whose branch name is `main` is an integration aid, not the canonical
filesystem destination. The trigger does not include push, upload, branch
deletion, protected-media deletion, or unrelated worktree cleanup.

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

Episode promotion is incomplete until the canonical checkout also contains
the phase, outcome, review-attempt, author-self-review, repair-attempt, and
screen-text ledgers; the final supervisor session and task capsules; and every
human/accepted-agent feedback plus issue JSON. `episode-retrospective` must be
able to observe those records from the canonical episode tree. A final MP4
with those ledgers stranded only in producer worktrees is a portability pass
for media, but not a complete process closeout.

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
