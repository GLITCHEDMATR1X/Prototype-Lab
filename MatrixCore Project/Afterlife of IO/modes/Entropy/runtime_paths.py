from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

APP_NAME = "Entropy"
APP_AUTHOR = "GLITCHED MATRIX"
PROJECT_ROOT = Path(__file__).resolve().parent


def _platform_root() -> Path:
    override = os.environ.get("ENTROPY_USER_DATA", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_AUTHOR / APP_NAME
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_AUTHOR / APP_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME")
        if base:
            return Path(base) / "glitched-matrix" / "entropy"
        return Path.home() / ".local" / "share" / "glitched-matrix" / "entropy"

    return Path.home() / f".{APP_NAME.lower()}"


def _select_user_root() -> Path:
    """Return a writable per-user root, falling back to the OS temp directory.

    Packaged builds may run from read-only folders or under restricted user
    profiles. Entropy never writes saves, settings, logs, crash bundles, or
    screenshots into the shipping directory.
    """
    preferred = _platform_root()
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return preferred
    except OSError:
        fallback = Path(tempfile.gettempdir()) / APP_AUTHOR / APP_NAME
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


USER_ROOT = _select_user_root()
SAVE_DIR = USER_ROOT / "saves"
CONFIG_DIR = USER_ROOT / "config"
LOG_DIR = USER_ROOT / "logs"
CRASH_DIR = USER_ROOT / "crashes"
SCREENSHOT_DIR = USER_ROOT / "screenshots"
CACHE_DIR = USER_ROOT / "cache"
SAVE_PATH = SAVE_DIR / "save_state.json"
SAVE_BACKUP_PATH = SAVE_DIR / "save_state.previous_good.json"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
RUNTIME_LOG = LOG_DIR / "runtime.log"
CRASH_LOG = LOG_DIR / "crash.log"
FAULT_LOG = LOG_DIR / "fatal_fault.log"
SESSION_STATE_PATH = LOG_DIR / "session_state.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "schema_version": 4,
    "window_mode": "fullscreen",
    "target_width": 1920,
    "target_height": 1080,
    "bordered_width": 1600,
    "bordered_height": 900,
    "hud_visible": True,
    "controls_overlay_seen": False,
    "mouse_sensitivity": 1.0,
    "master_volume": 1.0,
    "music_volume": 0.85,
    "sfx_volume": 0.95,
    "ambience_volume": 0.80,
    "audio_muted": False,
    "presentation_filter": "smooth",
}

