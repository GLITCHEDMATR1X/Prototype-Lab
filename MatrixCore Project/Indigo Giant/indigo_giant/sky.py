"""Pass 44 — the sky.

A camera-centred dome drawn behind everything:
  * the horizon is exactly the fog colour, so fogged terrain melts into it with no seam;
  * the zenith follows the time of day (pale teal noon, violet dusk, deep indigo night);
  * a soft sun disc by day, a small pale moon by night (both sit where the shadow light is);
  * a warm glow along the horizon under a low sun;
  * stars fade in after dusk and out before dawn.

The dome is hidden from the shadow camera, ignores lights, fog and the scene tint, and costs
one small draw call.  All the work is in shaders/sky.vert + sky.frag (GLSL 1.20, like the
rest of the game).
"""
from __future__ import annotations

import math

from panda3d.core import (Filename, Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat,
                          GeomVertexWriter, Shader, Vec3, Vec4)

from . import paths                 # Pass 62: where the game files are

DOME_RADIUS = 60.0

# (hour, zenith colour).  The horizon always uses the fog colour from daycycle.palette_at.
_ZENITH = (
    (0.0, (0.035, 0.045, 0.10)),
    (4.6, (0.035, 0.045, 0.10)),
    (6.0, (0.42, 0.46, 0.64)),
    (8.0, (0.60, 0.72, 0.78)),
    (15.8, (0.60, 0.72, 0.78)),
    (17.8, (0.46, 0.44, 0.62)),
    (19.2, (0.035, 0.045, 0.10)),
    (24.0, (0.035, 0.045, 0.10)),
)


def _smooth(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def zenith_at(hour: float):
    for (h0, c0), (h1, c1) in zip(_ZENITH, _ZENITH[1:]):
        if h0 <= hour <= h1:
            t = _smooth((hour - h0) / max(h1 - h0, 1e-6))
            return tuple(a + (b - a) * t for a, b in zip(c0, c1))
    return _ZENITH[0][1]


def night_amount(hour: float) -> float:
    """0 by day, 1 in deep night (stars, moon)."""
    if 5.8 <= hour <= 18.2:
        return 0.0
    if 18.2 < hour < 19.4:
        return _smooth((hour - 18.2) / 1.2)
    if 4.6 < hour < 5.8:
        return _smooth((5.8 - hour) / 1.2)
    return 1.0


def low_sun_amount(hour: float) -> float:
    """1 around sunrise / sunset, for the horizon glow."""
    return max(math.exp(-((hour - 6.4) / 0.9) ** 2), math.exp(-((hour - 17.7) / 0.9) ** 2))


def _make_dome(rings: int = 16, segments: int = 32) -> GeomNode:
    vdata = GeomVertexData('sky', GeomVertexFormat.getV3(), Geom.UHStatic)
    vdata.setNumRows((rings + 1) * (segments + 1))
    w = GeomVertexWriter(vdata, 'vertex')
    for r in range(rings + 1):
        # from a little below the horizon (-15 deg) up to the zenith
        el = math.radians(-15.0 + 105.0 * r / rings)
        for s in range(segments + 1):
            az = 2.0 * math.pi * s / segments
            w.addData3(math.cos(el) * math.sin(az) * DOME_RADIUS, math.cos(el) * math.cos(az) * DOME_RADIUS,
                       math.sin(el) * DOME_RADIUS)
    tris = GeomTriangles(Geom.UHStatic)
    row = segments + 1
    for r in range(rings):
        for s in range(segments):
            a, b = r * row + s, r * row + s + 1
            c, d = a + row, b + row
            tris.addVertices(a, c, b)       # faces inward
            tris.addVertices(b, c, d)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode('sky_dome')
    node.addGeom(geom)
    return node


class SkyDome:
    def __init__(self, camera, hide_mask=None):
        folder = paths.SHADERS
        shader = Shader.load(Shader.SL_GLSL, vertex=Filename.fromOsSpecific(str(folder / 'sky.vert')),
                             fragment=Filename.fromOsSpecific(str(folder / 'sky.frag')))
        if shader is None:
            raise RuntimeError(f'Could not load the sky shader from {folder}')
        self.np = camera.attachNewNode(_make_dome())
        self.np.setCompass()                        # follows the camera, never turns with it
        self.np.setShader(shader, 100)
        self.np.setBin('background', 0)
        self.np.setDepthWrite(False)
        self.np.setDepthTest(False)
        self.np.setLightOff(100)
        self.np.setFogOff(100)
        self.np.setColorScaleOff(100)
        self.np.setTwoSided(True)
        if hide_mask is not None:
            self.np.hide(hide_mask)                 # never in the shadow map
        self.set_state(12.0, Vec3(0, 0, 1), (0.91, 0.88, 0.82))

    def set_state(self, hour: float, to_light: Vec3, fog_rgb):
        night = night_amount(hour)
        z = zenith_at(hour)
        d = Vec3(to_light)
        d.normalize()
        self.np.setShaderInput('sky_horizon', Vec4(fog_rgb[0], fog_rgb[1], fog_rgb[2], 1.0))
        self.np.setShaderInput('sky_zenith', Vec4(z[0], z[1], z[2], 1.0))
        self.np.setShaderInput('sky_light_dir', d)
        # x = night (stars + moon), y = warm low-sun glow, z = disc size (cosine), w = disc strength
        by_day = 6.0 <= hour <= 18.0
        disc_cos = 0.99965 if by_day else 0.99988
        # the sun eases in / out at the horizon; the moon fades with the night
        strength = _smooth(min(hour - 6.0, 18.0 - hour) / 0.3) if by_day else night
        self.np.setShaderInput('sky_params', Vec4(night, low_sun_amount(hour), disc_cos, strength))
        disc = (1.0, 0.96, 0.86) if by_day else (0.86, 0.89, 0.96)
        self.np.setShaderInput('sky_disc_colour', Vec4(disc[0] * strength, disc[1] * strength, disc[2] * strength, 1.0))

    def destroy(self):
        self.np.removeNode()
