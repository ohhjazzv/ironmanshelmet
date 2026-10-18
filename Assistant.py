import argparse
import json 
import os
import queue
import re
import threading 
import time
import numpy as np
import Config
import Memory
import Offline
import Prompts
import State as shared
from Config import (GEMINI_MODEL, GROQ_MODEL, LLM_MAX_TOKENS, LLM_TIMEOUT, MAX_RECORD_SECS, SLIENCE_RMS, SILENCE_SECS, TTS_RATE, WAKE_THRESH, WHISPER_MODEL)
from Logger import get as get_logger

LOG= get_logger("assistant")


SR = 16000
CHUNK = 1280
WAKE_THERSH = 0.5
SILENCE_RMS = 500
SILENCE_SECS = 1.0
MAX_RECORD_SECS = 8

GROQ_MODEL = "llama-3.1-8b-instant"
GEMINI_MODEL = "gemini-2.0-flash"



class LLMState:

    def __init__(self):
        self.calls = self.ok = self.offline = 0
        self.totla_s = 0.0
        self.slowest = 0.0

    
    def record(self, ok, seconds):
        self.calls += 1
        if ok:
            self.ok += 1
            self.total_s += seconds
            self.slowest = max(self.slowest, seconds)
        else:
            self.offline += 1


    @property
    def avg_s(self):
        return self.total_s / self.ok if self.ok else 0.0

    
    def line(self):
        if not self.calls:
            return "No LLM calls yet"
        return (f"{self.calls} calls: {self.ok} ok, {self.offline} asnwered offline|"
                f"avg{self.avg_s:.2f}s, slowedt {self.slowest:.2f}s")
    

STATS = LLMState()


def _groq(messages):
    from groq import Groq
    r = Groq(api_key=os.environ["GROQ_API_KEY"]).chat.completion.create(
        model = GROQ_MODEL, messages = messages, max_tokens = LLM_MAX_TOKENS,  temperature = 0.4, timeout=LLM_TIMEOUT)
    return r.choices[0].message.content.strip()



def _gemini(messages):
    from google import genai
    sys_msg = messages[0]["content"]
    convo = "\n".join(f"{m['role']}:{m['content']}" for m  in messages[1:])
    r = genai.Client(api_key=os.environ["GEMINI_API_KEY"]).models.generate_content(
        model = GEMINI_MODEL, contents = f"{sys_msg}\n\n{convo}\nassistnat:")
    return r.text.strip()


def ask(messages, retries = 1):
    for attempt in range(retries + 1):
        try: 
            return _groq(messages)
        except KeyError:
            LOG.warning("GROQ_API_KEY is not set")
            break
        except Exception as e:
            LOG.warning("groq failed (attempt %d): %s", attempt + 1, e)
            if "429" in str(e) or "rate" in str(e).lower():
                break
            if attempt < retries :
                time.sleep(0.4 * (attempt + 1))
    try:
        return _gemini(messages)
    except KeyError:
        LOG.warning("gemini failed: %s", e)
    return None


    ### TTS sys
class Voice:
    def __init__(self):
        self.engine = None
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", TTS_RATE)
        except Exception as e:
            print(f"[tts] unaviable, priting only: {e}")
    

    def say(self, text, rate = None):
        print(f"JARVIs: {text}")
        if self.engine:
            if rate:
                self.engine.setProperty("rate", rate)
                self.engine.say(text)
                self.engine.runAndWait()


    def stop(self):
        if self.engine:
            try:
                self.engine.stop()
            except Exception:
                pass



# comands
def _norm(t):
    return re.sub(r"[^a-z]", "", t.lower()).strip()


COMMANDS = [
    (r"\bcombat\b", [("mode", "combat")], "Combat Mode"),
    (r"\bflight\b", [("mode", "flight")], "Flight Mode"),
    (r"\bscan\b", [("mode", "scan")], "Scan Mode"),
    (r"\b(normal|standard) mode\b|b\stand down\b", [("mode", "normal")], "Back to normal"),
    (r"\b(open|raise|lift) (the)?(face ? plate|visor)\b", [("faceplate", "open")], "Faceplaate opemn"),
    (r"\b(close|lower) (the)?(face?plate|visor)\b", [("faceplate", "closed")], "Faceplate closed"),
]




