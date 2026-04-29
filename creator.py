import time
from aqt import mw
from aqt.qt import *
from anki.utils import strip_html
from .fetcher import generate_full_word_data, fetch_audio_url, fetch_image_url, download_media
from .processor import FetchProgressDialog

def create_words(deck_name, model_name, field_mapping, mode, input_text, api_key, gemini_model, accent="US"):
    
    dialog = FetchProgressDialog(mw)
    dialog.setWindowTitle("Smart Word Creator")
    dialog.show()
    
    # Pre-process input
    if mode == "generate":
        lines = [line.strip() for line in input_text.strip().split('\n') if line.strip()]
        total_items = len(lines)
    else:
        lines = [line.strip() for line in input_text.strip().split('\n') if line.strip()]
        total_items = len(lines)
        
    if total_items == 0:
        dialog.log_message("[ERROR] No input provided.")
        dialog.finish_process()
        return

    model = mw.col.models.by_name(model_name)
    if not model:
        dialog.log_message(f"[ERROR] Note Type '{model_name}' not found.")
        dialog.finish_process()
        return
        
    deck_id = mw.col.decks.id_for_name(deck_name)
    
    def background_worker():
        success_count = 0
        error_count = 0
        skipped_count = 0
        processed_count = 0
        
        for line in lines:
            if dialog.is_cancelled:
                mw.taskman.run_on_main(lambda: dialog.log_message("[INFO] 🛑 Process was cancelled."))
                break
                
            while dialog.is_paused and not dialog.is_cancelled:
                time.sleep(0.1)
                
            if dialog.is_cancelled:
                break
                
            processed_count += 1
            
            def update_ui_status(p=processed_count, s=success_count, e=error_count, k=skipped_count):
                dialog.update_progress(p, total_items, s, e, k)
                
            mw.taskman.run_on_main(update_ui_status)
            
            if mode == "generate":
                word = line
                mw.taskman.run_on_main(lambda w=word: dialog.log_message(f"[FETCH] Generating data for '{w}' via Gemini..."))
                data = generate_full_word_data(word, api_key, gemini_model)
                if not data or not data.get('word'):
                    error_count += 1
                    mw.taskman.run_on_main(lambda w=word: dialog.log_message(f"[ERROR] ❌ Failed to generate data for '{w}'"))
                    continue
                    
                # Fetch Audio
                if field_mapping.get('audio'):
                    mw.taskman.run_on_main(lambda w=word: dialog.log_message(f"[FETCH] Getting audio for '{w}'..."))
                    audio_url = fetch_audio_url(word, accent)
                    if audio_url:
                        data['audio'] = download_media(audio_url, word, True, mw)
                
                # Fetch Image
                if field_mapping.get('image'):
                    mw.taskman.run_on_main(lambda w=word: dialog.log_message(f"[FETCH] Getting image for '{w}'..."))
                    image_url = fetch_image_url(word)
                    if image_url:
                        data['image'] = download_media(image_url, word, False, mw)
            else:
                # Import mode (TSV or pipe separated)
                parts = line.split('\t')
                if len(parts) < 2:
                    parts = line.split('|')
                
                parts = [p.strip() for p in parts]
                
                if len(parts) == 0:
                    error_count += 1
                    mw.taskman.run_on_main(lambda l=line: dialog.log_message(f"[ERROR] ❌ Invalid format: '{l[:20]}...'"))
                    continue
                    
                data = {'parts': parts, 'word': parts[0]}
                
                mw.taskman.run_on_main(lambda w=data['word']: dialog.log_message(f"[IMPORT] Processing '{w}'..."))
                
            # Create Note
            def create_note_on_main(d=data):
                try:
                    note = mw.col.new_note(model)
                    
                    if mode == "generate":
                        for key, val in d.items():
                            if key == 'parts': continue
                            target_field = field_mapping.get(key)
                            if target_field and target_field in note:
                                note[target_field] = str(val)
                    else:
                        # Sequential mapping for import mode
                        field_names = [f['name'] for f in model['flds']]
                        parts = d.get('parts', [])
                        for i, val in enumerate(parts):
                            if i < len(field_names):
                                note[field_names[i]] = str(val)
                            
                    mw.col.add_note(note, deck_id)
                    return True
                except Exception as e:
                    print(f"Error adding note: {e}")
                    return False
                    
            mw.taskman.run_on_main(create_note_on_main)
            
            success_count += 1
            word_str = data.get('word', 'Unknown')
            mw.taskman.run_on_main(lambda w=word_str: dialog.log_message(f"[SUCCESS] ✅ Created card for '{w}'"))

        # Finish routine
        def on_finish():
            dialog.update_progress(processed_count, total_items, success_count, error_count, skipped_count)
            dialog.log_message(f"\n--- FINISHED ---")
            dialog.log_message(f"Total processed: {processed_count}/{total_items}")
            dialog.log_message(f"Success: {success_count}")
            dialog.log_message(f"Error: {error_count}")
            dialog.log_message(f"Skipped: {skipped_count}")
            dialog.finish_process()
            mw.reset() # Refresh Anki UI
            
        mw.taskman.run_on_main(on_finish)

    mw.taskman.run_in_background(background_worker)
