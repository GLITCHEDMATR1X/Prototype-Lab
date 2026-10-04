"""Pure Pass 51 causal-progression rules with no pygame dependency."""
from __future__ import annotations

from typing import Any

FUTURE_CLUE_ID = "first_witness_absence"
CAUSAL_RESONANCE_ABILITY = "causal_resonance"
VEIL_WARD_ABILITY = "veil_ward"
LANTERN_PROJECTION_ABILITY = "lantern_projection"
REMOTE_RESONANCE_ABILITY = "remote_resonance"
ENTROPY_ARC_ABILITY = "entropy_arc"
PROJECTION_LANCE_ABILITY = "projection_lance"
ENTROPY_ARC_UNLOCK_WINS = 3
ENTROPY_ARC_MASTERY_WINS = 5
REMOTE_RESONANCE_UNLOCK_WINS = 2
REMOTE_RESONANCE_DEEP_WINS = 4
LANTERN_PROJECTION_BASE_SECONDS = 1.0
LANTERN_PROJECTION_MAX_SECONDS = 5.0
LANTERN_PROJECTION_MAX_LEVEL = 4
PROJECTION_LANCE_UPGRADE_WINS = 6
PROJECTION_LANCE_MASTERY_WINS = 8


def causal_resonance_band(distance: float, near_distance: float = 340.0,
                          mid_distance: float = 820.0) -> str:
    """Classify distance without returning coordinates or a direction marker."""
    try:
        value = max(0.0, float(distance))
    except (TypeError, ValueError, OverflowError):
        value = float("inf")
    near = max(0.0, float(near_distance))
    middle = max(near, float(mid_distance))
    if value <= near:
        return "near"
    if value <= middle:
        return "middle"
    return "faint"


def normalize_progression_state(raw: Any, shrine_activated: bool) -> tuple[bool, bool]:
    """Return clue/ability flags and migrate a logically completed older save."""
    progression = raw if isinstance(raw, dict) else {}
    clues = progression.get("discovered_clues")
    abilities = progression.get("learned_abilities")
    clue_ids = {str(item) for item in clues} if isinstance(clues, list) else set()
    ability_ids = {str(item) for item in abilities} if isinstance(abilities, list) else set()
    clue_discovered = FUTURE_CLUE_ID in clue_ids
    resonance_learned = CAUSAL_RESONANCE_ABILITY in ability_ids
    if shrine_activated:
        clue_discovered = True
        resonance_learned = True
    return clue_discovered, resonance_learned


def learned_ability_ids(raw: Any, shrine_activated: bool, rooted_crown_shrine_activated: bool = False, first_witness_defeated: bool = False, veil_warden_shrine_activated: bool = False) -> set[str]:
    """Normalize the extensible learned-ability list with legacy backfills."""
    progression = raw if isinstance(raw, dict) else {}
    abilities = progression.get("learned_abilities")
    result = {str(item) for item in abilities} if isinstance(abilities, list) else set()
    if shrine_activated:
        result.add(CAUSAL_RESONANCE_ABILITY)
    if rooted_crown_shrine_activated:
        result.add(VEIL_WARD_ABILITY)
    if first_witness_defeated:
        result.add(LANTERN_PROJECTION_ABILITY)
    if veil_warden_shrine_activated:
        result.add(PROJECTION_LANCE_ABILITY)
    return result


def lantern_projection_duration(upgrade_level: int) -> float:
    """Return the bounded exploration-only projection duration."""
    try:
        level = int(upgrade_level)
    except (TypeError, ValueError, OverflowError):
        level = 0
    level = max(0, min(LANTERN_PROJECTION_MAX_LEVEL, level))
    return min(LANTERN_PROJECTION_MAX_SECONDS, LANTERN_PROJECTION_BASE_SECONDS + float(level))


def remote_resonance_level(total_echo_wins: int) -> int:
    """Return 0 locked, 1 standard remote scan, 2 deep remote scan."""
    try:
        wins = max(0, int(total_echo_wins))
    except (TypeError, ValueError, OverflowError):
        wins = 0
    if wins >= REMOTE_RESONANCE_DEEP_WINS:
        return 2
    if wins >= REMOTE_RESONANCE_UNLOCK_WINS:
        return 1
    return 0


def remote_resonance_range_scale(total_echo_wins: int) -> float:
    """Bounded scouting range upgrade earned through Echo Challenges."""
    return 1.35 if remote_resonance_level(total_echo_wins) >= 2 else 1.0



def projection_lance_level(total_echo_wins: int, veil_warden_shrine_activated: bool) -> int:
    """Return 0 locked, 1 learned, 2 upgraded, 3 mastered.

    The Veil Warden Shrine unlocks the weapon itself; optional Echo Challenges
    then strengthen it without making those rematches mandatory for story play.
    """
    if not bool(veil_warden_shrine_activated):
        return 0
    try:
        wins = max(0, int(total_echo_wins))
    except (TypeError, ValueError, OverflowError):
        wins = 0
    if wins >= PROJECTION_LANCE_MASTERY_WINS:
        return 3
    if wins >= PROJECTION_LANCE_UPGRADE_WINS:
        return 2
    return 1


def projection_lance_stats(total_echo_wins: int, veil_warden_shrine_activated: bool) -> tuple[int, float]:
    """Return drone damage and bounded fire cooldown for Projection Lance."""
    level = projection_lance_level(total_echo_wins, veil_warden_shrine_activated)
    if level <= 0:
        return 0, 99.0
    if level >= 3:
        return 2, 0.42
    if level >= 2:
        return 1, 0.48
    return 1, 0.68


def entropy_arc_level(total_echo_wins: int) -> int:
    """Return 0 locked, 1 learned, 2 mastered through Shrine Echo victories."""
    try:
        wins = max(0, int(total_echo_wins))
    except (TypeError, ValueError, OverflowError):
        wins = 0
    if wins >= ENTROPY_ARC_MASTERY_WINS:
        return 2
    if wins >= ENTROPY_ARC_UNLOCK_WINS:
        return 1
    return 0


def entropy_arc_damage(total_echo_wins: int, focus: int = 0) -> tuple[int, int]:
    """Return damage and Focus consumed by the battle-only Entropy Arc.

    Learned form deals two Presence. Mastered form can consume one Focus to
    strengthen the arc to three Presence, creating a tactical link with the
    existing Focus command instead of replacing the readable boss counters.
    """
    level = entropy_arc_level(total_echo_wins)
    if level <= 0:
        return 0, 0
    try:
        held_focus = max(0, int(focus))
    except (TypeError, ValueError, OverflowError):
        held_focus = 0
    if level >= 2 and held_focus > 0:
        return 3, 1
    return 2, 0


def temporal_departure_state(x: float, y: float, walk_layer: int, facing: int) -> dict[str, float | int]:
    """Capture the exact place an era was left through its temporal terminal."""
    return {
        "x": float(x),
        "y": float(y),
        "walk_layer": int(walk_layer),
        "facing": -1 if int(facing) < 0 else 1,
    }


def temporal_return_candidate(raw: Any, world_key: str) -> dict[str, Any] | None:
    """Return a saved terminal-departure snapshot for one era without inventing one."""
    if not isinstance(raw, dict):
        return None
    candidate = raw.get(str(world_key))
    return dict(candidate) if isinstance(candidate, dict) else None
