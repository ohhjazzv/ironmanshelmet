import logging
import sys

_FORMAT = "%(asctime)s.%(msecs)03d %(name)-10s %(levelname)-5s %(message)s"
_configured = False


def setup(level=logging.INFO):
    """Call once, from main.py."""
    global _configured
    if _configured:
        logging.getLogger().setLevel(level)
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%H:%M:%S"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level)
    _configured = True


def get_logger(name):
    return logging.getLogger(name)

