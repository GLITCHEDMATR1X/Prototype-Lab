from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from game.building_stage import BuildingStageState
from game.progression import memory_records, recover_building_memory
from game.results import build_mission_result, result_dir, write_result_packets
from game.save_profile import (
    PROFILE_SCHEMA_ID,
    PROFILE_VERSION,
    ProfileState,
    backup_path,
    load_profile,
    profile_path,
    save_profile,
)
from game.version import BUILD_LABEL, PROJECT_NAME, VERSION

BUILDING_ORDER = (
    "surveillance_annex",
    "maintenance_depot",
    "transit_substation",
    "corporate_mall",
    "media_broadcast",
    "financial_exchange",
    "private_clinic",
    "automated_factory",
    "power_distribution_plant",
    "drone_assembly_facility",
    "waste_processing_complex",
)

ROUTES: dict[str, tuple[tuple[int, str], ...]] = {
    "surveillance_annex": ((1, "maintenance_bypass"), (2, "signal_replay"), (3, "credential_spoof")),
    "maintenance_depot": ((1, "maintenance_bypass"), (2, "credential_spoof"), (3, "maintenance_bypass"), (4, "maintenance_bypass")),
    "transit_substation": ((1, "signal_replay"), (2, "maintenance_bypass"), (3, "maintenance_bypass"), (4, "credential_spoof")),
    "corporate_mall": ((1, "signal_replay"), (2, "maintenance_bypass"), (3, "credential_spoof"), (4, "power_cycle")),
    "media_broadcast": ((1, "maintenance_bypass"), (2, "signal_replay"), (3, "credential_spoof"), (4, "power_cycle")),
    "financial_exchange": ((1, "signal_replay"), (2, "credential_spoof"), (3, "maintenance_bypass"), (4, "power_cycle")),
    "private_clinic": ((1, "signal_replay"), (2, "credential_spoof"), (3, "maintenance_bypass"), (4, "power_cycle")),
    "automated_factory": ((1, "signal_replay"), (2, "maintenance_bypass"), (3, "credential_spoof"), (4, "power_cycle")),
    "power_distribution_plant": ((1, "signal_replay"), (2, "maintenance_bypass"), (3, "credential_spoof"), (4, "power_cycle")),
    "drone_assembly_facility": ((1, "signal_replay"), (2, "maintenance_bypass"), (3, "credential_spoof"), (4, "power_cycle")),
    "waste_processing_complex": ((1, "signal_replay"), (2, "maintenance_bypass"), (3, "credential_spoof"), (4, "power_cycle")),
}

LEGACY_CAPTURED = BUILDING_ORDER[:7]
LEGACY_MEMORIES = (
    "andrew_awakening",
    "gleebs_continuity",
    "the_kept_route",
    "mall_identity_echo",
    "broadcast_dead_air",
    "ledger_without_a_name",
    "body_that_never_arrived",
)


def _record_hack(profile: ProfileState, stage: BuildingStageState, method_id: str) -> None:
    stage.selected_method_id = method_id
    stage.interact()
    if stage.last_outcome is None:
        raise RuntimeError(f"{stage.building_id}: method {method_id} produced no outcome")
    profile.record_hack(
        stage.building_id,
        method_id,
        stage.last_outcome.value,
        stage.trace,
        stage.detection_cause,
    )
    profile.record_clues(stage.building_id, stage.discovered_clues)


def _complete_building(profile: ProfileState, building_id: str) -> dict[str, Any]:
    stage = BuildingStageState(building_id)
    for camera_index, method_id in ROUTES[building_id]:
        if camera_index != 1:
            stage.select_camera(camera_index)
        if building_id == "maintenance_depot" and camera_index == 3:
            stage.drone_pos.update(1000, 380)
            stage.drone_docked = True
        _record_hack(profile, stage, method_id)
    if not stage.captured:
        raise RuntimeError(f"{building_id}: canonical route did not capture the building")
    profile.capture_building(building_id)
    profile.record_clues(building_id, stage.discovered_clues)
    memory = recover_building_memory(profile, building_id)
    return {
        "building_id": building_id,
        "captured": stage.captured,
        "trace": round(stage.trace, 3),
        "memory": memory.fragment_id if memory else None,
        "history": list(stage.history),
    }


