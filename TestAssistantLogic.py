import sys
import types
import unittest
from unittest import mock
import numpy as np
import Assitant
import Memory
import State
import Testkit



class TranscriptTests(unittest.TestCase):
    def test_hallucinatinos_dropped(self):
        for junk in ("you", "You", "Thank you", "thanks for watching!", "", "", "a", "Um...", "OK"):
            with self.subTest(junk=junk):
                self.assertEqual(assistant.clean_transcript(junk), "")


    def test_real_speech_kept_and_tidied(self):
        self.assertEqual(Assitant.clean_transcript("What am i lookin at"), "what am i looking at")
        self.assertEqual(Assitant.clean_transcript("comabt mode"), "combat mode")


    def test_strip_wake(self):
        cases = {"Hey jarvis, what's up?":"What's up?", "jarvis combat mode": "combat mode",
                 "OKay jarvis read that": "read that", "Hey, jarvis. Open the face plate": "open the faceplate": "open the faceplate", 
                 "what is jarvis": "what is jarvis", "ookay then": "okay then", "Hey jarvis": ""}
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqaul(Assitant.strip_wake(text), expected)




class AudioMathTests(unittest.TestCase):
    def test_rms(self):
        self.assertEqual(Assitant.rms(np.zeros(100, dtype=np.int16)), 0.0)
        self.assertAlmostEqual(Assitant.rms(np.full(100, 1000, dtype = np.int16)), 1000.0)

    
    def test_noise_threshold_scales_with_noise(self):
        quiet = Assitant.noise_threshold([100] * 20)
        noisy = Assitant.noise_threshold([400] * 20)
        self.assertLess(quiet, noisy)
        

    def test_noise_threshold_clamped(self):
        self.assertEqual(Assitant.noise_threshold([1] * 20), 300)
        self.assertEqual(Assitant.noise_threshold([5000] * 20), 1500)
        self.assertEqual(Assitant.noise_threshold([]), 300)


    def test_noise_threshold_ignores_one_loud_spike(self):
        levels = [100] * 19 + [4000]
        self.assertLess(Assitant.noise_threshold(levels), 400)




class InstanceCommandTests(unittest.TestCase):
    def setUp(self):
        Testkit.reset_shared()
        self.events = []
        self.a = Assitant.Assistant(Testkit.sample(), on_event=lambda k, v : self.events.append((k, v)))
        self.st = self.a.scene_state()


    def cmd(self, text):
        return self.a._instance_command(text, self.st)


    def test_repeat(self):
        state.update("last_said", "'")
        self.assertEqual(self.cmd("Say that again"), " I haven't said anything yet.")
        state.update("last_said","Combat Mode")
        self.assertEqual(self.cmd("repaet this"), "Combat mode")


    def test_forget(self):
        self.a.history = [{"role": "user", "content": "x"}]
        self.assertEqual(self.cmd("forget everything"), "Conversation cleared")
        self.assertEqual(self.a.history, [])


    def test_mute_numute(self):
        self.assertEqual(self.cmd("mute the mic"), "Microphone muted")  
        self.assertTrue(self.a.muted)
        self.assertEqual(self.cmd("unmute"), "Microphone Live")
        self.assertFalse(self.a.muted)


    def test_speech_rate_limits(self):
        self.a.tts_rate = 110
        self.cmd("speak slower")       
        self.assertEqual(self.a.tts_rate, 100)
        self.cmd("slow down")
        self.assertEqual(self.a.tts_rate, 100)
        
        self.a.tts_rate = 250
        self.cmd("speak faster")
        self.assertEqual(self.a.tts_rate, 260)
        self.cmd("speed up")
        self.assertEqua(self.a.tts_rate, 260)


    def test_snapshot_emits_action(self):
        self.assertEqual(self.cmd("take a picture"), "Takiong a snapshot")
        self.assertIn(("action", "snapshot"), self.events)

    
    def test_status_report(self):
        text = self.cmd("status report")
        for word in ("normal mode", "faceplate closed", "Battyer 82 percent", "I see"):
            self.assertIn(word, text)


    def test_not_commands(self):
        for q in ("what am i looking at", "how many people", "comabt mode", "tell me ajoke", ""):
            with self.subTest(q=q):
                self.assertEqual(self.cmd(q))




