# Layered Cognitive Staging

Use this reference when designing or revising a scene. It governs the animation author, not just the reviewer.

## Core Definition

Treat the screen as the learner's external working memory. Animation is a changing mathematical explanation, not motion added to narration.

Design from outside inward:

1. **Learning move**: decide what new mental operation the learner should be able to perform after the scene.
2. **Macro stage**: divide the whole screen into regions whose spatial relationship expresses the mathematical relationship.
3. **Regional refinement**: make each region locally informative with details that encode real mathematical variation.
4. **Micro choreography**: synchronize attention, formula tokens, labels, and transitions with spoken reasoning.
5. **Mechanical finish**: let scripts reject overlap, illegible type, subtitle intrusion, stale objects, and timing drift.

Never reverse this order. Token highlights cannot rescue a scene whose regions do not explain the idea.

## 1. Start From The Learner's State

Before choosing a graph or formula, write five things:

- what the learner can safely know before this scene;
- the exact claim or operation the scene adds;
- the most likely wrong interpretation;
- the visible evidence that corrects it;
- what a learner should be able to point to or predict when the scene succeeds.

At every beat, assume the learner knows only what has already been shown. A conclusion is permitted only after its visual evidence exists. This is the novice-state ledger.

Prefer a visible causal chain:

`parameter or choice -> mathematical action -> changed object -> conclusion`

If one arrow exists only in the author's head, the scene is incomplete.

## 2. Compose The Macro Stage

Assign each major region one teaching job, not merely one object type. Examples:

- parameter space: where a choice is made;
- object space: what that choice produces;
- process space: how the object changes;
- formula memory: which symbolic relation remains available;
- comparison space: which invariant or contrast is being tested.

The arrangement of regions should itself state part of the argument. Left-to-right can mean input-to-output; top-to-bottom can mean abstraction-to-instance; aligned rows can mean corresponding cases. Do not divide the screen into arbitrary boxes and fill them afterward.

The provided S-plane example works because its regions have different but connected jobs:

- the large left atlas makes many parameter choices simultaneously inspectable;
- each small graph makes the claim "one point encodes a whole function" locally concrete;
- the upper-right trace exposes one selected function in ordinary time;
- the lower-right complex-plane path exposes the same function through phase and magnitude;
- shared color and selection connect all three without explanatory prose.

That is semantic density: many details, one idea. It is not decoration.

## The Stage Is A Dynamic Cognitive Topology

Do not treat the macro stage as a permanent grid. Treat it as a time-varying graph:

- a **region** is a cognitive role with owned mathematical objects and an honest display mapping;
- a **stage state** says which regions are active, where they are, and which one currently carries the learner's task;
- a **relation** says how two regions share a driver, object identity, or inference;
- a **stage transition** changes this topology because the learner's task has changed.

This abstraction covers split screens, region replacement, local enlargement, full-screen promotion, camera travel, object rotation, coordinate changes, slices, projections, and high-dimensional views without listing them as separate tricks. They are all implementations of one operation:

> Change the display mapping and allocation of attention while preserving the mathematical identity and the learner's orientation.

Plan transitions by invariants, not by effect names:

1. **Pedagogical trigger**: what new question makes the old stage allocation insufficient?
2. **Focus transfer**: which region becomes primary, and which regions become context, breadcrumbs, or leave?
3. **Identity carrier**: which object, color, axis, parameter, or motion makes the learner recognize continuity?
4. **View mapping**: what changes in the mapping from the same mathematical object to the screen?
5. **Context policy**: what must remain long enough to preserve orientation, and what must disappear to release working memory?
6. **Completion test**: what visible state tells the learner that the new viewpoint is established?

For example, when three regions establish a correspondence and one now needs detailed treatment, do not cut to an unrelated full-screen redraw. Retire or quiet the two supporting regions, preserve a meaningful identity carrier, continuously promote the chosen region into the released space, then add its finer internal structure only after the new scale is stable. The same logic applies whether the implementation is a 2D zoom, a camera move, a three-dimensional rotation, a change of projection, or a high-dimensional slice.

A valid transition preserves four continuities:

- **object continuity**: the learner can identify what stayed the same;
- **causal continuity**: the transition occurs because the mathematical question changed;
- **spatial continuity**: the learner can track where the focus went, or receives an explicit new anchor;
- **semantic continuity**: a display change is not falsely presented as a change in the underlying mathematics.

