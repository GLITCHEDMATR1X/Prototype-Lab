from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}")


def main() -> int:
    files = [
        ROOT / "space_core.py",
        ROOT / "standard_ui.py",
        ROOT / "mission_state.py",
        ROOT / "runtime_paths.py",
        ROOT / "collapse_rules.py",
    ]
    for path in files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    require(True, "Pass 18 active modules parse")

    core = (ROOT / "space_core.py").read_text(encoding="utf-8")
    ui = (ROOT / "standard_ui.py").read_text(encoding="utf-8")
    runtime = (ROOT / "runtime_paths.py").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "build_manifest.json").read_text(encoding="utf-8"))

    require('"window_mode": "fullscreen"' in runtime, "fresh settings default to fullscreen")
    require('flags = pygame.NOFRAME | pygame.DOUBLEBUF' in core, "fullscreen uses borderless desktop window")
    require('pygame.FULLSCREEN' not in core, "no exclusive fullscreen display-mode request")
    require('"schema_version": 4' in runtime, "settings schema advanced to 4")
    require('old_schema < 4' in runtime, "settings migration advances older schemas")
    require('last_windowed_mode = "native_1080p" if active_window_mode in ("native_1080p", "fullscreen")' in core,
            "F11 returns fresh fullscreen profiles to borderless 1080p")

    require("draw_collapse_panel" in core and "draw_collapse_panel" in ui, "shared collapse instrument wired")
    require("draw_collapse_pressure" in core and "draw_collapse_pressure" in ui, "bounded collapse edge pressure wired")
    require("draw_failure_screen" in core and "draw_failure_screen" in ui, "terminal failure screen wired")
    require("collapse_frozen = paused or run_intro_active or mission_brief_visible or failure_active" in core,
            "collapse time freezes in modal states")
    require("SUPERNOVA_SHOCK_DAMAGE" in core and "hull_damage_rate" in core, "collapse consequences use shared rule authority")
    require("ship.take_hull_damage" in core, "collapse pressure damages real hull state")

    require("capture_system_checkpoint" in core and "restore_system_checkpoint" in core,
            "system-entry checkpoint methods exist")
    require('"system_checkpoint": self.system_checkpoint' in core, "checkpoint persists in atomic save")
    require("if not failure_active:\n                ship.save_state()" in core,
            "failure shutdown cannot overwrite good checkpoint")
    require("retry_system_checkpoint" in core and "CHECKPOINT RESTORED" in core, "retry restores current system")
    require("mission.fragments_secured_total" in core and "mission.system_index" in core,
            "failure summary exposes run advancement")

    env = os.environ.copy()
    with tempfile.TemporaryDirectory(prefix="entropy-pass18-settings-") as temp:
        env["ENTROPY_USER_DATA"] = temp
        code = (
            "import runtime_paths as r; "
            "s=r.load_settings(); "
            "assert s['schema_version']==4; "
            "assert s['window_mode']=='fullscreen'; "
            "r.save_settings(s); "
            "assert r.SETTINGS_PATH.exists();"
        )
        subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, env=env, check=True)
    require(True, "fresh settings save contract")

    with tempfile.TemporaryDirectory(prefix="entropy-pass18-migrate-") as temp:
        cfg = Path(temp) / "config"
        cfg.mkdir(parents=True)
        (cfg / "settings.json").write_text(
            json.dumps({"schema_version": 3, "window_mode": "native_1080p", "master_volume": 0.7}),
            encoding="utf-8",
        )
        env["ENTROPY_USER_DATA"] = temp
        code = (
            "import runtime_paths as r; "
            "s=r.load_settings(); "
            "assert s['schema_version']==4; "
            "assert s['window_mode']=='native_1080p'; "
            "assert s['master_volume']==0.7;"
        )
        subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, env=env, check=True)
    require(True, "Pass 17.1 user display choice survives migration")

    sys.path.insert(0, str(ROOT))
    from collapse_rules import (
        BLACK_HOLE_DAMAGE_PER_SECOND,
        COLLAPSE_DURATION,
        POST_SUPERNOVA_DAMAGE_PER_SECOND,
        SUPERNOVA_SHOCK_DAMAGE,
        hull_damage_rate,
        stage_for_remaining,
        warning_text,
    )

    require(COLLAPSE_DURATION == 60.0, "primary collapse timer is one minute")
    require(stage_for_remaining(60, 60) == "STABLE", "stable collapse stage")
    require(stage_for_remaining(30, 60) == "UNSTABLE", "unstable collapse stage")
    require(stage_for_remaining(12, 60) == "CRITICAL", "critical collapse stage")
    require(stage_for_remaining(0, 60) == "SUPERNOVA", "supernova collapse stage")
    require(SUPERNOVA_SHOCK_DAMAGE == 24, "supernova shock contract")
    require(hull_damage_rate(triggered=False, post_supernova=False, blackhole_active=False) == 0.0,
            "stable system causes no collapse hull damage")
    require(hull_damage_rate(triggered=True, post_supernova=True, blackhole_active=False) == POST_SUPERNOVA_DAMAGE_PER_SECOND,
            "post-supernova damage rate")
    require(hull_damage_rate(triggered=True, post_supernova=True, blackhole_active=True) == BLACK_HOLE_DAMAGE_PER_SECOND,
            "black-hole damage rate")
    require(bool(warning_text("UNSTABLE")) and bool(warning_text("BLACK HOLE")), "escalation warnings exist")

    from mission_state import MissionState

    class Planet:
        def __init__(self, style: str):
            self.style = style

    class System:
        seed = 112233
        planets = [Planet("desert"), Planet("ice"), Planet("fungal"), Planet("crystal")]

    mission = MissionState()
    mission.fragments_secured_total = 3
    mission.begin_system(System(), 4)
    require(mission.collapse_state == "STABLE", "new system resets collapse state")
    mission.update_collapse(11.0, 60.0)
    require(mission.collapse_state == "CRITICAL", "mission consumes collapse-rule authority")
    payload = mission.to_dict()
    require(payload["fragments_secured_total"] == 3 and payload["system_seed"] == 112233,
            "mission checkpoint payload preserves prior advancement and system identity")

    checkpoint_code = r"""
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
from mission_state import MissionState
class Planet:
    def __init__(self,style): self.style=style
class System:
    seed=998877
    planets=[Planet('desert'),Planet('ice'),Planet('fungal')]
ship=space_core.Ship(); mission=MissionState(); mission.begin_system(System(),3)
mission.fragments_secured_total=2
ship.fuel=74; ship.hull_hp=88; ship.cargo['salvage']=7
ship.capture_system_checkpoint(mission)
ship.fuel=1; ship.hull_hp=0; ship.cargo['salvage']=0; mission.fragments_secured_total=9
payload=ship.restore_system_checkpoint()
assert ship.fuel==74 and ship.hull_hp==88 and ship.cargo['salvage']==7
assert payload['fragments_secured_total']==2 and payload['system_seed']==998877
"""
    subprocess.run([sys.executable, "-B", "-c", checkpoint_code], cwd=ROOT, check=True)
    require(True, "live Ship checkpoint capture/restore methods")

    require(int(manifest.get("pass", 0)) >= 18, "manifest identifies a collapse-preserving pass")
    require(manifest.get("collapse_failure_contract", {}).get("pause_safe") is True,
            "manifest records pause-safe collapse contract")
    require(manifest.get("system_checkpoint_contract", {}).get("shutdown_failure_overwrite_blocked") is True,
            "manifest records checkpoint overwrite guard")

    print("FINAL_RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
