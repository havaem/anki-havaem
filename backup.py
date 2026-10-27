"""Back up the list of installed add-ons to JSON and reinstall them from it.

AnkiWeb add-ons are stored by their numeric install code, so a backup only
needs the codes (+ enabled state and settings) to bring them all back.
Add-ons that were installed from a file have no code; they are listed in the
backup but must be reinstalled by hand.
"""

import json
import os
import time
from typing import Optional

from aqt import mw

FORMAT = "havaem-addons-backup"
VERSION = 1
# secrets that must never leave this machine through an export
SECRET_KEYS = {"gemini_api_key"}

INSTALLED, MISSING, LOCAL_ONLY = "installed", "missing", "local"


def _self_dir() -> str:
    return mw.addonManager.addonFromModule(__name__)


def collect(include_config: bool = True) -> list:
    """Describe every installed add-on."""
    mgr = mw.addonManager
    entries = []
    for meta in mgr.all_addon_meta():
        config = None
        if include_config:
            config = mgr.addonMeta(meta.dir_name).get("config") or None
            if config and meta.dir_name == _self_dir():
                config = {k: v for k, v in config.items() if k not in SECRET_KEYS}
        entries.append(
            {
                "id": meta.ankiweb_id(),
                "dir": meta.dir_name,
                "name": meta.human_name(),
                "version": meta.human_version,
                "enabled": meta.enabled,
                "page": meta.page(),
                "config": config,
            }
        )
    entries.sort(key=lambda e: (e["id"] is None, e["name"].lower()))
    return entries


def build(entries: list) -> dict:
    from anki.buildinfo import version

    return {
        "format": FORMAT,
        "version": VERSION,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "anki_version": version,
        "addons": entries,
    }


def save(path: str, entries: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(build(entries), f, indent=2, ensure_ascii=False)


def load(path: str) -> list:
    """Read and validate a backup file; raises ``ValueError`` with a readable reason."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise ValueError(f"Cannot read file: {e}") from e
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("This is not a HAVAEM add-on backup file.")
    if data.get("version", 0) > VERSION:
        raise ValueError("This backup was made by a newer version of HAVAEM Tool Hub.")
    entries = []
    for raw in data.get("addons", []):
        if not isinstance(raw, dict) or not raw.get("dir"):
            continue
        entries.append(
            {
                "id": raw.get("id") if isinstance(raw.get("id"), int) else None,
                "dir": str(raw["dir"]),
                "name": str(raw.get("name") or raw["dir"]),
                "version": raw.get("version"),
                "enabled": bool(raw.get("enabled", True)),
                "page": raw.get("page"),
                "config": raw.get("config") if isinstance(raw.get("config"), dict) else None,
            }
        )
    return entries


def status(entry: dict) -> str:
    if entry["id"] is None:
        return LOCAL_ONLY
    return INSTALLED if entry["dir"] in set(mw.addonManager.allAddons()) else MISSING


def apply_state(entry: dict, restore_config: bool, restore_enabled: bool) -> None:
    """Apply saved settings / enabled flag to an add-on that is now installed."""
    mgr = mw.addonManager
    if entry["dir"] not in set(mgr.allAddons()):
        return
    if restore_config and entry.get("config"):
        mgr.writeConfig(entry["dir"], entry["config"])
    if restore_enabled and mgr.addon_meta(entry["dir"]).enabled != entry["enabled"]:
        mgr.toggleEnabled(entry["dir"], entry["enabled"])


def install_missing(parent, entries: list, restore_config: bool, restore_enabled: bool, on_done):
    """Download missing AnkiWeb add-ons, then restore their settings.

    ``on_done(log, installed_entries)`` is called on the main thread.
    """
    from aqt.addons import InstallOk, download_addons

    by_id = {e["id"]: e for e in entries if e["id"] is not None}

    def finished(log):
        done = []
        for addon_id, result in log:
            if isinstance(result, InstallOk) and addon_id in by_id:
                apply_state(by_id[addon_id], restore_config, restore_enabled)
                done.append(by_id[addon_id])
        on_done(log, done)

    if not by_id:
        on_done([], [])
        return
    download_addons(parent, mw.addonManager, list(by_id), finished)


# --------------------------------------------------------------------------- #
# Optional automatic backup on startup
# --------------------------------------------------------------------------- #

KEEP_AUTO_BACKUPS = 10


def auto_backup_dir() -> str:
    path = os.path.join(mw.addonManager.addonsFolder(_self_dir()), "user_files", "addon_backups")
    os.makedirs(path, exist_ok=True)
    return path


def run_auto_backup() -> Optional[str]:
    """Write today's backup (one per day) and prune old ones. Returns the path."""
    folder = auto_backup_dir()
    path = os.path.join(folder, f"addons-{time.strftime('%Y%m%d')}.json")
    if not os.path.exists(path):
        save(path, collect(include_config=True))
        old = sorted(f for f in os.listdir(folder) if f.startswith("addons-") and f.endswith(".json"))
        for name in old[:-KEEP_AUTO_BACKUPS]:
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass
    return path
