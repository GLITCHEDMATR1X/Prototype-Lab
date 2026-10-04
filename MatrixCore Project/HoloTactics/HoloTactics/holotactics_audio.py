from __future__ import annotations

import math
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from panda3d.core import Filename as PandaFilename
except Exception:  # Panda3D is imported lazily in tests/headless tooling.
    PandaFilename = None

SAMPLE_RATE = 44100
SFX_RELATIVE_DIR = Path("assets") / "sfx"
MUSIC_RELATIVE_DIR = Path("assets") / "music"


@dataclass(frozen=True)
class SfxSpec:
    filename: str
    duration: float
    frequencies: Tuple[float, ...]
    volume: float = 0.28
    sweep: float = 0.0
    noise: float = 0.0


@dataclass(frozen=True)
class MusicSpec:
    filename: str
    duration: float
    root_frequency: float
    volume: float = 0.10
    pulse_rate: float = 0.34
    intervals: Tuple[float, ...] = (1.0, 1.5, 2.0, 3.0)
    shimmer_rate: float = 0.08333333333333333
    pulse_depth: float = 0.30


SFX_CUES: Dict[str, SfxSpec] = {
    "start": SfxSpec("assets/sfx/start_simulation.wav", 0.42, (440.0, 660.0, 880.0), 0.20, 180.0),
    "select": SfxSpec("assets/sfx/select_unit.wav", 0.12, (620.0, 930.0), 0.16, 80.0),
    "move": SfxSpec("assets/sfx/move_unit.wav", 0.18, (330.0, 510.0), 0.18, 120.0),
    "attack": SfxSpec("assets/sfx/attack_pulse.wav", 0.22, (190.0, 420.0, 760.0), 0.26, -140.0, 0.03),
    "enemy_hit": SfxSpec("assets/sfx/enemy_response.wav", 0.24, (135.0, 260.0), 0.23, -90.0, 0.06),
    "patch": SfxSpec("assets/sfx/patch_pulse.wav", 0.30, (520.0, 740.0, 1040.0), 0.18, 140.0),
    "node": SfxSpec("assets/sfx/node_claim.wav", 0.32, (392.0, 784.0, 1176.0), 0.18, 160.0),
    "ability_drop": SfxSpec("assets/sfx/ability_drop.wav", 0.30, (260.0, 520.0, 1040.0), 0.19, 260.0, 0.03),
    "ability_cast": SfxSpec("assets/sfx/ability_cast.wav", 0.38, (180.0, 360.0, 720.0, 1080.0), 0.24, 320.0, 0.04),
    "core": SfxSpec("assets/sfx/core_break.wav", 0.42, (95.0, 180.0, 360.0), 0.30, -110.0, 0.08),
    "extraction": SfxSpec("assets/sfx/extraction_gate.wav", 0.46, (500.0, 750.0, 1000.0), 0.20, 220.0),
    "sector_clear": SfxSpec("assets/sfx/sector_clear.wav", 0.52, (330.0, 495.0, 660.0, 990.0), 0.20, 250.0),
    "expand": SfxSpec("assets/sfx/route_expand.wav", 0.55, (220.0, 440.0, 880.0), 0.22, 420.0),
    "warning": SfxSpec("assets/sfx/system_warning.wav", 0.28, (160.0, 240.0), 0.24, -60.0, 0.04),
    "defeat": SfxSpec("assets/sfx/link_lost.wav", 0.55, (220.0, 165.0, 110.0), 0.26, -180.0, 0.04),
    "blocked": SfxSpec("assets/sfx/blocked_input.wav", 0.10, (150.0, 95.0), 0.18, -30.0, 0.05),
    "toggle": SfxSpec("assets/sfx/sfx_toggle.wav", 0.16, (520.0, 780.0), 0.14, 60.0),
    "music_toggle": SfxSpec("assets/sfx/music_toggle.wav", 0.18, (330.0, 660.0, 990.0), 0.12, 100.0),
}

