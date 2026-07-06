# Visual Language And Style

Use the project palette and formula hierarchy consistently. The course should feel like blackboard mathematics with carefully used Kessoku Band accents, not a generic neon UI.

## Palette

Source of truth:

- `shared/style/STYLE.md`
- `shared/style/tokens.json`
- `shared/style/palette.png` or `shared/style/palette.svg`
- video-local `src/theme.py`

Core tokens:

| Token | Hex | Role |
|---|---:|---|
| `board` | `#111713` | main blackboard background |
| `board-2` | `#18221C` | secondary dark surface and panel fill |
| `chalk` | `#F4F1E8` | primary text, formulas, main ticks |
| `chalk-muted` | `#C9C7BD` | secondary labels, helper ticks, notes |
| `ryo-blue` | `#516B9F` | structure, definitions, coordinate systems, formal objects |
| `kita-red` | `#E46962` | conclusions, warnings, boundaries, error, strong change |
| `nijika-yellow` | `#EEC467` | intuition, examples, geometric highlights, aha moments |
| `bocchi-pink` | `#D17684` | questions, commentary, unknowns, soft emphasis |

Usage:

- Let blackboard and chalk dominate.
- Use at most two character accent colors in a single shot.
- Use yellow sparingly; it is the brightest highlight.
- Use red for strong signals only.
- Use blue as the default structure accent.
- Use pink for questions and soft prompts.
- Do not use pure black `#000000` or pure white `#FFFFFF`.
- Do not replace the palette with neon colors.

## Formula Hierarchy

- **Bare formula**: ordinary definition, intermediate variable, coordinate label, formula already in context. Default to `chalk`; use one semantic color if helpful.
- **Underline**: temporary active short formula or a formula that needs an eye anchor. At most one active underline per shot. Fade or lower opacity after use.
- **Frame/panel**: conclusion, key proposition, formula group, contrast structure, or derivation container.
- **Special color**: semantic only. Never color every variable just because it looks lively.

Do not stack color + underline + frame on every short formula. A frame is a hierarchy signal, not a default decoration.

Formula frames need an explicit role. Ordinary short formulas, coordinate
labels, route labels, and algebraic setup lines default to bare `MathTex`.
Use a frame only when it marks one of these roles: `conclusion`,
`active_focus`, `group_panel`, `contrast_pair`, `derivation_container`, or
`warning`. If more than one short formula in the same beat is framed, the
stage direction or scene contract must explain the hierarchy difference
between them.

## Text Discipline

Screen text complements narration; it does not replace it.

Allowed screen text:

- Object labels.
- Short prompts.
- Formula labels.
- Rhythm markers.
- Minimal emotional/character cues.

Avoid:

- Full explanatory sentences copied from narration.
- Long subtitle-like paragraphs.
- Repeating what the speaker can say clearly.

Self-check: if removing a line of text leaves the shot understandable through narration and math objects, remove or compress it.

## Layout Discipline

- Do not let formulas overlap coordinate axes, panels, or old fading content.
- Coordinate grids must be anchored to the same mathematical origin as their axes by default. The origin must be a real grid point; the horizontal and vertical axes must lie exactly on grid lines, not between adjacent grid lines. If a deliberately offset grid is ever used, state the mathematical reason in the stage direction and experiment log.
- Grids are not default decoration. In stacked layers, 3D basis objects, or
  mode-decomposition displays, do not repeat a grid on every layer unless the
  grid itself is the mathematical object being taught. Prefer curves, labels,
  depth separation, and at most restrained axes; repeated helper grids that
  become visually louder than the mathematical curves are blockers.
- Old panels should fully exit before new panels enter if their bounding boxes overlap.
- Do not put every formula inside a box.
- Do not use panel frames as default formula decoration. A panel means "this is a structured group, conclusion, contrast, or derivation container."
- Use explicit safe zones or layout slots for diagram areas, formula areas, bottom cues, and character sprites. Do not place major objects by repeated `to_corner` guesses.
- When a panel changes meaning, treat it as a state transition: remove or dim the old panel contents before new formulas enter the same slot.
- Treat layout as temporal occupancy, not a static slide. For every formula slot, diagram region, and sprite safe zone, know which object owns it at each interval.
- Do not cross-fade unrelated formulas in the same slot. If the new formula is not a transformation of the old one, clear the slot first, then enter the new content.
- Short transition overlap is allowed when it reads as motion, but unrelated
  formulas/text sharing a slot should overlap only briefly. If overlap lasts
  long enough to be readable as two stacked messages, it is a layout failure.
