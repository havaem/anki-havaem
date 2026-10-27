"""The two main operations: enrich existing notes, and create new ones."""

from aqt import mw
from anki.notes import NoteFieldsCheckResult
from anki.utils import strip_html

from . import config, providers
from .jobs import call_on_main, run_job
from .providers import KEY_LABELS, TEXT_KEYS, slugify


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def build_opts() -> dict:
    cfg = config.load()
    return {
        "gemini_key": cfg["gemini_api_key"].strip(),
        "gemini_model": cfg["gemini_model"],
        "language": cfg["translation_language"] or "Vietnamese",
        "fill_gaps": cfg["gemini_fill_gaps"],
        "cambridge_region": cfg["cambridge_region"],
        "google_region": cfg["google_region"],
        "audio_source": cfg["audio_source"],
        "audio_fallback": cfg["audio_fallback"],
        "workers": max(1, min(int(cfg["workers"]), 8)),
    }


def gather(word: str, keys, source: str, opts: dict):
    """Fetch every requested key for ``word``. Returns ``(values, problems)``."""
    values: dict = {}
    problems: list = []

    text_keys = [k for k in keys if k in TEXT_KEYS]
    if text_keys:
        got, probs = providers.fetch_text(word, text_keys, source, opts)
        values.update(got)
        problems += probs
        problems += [f"no {KEY_LABELS[k].lower()}" for k in text_keys if k not in got]

    if "audio" in keys:
        regions = {"cambridge": opts["cambridge_region"], "google": opts["google_region"]}
        audio, probs = providers.get_audio(word, opts["audio_source"], regions, opts["audio_fallback"])
        if audio:
            name = _store_media(f"{slugify(word)}_{audio.tag}", audio.data, audio.ext)
            values["audio"] = f"[sound:{name}]"
        else:
            problems += probs

    if "image" in keys:
        image, probs = providers.get_image(word)
        if image:
            data, ext = image
            name = _store_media(f"{slugify(word)}_img", data, ext)
            values["image"] = f'<img src="{name}">'
        else:
            problems += probs

    return values, problems


def _store_media(base: str, data: bytes, ext: str) -> str:
    return call_on_main(lambda: mw.col.media.write_data(f"havaem_{base}.{ext}", data))


def is_empty_field(raw: str) -> bool:
    return not (strip_html(raw).strip() or "<img" in raw or "[sound:" in raw)


def deck_search(deck_name: str, extra: str = "") -> str:
    from anki.collection import SearchNode

    nodes = [SearchNode(deck=deck_name)]
    return mw.col.build_search_string(*nodes, *([extra] if extra.strip() else []))


def deck_field_names(deck_name: str) -> list:
    """Field names of every note type used in a deck (and subdecks), in order."""
    from anki.utils import ids2str

    did = mw.col.decks.id_for_name(deck_name)
    if not did:
        return []
    dids = mw.col.decks.deck_and_child_ids(did)
    mids = mw.col.db.list(
        "select distinct n.mid from notes n join cards c on c.nid = n.id "
        f"where c.did in {ids2str(dids)}"
    )
    names: list = []
    for mid in mids:
        model = mw.col.models.get(mid)
        for fld in (model or {}).get("flds", []):
            if fld["name"] not in names:
                names.append(fld["name"])
    return names


def _short_problems(problems: list) -> str:
    unique = list(dict.fromkeys(problems))
    return f" (missing: {'; '.join(unique)})" if unique else ""


# --------------------------------------------------------------------------- #
# Enrich existing notes
# --------------------------------------------------------------------------- #


def plan_note(note, word_field: str, mapping: dict, overwrite: bool):
    """Return ``(word, keys_to_fill)``; ``word`` is None when the note can't be used."""
    if word_field not in note:
        return None, set()
    word = strip_html(note[word_field]).strip()
    if not word:
        return None, set()
    needs = {
        key
        for key, field in mapping.items()
        if key != "word" and field in note and (overwrite or is_empty_field(note[field]))
    }
    return word, needs


def scan_notes(query: str, word_field: str, mapping: dict, overwrite: bool) -> dict:
    """Count how many notes in ``query`` would be touched (no network)."""
    nids = mw.col.find_notes(query)
    result = {"total": len(nids), "actionable": 0, "no_word": 0, "by_key": {}}
    for nid in nids:
        word, needs = plan_note(mw.col.get_note(nid), word_field, mapping, overwrite)
        if not word:
            result["no_word"] += 1
        elif needs:
            result["actionable"] += 1
            for key in needs:
                result["by_key"][key] = result["by_key"].get(key, 0) + 1
    return result


