# Math Object Driven Animation

Core principle: **drive animation with real mathematical objects, then use honest visualization optimizations for readability**.

Do not imagine a "roughly nice" motion and wrap math around it later. First define the object, parameter, map, trajectory, field, metric, coordinate system, tensor, or network computation. Then let the image be generated from that object.

## Meaning Of Real

"Real" does not mean every object must be drawn at physical scale, original dimension, or full density. It means the causal logic behind the picture comes from mathematics.

Examples:

- Complex multiplication must be driven by modulus and argument change.
- Vector rotation must be driven by an angle parameter.
- Function graphs must be driven by the function or function family.
- Function scalar multiplication must be driven pointwise. For `c=-1`, the
  graph of `f` must become the reflection `(x,f(x)) -> (x,-f(x))` across the
  zero axis; translating or replacing it with an unrelated curve is a factual
  math error.
- Field arrows must be sampled from the actual field, even if length/opacity is display-mapped.

## Multi-Perspective Representations

Many mathematical concepts are not best explained by one diagram. A concept may have several equivalent or complementary representations: algebraic formulas, geometric diagrams, coordinate projections, slices, level sets, vector fields, flow lines, spectra, matrix actions, statistical summaries, and 3D surfaces. Animation should use these perspectives deliberately.

The rule is not "draw many pictures". The rule is: define one core mathematical object, then show multiple views that are all generated from that same object and can be visibly related to each other. The viewer should feel "this is the same thing from another angle", not "this is a new unrelated illustration".

Use multi-perspective representation when:

- One view explains formal structure but not intuition.
- One view shows local behavior while another shows global behavior.
- One view shows algebra while another shows geometry.
- One view shows the original high-dimensional object only through projection or summary.
- The concept is naturally defined by equivalences, such as Fourier transform, convolution, eigenvectors, gradient, metric, curvature, or Hamiltonian flow.

Ways to combine perspectives:

- **Sequential views**: introduce one representation, then transform or camera-move into another.
- **Synchronized split views**: show two views at once with shared moving parameters, such as a sliding convolution window and its output graph.
- **Overlay views**: combine compatible representations, such as contour lines plus height coloring, or vector-field arrows plus scalar magnitude coloring.
- **Inset/local views**: keep the global object visible while zooming into a local slice, tangent, or infinitesimal object.
- **Projection/slice views**: show a high-dimensional or 3D object through projections, level sets, sections, or unfolded slices.

Across perspectives, preserve object identity:

- The same point should remain visibly the same point.
- The same parameter should drive all synchronized views.
- The same function or matrix should generate every diagram.
- The same vector should keep its semantic color and label unless there is a deliberate reason to change it.
- The transition should carry an object, formula part, point, curve, grid, camera, or parameter across the cut.

Examples:

- Complex multiplication: algebraic product, matrix form, grid transform, polar form, and rotation-plus-scale vector motion should all come from `z -> wz`.
- Eigenvectors: unit circle deformation, invariant directions, repeated action `A^n v`, and equation `Av=lambda v` should all come from the same matrix `A`.
- Divergence and curl: arrow field, local area element, flux/circulation integral, and scalar heatmap should all come from the same vector field.
- Fourier transform: time signal, rotating inner product, spectrum point, frequency plot, and reconstruction should all come from the same `f(t)`.
- Convolution: sliding overlap, output point, full output curve, signal filtering, and image kernel view should all come from the same integral or discrete sum.
- Curvature and metric: tangent change, osculating circle, local zoom, unit ellipse, geodesics, and distance wavefronts should all come from the same curve or metric.
- Hamiltonian systems: vector field, phase orbit, energy contour, area element evolution, and Poincare section should all come from the same Hamiltonian.

Audit question: if two views cannot be traced back to the same object, parameter, or computation, either reconnect them mathematically or treat one as a separate analogy rather than a proof-like visualization.

## Restraint And Screen Budget

Multi-perspective views, shared drivers, real media, and mathematical sonification are tools, not defaults. Use the smallest visual system that makes the mathematical idea clear. A single focused coordinate plane, graph, or diagram is often better than three synchronized panels if the extra panels do not remove a real ambiguity.

Add a second view only when it earns its space:

- It reveals a relation the first view hides, such as algebra versus geometry, local versus global, or time domain versus frequency domain.
- It cross-checks the same object in a way the viewer can follow.
- It preserves identity across a transition, slice, projection, zoom, or camera move.
- It prevents a necessary abstraction from becoming misleading, such as a high-dimensional projection or a metric chart.
- It supports pacing without stealing attention from the mathematical object.

