"""Pass 45 — smooth character animation (GPU skinning).

Before Pass 45 every animation was a flip-book: each clip was baked into whole copies of the
mesh at 6-12 poses per second (the Red Giant at 6), and the game swapped between them. That
is why the giants moved in visible steps.

Now each character is ONE mesh in its bind pose with 4 joint indices + 4 weights per vertex.
The 65 joint matrices of every clip are sampled once at load (SKIN_SAMPLE_HZ, shared by all
actors that use the clip) and, every frame, the two samples around the exact clip time are
blended and sent to the vertex shader (shaders/skin.vert), which skins the mesh. Motion is
as smooth as the frame rate, at any speed, for every clip.

Also: loading is faster (no CPU deformation of 8.5k vertices per pose) and uses far less
memory (a clip is a few hundred KB of matrices instead of dozens of mesh copies).

The public surface is unchanged from the flip-book actor: apply_clip, clips, current_clip,
last_clip_time, joint_world_point, joint_local_points, foot_world_point, height_world, root.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from panda3d.core import (Filename, Geom, GeomNode, GeomTriangles, GeomVertexArrayFormat,
                          GeomVertexData, GeomVertexFormat, InternalName, OmniBoundingVolume, Point3,
                          PTA_LMatrix4f, Shader, Vec4)

from gltf_idle import GLBIdleSkin

SKIN_SAMPLE_HZ = 30.0          # joint samples per second of animation (blended between)
_CLIP_CACHE: dict = {}         # (glb path, clip) -> baked clip data, shared by all actors
_SHADER = [None]
_TRIS: dict = {}


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def skin_shader() -> Shader:
    if _SHADER[0] is None:
        folder = Path(__file__).resolve().parent / 'shaders'
        shader = Shader.load(Shader.SL_GLSL, vertex=Filename.fromOsSpecific(str(folder / 'skin.vert')),
                             fragment=Filename.fromOsSpecific(str(folder / 'sketch.frag')))
        if shader is None:
            raise RuntimeError(f'Could not load the character skinning shader from {folder}')
        _SHADER[0] = shader
    return _SHADER[0]


def _skin_format() -> GeomVertexFormat:
    arr = GeomVertexArrayFormat()
    arr.addColumn(InternalName.getVertex(), 3, Geom.NT_float32, Geom.C_point)
    arr.addColumn(InternalName.getNormal(), 3, Geom.NT_float32, Geom.C_normal)
    arr.addColumn(InternalName.getColor(), 4, Geom.NT_uint8, Geom.C_color)
    arr.addColumn(InternalName.make('skin_joints'), 4, Geom.NT_float32, Geom.C_other)
    arr.addColumn(InternalName.make('skin_weights'), 4, Geom.NT_float32, Geom.C_other)
    return GeomVertexFormat.registerFormat(arr)


_VERTEX_DTYPE = np.dtype([('p', '<f4', 3), ('n', '<f4', 3), ('c', 'u1', 4), ('j', '<f4', 4), ('w', '<f4', 4)])


def _axis_matrix(floor: float) -> np.ndarray:
    """glTF mesh space (x, y-up, z-front) -> actor space (-x, z, y - floor): a rotation plus
    the floor offset (the same change the flip-book used; Pass 41 made it mirror-free)."""
    return np.array([[-1.0, 0.0, 0.0, 0.0],
                     [0.0, 0.0, 1.0, 0.0],
                     [0.0, 1.0, 0.0, -floor],
                     [0.0, 0.0, 0.0, 1.0]])


def _bake_clip(glb_path: Path, clip_name: str) -> dict:
    key = (str(Path(glb_path).resolve()), clip_name)
    hit = _CLIP_CACHE.get(key)
    if hit is not None:
        return hit
    skin = GLBIdleSkin(glb_path, clip_name)
    floor = skin.source_floor_y
    c = _axis_matrix(floor)
    c_inv = np.linalg.inv(c)
    count = max(2, int(round(skin.duration * SKIN_SAMPLE_HZ)))
    mats, points = [], []
    for i in range(count + 1):                      # +1: the exact end, so the last span blends too
        t = skin.duration * i / count
        m, p = skin._skin_and_node_points(t, wrap=False)
        # skin matrices re-expressed in actor space, stored transposed (Panda's row-vector
        # layout) so GLSL receives them as column-vector matrices: joint_mats[j] * v
        mats.append(np.transpose(c @ m @ c_inv, (0, 2, 1)).astype(np.float32))
        points.append(np.stack([-p[:, 0], p[:, 2], p[:, 1] - floor], axis=1))
    hit = {'skin': skin, 'duration': skin.duration, 'count': count,
           'mats': np.stack(mats), 'joint_points': np.stack(points)}
    _CLIP_CACHE[key] = hit
    return hit


def _triangles(skin: GLBIdleSkin, index: int, primitive) -> GeomTriangles:
    key = (id(skin.primitives), index)
    tris = _TRIS.get(key)
    if tris is None:
        inds = primitive.indices.reshape(-1)
        big = int(inds.max()) >= 65535
        tris = GeomTriangles(Geom.UHStatic)
        tris.setIndexType(Geom.NT_uint32 if big else Geom.NT_uint16)
        array = tris.modifyVertices()
        array.setNumRows(len(inds))
        memoryview(array).cast('B')[:] = inds.astype(np.uint32 if big else np.uint16).tobytes()
        _TRIS[key] = tris
    return tris


def _color_bytes(color) -> np.ndarray:
    rgba = np.array([color[0], color[1], color[2], color[3]], dtype=np.float32)
    return np.floor(np.clip(rgba, 0.0, 1.0) * np.float32(255.0)).astype(np.uint8)


class SkinnedHumanoidActor:
    """One GPU-skinned mesh per character; drop-in replacement for the flip-book actor."""

    def __init__(self, parent, glb_path: Path, scale: float, name: str = 'humanoid', palette=None,
                 clip_names=None, frame_rate: float = SKIN_SAMPLE_HZ):
        self.glb_path = Path(glb_path)
        self.scale = scale
        self.root = parent.attachNewNode(name)
        self.root.setScale(scale)
        self.palette = palette or [Vec4(0.27, 0.54, 0.92, 1.0), Vec4(0.12, 0.29, 0.63, 1.0)]
        self.frame_rate = float(frame_rate)       # kept for old call sites; sampling is SKIN_SAMPLE_HZ
        self.clips: dict = {}
        self.current_clip = None
        self.last_clip_time = 0.0
        self._shown = None                        # (clip, time) last sent to the GPU
        requested = list(clip_names or ['Idle_Loop', 'Walk_Loop', 'Jog_Fwd_Loop', 'Sprint_Loop', 'Jump_Start',
                                        'Jump_Loop', 'Jump_Land', 'Crouch_Idle_Loop', 'Crouch_Fwd_Loop',
                                        'Fixing_Kneeling'])
        if 'Idle_Loop' not in requested:
            requested.insert(0, 'Idle_Loop')
        for clip in requested:
            self._load_clip(self.glb_path, clip)
        self.skin = self.clips['Idle_Loop']['skin']
        self._build_mesh()
        self.apply_clip('Idle_Loop', 0.0, force=True)

    # ---------------------------------------------------------------- build
    def _build_mesh(self):
        skin = self.skin
        floor = skin.source_floor_y
        fmt = _skin_format()
        self.joint_count = len(skin.joints)
        self.joint_mats = PTA_LMatrix4f.emptyArray(self.joint_count)
        self.mesh = self.root.attachNewNode('skinned_mesh')
        for index, pr in enumerate(skin.primitives):
            n = len(pr.positions)
            block = np.empty(n, dtype=_VERTEX_DTYPE)
            block['p'][:, 0] = -pr.positions[:, 0]
            block['p'][:, 1] = pr.positions[:, 2]
            block['p'][:, 2] = pr.positions[:, 1] - floor
            block['n'][:, 0] = -pr.normals[:, 0]
            block['n'][:, 1] = pr.normals[:, 2]
            block['n'][:, 2] = pr.normals[:, 1]
            block['c'] = _color_bytes(self.palette[index % len(self.palette)])
            block['j'] = pr.joints.astype(np.float32)
            block['w'] = pr.weights.astype(np.float32)
            vdata = GeomVertexData(f'{self.root.getName()}_p{index}', fmt, Geom.UHStatic)
            vdata.setNumRows(n)
            memoryview(vdata.modifyArray(0)).cast('B')[:] = block.tobytes()
            geom = Geom(vdata)
            geom.addPrimitive(_triangles(skin, index, pr))
            node = GeomNode(f'{self.root.getName()}_part_{index}')
            node.addGeom(geom)
            # the bind-pose bounds do not cover a punch or a fall: never cull a character
            node.setBounds(OmniBoundingVolume())
            node.setFinal(True)
            self.mesh.attachNewNode(node)
        self.mesh.setShader(skin_shader(), 10)
        self.mesh.setShaderInput('joint_mats', self.joint_mats)

    def _load_clip(self, glb_path: Path, clip_name: str):
        if clip_name not in self.clips:
            self.clips[clip_name] = _bake_clip(glb_path, clip_name)

    # ---------------------------------------------------------------- queries
    @property
    def height_world(self):
        return self.skin.source_height * self.scale

    def _span(self, clip, clip_time: float, loop: bool = True):
        d = clip['duration']
        t = (float(clip_time) % d) if loop else _clamp(float(clip_time), 0.0, d)
        pos = t / d * clip['count']
        i = min(int(pos), clip['count'] - 1)
        return i, pos - i

    def joint_world_point(self, node_name: str, clip_time: float, render_root) -> Point3:
        clip = self.clips[self.current_clip if self.current_clip in self.clips else 'Idle_Loop']
        i, a = self._span(clip, clip_time)
        idx = self.skin.node_index[node_name]
        p0 = clip['joint_points'][i][idx]
        x, y, z = p0 + (clip['joint_points'][i + 1][idx] - p0) * a
        return self.root.getMat(render_root).xformPoint(Point3(float(x), float(y), float(z)))

    def joint_local_points(self, clip_time: float) -> np.ndarray:
        clip = self.clips[self.current_clip if self.current_clip in self.clips else 'Idle_Loop']
        i, a = self._span(clip, clip_time)
        p0 = clip['joint_points'][i]
        return p0 + (clip['joint_points'][i + 1] - p0) * a

    def foot_world_point(self, side: str, clip_time: float, render_root) -> Point3:
        return self.joint_world_point('foot_l' if side == 'left' else 'foot_r', clip_time, render_root)

    # ---------------------------------------------------------------- play
    def apply_clip(self, clip_name: str, t: float, force: bool = False, loop: bool = True):
        clip = self.clips[clip_name]
        key = (clip_name, float(t), loop)
        self.current_clip = clip_name
        self.last_clip_time = float(t)
        if not force and key == self._shown:
            return
        self._shown = key
        i, a = self._span(clip, t, loop)
        m0 = clip['mats'][i]
        mats = m0 + (clip['mats'][i + 1] - m0) * np.float32(a)
        memoryview(self.joint_mats).cast('B')[:] = mats.tobytes()
