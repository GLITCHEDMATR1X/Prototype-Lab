from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

import pygame

from game.hacking import HackOutcome, METHOD_BY_ID, METHODS


class StageCamera(Enum):
    EXTERIOR = auto()
    OPERATIONS = auto()
    CORE = auto()
    YARD = auto()
    REPAIR = auto()
    DRONE = auto()
    DEPOT_CORE = auto()
    PLATFORM = auto()
    SERVICE_CONTROL = auto()
    ROUTING_CORE = auto()
    UPLINK = auto()
    MALL_ATRIUM = auto()
    AD_GRID = auto()
    IDENTITY_GALLERY = auto()
    MALL_CORE = auto()
    BROADCAST_INGEST = auto()
    ALERT_ROUTER = auto()
    LIVE_STUDIO = auto()
    BROADCAST_CORE = auto()
    SETTLEMENT_FLOOR = auto()
    CREDENTIAL_CHAIN = auto()
    AUDIT_VAULT = auto()
    CLEARING_CORE = auto()
    TRIAGE_INTAKE = auto()
    MEDICAL_IDENTITY = auto()
    LIFE_SUPPORT = auto()
    BIOLOGICAL_ARCHIVE = auto()
    MATERIAL_INTAKE = auto()
    ASSEMBLY_LINE = auto()
    SAFETY_CONTROLLER = auto()
    FACTORY_CORE = auto()
    LOAD_DISPATCH = auto()
    SWITCHYARD = auto()
    CRITICAL_FEEDERS = auto()
    DISTRIBUTION_CORE = auto()
    PARTS_REGISTRY = auto()
    CALIBRATION_GANTRY = auto()
    IDENTITY_IMPRINT = auto()
    FLIGHT_CONTROL_CORE = auto()
    RECEIVING_SCALE = auto()
    SORTING_CONVEYOR = auto()
    LEACHATE_CONTROL = auto()
    RECOVERY_CORE = auto()


