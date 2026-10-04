from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from display_config import inherited_display_args, display_contract_self_test

GAME_IDS = {"enceladus", "mimas", "iapetus", "titan", "mars", "pluto", "europa", "triton", "starfall"}
GAME_ID_ALIASES = {
    "enceladus": "enceladus",
    "enceladus_ice": "enceladus",
    "ice": "enceladus",
    "mimas": "mimas",
    "mimas_snowfield": "mimas",
    "mimas_snow": "mimas",
    "snowfield": "mimas",
    "iapetus": "iapetus",
    "iapetus_ridge": "iapetus",
    "ridge": "iapetus",
    "cassini_regio": "iapetus",
    "titan": "titan",
    "titan_methane": "titan",
    "titan_methane_coast": "titan",
    "methane_coast": "titan",
    "pluto": "pluto",
    "pluto_ice": "pluto",
    "sputnik_planitia": "pluto",
    "pluto_nitrogen_frontier": "pluto",
    "mars": "mars",
    "mars_snow_caps": "mars",
    "snow_caps": "mars",
    "europa": "europa",
    "europa_depths": "europa",
    "triton": "triton",
    "triton_valleys": "triton",
    "starfall": "starfall",
    "starfall_salvage": "starfall",
    "salvage": "starfall",
}

MISSION_KEYS = {
    "enceladus": "enceladus_ice",
    "mimas": "mimas_snowfield",
    "iapetus": "iapetus_ridge",
    "titan": "titan_methane_coast",
    "pluto": "pluto_nitrogen_frontier",
    "mars": "mars_snow_caps",
    "europa": "europa_depths",
    "triton": "triton_valleys",
    "starfall": "operation_starfall_shell",
}

# In-game mission transport should feel like one built-in Prototype Lab route.
# Earlier passes used os.execv and called that “same screen,” but on Windows that
# can look exactly like the game closed if the replacement process stutters, fails,
# or exits.  The stable lane is a linked handoff: start the target mission as a
# normal child process using the same display contract, then let the source quit.
# This still avoids two long-lived ShowBase windows, but no longer destroys the
# running process before the next mission has actually been started.
DEFAULT_TRANSPORT_MODE = "linked_handoff"
DRY_RUN_ENV = "GMATRIX_TRANSPORT_DRY_RUN"
MODE_ENV = "GMATRIX_TRANSPORT_MODE"


def normalize_game_id(game_id: str) -> str:
    normalized = str(game_id).strip().lower().replace(" ", "_").replace("-", "_")
    return GAME_ID_ALIASES.get(normalized, normalized)


def _project_root(current_file: str | os.PathLike[str]) -> Path:
    here = Path(current_file).resolve().parent
    if here.name.lower() == "starfall salvage":
        return here.parent
    return here


def registry_path(current_file: str | os.PathLike[str]) -> Path:
    return _project_root(current_file) / "mission_registry.json"


def active_game_path(current_file: str | os.PathLike[str]) -> Path:
    return _project_root(current_file) / "active_game.json"


def reports_dir(current_file: str | os.PathLike[str]) -> Path:
    path = _project_root(current_file) / "verification" / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def transport_state_path(current_file: str | os.PathLike[str]) -> Path:
    return reports_dir(current_file) / "transport_state.json"


def target_script(game_id: str, current_file: str | os.PathLike[str]) -> Path:
    game_id = normalize_game_id(game_id)
    if game_id not in GAME_IDS:
        raise ValueError(f"Unknown linked game: {game_id}")
    base = _project_root(current_file)
    if game_id in {"enceladus", "mimas", "iapetus", "titan", "mars", "pluto", "europa", "triton"}:
        return base / "main.py"
    # Operation StarFall shell lives at the package root in the current build.
    # Keep the old folder fallback for archives that still have a Starfall Salvage subfolder.
    root_shell = base.parent / "main.py"
    if root_shell.exists():
        return root_shell
    return base / "Starfall Salvage" / "main.py"


