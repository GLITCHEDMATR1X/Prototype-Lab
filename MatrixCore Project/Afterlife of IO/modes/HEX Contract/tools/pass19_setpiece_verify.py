from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.world_data import LAYOUTS, MAX_ACTOR_RADIUS, MIN_CLEAR_GAP, expand_object  # noqa: E402
from tools.pass14_world_verify import validate_layout  # noqa: E402

PASS18_WORLD_DATA = ROOT.parent / "world_data_pass18.py"

CORE_FROZEN = {
    "main.py": "6e74b175f9859b64976e2cc03509e8457598ce3d129037cdfc786d0eff131244",
    "game/sim.py": "9bcabf3d5997f8a2677c9dde67a3c74e9825b1c1704dffaded33dc556a8853cc",
    "game/data.py": "eb2262c00d24519e075e91e4a55bf2f4aa44e02b0e09475658f10c5b5db2b159",
    "game/world.py": "3a3d1a345e5a1f2b98e57f425324bcbe3e88bc33c35e27f92146f7fa993f56b4",
    "game/actors.py": "8be771ef389f8e0f739eebc5de59148c4671ca551f39d36ea44fe5fec7172a8e",
    "game/actor_visuals.py": "bffe05ba33677bfc59b322495ef233f739c5707d5bde1c46c5e6473de8a3a881",
    "game/audio.py": "4b0be21e1c38c883a4cdd9b0e26cb250f5de4744132e2f4fe23e46af9f8e2221",
    "game/app.py": "8cb044195b01ffd01df9aede7ee58c567e7d878e7894a74f1b111b89080e2c29",
    "game/render.py": "f2f05bfa62fe37155bbaac8584edb3b809eea34eb42cf4954934ad7585c245c5",
}

EXPECTED = {
    "purge": ["Flying Buttresses", "Altar Gate", "Choir Screens", "Broken Cloister", "Votive Rail"],
    "recovery": ["Mirror Archive", "Index Engine", "Stack Bridge", "Shard Barricade"],
    "rescue": ["Service Hook", "Signal Barricade", "Shrine Lane", "Split Bulkhead"],
}
DESTRUCTIBLE = {"Votive Rail", "Shard Barricade", "Split Bulkhead"}
TEXTURES = {
    "Flying Buttresses": "cathedral_flying_buttresses.png",
    "Altar Gate": "cathedral_altar_gate.png",
    "Choir Screens": "cathedral_choir_screens.png",
    "Broken Cloister": "cathedral_broken_cloister.png",
    "Votive Rail": "cathedral_votive_rail.png",
    "Mirror Archive": "blackglass_mirror_archive.png",
    "Index Engine": "blackglass_index_engine.png",
    "Stack Bridge": "blackglass_stack_bridge.png",
    "Shard Barricade": "blackglass_shard_barricade.png",
    "Service Hook": "ossuary_service_hook.png",
    "Signal Barricade": "ossuary_signal_barricade.png",
    "Shrine Lane": "ossuary_shrine_lane.png",
    "Split Bulkhead": "ossuary_split_bulkhead.png",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pass18():
    spec = importlib.util.spec_from_file_location("pass18_world_data", PASS18_WORLD_DATA)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Pass 18 world-data authority")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    base = load_pass18()
    frozen = {rel: (ROOT / rel).exists() and sha(ROOT / rel) == digest for rel, digest in CORE_FROZEN.items()}
    overall = all(frozen.values())
    maps = {}

    for key, expected_names in EXPECTED.items():
        layout = LAYOUTS[key]
        base_layout = base.LAYOUTS[key]
        base_by_id = {r["id"]: base.expand_object(r) for r in base_layout["objects"]}
        now_by_id = {r["id"]: expand_object(r) for r in layout["objects"]}
        bounds_equal = set(base_by_id) == set(now_by_id) and all(base_by_id[k]["bounds"] == now_by_id[k]["bounds"] for k in base_by_id)
        markers_equal = layout["markers"] == base_layout["markers"]

        records = [r for r in layout["objects"] if r.get("setpiece")]
        names = [r["setpiece"] for r in records]
        setpieces = {}
        for rec in records:
            ex = expand_object(rec)
            name = str(rec["setpiece"])
            setpieces[name] = {
                "id": rec["id"],
                "prefab": rec["prefab"],
                "texture": rec["texture"],
                "bounds": list(ex["bounds"]),
                "collision_parts": len(ex["parts"]),
                "real_movement_blocker": bool(ex["movement"] and ex["parts"]),
                "real_los_blocker": bool(ex["vision"] and ex["parts"]),
                "real_projectile_blocker": bool(ex["projectiles"] and ex["parts"]),
                "destructible": bool(ex["destructible"]),
            }

        geo = validate_layout(key)
        row_ok = (
            set(names) == set(expected_names) and len(names) == len(expected_names)
            and bounds_equal
            and markers_equal
            and geo["pass"]
            and geo["minimum_object_gap"] >= MIN_CLEAR_GAP
            and geo["minimum_live_marker_gap"] >= 140
            and geo["all_required_routes_reachable"]
            and MAX_ACTOR_RADIUS == 36
            and all(v["real_movement_blocker"] and v["real_los_blocker"] and v["real_projectile_blocker"] for v in setpieces.values())
            and all(setpieces[n]["destructible"] == (n in DESTRUCTIBLE) for n in expected_names)
        )
        maps[key] = {
            "pass": row_ok,
            "layout": layout["name"],
            "setpiece_count": len(records),
            "setpiece_names": names,
            "setpieces": setpieces,
            "pass18_outer_footprints_identical": bounds_equal,
            "pass18_marker_positions_identical": markers_equal,
            "minimum_obstacle_gap": geo["minimum_object_gap"],
            "minimum_live_marker_gap": geo["minimum_live_marker_gap"],
            "routes_with_all_cover_intact": geo["all_required_routes_reachable"],
            "issues": geo["issues"],
        }
        overall = overall and row_ok

    from PIL import Image
    texture_report = {}
    for setpiece, filename in TEXTURES.items():
        path = ROOT / "assets" / "world" / filename
        ok = path.exists()
        size = None
        mode = None
        if ok:
            with Image.open(path) as im:
                size = list(im.size)
                mode = im.mode
                ok = im.size == (64, 64) and im.mode in {"RGB", "RGBA"}
        texture_report[setpiece] = {"pass": ok, "file": filename, "size": size, "mode": mode}
        overall = overall and ok

    payload = {
        "pass19_tactical_setpiece_contract": "PASS" if overall else "FAIL",
        "source_base": "recovered HEX CONTRACT Pass 18 Broken-Maze Tactical Maps full package",
        "gameplay_ai_balance_source_byte_identical_to_pass18": frozen,
        "setpiece_identity_total": sum(len(v) for v in EXPECTED.values()),
        "maps": maps,
        "material_textures": texture_report,
        "contract": {
            "setpiece_counts": {"purge": 5, "recovery": 4, "rescue": 4},
            "minimum_obstacle_gap_px": 120,
            "largest_required_actor_radius_px": 36,
            "outer_footprints_must_match_pass18": True,
            "marker_positions_must_match_pass18": True,
            "destruction_required_for_progression": False,
            "visible_setpiece_parts_are_runtime_movement_los_projectile_geometry": True,
        },
    }
    out = ROOT / "verification" / "reports" / "pass19_tactical_setpieces.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
