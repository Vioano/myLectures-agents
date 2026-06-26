# Layout / Collision-Check Tools

Reusable helpers for catching element overlap before rendering a full scene.

## `layout_check.py` — Generic collision-check library

Drop-in module. Import into any Manim scene and pass a dict of elements
plus their `(t_enter, t_exit)` ranges. Reports:

- **OVERLAP** — bounding boxes of two simultaneously-visible elements
  intersect in both horizontal and vertical extents.
- **CLOSE** — both horizontal and vertical gaps are below the configured
  thresholds (default `0.3` each, sum `< 0.4`).

Example use inside a scene:

```python
from layout_check import check_layout

elements = {"f_label": f_label, "R = 1": r_label, ...}
time_ranges = {"f_label": (5.0, 99), "R = 1": (25.5, 99), ...}
issues = check_layout(elements, time_ranges, times=[22, 26, 29, 32, 35, 38])
assert not issues, "Layout has overlaps"
```

The checker reads bounding boxes from the mobject's current position, so
it works after any `.move_to()`, `.next_to()`, `.to_corner()`, `.scale()`,
or updater-driven change.

Also exports `draw_bbox_overlay(scene, elements, colors)` for rendering
a visual debug frame with a bounding box and name tag per element.

## `example_layout_debug_scene.py` — Reference full-scene demo

A complete `LayoutDebug(Scene)` built for the S005–S007 Taylor-expansion
merged scene. Shows how to:

1. Register every graph element, axis, label, and narrative text.
2. Assign `(t_enter, t_exit)` ranges to each.
3. Render the full debug frame with `SurroundingRectangle` + name tags.
4. Run `check_layout` at a list of peak times and print results.

Copy this as a starting template for a new scene, replace the element
dictionary, and keep the same structure.

## When to run

- After placing all narrative text but before the final render.
- After repositioning any element in response to a QC-frame complaint.
- Whenever a merged scene packs more than 4 narrative elements at once.

A clean `check_layout` pass does NOT guarantee the frame looks good
(typography, palette, semantic color use, math-object alignment all
need separate QC), but it does catch the most common "two pieces of
text landed on top of each other" bugs.
