"""Dependency-free expedition identity rules for Entropy Pass 33.

Pass 33 does not add another gameplay system.  It uses existing world classes,
hazards, ruins and Data Fragment progression to make successive abandoned-system
runs easier to distinguish.  This module stays pygame-free so its contracts can
be regression-tested in minimal build environments.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class WorldArchiveProfile:
    style: str
    world_name: str
    record_name: str
    landmark_name: str


WORLD_ARCHIVE_PROFILES = {
    "desert": WorldArchiveProfile("desert", "SEREKH DUNES", "DUST RECORD", "SUN RING"),
    "ice": WorldArchiveProfile("ice", "NIVALIS REACH", "CRYO RECORD", "CRYO NEEDLES"),
    "jungle": WorldArchiveProfile("jungle", "VIRIDIAN CROWN", "CANOPY RECORD", "ROOT CATHEDRAL"),
    "volcanic": WorldArchiveProfile("volcanic", "CINDER ATLAS", "THERMAL RECORD", "CALDERA CROWN"),
    "crystal": WorldArchiveProfile("crystal", "AUREL GLASS", "REFRACTION RECORD", "PRISM CHOIR"),
    "oceanic": WorldArchiveProfile("oceanic", "PELAGOS VAULT", "DROWNED RECORD", "FLOOD PYLONS"),
    "fungal": WorldArchiveProfile("fungal", "MYCELIAN BLOOM", "SPORE RECORD", "SPORE CROWN"),
    "rust": WorldArchiveProfile("rust", "FERRIC GRAVE", "INDUSTRIAL RECORD", "FOUNDRY RIBS"),
    "salt": WorldArchiveProfile("salt", "ILYR SALT MIRROR", "MIRROR RECORD", "MIRROR OBELISK"),
    "abyss": WorldArchiveProfile("abyss", "NOCTILUCENT BASIN", "VOID RECORD", "VOID LANTERN"),
    "storm": WorldArchiveProfile("storm", "TEMPEST PLATEAUS", "TEMPEST RECORD", "STORM MAST"),
    "roseglass": WorldArchiveProfile("roseglass", "ROSEGLASS BARRENS", "FRACTURE RECORD", "ROSEGLASS FAN"),
}

# Six existing ruin families become a soft authored progression cue.  The world
# generator is untouched; the mission simply prefers a different existing site
# family for each archive slot when one lies in the normal reachable target pool.
ARCHIVE_SITE_SEQUENCE = (
    ("ziggurat", "SURVEY ARCHIVE"),
    ("observatory", "OBSERVATION ARCHIVE"),
    ("bastion", "DEFENSE ARCHIVE"),
    ("spire", "SIGNAL ARCHIVE"),
    ("sepulcher", "REMNANT ARCHIVE"),
    ("labyrinth", "CONTINUITY ARCHIVE"),
)


def world_profile(style: str) -> WorldArchiveProfile:
    style = str(style or "unknown").lower()
    return WORLD_ARCHIVE_PROFILES.get(
        style,
        WorldArchiveProfile(style, style.upper() if style else "UNKNOWN WORLD", "UNKNOWN RECORD", "UNKNOWN LANDMARK"),
    )


def archive_slot(fragments_secured: int, required: int = 6, *, current_already_secured: bool = False) -> int:
    required = max(1, int(required))
    secured = max(0, min(required, int(fragments_secured)))
    if current_already_secured and secured > 0:
        return secured
    return min(required, secured + 1)


def archive_site_label(slot: int) -> str:
    idx = max(1, min(len(ARCHIVE_SITE_SEQUENCE), int(slot))) - 1
    return ARCHIVE_SITE_SEQUENCE[idx][1]


def preferred_site_order(slot: int) -> tuple[str, ...]:
    """Return all existing ruin kinds, rotated so this slot has a clear preference."""
    kinds = tuple(kind for kind, _label in ARCHIVE_SITE_SEQUENCE)
    idx = max(1, min(len(kinds), int(slot))) - 1
    return kinds[idx:] + kinds[:idx]


def style_variety_score(previous_style: str, candidate_style: str, hazard_by_style: dict[str, str]) -> int:
    """2 = new hazard family, 1 = new world class, 0 = immediate repeat."""
    previous_style = str(previous_style or "unknown").lower()
    candidate_style = str(candidate_style or "unknown").lower()
    if not candidate_style or candidate_style == "unknown":
        return 0
    if previous_style in ("", "unknown"):
        return 2
    if candidate_style == previous_style:
        return 0
    previous_hazard = str(hazard_by_style.get(previous_style, "UNKNOWN"))
    candidate_hazard = str(hazard_by_style.get(candidate_style, "UNKNOWN"))
    if previous_hazard != "UNKNOWN" and candidate_hazard != "UNKNOWN" and candidate_hazard != previous_hazard:
        return 2
    return 1


def best_site_candidates(structures: Iterable[object], slot: int) -> list[object]:
    """Return structures in authored slot-preference order without changing geometry."""
    structures = list(structures)
    if not structures:
        return []
    rank = {kind: idx for idx, kind in enumerate(preferred_site_order(slot))}
    return sorted(structures, key=lambda st: rank.get(str(getattr(st, "kind", "")), len(rank)))
