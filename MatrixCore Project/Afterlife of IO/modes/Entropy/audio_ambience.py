from __future__ import annotations

import json
import math
import os
import random
import struct
import wave
from pathlib import Path
from typing import Dict, Optional, Tuple

import pygame

ROOT = Path(__file__).resolve().parent
AMBIENCE_ROOT = ROOT / "assets" / "sfx" / "ambience"
GENERATOR_VERSION = "entropy-ambient-v1"
SAMPLE_RATE = 22050
LOOP_SECONDS = 6.0

# Surface worlds are deliberately one-to-one with the authored world classes.
SURFACE_PROFILES: Dict[str, dict] = {
    "desert": {"seed": 101, "base": 54, "air": 0.58, "rumble": 0.16, "spark": 0.05, "pulse": 0.10},
    "ice": {"seed": 102, "base": 72, "air": 0.45, "rumble": 0.08, "spark": 0.28, "pulse": 0.05},
    "jungle": {"seed": 103, "base": 46, "air": 0.26, "rumble": 0.22, "spark": 0.18, "pulse": 0.16},
    "volcanic": {"seed": 104, "base": 34, "air": 0.18, "rumble": 0.52, "spark": 0.14, "pulse": 0.22},
    "crystal": {"seed": 105, "base": 84, "air": 0.16, "rumble": 0.08, "spark": 0.46, "pulse": 0.10},
    "oceanic": {"seed": 106, "base": 42, "air": 0.32, "rumble": 0.26, "spark": 0.08, "pulse": 0.20},
    "fungal": {"seed": 107, "base": 39, "air": 0.22, "rumble": 0.34, "spark": 0.17, "pulse": 0.28},
    "rust": {"seed": 108, "base": 31, "air": 0.28, "rumble": 0.44, "spark": 0.12, "pulse": 0.16},
    "salt": {"seed": 109, "base": 67, "air": 0.52, "rumble": 0.07, "spark": 0.22, "pulse": 0.06},
    "abyss": {"seed": 110, "base": 27, "air": 0.14, "rumble": 0.56, "spark": 0.18, "pulse": 0.30},
    "storm": {"seed": 111, "base": 38, "air": 0.64, "rumble": 0.40, "spark": 0.08, "pulse": 0.26},
    "roseglass": {"seed": 112, "base": 78, "air": 0.20, "rumble": 0.10, "spark": 0.52, "pulse": 0.12},
}

RUIN_PROFILES: Dict[str, dict] = {
    "dungeon": {"seed": 201, "base": 33, "air": 0.10, "rumble": 0.58, "spark": 0.12, "pulse": 0.22},
    "castle": {"seed": 202, "base": 51, "air": 0.24, "rumble": 0.30, "spark": 0.26, "pulse": 0.18},
    "catacomb": {"seed": 203, "base": 24, "air": 0.12, "rumble": 0.68, "spark": 0.08, "pulse": 0.32},
}

SHIP_PROFILE = {"seed": 301, "base": 47, "air": 0.05, "rumble": 0.46, "spark": 0.03, "pulse": 0.12}


def _periodic_noise(seed: int, n: int, controls: int = 72) -> list[float]:
    """Smooth circular noise with matching loop endpoints."""
    rng = random.Random(seed)
    knots = [rng.uniform(-1.0, 1.0) for _ in range(controls)]
    out = [0.0] * n
    for i in range(n):
        pos = (i / n) * controls
        a = int(pos) % controls
        b = (a + 1) % controls
        t = pos - int(pos)
        t = t * t * (3.0 - 2.0 * t)
        out[i] = knots[a] * (1.0 - t) + knots[b] * t
    return out


def _tone(cycles: int, i: int, n: int, phase: float = 0.0) -> float:
    return math.sin(math.tau * cycles * i / n + phase)


