"""Data providers: dictionaries, Gemini, audio (Cambridge / Google) and images.

Nothing here touches Anki, so it can be tested on its own. Functions raise
``ProviderError`` for network/API problems and return empty results when a
word simply isn't found.
"""

import html
import json
import re
import threading
import urllib.parse
from dataclasses import dataclass
from typing import Optional

from . import net
from .net import HttpError

# --------------------------------------------------------------------------- #
# Field keys shared by the UI and the tasks
# --------------------------------------------------------------------------- #

FIELD_KEYS = [
    ("word", "Word"),
    ("ipa", "IPA"),
    ("pos", "Part of speech"),
    ("meaning", "Meaning"),
    ("sentence", "Example sentence"),
    ("tr_sentence", "Sentence translation"),
    ("synonyms", "Synonyms"),
    ("mnemonic", "Mnemonic"),
    ("audio", "Audio"),
    ("image", "Image"),
]
KEY_LABELS = dict(FIELD_KEYS)
TEXT_KEYS = ("ipa", "pos", "meaning", "sentence", "tr_sentence", "synonyms", "mnemonic")

TEXT_SOURCES = [
    ("Cambridge Dictionary", "cambridge"),
    ("Free Dictionary API", "free"),
    ("Gemini AI", "gemini"),
]

CAMBRIDGE_REGIONS = [("US", "us"), ("UK", "uk")]
GOOGLE_REGIONS = [
    ("US English", "us"),
    ("UK English", "uk"),
    ("Australian English", "au"),
    ("Indian English", "in"),
]
GOOGLE_LANG = {"us": "en-US", "uk": "en-GB", "au": "en-AU", "in": "en-IN"}
AUDIO_SOURCES = [("Cambridge Dictionary", "cambridge"), ("Google Translate", "google")]


class ProviderError(Exception):
    pass


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def _clean(markup: str) -> str:
    text = re.sub(r"<[^>]+>", "", markup)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _esc(text: str) -> str:
    """Field values are HTML; escape plain text coming from APIs."""
    return html.escape(text, quote=False)


