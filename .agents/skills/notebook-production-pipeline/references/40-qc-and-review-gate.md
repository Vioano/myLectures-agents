# QC And Review Gate

Use this before handoff.

## Automatic Audit

Run the notebook top-to-bottom in the notebook repository, then run:

```bash
uv run python /Volumes/bocchi/myLectures/.agents/skills/notebook-production-pipeline/scripts/audit_notebook.py --json <executed-notebook.ipynb> \
  > episodes/NNNN-slug/review/audits/NNNN-notebook-audit.json
```

The audit checks for:

- cell errors;
- widget-state errors;
- warning/error text in outputs;
- matplotlib font/glyph warnings;
- raw `interact(...)` usage;
- sliders that may continuously redraw;
- visible Markdown that exposes production/review/workaround intent instead
  of student-facing mathematical action;
- AI-ish or over-scripted public prose, using a small hard subset of the
  `$humanizer` rules: em/en dashes, generic signposting, negative-parallelism
  slogans, inflated "core/key/deep" framing, chatbot-like English phrases,
  and scaffold vocabulary in Markdown or code string literals;
- student-visible implementation slang or casual engineering metaphors, such
  as describing pixels as being thrown forward instead of naming the mapping
  and sampling relation;
- code cells that only print fixed calculations when Markdown equations or
  tables would be clearer;
- derivations or short calculations mechanically formatted as fill-in tables
  when equation blanks or numbered prompts would be clearer;
- calculations over-scaffolded as chains of fill-in blanks when an open
  calculation prompt would better match exam practice;
- custom bordered HTML answer boxes where plain Markdown spacing should be
  used for ordinary written work;
- notebook-level overuse of one question surface, such as too many fill-in
  prompts, prompt tables, choice prompts, or code checks;
- answer tables exposed directly after prompts instead of hidden behind a
  collapsible solution block;
- collapsible answer tables that have no visible fill-in table or equivalent
  question before the solution;
- worked solutions or full derivations visible before an attempt prompt,
  including cells headed "直接算", "标准结果", or similar answer-first prose;
- crude or chatty student-facing headings that state the author's attitude
  rather than the mathematical action;
- raw TeX pipe characters inside Markdown tables, such as `$|x|$`, that can
  break table rendering;
- oversized saved output risk.

Any error or noisy-output finding makes the candidate `revise`.

Save the audit JSON in the episode review area and record the exact command in
the review report. Terminal output is not sufficient for a passing gate. For a
passing review, the gate reads the JSON and requires top-level `status:
"pass"`, a result for the target notebook, and a notebook SHA-256 matching the
current file. A failing, missing, or stale audit file blocks the pass.

## Hard Review Receipt

Use `scripts/review_gate.py` for every production candidate review:

```bash
uv run python /Volumes/bocchi/myLectures/.agents/skills/notebook-production-pipeline/scripts/review_gate.py init \
  --repo-root /Volumes/bocchi/myLectures/数学物理方法PowerPack-Notebooks \
  --notebook /Volumes/bocchi/myLectures/数学物理方法PowerPack-Notebooks/notebooks/NNNN-slug.ipynb \
  --episode-dir /Volumes/bocchi/myLectures/数学物理方法PowerPack-Notebooks/episodes/NNNN-slug \
  --review-id NNNN-notebook-review-v01 \
  --risk-tier interactive \
  --owner codex \
  --reviewer codex-review
```

Then run:

```bash
uv run python .../review_gate.py checklist --state <state.json>
uv run python .../review_gate.py template-review --state <state.json> > review.json
uv run python .../review_gate.py submit-review --state <state.json> --review-json review.json
uv run python .../review_gate.py status --state <state.json> --require-pass
```

If repairs are required, use `template-fix` and `submit-fix`, then resubmit or
update the review until `status --require-pass` succeeds.

The gate is a receipt, not a substitute for judgment. It rejects incomplete
reviews, missing required readings, missing artifacts, open candidate flags,
uncovered abstract standards, unreviewed regressions, and absent ranked
quality sweeps.

It also rejects these formerly-soft failures:

- `artifacts.auto_audit_json` exists but does not have audit status `pass`;
- the audit JSON does not include the target notebook path;
- the audit JSON was produced for an older notebook hash;
- passing review omits `reviewer_independence`;
- the selected risk tier is lower than the minimum derived from existing
  human-feedback or regression issue records;
- `human-rejected` or `repeat-rejected` reviews claim a subagent review without
  a subagent session/evidence;
- `submit-fix` does not address every open candidate flag, ranked quality
  item, and open issue from the last review.

## Independent Review

When possible, run a separate review pass. It must inspect:

- notebook source;
- notebook contract, when required;
- executed output;
- interaction stability;
- exercise quality;
- feedback and hint quality;
- exam alignment;
- reusable-structure coverage when applicable;
- mathematical causality;
- presentation boundary and creator-intent text;
- known-regression checklist;
- README/review metadata and path status.

The review stance is a novice student plus a picky teacher. If the notebook is
technically runnable but does not teach the intended post-video action, revise.
The default verdict is `revise`; the reviewer must earn a pass by finding and
closing enough concrete candidate objections for the risk tier.

For any candidate that was already rejected by the user, a separate subagent is
preferred. If no subagent is available, the review report must say it was an
independent pass by the same main agent and explain why that exception is being
used. That exception is weaker evidence, not a real subagent review.

## Review Report

Write review reports under the target episode review area when the notebook is
a production candidate:

```text
episodes/NNNN-slug/review/audits/<review_id>__<reviewer>__<branch_slug>.md
episodes/NNNN-slug/review/issues/<review_id>_<issue_id>.json
```

Each report should include:

- target notebook path;
- source script/storyboard paths;
- notebook contract path or reason no contract was required;
- branch and reviewed commit if available;
- execution command;
- audit command and JSON/path;
- gate state path;
- verdict: `pass_for_user_review_pending`, `revise`, or `blocked`;
- abstract standards checklist;
- concrete regressions checklist;
- candidate red-flag ledger;
- ranked notebook-quality sweep;
- numbered findings.

## Issue JSON

Use JSON for actionable repair items:

```json
{
  "id": "0002-notebook-review-v01-001",
  "source": "human_review",
  "reviewer": "user",
  "notebook": "notebooks/0002-mpm-2-hilbert-space.ipynb",
  "review_id": "0002-notebook-review-v01",
  "severity": "major",
  "status": "open",
  "standard_key": "interaction_stability_failure",
  "pattern_key": "output_area_jitter_from_widget_warnings",
  "must_check_in_future": true,
  "applies_to_authoring": true,
  "authoring_preflight_check": "Use stable widget output and remove repeated warning/print output before handoff.",
  "evidence": {
    "cell": "Taylor widget",
    "screenshot": "",
    "path": "notebooks/0002-mpm-2-hilbert-space.ipynb"
  },
  "problem": "Slider changes repeatedly emit warnings and resize the output area.",
  "impact": "The student sees a jumpy unstable animation instead of a controlled experiment.",
  "suggested_fix": "Configure fonts, suppress known benign warnings, and replace raw interact with fixed-height interactive_output."
}
```

Human feedback and accepted agent feedback become future regression checks.
Ordinary unaccepted review comments remain current repair items only.

## User Handoff

Report:

- notebook path;
- draft or production status;
- execution validation;
- audit result;
- review report or issues;
- known limitations;
- whether user review is pending, approved, or changes requested.

Do not infer user approval from an automated or agent review pass.
