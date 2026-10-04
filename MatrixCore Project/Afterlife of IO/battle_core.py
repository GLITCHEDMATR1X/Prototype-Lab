"""Headless Memory Guardian battle authority for Afterlife of IO.

The pattern tables define each Guardian's readable questions and counter rules.
The live game may select among those questions non-sequentially; this module keeps
resolution deterministic for a selected move index and intentionally has no pygame
dependency so encounters can be regression-tested without the renderer/runtime.
"""
from __future__ import annotations
from dataclasses import dataclass

FIRST_WITNESS_MAX_PRESENCE = 6
FIRST_WITNESS_MAX_RESOLVE = 5


@dataclass(frozen=True)
class WitnessMove:
    key: str
    label: str
    telegraph: str
    gleebs_hint: str


@dataclass(frozen=True)
class WitnessResponse:
    player_damage: int = 0
    entity_heal: int = 0
    countered: bool = False
    message: str = ""


FIRST_WITNESS_PATTERN = (
    WitnessMove(
        key="witness_strike",
        label="DIRECT WITNESS",
        telegraph="THE WITNESS DRAWS A STRAIGHT LINE THROUGH IO.",
        gleebs_hint="GLEEBS // Something direct. Brace for the answer.",
    ),
    WitnessMove(
        key="gate_anchor",
        label="GATE ANCHOR",
        telegraph="THE GATE OPENS. AN ANCHOR FORMS BEHIND THE WITNESS.",
        gleebs_hint="GLEEBS // Do not let that connection settle.",
    ),
    WitnessMove(
        key="deep_recall",
        label="DEEP RECALL",
        telegraph="THE CHAMBER DOUBLES. IO'S MEMORY IS PULLED INWARD.",
        gleebs_hint="GLEEBS // Hold the lantern steady. Trust one image.",
    ),
)


def first_witness_move(turn_index: int) -> WitnessMove:
    """Return the deterministic move telegraphed for the current player turn."""
    try:
        index = int(turn_index)
    except (TypeError, ValueError):
        index = 0
    return FIRST_WITNESS_PATTERN[index % len(FIRST_WITNESS_PATTERN)]


def resolve_first_witness_response(
    turn_index: int,
    player_action: str,
    guard_active: bool,
    entity_presence: int,
) -> WitnessResponse:
    """Resolve the already-telegraphed First Witness response.

    Counter language is deliberately tied to the player's existing four-action
    battle vocabulary instead of introducing a new subsystem:
      * DIRECT WITNESS -> Guard fully answers it.
      * GATE ANCHOR    -> Lantern Shot severs the support link.
      * DEEP RECALL    -> Focus stabilizes IO; Guard only softens the mistake.
    """
    move = first_witness_move(turn_index)
    action = str(player_action or "").strip().lower()
    guard = bool(guard_active)
    try:
        presence = max(0, min(FIRST_WITNESS_MAX_PRESENCE, int(entity_presence)))
    except (TypeError, ValueError):
        presence = FIRST_WITNESS_MAX_PRESENCE

    if move.key == "witness_strike":
        if guard:
            return WitnessResponse(countered=True, message="The Witness's direct answer breaks on IO's lantern veil.")
        return WitnessResponse(player_damage=2, message="The Witness answers directly: -2 Resolve.")

    if move.key == "gate_anchor":
        if action == "shot":
            return WitnessResponse(countered=True, message="Lantern light severs the Gate's anchor before it can settle.")
        heal = min(1, FIRST_WITNESS_MAX_PRESENCE - presence)
        if heal:
            return WitnessResponse(entity_heal=heal, message="The Gate restores the Witness: +1 Presence.")
        return WitnessResponse(message="The Gate hardens the Witness at full Presence.")

    # DEEP RECALL is a memory attack. Focus is the intended answer; Guard is a
    # forgiving partial response so the player can learn the pattern without an
    # opaque punishment spike.
    if action == "focus":
        return WitnessResponse(countered=True, message="IO fixes on the lantern. The false memory collapses harmlessly.")
    if guard:
        return WitnessResponse(player_damage=1, message="The veil catches part of the recall, but IO still loses 1 Resolve.")
    return WitnessResponse(player_damage=2, message="Deep Recall tears through IO's continuity: -2 Resolve.")

# Pass 58 — second authored Entity.  This encounter deliberately keeps the
# existing four-command vocabulary while asking different questions with it.
ROOTED_CROWN_ID = "rooted_crown"
ROOTED_CROWN_MAX_PRESENCE = 7
ROOTED_CROWN_MAX_RESOLVE = 5

