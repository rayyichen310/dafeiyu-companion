"""Switches and the switch-aware context builder."""
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import load_plugin  # noqa: E402

plugin = load_plugin()
classify = plugin.classify
settings = plugin.settings
jokes = plugin.jokes


class UserText(unittest.TestCase):
    def test_multimodal_parts(self):
        img = {"type": "image_url", "image_url": {"url": "x"}}
        self.assertEqual(classify.user_text([{"type": "text", "text": "你看這隻貓"}, img]), ("你看這隻貓", False))
        self.assertEqual(classify.user_text([{"type": "text", "text": "看"}, {"type": "file", "file": {}}]),
                         ("看", True))


class Switches(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        patcher = mock.patch.object(settings, "hermes_home", lambda: self.home)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_defaults_without_file(self):
        cfg = settings.load()
        self.assertEqual({k: cfg[k] for k in settings.SWITCHES},
                         {"memes": True, "memewiki": True, "jokes": True, "jokes_wanjiqi": False})
        self.assertEqual(cfg["platforms"], ["discord"])
        self.assertEqual(cfg["meme_embed_url"], "")

    def test_embed_url_must_be_a_string(self):
        settings.settings_path().parent.mkdir(parents=True)
        settings.settings_path().write_text('{"meme_embed_url": 8081}', encoding="utf-8")
        with self.assertRaises(settings.SettingsError):
            settings.load()

    def test_set_switch_round_trip_and_persists_other_keys(self):
        settings.set_switch("jokes", False)
        settings.set_switch("jokes_wanjiqi", True)
        raw = json.loads(settings.settings_path().read_text(encoding="utf-8"))
        self.assertFalse(raw["jokes"])
        self.assertTrue(raw["jokes_wanjiqi"])
        self.assertTrue(raw["memes"])
        self.assertEqual(raw["platforms"], ["discord"])

    def test_bad_input_is_rejected(self):
        with self.assertRaises(ValueError):
            settings.set_switch("nope", True)
        with self.assertRaises(ValueError):
            settings.set_switch("jokes", "yes")

    def test_broken_file_fails_closed_and_is_never_overwritten(self):
        path = settings.settings_path()
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        cfg = settings.current()
        self.assertFalse(any(cfg[k] for k in settings.SWITCHES))
        self.assertEqual(cfg["platforms"], [])
        with self.assertRaises(settings.SettingsError):
            settings.set_switch("jokes", True)
        self.assertEqual(path.read_text(encoding="utf-8"), "{not json")


class ContextBuilder(unittest.TestCase):
    ALL = {"memes": True, "memewiki": True, "jokes": True, "jokes_wanjiqi": False, "platforms": ["discord"]}

    def build(self, text, **over):
        cfg = {**self.ALL, **over}
        return plugin.build_context(text, [{"role": "user", "content": text}], "discord", cfg)

    def test_every_turn_gets_two_or_three_jokes(self):
        for text in ("哈哈你好笨", "幫我查一下明天天氣"):
            with self.subTest(text=text):
                ctx = self.build(text)
                self.assertTrue(ctx.startswith("【玩梗】"))
                self.assertIn(ctx.count("\n- "), (2, 3))

    def test_joke_hint_has_no_opt_out_or_topic_ban(self):
        ctx = self.build("哈哈你好笨")
        for phrase in ("用不上就別用", "正經", "地域", "政治"):
            self.assertNotIn(phrase, ctx)

    def test_meme_question_gets_wiki_entry_and_no_jokes(self):
        ctx = self.build("去碼頭整點薯條是什麼梗")
        self.assertIn("[梗百科]「去码头整点薯条」", ctx)
        self.assertNotIn("【玩梗】", ctx)

    def test_every_turn_ends_with_persona_reminder_and_no_sticker_hint(self):
        for text in ("哈哈你好笨", "幫我查一下明天天氣", "去碼頭整點薯條是什麼梗"):
            with self.subTest(text=text):
                ctx = self.build(text)
                self.assertTrue(ctx.endswith(plugin.TONE_HINT))
                self.assertNotIn("[[meme", ctx)
        self.assertEqual(self.build("哈哈你好笨", jokes=False, memewiki=False, memes=False), plugin.TONE_HINT)

    def test_each_switch(self):
        self.assertNotIn("【玩梗】", self.build("哈哈你好笨", jokes=False))
        self.assertEqual(self.build("去碼頭整點薯條是什麼梗", memewiki=False).count("[梗百科]"), 0)
        self.assertIn("【玩梗】", self.build("去碼頭整點薯條是什麼梗", memewiki=False))  # no wiki entry -> jokes
        self.assertNotIn("【玩梗】", self.build("哈哈你好笨", jokes=False, memewiki=False))

    def test_wanjiqi_subswitch(self):
        seeds = {e["text"] for e in jokes.load_seeds()}
        rng = random.Random(1)
        for _ in range(30):
            picked = jokes.context_text(include_wanjiqi=False, rng=rng)
            lines = [ln[2:].split("（")[0] for ln in picked.splitlines() if ln.startswith("- ")]
            self.assertTrue(set(lines) <= seeds)
        wanjiqi = {e["text"] for e in jokes.load_wanjiqi()}
        seen = set()
        for _ in range(60):
            picked = jokes.context_text(include_wanjiqi=True, rng=rng)
            seen |= {ln[2:].split("（")[0] for ln in picked.splitlines() if ln.startswith("- ")}
        self.assertTrue(seen & wanjiqi)

    def test_missing_data_injects_nothing_instead_of_failing_the_turn(self):
        with tempfile.TemporaryDirectory() as empty, mock.patch.object(settings, "hermes_home", lambda: Path(empty)):
            with self.assertLogs(plugin.log, level="ERROR"):
                result = plugin._on_pre_llm_call(
                    user_message="去碼頭整點薯條是什麼梗", conversation_history=[], platform="discord")
        self.assertIsNone(result)

    def test_discord_gateway_prefixes_are_ignored(self):
        # Hermes prepends the triggering-message note (and the reply-to pointer) to the
        # Discord user message the hook sees; only the text the user wrote is classified.
        note = "[Triggering message id: `1000000000000000001` — use as `message_id` for reply/react/pin via the discord tools.]\n\n"
        reply = '[Replying to your previous message: "我剛跑完 `git status`，見 https://example.com/a.py\n第二行"]\n\n'
        for prefix in (note, note + reply, reply):
            with self.subTest(prefix=prefix[:20]):
                casual = prefix + "哈哈你好笨"
                self.assertTrue(plugin.build_context(
                    casual, [{"role": "user", "content": casual}], "discord", self.ALL).startswith("【玩梗】"))
                wiki = prefix + "去碼頭整點薯條是什麼梗"
                self.assertIn("[梗百科]「去码头整点薯条」", plugin.build_context(
                    wiki, [{"role": "user", "content": wiki}], "discord", self.ALL))

    def test_other_platforms_get_nothing(self):
        self.assertEqual(plugin.build_context("哈哈你好笨", [], "cron", self.ALL), "")
        self.assertEqual(plugin.build_context("哈哈你好笨", [], "cli", self.ALL), "")


if __name__ == "__main__":
    unittest.main()
