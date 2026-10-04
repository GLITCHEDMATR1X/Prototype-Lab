"""Authoritative campaign, run, and mission state for Entropy.

Pass 25 turns the former endless Relic Core loop into a complete expedition:
HOME -> emergency ship recovery -> six Data Fragments -> Gleebs delivery.
Legacy fragment fields stay serialized so older saves still migrate safely.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Dict, Iterable, List, Optional

from collapse_rules import stage_for_remaining
from expedition_identity import archive_site_label, archive_slot, best_site_candidates, world_profile


DATA_FRAGMENTS_REQUIRED = 6
CAMPAIGN_HOME = "home"
CAMPAIGN_SHIP_RECOVERY = "ship_recovery"
CAMPAIGN_EXPEDITION = "expedition"
CAMPAIGN_DELIVERY = "delivery"
CAMPAIGN_COMPLETE = "complete"
SHIP_BOOT_SEQUENCE = ("power", "storage", "fuel", "navigation", "cockpit")
CAMPAIGN_INTRO_REVISION = 1
GOAL_ACTIVE = "active"
GOAL_SECURED = "secured"
GOAL_MISSED = "missed"
GOAL_CARRYING = "carrying"
GOAL_INACTIVE = "inactive"

HAZARD_FAMILY_BY_STYLE = {
    "desert": "HEAT",
    "volcanic": "HEAT",
    "rust": "HEAT",
    "ice": "COLD",
    "salt": "COLD",
    "storm": "COLD",
    "jungle": "BIOLOGICAL",
    "fungal": "BIOLOGICAL",
    "oceanic": "BIOLOGICAL",
    "crystal": "ANOMALOUS",
    "abyss": "ANOMALOUS",
    "roseglass": "ANOMALOUS",
}

def legacy_save_needs_home_prologue(data: Optional[dict]) -> bool:
    """Return True for an impossible zero-progress expedition that skipped HOME.

    Entropy saves outside the shipping folder, so an older local profile can
    survive many package upgrades.  Pass 31 originally required an old
    ``campaign_intro_revision`` before rerouting a zero-progress expedition to
    HOME.  A profile written by a newer build could therefore be stamped with
    the current revision while still containing the old impossible state:
    expedition phase, zero Data Fragments, and no completed ship boot.

    In the real campaign an expedition cannot legitimately exist before the
    HOME evacuation and the complete five-step ship boot.  Treat an expedition
    with zero secured Data Fragments and an incomplete boot sequence as the
    migration signal regardless of intro revision.  A fully booted zero-fragment
    expedition and every save with real fragment progress remain resumable.
    """
    if not isinstance(data, dict):
        return False
    phase = str(data.get("campaign_phase", CAMPAIGN_EXPEDITION))
    completed_boot = {
        str(v) for v in (data.get("ship_boot_completed", ()) or ())
        if str(v) in SHIP_BOOT_SEQUENCE
    }
    boot_complete = all(step in completed_boot for step in SHIP_BOOT_SEQUENCE)
    return (
        phase == CAMPAIGN_EXPEDITION
        and int(data.get("fragments_secured_total", 0) or 0) <= 0
        and not boot_complete
        and not bool(data.get("gleebs_transmission_complete", False))
    )


ROLE_LABELS = {
    "home": "EMERGENCY SUPPLY CACHE",
    "fragment": "DATA FRAGMENT SIGNAL",
    "fuel": "FUEL SIGNATURE",
    "salvage": "SALVAGE TRACE",
    "survey": "LOW-VALUE SURVEY",
}


@dataclass
class PlanetMissionSignal:
    planet_index: int
    role: str
    style: str
    hazard_family: str

    @property
    def label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role.upper())

    @property
    def planet_label(self) -> str:
        return f"P{self.planet_index + 1} {self.style.upper()}"


@dataclass
class MissionState:
    """Single source of truth for one Entropy expedition."""

    run_started: bool = False
    system_index: int = 1
    system_seed: int = 0
    system_planet_count: int = 0
    target_planet_index: int = -1
    target_style: str = "unknown"
    target_hazard_family: str = "UNKNOWN"
    phase: str = "home_scavenge"
    collapse_state: str = "STABLE"
    collapse_remaining: float = 0.0
    current_planet_index: Optional[int] = None
    completed_objectives: List[str] = field(default_factory=list)
    signals: Dict[int, PlanetMissionSignal] = field(default_factory=dict)

    # Pass 25 campaign spine.
    campaign_phase: str = CAMPAIGN_HOME
    data_fragments_required: int = DATA_FRAGMENTS_REQUIRED
    ship_boot_completed: List[str] = field(default_factory=list)
    gleebs_transmission_complete: bool = False
    campaign_intro_revision: int = CAMPAIGN_INTRO_REVISION

    # Per-system goal resolution. Warp to a NEW system is locked until the
    # current fragment has been secured or has become irretrievable.
    system_goal_outcome: str = GOAL_ACTIVE
    missed_goals_total: int = 0

    # Legacy-compatible recovery state. ``fragments_secured_total`` is now the
    # authoritative Data Fragment total; the old name remains in the save schema.
    target_surface_seed: Optional[int] = None
    target_structure_seed: Optional[int] = None
    target_structure_title: str = "ABANDONED DATA SITE"
    inside_target_ruin: bool = False
    carrying_fragment: bool = False
    fragment_deposited: bool = False
    fragments_secured_total: int = 0
    surface_target_distance: Optional[float] = None

    # Each system may expose one deterministic resource cache.
    resource_claimed_planets: List[int] = field(default_factory=list)

    @property
    def data_fragments_secured(self) -> int:
        return max(0, int(self.fragments_secured_total))

    @property
    def data_fragments_remaining(self) -> int:
        return max(0, int(self.data_fragments_required) - self.data_fragments_secured)

    @property
    def current_archive_slot(self) -> int:
        return archive_slot(
            self.data_fragments_secured,
            self.data_fragments_required,
            current_already_secured=bool(self.fragment_deposited or self.system_goal_outcome == GOAL_SECURED),
        )

    @property
    def current_archive_style(self) -> str:
        style = str(self.target_style or "unknown").lower()
        if style not in ("", "unknown"):
            return style
        # A carried fragment may outlive its destroyed target world.  The
        # per-system signal table survives target retirement, so retain the
        # fragment's world identity until the next system begins.
        for signal in self.signals.values():
            if str(getattr(signal, "role", "")) == "fragment":
                signal_style = str(getattr(signal, "style", "unknown")).lower()
                if signal_style not in ("", "unknown"):
                    return signal_style
        return "unknown"

    @property
    def current_archive_record(self) -> str:
        return world_profile(self.current_archive_style).record_name

    @property
    def current_archive_world(self) -> str:
        return world_profile(self.current_archive_style).world_name

    @property
    def is_home_phase(self) -> bool:
        return self.campaign_phase == CAMPAIGN_HOME

    @property
    def is_ship_recovery_phase(self) -> bool:
        return self.campaign_phase == CAMPAIGN_SHIP_RECOVERY

    @property
    def is_expedition_phase(self) -> bool:
        return self.campaign_phase == CAMPAIGN_EXPEDITION

    @property
    def is_delivery_phase(self) -> bool:
        return self.campaign_phase == CAMPAIGN_DELIVERY

    @property
    def campaign_complete(self) -> bool:
        return self.campaign_phase == CAMPAIGN_COMPLETE or bool(self.gleebs_transmission_complete)

    @property
    def ship_boot_next_step(self) -> Optional[str]:
        done = set(self.ship_boot_completed)
        for step in SHIP_BOOT_SEQUENCE:
            if step not in done:
                return step
        return None

    @property
    def ship_boot_ready_for_cockpit(self) -> bool:
        return self.ship_boot_next_step == "cockpit"

    @property
    def warp_unlocked(self) -> bool:
        """New-system warp is a reward for resolving the current system goal."""
        if self.is_home_phase or self.is_ship_recovery_phase or self.is_delivery_phase or self.campaign_complete:
            return False
        return self.system_goal_outcome in (GOAL_SECURED, GOAL_MISSED)

    @property
    def warp_lock_reason(self) -> str:
        if self.warp_unlocked:
            return "HYPERDRIVE AVAILABLE"
        if self.is_ship_recovery_phase:
            return "RESTORE SHIP SYSTEMS BEFORE HYPERDRIVE"
        if self.is_delivery_phase:
            return "ALL DATA RECOVERED — CONTACT GLEEBS"
        if self.campaign_complete:
            return "EXPEDITION COMPLETE"
        if self.system_goal_outcome == GOAL_CARRYING or self.carrying_fragment:
            return "SECURE THE DATA FRAGMENT IN SHIP STORAGE"
        if self.system_goal_outcome == GOAL_ACTIVE:
            return "RESOLVE THE DATA FRAGMENT SIGNAL OR SURVIVE SYSTEM COLLAPSE"
        return "HYPERDRIVE LOCKED"

    def complete_ship_boot_step(self, step: str) -> bool:
        step = str(step).lower().strip()
        expected = self.ship_boot_next_step
        if expected is None or step != expected:
            return False
        if step not in self.ship_boot_completed:
            self.ship_boot_completed.append(step)
        if step == "cockpit":
            self.campaign_phase = CAMPAIGN_EXPEDITION
            self.system_goal_outcome = GOAL_ACTIVE
            self.phase = "locate_fragment"
            if "expedition_launched" not in self.completed_objectives:
                self.completed_objectives.append("expedition_launched")
        else:
            self.phase = f"ship_boot_{self.ship_boot_next_step or 'complete'}"
        return True

    def begin_ship_recovery(self) -> None:
        self.campaign_phase = CAMPAIGN_SHIP_RECOVERY
        self.phase = "ship_boot_power"
        self.current_planet_index = None
        self.carrying_fragment = False
        self.fragment_deposited = False
        self.ship_boot_completed = []
        if "home_evacuated" not in self.completed_objectives:
            self.completed_objectives.append("home_evacuated")

    def transmit_to_gleebs(self) -> bool:
        if self.data_fragments_secured < self.data_fragments_required:
            return False
        self.gleebs_transmission_complete = True
        self.campaign_phase = CAMPAIGN_COMPLETE
        self.phase = "complete"
        if "gleebs_transmission_complete" not in self.completed_objectives:
            self.completed_objectives.append("gleebs_transmission_complete")
        return True

    def begin_system(self, system, system_index: int) -> None:
        """Assign this system's single visible world to the current campaign phase."""
        self.system_index = int(system_index)
        self.system_seed = int(system.seed)
        self.system_planet_count = len(system.planets)
        self.current_planet_index = None
        self.collapse_state = "STABLE"
        self.collapse_remaining = 0.0
        self.completed_objectives = []
        self.signals = {}
        self.target_surface_seed = None
        self.target_structure_seed = None
        self.target_structure_title = "ABANDONED DATA SITE"
        self.inside_target_ruin = False
        self.carrying_fragment = False
        self.fragment_deposited = False
        self.surface_target_distance = None
        self.resource_claimed_planets = []
        self.system_goal_outcome = GOAL_INACTIVE if (self.is_home_phase or self.is_ship_recovery_phase or self.is_delivery_phase or self.campaign_complete) else GOAL_ACTIVE

        if self.is_home_phase:
            self.phase = "home_scavenge"
        elif self.is_ship_recovery_phase:
            self.phase = f"ship_boot_{self.ship_boot_next_step or 'cockpit'}"
        elif self.is_delivery_phase:
            self.phase = "deliver_to_gleebs"
        elif self.campaign_complete:
            self.phase = "complete"
        else:
            self.phase = "locate_fragment"

        if not system.planets:
            self.target_planet_index = -1
            self.target_style = "unknown"
            self.target_hazard_family = "UNKNOWN"
            if self.is_expedition_phase:
                self.system_goal_outcome = GOAL_MISSED
            return

        indices = list(range(len(system.planets)))
        self.target_planet_index = indices[0]
        primary_role = "home" if self.is_home_phase else "fragment"
        role_by_index = {idx: (primary_role if idx == self.target_planet_index else "survey") for idx in indices}

        for idx, planet in enumerate(system.planets):
            style = str(getattr(planet, "style", "unknown"))
            family = HAZARD_FAMILY_BY_STYLE.get(style, "UNKNOWN")
            role = role_by_index[idx]
            signal = PlanetMissionSignal(idx, role, style, family)
            self.signals[idx] = signal
            planet.mission_role = role
            planet.signal_label = signal.label
            planet.hazard_family = family
            planet.is_fragment_target = bool(role == "fragment")

        target = self.signals[self.target_planet_index]
        self.target_style = target.style
        self.target_hazard_family = target.hazard_family

    def apply_to_system(self, system) -> None:
        if int(getattr(system, "seed", -1)) != self.system_seed or len(system.planets) != self.system_planet_count:
            self.begin_system(system, self.system_index)
            return
        for idx, planet in enumerate(system.planets):
            signal = self.signals.get(idx)
            if signal is None:
                continue
            planet.mission_role = signal.role
            planet.signal_label = signal.label
            planet.hazard_family = signal.hazard_family
            planet.is_fragment_target = signal.role == "fragment"

    def mark_run_started(self) -> None:
        self.run_started = True

    def signal_for_planet(self, planet_index: Optional[int] = None) -> Optional[PlanetMissionSignal]:
        if planet_index is None:
            planet_index = self.current_planet_index
        if planet_index is None:
            return None
        return self.signals.get(int(planet_index))

    def resource_role(self, planet_index: Optional[int] = None) -> Optional[str]:
        signal = self.signal_for_planet(planet_index)
        if signal is None or signal.role not in ("home", "fuel", "salvage"):
            return None
        return signal.role

    def resource_claimed(self, planet_index: Optional[int] = None) -> bool:
        if planet_index is None:
            planet_index = self.current_planet_index
        if planet_index is None:
            return False
        return int(planet_index) in {int(v) for v in self.resource_claimed_planets}

    def claim_resource(self, planet_index: Optional[int] = None) -> Optional[str]:
        if planet_index is None:
            planet_index = self.current_planet_index
        role = self.resource_role(planet_index)
        if role is None or planet_index is None or self.resource_claimed(planet_index):
            return None
        self.resource_claimed_planets.append(int(planet_index))
        objective = "home_supply_secured" if role == "home" else "resource_cache_secured"
        if objective not in self.completed_objectives:
            self.completed_objectives.append(objective)
        self.phase = "home_wait_collapse" if role == "home" else "return_to_ship"
        return role

    def land_on(self, planet_index: int) -> None:
        self.current_planet_index = int(planet_index)
        self.inside_target_ruin = False
        self.surface_target_distance = None
        if self.is_home_phase:
            self.phase = "home_wait_collapse" if self.resource_claimed(planet_index) else "home_scavenge"
        elif self.current_planet_index != self.target_planet_index:
            self.phase = "optional_surface"
        elif self.fragment_deposited:
            self.phase = "return_to_ship"
        elif self.carrying_fragment:
            self.phase = "return_to_ship"
        else:
            self.phase = "locate_data_site"

    def bind_surface_target(self, surface_seed: int, structures: Iterable[object], ship_pos) -> Optional[int]:
        """Choose one stable, reachable abandoned archive on the target world."""
        if self.is_home_phase or self.is_ship_recovery_phase or self.campaign_complete:
            return None
        if self.current_planet_index != self.target_planet_index:
            return None

        structures = list(structures)
        if not structures:
            self.target_surface_seed = int(surface_seed)
            self.target_structure_seed = None
            self.target_structure_title = "NO VIABLE DATA SITE"
            return None

        valid_existing = (
            self.target_surface_seed == int(surface_seed)
            and self.target_structure_seed is not None
            and any(int(getattr(st, "seed", -1)) == int(self.target_structure_seed) for st in structures)
        )
        if valid_existing:
            return self.target_structure_seed

        sx, sy = float(ship_pos[0]), float(ship_pos[1])
        ranked = sorted(
            structures,
            key=lambda st: math.hypot(float(getattr(st, "x", sx)) - sx, float(getattr(st, "y", sy)) - sy),
        )
        preferred = [
            st for st in ranked
            if 48.0 <= math.hypot(float(getattr(st, "x", sx)) - sx, float(getattr(st, "y", sy)) - sy) <= 110.0
        ]
        pool = preferred or ranked[: max(1, min(4, len(ranked)))]
        # Pass 33: preserve the exact reachable target pool, but give each of
        # the six archive slots a different preferred existing ruin family.
        # This adds authored expedition identity without changing geometry,
        # target-distance balance, or save authority.
        slot = self.current_archive_slot
        ordered_pool = best_site_candidates(pool, slot)
        best_kind = str(getattr(ordered_pool[0], "kind", "")) if ordered_pool else ""
        kind_pool = [st for st in ordered_pool if str(getattr(st, "kind", "")) == best_kind] or ordered_pool
        rng = random.Random(self.system_seed ^ int(surface_seed) ^ 0xF16A6E ^ (slot * 0x9E37))
        chosen = kind_pool[rng.randrange(len(kind_pool))]

        self.target_surface_seed = int(surface_seed)
        self.target_structure_seed = int(getattr(chosen, "seed"))
        original_title = str(getattr(chosen, "title", "ABANDONED ARCHIVE"))
        self.target_structure_title = f"{original_title} / {archive_site_label(slot)}"
        self.phase = "locate_data_site"
        return self.target_structure_seed

    def update_surface_target_distance(self, distance: Optional[float]) -> None:
        self.surface_target_distance = None if distance is None else max(0.0, float(distance))

    def recover_surface_relic(self, structure_seed: Optional[int] = None) -> bool:
        """Recover this system's Data Fragment from the marked archive."""
        if self.is_home_phase or self.is_ship_recovery_phase or self.campaign_complete:
            return False
        if self.fragment_deposited or self.carrying_fragment:
            return False
        if self.current_planet_index != self.target_planet_index:
            return False
        if self.target_structure_seed is None:
            return False
        if structure_seed is not None and int(structure_seed) != int(self.target_structure_seed):
            return False
        self.inside_target_ruin = False
        self.carrying_fragment = False
        self.fragment_deposited = True
        self.system_goal_outcome = GOAL_SECURED
        self.fragments_secured_total = min(self.data_fragments_required, self.fragments_secured_total + 1)
        if self.fragments_secured_total >= self.data_fragments_required:
            self.campaign_phase = CAMPAIGN_DELIVERY
            self.phase = "return_to_ship_for_delivery"
        else:
            self.campaign_phase = CAMPAIGN_EXPEDITION
            self.phase = "return_to_ship"
        for objective in ("data_fragment_recovered", "fragment_deposited"):
            if objective not in self.completed_objectives:
                self.completed_objectives.append(objective)
        return True

    # Legacy ruin-flow compatibility. New gameplay stays top-down.
    def enter_structure(self, structure_seed: int, title: str = "ANCIENT RUIN") -> bool:
        is_target = (
            self.current_planet_index == self.target_planet_index
            and self.target_structure_seed is not None
            and int(structure_seed) == int(self.target_structure_seed)
        )
        self.inside_target_ruin = bool(is_target)
        if is_target and not self.carrying_fragment and not self.fragment_deposited:
            self.target_structure_title = f"{str(title)} / {archive_site_label(self.current_archive_slot)}"
            self.phase = "recover_fragment"
            if "target_ruin_entered" not in self.completed_objectives:
                self.completed_objectives.append("target_ruin_entered")
        return is_target

    def leave_structure(self) -> None:
        self.inside_target_ruin = False
        if self.fragment_deposited:
            self.phase = "return_to_ship"
        elif self.carrying_fragment:
            self.phase = "return_to_ship"
        elif self.current_planet_index == self.target_planet_index:
            self.phase = "locate_data_site"

    def recover_fragment(self, structure_seed: Optional[int] = None) -> bool:
        if self.fragment_deposited or self.carrying_fragment:
            return False
        if self.current_planet_index != self.target_planet_index:
            return False
        if self.target_structure_seed is None:
            return False
        if structure_seed is not None and int(structure_seed) != int(self.target_structure_seed):
            return False
        if not self.inside_target_ruin:
            return False
        self.carrying_fragment = True
        self.system_goal_outcome = GOAL_CARRYING
        self.phase = "return_to_ship"
        if "fragment_recovered" not in self.completed_objectives:
            self.completed_objectives.append("fragment_recovered")
        return True

    def deposit_fragment(self) -> bool:
        if not self.carrying_fragment or self.fragment_deposited:
            return False
        self.carrying_fragment = False
        self.fragment_deposited = True
        self.system_goal_outcome = GOAL_SECURED
        self.fragments_secured_total = min(self.data_fragments_required, self.fragments_secured_total + 1)
        self.campaign_phase = CAMPAIGN_DELIVERY if self.fragments_secured_total >= self.data_fragments_required else CAMPAIGN_EXPEDITION
        self.phase = "return_to_ship_for_delivery" if self.is_delivery_phase else "return_to_ship"
        if "fragment_deposited" not in self.completed_objectives:
            self.completed_objectives.append("fragment_deposited")
        return True

    def return_to_orbit(self) -> None:
        self.current_planet_index = None
        self.inside_target_ruin = False
        self.surface_target_distance = None
        if self.is_home_phase:
            self.phase = "home_scavenge"
        elif self.is_ship_recovery_phase:
            self.phase = f"ship_boot_{self.ship_boot_next_step or 'cockpit'}"
        elif self.is_delivery_phase:
            self.phase = "deliver_to_gleebs"
        elif self.fragment_deposited:
            self.phase = "return_to_ship"
        elif self.carrying_fragment:
            self.phase = "deposit_fragment"
        elif self.system_goal_outcome == GOAL_MISSED:
            self.phase = "goal_missed"
        else:
            self.phase = "locate_fragment"

    def retire_current_target(self, *, missed: bool = False, reason: str = "target_unavailable") -> bool:
        """Remove the dead-world waypoint while preserving any carried fragment.

        If the fragment never left the planet, the objective is considered missed
        and the same required fragment returns to the target pool next system.
        """
        had_target = self.target_planet_index >= 0 or self.target_structure_seed is not None
        if self.fragment_deposited:
            self.system_goal_outcome = GOAL_SECURED
        elif self.carrying_fragment:
            self.system_goal_outcome = GOAL_CARRYING
            self.phase = "deposit_fragment"
        elif missed:
            self.system_goal_outcome = GOAL_MISSED
            self.missed_goals_total = max(0, int(self.missed_goals_total)) + 1
            self.phase = "goal_missed"
            marker = f"goal_missed:{reason}"
            if marker not in self.completed_objectives:
                self.completed_objectives.append(marker)
        self.target_planet_index = -1
        self.target_style = "unknown"
        self.target_hazard_family = "UNKNOWN"
        self.target_surface_seed = None
        self.target_structure_seed = None
        self.target_structure_title = "DATA SIGNAL LOST"
        self.inside_target_ruin = False
        self.surface_target_distance = None
        return bool(had_target)

    def resolve_target_loss(self, reason: str = "planet_destroyed") -> str:
        """Resolve an objective when its planet can no longer be accessed."""
        if self.target_planet_index < 0 and self.system_goal_outcome in {GOAL_SECURED, GOAL_MISSED, GOAL_CARRYING}:
            return self.system_goal_outcome
        if self.fragment_deposited:
            self.retire_current_target(missed=False, reason=reason)
            return GOAL_SECURED
        if self.carrying_fragment:
            self.retire_current_target(missed=False, reason=reason)
            return GOAL_CARRYING
        self.retire_current_target(missed=True, reason=reason)
        return GOAL_MISSED

    def update_collapse(self, remaining: float, duration: float, triggered: bool = False, post_supernova: bool = False, blackhole: bool = False) -> None:
        self.collapse_remaining = max(0.0, float(remaining))
        if blackhole:
            self.collapse_state = "BLACK HOLE"
        elif post_supernova or triggered:
            self.collapse_state = "SUPERNOVA"
        elif duration <= 0.0:
            self.collapse_state = "UNKNOWN"
        else:
            self.collapse_state = stage_for_remaining(self.collapse_remaining, duration)

    def restore_from_dict(self, data: Optional[dict], system=None) -> bool:
        """Restore persisted state and migrate pre-Pass-25 saves safely."""
        if not isinstance(data, dict):
            return False

        self.fragments_secured_total = max(0, min(DATA_FRAGMENTS_REQUIRED, int(data.get("fragments_secured_total", self.fragments_secured_total))))
        self.data_fragments_required = DATA_FRAGMENTS_REQUIRED

        # Old RC1 saves had no campaign_phase. A started old save resumes as an
        # expedition rather than being unexpectedly sent back to HOME.
        if "campaign_phase" in data:
            phase = str(data.get("campaign_phase", CAMPAIGN_HOME))
        else:
            phase = CAMPAIGN_EXPEDITION if bool(data.get("run_started", False)) else CAMPAIGN_HOME
        if phase not in {CAMPAIGN_HOME, CAMPAIGN_SHIP_RECOVERY, CAMPAIGN_EXPEDITION, CAMPAIGN_DELIVERY, CAMPAIGN_COMPLETE}:
            phase = CAMPAIGN_EXPEDITION
        if self.fragments_secured_total >= DATA_FRAGMENTS_REQUIRED and phase not in (CAMPAIGN_COMPLETE,):
            phase = CAMPAIGN_DELIVERY
        self.campaign_phase = phase
        self.ship_boot_completed = [str(v) for v in data.get("ship_boot_completed", ()) if str(v) in SHIP_BOOT_SEQUENCE]
        self.gleebs_transmission_complete = bool(data.get("gleebs_transmission_complete", False))
        self.campaign_intro_revision = max(0, int(data.get("campaign_intro_revision", 0) or 0))
        self.system_goal_outcome = str(data.get("system_goal_outcome", GOAL_ACTIVE))
        if self.system_goal_outcome not in {GOAL_ACTIVE, GOAL_SECURED, GOAL_MISSED, GOAL_CARRYING, GOAL_INACTIVE}:
            self.system_goal_outcome = GOAL_ACTIVE
        self.missed_goals_total = max(0, int(data.get("missed_goals_total", 0) or 0))
        if self.gleebs_transmission_complete:
            self.campaign_phase = CAMPAIGN_COMPLETE

        if system is not None:
            if int(data.get("system_seed", -1)) != int(getattr(system, "seed", -2)):
                return False
            if int(data.get("system_planet_count", -1)) != len(getattr(system, "planets", ())):
                return False

        if system is not None and getattr(system, "planets", None):
            self.target_planet_index = 0
            self.signals = {}
            primary_role = "home" if self.is_home_phase else "fragment"
            for idx, planet in enumerate(system.planets):
                style = str(getattr(planet, "style", "unknown"))
                family = HAZARD_FAMILY_BY_STYLE.get(style, "UNKNOWN")
                role = primary_role if idx == self.target_planet_index else "survey"
                signal = PlanetMissionSignal(idx, role, style, family)
                self.signals[idx] = signal
                planet.mission_role = role
                planet.signal_label = signal.label
                planet.hazard_family = family
                planet.is_fragment_target = role == "fragment"
            target = self.signals[self.target_planet_index]
            self.target_style = target.style
            self.target_hazard_family = target.hazard_family

        self.run_started = bool(data.get("run_started", self.run_started))
        self.completed_objectives = [str(v) for v in data.get("completed_objectives", ())]
        self.target_surface_seed = data.get("target_surface_seed")
        self.target_structure_seed = data.get("target_structure_seed")
        self.target_structure_title = str(data.get("target_structure_title", self.target_structure_title))
        self.carrying_fragment = bool(data.get("carrying_fragment", False))
        self.fragment_deposited = bool(data.get("fragment_deposited", False))
        if self.fragment_deposited:
            self.system_goal_outcome = GOAL_SECURED
        elif self.carrying_fragment:
            self.system_goal_outcome = GOAL_CARRYING
        elif self.is_expedition_phase and self.system_goal_outcome == GOAL_INACTIVE:
            self.system_goal_outcome = GOAL_ACTIVE
        self.campaign_intro_revision = CAMPAIGN_INTRO_REVISION
        saved_target_index = int(data.get("target_planet_index", self.target_planet_index) or 0)
        if saved_target_index < 0 and self.system_goal_outcome in {GOAL_SECURED, GOAL_MISSED, GOAL_CARRYING}:
            self.target_planet_index = -1
            self.target_style = "unknown"
            self.target_hazard_family = "UNKNOWN"
            self.target_surface_seed = None
            self.target_structure_seed = None
            self.target_structure_title = "DATA SIGNAL LOST"
        self.resource_claimed_planets = sorted({int(v) for v in data.get("resource_claimed_planets", ()) if isinstance(v, (int, float, str)) and str(v).lstrip('-').isdigit()})
        self.current_planet_index = None
        self.inside_target_ruin = False
        self.surface_target_distance = None

        if self.campaign_complete:
            self.phase = "complete"
        elif self.is_home_phase:
            self.phase = "home_wait_collapse" if self.resource_claimed(self.target_planet_index) else "home_scavenge"
        elif self.is_ship_recovery_phase:
            self.phase = f"ship_boot_{self.ship_boot_next_step or 'cockpit'}"
        elif self.is_delivery_phase:
            self.phase = "deliver_to_gleebs"
        elif self.fragment_deposited:
            self.phase = "return_to_ship"
        elif self.carrying_fragment:
            self.phase = "deposit_fragment"
        else:
            self.phase = "locate_fragment"
        return True

    @property
    def system_goal_complete(self) -> bool:
        """Pass 25 removes objective auto-warp; the player owns departure timing."""
        return False

    @property
    def target_signal(self) -> Optional[PlanetMissionSignal]:
        return self.signals.get(self.target_planet_index)

    def objective_title(self, context: str = "space") -> str:
        if self.campaign_complete:
            return "EXPEDITION COMPLETE — DATA DELIVERED TO GLEEBS"
        if self.is_home_phase:
            if self.resource_claimed(self.target_planet_index):
                return "HOME IS LOST — STAY ALIVE UNTIL EVACUATION"
            return "HOME — RECOVER EMERGENCY SUPPLIES"
        if self.is_ship_recovery_phase:
            step = (self.ship_boot_next_step or "cockpit").upper()
            return f"RESTORE THE SHIP — {step}"
        if self.is_delivery_phase:
            return "RETURN TO THE COCKPIT — CONTACT GLEEBS"
        if self.system_goal_outcome == GOAL_MISSED:
            return "DATA SIGNAL LOST — HYPERDRIVE AVAILABLE"
        if self.target_planet_index < 0:
            return "NO VIABLE DATA SIGNAL"
        if self.fragment_deposited:
            return "DATA FRAGMENT SECURED — RETURN TO SHIP"
        if context == "interior":
            return f"ARCHIVE {self.current_archive_slot}/{self.data_fragments_required} — {self.current_archive_record}"
        if context in ("surface", "ruin"):
            return f"ARCHIVE {self.current_archive_slot}/{self.data_fragments_required} — RECOVER {self.current_archive_record}"
        return f"ARCHIVE {self.current_archive_slot}/{self.data_fragments_required} — {self.current_archive_record}"

    def objective_detail(self, context: str = "space", target_distance: Optional[float] = None) -> str:
        target = self.target_signal
        if self.campaign_complete:
            return "THE ABANDONED-WORLD ARCHIVE HAS BEEN TRANSFERRED INTO MATRIXCORE CUSTODY."
        if self.is_home_phase:
            if self.resource_claimed(self.target_planet_index):
                return "SUPPLIES SECURED IN FIELD PACK  •  SYSTEM COLLAPSE WILL TRIGGER EMERGENCY TRANSFER"
            distance = "" if self.surface_target_distance is None else f"  •  {self.surface_target_distance:03.0f}m"
            return f"LOCATE THE EMERGENCY CACHE{distance}  •  RECOVER FUEL CELLS + SALVAGE BEFORE SUPERNOVA"
        if self.is_ship_recovery_phase:
            steps = {
                "power": "RESTORE AUXILIARY POWER AT THE POWER RELAY",
                "storage": "STOW YOUR FIELD PACK AT CARGO STORAGE",
                "fuel": "PROCESS STORED FUEL CELLS AT THE FUEL PORT",
                "navigation": "INITIALIZE THE NAVIGATION ARRAY",
                "cockpit": "PROCEED TO THE COCKPIT AND BEGIN THE DATA EXPEDITION",
            }
            return steps.get(self.ship_boot_next_step or "cockpit", "PROCEED TO THE COCKPIT")
        if self.is_delivery_phase:
            return f"ALL {self.data_fragments_required} FRAGMENTS RECOVERED  •  COCKPIT LINK TARGET: GLEEBS"
        if target is None:
            if self.system_goal_outcome == GOAL_MISSED:
                return "TARGET WORLD LOST  •  REQUIRED DATA RETURNS TO THE NEXT SYSTEM  •  HYPERDRIVE AVAILABLE"
            if self.system_goal_outcome == GOAL_CARRYING:
                return "TARGET WORLD LOST  •  DATA IS IN YOUR POSSESSION  •  SECURE IT IN SHIP STORAGE"
            return "No viable data signal in this system."
        if self.fragment_deposited:
            return f"DATA ARCHIVE  {self.data_fragments_secured}/{self.data_fragments_required}  •  RETURN TO SHIP, REFUEL, THEN CHOOSE WHEN TO LEAVE"
        if context in ("surface", "ruin"):
            distance = "" if self.surface_target_distance is None else f"  •  {self.surface_target_distance:03.0f}m"
            return f"{self.current_archive_world}  •  {self.target_structure_title.upper()}{distance}  •  PRESS E AT THE LANDMARK"
        if context == "interior":
            return f"ARCHIVE STATUS  {self.data_fragments_secured}/{self.data_fragments_required}  •  REFUEL / STORE / UPGRADE / COCKPIT"
        distance = ""
        if target_distance is not None:
            distance = f"  •  {max(0.0, target_distance) / 1000.0:05.1f}k DIST"
        return f"TARGET {target.planet_label}  •  {target.hazard_family} HAZARD{distance}"

    def signal_summary(self) -> List[str]:
        order = ("home", "fragment", "fuel", "salvage", "survey")
        rows = []
        for role in order:
            for idx in sorted(self.signals):
                signal = self.signals[idx]
                if signal.role != role:
                    continue
                if role == "fragment" and self.fragment_deposited:
                    suffix = "  [RECOVERED]"
                elif role in ("home", "fuel", "salvage") and self.resource_claimed(idx):
                    suffix = "  [RECOVERED]"
                else:
                    suffix = ""
                rows.append(f"{signal.planet_label:<18} {signal.label}{suffix}")
        return rows

    def to_dict(self) -> dict:
        return {
            "run_started": bool(self.run_started),
            "campaign_phase": self.campaign_phase,
            "data_fragments_required": int(self.data_fragments_required),
            "ship_boot_completed": list(self.ship_boot_completed),
            "gleebs_transmission_complete": bool(self.gleebs_transmission_complete),
            "campaign_intro_revision": int(self.campaign_intro_revision),
            "system_goal_outcome": str(self.system_goal_outcome),
            "missed_goals_total": int(self.missed_goals_total),
            "system_index": int(self.system_index),
            "system_seed": int(self.system_seed),
            "system_planet_count": int(self.system_planet_count),
            "target_planet_index": int(self.target_planet_index),
            "target_style": self.target_style,
            "target_hazard_family": self.target_hazard_family,
            "phase": self.phase,
            "collapse_state": self.collapse_state,
            "collapse_remaining": float(self.collapse_remaining),
            "current_planet_index": self.current_planet_index,
            "completed_objectives": list(self.completed_objectives),
            "target_surface_seed": self.target_surface_seed,
            "target_structure_seed": self.target_structure_seed,
            "target_structure_title": self.target_structure_title,
            "inside_target_ruin": bool(self.inside_target_ruin),
            "carrying_fragment": bool(self.carrying_fragment),
            "fragment_deposited": bool(self.fragment_deposited),
            "fragments_secured_total": int(self.fragments_secured_total),
            "resource_claimed_planets": [int(v) for v in self.resource_claimed_planets],
            "signals": {
                str(idx): {
                    "planet_index": signal.planet_index,
                    "role": signal.role,
                    "style": signal.style,
                    "hazard_family": signal.hazard_family,
                }
                for idx, signal in self.signals.items()
            },
        }
