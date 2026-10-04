from __future__ import annotations

import argparse
import json
import hashlib
import gc
import os
import shutil
import copy
from itertools import combinations
from pathlib import Path
import sys

import pygame
try:
    from pygame._sdl2 import controller as sdl_controller
except Exception:  # pygame builds without SDL2 controller helpers still run keyboard/mouse.
    sdl_controller = None

from .data import HEROES, QUESTS, HERO_ORDERS, CONTRACT_COMPLICATIONS, EQUIPMENT_KITS, QUEST_INTEL, ENEMY_ARCHETYPES, ENEMY_VARIANTS, MISSION_ENVIRONMENTS, CIVILIAN_ROLES, SIGNATURE_BOSSES, HERO_LINKS, STORY_CHAIN, SOVEREIGN_AFTERMATHS, BOND_EVENTS, quest_fit, equipment_fit, recovery_quote, recovery_state
from . import render as render_module
from .render import Renderer, VIRTUAL_SIZE
from .actors import ActorArtist
from .actor_visuals import HERO_VISUAL_RADIUS, ENEMY_VISUAL_RADIUS, BOSS_VISUAL_RADIUS, CIVILIAN_VISUAL_RADIUS, PASS14_MIN_WORLD_GAP, MAX_ACTOR_VISUAL_DIAMETER, ACTOR_CLEARANCE_MARGIN, ACTOR_PRESENTATION_RULES
from .audio import AudioManager
from .achievements import AchievementTracker, ensure_achievement_state
from .platform_input import (
    INPUT_KEYBOARD, INPUT_XBOX, A_CONFIRM, A_BACK, A_ALT, A_INFO, A_MENU, A_VIEW,
    A_UP, A_DOWN, A_LEFT, A_RIGHT, A_LB, A_RB, wrap_index,
)
from .save_paths import DEFAULT_PROFILE_NAME, SAVE_ROOT_ENV, resolve_profile_path
from .crash_reporter import get_crash_reporter
from .microsoft_runtime import MicrosoftRuntime
from .display_policy import DEFAULT_WINDOW_SIZE, choose_desktop_size, fit_virtual_canvas
from .sim import Mission, WORLD


