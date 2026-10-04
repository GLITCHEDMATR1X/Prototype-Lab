"""Pure-Python wave/tactics director rules for Vector Arena Pass 04.

No Panda3D imports live here.  The schedule, spawn-gate choreography, tactical
roles and wave-hazard contract can therefore be tested deterministically in
packaging/build environments before a live Panda3D runtime is available.
"""
from __future__ import annotations

WAVE_SET_SIZE = 5
MAX_ACTIVE_THREATS = 22
WAVE_KINDS = ("ASSAULT", "HORDE", "BREACH", "ELITE", "OVERLOAD", "BLACKOUT", "GUARDIAN")

# Seven authored perimeter gates.  Names are descriptive only; the native mode
# owns the actual world coordinates.
GATE_LABELS = (
    "FRONT LEFT", "FRONT", "FRONT RIGHT", "LEFT", "RIGHT", "REAR LEFT", "REAR RIGHT"
)

TACTIC_ROLES = (
    "pressure", "flank_left", "flank_right", "anchor", "rear_left", "rear_right", "boss_support"
)

# Pass 07 removed the obsolete generic cover-layout table. Arena geometry now
# comes exclusively from vector_arena_arenas.architecture_pieces_for_profile().

def wave_kind_for(wave: int) -> str:
    wave = max(1, int(wave))
    if wave % WAVE_SET_SIZE == 0:
        return "GUARDIAN"
    pattern = ("ASSAULT", "HORDE", "BREACH", "ELITE", "ASSAULT", "OVERLOAD", "HORDE", "BLACKOUT", "BREACH")
    return pattern[(wave - 1) % len(pattern)]


def _role_for(kind: str, variant: str, index: int, set_index: int) -> str:
    """Deterministic tactical role.  Roles alter spawn gate and steering.

    The early game avoids cheap rear spawns.  Rear pressure is introduced from
    set two onward and remains explicitly telegraphed at the gate before the
    enemy becomes active.
    """
    if variant == "guardian":
        return "pressure"
    if variant == "sentry":
        return "anchor"
    if kind == "GUARDIAN":
        seq = ("boss_support", "flank_left", "flank_right", "anchor")
        return seq[index % len(seq)]
    if kind == "ELITE":
        seq = ("anchor", "flank_left", "flank_right", "pressure")
        return seq[index % len(seq)]
    if kind == "HORDE":
        seq = ("pressure", "flank_left", "pressure", "flank_right", "pressure")
    elif kind == "BLACKOUT":
        seq = ("flank_left", "flank_right", "pressure", "flank_left", "flank_right")
    elif kind == "OVERLOAD":
        seq = ("flank_left", "flank_right", "anchor", "pressure")
    elif kind == "BREACH":
        seq = ("pressure", "anchor", "flank_left", "flank_right")
    else:
        seq = ("pressure", "flank_left", "flank_right", "anchor")
    role = seq[index % len(seq)]
    # Rear attacks appear only after the player has learned the gate language.
    if set_index >= 1 and variant in {"stalker", "wraith"}:
        if index % 11 == 7:
            role = "rear_left"
        elif index % 11 == 9:
            role = "rear_right"
    return role


def _gate_for(role: str, index: int, set_index: int) -> int:
    choices = {
        "pressure": (1, 0, 2),
        "flank_left": (3, 0),
        "flank_right": (4, 2),
        "anchor": (0, 2, 1),
        "rear_left": (5,),
        "rear_right": (6,),
        "boss_support": (0, 2, 3, 4),
    }.get(role, (1,))
    return int(choices[(index + set_index) % len(choices)])


def _spawn_script(queue: list[str], wave: int, kind: str, set_index: int) -> list[dict]:
    script: list[dict] = []
    for index, variant in enumerate(queue):
        role = _role_for(kind, variant, index, set_index)
        gate = 1 if variant == "guardian" else _gate_for(role, index, set_index)
        # Heavy units receive a longer warning.  Horde fodder is faster but
        # never instant; the gate always advertises an imminent spawn.
        if variant == "guardian":
            telegraph = 1.25
        elif variant == "brute":
            telegraph = 0.92
        elif kind == "HORDE":
            telegraph = 0.48
        else:
            telegraph = 0.66
        script.append({
            "variant": variant,
            "gate": gate,
            "gate_label": GATE_LABELS[gate],
            "role": role,
            "formation": index // 3,
            "formation_slot": index % 3,
            "telegraph": telegraph,
        })
    return script


