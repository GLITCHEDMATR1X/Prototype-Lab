from __future__ import annotations

"""Platform-neutral achievement tracking for HEX CONTRACT.

Pass 23 keeps gameplay achievement logic independent from Xbox GDK libraries.
The tracker stores monotonic local progress and queues the latest title-managed
percentage for a future native Xbox bridge. A Windows GDK wrapper only needs to
provide an update callback that mirrors XblAchievementsUpdateAchievementAsync.
"""

from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class AchievementDefinition:
    key: str
    partner_id: str
    name: str
    gamerscore: int
    locked_description: str
    unlocked_description: str
    target: int
    metric: str
    base: bool = True
    secret: bool = False


ACHIEVEMENTS: tuple[AchievementDefinition, ...] = (
    AchievementDefinition("HC_001_FIRST_CONTRACT", "1", "Contract Proven", 25,
        "Complete your first contract.", "You completed your first contract.", 1, "successful_contracts"),
    AchievementDefinition("HC_002_SAINT_BROKEN", "2", "Saint Broken", 50,
        "Defeat the sovereign of Saint Voltage.", "Saint Voltage's sovereign has fallen.", 1, "purge_sovereigns"),
    AchievementDefinition("HC_003_BLACKGLASS_CRACKED", "3", "Blackglass Cracked", 50,
        "Defeat the sovereign guarding Blackglass.", "Blackglass no longer has its sovereign guardian.", 1, "recovery_sovereigns"),
    AchievementDefinition("HC_004_LAST_STOP", "4", "Last Stop", 50,
        "Defeat the sovereign of Pilgrim Ossuary.", "Pilgrim Ossuary's sovereign has fallen.", 1, "rescue_sovereigns"),
    AchievementDefinition("HC_005_SOVEREIGN_CHAIN", "5", "Sovereign Chain", 100,
        "Complete the full three-contract Sovereign Chain.", "You completed the Sovereign Chain.", 1, "chain_completions"),
    AchievementDefinition("HC_006_EVERY_HAND", "6", "Every Hand Has a Hex", 75,
        "Win a contract as the lead with each of the four heroes.", "Every hero has led a winning contract.", 4, "winning_lead_heroes"),
    AchievementDefinition("HC_007_FAVOR_RESERVE", "7", "Favor in Reserve", 25,
        "Bank your first Sidekick Perk.", "You banked a Sidekick Perk for a later contract.", 1, "sidekick_perks_earned"),
    AchievementDefinition("HC_008_THREE_AGAINST", "8", "Three Against the Contract", 75,
        "Win a contract with a full three-hero squad.", "A full three-hero squad completed a contract.", 1, "full_squad_wins"),
    AchievementDefinition("HC_009_HEX_LINKED", "9", "HEX Linked", 50,
        "Reach Link Mastery with any hero pair.", "A hero pair reached Link Mastery.", 1, "mastered_bonds"),
    AchievementDefinition("HC_010_NOBODY_STAYS_DEAD", "10", "Nobody Stays Dead", 50,
        "Restore an eliminated hero after a victory.", "An eliminated hero returned to the roster.", 1, "hero_restorations"),
    AchievementDefinition("HC_011_LAST_LIGHT", "11", "Last Light", 50,
        "Recover from a complete roster wipe and begin a new guild cycle.", "The Last Light Protocol began a new guild cycle.", 1, "roster_wipes"),
    AchievementDefinition("HC_012_EVERY_WAY_THROUGH", "12", "Every Way Through", 100,
        "Win on all nine approved broken-maze layouts.", "You won on every approved broken-maze layout.", 9, "approved_layout_wins"),
    AchievementDefinition("HC_013_BOUND_BY_CHOICE", "13", "Bound by Choice", 100,
        "Resolve six bond events.", "You resolved six bond events.", 6, "bond_events_resolved"),
    AchievementDefinition("HC_014_SOVEREIGN_HUNTER", "14", "Sovereign Hunter", 75,
        "Defeat ten sovereigns.", "You defeated ten sovereigns.", 10, "bosses_defeated"),
    AchievementDefinition("HC_015_CONTRACT_VETERAN", "15", "Contract Veteran", 75,
        "Win twenty-five contracts.", "You won twenty-five contracts.", 25, "successful_contracts"),
    AchievementDefinition("HC_016_GUILD_FORTUNE", "16", "Guild Fortune", 50,
        "Earn 10,000 lifetime credits.", "The guild earned 10,000 lifetime credits.", 10000, "lifetime_credits"),
)

