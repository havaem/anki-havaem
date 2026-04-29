import os
import json
from aqt import mw
from aqt.qt import *
from .processor import process_deck
from .creator import create_words

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except: pass
    return {"gemini_api_key": "", "gemini_model": "gemini-2.5-flash", "last_deck": "", "last_note_type": ""}

def save_config(config):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f)
    except: pass

class SettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = load_config()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        group = QGroupBox("AI Configuration")
        group.setStyleSheet("QGroupBox { font-weight: bold; }")
        form = QFormLayout(group)
        form.setSpacing(10)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setText(self.config.get("gemini_api_key", ""))
        self.api_key_input.setPlaceholderText("Enter your Gemini API key here...")
        form.addRow("Gemini API Key:", self.api_key_input)
        
        self.gemini_model_combo = QComboBox()
        self.gemini_model_combo.addItems([
            "gemini-3-pro",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ])
        self.gemini_model_combo.setCurrentText(self.config.get("gemini_model", "gemini-2.5-flash"))
        form.addRow("Gemini Model:", self.gemini_model_combo)
        
        layout.addWidget(group)
        
        save_btn = QPushButton("Save Settings")
        save_btn.setMinimumHeight(40)
        save_btn.setStyleSheet("font-weight: bold;")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        layout.addStretch()

    def save_settings(self):
        # Reload to avoid overwriting dynamically saved state
        current_config = load_config()
        current_config["gemini_api_key"] = self.api_key_input.text().strip()
        current_config["gemini_model"] = self.gemini_model_combo.currentText()
        save_config(current_config)
        QMessageBox.information(self, "Success", "Settings saved successfully!")


class AddMissingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Source Settings Group ---
        source_group = QGroupBox("1. Data Source & Deck Settings")
        source_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        source_form = QFormLayout()
        source_form.setSpacing(10)
        
        self.source_api_combo = QComboBox()
        self.source_api_combo.addItem("Cambridge Dictionary", "cambridge")
        self.source_api_combo.addItem("Free Dictionary API", "free")
        self.source_api_combo.addItem("AI (Gemini)", "gemini")
        self.source_api_combo.setToolTip("Select the API to fetch data from.")
        source_form.addRow("Data Source:", self.source_api_combo)
        
        self.deck_combo = QComboBox()
        self.deck_combo.setToolTip("Select the Anki deck to process.")
        self.deck_combo.setMaxVisibleItems(15)
        self.populate_decks()
        
        # Set last selected deck
        config = load_config()
        last_deck = config.get("last_deck", "")
        if last_deck:
            self.deck_combo.setCurrentText(last_deck)
            
        source_form.addRow("Select Deck:", self.deck_combo)
        
        self.source_combo = QComboBox()
        self.source_combo.setToolTip("Select the field that contains the target word.")
        source_form.addRow("Word Field (Source):", self.source_combo)
        
        source_group.setLayout(source_form)
        main_layout.addWidget(source_group)
        
        # --- Target Settings Group ---
        target_group = QGroupBox("2. Target Fields (Where to save data)")
        target_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        target_form = QFormLayout()
        target_form.setSpacing(10)
        
        self.meaning_combo = QComboBox()
        self.meaning_combo.setToolTip("Select the field to store the meaning.")
        target_form.addRow("Meaning Field:", self.meaning_combo)
        
        self.pos_combo = QComboBox()
        self.pos_combo.setToolTip("Select the field to store the part of speech.")
        target_form.addRow("Part of Speech Field:", self.pos_combo)
        
        self.audio_combo = QComboBox()
        self.audio_combo.setToolTip("Select the field to store the pronunciation audio.")
        target_form.addRow("Audio Field:", self.audio_combo)
        
        self.image_combo = QComboBox()
        self.image_combo.setToolTip("Select the field to store the illustration image.")
        target_form.addRow("Image Field:", self.image_combo)
        
        target_group.setLayout(target_form)
        main_layout.addWidget(target_group)
        
        # --- Options Group ---
        options_group = QGroupBox("3. Options")
        options_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        options_layout = QVBoxLayout()
        options_layout.setSpacing(10)
        
        accent_layout = QHBoxLayout()
        accent_layout.addWidget(QLabel("Pronunciation Accent:"))
        self.accent_combo = QComboBox()
        self.accent_combo.addItems(["US", "UK", "Any"])
        config = load_config()
        self.accent_combo.setCurrentText(config.get("audio_accent", "US"))
        self.accent_combo.currentTextChanged.connect(self.save_accent)
        accent_layout.addWidget(self.accent_combo)
        accent_layout.addStretch()
        options_layout.addLayout(accent_layout)
        
        self.overwrite_checkbox = QCheckBox("Overwrite existing values (if already filled)")
        self.overwrite_checkbox.setChecked(False)
        self.overwrite_checkbox.setToolTip("If checked, existing data in target fields will be replaced with new data.")
        options_layout.addWidget(self.overwrite_checkbox)
        
        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)
        
        # Connect deck change signal to auto-save and update fields
        self.deck_combo.currentTextChanged.connect(self.on_deck_changed)
        
        main_layout.addStretch()
        
        # --- Buttons ---
        self.start_btn = QPushButton("Start Processing")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.start_btn.clicked.connect(self.on_process_clicked)
        main_layout.addWidget(self.start_btn)
        
        # Initialize
        if self.deck_combo.count() > 0:
            self.on_deck_changed(self.deck_combo.currentText())

    def populate_decks(self):
        decks = mw.col.decks.all_names()
        self.deck_combo.addItems(decks)
        
    def save_accent(self, text):
        config = load_config()
        config["audio_accent"] = text
        save_config(config)
        
    def on_deck_changed(self, deck_name):
        # Auto-save deck selection
        config = load_config()
        config["last_deck"] = deck_name
        save_config(config)
        
        self.source_combo.clear()
        self.meaning_combo.clear()
        self.pos_combo.clear()
        self.audio_combo.clear()
        self.image_combo.clear()
        
        self.meaning_combo.addItem("<None>")
        self.pos_combo.addItem("<None>")
        self.audio_combo.addItem("<None>")
        self.image_combo.addItem("<None>")
        
        deck_id = mw.col.decks.id_for_name(deck_name)
        if deck_id is None: return
        
        card_ids = mw.col.find_cards(f'"deck:{deck_name}"')
        fields = set()
        for cid in card_ids[:50]:
            card = mw.col.get_card(cid)
            note = card.note()
            fields.update(note.keys())
            
        fields_list = sorted(list(fields))
        self.source_combo.addItems(fields_list)
        self.meaning_combo.addItems(fields_list)
        self.pos_combo.addItems(fields_list)
        self.audio_combo.addItems(fields_list)
        self.image_combo.addItems(fields_list)

    def on_process_clicked(self):
        deck_name = self.deck_combo.currentText()
        source_field = self.source_combo.currentText()
        meaning_field = self.meaning_combo.currentText()
        pos_field = self.pos_combo.currentText()
        audio_field = self.audio_combo.currentText()
        image_field = self.image_combo.currentText()
        accent = self.accent_combo.currentText()
        overwrite = self.overwrite_checkbox.isChecked()
        
        data_source = self.source_api_combo.currentData()
        
        config = load_config()
        api_key = config.get("gemini_api_key", "").strip()
        gemini_model = config.get("gemini_model", "gemini-2.5-flash")
        
        if data_source == "gemini" and not api_key:
            QMessageBox.warning(self, "Error", "Gemini API Key is missing! Please set it in the Settings tab.")
            return
        
        if meaning_field == "<None>": meaning_field = None
        if pos_field == "<None>": pos_field = None
        if audio_field == "<None>": audio_field = None
        if image_field == "<None>": image_field = None
        
        if not source_field:
            QMessageBox.warning(self, "Error", "Please select a Word field!")
            return
            
        if not meaning_field and not pos_field and not audio_field and not image_field:
            QMessageBox.warning(self, "Error", "Please select at least one target field!")
            return
            
        process_deck(deck_name, source_field, meaning_field, pos_field, audio_field, image_field, accent, overwrite, data_source, api_key, gemini_model, mw)


class SmartWordCreatorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mapping_combos = {}
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        config = load_config()
        
        # --- Settings Group ---
        settings_group = QGroupBox("1. Target Deck & Note Type")
        settings_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        settings_form = QFormLayout()
        settings_form.setSpacing(10)
        
        self.deck_combo = QComboBox()
        self.deck_combo.setMaxVisibleItems(15)
        self.populate_decks()
        
        last_deck = config.get("last_deck", "")
        if last_deck:
            self.deck_combo.setCurrentText(last_deck)
        self.deck_combo.currentTextChanged.connect(self.on_deck_changed)
        
        settings_form.addRow("Target Deck:", self.deck_combo)
        
        self.model_combo = QComboBox()
        self.model_combo.setMaxVisibleItems(15)
        self.populate_models()
        
        last_note_type = config.get("last_note_type", "")
        if last_note_type:
            self.model_combo.setCurrentText(last_note_type)
            
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        settings_form.addRow("Note Type:", self.model_combo)
        
        settings_group.setLayout(settings_form)
        main_layout.addWidget(settings_group)
        
        # --- Field Mapping Group ---
        self.mapping_group = QGroupBox("2. Field Mapping (Map generated data to Anki fields)")
        self.mapping_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        
        mapping_layout = QGridLayout()
        mapping_layout.setSpacing(10)
        
        self.data_keys = [
            ('word', 'Word'),
            ('ipa', 'IPA'),
            ('pos', 'Part of Speech'),
            ('meaning', 'Meaning'),
            ('sentence', 'Sentence'),
            ('vi_sentence', 'Vietnamese Sentence'),
            ('synonyms', 'Synonyms'),
            ('mnemonic', 'Mnemonic'),
            ('audio', 'Audio'),
            ('image', 'Image')
        ]
        
        row = 0
        col = 0
        for key, label in self.data_keys:
            mapping_layout.addWidget(QLabel(f"{label}:"), row, col)
            combo = QComboBox()
            self.mapping_combos[key] = combo
            mapping_layout.addWidget(combo, row, col + 1)
            row += 1
            if row > 3:
                row = 0
                col += 2
                
        self.mapping_group.setLayout(mapping_layout)
        main_layout.addWidget(self.mapping_group)
        
        # --- Input Group ---
        input_group = QGroupBox("3. Input Data")
        input_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        input_layout = QVBoxLayout()
        
        mode_layout = QHBoxLayout()
        self.radio_generate = QRadioButton("Auto-Generate via Gemini (Paste list of words)")
        self.radio_import = QRadioButton("Import Custom Data (Paste TSV/Pipes: Word | IPA | POS ...)")
        self.radio_generate.setChecked(True)
        mode_layout.addWidget(self.radio_generate)
        mode_layout.addWidget(self.radio_import)
        input_layout.addLayout(mode_layout)
        
        accent_layout = QHBoxLayout()
        accent_layout.addWidget(QLabel("Pronunciation Accent:"))
        self.accent_combo = QComboBox()
        self.accent_combo.addItems(["US", "UK", "Any"])
        self.accent_combo.setCurrentText(config.get("audio_accent", "US"))
        self.accent_combo.currentTextChanged.connect(self.save_accent)
        accent_layout.addWidget(self.accent_combo)
        accent_layout.addStretch()
        input_layout.addLayout(accent_layout)
        
        self.input_text = QTextEdit()
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.input_text.setFont(font)
        input_layout.addWidget(self.input_text)
        
        self.radio_generate.toggled.connect(self.on_mode_changed)
        self.on_mode_changed()
        
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group, 1) # Give it stretch
        
        # --- Buttons ---
        self.start_btn = QPushButton("Start Creating")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.start_btn.clicked.connect(self.on_process_clicked)
        main_layout.addWidget(self.start_btn)
        
        # Initialize
        if self.model_combo.count() > 0:
            self.on_model_changed(self.model_combo.currentText())

    def on_mode_changed(self):
        is_generate = getattr(self, 'radio_generate', None) and self.radio_generate.isChecked()
        if hasattr(self, 'mapping_group'):
            self.mapping_group.setVisible(is_generate)
            
        if hasattr(self, 'input_text'):
            if is_generate:
                self.input_text.setPlaceholderText("Generate Mode:\nEnter one word per line.\n\nGenerated data will be mapped to fields according to your mapping settings.")
            else:
                self.input_text.setPlaceholderText("Import Mode:\nPaste TSV or Pipe (|) separated data.\n\nEach column will automatically map to the Note Type's fields in sequential order\n(Column 1 -> Field 1, Column 2 -> Field 2, etc.)")

    def save_accent(self, text):
        config = load_config()
        config["audio_accent"] = text
        save_config(config)

    def populate_decks(self):
        decks = mw.col.decks.all_names()
        self.deck_combo.addItems(decks)

    def populate_models(self):
        models = mw.col.models.all_names()
        self.model_combo.addItems(models)
        
    def on_deck_changed(self, deck_name):
        config = load_config()
        config["last_deck"] = deck_name
        save_config(config)
        
    def on_model_changed(self, model_name):
        config = load_config()
        config["last_note_type"] = model_name
        save_config(config)
        
        model = mw.col.models.by_name(model_name)
        if not model: return
        
        field_names = [f['name'] for f in model['flds']]
        
        for key, combo in self.mapping_combos.items():
            combo.clear()
            combo.addItem("<None>")
            combo.addItems(field_names)
            
            # Auto-select if name roughly matches
            for field in field_names:
                if key.lower() in field.lower() or field.lower() in key.lower():
                    combo.setCurrentText(field)
                    break
                # Special cases
                if key == 'vi_sentence' and ('vietnamese' in field.lower() or 'vi ' in field.lower() or 'dịch' in field.lower()):
                    combo.setCurrentText(field)
                    break
                if key == 'pos' and 'speech' in field.lower() or 'loại từ' in field.lower() or 'từ loại' in field.lower():
                    combo.setCurrentText(field)
                    break

    def on_process_clicked(self):
        deck_name = self.deck_combo.currentText()
        model_name = self.model_combo.currentText()
        input_data = self.input_text.toPlainText().strip()
        
        config = load_config()
        api_key = config.get("gemini_api_key", "").strip()
        gemini_model = config.get("gemini_model", "gemini-2.5-flash")
        
        # Collect mapping
        field_mapping = {}
        for key, combo in self.mapping_combos.items():
            target = combo.currentText()
            if target != "<None>":
                field_mapping[key] = target
        
        mode = "generate" if self.radio_generate.isChecked() else "import"
        
        if not input_data:
            QMessageBox.warning(self, "Error", "Please provide input data!")
            return
            
        if mode == "generate" and not api_key:
            QMessageBox.warning(self, "Error", "Gemini API Key is missing! Please set it in the Settings tab.")
            return
            
        accent = self.accent_combo.currentText()
        create_words(deck_name, model_name, field_mapping, mode, input_data, api_key, gemini_model, accent)


class HavaemMainDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HAVAEM Tool Hub")
        self.resize(850, 600)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setMinimumWidth(200)
        self.sidebar.setStyleSheet("""
            QListWidget {
                font-size: 14px;
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 5px;
            }
            QListWidget::item:selected {
                background-color: #0078D7;
                color: white;
            }
        """)
        
        # Add items to sidebar
        item1 = QListWidgetItem("Add Missing Fields")
        item2 = QListWidgetItem("Smart Word Creator")
        item3 = QListWidgetItem("Settings")
        
        self.sidebar.addItem(item1)
        self.sidebar.addItem(item2)
        self.sidebar.addItem(item3)
        
        # Content Stack
        self.stack = QStackedWidget()
        
        self.add_missing_widget = AddMissingWidget()
        self.stack.addWidget(self.add_missing_widget)
        
        self.word_creator_widget = SmartWordCreatorWidget()
        self.stack.addWidget(self.word_creator_widget)
        
        self.settings_widget = SettingsWidget()
        self.stack.addWidget(self.settings_widget)
        
        # Connect sidebar to stack
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)
        
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.stack)
        
        splitter.setSizes([200, 650])
        main_layout.addWidget(splitter)

def show_dialog():
    dialog = HavaemMainDialog(mw)
    dialog.exec()
