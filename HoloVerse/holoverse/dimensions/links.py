from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path

LINK_SCHEMA = 1
STATE_SCHEMA = 2
RESPONDER_PROTOCOL = "holoverse_responder_v1"
NATIVE_HOST_CONTRACT = "holoverse_dimension_v1"
GENERIC_IDENTITY_FILE = ".holoverse_link.json"
MAX_SOURCE_BYTES = 128 * 1024
MAX_RECOVERY_MAIN_FILES = 12000


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _valid_uuid(value: str) -> str:
    raw = str(value or "").strip()
    try:
        return str(uuid.UUID(raw))
    except Exception:
        return ""


def _stable_responder_key(value: str) -> str:
    """Return a portable manifest-level project key for recovery.

    Responder UUIDs remain the strongest identity, but external Prototype Lab
    projects are often replaced by fresh ZIPs that omit the host-created
    ``holoverse/identity.json`` sidecar.  A declared responder ``id`` gives the
    host one conservative recovery key that survives pass numbers, folder moves,
    and source edits without depending on an absolute path or source hash.
    """
    raw = str(value or "").strip().lower()
    parts = re.findall(r"[a-z0-9]+", raw)
    return "_".join(parts)


def _safe_relative(project_root: Path, raw: str) -> Path | None:
    try:
        root = project_root.resolve()
        candidate = (root / Path(str(raw or ""))).resolve()
        candidate.relative_to(root)
        return candidate
    except Exception:
        return None


def detect_engine(entry: Path) -> str:
    try:
        text = entry.read_bytes()[:MAX_SOURCE_BYTES].decode("utf-8", errors="ignore").lower()
    except Exception:
        return "unknown"
    has_panda = any(token in text for token in ("from panda3d", "import panda3d", "from direct.", "showbase(", "loadprcfiledata("))
    has_pygame = "import pygame" in text or "from pygame" in text or "pygame." in text
    has_moderngl = "import moderngl" in text or "from moderngl" in text
    has_tk = "import tkinter" in text or "from tkinter" in text
    if has_pygame and has_moderngl:
        return "pygame+moderngl"
    if has_panda:
        return "panda3d"
    if has_pygame:
        return "pygame"
    if has_moderngl:
        return "moderngl"
    if has_tk:
        return "tkinter"
    return "python"


def display_name_for_entry(entry: Path, manifest: dict | None = None) -> str:
    manifest = manifest if isinstance(manifest, dict) else {}
    title = str(manifest.get("title") or "").strip()
    if title and title.upper() != "AUTO":
        return title
    try:
        text = entry.read_bytes()[:MAX_SOURCE_BYTES].decode("utf-8", errors="ignore")
        for pattern in (
            r'^\s*GAME_NAME\s*=\s*["\']([^"\']+)["\']',
            r'^\s*TITLE\s*=\s*["\']([^"\']+)["\']',
            r'^\s*APP_NAME\s*=\s*["\']([^"\']+)["\']',
            r'^\s*WINDOW_TITLE\s*=\s*["\']([^"\']+)["\']',
        ):
            match = re.search(pattern, text, flags=re.MULTILINE)
            if match:
                return match.group(1).strip()
    except Exception:
        pass
    return entry.parent.name or "Linked Simulation"


def project_fingerprint(entry: Path) -> str:
    """Portable fallback identity that deliberately excludes absolute/folder paths.

    The stable UUID sidecar is the primary identity.  This fingerprint is only a
    recovery aid for projects that cannot accept a sidecar or old links created
    before one existed.
    """
    root = entry.parent
    h = hashlib.sha256()
    h.update(b"holoverse-linked-project-v1\n")
    try:
        h.update(entry.read_bytes()[:MAX_SOURCE_BYTES])
    except Exception:
        h.update(entry.name.lower().encode("utf-8", errors="ignore"))
    try:
        names = []
        for child in root.iterdir():
            if child.name.lower() in {"__pycache__", ".git", "logs", "crash_reports", "saves"}:
                continue
            names.append(("d:" if child.is_dir() else "f:") + child.name.lower())
        h.update("\n".join(sorted(names)[:192]).encode("utf-8", errors="ignore"))
    except Exception:
        pass
    return h.hexdigest()


