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
import prompts
import state as shared
from assistant import Assistant
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



class App(tk, TK):
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
        b = tk.Button(parent, text=text, command=cmd, bg=PANEL, fg=color, activebackground="#12303a", activeforeground=color, relief="flat", bd=0, padx=4, font=FONT, highlightthickness=1, highlightbackground=color, font=FONT).pack(sisde="left", padx=6)
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


        s = tk.Scale(row, from_=lo, to=hi, resolution=step, orient="horizontal", showvalue=False, bg=PANEL. fg=TXT, troughcolor=BG, highlightthickness=0, bd=0, activebackgroud=CYAN, command=on_change)
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
            lbl = tk.Label(chips, text=F"{name} --", bg=PANEL, fg=DIM, font=FONT, padx=8, pady=3)
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
        self._slider(frame, "OCR every(s)", 0.5, 5.0, 0.5, p.ocr_every, lambda v: setatter(p, "ocr_every", v), "{:.1f}")

        tk.Label(frame, text="VOICE", bg=PANEL, fg=CYAN, font=FONT, anchor="w").pack(fill="x", padx=10, pady=(8, 0))
        self._slider(frame, "Wake word threshold", 0.20, 0.90, 0.05, a.wake_thresh, lambda b: setattr(a, "wakethresh", v))
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
                     