"""Pass 40 check: sound events, 3D falloff, music fades, replaceable files.

    python .dev/checks/pass40.py

Runs with the real OpenAL audio device (you will hear it on a PC with speakers).  On a
machine without an audio device it still runs; the game is silent but every event is
still triggered and counted.
"""
from __future__ import annotations

import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

from panda3d.core import Filename, MovieAudio, Point3, Vec3

import sys as _sys                                  # Pass 62: the game folder is two levels up
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from indigo_giant import app as game
from indigo_giant import audio as snd

FAILS: list[str] = []
CLOCK = [0.0]
HERE = Path(__file__).resolve().parents[2]          # Pass 62: the game folder


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def frame(a, dt=1 / 30.0):
    CLOCK[0] += dt
    t = CLOCK[0]
    h = math.radians(a.heading)
    fwd, right = Vec3(math.sin(h), math.cos(h), 0), Vec3(math.cos(h), -math.sin(h), 0)
    move = Vec3(0, 0, 0)
    if a.keys['w']: move += fwd
    if a.keys['d']: move += right
    if a.keys['a']: move -= right
    if a.controlled_name == 'giant':
        a._apply_giant_heavy_input(move, dt, t)
    else:
        a._apply_controlled_move(move, dt, t)
    a._update_indigo_defender(dt, t)
    a._update_companion(dt)
    a._update_red_giant(dt, t)
    a.survival_step(dt)
    a._place_camera(immediate=False, dt=dt)
    a._update_actor_shadows()
    a.service_stream_queue()


def run(a, seconds, until=None, dt=1 / 30.0):
    for i in range(int(round(seconds / dt))):
        frame(a, dt)
        if until is not None and until():
            return (i + 1) * dt
    return None


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


def park_red_far(a):
    p = a.human.getPos() + Vec3(700, 0, 0)
    a.red_giant.setPos(ground(a, p.x, p.y))
    a.red_state = 'idle'


