# Script Authoring Feedback Loop

This reference covers the TTS script stage before audio synthesis. It exists
because narration mistakes can become expensive after IndexTTS2 audio, SRT,
alignment, and `timeline.json` are produced.

## Trigger

Use this loop whenever an episode has a TTS `script.md`, especially after the
user flags wording, mathematical precision, AI-sounding narration, exposition
order, pronunciation, or "the animation can show this" overnarration.

## Required Inputs

Before revising `script.md`, read:

- `review/human-feedback/*.md`;
- accepted `review/agent-feedback/*.md`;
- `review/issues/*.json` with `source: human_review`,
  `source: accepted_agent_feedback`, `applies_to_script_authoring: true`, or
  `must_check_in_future: true`;
- `tts-speaking-rules.md`;
- `formula-manifest.md`;
- `references/50-known-failures-and-fixes.md`;
- the current `storyboard.md` and `timeline.json` if they already exist.

Then write a short script-authoring preflight in `experiment-log.md`. It must
name the applicable `pattern_key` records and say how the script revision will
avoid them.

## Feedback Record Contract

Every reusable user script critique should leave two tracked records:

1. A human-readable note under `review/human-feedback/`.
2. One actionable issue JSON under `review/issues/`.

For script problems, the issue JSON should include:

- `source: "human_review"`;
- `pattern_key`;
- `must_check_in_future: true`;
- `applies_to_authoring: true`;
- `applies_to_script_authoring: true`;
- `authoring_preflight_check`;
- `fix_target` including `script.md`, `tts-speaking-rules.md`, and any affected
  `formula-manifest.md`, `storyboard.md`, or `timeline.json`;
- optional `script_lint_rule` when the failure can be caught by regex,
  segment structure, terminology, or metadata checks.

## Hard Gates Before TTS

Do not synthesize or patch audio until all applicable gates pass:

- open human-review script issues have either been fixed or explicitly marked
  not applicable for this pass;
- `script.md` uses the agreed route terminology and account signature;
- pronunciation hacks are recorded in `tts-speaking-rules.md`;
- important spoken or displayed formulas are represented in
  `formula-manifest.md`;
- the local `scripts/lint_tts_script.py` or equivalent has run successfully;
- `render_full_indextts2.py --plan-only` or the local plan command confirms
  segment count, chunking, and character limits;
- if script edits change segment ids, `storyboard.md`, `timeline.json`, and
  review issues have been updated before audio work starts.

If no script lint exists yet, create a small episode-local checker before full
audio synthesis. The checker should fail or warn on recurring failures, not
try to judge the whole script.

## Claim Responsibility Check

For each core sentence, identify the subject and verb.

Reject wording when a mathematical object is assigned the wrong job:

- an expansion "answers" a why-question when it only displays a representation;
- an animation "proves" a formula when it only gives intuition;
- a transform "explains" a coefficient when orthogonality or projection is the
  actual reason;
- a screenshot, analogy, or title carries a claim that should come from a
  computation.

Prefer precise verbs:

- `represents`, `writes`, `shows`, `is read as`, `has coordinates`;
- `comes from`, `follows from`, `is why`, or `explains` only when the cited
  object actually supplies the reason.

## Visual Obviousness Check

Do not spend narration on frame-by-frame facts the animation can show.

Keep short labels for:

- what object is being built;
- which coefficient or basis function is active;
- what the partial sum, spectrum, phase, or density represents.

Cut or compress sentences that only describe obvious curve shape, motion, or
screen layout. Use the saved time for causality: why the construction works,
what the coordinate means, what the inverse step rebuilds, or what condition
will be proved in the Notebook.

## Notebook Boundary

Some rigor belongs in the companion Notebook rather than the video. The script
should state that boundary only when it helps the viewer trust the route.

Good video coverage:

- one concrete intuitive proof idea;
- the algebraic skeleton needed for the visual construction;
- what the formula means as a coordinate or reconstruction.

Notebook coverage:

- full orthogonality proofs;
- completeness and basis theorems;
- convergence conditions;
- distribution-level details such as delta functions when the video only needs
  the spectral intuition.

## Review Questions

Before marking the script ready for TTS, ask:

- Did every human-found script failure become a tracked issue or an accepted
  non-applicable note?
- Can a future agent find the rule without reading chat history?
- Did any old AI-sounding phrase survive because it felt convenient?
- Does the ending preview the next mathematical question, or does it expose the
  producer's course-route management?
- Are time-domain/frequency-domain, positive transform/inverse transform,
  phase, and continuous-frequency distinctions placed where the abstraction has
  earned them?
- If the animation already shows a fact, does the narration add meaning rather
  than repeat the frame?
