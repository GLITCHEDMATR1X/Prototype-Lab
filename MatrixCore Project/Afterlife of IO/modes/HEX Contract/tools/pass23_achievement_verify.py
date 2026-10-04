"""Pass 23 platform achievement verifier. No pygame import required."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from game.achievements import ACHIEVEMENTS, AchievementTracker, ensure_achievement_state, gamerscore_total

MANIFEST = ROOT / "platform/xbox/achievements_manifest.json"
PASS22 = Path("/mnt/data/hex_pass22_authority/HEX Contract")
FROZEN_PASS22 = ("main.py","game/data.py","game/sim.py","game/actors.py","game/actor_visuals.py","game/audio.py","game/render.py","game/world_data.py","game/world.py")

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def profile_fixture() -> dict:
    heroes = {k: {"successes": 0, "restorations": 0} for k in ("nyx", "circuit", "vesper", "morrow")}
    bonds = {"nyx|circuit": {"mastery": 0}, "nyx|vesper": {"mastery": 0}, "nyx|morrow": {"mastery": 0}, "circuit|vesper": {"mastery": 0}, "circuit|morrow": {"mastery": 0}, "vesper|morrow": {"mastery": 0}}
    return {
        "profile_version": 9,
        "guild": {"sidekick_perks": 0, "roster_wipes": 0, "bosses_defeated": 0, "lifetime_credits": 0},
        "campaign": {"aftermath_counts": {"purge": 0, "recovery": 0, "rescue": 0}, "chain_completions": 0, "bond_events_resolved": 0},
        "heroes": heroes,
        "bonds": bonds,
    }


class MissionStub:
    def __init__(self, quest="purge", layout="L1", sidekicks=(), status="SUCCESS"):
        self.quest_key = quest; self.world_layout_name = layout; self.sidekick_keys = tuple(sidekicks); self.status = status


def unlocked(profile, key): return bool(profile["achievements"]["unlocked"].get(key, False))


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = manifest["achievements"]
    frozen = {rel: (PASS22/rel).exists() and sha(ROOT/rel) == sha(PASS22/rel) for rel in FROZEN_PASS22}
    checks = {
        "pass22_gameplay_world_render_frozen": all(frozen.values()),
        "manifest_count_16": len(entries) == 16 == len(ACHIEVEMENTS),
        "gamerscore_exact_1000": sum(int(e["gamerscore"]) for e in entries) == gamerscore_total() == 1000,
        "gamerscore_each_0_200": all(0 <= int(e["gamerscore"]) <= 200 for e in entries),
        "unique_internal_ids": len({e["internal_id"] for e in entries}) == len(entries),
        "unique_partner_ids": len({e["partner_center_id"] for e in entries}) == len(entries),
        "descriptions_under_100": all(len(e["locked_description"]) <= 100 and len(e["unlocked_description"]) <= 100 for e in entries),
        "art_contract_1920x1080_png": all(e["image"]["required_size"] == [1920,1080] and e["image"]["format"] == "png" for e in entries),
        "all_base_public": all(e["base"] and e["visibility"] == "public" for e in entries),
        "title_managed": manifest["achievement_system"] == "title-managed",
    }

    p = profile_fixture(); t = AchievementTracker(p); t.evaluate_all()
    checks["fresh_profile_unlocks_none"] = not any(p["achievements"]["unlocked"].values())

    # 1 Contract Proven + 15 veteran progress
    p["heroes"]["nyx"]["successes"] = 1; t.evaluate_all()
    checks["first_contract"] = unlocked(p, "HC_001_FIRST_CONTRACT") and p["achievements"]["progress"]["HC_015_CONTRACT_VETERAN"] == 4
    # 2-4 sovereigns, 5 chain
    p["campaign"]["aftermath_counts"].update({"purge":1,"recovery":1,"rescue":1}); p["campaign"]["chain_completions"] = 1; t.evaluate_all()
    checks["three_sovereigns"] = all(unlocked(p,k) for k in ("HC_002_SAINT_BROKEN","HC_003_BLACKGLASS_CRACKED","HC_004_LAST_STOP"))
    checks["sovereign_chain"] = unlocked(p,"HC_005_SOVEREIGN_CHAIN")
    # 6 every lead hero
    for h in p["heroes"].values(): h["successes"] = max(1, int(h["successes"]))
    t.evaluate_all(); checks["every_hand"] = unlocked(p,"HC_006_EVERY_HAND")
    # 7 banked perk event
    t.record_sidekick_perk_banked(); checks["favor_reserve"] = unlocked(p,"HC_007_FAVOR_RESERVE")
    # 8 full squad win
    t.record_mission_result(MissionStub(layout="Broken Nave Labyrinth", sidekicks=("circuit","vesper"))); checks["three_against"] = unlocked(p,"HC_008_THREE_AGAINST")
    # 9 mastery
    p["bonds"]["nyx|circuit"]["mastery"] = 1; t.evaluate_all(); checks["hex_linked"] = unlocked(p,"HC_009_HEX_LINKED")
    # 10 restore
    p["heroes"]["vesper"]["restorations"] = 1; t.evaluate_all(); checks["nobody_stays_dead"] = unlocked(p,"HC_010_NOBODY_STAYS_DEAD")
    # 11 last light
    p["guild"]["roster_wipes"] = 1; t.evaluate_all(); checks["last_light"] = unlocked(p,"HC_011_LAST_LIGHT")
    # 12 all nine approved layouts
    quests = ("purge","recovery","rescue")
    for q in quests:
        for i in range(3): t.record_mission_result(MissionStub(q, f"layout-{i+1}"))
    checks["every_way_through"] = unlocked(p,"HC_012_EVERY_WAY_THROUGH") and len(p["achievements"]["stats"]["approved_layout_wins"]) >= 9
    # 13 bonds
    p["campaign"]["bond_events_resolved"] = 6; t.evaluate_all(); checks["bound_by_choice"] = unlocked(p,"HC_013_BOUND_BY_CHOICE")
    # 14 sovereign hunter
    p["guild"]["bosses_defeated"] = 10; t.evaluate_all(); checks["sovereign_hunter"] = unlocked(p,"HC_014_SOVEREIGN_HUNTER")
    # 15 veteran exactly 25 wins
    p["heroes"]["nyx"]["successes"] = 22; p["heroes"]["circuit"]["successes"] = 1; p["heroes"]["vesper"]["successes"] = 1; p["heroes"]["morrow"]["successes"] = 1; t.evaluate_all()
    checks["contract_veteran"] = unlocked(p,"HC_015_CONTRACT_VETERAN")
    # 16 fortune
    p["guild"]["lifetime_credits"] = 10000; t.evaluate_all(); checks["guild_fortune"] = unlocked(p,"HC_016_GUILD_FORTUNE")
    checks["all_16_unlockable"] = sum(1 for v in p["achievements"]["unlocked"].values() if v) == 16

    # Monotonic update contract
    before = p["achievements"]["progress"]["HC_016_GUILD_FORTUNE"]
    p["guild"]["lifetime_credits"] = 1; t.evaluate_all()
    after = p["achievements"]["progress"]["HC_016_GUILD_FORTUNE"]
    checks["progress_never_decreases"] = before == after == 100
    # Queue / adapter contract
    pending_before = dict(p["achievements"]["pending_platform_updates"])
    failed = t.sync_pending(lambda achievement_id, pct: False)
    checks["failed_sync_retains_queue"] = bool(failed["failed"]) and p["achievements"]["pending_platform_updates"] == pending_before
    sent = t.sync_pending(lambda achievement_id, pct: True)
    checks["successful_sync_clears_queue"] = bool(sent["sent"]) and not p["achievements"]["pending_platform_updates"]

    # Pass22 -> Pass23 migration, including no invented spent-perk history.
    legacy = profile_fixture(); legacy["profile_version"] = 8; legacy["guild"]["sidekick_perks"] = 2
    state = ensure_achievement_state(legacy)
    checks["v8_state_migration"] = state["schema_version"] == 1 and state["stats"]["sidekick_perks_earned"] == 2

    app = (ROOT/"game/app.py").read_text(encoding="utf-8")
    checks["runtime_hooks_present"] = all(token in app for token in (
        "AchievementTracker(self.profile)", "record_sidekick_perk_banked()", "record_mission_result(self.mission)", "self.achievement_tracker.evaluate_all()"
    ))
    checks["profile_schema_v9"] = '"profile_version": 9' in app and 'profile["profile_version"] = 9' in app
    checks["gdk_not_hard_dependency"] = "XblAchievementsUpdateAchievementAsync" not in app and "xbox" not in (ROOT/"requirements.txt").read_text(encoding="utf-8").lower()

    ok = all(checks.values())
    payload = {
        "pass23_platform_achievement_foundation": "PASS" if ok else "FAIL",
        "checks": checks,
        "achievement_count": len(entries),
        "gamerscore": sum(int(e["gamerscore"]) for e in entries),
        "maximum_single_gamerscore": max(int(e["gamerscore"]) for e in entries),
        "final_unlocked_count": sum(1 for v in p["achievements"]["unlocked"].values() if v),
        "partner_center_placeholders_remaining": manifest["partner_center_title_id"].startswith("REPLACE_") or manifest["partner_center_scid"].startswith("REPLACE_"),
        "native_gdk_bridge_required": True,
        "frozen_pass22_modules": frozen,
    }
    out = ROOT/"verification/reports/pass23_achievement_foundation.json"; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    print(json.dumps(payload,indent=2))
    return 0 if ok else 1

if __name__ == "__main__": raise SystemExit(main())