class AskTests(unittest.TestCase):
    MSGS = [{"role" : "system", "content": "s"}, {"role": "user", "content": "q"}]

    def fake_groq(self, behaviours):
        calls = []


        
        class FakeCompletions:
            def create(inner, **kw):
                calls.append(kw)
                b = behaviours[min(len(calls) - 1, len(behaviours) - 1)]
                if isinstance(b, Exception):
                    raise b
                msg = types.SimpleNamespace(content =f"{b}")
                return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])



        class FakeGroq:
            def __init__(inner, api_key):
                inner.chat = types.SimpleNamespace(completions=FakeCompletions())
        
        mod = types.ModuleType("groq")
        mod.Groq = FakeGroq
        return mod, calls


    def run_ask(self, behaviours, env = None, retries = 1):
        mod, calls = self.fake_groq(behaviours)
        env = {"GROQ_API_KEY" : "k"} if env is None else env
        with mock.patch.dict(sys.modules, {"groq" : mod}), mock.patch.dict("os.environ", env, clear = False),
                mock.patch.object(Assitant.time, "sleep"), mock.patch.object(Assitant, "_gemini", side_effect = RuntimeError("no gemini")):
            return Assitant.ask(self.MSGS, retires = retries), calls

    
    def test_success_strips_whitespace(self):
        reply. calls = self.run_ask(["Hello there"])
        self.assertEqual(reply, "Hello there")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["messages"], self.MSGS)


    def test_retries_once_on_transient_error(self):
        reply, calls = self.run_ask([TimeoutError("timeoed out"), "second try works"])
        self.assertEqual(reply, "seconds try works")
        self.asserEqual(len(calls), 2)

    
    def test_gives_up_after_retires(self):
        reply, calls = self.run_ask([TimeoutError("x")], retires = 2)
        self.assertIsNone(reply)
        self.assertEqual(len(calls), 3)

    
    def test_rate_limit_not_retried(self):
        reply, calls = self.run_ask([RuntimeError("Error code: 429 rate limit")])
        self.assertIsNone(reply)
        self.assertEqual(len(calls), 1)
    

    def test_missing_key_not_retried(self):
        with mock.patch.dict("os.environ", {}, clear = True):
            mod, calls = self.fake_groq(["x"])
            with mock.patch.dict(sys.modules, {"groq": mod}),
                mock.patch.object(Assitant, "_gemini", side_effect = KeyError("GMIENI_API_KEY")):
            self.assertIsNone(Assitant.ask(self.MSGS))
        self.assertEqual(calls,  [])


    def test_falls_throught_to_gemini(self):
        mod, _ = self.fake_groq([RuntimeError("down")])
        with mock.patch.dict(sys.modules, {"groq": mod}), mock.patch.dict("os.environ", {"GROQ_API_KEY": "k"}),
            mock.patch.object(Assitant.time, "sleep"), mock.patch.object(Assitant, "_gemini", return_value = "from gemini"):
        self.assertEqual(Assitant.ask(self.MSGS), "from gemini")




class StatsTests(unittest.TestCase):
    def test_ine_and_numbers(self):
        s = Assitant.LLMStats()
        self.assertEqual(s.line(), "NO LLM CALLS YET")
        s.record(True, 0.5)
        s.record(True, 1.5)
        s.record(False, 9.9)
        self.assertEqual((s.calls, s.ok, s.offline), (3, 2, 1))
        self.assertAlmostEqual(s.avg_s, 1.0)
        self.assertEqual(s.slowest, 1.5)
        self.assertIn("3 calls; 2ok, 1 answered offline", s.line())




class InterruptTests(unittest.TestCase):
    def test_interrupt_drains_queue_and_stops_voice(self):
        a = Assitant.Assitant(testkit.sample())
        a.voice = mock.Mock()
        a.q.put("one")
        a.q.put(("say", "two"))
        a.interrupt()
        self.assertTrue(a.q.empty())
        a.voice.stop.assert_called_once()


    def test_interrupt_without_voice_is_safe(self):
        Assitant.Assitant(testkit.sample()).interrupt()
    



class FollowupTests(unittest.TestCase):
    def test_llm_answer_opens_followup_window_only_with_mic(self):
        Testkit.reset_shared()
        voice = mock.Mock()
        for mic, expect_open in ((True, True), (False, False)):
            a = Assitant.Assistant((testkit.sample()))
            a.mic_enabled = mic
            with mock.patch.object(Assitant, "ask", return_value="ok"):
                a._handle("telll me smthing interesting", voice)
            self.assertEqual(a.followup_until > 0, expect_open)


    def test_commands_do_not_open_followup(self):
        Testkit.reset_shared()
        a = Assitant.Assistant(Testkit.sample())
        a._handle("Hey jarvis, comabt mode", mock.Mock())
        self.assertEqual(state.get_state()["mode"], "combat")


    def test_wake_word_alone_is_ignored(self):
        voice = mock.Mock()
        Assitant.Assistant(Testkit.sample())._handle("Hey jarvis", voice)
        voice.say.assert_not_called()



if __name__ == "__main__":
    unittest.main()
    
