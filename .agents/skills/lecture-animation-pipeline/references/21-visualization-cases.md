# Visualization Cases

Use these standard solutions to test whether a Manim plan follows the mathematical-object-driven philosophy.

## Infinitesimal Segment, Angle, Or Rotation

Problem: show `dx`, `h`, `Delta theta`, `theta/N`, or `1+i theta/N`.

Standard solution:

- Define the small quantity first: point `x` to `x+h`, two rays from one vertex, or rotation by `Delta theta = theta/N`.
- Make it teaching-visible: about 1 to 5 degrees, or total angle divided by `N` with `N` consistent with displayed formula.
- Keep it attached to the original structure: curve, axis, tangent, path, vertex, or rotation center.
- If the label does not fit, zoom, use an inset, use an arrow, or use a brace. Do not redraw a disconnected local version.
- In zoomed view, the label, arc, and rays must still come from the same small quantity.
- For infinitesimal rotation, distinguish exact circular arc, tangent approximation, and error term by color or stroke.

Pass condition: the small object remains connected to the original mathematical structure.

## 2D Vector Field With Huge Magnitude Range

Problem: integer grid arrows for `F(x,y)` have vastly different magnitudes.

Standard solution:

- Compute each vector `v_ij = F(i,j)` and magnitude `m_ij = |v_ij|`.
- Use real direction `v_ij/m_ij`.
- Use logarithmic or saturated display length, such as `L_display = L_min + (L_max-L_min) log(1+m/s)/log(1+M/s)`.
- Give nonzero small vectors a minimum visible length.
- For near-zero vectors with unstable direction, draw a dot.
- Use color, opacity, width, or legend to show true magnitude.
- For path integrals, emphasize arrows on and near the path; fade or omit far arrows.

Pass condition: direction is true; length compression is disclosed or visually encoded.

## Symplectic Phase Portrait

Problem: show Hamiltonian phase portraits, orbits, symplectic structure, and phase-volume preservation.

Standard solution:

- Start from the Hamiltonian `H(q,p)`.
- Compute `X_H = J grad H`.
- Show energy contours, phase-flow trajectories, and local area elements advected by the flow.
- Sample arrows around orbits or key energy shells, not the whole plane.
- If speed varies greatly, compress arrow length and use color for true speed.
- Place sound cues at orbit closure, section crossing, or energy-shell transitions.

Pass condition: trajectories come from integrating the equations; area preservation is shown by flow of a local region, not a decorative rotation.

## High-Dimensional Ensemble Phase Space

Problem: show geometry in `R^{6N}` without pretending to draw the full object.

Standard solution:

- Define the true object: high-dimensional point, distribution, energy shell, or sample trajectory.
- Show projections or summaries: `(q_1,p_1)`, PCA, energy distribution, covariance ellipsoid, linked small multiples.
- Use synchronized views to avoid implying one projection is the whole space.
- Generate points, density, or tracks from real samples or real simulated data.
- Record top-k dimension or representative sample selection rules.

Pass condition: the viewer can tell this is a projection or statistical summary, not the high-dimensional body itself.

## Special Coordinate Systems

Problem: show polar, spherical, parabolic, or general curvilinear coordinates.

Standard solution:

- Start from coordinate map `x = x(u,v,w)`.
- Draw regular grid in parameter space, then map it into actual space.
- Drive local basis vectors by partial derivatives `partial x / partial u_i`.
- Use color, width, density, or opacity to show Jacobian changes and coordinate singularities.
- In 3D, prefer surfaces, coordinate curves, tangent bases, and camera motion over explanatory text.

Pass condition: coordinate curves are computed from the map, not hand-drawn to look curvy.

## Weird Metric Distance

Problem: a plane looks Euclidean as a coordinate chart, but metric `g_ij(x)` defines non-Euclidean distance.

Standard solution:

- Treat the canvas as coordinate paper, not true ruler paper.
- At sampled points, draw local unit circles `v^T g(x) v = 1`; these usually appear as ellipses.
- Compute distance function `T(x)=d_g(p,x)` and draw metric wavefronts `T(x)=constant`.
- Draw geodesics between points. Optionally show Euclidean straight line as a faded comparison.
- Show path length integral `L_g(gamma)=int sqrt(gamma'(t)^T g(gamma(t)) gamma'(t)) dt`.

Pass condition: distance comes from metric/path integral; the screen straight line is only a candidate path.

## Gaussian Beam

Problem: real beam curvature may be too subtle to see.

Standard solution:

- Use the real Gaussian beam formula family: waist, Rayleigh length, wavefront curvature, envelope.
- If the lesson needs visible curvature, choose pedagogical parameters with a smaller curvature radius.
- Generate envelope, wavefront, and waist from those parameters.
- Record in storyboard or log that parameters are illustrative.