MUSIC_CUES: Dict[str, MusicSpec] = {
    # Fallback/title ambience retained for compatibility.  Sector music below is
    # deliberately distinct but uses the same restrained HoloTactics palette.
    "holo_ambient": MusicSpec("assets/music/holoverse_ambient_loop.wav", 12.0, 110.0, 0.075, 0.30),
    "sector_1_archive": MusicSpec(
        "assets/music/sector01_archive_gate.wav", 12.0, 98.0, 0.072, 0.25,
        (1.0, 1.5, 2.0, 3.0), 1.0 / 12.0, 0.20,
    ),
    "sector_2_signal": MusicSpec(
        "assets/music/sector02_signal_causeway.wav", 12.0, 123.5, 0.070, 0.50,
        (1.0, 1.25, 2.0, 4.0), 2.0 / 12.0, 0.34,
    ),
    "sector_3_fracture": MusicSpec(
        "assets/music/sector03_fracture_expanse.wav", 12.0, 92.5, 0.068, 0.3333333333333333,
        (1.0, 1.414, 1.75, 2.5), 3.0 / 12.0, 0.42,
    ),
    "sector_4_outer": MusicSpec(
        "assets/music/sector04_outer_signal_grid.wav", 12.0, 82.5, 0.070, 0.4166666666666667,
        (1.0, 2.0, 2.5, 4.0), 2.0 / 12.0, 0.28,
    ),
    "sector_5_horizon": MusicSpec(
        "assets/music/sector05_matrix_horizon.wav", 12.0, 73.5, 0.076, 0.5833333333333334,
        (1.0, 1.5, 2.25, 4.5), 4.0 / 12.0, 0.40,
    ),
}

SECTOR_MUSIC_CUES: Dict[int, str] = {
    1: "sector_1_archive",
    2: "sector_2_signal",
    3: "sector_3_fracture",
    4: "sector_4_outer",
    5: "sector_5_horizon",
}




def _normalized_panda_path_string(path: Path | str) -> str:
    raw = str(path)
    # Panda3D's virtual file system expects /d/... for Windows drive paths;
    # raw D:\... strings can warn and fail inside loadSfx/loadMusic.
    if len(raw) >= 3 and raw[1] == ":" and raw[2] in {"\\", "/"} and raw[0].isalpha():
        tail = raw[3:].replace(chr(92), "/")
        return f"/{raw[0].lower()}/{tail}"
    return raw.replace("\\", "/")


def _loader_audio_path(path: Path | str):
    """Return a Panda3D-safe asset path for SFX/music loading.

    Panda3D reports and may reject raw Windows strings such as
    ``D:\\Apps\\...\\start.wav``. This normalizes them to Panda-style
    paths before the loader sees the asset. POSIX/headless paths are unchanged.
    """
    normalized = _normalized_panda_path_string(path)
    if PandaFilename is not None:
        try:
            return PandaFilename(normalized)
        except Exception:
            pass
    return normalized

def _clip_sample(value: float) -> int:
    return int(max(-1.0, min(1.0, value)) * 32767)


def _envelope(t: float, duration: float) -> float:
    attack = min(0.035, max(0.004, duration * 0.12))
    release = min(0.080, max(0.012, duration * 0.22))
    if t < attack:
        return t / attack
    if t > duration - release:
        return max(0.0, (duration - t) / release)
    return 1.0


def _music_envelope(t: float, duration: float) -> float:
    fade = min(1.2, max(0.20, duration * 0.10))
    if t < fade:
        return t / fade
    if t > duration - fade:
        return max(0.0, (duration - t) / fade)
    return 1.0


def _pseudo_noise(index: int) -> float:
    # Deterministic tiny crackle without needing random state or external assets.
    return math.sin(index * 12.9898 + 78.233) * 43758.5453 % 1.0 * 2.0 - 1.0


def _write_tone(path: Path, spec: SfxSpec) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = max(1, int(SAMPLE_RATE * spec.duration))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for i in range(samples):
            t = i / SAMPLE_RATE
            env = _envelope(t, spec.duration)
            value = 0.0
            for idx, base_freq in enumerate(spec.frequencies):
                sweep_freq = base_freq + spec.sweep * (t / max(spec.duration, 0.001))
                value += math.sin(math.tau * sweep_freq * t + idx * 0.35) / len(spec.frequencies)
            if spec.noise:
                value += _pseudo_noise(i) * spec.noise
            value *= spec.volume * env
            frames.extend(_clip_sample(value).to_bytes(2, byteorder="little", signed=True))
        wav.writeframes(bytes(frames))