def _seed_legacy_profile(path: Path) -> None:
    payload = {
        "profile_version": 5,
        "captured_buildings": list(LEGACY_CAPTURED),
        "unlocked_buildings": [*LEGACY_CAPTURED, "automated_factory"],
        "discovered_clues": {},
        "memory_fragments": list(LEGACY_MEMORIES),
        "gleebs_detection_history": {},
        "building_lockouts": {},
        "districts_completed": ["municipal_fringe", "commercial_spine"],
        "method_usage": {"signal_replay": 8, "maintenance_bypass": 10, "credential_spoof": 7, "power_cycle": 4},
        "statistics": {
            "total_hacks": 29,
            "clean_hacks": 29,
            "noisy_hacks": 0,
            "rejected_hacks": 0,
            "gleebs_alarms": 0,
            "civilian_system_violations": 0,
            "building_captures": 7,
            "maximum_trace": 0,
        },
        "settings": {"audio_captions": True, "state_symbols": True, "reduced_flashing": False},
        "onboarding_step": 5,
        "onboarding_complete": True,
        "first_awakened_at": time.time() - 3600,
        "last_saved_at": 0,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_acceptance_playthrough(mode: str) -> int:
    if mode not in {"blank", "migrated"}:
        raise ValueError(f"unsupported acceptance mode: {mode}")

    active_profile = profile_path()
    output_root = result_dir()
    output_root.mkdir(parents=True, exist_ok=True)
    report_path = output_root / f"acceptance_{mode}.json"
    markdown_path = output_root / f"acceptance_{mode}.md"

    if active_profile.exists() or backup_path(active_profile).exists():
        raise RuntimeError(f"acceptance profile path must be empty: {active_profile}")
    if mode == "migrated":
        _seed_legacy_profile(active_profile)

    checks: list[dict[str, Any]] = []

    def record(name: str, passed: object, detail: object = "") -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    profile = load_profile(active_profile)
    initial_captures = len(profile.captured_buildings)
    record("profile_writable", profile.write_enabled, profile.recovery_notice)
    serialized_start = profile.to_dict()
    record("profile_schema_loaded", serialized_start.get("profile_version") == PROFILE_VERSION and serialized_start.get("profile_schema") == PROFILE_SCHEMA_ID, serialized_start)
    record("start_state", initial_captures == (0 if mode == "blank" else 7), initial_captures)
    if mode == "migrated":
        record("legacy_progress_migrated", "commercial_spine" in profile.districts_completed and "automated_factory" in profile.unlocked_buildings, sorted(profile.districts_completed))

    played: list[dict[str, Any]] = []
    for building_id in BUILDING_ORDER:
        if building_id in profile.captured_buildings:
            continue
        played.append(_complete_building(profile, building_id))
        save_profile(profile, active_profile)
        profile = load_profile(active_profile)
        record(f"persist_after_{building_id}", building_id in profile.captured_buildings, sorted(profile.captured_buildings))

    profile.onboarding_step = 5
    profile.onboarding_complete = True
    save_profile(profile, active_profile)
    profile = load_profile(active_profile)
    completion_time = 1212.5 if mode == "blank" else 512.5
    packets = write_result_packets(profile, completion_time, output_root)
    mission = build_mission_result(profile, completion_time)

    record("all_buildings_captured", set(BUILDING_ORDER) == profile.captured_buildings, sorted(profile.captured_buildings))
    record("all_memories_restored", len(memory_records(profile)) == 11 and len(profile.memory_fragments) == 11, profile.memory_fragments)
    record("three_districts_complete", {"municipal_fringe", "commercial_spine", "industrial_grid"}.issubset(profile.districts_completed), sorted(profile.districts_completed))
    record("chapter_one_complete", mission.completed and mission.return_to_lab and mission.buildings_captured == 11 and mission.memory_fragments == 11, asdict(mission))
    record("result_packets_written", all(path.exists() for path in packets.values()), {name: str(path) for name, path in packets.items()})
    record("profile_backup_present", backup_path(active_profile).exists(), str(backup_path(active_profile)))
    record("atomic_temp_absent", not active_profile.with_name(active_profile.name + ".tmp").exists())

    saved_raw = json.loads(active_profile.read_text(encoding="utf-8"))
    record("frozen_schema_written", saved_raw.get("profile_version") == PROFILE_VERSION and saved_raw.get("profile_schema") == PROFILE_SCHEMA_ID, {"version": saved_raw.get("profile_version"), "schema": saved_raw.get("profile_schema")})

    passed = all(check["passed"] for check in checks)
    report = {
        "project": PROJECT_NAME,
        "version": VERSION,
        "build": BUILD_LABEL,
        "mode": mode,
        "profile_path": str(active_profile),
        "initial_captures": initial_captures,
        "buildings_played": played,
        "mission_result": asdict(mission),
        "checks": checks,
        "summary": {
            "passed": sum(bool(check["passed"]) for check in checks),
            "failed": sum(not bool(check["passed"]) for check in checks),
            "final_result": "PASS" if passed else "FAIL",
        },
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(
        f"# {PROJECT_NAME} — {mode.title()} Acceptance Playthrough\n\n"
        + "\n".join(f"- {'PASS' if check['passed'] else 'FAIL'} — {check['name']}" for check in checks)
        + f"\n\nFINAL_RESULT={report['summary']['final_result']}\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"]))
    return 0 if passed else 1
