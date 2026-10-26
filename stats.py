# ==========================================================================
# FILE 3 of 6: stats.py
# ==========================================================================
"""
Settings, session statistics and the summary page.
Suggested owner: P2. Uses theme.py for the widgets.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import customtkinter as ctk

from theme import (
    BAD,
    GOOD,
    INK,
    INK_HOVER,
    LINE,
    MUTED,
    WARN,
    DonutChart,
    SegmentBar,
    card,
    fmt_dur,
    font,
)


# --------------------------------------------------------------------------
# Settings the sliders control (read live by the engine every frame)
# --------------------------------------------------------------------------
@dataclass
class Settings:
    ratio_tol_pct: float = 15  # ear-to-shoulder drop vs baseline that counts as bad
    tilt_tol_deg: float = 15  # head tilt increase vs baseline that counts as bad
    flip_frames: int = 10  # bad/out-of-range frames in a row before the status flips
    alert_s: float = 30  # show a warning after this many seconds of bad posture
    ideal_cm: float = 60  # your real eye-to-screen distance when you calibrate
    dist_min_cm: float = 40  # closer than this is "too close"
    dist_max_cm: float = 70  # farther than this is "too far"
    sound_on: bool = True


# --------------------------------------------------------------------------
# Session statistics (from calibration until finish)
# --------------------------------------------------------------------------
class SessionStats:
    def __init__(self):
        self.start = time.time()
        self.end: float | None = None
        self.good_s = 0.0
        self.bad_s = 0.0
        self.bad_episodes = 0
        self.longest_bad_s = 0.0
        self.max_drop_pct = 0.0
        self.dist_s = {"ideal": 0.0, "close": 0.0, "far": 0.0}
        self._in_bad = False
        self._cur_bad = 0.0
        self._dist_weighted = 0.0
        self._dist_time = 0.0
        self.segments: list[list] = []  # [is_good, seconds] in order, for the timeline

    def update(self, dt, is_good, drop_pct, dist_kind, est_cm):
        if is_good:
            self.good_s += dt
            self._in_bad = False
            self._cur_bad = 0.0
        else:
            self.bad_s += dt
            if not self._in_bad:
                self._in_bad = True
                self.bad_episodes += 1
            self._cur_bad += dt
            self.longest_bad_s = max(self.longest_bad_s, self._cur_bad)
        self.max_drop_pct = max(self.max_drop_pct, drop_pct)
        self.dist_s[dist_kind] += dt
        self._dist_weighted += est_cm * dt
        self._dist_time += dt
        if self.segments and self.segments[-1][0] == is_good:
            self.segments[-1][1] += dt
        else:
            self.segments.append([is_good, dt])

    def summary(self) -> dict:
        end = self.end or time.time()
        tracked = self.good_s + self.bad_s
        good_pct = self.good_s / tracked * 100 if tracked > 0 else 0.0
        return {
            "session_s": end - self.start,
            "tracked_s": tracked,
            "good_s": self.good_s,
            "bad_s": self.bad_s,
            "good_pct": good_pct,
            "bad_pct": 100 - good_pct if tracked > 0 else 0.0,
            "episodes": self.bad_episodes,
            "avg_bad_s": self.bad_s / self.bad_episodes if self.bad_episodes else 0.0,
            "longest_bad_s": self.longest_bad_s,
            "max_drop_pct": self.max_drop_pct,
            "dist_s": dict(self.dist_s),
            "avg_dist_cm": self._dist_weighted / self._dist_time
            if self._dist_time
            else 0.0,
            "segments": [(g, s) for g, s in self.segments],
        }


# --------------------------------------------------------------------------
# Page 3: Summary dashboard
# --------------------------------------------------------------------------
def ledger(parent, rows):
    wrap = ctk.CTkFrame(parent, fg_color="transparent")
    for i, (label, value) in enumerate(rows):
        row = ctk.CTkFrame(wrap, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text=label, font=font(13), text_color=MUTED).pack(
            side="left", pady=8
        )
        ctk.CTkLabel(row, text=value, font=font(14, True), text_color=INK).pack(
            side="right", pady=8
        )
        if i < len(rows) - 1:
            ctk.CTkFrame(wrap, height=1, fg_color=LINE).pack(fill="x")
    return wrap


def grade(score):
    if score >= 85:
        return "Excellent", GOOD
    if score >= 70:
        return "Good", GOOD
    if score >= 50:
        return "Fair", WARN
    return "Needs work", BAD


class StatsPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=32, pady=(24, 8))
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(
            titles,
            text="Session summary",
            font=font(26, True),
            text_color=INK,
            anchor="w",
        ).pack(anchor="w")
        self.subtitle = ctk.CTkLabel(
            titles, text="", font=font(13), text_color=MUTED, anchor="w"
        )
        self.subtitle.pack(anchor="w")
        ctk.CTkButton(
            header,
            text="Quit app",
            width=110,
            height=38,
            corner_radius=10,
            font=font(14, True),
            fg_color="transparent",
            border_width=1,
            border_color=INK,
            text_color=INK,
            hover_color="#E3E8EF",
            command=app.on_close,
        ).pack(side="right")
        ctk.CTkButton(
            header,
            text="Back to home",
            width=140,
            height=38,
            corner_radius=10,
            font=font(14, True),
            fg_color=INK,
            hover_color=INK_HOVER,
            text_color="white",
            command=lambda: app.show_page("home"),
        ).pack(side="right", padx=(0, 10))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=32, pady=(8, 28))

    def show(self, d):
        for child in self.body.winfo_children():
            child.destroy()
        if d is None or d["tracked_s"] <= 0:
            self.subtitle.configure(text="No data was recorded")
            box = card(self.body)
            box.pack(fill="both", expand=True)
            ctk.CTkLabel(
                box, text="Nothing to show yet", font=font(22, True), text_color=INK
            ).pack(expand=True, pady=(0, 4))
            ctk.CTkLabel(
                box,
                text="Statistics start when you press Calibrate and stop when you finish.\n"
                "Go back, start again, calibrate, and let it run for a while.",
                font=font(14),
                text_color=MUTED,
                justify="center",
            ).pack(expand=True)
            return

        self.subtitle.configure(
            text=f"From calibration to finish, {fmt_dur(d['session_s'])}"
        )
        body = self.body
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # left: score donut
        left = card(body, width=360)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 18))
        left.pack_propagate(False)
        ctk.CTkLabel(
            left, text="Neck posture", font=font(16, True), text_color=INK, anchor="w"
        ).pack(fill="x", padx=22, pady=(20, 0))
        ctk.CTkLabel(
            left,
            text="Share of tracked time",
            font=font(12),
            text_color=MUTED,
            anchor="w",
        ).pack(fill="x", padx=22)
        donut = DonutChart(left)
        donut.pack(fill="both", expand=True, padx=14, pady=6)
        donut.set(d["good_pct"], True, f"{d['good_pct']:.0f}%", "good posture")
        label, color = grade(d["good_pct"])
        ctk.CTkLabel(left, text=label, font=font(22, True), text_color=color).pack(
            pady=(0, 2)
        )
        ctk.CTkLabel(
            left,
            text=f"{fmt_dur(d['good_s'])} good, {fmt_dur(d['bad_s'])} bad",
            font=font(13),
            text_color=MUTED,
        ).pack(pady=(0, 20))

        # right: ledgers, timeline, distance
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        tables = card(right)
        tables.grid(row=0, column=0, sticky="ew")
        tables.grid_columnconfigure((0, 1), weight=1, uniform="ledger")
        ledger(
            tables,
            [
                ("Good posture", fmt_dur(d["good_s"])),
                ("Bad posture", fmt_dur(d["bad_s"])),
                ("Bad episodes", str(d["episodes"])),
                ("Average bad episode", fmt_dur(d["avg_bad_s"])),
                ("Longest bad episode", fmt_dur(d["longest_bad_s"])),
                ("Worst head drop", f"{d['max_drop_pct']:.0f}%"),
            ],
        ).grid(row=0, column=0, sticky="nsew", padx=(22, 14), pady=14)
        dist = d["dist_s"]
        dist_total = sum(dist.values()) or 1
        ledger(
            tables,
            [
                ("Session length", fmt_dur(d["session_s"])),
                ("Time tracked", fmt_dur(d["tracked_s"])),
                ("Average distance", f"{d['avg_dist_cm']:.0f} cm"),
                ("In range", fmt_dur(dist["ideal"])),
                ("Too close", fmt_dur(dist["close"])),
                ("Too far", fmt_dur(dist["far"])),
            ],
        ).grid(row=0, column=1, sticky="nsew", padx=(14, 22), pady=14)

        timeline = card(right)
        timeline.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        ctk.CTkLabel(
            timeline,
            text="Neck posture over time",
            font=font(15, True),
            text_color=INK,
            anchor="w",
        ).pack(fill="x", padx=22, pady=(16, 8))
        bar = SegmentBar(timeline, height=26)
        bar.pack(fill="x", padx=22)
        bar.set([(sec, GOOD if good else BAD) for good, sec in d["segments"]])
        ends = ctk.CTkFrame(timeline, fg_color="transparent")
        ends.pack(fill="x", padx=22, pady=(6, 16))
        ctk.CTkLabel(ends, text="calibration", font=font(12), text_color=MUTED).pack(
            side="left"
        )
        ctk.CTkLabel(ends, text="finish", font=font(12), text_color=MUTED).pack(
            side="right"
        )
        self._legend(ends, [("Good", GOOD), ("Bad", BAD)]).pack()

        distance = card(right)
        distance.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        ctk.CTkLabel(
            distance,
            text="Eyes to screen",
            font=font(15, True),
            text_color=INK,
            anchor="w",
        ).pack(fill="x", padx=22, pady=(16, 8))
        dbar = SegmentBar(distance, height=26)
        dbar.pack(fill="x", padx=22)
        dbar.set([(dist["ideal"], GOOD), (dist["close"], BAD), (dist["far"], WARN)])
        legend = self._legend(
            distance,
            [
                (f"In range {dist['ideal'] / dist_total * 100:.0f}%", GOOD),
                (f"Too close {dist['close'] / dist_total * 100:.0f}%", BAD),
                (f"Too far {dist['far'] / dist_total * 100:.0f}%", WARN),
            ],
        )
        legend.pack(anchor="w", padx=22, pady=(8, 16))

    @staticmethod
    def _legend(parent, items):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        for text, color in items:
            item = ctk.CTkFrame(frame, fg_color="transparent")
            item.pack(side="left", padx=(0, 18))
            ctk.CTkFrame(
                item, width=10, height=10, corner_radius=3, fg_color=color
            ).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(item, text=text, font=font(12), text_color=MUTED).pack(
                side="left"
            )
        return frame
