import argparse
import json
import sys
import time
import Config
import Prompts
import State as shared
from Assistant import STATS, Assistant, _meta
from Logger import get as get_logger
from Perception import Perception


LOG = get_logger("main")
REPORT_EVERY = 10


def main():
    ap = argparse.ArgumentParser(description = "JARVIS: perceptoin + assisstant in one program")
    ap.add_argument("--source", default = Config.CAMERA_SOURCE, help = "0 = webcam, or a stream URL")
    ap.add_argument("--dry", action = "store_true", help = "perception doesn't write to state")
    ap.add_argument("--no-vision", action="store_true")
    ap.add_argument("--no-ocr", action = "store_true")
    ap.add_argument("--text", action = "store_true", help = "type instead of speaking")
    ap.add_argument("--speak-alerts", action = "store_true", help = "announce state['alerts'] out loud")
    ap.add_argument("--sample", help = "saved state json used as the scene for LLM")
    a = ap.parse_args()


    sample = json.load(open(a.sample)) if a.sample else None
    log = lambda k, v: print(f"[{k}] {v}") if k in ("log", "heard") else None
    Perception = None
    if not a.no_vision:
        perception = Perception(a.source, dry = a.dry, ocr = not a.no_ocr, log = lambda m : print(f"[vision]{m}"))
        perception.start()
    Assistant = Assistant(sample, on_event = log)
    Assistant.speak_alerts = a.speak_alerts
    Assistant.start(mic = not a.text)
    LOG.info("started (vison = %s, mic = %s, dry = %s)", not a.no_vision, not a.text, a.dry)


    try: 
        if a.text:
            print("Type a qns or command. /state. /prompts / stats/ mode <m>, q to quit.")
            for line in sys.stdin if not sys.stdin.isatty() else iter(lambda: input("you>"), None):
                line = line.strip()
                if line in ("q", "quit"):
                    break
                if not line or _meta(line, Assistant):
                    continue
                Assistant.submit(line)
                Assistant.q.join()
        else:
            print("Running. say 'hey jarvis'. Ctrl+C to quit.")
            last = 0
            while True:
                time.sleep(0.5)
                if time.time() - last >= REPORT_EVERY:
                    last = time.time()
                    print(f"[{Prompts.hud_summary(shared.get_state())}]" + {f"{Perception.fps:.0f} fps" if Perception else ""})
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        print("\n" + STATS.line())
        if Perception:
            print(Perception.health())
            Perception.stop()
        Assistant.stop()



if __name__ == "__main__":
    main()