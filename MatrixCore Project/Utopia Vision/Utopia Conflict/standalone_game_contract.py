"""GLITCHED MATRIX standalone mission result contract.

Stdlib-only contract for Prototype Lab launchable quests. A mission may be
started by Prototype Lab or directly from its own folder; it is not wrapped
inside a legacy wrapped runtime. The mission writes a local result packet that Prototype Lab
can validate and convert into shared points.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

CONTRACT_SCHEMA = "glitched_matrix_standalone_mission_result_v1"
PROFILE_SCHEMA = "glitched_matrix_standalone_mission_profile_preview_v1"
CONTRACT_FLAGS = {
    "--game-contract-test", "--game-result-test", "--complete-game-test", "--profile-test",
    "--mission-contract-test", "--mission-result-test", "--complete-mission-test",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "complete", "completed"}
    if value is None:
        return default
    return bool(value)


def load_manifest(root: str | Path | None = None) -> dict[str, Any]:
    folder = Path(root or Path.cwd()).resolve()
    path = folder / "standalone_manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"standalone_manifest.json missing for mission folder: {folder}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"standalone_manifest.json must contain an object: {path}")
    for required in ("id", "title", "entry", "engine", "core_loop", "score_rules"):
        if not data.get(required):
            raise ValueError(f"manifest missing required field '{required}': {path}")
    if data.get("depends_on_legacy_wrapper") is True or data.get("depends_on_external_hub") is True:
        raise ValueError(f"manifest still declares a wrapped/dependent runtime: {path}")
    return data


def default_sample_result(manifest: Mapping[str, Any], completed: bool = True) -> dict[str, Any]:
    sample = dict(manifest.get("mission_contract", {}).get("sample_result", {}) or {})
    if not sample:
        sample = dict(manifest.get("game_contract", {}).get("sample_result", {}) or {})
    if not sample:
        sample = dict(manifest.get("sample_result", {}) or {})
    if not sample:
        sample = {
            "score_delta": 1000,
            "completed": completed,
            "fragments_recovered": 1,
            "fragments_required": 1,
            "signal": "MISSION_SAMPLE_COMPLETE" if completed else "MISSION_SAMPLE_PARTIAL",
        }
    sample.setdefault("completed", completed)
    return sample


def _stat_payload(raw: Mapping[str, Any]) -> dict[str, int]:
    keys = [
        "kills", "wave", "enemies_remaining", "breaches_sealed", "breaches_required",
        "fragments_recovered", "fragments_required", "flags_captured", "flags_required",
        "campaign_points", "campaign_points_required", "nodes_captured", "nodes_required",
    ]
    return {k: _as_int(raw.get(k), 0) for k in keys if k in raw}


def _objective_count(raw: Mapping[str, Any]) -> int:
    return max(
        _as_int(raw.get("breaches_sealed"), 0),
        _as_int(raw.get("fragments_recovered"), 0),
        _as_int(raw.get("flags_captured"), 0),
        _as_int(raw.get("campaign_points"), 0),
        _as_int(raw.get("nodes_captured"), 0),
    )


def calculate_lab_points(score: int, completed: bool, raw: Mapping[str, Any]) -> int:
    base = max(0, score) // 10
    completion_bonus = 150 if completed else 0
    objective_bonus = min(140, _objective_count(raw) * 28)
    combat_bonus = min(100, _as_int(raw.get("kills"), 0) * 4)
    wave_bonus = min(90, max(0, _as_int(raw.get("wave"), 1) - 1) * 18)
    return max(0, base + completion_bonus + objective_bonus + combat_bonus + wave_bonus)


def badges_for(raw: Mapping[str, Any], completed: bool, score: int) -> list[str]:
    badges: list[str] = []
    if completed:
        badges.append("mission_complete")
    if score > 0:
        badges.append("scored_run")
    if _as_int(raw.get("kills"), 0) > 0:
        badges.append("combat_loop")
    if _as_int(raw.get("wave"), 0) >= 4:
        badges.append("wave_runner")
    if _objective_count(raw) > 0:
        badges.append("objective_progress")
    if completed and _as_int(raw.get("enemies_remaining"), 0) <= 0:
        badges.append("clean_finish")
    return badges or ["mission_boot"]


def normalize_game_result(raw_result: Mapping[str, Any] | None, manifest: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(raw_result or {})
    score = _as_int(raw.get("score_delta", raw.get("score", 0)), 0)
    completed = _as_bool(raw.get("completed"), False)
    mission_id = str(manifest.get("id") or raw.get("mission_id") or raw.get("mode_id") or raw.get("mode") or "unknown_mission")
    title = str(manifest.get("title") or raw.get("mode") or mission_id)
    points = calculate_lab_points(score, completed, raw)
    return {
        "schema": CONTRACT_SCHEMA,
        "mission_id": mission_id,
        "game_id": mission_id,
        "quest_id": mission_id,
        "title": title,
        "entry": str(manifest.get("entry", "main.py")),
        "engine": str(manifest.get("engine", "panda3d")),
        "launch_mode": str(manifest.get("launch_mode", "prototype_lab_mission_or_direct")),
        "prototype_lab_launchable": bool(manifest.get("prototype_lab_launchable", True)),
        "runtime_wrapper_required": bool(manifest.get("runtime_wrapper_required", False)),
        "completed": completed,
        "return_to_lab": True,
        "exit_to_desktop": False,
        "session_score": score,
        "score_delta": score,
        "prototype_lab_points_awarded": points,
        "quest_points_awarded": points,
        "profile_points_awarded": points,
        "badges": badges_for(raw, completed, score),
        "signal": str(raw.get("signal") or raw.get("memory_fragment") or ""),
        "stats": _stat_payload(raw),
        "raw_result": raw,
        "core_loop": manifest.get("core_loop", ""),
        "score_rules": manifest.get("score_rules", {}),
        "mission_status": manifest.get("mission_status", "active_prototype_lab_mission"),
        "timestamp_utc": now_iso(),
    }


def make_profile_preview(result: Mapping[str, Any]) -> dict[str, Any]:
    mission_id = str(result.get("mission_id", result.get("game_id", "unknown_mission")))
    return {
        "schema": PROFILE_SCHEMA,
        "timestamp_utc": now_iso(),
        "prototype_lab_points_preview_delta": _as_int(result.get("prototype_lab_points_awarded"), 0),
        "profile_points_preview_delta": _as_int(result.get("profile_points_awarded"), 0),
        "missions": {
            mission_id: {
                "completed": _as_bool(result.get("completed"), False),
                "best_score_preview": _as_int(result.get("session_score"), 0),
                "last_badges_preview": list(result.get("badges", []) or []),
                "last_signal_preview": str(result.get("signal", "")),
            }
        },
        "note": "Preview only. Prototype Lab should validate this local mission result before saving shared points.",
    }


def write_result_files(result: Mapping[str, Any], root: str | Path | None = None) -> dict[str, str]:
    folder = Path(root or Path.cwd()).resolve()
    reports = folder / "verification" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    json_path = reports / "game_result.json"
    mission_json_path = reports / "mission_result.json"
    md_path = reports / "game_result.md"
    mission_md_path = reports / "mission_result.md"
    profile_path = reports / "profile_preview.json"
    payload = json.dumps(result, indent=2, sort_keys=True)
    json_path.write_text(payload, encoding="utf-8")
    mission_json_path.write_text(payload, encoding="utf-8")
    profile = make_profile_preview(result)
    profile_path.write_text(json.dumps(profile, indent=2, sort_keys=True), encoding="utf-8")
    md_text = (
        "# Standalone Mission Result\n\n"
        f"- Mission: {result.get('title')} (`{result.get('mission_id')}`)\n"
        f"- Completed: {result.get('completed')}\n"
        f"- Session score: {result.get('session_score')}\n"
        f"- Prototype Lab points awarded: {result.get('prototype_lab_points_awarded')}\n"
        f"- Return to Lab: {result.get('return_to_lab')}\n"
        f"- Badges: {', '.join(result.get('badges', []) or [])}\n"
        f"- Signal: {result.get('signal', '')}\n"
    )
    md_path.write_text(md_text, encoding="utf-8")
    mission_md_path.write_text(md_text, encoding="utf-8")
    return {
        "game_result_json": str(json_path),
        "mission_result_json": str(mission_json_path),
        "game_result_md": str(md_path),
        "mission_result_md": str(mission_md_path),
        "profile_preview_json": str(profile_path),
    }


def handle_game_contract_cli(argv: list[str] | None = None, root: str | Path | None = None) -> int | None:
    args = list(sys.argv[1:] if argv is None else argv)
    if not any(flag in args for flag in CONTRACT_FLAGS):
        return None
    folder = Path(root or Path.cwd()).resolve()
    manifest = load_manifest(folder)
    status = {
        "schema": "glitched_matrix_standalone_mission_contract_test_v1",
        "status": "PASS",
        "mission_id": manifest.get("id"),
        "title": manifest.get("title"),
        "entry": manifest.get("entry"),
        "engine": manifest.get("engine"),
        "contract": manifest.get("mission_contract", manifest.get("game_contract", {})).get("schema", CONTRACT_SCHEMA),
        "mission_status": manifest.get("mission_status", "active_prototype_lab_mission"),
        "prototype_lab_launchable": bool(manifest.get("prototype_lab_launchable", True)),
        "runtime_wrapper_required": bool(manifest.get("runtime_wrapper_required", False)),
        "timestamp_utc": now_iso(),
    }
    result_flags = {"--game-result-test", "--complete-game-test", "--profile-test", "--mission-result-test", "--complete-mission-test"}
    if any(flag in args for flag in result_flags):
        completed = any(flag in args for flag in {"--complete-game-test", "--complete-mission-test", "--game-result-test", "--mission-result-test"})
        sample = default_sample_result(manifest, completed=completed)
        result = normalize_game_result(sample, manifest)
        paths = write_result_files(result, folder)
        status["result"] = result
        status["written"] = paths
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0
