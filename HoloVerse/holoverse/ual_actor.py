"""Skinned humanoid characters for HoloVerse (Pass 282.56): Nyx (the giant) and Orbit.

The same rigged mannequin the Indigo Giant archive uses for its giant and its
human (``assets/characters/UAL1_Standard.glb``, the Quaternius Universal
Animation Library, CC0), so HoloVerse's Nyx and Orbit read as the same
pair.  This is a trimmed port of that game's ``gltf_idle.GLBIdleSkin`` and
``skinned_actor.SkinnedHumanoidActor`` with HoloVerse's own GLSL 130 shader
(sun, sky ambient, fog, and an optional fresnel glow rim):

* the GLB is parsed once per process; each clip's 65 joint matrices are
  sampled at 30 Hz once and blended per frame on the GPU;
* without GLSL the mesh is posed once on the CPU (the first frame of its idle)
  and drawn with baked lighting, so the characters still appear.
"""
from __future__ import annotations

import json
import math
import time
import struct
from pathlib import Path

import numpy as np
from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomVertexArrayFormat, GeomVertexData,
                          GeomVertexFormat, InternalName, OmniBoundingVolume, PTA_LMatrix4f, Shader, Vec3, Vec4)

ROOT = Path(__file__).resolve().parents[1]
GLB_PATH = ROOT / "assets" / "characters" / "UAL1_Standard.glb"
SKIN_SAMPLE_HZ = 30.0

_COMPONENT_DTYPE = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_TYPE_SIZE = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
_SHARED: dict = {}
_CLIPS: dict = {}
_SHADER = [None, False]


# --------------------------------------------------------------------------
# glTF 2.0 skin reader (from the Indigo Giant's gltf_idle.py)
# --------------------------------------------------------------------------
def _quat_matrix(q):
    x, y, z, w = map(float, q)
    n = x * x + y * y + z * z + w * w
    if n <= 1e-12:
        return np.eye(4)
    s = 2.0 / n
    xx, yy, zz = x * x * s, y * y * s, z * z * s
    xy, xz, yz = x * y * s, x * z * s, y * z * s
    wx, wy, wz = w * x * s, w * y * s, w * z * s
    return np.array([[1 - (yy + zz), xy - wz, xz + wy, 0], [xy + wz, 1 - (xx + zz), yz - wx, 0],
                     [xz - wy, yz + wx, 1 - (xx + yy), 0], [0, 0, 0, 1]], dtype=np.float64)


def _trs(t, r, s):
    m = _quat_matrix(r)
    m[:3, 0] *= s[0]
    m[:3, 1] *= s[1]
    m[:3, 2] *= s[2]
    m[:3, 3] = t
    return m


def _slerp(a, b, alpha):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    dot = float(np.dot(a, b))
    if dot < 0.0:
        b, dot = -b, -dot
    dot = min(1.0, max(-1.0, dot))
    if dot > 0.9995:
        q = a + alpha * (b - a)
        return q / max(np.linalg.norm(q), 1e-12)
    theta0 = math.acos(dot)
    theta = theta0 * alpha
    s0 = math.sin(theta0)
    return (math.sin(theta0 - theta) / s0) * a + (math.sin(theta) / s0) * b


