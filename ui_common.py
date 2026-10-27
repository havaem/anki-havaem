"""Shared UI pieces: page scaffold, field mapper, audio picker."""

import os
import tempfile

from aqt import mw
from aqt.qt import *

from . import config
from .providers import CAMBRIDGE_REGIONS, FIELD_KEYS, GOOGLE_REGIONS, get_audio
from .theme import Group, Segmented, Switch

# Short labels for segmented controls (the full names live in providers.py)
TEXT_SEG = [("Cambridge", "cambridge"), ("Free API", "free"), ("Gemini", "gemini")]
AUDIO_SEG = [("Cambridge", "cambridge"), ("Google", "google")]
REGION_SEG = {
    "cambridge": [(label, value) for label, value in CAMBRIDGE_REGIONS],
    "google": [("US", "us"), ("UK", "uk"), ("Australia", "au"), ("India", "in")],
}


def muted(widget: QWidget) -> None:
    widget.setObjectName("secondary")


def style_primary(button: QPushButton) -> None:
    button.setObjectName("primary")
    button.setCursor(Qt.CursorShape.PointingHandCursor)


class Page(QScrollArea):
    """Scrollable page with a large title; put groups in ``self.body``."""

    MAX_WIDTH = 680

    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setAutoFillBackground(False)

        inner = QWidget()
        inner.setObjectName("pageInner")
        outer = QHBoxLayout(inner)
        outer.setContentsMargins(28, 28, 28, 32)
        content = QWidget()
        content.setMaximumWidth(self.MAX_WIDTH)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        outer.addStretch(1)
        outer.addWidget(content, 100)
        outer.addStretch(1)

        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(22)
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        self.body.addWidget(heading)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("secondary")
            sub.setWordWrap(True)
            self.body.addWidget(sub)
        self.setWidget(inner)

    def add_primary(self, button: QPushButton) -> None:
        style_primary(button)
        self.body.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.body.addStretch()


# --------------------------------------------------------------------------- #
# Field mapping
# --------------------------------------------------------------------------- #

# order matters: more specific keys claim their field first
_HINTS = [
    ("tr_sentence", ("translat", "vietnam", "dịch", "_vi", "vi_", "viet")),
    ("sentence", ("sentence", "example", "câu", "ví dụ", "context")),
    ("ipa", ("ipa", "phonetic", "pronunc", "phiên âm")),
    ("pos", ("part of speech", "speech", "pos", "loại từ", "từ loại", "type")),
    ("synonyms", ("synonym", "đồng nghĩa")),
    ("mnemonic", ("mnemonic", "mẹo", "tip", "hint", "memo")),
    ("audio", ("audio", "sound", "âm thanh", "voice")),
    ("image", ("image", "picture", "img", "photo", "hình", "ảnh")),
    ("meaning", ("meaning", "definition", "nghĩa", "def", "back")),
    ("word", ("word", "vocab", "term", "từ", "front", "expression")),
]


def guess_fields(field_names: list) -> dict:
    taken: set = set()
    guess: dict = {}
    for key, hints in _HINTS:
        for name in field_names:
            lowered = name.lower()
            if name not in taken and any(h in lowered for h in hints):
                guess[key] = name
                taken.add(name)
                break
    if "word" not in guess and field_names:
        guess["word"] = field_names[0]
    return guess


