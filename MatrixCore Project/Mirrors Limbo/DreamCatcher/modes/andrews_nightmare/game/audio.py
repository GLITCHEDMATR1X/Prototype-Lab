from __future__ import annotations

import math
from pathlib import Path

from panda3d.core import ClockObject, Filename


class NightmareAudio:
    """Soundtrack/SFX owner for Andrew's Nightmare.

    Pass 14 ships with original procedural ambient WAV loops and authored SFX.
    User tracks can still be added to assets/audio/music.  The manager owns the
    active loop, performs the datamosh pitch/fade, and advances to a different
    track after relocation.  Missing or removed audio remains safe.
    """

    MUSIC_EXTS = {".wav", ".ogg", ".mp3", ".flac"}
    SFX_EXTS = {".wav", ".ogg", ".mp3"}

    def __init__(self, base, project_root: Path, enabled: bool = True, playlist_seed: int = 0):
        self.base = base
        self.project_root = Path(project_root)
        self.enabled = bool(enabled)
        self._playlist_seed = int(playlist_seed)
        self.music_dir = self.project_root / "assets" / "audio" / "music"
        self.sfx_dir = self.project_root / "assets" / "audio" / "sfx"
        self.music_dir.mkdir(parents=True, exist_ok=True)
        self.sfx_dir.mkdir(parents=True, exist_ok=True)

        self.track_paths = sorted(
            p for p in self.music_dir.iterdir()
            if p.is_file() and p.suffix.lower() in self.MUSIC_EXTS
        )
        self._sfx_paths = {
            p.stem.lower(): p for p in self.sfx_dir.iterdir()
            if p.is_file() and p.suffix.lower() in self.SFX_EXTS
        }
        self._sfx_cache = {}
        self.current = None
        self.current_path: Path | None = None
        self._track_index = -1
        self._mosh_active = False
        self._mosh_started = 0.0
        self._mosh_duration = 1.18
        self._fade_in = 0.0
        self._null_layer = False
        self._base_volume = 0.72
        self._instance_number = 0
        self.base.taskMgr.add(self._update, "nightmare-audio", sort=70)

    @property
    def track_count(self) -> int:
        return len(self.track_paths)

    def _load_track(self, path: Path):
        if not self.enabled:
            return None
        try:
            snd = self.base.loader.loadSfx(Filename.fromOsSpecific(str(path)))
            if snd is None:
                return None
            snd.setLoop(True)
            snd.setVolume(0.0)
            snd.setPlayRate(1.0)
            return snd
        except Exception as exc:
            print(f"AUDIO_TRACK_SKIPPED={path.name!r} ERROR={exc!r}")
            return None

    def start_instance(self, instance_number: int = 0):
        self._instance_number = int(instance_number)
        if self._null_layer or not self.track_paths or not self.enabled:
            return False
        # Deterministic cycle through the user's playlist.  Immediate repeats are
        # impossible when two or more tracks are present.
        if self._track_index < 0:
            self._track_index = (self._playlist_seed + self._instance_number) % len(self.track_paths)
        path = self.track_paths[self._track_index]
        snd = self._load_track(path)
        if snd is None:
            return False
        self.stop_current()
        self.current = snd
        self.current_path = path
        self.current.play()
        self._fade_in = 1.0
        return True

    def advance_instance(self, instance_number: int):
        self._instance_number = int(instance_number)
        if self._null_layer or not self.enabled or not self.track_paths:
            self.stop_current()
            return False
        if len(self.track_paths) > 1:
            self._track_index = (self._track_index + 1) % len(self.track_paths)
        else:
            self._track_index = 0
        return self.start_instance(self._instance_number)

    def begin_datamosh(self, duration: float = 1.18, play_disturb_sfx: bool = True):
        if self._null_layer:
            return
        self._mosh_active = True
        self._mosh_started = ClockObject.getGlobalClock().getFrameTime()
        self._mosh_duration = max(0.25, float(duration))
        if play_disturb_sfx:
            self.play_sfx("sleeper_disturb")

    def finish_datamosh(self, instance_number: int, advance_track: bool = True):
        self._mosh_active = False
        if self.current:
            try:
                self.current.setPlayRate(1.0)
                self.current.setVolume(0.0)
            except Exception:
                pass
        if advance_track:
            self.advance_instance(instance_number)
        elif self.current:
            self._fade_in = 1.0

    def enter_null_layer(self):
        self._null_layer = True
        self._mosh_active = False
        self.stop_current()

    def stop_current(self):
        if self.current is not None:
            try:
                self.current.stop()
            except Exception:
                pass
        self.current = None
        self.current_path = None
        self._fade_in = 0.0

    def play_sfx(self, name: str, volume: float = 0.85):
        if not self.enabled or self._null_layer:
            return False
        key = str(name).lower()
        path = self._sfx_paths.get(key)
        if path is None:
            return False
        snd = self._sfx_cache.get(key)
        if snd is None:
            try:
                snd = self.base.loader.loadSfx(Filename.fromOsSpecific(str(path)))
                self._sfx_cache[key] = snd
            except Exception:
                return False
        try:
            snd.setLoop(False)
            snd.setPlayRate(1.0)
            snd.setVolume(max(0.0, min(1.0, float(volume))))
            snd.play()
            return True
        except Exception:
            return False

    def _update(self, task):
        if self._null_layer or self.current is None:
            return task.cont
        now = ClockObject.getGlobalClock().getFrameTime()
        try:
            if self._mosh_active:
                t = max(0.0, min(1.0, (now - self._mosh_started) / self._mosh_duration))
                # The tune physically sags and wobbles instead of merely having a
                # glitch SFX placed over it.  Playback rate changes pitch and tempo.
                wobble = math.sin(now * 8.1) * 0.032 * (0.25 + 0.75 * t)
                rate = max(0.62, 1.0 - 0.28 * t + wobble)
                self.current.setPlayRate(rate)
                self.current.setVolume(self._base_volume * (1.0 - t) ** 1.35)
            elif self._fade_in > 0.0:
                self._fade_in = max(0.0, self._fade_in - min(0.05, ClockObject.getGlobalClock().getDt()) / 1.25)
                self.current.setPlayRate(1.0)
                self.current.setVolume(self._base_volume * (1.0 - self._fade_in))
            else:
                self.current.setPlayRate(1.0)
                self.current.setVolume(self._base_volume)
        except Exception:
            pass
        return task.cont
