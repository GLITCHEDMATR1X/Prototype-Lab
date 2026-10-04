"""Archive-ruin dives: Entropy hands its live window to the DreamCrawler team.

Loop (one per system archive):

1. Land on the target planet and walk to the marked archive ruin.
2. Press E: the nine-bot DreamCrawler party descends into the ruin.  Floor 1
   hides the stairs down; the last floor is the vault with the Data Fragment,
   guarded by a WARDEN crawler.
3. Anyone in the party can take the fragment.  Regroup at the ASCENT LINE (the
   vault floor's arrival point) to climb out.
4. Back on the surface Entropy marks the fragment as carried.  Return to the
   ship and secure it at CARGO / DATA ARCHIVE — the normal Entropy route.

While underground the collapse clock runs at ``DIVE_COLLAPSE_RATE`` (1/4 speed).
A retreat, a downed diver or a collapse leaves the fragment in the ruin; the
player may dive again while the system survives, and a missed archive is
reassigned by the campaign exactly as before.

If DreamCrawler is not installed next to Entropy, ``dive_available()`` is False
and Entropy keeps its original surface recovery.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

DIVE_COLLAPSE_RATE = 0.25
DIVE_DEPTH = 2
_MODULE_NAME = "gx_dreamcrawler_core"
_core = None
_core_failed = False


def _valid(path: Path) -> bool:
    return (path / "dreamcrawler_core.py").is_file()


def find_dreamcrawler_dir() -> Path | None:
    override = os.environ.get("GX_DREAMCRAWLER_DIR", "").strip()
    if override:
        candidate = Path(override).expanduser()
        if _valid(candidate):
            return candidate.resolve()
    here = Path(__file__).resolve().parent
    for candidate in (here.parent / "DreamCrawler", here / "modes" / "DreamCrawler", here.parent / "modes" / "DreamCrawler"):
        if _valid(candidate):
            return candidate.resolve()
    return None


def load_core():
    """Import DreamCrawler's engine once, under a private module name."""
    global _core, _core_failed
    if _core is not None or _core_failed:
        return _core
    folder = find_dreamcrawler_dir()
    if folder is None:
        _core_failed = True
        return None
    try:
        spec = importlib.util.spec_from_file_location(_MODULE_NAME, folder / "dreamcrawler_core.py")
        if spec is None or spec.loader is None:
            raise ImportError("no loader for dreamcrawler_core.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[_MODULE_NAME] = module
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(_MODULE_NAME, None)
        _core_failed = True
        raise
    _core = module
    return _core


def dive_available() -> bool:
    try:
        return load_core() is not None
    except Exception:
        return False


def run_dive(*, seed: int, site_label: str, collapse_remaining: float | None, auto_frames: int = 0) -> dict:
    """Run one dive in the current window and return DreamCrawler's result dict.

    ``auto_frames`` is a QA hook: the dive retreats after that many frames.
    """
    core = load_core()
    if core is None:
        raise RuntimeError("DreamCrawler is not installed next to Entropy")
    return core.run_expedition({
        "seed": int(seed),
        "depth": DIVE_DEPTH,
        "collapse_remaining": collapse_remaining,
        "collapse_rate": DIVE_COLLAPSE_RATE,
        "site_label": site_label,
        "auto_frames": int(auto_frames),
    })


def collapse_refund(result: dict) -> float:
    """Seconds to push Entropy's wall-clock deadlines back after a dive.

    The dive charged ``collapse_charged`` seconds (1/4 speed, frozen while
    paused); every other second the player spent underground is refunded.
    """
    wall = max(0.0, float(result.get("wall_seconds", 0.0) or 0.0))
    charged = max(0.0, float(result.get("collapse_charged", 0.0) or 0.0))
    return max(0.0, wall - charged)
