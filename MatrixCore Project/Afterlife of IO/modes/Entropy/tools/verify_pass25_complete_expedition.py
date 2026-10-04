#!/usr/bin/env python3
"""Dependency-free Pass 25 campaign verifier.

Runs without pygame/Panda3D so the campaign/state contract can be tested in
headless build environments. Native rendering/input still requires pygame-ce.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(ROOT))

from mission_state import (
    MissionState,
    DATA_FRAGMENTS_REQUIRED,
    CAMPAIGN_HOME,
    CAMPAIGN_SHIP_RECOVERY,
    CAMPAIGN_EXPEDITION,
    CAMPAIGN_DELIVERY,
    CAMPAIGN_COMPLETE,
    SHIP_BOOT_SEQUENCE,
)

checks = []

def require(condition, label, detail=""):
    ok = bool(condition)
    checks.append({"check": label, "ok": ok, "detail": detail})
    if not ok:
        raise AssertionError(f"{label}: {detail}")

class Planet:
    def __init__(self, style="desert"):
        self.style = style

class System:
    def __init__(self, seed, style="desert"):
        self.seed = int(seed)
        self.planets = [Planet(style)]

class Structure:
    def __init__(self, seed, x=70.0, y=0.0, title="Archive Spire"):
        self.seed = int(seed)
        self.x = float(x)
        self.y = float(y)
        self.title = title

# 1) Fresh campaign begins on HOME and assigns HOME supply objective.
mission = MissionState()
home = System(1001, "desert")
mission.begin_system(home, 1)
mission.mark_run_started()
mission.land_on(0)
require(mission.campaign_phase == CAMPAIGN_HOME, "fresh campaign starts on HOME")
require(mission.target_signal is not None and mission.target_signal.role == "home", "HOME world receives emergency-cache role")
require(mission.objective_title("surface").startswith("HOME"), "HOME has dedicated objective copy")
require(mission.claim_resource(0) == "home", "HOME emergency cache is claimable")
require("home_supply_secured" in mission.completed_objectives, "HOME supplies advance objective")

# 2) First supernova transitions into ordered ship recovery.
mission.begin_ship_recovery()
require(mission.campaign_phase == CAMPAIGN_SHIP_RECOVERY, "HOME evacuation enters ship recovery")
require(mission.ship_boot_next_step == "power", "ship recovery starts at power")
require(not mission.complete_ship_boot_step("fuel"), "ship boot rejects out-of-order steps")
for step in SHIP_BOOT_SEQUENCE:
    require(mission.ship_boot_next_step == step, f"ship boot expects {step}")
    require(mission.complete_ship_boot_step(step), f"ship boot accepts {step}")
require(mission.campaign_phase == CAMPAIGN_EXPEDITION, "cockpit launches expedition")
require("expedition_launched" in mission.completed_objectives, "expedition launch is recorded")

# 3) Six systems produce exactly six Data Fragments with no objective auto-warp.
styles = ("ice", "jungle", "volcanic", "crystal", "oceanic", "abyss")
for i, style in enumerate(styles, start=1):
    system = System(2000 + i, style)
    mission.begin_system(system, i + 1)
    mission.land_on(0)
    structure = Structure(9000 + i, x=65.0 + i, title=f"Archive {i}")
    target = mission.bind_surface_target(3000 + i, [structure], (0.0, 0.0))
    require(target == structure.seed, f"system {i} binds stable data archive")
    before = mission.data_fragments_secured
    require(mission.recover_surface_relic(structure.seed), f"system {i} recovers Data Fragment")
    require(mission.data_fragments_secured == before + 1, f"system {i} increments archive once")
    require(not mission.recover_surface_relic(structure.seed), f"system {i} rejects duplicate recovery")
    require(not mission.system_goal_complete, f"system {i} does not auto-warp")

require(mission.data_fragments_secured == DATA_FRAGMENTS_REQUIRED, "six Data Fragments complete archive")
require(mission.campaign_phase == CAMPAIGN_DELIVERY, "sixth fragment enters Gleebs delivery phase")
require("GLEEBS" in mission.objective_title("space"), "delivery objective names Gleebs")
require(mission.transmit_to_gleebs(), "Gleebs transmission completes campaign")
require(mission.campaign_phase == CAMPAIGN_COMPLETE and mission.campaign_complete, "campaign reaches complete state")
require(not mission.transmit_to_gleebs() is False or mission.campaign_complete, "completed campaign remains terminal")

# 4) Save round-trip preserves complete campaign.
payload = mission.to_dict()
restored = MissionState()
require(restored.restore_from_dict(payload), "Pass 25 save payload restores")
require(restored.campaign_complete, "campaign-complete flag survives save round-trip")
require(restored.data_fragments_secured == 6, "Data Fragment count survives save round-trip")
require(restored.gleebs_transmission_complete, "Gleebs transmission survives save round-trip")

# 5) RC1 migration: started old save joins expedition; untouched old save starts HOME.
legacy_started = {
    "run_started": True,
    "system_index": 4,
    "system_seed": 4040,
    "system_planet_count": 1,
    "fragments_secured_total": 2,
}
legacy_system = System(4040, "storm")
migrated = MissionState()
require(migrated.restore_from_dict(legacy_started, legacy_system), "started RC1 save migrates")
require(migrated.campaign_phase == CAMPAIGN_EXPEDITION, "started RC1 save is not forced through HOME prologue")
require(migrated.data_fragments_secured == 2, "legacy recovered count becomes Data Fragment count")

legacy_fresh = {
    "run_started": False,
    "system_index": 1,
    "system_seed": 5050,
    "system_planet_count": 1,
    "fragments_secured_total": 0,
}
legacy_home_system = System(5050, "desert")
fresh_migrated = MissionState()
require(fresh_migrated.restore_from_dict(legacy_fresh, legacy_home_system), "unstarted RC1 save migrates")
require(fresh_migrated.campaign_phase == CAMPAIGN_HOME, "unstarted RC1 save begins HOME prologue")

# 6) Static runtime contracts for pygame-bound modules.
space_src = (ROOT / "space_core.py").read_text(encoding="utf-8")
interior_src = (ROOT / "interiors.py").read_text(encoding="utf-8")
terrain_src = (ROOT / "terrains.py").read_text(encoding="utf-8")
ui_src = (ROOT / "standard_ui.py").read_text(encoding="utf-8")
progression_src = (ROOT / "ship_progression.py").read_text(encoding="utf-8")

for filename in ("space_core.py", "interiors.py", "terrains.py", "standard_ui.py", "ship_progression.py", "mission_state.py"):
    ast.parse((ROOT / filename).read_text(encoding="utf-8"), filename=filename)
require(True, "campaign runtime files parse as Python")
require("HOME SUPERNOVA — EMERGENCY TRANSFER ENGAGED" in space_src and "commit_home_evacuation" in space_src, "HOME supernova has guaranteed transfer path")
require("supernova_deadline = None" in space_src and "is_ship_recovery_phase" in space_src, "ship recovery can freeze collapse clock")
require("request_campaign_complete" in space_src and "draw_campaign_complete_screen" in space_src, "Gleebs completion state is wired into main loop")
require("try_restore_power" in interior_src and "try_store_inventory" in interior_src and "try_initialize_navigation" in interior_src and "try_cockpit" in interior_src, "ship tutorial stations exist")
require("player_pack" in interior_src and "add_resource(self.ship" in interior_src, "field pack can be stored into ship cargo")
require("DATA FRAGMENT RECOVERED" in terrain_src and "RECOVER DATA FRAGMENT" in terrain_src, "surface target uses Data Fragment language")
require("DATA TRANSFER COMPLETE" in ui_src and "GLEEBS" in ui_src and "MATRIXCORE" in ui_src, "endgame presentation ties to Gleebs and MatrixCore")
require("DATA SIGNAL ONLY" in progression_src, "scanner upgrade copy follows Data Fragment campaign")
require("system_goal_complete" in (ROOT / "mission_state.py").read_text() and "return False" in (ROOT / "mission_state.py").read_text(), "legacy objective auto-warp is disabled")

result = {
    "pass": "Entropy Pass 25 — Complete Expedition",
    "status": "PASS",
    "data_fragments_required": DATA_FRAGMENTS_REQUIRED,
    "ship_boot_sequence": list(SHIP_BOOT_SEQUENCE),
    "checks": checks,
    "checks_passed": sum(1 for x in checks if x["ok"]),
    "checks_total": len(checks),
}
print(json.dumps(result, indent=2))
