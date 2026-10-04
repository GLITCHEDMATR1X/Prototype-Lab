"""Pass 39 — the desert: heat, shade, finds, the landmark trail, sea-shell shelters.

HEAT & STAMINA (human only — the giants are native to this place)
    Heat rises in the sun and falls in shade.  In full sun heat fills in ~2 minutes;
    at full heat health drains over ~3 minutes, so ~5 minutes of unbroken exposure
    kills.  Heat also slowly drains stamina and, above 70, slows you down.
    Shade: the giants' real sun shadows (the Pass 36 shade query), shells and landmarks.
    Riding on the giant's shoulder is full exposure (x1.25): safe from stomps, not from the sun.
    Stamina: jogging, sprinting, jumping and smashing spend it; at zero you are winded
    (walk only) until it recovers to 25.

SHADE ME (5 / wheel)  the giant stands sunward of you so its shadow covers you, and keeps it there.
WHISTLE (Q / wheel)   works anywhere, even hidden in a shell: the giant comes running, and will
                      defend you from far further away than it would notice on its own.

FINDS
    Half-buried mounds scattered through the desert.  The giant senses them from far
    away (a pale shimmer marks each one) and turns to look.  Hold E on one to dig it up:
    moss pods and water gourds (food), dune fibre, amber resin, shell shards — or nothing.
    G eats: a water gourd if you are hot (cools you), otherwise moss pods (stamina, health).

LANDMARKS — the non-linear trail
    Eight far landmarks (ribcages, spires, glass beads).  Two are visible from the start
    as tall shimmers; studying one (hold E beside it) gives a small cache and lets the
    giant sense the landmarks linked to it.  The giant also spots any landmark it walks
    within ~250 m of.  Follow them in any order.

SHELLS
    Empty sea shells, big enough to walk into (Pass 55).  Walk in through the mouth of an intact
    shell (or E at its mouth to step in); walk back out the same way.  The walls are solid.
    Inside a cracked shell is only shade.
    Inside an intact one: heat, stamina and health all recover slowly, and the Red Giant loses you —
    unless it saw you go in, or stumbles within ~26 m.  Then it tries to overturn the
    shell (~7 s).  Whistle.  Cracked shells can be patched (hold E: 3 scraps + 1 resin).
    As the giant, E lifts a nearby empty shell and E sets it down in front of you
    (upright again, if the Red Giant flipped it).
"""
from __future__ import annotations

import math
from collections import Counter

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import CardMaker, PNMImage, Point3, TextNode, Texture, TransparencyAttrib, Vec3

import desert_world as world
import flora
import locomotion
from survival import K, _angle_delta, _approach, _clamp, _flat_dist, globalClock

# ------------------------------------------------------------------ heat & stamina
HEAT_MAX = 100.0
HEAT_SUN_RATE = HEAT_MAX / 120.0          # full heat after 2 minutes of sun
HEAT_RIDE_MULT = 1.25
HEAT_SHADE_RATE = 2.0
HEAT_SHELL_RATE = 4.0
HEAT_DAMAGE_RATE = 100.0 / 180.0          # full heat -> dead in 3 more minutes (5 total)
HEAT_SLOW_START = 70.0
STAMINA_MAX = 100.0
STAMINA_REGEN = 9.0
STAMINA_COST = {'jog': 3.0, 'sprint': 14.0}   # Pass 52: sprint is 6.6 m/s now (was 3.5)
STAMINA_JUMP = 10.0
STAMINA_SMASH = 6.0
STAMINA_WINDED_RECOVER = 25.0
SHELL_HEAL_RATE = 0.6
SHELL_STAMINA_RATE = 12.0
WELL_HEAT_MULT = 0.85             # Pass 51: after drinking at the Sky Well
CLOAK_HEAT_MULT = 0.75                     # Pass 43 upgrades (crafted with B)
WRAPS_STAMINA_MULT = 0.7
SIP_COOLING = 25.0

# ------------------------------------------------------------------ inventory
HUMAN_BAG = 12
GIANT_BAG = 60
ITEM_ORDER = ('pod', 'gourd', 'scraps', 'resin', 'fibre', 'shard', 'bane')
ITEM_LABEL = {'pod': 'pods', 'gourd': 'gourds', 'scraps': 'scraps', 'resin': 'resin', 'fibre': 'fibre', 'shard': 'shards',
              'bane': 'pale scraps'}             # Pass 47: from the pale bloom
FOOD = {'pod': {'stamina': 45.0, 'health': 12.0, 'heat': 0.0},
        'gourd': {'stamina': 20.0, 'health': 4.0, 'heat': -35.0}}
PATCH_COST = {'scraps': 3, 'resin': 1}
SHARE_RANGE = 14.0

# ------------------------------------------------------------------ interactions
SENSE_RANGE = 170.0                 # Pass 42: finds are sparser, Indigo senses further
SENSE_PERIOD = 1.5
LANDMARK_SPOT_RANGE = 420.0
NOTICE_TIME = 4.0                   # Indigo keeps looking long enough for you to follow its gaze
DIG_RANGE = 2.2
STUDY_RANGE = 6.0
PATCH_RANGE = 4.8                   # Pass 55: from the shell's middle (the shells are bigger)
HOLD_TIMES = {'dig': 1.0, 'study': 1.6, 'patch': 1.5, 'smash': 1.2, 'glow': 1.4}   # glow: Pass 59
GIANT_SHELL_REACH = 10.0
GIANT_PICKUP_TIME = 0.83
SHADE_STAND_PRECISION = 0.8
SHADE_MIN_OFFSET = 4.5

# ------------------------------------------------------------------ red vs shells, whistle
WHISTLE_ALERT = 40.0
WHISTLE_TRIGGER_RANGE = 120.0
INDIGO_AWARE_RANGE = 70.0
RED_SNIFF_RANGE = 26.0
RED_SHELL_STOP = 7.0                # Pass 55: the shells are bigger
RED_OVERTURN_TIME = 7.0
EJECT_DAZE = 1.6
SHELL_SEE_THROUGH = 0.35            # Pass 55: the shell you stand in fades so you can see yourself
SHELL_FADE_RATE = 2.5


