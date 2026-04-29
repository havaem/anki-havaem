import urllib.request
import urllib.parse
import urllib.error
import json
import re
import os
import time

def fetch_free_api(word: str) -> dict:
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(word)}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            if isinstance(data, list) and len(data) > 0:
                entry = data[0]
                meanings = entry.get('meanings', [])
                if meanings:
                    first_meaning = meanings[0]
                    part_of_speech = first_meaning.get('partOfSpeech', '')
                    definitions = first_meaning.get('definitions', [])
                    meaning_text = definitions[0].get('definition', '') if definitions else ''
                    return {'partOfSpeech': part_of_speech, 'meaning': meaning_text}
    except Exception:
        pass
    return {}

def fetch_cambridge(word: str) -> dict:
    url = f"https://dictionary.cambridge.org/dictionary/english/{urllib.parse.quote(word)}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
            
            # Simple regex parsing
            pos_match = re.search(r'<span class="pos dpos"[^>]*>([^<]+)</span>', html)
            part_of_speech = pos_match.group(1) if pos_match else ''
            
            meaning_match = re.search(r'<div class="def ddef_d db">(.*?)</div>', html, flags=re.DOTALL)
            meaning_text = ''
            if meaning_match:
                meaning_text = re.sub(r'<[^>]+>', '', meaning_match.group(1)).strip()
                if meaning_text.endswith(':'):
                    meaning_text = meaning_text[:-1].strip()

            return {'partOfSpeech': part_of_speech, 'meaning': meaning_text}
    except Exception:
        pass
    return {}

def fetch_gemini(word: str, api_key: str, model: str) -> dict:
    if not api_key:
        return {}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    prompt = f"Provide the most common part of speech and a brief, single-sentence definition for the English word: '{word}'. Return ONLY a JSON object with exactly two keys: 'partOfSpeech' and 'meaning'. Do not include any markdown formatting or extra text."
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            
            text = res_json['candidates'][0]['content']['parts'][0]['text']
            text = text.replace('```json', '').replace('```', '').strip()
            result = json.loads(text)
            
            return {
                'partOfSpeech': result.get('partOfSpeech', ''),
                'meaning': result.get('meaning', '')
            }
    except Exception as e:
        print("Gemini API Error:", e)
        pass
    return {}

def fetch_word_data(word: str, source: str, api_key: str = "", gemini_model: str = "gemini-2.5-flash") -> dict:
    if source == 'cambridge':
        return fetch_cambridge(word)
    elif source == 'gemini':
        return fetch_gemini(word, api_key, gemini_model)
    else:
        return fetch_free_api(word)

def generate_full_word_data(word: str, api_key: str, model: str) -> dict:
    if not api_key:
        return {}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    prompt = f"""
You are an expert English teacher. Provide detailed information for the English word: '{word}'.
Return ONLY a valid JSON object with EXACTLY these keys:
- "word": the base form of the word
- "ipa": the International Phonetic Alphabet transcription (e.g., "/ɡlaɪd/")
- "pos": the part of speech (e.g., "noun", "verb")
- "meaning": a clear, concise English definition
- "sentence": a natural, common English example sentence using the word
- "vi_sentence": a natural Vietnamese translation of the example sentence
- "synonyms": 2-3 synonyms separated by commas
- "mnemonic": a short, memorable tip or trick (in English or Vietnamese) to remember the word

Do not include any markdown formatting, backticks, or extra text outside the JSON.
"""
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            
            text = res_json['candidates'][0]['content']['parts'][0]['text']
            text = text.replace('```json', '').replace('```', '').strip()
            result = json.loads(text)
            
            return {
                'word': result.get('word', word),
                'ipa': result.get('ipa', ''),
                'pos': result.get('pos', ''),
                'meaning': result.get('meaning', ''),
                'sentence': result.get('sentence', ''),
                'vi_sentence': result.get('vi_sentence', ''),
                'synonyms': result.get('synonyms', ''),
                'mnemonic': result.get('mnemonic', '')
            }
    except Exception as e:
        print("Gemini API Full Data Error:", e)
        pass
    return {}

def fetch_audio_url(word: str, accent: str = "us") -> str:
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(word)}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            if isinstance(data, list) and len(data) > 0:
                phonetics = data[0].get('phonetics', [])
                # Try to find exact accent match
                for p in phonetics:
                    audio = p.get('audio', '')
                    if audio and f"-{accent.lower()}.mp3" in audio.lower():
                        return audio
                # Fallback to any audio if accent not found
                for p in phonetics:
                    audio = p.get('audio', '')
                    if audio:
                        return audio
    except Exception:
        pass
    return ""

def fetch_image_url(word: str) -> str:
    # 1. Try Wikimedia pageimages API
    url = f"https://en.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(word)}&prop=pageimages&format=json&pithumbsize=500"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            pages = data.get('query', {}).get('pages', {})
            for page_id, page_info in pages.items():
                if 'thumbnail' in page_info:
                    return page_info['thumbnail']['source']
    except Exception:
        pass
        
    # 2. Fallback to Google Images
    google_url = f"https://www.google.com/search?q={urllib.parse.quote(word)}&tbm=isch"
    try:
        req = urllib.request.Request(google_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            # The first image is often the Google Logo. We look for actual image thumbnails from gstatic.
            matches = re.findall(r'<img[^>]+src="([^"]+gstatic\.com/images[^"]+)"', html)
            if matches:
                return matches[0]
    except Exception:
        pass
        
    # 3. Fallback to Cambridge Dictionary
    cambridge_url = f"https://dictionary.cambridge.org/dictionary/english/{urllib.parse.quote(word)}"
    try:
        req = urllib.request.Request(cambridge_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
            match = re.search(r'src="([^"]+/images/thumb/[^"]+)"', html)
            if match:
                img_url = match.group(1)
                if img_url.startswith('/'):
                    img_url = "https://dictionary.cambridge.org" + img_url
                return img_url
    except Exception:
        pass
        
    return ""

def download_media(url: str, word: str, is_audio: bool, mw) -> str:
    if not url: return ""
    try:
        ext = url.split('.')[-1].lower()
        if '?' in ext:
            ext = ext.split('?')[0]
            
        if is_audio:
            if 'mp3' not in ext and 'ogg' not in ext and 'wav' not in ext:
                ext = 'mp3'
        else:
            if ext not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                ext = 'jpg'
                
        # Clean word for filename
        clean_word = "".join([c for c in word if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
        timestamp = int(time.time())
        prefix = "audio" if is_audio else "img"
        filename = f"havaem_{prefix}_{clean_word}_{timestamp}.{ext}"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read()
            
        # Write to Anki media folder
        media_dir = mw.col.media.dir()
        file_path = os.path.join(media_dir, filename)
        with open(file_path, "wb") as f:
            f.write(data)
            
        if is_audio:
            return f"[sound:{filename}]"
        else:
            return f'<img src="{filename}">'
    except Exception as e:
        print(f"Media download error for {url}: {e}")
        return ""

