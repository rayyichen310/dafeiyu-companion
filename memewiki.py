"""Meme wiki: port of thawline/dsh-memewiki lib/index.js (MIT) at e377a9b87d2bcb6fee8f22e31afc2bf72ee3f5a4.

Ported as-is: the five lookup steps and their SQL, the "does this look like asking about a
meme" gate (问梗模式 / 裸词模式 / stop lists), the entry formatter and the injected rule text.
Not ported: the settings page / web API, the 串子程度 slider (off by default upstream),
write access to the database.
Changes: Python instead of Node; queries are folded Traditional -> Simplified before matching
(the database and the upstream patterns are simplified Chinese).
"""
from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

from . import settings
from .zhfold import to_simplified

log = logging.getLogger(__name__)


def db_path() -> Path:
    return settings.data_dir() / "memewiki" / "memes.db"


def _connect() -> sqlite3.Connection:
    path = db_path()
    if not path.exists():
        raise FileNotFoundError(f"meme wiki database missing: {path} (run plugins/dafeiyu-companion/fetch_sources.sh memewiki)")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- lookup (查词库) ----------

def lookup(query: str) -> dict | None:
    q = to_simplified(str(query or "")).strip()
    if not q:
        return None
    conn = _connect()
    try:
        # 1) exact title
        row = conn.execute("SELECT * FROM memes WHERE title = ?", (q,)).fetchone()
        if row:
            return dict(row)
        # 1.5) alias (comma separated, whole-item exact match)
        row = conn.execute(
            "SELECT * FROM memes WHERE aliases IS NOT NULL AND "
            "instr(',' || lower(aliases) || ',', ',' || lower(?) || ',') > 0 LIMIT 1", (q,)).fetchone()
        if row:
            return dict(row)
        # 2) title starts with the query (shortest title wins)
        row = conn.execute(
            "SELECT * FROM memes WHERE lower(title) LIKE lower(?) || '%' ORDER BY length(title) ASC LIMIT 1",
            (q,)).fetchone()
        if row:
            return dict(row)
        # 3) query contains a title (longest title wins)
        row = conn.execute(
            "SELECT * FROM memes WHERE length(title) >= 2 AND instr(?, title) > 0 "
            "ORDER BY length(title) DESC LIMIT 1", (q,)).fetchone()
        if row:
            return dict(row)
        # 4) title contains the query: >= 3 chars, or >= 2 for pure ascii alphanumerics
        relaxed = len(q) >= 2 and re.fullmatch(r"[0-9a-z]+", q, re.IGNORECASE) is not None
        if len(q) >= 3 or relaxed:
            row = conn.execute(
                "SELECT * FROM memes WHERE instr(title, ?) > 0 ORDER BY length(title) ASC LIMIT 1", (q,)).fetchone()
            if row:
                return dict(row)
        return None
    finally:
        conn.close()


def _clip(value, limit: int) -> str:
    text = re.sub(r"\s+", " ", "" if value is None else str(value)).strip()
    return text[:limit] + "…" if len(text) > limit else text


def entry_text(row: dict | None) -> str:
    if not row:
        return ""
    usage = _clip(row.get("usage"), 700)
    meaning = _clip(row.get("summary") or row.get("origin") or "", 500)
    tags = _clip(row.get("tags"), 120)
    lines = [f"[梗百科]「{row.get('title') or ''}」"]
    if tags:
        lines.append(f"标签：{tags}")
    if usage:
        lines.append(f"怎么用 / 怎么接：\n{usage}")
    if meaning:
        lines.append(f"出处与含义：\n{meaning}")
    return "\n".join(lines)


RULES = (
    "[梗百科·内置用法]\n"
    "1. 查到词条就**先接梗、别科普**：照「怎么用/怎么接」回一句，像本来就会；\n"
    "2. 只有对方明确问「这是什么梗」才解释出处，一两句就够，不要念词条；\n"
    "3. 查不到就说不知道，别硬编，也别把两个不相干的梗拼一起；\n"
    "4. 说话用短句，别用客服腔。"
)