VEIL_WARDEN_ID = "boss3"
VEIL_WARDEN_MAX_PRESENCE = 8
VEIL_WARDEN_MAX_RESOLVE = 5

ROOTED_CROWN_PATTERN = (
    WitnessMove(
        key="crown_pressure",
        label="CROWN PRESSURE",
        telegraph="THE CROWN LOWERS. THE CHAMBER'S WEIGHT GATHERS OVER IO.",
        gleebs_hint="GLEEBS // Do not brace against weight. Find the still point.",
    ),
    WitnessMove(
        key="rooted_seal",
        label="ROOTED SEAL",
        telegraph="THE ROOT MASS CLOSES AROUND THE LANTERN'S REFLECTION.",
        gleebs_hint="GLEEBS // Hold your ground. Let the seal meet the veil.",
    ),
    WitnessMove(
        key="hollow_bloom",
        label="HOLLOW BLOOM",
        telegraph="THE CROWN OPENS INTO A FALSE SKY. THE GATE BEGINS TO FEED IT.",
        gleebs_hint="GLEEBS // Break the bloom before it drinks the chamber.",
    ),
)


def rooted_crown_move(turn_index: int) -> WitnessMove:
    try:
        index = int(turn_index)
    except (TypeError, ValueError):
        index = 0
    return ROOTED_CROWN_PATTERN[index % len(ROOTED_CROWN_PATTERN)]


def resolve_rooted_crown_response(
    turn_index: int,
    player_action: str,
    guard_active: bool,
    entity_presence: int,
) -> WitnessResponse:
    """Resolve The Rooted Crown's deterministic three-question pattern.

    The battle shares IO's established command set without cloning the First
    Witness's consequence pattern:
      * CROWN PRESSURE -> Focus is the clean counter; Guard only softens it.
      * ROOTED SEAL    -> Guard cleanly absorbs the closing seal.
      * HOLLOW BLOOM   -> Lantern Shot interrupts a stronger two-point heal.
    """
    move = rooted_crown_move(turn_index)
    action = str(player_action or "").strip().lower()
    guard = bool(guard_active)
    try:
        presence = max(0, min(ROOTED_CROWN_MAX_PRESENCE, int(entity_presence)))
    except (TypeError, ValueError):
        presence = ROOTED_CROWN_MAX_PRESENCE

    if move.key == "crown_pressure":
        if action == "focus":
            return WitnessResponse(countered=True, message="IO fixes on one still point. The Crown's weight passes around the lantern.")
        if guard:
            return WitnessResponse(player_damage=1, message="The veil bends under the Crown: -1 Resolve.")
        return WitnessResponse(player_damage=2, message="The Crown drives the chamber downward: -2 Resolve.")

    if move.key == "rooted_seal":
        if guard:
            return WitnessResponse(countered=True, message="The seal closes on IO's veil and fractures harmlessly around the lantern.")
        return WitnessResponse(player_damage=2, message="The Rooted Seal closes around IO: -2 Resolve.")

    if action == "shot":
        return WitnessResponse(countered=True, message="Lantern light pierces the Hollow Bloom before the Gate can feed it.")
    heal = min(2, ROOTED_CROWN_MAX_PRESENCE - presence)
    if heal:
        return WitnessResponse(entity_heal=heal, message=f"The Hollow Bloom drinks from the chamber: +{heal} Presence.")
    return WitnessResponse(message="The Hollow Bloom opens at full Presence, unable to restore more.")


# Pass 71 — third authored Entity. The Veil Warden tests the same readable
# base commands while reframing the Veil as an isolation boundary rather than
# a mystical horizon. Entropy Arc remains optional bonus damage, never a
# required counter, so story progression does not depend on Echo grinding.
VEIL_WARDEN_PATTERN = (
    WitnessMove(
        key="boundary_fold",
        label="BOUNDARY FOLD",
        telegraph="THE VEIL FOLDS INWARD. TWO EDGES TRY TO BECOME ONE.",
        gleebs_hint="GLEEBS // Hold the edge. Let the fold spend itself on the veil.",
    ),
    WitnessMove(
        key="false_exit",
        label="FALSE EXIT",
        telegraph="A BRIGHT OPENING APPEARS WHERE NO EXIT CAN EXIST.",
        gleebs_hint="GLEEBS // Do not follow the picture. Fix on what you already know.",
    ),
    WitnessMove(
        key="archive_latch",
        label="ARCHIVE LATCH",
        telegraph="A LATCH FORMS ACROSS THE WARDEN'S CENTER AND BEGINS TO SEAL.",
        gleebs_hint="GLEEBS // Break the latch before it closes the record around you.",
    ),
)


