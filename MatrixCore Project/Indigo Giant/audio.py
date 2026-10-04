"""Pass 40 — sound for The Indigo Giant: 3D sound effects, ambience and music.

FILES (everything is replaceable — see audio/README_AUDIO.txt)
    audio/sfx/<event>_NN.wav|ogg|flac|mp3     one or more variants per event; a random one plays
    audio/music/ambient_NN.*                   ambient cues, played one at a time with quiet gaps
    audio/music/battle_NN.*                    battle loop, faded in/out with the fighting
    audio/music/stinger_<name>.*               one-shot cues (landmark, red_return, ko)
    audio/audio_manifest.json                  per-event distance / volume / pitch tuning (optional)
    audio/audio_settings.json                  master / music / sfx / ambience volumes (optional)

3D: sound effects are positioned in the world and heard from the camera, fading with
distance (OpenAL inverse-distance with a per-event reference and max distance).  OpenAL
only positions MONO files; stereo files still play, just without direction or falloff.

A missing file never breaks the game: that event is simply silent (listed once in the log).
Keys: M mutes / unmutes the music.
"""
from __future__ import annotations

import json
import math
import random
from collections import Counter
from pathlib import Path

from panda3d.core import AudioSound, Filename, Point3

AUDIO_EXTS = ('.ogg', '.wav', '.flac', '.mp3')

