## Plan Progressively, Then Lock Progressively

Do not design the whole episode at equal detail in one pass, and do not jump from a finished `timeline.json` directly into isolated scene code. Use this required macro-to-micro planning chain:

1. **Lecture truth.** Finish the lecture notes and mathematical argument first.
2. **Provisional episode language.** Write only a coarse narration outline and coarse `storyboard.md`. Establish the teaching order, scene jobs, cross-scene identities, and approximate boundaries, but do not synthesize or align the whole episode.
3. **Whole-episode visual spine and batch plan.** The main agent seals `episode_visual_spine.json`, then plans the next three to five scenes in `batch_visual_plan.json`. In parallel mode it also locks the batch entry/exit and adjacent-scene handoffs before delegation. Both remain macro plans rather than beat-level choreography.
4. **Just-in-time narration and visual-scheme co-design.** For the active scene, evolve the scene narration and detailed visual scheme together without writing animation code. Specify the learner state, real mathematical drivers, stage regions and time-varying states, transitions and clearance, identity carriers, composition/hierarchy/negative-space jobs, screen-text necessity, formula memory, and preliminary clause-to-state handoffs. Optional Keynote, grayscale wireframes, or a few critical keyframes may test risky compositions or transitions; they are supporting evidence, not the plan and not a time-based animatic.
   Before any proposed learner-facing literal enters final `scene_plan.json` or
   animation source, run the v1 screen-text decision gate described below.
5. **Scene-local audio and timing lock.** Lock that scene's exact script only
   after author self-review, distinct independent review, and the user's exact
   script approval. Then synthesize and listen to its audio, generate reader
   SRT plus exact word-level SRT/alignment, seal narration QC, and write its
   local timeline fragment. Select visual anchors from real word timestamps,
   not sentence estimates. No animation source is authorized yet. ASR is
   machine evidence and never silently replaces a human listen.
6. **Complete and independently review the timing-bound visual plan.** Replace every provisional clause handoff with exact word anchors, run deterministic scene-plan validation, then give the complete visual plan to a reviewer who is not its author. The reviewer must pass novice causality, mathematical-object truth, stage choreography/attention, visual composition/finish, and production/audio-handoff feasibility; every stage state and transition receives concrete evidence. Keyframes can strengthen a finding but cannot compensate for a missing plan field. A sealed `visual_plan_review.json`, exact `scene_production.json`, and compiled registry jointly authorize animation production. A later semantic, stage, composition, identity, audio, timing, or handoff change invalidates the corresponding hashes and requires revalidation; material visual-plan changes require another independent plan pass.
7. **Word-first animation production.** Only after the exact scene WAV, alignment, narration QC, `scene_production.json`, and execution registry exist may final animation source be written. Compile every spoken clause
   into a word-anchored action whose rendered mathematical driver changes by a
   nonzero amount. A `play()` call, updater, or tracker with zero displacement
   is not motion. Screen the rendered candidate for low-motion spoken windows
   and review every hit from the exact words; unexplained holds return to
   authoring before independent review.
8. **Final scene review.** Run deterministic QC, then enforce `author -> self-review -> independent voiced review`. Every independent `revise` returns to repair and a new self-review.
9. **Final assembly.** After all scenes pass, concatenate scene audio/video and offset-merge the local reader SRT, word alignment, and timeline fragments into final episode artifacts. Assembly must not silently retime an approved scene.

The pre-production scene-complexity gate treats 45-75 seconds as the normal scene target, warns above 75 seconds, and blocks scenes above 90 seconds. A longer scene may proceed only with a structured `scene_split_exception` that names at least two internal sections, their stage-state ownership, a real clearance checkpoint, and why splitting would damage novice continuity. Do not use the exception to protect a late monolithic design.

Use progressive locking:

- the episode layer locks teaching order, approximate scene boundaries, cross-scene object identity, and stable visual conventions, not exact audio;
- the batch layer locks continuity, transition ownership, reuse/variation, and relative complexity across neighboring scenes;
- the scene-audio layer first locks exact wording, listened WAV, subtitles, word timing, and narration QC;
- the pre-production visual layer then locks the word-anchored detailed scheme, stage states, mathematical invariants, attention transfers, composition, and handoffs only after independent plan review;
- micro choreography may change only inside those approved semantics and exact anchors; any semantic, stage, composition, audio, timing, or planning change must update the owning artifact and invalidate the appropriate downstream hashes.

Artifact responsibilities are distinct. `storyboard.md` stays human-readable and coarse at episode scale. `progressive_production.json` records which scenes are provisional, designing, audio-aligned, approved, or assembled. Each audio-aligned scene freezes a `scene_production.json` containing its script, audio, reader SRT, word-level SRT/alignment, exact ASR transcript, timeline fragment, and sealed narration QC. `episode_visual_spine.json`, `batch_visual_plan.json`, and `scene_plan.json` remain the visual planning chain. A review candidate in progressive mode must include the exact scene production contract and compiled execution registry.