def veil_warden_move(turn_index: int) -> WitnessMove:
    try:
        index = int(turn_index)
    except (TypeError, ValueError):
        index = 0
    return VEIL_WARDEN_PATTERN[index % len(VEIL_WARDEN_PATTERN)]


def resolve_veil_warden_response(
    turn_index: int, player_action: str, guard_active: bool, entity_presence: int
) -> WitnessResponse:
    """Resolve the Veil Warden's three readable questions.

    BOUNDARY FOLD -> Guard. FALSE EXIT -> Focus. ARCHIVE LATCH -> Shot.
    This deliberately tests mastery of the original vocabulary before the
    campaign asks IO to cross the Veil itself.
    """
    move = veil_warden_move(turn_index)
    action = str(player_action or "").strip().lower()
    guard = bool(guard_active)
    try:
        presence = max(0, min(VEIL_WARDEN_MAX_PRESENCE, int(entity_presence)))
    except (TypeError, ValueError):
        presence = VEIL_WARDEN_MAX_PRESENCE

    if move.key == "boundary_fold":
        if guard:
            return WitnessResponse(countered=True, message="IO's veil holds one edge steady. The Boundary Fold passes around it.")
        return WitnessResponse(player_damage=2, message="The Fold closes through IO's continuity: -2 Resolve.")

    if move.key == "false_exit":
        if action == "focus":
            return WitnessResponse(countered=True, message="IO fixes on the lantern. The impossible exit loses its shape.")
        if guard:
            return WitnessResponse(player_damage=1, message="The veil catches the false crossing, but IO loses 1 Resolve.")
        return WitnessResponse(player_damage=2, message="IO follows a route that never existed: -2 Resolve.")

    if action == "shot":
        return WitnessResponse(countered=True, message="Lantern light cuts the Archive Latch before the Veil can seal.")
    heal = min(1, VEIL_WARDEN_MAX_PRESENCE - presence)
    if heal:
        return WitnessResponse(entity_heal=heal, message="The Archive Latch closes another layer around the Warden: +1 Presence.")
    return WitnessResponse(message="The Archive Latch hardens at full Presence.")


# Pass 68 — optional recurring Shrine Echo Challenges. Story battles remain
# tier 0. Rematches begin at tier 1 and scale to a bounded tier 5.
ECHO_CHALLENGE_MAX_TIER = 5


def echo_challenge_tier(rematch_wins: int) -> int:
    try:
        wins = max(0, int(rematch_wins))
    except (TypeError, ValueError, OverflowError):
        wins = 0
    return min(ECHO_CHALLENGE_MAX_TIER, wins + 1)


def echo_challenge_presence(base_presence: int, tier: int) -> int:
    try:
        challenge = max(0, min(ECHO_CHALLENGE_MAX_TIER, int(tier)))
    except (TypeError, ValueError, OverflowError):
        challenge = 0
    return max(1, int(base_presence) + challenge * 2)