def render(row: dict) -> str:
    # upstream: rules + "\n" + (串子文案, empty when its switch is off) + "\n" + entry
    return RULES + "\n\n" + entry_text(row)


# ---------- gate: does the message look like asking about a meme? (提取查询) ----------

ASK_PATTERN = re.compile(
    r"(?:是)?(?:什么梗|啥梗|什么来头|什么来历|什么出处|什么意思|啥意思|怎么用|怎么接|怎么玩|如何用)"
    r"(?:啊|呀|呢|的|啊这是)?[？?。！!~～]*\Z")
BARE_PATTERN = re.compile(r"[一-龥A-Za-z0-9·]{2,10}\Z")

EMPTY_REFERENTS = {
    "这", "那", "它", "他", "她", "这个", "那个", "你", "这句话", "那句话", "上面", "刚才", "下文", "前面",
}
STOPWORDS = {
    "在吗", "在不在", "哈哈", "哈哈哈", "笑死", "好的", "好吧", "晚安", "早安",
    "睡觉", "吃饭", "干嘛", "没事", "收到", "谢谢", "好耶", "草", "典", "乐",
}
CHATTER = {
    "我是谁", "错了", "情绪", "接下一句", "你也学一个", "今天看什么", "到底多少了",
    "搜出来了吗", "来点贴吧评价", "都是同龄人", "你同事", "道德这么高",
    "这是谁的手臂", "比我能串", "宝宝你醒了", "中国人能不能飞", "你现在什么人格",
}
SENTENCE_PARTS = re.compile(r"怎么样|怎么|多少|为什么|能不能|是不是|什么|了吗|了没|一下|你说|要不要|有没有")
WAKE_WORDS = ["小鲸鱼", "大鲸鱼", "大肥鲸", "小肥鲸", "大肥鱼", "奶鱼", "鲸鱼", "deepseek", "ds"]

_EDGE_PUNCT = re.compile(r"^[ ，,。.！!？?]+|[ ，,。.！!？?]+\Z")
_WAKE_EDGE = re.compile(r"^[，,。.！!？?:：]+|[，,。.！!？?:：]+\Z")


def _clean(text: str) -> str:
    t = str(text or "").strip()
    t = re.sub(r"^(@\S+\s*)+", "", t)
    for word in WAKE_WORDS:
        if t.startswith(word):
            t = _WAKE_EDGE.sub("", t[len(word):].strip())
            break
    return t.strip()


def extract_query(text: str) -> str | None:
    """Candidate meme title from a user message, or None when it does not look like a meme question."""
    t = _clean(to_simplified(text))
    if not t:
        return None
    m = ASK_PATTERN.search(t)
    if m:
        head = _EDGE_PUNCT.sub("", t[:m.start()])
        head = re.sub(r"^是+|是+\Z", "", head).strip()
        head = re.sub(r"(这个梗|那个梗|这梗|那梗|这个|那个)\Z", "", head).strip()
        head = re.sub(r"(到底|究竟)\Z", "", head).strip()
        if head in EMPTY_REFERENTS:
            return None
        if len(head) <= 2 and head and head[0] in "这那它他她":
            return None
        if 1 < len(head) <= 12:
            return head
        return None
    if BARE_PATTERN.match(t) and t not in STOPWORDS and t not in CHATTER:
        if SENTENCE_PARTS.search(t):
            return None
        return t
    return None


# ---------- entry points used by the plugin ----------

def context_for(text: str) -> str:
    """Text to inject for this user message: rules + the single hit entry, or '' when nothing hits."""
    query = extract_query(text)
    if not query:
        return ""
    row = lookup(query)
    if not row:
        return ""
    log.info("dafeiyu-companion memewiki hit: %s -> %s", query, row.get("title"))
    return render(row)


def search(query: str) -> str:
    """Tool result for search_meme_wiki."""
    q = str(query or "").strip()
    if not q:
        return "要查什么？给我一个词。"
    row = lookup(q)
    if not row:
        return f"词库里没收录「{q}」。别硬解释——说不知道，或者反问一句「这什么梗」。"
    return render(row)
