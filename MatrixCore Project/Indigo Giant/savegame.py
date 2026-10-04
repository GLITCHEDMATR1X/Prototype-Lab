"""Pass 43 — the journey is saved.

Where:  %LOCALAPPDATA%\\GLITCHED MATRIX\\INDIGO GIANT\\journey.json   (Windows)
        ~/.local/share/glitched-matrix/indigo-giant/journey.json      (elsewhere)
        (INDIGO_SAVE_DIR overrides, used by the tests)
When:   every 2 minutes, when you sleep, on F5, and when you quit (Esc menu or closing the window).
New:    run with --new, or choose "new journey" in the Esc menu (the old file is kept as .bak).

The file stores the world as a list of *changes* from the seed-generated desert (dug finds,
moved / patched / flipped shells, smashed or planted branches, visited landmarks) plus the
characters. Players are stored as a list ("players": [...]) so co-op can add more later.
"""
from __future__ import annotations

import ast
import json
import os
import sys
import time
from pathlib import Path

from panda3d.core import Point3

import desert_world
import flora
from survival import K

SAVE_VERSION = 1
SAVE_NAME = 'journey.json'
AUTOSAVE_SECONDS = 120.0


def save_folder(override: Path | None = None) -> Path:
    if override is not None:
        return Path(override)
    env = os.environ.get('INDIGO_SAVE_DIR')
    if env:
        return Path(env)
    if sys.platform.startswith('win'):
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
        return base / 'GLITCHED MATRIX' / 'INDIGO GIANT'
    return Path.home() / '.local' / 'share' / 'glitched-matrix' / 'indigo-giant'


def backup_unreadable(folder: Path) -> Path | None:
    """Pass 44 (B5): move a save we cannot use aside, so the next autosave never destroys it."""
    path = Path(folder) / SAVE_NAME
    if not path.is_file():
        return None
    dest = path.with_name(f'journey.unreadable-{time.strftime("%Y%m%d-%H%M%S")}.json')
    try:
        os.replace(path, dest)
    except OSError as exc:
        print(f'[save] could not back up {path.name}: {exc}')
        return None
    print(f'[save] kept the old journey as {dest.name}')
    return dest


def read_save(folder: Path):
    path = Path(folder) / SAVE_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('not a journey object')
    except (OSError, ValueError) as exc:
        print(f'[save] could not read {path}: {exc} - starting a new journey')
        backup_unreadable(folder)
        return None
    if data.get('version') != SAVE_VERSION:
        print(f'[save] {path.name} is from another version - starting a new journey')
        backup_unreadable(folder)
        return None
    return data


def _pid(p) -> str:
    return repr(p)


def _unpid(s: str):
    return ast.literal_eval(s)


def _xyz(p) -> list:
    return [round(float(p.x), 3), round(float(p.y), 3), round(float(p.z), 3)]


