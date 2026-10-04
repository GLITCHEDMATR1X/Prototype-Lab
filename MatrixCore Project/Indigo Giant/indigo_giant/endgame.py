"""Pass 47 — the only ending: the pale bloom and the Red Giant's last meal.

Nothing can kill the Red Giant - it only gets knocked out, flees, lurks and comes back
angrier - until you find a very rare plant, the PALE BLOOM (places.py):

  1. Find a pale bloom. One always grows about 3 km from where you start; a few more grow,
     very rarely, farther out. Camps, painted totem poles and the sitting statues point the
     way, and Indigo grows uneasy near one.
  2. Tear it up (hold E): you get 3 pale scraps.
  3. Work a pale scrap into a living blood branch (hold E) - the Red Giant's favourite food.
     The branch's red veins turn the colour of bone. It no longer heals you.
  4. The Red Giant smells it from anywhere. It stops hunting you, comes for the branch,
     tears it up and eats it... and does not get up again.

After that the desert is yours: the journey (trail, places, camp, making things) goes on
without the Red Giant. The ending is saved.
"""
from __future__ import annotations

from panda3d.core import Point3, Vec3

from . import flora
from .survival import K, _approach, _flat_dist

RED_BAIT_FAR = 520.0            # farther than this, it is brought to the edge of the haze...
RED_BAIT_ARRIVE = 450.0         # ...this far from the branch (beyond sight), and walks the rest
RED_EAT_REACH = 7.0
EAT_TAKE_AT = 1.6               # kneeling, it tears the branch out of the ground
SICKEN_TIME = 2.6               # staggering
ENDING_DELAY = 3.5              # after it falls, the ending card
POISON_COST = {'bane': 1}
POISON_TIME = 2.0
EAT_CANCEL_REACH = 9.0          # knocked away from the branch mid-meal: the meal is off


