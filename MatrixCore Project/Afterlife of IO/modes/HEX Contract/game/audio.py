from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

import pygame


class AudioManager:
    """Presentation-focused audio layer for HEX CONTRACT.

    Short cues are pre-generated and loaded as ``Sound`` objects. Long-form music
    is optional and streamed from ``assets/music`` so user-supplied Fragment
    tracks do not have to be held in memory. Audio-device or decoder failure is
    always non-fatal and ``--no-audio`` remains a supported launch path.
    """

    SAMPLE_RATE = 22050
    MUSIC_EXTENSIONS = {".wav", ".ogg", ".mp3"}

    SFX_SPECS = {
        "confirm": (0.11, (440.0, 660.0), 0.28, 0.0, 0.00),
        "back": (0.10, (330.0, 220.0), 0.22, 0.0, 0.00),
        "deploy": (0.24, (110.0, 220.0, 440.0), 0.26, 8.0, 0.06),
        "success": (0.40, (392.0, 523.25, 659.25), 0.26, 3.0, 0.02),
        "failure": (0.35, (196.0, 146.83), 0.24, 2.0, 0.05),
        "restore": (0.32, (261.63, 392.0, 783.99), 0.24, 4.0, 0.02),
        "hero_melee": (0.13, (92.0, 184.0, 368.0), 0.34, 14.0, 0.26),
        "hero_ranged": (0.12, (360.0, 720.0, 1080.0), 0.28, 18.0, 0.10),
        "hero_ability": (0.28, (145.0, 290.0, 580.0), 0.28, 7.0, 0.08),
        "enemy_melee": (0.15, (72.0, 144.0, 216.0), 0.30, 10.0, 0.30),
        "enemy_ranged": (0.14, (205.0, 410.0, 615.0), 0.26, 13.0, 0.16),
        "impact_enemy": (0.10, (118.0, 236.0), 0.30, 21.0, 0.38),
        "impact_hero": (0.14, (88.0, 132.0), 0.31, 8.0, 0.34),
        "enemy_down": (0.20, (132.0, 99.0, 66.0), 0.26, 5.0, 0.24),
        "cover_hit": (0.11, (155.0, 310.0), 0.28, 17.0, 0.34),
        "cover_break": (0.34, (82.0, 123.0, 164.0), 0.34, 5.0, 0.45),
        "objective": (0.25, (330.0, 495.0, 660.0), 0.25, 4.0, 0.04),
        "civilian_link": (0.21, (392.0, 587.0), 0.22, 5.0, 0.03),
        "boss_intro": (0.55, (55.0, 82.5, 165.0), 0.34, 2.5, 0.18),
        "boss_phase": (0.34, (110.0, 220.0, 440.0), 0.31, 8.0, 0.12),
        "boss_special": (0.24, (73.0, 146.0, 292.0), 0.30, 12.0, 0.22),
        "boss_down": (0.72, (65.0, 97.5, 130.0, 195.0), 0.34, 2.2, 0.22),
    }

    AMBIENCE_SPECS = {
        "ambience_guild": (3.2, (55.0, 82.5, 110.0), 0.070, 0.27, 0.02),
        "ambience_purge": (3.6, (43.0, 64.5, 129.0), 0.074, 0.33, 0.04),
        "ambience_recovery": (3.8, (49.0, 98.0, 196.0), 0.066, 0.22, 0.03),
        "ambience_rescue": (3.5, (58.0, 87.0, 174.0), 0.068, 0.29, 0.05),
    }

    COOLDOWNS_MS = {
        "hero_melee": 70,
        "hero_ranged": 70,
        "enemy_melee": 85,
        "enemy_ranged": 85,
        "impact_enemy": 55,
        "impact_hero": 75,
        "cover_hit": 90,
        "boss_special": 180,
    }

    def __init__(self, root: Path, enabled: bool, settings: dict):
        self.root = root
        self.enabled = bool(enabled and pygame.mixer.get_init())
        self.settings = settings
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.ambience_channel: pygame.mixer.Channel | None = None
        self.current_ambience = ""
        self.current_context = ""
        self.last_play_ms: dict[str, int] = {}
        self.music_dir = root / "assets" / "music"
        self.music_tracks: list[Path] = []
        self.music_routes: dict[str, Path] = {}
        self.music_context = ""
        self.current_music: Path | None = None
        self.music_failed: set[Path] = set()
        if not self.enabled:
            return
        try:
            pygame.mixer.set_num_channels(max(24, pygame.mixer.get_num_channels()))
        except pygame.error:
            pass
        self.asset_dir = root / "assets" / "generated" / "sfx"
        self.asset_dir.mkdir(parents=True, exist_ok=True)
        self.music_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_assets()
        for key in tuple(self.SFX_SPECS) + tuple(self.AMBIENCE_SPECS):
            try:
                self.sounds[key] = pygame.mixer.Sound(str(self.asset_dir / f"{key}.wav"))
            except pygame.error:
                self.enabled = False
                self.sounds.clear()
                return
        self.refresh_music_library()
        self._load_music_manifest()
        self.apply_settings(settings)

    @staticmethod
    def _envelope(i: int, total: int, attack: float = 0.045, release: float = 0.24) -> float:
        x = i / max(1, total - 1)
        a = min(1.0, x / max(0.001, attack))
        r = min(1.0, (1.0 - x) / max(0.001, release))
        return max(0.0, min(a, r))

    def _write_tone(
        self,
        path: Path,
        duration: float,
        freqs: tuple[float, ...],
        volume: float,
        pulse: float = 0.0,
        noise_mix: float = 0.0,
    ) -> None:
        total = max(1, int(self.SAMPLE_RATE * duration))
        frames = bytearray()
        for i in range(total):
            t = i / self.SAMPLE_RATE
            tonal = sum(math.sin(2.0 * math.pi * f * t) for f in freqs) / max(1, len(freqs))
            # Deterministic pseudo-noise gives impacts texture without runtime RNG.
            noisy = math.sin(i * 12.9898 + math.sin(i * 0.071) * 43.17)
            sample = tonal * (1.0 - noise_mix) + noisy * noise_mix
            if pulse:
                sample *= 0.72 + 0.28 * math.sin(2.0 * math.pi * pulse * t)
            sample *= self._envelope(i, total) * volume
            value = int(max(-1.0, min(1.0, sample)) * 32767)
            frames.extend(struct.pack("<h", value))
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.SAMPLE_RATE)
            wav.writeframes(frames)

    def _ensure_assets(self) -> None:
        for key, args in {**self.SFX_SPECS, **self.AMBIENCE_SPECS}.items():
            path = self.asset_dir / f"{key}.wav"
            if not path.exists() or path.stat().st_size < 128:
                self._write_tone(path, *args)
        # Preserve the original Pass 12 filename for old overlays/drop-ins.
        legacy = self.asset_dir / "ambience.wav"
        if not legacy.exists():
            try:
                legacy.write_bytes((self.asset_dir / "ambience_guild.wav").read_bytes())
            except OSError:
                pass

    def refresh_music_library(self) -> list[Path]:
        if not self.music_dir.exists():
            self.music_tracks = []
            return self.music_tracks
        self.music_tracks = sorted(
            p for p in self.music_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in self.MUSIC_EXTENSIONS
        )
        return list(self.music_tracks)

    def _load_music_manifest(self) -> None:
        self.music_routes = {}
        manifest_path = self.music_dir / "music_manifest.json"
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            routing = data.get("routing", {})
            main = routing.get("main")
            battle = routing.get("battle", {})
            if isinstance(main, str):
                self.music_routes["main"] = self.music_dir / main
            if isinstance(battle, dict):
                for key in ("purge", "recovery", "rescue", "sovereign"):
                    rel = battle.get(key)
                    if isinstance(rel, str):
                        self.music_routes[key] = self.music_dir / rel
        except (OSError, ValueError, TypeError):
            self.music_routes = {}

    def _effective_music_gain(self) -> float:
        master = max(0.0, min(1.0, float(self.settings.get("master_volume", 0.8))))
        music = max(0.0, min(1.0, float(self.settings.get("music_volume", 0.75))))
        # Music is an independent user control.  The shipped default remains
        # slightly below SFX, but 100% now means full music output instead of
        # being silently clamped by the SFX slider.
        return master * music

    def apply_settings(self, settings: dict) -> None:
        self.settings = settings
        if not self.enabled:
            return
        master = max(0.0, min(1.0, float(settings.get("master_volume", 0.8))))
        sfx = max(0.0, min(1.0, float(settings.get("sfx_volume", 0.8))))
        ambience = max(0.0, min(1.0, float(settings.get("ambience_volume", 0.45))))
        for key, sound in self.sounds.items():
            sound.set_volume(master * (ambience if key.startswith("ambience_") else sfx))
        try:
            pygame.mixer.music.set_volume(self._effective_music_gain())
        except pygame.error:
            pass

    def play(self, key: str) -> None:
        if not self.enabled or key not in self.sounds:
            return
        now = pygame.time.get_ticks()
        cooldown = self.COOLDOWNS_MS.get(key, 0)
        if cooldown and now - self.last_play_ms.get(key, -100000) < cooldown:
            return
        self.last_play_ms[key] = now
        try:
            self.sounds[key].play()
        except pygame.error:
            pass

    def _set_ambience_key(self, key: str) -> None:
        if not self.enabled or key not in self.sounds or self.current_ambience == key:
            return
        self.stop_ambience()
        try:
            self.ambience_channel = self.sounds[key].play(loops=-1, fade_ms=260)
            self.current_ambience = key
        except pygame.error:
            self.ambience_channel = None
            self.current_ambience = ""

    def _stop_music(self) -> None:
        if not self.enabled:
            return
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        self.current_music = None
        self.music_context = ""

    def _switch_music(self, context: str, track: Path | None) -> None:
        if not self.enabled:
            return
        if track is None or track in self.music_failed or not track.exists():
            if self.current_music is not None:
                self._stop_music()
            self.music_context = context
            return
        if self.current_music == track and self.music_context == context:
            try:
                busy = pygame.mixer.music.get_busy()
            except pygame.error:
                busy = False
            if busy:
                return
        # pygame.mixer.music is one streamed channel.  Stop the previous context
        # before loading the new one so menu/battle/boss music never overlaps.
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(str(track))
            pygame.mixer.music.set_volume(self._effective_music_gain())
            pygame.mixer.music.play(loops=-1, fade_ms=280)
            self.current_music = track
            self.music_context = context
        except (pygame.error, OSError):
            self.music_failed.add(track)
            self.current_music = None
            self.music_context = context

    def set_context(self, state: str, quest_key: str | None = None, *, sovereign: bool = False) -> None:
        if not self.enabled:
            return
        if state == "MISSION" and quest_key:
            self._set_ambience_key(f"ambience_{quest_key}")
            route_key = "sovereign" if sovereign else quest_key
            context = f"mission:{quest_key}:{'sovereign' if sovereign else 'battle'}"
            track = self.music_routes.get(route_key)
        else:
            self._set_ambience_key("ambience_guild")
            context = "main"
            track = self.music_routes.get("main")
        self._switch_music(context, track)
        self.current_context = state

    # Compatibility with Pass 12-15 call sites/tools.
    def set_ambience(self, active: bool) -> None:
        if active:
            self.set_context("GUILD")
        elif self.current_ambience:
            self.stop_ambience()

    def stop_ambience(self) -> None:
        if self.ambience_channel is not None:
            try:
                self.ambience_channel.fadeout(220)
            except pygame.error:
                pass
        self.ambience_channel = None
        self.current_ambience = ""