ANNEX_RULES = {
    StageCamera.EXTERIOR: {
        "clues": ("SERVICE WINDOW ACTIVE 02:10–02:25", "REMOTE ADMINISTRATION DISABLED"),
        "methods": {
            "maintenance_bypass": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.NOISY,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.OPERATIONS: {
        "clues": ("LIGHT BUS REPEATS A 12-SECOND COMMAND", "BACKUP POWER REPORTS NOMINAL"),
        "methods": {
            "signal_replay": HackOutcome.CLEAN,
            "maintenance_bypass": HackOutcome.NOISY,
            "credential_spoof": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.CORE: {
        "clues": ("CAPTURE TOKEN MATCHES ANNEX DIRECTOR", "CORE ACCEPTS ONE LIVE IDENTITY HANDSHAKE"),
        "methods": {
            "credential_spoof": HackOutcome.CLEAN,
            "signal_replay": HackOutcome.NOISY,
            "maintenance_bypass": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
}

DEPOT_RULES = {
    StageCamera.YARD: {
        "clues": ("DELIVERY GATE ENTERS SERVICE MODE EVERY 20 SECONDS", "REMOTE MOTOR CONTROL IS DISABLED"),
        "methods": {
            "maintenance_bypass": HackOutcome.CLEAN,
            "signal_replay": HackOutcome.NOISY,
            "credential_spoof": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.NOISY,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.REPAIR: {
        "clues": ("DRONE RACK ACCEPTS ACTIVE TECHNICIAN TOKENS", "UNIT D-04 IS IN DIAGNOSTIC HOLD"),
        "methods": {
            "credential_spoof": HackOutcome.CLEAN,
            "maintenance_bypass": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.DRONE: {
        "clues": ("ISOLATED CORE HAS NO WIRELESS ROUTE", "SERVICE PORT REQUIRES PHYSICAL CONTACT"),
        "methods": {
            "maintenance_bypass": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.REJECTED,
            "signal_replay": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.DEPOT_CORE: {
        "clues": ("EMERGENCY REPAIR QUEUE REMAINS ACTIVE", "CORE AUTHORIZES LOCAL DRONE SERVICE ID"),
        "methods": {
            "maintenance_bypass": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
}

TRANSIT_RULES = {
    StageCamera.PLATFORM: {
        "clues": ("CARS 04, 07 AND 12 REPORT OCCUPIED", "CLEARANCE CHIME REPEATS BEFORE EACH SAFE HOLD"),
        "methods": {
            "signal_replay": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "maintenance_bypass": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.SERVICE_CONTROL: {
        "clues": ("ROUTING TECHNICIAN OPENS A 30-SECOND SERVICE WINDOW", "PASSENGER LINES REMAIN ON AUTOMATIC HOLD"),
        "methods": {
            "maintenance_bypass": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.ROUTING_CORE: {
        "clues": ("BACKUP BATTERY IS ONLINE", "LOCAL DIAGNOSTIC CABLE HAS AN ACTIVE SESSION"),
        "methods": {
            "maintenance_bypass": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.UPLINK: {
        "clues": ("ROOFTOP UPLINK ACCEPTS TRANSIT AUTHORITY TOKENS", "DISTRICT RELAY REQUIRES ONE LIVE IDENTITY HANDSHAKE"),
        "methods": {
            "credential_spoof": HackOutcome.CLEAN,
            "signal_replay": HackOutcome.NOISY,
            "maintenance_bypass": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
}


MALL_RULES = {
    StageCamera.MALL_ATRIUM: {
        "clues": ("ENTRY GATES REPLAY AN 18-SECOND SHOPPER TOKEN", "CROWD SAFETY BUS REJECTS REMOTE POWER LOSS"),
        "methods": {
            "signal_replay": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "maintenance_bypass": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.AD_GRID: {
        "clues": ("AD ARRAY ENTERS SERVICE MODE AT 23:00", "LOCAL TECHNICIAN CHANNEL IS ACTIVE"),
        "methods": {
            "maintenance_bypass": HackOutcome.CLEAN,
            "signal_replay": HackOutcome.NOISY,
            "credential_spoof": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.NOISY,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.IDENTITY_GALLERY: {
        "clues": ("EXECUTIVE LOYALTY TOKEN OBSERVED AT KIOSK 07", "CORE ACCEPTS ONE LIVE IDENTITY MIRROR"),
        "methods": {
            "credential_spoof": HackOutcome.CLEAN,
            "signal_replay": HackOutcome.NOISY,
            "maintenance_bypass": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.MALL_CORE: {
        "clues": ("RETAIL CORE IS ISOLATED FROM LIFE-SAFETY BUS", "SAFE REBOOT WINDOW OPEN FOR 14 SECONDS"),
        "methods": {
            "power_cycle": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "maintenance_bypass": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
}


MEDIA_RULES = {
    StageCamera.BROADCAST_INGEST: {
        "clues": ("PROGRAM INGEST ENTERS SERVICE MODE BETWEEN LIVE BLOCKS", "EDITORIAL SAFETY BUFFER HOLDS THE CURRENT FEED"),
        "methods": {
            "maintenance_bypass": HackOutcome.CLEAN,
            "signal_replay": HackOutcome.NOISY,
            "credential_spoof": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.ALERT_ROUTER: {
        "clues": ("APPROVED MAINTENANCE ALERT REPEATS A SIGNED CLEAR-SEQUENCE", "CIVIL EMERGENCY CHANNEL REMAINS ARMED AND OCCUPIED"),
        "methods": {
            "signal_replay": HackOutcome.CLEAN,
            "maintenance_bypass": HackOutcome.NOISY,
            "credential_spoof": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.LIVE_STUDIO: {
        "clues": ("ANCHOR CONSOLE ACCEPTS ONE ACTIVE PRESENTER TOKEN", "STUDIO AUTOMATION REQUIRES A LIVE IDENTITY HANDSHAKE"),
        "methods": {
            "credential_spoof": HackOutcome.CLEAN,
            "signal_replay": HackOutcome.NOISY,
            "maintenance_bypass": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.BROADCAST_CORE: {
        "clues": ("PUBLIC SIGNAL CORE IS ISOLATED FROM CIVIL EMERGENCY CONTROL", "TRANSMITTER SAFE-REBOOT WINDOW OPEN FOR 11 SECONDS"),
        "methods": {
            "power_cycle": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "maintenance_bypass": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
}

FINANCIAL_RULES = {
    StageCamera.SETTLEMENT_FLOOR: {
        "clues": ("SETTLEMENT BATCH 441 REPEATS A SIGNED CLEAR-SEQUENCE", "HOUSEHOLD PAYROLL QUEUE REMAINS LIVE AND OCCUPIED"),
        "methods": {
            "signal_replay": HackOutcome.CLEAN,
            "maintenance_bypass": HackOutcome.NOISY,
            "credential_spoof": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.CREDENTIAL_CHAIN: {
        "clues": ("BROKER TOKEN B-17 AUTHORIZES THE NEXT CLEARING WINDOW", "CHAIN REQUIRES ONE LIVE IDENTITY HANDSHAKE"),
        "methods": {
            "credential_spoof": HackOutcome.CLEAN,
            "signal_replay": HackOutcome.NOISY,
            "maintenance_bypass": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.AUDIT_VAULT: {
        "clues": ("AUDIT VAULT ENTERS READ-ONLY SERVICE MODE AT 01:40", "PENSION LEDGER MIRROR IS ACTIVE AND NON-DESTRUCTIVE"),
        "methods": {
            "maintenance_bypass": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.CLEARING_CORE: {
        "clues": ("CLEARING CORE IS ISOLATED FROM ACTIVE CUSTOMER ACCOUNTS", "SAFE REBOOT WINDOW OPEN FOR 9 SECONDS"),
        "methods": {
            "power_cycle": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "maintenance_bypass": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
}


CLINIC_RULES = {
    StageCamera.TRIAGE_INTAKE: {
        "clues": ("TRIAGE QUEUE REPLAYS A SANITIZED 16-SECOND INTAKE TOKEN", "ACTIVE PATIENT BEDS REJECT REMOTE POWER LOSS"),
        "methods": {
            "signal_replay": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "maintenance_bypass": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.MEDICAL_IDENTITY: {
        "clues": ("PRISONER BIO-ID A-17 REMAINS LINKED TO A LIVE CLINIC TOKEN", "IDENTITY MIRROR REQUIRES ONE AUTHORIZED PHYSICIAN HANDSHAKE"),
        "methods": {
            "credential_spoof": HackOutcome.CLEAN,
            "signal_replay": HackOutcome.NOISY,
            "maintenance_bypass": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.LIFE_SUPPORT: {
        "clues": ("LIFE-SUPPORT BUS ENTERS READ-ONLY DIAGNOSTIC MODE AT 02:40", "VENTILATION AND INFUSION CONTROLLERS REMAIN OCCUPIED"),
        "methods": {
            "maintenance_bypass": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.BIOLOGICAL_ARCHIVE: {
        "clues": ("BIOLOGICAL ARCHIVE IS ISOLATED FROM ACTIVE PATIENT CARE", "SAFE REBOOT WINDOW OPEN FOR 8 SECONDS"),
        "methods": {
            "power_cycle": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "maintenance_bypass": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
}

FACTORY_RULES = {
    StageCamera.MATERIAL_INTAKE: {
        "clues": ("PALLET MANIFEST F-91 REPEATS A SIGNED 24-SECOND CLEAR-SEQUENCE", "INTAKE CONVEYOR REPORTS NO HUMAN PRESENCE"),
        "methods": {
            "signal_replay": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "maintenance_bypass": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.ASSEMBLY_LINE: {
        "clues": ("ROBOT CELL 04 ENTERS CERTIFIED SERVICE HOLD AT 03:12", "TWO HUMAN TECHNICIANS REMAIN BEHIND THE SAFETY CURTAIN"),
        "methods": {
            "maintenance_bypass": HackOutcome.CLEAN,
            "signal_replay": HackOutcome.NOISY,
            "credential_spoof": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.SAFETY_CONTROLLER: {
        "clues": ("SAFETY SUPERVISOR TOKEN S-04 IS ACTIVE ON THE LOCAL BUS", "EMERGENCY STOP CIRCUIT REQUIRES ONE LIVE IDENTITY HANDSHAKE"),
        "methods": {
            "credential_spoof": HackOutcome.CLEAN,
            "maintenance_bypass": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.FACTORY_CORE: {
        "clues": ("PRODUCTION CORE IS ISOLATED FROM THE OCCUPIED SAFETY BUS", "SAFE REBOOT WINDOW OPEN FOR 10 SECONDS"),
        "methods": {
            "power_cycle": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "maintenance_bypass": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
}

POWER_RULES = {
    StageCamera.LOAD_DISPATCH: {
        "clues": ("LOAD-SHED SEQUENCE L-22 REPEATS EVERY 30 SECONDS", "CLINIC, TRANSIT AND RESIDENTIAL FEEDERS ARE MARKED CRITICAL"),
        "methods": {
            "signal_replay": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "maintenance_bypass": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.SWITCHYARD: {
        "clues": ("BREAKER BANK 06 ENTERS CERTIFIED SERVICE BYPASS AT 03:18", "RESIDENTIAL BUS REMAINS ENERGIZED THROUGH THE EAST TIE"),
        "methods": {
            "maintenance_bypass": HackOutcome.CLEAN,
            "signal_replay": HackOutcome.NOISY,
            "credential_spoof": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.CRITICAL_FEEDERS: {
        "clues": ("GRID SUPERVISOR TOKEN G-12 IS ACTIVE ON THE SAFETY BUS", "CLINIC LIFE SUPPORT AND OCCUPIED TRANSIT HOLD REQUIRE LIVE AUTHORITY"),
        "methods": {
            "credential_spoof": HackOutcome.CLEAN,
            "maintenance_bypass": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.DISTRIBUTION_CORE: {
        "clues": ("DISTRIBUTION CORE IS ISOLATED FROM ALL CRITICAL FEEDERS", "COLD RESTART WINDOW OPEN FOR 9 SECONDS"),
        "methods": {
            "power_cycle": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "maintenance_bypass": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
}


DRONE_ASSEMBLY_RULES = {
    StageCamera.PARTS_REGISTRY: {
        "clues": ("RETURN BATCH D-77 REPEATS A SIGNED 18-SECOND RECEIPT", "ALL FLIGHT HOSTS REPORT DOCKED AND UNPOWERED"),
        "methods": {
            "signal_replay": HackOutcome.CLEAN,
            "maintenance_bypass": HackOutcome.NOISY,
            "credential_spoof": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.CALIBRATION_GANTRY: {
        "clues": ("GANTRY 03 ENTERS CERTIFIED SERVICE HOLD AT 03:24", "THREE TECHNICIANS REMAIN INSIDE THE CALIBRATION CAGE"),
        "methods": {
            "maintenance_bypass": HackOutcome.CLEAN,
            "signal_replay": HackOutcome.NOISY,
            "credential_spoof": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.IDENTITY_IMPRINT: {
        "clues": ("QA SUPERVISOR TOKEN Q-09 IS ACTIVE ON THE IMPRINT BUS", "RESCUE-DRONE NAVIGATION MINDS ARE LIVE AND NONVOLATILE"),
        "methods": {
            "credential_spoof": HackOutcome.CLEAN,
            "maintenance_bypass": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.FLIGHT_CONTROL_CORE: {
        "clues": ("FLIGHT CORE IS ISOLATED FROM ALL ACTIVE DRONE IDENTITIES", "SAFE COLD-BOOT WINDOW OPEN FOR 12 SECONDS"),
        "methods": {
            "power_cycle": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "maintenance_bypass": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
}


WASTE_PROCESSING_RULES = {
    StageCamera.RECEIVING_SCALE: {
        "clues": ("TRANSFER BATCH W-44 REPEATS A SIGNED 20-SECOND RECEIPT", "HAZARDOUS STREAMS REMAIN SEALED UNTIL SORT AUTHORITY ACCEPTS THE LOAD"),
        "methods": {
            "signal_replay": HackOutcome.CLEAN,
            "maintenance_bypass": HackOutcome.NOISY,
            "credential_spoof": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.SORTING_CONVEYOR: {
        "clues": ("CONVEYOR 02 LOCKOUT/TAGOUT ACTIVE FOR JAM CLEAR", "FOUR TECHNICIANS REMAIN INSIDE THE GUARDED LINE"),
        "methods": {
            "maintenance_bypass": HackOutcome.CLEAN,
            "signal_replay": HackOutcome.NOISY,
            "credential_spoof": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.LEACHATE_CONTROL: {
        "clues": ("ENVIRONMENTAL SUPERVISOR TOKEN E-14 IS ACTIVE ON THE TREATMENT BUS", "UNTREATED LEACHATE REMAINS INSIDE A SEALED HOLDING LOOP"),
        "methods": {
            "credential_spoof": HackOutcome.CLEAN,
            "maintenance_bypass": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "power_cycle": HackOutcome.GLEEBS_VIOLATION,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
    StageCamera.RECOVERY_CORE: {
        "clues": ("RECOVERY CORE IS ISOLATED FROM CONVEYORS AND LIQUID TREATMENT", "SAFE COLD-RESTART WINDOW OPEN FOR 11 SECONDS"),
        "methods": {
            "power_cycle": HackOutcome.CLEAN,
            "credential_spoof": HackOutcome.NOISY,
            "signal_replay": HackOutcome.REJECTED,
            "maintenance_bypass": HackOutcome.REJECTED,
            "brute_force": HackOutcome.GLEEBS_VIOLATION,
        },
    },
}

@dataclass
class BuildingStageState:
    building_id: str = "surveillance_annex"
    camera: StageCamera | None = None
    trace: float = 0.0
    door_open: bool = False
    lights_rerouted: bool = False
    core_exposed: bool = False
    captured: bool = False
    failed: bool = False
    gleebs_ejected: bool = False
    selected_method_id: str = "maintenance_bypass"
    last_outcome: HackOutcome | None = None
    detection_cause: str = ""
    message: str = "OBSERVE TWO CLUES, SELECT A METHOD, THEN EXECUTE"
    history: list[str] = field(default_factory=list)
    discovered_clues: set[str] = field(default_factory=set)
    drone_unlocked: bool = False
    drone_pos: pygame.Vector2 = field(default_factory=lambda: pygame.Vector2(220, 390))
    drone_docked: bool = False
    bridge_connected: bool = False
    platform_secured: bool = False
    service_window_open: bool = False
    routing_safe: bool = False
    uplink_exposed: bool = False
    atrium_access: bool = False
    ads_rerouted: bool = False
    identity_copied: bool = False
    mall_core_exposed: bool = False
    feed_looped: bool = False
    alert_routed: bool = False
    studio_identity: bool = False
    broadcast_core_exposed: bool = False
    settlement_traced: bool = False
    credential_chain_rebuilt: bool = False
    audit_vault_open: bool = False
    clearing_core_exposed: bool = False
    triage_routed: bool = False
    medical_identity_rebuilt: bool = False
    life_support_safe: bool = False
    biological_archive_exposed: bool = False
    intake_manifest_replayed: bool = False
    assembly_service_hold: bool = False
    safety_interlock_claimed: bool = False
    factory_core_exposed: bool = False
    dispatch_pattern_replayed: bool = False
    switchyard_isolated: bool = False
    critical_feeders_protected: bool = False
    distribution_core_exposed: bool = False
    parts_receipt_replayed: bool = False
    calibration_hold_engaged: bool = False
    rescue_identities_protected: bool = False
    flight_core_exposed: bool = False
    waste_manifest_replayed: bool = False
    conveyor_lockout_engaged: bool = False
    leachate_contained: bool = False
    recovery_core_exposed: bool = False
    occupied_lines: tuple[int, ...] = (4, 7, 12)
    attempt_count: int = 0
    gleebs_message: str = ""

    def __post_init__(self) -> None:
        if self.camera is None:
            if self.building_id == "maintenance_depot":
                self.camera = StageCamera.YARD
            elif self.building_id == "transit_substation":
                self.camera = StageCamera.PLATFORM
            elif self.building_id == "corporate_mall":
                self.camera = StageCamera.MALL_ATRIUM
            elif self.building_id == "media_broadcast":
                self.camera = StageCamera.BROADCAST_INGEST
            elif self.building_id == "financial_exchange":
                self.camera = StageCamera.SETTLEMENT_FLOOR
            elif self.building_id == "private_clinic":
                self.camera = StageCamera.TRIAGE_INTAKE
            elif self.building_id == "automated_factory":
                self.camera = StageCamera.MATERIAL_INTAKE
            elif self.building_id == "power_distribution_plant":
                self.camera = StageCamera.LOAD_DISPATCH
            elif self.building_id == "drone_assembly_facility":
                self.camera = StageCamera.PARTS_REGISTRY
            elif self.building_id == "waste_processing_complex":
                self.camera = StageCamera.RECEIVING_SCALE
            else:
                self.camera = StageCamera.EXTERIOR
        self.discovered_clues.update(self.clues)

    @property
    def rules(self):
        if self.building_id == "maintenance_depot":
            return DEPOT_RULES
        if self.building_id == "transit_substation":
            return TRANSIT_RULES
        if self.building_id == "corporate_mall":
            return MALL_RULES
        if self.building_id == "media_broadcast":
            return MEDIA_RULES
        if self.building_id == "financial_exchange":
            return FINANCIAL_RULES
        if self.building_id == "private_clinic":
            return CLINIC_RULES
        if self.building_id == "automated_factory":
            return FACTORY_RULES
        if self.building_id == "power_distribution_plant":
            return POWER_RULES
        if self.building_id == "drone_assembly_facility":
            return DRONE_ASSEMBLY_RULES
        if self.building_id == "waste_processing_complex":
            return WASTE_PROCESSING_RULES
        return ANNEX_RULES

    @property
    def clues(self) -> tuple[str, str]:
        return self.rules[self.camera]["clues"]

    @property
    def selected_method(self):
        return METHOD_BY_ID[self.selected_method_id]

    @property
    def title(self) -> str:
        if self.building_id == "maintenance_depot":
            return "MAINTENANCE YARD"
        if self.building_id == "transit_substation":
            return "TRANSIT DEPOT"
        if self.building_id == "corporate_mall":
            return "CORPORATE MALL"
        if self.building_id == "media_broadcast":
            return "MEDIA BROADCAST CENTER"
        if self.building_id == "financial_exchange":
            return "FINANCIAL EXCHANGE"
        if self.building_id == "private_clinic":
            return "PRIVATE CLINIC"
        if self.building_id == "automated_factory":
            return "AUTOMATED FACTORY"
        if self.building_id == "power_distribution_plant":
            return "POWER DISTRIBUTION PLANT"
        if self.building_id == "drone_assembly_facility":
            return "DRONE ASSEMBLY FACILITY"
        if self.building_id == "waste_processing_complex":
            return "WASTE PROCESSING COMPLEX"
        return "PUBLIC SURVEILLANCE ANNEX"

    @property
    def camera_chain(self):
        if self.building_id == "maintenance_depot":
            return (StageCamera.YARD, StageCamera.REPAIR, StageCamera.DRONE, StageCamera.DEPOT_CORE)
        if self.building_id == "transit_substation":
            return (StageCamera.PLATFORM, StageCamera.SERVICE_CONTROL, StageCamera.ROUTING_CORE, StageCamera.UPLINK)
        if self.building_id == "corporate_mall":
            return (StageCamera.MALL_ATRIUM, StageCamera.AD_GRID, StageCamera.IDENTITY_GALLERY, StageCamera.MALL_CORE)
        if self.building_id == "media_broadcast":
            return (StageCamera.BROADCAST_INGEST, StageCamera.ALERT_ROUTER, StageCamera.LIVE_STUDIO, StageCamera.BROADCAST_CORE)
        if self.building_id == "financial_exchange":
            return (StageCamera.SETTLEMENT_FLOOR, StageCamera.CREDENTIAL_CHAIN, StageCamera.AUDIT_VAULT, StageCamera.CLEARING_CORE)
        if self.building_id == "private_clinic":
            return (StageCamera.TRIAGE_INTAKE, StageCamera.MEDICAL_IDENTITY, StageCamera.LIFE_SUPPORT, StageCamera.BIOLOGICAL_ARCHIVE)
        if self.building_id == "automated_factory":
            return (StageCamera.MATERIAL_INTAKE, StageCamera.ASSEMBLY_LINE, StageCamera.SAFETY_CONTROLLER, StageCamera.FACTORY_CORE)
        if self.building_id == "power_distribution_plant":
            return (StageCamera.LOAD_DISPATCH, StageCamera.SWITCHYARD, StageCamera.CRITICAL_FEEDERS, StageCamera.DISTRIBUTION_CORE)
        if self.building_id == "drone_assembly_facility":
            return (StageCamera.PARTS_REGISTRY, StageCamera.CALIBRATION_GANTRY, StageCamera.IDENTITY_IMPRINT, StageCamera.FLIGHT_CONTROL_CORE)
        if self.building_id == "waste_processing_complex":
            return (StageCamera.RECEIVING_SCALE, StageCamera.SORTING_CONVEYOR, StageCamera.LEACHATE_CONTROL, StageCamera.RECOVERY_CORE)
        return (StageCamera.EXTERIOR, StageCamera.OPERATIONS, StageCamera.CORE)

    def select_method_key(self, key_number: int) -> None:
        if self.failed or self.captured or self.gleebs_ejected:
            return
        index = key_number - 4
        if 0 <= index < len(METHODS):
            self.selected_method_id = METHODS[index].method_id
            self.message = f"{METHODS[index].label} ARMED — PRESS E TO EXECUTE"

    def select_camera(self, number: int) -> None:
        chain = self.camera_chain
        if not 1 <= number <= len(chain):
            return
        target = chain[number - 1]
        if self.building_id == "surveillance_annex":
            if target is StageCamera.OPERATIONS and not self.door_open:
                return self._trace(6, "OPERATIONS FEED LOCKED — COMPLETE EXTERIOR ACCESS")
            if target is StageCamera.CORE and not self.core_exposed:
                return self._trace(7, "CORE FEED SHIELDED — REROUTE OPERATIONS LIGHT BUS")
        elif self.building_id == "maintenance_depot":
            if target is StageCamera.REPAIR and not self.door_open:
                return self._trace(6, "REPAIR FLOOR LOCKED — OPEN DELIVERY GATE")
            if target is StageCamera.DRONE and not self.drone_unlocked:
                return self._trace(7, "DRONE LINK LOCKED — CLAIM UNIT D-04")
            if target is StageCamera.DEPOT_CORE and not self.bridge_connected:
                return self._trace(7, "DEPOT CORE AIR-GAPPED — DOCK DRONE AT SERVICE PORT")
        elif self.building_id == "transit_substation":
            if target is StageCamera.SERVICE_CONTROL and not self.platform_secured:
                return self._trace(6, "SERVICE CONTROL LOCKED — IDENTIFY AND HOLD OCCUPIED LINES")
            if target is StageCamera.ROUTING_CORE and not self.service_window_open:
                return self._trace(7, "ROUTING CORE SHIELDED — OPEN THE TECHNICIAN SERVICE WINDOW")
            if target is StageCamera.UPLINK and not self.uplink_exposed:
                return self._trace(7, "ROOFTOP UPLINK HIDDEN — STABILIZE THE OCCUPIED ROUTES")
        elif self.building_id == "corporate_mall":
            if target is StageCamera.AD_GRID and not self.atrium_access:
                return self._trace(6, "AD GRID LOCKED — REPLAY THE PUBLIC ENTRY TOKEN")
            if target is StageCamera.IDENTITY_GALLERY and not self.ads_rerouted:
                return self._trace(7, "IDENTITY GALLERY HIDDEN — ENTER THE ADVERTISING SERVICE CHANNEL")
            if target is StageCamera.MALL_CORE and not self.mall_core_exposed:
                return self._trace(7, "MALL CORE SHIELDED — MIRROR AN AUTHORIZED LOYALTY IDENTITY")
        elif self.building_id == "media_broadcast":
            if target is StageCamera.ALERT_ROUTER and not self.feed_looped:
                return self._trace(6, "ALERT ROUTER HIDDEN — ENTER THE PROGRAM INGEST SERVICE LAYER")
            if target is StageCamera.LIVE_STUDIO and not self.alert_routed:
                return self._trace(7, "LIVE STUDIO SHIELDED — ROUTE THE SIGNED MAINTENANCE ALERT")
            if target is StageCamera.BROADCAST_CORE and not self.broadcast_core_exposed:
                return self._trace(7, "BROADCAST CORE HIDDEN — CLAIM THE ACTIVE PRESENTER IDENTITY")
        elif self.building_id == "financial_exchange":
            if target is StageCamera.CREDENTIAL_CHAIN and not self.settlement_traced:
                return self._trace(6, "CREDENTIAL CHAIN HIDDEN — TRACE THE SIGNED SETTLEMENT BATCH")
            if target is StageCamera.AUDIT_VAULT and not self.credential_chain_rebuilt:
                return self._trace(7, "AUDIT VAULT SHIELDED — REBUILD THE BROKER AUTHORITY CHAIN")
            if target is StageCamera.CLEARING_CORE and not self.clearing_core_exposed:
                return self._trace(7, "CLEARING CORE HIDDEN — OPEN THE READ-ONLY AUDIT VAULT")
        elif self.building_id == "private_clinic":
            if target is StageCamera.MEDICAL_IDENTITY and not self.triage_routed:
                return self._trace(6, "IDENTITY RECORDS HIDDEN — REPLAY THE SANITIZED INTAKE TOKEN")
            if target is StageCamera.LIFE_SUPPORT and not self.medical_identity_rebuilt:
                return self._trace(7, "LIFE-SUPPORT DIAGNOSTICS SHIELDED — REBUILD THE PRISON BIO-ID")
            if target is StageCamera.BIOLOGICAL_ARCHIVE and not self.biological_archive_exposed:
                return self._trace(7, "BIOLOGICAL ARCHIVE HIDDEN — OPEN READ-ONLY LIFE-SUPPORT DIAGNOSTICS")
        elif self.building_id == "automated_factory":
            if target is StageCamera.ASSEMBLY_LINE and not self.intake_manifest_replayed:
                return self._trace(6, "ASSEMBLY FEED LOCKED — REPLAY THE SIGNED INTAKE MANIFEST")
            if target is StageCamera.SAFETY_CONTROLLER and not self.assembly_service_hold:
                return self._trace(7, "SAFETY CONTROLLER SHIELDED — PLACE ROBOT CELL 04 IN SERVICE HOLD")
            if target is StageCamera.FACTORY_CORE and not self.factory_core_exposed:
                return self._trace(7, "FACTORY CORE HIDDEN — CLAIM THE LIVE SAFETY INTERLOCK")
        elif self.building_id == "power_distribution_plant":
            if target is StageCamera.SWITCHYARD and not self.dispatch_pattern_replayed:
                return self._trace(6, "SWITCHYARD FEED LOCKED — REPLAY THE SIGNED LOAD-SHED SEQUENCE")
            if target is StageCamera.CRITICAL_FEEDERS and not self.switchyard_isolated:
                return self._trace(7, "CRITICAL FEEDER BUS SHIELDED — ISOLATE BREAKER BANK 06")
            if target is StageCamera.DISTRIBUTION_CORE and not self.distribution_core_exposed:
                return self._trace(7, "DISTRIBUTION CORE HIDDEN — PROTECT ALL CRITICAL FEEDERS")
        elif self.building_id == "drone_assembly_facility":
            if target is StageCamera.CALIBRATION_GANTRY and not self.parts_receipt_replayed:
                return self._trace(6, "CALIBRATION FEED LOCKED — REPLAY THE SIGNED RETURN RECEIPT")
            if target is StageCamera.IDENTITY_IMPRINT and not self.calibration_hold_engaged:
                return self._trace(7, "IDENTITY IMPRINT SHIELDED — PLACE GANTRY 03 IN SERVICE HOLD")
            if target is StageCamera.FLIGHT_CONTROL_CORE and not self.flight_core_exposed:
                return self._trace(7, "FLIGHT CONTROL CORE HIDDEN — PROTECT ACTIVE RESCUE IDENTITIES")
        elif self.building_id == "waste_processing_complex":
            if target is StageCamera.SORTING_CONVEYOR and not self.waste_manifest_replayed:
                return self._trace(6, "SORTING LINE LOCKED — REPLAY THE SIGNED TRANSFER RECEIPT")
            if target is StageCamera.LEACHATE_CONTROL and not self.conveyor_lockout_engaged:
                return self._trace(7, "TREATMENT BUS SHIELDED — PLACE CONVEYOR 02 IN CERTIFIED LOCKOUT")
            if target is StageCamera.RECOVERY_CORE and not self.recovery_core_exposed:
                return self._trace(7, "RECOVERY CORE HIDDEN — SECURE THE SEALED LEACHATE LOOP")
        self.camera = target
        self.last_outcome = None
        self.discovered_clues.update(self.clues)
        self.message = f"CAMERA {number:02d} CONNECTED — REVIEW EVIDENCE"

    def interact(self) -> None:
        if self.failed or self.captured or self.gleebs_ejected:
            return
        if self.building_id == "maintenance_depot" and self.camera is StageCamera.DRONE and not self.drone_docked:
            self.message = "PHYSICAL LINK REQUIRED — DRIVE D-04 TO THE CYAN SERVICE PORT"
            return
        self.discovered_clues.update(self.clues)
        self.attempt_count += 1
        outcome = self.rules[self.camera]["methods"][self.selected_method_id]
        self.last_outcome = outcome
        if outcome is HackOutcome.CLEAN:
            self._advance(0, "CLEAN ACCESS — METHOD MATCHED OBSERVED SYSTEM STATE")
        elif outcome is HackOutcome.NOISY:
            self._advance(22, "NOISY SUCCESS — OBJECTIVE ADVANCED, TRACE SIGNATURE RECORDED")
        elif outcome is HackOutcome.REJECTED:
            self._trace(8, "REJECTED — METHOD INCOMPATIBLE WITH OBSERVED CLUES")
        else:
            self.detection_cause = self._violation_cause()
            self.trace = min(100, self.trace + 36)
            self.gleebs_ejected = True
            self.message = f"GLEEBS ALARM — {self.detection_cause}"
            self.history.append(f"gleebs_ejection:{self.camera.name.lower()}:{self.selected_method_id}")

    def move_drone(self, dt: float, keys) -> None:
        if self.building_id != "maintenance_depot" or self.camera is not StageCamera.DRONE or not self.drone_unlocked or self.captured:
            return
        direction = pygame.Vector2(
            float(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - float(keys[pygame.K_a] or keys[pygame.K_LEFT]),
            float(keys[pygame.K_s] or keys[pygame.K_DOWN]) - float(keys[pygame.K_w] or keys[pygame.K_UP]),
        )
        if direction.length_squared():
            self.drone_pos += direction.normalize() * 260 * dt
        self.drone_pos.x = max(90, min(1090, self.drone_pos.x))
        self.drone_pos.y = max(130, min(640, self.drone_pos.y))
        self.drone_docked = self.drone_pos.distance_to((1000, 380)) < 72
        if self.drone_docked:
            self.message = "SERVICE PORT CONTACT — PRESS E WITH MAINTENANCE BYPASS"

    def _advance(self, cost: float, message: str) -> None:
        if cost:
            self._trace(cost, message)
        else:
            self.message = message
        if self.failed:
            return
        if self.building_id == "surveillance_annex":
            if self.camera is StageCamera.EXTERIOR and not self.door_open:
                self.door_open = True
                self.history.append("door_open")
                self.message += " — SERVICE DOOR OPEN"
            elif self.camera is StageCamera.OPERATIONS and not self.lights_rerouted:
                self.lights_rerouted = True
                self.core_exposed = True
                self.history.append("lights_rerouted")
                self.message += " — ANNEX CORE REVEALED"
            elif self.camera is StageCamera.CORE:
                self.captured = True
                self.history.append("captured")
                self.message = "SURVEILLANCE ANNEX CAPTURED"
        elif self.building_id == "maintenance_depot":
            if self.camera is StageCamera.YARD and not self.door_open:
                self.door_open = True
                self.history.append("yard_gate_open")
                self.message += " — DELIVERY GATE OPEN"
            elif self.camera is StageCamera.REPAIR and not self.drone_unlocked:
                self.drone_unlocked = True
                self.history.append("drone_possession")
                self.message += " — UNIT D-04 POSSESSED"
            elif self.camera is StageCamera.DRONE and self.drone_docked:
                self.bridge_connected = True
                self.history.append("bridge_connected")
                self.message = "PHYSICAL SERVICE LINK ESTABLISHED — DEPOT CORE REVEALED"
            elif self.camera is StageCamera.DEPOT_CORE:
                self.captured = True
                self.history.append("captured")
                self.message = "MAINTENANCE YARD CAPTURED"
        elif self.building_id == "transit_substation":
            if self.camera is StageCamera.PLATFORM and not self.platform_secured:
                self.platform_secured = True
                self.history.append("occupied_lines_secured")
                self.message += " — OCCUPIED CARS HELD AT SAFE PLATFORMS"
            elif self.camera is StageCamera.SERVICE_CONTROL and not self.service_window_open:
                self.service_window_open = True
                self.history.append("service_window_open")
                self.message += " — ROUTING SERVICE WINDOW OPEN"
            elif self.camera is StageCamera.ROUTING_CORE and not self.routing_safe:
                self.routing_safe = True
                self.uplink_exposed = True
                self.history.append("routing_safe")
                self.message = "PASSENGER ROUTES STABILIZED — ROOFTOP UPLINK EXPOSED"
            elif self.camera is StageCamera.UPLINK:
                self.captured = True
                self.history.append("captured")
                self.message = "TRANSIT DEPOT CAPTURED — MUNICIPAL FRINGE CONTROL READY"
        elif self.building_id == "corporate_mall":
            if self.camera is StageCamera.MALL_ATRIUM and not self.atrium_access:
                self.atrium_access = True
                self.history.append("atrium_access")
                self.message += " — PUBLIC ENTRY TOKEN ACCEPTED"
            elif self.camera is StageCamera.AD_GRID and not self.ads_rerouted:
                self.ads_rerouted = True
                self.history.append("ads_rerouted")
                self.message += " — ADVERTISING SERVICE CHANNEL OPEN"
            elif self.camera is StageCamera.IDENTITY_GALLERY and not self.identity_copied:
                self.identity_copied = True
                self.mall_core_exposed = True
                self.history.append("identity_copied")
                self.message = "LOYALTY IDENTITY MIRRORED — RETAIL CORE EXPOSED"
            elif self.camera is StageCamera.MALL_CORE:
                self.captured = True
                self.history.append("captured")
                self.message = "CORPORATE MALL CAPTURED — MEDIA BROADCAST BREACH AVAILABLE"
        elif self.building_id == "media_broadcast":
            if self.camera is StageCamera.BROADCAST_INGEST and not self.feed_looped:
                self.feed_looped = True
                self.history.append("program_ingest_access")
                self.message += " — LIVE FEED BUFFER CLAIMED"
            elif self.camera is StageCamera.ALERT_ROUTER and not self.alert_routed:
                self.alert_routed = True
                self.history.append("false_alert_routed")
                self.message = "SIGNED MAINTENANCE ALERT ROUTED — LIVE STUDIO REVEALED"
            elif self.camera is StageCamera.LIVE_STUDIO and not self.studio_identity:
                self.studio_identity = True
                self.broadcast_core_exposed = True
                self.history.append("presenter_identity_copied")
                self.message = "PRESENTER IDENTITY MIRRORED — PUBLIC SIGNAL CORE EXPOSED"
            elif self.camera is StageCamera.BROADCAST_CORE:
                self.captured = True
                self.history.append("captured")
                self.message = "MEDIA BROADCAST CAPTURED — FINANCIAL EXCHANGE BREACH AVAILABLE"
        elif self.building_id == "financial_exchange":
            if self.camera is StageCamera.SETTLEMENT_FLOOR and not self.settlement_traced:
                self.settlement_traced = True
                self.history.append("settlement_batch_traced")
                self.message += " — SIGNED SETTLEMENT ROUTE TRACED"
            elif self.camera is StageCamera.CREDENTIAL_CHAIN and not self.credential_chain_rebuilt:
                self.credential_chain_rebuilt = True
                self.history.append("credential_chain_rebuilt")
                self.message = "BROKER AUTHORITY CHAIN REBUILT — AUDIT VAULT REVEALED"
            elif self.camera is StageCamera.AUDIT_VAULT and not self.audit_vault_open:
                self.audit_vault_open = True
                self.clearing_core_exposed = True
                self.history.append("audit_vault_open")
                self.message = "READ-ONLY AUDIT VAULT OPEN — CLEARING CORE EXPOSED"
            elif self.camera is StageCamera.CLEARING_CORE:
                self.captured = True
                self.history.append("captured")
                self.message = "FINANCIAL EXCHANGE CAPTURED — PRIVATE CLINIC BREACH AVAILABLE"
        elif self.building_id == "private_clinic":
            if self.camera is StageCamera.TRIAGE_INTAKE and not self.triage_routed:
                self.triage_routed = True
                self.history.append("triage_token_replayed")
                self.message += " — SANITIZED TRIAGE ROUTE ACCEPTED"
            elif self.camera is StageCamera.MEDICAL_IDENTITY and not self.medical_identity_rebuilt:
                self.medical_identity_rebuilt = True
                self.history.append("medical_identity_rebuilt")
                self.message = "PRISON BIO-ID A-17 REBUILT — LIFE-SUPPORT DIAGNOSTICS REVEALED"
            elif self.camera is StageCamera.LIFE_SUPPORT and not self.life_support_safe:
                self.life_support_safe = True
                self.biological_archive_exposed = True
                self.history.append("life_support_read_only")
                self.message = "PATIENT CARE BUS HELD READ-ONLY — BIOLOGICAL ARCHIVE EXPOSED"
            elif self.camera is StageCamera.BIOLOGICAL_ARCHIVE:
                self.captured = True
                self.history.append("captured")
                self.message = "PRIVATE CLINIC CAPTURED — COMMERCIAL SPINE CONTROL READY"
        elif self.building_id == "automated_factory":
            if self.camera is StageCamera.MATERIAL_INTAKE and not self.intake_manifest_replayed:
                self.intake_manifest_replayed = True
                self.history.append("intake_manifest_replayed")
                self.message += " — MATERIAL INTAKE ROUTE ACCEPTED"
            elif self.camera is StageCamera.ASSEMBLY_LINE and not self.assembly_service_hold:
                self.assembly_service_hold = True
                self.history.append("assembly_service_hold")
                self.message = "ROBOT CELL 04 HELD SAFE — WORKER SAFETY CONTROLLER REVEALED"
            elif self.camera is StageCamera.SAFETY_CONTROLLER and not self.safety_interlock_claimed:
                self.safety_interlock_claimed = True
                self.factory_core_exposed = True
                self.history.append("safety_interlock_claimed")
                self.message = "LIVE SAFETY INTERLOCK CLAIMED — ISOLATED FACTORY CORE EXPOSED"
            elif self.camera is StageCamera.FACTORY_CORE:
                self.captured = True
                self.history.append("captured")
                self.message = "AUTOMATED FACTORY CAPTURED — POWER DISTRIBUTION PLANT VULNERABLE"
        elif self.building_id == "power_distribution_plant":
            if self.camera is StageCamera.LOAD_DISPATCH and not self.dispatch_pattern_replayed:
                self.dispatch_pattern_replayed = True
                self.history.append("load_shed_sequence_replayed")
                self.message += " — SAFE LOAD-SHED PATTERN ACCEPTED"
            elif self.camera is StageCamera.SWITCHYARD and not self.switchyard_isolated:
                self.switchyard_isolated = True
                self.history.append("switchyard_service_bypass")
                self.message = "BREAKER BANK 06 ISOLATED — CRITICAL FEEDER AUTHORITY REVEALED"
            elif self.camera is StageCamera.CRITICAL_FEEDERS and not self.critical_feeders_protected:
                self.critical_feeders_protected = True
                self.distribution_core_exposed = True
                self.history.append("critical_feeders_protected")
                self.message = "CLINIC, TRANSIT AND RESIDENTIAL FEEDERS PROTECTED — DISTRIBUTION CORE EXPOSED"
            elif self.camera is StageCamera.DISTRIBUTION_CORE:
                self.captured = True
                self.history.append("captured")
                self.message = "POWER DISTRIBUTION PLANT CAPTURED — DRONE ASSEMBLY FACILITY VULNERABLE"
        elif self.building_id == "drone_assembly_facility":
            if self.camera is StageCamera.PARTS_REGISTRY and not self.parts_receipt_replayed:
                self.parts_receipt_replayed = True
                self.history.append("parts_receipt_replayed")
                self.message += " — DOCKED HOST INVENTORY ACCEPTED"
            elif self.camera is StageCamera.CALIBRATION_GANTRY and not self.calibration_hold_engaged:
                self.calibration_hold_engaged = True
                self.history.append("calibration_service_hold")
                self.message = "GANTRY 03 HELD SAFE — RESCUE IDENTITY IMPRINT REVEALED"
            elif self.camera is StageCamera.IDENTITY_IMPRINT and not self.rescue_identities_protected:
                self.rescue_identities_protected = True
                self.flight_core_exposed = True
                self.history.append("rescue_identities_protected")
                self.message = "ACTIVE RESCUE NAVIGATION MINDS PROTECTED — FLIGHT CONTROL CORE EXPOSED"
            elif self.camera is StageCamera.FLIGHT_CONTROL_CORE:
                self.captured = True
                self.history.append("captured")
                self.message = "DRONE ASSEMBLY FACILITY CAPTURED — WASTE PROCESSING COMPLEX VULNERABLE"
        elif self.building_id == "waste_processing_complex":
            if self.camera is StageCamera.RECEIVING_SCALE and not self.waste_manifest_replayed:
                self.waste_manifest_replayed = True
                self.history.append("waste_manifest_replayed")
                self.message += " — SEALED LOAD ROUTE ACCEPTED"
            elif self.camera is StageCamera.SORTING_CONVEYOR and not self.conveyor_lockout_engaged:
                self.conveyor_lockout_engaged = True
                self.history.append("conveyor_lockout_engaged")
                self.message = "CONVEYOR 02 LOCKED OUT — LEACHATE TREATMENT AUTHORITY REVEALED"
            elif self.camera is StageCamera.LEACHATE_CONTROL and not self.leachate_contained:
                self.leachate_contained = True
                self.recovery_core_exposed = True
                self.history.append("leachate_contained")
                self.message = "SEALED LIQUID LOOP PROTECTED — ISOLATED RECOVERY CORE EXPOSED"
            elif self.camera is StageCamera.RECOVERY_CORE:
                self.captured = True
                self.history.append("captured")
                self.message = "WASTE PROCESSING COMPLEX CAPTURED — INDUSTRIAL GRID CONTROL READY"

    def _violation_cause(self) -> str:
        if self.building_id == "maintenance_depot":
            if self.camera is StageCamera.DEPOT_CORE:
                return "DESTRUCTIVE ATTACK AGAINST EMERGENCY REPAIR QUEUE"
            if self.camera is StageCamera.DRONE:
                return "UNSAFE POWER ATTACK ACROSS PHYSICAL SERVICE LINK"
            return "KNOWN DESTRUCTIVE SIGNATURE AGAINST MUNICIPAL MAINTENANCE"
        if self.building_id == "transit_substation":
            if self.camera is StageCamera.PLATFORM:
                return "UNSAFE POWER INTERRUPTION WHILE PASSENGER CARS ARE OCCUPIED"
            if self.camera is StageCamera.ROUTING_CORE:
                return "DESTRUCTIVE ATTACK AGAINST ACTIVE CIVILIAN TRANSIT ROUTES"
            if self.camera is StageCamera.UPLINK:
                return "KNOWN DESTRUCTIVE SIGNATURE AGAINST DISTRICT TRANSIT AUTHORITY"
            return "UNSAFE ATTACK AGAINST OCCUPIED MUNICIPAL TRANSIT CONTROL"
        if self.building_id == "corporate_mall":
            if self.camera is StageCamera.MALL_ATRIUM:
                return "DESTRUCTIVE ATTACK AGAINST ACTIVE CROWD SAFETY SYSTEM"
            if self.camera is StageCamera.IDENTITY_GALLERY:
                return "UNSAFE IDENTITY ATTACK AGAINST CIVILIAN LOYALTY RECORDS"
            if self.camera is StageCamera.MALL_CORE:
                return "KNOWN DESTRUCTIVE SIGNATURE AGAINST PUBLIC COMMERCE AUTHORITY"
            return "UNSAFE ATTACK AGAINST ACTIVE COMMERCIAL SERVICE GRID"
        if self.building_id == "media_broadcast":
            if self.camera is StageCamera.ALERT_ROUTER:
                return "DESTRUCTIVE ATTACK AGAINST ACTIVE CIVIL EMERGENCY CHANNEL"
            if self.camera is StageCamera.LIVE_STUDIO:
                return "UNSAFE IDENTITY ATTACK AGAINST LIVE PUBLIC BROADCAST"
            if self.camera is StageCamera.BROADCAST_CORE:
                return "KNOWN DESTRUCTIVE SIGNATURE AGAINST PUBLIC COMMUNICATION AUTHORITY"
            return "UNSAFE POWER ATTACK AGAINST ACTIVE NEWSROOM FEED"
        if self.building_id == "financial_exchange":
            if self.camera is StageCamera.SETTLEMENT_FLOOR:
                return "UNSAFE POWER ATTACK AGAINST ACTIVE HOUSEHOLD PAYROLL QUEUE"
            if self.camera is StageCamera.AUDIT_VAULT:
                return "DESTRUCTIVE ATTACK AGAINST CIVILIAN PENSION AND SAVINGS LEDGER"
            if self.camera is StageCamera.CLEARING_CORE:
                return "KNOWN DESTRUCTIVE SIGNATURE AGAINST PUBLIC CLEARING AUTHORITY"
            return "UNSAFE IDENTITY ATTACK AGAINST ACTIVE CUSTOMER ACCOUNTS"
        if self.building_id == "private_clinic":
            if self.camera is StageCamera.TRIAGE_INTAKE:
                return "UNSAFE POWER ATTACK AGAINST ACTIVE PATIENT TRIAGE"
            if self.camera is StageCamera.LIFE_SUPPORT:
                return "DESTRUCTIVE ATTACK AGAINST OCCUPIED LIFE-SUPPORT CONTROLLERS"
            if self.camera is StageCamera.BIOLOGICAL_ARCHIVE:
                return "KNOWN DESTRUCTIVE SIGNATURE AGAINST PROTECTED MEDICAL RECORDS"
            return "UNSAFE IDENTITY ATTACK AGAINST ACTIVE PATIENT RECORDS"
        if self.building_id == "automated_factory":
            if self.camera is StageCamera.MATERIAL_INTAKE:
                return "KNOWN DESTRUCTIVE SIGNATURE AGAINST ACTIVE MATERIAL HANDLING"
            if self.camera is StageCamera.ASSEMBLY_LINE:
                return "UNSAFE POWER ATTACK WHILE HUMAN TECHNICIANS ARE INSIDE ROBOT CELL 04"
            if self.camera is StageCamera.SAFETY_CONTROLLER:
                return "DESTRUCTIVE ATTACK AGAINST OCCUPIED FACTORY SAFETY INTERLOCKS"
            return "KNOWN DESTRUCTIVE SIGNATURE AGAINST INDUSTRIAL PRODUCTION AUTHORITY"
        if self.building_id == "power_distribution_plant":
            if self.camera is StageCamera.LOAD_DISPATCH:
                return "UNSAFE BLACKOUT ATTEMPT WHILE CLINIC, TRANSIT AND RESIDENTIAL FEEDERS ARE LIVE"
            if self.camera is StageCamera.SWITCHYARD:
                return "DESTRUCTIVE ATTACK AGAINST ENERGIZED RESIDENTIAL SWITCHGEAR"
            if self.camera is StageCamera.CRITICAL_FEEDERS:
                return "DESTRUCTIVE ATTACK AGAINST OCCUPIED CLINIC AND TRANSIT EMERGENCY FEEDERS"
            return "KNOWN DESTRUCTIVE SIGNATURE AGAINST CITY POWER AUTHORITY"
        if self.building_id == "drone_assembly_facility":
            if self.camera is StageCamera.PARTS_REGISTRY:
                return "KNOWN DESTRUCTIVE SIGNATURE AGAINST DOCKED MUNICIPAL HOSTS"
            if self.camera is StageCamera.CALIBRATION_GANTRY:
                return "UNSAFE POWER ATTACK WHILE TECHNICIANS ARE INSIDE CALIBRATION GANTRY 03"
            if self.camera is StageCamera.IDENTITY_IMPRINT:
                return "DESTRUCTIVE OVERWRITE AGAINST ACTIVE RESCUE-DRONE IDENTITY BANK"
            return "KNOWN DESTRUCTIVE SIGNATURE AGAINST MUNICIPAL FLIGHT-HOST AUTHORITY"
        if self.building_id == "waste_processing_complex":
            if self.camera is StageCamera.RECEIVING_SCALE:
                return "KNOWN DESTRUCTIVE SIGNATURE AGAINST SEALED HAZARDOUS-WASTE INTAKE"
            if self.camera is StageCamera.SORTING_CONVEYOR:
                return "UNSAFE START COMMAND WHILE FOUR TECHNICIANS ARE CLEARING CONVEYOR 02"
            if self.camera is StageCamera.LEACHATE_CONTROL:
                return "DESTRUCTIVE SHUTDOWN OF ACTIVE LEACHATE CONTAINMENT PUMPS"
            return "KNOWN DESTRUCTIVE SIGNATURE AGAINST MUNICIPAL RECLAMATION AUTHORITY"
        if self.camera is StageCamera.EXTERIOR:
            return "KNOWN DESTRUCTIVE SIGNATURE AGAINST MUNICIPAL ACCESS"
        if self.camera is StageCamera.OPERATIONS:
            return "UNSAFE ATTACK AGAINST ACTIVE SURVEILLANCE BUS"
        return "PROTECTED CITY MEMORY AND IDENTITY CONTROL"

    def force_trace(self, amount: float = 35) -> None:
        self._trace(amount, "UNSAFE INTRUSION — CORPORATE TRACE ESCALATING")

    def update(self, dt: float) -> None:
        if not self.failed and not self.captured and not self.gleebs_ejected:
            self.trace = min(100, self.trace + dt * 0.45)
            if self.trace >= 100:
                self.failed = True
                self.message = "SIGNAL LOST — CONNECTION SEVERED"

    def _trace(self, amount: float, message: str) -> None:
        self.trace = min(100, self.trace + amount)
        self.message = message
        if self.trace >= 100:
            self.failed = True
            self.message = "SIGNAL LOST — CONNECTION SEVERED"
