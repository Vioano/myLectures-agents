# Exercise Taste And Red Flags

This file defines what counts as a good notebook exercise.

The soul of the notebook is not interactivity. It is the quality of the
problems and feedback.

## Good Exercise Shape

Prefer exercises that force one precise mathematical action:

- explain a concept in original language;
- identify a structure in disguise;
- compute a quantity with the correct normalization;
- choose a definition from the problem context;
- find a counterexample;
- repair a wrong solution;
- predict before running;
- compare a visual check with a hand calculation;
- transfer to a nearby function, interval, basis, or boundary condition.

Every exercise should say what the student is practicing.

## Four-Layer Structure

Use these layers as a design checklist:

### A. Concept Discrimination

Good for Markdown, choices, matching, or short answer.

Examples:

- Is this set a vector space?
- Is this integral a legal inner product?
- Is this coefficient formula a projection?
- Does this matrix come from multiplying by a complex number?

### B. Standard Calculation

Good for exam fluency with optional answer checks.

Examples:

- compute an inner product or norm;
- find Fourier coefficients;
- convert a complex number to polar form;
- compute roots of unity;
- solve a short boundary-condition basis selection.

### C. Error Diagnosis

Good for Notebook because feedback can be layered.

Examples:

- forgot conjugation in a complex inner product;
- treated graph crossing as function orthogonality;
- forgot the denominator in a projection;
- used a Fourier coefficient formula from the wrong interval;
- assumed a positive-function set is a vector space.

### D. Variant Transfer

Good for checking that the student did not memorize one example.

Examples:

- change `x` to `x^2`, a square wave, or `|x|`;
- change `[-pi, pi]` to `[0, L]`;
- change an ordinary inner product to a weighted inner product;
- change Fourier basis to Legendre or Bessel preview;
- change scalar infinitesimal evolution to matrix evolution.

## Interaction Levels

Choose the lowest level that serves the exercise:

```text
Level 0: pure Markdown response
Level 1: static prompt + collapsible hint/solution
Level 2: answer input + automatic check
Level 3: parameter interaction + structural observation
Level 4: object-level experiment, such as image-as-plane-object transform
```

Do not escalate levels for polish. Escalate only when feedback, structure
recognition, or object manipulation genuinely improves.

## Red Flags

Reject or rewrite when:

- the exercise only says "run this cell" or "observe";
- a slider changes a plot but not the student's reasoning;
- a plot appears before the student has predicted or computed;
- code solves the problem before the student does;
- the answer is shown without diagnosing common wrong paths;
- every problem is visual and none is exam-like;
- every problem is exam-like and none checks concept structure;
- a question has no feedback or transfer variant;
- a Markdown prompt is replaced by code for no reason;
- a long derivation is dumped instead of split into decision points;
- a formula appears without asking where its denominator, interval, weight, or
  conjugation came from.

## Red Flag Names

Use these `pattern_key` values when relevant:

- `run_all_observation_only`
- `slider_without_problem_action`
- `visualization_before_prediction`
- `code_solves_before_student`
- `missing_error_diagnosis`
- `exam_drill_without_structure`
- `concept_prompt_forced_into_code`
- `projection_denominator_hidden`
- `inner_product_context_missing`
- `partial_sum_as_main_dish`
