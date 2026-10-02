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