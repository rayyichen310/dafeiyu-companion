"""Meme wiki matcher and "looks like asking about a meme" gate, against the pinned memes.db.

Run: python3 -m unittest discover -s <plugin dir>/tests -t <plugin dir>/tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import load_plugin  # noqa: E402

plugin = load_plugin()
mw = plugin.memewiki


class LookupSteps(unittest.TestCase):
    def title(self, q):
        row = mw.lookup(q)
        return row["title"] if row else None

    def test_exact_title(self):
        self.assertEqual(self.title("去码头整点薯条"), "去码头整点薯条")

    def test_alias_exact_item(self):
        self.assertEqual(self.title("kskbl"), "康神开播了")
        self.assertEqual(self.title("KSKBL"), "康神开播了")  # case-insensitive

    def test_title_prefix_shortest(self):
        self.assertEqual(self.title("48"), "48上单")

    def test_query_contains_title(self):
        self.assertEqual(self.title("去码头整点薯条是什么意思呢"), "去码头整点薯条")

    def test_title_contains_query_from_three_chars(self):
        self.assertEqual(self.title("码头整"), "去码头整点薯条")

    def test_two_char_chinese_query_does_not_substring_match(self):
        self.assertIsNone(self.title("头整"))  # inside a title, but only 2 chars

    def test_traditional_query_is_folded(self):
        self.assertEqual(self.title("去碼頭整點薯條"), "去码头整点薯条")

    def test_miss_and_empty(self):
        self.assertIsNone(mw.lookup("这个词库里肯定没有的东西xyz"))
        self.assertIsNone(mw.lookup("   "))


class Gate(unittest.TestCase):
    def test_asking_forms(self):
        for text, want in [
            ("去码头整点薯条是什么梗", "去码头整点薯条"),
            ("去码头整点薯条是什么梗？", "去码头整点薯条"),
            ("去码头整点薯条什么意思", "去码头整点薯条"),
            ("破防是啥意思啊", "破防"),
            ("这个到底怎么用", None),           # empty referent
            ("它是什么梗", None),
            ("大肥魚，破防是什麼梗", "破防"),     # wake word + Traditional
            ("@小明 破防是什么梗", "破防"),       # leading mention
        ]:
            with self.subTest(text=text):
                self.assertEqual(mw.extract_query(text), want)

    def test_traditional_question(self):
        self.assertEqual(mw.extract_query("去碼頭整點薯條是什麼梗"), "去码头整点薯条")

    def test_bare_word_passes_gate(self):
        self.assertEqual(mw.extract_query("kskbl"), "kskbl")
        self.assertEqual(mw.extract_query("破防"), "破防")

    def test_chatter_and_sentences_are_not_asking(self):
        for text in ["哈哈", "在吗", "晚安", "我是谁", "今天吃什么好呢", "你有没有睡饱",
                     "这样不行吧，我再想想看有没有别的办法", "", "   "]:
            with self.subTest(text=text):
                self.assertIsNone(mw.extract_query(text))


class Injection(unittest.TestCase):
    def test_question_about_known_meme_injects_only_that_entry(self):
        ctx = mw.context_for("去碼頭整點薯條是什麼梗")
        self.assertIn("[梗百科·内置用法]", ctx)
        self.assertEqual(ctx.count("[梗百科]「"), 1)
        self.assertIn("[梗百科]「去码头整点薯条」", ctx)
        self.assertLess(len(ctx), 2200)  # rules (~160) + usage<=700 + meaning<=500 + tags<=120

    def test_plain_chat_injects_nothing(self):
        for text in ["今天好累喔", "哈哈", "你在幹嘛", "我晚點再跟你說", "這個東西到底怎麼用", "這個梗到底怎麼用"]:
            with self.subTest(text=text):
                self.assertEqual(mw.context_for(text), "")

    def test_unknown_meme_injects_nothing(self):
        self.assertEqual(mw.context_for("蚌埠住了是什么梗"), "")  # absent from the pinned database

    def test_search_tool_text(self):
        self.assertIn("[梗百科]「破防」", mw.search("破防"))
        self.assertIn("没收录", mw.search("没有这个词xyz"))


if __name__ == "__main__":
    unittest.main()
