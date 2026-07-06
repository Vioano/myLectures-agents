# QC And Review Gate

Use this before handoff.

## Automatic Audit

Run the notebook top-to-bottom in the notebook repository, then run:

```bash
uv run python /Volumes/bocchi/myLectures/.agents/skills/notebook-production-pipeline/scripts/audit_notebook.py <executed-notebook.ipynb>
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
- oversized saved output risk.

Any error or noisy-output finding makes the candidate `revise`.

Save the audit JSON or terminal output in the episode review area, or record
the exact command and result in the review report. The hard review gate expects
an audit artifact path for production candidates.

## Hard Review Receipt

Use `scripts/review_gate.py` for every production candidate review:

```bash
python /Volumes/bocchi/myLectures/.agents/skills/notebook-production-pipeline/scripts/review_gate.py init \
  --repo-root /Volumes/bocchi/myLectures \
  --notebook /Volumes/bocchi/myLectures/数学物理方法PowerPack-Notebooks/notebooks/NNNN-slug/notebook.ipynb \
  --review-id NNNN-notebook-review-v01 \
  --risk-tier interactive \
  --owner codex \
  --reviewer codex-review
```

Then run:

```bash
python .../review_gate.py checklist --state <state.json>
python .../review_gate.py template-review --state <state.json> > review.json
python .../review_gate.py submit-review --state <state.json> --review-json review.json
python .../review_gate.py status --state <state.json> --require-pass
```

If repairs are required, use `template-fix` and `submit-fix`, then resubmit or
update the review until `status --require-pass` succeeds.

The gate is a receipt, not a substitute for judgment. It rejects incomplete
reviews, missing required readings, missing artifacts, open candidate flags,
uncovered abstract standards, unreviewed regressions, and absent ranked
quality sweeps.

## Independent Review

When possible, run a separate review pass. It must inspect:

- notebook source;
- notebook contract, when required;
- executed output;
- interaction stability;
- exercise quality;
- feedback and hint quality;
- exam alignment;
- pattern-card coverage when applicable;
- mathematical causality;
- presentation boundary and creator-intent text;
- known-regression checklist;
- README/review metadata and path status.

The review stance is a novice student plus a picky teacher. If the notebook is
technically runnable but does not teach the intended post-video action, revise.
The default verdict is `revise`; the reviewer must earn a pass by finding and
closing enough concrete candidate objections for the risk tier.

## Review Report

Write review reports under the target episode review area when the notebook is
a production candidate:

```text
notebooks/NNNN-slug/review/audits/<review_id>__<reviewer>__<branch_slug>.md
notebooks/NNNN-slug/review/issues/<review_id>_<issue_id>.json
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
  "notebook": "notebooks/0002-mpm-2-hilbert-space/notebook.ipynb",
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
    "path": "notebooks/0002-mpm-2-hilbert-space/notebook.ipynb"
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
