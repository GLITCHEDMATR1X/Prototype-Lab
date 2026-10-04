"""Gameplay-pressure authority for Vector Wars.

Combat population is deliberately independent from rendering/performance presets.
Performance profiles may reduce draw/update budgets, but they must not silently
change campaign difficulty by spawning fewer or more combatants.

The current Standard values preserve the pre-Pass16 default ``smooth`` profile,
so normal players do not receive a balance change in this pass.
"""

from __future__ import annotations

STANDARD_COMBAT_COUNTS = {
    "traffic": 30,
    "fighters": 10,
    "ufos": 3,
    "warships": 5,
    "helicopters": 2,
}


def standard_count(key: str) -> int:
    name = str(key).strip().lower()
    if name not in STANDARD_COMBAT_COUNTS:
        raise KeyError(name)
    return int(STANDARD_COMBAT_COUNTS[name])


def validate_campaign_capacity(
    *,
    ground_street_goal: int,
    air_fighter_goal: int,
    air_ufo_goal: int,
    ocean_warship_goal: int,
    ocean_helicopter_goal: int,
) -> list[str]:
    """Return human-readable issues if a phase cannot field its objective set.

    Ground traffic respawns continuously, so at least one street target is enough
    mechanically; we still require a useful live population of eight so the first
    objective does not become a waiting exercise. Other fronts require enough live
    initial/limited population to support their current objective pacing.
    """
    issues: list[str] = []
    if standard_count("traffic") < min(8, int(ground_street_goal)):
        issues.append("ground traffic population is too low for the street-assault pacing target")
    if standard_count("fighters") < int(air_fighter_goal):
        issues.append("fighter population is lower than the air fighter objective")
    if standard_count("ufos") < int(air_ufo_goal):
        issues.append("UFO population is lower than the air UFO objective")
    if standard_count("warships") < int(ocean_warship_goal):
        issues.append("warship population is lower than the ocean warship objective")
    if standard_count("helicopters") < int(ocean_helicopter_goal):
        issues.append("helicopter population limit is lower than the ocean helicopter objective")
    return issues
