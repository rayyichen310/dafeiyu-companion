"""Reply-time stickers, decided outside the chat model.

The chat model drifted: it copied stickers from its own history onto nearly every reply, and in
long tool-heavy sessions the sticker rules faded. So before each Discord reply is sent, the
transform_llm_output hook:

1. Strips every sticker trace the chat model wrote ([[meme:...]], meme-pack MEDIA lines,
   "[貼圖...]" notes).
2. decide: deepseek-flash, seeing this turn's user message and the reply, answers "不貼" or quotes
   the reply's most emotional line plus a one-emotion reaction (under 15 characters). Mood words
   such as 害羞 / 無奈 did not fit the images (26 shy images, none fits "admitting a mistake"), and
   a line from the end of the reply missed emotions placed before a closing question.
3. pick: deepseek-flash reads the quote and reaction and picks one image, minus the last 10 sent
   in any session.
   - Default: every caption, numbered in a fixed order, is in the system prompt, so the prompt
     cache covers almost all of it; the recent images are named in the user message. A recent
     or failed pick is replaced by a random unused image (logged).
   - With meme_embed_url set (config/companion.json): the reaction is embedded and only the 8
     captions whose "適合" part is closest are offered. Cheaper per call; scored lower.
   Offline, 60 posted Discord replies, every variant's image scored 1-5 by Sonnet in one blind
   round: full list 2.95, embedding top 8 2.73, the earlier mood-category pick 2.15 (scores move
   about 0.3 between rounds, so only compare within one). An earlier embedding top-3 pick on the
   whole reply let a few images take most posts (11 of 68 for one image).

Hermes's background review of a turn (bg-review thread) also passes through this hook; its text is
never sent, so it gets no decision.

A switched-off feature, an unexpected decider answer or a failed lookup sends the reply without
an image (logged). The recent-sticker list is kept in <HERMES_HOME>/companion-data/recent-stickers.json
so it survives /new and gateway restarts.

History seen by the model (llm_request middleware, scrub_request): a meme-pack MEDIA line in an
earlier assistant reply becomes "[貼圖：caption]". The stored transcript and Discord keep the
image; the model knows what was sent but has no path to copy.
"""
from __future__ import annotations

import json
import logging
import random
import re
import threading
import urllib.request
from array import array

from . import memes, settings

log = logging.getLogger(__name__)

CHAT_URL = "https://api.deepseek.com/chat/completions"
PICK_MODEL = "deepseek-flash"
# Per-call timeouts: decide (retried once on an empty answer) + embed + pick stay under Hermes's
# 30 s plugin hook timeout. Offline, decide took 1.8 s median / 9.6 s max (1 of 60 over 8 s), the
# full-list pick 2.4 s / 8.8 s.
DECIDE_TIMEOUT, EMBED_TIMEOUT, PICK_TIMEOUT = 8, 3, 10
EMBED_TOP_K = 8
EMBED_QUERY = "Instruct: 找出適合表達這個反應的表情包使用情境\nQuery: "
LIST_SEED = 7  # the caption order the offline evaluation used

DECIDE_SYSTEM = """你幫大肥魚（一條傲嬌、愛吃、偶爾犯蠢的 AI 胖魚）決定這則 Discord 回覆要不要附一張表情包。表情包是大肥魚自己的反應，像真人聊天時隨手丟的貼圖。

先讀完整則回覆，找出大肥魚情緒最明顯的那一句：通常是它自言自語、帶語氣的句子（例如有「本魚」、哼、嗚、拴Q、好傢伙、退退退），常在結尾附近，但不一定是最後一句；最後一句常常只是問下一步。

不貼：整則只是交代資訊、列資料、一般說明，找不到這種句子。拿不準就不貼。使用者要求貼圖時一定貼。

要貼就輸出兩行：
情緒句：（從回覆原封不動抄出那一句）
反應：（15 字以內，只寫那一句的一種情緒和情境）

反應只寫一種情緒，不要寫成「得意又心虛」這種組合；那一句本身就是混合情緒時才照實寫，例如：明明很糟還硬說沒事、嘴硬說還好、被逗到好氣又好笑、假裝不在意。
只把事情做完不算得意；要有炫耀或自誇的語氣才算。

範例：
情緒句：本魚的查證直接原地失業。嗚……
反應：被打臉、自嘲吃癟

不貼時只輸出「不貼」。"""
PICK_SYSTEM = "你是大肥魚，一條傲嬌的 AI 胖魚。從候選表情包裡挑一張最符合你此刻反應的，只輸出編號。"

