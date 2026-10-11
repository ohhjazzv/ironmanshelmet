import time

import cv2
import numpy as np
import psutil

from perception.face import FaceID

W, H = 640, 480
CYAN = (255, 230, 120)   # OpenCV colours are BGR, not RGB
RED = (60, 60, 255)
GREEN = (120, 255, 120)
WHITE = (255, 255, 255)


def crosshair(img):
    cx, cy = W // 2, H // 2
    cv2.line(img, (cx - 20, cy), (cx - 6, cy), CYAN, 1)
    cv2.line(img, (cx + 6, cy), (cx + 20, cy), CYAN, 1)
    cv2.line(img, (cx, cy - 20), (cx, cy - 6), CYAN, 1)
    cv2.line(img, (cx, cy + 6), (cx, cy + 20), CYAN, 1)
    cv2.circle(img, (cx, cy), 2, CYAN, -1)


def face_box(img, person):
    x, y, w, h = person["box"]
    known = person["name"] != "UNKNOWN"
    colour = GREEN if known else RED
    # corner brackets instead of a full box: looks more Iron Man
    L = w // 4
    for (px, py, dx, dy) in [(x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)]:
        cv2.line(img, (px, py), (px + dx * L, py), colour, 2)
        cv2.line(img, (px, py), (px, py + dy * L), colour, 2)
    label = person["name"].upper() if known else "UNKNOWN"
    cv2.putText(img, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, colour, 2)
    cv2.putText(img, f'match {int(person["score"] * 100)}%', (x, y + h + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 1)


def read_battery():
    """Real laptop battery. Returns (percent, charging) or (None, False) on a desktop."""
    b = psutil.sensors_battery()
    if b is None:
        return None, False
    return int(b.percent), bool(b.power_plugged)


def battery(img, percent, charging):
    x, y, w, h = W - 110, 15, 90, 14
    if percent is None:
        cv2.putText(img, "NO BATT", (x, y + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, CYAN, 1)
        return
    colour = CYAN if percent > 20 or charging else RED
    cv2.rectangle(img, (x, y), (x + w, y + h), colour, 1)
    cv2.rectangle(img, (x + 2, y + 2), (x + 2 + int((w - 4) * percent / 100), y + h - 2), colour, -1)
    text = f"{percent}%" + (" +" if charging else "")
    cv2.putText(img, text, (x - 55, y + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 1)


def main():
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, W)            # ask the webcam for 640x480
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    faces = FaceID()
    print("known faces:", list(faces.known) or "nobody - run: python -m perception.face --enroll jaz")
    batt, charging = read_battery()
    last_batt = time.time()

    while True:
        ok, frame = cam.read()
        if ok:
            frame = cv2.resize(frame, (W, H))
        else:
            frame = np.zeros((H, W, 3), np.uint8)   # no webcam: black screen

        if time.time() - last_batt > 5:              # battery only changes slowly
            batt, charging = read_battery()
            last_batt = time.time()

        people = faces.identify(frame)
        for p in people:
            face_box(frame, p)
        crosshair(frame)
        battery(frame, batt, charging)
        cv2.putText(frame, "MODE: NORMAL", (15, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.55, CYAN, 1)
        cv2.putText(frame, time.strftime("%H:%M:%S"), (15, H - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, WHITE, 1)
        if any(p["name"] == "jaz" for p in people):
            cv2.putText(frame, "WELCOME BACK, JAZ", (W // 2 - 120, H - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, GREEN, 2)

        cv2.imshow("HELMET HUD", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
