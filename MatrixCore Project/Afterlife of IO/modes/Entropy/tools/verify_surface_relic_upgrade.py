from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}")


def main() -> int:
    active = [
        "space_core.py", "standard_ui.py", "mission_state.py", "ship_progression.py",
        "terrains.py", "interiors.py", "runtime_paths.py", "collapse_rules.py",
    ]
    for name in active:
        ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)
    require(True, "active Pass 18.1 modules parse")

    terrain = (ROOT / "terrains.py").read_text(encoding="utf-8")
    mission_src = (ROOT / "mission_state.py").read_text(encoding="utf-8")
    progression = (ROOT / "ship_progression.py").read_text(encoding="utf-8")
    ui = (ROOT / "standard_ui.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "build_manifest.json").read_text(encoding="utf-8"))

    require("self.enter_dungeon(st)" not in terrain, "surface interaction cannot enter first-person ruins")
    enter_block = terrain[terrain.index("    def enter_dungeon"):terrain.index("    def leave_dungeon")]
    require("self.mode = 'dungeon'" not in enter_block, "legacy enter_dungeon hook cannot reactivate first-person mode")
    require("def try_collect_relic_core" in terrain, "surface Relic Core interaction exists")
    require("recover_surface_relic(structure.seed)" in terrain, "surface interaction advances authoritative mission state")
    require("add_resource(self.ship, 'relic_cores', 1)" in terrain, "surface recovery adds one persistent Relic Core")
    require("RELIC CORE" in terrain and ("E  RECOVER + PROCESS" in terrain or "E  RECOVER CORE" in terrain or "RECOVER RELIC CORE" in terrain), "top-down target and prompt are visible")
    require("fragment_deposited" in terrain, "recovered landmark stops advertising duplicate pickup")

    require("def recover_surface_relic" in mission_src, "mission has direct surface recovery method")
    require("self.fragment_deposited = True" in mission_src, "direct recovery completes the system objective")
    require("self.fragments_secured_total += 1" in mission_src, "historical recovery total advances")

    require('ship.cargo["relic_cores"]' in progression, "Relic Core cargo migrates and persists")
    require('payment = "1 RELIC CORE"' in progression, "Fabricator can spend a Relic Core")
    require('elif salvage >= cost' in progression, "original salvage payment remains available")
    require("1 CORE OR" in (ROOT / "interiors.py").read_text(encoding="utf-8"), "Fabricator displays both payment routes")
    require("recover / process ruins and objects" in ui, "controls teach surface recovery instead of ruin entry")
    require("### Ruins" not in readme, "README no longer advertises first-person ruin controls")
    core = (ROOT / "space_core.py").read_text(encoding="utf-8")
    parser_start = core.index('"--test-state"')
    parser_end = core.index('parser.add_argument("--test-seed"')
    parser_block = core[parser_start:parser_end]
    require('"dungeon"' not in parser_block and '"castle"' not in parser_block and '"catacomb"' not in parser_block,
            "launch parser exposes no first-person ruin test states")
    require(int(manifest.get("pass", 0)) >= 18, "manifest identifies an accepted relic-loop pass")
    require(manifest["recovery_loop_audit"]["active_first_person_ruin_transition"] is False,
            "manifest rejects active first-person ruin transition")

    from mission_state import MissionState
    from ship_progression import add_resource, ensure_progression, purchase_upgrade, resource_amount

    class DummyShip:
        def __init__(self):
            self.cargo = {}
            self.upgrade_levels = {}
            self.hull_hp_max = 100
            self.hull_hp = 100
            self.fuel = 60
            self.state_dirty = False

    mission = MissionState(target_planet_index=2, current_planet_index=2, target_structure_seed=991)
    require(mission.recover_surface_relic(991), "matching marked landmark recovers the Relic Core")
    require(not mission.recover_surface_relic(991), "duplicate Relic Core recovery is rejected")
    require(mission.fragment_deposited and not mission.carrying_fragment, "new recovery has no carried/deposit-only state")

    ship = DummyShip()
    ensure_progression(ship)
    add_resource(ship, "relic_cores", 1)
    add_resource(ship, "salvage", 12)
    ok, msg = purchase_upgrade(ship, "warp")
    require(ok and resource_amount(ship, "relic_cores") == 0 and resource_amount(ship, "salvage") == 12,
            "Relic Core installs an existing upgrade before salvage")
    require("USED 1 RELIC CORE" in msg, "upgrade feedback names the consumed item")

    ship2 = DummyShip()
    ensure_progression(ship2)
    add_resource(ship2, "salvage", 5)
    ok, msg = purchase_upgrade(ship2, "warp")
    require(ok and resource_amount(ship2, "salvage") == 0, "salvage fallback still installs the same upgrade")
    require("USED 5 SALVAGE" in msg, "fallback payment feedback remains explicit")

    print("FINAL_RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
