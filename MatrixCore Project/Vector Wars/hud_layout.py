"""Pure HUD layout/copy authority for Vector Wars.

Keeps gameplay-critical text in stable, non-overlapping 1920x1080 safe zones.
No pygame dependency so layout contracts can run in the regression suite.
"""

INTERNAL_SIZE = (1920, 1080)

MISSION_PANEL_Y = 10
MISSION_PANEL_H = 62
TEMP_NOTICE_Y = 82
WEAPON_NOTICE_Y = 114
DIAGNOSTIC_Y = 150
FOOTER_Y = 1052


def mission_lines(*, campaign_complete, ocean_mode, ground_assault, redeploy_required,
                  ground_operation, air_operation, ocean_operation):
    """Return a short uppercase label plus a sentence-case mission line."""
    if campaign_complete:
        return "CAMPAIGN COMPLETE", "Ground, Air, and Ocean secured - Enter to replay"

    if ocean_mode:
        if ocean_operation.complete:
            return "SEA CONTROL ESTABLISHED", "Three-front operation complete"
        if ocean_operation.warship_kills < ocean_operation.WARSHIP_GOAL:
            return (
                "OCEAN // SEA CONTROL",
                f"Sink hostile warships  {ocean_operation.warship_kills}/{ocean_operation.WARSHIP_GOAL}",
            )
        return (
            "OCEAN // MARITIME AIR DEFENSE",
            f"Defeat hostile helicopters  {ocean_operation.helicopter_kills}/{ocean_operation.HELICOPTER_GOAL}",
        )

    if ground_assault:
        if redeploy_required:
            return "GROUND // UNIT LOST", "Press Enter to redeploy - operation progress preserved"
        if ground_operation.complete:
            return "GROUND SECURED", "Air phase active"
        if ground_operation.street_destroyed < ground_operation.STREET_GOAL:
            return (
                "GROUND // STREET ASSAULT",
                f"Break hostile street units  {ground_operation.street_destroyed}/{ground_operation.STREET_GOAL}",
            )
        return (
            "GROUND // GIANT HUNT",
            f"Destroy a Giant  {ground_operation.giants_destroyed}/{ground_operation.GIANT_GOAL}",
        )

    if air_operation.complete:
        return "AIR SECURED", "Maritime phase active"
    if air_operation.fighter_kills < air_operation.FIGHTER_GOAL:
        return (
            "AIR // AIR CONTROL",
            f"Defeat hostile fighters  {air_operation.fighter_kills}/{air_operation.FIGHTER_GOAL}",
        )
    return (
        "AIR // UFO INTERCEPT",
        f"Intercept UFO contacts  {air_operation.ufo_kills}/{air_operation.UFO_GOAL}",
    )


def vertical_zones():
    """Named top-level HUD bands for contract tests."""
    return {
        "mission": (MISSION_PANEL_Y, MISSION_PANEL_Y + MISSION_PANEL_H),
        "temp_notice": (TEMP_NOTICE_Y, TEMP_NOTICE_Y + 26),
        "weapon_notice": (WEAPON_NOTICE_Y, WEAPON_NOTICE_Y + 32),
        "diagnostics": (DIAGNOSTIC_Y, DIAGNOSTIC_Y + 96),
        "footer": (FOOTER_Y, 1080),
    }


def zones_do_not_overlap():
    zones = list(vertical_zones().items())
    for i, (_, a) in enumerate(zones):
        for _, b in zones[i + 1:]:
            if max(a[0], b[0]) < min(a[1], b[1]):
                return False
    return True
