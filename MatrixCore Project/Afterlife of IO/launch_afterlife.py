from __future__ import annotations

"""Afterlife of IO standard-library bootstrap.

This file exists so startup diagnostics begin before main.py imports pygame/SDL.
It intentionally imports no third-party package itself.
"""

import faulthandler
import os
import platform
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

from build_info import DISPLAY_TITLE

ROOT = Path(__file__).resolve().parent


def diagnostic_dir() -> Path:
    candidates: list[Path] = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "GLITCHED MATRIX" / "Afterlife of IO")
    candidates += [ROOT / "saves", Path(tempfile.gettempdir()) / "GLITCHED_MATRIX" / "Afterlife of IO"]
    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".bootstrap_write_probe"
            probe.write_text("ok", encoding="ascii")
            probe.unlink(missing_ok=True)
            return path
        except Exception:
            continue
    return ROOT


LOG_DIR = diagnostic_dir()
LOG_PATH = LOG_DIR / "startup.log"
CONSOLE_PATH = LOG_DIR / "startup_console.log"


def write(line: str) -> None:
    try:
        with LOG_PATH.open("a", encoding="utf-8") as h:
            h.write(f"[{datetime.now().isoformat(timespec='seconds')}] {line}\n")
    except Exception:
        pass


def run() -> int:
    # Replace old startup information each launch, so the file always describes
    # the most recent attempt instead of becoming an unbounded historical log.
    try:
        LOG_PATH.write_text("", encoding="utf-8")
    except Exception:
        pass
    write(f"BOOTSTRAP {DISPLAY_TITLE} begin")
    write(f"executable={sys.executable!r}")
    write(f"python={sys.version!r}")
    write(f"platform={platform.platform()!r}")
    write(f"cwd={os.getcwd()!r}")
    write(f"argv={sys.argv!r}")

    fault_handle = None
    try:
        fault_handle = LOG_PATH.open("a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=fault_handle, all_threads=True)
        write("faulthandler enabled before importing main/pygame")
    except Exception as exc:
        write(f"faulthandler setup failed: {type(exc).__name__}: {exc}")

    try:
        write("importing main.py (pygame import begins inside main)")
        import main as game_main
        write("main.py import completed")
        rc = game_main.main()
        write(f"game returned normally rc={rc!r}")
        return int(rc or 0)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        write(f"SystemExit code={code!r}")
        return int(code)
    except BaseException as exc:
        write(f"bootstrap caught {type(exc).__name__}: {exc}")
        try:
            with LOG_PATH.open("a", encoding="utf-8") as h:
                traceback.print_exc(file=h)
        except Exception:
            pass
        return 70
    finally:
        try:
            if fault_handle:
                fault_handle.flush()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(run())
