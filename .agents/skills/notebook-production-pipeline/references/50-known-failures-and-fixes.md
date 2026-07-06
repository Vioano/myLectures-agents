# Known Failures And Fixes

Use this file in two layers:

1. Abstract review standards that let reviewers reject new problems without an
   exact prior case.
2. Concrete regression cases already seen in notebook work.

## Abstract Review Standards

### `course_object_alignment_failure`

Failure class: the notebook is about the same topic as the video but does not
reinforce the video's main course object or student action.

Reject when:

- sections are broad topic summaries rather than targeted after-video practice;
- examples are valid but do not reveal the intended idea;
- widgets explore side topics before the core construction is established.

### `problem_driven_design_failure`

Failure class: the notebook is organized as explanation, demonstration, or
visualization instead of interactive problem practice.

Reject when:

- section goals are topics rather than student abilities;
- the student can run the notebook passively without answering anything;
- visualizations appear before prediction, calculation, or diagnosis;
- the notebook never asks whether the student can use the video's structure in
  a new problem.

### `exam_alignment_failure`

Failure class: the notebook does not train the course's exam-relevant actions,
or it trains them as ordinary homework without structural feedback.

Reject when:

- there are concept prompts but no standard computations;
- there are computations but no normalization, interval, basis, or condition
  checks;
- errors are marked wrong but not diagnosed;
- no transfer variant checks whether the method generalizes.

### `feedback_design_failure`

Failure class: answer checking, hints, and solutions do not form a learning
loop.

Reject when:

- hints reveal the answer immediately;
- feedback only says correct/incorrect;
- standard solutions show results without method and common wrong paths;
- answer checks validate only the final number when the structural decision is
  the learning target.

### `cell_modality_failure`

Failure class: the notebook chooses code or widgets because Jupyter can, not
because the exercise needs them.

Reject when:

- concept explanation prompts are forced into code;
- every question gets a widget;
- a Markdown-only question would test the concept better;
- a widget manipulates UI parameters without manipulating a mathematical
  object or feedback state.

### `pattern_card_failure`

Failure class: a reusable mother structure appears but the notebook does not
train recognition across disguises.

Reject when:

- projection coefficients are given as isolated formulas;
- infinitesimal composition appears only as an Euler formula trick;
- vector-space judgment only lists definitions instead of closure tests;
- inner products are used without space, measure, weight, or conjugation
  awareness.

### `demo_gallery_failure`

Failure class: the notebook is a set of polished demos with weak exercises.

Reject when:

- most cells ask the student only to run or observe;
- there is no prediction, calculation, modification, or explanation task;
- optional extensions dominate the main learning path.

### `mathematical_causality_failure`

Failure class: formulas and plots appear correct, but the code does not expose
the causal chain the student needs to learn.

Reject when:

- function-to-vector sampling skips components, products, sums, or limits;
- Fourier coefficients are shown without projection computation;
- scalar multiplication, rotation, conjugation, or limits are presented as a
  convenient curve swap.

### `interaction_stability_failure`

Failure class: widgets make the notebook unstable, jumpy, noisy, or fragile.

Reject when:

- slider changes emit repeated warnings or print logs;
- output area height changes during interaction;
- matplotlib widgets redraw continuously without need;
- widget state contains hidden exceptions.

### `output_hygiene_failure`

Failure class: committed outputs contain tracebacks, warning spam, giant dumps,
or unreadable fonts.

Reject when:

- Chinese labels render as boxes;
- warnings dominate the output area;
- saved output size is large without a static-viewing reason;
- GitHub/static readers see broken or empty key content.

### `presentation_boundary_failure`

Failure class: student-facing notebook cells expose the creator's production
intent, review logic, pipeline compliance, or implementation workaround instead
of stating the mathematical task.

Reject when:

- Markdown explains that the notebook is "not a transcript" or describes the
  author's teaching design instead of giving the student a problem action;
- visible text says a widget is "stable", "not using interact", "fixed-height",
  or otherwise explains a UI workaround;
- visible prose says a plot is "only feedback" or "not the main content"
  instead of instructing the student what to compute and check;
- cells mention the skill, pipeline, review gate, audit, draft status, or
  production candidate status in material meant for students.

### `source_boundary_failure`

