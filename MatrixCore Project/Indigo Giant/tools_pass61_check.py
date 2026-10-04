"""Pass 61 check: Nyx, Orbit and Crimson; the etchings; Gleebs and the end of REDACTED.

    python tools_pass61_check.py
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import sys
import tempfile
import tokenize
from pathlib import Path

from panda3d.core import Point3, TextNode

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='indigo_save61_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import endgame        # noqa: E402
import gleebs         # noqa: E402
import lore           # noqa: E402
import main as game   # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
DT = 1 / 30.0


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


def new_app(**kw):
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, persist=True, save_dir=TMP,
                                       show_title=False, **kw)
    a.time_frozen = True
    a.comp.update({'mode': 'stay', 'moving': False})
    return a


def hold_e(a, seconds):
    a.keys['e'] = True
    a.e_hold['spent'] = False
    for _ in range(int(seconds / DT) + 1):
        a._update_e_hold(DT)
    a.keys['e'] = False
    a._update_e_hold(DT)


def panel_words(a):
    words = [tn.node().getText() for tn in a.panel.findAllMatches('**/+TextNode') if isinstance(tn.node(), TextNode)]
    return words


def panel_buttons(a):
    return [np_.getPythonTag('label') for np_ in a.panel.findAllMatches('**/+PGButton')]


def old_names_in_player_text():
    """String literals a player can read that still say Indigo / the red one (the game title and
    file names excepted; docstrings and identifiers are not player text)."""
    pat = re.compile(r"\bIndigo\b(?! Giant)|\b[Tt]he red one\b|\bRed Giant\b")
    found = []
    for f in sorted(glob.glob(str(HERE / '*.py'))):
        name = Path(f).name
        if name.startswith('tools_') or name in ('animation_audit.py', 'perf_probe.py'):
            continue
        for tok in tokenize.generate_tokens(io.StringIO(Path(f).read_text(encoding='utf-8')).readline):
            if tok.type != tokenize.STRING or '"""' in tok.string[:4] or "'''" in tok.string[:4]:
                continue
            body = tok.string.strip('rfbuRFBU').strip('"\'')
            if ' ' in body and pat.search(body) and 'print(' not in tok.line:
                found.append(f'{name}:{tok.start[0]}')
    return found


