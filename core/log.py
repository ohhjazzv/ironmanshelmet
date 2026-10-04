"""
log.py - one logging setup for every module.

    from core.log import get_logger
    log = get_logger("hud")
    log.info("started")

Every module gets a named logger, so you can filter output by name.
"""
import logging
import sys

_FORMAT = "%(asctime)s.%(msecs)03d %(name)-10s %(levelname)-5s %(message)s"
_configured = False


def setup(level=logging.INFO):
    """Call once, from main.py or a module's __main__."""
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