def _hazard_profile(kind: str, set_index: int) -> dict:
    if kind == "OVERLOAD":
        return {
            "kind": "ARC_SURGE", "enabled": True,
            "interval": max(2.7, 3.8 - set_index * 0.12),
            "telegraph": 1.05, "active": 0.72,
            "radius": 10.5, "damage": 11.0 + set_index * 1.4, "heat": 24.0,
        }
    if kind == "BLACKOUT":
        return {
            "kind": "SCAN_PULSE", "enabled": True,
            "interval": max(3.7, 5.1 - set_index * 0.12),
            "telegraph": 1.25, "active": 0.62,
            "radius": 13.0, "damage": 8.0 + set_index * 1.0, "heat": 8.0,
        }
    if kind == "GUARDIAN":
        return {
            "kind": "REDLINE_FIELD", "enabled": True,
            "interval": max(3.3, 4.9 - set_index * 0.10),
            "telegraph": 1.10, "active": 0.68,
            "radius": 11.5, "damage": 14.0 + set_index * 1.6, "heat": 12.0,
        }
    return {
        "kind": "NONE", "enabled": False,
        "interval": 999.0, "telegraph": 1.0, "active": 0.5,
        "radius": 0.0, "damage": 0.0, "heat": 0.0,
    }


def build_wave_plan(wave: int) -> dict:
    """Return deterministic composition, gate choreography and hazards."""
    wave = max(1, int(wave))
    set_index = (wave - 1) // WAVE_SET_SIZE
    # Population growth is capped so endless play becomes harder without turning
    # late waves into multi-minute cleanup marathons. Durability, mutations,
    # timing and tactics continue scaling after population reaches its ceiling.
    growth = min(set_index, 10)
    kind = wave_kind_for(wave)
    counts = {"stalker": 0, "wraith": 0, "sentry": 0, "brute": 0, "guardian": 0}
    max_active = min(MAX_ACTIVE_THREATS, 10 + set_index * 2)
    spawn_interval = max(0.28, 0.72 - set_index * 0.04)
    required_breaches = 0
    heat_gain = 1.0
    heat_cool = 1.0
    if kind == "ASSAULT":
        counts.update(stalker=6 + growth * 2, wraith=2 + growth, sentry=2 + growth, brute=max(0, growth))
    elif kind == "HORDE":
        counts.update(stalker=14 + growth * 4, wraith=4 + growth * 2, sentry=2 + growth)
        max_active = min(MAX_ACTIVE_THREATS, 18 + set_index)
        spawn_interval = max(0.22, 0.34 - set_index * 0.015)
    elif kind == "BREACH":
        counts.update(stalker=8 + growth * 2, wraith=3 + growth, sentry=3 + growth, brute=1 + growth // 2)
        required_breaches = min(3, 1 + set_index // 2)
    elif kind == "ELITE":
        counts.update(stalker=2 + growth, wraith=3 + growth, sentry=4 + growth, brute=3 + growth)
        max_active = min(MAX_ACTIVE_THREATS, 11 + set_index)
        spawn_interval = 0.82
    elif kind == "OVERLOAD":
        counts.update(stalker=7 + growth * 2, wraith=4 + growth, sentry=3 + growth, brute=2 + growth // 2)
        heat_gain = 1.35
        heat_cool = 0.68
    elif kind == "BLACKOUT":
        counts.update(stalker=7 + growth * 2, wraith=7 + growth * 2, sentry=3 + growth, brute=1 + growth // 2)
        spawn_interval = 0.52
    elif kind == "GUARDIAN":
        counts.update(stalker=5 + growth * 2, wraith=2 + growth, sentry=2 + growth, brute=2 + growth, guardian=min(3, 1 + growth // 2))
        max_active = min(MAX_ACTIVE_THREATS, 10 + set_index)
        spawn_interval = 0.76

    queue: list[str] = []
    order = ("stalker", "wraith", "sentry", "brute", "guardian")
    remaining = dict(counts)
    while any(remaining.values()):
        for variant in order:
            if remaining[variant] > 0:
                queue.append(variant)
                remaining[variant] -= 1
    spawn_script = _spawn_script(queue, wave, kind, set_index)
    role_counts = {role: 0 for role in TACTIC_ROLES}
    gate_counts = {str(i): 0 for i in range(len(GATE_LABELS))}
    for directive in spawn_script:
        role_counts[directive["role"]] += 1
        gate_counts[str(directive["gate"])] += 1
    return {
        "wave": wave,
        "set_index": set_index,
        "kind": kind,
        "queue": queue,
        "spawn_script": spawn_script,
        "role_counts": role_counts,
        "gate_counts": gate_counts,
        "counts": counts,
        "max_active": int(max_active),
        "spawn_interval": float(spawn_interval),
        "required_breaches": int(required_breaches),
        "heat_gain": float(heat_gain),
        "heat_cool": float(heat_cool),
        "hazard": _hazard_profile(kind, set_index),
    }