def _render_profile(profile: dict, out_path: Path, volume: float = 0.72) -> None:
    n = int(SAMPLE_RATE * LOOP_SECONDS)
    seed = int(profile["seed"])
    noise_a = _periodic_noise(seed, n, 80)
    noise_b = _periodic_noise(seed ^ 0xA51C, n, 29)
    rng = random.Random(seed ^ 0x7711)

    # Frequencies are represented as integer cycles over the whole file so the
    # resulting waveform joins cleanly when SDL_mixer loops it.
    base_cycles = max(1, int(round(float(profile["base"]) * LOOP_SECONDS)))
    harmonic_cycles = base_cycles * 2
    sub_cycles = max(1, base_cycles // 2)
    sparkle_cycles = [rng.randint(210, 520) for _ in range(3)]
    pulse_cycles = rng.randint(2, 5)

    frames = bytearray()
    for i in range(n):
        air = noise_a[i] * float(profile["air"])
        texture = noise_b[i] * float(profile["air"]) * 0.34
        rumble = (
            _tone(sub_cycles, i, n, 0.2) * 0.62
            + _tone(base_cycles, i, n, 1.1) * 0.28
            + _tone(harmonic_cycles, i, n, 2.0) * 0.10
        ) * float(profile["rumble"])
        pulse_env = (0.5 + 0.5 * _tone(pulse_cycles, i, n, 0.7)) ** 5
        pulse = pulse_env * _tone(base_cycles + 7, i, n, 1.9) * float(profile["pulse"])
        spark = 0.0
        for j, cyc in enumerate(sparkle_cycles):
            shimmer = (0.5 + 0.5 * _tone(j + 1, i, n, j * 1.7)) ** 8
            spark += _tone(cyc, i, n, j * 0.9) * shimmer
        spark *= float(profile["spark"]) / max(1, len(sparkle_cycles))

        left = (rumble + air * 0.31 + texture * 0.18 + pulse + spark) * volume
        right = (rumble + air * 0.27 - texture * 0.16 + pulse * 0.92 + spark * 0.86) * volume
        left = max(-0.96, min(0.96, left))
        right = max(-0.96, min(0.96, right))
        frames.extend(struct.pack("<hh", int(left * 32767), int(right * 32767)))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(frames)


def ensure_ambient_assets(force: bool = False) -> dict:
    """Ensure deterministic loops exist without requiring a writable install.

    Release packages already contain every loop. If a developer removes one,
    regeneration is attempted as a best-effort convenience; read-only install
    folders never prevent the game from starting.
    """
    expected = []
    expected.extend((AMBIENCE_ROOT / "surface" / f"{key}.wav", profile, 0.62) for key, profile in SURFACE_PROFILES.items())
    expected.extend((AMBIENCE_ROOT / "ruins" / f"{key}.wav", profile, 0.56) for key, profile in RUIN_PROFILES.items())
    expected.append((AMBIENCE_ROOT / "interior" / "ship_hum.wav", SHIP_PROFILE, 0.52))

    version_file = AMBIENCE_ROOT / ".ambient_version"
    manifest_path = AMBIENCE_ROOT / "manifest.json"
    try:
        version_ok = version_file.is_file() and version_file.read_text(encoding="utf-8").strip() == GENERATOR_VERSION
    except OSError:
        version_ok = False

    all_present = all(path.is_file() for path, _profile, _volume in expected)
    if not force and version_ok and all_present:
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                raw.setdefault("generated", [])
                raw["read_only_safe"] = True
                return raw
        except (OSError, ValueError, TypeError):
            pass
        return {
            "version": GENERATOR_VERSION,
            "sample_rate": SAMPLE_RATE,
            "loop_seconds": LOOP_SECONDS,
            "surface_loops": sorted(SURFACE_PROFILES),
            "ruin_loops": sorted(RUIN_PROFILES),
            "interior_loop": "ship_hum",
            "generated": [],
            "read_only_safe": True,
        }

    generated = []
    errors = []
    try:
        AMBIENCE_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        errors.append(str(exc))

    for path, profile, volume in expected:
        if force or not path.is_file():
            try:
                _render_profile(profile, path, volume)
                generated.append(str(path.relative_to(ROOT)))
            except OSError as exc:
                errors.append(f"{path.name}: {exc}")

    manifest = {
        "version": GENERATOR_VERSION,
        "sample_rate": SAMPLE_RATE,
        "loop_seconds": LOOP_SECONDS,
        "surface_loops": sorted(SURFACE_PROFILES),
        "ruin_loops": sorted(RUIN_PROFILES),
        "interior_loop": "ship_hum",
        "generated": generated,
        "read_only_safe": True,
        "errors": errors,
    }
    try:
        version_file.write_text(GENERATOR_VERSION + "\n", encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        errors.append(str(exc))
    return manifest


class AmbientAudio:
    """Owns looped environmental audio without interfering with weapon/engine SFX.

    Channels 2 and 3 cross-fade between level loops. Channel 4 is reserved for
    the ship-interior hum. Engine and one-shot effects remain on channels 0/1.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = bool(enabled and pygame.mixer.get_init())
        self.surface_sounds: Dict[str, pygame.mixer.Sound] = {}
        self.ruin_sounds: Dict[str, pygame.mixer.Sound] = {}
        self.ship_hum: Optional[pygame.mixer.Sound] = None
        self.channels: Tuple[Optional[pygame.mixer.Channel], Optional[pygame.mixer.Channel]] = (None, None)
        self.hum_channel: Optional[pygame.mixer.Channel] = None
        self.active_bank = 0
        self.active_key: Optional[str] = None
        self.context = "space"
        self.transition_count = 0
        self.load_errors = []
        self.master_volume = 1.0
        self.ambience_volume = 1.0
        self.muted = False
        self.level_base_volume = 0.0
        self.hum_base_volume = 0.68

        if not self.enabled:
            return
        try:
            pygame.mixer.set_num_channels(max(8, pygame.mixer.get_num_channels()))
            pygame.mixer.set_reserved(max(5, 5))
            self.channels = (pygame.mixer.Channel(2), pygame.mixer.Channel(3))
            self.hum_channel = pygame.mixer.Channel(4)
            self._load()
        except Exception as exc:
            self.load_errors.append(str(exc))
            self.enabled = False

    def _load_sound(self, path: Path) -> Optional[pygame.mixer.Sound]:
        try:
            return pygame.mixer.Sound(path)
        except Exception as exc:
            self.load_errors.append(f"{path.name}: {exc}")
            return None

    def _load(self) -> None:
        for key in SURFACE_PROFILES:
            snd = self._load_sound(AMBIENCE_ROOT / "surface" / f"{key}.wav")
            if snd is not None:
                self.surface_sounds[key] = snd
        for key in RUIN_PROFILES:
            snd = self._load_sound(AMBIENCE_ROOT / "ruins" / f"{key}.wav")
            if snd is not None:
                self.ruin_sounds[key] = snd
        self.ship_hum = self._load_sound(AMBIENCE_ROOT / "interior" / "ship_hum.wav")

    def _stop_level_loops(self, fade_ms: int = 420) -> None:
        for channel in self.channels:
            if channel is not None and channel.get_busy():
                channel.fadeout(fade_ms)
        self.active_key = None

    def _stop_hum(self, fade_ms: int = 360) -> None:
        if self.hum_channel is not None and self.hum_channel.get_busy():
            self.hum_channel.fadeout(fade_ms)

    def _scaled_volume(self, base: float) -> float:
        if self.muted:
            return 0.0
        return max(0.0, min(1.0, float(base) * self.master_volume * self.ambience_volume))

    def set_mix(self, master: float, ambience: float, muted: bool = False) -> None:
        self.master_volume = max(0.0, min(1.0, float(master)))
        self.ambience_volume = max(0.0, min(1.0, float(ambience)))
        self.muted = bool(muted)
        for channel in self.channels:
            if channel is not None and channel.get_busy():
                channel.set_volume(self._scaled_volume(self.level_base_volume))
        if self.hum_channel is not None and self.hum_channel.get_busy():
            self.hum_channel.set_volume(self._scaled_volume(self.hum_base_volume))

    def _play_level(self, key: str, sound: Optional[pygame.mixer.Sound], volume: float) -> None:
        if sound is None or key == self.active_key:
            return
        old = self.channels[self.active_bank]
        self.active_bank = 1 - self.active_bank
        new = self.channels[self.active_bank]
        if old is not None and old.get_busy():
            old.fadeout(650)
        if new is not None:
            new.stop()
            new.play(sound, loops=-1, fade_ms=650)
            self.level_base_volume = float(volume)
            new.set_volume(self._scaled_volume(self.level_base_volume))
            self.active_key = key
            self.transition_count += 1

    def sync_space(self) -> None:
        if not self.enabled:
            return
        if self.context != "space" or self.active_key is not None:
            self._stop_level_loops()
            self._stop_hum()
            self.context = "space"
            self.transition_count += 1

    def sync_interior(self) -> None:
        if not self.enabled:
            return
        if self.context != "interior" or self.active_key is not None:
            self._stop_level_loops()
        if self.ship_hum is not None and self.hum_channel is not None:
            if not self.hum_channel.get_busy() or self.hum_channel.get_sound() is not self.ship_hum:
                self.hum_channel.stop()
                self.hum_channel.play(self.ship_hum, loops=-1, fade_ms=620)
                self.hum_channel.set_volume(self._scaled_volume(self.hum_base_volume))
                self.transition_count += 1
        self.context = "interior"

    def sync_surface(self, biome_key: str) -> None:
        if not self.enabled:
            return
        if self.context == "interior":
            self._stop_hum()
        key = biome_key if biome_key in self.surface_sounds else "desert"
        self._play_level(f"surface:{key}", self.surface_sounds.get(key), 0.62)
        self.context = f"surface:{key}"

    def sync_ruin(self, ruin_key: str) -> None:
        if not self.enabled:
            return
        if self.context == "interior":
            self._stop_hum()
        key = ruin_key if ruin_key in self.ruin_sounds else "dungeon"
        self._play_level(f"ruin:{key}", self.ruin_sounds.get(key), 0.58)
        self.context = f"ruin:{key}"

    def sync_surface_view(self, surface) -> None:
        if not self.enabled:
            return
        if getattr(surface, "mode", "surface") == "surface":
            biome = getattr(surface, "biome", {}) or {}
            self.sync_surface(str(biome.get("terrain", "desert")))
        else:
            self.sync_ruin(str(getattr(surface, "current_area", "dungeon")))

    def stop_all(self, fade_ms: int = 160) -> None:
        if not self.enabled:
            return
        self._stop_level_loops(fade_ms)
        self._stop_hum(fade_ms)
        self.context = "stopped"

    def state(self) -> dict:
        return {
            "enabled": self.enabled,
            "context": self.context,
            "active_key": self.active_key,
            "ambient_channels_busy": [bool(ch and ch.get_busy()) for ch in self.channels],
            "hum_busy": bool(self.hum_channel and self.hum_channel.get_busy()),
            "surface_loaded": len(self.surface_sounds),
            "ruins_loaded": len(self.ruin_sounds),
            "hum_loaded": self.ship_hum is not None,
            "transition_count": self.transition_count,
            "load_errors": list(self.load_errors),
        }
