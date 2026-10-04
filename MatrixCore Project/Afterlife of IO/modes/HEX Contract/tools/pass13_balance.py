"""Deterministic RC1 balance and strategy-dominance audit for HEX CONTRACT."""
from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.data import HEROES, QUESTS, EQUIPMENT_KITS, HERO_ORDERS, HERO_LINKS, equipment_fit, quest_fit

REPORTS = ROOT / "verification" / "reports"


def simulate(spec: tuple[str, str, str, str, str, int]) -> dict:
    from game.sim import Mission

    hero, quest, equipment, order, support, seed = spec
    mission = Mission(hero, quest, seed=seed, equipment_key=equipment, order_key=order, support_key=support)
    for _ in range(3400):
        mission.update(0.05)
        if mission.status != "ACTIVE":
            break
    if mission.status == "ACTIVE":
        mission.status = "FAILED"
        mission.result_reason = "RC1 deterministic observation window expired"
        mission._finalize_result()
    report = mission.report()
    return {
        "hero": hero,
        "quest": quest,
        "equipment": equipment,
        "order": order,
        "support": support,
        "status": report["status"],
        "reason": report["reason"],
        "time": report["time"],
        "hp_ratio": round(report["hero_hp"] / max(1.0, mission.hero.max_hp), 4),
        "strain_delta": report["strain_delta"],
        "credits": report["reward_credits"],
        "boss_defeated": report["boss_defeated"],
        "fit": report["quest_fit_percent"],
        "echo_damage_absorbed": report["behavior_counts"].get("echo_damage_absorbed", 0),
    }


def parallel_simulate(specs: list[tuple[str, str, str, str, str, int]]) -> list[dict]:
    workers = min(12, max(1, os.cpu_count() or 1), len(specs))
    rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(simulate, spec) for spec in specs]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda r: (list(QUESTS).index(r["quest"]), list(HEROES).index(r["hero"]), r["equipment"], r["order"], r["support"]))
    return rows


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)

    core_specs = [(hero, quest, "ampoule", "balanced", "none", 13013) for quest in QUESTS for hero in HEROES]
    core = parallel_simulate(core_specs)
    matrix = {f"{row['hero']}/{row['quest']}": row for row in core}

    # These outcomes define the intended autonomous role lattice.  Circuit is
    # intentionally broadly survivable, but it is neither the fastest purge
    # operative nor the lowest-strain recovery specialist.
    expected_success = {
        "nyx/purge", "nyx/recovery", "nyx/rescue",
        "circuit/purge", "circuit/recovery", "circuit/rescue",
        "vesper/recovery", "vesper/rescue",
        "morrow/recovery", "morrow/rescue",
    }
    actual_success = {key for key, row in matrix.items() if row["status"] == "SUCCESS"}
    role_lattice_pass = actual_success == expected_success

    prepared_specs = [
        ("morrow", "purge", "aegis", "balanced", "none", 13013),
        ("nyx", "rescue", "beacon", "protect", "circuit", 13013),
        ("vesper", "recovery", "surveyor", "objective", "circuit", 13013),
        ("circuit", "purge", "aegis", "eliminate", "vesper", 13013),
    ]
    prepared = parallel_simulate(prepared_specs)
    prepared_pass = all(row["status"] == "SUCCESS" for row in prepared)

    equipment_top_counts = {key: 0 for key in EQUIPMENT_KITS}
    equipment_rows = []
    for hero in HEROES:
        for quest in QUESTS:
            fits = {kit: equipment_fit(kit, hero, quest)["score"] for kit in EQUIPMENT_KITS}
            best = max(fits, key=fits.get)
            equipment_top_counts[best] += 1
            equipment_rows.append({"hero": hero, "quest": quest, "best": best, "scores": {k: round(v, 4) for k, v in fits.items()}})
    equipment_diversity_pass = sum(1 for count in equipment_top_counts.values() if count > 0) >= 3 and max(equipment_top_counts.values()) < len(HEROES) * len(QUESTS)

    hero_successes = {hero: sum(1 for row in core if row["hero"] == hero and row["status"] == "SUCCESS") for hero in HEROES}
    quest_successes = {quest: sum(1 for row in core if row["quest"] == quest and row["status"] == "SUCCESS") for quest in QUESTS}
    every_hero_viable = all(value >= 1 for value in hero_successes.values())
    every_quest_has_choices = all(value >= 2 for value in quest_successes.values())

    # Multi-objective dominance: no hero may be simultaneously fastest, safest,
    # and lowest-strain across all three contracts.
    leaders = {}
    for quest in QUESTS:
        successful = [row for row in core if row["quest"] == quest and row["status"] == "SUCCESS"]
        leaders[quest] = {
            "fastest": min(successful, key=lambda r: r["time"])["hero"],
            "safest": max(successful, key=lambda r: r["hp_ratio"])["hero"],
            "lowest_strain": min(successful, key=lambda r: r["strain_delta"])["hero"],
        }
    universal_leaders = [hero for hero in HEROES if all(hero in leaders[q].values() for q in QUESTS)]
    no_universal_dominance = not universal_leaders

    echo_rows = [row for row in core + prepared if row["hero"] == "morrow"]
    echo_logic_pass = any(row["echo_damage_absorbed"] > 0 for row in echo_rows)

    payload = {
        "pass": 13,
        "release": "Balance and Finalization RC1",
        "research_basis": "Simulation-based multi-objective balance audit; success alone is not treated as the only balance target.",
        "core_matrix": core,
        "expected_success_set": sorted(expected_success),
        "actual_success_set": sorted(actual_success),
        "role_lattice": "PASS" if role_lattice_pass else "FAIL",
        "prepared_recovery_cases": prepared,
        "prepared_recovery": "PASS" if prepared_pass else "FAIL",
        "hero_success_counts": hero_successes,
        "quest_success_counts": quest_successes,
        "every_hero_viable": every_hero_viable,
        "every_quest_has_multiple_choices": every_quest_has_choices,
        "multi_objective_leaders": leaders,
        "universal_leaders": universal_leaders,
        "no_universal_dominance": no_universal_dominance,
        "equipment_top_counts": equipment_top_counts,
        "equipment_fit_rows": equipment_rows,
        "equipment_diversity": "PASS" if equipment_diversity_pass else "FAIL",
        "order_doctrines": list(HERO_ORDERS),
        "link_doctrines": list(HERO_LINKS),
        "echo_pressure_is_real": echo_logic_pass,
    }
    checks = [role_lattice_pass, prepared_pass, equipment_diversity_pass, every_hero_viable, every_quest_has_choices, no_universal_dominance, echo_logic_pass]
    payload["final_result"] = "PASS" if all(checks) else "FAIL"
    out = REPORTS / "pass13_balance_audit.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({
        "final_result": payload["final_result"],
        "hero_success_counts": hero_successes,
        "quest_success_counts": quest_successes,
        "leaders": leaders,
        "equipment_top_counts": equipment_top_counts,
    }, indent=2))
    return 0 if payload["final_result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
