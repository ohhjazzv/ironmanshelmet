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
        for bad in (["cup"], [None], [[1, 2, 3, 4]], "cup", 5):
            with self.subTest(bad=bad):
                with self.assertRaises((ValueError, TypeError)):
                    State.set_detections(bad)
    

    def test_detections_accepts_tuple_and_empty(self):
        State.set_detections((good_det(1), good_det(2)))
        self.assertEqual(len(State.get("detections")), 2)
        State.set_detections([])
        self.assertEqual(State.get("detections"), [])
    

    def test_text_seen_variants(self):
        State.update("text_seen", ("A", "B"))
        self.assertEqual(State.get("text_seen"), ["A", "B"])
        State.update("text_seen", [])
        self.assertEqual(State.get("text_seen"), [])
        for bad in ("EXIT", [None], [["EXIT"]], 5):
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    State.update("text_seen", bad)


    def test_unicode_strings_survive(self):
        State.update("last_heard", "Ni HAO JARVIS 你好")
        self.assertEqual(State.get("last_heard"), "Ni hao jarvis")


    def test_alerts_tuple_becomes_list(self):
        State.update("alerts", ("a", "b"))
        self.assertEqual(State.get("alerts"), ["a", "b"])
    

    def test_error_messages_help(self):
        with self.assertRaises(KeyError) as ctx:
            State.update("battery", 5)
        self.assertIn("battery", str(ctx.exception))
        self.assertIn("SCHEMA.md", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            State.update("mode", "turbo")
        self.assertIn("combat", str(ctx.exception))



class AtomicityTests(unittest.TestCase):
    def setUp(self):
        State.reset()


    def test_failed_update_leaves_old_value(self):
        State.update("mode", "combat")
        with self.assertRaises(ValueError):
            State.update("mode", "turbo")
        self.assertEqual(State.get("mode"), "combat")


    def test_failed_set_detections_changes_nothing(self):
        State.set_detections([good_det(1)])
        ts = State.get("perception_ts")
        time.sleep(0.01)
        bad = good_det(2)
        del bad["conf"]
        with self.assertRaises(ValueError):
            State.set_detections([good_det(3), bad])
        self.assertEqual([d["id"] for d in State.get("detections")], [1])
        self.assertEqual(State.get("perception_ts"), ts)


    def test_set_detectinos_stamps_increasing_time(self):
        State.set_detections([])
        first = State.get("perception_ts")
        time.sleep(0.01)
        State.set_detections([])
        self.assertGreater(State.get("perception_ts"), first)
        self.assertLess(abs(State.get("perception_ts") - time.time()), 2)


    def test_input_mutation_after_write_is_isolated(self):
        dets = [good_det()]
        State.set_detections(dets)
        dets[0]["label"] = "CHANGED"
        dets.append(good_det(2))
        self.assertEqual(State.get("detections"), [good_det()])


    def test_get_returns_independent_copies_each_time(self):
        a, b = State.get("frame_size"), State.get("frame_size")
        a.append(1)
        self.assertEqual(b, [640, 480])


    def test_get_unknown_key(self):
        with self.assertRaises(KeyError) as ctx:
            State.get("nope")
        self.assertIn("nope", str(ctx.exception))




class FilesTest(unittest.TestCase):
    def setUp(self):
        State.reset()
        self.dir = tempfile.mkdtemp()


    def path(self, name="s.json"):
        return os.path.join(self.dir, name)
    

    def test_saved_file_has_every_key_and_is_pretty(self):
        State.save(self.path())
        with open(self.path()) as f:
            raw = f.read()
        self.assertEqual(set(json.loads(raw)), set(State.DEFAULTS))
        self.assertIn("\n", raw)


    def test_round_trip_everything(self):
        State.set_detections([good_det(1), good_det(2, "person")])
        State.update("text_seen", ["EXIT", "STOP"])
        State.update("mode", "flight")
        State.update("battery", 42)
        State.update("alerts", ["person appeared"])
        State.save(self.path())
        before = State.get_state()
        State.reset()
        State.load(self.path())
        self.assertEqual(State.get_state(), before)


    def test_partial_file_keeps_other_keys(self):
        State.update("mode", "scan")
        with open(self.path(), "w") as f:
            json.dump({"battery": 7}, f)
        State.load(self.path())
        self.assertEqual((State.get("battery"), State.get("mode")), (7, "scan"))


    def test_unknown_key_in_file_raises(self):
        with open(self.path(), "w") as f:
            json.dump({"mood": "great"}, f)
        with self.assertRaises(KeyError):
            State.load(self.path())

    
    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            State.load(self.path("nope.json"))
        

    def test_broken_json(self):
        with open(self.path(), "w") as f:
            f.write("{not json")
        with self.assertRaises(ValueError):
            State.load(self.path())


    def test_all_scene_files_load(self):
        scenes = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenes")
        for name in sorted(os.listdir(scenes)):
            with self.subTest(scene = name):
                State.reset()
                State.load(os.path.join(scenes, name))



class ConcurrenyTests(unittest.TestCase):
    def setUp(self):
        State.reset()
    

    def test_readers_never_see_half_written_detections(self):
        errors, stop = [], threading.Event()


        def writer(n):
            while not stop.is_set():
                State.set_dections([good_det(n) for _ in range(random.randint(0,8))])

        
        def reader():
            for _ in range(500):
                ids =  {d["id"] for d in State.get_state()["detections"]}
                if len(ids) > 1:
                    errors.append(ids)

        writers = [threading.Thread(target = writer, args=(n,)) for n  in (1, 2, 3)]
        readers = [threading.Thread(target = reader) for _ in range(3)]
        for t in writers + readers:
            t.start()
        for t in readers:
            t.join()
        stop.set()

        for t in writers:
            t.join()
        self.assertEqual(errors, [])


    def test_different_threads_different_keys(self):
        def spam(key, values):
            for v in values:
                State.update(key, v)
        

        threads = [
            threading.Thread(target=spam, args=("mode", ["combat", "scan"] * 200)),
            threading.Thread(target=spam, args=("last_heard", [f"h{i}" for i in range(400)])),
            threading.Thread(target=spam, args=("battery", list(range(100)) * 4)),
            threading.Thread(target=spam, args=("listening", [True, False] * 200)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()
        s = State.get_state()
        self.assertEqual((s["mode"], s["last_heard"], s["battery"], s["listening"]), ("scan", "h399", 99, False))


    def test_reset_while_reading(self):
        stop = threading.Event()
        problems = []

        def resetter():
            while not stop.is_set():
                State.reset()

        def reader():
            for _ in range(500):
                if set(State.get_state()) != set(State.DEFAULTS):
                    problems.append("keys vanished during reset")

        t1, t2 = threading.Thread(target = resetter), threading.Thread(target = reader)
        t1.start()
        t2.start()
        t2.join()
        stop.set()
        t1.join()
        self.assertEqual(problems, [])



class FuzzTests(unittest.TestCase):
    def test_random_valid_updates_keep_state_valid(self):
        rng = random.Random(1234)
        State.reset()
        makers = {
            "mode": lambda: rng.choice(State.MODES),
            "faceplate": lambda: rng.choice(State.FACEPLATE),
            "listening": lambda: rng.random() < 0.5,
            "thinking": lambda: rng.random() < 0.5,
            "connected": lambda: rng.random() < 0.5,
            "battery": lambda: rng.choice([None, rng.randint(0, 100), rng.uniform(0, 100)]),
            "last_heared": lambda: "".join(rng.choice("abc xyz") for _ in range(rng.randint(0, 20))),
            "last_said":lambda: "".join(rng.choice("abc xyz") for _ in range(rng.randint(0, 20))),
            "text_seen": lambda: [str(rng.random()) for _ in range(rng.randint(0, 9))],
            "alerts": lambda: [str(rng.random()) for _ in range(rng.randint(0, 3))],
            "frame_size": lambda: [rng.randint(1, 4000), rng.randint(1, 4000)],
            "perception_ts": lambda: rng.uniform(0, 2e9),
        }
            
            for _ in range(2000):
                key = rng.choice(list(makers))
                State.update(key, makers[key]())
                if rng.random() < 0.05:
                    state.set_detections([good_det(rng.randint(0, 9)) for _ in range(rng.randint(0, 5))])
            for key, value in State.get_state().items():
                State._validate(key, value)
            self.assertLessEqual(len(state.get("text_seen")), State.MAX_TEXT_SEEN)


    def test_random_invalid_values_never_corrupt(self):
        rng = random.Random(99)
        State.reset()
        State.update("mode", "combat")
        junk = [None, 3, -1, 2.5, "zzz", [], {}, (), [1], {"a": 1}, object()]

        for _ in range(500):
            key = rng.choice(["mode", "faceplate", "listening", "battery", "frame_size", "perception_ts", "last_said"])
            value = rng.choice(junk)
            try: 
                State.update(key, value)
            except (TypeError, ValueError):
                pass

            for key, value in State.get_state().items():
                State._validate(key, value)

    if __name__ == "__main__":
        unittest.main()



