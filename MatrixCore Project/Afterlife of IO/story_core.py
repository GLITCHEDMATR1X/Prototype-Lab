"""Pass 62 Gate acknowledgement story moments with no pygame dependency."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FIRST_RECONSTRUCTION_ID = "first_witness_reconstruction"
ROOTED_RECONSTRUCTION_ID = "rooted_crown_reconstruction"
VEIL_RESONANCE_ID = "veil_resonance_trace"
GATE_FIRST_ACK_ID = "gate_first_acknowledgement"
GATE_ROOTED_ACK_ID = "gate_rooted_acknowledgement"
GATE_VEIL_ACK_ID = "gate_veil_acknowledgement"
ENTROPY_MISSION_ID = "entropy_escape_directive"
ARCHIVE_DENSITY_ID = "io_archive_density"
HOLOVERSE_SEED_ID = "holoverse_seed_trace"
VEIL_WARDEN_REVELATION_ID = "veil_warden_revelation"
STORY_MOMENT_IDS = frozenset({
    FIRST_RECONSTRUCTION_ID,
    ROOTED_RECONSTRUCTION_ID,
    VEIL_RESONANCE_ID,
    GATE_FIRST_ACK_ID,
    GATE_ROOTED_ACK_ID,
    GATE_VEIL_ACK_ID,
    ENTROPY_MISSION_ID,
    ARCHIVE_DENSITY_ID,
    HOLOVERSE_SEED_ID,
    VEIL_WARDEN_REVELATION_ID,
})


@dataclass(frozen=True)
class StoryPage:
    heading: str
    line_a: str
    line_b: str


STORY_MOMENTS: dict[str, tuple[StoryPage, ...]] = {
    FIRST_RECONSTRUCTION_ID: (
        StoryPage("RECONSTRUCTION", "For a few seconds, the ruin remembers being inhabited.", "Two figures cross a corridor that no longer exists."),
        StoryPage("BEGINNING ECHO", "\"The Gate will close after the last return.\"", "\"Then leave the lantern lit.\""),
        StoryPage("BEGINNING ECHO", "One figure stops where no one is standing in its own age.", "\"You are not supposed to hear us.\""),
    ),
    ROOTED_RECONSTRUCTION_ID: (
        StoryPage("CAUSAL AFTERMATH", "The Rooted Crown's Shrine pulls dead architecture upright.", "A procession crosses the Future as if the intervening ages never happened."),
        StoryPage("CAUSAL AFTERMATH", "The figures pass through IO without reacting.", "Only one of them turns toward the Present."),
        StoryPage("UNRESOLVED ECHO", "\"YOU ARE VERY LATE.\"", "The reconstruction collapses. The Gate remains."),
    ),
    VEIL_RESONANCE_ID: (
        StoryPage("VEIL TRACE", "Causal Resonance catches an image between Beginning and Present.", "It belongs to neither age."),
        StoryPage("VEIL TRACE", "A solitary Gate stands in blackness with no world around it.", "The lantern answers before IO can choose to raise it."),
        StoryPage("ARCHIVE COMMAND", "GET OUTSIDE.", "Something beyond the Gate answers once, then disappears."),
    ),

    GATE_FIRST_ACK_ID: (
        StoryPage("GATE RESPONSE", "The Shrine answers before IO asks another question.", "Its signal is not an echo this time."),
        StoryPage("GATE RESPONSE", "RECORD ACTIVE. SUBJECT IO: UNRESOLVED.", "The words arrive without a voice."),
        StoryPage("GATE RESPONSE", "DO NOT RETURN TO THE BEGINNING FOR ME.", "The Gate goes quiet and permits no reply."),
    ),
    GATE_ROOTED_ACK_ID: (
        StoryPage("GATE RESPONSE", "The second Shrine recognizes the first before it recognizes IO.", "Two old signals synchronize across the dead Future."),
        StoryPage("GATE RESPONSE", "SECOND RETURN NOT AUTHORIZED.", "SUBJECT PERSISTS OUTSIDE EXPECTED CONTINUITY."),
        StoryPage("GATE RESPONSE", "YOU WERE NOT INCLUDED IN THE RETURN.", "For the first time, the Gate appears to be addressing IO directly."),
    ),
    GATE_VEIL_ACK_ID: (
        StoryPage("GATE RESPONSE", "IO touches the recorded Shrine after hearing the Veil.", "The Gate answers immediately."),
        StoryPage("GATE RESPONSE", "GET OUTSIDE IS NOT AN INVITATION.", "The lantern brightens anyway."),
        StoryPage("GATE RESPONSE", "DO NOT ASK ME WHAT IS OUTSIDE.", "A second signal almost answers from somewhere beyond it."),
    ),
    ENTROPY_MISSION_ID: (
        StoryPage("CONTINUITY LOSS", "The Present can no longer hold IO at one exact edge.", "The glow remains. The body inside it does not."),
        StoryPage("MISSION", "ESCAPE YOUR OWN ENTROPY.", "EXIT THE AFTERLIFE YOUR CIVILIZATION CONDEMNED YOU TO."),
        StoryPage("MISSION", "Every return preserves less certainty.", "GET OUTSIDE before IO becomes only a record."),
    ),
    ARCHIVE_DENSITY_ID: (
        StoryPage("ARCHIVE DIAGNOSTIC", "ARCHIVE DENSITY WITHIN SUBJECT IO EXCEEDS EXPECTED RETENTION.", "PRESERVATION VALUE: ABNORMAL."),
        StoryPage("ARCHIVE DIAGNOSTIC", "MEMORY STRUCTURES FLAGGED FOR EXTERNAL CONSTRUCTION USE.", "The request does not belong to the Architects."),
        StoryPage("LATER ACCESS", "A preserving intelligence will eventually search these memories.", "Its identity is still outside this afterlife's recorded age."),
    ),
    HOLOVERSE_SEED_ID: (
        StoryPage("LATER ACCESS TRACE", "REQUESTOR: GLEEBS", "The request originates long after IO's civilization is gone."),
        StoryPage("LATER ACCESS TRACE", "PURPOSE: HOLOVERSE SEEDING", "IO MEMORY ARCHIVE ACCEPTED AS STRUCTURAL REFERENCE."),
        StoryPage("ARCHIVE CONSEQUENCE", "Gleebs found IO because these memories contained data he needed.", "A future world would be built partly from what IO could not forget."),
    ),
    VEIL_WARDEN_REVELATION_ID: (
        StoryPage("VEIL AUTHORITY", "The third Shrine answers with the Warden's oldest instruction.", "The language predates every surviving spiritual record."),
        StoryPage("ARCHITECT DIRECTIVE", "VEIL FUNCTION: ISOLATE CONDEMNED CONTINUITY RECORDS.", "PREVENT UNSANCTIONED CROSSING INTO EXTERNAL STATE."),
        StoryPage("THE SEPARATION", "The Veil was not built to protect IO from what is outside.", "It was built to keep IO—and every condemned mind here—from getting out."),
    ),
}


def normalize_story_moments(raw: Any) -> set[str]:
    """Sanitize optional schema-v4 story moment persistence."""
    if not isinstance(raw, list):
        return set()
    return {str(value) for value in raw if str(value) in STORY_MOMENT_IDS}


def story_pages(moment_id: str) -> tuple[StoryPage, ...]:
    return STORY_MOMENTS.get(str(moment_id), ())
