import html
import os
import time

from aqt import mw
from aqt.qt import *
from aqt.utils import openFolder, showInfo, showWarning, tooltip

from . import backup, config
from .theme import Group, Segmented, Switch
from .ui_common import Page, style_primary

STATUS_TEXT = {
    backup.INSTALLED: "Installed",
    backup.MISSING: "Not installed",
    backup.LOCAL_ONLY: "Install manually",
}


def _make_table(headers: list) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().hide()
    table.verticalHeader().setDefaultSectionSize(34)
    table.setShowGrid(False)
    table.setFrameShape(QFrame.Shape.NoFrame)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.setMinimumHeight(260)
    head = table.horizontalHeader()
    head.setHighlightSections(False)
    head.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    for col in range(1, len(headers)):
        head.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    return table


def _fill(table: QTableWidget, entries: list, columns, checked, checkable=lambda e: True) -> None:
    table.setRowCount(len(entries))
    for row, entry in enumerate(entries):
        name = QTableWidgetItem(entry["name"])
        flags = Qt.ItemFlag.ItemIsEnabled
        if checkable(entry):
            flags |= Qt.ItemFlag.ItemIsUserCheckable
            name.setCheckState(Qt.CheckState.Checked if checked(entry) else Qt.CheckState.Unchecked)
        name.setFlags(flags)
        name.setData(Qt.ItemDataRole.UserRole, entry)
        table.setItem(row, 0, name)
        for col, text in enumerate(columns(entry), start=1):
            table.setItem(row, col, QTableWidgetItem(text))


def _checked_entries(table: QTableWidget) -> list:
    out = []
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item.checkState() == Qt.CheckState.Checked:
            out.append(item.data(Qt.ItemDataRole.UserRole))
    return out


def _set_all(table: QTableWidget, state: Qt.CheckState) -> None:
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
            item.setCheckState(state)


def _select_buttons(table: QTableWidget) -> QWidget:
    holder = QWidget()
    lay = QHBoxLayout(holder)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    all_btn, none_btn = QPushButton("All"), QPushButton("None")
    all_btn.clicked.connect(lambda: _set_all(table, Qt.CheckState.Checked))
    none_btn.clicked.connect(lambda: _set_all(table, Qt.CheckState.Unchecked))
    lay.addWidget(all_btn)
    lay.addWidget(none_btn)
    return holder