class EndgameMixin:
    red_eating = None
    _poison_job = None
    ending_shown = False
    _bait_announced = False
    _ending_t = None

    def _init_endgame(self):
        self.red_eating = None
        self.ending_shown = False
        self._bait_announced = False
        self.red_giant_actor._load_clip(self.giant_glb, 'Fixing_Kneeling')   # kneels to eat
        self._poison_job = None
        self.bind_action('poison', self._on_poison_press)

    # ------------------------------------------------------------ poisoning a branch
    # Pass 49: its own key (X, rebindable) so carrying pale scraps never takes over E
    # (hide / dig / smash stay where they were).
    def poison_target(self):
        if (self.controlled_name != 'human' or not self.human_alive or self.carried or self.red_dead
                or getattr(self, 'hidden_shell', None) is not None or self.pooled_count('bane') <= 0):
            return None
        return self.flora.nearest_intact(self.human.getPos(self.render), flora.SMASH_RANGE_HUMAN, healthy_only=True)

    def _on_poison_press(self):
        if self.input_blocked() or self._poison_job is not None:
            return
        if self.pooled_count('bane') <= 0 or self.red_dead:
            return
        b = self.poison_target()
        if b is None:
            self.say('stand beside a living blood branch', 1.5)
            return
        self._poison_job = {'branch': b, 't': 0.0, 'from': Point3(self.human.getPos(self.render))}

    def poison_prompt(self):
        """(text, progress) for the HUD, or None."""
        job = self._poison_job
        if job is not None:
            return 'work a pale scrap into the branch', min(1.0, job['t'] / POISON_TIME)
        if self.poison_target() is not None:
            return 'work a pale scrap into the branch', 0.0
        return None

    def _update_poison_job(self, dt: float):
        job = self._poison_job
        if job is None:
            return
        b = job['branch']
        moved = _flat_dist(self.human.getPos(self.render), job['from']) > 1.2
        if moved or not self.human_alive or self.carried or b.smashed or b.poisoned or self.input_blocked():
            self._poison_job = None
            return
        job['t'] += dt
        clip = self.human_actor.clips['Fixing_Kneeling']
        self.human_actor.apply_clip('Fixing_Kneeling', min(job['t'], clip['duration'] - 1e-4), loop=False)
        if job['t'] >= POISON_TIME:
            self._poison_job = None
            self.human_actor.apply_clip('Idle_Loop', 0.0, force=True)
            self.poison_branch(b)

    def poison_branch(self, target) -> bool:
        if target is None or target.smashed or target.poisoned or not self.spend_pooled(POISON_COST):
            return False
        self.flora.set_poisoned(target)
        self.stats['poisoned'] += 1
        self._bait_announced = False
        self.sfx('patch', target.pos)
        self.say('You work the pale scrap into the branch. Its red veins turn the colour of bone.', 4.0)
        self.lore_log.append('You poisoned a blood branch with the pale bloom.')
        return True

    # ------------------------------------------------------------ the Red Giant's hunger
    def current_bait(self):
        """The poisoned branch nearest the Red Giant (Pass 49: from the flora's small poisoned
        set, not a scan of every branch)."""
        best, best_d = None, None
        rp = self.red_giant.getPos(self.render)
        for b in self.flora.poisoned.values():
            if b.smashed:
                continue
            d = _flat_dist(b.pos, rp)
            if best_d is None or d < best_d:
                best, best_d = b, d
        return best

    def _update_red_endgame(self, dt: float, clock_t: float) -> bool:
        """Runs inside the Red Giant's update (after knock-out / flee). True = handled."""
        if self.red_eating is not None:
            self._update_red_eating(dt)
            return True
        bait = self.current_bait()
        if bait is None:
            return False
        rp = self.red_giant.getPos(self.render)
        if _flat_dist(rp, bait.pos) > RED_BAIT_FAR:
            # it has been following you from far off: bring it to the edge of the haze
            d = Vec3(rp.x - bait.pos.x, rp.y - bait.pos.y, 0)
            if d.length() < 1e-3:
                d = Vec3(1, 0, 0)
            d.normalize()
            x, y = bait.pos.x + d.x * RED_BAIT_ARRIVE, bait.pos.y + d.y * RED_BAIT_ARRIVE
            self.red_giant.setPos(x, y, self.field.height(x, y) - self.red_giant_actor.height_world * K['GROUND_SINK_FRACTION'])
        if not self._bait_announced:
            self._bait_announced = True
            self.sfx('roar_red_return', self.red_giant.getPos(self.render))
            self.say('Far off, Crimson lifts its head. It has smelled the branch.', 4.0)
        self.red_lurking = False
        self.red_returning = False
        self.red_state = 'bait'
        self.attack_states['red'].update({'active': False, 'elapsed': 0.0, 'hit_done': False})
        d = self._red_walk_to(bait.pos, dt, RED_EAT_REACH)
        if d <= RED_EAT_REACH:
            self.red_eating = {'phase': 'eat', 't': 0.0, 'branch': bait, 'taken': False}
            self.red_motion_speed = 0.0
            self.say('Crimson kneels over the pale branch.', 3.0)
        return True

    def _face_point_red(self, p: Point3, dt: float):
        rp = self.red_giant.getPos(self.render)
        want = K['heading_toward'](p.x - rp.x, p.y - rp.y)
        delta = ((want - self.red_motion_heading + 180.0) % 360.0) - 180.0
        turn = K['GIANT_TURN_RATE_DEG'] * dt
        self.red_motion_heading += max(-turn, min(turn, delta))
        self.red_giant.setH(self.red_motion_heading)

    def _update_red_eating(self, dt: float):
        e = self.red_eating
        e['t'] += dt
        clips = self.red_giant_actor.clips
        self.red_motion_speed = _approach(self.red_motion_speed, 0.0, K['GIANT_BRAKING'] * dt)
        if e['phase'] == 'eat':
            b = e['branch']
            if not e['taken'] and _flat_dist(self.red_giant.getPos(self.render), b.pos) > EAT_CANCEL_REACH:
                self.red_eating = None             # Pass 49: interrupted - it will come back for it
                return
            self.red_state = 'eating'
            self._face_point_red(b.pos, dt)
            dur = clips['Fixing_Kneeling']['duration']       # kneel, eat with both hands, stand
            t = e['t']
            self.red_giant_actor.apply_clip('Fixing_Kneeling', min(t, dur - 1e-4), loop=False)
            if not e['taken'] and t >= EAT_TAKE_AT:
                e['taken'] = True
                self.flora.smash(b)                         # torn out of the ground and eaten
                self.sfx('branch_smash', b.pos)
            if t >= dur:
                e.update(phase='sicken', t=0.0)
                self.say('Crimson stands. It sways. Something is wrong inside it.', 3.5)
                self.sfx('roar_red_scared', self.red_giant.getPos(self.render))
        elif e['phase'] == 'sicken':
            self.red_state = 'sick'
            dur = clips['Hit_Chest']['duration']
            self.red_giant_actor.apply_clip('Hit_Chest', e['t'] % dur, loop=False)
            if e['t'] >= SICKEN_TIME:
                e.update(phase='fall', t=0.0)
                self.sfx('roar_red_ko', self.red_giant.getPos(self.render))
        elif e['phase'] == 'fall':
            dur = clips['Death01']['duration']
            self.red_giant_actor.apply_clip('Death01', min(e['t'], dur - 1e-4), loop=False)
            if e['t'] >= dur:
                self.red_giant_dies()

    def red_giant_dies(self):
        """The end of the Red Giant (also used when a save with it dead is loaded)."""
        self.red_eating = None
        self.red_dead = True
        self.red_alive = False
        self.red_health = 0.0
        self.red_state = 'dead'
        self.red_knocked_out = self.red_recovering = self.red_fleeing = self.red_lurking = False
        self.red_returning = False
        self.red_motion_speed = 0.0
        self.indigo_defending = False
        self.attack_states['red'].update({'active': False, 'elapsed': 0.0, 'hit_done': False})
        self.red_giant_actor.apply_clip('Death01', self.red_giant_actor.clips['Death01']['duration'] - 1e-4,
                                        force=True, loop=False)
        if not self.ending_shown:
            self.stats['red_ended'] = 1
            self.lore_log.append('Crimson ate the pale branch and lay down, and did not get up.')
            self._ending_t = ENDING_DELAY

    def survival_step(self, dt: float):
        super().survival_step(dt)
        if not self.world_frozen():
            self._update_poison_job(dt)
        t = self._ending_t
        if t is None or self.ending_shown or self.world_frozen():
            return
        self._ending_t = t - dt
        if self._ending_t <= 0.0:
            self._ending_t = None
            self.show_ending()

    def show_ending(self):
        self.ending_shown = True
        if hasattr(self, 'save_game'):
            self.save_game('the end')
        if hasattr(self, 'toggle_panel'):
            self.toggle_panel('ending')

    def ending_lines(self):
        def n(count, one, many):
            return f'{count} {one if count == 1 else many}'
        places_found = self.places.found_count() if getattr(self, 'places', None) else 0
        return [
            f'{n(self.day, "day", "days")} in the desert,  {n(self.nights_slept, "night", "nights")} slept in shells',
            f'{n(self.landmarks.visited_count(), "marker", "markers")} studied,  '
            f'{n(places_found, "place", "places")} found',
            f'{n(self.stats["finds_dug"], "find", "finds")} dug,  {n(self.stats["planted"], "seed", "seeds")} planted',
        ]
