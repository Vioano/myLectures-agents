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
- a collapsible answer table appears without a visible unfinished table or
  equivalent question first;
- a worked solution, complete derivation, or final numerical result is visible
  before the student is asked to compute, fill, predict, or diagnose;
- answer checks validate only the final number when the structural decision is
  the learning target.

### `cell_modality_failure`

Failure class: the notebook chooses code or widgets because Jupyter can, not
because the exercise needs them.

Reject when:

- concept explanation prompts are forced into code;
- a fixed calculation is printed by Python when a Markdown equation or table
  would be clearer;
- every question gets a widget;
- every question gets a fill-in table, even when the task is a single
  derivation or short calculation;
- every standard calculation becomes a chain of fill-in blanks or identical
  open-work templates instead of varying the question form by the knowledge
  being tested;
- an ordinary written calculation area is rendered as a custom bordered HTML
  box instead of plain Markdown spacing;
- a Markdown-only question would test the concept better;
- a widget manipulates UI parameters without manipulating a mathematical
  object or feedback state.
- long setup, font, style, path, or helper code is exposed as a main notebook
  cell instead of being hidden in a helper module.

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
- visible headings, widget labels, or feedback text preserve agent scaffold
  language such as "Concept Check", "Pattern Card", "Optional Lab",
  "Stable Lab", "raw sum", "模式卡", "隐藏奇点雷达", "小型训练器",
  or internal error-mode names instead of polished course-facing Chinese.
- visible code or output reads like a debug dump, for example `[OK]`,
  `[CHECK]`, `len1_sq`, `is_projection`, raw dictionaries, or English plot
  labels that are not mathematical notation.
- visible Markdown or code string literals contain obvious AI-writing residue:
  em/en dashes, generic signposting, "not just X but Y" slogans, inflated
  "core/key/deep" framing, chatbot-like English phrases, or over-scripted
  scaffold names.
- visible prose uses implementation slang or casual metaphors such as "throw
  pixels forward", "push it over", "patch the holes", "just shove it in",
  "magic", "black box", or similar wording where a precise mathematical or
  computational relation is needed.
- visible prose explains backstage implementation details, such as image
  resampling, inverse sampling, callback mechanics, output positions, source
  pixels, or UI plumbing, when the student task is a mathematical action rather
  than inspecting that implementation.
- visible headings describe packaging, revision sheets, or content format, for
  example "one-page exam summary" or "knowledge checklist", instead of naming
  the mathematical action the student should perform.
- visible headings use crude, chatty, or contempt-flavored wording such as
  "abstract nonsense", "玄学", "套路", "废话", or similar phrases. Even if
  the intended point is mathematically reasonable, the student-facing heading
  should name the action or criterion being trained.

### `source_boundary_failure`

Failure class: drafts, generated files, production notebooks, and review
records are mixed.

Reject when:

- rejected notebooks remain at `notebook.ipynb`;
- public notebooks are hidden under `notebooks/NNNN-slug/notebook.ipynb`
  instead of exposed as `notebooks/NNNN-slug.ipynb`;
- draft attempts are presented as final;
- validation outputs or caches are committed as source.

### `review_gate_bypass_failure`

Failure class: the notebook is handed off after an informal review without a
hard receipt showing required reading, candidate flags, ranked quality sweep,
regression checks, and issue/fix status.

Reject when:

- the reviewer says "looks good" without a red-flag ledger;
- no `review_gate.py` state exists for a production candidate;
- the review cites an audit JSON whose status is not `pass`;
- the review claims subagent/independent review without
  `reviewer_independence` evidence;
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

### `student_visible_scaffold_language`

Failure: student-facing notebook headings, widget labels, plotted labels, or
printed feedback preserve scaffolding vocabulary from the production process or
from an external generator, for example "Concept Check", "Pattern Card",
"Optional Lab", "Stable Lab", "raw sum", `missing_sign`, "target x", "模式卡",
"隐藏奇点雷达", "封闭性扫描", or "小型训练器". The notebook may be
mathematically correct, but the surface language looks like a draft artifact
rather than a finished course companion.