def _responder_info(project_root: Path) -> dict:
    hv = project_root / "holoverse"
    manifest_path = hv / "holoverse_dimension.json"
    manifest = _read_json(manifest_path) if manifest_path.is_file() else {}
    if str(manifest.get("protocol") or "").strip() != RESPONDER_PROTOCOL:
        return {}
    identity = _read_json(hv / "identity.json")
    return {
        "manifest": manifest,
        "manifest_path": manifest_path,
        "identity_path": hv / "identity.json",
        "dimension_id": _valid_uuid(identity.get("dimension_id")),
        "stable_key": _stable_responder_key(manifest.get("id")),
    }


def _generic_identity(project_root: Path) -> dict:
    path = project_root / GENERIC_IDENTITY_FILE
    payload = _read_json(path) if path.is_file() else {}
    return {"path": path, "dimension_id": _valid_uuid(payload.get("dimension_id"))}


def _repair_responder_identity(project_root: Path, dimension_id: str) -> bool:
    """Restore a responder UUID sidecar from durable HoloVerse link state.

    This is intentionally conservative: it only writes when the selected project
    still declares the responder protocol, the durable id is a valid UUID, and
    the responder sidecar is currently missing.  It therefore repairs fresh-build
    replacement without inventing a new reality or touching arbitrary projects.
    """
    wanted = _valid_uuid(dimension_id)
    if not wanted:
        return False
    responder = _responder_info(project_root)
    if not responder or responder.get("dimension_id"):
        return False
    try:
        _atomic_write_json(
            responder["identity_path"],
            {"schema": 1, "protocol": RESPONDER_PROTOCOL, "dimension_id": wanted},
        )
        return True
    except Exception:
        return False


def _ensure_project_identity(project_root: Path) -> tuple[str, str]:
    """Return (uuid, identity_mode), preferring the optional responder identity."""
    responder = _responder_info(project_root)
    generic = _generic_identity(project_root)
    if responder:
        # If this project was linked before a responder was added, migrate the
        # existing generic UUID into the responder instead of inventing a new reality.
        dimension_id = responder.get("dimension_id") or generic.get("dimension_id") or str(uuid.uuid4())
        if not responder.get("dimension_id"):
            try:
                _atomic_write_json(
                    responder["identity_path"],
                    {"schema": 1, "protocol": RESPONDER_PROTOCOL, "dimension_id": dimension_id},
                )
            except Exception:
                pass
        return dimension_id, "responder"

    dimension_id = generic.get("dimension_id") or str(uuid.uuid4())
    if not generic.get("dimension_id"):
        try:
            _atomic_write_json(
                generic["path"],
                {
                    "schema": 1,
                    "protocol": "holoverse_link_identity_v1",
                    "dimension_id": dimension_id,
                    "note": "Stable identity used by HoloVerse when this project is moved or renamed.",
                },
            )
            return dimension_id, "sidecar"
        except Exception:
            return dimension_id, "host_only"
    return dimension_id, "sidecar"


def _project_icon(root: Path | None) -> Path | None:
    """Return the project's root icon.png, preferring the exact file name.

    Dimension Archive presentation treats a project's own icon.png as its
    canonical visual identity.  A case-insensitive fallback keeps moved projects
    authored on Windows readable when tested on case-sensitive filesystems.
    """
    if root is None:
        return None
    folder = Path(root)
    try:
        exact = folder / "icon.png"
        if exact.is_file():
            return exact
        if not folder.is_dir():
            return None
        for child in folder.iterdir():
            if child.is_file() and child.name.casefold() == "icon.png":
                return child
    except Exception:
        return None
    return None