def _heat_haze_texture() -> Texture:
    img = PNMImage(128, 128, 4)
    for y in range(128):
        for x in range(128):
            dx, dy = (x - 63.5) / 63.5, (y - 63.5) / 63.5
            r = math.sqrt(dx * dx * 0.8 + dy * dy)
            a = _clamp((r - 0.55) / 0.6, 0.0, 1.0) ** 1.6
            img.setXelA(x, y, 0.96, 0.58, 0.28, a)
    tex = Texture('heat_haze')
    tex.load(img)
    return tex


class DesertMixin:
    """Mixed in before SurvivalMixin (its methods extend / override a few survival ones)."""

    # ------------------------------------------------------------ inventory plumbing
    def _bags(self):
        if '_inv' not in self.__dict__:
            self._inv = {'human': Counter(), 'giant': Counter()}
        return self._inv

    @property
    def human_scraps(self):
        return self._bags()['human']['scraps']

    @human_scraps.setter
    def human_scraps(self, value):
        self._bags()['human']['scraps'] = int(value)

    @property
    def giant_scraps(self):
        return self._bags()['giant']['scraps']

    @giant_scraps.setter
    def giant_scraps(self, value):
        self._bags()['giant']['scraps'] = int(value)

    def bag(self, owner: str) -> Counter:
        return self._bags()[owner]

    def bag_count(self, owner: str) -> int:
        return sum(self._bags()[owner].values())

    def bag_space(self, owner: str) -> int:
        return max(0, (HUMAN_BAG if owner == 'human' else GIANT_BAG) - self.bag_count(owner))

    def giant_within_reach(self) -> bool:
        return self.giant_alive and (self.carried or _flat_dist(self.human.getPos(self.render),
                                                                self.giant.getPos(self.render)) <= SHARE_RANGE)

    def give_items(self, items: dict, giant_overflow: bool = True) -> dict:
        """Put items in the human's bag, overflow to the giant if it is close. Returns what was lost."""
        lost = {}
        for item, n in items.items():
            take = min(n, self.bag_space('human'))
            self.bag('human')[item] += take
            rest = n - take
            if rest and giant_overflow and self.giant_within_reach():
                g = min(rest, self.bag_space('giant'))
                self.bag('giant')[item] += g
                rest -= g
            if rest:
                lost[item] = rest
        return lost

    def pooled_count(self, item: str) -> int:
        n = self.bag('human')[item]
        if self.giant_within_reach():
            n += self.bag('giant')[item]
        return n

    def spend_pooled(self, cost: dict) -> bool:
        if any(self.pooled_count(i) < n for i, n in cost.items()):
            return False
        for item, n in cost.items():
            from_human = min(n, self.bag('human')[item])
            self.bag('human')[item] -= from_human
            self.bag('giant')[item] -= n - from_human
        return True

    def transfer_scraps(self, to_giant: bool) -> int:
        """T: give everything you carry to the giant.  Y: take materials back (not food)."""
        if self.input_blocked():
            return 0
        if not (self.human_alive and self.giant_alive) or not self.giant_within_reach():
            return 0
        src, dst = ('human', 'giant') if to_giant else ('giant', 'human')
        order = ITEM_ORDER if to_giant else ('scraps', 'resin', 'fibre', 'shard', 'bane')
        moved = 0
        for item in order:
            n = min(self.bag(src)[item], self.bag_space(dst))
            self.bag(src)[item] -= n
            self.bag(dst)[item] += n
            moved += n
        return moved

    # --------------------------------------------------------------------- setup
    def _init_desert(self, seed: int):
        start = self.human.getPos(self.render)
        mask = K['SHADOW_CAMERA_MASK']
        self.finds = world.FindField(self.render, self.field, seed, start, mask)
        self.shells = world.ShellField(self.render, self.field, seed, start)
        self.landmarks = world.LandmarkField(self.render, self.field, seed, start, mask)
        self.heat = 0.0
        self.stamina = STAMINA_MAX
        self.winded = False
        self.human_effort = 'idle'
        self.hidden_shell = None
        self.shell_fade = {}                   # Pass 55: shell -> alpha while it is see-through
        self.human_dazed = 0.0
        self.whistle_alert = 0.0
        self.notice = None
        self._sense_timer = 0.0
        self._desert_timer = 0.0
        self._static_shade = []
        self.e_hold = {'kind': None, 'target': None, 't': 0.0, 'spent': False}
        self.giant_held_shell = None
        self.giant_action = None
        self.red_saw_hide = False
        self.red_overturn_t = 0.0
        self.red_shell_state = ''
        self.heat_deaths = 0
        self.shelter_word = 'sun'
        self.red_giant_actor._load_clip(self.giant_glb, 'Push_Loop')

        self.lore_text = OnscreenText(text='', pos=(0.0, -0.52), align=TextNode.ACenter, scale=0.045,
                                      fg=(0.14, 0.12, 0.16, 0.0), wordwrap=30, mayChange=True)
        self._lore_alpha = 0.0
        self._lore_hold = 0.0
        cm = CardMaker('heat_haze')
        cm.setFrame(-1, 1, -1, 1)
        self.heat_card = self.render2d.attachNewNode(cm.generate())
        self.heat_card.setTexture(_heat_haze_texture())
        self.heat_card.setTransparency(TransparencyAttrib.MAlpha)
        self.heat_card.setBin('background', 0)
        self.heat_card.setDepthWrite(False)
        self.heat_card.setAlphaScale(0.0)

        self.bind_action('use', self._on_e_press)
        self.bind_action('eat', self.eat)
        self._refresh_world(force=True)
        if hasattr(self, 'drain_stream_queue'):
            self.drain_stream_queue()           # Pass 55: the levelled ground is there from the first frame

    # ------------------------------------------------------------------ messages
    def say(self, text: str, seconds: float = 4.0):
        self.lore_text.setText(text)
        self._lore_alpha = 1.0
        self._lore_hold = seconds

    def _update_say(self, dt: float):
        if self._lore_hold > 0.0:
            self._lore_hold -= dt
        elif self._lore_alpha > 0.0:
            self._lore_alpha = max(0.0, self._lore_alpha - dt * 0.6)
        else:
            return
        # Pass 61: night ink (pale) at night - the words were drawn dark on the dark desert
        ink = self._ink_now() if hasattr(self, '_ink_now') else (0.14, 0.12, 0.16)
        self.lore_text.setFg((*ink, 0.9 * self._lore_alpha))
        dark = sum(ink) < 1.5
        self.lore_text.setShadow((1.0, 0.98, 0.94, 0.30 * self._lore_alpha) if dark
                                 else (0.02, 0.02, 0.05, 0.55 * self._lore_alpha))

    # -------------------------------------------------------------------- shade
    def _sun_offset(self) -> Vec3:
        """Horizontal shadow offset per metre of height, along the sun ray."""
        ray = self.sun_ray_world
        k = 1.0 / max(-ray.z, 0.15)
        return Vec3(ray.x * k, ray.y * k, 0.0)

    def _refresh_world(self, force: bool = False):
        focus = self.giant.getPos(self.render) if self.controlled_name == 'giant' else self.human.getPos(self.render)
        self.shells.update_active(focus)          # Pass 55: first - shells keep their ground clear
        self.finds.update_active(focus)
        if self.shells.changed:
            # the sand under new shells was levelled; loaded ground there is rebuilt (normally
            # none: shell sites are chosen beyond the built ground, except around the start)
            changed, self.shells.changed = self.shells.changed, []
            if hasattr(self, 'invalidate_terrain_near'):
                self.invalidate_terrain_near(changed)
            self._resettle_near(changed)
        off = self._sun_offset()
        hp = self.human.getPos(self.render)
        circles = self.shells.shade_circles(off) + self.landmarks.shade_circles(off)
        self._static_shade = [c for c in circles if math.hypot(c[0] - hp.x, c[1] - hp.y) < 80.0]

    def _resettle_near(self, circles):
        """Pass 57: after the sand is levelled (a shell set down), what stands on it follows the
        new ground: blood branches, stumps, scraps and half-buried finds."""
        def near(p):
            return any((p.x - x) ** 2 + (p.y - y) ** 2 <= r * r for x, y, r in circles)
        fl = getattr(self, 'flora', None)
        if fl is not None:
            for b in fl.branches.values():
                if near(b.pos):
                    b.pos = Point3(b.pos.x, b.pos.y, self.field.height(b.pos.x, b.pos.y))
                    for node in (b.node, b.stump):
                        if node is not None:
                            node.setZ(b.pos.z)
            for sc in fl.scraps:
                if near(sc.pos):
                    sc.pos = Point3(sc.pos.x, sc.pos.y, self.field.height(sc.pos.x, sc.pos.y) + 0.02)
                    sc.node.setZ(sc.pos.z)
        for f in self.finds.finds.values():
            if not f.dug and near(f.pos):
                f.pos = Point3(f.pos.x, f.pos.y, world.resting_z(self.field, f.pos.x, f.pos.y, 0.7))
                if f.node is not None:
                    f.node.setZ(f.pos.z)

    def point_in_shade(self, p: Point3) -> bool:
        for x, y, r in self._static_shade:
            if (p.x - x) ** 2 + (p.y - y) ** 2 <= r * r:
                return True
        shadows = getattr(self, 'actor_shadows', {})
        for owner in ('giant', 'red'):
            sh = shadows.get(owner)
            if sh is not None and sh.contains_xy(p):
                return True
        return False

    # ------------------------------------------------------------ heat & stamina
    # defaults, overridden by the day cycle / crafting mixins
    def sun_heat_factor(self) -> float:
        return 1.0

    def has_upgrade(self, name: str) -> bool:
        return False

    def on_branch_smashed(self, branch, by: str):
        return False

    def human_winded(self) -> bool:
        return self.winded

    def stamina_cap(self) -> float:
        return STAMINA_MAX - 0.6 * max(0.0, self.heat - 40.0)

    def heat_speed_factor(self) -> float:
        return 1.0 - 0.3 * _clamp((self.heat - HEAT_SLOW_START) / (HEAT_MAX - HEAT_SLOW_START), 0.0, 1.0)

    def spend_stamina(self, amount: float) -> bool:
        amount *= self.stamina_cost_scale()
        if self.winded or self.stamina < amount:
            return False
        self.stamina -= amount
        self.on_stamina_spent(amount)
        return True

    # Pass 59: hooks for perks (Indigo's glow, glow.py)
    def stamina_cost_scale(self) -> float:
        return 1.0

    def work_speed(self) -> float:
        return 1.0

    def human_damage_scale(self) -> float:
        return 1.0

    def on_stamina_spent(self, amount: float):
        pass

    def _update_heat(self, dt: float):
        if not self.human_alive:
            return
        hp = self.human.getPos(self.render)
        if self.hidden_shell is not None:
            where = 'shell'
        elif not self.carried and self.shells.inside(hp, ('cracked',), world.OUTSIDE_Q) is not None:
            where = 'shade'                     # Pass 55: a cracked shell still shades you
        elif self.carried:
            where = 'riding shaded' if self.has_upgrade('canopy') else 'riding'
        elif self.point_in_shade(hp):
            where = 'shade'
        else:
            where = 'sun'
        self.shelter_word = where
        sun = self.sun_heat_factor()           # Pass 43: follows the time of day (1.0 without a day cycle)
        if where == 'shell':
            self.heat = max(0.0, self.heat - HEAT_SHELL_RATE * dt)
            self.human_health = min(K['HUMAN_MAX_HEALTH'], self.human_health + SHELL_HEAL_RATE * dt)
        elif where in ('shade', 'riding shaded'):
            self.heat = max(0.0, self.heat - HEAT_SHADE_RATE * dt)
        elif sun < 0.0:                         # night air cools you
            self.heat = max(0.0, self.heat + HEAT_SUN_RATE * sun * dt)
        else:
            cloak = CLOAK_HEAT_MULT if self.has_upgrade('cloak') else 1.0
            if self.has_upgrade('wellwater'):          # Pass 51: drank at the Sky Well
                cloak *= WELL_HEAT_MULT
            ride = HEAT_RIDE_MULT if where == 'riding' else 1.0
            self.heat = min(HEAT_MAX, self.heat + HEAT_SUN_RATE * sun * cloak * ride * dt)

        # stamina
        effort = self.human_effort if self.controlled_name == 'human' else 'idle'
        cost = STAMINA_COST.get(effort, 0.0) * (WRAPS_STAMINA_MULT if self.has_upgrade('wraps') else 1.0)
        if self.e_hold['kind'] == 'smash' and self.e_hold['t'] > 0.0:
            cost += STAMINA_SMASH
        cost *= self.stamina_cost_scale()                      # Pass 59
        if cost > 0.0:
            self.stamina -= cost * dt
            self.on_stamina_spent(cost * dt)
        else:
            regen = STAMINA_REGEN * (1.0 - 0.7 * self.heat / HEAT_MAX)
            if where == 'shell':
                regen += SHELL_STAMINA_RATE
            self.stamina += regen * dt
        # Heat wears you down: the most stamina you can hold shrinks as you overheat
        # (100 -> 64 at full heat) and comes back as you cool.
        self.stamina = _clamp(self.stamina, 0.0, self.stamina_cap())
        if self.stamina <= 0.0:
            self.winded = True
        elif self.winded and self.stamina >= STAMINA_WINDED_RECOVER:
            self.winded = False

        if self.heat >= HEAT_MAX:
            self.human_health -= HEAT_DAMAGE_RATE * self.human_damage_scale() * dt
            if self.human_health <= 0.0:
                self.heat_deaths += 1
                self._down_human()
                self.say('The heat took you.', 5.0)

        haze = _clamp((self.heat - 35.0) / 65.0, 0.0, 1.0)
        self.heat_card.setAlphaScale(0.75 * haze * (0.9 + 0.1 * math.sin(globalClock.getFrameTime() * 3.0)))

    def eat(self):
        if self.input_blocked():
            return None
        if not self.human_alive:
            return None
        order = ('gourd', 'pod') if self.heat >= 45.0 else ('pod', 'gourd')
        sips = getattr(self, 'water_sips', 0)
        if sips > 0 and self.heat >= 45.0 and self.pooled_count('gourd') == 0:
            self.water_sips = sips - 1
            self.heat = max(0.0, self.heat - SIP_COOLING)
            self.stamina = min(self.stamina_cap(), self.stamina + 10.0)
            self.sfx('eat', self.human.getPos(self.render))
            self.say(f'a sip of dew from the skin  ({self.water_sips} left)', 2.0)
            return 'sip'
        for item in order:
            if self.pooled_count(item) > 0:
                self.spend_pooled({item: 1})
                fx = FOOD[item]
                self.heat = _clamp(self.heat + fx['heat'], 0.0, HEAT_MAX)
                self.stamina = min(self.stamina_cap(), self.stamina + fx['stamina'])
                self.human_health = min(K['HUMAN_MAX_HEALTH'], self.human_health + fx['health'])
                if self.stamina >= STAMINA_WINDED_RECOVER:
                    self.winded = False
                self.sfx('eat', self.human.getPos(self.render))
                self.say('water gourd — cool and bitter' if item == 'gourd' else 'moss pods — chewy, sweet', 2.5)
                return item
        self.say('nothing to eat', 1.5)
        return None

    # ------------------------------------------------------------------ E: context
    def _e_target(self):
        """What E does for the human right now: (kind, target) or (None, None)."""
        if (self.controlled_name != 'human' or not self.human_alive or self.carried
                or self.human_dazed > 0.0):
            return None, None
        hp = self.human.getPos(self.render)
        if self.hidden_shell is None:
            s = self.shells.at_mouth(hp)         # Pass 55: E at the mouth steps you in
            if s is not None and not s.occupied:
                return 'hide', s
        f = self.finds.nearest(hp, DIG_RANGE)
        if f is not None:
            return 'dig', f
        lm = self.landmarks.nearest(hp, STUDY_RANGE)
        if lm is not None:
            return 'study', lm
        s = self.shells.nearest(hp, PATCH_RANGE, states=('cracked',))
        if s is not None:
            return 'patch', s
        b = self.flora.nearest_intact(hp, flora.SMASH_RANGE_HUMAN)
        if b is not None:
            return 'smash', b
        return None, None

    def _on_e_press(self):
        if self.input_blocked():
            return
        self.keys['e'] = True
        self.e_hold['spent'] = False
        if self.controlled_name == 'giant':
            self.giant_shell_action()
            return
        kind, target = self._e_target()
        if kind == 'hide':
            self.enter_shell(target)
            self.e_hold['spent'] = True

    def human_is_smashing(self) -> bool:
        return self.e_hold['t'] > 0.0

    def _update_e_hold(self, dt: float):
        h = self.e_hold
        airborne = self.jump_states['human']['active']          # Pass 44 (B11): no digging mid-air
        if not self.keys.get('e') or h['spent'] or self.gesture is not None or airborne or self.input_blocked():
            if h['t'] > 0.0 and self.human_alive and not self.carried:
                self.human_actor.apply_clip('Idle_Loop', 0.0, force=True)
            h.update({'kind': None, 'target': None, 't': 0.0})
            self.smash_hold = 0.0
            return
        kind, target = self._e_target()
        if kind not in HOLD_TIMES:
            h.update({'kind': None, 'target': None, 't': 0.0})
            self.smash_hold = 0.0
            return
        if target is not h['target']:
            h.update({'kind': kind, 'target': target, 't': 0.0})
        if kind == 'patch' and any(self.pooled_count(i) < n for i, n in PATCH_COST.items()):
            self.say('patching needs 3 scraps and 1 resin', 1.5)
            h['spent'] = True
            return
        if kind == 'smash' and self.stamina <= 0.0:
            return
        h['t'] += dt * self.work_speed()                     # Pass 59: quicker hands with the glow
        self.smash_hold = h['t']
        clips = self.human_actor.clips
        if kind == 'smash':
            self.human_actor.apply_clip('Punch_Jab', (h['t'] * 1.4) % clips['Punch_Jab']['duration'], loop=False)
        elif kind in ('study', 'glow', 'etching', 'leave'):   # Pass 61: etchings, Gleebs
            self.human_actor.apply_clip('Interact', h['t'], loop=False)
        else:
            self.human_actor.apply_clip('Fixing_Kneeling', min(h['t'], 1.19), loop=False)
        if h['t'] >= HOLD_TIMES[kind]:
            self._complete_e(kind, target)
            h.update({'kind': None, 'target': None, 't': 0.0, 'spent': True})
            self.smash_hold = 0.0
            self.human_actor.apply_clip('Idle_Loop', 0.0, force=True)

    def _complete_e(self, kind, target):
        if kind == 'smash':
            self.flora.smash(target)
            self.sfx('branch_smash', target.pos)
        elif kind == 'dig':
            self.sfx('dig', target.pos)
            item, n = self.finds.dig(target)
            name = world.FIND_NAMES[target.kind]
            if item:
                lost = self.give_items({item: n})
                self.say(name + (' — no room to carry it all' if lost else ''), 2.5)
            else:
                self.say(name, 2.0)
        elif kind == 'study':
            self.sfx('landmark_study', self.human.getPos(self.render))
            cache, newly = self.landmarks.visit(target)
            lost = self.give_items(cache)
            text = target.lore
            if newly:
                text += f'\nIndigo gazes {self.bearing_words(newly[0].pos)}: there is more out there.'
                self.notice = {'pos': Point3(newly[0].pos), 't': NOTICE_TIME}
            if lost:
                text += '\n(you could not carry everything)'
            if self.landmarks.visited_count() == len(self.landmarks.items):
                text += '\nEvery marker found.'
            self.say(text, 7.0)
        elif kind == 'patch':
            if self.spend_pooled(PATCH_COST):
                self.shells.set_state(target, 'intact')
                self.sfx('patch', target.pos)
                self.say('shell patched — you can shelter in it now', 2.5)

    # -------------------------------------------------------------------- shells
    def enter_shell(self, s, walked_in: bool = False) -> bool:
        """Pass 55: you are inside the shell and can move about in it. walked_in: you walked
        through the mouth; otherwise (E at the mouth, a loaded save) you step in to its middle."""
        if s is None or s.state != 'intact' or s.occupied or not self.human_alive:
            return False
        # Pass 44 (B1): never go into a shell while Indigo is lifting / lowering you
        if self.carried or self.comp.get('mode') in ('pickup', 'setdown'):
            return False
        self.hidden_shell = s
        s.occupied = True
        self.sfx('shell_enter', s.pos)
        if not walked_in:
            p = self.shells.inner_spot(s)
            p.z = self.field.height(p.x, p.y) - self.human_actor.height_world * K['GROUND_SINK_FRACTION']
            self.human.setPos(p)
            self.human.setH(s.heading + 180.0)          # facing in, toward the back wall
        self.human.show()
        red_active = not (self.red_knocked_out or self.red_recovering or self.red_fleeing or self.red_lurking or self.red_dead)
        self.red_saw_hide = red_active and self._human_red_distance() <= self.red_detection_range()
        self.red_overturn_t = 0.0
        self.say('inside the shell. cool, quiet.', 2.0)
        return True

    def exit_shell(self, eject: bool = False):
        s = self.hidden_shell
        if s is None:
            return
        self.hidden_shell = None
        s.occupied = False
        s.shake = 0.0
        if not eject:
            self.sfx('shell_exit', s.pos)
        # Pass 55: walking out, you are already outside and stay where you are. Thrown out (or
        # sent out from code while still inside) you land in front of the mouth, facing out.
        inside = self.shells._q(*self.shells._local(s, self.human.getPos(self.render))) <= world.OUTSIDE_Q
        if eject or inside:
            p = s.entrance_point()
            if eject:
                h = math.radians(s.heading)
                p = Point3(p.x - math.sin(h) * 1.2, p.y + math.cos(h) * 1.2, 0)
            p.z = self.field.height(p.x, p.y) - self.human_actor.height_world * K['GROUND_SINK_FRACTION']
            self.human.setPos(p)
            self.human.setH(s.heading)
            self.human_actor.apply_clip('Crouch_Idle_Loop' if eject else 'Idle_Loop', 0.0, force=True)
        self.human.show()
        self.red_saw_hide = False
        self.red_overturn_t = 0.0

    def giant_clear_of_shells(self, actor, old: Point3, pos: Point3) -> Point3:
        """Pass 55: Indigo walks around shells, not through them (the red one strides over them;
        it has to reach you). Returns pos, with z re-read if it moved."""
        fixed = self.shells.keep_out(old, pos)
        if fixed.x != pos.x or fixed.y != pos.y:
            fixed.z = self.field.height(fixed.x, fixed.y) - actor.height_world * K['GROUND_SINK_FRACTION']
            return fixed
        return pos

    def _update_pickup(self, dt, hp):
        """Pass 57: Indigo does not reach through a shell's roof to lift you: if you are inside
        one when it comes for you, it waits outside."""
        c = self.comp
        if c.get('phase') == 'approach' and self.shells.inside(hp, limit=world.OUTSIDE_Q) is not None:
            c.update({'mode': 'stay', 'phase': '', 'elapsed': 0.0, 'moving': False, 'target': None})
            self.say('Nyx cannot reach you in there', 2.0)
            return
        super()._update_pickup(dt, hp)

    def _setdown_point(self) -> Point3:
        """Pass 57: never set you down in a shell's wall or on an overturned one."""
        p = super()._setdown_point()
        q = self.shells.clear_point(p, self.giant.getPos(self.render), pad=world.BODY_RADIUS + 0.15)
        if q.x != p.x or q.y != p.y:
            q.z = self.field.height(q.x, q.y) - self.human_actor.height_world * K['GROUND_SINK_FRACTION']
        return q

    def _update_shell_presence(self):
        """Pass 55: walking into an intact shell hides you in it; walking out leaves it."""
        if not self.human_alive or self.carried:
            return
        hp = self.human.getPos(self.render)
        s = self.hidden_shell
        if s is not None:
            if s.state != 'intact' or s.held or self.shells._q(*self.shells._local(s, hp)) > world.OUTSIDE_Q:
                self.exit_shell()
            return
        s = self.shells.inside(hp, ('intact',))
        if s is not None and not s.occupied:
            self.enter_shell(s, walked_in=True)

    def _update_shell_fade(self, dt: float):
        """Pass 55: the shell you stand in turns see-through, so the camera still shows you."""
        s = None
        if self.controlled_name == 'human' and self.human_alive and not self.carried:
            s = self.hidden_shell or self.shells.inside(self.human.getPos(self.render), limit=world.OUTSIDE_Q)
        if s is not None and s not in self.shell_fade:
            self.shell_fade[s] = 1.0
        for shell in list(self.shell_fade):
            want = SHELL_SEE_THROUGH if shell is s else 1.0
            a = _approach(self.shell_fade[shell], want, SHELL_FADE_RATE * dt)
            node = getattr(shell, 'node', None)
            if node is None or getattr(shell, 'held', False):
                a = 1.0
            if a >= 1.0:
                del self.shell_fade[shell]
                if node is not None:
                    node.clearTransparency()
                    node.setAlphaScale(1.0)
                    node.setDepthWrite(True)
                continue
            self.shell_fade[shell] = a
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setDepthWrite(False)
            node.setAlphaScale(a)

    def giant_shell_action(self) -> bool:
        """Giant-controlled E: lift the nearest empty shell, or set the held one down."""
        if not self.giant_alive or self.giant_action is not None:
            return False
        if self.kneel_state['phase'] != 'standing' or self.jump_states['giant']['active']:
            return False
        if self.giant_held_shell is not None:
            front = self.giant.getPos(self.render) + K['heading_forward'](self.giant.getH()) * 7.0
            self.shells.place(self.giant_held_shell, front, self.giant.getH() + 180.0)
            self.sfx('shell_place', self.giant_held_shell.pos)
            self.giant_held_shell = None
            return True
        s = self.shells.nearest(self.giant.getPos(self.render), GIANT_SHELL_REACH)
        if s is None or s.occupied or s.flip_t > 0.0:
            return False
        self.giant_action = {'clip': 'PickUp_Table', 't': 0.0, 'shell': s}
        self.giant_motion_speed = 0.0
        self.giant_actor.apply_clip('PickUp_Table', 0.0, force=True, loop=False)
        return True

    def _update_giant_action(self, dt: float) -> bool:
        a = self.giant_action
        if a is None:
            return False
        a['t'] += dt
        self.giant_actor.apply_clip(a['clip'], a['t'], loop=False)
        if a['t'] >= GIANT_PICKUP_TIME:
            self.giant_action = None
            s = a['shell']
            if not s.occupied:
                s.held = True
                self.giant_held_shell = s
                self.sfx('shell_lift', self.giant.getPos(self.render))
                self.shells._show(s)
            self.giant_actor.apply_clip('Idle_Loop', 0.0, force=True)
        return True

    def _update_held_shell(self):
        s = self.giant_held_shell
        if s is None:
            return
        if not self.giant_alive:
            self.shells.place(s, self.giant.getPos(self.render) + Vec3(5, 0, 0), self.giant.getH())
            self.giant_held_shell = None
            return
        if s.node is None:
            self.shells._show(s)
        hand = self.giant_actor.joint_world_point('hand_r', self.giant_actor.last_clip_time, self.render)
        s.pos = Point3(hand.x, hand.y, self.field.height(hand.x, hand.y))
        s.node.setPos(hand.x, hand.y, hand.z - 0.9)
        s.node.setHpr(self.giant.getH(), 0, 0)

    # ------------------------------------------------------------ shade, whistle
    def _issue_extra_order(self, name: str, point):
        c = self.comp
        if name == 'shade' and not self.carried:
            c.update({'mode': 'shade', 'moving': True, 'target': None, 'shade_lost': 0.0})
        elif name == 'whistle':
            self.whistle_alert = WHISTLE_ALERT
            threat = (not (self.red_knocked_out or self.red_recovering or self.red_fleeing or self.red_lurking or self.red_dead)
                      and self._human_red_distance() <= WHISTLE_TRIGGER_RANGE)
            if not threat and not self.carried:
                c.update({'mode': 'follow', 'moving': True, 'target': None})
            self.say('the whistle carries across the dunes', 1.5)

    def _shade_spot(self, hp: Point3) -> Point3:
        off = self._sun_offset()
        k = off.length()
        if k < 1e-4:
            return Point3(hp)
        direction = Vec3(off.x / k, off.y / k, 0)
        dist = max(SHADE_MIN_OFFSET, 0.55 * self.giant_height * k)   # Pass 52: the torso's shadow, not the shoulder's
        p = hp - direction * dist
        return Point3(p.x, p.y, self.field.height(p.x, p.y))

    def _update_shade_mode(self, dt: float, hp: Point3):
        c = self.comp
        spot = self._shade_spot(hp)
        if c['moving']:
            # Pass 52: stand within 0.8 m (was 1.5): at 1.5 m you could end up on the very edge of
            # the shadow, in or out depending on Indigo's breathing
            if self._ai_walk_giant(spot, dt, SHADE_STAND_PRECISION,
                                   jog=_flat_dist(self.giant.getPos(self.render), spot) > 40.0):
                c['moving'] = False
                c['shade_lost'] = 0.0
            return
        self.giant_motion_speed = 0.0
        self.giant_actor.apply_clip('Idle_Loop', globalClock.getFrameTime())
        if self.giant_shadow_contains(hp) or _flat_dist(self.giant.getPos(self.render), spot) <= 3.0:
            c['shade_lost'] = 0.0
        else:
            c['shade_lost'] = c.get('shade_lost', 0.0) + dt
            if c['shade_lost'] > 0.8:
                c['moving'] = True

    def indigo_aware(self) -> bool:
        """Does the Indigo Giant notice the human is in danger?"""
        if self.whistle_alert > 0.0 or self.carried:
            return True
        if self.hidden_shell is not None:
            return False
        return _flat_dist(self.giant.getPos(self.render), self.human.getPos(self.render)) <= INDIGO_AWARE_RANGE

    def defense_trigger_range(self) -> float:
        return WHISTLE_TRIGGER_RANGE if self.whistle_alert > 0.0 else K['INDIGO_DEFENSE_TRIGGER_RANGE']

    # --------------------------------------------------------------- sensing
    def _update_sense(self, dt: float):
        self._sense_timer -= dt
        if self.notice is not None:
            self.notice['t'] -= dt
            c = self.comp
            idle = (c['mode'] in ('stay', 'follow') and not c['moving'] and not self.indigo_defending
                    and self.kneel_state['phase'] == 'standing' and self.controlled_name == 'human'
                    and not self.attack_states['giant']['active'] and self.giant_action is None)
            if idle:
                self._face_point(self.notice['pos'], dt)
            if self.notice['t'] <= 0.0:
                self.notice = None
        if self._sense_timer > 0.0 or not self.giant_alive:
            return
        self._sense_timer = SENSE_PERIOD
        gp = self.giant.getPos(self.render)
        found = self.finds.sense(gp, SENSE_RANGE)
        if found and self.notice is None:
            self.notice = {'pos': Point3(found[0].pos), 't': NOTICE_TIME}
            self.sfx('hum_indigo_sense', Point3(gp.x, gp.y, gp.z + self.giant_height * 0.85))
            self.say(f'Nyx turns {self.bearing_words(found[0].pos)}' + (' — something there' if len(found) == 1
                     else f' — {len(found)} things out there'), 3.0)
        for lm in self.landmarks.items:
            if not lm.revealed and _flat_dist(lm.pos, gp) <= LANDMARK_SPOT_RANGE:
                self.landmarks.reveal(lm)
                self.notice = {'pos': Point3(lm.pos), 't': NOTICE_TIME}
                self.say(f'Nyx gazes {self.bearing_words(lm.pos)}, toward a shape on the horizon', 3.5)

    def bearing_words(self, p: Point3) -> str:
        """Direction of p relative to the camera view, in words (no map, no markers)."""
        hp = self.human.getPos(self.render)
        want = math.degrees(math.atan2(p.x - hp.x, p.y - hp.y))       # camera convention: 0 = +Y
        rel = _angle_delta(self.heading, want)
        words = ('ahead', 'ahead and to the right', 'to the right', 'behind you, to the right', 'behind you',
                 'behind you, to the left', 'to the left', 'ahead and to the left')
        return words[int(((rel + 22.5) % 360.0) // 45.0)]

    # ------------------------------------------------------------ red vs shells
    def _red_walk_to(self, target: Point3, dt: float, stop: float, walk_only: bool = False,
                     speed_k: float = 1.0) -> float:
        rp = self.red_giant.getPos(self.render)
        d = _flat_dist(rp, target)
        if d <= stop:
            self.red_motion_speed = _approach(self.red_motion_speed, 0.0, K['GIANT_BRAKING'] * dt)
            return d
        desired = K['heading_toward'](target.x - rp.x, target.y - rp.y)
        turn = K['GIANT_TURN_RATE_DEG'] * dt
        self.red_motion_heading += _clamp(_angle_delta(self.red_motion_heading, desired), -turn, turn)
        self.red_giant.setH(self.red_motion_heading)
        near = walk_only or d <= K['RED_APPROACH_WALK_RANGE']
        pace = (self.red_pace() if hasattr(self, 'red_pace') else 1.0) * speed_k   # tired / tracking
        clip, speed = locomotion.gait('giant', 'walk' if near else 'sprint')      # Pass 52
        speed *= pace
        self.red_motion_speed = _approach(self.red_motion_speed, speed, K['GIANT_ACCELERATION'] * dt)
        old = self.red_giant.getPos()
        pos = old + K['heading_forward'](self.red_motion_heading) * self.red_motion_speed * dt
        pos.z = self.field.height(pos.x, pos.y) - self.red_giant_actor.height_world * K['GROUND_SINK_FRACTION']
        self.red_giant.setPos(pos)
        self.stride('red', clip, Vec3(pos.x - old.x, pos.y - old.y, 0).length())   # feet match the ground
        return d

    def _update_red_vs_shell(self, dt: float, clock_t: float) -> bool:
        """Red Giant behaviour while the human hides.  Returns True when it handled the frame."""
        s = self.hidden_shell
        if s is None:
            self.red_shell_state = ''
            return False
        if self.giant_alive and self._giant_flat_distance() <= K['RED_ENGAGE_INDIGO_RANGE']:
            # Indigo is on it: fight instead of heaving at the shell.
            s.shake = 0.0
            self.red_overturn_t = 0.0
            self.red_shell_state = ''
            return False
        rp = self.red_giant.getPos(self.render)
        if not self.red_saw_hide and _flat_dist(rp, s.pos) > RED_SNIFF_RANGE:
            # It lost you: stand and listen.
            self.red_shell_state = 'searching'
            self.red_state = 'idle'
            self.red_motion_speed = _approach(self.red_motion_speed, 0.0, K['GIANT_BRAKING'] * dt)
            self.red_giant_actor.apply_clip('Idle_Loop', clock_t)
            return True
        self.red_saw_hide = True
        d = self._red_walk_to(s.pos, dt, RED_SHELL_STOP)
        if d > RED_SHELL_STOP:
            self.red_shell_state = 'to_shell'
            self.red_state = 'pursue'
            return True
        # heave
        self.red_shell_state = 'overturn'
        self.red_state = 'overturn'
        desired = K['heading_toward'](s.pos.x - rp.x, s.pos.y - rp.y)
        turn = K['GIANT_TURN_RATE_DEG'] * dt
        self.red_motion_heading += _clamp(_angle_delta(self.red_motion_heading, desired), -turn, turn)
        self.red_giant.setH(self.red_motion_heading)
        self.red_overturn_t += dt
        s.shake = _clamp(self.red_overturn_t / RED_OVERTURN_TIME, 0.15, 1.0)
        self.red_giant_actor.apply_clip('Push_Loop', self.red_overturn_t)
        if self.red_overturn_t >= RED_OVERTURN_TIME:
            self.shells.start_flip(s)
            self.sfx('shell_flip', s.pos)
            self.exit_shell(eject=True)
            self.human_dazed = EJECT_DAZE
            self.red_shell_state = ''
            self.red_state = 'pursue'
            self.red_stomp_cooldown = max(self.red_stomp_cooldown, 1.0)
            self.say('the shell rolls over — you are thrown out', 2.5)
        return True

    def red_shell_word(self) -> str:
        return {'searching': 'searching', 'to_shell': 'coming for your shell',
                'overturn': 'heaving at your shell!'}.get(self.red_shell_state, '')

    # --------------------------------------------------------------- per frame
    def survival_step(self, dt: float):
        self._desert_timer -= dt
        if self._desert_timer <= 0.0:
            self._desert_timer = 0.5
            self._refresh_world()
        self.whistle_alert = max(0.0, self.whistle_alert - dt)
        if self.human_dazed > 0.0:
            self.human_dazed = max(0.0, self.human_dazed - dt)
            if self.human_alive:
                self.human_actor.apply_clip('Crouch_Idle_Loop', globalClock.getFrameTime())
        self._update_sense(dt)
        self._update_heat(dt)
        self._update_held_shell()
        t = globalClock.getFrameTime()
        eye = self.camera.getPos(self.render)
        self.finds.update(dt, eye)
        self.shells.update(dt, t)
        self._update_shell_fade(dt)
        self.landmarks.update(t, eye)
        self._update_say(dt)
        super().survival_step(dt)
        if self.hidden_shell is not None and self.controlled_name == 'human':
            self.cam_target = self._controlled_focus()

    # --------------------------------------------------------------------- HUD
    def _update_survival_hud(self):
        hp = int(math.ceil(self.human_health)) if self.human_alive else 0
        where = {'sun': 'in the sun', 'shade': 'in shade', 'shell': 'in a shell', 'riding': 'riding in the sun',
                 'riding shaded': 'riding, shaded'}[self.shelter_word]
        winded = '  winded' if self.winded else ''
        lines = [f'orbit {hp:3d}   stamina {int(self.stamina):3d}{winded}   heat {int(self.heat):3d}  {where}']
        items = [f'{self.bag("human")[i]} {ITEM_LABEL[i]}' for i in ITEM_ORDER if self.bag('human')[i]]
        lines.append(f'bag {self.bag_count("human")}/{HUMAN_BAG}' + (':  ' + ', '.join(items) if items else ''))
        held = '   holding a shell' if self.giant_held_shell is not None else ''
        lines.append(f'nyx    {int(math.ceil(self.giant_health)):3d}   bag {self.bag_count("giant")}/{GIANT_BAG}'
                     f'   {self._companion_word()}{held}')
        red = self.red_shell_word() or self._red_word()
        lines.append(f'crimson {int(math.ceil(self.red_health)):3d}   {red}')
        lines.append(f'markers {self.landmarks.visited_count()}/{len(self.landmarks.items)}')
        prompt = self._prompt()
        if prompt:
            lines.append(prompt)
        text = '\n'.join(lines)
        if text != self._hud_cache:
            self._hud_cache = text
            self.status_text.setText(text)

    def _prompt(self) -> str:
        if not self.human_alive:
            return ''
        if self.controlled_name == 'giant':
            if not self.giant_alive:
                return ''
            if self.giant_held_shell is not None:
                return '[E] set the shell down'
            parts = []
            if self.shells.nearest(self.giant.getPos(self.render), GIANT_SHELL_REACH) is not None:
                parts.append('[E] lift shell')
            if self.giant_smash_target() is not None:
                parts.append('[F] smash branch')
            return '   '.join(parts)
        if self.hidden_shell is not None:
            return 'walk out through the mouth   [Q] whistle'
        kind, target = self._e_target()
        prompt = {'hide': '[E] step into the shell', 'dig': '[hold E] dig', 'smash': '[hold E] smash branch',
                  'patch': '[hold E] patch shell (3 scraps, 1 resin)'}.get(kind, '')
        if kind == 'study':
            prompt = f'[hold E] study the {target.kind}'
        wants_food = self.heat >= 45.0 or self.stamina < 50.0 or self.human_health < 70.0
        if wants_food and (self.pooled_count('pod') or self.pooled_count('gourd')):
            prompt = (prompt + '   ' if prompt else '') + '[G] eat'
        return prompt

    # ------------------------------------------------------------------ retry
    def reset_survival_after_retry(self):
        super().reset_survival_after_retry()
        if self.hidden_shell is not None:
            self.hidden_shell.occupied = False
            self.hidden_shell.shake = 0.0
            self.hidden_shell = None
        self.human.show()
        for s in list(self.shell_fade):
            self.shell_fade[s] = 0.999                  # fades back in on the next frame
        self.heat = 0.0
        self.stamina = STAMINA_MAX
        self.winded = False
        self.human_dazed = 0.0
        self.whistle_alert = 0.0
        self.notice = None
        self.giant_action = None
        if self.giant_held_shell is not None:
            base = self.giant_base_pos
            self.shells.place(self.giant_held_shell, Point3(base.x + 9, base.y, base.z), 0.0)
            self.giant_held_shell = None
        self.red_saw_hide = False
        self.red_overturn_t = 0.0
        self.e_hold.update({'kind': None, 'target': None, 't': 0.0, 'spent': False})