DEFINITIONS = {a.key: a for a in ACHIEVEMENTS}
BY_PARTNER_ID = {a.partner_id: a for a in ACHIEVEMENTS}


def _default_state() -> dict:
    return {
        "schema_version": 1,
        "progress": {a.key: 0 for a in ACHIEVEMENTS},
        "unlocked": {a.key: False for a in ACHIEVEMENTS},
        "pending_platform_updates": {},
        "stats": {
            "approved_layout_wins": [],
            "sidekick_perks_earned": 0,
            "full_squad_wins": 0,
        },
    }


def ensure_achievement_state(profile: dict) -> dict:
    state = profile.setdefault("achievements", _default_state())
    if not isinstance(state, dict):
        state = _default_state()
        profile["achievements"] = state
    state["schema_version"] = 1
    progress = state.setdefault("progress", {})
    unlocked = state.setdefault("unlocked", {})
    pending = state.setdefault("pending_platform_updates", {})
    stats = state.setdefault("stats", {})
    if not isinstance(progress, dict): progress = {}; state["progress"] = progress
    if not isinstance(unlocked, dict): unlocked = {}; state["unlocked"] = unlocked
    if not isinstance(pending, dict): pending = {}; state["pending_platform_updates"] = pending
    if not isinstance(stats, dict): stats = {}; state["stats"] = stats
    wins = stats.get("approved_layout_wins", [])
    if not isinstance(wins, list): wins = []
    stats["approved_layout_wins"] = sorted({str(v) for v in wins})
    stats["sidekick_perks_earned"] = max(0, int(stats.get("sidekick_perks_earned", 0)))
    stats["full_squad_wins"] = max(0, int(stats.get("full_squad_wins", 0)))
    # Pass 22 -> 23 best-effort migration: current banked perks prove at least
    # that many perks have been earned, but spent historical perks cannot be inferred.
    current_perks = max(0, int(profile.get("guild", {}).get("sidekick_perks", 0)))
    stats["sidekick_perks_earned"] = max(stats["sidekick_perks_earned"], current_perks)
    for achievement in ACHIEVEMENTS:
        progress[achievement.key] = max(0, min(100, int(progress.get(achievement.key, 0))))
        unlocked[achievement.key] = bool(unlocked.get(achievement.key, False) or progress[achievement.key] >= 100)
    return state


def _metric_value(profile: dict, metric: str) -> int:
    guild = profile.get("guild", {})
    campaign = profile.get("campaign", {})
    heroes = profile.get("heroes", {})
    bonds = profile.get("bonds", {})
    state = ensure_achievement_state(profile)
    stats = state["stats"]
    if metric == "successful_contracts":
        return sum(max(0, int(record.get("successes", 0))) for record in heroes.values() if isinstance(record, dict))
    if metric == "purge_sovereigns":
        return max(0, int(campaign.get("aftermath_counts", {}).get("purge", 0)))
    if metric == "recovery_sovereigns":
        return max(0, int(campaign.get("aftermath_counts", {}).get("recovery", 0)))
    if metric == "rescue_sovereigns":
        return max(0, int(campaign.get("aftermath_counts", {}).get("rescue", 0)))
    if metric == "chain_completions":
        return max(0, int(campaign.get("chain_completions", 0)))
    if metric == "winning_lead_heroes":
        return sum(1 for record in heroes.values() if isinstance(record, dict) and int(record.get("successes", 0)) > 0)
    if metric == "sidekick_perks_earned":
        return int(stats.get("sidekick_perks_earned", 0))
    if metric == "full_squad_wins":
        return int(stats.get("full_squad_wins", 0))
    if metric == "mastered_bonds":
        return sum(1 for record in bonds.values() if isinstance(record, dict) and int(record.get("mastery", 0)) > 0)
    if metric == "hero_restorations":
        return sum(max(0, int(record.get("restorations", 0))) for record in heroes.values() if isinstance(record, dict))
    if metric == "roster_wipes":
        return max(0, int(guild.get("roster_wipes", 0)))
    if metric == "approved_layout_wins":
        return len(stats.get("approved_layout_wins", []))
    if metric == "bond_events_resolved":
        return max(0, int(campaign.get("bond_events_resolved", 0)))
    if metric == "bosses_defeated":
        return max(0, int(guild.get("bosses_defeated", 0)))
    if metric == "lifetime_credits":
        return max(0, int(guild.get("lifetime_credits", 0)))
    return 0


