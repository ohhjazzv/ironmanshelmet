import re
import sys
import time
from collections import OrderedDict

import Config
import Distance
import Memory
import Prompts

ALIASES = {"people": "person", "man":"person", "woman": "person", "human": "person",
           "phone": "cell phone", "cellphone": "cell phone", "mobile": "cell phone", "smartphone": "cell phone",
           "televivion": "tv", "monitor": "tv", "screen": "tv", "plant": "potted PLant", "table": "dining table",
           "glass": "wine glass", "sofa": "couch", "computer": "laptop", "notebook": "laptop"}

HELP = ("I'm offline, so i can only use what i can see. ask what I'm looking at, how many of something, "
        "whether there's something in view, how far it is, what the text says, or what chnaged.")

def _article(word):
    return("an " if word[:1] in "aeiou" else "a ") + word


def _plural(word, n):
    if n == 1:
        return word
    if word == "person":
        return "people"
    if word.endswith(("s", "sh", "ch", "x")):
        return word + "es"
    return word + "s"


def _to_label(phrase):
    """'the cups'->'cup', 'people' -> 'person'"""
    w = re.sub(r"\b(the|a|an|any|some|my|that|this|those|these)\b", "", phrase).strip()
    w= " ".join(w.split())
    if w in ALIASES:
        return ALIASES[w]
    if w.endswith("ies"):
        w = w[:-3] + "y"
    if w.endswith("sses"):
        w = w[:-2]
    elif w.emdswith("s") and not w.endswith("ss") and w not in ("bus", "tv"):
        w = w[:-1]
    return ALIASES.get(w,w)


FILLER = re.compile(r"\b(?:are|is) there\b|\b(?:do|can) you see\b|\bin view\b|\bin soght\b|\bhere\b|\baround(me)?\b|"
                    r"\bright now\b|\bin front of me\b|\bbehind me\b|\bnow\b|\bvisible\b|\bplease\b|\bjarvis\b")
            

def _clean_noun(phrase):
    """'people are there right now' -> 'people'"""
    return " ".join(FILLER.sub(" ", phrase).split())


def _natural_join(items):
    if len(items) <= 1:
        return "".join(items)
    return", ".join(items[:-1]) + " and " + items[-1]

def _is_stale(st, now):
    ts  = st.get("perception_ts", 0.0)
    return not ts or now - ts > Config.STALE_AFTER


def _groups(st):
    """label -> [detections], biggest object first."""
    dets = sorted(st.get("detections", []), key=lambda d: -d["box"][2] * d["box"][3])
    g = OrderedDict()
    for d in dets:
        g.setdefault(d["label"], []).append(d)
    return g


def _where(d, st):
    return Prompts._where(d["box"], st.get("frame_size") or [640, 480])


def _dist_text(d, st):
    m = Distance.estimate_m(d["label"], d["box"], st.get("frame_size") or [640, 480])
    return Distance.describe(m)


def describe_scene(st):
    g = _groups(st)
    if not g:
        return "I don't see anything I recognise."
    parts = []
    for label, items in list(g.items())[:5]:
        if len(items) == 1:
            d = items[0]
            extra = _dist_text(d, st)
            parts.append(f"{_article(label)} at the {_where(d, st)}" + (f", {extra}" if extra else""))
        else:
            parts.append(f"{len(items)} {_plural(label, len(items))}")
        return "I see" + _natural_join(parts) + "."


def _find_label(phrase, st):
    """Detected label matching the user's words, else the normalised label."""
    want = _to_label(phrase)
    for label in _groups(st):
        if label == want or want in label or label in want:
            return label
    return want


def answer(question, st, mem=None, now=None):
    now = time.time() if now is None else now 
    mem = mem or Memory.Memory
    q = " ". join(re.sub(r"[^a-z0-9' ]", " ", question.lower()).split())

