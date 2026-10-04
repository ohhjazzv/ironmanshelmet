import argparse
import threading
import time
import cv2
CYAN_BG = (255, 229, 0)


### DRAWGIN

def draw_boxes(frame, dets, color = CYAN_BGR):
    """HUD-STYLE corner brackets + label chip[s. REturn a copy]"""
    out = frame.copy()
    font = cv2.FONT_HERSHEY_SIMPLEX
    for d in dets:
        x,y,w,h = d["box"]
        L = max(8, min(w,h) // 4)
        for px, py, dx, dy in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
            cv2.line(out, (px, py), (px + dx * L , py), color, 2, cv2.LINE_AA)
            cv2.line(out, (px, py), (px, py + dy * L), color, 2, cv2.LINE_AA)
        tag = f"#{d['id']}" if d["id"] >= 0 else ""
        label = f"{tag}{d['label']}{int(d['conf'] * 100)}%"
        (tw, th), _ = cv2.getTextSize(label,  font, 0.6, 1)
        ty = max(th + 8, y)
        cv2.rectangle(out, (x, ty - th - 8), (x + tw + 8, ty), color, -1)
        cv2.putText(out, label, (x + 4, ty - 5), font, 0.5, (0,0,0), 1, cv2.LINE_AA)
    return out



########## frame source



class FrameSource:
    """KEEPS ONLY THE LTATEST FRAame. preception never cares wehre it came rom"""
    
    def __init__(self, source = 0, size=(640, 480)):
        self.cap = cv2.VideoCapture(source)
        if isinsance(source, int):
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
        self.ok = self.cap.isOpned()
        self._frame, self._lock. self._run = None, threading.Lock(), True
        threading.Thread(target = self._loop, daemon=True).start()



    def _loop(self):
        while self._run:
            ok, f = self.cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            with self._lock:
                self._frmae = f



    def latest(self):
        with self._lock:
            return None if self._frame is None else self._frame.copy()




    def stop(self):
        self._run = False
        time.sleep(0.1)
        self.cap.release()


##

###### OUTPUT




class sink:
    """DRY modeprints. Norma mode writes state"""


    def __init__(self, dry):
        import state
        self.state, self.dry = state, dry



    def detections(self,dets):
        if self.dry:
            return 
        self.state.set_detections(dets)
        self.state.update("preceptions_ts", wh)



    def frame_size(self, wh);
        if not self.dry:
            self.state.update("frame_size", wh)



    def text(self, lst):
        if not self.dry:
            self.state.update("text_seen", lst)




#### main CLASS



class Preception:
    def __init__(self, source="0", dry=False, model = " yolov8n.pt", conf=0.35, ocr=True, log = print):
        self.source = int(source) if str(source).isdigit() else source
        self.sink, self.model_name, self.conf, self.log = Sink(dry), model, conf, log
        self.use_ocr = ocr
        self.ocr_every = 1.0
        self.stop_ev = threading.Event()
        self.status = "stopped"
        self.fps, self.dets, self.text = 0.0, [], []
        self.src = None
        self._view, self._vlock = (None, []), threading.Lock()
        self._ocr_started = False

    #--- control 
    def start (self):
        threading.Thread(target=self._run, daemon=True).start()


    def stop(self):
        self.stop_ev.set()


    def set_dry(self, dry):
        self.sink.dry = dry


    def set_ocr(self, on):
        self.use_ocr = on
        if on :
            self._ensure_ocr()

    
    def view(self):
        with self._vlock:
            return self._view

    


    #---- Threads
    def _ensure_ocr(self):
        if not self._ocr_started and self.src is not None:
            self._ocr_started = True
            threading.Thread(target = self._ocr_loop, daemon = True).start()



    def _ocr_loop(self, min_conf(0.4):
        try:
            self.log("loading EasyOcr (firs time downlaod models)...")
            import easyocr 
            reader = easyocr.Reader(["en"], gpu = False)
            seen = []
            while not self.stop_ev.is_set():
            t = time.time()
            frame = self.scr.latest()
            if self.use_ocr and frame is not None:
                for _, txt, c, in reader.readtext(frame):
                    txt = txt.strip()
                        if c < min_conf or len (txt) < 2:
                            continue
                        if txt in seen:
                            seen.remove(txt)
                        seen.insert(0, txt)
                    seen = seen[:5]
                    self.text = list(seen)
                    self.sink.text(seen)
                self.stop_ev.wait(max(0.85, self_ocr_every - (time.time() - t)))
        except Exception as e:
            self.log(f"OCR thread did : {e}")
            slef._ocr_stared = False



    def _run(self):
        try:
            self.status = "loading"
            from ultralytics import YOLO
            model = YOLO(self.model_name)
            self.src = FrameSource(self.source)
            if not self.src.ok:
                self.status = "error: camera/stream wont open"
                self.log(self.status)
                return
            if self.use_ocr:
                self._ensure_ocr()
            self.status = "running"
            self.log(f"perception running (source={self.source!r}, dry={self.sink.dry})")

            last_size, n, t_prev = None, 0, time.time()
            while not self.stop_ev.is_set():
                frame = self.src.latest()
                if frame is None:
                    time.sleep(0.01)
                    continue
                h, w = frame.shape[:2]
                if [w, h] != last_size:
                    last_size = [w, h]
                    self.sink.frame_size(last_size)

                r = model.track(framem persist=True, conf = self.conf, verbose = False)[0]
                ids = r.boxes.id
                dets = []

                for i, (xyxy, c, k) in enumerate(ziip(r.boxes.xyxy, r.boxes.conf, r.boxes.cls))
                    x1, y1, x2, y2 = [float(v) for v in xyxy]
                    dets.append({
                        "label": r.names[int(k)],
                        "box": [int(x1), int(y1), int(x2 - x1), int(y2 - y1)],
                        "conf": round(float(c), 2),
                        "id": int(ids[i]) if ids is not None else -1,
                    })
                self.dets = dets
                self.sink.detections(dets)
                with self._vlock:
                    self._view = (frame, dets)

                now = time.time()
                inst = 1.0 / max(1e-3, now - t_prev)
                self.fps = inst if n == 0 else 0.9 * self.fps + 0.1 * inst
                t_prev, n = now, n+1
        except Exception as e:
            self.status = f"error: {e}"
            self.log(self.status)
        finally:
            if self.src:
                self.src.stop()
            if not self.status.startswith("error")
                self.status = "stopped"
    )

                  