def inspect_entry(entry: Path, create_identity: bool = False) -> dict:
    entry = Path(entry).expanduser().resolve()
    if entry.name.lower() != "main.py" or not entry.is_file():
        raise ValueError("Select the simulation's main.py")
    root = entry.parent
    responder = _responder_info(root)
    manifest = responder.get("manifest", {}) if responder else {}
    generic = _generic_identity(root)
    responder_id = responder.get("dimension_id", "") if responder else ""
    generic_id = generic.get("dimension_id", "")
    dimension_id = responder_id or generic_id
    identity_mode = "responder" if responder_id else ("sidecar" if generic_id else "fingerprint")
    if create_identity:
        dimension_id, identity_mode = _ensure_project_identity(root)

    entry_from_manifest = entry
    if manifest:
        manifest_entry = _safe_relative(root, str(manifest.get("entry") or "main.py"))
        if manifest_entry and manifest_entry.is_file():
            entry_from_manifest = manifest_entry

    adapter = None
    compatibility = "linked"
    if manifest:
        compatibility = str(manifest.get("compatibility") or "linked").strip().lower()
        adapter_raw = str(manifest.get("native_adapter") or "").strip()
        adapter_path = _safe_relative(root, adapter_raw) if adapter_raw else None
        if adapter_path and adapter_path.is_file():
            adapter = adapter_path
        elif compatibility in {"native", "adapted"}:
            compatibility = "linked"
    if compatibility not in {"linked", "legacy", "adapted", "native", "disabled"}:
        compatibility = "linked"
    host_contract = str(manifest.get("host_contract") or "").strip()
    # An explicit responder claiming a different host contract is never allowed to
    # enter the current native lifecycle merely because it also names an adapter.
    if host_contract and host_contract != NATIVE_HOST_CONTRACT and compatibility in {"native", "adapted"}:
        compatibility = "linked"

    description = str(manifest.get("description") or "").strip()
    if not description:
        description = "External simulation linked by selecting its main.py. Source remains outside HoloVerse and can be adapted independently."

    # Project-root icon.png is the visual identity authority for linked
    # simulations.  Older links may still carry a valid preview.png path; do
    # not let that stale presentation choice outrank a newly supplied icon.
    preview = _project_icon(root)
    if preview is None:
        for raw in (
            manifest.get("preview") if manifest else "",
            "preview.png",
            "title.png",
        ):
            if not raw:
                continue
            candidate = _safe_relative(root, str(raw))
            if candidate and candidate.is_file():
                preview = candidate
                break

    return {
        "schema": LINK_SCHEMA,
        "dimension_id": dimension_id,
        "identity_mode": identity_mode,
        "title": display_name_for_entry(entry_from_manifest, manifest),
        "project_root": str(root),
        "entry_path": str(entry_from_manifest),
        "entry_name": entry_from_manifest.name,
        "fingerprint": project_fingerprint(entry_from_manifest),
        "engine": str(manifest.get("engine") or "").strip().lower() or detect_engine(entry_from_manifest),
        "compatibility": compatibility,
        "native_adapter": str(adapter) if adapter else "",
        "host_contract": host_contract,
        "return_target": str(manifest.get("return_target") or "").strip(),
        "description": description,
        "preview": str(preview) if preview else "",
        "responder": bool(responder),
        "responder_key": str(responder.get("stable_key") or "") if responder else "",
        "last_seen": int(time.time()),
    }


def merge_link(state: dict, entry: Path) -> tuple[dict, bool]:
    """Register/relink an entry. Returns (link_payload, updated_existing)."""
    info = inspect_entry(entry, create_identity=True)
    links = state.setdefault("links", {})
    if not isinstance(links, dict):
        links = state["links"] = {}

    dimension_id = str(info.get("dimension_id") or "").strip()
    responder_key = str(info.get("responder_key") or "").strip()
    fingerprint = str(info.get("fingerprint") or "")
    existing_key = ""
    for key, old in links.items():
        if not isinstance(old, dict):
            continue
        if dimension_id and str(old.get("dimension_id") or "") == dimension_id:
            existing_key = str(key)
            break
        if responder_key and str(old.get("responder_key") or "") == responder_key:
            existing_key = str(key)
            break
        if fingerprint and str(old.get("fingerprint") or "") == fingerprint:
            existing_key = str(key)
            break

    key = existing_key or dimension_id or str(uuid.uuid4())
    old = links.get(key) if isinstance(links.get(key), dict) else {}
    roots = []
    project_root = Path(info["project_root"])
    automatic_roots = [project_root.parent]
    # One level above the containing bundle lets a renamed MatrixCore-style
    # collection recover without scanning an entire drive.
    if project_root.parent.parent != project_root.parent:
        automatic_roots.append(project_root.parent.parent)
    for value in list(old.get("search_roots") or []) + [str(p) for p in automatic_roots]:
        value = str(value or "").strip()
        if value and value not in roots:
            roots.append(value)
    payload = {**old, **info, "search_roots": roots[:8], "missing": False}
    links[key] = payload
    state["last_link_dir"] = str(Path(info["entry_path"]).parent)
    return payload, bool(existing_key)


