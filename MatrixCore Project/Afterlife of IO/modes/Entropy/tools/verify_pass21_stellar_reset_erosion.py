from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def require(condition, label):
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}")


def main() -> int:
    active = [
        "space_core.py", "system_safety.py", "collapse_rules.py", "mission_state.py",
        "surface_resources.py", "terrains.py", "interiors.py", "standard_ui.py",
    ]
    for name in active:
        ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)
    require(True, "Pass 21 active modules parse")

    core = (ROOT / "space_core.py").read_text(encoding="utf-8")
    safety_source = (ROOT / "system_safety.py").read_text(encoding="utf-8")
    collapse_source = (ROOT / "collapse_rules.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "build_manifest.json").read_text(encoding="utf-8"))

    require("APP_VERSION" in core and "Release Candidate 1" in core, "runtime preserves Pass 21 under release-candidate authority")
    require("COLLAPSE_DURATION = 60.0" in collapse_source, "primary collapse timer is exactly one minute")
    require("previous_ship_pos = ship.pos" in core, "runtime captures pre-movement position")
    require("star_impact_detected(" in core, "runtime performs stellar impact detection")
    require("reset_ship_to_system_spawn(ship)" in core, "sun impact uses centralized system-spawn reset")
    require("stellar impact — reset to system entry" in core, "sun reset provides navigation feedback")
    require("SUN COLLISION — FLIGHT POSITION RESTORED" in core, "sun reset provides readable banner feedback")
    require("solar_erosion_pts" in core and "draw_solar_erosion" in core, "bounded solar erosion renderer is wired")
    require("for _ in range(72)" in core, "each planet receives a fixed 72-spec erosion pool")
    require("planet._last_orbital_surface = surface" in core, "erosion samples the rendered planet material")
    require("stellar_ratio" in core and "collapse_pressure" in core, "erosion responds to proximity and collapse pressure")

    impact_block = core[core.index("# Stellar contact is a navigation reset"):core.index("# A world that cannot currently transition")]
    require("supernova_deadline" not in impact_block and "system.generate" not in impact_block, "sun reset does not restart timer or regenerate system")
    require("take_hull_damage" not in impact_block and "activate_failure" not in impact_block, "sun reset is non-destructive")

    from collapse_rules import COLLAPSE_DURATION, stage_for_remaining
    from system_safety import (
        SYSTEM_SPAWN_POSITION, reset_ship_to_system_spawn, star_impact_detected,
        stellar_collision_radius,
    )

    require(COLLAPSE_DURATION == 60.0, "live collapse authority reports 60 seconds")
    require(stage_for_remaining(60.0, COLLAPSE_DURATION) == "STABLE", "one-minute clock begins stable")
    require(stage_for_remaining(30.0, COLLAPSE_DURATION) == "UNSTABLE", "30 seconds is unstable")
    require(stage_for_remaining(12.0, COLLAPSE_DURATION) == "CRITICAL", "12 seconds is critical")

    star = (0.0, 0.0, 5000.0)
    radius = 2000.0
    require(star_impact_detected((0, 0, 0), (0, 0, 5000), star, radius), "direct sun impact is detected")
    require(star_impact_detected((0, 0, 0), (0, 0, 10000), star, radius), "high-speed tunnel through sun is detected")
    require(not star_impact_detected((5000, 5000, 0), (5000, 5000, 10000), star, radius), "clear flight path does not false-trigger")
    require(stellar_collision_radius(2000.0) == 2160.0, "stellar collision radius follows visible surface scale")

    class DummyShip:
        def __init__(self):
            self.pos = (9.0, 8.0, 7.0)
            self.vel = (120.0, -4.0, 88.0)
            self.yaw = self.pitch = self.roll = 1.0
            self.yaw_rate = self.pitch_rate = self.roll_rate = 2.0
            self.orientation = (0.0, 1.0, 0.0, 0.0)
            self.hyperspace = True
            self.hyper_t = 1.1
            self.hyper_cooldown = 0.0
            self.speed = self.speed_norm = 9.0
            self.boost_norm = self.hyper_norm = 1.0
            self.local_clearance = 8.0
            self.heat = 0.9
            self.state_dirty = False
            self.cargo = {"relic_core": 3, "salvage": 7}
            self.hull_hp = 83
            self.fuel = 44
        def set_orientation(self, value):
            self.orientation = tuple(value)

    ship = DummyShip()
    cargo_before = dict(ship.cargo)
    hull_before, fuel_before = ship.hull_hp, ship.fuel
    reset_ship_to_system_spawn(ship)
    require(ship.pos == SYSTEM_SPAWN_POSITION and ship.vel == (0.0, 0.0, 0.0), "reset restores default system position and stops movement")
    require(ship.orientation == (1.0, 0.0, 0.0, 0.0), "reset restores default orientation")
    require(not ship.hyperspace and ship.speed == 0.0, "reset clears active flight momentum")
    require(ship.cargo == cargo_before and ship.hull_hp == hull_before and ship.fuel == fuel_before, "reset preserves cargo hull and fuel")

    # Import the real generator through the same headless adapter used by the
    # regression suite and confirm deterministic bounded erosion data.
    generator_code = r'''
import sys, types
class Dummy:
    def __init__(self,*a,**k): pass
    def __call__(self,*a,**k): return Dummy()
    def __getattr__(self,n): return Dummy()
    def __iter__(self): return iter(())
    def __bool__(self): return False
class Pygame(types.ModuleType):
    def __getattr__(self,n):
        if n.startswith('K_') or n.isupper(): return 0
        return Dummy()
pg=Pygame('pygame'); pg.Surface=Dummy; pg.Rect=Dummy; pg.USEREVENT=24
for name in ('font','mixer','display','draw','transform','image','time','event','mouse','key'):
    setattr(pg,name,Dummy())
sys.modules['pygame']=pg
import space_core
one=space_core.SolarSystem(seed=20260804)
two=space_core.SolarSystem(seed=20260804)
assert len(one.planets)==1
assert len(one.planets[0].solar_erosion_pts)==72
assert isinstance(one.planets[0].solar_erosion_pts, tuple)
assert one.planets[0].solar_erosion_pts==two.planets[0].solar_erosion_pts
assert all(len(spec)==6 for spec in one.planets[0].solar_erosion_pts)
'''
    subprocess.run([sys.executable, "-B", "-c", generator_code], cwd=ROOT, check=True)
    require(True, "live generator creates deterministic fixed-size erosion specs")

    require(int(manifest.get("pass", 0)) >= 21, "manifest preserves Pass 21 or newer authority")
    require(manifest.get("collapse_failure_contract", {}).get("collapse_duration_seconds") == 60, "manifest locks one-minute collapse")
    require(manifest.get("stellar_safety_contract", {}).get("timer_restart") is False, "manifest locks non-restarting sun reset")
    require(manifest.get("solar_erosion_contract", {}).get("fixed_specs_per_planet") == 72, "manifest locks bounded erosion pool")
    require("60 seconds" in readme and "sun" in readme.lower() and "erosion" in readme.lower(), "README documents Pass 21 behavior")

    print("FINAL_RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
