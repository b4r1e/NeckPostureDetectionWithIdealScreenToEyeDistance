"""
Look and feel: colours, fonts, small helpers and reusable widgets.
Suggested owner: P4. Imports nothing from the other project files.
"""

from __future__ import annotations

import math
import tkinter as tk
from functools import lru_cache

import customtkinter as ctk

# --------------------------------------------------------------------------
# Look: quiet slate surfaces, ink buttons, colour reserved for posture status
# --------------------------------------------------------------------------
BG = "#EEF1F5"
CARD = "#FFFFFF"
INK = "#16202E"
INK_HOVER = "#2B3A52"
MUTED = "#6B7686"
LINE = "#DDE2EA"
TRACK = "#D3DAE5"
GOOD = "#1E9E6A"
BAD = "#E5484D"
WARN = "#D98E04"
VIDEO_BG = "#0E141C"


@lru_cache(maxsize=None)
def font(size: int, bold: bool = False) -> ctk.CTkFont:
    # Must only be called after the root window exists.
    return ctk.CTkFont(size=size, weight="bold" if bold else "normal")


def card(parent, radius: int = 18, **kw) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        parent,
        fg_color=CARD,
        corner_radius=radius,
        border_width=1,
        border_color=LINE,
        **kw,
    )


def fmt_dur(seconds: float) -> str:
    seconds = int(round(seconds))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def fmt_clock(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


# --------------------------------------------------------------------------
# Small widgets
# --------------------------------------------------------------------------
class SettingRow(ctk.CTkFrame):
    def __init__(self, master, title, hint, lo, hi, value, unit, on_change):
        super().__init__(master, fg_color="transparent")
        self.unit, self.on_change = unit, on_change
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=title, font=font(13, True), text_color=INK).pack(
            side="left"
        )
        self.value_label = ctk.CTkLabel(
            top, text="", font=font(13, True), text_color=INK
        )
        self.value_label.pack(side="right")
        self.slider = ctk.CTkSlider(
            self,
            from_=lo,
            to=hi,
            number_of_steps=int(hi - lo),
            command=self._changed,
            fg_color=TRACK,
            progress_color=INK,
            button_color=INK,
            button_hover_color=INK_HOVER,
            height=16,
        )
        self.slider.pack(fill="x", pady=(8, 4))
        self.slider.set(value)
        ctk.CTkLabel(
            self,
            text=hint,
            font=font(11),
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=250,
        ).pack(fill="x")
        self._show(value)

    def _show(self, v):
        self.value_label.configure(text=f"{int(round(v))}{self.unit}")

    def _changed(self, v):
        v = int(round(v))
        self._show(v)
        self.on_change(v)

    def set(self, v):
        self.slider.set(v)
        self._show(v)


class Stat(ctk.CTkFrame):
    def __init__(self, master, title):
        super().__init__(
            master, fg_color=CARD, corner_radius=14, border_width=1, border_color=LINE
        )
        ctk.CTkLabel(
            self, text=title, font=font(12), text_color=MUTED, anchor="w"
        ).pack(fill="x", padx=16, pady=(12, 0))
        self.value = ctk.CTkLabel(
            self, text="-", font=font(26, True), text_color=INK, anchor="w"
        )
        self.value.pack(fill="x", padx=16)
        self.sub = ctk.CTkLabel(
            self, text=" ", font=font(12), text_color=MUTED, anchor="w"
        )
        self.sub.pack(fill="x", padx=16, pady=(0, 12))

    def set(self, value, sub=" ", color=INK):
        self.value.configure(text=value, text_color=color)
        self.sub.configure(text=sub or " ")


