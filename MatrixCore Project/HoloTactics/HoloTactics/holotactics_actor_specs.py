from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ActorVisualSpec:
    actor_id: str
    name: str
    faction: str
    silhouette: str
    palette: tuple[str, ...]
    board_read: str
    footprint_radius: float
    max_height: float
    reference_note: str


GLEEBS_REFERENCE_ASSET = Path("assets/reference/Gleebs.png")

ACTOR_VISUAL_SPECS: dict[str, ActorVisualSpec] = {
    "gleebs": ActorVisualSpec(
        actor_id="gleebs",
        name="Gleebs",
        faction="player",
        silhouette="compact horned glitch-guide with dark core body, toxic-green visor, purple armor breaks, and paired orb accents",
        palette=("blackened holo body", "toxic green", "deep purple", "cyan orb", "red orb"),
        board_read="main-character support/controller; must remain recognizable as Gleebs rather than a generic cute bot",
        footprint_radius=0.48,
        max_height=1.16,
        reference_note="Uses the supplied Gleebs reference image as the identity reference for color/silhouette language; no generated art is required.",
    ),
    "guard": ActorVisualSpec(
        actor_id="guard",
        name="Fracture Guard",
        faction="player",
        silhouette="wide anchor-tank with broad shoulders, heavy shield mass, and low stable stance",
        palette=("dark blue chassis", "cyan trim", "bright shield core"),
        board_read="defender/frontline; readable as the heaviest ally even at board distance",
        footprint_radius=0.54,
        max_height=1.06,
        reference_note="Keeps player-side controlled hologram language; not corrupted or monstrous.",
    ),
    "runner": ActorVisualSpec(
        actor_id="runner",
        name="Phase Runner",
        faction="player",
        silhouette="slender skirmisher with forward lean, swept phase fins, and motion-streak panels",
        palette=("deep indigo", "cyan edge light", "violet phase trails"),
        board_read="fast/flanker; thinner than Guard and more dynamic than Gleebs",
        footprint_radius=0.46,
        max_height=1.04,
        reference_note="Uses controlled HoloVerse motion accents; avoids bulky armor.",
    ),
    "anomaly": ActorVisualSpec(
        actor_id="anomaly",
        name="Corrupted Anomaly",
        faction="enemy",
        silhouette="fragmented melee disruptor with dark broken mass, toxic cores, red hostile base, and jagged shard arms",
        palette=("near-black", "corruption purple", "toxic green", "hostile red"),
        board_read="enemy melee/disruptor; reference-inspired corruption without confusing it for Gleebs",
        footprint_radius=0.55,
        max_height=1.18,
        reference_note="Borrows green/purple hostile energy from the Gleebs reference while keeping red enemy coding.",
    ),
    "sentry": ActorVisualSpec(
        actor_id="sentry",
        name="Rule Sentry",
        faction="enemy",
        silhouette="floating ranged eye-drone with vertical spine, side fins, and red targeting core",
        palette=("dark maroon", "red sensor", "purple fins", "toxic secondary glow"),
        board_read="enemy ranged/enforcer; should look more precise and mechanical than the Anomaly",
        footprint_radius=0.50,
        max_height=1.18,
        reference_note="Uses orb/core language from the reference while remaining a separate enemy type.",
    ),
}


def validate_actor_visual_specs() -> list[str]:
    issues: list[str] = []
    required = {"gleebs", "guard", "runner", "anomaly", "sentry"}
    if set(ACTOR_VISUAL_SPECS) != required:
        issues.append("actor spec set does not match current playable/enemy units")
    for actor_id, spec in ACTOR_VISUAL_SPECS.items():
        if spec.footprint_radius > 0.62:
            issues.append(f"{actor_id}: footprint too large for one board tile")
        if spec.max_height > 1.25:
            issues.append(f"{actor_id}: silhouette too tall for current camera/UI clearance")
        if not spec.silhouette or not spec.board_read:
            issues.append(f"{actor_id}: missing readable actor direction")
    if "reference" not in ACTOR_VISUAL_SPECS["gleebs"].reference_note.lower():
        issues.append("gleebs: supplied identity reference is not documented in the spec")
    for actor_id in ("anomaly", "sentry"):
        spec = ACTOR_VISUAL_SPECS[actor_id]
        if "red" not in " ".join(spec.palette).lower():
            issues.append(f"{actor_id}: enemy coding must retain red hostile language")
    return issues