QUOTE_RE = re.compile(r"情[緒绪]句\s*[:：]\s*(.+)")
REACTION_RE = re.compile(r"反[應应]\s*[:：]\s*(.+)")

MARKER_RE = re.compile(r"\[\[\s*meme\s*[:：][^\]\n]{0,20}\]\]", re.IGNORECASE)
PACK_MEDIA_RE = re.compile(r"^[ \t]*MEDIA:[ \t]*\S*/meme-packs/[^/\s]+/memes/[A-Za-z]+/\S*[ \t]*(?:\n|$)", re.M)
PACK_MEDIA_LINE_RE = re.compile(r"^[ \t]*MEDIA:[ \t]*(\S*/meme-packs/[^/\s]+/memes/[A-Za-z]+/\S*)[ \t]*$", re.M)
NOTE_RE = re.compile(r"\[貼圖(?:[:：][^\]\n]{1,80})?\]")

_catalog: list[dict] | None = None  # captioned images in the fixed listing order
_list_system: str | None = None
_captions: dict[str, str] | None = None  # file -> caption
_index: tuple[str, list[array]] | None = None  # (embed url, vector per _rows() entry)
_index_lock = threading.Lock()
_user_text: dict[str, str] = {}  # session_id -> this turn's user message (set by pre_llm_call)
_recent_lock = threading.Lock()
RECENT = 10  # stickers left out of the next picks, across all sessions


def _rows() -> list[dict]:
    """Captioned images in a fixed shuffled order: stable across restarts, so the listed system
    prompt stays byte-identical and cached; shuffled, so no category sits at the top."""
    global _catalog
    if _catalog is None:
        rows = [r for r in memes.load_catalog() if r["caption"].strip()]
        _catalog = random.Random(LIST_SEED).sample(rows, len(rows))
    return _catalog


def _recent_path():
    return settings.data_dir() / "recent-stickers.json"


def recent_files() -> list[str]:
    """Files of the last RECENT stickers sent, oldest first; [] when none were recorded yet."""
    path = _recent_path()
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _remember_sent(file: str) -> None:
    with _recent_lock:
        recent = [f for f in recent_files() if f != file] + [file]
        tmp = _recent_path().with_suffix(".tmp")
        tmp.write_text(json.dumps(recent[-RECENT:], ensure_ascii=False), encoding="utf-8")
        tmp.replace(_recent_path())


def _api_key() -> str:
    # Hermes' credential route: honours the active profile's .env under multiplexing.
    from agent.secret_scope import get_secret
    key = get_secret("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set for this Hermes profile")
    return key


