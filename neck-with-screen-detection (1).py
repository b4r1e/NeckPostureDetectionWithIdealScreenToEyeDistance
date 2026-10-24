"""
Neck Posture Detector (v4 Sound
  - GOOD -> BAD  : plays a "warning" sound (two low beeps)
  - BAD  -> GOOD : plays a "confirm" sound (one higher beep)

Usage:
    python neck_posture_detector_v4.py --source 0
    python neck_posture_detector_v4.py --source 0 --no-sound   # disable sound

Controls:
    c = calibrate (do this once, sitting with good posture)
    q = quit

Requirements:
    pip install opencv-python mediapipe numpy sounddevice
"""

import argparse
import math
import os
import time
import urllib.request
from collections import deque

import subprocess
import threading

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    PoseLandmarker,
    PoseLandmarkerOptions,
    RunningMode,
)

DEVIATION_LIMIT_PCT = 15        # % drop from your calibrated baseline = "bad"
SMOOTHING_WINDOW = 7          
BAD_STREAK_TO_FLIP = 10        
BAD_POSTURE_ALERT_SECONDS = 30  

MODEL_PATH = "pose_landmarker_lite.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)

LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
LEFT_EAR, RIGHT_EAR = 7, 8
LEFT_EYE, RIGHT_EYE = 2, 5

DISTANCE_MIN_CM = 40            #"too close"
DISTANCE_MAX_CM = 70            #"too far"

FONT = cv2.FONT_HERSHEY_SIMPLEX
COLOR_GOOD = (0, 255, 0)
COLOR_BAD = (0, 0, 255)
COLOR_WARN = (0, 255, 255)
COLOR_INFO = (255, 200, 0)

# Sound
def _play_blocking(path):
    # afplay is macOS's built-in command-line audio player - no extra
    # Python package needed, and it just works with mp3 out of the box.
    subprocess.run(["afplay", path], check=False)


def play_sound_file(path, enabled):
    if not enabled or not path:
        return
    # Run it in a daemon thread so the camera loop keeps running while
    # the mp3 plays instead of waiting for it to finish.
    threading.Thread(target=_play_blocking, args=(path,), daemon=True).start()


def raise_alert():
    print("[ALERT] Bad neck posture sustained too long - change your posture!")


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------
def ensure_model_downloaded(path=MODEL_PATH, url=MODEL_URL):
    if not os.path.exists(path):
        print(f"Downloading pose landmarker model to {path} ...")
        urllib.request.urlretrieve(url, path)
        print("Download complete.")
    return path