# event: min_distance (full volume inside), max_distance (silent beyond), volume, pitch variation,
#        voices (simultaneous copies per file), spatial (False = plays at the listener)
DEFAULT_MANIFEST = {
    'footstep_human':   {'min': 6.0,   'max': 45.0,  'volume': 0.55, 'pitch': 0.08, 'voices': 3},
    'footstep_giant':   {'min': 30.0,  'max': 420.0, 'volume': 0.95, 'pitch': 0.06, 'voices': 3},
    'footstep_red':     {'min': 30.0,  'max': 480.0, 'volume': 1.0,  'pitch': 0.06, 'voices': 3},
    'land_human':       {'min': 6.0,   'max': 45.0,  'volume': 0.7,  'pitch': 0.06, 'voices': 1},
    'land_giant':       {'min': 35.0,  'max': 480.0, 'volume': 1.0,  'pitch': 0.05, 'voices': 1},
    'kneel_giant':      {'min': 30.0,  'max': 400.0, 'volume': 0.9,  'pitch': 0.05, 'voices': 1},
    'stand_giant':      {'min': 30.0,  'max': 300.0, 'volume': 0.6,  'pitch': 0.05, 'voices': 1},
    'stomp_red':        {'min': 35.0,  'max': 500.0, 'volume': 1.0,  'pitch': 0.05, 'voices': 2},
    'roar_red_hunt':    {'min': 60.0,  'max': 900.0, 'volume': 1.0,  'pitch': 0.05, 'voices': 1},
    'roar_red_scared':  {'min': 60.0,  'max': 900.0, 'volume': 1.0,  'pitch': 0.05, 'voices': 1},
    'roar_red_ko':      {'min': 60.0,  'max': 900.0, 'volume': 1.0,  'pitch': 0.03, 'voices': 1},
    'roar_red_return':  {'min': 150.0, 'max': 1500.0, 'volume': 0.9, 'pitch': 0.03, 'voices': 1},
    'roar_red_heave':   {'min': 40.0,  'max': 500.0, 'volume': 0.9,  'pitch': 0.08, 'voices': 2},
    'call_indigo':      {'min': 60.0,  'max': 1000.0, 'volume': 0.9, 'pitch': 0.03, 'voices': 1},
    'hum_indigo_sense': {'min': 40.0,  'max': 400.0, 'volume': 0.6,  'pitch': 0.03, 'voices': 1},
    'gesture_come':     {'min': 8.0,   'max': 80.0,  'volume': 0.5,  'pitch': 0.02, 'voices': 1},
    'gesture_stay':     {'min': 8.0,   'max': 80.0,  'volume': 0.5,  'pitch': 0.02, 'voices': 1},
    'gesture_shade':    {'min': 8.0,   'max': 80.0,  'volume': 0.5,  'pitch': 0.02, 'voices': 1},
    'gesture_lift':     {'min': 8.0,   'max': 80.0,  'volume': 0.5,  'pitch': 0.02, 'voices': 1},
    'gesture_goto':     {'min': 8.0,   'max': 80.0,  'volume': 0.5,  'pitch': 0.02, 'voices': 1},
    'whistle':          {'min': 20.0,  'max': 600.0, 'volume': 0.8,  'pitch': 0.03, 'voices': 1},
    'punch_swing':      {'min': 25.0,  'max': 250.0, 'volume': 0.7,  'pitch': 0.1,  'voices': 2},
    'punch_hit':        {'min': 35.0,  'max': 450.0, 'volume': 1.0,  'pitch': 0.08, 'voices': 2},
    'branch_smash':     {'min': 10.0,  'max': 120.0, 'volume': 0.8,  'pitch': 0.08, 'voices': 2},
    'dig':              {'min': 5.0,   'max': 40.0,  'volume': 0.7,  'pitch': 0.08, 'voices': 1},
    'eat':              {'min': 5.0,   'max': 30.0,  'volume': 0.7,  'pitch': 0.08, 'voices': 1},
    'patch':            {'min': 5.0,   'max': 40.0,  'volume': 0.7,  'pitch': 0.05, 'voices': 1},
    'shell_enter':      {'min': 6.0,   'max': 60.0,  'volume': 0.7,  'pitch': 0.05, 'voices': 1},
    'shell_exit':       {'min': 6.0,   'max': 60.0,  'volume': 0.7,  'pitch': 0.05, 'voices': 1},
    'shell_creak':      {'min': 12.0,  'max': 200.0, 'volume': 0.9,  'pitch': 0.1,  'voices': 2},
    'shell_flip':       {'min': 20.0,  'max': 300.0, 'volume': 1.0,  'pitch': 0.05, 'voices': 1},
    'shell_lift':       {'min': 20.0,  'max': 250.0, 'volume': 0.8,  'pitch': 0.05, 'voices': 1},
    'shell_place':      {'min': 20.0,  'max': 300.0, 'volume': 0.9,  'pitch': 0.05, 'voices': 1},
    'landmark_study':   {'min': 10.0,  'max': 120.0, 'volume': 0.7,  'pitch': 0.0,  'voices': 1},
    'human_hurt':       {'min': 6.0,   'max': 80.0,  'volume': 0.8,  'pitch': 0.06, 'voices': 1},
    'human_down':       {'min': 6.0,   'max': 80.0,  'volume': 0.8,  'pitch': 0.03, 'voices': 1},
    # Pass 54: the newer moments
    'indigo_shake':     {'min': 8.0,   'max': 60.0,  'volume': 0.7,  'pitch': 0.08, 'voices': 1},
    'indigo_wake':      {'min': 30.0,  'max': 300.0, 'volume': 0.9,  'pitch': 0.03, 'voices': 1},
    'giant_fall':       {'min': 50.0,  'max': 700.0, 'volume': 1.0,  'pitch': 0.05, 'voices': 1},
    'red_poisoned':     {'min': 20.0,  'max': 250.0, 'volume': 0.9,  'pitch': 0.04, 'voices': 1},
    'tower_climb':      {'spatial': False, 'volume': 0.6},
    'legend_found':     {'spatial': False, 'volume': 0.8},
    'well_drink':       {'min': 6.0,   'max': 60.0,  'volume': 0.8,  'pitch': 0.05, 'voices': 1},
    # Pass 61: etchings, and Gleebs
    'lore_read':        {'min': 5.0,   'max': 50.0,  'volume': 0.7,  'pitch': 0.03, 'voices': 1},
    'gleebs_arrive':    {'spatial': False, 'volume': 0.9},
    'gleebs_voice':     {'spatial': False, 'volume': 0.55, 'pitch': 0.06},
    'gleebs_depart':    {'spatial': False, 'volume': 0.9},
    # listener-locked (2D)
    'heartbeat':        {'spatial': False, 'volume': 0.6, 'loop': True},
    'amb_wind':         {'spatial': False, 'volume': 0.5, 'loop': True, 'category': 'ambience'},
    'amb_heat':         {'spatial': False, 'volume': 0.35, 'loop': True, 'category': 'ambience'},
}
DEFAULT_SETTINGS = {'master': 1.0, 'music': 0.7, 'sfx': 1.0, 'ambience': 0.8}
SHELL_MUFFLE = 0.45                 # everything outside sounds quieter from inside a shell
BATTLE_FADE_IN = 2.5
BATTLE_FADE_OUT = 6.0
BATTLE_HOLD = 8.0                   # keep the battle music a while after the fighting stops
AMBIENT_GAP = (18.0, 45.0)          # quiet between ambient cues
AMBIENT_FIRST_DELAY = 4.0


