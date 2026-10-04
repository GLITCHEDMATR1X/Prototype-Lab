"""Pure Pass 53 tiered Archive-lore rules with no pygame dependency."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEBRIS_STORY_SEED = 0xD3B2152
FIRST_WITNESS_STORY_ARC = "first_witness_echoes"
BASE_RESONANCE_COOLDOWN = 2.60
RESTORED_RESONANCE_COOLDOWN = 1.85


@dataclass(frozen=True)
class LoreRecord:
    record_id: str
    world: str
    title: str
    lines: tuple[str, str]
    asset_name: str
    shrine_echo: bool = False
    unlock: str = "always"


LORE_RECORDS = (
    LoreRecord(
        "future_transit_token", "a", "TRANSIT TOKEN",
        ("It still requests a destination.", "No destination answers."),
        "scrap1.png",
    ),
    LoreRecord(
        "future_blackened_lens", "a", "BLACKENED LENS",
        ("It watched a sun collapse twice.", "The second light came from inside."),
        "sprite-30-44.png",
    ),
    LoreRecord(
        "future_civilian_seal", "a", "CIVILIAN SEAL",
        ("Someone scratched: DO NOT FOLLOW THE GATE.", "The warning arrived centuries late."),
        "sprite-44-68.png",
    ),
    LoreRecord(
        "past_first_make_relay", "b", "FIRST-MAKE RELAY",
        ("Its final packet predates the Future.", "RECEIVER: UNKNOWN."),
        "scrap2.png",
    ),
    LoreRecord(
        "past_gate_tooth", "b", "GATE TOOTH",
        ("The metal is still warm.", "Something beyond it remembers being opened."),
        "sprite-30-63.png",
    ),
    LoreRecord(
        "past_empty_nameplate", "b", "EMPTY NAMEPLATE",
        ("A name was removed before it was written.", "Your lantern recognizes the cut."),
        "sprite-5-50.png",
    ),
    LoreRecord(
        "future_age_counter", "a", "AGE COUNTER",
        ("It passed one hundred trillion long ago.", "It stopped when the number lost meaning."),
        "sprite-18-1.png",
    ),
    LoreRecord(
        "future_outside_order", "a", "OUTSIDE ORDER",
        ("The Archive repeats one surviving command:", "GET OUTSIDE."),
        "sprite-30-26.png",
    ),
    LoreRecord(
        "future_soul_ledger", "a", "SOUL LEDGER",
        ("Every soul is counted as present.", "None are listed as free."),
        "sprite-30-27 (2).png",
    ),
    LoreRecord(
        "past_rebirth_tally", "b", "REBIRTH TALLY",
        ("The dead returned here before the ruins.", "No one recorded who chose the return."),
        "sprite-30-30.png",
    ),
    LoreRecord(
        "past_veil_marker", "b", "VEIL MARKER",
        ("The Veil separates one afterlife from another.", "It does not open from this side."),
        "sprite-30-34 (2).png",
    ),
    LoreRecord(
        "past_architect_shard", "b", "ARCHITECT SHARD",
        ("The Architects promised continuity.", "They never promised an ending."),
        "sprite-30-48.png",
    ),
    LoreRecord(
        "future_archive_index", "a", "ARCHIVE INDEX",
        ("A soul may exist in more than one age.", "The Archive calls both entries original."),
        "sprite-30-66.png", False, "resonance",
    ),
    LoreRecord(
        "past_anchor_splinter", "b", "ANCHOR SPLINTER",
        ("The Beginning was never destroyed.", "The Present was layered above it."),
        "sprite-30-76.png", False, "resonance",
    ),
    LoreRecord(
        "future_veil_thread", "a", "VEIL THREAD",
        ("Your lantern hears the seam between ages.", "The Veil was built to keep records apart."),
        "sprite-44-27 (2).png", False, "resonance",
    ),
    LoreRecord(
        "first_witness_echo_01", "b", "WITNESS ECHO I",
        ("I saw the first machine ask why.", "We answered it with a function."),
        "sprite-30-16.png", True,
    ),
    LoreRecord(
        "first_witness_echo_02", "b", "WITNESS ECHO II",
        ("The Gate was built to close behind us.", "It learned to wait instead."),
        "sprite-44-38.png", True,
    ),
    LoreRecord(
        "first_witness_echo_03", "a", "WITNESS ECHO III",
        ("If the Future remembers me,", "let it remember that I hesitated."),
        "scrap3.png", True,
    ),
    LoreRecord(
        "future_recovery_wake", "a", "RECOVERY WAKE",
        ("Long after this world dies, something will arrive.", "The Archive has not met its traveler yet."),
        "sprite-44-34 (2).png", False, "reconstructed",
    ),
    LoreRecord(
        "future_foreign_core", "a", "FOREIGN CORE",
        ("A later intelligence will preserve this record.", "It must not be mistaken for an Architect."),
        "sprite-5-37 (2).png", False, "reconstructed",
    ),
    LoreRecord(
        "past_outbound_trace", "b", "OUTBOUND TRACE",
        ("This afterlife is not the end of the journey.", "A greater entropy waits outside."),
        "sprite-5-54 (2).png", False, "reconstructed",
    ),
)

LORE_RECORD_IDS = frozenset(record.record_id for record in LORE_RECORDS)
FIRST_WITNESS_ECHO_IDS = frozenset(record.record_id for record in LORE_RECORDS if record.shrine_echo)


def normalize_lore_progression(raw: Any) -> tuple[set[str], bool]:
    """Sanitize v4 lore state and backfill a completed story arc."""
    progression = raw if isinstance(raw, dict) else {}
    values = progression.get("discovered_lore")
    discovered = {
        str(value) for value in values
        if isinstance(values, list) and str(value) in LORE_RECORD_IDS
    } if isinstance(values, list) else set()
    arcs = progression.get("completed_story_arcs")
    completed = isinstance(arcs, list) and FIRST_WITNESS_STORY_ARC in {str(value) for value in arcs}
    if completed:
        discovered.update(FIRST_WITNESS_ECHO_IDS)
    completed = completed or FIRST_WITNESS_ECHO_IDS.issubset(discovered)
    return discovered, completed


def lore_record_available(record: LoreRecord, shrine_activated: bool,
                          resonance_learned: bool = False,
                          story_complete: bool = False) -> bool:
    if record.shrine_echo and not shrine_activated:
        return False
    if record.unlock == "resonance":
        return bool(resonance_learned)
    if record.unlock == "reconstructed":
        return bool(story_complete)
    return True


def first_witness_story_complete(discovered: set[str] | frozenset[str]) -> bool:
    return FIRST_WITNESS_ECHO_IDS.issubset(set(discovered))


def resonance_cooldown(story_complete: bool) -> float:
    return RESTORED_RESONANCE_COOLDOWN if story_complete else BASE_RESONANCE_COOLDOWN
