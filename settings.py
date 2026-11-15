"""Switch file for the companion plugin: <HERMES_HOME>/config/companion.json.

Read on every turn / tool call (no cache), so a change applies to the next turn without a
gateway restart. Missing file = defaults. An unreadable or malformed file fails closed (every
feature off, error logged) instead of silently falling back to "on".
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

SWITCHES = ("memes", "memewiki", "jokes")
DEFAULTS = {"memes": True, "memewiki": True, "jokes": True}
# The hooks only act on these platforms (cron, CLI, API turns get nothing).
DEFAULT_PLATFORMS = ["discord"]
# Sticker pick: "" lists every caption to deepseek-flash; an embedding endpoint URL (TEI /embed)
# narrows to the 8 closest captions first (meme_marker.py).
DEFAULT_EMBED_URL = ""


class SettingsError(RuntimeError):
    pass


def hermes_home() -> Path:
    # Hermes' own resolution, so a profile's home is used; imported here so the tests run
    # without Hermes installed.
    from hermes_constants import get_hermes_home
    return get_hermes_home()


def data_dir() -> Path:
    return hermes_home() / "companion-data"


def settings_path() -> Path:
    return hermes_home() / "config" / "companion.json"


def load() -> dict:
    """Return {switch: bool, ..., "platforms": [str], "meme_embed_url": str}; raise SettingsError
    on a bad file."""
    path = settings_path()
    raw: dict = {}
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SettingsError(f"cannot read {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise SettingsError(f"{path} must contain a JSON object")
    out: dict = {}
    for name in SWITCHES:
        value = raw.get(name, DEFAULTS[name])
        if not isinstance(value, bool):
            raise SettingsError(f"{path}: {name} must be true or false, got {value!r}")
        out[name] = value
    platforms = raw.get("platforms", DEFAULT_PLATFORMS)
    if not isinstance(platforms, list) or not all(isinstance(p, str) for p in platforms):
        raise SettingsError(f"{path}: platforms must be a list of strings")
    out["platforms"] = platforms
    embed_url = raw.get("meme_embed_url", DEFAULT_EMBED_URL)
    if not isinstance(embed_url, str):
        raise SettingsError(f"{path}: meme_embed_url must be a string")
    out["meme_embed_url"] = embed_url
    return out


def current() -> dict:
    """Like load(), but fail closed: on error everything is off."""
    try:
        return load()
    except SettingsError as exc:
        log.error("dafeiyu-companion: %s - all features disabled until fixed", exc)
        return {**{name: False for name in SWITCHES}, "platforms": [], "meme_embed_url": ""}


def set_switch(name: str, value: bool) -> dict:
    if name not in SWITCHES:
        raise ValueError(f"unknown switch {name!r}; choose from {', '.join(SWITCHES)}")
    if not isinstance(value, bool):
        raise ValueError("value must be true or false")
    state = load()  # raises SettingsError if the file is broken: never overwrite it blindly
    state[name] = value
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".companion.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return state