def _span_inner(s: str, pos: int) -> str:
    """Inner HTML of the <span> whose opening tag ends at ``pos`` (handles nesting)."""
    depth = 1
    for m in re.finditer(r"<(/?)span\b", s[pos:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return s[pos : pos + m.start()]
    return s[pos : pos + 300]


def _attr(tag: str, name: str) -> str:
    m = re.search(rf'\b{name}\s*=\s*"([^"]*)"', tag)
    return m.group(1) if m else ""


def slugify(word: str, limit: int = 50) -> str:
    slug = "".join(c if c.isalnum() else "_" for c in word.strip().lower())
    return re.sub(r"_+", "_", slug).strip("_")[:limit] or "word"


# --------------------------------------------------------------------------- #
# Cambridge Dictionary
# --------------------------------------------------------------------------- #

CAMBRIDGE_BASE = "https://dictionary.cambridge.org"
_cambridge_cache: dict = {}
_cache_lock = threading.Lock()


def clear_caches() -> None:
    with _cache_lock:
        _cambridge_cache.clear()


def parse_cambridge(page: str) -> dict:
    """Extract pos / definition / example / per-region IPA + audio URLs."""
    out: dict = {"audio": {}, "ipa_by_region": {}}

    m = re.search(r'<span class="pos dpos"[^>]*>', page)
    if m:
        out["pos"] = _clean(_span_inner(page, m.end()))

    m = re.search(r'<div class="def ddef_d db">(.*?)</div>', page, re.S)
    if m:
        out["meaning"] = _clean(m.group(1)).rstrip(":").strip()

    m = re.search(r'<span class="eg deg">', page)
    if m:
        out["sentence"] = _clean(_span_inner(page, m.end()))

    for region in ("uk", "us"):
        m = re.search(rf'<span class="{region} dpron-i[^"]*">', page)
        if not m:
            continue
        chunk = page[m.end() : m.end() + 3000]
        nxt = re.search(r'class="(?:uk|us) dpron-i', chunk)
        if nxt:
            chunk = chunk[: nxt.start()]
        for tag in re.findall(r"<source[^>]*>", chunk):
            if "audio/mpeg" in tag and _attr(tag, "src"):
                out["audio"][region] = urllib.parse.urljoin(CAMBRIDGE_BASE, _attr(tag, "src"))
                break
        ipa = re.search(r'<span class="ipa dipa[^"]*">', chunk)
        if ipa:
            text = _clean(_span_inner(chunk, ipa.end()))
            if text:
                out["ipa_by_region"][region] = f"/{text}/"
    return out


def cambridge(word: str) -> dict:
    key = word.strip().lower()
    with _cache_lock:
        if key in _cambridge_cache:
            return _cambridge_cache[key]

    slug = urllib.parse.quote(key.replace(" ", "-"))
    try:
        resp = net.fetch(
            f"{CAMBRIDGE_BASE}/dictionary/english/{slug}",
            headers={"Referer": CAMBRIDGE_BASE + "/"},
        )
    except HttpError as e:
        if e.status == 404:
            result: dict = {}
            with _cache_lock:
                _cambridge_cache[key] = result
            return result
        raise ProviderError(f"Cambridge: {e}") from e

    if "/spellcheck/" in resp.url or "/search/" in resp.url:
        result = {}  # word not in dictionary, Cambridge redirected to suggestions
    else:
        result = parse_cambridge(resp.body.decode("utf-8", "replace"))
    with _cache_lock:
        _cambridge_cache[key] = result
    return result


def _cambridge_text(word: str, region: str) -> dict:
    page = cambridge(word)
    out = {k: page[k] for k in ("pos", "meaning", "sentence") if page.get(k)}
    ipas = page.get("ipa_by_region", {})
    ipa = ipas.get(region) or ipas.get("us") or ipas.get("uk")
    if ipa:
        out["ipa"] = ipa
    return out


# --------------------------------------------------------------------------- #
# Free Dictionary API
# --------------------------------------------------------------------------- #


def _free_dictionary(word: str) -> dict:
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(word.strip())}"
    try:
        resp = net.fetch(url)
    except HttpError as e:
        if e.status == 404:
            return {}
        raise ProviderError(f"Free Dictionary: {e}") from e
    try:
        entry = json.loads(resp.body.decode("utf-8"))[0]
    except (ValueError, IndexError, KeyError, TypeError):
        return {}

    out: dict = {}
    ipa = entry.get("phonetic") or next(
        (p["text"] for p in entry.get("phonetics", []) if p.get("text")), ""
    )
    if ipa:
        out["ipa"] = ipa
    meanings = entry.get("meanings") or []
    if meanings:
        first = meanings[0]
        out["pos"] = first.get("partOfSpeech", "")
        defs = first.get("definitions") or []
        if defs:
            out["meaning"] = defs[0].get("definition", "")
            out["sentence"] = next((d["example"] for d in defs if d.get("example")), "")
        syn = list(first.get("synonyms") or [])
        for d in defs:
            syn += d.get("synonyms") or []
        if syn:
            out["synonyms"] = ", ".join(dict.fromkeys(syn))
    return {k: v for k, v in out.items() if v}


# --------------------------------------------------------------------------- #
# Gemini
# --------------------------------------------------------------------------- #

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _gemini_error(e: HttpError) -> str:
    try:
        return json.loads(e.body.decode("utf-8"))["error"]["message"]
    except Exception:
        return str(e)


def _gemini_call(prompt: str, api_key: str, model: str, as_json: bool = True) -> str:
    payload: dict = {"contents": [{"parts": [{"text": prompt}]}]}
    if as_json:
        payload["generationConfig"] = {"responseMimeType": "application/json", "temperature": 0.3}
    try:
        resp = net.fetch(
            GEMINI_URL.format(model=urllib.parse.quote(model, safe="-.")),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            timeout=60,
            retries=3,
        )
    except HttpError as e:
        raise ProviderError(f"Gemini: {_gemini_error(e)}") from e
    try:
        parts = json.loads(resp.body.decode("utf-8"))["candidates"][0]["content"]["parts"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise ProviderError("Gemini returned an empty or blocked response") from e
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def _gemini_prompt(word: str, keys: list, language: str) -> str:
    desc = {
        "ipa": 'IPA transcription in slashes, e.g. "/ɡlaɪd/"',
        "pos": 'most common part of speech, lowercase English (e.g. "noun", "verb")',
        "meaning": "a clear, concise English definition in one sentence",
        "sentence": "a natural, common English example sentence using the word",
        "tr_sentence": f"a natural {language} translation of the example sentence",
        "synonyms": "2-3 English synonyms separated by commas",
        "mnemonic": f"a short, memorable tip to remember the word (in {language} or English)",
    }
    lines = "\n".join(f'- "{k}": {desc[k]}' for k in keys)
    return (
        f"You are an expert English teacher. Give information about the English word or phrase: "
        f'"{word}".\nReturn ONLY a JSON object with EXACTLY these string keys:\n{lines}\n'
        "No markdown, no extra text."
    )


def gemini_lookup(word: str, keys: list, api_key: str, model: str, language: str) -> dict:
    wanted = [k for k in keys if k in TEXT_KEYS]
    ask = list(wanted)
    if "tr_sentence" in ask and "sentence" not in ask:
        ask.insert(ask.index("tr_sentence"), "sentence")  # needed to translate
    if not ask:
        return {}
    text = _gemini_call(_gemini_prompt(word, ask, language), api_key, model)
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        data = json.loads(text)
    except ValueError as e:
        raise ProviderError("Gemini returned invalid JSON") from e
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        return {}
    out = {}
    for k in wanted:
        v = data.get(k)
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        if v:
            out[k] = str(v).strip()
    return out


def test_gemini(api_key: str, model: str) -> str:
    """Return the model's short reply; raises ProviderError when the key/model is bad."""
    return _gemini_call("Reply with the single word: OK", api_key, model, as_json=False).strip()


# --------------------------------------------------------------------------- #
# Text lookup (+ optional Gemini for gaps)
# --------------------------------------------------------------------------- #


def fetch_text(word: str, keys: list, source: str, opts: dict):
    """Return ``(values, problems)``. ``values`` maps key -> HTML-safe text."""
    keys = [k for k in keys if k in TEXT_KEYS]
    problems: list = []
    data: dict = {}
    api_key = (opts.get("gemini_key") or "").strip()

    try:
        if source == "cambridge":
            data = _cambridge_text(word, opts.get("cambridge_region", "us"))
        elif source == "free":
            data = _free_dictionary(word)
        elif source == "gemini":
            if not api_key:
                raise ProviderError("Gemini API key is missing")
            data = gemini_lookup(
                word, keys, api_key, opts["gemini_model"], opts.get("language", "Vietnamese")
            )
    except ProviderError as e:
        problems.append(str(e))

    missing = [k for k in keys if not data.get(k)]
    if missing and source != "gemini" and opts.get("fill_gaps") and api_key:
        try:
            extra = gemini_lookup(
                word, missing, api_key, opts["gemini_model"], opts.get("language", "Vietnamese")
            )
            data.update({k: v for k, v in extra.items() if v})
        except ProviderError as e:
            problems.append(str(e))

    values = {k: _esc(data[k]) for k in keys if data.get(k)}
    return values, problems


# --------------------------------------------------------------------------- #
# Audio
# --------------------------------------------------------------------------- #


@dataclass
class Audio:
    data: bytes
    tag: str  # e.g. "cambridge_us", used in the media filename
    ext: str = "mp3"


def _download_audio(url: str, referer: Optional[str] = None) -> bytes:
    headers = {"Referer": referer} if referer else {}
    try:
        body = net.fetch(url, headers=headers, timeout=25).body
    except HttpError as e:
        raise ProviderError(str(e)) from e
    if len(body) < 400 or body.lstrip()[:1] == b"<":
        raise ProviderError("response was not an audio file")
    return body


def _audio_cambridge(word: str, region: str) -> Audio:
    urls = cambridge(word).get("audio", {})
    other = "uk" if region == "us" else "us"
    for r in (region, other):
        if urls.get(r):
            return Audio(_download_audio(urls[r], CAMBRIDGE_BASE + "/"), f"cambridge_{r}")
    raise ProviderError("no audio on Cambridge")


def _audio_google(word: str, region: str) -> Audio:
    lang = GOOGLE_LANG.get(region, "en-US")
    url = (
        "https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob"
        f"&tl={lang}&q={urllib.parse.quote(word.strip())}"
    )
    return Audio(_download_audio(url, "https://translate.google.com/"), f"google_{region}")


def get_audio(word: str, source: str, regions: dict, fallback: bool):
    """Return ``(Audio | None, problems)``, trying the chosen source then the other."""
    order = [source] + ([s for s in ("cambridge", "google") if s != source] if fallback else [])
    loaders = {
        "cambridge": lambda: _audio_cambridge(word, regions.get("cambridge", "us")),
        "google": lambda: _audio_google(word, regions.get("google", "us")),
    }
    problems = []
    for src in order:
        try:
            return loaders[src](), problems
        except ProviderError as e:
            problems.append(f"audio/{src}: {e}")
    return None, problems


# --------------------------------------------------------------------------- #
# Image
# --------------------------------------------------------------------------- #

IMAGE_EXTS = ("jpg", "jpeg", "png", "gif", "webp")


def _ext_of(url: str, default: str = "jpg") -> str:
    ext = urllib.parse.urlparse(url).path.rsplit(".", 1)[-1].lower()
    return ext if ext in IMAGE_EXTS else default


def _image_url(word: str) -> str:
    q = urllib.parse.quote(word.strip())
    try:
        resp = net.fetch(
            "https://en.wikipedia.org/w/api.php?action=query&redirects=1&prop=pageimages"
            f"&format=json&pithumbsize=500&titles={q}"
        )
        for page in json.loads(resp.body.decode("utf-8")).get("query", {}).get("pages", {}).values():
            if "thumbnail" in page:
                return page["thumbnail"]["source"]
    except (HttpError, ValueError):
        pass

    try:
        slug = urllib.parse.quote(word.strip().lower().replace(" ", "-"))
        page = net.fetch(f"{CAMBRIDGE_BASE}/dictionary/english/{slug}").body.decode("utf-8", "replace")
        m = re.search(r'src="([^"]+/images/thumb/[^"]+)"', page)
        if m:
            return urllib.parse.urljoin(CAMBRIDGE_BASE, m.group(1))
    except HttpError:
        pass
    return ""


def get_image(word: str):
    """Return ``((bytes, ext) | None, problems)``."""
    url = _image_url(word)
    if not url:
        return None, ["image: nothing found"]
    try:
        return (net.fetch(url, timeout=25).body, _ext_of(url)), []
    except HttpError as e:
        return None, [f"image: {e}"]