def load_registry(current_file: str | os.PathLike[str]) -> dict[str, Any]:
    path = registry_path(current_file)
    if not path.exists():
        return {"registry_version": 0, "missions": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"registry_version": 0, "missions": []}


def mission_summary(current_file: str | os.PathLike[str]) -> list[dict[str, Any]]:
    registry = load_registry(current_file)
    out: list[dict[str, Any]] = []
    for mission in registry.get("missions", []):
        mid = mission.get("mission_id", "")
        target = normalize_game_id(mid)
        if target not in GAME_IDS:
            target = normalize_game_id(mission.get("game_id", mid))
        try:
            script = target_script(target, current_file)
        except Exception:
            script = _project_root(current_file) / str(mission.get("entry", ""))
        row = dict(mission)
        row["script"] = str(script)
        row["exists"] = script.exists()
        out.append(row)
    return out


def read_transport_state(current_file: str | os.PathLike[str]) -> dict[str, Any]:
    path = transport_state_path(current_file)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_transport_state(source: str, target: str, current_file: str | os.PathLike[str], *, reason: str = "button", extra: dict[str, Any] | None = None) -> Path:
    source_id = normalize_game_id(source)
    target_id = normalize_game_id(target)
    base = _project_root(current_file)
    payload: dict[str, Any] = {
        "transport_contract": "prototype_lab_link_v3",
        "source": source_id,
        "source_mission_id": MISSION_KEYS.get(source_id, source_id),
        "target": target_id,
        "target_mission_id": MISSION_KEYS.get(target_id, target_id),
        "reason": reason,
        "timestamp": int(time.time()),
        "base_dir": str(base),
        "target_script": str(target_script(target_id, current_file)),
        "return_supported": True,
        "launch_mode": DEFAULT_TRANSPORT_MODE,
        "display_mode": "reference_1080p_window",
        "same_screen_default": True,
        "handoff_method": "subprocess_then_source_exit",
        "moon_route": target_id in {"enceladus", "mimas", "iapetus", "titan", "mars", "pluto", "europa", "triton"},
    }
    if extra:
        payload.update(extra)
    out_path = transport_state_path(current_file)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return out_path


def write_active_game(target: str, current_file: str | os.PathLike[str]) -> Path:
    target_id = normalize_game_id(target)
    ordered_links = [MISSION_KEYS.get(target_id, target_id)]
    for mission_key in ["operation_starfall_shell", "mimas_snowfield", "enceladus_ice", "iapetus_ridge", "titan_methane_coast", "mars_snow_caps", "pluto_nitrogen_frontier", "europa_depths", "triton_valleys"]:
        if mission_key not in ordered_links:
            ordered_links.append(mission_key)
    payload = {
        "active_default": MISSION_KEYS.get(target_id, target_id),
        "active_runtime": MISSION_KEYS.get(target_id, target_id),
        "linked_games": ordered_links,
        "transport_mode": "embedded_world_return_controls_v2",
        "handoff_method": "subprocess_then_source_exit",
        "display_contract": "operation_starfall_reference_1080p_window_v3",
        "default_display_mode": "reference_1080p_window",
        "return_supported": True,
        "last_updated": int(time.time()),
    }
    path = active_game_path(current_file)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _requested_transport_mode() -> str:
    requested = os.environ.get(MODE_ENV, DEFAULT_TRANSPORT_MODE).strip().lower().replace("-", "_")
    if requested in {"exec", "same_process", "same_screen_exec", "in_place"}:
        return "same_screen_exec"
    if requested in {"same_screen", "handoff", "linked", "linked_handoff", "process", "separate", "separate_process"}:
        return DEFAULT_TRANSPORT_MODE
    return DEFAULT_TRANSPORT_MODE


