"""Pass 48 — living giants: hunger, mood, tracks, crumbs, and the cold night.

THE RED GIANT
  Tracks you     with nothing else to do, it follows your footsteps - the trail you leave
                 (a breadcrumb every 10 m) - at a walk, wherever you went, however far.
  Hunger         rises all the time (empty to starving in ~8 minutes). Hungry (over half),
                 it plucks a blood branch out of the ground, kneels and eats it, leaving a
                 torn stump and a few crumbs. Crumbs are clues: find a stump it ate and you
                 learn how long ago, and which way it went.
  Mood           by day it is SNEAKY when fed and calm: it walks, keeps its distance and
                 stands very still while you look at it (look away and it creeps closer).
                 It is AGGRESSIVE when hungry (over 70%) or angry (3+ beatings) or woken:
                 it sees 30% farther and sprints at you.
  Night          the cold drains both giants. They move slower as their energy falls. When
                 the Red Giant runs out it hunches down and rests until dawn - unless you
                 walk up to it (18 m), which wakes it, furious.

INDIGO
  Energy         drains at night, returns by day. Low energy = slower. Nearly empty at
                 night, it hunches down to rest and will not follow (it still carries you).
  Food           blood-branch scraps are food for both of you. Indigo eats scraps from its
                 own bag when it is tired or hurt; give it some (T) or keep them for later.

YOU
  Cold           at night you get cold (the "heat" bar turns blue: cold). Warmth: stand
                 close to Indigo's body, ride on it, eat a blood scrap, or sleep. A shell
                 halves the cold. Frozen through, you lose life.
  Sleep          at night you can sleep curled against Indigo (Z beside it or riding it),
                 not only in a shell. Sleeping by Indigo does not move your camp.
Blood branches are the one common plant: food and healing for you, food for both giants.
"""
from __future__ import annotations

import math
from collections import deque

from panda3d.core import Point3, Vec3

import desert
from survival import K, _approach, _flat_dist

TRAIL_STEP = 10.0               # a breadcrumb every 10 m you walk
TRAIL_KEEP = 400                # the last 4 km of your trail
TRAIL_REACH = 6.0
RED_HUNGER_SECONDS = 480.0      # empty -> starving
RED_MEAL = 0.6                  # one branch fills it this much
FORAGE_HUNGER = 0.5
FORAGE_RANGE = 260.0
FORAGE_HUMAN_CLEAR = 45.0       # it will not stop to eat with you right beside it
AGGRESSIVE_HUNGER = 0.72
AGGRESSIVE_ANGER = 3
AGGRESSIVE_SIGHT = 1.3
WOKEN_RAGE = 90.0               # seconds of fury after being woken
NIGHT_DRAIN = 1.0 / 200.0       # energy per second at night (the night is ~4 minutes)
DAY_RECOVER = 1.0 / 150.0
REST_RECOVER = 1.0 / 400.0      # a resting giant claws a little back
RED_REST_ENERGY = 0.3
WAKE_RANGE = 18.0
SNEAK_WATCH_DEG = 38.0
SNEAK_FREEZE_RANGE = 150.0
INDIGO_REST_ENERGY = 0.2
INDIGO_EAT_ENERGY = 0.5
INDIGO_EAT_EVERY = 8.0
SCRAP_ENERGY = 0.25
SCRAP_HEALTH = 15.0
CHILL_MAX = 100.0
CHILL_RATE = CHILL_MAX / 160.0  # alone in the open, frozen through in under 3 minutes
CHILL_WARM = 14.0               # per second beside Indigo or riding it
CHILL_SHELL_MULT = 0.5
CHILL_DAY_DECAY = 6.0
CHILL_DAMAGE = 100.0 / 150.0    # life per second when frozen through
SCRAP_WARMTH = 20.0
INDIGO_WARM_RANGE = 14.0
CLUE_RANGE = 9.0
CLUE_FRESH = 90.0               # seconds: "moments ago"
MEAL_TAKE_AT = 1.6
MEAL_REACH = 9.0                # a meal only goes on while it is standing at the branch
TRACK_SPEED = 0.55              # Pass 49: following tracks at ~1.6-2 m/s: faster than a walk, a jog outpaces it
SNEAK_PURSUIT = 0.6             # Pass 49: creeping in on you (~2.2 m/s), between your walk and jog
PROVOKED_TIME = 30.0            # hit while busy, it drops everything and fights back
FORAGE_LOOK_EVERY = 1.0         # seconds between searches for a branch to eat
SAFE_SLEEP_STATES = ('idle', 'rest', 'track', 'forage', 'meal', 'lurk', 'flee', 'knocked_out', 'recovering', 'dead',
                     'dazed')            # Pass 54: the day after a knock-out it has lost you
