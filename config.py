"""Settings storage.

Settings live in Anki's add-on config (stored in the profile's ``meta.json``),
so they survive add-on updates. ``config.json`` only holds the defaults.
"""

import json
import os

from aqt import mw

_DEFAULTS_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def _addon_name() -> str:
    return mw.addonManager.addonFromModule(__name__)


def _defaults() -> dict:
    try:
        with open(_DEFAULTS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load() -> dict:
    cfg = _defaults()
    cfg.update(mw.addonManager.getConfig(_addon_name()) or {})
    return cfg


def get(key: str, default=None):
    return load().get(key, default)


def update(**changes) -> None:
    cfg = load()
    cfg.update(changes)
    mw.addonManager.writeConfig(_addon_name(), cfg)


def get_mapping(scope: str) -> dict:
    """Saved field mapping for a deck / note type, e.g. ``"nt:Vocabulary"``."""
    return dict(load().get("mappings", {}).get(scope, {}))


def save_mapping(scope: str, mapping: dict) -> None:
    mappings = dict(load().get("mappings", {}))
    mappings[scope] = mapping
    update(mappings=mappings)


def addon_dir() -> str:
    return mw.addonManager.addonsFolder(_addon_name())
