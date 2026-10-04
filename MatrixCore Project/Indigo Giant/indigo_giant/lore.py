"""Pass 61 - etchings: little notes of lore hidden across the desert.

Fourteen standing stones, each cut with a few lines of glowing glyphs. The small people who
lived here long ago left them. Read in order (nearest first), they tell who Nyx, Orbit and
Crimson are, why this world is called REDACTED, that it is dying, and that someone called
Gleebs once came here in a beam of light.

  - The first stands ~60 m from where the journey starts; the last ~9.5 km out.
  - By day the etching is a faint pale-cyan scratch; at night it glows, and a soft glimmer
    over the stone shows it from ~250 m away.
  - Hold E beside it (1 s) to read it. Read etchings dim a little; you can read them again.
  - J > notes: every etching you have read.
"""
from __future__ import annotations

import math
import random

from panda3d.core import (CardMaker, ColorBlendAttrib, NodePath, PNMImage, Point3, Texture, TransparencyAttrib,
                          Vec3, Vec4)

from . import desert
from . import sky
from .desert_geom import Mesh
from .survival import K, _flat_dist

READ_RANGE = 2.4                      # metres from the stone to read it
HOLD_TIME = 1.0
STONE_H = 1.25
STONE_W = (0.86, 0.62)                # base, top
STONE_D = 0.30
STONE_COLOUR = Vec4(0.86, 0.82, 0.74, 1.0)
GLYPH_COLOUR = (0.45, 0.95, 1.00)     # the light the etching holds
CUT_COLOUR = (0.30, 0.27, 0.25, 0.75)  # the marks as cut stone
GLYPH_DAY = 0.22                      # how bright an etching is by day (night: 1)
GLYPH_READ = 0.55                     # a read etching dims to this
GLIMMER_SIZE = 2.6                    # the soft glimmer above a stone at night (metres)
GLIMMER_FADE = (110.0, 260.0)         # it fades out between these camera distances
PLACE_CLEAR = 45.0                    # metres from any place or trail landmark
CLEAR_RADIUS = 6.0                    # nothing else is placed this close to a stone
DESERT_ID = 'etching'

# (distance from the start in metres, the words cut in the stone). Nearest first: the names
# come early, the planet and its fate in the middle, Gleebs far out.
NOTES = (
    (60.0, "A tall walker the colour of dusk is cut here, and beside it a name: NYX. "
           "Under it, smaller: 'the night that keeps you warm'."),
    (170.0, "A tiny figure drawn circling a tall one, round and round, never far. The small ones "
            "called it ORBIT, because it never strays from Nyx."),
    (330.0, "A red giant, cut in a harder hand. Its name is cut deep: CRIMSON. At night it burns, "
            "and its light throws everything away from it."),
    (560.0, "Crimson is stronger than Nyx. But the carver drew it eating everything in its path, bitter "
            "or sweet, and cut a small crooked mark over its head: not wise."),
    (850.0, "This world's name was cut here once. It has been scratched out so hard the stone is scarred. "
            "Over the scars, in a neat, foreign hand: REDACTED."),
    (1250.0, "The sky used to be full of lights that came and went. The carver counted them each night. "
             "The count grows smaller down the stone, and then stops."),
    (1750.0, "Those who left did not want this world found. They took its name from every chart and every "
             "star map, and wrote REDACTED in its place."),
    (2350.0, "First the rivers went, then the green. Now only the blood branches, the pale flower and the "
             "wind. REDACTED is dying, slowly."),
    (3050.0, "Nyx's kind were many once: a long line of tall walkers runs across the stone. At the end of "
             "the line only one is left, and one small thing beside it."),
    (3900.0, "Crimson's kind never learned to wait. The carver drew one eating a pale flower because it "
             "was there, and lying down after, and not getting up."),
    (4900.0, "A figure made of thin bright lines, with long ears, standing in a beam that falls out of "
             "the sky. Under it, one word: GLEEBS."),
    (6100.0, "Gleebs came once, long ago, and took the last small ones away in its light. It left a "
             "promise: it listens, for anyone still here."),
    (7600.0, "When Crimson lies down and does not get up, the sky will answer. Go into the light "
             "together. It will not take one who is alone."),
    (9400.0, "The last etching, cut fast, as if the carver heard something coming: REDACTED is dying. "
             "Do not stay. Do not stay alone."),
)
desert.HOLD_TIMES.setdefault(DESERT_ID, HOLD_TIME)