def start_enrich(parent, query, word_field, mapping, source, overwrite):
    opts = build_opts()
    nids = mw.col.find_notes(query)
    providers.clear_caches()

    def handler(nid, log):
        word, needs = call_on_main(lambda: plan_note(mw.col.get_note(nid), word_field, mapping, overwrite))
        if not word:
            return "skip", f"note {nid}: no word in '{word_field}'"
        if not needs:
            return "skip", f"'{word}': already complete"

        values, problems = gather(word, needs, source, opts)
        if not values:
            return "error", f"'{word}': nothing found{_short_problems(problems)}"

        def apply():
            note = mw.col.get_note(nid)
            for key, value in values.items():
                field = mapping[key]
                # never clobber something the user typed while we were fetching
                if field in note and (overwrite or is_empty_field(note[field])):
                    note[field] = value
            mw.col.update_note(note)

        call_on_main(apply)
        return "ok", f"'{word}': filled {', '.join(KEY_LABELS[k] for k in values)}{_short_problems(problems)}"

    return run_job(
        parent, "Add Missing Fields", nids, handler,
        label=lambda nid: f"note {nid}", workers=opts["workers"],
    )


# --------------------------------------------------------------------------- #
# Create new notes
# --------------------------------------------------------------------------- #


def _is_duplicate(notetype, mapping: dict, values: dict) -> bool:
    note = mw.col.new_note(notetype)
    for key, value in values.items():
        field = mapping.get(key)
        if field and field in note:
            note[field] = value
    try:
        return note.fields_check() == NoteFieldsCheckResult.DUPLICATE
    except Exception:
        return False


def _add_note(notetype, deck_id, fields: dict, tags: list):
    note = mw.col.new_note(notetype)
    for field, value in fields.items():
        if field in note:
            note[field] = value
    note.tags = tags
    mw.col.add_note(note, deck_id)


def parse_import_line(line: str) -> list:
    sep = "\t" if "\t" in line else "|"
    return [p.strip() for p in line.split(sep)]


def start_create(parent, deck_name, notetype_name, mapping, mode, text, source, skip_dups, tag):
    opts = build_opts()
    notetype = mw.col.models.by_name(notetype_name)
    deck_id = mw.col.decks.id_for_name(deck_name)
    if not notetype or not deck_id:
        from aqt.utils import showWarning

        showWarning("The selected deck or note type no longer exists.", parent=parent)
        return None

    tags = [t for t in tag.split() if t]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    field_names = [f["name"] for f in notetype["flds"]]
    providers.clear_caches()

    if mode == "generate":
        seen: set = set()
        items = [w for w in lines if not (w.lower() in seen or seen.add(w.lower()))]
        wanted = [k for k in mapping if k != "word"]

        def handler(word, log):
            if skip_dups and call_on_main(lambda: _is_duplicate(notetype, mapping, {"word": word})):
                return "skip", f"'{word}': already exists"
            values, problems = gather(word, wanted, source, opts) if wanted else ({}, [])
            core = [k for k in wanted if k in TEXT_KEYS] or wanted
            if core and not any(k in values for k in core):
                return "error", f"'{word}': nothing found{_short_problems(problems)}"
            values["word"] = providers._esc(word)
            fields = {mapping[k]: v for k, v in values.items() if k in mapping}
            call_on_main(lambda: _add_note(notetype, deck_id, fields, tags))
            return "ok", f"'{word}': created{_short_problems(problems)}"

    else:
        items = lines
        media_keys = [k for k in ("audio", "image") if k in mapping]

        def handler(line, log):
            parts = parse_import_line(line)
            word = strip_html(parts[0]).strip() if parts else ""
            if not word:
                return "error", f"invalid line: '{line[:30]}'"
            if len(parts) > len(field_names):
                return "error", f"'{word}': {len(parts)} columns but note type has {len(field_names)} fields"
            fields = dict(zip(field_names, parts))

            if skip_dups:
                probe = {"word": fields[field_names[0]]}
                first = {"word": field_names[0]}
                if call_on_main(lambda: _is_duplicate(notetype, first, probe)):
                    return "skip", f"'{word}': already exists"

            problems: list = []
            need = [k for k in media_keys if not fields.get(mapping[k])]
            if need:
                values, problems = gather(word, need, source, opts)
                fields.update({mapping[k]: v for k, v in values.items()})
            def add_if_new():
                identity = {field: field for field in fields}
                if skip_dups and _is_duplicate(notetype, identity, fields):
                    return False
                _add_note(notetype, deck_id, fields, tags)
                return True

            if not call_on_main(add_if_new):
                return "skip", f"'{word}': already exists"
            return "ok", f"'{word}': created{_short_problems(problems)}"

    return run_job(
        parent, "Smart Word Creator", items, handler,
        label=lambda item: f"'{str(item)[:30]}'", workers=opts["workers"],
    )
