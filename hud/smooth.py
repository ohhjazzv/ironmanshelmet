"""
smooth.py - glide boxes between perception updates instead of jumping.

Perception updates ~15 times a second, the HUD draws 20+. Boxes keyed by
tracker id ease toward their new position each frame. Untracked boxes
(id -1) are drawn as-is.
"""


class BoxSmoother:
    def __init__(self, alpha=0.5):
        self.alpha = alpha      # 1.0 = no smoothing, lower = smoother but laggier
        self._boxes = {}        # id -> [x, y, w, h] as floats

    def apply(self, detections):
        """Returns new detection dicts with smoothed boxes. Doesn't mutate input."""
        out, seen = [], set()
        for d in detections:
            tid = d.get("id", -1)
            if tid < 0:
                out.append(d)
                continue
            seen.add(tid)
            target = [float(v) for v in d["box"]]
            prev = self._boxes.get(tid)
            if prev is None:
                cur = target
            else:
                cur = [p + (t - p) * self.alpha for p, t in zip(prev, target)]
            self._boxes[tid] = cur
            out.append({**d, "box": [int(round(v)) for v in cur]})
        for tid in list(self._boxes):
            if tid not in seen:
                del self._boxes[tid]
        return out