class GLBSkin:
    """The parsed GLB: skin, joints, bind-pose primitives and animations."""

    def __init__(self, path: Path):
        data = Path(path).read_bytes()
        magic, version, total = struct.unpack_from("<4sII", data, 0)
        if magic != b"glTF" or version != 2 or total != len(data):
            raise ValueError("expected a glTF 2.0 GLB")
        offset, js, binary = 12, None, None
        while offset < len(data):
            length, kind = struct.unpack_from("<II", data, offset)
            offset += 8
            chunk = data[offset:offset + length]
            offset += length
            if kind == 0x4E4F534A:
                js = chunk
            elif kind == 0x004E4942:
                binary = chunk
        self.json = json.loads(js.decode("utf-8").rstrip("\x00 "))
        self.binary = binary
        self.parents = {c: i for i, n in enumerate(self.json["nodes"]) for c in n.get("children", [])}
        skin = self.json["skins"][0]
        self.joints = list(skin["joints"])
        ibm = self.accessor(skin["inverseBindMatrices"]).astype(np.float64)
        self.inverse_bind = np.stack([row.reshape((4, 4), order="F") for row in ibm], axis=0)
        self.mesh_node = next(i for i, n in enumerate(self.json["nodes"]) if "mesh" in n and n.get("skin") == 0)
        self.primitives = self._primitives(self.json["nodes"][self.mesh_node]["mesh"])
        self.defaults = [{"translation": np.asarray(n.get("translation", [0, 0, 0]), dtype=np.float64),
                          "rotation": np.asarray(n.get("rotation", [0, 0, 0, 1]), dtype=np.float64),
                          "scale": np.asarray(n.get("scale", [1, 1, 1]), dtype=np.float64)} for n in self.json["nodes"]]
        ys = np.concatenate([p[0][:, 1] for p in self.primitives])
        self.floor = float(ys.min())
        self.height = float(ys.max() - ys.min())
        self.animations = {a.get("name"): a for a in self.json.get("animations", [])}

    def accessor(self, index: int):
        acc = self.json["accessors"][index]
        view = self.json["bufferViews"][acc["bufferView"]]
        dtype = np.dtype(_COMPONENT_DTYPE[acc["componentType"]]).newbyteorder("<")
        comps = _TYPE_SIZE[acc["type"]]
        count = int(acc["count"])
        start = int(view.get("byteOffset", 0)) + int(acc.get("byteOffset", 0))
        stride = int(view.get("byteStride", dtype.itemsize * comps))
        if stride == dtype.itemsize * comps:
            out = np.frombuffer(self.binary, dtype=dtype, count=count * comps, offset=start).reshape(count, comps)
        else:
            out = np.ndarray((count, comps), dtype=dtype, buffer=self.binary, offset=start, strides=(stride, dtype.itemsize)).copy()
        if acc["type"] == "SCALAR":
            out = out[:, 0]
        if acc.get("normalized"):
            if np.issubdtype(dtype, np.unsignedinteger):
                out = out.astype(np.float32) / np.iinfo(dtype).max
            elif np.issubdtype(dtype, np.signedinteger):
                out = np.maximum(out.astype(np.float32) / np.iinfo(dtype).max, -1.0)
        return np.array(out, copy=True)

    def _primitives(self, mesh_index):
        out = []
        for pr in self.json["meshes"][mesh_index]["primitives"]:
            a = pr["attributes"]
            weights = self.accessor(a["WEIGHTS_0"]).astype(np.float64)
            sums = weights.sum(axis=1, keepdims=True)
            weights = np.divide(weights, sums, out=np.zeros_like(weights), where=sums > 1e-12)
            out.append((self.accessor(a["POSITION"]).astype(np.float64), self.accessor(a["NORMAL"]).astype(np.float64),
                         self.accessor(a["JOINTS_0"]).astype(np.int32), weights,
                         self.accessor(pr["indices"]).astype(np.int32).reshape(-1)))
        return out

    def _channels(self, name):
        anim = self.animations[name]
        out = []
        for ch in anim["channels"]:
            sampler = anim["samplers"][ch["sampler"]]
            out.append((int(ch["target"]["node"]), ch["target"]["path"], self.accessor(sampler["input"]).astype(np.float64),
                        self.accessor(sampler["output"]).astype(np.float64), sampler.get("interpolation", "LINEAR")))
        return out

    @staticmethod
    def _sample(ch, t):
        _node, path, times, vals, interp = ch
        if t <= times[0]:
            return vals[0]
        if t >= times[-1]:
            return vals[-1]
        i = int(np.searchsorted(times, t, side="right") - 1)
        dt = times[i + 1] - times[i]
        a = 0.0 if dt <= 0 else float((t - times[i]) / dt)
        if interp == "STEP":
            return vals[i]
        if path == "rotation":
            return _slerp(vals[i], vals[i + 1], a)
        return vals[i] * (1.0 - a) + vals[i + 1] * a

    def skin_matrices(self, channels, t):
        trs = [{k: v.copy() for k, v in d.items()} for d in self.defaults]
        for ch in channels:
            trs[ch[0]][ch[1]] = self._sample(ch, t)
        local = [_trs(v["translation"], v["rotation"], v["scale"]) for v in trs]
        glob = [None] * len(local)

        def resolve(i):
            if glob[i] is None:
                parent = self.parents.get(i)
                glob[i] = local[i] if parent is None else resolve(parent) @ local[i]
            return glob[i]
        for i in range(len(local)):
            resolve(i)
        inv_mesh = np.linalg.inv(glob[self.mesh_node])
        return np.stack([inv_mesh @ glob[node] @ self.inverse_bind[j] for j, node in enumerate(self.joints)], axis=0)