- Use the whole frame over time: a formula can move from bottom cue to side board to center reveal if its role changes. Do not keep forcing every formula into one corner.
- Titles must live in their own reserved title band or be omitted. Never let a title line share vertical space with formula panels.
- Avoid stale `always_redraw` objects reappearing after fadeout; remove them or stop their updaters.
- Use stable dimensions and predictable panel positions.
- On-diagram annotations are allowed only when they directly label or reveal
  the local mathematical object, such as a sample value, tangent line,
  derivative cue, normal direction, local linear approximation, or zoomed
  patch. They must have a visible anchor, preserve the main object silhouette,
  stay readable without covering the active construction, and clear when their
  local role ends. If the annotation needs a sentence or a large panel, move it
  to a side lane or local inset instead of covering the graph.
- Connector lines must have named ownership and bounded endpoints. Prefer
  edge-to-edge arrows over decorative baselines. A connector must terminate at
  the node, formula token, sample point, or contour it relates; it must not run
  through a node as a long background line unless that background axis or
  number line is the actual mathematical object being taught.
- When a scene needs a canonical mathematical diagram and the visual treatment
  is uncertain, consult classic textbook conventions before inventing a shape.
  Examples include punctured neighborhoods around singularities, branch cuts,
  contour indentation, eigenfunction mode diagrams, and Green-function source
  markers. Record the adopted convention in stage direction, the scene
  contract, or the experiment log.

## Stage Direction Discipline

For any formula-dense Manim sample, write stage direction before implementation. This is stricter than a storyboard summary: it must describe the timeline occupancy of every major formula, diagram, panel, sprite, and sound cue.

Each stage direction entry should state:

- the local time interval;
- the stage zone used by each formula or diagram;
- whether the object enters, exits, moves, transforms, changes color, dims, or becomes a label;
- whether a frame, underline, bare formula, or color accent is justified by hierarchy;
- which old objects must be cleared before the new object enters;
- which formula parts preserve identity across a transformation;
- whether the viewer can follow the logic through motion rather than seeing disconnected formulas appear in arbitrary places.

Do not use one small corner as a perpetual rewrite board. Use the whole frame over time: definitions can begin in a parameter shelf, algebra can travel through a bottom formula lane, structural formulas can occupy a side board, and consequences can move into a proof lane or center reveal. A frame is a stage role, not a default wrapper.

Stage zones are not permanent jobs. They are temporary claims on canvas space for the current subshot. A strong stage direction should name the layout mode:

- `split_plane_formula`: diagram and formula read together with a visible bridge.
- `full_plane_takeover`: a diagram, grid, surface, or flow takes the whole frame; formulas become short labels or leave.
- `derivation_page`: a long proof takes the main stage; diagrams shrink to insets or exit.
- `linked_cluster`: strongly related definitions, equations, and conclusions stay visually adjacent, aligned, bracketed, connected, or transformed into one another.
- `center_reveal`: a conclusion receives central space and old support objects dim or exit.

Avoid the opposite failure: fixed safe zones that make every region do only one thing forever. If a proof needs a full page, give it the full page. If a plane needs to become immersive, let it take over. If a definition and a conclusion are logically tight, pull them together or animate the connection; do not separate them into distant corners with dead empty space between them.

Blocks are optional attention groups, not the primitive unit of animation. The primitive unit is the mathematical object and its relationship to other objects. Use a block only when it helps the viewer track that relationship. A block may appear for one subshot, split into smaller groups, merge into another group, move with a formula, dissolve into a full-screen diagram, or not exist at all.

## Color Semantics In Episode 0001

- Blue: complex plane, structural definitions, matrices, maps.
- Yellow: example vectors, product vectors, geometric insight, key step.
- Red: outside convergence radius, singularities, warnings, hard boundaries.
- Pink: question marks, unknown maps, "why does this happen?" prompts.

If a frame only uses blue/yellow/white for too long, ask whether a question or warning should use pink/red, or whether the shot should remain restrained.
