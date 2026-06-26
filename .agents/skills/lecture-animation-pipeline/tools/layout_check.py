"""Reusable layout / collision-check helpers for Manim scenes.

Drop this file next to your scene module (e.g. ``src/layout_check.py``) and
call :func:`check_layout` at the end of a scene to report overlapping or
too-close element pairs at a list of peak times. The checker uses the
current bounding boxes of the mobjects, so any position/scale changes made
during the scene are captured automatically.

Example:

    from layout_check import check_layout

    elements = {
        "f_label": f_label,
        "R = 1":   r_label,
        ...
    }
    time_ranges = {
        "f_label": (5.0, 99),   # visible from 5s onward
        "R = 1":   (25.5, 99),
    }
    check_layout(elements, time_ranges, times=[22, 26, 29, 32, 35])

An overlap is reported when the horizontal AND vertical extents of two
visible elements intersect. A "close" warning is raised when both gaps
(horizontal and vertical) are below a configurable threshold.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from manim import Mobject, config


def _bbox(mob: Mobject) -> tuple[float, float, float, float]:
    """Return ``(x_min, x_max, y_min, y_max)`` in frame coordinates."""
    x_min = mob.get_left()[0]
    x_max = mob.get_right()[0]
    y_min = mob.get_bottom()[1]
    y_max = mob.get_top()[1]
    return x_min, x_max, y_min, y_max


def check_layout(
    elements: Mapping[str, Mobject],
    time_ranges: Mapping[str, tuple[float, float]],
    times: Iterable[float] = (22.0, 26.0, 29.0, 32.0, 35.0),
    close_h: float = 0.3,
    close_v: float = 0.3,
    close_total: float = 0.4,
    close_as_issue: bool = False,
    verbose: bool = True,
) -> list[str]:
    """Report OVERLAP / CLOSE issues between simultaneously-visible elements.

    Parameters
    ----------
    elements :
        Name -> Mobject mapping.
    time_ranges :
        Name -> ``(t_enter, t_exit)``. Use a very large ``t_exit`` for
        persistent elements.
    times :
        Moments (in seconds) at which to evaluate visibility.
    close_h, close_v :
        Thresholds for "close" warnings on horizontal / vertical gap.
    close_total :
        ``h_gap + v_gap`` must be below this to raise a CLOSE warning.
    verbose :
        When True, print every check time, every issue, and a summary.

    Returns
    -------
    list of str
        Every OVERLAP message (one per pair per time). Empty means clean.
    """
    times = sorted(set(times))
    issues: list[str] = []

    for t in times:
        visible = [
            name for name, (t0, t1) in time_ranges.items()
            if name in elements and t0 <= t <= t1
        ]
        if verbose:
            print(f"\n--- t = {t:g}s: {len(visible)} elements visible ---")
        for i in range(len(visible)):
            for j in range(i + 1, len(visible)):
                na, nb = visible[i], visible[j]
                ax1, ax2, ay1, ay2 = _bbox(elements[na])
                bx1, bx2, by1, by2 = _bbox(elements[nb])
                h_ov = min(ax2, bx2) - max(ax1, bx1)
                v_ov = min(ay2, by2) - max(ay1, by1)
                if h_ov > 0 and v_ov > 0:
                    msg = (
                        f"  ** OVERLAP t={t:g} ** {na} <-> {nb}"
                        f"  h={h_ov:+.2f} v={v_ov:+.2f}"
                    )
                    if verbose:
                        print(msg)
                    issues.append(msg)
                else:
                    h_gap = max(bx1 - ax2, ax1 - bx2, 0.0)
                    v_gap = max(by1 - ay2, ay1 - by2, 0.0)
                    if (
                        h_gap < close_h
                        and v_gap < close_v
                        and h_gap + v_gap < close_total
                    ):
                        msg = (
                            f"  !! CLOSE t={t:g} !!   {na} <-> {nb}"
                            f"  hg={h_gap:.2f} vg={v_gap:.2f}"
                        )
                        if verbose:
                            print(msg)
                        if close_as_issue:
                            issues.append(msg)

    if verbose:
        if not issues:
            print("\n\u2713\u2713\u2713 NO OVERLAPS at any checked time! \u2713\u2713\u2713")
        else:
            print(f"\n\u2717\u2717\u2717 {len(issues)} overlaps found \u2717\u2717\u2717")
    return issues


def check_frame_bounds(
    elements: Mapping[str, Mobject],
    *,
    margin: float = 0.06,
    verbose: bool = True,
) -> list[str]:
    """Report elements that extend outside the render frame.

    ``margin`` keeps objects away from the exact edge, because frame-edge text
    often looks clipped after video compression even if it is mathematically
    inside the camera rectangle.
    """
    half_w = config.frame_width / 2
    half_h = config.frame_height / 2
    issues: list[str] = []
    for name, mob in elements.items():
        x_min, x_max, y_min, y_max = _bbox(mob)
        if (
            x_min < -half_w + margin
            or x_max > half_w - margin
            or y_min < -half_h + margin
            or y_max > half_h - margin
        ):
            msg = (
                f"  ** OUT_OF_FRAME ** {name}"
                f" bbox=({x_min:.2f},{x_max:.2f},{y_min:.2f},{y_max:.2f})"
            )
            if verbose:
                print(msg)
            issues.append(msg)
    if verbose and not issues:
        print("\n✓✓✓ NO FRAME-BOUND VIOLATIONS! ✓✓✓")
    return issues


def check_containment(
    pairs: Mapping[str, tuple[Mobject, Mobject] | Sequence[Mobject]],
    *,
    pad: float = 0.04,
    verbose: bool = True,
) -> list[str]:
    """Report text/formula content that does not fit inside its container.

    Each pair is ``name -> (container, content)``. It is intended for chips,
    rounded panels, vector brackets, and formula frames where touching or
    crossing the border should fail review.
    """
    issues: list[str] = []
    for name, pair in pairs.items():
        container, content = pair[0], pair[1]
        cx_min, cx_max, cy_min, cy_max = _bbox(container)
        tx_min, tx_max, ty_min, ty_max = _bbox(content)
        if (
            tx_min < cx_min + pad
            or tx_max > cx_max - pad
            or ty_min < cy_min + pad
            or ty_max > cy_max - pad
        ):
            msg = (
                f"  ** CONTAINMENT_FAIL ** {name}"
                f" content=({tx_min:.2f},{tx_max:.2f},{ty_min:.2f},{ty_max:.2f})"
                f" container=({cx_min:.2f},{cx_max:.2f},{cy_min:.2f},{cy_max:.2f})"
            )
            if verbose:
                print(msg)
            issues.append(msg)
    if verbose and not issues:
        print("\n✓✓✓ NO CONTAINMENT VIOLATIONS! ✓✓✓")
    return issues


def check_reserved_regions(
    regions: Mapping[str, Mobject],
    elements: Mapping[str, Mobject],
    region_time_ranges: Mapping[str, tuple[float, float]],
    element_time_ranges: Mapping[str, tuple[float, float]],
    *,
    times: Iterable[float],
    verbose: bool = True,
) -> list[str]:
    """Report elements that intrude into protected diagram/stage regions.

    Use this when text/panel checks are not enough. For example, an operation
    board may not overlap a live function graph even if it does not overlap any
    other formula. ``regions`` are usually invisible rectangles representing
    active graph, coordinate-plane, sampling, or sprite-safe zones.
    """
    issues: list[str] = []
    times = sorted(set(times))
    for t in times:
        active_regions = [
            name for name, (t0, t1) in region_time_ranges.items()
            if name in regions and t0 <= t <= t1
        ]
        active_elements = [
            name for name, (t0, t1) in element_time_ranges.items()
            if name in elements and t0 <= t <= t1
        ]
        if verbose:
            print(
                f"\n--- t = {t:g}s: {len(active_regions)} protected region(s),"
                f" {len(active_elements)} checked element(s) ---"
            )
        for rn in active_regions:
            rx1, rx2, ry1, ry2 = _bbox(regions[rn])
            for en in active_elements:
                ex1, ex2, ey1, ey2 = _bbox(elements[en])
                h_ov = min(rx2, ex2) - max(rx1, ex1)
                v_ov = min(ry2, ey2) - max(ry1, ey1)
                if h_ov > 0 and v_ov > 0:
                    msg = (
                        f"  ** RESERVED_REGION_INTRUSION t={t:g} **"
                        f" {en} -> {rn} h={h_ov:+.2f} v={v_ov:+.2f}"
                    )
                    if verbose:
                        print(msg)
                    issues.append(msg)
    if verbose and not issues:
        print("\n✓✓✓ NO RESERVED-REGION INTRUSIONS! ✓✓✓")
    return issues


def draw_bbox_overlay(scene, elements, colors=None, tag_font_size: int = 10):
    """Add a bounding-box + name-tag overlay for every element.

    Useful for rendering a visual debug frame. Call before ``self.wait()``
    or inside a ``self.play(...)`` block. ``colors`` is an optional name ->
    color mapping; defaults to WHITE.
    """
    from manim import SurroundingRectangle, Text, WHITE

    colors = colors or {}
    for name, mob in elements.items():
        c = colors.get(name, WHITE)
        box = SurroundingRectangle(mob, color=c, buff=0.04, stroke_width=1.0)
        tag = Text(name, font_size=tag_font_size, color=c).next_to(box, UP, buff=0.01)
        scene.add(mob, box, tag)