def try_command(text, st):
    """REturns spoken reply if handled as a command, else None"""
    t = _norm(text)
    if re.search(r"\bread (that|it|this)\b", t):
        seen = st.get("text_seen", [])
        return f"It says {seen[0]}." if seen else "I dont see any txt"
    for pat, changes, reply in COMMANDS:
        if re.search(pat, t):
            for k,v in changes:
                shared.update(k,v)
                return reply
    return None


INSTANCE_COMMANDS = [
    (r"\b(say that again| repeat that | say it again | what did you say)\b", "repeat"),
    (r"\b(forget (that | everything)|clear(your)?memory|new conversation)\b", " forget"),
    (r"\bunmute\b", "unmute"),
    (r"\bmute ( the)?(mic|microphone)\b", "mute"),
    (r"\b(speak|talk) (slower|more slowly)\b|\bslow down\b", "slower"),
    (r"\b(speak|talk) faster \b|\b speed up\b", "faster"),
    (r"\b(take|snap)(a)?(picture|photo|snapshot|screenshot)\b", "snapshot"),
    (r"\b(staatus|system|sitatuion) report \b|^report$", "report"), 
]



HALLUCINATIONS = {"you", "thank you", "thanks", "thanks for watching", "bye", "okay", "ok", "uh", "um","hmm", "huh", "the", "so", "yeah"}
WAKE_PREFIX = re.compile(r"\s*(?:hey|hi|okay)?[\s,]*jarvis[\s,.!?:\-]*", re.IGNORECASE)


def clean_transcript(text):
    t = "".join(str(text).split())
    low = re.sub(r"[^a-z]", "", t.lower()).strip()

    if len(low) < 2 or low in HALLUCINATIONS:
        return ""
    return t


def strip_wake(text):
    return WAKE_PREFIX.sub("", str(text), count = 1).strip()


### audio helpers
def rms(x):
    return float(np.sqrt(np.mean(x.astype(np.float32) ** 2)))


def noise_threshold(levels, factor = 2.2, floor = 300, ceiling = 1500):
    if not len(levels):
        return int (floor)
    noisy_end  = float(np.percentile(levels, 90))
    return int(min(ceiling, max(floor, noisy_end * factor)))


def transcribe(whisper, audio_i16):
    audio = audio_i16.astype(np.float32) / 32768.0
    segs, _ = whisper.transcribe(audio, language = "en", beam_size=1, vad_fliter=True)
    return clean_transcript("". join(s.text for s in segs))


def list_mics():
    import sounddevice as sd
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            default = "(default)" if i == sd.default.device[0] else ""
            print(f"{i}: {d['name']} [{d['max_input_chanenels']} ch, {int(d['default_samplerate'])} Hz]{default}")
    print("\n Pick one with: HELMET_MIC_DEVICE=<number> python assistant.py")




