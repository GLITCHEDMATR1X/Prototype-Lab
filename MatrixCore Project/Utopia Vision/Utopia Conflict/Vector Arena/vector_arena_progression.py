"""Pure-Python between-set progression and arena-mutation rules for Pass 04.

This module intentionally has no Panda3D imports so upgrade/mutation balance and
long-run contracts can be checked in packaging environments.
"""
from __future__ import annotations

UPGRADE_IDS = ("VOLT_LATTICE", "REACTIVE_SHELL", "PHASE_RECOVERY")

UPGRADE_BASE = {
    "VOLT_LATTICE": {
        "title": "VOLT LATTICE",
        "category": "WEAPON MUTATION",
        "summary": "+10% weapon + breach damage / stack",
    },
    "REACTIVE_SHELL": {
        "title": "REACTIVE SHELL",
        "category": "SYSTEM MUTATION",
        "summary": "+10 armor cap + 5% enemy resist / stack",
    },
    "PHASE_RECOVERY": {
        "title": "PHASE RECOVERY",
        "category": "ARENA ABILITY",
        "summary": "-10% hazard damage + faster repulsor / stack",
    },
}

_MUTATIONS = (
    {
        "id": "STABLE_MATRIX",
        "name": "STABLE MATRIX",
        "summary": "baseline simulation geometry",
        "spawn_interval_mult": 1.0,
        "telegraph_mult": 1.0,
        "active_bonus": 0,
        "hazard_interval_mult": 1.0,
        "hazard_damage_mult": 1.0,
        "breach_hp_mult": 1.0,
    },
    {
        "id": "GATE_OVERCLOCK",
        "name": "GATE OVERCLOCK",
        "summary": "spawn gates cycle faster",
        "spawn_interval_mult": 0.94,
        "telegraph_mult": 0.95,
        "active_bonus": 0,
        "hazard_interval_mult": 1.0,
        "hazard_damage_mult": 1.0,
        "breach_hp_mult": 1.0,
    },
    {
        "id": "PHASE_FRACTURE",
        "name": "PHASE FRACTURE",
        "summary": "one additional simultaneous threat may remain active",
        "spawn_interval_mult": 0.98,
        "telegraph_mult": 1.0,
        "active_bonus": 1,
        "hazard_interval_mult": 0.96,
        "hazard_damage_mult": 1.0,
        "breach_hp_mult": 1.0,
    },
    {
        "id": "REDLINE_GRID",
        "name": "REDLINE GRID",
        "summary": "special-wave floor hazards cycle harder",
        "spawn_interval_mult": 1.0,
        "telegraph_mult": 1.0,
        "active_bonus": 0,
        "hazard_interval_mult": 0.90,
        "hazard_damage_mult": 1.06,
        "breach_hp_mult": 1.0,
    },
    {
        "id": "BREACH_RESONANCE",
        "name": "BREACH RESONANCE",
        "summary": "breach cores become more stable and harder to erase",
        "spawn_interval_mult": 0.98,
        "telegraph_mult": 1.0,
        "active_bonus": 0,
        "hazard_interval_mult": 1.0,
        "hazard_damage_mult": 1.0,
        "breach_hp_mult": 1.10,
    },
)


def upgrade_choices(stacks: dict[str, int] | None = None) -> list[dict]:
    stacks = stacks or {}
    result = []
    for index, upgrade_id in enumerate(UPGRADE_IDS, start=1):
        base = UPGRADE_BASE[upgrade_id]
        current = max(0, int(stacks.get(upgrade_id, 0)))
        result.append({
            "slot": index,
            "id": upgrade_id,
            "title": base["title"],
            "category": base["category"],
            "summary": base["summary"],
            "current_stack": current,
            "next_stack": current + 1,
        })
    return result


def upgrade_effects(stacks: dict[str, int] | None = None) -> dict:
    stacks = stacks or {}
    weapon = max(0, int(stacks.get("VOLT_LATTICE", 0)))
    shell = max(0, int(stacks.get("REACTIVE_SHELL", 0)))
    phase = max(0, int(stacks.get("PHASE_RECOVERY", 0)))
    return {
        "weapon_damage_mult": 1.0 + weapon * 0.10,
        "max_armor": 82.0 + shell * 10.0,
        "incoming_damage_mult": max(0.45, 1.0 - shell * 0.05),
        "hazard_damage_mult": max(0.35, 1.0 - phase * 0.10),
        "repulsor_cooldown_mult": max(0.62, 1.0 - phase * 0.04),
        "reconstruction_health": 4.0 + phase * 5.0,
        "reconstruction_armor": 7.0 + phase * 7.0,
    }


def arena_mutation_for_set(set_number: int) -> dict:
    """Return the deterministic mutation active during a 1-based wave set.

    Set 1 is deliberately stable. Later sets cycle through four mutation
    families. Every complete cycle slightly intensifies the same family without
    removing telegraphs or exceeding the global active-threat cap in runtime.
    """
    set_number = max(1, int(set_number))
    if set_number == 1:
        return dict(_MUTATIONS[0], intensity=0, set_number=1)
    family_index = 1 + ((set_number - 2) % 4)
    cycle = (set_number - 2) // 4
    item = dict(_MUTATIONS[family_index])
    item["intensity"] = cycle + 1
    item["set_number"] = set_number
    if cycle > 0:
        # Gentle bounded escalation. Telegraphs never fall below 78% of their
        # authored warning time and mutation scaling never bypasses runtime caps.
        item["spawn_interval_mult"] = max(0.84, float(item["spawn_interval_mult"]) - cycle * 0.015)
        item["telegraph_mult"] = max(0.78, float(item["telegraph_mult"]) - cycle * 0.01)
        item["active_bonus"] = min(2, int(item["active_bonus"]) + cycle // 2)
        item["hazard_interval_mult"] = max(0.78, float(item["hazard_interval_mult"]) - cycle * 0.02)
        item["hazard_damage_mult"] = min(1.28, float(item["hazard_damage_mult"]) + cycle * 0.025)
        item["breach_hp_mult"] = min(1.32, float(item["breach_hp_mult"]) + cycle * 0.03)
    return item


def apply_mutation_to_plan(plan: dict, set_number: int, max_active_cap: int = 22) -> dict:
    out = dict(plan)
    mutation = arena_mutation_for_set(set_number)
    out["spawn_interval"] = max(0.18, float(out.get("spawn_interval", 0.7)) * float(mutation["spawn_interval_mult"]))
    out["max_active"] = min(int(max_active_cap), int(out.get("max_active", 10)) + int(mutation["active_bonus"]))
    script = []
    for directive in out.get("spawn_script", []):
        entry = dict(directive)
        entry["telegraph"] = max(0.36, float(entry.get("telegraph", 0.66)) * float(mutation["telegraph_mult"]))
        script.append(entry)
    out["spawn_script"] = script
    hazard = dict(out.get("hazard", {}))
    if hazard.get("enabled"):
        hazard["interval"] = max(2.2, float(hazard.get("interval", 4.0)) * float(mutation["hazard_interval_mult"]))
        # Endless runs must remain survivable: special hazards can become more
        # frequent, but a single floor discharge never scales into a one-shot.
        hazard["damage"] = min(38.0, float(hazard.get("damage", 0.0)) * float(mutation["hazard_damage_mult"]))
    out["hazard"] = hazard
    out["arena_mutation"] = mutation
    return out