def _files_for(folder: Path, stem: str):
    """<stem>.ext and <stem>_NN.ext variants, in name order."""
    out = []
    if folder.is_dir():
        for p in sorted(folder.iterdir()):
            if p.suffix.lower() not in AUDIO_EXTS:
                continue
            name = p.stem
            if name == stem or (name.startswith(stem + '_') and name[len(stem) + 1:].isdigit()):
                out.append(p)
    return out


class _Voice:
    __slots__ = ('sound', 'file')

    def __init__(self, sound, file):
        self.sound, self.file = sound, file


class AudioDirector:
    def __init__(self, base, root: Path):
        self.base = base
        self.root = Path(root)
        self.sfx_dir = self.root / 'sfx'
        self.music_dir = self.root / 'music'
        self.manifest = {k: dict(v) for k, v in DEFAULT_MANIFEST.items()}
        self.settings = dict(DEFAULT_SETTINGS)
        self._load_json_overrides()
        managers = getattr(base, 'sfxManagerList', None) or []
        self.sfx_manager = managers[0] if managers else None
        self.music_manager = getattr(base, 'musicManager', None)
        self.enabled = self.sfx_manager is not None and self.sfx_manager.isValid()
        self.voices: dict[str, list[_Voice]] = {}
        self.missing: set[str] = set()
        self.stats = Counter()
        self.culled = Counter()
        self.rr: dict[str, int] = {}
        self.last_file: dict[str, Path] = {}
        self.listener = (0.0, 0.0, 0.0)
        self.muffle = 1.0
        self.music_muted = False
        self.loops: dict[str, dict] = {}
        self.rng = random.Random(40)
        if self.sfx_manager is not None:
            self.sfx_manager.audio3dSetDistanceFactor(1.0)     # 1 world unit = 1 metre
            self.sfx_manager.audio3dSetDopplerFactor(0.0)       # no pitch wobble on fast giants
            self.sfx_manager.audio3dSetDropOffFactor(1.0)
        for name in self.manifest:
            self._load_event(name)
        # music
        self.ambient_tracks = [self._load_music(p) for p in _files_for(self.music_dir, 'ambient')]
        self.ambient_tracks = [s for s in self.ambient_tracks if s is not None]
        battle = [self._load_music(p) for p in _files_for(self.music_dir, 'battle')]
        self.battle = next((s for s in battle if s is not None), None)
        if self.battle is not None:
            self.battle.setLoop(True)
        self.stingers = {}
        for p in self.music_dir.glob('stinger_*') if self.music_dir.is_dir() else []:
            if p.suffix.lower() in AUDIO_EXTS:
                s = self._load_music(p)
                if s is not None:
                    self.stingers[p.stem[len('stinger_'):]] = s
        self.ambient_order = list(range(len(self.ambient_tracks)))
        self.rng.shuffle(self.ambient_order)
        self.ambient_index = -1
        self.ambient_current = None
        self.ambient_wait = AMBIENT_FIRST_DELAY
        self.battle_level = 0.0
        self.battle_hold = 0.0
        self.battle_active = False
        self.stinger_duck = 0.0
        self.pending: list[tuple[float, str, tuple | None, float]] = []

    # ------------------------------------------------------------ loading
    def _load_json_overrides(self):
        for fname, target in (('audio_manifest.json', 'manifest'), ('audio_settings.json', 'settings')):
            path = self.root / fname
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                print(f'[audio] ignoring {path.name}: {exc}')
                continue
            if target == 'settings':
                for k, v in data.items():
                    if k in self.settings and isinstance(v, (int, float)):
                        self.settings[k] = max(0.0, float(v))
            else:
                for event, cfg in data.items():
                    if isinstance(cfg, dict) and not event.startswith('_'):
                        self.manifest.setdefault(event, {}).update(cfg)

    def _load_sound(self, path: Path):
        try:
            return self.base.loader.loadSfx(Filename.fromOsSpecific(str(path)))
        except Exception as exc:        # a broken file must never stop the game
            print(f'[audio] could not load {path.name}: {exc}')
            return None

    def _load_music(self, path: Path):
        try:
            return self.base.loader.loadMusic(Filename.fromOsSpecific(str(path)))
        except Exception as exc:
            print(f'[audio] could not load {path.name}: {exc}')
            return None

    def _load_event(self, name: str):
        files = _files_for(self.sfx_dir, name)
        cfg = self.manifest[name]
        voices = []
        for f in files:
            for _ in range(max(1, int(cfg.get('voices', 1)))):
                s = self._load_sound(f)
                if s is not None:
                    if cfg.get('spatial', True):
                        s.set3dMinDistance(float(cfg.get('min', 10.0)))
                        s.set3dMaxDistance(float(cfg.get('max', 300.0)))
                    voices.append(_Voice(s, f))
        if not voices:
            self.missing.add(name)
        self.voices[name] = voices

    # ------------------------------------------------------------- volumes
    def _category_gain(self, cfg) -> float:
        cat = cfg.get('category', 'sfx')
        return self.settings['master'] * self.settings.get(cat, 1.0)

    def _music_gain(self) -> float:
        return 0.0 if self.music_muted else self.settings['master'] * self.settings['music']

    def toggle_music(self):
        self.music_muted = not self.music_muted
        return self.music_muted

    # ------------------------------------------------------------- one-shots
    def play(self, name: str, pos=None, volume: float = 1.0, delay: float = 0.0):
        """Play an event at a world position (None = at the listener)."""
        if delay > 0.0:
            self.pending.append((delay, name, None if pos is None else (pos[0], pos[1], pos[2]), volume))
            return None
        cfg = self.manifest.get(name)
        voices = self.voices.get(name)
        self.stats[name] += 1
        if cfg is None or not voices:
            return None
        spatial = cfg.get('spatial', True) and pos is not None
        if spatial:
            lx, ly, lz = self.listener
            d = math.sqrt((pos[0] - lx) ** 2 + (pos[1] - ly) ** 2 + (pos[2] - lz) ** 2)
            if d > float(cfg.get('max', 300.0)) * 1.05:
                self.culled[name] += 1
                return None
        files = sorted({v.file for v in voices})
        choice = files[0]
        if len(files) > 1:
            options = [f for f in files if f != self.last_file.get(name)]
            choice = self.rng.choice(options)
        self.last_file[name] = choice
        pool = [v for v in voices if v.file == choice]
        idle = [v for v in pool if v.sound.status() != AudioSound.PLAYING]
        if idle:
            voice = idle[0]
        else:
            i = self.rr.get(name, 0) % len(pool)
            self.rr[name] = i + 1
            voice = pool[i]
        s = voice.sound
        s.stop()
        p = pos if spatial else self.listener
        s.set3dAttributes(p[0], p[1], p[2], 0.0, 0.0, 0.0)
        pitch = float(cfg.get('pitch', 0.0))
        s.setPlayRate(1.0 + self.rng.uniform(-pitch, pitch))
        muffle = self.muffle if spatial else 1.0
        s.setVolume(max(0.0, min(1.0, float(cfg.get('volume', 1.0)) * volume * self._category_gain(cfg) * muffle)))
        s.play()
        return s

    # ------------------------------------------------------------------ loops
    def set_loop(self, name: str, target: float):
        """Listener-locked looping bed (wind, heat, heartbeat) faded toward target (0..1)."""
        st = self.loops.get(name)
        if st is None:
            voices = self.voices.get(name) or []
            st = {'sound': voices[0].sound if voices else None, 'level': 0.0, 'target': 0.0, 'playing': False}
            if st['sound'] is not None:
                st['sound'].setLoop(True)
            self.loops[name] = st
        st['target'] = max(0.0, min(1.0, target))

    def _update_loops(self, dt: float):
        for name, st in self.loops.items():
            s = st['sound']
            rate = 0.8 * dt
            st['level'] += max(-rate, min(rate, st['target'] - st['level']))
            if s is None:
                continue
            if st['level'] > 0.001 and not st['playing']:
                s.play()
                st['playing'] = True
            elif st['level'] <= 0.001 and st['playing']:
                s.stop()
                st['playing'] = False
            if st['playing']:
                cfg = self.manifest.get(name, {})
                s.set3dAttributes(*self.listener, 0.0, 0.0, 0.0)
                s.setVolume(st['level'] * float(cfg.get('volume', 1.0)) * self._category_gain(cfg))

    # ------------------------------------------------------------------ music
    def stinger(self, name: str):
        self.stats['stinger_' + name] += 1
        s = self.stingers.get(name)
        if s is None or self.music_muted:
            return None
        s.stop()
        s.setVolume(0.9 * self._music_gain())
        s.play()
        self.stinger_duck = max(self.stinger_duck, s.length() if s.length() > 0 else 4.0)
        return s

    def set_battle(self, active: bool):
        self.battle_active = bool(active)

    def _update_music(self, dt: float):
        gain = self._music_gain()
        # battle layer
        if self.battle_active:
            self.battle_hold = BATTLE_HOLD
            self.battle_level = min(1.0, self.battle_level + dt / BATTLE_FADE_IN)
        else:
            self.battle_hold = max(0.0, self.battle_hold - dt)
            if self.battle_hold <= 0.0:
                self.battle_level = max(0.0, self.battle_level - dt / BATTLE_FADE_OUT)
        if self.battle is not None:
            playing = self.battle.status() == AudioSound.PLAYING
            if self.battle_level > 0.0 and not playing:
                self.battle.play()
            elif self.battle_level <= 0.0 and playing:
                self.battle.stop()
            self.battle.setVolume(self.battle_level * gain)
        # ambient cues: one at a time, quiet gaps between, ducked under battle and stingers
        self.stinger_duck = max(0.0, self.stinger_duck - dt)
        duck = (1.0 - self.battle_level) * (0.4 if self.stinger_duck > 0.0 else 1.0)
        cur = self.ambient_current
        if cur is not None and cur.status() == AudioSound.PLAYING:
            cur.setVolume(0.8 * gain * duck)
        elif self.ambient_tracks:
            if cur is not None:
                self.ambient_current = None
                self.ambient_wait = self.rng.uniform(*AMBIENT_GAP)
            self.ambient_wait -= dt
            if self.ambient_wait <= 0.0:
                self.ambient_index = (self.ambient_index + 1) % len(self.ambient_order)
                self.ambient_current = self.ambient_tracks[self.ambient_order[self.ambient_index]]
                self.ambient_current.setVolume(0.8 * gain * duck)
                self.ambient_current.play()
                self.stats['ambient_cue'] += 1
                # headless/null audio never reports PLAYING: fall back to a timed gap
                self.ambient_wait = self.rng.uniform(*AMBIENT_GAP) + max(0.0, self.ambient_current.length())

    # ----------------------------------------------------------------- frame
    def update(self, dt: float, listener_np, render):
        pos = listener_np.getPos(render)
        q = listener_np.getQuat(render)
        fwd, up = q.getForward(), q.getUp()
        self.listener = (pos.x, pos.y, pos.z)
        if self.sfx_manager is not None:
            self.sfx_manager.audio3dSetListenerAttributes(pos.x, pos.y, pos.z, 0, 0, 0,
                                                          fwd.x, fwd.y, fwd.z, up.x, up.y, up.z)
        if self.pending:
            keep = []
            for delay, name, p, vol in self.pending:
                delay -= dt
                if delay <= 0.0:
                    self.play(name, p, vol)
                else:
                    keep.append((delay, name, p, vol))
            self.pending = keep
        self._update_loops(dt)
        self._update_music(dt)

    def shutdown(self):
        """Stop and release every sound before the audio device goes away (avoids an
        OpenAL crash at interpreter exit seen with sounds still alive)."""
        for voices in self.voices.values():
            for v in voices:
                v.sound.stop()
        for s in list(self.ambient_tracks) + list(self.stingers.values()) + ([self.battle] if self.battle else []):
            s.stop()
        for st in self.loops.values():
            if st['sound'] is not None:
                st['sound'].stop()
        self.voices.clear()
        self.loops.clear()
        self.ambient_tracks = []
        self.ambient_current = None
        self.stingers.clear()
        self.battle = None
        self.enabled = False
        for mgr in [self.sfx_manager, self.music_manager]:
            if mgr is not None:
                mgr.stopAllSounds()
                mgr.clearCache()
        if self.music_manager is not None:
            # A streamed music track that has played leaves OpenAL's streaming thread
            # alive; shutting the music manager down first avoids a crash at exit.
            self.music_manager.shutdown()

    def report(self) -> str:
        loaded = sum(1 for v in self.voices.values() if v)
        return (f'audio: {"on" if self.enabled else "off (no device)"}; {loaded}/{len(self.voices)} events loaded; '
                f'{len(self.ambient_tracks)} ambient cue(s); battle {"yes" if self.battle else "no"}; '
                f'{len(self.stingers)} stinger(s)' + (f'; silent: {", ".join(sorted(self.missing))}' if self.missing else ''))


