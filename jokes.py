"""Jokes (玩梗): seeds and injection wording from Hanson0901/dsh-line-bot (MIT), lib/jokes.mjs at
87d5bea0d76546f132cf95cadf52e8f74c28e23a; optional wanjiqi source from Chu-Xin-r/wanjiqi-meme (MIT),
memes_top100.json, filtered the way dsh-line-bot lib/host.mjs 'joke-import-wanjiqi' does.
The injection wording is rewritten from upstream: offered on every turn, no opt-out phrasing, no
topic ban (the owner's choice); only "not when the user is sad" is kept.
"""
from __future__ import annotations

import json
import random
import re

from . import settings

WANJIQI_USAGE = "玩機器 6657 直播間彈幕梗（來源：wanjiqi-meme）"
MAX_USE_PER_REPLY = 1
MIN_PER_TURN, MAX_PER_TURN = 2, 3


def _norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def load_seeds() -> list[dict]:
    path = settings.data_dir() / "jokes" / "dsh-line-bot-jokes-defaults.json"
    return [{"text": e["text"], "usage": e.get("usage", ""), "source": "seed"}
            for e in json.loads(path.read_text(encoding="utf-8"))]


def load_wanjiqi() -> list[dict]:
    path = settings.data_dir() / "jokes" / "wanjiqi-memes_top100.json"
    out, seen = [], set()
    for item in json.loads(path.read_text(encoding="utf-8")):
        text = _norm(item.get("barrage"))
        if not (4 <= len(text) <= 40) or text in seen:  # host.mjs: 4..40 chars
            continue
        seen.add(text)
        out.append({"text": text, "usage": WANJIQI_USAGE, "source": "wanjiqi"})
    return out


def pool(include_wanjiqi: bool) -> list[dict]:
    entries = load_seeds()
    if include_wanjiqi:
        entries += load_wanjiqi()
    return entries


def render(picked: list[dict]) -> str:
    lines = [f"- {e['text']}" + (f"（{e['usage']}）" if e.get("usage") else "") for e in picked]
    return "\n".join([
        f"【玩梗】這輪可以挑一個梗自然用進回覆，一次最多 {MAX_USE_PER_REPLY} 個，不用解釋；"
        "梗只加在語氣上，內容、數字和指令照常寫清楚；使用者難過時不用。",
        "可用：",
        *lines,
    ])


def context_text(include_wanjiqi: bool, rng: random.Random | None = None) -> str:
    rng = rng or random
    entries = pool(include_wanjiqi)
    if not entries:
        return ""
    count = min(rng.randint(MIN_PER_TURN, MAX_PER_TURN), len(entries))
    return render(rng.sample(entries, count))
