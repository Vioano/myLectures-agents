# Interaction And Style

Use this file when writing widgets, plots, outputs, and explanations.

## Interactivity

Widgets are expensive attention devices. Use them only when changing a
parameter helps the student solve, check, diagnose, or transfer a problem.

Jupyter is a flexible exercise container, not a code-first format. Some of the
best concept checks are pure Markdown. Do not force code into a prompt whose
goal is explanation in the student's own words.

Required for production widgets:

- set sliders to `continuous_update=False` unless smooth continuous motion is
  essential and tested;
- keep output height stable with `widgets.Output` or `interactive_output`;
- avoid repeated warning, logging, or print output during slider changes;
- prevent hidden widget-state errors;
- keep defaults pedagogically meaningful;
- keep parameter ranges small enough to remain readable.

Avoid raw `interact(...)` for matplotlib-heavy cells because it clears and
rebuilds output on every change. Prefer a stable wrapper around
`interactive_output`.

## Interaction Levels

Use the lowest level that fits the teaching function:

- Level 0: pure Markdown response.
- Level 1: static prompt with collapsible hint, answer, or common mistake.
- Level 2: answer input with automatic check.
- Level 3: parameter interaction with structural observation.
- Level 4: object-level experiment, such as transforming uploaded image
  coordinates by a complex map.

Escalate only when the higher level improves feedback or object manipulation.

## Output Hygiene

- Configure Chinese-capable fonts before plotting Chinese labels.
- Treat repeated font warnings, tracebacks, and long debug dumps as blockers.
- Keep figure sizes predictable.
- Close matplotlib figures after display to avoid figure accumulation.
- Prefer text summaries with fixed length over growing print logs.

## Plot Style

Use restrained blackboard-style plots:

- dark board background;
- chalk-like labels;
- semantic colors consistent with the video when known;
- no decorative gradients or arbitrary palettes;
- readable legends and axis labels.

When in doubt, prioritize clarity over matching animation polish. The notebook
is an executable learning artifact.

## Prose

Write enough prose to orient the exercise, not a full lecture transcript.
Use short prompts before code cells:

- what to answer or predict first;
- what structure to identify;
- what computation to perform;
- what feedback will check;
- what failure would reveal the concept.

Prefer "problem statement -> student action -> hint/solution" over long
expository Markdown.

## Presentation Boundary

Student-facing notebook text must not explain the production process, review
gate, skill philosophy, or implementation workaround. Do not write visible
prose such as "this notebook is not a transcript", "this widget is stable",
"we avoid interact to prevent flicker", "this plot is only feedback", or
"this satisfies the pipeline". Those are authoring/review facts, not learning
content.

Keep the stable behavior in code and review artifacts. In the notebook body,
state the mathematical action directly:

- weak: "These sliders do not use interact, so output height stays fixed."
- strong: "Change N. Which sum approaches the integral?"
- weak: "This plot is feedback, not the main content."
- strong: "Compute the coefficient first, then use the plot to check it."

If a sentence explains why the agent designed a cell that way, move it to the
notebook contract, review report, issue JSON, code comment, or skill docs.

## Static Export

Production notebooks should remain useful when viewed on GitHub. If a key idea
requires a widget, include a small static checkpoint or explanatory summary so
the notebook is not empty for non-interactive readers.
