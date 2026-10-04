"""Vectorized HoloVerse ring terrain heights (Pass 282.51).

``ring_height_grid`` returns exactly what ``CommandHubApp.world_height_at`` in
world.py returns, for whole arrays of points that lie inside one surface ring.
The ground mesh builder samples thousands of vertices per sector; doing that
through the scalar Python height function made ring entry stall (Ice needed
about 45 microseconds per sample because of the Frost Circuit lookup).

The scalar path in world.py stays the authority for walking, props and
collision.  ``tools/validate_282_51_ring_ground.py`` compares the two on random
points of every ring, so the formulas here must be kept in step with
``biome_height_offset_at`` and the region relief helpers.

Pure numpy + stdlib; no Panda3D import.
"""
from __future__ import annotations

import math

import numpy as np

from holoverse.desert_region import DESERT_DUNE_WAVES
from holoverse.frost_track import FROST_TRACK_HALF_WIDTH, sampled_world_centerline
from holoverse.hills_region import HILLS_REPEAT_BANDS, _HILLS_REPEAT_PRECOMPUTED
from holoverse.ice_region import ICE_GLACIAL_WAVES

TAU = math.tau
HUB_GROUND_LEVEL = 0.03            # world.py CommandHubApp.hub_ground_level()
BIOME_TRANSITION_BLEND = 0.080     # world.py BIOME_TRANSITION_BLEND
CORRIDOR_DEGREES = (-90.0, 0.0, 90.0, 180.0)  # world.py BIOME_CORRIDOR_DEGREES
CORRIDOR_HALF_WIDTH = 0.058

_HILLS_TABLES = tuple(np.asarray(rows, dtype=np.float64) for rows in _HILLS_REPEAT_PRECOMPUTED)
_TRACK = np.asarray(sampled_world_centerline(), dtype=np.float64)
_TRACK_MIX_FULL_DISTANCE = FROST_TRACK_HALF_WIDTH * 0.70 + 92.0 + 1.0
_TRACK_BOX = (
    float(_TRACK[:, 0].min()) - _TRACK_MIX_FULL_DISTANCE,
    float(_TRACK[:, 1].min()) - _TRACK_MIX_FULL_DISTANCE,
    float(_TRACK[:, 0].max()) + _TRACK_MIX_FULL_DISTANCE,
    float(_TRACK[:, 1].max()) + _TRACK_MIX_FULL_DISTANCE,
)


def _smootherstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _smoothstep01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _lerp(a, b, t):
    return a + (b - a) * t


def corridor_weight(angle, lane_half_width: float = CORRIDOR_HALF_WIDTH):
    half = max(0.010, float(lane_half_width))
    best = np.zeros_like(angle)
    for deg in CORRIDOR_DEGREES:
        d = np.abs(np.mod(angle - math.radians(deg) + math.pi, TAU) - math.pi)
        w = np.where(d < half, 1.0 - _smootherstep(d / half), 0.0)
        best = np.maximum(best, w)
    return np.clip(best, 0.0, 1.0)


def repeating_hills_relief(x, y, r0: float, r1: float):
    radius = np.hypot(x, y)
    span = max(1.0, float(r1) - float(r0))
    angle = np.mod(np.arctan2(y, x), TAU)
    scores = []
    for band_idx, (band_t, repeat_count, radial_half, tangent_half, phase) in enumerate(HILLS_REPEAT_BANDS):
        n = int(repeat_count)
        cell = TAU / float(n)
        idx = np.mod(np.round((angle - float(phase)) / cell).astype(np.int64), n)
        table = _HILLS_TABLES[band_idx]
        radial_jitter = table[idx, 0]
        angle_jitter = table[idx, 1]
        amp = table[idx, 2]
        center_t = np.clip(float(band_t) + radial_jitter, 0.08, 0.92)
        center_r = float(r0) + span * center_t
        center_a = np.mod(float(phase) + idx * cell + angle_jitter, TAU)
        da = np.mod(angle - center_a + math.pi, TAU) - math.pi
        dr = radius - center_r
        tangent_distance = da * center_r
        q = dr * dr / (float(radial_half) ** 2) + tangent_distance * tangent_distance / (float(tangent_half) ** 2)
        u = 1.0 - q
        mound = u * u * (3.0 - 2.0 * u)
        scores.append(np.where(q < 1.0, amp * mound, 0.0))
    stack = np.sort(np.stack(scores, axis=0), axis=0)
    strongest = np.maximum(stack[-1], 0.0)
    second = np.maximum(stack[-2], 0.0)
    shoulder = strongest + second * 0.22
    low_roll = 0.07 * (0.5 + 0.5 * np.sin(angle * 3.0 + radius * 0.0061))
    return np.maximum(0.0, shoulder + low_roll)


