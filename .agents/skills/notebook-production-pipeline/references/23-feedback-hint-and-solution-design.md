# Feedback Hint And Solution Design

Use this when designing answer checks, hints, solutions, and cell modality.

Notebook interaction is a feedback loop, not a UI layer.

```text
answer -> check -> targeted hint -> revised answer -> solution -> variant
```

## Cell Modality Rule

Choose the cell type by teaching function:

- pure Markdown for concept restatement and qualitative diagnosis;
- collapsible Markdown for hints, standard answers, and common wrong answers;
- one or two equation blanks when a single missing normalization, sign, or
  structural quantity is the target;
- open calculation space for standard computations, derivations, and proof-like
  questions where the student should choose the order of steps;
- tables only when the student is comparing multiple cases, matching
  structures, or classifying a family of objects;
- short code checks for numerical, symbolic, choice, or matrix answers;
- widgets only for structural parameter variation;
- object-level labs only for high-value transformations that paper cannot show
  well.

Static questions are not inferior. Some of the strongest concept checks should
be Markdown-only.

Do not repair an exposed answer by turning every exercise into a blank table or
a fill-in-blank worksheet. That replaces one mechanical surface with another.
If the task is "derive this coefficient" or "compute this projection", usually
give the problem statement, a few requirements, and a blank working area. Use
blanks only for the one step you want to isolate. Use a table only when rows
and columns help the student see a comparison that would be harder to see in
prose. A blank working area should be ordinary Markdown spacing: write the
prompt, leave several blank lines, then put the reference solution under
`<details>`. Do not add a custom bordered HTML box for ordinary handwritten
work.

## Hint Ladder

Prefer layered hints:

1. recall the relevant structure;
2. point to the missing object or condition;
3. give the first algebraic step;
4. reveal the standard solution.

Do not reveal the final answer as the first hint.

## Answer Checking

When using code to check answers:

- check the smallest meaningful step, not only the final result;
- return short feedback, not long logs;
- distinguish arithmetic errors from structural errors;
- when possible, generate a nearby variant after success;
- keep check functions deterministic and visible enough to be trusted.

Examples:

- For complex multiplication, check matrix entries, scale, and angle
  separately.
- For vector-space tests, check addition closure, scalar closure, and zero
  object separately.
- For projection formulas, ask for target, basis, inner product, denominator,
  and conjugation before asking for the final coefficient.

## Solutions

A standard solution should show the method, not only the answer.

Good solution blocks include:

- the structure being used;
- the key decision;
- the computation;
- the common wrong path;
- the transfer note.

Keep solutions compact. The video already carried the lecture.

## Feedback Copy

Feedback should sound like a precise tutor:

- "The denominator is the basis vector's length squared."
- "This fails scalar closure: multiply a positive function by `-1`."
- "This integral is an inner product only after the interval and weight are
  specified."
- "The plot is a check. The coefficient still needs to come from projection."

Avoid vague copy:

- "Try again."
- "Think about it."
- "Incorrect."
- "Looks good."

## Static Viewing

GitHub/static readers must still see the learning path. For widget-heavy
sections, include:

- the prompt;
- the expected student decision;
- one static checkpoint output;
- a short explanation of what the interaction would test.