The stage may transform freely when these continuities hold. A fixed layout is not safer if it forces cramped formulas or leaves dead regions on screen.

## Use A Generative Visual Grammar, Not An Effect Catalog

Represent every shot with three layers:

`screen(t) = display(math_state(t), view_mapping(t), attention(t))`

- **math state M**: the actual function, parameter, sample, transformation, proof state, or geometric object;
- **view mapping D**: how that state is projected, sliced, scaled, arranged, colored, sonified, or mapped to the screen;
- **attention A**: which relation is primary, which objects remain as context, and where the next handoff goes.

This is a generative grammar:

- change `M` when the mathematics changes;
- change `D` when the same mathematics needs a more revealing representation;
- change `A` when the learner's question or working-memory allocation changes;
- change several together only when their causal relationship is explicit.

Make this distinction executable. Every stage state and runtime cue must expose comparable identifiers for `M`, `D`, and `A`. The CLI derives the actual change vector from before/after values and rejects a declared vector that does not match. A view-only change must preserve the math-state identity; an attention-only change must preserve both the math state and display mapping; a mathematical change must name its real driver.

Also separate the mathematical parameter from the screen parameter. A limit object may use `epsilon_math -> 0` while a local inset uses a readable `epsilon_screen`; the latter belongs to `D`, never to `M`. For a keyhole contour, the small circle and the nearly coincident outgoing/return paths may be enlarged or separated by a declared local zoom or nonlinear magnifier while winding number, orientation, singularity exclusion, and limiting family remain invariant. If the curve itself is deformed, declare `equivalent_deformation` and verify the equivalence basis. The author may invent any representation, but the plan and runtime must expose what stayed true, what was visually distorted, and what the learner is forbidden to infer from that distortion.

The author is therefore not asked to select from a menu of zooms, rotations, split screens, or camera moves. The author is asked:

1. What relation is currently invisible or hard to inspect?
2. What must remain invariant so the learner recognizes the same mathematical object?
3. What display mapping would make that relation perceptible?
4. What context must remain, shrink, or leave so attention can move there?
5. What visible test would prove that the new representation helped?

The implementation may use any visual language that answers those questions and respects the continuity invariants.

For complex or repeatedly rejected scenes, generate lightweight stage hypotheses before coding. These are not multiple polished animations. They are materially different answers to the representational problem. Compare them by:

- causal visibility;
- identity continuity;
- external working-memory support;
- local inspectability;
- visual economy;
- capacity for truthful refinement.

Select one and record why the others fail. This gives the same author Agent room to invent without paying for several rendering or review agents.

Retrieve precedents by **problem signature**, not by effect name. Search for the learner operation, hidden relation, mathematical driver, identity invariant, and attention transfer. A useful old scene may use a completely different camera technique while solving the same representational problem.

## 3. Refine Each Region Locally

After the wireframe composition works, ask of every region:

- What local question does this region answer?
- Which mathematical variation can be made inspectable here?
- Which detail makes the object more concrete for a novice?
- Which detail would be meaningless if the narration were muted?

Add a detail only when it passes all four tests:

1. it encodes a mathematical quantity, case, invariant, or correspondence;
2. it strengthens the region's teaching job;
3. it preserves the global visual hierarchy;
4. it can be explained by pointing, not by adding producer commentary.

Useful refinement includes small multiples, truthful samples, local axes, selected cases, residue trails, error curves, partial sums, and token ancestry. Avoid empty frames, decorative fills, ornamental arrows, and repeated boxes whose only purpose is to make the screen look busy.

## 4. Choreograph Attention At The Micro Level

The eye should have a route, not a scavenger hunt.

- Keep one dominant focal change per beat. A comparison may use two only when both are visibly coupled.
- Let context remain quieter while the active object changes through brightness, color, motion, or isolation.
- Highlight the mathematical term being spoken, but only when the highlight identifies an operation or correspondence.
- Begin the visual evidence just before or with the spoken claim; do not reveal the proof several seconds later.
- End an object's visual ownership when its reasoning job ends.

Formula derivation is spatial choreography:

- preserve previous lines needed by the next inference;
- align equal roles vertically or horizontally;
- transform the same token when its identity persists;
- show where factors come from and where they go;
- bind a spoken term to its exact token or visual object;
- use the rest of the screen for the mathematical action that makes the formula true.