Fix:

- rewrite visible labels as polished course-facing Chinese;
- use direct mathematical action in headings: "判断封闭性", "先看最近的复奇点",
  "拆出基函数、内积和分母";
- keep reusable structure names only when they are truly course vocabulary, and
  introduce them as mathematical tools rather than production tags;
- scan Markdown plus code string literals, not just rendered Markdown, because
  plot labels, widget labels, and feedback text usually live inside code cells;
- reject the candidate if visible scaffold language survives in a public
  notebook.

### `ai_writing_pattern_public_text`

Failure: the notebook has mathematically plausible prose, but the surface
still sounds like generated courseware: generic signposting, "not just X but Y"
parallelism, inflated "核心/关键/深层/系统性" framing, em/en dashes, or
chatbot-like English filler. This is a student-facing polish failure, not a
minor wording preference.

Fix:

- run the public Markdown and code string literals through the hard
  `$humanizer` subset in `audit_notebook.py`;
- rewrite as direct course prompts: compute, judge, compare, diagnose, or
  explain;
- use short ordinary Chinese unless a term is real course vocabulary;
- if a previous user essay or course note is available as a style sample, use
  it for the human review pass, but keep the hard script focused on detectable
  residue rather than subjective taste.

### `student_visible_engineering_jargon`

Failure: a student-facing notebook sentence explains an implementation with
casual engineering slang or metaphor, for example saying that pixels are
"thrown forward" when describing image resampling. The sentence may point at a
real computational issue, but the surface sounds like an internal development
note rather than course prose.

Fix:

- rewrite the sentence as a precise relation between mathematical objects;
- keep implementation notes only when the student is meant to inspect that
  implementation;
- name required conditions, such as `w != 0` before using `z = z' / w`;
- for image transforms, describe forward mapping and inverse sampling directly:
  inverse sampling chooses an output position, finds its source position, then
  samples the source image; forward mapping may leave some output positions
  uncovered;
- reject recurring Chinese implementation slang such as "往前扔", "丢过去",
  "搬过去", "乱采", "补洞", and "糊边" in student-facing text;
- add repeated slang terms to `audit_notebook.py` under
  `student_visible_engineering_jargon`.

### `student_visible_backstage_implementation_detail`

Failure: a student-facing notebook sentence explains the implementation behind
a visual or widget even though the implementation is not the learning task. In
the complex-number image experiment, wording such as "image resampling",
"inverse sampling", "output position", "read the source image color", or
"source pixels are uncovered" belongs backstage. The learner should see the
mathematical action: treat image positions as points in the complex plane and
watch multiplication by `w` scale and rotate them.

Fix:

- delete implementation prose when it is not part of the exercise;
- replace it with a mathematical task, prediction, or observation target;
- keep sampling, callbacks, output-height control, font handling, and other
  mechanics in code comments, helper modules, contracts, review reports, or
  issue JSON;
- audit public Markdown and code string literals for implementation phrases
  such as "图像重采样", "反向采样", "反着算", "输出位置", "原图颜色",
  and "原像素".

### `student_visible_packaging_heading`

Failure: a student-facing heading names the packaging format instead of the
mathematical action, for example "一页考试总结", "考试速查", "知识清单", or
"总结页". These headings make the notebook feel like a generated study pack
or production outline. They do not tell the student what structure to use.

Fix:

- rewrite the heading as a concrete action: "判断空间题：封闭、内积、完备",
  "展开题先问：空间、内积、基底、归一化", or "做题前先拆：模、角、矩阵、最近奇点";
- keep exam alignment in the exercise design and review docs, not as a generic
  public label;
- add recurring packaging titles to `audit_notebook.py` so future drafts are
  rejected before handoff.

### `student_visible_crude_heading`

