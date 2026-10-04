"""Pass 56 check: a natural shell mouth.

The mouth is a smooth arch with splayed feet, the shell has a real wall (outer ribbed surface,
pearly inside, rounded lip) with no open or paper-thin edges, broken holes follow their jagged
outline, and walking in and out follows the arch and the roof.

    python .dev/checks/pass56.py
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

from panda3d.core import CullFaceAttrib, GeomVertexReader, Point3, Vec3

HERE = Path(__file__).resolve().parents[2]          # Pass 62: the game folder
TMP = Path(tempfile.mkdtemp(prefix='indigo_save56_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import sys as _sys                                  # Pass 62: the game folder is two levels up
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from indigo_giant import desert_geom as geom    # noqa: E402
from indigo_giant import desert_world as world  # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
DT = 1 / 30.0


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def mesh_of(np_):
    """(positions, normals, triangles) of a built shell."""
    geom_ = np_.node().getGeom(0)
    vd = geom_.getVertexData()
    rv, rn = GeomVertexReader(vd, 'vertex'), GeomVertexReader(vd, 'normal')
    pts, nrm = [], []
    while not rv.isAtEnd():
        pts.append(Vec3(rv.getData3()))
        nrm.append(Vec3(rn.getData3()))
    tris = []
    for p in range(geom_.getNumPrimitives()):
        prim = geom_.getPrimitive(p).decompose()
        for t in range(prim.getNumPrimitives()):
            s = prim.getPrimitiveStart(t)
            tris.append((prim.getVertex(s), prim.getVertex(s + 1), prim.getVertex(s + 2)))
    return pts, nrm, tris


def open_edges(pts, tris):
    """Edges used by only one triangle, matched by position (the mesh repeats vertices at seams)."""
    def key(i):
        p = pts[i]
        return (round(p.x, 3), round(p.y, 3), round(p.z, 3))
    count = Counter()
    for a, b, c in tris:
        ka, kb, kc = key(a), key(b), key(c)
        if len({ka, kb, kc}) < 3:
            continue
        for e in ((ka, kb), (kb, kc), (kc, ka)):
            count[tuple(sorted(e))] += 1
    return [e for e, n in count.items() if n == 1]


def mouth_side(e):
    """Is an edge on the front (mouth) side of the shell, above the sand?"""
    (x0, y0, z0), (x1, y1, z1) = e
    ang = math.degrees(math.atan2(0.5 * (y0 + y1), 0.5 * (x0 + x1)))
    return abs(ang - 90.0) < geom.MOUTH_HALF_BASE + 12.0 and max(z0, z1) > 0.05


def main():
    # 1. the arch: rounded, tall enough, splayed feet, smooth
    hs = [geom.mouth_height(a * 0.25) for a in range(int(geom.MOUTH_HALF_BASE * 4) + 2)]
    falling = all(hs[i + 1] <= hs[i] + 1e-6 for i in range(len(hs) - 1))
    walk = geom.mouth_walkable_deg()
    chord = 2.0 * geom.SHELL_RY * math.sin(math.radians(walk))
    base = 2.0 * geom.SHELL_RY * math.sin(math.radians(geom.MOUTH_HALF_BASE))
    check('the mouth is a rounded arch: highest in the middle, falling smoothly to the sand',
          falling and abs(hs[0] - geom.MOUTH_TOP) < 1e-3 and hs[-1] == 0.0, f'{geom.MOUTH_TOP} m high')
    check('it is a doorway: you walk through upright (head clear), ~3 m across at the sand',
          geom.MOUTH_TOP >= geom.MOUTH_CLEAR + 0.2 and chord >= 1.2 and 2.5 <= base <= 3.5,
          f'walk-through {chord:.2f} m, at the sand {base:.2f} m')
    foot = geom.mouth_half_width(0.0) - geom.mouth_half_width(geom.MOUTH_FOOT_H)
    core = geom.MOUTH_CORE_DEG * (1.0 - (geom.MOUTH_FOOT_H / geom.MOUTH_TOP) ** geom.MOUTH_SHAPE) ** (1.0 / geom.MOUTH_SHAPE)
    check('its feet splay out where they meet the sand (not a straight cut down)',
          foot > (geom.MOUTH_CORE_DEG - core) + 3.0, f'{foot:.1f} deg wider over the lowest {geom.MOUTH_FOOT_H} m')

    # 2. the mesh: a real wall all round the mouth, faces the right way, a sane size
    intact, cracked = geom.build_shell(False, 7), geom.build_shell(True, 8)
    for name, np_ in (('intact', intact), ('cracked', cracked)):
        pts, nrm, tris = mesh_of(np_)
        bare = mesh_of(geom.build_shell(name == 'cracked', 7 if name == 'intact' else 8, barnacles=False))
        edges = open_edges(bare[0], bare[2])
        at_mouth = [e for e in edges if mouth_side(e)]
        check(f'{name}: the shell is closed - no open or paper-thin edge anywhere (a lip joins the outer '
              'and inner walls round the rim and the mouth; broken holes have walls)', not edges,
              f'{len(edges)} open edges, {len(at_mouth)} of them at the mouth')
        wrong = 0
        for a, b, c in tris:
            face = (pts[b] - pts[a]).cross(pts[c] - pts[a])
            if face.dot(nrm[a] + nrm[b] + nrm[c]) < 0.0:
                wrong += 1
        check(f'{name}: every face is wound to face out (can render one-sided)', wrong == 0, f'{wrong} of {len(tris)}')
        check(f'{name}: a sensible size to draw', len(tris) < 16000, f'{len(tris)} triangles, {len(pts)} vertices')
        check(f'{name}: drawn one-sided (the wall has two faces now)', not np_.hasAttrib(CullFaceAttrib))

    # 3. the edge of the arch is smooth (no steps where mesh rows used to be cut)
    pts, nrm, tris = mesh_of(intact)
    cols = geom._shell_columns()
    arch = [(th, geom.mouth_height(th - 90.0)) for th in cols if 0.0 < geom.mouth_height(th - 90.0)]
    pos = []
    for th, h in arch:
        phi = math.acos(min(0.97, h / geom.SHELL_H))
        t = math.radians(th)
        pos.append(Vec3(geom.SHELL_RX * math.sin(phi) * math.cos(t), geom.SHELL_RY * math.sin(phi) * math.sin(t), h))
    steps = [(pos[i + 1] - pos[i]).length() for i in range(len(pos) - 1)]
    turns = []
    for i in range(1, len(pos) - 1):
        u, v = pos[i] - pos[i - 1], pos[i + 1] - pos[i]
        if u.length() > 1e-6 and v.length() > 1e-6:
            u.normalize()
            v.normalize()
            turns.append(math.degrees(math.acos(max(-1.0, min(1.0, u.dot(v))))))
    check('the arch edge is a smooth curve: short segments, no sharp kinks',
          max(steps) < 0.35 and max(turns) < 30.0, f'{len(pos)} points, longest {max(steps):.2f} m, sharpest turn {max(turns):.0f} deg')

    # 4. walking: through the arch where it clears your head, not through its sides; inside,
    #    only where the roof clears your head
    from indigo_giant import app as game
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, new_game=True, persist=True, save_dir=TMP,
                                       show_title=False)
    a.time_frozen = True
    a.heat_factor_override = 0.0
    a.comp.update({'mode': 'stay', 'moving': False})
    b = a.human_base_pos
    a.giant.setPos(Point3(b.x + 150, b.y + 80, a.field.height(b.x + 150, b.y + 80)))
    a.red_giant.setPos(Point3(b.x + 700, b.y, a.field.height(b.x + 700, b.y)))
    s = a.shells.shells[('start', 0)]
    a.shells.set_state(s, 'intact')
    a._refresh_world(force=True)
    sf = a.shells

    def world_of(ang_deg, radius_q):
        t = math.radians(ang_deg)
        lx, ly = geom.SHELL_RX * radius_q * math.cos(t), geom.SHELL_RY * radius_q * math.sin(t)
        h = math.radians(s.heading)
        return Point3(s.pos.x + lx * math.cos(h) - ly * math.sin(h), s.pos.y + lx * math.sin(h) + ly * math.cos(h), 0)

    def walk_in_at(ang):
        """Walk radially inward from outside at this angle round the shell; the q you end at."""
        start = world_of(ang, 1.6)
        a.human.setPos(start.x, start.y, a.field.height(start.x, start.y))
        goal = world_of(ang, 0.1)
        t = 0.0
        while t < 6.0:
            hp = a.human.getPos(a.render)
            d = Vec3(goal.x - hp.x, goal.y - hp.y, 0)
            if d.length() < 0.2:
                break
            a._apply_controlled_move(d, DT, t, gait='walk')
            t += DT
        a._apply_controlled_move(Vec3(0, 0, 0), DT, t)
        return sf._q(*sf._local(s, a.human.getPos(a.render)))

    through = walk_in_at(90.0 + geom.mouth_walkable_deg() * 0.8)
    # Pass 57: near the opening the doorframe guides you in (a funnel); well off to the side it stops you
    jamb = walk_in_at(90.0 + geom.mouth_walkable_deg() + world.FUNNEL_DEG + 5.0)
    check('you walk in through the arch, but not through its low sides (the jambs)',
          through < 0.3 and jamb >= 1.0, f'in the arch you reach q {through:.2f}; at the jamb you stop at q {jamb:.2f}')
    for _ in range(3):
        a._update_shell_presence()
    for ang in (0.0, 45.0, 135.0, 180.0, 270.0):
        goal = world_of(ang, 1.3)
        t = 0.0
        a.human.setPos(sf.inner_spot(s))
        while t < 5.0:
            hp = a.human.getPos(a.render)
            a._apply_controlled_move(Vec3(goal.x - hp.x, goal.y - hp.y, 0), DT, t, gait='walk')
            t += DT
    q = sf._q(*sf._local(s, a.human.getPos(a.render)))
    roof = geom.SHELL_H * math.sqrt(max(0.0, 1.0 - q * q)) - geom.SHELL_THICK
    check('inside, you walk only where the roof is above your head (not into the low rim)',
          roof >= a.human_height + 0.05, f'as far as q {q:.2f}: roof {roof:.2f} m, you {a.human_height:.2f} m')
    check('the standing room inside is ~5 m across', 2.0 * geom.SHELL_RX * world.ROOM_Q >= 4.5,
          f'{2 * geom.SHELL_RX * world.ROOM_Q:.1f} x {2 * geom.SHELL_RY * world.ROOM_Q:.1f} m')

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