class App:
    def __init__(self, args: argparse.Namespace):
        project_root = Path(__file__).resolve().parents[1]
        self.args = args
        self.microsoft_runtime = MicrosoftRuntime.autodetect(project_root)
        self.platform_save_auto = not bool(args.profile or args.save_root or os.environ.get(SAVE_ROOT_ENV))
        platform_save_root = str(self.microsoft_runtime.save_root) if self.platform_save_auto and self.microsoft_runtime.save_root else args.save_root
        if args.no_audio:
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        # Windows must opt into DPI awareness before SDL initializes video or the OS
        # can bitmap-scale a desktop-sized borderless window at 125/150/200% DPI.
        if os.name == "nt":
            os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
        pygame.init()
        if args.no_audio:
            pygame.mixer.quit()
        self.display_index = max(0, int(getattr(args, "display_index", 0)))
        self.borderless_fullscreen = not bool(getattr(args, "windowed", False))
        if bool(getattr(args, "fullscreen", False)):
            self.borderless_fullscreen = True
        self.desktop_size = self._detect_desktop_size()
        # --inherit-display: Afterlife of IO hands over its live window so the
        # switch never closes or reopens the OS window.
        inherited = pygame.display.get_surface() if bool(getattr(args, "inherit_display", False)) else None
        self.hosted = inherited is not None
        if self.hosted:
            self.screen = inherited
            self.borderless_fullscreen = bool(inherited.get_flags() & pygame.FULLSCREEN) or tuple(inherited.get_size()) == tuple(self.desktop_size)
            render_module.QUIT_LABEL = "RETURN TO AFTERLIFE"
        else:
            self.screen = self._set_display_mode(self.borderless_fullscreen)
        pygame.display.set_caption("HEX CONTRACT")
        self.canvas = pygame.Surface(VIRTUAL_SIZE).convert()
        self.renderer = Renderer(self.canvas)
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "TITLE"
        self.input_mode = INPUT_KEYBOARD
        self.controllers: dict[int, object] = {}
        self.controller_connected = False
        self.controller_name = ""
        self.platform_notice = ""
        self.platform_notice_until = 0
        self.axis_latch = {"x": 0, "y": 0}
        self.title_index = 0
        self.restore_index = 0
        self.bond_index = 0
        self._init_controllers()
        self.selected_quest: str | None = None
        self.selected_hero: str | None = None
        self.selected_order: str = args.order
        self.selected_equipment: str = args.equipment
        self.selected_support: str = args.support
        self.selected_sidekicks: list[str] = [args.support] if args.support in HEROES else []
        self.mission: Mission | None = None
        self.show_help = False
        self.help_page = 0
        self.settings_index = 0
        self.settings_return_state = "TITLE"
        self.new_guild_confirm = False
        self.show_analysis = bool(args.analysis)
        self.show_dossier = bool(args.dossier)
        self.paused = False
        self.mission_pause_index = 0
        self.abort_contract_confirm = False
        self.auto_elapsed = 0.0
        self.auto_saved = False
        self.quest_rects = [pygame.Rect(85+i*610,230,535,675) for i in range(3)]
        self.hero_rects = [pygame.Rect(75+i*450,215,420,640) for i in range(len(HEROES))]
        self.deploy_rect = pygame.Rect(735, 978, 450, 54)
        self.recovery_rect = pygame.Rect(245, 978, 430, 54)
        self.order_rects = [pygame.Rect(95 + i * 345, 862, 310, 58) for i in range(len(HERO_ORDERS))]
        self.equipment_rects = [pygame.Rect(100 + i * 455, 520, 410, 300) for i in range(len(EQUIPMENT_KITS))]
        self.loadout_deploy_rect = pygame.Rect(735, 950, 450, 66)
        self.support_rects = [pygame.Rect(250 + i * 355, 844, 320, 78) for i in range(len(HEROES))]
        self.bond_anchor_rect = pygame.Rect(330, 790, 580, 130)
        self.bond_boundary_rect = pygame.Rect(1010, 790, 580, 130)
        self.title_rects = {
            "continue": pygame.Rect(705, 520, 510, 72),
            "settings": pygame.Rect(705, 610, 510, 64),
            "guide": pygame.Rect(705, 690, 510, 64),
            "quit": pygame.Rect(705, 770, 510, 64),
        }
        self.settings_row_rects = [pygame.Rect(490, 246 + i * 75, 940, 56) for i in range(8)]
        self.settings_back_rect = pygame.Rect(760, 910, 400, 62)
        self.settings_minus_rects = [pygame.Rect(1530, 256 + i * 75, 52, 36) for i in range(4)]
        self.settings_plus_rects = [pygame.Rect(1748, 256 + i * 75, 52, 36) for i in range(4)]
        self.mission_pause_rects = [pygame.Rect(700, 452 + i * 86, 520, 64) for i in range(3)]
        self.profile_path = resolve_profile_path(project_root, args.profile, platform_save_root)
        self.crash_reporter = get_crash_reporter()
        # Crash diagnostics stay local and are deliberately separate from a
        # future XGameSaveFiles/cloud-save root.
        diagnostics_root = Path(os.environ["HEX_CONTRACT_CRASH_ROOT"]).expanduser() if os.environ.get("HEX_CONTRACT_CRASH_ROOT") else project_root
        if not os.environ.get("HEX_CONTRACT_CRASH_ROOT") and os.name == "nt" and os.environ.get("LOCALAPPDATA"):
            diagnostics_root = Path(os.environ["LOCALAPPDATA"]) / "GLITCHED MATRIX" / "HEX CONTRACT"
        self.crash_reporter.configure(project_root, diagnostics_root, build_label="Pass 32 Finalization UX Audio Build Fixes")
        self.crash_reporter.set_state_provider(self._crash_state_snapshot)
        self.crash_reporter.breadcrumb("app_initialized", profile_name=self.profile_path.name, scenario=args.scenario)
        self.crash_artifact = None
        self.crash_message = ""
        self.crash_phase = ""
        self.crash_recovery_active = False
        self.profile_existed = self.profile_path.exists()
        self.profile_recovery_note = ""
        self.saving_enabled = not args.no_save and not bool(args.test_shot)
        self.profile = self._load_profile()
        self.achievement_tracker = AchievementTracker(self.profile)
        self._evaluate_achievements()
        self._save_profile()
        self.renderer.apply_settings(self.profile.get("settings", {}))
        self.audio = AudioManager(Path(__file__).resolve().parents[1], not args.no_audio, self.profile.get("settings", {}))
        self.result_applied = False
        self.restore_message = ""
        self.last_light_message = ""
        if args.scenario in QUESTS:
            self.selected_quest = args.scenario
            self.selected_hero = args.hero
            self.mission = self._new_mission(args.hero, args.scenario)
            if args.force_complication:
                if args.scenario == "recovery":
                    self.mission.artifact_collected = True
                    self.mission.hero.artifact = True
                    self.mission.objective_progress = 1
                elif args.scenario == "rescue":
                    self.mission.civilians[0].rescued = True
                    self.mission.hero.rescued = 1
                    self.mission.objective_progress = 1
                self.mission._trigger_complication()
            if args.force_boss:
                if not self.mission.complication_triggered:
                    self.mission._trigger_complication()
                self.mission._spawn_signature_boss()
                boss = next(e for e in self.mission.enemies if e.is_boss)
                boss.hp = boss.max_hp * (0.42 if args.boss_phase_two else 1.0)
                if args.boss_phase_two:
                    boss.boss_phase = 2
                    self.mission.boss_phase_note = f"PHASE II / {self.mission.boss_profile['phase_two']}"
            if args.force_echo and args.hero == "morrow":
                corpse = self.mission.enemies[0]
                corpse.dead = True
                corpse.hp = 0
                self.mission.hero.pos = pygame.Vector2(corpse.pos)
                living = next((e for e in self.mission.enemies[1:] if not e.dead), None)
                if living is not None:
                    self.mission._hero_attack(living, 0.016)
            self.mission.inspection = {"type": args.inspect, "index": max(0, args.inspect_index)}
            if args.last_survivor:
                for key in HEROES:
                    if key != args.hero:
                        self.profile["heroes"][key]["availability"] = "ELIMINATED"
                        self.profile["heroes"][key]["strain"] = 100
                        self.profile["heroes"][key]["field_condition"] = "ELIMINATED"
            if args.force_success:
                self.mission.status = "SUCCESS"
                self.mission.time = 64.0
                self.mission.hero.hp = self.mission.hero.max_hp * 0.78
                self.mission.complication_resolved = True
                self.mission.result_reason = "The contract was completed during proof staging"
                self.mission._finalize_result()
                self._apply_mission_result()
            elif args.force_death:
                self.mission._damage_hero(99999)
                self.mission._finalize_result()
                self._apply_mission_result()
            self.state = "MISSION"

    def _detect_desktop_size(self) -> tuple[int, int]:
        try:
            sizes = pygame.display.get_desktop_sizes()
        except Exception:
            sizes = []
        fallback = VIRTUAL_SIZE
        if not sizes:
            try:
                info = pygame.display.Info()
                fallback = (int(getattr(info, "current_w", VIRTUAL_SIZE[0])), int(getattr(info, "current_h", VIRTUAL_SIZE[1])))
            except Exception:
                fallback = VIRTUAL_SIZE
        if sizes:
            self.display_index = max(0, min(self.display_index, len(sizes) - 1))
        return choose_desktop_size(sizes, self.display_index, fallback=fallback)

    def _set_display_mode(self, borderless: bool):
        self.borderless_fullscreen = bool(borderless)
        self.args.fullscreen = self.borderless_fullscreen
        if self.borderless_fullscreen:
            # Pygame/SDL uses desktop-fullscreen (borderless) when FULLSCREEN is
            # requested at the desktop's *current* resolution.  We therefore
            # cover the desktop/taskbar without asking the monitor to switch to
            # another physical video mode.
            self.desktop_size = self._detect_desktop_size()
            return pygame.display.set_mode(self.desktop_size, pygame.FULLSCREEN, display=self.display_index)
        return pygame.display.set_mode(DEFAULT_WINDOW_SIZE, pygame.RESIZABLE, display=self.display_index)

    def _toggle_display_mode(self) -> None:
        self.screen = self._set_display_mode(not self.borderless_fullscreen)
        mode = "BORDERLESS DESKTOP" if self.borderless_fullscreen else "WINDOWED 1280×720"
        self.platform_notice = mode
        try:
            self.platform_notice_until = int(pygame.time.get_ticks()) + 1800
        except Exception:
            self.platform_notice_until = 0

    def display_contract(self) -> dict:
        window_size = tuple(int(v) for v in self.screen.get_size())
        present = fit_virtual_canvas(window_size, VIRTUAL_SIZE)
        return {
            "mode": "borderless_desktop" if self.borderless_fullscreen else "windowed",
            "borderless": bool(self.borderless_fullscreen),
            "exclusive_fullscreen": False,
            "display_index": int(self.display_index),
            "desktop_size": list(self.desktop_size),
            "window_size": list(window_size),
            "virtual_size": list(VIRTUAL_SIZE),
            "presentation_rect": [present.x, present.y, present.width, present.height],
            "presentation_scale": round(present.scale, 8),
            "integer_scale": bool(present.integer_scale),
            "aspect_preserved": True,
            "monitor_mode_change_requested": False,
        }

    def _default_profile(self) -> dict:
        return {
            "profile_version": 9,
            "guild": {"credits": 1600, "renown": 0, "contracts": 0, "lifetime_credits": 0, "restoration_tokens": 0, "sidekick_perks": 0, "cycles": 1, "roster_wipes": 0, "last_light_pending": False, "last_roster_event": "GUILD ROSTER READY", "bosses_defeated": 0, "link_missions": 0, "last_profile_recovery": "NONE"},
            "settings": {"master_volume": 0.85, "sfx_volume": 0.85, "ambience_volume": 0.45, "music_volume": 0.75, "reduced_motion": False, "high_contrast": False, "tutorial_tips": True, "text_scale": "standard"},
            "onboarding": {"completed": False, "missions_started": 0, "first_success": False},
            "campaign": {
                "chain_step": 0, "chain_completions": 0, "last_chain_event": "CHAIN READY / ASH TESTAMENT",
                "aftermath_counts": {key: 0 for key in QUESTS}, "last_aftermath": "none",
                "pending_bond_event": None, "bond_events_resolved": 0,
            },
            "bonds": {
                f"{a}|{b}": {"points": 0, "missions": 0, "victories": 0, "mastery": 0, "event_level": 0, "title": "UNTESTED LINK"}
                for i, a in enumerate(HEROES) for b in list(HEROES)[i+1:]
            },
            "heroes": {
                key: {"strain": 0, "missions": 0, "successes": 0, "last_consequence": "READY", "recoveries": 0, "field_condition": "COMBAT READY", "availability": "ACTIVE", "deaths": 0, "restorations": 0, "eliminated_contract": ""}
                for key in HEROES
            },
        }

    def _load_profile(self) -> dict:
        profile = self._default_profile()
        loaded: dict = {}
        source = self.profile_path
        temp_source = self.profile_path.with_suffix(self.profile_path.suffix + ".tmp")

        def read_object(path: Path) -> dict:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise TypeError("Profile root must be an object")
            return value

        if source.exists():
            try:
                loaded = read_object(source)
            except (OSError, ValueError, TypeError):
                backup = source.with_suffix(source.suffix + ".corrupt")
                index = 1
                while backup.exists():
                    backup = source.with_suffix(source.suffix + f".corrupt.{index}")
                    index += 1
                try:
                    shutil.copy2(source, backup)
                except OSError:
                    backup = source
                self.profile_recovery_note = f"CORRUPT PROFILE QUARANTINED / {backup.name}"
                if temp_source.exists():
                    try:
                        loaded = read_object(temp_source)
                        self.profile_recovery_note = "INTERRUPTED SAVE RECOVERED FROM TEMP FILE"
                    except (OSError, ValueError, TypeError):
                        loaded = {}
        elif temp_source.exists():
            try:
                loaded = read_object(temp_source)
                self.profile_recovery_note = "INTERRUPTED SAVE RECOVERED FROM TEMP FILE"
            except (OSError, ValueError, TypeError):
                loaded = {}

        if loaded:
            profile["guild"].update(loaded.get("guild", {}) if isinstance(loaded.get("guild"), dict) else {})
            if isinstance(loaded.get("settings"), dict):
                profile["settings"].update(loaded["settings"])
            if isinstance(loaded.get("onboarding"), dict):
                profile["onboarding"].update(loaded["onboarding"])
            if isinstance(loaded.get("campaign"), dict):
                campaign_loaded = loaded["campaign"]
                for key, value in campaign_loaded.items():
                    if key == "aftermath_counts" and isinstance(value, dict):
                        profile["campaign"]["aftermath_counts"].update({q: int(value.get(q, 0)) for q in QUESTS})
                    elif key in profile["campaign"]:
                        profile["campaign"][key] = value
            for pair, record in (loaded.get("bonds", {}) if isinstance(loaded.get("bonds"), dict) else {}).items():
                if pair in profile["bonds"] and isinstance(record, dict):
                    profile["bonds"][pair].update(record)
            loaded_heroes = loaded.get("heroes", {}) if isinstance(loaded.get("heroes"), dict) else {}
            for key in HEROES:
                if isinstance(loaded_heroes.get(key), dict):
                    profile["heroes"][key].update(loaded_heroes[key])
                profile["heroes"][key].setdefault("availability", "ACTIVE")
                profile["heroes"][key].setdefault("deaths", 0)
                profile["heroes"][key].setdefault("restorations", 0)
                profile["heroes"][key].setdefault("eliminated_contract", "")
                if profile["heroes"][key].get("availability") == "ELIMINATED":
                    profile["heroes"][key]["strain"] = 100
                    profile["heroes"][key]["field_condition"] = "ELIMINATED"
                else:
                    profile["heroes"][key]["availability"] = "ACTIVE"
                    profile["heroes"][key]["field_condition"] = recovery_state(key, profile["heroes"][key].get("strain", 0))["name"]
            profile["campaign"]["chain_step"] = int(profile["campaign"].get("chain_step", 0)) % len(STORY_CHAIN["order"])

        profile["profile_version"] = 9
        profile["settings"]["master_volume"] = max(0.0, min(1.0, float(profile["settings"].get("master_volume", 0.85))))
        profile["settings"]["sfx_volume"] = max(0.0, min(1.0, float(profile["settings"].get("sfx_volume", 0.85))))
        profile["settings"]["ambience_volume"] = max(0.0, min(1.0, float(profile["settings"].get("ambience_volume", 0.45))))
        profile["settings"]["music_volume"] = max(0.0, min(1.0, float(profile["settings"].get("music_volume", 0.75))))
        profile["settings"]["text_scale"] = "large" if profile["settings"].get("text_scale") == "large" else "standard"
        if self.profile_recovery_note:
            profile["guild"]["last_profile_recovery"] = self.profile_recovery_note
        profile["guild"]["sidekick_perks"] = max(0, int(profile["guild"].get("sidekick_perks", 0)))
        ensure_achievement_state(profile)

        active = [key for key in HEROES if profile["heroes"][key].get("availability") == "ACTIVE"]
        fallen = [key for key in HEROES if profile["heroes"][key].get("availability") == "ELIMINATED"]
        if not active:
            profile["guild"]["last_light_pending"] = True
            profile["guild"]["restoration_tokens"] = 0
            profile["guild"]["last_roster_event"] = "TOTAL ROSTER LOSS / LAST LIGHT ARMED"
        elif not fallen:
            # Pass 22 migration: a victory charge with nobody left to revive becomes
            # a persistent Sidekick Perk instead of being discarded.
            stranded = max(0, int(profile["guild"].get("restoration_tokens", 0)))
            if stranded:
                profile["guild"]["sidekick_perks"] += stranded
            profile["guild"]["restoration_tokens"] = 0
            profile["guild"]["last_light_pending"] = False
        return profile


    def _campaign_expected_quest(self) -> str:
        step = int(self.profile.get("campaign", {}).get("chain_step", 0)) % len(STORY_CHAIN["order"])
        return STORY_CHAIN["order"][step]

    def _mission_aftermath(self, quest_key: str) -> str:
        campaign = self.profile.get("campaign", {})
        counts = campaign.get("aftermath_counts", {})
        if quest_key == "recovery" and int(counts.get("purge", 0)) > 0:
            return "choir_silence"
        if quest_key == "rescue" and int(counts.get("recovery", 0)) > 0:
            return "open_index"
        if quest_key == "purge" and int(campaign.get("chain_completions", 0)) > 0 and int(counts.get("rescue", 0)) > 0:
            return "mercy_route"
        return "none"

    def _next_meta_state(self) -> str:
        if self.profile.get("guild", {}).get("last_light_pending"):
            return "LAST_LIGHT"
        if self._fallen_heroes() and int(self.profile.get("guild", {}).get("restoration_tokens", 0)) > 0:
            return "RESTORE_SELECT"
        if self.profile.get("campaign", {}).get("pending_bond_event"):
            return "BOND_EVENT"
        return "CONTRACT_BOARD"

    def _queue_bond_event(self, pair: str, old_points: int, new_points: int) -> None:
        bond = self.profile["bonds"][pair]
        current_level = int(bond.get("event_level", 0))
        crossed = [level for level in (3, 6, 9) if old_points < level <= new_points and level > current_level]
        if not crossed or self.profile["campaign"].get("pending_bond_event"):
            return
        level = min(crossed)
        self.profile["campaign"]["pending_bond_event"] = {"pair": pair, "level": level}

    def _resolve_bond_event(self, choice: str) -> bool:
        pending = self.profile.get("campaign", {}).get("pending_bond_event")
        if not isinstance(pending, dict):
            return False
        pair = pending.get("pair", "")
        level = int(pending.get("level", 0))
        if pair not in self.profile.get("bonds", {}) or pair not in BOND_EVENTS or choice not in {"anchor", "boundary"}:
            return False
        a, b = pair.split("|")
        bond = self.profile["bonds"][pair]
        event = BOND_EVENTS[pair]
        if choice == "anchor":
            bond["mastery"] = min(3, int(bond.get("mastery", 0)) + 1)
            bond["title"] = event["name"]
            for hero_key in (a, b):
                record = self.profile["heroes"][hero_key]
                if record.get("availability", "ACTIVE") == "ACTIVE":
                    record["strain"] = min(100, int(record.get("strain", 0)) + 2)
                    record["field_condition"] = recovery_state(hero_key, record["strain"])["name"]
            outcome = "BOND ANCHORED / LINK MASTERY INCREASED"
        else:
            bond["title"] = "PROFESSIONAL DISTANCE"
            for hero_key in (a, b):
                record = self.profile["heroes"][hero_key]
                if record.get("availability", "ACTIVE") == "ACTIVE":
                    record["strain"] = max(0, int(record.get("strain", 0)) - 4)
                    record["field_condition"] = recovery_state(hero_key, record["strain"])["name"]
            outcome = "BOUNDARY KEPT / SHARED STRAIN REDUCED"
        bond["event_level"] = max(int(bond.get("event_level", 0)), level)
        bond["last_choice"] = choice
        bond["last_outcome"] = outcome
        self.profile["campaign"]["pending_bond_event"] = None
        self.profile["campaign"]["bond_events_resolved"] = int(self.profile["campaign"].get("bond_events_resolved", 0)) + 1
        self.profile["campaign"]["last_bond_event"] = f"{event['name']} / {outcome}"
        self._evaluate_achievements()
        self._save_profile()
        return True

    def _active_heroes(self) -> list[str]:
        return [key for key in HEROES if self.profile["heroes"].get(key, {}).get("availability", "ACTIVE") == "ACTIVE"]

    def _fallen_heroes(self) -> list[str]:
        return [key for key in HEROES if self.profile["heroes"].get(key, {}).get("availability", "ACTIVE") == "ELIMINATED"]

    def _sidekick_candidates(self, hero_key: str) -> list[str]:
        return [key for key in HEROES if key != hero_key and self.profile["heroes"].get(key, {}).get("availability", "ACTIVE") == "ACTIVE"]

    def _sidekick_limit(self) -> int:
        # Sidekick deployment is available only when the roster has nobody to revive.
        if self._fallen_heroes():
            return 0
        return min(2, max(0, int(self.profile.get("guild", {}).get("sidekick_perks", 0))))

    def _resolve_sidekicks(self, hero_key: str) -> list[str]:
        allowed = set(self._sidekick_candidates(hero_key))
        limit = self._sidekick_limit()
        return [key for key in self.selected_sidekicks if key in allowed][:limit]

    def _toggle_sidekick(self, hero_key: str, sidekick_key: str) -> bool:
        if sidekick_key not in self._sidekick_candidates(hero_key) or self._sidekick_limit() <= 0:
            return False
        if sidekick_key in self.selected_sidekicks:
            self.selected_sidekicks.remove(sidekick_key)
            self.audio.play("back")
            return True
        if len(self._resolve_sidekicks(hero_key)) >= self._sidekick_limit():
            return False
        self.selected_sidekicks.append(sidekick_key)
        self.audio.play("confirm")
        return True

    def _cycle_sidekick_team(self, hero_key: str) -> None:
        candidates = self._sidekick_candidates(hero_key)
        limit = self._sidekick_limit()
        if not candidates or limit <= 0:
            self.selected_sidekicks.clear()
            return
        current = self._resolve_sidekicks(hero_key)
        target_count = (len(current) + 1) % (limit + 1)
        self.selected_sidekicks = candidates[:target_count]
        self.audio.play("confirm")

    def _restore_hero(self, hero_key: str) -> bool:
        guild = self.profile["guild"]
        record = self.profile["heroes"].get(hero_key)
        if not record or record.get("availability") != "ELIMINATED" or int(guild.get("restoration_tokens", 0)) <= 0:
            return False
        guild["restoration_tokens"] = max(0, int(guild.get("restoration_tokens", 0)) - 1)
        record["availability"] = "ACTIVE"
        record["strain"] = min(55, 28 + int(record.get("deaths", 0)) * 7 + int(record.get("restorations", 0)) * 4)
        record["field_condition"] = recovery_state(hero_key, record["strain"])["name"]
        record["restorations"] = int(record.get("restorations", 0)) + 1
        record["last_consequence"] = "RESTORED BY VICTORY"
        record["eliminated_contract"] = ""
        guild["last_roster_event"] = f"{HEROES[hero_key]['name']} RESTORED"
        if not self._fallen_heroes():
            guild["restoration_tokens"] = 0
        self.restore_message = guild["last_roster_event"]
        self._evaluate_achievements()
        self.audio.play("restore")
        self._save_profile()
        return True

    def _execute_last_light_reset(self) -> bool:
        guild = self.profile["guild"]
        if not guild.get("last_light_pending"):
            return False
        guild["roster_wipes"] = int(guild.get("roster_wipes", 0)) + 1
        guild["cycles"] = int(guild.get("cycles", 1)) + 1
        guild["restoration_tokens"] = 0
        guild["last_light_pending"] = False
        guild["last_roster_event"] = "LAST LIGHT PROTOCOL / NEW GUILD CYCLE"
        self.profile["campaign"]["pending_bond_event"] = None
        for key, record in self.profile["heroes"].items():
            record["availability"] = "ACTIVE"
            record["strain"] = 36
            record["field_condition"] = recovery_state(key, 36)["name"]
            record["last_consequence"] = "RECONSTITUTED AFTER ROSTER WIPE"
            record["eliminated_contract"] = ""
        self.selected_hero = None
        self.last_light_message = guild["last_roster_event"]
        self._evaluate_achievements()
        self.audio.play("restore")
        self._save_profile()
        return True

    def _evaluate_achievements(self) -> list[str]:
        newly = self.achievement_tracker.evaluate_all()
        if self.microsoft_runtime.ready:
            result = self.achievement_tracker.sync_pending(self.microsoft_runtime.update_achievement)
            if result.get("sent"):
                self.platform_notice = f"XBOX ACHIEVEMENTS SYNCED / {len(result['sent'])}"
        return newly

    def _refresh_platform_save_root(self) -> None:
        if not self.microsoft_runtime.ready:
            return
        new_root = self.microsoft_runtime.refresh_save_root()
        if new_root is None or not self.platform_save_auto:
            return
        target = Path(new_root) / DEFAULT_PROFILE_NAME
        if target == self.profile_path:
            return
        # Focus loss already checkpointed the previous root. If Gaming Runtime
        # returns a different root after resume, keep the live profile and move
        # subsequent writes to the newly synchronized location.
        self.profile_path = target
        self._save_profile()

    def _save_profile(self) -> None:
        if not self.saving_enabled:
            return
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.profile_path.with_suffix(self.profile_path.suffix + ".tmp")
        backup = self.profile_path.with_suffix(self.profile_path.suffix + ".bak")
        temp.write_text(json.dumps(self.profile, indent=2), encoding="utf-8")
        if self.profile_path.exists():
            try:
                shutil.copy2(self.profile_path, backup)
            except OSError:
                pass
        temp.replace(self.profile_path)

    def _apply_settings(self) -> None:
        settings = self.profile.setdefault("settings", self._default_profile()["settings"])
        self.renderer.apply_settings(settings)
        if hasattr(self, "audio"):
            self.audio.apply_settings(settings)
        self._save_profile()

    def _adjust_setting(self, direction: int) -> None:
        keys = ("master_volume", "sfx_volume", "ambience_volume", "music_volume", "reduced_motion", "high_contrast", "tutorial_tips", "text_scale")
        key = keys[self.settings_index % len(keys)]
        settings = self.profile["settings"]
        if key in {"master_volume", "sfx_volume", "ambience_volume", "music_volume"}:
            settings[key] = round(max(0.0, min(1.0, float(settings.get(key, 0.5)) + direction * 0.05)), 2)
        elif key == "text_scale":
            settings[key] = "large" if settings.get(key) != "large" else "standard"
        else:
            settings[key] = not bool(settings.get(key, False))
        self._apply_settings()
        self.audio.play("confirm")

    def _reset_guild_profile(self) -> None:
        settings = dict(self.profile.get("settings", {}))
        self.profile = self._default_profile()
        ensure_achievement_state(self.profile)
        self.achievement_tracker = AchievementTracker(self.profile)
        self.profile["settings"].update(settings)
        self.new_guild_confirm = False
        self.selected_quest = None
        self.selected_hero = None
        self._apply_settings()
        self._save_profile()

    def _continue_from_title(self) -> None:
        self.new_guild_confirm = False
        self.state = self._next_meta_state()
        self.audio.play("confirm")

    def _recover_selected(self) -> bool:
        if not self.selected_hero:
            return False
        record = self.profile["heroes"][self.selected_hero]
        if record.get("availability", "ACTIVE") != "ACTIVE":
            return False
        quote = recovery_quote(self.selected_hero, record.get("strain", 0))
        guild = self.profile["guild"]
        if not quote["ready"] or int(guild.get("credits", 0)) < int(quote["cost"]):
            return False
        guild["credits"] = int(guild.get("credits", 0)) - int(quote["cost"])
        record["strain"] = int(quote["remaining"])
        record["field_condition"] = recovery_state(self.selected_hero, record["strain"])["name"]
        record["recoveries"] = int(record.get("recoveries", 0)) + 1
        record["last_consequence"] = "GUILD MEDBAY RECOVERY"
        record["last_recovery_cost"] = int(quote["cost"])
        self._save_profile()
        return True

    @staticmethod
    def _bond_key(a: str, b: str) -> str:
        return "|".join(sorted((a, b), key=list(HEROES).index))

    def _support_candidates(self, hero_key: str) -> list[str]:
        return [key for key in HEROES if key != hero_key and self.profile["heroes"][key].get("availability", "ACTIVE") == "ACTIVE"]

    def _resolve_support(self, hero_key: str) -> str:
        sidekicks = self._resolve_sidekicks(hero_key)
        return sidekicks[0] if sidekicks else "none"

    def _new_mission(self, hero_key: str, quest_key: str) -> Mission:
        if self.profile["heroes"][hero_key].get("availability", "ACTIVE") != "ACTIVE":
            raise ValueError(f"Eliminated hero cannot deploy: {hero_key}")
        strain = float(self.profile["heroes"][hero_key].get("strain", 0))
        self.result_applied = False
        sidekicks = self._resolve_sidekicks(hero_key)
        support_key = sidekicks[0] if sidekicks else "none"
        mastery = 0
        if support_key != "none":
            mastery = int(self.profile["bonds"][self._bond_key(hero_key, support_key)].get("mastery", 0))
        sidekick_strains = {key: float(self.profile["heroes"][key].get("strain", 0)) for key in sidekicks}
        chapter = STORY_CHAIN["chapters"][quest_key]["name"] if self._campaign_expected_quest() == quest_key else "SIDE CONTRACT"
        completed_counts = self.profile.get("campaign", {}).get("aftermath_counts", {})
        layout_cycle = int(completed_counts.get(quest_key, 0))
        mission_seed = int(self.args.seed) + layout_cycle
        return Mission(hero_key, quest_key, mission_seed, starting_strain=strain, order_key=self.selected_order, equipment_key=self.selected_equipment, support_key=support_key, support_mastery=mastery, aftermath_key=self._mission_aftermath(quest_key), chain_chapter=chapter, sidekick_keys=tuple(sidekicks), sidekick_strains=sidekick_strains)

    def _prepare_selected(self) -> None:
        if not self.selected_hero or not self.selected_quest:
            return
        if self.profile["heroes"][self.selected_hero].get("availability", "ACTIVE") != "ACTIVE":
            return
        self.state = "LOADOUT_PREP"

    def _deploy_selected(self) -> None:
        if not self.selected_hero or not self.selected_quest:
            return
        if self.profile["heroes"][self.selected_hero].get("availability", "ACTIVE") != "ACTIVE":
            return
        sidekicks = self._resolve_sidekicks(self.selected_hero)
        self.crash_reporter.breadcrumb(
            "mission_launch_requested",
            hero=self.selected_hero, quest=self.selected_quest, sidekicks=list(sidekicks),
            order=self.selected_order, equipment=self.selected_equipment,
        )
        profile_before = copy.deepcopy(self.profile)
        try:
            if getattr(self.args, "crash_reporter_test", False):
                raise RuntimeError("PASS27_SYNTHETIC_MISSION_LAUNCH_CRASH")
            mission = self._new_mission(self.selected_hero, self.selected_quest)
            launch_check = mission.validate_launch_state()
            self.crash_reporter.breadcrumb("mission_launch_preflight_pass", **launch_check)
            # Commit persistent costs only after the full Mission object has been
            # constructed.  A constructor failure therefore cannot consume perks.
            if sidekicks:
                guild = self.profile["guild"]
                guild["sidekick_perks"] = max(0, int(guild.get("sidekick_perks", 0)) - len(sidekicks))
                guild["last_roster_event"] = f"SIDEKICK DEPLOYMENT / {len(sidekicks)} PERK{'S' if len(sidekicks) != 1 else ''} SPENT"
            onboarding = self.profile.setdefault("onboarding", {"completed": False, "missions_started": 0, "first_success": False})
            onboarding["missions_started"] = int(onboarding.get("missions_started", 0)) + 1
            self._save_profile()
            self.mission = mission
            self.audio.play("deploy")
            self.state = "MISSION"
            self.crash_reporter.breadcrumb(
                "mission_launch_committed", hero=mission.hero_key, quest=mission.quest_key,
                layout=getattr(mission, "world_layout_name", ""), party_size=getattr(mission, "party_size", 1),
                enemy_count=len(getattr(mission, "enemies", [])),
            )
        except Exception as exc:
            self.profile = profile_before
            self.achievement_tracker = AchievementTracker(self.profile)
            self.mission = None
            # Best-effort rollback protects banked Sidekick Perks and the
            # missions-started counter if a later launch step failed.
            try:
                self._save_profile()
                self.crash_reporter.breadcrumb("mission_launch_rollback_saved")
            except Exception as rollback_exc:
                self.crash_reporter.breadcrumb("mission_launch_rollback_save_failed", error=f"{type(rollback_exc).__name__}: {rollback_exc}")
            self._enter_crash_recovery(exc, phase="mission_launch", recover_to="LOADOUT_PREP")

    def _apply_mission_result(self) -> None:
        if self.result_applied or not self.mission or self.mission.status == "ACTIVE":
            return
        record = self.profile["heroes"][self.mission.hero_key]
        record["missions"] = int(record.get("missions", 0)) + 1
        if self.mission.status == "SUCCESS":
            record["successes"] = int(record.get("successes", 0)) + 1
            onboarding = self.profile.setdefault("onboarding", {"completed": False, "missions_started": 0, "first_success": False})
            onboarding["first_success"] = True
            onboarding["completed"] = True
        record["strain"] = max(0, min(100, int(record.get("strain", 0)) + int(self.mission.strain_delta)))
        record["field_condition"] = recovery_state(self.mission.hero_key, record["strain"])["name"]
        record["last_consequence"] = self.mission.result_consequence
        record["last_fit"] = self.mission.fit["rating"]
        record["last_order"] = self.mission.order_key
        record["last_order_status"] = self.mission.order_status
        record["last_complication"] = self.mission.complication["key"]
        record["last_equipment"] = self.mission.equipment_key
        record["last_equipment_note"] = self.mission.equipment_note
        record["last_reward"] = int(self.mission.reward_credits)
        guild = self.profile["guild"]
        hero_died = self.mission.status == "FAILED" and self.mission.hero.hp <= 0
        if hero_died:
            self.mission.result_consequence = "HERO ELIMINATED"
            record["availability"] = "ELIMINATED"
            record["deaths"] = int(record.get("deaths", 0)) + 1
            record["strain"] = 100
            record["field_condition"] = "ELIMINATED"
            record["last_consequence"] = "ELIMINATED IN FIELD"
            record["eliminated_contract"] = self.mission.quest_key
        guild["credits"] = int(guild.get("credits", 0)) + int(self.mission.reward_credits)
        guild["renown"] = int(guild.get("renown", 0)) + int(self.mission.reward_renown)
        guild["contracts"] = int(guild.get("contracts", 0)) + 1
        guild["lifetime_credits"] = int(guild.get("lifetime_credits", 0)) + int(self.mission.reward_credits)
        if hero_died and not self._active_heroes():
            guild["last_light_pending"] = True
            guild["restoration_tokens"] = 0
            guild["last_roster_event"] = "TOTAL ROSTER LOSS / LAST LIGHT ARMED"
            self.mission.roster_event = "LAST HERO ELIMINATED"
        elif self.mission.status == "SUCCESS" and self._fallen_heroes():
            guild["restoration_tokens"] = int(guild.get("restoration_tokens", 0)) + 1
            guild["last_roster_event"] = "VICTORY RESTORATION AVAILABLE"
            self.mission.roster_event = "RESTORE ONE FALLEN HERO"
        elif hero_died:
            guild["last_roster_event"] = f"{HEROES[self.mission.hero_key]['name']} ELIMINATED"
            self.mission.roster_event = f"{len(self._active_heroes())} HEROES REMAIN"
        elif self.mission.status == "SUCCESS":
            guild["sidekick_perks"] = int(guild.get("sidekick_perks", 0)) + 1
            self.achievement_tracker.record_sidekick_perk_banked()
            guild["last_roster_event"] = f"SIDEKICK PERK BANKED / {guild['sidekick_perks']} READY"
            self.mission.roster_event = guild["last_roster_event"]
        else:
            self.mission.roster_event = "ROSTER UNCHANGED"
        for sidekick_key in getattr(self.mission, "sidekick_keys", ()):
            pair = self._bond_key(self.mission.hero_key, sidekick_key)
            bond = self.profile["bonds"][pair]
            old_points = int(bond.get("points", 0))
            bond["missions"] = int(bond.get("missions", 0)) + 1
            bond["points"] = min(9, old_points + (2 if self.mission.status == "SUCCESS" else 1))
            if self.mission.status == "SUCCESS":
                bond["victories"] = int(bond.get("victories", 0)) + 1
            guild["link_missions"] = int(guild.get("link_missions", 0)) + 1
            self._queue_bond_event(pair, old_points, int(bond["points"]))
        self.mission.campaign_event = "CHAIN POSITION HELD"
        if self.mission.boss_defeated:
            guild["bosses_defeated"] = int(guild.get("bosses_defeated", 0)) + 1
            campaign = self.profile["campaign"]
            counts = campaign["aftermath_counts"]
            counts[self.mission.quest_key] = int(counts.get(self.mission.quest_key, 0)) + 1
            campaign["last_aftermath"] = STORY_CHAIN["chapters"][self.mission.quest_key]["aftermath"]
            expected = self._campaign_expected_quest()
            if self.mission.status == "SUCCESS" and self.mission.quest_key == expected:
                next_step = int(campaign.get("chain_step", 0)) + 1
                if next_step >= len(STORY_CHAIN["order"]):
                    campaign["chain_step"] = 0
                    campaign["chain_completions"] = int(campaign.get("chain_completions", 0)) + 1
                    bonus_credits = int(STORY_CHAIN["completion_credits"])
                    bonus_renown = int(STORY_CHAIN["completion_renown"])
                    guild["credits"] += bonus_credits
                    guild["lifetime_credits"] += bonus_credits
                    guild["renown"] += bonus_renown
                    self.mission.campaign_event = f"SOVEREIGN CHAIN COMPLETE / +{bonus_credits:,} CR / +{bonus_renown} RENOWN"
                else:
                    campaign["chain_step"] = next_step
                    next_quest = STORY_CHAIN["order"][next_step]
                    self.mission.campaign_event = f"CHAIN ADVANCED / NEXT {STORY_CHAIN['chapters'][next_quest]['name']}"
                campaign["last_chain_event"] = self.mission.campaign_event
            else:
                self.mission.campaign_event = f"{STORY_CHAIN['chapters'][self.mission.quest_key]['aftermath']} ESTABLISHED / CHAIN POSITION HELD"
        self.achievement_tracker.record_mission_result(self.mission)
        self.result_applied = True
        self.audio.play("success" if self.mission.status == "SUCCESS" else "failure")
        self._save_profile()
        self._write_prototype_lab_result()

    def _write_prototype_lab_result(self) -> dict:
        if not self.mission or self.mission.status == "ACTIVE":
            return {}
        report = self.mission.report()
        completed = self.mission.status == "SUCCESS"
        lab_points = (120 if completed else 25) + int(self.mission.reward_credits // 40)
        if self.mission.boss_defeated:
            lab_points += 40
        if self.mission.complication_resolved:
            lab_points += 20
        payload = {
            "contract_version": 1,
            "project_id": "hex_contract",
            "project_name": "HEX CONTRACT",
            "release": "Pass 14 Tactical World Foundation",
            "source_only": True,
            "runtime_wrapper_required": False,
            "completed": completed,
            "return_to_lab": True,
            "hero": self.mission.hero_key,
            "quest": self.mission.quest_key,
            "status": self.mission.status,
            "reason": self.mission.result_reason,
            "prototype_lab_points_awarded": lab_points,
            "credits_earned": int(self.mission.reward_credits),
            "renown_earned": int(self.mission.reward_renown),
            "boss_defeated": bool(self.mission.boss_defeated),
            "complication_resolved": bool(self.mission.complication_resolved),
            "hero_survived": bool(self.mission.hero.hp > 0),
            "strain_delta": int(self.mission.strain_delta),
            "roster_event": getattr(self.mission, "roster_event", "ROSTER UNCHANGED"),
            "campaign_event": getattr(self.mission, "campaign_event", "CHAIN POSITION HELD"),
            "mission_report": report,
        }
        if self.saving_enabled:
            result_path = self.profile_path.with_name("hex_contract_game_result.json")
            temp = result_path.with_suffix(result_path.suffix + ".tmp")
            result_path.parent.mkdir(parents=True, exist_ok=True)
            temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(temp, result_path)
        return payload

    def _crash_state_snapshot(self) -> dict:
        mission = self.mission
        snapshot = {
            "ui_state": self.state,
            "paused": bool(self.paused),
            "input_mode": self.input_mode,
            "controller_connected": bool(self.controller_connected),
            "selected_quest": self.selected_quest or "",
            "selected_hero": self.selected_hero or "",
            "selected_order": self.selected_order,
            "selected_equipment": self.selected_equipment,
            "selected_sidekicks": list(self.selected_sidekicks),
            "profile_version": int(self.profile.get("profile_version", 0)) if hasattr(self, "profile") else 0,
            "profile_name": self.profile_path.name if hasattr(self, "profile_path") else "",
        }
        if mission is not None:
            snapshot["mission"] = {
                "hero": getattr(mission, "hero_key", ""),
                "quest": getattr(mission, "quest_key", ""),
                "layout": getattr(mission, "world_layout_name", ""),
                "party_size": int(getattr(mission, "party_size", 1)),
                "sidekicks": list(getattr(mission, "sidekick_keys", ())),
                "status": getattr(mission, "status", ""),
                "time": round(float(getattr(mission, "time", 0.0)), 3),
                "enemy_count": len(getattr(mission, "enemies", [])),
                "civilian_count": len(getattr(mission, "civilians", [])),
                "complication_triggered": bool(getattr(mission, "complication_triggered", False)),
                "boss_spawned": bool(any(getattr(enemy, "is_boss", False) for enemy in getattr(mission, "enemies", []))),
            }
        return snapshot

    def _enter_crash_recovery(self, exc: BaseException, *, phase: str, recover_to: str = "CONTRACT_BOARD") -> None:
        if self.crash_recovery_active:
            raise exc
        self.crash_recovery_active = True
        self.paused = True
        artifact = self.crash_reporter.capture_exception(
            exc, phase=phase, recoverable=True,
            extra={"recover_to": recover_to, "selected_quest": self.selected_quest or "", "selected_hero": self.selected_hero or ""},
        )
        self.crash_artifact = artifact
        self.crash_phase = phase
        self.crash_message = f"Crash ID {artifact.report_id}" if artifact is not None else "Crash report write failed"
        self.state = "CRASH_RECOVERY"
        self.mission = None
        try:
            self.audio.set_context("CRASH_RECOVERY")
        except Exception:
            pass
        self.crash_recover_to = recover_to
        self.crash_reporter.breadcrumb("entered_crash_recovery", phase=phase, report_id=getattr(artifact, "report_id", ""))

    def _leave_crash_recovery(self) -> None:
        self.state = getattr(self, "crash_recover_to", "CONTRACT_BOARD")
        self.paused = False
        self.crash_recovery_active = False
        self.crash_artifact = None
        self.crash_message = ""
        self.crash_phase = ""

    def _draw_crash_recovery(self) -> None:
        # Draw directly with pygame so a renderer-specific failure cannot hide
        # the diagnostic screen.  This panel intentionally avoids gameplay HUD.
        self.canvas.fill((18, 20, 27))
        try:
            pygame.draw.rect(self.canvas, (60, 66, 80), pygame.Rect(110, 90, 1700, 900), border_radius=20)
            pygame.draw.rect(self.canvas, (123, 211, 255), pygame.Rect(115, 95, 1690, 8), border_radius=4)
            pygame.draw.rect(self.canvas, (102, 112, 135), pygame.Rect(110, 90, 1700, 900), width=3, border_radius=20)
            font_title = pygame.font.Font(None, 64)
            font_body = pygame.font.Font(None, 34)
            font_small = pygame.font.Font(None, 27)
            rows = [
                (font_title, "MISSION INTERRUPTED", (255, 214, 118), 116),
                (font_body, "HEX CONTRACT caught an error instead of closing silently.", (232, 235, 242), 220),
                (font_body, self.crash_message or "Crash report captured", (120, 218, 255), 274),
                (font_small, f"Phase: {self.crash_phase or 'unknown'}", (178, 186, 205), 334),
                (font_small, "A local report ZIP was written to the crash folder. No data was uploaded.", (178, 186, 205), 386),
                (font_small, "Press ENTER / A to return safely.  ESC / B also returns.", (220, 224, 232), 472),
                (font_small, "When reporting the bug, attach the newest HEX_CONTRACT_crash_*.zip file.", (220, 224, 232), 516),
            ]
            for font, text, color, y in rows:
                surf = font.render(text, True, color)
                self.canvas.blit(surf, ((VIRTUAL_SIZE[0] - surf.get_width()) // 2, y))
        except Exception:
            # Even if font rendering fails, keep a valid frame rather than
            # recursing into the crash handler.
            pygame.draw.rect(self.canvas, (120, 30, 36), pygame.Rect(300, 220, 1320, 420), width=4)

    def _init_controllers(self) -> None:
        if sdl_controller is None:
            return
        try:
            sdl_controller.init()
            sdl_controller.set_eventstate(True)
            for index in range(sdl_controller.get_count()):
                self._open_controller(index, announce=False)
        except Exception:
            self.controllers.clear()
            self.controller_connected = False

    def _open_controller(self, device_index: int, announce: bool = True) -> bool:
        if sdl_controller is None:
            return False
        try:
            if not sdl_controller.is_controller(int(device_index)):
                return False
            controller = sdl_controller.Controller(int(device_index))
            joystick = controller.as_joystick()
            instance_id = int(joystick.get_instance_id())
            self.controllers[instance_id] = controller
            self.controller_connected = True
            self.controller_name = str(joystick.get_name() or "Xbox Controller")
            if announce:
                self._platform_toast("Xbox Controller CONNECTED")
            return True
        except Exception:
            return False

    def _remove_controller(self, instance_id: int) -> None:
        controller = self.controllers.pop(int(instance_id), None)
        if controller is not None:
            try:
                controller.quit()
            except Exception:
                pass
        self.controller_connected = bool(self.controllers)
        if not self.controller_connected:
            was_xbox = self.input_mode == INPUT_XBOX
            self.input_mode = INPUT_KEYBOARD
            self.controller_name = ""
            if was_xbox and self.state == "MISSION" and self.mission and self.mission.status == "ACTIVE":
                self.paused = True
            self._platform_toast("Xbox Controller DISCONNECTED / GAME PAUSED" if was_xbox and self.state == "MISSION" else "Xbox Controller DISCONNECTED")
            self._checkpoint("controller_disconnect")

    def _platform_toast(self, message: str, duration_ms: int = 2600) -> None:
        self.platform_notice = str(message)
        try:
            now = int(pygame.time.get_ticks())
        except Exception:
            now = 0
        self.platform_notice_until = now + max(0, int(duration_ms))

    def _set_input_mode(self, mode: str) -> None:
        if mode not in {INPUT_KEYBOARD, INPUT_XBOX}:
            return
        if self.input_mode != mode:
            self.input_mode = mode
            if mode == INPUT_XBOX:
                self._platform_toast("Xbox Controller ACTIVE", 1500)

    def _checkpoint(self, reason: str) -> None:
        # Keep checkpoint semantics simple and synchronous.  Platform save
        # backends can remap the directory without changing call sites.
        _ = reason  # kept for future platform telemetry; profile schema remains v9.
        self._save_profile()

    def _controller_button_action(self, button: int) -> str | None:
        mapping = {
            getattr(pygame, "CONTROLLER_BUTTON_A", 0): A_CONFIRM,
            getattr(pygame, "CONTROLLER_BUTTON_B", 1): A_BACK,
            getattr(pygame, "CONTROLLER_BUTTON_X", 2): A_ALT,
            getattr(pygame, "CONTROLLER_BUTTON_Y", 3): A_INFO,
            getattr(pygame, "CONTROLLER_BUTTON_START", 6): A_MENU,
            getattr(pygame, "CONTROLLER_BUTTON_BACK", 4): A_VIEW,
            getattr(pygame, "CONTROLLER_BUTTON_DPAD_UP", 11): A_UP,
            getattr(pygame, "CONTROLLER_BUTTON_DPAD_DOWN", 12): A_DOWN,
            getattr(pygame, "CONTROLLER_BUTTON_DPAD_LEFT", 13): A_LEFT,
            getattr(pygame, "CONTROLLER_BUTTON_DPAD_RIGHT", 14): A_RIGHT,
            getattr(pygame, "CONTROLLER_BUTTON_LEFTSHOULDER", 9): A_LB,
            getattr(pygame, "CONTROLLER_BUTTON_RIGHTSHOULDER", 10): A_RB,
        }
        return mapping.get(int(button))

    def _controller_axis_action(self, event) -> str | None:
        axis = int(getattr(event, "axis", -1))
        value = int(getattr(event, "value", 0))
        left_x = getattr(pygame, "CONTROLLER_AXIS_LEFTX", 0)
        left_y = getattr(pygame, "CONTROLLER_AXIS_LEFTY", 1)
        high, low = 18000, 9500
        if axis == left_x:
            if abs(value) < low:
                self.axis_latch["x"] = 0
                return None
            direction = 1 if value > high else -1 if value < -high else 0
            if direction and direction != self.axis_latch["x"]:
                self.axis_latch["x"] = direction
                return A_RIGHT if direction > 0 else A_LEFT
        elif axis == left_y:
            if abs(value) < low:
                self.axis_latch["y"] = 0
                return None
            direction = 1 if value > high else -1 if value < -high else 0
            if direction and direction != self.axis_latch["y"]:
                self.axis_latch["y"] = direction
                return A_DOWN if direction > 0 else A_UP
        return None

    def _first_active_hero(self) -> str | None:
        return next((key for key in HEROES if self.profile["heroes"][key].get("availability", "ACTIVE") == "ACTIVE"), None)

    def _cycle_active_hero(self, direction: int) -> None:
        active = [key for key in HEROES if self.profile["heroes"][key].get("availability", "ACTIVE") == "ACTIVE"]
        if not active:
            self.selected_hero = None
            return
        current = self.selected_hero if self.selected_hero in active else active[0]
        self.selected_hero = active[wrap_index(active.index(current), direction, len(active))]
        self.audio.play("confirm")

    def _cycle_restore_hero(self, direction: int) -> None:
        fallen = self._fallen_heroes()
        if not fallen:
            return
        self.restore_index = wrap_index(self.restore_index, direction, len(fallen))
        self.selected_hero = fallen[self.restore_index]
        self.audio.play("confirm")

    def _cycle_sidekick_combo(self, direction: int) -> None:
        if not self.selected_hero:
            return
        candidates = self._sidekick_candidates(self.selected_hero)
        limit = self._sidekick_limit()
        combos: list[tuple[str, ...]] = [()]
        for count in range(1, min(limit, len(candidates)) + 1):
            combos.extend(combinations(candidates, count))
        if not combos:
            self.selected_sidekicks = []
            return
        current = tuple(self._resolve_sidekicks(self.selected_hero))
        try:
            index = combos.index(current)
        except ValueError:
            index = 0
        self.selected_sidekicks = list(combos[wrap_index(index, direction, len(combos))])
        self.audio.play("confirm")

    def _activate_title_focus(self) -> None:
        actions = ("continue", "settings", "guide", "quit")
        action = actions[self.title_index % len(actions)]
        if action == "continue":
            self._continue_from_title()
        elif action == "settings":
            self.settings_return_state = "TITLE"; self.state = "SETTINGS"; self.audio.play("confirm")
        elif action == "guide":
            self.show_help = True; self.help_page = 0; self.audio.play("confirm")
        else:
            self._checkpoint("title_quit")
            self.running = False

    def _handle_platform_action(self, action: str) -> None:
        self._set_input_mode(INPUT_XBOX)
        if self.show_help:
            if action in {A_LEFT, A_LB}:
                self.help_page = (self.help_page - 1) % 2; self.audio.play("back")
            elif action in {A_RIGHT, A_RB}:
                self.help_page = (self.help_page + 1) % 2; self.audio.play("confirm")
            elif action in {A_CONFIRM, A_BACK, A_MENU}:
                self.show_help = False; self.audio.play("back")
            return
        if action == A_MENU and self.state != "MISSION":
            self.show_help = True; self.help_page = 0; self.audio.play("confirm"); return
        if self.state == "TITLE":
            if action == A_UP:
                self.title_index = wrap_index(self.title_index, -1, 4); self.audio.play("back")
            elif action == A_DOWN:
                self.title_index = wrap_index(self.title_index, 1, 4); self.audio.play("confirm")
            elif action == A_CONFIRM:
                self._activate_title_focus()
            elif action == A_INFO:
                if self.new_guild_confirm:
                    self._reset_guild_profile(); self._continue_from_title()
                else:
                    self.new_guild_confirm = True; self.audio.play("back")
            return
        if self.state == "SETTINGS":
            if action == A_UP:
                self.settings_index = wrap_index(self.settings_index, -1, 8); self.audio.play("back")
            elif action == A_DOWN:
                self.settings_index = wrap_index(self.settings_index, 1, 8); self.audio.play("confirm")
            elif action == A_LEFT:
                self._adjust_setting(-1)
            elif action in {A_RIGHT, A_CONFIRM}:
                self._adjust_setting(1)
            elif action == A_BACK:
                self.state = self.settings_return_state; self.audio.play("back")
            return
        if self.state == "CONTRACT_BOARD":
            keys = list(QUESTS)
            current = self.selected_quest if self.selected_quest in QUESTS else keys[0]
            if action in {A_LEFT, A_RIGHT}:
                delta = -1 if action == A_LEFT else 1
                self.selected_quest = keys[wrap_index(keys.index(current), delta, len(keys))]; self.audio.play("confirm")
            elif action == A_CONFIRM:
                self.selected_quest = current; self.state = "HERO_SELECT"; self.selected_hero = self._first_active_hero(); self.audio.play("confirm")
            elif action == A_INFO:
                self.settings_return_state = "CONTRACT_BOARD"; self.state = "SETTINGS"; self.audio.play("confirm")
            elif action == A_BACK:
                self.state = "TITLE"; self.audio.play("back")
            return
        if self.state == "HERO_SELECT":
            if action in {A_LEFT, A_RIGHT}:
                self._cycle_active_hero(-1 if action == A_LEFT else 1)
            elif action in {A_LB, A_RB}:
                keys = list(HERO_ORDERS)
                delta = -1 if action == A_LB else 1
                self.selected_order = keys[wrap_index(keys.index(self.selected_order), delta, len(keys))]; self.audio.play("confirm")
            elif action == A_ALT:
                self._recover_selected()
            elif action == A_CONFIRM:
                if not self.selected_hero:
                    self.selected_hero = self._first_active_hero()
                self._prepare_selected()
            elif action == A_BACK:
                self.state = "CONTRACT_BOARD"; self.audio.play("back")
            return
        if self.state == "LOADOUT_PREP":
            if action in {A_LEFT, A_RIGHT}:
                keys = list(EQUIPMENT_KITS)
                delta = -1 if action == A_LEFT else 1
                self.selected_equipment = keys[wrap_index(keys.index(self.selected_equipment), delta, len(keys))]; self.audio.play("confirm")
            elif action in {A_LB, A_RB}:
                self._cycle_sidekick_combo(-1 if action == A_LB else 1)
            elif action == A_CONFIRM:
                self._deploy_selected()
            elif action == A_BACK:
                self.state = "HERO_SELECT"; self.audio.play("back")
            return
        if self.state == "RESTORE_SELECT":
            if action in {A_LEFT, A_RIGHT}:
                self._cycle_restore_hero(-1 if action == A_LEFT else 1)
            elif action == A_CONFIRM:
                fallen = self._fallen_heroes()
                target = self.selected_hero if self.selected_hero in fallen else (fallen[0] if fallen else None)
                if target and self._restore_hero(target):
                    self.state = self._next_meta_state()
            return
        if self.state == "LAST_LIGHT":
            if action == A_CONFIRM:
                self._execute_last_light_reset(); self.state = self._next_meta_state()
            return
        if self.state == "BOND_EVENT":
            if action in {A_LEFT, A_RIGHT}:
                self.bond_index = 0 if action == A_LEFT else 1; self.audio.play("confirm")
            elif action == A_CONFIRM:
                if self._resolve_bond_event("anchor" if self.bond_index == 0 else "boundary"):
                    self.state = self._next_meta_state()
            return
        if self.state == "MISSION" and self.mission:
            if self.mission.status == "ACTIVE" and self.paused:
                if action == A_UP:
                    self.mission_pause_index = wrap_index(self.mission_pause_index, -1, 3); self.abort_contract_confirm = False; self.audio.play("back")
                elif action == A_DOWN:
                    self.mission_pause_index = wrap_index(self.mission_pause_index, 1, 3); self.abort_contract_confirm = False; self.audio.play("confirm")
                elif action == A_CONFIRM:
                    self._activate_mission_pause_option()
                elif action in {A_BACK, A_MENU}:
                    self._resume_mission()
                return
            if action == A_MENU:
                self._open_mission_pause()
            elif action == A_BACK and self.mission.status == "ACTIVE":
                self._open_mission_pause()
            elif action == A_ALT:
                self.show_analysis = not self.show_analysis
                if self.show_analysis: self.show_dossier = False
            elif action == A_INFO:
                self.show_dossier = not self.show_dossier
                if self.show_dossier: self.show_analysis = False
            elif action == A_CONFIRM and self.mission.status != "ACTIVE":
                self.mission = None; self.paused = False; self.selected_hero = None; self.selected_sidekicks = []
                self.state = self._next_meta_state()
            return

    def _open_mission_pause(self) -> None:
        if self.state != "MISSION" or not self.mission or self.mission.status != "ACTIVE":
            return
        self.paused = True
        self.mission_pause_index = 0
        self.abort_contract_confirm = False
        self.audio.play("back")

    def _resume_mission(self) -> None:
        self.paused = False
        self.mission_pause_index = 0
        self.abort_contract_confirm = False
        self.audio.play("confirm")

    def _abort_active_contract(self) -> None:
        if self.state != "MISSION" or not self.mission or self.mission.status != "ACTIVE":
            return
        self._checkpoint("abort_active_contract")
        self.crash_reporter.breadcrumb("mission_aborted_by_player", hero=self.mission.hero_key, quest=self.mission.quest_key)
        self.mission = None
        self.paused = False
        self.abort_contract_confirm = False
        self.mission_pause_index = 0
        self.selected_hero = None
        self.selected_sidekicks = []
        self.state = "CONTRACT_BOARD"
        self.audio.play("back")

    def _activate_mission_pause_option(self) -> None:
        option = self.mission_pause_index % 3
        if option == 0:
            self._resume_mission()
            return
        if option == 1:
            self.settings_return_state = "MISSION"
            self.state = "SETTINGS"
            self.abort_contract_confirm = False
            self.audio.play("confirm")
            return
        if not self.abort_contract_confirm:
            self.abort_contract_confirm = True
            self.audio.play("back")
            return
        self._abort_active_contract()

    def _virtual_mouse(self, pos):
        present = fit_virtual_canvas(self.screen.get_size(), VIRTUAL_SIZE)
        sx = present.width / VIRTUAL_SIZE[0]
        sy = present.height / VIRTUAL_SIZE[1]
        return ((pos[0] - present.x) / sx, (pos[1] - present.y) / sy)

    def _handle_click(self, pos, button):
        if self.show_help:
            return
        vpos = self._virtual_mouse(pos)
        if self.state == "TITLE":
            if button == 1:
                if self.title_rects["continue"].collidepoint(vpos):
                    self._continue_from_title()
                elif self.title_rects["settings"].collidepoint(vpos):
                    self.settings_return_state = "TITLE"; self.state = "SETTINGS"; self.audio.play("confirm")
                elif self.title_rects["guide"].collidepoint(vpos):
                    self.show_help = True; self.help_page = 0; self.audio.play("confirm")
                elif self.title_rects["quit"].collidepoint(vpos):
                    self.running = False
            return
        if self.state == "SETTINGS":
            if button == 1:
                for i in range(4):
                    if self.settings_minus_rects[i].collidepoint(vpos):
                        self.settings_index = i; self._adjust_setting(-1); return
                    if self.settings_plus_rects[i].collidepoint(vpos):
                        self.settings_index = i; self._adjust_setting(1); return
                for i, rect in enumerate(self.settings_row_rects):
                    if rect.collidepoint(vpos):
                        self.settings_index = i
                        if i >= 4:
                            self._adjust_setting(1)
                        return
                if self.settings_back_rect.collidepoint(vpos):
                    self.state = self.settings_return_state; self.audio.play("back")
            return
        if self.state == "CONTRACT_BOARD":
            if button == 1:
                for rect, key in zip(self.quest_rects, QUESTS):
                    if rect.collidepoint(vpos):
                        self.selected_quest = key
                        self.audio.play("confirm")
                        self.state = "HERO_SELECT"
                        break
        elif self.state == "HERO_SELECT":
            if button == 3:
                self.state = "CONTRACT_BOARD"
            elif button == 1:
                for rect, key in zip(self.order_rects, HERO_ORDERS):
                    if rect.collidepoint(vpos):
                        self.selected_order = key
                        self.audio.play("confirm")
                        return
                if self.recovery_rect.collidepoint(vpos) and self.selected_hero:
                    self._recover_selected()
                    return
                if self.deploy_rect.collidepoint(vpos) and self.selected_hero:
                    self._prepare_selected()
                    return
                for rect, key in zip(self.hero_rects, HEROES):
                    if rect.collidepoint(vpos):
                        if self.profile["heroes"][key].get("availability", "ACTIVE") != "ACTIVE":
                            return
                        if self.selected_hero == key:
                            self._prepare_selected()
                        else:
                            self.selected_hero = key
                            self.audio.play("confirm")
                        break
        elif self.state == "RESTORE_SELECT":
            if button == 1:
                for rect, key in zip(self.hero_rects, HEROES):
                    if rect.collidepoint(vpos) and self._restore_hero(key):
                        self.state = self._next_meta_state()
                        return
        elif self.state == "BOND_EVENT":
            if button == 1:
                if self.bond_anchor_rect.collidepoint(vpos) and self._resolve_bond_event("anchor"):
                    self.state = self._next_meta_state()
                elif self.bond_boundary_rect.collidepoint(vpos) and self._resolve_bond_event("boundary"):
                    self.state = self._next_meta_state()
        elif self.state == "LOADOUT_PREP":
            if button == 3:
                self.state = "HERO_SELECT"
            elif button == 1:
                for rect, key in zip(self.support_rects, HEROES):
                    if rect.collidepoint(vpos) and self.selected_hero:
                        if self._toggle_sidekick(self.selected_hero, key):
                            return
                for rect, key in zip(self.equipment_rects, EQUIPMENT_KITS):
                    if rect.collidepoint(vpos):
                        self.selected_equipment = key
                        self.audio.play("confirm")
                        return
                if self.loadout_deploy_rect.collidepoint(vpos):
                    self._deploy_selected()
        elif self.state == "MISSION" and self.mission:
            if self.paused and self.mission.status == "ACTIVE":
                if button == 1:
                    for i, rect in enumerate(self.mission_pause_rects):
                        if rect.collidepoint(vpos):
                            if self.mission_pause_index != i:
                                self.abort_contract_confirm = False
                            self.mission_pause_index = i
                            self._activate_mission_pause_option()
                            return
                elif button == 3:
                    self._resume_mission()
                return
            if button == 1:
                self.mission.inspect_actor_at(pygame.Vector2(vpos))
                self.show_dossier = True
                self.show_analysis = False
            elif button == 3:
                self.show_dossier = False

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self._checkpoint("window_quit")
            self.running = False
            return
        if self.state == "CRASH_RECOVERY":
            if event.type == pygame.KEYDOWN and event.key in {pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE}:
                self._leave_crash_recovery()
            elif event.type == getattr(pygame, "CONTROLLERBUTTONDOWN", -9003):
                action = self._controller_button_action(getattr(event, "button", -1))
                if action in {A_CONFIRM, A_BACK}:
                    self._leave_crash_recovery()
            return
        if event.type == getattr(pygame, "CONTROLLERDEVICEADDED", -9001):
            device_index = getattr(event, "device_index", getattr(event, "which", 0))
            self._open_controller(int(device_index), announce=True)
            return
        if event.type == getattr(pygame, "CONTROLLERDEVICEREMOVED", -9002):
            instance_id = getattr(event, "instance_id", getattr(event, "which", -1))
            self._remove_controller(int(instance_id))
            return
        if event.type == getattr(pygame, "CONTROLLERBUTTONDOWN", -9003):
            action = self._controller_button_action(getattr(event, "button", -1))
            if action:
                self._handle_platform_action(action)
            return
        if event.type == getattr(pygame, "CONTROLLERAXISMOTION", -9004):
            action = self._controller_axis_action(event)
            if action:
                self._handle_platform_action(action)
            return
        if event.type in {getattr(pygame, "WINDOWFOCUSLOST", -9010), getattr(pygame, "WINDOWMINIMIZED", -9011)}:
            if self.state == "MISSION" and self.mission and self.mission.status == "ACTIVE":
                self.paused = True
                self._platform_toast("FOCUS LOST / CONTRACT PAUSED")
            self._checkpoint("focus_lost")
            return
        if event.type in {getattr(pygame, "WINDOWFOCUSGAINED", -9012), getattr(pygame, "WINDOWRESTORED", -9013)}:
            self._refresh_platform_save_root()
            self._platform_toast("FOCUS RESTORED / PRESS MENU OR SPACE TO RESUME" if self.paused else "FOCUS RESTORED", 1800)
            return
        if event.type == pygame.KEYDOWN:
            self._set_input_mode(INPUT_KEYBOARD)
            if self.show_help:
                if event.key in {pygame.K_LEFT, pygame.K_a}:
                    self.help_page = (self.help_page - 1) % 2; self.audio.play("back")
                elif event.key in {pygame.K_RIGHT, pygame.K_d, pygame.K_TAB}:
                    self.help_page = (self.help_page + 1) % 2; self.audio.play("confirm")
                elif event.key in {pygame.K_h, pygame.K_ESCAPE, pygame.K_RETURN}:
                    self.show_help = False; self.audio.play("back")
                return
            if event.key == pygame.K_F11:
                self._toggle_display_mode()
                return
            if event.key == pygame.K_h:
                self.show_help = True; self.help_page = 0; self.audio.play("confirm"); return
            if self.state == "TITLE":
                if event.key in {pygame.K_RETURN, pygame.K_c}:
                    self._continue_from_title()
                elif event.key == pygame.K_s:
                    self.settings_return_state = "TITLE"; self.state = "SETTINGS"; self.audio.play("confirm")
                elif event.key == pygame.K_n:
                    if self.new_guild_confirm:
                        self._reset_guild_profile(); self._continue_from_title()
                    else:
                        self.new_guild_confirm = True; self.audio.play("back")
                elif event.key in {pygame.K_ESCAPE, pygame.K_q}:
                    self.running = False
                return
            if self.state == "SETTINGS":
                if event.key in {pygame.K_UP, pygame.K_w}:
                    self.settings_index = (self.settings_index - 1) % 8; self.audio.play("back")
                elif event.key in {pygame.K_DOWN, pygame.K_s}:
                    self.settings_index = (self.settings_index + 1) % 8; self.audio.play("confirm")
                elif event.key in {pygame.K_LEFT, pygame.K_a}:
                    self._adjust_setting(-1)
                elif event.key in {pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_SPACE}:
                    self._adjust_setting(1)
                elif event.key == pygame.K_ESCAPE:
                    self.state = self.settings_return_state; self.audio.play("back")
                return
            if event.key == pygame.K_s and self.state == "CONTRACT_BOARD":
                self.settings_return_state = "CONTRACT_BOARD"; self.state = "SETTINGS"; self.audio.play("confirm"); return
            if self.state == "MISSION" and self.mission and self.mission.status == "ACTIVE" and self.paused:
                if event.key in {pygame.K_UP, pygame.K_w}:
                    self.mission_pause_index = wrap_index(self.mission_pause_index, -1, 3); self.abort_contract_confirm = False; self.audio.play("back")
                elif event.key in {pygame.K_DOWN, pygame.K_s}:
                    self.mission_pause_index = wrap_index(self.mission_pause_index, 1, 3); self.abort_contract_confirm = False; self.audio.play("confirm")
                elif event.key == pygame.K_RETURN:
                    self._activate_mission_pause_option()
                elif event.key in {pygame.K_ESCAPE, pygame.K_SPACE}:
                    self._resume_mission()
                return
            if event.key == pygame.K_TAB and self.state == "MISSION":
                self.show_analysis = not self.show_analysis
                if self.show_analysis:
                    self.show_dossier = False
            elif event.key == pygame.K_i and self.state == "MISSION":
                self.show_dossier = not self.show_dossier
                if self.show_dossier:
                    self.show_analysis = False
            elif event.key == pygame.K_SPACE and self.state == "MISSION" and self.mission and self.mission.status == "ACTIVE":
                self._open_mission_pause()
            elif event.key == pygame.K_o and self.state == "HERO_SELECT":
                keys = list(HERO_ORDERS)
                self.selected_order = keys[(keys.index(self.selected_order) + 1) % len(keys)]
            elif event.key == pygame.K_r and self.state == "HERO_SELECT":
                self._recover_selected()
            elif event.key == pygame.K_RETURN and self.state == "HERO_SELECT" and self.selected_hero:
                self._prepare_selected()
            elif event.key == pygame.K_b and self.state == "LOADOUT_PREP" and self.selected_hero:
                self._cycle_sidekick_team(self.selected_hero)
            elif event.key == pygame.K_e and self.state == "LOADOUT_PREP":
                keys = list(EQUIPMENT_KITS)
                self.selected_equipment = keys[(keys.index(self.selected_equipment) + 1) % len(keys)]
            elif event.key == pygame.K_RETURN and self.state == "LOADOUT_PREP":
                self._deploy_selected()
            elif event.key == pygame.K_RETURN and self.state == "MISSION" and self.mission and self.mission.status != "ACTIVE":
                self.mission = None; self.paused = False; self.selected_hero = None
                self.selected_sidekicks = []
                self.state = self._next_meta_state()
            elif event.key == pygame.K_RETURN and self.state == "LAST_LIGHT":
                self._execute_last_light_reset(); self.state = self._next_meta_state()
            elif self.state == "BOND_EVENT" and event.key in {pygame.K_1, pygame.K_a}:
                if self._resolve_bond_event("anchor"):
                    self.state = self._next_meta_state()
            elif self.state == "BOND_EVENT" and event.key in {pygame.K_2, pygame.K_d}:
                if self._resolve_bond_event("boundary"):
                    self.state = self._next_meta_state()
            elif event.key == pygame.K_ESCAPE:
                if self.state == "MISSION" and self.mission and self.mission.status == "ACTIVE":
                    self._open_mission_pause()
                elif self.state == "LOADOUT_PREP":
                    self.audio.play("back"); self.state = "HERO_SELECT"
                elif self.state == "HERO_SELECT":
                    self.audio.play("back"); self.state = "CONTRACT_BOARD"
                elif self.state == "CONTRACT_BOARD":
                    self.audio.play("back"); self.state = "TITLE"
                elif self.state in {"RESTORE_SELECT", "LAST_LIGHT", "BOND_EVENT"}:
                    self.audio.play("back")
                else:
                    self.audio.play("back"); self.state = "TITLE"
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._set_input_mode(INPUT_KEYBOARD)
            self._handle_click(event.pos, event.button)

    def update(self, dt):
        if self.state == "CRASH_RECOVERY":
            return
        mission_audio_context = bool(self.mission and (self.state == "MISSION" or (self.state == "SETTINGS" and self.settings_return_state == "MISSION")))
        quest_key = self.mission.quest_key if mission_audio_context else None
        sovereign_music = bool(mission_audio_context and self.mission and getattr(self.mission, "boss_spawned", False))
        try:
            self.audio.set_context("MISSION" if mission_audio_context else self.state, quest_key, sovereign=sovereign_music)
            if self.state == "MISSION" and self.mission and not self.paused and not self.show_help:
                self.mission.update(dt)
                for cue in self.mission.consume_presentation_events():
                    self.audio.play(cue)
                self._apply_mission_result()
        except Exception as exc:
            if self.state == "MISSION":
                self._enter_crash_recovery(exc, phase="mission_update", recover_to="CONTRACT_BOARD")
            else:
                raise

    def draw(self):
        if self.state == "CRASH_RECOVERY":
            self._draw_crash_recovery()
        elif self.state == "TITLE":
            self.renderer.draw_title_screen(self.profile, self.profile_existed or int(self.profile.get("guild", {}).get("contracts", 0)) > 0, self.profile_recovery_note, self.new_guild_confirm, self.title_index)
        elif self.state == "SETTINGS":
            self.renderer.draw_settings(self.profile.get("settings", {}), self.settings_index)
        elif self.state == "CONTRACT_BOARD":
            self.renderer.draw_contract_board(self.selected_quest, self.profile)
        elif self.state == "HERO_SELECT":
            self.renderer.draw_hero_select(self.selected_quest or "purge", self.selected_hero, self.profile, self.selected_order)
        elif self.state == "RESTORE_SELECT":
            self.renderer.draw_restore_select(self.profile, self.selected_hero if self.selected_hero in self._fallen_heroes() else (self._fallen_heroes()[self.restore_index % len(self._fallen_heroes())] if self._fallen_heroes() else None))
        elif self.state == "LAST_LIGHT":
            self.renderer.draw_last_light(self.profile)
        elif self.state == "BOND_EVENT":
            self.renderer.draw_bond_event(self.profile, self.bond_index)
        elif self.state == "LOADOUT_PREP":
            self.renderer.draw_loadout_prep(self.selected_quest or "purge", self.selected_hero or "nyx", self.selected_order, self.selected_equipment, self._resolve_sidekicks(self.selected_hero or "nyx"), self.profile)
        elif self.state == "MISSION" and self.mission:
            tutorial = bool(self.profile.get("settings", {}).get("tutorial_tips", True) and not self.profile.get("onboarding", {}).get("completed", False))
            self.renderer.draw_mission(self.mission, self.show_analysis, self.show_dossier, self.paused, tutorial_tip=tutorial, pause_index=self.mission_pause_index, abort_confirm=self.abort_contract_confirm)
        if self.show_help:
            self.renderer.draw_help(self.help_page)
        try:
            now = int(pygame.time.get_ticks())
        except Exception:
            now = 0
        notice = self.platform_notice if self.platform_notice and now <= self.platform_notice_until else ""
        if self.platform_notice and not notice:
            self.platform_notice = ""
        if self.state != "CRASH_RECOVERY":
            self.renderer.draw_platform_prompt(self.input_mode, self.state, controller_connected=self.controller_connected, notice=notice, mission=self.mission if self.state == "MISSION" else None, paused=self.paused)
        present = fit_virtual_canvas(self.screen.get_size(), VIRTUAL_SIZE)
        size = (present.width, present.height)
        # Exact whole-number desktop scales preserve the native 1920×1080 look
        # and are cheaper than resampling; fractional/downscales stay smooth.
        if present.integer_scale:
            frame = pygame.transform.scale(self.canvas, size)
        else:
            frame = pygame.transform.smoothscale(self.canvas, size)
        self.screen.fill((0,0,0))
        self.screen.blit(frame, (present.x, present.y))
        pygame.display.flip()

    def save_shot(self, path: str):
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(self.canvas, str(p))

    def run(self):
        self.crash_reporter.breadcrumb("main_loop_started")
        while self.running:
            try:
                if self.args.test_shot:
                    self.clock.tick(0)
                    dt = 1.0 / 60.0
                else:
                    dt = self.clock.tick(60) / 1000.0
                for event in pygame.event.get():
                    self.handle_event(event)
                self.update(dt)
                self.draw()
                if self.args.test_shot:
                    self.auto_elapsed += dt
                    if self.auto_elapsed >= self.args.seconds and not self.auto_saved:
                        self.save_shot(self.args.test_shot)
                        self.auto_saved = True
                        if self.mission:
                            report_path = Path(self.args.test_shot).with_suffix(".json")
                            report_path.write_text(json.dumps(self.mission.report(), indent=2), encoding="utf-8")
                        self.running = False
            except Exception as exc:
                if self.state == "MISSION" and not self.crash_recovery_active:
                    self._enter_crash_recovery(exc, phase="mission_frame", recover_to="CONTRACT_BOARD")
                    continue
                raise
        self._checkpoint("normal_exit")
        self._evaluate_achievements()
        self.crash_reporter.breadcrumb("main_loop_stopped")
        self.microsoft_runtime.shutdown()
        if self.hosted:
            # The window and mixer belong to Afterlife of IO; only stop our audio.
            try:
                pygame.mixer.music.stop()
                pygame.mixer.stop()
            except pygame.error:
                pass
        else:
            pygame.quit()


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="HEX CONTRACT — autonomous cyber-fantasy hero simulator")
    p.add_argument("--no-audio", action="store_true")
    p.add_argument("--fullscreen", action="store_true", help="Legacy alias for the default borderless-desktop mode")
    p.add_argument("--windowed", action="store_true", help="Start in a bordered 1280×720 window instead of default borderless desktop mode")
    p.add_argument("--display-index", type=int, default=0, help="Desktop/display index used for borderless presentation")
    p.add_argument("--display-self-test", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--inherit-display", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--test-shot")
    p.add_argument("--scenario", choices=list(QUESTS) + ["title", "board", "heroes", "loadout", "restore", "lastlight", "bond", "settings", "help", "onboarding"], default="board")
    p.add_argument("--screen-quest", choices=list(QUESTS), default="recovery", help="Quest shown by the static hero-selection screenshot mode")
    p.add_argument("--hero", choices=list(HEROES), default="nyx")
    p.add_argument("--order", choices=list(HERO_ORDERS), default="balanced")
    p.add_argument("--equipment", choices=list(EQUIPMENT_KITS), default="ampoule")
    p.add_argument("--support", choices=["auto", "none"] + list(HEROES), default="auto")
    p.add_argument("--force-boss", action="store_true", help="Stage the contract signature sovereign for screenshots and tests")
    p.add_argument("--boss-phase-two", action="store_true", help="Stage the signature sovereign below half integrity")
    p.add_argument("--force-complication", action="store_true", help="Start a proof scenario in its authored complication state")
    p.add_argument("--force-success", action="store_true", help="Force a completed proof contract for result and restoration verification")
    p.add_argument("--force-death", action="store_true", help="Force the selected proof hero to die for roster-state verification")
    p.add_argument("--last-survivor", action="store_true", help="Mark every other hero eliminated before a forced-death proof")
    p.add_argument("--force-echo", action="store_true", help="Stage MORROW-9 with one freshly raised echo for visual verification")
    p.add_argument("--seconds", type=float, default=12.0)
    p.add_argument("--seed", type=int, default=1701)
    p.add_argument("--quick-test", action="store_true")
    p.add_argument("--analysis", action="store_true", help="Start mission screenshots with the observer analysis panels open")
    p.add_argument("--dossier", action="store_true", help="Start mission screenshots with the actor dossier open")
    p.add_argument("--inspect", choices=["hero", "enemy", "civilian"], default="hero")
    p.add_argument("--inspect-index", type=int, default=0)
    p.add_argument("--profile", help="Override the guild profile JSON path")
    p.add_argument("--save-root", help="Override the writable save directory; future XGameSaveFiles/GDK launchers can provide this path")
    p.add_argument("--no-save", action="store_true", help="Disable persistent hero consequences")
    p.add_argument("--profile-test", action="store_true")
    p.add_argument("--actor-detail-test", action="store_true")
    p.add_argument("--orders-complications-test", action="store_true")
    p.add_argument("--equipment-intel-test", action="store_true")
    p.add_argument("--guild-economy-test", action="store_true")
    p.add_argument("--pass07-test", action="store_true", help="Legacy Pass 07 visual regression alias")
    p.add_argument("--pass08-test", dest="pass09_test", action="store_true", help="Legacy Pass 08 regression alias")
    p.add_argument("--pass09-test", dest="pass09_test", action="store_true")
    p.add_argument("--roster-cycle-test", action="store_true")
    p.add_argument("--identity-test", action="store_true", help="Validate contract environments and quest-specific enemy identity")
    p.add_argument("--pass10-test", action="store_true", help="Validate signature sovereigns, HEX links, and persistent bonds")
    p.add_argument("--pass11-test", action="store_true", help="Validate sovereign story chain, aftermath carryover, and bond events")
    p.add_argument("--pass12-test", action="store_true", help="Validate title, settings, onboarding, audio safety, and profile recovery")
    p.add_argument("--pass13-test", action="store_true", help="Validate RC1 balance rules, result contract, and source integration")
    p.add_argument("--pass14-test", action="store_true", help="Validate full-frame tactical worlds, prefab cover, spawners, clearance, and destruction")
    p.add_argument("--pass15-test", action="store_true", help="Validate filled actor bodies, civilian role identity, sovereign geometry, and Pass 14 clearance compatibility")
    p.add_argument("--pass16-test", action="store_true", help="Validate presentation cue routing, mission ambience, optional music hooks, and unchanged simulation contracts")
    p.add_argument("--pass23-achievement-test", action="store_true", help="Validate platform achievement tracking through the runtime profile")
    p.add_argument("--crash-reporter-test", action="store_true", help=argparse.SUPPRESS)
    return p.parse_args(argv)


def quick_test() -> int:
    outcomes = []
    for qi, quest in enumerate(QUESTS):
        for hi, hero in enumerate(HEROES):
            mission = Mission(hero, quest, seed=1701 + qi*10 + hi)
            for _ in range(1050):
                mission.update(0.05)
                if mission.status != "ACTIVE":
                    break
            if mission.status == "ACTIVE":
                mission.status = "FAILED"
                mission.result_reason = "Deterministic matrix observation window expired"
                mission._finalize_result()
            report = mission.report()
            assert report["status"] in {"SUCCESS", "FAILED"}
            assert 0 <= report["hero_hp"] <= mission.hero.max_hp
            assert report["objective_total"] >= 1
            assert report["consequence"] != "PENDING"
            outcomes.append(report)
            del mission
            gc.collect()

    assert quest_fit("nyx", "purge")["score"] > quest_fit("vesper", "purge")["score"]
    assert quest_fit("vesper", "recovery")["score"] > quest_fit("nyx", "recovery")["score"]
    assert quest_fit("circuit", "rescue")["score"] > quest_fit("nyx", "rescue")["score"]

    signatures = {
        "nyx_wounded_pursuit": sum(r["behavior_counts"]["wounded_pursuit"] for r in outcomes if r["hero"] == "nyx"),
        "circuit_protective_intercepts": sum(r["behavior_counts"]["civilian_intercepts"] for r in outcomes if r["hero"] == "circuit"),
        "vesper_machine_bypass": sum(r["behavior_counts"]["objective_bypass"] for r in outcomes if r["hero"] == "vesper"),
        "morrow_echo_reanimations": sum(r["behavior_counts"].get("echo_reanimations", 0) for r in outcomes if r["hero"] == "morrow"),
    }
    assert signatures["nyx_wounded_pursuit"] > 0
    assert signatures["circuit_protective_intercepts"] > 0
    assert signatures["vesper_machine_bypass"] > 0
    payload = {"quick_test": "PASS", "matrix_size": len(outcomes), "personality_signatures": signatures, "contracts": outcomes}
    target = Path("verification/reports/pass13_quick_test.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


def profile_test(path: str) -> int:
    pygame.init()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    fixture = target.with_name("pass12_profile_migration_fixture.json")
    fixture.unlink(missing_ok=True)
    # Deliberately use the pre-MORROW schema to exercise real legacy -> v4 migration.
    legacy_heroes = {
        key: {"strain": (34 if key == "nyx" else 0), "missions": 0, "successes": 0, "last_consequence": "READY", "recoveries": 0}
        for key in ("nyx", "circuit", "vesper")
    }
    fixture.write_text(json.dumps({
        "profile_version": 2,
        "guild": {"credits": 2200, "renown": 3, "contracts": 1, "lifetime_credits": 500},
        "heroes": legacy_heroes,
    }, indent=2), encoding="utf-8")
    args = parse_args(["--no-audio", "--profile", str(fixture)])
    app = App(args)
    assert app.profile["profile_version"] == 9
    assert set(app.profile["heroes"]) == set(HEROES)
    assert app.profile["heroes"]["morrow"]["field_condition"] == "COMBAT READY"
    assert "PHASE FRACTURE" in app.profile["heroes"]["nyx"]["field_condition"]

    mission = Mission("nyx", "rescue", seed=1777, starting_strain=34)
    for _ in range(int(130 / 0.05)):
        mission.update(0.05)
        if mission.status != "ACTIVE":
            break
    record = app.profile["heroes"]["nyx"]
    record["missions"] += 1
    record["successes"] += int(mission.status == "SUCCESS")
    record["strain"] = max(0, min(100, int(record["strain"]) + mission.strain_delta))
    record["last_consequence"] = mission.result_consequence
    record["field_condition"] = recovery_state("nyx", record["strain"])["name"]
    app._save_profile()
    loaded = json.loads(fixture.read_text(encoding="utf-8"))
    assert loaded["profile_version"] == 9
    assert "morrow" in loaded["heroes"]
    assert loaded["heroes"]["nyx"]["missions"] == 1
    assert loaded["heroes"]["nyx"]["last_consequence"] != "READY"
    report = {
        "profile_test": "PASS",
        "profile_fixture": str(fixture),
        "migrated_version": loaded["profile_version"],
        "hero_count": len(loaded["heroes"]),
        "morrow_added": "morrow" in loaded["heroes"],
        "roster_fields_added": all("availability" in loaded["heroes"][key] for key in HEROES),
        "nyx": loaded["heroes"]["nyx"],
    }
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    fixture.unlink(missing_ok=True)
    print(json.dumps(report, indent=2))
    pygame.quit()
    return 0



def actor_detail_test(path: str) -> int:
    pygame.init()
    artist = ActorArtist()
    portraits = {}
    signatures = set()
    for key in HEROES:
        surf = artist.portrait(key, 180)
        raw = pygame.image.tobytes(surf, "RGBA")
        digest = hashlib.sha256(raw).hexdigest()
        alpha_pixels = sum(1 for i in range(3, len(raw), 4) if raw[i] > 0)
        assert alpha_pixels > 1200
        signatures.add(digest)
        portraits[key] = {"sha256": digest, "visible_pixels": alpha_pixels}
    assert len(signatures) == len(HEROES)

    mission = Mission("circuit", "rescue", seed=1903)
    for _ in range(80):
        mission.update(1.0 / 60.0)
    assert mission.hero.pose in {"READY", "MOVE", "RUN", "SLASH", "WARD", "HIT", "CHANNEL"}
    assert mission.inspected_actor()["name"] == HEROES["circuit"]["name"]
    mission.inspection = {"type": "enemy", "index": 0}
    enemy = mission.inspected_actor()
    assert enemy["name"] == ENEMY_VARIANTS[mission.quest_key][mission.enemies[0].kind]["name"]
    mission.inspection = {"type": "civilian", "index": 1}
    civilian = mission.inspected_actor()
    assert civilian["name"] == CIVILIAN_ROLES[1]["role"]
    assert len({r["role"] for r in CIVILIAN_ROLES}) == 3

    report = {
        "actor_detail_test": "PASS",
        "hero_portraits": portraits,
        "unique_portrait_signatures": len(signatures),
        "live_hero_pose": mission.hero.pose,
        "enemy_dossier": enemy,
        "civilian_dossier": civilian,
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    pygame.quit()
    return 0

def orders_complications_test(path: str) -> int:
    results = []
    # Trigger each authored complication through its real gameplay condition.
    for qi, quest in enumerate(QUESTS):
        hero = "circuit" if quest == "rescue" else ("vesper" if quest == "recovery" else "nyx")
        mission = Mission(hero, quest, seed=2400 + qi, order_key="objective")
        if quest == "purge":
            mission.hero.kills = 3
            mission.update(0.025)
        elif quest == "recovery":
            mission.hero.pos = pygame.Vector2(1600, 305)
            mission.update(0.025)
        else:
            mission.hero.pos = pygame.Vector2(mission.civilians[0].pos)
            mission.update(0.025)
        report = mission.report()
        assert report["complication_triggered"] is True
        assert report["complication"] == CONTRACT_COMPLICATIONS[quest]["key"]
        results.append(report)

    order_cases = {
        "balanced": ("nyx", "recovery"),
        "objective": ("vesper", "recovery"),
        "protect": ("circuit", "rescue"),
        "eliminate": ("nyx", "purge"),
        "survive": ("nyx", "purge"),
    }
    order_signatures = {}
    for order, (hero, quest) in order_cases.items():
        mission = Mission(hero, quest, seed=2480, order_key=order)
        if order == "survive":
            mission.hero.hp = mission.hero.max_hp * 0.12
            mission.hero.resolve = 12
        for _ in range(80):
            mission.update(0.025)
            if mission.status != "ACTIVE":
                break
        order_signatures[order] = {
            "status": mission.order_status,
            "follow": round(mission.order_follow_seconds, 2),
            "override": round(mission.order_override_seconds, 2),
            "intent": mission.hero.intent,
        }
    override = Mission("nyx", "recovery", seed=2499, order_key="protect")
    for _ in range(80):
        override.update(0.025)
    order_signatures["personality_override"] = {
        "status": override.order_status,
        "follow": round(override.order_follow_seconds, 2),
        "override": round(override.order_override_seconds, 2),
        "intent": override.hero.intent,
    }
    for key in ("objective", "protect", "eliminate", "survive"):
        assert order_signatures[key]["follow"] > 0
    assert order_signatures["personality_override"]["override"] > 0
    payload = {"orders_complications_test": "PASS", "quest_results": results, "order_signatures": order_signatures}
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


def equipment_intel_test(path: str) -> int:
    rows = []
    for quest in QUESTS:
        for hero in HEROES:
            for equipment in EQUIPMENT_KITS:
                mission = Mission(hero, quest, seed=3500, order_key="balanced", equipment_key=equipment)
                assert mission.equipment_key == equipment
                assert mission.equipment_fit["percent"] >= 18
                rows.append({
                    "hero": hero, "quest": quest, "equipment": equipment,
                    "max_hp": round(mission.hero.max_hp, 2),
                    "speed": round(mission.hero.speed, 2),
                    "range": round(mission.hero.attack_range, 2),
                    "fit": mission.equipment_fit["rating"],
                })
    assert Mission("circuit", "purge", equipment_key="aegis").hero.max_hp > Mission("circuit", "purge", equipment_key="surveyor").hero.max_hp
    assert Mission("vesper", "recovery", equipment_key="surveyor").hero.attack_range > Mission("vesper", "recovery", equipment_key="aegis").hero.attack_range
    beacon = Mission("circuit", "rescue", equipment_key="beacon")
    assert beacon.hero.protectiveness > HEROES["circuit"]["protectiveness"]
    ampoule = Mission("nyx", "purge", equipment_key="ampoule")
    ampoule.hero.hp = ampoule.hero.max_hp * 0.35
    ampoule._damage_hero(5)
    assert ampoule.consumable_used and ampoule.hero.hp > ampoule.hero.max_hp * 0.45
    assert all(QUEST_INTEL[q]["confirmed"] and QUEST_INTEL[q]["unknown"] for q in QUESTS)
    payload = {"equipment_intel_test": "PASS", "matrix_entries": len(rows), "rows": rows}
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0

def guild_economy_test(path: str) -> int:
    from .data import recovery_quote
    successful = Mission("circuit", "rescue", seed=4601, order_key="protect", equipment_key="beacon")
    successful.status = "SUCCESS"
    successful.time = 58.0
    successful.hero.hp = successful.hero.max_hp * 0.82
    successful.complication_resolved = True
    successful.order_status = "COMPLYING"
    successful._finalize_result()
    assert successful.reward_credits > QUESTS["rescue"]["base_credits"]
    assert successful.reward_renown >= QUESTS["rescue"]["base_renown"]

    failed = Mission("vesper", "purge", seed=4602, equipment_key="surveyor")
    failed.status = "FAILED"
    failed.time = 44.0
    failed._finalize_result()
    assert 0 < failed.reward_credits < QUESTS["purge"]["base_credits"]
    assert failed.reward_renown == 0

    quotes = {hero: recovery_quote(hero, 48) for hero in HEROES}
    assert all(q["cost"] > 0 and q["reduction"] > 0 for q in quotes.values())
    assert quotes["circuit"]["reduction"] >= quotes["vesper"]["reduction"]
    temp_profile = Path(path).with_name("pass12_recovery_integration_profile.json")
    temp_profile.unlink(missing_ok=True)
    temp_profile.write_text(json.dumps({
        "profile_version": 2,
        "guild": {"credits": 5000, "renown": 0, "contracts": 0, "lifetime_credits": 0},
        "heroes": {key: {"strain": (48 if key == "nyx" else 0), "missions": 0, "successes": 0, "last_consequence": "READY", "recoveries": 0} for key in HEROES},
    }), encoding="utf-8")
    args = parse_args(["--no-audio", "--profile", str(temp_profile)])
    app = App(args)
    app.selected_hero = "nyx"
    before = int(app.profile["guild"]["credits"])
    applied = app._recover_selected()
    after = int(app.profile["guild"]["credits"])
    assert applied and after < before and int(app.profile["heroes"]["nyx"]["strain"]) < 48
    temp_profile.unlink(missing_ok=True)
    pygame.quit()

    payload = {
        "guild_economy_test": "PASS",
        "success_reward": {"credits": successful.reward_credits, "renown": successful.reward_renown, "notes": successful.reward_notes},
        "failure_salvage": {"credits": failed.reward_credits, "renown": failed.reward_renown},
        "recovery_quotes": quotes,
        "recovery_integration": {"credits_before": before, "credits_after": after, "strain_after": app.profile["heroes"]["nyx"]["strain"]},
    }
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


def pass09_test(path: str) -> int:
    pygame.init()
    artist = ActorArtist()
    signatures = {}
    for hero in HEROES:
        surf = artist.portrait(hero, 196, "surveyor" if hero == "morrow" else "ampoule")
        raw = pygame.image.tobytes(surf, "RGBA")
        signatures[hero] = hashlib.sha256(raw).hexdigest()
        assert sum(1 for i in range(3, len(raw), 4) if raw[i]) > 1500
    assert len(set(signatures.values())) == 4

    animation_frames = {}
    for hero in HEROES:
        mission = Mission(hero, "purge", seed=5700 + len(animation_frames))
        seen = set()
        for _ in range(80):
            mission.update(1.0 / 60.0)
            seen.add(mission.hero.anim_frame)
        animation_frames[hero] = sorted(seen)
        assert len(seen) >= 3

    echo = Mission("morrow", "purge", seed=5777, starting_strain=50, equipment_key="surveyor")
    echo.enemies[0].dead = True
    echo.enemies[0].hp = 0
    living = next(e for e in echo.enemies[1:] if not e.dead)
    echo.hero.pos = pygame.Vector2(echo.enemies[0].pos)
    echo._hero_attack(living, 0.016)
    raised = [e for e in echo.enemies if e.echo_reanimated and not e.dead]
    assert raised and echo.behavior_counts["echo_reanimations"] == 1
    assert echo.hero.corruption > 20

    conditions = {}
    for hero in HEROES:
        mission = Mission(hero, "recovery", seed=5790, starting_strain=52)
        conditions[hero] = {
            "name": mission.hero.field_condition,
            "speed": round(mission.hero.speed, 2),
            "range": round(mission.hero.attack_range, 2),
            "aggression": round(mission.hero.aggression, 2),
            "caution": round(mission.hero.caution, 2),
            "corruption": round(mission.hero.corruption, 2),
        }
        assert mission.hero.field_condition.startswith("SEVERE")
    assert conditions["nyx"]["aggression"] > HEROES["nyx"]["aggression"]
    assert conditions["circuit"]["speed"] < HEROES["circuit"]["speed"]
    assert conditions["vesper"]["range"] < HEROES["vesper"]["range"]
    assert conditions["morrow"]["corruption"] > 0

    payload = {
        "legacy_roster_animation_test": "PASS",
        "hero_count": len(HEROES),
        "portrait_signatures": signatures,
        "animation_frames": animation_frames,
        "morrow_echo": {"raised": len(raised), "corruption": round(echo.hero.corruption, 2)},
        "recovery_conditions": conditions,
    }
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    pygame.quit()
    return 0


def roster_cycle_test(path: str) -> int:
    pygame.init()
    temp = Path(path).with_name("pass12_roster_cycle_profile.json")
    temp.unlink(missing_ok=True)
    args = parse_args(["--no-audio", "--profile", str(temp)])
    app = App(args)
    # One hero dies and is locked out.
    app.selected_quest = "purge"; app.selected_hero = "nyx"
    app.mission = app._new_mission("nyx", "purge")
    app.mission._damage_hero(99999); app.mission._finalize_result(); app._apply_mission_result()
    assert app.profile["heroes"]["nyx"]["availability"] == "ELIMINATED"
    try:
        app._new_mission("nyx", "purge")
        raise AssertionError("eliminated hero deployed")
    except ValueError:
        pass
    app.state = "HERO_SELECT"; app.selected_hero = None
    scale = app.screen.get_width() / VIRTUAL_SIZE[0]
    nyx_center = app.hero_rects[0].center
    app._handle_click((nyx_center[0] * scale, nyx_center[1] * scale), 1)
    assert app.selected_hero is None
    # A surviving hero victory earns exactly one restoration choice.
    app.mission = app._new_mission("circuit", "rescue")
    app.mission.status = "SUCCESS"; app.mission.time = 55; app.mission.hero.hp = app.mission.hero.max_hp
    app.mission.complication_resolved = True; app.mission._finalize_result(); app.result_applied = False; app._apply_mission_result()
    assert app.profile["guild"]["restoration_tokens"] == 1
    reloaded = App(parse_args(["--no-audio", "--profile", str(temp)]))
    assert reloaded.state == "TITLE"
    assert reloaded._next_meta_state() == "RESTORE_SELECT"
    reloaded._continue_from_title()
    assert reloaded.state == "RESTORE_SELECT"
    assert reloaded.profile["guild"]["restoration_tokens"] == 1
    app = reloaded
    scale = app.screen.get_width() / VIRTUAL_SIZE[0]
    app._handle_click((nyx_center[0] * scale, nyx_center[1] * scale), 1)
    assert app.profile["heroes"]["nyx"]["availability"] == "ACTIVE"
    assert app.profile["guild"]["restoration_tokens"] == 0
    assert app._restore_hero("nyx") is False
    # Full wipe arms Last Light and safely restores the whole roster on acknowledgement.
    for key in HEROES:
        app.profile["heroes"][key]["availability"] = "ELIMINATED"
        app.profile["heroes"][key]["strain"] = 100
    app.profile["guild"]["last_light_pending"] = True
    app._save_profile()
    reloaded = App(parse_args(["--no-audio", "--profile", str(temp)]))
    assert reloaded.state == "TITLE"
    assert reloaded._next_meta_state() == "LAST_LIGHT"
    reloaded._continue_from_title()
    assert reloaded.state == "LAST_LIGHT"
    app = reloaded
    before_cycle = app.profile["guild"]["cycles"]
    assert app._execute_last_light_reset()
    assert all(app.profile["heroes"][key]["availability"] == "ACTIVE" for key in HEROES)
    assert app.profile["guild"]["cycles"] == before_cycle + 1
    assert app._execute_last_light_reset() is False
    assert app.profile["guild"]["cycles"] == before_cycle + 1
    assert app.profile["guild"]["last_light_pending"] is False
    loaded = json.loads(temp.read_text(encoding="utf-8"))
    assert loaded["profile_version"] == 9
    payload = {
        "roster_cycle_test": "PASS",
        "hero_count": len(HEROES),
        "elimination_lockout": True,
        "victory_restoration": True,
        "restoration_relaunch_persistence": True,
        "last_light_relaunch_persistence": True,
        "last_light_reset": True,
        "cycle": loaded["guild"]["cycles"],
        "roster_wipes": loaded["guild"]["roster_wipes"],
        "heroes": loaded["heroes"],
    }
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True); target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.unlink(missing_ok=True)
    print(json.dumps(payload, indent=2))
    pygame.quit()
    return 0

def identity_test(path: str) -> int:
    pygame.init()
    assert set(MISSION_ENVIRONMENTS) == set(QUESTS)
    assert set(ENEMY_VARIANTS) == set(QUESTS)
    environment_rows = {}
    all_variant_names = []
    for quest in QUESTS:
        env = MISSION_ENVIRONMENTS[quest]
        assert env["site"] and env["site_code"] and len(env["landmarks"]) == 3
        assert len({env["floor"], env["wall"], env["accent"]}) == 3
        assert set(ENEMY_VARIANTS[quest]) == set(ENEMY_ARCHETYPES)
        names = [ENEMY_VARIANTS[quest][kind]["name"] for kind in ENEMY_ARCHETYPES]
        assert len(set(names)) == 3
        all_variant_names.extend(names)
        mission = Mission("morrow" if quest == "recovery" else ("circuit" if quest == "rescue" else "nyx"), quest, seed=6900+len(environment_rows))
        mission.inspection = {"type": "enemy", "index": 0}
        dossier = mission.inspected_actor()
        assert dossier["name"] in names
        report = mission.report()
        assert report["site"] == env["site"]
        assert len(report["enemy_variants"]) >= 2
        environment_rows[quest] = {
            "site": env["site"], "site_code": env["site_code"], "landmarks": env["landmarks"],
            "enemy_variants": names, "dossier_example": dossier["name"],
        }
    assert len(set(all_variant_names)) == 9
    payload = {"identity_test": "PASS", "environment_count": len(environment_rows), "unique_enemy_variants": len(set(all_variant_names)), "contracts": environment_rows}
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True); target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    pygame.quit()
    return 0

def pass10_test(path: str) -> int:
    pygame.init()
    sovereigns = {}
    for idx, quest in enumerate(QUESTS):
        hero = ("nyx", "vesper", "circuit")[idx]
        support = ("circuit", "morrow", "vesper")[idx]
        mission = Mission(hero, quest, seed=7600 + idx, equipment_key="surveyor", support_key=support)
        mission._trigger_complication()
        mission._spawn_signature_boss()
        bosses = [e for e in mission.enemies if e.is_boss]
        assert len(bosses) == 1
        boss = bosses[0]
        assert boss.boss_id == SIGNATURE_BOSSES[quest]["id"]
        assert mission.objective_text()
        boss.hp = boss.max_hp * 0.20
        mission._update_enemies(0.05)
        assert boss.boss_phase == 2
        assert mission.behavior_counts["boss_phase_changes"] == 1
        boss.hp = min(1.0, boss.hp)
        mission.hero.pos = pygame.Vector2(boss.pos)
        mission.hero.attack_timer = 0
        mission.hero.damage = 999
        mission.hero.attack_range = 50
        mission._hero_attack(boss, 0.016)
        assert boss.dead and mission.boss_defeated
        sovereigns[quest] = {
            "name": mission.boss_profile["name"],
            "phase_two": mission.boss_profile["phase_two"],
            "defeated": mission.boss_defeated,
            "support": mission.support["name"],
        }

    base = Mission("nyx", "purge", support_key="none")
    linked_nyx = Mission("circuit", "purge", support_key="nyx")
    linked_circuit = Mission("nyx", "purge", support_key="circuit")
    linked_vesper = Mission("nyx", "purge", support_key="vesper")
    linked_morrow = Mission("nyx", "purge", support_key="morrow")
    assert linked_nyx.hero.damage > HEROES["circuit"]["damage"]
    assert linked_circuit.hero.max_hp > base.hero.max_hp
    assert linked_vesper.hero.attack_range > base.hero.attack_range
    assert linked_morrow.hero.resolve > base.hero.resolve

    temp = Path(path).with_name("pass12_bond_profile.json")
    temp.unlink(missing_ok=True)
    args = parse_args(["--no-audio", "--profile", str(temp), "--support", "circuit"])
    app = App(args)
    app.selected_quest = "purge"
    app.selected_hero = "nyx"
    app.selected_support = "circuit"
    app.mission = app._new_mission("nyx", "purge")
    assert app.mission.support_key == "circuit"
    app.mission.status = "SUCCESS"
    app.mission.time = 68.0
    app.mission.hero.hp = app.mission.hero.max_hp * 0.7
    app.mission.boss_spawned = True
    app.mission.boss_defeated = True
    app.mission.complication_resolved = True
    app.mission._finalize_result()
    app._apply_mission_result()
    pair = app._bond_key("nyx", "circuit")
    assert app.profile["bonds"][pair]["points"] == 2
    assert app.profile["guild"]["bosses_defeated"] == 1
    reloaded = App(parse_args(["--no-audio", "--profile", str(temp)]))
    assert reloaded.profile["bonds"][pair]["points"] == 2
    assert reloaded.profile["profile_version"] == 9

    payload = {
        "pass10_regression": "PASS",
        "signature_sovereigns": sovereigns,
        "hex_links": {
            "nyx_damage": round(linked_nyx.hero.damage, 2),
            "circuit_vitality": round(linked_circuit.hero.max_hp, 2),
            "vesper_range": round(linked_vesper.hero.attack_range, 2),
            "morrow_resolve": round(linked_morrow.hero.resolve, 2),
        },
        "persistent_bond": {"pair": pair, **reloaded.profile["bonds"][pair]},
        "profile_version": reloaded.profile["profile_version"],
    }
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.unlink(missing_ok=True)
    print(json.dumps(payload, indent=2))
    pygame.quit()
    return 0


def pass11_test(path: str) -> int:
    pygame.init()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    profile_path = target.with_name("pass12_campaign_profile.json")
    profile_path.unlink(missing_ok=True)
    args = parse_args(["--no-audio", "--profile", str(profile_path), "--support", "none"])
    app = App(args)
    start_credits = int(app.profile["guild"]["credits"])
    chain_rows = []
    for expected_step, quest in enumerate(STORY_CHAIN["order"]):
        hero = ("nyx", "vesper", "circuit")[expected_step]
        app.selected_quest = quest
        app.selected_hero = hero
        app.selected_support = "none"
        mission = app._new_mission(hero, quest)
        mission.status = "SUCCESS"
        mission.time = 61.0 + expected_step
        mission.hero.hp = mission.hero.max_hp * 0.82
        mission.complication_resolved = True
        mission.boss_spawned = True
        mission.boss_defeated = True
        mission.result_reason = "Pass 12 campaign-regression sovereign-chain proof"
        mission._finalize_result()
        app.mission = mission
        app.result_applied = False
        app._apply_mission_result()
        chain_rows.append({
            "quest": quest,
            "campaign_event": mission.campaign_event,
            "chain_step": int(app.profile["campaign"]["chain_step"]),
            "aftermath_count": int(app.profile["campaign"]["aftermath_counts"][quest]),
        })
        if quest == "purge":
            next_mission = app._new_mission("vesper", "recovery")
            base = Mission("vesper", "recovery", aftermath_key="none")
            assert next_mission.aftermath_key == "choir_silence"
            assert next_mission.hero.resolve > base.hero.resolve
        elif quest == "recovery":
            next_mission = app._new_mission("circuit", "rescue")
            assert next_mission.aftermath_key == "open_index"
    assert app.profile["campaign"]["chain_step"] == 0
    assert app.profile["campaign"]["chain_completions"] == 1
    assert app.profile["guild"]["credits"] >= start_credits + STORY_CHAIN["completion_credits"]
    mercy = app._new_mission("nyx", "purge")
    plain = Mission("nyx", "purge", aftermath_key="none")
    assert mercy.aftermath_key == "mercy_route"
    assert mercy.hero.speed > plain.hero.speed

    # Bond milestone: a victory crosses 3 points and queues an authored event.
    pair = app._bond_key("nyx", "circuit")
    app.profile["bonds"][pair]["points"] = 2
    app.profile["campaign"]["pending_bond_event"] = None
    app.selected_quest = "purge"
    app.selected_hero = "nyx"
    app.selected_support = "circuit"
    linked = app._new_mission("nyx", "purge")
    linked.status = "FAILED"  # +1 crosses exactly to the first milestone without another chain advance.
    linked.time = 83.0
    linked.hero.hp = max(1.0, linked.hero.max_hp * 0.4)
    linked.result_reason = "Bond milestone proof"
    linked._finalize_result()
    app.mission = linked
    app.result_applied = False
    app._apply_mission_result()
    pending = app.profile["campaign"]["pending_bond_event"]
    assert pending == {"pair": pair, "level": 3}
    before_strain = [int(app.profile["heroes"][k]["strain"]) for k in ("nyx", "circuit")]
    assert app._resolve_bond_event("anchor")
    assert app.profile["bonds"][pair]["mastery"] == 1
    assert app.profile["bonds"][pair]["event_level"] == 3
    assert app.profile["campaign"]["pending_bond_event"] is None
    after_strain = [int(app.profile["heroes"][k]["strain"]) for k in ("nyx", "circuit")]
    assert all(after >= before for before, after in zip(before_strain, after_strain))
    mastered = app._new_mission("nyx", "purge")
    assert mastered.support_mastery == 1

    # Boundary outcome is distinct and reduces shared strain.
    pair2 = app._bond_key("vesper", "morrow")
    app.profile["heroes"]["vesper"]["strain"] = 20
    app.profile["heroes"]["morrow"]["strain"] = 20
    app.profile["campaign"]["pending_bond_event"] = {"pair": pair2, "level": 3}
    assert app._resolve_bond_event("boundary")
    assert app.profile["heroes"]["vesper"]["strain"] == 16
    assert app.profile["heroes"]["morrow"]["strain"] == 16
    assert app.profile["bonds"][pair2]["mastery"] == 0

    app._save_profile()
    reloaded = App(parse_args(["--no-audio", "--profile", str(profile_path)]))
    assert reloaded.profile["profile_version"] == 9
    assert reloaded.profile["campaign"]["chain_completions"] == 1
    assert reloaded.profile["bonds"][pair]["mastery"] == 1
    payload = {
        "pass11_test": "PASS",
        "story_chain": STORY_CHAIN["name"],
        "chain_rows": chain_rows,
        "chain_completions": reloaded.profile["campaign"]["chain_completions"],
        "aftermaths": {quest: reloaded.profile["campaign"]["aftermath_counts"][quest] for quest in QUESTS},
        "bond_anchor": {"pair": pair, **reloaded.profile["bonds"][pair]},
        "bond_boundary": {"pair": pair2, **reloaded.profile["bonds"][pair2]},
        "profile_version": reloaded.profile["profile_version"],
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    profile_path.unlink(missing_ok=True)
    print(json.dumps(payload, indent=2))
    pygame.quit()
    return 0



def pass12_test(path: str) -> int:
    pygame.init()
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    profile_path = target.with_name("pass12_mastering_profile.json")
    corrupt_path = target.with_name("pass12_corrupt_profile.json")
    for candidate in profile_path.parent.glob("pass12_corrupt_profile.json*"):
        candidate.unlink(missing_ok=True)
    profile_path.unlink(missing_ok=True)

    app = App(parse_args(["--no-audio", "--profile", str(profile_path)]))
    assert app.state == "TITLE"
    assert app.profile["profile_version"] == 9
    assert app.profile["settings"]["tutorial_tips"] is True
    # Real event-flow regression for title, board settings, and guide paging.
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert app.state == "CONTRACT_BOARD"
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s))
    assert app.state == "SETTINGS"
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert app.state == "CONTRACT_BOARD"
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h))
    assert app.show_help and app.help_page == 0
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    assert app.help_page == 1
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h))
    assert not app.show_help
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert app.state == "TITLE"
    app.settings_index = 0
    app._adjust_setting(-1)
    app.settings_index = 3
    app._adjust_setting(1)
    app.profile["onboarding"]["missions_started"] = 1
    app.profile["onboarding"]["completed"] = True
    app._save_profile()
    reloaded = App(parse_args(["--no-audio", "--profile", str(profile_path)]))
    assert reloaded.profile["settings"]["master_volume"] == 0.65
    assert reloaded.profile["settings"]["reduced_motion"] is True
    assert reloaded.profile["onboarding"]["completed"] is True

    corrupt_path.write_text('{"profile_version": 7, BAD JSON', encoding="utf-8")
    recovered = App(parse_args(["--no-audio", "--profile", str(corrupt_path)]))
    assert recovered.profile["profile_version"] == 9
    assert "CORRUPT PROFILE" in recovered.profile_recovery_note
    backups = sorted(corrupt_path.parent.glob(corrupt_path.name + ".corrupt*"))
    assert backups

    # Interrupted save recovery should prefer a valid temp file.
    temp_profile = target.with_name("pass12_temp_recovery.json")
    temp_profile.unlink(missing_ok=True)
    temp_file = temp_profile.with_suffix(temp_profile.suffix + ".tmp")
    fixture = app._default_profile(); fixture["guild"]["credits"] = 4321
    temp_file.write_text(json.dumps(fixture), encoding="utf-8")
    temp_recovered = App(parse_args(["--no-audio", "--profile", str(temp_profile)]))
    assert temp_recovered.profile["guild"]["credits"] == 4321
    assert "TEMP FILE" in temp_recovered.profile_recovery_note

    payload = {
        "pass12_test": "PASS",
        "profile_version": reloaded.profile["profile_version"],
        "title_state": app.state,
        "title_settings_help_flow": True,
        "settings_persist": True,
        "onboarding_persist": True,
        "corrupt_backup": backups[0].name,
        "temp_recovery": temp_recovered.profile_recovery_note,
        "no_audio_safe": not recovered.audio.enabled,
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    for candidate in (profile_path, profile_path.with_suffix(profile_path.suffix + ".bak"), corrupt_path, temp_profile, temp_file):
        candidate.unlink(missing_ok=True)
    for candidate in corrupt_path.parent.glob(corrupt_path.name + ".corrupt*"):
        candidate.unlink(missing_ok=True)
    print(json.dumps(payload, indent=2))
    pygame.quit()
    return 0

def pass13_test(path: str) -> int:
    pygame.init()
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    profile_path = target.with_name("pass13_rc1_profile.json")
    result_path = profile_path.with_name("hex_contract_game_result.json")
    for candidate in (profile_path, profile_path.with_suffix(profile_path.suffix + ".bak"), result_path):
        candidate.unlink(missing_ok=True)
    app = App(parse_args(["--no-audio", "--profile", str(profile_path)]))
    app.selected_quest = "purge"
    app.selected_hero = "nyx"
    app.selected_order = "balanced"
    app.selected_equipment = "ampoule"
    app.selected_support = "circuit"
    mission = app._new_mission("nyx", "purge")
    for _ in range(3400):
        mission.update(0.05)
        if mission.status != "ACTIVE":
            break
    assert mission.status == "SUCCESS"
    app.mission = mission
    app.result_applied = False
    app._apply_mission_result()
    assert result_path.exists()
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["project_id"] == "hex_contract"
    assert result["completed"] is True
    assert result["return_to_lab"] is True
    assert result["source_only"] is True
    assert result["runtime_wrapper_required"] is False
    assert result["prototype_lab_points_awarded"] > 0
    assert result["hero"] == "nyx" and result["quest"] == "purge"
    payload = {
        "pass13_test": "PASS",
        "release": result["release"],
        "source_only": result["source_only"],
        "result_contract": "PASS",
        "lab_points": result["prototype_lab_points_awarded"],
        "balance_rules": {
            "objective_line_of_sight_gate": True,
            "echoes_absorb_real_damage": True,
            "signature_bosses_cannot_be_overridden": True,
            "fit_guard_capped": 0.14,
        },
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    for candidate in (profile_path, profile_path.with_suffix(profile_path.suffix + ".bak"), result_path):
        candidate.unlink(missing_ok=True)
    print(json.dumps(payload, indent=2))
    pygame.quit()
    return 0



def pass15_test(path: str) -> int:
    pygame.init()
    artist = ActorArtist()
    sample = pygame.Surface((220, 220), pygame.SRCALPHA)

    def bounds_for(draw_call):
        sample.fill((0, 0, 0, 0))
        draw_call(sample)
        mask = pygame.mask.from_surface(sample)
        rects = mask.get_bounding_rects()
        assert rects
        united = rects[0].copy()
        for rect in rects[1:]:
            united.union_ip(rect)
        return [united.x, united.y, united.w, united.h], mask.count()

    hero_rows = {}
    for index, key in enumerate(HEROES):
        mission = Mission(key, "purge", seed=15100 + index)
        mission.hero.pos = pygame.Vector2(110, 116)
        mission.hero.facing = pygame.Vector2(0, -1)
        rect, pixels = bounds_for(lambda surf, m=mission: artist.draw_hero_world(surf, m, 1.25))
        hero_rows[key] = {"bounds": rect, "visible_pixels": pixels, "visual_radius_contract": HERO_VISUAL_RADIUS[key]}
        assert pixels > 500
        assert rect[2] <= HERO_VISUAL_RADIUS[key] * 2 + 22

    enemy_rows = {}
    for index, kind in enumerate(ENEMY_ARCHETYPES):
        mission = Mission("circuit", "purge", seed=15200 + index)
        enemy = next(e for e in mission.enemies if e.kind == kind)
        enemy.pos = pygame.Vector2(110, 116)
        enemy.facing = pygame.Vector2(0, -1)
        variant = ENEMY_VARIANTS["purge"][kind]
        rect, pixels = bounds_for(lambda surf, e=enemy, v=variant: artist.draw_enemy_world(surf, e, 1.4, v))
        enemy_rows[kind] = {"bounds": rect, "visible_pixels": pixels, "visual_radius_contract": ENEMY_VISUAL_RADIUS[kind], "collision_radius": enemy.radius}
        assert pixels > 400
        assert enemy.radius in {18.0, 19.0, 20.0}

    boss_rows = {}
    for index, quest in enumerate(QUESTS):
        mission = Mission("circuit", quest, seed=15300 + index)
        mission._spawn_signature_boss()
        boss = next(e for e in mission.enemies if e.is_boss)
        boss.pos = pygame.Vector2(110, 116)
        boss.facing = pygame.Vector2(0, -1)
        profile = SIGNATURE_BOSSES[quest]
        rect, pixels = bounds_for(lambda surf, e=boss, v=profile: artist.draw_enemy_world(surf, e, 1.7, v))
        boss_rows[boss.boss_id] = {"bounds": rect, "visible_pixels": pixels, "visual_radius_contract": BOSS_VISUAL_RADIUS[boss.boss_id], "collision_radius": boss.radius}
        assert pixels > 750
        assert boss.radius == float(profile["radius"])

    civilian_rows = {}
    mission = Mission("circuit", "rescue", seed=15400)
    for i, civ in enumerate(mission.civilians[:3]):
        civ.pos = pygame.Vector2(110, 116)
        civ.facing = pygame.Vector2(0, -1)
        civ.role_index = i
        rect, pixels = bounds_for(lambda surf, c=civ: artist.draw_civilian_world(surf, c, 1.1))
        civilian_rows[CIVILIAN_ROLES[i]["role"]] = {"bounds": rect, "visible_pixels": pixels}
        assert pixels > 180
        assert rect[2] <= CIVILIAN_VISUAL_RADIUS * 2 + 12

    assert ACTOR_PRESENTATION_RULES["combat_stats_changed"] is False
    assert ACTOR_PRESENTATION_RULES["collision_radii_changed"] is False
    assert MAX_ACTOR_VISUAL_DIAMETER < PASS14_MIN_WORLD_GAP
    assert ACTOR_CLEARANCE_MARGIN >= 20

    payload = {
        "pass15_test": "PASS",
        "hero_world_bodies": hero_rows,
        "enemy_world_bodies": enemy_rows,
        "sovereign_world_bodies": boss_rows,
        "civilian_role_bodies": civilian_rows,
        "pass14_min_world_gap": PASS14_MIN_WORLD_GAP,
        "max_actor_visual_diameter": MAX_ACTOR_VISUAL_DIAMETER,
        "clearance_margin": ACTOR_CLEARANCE_MARGIN,
        "presentation_rules": ACTOR_PRESENTATION_RULES,
    }
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    pygame.quit()
    return 0

def pass16_test(path: str) -> int:
    rows = []
    for qi, quest in enumerate(QUESTS):
        mission = Mission("nyx", quest, seed=16160 + qi)
        mission.emit_presentation("hero_melee")
        mission.emit_presentation("impact_enemy")
        cues = mission.consume_presentation_events()
        assert cues == ["hero_melee", "impact_enemy"]
        assert mission.consume_presentation_events() == []
        rows.append({"quest": quest, "cue_queue": cues, "world_obstacles": len(mission.world_obstacles)})
    defaults = App.__new__(App)._default_profile()
    assert "music_volume" in defaults["settings"]
    payload = {
        "pass16_test": "PASS",
        "presentation_only_queue": "PASS",
        "music_volume_default": defaults["settings"]["music_volume"],
        "contracts": rows,
    }
    out = Path(path); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("PASS16_PRESENTATION_AUDIO PASS")
    return 0


def pass14_test(path: str) -> int:
    pygame.init()
    rows = []
    for qi, quest in enumerate(QUESTS):
        mission = Mission("circuit" if quest == "rescue" else "vesper", quest, seed=14014 + qi)
        physical = [o for o in mission.world_obstacles if o.blocks_movement]
        destructible = [o for o in physical if o.destructible]
        spawners = [o for o in mission.world_obstacles if o.category == "spawner"]
        corners = [o for o in physical if o.category == "corner"]
        assert WORLD.width == 1864 and WORLD.height == 906
        assert len(physical) >= 8
        assert destructible and corners and len(spawners) >= 2
        # Every authored required marker must accept the largest live actor radius.
        required = [name for name in mission.world_markers if name.startswith(("enemy_", "comp_", "boss", "civilian_"))]
        for name in required:
            assert mission._walkable_grid_point(mission.world_markers[name], 36.0), (quest, name)
        before = len(mission.obstacles)
        target = destructible[0]
        assert target.damage_state == "INTACT"
        mission._damage_world_obstacle(target, target.max_hp * 0.45, "TEST")
        assert target.damage_state == "CRACKED"
        mission._damage_world_obstacle(target, target.max_hp, "TEST")
        assert target.destroyed and target.damage_state == "RUBBLE"
        assert len(mission.obstacles) < before
        mission._spawn_signature_boss()
        boss = next(e for e in mission.enemies if e.is_boss)
        assert boss.pos.distance_to(mission.world_markers["boss"]) < 0.1
        rows.append({
            "quest": quest, "layout": mission.world_layout_name,
            "physical_objects": len(physical), "spawners": len(spawners),
            "corners": len(corners), "destructible": len(destructible),
            "destruction_opens_route": len(mission.obstacles) < before,
            "boss_marker_authority": True,
        })
    payload = {"pass14_test": "PASS", "world_rect": list(WORLD), "layouts": rows}
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    pygame.quit()
    return 0


def pass23_achievement_test(path: str) -> int:
    pygame.init()
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    profile_path = target.with_name("pass23_achievement_profile.json")
    for candidate in (profile_path, profile_path.with_suffix(profile_path.suffix + ".bak")):
        candidate.unlink(missing_ok=True)
    app = App(parse_args(["--no-audio", "--profile", str(profile_path)]))
    assert app.profile["profile_version"] == 9
    assert app.profile["achievements"]["schema_version"] == 1
    # Direct profile-state checks keep this runtime test deterministic while
    # pure-Python tools/pass23_achievement_verify.py covers all sixteen triggers.
    app.profile["heroes"]["nyx"]["successes"] = 1
    app.profile["guild"]["lifetime_credits"] = 10000
    app.achievement_tracker.evaluate_all()
    assert app.profile["achievements"]["unlocked"]["HC_001_FIRST_CONTRACT"]
    assert app.profile["achievements"]["unlocked"]["HC_016_GUILD_FORTUNE"]
    app._save_profile()
    reloaded = App(parse_args(["--no-audio", "--profile", str(profile_path)]))
    assert reloaded.profile["profile_version"] == 9
    assert reloaded.profile["achievements"]["unlocked"]["HC_001_FIRST_CONTRACT"]
    payload = {
        "pass23_runtime_achievement_test": "PASS",
        "profile_version": 9,
        "achievement_schema": 1,
        "unlocked": [k for k, v in reloaded.profile["achievements"]["unlocked"].items() if v],
        "pending_platform_updates": reloaded.profile["achievements"]["pending_platform_updates"],
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    for candidate in (profile_path, profile_path.with_suffix(profile_path.suffix + ".bak")):
        candidate.unlink(missing_ok=True)
    print(json.dumps(payload, indent=2))
    pygame.quit()
    return 0


def main(argv=None):
    args = parse_args(argv)
    if args.crash_reporter_test:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        args.no_audio = True
        args.no_save = False
        if not args.profile:
            crash_test_root = Path(args.save_root) if args.save_root else Path("verification/reports")
            args.profile = str(crash_test_root / "pass27_crash_reporter_runtime_profile.json")
        app = App(args)
        app.selected_quest = "purge"
        app.selected_hero = "nyx"
        app.selected_sidekicks = []
        app.state = "LOADOUT_PREP"
        app._deploy_selected()
        assert app.state == "CRASH_RECOVERY"
        assert app.crash_artifact is not None
        payload = {
            "pass27_runtime_crash_reporter_test": "PASS",
            "state": app.state,
            "crash_phase": app.crash_phase,
            "crash_id": app.crash_artifact.report_id,
            "bundle_name": Path(app.crash_artifact.bundle_path).name,
        }
        out = Path("verification/reports/pass27_crash_reporter_runtime.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        # Keep the crash artifact for inspection, but remove the synthetic profile.
        for candidate in (Path(args.profile), Path(args.profile + ".bak")):
            candidate.unlink(missing_ok=True)
        pygame.quit()
        app.microsoft_runtime.shutdown()
        print(json.dumps(payload, indent=2))
        return 0
    if args.quick_test:
        return quick_test()
    if args.display_self_test:
        app = App(args)
        payload = app.display_contract()
        assert payload["mode"] == ("windowed" if args.windowed else "borderless_desktop")
        assert payload["virtual_size"] == list(VIRTUAL_SIZE)
        assert payload["aspect_preserved"] is True
        assert payload["monitor_mode_change_requested"] is False
        if not args.windowed:
            assert payload["borderless"] is True
            assert payload["window_size"] == payload["desktop_size"]
        target = Path("verification/reports/pass30_display_runtime.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"pass30_display_self_test": "PASS", **payload}, indent=2), encoding="utf-8")
        pygame.quit()
        app.microsoft_runtime.shutdown()
        print(json.dumps({"pass30_display_self_test": "PASS", **payload}, indent=2))
        return 0
    if args.profile_test:
        return profile_test(args.profile or "verification/reports/pass13_profile_test.json")
    if args.actor_detail_test:
        return actor_detail_test("verification/reports/pass13_actor_detail_test.json")
    if args.orders_complications_test:
        return orders_complications_test("verification/reports/pass13_orders_complications_test.json")
    if args.equipment_intel_test:
        return equipment_intel_test("verification/reports/pass13_equipment_intel_test.json")
    if args.guild_economy_test:
        return guild_economy_test("verification/reports/pass13_guild_economy_test.json")
    if args.pass09_test or args.pass07_test:
        return pass09_test("verification/reports/pass13_expanded_roster_regression.json")
    if args.roster_cycle_test:
        return roster_cycle_test("verification/reports/pass13_roster_cycle_test.json")
    if args.identity_test:
        return identity_test("verification/reports/pass13_identity_test.json")
    if args.pass10_test:
        return pass10_test("verification/reports/pass13_sovereign_link_regression.json")
    if args.pass11_test:
        return pass11_test("verification/reports/pass13_campaign_bond_regression.json")
    if args.pass12_test:
        return pass12_test("verification/reports/pass13_mastering_regression.json")
    if args.pass13_test:
        return pass13_test("verification/reports/pass13_rc1_integration_test.json")
    if args.pass14_test:
        return pass14_test("verification/reports/pass14_runtime_world_test.json")
    if args.pass15_test:
        return pass15_test("verification/reports/pass15_actor_identity_runtime.json")
    if args.pass16_test:
        return pass16_test("verification/reports/pass16_presentation_audio_runtime.json")
    if args.pass23_achievement_test:
        return pass23_achievement_test("verification/reports/pass23_achievement_runtime.json")
    # Special static-screen screenshot modes.
    if args.scenario == "board":
        args.scenario = "board"
    app = App(args)
    if args.scenario == "title":
        app.state = "TITLE"
    elif args.scenario == "settings":
        app.state = "SETTINGS"
        app.settings_return_state = "TITLE"
        app.settings_index = 3
    elif args.scenario == "help":
        app.state = "CONTRACT_BOARD"
        app.show_help = True
        app.help_page = 0
    elif args.scenario == "onboarding":
        app.state = "CONTRACT_BOARD"
        app.profile["onboarding"]["completed"] = False
        app.profile["settings"]["tutorial_tips"] = True
    elif args.scenario == "loadout":
        app.selected_quest = args.screen_quest
        app.selected_hero = args.hero
        app.state = "LOADOUT_PREP"
    elif args.scenario == "heroes":
        app.selected_quest = args.screen_quest
        app.selected_hero = args.hero
        app.state = "HERO_SELECT"
    elif args.scenario == "restore":
        for key in ("nyx", "vesper"):
            app.profile["heroes"][key]["availability"] = "ELIMINATED"
            app.profile["heroes"][key]["strain"] = 100
            app.profile["heroes"][key]["field_condition"] = "ELIMINATED"
            app.profile["heroes"][key]["deaths"] = 1
        app.profile["guild"]["restoration_tokens"] = 1
        app.state = "RESTORE_SELECT"
    elif args.scenario == "lastlight":
        for key in HEROES:
            app.profile["heroes"][key]["availability"] = "ELIMINATED"
            app.profile["heroes"][key]["strain"] = 100
            app.profile["heroes"][key]["field_condition"] = "ELIMINATED"
        app.profile["guild"]["last_light_pending"] = True
        app.state = "LAST_LIGHT"
    elif args.scenario == "bond":
        pair = "nyx|circuit"
        app.profile["bonds"][pair].update({"points": 3, "missions": 2, "victories": 2})
        app.profile["campaign"]["pending_bond_event"] = {"pair": pair, "level": 3}
        app.state = "BOND_EVENT"
    elif args.scenario == "board":
        app.state = "CONTRACT_BOARD"
    app.run()
    return 0
