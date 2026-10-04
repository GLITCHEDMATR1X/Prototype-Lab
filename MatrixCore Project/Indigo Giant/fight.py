"""Pass 53 — giants with stamina, knock-outs you can wake from, a day's calm, and poison.

STAMINA   Both giants have fight stamina (the thin bar under Indigo's life).
          - Throwing a punch costs a little.
          - Taking a hit costs more, and leaves a small wound in life (blood branches heal it).
          - Between blows they catch their breath slowly; once the fight stops, quickly.
          - Cold, tired giants (Pass 48 energy) recover more slowly.
          - Hurrying (sprint) wears Indigo a little.
KNOCK-OUT A giant goes down only when a hit lands while it is EXHAUSTED (no stamina left),
          or when its life truly runs out. Before Pass 53, four hits knocked a giant down
          (about five seconds of punching); now a straight fight lasts about half a minute.
          A sneaky (fed, calm) Red Giant runs off when it is nearly spent. An aggressive one
          fights until it drops.

INDIGO DOWN
          Tap E beside it (three shakes) to wake it. It gets up slowly with a little stamina
          and some life back. Left alone, it wakes by itself at dawn.

RED DOWN  It lies down for 2.5 minutes - time to run. It gets up dazed and has lost you for
          a whole day:
            - it wanders, eats and rests, but does not hunt you or follow your tracks
          After that day it finds your trail again and follows it. Hit it while it is dazed
          and the calm is over.

POISON    Carrying pale scraps (from the pale bloom)? Tap E beside the knocked-out red one
          to push one between its teeth. Each dose (up to 3):
            - its stamina: -20%
            - the force of its blows: -15%
            - its pace: -8%
            - how far it sees you: -10%
            - it stays down a minute longer
          The poisoned blood branch is still the only thing that ends it.
"""
from __future__ import annotations

import math
import random

from panda3d.core import Point3, Vec3

from survival import K, _flat_dist

STAMINA_MAX = {'giant': 120.0, 'red': 100.0}
PUNCH_COST = 2.0
EXHAUSTED = PUNCH_COST          # too tired to throw a punch = exhausted: the next hit knocks it down
HIT_STAMINA = 4.5               # stamina a landed hit takes
HIT_HEALTH = 2.5                # the wound it leaves
REGEN_FIGHTING = 1.0            # per second between blows
REGEN_CALM = 12.0               # per second once no blow has been thrown or taken for CALM_AFTER s
CALM_AFTER = 3.0
SPRINT_DRAIN = 1.5              # Indigo hurrying
RED_FLEE_STAMINA = 0.22         # a sneaky red one runs when this spent

WAKE_TAPS = 3
WAKE_RANGE = 16.0               # metres from Indigo's body (it lies ~20 m long)
WAKE_TAP_GAP = 2.5              # taps further apart than this start over
GETUP_TIME = 1.8
WAKE_HEALTH = 45.0
WAKE_STAMINA = 0.4              # of full

# Pass 58: fighting as Indigo (you control it)
#   tap left mouse / F      a punch; jab and cross alternate. Pressed during a punch, the next
#                           one is queued and cuts in once the blow has landed: combos flow.
#   hold, then let go       a two-handed hammer blow: Indigo winds up while you hold, then
#                           strikes twice. It costs more, hits harder, drives the red one back
#                           and staggers it.
#   aim                     each blow turns Indigo to the red one and steps in if it is just
#                           out of reach; a blow lands only where Indigo faces.
HEAVY_COST = 5.0                # the hammer blow (a punch is PUNCH_COST)
TAP_TIME = 0.18                 # held shorter than this: a punch
CHARGE_FULL = 0.45              # held this long: the hammer blow is ready (let go to strike)
WINDUP_END = 0.31               # the hammer blow's wind-up, in its clip (Sword_Attack)
CHAIN_AFTER_HIT = 0.16          # a queued blow cuts in this long after the last one landed
ASSIST_RANGE = 12.0             # a blow turns Indigo toward the red one this close...
ASSIST_ARC = 110.0              # ...if it is within this angle of where Indigo faces
ASSIST_TURN = 420.0             # deg/s
LUNGE_CLOSE = 4.6               # step in to this distance (a punch reaches 5.4)
LUNGE_SPEED = 11.0              # m/s, during the wind-up only
HIT_ARC = 75.0                  # a blow lands on the red one within this angle of Indigo's facing
HEAVY_KNOCKBACK_POWER = 1.4     # blows at least this strong drive the red one back
KNOCKBACK = 3.2                 # metres
KNOCKBACK_TIME = 0.35
STAGGER = 1.1                   # seconds before the staggered red one can strike again