Typesetting quality is part of mathematical identity. Render each displayed row as one LaTeX expression, then isolate substrings for semantic color; do not assemble a row from independently spaced visual fragments. Align repeated rows by a mathematical anchor such as the equals sign. Emphasis must be readable throughout its motion, not merely at the final frame. Prefer a restrained color/brightness pulse, a soft local halo, or a small scale pulse with a perceptible hold. Do not use a rapidly traced bounding box: its partial intermediate frame reads as an accidental bracket. If scale is used, capture the pre-emphasis geometry and prove that the exact bbox and baseline return afterward.

Cross-region correspondence does not automatically require an arrow. Prefer, in order: a continuous transform of the same object, synchronized changes in matched colors, a compact formula bridge, or a short routed connector in free space. A long straight arrow through an active graph is a failure even when its endpoints are semantically correct.

Every stage transition needs an inspected midpoint. The old and new allocations may both be partially present while interpolating, but they may not read as two complete competing layouts. Preserve one identity carrier, settle the new geometry, and only then add new detail or formula emphasis. Treat the move as one continuous trajectory. A single smooth interpolation is preferred; if telemetry capture requires two animation segments, use matched ease-in/ease-out halves whose midpoint velocities agree instead of two default-smooth segments that each stop.

Do not use one formula slot as a replacement machine. Do not highlight every syllable. Highlight structure.

## 5. Separate Semantic Work From Mechanical Work

The author owns:

- the learner-state model;
- the mathematical driver;
- the semantic topology of the stage;
- the choice of truthful local refinements;
- the attention route and object identity;
- the aesthetic rhythm of the explanation.

Automation owns:

- frame and subtitle-zone bounds;
- region and container overflow;
- text and formula collisions;
- minimum readable type;
- unapproved overlaps and cramped spacing;
- narration-to-visual lag;
- unjustified long fades and transitions;
- stale objects after semantic ownership ends;
- excessive simultaneous focal objects;
- missing QC coverage at decisive beats.
- missing QC coverage inside every stage transition;
- formula rest-geometry drift after emphasis;
- cross-region connectors that cross protected mathematical objects;
- clause-level visual onset drift for major claims.

Automation runs four gates in parallel, not as substitutes:

- layout asks whether every visible object is legible, separated, bounded, and professionally staged;
- mathematical-object truth asks whether the visible carrier occupies the exact state, coordinate, identity, and operation claimed by the mathematics;
- timing/attention asks whether the learner is looking at the right completed evidence when the clause names it;
- novice causality asks whether cause, action, result, and permitted inference are visible in order.

For every primary object, write an executable invariant before coding. Do not animate a group merely because its overall center reaches a target; animate and measure the mathematical carrier whose coordinate or state carries the claim. Labels, braces, and annotations are dependents. A layout pass cannot certify a false mathematical state, and a correct mathematical state cannot pardon an ugly or colliding layout.

The author must export runtime telemetry for these checks. A manually asserted "looks fine" audit is not evidence.

## Authoring Passes

### Pass A: Learning Contract

Write the learner state, core claim, misconception, visible evidence, and success test. Reject the scene if these are vague.

### Pass B: Grayscale Wireframe

Place only major regions and primary objects. Verify that region relationships communicate the argument before adding formulas or polish.

### Pass C: Mathematical Animatic

Connect all decisive changes to real drivers. Verify cause, operation, and result with low-resolution output.

### Pass D: Regional Refinement

Add small multiples, samples, local axes, formula memory, or other semantically owned detail. Keep the primary hierarchy intact.

### Pass E: Micro Choreography

Bind every major spoken clause to its own object change, then tune attention handoffs, holds, transformations, and exits. Record formula rest geometry before emphasis and add a QC anchor at every stage-transition midpoint.

### Pass F: Deterministic Preflight

Export telemetry and run `validate-authoring-qc`. Fix every mechanical failure before rendering the review candidate.

## Final Author Test

Before handoff, answer without referring to intention:

- What should a novice look at first, second, and third?
- What changed mathematically at each step?
- What can the learner infer now that was not inferable one beat earlier?
- Which local detail makes the idea more inspectable rather than merely prettier?
- With narration muted, is the central correspondence still visible?
- With the picture hidden, does the narration still name the same objects and operations?
- Can a novice teach the claim back in one sentence and predict what changes when the scene driver changes?

If these answers are not concrete, return to the earliest failing pass rather than polishing later symptoms.