def desert_dune_relief(x, y, r0: float, r1: float):
    radius = np.hypot(x, y)
    span = max(1.0, float(r1) - float(r0))
    ring_t = np.clip((radius - float(r0)) / span, 0.0, 1.0)
    total = np.zeros_like(x)
    weight = 0.0
    for heading, wavelength, amp, phase, warp_scale in DESERT_DUNE_WAVES:
        c = math.cos(float(heading)); s = math.sin(float(heading))
        along = x * c + y * s
        across = -x * s + y * c
        warp = np.sin(across / float(warp_scale) * TAU + float(phase) * 0.45) * 0.55
        wave = np.sin((along / float(wavelength)) * TAU + float(phase) + warp)
        crest = _smoothstep01(0.5 + 0.5 * wave) ** 1.65
        total = total + crest * float(amp)
        weight += float(amp)
    dunes = total / max(1e-6, weight)
    broad = 0.5 + 0.5 * np.sin(ring_t * TAU * 2.35 + np.arctan2(y, x) * 1.4)
    return 0.12 + dunes * 1.68 + broad * 0.22


def frost_track_distance(x, y):
    """Same result as frost_track.nearest_centerline_distance (including its
    vertex-snapping projection), vectorized over points."""
    px = x[..., None]
    py = y[..., None]
    ax = _TRACK[:, 0]; ay = _TRACK[:, 1]
    bx = np.roll(ax, -1); by = np.roll(ay, -1)
    vx = bx - ax; vy = by - ay
    den = vx * vx + vy * vy
    dot = (px - ax) * vx + (py - ay) * vy
    t = np.where(den <= 1e-9, 0.0, np.maximum(0.0, np.minimum(1.0, dot) / np.where(den <= 1e-9, 1.0, den)))
    qx = ax + vx * t; qy = ay + vy * t
    d2 = (px - qx) ** 2 + (py - qy) ** 2
    return np.sqrt(np.min(d2, axis=-1))


def ice_glacial_relief(x, y, r0: float, r1: float, track_radius: float):
    radius = np.hypot(x, y)
    total = np.zeros_like(x)
    weight = 0.0
    for heading, wavelength, amp, phase in ICE_GLACIAL_WAVES:
        c = math.cos(heading); s = math.sin(heading)
        along = x * c + y * s
        across = -x * s + y * c
        warp = np.sin(across / 620.0 * TAU + phase * 0.4) * 0.42
        wave = np.sin(along / wavelength * TAU + phase + warp)
        ridge = (1.0 - np.abs(wave)) ** 1.65
        total = total + ridge * amp
        weight += amp
    relief = total / max(1e-6, weight)
    broad = 0.5 + 0.5 * np.sin(radius * 0.0072 + np.arctan2(y, x) * 2.2)
    raw = 0.14 + relief * 1.46 + broad * 0.18
    track_mix = np.ones_like(x)
    # Beyond ~119 m from the course the mix is exactly 1, so only points inside
    # the course bounding box (plus that margin) need the segment search.
    near = ((x >= _TRACK_BOX[0]) & (x <= _TRACK_BOX[2]) & (y >= _TRACK_BOX[1]) & (y <= _TRACK_BOX[3]))
    if np.any(near):
        dist = frost_track_distance(x[near], y[near])
        track_mix[near] = _smoothstep01((dist - FROST_TRACK_HALF_WIDTH * 0.70) / 92.0)
    calm = 0.18 + relief * 0.16
    return calm * (1.0 - track_mix) + raw * track_mix


