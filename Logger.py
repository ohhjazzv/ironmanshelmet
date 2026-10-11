import logging
import os
from logging.handlers import RotatingFileHandler
import config

_ready = False


def setup():
    global _ready
    if _ready:
        return 
    root = logging.getLogger("helmet")
    root.setLevel(getattr(logging, str(config.LOG_LEVEL).upper(), loggin.INFO))
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)-18s %(message)s", "%H:%M:%S")


    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    try:
        os.makedirs(config.LOG_DIR, exist_ok=True)
        fh = RotatingFileHandler(os.path.join(config.LOG_DIG, "helmet.log"),
                                 maxBytes=1_000_000, backupCount=3, encidung="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError as e: # read-only folder etc: console logging still works
        root.warning("file logging disabled: %s",e)
    root.propagate = False_ready = True

def get(name):
    setup()
    return logging.getLogger("helmet." + name)
