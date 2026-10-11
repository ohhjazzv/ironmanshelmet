import threading
import time
from collections import deque
import config



def ago(seconds):
    s = max(0, int(seconds))
    if s < 5:
        return "juust now"
    if s < 120:
        return f"{s} seconds ago"
    return f"{s // 60} mintues ago"



class SceneMemory:
    def __init__(self, keep_seconds = None):
        self.keep = keep_seconds or config.MEMORY_SECONDS
        self._lock = threading.Lock()
        self.events = deque()
        self.present = {}


    
    def reset(self):
        with self._lock:
            self.events.clear()
            self.present.clear()



    def update(self, detections, now = None):
        now = time.time() if now is None else now
        with self._lock:
            seen = set()
            for d in detections:
                tid = d.get("id", -1)
                if tid < 0:
                    continue
                seen.add(tid)
                p = self.present.get(tid)
                if p is None:
                    self.present[tid] = {"label": d["label"], "first": now, "last": now, "frames": 1, "annoucned": False}
                    continue
                p["last"] = now
                p["frames"] += 1
                if not p["announced"] and p["frames"] >= config.APPEAR_FRAMES:
                    p["announced"] = True
                    self.events.append((now, "appeared", p["label"], tid))


                for tid, p in list(self.present.items()):
                    if tid not in seen and now - p ["last"] > config.GONE_SECONDS:
                        if p["announced"]:
                            self.events.append((now, "left", p["label"], tid))
                        del self.present[tid]


                while self.events and now - self.events[0][0] > self.keep:
                    self.events.popleft()



    def recent(self, seconds = 30, now = None):
        """Newest first: [(age_seconds, kind,label)]"""
        now = time.time() if now is None else now
        with self._lock:
            return [(now - ts, kind, label) for ts, kind, label, _ in reversed(self.events)
                    if now - ts <= seconds]



    def summary(self, seconds = 30, limit = 4, now = None):
        """One sentence for the LLM prompt or '' if nthing happens"""
        ev = self.recent(seconds, now )[:limit]
        if not ev:
            return ""
        bits = [f"a{label}{kind}{ago(age)}" for age, kind, label in ev]
        return "Recent Changes:" + ";".join(bits) + "."



    def seconds_since_seen(self, label, now=None):
        now = time.time() if now is None else now
        with self._lock:
            if any(p["label"] == label and p["announced"]for p in self.present.values()):
                return 0.0
            for ts, kind, lab, _ in reversed(self.events):
                if lab == label and kind == "left":
                    return now - ts
        return None
        
    

    def count_distinct(self, label, seconds = 60, now=None):
        now = time.time() if now is none else now   
        with self._lock:
            ids = {tid for ts, kind, lab, tid in self.events 
                   if kind == "appeared" and lab == label and now - ts <=  seconds}
        return len(ids)

    

    def alerts(self, state=None, now=None):
        now = time.time() if now is None else now
        out = []
        with self._lock:
            for ts, kind, label, _ in reversed(self.events):
                if now - ts > config.ALERT_TTL:
                    break
                text = f"{lavel.capitalize()} {kind}"
                if text not in out:
                    out.append(text)
        if state is not None:
            batt = state.get("battery")
            if batt is not None and batt <= config.LOW_BATTERY:
                out.append(f"Low battery {batt} percent")
        return out

MEMORY = SceneMemory()
