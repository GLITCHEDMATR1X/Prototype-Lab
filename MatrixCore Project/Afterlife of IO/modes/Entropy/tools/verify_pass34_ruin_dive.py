#!/usr/bin/env python3
"""Pass 34 verifier: DreamCrawler archive-ruin dives inside Entropy.

Headless (SDL dummy).  Checks the whole retrieve-and-return loop:
E at the marked ruin requests a dive -> the dive runs in the current window ->
a recovered fragment is CARRIED -> securing it at the ship CARGO station counts
the archive.  A retreat leaves the fragment below and the ruin re-divable.
The 1/4-speed collapse clock refund is checked numerically.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

import ruin_dive  # noqa: E402
from mission_state import MissionState, SHIP_BOOT_SEQUENCE  # noqa: E402

checks: list[tuple[str, bool, str]] = []


def require(ok, label, detail=""):
    checks.append((label, bool(ok), str(detail)))
    print(("PASS" if ok else "FAIL"), label, detail)


class Planet:
    def __init__(self, style):
        self.style = style


class System:
    def __init__(self, seed, style="volcanic"):
        self.seed = int(seed)
        self.planets = [Planet(style)]


def launched_mission():
    mission = MissionState()
    mission.begin_system(System(1001, "desert"), 1)
    mission.mark_run_started()
    mission.land_on(0)
    mission.claim_resource(0)
    mission.begin_ship_recovery()
    for step in SHIP_BOOT_SEQUENCE:
        mission.complete_ship_boot_step(step)
    mission.begin_system(System(2001), 2)
    mission.land_on(0)
    return mission


# 1) DreamCrawler engine is installed beside Entropy and loads privately.
require(ruin_dive.find_dreamcrawler_dir() is not None, "DreamCrawler found beside Entropy", ruin_dive.find_dreamcrawler_dir())
require(ruin_dive.dive_available(), "dreamcrawler_core loads without opening a window")
require(pygame.display.get_surface() is None, "loading the engine has no display side effect")

# 2) E at the marked ruin becomes a dive request (no instant recovery).
import terrains  # noqa: E402

mission = launched_mission()
structure = SimpleNamespace(seed=9101, x=40.0, y=0.0, title="Obsidian Archive", radius=12.0, is_mission_target=True)
require(mission.bind_surface_target(3001, [structure], (0.0, 0.0)) == structure.seed, "archive ruin bound as target")
fake = SimpleNamespace(mission_state=mission, ship=object(), ruin_dive_request=None)
fake.nearest_harvestable = lambda _r=10.0: ("structure", structure, 3.0)
fake.target_awaits_fragment = lambda st: terrains.SurfaceView.target_awaits_fragment(fake, st)
require(terrains.SurfaceView.try_harvest_nearby(fake) is True, "E at the ruin is consumed")
require(fake.ruin_dive_request is structure, "E at the ruin requests a DreamCrawler dive")
require(not mission.fragment_deposited and not mission.carrying_fragment, "no instant surface recovery while dives exist")

# 3) The dive runs in the host window and returns (QA auto-retreat).
pygame.init()
window = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
result = ruin_dive.run_dive(seed=structure.seed, site_label="ARCHIVE 1/6 — Obsidian Archive", collapse_remaining=40.0, auto_frames=120)
require(result["outcome"] == "retreat", "auto-retreat outcome reported", result)
require(pygame.display.get_surface() is window and pygame.get_init(), "dive keeps Entropy's window and pygame alive")
require(abs(result["collapse_charged"] - 120 * ruin_dive.DIVE_COLLAPSE_RATE / 60.0) < 0.35, "collapse charged at 1/4 speed", result["collapse_charged"])
require(abs(ruin_dive.collapse_refund({"wall_seconds": 100.0, "collapse_charged": 25.0}) - 75.0) < 1e-6, "100 s underground costs 25 s of collapse")
require(ruin_dive.collapse_refund({"wall_seconds": 5.0, "collapse_charged": 9.0}) == 0.0, "refund never negative")
collapse = ruin_dive.run_dive(seed=5, site_label="QA", collapse_remaining=0.1, auto_frames=400)
require(collapse["outcome"] == "collapse", "clock running out underground ends the dive", collapse)

# 4) Retreat leaves the fragment in the ruin; a recovered dive carries it home.
require(terrains.SurfaceView.target_awaits_fragment(fake, structure), "after a retreat the ruin still holds the fragment")
require(mission.enter_structure(structure.seed, structure.title), "dive success enters the target archive")
require(mission.recover_fragment(structure.seed), "dive success recovers the fragment")
mission.leave_structure()
require(mission.carrying_fragment and not mission.fragment_deposited, "fragment is carried back to the ship")
require(not terrains.SurfaceView.target_awaits_fragment(fake, structure), "ruin no longer offers a dive while carrying")
before = mission.fragments_secured_total
require(mission.deposit_fragment(), "CARGO station secures the carried fragment")
require(mission.fragments_secured_total == before + 1 and mission.fragment_deposited, "archive count advances once")

# 5) Space-core wiring (source contract).
src = (ROOT / "space_core.py").read_text(encoding="utf-8")
require("def run_archive_dive(surface, structure):" in src, "space_core runs dives from the surface loop")
require("ruin_dive.collapse_refund(result)" in src and "supernova_deadline += refund" in src, "dive time refunds the wall-clock deadline")
require("transition_gap_grace_frames = max(transition_gap_grace_frames, 3)" in src, "dive return never triggers the resume-pause guard")

ok = all(c[1] for c in checks)
print(f"\nFINAL {'PASS' if ok else 'FAIL'} {sum(c[1] for c in checks)}/{len(checks)}")
pygame.quit()
raise SystemExit(0 if ok else 1)