def ring_offset_grid(x, y, ring: dict):
    """biome_height_offset_at for points inside ``ring`` (finite land rings)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    kind = str(ring.get("kind", ""))
    r0 = float(ring["r0"]); r1 = float(ring["r1"])
    if kind in ("flat", "", "metropolis", "water"):
        if kind in ("metropolis", "water"):
            raise ValueError(f"ring kind {kind!r} is not a sector-ground ring")
        return np.zeros_like(x)
    radius = np.sqrt(x * x + y * y)
    span = max(1.0, r1 - r0)
    t = np.clip((radius - r0) / span, 0.0, 1.0)
    seam_blend = max(0.04, BIOME_TRANSITION_BLEND)
    seam_in = _smootherstep(np.clip(t / seam_blend, 0.0, 1.0))
    seam_out = _smootherstep(np.clip((1.0 - t) / seam_blend, 0.0, 1.0))
    envelope = np.sin(math.pi * t) * seam_in * seam_out
    envelope = np.maximum(envelope, 0.0)
    angle = np.arctan2(y, x)
    h = float(ring.get("height", 0.0))
    corridor = corridor_weight(angle)
    corridor_scale = _lerp(1.0, 0.24, corridor)
    if kind == "forest":
        und = 0.52 + 0.30 * np.sin(angle * 5.0 + radius * 0.010) + 0.18 * np.sin(angle * 11.0 - radius * 0.006)
        root_swell = 0.16 * np.cos(x * 0.006 - y * 0.004)
        value = h * (envelope ** 1.04) * np.clip(und + root_swell, 0.16, 1.12)
    elif kind == "hills":
        mound = repeating_hills_relief(x, y, r0, r1)
        broad = 0.12 + 0.08 * np.sin(angle * 2.0 - radius * 0.0031) + 0.05 * np.cos(x * 0.0022 + y * 0.0016)
        profile = np.clip(broad + mound, 0.04, 1.92)
        value = h * (envelope ** 1.14) * profile * _lerp(1.0, 0.14, corridor)
    elif kind == "mushroom":
        ridge = np.sin(angle * 3.2 + radius * 0.0042)
        cross = np.sin(angle * 7.0 - radius * 0.0064)
        pocket = np.cos(x * 0.0030 + y * 0.0044)
        mound = np.abs(np.sin(angle * 4.5 + radius * 0.0028)) * 0.34
        rolling = 0.48 + 0.34 * ridge + 0.22 * cross + 0.18 * pocket + mound
        value = h * (envelope ** 1.10) * np.clip(rolling, 0.08, 1.28)
    elif kind == "desert":
        dune = desert_dune_relief(x, y, r0, r1)
        value = h * (envelope ** 1.10) * dune * _lerp(1.0, 0.18, corridor)
    elif kind == "ice":
        glacial = ice_glacial_relief(x, y, r0, r1, (r0 + r1) * 0.5)
        value = h * (envelope ** 1.08) * glacial * _lerp(1.0, 0.28, corridor)
    elif kind == "urban":
        block = np.where(np.mod(np.floor(np.mod(angle, TAU) / (TAU / 16.0)), 2) == 0, 1.0, 0.62)
        crater = 0.24 * np.sin(x * 0.0082 + y * 0.0051) + 0.18 * np.cos(x * 0.0041 - y * 0.0093)
        berms = 0.22 * np.abs(np.sin(angle * 10.0 + radius * 0.0044))
        value = h * envelope * np.clip(0.28 + 0.42 * block + crater + berms, 0.10, 1.18)
    else:
        value = np.zeros_like(x)
    return value * corridor_scale


def ring_height_grid(x, y, ring: dict):
    """World height (hub ground level + ring offset) for points inside ``ring``."""
    return HUB_GROUND_LEVEL + ring_offset_grid(x, y, ring)
