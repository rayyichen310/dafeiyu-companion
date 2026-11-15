"""Sticker catalog: index.db rows must stay inside their pack directory."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import load_plugin  # noqa: E402

plugin = load_plugin()
memes = plugin.memes


class LoadCatalog(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        home = Path(tmp.name)
        pack = home / "companion-data" / "meme-packs" / "p-v1"
        pack.mkdir(parents=True)
        (pack / "manifest.json").write_text('{"name": "p"}', encoding="utf-8")
        conn = sqlite3.connect(pack / "index.db")
        conn.execute("CREATE TABLE memes (path TEXT, tag TEXT, caption TEXT, keywords TEXT)")
        self.outside = home / "secret.txt"
        conn.executemany("INSERT INTO memes VALUES (?, 'happy', ?, '')", [
            ("memes/ok.gif", "ok"),
            ("../../secret.txt", "dot-dot"),
            (str(self.outside), "absolute"),
        ])
        conn.commit()
        conn.close()
        for patcher in (mock.patch.object(plugin.settings, "hermes_home", lambda: home),
                        mock.patch.object(memes, "_overrides", lambda: {})):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.pack = pack

    def test_rows_that_leave_the_pack_directory_are_dropped(self):
        rows = memes.load_catalog()
        self.assertEqual([r["caption"] for r in rows], ["ok"])
        self.assertEqual(rows[0]["file"], str(self.pack / "memes/ok.gif"))

    def test_each_dropped_row_is_logged(self):
        with self.assertLogs(memes.__name__, "WARNING") as logs:
            memes.load_catalog()
        self.assertEqual(len(logs.records), 2)


if __name__ == "__main__":
    unittest.main()
