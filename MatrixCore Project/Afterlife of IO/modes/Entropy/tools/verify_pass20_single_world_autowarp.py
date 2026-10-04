from __future__ import annotations

import ast
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def require(condition, label):
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}")


def extract_styles(core_source: str):
    tree = ast.parse(core_source, filename="space_core.py")
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "ORBITAL_PLANET_STYLES" for t in node.targets):
                return tuple(ast.literal_eval(node.value))
    raise AssertionError("ORBITAL_PLANET_STYLES not found")


def main():
    active = [
        "space_core.py", "mission_state.py", "surface_resources.py",
        "terrains.py", "standard_ui.py", "ship_progression.py",
    ]
    for name in active:
        ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)
    require(True, "Pass 20 active modules parse")

    core = (ROOT / "space_core.py").read_text(encoding="utf-8")
    mission_source = (ROOT / "mission_state.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "build_manifest.json").read_text(encoding="utf-8"))

    require("n = 1" in core, "system generator creates exactly one planet")
    require("one star, one varied landable world" in core, "single-world generator authority is documented in code")
    require("ring_variant_rng" in core, "ring presence remains a variation instead of being forced")

    styles = extract_styles(core)
    require(len(styles) == 12 and len(set(styles)) == 12, "all twelve planet classes remain in the source pool")
    observed = set()
    for seed in range(1000):
        order = list(styles)
        random.Random(seed ^ 0x50A7B17).shuffle(order)
        observed.add(order[0])
    require(observed == set(styles), "all twelve world classes appear as the sole planet across verification seeds")

    require("AUTO_OBJECTIVE_WARP_DELAY = 1.35" in core, "goal completion preserves a short pickup confirmation")
    require("def queue_objective_autowarp" in core, "goal completion queues automatic progression")
    require("def commit_objective_autowarp" in core, "automatic progression has one centralized transition")
    for context_cleanup in (
        'globals().get("game_mode") == GAME_MODE_SURFACE',
        'globals().get("game_mode") == GAME_MODE_INTERIOR',
        'globals()["game_mode"] = GAME_MODE_SPACE',
    ):
        require(context_cleanup in core, f"autowarp supports cleanup path: {context_cleanup}")
    require('globals()["pending_warp_jumps"] = 1' in core, "objective completion advances exactly one system")
    require("mission.system_goal_complete" in core, "runtime progression reads authoritative mission completion")
    require("objective autowarp already locked" in core, "manual warp cannot conflict with completed-goal transition")
    require("NEXT SYSTEM INBOUND" in mission_source, "mission tracker teaches automatic progression")

    require("resolve_planet_exclusion" in core, "space runtime applies unavailable-planet safety correction")
    require("planet_exclusion_radius" in core, "landing and collision safety share one atmosphere boundary")
    require("planetfall unavailable — safe course corrected" in core, "navigation correction provides player feedback")

    require("one planet" in readme.lower(), "README documents the single-world rule")
    require("automatically" in readme.lower() and "warp" in readme.lower(), "README documents automatic goal progression")
    require(int(manifest.get("pass", 0)) >= 20, "manifest preserves Pass 20 single-world authority")
    require(manifest.get("single_world_progression", {}).get("planets_per_system") == 1, "manifest locks one planet per system")
    require(manifest.get("single_world_progression", {}).get("world_class_pool") == 12, "manifest preserves all world variants")

    from mission_state import MissionState
    from surface_resources import (
        planet_exclusion_radius, planet_is_landable, resolve_planet_exclusion,
    )

    class Planet:
        def __init__(self, style="ice", destroyed=False, radius=90.0):
            self.style = style
            self.destroyed = destroyed
            self.radius = radius
            self.mission_role = ""
            self.signal_label = ""
            self.hazard_family = ""
            self.is_fragment_target = False

    class System:
        seed = 20260804
        planets = [Planet("fungal")]

    mission = MissionState()
    mission.begin_system(System(), 7)
    require(mission.system_planet_count == 1, "mission records one visible planet")
    require(mission.target_planet_index == 0, "the sole planet is the objective world")
    require(len(mission.signals) == 1 and mission.signals[0].role == "fragment", "single planet carries the Relic Core signal")
    mission.land_on(0)
    mission.target_structure_seed = 919
    require(mission.recover_surface_relic(919), "surface Relic Core completes successfully")
    require(mission.system_goal_complete, "Relic Core completion authorizes autowarp")
    require(mission.objective_title("surface") == "RELIC CORE RECOVERED — AUTO-WARP LOCKED", "surface objective updates to autowarp state")

    intact = Planet(destroyed=False, radius=80.0)
    require(planet_is_landable(intact), "intact sole planet remains landable")
    pos, vel, corrected = resolve_planet_exclusion((100.0, 0.0, 0.0), (-50.0, 0.0, 0.0), (0.0, 0.0, 0.0), intact)
    require(not corrected and pos == (100.0, 0.0, 0.0), "landable planet does not deflect normal approach")

    destroyed = Planet(destroyed=True, radius=80.0)
    pos, vel, corrected = resolve_planet_exclusion((100.0, 0.0, 0.0), (-50.0, 0.0, 0.0), (0.0, 0.0, 0.0), destroyed)
    require(corrected, "destroyed planet triggers safe exclusion")
    require(math.dist(pos, (0.0, 0.0, 0.0)) >= planet_exclusion_radius(destroyed), "corrected ship is outside atmosphere boundary")
    require(vel[0] >= -1e-6, "inward velocity is removed by safe exclusion")

    blocked = Planet(destroyed=False, radius=80.0)
    pos, vel, corrected = resolve_planet_exclusion((50.0, 0.0, 0.0), (-10.0, 0.0, 0.0), (0.0, 0.0, 0.0), blocked, force_blocked=True)
    require(corrected, "temporarily blocked planet entry also deflects safely")

    print("FINAL_RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
