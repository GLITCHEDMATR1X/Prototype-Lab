"""Pass 42 world check: calmer dunes, level ground under structures, no glowing markers,
things spread out for a longer journey.

    python .dev/checks/pass42.py [--shots DIR]
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from panda3d.core import Vec3

import sys as _sys                                  # Pass 62: the game folder is two levels up
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from indigo_giant import app as game
from indigo_giant import desert_geom
from indigo_giant import desert_world
from indigo_giant import flora

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def slope(field, x, y):
    return math.degrees(math.acos(max(-1.0, min(1.0, field.normal(x, y).z))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shots', type=Path)
    args = ap.parse_args()
    glb = Path(__file__).resolve().parents[2] / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=glb)
    a.time_frozen = True          # Pass 43: hold the clock at a steady sun for these checks
    a.heat_factor_override = 1.0
    f = a.field
    sx, sy = game.human_start_xy()

    # ------------------------------------------------------------------ terrain
    xs = np.arange(sx - 700, sx + 700, 4.0)
    hs = np.array([[f.height(x, y) for x in xs] for y in xs[::2]])
    gy, gx = np.gradient(hs, 8.0, 4.0)
    sl = np.degrees(np.arctan(np.hypot(gx, gy)))
    check('dunes are gentle: median slope under 7 deg', np.percentile(sl, 50) < 7.0, f'{np.percentile(sl, 50):.1f}')
    check('95% of ground under 12 deg (giant-walkable)', np.percentile(sl, 95) < 12.0, f'{np.percentile(sl, 95):.1f}')
    check('no cliffs: steepest under 20 deg', sl.max() < 20.0, f'{sl.max():.1f}')
    check('height range is modest (under 16 m)', hs.max() - hs.min() < 16.0, f'{hs.min():.1f}..{hs.max():.1f}')

    # ------------------------------------------------------------------ landmarks on level ground
    worst = 0.0
    far = []
    for lm in a.landmarks.items:
        r = desert_geom.LANDMARK_SHAPES[lm.kind][0]
        for k in range(12):
            for rr in (0.0, r * 0.5, r):
                x = lm.pos.x + math.cos(k * math.pi / 6) * rr
                y = lm.pos.y + math.sin(k * math.pi / 6) * rr
                worst = max(worst, abs(f.height(x, y) - lm.pos.z))
        far.append(math.hypot(lm.pos.x - sx, lm.pos.y - sy))
    check('landmarks stand on levelled ground (height spread under 0.3 m)', worst < 0.3, f'{worst:.2f} m')
    check('landmarks spread out for a journey (farthest > 1 km)', max(far) > 1000 and min(far) > 250,
          f'{min(far):.0f}..{max(far):.0f} m')
    from panda3d.core import InternalName, ShaderAttrib
    attrib = a.landmarks.root.getAttrib(ShaderAttrib)
    # Pass 45: landmarks now share the world fog and keep only a faint ghost beyond it
    ghost = attrib.getShaderInputVector(InternalName.make('fog_floor'))[0]
    check('landmarks sit in the world fog (faint ghost only)', abs(ghost - desert_world.LANDMARK_GHOST) < 1e-6
          and not attrib.hasShaderInput(InternalName.make('fog_density')), f'{ghost:.3f}')
    check('no glowing beacon nodes in the world', a.render.find('**/*beacon*').isEmpty(), a.render.find('**/*beacon*'))

    # ------------------------------------------------------------------ small things on level ground
    for focus in [(sx + dx, sy + dy) for dx in (-500, 0, 500) for dy in (-500, 0, 500)]:
        a.finds.update_active(Vec3(*focus, 0))
        a.shells.update_active(Vec3(*focus, 0))
        a.flora.update_active(Vec3(*focus, 0))
    finds = [x for x in a.finds.finds.values() if x.pid != ('start', 0)]
    shells = [x for x in a.shells.shells.values() if x.pid != ('start', 0)]
    branches = [b for b in a.flora.branches.values() if b.pid != ('start', 0)]
    ws = max(slope(f, s.pos.x, s.pos.y) for s in shells)
    wf = max(slope(f, x.pos.x, x.pos.y) for x in finds)
    wb = max(slope(f, b.pos.x, b.pos.y) for b in branches)
    check('shells rest on level ground', ws <= desert_world.MAX_SLOPE_DEG + 1e-6, f'max {ws:.1f} deg')
    check('finds rest on level ground', wf <= desert_world.MAX_SLOPE_DEG + 1e-6, f'max {wf:.1f} deg')
    check('blood branches root on level ground', wb <= flora.MAX_SLOPE_DEG + 1e-6, f'max {wb:.1f} deg')
    float_worst = 0.0
    for s in shells:
        for k in range(8):
            x = s.pos.x + math.cos(k * math.pi / 4) * desert_geom.SHELL_RX
            y = s.pos.y + math.sin(k * math.pi / 4) * desert_geom.SHELL_RX
            float_worst = max(float_worst, s.pos.z - f.height(x, y))
    check('shell rims never float above the sand', float_worst <= 0.01, f'{float_worst:.3f} m')

    def spacing(items):
        pts = np.array([(i.pos.x, i.pos.y) for i in items])
        d = np.sqrt(((pts[:, None, :] - pts[None, :, :]) ** 2).sum(-1))
        np.fill_diagonal(d, 1e9)
        return float(np.median(d.min(1)))
    area_km2 = (1400 * 1400) / 1e6
    check('finds are spread out', spacing(finds) > 60.0, f'{len(finds)} in ~{area_km2:.1f} km2, median gap {spacing(finds):.0f} m')
    check('shells are spread out (but a walk apart)', 60.0 < spacing(shells) < 220.0,
          f'{len(shells)} shells, median gap {spacing(shells):.0f} m')
    check('blood branches are spread out', spacing(branches) > 40.0, f'{len(branches)} branches, median gap {spacing(branches):.0f} m')

    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)
        lm = min(a.landmarks.items, key=lambda o: math.hypot(o.pos.x - sx, o.pos.y - sy))
        hp = a.human.getPos()
        d = Vec3(lm.pos.x - hp.x, lm.pos.y - hp.y, 0)
        d.normalize()
        hp = hp + d * 30.0
        a.human.setPos(hp.x, hp.y, f.height(hp.x, hp.y))
        a.drain_stream_queue()
        a.heading = math.degrees(math.atan2(lm.pos.x - hp.x, lm.pos.y - hp.y))
        a._snap_camera_to_controlled(immediate=True)
        a.settle_visibility(3.0)
        for _ in range(3):
            a.graphicsEngine.renderFrame()
        a.win.saveScreenshot(str(args.shots / 'p42_horizon.png'))
        a.heading += 120
        a._snap_camera_to_controlled(immediate=True)
        a.distance = 30
        a.pitch = -16
        a._place_camera(immediate=True)
        for _ in range(3):
            a.graphicsEngine.renderFrame()
        a.win.saveScreenshot(str(args.shots / 'p42_dunes.png'))
        near = lm.pos + Vec3(70, -40, 0)
        a.human.setPos(near.x, near.y, f.height(near.x, near.y))
        a.heading = math.degrees(math.atan2(lm.pos.x - near.x, lm.pos.y - near.y))
        a._snap_camera_to_controlled(immediate=True)
        a.pitch = -6
        a._place_camera(immediate=True)
        a.drain_stream_queue()
        for _ in range(3):
            a.graphicsEngine.renderFrame()
        a.win.saveScreenshot(str(args.shots / 'p42_landmark_near.png'))

    a.destroy()
    print('RESULT', 'FAIL' if FAILS else 'PASS', FAILS)
    sys.exit(1 if FAILS else 0)


if __name__ == '__main__':
    main()
