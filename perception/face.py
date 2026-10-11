import argparse
import os
import urllib.request

import cv2
import numpy as np

MODEL_DIR = "models"
FACES_DIR = "faces"
MATCH = 0.36     # 0..1, higher = stricter (OpenCV recommends 0.363). Below this the face is "UNKNOWN"

URL = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
DETECT = "face_detection_yunet_2023mar.onnx"
RECOG = "face_recognition_sface_2021dec.onnx"
FILES = {DETECT: URL + "face_detection_yunet/" + DETECT,
         RECOG: URL + "face_recognition_sface/" + RECOG}


def get_models():
    """Download the two model files the first time (about 40 MB)."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    for name, url in FILES.items():
        path = os.path.join(MODEL_DIR, name)
        if not os.path.exists(path) or os.path.getsize(path) < 10_000:
            print("downloading", name, "...")
            urllib.request.urlretrieve(url, path)
    return os.path.join(MODEL_DIR, DETECT), os.path.join(MODEL_DIR, RECOG)


class FaceID:
    def __init__(self):
        det_path, rec_path = get_models()
        self.detector = cv2.FaceDetectorYN.create(det_path, "", (320, 320), 0.8)
        self.recogniser = cv2.FaceRecognizerSF.create(rec_path, "")
        self.known = self.load_known()        # {"jaz": array of fingerprints}

    def load_known(self):
        known = {}
        if os.path.isdir(FACES_DIR):
            for f in os.listdir(FACES_DIR):
                if f.endswith(".npy"):
                    known[f[:-4]] = np.load(os.path.join(FACES_DIR, f))
        return known

    def find(self, frame):
        """Return the raw faces YuNet found (one row per face)."""
        h, w = frame.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame)
        return [] if faces is None else faces

    def fingerprint(self, frame, face):
        crop = self.recogniser.alignCrop(frame, face)
        return self.recogniser.feature(crop)

    def who(self, fp):
        """Compare one fingerprint with everyone saved. Returns (name, score)."""
        best, best_score = "UNKNOWN", 0.0
        for name, saved in self.known.items():
            score = max(self.recogniser.match(fp, s.reshape(1, -1), cv2.FaceRecognizerSF_FR_COSINE)
                        for s in saved)
            if score > best_score:
                best, best_score = name, score
        if best_score < MATCH:
            best = "UNKNOWN"
        return best, best_score

    def identify(self, frame):
        """Main function: list of {"name", "score", "box": [x, y, w, h]}."""
        out = []
        for face in self.find(frame):
            name, score = self.who(self.fingerprint(frame, face))
            x, y, w, h = [int(v) for v in face[:4]]
            out.append({"name": name, "score": round(float(score), 2), "box": [x, y, w, h]})
        return out


def enroll_photos(name, paths):
    """Same as enroll() but from photo files instead of the webcam."""
    fid = FaceID()
    saved = []
    for p in paths:
        img = cv2.imread(p)
        if img is None:
            print("can't open", p)
            continue
        faces = fid.find(img)
        if len(faces) != 1:
            print(p, "- need exactly one face, found", len(faces))
            continue
        saved.append(fid.fingerprint(img, faces[0])[0])
        print(p, "- ok")
    save(name, saved)


def save(name, saved):
    if not saved:
        print("nothing saved")
        return
    os.makedirs(FACES_DIR, exist_ok=True)
    path = os.path.join(FACES_DIR, name.lower() + ".npy")
    if os.path.exists(path):                       # add to what's already there
        saved = list(np.load(path)) + saved
    np.save(path, np.array(saved))
    print("saved", len(saved), "fingerprints for", name)


def enroll(name, shots=10):
    """Save `shots` fingerprints of the one face in front of the camera."""
    fid = FaceID()
    cam = cv2.VideoCapture(0)
    saved = []
    print("Look at the camera. Press SPACE to take a shot, turn your head a little each time. q to stop.")
    while len(saved) < shots:
        ok, frame = cam.read()
        if not ok:
            print("no webcam")
            break
        faces = fid.find(frame)
        show = frame.copy()
        for f in faces:
            x, y, w, h = [int(v) for v in f[:4]]
            cv2.rectangle(show, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(show, f"{name}: {len(saved)}/{shots}  SPACE = shot", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("enroll", show)
        key = cv2.waitKey(30) & 0xFF
        if key == ord("q"):
            break
        if key == ord(" "):
            if len(faces) != 1:
                print("need exactly one face in view, found", len(faces))
                continue
            saved.append(fid.fingerprint(frame, faces[0])[0])
            print("shot", len(saved))
    cam.release()
    cv2.destroyAllWindows()
    save(name, saved)


def test():
    fid = FaceID()
    print("known:", list(fid.known) or "nobody yet - run with --enroll jaz")
    cam = cv2.VideoCapture(0)
    while True:
        ok, frame = cam.read()
        if not ok:
            break
        for p in fid.identify(frame):
            x, y, w, h = p["box"]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, f'{p["name"]} {p["score"]}', (x, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("face test", frame)
        if cv2.waitKey(30) & 0xFF == ord("q"):
            break
    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--enroll", metavar="NAME")
    ap.add_argument("--photos", nargs="+", metavar="FILE")
    args = ap.parse_args()
    if args.enroll and args.photos:
        enroll_photos(args.enroll, args.photos)
    elif args.enroll:
        enroll(args.enroll)
    else:
        test()
