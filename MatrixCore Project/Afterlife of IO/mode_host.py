"""Unlockable modes hosted inside the Afterlife of IO window.

Afterlife of IO is the hub.  Its title screen has a MODES menu; each mode is
unlocked by campaign progress read from the manual save slots:

    HEX CONTRACT  — defeat 2 Memory Guardians
    GHOST SIGNAL  — defeat 4 Memory Guardians
    ENTROPY       — complete the Afterlife campaign (endgame)

A mode runs in-process and adopts Afterlife's live SDL window (no second OS
window, no close/reopen flash).  When the mode ends, control returns here and
Afterlife rebuilds its title screen in the same window.

Isolation contract for a hosted run (``run_mode``):
* the mode folder is put on ``sys.path`` only for the run; every module it
  imported is removed afterwards so two modes that both ship a ``game``
  package (HEX Contract, Ghost Signal) can never see each other's code;
* cwd, environment, excepthook/threading/unraisable hooks and the mixer channel
  layout are restored;
* a mode that crashes is logged and reported on the title; it never takes the
  Afterlife process down with it.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import pygame

ROOT = Path(__file__).resolve().parent
MODES_DIR = ROOT / "modes"


@dataclass(frozen=True)
class ModeSpec:
    mode_id: str
    title: str
    folder: str
    guardians_required: int | None  # None = needs the finished campaign
    tagline: str
    marker: str  # a file that must exist for the folder to count as installed

    @property
    def requirement_text(self) -> str:
        if self.guardians_required is None:
            return "COMPLETE THE AFTERLIFE CAMPAIGN"
        return f"DEFEAT {self.guardians_required} MEMORY GUARDIANS"


MODES: tuple[ModeSpec, ...] = (
    ModeSpec("hex_contract", "HEX CONTRACT", "HEX Contract", 2,
             "Guild contracts. Send heroes, read the field, keep them alive.", "game/app.py"),
    ModeSpec("ghost_signal", "GHOST SIGNAL", "Ghost Signal", 4,
             "Take the city one building core at a time.", "game/app.py"),
    ModeSpec("entropy", "ENTROPY", "Entropy", None,
             "Endgame. Six dying systems, six archives, one ship.", "space_core.py"),
)
MODE_BY_ID = {spec.mode_id: spec for spec in MODES}


# ---------------------------------------------------------------------------
# Unlocks
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Progress:
    guardians: int = 0
    campaign_complete: bool = False


def read_progress(load_slot: Callable[[int], dict], slot_count: int, guardian_ids: Iterable[str]) -> Progress:
    """Best progress across all manual save slots."""
    valid = set(guardian_ids)
    best_guardians = 0
    complete = False
    for slot in range(1, slot_count + 1):
        try:
            data = load_slot(slot)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        progression = data.get("progression") if isinstance(data.get("progression"), dict) else {}
        raw = progression.get("defeated_entities")
        defeated = {str(v) for v in raw} if isinstance(raw, (list, tuple, set)) else set()
        entity = data.get("entity") if isinstance(data.get("entity"), dict) else {}
        if entity.get("defeated"):
            defeated.add("first_witness")
        best_guardians = max(best_guardians, len(defeated & valid))
        complete = complete or bool(progression.get("campaign_complete", False))
    return Progress(best_guardians, complete)


def is_unlocked(spec: ModeSpec, progress: Progress, remembered: Iterable[str] = ()) -> bool:
    if spec.mode_id in set(remembered):
        return True
    if spec.guardians_required is None:
        return progress.campaign_complete
    return progress.campaign_complete or progress.guardians >= spec.guardians_required


def unlocked_ids(progress: Progress, remembered: Iterable[str] = ()) -> list[str]:
    remembered = list(remembered)
    return [spec.mode_id for spec in MODES if is_unlocked(spec, progress, remembered)]


def progress_text(spec: ModeSpec, progress: Progress) -> str:
    if spec.guardians_required is None:
        return f"{spec.requirement_text}"
    have = min(progress.guardians, spec.guardians_required)
    return f"{spec.requirement_text}  ({have}/{spec.guardians_required})"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
def find_mode_dir(spec: ModeSpec) -> Path | None:
    """modes/<folder> inside Afterlife first; env override for dev layouts."""
    override = os.environ.get(f"GX_{spec.mode_id.upper()}_DIR", "").strip()
    candidates = []
    if override:
        candidates.append(Path(override).expanduser())
    candidates += [MODES_DIR / spec.folder, ROOT.parent / spec.folder]
    for candidate in candidates:
        if (candidate / spec.marker).is_file():
            return candidate.resolve()
    return None


# ---------------------------------------------------------------------------
# Hosted run
# ---------------------------------------------------------------------------
def _user_dir(name: str) -> Path:
    base = os.environ.get("LOCALAPPDATA") if sys.platform == "win32" else None
    root = Path(base) / "GLITCHED MATRIX" if base else Path.home() / ".glitched_matrix"
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _module_under(module, folder: Path) -> bool:
    file = getattr(module, "__file__", None)
    if not file:
        paths = getattr(module, "__path__", None)
        file = next(iter(paths), None) if paths else None
    if not file:
        return False
    try:
        Path(file).resolve().relative_to(folder)
        return True
    except (ValueError, OSError):
        return False


def _top_level_names(folder: Path) -> set[str]:
    names = set()
    for entry in folder.iterdir():
        if entry.suffix == ".py":
            names.add(entry.stem)
        elif entry.is_dir() and (entry / "__init__.py").is_file():
            names.add(entry.name)
    return names


def _purge_modules(folder: Path, shadow_names: set[str], extra: Iterable[str] = ()) -> None:
    for name in list(sys.modules):
        module = sys.modules.get(name)
        top = name.split(".", 1)[0]
        if _module_under(module, ROOT) and not _module_under(module, folder):
            continue  # never unload Afterlife's own modules (e.g. its main.py)
        if name in extra or _module_under(module, folder) or (top in shadow_names and name != "__main__"):
            sys.modules.pop(name, None)


def _run_entropy(folder: Path) -> int:
    spec = importlib.util.spec_from_file_location("gx_entropy_space_core", folder / "space_core.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load Entropy from {folder}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return int(module.main(["--inherit-display"]) or 0)


def _run_hex_contract(folder: Path) -> int:
    save_root = _user_dir("HEX CONTRACT")
    os.environ.setdefault("HEX_CONTRACT_SAVE_ROOT", str(save_root))
    os.environ.setdefault("HEX_CONTRACT_CRASH_ROOT", str(save_root))
    crash = importlib.import_module("game.crash_reporter")
    reporter = crash.bootstrap_crash_reporter(folder, build_label="Pass 32 (hosted by Afterlife of IO)")
    app = importlib.import_module("game.app")
    try:
        code = int(app.main(["--inherit-display", "--scenario", "title"]) or 0)
    except SystemExit as exc:
        code = int(exc.code) if isinstance(exc.code, int) else 0
    reporter.mark_clean_exit()
    return code


def _run_ghost_signal(folder: Path) -> int:
    app = importlib.import_module("game.app")
    config = app.AppConfig(inherit_display=True)
    return int(app.GhostSignalApp(config).run() or 0)


_RUNNERS = {"entropy": _run_entropy, "hex_contract": _run_hex_contract, "ghost_signal": _run_ghost_signal}


def run_mode(spec: ModeSpec, folder: Path, log: Callable[[str], None] = lambda _m: None,
             restore_fault_handler: Callable[[], None] | None = None) -> tuple[int, str]:
    """Run ``spec`` in the current window.  Returns (exit code, title notice)."""
    folder = Path(folder).resolve()
    runner = _RUNNERS[spec.mode_id]
    shadow = _top_level_names(folder)
    saved_path = list(sys.path)
    saved_cwd = os.getcwd()
    saved_env = dict(os.environ)
    saved_hooks = (sys.excepthook, threading.excepthook, sys.unraisablehook)
    saved_channels = pygame.mixer.get_num_channels() if pygame.mixer.get_init() else None
    saved_repeat = pygame.key.get_repeat()
    notice = ""
    code = 0
    _purge_modules(folder, shadow)
    sys.path.insert(0, str(folder))
    try:
        os.chdir(folder)
        log(f"MODE {spec.mode_id} start dir={folder}")
        code = runner(folder)
        log(f"MODE {spec.mode_id} returned rc={code}")
    except SystemExit as exc:
        code = int(exc.code) if isinstance(exc.code, int) else 0
        log(f"MODE {spec.mode_id} SystemExit rc={code}")
    except BaseException as exc:  # a mode must never take the hub down
        if isinstance(exc, KeyboardInterrupt):
            raise
        code = 1
        notice = f"{spec.title} CLOSED UNEXPECTEDLY — DETAILS IN THE STARTUP LOG"
        log(f"MODE {spec.mode_id} crashed {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
    finally:
        try:
            os.chdir(saved_cwd)
        except OSError:
            pass
        sys.path[:] = saved_path
        os.environ.clear()
        os.environ.update(saved_env)
        sys.excepthook, threading.excepthook, sys.unraisablehook = saved_hooks
        _purge_modules(folder, shadow, extra=("gx_entropy_space_core", "gx_dreamcrawler_core"))
        if restore_fault_handler is not None:
            try:
                restore_fault_handler()
            except Exception:
                pass
        _restore_pygame(saved_channels, saved_repeat)
    return code, notice


def _restore_pygame(channels: int | None, repeat: tuple[int, int]) -> None:
    if not pygame.get_init():
        pygame.init()
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.stop()
            pygame.mixer.set_reserved(0)
            if channels:
                pygame.mixer.set_num_channels(channels)
    except pygame.error:
        pass
    try:
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)
        pygame.key.set_repeat(*repeat)
        pygame.event.set_allowed(None)
        pygame.event.clear()
    except pygame.error:
        pass
