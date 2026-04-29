import time
from aqt import mw
from aqt.qt import *
from anki.utils import strip_html
from .fetcher import fetch_word_data, fetch_audio_url, fetch_image_url, download_media

class FetchProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fetching Data...")
        self.resize(550, 450)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.is_paused = False
        self.is_cancelled = False
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        # Use a monospace font for better readability
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.log_text.setFont(font)
        layout.addWidget(self.log_text)
        
        self.btn_layout = QHBoxLayout()
        self.btn_layout.addStretch()
        
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setMinimumWidth(100)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.btn_layout.addWidget(self.pause_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumWidth(100)
        self.cancel_btn.clicked.connect(self.cancel_process)
        self.btn_layout.addWidget(self.cancel_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setMinimumWidth(100)
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setVisible(False)
        self.btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(self.btn_layout)
        
    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_btn.setText("Resume")
            self.log_message("\n[INFO] ⏸ Process paused by user. Click Resume to continue.")
        else:
            self.pause_btn.setText("Pause")
            self.log_message("[INFO] ▶ Process resumed.\n")
            
    def cancel_process(self):
        self.is_cancelled = True
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.log_message("\n[INFO] 🛑 Cancelling... Please wait for the current item to finish.")
        
    def finish_process(self):
        self.pause_btn.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.close_btn.setVisible(True)
        
    def update_progress(self, current, total, success, error, skipped):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Processing: {current}/{total} | Success: {success} | Error: {error} | Skipped: {skipped}")
        
    def log_message(self, msg):
        self.log_text.append(msg)
        # Scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # Limit to 1000 blocks to prevent lag
        doc = self.log_text.document()
        if doc.blockCount() > 1000:
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor, 100)
            cursor.removeSelectedText()

def process_deck(deck_name, source_field, meaning_field, pos_field, audio_field, image_field, accent, overwrite, data_source, api_key, gemini_model, parent_window):
    
    # We use mw as parent so the dialog doesn't close when AddMissingDialog closes
    dialog = FetchProgressDialog(mw)
    dialog.show()
    
    note_ids = mw.col.find_notes(f'"deck:{deck_name}"')
    total_notes = len(note_ids)
    
    def background_worker():
        success_count = 0
        error_count = 0
        skipped_count = 0
        processed_count = 0
        
        for nid in note_ids:
            if dialog.is_cancelled:
                mw.taskman.run_on_main(lambda: dialog.log_message("[INFO] Process was cancelled."))
                break
                
            while dialog.is_paused and not dialog.is_cancelled:
                time.sleep(0.1)
                
            if dialog.is_cancelled:
                break
                
            processed_count += 1
            
            # Helper to run on main thread safely
            def update_ui_status(p=processed_count, s=success_count, e=error_count, k=skipped_count):
                dialog.update_progress(p, total_notes, s, e, k)
                
            mw.taskman.run_on_main(update_ui_status)
            
            note = mw.col.get_note(nid)
            
            if source_field not in note:
                skipped_count += 1
                continue
                
            word = strip_html(note[source_field]).strip()
            if not word:
                skipped_count += 1
                continue
                
            needs_meaning = False
            if meaning_field and meaning_field in note:
                raw_val = note[meaning_field].strip()
                current_val = strip_html(raw_val).strip()
                if overwrite or (not current_val and "<img" not in raw_val and "[sound:" not in raw_val):
                    needs_meaning = True

            needs_pos = False
            if pos_field and pos_field in note:
                raw_val = note[pos_field].strip()
                current_val = strip_html(raw_val).strip()
                if overwrite or (not current_val and "<img" not in raw_val and "[sound:" not in raw_val):
                    needs_pos = True
                    
            needs_audio = False
            if audio_field and audio_field in note:
                raw_val = note[audio_field].strip()
                current_val = strip_html(raw_val).strip()
                if overwrite or (not current_val and "<img" not in raw_val and "[sound:" not in raw_val):
                    needs_audio = True
                    
            needs_image = False
            if image_field and image_field in note:
                raw_val = note[image_field].strip()
                current_val = strip_html(raw_val).strip()
                if overwrite or (not current_val and "<img" not in raw_val and "[sound:" not in raw_val):
                    needs_image = True
            
            if not needs_meaning and not needs_pos and not needs_audio and not needs_image:
                skipped_count += 1
                mw.taskman.run_on_main(lambda w=word: dialog.log_message(f"[SKIP] '{w}' (Fields already filled)"))
                continue
                
            mw.taskman.run_on_main(lambda w=word: dialog.log_message(f"[FETCH] Requesting data for '{w}'..."))
            
            changed = False
            
            # Text Data
            if needs_meaning or needs_pos:
                data = fetch_word_data(word, data_source, api_key, gemini_model)
                if data:
                    if needs_meaning and data.get('meaning'):
                        note[meaning_field] = data['meaning']
                        changed = True
                    if needs_pos and data.get('partOfSpeech'):
                        note[pos_field] = data['partOfSpeech']
                        changed = True
            
            # Audio Data
            if needs_audio:
                audio_url = fetch_audio_url(word, accent)
                if audio_url:
                    mw.taskman.run_on_main(lambda: dialog.log_message(f"  -> Downloading audio..."))
                    audio_tag = download_media(audio_url, word, True, mw)
                    if audio_tag:
                        note[audio_field] = audio_tag
                        changed = True
                        
            # Image Data
            if needs_image:
                image_url = fetch_image_url(word)
                if image_url:
                    mw.taskman.run_on_main(lambda: dialog.log_message(f"  -> Downloading image..."))
                    image_tag = download_media(image_url, word, False, mw)
                    if image_tag:
                        note[image_field] = image_tag
                        changed = True
            
            if not changed:
                error_count += 1
                mw.taskman.run_on_main(lambda w=word: dialog.log_message(f"[ERROR] ❌ Failed to fetch new data for '{w}'"))
                continue
                
            success_count += 1
            # Safely update DB on main thread
            def save_note(n=note):
                mw.col.update_note(n)
            mw.taskman.run_on_main(save_note)
            mw.taskman.run_on_main(lambda w=word: dialog.log_message(f"[SUCCESS] ✅ Updated '{w}'"))
                
        # Finish routine
        def on_finish():
            dialog.update_progress(processed_count, total_notes, success_count, error_count, skipped_count)
            dialog.log_message(f"\n--- FINISHED ---")
            dialog.log_message(f"Total processed: {processed_count}/{total_notes}")
            dialog.log_message(f"Success: {success_count}")
            dialog.log_message(f"Error: {error_count}")
            dialog.log_message(f"Skipped: {skipped_count}")
            dialog.finish_process()
            mw.reset() # Refresh Anki UI
            
        mw.taskman.run_on_main(on_finish)

    mw.taskman.run_in_background(background_worker)