Failure: a student-facing heading tries to sound lively by using a crude or
chatty negative phrase, for example "完备性不是抽象废话". The problem is not
only tone. The heading tells the student what the author thinks of a concept
instead of naming the mathematical judgment the student should make.

Fix:

- rewrite the heading as a task or criterion, such as "完备性看极限是否还在空间里";
- keep casual contrast out of section titles unless it is already stable course
  vocabulary;
- add repeated crude heading words to `audit_notebook.py` under
  `student_visible_crude_heading`.

### `student_visible_answer_not_collapsed`

Failure: a notebook asks a question and immediately shows a full answer table
in the visible flow. The answer may be correct, but the student can read past
the question without first committing to a judgment.

Fix:

- keep the prompt visible and put answer tables under `<details>`;
- use a short summary label such as "对照答案" or "参考判断";
- do not fold the original question into the answer block;
- reject bare answer headings like "对照答案：" or "参考答案：" when they are
  not inside a collapsible block.

### `answer_table_without_prompt_table`

Failure: a notebook hides an answer table in `<details>`, but the visible part
does not first give the student a table to fill or an equivalent question. The
surface looks cleaner than a bare answer dump, but the exercise still starts
from the answer rather than from the student's action.

Fix:

- before a collapsible answer table, show the same rows with blank cells or
  explicit prompts for the decisions being trained;
- keep the answer table inside `<details>` as feedback, not as the first
  encounter with the task;
- audit `<details>` blocks with summaries such as "对照答案", "参考答案",
  "参考判断", or "参考拆解" and reject them when no incomplete table or
  fill-in prompt appears before the solution.

### `visible_worked_solution_before_attempt`

Failure: a static exercise gives the full computation in the visible notebook
body before the student has a chance to attempt it. This includes prose such as
"直接算", "两列直接算", "标准结果", "前几项是", or a paragraph that immediately
derives the final coefficient. It is the same failure as an answer table
without a question, but in derivation form.

Fix:

- first show the task: blanks, a short list of quantities to compute, a table
  to fill, or a prediction prompt;
- put the worked computation inside `<details>` after the prompt;
- keep the visible path as problem statement -> student action -> optional
  feedback, not problem statement -> solution;
- make the audit scan the visible text before `<details>`, not only answer
  table headings.

### `prompt_table_overuse_for_derivation`

Failure: after being told not to expose answers, the notebook turns ordinary
derivations and short calculations into blank tables such as "步骤 / 你要得到的
结果" or "量 / 结果". The answer is no longer exposed, but the exercise surface
becomes a repetitive worksheet. A derivation should read like a mathematical
path, not like every cell has been forced into the same table mold.

Fix:

- use tables for comparison, matching, classification, or many-case structure
  recognition;
- use numbered prompts, equation blanks, or a compact answer checker for a
  single calculation or derivation;
- when repairing answer exposure, choose the cell shape from the mathematical
  action rather than replacing all answers with blank tables;
- audit visible Markdown for generic prompt-table headers such as "步骤 / 你要
  得到的结果", "量 / 结果", "问题 / 结果", or "对象 / 结果".

### `mechanical_fill_blank_overuse`

Failure: after rejecting answer dumps and table overuse, the notebook turns
standard calculations into a sequence of tiny blanks. This is still mechanical:
the student is no longer choosing the solution structure, only filling slots
chosen by the author.

Fix:

- use fill-in blanks only when one missing object is the target, such as a
  denominator, sign, parity, or normalization factor;
- for calculation/proof questions, give the problem, a short list of required
  ingredients, and a plain Markdown working area made from ordinary blank
  lines;
- keep the reference solution collapsed;
- audit visible Markdown for cells with three or more equation blanks before
  the solution block.

### `styled_answer_box_chrome`

Failure: after rejecting fill-in and table overuse, the notebook adds a
bordered HTML answer box for ordinary written work. That is still an
unnecessary UI template. For a calculation or proof prompt, the student-facing
surface should read like course notes: prompt, space to work, then a collapsed
reference solution.

Fix:

- write the prompt in normal Markdown;
- leave several blank lines before the `<details>` solution block when a
  written working area is useful;
- do not add custom borders, rounded boxes, min-height divs, textarea-looking
  blocks, or other answer-box chrome unless the exercise truly requires typed
  input and checking;
- make `audit_notebook.py` reject styled answer boxes as
  `cell_modality_failure/styled_answer_box_chrome`.

### `single_question_form_overuse`

Failure: a notebook technically has problems before answers, but too many
exercises share the same surface form: all tables, all blanks, all answer
boxes, all choice prompts, or all code checks. The result feels like an agent
converted everything through one template instead of choosing an assessment
form.

Fix:

- map question form to knowledge type: choice/matching for discrimination,
  open calculation for standard computation, table for multi-case comparison,
  wrong-solution repair for error diagnosis, widget/plot only after a
  prediction or calculation;
- in review, scan adjacent exercises and reject three repeated surfaces
  without a mathematical reason;
- keep the main path varied but not decorative.

### `object_level_experiment_missing_user_input`

Failure: an object-level notebook experiment uses only a built-in demo object
when the student should be able to bring in their own object. For the complex
image-coordinate experiment, using only a synthetic demo image weakens the
point that every pixel position can be treated as a complex number.

Fix:

- keep a default demo object for static execution;
- add a user input route such as image upload when the experiment is about
  transforming an arbitrary object;
- preserve stable widget behavior: fixed output height, no warning spam, and
  deterministic fallback when no upload is provided.

### `markdown_table_math_pipe_break`

Failure: a Markdown table contains TeX with raw vertical bars, such as `$|x|$`
or `$x(\pi-|x|)$`. The `|` characters are interpreted as table separators by
many renderers, so the formula splits across cells or renders as literal
fragments.

Fix:

- write absolute values as `\lvert x\rvert` inside Markdown tables;
- escape pipe characters if a raw bar is unavoidable;
- audit Markdown tables for TeX pipe characters before handoff.

### `debug_dump_cell_surface`

Failure: a notebook cell technically checks the right mathematics, but the
student-facing surface is a code/debug artifact: long setup blocks, raw
dictionaries, keys such as `len1_sq`, `[OK]`/`[CHECK]` prefixes, English labels
such as "unit circle", or implementation-oriented table fields.

Fix:

- move reusable setup, style, font, path, and widget boilerplate into helper
  modules;
- print compact course-facing feedback in Chinese;
- replace raw dictionaries with short equations, tables, or sentences;
- keep code cells only when reading or modifying the code is part of the
  mathematical task;
- add audit patterns for repeated debug-output labels.

### `static_calculation_forced_into_code`

Failure: a notebook uses a code cell only to compute fixed values that could
be stated more clearly as equations or a table, for example looping over three
hand-checkable cases and printing results. The cell has no parameter
interaction, no visualization, no answer input, and no student-editable
calculation.

Fix:

- move fixed results into Markdown equations or tables;
- keep code only when the student modifies an input, receives meaningful
  feedback, or manipulates a mathematical object;
- if a computation is meant to build intuition, turn it into a plot, widget,
  randomized variant, or answer checker after the student predicts first;
- audit code cells with `print` or `feedback` but no visual, widget, input, or
  editable answer target as `cell_modality_failure/static_result_dump_cell`.

### `deep_generic_notebook_path`

Failure: the public notebook is stored at
`notebooks/NNNN-slug/notebook.ipynb`, mixing the student-facing artifact with
episode README, draft, review, and issue-control files. The path is harder to
open, and it encourages future agents to treat production-control scaffolding
as part of the public notebook surface.

Fix:

- publish current candidates as `notebooks/NNNN-slug.ipynb`;
- move README, contracts, drafts, review gates, human/agent feedback, and issue
  JSON to `episodes/NNNN-slug/`;
- update review reports and issue JSON to point at the shallow public notebook;
- make `audit_notebook.py` flag the old deep generic path as
  `source_boundary_failure`.

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
