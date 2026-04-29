from aqt import mw
from aqt.qt import *
from .gui import show_dialog

action = QAction("HAVAEM Tool Hub", mw)
action.triggered.connect(show_dialog)
mw.form.menuTools.addAction(action)
