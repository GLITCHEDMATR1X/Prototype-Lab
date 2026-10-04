from __future__ import annotations

import datetime as _datetime
import os
import platform
import sys
import traceback
from pathlib import Path

from game.runtime_paths import crash_log_path
from game.version import BUILD_LABEL, PROJECT_NAME, VERSION


def write_crash_report(exc: BaseException) -> Path:
    path = crash_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        PROJECT_NAME,
        BUILD_LABEL,
        f"Version: {VERSION}",
        f"Time UTC: {_datetime.datetime.now(_datetime.timezone.utc).isoformat()}",
        f"Python: {sys.version}",
        f"Platform: {platform.platform()}",
        f"Executable: {sys.executable}",
        f"Working directory: {os.getcwd()}",
        "",
        "Unhandled exception:",
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def show_native_crash_message(path: Path) -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            0,
            f"GHOST SIGNAL: UTOPIA could not continue.\n\nA crash report was written to:\n{path}",
            "GHOST SIGNAL: UTOPIA",
            0x10,
        )
    except Exception:
        pass
