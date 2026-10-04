import time
import cv2
from  ultralytics import YOLO

model = YOLO("yolov8n.pt")
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

t0, n = time.time(), 0
while True:
    ok, frame = cap.read()
    if not ok:
        break
    r = model(frame, verbose=False)[0]
    labels = [r.names[int(c)] for c in r.boxes.cls]
    n += 1
    fps = n / (time.time() - t0)
    print(f"{fps:5.1f} fps | {labels}")
    cv2.imshow("yolo", r.plot())
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cap.release()
cv2.destroyAllWindows()