Failure class: drafts, generated files, production notebooks, and review
records are mixed.

Reject when:

- rejected notebooks remain at `notebook.ipynb`;
- draft attempts are presented as final;
- validation outputs or caches are committed as source.

### `review_gate_bypass_failure`

Failure class: the notebook is handed off after an informal review without a
hard receipt showing required reading, candidate flags, ranked quality sweep,
regression checks, and issue/fix status.

Reject when:

- the reviewer says "looks good" without a red-flag ledger;
- no `review_gate.py` state exists for a production candidate;
- candidate flags remain open or are silently dropped;
- fixes are described in chat but not tied to issue IDs or evidence.

## Concrete Regression Cases

### `output_area_jitter_from_widget_warnings`

Failure: a matplotlib widget emits repeated font/glyph warnings each time a
slider changes. The output area grows and shrinks, so the plot jumps.

Fix:

- configure Chinese-capable fonts;
- suppress known benign font warnings after fixing the font path;
- use fixed-height `interactive_output` or `widgets.Output`;
- avoid noisy `print` in widget callbacks;
- set sliders to `continuous_update=False` unless continuous motion is
  deliberately required.

### `creator_intent_text_in_student_notebook`

Failure: a notebook repairs a real engineering problem, but then explains the
repair in the student-facing body: "this slider is stable", "we avoid interact
because old drafts flickered", "this notebook is not X but Y", or similar
authoring commentary. The implementation is improved, but the artifact still
feels like the agent is narrating its design process to the learner.

Fix:

- keep engineering choices in helper code, code comments, contracts, review
  reports, and issue JSON;
- rewrite visible Markdown as direct student action: predict, compute, vary a
  parameter, compare, diagnose, or summarize;
- during review, scan Markdown and widget labels for pipeline/review/workaround
  terms before passing the notebook;
- record repeated cases as `presentation_boundary_failure` so future authors
  check it before writing prose.

### `hidden_widget_state_error`

Failure: notebook execution succeeds, but widget metadata stores an exception
from an `interactive_output` callback, so reopening the notebook shows a hidden
error state.

Fix:

- inspect widget state during audit;
- align widget control names with function parameters;
- execute and audit the saved notebook, not only the visible cell status.

### `external_worker_notebook_direction_drift`

Failure: an external worker creates a broad notebook from topic names instead
of the course direction. It may be runnable, but it does not match the intended
teaching style.

Fix:

- move the attempt to `draft/`;
- require a notebook plan before authoring;
- have the coordinator own pedagogy and exercise direction;
- assign external workers only bounded tasks after the plan is concrete.

### `visualization_gallery_instead_of_problem_session`

Failure: the notebook treats Jupyter as a place to reproduce or extend video
visuals, with plots and widgets as the primary content.

Fix:

- rewrite goals as "Student can ..." abilities;
- move visualizations after prediction or calculation;
- add concept discrimination, standard calculation, error diagnosis, and
  transfer layers;
- keep only interactions that improve feedback, structure recognition, or
  object manipulation.

### `projection_pattern_not_trained`

Failure: Fourier or orthogonal-expansion material asks students to compute
coefficients without training the projection template.

Fix:

- add the mother formula `c_n = <phi_n, f> / <phi_n, phi_n>`;
- ask for basis, inner product, interval, weight, conjugation, and denominator;
- include disguised formulas such as normalized sine basis, weighted
  Sturm-Liouville form, Legendre coefficient, and a non-projection distractor.

### `infinitesimal_exponential_pattern_lost`

Failure: Euler formula or matrix exponential content is presented as a formula
instead of the thought pattern "small linear changes compound into an
exponential finite transformation."

Fix:

- train scalar, complex, and matrix forms side by side;
- ask students to identify the generator and small-step factor;
- include at least one non-example where the exponentiation limit does not
  apply.

### `zero_flag_polite_review`

Failure: a reviewer returns a pass with no concrete objections, no ranked
quality comparison, and no explanation of why the notebook was low risk.

Fix:

- use `review_gate.py template-review`;
- select the appropriate risk tier;
- record enough candidate flags for that tier;
- close every flag through fix, explicit pardon, or not-applicable evidence;
- keep the ranked notebook-quality sweep even when the final verdict passes.
