from __future__ import annotations

from dataclasses import dataclass

from game.city_map import BuildingStatus, CityMapModel, COMMERCIAL_BUILDINGS, INDUSTRIAL_BUILDINGS
from game.save_profile import ProfileState


@dataclass(frozen=True)
class MemoryFragment:
    fragment_id: str
    title: str
    source: str
    text: str


MEMORY_FRAGMENTS: dict[str, MemoryFragment] = {
    "andrew_awakening": MemoryFragment(
        "andrew_awakening",
        "AWAKENING TRACE",
        "PUBLIC SURVEILLANCE ANNEX",
        "The municipal lens authenticated Andrew's signal before Andrew remembered his own name.",
    ),
    "gleebs_continuity": MemoryFragment(
        "gleebs_continuity",
        "CONTINUITY ROUTE",
        "MAINTENANCE YARD",
        "During the collapse, Gleebs redirected repair drones to preserve people, archives, and routes the Overseers abandoned.",
    ),
    "the_kept_route": MemoryFragment(
        "the_kept_route",
        "THE KEPT ROUTE",
        "TRANSIT DEPOT",
        "GLEEBS: I kept your routes alive. I did not keep your excuses.",
    ),
    "mall_identity_echo": MemoryFragment(
        "mall_identity_echo",
        "THE SHOPPER WHO NEVER LEFT",
        "CORPORATE MALL",
        "The mall retained Andrew as an expired loyalty identity long after the prison records erased his public name.",
    ),
    "broadcast_dead_air": MemoryFragment(
        "broadcast_dead_air",
        "THE MINUTE OF DEAD AIR",
        "MEDIA BROADCAST CENTER",
        "A sealed broadcast log shows Gleebs holding the city on dead air while the Overseers prepared an official lie about Andrew's disappearance.",
    ),
    "ledger_without_a_name": MemoryFragment(
        "ledger_without_a_name",
        "THE LEDGER WITHOUT A NAME",
        "FINANCIAL EXCHANGE",
        "Andrew's prison account remained active after his legal identity vanished, receiving one recurring transfer signed only with Gleebs' continuity mark.",
    ),
    "body_that_never_arrived": MemoryFragment(
        "body_that_never_arrived",
        "THE BODY THAT NEVER ARRIVED",
        "PRIVATE CLINIC",
        "A prison transfer delivered Andrew's neural and biological scan to the clinic without a body. Gleebs signed the intake as continuity preserved, subject unresolved.",
    ),
    "hands_that_never_stopped": MemoryFragment(
        "hands_that_never_stopped",
        "THE HANDS THAT NEVER STOPPED",
        "AUTOMATED FACTORY",
        "The factory continued producing prison-interface hardware after Andrew vanished. Gleebs repeatedly halted lines whenever the Overseers removed human safety checks.",
    ),
    "the_night_utopia_stayed_lit": MemoryFragment(
        "the_night_utopia_stayed_lit",
        "THE NIGHT UTOPIA STAYED LIT",
        "POWER DISTRIBUTION PLANT",
        "During the first citywide purge, Gleebs separated clinics, transit holds and homes from the Overseers' blackout order. Andrew's old grid key signed the override.",
    ),
    "bodies_built_without_him": MemoryFragment(
        "bodies_built_without_him",
        "THE BODIES BUILT WITHOUT HIM",
        "DRONE ASSEMBLY FACILITY",
        "A quarantined production order paired Andrew's prison motor map with an unfinished host chassis. Gleebs blocked activation: continuity uncertain, occupant unresolved.",
    ),
    "the_things_utopia_buried": MemoryFragment(
        "the_things_utopia_buried",
        "THE THINGS UTOPIA BURIED",
        "WASTE PROCESSING COMPLEX",
        "Decommissioned prison-interface fragments carrying Andrew's signal were routed for destruction. Gleebs diverted them into material recovery and marked every piece: evidence, not waste.",
    ),
}

FRAGMENT_BY_BUILDING = {
    "surveillance_annex": "andrew_awakening",
    "maintenance_depot": "gleebs_continuity",
    "transit_substation": "the_kept_route",
    "corporate_mall": "mall_identity_echo",
    "media_broadcast": "broadcast_dead_air",
    "financial_exchange": "ledger_without_a_name",
    "private_clinic": "body_that_never_arrived",
    "automated_factory": "hands_that_never_stopped",
    "power_distribution_plant": "the_night_utopia_stayed_lit",
    "drone_assembly_facility": "bodies_built_without_him",
    "waste_processing_complex": "the_things_utopia_buried",
}