class SaveMixin:
    def _init_save(self):
        self._autosave_t = AUTOSAVE_SECONDS
        self.last_save_reason = ''
        self.bind_action('quick_save', self.save_game, ['quick save'])
        # apply dug finds as their cells stream in
        self.finds.dug_pids = set()

    # ------------------------------------------------------------------ save
    def snapshot(self) -> dict:
        hp = self.human.getPos(self.render)
        gp = self.giant.getPos(self.render)
        rp = self.red_giant.getPos(self.render)
        shells = []
        for s in self.shells.shells.values():
            pos = s.pos
            shells.append({'pid': _pid(s.pid), 'pos': _xyz(pos), 'heading': round(s.heading, 2),
                           'state': s.state})          # Pass 44 (B14): a shell mid-overturn loads overturned
        branches = []
        for b in self.flora.branches.values():
            if b.smashed or b.pid[0] == 'planted' or b.poisoned:
                branches.append({'pid': _pid(b.pid), 'pos': _xyz(b.pos), 'variant': b.variant,
                                 'heading': round(b.heading, 2), 'smashed': b.smashed,
                                 'regrow_left': round(b.regrow_left, 1), 'grow': round(b.grow, 3),
                                 'poisoned': bool(b.poisoned),
                                 'eaten_age': (round(self.flora.time - b.eaten_at, 1)
                                               if getattr(b, 'eaten_at', None) is not None else None)})
        camp = getattr(self, 'camp_shell', None)
        hidden = getattr(self, 'hidden_shell', None)
        held = getattr(self, 'giant_held_shell', None)
        mode = self.comp.get('mode', 'stay')
        if self.carried:
            mode = 'carry'                       # a lift / set-down in progress saves as riding
        elif mode not in ('follow', 'stay', 'shade'):
            mode = 'stay'                        # go-there and half-finished lifts just wait
        return {
            'version': SAVE_VERSION,
            'saved_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'seed': self.seed,
            'day': self.day, 'hour': round(self.hour, 3), 'nights_slept': self.nights_slept,
            'chapter': self.landmarks.chapter,
            'players': [{
                'id': 'p1',
                'pos': _xyz(hp), 'heading': round(self.human.getH(), 2),
                'health': round(self.human_health, 2), 'heat': round(self.heat, 2),
                'stamina': round(self.stamina, 2), 'bag': dict(self.bag('human')),
                'upgrades': sorted(self.upgrades), 'water_sips': self.water_sips,
                'hidden_shell': _pid(hidden.pid) if hidden is not None else None,
                'carried': bool(self.carried),
            }],
            'giant': {'pos': _xyz(gp), 'heading': round(self.giant.getH(), 2),
                      'health': round(self.giant_health, 2), 'bag': dict(self.bag('giant')),
                      'mode': mode, 'held_shell': _pid(held.pid) if held is not None else None},
            'red': {'pos': _xyz(rp), 'health': round(self.red_health, 2), 'anger': self.red_anger,
                    'lurking': self.red_lurking, 'lurk_elapsed': round(self.red_lurk_elapsed, 1),
                    'knocked_out': bool(self.red_knocked_out),
                    'ko_remaining': round(float(getattr(self, 'red_knockout_remaining', 0.0)), 1),
                    'ko_elapsed': round(float(getattr(self, 'red_knockout_elapsed', 0.0)), 1),     # Pass 54
                    'fleeing': bool(self.red_fleeing or self.red_recovering),
                    'dead': bool(self.red_dead or self.red_eating is not None),   # Pass 47: the ending
                    'heading': round(self.red_giant.getH(), 2)},
            'ending_shown': bool(getattr(self, 'ending_shown', False)),
            'tutorial': getattr(self, 'teach_step', None),                  # Pass 50: first-dawn hints
            'life': self.giants_life_snapshot() if hasattr(self, 'giants_life_snapshot') else {},   # Pass 48
            'world': {
                'finds_dug': sorted(_pid(f.pid) for f in self.finds.finds.values() if f.dug)
                + sorted(self.finds.dug_pids - {_pid(f.pid) for f in self.finds.finds.values()}),
                'shells': shells,
                'branches': branches,
                'landmarks_visited': [lm.idx for lm in self.landmarks.items if lm.visited],
                'landmarks_revealed': [lm.idx for lm in self.landmarks.items if lm.revealed],
                'camp': _pid(camp.pid) if camp is not None else None,
                'places': self.places_snapshot() if hasattr(self, 'places_snapshot') else {},   # Pass 46
                'fight': self.fight_snapshot() if hasattr(self, 'fight_snapshot') else {},      # Pass 53
                'glow': self.glow_snapshot() if hasattr(self, 'glow_snapshot') else {},         # Pass 59
            },
            'stats': dict(self.stats),
            'lore': list(self.lore_log),
            'etchings': self.lore_snapshot() if hasattr(self, 'lore_snapshot') else [],        # Pass 61
            'gleebs': self.gleebs_snapshot() if hasattr(self, 'gleebs_snapshot') else {},       # Pass 61
        }

    def save_game(self, reason: str = 'autosave') -> bool:
        if not getattr(self, 'persist', False) or not self.human_alive:
            return False
        try:
            folder = Path(self.save_dir)
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / SAVE_NAME
            tmp = path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.snapshot(), indent=1), encoding='utf-8')
            os.replace(tmp, path)          # atomic: a crash mid-save never corrupts the journey
        except OSError as exc:
            print(f'[save] could not save: {exc}')
            return False
        self.last_save_reason = reason
        self._autosave_t = AUTOSAVE_SECONDS
        if reason in ('quick save', 'slept'):
            self.flash_saved() if hasattr(self, 'flash_saved') else None
        return True

    def new_journey_file(self):
        """Keep the old journey as a backup and start fresh next launch."""
        path = Path(self.save_dir) / SAVE_NAME
        if path.is_file():
            os.replace(path, path.with_suffix('.bak'))

    def survival_step(self, dt: float):
        super().survival_step(dt)
        if getattr(self, 'persist', False) and not self.world_frozen():
            self._autosave_t -= dt
            if self._autosave_t <= 0.0:
                self.save_game('autosave')

    def userExit(self):
        if getattr(self, 'persist', False) and getattr(self, 'human', None) is not None:
            self.save_game('quit')
        super().userExit()

    # ------------------------------------------------------------------ load
    def apply_pending_save(self):
        data = self.pending_save
        self.pending_save = None
        if not data:
            return False
        try:
            self._apply_save(data)
        except Exception as exc:          # a damaged save must not stop the game
            print(f'[save] could not apply the saved journey ({exc}); starting fresh')
            backup_unreadable(self.save_dir)
            return False
        self.cam_target = self._controlled_focus()     # Pass 44 (B15): stream around where you are
        self.loaded_from_save = True                    # Pass 50: the title offers "continue"
        self._refresh_world(force=True)
        self._update_stream(force=True)
        self.drain_stream_queue()
        if hasattr(self, '_snd'):                       # Pass 44: no landmark stinger on every load
            self._snd['visited'] = self.landmarks.visited_count()
        self.say(f'day {self.day}.  the journey continues.', 3.0)
        return True

    def _apply_save(self, d: dict):
        self.day = int(d.get('day', 1))
        t = d.get('tutorial')
        self.teach_step = int(t) if isinstance(t, int) else 99      # older journeys: hints already past
        self.hour = float(d.get('hour', 7.0))
        self.nights_slept = int(d.get('nights_slept', 0))
        for _ in range(2, int(d.get('chapter', 1)) + 1):
            self.landmarks.add_chapter()
        w = d.get('world', {})
        if hasattr(self, 'apply_places'):
            self.apply_places(w.get('places', {}))          # Pass 46: places found / searched
        visited = set(w.get('landmarks_visited', []))
        revealed = set(w.get('landmarks_revealed', []))
        for lm in self.landmarks.items:
            lm.visited = lm.idx in visited
            lm.revealed = lm.idx in revealed or lm.visited
        # finds: mark dug now if known, and remember the rest for when their cells stream in
        self.finds.dug_pids = set(w.get('finds_dug', []))
        for f in self.finds.finds.values():
            if _pid(f.pid) in self.finds.dug_pids:
                f.dug = True
                self.finds._clear(f)
        # shells: exact positions and states
        for rec in w.get('shells', []):
            pid = _unpid(rec['pid'])
            x, y, z = rec['pos']
            s = self.shells.shells.get(pid)
            if s is None:
                s = desert_world.Shell(pid, Point3(x, y, z), rec['heading'], rec['state'])
                self.shells.shells[pid] = s
            else:
                s.pos, s.heading, s.state = Point3(x, y, z), rec['heading'], rec['state']
            self.shells.settle(s)          # Pass 57: its levelled sand (lost on every load before)
            if s.node is not None:
                self.shells._show(s)
        camp = w.get('camp')
        self.camp_shell = self.shells.shells.get(_unpid(camp)) if camp else None
        # branches: smashed ones and the ones you planted
        for rec in w.get('branches', []):
            pid = _unpid(rec['pid'])
            x, y, z = rec['pos']
            b = self.flora.branches.get(pid)
            if b is None:
                b = flora.BloodBranch(pid, Point3(x, y, z), rec['variant'], rec['heading'])
                self.flora.branches[pid] = b
                if pid[0] == 'planted':
                    self.flora.planted.append(b)
            b.smashed = bool(rec['smashed'])
            b.regrow_left = float(rec['regrow_left'])
            if b.smashed:
                self.flora.regrowing[pid] = b
            b.grow = float(rec.get('grow', 1.0))
            if rec.get('poisoned', False) and not b.smashed:
                self.flora.set_poisoned(b)
            if b.smashed and rec.get('eaten_age') is not None:       # Pass 49: the clue survives a load
                b.eaten_at = self.flora.time - float(rec['eaten_age'])
            self.flora._index(b)
            if b.node is not None or b.stump is not None:
                self.flora._spawn(b)
        # characters
        p = (d.get('players') or [{}])[0]
        if p:
            x, y, z = p['pos']
            self.human.setPos(x, y, self.field.height(x, y) - self.human_actor.height_world * K['GROUND_SINK_FRACTION'])
            self.human.setH(p.get('heading', 0.0))
            self.human_health = float(p.get('health', 100.0))
            self.heat = float(p.get('heat', 0.0))
            self.stamina = float(p.get('stamina', 100.0))
            self.bag('human').clear()
            self.bag('human').update({k: int(v) for k, v in p.get('bag', {}).items()})
            self.upgrades = set(p.get('upgrades', []))
            self.water_sips = int(p.get('water_sips', 0))
        g = d.get('giant', {})
        if g:
            x, y, z = g['pos']
            self.giant.setPos(x, y, self.field.height(x, y) - self.giant_actor.height_world * K['GROUND_SINK_FRACTION'])
            self.giant.setH(g.get('heading', 205.0))
            self.giant_motion_heading = self.giant.getH()
            self.giant_health = float(g.get('health', 100.0))
            self.giant_alive = self.giant_health > 0.0
            self.bag('giant').clear()
            self.bag('giant').update({k: int(v) for k, v in g.get('bag', {}).items()})
        r = d.get('red', {})
        if r:
            x, y, z = r['pos']
            self.red_giant.setPos(x, y, self.field.height(x, y))
            self.red_health = float(r.get('health', 100.0))
            self.red_anger = int(r.get('anger', 0))
            anger = self.red_anger
            # Pass 47: a dead Red Giant lies where it fell.
            # Pass 44 (B8): a knocked-out or fleeing Red Giant stays that way after a load.
            if r.get('dead'):
                self.red_giant.setH(float(r.get('heading', 0.0)))
                self.ending_shown = bool(d.get('ending_shown', True))
                self.red_giant_dies()
            elif r.get('knocked_out') or (self.red_health <= 0.0 and not r.get('lurking')):
                self._knock_out_red()
                self.red_knockout_remaining = float(r.get('ko_remaining', 0.0)) or self.red_knockout_remaining
                self.red_knockout_elapsed = float(r.get('ko_elapsed', 1e3))      # it has already fallen
            elif r.get('lurking'):
                self.red_begin_lurk()
                self.red_lurk_elapsed = float(r.get('lurk_elapsed', 0.0))
            elif r.get('fleeing'):
                self.red_fleeing = True
                self.red_flee_elapsed = 0.0
                self.red_state = 'flee'
            else:
                self.red_scare_check()           # a badly hurt Red Giant keeps its distance
            self.red_anger = anger
        if hasattr(self, 'apply_fight'):
            self.apply_fight(w.get('fight', {}))            # Pass 53: stamina, Indigo down, the red one's calm, poison
        if hasattr(self, 'apply_glow'):
            self.apply_glow(w.get('glow', {}))              # Pass 59: the glow you carry, Indigo's glow
        # Pass 44 (B7): hidden in a shell, riding Indigo, the shell Indigo holds, the companion mode
        shells = self.shells.shells
        held = g.get('held_shell') if g else None
        hs = shells.get(_unpid(held)) if held else None
        if hs is not None and self.giant_alive and not hs.occupied:
            hs.held = True
            self.giant_held_shell = hs
            if hs.node is not None:
                self.shells._show(hs)
        mode = (g or {}).get('mode', 'stay')
        hidden = p.get('hidden_shell') if p else None
        s = shells.get(_unpid(hidden)) if hidden else None
        if s is not None and not s.held and self.human_alive:
            # Pass 55: stay where you stood inside it (an older save put you at its very middle)
            inside = self.shells.inside(self.human.getPos(self.render), ('intact',)) is s
            self.enter_shell(s, walked_in=inside)
            self.red_saw_hide = False
        elif p and p.get('carried') and self.giant_alive and self.human_alive:
            self.carried = True
            mode = 'carry'
        if mode in ('follow', 'stay', 'shade', 'carry') and self.giant_alive and (mode != 'carry' or self.carried):
            self.comp.update({'mode': mode, 'phase': '', 'elapsed': 0.0, 'target': None, 'moving': False,
                              'lift_from': None, 'lower_to': None})
        if hasattr(self, 'apply_giants_life'):
            self.apply_giants_life(d.get('life', {}))       # Pass 48: hunger, energy, cold, your trail
        self.stats.clear()
        self.stats.update(d.get('stats', {}))
        self.lore_log = list(d.get('lore', []))
        if self.red_dead:                    # Pass 49: saved during its last meal - finish the story
            ended = 'Crimson ate the pale branch and lay down, and did not get up.'
            if ended not in self.lore_log:
                self.lore_log.append(ended)
            self.stats['red_ended'] = 1
            for b in list(self.flora.poisoned.values()):
                self.flora.smash(b, crumbs=0)
        if hasattr(self, 'apply_lore'):
            self.apply_lore(d.get('etchings', []))          # Pass 61: the etchings you have read
        if hasattr(self, 'apply_gleebs'):
            self.apply_gleebs(d.get('gleebs', {}))          # Pass 61: Gleebs waiting, or the journey over
        self._apply_time(force=True)
