from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def user_data_root() -> Path:
    """Where The Archivist keeps the reader's own files (same layout as the other Glitched Matrix
    games): Windows %LOCALAPPDATA%\\GLITCHED MATRIX\\The Archivist, macOS ~/Library/Application Support/
    GLITCHED MATRIX/The Archivist, Linux ~/.local/share/glitched-matrix/the-archivist.
    ARCHIVIST_USER_DATA overrides it.  The game folder is never written."""
    import sys
    override = str(os.environ.get("ARCHIVIST_USER_DATA") or "").strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = str(os.environ.get("LOCALAPPDATA") or "").strip()
        return (Path(base) if base else Path.home() / "AppData" / "Local") / "GLITCHED MATRIX" / "The Archivist"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "GLITCHED MATRIX" / "The Archivist"
    xdg = str(os.environ.get("XDG_DATA_HOME") or "").strip()
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / "glitched-matrix" / "the-archivist"


USER_SAVE_DIR = user_data_root() / "saves"
BOOK_ROOT = ROOT / "assets" / "books"
CATALOG_PATH = BOOK_ROOT / "catalog.json"
LINKS_PATH = USER_SAVE_DIR / "simulation_links.json"
READING_PATH = USER_SAVE_DIR / "reading_progress.json"
ORB_ROOT = ROOT / "assets" / "orbs"
ASSET_ROOT = ROOT / "assets"
CYBER_ORB_ROOT = ROOT / "assets" / "cyber_orbs"

FEATURED_BOOK_IDS = (
    "continuation_afterlife_of_io",
    "continuation_entropy",
    "continuation_matrixcore",
    "archive_true_version",
    "continuation_the_restoration_of_utopia",
    "archive_the_empty_field",
)


def _read_json(path: Path, fallback: Any):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return fallback


def load_catalog() -> list[dict]:
    data = _read_json(CATALOG_PATH, [])
    return [dict(item) for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def catalog_by_id() -> dict[str, dict]:
    return {str(book.get("id")): book for book in load_catalog() if str(book.get("id", ""))}


def featured_books() -> list[dict]:
    by_id = catalog_by_id()
    result = [by_id[book_id] for book_id in FEATURED_BOOK_IDS if book_id in by_id]
    if len(result) < 6:
        for book in by_id.values():
            if book not in result:
                result.append(book)
            if len(result) >= 6:
                break
    return result


def book_text(book: dict) -> str:
    rel = str(book.get("text_file") or "").strip()
    if not rel:
        return "[No archive text is available for this record.]"
    path = (BOOK_ROOT / rel).resolve()
    try:
        if not path.is_relative_to(BOOK_ROOT.resolve()):
            return "[Archive record path rejected.]"
        return path.read_text(encoding="utf-8")
    except OSError:
        return "[This archive record could not be read from disk.]"


def load_links() -> dict[str, dict]:
    payload = _read_json(LINKS_PATH, {"version": 2, "links": {}})
    links = payload.get("links") if isinstance(payload, dict) else {}
    return {str(k): dict(v) for k, v in links.items() if isinstance(v, dict)} if isinstance(links, dict) else {}


def simulation_record(book_id: str) -> dict | None:
    return load_links().get(str(book_id))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_simulation(book_id: str, max_dirs: int = 1000, max_candidates: int = 240, max_depth: int = 4) -> tuple[Path | None, str]:
    """Resolve an existing Library Robot link without guessing or drive scans.

    The old library stored an exact main.py SHA and a small set of nearby roots.
    We preserve that safety contract: current path first, then bounded exact-hash
    recovery only.  The save file is not rewritten in Pass 01.
    """
    rec = simulation_record(book_id)
    if not rec:
        return None, "NO SIMULATION LINK"
    raw = str(rec.get("main_path") or "").strip()
    current = Path(raw).expanduser() if raw else None
    expected_sha = str(rec.get("main_sha256") or "").strip().lower()
    expected_size = int(rec.get("main_size") or 0)
    if current and current.is_file() and current.name.lower() == "main.py":
        if not expected_size or current.stat().st_size == expected_size:
            if not expected_sha or _sha256(current).lower() == expected_sha:
                return current.resolve(), "LINK READY"
    roots: list[Path] = []
    for value in rec.get("search_roots", []) if isinstance(rec.get("search_roots"), list) else []:
        try:
            p = Path(str(value)).expanduser()
        except Exception:
            continue
        if p.is_dir() and p not in roots:
            roots.append(p)
    if current:
        for p in (current.parent, current.parent.parent if current.parent != current else current.parent):
            if p.is_dir() and p not in roots:
                roots.append(p)
    if not expected_sha or not expected_size:
        return None, "SOURCE MOVED // NO RECOVERY FINGERPRINT"
    matches: list[Path] = []
    visited_dirs = 0
    candidates = 0
    for root in roots[:8]:
        root = root.resolve()
        for dirpath, dirnames, filenames in os.walk(root):
            here = Path(dirpath)
            try:
                depth = len(here.relative_to(root).parts)
            except Exception:
                depth = max_depth
            visited_dirs += 1
            if visited_dirs > max_dirs:
                break
            if depth >= max_depth:
                dirnames[:] = []
            if "main.py" not in filenames:
                continue
            candidate = here / "main.py"
            candidates += 1
            if candidates > max_candidates:
                break
            try:
                if candidate.stat().st_size == expected_size and _sha256(candidate).lower() == expected_sha:
                    matches.append(candidate.resolve())
                    if len(matches) > 1:
                        return None, "MULTIPLE EXACT SIMULATION COPIES FOUND"
            except OSError:
                pass
        if visited_dirs > max_dirs or candidates > max_candidates:
            break
    if len(matches) == 1:
        return matches[0], "EXACT MOVED SOURCE FOUND"
    return None, "SIMULATION SOURCE MISSING"


def orb_texture_path(book_id: str) -> Path | None:
    """Return packaged story texture for an archive orb."""
    safe = "".join(ch if (ch.isalnum() or ch in "_.-") else "_" for ch in str(book_id or ""))
    for root in (CYBER_ORB_ROOT, ORB_ROOT):
        for ext in (".jpg", ".png", ".jpeg"):
            path = root / f"{safe}{ext}"
            if path.is_file():
                return path
    return None



def find_soundtrack() -> Path | None:
    """Find the user drop-in archive soundtrack deterministically.

    `assets/soundtrack.mp3` wins. Otherwise the first MP3 under assets/ is used.
    This stays independent of Panda3D so packaging/validation can test it.
    """
    candidates: list[Path] = []
    if ASSET_ROOT.is_dir():
        try:
            candidates = [p for p in ASSET_ROOT.rglob("*") if p.is_file() and p.suffix.lower() == ".mp3"]
        except OSError:
            candidates = []
    if not candidates:
        return None
    return sorted(set(candidates), key=lambda p: (0 if p.name.lower() == "soundtrack.mp3" else 1, p.name.lower(), os.fspath(p)))[0]

def simulation_art_path(book_id: str) -> Path | None:
    """Use a linked simulation's own icon when the exact stored art path exists.

    The saved absolute path is advisory only; no search or guessing is performed.
    """
    rec = simulation_record(str(book_id))
    if not rec:
        return None
    raw = str(rec.get("art_path") or "").strip()
    if not raw:
        return None
    try:
        path = Path(raw).expanduser()
    except Exception:
        return None
    return path.resolve() if path.is_file() else None