def main():
    # ------------------------------------------------------------ 1. the names
    left = old_names_in_player_text()
    check('player-facing text calls them Nyx, Orbit and Crimson (no "Indigo" / "the red one" left)',
          not left, ', '.join(left[:6]))
    a = new_app(new_game=True)
    b = a.human_base_pos
    a.red_giant.setPos(ground(a, b.x + 60, b.y + 40))
    a.red_state = 'pursue'
    a.survival_step(DT)
    a._update_hud(DT)
    red_label = a.hud_red.getText()
    check('the HUD: "nyx" under your companion, "crimson" for the red giant',
          a.bar_indigo.label.getText().startswith('nyx') and red_label.startswith('crimson'),
          f'{a.bar_indigo.label.getText()!r}, {red_label!r}')
    a.toggle_panel('help')
    words = panel_words(a)
    a.close_panel()
    check('F1 help: "be Nyx / be Orbit", "Nyx: punch", sleeping "by Nyx"',
          'be Nyx / be Orbit' in words and any(w.startswith('Nyx: punch') for w in words)
          and any('by Nyx' in w for w in words))

    # ------------------------------------------------------------ 2. the etchings
    es = a.etchings
    dists = [(e.pos - b).length() for e in es]
    texts = ' '.join(e.text for e in es)
    check('14 etchings stand across the desert, from ~60 m out to ~9.4 km, nearest first',
          len(es) == 14 and dists == sorted(dists) and 40 < dists[0] < 90 and dists[-1] > 8500,
          f'{[round(d) for d in dists]}')
    check('together they tell of NYX, ORBIT, CRIMSON (not wise), REDACTED (hidden, dying) and GLEEBS',
          all(w in texts for w in ('NYX', 'ORBIT', 'CRIMSON', 'REDACTED', 'GLEEBS', 'not wise', 'dying',
                                   'did not want this world found')))
    clear = all(a.places.nearest(e.pos, 30.0) is None for e in es) and all(
        min((abs((s.pos - e.pos).length()) for s in a.shells.shells.values()), default=99) > 6.0 for e in es)
    check('each stands on open sand (no shell or place on top of it)', clear)

    e = es[0]
    a.human.setPos(ground(a, e.pos.x + 1.5, e.pos.y))
    a.hour = 14.0
    a._apply_time(force=True)
    a.survival_step(DT)
    day_glyph = e.glyphs[0].getColor()[3]
    day_glimmer = not e.glimmer.isHidden()
    a.hour = 23.0
    a._apply_time(force=True)
    a.camera.setPos(e.pos + Point3(0, -40, 5))
    a.survival_step(DT)
    night_glyph = e.glyphs[0].getColor()[3]
    check('by day the marks are a faint cut; at night they glow, and a glimmer shows the stone from far off',
          night_glyph > day_glyph * 3 and day_glimmer is False and not e.glimmer.isHidden(),
          f'glyph {day_glyph:.2f} -> {night_glyph:.2f}')
    kind, target = a._e_target()
    prompt = a.place_prompt(kind, target)
    a.lore_text.setText('')
    hold_e(a, lore.HOLD_TIME + 0.1)
    said = a.lore_text.getText()
    head, notes = a.notes_lines()
    check('beside it, hold E to read the etching: its words, and "etching 1 of 14 · J > notes"',
          kind == 'etching' and prompt == 'read the etching' and e.read and 'NYX' in said and '1 of 14' in said
          and head.endswith('1 of 14') and notes == [e.text], said[:60])
    check('a read etching dims a little; you can read it again',
          a._e_target()[0] == 'etching' and a.place_prompt(*a._e_target()) == 'read the etching again'
          and e.glyphs[0].getColor()[3] < night_glyph)
    a.journal_page = 'notes'
    a.toggle_panel('journal')
    words = panel_words(a)
    a.close_panel()
    check('J > notes lists the etchings you have read', any('etchings read' in w for w in words)
          and any(w.startswith('A tall walker') for w in words))

    # ------------------------------------------------------------ 3. night words are readable
    a.say('test', 2.0)
    a._update_say(DT)
    fg = a.lore_text.textNode.getTextColor()
    check('at night the spoken lines are pale ink (they were dark on the dark sand)', fg[0] > 0.7, f'{fg}')

    # ------------------------------------------------------------ 4. Crimson falls; Gleebs comes
    a.hour = 16.0
    a._apply_time(force=True)
    a.human.setPos(ground(a, b.x, b.y))
    a.giant.setPos(ground(a, b.x + 10, b.y - 6))
    a.red_giant.setPos(ground(a, b.x + 40, b.y + 30))
    a.heading = 0.0
    a.red_giant_dies()
    for _ in range(int((endgame.ENDING_DELAY + 0.2) / DT)):
        a.survival_step(DT)
    gp = a.gleebs_pos
    ahead = gp.y - b.y
    actor = a.gleebs_actor
    h = actor.getTightBounds() if actor is not None else None
    height = (h[1].z - h[0].z) if h else 0.0
    check('when Crimson has fallen, a beam of light comes down ~58 m ahead of you, clear of shells',
          a.gleebs_state == 'arriving' and not a.gleebs_root.isHidden() and 45 < (gp - b).length() < 90
          and ahead > 30.0 and a._gleebs_spot_ok(gp.x, gp.y), f'{(gp - b).length():.0f} m, {ahead:.0f} m ahead')
    check('Gleebs stands in it as a hologram (the Utopia Vision model, looping Idle), taller than Nyx',
          actor is not None and 'Idle' in actor.getAnimNames() and actor.getCurrentAnim() == 'Idle'
          and height > a.giant_height * 1.1, f'{height:.1f} m (Nyx {a.giant_height:.1f} m)')
    spoken = []
    for _ in range(int(gleebs.ARRIVE_END / DT) + 2):
        before = a.lore_text.getText()
        a.survival_step(DT)
        if a.lore_text.getText() != before:
            spoken.append(a.lore_text.getText())
    joined = ' '.join(spoken)
    check('it speaks: it heard Nyx and Orbit; REDACTED is hidden and dying; Crimson stays; it will wait',
          all(w in joined for w in ('Nyx. Orbit.', 'REDACTED', 'dying', 'Crimson', 'I will wait'))
          and a.gleebs_state == 'waiting', f'{len(spoken)} lines')
    light = a.render.getShaderInput('glow3_color')
    lv = light.getVector()
    check('its cyan light falls on the sand around it', lv[1] > 0.4 and lv[2] > 0.4 and lv[0] < lv[2],
          f'{lv[0]:.2f} {lv[1]:.2f} {lv[2]:.2f}')

    # ------------------------------------------------------------ 5. alone, it will not take you
    a.giant.setPos(ground(a, gp.x + 120, gp.y))
    a.human.setPos(ground(a, gp.x - 3, gp.y - 2))
    kind, _t = a._e_target()
    hold_e(a, gleebs.ALONE_HOLD + 0.1)
    check('step into the light alone: "Not alone. Bring Nyx..." - you stay',
          kind == 'alone' and a.gleebs_state == 'waiting' and 'Bring Nyx' in a.lore_text.getText())

    # ------------------------------------------------------------ 6. saved while it waits
    a.save_game('check')
    a.persist = False
    a.destroy()
    a = new_app()
    check('saved while Gleebs waits: it is still there after a load, in the same place; your etchings too',
          a.gleebs_state == 'waiting' and (a.gleebs_pos - gp).length() < 0.5 and a.etchings[0].read
          and not a.etchings[1].read, f'{a.gleebs_state}')

    # ------------------------------------------------------------ 7. together: leave REDACTED
    gp = a.gleebs_pos
    a.human.setPos(ground(a, gp.x - 3, gp.y - 2))
    a.giant.setPos(ground(a, gp.x + 14, gp.y - 8))
    a.carried = True
    riding_kind = a._e_target()[0]
    riding_prompt = a._prompt_and_progress()[0]
    a.carried = False
    check('riding on Nyx into the light counts as together (the prompt shows while riding)',
          riding_kind == 'leave' and 'leave REDACTED with Gleebs' in riding_prompt, riding_prompt)
    kind, _t = a._e_target()
    prompt = a.place_prompt(kind, None)
    hold_e(a, gleebs.LEAVE_HOLD + 0.1)
    check('with Nyx beside you in the light: hold E - "leave REDACTED with Gleebs"',
          kind == 'leave' and prompt == 'leave REDACTED with Gleebs' and a.gleebs_state == 'leaving')
    check('the leaving scene: no control (the world holds still), the HUD steps aside',
          a.world_frozen() and a.input_blocked() and a.hud_vitals.isHidden())
    z0 = a.human.getZ()
    rp = a.red_giant.getPos()
    cams = []
    for _ in range(int(gleebs.LEAVE_END / DT) + 3):
        a.survival_step(DT)
        a._place_camera(immediate=False, dt=DT)
        cams.append((a.gleebs_t, (a.camera.getPos() - rp).length()))
        if a.gleebs_t < gleebs.RISE_TIME * 0.9:
            rise = a.human.getZ() - z0
    near_crimson = min(dist for t, dist in cams if t > gleebs.CRIMSON_SHOT[0] + 0.5)
    check('Nyx and Orbit rise up the beam; then the camera finds Crimson, left lying below',
          rise > 30.0 and near_crimson < 45.0, f'rose {rise:.0f} m; camera {near_crimson:.0f} m from Crimson')
    words = (panel_words(a) + panel_buttons(a)) if a.panel is not None else []
    check('the end: "they left REDACTED" - Crimson perished with REDACTED - new journey / quit',
          a.gleebs_state == 'gone' and a.panel_name == 'ending' and a.human.isHidden() and a.giant.isHidden()
          and 'they left REDACTED' in words and any('perished with REDACTED' in w for w in words)
          and 'new journey' in words and 'quit' in words and a.stats.get('left_redacted') == 1,
          f'{a.gleebs_state}, {a.panel_name}, {words[:8]}')
    a.close_panel()
    a.survival_step(DT)
    check('the card comes back if closed (the journey is over)', a.panel_name == 'ending')
    a.close_panel()
    a.persist = True
    a.save_game('check')
    a.persist = False
    a.destroy()
    a = new_app()
    a.survival_step(DT)
    check('loading a journey that has ended shows the ending again', a.gleebs_state == 'gone'
          and a.panel_name == 'ending')
    a.persist = False
    a.destroy()

    # ------------------------------------------------------------ 8. a journey from before Pass 61
    save = json.loads((TMP / 'journey.json').read_text(encoding='utf-8'))
    save.pop('gleebs', None)
    save['ending_shown'] = True
    (TMP / 'journey.json').write_text(json.dumps(save), encoding='utf-8')
    a = new_app()
    for _ in range(int(7.0 / DT)):
        a.survival_step(DT)
    check('an older journey whose Crimson already lay dead: Gleebs comes a few seconds after loading',
          a.gleebs_state == 'arriving')
    a.persist = False
    a.destroy()

    # ------------------------------------------------------------ 9. the sounds
    man = json.loads((HERE / 'audio' / 'audio_manifest.json').read_text(encoding='utf-8'))
    names = ('lore_read', 'gleebs_arrive', 'gleebs_voice', 'gleebs_depart')
    check('sounds: an etching lighting, Gleebs arriving, speaking and the departure',
          all(n in man and (HERE / 'audio' / 'sfx' / f'{n}_01.wav').is_file() for n in names))

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
