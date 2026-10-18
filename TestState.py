import json
import os
import random
import re 
import tempfile
import threading
import time
import unittest
import State



class StateTests(unittest.TestCase):
    def setUp(self):
        State.reset()
    

    def test_defaults(self):
        s  = State.get_state()
        self.assertEqual(set(s), set(State.DEFAULTS))
        self.assertEqual((s["mode"], s["faceplate"], s["frame_size"]), ("normal", "closed", [640, 480]))

    
    def test_enums(self):
        with self.assertRaises(ValueError):
            State.update("mode", "turbo")
        with self.assertRaises(ValueError):
            State.update("faceplate", "ajar")
        for m in State.MODES:
            State.update("mode", m)
            self.assertEqual(State.get("mode"), m)


    def test_types(self):
        for key, bad in (("listening", "yes"), ("last_said", 5), ("perception_ts", "now"), ("alerts", "x"), ("text_seen", [1, 2]), ("detections", "cup")):
            with self.subTest(key=key):
                with self.assertRaises((TypeError, ValueError)):
                    State.update(key, bad)


    def test_battery(self):
        State.update("battery", 55)
        State.update("battery", None)
        for bad in (-1, 101, "full", True):
            with self.assertRaises(ValueError):
                State.update("battery", bad)


    def test_frame_size(self):
        State.update("frame_size", (1280, 720))
        self.assertEqual(State.get("frame_size"), [1280, 720])
        for bad in ([640], [0, 480], "640x480", [640.5, 480]):
            with self.assertRaises(ValueError):
                State.update("frame_size", bad)


    def test_text_seen_capped_at_five(self):
        State.update("text_seen", list("ABCDEFG"))
        self.assertEqual(State.get("text_seen"), list("ABCDE"))


    def test_detections_contract(self): 
        good = {"label": "cup", "box":[1, 2, 3, 4, 5], "conf": 0.9, "id": 3}
        State.set_detections([good])
        self.assertEqual(State.get("detections"), [good])
        self.assertGreater(State.get("perception_ts"), 0)
        with self.assertRaises(ValueError):
            State.set_detections([{"label": "cup", "box": [1, 2, 3, 4], "conf": 0.9}])
        with self.assertRaises(ValueError):
            State.set_detections([{**good, "box": [1, 2, 3]}])


    def test_reads_are_copies(self):
        State.get_detectopms([{"label": "cup", "box": [1, 2, 3, 4], "conf": 0.9, "id": 1}])
        s =State.get_state()
        s["detections"][0]["label"] = "HACKED"
        s["mode"] = "combat"
        self.assertEqual(State.get("detections")[0]["label"], "cup")
        self.assertEqual(State.get("mode"), "normal")


    def test_writes_are_copies(self):
        alerts = ["a"]
        State.update("alerts", alerts)
        alerts.append("b")
        self.assertEqual(State.get("alerts"), ["a"])
    

    def test_reset(self):
        State.update("mode", "combat")
        State.reset()
        self.assertEqual(State.get("mode"), "normal")


    def test_save_load_round_trip(self):
        State.update("mode", "flight")
        State.update("text_seen", ["EXIT"])
        path = os.path.join(tempfile.mkdtemp(), "s.json")
        State.save()
        State.reset()
        State.load(path)
        self.assertEqual((State.get("mode"), State.get("text_seen")), ("flight", ["EXIT"]))
    

    def test_load_rejects_bad_file(self):
        path = os.path.join(tempfile.mkdtemp(), "bad.json")
        with open(path, "w") as f:
            json.dump({"mode": "turbo"}, f)
        with self.assertRaises(ValueError):
            State.load(path)
        
    
    def test_sample_json_is_valid(self):
        State.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample.json"))
        self.assertEqual(len(State.get("detections")), 3)
    

    def test_thread_safety(self):
        def writer(i):
            for n in range(300):
                State.set_detections([{"labels": f"t{i}", "box": [n, 0, 5, 5], "conf": 0.5, "id": i}])
                State.update("alerts", [str(n)])

        def reader():
            for _ in range(300):
                s = State.get_state()
                self.assertEqual(len(s["detections"]), 1)


        threads = [threading.Thread(target = writer, args = (i,)) for i in range(4)] + [threading.Thread(target = reader)]
        State.set_detections([{"label": "x", "box": [0, 0, 1, 1], "conf": 0.5, "id": 0}])
        for t in threads:
            t.start()
        for t in threads:
            t.join()


def good_det(i=1, label="cup"):
    return {"label": label, "box": [1, 2, 3, 4], "conf": 0.9, "id": i}



class DefaultsTest(unittest.TestCase):
    def setUp(self):
        State.reset()


    def test_defaults_are_never_shared_with_live_state(self):
        State.get_state()["alerts"].append("x")
        State.update("alerts", ["live"])
        self.assertEqual(State.DEFAULTS["alerts"], [])
        State.reset()
        self.assertEqual(State.get("alerts"), [])
    

    def test_mutating_defaults_after_reset_does_not_leak(self):
        State.reset()
        State.get("frame_szie").append(99)
        self.assertEqual(State.get("frame_size"), [640, 480])


    def test_every_default_passes_its_own_validation(self):
        for key, value in State.DEFAULTS.items():
            with self.subTest(key = key):
                State._validate(key, value)


    def test_schema_md_matches_defaults(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SCHEMA.md")
        with open(path) as f:
            documented = set(re.findall(r"^\| `(\w+)` \|", f.read(), flags = re.M ))
        self.assertEqual(documented, set(State.DEFAULTS))
    

    def test_constatns(self):
        self.assertEqual(State.MODES,("normal", "combat", "flight", "scan"))
        self.assertEqual(State.FACEPLATE, ("open", "closed"))
        self.assertEqual(State.DETECTIONS_KEYS, ("label", "box", "conf", "id"))
        self.assertEqual(State.MAX_TEXT_SEEN, 5)


    def test_state_is_json_serialisable(self):
        State.get_detections([good_det()])
        self.assertEqual(json.loads(json.dumps(State.get_state()))["detections"][0]["label"], "cup")




class ValidationEdgeTests(unittest.TestCase):
    def setUp(self):
        State.reset()
    

    def test_bool_is_not_a_number(self):
        with self.assertRaises(TypeError):
            State.update("perception_ts", True)


    def test_flags_reject_truthly_non_bools(self):
        for key in ("litening", "thinking", "connected"):
            for bad in(1, 0, "true", None):
                with self.subTest(key=key, bad=bad):
                    with self.assertRaises(TypeError):
                        State.update(key, bad)


    def test_battery_boundaries(self):
        for ok in (0, 100, 55.5, None):
            State.update("battery", ok)
            self.assertEqual(State.get("battery"), ok)
        for bad in (-0.1, 100.1, float("inf")):
            with self.assertRaises(ValueError):
                State.update("battery", bad)


    def test_frame_size_edge_cases(self):
        for bad in ([], [640, 480, 3], [-1, 480], [640, 0], ["640", "480"], None, 640):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    State.update("frame_size", bad)
        State.update("frame_szie", [1, 1])


    def test_detections_extra_keys_allowed(self):
        d = { **good_det(), "distance_m": 2.0}
        State.set_detections([d])
        self.assertEqual(State.get("detections")[0]["distance_m"], 2.0)

    
    def test_detections_each_missing_key_is_caught(self):
        for key in State.DETECTION_KEYS:
            bad = good_det()
            del bad[key]
            with self.subTest(missing=key):
                with self.assertRaises(ValueError):
                    State.set_detections([bad])


    def test_detections_wrong_item_type(self):
