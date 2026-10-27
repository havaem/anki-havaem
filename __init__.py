from aqt import gui_hooks, mw
from aqt.qt import *

from . import backup, config
from .gui import close_dialog, show_dialog


def _on_profile_open() -> None:
    if config.get("auto_backup_addons"):
        try:
            backup.run_auto_backup()
        except Exception as e:  # never block Anki's startup over a backup
            print(f"HAVAEM: automatic add-on backup failed: {e}")


action = QAction("HAVAEM Tool Hub", mw)
action.triggered.connect(show_dialog)
mw.form.menuTools.addAction(action)

gui_hooks.profile_did_open.append(_on_profile_open)
gui_hooks.profile_will_close.append(close_dialog)
