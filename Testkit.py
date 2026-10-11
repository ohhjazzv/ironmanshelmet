import json 
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))



def sample(**override):
    with open(os.path.join(HERE, "sample.json")) as f:
        st = json.load(f)
    st["perceptions_ts"] = time.time()
    st.update(overrides)
    return st



def reset_shared():
    import state
    state.update("mode", "normal")
    state.update("faceplate", "closed")
    state.update("listening", False)
    state.update("thinking", False)
    state.update("alerts", [])
    state.update("text_seen", [])



def det(label, x, y, w, h, tid, conf = 0.9):
    return {"label": label, "box": [x,y,w,h], "conf":conf, "id":tid}