class DonutChart(tk.Canvas):
    def __init__(self, master):
        super().__init__(master, bg=CARD, highlightthickness=0)
        self.pct, self.has_data, self.center, self.caption = 0.0, False, "", ""
        self.bind("<Configure>", lambda e: self.redraw())

    def set(self, pct, has_data, center, caption):
        self.pct, self.has_data, self.center, self.caption = (
            pct,
            has_data,
            center,
            caption,
        )
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40 or h < 40:
            return
        size = min(w, h) - 20
        thick = max(14, size * 0.11)
        cx, cy, r = w / 2, h / 2, size / 2 - thick / 2
        box = (cx - r, cy - r, cx + r, cy + r)
        if not self.has_data:
            self.create_oval(*box, outline=TRACK, width=thick)
        else:
            self.create_oval(*box, outline=BAD, width=thick)
            if self.pct >= 99.9:
                self.create_oval(*box, outline=GOOD, width=thick)
            elif self.pct > 0.1:
                self.create_arc(
                    *box,
                    start=90,
                    extent=-3.6 * self.pct,
                    style="arc",
                    outline=GOOD,
                    width=thick,
                )
        self.create_text(
            cx,
            cy - 10,
            text=self.center,
            font=font(int(max(28, size * 0.2)), True),
            fill=INK,
        )
        self.create_text(
            cx, cy + size * 0.1 + 8, text=self.caption, font=font(13), fill=MUTED
        )


class SegmentBar(tk.Canvas):
    def __init__(self, master, height=26):
        super().__init__(master, bg=CARD, highlightthickness=0, height=height)
        self.segments = []
        self.bind("<Configure>", lambda e: self.redraw())

    def set(self, segments):
        self.segments = [(v, c) for v, c in segments if v > 0]
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        total = sum(v for v, _ in self.segments)
        if total <= 0:
            self.create_rectangle(0, 0, w, h, fill=TRACK, width=0)
            return
        x = 0.0
        for v, color in self.segments:
            nx = x + w * v / total
            self.create_rectangle(x, 0, max(x + 1, nx), h, fill=color, width=0)
            x = nx


class PostureDiagram(tk.Canvas):
    """Home page illustration: upright neck versus a neck leaning forward."""

    def __init__(self, master):
        super().__init__(master, bg=BG, highlightthickness=0)
        self.bind("<Configure>", lambda e: self.redraw())

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 100 or h < 100:
            return
        s = min(w, h) / 560
        cx, sy = w * 0.46, h * 0.76
        faint = "#B8C1CE"

        self.create_line(
            cx - 170 * s,
            sy,
            cx + 170 * s,
            sy,
            fill=faint,
            width=max(4, 8 * s),
            capstyle="round",
        )
        for dx in (-170, 170):
            self.create_oval(
                cx + dx * s - 9 * s,
                sy - 9 * s,
                cx + dx * s + 9 * s,
                sy + 9 * s,
                fill=faint,
                outline="",
            )
        self.create_line(cx, sy, cx, sy - 400 * s, fill=faint, width=2, dash=(6, 6))

        # upright neck and head
        gx, gy = cx + 8 * s, sy - 230 * s
        self.create_oval(
            gx - 74 * s,
            gy - 118 * s,
            gx + 74 * s,
            gy + 30 * s,
            outline=GOOD,
            width=max(2, 3 * s),
        )
        self.create_line(
            cx, sy, gx, gy, fill=GOOD, width=max(5, 9 * s), capstyle="round"
        )
        self.create_oval(
            gx - 9 * s, gy - 9 * s, gx + 9 * s, gy + 9 * s, fill=GOOD, outline=""
        )
        self.create_text(
            gx,
            gy - 146 * s,
            text="upright",
            fill=GOOD,
            font=font(15, True),
            anchor="center",
        )

        # neck leaning forward
        bx, by = cx + 150 * s, sy - 180 * s
        self.create_oval(
            bx - 74 * s,
            by - 118 * s,
            bx + 74 * s,
            by + 30 * s,
            outline=BAD,
            width=max(2, 3 * s),
            dash=(7, 5),
        )
        self.create_line(
            cx, sy, bx, by, fill=BAD, width=max(5, 9 * s), capstyle="round"
        )
        self.create_oval(
            bx - 9 * s, by - 9 * s, bx + 9 * s, by + 9 * s, fill=BAD, outline=""
        )
        self.create_text(
            bx,
            by - 146 * s,
            text="leaning forward",
            fill=BAD,
            font=font(15, True),
            anchor="center",
        )

        ang = math.degrees(math.atan2(bx - cx, sy - by))
        rr = 120 * s
        self.create_arc(
            cx - rr,
            sy - rr,
            cx + rr,
            sy + rr,
            start=90 - ang,
            extent=ang,
            style="arc",
            outline=BAD,
            width=max(2, 3 * s),
        )
