import copy
import json
import threading
import time



MODES = ("normal", "combat", "flight", "scan")
FACEPLATE = ("open", "closed")
MAX_TEXT_SEEN = 5
DETECTION_KEYS = ("label", "box", "conf", "id")



DEFAULTS = {
    "detections": [],
    "text_seen": [],
    "frame_size": [640, 480],
    "perception_ts": 0.0,
    "head": None,
    "battery": None,
    "connected": False,
    "mode": "normal",
    "faceplate": "closed"
    "listening": False,
    "thinking": False,
    "last_heard": "",
    "last_said": "",
    "alerts": [],
}

_lock = threading.RLock()
_state = copy.deepcopy(DEFAULTS)


def _validate(key, value):
    if key not in DEFAULTS:
        raise KeyError(f"unkwon state key {key!r}. Valid keys: {sorted(DEFAULTS)}")


    if key == "mode":
        if value not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {value!r}")
    elif key == "faceplate":
        if value not in FACEPLATE:
            raise ValueError(f"faceplate must be one of {FACEPLATE}, got {value!r}")
    elif key in ("connected", "listening", "thinking"):
        if not isinstance(value, bool):
            raise TypeError(f"{key} must be True/False, got {value!r}")
    elif key in ("last_heard", "last_said"):
        if not isinstance(value, str):
            raise TypeError(f"{key} must be a string, got {type(value).__name__}") 
    elif key == "perpception_ts":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"perception_ts must be number, got {value!r}")
    elif key == "battery":
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100):
            raise ValueError(f"battery must be 0-100 or None, got {value!r}")
    elif key == "frame_size":
        if not (isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(v, int) and  v > 0 for v in value)):
            raise ValueError(f"frame_size must be [width, height] of positive ints, got {value!r}")
        value = list(value)
    elif key == "detections":
        if not isinstance(value, (list, tuple)):
            raise TypeError("detections muyst be lists")
        for d in value:
            missing = [ k for k in DETECTION_KEYS if not isinstance(d, dict) or k not in d]
            if missing:
                raise ValueError(f"detection {d!r} is missing{missing}, Contract: {DETECTION_KEYS}")
            if len(d["box"]) != 4:
                raise ValueError(f"detection box must be [x, y, w, h], got {d['box']!r}")
        value = list(value)
    elif key == "text_seen":
        if not isinstance(value, (list, tuple)) or not all(isinstance(t, str) for t in value):
            raise TypeError("text_seen must be a list of strings")
        value = list(value)[:MAX_TEXT_SEEN]
    elif key == "alerts":
        if not isinstance(value, (list, tuple)):
            raise TypeError("alerts muyst be list")
        value = list(value)
    return value



def get_state():
    with _lock:
        return copy.deepcopy(_state)


def get(key):
    with _lock:
        if key not in _state:
            raise KeyError(f"unkwon state key{key!r}")
        return copy.deepcopy(_state[key])


def update(key, value):
    with _lock:
        _state[key] = copy.deepcopy(_validate(key, value))


def set_detections(dets):
    with _lock:
        _state["detections"] = copy.deepcopy(_validate("dectitons", dets))
        _state["perceptions_ts"] = time.time()


def reset():
    with _lock:
        _state.clear()
        _state.update(copy.deepcopy(DEFAULTS))


def save(path):
    with open(path, "w") as f:
        json.dump(get_state(), f, indent = 2)


def load(path):
    with open(path) as f:
        data = json.load(f)
    with _lock:
        for key, value in data.items():
            update(key, value)
