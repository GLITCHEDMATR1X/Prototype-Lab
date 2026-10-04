"""Pass 37/38 performance probe for The Indigo Giant.

Runs the real game tasks in an offscreen window for a scripted route (human walk,
human sprint, giant jog) and reports how long the Python game logic takes per frame,
separately from GPU rendering.

    python .dev/tools/perf_probe.py

Pass 36 measured ~180 ms of logic per frame here (the hidden proxy shadows re-solved
the whole skeleton ~90 times per refresh); Pass 37 measures ~3 ms.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # Pass 62: the game folder
sys.path.insert(0, str(ROOT))
sys.argv = [sys.argv[0]]

import sys as _sys                                  # Pass 62: the game folder is two levels up
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from indigo_giant import app as game  # noqa: E402
from panda3d.core import ClockObject  # noqa: E402


def main() -> int:
    started = time.perf_counter()
    world = game.StreamingTerrainWithGiant(
        offscreen=True, giant_glb=ROOT / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb')
    print(f"startup: {time.perf_counter() - started:.1f} s")
    tm = world.taskMgr
    for name, fn, sort in (('m', world._movement_task, 5), ('d', world._indigo_defender_task, 6),
                           ('r', world._red_giant_task, 7), ('sv', world._survival_task, 8),
                           ('c', world._camera_task, 9),
                           ('s', world._stream_task, 10), ('v', world._visibility_task, 11),
                           ('sh', world._shadow_task, 12)):
        tm.add(fn, name, sort=sort)
    clock = ClockObject.getGlobalClock()
    clock.setMode(ClockObject.MNonRealTime)
    clock.setFrameRate(60)
    # Render separately so game logic and GPU/driver time are measured apart.
    tm.remove('igLoop')

    def run(label: str, frames: int, **keys) -> None:
        for k in world.keys:
            world.keys[k] = bool(keys.get(k, False))
        logic = []
        for _ in range(frames):
            t = time.perf_counter()
            tm.step()
            logic.append(time.perf_counter() - t)
            world.graphicsEngine.renderFrame()
        logic.sort()
        print(f"{label:18s} logic/frame  p50 {logic[len(logic)//2]*1000:5.2f} ms   p95 {logic[int(len(logic)*0.95)]*1000:5.2f} ms"
              f"   max {logic[-1]*1000:6.2f} ms")

    run('human walk', 240, w=True)
    run('human sprint', 240, w=True, shift=True, control=True)
    world._toggle_control()
    run('giant jog', 360, w=True, shift=True)
    world.destroy()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
