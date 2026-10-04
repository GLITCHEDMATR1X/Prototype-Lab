"""Pass 38 — companion & survival layer for The Indigo Giant.

Direction: a Fantastic Planet / Journey-style survival game between a small human
and the Indigo Giant.  This module adds, on top of the Pass 37 movement/combat core:

GESTURES (human only, no text menus)
    1 / wheel-up      COME      the giant walks over and keeps following
    2 / wheel-right   STAY      the giant holds its ground
    3 / wheel-down    LIFT ME   the giant kneels, picks the human up onto its shoulder
                      (again)   SET ME DOWN
    4 / wheel-left    GO THERE  point at the ground (mouse cursor) and the giant walks there
    Hold the middle mouse button for the gesture wheel; flick toward a gesture, release.

RIDING
    While carried, hold W to let the giant walk where you look (AI travel), or click
    the ground / press 4 to send it somewhere.  TAB takes the reins (you steer the
    giant directly, still riding).  Carried humans cannot be stomped.

BLOOD BRANCHES (see flora.py)
    Stand close to heal (limited sap per plant).  Hold E beside one as the human, or
    press F near one as the giant, to smash it into scraps.  Scraps are picked up by
    walking over them (human carries 12, the giant 60).  T gives your scraps to the
    giant, Y takes scraps back.

RED GIANT — an ongoing threat that never dies
    Low health (<= 30) scares it off; zero knocks it out (then it flees).  After fleeing
    it lurks out of sight, regains strength and later returns, a little angrier each time.
"""
from __future__ import annotations

import math

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat,
                          GeomVertexWriter, ClockObject, Point3, TextNode, TransparencyAttrib, Vec3)

import flora
import locomotion

globalClock = ClockObject.getGlobalClock()

K: dict = {}   # tuning constants bound from main.py (bind_constants)

HUMAN_SCRAP_CAPACITY = 12
GIANT_SCRAP_CAPACITY = 60
GESTURE_TIME = 0.85
FOLLOW_STOP = 9.0
FOLLOW_RESUME = 18.0
FOLLOW_JOG_DISTANCE = 45.0
PICKUP_REACH = 4.4
GOTO_ARRIVE = 3.5
TRANSFER_RANGE = 14.0
KNEEL_ENTER_TIME = 1.20
LIFT_TIME = 0.9
LOWER_TIME = 0.9
HUMAN_SMASH_HOLD = 1.2
SITTING_PELVIS = 0.54          # Sitting_Idle_Loop pelvis height (source metres)
SHOULDER_SEAT_LIFT = 0.055     # fraction of giant height above the clavicle line
RED_SCARE_HEALTH = 30.0
RED_REGEN_PER_SEC = 1.2
RED_RETURN_BASE = 110.0
RED_RETURN_MIN = 45.0
RED_RETURN_PER_ANGER = 20.0
GESTURE_CLIPS = {'come': 'Interact', 'stay': 'Spell_Simple_Enter', 'lift': 'Idle_Talking_Loop',
                 'setdown': 'Idle_Talking_Loop', 'goto': 'Interact', 'shade': 'Spell_Simple_Enter',
                 'whistle': 'Idle_Talking_Loop'}
GESTURE_WORDS = {'come': 'come', 'stay': 'stay', 'lift': 'lift me', 'setdown': 'set me down', 'goto': 'go there',
                 'shade': 'shade me', 'whistle': '~ whistle ~'}
# Gesture wheel: six 60-degree sectors, angle measured from screen-right, counter-clockwise.
WHEEL_SLOTS = (('come', 90.0), ('stay', 30.0), ('shade', -30.0), ('lift', -90.0), ('goto', -150.0), ('whistle', 150.0))
WHEEL_RADIUS = 0.24
HUMAN_EXTRA_CLIPS = ('Interact', 'Spell_Simple_Enter', 'Idle_Talking_Loop', 'Sitting_Idle_Loop', 'Punch_Jab')


def bind_constants(namespace: dict) -> None:
    K.update(namespace)


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _approach(cur, target, amount):
    if cur < target:
        return min(target, cur + amount)
    return max(target, cur - amount)


def _angle_delta(cur, target):
    return ((target - cur + 180.0) % 360.0) - 180.0


def _flat_dist(a: Point3, b: Point3) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


