from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def require(condition, label):
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}")


def main():
    active = ["space_core.py", "terrains.py", "surface_resources.py", "standard_ui.py", "ship_progression.py"]
    for name in active:
        ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)
    require(True, "Pass 19 modules parse")

    core = (ROOT / "space_core.py").read_text(encoding="utf-8")
    terrain = (ROOT / "terrains.py").read_text(encoding="utf-8")
    ui = (ROOT / "standard_ui.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "build_manifest.json").read_text(encoding="utf-8"))

    require('PAUSE_KEY = getattr(pygame, "K_BACKQUOTE"' in core, "pause is mapped to backtick")
    require("if key == PAUSE_KEY" in core and "if key == pygame.K_p" not in core, "P no longer controls pause")
    require('("`", "pause / resume")' in ui and "P RESUME" not in ui, "all pause UI teaches backtick")
    require('planet_is_landable(system.planets[nearest_planet_i])' in core, "atmosphere entry accepts every intact nearest planet")
    require('if not planet_is_landable(system.planets[i])' in core, "destroyed planets are excluded from landing selection")
    require('LANDABLE' in core, "orbital labels communicate universal planetfall")

    require("def try_harvest_nearby" in terrain, "surface recovery interaction exists")
    for category in ("structure", "prop", "tree", "plant"):
        require(repr(category) in terrain, f"{category} category is recoverable")
    require("harvest_yield" in terrain and "add_resource" in terrain, "recovered objects process into existing resources")
    require("surface_harvests" in core and "surface_harvests" in terrain, "harvest persistence is saved and restored")
    require("TOPDOWN_MAP_SCALE = 4" in terrain, "surface map memory scale reduced")
    require("harvest_scan_at" in terrain and "+ 0.15" in terrain, "nearby recovery scans are throttled")
    require("index = {'trees': {}, 'plants': {}, 'props': {}, 'harvest': {}}" in terrain, "recoverable objects use a local spatial index")
    require("for cy in range(base_cy - 1, base_cy + 2)" in terrain, "recovery lookup examines only nearby buckets")
    require("not self._harvest_state_loaded" in terrain, "harvest save state is normalized once per planetfall")
    require(("pygame.transform.scale(crop" in terrain) or ("_draw_chunked_terrain" in terrain and "pygame.transform.scale(canvas" in terrain), "surface terrain uses a bounded fast internal render path")
    require("every intact planet" in readme.lower(), "README documents universal planetfall")
    require(int(manifest.get("pass", 0)) >= 19, "manifest preserves Pass 19 planetfall authority")

    from surface_resources import harvest_id, harvest_yield, normalize_harvest_map, planet_is_landable

    class Planet:
        destroyed = False
    p = Planet()
    require(planet_is_landable(p), "intact planet is landable")
    p.destroyed = True
    require(not planet_is_landable(p), "destroyed planet is not landable")

    base = harvest_yield(100, 200, "structure", 0)
    upgraded = harvest_yield(100, 200, "structure", 3)
    require(base["salvage"] >= 3, "ruin processing always yields salvage")
    require(upgraded["salvage"] > base["salvage"], "Surface Rig improves ruin yield")
    require(harvest_yield(100, 201, "tree", 0)["fuel_cells"] >= 1, "organic growth processes into fuel cells")
    require(harvest_id("prop", 88) == "p:88", "object harvest IDs are stable")
    require(normalize_harvest_map({"1": ["p:2", "p:2", "s:3"]}) == {"1": ["p:2", "s:3"]}, "harvest persistence compacts duplicate IDs")

    print("FINAL_RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