After exact audio and word alignment exist, run `validate-scene-plan --output ...`, then `prepare-visual-plan-review` and
`seal-visual-plan-review`. The draft may bind zero or more optional
`--probe keynote=...`, `keyframe=...`, or `wireframe=...` artifacts, but it
cannot pass until the detailed plan itself is complete and every independent
review check passes. Workflow-v2 `phase-start` requires the sealed
`--visual-plan-review` and exact audio-aligned `--scene-production` before
authoring or rendering; a workflow-v1 `design_readiness.json` or silent
animatic cannot substitute for either gate.
New episodes use workflow v3, which additionally requires the profile-bound
`--narration-workflow`: TTS/ASR may start only from `tts_input_locked`, and
animation authoring/render only from `animation_authorized`. The latter state
is sealed only after exact user script approval and current post-TTS
readiness/scene-production bindings. See `references/narration-workflow.md`.

If narration is repaired after animation already exists, do not pretend that
the normal ordering was followed. Open the explicit post-animation narration
repair state, preserve the previous media lineage, invalidate every affected
audio/timing/plan/QC/review/assembly artifact, and rebind from current bytes.
The default is to freeze animation source and reuse pixels only when decoded
evidence proves they remain valid. Any wording change reopens the full
author-reviewer-user script gate; pronunciation or delivery-only repair may
retain the exact script approval but must still rebuild all downstream audio
and timing evidence.
Every seal attempt is retained in `visual_plan_review_attempts.jsonl`, including
probe-backed rejections. Authoring/render phase events retain both the reviewed
and explicitly supplied scene-production hashes. Use these records in the next
episode retrospective to measure pre-animation findings, first-attempt pass
rate, gate coverage, and any attempted keyframe-for-plan substitution; do not
treat missing legacy telemetry as zero.
The same phase start must also receive the fresh episode-level
`--episode-readiness` receipt; its bound narration/audio/alignment,
pronunciation input, and ear evidence are rehashed before expensive work.
Before any full-scene TTS inference, compile the spoken input with
`scripts/compile_tts_input_mapping.py`. The compiler reads the immutable formal
script, the canonical candidate/forbidden-form registry in
`references/tts-pronunciation-registry.json`, and an exact route ID; it emits
one ordered, non-overlapping character-span occurrence inventory and the only
TTS input that the readiness gate may accept. Preflight replays every span and
requires byte-exact reconstruction, rejects unregistered edits and forbidden
forms, and hash-binds the registry, route, mapping, and TTS input. Renderers
must call the canonical receipt validator before plan-only output, cache reuse,
directory creation, or inference; a `pass` string in hand-written JSON is not
authority. Cached raw audio requires a matching TTS-input, mapping, and route
fingerprint sidecar. There is no skip-validation flag.
The pronunciation hard gate listens against the exact bound scene WAV with
ordered per-occurrence windows; an arbitrary or extracted file cannot stand in
for final scene audio. A human or independent reviewer must provide a
hash-bound pronunciation record for those exact windows. Novice bridges
require a hash-bound semantic review in addition to exact narration quotes.
If the episode owner explicitly authorizes `asr_machine_user_authorized` for a
bounded production pass, the readiness contract may bind a user-authority
artifact and a separate ASR machine-review record for each exact window. This
is not a human-listening pass: the receipt must say
`human_review_pending=true`, and the final user audio review remains required
before submission or assembly.
The canonical registry is a fail-closed inventory of allowed audition
candidates and known forbidden forms, not a universal claim about how a Greek
or Latin symbol sounds. Calibrate the active engine, voice, exact route, and
sentence context; bind the tested candidate to every occurrence and scene;
keep standard notation in learner-facing script, subtitles, and formulas; and
treat a pass in one sentence as no evidence for another. A literal candidate
such as `w` or `theta`, and an expanded candidate such as `residue f`, remains
`candidate_pending_exact_scene_ear_review` until the final WAV is heard. Any
pronunciation retry invalidates that scene's audio hash, word alignment,
timeline fragment, voiced render, and downstream assembly.
Visible-text budgets are extracted from the exact scene source and must equal
the declared inventory rather than trusting self-reported counts.
Use a `pre_tts` episode-readiness receipt for initial synthesis: it seals the
spoken-form input without demanding future audio. After synthesis and listening,
rerun as `post_tts`; every scene must then bind
`screen_text_semantic_contract_path` to a machine-readable contract whose
constructor/payload/count inventory exactly matches the final source and whose
items explain the unique visual job, necessity, removal failure, mathematical
or learner-question anchor, and clearance condition of every visible literal.
Candidate/repair renders and finalization reject the pre-TTS stage or a
post-TTS receipt with missing, stale, extra, or self-exempted screen text.
The source extractor, not the author, decides which visible literals exist.
Roles such as recap, transition, creator note, production explanation, reviewer
instruction, persona signature, or next-video routing never justify learner
facing prose by themselves. The contract must bind every surviving literal to
an exact mathematical object, parameter, comparison, or learner question.
Any literal that explains the production process, names the causal-chain
review, announces a recap operation, or foregrounds the creator/agent must be
removed from active source; setting
`externalizes_production_intent=false` cannot exempt its wording.

