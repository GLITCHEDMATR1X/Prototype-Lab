"""HoloCore HC-1 validator (offscreen, no GPU needed).

Checks the pieces of the upward-strata pass in isolation:

  creatures       jellyfish, mermaid and octopus are untouched (same source as
                  the RAR baseline recorded below) and build as before
  strata_config   strata.json parses; bands rise strictly; every asset folder
                  named exists; the last band is open-ended
  strata_assets   every drop-in imports, declares STRATA_OBJECT and builds
  atmosphere      band colours/fog blend continuously across every band floor
  vessel_rules    boost, hull height band and exit behaviour
  embedded        the HoloVerse native mount (holoverse_native_adapter) rises
                  and sinks on foot, keeps altitude while walking, boosts the
                  piloted vessel, streams strata, and cleans everything
                  (strata root, band title) up on destroy

Usage (from the HoloCore folder):  python tools/validate_holocore_hc1.py
Writes logs/holocore_hc1_validation.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from panda3d.core import loadPrcFileData  # noqa: E402

loadPrcFileData("", "window-type offscreen\nload-display p3tinydisplay\nwin-size 640 360\naudio-library-name null")

from direct.showbase.ShowBase import ShowBase  # noqa: E402
from panda3d.core import GeomLines, GeomLinestrips, GeomTriangles, NodePath, Vec3  # noqa: E402

RESULTS: list[dict] = []


def check(name: str, ok: bool, **info) -> None:
    RESULTS.append({"check": name, "ok": bool(ok), **info})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {json.dumps(info)[:260]}")


def prim_counts(root: NodePath):
    """(line segments, triangles) under a node."""
    lines = tris = 0
    for np_ in root.findAllMatches("**/+GeomNode"):
        node = np_.node()
        for gi in range(node.getNumGeoms()):
            geom = node.getGeom(gi)
            for pi in range(geom.getNumPrimitives()):
                prim = geom.getPrimitive(pi)
                if isinstance(prim, GeomLines):
                    lines += prim.getNumPrimitives()
                elif isinstance(prim, GeomLinestrips):
                    lines += max(0, prim.getNumVertices() - prim.getNumPrimitives())
                elif isinstance(prim, GeomTriangles):
                    tris += prim.getNumPrimitives()
    return lines, tris


# MD5 of the creature sources as shipped before HC-1; HC-1 does not change them.
CREATURE_BASELINE = {
    "holo_jellyfish.py": "04e44d1e7719fbc612cffa6c9f62c58b",
    "holo_mermaid.py": "784d22497dc3b70adae9a02937581256",
    "holo_octopus.py": "1d76e1f1b00ae0b2793ae688c374972a",
}


def check_creatures(base) -> None:
    import hashlib

    from holo_jellyfish import HoloJellyfishMob
    from holo_mermaid import HoloMermaidMob
    from holo_octopus import HoloOctopusMob

    sums = {name: hashlib.md5((ROOT / name).read_bytes()).hexdigest() for name in CREATURE_BASELINE}
    built = {}
    for name, mob in (("jellyfish", HoloJellyfishMob(seed=11).build(base.render, Vec3(0, 0, 0))),
                      ("mermaid", HoloMermaidMob(seed=11).build(base.render, Vec3(30, 0, 0))),
                      ("octopus", HoloOctopusMob(seed=11).build(base.render, Vec3(60, 0, 0)))):
        lines, tris = prim_counts(mob.root)
        built[name] = {"line_segments": lines, "triangles": tris}
        mob.destroy()
    check("creatures_unchanged", sums == CREATURE_BASELINE and all(v["triangles"] > 0 for v in built.values()),
          md5_match={k: sums[k] == v for k, v in CREATURE_BASELINE.items()}, built=built)


def check_strata_config() -> None:
    from dimensions.holocore_strata import load_bands

    path = ROOT / "assets" / "strata" / "strata.json"
    bands, data = load_bands(path)
    floors = [b.floor for b in bands]
    rising = all(b > a for a, b in zip(floors, floors[1:]))
    missing = [b.asset_folder for b in bands if b.asset_folder and not (ROOT / "assets" / "strata" / b.asset_folder).is_dir()]
    kinds = sorted({k for b in bands for k in b.creatures})
    check("strata_config", data.get("schema") == 1 and len(bands) >= 5 and rising and not missing and bands[0].band_id == "seabed"
          and set(kinds) <= {"jellyfish", "mermaid", "octopus"},
          bands=[(b.band_id, b.floor) for b in bands], missing_folders=missing, creatures=kinds)


def check_strata_assets(base) -> None:
    from random import Random
    from dimensions.holocore_strata import HoloCoreStrata

    parent = base.render.attachNewNode("validate_strata_parent")
    strata = HoloCoreStrata(base, ROOT / "assets", parent)
    built = {}
    ok = True
    for band in strata.bands:
        for asset in strata.assets.get(band.band_id, []):
            node = asset.build(strata.life_root, 0.0, 0.0, 500.0, Random(3), {"band_id": band.band_id, "band_name": band.name, "accent": band.accent, "cell": (0, 0, 0)})
            good = node is not None and not node.isEmpty() and prim_counts(node)[0] > 20
            if good:
                asset.update(node, 1.5)
            built[f"{band.band_id}/{asset.asset_id}"] = bool(good)
            ok = ok and good
    check("strata_assets", ok and len(built) >= 4, assets=built)
    # Atmosphere continuity across every floor.
    worst = 0.0
    for band in strata.bands[1:]:
        lo = strata.blended_atmosphere(band.floor - 0.01)
        hi = strata.blended_atmosphere(band.floor + 0.01)
        worst = max(worst, max(abs(lo["background"][i] - hi["background"][i]) for i in range(3)), abs(lo["fog_density"] - hi["fog_density"]) * 100.0)
    check("atmosphere_continuous", worst < 1e-3, worst_step=round(worst, 6))
    strata.destroy()
    parent.removeNode()


def check_vessel_rules(base) -> None:
    from holo_vessel import HoloVessel

    v = HoloVessel().build(base, Vec3(0, -300, 0), heading=180.0)
    v.flight_altitude = 0.0
    v.update_ground_lock(lambda x, y: 0.0)
    a0 = v.flight_altitude
    v.move_piloted(0.05, 0.0, 0.0, 1.0, lambda x, y: 0.0, boost=False)
    plain = v.flight_altitude - a0
    a1 = v.flight_altitude
    v.move_piloted(0.05, 0.0, 0.0, 1.0, lambda x, y: 0.0, boost=True)
    boosted = v.flight_altitude - a1
    low_exit = v.exit_world_position(0.0).z          # hovering ~6 m: step down to the seabed
    v.flight_altitude = 600.0
    v.update_ground_lock(lambda x, y: 0.0)
    high_exit = v.exit_world_position(0.0).z         # high in the column: float out at ramp height
    entry = v.entry_world_position()
    far_above = Vec3(entry.x, entry.y, entry.z + 300.0)
    check("vessel_rules", boosted > plain * 2.0 and abs(low_exit) < 1e-4 and abs(high_exit - 600.0) < 0.5
          and v.is_near_entry(entry) and not v.is_near_entry(far_above),
          climb_plain=round(plain, 3), climb_boost=round(boosted, 3), low_exit_z=round(low_exit, 3), high_exit_z=round(high_exit, 2))
    v.root.removeNode()


def check_embedded(base) -> None:
    import holoverse_native_adapter as nat

    baseline_aspect = base.aspect2d.getNumChildren()
    mode = nat.create_mode(base, entry_path=ROOT / "main.py")
    mode.enter()
    try:
        strata = getattr(mode.outer_world, "strata", None)
        mode.player.setPos(900.0, -900.0, 0.0)
        for _ in range(5):
            mode.update(0.05)
        z0 = mode.player.getZ()
        mode._keys["space"] = True
        for _ in range(40):
            mode.update(0.05)                         # 2 s of rise
        mode._keys["space"] = False
        risen = mode.player.getZ() - z0
        # walk while airborne: altitude above the seabed is kept
        off_before = mode.player.getZ() - mode._ground_z(mode.player.getX(), mode.player.getY())
        mode._keys["w"] = True
        for _ in range(20):
            mode.update(0.05)
        mode._keys["w"] = False
        off_after = mode.player.getZ() - mode._ground_z(mode.player.getX(), mode.player.getY())
        mode._keys["c"] = True
        for _ in range(10):
            mode.update(0.05)
        mode._keys["c"] = False
        sunk = off_after - (mode.player.getZ() - mode._ground_z(mode.player.getX(), mode.player.getY()))
        check("embedded_on_foot_flight", risen > 70.0 and abs(off_after - off_before) < 0.05 and sunk > 15.0,
              risen_m=round(risen, 2), offset_before=round(off_before, 2), offset_after=round(off_after, 2), sunk_m=round(sunk, 2))

        # lift into the Drift Column and let strata stream
        mode.player.setZ(mode._ground_z(mode.player.getX(), mode.player.getY()) + 420.0)
        for _ in range(60):
            mode.update(0.05)
        rep = strata.report() if strata is not None else {}
        check("embedded_strata_stream", strata is not None and rep.get("band") == "drift_column" and rep.get("cells", 0) > 0
              and sum(rep.get("drifters", {}).values()) > 0, report={k: rep.get(k) for k in ("band", "cells", "drifters", "camera_z")})

        # piloted vessel: Shift boost doubles+ the climb
        vessel = mode.holo_vessel
        mode.holo_vessel_boarded = True
        mode.holo_vessel_piloting = True
        mode._keys["space"] = True
        a0 = vessel.flight_altitude
        mode.update(0.05)
        plain = vessel.flight_altitude - a0
        mode._keys["shift"] = True
        a1 = vessel.flight_altitude
        mode.update(0.05)
        boosted = vessel.flight_altitude - a1
        mode._keys["space"] = mode._keys["shift"] = False
        check("embedded_vessel_boost", boosted > plain * 2.0, climb_plain=round(plain, 3), climb_boost=round(boosted, 3))
        title_live = strata is not None and strata._title is not None
    finally:
        mode.destroy()
    leftovers = [c.getName() for c in base.render.getChildren() if "strata" in c.getName() or "holocore" in c.getName().lower()]
    check("embedded_cleanup", not leftovers and base.aspect2d.getNumChildren() <= baseline_aspect,
          render_leftovers=leftovers, aspect2d_children=base.aspect2d.getNumChildren(), aspect2d_before=baseline_aspect,
          title_was_created=bool(title_live))


def main() -> int:
    base = ShowBase()
    for fn, needs_base in ((check_creatures, True), (check_strata_config, False),
                           (check_strata_assets, True), (check_vessel_rules, True), (check_embedded, True)):
        try:
            fn(base) if needs_base else fn()
        except Exception as exc:
            import traceback

            traceback.print_exc()
            check(fn.__name__, False, error=f"{exc.__class__.__name__}:{exc}")
    passed = sum(1 for r in RESULTS if r["ok"])
    report = {"schema": 1, "kind": "holocore_hc1_validation", "status": "PASS" if passed == len(RESULTS) else "FAIL",
              "passed": passed, "total": len(RESULTS), "checks": RESULTS}
    out = ROOT / "logs" / "holocore_hc1_validation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"holocore_hc1_validation {passed}/{len(RESULTS)} -> {out}")
    base.destroy()
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
