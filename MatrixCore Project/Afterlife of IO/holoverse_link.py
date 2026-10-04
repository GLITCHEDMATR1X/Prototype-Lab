"""Afterlife of IO as a HoloVerse dimension (linked, own window).

In the lore, HoloVerse is the present and each dimension is an archive of the past that Gleebs
brought with him. Afterlife of IO is IO's: the afterlife it escaped, carrying the civilization
archives Gleebs needed, before it became HoloVerse's HoloForge guide.

HoloVerse (Gleebs -> Dimension Archive) starts this game as a separate process in its own
window, because it is pygame and HoloVerse is Panda3D. While HoloVerse waits, it shows its
loading overlay; when this process ends, HoloVerse comes back. So:

  - "Quit" reads "RETURN TO HOLOVERSE" while launched from HoloVerse (nothing else changes:
    saves, settings and keys are the game's own, in %LOCALAPPDATA%).
  - On the way out the game leaves HoloVerse a small result (Memory Guardians defeated,
    whether the campaign is complete) in the file HoloVerse names in HOLOVERSE_RETURN_SIGNAL_PATH.

Run on its own (RUN_GAME.bat, python main.py, the Lab) none of this is active.
Standard library only, so it can be imported before pygame.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

MODE_ID = "afterlife_of_io"
TITLE = "Afterlife of IO"
GUARDIANS_REQUIRED = 7
SIGNAL_COMPLETE = "afterlife_of_io_campaign_complete"
SIGNAL_RECOVERING = "afterlife_of_io_archives_recovering"

_live = {"guardians": 0, "campaign_complete": False}


def hosted() -> bool:
    """True when HoloVerse's Dimension Archive started this process."""
    return (os.environ.get("HOLOVERSE_LINK_MODE", "") == "compatibility_external"
            and bool(os.environ.get("HOLOVERSE_RETURN_SIGNAL_PATH", "")))


def quit_label(standalone: str) -> str:
    """The quit wording for menus: 'RETURN TO HOLOVERSE' while hosted, else the usual text."""
    return "RETURN TO HOLOVERSE" if hosted() else standalone


def note_progress(guardians: int | None = None, campaign_complete: bool | None = None) -> None:
    """Remember progress made in this session (it may not be saved yet)."""
    if guardians is not None:
        _live["guardians"] = max(_live["guardians"], int(guardians))
    if campaign_complete:
        _live["campaign_complete"] = True


def result(saved_guardians: int = 0, saved_complete: bool = False) -> dict:
    guardians = min(GUARDIANS_REQUIRED, max(int(saved_guardians), _live["guardians"]))
    complete = bool(saved_complete or _live["campaign_complete"])
    if complete:
        signal = SIGNAL_COMPLETE
        response = "IO's continuity crossed the Veil. Its archive is whole, and it came home with me."
    elif guardians:
        signal = SIGNAL_RECOVERING
        response = f"IO is still recovering the civilization archives: {guardians} of {GUARDIANS_REQUIRED}."
    else:
        signal = ""
        response = "IO is still waiting between the Beginning and the Present."
    return {
        "mode_id": MODE_ID,
        "title": TITLE,
        "completed": complete,
        "signal": signal,
        "guardians_defeated": guardians,
        "fragments_recovered": str(guardians),
        "fragments_required": str(GUARDIANS_REQUIRED),
        "gleebs_response": response,
    }


def report_to_holoverse(saved_guardians: int = 0, saved_complete: bool = False) -> bool:
    """Write the result for HoloVerse to read when this process ends. Never raises."""
    if not hosted():
        return False
    try:
        path = Path(os.environ["HOLOVERSE_RETURN_SIGNAL_PATH"])
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": 1,
            "source": MODE_ID,
            "reason": "afterlife_exit",
            "timestamp": time.time(),
            "result": result(saved_guardians, saved_complete),
        }
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return True
    except Exception:
        return False
