from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

_COMPONENT_DTYPE = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_TYPE_SIZE = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


def _quat_matrix(q):
    x, y, z, w = map(float, q)
    n = x*x + y*y + z*z + w*w
    if n <= 1e-12:
        return np.eye(4, dtype=np.float64)
    s = 2.0 / n
    xx, yy, zz = x*x*s, y*y*s, z*z*s
    xy, xz, yz = x*y*s, x*z*s, y*z*s
    wx, wy, wz = w*x*s, w*y*s, w*z*s
    return np.array([
        [1-(yy+zz), xy-wz, xz+wy, 0],
        [xy+wz, 1-(xx+zz), yz-wx, 0],
        [xz-wy, yz+wx, 1-(xx+yy), 0],
        [0,0,0,1],
    ], dtype=np.float64)


def _trs_matrix(t, r, s):
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
        b = -b
        dot = -dot
    dot = min(1.0, max(-1.0, dot))
    if dot > 0.9995:
        q = a + alpha * (b - a)
        q /= max(np.linalg.norm(q), 1e-12)
        return q
    theta0 = math.acos(dot)
    theta = theta0 * alpha
    sin_theta0 = math.sin(theta0)
    return (math.sin(theta0 - theta) / sin_theta0) * a + (math.sin(theta) / sin_theta0) * b


@dataclass
class Primitive:
    positions: np.ndarray
    normals: np.ndarray
    joints: np.ndarray
    weights: np.ndarray
    indices: np.ndarray
    material_index: int


# Pass 37: the GLB is parsed once per file and shared by every clip/actor.
# Previously every clip of every actor re-read and re-decoded the 7.6 MB file.
_SHARED_CACHE: dict = {}


