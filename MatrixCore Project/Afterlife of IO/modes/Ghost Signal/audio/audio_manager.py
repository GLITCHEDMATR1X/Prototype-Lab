from __future__ import annotations

from pathlib import Path
from typing import Any

import pygame


class AudioManager:
    """Small channel-based audio authority with non-stacking ambience loops."""

    AMBIENCE_CHANNEL = 0
    MACHINE_CHANNEL = 1
    MUSIC_CHANNEL = 2
    SFX_CHANNELS = tuple(range(3, 8))

    def __init__(self, disabled: bool = False, asset_root: Path | None = None) -> None:
        self.disabled = bool(disabled)
        self.available = False
        self.muted = False
        self.master_volume = 0.8
        self.ambience_volume = 0.62
        self.music_volume = 0.42
        self.sfx_volume = 0.86
        self.current_scene = "silent"
        self.current_machine = ""
        self.paused = False
        self.asset_root = asset_root or Path(__file__).resolve().parents[1] / "assets" / "audio" / "generated"
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self._sfx_cursor = 0
        # False when a host (Afterlife of IO) already owns the mixer; then
        # shutdown() only stops sounds instead of closing the host's audio.
        self.owns_mixer = False
        if self.disabled:
            return
        try:
            pygame.mixer.pre_init(22050, -16, 2, 512)
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(22050, -16, 2, 512)
                self.owns_mixer = True
            pygame.mixer.set_num_channels(8)
            pygame.mixer.set_reserved(3)
            self.available = True
            self._load_assets()
        except (pygame.error, OSError):
            self.disabled = True
            self.available = False

    def _load_assets(self) -> None:
        names = (
            "city_ambience",
            "interior_hum",
            "drone_loop",
            "signal_score",
            "ui_select",
            "ui_confirm",
            "camera_switch",
            "hack_clean",
            "hack_noisy",
            "hack_rejected",
            "gleebs_alarm",
            "building_capture",
            "district_complete",
            "ui_back",
            "memory_restore",
            "lockout_start",
        )
        for name in names:
            path = self.asset_root / f"{name}.wav"
            if path.exists():
                self.sounds[name] = pygame.mixer.Sound(path)

    def apply_settings(self, settings: dict[str, Any]) -> None:
        self.master_volume = max(0.0, min(1.0, float(settings.get("master_volume", 0.8))))
        self.ambience_volume = max(0.0, min(1.0, float(settings.get("ambience_volume", 0.62))))
        self.music_volume = max(0.0, min(1.0, float(settings.get("music_volume", 0.42))))
        self.sfx_volume = max(0.0, min(1.0, float(settings.get("sfx_volume", 0.86))))
        self.muted = bool(settings.get("muted", False))
        self._refresh_channel_volumes()

    def _refresh_channel_volumes(self) -> None:
        if not self.available:
            return
        mute = 0.0 if self.muted else 1.0
        pygame.mixer.Channel(self.AMBIENCE_CHANNEL).set_volume(
            self.master_volume * self.ambience_volume * mute
        )
        pygame.mixer.Channel(self.MACHINE_CHANNEL).set_volume(
            self.master_volume * self.ambience_volume * 0.72 * mute
        )
        pygame.mixer.Channel(self.MUSIC_CHANNEL).set_volume(
            self.master_volume * self.music_volume * mute
        )
        for channel_id in self.SFX_CHANNELS:
            pygame.mixer.Channel(channel_id).set_volume(
                self.master_volume * self.sfx_volume * mute
            )

    def set_scene(self, scene: str, machine: str = "") -> None:
        if not self.available:
            self.current_scene = scene
            self.current_machine = machine
            return
        if scene != self.current_scene:
            self.current_scene = scene
            ambience_name = {
                "title": "city_ambience",
                "city": "city_ambience",
                "stage": "interior_hum",
                "ejection": "interior_hum",
            }.get(scene, "")
            channel = pygame.mixer.Channel(self.AMBIENCE_CHANNEL)
            channel.fadeout(220)
            if ambience_name and ambience_name in self.sounds:
                channel.play(self.sounds[ambience_name], loops=-1, fade_ms=240)
        music_channel = pygame.mixer.Channel(self.MUSIC_CHANNEL)
        if scene in ("title", "city", "stage") and "signal_score" in self.sounds:
            if not music_channel.get_busy():
                music_channel.play(self.sounds["signal_score"], loops=-1, fade_ms=350)
        elif music_channel.get_busy():
            music_channel.fadeout(250)
        if machine != self.current_machine:
            self.current_machine = machine
            channel = pygame.mixer.Channel(self.MACHINE_CHANNEL)
            channel.fadeout(150)
            if machine and machine in self.sounds:
                channel.play(self.sounds[machine], loops=-1, fade_ms=180)
        self._refresh_channel_volumes()

    def play(self, cue: str) -> None:
        if not self.available or self.muted or cue not in self.sounds:
            return
        cue_gain = {
            "ui_select": 0.72,
            "ui_confirm": 0.78,
            "ui_back": 0.70,
            "camera_switch": 0.80,
            "hack_clean": 0.92,
            "hack_noisy": 0.88,
            "hack_rejected": 0.82,
            "gleebs_alarm": 0.90,
            "building_capture": 0.92,
            "district_complete": 0.92,
            "memory_restore": 0.86,
            "lockout_start": 0.88,
        }.get(cue, 1.0)
        channel = None
        for channel_id in self.SFX_CHANNELS:
            candidate = pygame.mixer.Channel(channel_id)
            if not candidate.get_busy():
                channel = candidate
                break
        if channel is None:
            channel_id = self.SFX_CHANNELS[self._sfx_cursor % len(self.SFX_CHANNELS)]
            self._sfx_cursor += 1
            channel = pygame.mixer.Channel(channel_id)
        mute = 0.0 if self.muted else 1.0
        channel.set_volume(self.master_volume * self.sfx_volume * cue_gain * mute)
        channel.play(self.sounds[cue])

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        self._refresh_channel_volumes()
        return self.muted

    def pause(self) -> None:
        if self.available and not self.paused:
            pygame.mixer.pause()
            self.paused = True

    def resume(self) -> None:
        if self.available and self.paused:
            pygame.mixer.unpause()
            self.paused = False

    def snapshot(self) -> dict[str, object]:
        return {
            "available": self.available,
            "disabled": self.disabled,
            "muted": self.muted,
            "scene": self.current_scene,
            "machine": self.current_machine,
            "loaded": sorted(self.sounds),
        }

    def shutdown(self) -> None:
        if self.available:
            pygame.mixer.stop()
            if self.owns_mixer:
                pygame.mixer.quit()