def _candidate_identity(entry: Path) -> tuple[str, str, str]:
    root = entry.parent
    responder = _responder_info(root)
    responder_key = str(responder.get("stable_key") or "") if responder else ""
    if responder and responder.get("dimension_id"):
        return str(responder["dimension_id"]), "", responder_key
    generic = _generic_identity(root)
    if generic.get("dimension_id"):
        return str(generic["dimension_id"]), "", responder_key
    return "", project_fingerprint(entry), responder_key


def recover_link(link: dict, shared_search_roots: list[str] | None = None) -> dict:
    """Resolve a moved/renamed project conservatively without scanning whole drives."""
    if not isinstance(link, dict):
        return {}
    wanted_id = str(link.get("dimension_id") or "").strip()
    wanted_key = str(link.get("responder_key") or "").strip()
    wanted_fp = str(link.get("fingerprint") or "").strip()
    current = Path(str(link.get("entry_path") or ""))
    if current.is_file() and current.name.lower() == "main.py":
        try:
            # A fresh ZIP replacement may have removed HoloVerse's UUID sidecar.
            # Re-seed it from durable host state before inspecting the same path.
            _repair_responder_identity(current.parent, wanted_id)
            fresh = inspect_entry(current, create_identity=False)
            # Never let a missing sidecar erase durable identity during refresh.
            if wanted_id and not str(fresh.get("dimension_id") or "").strip():
                fresh["dimension_id"] = wanted_id
            if wanted_key and not str(fresh.get("responder_key") or "").strip():
                fresh["responder_key"] = wanted_key
            return {**link, **fresh, "missing": False}
        except Exception:
            pass

    roots = []
    for raw in list(link.get("search_roots") or []) + list(shared_search_roots or []):
        raw = str(raw or "").strip()
        if raw and raw not in roots:
            roots.append(raw)

    checked = 0
    for raw in roots:
        root = Path(raw).expanduser()
        if not root.exists() or not root.is_dir():
            continue
        try:
            iterator = root.rglob("main.py")
            for candidate in iterator:
                checked += 1
                if checked > MAX_RECOVERY_MAIN_FILES:
                    return {**link, "missing": True}
                try:
                    cid, cfp, ckey = _candidate_identity(candidate)
                except Exception:
                    continue
                identity_match = bool(wanted_id and cid == wanted_id)
                responder_match = bool(wanted_key and ckey and ckey == wanted_key)
                fingerprint_match = bool(wanted_fp and cfp == wanted_fp)
                if identity_match or responder_match or fingerprint_match:
                    try:
                        if wanted_id and responder_match and not cid:
                            _repair_responder_identity(candidate.parent, wanted_id)
                        fresh = inspect_entry(candidate, create_identity=False)
                    except Exception:
                        continue
                    if wanted_id and not str(fresh.get("dimension_id") or "").strip():
                        fresh["dimension_id"] = wanted_id
                    if wanted_key and not str(fresh.get("responder_key") or "").strip():
                        fresh["responder_key"] = wanted_key
                    fresh["search_roots"] = list(dict.fromkeys(roots + [str(candidate.parent.parent)]))[:8]
                    return {**link, **fresh, "missing": False, "recovered_at": int(time.time())}
        except Exception:
            continue
    return {**link, "missing": True}


def refresh_links(state: dict) -> bool:
    links = state.get("links") if isinstance(state.get("links"), dict) else {}
    shared = []
    for item in links.values():
        if not isinstance(item, dict):
            continue
        for root in item.get("search_roots") or []:
            root = str(root or "").strip()
            if root and root not in shared:
                shared.append(root)
    changed = False
    for key, item in list(links.items()):
        if not isinstance(item, dict):
            continue
        fresh = recover_link(item, shared_search_roots=shared)
        if fresh != item:
            links[key] = fresh
            changed = True
    return changed