def midpoint(p1, p2):
    return (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2


def distance(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def tilt_from_vertical(p1, p2):
    vx, vy = (p2[0] - p1[0]), (p2[1] - p1[1])
    mag = math.hypot(vx, vy)
    if mag == 0:
        return 0.0
    cos_angle = max(-1.0, min(1.0, -vy / mag))
    return math.degrees(math.acos(cos_angle))


def main():
    parser = argparse.ArgumentParser(description="Calibrated neck posture detector with sound alerts")
    parser.add_argument("--source", default="0", help="Webcam index (e.g. 0) or path to a video file")
    parser.add_argument("--save", action="store_true", help="Save annotated output to output.mp4")
    parser.add_argument("--model", default=MODEL_PATH, help="Path to a pose_landmarker .task model file")
    parser.add_argument("--no-sound", action="store_true", help="Disable sound alerts")
    parser.add_argument("--good-sound", default="correct.mp3",
                         help="Path to the mp3 played whenever posture status changes")
    parser.add_argument("--bad-sound", default="windows-error.mp3",
                         help="Path to the mp3 played whenever posture status changes")
    parser.add_argument("--ideal-distance-cm", type=float, default=60.0,
                         help="Your real face-to-screen distance (cm) when you press 'c' to calibrate")
    args = parser.parse_args()
    sound_enabled = not args.no_sound

    model_path = ensure_model_downloaded(args.model) if args.model == MODEL_PATH else args.model

    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video source: {source}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480

    writer = None
    if args.save:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter("output.mp4", fourcc, fps, (width, height))

    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=model_path),
        running_mode=RunningMode.VIDEO,
        num_poses=1,
    )
    landmarker = PoseLandmarker.create_from_options(options)

    ratio_history = deque(maxlen=SMOOTHING_WINDOW)
    tilt_history = deque(maxlen=SMOOTHING_WINDOW)

    baseline_ratio = None
    baseline_tilt = None

    face_history = deque(maxlen=SMOOTHING_WINDOW)
    baseline_face = None     
    distance_ok = True
    close_streak = 0

    is_good = True
    bad_streak = 0
    good_frames = 0
    bad_frames = 0
    alert_sent = False
    frame_index = 0
    start_time = time.time()

    print("Sit up straight and press 'c' to calibrate. Press 'q' to quit.")

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        h, w = frame.shape[:2]
        frame_index += 1
        timestamp_ms = int((time.time() - start_time) * 1000) or frame_index

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect_for_video(mp_image, timestamp_ms)

        key = cv2.waitKey(1) & 0xFF

        if not result.pose_landmarks:
            cv2.putText(frame, "No person detected", (10, 30), FONT, 0.9, COLOR_WARN, 2)
            if writer:
                writer.write(frame)
            cv2.imshow("Neck Posture Detector", frame)
            if key == ord("q"):
                break
            continue

        lm = result.pose_landmarks[0]

        def point(idx):
            p = lm[idx]
            return (p.x * w, p.y * h)

        l_shoulder = point(LEFT_SHOULDER)
        r_shoulder = point(RIGHT_SHOULDER)
        l_ear = point(LEFT_EAR)
        r_ear = point(RIGHT_EAR)

        shoulder_mid = midpoint(l_shoulder, r_shoulder)
        ear_mid = midpoint(l_ear, r_ear)
        shoulder_width = distance(l_shoulder, r_shoulder) or 1.0

        raw_ratio = distance(ear_mid, shoulder_mid) / shoulder_width
        raw_tilt = tilt_from_vertical(shoulder_mid, ear_mid)

        ratio_history.append(raw_ratio)
        tilt_history.append(raw_tilt)
        smooth_ratio = sum(ratio_history) / len(ratio_history)
        smooth_tilt = sum(tilt_history) / len(tilt_history)

        l_eye = point(LEFT_EYE)
        r_eye = point(RIGHT_EYE)
        face_history.append(distance(l_eye, r_eye))
        smooth_face = sum(face_history) / len(face_history)

        if key == ord("c"):
            baseline_ratio = smooth_ratio
            baseline_tilt = smooth_tilt
            baseline_face = smooth_face
            bad_streak = 0
            close_streak = 0
            is_good = True
            distance_ok = True
            print(f"Calibrated. baseline_ratio={baseline_ratio:.3f} baseline_tilt={baseline_tilt:.1f}deg "
                  f"ideal_distance={args.ideal_distance_cm:.0f}cm (face={baseline_face:.1f}px)")

        if baseline_ratio is None:
            cv2.putText(frame, "Not calibrated - sit straight & press 'c'", (10, 30),
                        FONT, 0.8, COLOR_WARN, 2)
            for pt in (l_shoulder, r_shoulder, l_ear, r_ear):
                cv2.circle(frame, (int(pt[0]), int(pt[1])), 5, COLOR_INFO, -1)
            if writer:
                writer.write(frame)
            cv2.imshow("Neck Posture Detector", frame)
            if key == ord("q"):
                break
            continue

        ratio_drop_pct = (baseline_ratio - smooth_ratio) / baseline_ratio * 100
        tilt_increase = smooth_tilt - baseline_tilt
        frame_is_bad = ratio_drop_pct > DEVIATION_LIMIT_PCT or tilt_increase > DEVIATION_LIMIT_PCT

        if frame_is_bad:
            bad_streak += 1
        else:
            bad_streak = max(0, bad_streak - 2)

        overall_before_update = is_good and distance_ok

        if bad_streak >= BAD_STREAK_TO_FLIP:
            is_good = False
        elif bad_streak == 0:
            is_good = True

        # Screen distancenya
        est_distance_cm = args.ideal_distance_cm * baseline_face / max(smooth_face, 1e-6)
        too_close = est_distance_cm < DISTANCE_MIN_CM
        too_far = est_distance_cm > DISTANCE_MAX_CM

        if too_close or too_far:
            close_streak += 1
        else:
            close_streak = max(0, close_streak - 2)

        if close_streak >= BAD_STREAK_TO_FLIP:
            distance_ok = False
        elif close_streak == 0:
            distance_ok = True

        overall_ok = is_good and distance_ok
        if overall_before_update and not overall_ok:
            play_sound_file(args.bad_sound, sound_enabled)
        elif not overall_before_update and overall_ok:
            play_sound_file(args.good_sound, sound_enabled)

        color = COLOR_GOOD if is_good else COLOR_BAD

        if is_good:
            good_frames += 1
            bad_frames = 0
            alert_sent = False
        else:
            bad_frames += 1
            good_frames = 0

        for pt in (l_shoulder, r_shoulder, l_ear, r_ear):
            cv2.circle(frame, (int(pt[0]), int(pt[1])), 5, color, -1)
        sm = (int(shoulder_mid[0]), int(shoulder_mid[1]))
        em = (int(ear_mid[0]), int(ear_mid[1]))
        cv2.line(frame, sm, em, color, 3)

        info_text = f"Ratio: {smooth_ratio:.2f} (drop {ratio_drop_pct:.0f}%)  Tilt: {smooth_tilt:.0f} deg"
        cv2.putText(frame, info_text, (10, 30), FONT, 0.7, color, 2)
        status_text = "GOOD POSTURE" if is_good else "BAD POSTURE"
        cv2.putText(frame, status_text, (10, 60), FONT, 0.9, color, 2)

        good_time = good_frames / fps
        bad_time = bad_frames / fps
        time_text = (f"Good posture: {good_time:.1f}s" if is_good
                     else f"Bad posture: {bad_time:.1f}s")
        cv2.putText(frame, time_text, (10, h - 20), FONT, 0.8, color, 2)

        dist_color = COLOR_GOOD if distance_ok else COLOR_BAD
        dist_text = (f"Distance: ~{est_distance_cm:.0f} cm (ideal {DISTANCE_MIN_CM}-{DISTANCE_MAX_CM})"
                     + ("" if distance_ok else ("  TOO CLOSE" if too_close else "  TOO FAR")))
        cv2.putText(frame, dist_text, (10, h - 50), FONT, 0.7, dist_color, 2)

        screen_pt = (w // 2, h - 15)
        eye_mid = (int((l_eye[0] + r_eye[0]) / 2), int((l_eye[1] + r_eye[1]) / 2))
        cv2.line(frame, eye_mid, screen_pt, dist_color, 1)
        cv2.circle(frame, eye_mid, 4, dist_color, -1)
        cv2.circle(frame, screen_pt, 7, dist_color, 2)
        cv2.putText(frame, "SCREEN", (screen_pt[0] + 12, screen_pt[1] + 5), FONT, 0.5, dist_color, 1)

        if bad_time > BAD_POSTURE_ALERT_SECONDS:
            if not alert_sent:
                raise_alert()
                alert_sent = True
            cv2.putText(frame, "ALERT: CHANGE YOUR POSTURE!", (10, 90), FONT, 0.9, COLOR_BAD, 2)

        if writer:
            writer.write(frame)

        cv2.imshow("Neck Posture Detector", frame)
        if key == ord("q"):
            break

    cap.release()
    if writer:
        writer.release()
    landmarker.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

"""
Kendala:
- Algoritmanya masih susah dalam mendeteksi postur leher, terutama yang sedikit miring.
- Adanya masalah lighting dan posisi kamera
- Belum ada ketentuan delay atau peringatan secara berperiodik atau tertentu seperti 30 detik. Karena
kalau berposisi tegang (Tegak terlalu lama) seharusnya juga disebut sebagai Bad posture
"""