def _loop_frequency(frequency: float, duration: float) -> float:
    """Quantize a frequency to an integer number of cycles per loop."""
    cycles = max(1, round(frequency * duration))
    return cycles / duration


def _write_music_loop(path: Path, spec: MusicSpec) -> None:
    """Write a deterministic loop whose oscillator phases close at the seam.

    Panda3D's reliable looping path is AudioSound.setLoop(True).  Making every
    oscillator and modulation rate complete an integer number of cycles inside
    the WAV keeps our generated sector beds compatible with that method without
    requiring a frame-timed restart or a hidden crossfade task.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = max(1, int(SAMPLE_RATE * spec.duration))
    root = spec.root_frequency
    pulse_rate = _loop_frequency(spec.pulse_rate, spec.duration)
    shimmer_rate = _loop_frequency(spec.shimmer_rate, spec.duration)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for i in range(samples):
            t = i / SAMPLE_RATE
            pulse_phase = math.tau * pulse_rate * t
            slow_pulse = (1.0 - spec.pulse_depth) + spec.pulse_depth * (0.5 + 0.5 * math.sin(pulse_phase))
            shimmer = 0.5 + 0.5 * math.sin(math.tau * shimmer_rate * t + 1.2)
            value = 0.0
            for idx, ratio in enumerate(spec.intervals):
                freq = _loop_frequency(root * ratio, spec.duration)
                phase = idx * 0.9
                value += math.sin(math.tau * freq * t + phase) * (0.42 / (idx + 1))
            high = _loop_frequency(root * 6.0, spec.duration)
            value += math.sin(math.tau * high * t) * 0.018 * shimmer
            value *= spec.volume * slow_pulse
            frames.extend(_clip_sample(value).to_bytes(2, byteorder="little", signed=True))
        wav.writeframes(bytes(frames))


def ensure_sfx_assets(base_dir: Path | str) -> List[Path]:
    base_path = Path(base_dir)
    created_or_existing: List[Path] = []
    for spec in SFX_CUES.values():
        path = base_path / spec.filename
        if not path.exists() or path.stat().st_size <= 44:
            _write_tone(path, spec)
        created_or_existing.append(path)
    return created_or_existing


def ensure_music_assets(base_dir: Path | str) -> List[Path]:
    base_path = Path(base_dir)
    created_or_existing: List[Path] = []
    for spec in MUSIC_CUES.values():
        path = base_path / spec.filename
        if not path.exists() or path.stat().st_size <= 44:
            _write_music_loop(path, spec)
        created_or_existing.append(path)
    return created_or_existing


def ensure_audio_assets(base_dir: Path | str) -> List[Path]:
    return [*ensure_sfx_assets(base_dir), *ensure_music_assets(base_dir)]


def _validate_wav(path: Path, label: str, expected_rate: int = SAMPLE_RATE) -> List[str]:
    issues: List[str] = []
    if not path.exists():
        return [f"missing:{label}:{path.name}"]
    if path.stat().st_size <= 128:
        return [f"too_small:{label}:{path.name}"]
    try:
        with wave.open(str(path), "rb") as wav:
            if wav.getframerate() != expected_rate:
                issues.append(f"bad_rate:{label}:{wav.getframerate()}")
            if wav.getnchannels() != 1:
                issues.append(f"bad_channels:{label}:{wav.getnchannels()}")
            if wav.getnframes() <= 0:
                issues.append(f"empty:{label}:{path.name}")
    except wave.Error as exc:
        issues.append(f"bad_wav:{label}:{exc}")
    return issues


def validate_sfx_assets(base_dir: Path | str) -> List[str]:
    issues: List[str] = []
    base_path = Path(base_dir)
    for cue, spec in SFX_CUES.items():
        issues.extend(_validate_wav(base_path / spec.filename, cue))
    return issues


def validate_music_assets(base_dir: Path | str) -> List[str]:
    issues: List[str] = []
    base_path = Path(base_dir)
    for cue, spec in MUSIC_CUES.items():
        issues.extend(_validate_wav(base_path / spec.filename, cue))
    return issues


def validate_audio_assets(base_dir: Path | str) -> List[str]:
    return [*validate_sfx_assets(base_dir), *validate_music_assets(base_dir)]


class HoloSfx:
    """Small optional audio manager.

    The game must still run when the active Panda3D runtime uses the null audio
    backend, when running screenshot smoke tests, or when a sound device is absent.
    """

    def __init__(
        self,
        loader,
        base_dir: Path | str,
        muted: bool = False,
        music_muted: bool = False,
        volume: float = 0.72,
        music_volume: float = 0.34,
    ) -> None:
        self.loader = loader
        self.base_dir = Path(base_dir)
        self.muted = muted
        self.music_muted = music_muted
        self.volume = max(0.0, min(1.0, volume))
        self.music_volume = max(0.0, min(1.0, music_volume))
        self.sounds: Dict[str, object] = {}
        self.music: Dict[str, object] = {}
        self.active_music_key: str | None = None
        ensure_audio_assets(self.base_dir)
        self._load_all()

    def _load_all(self) -> None:
        for cue, spec in SFX_CUES.items():
            path = self.base_dir / spec.filename
            try:
                sound = self.loader.loadSfx(_loader_audio_path(path))
                if sound is None:
                    continue
                if hasattr(sound, "setVolume"):
                    sound.setVolume(self.volume)
                self.sounds[cue] = sound
            except Exception:
                continue
        for cue, spec in MUSIC_CUES.items():
            path = self.base_dir / spec.filename
            try:
                load_music = getattr(self.loader, "loadMusic", None)
                track = load_music(_loader_audio_path(path)) if callable(load_music) else self.loader.loadSfx(_loader_audio_path(path))
                if track is None:
                    continue
                if hasattr(track, "setVolume"):
                    track.setVolume(self.music_volume)
                if hasattr(track, "setLoop"):
                    track.setLoop(True)
                self.music[cue] = track
            except Exception:
                continue

    def play(self, cue: str) -> bool:
        if self.muted:
            return False
        sound = self.sounds.get(cue)
        if sound is None:
            return False
        try:
            sound.play()
            return True
        except Exception:
            return False

    def play_music(self, cue: str = "holo_ambient") -> bool:
        # One music authority at a time.  Replaying an already-active track can
        # stutter in Panda3D, while starting a new one without stopping the old
        # track stacks loops.  Treat a same-cue request as a no-op and stop the
        # previous cue before switching sectors.
        previous_key = self.active_music_key
        self.active_music_key = cue
        if self.music_muted:
            return False
        track = self.music.get(cue)
        if track is None:
            return False
        if previous_key == cue:
            try:
                if hasattr(track, "status") and hasattr(track, "PLAYING") and track.status() == track.PLAYING:
                    return True
            except Exception:
                pass
        if previous_key and previous_key != cue:
            previous = self.music.get(previous_key)
            if previous is not None:
                try:
                    previous.stop()
                except Exception:
                    pass
        try:
            if hasattr(track, "setLoop"):
                track.setLoop(True)
            if hasattr(track, "setVolume"):
                track.setVolume(self.music_volume)
            track.play()
            return True
        except Exception:
            return False

    def stop_music(self) -> None:
        for track in self.music.values():
            try:
                track.stop()
            except Exception:
                pass

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        if not self.muted:
            self.play("toggle")
        return self.muted

    def toggle_music(self) -> bool:
        self.music_muted = not self.music_muted
        if self.music_muted:
            self.stop_music()
        else:
            self.play("music_toggle")
            self.play_music(self.active_music_key or "holo_ambient")
        return self.music_muted

    def status_label(self) -> str:
        return "OFF" if self.muted else "ON"

    def music_status_label(self) -> str:
        return "OFF" if self.music_muted else "ON"
