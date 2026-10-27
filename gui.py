from aqt import mw
from aqt.qt import *
from aqt.utils import restoreGeom, saveGeom

from .page_backup import BackupPage
from .page_create import CreatorPage
from .page_enrich import EnrichPage
from .page_settings import SettingsPage
from .theme import FONT_FAMILIES, badge_icon, build_style

GEOMETRY_KEY = "havaem_tool_hub"

_dialog = None


class HavaemMainDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hub")
        self.setWindowTitle("HAVAEM Tool Hub")
        self.setMinimumSize(820, 580)
        self.resize(1000, 720)
        font = QFont()
        font.setFamilies(FONT_FAMILIES)
        self.setFont(font)
        self.setStyleSheet(build_style())
        restoreGeom(self, GEOMETRY_KEY)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        side = QWidget()
        side.setObjectName("side")
        side.setFixedWidth(220)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(12, 18, 12, 12)
        side_lay.setSpacing(8)
        name = QLabel("HAVAEM Tool Hub")
        name.setObjectName("appName")
        side_lay.addWidget(name)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setIconSize(QSize(26, 26))
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        side_lay.addWidget(self.nav, 1)

        self.stack = QStackedWidget()
        self.pages = []
        self._add_page("Add Missing Fields", badge_icon("plus", "#34c759"), EnrichPage())
        self._add_page("Smart Word Creator", badge_icon("spark", "#ff9f0a"), CreatorPage())
        self._add_page("Add-on Backup", badge_icon("backup", "#007aff"), BackupPage())
        self._add_page("Settings", badge_icon("sliders", "#8e8e93"), SettingsPage())

        layout.addWidget(side)
        layout.addWidget(self.stack, 1)

        self.nav.currentRowChanged.connect(self._show)
        self.nav.setCurrentRow(0)

    def _add_page(self, title: str, icon, page: QWidget) -> None:
        self.nav.addItem(QListWidgetItem(icon, title))
        self.stack.addWidget(page)
        self.pages.append(page)

    def _show(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
        page = self.pages[row]
        if hasattr(page, "refresh"):
            page.refresh()

    def done(self, result: int) -> None:
        saveGeom(self, GEOMETRY_KEY)
        super().done(result)


def show_dialog() -> None:
    """Open the hub (modeless; reuses the window if it is already open)."""
    global _dialog
    if _dialog is not None:
        try:
            _dialog.show()
            _dialog.raise_()
            _dialog.activateWindow()
            return
        except RuntimeError:  # underlying C++ object already deleted
            _dialog = None
    _dialog = HavaemMainDialog(mw)
    _dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    _dialog.destroyed.connect(lambda: _clear())
    _dialog.show()


def _clear() -> None:
    global _dialog
    _dialog = None


def close_dialog() -> None:
    """The collection is about to go away (profile switch / quit)."""
    if _dialog is not None:
        try:
            _dialog.close()
        except RuntimeError:
            pass
