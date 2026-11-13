"""Image catalog of the downloaded dsh-meme-packs packs.

Each pack's index.db holds a category tag, caption and keywords per image; it is read here and
never put into the model's context. caption-overrides.json, shipped in this plugin directory, replaces
the tag and caption per image ("<pack dir>/<path>" -> {"tag", "caption"}): the pinned upstream index.db
stays as downloaded. Tag "skip" leaves the image out. meme_marker.py chooses an image and delivers it with Hermes'
documented `MEDIA:<absolute path>` directive: the Discord adapter uploads the file (GIFs play
inline).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import settings


def _packs_dir() -> Path:
    return settings.data_dir() / "meme-packs"


def _overrides() -> dict:
    return json.loads(Path(__file__).with_name("caption-overrides.json").read_text(encoding="utf-8"))


def load_catalog() -> list[dict]:
    overrides = _overrides()
    rows = []
    for pack in sorted(p for p in _packs_dir().iterdir() if (p / "index.db").exists()):
        name = json.loads((pack / "manifest.json").read_text(encoding="utf-8")).get("name", pack.name)
        conn = sqlite3.connect(f"file:{pack / 'index.db'}?mode=ro", uri=True)
        try:
            for path, tag, caption, keywords in conn.execute("SELECT path, tag, caption, keywords FROM memes"):
                over = overrides.get(f"{pack.name}/{path}", {})
                tag, caption = over.get("tag", tag), over.get("caption", caption)
                if tag == "skip":
                    continue
                rows.append({"file": str(pack / path), "pack": name, "tag": tag,
                             "caption": caption or "", "keywords": keywords or ""})
        finally:
            conn.close()
    if not rows:
        raise FileNotFoundError(f"no meme packs found under {_packs_dir()}")
    return rows