def skin_for(path: Path = GLB_PATH) -> GLBSkin:
    key = str(Path(path).resolve())
    if key not in _SHARED:
        _SHARED[key] = GLBSkin(path)
    return _SHARED[key]


def _axis(floor: float):
    """glTF (x, y-up, z-front) -> HoloVerse actor space (-x, z, y - floor), facing +y."""
    return np.array([[-1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 1.0, 0.0, -floor], [0.0, 0.0, 0.0, 1.0]])


_BAKING: dict = {}


def bake_clip_step(name: str, budget_s: float = 0.008, path: Path = GLB_PATH):
    """Bake a clip a slice at a time. Returns the finished clip, or None while
    frames remain, so a caller can spread the work over several frames."""
    key = (str(Path(path).resolve()), name)
    if key in _CLIPS:
        return _CLIPS[key]
    job = _BAKING.get(key)
    if job is None:
        skin = skin_for(path)
        channels = skin._channels(name)
        duration = max(float(ch[2][-1]) for ch in channels)
        c = _axis(skin.floor)
        job = {"skin": skin, "channels": channels, "duration": duration, "c": c, "c_inv": np.linalg.inv(c),
               "count": max(2, int(round(duration * SKIN_SAMPLE_HZ))), "mats": []}
        _BAKING[key] = job
    t0 = time.perf_counter()
    count = job["count"]
    while len(job["mats"]) <= count:
        i = len(job["mats"])
        m = job["skin"].skin_matrices(job["channels"], job["duration"] * i / count)
        job["mats"].append(np.transpose(job["c"] @ m @ job["c_inv"], (0, 2, 1)).astype(np.float32))
        if budget_s is not None and time.perf_counter() - t0 >= budget_s and len(job["mats"]) <= count:
            return None
    clip = {"duration": job["duration"], "count": count, "mats": np.stack(job["mats"])}
    _CLIPS[key] = clip
    _BAKING.pop(key, None)
    return clip


def bake_clip(name: str, path: Path = GLB_PATH) -> dict:
    """Joint matrices for a clip at 30 Hz in actor space (transposed for Panda)."""
    return bake_clip_step(name, None, path)


# --------------------------------------------------------------------------
# Shader
# --------------------------------------------------------------------------
_VERT = """
#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat3 p3d_NormalMatrix;
uniform mat4 joint_mats[65];
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 p3d_Color;
in vec4 skin_joints;
in vec4 skin_weights;
out vec3 v_world_normal;
out vec3 v_eye_normal;
out vec3 v_eye_pos;
out vec4 v_color;
void main() {
    mat4 skin = joint_mats[int(skin_joints.x + 0.5)] * skin_weights.x
              + joint_mats[int(skin_joints.y + 0.5)] * skin_weights.y
              + joint_mats[int(skin_joints.z + 0.5)] * skin_weights.z
              + joint_mats[int(skin_joints.w + 0.5)] * skin_weights.w;
    vec4 vertex = skin * p3d_Vertex;
    vec3 normal = mat3(skin[0].xyz, skin[1].xyz, skin[2].xyz) * p3d_Normal;
    gl_Position = p3d_ModelViewProjectionMatrix * vertex;
    v_world_normal = normalize(mat3(p3d_ModelMatrix) * normal);
    v_eye_normal = normalize(p3d_NormalMatrix * normal);
    v_eye_pos = (p3d_ModelViewMatrix * vertex).xyz;
    v_color = p3d_Color;
}
"""

