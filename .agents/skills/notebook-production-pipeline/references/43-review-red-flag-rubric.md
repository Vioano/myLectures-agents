# Review Red Flag Rubric

This rubric adapts the animation pipeline's reverse-burden review mechanism to
course notebooks.

The reviewer is not trying to prove that the notebook is acceptable. The
reviewer is trying to find the strongest reasons it is not yet ready for the
student, then close those reasons with repair evidence or explicit documented
non-applicability.

## Default Verdict

Default to `revise`.

Accept only when:

- required skill references and episode feedback have been read and recorded;
- the notebook and audit artifacts exist, and the audit JSON reports
  `status: "pass"` for the target notebook;
- reviewer independence is declared with evidence;
- all abstract standards have evidence;
- all known regressions have been checked;
- enough candidate red flags have been collected for the risk tier;
- every candidate flag is `fixed`, `pardoned`, or `not_applicable`;
- every ranked notebook-quality issue is closed;
- the final gate command reports pass.

## Risk Tiers

Use the strictest tier that fits the candidate.

```text
low              Tiny metadata, README, or typo-only change.
normal           Ordinary notebook creation or repair.
interactive      Any widget, animation-like output, callback, or rich plot.
human-rejected   User already rejected the direction or found a serious issue.
repeat-rejected  Same notebook or pattern has been rejected more than once.
```

Recommended minimums:

```text
low:             0 candidate flags, 1 ranked quality item
normal:          5 candidate flags, 3 ranked quality items
interactive:     8 candidate flags, 4 ranked quality items
human-rejected: 12 candidate flags, 5 ranked quality items
repeat-rejected:18 candidate flags, 7 ranked quality items
```

A reviewer may exceed the minimum. A reviewer may not lower the minimum without
writing the downgrade reason in the review JSON and audit report.

## Candidate Red Flags

Each candidate flag is an objection that could block the notebook. It does not
need to be a final confirmed bug when first recorded. It must be investigated
and closed.

Allowed statuses:

- `open`: unresolved; pass is impossible.
- `fixed`: repaired with evidence.
- `pardoned`: accepted despite the cost, with a reason and owner.
- `not_applicable`: checked and shown not to apply.

Each flag should include:

- `id`
- `standard_key`
- `pattern_key` when it maps to known failures
- `severity`
- `evidence`
- `impact`
- `suggested_fix`
- `status`
- `resolution_evidence` or `pardon_reason` when closed

For `pardoned`, the reviewer must explain why the issue is safe for a novice
student, not merely why it is convenient to leave unchanged. For
`not_applicable`, the reviewer must name the inspected evidence that makes it
not applicable.

## Minimum Sweep Groups

Reviewers must actively search these groups:

- course-object alignment: does each section serve the episode's central
  learning action?
- problem-driven design: does the notebook test the student's ability to use
  the video structure in problems, rather than explain or visualize more?
- exam alignment: are standard course abilities trained without reducing the
  notebook to ordinary homework?
- exercise agency: does the student predict, compute, modify, or explain, not
  merely observe?
- feedback quality: are wrong answers diagnosed with targeted hints and
  repair routes?
- cell modality: is Markdown/code/widget/object lab chosen by teaching
  function? Are tables reserved for comparison and classification rather than
  used as the default shape for every exercise? Are fill-in blanks used
  sparingly, with proof/calculation questions given enough room for students
  to organize their own solution? If an open written area is needed, is it
  ordinary Markdown spacing rather than custom answer-box chrome?
- reusable-structure coverage: are reusable mother structures trained through
  disguised forms when applicable?
- mathematical causality: are sampling, sums, limits, projections, rotations,
  conjugation, and approximations exposed as real computational steps?
- interaction stability: do sliders, callbacks, redraws, output height, and
  widget state stay stable?
- output hygiene: are warnings, glyph boxes, tracebacks, huge dumps, and
  repeated logs absent from saved outputs?
- presentation boundary: does student-facing prose avoid creator-intent,
  pipeline, review-gate, draft-status, implementation-workaround text, and
  visible scaffold labels or implementation slang that make the notebook feel
  like an agent artifact?
- humanized public prose: does the notebook avoid the hard `$humanizer`
  failure subset: em/en dashes, generic signposting, negative-parallelism
  slogans, inflated "core/key/deep" framing, chatbot-like English phrases, and
  AI-ish scaffold vocabulary? Does it also avoid casual engineering metaphors
  when a precise mathematical relation is needed?
- static-reading fallback: can GitHub or a non-interactive reader still follow
  the core lesson?
- visual readability: are plots, legends, labels, colors, and code/prose
  density readable?
- source boundary: are public notebooks, drafts, generated files, validation
  outputs, and review records in the correct places? Public production
  notebooks must be `notebooks/NNNN-slug.ipynb`, not
  `notebooks/NNNN-slug/notebook.ipynb`.
- review traceability: are audit outputs, issues, fixes, and user-pending
  status recorded?

## Ranked Notebook-Quality Sweep

Every non-low-risk review must rank at least three candidates by relative harm.
Use concrete titles, not vague adjectives.

Examples:

- "1. Most unstable output: Taylor slider redraws and emits font warnings."
- "2. Weakest exercise: section 3 only asks the student to run a cell."
- "3. Least course-aligned visual: generic 3D surface does not reinforce the
  Hilbert-space inner-product action."

These ranked items may overlap with candidate flags, but they must be visible
as a separate ordered ledger. The purpose is to prevent a polite review from
missing the worst local quality problems.

## Abstract Standard Keys

Use these keys in review reports and issue JSON:

- `course_object_alignment_failure`
- `problem_driven_design_failure`
- `exam_alignment_failure`
- `feedback_design_failure`
- `cell_modality_failure`
- `pattern_card_failure`
- `demo_gallery_failure`
- `mathematical_causality_failure`
- `interaction_stability_failure`
- `output_hygiene_failure`
- `presentation_boundary_failure`
- `source_boundary_failure`
- `review_gate_bypass_failure`

## Pass Wording

Use `pass_for_user_review_pending` for a candidate that has passed automatic
and agent review but still needs user direction. Do not write `final_pass`
unless the user has explicitly approved that notebook direction.

## Reviewer Independence

Every passing review includes:

```json
{
  "reviewer_independence": {
    "owner": "codex",
    "reviewer": "codex-review",
    "mode": "subagent",
    "evidence": "Subagent session reviewed source, executed output, audit JSON, issue records, and ranked quality sweep.",
    "subagent_session": "<session id or worker log path>",
    "same_agent_exception_reason": ""
  }
}
```

Allowed modes are `subagent`, `independent_pass`, and `human_review`. For
`human-rejected` and `repeat-rejected`, `subagent` is preferred. If the same
main agent performs an independent pass because no subagent is available, the
exception reason must be explicit. Do not describe it as a subagent review.
