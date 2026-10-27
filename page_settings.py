from aqt import mw
from aqt.qt import *

from . import config, providers
from .theme import Group, Segmented
from .ui_common import Page

MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-3-pro",
]
WORKER_CHOICES = [(str(n), n) for n in (1, 2, 3, 4, 6, 8)]


class SettingsPage(Page):
    """Changes are saved as you make them."""

    def __init__(self):
        super().__init__("Settings", "Gemini is optional — dictionaries and audio work without it.")
        cfg = config.load()

        gem = Group("Gemini AI", "Get a free key at aistudio.google.com/app/apikey.")
        key_box = QWidget()
        key_lay = QHBoxLayout(key_box)
        key_lay.setContentsMargins(0, 0, 0, 0)
        key_lay.setSpacing(8)
        self.key = QLineEdit(cfg["gemini_api_key"])
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Paste your API key")
        self.show_key = QPushButton("Show")
        self.show_key.setCheckable(True)
        key_lay.addWidget(self.key, 1)
        key_lay.addWidget(self.show_key)
        gem.add_row("API key", key_box, expand=True)

        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItems(MODELS)
        self.model.setCurrentText(cfg["gemini_model"])
        gem.add_row("Model", self.model)

        self.language = QLineEdit(cfg["translation_language"])
        self.language.setPlaceholderText("Vietnamese")
        gem.add_row("Translate sentences to", self.language, expand=True)

        test_box = QWidget()
        test_lay = QHBoxLayout(test_box)
        test_lay.setContentsMargins(0, 0, 0, 0)
        test_lay.setSpacing(10)
        self.test_result = QLabel()
        self.test_result.setObjectName("secondary")
        self.test_btn = QPushButton("Test")
        test_lay.addWidget(self.test_result)
        test_lay.addWidget(self.test_btn)
        gem.add_row("Connection", test_box)
        self.body.addWidget(gem)

        perf = Group(
            "Performance",
            "How many words are fetched at the same time. Lower it if you hit rate limits.",
        )
        self.workers = Segmented(WORKER_CHOICES)
        self.workers.set_value(min((n for _, n in WORKER_CHOICES), key=lambda n: abs(n - int(cfg["workers"]))))
        perf.add_row("Parallel requests", self.workers)
        self.body.addWidget(perf)
        self.body.addStretch()

        self.show_key.toggled.connect(self._toggle_key)
        self.key.editingFinished.connect(self.save)
        self.language.editingFinished.connect(self.save)
        self.model.currentTextChanged.connect(lambda _: self.save())
        self.workers.valueChanged.connect(lambda _: self.save())
        self.test_btn.clicked.connect(self.test)

    def _toggle_key(self, shown: bool) -> None:
        self.key.setEchoMode(QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password)
        self.show_key.setText("Hide" if shown else "Show")

    def save(self) -> None:
        config.update(
            gemini_api_key=self.key.text().strip(),
            gemini_model=self.model.currentText().strip() or "gemini-2.5-flash",
            translation_language=self.language.text().strip() or "Vietnamese",
            workers=self.workers.value(),
        )

    def test(self) -> None:
        self.save()
        key, model = self.key.text().strip(), self.model.currentText().strip()
        if not key:
            self.test_result.setText("Enter an API key first")
            return
        self.test_btn.setEnabled(False)
        self.test_result.setText("Testing…")

        def done(future):
            self.test_btn.setEnabled(True)
            try:
                future.result()
                self.test_result.setText(f"✔ Works with {model}")
            except Exception as e:  # noqa: BLE001
                self.test_result.setText(f"✘ {str(e)[:70]}")

        mw.taskman.run_in_background(
            lambda: providers.test_gemini(key, model), done, uses_collection=False
        )
