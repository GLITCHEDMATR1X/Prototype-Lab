from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys
import traceback

GAME_ROOT = Path(__file__).resolve().parent
MAIN = GAME_ROOT / "main.py"


def _consume_handoff_marker() -> Path | None:
    """Consume the private launcher handoff argument before main.py sees argv."""
    marker: Path | None = None
    cleaned = [sys.argv[0]]
    args = list(sys.argv[1:])
    i = 0
    while i < len(args):
        if args[i] == "--gx-handoff" and i + 1 < len(args):
            marker = Path(args[i + 1])
            i += 2
            continue
        cleaned.append(args[i])
        i += 1
    sys.argv[:] = cleaned
    return marker


def _acknowledge_handoff(marker: Path | None) -> None:
    if marker is None:
        return
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(os.getpid()), encoding="ascii")
    except Exception:
        pass


def _become_standalone_game() -> None:
    """Remove all launcher/host identity before the Panda3D game is imported."""
    for key in ("GX_GENERIC_LAUNCHER", "GX_GAME_ROOT", "HOLOVERSE_EMBEDDED_MODE"):
        os.environ.pop(key, None)
    os.environ["MIRRORS_LIMBO_STANDALONE"] = "1"


def _log_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        root = Path(base) / "GLITCHED MATRIX" / "Mirrors Limbo"
    else:
        root = GAME_ROOT / "logs"
    root.mkdir(parents=True, exist_ok=True)
    return root / "startup_error.txt"


def main() -> int:
    marker = _consume_handoff_marker()
    _become_standalone_game()
    _acknowledge_handoff(marker)
    os.chdir(GAME_ROOT)
    sys.path.insert(0, str(GAME_ROOT))
    try:
        runpy.run_path(str(MAIN), run_name="__main__")
        return 0
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else 0
    except BaseException:
        try:
            _log_path().write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())