class Etching:
    __slots__ = ('idx', 'pos', 'heading', 'text', 'read', 'node', 'glyphs', 'glimmer')

    def __init__(self, idx, pos, heading, text):
        self.idx, self.pos, self.heading, self.text = idx, pos, heading, text
        self.read = False
        self.node = self.glimmer = None
        self.glyphs = ()


def _stone_mesh() -> NodePath:
    """A leaning slab of pale stone, a little narrower at the top (flat-shaded)."""
    m = Mesh('etching_stone')
    (wb, wt), d, h = STONE_W, STONE_D, STONE_H
    lo = [Point3(-wb / 2, -d / 2, -0.25), Point3(wb / 2, -d / 2, -0.25),
          Point3(wb / 2, d / 2, -0.25), Point3(-wb / 2, d / 2, -0.25)]
    hi = [Point3(-wt / 2, -d * 0.4, h), Point3(wt / 2, -d * 0.4, h * 0.94),
          Point3(wt / 2, d * 0.4, h * 0.94), Point3(-wt / 2, d * 0.4, h)]
    c = STONE_COLOUR
    dark = Vec4(c.x * 0.86, c.y * 0.86, c.z * 0.86, 1.0)

    def face(pts, colour):
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        n.normalize()
        centre = sum((Vec3(p) for p in pts), Vec3(0, 0, 0)) / len(pts)
        if n.dot(centre) < 0.0:                    # outward from the slab's middle
            n = -n
        ids = [m.vertex(p, n, colour) for p in pts]
        m.quad_facing(*ids)

    for i in range(4):
        j = (i + 1) % 4
        face([lo[i], lo[j], hi[j], hi[i]], c if i % 2 == 0 else dark)
    face(hi, c)
    return m.node()


def _glyph_texture(seed: int) -> Texture:
    """Rows of small angular glyphs, bright on black (drawn additively)."""
    rng = random.Random(seed)
    w, h = 64, 128
    img = PNMImage(w, h, 2)                 # grey + alpha: the marks are in the alpha
    img.fill(1.0)
    img.alphaFill(0.0)

    def line(x0, y0, x1, y1):
        steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for s in range(steps + 1):
            t = s / max(1, steps)
            x, y = int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t))
            for dx, dy in ((0, 0), (1, 0), (0, 1)):
                if 0 <= x + dx < w and 0 <= y + dy < h:
                    img.setAlpha(x + dx, y + dy, 1.0)

    y = 8
    while y < h - 14:
        x = 6
        while x < w - 14:
            cx, cy = x + 5, y + 5
            for _ in range(rng.randint(2, 4)):
                a = rng.choice((0, 45, 90, 135, 180, 225, 270, 315))
                r = rng.choice((3, 5))
                line(cx, cy, cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
            if rng.random() < 0.35:
                line(cx - 4, cy + 6, cx + 4, cy + 6)
            x += 13
        y += 17
    tex = Texture('etching_glyphs')
    tex.load(img)
    tex.setMagfilter(Texture.FTLinear)
    return tex


def _glow_card(parent, tex, w, h, billboard=False, additive=True) -> NodePath:
    cm = CardMaker('etching_glow' if additive else 'etching_cut')
    cm.setFrame(-w / 2, w / 2, -h / 2, h / 2)
    np_ = parent.attachNewNode(cm.generate())
    np_.setTexture(tex)
    if billboard:
        np_.setBillboardPointEye()
    np_.setShaderOff(10)
    np_.setLightOff(10)
    np_.setTransparency(TransparencyAttrib.MAlpha)
    if additive:
        np_.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha,
                                            ColorBlendAttrib.OOne))
    np_.setDepthWrite(False)
    np_.setBin('fixed', 31)
    np_.hide(K['SHADOW_CAMERA_MASK'])
    return np_


