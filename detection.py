# ==========================================================================
# FILE 5 of 6: detection.py
# ==========================================================================
"""
The live detection page: camera loop, video, status chips and the settings panel.
Suggested owner: P3. Uses engine.py and theme.py.
"""

from __future__ import annotations

import time
import tkinter as tk
import traceback

import customtkinter as ctk
import cv2

from engine import PostureEngine
from theme import (
    BAD,
    GOOD,
    INK,
    INK_HOVER,
    MUTED,
    TRACK,
    VIDEO_BG,
    WARN,
    SettingRow,
    Stat,
    card,
    fmt_clock,
    font,
)


# --------------------------------------------------------------------------
# Page 2: Live detection + settings
# --------------------------------------------------------------------------
class DetectionPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.engine: PostureEngine | None = None
        self.cap = None
        self.running = False
        self._after_id = None
        self._photo = None
        self._flash = ("", 0.0, MUTED)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(22, 12))
        ctk.CTkLabel(
            header, text="Live detection", font=font(24, True), text_color=INK
        ).pack(side="left")
        self.cal_label = ctk.CTkLabel(
            header, text="Not calibrated", font=font(13, True), text_color=WARN
        )
        self.cal_label.pack(side="left", padx=18)
        ctk.CTkButton(
            header,
            text="Finish (Q)",
            width=120,
            height=38,
            corner_radius=10,
            font=font(14, True),
            fg_color="transparent",
            border_width=1,
            border_color=INK,
            text_color=INK,
            hover_color="#E3E8EF",
            command=self.finish,
        ).pack(side="right")
        ctk.CTkButton(
            header,
            text="Calibrate (C)",
            width=140,
            height=38,
            corner_radius=10,
            font=font(14, True),
            fg_color=INK,
            hover_color=INK_HOVER,
            text_color="white",
            command=self.calibrate,
        ).pack(side="right", padx=(0, 10))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 24))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)

        self.video_holder = ctk.CTkFrame(left, fg_color=VIDEO_BG, corner_radius=18)
        self.video_holder.grid(row=0, column=0, sticky="nsew")
        self.video_label = tk.Label(
            self.video_holder,
            bg=VIDEO_BG,
            bd=0,
            text="Starting camera...",
            fg="#9FB3C8",
        )
        self.video_label.place(relx=0.5, rely=0.5, anchor="center")

        self.hint = ctk.CTkLabel(
            left,
            text=" ",
            font=font(14),
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=760,
        )
        self.hint.grid(row=1, column=0, sticky="ew", pady=(12, 8))

        chips = ctk.CTkFrame(left, fg_color="transparent")
        chips.grid(row=2, column=0, sticky="ew")
        for i in range(3):
            chips.grid_columnconfigure(i, weight=1, uniform="chip")
        self.chip_neck = Stat(chips, "Neck posture")
        self.chip_dist = Stat(chips, "Eyes to screen")
        self.chip_score = Stat(chips, "Good posture so far")
        self.chip_neck.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.chip_dist.grid(row=0, column=1, sticky="ew", padx=5)
        self.chip_score.grid(row=0, column=2, sticky="ew", padx=(10, 0))

        right = card(body, width=330)
        right.grid(row=0, column=1, sticky="ns")
        right.pack_propagate(False)
        self._build_settings(right)

    # -- settings panel -----------------------------------------------------
    def _build_settings(self, parent):
        s = self.app.settings
        ctk.CTkLabel(
            parent, text="Settings", font=font(18, True), text_color=INK, anchor="w"
        ).pack(fill="x", padx=20, pady=(18, 0))
        ctk.CTkLabel(
            parent,
            text="Changes apply right away.",
            font=font(12),
            text_color=MUTED,
            anchor="w",
        ).pack(fill="x", padx=20)
        scroll = ctk.CTkScrollableFrame(
            parent, fg_color="transparent", scrollbar_button_color=TRACK
        )
        scroll.pack(fill="both", expand=True, padx=8, pady=(6, 10))

        def section(text):
            ctk.CTkLabel(
                scroll, text=text, font=font(15, True), text_color=INK, anchor="w"
            ).pack(fill="x", padx=12, pady=(14, 2))

        def row(*args):
            r = SettingRow(scroll, *args)
            r.pack(fill="x", padx=12, pady=(8, 6))
            return r

        section("Neck posture")
        row(
            "Head drop",
            "How far your head may drop toward your shoulders before it counts as bad. Lower is stricter.",
            5,
            40,
            s.ratio_tol_pct,
            "%",
            lambda v: setattr(s, "ratio_tol_pct", v),
        )
        row(
            "Head tilt",
            "How much more your head may tilt than when you calibrated. Lower is stricter.",
            5,
            40,
            s.tilt_tol_deg,
            "°",
            lambda v: setattr(s, "tilt_tol_deg", v),
        )
        row(
            "Response delay",
            "Frames of bad posture needed before the status changes. Higher means fewer false alarms.",
            3,
            30,
            s.flip_frames,
            " frames",
            lambda v: setattr(s, "flip_frames", v),
        )
        row(
            "Warn after",
            "Show a warning when bad posture lasts this long.",
            5,
            120,
            s.alert_s,
            " s",
            lambda v: setattr(s, "alert_s", v),
        )

        section("Screen distance")
        row(
            "Distance when calibrating",
            "Your real eye-to-screen distance. Set it before you press Calibrate.",
            30,
            100,
            s.ideal_cm,
            " cm",
            lambda v: setattr(s, "ideal_cm", v),
        )
        self.row_min = row(
            "Too close below",
            "Closer than this counts as too close.",
            20,
            80,
            s.dist_min_cm,
            " cm",
            self._on_min,
        )
        self.row_max = row(
            "Too far above",
            "Farther than this counts as too far.",
            40,
            140,
            s.dist_max_cm,
            " cm",
            self._on_max,
        )

        section("Sound")
        sw = ctk.CTkSwitch(
            scroll,
            text="Play a sound when status changes",
            font=font(13),
            text_color=INK,
            progress_color=GOOD,
            fg_color=TRACK,
            button_color="white",
            button_hover_color="#F3F5F8",
            command=lambda: setattr(s, "sound_on", bool(sw.get())),
        )
        if s.sound_on:
            sw.select()
        sw.pack(anchor="w", padx=12, pady=(8, 12))

    def _on_min(self, v):
        s = self.app.settings
        s.dist_min_cm = v
        if v > s.dist_max_cm - 5:
            s.dist_max_cm = min(140, v + 5)
            self.row_max.set(s.dist_max_cm)

    def _on_max(self, v):
        s = self.app.settings
        s.dist_max_cm = v
        if v < s.dist_min_cm + 5:
            s.dist_min_cm = max(20, v - 5)
            self.row_min.set(s.dist_min_cm)

    # -- session control ----------------------------------------------------
    def begin(self, model_path, camera_index):
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            raise RuntimeError(
                "Could not open the camera. Close other apps using it and check camera permission."
            )
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        try:
            self.engine = PostureEngine(
                self.app.settings, self.app.sound, model_path=model_path
            )
        except Exception:
            cap.release()
            raise
        self.cap = cap
        self.running = True
        self.video_label.configure(image="", text="Starting camera...")
        self.cal_label.configure(text="Not calibrated", text_color=WARN)
        for chip in (self.chip_neck, self.chip_dist, self.chip_score):
            chip.set("-", "waiting for calibration")
        self._set_hint(
            "Sit straight at your usual distance, then press Calibrate (C).", MUTED
        )
        self._tick()

    def _stop_loop(self):
        self.running = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def shutdown(self):
        self._stop_loop()
        if self.engine is not None:
            self.engine.finish()
            self.engine = None

    def calibrate(self):
        if not self.running or self.engine is None:
            return
        if self.engine.calibrate():
            self._flash = (
                "Calibrated. Statistics are now being recorded.",
                time.time() + 2.5,
                GOOD,
            )
        else:
            self._flash = (
                "No person in view, so there is nothing to calibrate on.",
                time.time() + 2.5,
                WARN,
            )

    def finish(self):
        if not self.running and self.engine is None:
            return
        self._stop_loop()
        summary = self.engine.finish() if self.engine is not None else None
        self.engine = None
        self.app.show_stats(summary)

    # -- frame loop ---------------------------------------------------------
    def _tick(self):
        if not self.running:
            return
        try:
            ok, frame = self.cap.read()
            if not ok:
                self._set_hint("Could not read from the camera.", BAD)
                self._after_id = self.after(200, self._tick)
                return
            frame = cv2.flip(frame, 1)  # mirror view feels natural
            info = self.engine.process(frame)
            self._render(frame)
            self._update_ui(info)
        except Exception as exc:  # keep the app alive, show what happened
            traceback.print_exc()
            self.running = False
            self._set_hint(
                f"Detection stopped: {exc}. Press Finish to leave this page.", BAD
            )
            return
        self._after_id = self.after(1, self._tick)

    def _render(self, frame):
        h, w = frame.shape[:2]
        avail_w = max(self.video_holder.winfo_width() - 16, 320)
        avail_h = max(self.video_holder.winfo_height() - 16, 240)
        scale = min(avail_w / w, avail_h / h)
        size = (max(1, int(w * scale)), max(1, int(h * scale)))
        rgb = cv2.cvtColor(
            cv2.resize(frame, size, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB
        )
        # Tk can read a binary PPM directly, so Pillow's ImageTk is not needed.
        # (ImageTk fails on some Python/Tk builds with "invalid command name PyImagingPhoto".)
        header = f"P6 {size[0]} {size[1]} 255\n".encode()
        self._photo = tk.PhotoImage(master=self, data=header + rgb.tobytes())
        self.video_label.configure(image=self._photo, text="")

    def _set_hint(self, text, color):
        flash_text, until, flash_color = self._flash
        if time.time() < until:
            text, color = flash_text, flash_color
        self.hint.configure(text=text, text_color=color)

    def _update_ui(self, info):
        if not info["person"]:
            self._set_hint("No person in view. Move into the frame.", WARN)
            return
        if not info["calibrated"]:
            self.cal_label.configure(text="Not calibrated", text_color=WARN)
            self._set_hint(
                "Sit straight at your usual distance, then press Calibrate (C).", MUTED
            )
            return

        self.cal_label.configure(text="Calibrated", text_color=GOOD)
        neck_color = GOOD if info["is_good"] else BAD
        self.chip_neck.set(
            "Good" if info["is_good"] else "Bad",
            f"head drop {info['drop']:.0f}%, tilt {info['tilt']:+.0f}°",
            neck_color,
        )
        kind = info["dist_kind"]
        s = self.app.settings
        label = {"ideal": "In range", "close": "Too close", "far": "Too far"}[kind]
        color = {"ideal": GOOD, "close": BAD, "far": WARN}[kind]
        self.chip_dist.set(
            f"{info['est_cm']:.0f} cm",
            f"{label}, ideal {s.dist_min_cm:.0f} to {s.dist_max_cm:.0f} cm",
            color,
        )
        self.chip_score.set(
            f"{info['score']:.0f}%", f"tracked {fmt_clock(info['tracked_s'])}"
        )

        if info["alert"]:
            self._set_hint(
                f"Bad neck posture for {info['bad_time']:.0f} s. Lift your head and relax your shoulders.",
                BAD,
            )
        elif not info["is_good"]:
            self._set_hint("Neck posture is off. Straighten up.", BAD)
        elif kind == "close":
            self._set_hint("You are too close to the screen. Lean back.", BAD)
        elif kind == "far":
            self._set_hint("You are far from the screen. Move a little closer.", WARN)
        else:
            self._set_hint("Looking good. Keep it up.", GOOD)