_LAST_SAVE_READ_INFO: Dict[str, Any] = {
    "source": "none",
    "recovered": False,
    "error": "",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_runtime_dirs() -> None:
    for path in (SAVE_DIR, CONFIG_DIR, LOG_DIR, CRASH_DIR, SCREENSHOT_DIR, CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)


def migrate_legacy_files() -> None:
    """Copy old writable files out of the shipping folder without deleting them."""
    ensure_runtime_dirs()
    legacy_save = PROJECT_ROOT / "save_state.json"
    if legacy_save.is_file() and not SAVE_PATH.exists():
        try:
            shutil.copy2(legacy_save, SAVE_PATH)
        except OSError:
            pass

    legacy_logs = PROJECT_ROOT / "logs"
    if legacy_logs.is_dir():
        for name in ("runtime.log", "crash.log"):
            src = legacy_logs / name
            dst = LOG_DIR / f"legacy_{name}"
            if src.is_file() and not dst.exists():
                try:
                    shutil.copy2(src, dst)
                except OSError:
                    pass


def _fsync_directory(directory: Path) -> None:
    """Best-effort persistence of the directory entry after an atomic replace."""
    try:
        flags = getattr(os, "O_DIRECTORY", 0) | os.O_RDONLY
        fd = os.open(str(directory), flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _atomic_json_write(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON through a same-directory temporary file and atomic replace.

    The payload is flushed and fsynced before replacement.  The directory entry
    is then fsynced where the host supports it.  This keeps a power loss or
    forced termination from leaving a half-written JSON file behind.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        os.replace(tmp_name, path)
        _fsync_directory(path.parent)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _read_json_dict(path: Path) -> Tuple[Dict[str, Any], str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}, "root is not an object"
        return raw, ""
    except FileNotFoundError:
        return {}, "missing"
    except (OSError, ValueError, TypeError) as exc:
        return {}, f"{type(exc).__name__}: {exc}"


def load_settings() -> Dict[str, Any]:
    ensure_runtime_dirs()
    settings = dict(DEFAULT_SETTINGS)
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            old_schema = int(raw.get("schema_version", 0) or 0)
            for key in DEFAULT_SETTINGS:
                if key in raw:
                    settings[key] = raw[key]
            if old_schema < 2:
                settings["window_mode"] = "fullscreen"
            if old_schema < 4:
                settings["schema_version"] = 4
                settings.setdefault("bordered_width", 1600)
                settings.setdefault("bordered_height", 900)
                settings.setdefault("music_volume", 0.85)
                settings.setdefault("sfx_volume", 0.95)
                settings.setdefault("ambience_volume", 0.80)
                settings.setdefault("audio_muted", False)
                try:
                    _atomic_json_write(SETTINGS_PATH, settings)
                except OSError:
                    pass
    except (OSError, ValueError, TypeError):
        pass
    return settings


def save_settings(settings: Dict[str, Any]) -> None:
    payload = dict(DEFAULT_SETTINGS)
    for key in DEFAULT_SETTINGS:
        if key in settings:
            payload[key] = settings[key]
    _atomic_json_write(SETTINGS_PATH, payload)


def write_save(data: Dict[str, Any], path: Path | None = None) -> None:
    """Crash-resistant save with a validated previous-good generation.

    The previous primary save is copied into ``save_state.previous_good.json``
    only when it parses as a JSON object.  The new primary is then atomically
    published and read back before the write is considered successful.
    """
    target = path or SAVE_PATH
    target = Path(target)
    if target == SAVE_PATH:
        previous, _err = _read_json_dict(SAVE_PATH)
        if previous:
            _atomic_json_write(SAVE_BACKUP_PATH, previous)

    _atomic_json_write(target, data)
    verify, error = _read_json_dict(target)
    if not verify:
        raise OSError(f"save verification failed: {error or 'empty payload'}")
    if target == SAVE_PATH and not SAVE_BACKUP_PATH.exists():
        # A brand-new profile still gets a recovery generation immediately;
        # subsequent writes rotate the prior validated primary into this slot.
        _atomic_json_write(SAVE_BACKUP_PATH, verify)


def read_save(path: Path | None = None) -> Dict[str, Any]:
    """Read the primary save, recovering from previous-good if necessary."""
    global _LAST_SAVE_READ_INFO
    target = Path(path or SAVE_PATH)
    raw, error = _read_json_dict(target)
    if raw:
        _LAST_SAVE_READ_INFO = {"source": "primary", "recovered": False, "error": ""}
        return raw

    if target == SAVE_PATH:
        backup, backup_error = _read_json_dict(SAVE_BACKUP_PATH)
        if backup:
            try:
                _atomic_json_write(SAVE_PATH, backup)
                restore_error = ""
            except OSError as exc:
                restore_error = f"; primary restore failed: {exc}"
            _LAST_SAVE_READ_INFO = {
                "source": "previous_good",
                "recovered": True,
                "error": f"primary {error}{restore_error}",
            }
            return backup
        error = f"primary {error}; previous_good {backup_error}"

    _LAST_SAVE_READ_INFO = {"source": "none", "recovered": False, "error": error}
    return {}


def get_last_save_read_info() -> Dict[str, Any]:
    return dict(_LAST_SAVE_READ_INFO)


def _read_session_state() -> Dict[str, Any]:
    raw, _error = _read_json_dict(SESSION_STATE_PATH)
    return raw


def mark_session_started(build: str, verification: bool = False) -> Dict[str, Any]:
    """Mark this process active and report whether the prior run was unclean."""
    ensure_runtime_dirs()
    if verification:
        return {"previous_unclean": False, "previous": {}}
    previous = _read_session_state()
    previous_unclean = bool(previous and previous.get("state") in {"active", "crashed"})
    payload = {
        "schema_version": 1,
        "state": "active",
        "build": str(build),
        "started_at_utc": _utc_now(),
        "last_checkpoint_utc": _utc_now(),
        "last_checkpoint_reason": "startup",
    }
    _atomic_json_write(SESSION_STATE_PATH, payload)
    return {"previous_unclean": previous_unclean, "previous": previous}


def mark_session_checkpoint(reason: str) -> None:
    state = _read_session_state()
    if not state or state.get("state") != "active":
        return
    state["last_checkpoint_utc"] = _utc_now()
    state["last_checkpoint_reason"] = str(reason)
    _atomic_json_write(SESSION_STATE_PATH, state)


def mark_session_crashed(crash_id: str = "") -> None:
    state = _read_session_state()
    state.update({
        "schema_version": 1,
        "state": "crashed",
        "ended_at_utc": _utc_now(),
        "crash_id": str(crash_id),
    })
    _atomic_json_write(SESSION_STATE_PATH, state)


def mark_session_clean_exit() -> None:
    state = _read_session_state()
    state.update({
        "schema_version": 1,
        "state": "clean",
        "ended_at_utc": _utc_now(),
        "last_checkpoint_reason": "clean_exit",
    })
    _atomic_json_write(SESSION_STATE_PATH, state)


migrate_legacy_files()
