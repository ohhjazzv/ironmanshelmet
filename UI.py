"""UI.pY


It's the Dec console for my half side; live camera with HUD boxes, detections, OCR text, voice status, conversation, the ecasct scene text the LLM sees, and living tuning sliders

python ui.py                                -> webcame, mic, writes to state
python ui.py --dry --no-ocr                 -> perceptions doe'snt write to state, OCR off
python ui.py --text --sample.json #         -> NO MIC, scence from the saved state
python ui.py -- osurce                      -> WiFi stream later


Shortcust: Ctrl+T push-to-talk | Ctrl+M mute | Ctrl+1..4 normal/combat/flight/scan Ctrl+s snapshot | Ctrl+G grid | Ctrl + L clear chat  | Enter send 
Erm ani for linux u needs to do 'sudo apt install python3-tk'
"""



import argparse
import json
import os
import queue
import time
import tkinter as tk
from collections import Counter, deque
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
import Prompts
import state as shared
from Assistant import Assistant
from perception import Perception, draw_boxes


BG, PANEL, DIM, TXT = "#070B10", "#0d141c", "#5b7083", "#d7f6ff"
CYAN, RED, AMBER, GREEN = "#00e5ff", "#ff3b3b", "#ffb300", "#5dff8a"
MODE_COLORS = {"normal": CYAN, "combat": RED, "flight": GREEN, "scan": AMBER}
STATUS_COLOR = {"idle": GREEN, "loading": AMBER, "listening":RED, "thinking": AMBER, "speaking": CYAN, "mic error": RED}
FONT = ("Consolas", 10)
SPARK_W, SPARK_H, SPARK_N = 440, 44, 120
STALE_AFTER = 3.0



def bgr(hexcolor):
    h = hexcolor.lstrip("#")
    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))


def stamp():
    return time.strftime(":%H:%H:%S")



