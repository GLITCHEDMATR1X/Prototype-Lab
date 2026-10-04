"""Operation StarFall as a HoloVerse dimension (linked, own window).  Pass 282.65.

HoloVerse starts this game as a separate process from a HoloSpace planet or Gleebs'
Dimension Archive and comes back when the process ends.  Optional helpers:

  hosted()                  True when HoloVerse launched this process
  quit_label("QUIT")        "RETURN TO HOLOVERSE" while hosted, else the given text
  report_to_holoverse(...)  leave Gleebs a small result before exiting (never raises)
  install_exit_report(fn)   report automatically whenever the process ends

Standard library only, so it can be imported before Panda3D.  Run on its own, nothing changes.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

MODE_ID = "operation_starfall"
TITLE = "Operation StarFall"


def hosted() -> bool:
    return (os.environ.get("HOLOVERSE_LINK_MODE", "") == "compatibility_external"
            and bool(os.environ.get("HOLOVERSE_RETURN_SIGNAL_PATH", "")))


def quit_label(standalone: str = "QUIT") -> str:
    return "RETURN TO HOLOVERSE" if hosted() else standalone


def report_to_holoverse(completed: bool = False, signal: str = "", gleebs_response: str = "", **extra) -> bool:
    global _REPORTED
    if not hosted():
        return False
    try:
        path = Path(os.environ["HOLOVERSE_RETURN_SIGNAL_PATH"])
        path.parent.mkdir(parents=True, exist_ok=True)
        result = {"mode_id": MODE_ID, "title": TITLE, "completed": bool(completed), "signal": str(signal),
                  "gleebs_response": str(gleebs_response)}
        result.update(extra)
        payload = {"schema": 1, "source": MODE_ID, "reason": "dimension_exit", "timestamp": time.time(), "result": result}
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        _REPORTED = True
        return True
    except Exception:
        return False


_REPORTED = False


def install_exit_report(provider) -> None:
    """Report automatically when the process ends (window closed, ESC, QUIT).

    provider() returns a dict of report_to_holoverse keyword arguments.  An explicit
    report_to_holoverse() call made earlier wins; this only fills the gap.  Never raises.
    """
    if not hosted():
        return
    import atexit

    def _on_exit():
        if _REPORTED:
            return
        try:
            data = provider() or {}
        except Exception:
            data = {}
        report_to_holoverse(**data)

    atexit.register(_on_exit)
