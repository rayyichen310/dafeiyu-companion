"""Traditional -> Simplified character folding for matching only.

The meme wiki and the meme-pack captions are simplified Chinese; the user chats in Traditional.
The table is OpenCC's character-level TSCharacters.txt (Apache-2.0, see docs/data-sources.md).
The text shown to the model or the user is never converted, only the string used for lookup.
"""
from __future__ import annotations

from . import settings

_TABLE: dict[int, str] | None = None


def _load() -> dict[int, str]:
    path = settings.data_dir() / "opencc" / "TSCharacters.txt"
    table: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, _, values = line.partition("\t")
        if len(key) == 1 and values:
            table[ord(key)] = values.split()[0]
    return table


def to_simplified(text: str) -> str:
    global _TABLE
    if _TABLE is None:
        _TABLE = _load()
    return str(text).translate(_TABLE)
