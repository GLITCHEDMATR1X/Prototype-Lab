from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.world_data import LAYOUTS, WORLD_RECT, expand_object  # noqa: E402
from tools.pass14_world_verify import validate_layout  # noqa: E402

PASS17_FROZEN = {
    "game/sim.py": "9bcabf3d5997f8a2677c9dde67a3c74e9825b1c1704dffaded33dc556a8853cc",
    "game/data.py": "eb2262c00d24519e075e91e4a55bf2f4aa44e02b0e09475658f10c5b5db2b159",
    "game/world.py": "3a3d1a345e5a1f2b98e57f425324bcbe3e88bc33c35e27f92146f7fa993f56b4",
    "game/actors.py": "8be771ef389f8e0f739eebc5de59148c4671ca551f39d36ea44fe5fec7172a8e",
    "game/actor_visuals.py": "bffe05ba33677bfc59b322495ef233f739c5707d5bde1c46c5e6473de8a3a881",
    "game/audio.py": "4b0be21e1c38c883a4cdd9b0e26cb250f5de4744132e2f4fe23e46af9f8e2221",
    "game/app.py": "8cb044195b01ffd01df9aede7ee58c567e7d878e7894a74f1b111b89080e2c29",
    "game/render.py": "f2f05bfa62fe37155bbaac8584edb3b809eea34eb42cf4954934ad7585c245c5",
}

PASS17_MARKERS = {
    "purge": {
        "entry": (120, 900), "extraction": (120, 900), "boss": (948, 554),
        "enemy_0": (498, 554), "enemy_1": (698, 554), "enemy_2": (1298, 554),
        "enemy_3": (1798, 254), "enemy_4": (1798, 554), "enemy_5": (398, 904), "enemy_6": (1448, 904),
        "comp_0": (98, 254), "comp_1": (1548, 704), "spawn_gate_0": (98, 254), "spawn_gate_1": (1548, 704),
    },
    "recovery": {
        "entry": (120, 900), "extraction": (120, 900), "reroute_extraction": (98, 254),
        "artifact": (1448, 604), "memory_well": (1098, 904), "boss": (1798, 804),
        "enemy_0": (298, 554), "enemy_1": (498, 554), "enemy_2": (898, 554), "enemy_3": (1098, 554), "enemy_4": (1298, 504),
        "comp_0": (1798, 254), "comp_1": (1798, 604), "spawn_gate_0": (1798, 254), "spawn_gate_1": (1798, 604),
    },
    "rescue": {
        "entry": (120, 900), "extraction": (120, 900), "boss": (1798, 604),
        "civilian_0": (648, 554), "civilian_1": (1048, 604), "civilian_2": (1348, 604),
        "enemy_0": (248, 554), "enemy_1": (448, 554), "enemy_2": (548, 704), "enemy_3": (1198, 554), "enemy_4": (1798, 254),
        "comp_0": (98, 254), "comp_1": (1798, 404), "spawn_gate_0": (98, 254), "spawn_gate_1": (1798, 404),
    },
}

EXPECTED_MAZE_PIECES = {"purge": 7, "recovery": 7, "rescue": 6}
EXPECTED_PHYSICAL = {"purge": 8, "recovery": 8, "rescue": 8}
EXPECTED_TEXTURES = {
    "cathedral_labyrinth_stone.png",
    "blackglass_labyrinth_panels.png",
    "ossuary_labyrinth_bulkheads.png",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    frozen = {rel: sha(ROOT / rel) == digest for rel, digest in PASS17_FROZEN.items()}
    geometry = {}
    all_ok = all(frozen.values())
    world_area = WORLD_RECT[2] * WORLD_RECT[3]

    for key, layout in LAYOUTS.items():
        base = validate_layout(key)
        expanded = [expand_object(o) for o in layout["objects"]]
        physical = [o for o in expanded if o["movement"]]
        maze_count = sum(1 for o in physical if o.get("maze_piece"))
        part_area = sum(w * h for o in physical for _, _, w, h in o["parts"])
        density = 100.0 * part_area / world_area
        marker_preserved = layout["markers"] == PASS17_MARKERS[key]
        access_breaks = list(layout.get("access_breaks", []))
        destructibles = sum(1 for o in physical if o["destructible"])
        row_ok = (
            base["pass"]
            and len(physical) == EXPECTED_PHYSICAL[key]
            and maze_count == EXPECTED_MAZE_PIECES[key]
            and len(access_breaks) == 4
            and marker_preserved
            and destructibles >= 1
            and 13.0 <= density <= 15.5
        )
        geometry[key] = {
            "pass": row_ok,
            "layout": layout["name"],
            "physical_objects": len(physical),
            "maze_pieces": maze_count,
            "access_breaks": access_breaks,
            "minimum_object_gap": base["minimum_object_gap"],
            "minimum_live_marker_gap": base["minimum_live_marker_gap"],
            "routes_valid_before_destruction": base["all_required_routes_reachable"],
            "marker_positions_identical_to_pass17": marker_preserved,
            "destructible_shortcuts": destructibles,
            "solid_density_percent_estimate": round(density, 2),
            "issues": base["issues"],
        }
        all_ok = all_ok and row_ok

    textures = {}
    from PIL import Image
    for name in sorted(EXPECTED_TEXTURES):
        p = ROOT / "assets" / "world" / name
        ok = p.exists()
        size = None
        mode = None
        if ok:
            with Image.open(p) as im:
                size = list(im.size)
                mode = im.mode
                ok = im.size == (64, 64) and im.mode in {"RGB", "RGBA"}
        textures[name] = {"pass": ok, "size": size, "mode": mode}
        all_ok = all_ok and ok

    payload = {
        "pass18_broken_maze_contract": "PASS" if all_ok else "FAIL",
        "source_base": "user-supplied HEX CONTRACT Pass 17 World Material Readability full package",
        "gameplay_files_byte_identical_to_pass17": frozen,
        "marker_positions_preserved": all(v["marker_positions_identical_to_pass17"] for v in geometry.values()),
        "geometry": geometry,
        "new_material_textures": textures,
        "contract": {
            "minimum_obstacle_gap_px": 120,
            "largest_required_actor_radius_px": 36,
            "minimum_live_marker_spacing_px": 140,
            "destruction_required_for_route": False,
        },
    }
    out = ROOT / "verification" / "reports" / "pass18_maze_worlds.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
