"""Blank-profile campaign, relaunch, save, and result-contract endurance test."""
from __future__ import annotations

import json
import os
from pathlib import Path
import resource
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.app import App, parse_args

REPORTS = ROOT / "verification" / "reports"


def run_mission(app: App, hero: str, quest: str, equipment: str, order: str, support: str) -> dict:
    app.selected_hero = hero
    app.selected_quest = quest
    app.selected_equipment = equipment
    app.selected_order = order
    app.selected_support = support
    mission = app._new_mission(hero, quest)
    for _ in range(3400):
        mission.update(0.05)
        if mission.status != "ACTIVE":
            break
    if mission.status == "ACTIVE":
        mission.status = "FAILED"
        mission.result_reason = "RC1 endurance observation window expired"
        mission._finalize_result()
    app.mission = mission
    app.result_applied = False
    app._apply_mission_result()
    return mission.report()


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    profile = REPORTS / "pass13_endurance_profile.json"
    result = REPORTS / "hex_contract_game_result.json"
    for path in (profile, profile.with_suffix(profile.suffix + ".bak"), profile.with_suffix(profile.suffix + ".tmp"), result):
        path.unlink(missing_ok=True)

    app = App(parse_args(["--no-audio", "--profile", str(profile)]))
    rows = []
    plan = [
        ("nyx", "purge", "ampoule", "eliminate", "circuit"),
        ("vesper", "recovery", "surveyor", "objective", "morrow"),
        ("circuit", "rescue", "beacon", "protect", "vesper"),
    ]
    for cycle in range(4):
        for hero, quest, equipment, order, support in plan:
            report = run_mission(app, hero, quest, equipment, order, support)
            rows.append({"cycle": cycle + 1, **{key: report[key] for key in ("hero", "quest", "status", "time", "hero_hp", "strain_delta", "reward_credits", "boss_defeated")}})
            assert report["status"] == "SUCCESS"
            if app.profile["campaign"].get("pending_bond_event"):
                assert app._resolve_bond_event("boundary")
        app._save_profile()
        app = App(parse_args(["--no-audio", "--profile", str(profile)]))
        assert app.profile["campaign"]["chain_completions"] == cycle + 1
        assert app.profile["guild"]["contracts"] == (cycle + 1) * 3
        assert all(record["availability"] == "ACTIVE" for record in app.profile["heroes"].values())

    assert result.exists()
    result_payload = json.loads(result.read_text(encoding="utf-8"))
    assert result_payload["completed"] is True and result_payload["return_to_lab"] is True
    before = profile.stat().st_size
    for _ in range(30):
        app._save_profile()
    after = profile.stat().st_size
    reloaded = App(parse_args(["--no-audio", "--profile", str(profile)]))

    payload = {
        "pass": 13,
        "blank_profile_campaigns": 4,
        "actual_contracts_completed": len(rows),
        "rows": rows,
        "chain_completions": reloaded.profile["campaign"]["chain_completions"],
        "guild_contracts": reloaded.profile["guild"]["contracts"],
        "active_heroes": [key for key, record in reloaded.profile["heroes"].items() if record["availability"] == "ACTIVE"],
        "save_size_before_rewrites": before,
        "save_size_after_rewrites": after,
        "save_size_stable": before == after,
        "result_contract": {
            "project_id": result_payload["project_id"],
            "return_to_lab": result_payload["return_to_lab"],
            "runtime_wrapper_required": result_payload["runtime_wrapper_required"],
        },
        "peak_rss_kb": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
    }
    checks = [
        payload["chain_completions"] == 4,
        payload["guild_contracts"] == 12,
        len(payload["active_heroes"]) == 4,
        payload["save_size_stable"],
        payload["result_contract"]["return_to_lab"],
        payload["result_contract"]["runtime_wrapper_required"] is False,
    ]
    payload["final_result"] = "PASS" if all(checks) else "FAIL"
    out = REPORTS / "pass13_endurance.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    for path in (profile, profile.with_suffix(profile.suffix + ".bak"), profile.with_suffix(profile.suffix + ".tmp"), result):
        path.unlink(missing_ok=True)
    print(json.dumps({k: payload[k] for k in ("final_result", "actual_contracts_completed", "chain_completions", "guild_contracts", "save_size_stable", "peak_rss_kb")}, indent=2))
    return 0 if payload["final_result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
