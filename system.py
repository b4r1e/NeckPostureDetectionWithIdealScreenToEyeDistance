"""
Files and sound: finding the model and mp3 files, downloading the pose model,
and playing the alert sounds. Suggested owner: P5. Imports nothing from the
other project files.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
MODEL_NAME = "pose_landmarker_lite.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)


def find_asset(name: str) -> Path:
    """Look in assets/ first, then next to this script, then in the current folder."""
    for folder in (ASSETS_DIR, BASE_DIR, Path.cwd()):
        if (folder / name).exists():
            return folder / name
    return ASSETS_DIR / name


def ensure_model() -> Path:
    path = find_asset(MODEL_NAME)
    if not path.exists():
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(MODEL_URL, tmp)
        tmp.replace(path)
    return path


# --------------------------------------------------------------------------
# Sound (plays an mp3 only when the combined status flips)
# --------------------------------------------------------------------------
class SoundPlayer:
    def __init__(self, good_path: str, bad_path: str):
        self.paths = {"good": good_path, "bad": bad_path}
        self._warned: set[str] = set()

    @staticmethod
    def _command(path: str):
        if sys.platform == "darwin" and shutil.which("afplay"):
            return ["afplay", path]
        if shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]
        if shutil.which("mpg123"):
            return ["mpg123", "-q", path]
        return None

    def _warn_once(self, key: str, message: str):
        if key not in self._warned:
            self._warned.add(key)
            print(f"[sound] {message}")

    def play(self, kind: str):
        path = self.paths.get(kind)
        if not path or not Path(path).exists():
            self._warn_once(f"missing-{kind}", f"file not found: {path}")
            return
        cmd = self._command(str(path))
        if cmd is None:
            self._warn_once(
                "no-player", "no audio player found (afplay, ffplay or mpg123)"
            )
            return
        threading.Thread(
            target=lambda: subprocess.run(
                cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            ),
            daemon=True,
        ).start()
