# Exam And Concept Alignment

Use this file when deciding what a notebook should train.

A myLectures notebook must align three layers:

```text
video structure -> problem action -> exam competence
```

If any layer is missing, revise the design.

## Ability Targets

Write notebook goals as abilities, not topics.

Weak:

- Learn Fourier series.
- Understand Hilbert spaces.
- Explore complex numbers.

Strong:

- Recognize a coefficient integral as a projection.
- Decide whether a function set is closed under scalar multiplication.
- Compute the matrix of multiplication by a complex number.
- Explain why a complex inner product needs conjugation.
- Find the nearest complex singularity that controls Taylor radius.
- Choose the correct basis from a boundary condition.

## Pattern Recognition Training

For a reusable mother structure, ask students to identify:

- the object;
- the allowed operations;
- the space;
- the inner product or comparison rule;
- the basis or direction;
- the normalization factor;
- the failure condition.

Examples:

```text
Projection problem = (space, inner product, basis, normalization).
Taylor radius problem = (center, singularities, nearest distance).
Vector-space problem = (objects, addition, scalar multiplication, zero object).
Infinitesimal evolution = (state, generator, small step, continuous product).
```

## Exam Skill Categories

Use a balanced set of categories. Not every episode needs all of them.

- Concept restatement: explain the idea without copying the video.
- Recognition: decide which structure a new problem belongs to.
- Calculation: carry out standard exam computations.
- Normalization: find the denominator, weight, interval, or length square.
- Counterexample: find the fastest reason a candidate fails.
- Error diagnosis: locate and repair a wrong solution.
- Transfer: solve the same pattern after changing representation or domain.

## Question Form Fit

Choose the question shape from the knowledge being tested:

- concept discrimination: short answer, true/false with reason, choice, or
  matching;
- standard calculation: open calculation space or a code answer checker, not a
  chain of tiny blanks unless the point is one missing normalization;
- derivation/proof: a larger blank working area plus a collapsed reference
  solution;
- structure recognition across many cases: table or matching prompt;
- error diagnosis: show a wrong solution and ask the student to locate and
  repair the first bad step;
- transfer: a nearby variant with fewer hints than the main example;
- parameter intuition: prediction first, then widget/plot check.

Do not let one form dominate the notebook. If three adjacent exercises have
the same surface shape, review whether the question type is being chosen
mechanically instead of by the mathematical action.

## Early Course Anchors

### Episode 0001

Train:

- nearest complex singularity for Taylor radius;
- complex multiplication as a special `2 x 2` matrix;
- modulus and argument as scale and rotation;
- powers, roots, and De Moivre-style exam tasks;
- infinitesimal composition becoming exponential form.

### Episode 0002

Train:

- vector-space closure and zero-object checks;
- legal inner products, including conjugation;
- function inner product as sum-to-integral bridge;
- orthogonality as inner product zero, not graph geometry;
- completeness as "limit stays in the space";
- the three-stage test: vector space, inner product space, Hilbert space.

### Episode 0003

Train:

- projection formula literacy;
- denominator awareness;
- complex conjugate in coefficient formulas;
- orthogonality killing cross-terms;
- parity shortcuts;
- deriving Fourier coefficients from the projection template;
- using partial sums as checks after calculation.

## Alignment Test

Before implementation, answer:

1. What exact exam or problem action does this section train?
2. Which video concept does that action call on?
3. What misconception will this section expose?
4. What feedback does the student receive after an answer?
5. What nearby variant confirms transfer?

If these answers are vague, do not author cells yet.