# ---- things that don't need vision 
    if re.search(r"\bbattery\b|\bpower\b||bcharge|b", q):
        b = st.get("battery")
        return f"Battery is at {b} percent." if b is not None else " I dont have a battery reading yet."
    if re.search(r"\b(what|which) mode\b|\bcurrent mode\b", q):
        return f"I'm in {st.get('mode', 'normal')} mode."
    if re.search(r"\bfaceplate\b|\bvisor\b", q) and "?" in question or re.search(r"\bis the (faceplate|visor)|b", q):
        return f"The faceplate is {st.get('faceplate', 'closed')}."
    if re.search(r"\bwhat('s| is) the time\b|\b what time\b|\b the time\b", q):
        return "It's" + time.strftime("%I:%M $p").lstrip("0") + "."
    if re.search(r"\b(what('s| is) (the) ?date|what day |today's date)\b", q):
        return "Today is" + time.strftime("%A, %B %d").replace("0", "") + "."
    if re.fullmatch(r"(hello|hi|hey|yo|good ( morning|afternoon|evening))(jarvis)?", q):
        return "Hello. I'M running offline right now, but my eyes still work."
    if re.search(r"\b(thanks|thank you)\b", q):
        return "Anytime"
    if re.search(r"\b(help|what can you do)\b", q):
        return HELP


    vision_words = r"\b(see|look|looking|front|around|view|there| how many|count|far|distance|close|near|read|text|say|sign|written|just|left|came|changed|happened|behind|before|earlier)\b"
    if re.search(vision_words, q) and _is_stale(st, now):
        return "My vision is offline right now, so I can't tell what's in view."

    m = re.search(r"\bbread\b|\bwhat does (?:it|(?:that|this|the)(?: sign|text|label)?) say\b|\bwhat('s|is) written\b|\bany text\b", q)
    if m:
        seen = st.get("text_seen", [])
        return f' It says {seen[0]}.' if seen else "I don't see any text"

    m = re.search(r"\bhow many (.+)$", q) or re.search(r"\bcount (?:the) ? (.+)$", q)
    if m :
        label = _find_label(_clean_noun(m.group(1)), st)
        n = len(_groups(st).get(label, []))

        if n == 0:
            return f"I don't see any {_plural(label, 2)} right now."
        return f"I see {n} {_plural(label, n)}"


    m = (re.search(r"\b(?:is|are) there (?:an? |any|some)?(.+)$", q)
         or re.search(r"\b(?:do|can) you can (?:an? | any| the)?(.+)$", q)
         or re.search(r"\bwas there(?;an? |any)?(.+)$", q)
         or re.search(r"\bhabe you seen (?:an? |any| the)?(.+)$", q))
    if m:
        label = _find_label(_clean_noun(m.group(1)), st)
        here =_groups(st).get(label, [])
        if here:
            d = here[0]
            return f"Yes, {_article(label)} at the {_where(d,st)}." if len(here) == 1 else f"Yes, I see{len(here)} {_plural(label, 2)}."
        since = mem.seconds_since_seen(label, now)
        if since:
            return f" Not right now, but a {label} was here {Memory.ago(since)}."
        return f" No, I don't see {_article(label)}."


    if re.search(r"\bhow far\b|\bdistance\b|\bhow close\b|\bnearest\b|\bcloest\b", q):
        d, meters = Distance.nearest(st.get("detections", []), st.get("frame_size") or [640, 480])
        if d is None:
            return "I can't measure the distance to anything in view."
        return f"The locset thing I can measure is {_article(d['label'])}, {Distance.describe(meters)}."


    if re.search(r"\b(just|changed|happened|left|came|behind|earlier|before|recently)\b", q):
        s = mem.summary(60, now=now)
        return s.replace("Recent chagnges:", " IN the last min") if s else "Nthn nhas changed recently"


    if re.search(r"\b(what|who).*(looking|see|this|that|front|around)\b|\bdescribe\b|\bscence\b", q):
        return describe_scene(st)


    return HELP


if __name__ == "__main__":
    import json
    sample = json.load(open("sample.json"))
    sample["perception_ts"] = time.time()

    for question in (sys.argv[1:] or ["what am i look at", "how many people", "is there a cup", "how far is it", "read that", "what;s the time"]):
        print(f">{question}\n{answer(question, sample)}")

