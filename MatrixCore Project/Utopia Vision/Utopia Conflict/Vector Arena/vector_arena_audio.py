"""Local audio runtime for Vector Arena.

Designed to work both in the standalone ShowBase and when the arena is mounted
inside HoloVerse.  It never assumes ownership of the host's global music; all
Vector Arena music, ambience and SFX are loaded as local sounds and explicitly
stopped on exit.
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    from direct.showbase.Audio3DManager import Audio3DManager
except Exception:  # pragma: no cover - keeps static/contract tooling safe
    Audio3DManager = None

LOCAL_POOL_SIZES = {"pulse_rifle": 4, "heat_vent": 3, "player_hit": 2}

POSITIONAL_KEYS = {
    "enemy_hit", "enemy_destroyed", "enemy_spawn",
    "enemy_stalker", "enemy_brute", "enemy_sentry", "enemy_wraith", "enemy_guardian",
    "breach_spawn", "breach_hit", "breach_sealed",
    "gate_charge", "guardian_charge", "guardian_slam", "hazard_warning", "hazard_discharge",
}

DEFAULT_FILES = {
    "pulse_rifle": "pulse_rifle.wav",
    "repulsor_blast": "repulsor_blast.wav",
    "heat_vent": "heat_vent.wav",
    "enemy_hit": "enemy_hit.wav",
    "enemy_destroyed": "enemy_destroyed.wav",
    "wave_start": "wave_start.wav",
    "player_hit": "player_hit.wav",
    "enemy_spawn": "enemy_spawn.wav",
    "enemy_stalker": "enemy_stalker.wav",
    "enemy_brute": "enemy_brute.wav",
    "enemy_sentry": "enemy_sentry.wav",
    "enemy_wraith": "enemy_wraith.wav",
    "enemy_guardian": "enemy_guardian.wav",
    "weapon_upgrade": "weapon_upgrade.wav",
    "overheat_warning": "overheat_warning.wav",
    "low_health": "low_health.wav",
    "player_reboot": "player_reboot.wav",
    "ui_toggle": "ui_toggle.wav",
    "breach_spawn": "breach_spawn.wav",
    "breach_hit": "breach_hit.wav",
    "breach_sealed": "breach_sealed.wav",
    "combo_surge": "combo_surge.wav",
    "horde_alarm": "horde_alarm.wav",
    "guardian_alarm": "guardian_alarm.wav",
    "arena_reconstruct": "arena_reconstruct.wav",
    "gate_charge": "gate_charge.wav",
    "flank_alarm": "flank_alarm.wav",
    "guardian_charge": "guardian_charge.wav",
    "guardian_slam": "guardian_slam.wav",
    "hazard_warning": "hazard_warning.wav",
    "hazard_discharge": "hazard_discharge.wav",
    "upgrade_offer": "upgrade_offer.wav",
    "upgrade_select": "upgrade_select.wav",
    "mutation_shift": "mutation_shift.wav",
}

DEFAULT_VOLUMES = {
    "pulse_rifle": .62, "repulsor_blast": .82, "heat_vent": .50,
    "enemy_hit": .46, "enemy_destroyed": .78, "wave_start": .62,
    "player_hit": .70, "enemy_spawn": .46, "enemy_stalker": .42,
    "enemy_brute": .58, "enemy_sentry": .44, "enemy_wraith": .48,
    "enemy_guardian": .68, "weapon_upgrade": .78, "overheat_warning": .62,
    "low_health": .58, "player_reboot": .78, "ui_toggle": .34,
    "breach_spawn": .58, "breach_hit": .42, "breach_sealed": .78,
    "combo_surge": .62, "horde_alarm": .72, "guardian_alarm": .84, "arena_reconstruct": .78,
    "gate_charge": .48, "flank_alarm": .62, "guardian_charge": .78,
    "guardian_slam": .88, "hazard_warning": .56, "hazard_discharge": .76,
    "upgrade_offer": .68, "upgrade_select": .82, "mutation_shift": .72,
}

DEFAULT_INTERVALS = {
    "pulse_rifle": .055, "repulsor_blast": .35, "heat_vent": .09,
    "enemy_hit": .035, "enemy_destroyed": .08, "wave_start": .45,
    "player_hit": .18, "enemy_spawn": .16, "enemy_stalker": .18,
    "enemy_brute": .18, "enemy_sentry": .18, "enemy_wraith": .18,
    "enemy_guardian": .28, "weapon_upgrade": .9, "overheat_warning": .8,
    "low_health": 1.5, "player_reboot": 1.0, "ui_toggle": .10,
    "breach_spawn": .55, "breach_hit": .08, "breach_sealed": .40,
    "combo_surge": .85, "horde_alarm": .9, "guardian_alarm": 1.2, "arena_reconstruct": 1.0,
    "gate_charge": .12, "flank_alarm": .85, "guardian_charge": .70,
    "guardian_slam": .65, "hazard_warning": .55, "hazard_discharge": .20,
    "upgrade_offer": .90, "upgrade_select": .24, "mutation_shift": .80,
}


def _clamp(value, low=0.0, high=1.0):
    try:
        value = float(value)
    except Exception:
        value = low
    return max(low, min(high, value))


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


class VectorArenaAudioRuntime:
    def __init__(self, host, folder: Path):
        self.host = host
        self.folder = Path(folder)
        self.loader = getattr(host, "loader", None)
        self.camera = getattr(host, "camera", None)
        self.render = getattr(host, "render", None)
        self.elapsed = 0.0
        self.config = _read_json(self.folder / "vector_arena_config.json")
        self.profile = _read_json(self.folder / "audio_profile.json")
        audio = self.config.get("audio", {}) if isinstance(self.config.get("audio", {}), dict) else {}
        self.enabled = bool(audio.get("enabled", True))
        self.sfx_enabled = self.enabled and bool(audio.get("sfx_enabled", True))
        self.music_enabled = self.enabled and bool(audio.get("music_enabled", True))
        self.ambience_enabled = self.enabled and bool(audio.get("ambience_enabled", True))
        self.transition_enabled = self.enabled and bool(audio.get("transition_enabled", True))
        self.spatial_enabled = self.sfx_enabled and bool(audio.get("spatial_sfx_enabled", True))
        self.master = _clamp(audio.get("master_volume", 1.0))
        self.sfx_master = _clamp(audio.get("sfx_master_volume", .86))
        self.music_volume = _clamp(audio.get("music_volume", self.profile.get("music_volume", .62)))
        self.ambience_volume = _clamp(audio.get("ambience_volume", self.profile.get("air_volume", .22)))
        self.transition_volume = _clamp(audio.get("transition_volume", self.profile.get("transition_sfx_volume", .70)))
        self.sfx_volumes = dict(DEFAULT_VOLUMES)
        if isinstance(audio.get("sfx_volumes"), dict):
            for key, value in audio["sfx_volumes"].items():
                self.sfx_volumes[str(key)] = _clamp(value)
        self.min_intervals = dict(DEFAULT_INTERVALS)
        self.last_play = {}
        self.sfx = {}
        self.local_pools = {}
        self.local_cursor = {}
        self.positional_pools = {}
        self.positional_cursor = {}
        self.music = []
        self.music_index = 0
        self.music_elapsed = 0.0
        self.music_rotation = max(8.0, float(self.profile.get("music_rotation_seconds", 60.0) or 60.0))
        self.crossfade_duration = max(.25, float(audio.get("music_crossfade_seconds", 1.5) or 1.5))
        self.crossfade_elapsed = 0.0
        self.crossfade_from = None
        self.crossfade_to = None
        self.ambience = []
        self.transition_enter = None
        self.audio3d = None
        self._audio3d_task = None
        self.loaded_count = 0
        self._active_loops = []

    def _asset(self, category: str, name: str) -> Path | None:
        if not name:
            return None
        candidates = [
            self.folder / "assets" / "audio" / category / name,
            self.folder / "assets" / "audio" / category / "overrides" / name,
        ]
        if category == "sfx":
            candidates.append(self.folder / "assets" / "sfx" / name)
        for path in candidates:
            if path.is_file():
                return path
        return None

    @staticmethod
    def _path(path: Path) -> str:
        return str(path.resolve()).replace("\\", "/")

    def load(self):
        if not self.enabled or self.loader is None:
            return
        if self.spatial_enabled and Audio3DManager is not None:
            try:
                managers = getattr(self.host, "sfxManagerList", [])
                if managers and self.camera is not None:
                    from direct.task.TaskManagerGlobal import taskMgr
                    self.audio3d = Audio3DManager(managers[0], self.camera, root=self.render)
                    self.audio3d.setDropOffFactor(.75)
                    # Remember only the update task this manager created: the host (eg. Utopia
                    # Vision) runs its own Audio3DManager task under the same name. Match by the
                    # bound manager, not id(): Panda may hand back fresh task wrappers.
                    self._audio3d_task = next((t for t in taskMgr.getTasksNamed("Audio3DManager-updateTask")
                                               if getattr(t.getFunction(), "__self__", None) is self.audio3d), None)
            except Exception:
                self.audio3d = None

        if self.sfx_enabled:
            for key, filename in DEFAULT_FILES.items():
                path = self._asset("sfx", filename)
                if path is None:
                    continue
                try:
                    sound = self.loader.loadSfx(self._path(path))
                    sound.setVolume(self.master * self.sfx_master * self.sfx_volumes.get(key, .7))
                    self.sfx[key] = sound
                    self.loaded_count += 1
                    pool_size = int(LOCAL_POOL_SIZES.get(key, 0))
                    if pool_size > 1:
                        pool = [sound]
                        for _ in range(pool_size - 1):
                            try:
                                extra = self.loader.loadSfx(self._path(path))
                                extra.setVolume(self.master * self.sfx_master * self.sfx_volumes.get(key, .7))
                                pool.append(extra)
                                self.loaded_count += 1
                            except Exception:
                                break
                        self.local_pools[key] = pool
                        self.local_cursor[key] = 0
                except Exception:
                    pass
                if key in POSITIONAL_KEYS and self.audio3d is not None:
                    pool = []
                    for _ in range(3):
                        try:
                            sound3d = self.audio3d.loadSfx(self._path(path))
                            sound3d.setVolume(self.master * self.sfx_master * self.sfx_volumes.get(key, .7))
                            self.audio3d.setSoundMinDistance(sound3d, 7.0)
                            self.audio3d.setSoundMaxDistance(sound3d, 155.0)
                            pool.append(sound3d)
                            self.loaded_count += 1
                        except Exception:
                            break
                    if pool:
                        self.positional_pools[key] = pool
                        self.positional_cursor[key] = 0

        if self.music_enabled:
            names = self.profile.get("music_variants", [])
            if not isinstance(names, list): names = []
            for name in names:
                path = self._asset("music", str(name))
                if path is None:
                    continue
                try:
                    sound = self.loader.loadSfx(self._path(path))
                    sound.setLoop(True)
                    sound.setVolume(0.0)
                    self.music.append(sound)
                    self.loaded_count += 1
                except Exception:
                    pass

        if self.ambience_enabled:
            names = self.profile.get("ambience_loops", [])
            if not isinstance(names, list) or not names:
                names = [self.profile.get("air_loop", "arena_void_loop.wav")]
            for name in names:
                path = self._asset("ambience", str(name))
                if path is None:
                    continue
                try:
                    sound = self.loader.loadSfx(self._path(path))
                    sound.setLoop(True)
                    sound.setVolume(self.master * self.ambience_volume / max(1, len(names)))
                    self.ambience.append(sound)
                    self.loaded_count += 1
                except Exception:
                    pass

        if self.transition_enabled:
            name = str(self.profile.get("transition_enter_sfx", self.profile.get("transition_sfx", "dimension_enter.wav")))
            path = self._asset("transition", name)
            if path is not None:
                try:
                    self.transition_enter = self.loader.loadSfx(self._path(path))
                    self.transition_enter.setVolume(self.master * self.transition_volume)
                    self.loaded_count += 1
                except Exception:
                    self.transition_enter = None

    def start(self):
        if self.transition_enter is not None:
            try: self.transition_enter.play()
            except Exception: pass
        for sound in self.ambience:
            try: sound.play()
            except Exception: pass
        if self.music:
            self.music_index = 0
            self.music_elapsed = 0.0
            try:
                self.music[0].setVolume(self.master * self.music_volume)
                self.music[0].play()
            except Exception:
                pass

    def _begin_crossfade(self):
        if len(self.music) < 2 or self.crossfade_to is not None:
            return
        nxt = (self.music_index + 1) % len(self.music)
        self.crossfade_from = self.music_index
        self.crossfade_to = nxt
        self.crossfade_elapsed = 0.0
        try:
            self.music[nxt].setVolume(0.0)
            self.music[nxt].play()
        except Exception:
            self.crossfade_from = self.crossfade_to = None

    def update(self, dt: float):
        self.elapsed += max(0.0, float(dt))
        if not self.music:
            return
        self.music_elapsed += max(0.0, float(dt))
        if self.crossfade_to is None and self.music_elapsed >= self.music_rotation:
            self._begin_crossfade()
        if self.crossfade_to is not None:
            self.crossfade_elapsed += max(0.0, float(dt))
            alpha = _clamp(self.crossfade_elapsed / self.crossfade_duration)
            full = self.master * self.music_volume
            try: self.music[self.crossfade_from].setVolume(full * (1.0 - alpha))
            except Exception: pass
            try: self.music[self.crossfade_to].setVolume(full * alpha)
            except Exception: pass
            if alpha >= 1.0:
                try: self.music[self.crossfade_from].stop()
                except Exception: pass
                self.music_index = self.crossfade_to
                self.music_elapsed = 0.0
                self.crossfade_from = self.crossfade_to = None

    def play(self, key: str, pos=None) -> bool:
        if not self.sfx_enabled:
            return False
        key = str(key)
        interval = float(self.min_intervals.get(key, .04))
        if self.elapsed - float(self.last_play.get(key, -999.0)) < interval:
            return False
        self.last_play[key] = self.elapsed
        if pos is not None and key in self.positional_pools:
            pool = self.positional_pools[key]
            idx = self.positional_cursor.get(key, 0) % len(pool)
            self.positional_cursor[key] = (idx + 1) % len(pool)
            sound = pool[idx]
            try:
                sound.set3dAttributes(float(pos.x), float(pos.y), float(pos.z), 0.0, 0.0, 0.0)
                sound.play()
                return True
            except Exception:
                pass
        if key in self.local_pools:
            pool = self.local_pools[key]
            idx = self.local_cursor.get(key, 0) % len(pool)
            self.local_cursor[key] = (idx + 1) % len(pool)
            try:
                pool[idx].play()
                return True
            except Exception:
                pass
        sound = self.sfx.get(key)
        if sound is not None:
            try:
                sound.play()
                return True
            except Exception:
                pass
        return False

    def start_positional_loop(self, filename: str, node, volume=.35):
        if not self.spatial_enabled or self.audio3d is None or node is None:
            return None
        path = self._asset("sfx", filename)
        if path is None:
            return None
        try:
            sound = self.audio3d.loadSfx(self._path(path))
            sound.setLoop(True)
            sound.setVolume(self.master * self.sfx_master * _clamp(volume))
            self.audio3d.setSoundMinDistance(sound, 9.0)
            self.audio3d.setSoundMaxDistance(sound, 140.0)
            self.audio3d.attachSoundToObject(sound, node)
            sound.play()
            self._active_loops.append(sound)
            self.loaded_count += 1
            return sound
        except Exception:
            return None

    def stop_loop(self, sound):
        if sound is None:
            return
        try: sound.stop()
        except Exception: pass
        if self.audio3d is not None:
            try: self.audio3d.detachSound(sound)
            except Exception: pass
        if sound in self._active_loops:
            self._active_loops.remove(sound)

    def stop(self):
        for sound in list(self._active_loops):
            self.stop_loop(sound)
        local_extra = [sound for pool in self.local_pools.values() for sound in pool]
        for collection in (self.sfx.values(), local_extra, self.music, self.ambience, [self.transition_enter] if self.transition_enter else []):
            for sound in list(collection):
                if sound is None: continue
                try: sound.stop()
                except Exception: pass
        for pool in self.positional_pools.values():
            for sound in pool:
                try: sound.stop()
                except Exception: pass
        if self.audio3d is not None:
            # Never call Audio3DManager.disable(): it removes every task named
            # "Audio3DManager-updateTask", including the host's own spatial-audio task.
            try:
                for owner in list(self.audio3d.sound_dict.keys()):
                    for sound in list(self.audio3d.sound_dict.get(owner, [])):
                        self.audio3d.detachSound(sound)
            except Exception:
                pass
            task = getattr(self, "_audio3d_task", None)
            if task is not None:
                try:
                    from direct.task.TaskManagerGlobal import taskMgr
                    taskMgr.remove(task)
                except Exception:
                    pass
            self._audio3d_task = None
        self.audio3d = None
        self.sfx.clear(); self.local_pools.clear(); self.music.clear(); self.ambience.clear(); self.positional_pools.clear(); self._active_loops.clear()

    def stats(self) -> dict:
        return {
            "audio_loaded": int(self.loaded_count),
            "sfx_events": len(self.sfx),
            "local_overlap_pools": len(self.local_pools),
            "positional_event_types": len(self.positional_pools),
            "music_tracks": len(self.music),
            "ambience_loops": len(self.ambience),
            "spatial_enabled": bool(self.audio3d is not None),
        }
