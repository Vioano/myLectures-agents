# Problem Driven Interactive Notebooks

This is the core philosophy for myLectures companion notebooks.

Video builds the viewpoint. Notebook tests whether the student can call that
viewpoint inside problems.

The notebook is not a second video, a lecture transcript, a visualization
gallery, or a slider playground. It is an interactive problem session:

```text
Notebook = problem-driven practice
         + concept diagnosis
         + exam training
         + feedback loops
         + only the interaction that earns its place.
```

## Primary Role

The main question is not "can the notebook explain more?" The main question is:

```text
Can the student use the video's structure to solve, judge, diagnose, and
transfer problems?
```

For every notebook, define the expected student actions before choosing code,
plots, widgets, or prose. Good actions include:

- restate a concept in the student's own words;
- identify the hidden structure in a new formula or problem;
- compute a standard exam quantity;
- choose the right space, inner product, interval, weight, or basis;
- find the fastest counterexample or failure condition;
- diagnose a wrong solution;
- use a small visualization to check a completed calculation;
- transfer the same pattern to a nearby variant.

## Jupyter Is A Container

Choosing Jupyter does not mean every exercise needs Python or every concept
needs a widget. It means one artifact can mix the right cell type for the
teaching function:

- pure Markdown concept prompts;
- collapsible hints and reference answers;
- stepwise derivation fill-ins;
- short code checks for numeric or symbolic answers;
- randomized variants;
- a few high-value object-level experiments;
- static summaries for GitHub readers.

Cell form follows teaching function, not technical possibility.

## Problem First, Explanation Second

For main-path sections, prefer this order:

```text
predict -> answer/compute -> check -> hint -> repair -> standard solution -> variant
```

Do not begin every section with long explanation. Make the student act first
when the prerequisite was already built in the video.

## Four Exercise Layers

Every substantial notebook should cover these layers, with emphasis chosen by
episode:

1. **Concept discrimination**: identify whether a structure is present.
2. **Standard calculation**: train exam-like computational fluency.
3. **Error diagnosis**: expose common wrong mental models.
4. **Variant transfer**: change function, interval, basis, boundary condition,
   representation, or normalization and check whether the student still sees
   the same structure.

The layers should not become a long worksheet. Use fewer, sharper exercises
that reveal the course structure.

## Pattern Cards

Some concepts are important enough to train as reusable recognition patterns.
A pattern deserves a card when:

- it will appear repeatedly later;
- it is disguised by many formulas;
- students tend to memorize local tricks instead of seeing the mother
  structure.

Pattern cards are short modules that ask students to recognize the same
structure across several disguises. For the early course, key patterns include:

- nearest complex singularity controls Taylor radius;
- complex multiplication is a constrained plane linear map;
- infinitesimal changes compound into exponentials;
- function spaces are defined by operations and closure;
- inner products depend on space, measure, weight, and conjugation;
- orthogonality kills cross-terms, so coefficients are projections.

Keep only patterns that serve the current episode. Do not turn every concept
into a pattern card.

## Interaction Standard

Good interaction lets the student manipulate a mathematical object, answer, or
feedback state. Bad interaction only lets the student manipulate a UI.

Valid high-value interactions include:

- answer checking with targeted hints;
- random variants that keep the same structure;
- a vector-space or inner-product legality checker;
- a projection-pattern recognizer;
- a complex multiplication experiment where a number acts on points, grids, or
  image coordinates;
- a finite-sampling slider that shows a sum becoming an integral;
- a partial-sum plot used after hand-derived coefficients to check mistakes.

Do not add a widget before naming the problem it helps the student solve.

## Exam Alignment Without Ordinary Homework

The notebook should train exam abilities, but it is not a plain homework dump.
Each exam-like problem should reveal the structure behind the procedure:

- why a denominator appears;
- which inner product is being used;
- why a conjugate is required;
- what condition fails in a non-example;
- which term vanishes by parity or orthogonality;
- how a formula changes when the interval or weight changes.

If an exercise only asks for final answers without diagnosing the method, it is
too close to ordinary homework.

## Non-Negotiable Taste

- Do not make notebooks into video subtitles.
- Do not make visualizations the main learning product.
- Do not make every question code-interactive.
- Do not let students run cells passively and feel they understood.
- Do not give formulas without asking where the space, inner product, basis,
  normalization, or failure condition came from.
- Do not hide the exam skill behind a pretty plot.
- Do not hide conceptual weakness behind a runnable notebook.