class LoreMixin:
    # ------------------------------------------------------------ build
    def _init_lore(self):
        self.etchings = []
        self._etching_root = self.render.attachNewNode('etchings')
        start = self.human_base_pos
        rng = random.Random(f'{self.seed}:etchings')
        base = rng.uniform(0.0, 360.0)
        stone = _stone_mesh()
        textures = [_glyph_texture(self.seed * 7 + k) for k in range(4)]
        from .glow import _aura_texture
        glimmer_tex = _aura_texture()
        for i, (dist, text) in enumerate(NOTES):
            ang = base + i * 137.508 + rng.uniform(-20.0, 20.0)       # the golden angle: all round you
            x, y = self._etching_spot(start, dist, ang, rng)
            e = Etching(i, Point3(x, y, self.field.height(x, y)), rng.uniform(0.0, 360.0), text)
            if hasattr(self.field, 'add_clear_zone'):
                self.field.add_clear_zone(x, y, CLEAR_RADIUS)
            node = self._etching_root.attachNewNode(f'etching_{i}')
            node.setPos(e.pos.x, e.pos.y, e.pos.z)
            node.setH(e.heading)
            node.setR(rng.uniform(-4.0, 4.0))
            stone.instanceTo(node)
            glyphs = []
            for side, tex in ((0, textures[i % len(textures)]), (180, textures[(i + 1) % len(textures)])):
                # cut into both broad faces: the dark cut (seen by day) and the light it holds
                face_y = (-1 if side == 0 else 1) * (STONE_D * 0.45 + 0.02)
                cut = _glow_card(node, tex, 0.46, 0.80, additive=False)
                cut.setH(side)
                cut.setPos(0.0, face_y, STONE_H * 0.50)
                cut.setColor(*CUT_COLOUR)
                glyph = _glow_card(node, tex, 0.46, 0.80)
                glyph.setH(side)
                glyph.setPos(0.0, face_y * 1.08, STONE_H * 0.50)
                glyphs.append(glyph)
            glimmer = _glow_card(self._etching_root, glimmer_tex, GLIMMER_SIZE, GLIMMER_SIZE, billboard=True)
            glimmer.setPos(e.pos.x, e.pos.y, e.pos.z + STONE_H * 0.7)
            glimmer.hide()
            e.node, e.glyphs, e.glimmer = node, tuple(glyphs), glimmer
            self.etchings.append(e)
        self._etching_glow = -1.0
        self._update_etchings(force=True)

    def _etching_spot(self, start: Point3, dist: float, ang: float, rng: random.Random):
        """A clear, fairly level spot near (dist, ang) from the start: not in a shell, a place or water."""
        for attempt in range(40):
            a = math.radians(ang + (attempt * 23.0 if attempt else 0.0))
            d = dist * (1.0 + 0.04 * attempt * (1 if attempt % 2 else -1))
            x, y = start.x + math.sin(a) * d, start.y + math.cos(a) * d
            if not self._etching_spot_ok(x, y):
                continue
            return x, y
        a = math.radians(ang)
        return start.x + math.sin(a) * dist, start.y + math.cos(a) * dist

    def _etching_spot_ok(self, x: float, y: float) -> bool:
        field = self.field
        if hasattr(field, 'is_clear') and not field.is_clear(x, y):
            return False
        h = [field.height(x + dx, y + dy) for dx, dy in ((1.2, 0), (-1.2, 0), (0, 1.2), (0, -1.2))]
        if max(h) - min(h) > 0.9:                                  # not on a steep dune face
            return False
        p = Point3(x, y, 0.0)
        shells = getattr(self, 'shells', None)
        if shells is not None and any(_flat_dist(s.pos, p) < 9.0 for s in shells.shells.values()):
            return False
        # every place and trail landmark, near or not yet built (their layout is pure rules)
        pf = self._places_field() if hasattr(self, '_places_field') else getattr(self, 'places', None)
        if pf is not None:
            layout = pf.layout
            if next(iter(layout.places_within(x, y, PLACE_CLEAR)), None) is not None:
                return False
            d0 = math.hypot(x - layout.start.x, y - layout.start.y)
            if any(math.hypot(x - tx, y - ty) < PLACE_CLEAR for tx, ty in layout._trail_sites(d0)):
                return False
            if pf.in_water(p):
                return False
        return True

    # ------------------------------------------------------------ reading
    def etching_near(self, p: Point3):
        best, best_d = None, READ_RANGE
        for e in getattr(self, 'etchings', ()):
            d = _flat_dist(e.pos, p)
            if d <= best_d:
                best, best_d = e, d
        return best

    def etchings_read(self) -> list:
        return [e for e in getattr(self, 'etchings', ()) if e.read]

    def _e_target(self):
        kind, target = super()._e_target()
        if kind is None and self.controlled_name == 'human' and self.human_alive and not self.carried \
                and self.hidden_shell is None and getattr(self, 'etchings', None):
            e = self.etching_near(self.human.getPos(self.render))
            if e is not None:
                return DESERT_ID, e
        return kind, target

    def place_prompt(self, kind, target) -> str:
        if kind == DESERT_ID:
            return 'read the etching again' if target.read else 'read the etching'
        return super().place_prompt(kind, target)

    def _complete_e(self, kind, target):
        if kind != DESERT_ID:
            return super()._complete_e(kind, target)
        first = not target.read
        target.read = True
        if first:
            self.stats['etchings'] = len(self.etchings_read())
            if 'etchings_told' not in self.stats:
                self.stats['etchings_told'] = 1
        self.sfx('lore_read', Point3(target.pos.x, target.pos.y, target.pos.z + 1.0))
        found = len(self.etchings_read())
        tail = f'\n(etching {found} of {len(self.etchings)}  ·  J > notes)' if first else ''
        self.say(target.text + tail, 9.0 if first else 7.0)
        self._update_etchings(force=True)
        return None

    def notes_lines(self):
        """(heading, texts in the order the etchings stand from the start) for the journal's notes page."""
        read = sorted(self.etchings_read(), key=lambda e: e.idx)
        head = f'etchings read   {len(read)} of {len(getattr(self, "etchings", ()))}'
        return head, [e.text for e in read]

    # ------------------------------------------------------------ per frame
    def survival_step(self, dt: float):
        super().survival_step(dt)
        if getattr(self, 'etchings', None):
            self._update_etchings()

    def _update_etchings(self, force: bool = False):
        night = sky.night_amount(self.hour) if hasattr(self, 'hour') else 0.0
        base = GLYPH_DAY + (1.0 - GLYPH_DAY) * night
        cam = self.camera.getPos(self.render)
        pulse = 0.9 + 0.1 * math.sin(getattr(self, '_fight_clock', 0.0) * 1.3)
        for e in self.etchings:
            d = (e.pos - cam).length()
            if d > 900.0 and not force:
                if not e.node.isHidden():
                    e.node.hide()
                    e.glimmer.hide()
                continue
            if e.node.isHidden():
                e.node.show()
            k = base * (GLYPH_READ if e.read else 1.0) * pulse
            for glyph in e.glyphs:
                glyph.setColor(GLYPH_COLOUR[0], GLYPH_COLOUR[1], GLYPH_COLOUR[2], min(1.0, 0.95 * k))
            fade = 1.0 - min(1.0, max(0.0, (d - GLIMMER_FADE[0]) / (GLIMMER_FADE[1] - GLIMMER_FADE[0])))
            g = 0.30 * night * fade * (0.6 if e.read else 1.0) * pulse
            if g > 0.005:
                e.glimmer.setColor(GLYPH_COLOUR[0], GLYPH_COLOUR[1], GLYPH_COLOUR[2], g)
                e.glimmer.show()
            else:
                e.glimmer.hide()

    # ------------------------------------------------------------ saves
    def lore_snapshot(self) -> list:
        return [e.idx for e in self.etchings_read()]

    def apply_lore(self, read):
        ids = {int(i) for i in (read or []) if isinstance(i, (int, float, str)) and str(i).lstrip('-').isdigit()}
        for e in getattr(self, 'etchings', ()):
            e.read = e.idx in ids
        self._update_etchings(force=True)