### Decision-time screen-text preregistration (autopilot v8)

Do not wait for source review to ask whether a visible string belongs on the
student-facing stage. For every proposed `Text`, `MathTex`, project wrapper, or
other visible literal, use these three CLI states before writing final source:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" prepare-screen-text-registration \
  --repo-root . --profile "$SCENE/scene_profile.json" \
  --constructor cn_text --payload '奇点为什么挡住围道？' \
  --role transient_question --output "$SCENE/text-prereg-001.json"

# Fill the generated *.reflection_draft.json. Argue both the keep hypothesis
# and the remove-or-replace hypothesis; a risk match is explicitly not a verdict.
python3 "$SKILL/scripts/pipeline_v2.py" seal-screen-text-reflection \
  --preregistration "$SCENE/text-prereg-001.json" \
  --input "$SCENE/text-prereg-001.reflection_draft.json" \
  --output "$SCENE/text-reflection-001.json"

python3 "$SKILL/scripts/pipeline_v2.py" commit-screen-text-registration \
  --repo-root . --profile "$SCENE/scene_profile.json" \
  --preregistration "$SCENE/text-prereg-001.json" \
  --reflection "$SCENE/text-reflection-001.json" \
  --output "$SCENE/text-registration-001.json"
```

The preregistration prompt is neutral: it must make the author seriously test
both possible conclusions. `revise` and `remove` are valid terminal decisions
and are recorded as pre-source prevention; a revised payload must start a new
preregistration. A risk-signalled `keep` needs counterreflection, but even a
complete counterreflection cannot override the deterministic formal boundary.
Only a `registered` receipt supplies `screen_text_contract_patch`; copy the
latest complete patch into the scene plan. Autopilot v8 validates that the
embedded semantic items exactly match the profile-bound registry and durable
attempt ledger, then freezes that registry as a review artifact. Directly
inventing `registration_id`, `preregistration_hash`, or `reflection_hash`
fields is not an accepted substitute.

The episode retrospective automatically reads
`review/evolution/screen_text_registration_attempts.jsonl` and compares the
current episode with the Episode 8 pre-change baseline in
`references/experiments/screen-text-preregistration-v1.json`. It reports gate
coverage for both proposed literals and planned scenes, zero-candidate scenes,
keep/revise/remove decisions, formal blocks, pre-source prevention, human
boundary escapes by issue, scene, and exact payload where attribution exists,
and human findings that necessary visible text was overblocked. Every compiled
scene writes an idempotent `gate_initialized`
observation, so an empty candidate set is not confused with a scene that never
ran the gate. An absent historical ledger is `unknown`, never zero.
Cross-episode effectiveness requires both observed prevention and fewer human
escapes, while the overblock count remains zero; rerunning the tool on Episode
8 proves instrumentation only.

Before a scene may enter `audio_aligned`, create the exact ASR transcript and a narration QC draft, then seal both the audio and language checks through the CLI. The QC gate compares the approved script with the ASR transcript after punctuation/space normalization, verifies reader and word-level subtitle bounds, checks word alignment and timeline duration against decoded audio, enforces a maximum 0.25-second drift, requires complete playback, and records an audio-only novice teach-back and concrete confusion test. Merely having an audio file is not evidence that the scene is teachable or aligned.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" seal-narration-qc \
  --repo-root . --episode-spine "$EPISODE/episode_visual_spine.json" \
  --scene-slug <scene_slug> --script path/to/script.md --audio path/to/audio.wav \
  --reader-srt path/to/reader.srt --word-srt path/to/word.srt \
  --word-alignment path/to/word_alignment.json \
  --timeline-fragment path/to/timeline_fragment.json \
  --asr-transcript path/to/asr_transcript.txt \
  --review-draft path/to/narration_qc_draft.json \
  --output path/to/narration_qc.json
```

After writing either upstream JSON artifact, seal it deterministically instead of calculating hashes by hand:

```bash
python3 "$SKILL/scripts/pipeline_v2.py" seal-planning-artifact --input path/to/episode_visual_spine.json
python3 "$SKILL/scripts/pipeline_v2.py" seal-planning-artifact --input path/to/batch_visual_plan.json
```

Initialize the progressive tracker from the coarse timeline, then reseal it whenever one scene advances. Whole-episode narration must remain `outline_draft`; whole-episode storyboard status remains `coarse` until final assembly.

```bash
python3 "$SKILL/scripts/pipeline_v2.py" init-progressive-production \
  --repo-root . --episode "$EPISODE" \
  --lecture-notes path/to/lecture.md --narration-outline path/to/script-outline.md \
  --storyboard "$EPISODE/storyboard.md"
python3 "$SKILL/scripts/pipeline_v2.py" seal-progressive-production \
  --repo-root . --input "$EPISODE/progressive_production.json"
```
