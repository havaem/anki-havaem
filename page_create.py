from aqt import mw
from aqt.qt import *
from aqt.utils import showWarning

from . import config, tasks
from .theme import Group, Segmented, Switch
from .ui_common import TEXT_SEG, AudioOptions, FieldMapper, Page

MODES = [("Word list", "generate"), ("Import data", "import")]


class CreatorPage(Page):
    def __init__(self):
        super().__init__(
            "Smart Word Creator",
            "Paste a list of words and get finished cards — or import your own table.",
        )
        cfg = config.load()

        # Destination -------------------------------------------------------
        dest = Group("Destination")
        self.deck = QComboBox()
        self.deck.setMaxVisibleItems(20)
        self.deck.addItems(sorted(d.name for d in mw.col.decks.all_names_and_ids()))
        self.deck.setCurrentIndex(
            max(self.deck.findText(cfg["last_deck"] or mw.col.decks.current()["name"]), 0)
        )
        dest.add_row("Deck", self.deck)
        self.notetype = QComboBox()
        self.notetype.setMaxVisibleItems(20)
        self.notetype.addItems(sorted(n.name for n in mw.col.models.all_names_and_ids()))
        self.notetype.setCurrentIndex(
            max(self.notetype.findText(cfg["last_note_type"] or mw.col.models.current()["name"]), 0)
        )
        dest.add_row("Note type", self.notetype)
        self.tag = QLineEdit(cfg["new_note_tag"])
        self.tag.setPlaceholderText("Optional")
        dest.add_row("Tag new notes", self.tag, expand=True)
        self.skip_dups = Switch(bool(cfg["skip_duplicates"]))
        dest.add_row(
            "Skip existing words", self.skip_dups,
            sublabel="Checks the first field of the note type",
        )
        self.body.addWidget(dest)

        # Words -------------------------------------------------------------
        self.words = Group("Words")
        self.mode = Segmented(MODES)
        self.words.add_row("Input", self.mode)
        self.text = QPlainTextEdit()
        self.text.setMinimumHeight(150)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.text.setFont(mono)
        self.words.add_widget(self.text, margins=(12, 10, 12, 10))
        self.body.addWidget(self.words)

        # Fields ------------------------------------------------------------
        self.fields_group = Group(
            "Fields", "Which note type field receives each piece of data. “None” skips it."
        )
        self.mapper = FieldMapper()
        self.mapper.add_to(self.fields_group)
        self.body.addWidget(self.fields_group)

        # Text source -------------------------------------------------------
        self.text_group = Group("Text source")
        self.source = Segmented(TEXT_SEG)
        self.source.set_value(cfg["create_source"])
        self.text_group.add_row("Source", self.source)
        self.fill_gaps = Switch(bool(cfg["gemini_fill_gaps"]))
        self.text_group.add_row("Fill gaps with Gemini", self.fill_gaps, sublabel="Needs an API key")
        self.body.addWidget(self.text_group)

        # Audio -------------------------------------------------------------
        audio = Group("Audio", "Used when an Audio field is selected above.")
        self.audio = AudioOptions()
        self.audio.add_to(audio)
        self.body.addWidget(audio)

        self.start_btn = QPushButton("Create Cards")
        self.add_primary(self.start_btn)

        self.deck.currentTextChanged.connect(lambda d: d and config.update(last_deck=d))
        self.notetype.currentTextChanged.connect(self.on_notetype_changed)
        self.mapper.changed.connect(self.on_mapping_changed)
        self.mode.valueChanged.connect(lambda _: self.on_mode_changed())
        self.text.textChanged.connect(self.update_counter)
        self.source.valueChanged.connect(lambda v: config.update(create_source=v))
        self.fill_gaps.toggled.connect(lambda v: config.update(gemini_fill_gaps=v))
        self.skip_dups.toggled.connect(lambda v: config.update(skip_duplicates=v))
        self.tag.editingFinished.connect(lambda: config.update(new_note_tag=self.tag.text().strip()))
        self.start_btn.clicked.connect(self.start)

        self.on_notetype_changed(self.notetype.currentText())
        self.on_mode_changed()

    # ---- state ------------------------------------------------------------

    def refresh(self) -> None:
        self.audio.reload()
        self.fill_gaps.setChecked(bool(config.get("gemini_fill_gaps")))

    @property
    def is_generate(self) -> bool:
        return self.mode.value() == "generate"

    def _field_names(self) -> list:
        model = mw.col.models.by_name(self.notetype.currentText())
        return [f["name"] for f in model["flds"]] if model else []

    def on_notetype_changed(self, name: str) -> None:
        if not name:
            return
        config.update(last_note_type=name)
        self.mapper.set_fields(self._field_names(), config.get_mapping(f"nt:{name}"))
        self.on_mode_changed()

    def on_mapping_changed(self) -> None:
        name = self.notetype.currentText()
        if name:
            config.save_mapping(f"nt:{name}", self.mapper.raw_mapping())

    def on_mode_changed(self) -> None:
        generate = self.is_generate
        self.mapper.set_enabled_keys(None if generate else {"audio", "image"})
        self.text_group.setEnabled(generate)
        if generate:
            self.text.setPlaceholderText("glide\nresilient\nlook forward to")
        else:
            self.text.setPlaceholderText("glide | /ɡlaɪd/ | verb | to move smoothly | …")
        self.update_counter()

    def update_counter(self) -> None:
        n = len([ln for ln in self.text.toPlainText().splitlines() if ln.strip()])
        if self.is_generate:
            self.words.set_footer(f"One word or phrase per line · {n} {'word' if n == 1 else 'words'}")
        else:
            order = ", ".join(f"{i} {name}" for i, name in enumerate(self._field_names(), 1))
            self.words.set_footer(
                f"One note per line; columns separated by a tab or “|” fill the fields in order "
                f"({order}). Audio and image are fetched for column 1 when their field is chosen "
                f"below. · {n} {'row' if n == 1 else 'rows'}"
            )

    # ---- action -----------------------------------------------------------

    def start(self) -> None:
        text = self.text.toPlainText().strip()
        if not text:
            showWarning("Paste some words (or rows) first.", parent=self)
            return

        mapping = self.mapper.mapping()
        source = self.source.value()
        if self.is_generate:
            if "word" not in mapping:
                showWarning("Choose the field that receives the word.", parent=self)
                return
            if source == "gemini" and not config.get("gemini_api_key").strip():
                showWarning("Add your Gemini API key in Settings first.", parent=self)
                return
        else:
            mapping = {k: v for k, v in mapping.items() if k in ("audio", "image")}

        tasks.start_create(
            self.window(),
            self.deck.currentText(),
            self.notetype.currentText(),
            mapping,
            "generate" if self.is_generate else "import",
            text,
            source,
            self.skip_dups.isChecked(),
            self.tag.text(),
        )
