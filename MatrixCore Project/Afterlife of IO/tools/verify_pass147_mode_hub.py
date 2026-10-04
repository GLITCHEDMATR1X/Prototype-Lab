"""Pass 147 verification: MODES hub unlocks and same-window round trips.

Runs headless (SDL dummy drivers) against a throwaway save folder:

1. Unlock rules: 2 guardians -> HEX CONTRACT, 4 -> GHOST SIGNAL,
   campaign complete -> ENTROPY; remembered unlocks survive.
2. Each mode runs hosted in the live window, is closed, and control returns
   with the same pygame display, no leaked mode modules and restored sys.path.
3. Full hub: title -> MODES -> HEX CONTRACT -> quit -> Afterlife title -> quit.

Usage:  python tools/verify_pass147_mode_hub.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

import main as afterlife  # noqa: E402
import mode_host  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []
TMP = Path(tempfile.mkdtemp(prefix="afterlife_p147_"))
afterlife._user_data_dir = lambda: TMP  # never touch the player's saves


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(("PASS" if ok else "FAIL"), name, detail)


def write_slot(slot: int, guardians: int, complete: bool = False) -> None:
    ids = list(afterlife.MEMORY_GUARDIAN_ORDER[:guardians])
    payload = {"world": "a", "walk_layer": 1, "player": {"x": 10, "y": 10},
               "progression": {"defeated_entities": ids, "campaign_complete": complete}}
    (TMP / f"manual_save_slot_{slot}.json").write_text(json.dumps(payload), encoding="utf-8")


def clear_slots() -> None:
    for p in TMP.glob("manual_save_slot_*.json"):
        p.unlink()


def post_later(delay: float, *events: pygame.event.Event, gap: float = 0.35) -> threading.Thread:
    def run():
        time.sleep(delay)
        for event in events:
            pygame.event.post(event)
            time.sleep(gap)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def key(k: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0)


# 1. Unlock rules -----------------------------------------------------------------
clear_slots()
p = afterlife.mode_progress()
check("no saves -> nothing unlocked", mode_host.unlocked_ids(p) == [], str(mode_host.unlocked_ids(p)))
write_slot(1, 2)
p = afterlife.mode_progress()
check("2 guardians -> HEX CONTRACT only", mode_host.unlocked_ids(p) == ["hex_contract"], f"{p}")
write_slot(2, 4)
p = afterlife.mode_progress()
check("4 guardians (best slot) -> + GHOST SIGNAL", mode_host.unlocked_ids(p) == ["hex_contract", "ghost_signal"], f"{p}")
write_slot(3, 7, complete=True)
p = afterlife.mode_progress()
check("campaign complete -> + ENTROPY", mode_host.unlocked_ids(p) == ["hex_contract", "ghost_signal", "entropy"], f"{p}")
clear_slots()
check("remembered unlocks persist without saves",
      mode_host.unlocked_ids(afterlife.mode_progress(), afterlife.remembered_modes({"unlocked_modes": ["ghost_signal"]})) == ["ghost_signal"])
check("legacy entropy flag migrates", afterlife.remembered_modes({"entropy_mode_unlocked": True}) == ["entropy"])
for spec in mode_host.MODES:
    check(f"{spec.title} installed", mode_host.find_mode_dir(spec) is not None, str(mode_host.find_mode_dir(spec)))

# 2. Hosted round trips ----------------------------------------------------------
pygame.init()
window = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
for spec in mode_host.MODES:
    folder = mode_host.find_mode_dir(spec)
    path_before = list(sys.path)
    post_later(6.0, pygame.event.Event(pygame.QUIT))
    started = time.time()
    code, notice = mode_host.run_mode(spec, folder, log=lambda m: None)
    elapsed = time.time() - started
    surface = pygame.display.get_surface()
    leaked = sorted(n for n in sys.modules if n.split(".")[0] in {"game", "audio", "rendering", "ui", "space_core", "terrains"})
    check(f"{spec.title} returns to host", notice == "" and elapsed < 60, f"rc={code} {elapsed:.1f}s {notice}")
    check(f"{spec.title} keeps the host window", surface is not None and pygame.display.get_init() and pygame.get_init(),
          str(surface.get_size() if surface else None))
    check(f"{spec.title} leaves no modules/path behind", not leaked and sys.path == path_before, ",".join(leaked))
    pygame.event.clear()

# 3. Full hub loop -------------------------------------------------------------
clear_slots()
write_slot(1, 2)
sys.argv = [sys.argv[0], "--windowed"]
log_lines: list[str] = []
real_log = afterlife._early_log
afterlife._early_log = lambda m: (log_lines.append(m), real_log(m))
post_later(12.0,
           key(pygame.K_DOWN), key(pygame.K_DOWN), key(pygame.K_DOWN), key(pygame.K_RETURN),  # MODES
           key(pygame.K_RETURN),                                                             # HEX CONTRACT
           gap=0.6)
post_later(26.0, pygame.event.Event(pygame.QUIT))   # quit HEX -> back to Afterlife
post_later(44.0, pygame.event.Event(pygame.QUIT))   # quit Afterlife title
rc = afterlife.main()
handed = any("handing active display to HEX CONTRACT" in m for m in log_lines)
rebuilt = sum(1 for m in log_lines if m.startswith("MAIN enter argv")) == 2
check("hub launches HEX CONTRACT from MODES", handed)
check("quitting HEX returns to the Afterlife title", rebuilt and rc == 0, f"sessions={sum(1 for m in log_lines if m.startswith('MAIN enter argv'))}")

for m in log_lines:
    if m.startswith(("MAIN enter", "MAIN handing", "MAIN HEX", "MODE", "MAIN clean")):
        print("   LOG", m[:120])
ok = all(r[1] for r in RESULTS)
print(f"\nFINAL {'PASS' if ok else 'FAIL'} {sum(r[1] for r in RESULTS)}/{len(RESULTS)}")
sys.exit(0 if ok else 1)