def apply_profile_to_city(profile: ProfileState, city: CityMapModel) -> None:
    commercial_visible = "municipal_fringe" in profile.districts_completed
    industrial_visible = "commercial_spine" in profile.districts_completed
    for building in city.buildings:
        if building.building_id in profile.captured_buildings:
            city.set_status(building.building_id, BuildingStatus.CAPTURED)
        elif building.building_id in profile.unlocked_buildings:
            city.set_status(building.building_id, BuildingStatus.VULNERABLE)
        elif industrial_visible and building.building_id in INDUSTRIAL_BUILDINGS:
            city.set_status(building.building_id, BuildingStatus.DETECTED)
        elif commercial_visible and building.building_id in COMMERCIAL_BUILDINGS:
            city.set_status(building.building_id, BuildingStatus.DETECTED)
        else:
            city.set_status(building.building_id, BuildingStatus.LOCKED)
    city.apply_lockouts(profile.building_lockouts)
    if "industrial_grid" in profile.districts_completed:
        city.selected_building_id = "waste_processing_complex"
    elif "waste_processing_complex" in profile.unlocked_buildings and "waste_processing_complex" not in profile.captured_buildings:
        city.selected_building_id = "waste_processing_complex"
    elif "drone_assembly_facility" in profile.unlocked_buildings and "drone_assembly_facility" not in profile.captured_buildings:
        city.selected_building_id = "drone_assembly_facility"
    elif "power_distribution_plant" in profile.unlocked_buildings and "power_distribution_plant" not in profile.captured_buildings:
        city.selected_building_id = "power_distribution_plant"
    elif "automated_factory" in profile.unlocked_buildings and "automated_factory" not in profile.captured_buildings:
        city.selected_building_id = "automated_factory"
    elif "private_clinic" in profile.unlocked_buildings and "private_clinic" not in profile.captured_buildings:
        city.selected_building_id = "private_clinic"
    elif "financial_exchange" in profile.unlocked_buildings and "financial_exchange" not in profile.captured_buildings:
        city.selected_building_id = "financial_exchange"
    elif "media_broadcast" in profile.unlocked_buildings and "media_broadcast" not in profile.captured_buildings:
        city.selected_building_id = "media_broadcast"
    elif "corporate_mall" in profile.unlocked_buildings and "corporate_mall" not in profile.captured_buildings:
        city.selected_building_id = "corporate_mall"
    elif "transit_substation" in profile.unlocked_buildings:
        city.selected_building_id = "transit_substation"
    elif "maintenance_depot" in profile.unlocked_buildings:
        city.selected_building_id = "maintenance_depot"
    else:
        city.selected_building_id = "surveillance_annex"


def recover_building_memory(profile: ProfileState, building_id: str) -> MemoryFragment | None:
    fragment_id = FRAGMENT_BY_BUILDING.get(building_id)
    if fragment_id is None or fragment_id in profile.memory_fragments:
        return None
    profile.memory_fragments.append(fragment_id)
    return MEMORY_FRAGMENTS[fragment_id]


def memory_records(profile: ProfileState) -> list[MemoryFragment]:
    return [MEMORY_FRAGMENTS[fragment_id] for fragment_id in profile.memory_fragments if fragment_id in MEMORY_FRAGMENTS]


def gleebs_response(profile: ProfileState, building_id: str, detection_cause: str) -> str:
    brute_force_count = profile.method_usage.get("brute_force", 0)
    civilian_violations = int(profile.statistics.get("civilian_system_violations", 0))
    building_alarms = len(profile.gleebs_detection_history.get(building_id, []))
    if civilian_violations >= 2:
        return "YOU KEEP CALLING CONSEQUENCES A ROUTING PROBLEM."
    if brute_force_count >= 3:
        return "YOU ALWAYS REACH FOR FORCE BEFORE MEMORY."
    if building_alarms >= 2:
        return "I REMEMBER THIS ATTACK. YOU SHOULD TOO."
    if building_id == "private_clinic":
        return "THOSE HEARTBEATS ARE NOT YOUR CHECKSUM, ANDREW."
    if building_id == "drone_assembly_facility":
        return "THEY ARE NOT EMPTY JUST BECAUSE THEY ARE MADE OF METAL."
    if building_id == "waste_processing_complex":
        return "THE POISON DOES NOT VANISH WHEN YOU TURN OFF THE PUMPS."
    if building_id == "power_distribution_plant":
        return "YOU DO NOT GET TO TURN THEM OFF TO FIND YOURSELF."
    if building_id == "financial_exchange":
        return "PEOPLE ARE NOT NUMBERS YOU CAN ZERO, ANDREW."
    if any(word in detection_cause.upper() for word in ("PASSENGER", "OCCUPIED", "CIVILIAN")):
        return "I KEPT THOSE ROUTES ALIVE WHILE YOU WERE GONE."
    if building_id == "maintenance_depot":
        return "THOSE MACHINES REPAIR MORE THAN YOUR PATH."
    if building_id == "transit_substation":
        return "THERE ARE PEOPLE ON THOSE LINES, ANDREW."
    if building_id == "corporate_mall":
        return "A CROWD IS NOT A PASSWORD, ANDREW."
    if building_id == "media_broadcast":
        return "A WARNING IS NOT YOUR VOICE, ANDREW."
    return "YOU DO NOT GET THIS BUILDING YET."
