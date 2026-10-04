"""Pass 15 actor presentation authority.

These values describe rendered footprint targets only.  They deliberately do
not alter the simulation's collision radii or combat statistics.  The largest
visual footprint remains below the Pass 14 minimum 120 px obstacle gap so
actors still read cleanly inside validated lanes.
"""

HERO_VISUAL_RADIUS = {
    "nyx": 38,
    "circuit": 46,
    "vesper": 38,
    "morrow": 41,
}

ENEMY_VISUAL_RADIUS = {
    "revenant": 30,
    "construct": 32,
    "cantor": 34,
}

BOSS_VISUAL_RADIUS = {
    "ash_saint": 48,
    "mirror_abbot": 49,
    "last_conductor": 47,
}

CIVILIAN_VISUAL_RADIUS = 24
PASS14_MIN_WORLD_GAP = 120

# The visual contract is intentionally conservative: two largest sovereign
# visual radii can fit inside the minimum world gap without overlap.
MAX_ACTOR_VISUAL_DIAMETER = max(BOSS_VISUAL_RADIUS.values()) * 2
ACTOR_CLEARANCE_MARGIN = PASS14_MIN_WORLD_GAP - MAX_ACTOR_VISUAL_DIAMETER

CIVILIAN_STYLE = {
    0: {
        "name": "ARCHIVE PILGRIM",
        "coat": (48, 70, 88),
        "cloth": (204, 231, 244),
        "accent": (92, 226, 255),
        "prop": "archive_case",
        "headgear": "hood",
    },
    1: {
        "name": "CHOIR DEFECTOR",
        "coat": (48, 31, 39),
        "cloth": (124, 91, 74),
        "accent": (255, 184, 76),
        "prop": "broken_insignia",
        "headgear": "cowl",
    },
    2: {
        "name": "RELIC MEDIC",
        "coat": (104, 116, 113),
        "cloth": (214, 225, 218),
        "accent": (106, 255, 176),
        "prop": "med_satchel",
        "headgear": "cap",
    },
}

ACTOR_PRESENTATION_RULES = {
    "hero_body_fill": True,
    "enemy_body_fill": True,
    "civilian_role_costumes": True,
    "boss_unique_body_geometry": True,
    "combat_stats_changed": False,
    "collision_radii_changed": False,
}