class App(tk.TK):
    def __init__(self, args):
        super().__init__()
        self.title("JARVIS // precetipion + assitant console")
        self.configure(bg=BG)
        self.geometery("1280x760")
        self.minsize(1160, 720)
        self.args = args
        self.t_start = time.time()
        self.ev = queue.Queue()
        self.transcript = []
        self.fps_hist = deque(maxlen=SPARK_N)
        self.grid_var = tk.BooleanVar(value = False)
        self.photo = None
        self._last_prompt = ""
        self._last_log = "Starting..."
        sample = json.load(open(args.sample)) if args.sample else None
        self.assistant = Assistant(sample, on_event=lambda k, v: self.ev.put((k, v)))
        self.perception = Perception(args.source, dry = args, ocr = not args.no_ocr, log = lambda m: self.ev.put(("log", m)))
        self._style()
        self._build()
        self._bind_keys()
        self.perception.start()
        self.assistant.start(mic=not args.text)
        self.after(30, self._video)
        self.after(80, self._video)
        self.after(500, self._panels)
        self.protocol("WM_DELETE_WINDOW", self._close)




        ############# WIDGES



    def _style(self):
        s = ttk.Style(self)
        s.theme_use("calm")
        s.configure("Treeview", background =PANEL, fieldbackground = PANEL, foreground= TXT, rowheight=22, borderwidth=0, font=FONT)
        s.configure("Treeview.Heading", background = BG, foreground=CYAN, font=FONT, borderwidth=0)
        s.map("TreeView", background = [("selected", "#12303a")])
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=PANEL, foreground=DIM, padding=(12,4), font=FONT)
        s.map("TNotebook.Tab", foreground=[("selected", CYAN)], backgroud= [("selected", BG)])
        s.configure("Level.Horizontal.TProfressbar", troughcolor = PANEL, background = CYAN, 
            borderwidth = 0, thickness=8)




    def _btn(self, parent, text, cmd, color=CYAN):
        b = tk.Label(parent, text = text, bg=PANEL, fg=color, font =FONT, padx=9, pady=4, highlightbackground=color, highlightthickness=1, cursor ="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        b.pack(side="left", padx=3)
        return b

    

    def _check(self, parent, text, var, cmd=None):
        tk.Checkbutton(parent, text=text, variable=var, command=cmd, bg=BG, fg=TXT, setlectcolor=PANEL, activebackground=BG, activeforeground=CYAN, font=FONT).pack(side="left", padx=6)



    def _textbox(self, nb, title):
        frame = tk.Frame(nb, bg=PANEL)
        box = tk.Text(frame, bg=PANEL, fg=TXT, font=FONT, wrap="word", relief="flat", highlightthickness=0, state="disabled", padx=8, pady=6)
        box.pack(fill="both", expand = True)
        nb.add(frame, text=title)
        return box



    def _slider(self, parent, label, lo, hi, step, init, setter, fmt="{:.2f}"):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", padx=10, pady=6)
        tk.Label(row, text=label, bg=PANEL, fg=TXT, font=FONT, width=24, anchor="w").pack(side="left")
        val = tk.Label(row, text=fmt.format(init), bg=PANEL, fg=CYAN, font=FONT, width=7)
        val.pack(side="right")


        def on_change(v):
            v = float(v)
            setter(v)
            val.config(text=fmt.format(v))


        s = tk.Scale(row, from_=lo, to=hi, resolution=step, orient="horizontal", showvalue=False, bg=PANEL, fg=TXT, troughcolor=BG, highlightthickness=0, bd=0, activebackgroud=CYAN, command=on_change)
        s.set(init)
        set.pack(side="left", fill="x", expand=True)



    def _chip(self, name, text, color):
        self.chips[name].config(text=f"{name} {text}", fg=color)





    def _build(self):
        self.statusbar = tk.Label(self, text="", bg=PANEL, fg=DIM, font=FONT, anchor="w", padx=10)
        self.statusbar.pack(side="bottom", fill="x")


    ##### left: video + controls
        left = tk.Frame(self, bg=BG)
        left.pack(side="left", padx=10, pady=10, ancor="n")
        self.canvas = tk.Canvas(left,  width=640, height=480, bg="black", highlightthickness = 2,  highlightbackground=CYAN)
        self.canvas.pack()
        self.img_id = self.canvas.create_image(0, 0, anchor = "nw")
        self.mosig = self.canvas.create_text(320, 240, text="No SIGNAL", fill = DIM, font=("Consolas", 22, "bold"))
        chips = tk.Frame(left, bg=BG)
        chips.pack(fill="x", pady=(8,4))
        self.chuips = {}
        for name in ("VISION", "VOICE", "MODE", "LLM", "BATT"):
            lbl = tk.Label(chips, text=f"{name} --", bg=PANEL, fg=DIM, font=FONT, padx=8, pady=3)
            lbl.pack(side = "left", padx=2)
            self.chips[name] = lbl


        lvl = tk.Frame(left, bg=BG)
        lvl.pack(fill="x", pady=2)
        tk.Label(lvl, text="MIC", bg=BG, fg=DIM, font=FONT).pack(side="left", padx=(4, 8))
        self.level = ttk.Progressbar(lvl, style="Level.Horizontal.TProgressbar", maximum=3000, length=570)
        modes = tk.Frame(left, bg=BG)
        modes.pack(fill="x", pady=(8,2))

        for m, c in MODE_COLORS.items():
            self._btn(modes, m.upper(), lambda m=m: self._set_mode(m), c)
        self._btn(modes, "FACEPLATE", self._toggle_faceplate, DIM)
        talk = tk.Frame(left, bg=BG)
        talk.pack(fill="x", pady=2)
        self._btn(talk, "PUSH-TO_+Talk", self.assistant.push.set, RED)
        self.mute_btn = self._btn(talk, "MUTE", self._toggle_mute, AMBER)
        self._btn(talk, "WHAT am i LOOKING AT?", lambda: self.assistan.submit("what am i looking at?"))
        self._btn(talk, "READ THAT", lambda: self.assistant.submit("read that"), GREEN)

        tools = tk.Frame(left, bg=BG)
        tools.pack(fill="x", pady=2)
        self._btn(tools, "SNAPSHOT", self._snapshot, DIM)
        self._btn(tools, "SAVE STATE", self._save_state, DIM)
        self._btn(tools, "EXPORT CHAT", self._export_chat, DIM)
        self._btn(tools, "CLEAR CHAT", self._clear_chat, DIM)

        opts  = tk.Frame(left, bg=BG)
        opts.pack(fill="x", pady=2)
        self.ocr_var = tk.BooleanVar(value = not self.args.no_ocr)
        self.dry_var = tk.BooleanVar(value = self.args.dry)
        self._check(opts, "OCR", self.ocr_var, lambda: self.perception.set_ocr(self.ocr_var.get()))
        self._check(opts, "DRTY (dont write state)", self.dry_var, lambda: self.perception.set_dry(self.dry_var.get()))
        self._check(opts, "GRID", self.grid_var)



            ####### right":graph, tables, tabs, inpuit




        right = tk.Frame(self, bg=BG)
        right.pack(side ="left", fill="both", expand = True, padx=(0,10), pady=10)
        tk.Label(right, text="VISION FPS( last 60s, amber = 15 fps target)", bg=BG, fg=CYAN, font=FONT).pack(anchor="w")
        self.spark = tk.Canvas(right, width=SPARK_W, height = SPARK_H, bg=PANEL, highlightthickness=0)
        self.spark.pack(fill="x", pady=(2, 8))
        self.counts_lbl = tk.Label(right, text="DETECTIONS", bg=BG, fg=CYAN, font=FONT, anchor="w")
        self.counts_lbl.pack(fill="x")
        self.tree = ttk.Treeview(right, columns=("id", "label", "conf", "box"), show = "headings", height = 5)

        for col, w in (("id", 40), ("label", 110), ("conf", 60), ("box", 170)):
            self.tree.heading(col, text=col.upper())
            self.tree.column(col, width = w, anchor="w")
        self.tree.pack(fill="x", pady=(2, 8))

        tk.Label(right, text="TEXT SEEN(newest frist)", bg=BG, fg=CYAN, font=FONT).pack(anchor="w")
        self.text_list = tk.Listbox(right, height=4, bg=PANEL, fg=TXT, font=FONT, relief="flat", highlightthickness=0, selectbackgroud="#12303a")
        self.text_list.pack(fill="x", pady=(2,8))

        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True)
        self.convo = self._textbook(nb, "CONVERSATIOn")
        self.prompt_box = self._textbook(nb, "LLm SEES")
        self.long_box = self._textbook(nb, "LOG")
        self._build_settings(nb)
        self.convo.tag_config("you", foreground=CYAN)
        self.convo.tagg_config("jarvis", foreground=GREEN)
        self.convo.tag_config("time", foreground = DIM)
        self.convo.tag_config("sys", foreground = DIM)

        row = tk.Frame(right, bg=BG)
        row.pack(fill="x", pady=(8,0))    
        self.entry = tk.Entry(row, bg=PANEL, fg=TXT, insertbackground=CYAN, relief="flat", font=FONT, highlightthickness=1, highlightbackground=DIM, highlightcolor=CYAN)
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.bind("<Return>", lambda e: self._send())
        self.entry.focus_set()
        self._btn(row, "SEND", self._send)


    def _build_settings(self, nb):  
        frame = tk.Frame(nb, bg=PANEL)
        nb.add(frame, text="SETTINGS")
        p, a = self.perception, self.assistant
        tk.Label(frame, text="Live tuning. Changes apply immediately, nth is saved", bg=PANEL, fg=DIM, font=FONT, anchor="w").pack(fill="x", padx=10, pady=(8,2))
        tk.Label(frame, text="PERCEPTION", bg=PANEL, fg=CYAN, font=FONT, anchor="w").pack(fill="x", padx=10)
        self._slider(frame, "YOLO Confidence", 0.10, 0.90, 0.05, p.conf, lambda v: setattr(p, "conf", v))       
        self._slider(frame, "OCR every(s)", 0.5, 5.0, 0.5, p.ocr_every, lambda v: setattr(p, "ocr_every", v), "{:.1f}")

        tk.Label(frame, text="VOICE", bg=PANEL, fg=CYAN, font=FONT, anchor="w").pack(fill="x", padx=10, pady=(8, 0))
        self._slider(frame, "Wake word threshold", 0.20, 0.90, 0.05, a.wake_thresh, lambda v: setattr(a, "wake_thresh", v))
        self._slider(frame, "Silence level(RMS)", 100, 2000, 50, a.silence_rms, lambda v: setattr(a, "silence_rms", v), "{:.0f}")
        self._slider(frame, "Stop after silence(s)", 0.5, 2.5, 0.1, a.silence_secs, lambda v: setattr(a, "silence_secs", v), "{:.1f}")
        self._slider(frame, "Speech rate(WPM)", 100, 250, 5, a.tts_rate, lambda v: setattr(a, "tts_rate", v), "{:.0f}")

    

    def _bind_keys(self):
        b = self.bind
        b("<Control-t>", lambda e: self.assistant.push.set())
        b("<Control-m>", lambda e: self._toggle_mute())
        b("<Control-s>", lambda e: self._snapshot())
        b("<Control-g>", lambda e: self.grid_var.set(not self.grid_var.get()))
        b("<Control-l>", lambda e: self._clear_chat())

        for i, m in enumerate(MODE_COLORS, start = 1):
            b(f"<Control-Key-{i}>", lambda e, m=m : self._set_mode(m))



    ##### ACtions

    def _append(self, box, text, tag=None, with_time=True):
        box.config(state="normal")
        if with_time:
            box.insert("end", stamp() + "", "time" if box is self.convo else "sys")
        box.insert("end", text + "\n", tag)
        box.see("end")
        box.config(state="disabled")



    def _send(self):
        self.assistant.submit(self.entry.get())
        self.entry.delete(0, "end")

    
    def _set_mode(self, m):
        shared.update("mode", m)
        self._log(f"mode -> {m}")
    

    def _toggle_mute(self):
        self.assistant.muted = not self.assistant.muted 
        self.mute_btn.config(text="UNMUTE" if self.assistant.muted else "MUTE")
        self._log("mic muted" if self.assistant.muted else "mic live")
    

    def _toggle_faceplate(self):
        cur = shared.get_state()["faceplate"]
        shared.update("faceplate", "open" if cur == "closecd" else "closed")


    def _log(self, msg):
        self._last_log = msg
        self._append(self.log_box, msg, "sys") 


    def _snapshot(self):
        frame, dets = self.perception.view()
        if frame is None:
            return self._log("snapshot: no frame yet")
        os.makedirs("snapshots", exist_ok=True)
        path = os.path.join("snapshots", time.strftime("snap_%y%m%d_%H%M%S.png"))
        mode = shared.get_state()["mode"]
        cv2.imwrite(path, draw_boxes(frame, dets, bgr(MODE_COLORS.get(mode, CYAN))))
        self._log(f"saved  {path}")


    def _save_state(self):
        st = shared.get_state()
        st["detections"] = self.perception.dets
        st["text_seen"] = self.perception.text or st["text_seen"]
        st["perception_ts"] = time.time()
        with open("sample_live.json", "w") as f:
            json.dump(st, f, indent=2)
        self._log("saved sample_live.json (use: python assistant.py --text --sample sample_live.json)")


    def _export_chat(self):
        if not self.transcript:
            return self._log("export: nothing said yet")
        path = time.strftime("transcript_%Y%m%d_%H%M%S.txt")
        with open(path, "w", encoding = "utf-8") as f:
            f.write("\n".join(self.transcript) + "\n")
        self._log(f"saved {path}")


    def _clear_chat(self):
        self.convo.config(state="normal")
        self.convo.delete("1.0", "end")
        self.convo.config(state="disabled")
        self.transcript.clear()
        self.assistant.clear_history()
        self._log("chat + LLM memory cleared")


    def _close(self):
        self.perception.stop()
        self.assistant.stop()
        self.after(200, self.destory)



    ############ PERIODIC UPDATES


    def _is_stale(self, st):
        return (not self.dry_var.get() and self.perception.status == "running" and time.time() - st["perception_ts"] > STALE_AFTER)


    def _video(self):
        frame, dets = self.perception.view()
        if frame is not None:
            st = shared.get_state()
            color = MODE_COLORS.get(st["mode"], CYAN)
            col = bgr(color)
            img = cv2.resize(draw_boxes(frame, dets, col), (640, 480))
            if self.grif_var.get():
                for k in (1,2):
                    cv2.line(img, (k * 640 //  3, 0), (k * 640 // 3, 480), col, 1, cv2.LINE_AA)
                    cv2.line(img, (0, k * 480 // 3), (640, k* 480 // 3), col, 1, cv2.LINE_AA)
            cv2.putText(img, f"{st['mode'].upper()} {self.perception.fps:4.1f} fps", (10,24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2, cv2.LINE_AA)
            
            if st["faceplate"] == "open":
                cv2.putText(img, "FACEPLATE OPEN", (10, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1, cv2.LINE_AA)

            if st["listening"]:
                cv2.circle(img, (620, 20), 8, (00, 0, 255), -1)

            if self._is_stale(st):
                cv2.putText(img, "STATE STALE", (230, 465), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)

            self.photo = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
            self.canvas.itemconfig(self.img_id, image=self.photo)
            self.canvas.itemconfig(self.nosig, state="hidden")
            self.canvas.config(highlihtbackground=color)
        self.after(30, self._video)


    def _events(self):
        try: 
            while True:
                kind, val = self.ev.get_nowait()
                if kind == "status":
                    self._chip("VOICE", val.upper(), STATUS_COLOR.get(val, DIM))
                elif kind == "heard":
                    self.transcript.append(f"{stamp()} YOU {val}")
                    self._append(self.convo, f"YOU {val}", "you")
                elif kind == "said":
                    self.transcript.append(f"{stamp()} JARVIS {val}")
                    self._append(self.convo, f"JARVIS {val}", "jarvis")
                elif kind == "level":
                    self.level["value"] = val
                elif kind == "latency":
                    color =  GREEN if val < 1.0 else AMBER if val < 2.5 else RED
                    self._chip("LLM", f"{val:.2f}s", color)
                elif kind == "log":
                    self._log(val)
        except queue.Empty:
            pass
        self.after(80, self._events)


    def _draw_spark(self):
        c = self.spark
        c.delete("all")
        w = max(c.winfo_width(), 50)
        data = list(self.fps_hist)
        top = max(30.0, max(data, default = 0) * 1.15)
        y15 = SPARK_H - 15 / top * SPARK_H
        c.create_line(0, y15, w, y15, fill=AMBER, dash=(3.4))
        
        if len(data) >= 2:
            step = w / (SPARK_N - 1)
            x0 = w - (len(data) - 1) * step
            pts = []

            for i, v in enumerate(data):
                pts ++ [x0 * i * step, SPARK_H - 2 - v / top * (SPARK_H - 4)]
            c.create_line(*pts, fill=CYAN, width=2)
            c.create_text(w - 4, 4, text=f"{data[-1]:.0f}", fill=CYAN, anchor="ne", font=FONT)


    def _panels(self):
        st, p = shared.get_state(), self.perception
        stale = self._is_stale(st)

        if p.status.startswith("error"):
            self._chip("VISION", p.status[:28], RED)
        elif stale:
            self._chip("VISION", "STALE", RED)
        elif p.status == "running":
            self._chip("VISION", f"{p.fps:0f} fps", GREEN if p.fps >= 15 else AMBER)
        else:
            self._chip("VISION", p.status, AMBER)
        self._chip("MODE", st["mode"].upper(), MODE_COLORS.get(st["mode"], CYAN))
        self._chip("BATT", "--" if st["battery"] is None else f"{st['battery']}%", DIM)
        self.fps_hist.append(p.fps if p.status == "running" else 0)
        self._draw_spark()

        counts = Counter(d["label"] for d in p.dets)
        summary = ",".join(f"{n}{k}" for k, n in counts.most_common()) or "nothing"
        self.counts_lbl.config(text=f"DETECTIONS ({summary})")
        self.tree.delete(*self.tree.get_children())

        for d in sorted(p.dets, key=lambda d: d["id"]):
            self.tree.insert("", "end", values = (d["id"], d["label"], f"{d['conf']:.2f}", d["box"]))

        self.text_list.delete(0, "end")

        for t in (p.text or st["text_seen"]):
            self.text_list.insert("end", t)

        live = prompts.build_messages(self.assistant.scene_state(), "<your queswtion>")[0]["content"]

        if live != self._last_prompt:
            self._last_prompt = live
            self.prompt_box.config(state="normal")
            self.prompt_box.delete("1.0", "end")
            self.prompt_box.insert("end", live)
            self.prompt_box.config(state="disabled") 

        up = int(time.time() - self.t_start)
        self.satusbar.config(
            text = f"up{up // 60:02d}:{up % 60:02d} | heard: {st['last_heard'][:40] or '-'} | "
                    f" said: {st['last_said'][:40] or '-'} | {self._last_log[:60]}"
        )
        self.after(500, self._panels)



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="0")
    ap.add_argument("--sample", help = "saved state json used as the scene.  for the LLM")
    ap.add_argument("--dry", action = "store_true")
    ap.add_argument("--no-ocr", action = "store_true")
    ap.add_argument("--text", action ="store_true",  help="no mic, typing only")
    App(ap.parse_args()).mainloop()



if __name__ == "__main__":
    main()


