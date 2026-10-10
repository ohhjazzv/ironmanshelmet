import os


def  _env(name, default):
    raw = os.environ.get("HELMENT_" + name)
    if raw is None:
        return default
    try:
        return type(default)(raw)
    except ValueError:
        print(f"[config] bad value for HELMET_{name}={raw!r}, using {default!r}")
        return default


GROQ_MODEL = _env("GROQ_MODEL", "llama-3.1-8b-instant")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.0-flash")
LLM_TIMEOUT = _env("LLM_TIMEOUT", 10.00)
LLM_MAX_TOKENS = _env("LLM_MAX_TOKENS", 120)
WAKE_THRESH = _env("WAKE_THRES", 0.5)
SILENCE_RMS = _env("SILENCE_RMS", 500)
SILENCE_SECS = _env("SILENCE_SECS", 1.0)
MAX_RECORD_SECS = _env("MAX_RECORD_SECS", 8)
WHISPER_MODEL = _env("WHISPER_MODEL", "base.en")
TTS_RATE = _env("TTS_RATE", 175)
YOLO_MODEL = _env("YOLO_MODEL", "yolov8n.pt")
YOLO_CONF = _env("YOLO_CONF", 0.35)
CAMERA_SOURCE = _env("CAMERA_SOUECE", "0")
OCR_EVERY = _env("OCR_EVERY", 1.0)
OCR_MIN_CONF = _env("OCR_MIN_CONF", 0.4)
STALE_AFTER = _env("STALE_AFTER", 3.0)
CAMERA_HFOV_DEG = _env("CAMERA_HFOV_DEF", 65.0)
MEMORY_SECONDS = _env("MEMORY_SECONDS", 120)
APPEAR_FRAMES = _env("APPEAR_FRAMES", 3)
GONE_SECONDS = _env("GONE_SECONDS", 2.0)
ALERT_TTL = _env("ALERT_TTL", 8.0)
LOW_BATTERY = _env("LOW_BATTERY", 20)
LOG_DIR = _env("LOG_DIR", "logs")
LOG_LEVEL = _env("LOG_LEVEL", "INFO")
MIC_DEVICE = _env("MIC_DEVICE", -1)
AUTO_CALIBRATE = _env("AUTO_CALIBRATE", 1)
WAKE_BEEP = _env("WAKE_BEEP", 1)
FOLLOWUP_SECS = _env("FOLLOWUP_SECS", 6.0)
YOLO_IMGSZ = _env("YOLO_IMGSZ", 640)
SMOOTHING = _env("SMOOTHING", 0.5)
MIN_BOX_AREA = _env("MIN_BOX_AREA", 400)
IGNORE_LABELS = _env("IGNORE_LABELS", "")
DEDUPE_IOU = _env("DEDUPE_IOU", 0.85)
CAMERA_RECONNECT_S = _env("CMAERA_RECONNECT_S", 2.0)
