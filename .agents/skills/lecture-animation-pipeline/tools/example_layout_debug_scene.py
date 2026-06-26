from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import *

config["no_latex_cleanup"] = True

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.append(str(THIS_DIR))

from theme import (
    BOARD, BOCCHI_PINK, CHALK, CHALK_MUTED, KITA_RED,
    NIJIKA_YELLOW, RYO_BLUE, board_panel, label, math_tex, soft_line,
)


class LayoutDebug(Scene):
    """Full collision check of ALL simultaneously-visible elements at peak times."""

    def construct(self):
        self.camera.background_color = BOARD

        ox, oy, sx, sy = -1.5, -1.0, 1.05, 2.6

        def pt(x, y):
            return RIGHT * (ox + x * sx) + UP * (oy + y * sy)

        def f_func(x):
            return 1.0 / (1.0 + x * x)

        def partial_sum(x, n):
            s = 0.0
            for k in range(n + 1):
                s += ((-1) ** k) * (x ** (2 * k))
            return s

        # ── frame boundary ──
        frame_w = config.frame_width
        frame_h = config.frame_height
        self.add(Rectangle(width=frame_w, height=frame_h, color=WHITE,
                           stroke_width=1, stroke_opacity=0.3))

        # ═══ ALL GRAPH ELEMENTS ═══
        elements = {}
        time_ranges = {}

        # coordinate system
        elements["x_axis"] = Line(pt(-3.2, 0), pt(3.2, 0), color=CHALK_MUTED, stroke_width=2.2, stroke_opacity=0.6)
        time_ranges["x_axis"] = (0, 99)
        elements["y_axis"] = Line(pt(0, -0.15), pt(0, 1.55), color=CHALK_MUTED, stroke_width=2.2, stroke_opacity=0.6)
        time_ranges["y_axis"] = (0, 99)

        elements["f_curve"] = ParametricFunction(
            lambda t: pt(t, f_func(t)), t_range=[-2.8, 2.8],
            color=CHALK, stroke_width=2.5, stroke_opacity=0.5)
        time_ranges["f_curve"] = (5, 99)

        elements["f_label"] = math_tex(
            r"f(x) = \frac{1}{1+x^2}", font_size=34, color=CHALK,
        ).to_corner(UR, buff=0.5).shift(LEFT * 0.5 + DOWN * 0.3)
        time_ranges["f_label"] = (1.8, 99)

        # series panel
        sp = board_panel(5.8, 1.2, opacity=0.35)
        sp.move_to(RIGHT * 3.2 + UP * 0.4)
        elements["series_panel"] = sp
        time_ranges["series_panel"] = (9.5, 31)

        # divergence curves
        elements["div_right"] = ParametricFunction(
            lambda t: pt(t, partial_sum(t, 9)), t_range=[1.1, 2.5],
            color=KITA_RED, stroke_width=2.0, stroke_opacity=0.5)
        time_ranges["div_right"] = (25.5, 31)
        elements["div_left"] = ParametricFunction(
            lambda t: pt(t, partial_sum(t, 9)), t_range=[-2.5, -1.1],
            color=KITA_RED, stroke_width=2.0, stroke_opacity=0.5)
        time_ranges["div_left"] = (25.5, 31)

        # ±1 markers
        elements["tick_+1"] = Line(pt(1, -0.08), pt(1, 0.08), color=KITA_RED, stroke_width=3)
        time_ranges["tick_+1"] = (25.5, 99)
        elements["tick_-1"] = Line(pt(-1, -0.08), pt(-1, 0.08), color=KITA_RED, stroke_width=3)
        time_ranges["tick_-1"] = (25.5, 99)
        elements["+1_label"] = math_tex("+1", font_size=24, color=KITA_RED).next_to(pt(1, 0), DOWN, buff=0.15)
        time_ranges["+1_label"] = (28, 99)
        elements["-1_label"] = math_tex("-1", font_size=24, color=KITA_RED).next_to(pt(-1, 0), DOWN, buff=0.15)
        time_ranges["-1_label"] = (28, 99)
        elements["r_line"] = DashedLine(pt(-1, 0), pt(1, 0), color=KITA_RED, stroke_width=2, dash_length=0.08)
        time_ranges["r_line"] = (25.5, 99)

        # checkmarks
        elements["✓_+1"] = math_tex(r"\checkmark", font_size=28, color=RYO_BLUE).next_to(pt(1, f_func(1)), UP, buff=0.15)
        time_ranges["✓_+1"] = (31, 34)
        elements["✓_-1"] = math_tex(r"\checkmark", font_size=28, color=RYO_BLUE).next_to(pt(-1, f_func(-1)), UP, buff=0.15)
        time_ranges["✓_-1"] = (31, 34)

        # ghost y-axis
        elements["ghost_y"] = Line(pt(0, -0.15), pt(0, 1.55), color=NIJIKA_YELLOW,
                                    stroke_width=1.8, stroke_opacity=0.18)
        time_ranges["ghost_y"] = (37, 99)

        # ═══ NARRATIVE TEXT (NEW POSITIONS) ═══
        elements["friendly?"] = math_tex(
            r"\text{looks friendly?}", font_size=32, color=BOCCHI_PINK,
        ).move_to(UP * 3.5)
        time_ranges["friendly?"] = (20.32, 25.5)

        elements["R = 1"] = math_tex(
            r"R = 1", font_size=40, color=KITA_RED,
        ).move_to(RIGHT * 4.5 + UP * 1.5)
        time_ranges["R = 1"] = (25.5, 99)

        elements["smooth"] = math_tex(
            r"\text{smooth on all of } \mathbb{R}", font_size=28, color=RYO_BLUE,
        ).move_to(UP * 3.5)
        time_ranges["smooth"] = (31, 34)

        elements["why R=1?"] = math_tex(
            r"\text{why } R = 1\,?", font_size=42, color=KITA_RED,
        ).move_to(RIGHT * 4.5 + UP * 0.5)
        time_ranges["why R=1?"] = (34, 37)

        elements["hidden"] = math_tex(
            r"\text{the answer is hidden}", font_size=32, color=BOCCHI_PINK,
        ).move_to(RIGHT * 4.5 + DOWN * 1.5)
        time_ranges["hidden"] = (37, 99)

        # ═══ DRAW ALL + BOUNDING BOXES ═══
        colors = {
            "x_axis": CHALK_MUTED, "y_axis": CHALK_MUTED, "f_curve": CHALK,
            "f_label": CHALK, "series_panel": RYO_BLUE, "div_right": KITA_RED,
            "div_left": KITA_RED, "tick_+1": KITA_RED, "tick_-1": KITA_RED,
            "+1_label": KITA_RED, "-1_label": KITA_RED, "r_line": KITA_RED,
            "✓_+1": RYO_BLUE, "✓_-1": RYO_BLUE, "ghost_y": NIJIKA_YELLOW,
            "friendly?": BOCCHI_PINK, "R = 1": KITA_RED, "smooth": RYO_BLUE,
            "why R=1?": NIJIKA_YELLOW, "hidden": BOCCHI_PINK,
        }

        for name, mob in elements.items():
            c = colors.get(name, WHITE)
            box = SurroundingRectangle(mob, color=c, buff=0.04, stroke_width=1.0)
            tag = Text(name, font_size=10, color=c).next_to(box, UP, buff=0.01)
            self.add(mob, box, tag)

        # ═══ COLLISION CHECK AT PEAK TIMES ═══
        check_times = [22, 26, 29, 32, 35, 38, 42]
        all_issues = []

        for t in check_times:
            visible = [n for n, (t0, t1) in time_ranges.items() if t0 <= t <= t1]
            print(f"\n--- t = {t}s: {len(visible)} elements visible ---")
            for i in range(len(visible)):
                for j in range(i + 1, len(visible)):
                    a, b = elements[visible[i]], elements[visible[j]]
                    ax1, ax2 = a.get_left()[0], a.get_right()[0]
                    ay1, ay2 = a.get_bottom()[1], a.get_top()[1]
                    bx1, bx2 = b.get_left()[0], b.get_right()[0]
                    by1, by2 = b.get_bottom()[1], b.get_top()[1]
                    h_ov = min(ax2, bx2) - max(ax1, bx1)
                    v_ov = min(ay2, by2) - max(ay1, by1)
                    if h_ov > 0 and v_ov > 0:
                        msg = f"  ** OVERLAP t={t} ** {visible[i]} <-> {visible[j]}  h={h_ov:+.2f} v={v_ov:+.2f}"
                        print(msg)
                        all_issues.append(msg)
                    else:
                        h_gap = max(bx1 - ax2, ax1 - bx2, 0)
                        v_gap = max(by1 - ay2, ay1 - by2, 0)
                        if h_gap < 0.3 and v_gap < 0.3 and h_gap + v_gap < 0.4:
                            msg = f"  !! CLOSE t={t} !!   {visible[i]} <-> {visible[j]}  hg={h_gap:.2f} vg={v_gap:.2f}"
                            print(msg)

        if not all_issues:
            print("\n✓✓✓ NO OVERLAPS at any checked time! ✓✓✓")
        else:
            print(f"\n✗✗✗ {len(all_issues)} overlaps found ✗✗✗")
