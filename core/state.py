"""
stats.py - measure, don't guess.  Rolling timings per stage.

    from core import stats
    with stats.timer("hud.draw"):
        ...draw...
    stats.tick("hud.frame")          # count events -> rate per second

    stats.report()  ->  "hud.draw 4.1 ms | hud.frame 19.8/s"

Thread-safe. Keeps the last WINDOW samples per stage.
"""
import threading
import time
from collections import deque
from contextlib import contextmanager

WINDOW = 100

_lock = threading.Lock()
_durations = {}   # name -> deque of seconds
_ticks = {}       # name -> deque of timestamps


@contextmanager
def timer(name):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        record(name, time.perf_counter() - t0)


def record(name, seconds):
    with _lock:
        _durations.setdefault(name, deque(maxlen=WINDOW)).append(seconds)


def tick(name):
    with _lock:
        _ticks.setdefault(name, deque(maxlen=WINDOW)).append(time.perf_counter())


def avg_ms(name):
    with _lock:
        d = list(_durations.get(name, ()))
    return sum(d) / len(d) * 1000 if d else None


def rate(name):
    """Events per second over the recorded window."""
    with _lock:
        t = list(_ticks.get(name, ()))
    if len(t) < 2 or t[-1] == t[0]:
        return None
    return (len(t) - 1) / (t[-1] - t[0])


def report():
    with _lock:
        names_d = sorted(_durations)
        names_t = sorted(_ticks)
    parts = [f"{n} {avg_ms(n):.1f} ms" for n in names_d]
    parts += [f"{n} {rate(n):.1f}/s" for n in names_t if rate(n) is not None]
    return " | ".join(parts) if parts else "(no stats yet)"


def reset():
    with _lock:
        _durations.clear()
        _ticks.clear()


def start_reporter(stop_event, every=5.0, log=None):
    """Background thread that logs report() every few seconds."""
    def loop():
        while not stop_event.wait(every):
            (log.info if log else print)("stats: " + report())
    threading.Thread(target=loop, daemon=True, name="stats").start()