desert.FOOD.setdefault('scraps', {'stamina': 15.0, 'health': 10.0, 'heat': 0.0})


class GiantsLifeMixin:
    red_meal = None

    def _init_giants_life(self):
        self.red_hunger = 0.35
        self.red_energy = 1.0
        self.red_resting = False
        self.red_woken_t = 0.0
        self.red_provoked_t = 0.0
        self._forage_look = 0.0
        self._forage_pick = None
        self.giant_energy = 1.0
        self.indigo_resting = False
        self.chill = 0.0
        self.trail: deque = deque(maxlen=TRAIL_KEEP)          # (serial, x, y)
        self._trail_serial = 0
        self._trail_last = Point3(self.human.getPos(self.render))
        self.red_trail_serial = None
        self._indigo_eat_t = INDIGO_EAT_EVERY
        self._clues_seen: set = set()
        for actor in (self.giant_actor, self.red_giant_actor):
            actor._load_clip(self.giant_glb, 'Crouch_Idle_Loop')   # hunched against the cold
        self.red_giant_actor._load_clip(self.giant_glb, 'Fixing_Kneeling')

    # ------------------------------------------------------------ moods and paces
    def red_mood(self) -> str:
        if self.red_woken_t > 0.0 or self.red_hunger >= AGGRESSIVE_HUNGER or self.red_anger >= AGGRESSIVE_ANGER:
            return 'aggressive'
        return 'sneaky'

    def red_pace(self) -> float:
        return (0.55 + 0.45 * self.red_energy) * (0.85 if self.is_night() else 1.0)

    def giant_pace(self) -> float:
        return (0.55 + 0.45 * self.giant_energy) * (0.85 if self.is_night() else 1.0)

    def red_detection_range(self) -> float:
        base = super().red_detection_range()
        return base * (AGGRESSIVE_SIGHT if self.red_mood() == 'aggressive' else 1.0)

    def red_watched(self) -> bool:
        """Is the camera looking at the Red Giant?"""
        cp = self.camera.getPos(self.render)
        rp = self.red_giant.getPos(self.render)
        d = Vec3(rp.x - cp.x, rp.y - cp.y, 0)
        if d.length() < 1e-3:
            return True
        want = math.degrees(math.atan2(d.x, d.y))
        rel = (want - self.heading + 180.0) % 360.0 - 180.0
        return abs(rel) <= SNEAK_WATCH_DEG

    def red_pursuit_style(self, distance: float) -> str:
        """'sprint', 'walk' or 'freeze' for the main pursuit code."""
        if self.red_mood() == 'aggressive':
            return 'sprint' if distance > K['RED_APPROACH_WALK_RANGE'] else 'walk'
        if K['RED_STOMP_RANGE'] + 10.0 < distance <= SNEAK_FREEZE_RANGE and self.red_watched() and self.human_alive:
            return 'freeze'
        return 'sneak'

    # ------------------------------------------------------------ the clock of the living
    def survival_step(self, dt: float):
        super().survival_step(dt)
        if not hasattr(self, 'giant_energy') or self.world_frozen():
            return
        self._record_trail()
        night = self.is_night()
        # Red Giant: hunger always, energy with the cold
        if not self.red_dead:
            self.red_hunger = min(1.0, self.red_hunger + dt / RED_HUNGER_SECONDS)
            if self.red_resting:
                self.red_energy = min(1.0, self.red_energy + REST_RECOVER * dt)
            elif night:
                self.red_energy = max(0.0, self.red_energy - NIGHT_DRAIN * dt)
            else:
                self.red_energy = min(1.0, self.red_energy + DAY_RECOVER * dt)
            self.red_woken_t = max(0.0, self.red_woken_t - dt)
            self.red_provoked_t = max(0.0, self.red_provoked_t - dt)
        # Indigo
        if self.giant_alive:
            if night and not self.indigo_resting:
                cold = self.indigo_cold_scale() if hasattr(self, 'indigo_cold_scale') else 1.0   # Pass 59: its glow
                self.giant_energy = max(0.0, self.giant_energy - NIGHT_DRAIN * cold * dt)
            elif not night:
                self.giant_energy = min(1.0, self.giant_energy + DAY_RECOVER * dt)
            self._indigo_eats(dt)
        # you
        self._update_chill(dt, night)
        self._check_clues()

    def _record_trail(self):
        if not self.human_alive or self.carried or self.hidden_shell is not None:
            return
        hp = self.human.getPos(self.render)
        if not self.trail or _flat_dist(hp, self._trail_last) >= TRAIL_STEP:
            self._trail_serial += 1
            self.trail.append((self._trail_serial, float(hp.x), float(hp.y)))
            self._trail_last = Point3(hp)

    def _indigo_eats(self, dt: float):
        self._indigo_eat_t -= dt
        if self._indigo_eat_t > 0.0:
            return
        self._indigo_eat_t = INDIGO_EAT_EVERY
        tired = self.giant_energy < INDIGO_EAT_ENERGY or self.giant_health < K['GIANT_MAX_HEALTH'] * 0.6
        if tired and self.bag('giant')['scraps'] > 0:
            self.bag('giant')['scraps'] -= 1
            self.giant_energy = min(1.0, self.giant_energy + SCRAP_ENERGY)
            self.giant_health = min(K['GIANT_MAX_HEALTH'], self.giant_health + SCRAP_HEALTH)
            if self.human_alive and _flat_dist(self.human.getPos(self.render), self.giant.getPos(self.render)) < 60.0:
                self.say('Nyx eats a blood scrap from its bag.', 2.0)

    def warm_beside_indigo(self) -> bool:
        if not self.giant_alive or not self.human_alive:
            return False
        if self.carried:
            return True
        return _flat_dist(self.human.getPos(self.render), self.giant.getPos(self.render)) <= INDIGO_WARM_RANGE

    def _update_chill(self, dt: float, night: bool):
        if not self.human_alive:
            return
        if self.warm_beside_indigo():
            self.chill = max(0.0, self.chill - CHILL_WARM * dt)
        elif night:
            rate = CHILL_RATE * (CHILL_SHELL_MULT if self.hidden_shell is not None else 1.0)
            self.chill = min(CHILL_MAX, self.chill + rate * dt)
        else:
            self.chill = max(0.0, self.chill - CHILL_DAY_DECAY * dt)
        if self.chill >= CHILL_MAX:
            self.human_health -= CHILL_DAMAGE * self.human_damage_scale() * dt
            if self.human_health <= 0.0:
                self.human_health = 0.0
                self.say('the cold takes you', 3.0)
                self._down_human()

    def eat(self):
        """Blood scraps are food too (after pods and gourds): life, breath and a little warmth."""
        if self.input_blocked() or not self.human_alive:
            return None
        if self.pooled_count('pod') or self.pooled_count('gourd') or (getattr(self, 'water_sips', 0) and self.heat >= 45.0):
            return super().eat()
        if self.pooled_count('scraps') <= 0:
            return super().eat()
        self.spend_pooled({'scraps': 1})
        fx = desert.FOOD['scraps']
        self.stamina = min(self.stamina_cap(), self.stamina + fx['stamina'])
        self.human_health = min(K['HUMAN_MAX_HEALTH'], self.human_health + fx['health'])
        self.chill = max(0.0, self.chill - SCRAP_WARMTH)
        self.sfx('eat', self.human.getPos(self.render))
        self.say('a blood scrap - salty, and warm going down', 2.0)
        return 'scraps'

    # ------------------------------------------------------------ clues
    def _check_clues(self):
        if not self.human_alive:
            return
        hp = self.human.getPos(self.render)
        for b in self.flora.branches_near(hp, CLUE_RANGE):
            if getattr(b, 'eaten_at', None) is None or b.pid in self._clues_seen:
                continue
            if _flat_dist(b.pos, hp) <= CLUE_RANGE:
                self._clues_seen.add(b.pid)
                age = self.flora.time - b.eaten_at
                when = 'moments ago' if age < CLUE_FRESH else 'a while ago'
                where = '' if self.red_dead else f'  Its tracks lead {self.bearing_words(self.red_giant.getPos(self.render))}.'
                self.say(f'Crumbs of blood branch around a torn stump. Crimson ate here, {when}.{where}', 4.5)
                return

    # ------------------------------------------------------------ Indigo in the cold
    def _update_companion(self, dt: float):
        rest = (self.giant_alive and self.is_night() and self.giant_energy < INDIGO_REST_ENERGY
                and not self.carried and self.comp.get('mode') not in ('pickup', 'setdown', 'carry')
                and not self.indigo_defending and self.controlled_name == 'human')
        if rest:
            if not self.indigo_resting:
                self.say('Nyx is too cold to walk. It hunches down to wait for the dawn.', 3.5)
            self.indigo_resting = True
            self.giant_motion_speed = 0.0
            self.giant_actor.apply_clip('Crouch_Idle_Loop', globalClock.getFrameTime())
            return
        self.indigo_resting = False
        super()._update_companion(dt)

    def _companion_word(self) -> str:
        if getattr(self, 'indigo_resting', False):
            return 'hunched against the cold'
        word = super()._companion_word()
        if self.giant_alive and getattr(self, 'giant_energy', 1.0) < 0.35:
            word += ', tired'
        return word

    # ------------------------------------------------------------ the Red Giant's day
    def _update_red_life(self, dt: float, clock_t: float) -> bool:
        """Runs inside the Red Giant's update after knock-out / bait / lurk. True = handled."""
        if not hasattr(self, 'red_energy'):
            return False
        hp = self.human.getPos(self.render)
        rp = self.red_giant.getPos(self.render)
        dist = _flat_dist(hp, rp)
        # Pass 49: hit while resting, eating or wandering, it drops everything and fights back
        if self.red_provoked_t > 0.0:
            if self.red_resting or self.red_meal is not None:
                self.red_resting = False
                self.red_meal = None
                self.red_woken_t = max(self.red_woken_t, WOKEN_RAGE * 0.5)
            return False
        # the night: rest when spent (walking up to it wakes it)
        if self.red_resting:
            if not self.is_night() or self.red_energy > 0.8:
                self.red_resting = False
            elif self.human_alive and dist <= WAKE_RANGE:
                self.red_resting = False
                self.red_woken_t = WOKEN_RAGE
                self.red_energy = max(self.red_energy, 0.5)
                self.sfx('roar_red_hunt', rp)
                self.say('Crimson wakes, and it is furious.', 3.0)
            else:
                self.red_state = 'rest'
                self.red_motion_speed = _approach(self.red_motion_speed, 0.0, K['GIANT_BRAKING'] * dt)
                self.red_giant_actor.apply_clip('Crouch_Idle_Loop', clock_t)
                return True
        if (self.is_night() and self.red_energy < RED_REST_ENERGY and dist > WAKE_RANGE * 1.5
                and self.red_state not in ('melee', 'stomp', 'overturn') and self.red_meal is None):
            self.red_resting = True
            self.red_state = 'rest'
            return True
        # a meal under way
        if self.red_meal is not None:
            self._update_red_meal(dt)
            return True
        # hungry: pluck a blood branch
        if self.red_hunger >= FORAGE_HUNGER and dist > FORAGE_HUMAN_CLEAR:
            b = self._forage_target(rp, dt)
            if b is not None:
                self.red_state = 'forage'
                d = self._red_walk_to(b.pos, dt, 6.5, walk_only=self.red_mood() == 'sneaky',
                                      speed_k=TRACK_SPEED if self.red_mood() == 'sneaky' else 1.0)
                if d <= 6.5:
                    self.red_meal = {'t': 0.0, 'branch': b, 'taken': False}
                return True
        # nothing to do: follow the human's tracks
        if self.human_alive and dist > self.red_detection_range() and self.trail:
            return self._red_track(dt, rp)
        return False

    def _forage_target(self, rp: Point3, dt: float = 0.0):
        """Nearest healthy branch within reach; looked up once a second through the flora's
        cell index (Pass 49: no per-frame scan of every branch ever grown)."""
        pick = self._forage_pick
        if pick is not None and not pick.smashed and not pick.poisoned:
            self._forage_look -= dt
            if self._forage_look > 0.0:
                return pick
        self._forage_look = FORAGE_LOOK_EVERY
        best, best_d = None, FORAGE_RANGE
        for b in self.flora.branches_near(rp, FORAGE_RANGE):
            if b.smashed or b.poisoned or b.grow < 1.0:
                continue
            d = _flat_dist(b.pos, rp)
            if d < best_d:
                best, best_d = b, d
        self._forage_pick = best
        return best

    def _update_red_meal(self, dt: float):
        m = self.red_meal
        b = m['branch']
        if _flat_dist(self.red_giant.getPos(self.render), b.pos) > MEAL_REACH:
            self.red_meal = None               # Pass 49: interrupted (knocked out, scared off): no meal
            return
        m['t'] += dt
        self.red_state = 'meal'
        self.red_motion_speed = _approach(self.red_motion_speed, 0.0, K['GIANT_BRAKING'] * dt)
        rp = self.red_giant.getPos(self.render)
        want = K['heading_toward'](b.pos.x - rp.x, b.pos.y - rp.y)
        delta = (want - self.red_motion_heading + 180.0) % 360.0 - 180.0
        turn = K['GIANT_TURN_RATE_DEG'] * dt
        self.red_motion_heading += max(-turn, min(turn, delta))
        self.red_giant.setH(self.red_motion_heading)
        dur = self.red_giant_actor.clips['Fixing_Kneeling']['duration']
        self.red_giant_actor.apply_clip('Fixing_Kneeling', min(m['t'], dur - 1e-4), loop=False)
        if not m['taken'] and m['t'] >= MEAL_TAKE_AT:
            m['taken'] = True
            if b.smashed:                      # someone got there first
                self.red_meal = None
                return
            self.flora.smash(b, crumbs=2)
            b.eaten_at = self.flora.time
            self._clues_seen.discard(b.pid)
            self._forage_pick = None
            self.sfx('branch_smash', b.pos)
            self.red_hunger = max(0.0, self.red_hunger - RED_MEAL)     # counted when it is eaten
            self.red_energy = min(1.0, self.red_energy + 0.2)
        if m['t'] >= dur:
            self.red_meal = None

    def _red_track(self, dt: float, rp: Point3) -> bool:
        """Walk along the human's breadcrumbs, oldest unvisited first."""
        newest = self.trail[-1][0]
        oldest = self.trail[0][0]
        s = self.red_trail_serial
        if s is None or s < oldest or s > newest:
            # join the trail at the breadcrumb nearest to it
            s = min(self.trail, key=lambda c: (c[1] - rp.x) ** 2 + (c[2] - rp.y) ** 2)[0]
        crumb = self.trail[s - oldest]
        target = Point3(crumb[1], crumb[2], 0.0)
        if _flat_dist(rp, target) <= TRAIL_REACH:
            if s >= newest:
                self.red_trail_serial = s
                return False                    # caught up with the newest print: idle / hunt
            s += 1
            crumb = self.trail[s - oldest]
            target = Point3(crumb[1], crumb[2], 0.0)
        self.red_trail_serial = s
        self.red_state = 'track'
        self._red_walk_to(target, dt, 1.0, walk_only=True, speed_k=TRACK_SPEED)
        return True

    # ------------------------------------------------------------ sleep beside Indigo
    def red_blocks_sleep(self) -> bool:
        """Pass 49: only a Red Giant that is coming for you keeps you awake - not one resting,
        eating, wandering or following old tracks."""
        return self.red_state not in SAFE_SLEEP_STATES

    def sleep_spot_beside_indigo(self) -> bool:
        return self.warm_beside_indigo()

    def _do_sleep(self):
        beside = self.hidden_shell is None
        super()._do_sleep()
        self.chill = 0.0
        self.giant_energy = 1.0
        self.indigo_resting = False
        if not self.red_dead:
            self.red_energy = 1.0
            self.red_resting = False
            self.red_hunger = min(1.0, self.red_hunger + 0.25)     # it went hungry all night
        if beside:
            self.say(f'day {self.day}.  you slept curled against Nyx, warm all night.', 3.5)

    # ------------------------------------------------------------ save
    def giants_life_snapshot(self) -> dict:
        return {'red_hunger': round(self.red_hunger, 3), 'red_energy': round(self.red_energy, 3),
                'red_resting': self.red_resting, 'red_woken_t': round(self.red_woken_t, 1),
                'giant_energy': round(self.giant_energy, 3),
                'chill': round(self.chill, 2), 'trail': [[round(x, 1), round(y, 1)] for _s, x, y in list(self.trail)[-80:]]}

    def apply_giants_life(self, d: dict):
        if not d:
            return
        self.red_hunger = float(d.get('red_hunger', self.red_hunger))
        self.red_energy = float(d.get('red_energy', self.red_energy))
        self.red_resting = bool(d.get('red_resting', False))
        self.red_woken_t = float(d.get('red_woken_t', 0.0))
        self.giant_energy = float(d.get('giant_energy', self.giant_energy))
        self.chill = float(d.get('chill', 0.0))
        self.trail.clear()
        for x, y in d.get('trail', []):
            self._trail_serial += 1
            self.trail.append((self._trail_serial, float(x), float(y)))
        if self.trail:
            self._trail_last = Point3(self.trail[-1][1], self.trail[-1][2], 0.0)
        self.red_trail_serial = None
