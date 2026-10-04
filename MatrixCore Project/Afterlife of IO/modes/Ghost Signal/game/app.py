from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import pygame

from audio.audio_manager import AudioManager
from game.building_stage import BuildingStageState
from game.city_map import BuildingStatus, CityMapModel, VIEW_RECT
from game.progression import (
    apply_profile_to_city,
    gleebs_response,
    memory_records,
    recover_building_memory,
)
from game.results import result_dir, write_result_packets
from game.save_profile import ProfileState, load_profile, save_profile
from game.version import BUILD_LABEL, PASS_ID, VERSION, WINDOW_CAPTION
from game.states import GameState
from rendering.city_renderer import CityRenderer, VIRTUAL_SIZE
from rendering.stage_renderer import StageRenderer
from ui.settings import (
    DEFAULT_SETTINGS,
    SETTING_ROWS,
    SETTINGS_CLOSE_RECT,
    SETTINGS_RESET_RECT,
    adjust_setting,
    normalize_settings,
    reset_settings,
    settings_hit_test,
    settings_row_rect,
)


AUDIO_CAPTIONS = {
    "camera_switch": "CAMERA FEED SWITCHED",
    "hack_clean": "CLEAN ACCESS CONFIRMED",
    "hack_noisy": "TRACE SPIKE — NOISY ACCESS",
    "hack_rejected": "ACCESS REJECTED",
    "gleebs_alarm": "GLEEBS RESISTANCE ALARM",
    "building_capture": "BUILDING CORE CAPTURED",
    "district_complete": "DISTRICT NETWORK SYNCHRONIZED",
    "memory_restore": "MEMORY FRAGMENT RESTORED",
    "lockout_start": "RESISTANCE LOCKOUT STARTED",
}


@dataclass(frozen=True)
class AppConfig:
    no_audio: bool = False
    quick_test: bool = False
    scenario: str = "title"
    test_shot: Path | None = None
    max_frames: int | None = None
    fullscreen: bool = False
    window_size: tuple[int, int] = VIRTUAL_SIZE
    auto_confirm: bool = False
    # Afterlife of IO hosts Ghost Signal in its own live window.
    inherit_display: bool = False


