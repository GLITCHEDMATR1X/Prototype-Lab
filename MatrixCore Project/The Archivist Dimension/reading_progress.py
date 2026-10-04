"""Persistent reading progress for Library Robot.

No pygame dependency. The game owns rendering; this module owns only durable state.
"""

from __future__ import annotations

import json
import os
import time

SCHEMA_VERSION = 1


def empty_db():
    return {"schema": SCHEMA_VERSION, "books": {}}


def _normalize_record(record):
    rec = dict(record or {})
    rec["last_spread"] = max(0, int(rec.get("last_spread", 0) or 0))
    rec["max_page_seen"] = max(0, int(rec.get("max_page_seen", 0) or 0))
    rec["total_pages"] = max(1, int(rec.get("total_pages", 1) or 1))
    rec["opens"] = max(0, int(rec.get("opens", 0) or 0))
    rec["last_opened"] = float(rec.get("last_opened", 0.0) or 0.0)
    status = str(rec.get("status", "unread"))
    if status not in ("unread", "in_progress", "read"):
        status = "unread"
    rec["status"] = status
    return rec


def load_reading_db(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return empty_db()

    if not isinstance(data, dict) or data.get("schema") != SCHEMA_VERSION:
        return empty_db()

    db = empty_db()
    for book_id, record in dict(data.get("books", {})).items():
        db["books"][str(book_id)] = _normalize_record(record)
    return db


def save_reading_db(path, db):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "schema": SCHEMA_VERSION,
        "books": {
            str(book_id): _normalize_record(record)
            for book_id, record in dict(db.get("books", {})).items()
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


def get_record(db, book_id):
    return db.setdefault("books", {}).get(str(book_id))


def resume_spread(db, book_id, total_pages):
    total_pages = max(1, int(total_pages))
    record = get_record(db, book_id)
    if not record:
        return 0
    max_even_spread = max(0, ((total_pages - 1) // 2) * 2)
    spread = max(0, int(record.get("last_spread", 0)))
    spread -= spread % 2
    return min(max_even_spread, spread)


def note_open(db, book_id, total_pages, spread=0, now=None):
    book_id = str(book_id)
    total_pages = max(1, int(total_pages))
    books = db.setdefault("books", {})
    record = _normalize_record(books.get(book_id, {}))
    record["opens"] += 1
    record["last_opened"] = float(time.time() if now is None else now)
    books[book_id] = record
    return note_position(db, book_id, total_pages, spread, now=record["last_opened"])


def note_position(db, book_id, total_pages, spread, now=None):
    book_id = str(book_id)
    total_pages = max(1, int(total_pages))
    spread = max(0, int(spread))
    spread -= spread % 2
    max_even_spread = max(0, ((total_pages - 1) // 2) * 2)
    spread = min(spread, max_even_spread)

    books = db.setdefault("books", {})
    record = _normalize_record(books.get(book_id, {}))
    record["total_pages"] = total_pages
    record["last_spread"] = spread
    record["last_opened"] = float(time.time() if now is None else now)

    visible_through = min(total_pages, spread + 2)
    record["max_page_seen"] = max(record["max_page_seen"], visible_through)
    if record["max_page_seen"] >= total_pages:
        record["status"] = "read"
    elif record["max_page_seen"] > 0:
        record["status"] = "in_progress"
    else:
        record["status"] = "unread"

    books[book_id] = record
    return record


def progress_percent(db, book_id):
    record = get_record(db, book_id)
    if not record:
        return 0
    total = max(1, int(record.get("total_pages", 1)))
    seen = max(0, min(total, int(record.get("max_page_seen", 0))))
    return int(round(seen * 100.0 / total))


def progress_status(db, book_id):
    record = get_record(db, book_id)
    return str(record.get("status", "unread")) if record else "unread"


def summary(db, valid_book_ids=None):
    valid = set(valid_book_ids) if valid_book_ids is not None else None
    counts = {"unread": 0, "in_progress": 0, "read": 0}
    ids = valid if valid is not None else set(db.get("books", {}))
    for book_id in ids:
        counts[progress_status(db, book_id)] += 1
    return counts


def prune_reading_db(db, valid_book_ids):
    valid = set(str(v) for v in valid_book_ids)
    books = db.setdefault("books", {})
    removed = [book_id for book_id in books if book_id not in valid]
    for book_id in removed:
        books.pop(book_id, None)
    return len(removed)
