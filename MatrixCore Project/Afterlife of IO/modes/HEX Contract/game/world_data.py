from __future__ import annotations

"""Pure-data tactical world authority for HEX CONTRACT Pass 20.

Pass 20 preserves the verified Pass 19 tactical setpiece kit and adds two
additional approved broken-maze layouts per contract.  Every variant keeps the
same marker authority, setpiece identities, movement/LOS/projectile geometry
rules, 120 px minimum obstacle gap, and maximum 36 px actor requirement.
"""

from typing import Iterable

WORLD_RECT = (28, 184, 1864, 806)
MAX_ACTOR_RADIUS = 36
MIN_CLEAR_GAP = 120
PREFERRED_CLEAR_GAP = 150
SPAWN_CLEARANCE = 150
EDGE_CLEARANCE = 44

# Compound maze prefabs are intentionally chunky but broken open.  Bounds are
# used by the conservative spacing validator; parts are the real collision,
# vision and projectile blockers used at runtime.
PREFABS = {
    "wall_short": {"size": (180, 56), "parts": [(0, 0, 180, 56)], "category": "wall", "movement": True, "vision": True, "projectiles": True},
    "wall_long": {"size": (280, 60), "parts": [(0, 0, 280, 60)], "category": "wall", "movement": True, "vision": True, "projectiles": True},
    "corner_l": {"size": (220, 220), "parts": [(0, 0, 220, 56), (0, 0, 56, 220)], "category": "corner", "movement": True, "vision": True, "projectiles": True},
    "corner_broken": {"size": (220, 220), "parts": [(0, 0, 132, 54), (0, 0, 54, 148)], "category": "corner", "movement": True, "vision": True, "projectiles": True},
    "pillar": {"size": (76, 76), "parts": [(0, 0, 76, 76)], "category": "object", "movement": True, "vision": True, "projectiles": True},
    "archive_stack": {"size": (210, 78), "parts": [(0, 0, 210, 78)], "category": "object", "movement": True, "vision": True, "projectiles": True},
    "relic_carriage": {"size": (300, 96), "parts": [(0, 0, 300, 96)], "category": "object", "movement": True, "vision": True, "projectiles": True},
    "shrine": {"size": (86, 86), "parts": [(0, 0, 86, 86)], "category": "object", "movement": True, "vision": True, "projectiles": True},
    "brittle_short": {"size": (190, 58), "parts": [(0, 0, 190, 58)], "category": "wall", "movement": True, "vision": True, "projectiles": True, "destructible": True, "hp": 82.0},
    "brittle_long": {"size": (250, 58), "parts": [(0, 0, 250, 58)], "category": "wall", "movement": True, "vision": True, "projectiles": True, "destructible": True, "hp": 112.0},

    # Pass 18 broken-maze grammar.
    "maze_hook_left": {
        "size": (280, 180),
        "parts": [(0, 0, 280, 58), (0, 0, 58, 180), (0, 122, 130, 58)],
        "category": "corner", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "maze_hook_right": {
        "size": (280, 180),
        "parts": [(0, 0, 280, 58), (222, 0, 58, 180), (150, 122, 130, 58)],
        "category": "corner", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "maze_hook_left_compact": {
        "size": (240, 180),
        "parts": [(0, 0, 240, 58), (0, 0, 58, 180), (0, 122, 130, 58)],
        "category": "corner", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "maze_hook_right_compact": {
        "size": (240, 180),
        "parts": [(0, 0, 240, 58), (182, 0, 58, 180), (110, 122, 130, 58)],
        "category": "corner", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "maze_t": {
        "size": (280, 180),
        "parts": [(0, 0, 280, 58), (111, 0, 58, 180), (0, 122, 84, 58), (196, 122, 84, 58)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True,
    },
    "maze_u": {
        "size": (300, 180),
        "parts": [(0, 0, 58, 180), (242, 0, 58, 180), (0, 122, 300, 58)],
        "category": "corner", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "maze_zig": {
        "size": (300, 160),
        "parts": [(0, 0, 180, 54), (126, 53, 174, 54), (0, 106, 180, 54)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "maze_broken_gate": {
        "size": (300, 130),
        "parts": [(0, 0, 72, 130), (228, 0, 72, 130), (72, 0, 58, 58), (170, 72, 58, 58)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "maze_broken_gate_wide": {
        "size": (360, 130),
        "parts": [(0, 0, 60, 130), (300, 0, 60, 130)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "maze_brittle_shortcut": {
        "size": (260, 58), "parts": [(0, 0, 260, 58)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "destructible": True, "hp": 118.0, "maze_piece": True, "access_breaks": 1,
    },
    "maze_split_wall": {
        "size": (280, 150),
        "parts": [(0, 0, 112, 58), (168, 0, 112, 58), (111, 92, 58, 58)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "maze_split_wall_compact": {
        "size": (220, 140),
        "parts": [(0, 0, 86, 58), (134, 0, 86, 58), (81, 58, 58, 82)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },

    # Pass 19 tactical setpiece kit. Every prefab keeps the exact outer size of
    # the Pass 18 object it replaces; only the internal blocking silhouette is
    # authored. Parts stay inside the predecessor's occupied regions so the
    # verified broken-open routes can only stay equal or become more open.
    "setpiece_flying_buttresses": {
        "size": (280, 180),
        "parts": [(0, 0, 86, 58), (106, 0, 70, 58), (196, 0, 84, 58),
                  (0, 0, 58, 68), (0, 86, 58, 94), (0, 122, 130, 58)],
        "category": "corner", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "setpiece_altar_gate": {
        "size": (300, 130),
        "parts": [(0, 0, 72, 130), (228, 0, 72, 130),
                  (72, 0, 44, 58), (184, 72, 44, 58)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "setpiece_choir_screens": {
        "size": (280, 180),
        "parts": [(0, 0, 78, 58), (96, 0, 88, 58), (202, 0, 78, 58),
                  (111, 0, 58, 76), (111, 94, 58, 86),
                  (0, 122, 70, 58), (210, 122, 70, 58)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True,
    },
    "setpiece_broken_cloister": {
        "size": (300, 180),
        "parts": [(0, 0, 58, 72), (0, 90, 58, 90),
                  (242, 0, 58, 82), (242, 104, 58, 76),
                  (0, 122, 84, 58), (104, 122, 82, 58), (206, 122, 94, 58)],
        "category": "corner", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "setpiece_votive_rail": {
        "size": (260, 58),
        "parts": [(0, 0, 74, 58), (88, 0, 72, 58), (176, 0, 84, 58)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "destructible": True, "hp": 118.0, "maze_piece": True, "access_breaks": 1,
    },
    "setpiece_mirror_archive": {
        "size": (210, 78),
        "parts": [(0, 0, 60, 78), (76, 0, 58, 78), (150, 0, 60, 78)],
        "category": "object", "movement": True, "vision": True, "projectiles": True,
    },
    "setpiece_index_engine": {
        "size": (280, 180),
        "parts": [(0, 0, 70, 58), (88, 0, 104, 58), (210, 0, 70, 58),
                  (111, 0, 58, 72), (111, 94, 58, 86),
                  (0, 122, 76, 58), (204, 122, 76, 58)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True,
    },
    "setpiece_stack_bridge": {
        "size": (300, 160),
        "parts": [(0, 0, 78, 54), (92, 0, 88, 54),
                  (126, 53, 76, 54), (216, 53, 84, 54),
                  (0, 106, 82, 54), (98, 106, 82, 54)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "setpiece_shard_barricade": {
        "size": (260, 58),
        "parts": [(0, 0, 62, 58), (76, 0, 50, 58), (140, 0, 44, 58), (198, 0, 62, 58)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "destructible": True, "hp": 118.0, "maze_piece": True, "access_breaks": 1,
    },
    "setpiece_service_hook": {
        "size": (240, 180),
        "parts": [(0, 0, 74, 58), (94, 0, 70, 58), (184, 0, 56, 58),
                  (0, 0, 58, 70), (0, 88, 58, 92),
                  (0, 122, 62, 58), (76, 122, 54, 58)],
        "category": "corner", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "setpiece_signal_barricade": {
        "size": (300, 130),
        "parts": [(0, 0, 72, 130), (228, 0, 72, 130),
                  (72, 0, 38, 58), (190, 72, 38, 58)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "setpiece_shrine_lane": {
        "size": (300, 180),
        "parts": [(0, 0, 58, 72), (0, 90, 58, 90),
                  (242, 0, 58, 72), (242, 90, 58, 90),
                  (0, 122, 72, 58), (88, 122, 54, 58),
                  (158, 122, 54, 58), (228, 122, 72, 58)],
        "category": "corner", "movement": True, "vision": True, "projectiles": True,
        "maze_piece": True, "access_breaks": 1,
    },
    "setpiece_split_bulkhead": {
        "size": (260, 58),
        "parts": [(0, 0, 92, 58), (108, 0, 44, 58), (168, 0, 92, 58)],
        "category": "wall", "movement": True, "vision": True, "projectiles": True,
        "destructible": True, "hp": 118.0, "maze_piece": True, "access_breaks": 1,
    },
    "spawn_gate": {"size": (96, 96), "parts": [], "category": "spawner", "movement": False, "vision": False, "projectiles": False},
}

TEXTURE_FAMILIES = {
    "purge": {"wall": "cathedral_labyrinth_stone", "corner": "cathedral_labyrinth_stone", "object": "cathedral_reliquary", "spawner": "cathedral_spawn"},
    "recovery": {"wall": "blackglass_labyrinth_panels", "corner": "blackglass_labyrinth_panels", "object": "blackglass_archive", "spawner": "blackglass_spawn"},
    "rescue": {"wall": "ossuary_labyrinth_bulkheads", "corner": "ossuary_labyrinth_bulkheads", "object": "ossuary_carriage", "spawner": "ossuary_spawn"},
}

LAYOUTS = {
    "purge": {
        "name": "SAINT VOLTAGE / BROKEN NAVE LABYRINTH",
        "access_breaks": ["west_entry", "central_crossing", "south_flank", "east_fracture"],
        "objects": [
            {"id": "p_hook_nw", "prefab": "setpiece_flying_buttresses", "x": 220, "y": 250, "rotation": 0, "texture": "cathedral_flying_buttresses", "setpiece": "Flying Buttresses"},
            {"id": "p_t_north", "prefab": "setpiece_choir_screens", "x": 630, "y": 250, "rotation": 0, "texture": "cathedral_choir_screens", "setpiece": "Choir Screens"},
            {"id": "p_gate_north", "prefab": "setpiece_altar_gate", "x": 1030, "y": 250, "rotation": 0, "texture": "cathedral_altar_gate", "setpiece": "Altar Gate"},
            {"id": "p_hook_ne", "prefab": "maze_hook_right_compact", "x": 1450, "y": 250, "rotation": 0, "texture": "cathedral_labyrinth_stone"},
            {"id": "p_u_south", "prefab": "setpiece_broken_cloister", "x": 220, "y": 650, "rotation": 180, "texture": "cathedral_broken_cloister", "setpiece": "Broken Cloister"},
            {"id": "p_zig_south", "prefab": "maze_zig", "x": 650, "y": 680, "rotation": 0, "texture": "cathedral_labyrinth_stone"},
            {"id": "p_shortcut", "prefab": "setpiece_votive_rail", "x": 1070, "y": 700, "rotation": 0, "texture": "cathedral_votive_rail", "setpiece": "Votive Rail"},
            {"id": "p_reliquary_pillar", "prefab": "pillar", "x": 1710, "y": 760, "rotation": 0, "texture": "cathedral_pillar"},
        ],
        "markers": {
            "entry": (120, 900), "extraction": (120, 900), "boss": (948, 554),
            "enemy_0": (498, 554), "enemy_1": (698, 554), "enemy_2": (1298, 554),
            "enemy_3": (1798, 254), "enemy_4": (1798, 554), "enemy_5": (398, 904), "enemy_6": (1448, 904),
            "comp_0": (98, 254), "comp_1": (1548, 704),
            "spawn_gate_0": (98, 254), "spawn_gate_1": (1548, 704),
        },
    },
    "recovery": {
        "name": "BLACKGLASS / FRACTURED INDEX MAZE",
        "access_breaks": ["west_entry", "index_crossing", "memory_well_lane", "east_archive_gap"],
        "objects": [
            {"id": "r_hook_nw", "prefab": "maze_hook_right", "x": 220, "y": 250, "rotation": 0, "texture": "blackglass_labyrinth_panels"},
            {"id": "r_t_north", "prefab": "setpiece_index_engine", "x": 630, "y": 250, "rotation": 0, "texture": "blackglass_index_engine", "setpiece": "Index Engine"},
            {"id": "r_gate_north", "prefab": "maze_broken_gate", "x": 1030, "y": 250, "rotation": 0, "texture": "blackglass_labyrinth_panels"},
            {"id": "r_index_stack", "prefab": "setpiece_mirror_archive", "x": 1450, "y": 280, "rotation": 0, "texture": "blackglass_mirror_archive", "setpiece": "Mirror Archive"},
            {"id": "r_u_south", "prefab": "maze_u", "x": 220, "y": 650, "rotation": 0, "texture": "blackglass_labyrinth_panels"},
            {"id": "r_zig_south", "prefab": "setpiece_stack_bridge", "x": 650, "y": 650, "rotation": 0, "texture": "blackglass_stack_bridge", "setpiece": "Stack Bridge"},
            {"id": "r_shortcut", "prefab": "setpiece_shard_barricade", "x": 1070, "y": 680, "rotation": 0, "texture": "blackglass_shard_barricade", "setpiece": "Shard Barricade"},
            {"id": "r_split_se", "prefab": "maze_split_wall_compact", "x": 1450, "y": 780, "rotation": 0, "texture": "blackglass_labyrinth_panels"},
        ],
        "markers": {
            "entry": (120, 900), "extraction": (120, 900), "reroute_extraction": (98, 254),
            "artifact": (1448, 604), "memory_well": (1098, 904), "boss": (1798, 804),
            "enemy_0": (298, 554), "enemy_1": (498, 554), "enemy_2": (898, 554), "enemy_3": (1098, 554), "enemy_4": (1298, 504),
            "comp_0": (1798, 254), "comp_1": (1798, 604),
            "spawn_gate_0": (1798, 254), "spawn_gate_1": (1798, 604),
        },
    },
    "rescue": {
        "name": "PILGRIM OSSUARY / SPLIT MERCY MAZE",
        "access_breaks": ["west_entry", "mercy_crossing", "carriage_flank", "east_service_gap"],
        "objects": [
            {"id": "s_carriage_nw", "prefab": "relic_carriage", "x": 220, "y": 270, "rotation": 0, "texture": "ossuary_carriage"},
            {"id": "s_hook_north", "prefab": "setpiece_service_hook", "x": 640, "y": 250, "rotation": 0, "texture": "ossuary_service_hook", "setpiece": "Service Hook"},
            {"id": "s_gate_north", "prefab": "setpiece_signal_barricade", "x": 1000, "y": 250, "rotation": 0, "texture": "ossuary_signal_barricade", "setpiece": "Signal Barricade"},
            {"id": "s_hook_ne", "prefab": "maze_hook_right_compact", "x": 1420, "y": 250, "rotation": 0, "texture": "ossuary_labyrinth_bulkheads"},
            {"id": "s_carriage_sw", "prefab": "relic_carriage", "x": 280, "y": 820, "rotation": 0, "texture": "ossuary_carriage"},
            {"id": "s_u_south", "prefab": "setpiece_shrine_lane", "x": 700, "y": 720, "rotation": 0, "texture": "ossuary_shrine_lane", "setpiece": "Shrine Lane"},
            {"id": "s_shortcut", "prefab": "setpiece_split_bulkhead", "x": 1120, "y": 700, "rotation": 0, "texture": "ossuary_split_bulkhead", "setpiece": "Split Bulkhead"},
            {"id": "s_split_se", "prefab": "maze_split_wall_compact", "x": 1500, "y": 700, "rotation": 0, "texture": "ossuary_labyrinth_bulkheads"},
        ],
        "markers": {
            "entry": (120, 900), "extraction": (120, 900), "boss": (1798, 604),
            "civilian_0": (648, 554), "civilian_1": (1048, 604), "civilian_2": (1348, 604),
            "enemy_0": (248, 554), "enemy_1": (448, 554), "enemy_2": (548, 704), "enemy_3": (1198, 554), "enemy_4": (1798, 254),
            "comp_0": (98, 254), "comp_1": (1798, 404),
            "spawn_gate_0": (98, 254), "spawn_gate_1": (1798, 404),
        },
    },
}


# Pass 20 approved layout pool. The canonical Pass 19 layouts remain in
# LAYOUTS for historical verification. Two additional authored transforms per
# contract change lane rhythm and cover facing while preserving the same
# markers, setpiece identities, spacing requirements, and collision grammar.
PASS20_LAYOUT_MUTATIONS = {
    "purge": (
        {
            "name": "SAINT VOLTAGE / CROSSFLOW MAZE",
            "objects": {
                "p_hook_nw": (180, 270, 180), "p_t_north": (590, 270, 0),
                "p_gate_north": (990, 270, 180), "p_hook_ne": (1410, 288, 0),
                "p_u_south": (220, 650, 180), "p_zig_south": (650, 680, 180),
                "p_shortcut": (1070, 700, 0), "p_reliquary_pillar": (1710, 778, 0),
            },
        },
        {
            "name": "SAINT VOLTAGE / RELAY MAZE",
            "objects": {
                "p_hook_nw": (240, 230, 0), "p_t_north": (650, 230, 180),
                "p_gate_north": (1050, 230, 180), "p_hook_ne": (1470, 230, 180),
                "p_u_south": (260, 650, 180), "p_zig_south": (690, 680, 0),
                "p_shortcut": (1110, 700, 180), "p_reliquary_pillar": (1750, 760, 180),
            },
        },
    ),
    "recovery": (
        {
            "name": "BLACKGLASS / CROSSFLOW MAZE",
            "objects": {
                "r_hook_nw": (240, 250, 180), "r_t_north": (650, 250, 180),
                "r_gate_north": (1050, 268, 180), "r_index_stack": (1470, 280, 180),
                "r_u_south": (200, 670, 180), "r_zig_south": (630, 670, 180),
                "r_shortcut": (1050, 718, 0), "r_split_se": (1430, 800, 180),
            },
        },
        {
            "name": "BLACKGLASS / RELAY MAZE",
            "objects": {
                "r_hook_nw": (220, 270, 180), "r_t_north": (630, 270, 0),
                "r_gate_north": (1030, 270, 0), "r_index_stack": (1450, 300, 0),
                "r_u_south": (220, 668, 0), "r_zig_south": (650, 650, 0),
                "r_shortcut": (1070, 698, 180), "r_split_se": (1450, 798, 180),
            },
        },
    ),
    "rescue": (
        {
            "name": "PILGRIM OSSUARY / CROSSFLOW MAZE",
            "objects": {
                "s_carriage_nw": (220, 290, 180), "s_hook_north": (640, 270, 180),
                "s_gate_north": (1000, 270, 0), "s_hook_ne": (1420, 270, 180),
                "s_carriage_sw": (300, 840, 180), "s_u_south": (720, 740, 180),
                "s_shortcut": (1140, 720, 180), "s_split_se": (1520, 720, 0),
            },
        },
        {
            "name": "PILGRIM OSSUARY / RELAY MAZE",
            "objects": {
                "s_carriage_nw": (220, 272, 0), "s_hook_north": (640, 270, 180),
                "s_gate_north": (1000, 288, 180), "s_hook_ne": (1420, 270, 180),
                "s_carriage_sw": (280, 850, 180), "s_u_south": (700, 732, 0),
                "s_shortcut": (1120, 712, 0), "s_split_se": (1500, 730, 0),
            },
        },
    ),
}


def _make_layout_variant(base: dict, mutation: dict) -> dict:
    changed = mutation["objects"]
    objects = []
    for record in base["objects"]:
        item = dict(record)
        if item["id"] in changed:
            x, y, rotation = changed[item["id"]]
            item.update(x=x, y=y, rotation=rotation)
        objects.append(item)
    return {
        **base,
        "name": mutation["name"],
        "objects": objects,
        "markers": dict(base["markers"]),
        "access_breaks": list(base.get("access_breaks", [])),
    }


LAYOUT_POOLS = {
    key: (LAYOUTS[key],) + tuple(_make_layout_variant(LAYOUTS[key], mutation) for mutation in PASS20_LAYOUT_MUTATIONS[key])
    for key in LAYOUTS
}


def layout_variant_count(quest_key: str) -> int:
    return len(LAYOUT_POOLS[quest_key])


def select_layout(quest_key: str, layout_seed: int = 0) -> dict:
    pool = LAYOUT_POOLS[quest_key]
    return pool[int(layout_seed) % len(pool)]


def rotate_parts(parts: Iterable[tuple[int, int, int, int]], size: tuple[int, int], rotation: int):
    rotation %= 360
    if rotation not in (0, 90, 180, 270):
        raise ValueError(f"rotation must be 0/90/180/270, got {rotation}")
    w, h = size
    out = []
    for x, y, rw, rh in parts:
        if rotation == 0:
            out.append((x, y, rw, rh))
        elif rotation == 90:
            out.append((h - (y + rh), x, rh, rw))
        elif rotation == 180:
            out.append((w - (x + rw), h - (y + rh), rw, rh))
        else:
            out.append((y, w - (x + rw), rh, rw))
    return out


def rotated_size(size: tuple[int, int], rotation: int) -> tuple[int, int]:
    return size if rotation % 180 == 0 else (size[1], size[0])


def expand_object(record: dict) -> dict:
    prefab = PREFABS[record["prefab"]]
    rotation = int(record.get("rotation", 0)) % 360
    parts = rotate_parts(prefab.get("parts", []), prefab["size"], rotation)
    x, y = int(record["x"]), int(record["y"])
    world_parts = [(x + px, y + py, pw, ph) for px, py, pw, ph in parts]
    rw, rh = rotated_size(prefab["size"], rotation)
    destructible = bool(record.get("destructible", prefab.get("destructible", False)))
    max_hp = float(record.get("hp", prefab.get("hp", 0.0 if not destructible else 80.0)))
    return {
        **record,
        "category": prefab["category"], "bounds": (x, y, rw, rh), "parts": world_parts,
        "movement": bool(prefab.get("movement", True)), "vision": bool(prefab.get("vision", True)),
        "projectiles": bool(prefab.get("projectiles", True)), "destructible": destructible, "max_hp": max_hp,
        "maze_piece": bool(record.get("maze_piece", prefab.get("maze_piece", False))),
        "access_breaks": int(record.get("access_breaks", prefab.get("access_breaks", 0))),
    }
