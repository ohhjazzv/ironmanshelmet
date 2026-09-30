"""
main.py - starts every module as a thread.

    python main.py                  # fakestate + webcam + HUD (works today)
    python main.py --no-camera
    python main.py --debug          # verbose logs
    python main.py --real           # real perception + assistant (once Krish's parts land)

Modules that aren't built yet raise NotImplementedError; main logs it and keeps going.
"""
import argparse
import logging
import threading

import config
from core import state, fakestate
from core.log import get_logger, setup as setup_logging
from hud import hud

log = get_logger("main")


def start_thread(name, target, *args):
    def wrapper():
        try:
            target(*args)
        except NotImplementedError:
            log.warning("%s not built yet - skipping", name)
        except Exception:
            log.exception("%s crashed", name)
    t = threading.Thread(target=wrapper, name=name, daemon=True)
    t.start()
    return t


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--real", action="store_true", help="use perception + assistant instead of fakestate")
    p.add_argument("--no-camera", action="store_true")
    p.add_argument("--scenario", default="default")
    p.add_argument("--debug", action="store_true", help="verbose logging")
    args = p.parse_args()
    setup_logging(logging.DEBUG if args.debug else logging.INFO)
    log.info("starting: camera=%s real=%s scenario=%s",
             "off" if args.no_camera else config.CAMERA_SOURCE, args.real, args.scenario)

    stop = threading.Event()
    cam = None if args.no_camera else hud.Camera(config.CAMERA_SOURCE)

    if args.real:
        from perception import perception
        from assistant import assistant
        state.update("connected", True)   # no helmet yet: the laptop is the helmet
        start_thread("perception", perception.run, stop, cam.latest if cam else (lambda: None))
        start_thread("assistant", assistant.run, stop)
    else:
        fakestate.start(args.scenario)

    try:
        hud.run(stop, cam)                # HUD owns the main thread (OpenCV windows need it)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if cam:
            cam.stop()


if __name__ == "__main__":
    main()

        





