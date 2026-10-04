"""Local-only crash diagnostics for Entropy Pass 30.

No report is uploaded automatically.  Reports deliberately omit save contents,
environment variables, user names, and arbitrary filesystem listings.
"""
from __future__ import annotations

import faulthandler
import json
import os
import platform
import sys
import threading
import traceback
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from runtime_paths import (
    CRASH_DIR,
    CRASH_LOG,
    FAULT_LOG,
    RUNTIME_LOG,
    SAVE_BACKUP_PATH,
    SAVE_PATH,
    USER_ROOT,
    ensure_runtime_dirs,
    mark_session_crashed,
)

_BUILD = "unknown"
_CONTEXT_PROVIDER: Optional[Callable[[], Dict[str, Any]]] = None
_FAULT_HANDLE = None
_LAST_BUNDLE: Optional[Path] = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _redact_text(text: str) -> str:
    """Redact common per-user path prefixes from diagnostics."""
    out = str(text or "")
    candidates = []
    try:
        candidates.extend((str(Path.home()), os.path.expanduser("~"), str(USER_ROOT)))
    except Exception:
        pass
    for raw in sorted({v for v in candidates if v}, key=len, reverse=True):
        for variant in {raw, raw.replace("\\", "/"), raw.replace("/", "\\")}:
            if variant:
                out = out.replace(variant, "<USER_DATA>")
    return out


def _safe_context() -> Dict[str, Any]:
    if _CONTEXT_PROVIDER is None:
        return {}
    try:
        data = _CONTEXT_PROVIDER()
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        return {"context_error": f"{type(exc).__name__}: {exc}"}


def _tail(path: Path, limit: int = 32768) -> str:
    try:
        raw = path.read_bytes()
        return raw[-limit:].decode("utf-8", errors="replace")
    except OSError:
        return ""


def _save_meta(path: Path) -> Dict[str, Any]:
    try:
        stat = path.stat()
        return {
            "present": True,
            "bytes": int(stat.st_size),
            "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
        }
    except OSError:
        return {"present": False, "bytes": 0}


def _runtime_meta() -> Dict[str, Any]:
    return {
        "build": _BUILD,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "save_primary": _save_meta(SAVE_PATH),
        "save_previous_good": _save_meta(SAVE_BACKUP_PATH),
        "user_data_root_kind": "per-user",
    }


def set_context_provider(provider: Optional[Callable[[], Dict[str, Any]]]) -> None:
    global _CONTEXT_PROVIDER
    _CONTEXT_PROVIDER = provider


