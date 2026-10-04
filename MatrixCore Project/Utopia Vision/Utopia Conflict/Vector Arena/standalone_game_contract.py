"""GLITCHED MATRIX standalone game result contract.

This module is intentionally stdlib-only. It lets each split-out dimension prove
that it can run as its own game without needing an external hub.
The runtime may still return its own native result dictionary; this wrapper
normalizes it into a standalone session/profile packet owned by the game folder.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

CONTRACT_SCHEMA = "glitched_matrix_standalone_game_result_v1"
PROFILE_SCHEMA = "glitched_matrix_standalone_game_profile_preview_v1"
CONTRACT_FLAGS = {"--game-contract-test", "--game-result-test", "--complete-game-test", "--profile-test"}


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
        raise FileNotFoundError(f"standalone_manifest.json missing for game folder: {folder}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"standalone_manifest.json must contain an object: {path}")
    for required in ("id", "title", "entry", "engine", "core_loop", "score_rules"):
        if not data.get(required):
            raise ValueError(f"manifest missing required field '{required}': {path}")
    if data.get("depends_on_external_hub") is True:
        raise ValueError(f"manifest is not independent yet: {path}")
    return data


def default_sample_result(manifest: Mapping[str, Any], completed: bool = True) -> dict[str, Any]:
    sample = dict(manifest.get("game_contract", {}).get("sample_result", {}) or {})
    if not sample:
        sample = dict(manifest.get("sample_result", {}) or {})
    if not sample:
        sample = {
            "score_delta": 1000,
            "completed": completed,
            "signal": f"{manifest.get('id', 'game').upper()}_SAMPLE_SESSION",
        }
    sample["completed"] = completed if completed else _as_bool(sample.get("completed"), False)
    return sample


def _stat_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "kills", "wave", "breaches_sealed", "fragments_recovered", "fragments_required",
        "flags_captured", "flags_required", "campaign_points", "campaign_points_required",
        "enemies_remaining", "sfx_loaded", "weapon_rank",
    )
    return {k: raw[k] for k in keys if k in raw}


def _objective_count(raw: Mapping[str, Any]) -> int:
    return max(
        _as_int(raw.get("breaches_sealed"), 0),
        _as_int(raw.get("fragments_recovered"), 0),
        _as_int(raw.get("flags_captured"), 0),
        _as_int(raw.get("campaign_points"), 0),
    )


def calculate_profile_points(score: int, completed: bool, raw: Mapping[str, Any]) -> int:
    base = max(0, score) // 10
    completion_bonus = 150 if completed else 0
    objective_bonus = min(120, _objective_count(raw) * 24)
    combat_bonus = min(100, _as_int(raw.get("kills"), 0) * 4)
    wave_bonus = min(90, max(0, _as_int(raw.get("wave"), 1) - 1) * 18)
    return max(0, base + completion_bonus + objective_bonus + combat_bonus + wave_bonus)


def badges_for(raw: Mapping[str, Any], completed: bool, score: int) -> list[str]:
    badges: list[str] = []
    if completed:
        badges.append("session_complete")
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
    return badges or ["boot_trace"]


def normalize_game_result(raw_result: Mapping[str, Any] | None, manifest: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(raw_result or {})
    score = _as_int(raw.get("score_delta", raw.get("score", 0)), 0)
    completed = _as_bool(raw.get("completed"), False)
    game_id = str(manifest.get("id") or raw.get("mode_id") or raw.get("mode") or "unknown_game")
    title = str(manifest.get("title") or raw.get("mode") or game_id)
    points = calculate_profile_points(score, completed, raw)
    return {
        "schema": CONTRACT_SCHEMA,
        "game_id": game_id,
        "mission_id": game_id,
        "quest_id": game_id,
        "title": title,
        "entry": str(manifest.get("entry", "main.py")),
        "engine": str(manifest.get("engine", "panda3d")),
        "completed": completed,
        "return_to_lab": True,
        "exit_to_desktop": False,
        "session_score": score,
        "score_delta": score,
        "profile_points_awarded": points,
        "prototype_lab_points_awarded": points,
        "quest_points_awarded": points,
        "badges": badges_for(raw, completed, score),
        "signal": str(raw.get("signal") or raw.get("memory_fragment") or ""),
        "stats": _stat_payload(raw),
        "raw_result": raw,
        "core_loop": manifest.get("core_loop", ""),
        "score_rules": manifest.get("score_rules", {}),
        "independence_status": manifest.get("independence_status", "standalone_game"),
        "timestamp_utc": now_iso(),
    }


def make_profile_preview(result: Mapping[str, Any]) -> dict[str, Any]:
    game_id = str(result.get("game_id", "unknown_game"))
    return {
        "schema": PROFILE_SCHEMA,
        "timestamp_utc": now_iso(),
        "profile_points_preview_delta": _as_int(result.get("profile_points_awarded"), 0),
        "prototype_lab_points_preview_delta": _as_int(result.get("prototype_lab_points_awarded", result.get("profile_points_awarded")), 0),
        "games": {
            game_id: {
                "completed": _as_bool(result.get("completed"), False),
                "best_score_preview": _as_int(result.get("session_score"), 0),
                "last_badges_preview": list(result.get("badges", []) or []),
                "last_signal_preview": str(result.get("signal", "")),
            }
        },
        "note": "Preview only. Direct launches keep local profile output; Prototype Lab should validate this result before saving shared quest points.",
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
        "# Prototype Lab Jump-In Mission Result\n\n"
        f"- Game: {result.get('title')} (`{result.get('game_id')}`)\n"
        f"- Completed: {result.get('completed')}\n"
        f"- Session score: {result.get('session_score')}\n"
        f"- Profile points awarded: {result.get('profile_points_awarded')}\n"
        f"- Exit to desktop: {result.get('exit_to_desktop')}\n"
        f"- Badges: {', '.join(result.get('badges', []) or [])}\n"
        f"- Signal: {result.get('signal', '')}\n"
    )
    md_path.write_text(md_text, encoding="utf-8")
    mission_md_path.write_text(md_text, encoding="utf-8")
    return {"game_result_json": str(json_path), "mission_result_json": str(mission_json_path), "game_result_md": str(md_path), "mission_result_md": str(mission_md_path), "profile_preview_json": str(profile_path)}


def handle_game_contract_cli(argv: list[str] | None = None, root: str | Path | None = None) -> int | None:
    args = list(sys.argv[1:] if argv is None else argv)
    if not any(flag in args for flag in CONTRACT_FLAGS):
        return None
    folder = Path(root or Path.cwd()).resolve()
    manifest = load_manifest(folder)
    status = {
        "schema": "glitched_matrix_standalone_game_contract_test_v1",
        "status": "PASS",
        "game_id": manifest.get("id"),
        "title": manifest.get("title"),
        "entry": manifest.get("entry"),
        "engine": manifest.get("engine"),
        "contract": manifest.get("game_contract", {}).get("schema", CONTRACT_SCHEMA),
        "independence_status": manifest.get("independence_status", "standalone_game"),
        "timestamp_utc": now_iso(),
    }
    if "--game-result-test" in args or "--complete-game-test" in args or "--profile-test" in args:
        sample = default_sample_result(manifest, completed="--complete-game-test" in args or "--game-result-test" in args)
        result = normalize_game_result(sample, manifest)
        paths = write_result_files(result, folder)
        status["result"] = result
        status["written"] = paths
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0