Remove or avoid a view when:

- It repeats information already clear in the main view.
- It forces tiny unreadable panels or causes formula/diagram overlap.
- It exists mainly because the technique is available.
- It introduces a new representation without enough time to connect it to the original object.
- It makes the viewer track implementation cleverness instead of the mathematical relation.

Shared drivers do not imply every driver needs many displays. Real media does not imply every concept needs a photo or video. Sonification does not imply every mathematical event needs a sound. The producer's job is to choose the representation budget, then spend it only where it increases understanding.

## Shared Mathematical Drivers

The strongest multi-perspective design is one mathematical state driving several outputs at once. Do not separately animate the left graph, right formula, slider, label, and sound by hand. Define one driver, such as a parameter tracker, sampled array, ODE solution, matrix, tensor, event stream, or time variable, then let every dependent view read from it.

Simple example: for `y = a x^2 + b x + c`, the same trackers `a,b,c` should drive the left curve, the right equation, coefficient labels, vertex/root markers, discriminant status, and any parameter tick sounds. If the formula says `a=2` while the curve was drawn from `a=1.8`, the animation is wrong even if both look good.

Use this pattern for:

- **Fourier analysis**: the frequency `omega` drives the rotating-vector average, highlighted spectrum bin, partial reconstruction, formula term, and optional pitch cue.
- **Eigen decomposition**: one matrix `A` drives the grid transform, unit circle-to-ellipse image, eigenvector highlights, determinant/area meter, and `Av=lambda v`.
- **Gradient descent**: the iterate `x_k` drives the surface point, contour-map point, loss curve, tangent/gradient arrow, and parameter table.
- **PDE evolution**: the time `t` drives the heat surface, contour map, energy/norm graph, boundary flux arrows, and spectrum coefficients.
- **Hamiltonian flow**: the same trajectory time drives phase orbit, local vector arrow, energy readout, preserved area patch, and Poincare-section hit.
- **Probability and CLT**: the sample count or random seed stream drives the histogram, empirical mean path, variance label, theoretical overlay, and confidence-band cue.
- **Neural networks**: the same activation tensor drives the input patch highlight, convolution result, feature map, neuron graph, and class score bars.

Implementation rule: prefer shared trackers, shared arrays, shared functions, and shared event JSON over duplicated calculations. In `timeline.json` or `experiment-log.md`, name the driver and list all visual/audio channels that depend on it. During QC, pause on keyframes where several views should agree.

## Media-Bound Mathematical Transforms

Real photos, video frames, handwriting, scanned pages, or audio clips can make abstract objects more intuitive and playful. They must still be bound to a mathematical domain or data stream. Treat the media as a texture, signal, initial condition, point cloud, or dataset that is transformed by the same map as the mathematical object.

Basic example: to explain a linear map, put a real photo on coordinate paper and apply the matrix `A` to the grid and to the photo's coordinate domain. Rotation, scaling, reflection, and shear should follow `(x,y) -> A(x,y)`, not a hand-tuned image warp. Keep enough grid lines, corner markers, or pinned feature points visible so viewers can read the transformation.

Stronger examples:

- **Complex functions**: place an image texture on the complex plane, then warp selected grid cells, sample points, and the texture by `w=f(z)`. Mark branch cuts or singularities instead of hiding distortions.
- **Fourier/image filtering**: use a real image or audio clip as the signal; show FFT coefficients, filter mask, reconstructed image/audio, and energy loss from the same transform.
- **Convolution and CNNs**: slide a kernel over a real image patch; the highlighted patch, dot product, feature-map cell, and class score should read from the same window position and weights.
- **Heat equation**: use a photo as `u(x,y,0)`, evolve it by the heat equation, and show blur, spectrum decay, and energy curve from the same solution.
- **Fluid flow or diffeomorphism**: advect an image texture with a vector-field flow map while also showing streamlines or particles generated by that field.
- **Optics and lenses**: send a real image through a lens or medium by ray equations; the deformed image, rays, caustic, and focal marker should share the same optical model.
- **PCA or embeddings**: use real images or samples; the low-dimensional point, principal-coordinate sliders, and reconstruction all come from the same coefficients.
- **Special coordinates**: place a map, photo, or grid texture on the original domain, then remap it to polar, spherical, conformal, or curvilinear coordinates with coordinate lines visible.

Media does not replace mathematics. Record the media source path, transform map, driver parameters, and whether the media is a final asset, placeholder, generated reference, or editorial gag. If the media is only decorative, classify it as such; do not let it imply a mathematical claim.

## Honest Visualization Optimizations

Two optimization types are allowed:

1. **Display optimization**: sampling, transparency, logarithmic length scaling, clipping, local zoom, line-width adjustment, or selective emphasis. This changes how the object is shown, not what the object is.
2. **Teaching-parameter optimization**: choose a pedagogical parameter version of the mathematical object, such as a Gaussian beam with a more visible curvature radius. Record that it is a teaching parameter.

Before each shot, state:

- What the mathematical object is.
- Which values are true definitions or computations.
- Which display mappings are scaled, clipped, sampled, faded, zoomed, or exaggerated.
- Whether any optimization changes the mathematical relation being taught.
- Whether the shot needs a note in storyboard, timeline, subtitle, or experiment log.

## Sonification

Sound effects must land on mathematical events:

- Vector reaches target angle.
- Trajectory crosses singularity.
- Integral path closes.
- Matrix transform completes.
- Formula lands as a consequence of a shown relation.

Do not sprinkle sound purely by visual rhythm.

For sound effects beyond what Manim directly supports, export a mathematical event stream and let an external audio script consume it. The event stream can be JSON/CSV and should include time, event type, mathematical object id, position, and relevant parameters such as angle, norm, curvature, energy, or crossing index. External synthesis may use `numpy`, `scipy`, `soundfile`, `ffmpeg`, a sampler, or any other tool, but pitch, volume, pan, timbre, and decay should be derived from the event parameters when the sound is meant to represent mathematics.

Example event:

```json
{"time": 12.48, "event": "vector_reaches_angle", "object": "z_times_i", "theta": 1.5708, "position": [0, 1], "energy": 0.82}
```

This does not ban non-mathematical sound design. Humor, character reactions, UI-like transitions, and atmosphere may use additional editorial sounds if they help the video. The rule is classification: math sonification must be event-driven; editorial sound effects should be recorded as editorial/aesthetic choices and must not pretend to prove or encode a mathematical relation.

## Arrows And Directional Objects

Primary vectors, basis vectors, and field arrows should enter with `GrowArrow`. The shaft and tip should grow as one directed object. Avoid `Create(Arrow)` when it visually looks like "draw a line, then attach a triangle".

Curves, trajectories, circles, and grid lines may use `Create`, because being traced is their natural visual metaphor.

## Infinitesimals And Local Objects

For infinitesimal segments, angles, rotations, linearization, curvature, and local tangent objects:

- Do not enlarge the mathematical object itself just because it is hard to see.
- Keep the true small quantity, such as `Delta theta = theta/N`.
- Use camera zoom, local inset, magnifier, local coordinate rescaling, arrows, or braces to make it visible.
- Label the zoom or local coordinate when necessary.

For infinitesimal angles:

- `Delta theta` must be the angle between two real rays from the same vertex.
- Do not replace it with two floating local line segments.
- The angle should be small enough that a label does not fit in the full view, but not so tiny that the angle is invisible.
- If the label cannot fit, zoom around the vertex; the rays, arc, and label must still be generated from the same `Delta theta`.
- Adjust local line width if zoom makes strokes too thick, but do not detach the object from its true vertex.

## Formula And Visual Hierarchy

Formula styling is part of the display mapping:

- Bare formula: ordinary definition, intermediate variable, coordinate label, or formula already in context.
- Underline: only the currently active short formula or a formula that needs a temporary eye anchor; at most one active underline per shot.
- Frame: only a conclusion, key proposition, formula group, contrast structure, or right-side derivation panel.
- Special color: bind color to semantic role, not decoration.

Do not use color + underline + frame together on a short formula unless it is the only focus of the shot.

## Anti-Fabrication Audit

After each segment, audit:

- List all key motions, transformations, trajectories, angles, lengths, formulas, and sound cues.
- For each, ask whether it is driven by a real mathematical object, parameter, function, matrix, ODE, vector field, metric, tensor, or array computation.
- If multiple perspectives are used, list the shared object or parameter that connects them and how the transition preserves identity.
- Mark any hand-written endpoint, path, angle, curve, or velocity as fake animation unless it is an explicitly documented display mapping.
- Describe each display mapping: scale, projection, sampling, opacity, line width, local zoom, pedagogical parameter.
- Extract keyframes and inspect overlap, label mismatch, floating objects, incorrect arrow origins, filled arcs, thick zoomed strokes, and stale objects.
- If fake animation is found, rebuild the mathematical driver before discussing aesthetics.
- For scalar multiplication, conjugation, dot products, and other algebraic
  operations, inspect sample correspondences. If the screen cannot identify
  which original sample became which transformed sample, the operation is not
  visually proven even if the final formula is correct.