# ============================================================================ mixin
RED_HUNT_ROAR_COOLDOWN = 25.0
INDIGO_CALL_COOLDOWN = 12.0
HEAVE_PERIOD = 2.3
BATTLE_RANGE = 130.0


class AudioMixin:
    """Mixed in first: wires game events to the AudioDirector."""

    def _init_audio(self):
        root = Path(__file__).resolve().parent / 'audio'
        self.audio = AudioDirector(self, root)
        print(self.audio.report())
        self._snd = {'red_state': self.red_state, 'fleeing': False, 'ko': False, 'returning': False,
                     'defending': False, 'whistle': 0.0, 'visited': 0, 'hunt_cd': 0.0, 'call_cd': 0.0,
                     'heave_t': 0.0}
        self.bind_action('music', self._toggle_music)
        self.audio.set_loop('amb_wind', 1.0)

    def userExit(self):
        audio = getattr(self, 'audio', None)
        if audio is not None:
            audio.shutdown()
            self.audio = None
        super().userExit()

    def _toggle_music(self):
        muted = self.audio.toggle_music()
        if hasattr(self, 'say'):
            self.say('music off' if muted else 'music on', 1.2)

    def sfx(self, name: str, pos=None, volume: float = 1.0, delay: float = 0.0):
        audio = getattr(self, 'audio', None)
        if audio is None:
            return None
        return audio.play(name, pos, volume, delay)

    # ---------------------------------------------------------------- frame
    def survival_step(self, dt: float):
        super().survival_step(dt)
        if getattr(self, 'audio', None) is not None:
            self._audio_step(dt)

    def _audio_step(self, dt: float):
        a = self.audio
        s = self._snd
        s['hunt_cd'] = max(0.0, s['hunt_cd'] - dt)
        s['call_cd'] = max(0.0, s['call_cd'] - dt)
        rp = self.red_giant.getPos(self.render)
        gp = self.giant.getPos(self.render)
        red_head = Point3(rp.x, rp.y, rp.z + self.red_giant_height * 0.85)
        indigo_head = Point3(gp.x, gp.y, gp.z + self.giant_height * 0.85)
        red_active = not (self.red_knocked_out or self.red_recovering or self.red_fleeing or self.red_lurking or self.red_dead)

        # --- Red Giant voice
        hunting = self.red_state in ('pursue', 'melee', 'stomp', 'overturn')
        if (red_active and hunting and s['red_state'] not in ('pursue', 'melee', 'stomp', 'overturn')
                and s['hunt_cd'] <= 0.0 and not self.red_returning):
            self.sfx('roar_red_hunt', red_head)
            s['hunt_cd'] = RED_HUNT_ROAR_COOLDOWN
        if self.red_knocked_out and not s['ko']:
            self.sfx('roar_red_ko', rp)
            a.stinger('ko')
        elif self.red_fleeing and not s['fleeing'] and not self.red_recovering:
            self.sfx('roar_red_scared', red_head)
        if self.red_returning and not s['returning']:
            self.sfx('roar_red_return', red_head)
            a.stinger('red_return')
        if self.red_state == 'overturn':
            s['heave_t'] -= dt
            if s['heave_t'] <= 0.0:
                s['heave_t'] = HEAVE_PERIOD
                self.sfx('roar_red_heave', red_head)
                if self.hidden_shell is not None:
                    self.sfx('shell_creak', self.hidden_shell.pos)
        else:
            s['heave_t'] = 0.0
        s.update(red_state=self.red_state, fleeing=self.red_fleeing, ko=self.red_knocked_out,
                 returning=self.red_returning)

        # --- Indigo voice: answers a whistle, calls out when it moves to defend
        if self.whistle_alert > s['whistle'] + 1.0 and self.giant_alive:
            self.sfx('call_indigo', indigo_head, delay=0.9)
            s['call_cd'] = INDIGO_CALL_COOLDOWN
        s['whistle'] = self.whistle_alert
        if self.indigo_defending and not s['defending'] and s['call_cd'] <= 0.0:
            self.sfx('call_indigo', indigo_head)
            s['call_cd'] = INDIGO_CALL_COOLDOWN
        s['defending'] = self.indigo_defending

        # --- landmark trail cue
        visited = self.landmarks.visited_count()
        if visited > s['visited']:
            a.stinger('landmark')
        s['visited'] = visited

        # --- beds: wind, heat shimmer, heartbeat
        in_shell = self.hidden_shell is not None
        a.muffle = SHELL_MUFFLE if in_shell else 1.0
        a.set_loop('amb_wind', 0.25 if in_shell else (1.0 if self.carried else 0.7))
        a.set_loop('amb_heat', max(0.0, min(1.0, (self.heat - 40.0) / 60.0)) if self.human_alive else 0.0)
        danger = self.human_alive and (self.heat >= 85.0 or self.human_health <= 25.0)
        a.set_loop('heartbeat', 1.0 if danger else 0.0)

        # --- music: battle while the Red Giant is hunting close by, or Indigo is fighting
        near = self._human_red_distance() <= BATTLE_RANGE
        a.set_battle(self.human_alive and (self.indigo_defending or (red_active and hunting and near)))
        a.update(dt, self.camera, self.render)