def report_exception(exc_type, exc, tb, phase: str = "unhandled") -> Optional[Path]:
    """Write a verified, non-empty local crash bundle and return its path."""
    global _LAST_BUNDLE
    ensure_runtime_dirs()
    crash_id = "ENT-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6].upper()
    stem = f"Entropy_crash_{crash_id}"
    txt_path = CRASH_DIR / f"{stem}.txt"
    json_path = CRASH_DIR / f"{stem}.json"
    zip_tmp = CRASH_DIR / f".{stem}.zip.tmp"
    zip_path = CRASH_DIR / f"{stem}.zip"

    trace_text = _redact_text("".join(traceback.format_exception(exc_type, exc, tb)))
    context = _safe_context()
    payload = {
        "schema_version": 1,
        "crash_id": crash_id,
        "time_utc": _utc_now(),
        "phase": str(phase),
        "exception_type": getattr(exc_type, "__name__", str(exc_type)),
        "exception": _redact_text(str(exc)),
        "traceback": trace_text,
        "runtime": _runtime_meta(),
        "game_context": context,
        "privacy": {
            "automatic_upload": False,
            "save_contents_included": False,
            "environment_dump_included": False,
        },
    }

    try:
        txt = [
            "ENTROPY LOCAL CRASH REPORT",
            f"Crash ID: {crash_id}",
            f"Time UTC: {payload['time_utc']}",
            f"Build: {_BUILD}",
            f"Phase: {phase}",
            "",
            "Nothing was uploaded automatically.",
            "Save-file contents are not included in this bundle.",
            "",
            "GAME CONTEXT",
            json.dumps(context, indent=2, sort_keys=True),
            "",
            "TRACEBACK",
            trace_text,
        ]
        txt_path.write_text("\n".join(txt).rstrip() + "\n", encoding="utf-8")
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        # Keep the legacy crash.log useful as a plain append-only ledger.
        with CRASH_LOG.open("a", encoding="utf-8") as handle:
            handle.write("\n" + "=" * 80 + "\n")
            handle.write(f"[{payload['time_utc']}] {crash_id} phase={phase}\n")
            handle.write(trace_text)
            if not trace_text.endswith("\n"):
                handle.write("\n")
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass

        runtime_tail = _redact_text(_tail(RUNTIME_LOG))
        fault_tail = _redact_text(_tail(FAULT_LOG))
        with zipfile.ZipFile(zip_tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(txt_path, arcname=txt_path.name)
            archive.write(json_path, arcname=json_path.name)
            if runtime_tail:
                archive.writestr("runtime_log_tail.txt", runtime_tail)
            if fault_tail:
                archive.writestr("fatal_fault_log_tail.txt", fault_tail)
        with zipfile.ZipFile(zip_tmp, "r") as archive:
            bad = archive.testzip()
            if bad is not None or len(archive.namelist()) < 2:
                raise OSError(f"crash ZIP integrity failed: {bad}")
        if zip_tmp.stat().st_size <= 0:
            raise OSError("crash ZIP was empty")
        os.replace(zip_tmp, zip_path)
        mark_session_crashed(crash_id)
        _LAST_BUNDLE = zip_path
        return zip_path
    except Exception:
        try:
            zip_tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def install(build: str) -> None:
    """Install Python/thread/unraisable hooks and durable faulthandler output."""
    global _BUILD, _FAULT_HANDLE
    _BUILD = str(build)
    ensure_runtime_dirs()

    # The file starts non-empty so a low-level fault log can never masquerade as
    # a successful zero-byte crash report.
    try:
        _FAULT_HANDLE = FAULT_LOG.open("a", encoding="utf-8")
        _FAULT_HANDLE.write(f"\n[{_utc_now()}] Entropy fault handler armed — build={_BUILD}\n")
        _FAULT_HANDLE.flush()
        try:
            os.fsync(_FAULT_HANDLE.fileno())
        except OSError:
            pass
        faulthandler.enable(file=_FAULT_HANDLE, all_threads=True)
    except Exception:
        _FAULT_HANDLE = None

    def _sys_hook(exc_type, exc, tb):
        report_exception(exc_type, exc, tb, phase="sys.excepthook")
        traceback.print_exception(exc_type, exc, tb)

    sys.excepthook = _sys_hook

    if hasattr(threading, "excepthook"):
        def _thread_hook(args):
            report_exception(args.exc_type, args.exc_value, args.exc_traceback, phase=f"thread:{getattr(args.thread, 'name', 'unknown')}")
        threading.excepthook = _thread_hook

    if hasattr(sys, "unraisablehook"):
        def _unraisable_hook(args):
            exc = getattr(args, "exc_value", RuntimeError("unraisable exception"))
            report_exception(type(exc), exc, getattr(args, "exc_traceback", None), phase="unraisable")
        sys.unraisablehook = _unraisable_hook


def get_last_bundle() -> Optional[Path]:
    return _LAST_BUNDLE


def shutdown() -> None:
    global _FAULT_HANDLE
    try:
        if faulthandler.is_enabled():
            faulthandler.disable()
    except Exception:
        pass
    if _FAULT_HANDLE is not None:
        try:
            _FAULT_HANDLE.flush()
            _FAULT_HANDLE.close()
        except Exception:
            pass
        _FAULT_HANDLE = None
