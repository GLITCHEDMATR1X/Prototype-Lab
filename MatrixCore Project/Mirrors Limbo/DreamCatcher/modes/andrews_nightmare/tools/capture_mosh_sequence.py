from __future__ import annotations
import argparse
from pathlib import Path
from types import SimpleNamespace

from panda3d.core import Filename, Point3, Vec2, loadPrcFileData

parser = argparse.ArgumentParser(description='Capture deterministic temporal datamosh sequence')
parser.add_argument('--windowed', action='store_true', help='use a real Panda window instead of offscreen')
parser.add_argument('--tag', default='', help='optional output subfolder suffix')
opts = parser.parse_args()

if opts.windowed:
    loadPrcFileData('qa', 'win-size 1280 720\naudio-library-name null\nsync-video false')
else:
    loadPrcFileData('qa', 'window-type offscreen\nwin-size 1280 720\naudio-library-name null')

import sys
_GAME_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_GAME_ROOT))
sys.path.append(str(_GAME_ROOT.parents[2]))  # Mirror's Limbo root: shared gx_common package
from game.app import AndrewsNightmareApp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
name = 'mosh_sequence' + (f'_{opts.tag}' if opts.tag else '')
OUT = ROOT / 'verification' / name
OUT.mkdir(parents=True, exist_ok=True)
args = SimpleNamespace(
    windowed=opts.windowed, offscreen=not opts.windowed, smoke_test=False, self_test=False,
    qa_shot=None, qa_scene='spawn', dream_seed=17, no_audio=True,
)
app = AndrewsNightmareApp(args, ROOT)
app.player.manual_mode = True
app.dreamer.manual_mode = True
app.ui.crosshair.hide()
app.player.teleport(Point3(0.0, 7.1, 0.0), 0.0)
app.player.pitch = -1.0
app.camera.setP(-1.0)
app.dreamer.set_position(0.0, 10.0, 180.0)

# Prime the true temporal buffers with old-scene frames and establish a meaningful
# pre-contact motion vector. The teleport delta itself is intentionally not used.
app.vision._recent_motion = Vec2(-0.0095, 0.0018)
app.vision._recent_zoom = 0.0013
for i in range(10):
    app.vision._activate_feedback_target(2.0 + i / 60.0)
    app.graphicsEngine.renderFrame()

def relocate():
    app.player.teleport(Point3(7.1, 6.0, 0.0), 90.0)
    app.dreamer.set_position(-8.0, 11.0, 180.0)
    app.world.advance_dream_cycle()
    app._apply_cycle_environment()

def done():
    pass

app.vision.trigger_datamosh(relocate, done)
shots = {0, 12, 28, 38, 48, 66, 88, 110}
for frame in range(111):
    app.vision._update_event(1.0 / 60.0)
    app.vision._activate_feedback_target(3.0 + frame / 60.0)
    app.graphicsEngine.renderFrame()
    if frame in shots:
        path = OUT / f'frame_{frame:03d}.png'
        app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
        print(path.name, 'event', round(app.vision.event, 3), 'teleported', app.vision.teleported)

app.userExit()