RED_KO_TIME = 150.0             # lying down (was 300)
RED_CALM_HOURS = 24.0           # a whole day
RED_WANDER_EVERY = 45.0
FEED_RANGE = 16.0
POISON_KO_EXTRA = 60.0
MAX_WEAKNESS = 3
WEAK_STAMINA = 0.20
WEAK_BLOW = 0.15
WEAK_PACE = 0.08
WEAK_SIGHT = 0.10


class FightMixin:
    # ------------------------------------------------------------ state
    def _init_fight(self):
        self.giant_stamina = STAMINA_MAX['giant']
        self.red_stamina = STAMINA_MAX['red']
        self._since_blow = {'giant': 99.0, 'red': 99.0}
        self.giant_knocked_out = False
        self.giant_getup = -1.0                    # >= 0 while getting up
        self._wake_taps = 0
        self._wake_tap_t = -99.0
        self._fight_clock = 0.0
        self.red_calm_until = None                 # absolute game hours, while dazed
        self._red_wander = None
        self._red_wander_t = 0.0
        self.red_weakness = 0
        self.stats['indigo_knockouts'] = self.stats.get('indigo_knockouts', 0)
        for clip in ('Crouch_Idle_Loop', 'Fixing_Kneeling'):      # the dazed red one rests and eats
            self.red_giant_actor._load_clip(self.red_giant_actor.glb_path, clip)
        self.giant_actor._load_clip(self.giant_actor.glb_path, 'Sword_Attack')   # Pass 58: the hammer blow
        self.attack_hold = None                    # Pass 58: {'t': held seconds, 'src': 'key'/'mouse'}
        self.attack_queued = False
        self._red_knock = None

    def game_hours(self) -> float:
        return (getattr(self, 'day', 1) - 1) * 24.0 + getattr(self, 'hour', 12.0)

    def stamina_max(self, owner: str) -> float:
        m = STAMINA_MAX[owner]
        if owner == 'red':
            m *= 1.0 - WEAK_STAMINA * self.red_weakness
        return m

    def fight_stamina(self, owner: str) -> float:
        return self.giant_stamina if owner == 'giant' else self.red_stamina

    def _set_fight_stamina(self, owner: str, v: float):
        v = max(0.0, min(self.stamina_max(owner), v))
        if owner == 'giant':
            self.giant_stamina = v
        else:
            self.red_stamina = v

    def fight_spend(self, owner: str, amount: float):
        self._set_fight_stamina(owner, self.fight_stamina(owner) - amount)
        self._since_blow[owner] = 0.0

    def blow_scale(self, attacker: str) -> float:
        """How hard this giant's blows land (the red one's weaken with poison)."""
        return 1.0 - WEAK_BLOW * self.red_weakness if attacker == 'red' else 1.0

    # ------------------------------------------------------------ the hit (called from main)
    def resolve_hit(self, attacker: str, defender: str, power: float = 1.0) -> str:
        """Apply a landed blow (power: x a punch). Returns 'ko', 'hurt' or 'none'."""
        exhausted = self.fight_stamina(defender) < EXHAUSTED
        k = self.blow_scale(attacker) * power
        if defender == 'giant' and hasattr(self, 'indigo_hit_scale'):
            k *= self.indigo_hit_scale()             # Pass 59: at night Indigo's glow shields it
        self.fight_spend(defender, HIT_STAMINA * k)
        health = self._combat_health(defender) - HIT_HEALTH * k
        self._since_blow[attacker] = 0.0
        if defender == 'giant':
            self.giant_health = max(0.0, health)
            if exhausted or self.giant_health <= 0.0:
                return 'ko'
            return 'hurt'
        if hasattr(self, 'red_provoked_t'):
            self.red_provoked_t = 30.0             # Pass 49: hit while busy, it fights back
        self.red_health = max(0.0, health)
        self.red_calm_until = None                 # hit it while dazed: the calm is over
        if exhausted or self.red_health <= 0.0:
            return 'ko'
        return 'hurt'

    # ------------------------------------------------------------ Pass 58: fighting as Indigo
    def attack_press(self, src: str = 'key'):
        """Left mouse / F pressed while you are Indigo."""
        if self.input_blocked() or self.controlled_name != 'giant' or not self.giant_alive:
            return False
        if self.kneel_state['phase'] != 'standing' or self.jump_states['giant']['active'] or self.giant_action:
            return False
        if self.attack_states['giant']['active']:
            self.attack_queued = True              # a combo: the next punch goes when this one lands
            return True
        self.attack_hold = {'t': 0.0, 'src': src}
        self.keys['punch' if src == 'key' else 'attack_mouse'] = True     # the key's -up clears it
        return True

    def attack_release(self, src: str = 'key'):
        h = self.attack_hold
        if h is None or h['src'] != src:
            return False
        self.attack_hold = None
        if self.controlled_name != 'giant' or not self.giant_alive:
            return False
        if h['t'] >= CHARGE_FULL:
            return self.heavy_blow()
        return self._request_giant_melee()

    def heavy_blow(self) -> bool:
        red_in_reach = self._combat_alive('red') and self._giant_flat_distance() <= ASSIST_RANGE
        branch = None if red_in_reach else self.giant_smash_target()
        if not self._start_melee('giant', clip='Sword_Attack', cost=HEAVY_COST, start=WINDUP_END):
            self.giant_actor.apply_clip('Idle_Loop', 0.0, force=True)
            return False
        if branch is not None:
            self.pending_smash = branch
        self.sfx('punch_swing', self.giant.getPos(self.render) + Vec3(0, 0, self.giant_height * 0.8), 1.3)
        return True

    def update_attack_input(self, dt: float) -> bool:
        """Each frame while you are Indigo. Returns True while it is winding up a hammer blow
        (Indigo stands and turns to aim instead of walking)."""
        h = getattr(self, 'attack_hold', None)
        if h is None:
            return False
        held = self.keys.get('punch') if h['src'] == 'key' else self.keys.get('attack_mouse')
        if not held:                               # let go without an -up event (focus lost...)
            return bool(self.attack_release(h['src']))
        h['t'] += dt
        if h['t'] < TAP_TIME:
            return False
        # winding up: brake, face the red one if it is close, show the raised arms
        self.giant_motion_speed = 0.0
        self._assist_turn(dt)
        k = min(1.0, (h['t'] - TAP_TIME) / (CHARGE_FULL - TAP_TIME))
        self.giant_actor.apply_clip('Sword_Attack', WINDUP_END * k, force=True, loop=False)
        return True

    def _red_bearing(self):
        """(distance, angle off Indigo's facing in degrees) to the red one."""
        gp, rp = self.giant.getPos(self.render), self.red_giant.getPos(self.render)
        d = math.hypot(rp.x - gp.x, rp.y - gp.y)
        want = K['heading_toward'](rp.x - gp.x, rp.y - gp.y)
        off = (want - self.giant.getH() + 180.0) % 360.0 - 180.0
        return d, off, want

    def giant_faces_red(self) -> bool:
        return abs(self._red_bearing()[1]) <= HIT_ARC

    def _assist_turn(self, dt: float) -> bool:
        if not self._combat_alive('red'):
            return False
        d, off, want = self._red_bearing()
        if d > ASSIST_RANGE or abs(off) > ASSIST_ARC:
            return False
        step = max(-ASSIST_TURN * dt, min(ASSIST_TURN * dt, off))
        self.giant_motion_heading = self.giant.getH() + step
        self.giant.setH(self.giant_motion_heading)
        return True

    def melee_assist(self, dt: float, state: dict):
        """During your blow's wind-up: turn to the red one and step in if it is just out of reach."""
        if self.controlled_name != 'giant' or state.get('hit_i', 0) > 0:
            return
        if not self._assist_turn(dt):
            return
        d, off, _want = self._red_bearing()
        if d <= LUNGE_CLOSE or abs(off) > 40.0:
            return
        move = min(LUNGE_SPEED * dt, d - LUNGE_CLOSE)
        old = self.giant.getPos()
        fwd = K['heading_forward'](self.giant.getH())
        pos = old + fwd * move
        pos.z = self.field.height(pos.x, pos.y) - self.giant_actor.height_world * K['GROUND_SINK_FRACTION']
        if hasattr(self, 'giant_clear_of_shells'):
            pos = self.giant_clear_of_shells(self.giant_actor, old, pos)
        self.giant.setPos(pos)

    def melee_chain(self, state: dict, hits) -> bool:
        """A queued punch cuts into the tail of the last blow once it has landed."""
        if not self.attack_queued or self.controlled_name != 'giant' or not state.get('hit_done'):
            return False
        if state['elapsed'] < hits[-1][0] + CHAIN_AFTER_HIT:
            return False
        self.attack_queued = False
        state.update({'active': False, 'elapsed': 0.0, 'cooldown': 0.0})
        return bool(self._request_giant_melee())

    def knock_back_red(self):
        """A hammer blow drives the red one back a few metres and staggers it."""
        gp, rp = self.giant.getPos(self.render), self.red_giant.getPos(self.render)
        away = Vec3(rp.x - gp.x, rp.y - gp.y, 0)
        if away.length_squared() < 1e-6:
            away = K['heading_forward'](self.giant.getH())
        away.normalize()
        self._red_knock = {'dir': away, 'left': KNOCKBACK, 't': KNOCKBACK_TIME}
        st = self.attack_states['red']
        st.update({'active': False, 'elapsed': 0.0, 'hit_done': False,
                   'cooldown': max(st.get('cooldown', 0.0), STAGGER)})

    def _update_red_knock(self, dt: float):
        kb = self._red_knock
        if kb is None:
            return
        step = min(kb['left'], KNOCKBACK / KNOCKBACK_TIME * dt)
        kb['left'] -= step
        kb['t'] -= dt
        p = self.red_giant.getPos() + kb['dir'] * step
        p.z = self.field.height(p.x, p.y) - self.red_giant_actor.height_world * K['GROUND_SINK_FRACTION']
        self.red_giant.setPos(p)
        if kb['left'] <= 1e-4 or kb['t'] <= -0.5:
            self._red_knock = None

    def red_should_flee(self) -> bool:
        """A sneaky red one runs when nearly spent; an aggressive one fights on."""
        mood = self.red_mood() if hasattr(self, 'red_mood') else 'aggressive'
        return mood == 'sneaky' and self.red_stamina <= self.stamina_max('red') * RED_FLEE_STAMINA

    # ------------------------------------------------------------ Indigo down
    def knock_out_indigo(self):
        if self.giant_knocked_out:
            return
        self.giant_knocked_out = True
        self.giant_alive = False
        self.giant_getup = -1.0
        self.giant_ko_hours = self.game_hours()
        self._wake_taps = 0
        self.giant_motion_speed = 0.0
        self.stats['indigo_knockouts'] += 1
        self.attack_states['giant'].update({'active': False, 'elapsed': 0.0, 'hit_done': False})
        self.pending_smash = None                  # a half-thrown smash is forgotten
        self._drop_what_indigo_holds()
        self.giant_actor.apply_clip('Death01', 0.0, force=True, loop=False)
        self.sfx('giant_fall', self.giant.getPos(self.render))
        if self.controlled_name == 'giant':
            self._hand_control_back()              # you are yourself again - always
        key = self._key_word('use')
        self.say(f'Nyx falls, and does not get up.  Tap {key} beside it to wake it.', 5.0)

    def _drop_what_indigo_holds(self):
        """A falling giant lets go: a shell half-lifted or held drops beside it."""
        act = getattr(self, 'giant_action', None)
        self.giant_action = None
        held = getattr(self, 'giant_held_shell', None)
        if held is None and act is not None and act.get('shell') is not None and act['shell'].held:
            held = act['shell']
        if held is not None:
            beside = self.giant.getPos(self.render) + K['heading_forward'](self.giant.getH() + 90.0) * 8.0
            self.shells.place(held, beside, self.giant.getH())
            self.giant_held_shell = None

    def _hand_control_back(self):
        """Give the player the human again, whatever Indigo was in the middle of."""
        self.jump_states['giant'].update({'active': False, 'phase': 'ground', 'elapsed': 0.0, 'vz': 0.0})
        self.kneel_state.update({'phase': 'standing', 'elapsed': 0.0})
        if self.human_alive:
            self.controlled_name = 'human'
            self.keys.update({k: False for k in self.keys})
            if hasattr(self, '_update_control_text'):
                self._update_control_text()
            self._snap_camera_to_controlled(immediate=False)

    def _next_dawn_after(self, hours: float) -> float:
        start = math.floor((hours - 6.0) / 24.0) * 24.0 + 6.0     # the last 06:00 at or before
        return start + 24.0 if hours >= start else start

    def _key_word(self, action: str) -> str:
        import controls
        return controls.label(getattr(self, 'bindings', {}), action)

    def near_downed_indigo(self) -> bool:
        if not self.giant_knocked_out or self.giant_getup >= 0.0:
            return False
        hp = self.human.getPos(self.render)
        return self._near_body(self.giant_actor, self.giant, hp, WAKE_RANGE)

    def _near_body(self, actor, node, p: Point3, reach: float) -> bool:
        """Near a giant lying down: its root, its chest or its head."""
        t = actor.last_clip_time
        pts = [node.getPos(self.render)]
        for joint in ('spine_03', 'head'):
            if joint in actor.skin.node_index:
                pts.append(actor.joint_world_point(joint, t, self.render))
        return any(_flat_dist(q, p) <= reach for q in pts)

    def shake_indigo(self):
        if self._fight_clock - self._wake_tap_t > WAKE_TAP_GAP:
            self._wake_taps = 0                    # too slow: start shaking again
        self._wake_tap_t = self._fight_clock
        self._wake_taps += 1
        self.sfx('indigo_shake', self.giant.getPos(self.render))
        if self._wake_taps < WAKE_TAPS:
            words = ("You shake Nyx's great hand. Nothing.",
                     'You shout its name and shake it again. Its fingers twitch.')
            self.say(words[min(self._wake_taps - 1, 1)], 2.5)
            return
        self.wake_indigo('Nyx opens its eyes, and slowly gets up.')

    def wake_indigo(self, words: str):
        self.sfx('indigo_wake', self.giant.getPos(self.render))
        self.giant_getup = 0.0
        self._wake_taps = 0
        self.say(words, 3.5)

    def _update_giant_ko(self, dt: float) -> bool:
        """Indigo lying down or getting up. True = the giant is handled this frame."""
        if not self.giant_knocked_out:
            return False
        dur = self.giant_actor.clips['Death01']['duration']
        if self.giant_getup < 0.0:
            self.giant_actor.apply_clip('Death01', dur - 1e-4, loop=False)
            ko_at = getattr(self, 'giant_ko_hours', None)
            if ko_at is None:
                ko_at = self.giant_ko_hours = self.game_hours()
            if self.game_hours() >= self._next_dawn_after(ko_at):
                self.wake_indigo('With the dawn, Nyx stirs and gets up.')
            return True
        self.giant_getup += dt
        p = min(1.0, self.giant_getup / GETUP_TIME)
        self.giant_actor.apply_clip('Death01', max(0.0, (dur - 1e-4) * (1.0 - p)), loop=False)
        if p >= 1.0:
            self.giant_knocked_out = False
            self.giant_getup = -1.0
            self.giant_alive = True
            self.giant_health = max(self.giant_health, WAKE_HEALTH)
            self.giant_stamina = max(self.giant_stamina, STAMINA_MAX['giant'] * WAKE_STAMINA)
            self.giant_actor.apply_clip('Idle_Loop', 0.0, force=True)
            if self.comp.get('mode') not in ('follow', 'stay'):
                self.comp.update({'mode': 'follow', 'moving': True})
        return True

    # ------------------------------------------------------------ the red one down, then dazed
    def red_is_calm(self) -> bool:
        return self.red_calm_until is not None and self.game_hours() < self.red_calm_until

    def begin_red_calm(self):
        self.red_calm_until = self.game_hours() + RED_CALM_HOURS
        self._red_wander = None
        self._red_wander_t = 0.0

    def _update_red_calm(self, dt: float, clock_t: float) -> bool:
        """The day after a knock-out: it has lost you. True = handled."""
        if self.red_calm_until is None:
            return False
        if not self.red_is_calm():
            self.red_calm_until = None
            self.red_trail_serial = None           # pick the trail up where it is nearest
            self.say('Far behind you, Crimson has found your tracks again.', 4.0)
            return False
        self.red_state = 'dazed'
        # it still eats and rests (Pass 48) - but never hunts or tracks you
        if getattr(self, 'red_meal', None) is not None:
            self._update_red_meal(dt)
            return True
        if getattr(self, 'red_resting', False) or (self.is_night() and self.red_energy < 0.3):
            self.red_resting = True
            self.red_state = 'dazed'
            self.red_motion_speed = 0.0
            self.red_giant_actor.apply_clip('Crouch_Idle_Loop', clock_t)
            if not self.is_night():
                self.red_resting = False
            return True
        rp = self.red_giant.getPos(self.render)
        if getattr(self, 'red_hunger', 0.0) >= 0.5 and hasattr(self, '_forage_target'):
            b = self._forage_target(rp, dt)
            if b is not None:
                if self._red_walk_to(b.pos, dt, 6.5, walk_only=True, speed_k=0.5) <= 6.5:
                    self.red_meal = {'t': 0.0, 'branch': b, 'taken': False}
                self.red_state = 'dazed'
                return True
        self._red_wander_t -= dt
        if self._red_wander is None or self._red_wander_t <= 0.0:
            rng = random.Random(int(self.game_hours() * 10) + 7)
            a = rng.uniform(0, 2 * math.pi)
            r = rng.uniform(40.0, 120.0)
            self._red_wander = Point3(rp.x + math.cos(a) * r, rp.y + math.sin(a) * r, 0.0)
            self._red_wander_t = RED_WANDER_EVERY
        if self._red_walk_to(self._red_wander, dt, 4.0, walk_only=True, speed_k=0.45) <= 4.0:
            self.red_motion_speed = 0.0
            self.red_giant_actor.apply_clip('Idle_Loop', clock_t)
        self.red_state = 'dazed'
        return True

    # ------------------------------------------------------------ poison
    def can_feed_red(self) -> bool:
        return (self.red_knocked_out and not self.red_dead and self.red_weakness < MAX_WEAKNESS
                and self.pooled_count('bane') > 0
                and self._near_body(self.red_giant_actor, self.red_giant, self.human.getPos(self.render), FEED_RANGE))

    def feed_red_poison(self):
        self.spend_pooled({'bane': 1})             # your bag first, then Indigo's if it is beside you
        self.red_weakness += 1
        self.red_knockout_remaining += POISON_KO_EXTRA
        self._set_fight_stamina('red', self.red_stamina)
        self.stats['doses'] = self.stats.get('doses', 0) + 1
        self.sfx('red_poisoned', self.red_giant.getPos(self.render))
        left = MAX_WEAKNESS - self.red_weakness
        more = (f'  It could take {left} more.' if left else
                '  It will take no more like this. Only a poisoned blood branch will end it.')
        self.lore_log.append(f'You fed Crimson a pale scrap while it lay still. It is weaker ({self.red_weakness}).')
        self.say('You push a pale scrap between its teeth. It shudders, and sleeps deeper.\n'
                 f'Crimson is weaker now.{more}', 6.0)

    # ------------------------------------------------------------ E: wake Indigo, feed the red one
    def fight_e_kind(self):
        if (self.controlled_name != 'human' or not self.human_alive or self.carried
                or self.hidden_shell is not None):
            return None
        if self.near_downed_indigo():
            return 'wake'
        if self.can_feed_red():
            return 'feed'
        return None

    def _e_target(self):
        kind = self.fight_e_kind()
        if kind is not None:
            return kind, None
        return super()._e_target()

    def _on_e_press(self):
        kind = None if self.input_blocked() else self.fight_e_kind()
        if kind is None:
            return super()._on_e_press()
        self.keys['e'] = True
        self.e_hold['spent'] = True                # a tap, not a hold
        if kind == 'wake':
            self.shake_indigo()
        else:
            self.feed_red_poison()

    def place_prompt(self, kind, target) -> str:
        if kind == 'wake':
            return f'wake Nyx  ({self._wake_taps}/{WAKE_TAPS})' if self._wake_taps else 'wake Nyx'
        if kind == 'feed':
            return f'feed it a pale scrap  ({self.pooled_count("bane")} left)'
        return super().place_prompt(kind, target) if hasattr(super(), 'place_prompt') else ''

    # ------------------------------------------------------------ per frame
    def survival_step(self, dt: float):
        super().survival_step(dt)
        if self.world_frozen():
            return
        self._fight_clock += dt
        self._update_red_knock(dt)
        for owner in ('giant', 'red'):
            self._since_blow[owner] += dt
            down = self.giant_knocked_out if owner == 'giant' else (self.red_knocked_out or self.red_dead)
            if down:
                continue
            energy = getattr(self, 'giant_energy' if owner == 'giant' else 'red_energy', 1.0)
            rate = REGEN_CALM if self._since_blow[owner] >= CALM_AFTER else REGEN_FIGHTING
            rate *= 0.5 + 0.5 * energy
            v = self.fight_stamina(owner) + rate * dt
            if owner == 'giant' and getattr(self, 'giant_motion_gait', '') == 'sprint' and \
                    getattr(self, 'giant_motion_speed', 0.0) > K['GIANT_JOG_SPEED']:
                v -= (SPRINT_DRAIN + rate) * dt
            self._set_fight_stamina(owner, v)

    # ------------------------------------------------------------ poison's lasting effects
    def red_pace(self) -> float:
        return super().red_pace() * (1.0 - WEAK_PACE * self.red_weakness)

    def red_detection_range(self) -> float:
        return super().red_detection_range() * (1.0 - WEAK_SIGHT * self.red_weakness)

    # ------------------------------------------------------------ words for the HUD
    def _companion_word(self) -> str:
        if self.giant_knocked_out:
            if self.giant_getup >= 0.0:
                return 'getting up'
            return f'knocked out  ·  tap {self._key_word("use")} beside it'
        word = super()._companion_word()
        if self.giant_alive and self.giant_stamina < STAMINA_MAX['giant'] * 0.25:
            word += ', winded'
        return word

    def _red_word(self) -> str:
        if self.red_is_calm() and not (self.red_knocked_out or self.red_recovering):
            word = 'dazed  ·  it has lost you'
        else:
            word = super()._red_word()
        if self.red_weakness:
            word += '  ·  weakened' + ('' if self.red_weakness == 1 else f' x{self.red_weakness}')
        return word

    # ------------------------------------------------------------ save
    def fight_snapshot(self) -> dict:
        return {'giant_stamina': round(self.giant_stamina, 1), 'red_stamina': round(self.red_stamina, 1),
                'giant_ko': bool(self.giant_knocked_out), 'red_calm_until': self.red_calm_until,
                'giant_ko_hours': getattr(self, 'giant_ko_hours', None),
                'red_recovering': bool(getattr(self, 'red_recovering', False)),
                'red_weakness': int(self.red_weakness)}

    def apply_fight(self, d: dict):
        self.red_weakness = max(0, min(MAX_WEAKNESS, int(d.get('red_weakness', 0))))
        self.giant_stamina = float(d.get('giant_stamina', STAMINA_MAX['giant']))
        self.red_stamina = min(self.stamina_max('red'), float(d.get('red_stamina', STAMINA_MAX['red'])))
        cu = d.get('red_calm_until')
        self.red_calm_until = float(cu) if isinstance(cu, (int, float)) else None
        if d.get('giant_ko') or not self.giant_alive:     # older saves: 0 life = knocked out
            self.giant_knocked_out = False
            self.knock_out_indigo_quiet()
        if d.get('red_recovering') and not self.red_knocked_out:
            # saved while it was getting up (the save calls that 'fleeing'): it gets its calm day
            self.red_fleeing = self.red_recovering = False
            self.begin_red_calm()
            self.red_state = 'dazed'
        kh = d.get('giant_ko_hours')
        if isinstance(kh, (int, float)) and self.giant_knocked_out:
            self.giant_ko_hours = float(kh)

    def knock_out_indigo_quiet(self):
        self.giant_knocked_out = True
        self.giant_alive = False
        self.giant_ko_hours = self.game_hours()
        self.giant_getup = -1.0
        self._wake_taps = 0