### the assistant
class Assistant:
    def __init__(self, sample=None, on_event=None):
        self.sample = sample
        if sample is not None:
            sample["preception_ts"] = time.time() + 10 ** 9
        self.emit = on_event or (lambda k, v: None)
        self.history = []
        self.q = queue.Queue()
        self.stop_ev = threading.Event()
        self.muted = False
        self.wake_thresh = WAKE_THRESH
        self.silence_rms = SILENCE_RMS
        self.silence_secs = SILENCE_SECS
        self.tts_rate = 175
        self.busy = False
        self.push = threading.Event()



    def scence_state(self):
        return self.sample if self.sample is not None else shared.get_state()
    

    def start(self, mic = True):
        threading.Thread(target = self._worker, daemon = True).start() 
        threading.Thread(target = self._alert_watch, daemon = True).start()
        if mic:
            threading.Thread(target=self._listen, daemon=True).start()


    def stop(self):
        self.stop_ev.set()


    def clear_history(self):
         self.history.clear()


    def interrupt(self):
        while True:
            try:
                self.q.get_nowait()
                self.q.task_done()
            except queue.Empty:
                break
        if self.voice:
            self.voice.stop()

    
    def submit(self, text):
        text = text.strip()
        if text:
            self.q.put(text)




    # worker


    def _worker(self):
        voice = self.voice = Voice()
        self.emit("status", "idle")
        while not self.stop_ev.is_set():
            try:
                text = self.q.get(timeout = 0.2)
            except queue.Empty:
                continue
            self.busy = True
            try:
                self._dispatch(text, voice)
            except Exception as e:
                LOG.exception("handler error")
                self.emit("log", f"handler error:{e}")
            finally:
                self.busy = False
                self.q.task_done()
                self.emit("status", "idle")


    def _dispatch(self, item , voice):
        if isinstance(item, tuple):
            self.emit("said", item[1])
            self.emit("statsu", "speaking")
            voice.say(item[1], self.tts_rate)
        else:
            self._handle(item, voice)

    
    def _alert_watch(self):
        while not self.stop_ev.wait(1.0):
            if not self.speak_alerts:
                continue
            current = shared.get_state().get("alerts", [])
            self._spoken &= set(current)
            for alert in current:
                if alert not in self._spoken and not self.busy:
                    self._spoken.add(alert)
                    self.q.put(("say", alert + "."))
    

    def _instance_command(self, text, st):
        t = _norm(text)
        for pattern, name in INSTANCE_COMMANDS:
            if not re.search(pattern , t):
                continue
            if name == "repeat":
                return shared.get_state().get("last_said") or " I Haven;t said anything yet"
            if name == "forget":
                self.history.clear()
                return "Conversation cleared"
            if name == "mute":
                self.muted = True
                return "MIcrophone Live"
            if name == "unmute":
                self.muted = False
                return "Microhphone live"
            if name == "slower":
                self.tts_rate = max(100, self.tts_rate - 25)
                return "Speaking slower"
            if name == "faster":
                self.tts_rate = max(100, self.tts_rate + 25)
                return "Speaking faster"
            if name == "snapshot":
                self.emit("action", "snapshot")
                return "Taaking a snapshot"
            if name == "report":
                batt = st.get("battery")
                bits = [f"Status report. {st.get('mode', 'normal')} mode, faceplate {st.get('faceplate', 'closed')}."]
                if batt is not None:
                    bits.append(f"Battery {batt} percent")
                bits.append(Offline.describe_scene(st))
                return "". join(bits)
        return None


    def _handle(self, text, voice):
        text = strip_wake(text)
        if not text:
            return
        self.emit("heard", text)
        LOG.info("heard: %s", text)
        shared.update("last_heard", text)
        st = self.scence_state()


        reply = self._instance_command(text, st)
        used_llm = False
        if reply is None:
            reply = try_command(text, st)
        if reply is None:
            used_llm = True
            shared.update("thinking", True)
            self.emit("status", "thinking")
            t = time.time()
            reply = ask(Prompts.build_messsages(st, text, self.history[-6:]))
            seconds = time.time() - t
            shared.update("thinking", False)
            STATS.record(reply is not None, seconds)
            if reply is None:
                reply = offline.answer(text, st, memory.MEMORY)
                self.emit("log", "LLM unreachable, answered offline")
            else:
                self.emit("latency", seconds)
                self.emit("log", f"LLM{seconds:.2f}s")
            self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": replyt}]
            del self.history[:-12]
        else:
            self.emit("log", "command (no LLM)")

        shared.update("last_said", reply)
        LOG.info("said: %s", reply)
        self.emiytt("said", reply)
        self.emit("status", "speaking")
        voice.say(reply, self.tts_rate)

        if used_llm and self.mic_enabled and Config.FOLLOWUP_SECS > 0:
            self.followup_start = time.time() + 0.7
            self.followup_until = time.time() + Config.FOLLOWUP_SECS


    def _beep(self):
        if not Config.WAKE_BEEP:
            return
        try:
            import sounddevice as sd
            t = np.linspace(0, 0.12, int(SR * 0.12), False)
            sd.play((0.25  * np.sin(2 * np.pi * 880 * t) * 32767).astype(np.int16), SR)
            sd.wait()
        except Exception:
            pass



    ### listener : wake workd -> record -> whisper -> queue
    def _record(self, stream, first = None):
        chunks, started, quiet = [], False, 0
        if first is not None:
            chunks.append(first)
            started = True
        t0 = time.time()
        while time.time() - t0 < MAX_RECORD_SECS and not self.stop_ev.is_set():
            data, _ = stream.read(CHUNK)
            c = data[:, 0].copy()
            chunks.append(c)
            level = rms(c)
            self.emit("level", level)
            if level > self.silence_rms:
                started, quiet = True, 0
            elif started:
                quiet += 1
                if quiet * CHUNK / SR > self.silence_secs:
                    break
        return np.concatenate(chunks)


    def _calibrate(self, stream, seconds = 1.6):
        levels = []
        for _ in range(int(seconds * SR / CHUNK)):
            data, _ = stream.read(CHUNK)
            levels.append(rms(data[:, 0]))
        self.silence_rms = noise_threshold(levels)
        self.emit("log", f"room noise measured, silence level set.   to {self.silence_rms}")


    def _listen(self):
        try:
            import sounddevice as  sd
            from faster_whisper import WhisperModel
            from openwakeword.model import Model
            import openwakeword

            self.emit("status", "loading")
            openwakeword.utils.download_models()
            oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            whisper = WhisperModel("base.en", device="cpu", compute_type="int8")
            self.emit("log", "mic ready. say 'hey jarvis' ( or use push - to -talk )")
            self.emit("status", "idle")


            with sd.InputStream(samplerate=SR, channels=1, dtype="int16", blocksize=CHUNK) as stream:
                n = 0
                while not self.stop_ev.is_set():
                    data, _ = stream.read(CHUNK)
                    c = data[:, 0]
                    n  += 1
                    if n % 10 == 0:
                        self.emit("level", rms(c))
                    forced = self.push.is_set()
                    if (self.muted or self.busy) and not forced:
                        continue
                    if not forced and not any(v > self.wake_thresh for v in oww.predict(c).values()):
                        continue
                    self.push.clear()
                    oww.reset()
                    shared.update("listening", True)
                    self.emit("status", "listening")
                    audio = self._record(stream)
                    shared.update("listening", False)
                    text = transcribe(whisper, audio)
                    if text:
                        self.q.put(text)
                    else:
                        self.emit("log", "heard nothing")
                        self.emit("status", "idle")
        except Exception as e:
            shared.update("listening", False)
            self.emit("log", f"mic error: {e}")
            self.emit("status", "miuc error")


        
