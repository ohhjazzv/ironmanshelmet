import time
from collections import Counter

SYSTEM = (
    "You are JARVIS, the AI inside an Iron Man Style Helmet"
    "reply in 1-2 short spoken sentences. NO markdown, no list, no emojis"
    "you do not see anything urself: the SCENE below is everything you know abt"
    "what the wearer is lookin at If smthing inst in it say u dont see it"
    "Never invent objects or txt"
)



def _where(box, frame_size):
    fw, fh = frame_size or [640, 480]
    x, y, w, h = box
    cx, cy = (x + w / 2) / fw, (y + h / 2) / fh
    horiz = "left" if cx < 0.33 else "right" if cx > 0.66 else "center"
    vert = "top" if cy < 0.33 else "bottom" if cy > 0.66 else "middle"
    return horiz if vert == "middle" else f"{vert} {horiz}"


def describe_scene(state):
    now = time.time()
    ts = state.get("perception_ts", 0.0)
    if not ts or now -ts > 3:
        return "VISION is offline or stale, so you cant tell what is in view rn"

    dets = state.get("detections", [])
    if not dets:
        parts = ["Nth recognishle is int view"]
    else:
        counts = Counter(d["label"] for d in dets)
        summary = ",".join(f"{n}{lbl}" + ("s" if n > 1 else "") for lbl, n in counts.items())
        parts = [f"In View: {summary}"]
        fs = state.get("frame_size")

        for d in sorted(dets, key=lambda d: -d["box"][2] * d["box"][3])[:8]:
            parts.append(f"A {d['label']} at the {_where(d['box'], fs)} ({int(d['conf'] * 100)}% sure)")

    text = state.get("text_seen", [])

    if text:
        parts.append("text Visible: "+";".join(f'"{t}"' for t in text) + ".")
        return "".join(parts)
    


def describe_status(state):
    bits = [f"Mode: {state.get('mode')}.", f"Faceplate: {state.get('faceplate')}."]

    if state.get("battery") is not None:
        bits.append(f"Battery: {state['battery']}%")
    if state.get("alerts"):
        bits.append("Alerts: "+";".join(map(str, state["alerts"]))+ ".")
    return "".join(bits)


def build_messages(state, question, history = None):
    ctx = f"SCENE: {describe_scene(state)}\nSTATUS: {describe_status(state)}"
    msgs = [{"role": "system", "content": SYSTEM + "\n\n" + ctx}]
    msgs += history or []
    msgs.append({"role": "user", "content": question})
    return msgs