_FRAG = """
#version 130
uniform struct p3d_FogParameters { vec4 color; float density; float start; float end; float scale; } p3d_Fog;
uniform vec3 u_sun_dir;
uniform vec3 u_sun_color;
uniform vec3 u_sky_ambient;
uniform vec3 u_ground_bounce;
uniform vec4 u_rim;            // rgb glow colour, a = strength
in vec3 v_world_normal;
in vec3 v_eye_normal;
in vec3 v_eye_pos;
in vec4 v_color;
void main() {
    vec3 n = normalize(v_world_normal);
    float ndl = clamp((dot(n, normalize(u_sun_dir)) + 0.25) / 1.25, 0.0, 1.0);
    vec3 ambient = mix(u_ground_bounce, u_sky_ambient, n.z * 0.5 + 0.5);
    vec3 colour = v_color.rgb * (ambient + u_sun_color * ndl);
    vec3 view = normalize(-v_eye_pos);
    float fres = pow(1.0 - clamp(abs(dot(view, normalize(v_eye_normal))), 0.0, 1.0), 2.4);
    colour += u_rim.rgb * (fres * u_rim.a + u_rim.a * 0.12);
    float dist = length(v_eye_pos);
    float fog = 1.0;
    if (p3d_Fog.end > p3d_Fog.start) {
        fog = clamp((p3d_Fog.end - dist) / (p3d_Fog.end - p3d_Fog.start), 0.0, 1.0);
    }
    gl_FragColor = vec4(mix(p3d_Fog.color.rgb, colour, fog), 1.0);
}
"""


def skin_shader(gsg=None):
    """The skinning shader, or None where GLSL 1.30 is unavailable."""
    if _SHADER[1]:
        return _SHADER[0]
    _SHADER[1] = True
    try:
        from holoverse import ring_ground
        if ring_ground.ground_shader(gsg) is None:
            return None
        _SHADER[0] = Shader.make(Shader.SL_GLSL, vertex=_VERT, fragment=_FRAG)
    except Exception:
        _SHADER[0] = None
    return _SHADER[0]


def _skin_format():
    arr = GeomVertexArrayFormat()
    arr.addColumn(InternalName.getVertex(), 3, Geom.NT_float32, Geom.C_point)
    arr.addColumn(InternalName.getNormal(), 3, Geom.NT_float32, Geom.C_normal)
    arr.addColumn(InternalName.getColor(), 4, Geom.NT_uint8, Geom.C_color)
    arr.addColumn(InternalName.make("skin_joints"), 4, Geom.NT_float32, Geom.C_other)
    arr.addColumn(InternalName.make("skin_weights"), 4, Geom.NT_float32, Geom.C_other)
    return GeomVertexFormat.registerFormat(arr)


_VTX = np.dtype([("p", "<f4", 3), ("n", "<f4", 3), ("c", "u1", 4), ("j", "<f4", 4), ("w", "<f4", 4)])


