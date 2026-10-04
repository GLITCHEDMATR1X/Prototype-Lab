"""Pure-Python enemy evolution and encounter-doctrine rules for Vector Arena Pass 05.

No Panda3D imports live here.  Long-run enemy growth is intentionally bounded:
population remains capped by the horde director while later sets gain readable
variant evolutions, doctrine-specific pressure and three Guardian phases.
"""
from __future__ import annotations

EVOLUTION_MAX_LEVEL = 4
EVOLUTION_UNLOCK_SET = {
    "stalker": 2,
    "sentry": 3,
    "wraith": 3,
    "brute": 4,
    "guardian": 2,
}

EVOLUTION_NAMES = {
    "stalker": "RAPTOR FRAME",
    "sentry": "OVERWATCH FRAME",
    "wraith": "PHASE FRAME",
    "brute": "BULWARK FRAME",
    "guardian": "ASCENDANT FRAME",
}

DOCTRINE_NAMES = {
    "ASSAULT": "PINCER NET",
    "HORDE": "SWARM ACCELERATION",
    "BREACH": "CORE GUARD",
    "ELITE": "HEAVY SYNC",
    "OVERLOAD": "THERMAL PURSUIT",
    "BLACKOUT": "PHASE HUNT",
    "GUARDIAN": "ASCENDANT PROTOCOL",
}


def evolution_level_for(variant: str, set_number: int) -> int:
    variant = str(variant or "stalker")
    set_number = max(1, int(set_number))
    unlock = int(EVOLUTION_UNLOCK_SET.get(variant, 99))
    if set_number < unlock:
        return 0
    return min(EVOLUTION_MAX_LEVEL, 1 + (set_number - unlock) // 2)


def enemy_evolution_for(variant: str, set_number: int) -> dict:
    variant = str(variant or "stalker")
    level = evolution_level_for(variant, set_number)
    if level <= 0:
        return {
            "variant": variant,
            "level": 0,
            "id": "BASELINE",
            "name": "BASELINE FRAME",
            "hp_mult": 1.0,
            "speed_mult": 1.0,
            "damage_mult": 1.0,
            "attack_cooldown_mult": 1.0,
            "score_mult": 1.0,
            "lateral_mult": 1.0,
            "special_cooldown_mult": 1.0,
        }

    # Variant-specific growth stays deliberately modest.  Evolution is intended
    # to change the player's read and response, not create invisible stat walls.
    hp_step = {
        "stalker": 0.035,
        "sentry": 0.070,
        "wraith": 0.045,
        "brute": 0.085,
        "guardian": 0.080,
    }.get(variant, 0.04)
    speed_step = {
        "stalker": 0.040,
        "sentry": 0.015,
        "wraith": 0.045,
        "brute": 0.012,
        "guardian": 0.018,
    }.get(variant, 0.02)
    damage_step = {
        "stalker": 0.030,
        "sentry": 0.035,
        "wraith": 0.035,
        "brute": 0.040,
        "guardian": 0.040,
    }.get(variant, 0.03)

    return {
        "variant": variant,
        "level": level,
        "id": f"{variant.upper()}_EVO_{level}",
        "name": EVOLUTION_NAMES.get(variant, "EVOLVED FRAME"),
        "hp_mult": min(1.38, 1.0 + hp_step * level),
        "speed_mult": min(1.20, 1.0 + speed_step * level),
        "damage_mult": min(1.22, 1.0 + damage_step * level),
        "attack_cooldown_mult": max(0.78, 1.0 - 0.045 * level),
        "score_mult": 1.0 + 0.08 * level,
        "lateral_mult": min(1.24, 1.0 + (0.055 if variant in {"wraith", "stalker"} else 0.025) * level),
        "special_cooldown_mult": max(0.78, 1.0 - (0.045 if variant == "guardian" else 0.025) * level),
    }


def encounter_doctrine_for(kind: str, set_number: int) -> dict:
    kind = str(kind or "ASSAULT").upper()
    set_number = max(1, int(set_number))
    active = set_number >= 2
    # Doctrine pressure also remains bounded.  It changes what gets emphasized
    # in a wave without changing spawn caps or shortening authored telegraphs.
    return {
        "id": kind,
        "name": DOCTRINE_NAMES.get(kind, "VECTOR DISCIPLINE") if active else "BASELINE DISCIPLINE",
        "active": active,
        "stalker_speed_mult": 1.05 if active and kind in {"ASSAULT", "HORDE"} else 1.0,
        "wraith_lateral_mult": 1.08 if active and kind in {"BLACKOUT", "HORDE"} else 1.0,
        "sentry_hp_mult": 1.08 if active and kind in {"BREACH", "ELITE"} else 1.0,
        "brute_hp_mult": 1.08 if active and kind in {"BREACH", "ELITE", "GUARDIAN"} else 1.0,
        "guardian_special_mult": 0.92 if active and kind == "GUARDIAN" else 1.0,
        "score_mult": 1.05 if active else 1.0,
    }


def apply_enemy_progression(variant: str, set_number: int, kind: str) -> dict:
    evo = enemy_evolution_for(variant, set_number)
    doctrine = encounter_doctrine_for(kind, set_number)
    hp_mult = float(evo["hp_mult"])
    speed_mult = float(evo["speed_mult"])
    damage_mult = float(evo["damage_mult"])
    lateral_mult = float(evo["lateral_mult"])
    special_mult = float(evo["special_cooldown_mult"])
    if variant == "stalker":
        speed_mult *= float(doctrine["stalker_speed_mult"])
    elif variant == "wraith":
        lateral_mult *= float(doctrine["wraith_lateral_mult"])
    elif variant == "sentry":
        hp_mult *= float(doctrine["sentry_hp_mult"])
    elif variant == "brute":
        hp_mult *= float(doctrine["brute_hp_mult"])
    elif variant == "guardian":
        hp_mult *= float(doctrine["brute_hp_mult"])
        special_mult *= float(doctrine["guardian_special_mult"])
    return {
        **evo,
        "hp_mult": min(1.46, hp_mult),
        "speed_mult": min(1.24, speed_mult),
        "damage_mult": min(1.24, damage_mult),
        "lateral_mult": min(1.28, lateral_mult),
        "special_cooldown_mult": max(0.72, special_mult),
        "score_mult": float(evo["score_mult"]) * float(doctrine["score_mult"]),
        "doctrine": doctrine,
    }


def guardian_phase_for(hp: float, max_hp: float) -> int:
    ratio = max(0.0, min(1.0, float(hp) / max(0.001, float(max_hp))))
    if ratio > 0.66:
        return 1
    if ratio > 0.33:
        return 2
    return 3


def guardian_phase_profile(phase: int) -> dict:
    phase = max(1, min(3, int(phase)))
    if phase == 1:
        return {
            "phase": 1,
            "name": "SENTINEL",
            "telegraph_mult": 1.0,
            "special_cooldown_mult": 1.0,
            "rush_speed_mult": 1.0,
            "pulse_radius": 27.0,
            "damage_mult": 1.0,
        }
    if phase == 2:
        return {
            "phase": 2,
            "name": "OVERDRIVE",
            "telegraph_mult": 0.90,
            "special_cooldown_mult": 0.86,
            "rush_speed_mult": 1.10,
            "pulse_radius": 30.0,
            "damage_mult": 1.08,
        }
    return {
        "phase": 3,
        "name": "REDLINE",
        "telegraph_mult": 0.82,
        "special_cooldown_mult": 0.74,
        "rush_speed_mult": 1.18,
        "pulse_radius": 32.0,
        "damage_mult": 1.14,
    }
