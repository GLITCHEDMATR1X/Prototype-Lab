"""Persistent patron identity + memory for Library Robot.

This module deliberately has no pygame dependency.  It keeps long-lived identity
and preference data separate from the VisitorRobot movement FSM.
"""

from __future__ import annotations

import json
import os
import random
from copy import deepcopy

SCHEMA_VERSION = 1
MAX_GENERIC_PATRONS = 16
FAVORITE_LIMIT = 3


def empty_db():
    return {
        "schema": SCHEMA_VERSION,
        "next_generic_id": 1,
        "patrons": {},
    }


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_record(record):
    rec = dict(record or {})
    rec["patron_id"] = str(rec.get("patron_id", ""))
    rec["lore_id"] = str(rec.get("lore_id", ""))
    rec["display_name"] = str(rec.get("display_name", ""))
    accent = rec.get("accent", [110, 140, 150])
    if not isinstance(accent, list) or len(accent) != 3:
        accent = [110, 140, 150]
    rec["accent"] = [max(0, min(255, _safe_int(v, 128))) for v in accent]
    rec["appearance_variant"] = _safe_int(rec.get("appearance_variant", 0)) % 4
    rec["visits"] = max(0, _safe_int(rec.get("visits", 0)))
    rec["return_visits"] = max(0, _safe_int(rec.get("return_visits", 0)))
    rec["books_read"] = {
        str(k): max(0, _safe_int(v))
        for k, v in dict(rec.get("books_read", {})).items()
    }
    rec["books_borrowed"] = {
        str(k): max(0, _safe_int(v))
        for k, v in dict(rec.get("books_borrowed", {})).items()
    }
    rec["favorite_books"] = [
        str(v) for v in list(rec.get("favorite_books", []))[:FAVORITE_LIMIT]
    ]
    rec["current_loan"] = str(rec.get("current_loan", ""))
    rec["preferred_chair"] = rec.get("preferred_chair")
    if (
        not isinstance(rec["preferred_chair"], list)
        or len(rec["preferred_chair"]) != 2
    ):
        rec["preferred_chair"] = None
    else:
        try:
            rec["preferred_chair"] = [
                round(float(rec["preferred_chair"][0]), 2),
                round(float(rec["preferred_chair"][1]), 2),
            ]
        except (TypeError, ValueError):
            rec["preferred_chair"] = None
    rec["last_visit"] = float(rec.get("last_visit", 0.0) or 0.0)
    rec["last_book"] = str(rec.get("last_book", ""))
    rec["last_activity"] = str(rec.get("last_activity", ""))
    return rec


def load_patron_db(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return empty_db()

    if not isinstance(data, dict) or data.get("schema") != SCHEMA_VERSION:
        return empty_db()

    db = empty_db()
    db["next_generic_id"] = max(1, _safe_int(data.get("next_generic_id", 1), 1))
    for patron_id, record in dict(data.get("patrons", {})).items():
        rec = _normalize_record(record)
        if not rec["patron_id"]:
            rec["patron_id"] = str(patron_id)
        db["patrons"][rec["patron_id"]] = rec
    return db


def save_patron_db(path, db):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "schema": SCHEMA_VERSION,
        "next_generic_id": max(1, _safe_int(db.get("next_generic_id", 1), 1)),
        "patrons": {
            patron_id: _normalize_record(record)
            for patron_id, record in dict(db.get("patrons", {})).items()
        },
    }

    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    os.replace(temp_path, path)
    return payload


def patron_label(record):
    if not record:
        return ""
    if record.get("display_name"):
        return str(record["display_name"])
    patron_id = str(record.get("patron_id", ""))
    if patron_id.startswith("patron_"):
        return "PATRON " + patron_id.split("_", 1)[1]
    return patron_id.upper()


def ensure_lore_patron(db, lore_id, display_name, accent, appearance_variant=0):
    patron_id = "lore_" + str(lore_id)
    patrons = db.setdefault("patrons", {})
    if patron_id not in patrons:
        patrons[patron_id] = _normalize_record({
            "patron_id": patron_id,
            "lore_id": str(lore_id),
            "display_name": str(display_name or ""),
            "accent": list(accent),
            "appearance_variant": int(appearance_variant),
        })
    else:
        rec = patrons[patron_id]
        rec["lore_id"] = str(lore_id)
        if display_name:
            rec["display_name"] = str(display_name)
        rec["accent"] = list(accent)
        rec["appearance_variant"] = int(appearance_variant) % 4
    return patrons[patron_id]


def create_generic_patron(db, accent_pool, rng=random):
    patrons = db.setdefault("patrons", {})
    number = max(1, _safe_int(db.get("next_generic_id", 1), 1))
    patron_id = f"patron_{number:03d}"
    db["next_generic_id"] = number + 1
    accent = list(rng.choice(list(accent_pool)))
    rec = _normalize_record({
        "patron_id": patron_id,
        "accent": accent,
        "appearance_variant": rng.randrange(4),
    })
    patrons[patron_id] = rec
    return rec


