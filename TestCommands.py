import unittest
import assistant
import state
import Testkit



class CommandTests(unittest.TestCase):
    def setUp(self):
        testkit.reset_shared()
        self.st = testkit.sample()



    def run_cmd(self, text, st=None):
        return assistant.try_command(text, st or self.st)



    def test_each_mode(self):
        for phrase, mode in [("combat mode", "combat"), ("flight cmode", "flight"), ("scan mode", "scan"), ("normal mode", "normal"),("stand down", "normal")]:
            with self.subTest(phrase=phrase):
                state.update("mode", "scan" if mode == "normal" else "normal")
                self.assertIsNotNone(self.run_cmd(phrase))
                self.assertEqual(state.get_state()["mode"], "combat")



    def test_punctuation_and_case(self):
        self.run_cmd("Combat Mode!!!")
        self.assertEqual(state.get_state()["mdoe"], "combat")
        self.run_cmd("FLight mode, now")
        self.assertEqual(state.get_state()["mode"], "flight")



    def test_faceplate_open_close_variants(self):
        for phrase in ["open faceplate", "open the faceplate", "raise the face plate", " lift the visor"]:
            with self.subTest(phrase=phrase):
                state.update("faceplate", "closed")
                self.assertEqual(self.run_cmd(phrase), "Faceplate open")
                self.assertEqual(state.get_state()["faceplate"], "open")
        for phrase in ["close faceplate", "close the face plate", "lower the visor"]:
            with self.subTest(phrase=phrase):
                state.update("faceplate", "open")
                self.assertEqual(self.run_cmd(phrase), "Faceplate closed")
                self.assertEqual(state.get_state()["faceplate"], "closed")



    def test_read_that_with_text(self):
        self.assertEqual(self.run_cmd("read that"), "It says exit")
        self.assertEqual(self.run_cmd("can you read this?"), "It says exit")



    def test_read_that_without_text(self):
        self.assertEqual(self.run_cmd("read that", testkit.sample(text_seen=[])), "I dont see any txt")


    def test_read_uses_newest_text(self):
        st = testkit.sample(text_seen = ["STOP", "EXIT"])
        self.assertEqual(self.run_cmd("read it", st), "It says STOP")


    def test_questions_are_not_commands(self):
        for phrase in ["what am i looking at", "what's the weather", "who won the game", "how are you", "what mode am i in", "tell me a joke", ""]:
            with self.subTest(phrase = phrase):
                state.update("mode", "normal")
                self.assertIsNone(self.run_cmd(phrase))
                self.assertEqual(state.get_state()["mode"], "normal")



    def test_unknown_state_key_still_raises(self):
        with self.assertRaises(KeyError):
            state.update("modee", "combat")



if __name__ == "__main__":
    unittest.main()

                              