class GoMarker:
    """Faint ring on the ground where a GO THERE gesture points.  Fades in ~4 s."""
    LIFETIME = 4.0

    def __init__(self, parent, point: Point3, radius: float = 2.6, width: float = 0.35, segments: int = 32):
        vdata = GeomVertexData('go_marker', GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
        vw = GeomVertexWriter(vdata, 'vertex')
        nw = GeomVertexWriter(vdata, 'normal')
        cw = GeomVertexWriter(vdata, 'color')
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(segments + 1):
            a = 2.0 * math.pi * i / segments
            for r in (radius - width, radius):
                vw.addData3(math.cos(a) * r, math.sin(a) * r, 0.0)
                nw.addData3(0, 0, 1)
                cw.addData4(0.42, 0.36, 0.30, 1.0)      # scuffed-sand ring, not a glowing marker
            if i:
                b = (i - 1) * 2
                tris.addVertices(b, b + 1, b + 3)
                tris.addVertices(b, b + 3, b + 2)
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode('go_marker')
        node.addGeom(geom)
        self.root = parent.attachNewNode(node)
        self.root.setPos(point.x, point.y, point.z + 0.12)
        self.root.setTwoSided(True)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.root.setDepthWrite(False)
        self.root.setBin('transparent', 5)
        self.age = 0.0

    def update(self, dt: float) -> bool:
        self.age += dt
        if self.age >= self.LIFETIME:
            self.root.removeNode()
            return False
        pulse = 1.0 + 0.08 * math.sin(self.age * 6.0)
        self.root.setScale(pulse)
        self.root.setAlphaScale(0.45 * (1.0 - self.age / self.LIFETIME))
        return True


class SurvivalMixin:
    """Mixed into StreamingTerrainWithGiant (ShowBase)."""

    def sfx(self, name, pos=None, volume=1.0, delay=0.0):
        """Sound hook; audio.AudioMixin overrides it (silent when audio is not mixed in)."""
        return None

    # ------------------------------------------------------------------ setup
    def _init_survival(self, seed: int):
        self.carried = False
        self.comp = {'mode': 'stay', 'phase': '', 'elapsed': 0.0, 'target': None, 'moving': False,
                     'lift_from': None, 'lower_to': None}
        self.gesture = None
        self.human_scraps = 0
        self.giant_scraps = 0
        self.smash_hold = 0.0
        self.pending_smash = None
        self.red_anger = 0
        self.red_lurking = False
        self.red_lurk_elapsed = 0.0
        self.red_returning = False
        self.red_scare_count = 0
        self._hud_cache = ''
        self._go_marker = None
        self._gesture_alpha = 0.0
        self._wheel = None
        self._flora_timer = 0.0
        for clip in HUMAN_EXTRA_CLIPS:
            self.human_actor._load_clip(self.giant_glb, clip)
        if 'PickUp_Table' not in self.giant_actor.clips:
            self.giant_actor._load_clip(self.giant_glb, 'PickUp_Table')
        self.flora = flora.FloraField(self.render, self.field, seed, self.human.getPos(self.render))
        self.flora.update_active(self.human.getPos(self.render))

        self.status_text = OnscreenText(text='', pos=(-1.30, 0.80), align=TextNode.ALeft, scale=0.034,
                                        fg=(0.12, 0.10, 0.12, 0.85), mayChange=True)
        self.gesture_text = OnscreenText(text='', pos=(0.0, -0.64), align=TextNode.ACenter, scale=0.05,
                                         fg=(0.20, 0.24, 0.42, 0.0), mayChange=True)
        self._wheel_labels = {}
        for name, ang in WHEEL_SLOTS:
            x, y = math.cos(math.radians(ang)) * WHEEL_RADIUS * 1.25, math.sin(math.radians(ang)) * WHEEL_RADIUS
            t = OnscreenText(text=GESTURE_WORDS[name], pos=(x, y), align=TextNode.ACenter, scale=0.05,
                             fg=(0.15, 0.15, 0.2, 0.75), mayChange=True)
            t.hide()
            self._wheel_labels[name] = t

        for action, name in (('come', 'come'), ('stay', 'stay'), ('lift', 'lift'), ('go_there', 'goto'),
                             ('shade', 'shade'), ('whistle', 'whistle')):
            self.bind_action(action, self.gesture_command, [name])
        self.bind_action('give_to_giant', self.transfer_scraps, [True])
        self.bind_action('take_from_giant', self.transfer_scraps, [False])
        self.accept('mouse1', self._on_left_click)
        self.accept('mouse2', self._wheel_open)
        self.accept('mouse2-up', self._wheel_release)
        self.keys.setdefault('e', False)

    def _set_key_extra(self, key, value):
        self.keys[key] = value

    # --------------------------------------------------------------- gestures
    def gesture_command(self, name: str, ground_point: Point3 | None = None) -> bool:
        if self.input_blocked():
            return False
        if self.controlled_name != 'human' or not self.human_alive or not self.giant_alive:
            return False
        if self.jump_states['human']['active'] and not self.carried:   # Pass 44 (B11): sign on the ground
            return False
        # Pass 55: inside a shell Indigo cannot lift you or go anywhere for you (it would have to
        # reach in); every other sign works. Dazed hands cannot sign.
        if getattr(self, 'hidden_shell', None) is not None and name in ('lift', 'goto'):
            return False
        if getattr(self, 'human_dazed', 0.0) > 0.0 and name != 'whistle':
            return False
        if name == 'lift' and self.carried:
            name = 'setdown'
        if name in ('lift',) and self.comp['mode'] in ('pickup', 'setdown'):
            return False
        if name == 'goto' and ground_point is None:
            ground_point = self._ground_point_under_mouse() or self._ground_point_ahead()
        self.gesture = {'name': name, 'elapsed': 0.0}
        if not self.carried and self.human_alive:
            clip = GESTURE_CLIPS[name]
            self.human_actor.apply_clip(clip, 0.0, force=True, loop=False)
        self.gesture_text.setText(GESTURE_WORDS[name])
        self._gesture_alpha = 0.9
        self.gesture_text.setFg((0.20, 0.24, 0.42, self._gesture_alpha))
        sound = 'whistle' if name == 'whistle' else 'gesture_' + ('lift' if name == 'setdown' else name)
        self.sfx(sound, self.human.getPos(self.render))
        self._issue_companion_order(name, ground_point)
        return True

    def _issue_companion_order(self, name: str, point: Point3 | None):
        c = self.comp
        if name == 'come':
            if not self.carried:
                c.update({'mode': 'follow', 'moving': True, 'target': None})
        elif name == 'stay':
            c.update({'mode': 'carry' if self.carried else 'stay', 'moving': False, 'target': None})
        elif name == 'goto' and point is not None:
            c.update({'mode': 'carry' if self.carried else 'goto', 'target': Point3(point), 'moving': True})
            self._drop_marker(point)
        elif name == 'lift' and not self.carried:
            c.update({'mode': 'pickup', 'phase': 'approach', 'elapsed': 0.0, 'target': None})
        elif name == 'setdown' and self.carried:
            c.update({'mode': 'setdown', 'phase': 'kneel', 'elapsed': 0.0, 'target': None})
            self._begin_ai_kneel()
        else:
            self._issue_extra_order(name, point)

    def _issue_extra_order(self, name: str, point: Point3 | None):
        """Extended by later passes (shade, whistle)."""

    def _update_gesture(self, dt: float) -> bool:
        """Returns True while the human is busy performing a gesture."""
        if self._gesture_alpha > 0.0:
            self._gesture_alpha = max(0.0, self._gesture_alpha - dt * 0.7)
            self.gesture_text.setFg((0.20, 0.24, 0.42, self._gesture_alpha))
        if self.gesture is None:
            return False
        self.gesture['elapsed'] += dt
        visible = not self.carried
        if visible:
            clip = GESTURE_CLIPS[self.gesture['name']]
            self.human_actor.apply_clip(clip, self.gesture['elapsed'] * 1.2, loop=False)
        if self.gesture['elapsed'] >= GESTURE_TIME:
            self.gesture = None
            if visible:
                self.human_actor.apply_clip('Idle_Loop', 0.0, force=True)
            return False
        return True

    # gesture wheel (middle mouse)
    def _wheel_open(self):
        if self.input_blocked():
            return
        if self.controlled_name != 'human' or not self._has_mouse():
            return
        m = self.mouseWatcherNode.getMouse()
        self._wheel = {'origin': (m.x, m.y), 'choice': None, 'point': self._ground_point_under_mouse()}
        self._wheel_labels['lift'].setText('set me down' if self.carried else 'lift me')
        for t in self._wheel_labels.values():
            t.show()

    def _wheel_choice(self):
        if self._wheel is None or not self._has_mouse():
            return None
        m = self.mouseWatcherNode.getMouse()
        dx, dy = m.x - self._wheel['origin'][0], m.y - self._wheel['origin'][1]
        if math.hypot(dx, dy) < 0.06:
            return None
        ang = math.degrees(math.atan2(dy, dx))
        return min(WHEEL_SLOTS, key=lambda slot: abs(_angle_delta(ang, slot[1])))[0]

    def _update_wheel(self):
        if self._wheel is None:
            return
        choice = self._wheel_choice()
        for name, t in self._wheel_labels.items():
            t.setFg((0.55, 0.12, 0.10, 1.0) if name == choice else (0.15, 0.15, 0.2, 0.7))

    def _wheel_release(self):
        if self._wheel is None:
            return
        choice = self._wheel_choice()
        point = self._wheel['point']
        self._wheel = None
        for t in self._wheel_labels.values():
            t.hide()
        if choice:
            self.gesture_command(choice, point if choice == 'goto' else None)

    def _on_left_click(self):
        if self.input_blocked():
            return
        # While riding (human view), clicking the ground sends the giant there.
        if self.controlled_name == 'human' and self.carried and self._wheel is None:
            p = self._ground_point_under_mouse()
            if p is not None:
                self.gesture_command('goto', p)
        elif self.controlled_name == 'giant' and hasattr(self, 'attack_press'):
            self.attack_press('mouse')             # Pass 58: you are Indigo - left mouse fights

    # ---------------------------------------------------------- ground picking
    def _has_mouse(self) -> bool:
        mw = getattr(self, 'mouseWatcherNode', None)
        return mw is not None and mw.hasMouse()

    def _ground_point_under_mouse(self):
        if not self._has_mouse():
            return None
        m = self.mouseWatcherNode.getMouse()
        near, far = Point3(), Point3()
        if not self.camLens.extrude(m, near, far):
            return None
        a = self.render.getRelativePoint(self.cam, near)
        b = self.render.getRelativePoint(self.cam, far)
        return self._march_ray(a, b)

    def _ground_point_ahead(self):
        a = self.cam.getPos(self.render)
        forward = self.render.getRelativeVector(self.cam, Vec3(0, 1, 0))
        return self._march_ray(a, a + forward * 400.0)

    def _march_ray(self, a: Point3, b: Point3):
        d = b - a
        length = d.length()
        if length < 1e-6:
            return None
        d /= length
        prev = a
        step = 1.0
        t = 0.0
        while t < min(length, 420.0):
            t += step
            p = a + d * t
            if p.z <= self.field.height(p.x, p.y):
                # refine between prev and p
                lo, hi = prev, p
                for _ in range(10):
                    mid = (lo + hi) * 0.5
                    if mid.z <= self.field.height(mid.x, mid.y):
                        hi = mid
                    else:
                        lo = mid
                return Point3(hi.x, hi.y, self.field.height(hi.x, hi.y))
            prev = p
            step = min(4.0, step * 1.15)
        return None

    def _drop_marker(self, point: Point3):
        if getattr(self, '_go_marker', None) is not None:
            self._go_marker.root.removeNode()
        self._go_marker = GoMarker(self.render, point)

    # ------------------------------------------------------------ companion AI
    def companion_busy(self) -> bool:
        c = self.comp
        return (c['mode'] in ('pickup', 'setdown') or (c['mode'] in ('follow', 'goto') and c['moving'])
                or self.carried and c['moving'])

    def _ai_walk_giant(self, target: Point3, dt: float, stop: float, jog: bool = False) -> bool:
        """Heavy-locomotion walk toward target. Returns True once within stop distance."""
        gp = self.giant.getPos(self.render)
        if getattr(self, 'shells', None) is not None:
            target = self.shells.clear_point(target, gp)       # Pass 55: never aim to stand in a shell
        dist = _flat_dist(gp, target)
        pace = self.giant_pace() if hasattr(self, 'giant_pace') else 1.0     # Pass 48: the cold slows it
        clip, speed_goal = locomotion.gait('giant', 'jog' if jog else 'walk')      # Pass 52
        speed_goal *= pace
        rate = spacing = 0.0                     # unused since Pass 52 (the ground drives the cycle)
        arrived = dist <= stop
        if not arrived:
            desired = K['heading_toward'](target.x - gp.x, target.y - gp.y)
            delta = _angle_delta(self.giant_motion_heading, desired)
            turn = K['GIANT_TURN_RATE_DEG'] * dt
            self.giant_motion_heading += _clamp(delta, -turn, turn)
            # Slow down for tight turns and when close, so it never overshoots the human.
            ease = _clamp((dist - stop) / 12.0, 0.25, 1.0) * (0.35 if abs(delta) > 60 else 1.0)
            self.giant_motion_speed = _approach(self.giant_motion_speed, speed_goal * ease, K['GIANT_ACCELERATION'] * dt)
        else:
            self.giant_motion_speed = _approach(self.giant_motion_speed, 0.0, K['GIANT_BRAKING'] * dt)
        self._ai_giant_step(dt, clip, rate, spacing, speed_goal)
        return arrived and self.giant_motion_speed <= 0.05

    def _ai_giant_step(self, dt, clip, rate, spacing, speed_goal):
        if self.giant_motion_speed > 0.035:
            travel = K['heading_forward'](self.giant_motion_heading)
            old = self.giant.getPos()
            pos = old + travel * self.giant_motion_speed * dt
            pos.z = self.field.height(pos.x, pos.y) - self.giant_actor.height_world * K['GROUND_SINK_FRACTION']
            if hasattr(self, 'giant_clear_of_shells'):
                pos = self.giant_clear_of_shells(self.giant_actor, old, pos)   # Pass 55
            self.giant.setPos(pos)
            self.giant.setH(self.giant_motion_heading)
            self.stride('giant', clip, Vec3(pos.x - old.x, pos.y - old.y, 0).length())   # Pass 52
        else:
            self.giant_actor.apply_clip('Idle_Loop', globalClock.getFrameTime())

    def _face_point(self, target: Point3, dt: float):
        gp = self.giant.getPos(self.render)
        if _flat_dist(gp, target) < 0.5:
            return 0.0
        desired = K['heading_toward'](target.x - gp.x, target.y - gp.y)
        delta = _angle_delta(self.giant.getH(), desired)
        turn = K['GIANT_TURN_RATE_DEG'] * dt
        self.giant.setH(self.giant.getH() + _clamp(delta, -turn, turn))
        self.giant_motion_heading = self.giant.getH()
        return abs(delta)

    def _begin_ai_kneel(self):
        self.giant_motion_speed = 0.0
        self.kneel_state.update({'phase': 'enter', 'elapsed': 0.0})
        self.giant_actor.apply_clip('Fixing_Kneeling', 0.0, force=True, loop=False)

    def _update_companion(self, dt: float):
        """Runs after the defender logic.  Only drives the giant when nothing else does."""
        if not self.giant_alive:
            if self.carried:
                self._release_human(beside=True)
            return
        c = self.comp
        # Pass 44 (B6): a downed human is never lifted, carried or lowered
        if not self.human_alive and c['mode'] in ('pickup', 'setdown', 'carry'):
            self.abort_carry()
        mode = c['mode']
        # A carried human hands the giant to the player on TAB; the AI then only keeps the rider attached.
        if self.controlled_name != 'human':
            return
        if self.indigo_defending:
            return
        if self.attack_states['giant']['active']:
            # A punch (or branch smash) that was cut short when the defence ended must still
            # play out; otherwise the swing stays 'active' forever and the companion freezes.
            self._update_melee_state('giant', dt, globalClock.getFrameTime())
            return
        hp = self.human.getPos(self.render)
        if mode == 'follow':
            d = _flat_dist(self.giant.getPos(self.render), hp)
            if not c['moving'] and d > FOLLOW_RESUME:
                c['moving'] = True
            if c['moving']:
                if self._ai_walk_giant(hp, dt, FOLLOW_STOP, jog=d > FOLLOW_JOG_DISTANCE):
                    c['moving'] = False
            else:
                self._face_point(hp, dt)
                self.giant_actor.apply_clip('Idle_Loop', globalClock.getFrameTime())
        elif mode == 'goto':
            if self._ai_walk_giant(c['target'], dt, GOTO_ARRIVE, jog=_flat_dist(self.giant.getPos(self.render), c['target']) > FOLLOW_JOG_DISTANCE):
                c.update({'mode': 'stay', 'moving': False, 'target': None})
        elif mode == 'stay':
            c['moving'] = False
            self.giant_motion_speed = 0.0
            if self.kneel_state['phase'] != 'standing':      # an aborted pickup stands back up
                if self.kneel_state['phase'] in ('enter', 'kneeling'):
                    self.kneel_state.update({'phase': 'exit', 'elapsed': 0.0})
                self._update_kneel(dt)
        elif mode == 'pickup':
            self._update_pickup(dt, hp)
        elif mode == 'setdown':
            self._update_setdown(dt)
        elif mode == 'carry':
            self._update_carry_travel(dt)
        elif mode == 'shade':
            self._update_shade_mode(dt, hp)

    def _update_pickup(self, dt, hp):
        c = self.comp
        c['elapsed'] += dt
        if c['phase'] == 'approach':
            if self._ai_walk_giant(hp, dt, PICKUP_REACH):
                if self._face_point(hp, dt) < 8.0:
                    c.update({'phase': 'kneel', 'elapsed': 0.0})
                    self._begin_ai_kneel()
        elif c['phase'] == 'kneel':
            self._update_kneel(dt)
            if self.kneel_state['phase'] == 'kneeling':
                c.update({'phase': 'lift', 'elapsed': 0.0, 'lift_from': Point3(hp)})
                self.carried = True
                self.human_actor.apply_clip('Sitting_Idle_Loop', 0.0, force=True)
        elif c['phase'] == 'lift':
            self._update_kneel(dt)
            if c['elapsed'] >= LIFT_TIME:
                c.update({'phase': 'rise', 'elapsed': 0.0})
                self.kneel_state.update({'phase': 'exit', 'elapsed': 0.0})
        elif c['phase'] == 'rise':
            self._update_kneel(dt)
            if self.kneel_state['phase'] == 'standing':
                c.update({'mode': 'carry', 'phase': '', 'elapsed': 0.0, 'moving': False, 'target': None})

    def _update_setdown(self, dt):
        c = self.comp
        c['elapsed'] += dt
        if c['phase'] == 'kneel':
            self._update_kneel(dt)
            if self.kneel_state['phase'] == 'kneeling':
                c.update({'phase': 'lower', 'elapsed': 0.0, 'lower_to': self._setdown_point()})
        elif c['phase'] == 'lower':
            self._update_kneel(dt)
            if c['elapsed'] >= LOWER_TIME:
                self._release_human(beside=False)
                c.update({'phase': 'rise', 'elapsed': 0.0})
                self.kneel_state.update({'phase': 'exit', 'elapsed': 0.0})
        elif c['phase'] == 'rise':
            self._update_kneel(dt)
            if self.kneel_state['phase'] == 'standing':
                c.update({'mode': 'stay', 'phase': '', 'elapsed': 0.0, 'moving': False})

    def _update_carry_travel(self, dt):
        """Riding: hold W to walk where you look; or travel to a GO THERE point."""
        c = self.comp
        jog = bool(self.keys.get('shift'))
        if self.keys.get('w'):
            h = math.radians(self.heading)
            ahead = self.giant.getPos(self.render) + Vec3(math.sin(h), math.cos(h), 0) * 60.0
            c['target'] = None
            c['moving'] = True
            self._ai_walk_giant(ahead, dt, 0.0, jog=jog)
            return
        if c['target'] is not None:
            c['moving'] = True
            if self._ai_walk_giant(c['target'], dt, GOTO_ARRIVE, jog=jog):
                c.update({'target': None, 'moving': False})
            return
        c['moving'] = self.giant_motion_speed > 0.05
        self._ai_walk_giant(self.giant.getPos(self.render), dt, 1e9)

    def _setdown_point(self) -> Point3:
        fwd = K['heading_forward'](self.giant.getH())
        right = Vec3(fwd.y, -fwd.x, 0)
        p = self.giant.getPos(self.render) + fwd * 3.2 + right * 1.6
        p.z = self.field.height(p.x, p.y) - self.human_actor.height_world * K['GROUND_SINK_FRACTION']
        return p

    def abort_carry(self):
        """Pass 44 (B6): drop any lift / ride / set-down in progress and let Indigo wait."""
        if self.carried:
            self._release_human(beside=True)
        self.comp.update({'mode': 'stay', 'phase': '', 'elapsed': 0.0, 'target': None, 'moving': False,
                          'lift_from': None, 'lower_to': None})

    def _release_human(self, beside: bool):
        self.carried = False
        p = self._setdown_point() if beside or self.comp.get('lower_to') is None else self.comp['lower_to']
        self.human.setPos(p)
        self.human.setP(0)
        self.human.setR(0)
        self.human_actor.apply_clip('Idle_Loop', 0.0, force=True)
        self.comp['lower_to'] = None
        self.jump_states['human'].update({'active': False, 'phase': 'ground', 'elapsed': 0.0, 'vz': 0.0})

    # --------------------------------------------------------------- the rider
    def _carry_anchor(self) -> Point3:
        a = self.giant_actor.joint_world_point('clavicle_l', self.giant_actor.last_clip_time, self.render)
        b = self.giant_actor.joint_world_point('upperarm_l', self.giant_actor.last_clip_time, self.render)
        seat = a + (b - a) * 0.65   # nearer the shoulder cap than the neck
        seat.z += self.giant_height * SHOULDER_SEAT_LIFT - SITTING_PELVIS * self.human_actor.scale
        return seat

    def _update_rider(self, dt: float):
        c = self.comp
        if not self.carried or not self.human_alive:
            return
        seat = self._carry_anchor()
        if c['mode'] == 'pickup' and c['phase'] == 'lift' and c.get('lift_from') is not None:
            t = _clamp(c['elapsed'] / LIFT_TIME, 0.0, 1.0)
            s = t * t * (3 - 2 * t)
            start = c['lift_from']
            seat = start + (seat - start) * s
            seat.z += math.sin(t * math.pi) * self.giant_height * 0.06
        elif c['mode'] == 'setdown' and c['phase'] == 'lower' and c.get('lower_to') is not None:
            t = _clamp(c['elapsed'] / LOWER_TIME, 0.0, 1.0)
            s = t * t * (3 - 2 * t)
            end = c['lower_to']
            seat = seat + (end - seat) * s
        self.human.setPos(seat)
        self.human.setH(self.giant.getH())
        self.human_actor.apply_clip('Sitting_Idle_Loop', globalClock.getFrameTime())

    # -------------------------------------------------------- flora & scraps
    def _update_survival_world(self, dt: float):
        self._flora_timer -= dt
        if self._flora_timer <= 0.0:
            self._flora_timer = 0.5
            focus = self.giant.getPos(self.render) if self.controlled_name == 'giant' else self.human.getPos(self.render)
            self.flora.update_active(focus)
        hp = self.human.getPos(self.render)
        gp = self.giant.getPos(self.render)
        if self.human_alive and not self.carried and self.human_health < K['HUMAN_MAX_HEALTH']:
            self.human_health += self.flora.heal_amount(hp, flora.HUMAN_HEAL_RADIUS, flora.HUMAN_HEAL_RATE, dt,
                                                        K['HUMAN_MAX_HEALTH'] - self.human_health)
        if self.giant_alive and self.giant_health < K['GIANT_MAX_HEALTH']:
            self.giant_health += self.flora.heal_amount(gp, flora.GIANT_HEAL_RADIUS, flora.GIANT_HEAL_RATE, dt,
                                                        K['GIANT_MAX_HEALTH'] - self.giant_health)
        if self.human_alive and not self.carried:
            self.human_scraps += self.flora.collect_scraps(hp, flora.SCRAP_HUMAN_PICKUP, self.bag_space('human'))
        if self.giant_alive:
            self.giant_scraps += self.flora.collect_scraps(gp, flora.SCRAP_GIANT_PICKUP, self.bag_space('giant'))
        self._update_e_hold(dt)
        self.flora.update(dt)

    def human_is_smashing(self) -> bool:
        return self.smash_hold > 0.0

    def bag_space(self, owner: str) -> int:
        if owner == 'human':
            return HUMAN_SCRAP_CAPACITY - self.human_scraps
        return GIANT_SCRAP_CAPACITY - self.giant_scraps

    def _update_e_hold(self, dt: float):
        """Pass 38 behaviour (overridden in desert.py): hold E beside a branch to smash it."""
        hp = self.human.getPos(self.render)
        if (self.controlled_name == 'human' and self.human_alive and not self.carried
                and self.keys.get('e') and self.gesture is None):
            target = self.flora.nearest_intact(hp, flora.SMASH_RANGE_HUMAN)
            if target is not None:
                self.smash_hold += dt
                self.human_actor.apply_clip('Punch_Jab', (self.smash_hold * 1.4) % self.human_actor.clips['Punch_Jab']['duration'], loop=False)
                if self.smash_hold >= HUMAN_SMASH_HOLD:
                    self.flora.smash(target)
                    self.smash_hold = 0.0
                    self.human_actor.apply_clip('Idle_Loop', 0.0, force=True)
                return
        self.smash_hold = 0.0

    def transfer_scraps(self, to_giant: bool) -> int:
        if not (self.human_alive and self.giant_alive):
            return 0
        near = self.carried or _flat_dist(self.human.getPos(self.render), self.giant.getPos(self.render)) <= TRANSFER_RANGE
        if not near:
            return 0
        if to_giant:
            moved = min(self.human_scraps, GIANT_SCRAP_CAPACITY - self.giant_scraps)
            self.human_scraps -= moved
            self.giant_scraps += moved
        else:
            moved = min(self.giant_scraps, HUMAN_SCRAP_CAPACITY - self.human_scraps)
            self.giant_scraps -= moved
            self.human_scraps += moved
        return moved

    def giant_smash_target(self):
        """Branch the giant would smash with F, or None."""
        return self.flora.nearest_intact(self.giant.getPos(self.render), flora.SMASH_RANGE_GIANT)

    # ---------------------------------------------------------------- red boss
    def red_scare_check(self):
        """Called after the red giant takes a hit.  Low stamina (sneaky) or low health scares it off."""
        if self.red_knocked_out or self.red_fleeing:
            return
        # Pass 53: a sneaky red one runs when nearly out of stamina (an aggressive one fights on)
        spent = self.red_should_flee() if hasattr(self, 'red_should_flee') else False
        if spent or 0.0 < self.red_health <= RED_SCARE_HEALTH:
            self.red_fleeing = True
            self.red_flee_elapsed = 0.0
            self.red_state = 'flee'
            self.red_scare_count += 1
            self.red_anger += 1
            self.attack_states['red'].update({'active': False, 'elapsed': 0.0, 'hit_done': False})

    def red_begin_lurk(self):
        """After fleeing to safety: lurk out of sight, regain strength, return later."""
        self.red_lurking = True
        self.red_lurk_elapsed = 0.0
        self.red_returning = False
        self.red_state = 'lurk'

    def red_return_delay(self) -> float:
        return max(RED_RETURN_MIN, RED_RETURN_BASE - RED_RETURN_PER_ANGER * self.red_anger)

    def red_stomp_cooldown_value(self) -> float:
        return max(1.4, K['RED_STOMP_COOLDOWN'] - 0.25 * self.red_anger)

    def _update_red_lurk(self, dt: float, clock_t: float) -> bool:
        if not self.red_lurking:
            if not self.red_knocked_out and self.red_state in ('idle',):
                self.red_health = min(K['GIANT_MAX_HEALTH'], self.red_health + RED_REGEN_PER_SEC * 0.5 * dt)
            return False
        self.red_lurk_elapsed += dt
        self.red_state = 'lurk'
        self.red_health = min(K['GIANT_MAX_HEALTH'], self.red_health + RED_REGEN_PER_SEC * dt)
        self.red_motion_speed = _approach(self.red_motion_speed, 0.0, K['GIANT_BRAKING'] * dt)
        self.red_giant_actor.apply_clip('Idle_Loop', clock_t)
        if self.red_lurk_elapsed >= self.red_return_delay():
            self.red_lurking = False
            self.red_returning = True
            self.red_state = 'pursue'
        return True

    def red_target_is_human_blocked(self) -> bool:
        """A carried human is out of stomping reach; the red giant must go through Indigo."""
        return self.carried

    # --------------------------------------------------------------------- HUD
    def _companion_word(self) -> str:
        c = self.comp
        if not self.giant_alive:
            return 'down'
        if self.indigo_defending:
            return 'defending'
        if c['mode'] == 'carry':
            return 'carrying you' + (' — walking' if c['moving'] else '')
        return {'follow': 'following', 'stay': 'staying', 'goto': 'going there',
                'pickup': 'lifting you', 'setdown': 'setting you down'}.get(c['mode'], c['mode'])

    def _red_word(self) -> str:
        if self.red_knocked_out:
            return f'knocked out {int(self.red_knockout_remaining)}s'
        if self.red_recovering:
            return 'getting up'
        if self.red_fleeing:
            return 'scared off'
        if self.red_lurking:
            return 'lurking'
        if self.red_state == 'pursue' and not self.red_returning and hasattr(self, 'red_mood'):
            return 'hunting' if self.red_mood() == 'aggressive' else 'stalking'
        return {'pursue': 'returning' if self.red_returning else 'hunting', 'melee': 'fighting',
                'track': 'following your tracks', 'forage': 'looking for food', 'meal': 'eating',
                'rest': 'resting in the cold', 'watching': 'standing very still',
                'stomp': 'stomping', 'idle': 'wandering', 'bait': 'drawn to the pale branch',
                'eating': 'eating', 'sick': 'swaying', 'dead': 'still'}.get(self.red_state, self.red_state)

    def _update_survival_hud(self):
        hp = int(math.ceil(self.human_health)) if self.human_alive else 0
        text = (f'orbit {hp:3d}   scraps {self.human_scraps}/{HUMAN_SCRAP_CAPACITY}\n'
                f'nyx    {int(math.ceil(self.giant_health)):3d}   scraps {self.giant_scraps}/{GIANT_SCRAP_CAPACITY}   {self._companion_word()}\n'
                f'crimson {int(math.ceil(self.red_health)):3d}   {self._red_word()}')
        near = None
        if self.controlled_name == 'human' and self.human_alive and not self.carried:
            if self.flora.nearest_intact(self.human.getPos(self.render), flora.SMASH_RANGE_HUMAN):
                near = '[hold E] smash branch'
        elif self.controlled_name == 'giant' and self.giant_alive and self.giant_smash_target() is not None:
            near = '[F] smash branch'
        if near:
            text += f'\n{near}'
        if text != self._hud_cache:
            self._hud_cache = text
            self.status_text.setText(text)

    # -------------------------------------------------------------- per frame
    def _survival_task(self, task):
        dt = min(globalClock.getDt(), 0.05)
        self.survival_step(dt)
        return task.cont

    def survival_step(self, dt: float):
        marker = getattr(self, '_go_marker', None)
        if marker is not None and not marker.update(dt):
            self._go_marker = None
        self._update_wheel()
        self._update_companion(dt)
        self._update_rider(dt)
        self._update_survival_world(dt)
        self._update_survival_hud()
        if self.carried and self.controlled_name == 'human':
            self.cam_target = self._controlled_focus()

    def reset_survival_after_retry(self):
        if self.carried:
            self.carried = False
        self.comp.update({'mode': 'stay', 'phase': '', 'elapsed': 0.0, 'target': None, 'moving': False,
                          'lift_from': None, 'lower_to': None})
        self.gesture = None
        self.smash_hold = 0.0
        self.pending_smash = None
        self.red_lurking = False
        self.red_returning = False
        self.red_lurk_elapsed = 0.0
