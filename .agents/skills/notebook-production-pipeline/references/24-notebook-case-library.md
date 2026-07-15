# Notebook Case Library

Use this file when planning notebooks for early Math Physics Methods episodes.
The cases are design anchors, not full notebooks.

## 0001 Complex Numbers And Euler Formula

Working title:

```text
Complex multiplication as plane transformation: interactive problem notebook
```

Main question:

```text
Can the student treat complex multiplication as a plane linear transformation
and use that structure in exam problems?
```

Recommended path:

1. Concept check: why enter the complex plane when real-axis behavior looks
   smooth?
2. Taylor radius drills: find complex singularities and nearest distance.
3. Derive multiplication matrix for `w = alpha + beta i`.
4. Prove the matrix columns are equal-length and orthogonal, so there is no
   shear.
5. Predict before interaction: what do `w=2`, `w=i`, `w=1+i`, and `w=0` do?
6. High-value interaction: act on grid, unit circle, points, or uploaded image
   coordinates with `z -> wz`.
7. Exam drills: polar form, powers, roots of unity, De Moivre formula.
8. Pattern card: infinitesimal changes compound into exponentials.
9. Error diagnosis: "i was defined as rotation", wrong modulus, angle
   multiplication, ignoring complex singularities.
10. One-page exam summary.

Interaction budget:

- one main complex-plane transformation interaction;
- optional image-coordinate transform lab;
- one light numerical limit table for `(1 + i theta/N)^N`.

Do not make this a unit-circle animation gallery.

### Infinitesimal-To-Exponential Pattern

This pattern is important enough to be explicit.

Core form:

```text
state_next = (I + generator * dt) state_now
state(t) = exp(generator * t) state(0)
```

Teach layers:

- scalar growth: `(1 + a t/N)^N -> exp(a t)`;
- complex rotation: `(1 + i theta/N)^N -> exp(i theta)`;
- matrix rotation: `(I + J theta/N)^N -> exp(J theta)`, where
  `J = [[0, -1], [1, 0]]`;
- optional warning: time-dependent noncommuting generators are more subtle.

The goal is a thought pattern: small linear changes compounded many times
often become an exponential finite transformation.

## 0002 Hilbert Space

Working title:

```text
Why functions are vectors: Hilbert-space judgment and inner-product training
```

Main question:

```text
Can the student decide what the objects are, what operations are allowed, what
inner product is legal, and whether limits stay in the space?
```

Recommended path:

1. Markdown concept checks: what is a mathematical space, and why are functions
   vectors without being a metaphor?
2. Vector-space judgment set: positive functions, even functions, odd
   functions, `f(0)=0`, `f(0)=1`, degree at most `n`, degree exactly `n`.
3. Finite sampling bridge: functions as continuous-index vectors.
4. Inner product calculations: `sin`/`cos`, norms, orthogonality.
5. Error diagnosis: complex inner product without conjugation fails on
   `f(x)=i`.
6. Inner-product context matching: interval, domain, weight, measure, volume
   element.
7. Orthogonality is inner-product zero, not graph geometry.
8. Short projection preview without stealing the Fourier episode.
9. Completeness through counterexamples: rationals, polynomial limits.
10. Three-gate summary table: vector space, inner product space, Hilbert space.

Interaction budget:

- vector-space judgment checker;
- finite sampling slider for sum-to-integral;
- three-gate table checker.

Do not over-visualize abstraction. Train judgment.

## 0003 Fourier Projection

Working title:

```text
Why Fourier coefficients are projections: formula-pattern literacy notebook
```

Main question:

```text
Can the student see a coefficient integral and identify projection structure,
normalization, inner product, basis, interval, weight, and conjugation?
```

Recommended path:

1. Markdown concept check: Fourier coefficient as projection coordinate.
2. Two-dimensional projection warm-up; emphasize denominator as length
   squared.
3. Projection mother formula:
   `c_n = <phi_n, f> / <phi_n, phi_n>`.
4. Formula disguise recognition: Fourier, normalized sine basis, weighted
   projection, Legendre preview, non-projection integration by parts.
5. Inner-product definition drills: interval, weight, conjugation,
   normalization.
6. Orthogonality and Gram matrix: cross-terms vanish; diagonal entries explain
   constants.
7. Derive complex-exponential and sine/cosine coefficients.
8. Hand calculation: `f(x)=x` on `[-pi, pi]`.
9. Partial sums only after hand coefficients, as a check.
10. Error diagnosis: missing denominator, missing conjugate, wrong interval,
    wrong parity, treating frequency domain as another physical world.

Interaction budget:

- projection-pattern recognizer;
- orthogonality or Gram matrix checker;
- partial-sum check with wrong-coefficient modes;
- small random coefficient trainer.

Do not recreate a Fourier animation. Train projection reflex.

## Case Selection Rule

When creating a new notebook case:

1. state the main problem action;
2. list the reusable structures;
3. list exam abilities;
4. choose interaction levels;
5. list error diagnoses;
6. state what visualizations must not become the main dish.