def _percent(value: int, target: int) -> int:
    if target <= 0: return 100
    return max(0, min(100, int((max(0, value) * 100) // target)))


class AchievementTracker:
    """Owns monotonic achievement state and platform-update queueing."""

    def __init__(self, profile: dict):
        self.profile = profile
        self.state = ensure_achievement_state(profile)
        self.recent_unlocks: list[str] = []

    def record_mission_result(self, mission) -> list[str]:
        if getattr(mission, "status", "ACTIVE") == "SUCCESS":
            stats = self.state["stats"]
            layout_token = f"{mission.quest_key}|{mission.world_layout_name}"
            wins = set(stats.get("approved_layout_wins", []))
            wins.add(layout_token)
            stats["approved_layout_wins"] = sorted(wins)
            if len(tuple(getattr(mission, "sidekick_keys", ()))) >= 2:
                stats["full_squad_wins"] = int(stats.get("full_squad_wins", 0)) + 1
        return self.evaluate_all()

    def record_sidekick_perk_banked(self) -> list[str]:
        stats = self.state["stats"]
        stats["sidekick_perks_earned"] = int(stats.get("sidekick_perks_earned", 0)) + 1
        return self.evaluate_all()

    def evaluate_all(self) -> list[str]:
        newly_unlocked: list[str] = []
        for achievement in ACHIEVEMENTS:
            value = _metric_value(self.profile, achievement.metric)
            pct = _percent(value, achievement.target)
            old = int(self.state["progress"].get(achievement.key, 0))
            if pct > old:
                self.state["progress"][achievement.key] = pct
                current = int(self.state["pending_platform_updates"].get(achievement.partner_id, 0))
                self.state["pending_platform_updates"][achievement.partner_id] = max(current, pct)
            if pct >= 100 and not self.state["unlocked"].get(achievement.key, False):
                self.state["unlocked"][achievement.key] = True
                newly_unlocked.append(achievement.key)
        if newly_unlocked:
            self.recent_unlocks.extend(newly_unlocked)
        return newly_unlocked

    def pending_updates(self) -> list[tuple[str, int]]:
        return sorted(((str(k), int(v)) for k, v in self.state["pending_platform_updates"].items()), key=lambda item: int(item[0]))

    def sync_pending(self, update_callback: Callable[[str, int], bool]) -> dict:
        """Try queued title-managed updates through a future GDK bridge callback.

        The callback receives Partner Center achievement ID + monotonic percent.
        Return True only after the native service accepted/queued the update.
        """
        sent: list[str] = []
        failed: list[str] = []
        for partner_id, percent in self.pending_updates():
            try:
                ok = bool(update_callback(partner_id, percent))
            except Exception:
                ok = False
            if ok:
                self.state["pending_platform_updates"].pop(partner_id, None)
                sent.append(partner_id)
            else:
                failed.append(partner_id)
        return {"sent": sent, "failed": failed}


def gamerscore_total() -> int:
    return sum(a.gamerscore for a in ACHIEVEMENTS)
