"""The text the user actually wrote, from a Discord user message as the pre_llm_call hook sees it.

The meme wiki matches on this text. Jokes are offered on every turn, so there is no casual/task
classification here any more.
"""
from __future__ import annotations

import re

# Gateway prefixes on a Discord user message (hermes-agent gateway/run_inbound.py
# _prepend_inbound_reply_context): the triggering-message note, outermost, then the reply-to
# pointer quoting the earlier message. Neither is what the user wrote, so both are dropped.
_GATEWAY_PREFIX_RE = re.compile(
    r'\A(?:\[Triggering message id: [^\n]*\]\n\n)?'
    r'(?:\[Replying to(?: your previous message)?: ".*?"\]\n\n)?',
    re.DOTALL,
)
_TEXT_PART_TYPES = {"text", "input_text"}
_IMAGE_PART_TYPES = {"image", "image_url", "input_image"}


def user_text(content) -> tuple[str, bool]:
    """(text the user wrote, has_non_image_attachment) for a str or list-of-parts message content."""
    if isinstance(content, str):
        return _GATEWAY_PREFIX_RE.sub("", content, count=1), False
    if not isinstance(content, list):
        return "", False
    texts, other = [], False
    for part in content:
        if isinstance(part, str):
            texts.append(part)
        elif isinstance(part, dict):
            kind = part.get("type")
            if kind in _TEXT_PART_TYPES:
                texts.append(str(part.get("text", "")))
            elif kind not in _IMAGE_PART_TYPES:
                other = True
    return _GATEWAY_PREFIX_RE.sub("", "\n".join(texts), count=1), other