def _transport_args(script: Path, extra_args: list[str] | None) -> list[str]:
    args = [sys.executable, str(script)]
    args.extend(inherited_display_args(sys.argv))
    if extra_args:
        args.extend(extra_args)
    return args


def launch_linked_game(source: str, target: str, current_file: str | os.PathLike[str], extra_args: list[str] | None = None, *, reason: str = "button") -> bool:
    target_id = normalize_game_id(target)
    script = target_script(target_id, current_file)
    auto_args: list[str] = []
    if target_id in {"enceladus", "mimas", "iapetus", "titan", "mars", "pluto", "europa", "triton"}:
        auto_args.append(f"--moon={target_id}")
    combined_args = list(extra_args or [])
    for arg in auto_args:
        if arg not in combined_args:
            combined_args.append(arg)
    if not script.exists():
        return False
    mode = _requested_transport_mode()
    write_transport_state(source, target_id, current_file, reason=reason, extra={"launch_mode": mode})
    write_active_game(target_id, current_file)
    args = _transport_args(script, combined_args)
    if os.environ.get(DRY_RUN_ENV) == "1":
        return True
    try:
        if mode == "same_screen_exec":
            # Legacy/debug mode only.  This can look like a hard close on Windows,
            # so it is no longer the default route.
            os.chdir(str(script.parent))
            os.execv(sys.executable, args)
        import subprocess
        subprocess.Popen(args, cwd=str(script.parent))
        return True
    except Exception as exc:
        try:
            error_path = reports_dir(current_file) / "transport_error.json"
            error_path.write_text(json.dumps({
                "source": normalize_game_id(source),
                "target": target_id,
                "mode": mode,
                "args": args,
                "error": repr(exc),
                "timestamp": int(time.time()),
            }, indent=2), encoding="utf-8")
        except Exception:
            pass
        return False
    return False


def transport_link_self_test(current_file: str | os.PathLike[str]) -> dict[str, object]:
    enc = target_script("enceladus", current_file)
    mim = target_script("mimas", current_file)
    iap = target_script("iapetus", current_file)
    tit = target_script("titan", current_file)
    mar = target_script("mars", current_file)
    plu = target_script("pluto", current_file)
    eur = target_script("europa", current_file)
    tri = target_script("triton", current_file)
    star = target_script("starfall", current_file)
    registry = mission_summary(current_file)
    display_contract = display_contract_self_test(_project_root(current_file))
    return {
        "contract": "prototype_lab_link_v3",
        "launch_mode": DEFAULT_TRANSPORT_MODE,
        "handoff_method": "subprocess_then_source_exit",
        "legacy_exec_mode_env": MODE_ENV,
        "dry_run_env": DRY_RUN_ENV,
        "mode_env": MODE_ENV,
        "display_contract": {
            "mode": display_contract.get("default_mode"),
            "size": display_contract.get("default_size"),
            "same_screen_default": display_contract.get("default_mode") in {"reference_1080p_window", "desktop_resizable_window", "standard_bordered_window", "large_bordered_window", "windowed_fullscreen"},
        },
        "enceladus_exists": enc.exists(),
        "mimas_exists": mim.exists(),
        "iapetus_exists": iap.exists(),
        "titan_exists": tit.exists(),
        "mars_exists": mar.exists(),
        "pluto_exists": plu.exists(),
        "europa_exists": eur.exists(),
        "triton_exists": tri.exists(),
        "starfall_exists": star.exists(),
        "enceladus_script": str(enc),
        "mimas_script": str(mim),
        "iapetus_script": str(iap),
        "titan_script": str(tit),
        "mars_script": str(mar),
        "pluto_script": str(plu),
        "europa_script": str(eur),
        "triton_script": str(tri),
        "starfall_script": str(star),
        "registry_count": len(registry),
        "registry_entries_exist": all(bool(row.get("exists")) for row in registry) if registry else False,
        "active_game_path": str(active_game_path(current_file)),
        "transport_state_path": str(transport_state_path(current_file)),
    }
