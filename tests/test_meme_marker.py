"""Reply-time stickers: decider, both pick modes and history scrub, with the services faked."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import load_plugin  # noqa: E402

plugin = load_plugin()
mm = plugin.meme_marker
ON = {"memes": True, "memewiki": True, "jokes": True, "platforms": ["discord"],
      "meme_embed_url": ""}
EMBED = {**ON, "meme_embed_url": "http://embed"}
PACK = "/h/hermes/companion-data/meme-packs/dafeiyu-001-v1.3.0/memes"

ROWS = [{"file": f"/p/{n}.gif", "tag": tag, "caption": cap, "pack": "p", "keywords": ""}
        for n, (tag, cap) in enumerate([("sigh", "無語死魚臉；適合：被問煩了"), ("sad", "含著奶嘴流淚；適合：委屈"),
                                        ("sigh", "坐在火裡放空；適合：明明很糟還說沒事"),
                                        ("happy", "豎大拇指；適合：誇對方"), ("happy", "拉禮花；適合：慶祝")])]


class Transform(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.recent = Path(tmp.name) / "recent-stickers.json"
        for patcher in (mock.patch.object(mm, "_catalog", ROWS),
                        mock.patch.object(mm, "_list_system", None),
                        mock.patch.object(mm, "_index", None),
                        mock.patch.object(mm.random, "choice", lambda rows: rows[0]),
                        mock.patch.object(mm, "_recent_path", lambda: self.recent),
                        mock.patch.dict(mm._user_text, clear=True)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_transform(self, text, moment=("唉，又來", "被問煩了"), pick="2", cfg=ON, platform="discord", session="s1"):
        decide = moment if callable(moment) else (lambda user, reply: moment)
        ask = mock.Mock(side_effect=pick if isinstance(pick, BaseException) else (lambda s, u, t: pick))
        with mock.patch.object(mm, "decide", side_effect=decide) as d, mock.patch.object(mm, "_ask_flash", ask):
            out = mm.transform(text, platform, session, cfg)
        return out, d, ask

    def test_flash_picks_from_every_caption_given_the_quote_and_reaction(self):
        mm.remember_user("s1", "包裹到了沒")
        out, decide, ask = self.run_transform("還沒到，明天再查。唉，又來")
        self.assertEqual(decide.call_args.args, ("包裹到了沒", "還沒到，明天再查。唉，又來"))
        system, user, _ = ask.call_args.args
        self.assertTrue(all(f"{n}. {r['caption']}" in system for n, r in enumerate(ROWS, 1)))
        self.assertEqual(user, "情緒句：唉，又來\n你此刻的反應：被問煩了")
        self.assertEqual(out, "還沒到，明天再查。唉，又來\n\nMEDIA:/p/1.gif")

    def test_recent_stickers_are_named_in_the_user_message_and_the_listing_stays_cacheable(self):
        # Seen live: the same few images on a large share of posts. The listing in the system
        # prompt must not change between turns, or the prompt cache misses on ~470 captions.
        self.run_transform("唉", pick="1")
        self.assertEqual(json.loads(self.recent.read_text(encoding="utf-8")), ["/p/0.gif"])
        _, _, first = self.run_transform("唉", pick="4", session="s2")
        _, _, second = self.run_transform("唉", pick="5", session="s3")
        self.assertEqual(first.call_args.args[0], second.call_args.args[0])
        self.assertTrue(first.call_args.args[1].endswith("最近用過，別選：1"))
        self.assertTrue(second.call_args.args[1].endswith("最近用過，別選：1、4"))

    def test_a_recent_pick_is_replaced_by_an_unused_image(self):
        self.run_transform("唉", pick="1")
        with self.assertLogs(mm.log, "WARNING"):
            out, _, _ = self.run_transform("唉", pick="1")
        self.assertEqual(out, "唉\n\nMEDIA:/p/1.gif")

    def test_failed_pick_uses_an_unused_image(self):
        self.run_transform("唉", pick="1")
        with self.assertLogs(mm.log, "ERROR"):
            out, _, _ = self.run_transform("唉", pick=TimeoutError("flash slow"))
        self.assertEqual(out, "唉\n\nMEDIA:/p/1.gif")

    def test_every_image_recent_still_posts_one(self):
        self.recent.write_text(json.dumps([r["file"] for r in ROWS]), encoding="utf-8")
        with self.assertLogs(mm.log, "WARNING"):
            out, _, _ = self.run_transform("唉", pick="3")
        self.assertEqual(out, "唉\n\nMEDIA:/p/0.gif")

    def test_no_sticker_leaves_a_clean_reply_alone(self):
        out, _, ask = self.run_transform("明天 30 度", moment=None)
        self.assertIsNone(out)
        ask.assert_not_called()

    def test_chat_model_sticker_attempts_are_removed_and_the_decider_rules(self):
        for trace in ("[[meme:開心]]", f"MEDIA:{PACK}/sigh/wuyu.jpg", "[貼圖：无语死鱼脸]", "[貼圖]"):
            with self.subTest(trace=trace):
                out, decide, _ = self.run_transform(f"搞定了\n\n{trace}", moment=None)
                self.assertEqual(decide.call_args.args[1], "搞定了")
                self.assertEqual(out, "搞定了")
        self.assertEqual(self.run_transform("好\n\n[[meme:無奈]]", pick="5")[0], "好\n\nMEDIA:/p/4.gif")

    def test_other_media_is_kept(self):
        out, decide, _ = self.run_transform("報告在這\n\nMEDIA:/tmp/report.png", moment=None)
        self.assertIsNone(out)
        self.assertIn("MEDIA:/tmp/report.png", decide.call_args.args[1])

    def test_decider_failure_sends_the_reply_without_a_sticker(self):
        def broken(user, reply):
            raise TimeoutError("flash slow")
        with self.assertLogs(mm.log, "ERROR"):
            self.assertEqual(self.run_transform("好啦\n\n[貼圖]", moment=broken)[0], "好啦")

    def test_recent_list_is_bounded_and_moves_a_resent_file_to_the_end(self):
        for n in range(mm.RECENT + 3):
            mm._remember_sent(f"/p/x{n}.gif")
        mm._remember_sent("/p/x5.gif")
        recent = json.loads(self.recent.read_text(encoding="utf-8"))
        self.assertEqual(len(recent), mm.RECENT)
        self.assertEqual(recent[-1], "/p/x5.gif")
        self.assertEqual(recent.count("/p/x5.gif"), 1)

    def test_background_review_output_is_left_alone(self):
        # Hermes reviews each turn on a bg-review thread; its text never reaches Discord.
        result = {}
        def run():
            result["out"] = self.run_transform("好\n\n[[meme:開心]]")
        t = threading.Thread(target=run, name="bg-review")
        t.start()
        t.join()
        out, decide, _ = result["out"]
        self.assertIsNone(out)
        decide.assert_not_called()

    def test_switched_off_or_other_platform_never_asks_the_decider(self):
        out, decide, _ = self.run_transform("好\n\n[[meme:開心]]", cfg={**ON, "memes": False})
        self.assertEqual(out, "好")
        decide.assert_not_called()
        out, decide, _ = self.run_transform("好\n\n[[meme:開心]]", platform="cli")
        self.assertIsNone(out)
        decide.assert_not_called()

    # Embedding mode: the reaction against the "適合" part of each caption.

    def fake_embed(self, url, texts, timeout):
        self.assertEqual(url, "http://embed")
        known = {"被問煩了": (1.0, 0.0), "委屈": (0.6, 0.8), "明明很糟還說沒事": (0.8, 0.6),
                 "誇對方": (0.0, 1.0), "慶祝": (-1.0, 0.0)}
        return [mm.array("f", known[t.removeprefix(mm.EMBED_QUERY)]) for t in texts]

    def test_embed_mode_offers_the_closest_unused_captions_best_first(self):
        self.recent.write_text(json.dumps(["/p/0.gif"]), encoding="utf-8")
        with mock.patch.object(mm, "_embed", self.fake_embed):
            out, _, ask = self.run_transform("唉，又來", pick="1", cfg=EMBED)
        system, user, _ = ask.call_args.args
        self.assertEqual(system, mm.PICK_SYSTEM)
        listing = user.split("候選：\n", 1)[1].splitlines()
        self.assertEqual([line.split(". ", 1)[1] for line in listing],
                         [ROWS[n]["caption"] for n in (2, 1, 3, 4)])
        self.assertEqual(out, "唉，又來\n\nMEDIA:/p/2.gif")

    def test_embed_mode_failed_pick_uses_the_closest_caption(self):
        with mock.patch.object(mm, "_embed", self.fake_embed), self.assertLogs(mm.log, "ERROR"):
            out, _, _ = self.run_transform("唉", pick=ValueError("隨便"), cfg=EMBED)
        self.assertEqual(out, "唉\n\nMEDIA:/p/0.gif")


class Decide(unittest.TestCase):
    def ask(self, *answers):
        it = iter(answers)
        return mock.patch.object(mm, "_ask_flash", lambda system, user, timeout: next(it))

    def test_parses_quote_and_reaction_or_no_sticker(self):
        with self.ask("情緒句：本魚的查證直接原地失業。嗚……\n反應：「被打臉、自嘲吃癟」"):
            self.assertEqual(mm.decide("u", "r"), ("本魚的查證直接原地失業。嗚……", "被打臉、自嘲吃癟"))
        with self.ask("不貼"):
            self.assertIsNone(mm.decide("u", "r"))

    def test_simplified_answers_count(self):
        # flash sometimes answers in simplified Chinese ('开心' once cost a reply its sticker).
        with self.ask("情绪句：哼\n反应：嘴硬说还好"):
            self.assertEqual(mm.decide("u", "r"), ("哼", "嘴硬说还好"))
        with self.ask("不贴"):
            self.assertIsNone(mm.decide("u", "r"))

    def test_reaction_without_quote_still_posts(self):
        with self.ask("反應：被誇到不好意思"):
            self.assertEqual(mm.decide("u", "r"), ("", "被誇到不好意思"))

    def test_one_empty_answer_is_retried_then_garbage_raises(self):
        with self.ask("", "情緒句：好耶\n反應：得意炫耀"):
            self.assertEqual(mm.decide("u", "r"), ("好耶", "得意炫耀"))
        with self.ask("", ""), self.assertRaises(ValueError):
            mm.decide("u", "r")
        with self.ask("開心", ""), self.assertRaises(ValueError):
            mm.decide("u", "r")

    def test_long_reply_is_clipped_to_head_and_tail(self):
        seen = {}
        def ask(system, user, timeout):
            seen["user"] = user
            return "不貼"
        with mock.patch.object(mm, "_ask_flash", ask):
            mm.decide("u", "頭" * 3000 + "尾" * 3000)
        self.assertLess(len(seen["user"]), 2100)
        self.assertIn("頭", seen["user"])
        self.assertIn("尾", seen["user"])

    def test_user_text_store_is_bounded(self):
        with mock.patch.dict(mm._user_text, clear=True):
            for n in range(250):
                mm.remember_user(f"s{n}", "x")
            self.assertEqual(len(mm._user_text), 200)
            self.assertNotIn("s0", mm._user_text)


class PickNumber(unittest.TestCase):
    def test_multi_digit_numbers_and_out_of_range(self):
        # The full list has ~470 captions, so picks run to three digits.
        self.assertEqual(mm._pick_number("第 412 張", 469), 411)
        for answer in ("470", "0", "隨便"):
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                mm._pick_number(answer, 469)


CATALOG = [{"file": f"{PACK}/sigh/wuyu.jpg", "tag": "sigh", "caption": "无语死鱼脸", "pack": "p", "keywords": ""}]


class Scrub(unittest.TestCase):
    """History the model sees: sticker MEDIA lines -> notes."""

    def setUp(self):
        for patcher in (mock.patch.object(mm, "_captions", None),
                        mock.patch.object(mm.memes, "load_catalog", lambda: CATALOG)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_assistant_sticker_lines_become_notes_and_the_rest_is_untouched(self):
        msgs = [{"role": "user", "content": f"MEDIA:{PACK}/sigh/wuyu.jpg"},
                {"role": "assistant", "content": f"還沒到\n\nMEDIA:{PACK}/sigh/wuyu.jpg"},
                {"role": "assistant", "content": f"好熱\n\nMEDIA:{PACK}/daily/daily1.gif"},
                {"role": "assistant", "content": "報告\n\nMEDIA:/tmp/report.png"}]
        out = mm.scrub_request({"model": "m", "messages": msgs}, "discord", ON)["request"]
        self.assertEqual([m["content"] for m in out["messages"]], [
            f"MEDIA:{PACK}/sigh/wuyu.jpg", "還沒到\n\n[貼圖：无语死鱼脸]", "好熱\n\n[貼圖]", "報告\n\nMEDIA:/tmp/report.png"])
        self.assertEqual(out["model"], "m")

    def test_responses_api_parts(self):
        req = {"input": [{"role": "assistant", "content": [{"type": "output_text", "text": f"好\nMEDIA:{PACK}/sigh/wuyu.jpg"}]}]}
        self.assertEqual(mm.scrub_request(req, "discord", ON)["request"]["input"][0]["content"][0]["text"],
                         "好\n[貼圖：无语死鱼脸]")

    def test_nothing_to_change_or_other_platform_gives_none(self):
        self.assertIsNone(mm.scrub_request({"messages": [{"role": "assistant", "content": "嗯"}]}, "discord", ON))
        req = {"messages": [{"role": "assistant", "content": f"好\nMEDIA:{PACK}/sigh/wuyu.jpg"}]}
        self.assertIsNone(mm.scrub_request(req, "cli", ON))


if __name__ == "__main__":
    unittest.main()