class GhostSignalApp:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_caption(WINDOW_CAPTION)
        self.windowed_size = config.window_size
        self.fullscreen = config.fullscreen
        inherited = pygame.display.get_surface() if config.inherit_display else None
        self.hosted = inherited is not None
        if self.hosted:
            self.screen = inherited
            CityRenderer.disconnect_label = "DISCONNECT — BACK TO AFTERLIFE"
            self.fullscreen = bool(inherited.get_flags() & pygame.FULLSCREEN)
            if not self.fullscreen:
                self.windowed_size = tuple(inherited.get_size())
        else:
            self.screen = self._create_display()
        self.virtual = pygame.Surface(VIRTUAL_SIZE).convert()
        self.clock = pygame.time.Clock()
        self.profile = load_profile()
        self.profile.settings = normalize_settings(self.profile.settings)
        if not self.hosted:
            # The host's window choice must not overwrite Ghost Signal's own.
            self.profile.settings["fullscreen"] = self.fullscreen
            self.profile.settings["window_size"] = list(self.windowed_size)
        self.audio = AudioManager(config.no_audio)
        self.audio.apply_settings(self.profile.settings)
        text_scale = float(self.profile.settings["text_scale"])
        self.renderer = CityRenderer(text_scale)
        self.stage_renderer = StageRenderer(text_scale)
        self.city = CityMapModel()
        apply_profile_to_city(self.profile, self.city)
        self.pending_industrial_finale = (
            self.profile.profile_version < 4
            and "industrial_grid" in self.profile.districts_completed
        )
        if "industrial_grid" in self.profile.districts_completed:
            self.city.zoom = 0.82
            self.city.camera.update(1720, 940)
            self.city._clamp_camera()
        self.stage = BuildingStageState()
        self.state = GameState.TITLE
        self.previous_state = self.state
        self.show_help = False
        self.show_memory_archive = False
        self.show_settings = False
        self.settings_index = 0
        self.running = True
        self.ejection_elapsed = 0.0
        self.city_message = ""
        self._city_message_seen = ""
        self._city_message_age = 0.0
        if self.profile.recovery_notice:
            self.city_message = self.profile.recovery_notice
            self._city_message_seen = self.city_message
        self.last_memory_unlocked = ""
        self.elapsed = 0.0
        self.frame_count = 0
        self.start_time = time.perf_counter()
        self.frame_times: list[float] = []
        self._last_lockout_snapshot = dict(self.profile.building_lockouts)
        self._last_audio_state = ""
        self._district_audio_played = False
        self.audio_caption = ""
        self._audio_caption_age = 0.0
        self._audio_caption_duration = 2.6
        self.district_complete_page = 0
        self._apply_scenario(config.scenario)
        self._sync_audio(force=True)

    def _set_city_message(self, message: str) -> None:
        self.city_message = message
        self._city_message_seen = message
        self._city_message_age = 0.0

    def _advance_onboarding(self, step: int, complete: bool = False) -> None:
        if self.profile.onboarding_complete:
            return
        self.profile.onboarding_step = max(self.profile.onboarding_step, step)
        if complete:
            self.profile.onboarding_step = 5
            self.profile.onboarding_complete = True
            if self.state == GameState.BUILDING_STAGE:
                self.stage.message = "SIGNAL GUIDE COMPLETE — FOLLOW EVIDENCE • F1 REOPENS CONTROLS"
            else:
                self._set_city_message("SIGNAL GUIDE COMPLETE • F1 REOPENS CONTROLS AT ANY TIME")
        self._save_profile()

    def _save_profile(self) -> None:
        if not self.hosted:
            self.profile.settings["fullscreen"] = bool(self.fullscreen)
            self.profile.settings["window_size"] = [int(v) for v in self.windowed_size]
        self.profile.settings["muted"] = bool(self.audio.muted)
        save_profile(self.profile)

    def _apply_render_settings(self) -> None:
        scale = float(self.profile.settings.get("text_scale", 1.0))
        self.renderer.set_text_scale(scale)
        self.stage_renderer.set_text_scale(scale)
        self.audio.apply_settings(self.profile.settings)

    def _play_cue(self, cue: str) -> None:
        self.audio.play(cue)
        caption = AUDIO_CAPTIONS.get(cue, "")
        if caption and bool(self.profile.settings.get("audio_captions", True)):
            self.audio_caption = caption
            self._audio_caption_age = 0.0

    def _settings_changed(self) -> None:
        self.profile.settings = normalize_settings(self.profile.settings)
        self._apply_render_settings()
        self._play_cue("ui_select")
        self._save_profile()

    def _toggle_mute(self) -> None:
        muted = self.audio.toggle_mute()
        self.profile.settings["muted"] = muted
        self.city_message = "ALL AUDIO MUTED" if muted else "AUDIO RESTORED"
        self._save_profile()

    def _sync_audio(self, force: bool = False) -> None:
        if self.state == GameState.PAUSED or self.show_settings or self.show_help or self.show_memory_archive:
            self.audio.pause()
            return
        self.audio.resume()
        if self.state == GameState.TITLE:
            scene, machine = "title", ""
        elif self.state in (GameState.BUILDING_STAGE, GameState.GLEEBS_EJECTION):
            scene = "ejection" if self.state == GameState.GLEEBS_EJECTION else "stage"
            machine = "drone_loop" if (
                (self.stage.building_id == "maintenance_depot" and self.stage.drone_unlocked and self.stage.camera.name == "DRONE")
                or self.stage.building_id == "drone_assembly_facility"
            ) else ""
        else:
            scene, machine = "city", ""
        marker = f"{scene}:{machine}"
        if force or marker != self._last_audio_state:
            self.audio.set_scene(scene, machine)
            self._last_audio_state = marker

    def _seed_complete_profile(self) -> None:
        preserved_settings = normalize_settings(getattr(self.profile, "settings", {}))
        self.profile = ProfileState()
        self.profile.settings = preserved_settings
        self.profile.onboarding_step = 5
        self.profile.onboarding_complete = True
        self.profile.captured_buildings.update(
            {"surveillance_annex", "maintenance_depot", "transit_substation"}
        )
        self.profile.unlocked_buildings.update(self.profile.captured_buildings)
        self.profile.unlocked_buildings.add("corporate_mall")
        self.profile.districts_completed.add("municipal_fringe")
        self.profile.memory_fragments[:] = [
            "andrew_awakening",
            "gleebs_continuity",
            "the_kept_route",
        ]
        self.profile.statistics.update(
            {
                "total_hacks": 11,
                "clean_hacks": 9,
                "noisy_hacks": 1,
                "rejected_hacks": 0,
                "gleebs_alarms": 1,
                "civilian_system_violations": 1,
                "building_captures": 3,
                "maximum_trace": 58,
            }
        )
        self.profile.method_usage.update(
            {"maintenance_bypass": 6, "credential_spoof": 3, "signal_replay": 2}
        )
        apply_profile_to_city(self.profile, self.city)

    def _seed_commercial_profile(self) -> None:
        self._seed_complete_profile()
        self.profile.capture_building("corporate_mall")
        recover_building_memory(self.profile, "corporate_mall")
        self.profile.statistics["clean_hacks"] = max(13, int(self.profile.statistics.get("clean_hacks", 0)))
        apply_profile_to_city(self.profile, self.city)

    def _seed_financial_profile(self) -> None:
        self._seed_commercial_profile()
        self.profile.capture_building("media_broadcast")
        recover_building_memory(self.profile, "media_broadcast")
        self.profile.statistics["clean_hacks"] = max(17, int(self.profile.statistics.get("clean_hacks", 0)))
        apply_profile_to_city(self.profile, self.city)

    def _seed_clinic_profile(self) -> None:
        self._seed_financial_profile()
        self.profile.capture_building("financial_exchange")
        recover_building_memory(self.profile, "financial_exchange")
        self.profile.statistics["clean_hacks"] = max(21, int(self.profile.statistics.get("clean_hacks", 0)))
        apply_profile_to_city(self.profile, self.city)

    def _seed_industrial_profile(self) -> None:
        self._seed_clinic_profile()
        self.profile.capture_building("private_clinic")
        recover_building_memory(self.profile, "private_clinic")
        self.profile.districts_completed.add("commercial_spine")
        self.profile.unlocked_buildings.add("automated_factory")
        self.profile.statistics["clean_hacks"] = max(25, int(self.profile.statistics.get("clean_hacks", 0)))
        apply_profile_to_city(self.profile, self.city)

    def _seed_power_profile(self) -> None:
        self._seed_industrial_profile()
        self.profile.capture_building("automated_factory")
        recover_building_memory(self.profile, "automated_factory")
        self.profile.unlocked_buildings.add("power_distribution_plant")
        self.profile.statistics["clean_hacks"] = max(29, int(self.profile.statistics.get("clean_hacks", 0)))
        apply_profile_to_city(self.profile, self.city)

    def _seed_drone_profile(self) -> None:
        self._seed_power_profile()
        self.profile.capture_building("power_distribution_plant")
        recover_building_memory(self.profile, "power_distribution_plant")
        self.profile.unlocked_buildings.add("drone_assembly_facility")
        self.profile.statistics["clean_hacks"] = max(33, int(self.profile.statistics.get("clean_hacks", 0)))
        apply_profile_to_city(self.profile, self.city)

    def _seed_waste_profile(self) -> None:
        self._seed_drone_profile()
        self.profile.capture_building("drone_assembly_facility")
        recover_building_memory(self.profile, "drone_assembly_facility")
        self.profile.unlocked_buildings.add("waste_processing_complex")
        self.profile.statistics["clean_hacks"] = max(37, int(self.profile.statistics.get("clean_hacks", 0)))
        apply_profile_to_city(self.profile, self.city)

    def _seed_industrial_complete_profile(self) -> None:
        self._seed_waste_profile()
        self.profile.capture_building("waste_processing_complex")
        recover_building_memory(self.profile, "waste_processing_complex")
        self.profile.districts_completed.add("industrial_grid")
        self.profile.statistics["clean_hacks"] = max(41, int(self.profile.statistics.get("clean_hacks", 0)))
        apply_profile_to_city(self.profile, self.city)

    def _set_prior_captures(self, through: str) -> None:
        if through in ("depot", "transit", "mall", "media", "financial", "clinic", "factory", "power", "drone", "waste"):
            self.city.set_status("surveillance_annex", BuildingStatus.CAPTURED)
        if through in ("transit", "mall", "media", "financial", "clinic", "factory", "power", "drone", "waste"):
            self.city.set_status("maintenance_depot", BuildingStatus.CAPTURED)
        if through in ("mall", "media", "financial", "clinic", "factory", "power", "drone", "waste"):
            self.city.set_status("transit_substation", BuildingStatus.CAPTURED)
            self.city.set_status("corporate_mall", BuildingStatus.VULNERABLE if through == "mall" else BuildingStatus.CAPTURED)
        if through in ("media", "financial", "clinic", "factory", "power", "drone", "waste"):
            self.city.set_status("media_broadcast", BuildingStatus.VULNERABLE if through == "media" else BuildingStatus.CAPTURED)
        if through in ("financial", "clinic", "factory", "power", "drone", "waste"):
            self.city.set_status("financial_exchange", BuildingStatus.VULNERABLE if through == "financial" else BuildingStatus.CAPTURED)
        if through in ("clinic", "factory", "power", "drone", "waste"):
            self.city.set_status("private_clinic", BuildingStatus.VULNERABLE if through == "clinic" else BuildingStatus.CAPTURED)
        if through in ("factory", "power", "drone", "waste"):
            self.city.set_status("automated_factory", BuildingStatus.VULNERABLE if through == "factory" else BuildingStatus.CAPTURED)
        if through in ("power", "drone", "waste"):
            self.city.set_status("power_distribution_plant", BuildingStatus.VULNERABLE if through == "power" else BuildingStatus.CAPTURED)
        if through in ("drone", "waste"):
            self.city.set_status("drone_assembly_facility", BuildingStatus.VULNERABLE if through == "drone" else BuildingStatus.CAPTURED)
        if through == "waste":
            self.city.set_status("waste_processing_complex", BuildingStatus.VULNERABLE)

    def _apply_scenario(self, name: str) -> None:
        if name == "onboarding_city":
            self.profile = ProfileState()
            self.profile.settings = normalize_settings(self.profile.settings)
            self.profile.onboarding_step = 1
            self.profile.onboarding_complete = False
            apply_profile_to_city(self.profile, self.city)
            self.state = GameState.CITY_MAP
            self.city.selected_building_id = "surveillance_annex"
            return
        if name in ("onboarding_stage", "onboarding_method"):
            self.profile = ProfileState()
            self.profile.settings = normalize_settings(self.profile.settings)
            self.profile.onboarding_step = 2 if name == "onboarding_stage" else 3
            self.profile.onboarding_complete = False
            apply_profile_to_city(self.profile, self.city)
            self.stage = BuildingStageState("surveillance_annex")
            if name == "onboarding_method":
                self.stage.select_method_key(5)
            self.state = GameState.BUILDING_STAGE
            return
        if name == "continue_title":
            self._seed_industrial_profile()
            self.profile.onboarding_step = 5
            self.profile.onboarding_complete = True
            self.state = GameState.TITLE
            return
        if name in ("settings", "accessibility_city"):
            self._seed_complete_profile()
            self.state = GameState.CITY_MAP
            self.city.selected_building_id = "transit_substation"
            if name == "accessibility_city":
                self.profile.settings.update(
                    reduced_motion=True,
                    reduced_glitch=True,
                    reduced_flashing=True,
                    high_contrast=True,
                    state_symbols=True,
                    audio_captions=True,
                    edge_pan=False,
                    text_scale=1.15,
                )
                self._apply_render_settings()
                self.city_message = "ACCESSIBILITY PROFILE ACTIVE"
            else:
                self.show_settings = True
            return
        if name == "audio_caption":
            self._seed_complete_profile()
            self.state = GameState.CITY_MAP
            self.city.selected_building_id = "transit_substation"
            self.audio_caption = "BUILDING CORE CAPTURED"
            self._audio_caption_age = 0.0
            return
        if name == "pause":
            self._seed_complete_profile()
            self.city.selected_building_id = "transit_substation"
            self.previous_state = GameState.CITY_MAP
            self.state = GameState.PAUSED
            return
        if name == "help":
            self._seed_complete_profile()
            self.city.selected_building_id = "transit_substation"
            self.state = GameState.CITY_MAP
            self.show_help = True
            return
        if name == "stage_polish":
            self._set_prior_captures("transit")
            self.city.set_status("transit_substation", BuildingStatus.VULNERABLE)
            self.stage = BuildingStageState("transit_substation")
            self.stage.platform_secured = True
            self.stage.service_window_open = True
            self.stage.select_camera(3)
            self.state = GameState.BUILDING_STAGE
            return
        if name == "gleebs_reduced":
            self.profile.settings["reduced_glitch"] = True
            self.profile.settings["reduced_flashing"] = True
            self._apply_render_settings()
            self.stage = BuildingStageState("transit_substation")
            self.stage.platform_secured = True
            self.stage.service_window_open = True
            self.stage.select_camera(3)
            self.stage.selected_method_id = "brute_force"
            self.stage.interact()
            self.state = GameState.GLEEBS_EJECTION
            return
        if name == "title":
            self.state = GameState.TITLE
            return
        if name == "profile_city":
            self._seed_complete_profile()
            self.state = GameState.CITY_MAP
            self.city.selected_building_id = "transit_substation"
            self.city_message = "PROFILE RESTORED • MUNICIPAL FRINGE CONTROL 100%"
            return
        if name == "memory_archive":
            self._seed_waste_profile()
            self.profile.capture_building("waste_processing_complex")
            recover_building_memory(self.profile, "waste_processing_complex")
            self.profile.districts_completed.add("industrial_grid_reclamation_ready")
            apply_profile_to_city(self.profile, self.city)
            self.state = GameState.CITY_MAP
            self.city.selected_building_id = "waste_processing_complex"
            self.show_memory_archive = True
            self.city_message = "ELEVEN MEMORY FRAGMENTS RESTORED"
            return
        if name == "profile_relaunch":
            self.state = GameState.CITY_MAP
            self.city_message = "PERSISTENT PROFILE RESTORED"
            return
        if name == "gleebs_memory":
            self.profile.method_usage["brute_force"] = 3
            self.profile.statistics["civilian_system_violations"] = 2
            self.profile.gleebs_detection_history["transit_substation"] = [
                {"method": "brute_force", "cause": "OCCUPIED TRANSIT ROUTE", "timestamp": 1.0}
            ]
            self.stage = BuildingStageState("transit_substation")
            self.stage.selected_method_id = "power_cycle"
            self.stage.interact()
            self.stage.gleebs_message = gleebs_response(
                self.profile, self.stage.building_id, self.stage.detection_cause
            )
            self.state = GameState.GLEEBS_EJECTION
            return
        if name in ("city_map", "city_after_depot", "district_takeover"):
            self.state = GameState.CITY_MAP
            if name in ("city_after_depot", "district_takeover"):
                self._set_prior_captures("transit")
                self.city.set_status(
                    "transit_substation",
                    BuildingStatus.VULNERABLE if name == "city_after_depot" else BuildingStatus.CAPTURED,
                )
                self.city.selected_building_id = "transit_substation"
            if name == "district_takeover":
                self._seed_complete_profile()
                self.state = GameState.DISTRICT_COMPLETE
                self.city_message = "MUNICIPAL FRINGE CONTROLLED • DISTANT COMMERCIAL SPINE DETECTED"
            return

        if name == "commercial_spine_city":
            self._seed_complete_profile()
            self.state = GameState.CITY_MAP
            self.city.selected_building_id = "corporate_mall"
            self.city.zoom = 0.82
            self.city.camera.update(1700, 420)
            self.city._clamp_camera()
            self.city_message = "COMMERCIAL SPINE ONLINE • CORPORATE MALL BREACH AVAILABLE"
            return
        if name.startswith("mall_"):
            self._seed_complete_profile()
            self._set_prior_captures("mall")
            self.city.selected_building_id = "corporate_mall"
            self.city.zoom = 0.82
            self.city.camera.update(1700, 420)
            self.city._clamp_camera()
            self.stage = BuildingStageState("corporate_mall")
            self.state = GameState.BUILDING_STAGE
            if name in ("mall_ad_grid", "mall_identity", "mall_core", "mall_captured", "mall_gleebs"):
                self.stage.atrium_access = True
            if name in ("mall_identity", "mall_core", "mall_captured", "mall_gleebs"):
                self.stage.ads_rerouted = True
            if name in ("mall_core", "mall_captured"):
                self.stage.identity_copied = True
                self.stage.mall_core_exposed = True
            if name == "mall_ad_grid":
                self.stage.select_camera(2)
            elif name == "mall_identity":
                self.stage.select_camera(3)
            elif name in ("mall_core", "mall_captured"):
                self.stage.select_camera(4)
                if name == "mall_captured":
                    self.stage.selected_method_id = "power_cycle"
                    self.stage.interact()
            elif name == "mall_gleebs":
                self.stage.select_camera(3)
                self.stage.selected_method_id = "brute_force"
                self.stage.interact()
                self.stage.gleebs_message = gleebs_response(
                    self.profile, self.stage.building_id, self.stage.detection_cause
                )
                self.state = GameState.GLEEBS_EJECTION
            return

        if name == "financial_unlocked":
            self._seed_commercial_profile()
            self.profile.capture_building("media_broadcast")
            recover_building_memory(self.profile, "media_broadcast")
            apply_profile_to_city(self.profile, self.city)
            self.city.selected_building_id = "financial_exchange"
            self.city.zoom = 0.82
            self.city.camera.update(2110, 420)
            self.city._clamp_camera()
            self.state = GameState.CITY_MAP
            self.city_message = "PUBLIC COMMUNICATION ACCESS UNLOCKED • FINANCIAL EXCHANGE VULNERABLE"
            return
        if name == "media_city":
            self._seed_commercial_profile()
            self.city.selected_building_id = "media_broadcast"
            self.city.zoom = 0.82
            self.city.camera.update(1850, 420)
            self.city._clamp_camera()
            self.state = GameState.CITY_MAP
            self.city_message = "MEDIA BROADCAST BREACH AVAILABLE • PUBLIC SIGNAL AUTHORITY EXPOSED"
            return
        if name.startswith("media_"):
            self._seed_commercial_profile()
            self._set_prior_captures("media")
            self.city.selected_building_id = "media_broadcast"
            self.city.zoom = 0.82
            self.city.camera.update(1850, 420)
            self.city._clamp_camera()
            self.stage = BuildingStageState("media_broadcast")
            self.state = GameState.BUILDING_STAGE
            if name in ("media_alert_router", "media_studio", "media_core", "media_captured", "media_gleebs"):
                self.stage.feed_looped = True
            if name in ("media_studio", "media_core", "media_captured"):
                self.stage.alert_routed = True
            if name in ("media_core", "media_captured"):
                self.stage.studio_identity = True
                self.stage.broadcast_core_exposed = True
            if name == "media_alert_router":
                self.stage.select_camera(2)
            elif name == "media_studio":
                self.stage.select_camera(3)
            elif name in ("media_core", "media_captured"):
                self.stage.select_camera(4)
                if name == "media_captured":
                    self.stage.selected_method_id = "power_cycle"
                    self.stage.interact()
            elif name == "media_gleebs":
                self.stage.select_camera(2)
                self.stage.selected_method_id = "brute_force"
                self.stage.interact()
                self.stage.gleebs_message = gleebs_response(
                    self.profile, self.stage.building_id, self.stage.detection_cause
                )
                self.state = GameState.GLEEBS_EJECTION
            return


        if name in ("clinic_unlocked", "clinic_city", "commercial_takeover"):
            self._seed_clinic_profile()
            self.city.selected_building_id = "private_clinic"
            self.city.zoom = 0.82
            self.city.camera.update(2380, 420)
            self.city._clamp_camera()
            self.state = GameState.CITY_MAP
            if name == "commercial_takeover":
                self.profile.capture_building("private_clinic")
                recover_building_memory(self.profile, "private_clinic")
                apply_profile_to_city(self.profile, self.city)
                self.state = GameState.DISTRICT_COMPLETE
                self.city_message = "COMMERCIAL SPINE CONTROLLED • INDUSTRIAL GRID DETECTED"
            else:
                self.city_message = "FINANCIAL AUTHORITY CAPTURED • PRIVATE CLINIC VULNERABLE"
            return
        if name.startswith("clinic_"):
            self._seed_clinic_profile()
            self._set_prior_captures("clinic")
            self.city.selected_building_id = "private_clinic"
            self.city.zoom = 0.82
            self.city.camera.update(2380, 420)
            self.city._clamp_camera()
            self.stage = BuildingStageState("private_clinic")
            self.state = GameState.BUILDING_STAGE
            if name in ("clinic_identity", "clinic_life_support", "clinic_archive", "clinic_captured", "clinic_gleebs"):
                self.stage.triage_routed = True
            if name in ("clinic_life_support", "clinic_archive", "clinic_captured", "clinic_gleebs"):
                self.stage.medical_identity_rebuilt = True
            if name in ("clinic_archive", "clinic_captured"):
                self.stage.life_support_safe = True
                self.stage.biological_archive_exposed = True
            if name == "clinic_triage":
                self.stage.selected_method_id = "signal_replay"
            elif name == "clinic_identity":
                self.stage.select_camera(2)
                self.stage.selected_method_id = "credential_spoof"
            elif name == "clinic_life_support":
                self.stage.select_camera(3)
                self.stage.selected_method_id = "maintenance_bypass"
            elif name in ("clinic_archive", "clinic_captured"):
                self.stage.select_camera(4)
                self.stage.selected_method_id = "power_cycle"
                if name == "clinic_captured":
                    self.stage.interact()
            elif name == "clinic_gleebs":
                self.stage.select_camera(3)
                self.stage.selected_method_id = "brute_force"
                self.stage.interact()
                self.stage.gleebs_message = gleebs_response(self.profile, self.stage.building_id, self.stage.detection_cause)
                self.state = GameState.GLEEBS_EJECTION
            return
        if name == "financial_city":
            self._seed_financial_profile()
            self.city.selected_building_id = "financial_exchange"
            self.city.zoom = 0.82
            self.city.camera.update(2110, 420)
            self.city._clamp_camera()
            self.state = GameState.CITY_MAP
            self.city_message = "FINANCIAL EXCHANGE BREACH AVAILABLE • CLEARING AUTHORITY EXPOSED"
            return
        if name.startswith("financial_"):
            self._seed_financial_profile()
            self._set_prior_captures("financial")
            self.city.selected_building_id = "financial_exchange"
            self.city.zoom = 0.82
            self.city.camera.update(2110, 420)
            self.city._clamp_camera()
            self.stage = BuildingStageState("financial_exchange")
            self.state = GameState.BUILDING_STAGE
            if name == "financial_floor":
                self.stage.selected_method_id = "signal_replay"
            elif name == "financial_credentials":
                self.stage.selected_method_id = "credential_spoof"
            elif name == "financial_audit":
                self.stage.selected_method_id = "maintenance_bypass"
            elif name in ("financial_core", "financial_captured"):
                self.stage.selected_method_id = "power_cycle"
            if name in ("financial_credentials", "financial_audit", "financial_core", "financial_captured", "financial_gleebs"):
                self.stage.settlement_traced = True
            if name in ("financial_audit", "financial_core", "financial_captured", "financial_gleebs"):
                self.stage.credential_chain_rebuilt = True
            if name in ("financial_core", "financial_captured"):
                self.stage.audit_vault_open = True
                self.stage.clearing_core_exposed = True
            if name == "financial_credentials":
                self.stage.select_camera(2)
            elif name == "financial_audit":
                self.stage.select_camera(3)
            elif name in ("financial_core", "financial_captured"):
                self.stage.select_camera(4)
                if name == "financial_captured":
                    self.stage.selected_method_id = "power_cycle"
                    self.stage.interact()
            elif name == "financial_gleebs":
                self.stage.select_camera(3)
                self.stage.selected_method_id = "brute_force"
                self.stage.interact()
                self.stage.gleebs_message = gleebs_response(
                    self.profile, self.stage.building_id, self.stage.detection_cause
                )
                self.state = GameState.GLEEBS_EJECTION
            return

        if name == "industrial_grid_city":
            self._seed_industrial_profile()
            self.city.selected_building_id = "automated_factory"
            self.city.zoom = 0.82
            self.city.camera.update(1200, 1040)
            self.city._clamp_camera()
            self.state = GameState.CITY_MAP
            self.city_message = "INDUSTRIAL GRID DETECTED • AUTOMATED FACTORY BREACH AVAILABLE"
            return
        if name.startswith("factory_"):
            self._seed_industrial_profile()
            self._set_prior_captures("factory")
            self.city.selected_building_id = "automated_factory"
            self.city.zoom = 0.82
            self.city.camera.update(1200, 1040)
            self.city._clamp_camera()
            self.stage = BuildingStageState("automated_factory")
            self.state = GameState.BUILDING_STAGE
            if name in ("factory_line", "factory_safety", "factory_core", "factory_captured", "factory_gleebs"):
                self.stage.intake_manifest_replayed = True
            if name in ("factory_safety", "factory_core", "factory_captured", "factory_gleebs"):
                self.stage.assembly_service_hold = True
            if name in ("factory_core", "factory_captured"):
                self.stage.safety_interlock_claimed = True
                self.stage.factory_core_exposed = True
            if name == "factory_intake":
                self.stage.selected_method_id = "signal_replay"
            elif name == "factory_line":
                self.stage.select_camera(2)
                self.stage.selected_method_id = "maintenance_bypass"
            elif name == "factory_safety":
                self.stage.select_camera(3)
                self.stage.selected_method_id = "credential_spoof"
            elif name in ("factory_core", "factory_captured"):
                self.stage.select_camera(4)
                self.stage.selected_method_id = "power_cycle"
                if name == "factory_captured":
                    self.stage.interact()
            elif name == "factory_gleebs":
                self.stage.select_camera(2)
                self.stage.selected_method_id = "power_cycle"
                self.stage.interact()
                self.stage.gleebs_message = gleebs_response(self.profile, self.stage.building_id, self.stage.detection_cause)
                self.state = GameState.GLEEBS_EJECTION
            return

        if name == "power_grid_city":
            self._seed_power_profile()
            self._set_prior_captures("power")
            self.city.selected_building_id = "power_distribution_plant"
            self.city.zoom = 0.82
            self.city.camera.update(1400, 1040)
            self.city._clamp_camera()
            self.state = GameState.CITY_MAP
            self.city_message = "FACTORY CAPTURED • POWER DISTRIBUTION PLANT BREACH AVAILABLE"
            return
        if name.startswith("power_"):
            self._seed_power_profile()
            self._set_prior_captures("power")
            self.city.selected_building_id = "power_distribution_plant"
            self.city.zoom = 0.82
            self.city.camera.update(1400, 1040)
            self.city._clamp_camera()
            self.stage = BuildingStageState("power_distribution_plant")
            self.state = GameState.BUILDING_STAGE
            if name in ("power_switchyard", "power_feeders", "power_core", "power_captured", "power_gleebs"):
                self.stage.dispatch_pattern_replayed = True
            if name in ("power_feeders", "power_core", "power_captured", "power_gleebs"):
                self.stage.switchyard_isolated = True
            if name in ("power_core", "power_captured"):
                self.stage.critical_feeders_protected = True
                self.stage.distribution_core_exposed = True
            if name == "power_dispatch":
                self.stage.selected_method_id = "signal_replay"
            elif name == "power_switchyard":
                self.stage.select_camera(2)
                self.stage.selected_method_id = "maintenance_bypass"
            elif name == "power_feeders":
                self.stage.select_camera(3)
                self.stage.selected_method_id = "credential_spoof"
            elif name in ("power_core", "power_captured"):
                self.stage.select_camera(4)
                self.stage.selected_method_id = "power_cycle"
                if name == "power_captured":
                    self.stage.interact()
            elif name == "power_gleebs":
                self.stage.select_camera(3)
                self.stage.selected_method_id = "power_cycle"
                self.stage.interact()
                self.stage.gleebs_message = gleebs_response(self.profile, self.stage.building_id, self.stage.detection_cause)
                self.state = GameState.GLEEBS_EJECTION
            return

        if name == "drone_grid_city":
            self._seed_drone_profile()
            self._set_prior_captures("drone")
            self.city.selected_building_id = "drone_assembly_facility"
            self.city.zoom = 0.82
            self.city.camera.update(1680, 1040)
            self.city._clamp_camera()
            self.state = GameState.CITY_MAP
            self.city_message = "POWER GRID STABILIZED • DRONE ASSEMBLY FACILITY BREACH AVAILABLE"
            return
        if name.startswith("drone_"):
            self._seed_drone_profile()
            self._set_prior_captures("drone")
            self.city.selected_building_id = "drone_assembly_facility"
            self.city.zoom = 0.82
            self.city.camera.update(1680, 1040)
            self.city._clamp_camera()
            self.stage = BuildingStageState("drone_assembly_facility")
            self.state = GameState.BUILDING_STAGE
            if name in ("drone_calibration", "drone_identity", "drone_core", "drone_captured", "drone_gleebs"):
                self.stage.parts_receipt_replayed = True
            if name in ("drone_identity", "drone_core", "drone_captured", "drone_gleebs"):
                self.stage.calibration_hold_engaged = True
            if name in ("drone_core", "drone_captured"):
                self.stage.rescue_identities_protected = True
                self.stage.flight_core_exposed = True
            if name == "drone_parts":
                self.stage.selected_method_id = "signal_replay"
            elif name == "drone_calibration":
                self.stage.select_camera(2)
                self.stage.selected_method_id = "maintenance_bypass"
            elif name == "drone_identity":
                self.stage.select_camera(3)
                self.stage.selected_method_id = "credential_spoof"
            elif name in ("drone_core", "drone_captured"):
                self.stage.select_camera(4)
                self.stage.selected_method_id = "power_cycle"
                if name == "drone_captured":
                    self.stage.interact()
            elif name == "drone_gleebs":
                self.stage.select_camera(3)
                self.stage.selected_method_id = "power_cycle"
                self.stage.interact()
                self.stage.gleebs_message = gleebs_response(self.profile, self.stage.building_id, self.stage.detection_cause)
                self.state = GameState.GLEEBS_EJECTION
            return


        if name == "waste_grid_city":
            self._seed_waste_profile()
            self._set_prior_captures("waste")
            self.city.selected_building_id = "waste_processing_complex"
            self.city.zoom = 0.82
            self.city.camera.update(1940, 1040)
            self.city._clamp_camera()
            self.state = GameState.CITY_MAP
            self.city_message = "DRONE AUTHORITY SECURED • WASTE PROCESSING COMPLEX BREACH AVAILABLE"
            return
        if name.startswith("waste_"):
            self._seed_waste_profile()
            self._set_prior_captures("waste")
            self.city.selected_building_id = "waste_processing_complex"
            self.city.zoom = 0.82
            self.city.camera.update(1940, 1040)
            self.city._clamp_camera()
            self.stage = BuildingStageState("waste_processing_complex")
            self.state = GameState.BUILDING_STAGE
            if name in ("waste_sorting", "waste_leachate", "waste_core", "waste_captured", "waste_gleebs"):
                self.stage.waste_manifest_replayed = True
            if name in ("waste_leachate", "waste_core", "waste_captured", "waste_gleebs"):
                self.stage.conveyor_lockout_engaged = True
            if name in ("waste_core", "waste_captured"):
                self.stage.leachate_contained = True
                self.stage.recovery_core_exposed = True
            if name == "waste_receiving":
                self.stage.selected_method_id = "signal_replay"
            elif name == "waste_sorting":
                self.stage.select_camera(2)
                self.stage.selected_method_id = "maintenance_bypass"
            elif name == "waste_leachate":
                self.stage.select_camera(3)
                self.stage.selected_method_id = "credential_spoof"
            elif name in ("waste_core", "waste_captured"):
                self.stage.select_camera(4)
                self.stage.selected_method_id = "power_cycle"
                if name == "waste_captured":
                    self.stage.interact()
            elif name == "waste_gleebs":
                self.stage.select_camera(3)
                self.stage.selected_method_id = "power_cycle"
                self.stage.interact()
                self.stage.gleebs_message = gleebs_response(self.profile, self.stage.building_id, self.stage.detection_cause)
                self.state = GameState.GLEEBS_EJECTION
            return

        if name in ("industrial_controlled_city", "industrial_takeover", "industrial_cliffhanger"):
            self._seed_industrial_complete_profile()
            self._set_prior_captures("waste")
            self.city.set_status("waste_processing_complex", BuildingStatus.CAPTURED)
            self.city.selected_building_id = "waste_processing_complex"
            self.city.zoom = 0.82
            self.city.camera.update(1720, 940)
            self.city._clamp_camera()
            if name == "industrial_controlled_city":
                self.state = GameState.CITY_MAP
                self.city_message = "INDUSTRIAL GRID CONTROLLED • HIGH TOWERS ENCRYPTED"
            else:
                self.state = GameState.DISTRICT_COMPLETE
                self.district_complete_page = 1 if name == "industrial_cliffhanger" else 0
                self.city_message = "INDUSTRIAL GRID CONTROLLED • CITY AUTHORITY SIGNAL DETECTED"
            return

        if name == "city_lockout":
            self.state = GameState.CITY_MAP
            self.city.start_lockout(
                "surveillance_annex", 60, "KNOWN DESTRUCTIVE SIGNATURE AGAINST MUNICIPAL ACCESS"
            )
            self.city.set_status("maintenance_depot", BuildingStatus.VULNERABLE)
            self.city.selected_building_id = "maintenance_depot"
            self.city_message = "ANNEX LOCKED • MAINTENANCE YARD REMAINS AVAILABLE"
            return

        depot = name.startswith("depot_")
        transit = name.startswith("transit_")
        building_id = (
            "transit_substation" if transit else "maintenance_depot" if depot else "surveillance_annex"
        )
        self.stage = BuildingStageState(building_id)
        self.stage.discovered_clues.update(self.profile.discovered_clues.get(building_id, set()))
        self.state = GameState.BUILDING_STAGE

        if depot:
            self._set_prior_captures("depot")
            self.city.set_status("maintenance_depot", BuildingStatus.VULNERABLE)
            if name in (
                "depot_repair",
                "depot_drone",
                "depot_docked",
                "depot_core",
                "depot_captured",
                "depot_gleebs",
            ):
                self.stage.door_open = True
            if name in ("depot_drone", "depot_docked", "depot_core", "depot_captured", "depot_gleebs"):
                self.stage.drone_unlocked = True
            if name == "depot_repair":
                self.stage.select_camera(2)
            elif name in ("depot_drone", "depot_docked"):
                self.stage.select_camera(3)
                if name == "depot_docked":
                    self.stage.drone_pos.update(1000, 380)
                    self.stage.drone_docked = True
            elif name in ("depot_core", "depot_captured", "depot_gleebs"):
                self.stage.drone_pos.update(1000, 380)
                self.stage.drone_docked = True
                self.stage.bridge_connected = True
                self.stage.select_camera(4)
                if name == "depot_captured":
                    self.stage.selected_method_id = "maintenance_bypass"
                    self.stage.interact()
                elif name == "depot_gleebs":
                    self.stage.selected_method_id = "brute_force"
                    self.stage.interact()
        elif transit:
            self._set_prior_captures("transit")
            self.city.set_status("transit_substation", BuildingStatus.VULNERABLE)
            if name in ("transit_service", "transit_core", "transit_uplink", "transit_captured", "transit_gleebs"):
                self.stage.platform_secured = True
            if name in ("transit_core", "transit_uplink", "transit_captured", "transit_gleebs"):
                self.stage.service_window_open = True
            if name in ("transit_uplink", "transit_captured"):
                self.stage.routing_safe = True
                self.stage.uplink_exposed = True
            if name == "transit_service":
                self.stage.select_camera(2)
            elif name == "transit_core":
                self.stage.select_camera(3)
            elif name in ("transit_uplink", "transit_captured"):
                self.stage.select_camera(4)
                if name == "transit_captured":
                    self.stage.selected_method_id = "credential_spoof"
                    self.stage.interact()
            elif name == "transit_gleebs":
                self.stage.select_camera(3)
                self.stage.selected_method_id = "brute_force"
                self.stage.interact()
        else:
            if name in ("annex_operations", "annex_core", "annex_captured", "annex_trace_failure"):
                self.stage.door_open = True
            if name in ("annex_core", "annex_captured"):
                self.stage.lights_rerouted = True
                self.stage.core_exposed = True
            if name == "annex_operations":
                self.stage.select_camera(2)
            elif name in ("annex_core", "annex_captured"):
                self.stage.select_camera(3)
            if name == "annex_captured":
                self.stage.selected_method_id = "credential_spoof"
                self.stage.interact()
            if name == "annex_noisy":
                self.stage.selected_method_id = "credential_spoof"
                self.stage.interact()
            if name == "annex_rejected":
                self.stage.selected_method_id = "signal_replay"
                self.stage.interact()
            if name == "annex_trace_failure":
                self.stage.trace = 100
                self.stage.failed = True
            if name in ("annex_gleebs_warning", "gleebs_ejection"):
                self.stage.selected_method_id = "brute_force"
                self.stage.interact()
            if name == "gleebs_ejection":
                self.state = GameState.GLEEBS_EJECTION

    def _create_display(self):
        if self.fullscreen:
            return pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF)
        return pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE | pygame.DOUBLEBUF)

    def run(self) -> int:
        try:
            while self.running:
                dt = min(0.05, self.clock.tick(60) / 1000)
                self.elapsed += dt
                if dt > 0:
                    self.frame_times.append(dt)
                self._events()
                self._update(dt)
                self._render()
                self._present()
                self.frame_count += 1
                if self.config.max_frames is not None and self.frame_count >= self.config.max_frames:
                    self.running = False
            if self.config.test_shot:
                self.config.test_shot.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(self.screen, self.config.test_shot)
            if self.config.quick_test:
                self._write_quick_result()
            return 0
        finally:
            self._save_profile()
            self.audio.shutdown()
            if not self.hosted:
                pygame.quit()

    def _events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.VIDEORESIZE and not self.fullscreen:
                self.windowed_size = (max(960, event.w), max(540, event.h))
                self.screen = pygame.display.set_mode(
                    self.windowed_size, pygame.RESIZABLE | pygame.DOUBLEBUF
                )
                continue
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    self.fullscreen = not self.fullscreen
                    self.screen = self._create_display()
                    self._play_cue("ui_confirm")
                    self._save_profile()
                    continue
                if event.key == pygame.K_m and event.mod & pygame.KMOD_SHIFT:
                    self._toggle_mute()
                    continue
                if event.key == pygame.K_F2:
                    self.show_settings = not self.show_settings
                    self.show_help = False
                    self.show_memory_archive = False
                    self._play_cue("ui_confirm")
                    continue
                if self.show_settings:
                    if event.key == pygame.K_ESCAPE:
                        self.show_settings = False
                        self._play_cue("ui_confirm")
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        self.settings_index = (self.settings_index - 1) % len(SETTING_ROWS)
                        self._play_cue("ui_select")
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.settings_index = (self.settings_index + 1) % len(SETTING_ROWS)
                        self._play_cue("ui_select")
                    elif event.key in (pygame.K_LEFT, pygame.K_a):
                        if adjust_setting(self.profile.settings, self.settings_index, -1):
                            self._settings_changed()
                    elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_SPACE):
                        if adjust_setting(self.profile.settings, self.settings_index, 1):
                            self._settings_changed()
                    elif event.key == pygame.K_r:
                        reset_settings(self.profile.settings)
                        self._settings_changed()
                    continue
                if event.key in (pygame.K_F1, pygame.K_h):
                    self.show_help = not self.show_help
                    self.show_memory_archive = False
                    self.show_settings = False
                    self._play_cue("ui_select")
                    continue
                if event.key == pygame.K_g and not self.profile.onboarding_complete:
                    self._advance_onboarding(5, complete=True)
                    continue
                if event.key == pygame.K_m and self.state in (GameState.CITY_MAP, GameState.DISTRICT_COMPLETE):
                    self.show_memory_archive = not self.show_memory_archive
                    self.show_help = False
                    self.show_settings = False
                    self._play_cue("ui_select")
                    continue
                if event.key == pygame.K_ESCAPE:
                    if self.show_memory_archive:
                        self.show_memory_archive = False
                    elif self.show_help:
                        self.show_help = False
                    elif self.state == GameState.PAUSED:
                        self.state = self.previous_state
                    elif self.state == GameState.TITLE:
                        self.running = False
                    else:
                        self.previous_state = self.state
                        self.state = GameState.PAUSED
                    self._play_cue("ui_select")
                    continue
                if self.state == GameState.PAUSED and event.key == pygame.K_q:
                    self.running = False
                elif self.state == GameState.TITLE and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.pending_industrial_finale:
                        self.pending_industrial_finale = False
                        self.profile.profile_version = 5
                        self.district_complete_page = 0
                        self.state = GameState.DISTRICT_COMPLETE
                        self.city_message = "INDUSTRIAL GRID CONTROLLED • MIGRATED PROFILE FINALE"
                        self._save_profile()
                        self._play_cue("district_complete")
                    else:
                        self.state = GameState.CITY_MAP
                        if not self.profile.onboarding_complete:
                            self._advance_onboarding(1)
                        self._play_cue("ui_confirm")
                elif self.state == GameState.DISTRICT_COMPLETE and event.key in (
                    pygame.K_RETURN, pygame.K_SPACE, pygame.K_e
                ):
                    if "industrial_grid" in self.profile.districts_completed and self.district_complete_page == 0:
                        self.district_complete_page = 1
                        self.city_message = "GLEEBS SIGNAL OVERRIDE • HIGH TOWERS AUTHORITY DETECTED"
                        self._play_cue("gleebs_alarm")
                    else:
                        self.state = GameState.CITY_MAP
                        self._play_cue("ui_confirm")
                elif self.state == GameState.CITY_MAP and event.key in (pygame.K_RETURN, pygame.K_e):
                    if not self.show_memory_archive:
                        self._enter_selected()
                elif self.state == GameState.BUILDING_STAGE:
                    if event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                        before = self.stage.camera
                        self.stage.select_camera(event.key - pygame.K_0)
                        self._remember_stage_clues()
                        if self.stage.camera is not before:
                            self._play_cue("camera_switch")
                            if (
                                self.stage.building_id == "surveillance_annex"
                                and self.stage.camera.name == "OPERATIONS"
                                and not self.profile.onboarding_complete
                            ):
                                self._advance_onboarding(5, complete=True)
                    elif event.key == pygame.K_TAB and len(self.stage.camera_chain) == 4:
                        before = self.stage.camera
                        self.stage.select_camera(4)
                        self._remember_stage_clues()
                        if self.stage.camera is not before:
                            self._play_cue("camera_switch")
                    elif event.key in (pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8):
                        self.stage.select_method_key(event.key - pygame.K_0)
                        if (
                            self.stage.building_id == "surveillance_annex"
                            and self.stage.camera.name == "EXTERIOR"
                            and event.key == pygame.K_5
                            and not self.profile.onboarding_complete
                        ):
                            self._advance_onboarding(3)
                        self._play_cue("ui_select")
                    elif event.key == pygame.K_e:
                        self._execute_stage_interaction()
                    elif event.key == pygame.K_r:
                        self.stage.force_trace()
                        self.profile.statistics["maximum_trace"] = max(
                            float(self.profile.statistics.get("maximum_trace", 0)), self.stage.trace
                        )
                        self._play_cue("hack_noisy")
                    elif event.key == pygame.K_RETURN and (self.stage.captured or self.stage.failed):
                        self._return_city()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                virtual_pos = self._screen_to_virtual(event.pos)
                if event.button == 1 and self.show_settings:
                    point = (int(virtual_pos.x), int(virtual_pos.y))
                    if SETTINGS_CLOSE_RECT.collidepoint(point):
                        self.show_settings = False
                        self._play_cue("ui_back")
                    elif SETTINGS_RESET_RECT.collidepoint(point):
                        reset_settings(self.profile.settings)
                        self._settings_changed()
                    else:
                        row_index = settings_hit_test(point)
                        if row_index is not None:
                            self.settings_index = row_index
                            row = SETTING_ROWS[row_index]
                            row_rect = settings_row_rect(row_index)
                            direction = 1 if row.kind == "toggle" or point[0] >= row_rect.centerx else -1
                            if adjust_setting(self.profile.settings, row_index, direction):
                                self._settings_changed()
                            else:
                                self._play_cue("ui_select")
                    continue
                if event.button == 1:
                    if self.state == GameState.TITLE:
                        if self.pending_industrial_finale:
                            self.pending_industrial_finale = False
                            self.profile.profile_version = 5
                            self.district_complete_page = 0
                            self.state = GameState.DISTRICT_COMPLETE
                            self.city_message = "INDUSTRIAL GRID CONTROLLED • MIGRATED PROFILE FINALE"
                            self._save_profile()
                            self._play_cue("district_complete")
                        else:
                            self.state = GameState.CITY_MAP
                            if not self.profile.onboarding_complete:
                                self._advance_onboarding(1)
                            self._play_cue("ui_confirm")
                    elif (
                        self.state in (GameState.CITY_MAP, GameState.DISTRICT_COMPLETE)
                        and not self.show_help
                        and not self.show_memory_archive
                        and not self.show_settings
                    ):
                        before = self.city.selected_building_id
                        self.city.select_at(virtual_pos)
                        if before != self.city.selected_building_id:
                            self._play_cue("ui_select")
                elif event.button == 4 and self.state == GameState.CITY_MAP and not self.show_settings:
                    self.city.change_zoom(1)
                    self._play_cue("ui_select")
                elif event.button == 5 and self.state == GameState.CITY_MAP and not self.show_settings:
                    self.city.change_zoom(-1)
                    self._play_cue("ui_select")
            elif event.type == pygame.MOUSEWHEEL:
                if self.show_settings:
                    self.settings_index = (self.settings_index - (1 if event.y > 0 else -1)) % len(SETTING_ROWS)
                    self._play_cue("ui_select")
                elif self.state == GameState.CITY_MAP and not self.show_memory_archive:
                    self.city.change_zoom(1 if event.y > 0 else -1)
                    self._play_cue("ui_select")

    def _remember_stage_clues(self) -> None:
        self.profile.record_clues(self.stage.building_id, self.stage.discovered_clues)

    def _execute_stage_interaction(self) -> None:
        before_attempt = self.stage.attempt_count
        was_captured = self.stage.captured
        self.stage.interact()
        self._remember_stage_clues()
        if self.stage.attempt_count == before_attempt or self.stage.last_outcome is None:
            self._play_cue("hack_rejected")
            return
        outcome = self.stage.last_outcome.value
        if (
            self.stage.building_id == "surveillance_annex"
            and self.stage.camera.name == "EXTERIOR"
            and outcome == "clean_success"
            and not self.profile.onboarding_complete
        ):
            self._advance_onboarding(4)
        self.profile.record_hack(
            self.stage.building_id,
            self.stage.selected_method_id,
            outcome,
            self.stage.trace,
            self.stage.detection_cause,
        )
        cue = {
            "clean_success": "hack_clean",
            "noisy_success": "hack_noisy",
            "rejected_attempt": "hack_rejected",
            "gleebs_violation": "gleebs_alarm",
        }.get(outcome, "ui_confirm")
        self._play_cue(cue)
        if self.stage.captured and not was_captured:
            self._play_cue("building_capture")
        if self.stage.gleebs_ejected:
            self.stage.gleebs_message = gleebs_response(
                self.profile, self.stage.building_id, self.stage.detection_cause
            )
        self._save_profile()

    def _enter_selected(self) -> None:
        building = self.city.selected()
        if building.status == BuildingStatus.LOCKED_DOWN:
            self.city_message = (
                f"{building.name}: RESISTANCE LOCKOUT "
                f"{self.city.lockout_remaining(building.building_id):02d}s"
            )
            self._play_cue("hack_rejected")
            return
        if building.status not in (BuildingStatus.VULNERABLE, BuildingStatus.CAPTURED):
            self.city_message = f"{building.name}: NO VALID BREACH ROUTE"
            self._play_cue("hack_rejected")
            return
        self.stage = BuildingStageState(building.building_id)
        self.stage.discovered_clues.update(
            self.profile.discovered_clues.get(building.building_id, set())
        )
        self.state = GameState.BUILDING_STAGE
        self.city_message = ""
        if building.building_id == "surveillance_annex" and not self.profile.onboarding_complete:
            self._advance_onboarding(2)
        self._play_cue("ui_confirm")
        self._sync_audio(force=True)

    def _capture_profile_progress(self, building_id: str) -> None:
        self.profile.capture_building(building_id)
        self.profile.record_clues(building_id, self.stage.discovered_clues)
        fragment = recover_building_memory(self.profile, building_id)
        if fragment:
            self.last_memory_unlocked = fragment.fragment_id
            self.city_message = f"MEMORY RECOVERED • {fragment.title} • PRESS M TO REVIEW"
            self._play_cue("memory_restore")
        self.profile.building_lockouts.pop(building_id, None)
        self._save_profile()

    def _return_city(self) -> None:
        if self.stage.captured:
            self._capture_profile_progress(self.stage.building_id)
            apply_profile_to_city(self.profile, self.city)
            if self.stage.building_id == "surveillance_annex":
                self.city.selected_building_id = "maintenance_depot"
                self._set_city_message("ANNEX CAPTURED • MAINTENANCE YARD BREACH ROUTE ACQUIRED")
                self.state = GameState.CITY_MAP
            elif self.stage.building_id == "maintenance_depot":
                self.city.selected_building_id = "transit_substation"
                self._set_city_message("MAINTENANCE YARD CAPTURED • TRANSIT DEPOT BREACH ROUTE ACQUIRED")
                self.state = GameState.CITY_MAP
            elif self.stage.building_id == "transit_substation":
                self.city.selected_building_id = "corporate_mall"
                self.city.zoom = 0.82
                self.city.camera.update(1700, 420)
                self.city._clamp_camera()
                self.profile.districts_completed.add("municipal_fringe")
                self.profile.unlocked_buildings.add("corporate_mall")
                self._save_profile()
                apply_profile_to_city(self.profile, self.city)
                self.city.selected_building_id = "corporate_mall"
                write_result_packets(
                    self.profile, time.perf_counter() - self.start_time
                )
                self.city_message = (
                    "MUNICIPAL FRINGE CONTROLLED • CORPORATE MALL BREACH ROUTE ACQUIRED"
                )
                self.state = GameState.DISTRICT_COMPLETE
                self._play_cue("district_complete")
                self._district_audio_played = True
            elif self.stage.building_id == "corporate_mall":
                self.city.selected_building_id = "media_broadcast"
                self.city.zoom = 0.82
                self.city.camera.update(1850, 420)
                self.city._clamp_camera()
                self.city_message = (
                    "CORPORATE MALL CAPTURED • MEDIA BROADCAST BREACH ROUTE ACQUIRED"
                )
                self.state = GameState.CITY_MAP
            elif self.stage.building_id == "media_broadcast":
                self.city.selected_building_id = "financial_exchange"
                self.city.zoom = 0.82
                self.city.camera.update(2110, 420)
                self.city._clamp_camera()
                self.city_message = (
                    "MEDIA BROADCAST CAPTURED • PUBLIC COMMUNICATION ACCESS UNLOCKED • FINANCIAL EXCHANGE VULNERABLE"
                )
                self.state = GameState.CITY_MAP
            elif self.stage.building_id == "financial_exchange":
                self.city.selected_building_id = "private_clinic"
                self.city.zoom = 0.82
                self.city.camera.update(2380, 420)
                self.city._clamp_camera()
                self.city_message = (
                    "FINANCIAL EXCHANGE CAPTURED • TRANSACTION AUTHORITY ACQUIRED • PRIVATE CLINIC VULNERABLE"
                )
                self.state = GameState.CITY_MAP
            elif self.stage.building_id == "private_clinic":
                self.profile.districts_completed.add("commercial_spine")
                self.profile.unlocked_buildings.add("automated_factory")
                self._save_profile()
                apply_profile_to_city(self.profile, self.city)
                self.city.selected_building_id = "automated_factory"
                self.city.zoom = 0.82
                self.city.camera.update(1200, 1040)
                self.city._clamp_camera()
                write_result_packets(self.profile, time.perf_counter() - self.start_time)
                self.city_message = "COMMERCIAL SPINE CONTROLLED • ANDREW BIOLOGICAL FILE RECOVERED • AUTOMATED FACTORY VULNERABLE"
                self.state = GameState.DISTRICT_COMPLETE
                self._play_cue("district_complete")
            elif self.stage.building_id == "automated_factory":
                self.city.selected_building_id = "power_distribution_plant"
                self.city.zoom = 0.82
                self.city.camera.update(1400, 1040)
                self.city._clamp_camera()
                self.city_message = "AUTOMATED FACTORY CAPTURED • POWER DISTRIBUTION PLANT VULNERABLE"
                self.state = GameState.CITY_MAP
            elif self.stage.building_id == "power_distribution_plant":
                self.city.selected_building_id = "drone_assembly_facility"
                self.city.zoom = 0.82
                self.city.camera.update(1680, 1040)
                self.city._clamp_camera()
                self.city_message = "POWER DISTRIBUTION PLANT CAPTURED • CRITICAL GRID STABILIZED • DRONE ASSEMBLY FACILITY VULNERABLE"
                self.state = GameState.CITY_MAP
            elif self.stage.building_id == "drone_assembly_facility":
                self.city.selected_building_id = "waste_processing_complex"
                self.city.zoom = 0.82
                self.city.camera.update(1940, 1040)
                self.city._clamp_camera()
                self.city_message = "DRONE ASSEMBLY FACILITY CAPTURED • RESCUE IDENTITIES PRESERVED • WASTE PROCESSING COMPLEX VULNERABLE"
                self.state = GameState.CITY_MAP
            elif self.stage.building_id == "waste_processing_complex":
                self.profile.districts_completed.add("industrial_grid")
                self._save_profile()
                apply_profile_to_city(self.profile, self.city)
                self.city.selected_building_id = "waste_processing_complex"
                self.city.zoom = 0.82
                self.city.camera.update(1720, 940)
                self.city._clamp_camera()
                write_result_packets(self.profile, time.perf_counter() - self.start_time)
                self.city_message = "INDUSTRIAL GRID CONTROLLED • FOUR FACILITIES SYNCHRONIZED"
                self.district_complete_page = 0
                self.state = GameState.DISTRICT_COMPLETE
                self._play_cue("district_complete")
            else:
                self.state = GameState.CITY_MAP
            self.renderer = CityRenderer(float(self.profile.settings.get("text_scale", 1.0)))
        else:
            self.state = GameState.CITY_MAP
        self._sync_audio(force=True)

    def _apply_edge_pan(self, dt: float) -> None:
        if (
            not self.profile.settings.get("edge_pan", True)
            or self.config.quick_test
            or self.config.test_shot is not None
            or not pygame.mouse.get_focused()
        ):
            return
        pos = self._screen_to_virtual(pygame.mouse.get_pos())
        edge = 20
        delta = pygame.Vector2()
        if VIEW_RECT.left <= pos.x <= VIEW_RECT.left + edge:
            delta.x = -1
        elif VIEW_RECT.right - edge <= pos.x <= VIEW_RECT.right:
            delta.x = 1
        if VIEW_RECT.top <= pos.y <= VIEW_RECT.top + edge:
            delta.y = -1
        elif VIEW_RECT.bottom - edge <= pos.y <= VIEW_RECT.bottom:
            delta.y = 1
        if delta.length_squared() > 0:
            speed = 330.0 / max(self.city.zoom, 0.1)
            self.city.camera += delta.normalize() * speed * dt
            self.city._clamp_camera()

    def _update(self, dt: float) -> None:
        if self.city_message != self._city_message_seen:
            self._city_message_seen = self.city_message
            self._city_message_age = 0.0
        elif self.city_message:
            self._city_message_age += dt
            if self._city_message_age >= 7.0:
                self.city_message = ""
                self._city_message_seen = ""
                self._city_message_age = 0.0
        if self.audio_caption:
            self._audio_caption_age += dt
            if self._audio_caption_age >= self._audio_caption_duration:
                self.audio_caption = ""
                self._audio_caption_age = 0.0
        modal_open = self.show_help or self.show_memory_archive or self.show_settings
        if self.state == GameState.CITY_MAP and not modal_open:
            self.city.update(dt, pygame.key.get_pressed())
            self._apply_edge_pan(dt)
            active_lockouts = dict(self.city.lockouts)
            if active_lockouts != self._last_lockout_snapshot:
                self.profile.building_lockouts = active_lockouts
                self._last_lockout_snapshot = active_lockouts
                self._save_profile()
        elif self.state == GameState.BUILDING_STAGE and not modal_open:
            self.stage.update(dt)
            self.stage.move_drone(dt, pygame.key.get_pressed())
            self.profile.statistics["maximum_trace"] = max(
                float(self.profile.statistics.get("maximum_trace", 0)), self.stage.trace
            )
            if self.stage.gleebs_ejected:
                if not self.stage.gleebs_message:
                    self.stage.gleebs_message = gleebs_response(
                        self.profile, self.stage.building_id, self.stage.detection_cause
                    )
                self.state = GameState.GLEEBS_EJECTION
                self.ejection_elapsed = 0.0
                self._play_cue("gleebs_alarm")
        elif self.state == GameState.GLEEBS_EJECTION and not modal_open:
            self.ejection_elapsed += dt
            if self.ejection_elapsed >= 1.35:
                self.city.start_lockout(
                    self.stage.building_id, 60, self.stage.detection_cause
                )
                self._play_cue("lockout_start")
                expiry = self.city.lockouts[self.stage.building_id]
                self.profile.set_lockout(self.stage.building_id, expiry)
                self.profile.record_clues(
                    self.stage.building_id, self.stage.discovered_clues
                )
                apply_profile_to_city(self.profile, self.city)
                if self.stage.building_id == "surveillance_annex":
                    self.profile.unlocked_buildings.add("maintenance_depot")
                    self.city.set_status("maintenance_depot", BuildingStatus.VULNERABLE)
                    self.city.selected_building_id = "maintenance_depot"
                elif self.stage.building_id == "maintenance_depot":
                    self.city.selected_building_id = "surveillance_annex"
                elif self.stage.building_id == "corporate_mall":
                    self.city.selected_building_id = "transit_substation"
                    self.city.camera.update(self.city.selected().world_pos)
                elif self.stage.building_id == "media_broadcast":
                    self.city.selected_building_id = "corporate_mall"
                    self.city.camera.update(self.city.selected().world_pos)
                elif self.stage.building_id == "financial_exchange":
                    self.city.selected_building_id = "media_broadcast"
                    self.city.camera.update(self.city.selected().world_pos)
                elif self.stage.building_id == "private_clinic":
                    self.city.selected_building_id = "financial_exchange"
                    self.city.camera.update(self.city.selected().world_pos)
                elif self.stage.building_id == "automated_factory":
                    self.city.selected_building_id = "private_clinic"
                    self.city.camera.update(self.city.selected().world_pos)
                elif self.stage.building_id == "power_distribution_plant":
                    self.city.selected_building_id = "automated_factory"
                    self.city.camera.update(self.city.selected().world_pos)
                elif self.stage.building_id == "drone_assembly_facility":
                    self.city.selected_building_id = "power_distribution_plant"
                    self.city.camera.update(self.city.selected().world_pos)
                elif self.stage.building_id == "waste_processing_complex":
                    self.city.selected_building_id = "drone_assembly_facility"
                    self.city.camera.update(self.city.selected().world_pos)
                else:
                    self.city.selected_building_id = "maintenance_depot"
                self._last_lockout_snapshot = dict(self.city.lockouts)
                self._save_profile()
                self.city_message = (
                    f"GLEEBS EJECTED ANDREW • {self.stage.title} LOCKED • CITY FREEROAM ACTIVE"
                )
                self.state = GameState.CITY_MAP
        self._sync_audio()

    def _render(self) -> None:
        if self.state == GameState.TITLE:
            self.renderer.render_title(self.virtual, self.elapsed, self.profile)
        elif self.state in (GameState.BUILDING_STAGE, GameState.GLEEBS_EJECTION):
            self.stage_renderer.render(
                self.virtual,
                self.stage,
                self.elapsed,
                self.profile.settings,
                0 if self.profile.onboarding_complete else self.profile.onboarding_step,
            )
        else:
            self.renderer.render_city(
                self.virtual, self.city, self.elapsed, self.profile, self.profile.settings
            )
            if self.city_message:
                self.renderer.render_city_message(self.virtual, self.city_message)
            if self.state == GameState.DISTRICT_COMPLETE:
                self.renderer.render_district_complete(
                    self.virtual, self.elapsed, self.profile, self.district_complete_page
                )
            if self.show_memory_archive:
                self.renderer.render_memory_archive(
                    self.virtual, memory_records(self.profile), self.profile
                )
            if self.state == GameState.CITY_MAP and not self.profile.onboarding_complete:
                self.renderer.render_onboarding_city(
                    self.virtual, self.profile.onboarding_step, self.city.selected()
                )
        if (
            self.audio_caption
            and bool(self.profile.settings.get("audio_captions", True))
            and not (self.show_help or self.show_memory_archive or self.show_settings)
            and self.state != GameState.PAUSED
        ):
            self.renderer.render_audio_caption(
                self.virtual,
                self.audio_caption,
                stage_active=self.state in (GameState.BUILDING_STAGE, GameState.GLEEBS_EJECTION),
                city_message_active=bool(self.city_message),
            )
        if self.state == GameState.PAUSED:
            self.renderer.render_pause(self.virtual)
        if self.show_help:
            self.renderer.render_help(
                self.virtual, self.state in (GameState.BUILDING_STAGE, GameState.GLEEBS_EJECTION)
            )
        if self.show_settings:
            self.renderer.render_settings(
                self.virtual, self.profile.settings, self.settings_index, self.audio.available
            )

    def _present(self) -> None:
        screen_rect = self.screen.get_rect()
        scale = min(screen_rect.w / VIRTUAL_SIZE[0], screen_rect.h / VIRTUAL_SIZE[1])
        size = (int(VIRTUAL_SIZE[0] * scale), int(VIRTUAL_SIZE[1] * scale))
        output = (
            pygame.transform.smoothscale(self.virtual, size)
            if size != VIRTUAL_SIZE
            else self.virtual
        )
        self.screen.fill((0, 0, 0))
        self.screen.blit(output, output.get_rect(center=screen_rect.center))
        pygame.display.flip()

    def _screen_to_virtual(self, position):
        screen_rect = self.screen.get_rect()
        scale = min(screen_rect.w / VIRTUAL_SIZE[0], screen_rect.h / VIRTUAL_SIZE[1])
        left = (screen_rect.w - VIRTUAL_SIZE[0] * scale) / 2
        top = (screen_rect.h - VIRTUAL_SIZE[1] * scale) / 2
        return pygame.Vector2(
            (position[0] - left) / scale, (position[1] - top) / scale
        )

    def _write_quick_result(self) -> None:
        result = {
            "project": "GHOST SIGNAL: UTOPIA",
            "pass": PASS_ID,
            "version": VERSION,
            "build": BUILD_LABEL,
            "state": self.state.name,
            "frames": self.frame_count,
            "average_frame_ms": round(
                sum(self.frame_times) / max(1, len(self.frame_times)) * 1000, 4
            ),
            "captured_buildings": len(self.profile.captured_buildings),
            "memory_fragments": len(self.profile.memory_fragments),
            "audio": self.audio.snapshot(),
            "settings": dict(self.profile.settings),
            "result": "PASS",
        }
        path = result_dir() / "quick_test.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