def _ask_flash(system: str, user: str, timeout: float) -> str:
    # Thinking stays on: without it flash read an apology as 日常. 1500 tokens: 300 sometimes ran
    # out mid-thought and left content empty.
    body = json.dumps({"model": PICK_MODEL, "max_tokens": 1500, "messages": [
        {"role": "system", "content": system}, {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(CHAT_URL, data=body, method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {_api_key()}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    usage = data.get("usage") or {}
    log.info("dafeiyu-companion: flash call %d prompt (%d cached) + %d completion tokens",
             usage.get("prompt_tokens", 0), usage.get("prompt_cache_hit_tokens", 0),
             usage.get("completion_tokens", 0))
    return data["choices"][0]["message"]["content"] or ""


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n // 2] + "\n……\n" + text[-(n // 2):]


def decide(user: str, reply: str) -> tuple[str, str] | None:
    """(emotional line quoted from the reply, reaction) for a sticker, or None for 不貼. An empty
    answer is retried once."""
    prompt = f"使用者：{_clip(user, 500)}\n大肥魚的回覆：{_clip(reply, 2000)}"
    answer = (_ask_flash(DECIDE_SYSTEM, prompt, DECIDE_TIMEOUT)
              or _ask_flash(DECIDE_SYSTEM, prompt, DECIDE_TIMEOUT))
    reaction = REACTION_RE.search(answer)
    if reaction and reaction.group(1).strip().strip("「」"):
        quote = QUOTE_RE.search(answer)
        return (quote.group(1).strip() if quote else ""), reaction.group(1).strip().strip("「」")
    if "不貼" in answer or "不贴" in answer:
        return None
    raise ValueError(f"unexpected decider answer {answer[:40]!r}")


def _pick_number(answer: str, n: int) -> int:
    m = re.search(r"\d+", answer)
    if not m or not 1 <= int(m.group(0)) <= n:
        raise ValueError(f"unexpected pick answer {answer[:40]!r}")
    return int(m.group(0)) - 1


def _moment(quote: str, reaction: str) -> str:
    return f"情緒句：{quote}\n你此刻的反應：{reaction}"


def pick_listed(quote: str, reaction: str, skip: frozenset) -> dict:
    """Image picked by flash from every caption; the files in *skip* are named as off limits."""
    global _list_system
    rows = _rows()
    if _list_system is None:
        _list_system = PICK_SYSTEM + "\n\n候選：\n" + "\n".join(
            f"{n}. {r['caption']}" for n, r in enumerate(rows, 1))
    used = [str(n) for n, r in enumerate(rows, 1) if r["file"] in skip]
    avoid = f"\n\n最近用過，別選：{'、'.join(used)}" if used else ""
    return rows[_pick_number(_ask_flash(_list_system, _moment(quote, reaction) + avoid, PICK_TIMEOUT), len(rows))]


def _embed(url: str, texts: list[str], timeout: float) -> list[array]:
    out = []
    for i in range(0, len(texts), 32):
        req = urllib.request.Request(
            url, method="POST", headers={"Content-Type": "application/json"},
            data=json.dumps({"inputs": texts[i:i + 32], "normalize": True, "truncate": True}).encode())
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out += [array("f", v) for v in json.load(resp)]
    return out


def _fit_part(caption: str) -> str:
    """The "適合：" (when to use) part of a caption: matched against the reaction."""
    return caption.split("適合：", 1)[1] if "適合：" in caption else caption


def _caption_index(url: str) -> list[array]:
    global _index
    with _index_lock:
        if _index is None or _index[0] != url:
            rows = _rows()
            _index = (url, _embed(url, [_fit_part(r["caption"]) for r in rows], timeout=20))
            log.info("dafeiyu-companion: embedded %d meme captions", len(rows))
        return _index[1]


def warm_up(url: str) -> None:
    """Embed the captions in the background at load (about 10 s), so the first sticker is not slow."""
    def run():
        try:
            _caption_index(url)
        except Exception:  # noqa: BLE001 - retried on the first sticker
            log.exception("dafeiyu-companion: meme caption warm-up failed")
    threading.Thread(target=run, name="meme-index-warmup", daemon=True).start()


def nearest(url: str, reaction: str, skip: frozenset, k: int = EMBED_TOP_K) -> list[dict]:
    """The k images whose caption best fits *reaction*, best first, leaving out *skip*."""
    vectors = _caption_index(url)
    q = _embed(url, [EMBED_QUERY + reaction], timeout=EMBED_TIMEOUT)[0]
    scored = [(sum(x * y for x, y in zip(q, v)), r) for r, v in zip(_rows(), vectors) if r["file"] not in skip]
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:k]]


def pick_nearest(quote: str, reaction: str, options: list[dict]) -> dict:
    """Image picked by flash from *options*."""
    listing = "\n".join(f"{n}. {o['caption']}" for n, o in enumerate(options, 1))
    answer = _ask_flash(PICK_SYSTEM, f"{_moment(quote, reaction)}\n\n候選：\n{listing}", PICK_TIMEOUT)
    return options[_pick_number(answer, len(options))]


def remember_user(session_id: str, text: str) -> None:
    """Keep this turn's user message for the decider (called from pre_llm_call)."""
    if session_id:
        _user_text.pop(session_id, None)
        _user_text[session_id] = text
        while len(_user_text) > 200:
            _user_text.pop(next(iter(_user_text)))


def _caption_of(path: str) -> str:
    global _captions
    if _captions is None:
        _captions = {r["file"]: r["caption"].strip() for r in memes.load_catalog() if r["caption"].strip()}
    return _captions.get(path, "")


def _scrub_text(text: str) -> str:
    def note(m):
        caption = _caption_of(m.group(1))
        return f"[貼圖：{caption}]" if caption else "[貼圖]"
    return PACK_MEDIA_LINE_RE.sub(note, text)


def scrub_request(request, platform: str, cfg: dict | None = None) -> dict | None:
    """{"request": ...} with sticker MEDIA lines in assistant turns replaced by notes, or None."""
    cfg = cfg if cfg is not None else settings.current()
    if platform not in cfg["platforms"] or not isinstance(request, dict):
        return None
    changed = 0
    for key in ("messages", "input"):  # chat completions / Responses API
        for item in request.get(key) or []:
            if not isinstance(item, dict) or item.get("role") != "assistant":
                continue
            content = item.get("content")
            if isinstance(content, str):
                new = _scrub_text(content)
                if new != content:
                    item["content"], changed = new, changed + 1
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        new = _scrub_text(part["text"])
                        if new != part["text"]:
                            part["text"], changed = new, changed + 1
    if not changed:
        return None
    log.info("dafeiyu-companion: %d sticker MEDIA lines shown to the model as notes", changed)
    return {"request": request, "source": "dafeiyu-companion", "reason": "sticker MEDIA lines -> notes"}


def _pick(quote: str, reaction: str, embed_url: str) -> dict:
    skip = frozenset(recent_files())
    unused = [r for r in _rows() if r["file"] not in skip] or _rows()
    if embed_url:
        options = nearest(embed_url, reaction, skip) or unused[:1]
        try:
            return pick_nearest(quote, reaction, options)
        except Exception:  # noqa: BLE001
            log.exception("dafeiyu-companion: meme pick failed, using the closest caption")
            return options[0]
    try:
        picked = pick_listed(quote, reaction, skip)
    except Exception:  # noqa: BLE001
        log.exception("dafeiyu-companion: meme pick failed, using a random unused image")
        return random.choice(unused)
    if picked["file"] in skip:
        log.warning("dafeiyu-companion: flash picked a recent sticker, using a random unused image")
        return random.choice(unused)
    return picked


def transform(text: str, platform: str, session_id: str = "", cfg: dict | None = None) -> str | None:
    """The reply as it should go out: chat-model sticker traces removed, plus a sticker when the
    decider finds an emotional line. None when nothing changes."""
    text = text or ""
    cfg = cfg if cfg is not None else settings.current()
    if platform not in cfg["platforms"]:
        return None
    if threading.current_thread().name.startswith("bg-review"):
        return None  # Hermes's background review of the turn: its text is never sent
    clean = NOTE_RE.sub("", PACK_MEDIA_RE.sub("", MARKER_RE.sub("", text))).rstrip()
    unchanged = None if clean == text.rstrip() else clean
    if not clean.strip() or not cfg["memes"]:
        return unchanged
    try:
        moment = decide(_user_text.get(session_id, ""), clean)
        log.info("dafeiyu-companion: sticker decision %s", moment[1] if moment else "不貼")
        if moment is None:
            return unchanged
        picked = _pick(*moment, cfg.get("meme_embed_url", ""))
    except Exception:  # noqa: BLE001 - the reply must still go out
        log.exception("dafeiyu-companion: sticker decision or lookup failed, reply sent without one")
        return unchanged
    log.info("dafeiyu-companion: meme %s -> %s", moment[1], picked["caption"][:30])
    try:
        _remember_sent(picked["file"])
    except OSError:  # the sticker still goes out; it may repeat sooner
        log.exception("dafeiyu-companion: could not record the sent sticker")
    return f"{clean}\n\nMEDIA:{picked['file']}"