class BackupPage(Page):
    def __init__(self):
        super().__init__(
            "Add-on Backup",
            "Save the list of your add-ons to a file and reinstall them anywhere — "
            "a new computer, a fresh Anki, after a reset.",
        )
        self.loaded: list = []

        self.tabs = Segmented([("Export", 0), ("Import", 1)])
        self.body.addWidget(self.tabs, 0, Qt.AlignmentFlag.AlignLeft)
        self.stack = QStackedWidget()
        self.body.addWidget(self.stack)
        self.stack.addWidget(self._build_export())
        self.stack.addWidget(self._build_import())

        auto = Group(
            "Automatic backup",
            "Saves the add-on list in the background, once a day, and keeps the last 10.",
        )
        self.auto_check = Switch(bool(config.get("auto_backup_addons")))
        auto.add_row("Back up when Anki starts", self.auto_check)
        self.open_auto_btn = QPushButton("Open folder")
        auto.add_row("Backups", self.open_auto_btn)
        self.body.addWidget(auto)
        self.body.addStretch()

        self.tabs.valueChanged.connect(self.stack.setCurrentIndex)
        self.auto_check.toggled.connect(lambda v: config.update(auto_backup_addons=v))
        self.open_auto_btn.clicked.connect(lambda: openFolder(backup.auto_backup_dir()))
        self.refresh()

    # ---- layout -----------------------------------------------------------

    def _build_export(self) -> QWidget:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(22)

        group = Group("Installed add-ons", "Tick the add-ons to include.")
        self.export_table = _make_table(["Add-on", "Install code", "Version", "Enabled"])
        group.add_widget(self.export_table)
        group.add_row("Select", _select_buttons(self.export_table))
        self.include_config = Switch(True)
        self.include_config.setToolTip("Settings can contain private data such as API keys of other add-ons.")
        group.add_row(
            "Include add-on settings", self.include_config,
            sublabel="HAVAEM's own Gemini key is never exported",
        )
        lay.addWidget(group)

        self.export_btn = QPushButton("Export…")
        style_primary(self.export_btn)
        self.export_btn.clicked.connect(self.export_backup)
        lay.addWidget(self.export_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        return pane

    def _build_import(self) -> QWidget:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(22)

        self.file_group = Group("Backup file", "No file chosen.")
        self.open_btn = QPushButton("Choose…")
        self.open_btn.clicked.connect(self.open_backup)
        self.file_group.add_row("File", self.open_btn)
        lay.addWidget(self.file_group)

        group = Group(
            "Add-ons in the backup",
            "Missing add-ons are downloaded from AnkiWeb using their install codes.",
        )
        self.import_table = _make_table(["Add-on", "Install code", "Status", "Enabled"])
        group.add_widget(self.import_table)
        group.add_row("Select", _select_buttons(self.import_table))
        lay.addWidget(group)

        restore = Group("Restore")
        self.restore_config = Switch(True)
        self.restore_enabled = Switch(True)
        restore.add_row("Add-on settings", self.restore_config)
        restore.add_row("Enabled / disabled state", self.restore_enabled)
        lay.addWidget(restore)

        row = QHBoxLayout()
        row.addStretch()
        self.copy_btn = QPushButton("Copy Install Codes")
        self.copy_btn.setToolTip("Paste into Tools ▸ Add-ons ▸ Get Add-ons… to install by hand")
        self.copy_btn.clicked.connect(self.copy_codes)
        self.install_btn = QPushButton("Install Selected")
        style_primary(self.install_btn)
        self.install_btn.clicked.connect(self.install)
        row.addWidget(self.copy_btn)
        row.addWidget(self.install_btn)
        row.addStretch()
        lay.addLayout(row)
        return pane

    def refresh(self) -> None:
        entries = backup.collect(include_config=False)
        _fill(
            self.export_table,
            entries,
            columns=lambda e: [
                str(e["id"]) if e["id"] else "From file",
                e["version"] or "",
                "Yes" if e["enabled"] else "No",
            ],
            checked=lambda e: True,
        )

    # ---- export -----------------------------------------------------------

    def export_backup(self) -> None:
        chosen = {e["dir"] for e in _checked_entries(self.export_table)}
        if not chosen:
            showWarning("Tick at least one add-on to export.", parent=self)
            return
        default = os.path.join(
            os.path.expanduser("~"), f"anki-addons-{time.strftime('%Y%m%d')}.json"
        )
        path, _ = QFileDialog.getSaveFileName(self, "Export add-on list", default, "JSON (*.json)")
        if not path:
            return
        entries = [e for e in backup.collect(self.include_config.isChecked()) if e["dir"] in chosen]
        try:
            backup.save(path, entries)
        except OSError as e:
            showWarning(f"Could not write the file:\n{e}", parent=self)
            return
        local = sum(1 for e in entries if e["id"] is None)
        note = f"\n{local} add-on(s) were installed from files and must be reinstalled by hand." if local else ""
        tooltip(f"Saved {len(entries)} add-ons to {os.path.basename(path)}.{note}", period=5000, parent=self)

    # ---- import -----------------------------------------------------------

    def open_backup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open add-on backup", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.loaded = backup.load(path)
        except ValueError as e:
            showWarning(str(e), parent=self)
            return
        self.file_group.set_footer(f"{os.path.basename(path)} · {len(self.loaded)} add-ons")
        self._show_loaded()

    def _show_loaded(self) -> None:
        _fill(
            self.import_table,
            self.loaded,
            columns=lambda e: [
                str(e["id"]) if e["id"] else "—",
                STATUS_TEXT[backup.status(e)],
                "Yes" if e["enabled"] else "No",
            ],
            checked=lambda e: backup.status(e) == backup.MISSING,
            checkable=lambda e: backup.status(e) != backup.LOCAL_ONLY,
        )

    def _selected(self) -> list:
        return _checked_entries(self.import_table)

    def copy_codes(self) -> None:
        codes = [str(e["id"]) for e in self._selected() if e["id"]]
        if not codes:
            showWarning("Open a backup and tick add-ons with an install code first.", parent=self)
            return
        QApplication.clipboard().setText(" ".join(codes))
        tooltip(f"Copied {len(codes)} codes", parent=self)

    def install(self) -> None:
        selected = self._selected()
        if not selected:
            showWarning("Open a backup file and tick the add-ons to restore.", parent=self)
            return
        rc, re_ = self.restore_config.isChecked(), self.restore_enabled.isChecked()
        missing = [e for e in selected if backup.status(e) == backup.MISSING]
        present = [e for e in selected if backup.status(e) == backup.INSTALLED]
        for entry in present:
            backup.apply_state(entry, rc, re_)

        def finished(log, done):
            self._report(log, missing, present)
            self._show_loaded()

        backup.install_missing(self.window(), missing, rc, re_, finished)

    def _report(self, log: list, missing: list, present: list) -> None:
        from aqt.addons import InstallOk, describe_log_entry

        names = {e["id"]: e["name"] for e in missing}
        lines = []
        for entry in log:
            ok = isinstance(entry[1], InstallOk)
            label = html.escape(names.get(entry[0], str(entry[0])))
            reason = html.escape(describe_log_entry(entry).split(": ", 1)[-1])
            lines.append(f"✔ {label}" if ok else f"✘ {label} — {reason}")
        if present:
            lines.append(f"↻ Applied saved settings to {len(present)} installed add-on(s)")
        if not lines:
            lines.append("Nothing to install.")
        lines.append("<br>Restart Anki to load the add-ons.")
        showInfo("<br>".join(lines), textFormat="rich", parent=self.window(), title="Add-on restore")