def echo_challenge_damage_bonus(tier: int) -> int:
    try:
        challenge = max(0, min(ECHO_CHALLENGE_MAX_TIER, int(tier)))
    except (TypeError, ValueError, OverflowError):
        challenge = 0
    # Tier 1 is already harder through extra Presence. Later tiers also make
    # mistakes more expensive without changing the readable counter pattern.
    return max(0, (challenge - 1) // 2)

# Pass 85 — the remaining archive guardians are available nonlinearly in the Past.
# They reuse IO's readable three-answer vocabulary so challenge comes from timing,
# sequencing and punishment rather than opaque new controls.
ARCHIVE_CHORUS_ID = "boss4"
HOLLOW_ENGINE_ID = "boss5"
LAST_CARTOGRAPHER_ID = "boss6"
FINAL_GUARDIAN_ID = "finalboss"

ARCHIVE_CHORUS_MAX_PRESENCE = 9
HOLLOW_ENGINE_MAX_PRESENCE = 10
LAST_CARTOGRAPHER_MAX_PRESENCE = 12
FINAL_GUARDIAN_MAX_PRESENCE = 30
GENERIC_GUARDIAN_MAX_RESOLVE = 5

ARCHIVE_CHORUS_PATTERN = (
    WitnessMove("chorus_surge", "CHORUS SURGE", "A THOUSAND RECORDED VOICES COLLAPSE TOWARD IO.", "GLEEBS // Hold the edge. Let the voices break against the veil."),
    WitnessMove("name_loss", "NAME LOSS", "THE ARCHIVE REMOVES IO'S NAME FROM ITS OWN MEMORY.", "GLEEBS // Fix on one true memory. Do not follow the absence."),
    WitnessMove("echo_feed", "ECHO FEED", "THE CHOIR OPENS A CHANNEL AND BEGINS TO RESTORE ITSELF.", "GLEEBS // Cut the feed before the record fills itself again."),
)

HOLLOW_ENGINE_PATTERN = (
    WitnessMove("pressure_cycle", "PRESSURE CYCLE", "THE ENGINE COMPRESSES THE ROOM INTO ONE REPEATING SECOND.", "GLEEBS // Find the still point inside the repetition."),
    WitnessMove("vault_lock", "VAULT LOCK", "A MEMORY VAULT CLOSES AROUND IO'S LANTERN.", "GLEEBS // Break the lock before the archive seals."),
    WitnessMove("memory_shear", "MEMORY SHEAR", "TWO VERSIONS OF IO SLIDE APART ALONG THE SAME LINE.", "GLEEBS // Brace. Keep one version from separating."),
)

LAST_CARTOGRAPHER_PATTERN = (
    WitnessMove("map_fold", "MAP FOLD", "THE MAP OF THE LOST WORLD FOLDS THROUGH IO'S POSITION.", "GLEEBS // Hold your ground while the map passes through."),
    WitnessMove("false_coordinate", "FALSE COORDINATE", "A PERFECT ROUTE APPEARS TO A PLACE THAT NEVER EXISTED.", "GLEEBS // Trust the lantern, not the route."),
    WitnessMove("route_seal", "ROUTE SEAL", "THE CARTOGRAPHER CLOSES EVERY EXIT INTO ONE MARK.", "GLEEBS // Break the mark before the route is sealed."),
)

# The final guardian deliberately combines six already-learned questions. It is
# intended to be extremely difficult, but upgrades can increase starting Resolve
# and slightly reduce its Presence so complete mastery meaningfully improves odds.
FINAL_GUARDIAN_PATTERN = (
    WitnessMove("final_guard", "CIVILIZATION PRESS", "THE LAST ARCHIVE PRESSES AN ENTIRE CIVILIZATION AGAINST IO.", "GLEEBS // Guard. Do not let the dead world move you."),
    WitnessMove("final_focus", "IDENTITY ERASURE", "THE RECORD OFFERS IO A PERFECT MEMORY WITH HIMSELF REMOVED.", "GLEEBS // Focus. Keep one true self in the lantern."),
    WitnessMove("final_shot", "ARCHIVE SEAL", "THE FINAL VAULT BEGINS TO SEAL THE MEMORY SET FOREVER.", "GLEEBS // Shoot. Break the seal before it closes."),
    WitnessMove("final_focus", "ENTROPY MIRROR", "IO'S FUTURE DECAY IS REFLECTED BACK AS AN ORIGINAL MEMORY.", "GLEEBS // Focus. It is a reflection, not an origin."),
    WitnessMove("final_guard", "RETURN COLLAPSE", "EVERY FAILED RETURN ARRIVES AT ONCE.", "GLEEBS // Guard. Let the returns exhaust themselves."),
    WitnessMove("final_shot", "LAST INDEX", "THE CUSTODIAN WRITES THE LAST INDEX ENTRY: IO.", "GLEEBS // Shoot. Refuse the final entry."),
)


def _pattern_move(pattern: tuple[WitnessMove, ...], turn_index: int) -> WitnessMove:
    try:
        index = int(turn_index)
    except (TypeError, ValueError):
        index = 0
    return pattern[index % len(pattern)]


def archive_chorus_move(turn_index: int) -> WitnessMove:
    return _pattern_move(ARCHIVE_CHORUS_PATTERN, turn_index)


def hollow_engine_move(turn_index: int) -> WitnessMove:
    return _pattern_move(HOLLOW_ENGINE_PATTERN, turn_index)


def last_cartographer_move(turn_index: int) -> WitnessMove:
    return _pattern_move(LAST_CARTOGRAPHER_PATTERN, turn_index)


def final_guardian_move(turn_index: int) -> WitnessMove:
    return _pattern_move(FINAL_GUARDIAN_PATTERN, turn_index)


def _resolve_guardian_threeway(move: WitnessMove, action: str, guard: bool, presence: int,
                               max_presence: int, guard_key: str, focus_key: str, shot_key: str,
                               mistake_damage: int = 2, heal_amount: int = 1) -> WitnessResponse:
    action = str(action or "").strip().lower()
    if move.key == guard_key:
        if guard:
            return WitnessResponse(countered=True, message="The memory pressure breaks against IO's veil.")
        return WitnessResponse(player_damage=mistake_damage, message=f"The archive tears through IO: -{mistake_damage} Resolve.")
    if move.key == focus_key:
        if action == "focus":
            return WitnessResponse(countered=True, message="IO fixes on one true memory. The false record collapses.")
        if guard and mistake_damage > 1:
            return WitnessResponse(player_damage=mistake_damage - 1, message=f"The veil softens the false memory: -{mistake_damage - 1} Resolve.")
        return WitnessResponse(player_damage=mistake_damage, message=f"The false record consumes continuity: -{mistake_damage} Resolve.")
    if action == "shot":
        return WitnessResponse(countered=True, message="Lantern light breaks the archive seal before it can close.")
    heal = min(heal_amount, max(0, max_presence - int(presence)))
    if heal:
        return WitnessResponse(entity_heal=heal, message=f"The archive restores itself: +{heal} Presence.")
    return WitnessResponse(message="The archive seal hardens at full Presence.")


def resolve_archive_chorus_response(turn_index: int, player_action: str, guard_active: bool, entity_presence: int) -> WitnessResponse:
    return _resolve_guardian_threeway(archive_chorus_move(turn_index), player_action, guard_active, entity_presence,
                                     ARCHIVE_CHORUS_MAX_PRESENCE, "chorus_surge", "name_loss", "echo_feed", 2, 2)


def resolve_hollow_engine_response(turn_index: int, player_action: str, guard_active: bool, entity_presence: int) -> WitnessResponse:
    # Engine asks Focus -> Shot -> Guard.
    move = hollow_engine_move(turn_index)
    if move.key == "pressure_cycle":
        if str(player_action or "").lower() == "focus":
            return WitnessResponse(countered=True, message="IO finds the still point. The pressure cycle skips him.")
        return WitnessResponse(player_damage=2 if not guard_active else 1, message="The repeating second crushes IO's continuity.")
    if move.key == "vault_lock":
        if str(player_action or "").lower() == "shot":
            return WitnessResponse(countered=True, message="Lantern light fractures the vault lock.")
        heal = min(2, max(0, HOLLOW_ENGINE_MAX_PRESENCE - int(entity_presence)))
        return WitnessResponse(entity_heal=heal, message=f"The sealed vault restores {heal} Presence." if heal else "The vault is already full.")
    if guard_active:
        return WitnessResponse(countered=True, message="IO's veil keeps the two memories from shearing apart.")
    return WitnessResponse(player_damage=2, message="Memory Shear splits IO's continuity: -2 Resolve.")


def resolve_last_cartographer_response(turn_index: int, player_action: str, guard_active: bool, entity_presence: int) -> WitnessResponse:
    return _resolve_guardian_threeway(last_cartographer_move(turn_index), player_action, guard_active, entity_presence,
                                     LAST_CARTOGRAPHER_MAX_PRESENCE, "map_fold", "false_coordinate", "route_seal", 3, 2)


def resolve_final_guardian_response(turn_index: int, player_action: str, guard_active: bool, entity_presence: int) -> WitnessResponse:
    move = final_guardian_move(turn_index)
    action = str(player_action or "").strip().lower()
    if move.key == "final_guard":
        if guard_active:
            return WitnessResponse(countered=True, message="IO holds. The dead civilization breaks against the veil.")
        return WitnessResponse(player_damage=4, message="The civilization-wide pressure erases 4 Resolve.")
    if move.key == "final_focus":
        if action == "focus":
            return WitnessResponse(countered=True, message="IO preserves one true self. The erasure fails.")
        return WitnessResponse(player_damage=4 if not guard_active else 3, message="The false identity consumes IO's continuity.")
    if action == "shot":
        return WitnessResponse(countered=True, message="Lantern light fractures the final archive seal.")
    heal = min(3, max(0, FINAL_GUARDIAN_MAX_PRESENCE - int(entity_presence)))
    return WitnessResponse(entity_heal=heal, message=f"The Final Archive restores {heal} Presence." if heal else "The Final Archive cannot restore beyond full Presence.")


def final_guardian_limits(upgrade_score: int) -> tuple[int, int]:
    """Return the capstone's starting Resolve/Presence for total mastery.

    Score 0 remains deliberately brutal: 5 Resolve vs 30 Presence.
    Score 16 represents all major current power mastery plus the six recovered
    non-final civilization archives. Full mastery improves the opening to
    12 Resolve vs 20 Presence while the severe pattern/punishments remain.
    """
    try:
        score = max(0, min(16, int(upgrade_score)))
    except (TypeError, ValueError, OverflowError):
        score = 0
    return min(12, 5 + score // 2), max(20, FINAL_GUARDIAN_MAX_PRESENCE - score)
