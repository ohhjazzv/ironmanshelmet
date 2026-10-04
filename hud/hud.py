"""
hud.py - reads state ~20x/sec and draws the overlay.  (owner: Jaz)

    python -m hud.hud                 # fakestate + webcam background
    python -m hud.hud --no-camera     # fakestate on black
    python -m hud.hud --scenario busy
Press q to quit. Weeks 2-4 build this out; see the spec's element table.
"""
import argparse
import threading
import time

import cv2
import numpy as np

import config
from core import state, stats
from hud import layouts


class Camera:
    """Latest-frame-only webcam reader. Never queues old frames."""

    def __init__(self, source):
        self.frame = None
        self._stop = threading.Event()
        self.cap = None
        if source == "webcam":
            self.cap = cv2.VideoCapture(config.WEBCAM_INDEX)
        elif source.startswith("file:"):
            self.cap = cv2.VideoCapture(source[5:])
        if self.cap is not None and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_W)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_H)
            threading.Thread(target=self._loop, daemon=True, name="camera").start()

    def _loop(self):
        while not self._stop.is_set():
            ok, f = self.cap.read()
            if ok:
                self.frame = cv2.resize(f, (config.FRAME_W, config.FRAME_H))
            else:
                time.sleep(0.05)

    def latest(self):
        return None if self.frame is None else self.frame.copy()

    def stop(self):
        self._stop.set()


def black_frame():
    return np.zeros((config.FRAME_H, config.FRAME_W, 3), np.uint8)


def render(bg, s):
    """Pure function: background + state -> preview frame. Easy to test."""
    draw = layouts.LAYOUTS.get(s["mode"], layouts.normal)
    return draw(bg, s)


def run(stop_event, camera=None, show=True, on_frame=None):
    period = 1.0 / config.HUD_FPS
    while not stop_event.is_set():
        t0 = time.perf_counter()
        s = state.get_state()
        bg = camera.latest() if camera else None
        with stats.timer("hud.draw"):
            preview = render(bg if bg is not None else black_frame(), s)
        stats.tick("hud.frame")
        if on_frame:
            on_frame(preview, s)     # week 5: protocol.send_hud(to_oled(...))
        if show:
            cv2.imshow("HUD", preview)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                stop_event.set()
        time.sleep(max(0, period - (time.perf_counter() - t0)))
    if show:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    from core import fakestate
    p = argparse.ArgumentParser()
    p.add_argument("--no-camera", action="store_true")
    p.add_argument("--scenario", default="default")
    args = p.parse_args()
    fake_stop = fakestate.start(args.scenario)
    cam = None if args.no_camera else Camera(config.CAMERA_SOURCE)
    stop = threading.Event()
    try:
        run(stop, cam)
    finally:
        fake_stop.set()
        if cam:
            cam.stop()