class FieldMapper(QObject):
    """One row per data key with a field picker. ``mapping()`` -> {key: field}."""

    changed = pyqtSignal()

    def __init__(self, labels: dict = None, hints: dict = None):
        super().__init__()
        self.labels = labels or {}
        self.hints = hints or {}
        self.combos = {key: QComboBox() for key, _ in FIELD_KEYS}
        self.rows: dict = {}
        for combo in self.combos.values():
            combo.currentIndexChanged.connect(lambda _=0: self.changed.emit())

    def add_to(self, group: Group) -> None:
        for key, default_label in FIELD_KEYS:
            self.rows[key] = group.add_row(
                self.labels.get(key, default_label), self.combos[key], self.hints.get(key, "")
            )

    def set_fields(self, names: list, saved: dict = None) -> None:
        saved = saved or {}
        guess = guess_fields(names)
        for key, combo in self.combos.items():
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("None", "")
            for name in names:
                combo.addItem(name, name)
            wanted = saved[key] if key in saved else guess.get(key, "")
            combo.setCurrentIndex(max(combo.findData(wanted), 0))
            combo.blockSignals(False)
        self.changed.emit()

    def mapping(self) -> dict:
        return {k: c.currentData() for k, c in self.combos.items() if c.currentData()}

    def raw_mapping(self) -> dict:
        """Includes explicit 'None' choices, so they are remembered."""
        return {k: (c.currentData() or "") for k, c in self.combos.items()}

    def set_enabled_keys(self, keys) -> None:
        for key, row in self.rows.items():
            row.setEnabled(keys is None or key in keys)


# --------------------------------------------------------------------------- #
# Audio source / accent
# --------------------------------------------------------------------------- #


class AudioOptions(QObject):
    """Audio source, accent, fallback and a test button. Shared via config."""

    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.source = Segmented(AUDIO_SEG)
        self.region = Segmented(REGION_SEG["cambridge"])
        self.fallback = Switch()
        self.test_btn = QPushButton("Play “hello”")
        self.test_btn.setToolTip("Fetch and play a sample with the current choice")
        self.reload()
        self.source.valueChanged.connect(self._on_source)
        self.region.valueChanged.connect(self._on_region)
        self.fallback.toggled.connect(self._on_fallback)
        self.test_btn.clicked.connect(self.test_audio)

    def add_to(self, group: Group) -> None:
        group.add_row("Source", self.source)
        group.add_row("Accent", self.region)
        group.add_row(
            "Use the other source if missing", self.fallback,
            sublabel="Falls back when a word has no audio",
        )
        group.add_row("Preview", self.test_btn)

    def _fill_regions(self, source: str) -> None:
        self.region.set_options(REGION_SEG[source])
        self.region.set_value(config.get(f"{source}_region"))

    def reload(self) -> None:
        """Re-read from config (another page may have changed it)."""
        cfg = config.load()
        for w in (self.source, self.region, self.fallback):
            w.blockSignals(True)
        self.source.set_value(cfg["audio_source"])
        self._fill_regions(self.source.value())
        self.fallback.setChecked(bool(cfg["audio_fallback"]))
        for w in (self.source, self.region, self.fallback):
            w.blockSignals(False)

    def _on_source(self, source) -> None:
        config.update(audio_source=source)
        self._fill_regions(source)
        self.changed.emit()

    def _on_region(self, region) -> None:
        config.update(**{f"{self.source.value()}_region": region})
        self.changed.emit()

    def _on_fallback(self, checked: bool) -> None:
        config.update(audio_fallback=checked)
        self.changed.emit()

    def test_audio(self) -> None:
        from aqt.sound import av_player
        from aqt.utils import showWarning, tooltip

        source, region = self.source.value(), self.region.value()
        self.test_btn.setEnabled(False)

        def task():
            return get_audio("hello", source, {source: region}, fallback=False)

        def done(future):
            try:
                self.test_btn.setEnabled(True)
            except RuntimeError:  # The hub was closed during the request.
                return
            try:
                audio, problems = future.result()
            except Exception as e:  # noqa: BLE001
                showWarning(str(e), parent=self.test_btn)
                return
            if not audio:
                showWarning("Could not get audio:\n" + "\n".join(problems), parent=self.test_btn)
                return
            fd, path = tempfile.mkstemp(suffix=f".{audio.ext}", prefix="havaem_test_")
            with os.fdopen(fd, "wb") as f:
                f.write(audio.data)
            tooltip(f"Playing {audio.tag}", parent=self.test_btn)
            av_player.play_file(path)

        mw.taskman.run_in_background(task, done, uses_collection=False)
