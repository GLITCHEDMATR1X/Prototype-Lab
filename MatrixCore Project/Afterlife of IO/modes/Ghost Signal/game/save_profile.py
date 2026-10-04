from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from game.runtime_paths import user_data_dir

PROFILE_VERSION = 6
PROFILE_SCHEMA_ID = "ghost_signal_utopia.chapter_one.v1"
DEFAULT_UNLOCKED = {"surveillance_annex"}
STAT_KEYS = (
    "total_hacks",
    "clean_hacks",
    "noisy_hacks",
    "rejected_hacks",
    "gleebs_alarms",
    "civilian_system_violations",
    "building_captures",
    "maximum_trace",
)


@dataclass
class ProfileState:
    profile_version: int = PROFILE_VERSION
    profile_schema: str = PROFILE_SCHEMA_ID
    captured_buildings: set[str] = field(default_factory=set)
    unlocked_buildings: set[str] = field(default_factory=lambda: set(DEFAULT_UNLOCKED))
    discovered_clues: dict[str, set[str]] = field(default_factory=dict)
    memory_fragments: list[str] = field(default_factory=list)
    gleebs_detection_history: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    building_lockouts: dict[str, float] = field(default_factory=dict)
    districts_completed: set[str] = field(default_factory=set)
    method_usage: dict[str, int] = field(default_factory=dict)
    statistics: dict[str, int | float] = field(
        default_factory=lambda: {key: 0 for key in STAT_KEYS}
    )
    settings: dict[str, Any] = field(default_factory=dict)
    onboarding_step: int = 0
    onboarding_complete: bool = False
    first_awakened_at: float = field(default_factory=time.time)
    last_saved_at: float = 0.0
    recovered_from_backup: bool = field(default=False, repr=False, compare=False)
    recovery_notice: str = field(default="", repr=False, compare=False)
    write_enabled: bool = field(default=True, repr=False, compare=False)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "ProfileState":
        raw = raw if isinstance(raw, dict) else {}
        profile = cls()
        profile.profile_version = _safe_int(raw.get("profile_version", 1), 1)
        profile.profile_schema = str(raw.get("profile_schema", PROFILE_SCHEMA_ID))
        profile.captured_buildings = _string_set(raw.get("captured_buildings", []))
        profile.unlocked_buildings = _string_set(raw.get("unlocked_buildings", DEFAULT_UNLOCKED)) | DEFAULT_UNLOCKED
        clues = raw.get("discovered_clues", {})
        clues = clues if isinstance(clues, dict) else {}
        profile.discovered_clues = {
            str(building): _string_set(values)
            for building, values in clues.items()
            if isinstance(values, (list, tuple, set))
        }
        profile.memory_fragments = [str(v) for v in raw.get("memory_fragments", []) if isinstance(v, (str, int, float))]
        history = raw.get("gleebs_detection_history", {})
        history = history if isinstance(history, dict) else {}
        profile.gleebs_detection_history = {
            str(building): [entry for entry in entries if isinstance(entry, dict)][-8:]
            for building, entries in history.items()
            if isinstance(entries, list)
        }
        now = time.time()
        lockouts = raw.get("building_lockouts", {})
        lockouts = lockouts if isinstance(lockouts, dict) else {}
        profile.building_lockouts = {
            str(building): float(expiry)
            for building, expiry in lockouts.items()
            if _finite_number(expiry) and float(expiry) > now
        }
        profile.districts_completed = _string_set(raw.get("districts_completed", []))

        # All historic Chapter One profiles migrate through the same deterministic
        # unlock chain. This is the frozen V1 compatibility contract.
        municipal_complete = {"surveillance_annex", "maintenance_depot", "transit_substation"}.issubset(profile.captured_buildings)
        if "municipal_fringe" in profile.districts_completed or municipal_complete:
            profile.districts_completed.add("municipal_fringe")
            profile.unlocked_buildings.add("corporate_mall")
        if "corporate_mall" in profile.captured_buildings:
            profile.districts_completed.add("commercial_spine_started")
            profile.unlocked_buildings.add("media_broadcast")
        if "media_broadcast" in profile.captured_buildings:
            profile.unlocked_buildings.add("financial_exchange")
        if "financial_exchange" in profile.captured_buildings:
            profile.unlocked_buildings.add("private_clinic")
        if "private_clinic" in profile.captured_buildings:
            profile.districts_completed.add("commercial_spine")
            profile.unlocked_buildings.add("automated_factory")
        if "automated_factory" in profile.captured_buildings:
            profile.districts_completed.add("industrial_grid_started")
            profile.unlocked_buildings.add("power_distribution_plant")
        if "power_distribution_plant" in profile.captured_buildings:
            profile.districts_completed.add("industrial_grid_power_online")
            profile.unlocked_buildings.add("drone_assembly_facility")
        if "drone_assembly_facility" in profile.captured_buildings:
            profile.districts_completed.add("industrial_grid_drone_authority")
            profile.unlocked_buildings.add("waste_processing_complex")
        if "waste_processing_complex" in profile.captured_buildings:
            profile.districts_completed.add("industrial_grid_reclamation_ready")
        industrial_complete = {
            "automated_factory",
            "power_distribution_plant",
            "drone_assembly_facility",
            "waste_processing_complex",
        }.issubset(profile.captured_buildings)
        if industrial_complete:
            profile.districts_completed.add("industrial_grid")

        usage = raw.get("method_usage", {})
        usage = usage if isinstance(usage, dict) else {}
        profile.method_usage = {
            str(method): max(0, _safe_int(count, 0))
            for method, count in usage.items()
            if _finite_number(count)
        }
        stats = raw.get("statistics", {})
        stats = stats if isinstance(stats, dict) else {}
        profile.statistics = {
            key: max(0, float(stats.get(key, 0))) if key == "maximum_trace" else max(0, _safe_int(stats.get(key, 0), 0))
            for key in STAT_KEYS
        }
        settings = raw.get("settings", {})
        profile.settings = dict(settings) if isinstance(settings, dict) else {}
        profile.onboarding_step = max(0, min(5, _safe_int(raw.get("onboarding_step", 0), 0)))
        profile.onboarding_complete = bool(raw.get("onboarding_complete", False))
        if profile.captured_buildings or int(profile.statistics.get("total_hacks", 0)) > 0:
            profile.onboarding_step = 5
            profile.onboarding_complete = True
        profile.first_awakened_at = float(raw.get("first_awakened_at", time.time())) if _finite_number(raw.get("first_awakened_at")) else time.time()
        profile.last_saved_at = float(raw.get("last_saved_at", 0)) if _finite_number(raw.get("last_saved_at")) else 0.0
        return profile

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_schema": PROFILE_SCHEMA_ID,
            "profile_version": PROFILE_VERSION,
            "captured_buildings": sorted(self.captured_buildings),
            "unlocked_buildings": sorted(self.unlocked_buildings | DEFAULT_UNLOCKED),
            "discovered_clues": {
                building: sorted(clues) for building, clues in sorted(self.discovered_clues.items())
            },
            "memory_fragments": list(dict.fromkeys(self.memory_fragments)),
            "gleebs_detection_history": self.gleebs_detection_history,
            "building_lockouts": {
                building: round(float(expiry), 3)
                for building, expiry in sorted(self.building_lockouts.items())
                if float(expiry) > time.time()
            },
            "districts_completed": sorted(self.districts_completed),
            "method_usage": dict(sorted(self.method_usage.items())),
            "statistics": {
                key: round(float(self.statistics.get(key, 0)), 3) if key == "maximum_trace" else int(self.statistics.get(key, 0))
                for key in STAT_KEYS
            },
            "settings": self.settings,
            "onboarding_step": int(self.onboarding_step),
            "onboarding_complete": bool(self.onboarding_complete),
            "first_awakened_at": round(float(self.first_awakened_at), 3),
            "last_saved_at": round(float(self.last_saved_at), 3),
        }

    def record_clues(self, building_id: str, clues: set[str] | tuple[str, ...] | list[str]) -> None:
        self.discovered_clues.setdefault(building_id, set()).update(str(clue) for clue in clues)

    def record_hack(self, building_id: str, method_id: str, outcome: str, trace: float, detection_cause: str = "") -> None:
        self.method_usage[method_id] = self.method_usage.get(method_id, 0) + 1
        self.statistics["total_hacks"] = int(self.statistics.get("total_hacks", 0)) + 1
        key = {
            "clean_success": "clean_hacks",
            "noisy_success": "noisy_hacks",
            "rejected_attempt": "rejected_hacks",
            "gleebs_violation": "gleebs_alarms",
        }.get(outcome)
        if key:
            self.statistics[key] = int(self.statistics.get(key, 0)) + 1
        self.statistics["maximum_trace"] = max(float(self.statistics.get("maximum_trace", 0)), float(trace))
        if outcome == "gleebs_violation":
            if any(word in detection_cause.upper() for word in ("CIVILIAN", "PASSENGER", "OCCUPIED", "PEOPLE")):
                self.statistics["civilian_system_violations"] = int(self.statistics.get("civilian_system_violations", 0)) + 1
            entries = self.gleebs_detection_history.setdefault(building_id, [])
            entries.append({"method": method_id, "cause": detection_cause, "timestamp": round(time.time(), 3)})
            del entries[:-8]

    def capture_building(self, building_id: str) -> None:
        if building_id not in self.captured_buildings:
            self.statistics["building_captures"] = int(self.statistics.get("building_captures", 0)) + 1
        self.captured_buildings.add(building_id)
        self.unlocked_buildings.add(building_id)
        if building_id == "surveillance_annex":
            self.unlocked_buildings.add("maintenance_depot")
        elif building_id == "maintenance_depot":
            self.unlocked_buildings.add("transit_substation")
        elif building_id == "transit_substation":
            self.districts_completed.add("municipal_fringe"); self.unlocked_buildings.add("corporate_mall")
        elif building_id == "corporate_mall":
            self.districts_completed.add("commercial_spine_started"); self.unlocked_buildings.add("media_broadcast")
        elif building_id == "media_broadcast":
            self.unlocked_buildings.add("financial_exchange")
        elif building_id == "financial_exchange":
            self.unlocked_buildings.add("private_clinic")
        elif building_id == "private_clinic":
            self.districts_completed.add("commercial_spine"); self.unlocked_buildings.add("automated_factory")
        elif building_id == "automated_factory":
            self.districts_completed.add("industrial_grid_started"); self.unlocked_buildings.add("power_distribution_plant")
        elif building_id == "power_distribution_plant":
            self.districts_completed.add("industrial_grid_power_online"); self.unlocked_buildings.add("drone_assembly_facility")
        elif building_id == "drone_assembly_facility":
            self.districts_completed.add("industrial_grid_drone_authority"); self.unlocked_buildings.add("waste_processing_complex")
        elif building_id == "waste_processing_complex":
            self.districts_completed.add("industrial_grid_reclamation_ready")
            if {"automated_factory", "power_distribution_plant", "drone_assembly_facility", "waste_processing_complex"}.issubset(self.captured_buildings):
                self.districts_completed.add("industrial_grid")

    def set_lockout(self, building_id: str, expiry: float) -> None:
        self.building_lockouts[building_id] = float(expiry)

    def clear_expired_lockouts(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        before = set(self.building_lockouts)
        self.building_lockouts = {building: expiry for building, expiry in self.building_lockouts.items() if expiry > now}
        return before != set(self.building_lockouts)


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _string_set(value: object) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item) for item in value if isinstance(item, (str, int, float))}


