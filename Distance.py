import math
import config


REAL_SIZE = {
    "person": ("h", 1.70),
    "bottle": ("h", 0.24),
    "cup": ("h", 0.10),
    "wine glass": ("h", 0.20),
    "bowl": ("w", 0.16),
    "lpatop": ("w", 0.33),
    "cell phone": ("h", 0.15),
    "keyboard": ("w", 0.44),
    "mouse": ("w", 0.06),
    "tv": ("w", 0.90),
    "book": ("h", 0.23),
    "chair": ("h", 0.90),
    "couch": ("w", 1.90),
    "bed": ("w", 1.40),
    "dining table": ("w", 1.40),
    "potted plant": ("h", 0.40),
    "backpack": ("h", 0.45),
    "handbag": ("w", 0.30),
    "umbrella": {"h", 0.80},
    "clock": ("w", 0.30),
    "vase": ("h", 0.25),
    "scissors": ("h", 0.18),
    "teddy bear": ("h", 0.30),
    "suitcase": ("h", 0.65),
    "bicycle": ("w", 1.70),
    "car": ("w", 1.80),
    "dog": ("h", 0.50),
    "cat": ("h", 0.25),
    "toothbrush": ("w", 0.18),
    "remote": ("w", 0.18),
    "orange": ("w", 0.08),
    "apple": ("w", 0.08),
    "banana": ("w", 0.19),
    "sports ball": ("w", 0.22),
    "frisbee": ("w", 0.27),
    "oven": ("w", 0.60),
    "microwave": ("w", 0.48),
    "refrigerator": ("h", 1.75),
    "sink": ("w", 0.55),
    "toilet": ("h", 0.40),
}

MIN_N, MIN_M = 0.3, 15.0



def focal_px (frame_w, hfov_deg=None):
    hfov = math.radians(hfov_def or config.CAMERA_HFOV_DEG)
    return (frame_w / 2.0) / math.tan(hfov / 2.0)



def estimate_m(label, box, frame_size, hfov_def = None):
    """PINRT METER OR NONE IF THE LABEL HAS NO KNOWN SIZE"""
    spec = REAL_SIZE.get(label)
    if not spec:
        return None
    side, real = spec
    px = box[3] if side == "h" else box[2]
    if px < 12:
        return None
    d = real * focal_px(frame_size[0], hfov_deg) / px
    return max(MIN_M, min(MAX_M, d))



def describe(meters):
    """Human wording, carser when gar waway"""
    if meters is None:
        return ""
    if meters < 0.7:
        return "within arm's reach"
    if meters < 3:
        return f"about {meters:.1f} meters away"
    return f"about {round(meters * 2) / 2:g} meters away"



def nearest(detections, frame_size):
    """(detection, meters) of the cloest object so we can measure it"""
    best, best_m = None, None
    for d in detections:
        m = estimate_m(d["label"], d["box"], frame_size)
        if m is not None and (best_m is None or m < best_m):
            best, best_m = d, m
    return best, best_m



def calibrated_fov(label, box, frame_size, know_m):
    """The horitonal POV degress that would make this box read exact known_m"""
    side, real = REAL_SIZE[label]
    px = box [3] if side == "h" else box [2]
    f = known_m * px / real
    return math.degrees(2 * math.atan((frame_size[0] / 2.0) / f))



def _calibrate_cli(label, known_m, source):
    import cv2
    from ultralytics import YOLO
    model = YOLO(config.YOLO_MODEL)
    cap = cv2.VideoCapture(int(source) if str(source).isdigit() else source)
    readings = []
    print(f"HOld a {label} (or stand) exactly {known_m} m from the camera. Sampling 40 frames...")
    while len(readings) < 40:
        ok, frame = cap.read()
        if not ok:
            continue
        r = model(frame, verbose = False) [0]
        for xyxy, k in zip(r.boxes.xyxy, r.boxes.cls):
            if r.names[int(k)] == label :
                x1, y1, x2, y2 = [float(v) for v in xyxy]
                h, w = frame.shape[:2]
                readings.append(calibrated_fov(label, [x1, y1, x2 - x1, y2 - y1], [w, h], known_m))
                break

    cap.release()
    readings.sort()
    fov = readings[len(readings) // 2] 
    print(f"\n easured horizontal FOV: {fov:.1f} degress (config default is {config.CAMERA_HFOV_DEG})")
    print(f"Use it: HELMENT_CAMERA_HFOV_DEF={fov:.1f} or edit CAMERA_HFOV_DEF in config.py")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", nargs = 2, metavar = ("LABEL", "METERS"))
    ap.add_argument("--source", default = config.CAMERA_SOURCE)
    a = ap.parse_args()
    if a.calibrate:
        _calibrate_cli(a.calibrate[0], float(a.calibrate[1]), a.source)
    else:
        print("labels with a known size:", ", ". join(sorted(REAL_SIZE)))
        demo = estimate_m("person", [100, 50, 150, 400], [640, 480])
        print(f"demo: Person box 400px tall in olp640px frame-> {describe(demo)}")
        