def choose_generic_patron(db, accent_pool, active_ids=(), rng=random):
    patrons = db.setdefault("patrons", {})
    active_ids = set(active_ids or ())
    available = [
        rec for rec in patrons.values()
        if not rec.get("lore_id")
        and rec.get("patron_id") not in active_ids
        and not rec.get("current_loan")
    ]

    generic_count = sum(1 for rec in patrons.values() if not rec.get("lore_id"))

    # Build a recognizable repeat-customer population before endlessly creating
    # strangers.  Once the pool reaches 6, returning patrons are strongly favored.
    should_reuse = bool(available) and (
        generic_count >= 6 or rng.random() < min(.78, .22 + generic_count * .08)
    )
    if should_reuse:
        # Less-recent patrons get a slightly better chance to return.
        ordered = sorted(
            available,
            key=lambda rec: (float(rec.get("last_visit", 0.0)), int(rec.get("visits", 0))),
        )
        window = ordered[:max(1, min(6, len(ordered)))]
        return rng.choice(window)

    if generic_count < MAX_GENERIC_PATRONS:
        return create_generic_patron(db, accent_pool, rng)

    return rng.choice(available) if available else None


def start_visit(record, now_s, returning_loan=False):
    familiar = int(record.get("visits", 0)) > 0
    record["visits"] = int(record.get("visits", 0)) + 1
    if returning_loan:
        record["return_visits"] = int(record.get("return_visits", 0)) + 1
    record["last_visit"] = float(now_s)
    record["last_activity"] = "returning" if returning_loan else "arrived"
    return familiar


def _recompute_favorites(record):
    reads = dict(record.get("books_read", {}))
    borrows = dict(record.get("books_borrowed", {}))
    all_ids = set(reads) | set(borrows)
    scored = []
    for book_id in all_ids:
        score = reads.get(book_id, 0) * 3 + borrows.get(book_id, 0)
        scored.append((-score, book_id))
    record["favorite_books"] = [
        book_id for _, book_id in sorted(scored)[:FAVORITE_LIMIT]
    ]


def note_read(record, book_id, chair_xy=None):
    book_id = str(book_id)
    reads = record.setdefault("books_read", {})
    reads[book_id] = int(reads.get(book_id, 0)) + 1
    record["last_book"] = book_id
    record["last_activity"] = "read"
    if chair_xy is not None:
        record["preferred_chair"] = [
            round(float(chair_xy[0]), 2),
            round(float(chair_xy[1]), 2),
        ]
    _recompute_favorites(record)


def note_checkout(record, book_id):
    book_id = str(book_id)
    borrowed = record.setdefault("books_borrowed", {})
    borrowed[book_id] = int(borrowed.get(book_id, 0)) + 1
    record["current_loan"] = book_id
    record["last_book"] = book_id
    record["last_activity"] = "borrowed"
    _recompute_favorites(record)


def note_return(record, book_id):
    if str(record.get("current_loan", "")) == str(book_id):
        record["current_loan"] = ""
    record["last_book"] = str(book_id)
    record["last_activity"] = "returned"


def choose_memory_book(record, available_ids, rng=random):
    available = list(available_ids or ())
    if not available:
        return None

    favorites = [
        book_id for book_id in record.get("favorite_books", [])
        if book_id in available
    ]
    if favorites and rng.random() < .46:
        return rng.choice(favorites)

    seen = (
        set(record.get("books_read", {}))
        | set(record.get("books_borrowed", {}))
    )
    unread = [book_id for book_id in available if book_id not in seen]
    if unread and rng.random() < .70:
        return rng.choice(unread)

    return rng.choice(available)


def clear_transient_loans(db):
    """Reconcile patron memory with Pass 10's session-local circulation state.

    Circulation loans themselves are intentionally not persisted yet.  Without
    this repair, quitting while a generic patron has a book would permanently
    exclude that patron from future visits after restart.
    """
    repaired = 0
    for record in db.get("patrons", {}).values():
        if record.get("current_loan"):
            record["current_loan"] = ""
            record["last_activity"] = "loan_closed_on_restart"
            repaired += 1
    return repaired


def prune_book_memory(db, valid_book_ids):
    valid = set(valid_book_ids)
    for record in db.get("patrons", {}).values():
        for field in ("books_read", "books_borrowed"):
            record[field] = {
                book_id: count
                for book_id, count in record.get(field, {}).items()
                if book_id in valid
            }
        record["favorite_books"] = [
            book_id for book_id in record.get("favorite_books", [])
            if book_id in valid
        ]
        if record.get("current_loan") not in valid:
            record["current_loan"] = ""
        if record.get("last_book") not in valid:
            record["last_book"] = ""
        _recompute_favorites(record)


def recent_patrons(db, limit=8):
    patrons = list(db.get("patrons", {}).values())
    patrons.sort(
        key=lambda rec: (
            float(rec.get("last_visit", 0.0)),
            int(rec.get("visits", 0)),
        ),
        reverse=True,
    )
    return patrons[:max(1, int(limit))]
