from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path

PROTOCOL = "holoverse_responder_v1"
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
MANIFEST_PATH = HERE / "holoverse_dimension.json"
IDENTITY_PATH = HERE / "identity.json"
MAX_SOURCE_BYTES = 128 * 1024


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


def _safe_rel_path(project_root: Path, raw: str) -> Path | None:
    try:
        raw_path = Path(str(raw or "main.py"))
        candidate = (project_root / raw_path).resolve()
        root = project_root.resolve()
        candidate.relative_to(root)
        return candidate
    except Exception:
        return None


def _entry_path(manifest: dict) -> Path | None:
    return _safe_rel_path(PROJECT_ROOT, str(manifest.get("entry") or "main.py"))


def _detect_engine(entry: Path | None) -> str:
    if entry is None or not entry.is_file():
        return "missing"
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
    if entry.suffix.lower() == ".py":
        return "python"
    return "unknown"


def _source_fingerprint(entry: Path | None) -> str:
    h = hashlib.sha256()
    h.update(PROTOCOL.encode("utf-8"))
    if entry is None or not entry.is_file():
        h.update(b"missing-entry")
        return h.hexdigest()
    try:
        h.update(entry.read_bytes()[:MAX_SOURCE_BYTES])
    except Exception:
        h.update(str(entry.name).encode("utf-8", errors="ignore"))
    # Folder names and absolute paths are deliberately excluded.
    try:
        siblings = sorted(
            p.name.lower()
            for p in PROJECT_ROOT.iterdir()
            if p.name.lower() not in {"__pycache__", ".git", "logs", "crash_reports"}
        )[:128]
        h.update("\n".join(siblings).encode("utf-8", errors="ignore"))
    except Exception:
        pass
    return h.hexdigest()


def _display_name(manifest: dict) -> str:
    title = str(manifest.get("title") or "").strip()
    if title and title.upper() != "AUTO":
        return title
    entry = _entry_path(manifest)
    if entry and entry.is_file():
        try:
            text = entry.read_bytes()[:MAX_SOURCE_BYTES].decode("utf-8", errors="ignore")
            for pat in (
                r'^\s*GAME_NAME\s*=\s*["\']([^"\']+)["\']',
                r'^\s*TITLE\s*=\s*["\']([^"\']+)["\']',
                r'^\s*APP_NAME\s*=\s*["\']([^"\']+)["\']',
            ):
                match = re.search(pat, text, flags=re.MULTILINE)
                if match:
                    return match.group(1).strip()
        except Exception:
            pass
    return PROJECT_ROOT.name


def ensure_identity() -> dict:
    current = _read_json(IDENTITY_PATH)
    dimension_id = str(current.get("dimension_id") or "").strip()
    try:
        uuid.UUID(dimension_id)
    except Exception:
        dimension_id = str(uuid.uuid4())
        current = {
            "schema": 1,
            "protocol": PROTOCOL,
            "dimension_id": dimension_id,
        }
        _atomic_write_json(IDENTITY_PATH, current)
    return current


def describe(create_identity: bool = False) -> dict:
    manifest = _read_json(MANIFEST_PATH)
    identity = _read_json(IDENTITY_PATH)
    if create_identity and not identity.get("dimension_id"):
        identity = ensure_identity()
    entry = _entry_path(manifest)
    adapter_raw = str(manifest.get("native_adapter") or "").strip()
    adapter = _safe_rel_path(PROJECT_ROOT, adapter_raw) if adapter_raw else None
    dimension_id = str(identity.get("dimension_id") or "").strip()
    return {
        "schema": 1,
        "protocol": PROTOCOL,
        "dimension_id": dimension_id,
        "identity_portable": bool(dimension_id),
        "title": _display_name(manifest),
        "project_root": str(PROJECT_ROOT),
        "entry": str(entry) if entry else "",
        "entry_exists": bool(entry and entry.is_file()),
        "engine": _detect_engine(entry),
        "fingerprint": _source_fingerprint(entry),
        "compatibility": str(manifest.get("compatibility") or "linked").strip().lower(),
        "native_adapter": str(adapter) if adapter else "",
        "native_adapter_exists": bool(adapter and adapter.is_file()),
        "healthy": bool(entry and entry.is_file()),
    }


def launch_contract() -> dict:
    info = describe(create_identity=True)
    entry = Path(info["entry"]) if info.get("entry") else None
    if entry is None or not entry.is_file():
        return {"ok": False, "reason": "entry_missing", "describe": info}
    return {
        "ok": True,
        "protocol": PROTOCOL,
        "dimension_id": info["dimension_id"],
        "cwd": str(PROJECT_ROOT),
        "argv": [sys.executable, str(entry)],
        "env": {
            "HOLOVERSE_DIMENSION_ID": info["dimension_id"],
            "HOLOVERSE_PROJECT_ROOT": str(PROJECT_ROOT),
            "HOLOVERSE_LINK_MODE": "compatibility_external",
        },
        "describe": info,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="HoloVerse external-dimension responder")
    parser.add_argument("command", nargs="?", default="describe", choices=("describe", "health", "ensure-identity", "launch-contract"))
    args = parser.parse_args()
    if args.command == "ensure-identity":
        ensure_identity()
        payload = describe(create_identity=False)
    elif args.command == "launch-contract":
        payload = launch_contract()
    elif args.command == "health":
        payload = describe(create_identity=False)
        payload = {"ok": bool(payload.get("healthy")), **payload}
    else:
        payload = describe(create_identity=False)
    print(json.dumps(payload, sort_keys=True))
    if args.command == "health" and not payload.get("ok"):
        return 2
    if args.command == "launch-contract" and not payload.get("ok"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