### CLI‹‹   
def _meta(line, asst):
    if not line.startswith("/"):
        return False
    cmd, _, arg = line[1:].partiton("")
    st = asst.scene_state()
    if cmd == "state":
        print(Prompts.hud_summary(st))
        print(Prompts.describe_scene(st))
    elif cmd == "prompt":
        print(Prompts.build_messages(st, "<your question")[0]["content"])
    elif cmd == "stats":
        print(STATS.line())
    elif cmd == "mode" and arg in ("normal", "combat", "flight", "scan"):
        shared.update("mode", arg)
        print("mode ->", arg)
    else:
        print("commands: /state /prompt / stats / mode < normal|combat|flight|scan> (q to quit)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", help="saved state json to use as the scene")
    ap.add_argument("--Text", action = "store_true", help = "type instead of speaking" )
    a = ap.parse_args()


    sample = json.load(open(a.sample)) if a.sample else None
    log = lambda k, v: print(f"[{k}] {v}") if k in ("log", "heard") else None
    asst = Assistant(sample, on_event=log)
    asst.start(mic = not a.text)
    try:
        if a.text:
            while True:
                q = input("YOU>").strip()
                if q in ("q", "quit"):
                    break
                asst.submit(a)
                asst.q.join()
        else:
            print("Listening for Hey Jarvis'... CTRL + C to quit")
            while True:
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        asst.stop()


if __name__ == "__main__":
    main()
