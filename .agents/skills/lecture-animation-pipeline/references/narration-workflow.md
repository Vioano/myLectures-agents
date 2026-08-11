# Profile-Bound Narration Workflow

## Why This Is A State Machine

Narration is an upstream production artifact, not an informal prompt. A script
may enter TTS only after an explicit audience profile, a frozen candidate, an
author self-review, a distinct independent review, and the user's exact pass.
The same actor may not author and independently review one candidate.

The canonical states are:

`queued -> profile_outline_locked -> outline_reviewed -> drafting ->
script_candidate_frozen -> author_self_review_passed ->
revision_required | user_review_pending -> user_script_approved ->
tts_input_locked -> animation_authorized`.

`revision_required` returns only to `drafting`. It never deletes the failed
review attempt. A reviewer pass releases only `user_review_pending`; it cannot
approve the script or start TTS. The coordinator records the user's exact
words and exact candidate hash. Only `user_script_approved` can reach
`tts_input_locked`. `tts_input_locked` still does **not** authorize animation.
The coordinator must next bind the exact post-TTS readiness and
scene-production inventory. Only `animation_authorized` releases animation
source authoring or rendering.

## Permissions

- `author`: open drafting, freeze a candidate, and seal author self-review;
- `reviewer`: review the profile/outline and independently review a frozen
  candidate after author self-review;
- `coordinator`: bind or hot-rebind the profile, preserve the user's exact
  outcome, lock an approved candidate for TTS, and seal the final narration
  animation release;
- `user`: final script authority. No agent role may synthesize a user pass.

The author and reviewer ids must differ. If a reviewer edits the narration,
that actor becomes an author for the edited candidate and a different reviewer
must be bound before independent review.

## Profile Selection

Profiles live under `references/audience-profiles/`. The registry has no
default. Every episode or series explicitly binds one profile. The initial
profile models the broad Math Physics Methods audience; it must not leak into
a future advanced series.

The profile is a hard dependency of every script candidate and review. It
defines retained prerequisites, working-memory limits, ambiguity policy,
term-introduction rules, formula narration, tone, and review questions.

## Hot Update

Use `rebind-narration-profile` for a live user correction. This is a hot
migration, not a reset. The command preserves history and superseded evidence,
then invalidates the outline review, candidate, self-review, independent
review, user outcome, and TTS lock derived from the old bytes. Work resumes at
`profile_outline_locked`. A candidate already locked for TTS cannot be hot
rebound inside the same workflow revision.

## Evidence And Commands

All mutations use compare-and-swap through `--expected-state-hash`. Review
attempts append to JSONL under the same process lock as state mutation. Frozen
script JSON must bind the exact Markdown SHA. The static audit must be valid,
have zero issues, and bind the exact structured script.

Normal command order:

1. `init-narration-workflow`
2. `record-narration-outline-review`
3. `open-narration-drafting`
4. `freeze-narration-script`
5. `seal-narration-author-self-review`
6. `record-narration-independent-review`
7. `record-narration-user-outcome`
8. `lock-narration-tts-input`
9. synthesize/listen (or preserve explicit machine-only user authority), run
   ASR, word alignment, subtitles, timeline, narration QC, and post-TTS
   readiness
10. `seal-narration-animation-release`

New episode efficiency contracts use workflow gate v3. Their TTS/ASR phases
must bind a narration workflow in `tts_input_locked`; animation authoring and
render phases must bind the same workflow in `animation_authorized`. A visual
plan pass or old scene audio cannot substitute for this release.

Use `narration-workflow-status` after every handoff. A modern independent
review contains:

```json
{
  "workflow_binding": {
    "workflow_id": "...",
    "candidate_hash": "...",
    "profile_sha256": "...",
    "writing_contract_sha256": "..."
  },
  "verdict": "REVISE or PASS_FOR_USER_SCRIPT_REVIEW_ONLY"
}
```

`--import-existing-candidate` exists only to migrate a pre-state-machine,
hash-bound review without discarding it. Every later candidate must traverse
author self-review and the ordinary independent-review transition.

## Review Standard

The independent reviewer reads the complete script from the current bytes,
using only the current cue and previous cue, clearing memory at each scene
boundary. It verifies every fixed timing window, term bridge, hard word anchor,
formula-reading load, algebra step, ambiguity risk, and humor placement.
Passing static structure is necessary but not sufficient. A linguistic or
novice-causality finding keeps TTS blocked.

## Exceptional Post-Animation Narration Repair

Repairing narration after animation already exists is an exception, never the
normal route. Open it only with `open-post-animation-narration-repair` from an
exact `animation_authorized` lineage and only when the user explicitly
authorizes that repair. The repair record must bind the current candidate,
baseline media manifest, affected scenes, exact cue windows, reason, source
change permission, and the full downstream invalidation set.

Two repair kinds are allowed:

- `performance_only`: the approved wording is byte-identical; only delivery,
  pronunciation, prosody, or TTS changes. Script approval remains valid, but
  TTS/audio and every downstream timing, review, manifest, and assembly
  artifact is invalidated. Work returns to `user_script_approved`.
- `script_change`: wording or mathematical meaning changes. The candidate,
  author self-review, independent review, and user script approval are all
  invalidated. Work returns to `revision_required` and must traverse the full
  author -> independent reviewer -> user path again.

Both kinds preserve the old lineage as superseded evidence. They invalidate at
least TTS audio, ASR, word alignment, subtitles, timeline, scene production,
visual-plan binding, registry, runtime telemetry, authoring QC, review
manifest, self-review, independent review, episode assembly, and final-master
audit. Reuse of existing animation pixels is a claim to prove with hashes and
decoded evidence, not an assumption. Animation source remains frozen unless
the same user authority explicitly allows source changes. After repair, a new
`seal-narration-animation-release` must bind the repair-context hash before
animation/render can resume.
