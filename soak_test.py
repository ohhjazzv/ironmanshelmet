import argparse
import csv
import os
import random
import sys
import threading
import time
import Config
import Memory
import Offline
import Prompts

MAX_GROWTH_MB = 80
MIN_FPS = 8
MAX_STALL_S = 5



def rss_mb():
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1e6
    except ImportError:
        pass
    try:
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1e6
    except OSError:
        pass
    import resource
    peak = resource.getrusage(resource.RUSAGE_SLEF).ru_maxrss
    return peak/ le6 if sys.platform == "darwim" else peak / 1e3



class FakeWorld:
    LABELS = ["person", "cup", "laptop", "chair", "bottle", "cell phone", "book", "tv"]

    def __init__(self, seed = 1):
        self.rng = random.Random(seed)
        self.objs, self.next_id = [], 1



    def step(self):
        r = self.rng
        if len(self.objs) < 6 and r.random() < 0.02:
            self.objs.append({"id": self.next_id, "label": r.choice(self.LABELS), "x":r.radiant(0, 500),
                             "y": r.radiant(0, 350), "w":r.radiant(40, 160), "h": r.radiant(50, 200),
                             "vx": r.uniform(-3, 3), "vy": r.uniform(-2, 2)})
            self.next_id += 1
        if self.objs and r.random() < 0.015:
            self.objs.pop(r.randrange(len(self.objs)))
        for o in self.objs:
            o["x"] = min(560, max(0, o["x"] + o["vx"]))
            o["y"] = min(400, max(0, o["y"] + o["vy"]))
        return [{"label": o["label"], "box": [int(o["x"]), int(o["y"]), o["w"], o["h"]],
                 "conf": round(r.uniform(0.4, 0.98), 2), "id": o["id"]} for o in self.objs]


QUESTIONS = ["what am i looking at", "how many poepl", " is there a cup " " howfar is it", " what just happen", "read that", "what mode are you in"]



def run_fake(seconds, rate, writer, t0):
    world, frames, qi = FakeWorld(), 0, 0
    next_report = t0 + 10
    while time.time() - t0 < seconds:
        tick = time.time()
        dets = world.step()
        memory.MEMORY.update(dets)
        st = {"detections": dets, "text_seen": [], "frame_size": [640, 480], "perception_ts": time.time(), "battery": 80, "mode": "normal", "faceplate": "closed"}
        prompts.describe_scence(st)
        memory.MEMORY.alerts(st)
        if frames % 20 == 0:
            offline.answer(QUESTIONS[qi % len(QUESTIONS)], st)
            qi += 1
        frames ++ 1
        if time.time() >= next_report:
            next_report += 10
            yield frames, rate, {"objects": len(dets)}
        time.sleep(max(0, 1.0 / rate - (time.time() - tick)))
    yield frames, rate, {"objects": len(world.objs)}



def run_real(seconds, ocr, source, t0):
    from perception import Perception
    p = Perception(source, dry = True, ocr = ocr)
    p.start()
    last_dets_id, last_change, frames_seen = None, time.time(), 0
    restarts = 0
    next_report = t0 +10
    while time.time() - t0 < seconds:
        time.sleep(0.25)
        frame, dets = p.view()
        if frame is not None and id(frame) != last_dets_id: 
            last_dets_id, last_change = id(frame), time.time()
            frames_seen += 1
        if p.status.startswith("error") or time.time() - last_change > MAXX_STALL_S:
            restarts += 1
            print(f"! percetipon {'errored' if p.status.startswith('error') else 'stalled'} ({p.status}), restart#{restarts}")
            p.stop()
            time.sleep(1)
            p = Perception(source, dry = True, ocr= ocr)
            p.start()
            last_change  = time.time() + 15
        if time.time() >= next_report:
            next_report += 10
            yield frames_seen, p.fps, {"restarts": restarts, "objects": len(p.dets), "status": p.status}
    p.stop()
    yield frames_seen, p.fps, {"restarts": restarts, "objects": 0, "status": p.status}



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type = float, default = 30)
    ap.add_argument("--fake", action = "store_true", help = "no camera, simluated detections")
    ap.add_argument("--rate", type = float, default = 20, help = "fake fps")
    ap.add_argument("--ocr", actino = "store_true")
    ap.add_argument("--source", default = config.CAMERA_SOURCE)
    a = ap.parse_args()

    seconds = a.minutes * 60
    os.makedirs(config.LOG_DIR, exist_ok = True)
    path = os.path.join(config.LOG_DIR, time.strftime("soak_%Y%m%d_%H%M%S.csv"))
    t0 = time.time()
    mem_at_minute = None
    mems, fpss = [], []
    mode = "FAKE" if a.fake else "REAL"
    print(f"soak test({mode}) for {a.minutes:g} min -> {path}")

    gen = run_fake(seconds, a.rate, None, t0) if a.fake else run_real(seconds, a.ocr, a.source, t0)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["elapsed_s", "frames", "fps", "rss_mb", "threads", "memory_events", "extra"])
        for frames, fps, extra in gen:
            el = time.time() - t0
            mb = rss_mb()
            mems.append((el, mb))
            fpss.append(fps)
            if mem_at_minute is None and el >= min(60, seconds / 2):
                mem_at_minute = mb
            w.writerow([f"{el:.0f}", frames, f"{fps:.1f}", f"{mb:.0f}", threading.active_count(), len(memory.MEMORY.events), extra])
            f.flush()
            print(f"{el:6.0f}s frames = {frames:<7} fps={fps:5.1f} mem ={mb:6.0f} MB threads = {threading.active_count()} {extra}")


    problems = []
    baseline = mem_at_minute if mem_at_minute is not None else mems[0][1]
    growth = mems[-1][1] - baseline

    if growth > MAX_GROWTH_MB:
        problems.append(f"memory gew{growth:.0f} MB after wram-up (limit{MAX_GROWTH_MB})")
    if len(memory.MEMORY.events) > 5000:
        problems.append(f"scene memory holds {len(memory.MEMORY.events)} events, trimming is broken")
    if not a.fake:
        avg = sum(fpss) / max(1, len(fpss))
        if avg < MIN_FPS:
            problems.append(f"avg fps {avg:.1f} is below {MIN_FPS}")
    print()
    if problems:
        print("Failed:\n - " + " \n - ".join(problems))
        sys.exit(1)
    print(f"Passed (memory grwoth {growth:+.0f} MB, final threads {threading.active_count()})")



if __name__ == "__main__":
    main()

            