class SkinnedCharacter:
    """One GPU-skinned mannequin (CPU-posed fallback without GLSL).

    ``height`` is the standing height in metres; ``palette`` gives one RGBA per
    mesh part (the mannequin has two: body and joints); ``rim`` an RGB glow
    colour and strength for the fresnel edge (Indigo's night glow)."""

    def __init__(self, parent, name, height, palette, clips=("Idle_Loop",), rim=(0.0, 0.0, 0.0, 0.0), light=None, gsg=None,
                 path: Path = GLB_PATH):
        self.skin = skin_for(path)
        self.path = Path(path)
        self.root = parent.attachNewNode(name)
        self.scale = float(height) / max(1e-6, self.skin.height)
        self.root.setScale(self.scale)
        self.clips = {c: bake_clip(c, path) for c in clips if c in self.skin.animations}
        self.current = "Idle_Loop" if "Idle_Loop" in self.clips else next(iter(self.clips))
        self.shader = skin_shader(gsg)
        self.joint_mats = PTA_LMatrix4f.emptyArray(len(self.skin.joints))
        self._build(palette)
        if self.shader is not None:
            from holoverse import ring_ground as RG
            light = light or {}
            self.mesh.setShader(self.shader, 60)
            self.mesh.setShaderInput("joint_mats", self.joint_mats)
            self.mesh.setShaderInput("u_sun_dir", Vec3(*RG.SUN_DIRECTION))
            self.mesh.setShaderInput("u_sun_color", Vec3(*light.get("sun", RG.SUN_COLOR)))
            self.mesh.setShaderInput("u_sky_ambient", Vec3(*light.get("sky", (0.42, 0.44, 0.50))))
            self.mesh.setShaderInput("u_ground_bounce", Vec3(*light.get("bounce", (0.30, 0.28, 0.30))))
            self.mesh.setShaderInput("u_rim", Vec4(*rim))
            self.play(self.current, 0.0)

    @property
    def height(self):
        return self.skin.height * self.scale

    def _build(self, palette):
        skin = self.skin
        floor = skin.floor
        gpu = self.shader is not None
        if not gpu:
            idle = self.clips[self.current]["mats"][0]
            mats = np.transpose(idle, (0, 2, 1)).astype(np.float64)     # back to column-vector form
        self.mesh = self.root.attachNewNode("ual-mesh")
        fmt = _skin_format()
        for index, (pos, nrm, joints, weights, inds) in enumerate(skin.primitives):
            n = len(pos)
            block = np.empty(n, dtype=_VTX)
            block["p"][:, 0] = -pos[:, 0]
            block["p"][:, 1] = pos[:, 2]
            block["p"][:, 2] = pos[:, 1] - floor
            block["n"][:, 0] = -nrm[:, 0]
            block["n"][:, 1] = nrm[:, 2]
            block["n"][:, 2] = nrm[:, 1]
            rgba = palette[index % len(palette)]
            colour = np.floor(np.clip(np.array(rgba[:4], dtype=np.float32), 0.0, 1.0) * 255.0).astype(np.uint8)
            if not gpu:
                hp = np.concatenate([block["p"].astype(np.float64), np.ones((n, 1))], axis=1)
                outp = np.zeros((n, 4))
                outn = np.zeros((n, 3))
                for slot in range(4):
                    sel = mats[joints[:, slot]]
                    w = weights[:, slot][:, None]
                    outp += np.einsum("nij,nj->ni", sel, hp) * w
                    outn += np.einsum("nij,nj->ni", sel[:, :3, :3], block["n"].astype(np.float64)) * w
                block["p"] = outp[:, :3]
                nl = np.linalg.norm(outn, axis=1, keepdims=True)
                block["n"] = np.divide(outn, nl, out=np.zeros_like(outn), where=nl > 1e-9)
                # Baked light (sun from the ring-ground direction).
                from holoverse import ring_ground as RG
                ndl = np.clip((block["n"] @ np.asarray(RG.SUN_DIRECTION, dtype=np.float32) + 0.25) / 1.25, 0.0, 1.0)
                shade = (0.45 + 0.55 * ndl)[:, None]
                colour = np.clip(colour[None, :3].astype(np.float32) * shade, 0, 255).astype(np.uint8)
                block["c"][:, :3] = colour
                block["c"][:, 3] = 255
            else:
                block["c"] = colour
            block["j"] = joints.astype(np.float32)
            block["w"] = weights.astype(np.float32)
            vdata = GeomVertexData(f"{self.root.getName()}-p{index}", fmt, Geom.UHStatic)
            vdata.setNumRows(n)
            memoryview(vdata.modifyArray(0)).cast("B")[:] = block.tobytes()
            tris = GeomTriangles(Geom.UHStatic)
            big = int(inds.max()) >= 65535
            tris.setIndexType(Geom.NT_uint32 if big else Geom.NT_uint16)
            arr = tris.modifyVertices()
            arr.setNumRows(len(inds))
            memoryview(arr).cast("B")[:] = inds.astype(np.uint32 if big else np.uint16).tobytes()
            geom = Geom(vdata)
            geom.addPrimitive(tris)
            node = GeomNode(f"{self.root.getName()}-part{index}")
            node.addGeom(geom)
            node.setBounds(OmniBoundingVolume())      # skinned poses exceed the bind-pose bounds
            node.setFinal(True)
            self.mesh.attachNewNode(node)
        self.mesh.setTextureOff(10)
        if not gpu:
            self.mesh.setLightOff(1)

    def play(self, clip: str, t: float):
        """Pose the character at time ``t`` (seconds, looping) of ``clip``."""
        if self.shader is None:
            return
        if clip not in self.clips:
            clip = self.current
        self.current = clip
        data = self.clips[clip]
        pos = (float(t) % data["duration"]) / data["duration"] * data["count"]
        i = min(int(pos), data["count"] - 1)
        a = np.float32(pos - i)
        m0 = data["mats"][i]
        mats = m0 + (data["mats"][i + 1] - m0) * a
        memoryview(self.joint_mats).cast("B")[:] = mats.tobytes()

    def destroy(self):
        self.root.removeNode()
