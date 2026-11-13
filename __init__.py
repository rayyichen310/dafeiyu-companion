"""dafeiyu-companion: memes, meme wiki, jokes and their switches for the Discord bot.

Hook   pre_llm_call  -> meme wiki entry (only when the message asks about a meme and the wiki has it),
                        otherwise 2-3 joke seeds; then a one-line persona reminder
Hook   transform_llm_output -> deepseek-flash decides whether the reply gets a sticker and which
                        (meme_marker.py); the chat model's own sticker attempts are removed
Middleware llm_request -> earlier sticker MEDIA lines reach the model as "[貼圖：caption]" notes
Tools  search_meme_wiki, companion_switch
Switches: <HERMES_HOME>/config/companion.json, read on every turn.
"""
from __future__ import annotations

import json
import logging

from . import classify, jokes, meme_marker, memewiki, settings

log = logging.getLogger(__name__)
TOOLSET = "dafeiyu_companion"
TONE_HINT = "【語氣】照大肥魚人設說話：傲嬌、口癖、偶爾犯蠢，內容照常準確。"


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


# ---------- pre_llm_call ----------

def build_context(user_message, conversation_history, platform: str, cfg: dict | None = None) -> str:
    """Text appended to this turn's user message, '' when nothing applies."""
    cfg = cfg if cfg is not None else settings.current()
    if platform not in cfg["platforms"]:
        return ""
    text, _ = classify.user_text(user_message)
    parts = []
    wiki = memewiki.context_for(text) if cfg["memewiki"] else ""
    if wiki:
        parts.append(wiki)
    # A turn that asks about a meme gets the wiki entry only; the joke hints would just distract.
    if cfg["jokes"] and not wiki:
        parts.append(jokes.context_text(include_wanjiqi=cfg["jokes_wanjiqi"]))
    # Long tool-heavy sessions bury SOUL.md under tool output; this line sits next to the reply.
    # Persona only: a per-turn sticker hint made every reply carry a sticker.
    parts.append(TONE_HINT)
    return "\n\n".join(parts)


def _on_pre_llm_call(user_message=None, conversation_history=None, platform="", session_id="", **_):
    try:
        meme_marker.remember_user(session_id or "", classify.user_text(user_message)[0])
        context = build_context(user_message, conversation_history, platform or "")
    except Exception:  # a broken feature must not take the turn down
        log.exception("dafeiyu-companion: pre_llm_call failed, injecting nothing")
        return None
    log.info("dafeiyu-companion: platform=%s injected=%d chars", platform or "-", len(context))
    return {"context": context} if context else None


def _on_llm_request(request=None, platform="", **_):
    try:
        return meme_marker.scrub_request(request, platform or "")
    except Exception:  # the request must still go out unchanged
        log.exception("dafeiyu-companion: llm_request scrub failed, request sent unchanged")
        return None


def _on_transform_llm_output(response_text="", platform="", session_id="", **_):
    try:
        return meme_marker.transform(response_text, platform or "", session_id or "")
    except Exception:  # a broken feature must not take the reply down
        log.exception("dafeiyu-companion: transform_llm_output failed, reply sent unchanged")
        return None


# ---------- tools ----------

def _search_meme_wiki(params, **_):
    if not settings.current()["memewiki"]:
        return "梗百科目前是關閉的（使用者關掉了）。不要查，也別硬解釋。"
    try:
        return memewiki.search(str((params or {}).get("query", "")))
    except Exception as exc:
        log.exception("search_meme_wiki failed")
        return f"梗百科查詢失敗：{type(exc).__name__}: {exc}"


def _companion_switch(params, **_):
    params = params or {}
    feature, enabled = params.get("feature"), params.get("enabled")
    try:
        if feature is None and enabled is None:
            state = settings.load()
        else:
            if feature not in settings.SWITCHES:
                return _json({"success": False, "error": f"feature 必須是 {', '.join(settings.SWITCHES)} 其中之一"})
            if not isinstance(enabled, bool):
                return _json({"success": False, "error": "enabled 必須是 true 或 false"})
            state = settings.set_switch(feature, enabled)
    except Exception as exc:
        log.exception("companion_switch failed")
        return _json({"success": False, "error": f"{type(exc).__name__}: {exc}"})
    return _json({
        "success": True,
        "switches": {name: state[name] for name in settings.SWITCHES},
        "note": "梗百科與玩梗的注入從下一則使用者訊息開始生效；表情包與查梗工具立即生效。",
    })


SEARCH_MEME_WIKI_SCHEMA = {
    "name": "search_meme_wiki",
    "description": (
        "Look up an internet meme, slang or abbreviation. "
        "(offline meme wiki, 6696 entries, simplified Chinese.) "
        "查網路梗、縮寫、黑話的意思。內置 6696 條詞庫（簡體中文），本地毫秒級返回。"
        "看到沒有十足把握的新詞/梗/縮寫，先查它，別硬猜、別編。query 請用簡體字。"
    ),
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "要查的詞（梗名、縮寫、黑話），簡體字"}},
        "required": ["query"],
    },
}
COMPANION_SWITCH_SCHEMA = {
    "name": "companion_switch",
    "description": (
        "Toggle memes, meme wiki and jokes on or off. "
        "(switch, enable, disable, turn on, turn off the companion features.) "
        "開關陪聊功能。使用者說「關掉／開啟 表情包／梗百科／玩梗」時呼叫本工具（這是功能開關，不要改用 memory 記下來）。"
        "feature：memes（表情包）、memewiki（梗百科）、jokes（玩梗）、jokes_wanjiqi（玩梗裡較重口味的 wanjiqi 彈幕梗來源）。"
        "enabled：true 開、false 關。兩個參數都省略則只回報目前狀態。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "feature": {"type": "string", "enum": list(settings.SWITCHES)},
            "enabled": {"type": "boolean"},
        },
    },
}


def register(ctx):
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("transform_llm_output", _on_transform_llm_output)
    ctx.register_middleware("llm_request", _on_llm_request)
    embed_url = settings.current()["meme_embed_url"]
    if embed_url:
        meme_marker.warm_up(embed_url)
    ctx.register_tool(name="search_meme_wiki", toolset=TOOLSET, schema=SEARCH_MEME_WIKI_SCHEMA,
                      handler=_search_meme_wiki)
    ctx.register_tool(name="companion_switch", toolset=TOOLSET, schema=COMPANION_SWITCH_SCHEMA,
                      handler=_companion_switch)
