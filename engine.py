# ==========================================================================
# FILE 4 of 6: engine.py
# ==========================================================================
"""
Detection engine: landmarks, neck posture rules, distance estimate, overlay.
Suggested owner: P1. Uses stats.py (Settings, SessionStats) and system.py (SoundPlayer).
"""

from __future__ import annotations

import math
import time
from collections import deque

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    PoseLandmarker,
    PoseLandmarkerOptions,
    RunningMode,
)

from stats import SessionStats, Settings
from system import SoundPlayer

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
# BlazePose landmark indices
NOSE, L_EYE, R_EYE, L_EAR, R_EAR, L_SH, R_SH = 0, 2, 5, 7, 8, 11, 12
FACE_POINTS = range(0, 11)

SMOOTHING_WINDOW = 7  # frames averaged to reduce jitter
FONT = cv2.FONT_HERSHEY_SIMPLEX

# Overlay colours on the camera image (BGR order)
BGR_GOOD = (151, 220, 61)
BGR_BAD = (107, 107, 255)
BGR_WARN = (87, 200, 255)
BGR_NEUTRAL = (200, 179, 159)
BGR_SOFT = (238, 238, 238)


# --------------------------------------------------------------------------
# Geometry and drawing helpers
# --------------------------------------------------------------------------
def midpoint(p1, p2):
    return (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2


def distance(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def tilt_from_vertical(p1, p2):
    vx, vy = p2[0] - p1[0], p2[1] - p1[1]
    mag = math.hypot(vx, vy)
    if mag == 0:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, -vy / mag))))


def mean(values):
    return sum(values) / len(values)


def put_text(img, text, org, color, scale, thick=2):
    cv2.putText(img, text, org, FONT, scale, (0, 0, 0), thick + 2, cv2.LINE_AA)
    cv2.putText(img, text, org, FONT, scale, color, thick, cv2.LINE_AA)


