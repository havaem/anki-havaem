from aqt import mw
from aqt.qt import *
from aqt.utils import askUser, showWarning

from . import config, tasks
from .providers import KEY_LABELS
from .theme import Group, Segmented, Switch
from .ui_common import TEXT_SEG, AudioOptions, FieldMapper, Page

SCOPE_FOOTER = "Subdecks are included."


class EnrichPage(Page):
    def __init__(self):
        super().__init__(
            "Add Missing Fields",
            "Fill empty fields on existing cards — meaning, IPA, examples, audio, images.",
        )
        cfg = config.load()

        # Notes -------------------------------------------------------------
        self.scope = Group("Notes", SCOPE_FOOTER)
        self.deck = QComboBox()
        self.deck.setMaxVisibleItems(20)
        self.deck.addItems(sorted(d.name for d in mw.col.decks.all_names_and_ids()))
        self.deck.setCurrentIndex(
            max(self.deck.findText(cfg["last_deck"] or mw.col.decks.current()["name"]), 0)
        )
        self.scope.add_row("Deck", self.deck)
        self.extra = QLineEdit()
        self.extra.setPlaceholderText("tag:vocab -is:suspended")
        self.extra.setClearButtonEnabled(True)
        self.scope.add_row("Search filter", self.extra, sublabel="Optional", expand=True)
        self.scan_btn = QPushButton("Check")
        self.scope.add_row("What's missing?", self.scan_btn, sublabel="Counts notes · no network")
        self.body.addWidget(self.scope)

        # Fields ------------------------------------------------------------
        fields = Group(
            "Fields",
            "Pick the field that holds the word, then the fields to fill. “None” skips a field.",
        )
        self.mapper = FieldMapper(labels={"word": "Word"}, hints={"word": "Read from this field"})
        self.mapper.add_to(fields)
        self.body.addWidget(fields)

        # Text source -------------------------------------------------------
        text = Group("Text source", "Used for IPA, part of speech, meaning, examples and so on.")
        self.source = Segmented(TEXT_SEG)
        self.source.set_value(cfg["enrich_source"])
        text.add_row("Source", self.source)
        self.fill_gaps = Switch(bool(cfg["gemini_fill_gaps"]))
        text.add_row("Fill gaps with Gemini", self.fill_gaps, sublabel="Needs an API key")
        self.body.addWidget(text)

        # Audio -------------------------------------------------------------
        audio = Group("Audio", "Used when an Audio field is selected above.")
        self.audio = AudioOptions()
        self.audio.add_to(audio)
        self.body.addWidget(audio)

        # Options -----------------------------------------------------------
        opts = Group("Options", "Existing content is kept unless this is on.")
        self.overwrite = Switch(bool(cfg["overwrite"]))
        opts.add_row("Overwrite existing content", self.overwrite)
        self.body.addWidget(opts)

        self.start_btn = QPushButton("Start")
        self.add_primary(self.start_btn)

        self.deck.currentTextChanged.connect(self.on_deck_changed)
        self.mapper.changed.connect(self.on_mapping_changed)
        self.source.valueChanged.connect(lambda v: config.update(enrich_source=v))
        self.fill_gaps.toggled.connect(lambda v: config.update(gemini_fill_gaps=v))
        self.overwrite.toggled.connect(lambda v: config.update(overwrite=v))
        self.scan_btn.clicked.connect(self.scan)
        self.start_btn.clicked.connect(self.start)
        self.on_deck_changed(self.deck.currentText())

    # ---- state ------------------------------------------------------------

    def refresh(self) -> None:
        """Called when the page is shown: pick up changes from other pages."""
        self.audio.reload()
        self.fill_gaps.setChecked(bool(config.get("gemini_fill_gaps")))

    def on_deck_changed(self, deck: str) -> None:
        if not deck:
            return
        config.update(last_deck=deck)
        self.mapper.set_fields(tasks.deck_field_names(deck), config.get_mapping(f"deck:{deck}"))
        self.scope.set_footer(SCOPE_FOOTER)

    def on_mapping_changed(self) -> None:
        deck = self.deck.currentText()
        if deck:
            config.save_mapping(f"deck:{deck}", self.mapper.raw_mapping())
        self.scope.set_footer(SCOPE_FOOTER)

    def _query(self) -> str:
        return tasks.deck_search(self.deck.currentText(), self.extra.text())

    def _validate(self):
        mapping = self.mapper.mapping()
        if "word" not in mapping:
            showWarning("Choose the field that contains the word.", parent=self)
            return None
        targets = {k: v for k, v in mapping.items() if k != "word"}
        if not targets:
            showWarning("Choose at least one field to fill.", parent=self)
            return None
        if self.source.value() == "gemini" and not config.get("gemini_api_key").strip():
            showWarning("Add your Gemini API key in Settings first.", parent=self)
            return None
        return mapping["word"], targets

    # ---- actions ----------------------------------------------------------

    def scan(self) -> None:
        checked = self._validate()
        if not checked:
            return
        word_field, targets = checked
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            res = tasks.scan_notes(self._query(), word_field, targets, self.overwrite.isChecked())
        except Exception as e:  # bad search syntax, etc.
            showWarning(str(e), parent=self)
            return
        finally:
            QApplication.restoreOverrideCursor()
        parts = [f"{KEY_LABELS[k].lower()} {n}" for k, n in res["by_key"].items()]
        text = f"{res['total']} notes · {res['actionable']} need data"
        if parts:
            text += f" ({', '.join(parts)})"
        if res["no_word"]:
            text += f" · {res['no_word']} without a word"
        self.scope.set_footer(text)

    def start(self) -> None:
        checked = self._validate()
        if not checked:
            return
        word_field, targets = checked
        if self.overwrite.isChecked() and not askUser(
            "“Overwrite” is on: existing content in the selected fields will be replaced.\n\nContinue?",
            parent=self,
            defaultno=True,
        ):
            return
        try:
            query = self._query()
        except Exception as e:
            showWarning(str(e), parent=self)
            return
        tasks.start_enrich(
            self.window(), query, word_field, targets,
            self.source.value(), self.overwrite.isChecked(),
        )
