"""Pass 46 check: the wide world - hidden places everywhere, no edge, no unfinished ground.

    python tools_pass46_check.py
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

from panda3d.core import Point3, Vec3

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='indigo_save46_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import desert_world   # noqa: E402
import main as game   # noqa: E402
import places         # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
CLOCK = [0.0]


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


def park_red(a):
    p = a.human.getPos() + Vec3(3000, 0, 0)
    a.red_giant.setPos(ground(a, p.x, p.y))
    a.red_state = 'idle'


def go(a, x, y):
    """Teleport the human (and Indigo beside them) and let the world catch up."""
    a.human.setPos(ground(a, x, y))
    a.giant.setPos(ground(a, x + 25, y - 20))
    park_red(a)
    a.cam_target = a._controlled_focus()
    a._refresh_world(force=True)
    a._update_stream(force=True)
    a.drain_stream_queue()
    a._refresh_world(force=True)


def frames(a, seconds, dt=1 / 30.0):
    for _ in range(int(seconds / dt)):
        CLOCK[0] += dt
        a.survival_step(dt)


def main():
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, new_game=True, persist=True, save_dir=TMP)
    a.time_frozen = True
    a.heat_factor_override = 0.0
    pf = a.places
    start = Point3(a.human_base_pos)

    # ------------------------------------------------------------ places everywhere, always the same
    for R in range(0, 6001, 750):
        for ang in range(0, 360, 30):
            pf.update(Point3(start.x + R * math.cos(math.radians(ang)), start.y + R * math.sin(math.radians(ang)), 0))
    kinds = {p.kind for p in pf.places.values()}
    # Pass 51: the rare kinds start 3.4 km out and the legends are 8-18 km out (tools_pass51_check.py)
    near_kinds = set(places.TIERS['common'][0]) | set(places.TIERS['uncommon'][0])
    check('every common and uncommon kind of place exists within 6 km (and some rare ones)',
          near_kinds <= kinds and kinds & set(places.TIERS['rare'][0]), f'{len(pf.places)} places, {len(kinds)} kinds')
    other = places.PlaceField(a.render, game.TerrainField(a.seed), a.seed, start, game.SHADOW_CAMERA_MASK)
    for pid in list(pf.places)[:40]:
        other.update(Point3((pid[0] + 0.5) * places.PLACE_CELL, (pid[1] + 0.5) * places.PLACE_CELL, 0))
    same = all(other.places.get(pid) is not None and other.places[pid].kind == pf.places[pid].kind
               and abs(other.places[pid].pos.x - pf.places[pid].pos.x) < 1e-6 for pid in list(pf.places)[:40])
    check('the same seed always puts the same place in the same spot', same)
    other.root.removeNode()
    trail = [(lm.pos.x, lm.pos.y) for lm in a.landmarks.items] + [
        (x, y) for c in range(2, 7) for _i, x, y, _k, _h in desert_world.chapter_sites(
            a.seed, start.x, start.y, c, 8 + 5 * (c - 2))]
    near_trail = min(math.hypot(p.pos.x - x, p.pos.y - y) for p in pf.places.values() for x, y in trail)
    near_start = min(math.hypot(p.pos.x - start.x, p.pos.y - start.y) for p in pf.places.values())
    check('places keep clear of the trail landmarks and the start', near_trail >= places.TRAIL_CLEAR and
          near_start >= places.START_CLEAR, f'{near_trail:.0f} m from the trail, {near_start:.0f} m from the start')
    worst = 0.0
    for p in list(pf.places.values())[:60]:
        hs = [a.field.height(p.pos.x + math.cos(k) * p.radius, p.pos.y + math.sin(k) * p.radius) for k in range(8)]
        worst = max(worst, max(hs + [a.field.height(p.pos.x, p.pos.y)]) - min(hs + [a.field.height(p.pos.x, p.pos.y)]))
    check('every place stands on levelled ground', worst < 0.3, f'worst {worst:.2f} m')

    # ------------------------------------------------------------ discovery, search, water, rest, shade
    def closest(kind):
        return min((p for p in pf.places.values() if p.kind == kind),
                   key=lambda p: math.hypot(p.pos.x - start.x, p.pos.y - start.y))

    skull = closest('skull')
    go(a, skull.pos.x + skull.radius + 60, skull.pos.y)
    a._snd  # audio is up
    found_before = skull.found
    go(a, skull.pos.x + skull.radius + 10, skull.pos.y)
    check('walking up to a place finds it, names it and writes it in the journal',
          not found_before and skull.found and a.stats['places'] >= 1 and skull.name.split()[-1] in a.lore_log[-1],
          skull.name)
    clutter = [f for f in a.finds.finds.values() if math.hypot(f.pos.x - skull.pos.x, f.pos.y - skull.pos.y) < skull.radius + 6] \
        + [s for s in a.shells.shells.values() if math.hypot(s.pos.x - skull.pos.x, s.pos.y - skull.pos.y) < skull.radius + 6] \
        + [b for b in a.flora.branches.values() if math.hypot(b.pos.x - skull.pos.x, b.pos.y - skull.pos.y) < skull.radius + 6]
    check('nothing else spawns inside a place', not clutter, f'{len(clutter)} things inside')
    a.bag('human').clear()
    a.human.setPos(ground(a, skull.pos.x + skull.radius + 1.0, skull.pos.y))   # step up to it
    kind, target = a._e_target()
    ok_kind = kind == 'search' and target is skull
    a._complete_e(kind, target)
    got = sum(a.bag('human').values()) + sum(a.bag('giant').values())
    kind2, _ = a._e_target()
    check('a hidden cache can be searched once', ok_kind and got > 0 and kind2 != 'search', f'{got} items')
    off = a._sun_offset()
    sx, sy = skull.pos.x + off.x * places.KINDS['skull'][3] * 0.45, skull.pos.y + off.y * places.KINDS['skull'][3] * 0.45
    a.human.setPos(ground(a, sx, sy))
    a._refresh_world(force=True)
    check('a place casts real shade', a.point_in_shade(Point3(sx, sy, 0)))

    oasis = closest('oasis')
    go(a, oasis.pos.x + 3.0, oasis.pos.y)
    a.heat = 80.0
    frames(a, 2.0)
    waded = a.heat
    kind, target = a._e_target()
    if kind == 'drink':
        a._complete_e(kind, target)
    check('wading in an oasis cools you, drinking cools you completely',
          waded < 80.0 - places.WADE_COOLING * 1.5 and kind == 'drink' and a.heat == 0.0, f'80 -> {waded:.0f} -> {a.heat:.0f}')
    ring = closest('ring')
    go(a, ring.pos.x + 2.0, ring.pos.y + 1.0)
    a.stamina = 5.0
    kind, target = a._e_target()
    if kind == 'rest':
        a._complete_e(kind, target)
    check('resting in the stone ring restores stamina', kind == 'rest' and a.stamina == 100.0)

    # Indigo notices an unfound place before you do
    statue = closest('statue')
    d = places.SENSE_RADIUS - 30.0
    go(a, statue.pos.x + d, statue.pos.y)
    check('Indigo turns toward a place you have not found yet', statue.sensed and not statue.found)

    # ------------------------------------------------------------ save / load
    a.save_game('check')
    found = {repr(p.pid) for p in pf.places.values() if p.found}
    a.destroy()
    b = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, persist=True, save_dir=TMP)
    b.time_frozen = True
    go(b, skull.pos.x + skull.radius + 60, skull.pos.y)
    bs = b.places.places.get(skull.pid)
    check('places found and caches searched are saved', bs is not None and bs.found and bs.searched and
          b.places.found_count() == len(found), f'{b.places.found_count()} found')
    b.persist = False

    # ------------------------------------------------------------ no edge, no unfinished ground
    chunk = next(iter(b.loaded.values()))
    rows = chunk.node().getGeom(0).getVertexData().getNumRows()
    verts = game.CHUNK_CELLS + 1
    check('every chunk hangs a skirt (no crack can show the sky)', rows == verts * verts + 4 * game.CHUNK_CELLS, rows)
    b.controlled_name = 'giant'
    b.cam_target = b._controlled_focus()
    b._update_stream(force=True)
    b.drain_stream_queue()
    check('the fog is total before the ground ends',
          b._fog_end() <= b.ground_radius() + 1e-6 and b.ground_radius() >= game.GIANT_FAR_RADIUS * game.CHUNK_SIZE,
          f'fog end {b._fog_end():.0f} m, ground {b.ground_radius():.0f} m')
    # ride at a gallop for 30 s with the per-frame building budget: the ground never runs out
    import time as _t
    worst_ground = 1e9
    dt = 1 / 60.0
    for i in range(int(30 / dt)):
        b.cam_target = b.cam_target + Vec3(22.0 * dt, 9.0 * dt, 0)
        b._update_stream()
        t0 = _t.perf_counter()
        while b.pending_loads and (_t.perf_counter() - t0) * 1000.0 < game.STREAM_BUDGET_MS:
            if not b.service_stream_queue(1):
                break
        b._update_visibility(dt)
        worst_ground = min(worst_ground, b.ground_radius())
    check('riding fast, built ground always reaches past the fog line near you',
          worst_ground >= 3 * game.CHUNK_SIZE, f'worst {worst_ground:.0f} m of ground ahead')
    b.controlled_name = 'human'

    # far, far away: 40 km out there is still desert, places and ground
    far = Point3(start.x + 40000.0, start.y - 35000.0, 0)
    go(b, far.x, far.y)
    h = b.field.height(far.x, far.y)
    near_places = [p for p in b.places.places.values() if math.hypot(p.pos.x - far.x, p.pos.y - far.y) < places.PREPARE_RADIUS]
    check('53 km from the start the world goes on: ground, content and places',
          math.isfinite(h) and b.ground_radius() >= game.HUMAN_LOAD_RADIUS * game.CHUNK_SIZE and len(near_places) >= 1
          and len(b.shells.shells) > 0,
          f'{len(near_places)} places within reach, {len(b.loaded)} chunks')
    for _ in range(3):
        b.graphicsEngine.renderFrame()
    check('it renders out there without errors', True)

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