class GLBIdleSkin:
    """Minimal glTF 2.0 skin/animation reader for the supplied humanoid GLB."""
    def __init__(self, path: Path, animation_name: str = "Idle_Loop"):
        self.path = Path(path)
        key = str(self.path.resolve())
        shared = _SHARED_CACHE.get(key)
        if shared is None:
            shared = self._load_shared()
            _SHARED_CACHE[key] = shared
        (self.json, self.binary, self.parents, self.skin, self.joints, self.inverse_bind,
         self.mesh_node, self.primitives, self.defaults, self.source_floor_y,
         self.source_height, self.node_index) = shared
        self.animation = next(a for a in self.json["animations"] if a.get("name") == animation_name)
        self.animation_name = animation_name
        self.channels = self._prepare_channels(self.animation)
        self.duration = max(float(v["times"][-1]) for v in self.channels)

    def _load_shared(self):
        self.json, self.binary = self._read_glb(self.path)
        parents = self._make_parents()
        skin = self.json["skins"][0]
        joints = list(skin["joints"])
        ibm = self.accessor(skin["inverseBindMatrices"]).astype(np.float64)
        inverse_bind = np.stack([row.reshape((4,4), order='F') for row in ibm], axis=0)
        mesh_node = next(i for i,n in enumerate(self.json["nodes"]) if "mesh" in n and n.get("skin") == 0)
        primitives = self._read_primitives(self.json["nodes"][mesh_node]["mesh"])
        defaults = []
        for node in self.json["nodes"]:
            defaults.append({
                "translation": np.asarray(node.get("translation", [0,0,0]), dtype=np.float64),
                "rotation": np.asarray(node.get("rotation", [0,0,0,1]), dtype=np.float64),
                "scale": np.asarray(node.get("scale", [1,1,1]), dtype=np.float64),
            })
        all_y = np.concatenate([p.positions[:,1] for p in primitives])
        node_index = {n.get("name"): i for i, n in enumerate(self.json["nodes"]) if n.get("name")}
        return (self.json, self.binary, parents, skin, joints, inverse_bind, mesh_node, primitives,
                defaults, float(all_y.min()), float(all_y.max() - all_y.min()), node_index)

    @staticmethod
    def _read_glb(path):
        data = path.read_bytes()
        magic, version, total = struct.unpack_from('<4sII', data, 0)
        if magic != b'glTF' or version != 2 or total != len(data):
            raise ValueError('Expected glTF 2.0 GLB')
        offset = 12
        json_chunk = None
        bin_chunk = None
        while offset < len(data):
            length, chunk_type = struct.unpack_from('<II', data, offset)
            offset += 8
            chunk = data[offset:offset+length]
            offset += length
            if chunk_type == 0x4E4F534A:
                json_chunk = chunk
            elif chunk_type == 0x004E4942:
                bin_chunk = chunk
        if json_chunk is None or bin_chunk is None:
            raise ValueError('GLB missing JSON or BIN chunk')
        return json.loads(json_chunk.decode('utf-8').rstrip('\x00 ')), bin_chunk

    def _make_parents(self):
        parents = {}
        for i, node in enumerate(self.json["nodes"]):
            for child in node.get("children", []):
                parents[child] = i
        return parents

    def accessor(self, index: int):
        acc = self.json["accessors"][index]
        view = self.json["bufferViews"][acc["bufferView"]]
        dtype = np.dtype(_COMPONENT_DTYPE[acc["componentType"]]).newbyteorder('<')
        comps = _TYPE_SIZE[acc["type"]]
        count = int(acc["count"])
        start = int(view.get("byteOffset", 0)) + int(acc.get("byteOffset", 0))
        stride = int(view.get("byteStride", dtype.itemsize * comps))
        if stride == dtype.itemsize * comps:
            out = np.frombuffer(self.binary, dtype=dtype, count=count*comps, offset=start).reshape(count, comps)
        else:
            out = np.ndarray((count, comps), dtype=dtype, buffer=self.binary, offset=start, strides=(stride, dtype.itemsize)).copy()
        if acc["type"] == "SCALAR":
            out = out[:,0]
        if acc.get("normalized"):
            if np.issubdtype(dtype, np.unsignedinteger):
                out = out.astype(np.float32) / np.iinfo(dtype).max
            elif np.issubdtype(dtype, np.signedinteger):
                out = np.maximum(out.astype(np.float32) / np.iinfo(dtype).max, -1.0)
        return np.array(out, copy=True)

    def _read_primitives(self, mesh_index):
        result = []
        mesh = self.json["meshes"][mesh_index]
        for pr in mesh["primitives"]:
            a = pr["attributes"]
            positions = self.accessor(a["POSITION"]).astype(np.float64)
            normals = self.accessor(a["NORMAL"]).astype(np.float64)
            joints = self.accessor(a["JOINTS_0"]).astype(np.int32)
            weights = self.accessor(a["WEIGHTS_0"]).astype(np.float64)
            sums = weights.sum(axis=1, keepdims=True)
            weights = np.divide(weights, sums, out=np.zeros_like(weights), where=sums > 1e-12)
            indices = self.accessor(pr["indices"]).astype(np.int32).reshape(-1)
            result.append(Primitive(positions, normals, joints, weights, indices, int(pr.get("material", 0))))
        return result

    def _prepare_channels(self, animation):
        channels = []
        for ch in animation["channels"]:
            sampler = animation["samplers"][ch["sampler"]]
            channels.append({
                "node": int(ch["target"]["node"]),
                "path": ch["target"]["path"],
                "times": self.accessor(sampler["input"]).astype(np.float64),
                "values": self.accessor(sampler["output"]).astype(np.float64),
                "interpolation": sampler.get("interpolation", "LINEAR"),
            })
        return channels

    @staticmethod
    def _sample_channel(ch, t):
        times = ch["times"]
        vals = ch["values"]
        if t <= times[0]: return vals[0]
        if t >= times[-1]: return vals[-1]
        i = int(np.searchsorted(times, t, side='right') - 1)
        dt = times[i+1] - times[i]
        alpha = 0.0 if dt <= 0 else float((t - times[i]) / dt)
        if ch["interpolation"] == "STEP": return vals[i]
        if ch["path"] == "rotation": return _slerp(vals[i], vals[i+1], alpha)
        return vals[i] * (1.0-alpha) + vals[i+1] * alpha

    def _global_matrices(self, t):
        trs = [{k:v.copy() for k,v in d.items()} for d in self.defaults]
        for ch in self.channels:
            trs[ch["node"]][ch["path"]] = self._sample_channel(ch, t)
        local = [_trs_matrix(v["translation"], v["rotation"], v["scale"]) for v in trs]
        global_m = [None] * len(local)
        def resolve(i):
            if global_m[i] is not None: return global_m[i]
            parent = self.parents.get(i)
            global_m[i] = local[i] if parent is None else resolve(parent) @ local[i]
            return global_m[i]
        for i in range(len(local)): resolve(i)
        return global_m

    def skin_matrices(self, t):
        return self._skin_and_node_points(t)[0]

    def _skin_and_node_points(self, t, wrap: bool = True):
        """Skinning matrices plus every node's origin in mesh space, from one solve."""
        t = float(t % self.duration) if wrap else float(t)
        globals_ = self._global_matrices(t)
        inv_mesh = np.linalg.inv(globals_[self.mesh_node])
        mats = np.stack([inv_mesh @ globals_[node] @ self.inverse_bind[i] for i,node in enumerate(self.joints)], axis=0)
        points = np.stack([(inv_mesh @ g)[:3, 3] for g in globals_], axis=0)
        return mats, points

    def node_points(self, t, wrap: bool = True):
        """Mesh-space origin of every glTF node at time t (shape: nodes x 3)."""
        return self._skin_and_node_points(t, wrap)[1]

    def pose(self, t):
        return self.pose_with_points(t)[0]

    def pose_with_points(self, t):
        mats, points = self._skin_and_node_points(t)
        return self._deform(mats), points

    def _deform(self, mats):
        posed = []
        for pr in self.primitives:
            nverts = len(pr.positions)
            hp = np.concatenate([pr.positions, np.ones((nverts,1), dtype=np.float64)], axis=1)
            outp = np.zeros((nverts,4), dtype=np.float64)
            outn = np.zeros((nverts,3), dtype=np.float64)
            for slot in range(4):
                js = pr.joints[:,slot]
                w = pr.weights[:,slot]
                selected = mats[js]
                outp += np.einsum('nij,nj->ni', selected, hp) * w[:,None]
                outn += np.einsum('nij,nj->ni', selected[:,:3,:3], pr.normals) * w[:,None]
            norm = np.linalg.norm(outn, axis=1, keepdims=True)
            outn = np.divide(outn, norm, out=np.zeros_like(outn), where=norm > 1e-12)
            posed.append((outp[:,:3], outn))
        return posed
