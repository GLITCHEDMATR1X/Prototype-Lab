"""HoloCore HC-1 smoke: upward strata and the vessel in the open column.

Runs standalone HoloCore (main.py, unchanged) in its own window and drives it:

  1. seabed      the seabed looks exactly as before: clear colour, fog colour
                 and density are HoloCore's originals, no marine snow, no ring
  2. strata      strata.json loads; for each band the player is lifted into it,
                 the atmosphere (background, fog colour and density) matches the
                 band, free-drifting life and the band's drop-in assets stream in,
                 and a screenshot is taken looking across the column
  3. title       crossing a band floor shows the band title, then it fades
  4. vessel      piloted climb with Shift is faster than without; the vessel
                 rises into a higher band and the strata follow the pilot camera;
                 stepping out at altitude keeps you in the column; the parked
                 vessel neither boards nor blocks a player flying far above it
  5. frames      average frame time at the seabed and in the Drift Column

Writes logs/holocore_strata_smoke_report.json and logs/holocore_strata_*.png.
Usage (from the HoloCore folder):  python tools/smoke_holocore_strata.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from panda3d.core import Point3, Vec3  # noqa: E402

import main as holocore_main  # noqa: E402

LOG_DIR = ROOT / "logs"
REPORT = LOG_DIR / "holocore_strata_smoke_report.json"


class StrataSmoke:
    def __init__(self) -> None:
        self.app = holocore_main.HoloVerseWorldPrototype()
        self.steps: list[dict] = []
        self.shots: list[str] = []

    # helpers --------------------------------------------------------
    def frames(self, n: int = 3) -> None:
        for _ in range(n):
            self.app.taskMgr.step()

    def step(self, name: str, ok: bool, **info) -> None:
        self.steps.append({"step": name, "ok": bool(ok), **info})
        print(f"strata_smoke {name}: {'PASS' if ok else 'FAIL'} {json.dumps(info)[:300]}")

    def lift_player(self, x: float, y: float, z_abs: float) -> None:
        app = self.app
        ground = app._surface_z_for_player(Vec3(x, y, 0.0))
        app.player_surface_offset = float(z_abs) - ground
        app.player.setPos(Vec3(x, y, z_abs))
        app.camera.reparentTo(app.player)
        app.camera.setPos(0, 0, app.eye_height)
        app.camera.setHpr(0, 4.0, 0)
        app.outer_world.sync_around(app.player.getPos(app.render), force=True, immediate=True)

    def shot(self, name: str) -> str:
        path = LOG_DIR / f"holocore_strata_{name}.png"
        for _ in range(4):
            self.app.graphicsEngine.renderFrame()
        self.app.win.saveScreenshot(str(path))
        self.shots.append(str(path))
        return str(path)

    # checks ---------------------------------------------------------
    def check_seabed_unchanged(self) -> None:
        app = self.app
        strata = app.outer_world.strata
        self.lift_player(1180.0, -940.0, app._surface_z_for_player(Vec3(1180.0, -940.0, 0.0)))
        strata.settle()
        self.frames(3)
        bg = tuple(round(float(c), 4) for c in tuple(app.win.getClearColor())[:3])
        fog = app.render.getFog() if app.render.hasFog() else None
        fog_rgb = tuple(round(float(c), 4) for c in tuple(fog.getColor())[:3]) if fog is not None else None
        density = round(float(fog.getExpDensity()), 6) if fog is not None else None
        rings_shown = sum(1 for _b, n in strata.boundaries if not n.isHidden())
        self.step("seabed_unchanged", bg == (0.0, 0.0, 0.0025) and fog_rgb == (0.0, 0.0, 0.004) and density == 0.0022
                  and strata.snow_root.isHidden() and rings_shown == 0,
                  clear_color=bg, fog_color=fog_rgb, fog_density=density, snow_hidden=strata.snow_root.isHidden(), rings_shown=rings_shown)

    def check_bands(self) -> None:
        app = self.app
        strata = app.outer_world.strata
        self.step("strata_loaded", strata is not None and len(strata.bands) >= 5,
                  bands=[b.band_id for b in strata.bands] if strata else [])
        if strata is None:
            return
        x, y = 1180.0, -940.0
        for band in strata.bands:
            ceiling = next((b.floor for b in strata.bands if b.floor > band.floor), band.floor + 900.0)
            floor = max(band.floor, 13.0)
            z = floor + min(260.0, (ceiling - floor) * 0.5)
            self.lift_player(x, y, z)
            strata.settle()
            self.frames(4)
            strata.settle()
            rep = strata.report()
            atmo = strata.blended_atmosphere(rep["camera_z"])
            bg = tuple(app.win.getClearColor())[:3]
            fog = app.render.getFog() if app.render.hasFog() else None
            fog_ok = fog is not None and abs(fog.getExpDensity() - atmo["fog_density"]) < 1e-5
            bg_ok = all(abs(bg[i] - atmo["background"][i]) < 2e-3 for i in range(3))
            want_life = bool(band.creatures) or bool(strata.assets.get(band.band_id))
            kinds = rep["drifters"]
            has_assets = all(any(k == f"asset:{a.asset_id}" for k in kinds) for a in strata.assets.get(band.band_id, [])) if want_life else True
            life_ok = (not want_life) or sum(kinds.values()) > 0
            # look slightly up across the column
            app.camera.setHpr(0, 14.0, 0)
            shot = self.shot(band.band_id)
            self.step(f"band_{band.band_id}", rep["band"] == band.band_id and fog_ok and bg_ok and life_ok and has_assets,
                      camera_z=rep["camera_z"], cells=rep["cells"], drifters=kinds, background=rep["background"],
                      fog_density=rep["fog_density"], every_dropin_seen=has_assets, screenshot=shot)

    def showcase(self) -> None:
        """Portrait shots: the camera is put beside the nearest drifter of a kind."""
        app = self.app
        strata = app.outer_world.strata
        picks = (("drift_column", 430.0, "jellyfish", 70.0), ("lantern_shoals", 1040.0, "mermaid", 46.0),
                 ("leviathan_reach", 1840.0, "asset", 230.0), ("leviathan_reach", 1840.0, "octopus", 120.0))
        made = []
        for band_id, z, kind, back in picks:
            self.lift_player(1180.0, -940.0, z)
            strata.settle()
            self.frames(2)
            cam = strata.camera_position()
            best = None
            for cell in strata.cells.values():
                for d in cell.drifters:
                    if d.kind != kind:
                        continue
                    if kind == "asset" and (d.asset is None or d.asset.asset_id != "leviathan_ribcage"):
                        continue
                    dist = (d.node_root.getPos(app.render) - cam).length()
                    if best is None or dist < best[0]:
                        best = (dist, d)
            if best is None:
                continue
            d = best[1]
            target = d.node_root.getPos(app.render)
            # Move the player there so streaming, LOD and fades follow the camera.
            self.lift_player(target.x - back * 0.7, target.y - back * 0.7, target.z + back * 0.15)
            strata.update(0.0, strata._time, force=True)
            app.camera.lookAt(app.render, target)
            strata.update(0.0, strata._time, force=True)
            app.camera.lookAt(app.render, d.node_root.getPos(app.render))
            made.append(self.shot(f"showcase_{band_id}_{kind}"))
        self.step("showcase_shots", len(made) >= 3, screenshots=made)

    def check_title(self) -> None:
        strata = self.app.outer_world.strata
        before = strata.band_changes
        self.lift_player(1180.0, -940.0, 150.0)
        strata.update(0.02)
        self.lift_player(1180.0, -940.0, 400.0)
        strata.update(0.02)
        title = getattr(strata, "_title", None)
        text = title.getText() if title is not None else ""
        for _ in range(12):
            strata.update(0.05)
        alpha_mid = float(strata.title_alpha)
        for _ in range(120):
            strata.update(0.05)
        alpha_end = float(strata.title_alpha)
        self.step("band_title_on_crossing", strata.band_changes > before and "DRIFT COLUMN" in text and alpha_mid > 0.5 and alpha_end < 0.01,
                  text=text, alpha_visible=round(alpha_mid, 3), alpha_after=round(alpha_end, 3))

    def check_vessel(self) -> None:
        app = self.app
        vessel = getattr(app, "holo_vessel", None)
        if vessel is None:
            self.step("vessel_present", False)
            return
        strata = app.outer_world.strata
        vessel.flight_altitude = 0.0
        vessel.update_ground_lock(app._holo_vessel_ground_z)
        app._enter_holo_vessel_pilot_seat()
        app.key_map["space"] = True
        a0 = float(vessel.flight_altitude)
        app._update_holo_vessel_piloting(0.05)
        plain = float(vessel.flight_altitude) - a0
        app.key_map["shift"] = True
        a1 = float(vessel.flight_altitude)
        app._update_holo_vessel_piloting(0.05)
        boosted = float(vessel.flight_altitude) - a1
        # climb into the Lantern Shoals with Shift held
        for _ in range(200):
            app._update_holo_vessel_piloting(0.05)
            if vessel.root.getZ() > 900.0:
                break
        app.key_map["space"] = False
        app.key_map["shift"] = False
        strata.settle()
        self.frames(3)
        rep = strata.report()
        cam_z = float(app.camera.getZ(app.render))
        app.camera.lookAt(vessel.pilot_look_world_position())
        shot = self.shot("vessel_pilot_lantern_shoals")
        self.step("vessel_shift_boost_climb", boosted > plain * 2.0 and rep["band"] == "lantern_shoals" and cam_z > 760.0,
                  climb_plain_m=round(plain, 3), climb_boosted_m=round(boosted, 3), vessel_z=round(float(vessel.root.getZ()), 1),
                  band=rep["band"], screenshot=shot)
        # step out into the column at altitude
        app._leave_holo_vessel_pilot_seat()
        app._exit_holo_vessel_to_terrain()
        pz = float(app.player.getZ(app.render))
        ground = app._surface_z_for_player(app.player.getPos(app.render))
        self.step("vessel_exit_stays_in_column", pz > 700.0 and abs(pz - float(vessel.root.getZ())) < 1.0,
                  player_z=round(pz, 2), seabed_z=round(ground, 2), vessel_z=round(float(vessel.root.getZ()), 2))
        # park it back down; a player far above should neither board nor be blocked
        vessel.flight_altitude = 0.0
        vessel.update_ground_lock(app._holo_vessel_ground_z)
        entry = vessel.entry_world_position()
        high = Point3(entry.x, entry.y, entry.z + 400.0)
        over_hull = vessel.local_point(0.0, 5.0, 0.0)
        over_hull.setZ(over_hull.z + 400.0)
        on_ramp = Point3(entry)
        self.step("vessel_ignores_player_far_above",
                  (not vessel.is_near_entry(high)) and (not vessel.blocks_outside_position(over_hull)) and vessel.is_near_entry(on_ramp),
                  near_entry_high=vessel.is_near_entry(high), blocks_high=vessel.blocks_outside_position(over_hull),
                  near_entry_on_ramp=vessel.is_near_entry(on_ramp))

    def check_frames(self) -> None:
        out = {}
        strata = self.app.outer_world.strata

        def measure(n: int = 60) -> float:
            self.frames(10)
            t0 = time.perf_counter()
            self.frames(n)
            return round((time.perf_counter() - t0) / n * 1000.0, 2)

        for label, z in (("seabed", 13.0), ("drift_column", 420.0)):
            self.lift_player(1180.0, -940.0, z)
            strata.settle()
            out[label] = measure()
            strata.root.stash()
            out[label + "_strata_hidden"] = measure()
            strata.root.unstash()
        # Software GL under Xvfb is far slower than an RTX 2070 and is raster
        # bound (the seabed grid alone costs most of the seabed figure); this
        # guards against regressions, it is not a performance target.
        self.step("frame_time_ms", all(v < 400.0 for v in out.values()), frame_ms=out)

    def run(self) -> dict:
        self.frames(90)  # let the seabed stream in
        try:
            self.check_seabed_unchanged()
            self.check_bands()
            self.showcase()
            self.check_title()
            self.check_vessel()
            self.check_frames()
        except Exception as exc:
            import traceback

            traceback.print_exc()
            self.step("exception", False, error=f"{exc.__class__.__name__}:{exc}")
        errors = [s["step"] for s in self.steps if not s["ok"]]
        report = {
            "schema": 1,
            "kind": "holocore_hc1_strata_smoke",
            "status": "PASS" if not errors else "FAIL",
            "errors": errors,
            "steps": self.steps,
            "screenshots": self.shots,
            "strata": self.app.outer_world.strata.report() if self.app.outer_world.strata else None,
        }
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"holocore_strata_smoke status={report['status']} errors={errors} report={REPORT}")
        return report


if __name__ == "__main__":
    result = StrataSmoke().run()
    sys.exit(0 if result["status"] == "PASS" else 1)