def draw_banner(img, text):
    h, w = img.shape[:2]
    scale = max(0.6, 0.9 * w / 1280)
    (tw, th), _ = cv2.getTextSize(text, FONT, scale, 2)
    put_text(img, text, ((w - tw) // 2, h // 2), BGR_SOFT, scale, 2)


# --------------------------------------------------------------------------
# Detection engine (same rules as neck-with-stats.py, settings are live)
# --------------------------------------------------------------------------
class PostureEngine:
    def __init__(
        self, settings: Settings, sound: SoundPlayer, model_path=None, landmarker=None
    ):
        self.s = settings
        self.sound = sound
        if landmarker is None:
            options = PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(model_path)),
                running_mode=RunningMode.VIDEO,
                num_poses=1,
            )
            landmarker = PoseLandmarker.create_from_options(options)
        self.landmarker = landmarker

        self._t0 = time.time()
        self._last_ts = -1
        self._last_frame = time.time()
        self._ratio = deque(maxlen=SMOOTHING_WINDOW)
        self._tilt = deque(maxlen=SMOOTHING_WINDOW)
        self._face = deque(maxlen=SMOOTHING_WINDOW)

        self.latest = None  # (ratio, tilt, face) of the latest frame with a person
        self.baseline = None
        self.stats: SessionStats | None = None
        self._reset_state()

    def _reset_state(self):
        self.is_good = True
        self.distance_ok = True
        self.bad_streak = 0
        self.close_streak = 0
        self.bad_time = 0.0
        self.dist_kind = "ideal"

    # -- calibration --------------------------------------------------------
    def calibrate(self) -> bool:
        if self.latest is None:
            return False
        ratio, tilt, face = self.latest
        self.baseline = {"ratio": ratio, "tilt": tilt, "face": face}
        self._reset_state()
        self.stats = SessionStats()  # statistics start from this calibration
        return True

    # -- per frame ----------------------------------------------------------
    def process(self, frame) -> dict:
        now = time.time()
        dt = min(now - self._last_frame, 1.0)  # a stalled frame must not inflate stats
        self._last_frame = now
        h, w = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        ts = int((now - self._t0) * 1000)
        if ts <= self._last_ts:
            ts = self._last_ts + 1
        self._last_ts = ts
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.landmarker.detect_for_video(image, ts)

        if not result.pose_landmarks:
            self.latest = None
            draw_banner(frame, "No person detected")
            return {"person": False, "calibrated": self.baseline is not None}

        lm = result.pose_landmarks[0]

        def P(i):
            return (lm[i].x * w, lm[i].y * h)

        l_sh, r_sh, l_ear, r_ear, l_eye, r_eye = (
            P(L_SH),
            P(R_SH),
            P(L_EAR),
            P(R_EAR),
            P(L_EYE),
            P(R_EYE),
        )
        sh_mid, ear_mid, eye_mid = (
            midpoint(l_sh, r_sh),
            midpoint(l_ear, r_ear),
            midpoint(l_eye, r_eye),
        )
        shoulder_w = distance(l_sh, r_sh) or 1.0

        self._ratio.append(distance(ear_mid, sh_mid) / shoulder_w)
        self._tilt.append(tilt_from_vertical(sh_mid, ear_mid))
        self._face.append(distance(l_eye, r_eye))
        s_ratio, s_tilt, s_face = mean(self._ratio), mean(self._tilt), mean(self._face)
        self.latest = (s_ratio, s_tilt, s_face)

        pts = {
            "face": [P(i) for i in FACE_POINTS],
            "l_sh": l_sh,
            "r_sh": r_sh,
            "l_ear": l_ear,
            "r_ear": r_ear,
            "l_eye": l_eye,
            "r_eye": r_eye,
            "sh_mid": sh_mid,
            "ear_mid": ear_mid,
            "eye_mid": eye_mid,
        }

        if self.baseline is None:
            self._draw(frame, pts, BGR_NEUTRAL, BGR_NEUTRAL, "")
            return {"person": True, "calibrated": False}

        # -- neck posture: compare with the calibrated baseline
        s = self.s
        drop_pct = (self.baseline["ratio"] - s_ratio) / self.baseline["ratio"] * 100
        tilt_inc = s_tilt - self.baseline["tilt"]
        frame_bad = drop_pct > s.ratio_tol_pct or tilt_inc > s.tilt_tol_deg
        self.bad_streak = (
            self.bad_streak + 1 if frame_bad else max(0, self.bad_streak - 2)
        )

        overall_before = self.is_good and self.distance_ok
        if self.bad_streak >= s.flip_frames:
            self.is_good = False
        elif self.bad_streak == 0:
            self.is_good = True

        # -- screen distance: face size is inversely proportional to distance
        est_cm = s.ideal_cm * self.baseline["face"] / max(s_face, 1e-6)
        too_close, too_far = est_cm < s.dist_min_cm, est_cm > s.dist_max_cm
        if too_close:
            self.dist_kind = "close"
        elif too_far:
            self.dist_kind = "far"
        self.close_streak = (
            self.close_streak + 1
            if (too_close or too_far)
            else max(0, self.close_streak - 2)
        )
        if self.close_streak >= s.flip_frames:
            self.distance_ok = False
        elif self.close_streak == 0:
            self.distance_ok = True
        kind = "ideal" if self.distance_ok else self.dist_kind

        # -- one sound for the combined status, only when it flips
        overall_ok = self.is_good and self.distance_ok
        if s.sound_on:
            if overall_before and not overall_ok:
                self.sound.play("bad")
            elif not overall_before and overall_ok:
                self.sound.play("good")

        self.bad_time = 0.0 if self.is_good else self.bad_time + dt
        self.stats.update(dt, self.is_good, drop_pct, kind, est_cm)

        neck_color = BGR_GOOD if self.is_good else BGR_BAD
        dist_color = {"ideal": BGR_GOOD, "close": BGR_BAD, "far": BGR_WARN}[kind]
        self._draw(frame, pts, neck_color, dist_color, f"{est_cm:.0f} cm")

        tracked = self.stats.good_s + self.stats.bad_s
        return {
            "person": True,
            "calibrated": True,
            "is_good": self.is_good,
            "distance_ok": self.distance_ok,
            "dist_kind": kind,
            "est_cm": est_cm,
            "drop": drop_pct,
            "tilt": tilt_inc,
            "bad_time": self.bad_time,
            "alert": self.bad_time > s.alert_s,
            "score": self.stats.good_s / tracked * 100 if tracked > 0 else 100.0,
            "tracked_s": tracked,
        }

    # -- drawing ------------------------------------------------------------
    @staticmethod
    def _draw(frame, pts, neck_color, dist_color, dist_label):
        h, w = frame.shape[:2]
        u = w / 1280.0
        r = max(3, int(6 * u))
        th = max(2, int(4 * u))
        fs = max(0.5, 0.85 * u)

        def ip(p):
            return int(p[0]), int(p[1])

        sh_l, sh_r, sh_mid = ip(pts["l_sh"]), ip(pts["r_sh"]), ip(pts["sh_mid"])
        ear_mid, eye_mid = ip(pts["ear_mid"]), ip(pts["eye_mid"])

        for p in pts["face"]:  # face landmarks
            cv2.circle(frame, ip(p), max(2, r // 2), BGR_SOFT, -1, cv2.LINE_AA)

        cv2.line(frame, sh_l, sh_r, BGR_SOFT, max(1, th // 2), cv2.LINE_AA)  # shoulders
        neck_len = int(distance(sh_mid, ear_mid)) or 1
        cv2.line(
            frame, sh_mid, (sh_mid[0], sh_mid[1] - neck_len), BGR_SOFT, 1, cv2.LINE_AA
        )  # vertical reference
        cv2.line(frame, sh_mid, ear_mid, neck_color, th, cv2.LINE_AA)  # neck line

        for p in (sh_l, sh_r, ip(pts["l_ear"]), ip(pts["r_ear"])):
            cv2.circle(frame, p, r, neck_color, -1, cv2.LINE_AA)
        cv2.circle(frame, ear_mid, r, neck_color, -1, cv2.LINE_AA)
        for p in (ip(pts["l_eye"]), ip(pts["r_eye"])):
            cv2.circle(frame, p, r, dist_color, -1, cv2.LINE_AA)

        # eyes to the screen centre (the webcam sits just above it, bottom-centre of the image)
        screen_pt = (w // 2, h - int(0.05 * h))
        cv2.line(frame, eye_mid, screen_pt, dist_color, max(1, th // 2), cv2.LINE_AA)
        cv2.circle(frame, screen_pt, r + 2, dist_color, max(2, th // 2), cv2.LINE_AA)
        put_text(
            frame,
            "screen",
            (screen_pt[0] + r + 10, screen_pt[1] + 5),
            BGR_SOFT,
            fs * 0.7,
            1,
        )
        if dist_label:
            mid = ((eye_mid[0] + screen_pt[0]) // 2, (eye_mid[1] + screen_pt[1]) // 2)
            put_text(frame, dist_label, (mid[0] + 12, mid[1]), dist_color, fs, 2)

    # -- finish -------------------------------------------------------------
    def finish(self):
        summary = None
        if self.stats is not None:
            self.stats.end = time.time()
            summary = self.stats.summary()
        try:
            self.landmarker.close()
        except Exception:
            pass
        return summary
