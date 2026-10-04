"""Pass 45 check: smooth GPU-skinned characters, fog that blankets the world, messages
below the player.

    python .dev/checks/pass45.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np
from panda3d.core import (Geom, GeomNode, GeomVertexData, GeomVertexFormat, InternalName, PNMImage, Point3,
                          ShaderAttrib, Vec3)

HERE = Path(__file__).resolve().parents[2]          # Pass 62: the game folder
os.environ['INDIGO_SAVE_DIR'] = tempfile.mkdtemp(prefix='indigo_save45_')
sys.argv = sys.argv[:1]

import sys as _sys                                  # Pass 62: the game folder is two levels up
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from indigo_giant import desert_world   # noqa: E402
from indigo_giant import hud            # noqa: E402
from indigo_giant import app as game   # noqa: E402
from indigo_giant import sky            # noqa: E402
from indigo_giant import skinned_actor as sa   # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def grab(a):
    for _ in range(3):
        a.graphicsEngine.renderFrame()
    im = PNMImage()
    a.win.getScreenshot(im)
    return np.array([[im.getXel(x, y) for x in range(0, im.getXSize(), 3)] for y in range(0, im.getYSize(), 3)])


def cpu_pose_node(actor, clip, t):
    """Reference: the old CPU skinning of the same pose, as a static mesh."""
    skin = actor.clips[clip]['skin']
    posed, _ = skin.pose_with_points(t % skin.duration)
    node = actor.root.attachNewNode('cpu_reference')
    floor = skin.source_floor_y
    for i, (pr, (p, n)) in enumerate(zip(skin.primitives, posed)):
        blk = np.empty(len(p), dtype=game._FRAME_VERTEX_DTYPE)
        blk['p'][:, 0], blk['p'][:, 1], blk['p'][:, 2] = -p[:, 0], p[:, 2], p[:, 1] - floor
        blk['n'][:, 0], blk['n'][:, 1], blk['n'][:, 2] = -n[:, 0], n[:, 2], n[:, 1]
        blk['c'] = sa._color_bytes(actor.palette[i % len(actor.palette)])
        vd = GeomVertexData('ref', GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
        vd.setNumRows(len(p))
        memoryview(vd.modifyArray(0)).cast('B')[:] = blk.tobytes()
        geom = Geom(vd)
        geom.addPrimitive(sa._triangles(skin, i, pr))
        gn = GeomNode('ref')
        gn.addGeom(geom)
        node.attachNewNode(gn)
    return node


def main():
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, new_game=True, persist=False)
    a.time_frozen = True
    a.red_giant.setPos(a.red_giant.getPos() + Vec3(600, 0, 0))

    # ------------------------------------------------------------ smooth animation
    for name, actor in (('Indigo', a.giant_actor), ('Red Giant', a.red_giant_actor), ('human', a.human_actor)):
        rates = [c['count'] / c['duration'] for c in actor.clips.values()]
        parts = actor.mesh.findAllMatches('**/+GeomNode')
        check(f'{name}: one skinned mesh, every clip sampled at {sa.SKIN_SAMPLE_HZ:.0f} Hz and blended',
              parts.getNumPaths() == 2 and min(rates) >= sa.SKIN_SAMPLE_HZ * 0.9,
              f'{len(actor.clips)} clips, lowest {min(rates):.1f} samples/s (the flip-book was 6-12)')
    g = a.giant_actor
    pose = []
    for i in range(4):                      # four consecutive 60 fps frames of a walk
        g.apply_clip('Walk_Loop', 0.30 + i / 60.0)
        pose.append(np.frombuffer(memoryview(g.joint_mats), dtype=np.float32).copy())
    steps = [float(np.abs(pose[i + 1] - pose[i]).max()) for i in range(3)]
    check('the pose changes on every 60 fps frame (no held flip-book frames)', min(steps) > 1e-5,
          ' '.join(f'{s:.4f}' for s in steps))

    # the GPU pose matches the CPU reference skinning, pixel for pixel
    a.human.hide()
    g.apply_clip('Walk_Loop', 0.37, force=True)
    gp = a.giant.getPos(a.render)
    a.camera.setPos(gp + Vec3(40, -60, 25))
    a.camera.lookAt(gp + Vec3(0, 0, a.giant_height * 0.5))
    a._sync_sun_shader()
    gpu = grab(a)
    ref = cpu_pose_node(g, 'Walk_Loop', 0.37)
    g.mesh.hide()
    cpu = grab(a)
    ref.removeNode()
    g.mesh.show()
    a.human.show()
    diff = float((np.abs(gpu - cpu).max(axis=2) > 0.1).mean())
    check('GPU skinning draws exactly the pose the CPU skinning did', diff < 0.003, f'{diff:.4%} of pixels differ')

    # ------------------------------------------------------------ fog blankets the world
    lm_attr = a.landmarks.root.getAttrib(ShaderAttrib)
    check('landmarks share the world fog (no thin private haze), only a faint ghost beyond it',
          not lm_attr.hasShaderInput(InternalName.make('fog_density'))
          and abs(lm_attr.getShaderInputVector(InternalName.make('fog_floor'))[0] - desert_world.LANDMARK_GHOST) < 1e-6)
    a.hour = 17.6
    a._apply_time(force=True)
    fz = a.render.getAttrib(ShaderAttrib).getShaderInputVector(InternalName.make('fog_zenith'))
    z = sky.zenith_at(a.hour)
    check('fog above the horizon takes the sky colour behind it (objects melt into the sky)',
          all(abs(fz[i] - z[i]) < 1e-4 for i in range(3)))
    a.pitch = 0.0
    a.cam_target = a._controlled_focus()
    a._place_camera(immediate=True)
    up = a.render.getAttrib(ShaderAttrib).getShaderInputVector(InternalName.make('view_up'))
    check('world "up" reaches the shader in view space', up[1] > 0.95, f'{up[0]:.2f} {up[1]:.2f} {up[2]:.2f}')

    # ------------------------------------------------------------ messages below the player
    a.hour = 10.0
    a._apply_time(force=True)
    a.pitch = game.HUMAN_CAMERA_PITCH
    a.cam_target = a._controlled_focus()
    a._place_camera(immediate=True)
    a.say('Indigo turns ahead - 3 things out there', 5.0)
    one = a.lore_text.getPos()[1]
    a.say('Ribs of something that once walked here. It lay down facing the same way you are.\n'
          'Indigo gazes north-east: there is more out there.', 5.0)
    two = a.lore_text.getPos()[1]
    feet = a.human.getPos(a.render)
    p3 = a.cam.getRelativePoint(a.render, feet)
    p2 = Point3()
    a.camLens.project(p3, p2)
    lines = a.lore_text.textNode.getNumRows()
    top = two + a.lore_text.textNode.getLineHeight() * hud.LORE_SCALE     # top of the first line
    check('a message sits at the bottom of the screen', one <= -0.8 and a.hud_prompt.getPos()[1] < one,
          f'message {one:.2f}, prompt {a.hud_prompt.getPos()[1]:.2f}')
    check('a two-line message grows upward and stays below the player\'s feet', lines == 2 and top < p2.y,
          f'top {top:.2f}, feet {p2.y:.2f}')
    check('the collapse text is above the player, not over them', a.hud_down.getPos()[1] > 0.3)

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