def _finite_number(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return number == number and abs(number) != float("inf")


def profile_path() -> Path:
    override = os.environ.get("GHOST_SIGNAL_PROFILE_PATH")
    return Path(override).expanduser() if override else user_data_dir() / "profile.json"


def backup_path(path: Path | None = None) -> Path:
    path = path or profile_path()
    return path.with_name(path.name + ".bak")


def _decode_profile(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("profile root must be a JSON object")
    version = _safe_int(raw.get("profile_version", 1), 1)
    if version > PROFILE_VERSION:
        raise RuntimeError(f"profile version {version} is newer than supported version {PROFILE_VERSION}")
    return raw


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _quarantine_corrupt_profile(path: Path) -> Path | None:
    if not path.exists():
        return None
    destination = path.with_name(f"{path.stem}.corrupt-{int(time.time())}{path.suffix}")
    try:
        os.replace(path, destination)
    except OSError:
        return None
    return destination


def load_profile(path: Path | None = None) -> ProfileState:
    path = path or profile_path()
    backup = backup_path(path)
    if not path.exists() and not backup.exists():
        return ProfileState()

    if path.exists():
        try:
            return ProfileState.from_dict(_decode_profile(path))
        except RuntimeError as exc:
            # Never downgrade or overwrite a profile created by a future build.
            profile = ProfileState()
            profile.write_enabled = False
            profile.recovery_notice = f"SAVE FROM NEWER VERSION — WRITES DISABLED ({exc})"
            return profile
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    if backup.exists():
        try:
            raw = _decode_profile(backup)
            profile = ProfileState.from_dict(raw)
            quarantined = _quarantine_corrupt_profile(path)
            _atomic_write(path, json.dumps(raw, indent=2).encode("utf-8") + b"\n")
            profile.recovered_from_backup = True
            suffix = f" • CORRUPT COPY: {quarantined.name}" if quarantined else ""
            profile.recovery_notice = "SAVE RECOVERED FROM AUTOMATIC BACKUP" + suffix
            return profile
        except (OSError, ValueError, TypeError, RuntimeError, json.JSONDecodeError):
            pass

    return ProfileState()


def save_profile(profile: ProfileState, path: Path | None = None) -> Path:
    path = path or profile_path()
    if not profile.write_enabled:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    profile.last_saved_at = time.time()

    # Keep the previous valid generation before replacing the active profile.
    if path.exists():
        try:
            _decode_profile(path)
            _atomic_write(backup_path(path), path.read_bytes())
        except (OSError, ValueError, TypeError, RuntimeError, json.JSONDecodeError):
            pass

    payload = json.dumps(profile.to_dict(), indent=2).encode("utf-8") + b"\n"
    # Decode before replacement so malformed serialization can never reach disk.
    json.loads(payload.decode("utf-8"))
    _atomic_write(path, payload)
    profile.profile_version = PROFILE_VERSION
    profile.profile_schema = PROFILE_SCHEMA_ID
    return path


def load_lockouts(now: float | None = None) -> dict[str, float]:
    profile = load_profile()
    profile.clear_expired_lockouts(now)
    return dict(profile.building_lockouts)


def save_lockouts(lockouts: dict[str, float]) -> None:
    profile = load_profile()
    profile.building_lockouts = {str(k): float(v) for k, v in lockouts.items()}
    save_profile(profile)
