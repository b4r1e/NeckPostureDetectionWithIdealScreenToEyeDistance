# ==========================================================================
# FILE 6 of 6: main.py
# ==========================================================================
"""
Entry point: ties the pages together and starts the app.
Suggested owner: P5.

Run:
    uv add customtkinter
    uv run main.py
    uv run main.py --camera 1 --good-sound correct.mp3 --bad-sound windows-error.mp3

Keys on the detection page:  C = calibrate,  Q = finish.
"""

from __future__ import annotations

import argparse

import customtkinter as ctk

from detection import DetectionPage
from stats import Settings, StatsPage
from system import SoundPlayer, ensure_model, find_asset
from theme import BAD, BG, INK, INK_HOVER, MUTED, PostureDiagram, font


# --------------------------------------------------------------------------
# Page 1: Home
# --------------------------------------------------------------------------
class HomePage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=5, uniform="home")
        self.grid_columnconfigure(1, weight=6, uniform="home")
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=(64, 12))
        ctk.CTkLabel(
            left,
            text="Keep your neck and\nscreen distance in check",
            font=font(40, True),
            text_color=INK,
            anchor="w",
            justify="left",
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="Calibrate once while you sit well. The webcam then watches your neck posture "
            "and how far your eyes are from the screen, and plays a sound when either drifts.",
            font=font(15),
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=430,
        ).pack(anchor="w", pady=(16, 28))
        ctk.CTkButton(
            left,
            text="Start detection",
            height=52,
            width=220,
            corner_radius=12,
            font=font(16, True),
            fg_color=INK,
            hover_color=INK_HOVER,
            text_color="white",
            command=app.start_session,
        ).pack(anchor="w")
        self.status = ctk.CTkLabel(
            left,
            text="",
            font=font(13),
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=430,
        )
        self.status.pack(anchor="w", pady=(14, 0))
        ctk.CTkLabel(
            left,
            text="On the next page, press C to calibrate and Q to finish.",
            font=font(12),
            text_color=MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(18, 0))

        PostureDiagram(self).grid(row=0, column=1, sticky="nsew", padx=(0, 32), pady=32)

    def set_status(self, text, error=False):
        self.status.configure(text=text, text_color=BAD if error else MUTED)


# --------------------------------------------------------------------------
# App shell
# --------------------------------------------------------------------------
class App(ctk.CTk):
    def __init__(self, args):
        super().__init__()
        self.title("Neck Posture Detector")
        self.geometry("1240x800")
        self.minsize(1060, 700)
        self.configure(fg_color=BG)

        self.args = args
        self.settings = Settings()
        self.sound = SoundPlayer(args.good_sound, args.bad_sound)

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.pages = {}
        for name, cls in (
            ("home", HomePage),
            ("detect", DetectionPage),
            ("stats", StatsPage),
        ):
            page = cls(container, self)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = page
        self.current = "home"
        self.pages["home"].tkraise()

        self.bind("<Key>", self._on_key)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def show_page(self, name):
        self.current = name
        self.pages[name].tkraise()

    def start_session(self):
        home = self.pages["home"]
        home.set_status(
            "Loading the pose model. The first run downloads it, so this can take a moment."
        )
        self.update_idletasks()
        try:
            model = ensure_model()
            self.pages["detect"].begin(model, self.args.camera)
        except Exception as exc:
            home.set_status(f"Could not start: {exc}", error=True)
            return
        home.set_status("")
        self.show_page("detect")

    def show_stats(self, summary):
        self.pages["stats"].show(summary)
        self.show_page("stats")

    def _on_key(self, event):
        if self.current != "detect":
            return
        key = (event.keysym or "").lower()
        if key == "c":
            self.pages["detect"].calibrate()
        elif key == "q":
            self.pages["detect"].finish()

    def on_close(self):
        self.pages["detect"].shutdown()
        self.destroy()


def main():
    parser = argparse.ArgumentParser(
        description="Neck posture detector with a desktop interface"
    )
    parser.add_argument(
        "--camera", type=int, default=0, help="Camera index (default 0)"
    )
    parser.add_argument(
        "--good-sound",
        default=str(find_asset("correct.mp3")),
        help="mp3 played when posture becomes good again",
    )
    parser.add_argument(
        "--bad-sound",
        default=str(find_asset("windows-error.mp3")),
        help="mp3 played when neck posture or distance turns bad",
    )
    args = parser.parse_args()

    ctk.set_appearance_mode("light")
    App(args).mainloop()


if __name__ == "__main__":
    main()
