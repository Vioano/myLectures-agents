# Notebook Contract And Composer

Use this before implementing a production candidate notebook.

The purpose is the same as the animation scene contract: make ownership and
quality decisions explicit before code hides them.

## When Required

Write a notebook contract when:

- a new production notebook is being authored;
- a previous draft was rejected for wrong direction;
- the notebook has more than one widget or object-level lab;
- the notebook has exam training plus concept diagnosis plus visualization;
- the episode has human feedback or accepted agent feedback;
- the author is an external worker.

Small README or typo repairs do not need a full contract.

## Contract Location

Preferred path:

```text
notebooks/NNNN-slug/review/notebook-contract.md
```

Draft attempts may keep a temporary contract inside their draft directory, but
production candidates should move the final contract to `review/`.

## Required Fields

Use this compact structure:

```markdown
# Notebook Contract

## Target
- episode:
- notebook:
- source video/script/storyboard:
- student after video:

## Main Ability
- one sentence beginning with "Student can..."

## Pattern Cards
- name:
  - why this episode needs it:
  - disguised forms to test:

## Section Plan
| Section | Exercise layer | Cell modality | Student action | Feedback |
|---|---|---|---|---|

## Interaction Budget
| Interaction | Level | Mathematical object | Why it earns space |
|---|---:|---|---|

## Exam Alignment
- standard computations:
- recognition tasks:
- error diagnosis:
- transfer variants:

## Red Flags To Avoid
- pattern_key:
  - avoidance plan:

## Review Anchors
- commands:
- expected audit artifact:
- review_gate risk tier:
```

## Contract Rules

- Every section must have a student action.
- Every widget must name the mathematical object being manipulated.
- Every visualization must say whether it is pre-problem intuition,
  post-calculation check, or optional lab.
- Every exam drill must say what structure it trains.
- Every pattern card must include disguised variants.
- Every error diagnosis must name the wrong mental model.
- Every production candidate must have a review-gate risk tier.

## Worker Boundaries

External workers may implement bounded parts of a contracted notebook:

- one answer checker;
- one widget;
- one plot;
- one exercise section;
- one audit fix.

They must not decide the full notebook philosophy, exercise progression,
interaction budget, or production readiness. The coordinator owns the
contract.