Pass condition: teaching parameters are allowed; arbitrary decorative curves are not.

## Convolutional Neural Network

Problem: animate convolution, activation, pooling, and classification.

Standard solution:

- Use real tensor shapes and real computation flow.
- The sliding patch and kernel should compute actual dot products for the feature map.
- For multiple channels, show representative channels, top-k activations, or small multiples.
- ReLU, pooling, flattening, and linear layers should preserve true shapes and values.
- Color may be normalized and low activations may be hidden, but threshold and normalization rules must be fixed.

Pass condition: key frames and main value changes come from actual tensor computation, not generic blocks flowing across the screen.

## Gradient Of A Scalar Field

Problem: show the gradient of a scalar function `f(x,y)=u`, including why it is perpendicular to level curves and why it points in the direction of fastest increase.

Core object:

- Scalar field `f: R^2 -> R`.
- Level set `f(x,y)=u`.
- Point `p=(x0,y0)`.
- Gradient `grad f(p)=(f_x(p), f_y(p))`.

The same concept can be shown through multiple valid perspectives. Use one, sequence several, or mix them in the same shot. The important part is that every perspective is generated from the same `f` and the same point `p`, so the views cross-check each other instead of becoming separate illustrations.

### Perspective A: top-down contour view

- Draw the `xy` plane from above.
- Plot level curves `f(x,y)=u_k`.
- Mark point `p` on the contour `f(x,y)=f(p)`.
- Compute `grad f(p)` and draw the gradient arrow at `p`.
- Draw the tangent to the level curve at `p`; the gradient arrow must be perpendicular to this tangent.
- Use height coloring in the background if helpful; the color must be a fixed mapping from `f(x,y)`.

Display optimization:

- Normalize or cap arrow length if `|grad f|` is too large.
- Use opacity/sampling to avoid dense contour clutter.
- Use color to distinguish current contour, gradient, and tangent.

Pass condition: the arrow direction is computed from `grad f(p)`, not hand-placed to look perpendicular.

### Perspective B: oblique 3D mountain view

- Draw the surface `z=f(x,y)`.
- Transition the camera from top-down contours to an oblique view so contours become horizontal slices of a surface.
- Lift point `p` to `P=(x0,y0,f(x0,y0))`.
- Show a steepest descent/ascent path generated by an ODE such as `d gamma/dt = -grad f(gamma)` or normalized `-grad f/|grad f|`.
- At a point on the path, draw the local tangent arrow. Its `xy` projection aligns with `-grad f` for descent or `grad f` for ascent.

Display optimization:

- Use a pedagogically clear surface if the true one is too flat, but record this parameter choice.
- Use height coloring or contour bands on the surface to make level sets visible.

Pass condition: the path is integrated from the gradient field; it is not a hand-drawn nice downhill curve.

### Perspective C: vertical slice in the gradient direction

- Compute `e = grad f(p)/|grad f(p)|`.
- Cut the surface with the vertical plane through `p` in direction `e`; this plane contains the vertical axis and the gradient direction in the `xy` plane.
- The slice curve is `s -> f(p+s e)`.
- At `s=0`, the slice slope is `d/ds f(p+s e)|_{s=0}=|grad f(p)|`.
- Show the tangent line on this 2D slice and label the slope as `|grad f(p)|`.
- Optionally show another slice in a non-gradient direction with a smaller slope for comparison.

Display optimization:

- Split screen: left shows the 3D surface and cutting plane; right shows the unfolded slice curve.
- Use camera movement to make the cut feel continuous rather than a hard diagram switch.

Pass condition: the slice direction comes from the gradient and the tangent slope is the actual directional derivative.

### Perspective D: height coloring plus gradient field

- Use a top-down map colored by `f(x,y)`.
- Overlay sparse gradient arrows sampled from the true field `grad f(x,y)`.
- Use real directions; length can be normalized, capped, or log-scaled.
- Use color/opacity/legend to encode true magnitude.
- If showing flow, integrate `d gamma/dt = -grad f(gamma)` or `grad f(gamma)`.

Display optimization:

- Show only arrows near the current path or point of interest if the field is cluttered.
- Combine contours and coloring: contours give exact level sets; color gives global height intuition.

Pass condition: arrows and flow lines are sampled or integrated from the real gradient field.

### Multi-perspective transition strategy

- Start with contours to establish perpendicularity.
- Move the camera to an oblique surface to connect contours with height.
- Follow a gradient descent/ascent path on the surface.
- Cut the surface in the gradient direction and unfold the slice to show maximum slope.
- Return to the top-down view with coloring and sparse gradient arrows so the local story becomes a field-level story.

Manim camera movement, object morphing, and split-screen views should preserve object identity: the point `p`, contour through `p`, gradient direction, and slice direction must remain visibly the same mathematical objects across perspectives.
