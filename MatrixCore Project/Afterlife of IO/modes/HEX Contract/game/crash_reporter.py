from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import threading
import traceback
from typing import Any, Callable
import zipfile


REPORT_SCHEMA_VERSION = 2
CRASH_DIR_NAME = "crashes"
MAX_REPORT_SETS = 20
CRASH_ROOT_ENV = "HEX_CONTRACT_CRASH_ROOT"


@dataclass
class CrashArtifact:
    report_id: str
    json_path: str
    text_path: str
    bundle_path: str
    fatal_log_path: str | None = None


class CrashReporter:
    """Dependency-free local crash reporter for source and frozen builds.

    The reporter intentionally does not transmit data.  It records only a
    bounded set of runtime/platform fields, sanitized paths, caller-provided
    gameplay state, and recent in-memory breadcrumbs.
    """

    def __init__(self) -> None:
        self.project_root: Path | None = None
        self.crash_root: Path | None = None
        self.build_label = "UNKNOWN"
        self.state_provider: Callable[[], dict[str, Any]] | None = None
        self.breadcrumbs: deque[dict[str, Any]] = deque(maxlen=80)
        self._fault_handle = None
        self._installed = False
        self._reporting = False
        self.last_artifact: CrashArtifact | None = None
        self._session_journal_path: Path | None = None

    def configure(
        self,
        project_root: Path,
        writable_root: Path,
        *,
        build_label: str,
        state_provider: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.crash_root = Path(writable_root).expanduser().resolve() / CRASH_DIR_NAME
        self.crash_root.mkdir(parents=True, exist_ok=True)
        self.build_label = str(build_label)
        self._session_journal_path = self.crash_root / "SESSION_JOURNAL.log"
        self._durable_append(self._session_journal_path, f"SESSION START {datetime.now(timezone.utc).isoformat(timespec='seconds')} / {self.build_label}\n")
        if state_provider is not None:
            self.state_provider = state_provider
        self._rotate_previous_fault_log()
        self._enable_faulthandler()
        self._install_hooks()
        self._prune_old_reports()

    def set_state_provider(self, provider: Callable[[], dict[str, Any]] | None) -> None:
        self.state_provider = provider

    def breadcrumb(self, event: str, **fields: Any) -> None:
        row = {
            "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event": str(event)[:120],
        }
        for key, value in fields.items():
            row[str(key)[:80]] = self._safe_value(value)
        self.breadcrumbs.append(row)
        if self._session_journal_path is not None:
            try:
                self._durable_append(self._session_journal_path, json.dumps(row, ensure_ascii=False) + "\n")
            except Exception:
                pass

    def capture_exception(
        self,
        exc: BaseException,
        *,
        phase: str,
        recoverable: bool,
        extra: dict[str, Any] | None = None,
        tb=None,
    ) -> CrashArtifact | None:
        if self._reporting:
            return self.last_artifact
        self._reporting = True
        try:
            if self.crash_root is None:
                self._fallback_configure()
            assert self.crash_root is not None
            report_id = self._new_report_id()
            now = datetime.now(timezone.utc)
            emergency_path = self.crash_root / f"HEX_CONTRACT_emergency_{report_id}.log"
            self._durable_append(emergency_path, f"HEX CONTRACT EMERGENCY CRASH\nCrash ID: {report_id}\nPhase: {phase}\nException: {type(exc).__name__}: {self._sanitize_text(str(exc))}\n")
            tb_obj = tb if tb is not None else exc.__traceback__
            frames = self._traceback_frames(tb_obj)
            traceback_text = self._sanitize_text("".join(traceback.format_exception(type(exc), exc, tb_obj)))
            state: dict[str, Any] = {}
            if self.state_provider is not None:
                try:
                    provided = self.state_provider() or {}
                    state = self._safe_value(provided)
                except Exception as state_exc:
                    state = {"snapshot_error": f"{type(state_exc).__name__}: {state_exc}"}
            payload = {
                "schema_version": REPORT_SCHEMA_VERSION,
                "report_id": report_id,
                "time_utc": now.isoformat(timespec="seconds"),
                "build": self.build_label,
                "phase": str(phase),
                "recoverable": bool(recoverable),
                "exception": {
                    "type": type(exc).__name__,
                    "message": self._sanitize_text(str(exc))[:4000],
                    "frames": frames,
                    "traceback": traceback_text,
                },
                "runtime": self._runtime_info(),
                "game_state": state,
                "extra": self._safe_value(extra or {}),
                "breadcrumbs": list(self.breadcrumbs),
                "privacy": {
                    "automatic_upload": False,
                    "save_contents_included": False,
                    "environment_variables_included": False,
                    "absolute_user_paths_redacted": True,
                },
            }
            stem = f"HEX_CONTRACT_crash_{report_id}"
            json_path = self.crash_root / f"{stem}.json"
            text_path = self.crash_root / f"{stem}.txt"
            bundle_path = self.crash_root / f"{stem}.zip"
            self._atomic_write(json_path, json.dumps(payload, indent=2, ensure_ascii=False))
            self._atomic_write(text_path, self._human_report(payload))
            self._write_bundle(bundle_path, json_path, text_path, emergency_path)
            latest = self.crash_root / "LATEST_CRASH.txt"
            self._atomic_write(latest, self._human_report(payload) + f"\nBundle: {bundle_path.name}\n")
            artifact = CrashArtifact(
                report_id=report_id,
                json_path=str(json_path),
                text_path=str(text_path),
                bundle_path=str(bundle_path),
                fatal_log_path=str(self.crash_root / "fatal_fault.log"),
            )
            self.last_artifact = artifact
            self.breadcrumb("crash_report_written", report_id=report_id, phase=phase)
            self._prune_old_reports()
            return artifact
        except Exception:
            try:
                traceback.print_exc()
            except Exception:
                pass
            return None
        finally:
            self._reporting = False

    def capture_uncaught(self, exc_type, exc, tb) -> None:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            sys.__excepthook__(exc_type, exc, tb)
            return
        self.capture_exception(exc, phase="uncaught_top_level", recoverable=False, tb=tb)
        try:
            sys.__excepthook__(exc_type, exc, tb)
        except Exception:
            pass

    def show_native_error(self, artifact: CrashArtifact | None, *, title: str = "HEX CONTRACT — Crash Report") -> None:
        if artifact is None:
            message = "HEX CONTRACT stopped unexpectedly. A crash report could not be written."
        else:
            message = (
                "HEX CONTRACT stopped unexpectedly.\n\n"
                f"Crash ID: {artifact.report_id}\n"
                f"Report bundle: {Path(artifact.bundle_path).name}\n\n"
                "The report was saved locally in the game's crash folder."
            )
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, message, title, 0x00000010)
                return
            except Exception:
                pass
        try:
            print(message, file=sys.stderr)
        except Exception:
            pass

    def mark_clean_exit(self) -> None:
        self.breadcrumb("clean_exit")
        if self.crash_root is not None:
            try:
                marker = self.crash_root / "LAST_SESSION_STATUS.json"
                self._atomic_write(marker, json.dumps({
                    "clean_exit": True,
                    "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "build": self.build_label,
                }, indent=2))
            except Exception:
                pass
        self._close_fault_handle()

    def _install_hooks(self) -> None:
        if self._installed:
            return
        sys.excepthook = self.capture_uncaught
        if hasattr(threading, "excepthook"):
            def thread_hook(args):
                exc = args.exc_value
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    return threading.__excepthook__(args)
                self.capture_exception(
                    exc,
                    phase="uncaught_thread",
                    recoverable=False,
                    tb=args.exc_traceback,
                    extra={"thread_name": getattr(args.thread, "name", "")},
                )
            threading.excepthook = thread_hook
        if hasattr(sys, "unraisablehook"):
            def unraisable_hook(args):
                exc = args.exc_value or RuntimeError(str(args.err_msg or "Unraisable exception"))
                self.capture_exception(
                    exc,
                    phase="unraisable_exception",
                    recoverable=True,
                    tb=getattr(args, "exc_traceback", None),
                    extra={"err_msg": str(getattr(args, "err_msg", "") or "")},
                )
            sys.unraisablehook = unraisable_hook
        self._installed = True

    def _enable_faulthandler(self) -> None:
        self._close_fault_handle()
        if self.crash_root is None:
            return
        try:
            path = self.crash_root / "fatal_fault.log"
            existed = path.exists() and path.stat().st_size > 0
            self._fault_handle = path.open("ab", buffering=0)
            if not existed:
                self._fault_handle.write(b"HEX CONTRACT FAULTHANDLER ARMED\n")
                os.fsync(self._fault_handle.fileno())
            faulthandler.enable(file=self._fault_handle, all_threads=True)
        except Exception:
            self._fault_handle = None

    def _close_fault_handle(self) -> None:
        handle = self._fault_handle
        self._fault_handle = None
        if handle is None:
            return
        try:
            faulthandler.disable()
        except Exception:
            pass
        try:
            handle.close()
        except Exception:
            pass

    def _rotate_previous_fault_log(self) -> None:
        if self.crash_root is None:
            return
        path = self.crash_root / "fatal_fault.log"
        try:
            if not path.exists() or path.stat().st_size == 0:
                return
            raw = path.read_text(encoding="utf-8", errors="replace")
            meaningful = raw.replace("HEX CONTRACT FAULTHANDLER ARMED", "").strip()
            if not meaningful:
                path.unlink(missing_ok=True)
                return
            report_id = self._new_report_id(prefix="NATIVE")
            sanitized = self._sanitize_text(raw)
            previous = self.crash_root / f"HEX_CONTRACT_previous_native_fault_{report_id}.txt"
            bundle = self.crash_root / f"HEX_CONTRACT_previous_native_fault_{report_id}.zip"
            header = (
                "HEX CONTRACT PREVIOUS-SESSION NATIVE FAULT\n"
                "=" * 72 + "\n"
                f"Crash ID: {report_id}\n"
                "The prior process ended while Python faulthandler had diagnostic output.\n"
                "This may indicate a fatal interpreter/native-extension failure.\n\n"
            )
            self._atomic_write(previous, header + sanitized)
            with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.write(previous, arcname=previous.name)
            self._atomic_write(
                self.crash_root / "LATEST_CRASH.txt",
                header + f"Bundle: {bundle.name}\n\n" + sanitized,
            )
            path.unlink(missing_ok=True)
        except Exception:
            pass

    def _runtime_info(self) -> dict[str, Any]:
        frozen = bool(getattr(sys, "frozen", False))
        return {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "os": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "frozen": frozen,
            "bundle_mode": "pyinstaller" if frozen else "source",
            "executable_name": Path(sys.executable).name,
            "pid": os.getpid(),
        }

    def _traceback_frames(self, tb) -> list[dict[str, Any]]:
        rows = []
        for frame in traceback.extract_tb(tb) if tb else []:
            rows.append({
                "file": self._sanitize_path(frame.filename),
                "line": int(frame.lineno),
                "function": str(frame.name),
                "code": self._sanitize_text(frame.line or "")[:500],
            })
        return rows

    def _sanitize_path(self, value: str | os.PathLike[str]) -> str:
        text = str(value)
        try:
            path = Path(text).resolve()
            if self.project_root is not None:
                try:
                    rel = path.relative_to(self.project_root)
                    return f"<PROJECT>/{rel.as_posix()}"
                except ValueError:
                    pass
            if self.crash_root is not None:
                try:
                    rel = path.relative_to(self.crash_root.parent)
                    return f"<USER_DATA>/{rel.as_posix()}"
                except ValueError:
                    pass
            home = Path.home().resolve()
            try:
                rel = path.relative_to(home)
                return f"<HOME>/{rel.as_posix()}"
            except ValueError:
                pass
        except Exception:
            pass
        return Path(text).name if ("/" in text or "\\" in text) else text

    def _sanitize_text(self, text: str) -> str:
        result = str(text)
        replacements: list[tuple[str, str]] = []
        if self.project_root is not None:
            replacements.append((str(self.project_root), "<PROJECT>"))
        if self.crash_root is not None:
            replacements.append((str(self.crash_root.parent), "<USER_DATA>"))
        try:
            replacements.append((str(Path.home()), "<HOME>"))
        except Exception:
            pass
        for raw, token in sorted(replacements, key=lambda x: len(x[0]), reverse=True):
            if raw:
                result = result.replace(raw, token).replace(raw.replace("\\", "/"), token)
        return result

    def _safe_value(self, value: Any, depth: int = 0) -> Any:
        if depth > 5:
            return "<MAX_DEPTH>"
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, Path):
            return self._sanitize_path(value)
        if isinstance(value, str):
            return self._sanitize_text(value)[:8000]
        if isinstance(value, dict):
            result = {}
            for index, (key, item) in enumerate(value.items()):
                if index >= 80:
                    result["<TRUNCATED>"] = len(value) - 80
                    break
                result[str(key)[:120]] = self._safe_value(item, depth + 1)
            return result
        if isinstance(value, (list, tuple, set)):
            seq = list(value)
            return [self._safe_value(item, depth + 1) for item in seq[:80]]
        return self._sanitize_text(repr(value))[:1000]

    def _human_report(self, payload: dict[str, Any]) -> str:
        exc = payload["exception"]
        state = payload.get("game_state", {})
        lines = [
            "HEX CONTRACT CRASH REPORT",
            "=" * 72,
            f"Crash ID: {payload['report_id']}",
            f"Time UTC: {payload['time_utc']}",
            f"Build: {payload['build']}",
            f"Phase: {payload['phase']}",
            f"Recoverable: {payload['recoverable']}",
            f"Exception: {exc['type']}: {exc['message']}",
            "",
            "GAME STATE",
            "-" * 72,
            json.dumps(state, indent=2, ensure_ascii=False),
            "",
            "TRACEBACK",
            "-" * 72,
            exc["traceback"],
            "",
            "RECENT EVENTS",
            "-" * 72,
        ]
        for row in payload.get("breadcrumbs", [])[-30:]:
            lines.append(json.dumps(row, ensure_ascii=False))
        lines += [
            "",
            "PRIVACY",
            "-" * 72,
            "This report is local only. It does not include save-file contents or environment variables.",
            "Attach the ZIP with this Crash ID when reporting the issue.",
        ]
        return "\n".join(lines) + "\n"

    def _write_bundle(self, bundle_path: Path, json_path: Path, text_path: Path, emergency_path: Path | None = None) -> None:
        tmp = bundle_path.with_suffix(bundle_path.suffix + ".tmp")
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(json_path, arcname=json_path.name)
            zf.write(text_path, arcname=text_path.name)
            if emergency_path is not None and emergency_path.exists() and emergency_path.stat().st_size > 0:
                zf.write(emergency_path, arcname=emergency_path.name)
            if self._session_journal_path is not None and self._session_journal_path.exists() and self._session_journal_path.stat().st_size > 0:
                zf.write(self._session_journal_path, arcname=self._session_journal_path.name)
            previous_native = sorted(self.crash_root.glob("HEX_CONTRACT_previous_native_fault_*.txt")) if self.crash_root else []
            if previous_native:
                zf.write(previous_native[-1], arcname=previous_native[-1].name)
        with tmp.open("rb") as handle:
            os.fsync(handle.fileno())
        if tmp.stat().st_size <= 0:
            raise OSError("Crash bundle was empty")
        with zipfile.ZipFile(tmp, "r") as zf:
            bad = zf.testzip()
            if bad is not None:
                raise OSError(f"Crash bundle integrity failure: {bad}")
        os.replace(tmp, bundle_path)

    def _atomic_write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        data = text.encode("utf-8", errors="replace")
        with tmp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)

    def _durable_append(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = str(text).encode("utf-8", errors="replace")
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)

    def _new_report_id(self, prefix: str = "CR") -> str:
        now = datetime.now(timezone.utc)
        entropy = f"{now.timestamp()}:{os.getpid()}:{len(self.breadcrumbs)}".encode("utf-8")
        suffix = hashlib.sha256(entropy).hexdigest()[:8].upper()
        return f"{prefix}-{now.strftime('%Y%m%d-%H%M%S')}-{suffix}"

    def _prune_old_reports(self) -> None:
        if self.crash_root is None:
            return
        try:
            json_files = sorted(self.crash_root.glob("HEX_CONTRACT_crash_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old_json in json_files[MAX_REPORT_SETS:]:
                stem = old_json.stem
                for suffix in (".json", ".txt", ".zip"):
                    (self.crash_root / f"{stem}{suffix}").unlink(missing_ok=True)
        except Exception:
            pass

    def _fallback_configure(self) -> None:
        root = Path.cwd().resolve()
        if os.name == "nt" and getattr(sys, "frozen", False) and os.environ.get("LOCALAPPDATA"):
            writable = Path(os.environ["LOCALAPPDATA"]) / "GLITCHED MATRIX" / "HEX CONTRACT"
        else:
            writable = root
        self.configure(root, writable, build_label=self.build_label or "UNKNOWN")


_REPORTER = CrashReporter()


def get_crash_reporter() -> CrashReporter:
    return _REPORTER


def bootstrap_crash_reporter(project_root: Path, *, build_label: str) -> CrashReporter:
    if os.environ.get(CRASH_ROOT_ENV):
        writable = Path(os.environ[CRASH_ROOT_ENV]).expanduser()
    elif os.name == "nt" and getattr(sys, "frozen", False) and os.environ.get("LOCALAPPDATA"):
        writable = Path(os.environ["LOCALAPPDATA"]) / "GLITCHED MATRIX" / "HEX CONTRACT"
    else:
        writable = Path(project_root)
    _REPORTER.configure(Path(project_root), writable, build_label=build_label)
    _REPORTER.breadcrumb("process_bootstrap", frozen=bool(getattr(sys, "frozen", False)))
    return _REPORTER
