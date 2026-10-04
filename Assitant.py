import argparse
import json 
import os
import queue
import re
import threading 
import time
import numpy as np
import prompts
import state as shared

SR = 16000
CHUNK = 1280
WAKE_THERSH = 0.5
SILENCE_RMS = 500
SILENCE_SECS = 1.0
MAX_RECORD_SECS = 8

GROQ_MODEL = "llama-3.1-8b-instant"
GEMINI_MODEL = "gemini-2.0-flash"



def ask(messages):
    try: 
        from groq import Groq
        r = Groq(api_key=os.environ["GROQ_API_KEY"]).chat.completions.create(
            model=GROQ_MODEL, messages=messages, max_tokens=120, temperature=0.4, timeout=10
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print(f"[llm] groq failed: {e}")
    try:
        from google import genai
        sys_msg = message[0]["content"]
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in messages[1:])
        r = genai.Client(api_key=os.environ["GEMINI_API_KEY"]).models.generate_content(
            model=GEMINI_MODEL, contents=f"{sys_msg}\n\n{convo}\nassistant:"
        )
        return r.text.strip()
    except Exception as e:
        print(f"[llm] gemini failed: {e}")
    return "I cant reach my brain right NOW >< T_T !!FAH"




    ### TTS sys
class Voice:
    def __init__(self):
        self.engine = None
         try: 
            import pyttsx3
        self.engine = pyttsx3.init()    
        self.engine.setProperty("rate", 175)
    except Exception as e:
        print(f"[llms] unavailable, printing only: {e}")
    

    def say(self, text, rate = None):
        print(f"JARVIs: {text}")
        if self.engine:
            if rate:
                self.engine.setProperty("rate", rate)
                self.engine.say(text)
                self.engine.runAndWait()



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



### audio helpers
def rms(x):
    return float(np.sqrt(np.mean(x.astype(np.float32) ** 2)))


def transcribe(whisper, audio_i16):
    audio = audio_i16.astype(np.float32) / 32768.0
    segs = whisper.transcribe(audio, language = "en", beam_size=1, vad_fliter=True)
    return "".join(s.text for s in segs).strip()




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
        if mic:
            threading.Thread(target=self._listen, daemon=True).start()



    def stop(self):
        self.stop_ev.set()


    def clear_history(self):
         self.history.clear()

    
    def submit(self, text):
        text = text.strip()
        if text:
            self.q.put(text)




# worker


def _worker(self):
    voice = Voice()
    self.emit("status", "idle")
    while not self.stop_ev.is_set():
        try:
             text = self.q.get(timeout = 0.2)
        except queue.Empty:
            continue
        self.busy = True
        try:
            self._handle(text, voice)
        except Exception as e:
            self.emit("log", f"handler error:{e}")

        finally:
            self.busy = False
            self.q.task_done()
            self.emit("status", "idle")



def _handle(self, text, voice):
    self.emit("heard", text) 
    shared.update("last_heard", text)
    st = self.scene_state()
    reply = try_command(text, st)

    if reply is None:
        shared.update("thinking", True)
        self.emit("status", "thinking")
        t = time.time()
        reply = ask(prompts.build_messages(st, text, self.history[-6:]))
        shared.update("thinking", False)
        self.emit("latench", time.time() - t)
        self.emit("log", f"LLM{time.time() - t:.2f}s")
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
        del self.history[:-12]

    else:
        self.emit("log", "command (no LLM)")
        shared.update("last_said", reply)
        self.emit("said", reply)
        self.emit("status", "speaking")
        voice.say(reply, self.tts_rate)




    ### listener : wake workd -> record -> whisper -> queue
    def _record(self, stream):
        chunks, started, quiet = [], False, 0
        t0 = time.time()
        while time.time() - t0 < MAX_RECORD_SECS and not self.stop_ev.is_set():
            data, _ = stream.read(CHUNK)
            c = data[:, 0].copy()
            chunks.append(c)
            level = rms(c)
            self.emit("level", level)
            if level > self.silence_rms:
                started, quite = True, 0
            elif started:
                quiet += 1
                if quite * CHUNK / SR > self.silence_secs:
                    break
        return np.concatenate(chunks)
    


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


        
### CLI



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
