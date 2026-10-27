### **HAVAEM Tool Hub**

One hub (**Tools ▸ HAVAEM Tool Hub**) for building and maintaining vocabulary decks: create cards from a word list, fill the gaps in existing cards, pick your pronunciation source, and back up your add-ons.

#### ✨ Features

**1. Smart Word Creator**
* Paste words (one per line) and get finished cards: IPA, part of speech, meaning, example sentence, translation, synonyms, mnemonic, audio and an image.
* Text source: **Cambridge Dictionary**, **Free Dictionary API** or **Gemini AI**. Optionally let Gemini fill whatever the dictionary can't provide.
* Or import your own data (TSV or `|` separated) and let the add-on fetch just the audio / image.
* Skips words you already have, tags new notes, and remembers your field mapping per note type.

**2. Add Missing Fields**
* Choose a deck (subdecks included) plus an optional search filter, then fill empty IPA / POS / meaning / example / translation / synonyms / mnemonic / audio / image fields.
* **Check what's missing** first — counts the notes that need data without making any request.
* Existing content is preserved unless you tick *Overwrite*.

**3. Audio sources**
* **Cambridge Dictionary** — US or UK.
* **Google Translate** — US, UK, Australian or Indian English.
* One-click **Test** button, and an optional automatic fallback to the other source when a word has no audio.

**4. Add-on Backup**
* **Export** the list of installed add-ons (install codes, version, enabled state and settings) to a JSON file.
* **Import** it on any machine: missing add-ons are downloaded from AnkiWeb, then their settings and enabled state are restored. Add-ons installed from files have no install code and are listed for manual reinstall.
* Optional automatic daily backup (last 10 kept). HAVAEM's own Gemini key is never exported.

**5. Reliable processing**
* Parallel requests with automatic retry/back-off on rate limits, pause / cancel, live progress with ETA, and an honest log: a note only counts as done once Anki has saved it.
* Settings are stored in Anki's add-on config, so they survive updates.

#### 🚀 Getting started
1. Open **Tools ▸ HAVAEM Tool Hub**.
2. *(Optional)* In **Settings**, add a free [Gemini API key](https://aistudio.google.com/app/apikey) and press **Test connection**.
3. Pick **Smart Word Creator** or **Add Missing Fields**, choose the deck / note type, check the field mapping (it is guessed from the field names), and start.

#### Notes
* Requires Anki 2.1.50 or newer.
* Cambridge and Google are queried like a browser would; if a site changes its layout or blocks requests, use the audio fallback or switch source.

### **Support & Feedback**
Feel free to reach out with any issues, feature requests, or general feedback.