def main():
    # ------------------------------------------------------------ files
    files = sorted((HERE / 'audio').glob('*/*.*'))
    files = [f for f in files if f.suffix.lower() in snd.AUDIO_EXTS]
    bad = []
    for f in files:
        cursor = MovieAudio.get(Filename.fromOsSpecific(str(f))).open()
        if cursor is None or cursor.length() <= 0.05 or cursor.audioRate() <= 0:
            bad.append(f.name)
    check('every audio file decodes in Panda3D', files and not bad, f'{len(files)} files' + (f', bad: {bad}' if bad else ''))
    missing = [e for e in snd.DEFAULT_MANIFEST if not snd._files_for(HERE / 'audio' / 'sfx', e)]
    check('every sound event has at least one file', not missing, missing)
    for name in ('footstep_giant', 'footstep_red', 'roar_red_hunt', 'call_indigo'):
        f = snd._files_for(HERE / 'audio' / 'sfx', name)[0]
        mono = MovieAudio.get(Filename.fromOsSpecific(str(f))).open().audioChannels() == 1
        if not mono:
            check(f'{name} is mono (needed for 3D)', False)
    check('3D sounds are mono', True)

    glb = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
    a = game.StreamingTerrainWithGiant(offscreen=False, vsync=False, giant_glb=glb, show_title=False, persist=False)
    a.time_frozen = True          # Pass 43: hold the clock at a steady sun for these checks
    a.heat_factor_override = 1.0
    a.taskMgr.removeTasksMatching('*')          # we step the game ourselves
    au = a.audio
    print(au.report())
    check('audio director is up', au is not None and not au.missing, au.report())
    park_red_far(a)
    run(a, 1.0)

    # ------------------------------------------------------------ footsteps
    n0 = au.stats['footstep_human']
    a.keys['w'] = True
    run(a, 3.0)
    a.keys['w'] = False
    check('human footsteps sound while walking', au.stats['footstep_human'] - n0 >= 4, au.stats['footstep_human'] - n0)
    g0 = au.stats['footstep_giant']
    far = a.human.getPos() + Vec3(-60, 30, 0)
    a.human.setPos(ground(a, far.x, far.y))
    a.gesture_command('come')
    check('gesture sound plays', au.stats['gesture_come'] == 1)
    run(a, 15.0)
    check('giant footsteps sound as it walks over', au.stats['footstep_giant'] - g0 >= 3, au.stats['footstep_giant'] - g0)

    # distance culling / falloff
    c0 = au.culled['footstep_human']
    lp = Point3(*au.listener)
    au.play('footstep_human', Point3(lp.x + 500, lp.y, lp.z))
    check('far-away quiet sounds are culled', au.culled['footstep_human'] == c0 + 1)
    s = au.play('footstep_giant', Point3(lp.x + 200, lp.y, lp.z))
    check('giant steps still carry 200 m', s is not None)
    if s is not None and au.enabled:
        check('3D falloff is set per event', abs(s.get3dMinDistance() - 30.0) < 1e-3 and abs(s.get3dMaxDistance() - 420.0) < 1e-3)

    # ------------------------------------------------------------ whistle + Indigo call
    w0, c0 = au.stats['whistle'], au.stats['call_indigo']
    a.gesture_command('whistle')
    run(a, 1.5)
    check('whistle and Indigo answers', au.stats['whistle'] == w0 + 1 and au.stats['call_indigo'] == c0 + 1)

    # ------------------------------------------------------------ red hunt: roar, steps, battle music
    park_red_far(a)
    a.whistle_alert = 0.0
    run(a, 1.0)
    r0, rs0 = au.stats['roar_red_hunt'], au.stats['footstep_red']
    hp = a.human.getPos()
    a.red_giant.setPos(ground(a, hp.x + 90, hp.y))
    a.red_state = 'idle'
    a.giant.setPos(ground(a, hp.x - 200, hp.y))      # Indigo far away: let Red come
    a.comp.update({'mode': 'stay', 'moving': False})
    t = run(a, 10.0, until=lambda: au.battle_level >= 1.0)
    check('Red roars when it starts hunting', au.stats['roar_red_hunt'] == r0 + 1)
    check('battle music fades in (~2.5 s)', t is not None and 2.0 <= t <= 3.5, t)
    run(a, 4.0)
    check('Red footsteps sound', au.stats['footstep_red'] > rs0)
    # human hides from red? -> test muffle
    park_red_far(a)
    a.whistle_alert = 0.0
    t = run(a, 30.0, until=lambda: au.battle_level <= 0.0)
    check('battle music holds then fades out (~14 s)', t is not None and 12.0 <= t <= 16.0, t)

    # ------------------------------------------------------------ KO & scare voices, stingers
    ko0 = au.stats['roar_red_ko']
    a.red_giant.setPos(ground(a, hp.x + 30, hp.y))
    a._knock_out_red()
    run(a, 0.2)
    check('knockout roar + stinger', au.stats['roar_red_ko'] == ko0 + 1 and au.stats['stinger_ko'] >= 1)
    a.red_knocked_out = False
    a.red_recovering = False
    a._set_combat_health('red', 50.0)
    a.red_anger, a.red_hunger, a.red_woken_t = 0, 0.1, 0.0     # Pass 53: sneaky and nearly spent: it runs
    a.red_stamina = 15.0
    sc0 = au.stats['roar_red_scared']
    a.giant.setPos(ground(a, a.red_giant.getX() - 4.5, a.red_giant.getY()))
    a._apply_melee_hit('giant')
    run(a, 0.2)
    check('scared-off roar', a.red_fleeing and au.stats['roar_red_scared'] == sc0 + 1)
    check('punch impact sound', au.stats['punch_hit'] >= 1)
    park_red_far(a)
    a.red_fleeing = False
    a.red_begin_lurk()
    a.red_lurk_elapsed = a.red_return_delay()
    rr0 = au.stats['roar_red_return']
    run(a, 0.5)
    check('distant roar + stinger when Red returns', au.stats['roar_red_return'] == rr0 + 1 and au.stats['stinger_red_return'] >= 1)
    park_red_far(a)
    a.red_returning = False

    # ------------------------------------------------------------ desert actions
    f0 = a.finds.finds[('start', 0)]
    if not f0.dug:
        a.human.setPos(ground(a, f0.pos.x + 0.8, f0.pos.y))
        a._refresh_world()
        a._on_e_press()
        run(a, 1.4)
        a.keys['e'] = False
        check('dig sound', au.stats['dig'] == 1)
    a.bag('human')['gourd'] += 1
    a.heat = 60
    a.eat()
    check('eat sound', au.stats['eat'] >= 1)
    shell = a.shells.shells[('start', 0)]
    a.shells.set_state(shell, 'intact')
    a.human.setPos(ground(a, shell.entrance_point().x, shell.entrance_point().y))
    a._refresh_world()
    a._on_e_press()
    a.keys['e'] = False
    run(a, 0.5)
    check('shell enter sound, outside world muffled', au.stats['shell_enter'] == 1 and au.muffle == snd.SHELL_MUFFLE)
    check('wind drops inside the shell', a.audio.loops['amb_wind']['target'] < 0.3)
    a.exit_shell()
    run(a, 0.2)
    check('shell exit sound, muffle off', au.stats['shell_exit'] == 1 and au.muffle == 1.0)

    # overturn heaves
    a.red_giant.setPos(ground(a, shell.pos.x - 40, shell.pos.y))
    a.red_state = 'pursue'
    a.giant.setPos(ground(a, shell.pos.x + 200, shell.pos.y))
    a.human.setPos(ground(a, shell.entrance_point().x, shell.entrance_point().y))
    a.enter_shell(shell)
    t = run(a, 40.0, until=lambda: shell.state == 'flipped')
    check('heave grunts + creaks, then the flip', t is not None and au.stats['roar_red_heave'] >= 2
          and au.stats['shell_creak'] >= 2 and au.stats['shell_flip'] == 1,
          f"heave {au.stats['roar_red_heave']} creak {au.stats['shell_creak']} flip {au.stats['shell_flip']}")
    park_red_far(a)

    # heat heartbeat bed
    a.heat = 90.0
    run(a, 0.3)
    check('heartbeat when overheating', a.audio.loops['heartbeat']['target'] == 1.0)
    a.heat = 10.0
    run(a, 0.3)
    check('heartbeat stops when cool', a.audio.loops['heartbeat']['target'] == 0.0)

    # landmark stinger
    lm = next(x for x in a.landmarks.items if x.revealed and not x.visited)
    reach = __import__('indigo_giant.desert_geom', fromlist=['LANDMARK_SHAPES']).LANDMARK_SHAPES[lm.kind][0] + 3.0
    a.human_dazed = 0.0
    a.human.setPos(ground(a, lm.pos.x + reach, lm.pos.y))
    a._refresh_world()
    a._on_e_press()
    run(a, 2.2)
    a.keys['e'] = False
    run(a, 0.2)
    check('landmark chime + stinger', au.stats['landmark_study'] >= 1 and au.stats['stinger_landmark'] >= 1)

    # ambient cues
    a.audio.ambient_wait = 0.0
    k0 = au.stats['ambient_cue']
    run(a, 0.2)
    check('ambient music cue starts', au.stats['ambient_cue'] == k0 + 1)
    a._toggle_music()
    check('M mutes the music', au.music_muted and au._music_gain() == 0.0)
    a._toggle_music()

    # jump / kneel
    a.human.setPos(ground(a, a.human.getX(), a.human.getY()))
    l0 = au.stats['land_human']
    a.stamina = 100
    a._request_jump()
    run(a, 1.5)
    check('landing thud', au.stats['land_human'] == l0 + 1)
    a._toggle_control()
    a._toggle_kneel()
    run(a, 1.6)
    a._toggle_kneel()
    run(a, 1.6)
    check('giant kneel + stand sounds', au.stats['kneel_giant'] >= 1 and au.stats['stand_giant'] >= 1)
    a._toggle_control()

    print('events heard:', dict(sorted(au.stats.items())))

    # ------------------------------------------------------------ replaceable / missing files
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / 'sfx').mkdir()
        shutil.copy(HERE / 'audio/sfx/whistle_01.wav', tmp / 'sfx/whistle.wav')           # plain name works
        shutil.copy(HERE / 'audio/sfx/dig_01.wav', tmp / 'sfx/dig_07.wav')                # any number works
        (tmp / 'audio_manifest.json').write_text(json.dumps({'whistle': {'volume': 0.25}}))
        (tmp / 'audio_settings.json').write_text(json.dumps({'music': 0.3}))

        class FakeBase:
            loader = a.loader
            sfxManagerList = []
            musicManager = None
        d = snd.AudioDirector(FakeBase(), tmp)
        check('custom file names are picked up', d.voices['whistle'] and d.voices['dig'])
        check('manifest and settings overrides apply', d.manifest['whistle']['volume'] == 0.25 and d.settings['music'] == 0.3)
        check('missing files are silent, not errors', 'roar_red_hunt' in d.missing and d.play('roar_red_hunt', Point3(0, 0, 0)) is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    a.destroy()

    print('RESULT', 'FAIL' if FAILS else 'PASS', FAILS)
    sys.exit(1 if FAILS else 0)


if __name__ == '__main__':
    main()
